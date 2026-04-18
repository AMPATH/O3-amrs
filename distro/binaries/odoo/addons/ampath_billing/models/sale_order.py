from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_payment_method = fields.Char(string="Payment method (visit)", copy=False)
    x_insurance_scheme = fields.Char(string="Insurance scheme (visit)", copy=False)
    x_preauth_status = fields.Char(string="Pre-authorization status", copy=False)
    x_preauth_code = fields.Char(string="Pre-authorization code", copy=False)
    x_preauth_request_id = fields.Char(string="Pre-authorization request ID", copy=False)

    billing_actions_visible = fields.Boolean(
        compute='_compute_billing_actions_visible',
    )
    has_claim_eligible_lines = fields.Boolean(
        compute='_compute_has_claim_eligible_lines',
    )

    @api.depends('order_line.is_claim_eligible')
    def _compute_has_claim_eligible_lines(self):
        for order in self:
            order.has_claim_eligible_lines = any(
                l.is_claim_eligible for l in order.order_line
            )

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
        claim   — skip lines already submitted or approved
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

        elif action == 'claim':
            lines = lines.filtered(
                lambda l: l.claim_status not in ('submitted', 'approved')
            )
            lines = lines.filtered(lambda l: l.is_claim_eligible)
            if not lines:
                raise UserError(_(
                    "No eligible lines for claim: ensure patient UUID is set, "
                    "and for SHIF visits complete pre-authorization first."
                ))

        elif action == 'invoice':
            lines = lines.filtered(
                lambda l: l.ampath_line_invoice_status == 'to_invoice'
            )
            if not lines:
                raise UserError(_(
                    "All selected lines have already been invoiced."
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

    def action_claim_selected(self):
        self.ensure_one()
        lines = self._get_selected_lines(action='claim')
        lines.action_bulk_fhir_claim()
        lines.write({'selected': False})

    def action_invoice_selected(self):
        """Create a partial invoice for the checked lines and open it."""
        self.ensure_one()
        lines = self._get_selected_lines(action='invoice')
        result = lines.action_bulk_invoice()
        lines.write({'selected': False})
        return result

    def action_request_preauth(self):
        self.ensure_one()
        from odoo.addons.ampath_billing.services import afyalink_client

        rid, _body = afyalink_client.request_preauth(self.env, self)
        vals = {'x_preauth_status': 'pending'}
        if rid:
            vals['x_preauth_request_id'] = rid
        self.write(vals)

    def action_check_preauth_status(self):
        self.ensure_one()
        rid = self.x_preauth_request_id
        if not rid:
            raise UserError(_("No pre-authorization request id on this order."))
        from odoo.addons.ampath_billing.services import afyalink_client

        body = afyalink_client.check_preauth_status(self.env, rid)
        st, code = afyalink_client.parse_preauth_status_body(body)
        vals = {}
        if st:
            vals['x_preauth_status'] = st
        if code:
            vals['x_preauth_code'] = code
        if vals:
            self.write(vals)

    def action_pay_cash_clear_shif(self):
        """After SHIF rejection: switch to cash and clear SHIF pre-auth fields."""
        self.ensure_one()
        self.write({
            'x_payment_method': 'CASH',
            'x_insurance_scheme': '',
            'x_preauth_status': '',
            'x_preauth_code': '',
            'x_preauth_request_id': '',
        })
