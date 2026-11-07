"""Local first-use guidance. Never submits media, reads keys, or infers user intent."""
from pathlib import Path

from .common import ROOT, SKILL_ROOT, now, read_json, write_json


def catalog():
    return read_json(SKILL_ROOT / 'assets/capabilities.json')


def status(root=ROOT):
    revision = catalog()['revision']
    path = root / '.local/onboarding.json'
    try:
        saved = read_json(path) if path.is_file() else {}
    except (ValueError, OSError):
        saved = {}
    return {'revision': revision, 'due': saved.get('presented_revision') != revision,
            'guide_file': str(SKILL_ROOT / 'references/onboarding.md'),
            'welcome_command': 'welcome', 'state_file': '.local/onboarding.json',
            'meaning': 'presentation_record_only_not_user_comprehension'}


def acknowledge(root=ROOT, *, language='zh'):
    value = status(root)
    write_json(root / value['state_file'], {'presented_revision': value['revision'],
        'presented_at': now(), 'language': language,
        'meaning': 'Agent reports that the introduction was shown in chat; not user acceptance'})
    return {'status': 'introduction_recorded', 'onboarding': status(root), 'cloud_asr_called': False}


def welcome(diagnostics, root=ROOT, *, language='zh'):
    if language not in ('zh', 'en'):
        raise ValueError('language must be zh or en')
    data = catalog()
    entries = [{'id': c['id'], **c[language]} for c in data['capabilities']]
    message = [data['intro'][language], '']
    for entry in entries:
        message += [entry['title'] + ' — ' + entry['example'], entry['outcome'], '']
    message += data['notes'][language]
    checks = diagnostics.get('checks', {})
    acquisition = all(checks.get(k, False) for k in ('ffmpeg', 'ffprobe', 'playwright', 'chromium'))
    audio = all(checks.get(k, False) for k in ('ffmpeg', 'ffprobe'))
    credentials = bool(diagnostics.get('doubao_credentials_present'))
    return {'status': 'welcome', 'language': language, 'message': '\n'.join(message),
            'capabilities': entries, 'onboarding': status(root),
            'readiness': {'existing_text': 'available_to_agent',
                'download_environment': 'ready' if acquisition else 'needs_dependencies',
                'new_speech': 'ready_for_authorized_trial' if audio and credentials else
                              'needs_dependencies' if not audio else 'needs_speech_credentials',
                'speech_scope': 'local_media; Douyin media also needs download_environment',
                'knowledge_destination': 'configured_not_write_authorized' if diagnostics.get('vault_root') else 'choose_when_requested',
                'visual_review': 'check_current_agent_image_tools',
                'cloud_access': 'not_tested', 'douyin_login': 'not_tested_not_a_setup_requirement'},
            'next_action_for_agent': 'Present this introduction and relevant readiness in the conversation, then acknowledge; route the current request using the guide. Do not make the user learn commands.',
            'cloud_asr_called': False}
