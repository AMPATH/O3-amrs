# -*- coding: utf-8 -*-
"""AfyaLink HTTP client: pre-auth (SHIF) and claim submit.

Endpoint paths are configurable (DHA UAT vs prod differ). Set:
  ampath.afyalink.claim_submit_url  – full URL POST JSON body (FHIR Bundle)
  ampath.afyalink.preauth_request_url – POST JSON
  ampath.afyalink.preauth_status_url – GET template with {request_id} placeholder
"""
import logging
import urllib.parse

from odoo import _
from odoo.exceptions import UserError

from . import afyalink_auth

_logger = logging.getLogger(__name__)

_PARAM_CLAIM_URL = 'ampath.afyalink.claim_submit_url'
_PARAM_PREAUTH_REQ = 'ampath.afyalink.preauth_request_url'
_PARAM_PREAUTH_STATUS = 'ampath.afyalink.preauth_status_url'


def _param(env, key):
    return (env['ir.config_parameter'].sudo().get_param(key, '') or '').strip()


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


def request_preauth(env, order):
    url = _param(env, _PARAM_PREAUTH_REQ)
    if not url:
        raise UserError(_(
            'Pre-authorization request URL is not configured. '
            'Set system parameter "%s".'
        ) % _PARAM_PREAUTH_REQ)
    patient = (
        getattr(order, 'x_patient_uuid', None)
        or order.x_external_identifier
    )
    payload = {
        'patientUuid': patient,
        'orderId': order.id,
        'orderName': order.name,
        'insuranceScheme': getattr(order, 'x_insurance_scheme', None),
        'companyId': order.company_id.id if order.company_id else None,
    }
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
    """Best-effort FHIR Claim id from an AfyaLink / FHIR JSON response."""
    if not isinstance(body, dict):
        return None
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
    """Return (status_str, code_str) from heterogeneous JSON."""
    if not isinstance(body, dict):
        return None, None
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
    if st is not None:
        st = str(st).lower()
    if code is not None:
        code = str(code)
    return st, code
