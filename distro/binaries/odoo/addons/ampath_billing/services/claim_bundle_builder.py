# -*- coding: utf-8 -*-
"""Build a minimal FHIR R4 Claim bundle from Odoo sale order data.

Aligned conceptually with ampath-sha-claims ShaClaimBundleBuilder (Claim +
items + optional related pre-auth). Exact coding/display values should be
refined against DHA SHA Claim Bundle documentation when integrating live.
"""
import uuid
from datetime import datetime, timezone


def _patient_uuid(order):
    return (
        getattr(order, 'x_patient_uuid', None)
        or order.x_external_identifier
        or None
    )


def build_claim_bundle(order, lines, pre_auth_claim_id=None):
    """Return a dict suitable for JSON POST (Bundle type collection).

    :param order: sale.order record
    :param lines: sale.order.line recordset (product lines only)
    :param pre_auth_claim_id: optional FHIR Claim id for SHIF relatedClaim
    """
    patient_uuid = _patient_uuid(order)
    if not patient_uuid:
        raise ValueError('Sale order has no patient UUID (x_patient_uuid or x_external_identifier).')

    def _iso(dt):
        if not dt:
            return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        if hasattr(dt, 'isoformat'):
            s = dt.isoformat()
            return s if s.endswith('Z') or '+' in s else s
        return str(dt)

    claim_id = str(uuid.uuid4())
    items = []
    for idx, line in enumerate(lines, start=1):
        product = line.product_id
        code = product.default_code if product else None
        display = (product.name if product else line.name) or 'Item'
        items.append({
            'sequence': idx,
            'productOrService': {
                'coding': [{
                    'system': 'http://snomed.info/sct',
                    'code': code or 'unknown',
                    'display': display,
                }],
            },
            'quantity': {'value': line.product_uom_qty},
            'unitPrice': {'value': line.price_unit, 'currency': order.currency_id.name},
            'net': {'value': line.price_subtotal, 'currency': order.currency_id.name},
        })

    claim = {
        'resourceType': 'Claim',
        'id': claim_id,
        'status': 'active',
        'type': {
            'coding': [{
                'system': 'http://terminology.hl7.org/CodeSystem/claim-type',
                'code': 'professional',
            }],
        },
        'use': 'claim',
        'patient': {'reference': f'Patient/{patient_uuid}'},
        'created': _iso(order.date_order),
        'provider': {'display': order.company_id.name if order.company_id else ''},
        'priority': {'coding': [{'code': 'normal'}]},
        'insurance': [{
            'sequence': 1,
            'focal': True,
            'coverage': {'display': getattr(order, 'x_insurance_scheme', None) or ''},
        }],
        'item': items,
    }

    payment_method = (getattr(order, 'x_payment_method', None) or '').strip().upper()
    if payment_method:
        claim.setdefault('extension', []).append({
            'url': 'http://ampath.org/fhir/StructureDefinition/payment-method',
            'valueString': payment_method,
        })

    if pre_auth_claim_id:
        claim['related'] = [{
            'claim': {'reference': f'Claim/{pre_auth_claim_id}'},
            'relationship': {
                'coding': [{'code': 'priorauth', 'display': 'Prior Authorization'}],
            },
        }]

    bundle = {
        'resourceType': 'Bundle',
        'type': 'collection',
        'timestamp': _iso(order.date_order),
        'identifier': {
            'system': 'urn:ietf:rfc:3986',
            'value': f'urn:uuid:{claim_id}',
        },
        'entry': [{'fullUrl': f'urn:uuid:{claim_id}', 'resource': claim}],
    }
    return bundle, claim_id
