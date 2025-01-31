from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    accurate_vendor_code = fields.Char(string='Kode Vendor Accurate')