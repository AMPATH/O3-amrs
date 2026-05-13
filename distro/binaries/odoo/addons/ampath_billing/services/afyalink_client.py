# -*- coding: utf-8 -*-
"""AfyaLink HTTP client: pre-auth (SHIF) and claim submit.

Endpoint paths are configurable (DHA UAT vs prod differ). Set:
  ampath.afyalink.claim_submit_url  – full URL POST JSON body (FHIR Bundle)
  ampath.afyalink.preauth_request_url – POST JSON
  ampath.afyalink.preauth_status_url – GET template with {request_id} placeholder

AMPATH ETL / HIE (Odoo-shaped JSON, same builder as pre-auth preview). Set:
  ampath.etl_claims.submit_url — full URL (e.g. …/etl-claims/api/Hie/submit-claim-odoo)
  ampath.etl_claims.api_key — value for header AMPATH-CLAIMS-KEY
  Or on the host / container: AMPATH_ETL_CLAIMS_SUBMIT_URL, AMPATH_ETL_CLAIMS_API_KEY
  (used when the system parameters above are empty).

Submit body is the flat ``BuildClaimBundleRequest`` JSON (``patientUuid``, ``visitUuid``, …)
like Postman. Set ampath.etl_claims.wrap_request_body=1 (or env AMPATH_ETL_CLAIMS_WRAP_REQUEST=1)
only if a backend still expects ``{"request": {...}}``.

When ETL URL is set (parameter or env), sale order bulk claim uses this path instead of
posting a FHIR Bundle to AfyaLink.
"""
import logging
import os
import urllib.parse

from odoo import _
from odoo.exceptions import UserError

from . import afyalink_auth

_logger = logging.getLogger(__name__)

_PARAM_CLAIM_URL = 'ampath.afyalink.claim_submit_url'
_PARAM_PREAUTH_REQ = 'ampath.afyalink.preauth_request_url'
_PARAM_PREAUTH_STATUS = 'ampath.afyalink.preauth_status_url'
_PARAM_ETL_SUBMIT_URL = 'ampath.etl_claims.submit_url'
_PARAM_ETL_API_KEY = 'ampath.etl_claims.api_key'
# Docker / k8s: set these on the odoo container when you prefer env over DB parameters
_ENV_ETL_SUBMIT_URL = 'AMPATH_ETL_CLAIMS_SUBMIT_URL'
_ENV_ETL_API_KEY = 'AMPATH_ETL_CLAIMS_API_KEY'
_PARAM_ETL_WRAP_REQUEST = 'ampath.etl_claims.wrap_request_body'
_ENV_ETL_WRAP_REQUEST = 'AMPATH_ETL_CLAIMS_WRAP_REQUEST'


def _ensure_etl_submit_body_reports_success(body):
    """Raise UserError when ETL returns HTTP 2xx but JSON has explicit ``success: false``."""
    if not isinstance(body, dict):
        return
    success = body.get('success')
    if success is None and 'Success' in body:
        success = body['Success']
    if success is None:
        return
    if success is True or success == 1:
        return
    if isinstance(success, str) and success.strip().lower() in ('true', '1', 'yes'):
        return
    if success is False or success == 0 or (
        isinstance(success, str) and success.strip().lower() in ('false', '0', 'no')
    ):
        msg = body.get('message') or body.get('Message') or body.get('error') or body.get('Error')
        if isinstance(msg, dict):
            msg = msg.get('message') or msg.get('Message') or str(msg)
        detail = (msg or '').strip() if isinstance(msg, str) else (str(msg).strip() if msg else '')
        if not detail:
            detail = _('The server reported failure without details.')
        raise UserError(_('Claim submission failed: %s') % detail)


def _param(env, key):
    return (env['ir.config_parameter'].sudo().get_param(key, '') or '').strip()


