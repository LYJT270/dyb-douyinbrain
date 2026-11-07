"""Bounded, resumable public media downloads; no speech or model calls."""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib import request

from . import douyin_browser, media
from .catalog import fingerprint, select_variant
from .common import artifact_lock, digest, inside, now, read_json, relative, write_json


def inspect_file(path: Path, *, image=False) -> dict:
    probe = shutil.which('ffprobe')
    decoder = shutil.which('ffmpeg')
    if not probe or not decoder:
        raise RuntimeError('缺少 FFmpeg/ffprobe，无法验证下载文件')
    import json
    result = subprocess.run([probe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, check=True, timeout=30, creationflags=media._hidden())
    info = json.loads(result.stdout)
    videos = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
    if not videos:
        raise RuntimeError('素材没有可解码画面，未标记下载成功')
    subprocess.run([decoder, '-nostdin', '-v', 'error', '-i', str(path), '-frames:v', '1',
                    '-an', '-f', 'null', '-'], capture_output=True, check=True, timeout=30,
                   creationflags=media._hidden())
    duration = info.get('format', {}).get('duration')
    return {'width': videos[0].get('width'), 'height': videos[0].get('height'),
            'duration': float(duration) if duration is not None else None,
            'has_audio': any(s.get('codec_type') == 'audio' for s in info.get('streams', [])),
            'validation': 'length_streams_first_frame', 'kind': 'image' if image else 'video'}


def cached_asset(folder: Path, root: Path) -> dict | None:
    manifest = folder / 'asset.json'
    if not manifest.is_file():
        return None
    saved = read_json(manifest)
    path = inside(root, saved['file'])
    if path.is_file() and path.stat().st_size == saved['bytes'] and digest(path) == saved['sha256']:
        return {**saved, 'reused': True}
    raise RuntimeError('已有媒体缓存缺失或被修改，保留现场；请恢复缓存或明确选择新的获取版本')


def source_for_transcript(post, checksum, root):
    """Keep the exact ASR source when another workflow downloaded a different rendition."""
    base = root / '.cache/creator-media' / post['id'] / post['media_fingerprint'][:20]
    for manifest in base.glob('*/asset.json'):
        if read_json(manifest).get('sha256') == checksum:
            asset = cached_asset(manifest.parent, root)
            return {'kind': 'video', 'asset': asset, 'quality': 'recognized_source',
                    'complete': True, 'elapsed_seconds': 0.0}
    return None


def _finish_download(part, target, folder, root, image):
    verified = inspect_file(part, image=image)
    checksum = digest(part)
    part.replace(target)
    saved = {'file': relative(root, target), 'sha256': checksum,
             'bytes': target.stat().st_size, 'created': now(), **verified}
    write_json(folder / 'asset.json', saved)
    return {**saved, 'reused': False}


def download(addresses: list[str], folder: Path, root: Path, *, image=False,
             timeout=300, opener=None) -> dict:
    opener = opener or request.urlopen
    if not addresses:
        raise RuntimeError('此作品尚未取得可用媒体地址，已保留其文字资料')
    with artifact_lock(folder):
        existing = cached_asset(folder, root)
        if existing:
            return existing
        part = folder / 'source.part'
        transfer = folder / 'transfer.json'
        target = folder / ('source.image' if image else 'source.mp4')
        if target.exists():
            raise RuntimeError('存在尚未登记的下载文件，保留现场以便核对')
        previous_transfer = read_json(transfer) if transfer.is_file() else {}
        if part.is_file() and previous_transfer.get('expected_bytes') == part.stat().st_size:
            # A disconnect after the final byte must not turn a complete file into an HTTP 416 loop.
            return _finish_download(part, target, folder, root, image)
        started, last_error = time.monotonic(), None
        # Each alternate URL gets a bounded attempt. There are no unbounded retries.
        for address in addresses[:3]:
            if not address.startswith(('https://', 'http://')):
                continue
            if time.monotonic() - started >= timeout:
                break
            try:
                prior = read_json(transfer) if transfer.is_file() else {}
                offset = part.stat().st_size if part.is_file() else 0
                headers = {'User-Agent': douyin_browser.USER_AGENT, 'Referer': 'https://www.douyin.com/'}
                if offset:
                    headers['Range'] = f'bytes={offset}-'
                    if prior.get('etag') or prior.get('last_modified'):
                        headers['If-Range'] = prior.get('etag') or prior['last_modified']
                remaining = max(1, min(20, timeout - (time.monotonic() - started)))
                with opener(request.Request(address, headers=headers), timeout=remaining) as response:
                    status = response.getcode()
                    expected = None
                    if status == 206:
                        matched = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+|\*)', response.headers.get('Content-Range', ''))
                        if not matched or int(matched[1]) != offset:
                            raise RuntimeError('服务器返回的续传区间不匹配，未拼接文件')
                        if prior.get('etag') and response.headers.get('ETag') and prior['etag'] != response.headers['ETag']:
                            raise RuntimeError('续传媒体版本已变化，未拼接不同版本的数据')
                        if matched[3] != '*':
                            expected = int(matched[3])
                        mode = 'ab'
                    elif status == 200:
                        mode, offset = 'wb', 0
                        if response.headers.get('Content-Length'):
                            expected = int(response.headers['Content-Length'])
                    else:
                        raise RuntimeError(f'下载返回 HTTP {status}')
                    if 'text/html' in response.headers.get('Content-Type', '').lower():
                        raise RuntimeError('媒体地址返回网页，未当成视频保存')
                    if expected and shutil.disk_usage(folder).free < max(0, expected - offset):
                        raise RuntimeError('可用磁盘空间不足以保存此媒体')
                    write_json(transfer, {'etag': response.headers.get('ETag'),
                        'last_modified': response.headers.get('Last-Modified'), 'expected_bytes': expected,
                        'started': now(), 'resumed_at': offset})
                    with part.open(mode) as handle:
                        while True:
                            if time.monotonic() - started >= timeout:
                                raise TimeoutError('单条下载超过时限，保留已下载部分供续跑')
                            block = response.read(256 * 1024)
                            if not block:
                                break
                            handle.write(block)
                    if expected is not None and part.stat().st_size != expected:
                        raise RuntimeError('下载长度不完整，保留已下载部分供续跑')
                return _finish_download(part, target, folder, root, image)
            except Exception as exc:
                last_error = str(exc)
        raise RuntimeError(last_error or '没有可用的媒体地址或下载已超时')


