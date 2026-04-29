from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_id = fields.Many2one(string='Patient')
    user_id = fields.Many2one(string='Billing Officer')
    team_id = fields.Many2one(string='Billing Team')
    pricelist_id = fields.Many2one(string='Fee Schedule')
    order_line = fields.One2many(string='Service Lines')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_id = fields.Many2one(string='Item')
    product_template_id = fields.Many2one(string='Item')
    price_unit = fields.Float(string='Unit Fee')
    discount = fields.Float(string='Waiver (%)')
