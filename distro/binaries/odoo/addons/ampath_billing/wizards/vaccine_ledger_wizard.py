# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class AmpathVaccineLedgerWizard(models.TransientModel):
    _name = 'ampath.vaccine.ledger.wizard'
    _description = 'Vaccine Stock Ledger'

    state = fields.Selection(
        [
            ('criteria', 'Criteria'),
            ('preview', 'Preview'),
        ],
        default='criteria',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        required=True,
        default=fields.Date.context_today,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Antigen / Diluent',
        domain=(
            "[('type', '=', 'product'), "
            "'|', ('x_ampath_vaccine', '=', True), "
            "('categ_id.x_ampath_vaccine_category', '=', True)]"
        ),
        help='Leave empty to include all vaccine products with movements.',
    )
    preview_html = fields.Html(readonly=True, sanitize=False)
    report_pdf_name = fields.Char(readonly=True)

    def action_back_to_criteria(self):
        self.ensure_one()
        self.write({'state': 'criteria', 'preview_html': False})
        return self._reopen()

    def action_preview(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('Date from must be on or before date to.'))
        html = self._build_ledger_html()
        self.write(
            {
                'state': 'preview',
                'preview_html': html,
                'report_pdf_name': 'Vaccine-Stock-Ledger-%s-%s'
                % (self.date_from, self.date_to),
            }
        )
        return self._reopen()

    def action_print_pdf(self):
        self.ensure_one()
        if self.state != 'preview':
            self.action_preview()
        return self.env.ref(
            'ampath_billing.action_report_vaccine_ledger'
        ).report_action(self)

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _voucher_domain(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.product_id:
            domain.append(('line_ids.product_id', '=', self.product_id.id))
        return domain

    def _ledger_rows_by_product(self):
        """Return ordered dict product → list of row dicts with running balance."""
        self.ensure_one()
        Voucher = self.env['ampath.vaccine.picking']
        vouchers = Voucher.search(
            self._voucher_domain(),
            order='date asc, id asc',
        )
        by_product = defaultdict(list)
        for voucher in vouchers:
            for line in voucher.line_ids:
                if self.product_id and line.product_id != self.product_id:
                    continue
                receipts = issues = losses = 0.0
                if voucher.movement_type == 'receipt':
                    receipts = line.qty
                elif voucher.movement_type == 'issue':
                    issues = line.qty
                else:
                    losses = line.qty
                by_product[line.product_id].append(
                    {
                        'date': voucher.date,
                        'source_dest': voucher.source_dest or '',
                        'receipts': receipts,
                        'issues': issues,
                        'losses': losses,
                        'vvm_stage': line.vvm_stage or '',
                        'lot': line.lot_id.name if line.lot_id else '',
                        'expiry': line.expiry_date,
                        'voucher': voucher.name,
                        'delta': receipts - issues - losses,
                    }
                )
        # Opening balance = stock in vaccine store before date_from
        result = {}
        for product, rows in by_product.items():
            opening = self._opening_balance(product)
            balance = opening
            enriched = []
            if opening:
                enriched.append(
                    {
                        'date': self.date_from,
                        'source_dest': _('Opening balance'),
                        'receipts': 0.0,
                        'issues': 0.0,
                        'losses': 0.0,
                        'vvm_stage': '',
                        'lot': '',
                        'expiry': False,
                        'voucher': '',
                        'balance': opening,
                    }
                )
            for row in rows:
                balance += row['delta']
                row['balance'] = balance
                enriched.append(row)
            result[product] = enriched
        return result

    def _opening_balance(self, product):
        self.ensure_one()
        Location = self.env['stock.location']
        stores = Location.search(
            [
                ('x_ampath_vaccine_store', '=', True),
                ('company_id', 'in', [self.company_id.id, False]),
            ]
        )
        if not stores:
            return 0.0
        # Reconstruct: all done voucher lines for this product before date_from
        lines = self.env['ampath.vaccine.picking.line'].search(
            [
                ('picking_id.state', '=', 'done'),
                ('picking_id.company_id', '=', self.company_id.id),
                ('picking_id.date', '<', self.date_from),
                ('product_id', '=', product.id),
            ]
        )
        balance = 0.0
        for line in lines:
            mt = line.picking_id.movement_type
            if mt == 'receipt':
                balance += line.qty
            else:
                balance -= line.qty
        return balance

    def _build_ledger_html(self):
        self.ensure_one()
        sections = self._ledger_rows_by_product()
        if not sections:
            return (
                '<p>%s</p>'
                % _(
                    'No vaccine picking movements in this period for the selected criteria.'
                )
            )
        parts = [
            '<h3>%s</h3>' % _('Vaccine Stock Ledger'),
            '<p><strong>%s:</strong> %s<br/>'
            '<strong>%s:</strong> %s — %s</p>'
            % (
                _('Facility'),
                self.company_id.display_name,
                _('Period'),
                format_date(self.env, self.date_from),
                format_date(self.env, self.date_to),
            ),
        ]
        for product, rows in sections.items():
            parts.append('<h4>%s</h4>' % product.display_name)
            parts.append(
                '<table class="table table-sm table-bordered">'
                '<thead><tr>'
                '<th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
                '<th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th>'
                '</tr></thead><tbody>'
                % (
                    _('Date'),
                    _('Source/Destination'),
                    _('Receipts'),
                    _('Issues'),
                    _('Losses'),
                    _('VVM'),
                    _('Lot/Batch'),
                    _('Expiry'),
                    _('Balance'),
                    _('Voucher'),
                )
            )
            for row in rows:
                expiry = (
                    format_date(self.env, fields.Date.to_date(row['expiry']))
                    if row['expiry']
                    else ''
                )
                parts.append(
                    '<tr>'
                    '<td>%s</td><td>%s</td>'
                    '<td>%s</td><td>%s</td><td>%s</td>'
                    '<td>%s</td><td>%s</td><td>%s</td>'
                    '<td>%s</td><td>%s</td>'
                    '</tr>'
                    % (
                        format_date(self.env, row['date']),
                        row['source_dest'] or '',
                        self._fmt_qty(row['receipts']),
                        self._fmt_qty(row['issues']),
                        self._fmt_qty(row['losses']),
                        row['vvm_stage'] or '',
                        row['lot'] or '',
                        expiry,
                        self._fmt_qty(row['balance']),
                        row['voucher'] or '',
                    )
                )
            parts.append('</tbody></table>')
        return ''.join(parts)

    @staticmethod
    def _fmt_qty(qty):
        if not qty:
            return ''
        if abs(qty - int(qty)) < 1e-6:
            return str(int(qty))
        return '%.2f' % qty
