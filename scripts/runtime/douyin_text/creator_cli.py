"""CLI boundary for public creator tasks; all actual work lives in the owning modules."""
from pathlib import Path

from . import creator, creator_review
from .common import ROOT, artifact_lock


def add_parser(commands):
    parser = commands.add_parser('creator', help='博主全量分析或独立批量下载；按作品保存与续跑')
    sub = parser.add_subparsers(dest='creator_command', required=True)
    plan = sub.add_parser('plan', help='建立博主任务，不下载、不提交付费识别')
    plan.add_argument('source')
    plan.add_argument('--mode', choices=('analyze', 'download'), required=True)
    plan.add_argument('--quality', choices=('best', 'compact'))
    plan.add_argument('--instruction', default=creator.DEFAULT_INSTRUCTION)
    plan.add_argument('--images', action='store_true', help='已检查当前 Agent 确实可看图')
    plan.add_argument('--parallel-vision', action='store_true', help='宿主实际支持独立视觉核对任务，最多领取两份')
    offline = sub.add_parser('reanalyze', help='从已有任务建立独立离线分析；不刷新、不识别')
    offline.add_argument('task')
    offline.add_argument('--instruction', required=True)
    offline.add_argument('--images', action='store_true', help='当前会话实际可看图，不继承旧会话能力')
    offline.add_argument('--parallel-vision', action='store_true')
    for name in ('show', 'export'):
        sub.add_parser(name).add_argument('task')
    discovery = sub.add_parser('discover', help='刷新主页，逐页保存；未到底明确标为不完整')
    discovery.add_argument('task')
    discovery.add_argument('--anonymous-only', action='store_true')
    discovery.add_argument('--max-seconds', type=float, default=600)
    preflight = sub.add_parser('preflight', help='展示新增识别用量，不请求语音 API')
    preflight.add_argument('task')
    preflight.add_argument('--price-per-hour', type=float, help='仅填用户账户实际适用的每小时单价')
    preflight.add_argument('--item', action='append', help='只预览这些已发现的作品 ID；默认全部')
    approval = sub.add_parser('authorize', help='登记用户看过用量后的整批付费授权')
    approval.add_argument('task')
    approval.add_argument('--quote', required=True)
    approval.add_argument('--evidence', required=True)
    approval.add_argument('--max-audio-seconds', type=float)
    run = sub.add_parser('run', help='逐作品有限并发获取；下载模式永不识别，分析模式仅处理授权语音')
    run.add_argument('task')
    run.add_argument('--download-workers', type=int, default=2)
    run.add_argument('--asr-workers', type=int, default=1)
    run.add_argument('--item-timeout', type=float, default=300)
    run.add_argument('--retry-evidence', default='')
    run.add_argument('--limit-items', type=int, help='本次最多处理的作品数，仍保留全清单与未完成状态')
    run.add_argument('--item', action='append', help='本次只处理指定作品 ID')
    capability = sub.add_parser('capabilities', help='按当前会话实际工具更新能力，不按 Agent 品牌猜测')
    capability.add_argument('task')
    capability.add_argument('--images', action='store_true')
    capability.add_argument('--parallel-vision', action='store_true')
    prepare = sub.add_parser('prepare', help='按时间准备多图与全文核对包；此命令不完成视觉核对')
    prepare.add_argument('task')
    prepare.add_argument('--max-frames', type=int)
    prepare.add_argument('--strategy', choices=('content', 'action', 'subtitle'), default='content')
    prepare.add_argument('--batch-size', type=int, default=4)
    prepare.add_argument('--prepare-workers', type=int, default=2)
    prepare.add_argument('--reanalyze', action='store_true', help='重新分析已有材料，仍复用有效语音转写')
    prepare.add_argument('--item', action='append', help='只准备这些作品 ID；默认全部已就绪作品')
    prepare.add_argument('--cached-only', action='store_true', help='仅用本地材料；不联网补封面')
    claim = sub.add_parser('claim', help='领取一份核对包；具备并发能力时最多两份在处理')
    claim.add_argument('task')
    claim.add_argument('--worker', required=True)
    release = sub.add_parser('release', help='释放自己领取的核对包以便继续处理')
    release.add_argument('task')
    release.add_argument('--packet', required=True)
    release.add_argument('--worker', required=True)
    detail = sub.add_parser('detail', help='用缓存原视频对疑点定点补帧，不调用识别')
    detail.add_argument('task')
    detail.add_argument('--item', required=True)
    detail.add_argument('--start', type=float, default=0)
    detail.add_argument('--end', type=float)
    detail.add_argument('--every-frame', action='store_true')
    detail.add_argument('--max-frames', type=int, default=40)
    record = sub.add_parser('record', help='登记实际完成的看图、校对和逐条分析')
    record.add_argument('task')
    record.add_argument('--worker', required=True)
    record.add_argument('--file', type=Path, required=True)
    report = sub.add_parser('report', help='登记基于逐条证据的账号、内容、选题和阶段总结')
    report.add_argument('task')
    report.add_argument('--file', type=Path, required=True)


def dispatch(args):
    name = args.creator_command
    if name == 'plan':
        return creator.plan(args.source, mode=args.mode, quality=args.quality, instruction=args.instruction,
                            images=args.images, parallel_vision=args.parallel_vision)
    if name == 'reanalyze':
        return creator.reanalyze(args.task, args.instruction, images=args.images, parallel_vision=args.parallel_vision)
    if name == 'discover':
        return creator.discover(args.task, anonymous_only=args.anonymous_only, max_seconds=args.max_seconds)
    if name == 'preflight':
        return creator.preflight(args.task, price_per_hour=args.price_per_hour, item_ids=args.item)
    if name == 'authorize':
        return creator.authorize(args.task, args.quote, args.evidence, max_audio_seconds=args.max_audio_seconds)
    if name == 'run':
        return creator.run(args.task, download_workers=args.download_workers, asr_workers=args.asr_workers,
                           item_timeout=args.item_timeout, retry_evidence=args.retry_evidence,
                           limit_items=args.limit_items, item_ids=args.item)
    if name == 'prepare':
        return creator_review.prepare(args.task, max_frames=args.max_frames, strategy=args.strategy,
                                      batch_size=args.batch_size, prepare_workers=args.prepare_workers,
                                      reanalyze=args.reanalyze, item_ids=args.item, cached_only=args.cached_only)
    if name == 'claim':
        return creator_review.claim(args.task, args.worker)
    if name == 'release':
        return creator_review.release(args.task, args.packet, args.worker)
    if name == 'detail':
        return creator_review.detail(args.task, args.item, start=args.start, end=args.end,
                                     every_frame=args.every_frame, max_frames=args.max_frames)
    if name == 'record':
        return creator_review.record(args.task, args.file, args.worker)
    if name == 'report':
        return creator_review.report(args.task, args.file)
    if name == 'capabilities':
        task = creator.load(args.task)
        with artifact_lock(creator.account_dir(task, ROOT)):
            task = creator.load(args.task)
            task['capabilities'] = {'images': args.images, 'parallel_vision': args.images and args.parallel_vision}
            creator.save(task)
        return creator.summary(task)
    if name == 'export':
        return creator.export(args.task)
    return creator.summary(creator.load(args.task))
