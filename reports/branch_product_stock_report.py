# -*- coding: utf-8 -*-

from odoo import fields, models


class ReportBranchProductStock(models.AbstractModel):
    _name = "report.kio_branch_inventory.report_branch_product_stock"
    _description = "Warehouse Product Stock PDF Report"

    def _get_report_values(self, docids, data=None):
        data = data or {}

        wizard = False
        if data.get("wizard_id"):
            wizard = self.env["branch.product.stock.report.wizard"].browse(data.get("wizard_id"))

        products = self.env["product.product"].browse(data.get("product_ids") or docids)

        if not products:
            products = self.env["product.product"].search([("active", "=", True)])

        assigned_records = self.env["kio.branch.warehouse.user"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("active", "=", True),
        ])

        warehouses = assigned_records.mapped("warehouse_id")

        if not warehouses and self.env.user.has_group("kio_branch_inventory.group_branch_inventory_admin"):
            warehouses = self.env["stock.warehouse"].sudo().search([])

        rows = []
        totals = {
            "total_products": 0,
            "qty_available": 0.0,
            "free_qty": 0.0,
            "incoming_qty": 0.0,
            "outgoing_qty": 0.0,
        }

        serial = 1

        for warehouse in warehouses:
            for product in products:
                product_ctx = product.with_context(warehouse=warehouse.id)

                qty_available = product_ctx.qty_available
                free_qty = product_ctx.free_qty
                incoming_qty = product_ctx.incoming_qty
                outgoing_qty = product_ctx.outgoing_qty

                rows.append({
                    "serial": serial,
                    "warehouse": warehouse.display_name,
                    "product": product.display_name,
                    "default_code": product.default_code or "",
                    "category": product.categ_id.display_name or "",
                    "qty_available": qty_available,
                    "free_qty": free_qty,
                    "incoming_qty": incoming_qty,
                    "outgoing_qty": outgoing_qty,
                    "uom": product.uom_id.name or "",
                })

                totals["qty_available"] += qty_available
                totals["free_qty"] += free_qty
                totals["incoming_qty"] += incoming_qty
                totals["outgoing_qty"] += outgoing_qty
                serial += 1

        totals["total_products"] = len(rows)

        selected_branch = ", ".join(warehouses.mapped("display_name")) if warehouses else "No Assigned Warehouse"

        return {
            "doc_ids": products.ids,
            "doc_model": "product.product",
            "docs": products,
            "wizard": wizard,
            "warehouses": warehouses,
            "rows": rows,
            "totals": totals,
            "company": self.env.company,
            "generated_by": self.env.user,
            "generated_at": fields.Datetime.context_timestamp(self, fields.Datetime.now()),
            "report_type_label": "Assigned Warehouse Stock",
            "selected_branch": selected_branch,
        }