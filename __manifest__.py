{
    "name": "Product Total Stock All Companies",
    "version": "18.0.1.0.0",
    "summary": "Show total stock across all companies and auto fulfill shortages",
    "category": "Inventory/Inventory",
    "author": "Sirelkhatim",
    "license": "LGPL-3",
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
        # "views/res_company_views.xml",
        # "views/stock_warehouse_views.xml",
    ],
    "installable": True,
    "application": False,
}