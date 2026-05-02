from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_concept_source = fields.Selection(
        selection=[('local', 'Local')],
        string='Concept Source',
        copy=False,
        help='Open Concept Lab source key for this product/variant.',
    )
    x_concept_code = fields.Char(
        string='Concept Code',
        copy=False,
        help='Open Concept Lab concept code.',
    )
    x_drug_strength = fields.Char(
        string='Drug Strength',
        copy=False,
        help='Medication strength representation.',
    )
    x_intervention_code = fields.Char(
        string='Intervention code',
        copy=False,
        help='DHA / SHA catalogue code. Pre-authorization applies when this field is non-empty. '
             'Leave empty so the product stays on the PHC path.',
    )
