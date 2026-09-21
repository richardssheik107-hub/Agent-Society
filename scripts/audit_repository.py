#!/usr/bin/env python3
"""只读盘点与原文核验。需要完整 Git 历史，不读取 .env。"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit() -> dict:
    files = git('ls-files').decode().splitlines()
    manifest = ROOT / 'docs/current/cleanup_manifest.json'
    errors, modules, checked = [], {}, []
    if not manifest.exists():
        errors.append('缺少清理清单')
    else:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        pairs = list(data['archive_files'])
        for group in data['archive_directories']:
            original = git('ls-tree', '-r', '--name-only', group['ref'], group['source']).decode().splitlines()
            for source in original:
                relative = Path(source).relative_to(group['source'])
                pairs.append({'ref': group['ref'], 'source': source,
                              'archive': str(Path(group['archive']) / relative)})
        overrides = data.get('archive_original_overrides', {})
        known = {entry['archive'] for entry in pairs}
        if set(overrides) - known:
            errors.append('原文映射含未知条目')
        for entry in pairs:
            original_path = entry['archive']
            selected = overrides.get(original_path, original_path)
            p = (ROOT / selected).resolve()
            if not p.is_relative_to(ROOT.resolve()):
                errors.append('原文映射越出仓库: ' + original_path)
                continue
            expected = sha(git('show', entry['ref'] + ':' + entry['source']))
            if not p.is_file() or sha(p.read_bytes()) != expected:
                errors.append('归档原文变化: ' + selected)
            checked.append({'archive': selected, 'reading_path': original_path, 'sha256': expected})
        original = git('ls-tree', '-r', '--name-only', data['research_base']).decode().splitlines()
        for source in original:
            if source in data['allowed_legacy_changes']:
                continue
            if not any(source.startswith(prefix) for prefix in data['protected_base_prefixes']):
                continue
            p = ROOT / source
            expected = sha(git('show', data['research_base'] + ':' + source))
            if not p.is_file() or sha(p.read_bytes()) != expected:
                errors.append('历史代码变化: ' + source)
        for source in data['protected_main_files']:
            p = ROOT / source
            expected = sha(git('show', data['main_base'] + ':' + source))
            if not p.is_file() or sha(p.read_bytes()) != expected:
                errors.append('其他成员数据变化: ' + source)
        actual = git('rev-parse', 'HEAD:third_party/AgentSociety').decode().strip()
        if actual != data['upstream_gitlink']:
            errors.append('上游子模块版本改变')
    for name in files:
        p = ROOT / name
        if not p.is_file() or not name.endswith('.py'):
            continue
        if name.startswith(('src/', 'scripts/', 'tests/', 'smoke/')):
            try:
                ast.parse(p.read_text(encoding='utf-8'))
            except SyntaxError:
                errors.append('Python 语法错误: ' + name)
        if name.startswith('src/social_sim/'):
            module = name.split('/')[2]
            modules[module] = modules.get(module, 0) + 1
    for p in [ROOT / 'README.md', *(ROOT / 'docs/current').glob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
            if re.match(r'[a-z]+://', link) or link.startswith('#'):
                continue
            target = (p.parent / link.split('#', 1)[0]).resolve()
            if not target.exists():
                errors.append(f'断链: {p.relative_to(ROOT)} -> {link}')
    return {'tracked_files': len(files), 'modules': modules, 'archived_count': len(checked),
            'archived': checked, 'errors': errors,
            'status': 'PASS' if not errors else 'FAIL', 'read_only': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.check and report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
