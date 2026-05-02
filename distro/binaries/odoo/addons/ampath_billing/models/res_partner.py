from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_customer_dob = fields.Date(
        string='Date of birth',
        copy=False,
        help='Patient date of birth for claims (also loaded via initializer on some deployments).',
    )
