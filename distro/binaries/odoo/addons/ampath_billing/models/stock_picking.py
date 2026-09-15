# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_grn_number = fields.Char(
        string='Goods Receipt Note Number',
        copy=False,
        help='Goods Receipt Note number from the supplier documents.',
    )
    x_delivery_number = fields.Char(
        string='Delivery Number',
        copy=False,
        help='Delivery note / waybill number from the transporter.',
    )
    x_delivery_driver = fields.Char(
        string='Delivery Driver',
        copy=False,
        help='Name of the delivery driver who brought the goods.',
    )
    x_grn_document_ids = fields.Many2many(
        'ir.attachment',
        'stock_picking_grn_document_rel',
        'picking_id',
        'attachment_id',
        string='Goods Receipt Note Documents',
        copy=False,
        help='Supporting documents for this goods receipt (invoice, delivery note, etc.).',
    )

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._link_grn_attachments()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if 'x_grn_document_ids' in vals:
            self._link_grn_attachments()
        return res

    def _link_grn_attachments(self):
        """Point uploaded GRN files at this picking so they appear in chatter/attachments."""
        for picking in self:
            attachments = picking.x_grn_document_ids.filtered(
                lambda a: a.res_model != 'stock.picking' or a.res_id != picking.id
            )
            if attachments:
                attachments.write({'res_model': 'stock.picking', 'res_id': picking.id})
