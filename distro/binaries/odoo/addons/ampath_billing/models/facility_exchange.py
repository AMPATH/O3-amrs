# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AmpathExternalFacility(models.Model):
    _name = 'ampath.external.facility'
    _description = 'Other health facility'
    _order = 'name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Odoo company',
        help='Set when this site is also an AMPATH Odoo company.',
    )
    active = fields.Boolean(default=True)


class AmpathFacilityExchange(models.Model):
    _name = 'ampath.facility.exchange'
    _description = 'Inter-facility receipt or issue'
    _order = 'date desc, id desc'

    name = fields.Char(
        required=True,
        copy=False,
        default='New',
    )
    exchange_type = fields.Selection(
        [
            ('receipt', 'Receipt from other facility (E)'),
            ('issue', 'Issue to other facility (F)'),
        ],
        required=True,
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
    facility_id = fields.Many2one(
        'ampath.external.facility',
        string='Other facility',
        required=True,
    )
    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    reference = fields.Char()
    remarks = fields.Text()
    line_ids = fields.One2many(
        'ampath.facility.exchange.line',
        'exchange_id',
        string='Lines',
    )
    picking_id = fields.Many2one('stock.picking', copy=False, readonly=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self.warehouse_id = self.env['stock.warehouse'].search(
                [('company_id', '=', self.company_id.id)],
                limit=1,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') in (False, 'New'):
                code = (
                    'ampath.facility.exchange.receipt'
                    if vals.get('exchange_type') == 'receipt'
                    else 'ampath.facility.exchange.issue'
                )
                vals['name'] = self.env['ir.sequence'].next_by_code(code) or 'New'
        return super().create(vals_list)

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                raise UserError(_('Done documents cannot be cancelled.'))
            rec.state = 'cancel'
        return True

    def action_validate(self):
        for rec in self:
            rec._validate_exchange()
        return True

    def _external_transit_location(self):
        self.ensure_one()
        Location = self.env['stock.location']
        loc = Location.search(
            [
                ('company_id', '=', self.company_id.id),
                ('x_ampath_external_transit', '=', True),
            ],
            limit=1,
        )
        if loc:
            return loc
        from odoo.addons.ampath_billing.hooks import ensure_external_transit_locations

        ensure_external_transit_locations(self.env)
        loc = Location.search(
            [
                ('company_id', '=', self.company_id.id),
                ('x_ampath_external_transit', '=', True),
            ],
            limit=1,
        )
        if not loc:
            raise UserError(
                _('No external-facility transit location for %s.')
                % self.company_id.display_name
            )
        return loc

    def _validate_exchange(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft documents can be validated.'))
        if not self.line_ids:
            raise UserError(_('Add at least one line.'))
        warehouse = self.warehouse_id
        transit = self._external_transit_location()
        is_receipt = self.exchange_type == 'receipt'
        picking_type = warehouse.in_type_id if is_receipt else warehouse.out_type_id
        stock_loc = warehouse.lot_stock_id
        if is_receipt:
            location_id = transit.id
            location_dest_id = (
                picking_type.default_location_dest_id.id or stock_loc.id
            )
            moh647_flow = 'external_in'
        else:
            location_id = picking_type.default_location_src_id.id or stock_loc.id
            location_dest_id = transit.id
            moh647_flow = 'external_out'
        lines = []
        for line in self.line_ids:
            if float_compare(line.qty, 0, precision_digits=4) <= 0:
                raise UserError(
                    _('Quantity must be greater than zero on %s.')
                    % (line.product_id.display_name,)
                )
            lot = line.lot_id
            product = line.product_id
            if (
                not is_receipt
                and product.tracking in ('lot', 'serial')
                and not lot
            ):
                lot = self.env['stock.picking']._ampath_pick_fefo_lot(
                    product, warehouse, quantity=line.qty
                )
                if not lot:
                    raise UserError(
                        _('No in-stock lot for %s at %s.')
                        % (product.display_name, warehouse.display_name)
                    )
                line.lot_id = lot.id
            if is_receipt and product.tracking in ('lot', 'serial') and not lot:
                raise UserError(
                    _('Select a lot for received product %s.')
                    % product.display_name
                )
            lines.append({'product': product, 'quantity': line.qty, 'lot': lot})
        picking = self.env['stock.picking']._ampath_create_and_validate_picking(
            picking_type,
            location_id,
            location_dest_id,
            origin='%s %s' % (self.name, self.facility_id.name),
            company=self.company_id,
            lines=lines,
            moh647_flow=moh647_flow,
        )
        self.write({'state': 'done', 'picking_id': picking.id})


class AmpathFacilityExchangeLine(models.Model):
    _name = 'ampath.facility.exchange.line'
    _description = 'Inter-facility exchange line'

    exchange_id = fields.Many2one(
        'ampath.facility.exchange',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        domain="[('type', '=', 'product')]",
    )
    default_code = fields.Char(related='product_id.default_code', store=False)
    product_uom_id = fields.Many2one(related='product_id.uom_id', store=False)
    qty = fields.Float(
        string='Quantity',
        required=True,
        digits='Product Unit of Measure',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        domain="[('product_id', '=', product_id)]",
    )
    value = fields.Float(compute='_compute_value', store=True)
    remarks = fields.Char()

    @api.depends('qty', 'product_id', 'product_id.standard_price')
    def _compute_value(self):
        for line in self:
            line.value = (line.qty or 0.0) * (line.product_id.standard_price or 0.0)
