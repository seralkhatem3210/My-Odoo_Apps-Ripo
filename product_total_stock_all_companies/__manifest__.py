{
    "name": "Multi-Company Auto Stock Fulfillment",
    "version": "18.0.1.0.0",
    "summary": "Auto fulfill stock shortages across warehouses and companies",
    "description": "Automatically resolve stock shortages using internal and intercompany transfers with full automation.",
    "category": "Inventory/Inventory",
    "author": "Sirelkhatim",
    "website": "https://yourcompany.com",
    "license": "LGPL-3",
    "price": 152.0,
    "depends": [
        "stock",
        "product",
        "sale_stock",
        "purchase_stock",
        "sale_management",
        "purchase",
    ],
    "data": [
        "views/product_product_views.xml",
        "views/auto_fulfillment_log_views.xml",
        "views/stock_picking_views.xml", 
        "views/auto_fulfillment_dashboard_views.xml",       
        "security/ir.model.access.csv",       
    ],


    'assets': {
        'web.assets_backend': [
            'product_total_stock_all_companies/static/src/js/auto_fulfillment_dashboard.js',
            'product_total_stock_all_companies/static/src/xml/auto_fulfillment_dashboard.xml',
            'product_total_stock_all_companies/static/src/scss/auto_fulfillment_dashboard.scss',
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png"
    ],
    "installable": True,
    "application": True,
}
