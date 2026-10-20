#!/usr/bin/env python3
"""Sync Shadowrocket modules and proxy external GitHub script downloads.

Only download directives are changed; regexes, MITM settings and comments stay intact.
Uses only the Python standard library.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'modules.json'
OUTPUT = ROOT / 'modules'
README = ROOT / 'README.md'

SCRIPT_PATH = re.compile(r'(?i)(\bscript-path\s*=\s*)(https://[^\s,;"\x27]+)')
RULE_SET = re.compile(r'(?i)(\bRULE-SET\s*,\s*)(https://[^\s,;"\x27]+)')
FILENAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\.(?:module|sgmodule)\Z')
REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
BRANCH = re.compile(r'[A-Za-z0-9_./-]+\Z')


def proxy_github_url(url: str, prefix: str) -> str:
    """Proxy GitHub raw assets only; normalize /blob/ and /raw/ file URLs."""
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        return url
    host = (parsed.hostname or '').lower()
    if host in ('raw.githubusercontent.com', 'gist.githubusercontent.com'):
        if not parsed.path.strip('/'):
            return url
        target = url
    elif host == 'github.com':
        found = re.fullmatch(r'/([^/]+)/([^/]+)/(?:blob|raw)/(.+)', parsed.path)
        if not found:
            return url
        owner, repo, remainder = found.groups()
        target = urlunsplit(('https', 'raw.githubusercontent.com',
                             f'/{owner}/{repo}/{remainder}', parsed.query, parsed.fragment))
    else:
        return url
    return prefix + target


def convert_module(content: str, prefix: str) -> str:
    """Rewrite actual download fields, not regex patterns or comment text."""
    section = ''
    output = []
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            section = stripped.lower()
        if not stripped or stripped.startswith(('#', ';')):
            output.append(line)
            continue
        if section == '[script]':
            line = SCRIPT_PATH.sub(
                lambda m: m.group(1) + proxy_github_url(m.group(2), prefix), line)
        elif section == '[rule]':
            line = RULE_SET.sub(
                lambda m: m.group(1) + proxy_github_url(m.group(2), prefix), line)
        output.append(line)
    return ''.join(output)


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError('JSON 配置顶层必须是对象')
    prefix = config.get('proxy_prefix')
    if not isinstance(prefix, str) or not prefix.endswith('/'):
        raise ValueError('proxy_prefix 必须是以 / 结尾的 HTTPS 代理前缀')
    parsed = urlsplit(prefix)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('proxy_prefix 必须是有效的 HTTPS URL')
    if not REPOSITORY.fullmatch(config.get('repository', '')):
        raise ValueError('repository 必须采用 owner/repo 格式')
    branch = config.get('branch', '')
    if not isinstance(branch, str) or not BRANCH.fullmatch(branch) or '..' in branch:
        raise ValueError('branch 非法')
    modules = config.get('modules')
    if not isinstance(modules, list) or not modules:
        raise ValueError('modules 必须是非空数组')
    seen = set()
    for item in modules:
        if not isinstance(item, dict):
            raise ValueError('每个模块必须是 JSON 对象')
        filename, source, name = item.get('filename'), item.get('source'), item.get('name')
        if not isinstance(filename, str) or not FILENAME.fullmatch(filename):
            raise ValueError(f'不合法的 filename: {filename!r}')
        if filename.lower() in seen:
            raise ValueError(f'重复的 filename: {filename}')
        seen.add(filename.lower())
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f'{filename} 缺少模块名称 name')
        if not isinstance(source, str):
            raise ValueError(f'{filename} 缺少 source')
        url = urlsplit(source)
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError(f'{filename} 的 source 必须是 HTTPS URL')


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={
        'User-Agent': 'shadowrocket-module-sync/1.0',
        'Accept': 'text/plain, */*',
    })
    last_exc = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError('上游模块超过 2 MB')
            content = data.decode('utf-8-sig')
            if not content.strip() or re.search(r'(?i)^\s*(?:<!doctype html|<html\b)', content):
                raise ValueError('上游内容为空或是 HTML 页面，不是模块文本')
            return content
        except (OSError, UnicodeError, ValueError) as exc:
            last_exc = exc
            if isinstance(exc, ValueError) or attempt == 2:
                break
            time.sleep(2 ** attempt)
    raise RuntimeError(f'下载失败 {url}: {last_exc}')


def markdown_cell(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def make_readme(config: dict) -> str:
    repository, branch, prefix = (config[key] for key in ('repository', 'branch', 'proxy_prefix'))
    lines = [
        '# Shadowrocket 模块 GitHub 代理转换',
        '',
        '通过 GitHub Actions 定时下载上游 `.module` 或 `.sgmodule`，将 `[Script]` 中的 `script-path` 和'
        ' `[Rule]` 中的远程 `RULE-SET` GitHub Raw 地址改写为代理地址。'
        ' 其他规则、脚本参数、MITM 配置保持不变。',
        '',
        '> 此 README 的模块清单由 `scripts/convert.py` 自动生成。'
        ' 代理由第三方提供，速度及可用性可能变化。',
        '',
        '## 模块下载',
        '',
        '| 模块 | 原始模块 | 转换后的 Raw | 代理后的 Raw（推荐） |',
        '| --- | --- | --- | --- |',
    ]
    for module in config['modules']:
        raw = f'https://raw.githubusercontent.com/{repository}/{branch}/modules/{module["filename"]}'
        name = markdown_cell(module['name'])
        source = module['source']
        lines.append(f'| {name} | [上游原版]({source}) | [直接下载]({raw}) | [代理下载]({prefix}{raw}) |')
    lines += [
        '',
        '## 添加或更新模块',
        '',
        '只需编辑 [`config/modules.json`](config/modules.json) 的 `modules` 数组，'
        '为每个模块填写 `name`、`source`（原始 HTTPS 模块链接）、`filename`（如 `youtube.module` 或 `YouTube.Enhance.sgmodule`）。',
        '可按需修改 `proxy_prefix`（HTTPS 代理前缀，末尾保留 `/`）。'
        ' 保存并推送后，GitHub Actions 会自动生成 `modules/` 下的文件及这份链接清单。',
        '',
        '也可以在仓库的 **Actions → Sync Shadowrocket modules → Run workflow** 手动运行。'
        ' 默认每天同步一次；上游下载失败时任务会报错，不会提交不完整内容。',
        '',
        '## 转换规则与注意事项',
        '',
        '- 仅处理 `[Script]` 内 `script-path=` 以及 `[Rule]` 内 `RULE-SET,` 的 HTTPS GitHub 资源；'
        '支持 `raw.githubusercontent.com`、`gist.githubusercontent.com`、'
        '`github.com/owner/repo/blob/...` 和 `/raw/...`。',
        '- 已加代理的链接不会重复代理；非 GitHub URL、注释和 URL Rewrite 正则不会改写。',
        '- 这是**链接改写**，不会把外部 JS 下载、托管到本仓库；脚本执行时仍依赖代理服务。',
        '- `.sgmodule` 为 Surge 模块格式；下载链接代理化不代表可直接在 Shadowrocket 导入使用。',
        '- Shadowrocket 导入模块后，如涉及 HTTPS 响应改写，请按模块说明开启 HTTPS 解密。',
        '- 使用第三方代理意味着模块和脚本下载会经过该服务；敏感或重要场景建议替换为可信的自建代理。',
        '',
        '## 本地运行',
        '',
        '要求 Python 3.10+，无第三方依赖：',
        '',
        '```bash',
        'python3 -m unittest discover -s tests -v',
        'python3 scripts/convert.py',
        'python3 scripts/convert.py --check',
        '```',
        '',
    ]
    return '\n'.join(lines)


def sync(check: bool = False) -> bool:
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    validate_config(config)
    # Download everything first: one broken source must not cause a partial update.
    generated = {}
    for module in config['modules']:
        print(f'同步 {module["filename"]} ← {module["source"]}', flush=True)
        original = fetch_text(module['source'])
        generated[module['filename']] = convert_module(original, config['proxy_prefix'])
    generated_readme = make_readme(config)
    stale = sorted(p for p in OUTPUT.iterdir() if p.is_file() and p.suffix in ('.module', '.sgmodule') and p.name not in generated) if OUTPUT.exists() else []
    changed = []
    for filename, content in generated.items():
        file_path = OUTPUT / filename
        if not file_path.is_file() or file_path.read_text(encoding='utf-8') != content:
            changed.append(str(file_path.relative_to(ROOT)))
    if not README.is_file() or README.read_text(encoding='utf-8') != generated_readme:
        changed.append('README.md')
    changed += [str(p.relative_to(ROOT)) for p in stale]
    if check:
        if changed:
            print('文件与上游不一致:', ', '.join(changed), file=sys.stderr)
            return False
        print('文件均为最新')
        return True
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, content in generated.items():
        (OUTPUT / filename).write_text(content, encoding='utf-8', newline='')
    for path in stale:
        path.unlink()
    README.write_text(generated_readme, encoding='utf-8', newline='')
    print('更新完成:', ', '.join(changed) if changed else '无变化')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='下载并代理化 Shadowrocket 模块')
    parser.add_argument('--check', action='store_true', help='仅检查生成文件是否与上游一致')
    args = parser.parse_args()
    try:
        sys.exit(0 if sync(check=args.check) else 1)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f'错误: {exc}', file=sys.stderr)
        sys.exit(1)
