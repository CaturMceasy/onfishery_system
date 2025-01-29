from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Permintaan Pembelian'

    name = fields.Char(string='Nomor PR', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('purchase.request'))

    investor_id = fields.Many2one('res.investor', string='Investor', required=True)
    pool_ids = fields.Many2many('fishery.pool', string='Kolam', domain="[('investor_id', '=', investor_id)]")
    picking_id = fields.Many2one('stock.picking', string='Delivery Order')
    created_date = fields.Datetime(
        string='Created Date',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        help='Select date and time'
    )

    category = fields.Selection([
        ('feed', 'Pakan'),
        ('supplement', 'Saprotam'),
        ('seeds', 'Benur')
    ], string='Kategori', required=True)

    item_line_ids = fields.One2many('purchase.request.item.line', 'request_id', string='List Item')
    request_line_ids = fields.One2many('purchase.request.line', 'request_id', string='Detail Permintaan')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Dikonfirmasi'),
        ('po_created', 'PO Dibuat'),
        ('done', 'Selesai')
    ], default='draft')

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

    @api.onchange('investor_id')
    def _onchange_investor_id(self):
        if self.investor_id:
            self.pool_ids = [(6, 0, self.investor_id.pools_ids.ids)]

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
                ('purchase_request_id', '=', record.id)
            ])

    def action_view_delivery(self):
        self.ensure_one()
        deliveries = self.env['stock.picking'].search([
            ('purchase_request_id', '=', self.id)
        ])
        action = {
            'name': 'Delivery Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', deliveries.ids)],
        }
        if len(deliveries) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': deliveries.id,
            })
        return action

    def action_po_created(self):
        self._create_purchase_order()
        pickings = self._create_delivery_order()
        if pickings:
            self.write({
                'state': 'po_created',
            })
            # Jika ingin menampilkan semua DO yang dibuat
            return {
                'type': 'ir.actions.act_window',
                'name': 'Delivery Orders',
                'res_model': 'stock.picking',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', [p.id for p in pickings])],
                'target': 'current',
            }
        else:
            raise UserError('Failed to create Delivery Order')

    def action_done(self):
        self.write({'state': 'done'})

    def _create_detail_lines(self):
        for item in self.item_line_ids:
            for pool in self.pool_ids:
                self.env['purchase.request.line'].create({
                    'request_id': self.id,
                    'pool_id': pool.id,
                    'product_id': item.product_id.id,
                    'product_uom_qty': item.quantity
                })

    def _create_purchase_order(self):
        vendor_items = {}
        for line in self.request_line_ids:
            if line.product_id.seller_ids:
                vendor = line.product_id.seller_ids[0].partner_id
                if vendor not in vendor_items:
                    vendor_items[vendor] = {}
                if line.product_id not in vendor_items[vendor]:
                    vendor_items[vendor][line.product_id] = []
                vendor_items[vendor][line.product_id].append(line)

        for vendor, products in vendor_items.items():
            po = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'purchase_request_id': self.id,
                'origin': self.name,
                'notes': f'Investor: {self.investor_id.name}\nAlamat Pengiriman: {self.investor_id.investor_address}',
            })

            for product, lines in products.items():
                total_qty = sum(line.product_uom_qty for line in lines)
                po.order_line.create({
                    'order_id': po.id,
                    'product_id': product.id,
                    'product_qty': total_qty,
                    'product_uom': product.uom_id.id,
                    'price_unit': product.seller_ids[0].price,
                    'date_planned': fields.Datetime.now(),
                    'name': product.name,
                })

                # Create pool distribution untuk setiap line
                for line in lines:
                    self.env['purchase.order.pool.distribution'].create({
                        'purchase_id': po.id,
                        'pool_id': line.pool_id.id,
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                    })

    def _create_delivery_order(self):
        picking_type_out = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if not picking_type_out:
            raise UserError('No outgoing picking type found')

        pool_areas = {}
        for pool in self.pool_ids:
            if pool.area_id not in pool_areas:
                pool_areas[pool.area_id] = []
            pool_areas[pool.area_id].append(pool)

        pickings = []
        customers_location = self.env.ref('stock.stock_location_customers')

        for area, pools in pool_areas.items():
            # Create picking
            picking = self.env['stock.picking'].sudo().create({
                'picking_type_id': picking_type_out.id,
                'origin': self.name,
                'location_id': picking_type_out.default_location_src_id.id,
                'location_dest_id': customers_location.id,
                'company_id': self.company_id.id,
                'move_type': 'direct',
                'partner_id': area.partner_id.id if area.partner_id else self.investor_id.id,
                'purchase_request_id': self.id,
                'delivery_address': f"Area: {area.name}\n{area.address}",
                'state': 'draft',
            })
            pickings.append(picking)

            # Filter lines untuk area ini
            area_lines = self.request_line_ids.filtered(lambda l: l.pool_id in pools)

            # Group by product untuk stock moves
            for product_lines in self._group_by_product(area_lines):
                product = product_lines[0].product_id
                total_qty = sum(l.product_uom_qty for l in product_lines)

                # Create stock move
                move = self.env['stock.move'].sudo().create({
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom': product.uom_id.id,
                    'product_uom_qty': total_qty,
                    'picking_id': picking.id,
                    'location_id': picking_type_out.default_location_src_id.id,
                    'location_dest_id': customers_location.id,
                    'picking_type_id': picking_type_out.id,
                    'company_id': self.company_id.id,
                    'state': 'draft',
                })

                # Create pool distribution details
                for line in product_lines:
                    self.env['delivery.order.pool.distribution'].create({
                        'delivery_order_id': picking.id,
                        'pool_id': line.pool_id.id,
                        'product_id': line.product_id.id,
                        'quantity': line.product_uom_qty,
                    })

            picking.action_confirm()

        return pickings

    def _group_by_product(self, lines=None):
        if lines is None:
            lines = self.request_line_ids
        products = {}
        for line in lines:
            if line.product_id not in products:
                products[line.product_id] = []
            products[line.product_id].append(line)
        return products.values()

    def _generate_distribution_note(self, lines):
        return '\n'.join([
            f"Kolam {line.pool_id.name}: {line.product_uom_qty} {line.product_uom_id.name}"
            for line in lines
        ])


class PurchaseRequestItemLine(models.Model):
    _name = 'purchase.request.item.line'
    _description = 'List Item PR'

    request_id = fields.Many2one('purchase.request')
    product_id = fields.Many2one('product.product', required=True)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id')
    quantity = fields.Float('Quantity')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True
    )


class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Detail Permintaan PR'

    request_id = fields.Many2one('purchase.request')
    pool_id = fields.Many2one('fishery.pool')
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
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True
    )
