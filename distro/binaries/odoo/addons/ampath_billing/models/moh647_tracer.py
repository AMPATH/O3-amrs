# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AmpathMoh647Tracer(models.Model):
    _name = 'ampath.moh647.tracer'
    _description = 'MOH 647 Facility Tracer HPT'
    _order = 'sequence, id'

    sequence = fields.Integer(required=True, index=True)
    section = fields.Selection(
        [
            ('medicines', 'Medicines'),
            ('medical_supplies', 'Medical Supplies'),
            ('radiology', 'Radiology'),
            ('lab', 'Medical Laboratory / Diagnostic Reagents & Consumables'),
            ('nutrition', 'Nutrition'),
        ],
        required=True,
        index=True,
    )
    name = fields.Char(string='INN / Tracer name', required=True)
    unit_of_issue = fields.Char(string='Unit of Issue', required=True)
    active = fields.Boolean(default=True)
    product_line_ids = fields.One2many(
        'ampath.moh647.tracer.product',
        'tracer_id',
        string='Mapped products',
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Mapped products',
        compute='_compute_product_ids',
        inverse='_inverse_product_ids',
        store=False,
    )
    is_mapped = fields.Boolean(compute='_compute_is_mapped', store=True)

    _sql_constraints = [
        (
            'ampath_moh647_tracer_sequence_uniq',
            'unique(sequence)',
            'MOH 647 tracer sequence must be unique.',
        ),
    ]

    @api.depends('product_line_ids', 'product_line_ids.product_id')
    def _compute_product_ids(self):
        for tracer in self:
            tracer.product_ids = tracer.product_line_ids.mapped('product_id')

    def _inverse_product_ids(self):
        Mapping = self.env['ampath.moh647.tracer.product']
        for tracer in self:
            current = tracer.product_line_ids.mapped('product_id')
            to_add = tracer.product_ids - current
            to_remove = current - tracer.product_ids
            if to_remove:
                tracer.product_line_ids.filtered(
                    lambda line: line.product_id in to_remove
                ).unlink()
            for product in to_add:
                Mapping.create(
                    {
                        'tracer_id': tracer.id,
                        'product_id': product.id,
                    }
                )

    @api.depends('product_line_ids', 'product_line_ids.product_id')
    def _compute_is_mapped(self):
        for tracer in self:
            tracer.is_mapped = bool(tracer.product_line_ids.filtered('product_id'))

    def name_get(self):
        result = []
        for tracer in self:
            label = '%s. %s' % (tracer.sequence, tracer.name)
            result.append((tracer.id, label))
        return result


class AmpathMoh647TracerProduct(models.Model):
    _name = 'ampath.moh647.tracer.product'
    _description = 'MOH 647 Tracer Product Mapping'
    _order = 'id'

    tracer_id = fields.Many2one(
        'ampath.moh647.tracer',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='restrict',
        index=True,
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Report UoM override',
        help='Optional unit for report quantities; defaults to the product UoM.',
    )

    _sql_constraints = [
        (
            'ampath_moh647_tracer_product_uniq',
            'unique(tracer_id, product_id)',
            'A product can only be mapped once per tracer.',
        ),
    ]
