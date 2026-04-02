from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    auto_fulfillment_log_ids = fields.One2many(
        "auto.fulfillment.log",
        "picking_id",
        string="Auto Fulfillment Logs",
    )
    auto_fulfillment_log_count = fields.Integer(
        compute="_compute_auto_fulfillment_log_count",
        string="Auto Fulfillment Logs",
    )

    # ---------------------------------------------------------
    # Smart Button
    # ---------------------------------------------------------

    def _compute_auto_fulfillment_log_count(self):
        for rec in self:
            rec.auto_fulfillment_log_count = len(rec.auto_fulfillment_log_ids)

    def action_view_auto_fulfillment_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Auto Fulfillment Logs",
            "res_model": "auto.fulfillment.log",
            "view_mode": "list,form",
            "domain": [("picking_id", "=", self.id)],
            "context": {"default_picking_id": self.id},
        }

    # ---------------------------------------------------------
    # Core Helpers
    # ---------------------------------------------------------

    def _get_move_line_qty_to_done(self, move_line):
        return (
            getattr(move_line, "reserved_uom_qty", 0.0)
            or getattr(move_line, "reserved_qty", 0.0)
            or getattr(move_line, "quantity", 0.0)
            or getattr(move_line, "product_uom_qty", 0.0)
            or 0.0
        )

    def _get_available_qty_in_picking_source(self, product, location):
        self.ensure_one()
        quants = self.env["stock.quant"].sudo().search([
            ("product_id", "=", product.id),
            ("location_id", "child_of", location.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "=", self.company_id.id),
        ])
        return sum(quants.mapped("available_quantity"))

    def _auto_fill_done_quantities(self):
        self.ensure_one()

        for move in self.move_ids_without_package.filtered(lambda m: m.state not in ("done", "cancel")):
            required_qty = move.product_uom_qty
            done_total = 0.0

            if move.move_line_ids:
                for ml in move.move_line_ids:
                    qty = self._get_move_line_qty_to_done(ml)
                    if qty <= 0:
                        remaining = required_qty - done_total
                        qty = remaining if remaining > 0 else 0.0
                    ml.qty_done = qty
                    done_total += qty

                if done_total < required_qty and move.move_line_ids:
                    move.move_line_ids[0].qty_done += (required_qty - done_total)
            else:
                self.env["stock.move.line"].sudo().create({
                    "picking_id": self.id,
                    "move_id": move.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "qty_done": required_qty,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                })

    # ---------------------------------------------------------
    # Validation Hook
    # ---------------------------------------------------------

    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.code != "outgoing":
                continue

            # Auto cover shortage first
            picking._auto_cover_shortage_before_validate()

            # Re-assign after replenishment
            picking.invalidate_recordset()
            picking.action_assign()

            # Fill done quantities automatically
            picking._auto_fill_done_quantities()

        return super(
            StockPicking,
            self.with_context(skip_immediate=True, skip_backorder=True)
        ).button_validate()

    # ---------------------------------------------------------
    # Shortage Detection and Donor Plan
    # ---------------------------------------------------------

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

            donors = self._find_donor_plan(
                product=product,
                shortage_qty=shortage_qty,
                destination_location=move.location_id,
            )

            if not donors:
                raise UserError(
                    _("Not enough stock for %s and no donor warehouse/company was found.")
                    % product.display_name
                )

            planned_total = sum(donor["take_qty"] for donor in donors)
            if planned_total < shortage_qty:
                raise UserError(
                    _(
                        "Not enough combined stock for %s.\n"
                        "Required shortage: %s\n"
                        "Found across donor warehouses/companies: %s"
                    ) % (product.display_name, shortage_qty, planned_total)
                )

            for donor in donors:
                take_qty = donor.get("take_qty", 0.0)
                if take_qty <= 0:
                    continue

                if donor["company_id"].id == self.company_id.id:
                    self._auto_internal_transfer_same_company(
                        product=product,
                        qty=take_qty,
                        source_location=donor["location"],
                        destination_location=move.location_id,
                        donor_warehouse=donor["warehouse"],
                    )
                else:
                    self._auto_intercompany_replenishment(
                        product=product,
                        qty=take_qty,
                        donor_company=donor["company_id"],
                        donor_warehouse=donor["warehouse"],
                        destination_company=self.company_id,
                    )

        self.invalidate_recordset()
        self.action_assign()
        self._auto_fill_done_quantities()

    def _find_donor_plan(self, product, shortage_qty, destination_location):
        """
        Build a donor plan that can split the shortage across
        multiple warehouses/companies until the shortage is covered.
        """
        self.ensure_one()

        warehouses = self.env["stock.warehouse"].sudo().search(
            [("allow_as_auto_source", "=", True)],
            order="auto_fulfillment_source_priority asc, id asc",
        )

        remaining = shortage_qty
        donor_plan = []

        for warehouse in warehouses:
            # Skip exact same stock location if same company
            if (
                warehouse.company_id.id == self.company_id.id
                and warehouse.lot_stock_id.id == destination_location.id
            ):
                continue

            # Restrict by allowed destination companies
            if warehouse.auto_source_company_ids and self.company_id not in warehouse.auto_source_company_ids:
                continue

            stock_location = warehouse.lot_stock_id
            quants = self.env["stock.quant"].sudo().search([
                ("product_id", "=", product.id),
                ("location_id", "child_of", stock_location.id),
                ("location_id.usage", "=", "internal"),
                ("company_id", "=", warehouse.company_id.id),
            ])
            available = sum(quants.mapped("available_quantity"))

            if available <= 0:
                continue

            take_qty = min(available, remaining)

            donor_plan.append({
                "warehouse": warehouse,
                "location": stock_location,
                "company_id": warehouse.company_id,
                "available": available,
                "take_qty": take_qty,
            })

            remaining -= take_qty
            if remaining <= 0:
                break

        return donor_plan

    # ---------------------------------------------------------
    # Same Company Internal Transfer
    # ---------------------------------------------------------

    def _auto_internal_transfer_same_company(self, product, qty, source_location, destination_location, donor_warehouse):
        self.ensure_one()

        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id", "=", donor_warehouse.id),
            ("company_id", "=", self.company_id.id),
        ], limit=1)

        if not picking_type:
            raise UserError(
                _("No internal transfer type found for warehouse %s")
                % donor_warehouse.display_name
            )

        internal_picking = self.env["stock.picking"].sudo().create({
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "company_id": self.company_id.id,
            "origin": "%s / AUTO-FULFILL" % (self.name or ""),
            "move_type": "direct",
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

        internal_picking.action_confirm()
        internal_picking.action_assign()

        if not internal_picking.move_line_ids:
            for move in internal_picking.move_ids:
                self.env["stock.move.line"].sudo().create({
                    "picking_id": internal_picking.id,
                    "move_id": move.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "qty_done": qty,
                    "location_id": source_location.id,
                    "location_dest_id": destination_location.id,
                })
        else:
            for move_line in internal_picking.move_line_ids:
                move_line.qty_done = self._get_move_line_qty_to_done(move_line) or qty

        internal_picking.with_context(
            skip_immediate=True,
            skip_backorder=True
        ).button_validate()

        self.env["auto.fulfillment.log"].sudo().create({
            "name": "Internal Auto Fulfillment - %s" % (self.name or ""),
            "picking_id": self.id,
            "product_id": product.id,
            "source_company_id": self.company_id.id,
            "destination_company_id": self.company_id.id,
            "source_warehouse_id": donor_warehouse.id,
            "quantity": qty,
            "fulfillment_type": "internal",
            "internal_picking_id": internal_picking.id,
            "state": "done",
            "note": "Auto internal transfer completed successfully.",
        })

    # ---------------------------------------------------------
    # Intercompany Replenishment
    # ---------------------------------------------------------

    def _auto_intercompany_replenishment(
        self,
        product,
        qty,
        donor_company,
        donor_warehouse,
        destination_company,
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
            raise UserError(
                _("No vendor found for donor company %s.")
                % donor_company.display_name
            )
        if not customer:
            raise UserError(
                _("No customer found for destination company %s.")
                % destination_company.display_name
            )

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
        for donor_picking in donor_pickings:
            donor_picking.action_assign()

            if not donor_picking.move_line_ids:
                for move in donor_picking.move_ids_without_package:
                    self.env["stock.move.line"].with_company(donor_company).sudo().create({
                        "picking_id": donor_picking.id,
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "qty_done": move.product_uom_qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    })
            else:
                for move_line in donor_picking.move_line_ids:
                    move_line.qty_done = self._get_move_line_qty_to_done(move_line) or qty

            donor_picking.with_context(
                skip_immediate=True,
                skip_backorder=True
            ).button_validate()

        receipt_pickings = purchase_order.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        for receipt_picking in receipt_pickings:
            receipt_picking.action_assign()

            if not receipt_picking.move_line_ids:
                for move in receipt_picking.move_ids_without_package:
                    self.env["stock.move.line"].with_company(destination_company).sudo().create({
                        "picking_id": receipt_picking.id,
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "qty_done": move.product_uom_qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    })
            else:
                for move_line in receipt_picking.move_line_ids:
                    move_line.qty_done = self._get_move_line_qty_to_done(move_line) or qty

            receipt_picking.with_context(
                skip_immediate=True,
                skip_backorder=True
            ).button_validate()

        self.env["auto.fulfillment.log"].sudo().create({
            "name": "Intercompany Auto Fulfillment - %s" % (self.name or ""),
            "picking_id": self.id,
            "product_id": product.id,
            "source_company_id": donor_company.id,
            "destination_company_id": destination_company.id,
            "source_warehouse_id": donor_warehouse.id,
            "quantity": qty,
            "fulfillment_type": "intercompany",
            "sale_order_id": sale_order.id,
            "purchase_order_id": purchase_order.id,
            "state": "done",
            "note": "Auto intercompany replenishment completed successfully.",
        })