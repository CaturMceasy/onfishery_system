from odoo import models, fields, api


class FisheryArea(models.Model):
    _name = 'fishery.area'
    _description = 'Area Kolam'

    name = fields.Char('Nama Area', required=True)
    address = fields.Text('Alamat')
    partner_id = fields.Many2one('res.partner', 'Contact Person')

class FisheryPool(models.Model):
    _name = 'fishery.pool'
    _description = 'Kolam Perikanan'

    name = fields.Char(string='Nama Kolam', required=True)
    investor_id = fields.Many2one('res.investor', string='Investor', required=True)
    initial_capacity = fields.Float(string='Capacity')
    area_id = fields.Many2one('fishery.area', string='Address', required=True)
    # area_id = fields.Many2one('res.partner', string='Area')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    def calculate_pool_needs(self, product_category):
        # Logika perhitungan kebutuhan
        needs = {}
        # Implementasi spesifik sesuai kategori
        return needs