def _etl_submit_wrap_request_body(env):
    """When True, POST a wrapper with a ``request`` key; otherwise POST flat JSON (Postman shape)."""
    p = _param(env, _PARAM_ETL_WRAP_REQUEST).lower()
    if p in ('1', 'true', 'yes'):
        return True
    if p in ('0', 'false', 'no'):
        return False
    e = (os.environ.get(_ENV_ETL_WRAP_REQUEST) or '').strip().lower()
    if e in ('1', 'true', 'yes'):
        return True
    if e in ('0', 'false', 'no'):
        return False
    return False


def etl_submit_url_configured(env):
    """True if ETL URL is set via system parameter or environment."""
    return bool(_param(env, _PARAM_ETL_SUBMIT_URL) or (os.environ.get(_ENV_ETL_SUBMIT_URL) or '').strip())


def submit_claim(env, bundle_dict):
    url = _param(env, _PARAM_CLAIM_URL)
    if not url:
        raise UserError(_(
            'AfyaLink claim submission URL is not configured. '
            'Set system parameter "%s" to the full HTTPS endpoint.'
        ) % _PARAM_CLAIM_URL)
    force_refresh = False
    for _attempt in range(2):
        token = afyalink_auth.get_access_token(env, force_refresh=force_refresh)
        status, body = afyalink_auth.http_json(env, 'POST', url, body=bundle_dict, token=token)
        if status == 401 and not force_refresh:
            force_refresh = True
            continue
        if status and int(status) >= 400:
            _logger.error('AfyaLink claim submit failed %s: %s', status, body)
            raise UserError(_('Claim submission failed (%s): %s') % (status, body))
        return body
    return None


def claim_submit_indicates_success(body):
    """True only when the payer returns a JSON object with ``success`` exactly True."""
    return isinstance(body, dict) and body.get('success') is True


def submit_etl_hie_claim(env, payload_dict):
    """POST claim JSON to AMPATH ETL (AMPATH-CLAIMS-KEY), no OAuth.

    By default the body is **flat** (``patientUuid``, ``visitUuid``, ``services``, …) like Postman.
    Set ``ampath.etl_claims.wrap_request_body`` / ``AMPATH_ETL_CLAIMS_WRAP_REQUEST`` to wrap in
    ``{"request": ...}`` if the server requires it. ``serviceCode`` in each service must be a
    string, not JSON ``false``.
    """
    url = _param(env, _PARAM_ETL_SUBMIT_URL) or (os.environ.get(_ENV_ETL_SUBMIT_URL) or '').strip()
    if not url:
        raise UserError(_(
            'ETL claim URL is not configured. Set system parameter "%s" '
            'or environment variable "%s" to the full HTTPS endpoint (e.g. …/submit-claim-odoo).'
        ) % (_PARAM_ETL_SUBMIT_URL, _ENV_ETL_SUBMIT_URL))
    api_key = _param(env, _PARAM_ETL_API_KEY) or (os.environ.get(_ENV_ETL_API_KEY) or '').strip()
    if not api_key:
        raise UserError(_(
            'ETL claims API key is not configured. Set system parameter "%s" '
            'or environment variable "%s".'
        ) % (_PARAM_ETL_API_KEY, _ENV_ETL_API_KEY))
    body_out = {'request': payload_dict} if _etl_submit_wrap_request_body(env) else payload_dict
    status, body = afyalink_auth.http_json(
        env,
        'POST',
        url,
        body=body_out,
        token=None,
        extra_headers={'AMPATH-CLAIMS-KEY': api_key},
    )
    if status and int(status) >= 400:
        _logger.error('ETL claim submit failed %s: %s', status, body)
        raise UserError(_('Claim submission failed (%s): %s') % (status, body))
    _ensure_etl_submit_body_reports_success(body)
    return body


def etl_claim_external_id_from_response(body):
    """Best-effort id from heterogeneous ETL JSON (for sale.order.line.fhir_claim_id)."""
    if not isinstance(body, dict):
        return None
    for k in (
        'claimId', 'claim_id', 'ClaimId',
        'mediatorId', 'Mediator_Id', 'mediator_Id', 'mediator_id',
        'id',
    ):
        if body.get(k):
            return str(body[k])
    msg = body.get('message')
    if isinstance(msg, dict):
        for k in ('Mediator_Id', 'mediator_Id', 'mediator_id'):
            if msg.get(k):
                return str(msg[k])
    return None


