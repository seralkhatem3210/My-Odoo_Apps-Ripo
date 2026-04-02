from odoo import fields, models


class AutoFulfillmentLog(models.Model):
    _name = "auto.fulfillment.log"
    _description = "Auto Fulfillment Log"
    _order = "create_date desc"

    name = fields.Char(required=True, default="Auto Fulfillment")
    picking_id = fields.Many2one("stock.picking", string="Original Picking", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    source_company_id = fields.Many2one("res.company", string="Source Company")
    destination_company_id = fields.Many2one("res.company", string="Destination Company")
    source_warehouse_id = fields.Many2one("stock.warehouse", string="Source Warehouse")
    quantity = fields.Float(string="Quantity", required=True)
    fulfillment_type = fields.Selection([
        ("internal", "Internal Transfer"),
        ("intercompany", "Intercompany"),
    ], string="Fulfillment Type", required=True)
    internal_picking_id = fields.Many2one("stock.picking", string="Internal Transfer")
    sale_order_id = fields.Many2one("sale.order", string="Source Sale Order")
    purchase_order_id = fields.Many2one("purchase.order", string="Destination Purchase Order")
    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="draft", required=True)
    note = fields.Text(string="Notes")