from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _

import logging

_logger = logging.getLogger(__name__)


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _description = 'Permintaan Pembelian'

    request_type = fields.Selection([
        ('investor', 'Investor PR'),
        ('project', 'Project PR')
    ], string='Request Type', default='investor', required=True)

    # Field untuk Investor PR
    investor_id = fields.Many2one('res.investor', string='Investor')
    pool_ids = fields.Many2many('fishery.pool', string='Kolam', domain="[('investor_id', '=', investor_id)]")

    # Field untuk Project PR
    project_id = fields.Many2one('res.comproject', string='Project')
    company_ids = fields.Many2many('res.investor', string='Companies', domain="[('project_id', '=', project_id)]")

    name = fields.Char(string='Nomor PR', required=True, copy=False, readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code('purchase.request'))

    # investor_id = fields.Many2one('res.investor', string='Investor', required=True)
    # pool_ids = fields.Many2many('fishery.pool', string='Kolam', domain="[('investor_id', '=', investor_id)]")

    picking_id = fields.Many2one('stock.picking', string='Delivery Order')
    created_date = fields.Datetime(
        string='Created Date',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        help='Select date and time'
    )

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

    po_count = fields.Integer(string='PO Count', compute='_compute_po_count')

    def _compute_po_count(self):
        for record in self:
            record.po_count = self.env['purchase.order'].search_count([
                ('purchase_request_id', '=', record.id)
            ])

    # Method untuk action view PO
    def action_view_po(self):
        self.ensure_one()
        pos = self.env['purchase.order'].search([
            ('purchase_request_id', '=', self.id)
        ])
        action = {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', pos.ids)],
        }
        if len(pos) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': pos.id,
            })
        return action

    delivery_count = fields.Integer(compute='_compute_delivery_count')

    @api.onchange('request_type')
    def _onchange_request_type(self):
        # Reset nilai field ketika type berubah
        if self.request_type == 'project':
            self.investor_id = False
            self.pool_ids = [(5, 0, 0)]
        else:
            self.project_id = False
            self.company_ids = [(5, 0, 0)]

    @api.onchange('investor_id')
    def _onchange_investor_id(self):
        if self.request_type == 'investor' and self.investor_id:
            self.pool_ids = [(6, 0, self.investor_id.pools_ids.ids)]

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.request_type == 'project' and self.project_id:
            companies = self.env['res.investor'].search([('project_id', '=', self.project_id.id)])
            self.company_ids = [(6, 0, companies.ids)]

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
        # pickings = self._create_delivery_order()
        # if pickings:
        self.write({
            'state': 'po_created',
        })
        return self.action_view_po()
        #     # Jika ingin menampilkan semua DO yang dibuat
        #     return {
        #         'type': 'ir.actions.act_window',
        #         'name': 'Delivery Orders',
        #         'res_model': 'stock.picking',
        #         'view_mode': 'tree,form',
        #         'domain': [('id', 'in', [p.id for p in pickings])],
        #         'target': 'current',
        #     }
        # else:
        #     raise UserError('Failed to create Delivery Order')

    def action_done(self):
        self.write({'state': 'done'})

    def _create_detail_lines(self):
        self.ensure_one()
        if self.request_type == 'investor':
            # Logic untuk PR Investor
            for item in self.item_line_ids:
                for pool in self.pool_ids:
                    self.env['purchase.request.line'].create({
                        'request_id': self.id,
                        'pool_id': pool.id,
                        'product_id': item.product_id.id,
                        'product_uom_qty': item.quantity
                    })
        else:
            # Logic untuk PR Project
            for item in self.item_line_ids:
                qty_per_company = item.quantity / len(self.company_ids)
                for company in self.company_ids:
                    self.env['purchase.request.line'].create({
                        'request_id': self.id,
                        'reference_id': company.id,
                        'product_id': item.product_id.id,
                        'product_uom_qty': qty_per_company
                    })

    def _create_purchase_order(self):

        if self.request_type == 'investor':
            # Logic PO untuk PR Investor
            # Logic PO untuk PR Investor
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
                # Ambil sequence dari investor
                sequence = self.investor_id.sequence_id
                if not sequence:
                    raise UserError(f'No sequence found for investor {self.investor_id.name}')

                name = sequence.next_by_id()

                po = self.env['purchase.order'].create({
                    'partner_id': vendor.id,
                    'purchase_request_id': self.id,
                    'origin': self.name,
                    'name': name,
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
                    for line in lines:
                        self.env['purchase.order.pool.distribution'].create({
                            'purchase_id': po.id,
                            'pool_id': line.pool_id.id,
                            'product_id': line.product_id.id,
                            'quantity': line.product_uom_qty,
                        })
        else:
            # Logic untuk PR Project - PO per investor per vendor
            vendor_investor_items = {}
            for line in self.request_line_ids:
                if not line.product_id.seller_ids:
                    raise UserError(f'No vendor defined for product: {line.product_id.name}')
                vendor = line.product_id.seller_ids[0].partner_id
                investor = line.reference_id
                if vendor not in vendor_investor_items:
                    vendor_investor_items[vendor] = {}
                if investor not in vendor_investor_items[vendor]:
                    vendor_investor_items[vendor][investor] = {}
                if line.product_id not in vendor_investor_items[vendor][investor]:
                    vendor_investor_items[vendor][investor][line.product_id] = []
                vendor_investor_items[vendor][investor][line.product_id].append(line)

            for vendor, investor_data in vendor_investor_items.items():
                for investor, products in investor_data.items():
                    # Ambil sequence dari investor
                    sequence = investor.sequence_id
                    if not sequence:
                        raise UserError(f'No sequence found for investor {investor.name}')

                    name = sequence.next_by_id()

                    po = self.env['purchase.order'].create({
                        'partner_id': vendor.id,
                        'purchase_request_id': self.id,
                        'origin': self.name,
                        'name': name,
                        'investor_id': investor.id,
                        'notes': f'Project: {self.project_id.name}',
                    })

                    # Create lines untuk setiap produk
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
                        # Create distribution
                        for line in lines:
                            self.env['purchase.order.pool.distribution'].create({
                                'purchase_id': po.id,
                                'investor_id': line.reference_id.id,
                                'product_id': line.product_id.id,
                                'quantity': line.product_uom_qty,
                            })

                _logger.info("Finished creating POs")

    # Tambahkan function unlink
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_('You cannot delete a purchase request that is not in draft state.'))
        return super(PurchaseRequest, self).unlink()

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

        if self.request_type == 'investor':
            # Logic existing untuk PR Investor
            pool_areas = {}
            for pool in self.pool_ids:
                if pool.area_id not in pool_areas:
                    pool_areas[pool.area_id] = []
                pool_areas[pool.area_id].append(pool)

            for area, pools in pool_areas.items():
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

                area_lines = self.request_line_ids.filtered(lambda l: l.pool_id in pools)
                for product_lines in self._group_by_product(area_lines):
                    product = product_lines[0].product_id
                    total_qty = sum(l.product_uom_qty for l in product_lines)

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

                    for line in product_lines:
                        self.env['delivery.order.pool.distribution'].create({
                            'delivery_order_id': picking.id,
                            'pool_id': line.pool_id.id,
                            'product_id': line.product_id.id,
                            'quantity': line.product_uom_qty,
                        })

        else:
            # Logic untuk PR Project
            for investor in self.company_ids:
                picking = self.env['stock.picking'].sudo().create({
                    'picking_type_id': picking_type_out.id,
                    'origin': self.name,
                    'location_id': picking_type_out.default_location_src_id.id,
                    'location_dest_id': customers_location.id,
                    'company_id': self.company_id.id,
                    'move_type': 'direct',
                    'partner_id': investor.id,
                    'purchase_request_id': self.id,
                    'delivery_address': investor.investor_address,
                    'state': 'draft',
                })
                pickings.append(picking)

                investor_lines = self.request_line_ids.filtered(lambda l: l.reference_id.id == investor.id)
                for product_lines in self._group_by_product(investor_lines):
                    product = product_lines[0].product_id
                    total_qty = sum(l.product_uom_qty for l in product_lines)

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

                    for line in product_lines:
                        self.env['delivery.order.pool.distribution'].create({
                            'delivery_order_id': picking.id,
                            'investor_id': line.reference_id.id,  # Gunakan investor sebagai pool
                            'product_id': line.product_id.id,
                            'quantity': line.product_uom_qty,
                        })

            # Confirm semua pickings
        for picking in pickings:
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

    # Field untuk membedakan tipe
    reference_type = fields.Selection([
        ('pool', 'Pool'),
        ('investor', 'Investor')
    ], compute='_compute_reference_type', store=True)

    # Ganti company_id menjadi investor_id
    investor_id = fields.Many2one('res.investor', string='Investor')

    alternate_uom_qty = fields.Float(string='Alternate Quantity')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True
    )
    reference_id = fields.Many2one('res.investor', string='Companies')

    # Tambahkan compute field untuk menampilkan pool/investor
    display_reference = fields.Char(string='Reference', compute='_compute_display_reference', store=True)

    @api.depends('request_id.request_type', 'pool_id', 'reference_id')
    def _compute_display_reference(self):
        for record in self:
            if record.request_id.request_type == 'investor':
                record.display_reference = record.pool_id.name if record.pool_id else ''
            else:
                record.display_reference = record.reference_id.name if record.reference_id else ''
