# -*- coding: utf-8 -*-
"""FHIR R4 claim bundle aligned with ampath-sha-claims ShaClaimBundleBuilder.

Billing lines and amounts come from Odoo ``sale.order`` / ``sale.order.line``.
Reference: ``HIE Integration/Services/ShaClaimBundleBuilder.cs`` (ignore DB bill fetch).

System parameters (optional overrides; sensible defaults match the .NET sample):
  ampath.sha.fhir.base_url — base for literal references (default QA MIS host)
  ampath.sha.fhir.bundle_profile, organization_profile, patient_profile
  ampath.sha.fhir.intervention_code_system, icd11_system
  ampath.sha.fhir.facility_identifier_type_system, facility_level_extension,
  scheme_category_code_ext, scheme_category_name_ext, item_coverage_extension
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

_logger = logging.getLogger(__name__)

_DEFAULT_FHIR_BASE = 'https://qa-mis.apeiro-digital.com/fhir'
_DEFAULT_BUNDLE_PROFILE = (
    'https://qa-mis.apeiro-digital.com/fhir/StructureDefinition/bundle|1.0.0'
)
_DEFAULT_ORG_PROFILE = (
    'https://mis.apeiro-digital.com/fhir/StructureDefinition/provider-organization%7C1.0.0'
)
_DEFAULT_PATIENT_PROFILE = (
    'https://mis.apeiro-digital.com/fhir/StructureDefinition/patient%7C1.0.0'
)
_DEFAULT_INTERVENTION_SYSTEM = (
    'https://qa-mis.apeiro-digital.com/fhir/CodeSystem/intervention-codes'
)
_DEFAULT_ICD11 = 'https://qa-mis.apeiro-digital.com/fhir/terminology/CodeSystem/icd-11'
_DEFAULT_FACILITY_ID_TYPE = (
    'https://qa-mis.apeiro-digital.com/fhir/terminology/CodeSystem/facility-identifier-types'
)
_DEFAULT_FACILITY_LEVEL_EXT = (
    'https://qa-mis.apeiro-digital.com/fhir/StructureDefinition/facility-level'
)
_DEFAULT_SCHEME_CAT_CODE_EXT = (
    'https://qa-mis.apeiro-digital.com/fhir/StructureDefinition/schemeCategoryCode'
)
_DEFAULT_SCHEME_CAT_NAME_EXT = (
    'https://qa-mis.apeiro-digital.com/fhir/StructureDefinition/schemeCategoryName'
)
_DEFAULT_ITEM_COV_EXT = (
    'https://qa-mis.apeiro-digital.com/fhir/sha-coverage/StructureDefinition/Coverage'
)
_DEFAULT_ITEM_CATEGORY_SYSTEM = (
    'https://qa-mis.apeiro-digital.com/fhir/CodeSystem/category-codes'
)
_DEFAULT_ORG_TYPE_SYSTEM = 'https://ts.kenya-hie.health/fhir/terminology/CodeSystem/organization-type'
_DEFAULT_SHANUMBER_SYSTEM_SUFFIX = '/identifier/shanumber'
_DEFAULT_CLAIM_IDENTIFIER_SUFFIX = '/claim'


def _param(env, key, default=''):
    return (env['ir.config_parameter'].sudo().get_param(key, default) or '').strip()


def _fhir_base(env):
    return _param(env, 'ampath.sha.fhir.base_url', _DEFAULT_FHIR_BASE).rstrip('/')


def diagnoses_list(order):
    """Parse ``x_claim_diagnoses_json`` into a list of ``{'code': ..., 'display': ...}``."""
    raw = (order.x_claim_diagnoses_json or '').strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        _logger.warning('Invalid x_claim_diagnoses_json on order %s: %s', order.id, e)
        return []
    if not isinstance(data, list):
        return []
    out = []
    for row in data:
        if not isinstance(row, dict):
            continue
        code = (row.get('code') or '').strip()
        if not code:
            continue
        out.append({
            'code': code,
            'display': (row.get('display') or row.get('name') or '').strip(),
        })
    return out


def sha_patient_identifier(order):
    """HIE patient id for FHIR Patient.id (SHA client registry when set)."""
    reg = (order.x_sha_client_registry_id or '').strip()
    if reg:
        return reg
    return (
        getattr(order, 'x_patient_uuid', None)
        or (order.x_external_identifier or '')
    ).strip() or None


def coverage_id_for_order(order):
    cid = (order.x_coverage_id or '').strip()
    if cid:
        return cid
    pid = sha_patient_identifier(order)
    if not pid:
        return None
    return f'{pid}-sha-coverage'


def validate_claim_prerequisites(order, lines):
    """Raise ValueError with a clear message if the quotation cannot build a SHA bundle."""
    msgs = []
    partner = order.partner_id
    pid = sha_patient_identifier(order)
    if not pid:
        msgs.append('Patient identifier for claims (x_sha_client_registry_id or x_patient_uuid) is missing.')
    if not (order.x_sha_facility_id or '').strip():
        msgs.append('SHA facility id (x_sha_facility_id) is missing.')
    if not (order.x_sha_facility_name or '').strip():
        msgs.append('SHA facility name (x_sha_facility_name) is missing.')
    if not (order.x_sha_facility_level or '').strip():
        msgs.append('SHA facility level (x_sha_facility_level) is missing.')
    if not diagnoses_list(order):
        msgs.append('At least one ICD-11 diagnosis is required (x_claim_diagnoses_json).')
    cov = coverage_id_for_order(order)
    if not cov:
        msgs.append('Coverage id could not be resolved (set x_coverage_id or patient id).')
    dob = getattr(order, 'x_customer_dob', None) or (
        getattr(partner, 'x_customer_dob', None) if partner else None
    )
    if not dob:
        msgs.append('Patient date of birth is required (order or partner x_customer_dob).')
    for line in lines:
        if line.display_type or line.is_downpayment:
            continue
        code = (line.x_intervention_code or (line.product_id.default_code if line.product_id else '') or '').strip()
        if not code:
            msgs.append(
                f'Line "{line.name[:60]}..." needs an intervention code '
                '(product default code or x_intervention_code).'
            )
    if msgs:
        raise ValueError('Cannot build claim bundle:\n• ' + '\n• '.join(msgs))


def build_preauth_request_payload(order, lines=None):
    """JSON body for SHIF pre-authorization: mirrors BuildClaimBundleRequest (no OpenMRS bill fetch)."""
    lines = lines or order.order_line.filtered(lambda l: not l.display_type and not l.is_downpayment)
    services = _services_from_lines(order, lines)
    diagnoses = diagnoses_list(order)
    partner = order.partner_id
    gender = (order.x_patient_gender or (getattr(partner, 'x_gender', None) if partner else None) or 'Unknown')
    birth = None
    if getattr(order, 'x_customer_dob', None):
        birth = str(order.x_customer_dob)
    elif partner and getattr(partner, 'x_customer_dob', None):
        birth = str(partner.x_customer_dob)
    return {
        'visitUuid': (order.client_order_ref or '').strip() or None,
        'openmrsEncounterUuid': (order.x_openmrs_encounter_uuid or '').strip() or None,
        'patientUuid': (getattr(order, 'x_patient_uuid', None) or order.x_external_identifier),
        'shaPatientId': sha_patient_identifier(order),
        'orderId': order.id,
        'orderName': order.name,
        'insuranceScheme': order.x_insurance_scheme,
        'paymentMethod': order.x_payment_method,
        'facilityId': order.x_sha_facility_id,
        'facilityName': order.x_sha_facility_name,
        'facilityLevel': order.x_sha_facility_level,
        'coverageId': coverage_id_for_order(order),
        'schemeCategoryCode': order.x_scheme_category_code or 'CAT-SHA-001',
        'schemeCategoryName': order.x_scheme_category_name or 'SOCIAL HEALTH AUTHORITY',
        'claimType': order.x_claim_type or 'institutional',
        'claimSubType': order.x_claim_sub_type or 'op',
        'priorityCode': order.x_priority_code or 'normal',
        'practitionerId': (order.x_claim_practitioner_id or '').strip() or None,
        'patientFullName': partner.name if partner else order.name,
        'gender': gender,
        'birthDate': birth,
        'diagnoses': diagnoses,
        'services': services,
        'preAuthFhirClaimId': (order.x_preauth_fhir_claim_id or '').strip() or None,
    }


def _services_from_lines(order, lines):
    services = []
    for line in lines:
        if line.display_type or line.is_downpayment:
            continue
        product = line.product_id
        code = (line.x_intervention_code or (product.default_code if product else '') or '').strip()
        display = (product.name if product else line.name) or code
        qty = float(line.product_uom_qty or 0)
        unit = float(line.price_unit or 0)
        total = float(line.price_subtotal or 0) or unit * qty
        start = line.x_service_date_start or order.date_order
        end = line.x_service_date_end or order.date_order
        category = (
            (line.x_service_category or '').strip()
            or (product.categ_id.name if product and product.categ_id else '')
            or 'procedure'
        )
        preauth_line_id = (
            (line.x_preauth_fhir_claim_id or '').strip()
            or (order.x_preauth_fhir_claim_id or '').strip()
            or None
        )
        services.append({
            'serviceCode': code,
            'serviceDisplay': display,
            'category': category,
            'unitPrice': unit,
            'quantity': qty,
            'totalAmount': total,
            'serviceStart': _iso_z(start),
            'serviceEnd': _iso_z(end),
            'preAuthFhirClaimId': preauth_line_id,
        })
    return services


def _iso_z(dt):
    if not dt:
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    if hasattr(dt, 'astimezone'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    return str(dt)


def _split_human_name(full_name):
    parts = (full_name or '').strip().split()
    if not parts:
        return 'Unknown', []
    if len(parts) == 1:
        return parts[0], []
    return parts[-1], parts[:-1]


def build_claim_bundle(order, lines, pre_auth_claim_id=None):
    """Return ``(bundle_dict, claim_uuid)`` for POST to AfyaLink bundle endpoint (type *message*)."""
    validate_claim_prerequisites(order, lines)

    env = order.env
    base = _fhir_base(env)
    bundle_profile = _param(env, 'ampath.sha.fhir.bundle_profile', _DEFAULT_BUNDLE_PROFILE)
    org_profile = _param(env, 'ampath.sha.fhir.organization_profile', _DEFAULT_ORG_PROFILE)
    patient_profile = _param(env, 'ampath.sha.fhir.patient_profile', _DEFAULT_PATIENT_PROFILE)
    intervention_system = _param(env, 'ampath.sha.fhir.intervention_code_system', _DEFAULT_INTERVENTION_SYSTEM)
    icd11_system = _param(env, 'ampath.sha.fhir.icd11_system', _DEFAULT_ICD11)
    facility_id_type = _param(env, 'ampath.sha.fhir.facility_identifier_type_system', _DEFAULT_FACILITY_ID_TYPE)
    fac_level_ext = _param(env, 'ampath.sha.fhir.facility_level_extension', _DEFAULT_FACILITY_LEVEL_EXT)
    sch_code_ext = _param(env, 'ampath.sha.fhir.scheme_category_code_ext', _DEFAULT_SCHEME_CAT_CODE_EXT)
    sch_name_ext = _param(env, 'ampath.sha.fhir.scheme_category_name_ext', _DEFAULT_SCHEME_CAT_NAME_EXT)
    item_cov_ext = _param(env, 'ampath.sha.fhir.item_coverage_extension', _DEFAULT_ITEM_COV_EXT)
    item_cat_sys = _param(env, 'ampath.sha.fhir.item_category_system', _DEFAULT_ITEM_CATEGORY_SYSTEM)
    org_type_sys = _param(env, 'ampath.sha.fhir.organization_type_system', _DEFAULT_ORG_TYPE_SYSTEM)

    patient_id = sha_patient_identifier(order)
    coverage_id = coverage_id_for_order(order)
    claim_uuid = str(uuid.uuid4())
    bundle_uuid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    facility_id = order.x_sha_facility_id.strip()
    facility_name = order.x_sha_facility_name.strip()
    facility_level = order.x_sha_facility_level.strip()

    partner = order.partner_id
    full_name = partner.name if partner else order.name
    family, given = _split_human_name(full_name)
    gender_raw = (order.x_patient_gender or (getattr(partner, 'x_gender', None) if partner else None) or 'unknown').lower()
    if gender_raw in ('m', 'male'):
        gender = 'male'
    elif gender_raw in ('f', 'female'):
        gender = 'female'
    else:
        gender = 'unknown'

    birth_date = None
    if getattr(order, 'x_customer_dob', None):
        birth_date = str(order.x_customer_dob)
    elif partner and getattr(partner, 'x_customer_dob', None):
        birth_date = str(partner.x_customer_dob)
    if not birth_date:
        raise ValueError('Patient birth date is required on the order or partner for the claim bundle.')

    claim_type = (order.x_claim_type or 'institutional').strip()
    claim_sub_type = (order.x_claim_sub_type or 'op').strip()
    priority = (order.x_priority_code or 'normal').strip()
    scheme_cat_code = (order.x_scheme_category_code or 'CAT-SHA-001').strip()
    scheme_cat_name = (order.x_scheme_category_name or 'SOCIAL HEALTH AUTHORITY').strip()

    pre_id = (pre_auth_claim_id or (order.x_preauth_fhir_claim_id or '').strip() or None)

    currency = (order.currency_id.name or 'KES').upper()

    service_rows = []
    period_starts = []
    period_ends = []
    net_total = 0.0

    for line in lines:
        if line.display_type or line.is_downpayment:
            continue
        product = line.product_id
        code = (line.x_intervention_code or (product.default_code if product else '') or '').strip()
        display = (product.name if product else line.name) or code
        qty = float(line.product_uom_qty or 0)
        unit = float(line.price_unit or 0)
        total = float(line.price_subtotal or 0) or unit * qty
        net_total += total
        st = line.x_service_date_start or order.date_order
        en = line.x_service_date_end or order.date_order
        period_starts.append(st)
        period_ends.append(en)
        service_rows.append({
            'sequence': len(service_rows) + 1,
            'productOrService': {
                'coding': [{'system': intervention_system, 'code': code, 'display': display}],
            },
            'serviced': {
                'start': _iso_tz_plus3(st),
                'end': _iso_tz_plus3(en),
            },
            'quantity': {'value': qty},
            'unitPrice': {'value': unit, 'currency': currency},
            'factor': 1,
            'net': {'value': total, 'currency': currency},
            'category': {
                'coding': [{
                    'system': item_cat_sys,
                    'code': 'procedure',
                    'display': 'Procedure',
                }],
            },
            'extension': [{
                'url': item_cov_ext,
                'valueReference': {'reference': f'{base}/Coverage/{coverage_id}'},
            }],
        })

    bill_start = min(period_starts) if period_starts else order.date_order
    bill_end = max(period_ends) if period_ends else order.date_order

    organization = {
        'resourceType': 'Organization',
        'id': facility_id,
        'meta': {'profile': [org_profile]},
        'name': facility_name,
        'active': True,
        'extension': [{
            'url': fac_level_ext,
            'valueCodeableConcept': {
                'coding': [{
                    'system': fac_level_ext,
                    'code': facility_level,
                    'display': facility_level,
                }],
            },
        }],
        'identifier': [{
            'use': 'official',
            'value': facility_id,
            'type': {
                'coding': [{
                    'display': 'Code',
                    'system': facility_id_type,
                    'code': 'fr-code',
                }],
            },
        }],
        'type': [{
            'coding': [{'system': org_type_sys, 'code': 'prov'}],
        }],
    }

    patient = {
        'resourceType': 'Patient',
        'id': patient_id,
        'meta': {'profile': [patient_profile]},
        'identifier': [{
            'use': 'official',
            'system': f'{base}{_DEFAULT_SHANUMBER_SYSTEM_SUFFIX}',
            'value': patient_id,
        }],
        'name': [{'text': full_name, 'family': family, 'given': given}],
        'gender': gender,
        'birthDate': birth_date[:10] if birth_date else None,
    }

    coverage = {
        'resourceType': 'Coverage',
        'id': coverage_id,
        'status': 'active',
        'identifier': [{'use': 'official', 'value': coverage_id}],
        'beneficiary': {'reference': f'{base}/Patient/{patient_id}', 'type': 'Patient'},
        'extension': [
            {'url': sch_code_ext, 'valueString': scheme_cat_code},
            {'url': sch_name_ext, 'valueString': scheme_cat_name},
        ],
    }

    diagnosis_components = []
    for idx, d in enumerate(diagnoses_list(order), start=1):
        diagnosis_components.append({
            'sequence': idx,
            'diagnosisCodeableConcept': {
                'coding': [{
                    'system': icd11_system,
                    'code': d['code'],
                    'display': d['display'] or d['code'],
                }],
            },
        })

    claim = {
        'resourceType': 'Claim',
        'id': claim_uuid,
        'identifier': [{
            'system': f'{base}{_DEFAULT_CLAIM_IDENTIFIER_SUFFIX}',
            'value': claim_uuid,
        }],
        'status': 'active',
        'type': {
            'coding': [{
                'system': 'http://terminology.hl7.org/CodeSystem/claim-type',
                'code': claim_type,
            }],
        },
        'subType': {
            'coding': [{
                'system': 'http://terminology.hl7.org/CodeSystem/ex-claimsubtype',
                'code': claim_sub_type,
            }],
        },
        'use': 'claim',
        'patient': {
            'reference': f'{base}/Patient/{patient_id}',
            'type': 'Patient',
            'identifier': {
                'use': 'official',
                'system': f'{base}{_DEFAULT_SHANUMBER_SYSTEM_SUFFIX}',
                'value': patient_id,
            },
        },
        'billablePeriod': {
            'start': _iso_date_midnight(bill_start),
            'end': _iso_date_midnight(bill_end),
        },
        'created': now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        'provider': {'reference': f'{base}/Organization/{facility_id}', 'type': 'Organization'},
        'priority': {
            'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/processpriority', 'code': priority}],
        },
        'insurance': [{
            'sequence': 1,
            'focal': True,
            'coverage': {'reference': f'{base}/Coverage/{coverage_id}'},
        }],
        'diagnosis': diagnosis_components,
        'item': service_rows,
        'total': {'value': round(net_total, 2), 'currency': currency},
    }

    if pre_id:
        claim['related'] = [{
            'claim': {'reference': f'{base}/Claim/{pre_id}'},
        }]

    bundle = {
        'resourceType': 'Bundle',
        'id': bundle_uuid,
        'meta': {'profile': [bundle_profile]},
        'timestamp': now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        'type': 'message',
        'entry': [
            {'fullUrl': f'{base}/Organization/{facility_id}', 'resource': organization},
            {'fullUrl': f'{base}/Coverage/{coverage_id}', 'resource': coverage},
            {'fullUrl': f'{base}/Patient/{patient_id}', 'resource': patient},
            {'fullUrl': f'{base}/Claim/{claim_uuid}', 'resource': claim},
        ],
    }
    return bundle, claim_uuid


def _iso_date_midnight(dt):
    if not dt:
        d = datetime.now(timezone.utc).date()
    elif hasattr(dt, 'date') and callable(dt.date):
        d = dt.date()
    else:
        return str(dt)[:10] + 'T00:00:00'
    return d.isoformat() + 'T00:00:00'


def _iso_tz_plus3(dt):
    """Match .NET sample local offset +03:00 for line serviced period."""
    if not dt:
        dt = datetime.now(timezone.utc)
    if hasattr(dt, 'replace'):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone(timedelta(hours=3)))
        return dt.strftime('%Y-%m-%dT%H:%M:%S+03:00')
    return str(dt)
