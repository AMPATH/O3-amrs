# -*- coding: utf-8 -*-

import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AmpathPrescriptionPrintWizard(models.TransientModel):
    _name = 'ampath.prescription.print.wizard'
    _description = 'Confirm prescription print'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale order',
        required=True,
        ondelete='cascade',
    )
    line_ids = fields.One2many(
        'ampath.prescription.print.wizard.line',
        'wizard_id',
        string='Medications',
        help='Uncheck rows you do not want on the prescription PDF.',
    )
    prescription_pdf = fields.Binary(
        string='Prescription PDF',
        attachment=False,
    )
    prescription_pdf_name = fields.Char(string='PDF file name')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get('default_sale_order_id')
        if order_id and 'line_ids' in fields_list:
            order = self.env['sale.order'].browse(order_id)
            eligible = order._ampath_prescription_lines()
            if eligible:
                res['line_ids'] = [
                    (0, 0, {'sale_line_id': line.id, 'selected': True})
                    for line in eligible
                ]
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure nested lines always carry sale_line_id (web client can drop readonly fields)."""
        for vals in vals_list:
            order_id = vals.get('sale_order_id') or self.env.context.get(
                'default_sale_order_id'
            )
            if not order_id:
                continue
            order = self.env['sale.order'].browse(order_id)
            if not order.exists():
                continue
            eligible = order._ampath_prescription_lines()
            cmds = vals.get('line_ids') or []
            fixed = []
            for cmd in cmds:
                if (
                    isinstance(cmd, (list, tuple))
                    and len(cmd) >= 3
                    and cmd[0] == 0
                    and isinstance(cmd[2], dict)
                ):
                    sub = dict(cmd[2])
                    sid = sub.get('sale_line_id')
                    if not sid or sid not in eligible.ids:
                        continue
                    fixed.append(
                        (
                            0,
                            0,
                            {
                                'sale_line_id': sid,
                                'selected': bool(sub.get('selected', True)),
                            },
                        )
                    )
                else:
                    fixed.append(cmd)
            has_create = any(
                isinstance(c, (list, tuple)) and c and c[0] == 0 for c in fixed
            )
            if eligible and not has_create:
                vals['line_ids'] = [
                    (0, 0, {'sale_line_id': line.id, 'selected': True})
                    for line in eligible
                ]
            elif fixed:
                vals['line_ids'] = fixed
        return super().create(vals_list)

    def _ampath_prescription_eligible_lines(self):
        self.ensure_one()
        return self.sale_order_id._ampath_prescription_lines()

    def action_print_prescription_pdf(self):
        self.ensure_one()
        eligible = self._ampath_prescription_eligible_lines()
        if not eligible:
            raise UserError(
                _(
                    'There are no medication lines on this order. '
                    'Consultations and procedures are excluded; only stocked '
                    'or consumable products (medications) can appear here.'
                )
            )
        lines = self.line_ids.filtered('selected').mapped('sale_line_id')
        if not lines:
            raise UserError(
                _('Select at least one medication line (use the Print column).')
            )
        if not (lines <= eligible):
            raise UserError(_('Only medication lines from this order can be printed.'))
        lines.write({'ampath_prescription_printed': True})
        order = self.sale_order_id.sudo()
        report = self.env.ref('ampath_billing.action_report_sale_order_prescription')
        safe_name = (order.name or 'order').replace('/', '-')
        pdf_name = 'Prescription-%s.pdf' % safe_name
        try:
            order.write({'ampath_prescription_pdf_line_ids': [(6, 0, lines.ids)]})
            pdf_content, _ctype = (
                self.env['ir.actions.report']
                .with_context(report_pdf_no_attachment=True)
                ._render_qweb_pdf(report, order.ids, data=None)
            )
            self.write(
                {
                    'prescription_pdf': base64.b64encode(pdf_content),
                    'prescription_pdf_name': pdf_name,
                }
            )
        finally:
            order.write({'ampath_prescription_pdf_line_ids': [(5, 0, 0)]})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Prescription'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'views': [
                (
                    self.env.ref(
                        'ampath_billing.view_ampath_prescription_print_wizard_form'
                    ).id,
                    'form',
                )
            ],
            'flags': {'mode': 'readonly'},
        }

    def action_download_prescription_pdf(self):
        """Open PDF in a new browser tab (GET has no custom payload; binary is on wizard)."""
        self.ensure_one()
        if not self.prescription_pdf:
            raise UserError(_('Generate the prescription first.'))
        att = self.env['ir.attachment'].sudo().create(
            {
                'name': self.prescription_pdf_name or 'Prescription.pdf',
                'type': 'binary',
                'datas': self.prescription_pdf,
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
