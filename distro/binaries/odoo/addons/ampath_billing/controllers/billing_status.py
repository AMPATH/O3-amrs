# -*- coding: utf-8 -*-
"""
Billing status endpoints for the AMPATH EMR / EIP integration.

All endpoints require HTTP headers:
    login    – Odoo username
    password – Odoo password

Endpoints
---------
GET /ampath/billing/patient/<patient_external_id>
    All sale orders for a patient (OpenMRS patient UUID).

GET /ampath/billing/order/<order_id>
    Full detail for a single sale order (Odoo numeric ID).

GET /ampath/billing/orders
    Paginated list of sale orders with optional filters.
    Query params:
        company_external_id  – Location UUID of the company/facility
        date_from            – ISO date (YYYY-MM-DD), inclusive lower bound on date_order
        date_to              – ISO date (YYYY-MM-DD), inclusive upper bound on date_order
        state                – Order state: draft | sent | sale | done | cancel
        limit                – Max records to return (default 100, max 500)
        offset               – Pagination offset (default 0)
"""
import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_ORDER_STATE_LABELS = {
    'draft':  'Quotation',
    'sent':   'Quotation Sent',
    'sale':   'Sales Order',
    'done':   'Locked',
    'cancel': 'Cancelled',
}


class BillingStatusController(http.Controller):

    # ------------------------------------------------------------------
    # Authentication helper
    # ------------------------------------------------------------------

    def _authenticate(self):
        """Validate login/password headers and return uid, or None on failure."""
        login = request.httprequest.headers.get('login')
        password = request.httprequest.headers.get('password')
        if not login or not password:
            return None
        try:
            uid = request.session.authenticate(request.session.db, login, password)
            return uid if uid else None
        except Exception:
            return None

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, default=str),
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'no-store'),
            ],
            status=status,
        )

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _serialize_line(self, line):
        provider = line.insurance_provider_id
        product = line.product_id
        openmrs_order_id = getattr(line, 'x_openmrs_order_id', None) or None
        return {
            'id': line.id,
            'sequence': line.sequence,
            'openmrs_order_id': openmrs_order_id,
            'product_id': product.id if product else None,
            'product_name': product.name if product else line.name,
            'product_code': product.default_code if product else None,
            'product_category': (
                product.categ_id.name if product and product.categ_id else None
            ),
            'quantity': line.product_uom_qty,
            'uom': line.product_uom.name if line.product_uom else None,
            'price_unit': line.price_unit,
            'discount': line.discount,
            'price_subtotal': line.price_subtotal,
            'price_total': line.price_total,
            'billing_status': line.ampath_line_invoice_status,
            'invoice_indicator': line.invoice_indicator,
            'claim_status': line.claim_status,
            'fhir_claim_id': line.fhir_claim_id,
            'insurance_provider': {
                'id': provider.id,
                'name': provider.name,
            } if provider else None,
        }

    def _serialize_invoice_line(self, inv_line):
        """Summarise one account.move.line, linking back to its sale order lines."""
        sale_lines = inv_line.sale_line_ids
        return {
            'id': inv_line.id,
            'name': inv_line.name,
            'quantity': inv_line.quantity,
            'price_unit': inv_line.price_unit,
            'discount': inv_line.discount,
            'price_subtotal': inv_line.price_subtotal,
            'price_total': inv_line.price_total,
            # Back-reference to the originating sale order line(s)
            'sale_order_line_ids': sale_lines.ids,
            'sale_order_lines': [
                {
                    'id': sol.id,
                    'openmrs_order_id': getattr(sol, 'x_openmrs_order_id', None) or None,
                    'product_id': sol.product_id.id if sol.product_id else None,
                    'product_name': (
                        sol.product_id.name if sol.product_id else sol.name
                    ),
                    'product_code': sol.product_id.default_code if sol.product_id else None,
                    'product_category': (
                        sol.product_id.categ_id.name
                        if sol.product_id and sol.product_id.categ_id
                        else None
                    ),
                    'quantity': sol.product_uom_qty,
                    'uom': sol.product_uom.name if sol.product_uom else None,
                    'billing_status': sol.ampath_line_invoice_status,
                    'invoice_indicator': sol.invoice_indicator,
                    'claim_status': sol.claim_status,
                }
                for sol in sale_lines
                if not sol.display_type and not sol.is_downpayment
            ],
        }

    def _serialize_invoice(self, inv):
        # In Odoo 17 product lines have display_type == 'product';
        # tax, payment_term, and rounding lines are excluded.
        inv_lines = inv.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        )
        return {
            'id': inv.id,
            'name': inv.name,
            'state': inv.state,
            'payment_state': inv.payment_state,
            'amount_untaxed': inv.amount_untaxed,
            'amount_tax': inv.amount_tax,
            'amount_total': inv.amount_total,
            'invoice_date': str(inv.invoice_date) if inv.invoice_date else None,
            'invoice_date_due': (
                str(inv.invoice_date_due) if inv.invoice_date_due else None
            ),
            'invoice_lines': [
                self._serialize_invoice_line(l) for l in inv_lines
            ],
        }

    def _serialize_order(self, order):
        partner = order.partner_id
        company = order.company_id

        lines = [
            self._serialize_line(l)
            for l in order.order_line
            if not l.display_type and not l.is_downpayment
        ]

        invoices = [
            self._serialize_invoice(inv)
            for inv in order.invoice_ids
            if inv.move_type == 'out_invoice'
        ]

        patient_uuid = (
            getattr(order, 'x_patient_uuid', None)
            or order.x_external_identifier
            or None
        )
        company_ext_id = None
        if company:
            imd = request.env['ir.model.data'].sudo().search([
                ('model', '=', 'res.company'),
                ('res_id', '=', company.id),
                ('module', '=', 'init'),
            ], limit=1)
            company_ext_id = imd.name if imd else None

        return {
            'id': order.id,
            'name': order.name,
            'state': order.state,
            'state_label': _ORDER_STATE_LABELS.get(order.state, order.state),
            'date_order': (
                order.date_order.isoformat() if order.date_order else None
            ),
            'patient_uuid': patient_uuid,
            'customer': {
                'id': partner.id,
                'name': partner.name,
                'external_id': partner.x_external_identifier or None,
                'dob': str(partner.x_customer_dob) if partner.x_customer_dob else None,
            } if partner else None,
            'company': {
                'id': company.id,
                'name': company.name,
                'external_id': company_ext_id,
            } if company else None,
            'patient_dob': (
                str(order.x_customer_dob) if order.x_customer_dob else None
            ),
            'patient_weight': order.x_customer_weight or None,
            'amount_untaxed': order.amount_untaxed,
            'amount_tax': order.amount_tax,
            'amount_total': order.amount_total,
            'invoice_status': order.invoice_status,
            'order_lines': lines,
            'invoices': invoices,
        }

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @http.route(
        '/ampath/billing/patient/<string:patient_external_id>',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def billing_status_by_patient(self, patient_external_id, **kw):
        """Return all sale orders for a patient identified by their OpenMRS UUID.

        Searches both res.partner.x_external_identifier (partner UUID) and
        sale.order.x_external_identifier (order-level UUID set by EIP).
        """
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        env = request.env

        # Find orders via the partner's external ID
        partners = env['res.partner'].sudo().search(
            [('x_external_identifier', '=', patient_external_id)]
        )
        domain = ['|',
            ('partner_id', 'in', partners.ids),
            ('x_external_identifier', '=', patient_external_id),
        ]

        orders = env['sale.order'].sudo().search(
            domain,
            order='date_order desc',
        )

        if not orders:
            return self._json_response({
                'patient_external_id': patient_external_id,
                'orders': [],
            })

        return self._json_response({
            'patient_external_id': patient_external_id,
            'orders': [self._serialize_order(o) for o in orders],
        })

    @http.route(
        '/ampath/billing/order/<int:order_id>',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def billing_status_by_order(self, order_id, **kw):
        """Return full billing details for a single sale order by its Odoo id."""
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        order = request.env['sale.order'].sudo().browse(order_id)
        if not order.exists():
            return self._json_response(
                {'error': f'Order {order_id} not found.'},
                status=404,
            )

        return self._json_response(self._serialize_order(order))

    @http.route(
        '/ampath/billing/orders',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def list_orders(self, **kw):
        """Return a paginated list of sale orders with optional filters.

        Query parameters
        ----------------
        company_external_id : str, optional
            Location UUID used as the company's initializer XML-ID name.
        date_from : str, optional
            ISO date (YYYY-MM-DD).  Lower bound on date_order (inclusive).
        date_to : str, optional
            ISO date (YYYY-MM-DD).  Upper bound on date_order (inclusive).
        state : str, optional
            One of: draft | sent | sale | done | cancel
        limit : int, optional
            Max records to return (default 100, capped at 500).
        offset : int, optional
            Pagination offset (default 0).
        """
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        env = request.env

        # --- Build domain ---------------------------------------------------
        domain = []

        company_external_id = kw.get('company_external_id', '').strip()
        if company_external_id:
            imd = env['ir.model.data'].sudo().search([
                ('module', '=', 'init'),
                ('name', '=', company_external_id),
                ('model', '=', 'res.company'),
            ], limit=1)
            if not imd:
                return self._json_response({
                    'error': f'No company found for external ID "{company_external_id}".',
                }, status=404)
            domain.append(('company_id', '=', imd.res_id))

        date_from = kw.get('date_from', '').strip()
        if date_from:
            try:
                datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                return self._json_response(
                    {'error': 'date_from must be in YYYY-MM-DD format.'}, status=400
                )
            domain.append(('date_order', '>=', date_from + ' 00:00:00'))

        date_to = kw.get('date_to', '').strip()
        if date_to:
            try:
                datetime.strptime(date_to, '%Y-%m-%d')
            except ValueError:
                return self._json_response(
                    {'error': 'date_to must be in YYYY-MM-DD format.'}, status=400
                )
            domain.append(('date_order', '<=', date_to + ' 23:59:59'))

        state = kw.get('state', '').strip()
        valid_states = ('draft', 'sent', 'sale', 'done', 'cancel')
        if state:
            if state not in valid_states:
                return self._json_response(
                    {'error': f'state must be one of: {", ".join(valid_states)}.'},
                    status=400,
                )
            domain.append(('state', '=', state))

        # --- Pagination ------------------------------------------------------
        try:
            limit = min(int(kw.get('limit', 100)), 500)
            offset = int(kw.get('offset', 0))
        except (TypeError, ValueError):
            return self._json_response(
                {'error': 'limit and offset must be integers.'}, status=400
            )

        # --- Query -----------------------------------------------------------
        Order = env['sale.order'].sudo()
        total = Order.search_count(domain)
        orders = Order.search(domain, order='date_order desc', limit=limit, offset=offset)

        def _summary(order):
            partner = order.partner_id
            company = order.company_id
            patient_uuid = (
                getattr(order, 'x_patient_uuid', None)
                or order.x_external_identifier
                or None
            )
            company_ext_id = None
            if company:
                imd = env['ir.model.data'].sudo().search([
                    ('model', '=', 'res.company'),
                    ('res_id', '=', company.id),
                    ('module', '=', 'init'),
                ], limit=1)
                company_ext_id = imd.name if imd else None
            return {
                'id': order.id,
                'name': order.name,
                'state': order.state,
                'state_label': _ORDER_STATE_LABELS.get(order.state, order.state),
                'date_order': order.date_order.isoformat() if order.date_order else None,
                'patient_uuid': patient_uuid,
                'customer': {
                    'id': partner.id,
                    'name': partner.name,
                    'external_id': partner.x_external_identifier or None,
                } if partner else None,
                'company': {
                    'id': company.id,
                    'name': company.name,
                    'external_id': company_ext_id,
                } if company else None,
                'amount_total': order.amount_total,
                'invoice_status': order.invoice_status,
                'order_line_count': len(
                    order.order_line.filtered(
                        lambda l: not l.display_type and not l.is_downpayment
                    )
                ),
            }

        return self._json_response({
            'total': total,
            'limit': limit,
            'offset': offset,
            'orders': [_summary(o) for o in orders],
        })
