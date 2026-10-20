# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _ge_code_variants(code):
    """Return catalogue variants for one GE / concept code."""
    if not code:
        return set()
    code = str(code).strip()
    variants = {code}
    upper = code.upper()
    if upper.startswith('GE') and upper[2:].isdigit():
        variants.add(upper)
        variants.add(upper[2:])
    elif code.isdigit():
        variants.add(code)
        variants.add('GE' + code)
    else:
        variants.add(upper)
    return variants


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
        string='Product mapping lines',
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Mapped products',
        compute='_compute_product_ids',
        inverse='_inverse_product_ids',
        store=False,
    )
    related_product_ids = fields.Many2many(
        'product.product',
        string='Related drugs',
        compute='_compute_related_product_ids',
        store=False,
        help='Other catalogue products that share the same HIE GE code as a mapped product. '
             'Updates when new SKUs are synced for that GE.',
    )
    has_related_products = fields.Boolean(
        compute='_compute_related_product_ids',
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

    @api.depends(
        'product_line_ids',
        'product_line_ids.product_id',
        'product_line_ids.product_id.x_concept_code',
    )
    def _compute_related_product_ids(self):
        Product = self.env['product.product']
        for tracer in self:
            mapped = tracer.product_line_ids.mapped('product_id')
            codes = set()
            for product in mapped:
                codes |= _ge_code_variants(product.x_concept_code)
            if not codes:
                tracer.related_product_ids = Product.browse()
                tracer.has_related_products = False
                continue
            related = Product.search(
                [
                    ('x_concept_code', 'in', list(codes)),
                    ('id', 'not in', mapped.ids or [0]),
                ]
            )
            tracer.related_product_ids = related
            tracer.has_related_products = bool(related)

    @api.depends('product_line_ids', 'product_line_ids.product_id')
    def _compute_is_mapped(self):
        for tracer in self:
            tracer.is_mapped = bool(tracer.product_line_ids.filtered('product_id'))

    def action_apply_related_products(self):
        """Map all related GE sibling products onto this tracer (or selection)."""
        Mapping = self.env['ampath.moh647.tracer.product']
        added = 0
        for tracer in self:
            # Recompute to pick up newly synced catalogue SKUs
            tracer._compute_related_product_ids()
            related = tracer.related_product_ids
            if not related:
                continue
            existing = set(tracer.product_line_ids.mapped('product_id').ids)
            for product in related:
                if product.id in existing:
                    continue
                Mapping.create(
                    {
                        'tracer_id': tracer.id,
                        'product_id': product.id,
                    }
                )
                existing.add(product.id)
                added += 1
        if not added:
            raise UserError(
                _(
                    'No related drugs to apply. Map at least one product that has a '
                    'GE / concept code (x_concept_code), then try again.'
                )
            )
        return True

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
