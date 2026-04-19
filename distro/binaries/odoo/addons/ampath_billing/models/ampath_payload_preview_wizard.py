# -*- coding: utf-8 -*-
from odoo import fields, models


class AmpathPayloadPreviewWizard(models.TransientModel):
    _name = 'ampath.billing.payload.preview'
    _description = 'Preview SHA claim or pre-auth JSON payload'

    sale_order_id = fields.Many2one('sale.order', string='Quotation', required=True, ondelete='cascade')
    title = fields.Char(required=True)
    payload_text = fields.Text(string='JSON', readonly=True)
