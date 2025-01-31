{
    'name': 'Accurate Export',
    'version': '1.0',
    'category': 'Purchase',
    'summary': 'Export Purchase Orders to Accurate 5 XML format',
    'description': """
        This module adds functionality to export Purchase Orders to Accurate 5 XML format.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}