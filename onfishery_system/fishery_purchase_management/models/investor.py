from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta

class ResInvestor(models.Model):
    _name = 'res.investor'
    _description = 'Investor/CV'

    name = fields.Char(string='Nama Investor', required=True)
    pools_ids = fields.One2many('fishery.pool', 'investor_id', string='Kolam')
    total_pools = fields.Integer(compute='_compute_total_pools', store=True)
    partner_id = fields.Many2one('res.partner', string='Partner Related', required=True)
    investor_address = fields.Text(string='Alamat', compute='_compute_partner_address', store=True)
    project_id = fields.Many2one('res.comproject', string='Project', required=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    code = fields.Char(string='Investor Code', required=True, copy=False,
                       help='Kode investor 3 karakter untuk nomor PO. Contoh: ABB')
    sequence_id = fields.Many2one('ir.sequence', string='Purchase Order Sequence', copy=False)

    @api.model
    def create(self, vals):
        res = super(ResInvestor, self).create(vals)
        if not res.sequence_id and res.code:
            # Buat sequence baru dengan format yang diinginkan
            sequence = self.env['ir.sequence'].create({
                'name': f'PO Sequence for {res.name}',
                'code': f'purchase.order.{res.code.lower()}',
                'prefix': f'PO-{res.code}/%(year)s.%(month)s/',
                'padding': 4,
                'company_id': res.company_id.id,
                'use_date_range': True,  # Aktifkan date range untuk reset bulanan
            })
            # Buat date range untuk bulan ini
            current_date = fields.Date.today()
            self.env['ir.sequence.date_range'].create({
                'sequence_id': sequence.id,
                'date_from': current_date.replace(day=1),  # Awal bulan
                'date_to': current_date.replace(day=1, month=current_date.month % 12 + 1) - timedelta(days=1),
                # Akhir bulan
                'number_next': 1,
            })
            res.sequence_id = sequence.id
        return res

    @api.constrains('code')
    def _check_code(self):
        for record in self:
            if record.code:
                # Pastikan kode tepat 3 karakter
                if len(record.code) != 3:
                    raise UserError('Kode investor harus 3 karakter!')
                # Pastikan kode unik
                existing = self.search([
                    ('code', '=', record.code),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise UserError(f'Kode investor {record.code} sudah digunakan!')


    @api.depends('pools_ids')
    def _compute_total_pools(self):
        for record in self:
            record.total_pools = len(record.pools_ids)

    @api.depends('partner_id')
    def _compute_partner_address(self):
        for record in self:
            address_parts = []
            if record.partner_id:
                if record.partner_id.street:
                    address_parts.append(record.partner_id.street)
                if record.partner_id.street2:
                    address_parts.append(record.partner_id.street2)
                if record.partner_id.city:
                    address_parts.append(record.partner_id.city)
                if record.partner_id.state_id:
                    address_parts.append(record.partner_id.state_id.name)
                if record.partner_id.zip:
                    address_parts.append(record.partner_id.zip)
                if record.partner_id.country_id:
                    address_parts.append(record.partner_id.country_id.name)
            record.investor_address = '\n'.join(filter(None, address_parts))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = self.partner_id.name
