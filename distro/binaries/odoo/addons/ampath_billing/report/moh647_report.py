# -*- coding: utf-8 -*-

from odoo import api, models


class ReportMoh647(models.AbstractModel):
    _name = 'report.ampath_billing.report_moh647_document'
    _description = 'MOH 647 Facility Tracer HPT Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['ampath.moh647.report.wizard'].browse(docids)
        docs_data = []
        for wizard in wizards:
            docs_data.append(wizard._report_context())
        return {
            'doc_ids': docids,
            'doc_model': 'ampath.moh647.report.wizard',
            'docs': wizards,
            'docs_data': docs_data,
        }
