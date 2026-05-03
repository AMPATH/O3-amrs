from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_concept_source = fields.Selection(
        selection=[('local', 'Local')],
        string='Concept Source',
        compute='_compute_x_concept_source',
        inverse='_set_x_concept_source',
        help='Stored on the product variant; shown here when the template has a single variant.',
    )
    x_concept_code = fields.Char(
        string='Concept Code',
        compute='_compute_x_concept_code',
        inverse='_set_x_concept_code',
        help='Stored on the product variant; shown here when the template has a single variant.',
    )
    x_drug_strength = fields.Char(
        string='Drug Strength',
        compute='_compute_x_drug_strength',
        inverse='_set_x_drug_strength',
        help='Stored on the product variant; shown here when the template has a single variant.',
    )
    x_openmrs_drug_uuid = fields.Char(
        string='OpenMRS drug UUID',
        compute='_compute_x_openmrs_drug_uuid',
        inverse='_set_x_openmrs_drug_uuid',
        help='Stored on the product variant; OpenMRS Drug resource uuid.',
    )
    x_intervention_code = fields.Char(
        string='Intervention code',
        compute='_compute_x_intervention_code',
        inverse='_set_x_intervention_code',
        help='Stored on the product variant; shown here when the template has a single variant.',
    )

    @api.depends('product_variant_ids.x_concept_source')
    def _compute_x_concept_source(self):
        self._compute_template_field_from_variant_field('x_concept_source')

    def _set_x_concept_source(self):
        self._set_product_variant_field('x_concept_source')

    @api.depends('product_variant_ids.x_concept_code')
    def _compute_x_concept_code(self):
        self._compute_template_field_from_variant_field('x_concept_code')

    def _set_x_concept_code(self):
        self._set_product_variant_field('x_concept_code')

    @api.depends('product_variant_ids.x_drug_strength')
    def _compute_x_drug_strength(self):
        self._compute_template_field_from_variant_field('x_drug_strength')

    def _set_x_drug_strength(self):
        self._set_product_variant_field('x_drug_strength')

    @api.depends('product_variant_ids.x_openmrs_drug_uuid')
    def _compute_x_openmrs_drug_uuid(self):
        self._compute_template_field_from_variant_field('x_openmrs_drug_uuid')

    def _set_x_openmrs_drug_uuid(self):
        self._set_product_variant_field('x_openmrs_drug_uuid')

    @api.depends('product_variant_ids.x_intervention_code')
    def _compute_x_intervention_code(self):
        self._compute_template_field_from_variant_field('x_intervention_code')

    def _set_x_intervention_code(self):
        self._set_product_variant_field('x_intervention_code')
