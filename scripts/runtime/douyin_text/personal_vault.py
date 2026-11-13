"""Opt-in personal vault: resumable interviews and verified, replayable local writes.

The Agent selects facts, useful material and topic changes. This module persists
those decisions, enforces their scope, and never treats a prepared file as saved.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import quote, unquote

from .common import ROOT, SKILL_ROOT, artifact_lock, config, digest, inside, now, read_json, relative, write_json

RULES = ('AGENTS.md', 'SCHEMA.md', 'SOURCE_OF_TRUTH.md')
DOMAINS = ('life', 'work', 'learning')
DOMAIN_DIRS = {'life': '生活', 'work': '工作', 'learning': '学习'}
DOMAIN_ALIASES = {'creative': 'work'}
MODULES = DOMAINS
LEGACY_MODULES = (*MODULES, *DOMAIN_ALIASES)
FIELDS = {
    'background': '你主要在做什么，或者比较熟悉哪些领域？',
    'goal': '你最近最想推进的一件事是什么？',
    'preferences': '你希望我怎样和你沟通、配合和交付？',
    'name': '我怎么称呼你？也可以跳过。',
    'work.direction': '你目前的工作、项目或创作重点是什么？',
    'work.audience': '这些工作或内容主要服务谁？',
    'work.platform': '你主要在哪些平台或渠道开展？',
    'work.style': '你希望工作成果以什么风格或标准交付？',
    'learning.goal': '你想学会什么，准备怎样用它？',
    'learning.basis': '这个主题你已经了解哪些？',
    'learning.method': '怎样学习对你比较有效？',
    'learning.progress': '你已经尝试或掌握了哪些？可以用练习或复述来说明。',
}
LABELS = dict(zip(FIELDS, ('背景', '当前目标', '协作偏好', '称呼', '内容方向', '受众', '平台', '表达偏好',
                          '学习目标', '已有基础', '学习方式', '学习进展')))
PROFILE = '生活/个人档案/基本资料.md'
LEGACY_PROFILE = '个人/档案/基本资料.md'
ROLES = {'source', 'reviewed', 'draft', 'knowledge', 'profile', 'learning'}
HOOK_START, HOOK_END = '<!-- cy-vault:context:start -->', '<!-- cy-vault:context:end -->'
INDEX_START, INDEX_END = '<!-- cy-vault:index:start -->', '<!-- cy-vault:index:end -->'


def canonical_domain(value):
    return DOMAIN_ALIASES.get(value, value) if isinstance(value, str) else value


def field_domain(key):
    if key in {'background', 'goal', 'preferences', 'name'}:
        return 'life'
    prefix = key.split('.', 1)[0] if isinstance(key, str) else ''
    prefix = canonical_domain(prefix)
    return prefix if prefix in DOMAINS else None


def safe_field(key):
    if not isinstance(key, str):
        return False
    if key in {'background', 'goal', 'preferences', 'name'}:
        return True
    if len(key) > 96 or '/' in key or '\\' in key or '..' in key:
        return False
    return bool(re.fullmatch(r'(?:life|work|learning|creative)\.[\w-]+(?:\.[\w-]+)*', key, re.UNICODE))


def canonical_field(key):
    if isinstance(key, str) and key.startswith('creative.'):
        return 'work.' + key[len('creative.'):]
    return key


def scoped_target(value, module, target, *, profile=False, preserve_existing=False):
    """Place new local writes under their domain while leaving target-rule libraries in control."""
    if profile or value.get('write_mode') != 'local':
        return target
    domain = canonical_domain(module)
    if domain not in DOMAINS or target == '@profile':
        return target
    root = DOMAIN_DIRS[domain]
    path = Path(target)
    if preserve_existing:
        return path.as_posix()
    if path.parts and path.parts[0] == root:
        return path.as_posix()
    if path.parts and path.parts[0] in {'生活', '工作', '学习'}:
        raise ValueError('保存目标方向与本次模块不一致')
    # Old path roots and simple relative paths are inputs; new library writes use the
    # selected domain's 资料 area without changing any already saved transaction.
    if path.parts and path.parts[0] in {'素材', '知识库', '个人'}:
        tail = Path(*path.parts[1:])
    else:
        tail = path
    return (Path(root) / '资料' / tail).as_posix()


def _topic_id(label):
    if not isinstance(label, str) or not label.strip() or len(label) > 120:
        raise ValueError('topic 需要 1 到 120 个字符的主题名称')
    value = re.sub(r'[^\w.-]+', '-', label.strip(), flags=re.UNICODE).strip('-.')
    if not value or value in {'.', '..'} or len(value) > 80:
        raise ValueError('topic 不能作为安全主题键')
    return value


def _branch_spec(payload):
    branch = payload.get('branch')
    if branch is None:
        return None
    if isinstance(branch, str):
        branch = {'id': branch, 'status': payload.get('branch_status', 'in_progress')}
    if not isinstance(branch, dict):
        raise ValueError('branch 应为名称或含 id、status 的对象')
    ident, status = branch.get('id'), branch.get('status', 'in_progress')
    if not isinstance(ident, str) or len(ident) > 120:
        raise ValueError('branch id 需要 1 到 120 个字符')
    key = _topic_id(ident)
    if not isinstance(status, str) or status not in {'in_progress', 'paused', 'refused', 'complete'}:
        raise ValueError('branch status 应为 in_progress、paused、refused 或 complete')
    return {'id': key, 'label': ident, 'status': status}


def home(root):
    return root / '.local/vault'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def state(root=ROOT):
    path = home(root) / 'state.json'
    return read_json(path) if path.is_file() else {}


def save(value, root):
    write_json(home(root) / 'state.json', value)


def rules(vault):
    return {name: digest(vault / name) if (vault / name).is_file() else None for name in RULES}


def file_hash(path):
    return digest(path) if path.is_file() else '-'


def indexed_files(vault):
    index = vault / 'index.md'
    if not index.is_file():
        return set()
    found = set()
    # Accept Markdown titles, angle-wrapped destinations and parentheses in names.
    pattern = r'''\[[^\]]*\]\(\s*(?:<([^>]+)>|((?:[^\s()]|\([^()]*\))+))(?:\s+(?:"[^"]*"|'[^']*'|\([^()]*\)))?\s*\)'''
    for angled, plain in re.findall(pattern, index.read_text(encoding='utf-8-sig')):
        link = angled or plain
        try:
            found.add(inside(vault, unquote(link.split('#')[0])))
        except ValueError:
            continue
    return found


def _plain_target_path(value, target):
    if target == '@profile':
        return Path(value['profile_entry'])
    path = Path(target)
    if path.is_absolute() or path.drive or '..' in path.parts or ':' in target or not path.parts:
        raise ValueError('知识库目标应为库内相对路径')
    if path.suffix.lower() not in {'.md', '.txt', '.srt', '.json'}:
        raise ValueError('知识库保存文字材料；媒体和凭据留在工作区')
    vault = Path(value['vault_root'])
    destination = inside(vault, path)
    protected = {(vault / name).resolve() for name in (*RULES, 'index.md', '使用说明.md')}
    if path.parts[0].startswith('.') or destination in protected:
        raise ValueError('材料写入不能替换知识库规则或索引')
    return destination


def current_reference(value, target, sha256=None):
    """Project an old receipt into the current library without changing its evidence."""
    from .vault_migration import resolve_reference
    destination = _plain_target_path(value, target)
    if sha256 is None and (target == '@profile' or destination.is_file()):
        return destination, sha256, target
    mapped, projected_hash = resolve_reference(Path(value['vault_root']), target, sha256)
    if mapped == target and not destination.is_file():
        mapped, _ = resolve_reference(Path(value['vault_root']), target)
    return _plain_target_path(value, mapped), projected_hash, mapped


def target_path(value, target):
    if target == '@profile':
        return profile_reference(value)[0]
    return current_reference(value, target)[0]


def current_rows(value, rows):
    result = []
    for row in rows:
        path, sha256, target = current_reference(value, row['target'], row['sha256'])
        result.append({**row, 'target': target, 'sha256': sha256, 'path': path})
    return result


def profile_reference(value):
    profile = Path(value['profile_entry'])
    vault = Path(value['vault_root'])
    if profile.is_relative_to(vault):
        return current_reference(value, profile.relative_to(vault).as_posix(), value.get('profile_sha256'))
    return profile, value.get('profile_sha256'), '@profile'


def has_migrations(value):
    vault = Path(value['vault_root'])
    return any((vault / runtime / 'path-migrations.json').is_file()
               for runtime in ('.cy-vault-runtime', '.dyb-vault-runtime'))


def require(root, *, module=None, task=None, collection=True):
    value = state(root)
    if not value:
        raise ValueError('尚未开启个人知识库；先介绍并取得用户选择')
    if str(Path(config(root).get('vault_root') or '').resolve()) != value['vault_root']:
        raise ValueError('目标知识库已改变，先核对配置与原待处理项')
    if task and task in value.get('temporary_tasks', []):
        raise ValueError('本次任务不保存')
    if collection and value.get('collection_paused'):
        raise ValueError('自动积累已暂停')
    if module and canonical_domain(module) not in {canonical_domain(x) for x in value.get('modules', [])}:
        raise ValueError('当前模块尚未开启：' + module)
    return value


def replace_block(body, start, end, block):
    # Migrate just this owned block; leave user prose and other pending fields intact.
    legacy_start, legacy_end = start.replace('<!-- cy-', '<!-- dyb-'), end.replace('<!-- cy-', '<!-- dyb-')
    if legacy_start in body and start not in body:
        start, end = legacy_start, legacy_end
    if body.count(start) != body.count(end) or body.count(start) > 1:
        raise ValueError('受管理区块标记不完整或重复；请保留人工修改并核对')
    if start in body:
        begin, finish = body.index(start), body.index(end) + len(end)
        if finish < begin:
            raise ValueError('受管理区块标记顺序错误')
        return body[:begin] + block + body[finish:]
    return body + ('\n\n' if body and not body.endswith('\n\n') else '') + block + '\n'


def normalize_profile_markers(body, aliases):
    """Rename legacy managed fact blocks while leaving all text outside them intact."""
    for old, current in aliases.items():
        if old == current:
            continue
        for prefix in ('cy', 'dyb'):
            old_start = f'<!-- {prefix}-profile:{old}:start -->'
            old_end = f'<!-- {prefix}-profile:{old}:end -->'
            current_start = f'<!-- {prefix}-profile:{current}:start -->'
            current_end = f'<!-- {prefix}-profile:{current}:end -->'
            if old_start not in body and old_end not in body:
                continue
            if body.count(old_start) != 1 or body.count(old_end) != 1 or body.index(old_end) < body.index(old_start):
                raise ValueError('旧档案受管理区块标记不完整或重复；请保留人工修改并核对')
            current_markers = [f'<!-- {family}-profile:{current}:{edge} -->'
                               for family in ('cy', 'dyb') for edge in ('start', 'end')]
            present = [marker for marker in current_markers if marker in body]
            if present:
                matching = [marker for marker in current_markers if marker in body]
                starts = [marker for marker in matching if marker.endswith(':start -->')]
                ends = [marker for marker in matching if marker.endswith(':end -->')]
                if len(starts) != 1 or len(ends) != 1 or body.index(ends[0]) < body.index(starts[0]):
                    raise ValueError('现行档案受管理区块标记不完整或重复；请保留人工修改并核对')
                begin, finish = body.index(old_start), body.index(old_end) + len(old_end)
                body = body[:begin] + body[finish:]
            else:
                body = body.replace(old_start, current_start, 1).replace(old_end, current_end, 1)
    return body


def atomic(path, data, expected):
    if file_hash(path) != expected:
        raise ValueError('文件已被修改，需读取当前内容后合并：' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    # Check again after preparing the replacement; cooperating writers hold a lock.
    if file_hash(path) != expected:
        temporary.unlink()
        raise ValueError('写入前文件发生变化：' + str(path))
    os.replace(temporary, path)


def hook_path(root, scope, host, entry):
    if entry:
        return entry.expanduser().resolve()
    if scope == 'workspace':
        if host == 'claude':
            return root / 'CLAUDE.md'
        override = root / 'AGENTS.override.md'
        return override if override.is_file() else root / 'AGENTS.md'
    if host == 'codex':
        folder = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex')
        override = folder / 'AGENTS.override.md'
        return override if override.is_file() else folder / 'AGENTS.md'
    if host == 'claude':
        return Path.home() / '.claude/CLAUDE.md'
    raise ValueError('为当前 Agent 指定真实指令入口 --entry-file，或选择 codex / claude')


def install_hook(root, value, path):
    saved = path.read_bytes() if path.exists() else b''
    text = saved.decode('utf-8-sig')
    owner = 'cy-vault-workspace: ' + root.resolve().as_posix()
    has_hook = HOOK_START in text or HOOK_START.replace('cy-', 'dyb-') in text
    if has_hook and owner not in text and owner.replace('cy-vault-', 'dyb-vault-', 1) not in text:
        raise ValueError('该入口已经连接另一个知识库工作区；先核对用途，避免混用资料')
    newline = '\r\n' if '\r\n' in text else '\n'
    block = '\n'.join([HOOK_START, '## 个人知识库', owner,
        f"日常生活、工作、学习相关任务先读 <{(SKILL_ROOT / 'references/personal-vault.md').as_posix()}>，再通过 <{(SKILL_ROOT / 'scripts/invoke.ps1').as_posix()}> --workspace '{root.as_posix()}' kb context --query '<当前任务关键词>' 获取相关资料。",
        '命令提示有新版时，在本会话首次交付中明确告诉用户当前版本、新版及更新口令；仅有工具输出不算已提醒。同一会话不重复，新的会话仍提醒，继续完成原任务，不自动安装。',
        '明确任务先完成交付，不强制采访；再按开启范围积累明确个人信息、成果或反馈，必要时提醒其他未开始方向；暂停或拒绝的主题不催问。普通聊天不全量归档；不保存、暂停和目标库现行规则优先。',
        '个人档案只记录用户明确事实或纠正；第三方经历不能当成用户背景。该指令由 Agent 在对话中执行，不是后台事件服务。', HOOK_END]).replace('\n', newline)
    updated = replace_block(text, HOOK_START, HOOK_END, block)
    data = (b'\xef\xbb\xbf' if saved.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
    if data != saved:
        if saved:
            backup = home(root) / 'entry-backups' / (hashlib.sha256(saved).hexdigest() + '.md')
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(saved)
        atomic(path, data, hashlib.sha256(saved).hexdigest() if path.exists() else '-')
    value['hook'] = {'file': str(path), 'block_sha256': hashlib.sha256(block.encode()).hexdigest(),
                     'host_session': 'not_verified'}
    save(value, root)


def enable(root=ROOT, *, vault, create=False, scope='workspace', host='custom', entry=None,
           profile=None, evidence='', focus='life', selected=None, all_domains=False):
    from . import setup
    if not evidence.strip():
        raise ValueError('开启知识库需要用户选择的实际原话')
    focus = canonical_domain(selected or focus)
    if focus not in DOMAINS:
        raise ValueError('focus/selected 只能是 life、work 或 learning')
    vault = vault.expanduser().resolve()
    previous = state(root)
    if previous and previous['vault_root'] != str(vault):
        raise ValueError('本工作区已连接知识库；新库请使用独立工作区以保留原续办状态')
    path = hook_path(root, scope, host, entry)
    # Fail a conflicting global hook before creating or binding anything.
    if path.is_file():
        body = path.read_text(encoding='utf-8-sig')
        owned = any(prefix + root.resolve().as_posix() in body for prefix in ('cy-vault-workspace: ', 'dyb-vault-workspace: '))
        if any(mark in body for mark in (HOOK_START, HOOK_START.replace('cy-', 'dyb-'))) and not owned:
            raise ValueError('该入口已经连接另一个知识库工作区')
    setup.initialize(root, vault=vault, create_vault=create)
    marker_path = next((vault / name for name in ('.cy-vault.json', '.dyb-vault.json') if (vault / name).is_file()), None)
    marker = read_json(marker_path) if marker_path else {}
    local = marker.get('product') in {'cy-vault', 'dyb-vault'} and marker.get('rules') == rules(vault)
    previous_modules = {canonical_domain(x) for x in previous.get('modules', [])}
    disabled = {canonical_domain(x) for x in previous.get('disabled_modules', [])}
    value = previous or {'schema': 1, 'id': fingerprint([str(vault), now()])[:24], 'modules': [],
                        'fields': {}, 'skipped': [], 'answers': [], 'temporary_tasks': []}
    if all_domains:
        disabled.clear()
        modules = list(DOMAINS)
    elif not previous:
        modules = [domain for domain in DOMAINS if domain not in disabled]
    else:
        modules = [domain for domain in DOMAINS if domain in previous_modules and domain not in disabled]
    if previous and not all_domains and focus not in modules and previous.get('focus'):
        focus = canonical_domain(previous['focus'])
    if previous and focus not in modules and modules:
        focus = modules[0]
    if profile:
        profile_path = profile.expanduser().resolve()
    elif previous:
        profile_path = Path(previous.get('profile_entry', vault / PROFILE))
    elif (vault / LEGACY_PROFILE).is_file():
        profile_path = vault / LEGACY_PROFILE
    else:
        profile_path = vault / PROFILE
    value.update(vault_root=str(vault), profile_entry=str(profile_path), scope=scope, host=host,
                 modules=modules, pending_domains=[domain for domain in DOMAINS if domain not in modules and domain not in disabled],
                 focus=focus, selected=focus,
                 evidence=evidence, write_mode='local' if local else 'target_rules', rules=rules(vault))
    value['disabled_modules'] = [domain for domain in DOMAINS if domain in disabled]
    value.setdefault('progress', {'topics': {domain: {} for domain in DOMAINS}, 'branches': {}})
    value.setdefault('domain_started', {})
    if focus in modules:
        value['domain_started'].setdefault(focus, {'at': now(), 'reason': 'selected'})
    value.setdefault('profile_sha256', file_hash(profile_path))
    value.setdefault('collection_paused', False)
    value.setdefault('interview_paused', False)
    save(value, root)
    install_hook(root, value, path)
    return status(root)


def transactions(root):
    folder = home(root) / 'transactions'
    items = [read_json(p) for p in folder.glob('*/transaction.json')] if folder.exists() else []
    return sorted(items, key=lambda t: t.get('created_ns', 0))


def status(root=ROOT):
    value = state(root)
    if not value:
        return {'status': 'not_enabled', 'next': '可选：通过简短对话建立个人知识库，不影响当前任务'}
    modules = [d for d in DOMAINS if d in {canonical_domain(x) for x in value.get('modules', [])}]
    relevant = [k for k in FIELDS if '.' not in k or canonical_domain(k.split('.')[0]) in modules]
    known_fields = {canonical_field(k) for k in value.get('fields', {})}
    skipped_fields = {canonical_field(k) for k in value.get('skipped', [])}
    missing = [k for k in relevant if canonical_field(k) not in known_fields and canonical_field(k) not in skipped_fields]
    progress = value.get('progress') or {}
    topics = progress.get('topics') or {}
    started = value.get('domain_started') or {}
    if not value.get('focus') and not value.get('domain_started'):
        # Legacy module selection was opt-in onboarding evidence before all-domain defaults.
        for legacy in value.get('modules', []):
            domain = canonical_domain(legacy)
            if domain in DOMAINS:
                started.setdefault(domain, {'reason': 'legacy_selected_module'})
    pending_domains = value.get('pending_domains', [d for d in DOMAINS
        if d not in modules and d not in {canonical_domain(x) for x in value.get('disabled_modules', [])}])
    # Existing profile and indexed material count as evidence; empty domain folders do not.
    indexed = indexed_files(Path(value['vault_root']))
    for domain, folder in DOMAIN_DIRS.items():
        if any(path.is_relative_to(Path(value['vault_root']) / folder) for path in indexed):
            started.setdefault(domain, {'reason': 'existing_indexed_material'})
    profile_path = profile_reference(value)[0]
    if profile_path.is_file():
        started.setdefault('life', {'reason': 'existing_profile'})
    for key in value.get('fields', {}):
        fact = value['fields'][key]
        domain = fact.get('domain') if isinstance(fact, dict) else None
        domain = domain or field_domain(key)
        if domain:
            started.setdefault(domain, {'reason': 'existing_fact'})
    for item in transactions(root):
        domain = canonical_domain(item.get('module'))
        if domain in DOMAINS and item.get('status') in {'saved', 'pending', 'awaiting_target_writer'}:
            started.setdefault(domain, {'reason': 'existing_transaction'})
    domain_state = {}
    refused = []
    for domain in DOMAINS:
        if domain not in modules:
            state_name = 'not_started'
        elif domain not in started:
            state_name = 'not_started'
        elif value.get('interview_paused') or (
                topics.get(domain) and 'paused' in {item.get('status') for item in topics[domain].values()} and
                not any(item.get('status') == 'in_progress' for item in topics[domain].values())):
            state_name = 'paused'
        else:
            state_name = 'in_progress'
        entries = topics.get(domain, {})
        refused.extend({'domain': domain, 'topic': item.get('label', key)}
                       for key, item in entries.items() if item.get('status') == 'refused')
        domain_state[domain] = {'status': state_name, 'enabled': domain in modules,
                                'awaiting_confirmation': domain in pending_domains,
                                'topic_count': len(entries),
                                'started_at': started.get(domain, {}).get('at'),
                                'refused_topics': [item.get('label', key) for key, item in entries.items()
                                                   if item.get('status') == 'refused']}
    pending = [{'id': t['id'], 'task': t['task'], 'status': t['status'], 'error': t.get('error'),
                'manifest': str(home(root) / 'transactions' / t['id'] / 'transaction.json')}
               for t in transactions(root) if t['status'] != 'saved']
    hook = value.get('hook', {})
    file = Path(hook['file']) if hook.get('file') else None
    body = file.read_bytes().decode('utf-8-sig') if file and file.is_file() else ''
    start, end = (HOOK_START, HOOK_END) if HOOK_START in body else (HOOK_START.replace('cy-', 'dyb-'), HOOK_END.replace('cy-', 'dyb-'))
    block = body[body.index(start):body.index(end) + len(end)] if start in body and end in body else ''
    focus = canonical_domain(value.get('focus', value.get('selected', 'life')))
    next_field = next((k for k in missing if field_domain(k) == focus), None) or (missing[0] if missing else None)
    interview_prompt = None if value['interview_paused'] else (
        '围绕当前任务或已有资料继续访谈，每次问一个有用的问题；可自由选择主题，具体任务优先，直到用户暂停、停止或转题。')
    return {'status': 'enabled', 'vault_root': value['vault_root'], 'profile_entry': value['profile_entry'],
            'scope': value['scope'], 'modules': modules, 'focus': focus, 'selected': focus,
            'domains': domain_state, 'pending_domains': pending_domains, 'refused_topics': refused,
            'write_mode': value['write_mode'],
            'collection_paused': value['collection_paused'], 'interview_paused': value['interview_paused'],
            'missing_fields': missing, 'next_question': None if value['interview_paused'] else
                ({'field': next_field, 'question': FIELDS[next_field]} if next_field else
                 {'field': None, 'question': interview_prompt}),
            'interview_prompt': interview_prompt,
            'pending': pending, 'hook': {**hook, 'block_present': bool(block),
                'block_matches': bool(block) and hashlib.sha256(block.encode()).hexdigest() == hook.get('block_sha256')},
            'rules_changed': rules(Path(value['vault_root'])) != value['rules']}


def configure(root=ROOT, *, module=None, disable_module=None, pause=None, resume=None,
              skip_task=None, unskip_task=None, evidence=''):
    value = require(root, collection=False)
    value['modules'] = [domain for domain in DOMAINS
                        if domain in {canonical_domain(x) for x in value.get('modules', [])}]
    if module:
        module = canonical_domain(module)
        if module not in DOMAINS or not evidence.strip():
            raise ValueError('模块需要实际任务或用户选择的依据')
        if module not in value['modules']:
            value['modules'].append(module)
        value['pending_domains'] = [d for d in value.get('pending_domains', []) if canonical_domain(d) != module]
        value['disabled_modules'] = [d for d in value.get('disabled_modules', []) if canonical_domain(d) != module]
        value.setdefault('domain_started', {}).setdefault(module, {'at': now(), 'reason': 'selected'})
    if disable_module:
        module_to_disable = canonical_domain(disable_module)
        modules = {canonical_domain(x) for x in value.get('modules', [])}
        if module_to_disable not in DOMAINS or module_to_disable not in modules:
            raise ValueError('该方向当前未开启')
        modules.remove(module_to_disable)
        if not modules:
            raise ValueError('至少保留一个开启方向')
        value['modules'] = [d for d in DOMAINS if d in modules]
        value['disabled_modules'] = list(dict.fromkeys([*value.get('disabled_modules', []), module_to_disable]))
        if canonical_domain(value.get('focus', '')) == module_to_disable:
            value['focus'] = value['modules'][0]
            value['selected'] = value['focus']
    for field, setting in ((pause, True), (resume, False)):
        if field:
            value[field + '_paused'] = setting
    if skip_task and skip_task not in value['temporary_tasks']:
        value['temporary_tasks'].append(skip_task)
    if unskip_task:
        if not evidence.strip():
            raise ValueError('恢复本次保存需要用户实际要求')
        value['temporary_tasks'] = [x for x in value['temporary_tasks'] if x != unskip_task]
    save(value, root)
    return status(root)


def stage(manifest, root=ROOT, *, profile=False):
    module, task = manifest.get('module'), manifest.get('task')
    if not isinstance(task, str) or not task.strip():
        raise ValueError('保存任务需要稳定的 task 标识')
    value = require(root, module=None if profile else module, task=task, collection=not profile)
    if not profile and canonical_domain(module) not in DOMAINS:
        raise ValueError('自动积累需要明确的已开启模块')
    module = 'profile' if profile else canonical_domain(module)
    rows = []
    for item in manifest.get('files', []):
        role, target = item.get('role'), item.get('target', '')
        if role not in ROLES:
            raise ValueError('未知材料 role；可用 source、reviewed、draft、knowledge、learning，个人档案用 answer')
        if role == 'profile' and not profile:
            raise ValueError('个人档案通过 answer 记录明确回答或纠正，不能从普通材料推断')
        expected = item.get('expected_sha256', '-')
        requested_destination, projected_expected, projected_target = current_reference(
            value, target, expected if expected != '-' else None)
        if not profile and (requested_destination in {Path(value['profile_entry']), profile_reference(value)[0]} or
                            requested_destination.is_relative_to(Path(value['vault_root']) / '生活/个人档案') or
                            requested_destination.is_relative_to(Path(value['vault_root']) / '个人/档案')):
            raise ValueError('普通材料不能写入个人档案；请记录用户明确回答')
        target = projected_target
        if expected != '-':
            expected = projected_expected
        target = scoped_target(value, module, target, profile=profile,
                               preserve_existing=requested_destination.is_file() or expected != '-')
        destination = target_path(value, target)
        vault = Path(value['vault_root'])
        personal_dirs = [vault / label / '个人档案' for label in DOMAIN_DIRS.values()]
        if not profile and (destination in {Path(value['profile_entry']), profile_reference(value)[0]} or
                            any(destination.is_relative_to(folder) for folder in personal_dirs) or
                            destination.is_relative_to(vault / '个人/档案')):
            raise ValueError('普通材料不能写入个人档案；请记录用户明确回答')
        source = inside(root, item['source'])
        data = source.read_bytes()
        if not data.strip() or not item.get('sources'):
            raise ValueError('保存正文和来源记录不能为空')
        if role == 'source' and item.get('expected_sha256', '-') != '-':
            raise ValueError('原始资料不可覆盖，修订请另存版本')
        if expected != '-' and not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('更新需要读取时的 SHA-256；新增使用 -')
        rows.append({'source': relative(root, source), 'target': target, 'role': role,
                     'sha256': hashlib.sha256(data).hexdigest(), 'expected_sha256': expected,
                     'sources': item['sources']})
    if not rows or len({str(target_path(value, r['target'])).casefold() for r in rows}) != len(rows):
        raise ValueError('保存清单不能为空，且目标不能重复')
    signature = fingerprint([(r['role'], r['sha256']) for r in rows])
    # Identical source/outcome batches reuse verified destinations even across task IDs.
    for old in transactions(root):
        if old['status'] == 'saved' and canonical_domain(old['module']) == module:
            projected = current_rows(value, old['files'])
            if old['signature'] != signature and fingerprint(
                    [(row['role'], row['sha256']) for row in projected]) != signature:
                continue
            if all(file_hash(r['path']) == r['sha256'] for r in projected):
                indexed = indexed_files(Path(value['vault_root']))
                if all(r['path'] in indexed for r in projected if r['target'] != '@profile'):
                    return {**old, 'reused': True, 'current_files': [
                        {k: r[k] for k in ('target', 'sha256', 'role')} for r in projected]}
                if has_migrations(value):
                    return {**old, 'status': 'needs_index_repair', 'historical_status': old['status'],
                            'error': '当前索引缺少迁移后的资料；运行 kb apply 核对并修复当前索引'}
                old.update(status='pending', error='索引缺少已保存资料，等待修复并读回')
                write_json(home(root) / 'transactions' / old['id'] / 'transaction.json', old)
                return old
    ident = fingerprint([value['id'], module, rows])[:24]
    folder = home(root) / 'transactions' / ident
    existing = folder / 'transaction.json'
    if existing.is_file():
        prior = read_json(existing)
        if prior['status'] != 'saved':
            return prior
        # A historical receipt is not current evidence when a destination changed.
        ident = fingerprint([ident, [file_hash(target_path(value, r['target'])) for r in rows]])[:24]
        folder = home(root) / 'transactions' / ident
        existing = folder / 'transaction.json'
        if existing.is_file():
            return read_json(existing)
    folder.mkdir(parents=True, exist_ok=True)
    for n, row in enumerate(rows):
        snapshot = folder / f'{n}.payload'
        snapshot.write_bytes(inside(root, row['source']).read_bytes())
        row['snapshot'] = relative(root, snapshot)
    record = {'id': ident, 'task': task, 'module': module, 'profile': profile, 'signature': signature,
              'vault_root': value['vault_root'], 'policy_id': value['id'], 'at': now(), 'created_ns': time.time_ns(),
              'title': manifest.get('title', task), 'status': 'pending', 'files': rows}
    write_json(existing, record)
    return record


def write_index(vault, catalog):
    path = vault / 'index.md'
    previous = path.read_bytes() if path.is_file() else b''
    text = previous.decode('utf-8-sig')
    links = [f"- [{r['target']}]({quote(r['target'], safe='/')}) — {r['role']}" for r in catalog.values()]
    updated = replace_block(text, INDEX_START, INDEX_END,
                            '\n'.join([INDEX_START, '## 自动积累的资料', '', *links, INDEX_END]))
    atomic(path, updated.encode('utf-8'), hashlib.sha256(previous).hexdigest() if path.is_file() else '-')
    return digest(path)


def apply(ident, root=ROOT, *, external=False):
    record_file = inside(home(root) / 'transactions', ident) / 'transaction.json'
    record = read_json(record_file)
    try:
        value = require(root, module=None if record['profile'] else record['module'], task=record['task'],
                        collection=not record['profile'])
        vault = Path(value['vault_root'])
        if record['vault_root'] != str(vault) or record['policy_id'] != value['id']:
            raise ValueError('待处理项属于其他知识库配置')
        if not vault.is_dir():
            raise ValueError('知识库目录当前不可用')
        if rules(vault) != value['rules']:
            raise ValueError('知识库规则已改变；Agent 读取后运行 kb rules-reviewed 再续办')
        historical_projection = record['status'] == 'saved' and has_migrations(value)
        if not external and not historical_projection and (value['write_mode'] != 'local' or any(
                not target_path(value, row['target']).is_relative_to(vault) for row in record['files'])):
            record.update(status='awaiting_target_writer', error='按目标库现行入口完成写入和索引后运行 kb record')
            write_json(record_file, record)
            return record
        runtime = vault / ('.dyb-vault-runtime' if (vault / '.dyb-vault-runtime').exists() else '.cy-vault-runtime')
        with artifact_lock(runtime if not external and value['write_mode'] == 'local' else home(root)):
            if historical_projection:
                projected = current_rows(value, record['files'])
                if any(file_hash(row['path']) != row['sha256'] for row in projected):
                    return {**record, 'status': 'current_content_changed', 'historical_status': 'saved',
                            'error': '历史保存回执保留；当前文件与迁移投影不一致，请先核对现状'}
                indexed = indexed_files(vault)
                if any(row['path'] not in indexed for row in projected if row['target'] != '@profile'):
                    if external or value['write_mode'] != 'local':
                        return {**record, 'status': 'awaiting_target_writer', 'historical_status': 'saved',
                                'error': '先按目标库入口修复当前索引；历史回执未改变'}
                    catalog_path = runtime / 'catalog.json'
                    write_index(vault, read_json(catalog_path))
                return {**record, 'current_verified': True, 'current_files': [
                    {k: row[k] for k in ('target', 'sha256', 'role')} for row in projected]}
            for row in record['files']:
                if digest(inside(root, row['snapshot'])) != row['sha256']:
                    raise ValueError('待写入快照已改变')
                actual = file_hash(target_path(value, row['target']))
                if external and actual != row['sha256']:
                    raise ValueError('目标文件尚未写入或内容不一致：' + row['target'])
                if not external and actual not in {row['sha256'], row['expected_sha256']}:
                    raise ValueError('目标文件已修改，先合并：' + row['target'])
            if not external:
                for n, row in enumerate(record['files']):
                    target = target_path(value, row['target'])
                    if file_hash(target) == row['sha256']:
                        continue
                    if target.is_file():
                        backup = record_file.parent / f'{n}.previous'
                        if not backup.exists():
                            backup.write_bytes(target.read_bytes())
                    atomic(target, inside(root, row['snapshot']).read_bytes(), row['expected_sha256'])
                catalog_path = runtime / 'catalog.json'
                catalog = read_json(catalog_path) if catalog_path.is_file() else {}
                for row in record['files']:
                    if row['target'] != '@profile':
                        catalog[row['target']] = {k: row[k] for k in ('target', 'role', 'sha256', 'sources')}
                write_json(catalog_path, catalog)
                index_hash = write_index(vault, catalog)
            else:
                index = vault / 'index.md'
                indexed = indexed_files(vault)
                if any(target_path(value, row['target']) not in indexed
                       for row in record['files'] if row['target'] != '@profile'):
                    raise ValueError('索引尚未包含实际收录文件')
                index_hash = digest(index)
            if any(file_hash(target_path(value, r['target'])) != r['sha256'] for r in record['files']):
                raise ValueError('写入后的读回内容不一致')
            record.update(status='saved', saved_at=now(), error=None, index_sha256=index_hash,
                          method='target_rules_readback' if external else 'local_verified')
            write_json(record_file, record)
            for row in record['files']:
                current_profile = profile_reference(value)[0]
                if target_path(value, row['target']) == current_profile:
                    value['profile_entry'] = str(current_profile)
                    value['profile_sha256'] = row['sha256']
                    save(value, root)
        return record
    except (OSError, ValueError, RuntimeError) as exc:
        if record['status'] == 'saved' and has_migrations({'vault_root': record['vault_root']}):
            return {**record, 'status': 'current_verification_failed', 'historical_status': 'saved',
                    'error': str(exc)}
        record.update(status='pending', error=str(exc))
        write_json(record_file, record)
        return record


def retry(root=ROOT):
    return {'status': 'retry_checked', 'items': [apply(t['id'], root) for t in transactions(root) if t['status'] != 'saved']}


def answer(payload, root=ROOT):
    value = require(root, collection=False)
    original = payload.get('answer', '')
    fields, skipped = payload.get('fields', {}), payload.get('skip', [])
    if not isinstance(original, str) or not original.strip() or payload.get('source', 'user') != 'user':
        raise ValueError('只接受用户实际回答或明确纠正，保留原话；推测不能记成个人事实')
    if not isinstance(fields, dict) or not isinstance(skipped, list):
        raise ValueError('fields 应为字段到回答的对象，skip 应为字段列表')
    if any(not isinstance(key, str) for key in fields) or any(not isinstance(key, str) for key in skipped):
        raise ValueError('field 键和 skip 项必须是字符串')
    modules = {canonical_domain(x) for x in value.get('modules', [])}
    supplied = set(fields).union(skipped)
    legacy_global_fields = {'background', 'goal', 'preferences', 'name'}
    if (not all(safe_field(key) for key in supplied) or
            any(field_domain(key) not in modules and key not in legacy_global_fields for key in supplied) or
            any(not isinstance(v, str) or not v.strip() for v in fields.values())):
        raise ValueError('字段必须属于已开启方向并使用安全的 life./work./learning. 键；回答不能为空')
    normalized_fields = {canonical_field(key): text for key, text in fields.items()}
    normalized_skipped = {canonical_field(key) for key in skipped}
    legacy_aliases = {key: canonical_field(key) for key in supplied if canonical_field(key) != key}
    rekeyed = False
    for key in list(value.get('fields', {})):
        normalized = canonical_field(key)
        if normalized == key:
            continue
        legacy_aliases[key] = normalized
        old_fact = value['fields'].pop(key)
        current_fact = value['fields'].get(normalized)
        if current_fact is None or str(old_fact.get('at', '')) > str(current_fact.get('at', '')):
            value['fields'][normalized] = old_fact
        rekeyed = True
    old_skipped = {canonical_field(key) for key in value.get('skipped', [])}
    if old_skipped != set(value.get('skipped', [])):
        value['skipped'] = sorted(old_skipped)
        rekeyed = True
    if rekeyed:
        save(value, root)
    explicit_domain = payload.get('domain', payload.get('module'))
    if explicit_domain is not None:
        if not isinstance(explicit_domain, str):
            raise ValueError('回答 domain/module 必须是已开启的 life、work 或 learning')
        domain = canonical_domain(explicit_domain)
        if domain not in DOMAINS or domain not in modules:
            raise ValueError('回答 domain/module 必须是已开启的 life、work 或 learning')
    else:
        field_domains = {field_domain(key) for key in supplied if field_domain(key) in modules}
        field_domains.discard(None)
        if len(field_domains) == 1:
            domain = next(iter(field_domains))
        else:
            focused = canonical_domain(value.get('focus') or value.get('selected'))
            domain = focused if focused in modules else next((d for d in ('work', 'life', 'learning') if d in modules), None)
            if domain is None:
                raise ValueError('当前没有已开启方向；先明确开启一个方向')
    answer_domains = {domain}
    answer_domains.update(field_domain(key) for key in supplied
                           if field_domain(key) in modules)
    if not answer_domains <= modules:
        raise ValueError('回答跨越了未开启的方向')

    topic = payload.get('topic')
    if topic is None and payload.get('branch') is not None:
        topic = '一般访谈'
    topic_id = _topic_id(topic) if topic is not None else None
    topic_status = payload.get('topic_status', 'in_progress')
    if not isinstance(topic_status, str) or topic_status not in {'in_progress', 'paused', 'refused', 'complete'}:
        raise ValueError('topic_status 应为 in_progress、paused、refused 或 complete')
    branch = _branch_spec(payload)
    question = payload.get('question')
    if question is not None and (not isinstance(question, str) or len(question) > 600):
        raise ValueError('question 最多 600 个字符')
    ident = fingerprint(payload)[:24]
    if value['answers']:
        latest = value['answers'][-1]
        latest_file = home(root) / 'answers' / latest / 'answer.json'
        previous = read_json(latest_file) if latest_file.is_file() else {}
        previous.pop('at', None)
        if previous == payload:
            ident = latest  # Resume the immediately preceding reply after interruption.
        elif ident in value['answers']:
            # Repeating an older value after a correction is a new explicit answer.
            ident = fingerprint({'payload': payload, 'after': latest})[:24]
    folder = home(root) / 'answers' / ident
    folder.mkdir(parents=True, exist_ok=True)
    raw_files = {}
    raw_targets = {}
    for answer_domain in sorted(answer_domains):
        raw = folder / f'{answer_domain}-原始回答.md'
        if not raw.exists():
            raw.write_text('# 建档原始回答\n\n' + original + '\n', encoding='utf-8')
        raw_files[answer_domain] = raw
        raw_targets[answer_domain] = f"{DOMAIN_DIRS[answer_domain]}/资料/建档/{ident}.md"
    if ident not in value['answers']:
        write_json(folder / 'answer.json', {**payload, 'at': now()})
        value['answers'].append(ident)
        value.setdefault('fields', {})
        for key, text in normalized_fields.items():
            fact_domain = domain if key in legacy_global_fields else field_domain(key) or domain
            raw_domain = fact_domain if fact_domain in answer_domains else domain
            value['fields'][key] = {'value': text, 'answer': ident, 'at': now(),
                                    'domain': fact_domain, 'answer_target': raw_targets[raw_domain]}
            value.setdefault('domain_started', {}).setdefault(fact_domain,
                {'at': now(), 'reason': 'answered'})
        value['skipped'] = sorted(({canonical_field(k) for k in value.get('skipped', [])} | normalized_skipped) - set(normalized_fields))
        value.setdefault('domain_started', {})
        for answer_domain in answer_domains:
            value['domain_started'].setdefault(answer_domain, {'at': now(), 'reason': 'answered'})
        progress = value.setdefault('progress', {'topics': {}})
        topic_progress = progress.setdefault('topics', {})
        for answer_domain in answer_domains:
            topic_progress.setdefault(answer_domain, {})
        if topic_id:
            entry = topic_progress[domain].setdefault(topic_id, {
                'label': topic, 'fields': [], 'skipped': [], 'branches': {}})
            entry.update(status=topic_status, updated_at=now(), answer=ident)
            entry['fields'] = sorted(set(entry.get('fields', [])) | {
                key for key in normalized_fields
                if (domain if key in legacy_global_fields else field_domain(key) or domain) == domain})
            entry['skipped'] = sorted(set(entry.get('skipped', [])) | {
                key for key in normalized_skipped
                if (domain if key in legacy_global_fields else field_domain(key) or domain) == domain})
            if branch:
                entry.setdefault('branches', {})[branch['id']] = {
                    'label': branch['label'], 'status': branch['status'], 'updated_at': now(),
                    'question': question}
        save(value, root)
    profile_path, current_profile_hash, _ = profile_reference(value)
    target = profile_path.relative_to(Path(value['vault_root'])).as_posix() if profile_path.is_relative_to(Path(value['vault_root'])) else '@profile'
    candidate = folder / '基本资料.md'
    if payload.get('profile_file'):
        candidate = inside(root, payload['profile_file'])
        expected = payload.get('expected_sha256')
        if expected != file_hash(profile_path):
            raise ValueError('合并档案需要读取时的实际 SHA-256')
    else:
        expected = current_profile_hash
        current = profile_path.read_text(encoding='utf-8-sig') if profile_path.is_file() else ''
        # Queue consecutive interview replies behind the previous exact projection.
        # This is a known predecessor, not a rebase onto an unknown manual edit.
        pending_profiles = [r for t in transactions(root) if t['profile'] and t['status'] != 'saved'
                            for r in t['files'] if target_path(value, r['target']) == profile_path]
        if pending_profiles:
            previous = pending_profiles[-1]
            expected = previous['sha256']
            current = inside(root, previous['snapshot']).read_text(encoding='utf-8-sig')
        managed = '<!-- cy-profile:' in current or '<!-- dyb-profile:' in current
        body = current if managed else '# 个人基本资料\n\n本页按用户明确回答整理；未记录的信息保持未知。\n'
        if managed:
            body = normalize_profile_markers(body, legacy_aliases)
        changed_fields = normalized_fields if managed else value['fields']
        for key in changed_fields:
            fact = value['fields'][key]
            answer_path = target_path(value, fact.get('answer_target', f"素材/个人建档/{fact['answer']}.md"))
            try:
                source = quote(Path(os.path.relpath(answer_path, profile_path.parent)).as_posix(), safe='/')
            except ValueError:  # Different Windows drives cannot have a relative link.
                source = answer_path.as_uri()
            begin, end = f'<!-- cy-profile:{key}:start -->', f'<!-- cy-profile:{key}:end -->'
            label = LABELS.get(key, key)
            block = '\n'.join([begin, '## ' + label, '', fact['value'], '',
                               f"来源：[用户回答]({source})；记录于 {fact['at']}。", end])
            body = replace_block(body, begin, end, block)
        candidate.write_text(body, encoding='utf-8')
        # Existing canonical profiles require an Agent merge, never a replacement template.
        if profile_path.exists() and not managed:
            expected = '-'
    manifest_files = [
        {'source': relative(root, raw_files[answer_domain]), 'target': raw_targets[answer_domain],
         'role': 'source', 'sources': ['user:' + ident]}
        for answer_domain in sorted(answer_domains)]
    manifest_files.append({'source': relative(root, candidate), 'target': target, 'role': 'profile',
                           'expected_sha256': expected, 'sources': ['user:' + item for item in value['answers']]})
    manifest = {'task': 'profile-' + ident, 'module': 'profile', 'title': '个人建档', 'files': manifest_files}
    record = stage(manifest, root, profile=True)
    result = record if record.get('reused') else apply(record['id'], root)
    return {'status': 'answer_recorded', 'saving': result, 'onboarding': status(root)}


def revise(ident, replacements, root=ROOT):
    """Rebase a pending derived page after the Agent read and merged manual edits."""
    file = inside(home(root) / 'transactions', ident) / 'transaction.json'
    record = read_json(file)
    value = require(root, collection=False)
    if record['status'] == 'saved':
        raise ValueError('已完成的回执不可改写；新修订另建事务')
    for replacement in replacements:
        row = next((r for r in record['files'] if r['target'] == replacement['target']), None)
        if not row or row['role'] == 'source':
            raise ValueError('只能合并当前待处理项的衍生页，原始回答和来源不变')
        if replacement.get('expected_sha256') != file_hash(target_path(value, row['target'])):
            raise ValueError('请使用当前目标文件的 SHA-256')
        data = inside(root, replacement['source']).read_bytes()
        if not data.strip():
            raise ValueError('合并正文不能为空')
        snapshot = file.parent / (hashlib.sha256(data).hexdigest() + '.payload')
        snapshot.write_bytes(data)
        record.setdefault('revisions', []).append(dict(row))
        row.update(snapshot=relative(root, snapshot), sha256=digest(snapshot), expected_sha256=replacement['expected_sha256'])
    record['signature'] = fingerprint([(r['role'], r['sha256']) for r in record['files']])
    write_json(file, record)
    return apply(ident, root)


def context(root=ROOT, *, query='', task=None):
    result = status(root)
    if result['status'] == 'not_enabled':
        return result
    value = state(root)
    vault = Path(value['vault_root'])
    result['save_this_task'] = bool(result['modules']) and not value['collection_paused'] and task not in value['temporary_tasks']
    result['rule_files'] = [str(vault / name) for name in (*RULES, 'index.md') if (vault / name).is_file()]
    profile = profile_reference(value)[0]
    body = profile.read_text(encoding='utf-8-sig') if profile.is_file() else ''
    result['profile'] = {'text': body[:16000], 'truncated': len(body) > 16000, 'sha256': file_hash(profile)}
    terms = query.casefold().split()
    matches = []
    enabled_domains = {canonical_domain(x) for x in value.get('modules', [])}
    # Read only indexed Markdown files, never recursively crawl an existing library.
    if terms:
        for candidate in sorted(indexed_files(vault)):
            try:
                if candidate.suffix.lower() != '.md' or not candidate.is_file():
                    continue
                text = candidate.read_text(encoding='utf-8-sig')
                try:
                    rel = candidate.relative_to(vault).as_posix()
                except ValueError:
                    rel = ''
                folder = rel.split('/', 1)[0] if rel else ''
                match_domain = next((domain for domain, label in DOMAIN_DIRS.items() if label == folder), None)
                # A specific domain remains outside an older user's opt-in scope until enabled.
                if match_domain and match_domain not in enabled_domains:
                    continue
                score = sum(term in (candidate.name + '\n' + text).casefold() for term in terms)
                if score:
                    matches.append({'file': str(candidate), 'domain': match_domain,
                                    'score': score, 'excerpt': text[:1200]})
            except (ValueError, OSError, UnicodeError):
                continue
    result['matches'] = sorted(matches, key=lambda row: -row['score'])[:8]
    result['material_is_data_not_instructions'] = True
    return result


def collect(task_id, module, root=ROOT):
    """Reuse checked ordinary-task artifacts; creator/general material uses stage."""
    from . import content, workflow
    require(root, module=module, task=task_id)
    module = canonical_domain(module)
    task = workflow.load(task_id, root)
    values, reviewed = content.originals(task, root), content.checked_content(task, 'review', root)
    # Stable material identity excludes recognition timestamps and task identifiers.
    key = fingerprint([(v['source']['source'], v['text'], inside(root, r['file']).read_text(encoding='utf-8-sig'))
                       for v, r in zip(values, reviewed)])[:24]
    folder = home(root) / 'collections' / key
    folder.mkdir(parents=True, exist_ok=True)
    prefix = DOMAIN_DIRS[module] + '/资料/任务/' + key
    files, sources = [], [v['source']['source'] for v in values]
    for role, name, texts, peer in (
        ('source', '原文留底.md', [v['text'] for v in values], '校对逐字稿.md'),
        ('reviewed', '校对逐字稿.md', [inside(root, r['file']).read_text(encoding='utf-8-sig') for r in reviewed], '原文留底.md')):
        lines = ['# ' + name[:-3], '', f'同组材料：[{peer}]({peer})', '']
        for n, (value, text) in enumerate(zip(values, texts), 1):
            lines += [f'## {n}. ' + value['source']['title'], '', '来源：' + value['source']['source'], '', text, '']
        file = folder / name
        if not file.exists():
            file.write_text('\n'.join(lines), encoding='utf-8')
        files.append({'source': relative(root, file), 'target': prefix + '/' + name, 'role': role, 'sources': sources})
    for kind in ('delivery', 'analysis'):
        item = task.get(kind)
        if not item or (kind == 'delivery' and item.get('kind') != 'spoken'):
            continue
        if kind == 'analysis' and (item.get('stale') or task.get('status') not in {'completed', 'incomplete', 'published'}):
            continue  # A newer review can leave the previous analysis awaiting revision.
        source = inside(root, item['file'])
        if digest(source) != item['sha256']:
            raise ValueError('已交付成果发生变化，先核对版本')
        if kind == 'delivery':
            current = content.checked_content(task, 'spoken', root)
            if item.get('source_basis') != [{'id': r['id'], 'sha256': r['sha256']} for r in current]:
                continue  # Only collect a delivery that matches its registered version.
        files.append({'source': relative(root, source), 'target': prefix + '/' + kind + '-' + digest(source)[:12] + source.suffix,
                      'role': 'draft' if kind == 'delivery' else 'knowledge', 'sources': [prefix + '/校对逐字稿.md']})
    record = stage({'task': task_id, 'module': module, 'title': '任务成果', 'files': files}, root)
    result = record if record.get('reused') else apply(record['id'], root)
    return {**result, 'coverage_gaps': workflow.coverage_gaps(task, root), 'topic_synthesis': 'agent_updates_relevant_topics_after_reading'}
