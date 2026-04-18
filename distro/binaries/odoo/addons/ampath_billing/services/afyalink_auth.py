# -*- coding: utf-8 -*-
"""AfyaLink / DHA token acquisition (reference: ampath-sha-claims HieService.GetTokenAsync).

GET {base}/v1/hie-auth?key={consumer_key} with Basic Auth (username:password).
Configure via Settings > Technical > System Parameters (keys prefixed ampath.afyalink.).
"""
import base64
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)

_PARAM_BASE = 'ampath.afyalink.base_url'
_PARAM_KEY = 'ampath.afyalink.consumer_key'
_PARAM_USER = 'ampath.afyalink.username'
_PARAM_PASS = 'ampath.afyalink.password'
_PARAM_AUTH_PATH = 'ampath.afyalink.auth_path'
_DEFAULT_AUTH_PATH = '/v1/hie-auth'

# In-process cache: (db, base_url, user) -> (token, expires_epoch)
_token_cache = {}
_TOKEN_TTL_SEC = 60


def _get_param(env, key, default=''):
    return (env['ir.config_parameter'].sudo().get_param(key, default) or '').strip()


def _settings(env):
    return {
        'base_url': _get_param(env, _PARAM_BASE).rstrip('/'),
        'consumer_key': _get_param(env, _PARAM_KEY),
        'username': _get_param(env, _PARAM_USER),
        'password': _get_param(env, _PARAM_PASS),
        'auth_path': _get_param(env, _PARAM_AUTH_PATH) or _DEFAULT_AUTH_PATH,
    }


def settings_configured(env):
    s = _settings(env)
    return all([s['base_url'], s['consumer_key'], s['username'], s['password']])


def get_access_token(env, force_refresh=False):
    """Return Bearer token string for AfyaLink API calls."""
    s = _settings(env)
    if not all([s['base_url'], s['consumer_key'], s['username'], s['password']]):
        raise ValueError(
            'AfyaLink is not configured. Set system parameters: '
            f'{_PARAM_BASE}, {_PARAM_KEY}, {_PARAM_USER}, {_PARAM_PASS}'
        )

    cache_key = (env.cr.dbname, s['base_url'], s['username'])
    now = time.time()
    if not force_refresh and cache_key in _token_cache:
        token, exp = _token_cache[cache_key]
        if token and now < exp - 5:
            return token

    path = s['auth_path']
    if not path.startswith('/'):
        path = '/' + path
    qs = urllib.parse.urlencode({'key': s['consumer_key']})
    url = f"{s['base_url']}{path}?{qs}"
    raw = f"{s['username']}:{s['password']}"
    b64 = base64.b64encode(raw.encode('utf-8')).decode('ascii')
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Basic {b64}',
            'Accept': 'application/json, text/plain, */*',
        },
        method='GET',
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            body = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        _logger.error('AfyaLink auth HTTP %s: %s', e.code, err_body)
        raise ValueError(f'AfyaLink authentication failed (HTTP {e.code}): {err_body or e.reason}') from e
    except urllib.error.URLError as e:
        _logger.error('AfyaLink auth URL error: %s', e)
        raise ValueError(f'AfyaLink authentication failed: {e.reason}') from e

    token = _parse_token_response(body)
    _token_cache[cache_key] = (token, now + _TOKEN_TTL_SEC)
    return token


def clear_token_cache_for_tests():
    _token_cache.clear()


def _parse_token_response(body):
    body = body.strip()
    if not body:
        raise ValueError('AfyaLink auth returned an empty body')
    if body.startswith('{') or body.startswith('['):
        data = json.loads(body)
        if isinstance(data, dict):
            for k in ('access_token', 'token', 'accessToken', 'id_token'):
                if data.get(k):
                    return str(data[k])
        raise ValueError(f'Could not parse token from JSON response: {body[:200]}')
    return body


def http_json(env, method, url, *, body=None, token=None, timeout=60):
    """Perform HTTPS request; returns (status_code, parsed_json_or_text)."""
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    data = None
    if body is not None and method.upper() != 'GET':
        data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            status = resp.getcode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', errors='replace') if e.fp else ''
        status = e.code
        try:
            return status, json.loads(raw) if raw.strip().startswith('{') else raw
        except json.JSONDecodeError:
            return status, raw
    try:
        return status, json.loads(raw) if raw.strip().startswith('{') else raw
    except json.JSONDecodeError:
        return status, raw
