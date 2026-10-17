"""Publisher authentication stays on the owner computer / GitHub Actions."""
import os
import subprocess
import httpx


def publisher_token(owner):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        return token
    result = subprocess.run(['git', 'credential', 'fill'],
                            input=f'protocol=https\nhost=github.com\nusername={owner}\n\n',
                            text=True, capture_output=True, timeout=30,
                            env=dict(os.environ, GCM_INTERACTIVE='never', GIT_TERMINAL_PROMPT='0'),
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password'):
        raise RuntimeError('GitHub authentication is unavailable. Sign in to Git with Git Credential Manager.')
    return values['password']


def api(token, method, path, **kwargs):
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'User-Agent': 'MurerGroupStats-Publisher', **kwargs.pop('headers', {})}
    url = path if path.startswith('https://uploads.github.com/') else 'https://api.github.com' + path
    response = httpx.request(method, url, headers=headers, timeout=120, **kwargs)
    if response.status_code >= 400:
        # Never print response bodies, request headers, or token values.
        raise RuntimeError(f'GitHub returned HTTP {response.status_code} for {method} {path.split("?")[0]}.')
    return response.json() if response.content else None
