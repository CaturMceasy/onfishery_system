{
    'name': 'Fishery Purchase Management',
    'version': '1.0',
    'category': 'Purchase',
    'summary': 'Manajemen Pembelian Perikanan',
    'description': 'Modul khusus manajemen pembelian untuk PT. ABC',
    'depends': ['purchase', 'stock', 'base', 'web'],
    'data': [
        'security/purchase_request_security.xml',
        'security/ir.model.access.csv',
        'views/investor_view.xml',
        'views/pool_view.xml',
        'views/purchase_request_view.xml',
        'views/purchase_order_view.xml',
        'views/delivery_order_view.xml',
        'views/partner_view.xml',
        'views/login_templates.xml',
        'data/purchase_request_sequence.xml',
        # 'data/project_purchase_request_sequence.xml',
        'wizard/purchase_request_wizard.xml',
        'views/report_purchase_order.xml',
        'views/report_purchase_order_receipt.xml',
        'views/report_receipt_order.xml',
        'views/favicon.xml',
        # 'views/project_purchase_request_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fishery_purchase_management/static/src/js/favicon.js',
        ],
    },
    'installable': True,
    'application': True,
}
