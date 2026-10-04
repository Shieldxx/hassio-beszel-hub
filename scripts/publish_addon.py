"""Publish one Home Assistant add-on to the public Shieldxx/ha-addons repository.

Every add-on is developed in its own repository and only *released* into
ha-addons, one folder per add-on. Home Assistant installs from there:

    python scripts/publish_addon.py --dry-run   # show what would go out
    python scripts/publish_addon.py             # publish it

This file is identical in every development repository - compare the sha256
before editing one copy, and carry the change to the others. What differs is
scripts/publish.json next to it: which folder of this repository is the
add-on ("source_dir", "" for the repository root), which folder of ha-addons
it replaces ("addon_dir"), and which files and folders in it are published.

What goes out is an allowlist, not "everything minus some exclusions": a file
nobody named is never published, so personal data, tooling and history cannot
leak by accident. List what the image is built from, plus what Home Assistant
reads from the add-on folder (icon.png, CHANGELOG.md) and what the licenses
require to travel with the code (LICENSE, notices). The files are taken from
the last commit with `git archive`, never from the working tree, and the run
refuses to start with uncommitted changes, so what is published is always
exactly a commit.

Before pushing, every published file is scanned for credentials and personal
email addresses, and the commit is made under the GitHub noreply identity
whatever the local git config says.

The root of ha-addons - README.md, repository.json, .gitattributes - belongs
to no single add-on. Every run regenerates it from the add-on folders it finds
there, so each copy of this script writes the same root and a new add-on needs
no hand edit. Licenses are per add-on, in each folder's LICENSE.
"""

import argparse
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parent
SOURCE_REPO = SCRIPTS.parent
PUBLIC_URL = 'https://github.com/Shieldxx/ha-addons'

SETTINGS = json.loads((SCRIPTS / 'publish.json').read_text(encoding='utf-8'))
SOURCE_NAME = SETTINGS['source_repo']        # named in the release commit message
SOURCE_DIR = SETTINGS.get('source_dir', '')  # the add-on's folder in this repository
ADDON_DIR = SETTINGS['addon_dir']            # its folder in ha-addons
ALLOW_FILES = SETTINGS['files']
ALLOW_DIRS = SETTINGS.get('dirs', [])

CONFIG_NAMES = ('config.json', 'config.yaml', 'config.yml')

# Commits to the public repository never carry a personal address.
IDENTITY_NAME = 'Shieldxx'
IDENTITY_EMAIL = '37293647+Shieldxx@users.noreply.github.com'

FORBIDDEN = {
    'credential': re.compile(
        r'\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16}'
        r'|AIza[0-9A-Za-z\-_]{35}|xox[baprs]-[0-9A-Za-z-]{10,}|sk-(?:ant-)?[A-Za-z0-9\-_]{20,}'
        r'|(?:sk|rk)_live_[0-9a-zA-Z]{16,})'),
    'private key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'credentials in url': re.compile(r'[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@\'"]+:[^/\s:@\'"]+@'),
    'secret assignment': re.compile(
        r'''(?i)\b[a-z0-9_]*(?:secret|token|passwd|password|api[_-]?key|private[_-]?key)[a-z0-9_]*\b'''
        r'''\s*[:=]\s*['"][^'"\s]{8,}['"]'''),
    'hardcoded secret default': re.compile(
        r'''(?i)environ\.get\(\s*['"][a-z0-9_]*(?:secret|token|passw)[a-z0-9_]*['"]\s*,\s*['"][^'"]{4,}['"]'''),
}
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
ALLOWED_EMAILS = {IDENTITY_EMAIL, 'noreply@anthropic.com'}

REPOSITORY_JSON = {
    'name': 'Shieldxx Home Assistant add-ons',
    'url': PUBLIC_URL,
    'maintainer': 'Shieldxx',
}

ROOT_README = """\
# Shieldxx Home Assistant add-ons

[![Add this repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FShieldxx%2Fha-addons)

| Add-on | What it does | License |
|---|---|---|
{rows}

## Installing

1. **Settings -> Add-ons -> Add-on Store -> (top-right menu) -> Repositories**
2. Add `https://github.com/Shieldxx/ha-addons`
3. Open the add-on, install it, start it, and turn on **Show in sidebar**

Or use the button above.

## About this repository

Releases only. Each add-on is developed in its own repository and published
into its folder here by a script, so nothing here is edited by hand. Licenses
are per add-on: see the LICENSE in each folder.
"""

# Same rule as the development repositories: files run inside the Linux
# container must stay LF however the repository is cloned.
ROOT_GITATTRIBUTES = """\
*.sh        text eol=lf
Dockerfile  text eol=lf
"""


def git(*args, cwd=SOURCE_REPO, binary=False, check=True):
    # autocrlf off: bytes pass through untouched, so the public repository
    # stores exactly what the development one does.
    out = subprocess.run(['git', '-c', 'core.autocrlf=false', *args],
                         cwd=cwd, capture_output=True)
    if check and out.returncode != 0:
        sys.exit('git %s failed:\n%s' % (' '.join(args), out.stderr.decode(errors='replace')))
    return out.stdout if binary else out.stdout.decode('utf-8', errors='replace')


def scan(files):
    """Return (path, reason, excerpt) for every forbidden match."""
    hits = []
    for path, data in files.items():
        if b'\x00' in data[:8000]:
            continue  # binary
        text = data.decode('utf-8', errors='replace')
        for reason, pat in FORBIDDEN.items():
            for m in pat.finditer(text):
                hits.append((path, reason, m.group(0)[:70]))
        for m in EMAIL.finditer(text):
            if m.group(0) not in ALLOWED_EMAILS:
                hits.append((path, 'email address', m.group(0)))
    return hits