def request_preauth(env, order):
    from odoo.addons.ampath_billing.services.claim_bundle_builder import build_preauth_request_payload

    url = _param(env, _PARAM_PREAUTH_REQ)
    if not url:
        raise UserError(_(
            'Pre-authorization request URL is not configured. '
            'Set system parameter "%s".'
        ) % _PARAM_PREAUTH_REQ)
    payload = build_preauth_request_payload(order)
    token = afyalink_auth.get_access_token(env)
    status, body = afyalink_auth.http_json(env, 'POST', url, body=payload, token=token)
    if status and int(status) >= 400:
        _logger.error('AfyaLink preauth request failed %s: %s', status, body)
        raise UserError(_('Pre-authorization request failed (%s): %s') % (status, body))
    rid = None
    if isinstance(body, dict):
        for k in ('requestId', 'request_id', 'id', 'preauthRequestId'):
            if body.get(k):
                rid = str(body[k])
                break
    return rid, body


def check_preauth_status(env, request_id):
    template = _param(env, _PARAM_PREAUTH_STATUS)
    if not template:
        raise UserError(_(
            'Pre-authorization status URL is not configured. '
            'Set system parameter "%s" (use {request_id} in the path or query).'
        ) % _PARAM_PREAUTH_STATUS)
    url = template.format(request_id=urllib.parse.quote(request_id, safe=''))
    token = afyalink_auth.get_access_token(env)
    status, body = afyalink_auth.http_json(env, 'GET', url, token=token)
    if status and int(status) >= 400:
        _logger.error('AfyaLink preauth status failed %s: %s', status, body)
        raise UserError(_('Pre-authorization status check failed (%s): %s') % (status, body))
    return body


def claim_id_from_submit_response(body):
    """Best-effort FHIR Claim id or mediator bundle id from an AfyaLink / FHIR JSON response."""
    if not isinstance(body, dict):
        return None
    msg = body.get('message')
    if isinstance(msg, dict):
        for k in ('Mediator_Id', 'mediator_Id', 'mediator_id'):
            if msg.get(k):
                return str(msg[k])
        cids = msg.get('Claim_Ids') or msg.get('claim_Ids') or msg.get('claim_ids')
        if isinstance(cids, list) and cids:
            return str(cids[0])
    nested = body.get('data')
    if isinstance(nested, dict):
        for k in ('claimId', 'claim_id', 'fhirClaimId', 'mediator_id', 'Mediator_Id'):
            if nested.get(k):
                return str(nested[k])
        cids = nested.get('Claim_Ids') or nested.get('claim_ids')
        if isinstance(cids, list) and cids:
            return str(cids[0])
    if body.get('resourceType') == 'Claim' and body.get('id'):
        return str(body['id'])
    for ent in body.get('entry') or []:
        res = ent.get('resource') if isinstance(ent, dict) else None
        if isinstance(res, dict) and res.get('resourceType') == 'Claim' and res.get('id'):
            return str(res['id'])
    for k in ('id', 'claimId', 'claim_id'):
        if body.get(k):
            return str(body[k])
    return None


def parse_preauth_status_body(body):
    """Return (status_str, code_str, pre_auth_fhir_claim_id) from heterogeneous JSON."""
    if not isinstance(body, dict):
        return None, None, None
    st = (
        body.get('status')
        or body.get('preauthStatus')
        or body.get('state')
    )
    code = (
        body.get('code')
        or body.get('preauthCode')
        or body.get('authorizationCode')
    )
    fhir_claim = (
        body.get('preAuthClaimId')
        or body.get('preauthClaimId')
        or body.get('fhirClaimId')
        or body.get('claimId')
    )
    if isinstance(fhir_claim, dict) and fhir_claim.get('id'):
        fhir_claim = fhir_claim.get('id')
    if st is not None:
        st = str(st).lower()
    if code is not None:
        code = str(code)
    if fhir_claim is not None:
        fhir_claim = str(fhir_claim)
    return st, code, fhir_claim
