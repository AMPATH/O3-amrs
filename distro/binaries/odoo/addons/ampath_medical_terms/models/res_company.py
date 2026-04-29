from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    name = fields.Char(string='Facility Name')


class ResUsers(models.Model):
    _inherit = 'res.users'

    company_id = fields.Many2one(string='Default Facility')
    company_ids = fields.Many2many(string='Allowed Facilities')


class ResPartnerCompany(models.Model):
    """Relabel the company_id field on res.partner."""
    _inherit = 'res.partner'

    company_id = fields.Many2one(string='Facility')


class SaleOrderCompany(models.Model):
    _inherit = 'sale.order'

    company_id = fields.Many2one(string='Facility')


class AccountMoveCompany(models.Model):
    _inherit = 'account.move'

    company_id = fields.Many2one(string='Facility')


class StockPickingCompany(models.Model):
    _inherit = 'stock.picking'

    company_id = fields.Many2one(string='Facility')


class StockWarehouseCompany(models.Model):
    _inherit = 'stock.warehouse'

    company_id = fields.Many2one(string='Facility')


class ProductTemplateCompany(models.Model):
    _inherit = 'product.template'

    company_id = fields.Many2one(string='Facility')


class PurchaseOrderCompany(models.Model):
    _inherit = 'purchase.order'

    company_id = fields.Many2one(string='Facility')
