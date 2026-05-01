from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_rank = fields.Integer(string='Patient Rank')
    user_id = fields.Many2one(string='Billing Officer')
    team_id = fields.Many2one(string='Billing Team')
