from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_id = fields.Many2one(string='Patient')
    invoice_user_id = fields.Many2one(string='Billing Officer')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    product_id = fields.Many2one(string='Item')
    price_unit = fields.Float(string='Unit Fee')
    discount = fields.Float(string='Waiver (%)')
