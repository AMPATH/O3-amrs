from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    claim_status = fields.Selection([
        ('draft', 'Not Claimed'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', string="FHIR Status", copy=False)

    insurance_provider_id = fields.Many2one('res.partner', string="Insurance Payer")
    fhir_claim_id = fields.Char("FHIR ID", copy=False)
    billing_actions_visible = fields.Boolean(
        related='order_id.billing_actions_visible',
    )
    selected = fields.Boolean(string="✓", default=False, copy=False)

    ampath_line_invoice_status = fields.Selection([
        ('to_invoice', 'Not Invoiced'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
    ], compute='_compute_ampath_line_invoice_status',
       string="Billing Status",
       store=True,
    )

    invoice_indicator = fields.Char(
        compute='_compute_invoice_indicator',
        string="Inv.",
        help="✅ = paid  |  📄 = invoiced (awaiting payment)  |  blank = not yet invoiced",
    )

    is_line_locked = fields.Boolean(
        compute='_compute_is_line_locked',
        string="Locked",
        help="True when the line's invoice has been paid.",
    )

    is_claim_eligible = fields.Boolean(
        compute='_compute_is_claim_eligible',
        string="Claim eligible",
        help="True when this line can be included in an AfyaLink / FHIR claim from Odoo.",
    )

    x_intervention_code = fields.Char(
        string="SHA intervention code",
        copy=False,
        help="If set, overrides product default code for DHA intervention-codes in the claim bundle.",
    )
    x_service_date_start = fields.Datetime(
        string="Service start (claim)",
        copy=False,
        help="Defaults to order date when empty.",
    )
    x_service_date_end = fields.Datetime(
        string="Service end (claim)",
        copy=False,
        help="Defaults to order date when empty.",
    )

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    @api.depends(
        'display_type',
        'is_downpayment',
        'claim_status',
        'x_intervention_code',
        'product_id.default_code',
        'order_id.x_patient_uuid',
        'order_id.x_external_identifier',
        'order_id.x_sha_client_registry_id',
        'order_id.x_payment_method',
        'order_id.x_insurance_scheme',
        'order_id.x_preauth_status',
        'order_id.x_sha_facility_id',
        'order_id.x_sha_facility_name',
        'order_id.x_sha_facility_level',
        'order_id.x_claim_diagnoses_json',
        'order_id.x_customer_dob',
        'order_id.partner_id.x_customer_dob',
    )
    def _compute_is_claim_eligible(self):
        from odoo.addons.ampath_billing.services.claim_bundle_builder import diagnoses_list

        for line in self:
            if line.display_type or line.is_downpayment:
                line.is_claim_eligible = False
                continue
            if line.claim_status in ('submitted', 'approved'):
                line.is_claim_eligible = False
                continue
            order = line.order_id
            patient = (
                (order.x_sha_client_registry_id or '').strip()
                or getattr(order, 'x_patient_uuid', None)
                or order.x_external_identifier
            )
            if not patient:
                line.is_claim_eligible = False
                continue
            if not (order.x_sha_facility_id or '').strip() or not (order.x_sha_facility_name or '').strip():
                line.is_claim_eligible = False
                continue
            if not (order.x_sha_facility_level or '').strip():
                line.is_claim_eligible = False
                continue
            if not diagnoses_list(order):
                line.is_claim_eligible = False
                continue
            if not (
                getattr(order, 'x_customer_dob', None)
                or (order.partner_id and getattr(order.partner_id, 'x_customer_dob', None))
            ):
                line.is_claim_eligible = False
                continue
            product = line.product_id
            iv_code = (line.x_intervention_code or (product.default_code if product else '') or '').strip()
            if not iv_code:
                line.is_claim_eligible = False
                continue

            pm = (order.x_payment_method or '').strip().upper()
            scheme = (order.x_insurance_scheme or '').strip()
            requires_preauth = (
                pm == 'SHIF'
                or 'SHIF' in pm
                or 'SHIF' in scheme.upper()
            )
            if requires_preauth:
                pre = (order.x_preauth_status or '').strip().lower()
                line.is_claim_eligible = pre in (
                    'approved', 'authorized', 'authorisation', 'success', 'active',
                )
            else:
                line.is_claim_eligible = True

    @api.depends(
        'invoice_lines.move_id.state',
        'invoice_lines.move_id.payment_state',
        'invoice_lines.move_id.move_type',
    )
    def _compute_ampath_line_invoice_status(self):
        for line in self:
            if line.display_type or line.is_downpayment:
                line.ampath_line_invoice_status = 'to_invoice'
                continue
            posted = line.invoice_lines.filtered(
                lambda il: il.move_id.move_type == 'out_invoice'
                and il.move_id.state == 'posted'
            )
            if not posted:
                line.ampath_line_invoice_status = 'to_invoice'
            elif any(
                il.move_id.payment_state in ('paid', 'in_payment')
                for il in posted
            ):
                line.ampath_line_invoice_status = 'paid'
            else:
                line.ampath_line_invoice_status = 'invoiced'

    @api.depends('ampath_line_invoice_status')
    def _compute_invoice_indicator(self):
        icons = {'paid': '✅', 'invoiced': '📄', 'to_invoice': ''}
        for line in self:
            line.invoice_indicator = icons.get(
                line.ampath_line_invoice_status, ''
            )

    @api.depends('ampath_line_invoice_status')
    def _compute_is_line_locked(self):
        for line in self:
            line.is_line_locked = (
                not line.display_type
                and not line.is_downpayment
                and line.ampath_line_invoice_status == 'paid'
            )

    # ------------------------------------------------------------------
    # Write guard: block price edits on lines covered by a paid invoice
    # ------------------------------------------------------------------

    _PRICE_FIELDS = frozenset({
        'product_id', 'product_template_id',
        'product_uom_qty', 'price_unit', 'discount',
    })

    def write(self, vals):
        if bool(self._PRICE_FIELDS & set(vals)):
            locked = self.filtered(
                lambda l: not l.is_downpayment
                and not l.display_type
                and l.is_line_locked
            )
            if locked:
                names = ', '.join(
                    l.product_id.name or l.name or '?'
                    for l in locked
                )
                raise UserError(_(
                    "Cannot modify the following line(s) — they are covered by "
                    "a paid invoice:\n%s"
                ) % names)
        return super().write(vals)

    # ------------------------------------------------------------------
    # Invoice preparation: carry custom fields onto the invoice line
    # ------------------------------------------------------------------

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'claim_status': self.claim_status,
            'insurance_provider_id': self.insurance_provider_id.id,
            'fhir_claim_id': self.fhir_claim_id,
        })
        return res

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def action_bulk_waive(self):
        """Apply 100% discount to selected lines."""
        for line in self:
            line.write({'discount': 100.0})

    def action_bulk_fhir_claim(self):
        """Build the FHIR claim bundle from selected lines and open a JSON preview (no HTTP)."""
        lines = self.filtered(lambda l: not l.display_type and not l.is_downpayment)
        if not lines:
            raise UserError(_("No billable lines selected for claim preview."))
        orders = lines.mapped('order_id')
        if len(orders) > 1:
            raise UserError(_("Please select lines from a single order at a time."))
        order = orders[0]
        ineligible = lines.filtered(lambda l: not l.is_claim_eligible)
        if ineligible:
            raise UserError(_(
                "Some selected lines are not eligible for claims. Check: SHA facility "
                "fields, ICD-11 diagnoses JSON, intervention code per line, date of birth, "
                "SHIF pre-authorization when applicable, and claim status."
            ))
        from odoo.addons.ampath_billing.services.claim_bundle_builder import build_claim_bundle

        try:
            bundle, _internal_claim_id = build_claim_bundle(order, lines, pre_auth_claim_id=None)
        except ValueError as e:
            raise UserError(str(e)) from e

        return order._action_open_payload_preview(
            _('FHIR claim bundle (JSON)'),
            bundle,
        )

    def action_invoice_this_line(self):
        """Invoice only this single line — no checkbox required."""
        self.ensure_one()
        return self.action_bulk_invoice()

    def action_bulk_invoice(self):
        """Create a partial invoice for the selected lines (single or multi-line).

        All selected lines are invoiced at their full sale quantity regardless
        of delivery status or the order-level invoice_policy, so the caller
        should only pass lines that are genuinely ready to be billed.
        """
        orders = self.mapped('order_id')
        if len(orders) > 1:
            raise UserError(_(
                "Please select lines from a single order at a time."
            ))

        order = orders[0]
        invoice_vals = order._prepare_invoice()
        invoice_line_vals_list = []

        for line in self:
            if line.display_type or line.is_downpayment:
                continue
            line_vals = line._prepare_invoice_line()
            # Always bill the full line quantity, not just qty_to_invoice,
            # since we are doing explicit partial invoicing per selected line.
            line_vals['quantity'] = line.product_uom_qty
            invoice_line_vals_list.append((0, 0, line_vals))

        if not invoice_line_vals_list:
            raise UserError(_("No invoiceable lines selected."))

        invoice_vals['invoice_line_ids'] = invoice_line_vals_list
        invoice = self.env['account.move'].sudo().create(invoice_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
