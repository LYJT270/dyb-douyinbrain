"""Read-only task discovery and recovery guidance. The Agent performs the next action."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from . import content, creator, workflow, work
from .common import ROOT, digest, inside, read_json, relative


def input_key(value):
    value = value.strip()
    links = re.findall(r'https?://[^\s<>"，。]+', value)
    if len(links) == 1:
        url = urlsplit(links[0])
        if url.hostname in ('www.douyin.com', 'douyin.com', 'www.iesdouyin.com', 'iesdouyin.com'):
            match = re.fullmatch(r'/(?:share/)?(video|note|user)/([^/]+)/?', url.path)
            if match:
                return 'douyin:' + ('post' if match[1] in ('video', 'note') else 'user') + ':' + match[2]
        # Short URLs are not resolved here: recovery must remain offline.
        return links[0]
    path = Path(value).expanduser()
    if path.is_absolute() or path.exists():
        return str(path.resolve()).casefold()
    return value


def _text(value):
    return ' '.join((value or '').split())


def _action(name, **values):
    return {'action': name, **values}


def _file_state(entry, root):
    try:
        file = inside(root, entry['file'])
        if not file.is_file():
            return 'missing'
        return 'valid' if digest(file) == entry.get('sha256') else 'edited'
    except (OSError, ValueError, KeyError):
        return 'unavailable'


def document_summary(task, root):
    actions, gaps = [], workflow.coverage_gaps(task, root)
    reviewed = content.inspect_content(task, 'review', root)
    spoken = content.inspect_content(task, 'spoken', root)
    originals_ok = True
    if task.get('results'):
        try:
            content.originals(task, root)
        except (OSError, ValueError, KeyError) as exc:
            originals_ok = False
            gaps.append({'stage': 'source', 'error': str(exc)})
            actions.append(_action('inspect_source_gaps', note='保留所有现有文件，先核对来源缺口'))
    if not task.get('purpose') or not task.get('evidence'):
        actions.append(_action('record_intent', note='沿用用户已明确给出的用途；仅目标不明时补问'))
    elif not task.get('results') and task.get('offline'):
        actions.append(_action('source_gaps', note='离线任务缺少可用文稿，不重新识别'))
    elif not task.get('results'):
        actions.append(_action('run_native', command=['run', task['id']], note='读取本任务授权；不携带重试授权'))
    elif originals_ok:
        pending = [r for r in reviewed if r['state'] != 'valid']
        if pending:
            actions.append(_action('review_items', item_ids=[r['id'] for r in pending],
                note='已编辑文件先读差异并保留；逐条另存、登记，复用其余有效校对'))
        ready = {r['id'] for r in reviewed if r['state'] == 'valid'}
        purpose = task.get('purpose')
        if purpose == 'rewrite':
            todo = [r['id'] for r in spoken if r['id'] in ready and r['state'] != 'valid']
            if todo:
                actions.append(_action('rewrite_items', item_ids=todo, note='从当前有效校对稿续写；保留已有人工修改'))
        if purpose in ('rewrite', 'transcribe'):
            kind, rows = ('spoken', spoken) if purpose == 'rewrite' else ('review', reviewed)
            if rows and all(r['state'] == 'valid' for r in rows):
                delivery = task.get('delivery', {})
                basis = [{'id': r['id'], 'sha256': r['sha256']} for r in rows]
                if (_file_state(delivery, root) != 'valid' or delivery.get('kind') != kind or
                        delivery.get('source_basis', basis) != basis):
                    actions.append(_action('deliver', command=['deliver', task['id'], '--kind', kind],
                                           coverage='partial' if gaps else 'complete'))
        elif purpose == 'analyze' and not pending:
            report = task.get('analysis', {})
            if _file_state(report, root) != 'valid' or report.get('stale'):
                actions.append(_action('analyze', coverage='partial' if gaps else 'complete',
                    note='整批结论需处理缺口或取得接受部分范围的明确决定' if gaps else '复用校对稿生成本问题的分析'))
        elif purpose in ('ingest', 'compile') and not pending:
            actions.append(_action('resume_knowledge', authorization_source=f"runs/{task['id']}/task.json",
                                   note='读取当前归档和发布回执，按目标库入口续办，不重复发布'))
    jobs_file = workflow.task_path(task['id'], root).parent / 'jobs.json'
    jobs = read_json(jobs_file) if jobs_file.is_file() else []
    uncertain = []
    for job in jobs:
        for file in (root / '.cache' / job['id'] / workflow.version_for(task)).glob('chunk-*.json'):
            receipt = read_json(file)
            if receipt.get('status') != 'succeeded':
                uncertain.append({'id': job['id'], 'status': receipt.get('status'), 'file': relative(root, file)})
    if uncertain:
        actions.append(_action('resolve_paid_requests', requests=uncertain, needs_user_decision=True,
                               note='核对失败或未知请求；此前授权不自动成为重试授权'))
    if jobs and not task.get('offline'):
        actions = [a for a in actions if a['action'] != 'run_native']
        if gaps or not task.get('results'):
            actions.append(_action('resume_saved_items', command=['run', task['id'], '--saved-scope'],
                note='只处理已保存作品；沿用实际授权与缓存，不重扫主页。缺少身份的条目保留缺口'))
    if gaps:
        actions.append(_action('resolve_gaps', gaps=gaps, note='独立成果可继续，整批依赖仍保留缺口'))
    return {'task': task['id'], 'kind': 'document', 'status': task.get('status'),
            'goal': task.get('instruction') or task.get('purpose'), 'inputs': task.get('inputs', []),
            'authorization_source': f"runs/{task['id']}/task.json", 'coverage': {'ready_sources': len(reviewed), 'gaps': gaps},
            'working_content': {'review': reviewed, 'spoken': spoken}, 'delivery': task.get('delivery'),
            'next_actions': actions, 'finished': not actions and task.get('status') in ('completed', 'published')}


def creator_summary(task, root):
    state = creator.summary(task, root)
    actions = []
    posts = creator.records(task, root)
    if not posts:
        actions.append(_action('source_gap' if task.get('offline') else 'discover_initial_scope',
            needs_user_decision=bool(task.get('offline')), note='尚无已保存清单；恢复不会自动刷新主页'))
    elif not state['complete']:
        if task['mode'] == 'analyze' and not task.get('capabilities', {}).get('images'):
            actions.append(_action('check_current_capabilities', note='按当前工具设置 capabilities；不沿用旧会话看图能力'))
        packets = [p for p in task.get('packets', []) if p['status'] in ('pending', 'claimed')]
        if packets:
            actions.append(_action('claim_packet', packets=packets,
                                   note='领取未完成包；已有领取者或未过期租约按 claim 结果处理'))
        elif task['mode'] == 'analyze' and state['counts']['fully_analyzed'] < len(posts):
            actions.append(_action('prepare_local_review', command=['creator', 'prepare', task['id'], '--cached-only'],
                                   note='先使用已准备材料；本地缺口集中报告'))
        if task['mode'] == 'analyze' and state['counts']['analyzed']:
            actions.append(_action('report', coverage='complete' if state['counts']['fully_analyzed'] == len(posts)
                                   and state['discovery_complete'] else 'partial'))
        missing = [p['id'] for p in posts if not task['items'].get(p['id'], {}).get('media')]
        awaiting = [ident for ident, item in task['items'].items()
                    if item.get('speech', {}).get('status') == 'awaiting_usage_confirmation']
        unknown = [ident for ident, item in task['items'].items() if item.get('speech_error')]
        if task.get('offline'):
            if missing or awaiting or unknown:
                actions.append(_action('source_gaps', item_ids=sorted(set(missing + awaiting + unknown)),
                                       note='离线任务只处理现有材料；新增获取或识别另行说明'))
        else:
            if awaiting:
                actions.append(_action('preview_usage', item_ids=awaiting, needs_user_decision=True))
            if unknown:
                actions.append(_action('resolve_paid_requests', item_ids=unknown, needs_user_decision=True))
            if missing or task['mode'] == 'download' or state['counts']['speech_ready'] < len(posts):
                actions.append(_action('run_native', command=['creator', 'run', task['id']],
                    note='仅原清单和有效授权；不 discover、不自动重试付费请求'))
        if not state['discovery_complete']:
            actions.append(_action('scope_gap', note='原主页发现不完整；保留缺口，用户要求更新才刷新'))
    return {**state, 'kind': 'creator', 'goal': task['instruction'], 'inputs': [task['source']],
            'snapshot': task.get('snapshot') or {'discovery': task.get('discovery')},
            'authorization_source': f"runs/{task['id']}/task.json", 'offline': task.get('offline', False),
            'next_actions': actions, 'finished': state['complete']}


def summarize(task_id, root=ROOT):
    if task_id.startswith('work-'):
        state = work.show(task_id, root)
        actions = []
        for step in state['steps']:
            if step['artifact_issues']:
                actions.append(_action('inspect_working_artifacts', step=step['id'], artifacts=step['artifacts']))
            elif step['dependency_issues']:
                actions.append(_action('review_changed_inputs', step=step['id'], sources=step['source_artifacts']))
            elif step['ready']:
                native = []
                for ident in step['native_tasks']:
                    try:
                        native.append(summarize(ident, root))
                    except (OSError, ValueError, KeyError) as exc:
                        native.append({'task': ident, 'finished': False,
                                       'next_actions': [_action('inspect_native_gap', error=str(exc))]})
                actions.append(_action('continue_step', step=step['id'], skill=step['skill'],
                    instruction=step['instruction'], sources=step['source_artifacts'],
                    native_tasks=native))
            elif step['effective_status'] == 'partial':
                actions.append(_action('resolve_partial_step', step=step['id'], note=step['summary']))
        return {**state, 'kind': 'work', 'goal': state['request'], 'next_actions': actions,
                'finished': state['status'] == 'completed'}
    if re.fullmatch(r'creator-[0-9a-f]{16}', task_id):
        return creator_summary(creator.load(task_id, root), root)
    if re.fullmatch(r'dy-[0-9a-f]{16}', task_id):
        return document_summary(workflow.load(task_id, root), root)
    raise ValueError('恢复需要已有的 work-、dy- 或 creator- 任务 ID')


def resume(*, task_id=None, inputs=None, purpose=None, instruction=None, request=None, root=ROOT):
    base = {'workspace': str(root), 'network_called': False, 'cloud_asr_called': False,
            'scope_policy': 'saved_snapshot', 'executes_actions': False}
    if task_id:
        return {**base, 'status': 'selected', 'recovery': summarize(task_id, root)}
    wanted = sorted(input_key(x) for x in inputs) if inputs else None
    candidates, errors = [], []
    files = sorted((root / 'runs').glob('*/task.json')) + sorted((root / 'runs').glob('work-*/work.json'))
    for file in files:
        if not re.fullmatch(r'(?:dy|creator|work)-[0-9a-f]{16}', file.parent.name):
            continue
        try:
            task = read_json(file)
            sources = task.get('inputs') or ([task['source']] if task.get('source') else [])
            if wanted is not None and sorted(input_key(x) for x in sources) != wanted:
                continue
            task_purpose = task.get('purpose') or task.get('mode')
            if purpose and purpose != task_purpose:
                continue
            if instruction is not None and _text(instruction) != _text(task.get('instruction')):
                continue
            if request is not None and _text(request) != _text(task.get('request')):
                continue
            # An edited external text source is a new input, while its stored task snapshot remains resumable by ID.
            imports = task.get('text_imports') or ([task['text_import']] if task.get('text_import') else [])
            signatures = {x['source']: x['sha256'] for x in imports}
            signatures.update(task.get('input_fingerprints', {}))
            jobs_file = file.parent / 'jobs.json'
            if jobs_file.is_file():
                for job in read_json(jobs_file):
                    if job.get('id', '').startswith('local-') and job.get('input'):
                        signatures.setdefault(job['input'], job['id'][6:])
            changed = any(Path(source).is_file() and digest(Path(source)) != checksum
                          for source, checksum in signatures.items())
            unknown = any(not x.startswith(('http://', 'https://')) and Path(x).is_file() and x not in signatures for x in sources)
            candidates.append({'id': task['id'], 'goal': task.get('request') or task.get('instruction') or task_purpose,
                'inputs': sources, 'status': task.get('status'), 'purpose': task_purpose,
                'source_changed': changed, 'source_version_unknown': unknown,
                'created': task.get('created'), 'record': relative(root, file)})
        except (OSError, ValueError, KeyError) as exc:
            errors.append({'file': relative(root, file), 'error': str(exc)})
    precise = wanted is not None and (request is not None or purpose is not None and
               (purpose not in ('rewrite', 'analyze') or instruction is not None))
    if len(candidates) == 1 and precise and not candidates[0]['source_changed'] and not candidates[0]['source_version_unknown']:
        return {**base, 'status': 'matched', 'recovery': summarize(candidates[0]['id'], root), 'scan_issues': errors}
    return {**base, 'status': 'choose_task' if candidates else 'not_found', 'candidates': candidates,
            'scan_issues': errors, 'note': '按来源和目标选择；不因最新或文字相似自动合并任务'}


def add_parser(commands):
    command = commands.add_parser('resume', help='离线查找任务并给出下一步；不执行、不刷新、不授权')
    command.add_argument('--task')
    command.add_argument('--input', action='append')
    command.add_argument('--purpose', choices=(*workflow.PURPOSES, 'download'))
    command.add_argument('--instruction')
    command.add_argument('--request', help='组合任务的原始完整要求')
