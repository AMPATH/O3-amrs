import json

from odoo import models, fields, api, _
from odoo.exceptions import UserError


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
    has_claim_submit_lines = fields.Boolean(
        compute='_compute_has_claim_submit_lines',
        help='True when at least one line can be submitted (eligible, not waived, not yet invoiced).',
    )

    @api.depends('order_line.is_claim_eligible')
    def _compute_has_claim_eligible_lines(self):
        for order in self:
            order.has_claim_eligible_lines = any(
                l.is_claim_eligible for l in order.order_line
            )

    @api.depends(
        'order_line.is_claim_eligible',
        'order_line.discount',
        'order_line.ampath_line_invoice_status',
        'order_line.claim_status',
        'order_line.display_type',
        'order_line.is_downpayment',
    )
    def _compute_has_claim_submit_lines(self):
        for order in self:
            order.has_claim_submit_lines = bool(order._order_lines_for_etl_claim_submit())

    def _order_lines_for_etl_claim_submit(self):
        """Lines to POST on Submit claim: eligible, not waived, still **to_invoice** (not manually invoiced)."""
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: (
                not l.display_type
                and not l.is_downpayment
                and (l.discount or 0) < 100.0
                and l.ampath_line_invoice_status == 'to_invoice'
                and l.claim_status not in ('submitted', 'approved')
                and l.is_claim_eligible
            )
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

    def _action_open_claim_submit_result(self, lines_updated_count, response_body):
        """Short summary line + full payer JSON so nothing replaces the raw response."""
        self.ensure_one()
        if isinstance(response_body, (dict, list)):
            full_text = json.dumps(response_body, indent=2, ensure_ascii=False, default=str)
        else:
            full_text = str(response_body) if response_body is not None else ''
        headline = _(
            'Claim sent successfully. %(n)s sale order line(s) were set to Submitted.'
        ) % {'n': lines_updated_count}
        wiz = self.env['ampath.billing.claim.submit.result'].create({
            'sale_order_id': self.id,
            'headline': headline,
            'response_full': full_text,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Claim submission result'),
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
            # Legacy path if claim ever uses selection again; submit uses
            # ``_order_lines_for_etl_claim_submit()`` instead.
            lines = lines.filtered(
                lambda l: l.claim_status not in ('submitted', 'approved')
            )
            lines = lines.filtered(lambda l: l.is_claim_eligible)
            lines = lines.filtered(lambda l: (l.discount or 0) < 100.0)
            lines = lines.filtered(
                lambda l: l.ampath_line_invoice_status == 'to_invoice'
            )
            if not lines:
                raise UserError(_(
                    "No eligible lines for claim preview: complete SHA / visit data, "
                    "date of birth, patient id, intervention codes when applicable, and SHIF "
                    "pre-authorization when the product requires it."
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
        """Generate FHIR claim bundle JSON from selected lines and show it in a dialog."""
        self.ensure_one()
        lines = self._get_selected_lines(action='claim')
        result = lines.action_bulk_fhir_claim()
        lines.write({'selected': False})
        return result

    def action_submit_etl_claim_selected(self):
        """POST **all** qualifying lines to AMPATH ETL (not checkbox selection).

        Includes each product line that is claim-eligible, not waived (discount under 100%),
        not yet manually invoiced (billing status Not Invoiced), and not already submitted.
        """
        self.ensure_one()
        lines = self._order_lines_for_etl_claim_submit()
        if not lines:
            raise UserError(_(
                'No lines to submit: waive (100%% discount) and manually invoiced lines are '
                'excluded. Remaining lines must be claim-eligible and still **Not Invoiced**.'
            ))
        return lines.action_submit_etl_claim()

    def action_submit_claim_selected(self):
        """POST the FHIR bundle to the payer (AfyaLink); on success mark lines Submitted."""
        self.ensure_one()
        lines = self._get_selected_lines(action='claim')
        from odoo.addons.ampath_billing.services.claim_bundle_builder import build_claim_bundle
        from odoo.addons.ampath_billing.services.afyalink_client import (
            claim_submit_indicates_success,
            submit_claim,
        )

        order = self
        pre_id = (order.x_preauth_fhir_claim_id or '').strip() or None
        try:
            bundle, _claim_uuid = build_claim_bundle(order, lines, pre_auth_claim_id=pre_id)
        except ValueError as e:
            raise UserError(str(e)) from e

        body = submit_claim(self.env, bundle)
        if not claim_submit_indicates_success(body):
            detail = (
                json.dumps(body, indent=2, ensure_ascii=False, default=str)
                if isinstance(body, (dict, list))
                else str(body)
            )
            raise UserError(_(
                'The payer reported that the claim was not accepted (success is not true).\n\n'
                'Full response:\n%s'
            ) % detail)

        updated = lines.mark_claim_submitted_from_submit_response(body)
        lines.write({'selected': False})
        return self._action_open_claim_submit_result(len(updated), body)

    def action_invoice_selected(self):
        """Create a partial invoice for the checked lines and open it."""
        self.ensure_one()
        lines = self._get_selected_lines(action='invoice')
        result = lines.action_bulk_invoice()
        lines.write({'selected': False})
        return result

    def action_request_preauth(self):
        """Build the pre-authorization request payload and display it as JSON (no HTTP)."""
        self.ensure_one()
        from odoo.addons.ampath_billing.services.claim_bundle_builder import build_preauth_request_payload

        payload = build_preauth_request_payload(self)
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

    def _create_invoices(self, grouped=False, final=False, date=None):
        """Require on-hand stock for storable products before standard Odoo invoicing."""
        for order in self:
            for line in order.order_line:
                if line.display_type or line.is_downpayment:
                    continue
                qty = getattr(line, 'qty_to_invoice', None)
                if qty is None or qty <= 0:
                    continue
                line._ampath_assert_billable_quantity(qty)
        return super()._create_invoices(
            grouped=grouped, final=final, date=date,
        )
