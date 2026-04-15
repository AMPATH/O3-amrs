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

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

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
        """Submit FHIR claims for selected lines."""
        for line in self:
            if not line.insurance_provider_id:
                raise UserError(
                    _("Select an Insurance Payer for %s first.") % line.name
                )
            line.write({'claim_status': 'submitted', 'fhir_claim_id': 'FHIR-SO-TMP'})

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
