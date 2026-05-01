from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    partner_id = fields.Many2one(string='Supplier')
    order_line = fields.One2many(string='Item Lines')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_id = fields.Many2one(string='Item')
    price_unit = fields.Float(string='Unit Fee')
