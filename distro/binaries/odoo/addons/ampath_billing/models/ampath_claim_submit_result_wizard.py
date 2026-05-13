# -*- coding: utf-8 -*-
from odoo import fields, models


class AmpathClaimSubmitResultWizard(models.TransientModel):
    _name = 'ampath.billing.claim.submit.result'
    _description = 'Claim submission outcome (summary + full payer response)'

    sale_order_id = fields.Many2one('sale.order', string='Order', required=True, ondelete='cascade')
    headline = fields.Char(string='Summary', readonly=True)
    response_full = fields.Text(string='Full response from payer', readonly=True)
