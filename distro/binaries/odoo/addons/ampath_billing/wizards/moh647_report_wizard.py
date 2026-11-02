# -*- coding: utf-8 -*-

import base64
import csv
import io
from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None


UNMAPPED = '-'


class AmpathMoh647ReportWizard(models.TransientModel):
    _name = 'ampath.moh647.report.wizard'
    _description = 'MOH 647 Facility Tracer HPT Report'

    company_id = fields.Many2one(
        'res.company',
        string='Health Facility',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        string='Period Beginning',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Period Ending',
        required=True,
        default=fields.Date.today,
    )
    reporting_officer_name = fields.Char(string='Reporting officer name')
    reporting_officer_designation = fields.Char(string='Reporting officer designation')
    reporting_officer_email = fields.Char(string='Reporting officer email')
    reporting_officer_phone = fields.Char(string='Reporting officer telephone')
    approving_officer_name = fields.Char(string='Approving officer name')
    approving_officer_designation = fields.Char(string='Approving officer designation')
    approving_officer_email = fields.Char(string='Approving officer email')
    approving_officer_phone = fields.Char(string='Approving officer telephone')
    state = fields.Selection(
        [
            ('criteria', 'Criteria'),
            ('preview', 'Preview'),
        ],
        default='criteria',
        required=True,
    )
    preview_html = fields.Html(
        string='Report preview',
        sanitize=False,
        readonly=True,
    )
    report_pdf = fields.Binary(string='PDF', attachment=False)
    report_pdf_name = fields.Char()
    report_xlsx = fields.Binary(string='Excel', attachment=False)
    report_xlsx_name = fields.Char()

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise UserError(_('Period Beginning must be on or before Period Ending.'))

    def _get_tracers(self):
        self.ensure_one()
        return self.env['ampath.moh647.tracer'].search(
            [('active', '=', True)],
            order='sequence',
        )

    def _dt_start(self, day):
        return fields.Datetime.to_string(datetime.combine(day, time.min))

    def _dt_end(self, day):
        return fields.Datetime.to_string(datetime.combine(day, time.max))

    @staticmethod
    def _as_datetime(value):
        """Normalize ORM datetime fields (datetime or str) for comparisons."""
        if value is None or value is False:
            return False
        return fields.Datetime.to_datetime(value)

    def _company_internal_locations(self):
        self.ensure_one()
        Location = self.env['stock.location']
        warehouses = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)]
        )
        locations = warehouses.mapped('lot_stock_id')
        if not locations:
            locations = Location.search(
                [
                    ('company_id', '=', self.company_id.id),
                    ('usage', '=', 'internal'),
                ]
            )
        else:
            locations |= Location.search(
                [
                    ('id', 'child_of', locations.ids),
                    ('usage', '=', 'internal'),
                ]
            )
        return locations

    def _product_qty_at(self, products, location_ids, at_dt, include_inventory=True):
        """On-hand qty in product UoM at datetime by replaying moves after at_dt.

        When ``include_inventory`` is False, physical inventory corrections after
        ``at_dt`` are left in place so beginning balance uses the corrected count.
        """
        Quant = self.env['stock.quant']
        Move = self.env['stock.move']
        quants = Quant.search(
            [
                ('product_id', 'in', products.ids),
                ('location_id', 'in', location_ids),
            ]
        )
        qty_by_product = defaultdict(float)
        for quant in quants:
            qty_by_product[quant.product_id.id] += quant.quantity

        # Subtract net effect of moves completed after at_dt
        moves_after = Move.search(
            [
                ('product_id', 'in', products.ids),
                ('state', '=', 'done'),
                ('date', '>', at_dt),
                '|',
                ('location_id', 'in', location_ids),
                ('location_dest_id', 'in', location_ids),
            ]
        )
        for move in moves_after:
            if not include_inventory and self._is_physical_inventory_move(move):
                continue
            qty = self._move_qty_product_uom(move)
            if move.location_dest_id.id in location_ids and move.location_id.id not in location_ids:
                qty_by_product[move.product_id.id] -= qty
            elif move.location_id.id in location_ids and move.location_dest_id.id not in location_ids:
                qty_by_product[move.product_id.id] += qty
        return qty_by_product

    def _move_qty_product_uom(self, move):
        raw = move.quantity if 'quantity' in move._fields else move.quantity_done
        return move.product_uom._compute_quantity(
            raw, move.product_id.uom_id, rounding_method='HALF-UP'
        )

    def _is_scrap_location(self, location):
        return bool(location) and bool(getattr(location, 'scrap_location', False))

    def _is_scrap_move(self, move):
        return self._is_scrap_location(move.location_id) or self._is_scrap_location(
            move.location_dest_id
        )

    def _is_physical_inventory_move(self, move):
        """Inventory count corrections (not scrap write-offs)."""
        if self._is_scrap_move(move):
            return False
        return move.location_id.usage == 'inventory' or move.location_dest_id.usage == 'inventory'

    def _is_other_facility_location(self, location):
        if not location or location.usage not in ('internal', 'transit'):
            return False
        if not location.company_id:
            return False
        return location.company_id != self.company_id

    def _picking_type_code(self, move):
        picking = move.picking_id
        if not picking or not picking.picking_type_id:
            return False
        return picking.picking_type_id.code

    def _classify_move_qty(self, move, location_ids):
        """Return (bucket, qty) for report columns B–F.

        B = incoming Receipts only; E/F = other facilities (location or
        picking x_moh647_flow); D = scrap. Physical inventory omitted.
        """
        loc_in = move.location_id
        loc_out = move.location_dest_id
        qty = self._move_qty_product_uom(move)
        into = loc_out.id in location_ids and loc_in.id not in location_ids
        out_of = loc_in.id in location_ids and loc_out.id not in location_ids
        if not into and not out_of:
            return None, 0.0

        if self._is_physical_inventory_move(move):
            return None, 0.0
        if self._is_scrap_move(move):
            return 'D', qty

        if into and self._is_other_facility_location(loc_in):
            return 'E', qty
        if out_of and self._is_other_facility_location(loc_out):
            return 'F', qty

        moh647_flow = (
            move.picking_id.x_moh647_flow
            if move.picking_id and 'x_moh647_flow' in move.picking_id._fields
            else False
        )
        if into and moh647_flow == 'external_in':
            return 'E', qty
        if out_of and moh647_flow == 'external_out':
            return 'F', qty

        picking_code = self._picking_type_code(move)
        if into and picking_code == 'incoming':
            return 'B', qty
        if out_of and loc_out.usage in ('customer', 'production'):
            return 'C', qty
        if out_of and picking_code == 'outgoing':
            return 'C', qty
        return None, 0.0

    def _near_expiry(self, products, location_ids, date_to):
        Lot = self.env['stock.lot']
        if 'expiration_date' not in Lot._fields:
            return 0.0, False
        Quant = self.env['stock.quant']
        limit = date_to + timedelta(days=183)
        quants = Quant.search(
            [
                ('product_id', 'in', products.ids),
                ('location_id', 'in', location_ids),
                ('quantity', '>', 0),
                ('lot_id', '!=', False),
                ('lot_id.expiration_date', '!=', False),
                ('lot_id.expiration_date', '<=', fields.Datetime.to_string(
                    datetime.combine(limit, time.max)
                )),
                ('lot_id.expiration_date', '>=', fields.Datetime.to_string(
                    datetime.combine(date_to, time.min)
                )),
            ]
        )
        qty = 0.0
        earliest = False
        for quant in quants:
            qty += quant.quantity
            exp = quant.lot_id.expiration_date
            if exp:
                exp_date = fields.Datetime.to_datetime(exp).date() if isinstance(exp, str) else (
                    exp.date() if hasattr(exp, 'date') else exp
                )
                if not earliest or exp_date < earliest:
                    earliest = exp_date
        return qty, earliest

    def _days_out_of_stock(self, products, location_ids, date_from, date_to):
        """Best-effort: count days where reconstructed on-hand was <= 0."""
        if not products:
            return UNMAPPED
        Move = self.env['stock.move']
        start_qty = self._product_qty_at(
            products, location_ids, self._dt_start(date_from), include_inventory=False
        )
        total_start = sum(start_qty.values())
        moves = Move.search(
            [
                ('product_id', 'in', products.ids),
                ('state', '=', 'done'),
                ('date', '>=', self._dt_start(date_from)),
                ('date', '<=', self._dt_end(date_to)),
                '|',
                ('location_id', 'in', location_ids),
                ('location_dest_id', 'in', location_ids),
            ],
            order='date asc',
        )
        if not moves and total_start > 0:
            return 0
        # Day-by-day walk using move dates
        day = date_from
        on_hand = total_start
        days_oos = 0
        move_idx = 0
        move_list = list(moves)
        while day <= date_to:
            day_end = self._as_datetime(self._dt_end(day))
            while (
                move_idx < len(move_list)
                and self._as_datetime(move_list[move_idx].date) <= day_end
            ):
                move = move_list[move_idx]
                move_idx += 1
                if self._is_physical_inventory_move(move):
                    continue
                loc_ids = set(location_ids)
                q = self._move_qty_product_uom(move)
                if move.location_dest_id.id in loc_ids and move.location_id.id not in loc_ids:
                    on_hand += q
                elif move.location_id.id in loc_ids and move.location_dest_id.id not in loc_ids:
                    on_hand -= q
            if on_hand <= 0:
                days_oos += 1
            day += timedelta(days=1)
        return days_oos

    def _round_qty(self, qty):
        return float_round(qty, precision_digits=2)

    def _compute_mapped_line(self, tracer, location_ids):
        products = tracer.product_line_ids.mapped('product_id')
        if not products:
            return {
                'mapped': False,
                'A': UNMAPPED,
                'B': UNMAPPED,
                'C': UNMAPPED,
                'D': UNMAPPED,
                'E': UNMAPPED,
                'F': UNMAPPED,
                'G': UNMAPPED,
                'H': UNMAPPED,
                'I': UNMAPPED,
                'J': UNMAPPED,
            }

        start_dt = self._dt_start(self.date_from)
        end_dt = self._dt_end(self.date_to)
        begin = self._product_qty_at(
            products, location_ids, start_dt, include_inventory=False
        )
        A = sum(begin.values())

        Move = self.env['stock.move']
        moves = Move.search(
            [
                ('product_id', 'in', products.ids),
                ('state', '=', 'done'),
                ('date', '>=', start_dt),
                ('date', '<=', end_dt),
                '|',
                ('location_id', 'in', location_ids),
                ('location_dest_id', 'in', location_ids),
            ]
        )
        B = C = D = E = F = 0.0
        for move in moves:
            bucket, qty = self._classify_move_qty(move, location_ids)
            if bucket == 'B':
                B += qty
            elif bucket == 'C':
                C += qty
            elif bucket == 'D':
                D += qty
            elif bucket == 'E':
                E += qty
            elif bucket == 'F':
                F += qty

        closing = self._product_qty_at(
            products, location_ids, end_dt, include_inventory=True
        )
        G = sum(closing.values())
        H_qty, I_date = self._near_expiry(products, location_ids, self.date_to)
        J = self._days_out_of_stock(products, location_ids, self.date_from, self.date_to)

        return {
            'mapped': True,
            'A': self._round_qty(A),
            'B': self._round_qty(B),
            'C': self._round_qty(C),
            'D': self._round_qty(D),
            'E': self._round_qty(E),
            'F': self._round_qty(F),
            'G': self._round_qty(G),
            'H': self._round_qty(H_qty),
            'I': I_date.isoformat() if I_date else UNMAPPED,
            'J': J if J != UNMAPPED else UNMAPPED,
        }

    def _compute_lines(self):
        self.ensure_one()
        tracers = self._get_tracers()
        location_ids = self._company_internal_locations().ids
        lines = []
        current_section = None
        section_labels = dict(
            self.env['ampath.moh647.tracer']._fields['section'].selection
        )
        for tracer in tracers:
            if tracer.section != current_section:
                current_section = tracer.section
                lines.append(
                    {
                        'is_section': True,
                        'section': current_section,
                        'section_label': section_labels.get(current_section, current_section),
                    }
                )
            metrics = self._compute_mapped_line(tracer, location_ids)
            lines.append(
                {
                    'is_section': False,
                    'sequence': tracer.sequence,
                    'name': tracer.name,
                    'unit_of_issue': tracer.unit_of_issue,
                    'section': tracer.section,
                    'mapped': metrics['mapped'],
                    'A': metrics['A'],
                    'B': metrics['B'],
                    'C': metrics['C'],
                    'D': metrics['D'],
                    'E': metrics['E'],
                    'F': metrics['F'],
                    'G': metrics['G'],
                    'H': metrics['H'],
                    'I': metrics['I'],
                    'J': metrics['J'],
                }
            )
        return lines

    def _report_context(self):
        self.ensure_one()
        return {
            'wizard': self,
            'company': self.company_id,
            'lines': self._compute_lines(),
            'date_from': self.date_from,
            'date_to': self.date_to,
        }

    def _reopen_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('MOH 647 Report'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'views': [
                (
                    self.env.ref(
                        'ampath_billing.view_moh647_report_wizard_form'
                    ).id,
                    'form',
                )
            ],
        }

    def _render_preview_html(self):
        """Render report body as an Html fragment (not a full document)."""
        self.ensure_one()
        values = self.env['report.ampath_billing.report_moh647_document']._get_report_values(
            self.ids
        )
        html_content = self.env['ir.qweb']._render(
            'ampath_billing.report_moh647_body',
            values,
        )
        if isinstance(html_content, bytes):
            html_content = html_content.decode('utf-8')
        return html_content

    def action_preview(self):
        self.ensure_one()
        html_content = self._render_preview_html()
        if not html_content or not str(html_content).strip():
            raise UserError(_('Could not render the MOH 647 report preview.'))
        self.write(
            {
                'preview_html': html_content,
                'state': 'preview',
            }
        )
        return self._reopen_wizard()

    def action_back_to_criteria(self):
        self.ensure_one()
        self.write(
            {
                'state': 'criteria',
                'preview_html': False,
                'report_pdf': False,
                'report_pdf_name': False,
                'report_xlsx': False,
                'report_xlsx_name': False,
            }
        )
        return self._reopen_wizard()

    def action_print_pdf(self):
        self.ensure_one()
        report = self.env.ref('ampath_billing.action_report_moh647')
        pdf_content, _ctype = (
            self.env['ir.actions.report']
            .with_context(report_pdf_no_attachment=True)
            ._render_qweb_pdf(report, self.ids, data=None)
        )
        fname = 'MOH647-%s-%s-%s.pdf' % (
            (self.company_id.name or 'facility').replace('/', '-')[:40],
            self.date_from,
            self.date_to,
        )
        self.write(
            {
                'report_pdf': base64.b64encode(pdf_content),
                'report_pdf_name': fname,
            }
        )
        att = self.env['ir.attachment'].sudo().create(
            {
                'name': fname,
                'type': 'binary',
                'datas': self.report_pdf,
                'mimetype': 'application/pdf',
                'res_model': self._name,
                'res_id': self.id,
            }
        )
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % att.id,
            'target': 'new',
        }

    def action_export_excel(self):
        self.ensure_one()
        lines = self._compute_lines()
        headers = [
            'No',
            'INN',
            'Unit of Issue',
            'A Beginning Balance',
            'B Quantity Received',
            'C Total Quantity Issued',
            'D Losses',
            'E Positive Adjustments',
            'F Negative Adjustments',
            'G Physical Count',
            'H Near Expiry Qty',
            'I Earliest Expiry',
            'J Days out of Stock',
        ]
        rows = []
        for line in lines:
            if line.get('is_section'):
                rows.append([line.get('section_label') or ''] + [''] * (len(headers) - 1))
                continue
            rows.append(
                [
                    line['sequence'],
                    line['name'],
                    line['unit_of_issue'],
                    line['A'],
                    line['B'],
                    line['C'],
                    line['D'],
                    line['E'],
                    line['F'],
                    line['G'],
                    line['H'],
                    line['I'],
                    line['J'],
                ]
            )

        fname_base = 'MOH647-%s-%s-%s' % (
            (self.company_id.name or 'facility').replace('/', '-')[:40],
            self.date_from,
            self.date_to,
        )
        if Workbook is not None:
            wb = Workbook()
            ws = wb.active
            ws.title = 'MOH 647'
            ws.append(headers)
            for row in rows:
                ws.append(row)
            buf = io.BytesIO()
            wb.save(buf)
            data = base64.b64encode(buf.getvalue())
            fname = fname_base + '.xlsx'
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(headers)
            writer.writerows(rows)
            data = base64.b64encode(buf.getvalue().encode('utf-8'))
            fname = fname_base + '.csv'
            mimetype = 'text/csv'

        self.write({'report_xlsx': data, 'report_xlsx_name': fname})
        att = self.env['ir.attachment'].sudo().create(
            {
                'name': fname,
                'type': 'binary',
                'datas': data,
                'mimetype': mimetype,
                'res_model': self._name,
                'res_id': self.id,
            }
        )
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % att.id,
            'target': 'new',
        }
