# -*- coding: utf-8 -*-
"""
Billing status endpoint for the AMPATH EMR / EIP integration.

GET /ampath/billing/patient/<patient_external_id>

Headers (required):
    login    – Odoo username
    password – Odoo password

Response 200 (application/json):
{
  "patient_external_id": "<openmrs-uuid>",
  "orders": [
    {
      "id": 1,
      "name": "S00001",
      "state": "sale",
      "state_label": "Sales Order",
      "date_order": "2024-01-01T10:00:00",
      "customer": { "id": 5, "name": "John Doe",
                    "external_id": "<openmrs-uuid>",
                    "dob": "1990-01-01" },
      "company": { "id": 1, "name": "AMPATH" },
      "amount_untaxed": 500.0,
      "amount_tax": 0.0,
      "amount_total": 500.0,
      "invoice_status": "invoiced",
      "order_lines": [
        {
          "id": 10,
          "sequence": 1,
          "product_id": 25,
          "product_name": "Metformin 500mg",
          "product_code": "MET500",
          "product_category": "Medications",
          "quantity": 30.0,
          "uom": "Tablet",
          "price_unit": 5.0,
          "discount": 0.0,
          "price_subtotal": 150.0,
          "price_total": 150.0,
          "billing_status": "invoiced",
          "invoice_indicator": "📄",
          "claim_status": "draft",
          "insurance_provider": null
        }
      ],
      "invoices": [
        {
          "id": 7,
          "name": "INV/2024/0001",
          "state": "posted",
          "payment_state": "paid",
          "amount_total": 150.0,
          "invoice_date": "2024-01-02"
        }
      ]
    }
  ]
}
"""
import json
import logging

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
        return {
            'id': line.id,
            'sequence': line.sequence,
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

        return {
            'id': order.id,
            'name': order.name,
            'state': order.state,
            'state_label': _ORDER_STATE_LABELS.get(order.state, order.state),
            'date_order': (
                order.date_order.isoformat() if order.date_order else None
            ),
            'customer': {
                'id': partner.id,
                'name': partner.name,
                'external_id': partner.x_external_identifier or None,
                'dob': str(partner.x_customer_dob) if partner.x_customer_dob else None,
            } if partner else None,
            'company': {
                'id': company.id,
                'name': company.name,
            } if company else None,
            'patient_external_id': order.x_external_identifier or None,
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
