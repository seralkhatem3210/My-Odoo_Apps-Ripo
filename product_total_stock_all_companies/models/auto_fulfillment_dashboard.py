from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models


class AutoFulfillmentDashboard(models.AbstractModel):
    _name = "auto.fulfillment.dashboard"
    _description = "Auto Fulfillment Dashboard"

    @api.model
    def get_filter_options(self):
        companies = self.env["res.company"].sudo().search([])
        return {
            "companies": [{"id": c.id, "name": c.name} for c in companies],
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}
        domain = []

        date_from = (filters.get("date_from") or "").strip()
        date_to = (filters.get("date_to") or "").strip()
        company_id = filters.get("company_id")
        fulfillment_type = (filters.get("fulfillment_type") or "").strip()
        state = (filters.get("state") or "").strip()

        if date_from:
            domain.append(("create_date", ">=", f"{date_from} 00:00:00"))
        if date_to:
            domain.append(("create_date", "<=", f"{date_to} 23:59:59"))

        if company_id:
            company_id = int(company_id)
            domain.extend([
                "|",
                ("destination_company_id", "=", company_id),
                ("source_company_id", "=", company_id),
            ])

        if fulfillment_type:
            domain.append(("fulfillment_type", "=", fulfillment_type))

        if state:
            domain.append(("state", "=", state))

        Log = self.env["auto.fulfillment.log"].sudo()
        logs = Log.search(domain, order="create_date desc", limit=20)
        all_logs = Log.search(domain)

        total_fulfillments = len(all_logs)
        total_internal = len(all_logs.filtered(lambda l: l.fulfillment_type == "internal"))
        total_intercompany = len(all_logs.filtered(lambda l: l.fulfillment_type == "intercompany"))
        total_failed = len(all_logs.filtered(lambda l: l.state == "failed"))
        total_done = len(all_logs.filtered(lambda l: l.state == "done"))
        total_quantity = sum(all_logs.mapped("quantity")) if all_logs else 0
        total_products = len(set(all_logs.mapped("product_id").ids)) if all_logs else 0
        total_companies = len(set(all_logs.mapped("destination_company_id").ids)) if all_logs else 0
        avg_quantity = (total_quantity / total_fulfillments) if total_fulfillments else 0

        warehouse_map = defaultdict(float)
        product_map = defaultdict(float)
        trend_map = defaultdict(float)
        destination_company_map = defaultdict(float)
        type_map = defaultdict(float)
        state_map = defaultdict(float)

        for log in all_logs:
            qty = log.quantity or 0.0

            if log.source_warehouse_id:
                warehouse_map[log.source_warehouse_id.display_name] += qty

            if log.product_id:
                product_map[log.product_id.display_name] += qty

            if log.destination_company_id:
                destination_company_map[log.destination_company_id.display_name] += qty

            if log.fulfillment_type:
                type_map[log.fulfillment_type] += qty

            if log.state:
                state_map[log.state] += 1

            if log.create_date:
                date_key = fields.Date.to_string(fields.Date.to_date(log.create_date))
                trend_map[date_key] += qty

        top_warehouses = [
            {"label": k, "value": v}
            for k, v in sorted(warehouse_map.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        top_products = [
            {"label": k, "value": v}
            for k, v in sorted(product_map.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        top_destination_companies = [
            {"label": k, "value": v}
            for k, v in sorted(destination_company_map.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        fulfillment_type_split = [
            {"label": k.title(), "value": v}
            for k, v in sorted(type_map.items(), key=lambda x: x[1], reverse=True)
        ]

        state_split = [
            {"label": k.title(), "value": v}
            for k, v in sorted(state_map.items(), key=lambda x: x[1], reverse=True)
        ]

        daily_trend = [
            {"label": k, "raw_date": k, "value": v}
            for k, v in sorted(trend_map.items(), key=lambda x: x[0])
        ]

        # def ensure_min_data(data, is_pie=False):
        #     if not data:
        #         return [{"label": "No Data", "value": 1 if is_pie else 0}]
        #     if len(data) == 1:
        #         data.append({"label": "Other", "value": 0})
        #     return data

        # top_warehouses = ensure_min_data(top_warehouses)
        # top_products = ensure_min_data(top_products)
        # top_destination_companies = ensure_min_data(top_destination_companies)
        # fulfillment_type_split = ensure_min_data(fulfillment_type_split, is_pie=True)
        # state_split = ensure_min_data(state_split, is_pie=True)
        # daily_trend = ensure_min_data(daily_trend)
        def ensure_min_data(data, is_pie=False):
            if not data:
                return [{"label": "No Data", "value": 1 if is_pie else 0}]
            if len(data) == 1:
                data.append({"label": "Other", "value": 0})
            return data

        top_warehouses = ensure_min_data(top_warehouses)
        top_products = ensure_min_data(top_products)
        top_destination_companies = ensure_min_data(top_destination_companies)
        fulfillment_type_split = ensure_min_data(fulfillment_type_split, is_pie=True)
        state_split = ensure_min_data(state_split, is_pie=True)
        daily_trend = ensure_min_data(daily_trend)


        if daily_trend and len(daily_trend) == 1 and daily_trend[0]["label"] != "No Data":
            only = daily_trend[0]
            date_value = fields.Date.from_string(only["label"])
            prev_date = date_value - timedelta(days=1)
            daily_trend.insert(0, {
                "label": fields.Date.to_string(prev_date),
                "raw_date": fields.Date.to_string(prev_date),
                "value": 0,
            })

        recent_logs = []
        for log in logs:
            recent_logs.append({
                "id": log.id,
                "date": fields.Datetime.to_string(log.create_date) if log.create_date else "",
                "picking": log.picking_id.display_name if log.picking_id else "",
                "product": log.product_id.display_name if log.product_id else "",
                "type": log.fulfillment_type or "",
                "qty": log.quantity or 0,
                "source_warehouse": log.source_warehouse_id.display_name if log.source_warehouse_id else "",
                "source_company": log.source_company_id.display_name if log.source_company_id else "",
                "destination_company": log.destination_company_id.display_name if log.destination_company_id else "",
                "state": log.state or "",
            })

        return {
            "kpis": {
                "total_fulfillments": total_fulfillments,
                "total_internal": total_internal,
                "total_intercompany": total_intercompany,
                "total_failed": total_failed,
                "total_done": total_done,
                "total_quantity": total_quantity,
                "total_products": total_products,
                "total_companies": total_companies,
                "avg_quantity": round(avg_quantity, 2),
            },
            "top_warehouses": top_warehouses,
            "top_products": top_products,
            "top_destination_companies": top_destination_companies,
            "fulfillment_type_split": fulfillment_type_split,
            "state_split": state_split,
            "daily_trend": daily_trend,
            "recent_logs": recent_logs,
        }



# from collections import defaultdict
# from odoo import api, fields, models

# from datetime import timedelta

# if daily_trend and len(daily_trend) == 1:
#     only = daily_trend[0]
#     date = fields.Date.from_string(only["label"])
#     prev_date = date - timedelta(days=1)

#     daily_trend.insert(0, {
#         "label": fields.Date.to_string(prev_date),
#         "raw_date": fields.Date.to_string(prev_date),
#         "value": 0,
#     })


# class AutoFulfillmentDashboard(models.AbstractModel):
#     _name = "auto.fulfillment.dashboard"
#     _description = "Auto Fulfillment Dashboard"

#     @api.model
#     def get_filter_options(self):
#         companies = self.env["res.company"].sudo().search([])
#         return {
#             "companies": [{"id": c.id, "name": c.name} for c in companies],
#         }

#     @api.model
#     def get_dashboard_data(self, filters=None):
#         filters = filters or {}
#         domain = []

#         # if filters.get("date_from"):
#         #     domain.append(("create_date", ">=", filters["date_from"]))
#         # if filters.get("date_to"):
#         #     domain.append(("create_date", "<=", filters["date_to"]))
#         if filters.get("date_from"):
#             domain.append(("create_date", ">=", f"{filters['date_from']} 00:00:00"))
#         if filters.get("date_to"):
#             domain.append(("create_date", "<=", f"{filters['date_to']} 23:59:59"))
            
#         if filters.get("company_id"):
#             company_id = int(filters["company_id"])
#             domain.append("|")
#             domain.append(("destination_company_id", "=", company_id))
#             domain.append(("source_company_id", "=", company_id))
            
#         if filters.get("fulfillment_type"):
#             domain.append(("fulfillment_type", "=", filters["fulfillment_type"]))
#         if filters.get("state"):
#             domain.append(("state", "=", filters["state"]))

#         Log = self.env["auto.fulfillment.log"].sudo()
#         logs = Log.search(domain, order="create_date desc", limit=20)
#         all_logs = Log.search(domain)

#         total_fulfillments = len(all_logs)
#         total_internal = len(all_logs.filtered(lambda l: l.fulfillment_type == "internal"))
#         total_intercompany = len(all_logs.filtered(lambda l: l.fulfillment_type == "intercompany"))
#         total_failed = len(all_logs.filtered(lambda l: l.state == "failed"))
#         total_done = len(all_logs.filtered(lambda l: l.state == "done"))
#         total_quantity = sum(all_logs.mapped("quantity")) if all_logs else 0
#         total_products = len(set(all_logs.mapped("product_id").ids)) if all_logs else 0
#         total_companies = len(set(all_logs.mapped("destination_company_id").ids)) if all_logs else 0
#         avg_quantity = (total_quantity / total_fulfillments) if total_fulfillments else 0

#         warehouse_map = defaultdict(float)
#         product_map = defaultdict(float)
#         trend_map = defaultdict(float)
#         destination_company_map = defaultdict(float)
#         type_map = defaultdict(float)
#         state_map = defaultdict(float)

#         for log in all_logs:
#             qty = log.quantity or 0

#             if log.source_warehouse_id:
#                 warehouse_map[log.source_warehouse_id.display_name] += qty

#             if log.product_id:
#                 product_map[log.product_id.display_name] += qty

#             if log.destination_company_id:
#                 destination_company_map[log.destination_company_id.display_name] += qty

#             if log.fulfillment_type:
#                 type_map[log.fulfillment_type] += qty

#             if log.state:
#                 state_map[log.state] += 1

#             if log.create_date:
#                 date_key = fields.Date.to_string(fields.Date.to_date(log.create_date))
#                 trend_map[date_key] += qty

#         top_warehouses = [
#             {"label": k, "value": v}
#             for k, v in sorted(warehouse_map.items(), key=lambda x: x[1], reverse=True)[:10]
#         ]

#         top_products = [
#             {"label": k, "value": v}
#             for k, v in sorted(product_map.items(), key=lambda x: x[1], reverse=True)[:10]
#         ]

#         top_destination_companies = [
#             {"label": k, "value": v}
#             for k, v in sorted(destination_company_map.items(), key=lambda x: x[1], reverse=True)[:10]
#         ]

#         fulfillment_type_split = [
#             {"label": k.title(), "value": v}
#             for k, v in sorted(type_map.items(), key=lambda x: x[1], reverse=True)
#         ]

#         state_split = [
#             {"label": k.title(), "value": v}
#             for k, v in sorted(state_map.items(), key=lambda x: x[1], reverse=True)
#         ]

#         daily_trend = [
#             {"label": k, "raw_date": k, "value": v}
#             for k, v in sorted(trend_map.items(), key=lambda x: x[0])
#         ]

#         # Guarantee charts always have meaningful data

#         def ensure_min_data(data, is_pie=False):
#             if not data:
#                 return [{"label": "No Data", "value": 1 if is_pie else 0}]
#             if len(data) == 1:
#                 # add fake small value to avoid chart collapse
#                 data.append({"label": "Other", "value": 0})
#             return data

#         top_warehouses = ensure_min_data(top_warehouses)
#         top_products = ensure_min_data(top_products)
#         top_destination_companies = ensure_min_data(top_destination_companies)

#         fulfillment_type_split = ensure_min_data(fulfillment_type_split, is_pie=True)
#         state_split = ensure_min_data(state_split, is_pie=True)

#         daily_trend = ensure_min_data(daily_trend)
            

#         recent_logs = []
#         for log in logs:
#             recent_logs.append({
#                 "id": log.id,
#                 "date": fields.Datetime.to_string(log.create_date) if log.create_date else "",
#                 "picking": log.picking_id.display_name if log.picking_id else "",
#                 "product": log.product_id.display_name if log.product_id else "",
#                 "type": log.fulfillment_type or "",
#                 "qty": log.quantity or 0,
#                 "source_warehouse": log.source_warehouse_id.display_name if log.source_warehouse_id else "",
#                 "source_company": log.source_company_id.display_name if log.source_company_id else "",
#                 "destination_company": log.destination_company_id.display_name if log.destination_company_id else "",
#                 "state": log.state or "",
#             })

#         return {
#             "kpis": {
#                 "total_fulfillments": total_fulfillments,
#                 "total_internal": total_internal,
#                 "total_intercompany": total_intercompany,
#                 "total_failed": total_failed,
#                 "total_done": total_done,
#                 "total_quantity": total_quantity,
#                 "total_products": total_products,
#                 "total_companies": total_companies,
#                 "avg_quantity": round(avg_quantity, 2),
#             },
#             "top_warehouses": top_warehouses,
#             "top_products": top_products,
#             "top_destination_companies": top_destination_companies,
#             "fulfillment_type_split": fulfillment_type_split,
#             "state_split": state_split,
#             "daily_trend": daily_trend,
#             "recent_logs": recent_logs,
#         }


# # from collections import defaultdict
# # from odoo import api, fields, models


# # class AutoFulfillmentDashboard(models.AbstractModel):
# #     _name = "auto.fulfillment.dashboard"
# #     _description = "Auto Fulfillment Dashboard"

# #     @api.model
# #     def get_filter_options(self):
# #         companies = self.env["res.company"].sudo().search([])
# #         return {
# #             "companies": [{"id": c.id, "name": c.name} for c in companies],
# #         }

# #     @api.model
# #     def get_dashboard_data(self, filters=None):
# #         filters = filters or {}
# #         domain = []

# #         if filters.get("date_from"):
# #             domain.append(("create_date", ">=", filters["date_from"]))
# #         if filters.get("date_to"):
# #             domain.append(("create_date", "<=", filters["date_to"]))
# #         if filters.get("company_id"):
# #             domain.append(("destination_company_id", "=", int(filters["company_id"])))
# #         if filters.get("fulfillment_type"):
# #             domain.append(("fulfillment_type", "=", filters["fulfillment_type"]))
# #         if filters.get("state"):
# #             domain.append(("state", "=", filters["state"]))

# #         Log = self.env["auto.fulfillment.log"].sudo()
# #         logs = Log.search(domain, order="create_date desc", limit=20)
# #         all_logs = Log.search(domain)

# #         total_fulfillments = len(all_logs)
# #         total_internal = len(all_logs.filtered(lambda l: l.fulfillment_type == "internal"))
# #         total_intercompany = len(all_logs.filtered(lambda l: l.fulfillment_type == "intercompany"))
# #         total_failed = len(all_logs.filtered(lambda l: l.state == "failed"))
# #         total_quantity = sum(all_logs.mapped("quantity")) if all_logs else 0
# #         total_products = len(set(all_logs.mapped("product_id").ids)) if all_logs else 0

# #         warehouse_map = defaultdict(float)
# #         product_map = defaultdict(float)
# #         trend_map = defaultdict(float)

# #         for log in all_logs:
# #             if log.source_warehouse_id:
# #                 warehouse_map[log.source_warehouse_id.display_name] += log.quantity or 0

# #             if log.product_id:
# #                 product_map[log.product_id.display_name] += log.quantity or 0

# #             if log.create_date:
# #                 date_key = fields.Date.to_string(fields.Date.to_date(log.create_date))
# #                 trend_map[date_key] += log.quantity or 0

# #         top_warehouses = [
# #             {"label": k, "value": v}
# #             for k, v in sorted(warehouse_map.items(), key=lambda x: x[1], reverse=True)[:10]
# #         ]

# #         top_products = [
# #             {"label": k, "value": v}
# #             for k, v in sorted(product_map.items(), key=lambda x: x[1], reverse=True)[:10]
# #         ]

# #         daily_trend = [
# #             {"label": k, "raw_date": k, "value": v}
# #             for k, v in sorted(trend_map.items(), key=lambda x: x[0])
# #         ]

# #         recent_logs = []
# #         for log in logs:
# #             recent_logs.append({
# #                 "id": log.id,
# #                 "date": fields.Datetime.to_string(log.create_date) if log.create_date else "",
# #                 "picking": log.picking_id.display_name if log.picking_id else "",
# #                 "product": log.product_id.display_name if log.product_id else "",
# #                 "type": log.fulfillment_type or "",
# #                 "quantity": log.quantity or 0,
# #                 "source_warehouse": log.source_warehouse_id.display_name if log.source_warehouse_id else "",
# #                 "source_company": log.source_company_id.display_name if log.source_company_id else "",
# #                 "destination_company": log.destination_company_id.display_name if log.destination_company_id else "",
# #                 "state": log.state or "",
# #             })

# #         return {
# #             "kpis": {
# #                 "total_fulfillments": total_fulfillments,
# #                 "total_internal": total_internal,
# #                 "total_intercompany": total_intercompany,
# #                 "total_failed": total_failed,
# #                 "total_quantity": total_quantity,
# #                 "total_products": total_products,
# #             },
# #             "top_warehouses": top_warehouses,
# #             "top_products": top_products,
# #             "top_destination_companies": [],
# #             "daily_trend": daily_trend,
# #             "recent_logs": recent_logs,
# #         }
    


# # # from collections import defaultdict
# # # from odoo import api, fields, models


# # # class AutoFulfillmentDashboard(models.AbstractModel):
# # #     _name = "auto.fulfillment.dashboard"
# # #     _description = "Auto Fulfillment Dashboard"

# # #     @api.model
# # #     def get_filter_options(self):
# # #         companies = self.env["res.company"].sudo().search([])
# # #         return {
# # #             "companies": [{"id": c.id, "name": c.name} for c in companies],
# # #         }

# # #     @api.model
# # #     def get_dashboard_data(self, filters=None):
# # #         filters = filters or {}
# # #         domain = []

# # #         if filters.get("date_from"):
# # #             domain.append(("create_date", ">=", filters["date_from"]))
# # #         if filters.get("date_to"):
# # #             domain.append(("create_date", "<=", filters["date_to"]))
# # #         if filters.get("company_id"):
# # #             domain.append(("destination_company_id", "=", int(filters["company_id"])))
# # #         if filters.get("fulfillment_type"):
# # #             domain.append(("fulfillment_type", "=", filters["fulfillment_type"]))
# # #         if filters.get("state"):
# # #             domain.append(("state", "=", filters["state"]))

# # #         Log = self.env["auto.fulfillment.log"].sudo()
# # #         logs = Log.search(domain, order="create_date  desc", limit=20)
# # #         all_logs = Log.search(domain)

# # #         total_fulfillments = len(all_logs)
# # #         total_internal = len(all_logs.filtered(lambda l: l.fulfillment_type == "internal"))
# # #         total_intercompany = len(all_logs.filtered(lambda l: l.fulfillment_type == "intercompany"))
# # #         total_failed = len(all_logs.filtered(lambda l: l.state == "failed"))
# # #         total_quantity = sum(all_logs.mapped("quantity")) if all_logs else 0
# # #         total_products = len(set(all_logs.mapped("product_id").ids)) if all_logs else 0

# # #         warehouse_map = defaultdict(float)
# # #         product_map = defaultdict(float)
# # #         trend_map = defaultdict(float)

# # #         for log in all_logs:
# # #             if log.source_warehouse_id:
# # #                 warehouse_map[log.source_warehouse_id.display_name] += log.quantity or 0

# # #             if log.product_id:
# # #                 product_map[log.product_id.display_name] += log.quantity or 0

# # #             if log.create_date:
# # #                 date_key = fields.Date.to_string(fields.Date.to_date(log.create_date))
# # #                 trend_map[date_key] += log.quantity or 0

# # #         top_warehouses = [
# # #             {"label": k, "value": v}
# # #             for k, v in sorted(warehouse_map.items(), key=lambda x: x[1], reverse=True)[:10]
# # #         ]

# # #         top_products = [
# # #             {"label": k, "value": v}
# # #             for k, v in sorted(product_map.items(), key=lambda x: x[1], reverse=True)[:10]
# # #         ]

# # #         daily_trend = [
# # #             {"label": k, "raw_date": k, "value": v}
# # #             for k, v in sorted(trend_map.items(), key=lambda x: x[0])
# # #         ]

# # #         recent_logs = []
# # #         for log in logs:
# # #             recent_logs.append({
# # #                 "id": log.id,
# # #                 "date": fields.Datetime.to_string(log.create_date) if log.create_date else "",
# # #                 "picking": log.picking_id.display_name if log.picking_id else "",
# # #                 "product": log.product_id.display_name if log.product_id else "",
# # #                 "type": log.fulfillment_type or "",
# # #                 "quantity": log.quantity or 0,
# # #                 "source_warehouse": log.source_warehouse_id.display_name if log.source_warehouse_id else "",
# # #                 "source_company": log.source_company_id.display_name if log.source_company_id else "",
# # #                 "destination_company": log.destination_company_id.display_name if log.destination_company_id else "",
# # #                 "state": log.state or "",
# # #             })

# # #         return {
# # #             "kpis": {
# # #                 "total_fulfillments": total_fulfillments,
# # #                 "total_internal": total_internal,
# # #                 "total_intercompany": total_intercompany,
# # #                 "total_failed": total_failed,
# # #                 "total_quantity": total_quantity,
# # #                 "total_products": total_products,
# # #             },
# # #             "top_warehouses": top_warehouses,
# # #             "top_products": top_products,
# # #             "top_destination_companies": [],
# # #             "daily_trend": daily_trend,
# # #             "recent_logs": recent_logs,
# # #         }



# # # # from odoo import api, fields, models


# # # # class AutoFulfillmentDashboard(models.Model):
# # # #     _name = "auto.fulfillment.dashboard"
# # # #     _description = "Auto Fulfillment Dashboard"
# # # #     _auto = False

# # # #     name = fields.Char(string="Name")

# # # #     @api.model
# # # #     def get_dashboard_data(self):
# # # #         Log = self.env["auto.fulfillment.log"].sudo()

# # # #         all_logs = Log.search([])
# # # #         done_logs = Log.search([("state", "=", "done")])
# # # #         failed_logs = Log.search([("state", "=", "failed")])

# # # #         total_fulfillments = len(all_logs)
# # # #         total_internal = Log.search_count([
# # # #             ("fulfillment_type", "=", "internal"),
# # # #             ("state", "=", "done"),
# # # #         ])
# # # #         total_intercompany = Log.search_count([
# # # #             ("fulfillment_type", "=", "intercompany"),
# # # #             ("state", "=", "done"),
# # # #         ])
# # # #         total_failed = len(failed_logs)
# # # #         total_quantity = sum(done_logs.mapped("quantity"))
# # # #         total_products = len(set(done_logs.mapped("product_id").ids))

# # # #         top_warehouses = {}
# # # #         top_products = {}
# # # #         top_destination_companies = {}
# # # #         daily_trend = {}

# # # #         for log in done_logs:
# # # #             wh_name = log.source_warehouse_id.display_name or "Unknown"
# # # #             top_warehouses[wh_name] = top_warehouses.get(wh_name, 0.0) + log.quantity

# # # #             product_name = log.product_id.display_name or "Unknown"
# # # #             top_products[product_name] = top_products.get(product_name, 0.0) + log.quantity

# # # #             dest_company = log.destination_company_id.display_name or "Unknown"
# # # #             top_destination_companies[dest_company] = top_destination_companies.get(dest_company, 0.0) + log.quantity

# # # #             day_key = fields.Date.to_string(log.create_date.date()) if log.create_date else "Unknown"
# # # #             daily_trend[day_key] = daily_trend.get(day_key, 0.0) + log.quantity

# # # #         recent_logs = Log.search([], limit=10, order="create_date desc")

# # # #         return {
# # # #             "kpis": {
# # # #                 "total_fulfillments": total_fulfillments,
# # # #                 "total_internal": total_internal,
# # # #                 "total_intercompany": total_intercompany,
# # # #                 "total_failed": total_failed,
# # # #                 "total_quantity": total_quantity,
# # # #                 "total_products": total_products,
# # # #             },
# # # #             "top_warehouses": [
# # # #                 {"label": k, "value": v}
# # # #                 for k, v in sorted(top_warehouses.items(), key=lambda x: x[1], reverse=True)[:8]
# # # #             ],
# # # #             "top_products": [
# # # #                 {"label": k, "value": v}
# # # #                 for k, v in sorted(top_products.items(), key=lambda x: x[1], reverse=True)[:8]
# # # #             ],
# # # #             "top_destination_companies": [
# # # #                 {"label": k, "value": v}
# # # #                 for k, v in sorted(top_destination_companies.items(), key=lambda x: x[1], reverse=True)[:8]
# # # #             ],
# # # #             "daily_trend": [
# # # #                 {"label": k, "value": v}
# # # #                 for k, v in sorted(daily_trend.items(), key=lambda x: x[0])
# # # #             ],
# # # #             "recent_logs": [
# # # #                 {
# # # #                     "id": log.id,
# # # #                     "date": fields.Datetime.to_string(log.create_date) if log.create_date else "",
# # # #                     "picking": log.picking_id.name or "",
# # # #                     "product": log.product_id.display_name or "",
# # # #                     "type": log.fulfillment_type or "",
# # # #                     "quantity": log.quantity,
# # # #                     "state": log.state or "",
# # # #                     "source_company": log.source_company_id.display_name or "",
# # # #                     "destination_company": log.destination_company_id.display_name or "",
# # # #                     "source_warehouse": log.source_warehouse_id.display_name or "",
# # # #                 }
# # # #                 for log in recent_logs
# # # #             ],
# # # #         }

# # # # # from odoo import api, fields, models


# # # # # class AutoFulfillmentDashboard(models.Model):
# # # # #     _name = "auto.fulfillment.dashboard"
# # # # #     _description = "Auto Fulfillment Dashboard"
# # # # #     _auto = False

# # # # #     name = fields.Char(string="Name")
# # # # #     total_fulfillments = fields.Integer(string="Total Fulfillments")
# # # # #     total_internal = fields.Integer(string="Internal Transfers")
# # # # #     total_intercompany = fields.Integer(string="Intercompany Transfers")
# # # # #     total_failed = fields.Integer(string="Failed Fulfillments")
# # # # #     total_quantity = fields.Float(string="Total Quantity")
# # # # #     total_products = fields.Integer(string="Products")

# # # # #     @api.model
# # # # #     def get_dashboard_data(self):
# # # # #         Log = self.env["auto.fulfillment.log"].sudo()

# # # # #         total_fulfillments = Log.search_count([])
# # # # #         total_internal = Log.search_count([("fulfillment_type", "=", "internal"), ("state", "=", "done")])
# # # # #         total_intercompany = Log.search_count([("fulfillment_type", "=", "intercompany"), ("state", "=", "done")])
# # # # #         total_failed = Log.search_count([("state", "=", "failed")])

# # # # #         logs = Log.search([("state", "=", "done")])
# # # # #         total_quantity = sum(logs.mapped("quantity"))
# # # # #         total_products = len(set(logs.mapped("product_id").ids))

# # # # #         top_warehouses = {}
# # # # #         for log in logs:
# # # # #             key = log.source_warehouse_id.display_name or "Unknown"
# # # # #             top_warehouses[key] = top_warehouses.get(key, 0) + log.quantity

# # # # #         top_products = {}
# # # # #         for log in logs:
# # # # #             key = log.product_id.display_name or "Unknown"
# # # # #             top_products[key] = top_products.get(key, 0) + log.quantity

# # # # #         recent_logs = Log.search([], limit=10, order="create_date desc")

# # # # #         return {
# # # # #             "kpis": {
# # # # #                 "total_fulfillments": total_fulfillments,
# # # # #                 "total_internal": total_internal,
# # # # #                 "total_intercompany": total_intercompany,
# # # # #                 "total_failed": total_failed,
# # # # #                 "total_quantity": total_quantity,
# # # # #                 "total_products": total_products,
# # # # #             },
# # # # #             "top_warehouses": [
# # # # #                 {"label": k, "value": v} for k, v in sorted(top_warehouses.items(), key=lambda x: x[1], reverse=True)[:10]
# # # # #             ],
# # # # #             "top_products": [
# # # # #                 {"label": k, "value": v} for k, v in sorted(top_products.items(), key=lambda x: x[1], reverse=True)[:10]
# # # # #             ],
# # # # #             "recent_logs": [
# # # # #                 {
# # # # #                     "date": log.create_date.strftime("%Y-%m-%d %H:%M:%S") if log.create_date else "",
# # # # #                     "picking": log.picking_id.name or "",
# # # # #                     "product": log.product_id.display_name or "",
# # # # #                     "type": log.fulfillment_type or "",
# # # # #                     "quantity": log.quantity,
# # # # #                     "state": log.state or "",
# # # # #                 }
# # # # #                 for log in recent_logs
# # # # #             ],
# # # # #         }