def meta_from(text, filename):
    """name, version and description from an add-on manifest.

    YAML is read for these three top-level scalars only, so no YAML library is
    needed; a folded multi-line description would come back as its marker.
    """
    if filename.endswith('.json'):
        data = json.loads(text)
        return {k: str(data.get(k, '')) for k in ('name', 'version', 'description')}
    meta = {}
    for key in ('name', 'version', 'description'):
        m = re.search(r'^%s:[ \t]*(.*?)[ \t]*$' % key, text, re.M)
        meta[key] = m.group(1).strip('\'"') if m else ''
    return meta


def folder_meta(folder):
    """The manifest of the add-on in `folder`, or None if it holds no add-on."""
    for name in CONFIG_NAMES:
        path = folder / name
        if path.is_file():
            return meta_from(path.read_text(encoding='utf-8'), name)
    return None


def license_name(text):
    if 'PolyForm Noncommercial License 1.0.0' in text:
        return 'PolyForm Noncommercial 1.0.0'
    if text.lstrip().startswith('MIT License'):
        return 'MIT'
    return 'see LICENSE'


def root_readme(pub):
    rows = []
    for folder in sorted(p for p in pub.iterdir() if p.is_dir() and not p.name.startswith('.')):
        meta = folder_meta(folder)
        if meta is None:
            continue
        lic = folder / 'LICENSE'
        cell = ('[%s](%s/LICENSE)' % (license_name(lic.read_text(encoding='utf-8')), folder.name)
                if lic.is_file() else '-')
        rows.append('| [%s](%s) | %s | %s |' % (meta['name'], folder.name, meta['description'], cell))
    return ROOT_README.format(rows='\n'.join(rows))


def write_root(pub):
    """Regenerate the files at the root of ha-addons from its add-on folders."""
    (pub / 'repository.json').write_text(json.dumps(REPOSITORY_JSON, indent=2) + '\n',
                                         encoding='utf-8', newline='\n')
    (pub / 'README.md').write_text(root_readme(pub), encoding='utf-8', newline='\n')
    (pub / '.gitattributes').write_text(ROOT_GITATTRIBUTES, encoding='utf-8', newline='\n')
    # Licenses live in the add-on folders. A root LICENSE would claim one
    # add-on's terms for all of them - 0.2.x of BARF Companion put PolyForm here.
    stale = pub / 'LICENSE'
    if stale.exists():
        stale.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dry-run', action='store_true', help='show what would be published, push nothing')
    args = parser.parse_args()

    if git('status', '--porcelain').strip():
        sys.exit('Uncommitted changes. Commit first - only a commit is ever published.')

    head = git('rev-parse', '--short', 'HEAD').strip()

    # 1. The allowlisted files, as committed, relative to the add-on's folder.
    tree = 'HEAD:%s' % SOURCE_DIR if SOURCE_DIR else 'HEAD'
    archive = git('archive', '--format=tar', tree, '--', *ALLOW_FILES, *ALLOW_DIRS, binary=True)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                files[member.name] = tar.extractfile(member).read()

    manifest = next((n for n in CONFIG_NAMES if n in files), None)
    if manifest is None:
        sys.exit('No config.json or config.yaml among the published files.')
    version = meta_from(files[manifest].decode('utf-8'), manifest)['version']

    # Home Assistant shows the changelog next to the update; an update that
    # explains nothing is not worth publishing.
    if ('## %s ' % version).encode() not in files.get('CHANGELOG.md', b''):
        sys.exit('CHANGELOG.md has no "## %s" section. Describe this release first.' % version)

    # 2. Nothing goes out that the scan objects to.
    hits = scan(files)
    if hits:
        for path, reason, excerpt in hits:
            print('  BLOCKED %-26s %-24s %s' % (path, reason, excerpt))
        sys.exit('Refusing to publish: %d finding(s) above.' % len(hits))

    with tempfile.TemporaryDirectory() as tmp:
        pub = pathlib.Path(tmp) / 'ha-addons'
        git('clone', '--quiet', PUBLIC_URL, str(pub), cwd=tmp)

        # 3. Home Assistant only offers an update when the version changes.
        published = folder_meta(pub / ADDON_DIR) if (pub / ADDON_DIR).is_dir() else None
        old = published['version'] if published else None
        if old == version:
            sys.exit('Version %s is already published. Bump "version" in %s, '
                     'or Home Assistant will not offer the update.' % (version, manifest))

        # 4. Replace this add-on's folder wholesale, so a file deleted here is
        #    deleted there too. Other add-ons' folders are never touched.
        shutil.rmtree(pub / ADDON_DIR, ignore_errors=True)
        for name, data in files.items():
            target = pub / ADDON_DIR / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        write_root(pub)

        git('add', '--all', cwd=pub)
        changes = git('status', '--short', cwd=pub)
        print('Publishing %s %s (from %s %s)%s'
              % (ADDON_DIR, version, SOURCE_NAME, head, '' if old is None else ', replacing %s' % old))
        print('  %d files in %s/' % (len(files), ADDON_DIR))
        print(changes.rstrip() or '  (no file changes)')

        if args.dry_run:
            print('\nDry run: nothing pushed.')
            return

        identity = ['-c', 'user.name=%s' % IDENTITY_NAME, '-c', 'user.email=%s' % IDENTITY_EMAIL]
        git(*identity, 'commit', '--quiet', '-m',
            '%s %s\n\nPublished from %s %s.' % (ADDON_DIR, version, SOURCE_NAME, head), cwd=pub)
        git('push', '--quiet', 'origin', 'HEAD', cwd=pub)
        print('\nPushed to %s' % PUBLIC_URL)


if __name__ == '__main__':
    main()
