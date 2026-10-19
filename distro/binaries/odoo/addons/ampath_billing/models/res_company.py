# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_mfl_code = fields.Char(
        string='Facility MFL Code',
        help='Kenya Master Facility List code for MOH 647 and other facility reports.',
    )
    x_county = fields.Char(string='County')
    x_sub_county = fields.Char(string='Sub County')
