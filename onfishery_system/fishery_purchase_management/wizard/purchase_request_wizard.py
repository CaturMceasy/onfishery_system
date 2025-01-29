from odoo import models, fields, api


class PurchaseRequestWizard(models.TransientModel):
    _name = 'purchase.request.wizard'
    _description = 'Wizard Pembuatan Purchase Request'

    investor_id = fields.Many2one('res.investor', string='Investor', required=True)
    pool_ids = fields.Many2many('fishery.pool', string='Kolam')
    category = fields.Selection([
        ('feed', 'Pakan'),
        ('supplement', 'Saprotam'),
        ('seeds', 'Benur')
    ], string='Kategori', required=True)
    repeat_period = fields.Selection([
        ('monthly', 'Bulanan'),
        ('quarterly', '3 Bulanan'),
        ('semi_annual', '6 Bulanan')
    ], string='Periode Pengulangan')

    def create_purchase_request(self):
        # Logika pembuatan purchase request otomatis
        purchase_request = self.env['purchase.request'].create({
            'investor_id': self.investor_id.id,
            'pool_ids': [(6, 0, self.pool_ids.ids)],
            'category': self.category,
            'repeat_period': self.repeat_period
        })

        # Tambahkan logika untuk membuat request lines
        for pool in self.pool_ids:
            # Contoh sederhana, bisa disesuaikan dengan kebutuhan spesifik
            self.env['purchase.request.line'].create({
                'request_id': purchase_request.id,
                'pool_id': pool.id,
                # Tambahkan logika penentuan produk dan kuantitas
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': purchase_request.id,
            'target': 'current'
        }