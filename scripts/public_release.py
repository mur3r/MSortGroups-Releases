"""Runs in the public releases repository with its own limited GITHUB_TOKEN."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from release_github import api


def main():
    root = Path(__file__).resolve().parent.parent
    version = json.loads((root / 'incoming' / 'latest.json').read_text())['version']
    if not re.fullmatch(r'(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})', version):
        raise RuntimeError('Invalid incoming release version.')
    folder = root / 'incoming' / version
    raw = (folder / 'murer-update.json').read_bytes()
    signature = json.loads((folder / 'murer-update.sig').read_bytes())
    keys = json.loads((root / 'public-keys.json').read_text())
    Ed25519PublicKey.from_public_bytes(base64.b64decode(keys[signature['key_id']], validate=True)).verify(
        base64.b64decode(signature['signature'], validate=True), raw)
    manifest = json.loads(raw)
    if manifest['version'] != version or manifest['application'] != 'Murer Group Stats':
        raise RuntimeError('Manifest version or application mismatch.')
    if manifest['package']['name'] != f'MurerGroupStats-{version}.zip':
        raise RuntimeError('Unexpected archive name.')
    archive = folder / manifest['package']['name']
    if archive.stat().st_size != manifest['package']['size'] or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['package']['sha256']:
        raise RuntimeError('Incoming archive is incomplete or changed.')
    repository, token = os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN']
    releases = api(token, 'GET', f'/repos/{repository}/releases?per_page=100')
    release = next((r for r in releases if r['tag_name'] == 'v' + version), None)
    if release and not release['draft']:
        raise RuntimeError('Published versions are immutable. Increase VERSION in the source repository.')
    if not release:
        release = api(token, 'POST', f'/repos/{repository}/releases', json={
            'tag_name': 'v' + version, 'target_commitish':os.environ['GITHUB_SHA'],
            'name':'Murer Group Stats ' + version, 'body':(folder / 'RELEASE_NOTES.md').read_text(encoding='utf-8'),
            'draft':True, 'prerelease':False})
    names = {archive.name, 'murer-update.json', 'murer-update.sig'}
    for asset in release['assets']:
        if asset['name'] in names:
            api(token, 'DELETE', f"/repos/{repository}/releases/assets/{asset['id']}")
    for name in (archive.name, 'murer-update.json', 'murer-update.sig'):
        path = folder / name
        api(token, 'POST', release['upload_url'].split('{')[0] + '?name=' + quote(name),
            headers={'Content-Type':'application/octet-stream'}, content=path.read_bytes())
    published = api(token, 'PATCH', f"/repos/{repository}/releases/{release['id']}", json={'draft':False, 'make_latest':'true'})
    print('Published public signed release: ' + published['html_url'])


if __name__ == '__main__':
    main()
