import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)

# Lines in these claim states are paid via insurance, not on the patient cash invoice.
_CLAIM_EXCLUDE_FROM_CUSTOMER_INVOICE = frozenset({'submitted', 'approved'})


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    claim_status = fields.Selection([
        ('draft', 'Not Claimed'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='draft', string="Claim status", copy=False)

    insurance_provider_id = fields.Many2one('res.partner', string="Insurance Payer")
    fhir_claim_id = fields.Char("FHIR ID", copy=False)
    ampath_prescription_printed = fields.Boolean(
        string='Prescription printed',
        default=False,
        copy=False,
        help=(
            'Set when this line is included on a prescription PDF. '
            'It is excluded from customer invoices, from the understock '
            'invoice block until you clear the hold, and from warehouse '
            'deliveries until the hold is cleared.'
        ),
    )
    billing_actions_visible = fields.Boolean(
        related='order_id.billing_actions_visible',
    )
    selected = fields.Boolean(string="✓", default=False, copy=False)

    ampath_line_invoice_status = fields.Selection([
        ('to_invoice', 'Not Invoiced'),
        ('on_claim', 'On insurance claim'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
    ], compute='_compute_ampath_line_invoice_status',
       string="Billing Status",
       store=True,
    )

    invoice_indicator = fields.Char(
        compute='_compute_invoice_indicator',
        string="Inv.",
        help="✅ paid  |  📄 invoiced  |  🏥 on insurance claim  |  blank = cash not yet invoiced",
    )

    is_line_locked = fields.Boolean(
        compute='_compute_is_line_locked',
        string="Locked",
        help="True when the line's invoice has been paid.",
    )

    is_preauth_eligible = fields.Boolean(
        compute='_compute_is_preauth_eligible',
        string='Pre-auth eligible',
        help='Line has an intervention code and still needs SHA pre-authorization on the order.',
    )
    is_claim_eligible = fields.Boolean(
        compute='_compute_is_claim_eligible',
        string='PHC claim eligible',
        help='Eligible to submit as a PHC (SHA) claim for payment instead of cash: patient id '
             'and DOB set; intervention-code products also require approved pre-authorization.',
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
    x_service_category = fields.Char(
        string="Service category (claim)",
        copy=False,
        help="Optional category sent per service line in pre-auth payloads.",
    )
    x_preauth_fhir_claim_id = fields.Char(
        string="Pre-auth FHIR Claim id (line)",
        copy=False,
        help="If set, included as preAuthFhirClaimId for this service line.",
    )
    x_openmrs_order_id = fields.Char(
        string="OpenMRS order UUID",
        copy=False,
        help='Drug/order UUID from OpenMRS; EIP sets this when syncing lines.',
    )

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    def _ampath_excluded_from_customer_invoice(self):
        """True when this line is settled via an insurance claim, not patient cash invoice."""
        self.ensure_one()
        return self.claim_status in _CLAIM_EXCLUDE_FROM_CUSTOMER_INVOICE

    def _ampath_line_has_claim_patient_data(self):
        """Patient id + DOB present on order or partner (shared by pre-auth and PHC claim)."""
        self.ensure_one()
        order = self.order_id
        patient = (
            (order.x_sha_client_registry_id or '').strip()
            or (getattr(order, 'x_patient_uuid', None) or '').strip()
            or (getattr(order, 'x_external_identifier', None) or '').strip()
        )
        if not patient:
            return False
        return bool(
            getattr(order, 'x_customer_dob', None)
            or (order.partner_id and getattr(order.partner_id, 'x_customer_dob', None))
        )

    @api.depends(
        'display_type',
        'is_downpayment',
        'claim_status',
        'product_id.x_intervention_code',
        'order_id.x_patient_uuid',
        'order_id.x_external_identifier',
        'order_id.x_sha_client_registry_id',
        'order_id.x_preauth_status',
        'order_id.x_customer_dob',
        'order_id.partner_id.x_customer_dob',
    )
    def _compute_is_preauth_eligible(self):
        from odoo.addons.ampath_billing.services.claim_bundle_builder import (
            line_requires_sha_intervention_code,
        )

        approved_preauth = frozenset({
            'approved', 'authorized', 'authorisation', 'success', 'active',
        })
        for line in self:
            if line.display_type or line.is_downpayment:
                line.is_preauth_eligible = False
                continue
            if line.claim_status in ('submitted', 'approved'):
                line.is_preauth_eligible = False
                continue
            if not line_requires_sha_intervention_code(line):
                line.is_preauth_eligible = False
                continue
            if not line._ampath_line_has_claim_patient_data():
                line.is_preauth_eligible = False
                continue
            pre = (line.order_id.x_preauth_status or '').strip().lower()
            line.is_preauth_eligible = pre not in approved_preauth

    @api.depends(
        'display_type',
        'is_downpayment',
        'claim_status',
        'product_id.x_intervention_code',
        'order_id.x_patient_uuid',
        'order_id.x_external_identifier',
        'order_id.x_sha_client_registry_id',
        'order_id.x_preauth_status',
        'order_id.x_customer_dob',
        'order_id.partner_id.x_customer_dob',
    )
    def _compute_is_claim_eligible(self):
        from odoo.addons.ampath_billing.services.claim_bundle_builder import (
            line_requires_sha_intervention_code,
        )

        approved_preauth = frozenset({
            'approved', 'authorized', 'authorisation', 'success', 'active',
        })
        for line in self:
            if line.display_type or line.is_downpayment:
                line.is_claim_eligible = False
                continue
            if line.claim_status in ('submitted', 'approved'):
                line.is_claim_eligible = False
                continue
            if not line._ampath_line_has_claim_patient_data():
                line.is_claim_eligible = False
                continue
            if line_requires_sha_intervention_code(line):
                pre = (line.order_id.x_preauth_status or '').strip().lower()
                line.is_claim_eligible = pre in approved_preauth
            else:
                line.is_claim_eligible = True

    @api.depends(
        'invoice_lines.move_id.state',
        'invoice_lines.move_id.payment_state',
        'invoice_lines.move_id.move_type',
        'claim_status',
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
            if not posted and line._ampath_excluded_from_customer_invoice():
                line.ampath_line_invoice_status = 'on_claim'
                continue
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
        icons = {
            'paid': '✅',
            'invoiced': '📄',
            'on_claim': '🏥',
            'to_invoice': '',
        }
        for line in self:
            line.invoice_indicator = icons.get(
                line.ampath_line_invoice_status, ''
            )

    def _compute_qty_to_invoice(self):
        super()._compute_qty_to_invoice()
        for line in self.filtered(
            lambda l: l._ampath_excluded_from_customer_invoice()
            and not l.display_type
            and not l.is_downpayment
        ):
            line.qty_to_invoice = 0.0

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

    def _ampath_cancel_prescription_delivery_moves(self):
        """Cancel open fulfillment moves so the line disappears from delivery pickings."""
        for line in self:
            moves = line.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')
                and not m.scrapped
                and m.product_id == line.product_id
                and not (m.location_id.usage == 'customer' and m.to_refund)
            )
            if moves:
                moves._action_cancel()

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
        prev_presc = None
        if 'ampath_prescription_printed' in vals:
            prev_presc = {line.id: line.ampath_prescription_printed for line in self}
        res = super().write(vals)
        if prev_presc is not None:
            new_val = vals['ampath_prescription_printed']
            to_relaunch = self.env['sale.order.line']
            for line in self:
                old_val = prev_presc.get(line.id, False)
                if new_val and not old_val:
                    line._ampath_cancel_prescription_delivery_moves()
                elif not new_val and old_val and line.state == 'sale':
                    to_relaunch |= line
            if to_relaunch:
                to_relaunch._action_launch_stock_rule()
        return res

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Do not create or extend pickings for lines on prescription hold."""
        to_procure = self.filtered(lambda l: not l.ampath_prescription_printed)
        if not to_procure:
            return True
        prev = previous_product_uom_qty
        if prev:
            prev = {k: v for k, v in prev.items() if k in to_procure.ids}
            if not prev:
                prev = False
        return super(SaleOrderLine, to_procure)._action_launch_stock_rule(
            previous_product_uom_qty=prev
        )

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
    # Stock checks (storable products only; services / consumables skipped)
    # ------------------------------------------------------------------

    def _ampath_requires_stock_for_billing(self):
        """True when this line's product is storable (inventory must exist to bill/claim)."""
        self.ensure_one()
        product = self.product_id
        if not product:
            return False
        # Odoo 17+: is_storable distinguishes stocked goods (including tracked consumables).
        if 'is_storable' in product._fields:
            return bool(product.is_storable)
        # Older: only stockable type 'product' is constrained; service/consu skip.
        if product.type in ('service', 'consu'):
            return False
        return product.type == 'product'

    def _ampath_available_qty_product_uom(self):
        """On-hand (or free) qty for this product in the order warehouse context."""
        self.ensure_one()
        product = self.product_id
        order = self.order_id
        ctx = {}
        wh = order.warehouse_id
        if wh:
            ctx['warehouse'] = wh.id
        prod = product.with_context(**ctx)
        if 'free_qty' in prod._fields:
            return prod.free_qty
        return prod.qty_available

    def _ampath_stock_shortage_message(self, qty_in_line_uom):
        """Return a human-readable error fragment if storable stock is insufficient."""
        self.ensure_one()
        if self.display_type or self.is_downpayment:
            return None
        if not self._ampath_requires_stock_for_billing():
            return None
        product = self.product_id
        avail = self._ampath_available_qty_product_uom()
        needed = self.product_uom._compute_quantity(
            qty_in_line_uom,
            product.uom_id,
            rounding_method='HALF-UP',
        )
        prec = product.uom_id.rounding
        if float_compare(avail, needed, precision_rounding=prec) >= 0:
            return None
        wh = self.order_id.warehouse_id
        return _(
            '%(product)s: need %(need)s %(uom)s, available %(avail)s %(uom)s (warehouse: %(wh)s)'
        ) % {
            'product': product.display_name,
            'need': needed,
            'avail': avail,
            'uom': product.uom_id.name or '',
            'wh': wh.display_name if wh else _('N/A'),
        }

    def _ampath_assert_billable_quantity(self, qty_in_line_uom):
        """Block invoicing/claiming when storable qty is insufficient."""
        msg = self._ampath_stock_shortage_message(qty_in_line_uom)
        if msg:
            raise UserError(
                _('Cannot invoice or claim — insufficient stock:\n• %s') % msg
            )

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------

    def action_bulk_waive(self):
        """Apply 100% discount to selected lines."""
        for line in self:
            line.write({'discount': 100.0})

    def _ampath_claim_lines_common(self):
        """Validate PHC claim lines for ETL submit (no warehouse stock requirement)."""
        lines = self.filtered(lambda l: not l.display_type and not l.is_downpayment)
        if not lines:
            raise UserError(_("No billable lines selected for claim actions."))
        orders = lines.mapped('order_id')
        if len(orders) > 1:
            raise UserError(_("Please select lines from a single order at a time."))
        order = orders[0]
        ineligible = lines.filtered(lambda l: not l.is_claim_eligible)
        if ineligible:
            names = ', '.join(ineligible.mapped('product_id.display_name')[:8])
            raise UserError(_(
                'These lines are not PHC claim eligible: %(names)s. Check patient id and date '
                'of birth on the order; use Preauth and set visit pre-authorization to approved '
                'when the product has an intervention code.',
            ) % {'names': names})
        skipped = lines - order._ampath_lines_skip_for_stock_and_rx(lines)
        lines = order._ampath_lines_skip_for_stock_and_rx(lines)
        if not lines:
            raise UserError(_(
                'No lines to claim: rows may be on prescription hold or out of stock. '
                'Use "Print prescription" for understock medications; service lines should '
                'still submit if PHC claim eligible.'
            ))
        if skipped:
            _logger.info(
                'Claim submit skipped %s line(s) on order %s (Rx hold or understock): %s',
                len(skipped),
                order.name,
                ', '.join(skipped.mapped('product_id.display_name')[:8]),
            )
        return order, lines

    def action_submit_etl_claim(self):
        """POST BuildClaimBundleRequest-shaped JSON to AMPATH ETL (env / system params)."""
        order, lines = self._ampath_claim_lines_common()
        env = self.env
        from odoo.addons.ampath_billing.services import afyalink_client

        if not afyalink_client.etl_submit_url_configured(env):
            raise UserError(_(
                'AMPATH ETL submit URL is not configured. Set ir.config_parameter '
                '"ampath.etl_claims.submit_url" or environment variable '
                '"AMPATH_ETL_CLAIMS_SUBMIT_URL", and "AMPATH_ETL_CLAIMS_API_KEY" '
                '(or parameter ampath.etl_claims.api_key).'
            ))

        from odoo.addons.ampath_billing.services.claim_bundle_builder import build_preauth_request_payload

        payload = build_preauth_request_payload(order, lines)
        try:
            body = afyalink_client.submit_etl_hie_claim(env, payload)
        except UserError:
            raise
        except Exception as e:
            _logger.exception('ETL claim submit error')
            raise UserError(str(e)) from e

        ext_id = afyalink_client.etl_claim_external_id_from_response(body)
        line_vals = {'claim_status': 'submitted', 'selected': False}
        if ext_id:
            line_vals['fhir_claim_id'] = ext_id
        lines.write(line_vals)
        return order._action_open_claim_submit_result(body, submitted_lines=lines)

    def mark_claim_submitted_from_submit_response(self, submit_body):
        """After a successful payer POST, set *Submitted* and optional ``fhir_claim_id``."""
        from odoo.addons.ampath_billing.services.afyalink_client import claim_id_from_submit_response

        lines = self.filtered(lambda l: not l.display_type and not l.is_downpayment)
        lines = lines.filtered(lambda l: l.claim_status != 'approved')
        if not lines:
            return self.browse()
        vals = {'claim_status': 'submitted'}
        cid = claim_id_from_submit_response(submit_body) if submit_body is not None else None
        if cid:
            vals['fhir_claim_id'] = cid
        lines.write(vals)
        return lines

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
        lines_to_bill = self.filtered(lambda l: not l.display_type and not l.is_downpayment)
        held = lines_to_bill.filtered('ampath_prescription_printed')
        if held:
            raise UserError(_(
                'These lines are on prescription hold and cannot be invoiced until you use '
                '"Clear prescription hold" on the order: %s'
            ) % ', '.join(held.mapped('product_id.display_name')[:12]))

        on_claim = lines_to_bill.filtered(
            lambda l: l._ampath_excluded_from_customer_invoice()
        )
        lines_to_bill = lines_to_bill - on_claim
        if on_claim and not lines_to_bill:
            raise UserError(_(
                'Selected lines were submitted as insurance claims and are not billed on '
                'the patient invoice: %s'
            ) % ', '.join(on_claim.mapped('product_id.display_name')[:12]))

        understock = order._ampath_understock_invoiceable_lines()
        skipped_understock = lines_to_bill & understock
        lines_to_bill = lines_to_bill - skipped_understock
        if skipped_understock and not lines_to_bill:
            raise UserError(_(
                'Selected lines have insufficient stock. Use "Print prescription" for those '
                'medications (they are held off invoices and deliveries), or select other lines.'
            ))
        for line in lines_to_bill:
            line._ampath_assert_billable_quantity(line.product_uom_qty)

        invoice_vals = order._prepare_invoice()
        invoice_line_vals_list = []

        for line in lines_to_bill:
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
