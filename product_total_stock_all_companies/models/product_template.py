from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    qty_all_companies = fields.Float(
        string="On Hand (All Companies)",
        compute="_compute_qty_all_companies",
        digits="Product Unit of Measure",
    )

    free_qty_all_companies = fields.Float(
        string="Free Qty (All Companies)",
        compute="_compute_qty_all_companies",
        digits="Product Unit of Measure",
    )
    allow_auto_cross_company_fulfillment = fields.Boolean(
        string="Allow Auto Cross-Company Fulfillment",
        default=True,
    )

    @api.depends("product_variant_ids.qty_all_companies", "product_variant_ids.free_qty_all_companies")
    def _compute_qty_all_companies(self):
        for template in self:
            template.qty_all_companies = sum(template.product_variant_ids.mapped("qty_all_companies"))
            template.free_qty_all_companies = sum(template.product_variant_ids.mapped("free_qty_all_companies"))


    qty_all_companies = fields.Float(
        string="On Hand (All Companies)",
        compute="_compute_qty_all_companies",
        digits="Product Unit of Measure",
    )

    free_qty_all_companies = fields.Float(
        string="Free Qty (All Companies)",
        compute="_compute_qty_all_companies",
        digits="Product Unit of Measure",
    )

    allow_auto_cross_company_fulfillment = fields.Boolean(
        string="Allow Auto Cross-Company Fulfillment",
        default=True,
    )

    @api.depends(
        "product_variant_ids.qty_all_companies",
        "product_variant_ids.free_qty_all_companies",
    )
    def _compute_qty_all_companies(self):
        for template in self:
            template.qty_all_companies = sum(template.product_variant_ids.mapped("qty_all_companies"))
            template.free_qty_all_companies = sum(template.product_variant_ids.mapped("free_qty_all_companies"))
