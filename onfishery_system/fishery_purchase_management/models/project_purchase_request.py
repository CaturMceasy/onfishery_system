from odoo import models, fields, api
from datetime import datetime
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProjectPurchaseRequest(models.Model):
    _name = 'project.purchase.request'
    _description = 'Project Purchase Request'

    name = fields.Char(string='Nomor PR', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('project.purchase.request'))
    project_id = fields.Many2one('res.comproject', string='Project', required=True)
    company_ids = fields.Many2many('res.investor', string='Companies',
                                   domain="[('project_id', '=', project_id)]")
    picking_id = fields.Many2one('stock.picking', string='Delivery Order')
    created_date = fields.Datetime(
        string='Created Date',
        required=True,
        readonly=True,
        default=fields.Datetime.now
    )
    # category = fields.Selection([
    #     ('feed', 'Pakan'),
    #     ('supplement', 'Saprotam'),
    #     ('seeds', 'Benur')
    # ], string='Kategori', required=True)
    item_line_ids = fields.One2many('project.purchase.request.item.line', 'request_id', string='List Item')
    request_line_ids = fields.One2many('project.purchase.request.line', 'request_id', string='Detail Permintaan')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Dikonfirmasi'),
        ('po_created', 'PO Dibuat'),
        ('done', 'Selesai')
    ], default='draft', string='Status')
    repeat_period = fields.Selection([
        ('monthly', 'Bulanan'),
        ('quarterly', '3 Bulanan'),
        ('semi_annual', '6 Bulanan')
    ], string='Periode Pengulangan')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    delivery_count = fields.Integer(compute='_compute_delivery_count')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.company_ids = [(6, 0, self.project_id.company_list.ids)]

    def action_confirm(self):
        self._create_detail_lines()
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.ensure_one()
        self.request_line_ids.unlink()
        self.write({'state': 'draft'})

    def _compute_delivery_count(self):
        for record in self:
            record.delivery_count = self.env['stock.picking'].search_count([
                ('origin', '=', record.name)
            ])

    def action_view_delivery(self):
        self.ensure_one()
        deliveries = self.env['stock.picking'].search([
            ('origin', '=', self.name)
        ])
        action = {
            'name': 'Delivery Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', deliveries.ids)],
            'context': {'default_origin': self.name}
        }
        if len(deliveries) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': deliveries.id,
            })
        return action

    def _create_detail_lines(self):
        for item in self.item_line_ids:
            qty_per_company = item.quantity / len(self.company_ids)
            for company in self.company_ids:
                self.env['project.purchase.request.line'].create({
                    'request_id': self.id,
                    'company_id': company.id,
                    'product_id': item.product_id.id,
                    'product_uom_qty': qty_per_company
                })

    def _create_purchase_orders(self):
        vendor_items = {}
        # Mengelompokkan item berdasarkan vendor dan investor
        for line in self.request_line_ids:
            if not line.product_id.seller_ids:
                raise UserError(f'No vendor defined for product: {line.product_id.name}')

            vendor = line.product_id.seller_ids[0].partner_id
            investor = line.company_id  # ini adalah res.investor

            if vendor not in vendor_items:
                vendor_items[vendor] = {}
            if line.product_id not in vendor_items[vendor]:
                vendor_items[vendor][line.product_id] = []
            vendor_items[vendor][line.product_id].append(line)

        created_pos = []
        # Membuat PO untuk setiap vendor
        for vendor, products in vendor_items.items():
            po = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'purchase_request_id': self.id,  # Menggunakan field yang sama
                'origin': self.name,
                'notes': f'Project: {self.project_id.name}\nInvestor: {investor.name}',
            })
            created_pos.append(po.id)

            # Membuat PO lines
            for product, lines in products.items():
                total_qty = sum(line.product_uom_qty for line in lines)
                seller = product.seller_ids.filtered(lambda s: s.partner_id == vendor)[:1]
                if not seller:
                    raise UserError(f'No price defined for product: {product.name} and vendor: {vendor.name}')

                po.order_line.create({
                    'order_id': po.id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_qty': total_qty,
                    'product_uom': product.uom_id.id,
                    'price_unit': seller.price,
                    'date_planned': fields.Datetime.now(),
                })

                # Create distribution untuk setiap line
                for line in lines:
                    self.env['purchase.order.pool.distribution'].create({
                        'purchase_id': po.id,
                        'pool_id': line.company_id.id,  # investor sebagai pool
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                    })

        return self.env['purchase.order'].browse(created_pos)

    def action_po_created(self):
        purchase_orders = self._create_purchase_orders()
        if purchase_orders:
            self.write({'state': 'po_created'})
            return {
                'type': 'ir.actions.act_window',
                'name': 'Purchase Orders',
                'res_model': 'purchase.order',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', purchase_orders.ids)],
                'target': 'current',
            }
        else:
            raise UserError('Failed to create Purchase Orders')

    def action_done(self):
        self.write({'state': 'done'})


class ProjectPurchaseRequestItemLine(models.Model):
    _name = 'project.purchase.request.item.line'
    _description = 'List Item PR Project'

    request_id = fields.Many2one('project.purchase.request')
    product_id = fields.Many2one('product.product', required=True)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id')
    quantity = fields.Float('Quantity')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True
    )


class ProjectPurchaseRequestLine(models.Model):
    _name = 'project.purchase.request.line'
    _description = 'Detail Permintaan PR Project'

    request_id = fields.Many2one('project.purchase.request')
    company_id = fields.Many2one('res.investor')  # Changed from res.company to res.investor
    product_id = fields.Many2one('product.product')
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id')
    product_uom_qty = fields.Float('Quantity')
    product_uom_category_id = fields.Many2one(
        'uom.category',
        related='product_id.uom_id.category_id',
        readonly=True
    )
    alternate_uom_id = fields.Many2one(
        'uom.uom',
        string='Alternate UoM',
        domain="[('category_id', '=', product_uom_category_id)]"
    )
    alternate_uom_qty = fields.Float(string='Alternate Quantity')