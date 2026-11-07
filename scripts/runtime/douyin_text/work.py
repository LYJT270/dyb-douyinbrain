"""Link business steps without rewriting native tasks or executing their side effects."""
from __future__ import annotations

import copy
import re
import uuid
from pathlib import Path

from .common import ROOT, SKILL_ROOT, artifact_lock, digest, inside, now, read_json, relative, write_json

STATES = ('pending', 'running', 'completed', 'partial', 'blocked')
ROLES = ('raw', 'review', 'report', 'rewrite', 'subtitle', 'video', 'catalog', 'receipt', 'other')


def path(work_id, root=ROOT):
    if not re.fullmatch(r'work-[0-9a-f]{16}', work_id):
        raise ValueError('不是有效的组合工作 ID')
    return root / 'runs' / work_id / 'work.json'


def load(work_id, root=ROOT):
    value = read_json(path(work_id, root))
    if value.get('schema') != 1 or value.get('id') != work_id:
        raise ValueError('组合工作记录版本或 ID 不一致')
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + '不能为空')
    return value.strip()


def _save(value, root):
    value['updated'] = now()
    write_json(path(value['id'], root), value)


def create(spec, root=ROOT):
    request = _text(spec.get('request'), '用户原话')
    inputs = spec.get('inputs', [])
    if not isinstance(inputs, list) or any(not isinstance(x, str) for x in inputs):
        raise ValueError('inputs 应为素材字符串列表')
    members = {x['name'] for x in read_json(SKILL_ROOT / 'assets/skill-suite.json')['members']}
    steps, seen = [], set()
    if not isinstance(spec.get('steps'), list) or not spec['steps']:
        raise ValueError('至少需要一个工作步骤')
    for row in spec['steps']:
        key = row.get('id', '')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', key) or key in seen:
            raise ValueError('步骤 ID 应唯一且使用小写英文、数字、下划线或连字符')
        if row.get('skill') not in members:
            raise ValueError('步骤必须使用当前套件中的业务 Skill')
        depends = row.get('depends_on', [])
        if not isinstance(depends, list) or any(not isinstance(x, str) or x not in seen for x in depends):
            raise ValueError('依赖应指向前面已定义的步骤')
        if not isinstance(row.get('accept_partial', False), bool):
            raise ValueError('accept_partial 应为布尔值')
        steps.append({'id': key, 'skill': row['skill'], 'instruction': _text(row.get('instruction'), '步骤目标'),
                      'depends_on': list(dict.fromkeys(depends)), 'accept_partial': row.get('accept_partial', False),
                      'status': 'pending', 'native_tasks': [], 'artifacts': [], 'summary': '', 'coverage': ''})
        seen.add(key)
    value = {'schema': 1, 'id': 'work-' + uuid.uuid4().hex[:16], 'created': now(),
             'request': request, 'inputs': inputs, 'steps': steps, 'events': [],
             'authorization': 'Native task authorization remains authoritative; this record grants none.'}
    _save(value, root)
    return show(value['id'], root)


def _step(value, step_id):
    found = next((x for x in value['steps'] if x['id'] == step_id), None)
    if found is None:
        raise ValueError('组合工作没有这个步骤')
    return found


def _native(task_id, root):
    if re.fullmatch(r'creator-[0-9a-f]{16}', task_id):
        from .creator import load as read_task
        kind = 'creator'
    elif re.fullmatch(r'dy-[0-9a-f]{16}', task_id):
        from .workflow import load as read_task
        kind = 'document'
    else:
        raise ValueError('只可关联已有的 dy- 或 creator- 原生任务')
    task = read_task(task_id, root)
    if task.get('id') != task_id:
        raise ValueError('原生任务 ID 与文件不一致')
    return {'id': task_id, 'kind': kind, 'file': f'runs/{task_id}/task.json',
            'status': task.get('status'), 'purpose': task.get('purpose') or task.get('mode'),
            'instruction': task.get('instruction', ''),
            'authorization_source': f'runs/{task_id}/task.json'}


def link(work_id, step_id, task_id, root=ROOT):
    native = _native(task_id, root)
    with artifact_lock(path(work_id, root).parent):
        value = load(work_id, root)
        step = _step(value, step_id)
        if task_id not in step['native_tasks']:
            step['native_tasks'].append(task_id)
            value['events'].append({'at': now(), 'action': 'link', 'step': step_id, 'task': native['id']})
            _save(value, root)
    return show(work_id, root)


def _artifacts(entries, root):
    result, issues = [], []
    for entry in entries:
        item = dict(entry)
        try:
            file = inside(root, entry['file'])
            item['absolute_file'] = str(file)
            item['valid'] = file.is_file() and digest(file) == entry['sha256']
        except (OSError, ValueError, KeyError):
            item['valid'] = False
        if not item['valid']:
            issues.append(entry.get('file', 'unknown'))
        result.append(item)
    return result, issues