def fetch_post(post: dict, root: Path, *, quality='compact', timeout=300) -> dict:
    started = time.monotonic()
    base = root / '.cache/creator-media' / post['id'] / post['media_fingerprint'][:20]
    if post['kind'] == 'images':
        images = []
        errors = []
        for item in post['images']:
            try:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError('单条作品获取超过时限，已完成图片保留')
                asset = download(item['urls'], base / f"image-{item['index']:03d}", root,
                                 image=True, timeout=remaining)
                images.append({**asset, 'index': item['index']})
            except Exception as exc:
                errors.append({'index': item['index'], 'error': str(exc)})
        return {'kind': 'images', 'images': images, 'errors': errors,
                'complete': bool(images) and not errors and len(images) == len(post['images']),
                'elapsed_seconds': round(time.monotonic() - started, 3)}
    variant = select_variant(post.get('media_variants', []), quality)
    if variant is None:
        raise RuntimeError('此视频的媒体地址缺失，文字和统计数据仍然保留')
    signature = fingerprint({k: variant.get(k) for k in ('uri', 'width', 'height', 'bytes', 'bit_rate', 'address_kind')})[:20]
    asset = download(variant['urls'], base / signature, root, timeout=timeout)
    if variant.get('bytes') and asset['bytes'] != variant['bytes']:
        raise RuntimeError('下载文件长度与当前媒体版本元数据不一致，文件保留，未标记完成')
    return {'kind': 'video', 'asset': asset, 'quality': quality,
            'selected_variant': {k: v for k, v in variant.items() if k != 'urls'},
            'complete': True, 'elapsed_seconds': round(time.monotonic() - started, 3)}
