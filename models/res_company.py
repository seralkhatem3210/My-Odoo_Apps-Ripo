from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    auto_intercompany_customer_id = fields.Many2one(
        "res.partner",
        string="Auto Intercompany Customer",
        help="Customer used on donor company sale orders for automatic replenishment.",
    )

    auto_intercompany_vendor_id = fields.Many2one(
        "res.partner",
        string="Auto Intercompany Vendor",
        help="Vendor used on target company purchase orders for automatic replenishment.",
    )