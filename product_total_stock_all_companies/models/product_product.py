from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    qty_all_companies = fields.Float(
        string="On Hand (All Companies)",
        compute="_compute_all_companies_stock",
        digits="Product Unit of Measure",
        help="Total on hand quantity across all companies in internal locations.",
    )

    free_qty_all_companies = fields.Float(
        string="Free Qty (All Companies)",
        compute="_compute_all_companies_stock",
        digits="Product Unit of Measure",
        help="Total free quantity across all companies in internal locations.",
    )

    company_stock_summary = fields.Text(
        string="Company Stock Summary",
        compute="_compute_all_companies_stock",
        help="Stock summary for this product grouped by company.",
    )

    @api.depends("stock_quant_ids.quantity", "stock_quant_ids.reserved_quantity")
    def _compute_all_companies_stock(self):
        Quant = self.env["stock.quant"].sudo()
        Company = self.env["res.company"].sudo()

        companies = Company.search([])

        for product in self:
            total_qty = 0.0
            total_free = 0.0
            summary_lines = []

            for company in companies:
                groups = Quant.read_group(
                    domain=[
                        ("product_id", "=", product.id),
                        ("company_id", "=", company.id),
                        ("location_id.usage", "=", "internal"),
                    ],
                    fields=["quantity:sum", "reserved_quantity:sum"],
                    groupby=[],
                    lazy=False,
                )

                qty = groups[0]["quantity"] if groups else 0.0
                reserved = groups[0]["reserved_quantity"] if groups else 0.0
                free_qty = qty - reserved

                total_qty += qty
                total_free += free_qty

                if qty or free_qty:
                    summary_lines.append(
                        "%s: On Hand = %s | Free = %s" % (
                            company.name,
                            qty,
                            free_qty,
                        )
                    )

            product.qty_all_companies = total_qty
            product.free_qty_all_companies = total_free
            product.company_stock_summary = "\n".join(summary_lines) if summary_lines else "No stock in any company."