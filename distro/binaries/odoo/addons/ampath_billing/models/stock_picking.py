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
