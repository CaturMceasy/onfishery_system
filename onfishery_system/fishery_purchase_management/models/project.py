from odoo import models, fields, api


class CompanyProject(models.Model):
    _name = 'res.comproject'
    _description = 'Company Project'

    name = fields.Char(string='Project', required=True)
    code = fields.Char(string='Project Code')
    company_list = fields.One2many('res.investor', 'project_id', string='List Company')
    created_date = fields.Datetime(
        string='Created Date',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        help='Select date and time'
    )

    date_start = fields.Datetime(
        string='Date Start',
        required=True,
        # readonly=True,
        default=fields.Datetime.now,
        help='Select date and time'
    )

    # Relasi dengan res.partner
    partner_id = fields.Many2one('res.partner', string='Project Address', tracking=True)
    # Field related untuk menampilkan alamat dari partner
    street = fields.Char(related='partner_id.street', string='Street', readonly=False)
    zip = fields.Char(related='partner_id.zip', string='ZIP', readonly=False)
    city = fields.Char(related='partner_id.city', string='City', readonly=False)
    country_id = fields.Many2one(
        related='partner_id.country_id',
        string='Country',
        readonly=False
    )
    phone = fields.Char(related='partner_id.phone', string='Phone', readonly=False)
    mobile = fields.Char(related='partner_id.mobile', string='Mobile', readonly=False)
    email = fields.Char(related='partner_id.email', string='Email', readonly=False)

    @api.model
    def create(self, vals):
        # Jika tidak ada partner_id, buat contact baru
        if not vals.get('partner_id'):
            partner = self.env['res.partner'].create({
                'name': vals.get('name', ''),
                'street': vals.get('street'),
                'zip': vals.get('zip'),
                'city': vals.get('city'),
                'state_id': vals.get('state_id'),
                'country_id': vals.get('country_id'),
                'phone': vals.get('phone'),
                'mobile': vals.get('mobile'),
                'email': vals.get('email'),
                'type': 'project',  # Tipe contact untuk project
            })
            vals['partner_id'] = partner.id
        return super().create(vals)

    def write(self, vals):
        # Update partner jika ada perubahan pada nama project
        if vals.get('name'):
            for record in self:
                if record.partner_id:
                    record.partner_id.write({'name': vals['name']})
        return super().write(vals)
