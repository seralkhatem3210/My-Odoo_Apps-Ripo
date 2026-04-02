from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    auto_fulfillment_source_priority = fields.Integer(
        string="Auto Fulfillment Priority",
        default=10,
    )

    allow_as_auto_source = fields.Boolean(
        string="Allow as Auto Source",
        default=True,
    )

    auto_source_company_ids = fields.Many2many(
        "res.company",
        string="Allowed Destination Companies",
        help="Companies that are allowed to receive automatic replenishment from this warehouse.",
    )