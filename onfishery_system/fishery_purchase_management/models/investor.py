from odoo import models, fields, api

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