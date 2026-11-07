"""Package and installation identities for the five business entrypoints."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def validate_suite(suite, files):
    if not isinstance(suite, dict) or suite.get('schema') != 1 or suite.get('product') != 'dyb-douyinbrain':
        raise ValueError('Unsupported Skill suite identity')
    names = set()
    members = suite.get('members')
    if not isinstance(members, list) or not members:
        raise ValueError('Skill suite members are missing')
    for member in members:
        name = member.get('name', '')
        if not re.fullmatch(r'dyb-[a-z][a-z0-9-]*', name) or name == 'dyb-douyinbrain' or name in names:
            raise ValueError('Invalid or duplicate suite member')
        prefix = 'skills/' + name
        if member.get('source') != prefix:
            raise ValueError('Suite member source must match its name')
        if not {prefix + '/' + x for x in ('SKILL.md', 'agents/openai.yaml', 'scripts/invoke.ps1')} <= set(files):
            raise ValueError('Suite member is missing its entrypoint: ' + name)
        names.add(name)
    if any(p.startswith('skills/') and p.split('/')[1] not in names for p in files):
        raise ValueError('Unregistered Skill in the package')
    return suite


def check_installed(skill: Path, manifest=None):
    manifest = manifest or json.loads((skill / 'bundle.json').read_text(encoding='utf-8-sig'))
    suite = manifest.get('skill_suite')
    if not suite:
        return {'status': 'legacy_single_skill', 'verified': True, 'members': []}
    validate_suite(suite, manifest['file_sha256'])
    for name, checksum in manifest['file_sha256'].items():
        if name.startswith('skills/'):
            continue  # The package's child payloads are installed as siblings, checked below.
        file = skill / name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != checksum:
            raise ValueError('Shared suite payload differs: ' + name)
    if (skill / 'VERSION').read_text(encoding='utf-8-sig').strip() != manifest['version']:
        raise ValueError('Shared runtime version differs from the suite')
    manifest_hash = hashlib.sha256((skill / 'bundle.json').read_bytes()).hexdigest()
    rows = []
    for member in suite['members']:
        target = skill.parent / member['name']
        marker = json.loads((target / '.dyb-member.json').read_text(encoding='utf-8-sig'))
        if (marker.get('product'), marker.get('name'), marker.get('version'), marker.get('manifest_sha256')) != (
                'dyb-douyinbrain', member['name'], manifest['version'], manifest_hash):
            raise ValueError('Installed suite member identity differs: ' + member['name'])
        prefix = member['source'] + '/'
        for name, checksum in manifest['file_sha256'].items():
            if name.startswith(prefix):
                file = target / name[len(prefix):]
                if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != checksum:
                    raise ValueError('Installed suite member differs: ' + member['name'])
        rows.append({'name': member['name'], 'skill_file': str(target / 'SKILL.md'), 'version': manifest['version']})
    return {'status': 'verified', 'verified': True, 'members': rows}
