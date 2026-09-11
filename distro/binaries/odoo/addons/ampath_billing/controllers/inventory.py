# -*- coding: utf-8 -*-
"""
Inventory endpoints for AMPATH pharmacy dispensing (Odoo stock only).

Billing remains in OpenMRS/O3. These endpoints do not use sale.order.

The EIP Odoo–OpenMRS client (eip-odoo-openmrs-ampath) listens to OpenMRS
MedicationDispense events (completed pharmacy dispenses) and calls
dispense/reverse here to update stock.

All endpoints require HTTP headers:
    login    – Odoo username
    password – Odoo password

Endpoints
---------
GET /ampath/inventory/stock
    Full on-hand stock payload (qty + lots) for a drug at a warehouse.
    Query params:
        openmrs_drug_uuid    – OpenMRS drug UUID (init.<uuid> external ID) (required)
        company_external_id  – OpenMRS order location UUID (required)
        lot_name             – optional lot filter

GET /ampath/inventory/batches
    Lot/batch list for a drug at a warehouse.
    Same query params as /stock.

GET /ampath/inventory/quantity
    Quantity available (on-hand + free) for a drug at a warehouse.
    Same query params as /stock (lot_name ignored).

POST /ampath/inventory/dispense
    Create and validate an outgoing stock.picking for the given quantity.
    Idempotent when openmrs_order_id is supplied: same quantity returns the
    existing picking; a different quantity reverses the old picking first.
    JSON body:
        openmrs_drug_uuid, quantity, company_external_id (required)
        openmrs_order_id, patient_external_id, lot_name, lot_id, uom_name (optional)
        Prefer lot_name (Odoo stock.lot name). lot_id remains for legacy callers.

POST /ampath/inventory/reverse
    Cancel or return stock for a prior dispense keyed by openmrs_order_id.
    JSON body:
        openmrs_order_id (required)
"""
import json
import logging

