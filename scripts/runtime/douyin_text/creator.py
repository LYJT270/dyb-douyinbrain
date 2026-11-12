"""Durable creator catalogs, independent download/analysis modes and metered ASR.

The Agent does the semantic/visual work through review packets, never this module.
All task and content paths are workspace relative. No external analysis provider is
introduced and no account credentials are exported with the public business data.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import re
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from urllib.parse import urlsplit

from . import asr, catalog, creator_files, douyin_browser, media, workflow
from .common import ROOT, artifact_lock, digest, inside, now, read_json, relative, write_json

ANALYSIS_SCHEMA = 'creator-analysis-1'
DEFAULT_INSTRUCTION = '分析账号定位、内容特点、选题方向及随时间的变化，所有结论附作品依据。'


def task_path(task_id, root=ROOT):
    if not re.fullmatch(r'creator-[0-9a-f]{16}', task_id):
        raise ValueError('不是有效的博主任务 ID')
    return root / 'runs' / task_id / 'task.json'


def load(task_id, root=ROOT):
    return read_json(task_path(task_id, root))


def save(task, root=ROOT):
    task['updated'] = now()
    write_json(task_path(task['id'], root), task)


def account_dir(task, root):
    return root / 'outputs/creators' / task['account_key']


def records(task, root):
    path = task_path(task['id'], root).parent / 'catalog.json'
    return catalog.chronological(read_json(path).get('posts', [])) if path.is_file() else []


def book(task, root):
    path = account_dir(task, root) / 'state.json'
    return read_json(path) if path.is_file() else {'items': {}}


def save_book(task, state, root):
    write_json(account_dir(task, root) / 'state.json', state)


def require_online_task(task):
    if task.get('offline'):
        raise ValueError('此任务基于已有材料离线分析；新增获取或识别须另建明确授权的在线任务')


def reanalyze(task_id, instruction, *, images=False, parallel_vision=False, root=ROOT):
    """Fork a frozen catalog and existing evidence without refreshing or carrying paid authority."""
    if not instruction.strip():
        raise ValueError('需要新的分析问题')
    source = load(task_id, root)
    with artifact_lock(account_dir(source, root)):
        source = load(task_id, root)
        posts = records(source, root)
        if not posts:
            raise ValueError('原任务没有已保存的作品清单')
        task = copy.deepcopy(source)
        task.update(id='creator-' + uuid.uuid4().hex[:16], created=now(), instruction=instruction.strip(),
                    mode='analyze', status='awaiting_visual_analysis', offline=True,
                    authorizations=[], timing={}, report=None, packets=[], supplements=[])
        task['capabilities'] = {'images': bool(images), 'parallel_vision': bool(images and parallel_vision)}
        for key in ('preparation',):
            task.pop(key, None)
        task['snapshot'] = {'source_task': task_id, 'at': now(), 'discovery': copy.deepcopy(source['discovery']),
                            'catalog_sha256': catalog.fingerprint(posts)}
        for item in task['items'].values():
            if item.get('analysis'):
                item['review_evidence'] = copy.deepcopy(item['analysis'])
            item.pop('analysis', None)
            item.pop('analysis_error', None)
        write_json(task_path(task['id'], root).parent / 'catalog.json', {'posts': posts})
        save(task, root)
    return summary(task, root)


def review_record(item, post, root):
    """Verify prior review independently of the question; never invent a fresh visual attestation."""
    saved = item.get('review_evidence') or item.get('analysis') or {}
    if not saved.get('file'):
        return None
    try:
        file = inside(root, saved['file'])
        if digest(file) != saved.get('sha256'):
            return None
        value = read_json(file)
        source = value['source']
        if source['content_fingerprint'] != post['content_fingerprint']:
            return None
        if digest(inside(root, saved['review_file'])) != __import__('hashlib').sha256(value['review']['text'].encode('utf-8')).hexdigest():
            return None
        if item.get('speech', {}).get('result'):
            speech = read_json(inside(root, item['speech']['result']))
            if speech.get('text') != source['transcript']:
                return None
            text_file = item['speech'].get('text')
            if text_file and digest(inside(root, text_file)) != speech.get('output_sha256', {}).get('txt'):
                return None
        images = value.get('evidence_images', source['images'])
        for image in images:
            if digest(inside(root, image['file'])) != image['sha256']:
                return None
        return {'record': saved, 'value': value, 'images': images}
    except (OSError, ValueError, KeyError):
        return None


def plan(source, *, mode='analyze', quality=None, instruction=DEFAULT_INSTRUCTION,
         images=False, parallel_vision=False, root=ROOT):
    if mode not in ('analyze', 'download'):
        raise ValueError('模式应为 analyze 或 download')
    links = re.findall(r'https?://[^\s<>"，。]+', source)
    if len(links) != 1:
        raise ValueError('请提供一个抖音博主主页或包含一个主页短链的分享文案')
    url = douyin_browser.resolve_url(links[0])
    parsed = urlsplit(url)
    match = re.fullmatch(r'/(?:share/)?user/([A-Za-z0-9_-]+)/?', parsed.path)
    if parsed.hostname not in ('douyin.com', 'www.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com') or not match:
        raise ValueError('博主任务需要抖音 /user/ 主页链接')
    url = 'https://www.douyin.com/user/' + match[1]
    key = catalog.fingerprint(url)[:20]
    task = {'id': 'creator-' + uuid.uuid4().hex[:16], 'schema': 1, 'created': now(),
            'source': url, 'account_key': key, 'mode': mode,
            'quality': quality or ('best' if mode == 'download' else 'compact'),
            'instruction': instruction or DEFAULT_INSTRUCTION, 'analysis_schema': ANALYSIS_SCHEMA,
            'capabilities': {'images': bool(images), 'parallel_vision': bool(parallel_vision and images)},
            'status': 'needs_discovery', 'discovery': {'complete': False, 'pages': 0},
            'items': {}, 'authorizations': [], 'timing': {}, 'report': None}
    if task['quality'] not in ('best', 'compact'):
        raise ValueError('quality must be best or compact')
    save(task, root)
    return summary(task, root)


def discover(task_id, *, anonymous_only=False, max_seconds=600, root=ROOT, scanner=None):
    if max_seconds <= 0:
        raise ValueError('发现时限应大于 0')
    task = load(task_id, root)
    require_online_task(task)
    folder = task_path(task_id, root).parent
    with artifact_lock(account_dir(task, root)):
        # A new discovery always requests the public feed, even when media is cached.
        existing = {p['id']: p for p in records(task, root)}
        seen_now, pages, unresolved = set(), [], []
        attempt = uuid.uuid4().hex[:12]
        task.update(status='discovering', report=None, anonymous_only=anonymous_only)
        task['discovery'] = {'complete': False, 'pages': 0, 'started': now(), 'attempt': attempt}
        save(task, root)

        def on_page(payload, scan_state):
            raw_file = folder / 'pages' / attempt / f'{len(pages) + 1:05d}.json'
            write_json(raw_file, payload)
            for index, raw in enumerate(payload.get('aweme_list', [])):
                try:
                    post = catalog.normalize_post(raw) if isinstance(raw, dict) else None
                except (TypeError, ValueError, AttributeError, KeyError) as exc:
                    post = None
                    reason = '作品字段无法解析：' + str(exc)
                else:
                    reason = '作品缺少有效 ID 或不是业务记录对象'
                if post is None:
                    unresolved.append({'page': relative(root, raw_file), 'index': index, 'reason': reason})
                    continue
                if post:
                    item = task['items'].get(post['id'], {})
                    if item.get('content_fingerprint') != post['content_fingerprint']:
                        item.pop('analysis', None)
                    if item.get('media_fingerprint') != post['media_fingerprint']:
                        for field in ('media', 'speech', 'download_file', 'media_error', 'speech_error'):
                            item.pop(field, None)
                    existing[post['id']] = post
                    seen_now.add(post['id'])
            pages.append({'file': relative(root, raw_file), 'cursor': payload.get('cursor'),
                          'has_more': payload.get('has_more')})
            write_json(folder / 'catalog.json', {'posts': catalog.chronological(existing.values())})
            task['discovery'].update(scan_state, checkpoints=pages, current_scan_ids=sorted(seen_now))
            task['discovery'].update(pagination_complete=bool(scan_state.get('complete')),
                complete=bool(scan_state.get('complete')) and not unresolved, unresolved_records=unresolved)
            save(task, root)

        scanner = scanner or douyin_browser.scan_profile
        profile = None if anonymous_only else root / '.local/douyin-profile'
        try:
            outcome = scanner(task['source'], profile, on_page, max_seconds=max_seconds)
        except Exception as exc:
            outcome = {'complete': False, 'reason': 'discovery_error', 'error': str(exc)}
        complete = bool(outcome.get('complete')) and bool(seen_now) and not unresolved
        task['discovery'].update(outcome, checkpoints=pages, current_scan_ids=sorted(seen_now),
            pagination_complete=bool(outcome.get('complete')), complete=complete, unresolved_records=unresolved)
        if unresolved:
            task['discovery']['reason'] = 'unresolved_records'
        if complete:
            # Not seen in a complete refresh means unavailable in this snapshot, not deleted.
            selected = [p for ident, p in existing.items() if ident in seen_now]
        else:
            selected = list(existing.values())
        for post in selected:
            post['seen_in_latest_scan'] = post['id'] in seen_now
        write_json(folder / 'catalog.json', {'posts': catalog.chronological(selected)})
        task['status'] = 'discovered' if complete else 'discovery_incomplete'
        task['timing']['discovery_seconds'] = outcome.get('elapsed_seconds')
        save(task, root)
        write_json(account_dir(task, root) / 'latest-catalog.json', {
            'task': task_id, 'discovery': task['discovery'], 'posts': catalog.chronological(selected)})
    return summary(task, root)


def speech_task(post):
    return {'revision': 'creator-' + post['media_fingerprint'][:16]}


def speech_job(post, asset=None):
    return {'id': post['id'], 'title': post['title'], 'source': post['source'],
            'author': post.get('author', {}).get('nickname') or '未知作者',
            'published': post.get('published'), 'duration': post.get('duration'),
            'media_fingerprint': post['media_fingerprint'],
            'media': asset['file'] if asset else ''}


def cached_speech(post, root):
    if post['kind'] != 'video':
        return {'status': 'not_applicable'}
    result = workflow.cached_result(speech_job(post), speech_task(post), root)
    if result:
        return result
    folder = root / '.cache' / post['id'] / workflow.version_for(speech_task(post))
    no_speech = folder / 'no-speech.json'
    if no_speech.is_file():
        return read_json(no_speech)
    return None


def prior_requests(post, root):
    folder = root / '.cache' / post['id'] / workflow.version_for(speech_task(post))
    return [read_json(p) for p in sorted(folder.glob('chunk-*.json'))]


def usage(task, root, *, price_per_hour=None, item_ids=None):
    state = book(task, root)
    candidates, reusable, blocked, seconds, unknown = [], [], [], 0.0, 0
    posts = records(task, root)
    if item_ids is not None and not set(item_ids).issubset({p['id'] for p in posts}):
        raise ValueError('指定的作品不在本次清单内')
    for post in posts:
        if item_ids is not None and post['id'] not in item_ids:
            continue
        if post['kind'] != 'video' or task['mode'] != 'analyze':
            continue
        try:
            cached = cached_speech(post, root)
            if cached:
                reusable.append(post['id'])
                continue
        except (OSError, ValueError, RuntimeError) as exc:
            blocked.append({'id': post['id'], 'reason': 'cache', 'error': str(exc)})
            continue
        item = state['items'].get(post['id'], {})
        material = item.get('media', {}) if item.get('media_fingerprint') == post['media_fingerprint'] else {}
        asset = material.get('asset', {})
        if asset and not asset.get('has_audio'):
            reusable.append(post['id'])
            continue
        previous = prior_requests(post, root)
        retry_required = any(p.get('status') != 'succeeded' for p in previous)
        duration = asset.get('duration') if asset.get('duration') is not None else post.get('duration')
        known = sum(float(p.get('audio_duration', 0)) for p in previous if p.get('status') == 'succeeded')
        remaining = max(0, duration - known) if duration is not None else None
        if remaining is None:
            unknown += 1
        else:
            seconds += remaining
        candidates.append({'id': post['id'], 'media_fingerprint': post['media_fingerprint'],
                           'estimated_audio_seconds': remaining, 'retry_required': retry_required})
    quote_basis = {'items': candidates, 'asr_profile': asr.PROFILE, 'mode': task['mode'],
                   'selected_ids': sorted(item_ids) if item_ids is not None else None}
    quote = {'token': catalog.fingerprint(quote_basis), **quote_basis,
             'new_or_remaining_items': len(candidates), 'reusable_items': len(reusable),
             'known_audio_seconds': round(seconds, 3), 'unknown_duration_items': unknown,
             'blocked': blocked, 'visual_capable': task['capabilities']['images'],
             'discovery_complete': task['discovery'].get('complete', False),
             'currency': None, 'estimated_cost': None, 'price_per_hour': price_per_hour,
             'note': '数量与时长仅针对当前已发现作品；估算不是账单。未知时长不计入已知总量。'}
    if price_per_hour is not None:
        if price_per_hour < 0:
            raise ValueError('单价不能为负数')
        if not unknown:
            quote['estimated_cost'] = round(seconds / 3600 * price_per_hour, 4)
        quote['price_source'] = 'user_supplied_applicable_unit_price'
    return quote


def preflight(task_id, *, price_per_hour=None, item_ids=None, root=ROOT):
    task = load(task_id, root)
    require_online_task(task)
    quote = usage(task, root, price_per_hour=price_per_hour, item_ids=item_ids)
    write_json(task_path(task_id, root).parent / 'usage.json', quote)
    write_json(task_path(task_id, root).parent / 'usage' / (quote['token'] + '.json'), quote)
    return {'task': task_id, 'status': 'usage_preview', 'usage': quote,
            'workspace': str(root), 'cloud_asr_called': False}


def authorize(task_id, token, evidence, *, max_audio_seconds=None, root=ROOT):
    if not evidence.strip():
        raise ValueError('需要用户实际授权整批付费转写的原话')
    task = load(task_id, root)
    require_online_task(task)
    with artifact_lock(account_dir(task, root)):
        task = load(task_id, root)
        if task['mode'] != 'analyze':
            raise ValueError('下载模式不需要、也不会提交语音识别')
        if not task['capabilities']['images']:
            raise ValueError('尚未确认当前 Agent 的实际看图能力，不能将本任务承诺为完整视觉分析')
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise ValueError('用量预览标识无效')
        preview_file = task_path(task_id, root).parent / 'usage' / (token + '.json')
        if not preview_file.is_file():
            raise ValueError('请先展示本批用量预览')
        preview = read_json(preview_file)
        quote = usage(task, root, item_ids=preview.get('selected_ids'))
        if quote['token'] != token:
            raise ValueError('作品或识别状态发生变化，请重新展示用量后确认')
        if max_audio_seconds is not None and max_audio_seconds < 0:
            raise ValueError('识别用量上限不能为负数')
        task['authorizations'].append({'quote': token, 'evidence': evidence, 'at': now(),
            'items': [{'id': p['id'], 'media_fingerprint': p['media_fingerprint']} for p in quote['items']],
            'estimated_audio_seconds': quote['known_audio_seconds'],
            'unknown_duration_items': quote['unknown_duration_items'],
            'max_audio_seconds': max_audio_seconds, 'reserved_audio_seconds': 0,
            'reservations': []})
        save(task, root)
    return summary(task, root)


def _consent(task, post):
    for permission in reversed(task['authorizations']):
        if any(p['id'] == post['id'] and p['media_fingerprint'] == post['media_fingerprint'] for p in permission['items']):
            return permission
    return None


def _reserve(task, post, asset, root):
    consent = _consent(task, post)
    if consent is None:
        return False
    duration = asset.get('duration')
    if duration is None:
        raise RuntimeError('下载后仍无法确定音频时长，尚未提交识别')
    receipts = prior_requests(post, root)
    prior = sum(float(p.get('audio_duration', 0)) for p in receipts if p.get('status') == 'succeeded')
    amount = max(0, duration - prior)
    if consent.get('max_audio_seconds') is not None and consent['reserved_audio_seconds'] + amount > consent['max_audio_seconds']:
        raise RuntimeError('本批识别用量达到用户设定上限，尚未提交此作品')
    consent['reserved_audio_seconds'] += amount
    reservation = {'id': post['id'], 'seconds': amount, 'at': now(),
                   'prior_request_ids': [p.get('request_id') for p in receipts]}
    consent['reservations'].append(reservation)
    save(task, root)  # Reserve before submitting; an interrupted paid request is never resubmitted silently.
    return reservation


def _reconcile_failed_reservation(task, post, reservation, root):
    # transcribe persists each request before submitting. Once the future has
    # stopped, unchanged receipts prove this attempt did not submit that audio.
    try:
        before = reservation['prior_request_ids']
        receipts = prior_requests(post, root)
        if any(not p.get('request_id') or p.get('audio_duration') is None for p in receipts) or None in before:
            return
        submitted = sum(float(p['audio_duration']) for p in receipts if p['request_id'] not in before)
        if submitted < 0:
            return
    except (OSError, ValueError, KeyError, TypeError):
        return  # Unreadable receipts cannot establish that a request was unsubmitted.
    released = max(0, reservation['seconds'] - submitted)
    consent = _consent(task, post)
    consent['reserved_audio_seconds'] = max(0, consent['reserved_audio_seconds'] - released)
    reservation.update(released_audio_seconds=released, submitted_audio_seconds=submitted,
                       reconciled_at=now())


def _recognize(post, material, root, retry_evidence):
    asset = material['asset']
    if not asset.get('has_audio'):
        return {'status': 'no_audio_stream'}
    job = speech_job(post, asset)
    job['media'] = str(inside(root, asset['file']))
    started = time.monotonic()
    try:
        result = workflow.transcribe(job, speech_task(post), root, retry_failed=bool(retry_evidence))
    except RuntimeError:
        previous = prior_requests(post, root)
        if previous and all(p.get('status') == 'succeeded' and not p.get('result', {}).get('text', '').strip() for p in previous):
            result = {'status': 'no_speech_detected', 'source_media_sha256': asset['sha256'],
                      'receipts_retained': True}
            folder = root / '.cache' / post['id'] / workflow.version_for(speech_task(post))
            write_json(folder / 'no-speech.json', result)
        else:
            raise
    return {**result, 'elapsed_seconds': round(time.monotonic() - started, 3)}


def _fetch(post, task, root, timeout):
    started = time.monotonic()
    if task['mode'] == 'analyze' and post['kind'] == 'video':
        speech = cached_speech(post, root)
        if speech and speech.get('result'):
            result = read_json(inside(root, speech['result']))
            if result.get('source_media_sha256'):
                bound = creator_files.source_for_transcript(post, result['source_media_sha256'], root)
                if bound:
                    return bound
    try:
        return creator_files.fetch_post(post, root, quality=task['quality'], timeout=timeout)
    except Exception as original:
        # Expiring CDN URLs are refreshed once through the existing bounded public acquisition route.
        if post['kind'] != 'video' or '缓存' in str(original) or '空间' in str(original):
            raise
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError('单条作品获取超过时限，已下载部分保留') from original
        folder = task_path(task['id'], root).parent / 'url-refresh' / uuid.uuid4().hex[:12]
        refreshed = media.acquire_batch([post['source']], {}, folder, root, version='creator-metadata',
                                       audio=False, anonymous_only=task.get('anonymous_only', False),
                                       timeout=min(remaining, 90))
        if not refreshed:
            raise RuntimeError('媒体获取失败且地址刷新未成功：' + str(original)) from original
        values = refreshed[0].get('media_variants') or [{'urls': [refreshed[0]['media']]}]
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError('单条作品获取超过时限，地址刷新结果已保留')
        return creator_files.fetch_post({**post, 'media_variants': values}, root,
                                        quality=task['quality'], timeout=remaining)


def _write_download(post, material, task, root):
    source = inside(root, material['asset']['file'])
    folder = account_dir(task, root) / 'videos'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (post['aweme_id'] + '.mp4')
    if target.exists() and digest(target) != material['asset']['sha256']:
        target = folder / (post['aweme_id'] + '-' + material['asset']['sha256'][:12] + '.mp4')
    if not target.exists():
        shutil.copyfile(source, target)
    if digest(target) != material['asset']['sha256']:
        raise RuntimeError('交付视频校验失败，未登记完成')
    metadata = {k: v for k, v in post.items() if k not in ('media_variants', 'raw', 'images', 'covers')}
    write_json(target.with_suffix('.json'), {**metadata, 'download': material['asset'],
        'requested_quality': task['quality'], 'selected_variant': material.get('selected_variant'),
        'quality_note': '本次取得的可用版本，不是作者上传前的原始文件'})
    target.with_suffix('.txt').write_text(post['description'], encoding='utf-8')
    return relative(root, target)


def run(task_id, *, download_workers=2, asr_workers=1, item_timeout=300, retry_evidence='', root=ROOT,
        limit_items=None, item_ids=None,
        fetcher=None, recognizer=None):
    if not 1 <= download_workers <= 4 or not 1 <= asr_workers <= 2 or item_timeout <= 0:
        raise ValueError('获取并发范围为 1–4，语音并发为 1–2，单条超时应大于 0')
    task = load(task_id, root)
    require_online_task(task)
    with artifact_lock(account_dir(task, root)):
        task = load(task_id, root)
        posts = records(task, root)
        if not posts:
            raise ValueError('尚无作品清单，请先 discover；空列表不能证明主页已抓全')
        state = book(task, root)
        task['status'] = 'running'
        task['report'] = None
        started = time.monotonic()
        if retry_evidence:
            task.setdefault('retry_confirmations', []).append({'evidence': retry_evidence, 'at': now()})
        save(task, root)
        fetcher, recognizer = fetcher or _fetch, recognizer or _recognize
        selected = [p for p in posts if p['kind'] == 'video' or task['mode'] == 'analyze' and p['kind'] == 'images']
        if item_ids is not None:
            if not set(item_ids).issubset({p['id'] for p in selected}):
                raise ValueError('指定作品不在本任务可处理清单内')
            selected = [p for p in selected if p['id'] in item_ids]
        if limit_items is not None:
            if limit_items < 1:
                raise ValueError('单次处理数量应大于 0')
        if task['mode'] == 'analyze':
            remaining = []
            for post in selected:
                cached_item = state['items'].get(post['id'], {})
                analysis = cached_item.get('analysis', {})
                file = inside(root, analysis['file']) if analysis.get('file') else None
                if analysis.get('complete') and analysis.get('key') == analysis_key(post, task) and file and file.is_file() and digest(file) == analysis.get('sha256'):
                    task['items'][post['id']] = copy.deepcopy(cached_item)
                else:
                    remaining.append(post)
            selected = remaining
        else:
            remaining = []
            for post in selected:
                cached_item = state['items'].get(post['id'], {})
                if (cached_item.get('download_file') and
                        cached_item.get('content_fingerprint') == post['content_fingerprint'] and
                        cached_item.get('media', {}).get('quality') == task['quality'] and
                        not cached_item.get('media_error') and not download_error(cached_item, post, root)):
                    task['items'][post['id']] = copy.deepcopy(cached_item)
                else:
                    remaining.append(post)
            selected = remaining
        if limit_items is not None:
            selected = selected[:limit_items]
        pending = iter(selected)
        active_fetch, active_speech = {}, {}
        task['timing']['concurrency'] = {'download': download_workers, 'asr': asr_workers,
                                       'paid_parallelism_requires_account_capacity': True}

        def persist():
            save_book(task, state, root)
            save(task, root)

        def complete_material(post, material, speech_pool):
            item = task['items'].setdefault(post['id'], {})
            previous = state['items'].get(post['id'], {})
            if previous.get('media_fingerprint') != post['media_fingerprint']:
                previous = {}
            item.update(media=material, media_fingerprint=post['media_fingerprint'],
                        content_fingerprint=post['content_fingerprint'])
            item.pop('media_error', None)
            state['items'][post['id']] = {**previous, **item}
            if task['mode'] == 'download':
                item['download_file'] = _write_download(post, material, task, root)
            elif post['kind'] == 'images':
                item['speech'] = {'status': 'not_applicable'}
            elif not material['asset'].get('has_audio'):
                item['speech'] = {'status': 'no_audio_stream'}
            else:
                cached = cached_speech(post, root)
                if cached:
                    item['speech'] = cached
                    item.pop('speech_error', None)
                elif any(p.get('status') != 'succeeded' for p in prior_requests(post, root)) and not retry_evidence:
                    item['speech_error'] = '存在失败或结果未知的付费请求，需要核对并明确授权重试'
                elif not task['capabilities']['images']:
                    item['speech'] = {'status': 'awaiting_visual_capability'}
                else:
                    try:
                        permitted = _reserve(task, post, material['asset'], root)
                    except RuntimeError as exc:
                        item['speech_error'] = str(exc)
                        permitted = False
                    if permitted:
                        future = speech_pool.submit(recognizer, post, material, root, retry_evidence)
                        active_speech[future] = (post, permitted)
                    else:
                        item['speech'] = {'status': 'awaiting_usage_confirmation'}
            state['items'][post['id']] = {**state['items'][post['id']], **item}
            persist()

        with ThreadPoolExecutor(max_workers=download_workers) as downloads, ThreadPoolExecutor(max_workers=asr_workers) as speech:
            exhausted = False
            while not exhausted or active_fetch or active_speech:
                # Back-pressure keeps ready media from creating an unbounded ASR queue.
                while not exhausted and len(active_fetch) < download_workers and len(active_speech) < asr_workers + download_workers:
                    try:
                        post = next(pending)
                    except StopIteration:
                        exhausted = True
                        break
                    future = downloads.submit(fetcher, post, task, root, item_timeout)
                    active_fetch[future] = post
                if not active_fetch and not active_speech:
                    continue
                done, _ = wait([*active_fetch, *active_speech], return_when=FIRST_COMPLETED)
                for future in done:
                    if future in active_fetch:
                        post = active_fetch.pop(future)
                        try:
                            complete_material(post, future.result(), speech)
                        except Exception as exc:
                            task['items'].setdefault(post['id'], {})['media_error'] = str(exc)
                            persist()
                    else:
                        post, reservation = active_speech.pop(future)
                        item = task['items'].setdefault(post['id'], {})
                        try:
                            item['speech'] = future.result()
                            item.pop('speech_error', None)
                        except Exception as exc:
                            item['speech_error'] = str(exc)
                            _reconcile_failed_reservation(task, post, reservation, root)
                        state['items'][post['id']] = {**state['items'].get(post['id'], {}), **item}
                        persist()
        task['timing']['run_seconds'] = round(time.monotonic() - started, 3)
        if task['mode'] == 'analyze':
            awaiting = any(i.get('speech', {}).get('status') == 'awaiting_usage_confirmation' for i in task['items'].values())
            task['status'] = 'awaiting_usage_confirmation' if awaiting else 'awaiting_visual_analysis'
        else:
            task['status'] = 'downloaded'
        save(task, root)
    return export(task_id, root=root)


def analysis_key(post, task):
    return catalog.fingerprint({'content': post['content_fingerprint'], 'instruction': task['instruction'],
                                'asr': asr.PROFILE, 'schema': ANALYSIS_SCHEMA})


def analysis_record(item, post, task, root):
    saved = item.get('analysis', {})
    if saved.get('key') != analysis_key(post, task) or not saved.get('file'):
        return None
    file = inside(root, saved['file'])
    if not file.is_file() or digest(file) != saved.get('sha256'):
        return None
    reviewed = review_record({**item, 'review_evidence': saved}, post, root)
    return reviewed['value'] if reviewed else None


def review_material(post, item, root):
    material, speech = item.get('media', {}), item.get('speech', {})
    if post['kind'] == 'video' and speech.get('result'):
        checksum = read_json(inside(root, speech['result'])).get('source_media_sha256')
        if checksum and material.get('asset', {}).get('sha256') != checksum:
            material = creator_files.source_for_transcript(post, checksum, root)
            if not material:
                raise RuntimeError('转写使用的原媒体未找到；保留转写，不能用不同画质版本冒充同源画面')
    return material


def report_record(task, root):
    saved = task.get('report') or {}
    if not saved.get('file'):
        return None
    file = inside(root, saved['file'])
    if not file.is_file() or digest(file) != saved.get('sha256'):
        return None
    value = read_json(file)
    posts = records(task, root)
    snapshot = {p['id']: {'analysis': task['items'].get(p['id'], {}).get('analysis'),
                          'statistics': p['statistics'], 'observed_at': p['observed_at']} for p in posts}
    if value.get('basis_sha256') != catalog.fingerprint(snapshot):
        return None
    if any(task['items'].get(p['id'], {}).get('analysis') and
           analysis_record(task['items'][p['id']], p, task, root) is None for p in posts):
        return None
    return value


def download_error(item, post, root):
    if not item.get('download_file'):
        return None
    if item.get('media_fingerprint') != post['media_fingerprint']:
        return '交付视频来源已变化，需要重新核对'
    try:
        file = inside(root, item['download_file'])
        if not file.is_file():
            return '交付视频文件缺失'
        if digest(file) != item.get('media', {}).get('asset', {}).get('sha256'):
            return '交付视频文件已变化，原文件保持不动'
    except (OSError, ValueError):
        return '交付视频文件无法读取或路径无效'
    return None


def summary(task, root=ROOT):
    posts = records(task, root)
    counts = {'discovered': len(posts), 'videos': sum(p['kind'] == 'video' for p in posts),
              'image_posts': sum(p['kind'] == 'images' for p in posts), 'downloaded': 0,
              'speech_ready': 0, 'visual_reviewed': 0, 'review_reused': 0, 'analyzed': 0, 'fully_analyzed': 0, 'failed_items': 0}
    delivery_gaps = []
    for post in posts:
        item = task['items'].get(post['id'], {})
        media_valid = item.get('media_fingerprint') == post['media_fingerprint']
        analyzed = item.get('analysis', {})
        analysis_valid = analysis_record(item, post, task, root) is not None
        delivery_error = download_error(item, post, root) if task['mode'] == 'download' else None
        if delivery_error:
            delivery_gaps.append({'id': post['id'], 'file': item['download_file'], 'error': delivery_error})
        counts['downloaded'] += (media_valid and bool(item.get('download_file')) and not delivery_error
                                if task['mode'] == 'download' else media_valid and bool(item.get('media', {}).get('complete')))
        counts['speech_ready'] += media_valid and item.get('speech', {}).get('status') in ('transcribed', 'reused', 'no_speech_detected', 'no_audio_stream', 'not_applicable')
        counts['visual_reviewed'] += analysis_valid and bool(analyzed.get('visual_complete'))
        counts['review_reused'] += analysis_valid and bool(analyzed.get('review_reused'))
        counts['analyzed'] += analysis_valid and bool(analyzed.get('file'))
        counts['fully_analyzed'] += analysis_valid and bool(analyzed.get('complete'))
        counts['failed_items'] += bool(delivery_error or item.get('media_error') or item.get('speech_error') or item.get('analysis_error') or item.get('media', {}).get('errors'))
    required = counts['videos'] if task['mode'] == 'download' else len(posts)
    finished = counts['downloaded'] if task['mode'] == 'download' else counts['fully_analyzed']
    complete = bool(posts) and bool(task['discovery'].get('complete')) and required == finished and not counts['failed_items']
    if task['mode'] == 'analyze':
        complete = complete and counts['visual_reviewed'] == required and report_record(task, root) is not None
    return {'task': task['id'], 'mode': task['mode'], 'status': 'completed' if complete else task['status'],
            'complete': complete, 'discovery_complete': bool(task['discovery'].get('complete')),
            'counts': counts, 'delivery_gaps': delivery_gaps, 'timing': task.get('timing', {}), 'workspace': str(root),
            'task_file': relative(root, task_path(task['id'], root)),
            'delivery_directory': relative(root, account_dir(task, root) / 'reports' / task['id']),
            'capabilities': task['capabilities'], 'offline': task.get('offline', False), 'snapshot': task.get('snapshot')}


def export(task_id, *, root=ROOT):
    task = load(task_id, root)
    posts = records(task, root)
    destination = account_dir(task, root) / 'reports' / task_id
    destination.mkdir(parents=True, exist_ok=True)
    fields = ['id', 'source', 'published', 'kind', 'title', 'description', 'duration', 'observed_at',
              'digg_count', 'comment_count', 'collect_count', 'share_count', 'play_count',
              'download_file', 'speech_status', 'transcript_file', 'reviewed_text_file',
              'visual_reviewed', 'analysis_complete', 'analysis_file', 'category', 'topic',
              'angle', 'summary', 'opening', 'format', 'error']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for post in posts:
        item = task['items'].get(post['id'], {})
        checked = analysis_record(item, post, task, root)
        errors = [str(item[k]) for k in ('media_error', 'speech_error', 'analysis_error') if item.get(k)]
        delivery_error = download_error(item, post, root)
        if delivery_error:
            errors.append(delivery_error)
        row = {k: post.get(k) for k in fields if k in post}
        row.update({k: post.get('statistics', {}).get(k) for k in fields if k.endswith('_count')})
        row.update(download_file=item.get('download_file'), speech_status=item.get('speech', {}).get('status'),
                   transcript_file=item.get('speech', {}).get('text'),
                   reviewed_text_file=item.get('analysis', {}).get('review_file') if checked else None,
                   visual_reviewed=bool(checked and checked.get('visual_complete')),
                   analysis_complete=bool(checked and checked.get('complete')),
                   analysis_file=item.get('analysis', {}).get('file') if checked else None,
                   error='; '.join(errors))
        row.update({k: checked['analysis'].get(k) if checked else None
                    for k in ('category', 'topic', 'angle', 'summary', 'opening', 'format')})
        # Spreadsheet applications must not execute creator-provided captions as formulas.
        row = {k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v) for k, v in row.items()}
        writer.writerow(row)
    (destination / '作品明细.csv').write_text(stream.getvalue(), encoding='utf-8-sig', newline='')
    with (destination / '原始作品.jsonl').open('w', encoding='utf-8') as handle:
        for post in posts:
            handle.write(json.dumps({'id': post['id'], 'observed_at': post['observed_at'], 'raw': post['raw']}, ensure_ascii=False) + '\n')
        for unresolved in task['discovery'].get('unresolved_records', []):
            raw = read_json(inside(root, unresolved['page']))['aweme_list'][unresolved['index']]
            handle.write(json.dumps({'id': None, 'unresolved': unresolved, 'raw': raw}, ensure_ascii=False) + '\n')
    with (destination / '分析与核对.jsonl').open('w', encoding='utf-8') as handle:
        for post in posts:
            item = task['items'].get(post['id'], {})
            handle.write(json.dumps({'id': post['id'], 'published': post.get('published'),
                'observed_at': post['observed_at'], 'statistics': post['statistics'],
                'processing': item, 'result': analysis_record(item, post, task, root)}, ensure_ascii=False) + '\n')
    result = summary(task, root)
    write_json(destination / '采集与处理状态.json', {**result, 'discovery': task['discovery'], 'items': task['items']})
    lines = ['# 博主任务报告', '', '- 来源：' + task['source'], '- 模式：' + task['mode'],
             '- 生成时间：' + now(), '- 作品清单完整：' + str(result['discovery_complete']),
             '- 全部工作完成：' + str(result['complete']), '',
             '范围为本次会话可访问的公开作品。缺失字段保持为空；未到分页末尾不代表全量。', '',
             '## 处理进度', '', *[f'- {k}：{v}' for k, v in result['counts'].items()], '']
    aggregate = report_record(task, root)
    if task.get('offline'):
        lines += ['本报告使用原任务保存的素材范围，没有刷新主页或互动数据。',
                  '原任务：' + task['snapshot']['source_task'], '分析问题：' + task['instruction'], '']
    if aggregate:
        for key, title in [('account', '账号分析'), ('content', '内容分析'), ('topics', '选题分析')]:
            lines += ['## ' + title, '', aggregate[key], '']
        lines += ['## 阶段变化', '']
        for stage in aggregate['stages']:
            lines += ['### ' + stage['title'], '', stage['summary'], '',
                      '依据：' + '、'.join(stage['item_ids']), '']
    elif task['mode'] == 'analyze':
        lines += ['账号、内容、选题和阶段总结尚待 Agent 基于已核对材料完成。', '']
    lines += ['## 按发布时间排序的作品', '']
    for post in posts:
        item = task['items'].get(post['id'], {})
        title = post['title'].replace('\n', ' ').replace('\r', ' ')
        lines += [f"### {post.get('published') or '时间未知'} · {title}", '', f"来源：{post['source']}", '']
        analysis = analysis_record(item, post, task, root)
        if analysis:
            lines += [analysis['analysis']['summary'], '', '选题：' + analysis['analysis']['topic'], '']
            for key, label in [('category', '分类'), ('angle', '切入角度'), ('opening', '开头'), ('format', '形式')]:
                lines += [label + '：' + analysis['analysis'][key], '']
            reviewed = item['analysis'].get('review_file')
            if reviewed:
                link = Path(os.path.relpath(inside(root, reviewed), destination)).as_posix()
                lines += [f'[校对正文](<{link}>)', '']
            notes = analysis.get('review', {}).get('unresolved', [])
            notes += analysis.get('review', {}).get('review_notes', [])
            if notes:
                lines += ['核对记录／未解疑点：', '']
                lines += ['- ' + (note.get('text', '') + ' ' + note.get('detail', '') if isinstance(note, dict) else str(note)) for note in notes]
                lines += ['']
        else:
            lines += ['尚未完成逐条内容分析。' if task['mode'] == 'analyze' else '下载状态见作品明细。', '']
    (destination / '报告.md').write_text('\n'.join(lines), encoding='utf-8')
    return result
