# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AmpathVaccinePicking(models.Model):
    _name = 'ampath.vaccine.picking'
    _description = 'Vaccine picking voucher'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Voucher',
        required=True,
        copy=False,
        default='New',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        default='draft',
        required=True,
    )
    movement_type = fields.Selection(
        [
            ('receipt', 'Receipt'),
            ('issue', 'Issue'),
            ('loss', 'Loss'),
        ],
        required=True,
        default='issue',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    vaccine_store_id = fields.Many2one(
        'stock.location',
        string='Vaccine store',
        required=True,
        domain=(
            "[('usage', '=', 'internal'), "
            "('x_ampath_vaccine_store', '=', True), "
            "('company_id', 'in', [company_id, False])]"
        ),
        check_company=True,
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination location',
        domain=(
            "[('usage', '=', 'internal'), "
            "('company_id', 'in', [company_id, False])]"
        ),
        check_company=True,
        help='Required for issues (default MCH).',
    )
    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    source_dest = fields.Char(
        string='Source / Destination',
        help='Ledger text, e.g. "from Divis" or "To MCH".',
    )
    last_order_date = fields.Date(string='Date of last order')
    next_order_date = fields.Date(string='Expected date of next order')
    requisitioning_officer = fields.Char()
    requisitioning_designation = fields.Char()
    issued_by = fields.Char()
    received_by = fields.Char()
    received_designation = fields.Char()
    remarks = fields.Text()
    line_ids = fields.One2many(
        'ampath.vaccine.picking.line',
        'picking_id',
        string='Lines',
    )
    stock_picking_id = fields.Many2one(
        'stock.picking',
        string='Stock picking',
        copy=False,
        readonly=True,
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if not self.company_id:
            return
        self.warehouse_id = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)],
            limit=1,
        )
        self._sync_locations_for_warehouse()

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        self._sync_locations_for_warehouse()

    @api.onchange('movement_type', 'location_dest_id')
    def _onchange_movement_type(self):
        if self.movement_type == 'issue' and self.location_dest_id:
            self.source_dest = 'To %s' % (self.location_dest_id.name or 'MCH')
        elif self.movement_type == 'loss':
            self.source_dest = self.source_dest or 'Losses (Discarded)'
        elif self.movement_type == 'receipt' and not self.source_dest:
            self.source_dest = 'Receipt'

    def _sync_locations_for_warehouse(self):
        self.ensure_one()
        if not self.warehouse_id:
            return
        from odoo.addons.ampath_billing.hooks import (
            ensure_department_locations,
            ensure_vaccine_store_locations,
        )

        ensure_vaccine_store_locations(self.env)
        ensure_department_locations(self.env)
        store = self.env['stock.location'].search(
            [
                ('x_ampath_vaccine_store', '=', True),
                ('company_id', '=', self.warehouse_id.company_id.id),
                ('location_id', 'child_of', self.warehouse_id.view_location_id.id),
            ],
            limit=1,
        )
        if store:
            self.vaccine_store_id = store
        mch = self.env['stock.location'].search(
            [
                ('name', '=', 'MCH'),
                ('usage', '=', 'internal'),
                ('company_id', '=', self.warehouse_id.company_id.id),
                ('location_id', 'child_of', self.warehouse_id.view_location_id.id),
            ],
            limit=1,
        )
        if self.movement_type == 'issue' and mch and not self.location_dest_id:
            self.location_dest_id = mch
            self.source_dest = self.source_dest or 'To MCH'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env['res.company'].browse(
            res.get('company_id') or self.env.company.id
        )
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', company.id)],
            limit=1,
        )
        if warehouse and 'warehouse_id' in fields_list and not res.get('warehouse_id'):
            res['warehouse_id'] = warehouse.id
        if warehouse:
            from odoo.addons.ampath_billing.hooks import (
                ensure_department_locations,
                ensure_vaccine_store_locations,
            )

            ensure_vaccine_store_locations(self.env)
            ensure_department_locations(self.env)
            if 'vaccine_store_id' in fields_list and not res.get('vaccine_store_id'):
                store = self.env['stock.location'].search(
                    [
                        ('x_ampath_vaccine_store', '=', True),
                        ('company_id', '=', company.id),
                        ('location_id', 'child_of', warehouse.view_location_id.id),
                    ],
                    limit=1,
                )
                if store:
                    res['vaccine_store_id'] = store.id
            if (
                res.get('movement_type', 'issue') == 'issue'
                and 'location_dest_id' in fields_list
                and not res.get('location_dest_id')
            ):
                mch = self.env['stock.location'].search(
                    [
                        ('name', '=', 'MCH'),
                        ('usage', '=', 'internal'),
                        ('company_id', '=', company.id),
                        ('location_id', 'child_of', warehouse.view_location_id.id),
                    ],
                    limit=1,
                )
                if mch:
                    res['location_dest_id'] = mch.id
                    if 'source_dest' in fields_list and not res.get('source_dest'):
                        res['source_dest'] = 'To MCH'
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') in (False, 'New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('ampath.vaccine.picking')
                    or 'New'
                )
        return super().create(vals_list)

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Done vouchers cannot be cancelled.'))
            rec.state = 'cancel'
        return True

    def action_validate(self):
        for rec in self:
            rec._validate_vaccine_picking()
        return True

    def _scrap_location(self):
        self.ensure_one()
        scrap = self.warehouse_id.scrap_location_id
        if scrap:
            return scrap
        Location = self.env['stock.location']
        scrap = Location.search(
            [
                ('scrap_location', '=', True),
                ('company_id', 'in', [self.company_id.id, False]),
            ],
            limit=1,
        )
        if not scrap:
            raise UserError(
                _('No scrap location configured for %s.')
                % self.company_id.display_name
            )
        return scrap

    def _validate_vaccine_picking(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft vouchers can be validated.'))
        if not self.line_ids:
            raise UserError(_('Add at least one line.'))
        if not self.vaccine_store_id:
            raise UserError(_('Select a vaccine store location.'))
        warehouse = self.warehouse_id
        store = self.vaccine_store_id
        movement = self.movement_type
        if movement == 'receipt':
            picking_type = warehouse.in_type_id
            # Prefer external transit → vaccine store so MOH 647 does not count B.
            transit = self.env['stock.location'].search(
                [
                    ('company_id', '=', self.company_id.id),
                    ('x_ampath_external_transit', '=', True),
                ],
                limit=1,
            )
            if not transit:
                from odoo.addons.ampath_billing.hooks import (
                    ensure_external_transit_locations,
                )

                ensure_external_transit_locations(self.env)
                transit = self.env['stock.location'].search(
                    [
                        ('company_id', '=', self.company_id.id),
                        ('x_ampath_external_transit', '=', True),
                    ],
                    limit=1,
                )
            if not transit:
                raise UserError(
                    _('No external-facility transit location for %s.')
                    % self.company_id.display_name
                )
            location_id = transit.id
            location_dest_id = store.id
            moh710_flow = 'vaccine_in'
        elif movement == 'issue':
            if not self.location_dest_id:
                raise UserError(_('Select a destination location (e.g. MCH).'))
            if self.location_dest_id.usage != 'internal':
                raise UserError(
                    _('Destination location must be an internal location.')
                )
            picking_type = warehouse.int_type_id or warehouse.out_type_id
            location_id = store.id
            location_dest_id = self.location_dest_id.id
            moh710_flow = 'vaccine_out'
        else:
            picking_type = warehouse.out_type_id
            location_id = store.id
            location_dest_id = self._scrap_location().id
            moh710_flow = 'vaccine_loss'

        lines = []
        for line in self.line_ids:
            if float_compare(line.qty, 0, precision_digits=4) <= 0:
                raise UserError(
                    _('Quantity must be greater than zero on %s.')
                    % (line.product_id.display_name,)
                )
            lot = line.lot_id
            product = line.product_id
            if movement == 'receipt':
                if product.tracking in ('lot', 'serial') and not lot:
                    raise UserError(
                        _('Select a lot for received product %s.')
                        % product.display_name
                    )
            else:
                if product.tracking in ('lot', 'serial') and not lot:
                    lot = self.env['stock.picking']._ampath_pick_fefo_lot(
                        product,
                        warehouse,
                        quantity=line.qty,
                        location=store,
                    )
                    if not lot:
                        raise UserError(
                            _('No in-stock lot for %s at %s.')
                            % (product.display_name, store.display_name)
                        )
                    line.lot_id = lot.id
            lines.append({'product': product, 'quantity': line.qty, 'lot': lot})

        picking = self.env['stock.picking']._ampath_create_and_validate_picking(
            picking_type,
            location_id,
            location_dest_id,
            origin='VP %s' % self.name,
            company=self.company_id,
            lines=lines,
            moh647_flow=False,
            moh710_flow=moh710_flow,
        )
        self.write({'state': 'done', 'stock_picking_id': picking.id})


class AmpathVaccinePickingLine(models.Model):
    _name = 'ampath.vaccine.picking.line'
    _description = 'Vaccine picking line'

    picking_id = fields.Many2one(
        'ampath.vaccine.picking',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        domain=(
            "[('type', '=', 'product'), "
            "'|', ('x_ampath_vaccine', '=', True), "
            "('categ_id.x_ampath_vaccine_category', '=', True)]"
        ),
    )
    default_code = fields.Char(related='product_id.default_code', store=False)
    product_uom_id = fields.Many2one(related='product_id.uom_id', store=False)
    qty = fields.Float(
        string='Amount in doses',
        required=True,
        digits='Product Unit of Measure',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        domain="[('product_id', '=', product_id)]",
    )
    expiry_date = fields.Datetime(
        string='Expiry date',
        compute='_compute_expiry_date',
        store=False,
        readonly=True,
    )
    vvm_stage = fields.Selection(
        [
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4'),
        ],
        string='VVM stage',
    )
    value = fields.Float(compute='_compute_value', store=True)
    remarks = fields.Char()

    @api.depends('lot_id')
    def _compute_expiry_date(self):
        has_expiry = 'expiration_date' in self.env['stock.lot']._fields
        for line in self:
            if has_expiry and line.lot_id:
                line.expiry_date = line.lot_id.expiration_date
            else:
                line.expiry_date = False

    @api.depends('qty', 'product_id', 'product_id.standard_price')
    def _compute_value(self):
        for line in self:
            line.value = (line.qty or 0.0) * (line.product_id.standard_price or 0.0)
