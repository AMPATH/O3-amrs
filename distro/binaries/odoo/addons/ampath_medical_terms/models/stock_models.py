from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    name = fields.Char(string='Medical Store Name')


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    partner_id = fields.Many2one(string='Patient')


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    product_id = fields.Many2one(string='Item')
    lot_id = fields.Many2one(string='Batch/Serial Number')


class StockLot(models.Model):
    _inherit = 'stock.lot'

    name = fields.Char(string='Batch/Serial Number')


class StockMove(models.Model):
    _inherit = 'stock.move'

    product_id = fields.Many2one(string='Item')


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    product_id = fields.Many2one(string='Item')
    lot_id = fields.Many2one(string='Batch/Serial Number')
    lot_name = fields.Char(string='Batch/Serial Number')


class StockOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    product_id = fields.Many2one(string='Item')
    warehouse_id = fields.Many2one(string='Medical Store')
