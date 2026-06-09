# -*- coding: utf-8 -*-
{
    'name': "Branch Inventory",

    'summary': "Branch inventory menus for internal transfers and stock.",

    'description': """
Branch inventory menus for stock operations.
    """,

    'author': "KIO",
    'website': "",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Branch Inventory',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/branch_inventory_rules.xml',
        'reports/branch_product_stock_report.xml',
        'views/physical_inventory_views.xml',
        'views/views.xml',
        'views/warehouse_user_views.xml',
        # 'wizards/branch_product_stock_report_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kio_branch_inventory/static/src/js/branch_physical_inventory_barcode.js',
        ],
    },
    'application': True,
    'installable': True,
}
