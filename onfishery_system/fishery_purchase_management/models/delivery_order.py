from odoo import models, fields, api
from odoo.exceptions import UserError


class DeliveryOrderExtended(models.Model):
    _inherit = 'stock.picking'

    purchase_request_id = fields.Many2one('purchase.request', string='Referensi PR')
    pool_distribution_ids = fields.One2many('delivery.order.pool.distribution', 'delivery_order_id',
                                            string='Distribusi Kolam')
    delivery_address = fields.Text(string='Detail Address')

    def action_create_receipt_report(self):
        """
        """
        # Pastikan picking sudah validated
        if self.state != 'done':
            raise UserError("Laporan penerimaan barang hanya bisa dicetak setelah transfer divalidasi.")

        # Cetak laporan
        return self.env.ref('fishery_purchase_management.stock_picking_receipt_report_action').report_action(self)


class DeliveryOrderPoolDistribution(models.Model):
    _name = 'delivery.order.pool.distribution'
    _description = 'Distribusi Kolam pada Delivery Order'

    delivery_order_id = fields.Many2one('stock.picking', string='Delivery Order')
    pool_id = fields.Many2one('fishery.pool', string='Kolam')
    investor_id = fields.Many2one('res.investor', string='Investor')
    product_id = fields.Many2one('product.product', string='Produk')
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id')
    quantity = fields.Float(string='Kuantitas')

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    distribution_type = fields.Selection([
        ('pool', 'Pool Distribution'),
        ('investor', 'Investor Distribution')
    ], string='Distribution Type', compute='_compute_distribution_type', store=True)

    @api.depends('pool_id', 'investor_id')
    def _compute_distribution_type(self):
        for record in self:
            record.distribution_type = 'pool' if record.pool_id else 'investor'