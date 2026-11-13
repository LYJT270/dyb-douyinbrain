"""Agent-facing commands for personal-vault operations (no interactive CLI wizard)."""
from pathlib import Path

from . import personal_vault as kb
from .common import ROOT, artifact_lock, inside, read_json


def add_parser(sub):
    parser = sub.add_parser('kb', help='个人知识库建档、上下文、主动积累与续办')
    commands = parser.add_subparsers(dest='kb_command', required=True)
    commands.add_parser('status')
    context = commands.add_parser('context')
    context.add_argument('--query', default='')
    context.add_argument('--task')
    enable = commands.add_parser('enable')
    enable.add_argument('--vault', type=Path, required=True)
    enable.add_argument('--create', action='store_true')
    enable.add_argument('--scope', choices=['workspace', 'agent'], required=True)
    enable.add_argument('--host', choices=['codex', 'claude', 'custom'], default='custom')
    enable.add_argument('--entry-file', type=Path)
    enable.add_argument('--profile-entry', type=Path)
    enable.add_argument('--evidence', required=True)
    module = commands.add_parser('module')
    module.add_argument('module', choices=kb.MODULES)
    module.add_argument('--evidence', required=True)
    for name in ('pause', 'resume'):
        action = commands.add_parser(name)
        action.add_argument('area', choices=['collection', 'interview'])
    for name in ('skip-task', 'unskip-task'):
        action = commands.add_parser(name)
        action.add_argument('task')
        action.add_argument('--evidence', default='')
    answer = commands.add_parser('answer')
    answer.add_argument('--file', type=Path, required=True)
    stage = commands.add_parser('stage')
    stage.add_argument('--manifest', type=Path, required=True)
    stage.add_argument('--prepare-only', action='store_true')
    for name in ('apply', 'record'):
        commands.add_parser(name).add_argument('transaction')
    commands.add_parser('retry')
    revise = commands.add_parser('revise')
    revise.add_argument('transaction')
    revise.add_argument('--file', type=Path, required=True)
    collect = commands.add_parser('collect')
    collect.add_argument('task')
    collect.add_argument('--module', choices=kb.MODULES, required=True)
    rules = commands.add_parser('rules-reviewed')
    rules.add_argument('--evidence', required=True, help='Agent 已读规则的具体结论，不索要重复用户确认')
    rules.add_argument('--writer', choices=['local', 'target_rules'], required=True)


def dispatch(args, root=ROOT):
    action = args.kb_command
    if action == 'status':
        return kb.status(root)
    if action == 'context':
        return kb.context(root, query=args.query, task=args.task)
    with artifact_lock(kb.home(root) / 'control'):
        if action == 'enable':
            return kb.enable(root, vault=args.vault, create=args.create, scope=args.scope, host=args.host,
                             entry=args.entry_file, profile=args.profile_entry, evidence=args.evidence)
        if action == 'module':
            return kb.configure(root, module=args.module, evidence=args.evidence)
        if action in {'pause', 'resume'}:
            return kb.configure(root, **{action: args.area})
        if action in {'skip-task', 'unskip-task'}:
            return kb.configure(root, **{action.replace('-', '_'): args.task}, evidence=args.evidence)
        if action == 'answer':
            return kb.answer(read_json(inside(root, args.file)), root)
        if action == 'stage':
            item = kb.stage(read_json(inside(root, args.manifest)), root)
            return item if args.prepare_only or item.get('reused') else kb.apply(item['id'], root)
        if action in {'apply', 'record'}:
            return kb.apply(args.transaction, root, external=action == 'record')
        if action == 'retry':
            return kb.retry(root)
        if action == 'revise':
            return kb.revise(args.transaction, read_json(inside(root, args.file)), root)
        if action == 'collect':
            return kb.collect(args.task, args.module, root)
        if action == 'rules-reviewed':
            value = kb.require(root, collection=False)
            if not args.evidence.strip():
                raise ValueError('需要具体的规则核对结论')
            value.update(rules=kb.rules(Path(value['vault_root'])), write_mode=args.writer,
                         rules_review={'evidence': args.evidence, 'at': kb.now()})
            kb.save(value, root)
            return kb.status(root)
    raise ValueError('Unknown personal-vault command')
