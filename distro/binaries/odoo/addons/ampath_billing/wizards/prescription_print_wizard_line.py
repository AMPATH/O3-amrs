# -*- coding: utf-8 -*-

from odoo import fields, models


class AmpathPrescriptionPrintWizardLine(models.TransientModel):
    _name = 'ampath.prescription.print.wizard.line'
    _description = 'Prescription print line selection'

    wizard_id = fields.Many2one(
        'ampath.prescription.print.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Order line',
        required=True,
    )
    selected = fields.Boolean(string='Print', default=True)