from odoo import http
from odoo.http import request
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class InventoryController(http.Controller):

    def _authenticate(self):
        login = request.httprequest.headers.get('login')
        password = request.httprequest.headers.get('password')
        if not login or not password:
            return None
        try:
            uid = request.session.authenticate(request.session.db, login, password)
            return uid if uid else None
        except Exception:
            return None

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, default=str),
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'no-store'),
            ],
            status=status,
        )

    def _order_origin_marker(self, openmrs_order_id):
        return f'order={openmrs_order_id}'

    def _build_origin(self, openmrs_order_id=None, patient_external_id=None):
        origin_parts = ['Pharmacy dispense']
        if openmrs_order_id:
            origin_parts.append(self._order_origin_marker(openmrs_order_id))
        if patient_external_id:
            origin_parts.append(f'patient={patient_external_id}')
        return ' | '.join(origin_parts)

    def _find_picking_by_order_id(self, env, openmrs_order_id):
        if not openmrs_order_id:
            return env['stock.picking']
        marker = self._order_origin_marker(openmrs_order_id)
        return env['stock.picking'].sudo().search([
            ('origin', 'ilike', marker),
            ('state', '!=', 'cancel'),
        ], order='id desc', limit=1)

    def _quantity_done_for_product(self, picking, product):
        total = 0.0
        for move in picking.move_ids:
            if move.product_id == product:
                total += self._get_move_qty_done(move)
        return total

    def _get_move_qty_done(self, move):
        """Odoo 17+ uses stock.move.quantity; older builds used quantity_done."""
        if 'quantity_done' in move._fields and move.quantity_done:
            return move.quantity_done
        return move.quantity if 'quantity' in move._fields else 0.0

    def _set_move_line_qty_done(self, move_line, quantity):
        """Odoo 17+ uses stock.move.line.quantity; older builds used qty_done."""
        if 'quantity' in move_line._fields:
            move_line.quantity = quantity
        elif 'qty_done' in move_line._fields:
            move_line.qty_done = quantity
        else:
            raise AttributeError(
                f'{move_line._name} has neither quantity nor qty_done'
            )

    def _set_move_qty_done(self, move, quantity):
        """Odoo 17+ uses stock.move.quantity; older builds used quantity_done."""
        if 'quantity' in move._fields:
            move.quantity = quantity
        elif 'quantity_done' in move._fields:
            move.quantity_done = quantity
        else:
            raise AttributeError(
                f'{move._name} has neither quantity nor quantity_done'
            )

    def _validate_picking_wizard(self, env, picking):
        result = picking.button_validate()
        if isinstance(result, dict) and result.get('res_model'):
            wizard_model = result['res_model']
            wizard_ctx = result.get('context') or {}
            wizard = env[wizard_model].sudo().with_context(**wizard_ctx).create({})
            if hasattr(wizard, 'process'):
                wizard.process()
            elif hasattr(wizard, 'process_cancel_backorder'):
                wizard.process_cancel_backorder()

    def _reverse_picking(self, env, picking):
        """Cancel a draft picking or create a return for a validated one."""
        if not picking or not picking.exists():
            return {'status': 'not_found'}
        if picking.state == 'cancel':
            return {
                'status': 'already_cancelled',
                'picking_id': picking.id,
                'picking_name': picking.name,
            }
        if picking.state != 'done':
            picking.action_cancel()
            return {
                'status': 'cancelled',
                'picking_id': picking.id,
                'picking_name': picking.name,
            }

        ReturnWizard = env['stock.return.picking'].sudo()
        wizard = ReturnWizard.with_context(
            active_id=picking.id,
            active_ids=picking.ids,
        ).create({})
        if not wizard.product_return_moves:
            _logger.warning(
                'No return moves for picking %s (order reversal)', picking.name
            )
            return {
                'status': 'no_return_moves',
                'picking_id': picking.id,
                'picking_name': picking.name,
            }

        for return_move in wizard.product_return_moves:
            return_move.quantity = return_move.move_id.quantity

        action = wizard.create_returns()
        return_picking = env['stock.picking'].browse(action['res_id'])
        return_picking.action_confirm()
        return_picking.action_assign()
        for move_line in return_picking.move_line_ids:
            self._set_move_line_qty_done(move_line, move_line.product_uom_qty)
        if not return_picking.move_line_ids:
            for move in return_picking.move_ids:
                self._set_move_qty_done(move, move.product_uom_qty)
        self._validate_picking_wizard(env, return_picking)

        return {
            'status': 'returned',
            'picking_id': picking.id,
            'picking_name': picking.name,
            'return_picking_id': return_picking.id,
            'return_picking_name': return_picking.name,
        }

    def _resolve_company(self, env, company_external_id):
        """Map OpenMRS location UUID → res.company via ir.model.data (init module)."""
        imd = env['ir.model.data'].sudo().search([
            ('module', '=', 'init'),
            ('name', '=', company_external_id),
            ('model', '=', 'res.company'),
        ], limit=1)
        if not imd:
            return None
        return env['res.company'].sudo().browse(imd.res_id).exists()

    def _resolve_warehouse(self, env, company):
        Warehouse = env['stock.warehouse'].sudo()
        wh = Warehouse.search([('company_id', '=', company.id)], limit=1)
        return wh if wh else None

    def _resolve_product(self, env, openmrs_drug_uuid):
        """Resolve a single product for a drug UUID (legacy / single-SKU).

        Prefers products with ``x_openmrs_drug_uuid``; falls back to
        ``ir.model.data`` name = uuid (CSV seed era).
        """
        products = self._resolve_products(env, openmrs_drug_uuid)
        return products[:1] if products else None

    def _resolve_products(self, env, openmrs_drug_uuid):
        """All stockable products linked to an OpenMRS drug UUID (multi-SKU)."""
        Product = env['product.product'].sudo()
        if 'x_openmrs_drug_uuid' in Product._fields:
            products = Product.search([
                ('x_openmrs_drug_uuid', '=', openmrs_drug_uuid),
                ('active', '=', True),
            ])
            if products:
                return products

        imd = env['ir.model.data'].sudo().search([
            ('module', '=', 'init'),
            ('name', '=', openmrs_drug_uuid),
            ('model', 'in', ['product.product', 'product.template']),
        ], limit=1)
        if not imd:
            return Product.browse()
        if imd.model == 'product.product':
            return Product.browse(imd.res_id).exists()
        template = env['product.template'].sudo().browse(imd.res_id).exists()
        if not template:
            return Product.browse()
        variant = template.product_variant_id
        return variant if variant else Product.browse()

    def _available_qty(self, product, warehouse):
        prod = product.with_context(warehouse=warehouse.id)
        if 'free_qty' in prod._fields:
            return prod.free_qty
        return prod.qty_available

    def _available_qty_multi(self, products, warehouse):
        return sum(self._available_qty(p, warehouse) for p in products)

    def _serialize_lots(self, env, products, warehouse, lot_name=None):
        """Serialize lots across one or more SKU products (include SKU identity)."""
        if not products:
            return []
        Quant = env['stock.quant'].sudo()
        domain = [
            ('product_id', 'in', products.ids),
            ('location_id', 'child_of', warehouse.lot_stock_id.id),
            ('quantity', '>', 0),
        ]
        if lot_name:
            domain.append(('lot_id.name', '=', lot_name))
        quants = Quant.search(domain)
        lots = []
        seen = set()
        for quant in quants:
            lot = quant.lot_id
            if not lot or lot.id in seen:
                continue
            seen.add(lot.id)
            product = quant.product_id
            lots.append({
                'id': lot.id,
                'name': lot.name,
                'quantity': quant.quantity,
                'expiration_date': (
                    lot.expiration_date.isoformat()
                    if getattr(lot, 'expiration_date', None) else None
                ),
                'product_id': product.id,
                'product_name': product.display_name,
                'default_code': product.default_code or False,
            })
        return lots

    def _resolve_stock_context(self, env, openmrs_drug_uuid, company_external_id):
        """Resolve company, warehouse, and products for inventory GET endpoints.

        Returns ``(company, warehouse, products, error_response)``. On success
        ``error_response`` is ``None``. ``products`` may contain multiple SKUs.
        """
        if not openmrs_drug_uuid:
            return None, None, None, self._json_response(
                {'error': 'openmrs_drug_uuid is required.'}, status=400
            )
        if not company_external_id:
            return None, None, None, self._json_response(
                {'error': 'company_external_id (OpenMRS order location UUID) is required.'},
                status=400,
            )

        company = self._resolve_company(env, company_external_id)
        if not company:
            return None, None, None, self._json_response({
                'error': f'No company found for external ID "{company_external_id}".',
            }, status=404)

        warehouse = self._resolve_warehouse(env, company)
        if not warehouse:
            return None, None, None, self._json_response({
                'error': f'No warehouse found for company "{company.name}".',
            }, status=400)

        products = self._resolve_products(env, openmrs_drug_uuid)
        if not products:
            return None, None, None, self._json_response({
                'error': f'No product found for external ID "{openmrs_drug_uuid}".',
            }, status=404)

        return company, warehouse, products, None

    def _stock_payload(self, products, warehouse, company_external_id, openmrs_drug_uuid, lot_name=None):
        env = request.env
        avail = self._available_qty_multi(products, warehouse)
        primary = products[0]
        free_qty = avail
        return {
            'openmrs_drug_uuid': openmrs_drug_uuid,
            'order_location_uuid': company_external_id,
            'product_id': primary.id if len(products) == 1 else False,
            'product_name': primary.display_name if len(products) == 1 else False,
            'products': [{
                'id': p.id,
                'name': p.display_name,
                'default_code': p.default_code or False,
                'qty_available': self._available_qty(p, warehouse),
            } for p in products],
            'warehouse': {'id': warehouse.id, 'name': warehouse.display_name},
            'uom': {
                'id': primary.uom_id.id,
                'name': primary.uom_id.name,
            },
            'qty_available': avail,
            'free_qty': free_qty,
            'lots': self._serialize_lots(env, products, warehouse, lot_name=lot_name),
        }

    def _quantity_payload(self, products, warehouse, company_external_id, openmrs_drug_uuid):
        avail = self._available_qty_multi(products, warehouse)
        primary = products[0]
        return {
            'openmrs_drug_uuid': openmrs_drug_uuid,
            'order_location_uuid': company_external_id,
            'product_id': primary.id if len(products) == 1 else False,
            'product_name': primary.display_name if len(products) == 1 else False,
            'products': [{
                'id': p.id,
                'name': p.display_name,
                'default_code': p.default_code or False,
                'qty_available': self._available_qty(p, warehouse),
            } for p in products],
            'warehouse': {'id': warehouse.id, 'name': warehouse.display_name},
            'uom': {
                'id': primary.uom_id.id,
                'name': primary.uom_id.name,
            },
            'qty_available': avail,
            'free_qty': avail,
        }

    def _batches_payload(self, products, warehouse, company_external_id, openmrs_drug_uuid, lot_name=None):
        env = request.env
        primary = products[0]
        return {
            'openmrs_drug_uuid': openmrs_drug_uuid,
            'order_location_uuid': company_external_id,
            'product_id': primary.id if len(products) == 1 else False,
            'product_name': primary.display_name if len(products) == 1 else False,
            'products': [{
                'id': p.id,
                'name': p.display_name,
                'default_code': p.default_code or False,
            } for p in products],
            'warehouse': {'id': warehouse.id, 'name': warehouse.display_name},
            'uom': {
                'id': primary.uom_id.id,
                'name': primary.uom_id.name,
            },
            'lots': self._serialize_lots(env, products, warehouse, lot_name=lot_name),
        }

    def _create_and_validate_dispense_picking(
        self,
        env,
        product,
        warehouse,
        company,
        quantity,
        origin,
        patient_external_id=None,
        lot_id=None,
    ):
        free_qty = self._available_qty(product, warehouse)
        prec = product.uom_id.rounding
        if float_compare(free_qty, quantity, precision_rounding=prec) < 0:
            return None, self._json_response({
                'error': (
                    f'Insufficient stock for {product.display_name}: '
                    f'need {quantity} {product.uom_id.name}, '
                    f'available {free_qty} (warehouse: {warehouse.display_name})'
                ),
            }, status=400)

        picking_type = warehouse.out_type_id
        if not picking_type:
            return None, self._json_response({
                'error': f'Warehouse "{warehouse.display_name}" has no outgoing picking type.',
            }, status=400)

        partner = False
        if patient_external_id:
            partner = env['res.partner'].sudo().search([
                '|',
                ('x_external_identifier', '=', patient_external_id),
                ('ref', '=', patient_external_id),
            ], limit=1)

        Picking = env['stock.picking'].sudo()
        Move = env['stock.move'].sudo()

        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id
            or warehouse.lot_stock_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id
            or env.ref('stock.stock_location_customers').id,
            'origin': origin,
            'company_id': company.id,
        }
        if partner:
            picking_vals['partner_id'] = partner.id

        picking = Picking.create(picking_vals)

        move_vals = {
            'name': product.display_name,
            'product_id': product.id,
            'product_uom_qty': quantity,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'picking_type_id': picking_type.id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
            'company_id': company.id,
        }
        move = Move.create(move_vals)

        picking.action_confirm()
        picking.action_assign()

        if lot_id:
            lot = env['stock.lot'].sudo().browse(int(lot_id)).exists()
            if not lot:
                picking.action_cancel()
                return None, self._json_response(
                    {'error': f'Lot id {lot_id} not found.'}, status=400
                )
            for move_line in picking.move_line_ids:
                if move_line.product_id == product:
                    move_line.lot_id = lot.id
                    self._set_move_line_qty_done(move_line, quantity)
        else:
            for move_line in picking.move_line_ids:
                if move_line.product_id == product:
                    self._set_move_line_qty_done(move_line, quantity)
            if not picking.move_line_ids:
                self._set_move_qty_done(move, quantity)

        self._validate_picking_wizard(env, picking)
        picking.invalidate_recordset()
        return picking, None

    def _resolve_lot(self, env, products, lot_id=None, lot_name=None):
        """Resolve stock.lot from lot_id (legacy) or lot_name (preferred).

        Returns ``(lot, product, error_response)``. On success ``error_response`` is None.
        Prefer lot_id when both are supplied.
        """
        Lot = env['stock.lot'].sudo()
        if lot_id not in (None, '', False):
            lot = Lot.browse(int(lot_id)).exists()
            if not lot:
                return None, None, self._json_response(
                    {'error': f'Lot id {lot_id} not found.'}, status=404
                )
            if lot.product_id not in products:
                return None, None, self._json_response({
                    'error': (
                        f'Lot {lot_id} product does not match openmrs_drug_uuid.'
                    ),
                }, status=400)
            return lot, lot.product_id, None

        if lot_name:
            lot = Lot.search([
                ('name', '=', lot_name),
                ('product_id', 'in', products.ids),
            ], limit=1)
            if not lot:
                return None, None, self._json_response({
                    'error': f'No lot found for lot_name "{lot_name}".',
                }, status=404)
            return lot, lot.product_id, None

        return None, None, None

    @http.route(
        '/ampath/inventory/stock',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def get_stock(self, **kw):
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        openmrs_drug_uuid = (kw.get('openmrs_drug_uuid') or '').strip()
        company_external_id = (kw.get('company_external_id') or '').strip()
        lot_name = (kw.get('lot_name') or '').strip() or None

        env = request.env
        _company, warehouse, products, error = self._resolve_stock_context(
            env, openmrs_drug_uuid, company_external_id
        )
        if error:
            return error

        return self._json_response(
            self._stock_payload(
                products,
                warehouse,
                company_external_id,
                openmrs_drug_uuid,
                lot_name=lot_name,
            )
        )

    @http.route(
        '/ampath/inventory/batches',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def get_batches(self, **kw):
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        openmrs_drug_uuid = (kw.get('openmrs_drug_uuid') or '').strip()
        company_external_id = (kw.get('company_external_id') or '').strip()
        lot_name = (kw.get('lot_name') or '').strip() or None

        env = request.env
        _company, warehouse, products, error = self._resolve_stock_context(
            env, openmrs_drug_uuid, company_external_id
        )
        if error:
            return error

        return self._json_response(
            self._batches_payload(
                products,
                warehouse,
                company_external_id,
                openmrs_drug_uuid,
                lot_name=lot_name,
            )
        )

    @http.route(
        '/ampath/inventory/quantity',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def get_quantity(self, **kw):
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        openmrs_drug_uuid = (kw.get('openmrs_drug_uuid') or '').strip()
        company_external_id = (kw.get('company_external_id') or '').strip()

        env = request.env
        _company, warehouse, products, error = self._resolve_stock_context(
            env, openmrs_drug_uuid, company_external_id
        )
        if error:
            return error

        return self._json_response(
            self._quantity_payload(
                products,
                warehouse,
                company_external_id,
                openmrs_drug_uuid,
            )
        )

    @http.route(
        '/ampath/inventory/dispense',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def dispense(self, **kw):
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        try:
            body = json.loads(request.httprequest.data.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return self._json_response({'error': 'Invalid JSON body.'}, status=400)

        openmrs_drug_uuid = (body.get('openmrs_drug_uuid') or '').strip()
        company_external_id = (body.get('company_external_id') or '').strip()
        openmrs_order_id = (body.get('openmrs_order_id') or '').strip() or None
        patient_external_id = (body.get('patient_external_id') or '').strip() or None
        lot_id = body.get('lot_id')
        lot_name = (body.get('lot_name') or '').strip() or None
        quantity = body.get('quantity')

        if not openmrs_drug_uuid:
            return self._json_response(
                {'error': 'openmrs_drug_uuid is required.'}, status=400
            )
        if not company_external_id:
            return self._json_response(
                {'error': 'company_external_id (OpenMRS order location UUID) is required.'},
                status=400,
            )
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            return self._json_response(
                {'error': 'quantity must be a number.'}, status=400
            )
        if quantity <= 0:
            return self._json_response(
                {'error': 'quantity must be greater than zero.'}, status=400
            )

        env = request.env
        company = self._resolve_company(env, company_external_id)
        if not company:
            return self._json_response({
                'error': f'No company found for external ID "{company_external_id}".',
            }, status=404)

        warehouse = self._resolve_warehouse(env, company)
        if not warehouse:
            return self._json_response({
                'error': f'No warehouse found for company "{company.name}".',
            }, status=400)

        products = self._resolve_products(env, openmrs_drug_uuid)
        if not products:
            return self._json_response({
                'error': f'No product found for external ID "{openmrs_drug_uuid}".',
            }, status=404)

        lot, lot_product, lot_error = self._resolve_lot(
            env, products, lot_id=lot_id, lot_name=lot_name
        )
        if lot_error:
            return lot_error

        product = lot_product or products[0]
        if not lot and len(products) > 1:
            return self._json_response({
                'error': (
                    'lot_name (or lot_id) is required when multiple SKUs exist for this drug. '
                    'Use GET /ampath/inventory/batches to choose a batch.'
                ),
            }, status=400)

        # Optional unit UUID check (shared UUID5 with OpenMRS dispensing unit)
        quantity_unit_uuid = (body.get('quantity_unit_uuid') or body.get('uom_uuid') or '').strip()
        if quantity_unit_uuid:
            uom_imd = env['ir.model.data'].sudo().search([
                ('module', '=', 'init'),
                ('name', '=', quantity_unit_uuid),
                ('model', '=', 'uom.uom'),
            ], limit=1)
            if uom_imd and product.uom_id.id != uom_imd.res_id:
                return self._json_response({
                    'error': (
                        f'Dispense unit uuid "{quantity_unit_uuid}" does not match '
                        f'product UOM for {product.display_name}.'
                    ),
                }, status=400)

        prec = product.uom_id.rounding

        if openmrs_order_id:
            existing = self._find_picking_by_order_id(env, openmrs_order_id)
            if existing:
                existing_qty = self._quantity_done_for_product(existing, product)
                if float_compare(existing_qty, quantity, precision_rounding=prec) == 0:
                    remaining = self._available_qty(product, warehouse)
                    return self._json_response({
                        'picking_id': existing.id,
                        'picking_name': existing.name,
                        'quantity_done': existing_qty,
                        'free_qty': remaining,
                        'product_id': product.id,
                        'order_location_uuid': company_external_id,
                        'warehouse': {'id': warehouse.id, 'name': warehouse.display_name},
                        'openmrs_order_id': openmrs_order_id,
                        'idempotent': True,
                    })
                reverse_result = self._reverse_picking(env, existing)
                _logger.info(
                    'Reversed prior dispense for order %s before quantity update: %s',
                    openmrs_order_id,
                    reverse_result,
                )

        origin = self._build_origin(openmrs_order_id, patient_external_id)
        picking, error_response = self._create_and_validate_dispense_picking(
            env,
            product,
            warehouse,
            company,
            quantity,
            origin,
            patient_external_id=patient_external_id,
            lot_id=lot.id if lot else None,
        )
        if error_response:
            return error_response

        remaining = self._available_qty(product, warehouse)
        return self._json_response({
            'picking_id': picking.id,
            'picking_name': picking.name,
            'quantity_done': quantity,
            'free_qty': remaining,
            'product_id': product.id,
            'order_location_uuid': company_external_id,
            'warehouse': {'id': warehouse.id, 'name': warehouse.display_name},
            'openmrs_order_id': openmrs_order_id,
            'idempotent': False,
        })

    @http.route(
        '/ampath/inventory/reverse',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def reverse(self, **kw):
        uid = self._authenticate()
        if not uid:
            return self._json_response(
                {'error': 'Authentication failed. Provide login and password headers.'},
                status=401,
            )

        try:
            body = json.loads(request.httprequest.data.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return self._json_response({'error': 'Invalid JSON body.'}, status=400)

        openmrs_order_id = (body.get('openmrs_order_id') or '').strip()
        if not openmrs_order_id:
            return self._json_response(
                {'error': 'openmrs_order_id is required.'}, status=400
            )

        env = request.env
        picking = self._find_picking_by_order_id(env, openmrs_order_id)
        if not picking:
            return self._json_response({
                'openmrs_order_id': openmrs_order_id,
                'status': 'not_found',
                'message': 'No active picking found for this order.',
            })

        result = self._reverse_picking(env, picking)
        result['openmrs_order_id'] = openmrs_order_id
        return self._json_response(result)
