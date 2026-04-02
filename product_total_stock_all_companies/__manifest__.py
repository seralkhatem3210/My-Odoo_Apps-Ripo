# -*- coding: utf-8 -*-
################################################################################
#    Sirelkhatim Technologies
#    License: LGPL-3
################################################################################
{
    "name": "Product Total Stock All Companies",
    "summary": "View total stock across all companies and auto-fulfill shortages with smart intercompany transfers.",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "Sirelkhatim",
    "website": "https://sirelkhatim.uk",
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

    "images": [
        "static/description/screenshot1.png",
    ],

    "application": False,
    "installable": True,

    "description": """
Product Total Stock (All Companies)
===================================

Gain full visibility of product quantities across all companies and automate stock shortage fulfillment using intelligent intercompany transfers.

Key Features
------------
- View total on-hand quantity across all companies in one place
- Display free quantity (available stock) across companies
- Automatic detection of stock shortages during validation
- Auto intercompany replenishment from available stock in other companies
- Seamless integration with standard Odoo Inventory workflows
- Works with internal transfers and multi-company environments

Auto Fulfillment Logic
---------------------
- When validating a picking:
  * If stock is insufficient in the current company
  * The system searches other companies for available quantity
  * Automatically creates internal/intercompany transfers
  * Completes delivery and receipt flow (optional automation)

- Smart quantity allocation:
  * Uses available quantities from multiple companies if needed
  * Prevents over-allocation
  * Ensures smooth fulfillment without manual intervention

Multi-Company Support
--------------------
- Fully compatible with Odoo multi-company setup
- Supports shared products across companies
- Real-time aggregated stock computation
- No need to switch companies manually

Technical Overview
-----------------
- Extends:
  * product.product
  * product.template
  * stock.picking

- Adds:
  * qty_all_companies
  * free_qty_all_companies

- Hooks into:
  * Picking validation (button_validate)
  * Automatic replenishment logic

Compatibility
-------------
- ✅ Odoo 18 Community & Enterprise
- ✅ Multi-company environments
- ✅ Inventory + Sales + Purchase flows

Use Cases
---------
- Central warehouse supplying multiple companies
- Franchise or multi-branch organizations
- Manufacturing groups with shared stock
- Companies needing automated stock balancing

Support
-------
Need help or customization?

🌐 https://sirelkhatim.uk  
📩 Arabic & English support available

العربية (ملخص)
--------------
- عرض إجمالي المخزون عبر جميع الشركات
- دعم بيئات الشركات المتعددة في أودو
- نقل تلقائي للمخزون بين الشركات عند وجود نقص
- تكامل كامل مع عمليات المخزون والبيع والشراء
- تقليل العمل اليدوي وزيادة كفاءة العمليات
""",
<<<<<<< HEAD
}
=======
}
>>>>>>> 82b601706817fdff461936f2a832f05bdc02dfb9
