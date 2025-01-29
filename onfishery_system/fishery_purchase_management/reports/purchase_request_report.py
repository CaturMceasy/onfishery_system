from odoo import models, api


class PurchaseRequestReport(models.AbstractModel):
    _name = 'report.fishery_purchase_management.report_purchase_request'

    @api.model
    def _get_report_values(self, docids, data=None):
        # Logika untuk mengambil data laporan
        docs = self.env['purchase.request'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.request',
            'docs': docs,
        }