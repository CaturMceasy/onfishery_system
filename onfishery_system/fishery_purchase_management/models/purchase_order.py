from odoo import models, fields, api


class PurchaseOrderExtended(models.Model):
    _inherit = 'purchase.order'

    purchase_request_id = fields.Many2one('purchase.request', string='Purchase Request')
    investor_id = fields.Many2one('res.investor', string='PO from', compute='_compute_investor_id', store=True)
    pool_distribution_ids = fields.One2many('purchase.order.pool.distribution', 'purchase_id',
                                            string='Distribusi Kolam')

    @api.model
    def create(self, vals):
        if vals.get('investor_id'):
            investor = self.env['res.investor'].browse(vals['investor_id'])
            if investor and investor.sequence_id:
                # Gunakan sequence investor dengan format yang sudah ditentukan
                vals['name'] = investor.sequence_id.next_by_id()
                # Jika sequence untuk bulan ini belum ada, akan dibuat otomatis
            else:
                # Fallback ke sequence default jika tidak ada investor
                vals['name'] = self.env['ir.sequence'].next_by_code('purchase.order')
        return super(PurchaseOrderExtended, self).create(vals)

    @api.depends('purchase_request_id', 'purchase_request_id.investor_id', 'purchase_request_id.request_type')
    def _compute_investor_id(self):
        for po in self:
            if po.purchase_request_id.request_type == 'investor':
                po.investor_id = po.purchase_request_id.investor_id

    def _prepare_picking(self):
        res = super()._prepare_picking()
        if self.purchase_request_id and self.investor_id:
            res.update({
                'delivery_address': self.investor_id.investor_address,
                'purchase_request_id': self.purchase_request_id.id,
            })
        return res

    def button_confirm(self):
        res = super(PurchaseOrderExtended, self).button_confirm()
        # Update receipt yang baru dibuat
        picking = self.picking_ids.filtered(
            lambda x: x.state not in ['done', 'cancel'] and x.picking_type_code == 'incoming')
        if picking:
            picking.write({
                'delivery_address': self.investor_id.investor_address,
                'purchase_request_id': self.purchase_request_id.id,
            })
            # Copy distribusi kolam
            for dist in self.pool_distribution_ids:
                self.env['delivery.order.pool.distribution'].create({
                    'delivery_order_id': picking.id,
                    'pool_id': dist.pool_id.id,
                    'product_id': dist.product_id.id,
                    'quantity': dist.quantity,
                })
        return res

    def print_purchase_order_receipt(self):
        """
        Method untuk mencetak berita acara penerimaan barang
        """
        return self.env.ref('fishery_purchase_management.purchase_order_receipt_report_action').report_action(self)


class PurchaseOrderPoolDistribution(models.Model):
    _name = 'purchase.order.pool.distribution'
    _description = 'Distribusi Kolam pada Purchase Order'

    purchase_id = fields.Many2one('purchase.order', string='Purchase Order')
    pool_id = fields.Many2one('fishery.pool', string='Kolam')
    investor_id = fields.Many2one('res.investor', string='Investor')
    product_id = fields.Many2one('product.product', string='Produk')
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        related='product_id.uom_id',
        readonly=True,
        store=True
    )
    quantity = fields.Float(string='Quantity')

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