def show(work_id, root=ROOT):
    value = copy.deepcopy(load(work_id, root))
    evaluated = {}
    for step in value['steps']:
        step['artifacts'], issues = _artifacts(step['artifacts'], root)
        step['artifact_issues'] = issues
        step['native_status'] = []
        for task_id in step['native_tasks']:
            try:
                step['native_status'].append(_native(task_id, root))
            except (OSError, ValueError, KeyError) as exc:
                step['native_status'].append({'id': task_id, 'status': 'unavailable', 'error': str(exc)})
        blocked = [key for key in step['depends_on'] if evaluated[key]['effective_status'] != 'completed'
                   and not (step['accept_partial'] and evaluated[key]['effective_status'] == 'partial')]
        step['blocked_by'] = blocked
        input_snapshot = {key: [{'file': a['file'], 'sha256': a['sha256']} for a in evaluated[key]['artifacts']]
                          for key in step['depends_on']}
        changed = (step['status'] in ('completed', 'partial') and step.get('input_snapshot', {}) != input_snapshot)
        step['dependency_issues'] = ['upstream_artifacts_changed'] if changed else []
        step['effective_status'] = 'stale' if issues or changed else ('blocked' if blocked else step['status'])
        step['ready'] = not issues and not changed and not blocked and step['status'] in ('pending', 'running', 'blocked')
        step['source_artifacts'] = [dict(a, from_step=key) for key in step['depends_on']
                                    for a in evaluated[key]['artifacts'] if a['valid']]
        evaluated[step['id']] = step
    states = [x['effective_status'] for x in value['steps']]
    if all(x == 'completed' for x in states):
        status = 'completed'
    elif all(x in ('completed', 'partial') for x in states):
        status = 'partial'
    elif all(x['status'] == 'pending' for x in value['steps']):
        status = 'planned'
    elif any(x['ready'] for x in value['steps']):
        status = 'in_progress'
    else:
        status = 'blocked'
    value.update(status=status, record=relative(root, path(work_id, root)), workspace=str(root),
                 ready_steps=[x['id'] for x in value['steps'] if x['ready']],
                 completion_basis='Agent records plus current artifact integrity; not independent semantic or publication verification',
                 cloud_asr_called=False)
    return value


def record(work_id, step_id, result, root=ROOT):
    state = result.get('status')
    if state not in STATES:
        raise ValueError('步骤状态应为 pending、running、completed、partial 或 blocked')
    summary = _text(result.get('summary'), '结果或缺口说明')
    coverage = result.get('coverage', '')
    if state in ('completed', 'partial'):
        coverage = _text(coverage, '实际范围')
        if not result.get('artifacts'):
            raise ValueError('完成或部分完成必须登记实际产物')
    files = []
    for entry in result.get('artifacts', []):
        if entry.get('role') not in ROLES:
            raise ValueError('产物 role 不受支持')
        file = inside(root, entry['file'])
        if not file.is_file():
            raise ValueError('产物文件不存在：' + str(file))
        files.append({'file': relative(root, file), 'role': entry['role'], 'sha256': digest(file)})
    with artifact_lock(path(work_id, root).parent):
        value = load(work_id, root)
        current = _step(show(work_id, root), step_id)
        if state in ('running', 'completed', 'partial') and current['blocked_by']:
            raise ValueError('前序步骤未完成或产物失效，不能推进依赖步骤')
        step = _step(value, step_id)
        source_steps = {x['id']: x for x in value['steps']}
        snapshot = {key: [{'file': a['file'], 'sha256': a['sha256']} for a in source_steps[key]['artifacts']]
                    for key in step['depends_on']}
        value['events'].append({'at': now(), 'action': 'record', 'step': step_id,
                                'previous': {k: copy.deepcopy(step[k]) for k in ('status', 'summary', 'coverage', 'artifacts')},
                                'status': state})
        step.update(status=state, summary=summary, coverage=coverage, artifacts=files, input_snapshot=snapshot, recorded_at=now())
        _save(value, root)
    return show(work_id, root)


def list_works(root=ROOT, *, task_id=None, limit=20):
    if not 1 <= limit <= 100:
        raise ValueError('limit 应为 1 到 100')
    rows = []
    for file in (root / 'runs').glob('work-*/work.json'):
        try:
            value = load(file.parent.name, root)
            if task_id and not any(task_id in step['native_tasks'] for step in value['steps']):
                continue
            rows.append({'id': value['id'], 'request': value['request'], 'updated': value['updated'],
                         'record': relative(root, file)})
        except (OSError, ValueError, KeyError):
            continue
    rows.sort(key=lambda row: (row['updated'], row['id']), reverse=True)
    return {'status': 'listed', 'works': rows[:limit], 'total': len(rows), 'cloud_asr_called': False}


def add_parser(sub):
    group = sub.add_parser('work', help='组合任务记录；不自动执行或授权业务步骤')
    commands = group.add_subparsers(dest='work_command', required=True)
    commands.add_parser('create').add_argument('--file', type=Path, required=True)
    commands.add_parser('show').add_argument('work')
    listing = commands.add_parser('list')
    listing.add_argument('--task')
    listing.add_argument('--limit', type=int, default=20)
    for name in ('link', 'record'):
        command = commands.add_parser(name)
        command.add_argument('work')
        command.add_argument('step')
        command.add_argument('--task' if name == 'link' else '--file',
                             type=str if name == 'link' else Path, required=True)


def dispatch(args):
    if args.work_command == 'create':
        return create(read_json(args.file))
    if args.work_command == 'show':
        return show(args.work)
    if args.work_command == 'list':
        return list_works(task_id=args.task, limit=args.limit)
    if args.work_command == 'link':
        return link(args.work, args.step, args.task)
    return record(args.work, args.step, read_json(args.file))
