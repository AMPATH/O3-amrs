# -*- coding: utf-8 -*-

from odoo import api, models


class ReportSaleOrderPrescription(models.AbstractModel):
    _name = 'report.ampath_billing.report_sale_order_prescription_document'
    _description = 'Prescription PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        orders = self.env['sale.order'].browse(docids)
        line_ids = data.get('prescription_line_ids')
        prescription_lines = {}
        for order in orders:
            pdf_lines = order.ampath_prescription_pdf_line_ids
            if pdf_lines:
                prescription_lines[order.id] = pdf_lines
            elif line_ids:
                selected = self.env['sale.order.line'].browse(line_ids)
                prescription_lines[order.id] = selected.filtered(
                    lambda l, o=order: l.order_id == o
                )
            else:
                prescription_lines[order.id] = order._ampath_prescription_lines()
        return {
            'doc_ids': docids,
            'doc_model': 'sale.order',
            'docs': orders,
            'prescription_lines': prescription_lines,
        }
