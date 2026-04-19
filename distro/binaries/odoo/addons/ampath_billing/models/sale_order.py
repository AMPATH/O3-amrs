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
        'May be populated by EIP from OpenMRS FHIR Condition.',
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
                    "No eligible lines for claim preview: complete SHA / visit data, "
                    "diagnoses, intervention codes, date of birth, and SHIF pre-authorization when applicable."
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
