# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_grn_number = fields.Char(
        string='Goods Receipt Note Number',
        copy=False,
        help='Goods Receipt Note number from the supplier documents.',
    )
    x_delivery_number = fields.Char(
        string='Delivery Number',
        copy=False,
        help='Delivery note / waybill number from the transporter.',
    )
    x_delivery_driver = fields.Char(
        string='Delivery Driver',
        copy=False,
        help='Name of the delivery driver who brought the goods.',
    )
    x_grn_document_ids = fields.Many2many(
        'ir.attachment',
        'stock_picking_grn_document_rel',
        'picking_id',
        'attachment_id',
        string='Goods Receipt Note Documents',
        copy=False,
        help='Supporting documents for this goods receipt (invoice, delivery note, etc.).',
    )
    x_moh647_flow = fields.Selection(
        [
            ('external_in', 'External receipt (E)'),
            ('external_out', 'External issue (F)'),
        ],
        string='MOH 647 flow',
        copy=False,
        help='When set, MOH 647 counts this picking as E or F instead of B or C.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._link_grn_attachments()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if 'x_grn_document_ids' in vals:
            self._link_grn_attachments()
        return res

    def _link_grn_attachments(self):
        """Point uploaded GRN files at this picking so they appear in chatter/attachments."""
        for picking in self:
            attachments = picking.x_grn_document_ids.filtered(
                lambda a: a.res_model != 'stock.picking' or a.res_id != picking.id
            )
            if attachments:
                attachments.write({'res_model': 'stock.picking', 'res_id': picking.id})

    def button_validate(self):
        internals = self.filtered(lambda p: p.picking_type_code == 'internal')
        if internals:
            internals._ampath_prepare_internal_lot_validate()
        return super().button_validate()

    def _ampath_prepare_internal_lot_validate(self):
        """Reserve existing lots before Odoo copies Demand onto Quantity without lot_id."""
        for picking in self:
            picking._ampath_rewrite_view_destinations()
            if picking.state == 'draft':
                picking.action_confirm()
            lot_moves = picking.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')
                and m.product_id.tracking in ('lot', 'serial')
                and not m.move_line_ids.filtered('lot_id')
            )
            for move in lot_moves:
                move.quantity = 0
                if 'picked' in move._fields:
                    move.picked = False
            if lot_moves:
                picking.action_assign()
            still = picking.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')
                and m.product_id.tracking in ('lot', 'serial')
                and not m.move_line_ids.filtered('lot_id')
            )
            still._ampath_fill_lots_from_quants()
            picking._ampath_raise_if_missing_lots()
            # Odoo 17 Validate only completes moves flagged as picked.
            for move in picking.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')
                and m.move_line_ids.filtered(lambda ml: ml.lot_id and ml.quantity)
            ):
                if 'picked' in move._fields:
                    move.picked = True

    def _ampath_rewrite_view_destinations(self):
        self.ensure_one()
        dest = self._ampath_internal_stock_location(self.location_dest_id)
        if dest != self.location_dest_id:
            self.location_dest_id = dest
            self.move_ids.filtered(
                lambda m: m.state not in ('done', 'cancel')
            ).location_dest_id = dest
            self.move_line_ids.filtered(
                lambda ml: ml.state not in ('done', 'cancel')
            ).location_dest_id = dest

    def _ampath_internal_stock_location(self, location):
        if not location or location.usage != 'view':
            return location
        Location = self.env['stock.location']
        children = Location.search(
            [
                ('id', 'child_of', location.id),
                ('id', '!=', location.id),
                ('usage', '=', 'internal'),
            ]
        )
        named = children.filtered(lambda loc: 'stock' in (loc.name or '').lower())
        return named[:1] or children[:1] or location

    def _ampath_raise_if_missing_lots(self):
        self.ensure_one()
        missing = []
        for move in self.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id.tracking in ('lot', 'serial')
        ):
            if move.move_line_ids.filtered('lot_id'):
                continue
            batches = self._ampath_onhand_batch_summary(move)
            missing.append(
                _(
                    '%(product)s at %(location)s (on-hand batches: %(batches)s)'
                )
                % {
                    'product': move.product_id.display_name,
                    'location': move.location_id.display_name,
                    'batches': batches,
                }
            )
        if missing:
            raise UserError(
                _('No batch could be reserved for:\n- %s') % '\n- '.join(missing)
            )

    def _ampath_onhand_batch_summary(self, move):
        Quant = self.env['stock.quant']
        quants = Quant.search(
            [
                ('product_id', '=', move.product_id.id),
                ('location_id', 'child_of', move.location_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ]
        )
        parts = []
        for quant in quants:
            available = quant.quantity - quant.reserved_quantity
            if available > 0:
                parts.append('%s (%s)' % (quant.lot_id.name, available))
        return ', '.join(parts[:8]) if parts else _('none')

    def _ampath_set_move_line_qty(self, move_line, quantity):
        if 'quantity' in move_line._fields:
            move_line.quantity = quantity
        elif 'qty_done' in move_line._fields:
            move_line.qty_done = quantity

    def _ampath_set_move_qty(self, move, quantity):
        if 'quantity' in move._fields:
            move.quantity = quantity
        elif 'quantity_done' in move._fields:
            move.quantity_done = quantity

    def _ampath_run_validate(self):
        """Validate picking, completing immediate wizards (backorder / expiry)."""
        self.ensure_one()
        result = self.button_validate()
        if isinstance(result, dict) and result.get('res_model'):
            wizard = self.env[result['res_model']].with_context(
                **(result.get('context') or {})
            ).create({})
            if hasattr(wizard, 'process'):
                wizard.process()
            elif hasattr(wizard, 'process_cancel_backorder'):
                wizard.process_cancel_backorder()
        self.invalidate_recordset()
        return self

    @api.model
    def _ampath_pick_fefo_lot(self, product, warehouse, quantity=None):
        if not product or not warehouse:
            return self.env['stock.lot']
        Quant = self.env['stock.quant']
        Lot = self.env['stock.lot']
        has_expiry = 'expiration_date' in Lot._fields
        quants = Quant.search(
            [
                ('product_id', '=', product.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
                ('lot_id', '!=', False),
                ('quantity', '>', 0),
            ]
        )
        quants = quants.filtered(lambda q: (q.quantity - q.reserved_quantity) > 0)
        if not quants:
            return Lot
        far_future = fields.Datetime.to_datetime('2099-12-31 23:59:59')
        now = fields.Datetime.now()

        def _fefo_key(quant):
            if has_expiry:
                return (
                    quant.lot_id.expiration_date or far_future,
                    quant.in_date or now,
                    quant.id,
                )
            return (quant.in_date or now, quant.id)

        if quantity:
            fulfilling = quants.filtered(
                lambda q: (q.quantity - q.reserved_quantity) >= quantity
            )
            if fulfilling:
                quants = fulfilling
        return quants.sorted(_fefo_key)[:1].lot_id

    @api.model
    def _ampath_create_and_validate_picking(
        self,
        picking_type,
        location_id,
        location_dest_id,
        origin,
        company,
        lines,
        partner=None,
        moh647_flow=False,
    ):
        """Create and validate a picking.

        ``lines`` is a list of dicts: product, quantity, lot (optional recordset).
        """
        if not picking_type:
            raise UserError(_('No picking type configured for this warehouse.'))
        Picking = self.sudo()
        Move = self.env['stock.move'].sudo()
        vals = {
            'picking_type_id': picking_type.id,
            'location_id': location_id,
            'location_dest_id': location_dest_id,
            'origin': origin,
            'company_id': company.id,
        }
        if partner:
            vals['partner_id'] = partner.id
        if moh647_flow:
            vals['x_moh647_flow'] = moh647_flow
        picking = Picking.create(vals)
        created_moves = []
        for line in lines:
            product = line['product']
            quantity = line['quantity']
            move = Move.create(
                {
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': quantity,
                    'product_uom': product.uom_id.id,
                    'picking_id': picking.id,
                    'picking_type_id': picking_type.id,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'company_id': company.id,
                }
            )
            created_moves.append(move)
        picking.action_confirm()
        picking.action_assign()
        for line, move in zip(lines, created_moves):
            quantity = line['quantity']
            lot = line.get('lot')
            if lot:
                for move_line in picking.move_line_ids.filtered(
                    lambda ml: ml.product_id == move.product_id
                ):
                    move_line.lot_id = lot.id
                    picking._ampath_set_move_line_qty(move_line, quantity)
            else:
                move_lines = picking.move_line_ids.filtered(
                    lambda ml: ml.product_id == move.product_id
                )
                if move_lines:
                    picking._ampath_set_move_line_qty(move_lines[0], quantity)
                else:
                    picking._ampath_set_move_qty(move, quantity)
            if 'picked' in move._fields:
                move.picked = True
        picking._ampath_run_validate()
        if picking.state != 'done':
            raise UserError(
                _('Could not validate stock picking %s (state: %s).')
                % (picking.name, picking.state)
            )
        return picking


class StockLocation(models.Model):
    _inherit = 'stock.location'

    x_ampath_external_transit = fields.Boolean(
        string='AMPATH external-facility transit',
        help='Source/destination for inter-facility receipts and issues (MOH 647 E/F).',
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _ampath_fill_lots_from_quants(self):
        """Put remaining demand onto existing source lots (FEFO then oldest quant)."""
        Quant = self.env['stock.quant']
        MoveLine = self.env['stock.move.line']
        Lot = self.env['stock.lot']
        has_expiry = 'expiration_date' in Lot._fields
        for move in self:
            remaining = move.product_uom._compute_quantity(
                move.product_uom_qty, move.product_id.uom_id, rounding_method='HALF-UP'
            )
            remaining -= sum(
                ml.product_uom_id._compute_quantity(
                    ml.quantity, move.product_id.uom_id, rounding_method='HALF-UP'
                )
                for ml in move.move_line_ids
                if ml.lot_id
            )
            prec = move.product_id.uom_id.rounding
            if float_compare(remaining, 0, precision_rounding=prec) <= 0:
                continue
            quants = Quant.search(
                [
                    ('product_id', '=', move.product_id.id),
                    ('location_id', 'child_of', move.location_id.id),
                    ('lot_id', '!=', False),
                ]
            )
            quants = quants.filtered(
                lambda q: float_compare(
                    q.quantity - q.reserved_quantity, 0, precision_rounding=prec
                )
                > 0
            )
            if has_expiry:
                far_future = fields.Datetime.to_datetime('2099-12-31 23:59:59')
                quants = quants.sorted(
                    lambda q: (
                        q.lot_id.expiration_date or far_future,
                        q.in_date or fields.Datetime.now(),
                        q.id,
                    )
                )
            else:
                quants = quants.sorted(lambda q: (q.in_date or fields.Datetime.now(), q.id))
            for quant in quants:
                if float_compare(remaining, 0, precision_rounding=prec) <= 0:
                    break
                available = quant.quantity - quant.reserved_quantity
                take = min(available, remaining)
                if float_compare(take, 0, precision_rounding=prec) <= 0:
                    continue
                empty = move.move_line_ids.filtered(
                    lambda ml: not ml.lot_id
                    and float_is_zero(ml.quantity, precision_rounding=prec)
                )[:1]
                if empty:
                    empty.write(
                        {
                            'lot_id': quant.lot_id.id,
                            'location_id': quant.location_id.id,
                            'quantity': take,
                        }
                    )
                else:
                    vals = move._prepare_move_line_vals(take, quant)
                    vals['lot_id'] = quant.lot_id.id
                    vals['quantity'] = take
                    MoveLine.create(vals)
                remaining -= take
            leftovers = move.move_line_ids.filtered(
                lambda ml: not ml.lot_id
                and float_is_zero(ml.quantity, precision_rounding=prec)
            )
            leftovers.unlink()


def _is_internal_transfer_type(name):
    if isinstance(name, dict):
        name = name.get('en_US') or next(iter(name.values()), '')
    return 'internal transfer' in (name or '').lower()


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    @api.model
    def _ampath_configure_internal_transfers(self):
        """Internal transfers consume existing batches and show detailed operations."""
        types = self.sudo().search([('code', '=', 'internal')])
        internals = types.filtered(lambda t: _is_internal_transfer_type(t.name))
        for ptype in internals:
            vals = {
                'show_operations': True,
                'use_create_lots': False,
                'use_existing_lots': True,
            }
            src = ptype.default_location_src_id
            src_name = (src.complete_name or src.name or '').lower()
            if src and 'kesse/stock' in src_name:
                pharmacy_stock = self.env['stock.location'].sudo().search(
                    [
                        ('company_id', '=', ptype.company_id.id),
                        ('usage', '=', 'internal'),
                        ('name', '=', 'Kesses Pharmacy Stock'),
                    ],
                    limit=1,
                )
                if pharmacy_stock:
                    vals['default_location_dest_id'] = pharmacy_stock.id
            ptype.write(vals)
        return internals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code') == 'internal' and _is_internal_transfer_type(vals.get('name')):
                vals.setdefault('show_operations', True)
                vals.setdefault('use_create_lots', False)
                vals.setdefault('use_existing_lots', True)
        return super().create(vals_list)
