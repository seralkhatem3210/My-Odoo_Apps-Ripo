from dataclasses import fields
from odoo import api, fields, models, _

from odoo import api, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"


    def _get_move_line_qty_to_done(self, ml):
        qty = (
            getattr(ml, "reserved_uom_qty", 0.0)
            or getattr(ml, "reserved_qty", 0.0)
            or getattr(ml, "quantity", 0.0)
            or getattr(ml, "product_uom_qty", 0.0)
        )
        return qty

    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.code != "outgoing":
                continue
            picking._auto_cover_shortage_before_validate()
        return super().button_validate()

    def _auto_cover_shortage_before_validate(self):
        self.ensure_one()

        for move in self.move_ids_without_package.filtered(lambda m: m.state not in ("done", "cancel")):
            product = move.product_id
            template = product.product_tmpl_id

            if not template.allow_auto_cross_company_fulfillment:
                continue

            needed_qty = move.product_uom_qty
            available_qty = self._get_available_qty_in_picking_source(product, move.location_id)
            shortage_qty = needed_qty - available_qty

            if shortage_qty <= 0:
                continue

            donor = self._find_best_donor(product, shortage_qty)
            if not donor:
                raise UserError(
                    _("Not enough stock for %s and no donor warehouse/company was found.") % product.display_name
                )

            if donor["company_id"].id == self.company_id.id:
                self._auto_internal_transfer_same_company(
                    product=product,
                    qty=shortage_qty,
                    source_location=donor["location"],
                    destination_location=move.location_id,
                    donor_warehouse=donor["warehouse"],
                )
            else:
                self._auto_intercompany_replenishment(
                    product=product,
                    qty=shortage_qty,
                    donor_company=donor["company_id"],
                    donor_warehouse=donor["warehouse"],
                    destination_company=self.company_id,
                    destination_location=move.location_id,
                )

        self.action_assign()

    def _get_available_qty_in_picking_source(self, product, location):
        quants = self.env["stock.quant"].sudo().search([
            ("product_id", "=", product.id),
            ("location_id", "child_of", location.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "=", self.company_id.id),
        ])
        return sum(quants.mapped("available_quantity"))

    def _find_best_donor(self, product, shortage_qty):
        warehouses = self.env["stock.warehouse"].sudo().search(
            [("allow_as_auto_source", "=", True)],
            order="auto_fulfillment_source_priority asc, id asc",
        )

        for wh in warehouses:
            if wh.company_id.id == self.company_id.id and wh.lot_stock_id.id == self.location_id.id:
                continue

            if wh.auto_source_company_ids and self.company_id not in wh.auto_source_company_ids:
                continue

            stock_loc = wh.lot_stock_id
            quants = self.env["stock.quant"].sudo().search([
                ("product_id", "=", product.id),
                ("location_id", "child_of", stock_loc.id),
                ("location_id.usage", "=", "internal"),
                ("company_id", "=", wh.company_id.id),
            ])
            available = sum(quants.mapped("available_quantity"))
            if available >= shortage_qty:
                return {
                    "warehouse": wh,
                    "location": stock_loc,
                    "company_id": wh.company_id,
                    "available": available,
                }
        return False

    def _auto_internal_transfer_same_company(self, product, qty, source_location, destination_location, donor_warehouse):
        self.ensure_one()

        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id", "=", donor_warehouse.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

        if not picking_type:
            raise UserError(_("No internal transfer type found for warehouse %s") % donor_warehouse.display_name)

        internal = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "company_id": self.company_id.id,
            "origin": "%s / AUTO-FULFILL" % (self.name or ""),
            "move_ids_without_package": [(0, 0, {
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": source_location.id,
                "location_dest_id": destination_location.id,
                "company_id": self.company_id.id,
            })],
        })

        internal.action_confirm()
        internal.action_assign()

        if not internal.move_line_ids:
            for move in internal.move_ids:
                self.env["stock.move.line"].create({
                    "picking_id": internal.id,
                    "move_id": move.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "qty_done": qty,
                    "location_id": source_location.id,
                    "location_dest_id": destination_location.id,
                })
        else:
            for ml in internal.move_line_ids:
                ml.qty_done = self._get_move_line_qty_to_done(ml)

        internal.button_validate()

    # def _auto_intercompany_replenishment(
    #     self,
    #     product,
    #     qty,
    #     donor_company,
    #     donor_warehouse,
    #     destination_company,
    #     destination_location,
    # ):
    #     self.ensure_one()

    def _auto_intercompany_replenishment(
        self,
        product,
        qty,
        donor_company,
        donor_warehouse,
        destination_company,
        destination_location,
    ):
        self.ensure_one()

        vendor = donor_company.auto_intercompany_vendor_id
        if not vendor and donor_company.partner_id:
            vendor = donor_company.partner_id
            donor_company.sudo().write({
                "auto_intercompany_vendor_id": vendor.id,
            })

        customer = destination_company.auto_intercompany_customer_id
        if not customer and destination_company.partner_id:
            customer = destination_company.partner_id
            destination_company.sudo().write({
                "auto_intercompany_customer_id": customer.id,
            })

        if not vendor:
            raise UserError(_("No vendor found for donor company %s.") % donor_company.display_name)
        if not customer:
            raise UserError(_("No customer found for destination company %s.") % destination_company.display_name)


        # vendor = donor_company.auto_intercompany_vendor_id or donor_company.partner_id
        # customer = destination_company.auto_intercompany_customer_id or destination_company.partner_id

        # if not vendor:
        #     raise UserError(
        #         _("No vendor found for donor company %s. Please set Auto Intercompany Vendor or company contact.")
        #         % donor_company.display_name
        #     )
        # if not customer:
        #     raise UserError(
        #         _("No customer found for destination company %s. Please set Auto Intercompany Customer or company contact.")
        #         % destination_company.display_name
        #     )
        
        # # vendor = donor_company.auto_intercompany_vendor_id
        # # customer = destination_company.auto_intercompany_customer_id

        # vendor = donor_company.auto_intercompany_vendor_id or donor_company.partner_id
        # customer = destination_company.auto_intercompany_customer_id or destination_company.partner_id

        # if not vendor:
        #     raise UserError(_("Set Auto Intercompany Vendor on donor company %s.") % donor_company.display_name)
        # if not customer:
        #     raise UserError(_("Set Auto Intercompany Customer on destination company %s.") % destination_company.display_name)

        purchase_order = self.env["purchase.order"].with_company(destination_company).sudo().create({
            "partner_id": vendor.id,
            "company_id": destination_company.id,
            "origin": "%s / AUTO-INTERCOMPANY" % (self.name or ""),
            "order_line": [(0, 0, {
                "name": product.display_name,
                "product_id": product.id,
                "product_qty": qty,
                "product_uom": product.uom_po_id.id or product.uom_id.id,
                "price_unit": product.standard_price or 0.0,
                "date_planned": fields.Datetime.now(),
            })],
        })
        purchase_order.button_confirm()

        sale_order = self.env["sale.order"].with_company(donor_company).sudo().create({
            "partner_id": customer.id,
            "company_id": donor_company.id,
            "origin": "%s / AUTO-INTERCOMPANY" % (self.name or ""),
            "order_line": [(0, 0, {
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "price_unit": product.lst_price or 0.0,
            })],
        })
        sale_order.action_confirm()

        donor_pickings = sale_order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        for picking in donor_pickings:
            picking.action_assign()
            if not picking.move_line_ids:
                for move in picking.move_ids_without_package:
                    self.env["stock.move.line"].with_company(donor_company).sudo().create({
                        "picking_id": picking.id,
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "qty_done": move.product_uom_qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    })
            else:
                for ml in picking.move_line_ids:
                    ml.qty_done = self._get_move_line_qty_to_done(ml)
            picking.button_validate()

        receipt_pickings = purchase_order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        for picking in receipt_pickings:
            picking.action_assign()
            if not picking.move_line_ids:
                for move in picking.move_ids_without_package:
                    self.env["stock.move.line"].with_company(destination_company).sudo().create({
                        "picking_id": picking.id,
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "qty_done": move.product_uom_qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    })
            else:
                for ml in picking.move_line_ids:
                    ml.qty_done = self._get_move_line_qty_to_done(ml)
            picking.button_validate()