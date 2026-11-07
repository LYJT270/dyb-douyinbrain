"""Public post records, independent of whether a media file can be downloaded."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from .common import SHANGHAI, now


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def urls(value) -> list[str]:
    if not isinstance(value, dict):
        return []
    candidates = value.get('url_list') or value.get('urlList') or []
    if isinstance(candidates, str):
        candidates = [candidates]
    if value.get('url'):
        candidates = [*candidates, value['url']]
    return list(dict.fromkeys(u for u in candidates if isinstance(u, str)
                             and u.startswith(('https://', 'http://'))))


def variants(video: dict) -> list[dict]:
    found = []
    for entry in video.get('bit_rate') or []:
        if not isinstance(entry, dict) or entry.get('format') not in (None, 'mp4'):
            continue  # An isolated DASH video stream is not a complete download.
        address = entry.get('play_addr') or {}
        if urls(address):
            found.append({'urls': urls(address), 'width': address.get('width') or video.get('width'),
                          'height': address.get('height') or video.get('height'),
                          'bytes': address.get('data_size'), 'bit_rate': entry.get('bit_rate'),
                          'uri': address.get('uri'), 'format': 'mp4'})
    for key in ('play_addr', 'play_addr_h264', 'play_addr_265', 'download_addr'):
        address = video.get(key) or {}
        if urls(address):
            found.append({'urls': urls(address), 'width': address.get('width') or video.get('width'),
                          'height': address.get('height') or video.get('height'),
                          'bytes': address.get('data_size'), 'bit_rate': None,
                          'uri': address.get('uri'), 'format': 'mp4', 'address_kind': key})
    seen, result = set(), []
    for entry in found:
        if tuple(entry['urls']) not in seen:
            seen.add(tuple(entry['urls']))
            result.append(entry)
    return result


def select_variant(values: list[dict], quality='best') -> dict | None:
    available = [v for v in values if v.get('urls')]
    if not available:
        return None
    def score(v):
        return ((v.get('width') or 0) * (v.get('height') or 0),
                v.get('bit_rate') or 0, v.get('bytes') or 0)
    if quality == 'best':
        return max(available, key=score)
    if quality != 'compact':
        raise ValueError('quality must be best or compact')
    eligible = [v for v in available if min(v.get('width') or 0, v.get('height') or 0) >= 540]
    return min(eligible, key=lambda v: (v.get('bytes') or float('inf'), score(v))) if eligible else max(available, key=score)


def normalize_post(raw: dict) -> dict | None:
    ident = str(raw.get('aweme_id') or '')
    if not ident.isdigit():
        return None
    video = raw.get('video') if isinstance(raw.get('video'), dict) else {}
    image_values = raw.get('images') or (raw.get('image_post_info') or {}).get('images') or []
    images = []
    for index, entry in enumerate(image_values):
        address = entry.get('display_image') or entry.get('origin_image') or entry
        images.append({'index': index + 1, 'urls': urls(address), 'uri': address.get('uri'),
                       'width': address.get('width'), 'height': address.get('height')})
    kind = 'images' if image_values or raw.get('aweme_type') in (68, 150) else 'video' if video else 'unknown'
    published = None
    if isinstance(raw.get('create_time'), (float, int)) and raw['create_time'] > 0:
        try:
            published = datetime.fromtimestamp(raw['create_time'], SHANGHAI).isoformat(timespec='seconds')
        except (OverflowError, OSError, ValueError):
            pass
    duration = video.get('duration', raw.get('duration'))
    duration = duration / 1000 if isinstance(duration, (int, float)) and duration >= 0 else None
    media_variants = variants(video)
    media_identity = {'kind': kind, 'duration': duration,
                      'uri': ((video.get('play_addr') or {}).get('uri') or video.get('vid')) if kind == 'video' else None,
                      'images': [{k: x.get(k) for k in ('index', 'uri', 'width', 'height')} for x in images]}
    # Signed CDN URLs and changing counters do not invalidate content analysis.
    text = raw.get('desc') or ''
    return {'id': 'douyin-' + ident, 'aweme_id': ident, 'kind': kind, 'title': text or ident,
            'description': text, 'published': published, 'duration': duration,
            'source': 'https://www.douyin.com/' + ('note/' if kind == 'images' else 'video/') + ident,
            'author': raw.get('author') or {}, 'statistics': raw.get('statistics') or {},
            'text_extra': raw.get('text_extra') or [], 'is_top': raw.get('is_top'),
            'media_variants': media_variants, 'images': images,
            'covers': urls(video.get('origin_cover') or video.get('cover') or {}),
            'media_fingerprint': fingerprint(media_identity),
            'content_fingerprint': fingerprint({'media': media_identity, 'description': text,
                                                'published': published}),
            'observed_at': now(), 'raw': raw}


def chronological(items):
    # Unknown publication times stay visibly unknown, after dated records.
    return sorted(items, key=lambda p: (p.get('published') is None, p.get('published') or '', p['id']))
