from odoo import models, fields, api

class CompanyProject(models.Model):
    _name = 'res.comproject'
    _description = 'Company Project'

    name = fields.Char(string='Project', required=True)
    code = fields.Char(string='Project Code')
    company_list = fields.One2many('res.investor','project_id',string='List Company')
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