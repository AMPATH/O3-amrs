import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_payment_method = fields.Char(string="Payment method (visit)", copy=False)
    x_insurance_scheme = fields.Char(string="Insurance scheme (visit)", copy=False)
    x_preauth_status = fields.Char(string="Pre-authorization status", copy=False)
    x_preauth_code = fields.Char(string="Pre-authorization code", copy=False)
    x_preauth_request_id = fields.Char(string="Pre-authorization request ID", copy=False)
    x_preauth_fhir_claim_id = fields.Char(
        string="Pre-auth FHIR Claim id",
        copy=False,
        help="FHIR Claim.id returned after SHIF pre-authorization; links the final claim via Claim.related.",
    )

    # SHA / HIE bundle data (BuildClaimBundleRequest); billing amounts from Odoo lines.
    x_sha_client_registry_id = fields.Char(
        string="SHA client registry id",
        copy=False,
        help="National / SHA patient id for FHIR Patient.id. If empty, OpenMRS patient UUID is used.",
    )
    x_sha_facility_id = fields.Char(string="SHA facility id", copy=False)
    x_sha_facility_name = fields.Char(string="SHA facility name", copy=False)
    x_sha_facility_level = fields.Char(string="SHA facility level", copy=False)
    x_coverage_id = fields.Char(
        string="Coverage id override",
        copy=False,
        help="If empty, defaults to \"{patient}-sha-coverage\" from SHA client registry id or patient UUID.",
    )
    x_scheme_category_code = fields.Char(
        string="Scheme category code", default="CAT-SHA-001", copy=False)
    x_scheme_category_name = fields.Char(
        string="Scheme category name",
        default="SOCIAL HEALTH AUTHORITY",
        copy=False,
    )
    x_claim_type = fields.Char(string="Claim type", default="institutional", copy=False)
    x_claim_sub_type = fields.Char(string="Claim sub-type", default="op", copy=False)
    x_priority_code = fields.Char(string="Process priority", default="normal", copy=False)
    x_claim_practitioner_id = fields.Char(string="Claim practitioner id", copy=False)
    x_claim_diagnoses_json = fields.Text(
        string="Claim diagnoses (JSON)",
        copy=False,
        help='ICD-11-oriented list: [{"code":"...","display":"..."}, ...]. '
        'The EIP fills this from FHIR Conditions for the whole visit (visit encounter + child encounters) '
        'when the quotation is created and whenever a new order line is synced.',
    )
    x_openmrs_encounter_uuid = fields.Char(
        string="OpenMRS clinical encounter UUID",
        copy=False,
        help="Encounter that triggered the quotation (EIP); used to refresh diagnoses from FHIR.",
    )
    x_patient_gender = fields.Char(
        string="Patient gender (claims)",
        copy=False,
        help="male / female / unknown — sent on FHIR Patient and pre-auth payload.",
    )
    # Declared here (not only via odoo_initializer CSV) so @api.depends on sale.order.line
    # resolves during registry init; ampath_billing is auto_install and loads with sale.
    x_patient_uuid = fields.Char(string="Patient UUID", copy=False)
    x_external_identifier = fields.Char(string="Customer External ID", copy=False)
    x_customer_dob = fields.Date(string="Customer Date of Birth", copy=False)
    x_customer_weight = fields.Char(
        string="Customer weight",
        copy=False,
        help='Patient weight from OpenMRS (EIP); corresponds to odoo.customer.weight.field.',
    )

    billing_actions_visible = fields.Boolean(
        compute='_compute_billing_actions_visible',
    )
    has_claim_eligible_lines = fields.Boolean(
        compute='_compute_has_claim_eligible_lines',
    )
    has_preauth_eligible_lines = fields.Boolean(
        compute='_compute_has_preauth_eligible_lines',
        help='True when at least one line needs SHA pre-authorization (intervention code).',
    )
    has_claim_submit_lines = fields.Boolean(
        compute='_compute_has_claim_submit_lines',
        help='True when at least one line can be submitted as a PHC claim (ETL) instead of cash.',
    )

    # Prescription print (ported from Transcare health_care)
    ampath_has_understock_lines = fields.Boolean(
        compute='_compute_ampath_has_understock_lines',
        string='Understock for invoicing',
        help=(
            'Storable products still have quantity to invoice, not enough free stock, '
            'and are not yet marked by printing the prescription.'
        ),
    )
    ampath_has_prescription_hold = fields.Boolean(
        compute='_compute_ampath_has_prescription_hold',
        string='Has prescription invoice hold',
    )
    ampath_prescription_pdf_line_ids = fields.Many2many(
        'sale.order.line',
        'ampath_so_prescript_pdf_line_rel',
        'order_id',
        'line_id',
        string='Prescription PDF lines (staging)',
        copy=False,
    )

    ampath_amount_visit_total = fields.Monetary(
        string='Visit total (untaxed)',
        compute='_compute_ampath_billing_totals',
        store=True,
        currency_field='currency_id',
        help='Sum of untaxed line amounts on this order (product lines only).',
    )
    ampath_amount_insurance_claim = fields.Monetary(
        string='Insurance (claim submitted)',
        compute='_compute_ampath_billing_totals',
        store=True,
        currency_field='currency_id',
        help='Untaxed value of lines submitted or approved on an insurance claim.',
    )
    ampath_amount_cash_invoiced = fields.Monetary(
        string='Cash invoiced',
        compute='_compute_ampath_billing_totals',
        store=True,
        currency_field='currency_id',
        help='Untaxed value of lines already on a posted patient invoice.',
    )
    ampath_amount_cash_to_invoice = fields.Monetary(
        string='Cash to invoice',
        compute='_compute_ampath_billing_totals',
        store=True,
        currency_field='currency_id',
        help='Untaxed value of lines still to bill to the patient in cash.',
    )

    def _ampath_billable_product_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and not l.is_downpayment
        )

    @api.depends(
        'order_line.price_subtotal',
        'order_line.claim_status',
        'order_line.ampath_line_invoice_status',
        'order_line.display_type',
        'order_line.is_downpayment',
        'currency_id',
    )
    def _compute_ampath_billing_totals(self):
        claim_states = frozenset({'submitted', 'approved'})
        for order in self:
            lines = order._ampath_billable_product_lines()
            order.ampath_amount_visit_total = sum(lines.mapped('price_subtotal'))
            claim_lines = lines.filtered(lambda l: l.claim_status in claim_states)
            order.ampath_amount_insurance_claim = sum(claim_lines.mapped('price_subtotal'))
            cash_invoiced = lines.filtered(
                lambda l: l.ampath_line_invoice_status in ('invoiced', 'paid')
            )
            order.ampath_amount_cash_invoiced = sum(cash_invoiced.mapped('price_subtotal'))
            cash_to_inv = lines.filtered(
                lambda l: l.ampath_line_invoice_status == 'to_invoice'
            )
            order.ampath_amount_cash_to_invoice = sum(cash_to_inv.mapped('price_subtotal'))

    @api.depends(
        'order_line.is_preauth_eligible',
        'order_line.product_id.x_intervention_code',
        'order_line.claim_status',
        'order_line.display_type',
        'order_line.is_downpayment',
        'order_line.order_id.x_preauth_status',
        'order_line.order_id.x_patient_uuid',
        'order_line.order_id.x_customer_dob',
    )
    def _compute_has_preauth_eligible_lines(self):
        for order in self:
            order.has_preauth_eligible_lines = bool(order._ampath_preauth_action_lines())

    @api.depends(
        'order_line.is_claim_eligible',
        'order_line.ampath_prescription_printed',
        'order_line.discount',
        'order_line.ampath_line_invoice_status',
        'order_line.claim_status',
        'order_line.display_type',
        'order_line.is_downpayment',
        'order_line.product_id',
        'order_line.qty_to_invoice',
        'warehouse_id',
    )
    def _compute_has_claim_eligible_lines(self):
        for order in self:
            order.has_claim_eligible_lines = bool(order._ampath_claim_action_lines())

    @api.depends(
        'order_line.is_claim_eligible',
        'order_line.ampath_prescription_printed',
        'order_line.discount',
        'order_line.ampath_line_invoice_status',
        'order_line.claim_status',
        'order_line.display_type',
        'order_line.is_downpayment',
        'order_line.product_id',
        'order_line.qty_to_invoice',
        'warehouse_id',
    )
    def _compute_has_claim_submit_lines(self):
        for order in self:
            order.has_claim_submit_lines = bool(order._order_lines_for_etl_claim_submit())

    def _ampath_lines_skip_for_stock_and_rx(self, lines):
        """Drop prescription-hold and understock storable lines (invoice + claim parity)."""
        self.ensure_one()
        lines = lines.filtered(lambda l: not l.display_type and not l.is_downpayment)
        return lines.filtered(lambda l: not l.ampath_prescription_printed) - (
            self._ampath_understock_invoiceable_lines()
        )

    def _ampath_preauth_action_lines(self, lines=None):
        """Intervention-code lines that still need SHA pre-authorization (no stock gate)."""
        self.ensure_one()
        if lines is None:
            lines = self.order_line
        return lines.filtered(
            lambda l: (
                not l.display_type
                and not l.is_downpayment
                and l.is_preauth_eligible
            )
        )

    def _ampath_claim_action_lines(self, lines=None):
        """PHC claim lines for ETL submit (payment instead of cash), excl. Rx hold / understock."""
        self.ensure_one()
        if lines is None:
            lines = self.order_line
        candidates = lines.filtered(
            lambda l: (
                not l.display_type
                and not l.is_downpayment
                and (l.discount or 0) < 100.0
                and l.ampath_line_invoice_status == 'to_invoice'
                and l.claim_status not in ('submitted', 'approved')
                and l.is_claim_eligible
            )
        )
        return self._ampath_lines_skip_for_stock_and_rx(candidates)

    def _order_lines_for_etl_claim_submit(self):
        """All qualifying PHC claim lines for Submit claim (ETL)."""
        self.ensure_one()
        return self._ampath_claim_action_lines()

    @api.depends('state', 'invoice_ids.payment_state')
    def _compute_billing_actions_visible(self):
        for order in self:
            if order.state in ('done', 'cancel'):
                order.billing_actions_visible = False
            elif order.state == 'sale' and order.invoice_ids:
                all_paid = all(
                    inv.payment_state == 'paid'
                    for inv in order.invoice_ids
                    if inv.state == 'posted'
                )
                order.billing_actions_visible = not all_paid
            else:
                order.billing_actions_visible = True

    @api.depends('order_line.ampath_prescription_printed')
    def _compute_ampath_has_prescription_hold(self):
        for order in self:
            order.ampath_has_prescription_hold = bool(
                order.order_line.filtered('ampath_prescription_printed')
            )

    @api.depends(
        'order_line',
        'order_line.display_type',
        'order_line.product_id',
        'order_line.product_id.type',
        'order_line.qty_to_invoice',
        'order_line.qty_delivered',
        'order_line.qty_invoiced',
        'order_line.product_uom',
        'order_line.ampath_prescription_printed',
        'warehouse_id',
        'company_id',
    )
    def _compute_ampath_has_understock_lines(self):
        for order in self:
            order.ampath_has_understock_lines = bool(
                order._ampath_understock_invoiceable_lines()
            )

    def _ampath_stock_warehouse(self):
        self.ensure_one()
        wh = self.warehouse_id
        if not wh:
            wh = (
                self.env['stock.warehouse']
                .sudo()
                .search([('company_id', 'in', self.company_id.ids)], limit=1)
            )
        return wh

    def _ampath_understock_invoiceable_lines(self):
        """Storable lines to invoice with insufficient free qty (excl. prescription hold)."""
        self.ensure_one()
        wh = self._ampath_stock_warehouse()
        bad = self.env['sale.order.line']
        for line in self.order_line:
            if line.display_type in ('line_section', 'line_note'):
                continue
            if line.ampath_prescription_printed:
                continue
            if line.claim_status in ('submitted', 'approved'):
                continue
            if not line._ampath_requires_stock_for_billing():
                continue
            qty_to_inv = line.qty_to_invoice
            if qty_to_inv <= 0:
                continue
            product = line.product_id
            if wh:
                product = product.with_context(warehouse=wh.id)
            avail = product.free_qty
            qty_in_product_uom = line.product_uom._compute_quantity(
                qty_to_inv,
                line.product_id.uom_id,
            )
            precision = line.product_id.uom_id.rounding
            if float_compare(avail, qty_in_product_uom, precision_rounding=precision) < 0:
                bad |= line
        return bad

    def _ampath_prescription_lines(self):
        """Medication-style lines only: goods (storable/consumable), not services.

        Excludes optional-product child lines (``linked_line_id`` when present).
        """
        self.ensure_one()
        lines = self.env['sale.order.line']
        has_linked = 'linked_line_id' in self.env['sale.order.line']._fields
        for line in self.order_line:
            if line.display_type:
                continue
            if not line.product_id:
                continue
            if line.product_id.type not in ('product', 'consu'):
                continue
            if has_linked and line.linked_line_id:
                continue
            lines |= line
        return lines

    def _get_invoiceable_lines(self, final=False):
        """Invoiceable lines minus prescription hold and minus understocked storable meds.

        Understocked lines (not yet on a prescription PDF) are skipped so services and
        in-stock lines can still be invoiced; print prescription to hold meds off invoices
        and deliveries until stock is available or the hold is cleared.
        """
        lines = super()._get_invoiceable_lines(final=final)
        lines = lines.filtered(
            lambda l: l.display_type in ('line_section', 'line_note')
            or not l.ampath_prescription_printed
        )
        lines = lines.filtered(
            lambda l: l.display_type in ('line_section', 'line_note')
            or l.claim_status not in ('submitted', 'approved')
        )
        bad = self._ampath_understock_invoiceable_lines()
        return lines - bad

    def action_print_prescription(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Print prescription'),
            'res_model': 'ampath.prescription.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_order_id': self.id},
        }

    def action_clear_prescription_invoice_hold(self):
        """Include prescription-printed medication lines on invoices again."""
        for order in self:
            order.order_line.filtered('ampath_prescription_printed').write(
                {'ampath_prescription_printed': False}
            )
            order.ampath_prescription_pdf_line_ids = [(5, 0, 0)]
        return True

    def _action_open_payload_preview(self, title, payload_dict):
        """Open a modal with pretty-printed JSON (no external HTTP)."""
        self.ensure_one()
        text = json.dumps(payload_dict, indent=2, ensure_ascii=False, default=str)
        wiz = self.env['ampath.billing.payload.preview'].create({
            'sale_order_id': self.id,
            'title': title,
            'payload_text': text,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'ampath.billing.payload.preview',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _action_open_claim_submit_result(self, body, submitted_lines=None):
        """Modal after a successful claim submit (not the offline payload preview)."""
        self.ensure_one()
        from odoo.addons.ampath_billing.services.afyalink_client import etl_claim_response_headline

        headline = etl_claim_response_headline(body)
        response_full = json.dumps(
            body if isinstance(body, dict) else {'raw': body},
            indent=2,
            ensure_ascii=False,
            default=str,
        )
        wiz = self.env['ampath.billing.claim.submit.result'].create({
            'sale_order_id': self.id,
            'headline': headline,
            'response_full': response_full,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Claim sent'),
            'res_model': 'ampath.billing.claim.submit.result',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_selected_lines(self, action=None):
        """
        Return selected product lines that are eligible for *action*.

        Rows excluded for every action
        ────────────────────────────────
        • section / note rows  (display_type set)
        • down-payment lines   (is_downpayment)
        • lines locked by a paid invoice (is_line_locked)

        Additional per-action exclusions
        ──────────────────────────────────
        waive   — skip lines already at 100% discount
        invoice — skip lines already fully invoiced
        """
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda l: l.selected and not l.display_type and not l.is_downpayment
        )
        if not lines:
            raise UserError(_(
                "No lines selected. Check the ✓ column on the lines you want "
                "to act on."
            ))

        lines = lines.filtered(lambda l: not l.is_line_locked)

        if action == 'waive':
            lines = lines.filtered(lambda l: l.discount != 100.0)
            if not lines:
                raise UserError(_(
                    "All selected lines are already waived or covered by a "
                    "paid invoice — nothing to waive."
                ))

        elif action == 'invoice':
            lines = lines.filtered(lambda l: not l.ampath_prescription_printed)
            lines = lines.filtered(
                lambda l: l.claim_status not in ('submitted', 'approved')
            )
            understock = self._ampath_understock_invoiceable_lines()
            lines = lines - understock
            lines = lines.filtered(
                lambda l: l.ampath_line_invoice_status == 'to_invoice'
            )
            if not lines:
                raise UserError(_(
                    'No lines to invoice: they may already be invoiced, submitted on an '
                    'insurance claim, on prescription hold (use "Clear prescription hold"), '
                    'or out of stock (use "Print prescription" for those medications).'
                ))

        else:
            if not lines:
                raise UserError(_(
                    "No eligible lines to process after excluding locked items."
                ))

        return lines

    def action_waive_selected(self):
        self.ensure_one()
        lines = self._get_selected_lines(action='waive')
        lines.action_bulk_waive()
        lines.write({'selected': False})

    def action_submit_etl_claim_selected(self):
        """POST all qualifying PHC claim lines to AMPATH ETL (insurance payment, not cash)."""
        self.ensure_one()
        lines = self._order_lines_for_etl_claim_submit()
        if not lines:
            raise UserError(_(
                'No PHC claim lines to submit. Waived, invoiced, or already-submitted lines '
                'are excluded. Intervention-code products need approved pre-authorization '
                '(use Preauth first). Out-of-stock medications need Print prescription first.'
            ))
        return lines.action_submit_etl_claim()

    def action_invoice_selected(self):
        """Create a partial invoice for the checked lines and open it."""
        self.ensure_one()
        lines = self._get_selected_lines(action='invoice')
        result = lines.action_bulk_invoice()
        lines.write({'selected': False})
        return result

    def action_request_preauth(self):
        """Build SHA pre-authorization JSON for intervention-code lines (separate from claim submit)."""
        self.ensure_one()
        lines = self._ampath_preauth_action_lines()
        if not lines:
            raise UserError(_(
                'No lines need pre-authorization. Preauth applies to products with an '
                'intervention code when visit pre-authorization is not yet approved.'
            ))
        from odoo.addons.ampath_billing.services.claim_bundle_builder import build_preauth_request_payload

        payload = build_preauth_request_payload(self, lines)
        return self._action_open_payload_preview(
            _('Pre-authorization payload (JSON)'),
            payload,
        )

    def action_check_preauth_status(self):
        self.ensure_one()
        raise UserError(_(
            'Pre-authorization status polling is not enabled yet. '
            'It will be wired when the receiving endpoint is available.'
        ))

    def action_pay_cash_clear_shif(self):
        """After SHIF rejection: switch to cash and clear SHIF pre-auth fields."""
        self.ensure_one()
        self.write({
            'x_payment_method': 'CASH',
            'x_insurance_scheme': '',
            'x_preauth_status': '',
            'x_preauth_code': '',
            'x_preauth_request_id': '',
            'x_preauth_fhir_claim_id': '',
        })

