from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    list_price = fields.Float(string='Sales Fee')
    standard_price = fields.Float(string='Cost')


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    name = fields.Char(string='Fee Schedule')


class ProductCategory(models.Model):
    _inherit = 'product.category'

    name = fields.Char(string='Item Category')
