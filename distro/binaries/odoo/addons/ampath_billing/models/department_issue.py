# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class AmpathIssueDepartment(models.Model):
    _name = 'ampath.issue.department'
    _description = 'Issue department (point of use)'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class AmpathDepartmentIssue(models.Model):
    _name = 'ampath.department.issue'
    _description = 'Department issue voucher (S11)'
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
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Issue point',
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    department_id = fields.Many2one(
        'ampath.issue.department',
        string='Point of use',
        required=True,
    )
    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    account_no = fields.Char(string='Account No.')
    requisitioning_officer = fields.Char()
    requisitioning_designation = fields.Char()
    issued_by = fields.Char()
    received_by = fields.Char()
    received_designation = fields.Char()
    remarks = fields.Text()
    line_ids = fields.One2many(
        'ampath.department.issue.line',
        'issue_id',
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
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('ampath.department.issue')
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
            rec._validate_issue()
        return True

    def _validate_issue(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft vouchers can be validated.'))
        if not self.line_ids:
            raise UserError(_('Add at least one line.'))
        warehouse = self.warehouse_id
        picking_type = warehouse.out_type_id
        location_id = (
            picking_type.default_location_src_id.id
            or warehouse.lot_stock_id.id
        )
        location_dest_id = (
            picking_type.default_location_dest_id.id
            or self.env.ref('stock.stock_location_customers').id
        )
        lines = []
        for line in self.line_ids:
            if float_compare(line.qty_issued, 0, precision_digits=4) <= 0:
                raise UserError(
                    _('Qty issued must be greater than zero on %s.')
                    % (line.product_id.display_name,)
                )
            lot = line.lot_id
            product = line.product_id
            if product.tracking in ('lot', 'serial') and not lot:
                lot = self.env['stock.picking']._ampath_pick_fefo_lot(
                    product, warehouse, quantity=line.qty_issued
                )
                if not lot:
                    raise UserError(
                        _('No in-stock lot for %s at %s.')
                        % (product.display_name, warehouse.display_name)
                    )
                line.lot_id = lot.id
            lines.append(
                {
                    'product': product,
                    'quantity': line.qty_issued,
                    'lot': lot,
                }
            )
        picking = self.env['stock.picking']._ampath_create_and_validate_picking(
            picking_type,
            location_id,
            location_dest_id,
            origin='S11 %s' % self.name,
            company=self.company_id,
            lines=lines,
            moh647_flow=False,
        )
        self.write({'state': 'done', 'picking_id': picking.id})


class AmpathDepartmentIssueLine(models.Model):
    _name = 'ampath.department.issue.line'
    _description = 'Department issue line'

    issue_id = fields.Many2one(
        'ampath.department.issue',
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
    qty_required = fields.Float(string='Qty required', digits='Product Unit of Measure')
    qty_issued = fields.Float(
        string='Qty issued',
        required=True,
        digits='Product Unit of Measure',
    )
    lot_id = fields.Many2one(
        'stock.lot',
        domain="[('product_id', '=', product_id)]",
    )
    value = fields.Float(compute='_compute_value', store=True)
    remarks = fields.Char()

    @api.depends('qty_issued', 'product_id', 'product_id.standard_price')
    def _compute_value(self):
        for line in self:
            line.value = (line.qty_issued or 0.0) * (line.product_id.standard_price or 0.0)
