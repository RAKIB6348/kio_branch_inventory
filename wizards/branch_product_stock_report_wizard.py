# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BranchProductStockReportWizard(models.TransientModel):
    _name = "branch.product.stock.report.wizard"
    _description = "Warehouse Product Stock Report Wizard"

    report_type = fields.Selection(
        [
            ("all", "All Warehouses"),
            ("specific", "Specific Warehouse"),
        ],
        string="Report Type",
        required=True,
        default="all",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
    )
    available_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        compute="_compute_available_warehouse_ids",
    )
    category_id = fields.Many2one(
        "product.category",
        string="Product Category",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
    )
    active_products_only = fields.Boolean(
        string="Active Products Only",
        default=True,
    )

    @api.depends_context("uid")
    def _compute_available_warehouse_ids(self):
        for wizard in self:
            wizard.available_warehouse_ids = wizard._get_allowed_warehouses()

    @api.onchange("report_type")
    def _onchange_report_type(self):
        if self.report_type == "all":
            self.warehouse_id = False
        return self._get_warehouse_domain()

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        return self._get_warehouse_domain()

    def _get_warehouse_domain(self):
        return {"domain": {"warehouse_id": [("id", "in", self._get_allowed_warehouses().ids)]}}

    def _is_report_admin(self):
        return (
            self.env.is_superuser()
            or self.env.user.has_group("kio_branch_inventory.group_branch_inventory_admin")
            or self.env.user.has_group("stock.group_stock_manager")
        )

    def _get_allowed_warehouses(self):
        Warehouse = self.env["stock.warehouse"]
        if self._is_report_admin():
            return Warehouse.search([])
        return self.env.user.branch_warehouse_user_ids.mapped("warehouse_id")

    def _get_report_warehouses(self):
        self.ensure_one()
        allowed_warehouses = self._get_allowed_warehouses()
        if not allowed_warehouses:
            raise UserError(_("No warehouse is assigned to your user."))

        if self.report_type == "specific":
            if not self.warehouse_id:
                raise UserError(_("Please select a Warehouse."))
            if self.warehouse_id not in allowed_warehouses:
                raise UserError(_("You are not allowed to generate a report for this warehouse."))
            return self.warehouse_id

        return allowed_warehouses

    def _get_products(self):
        self.ensure_one()
        domain = []
        if self.active_products_only:
            domain.append(("active", "=", True))
        if self.category_id:
            domain.append(("categ_id", "child_of", self.category_id.id))
        if self.product_id:
            domain.append(("id", "=", self.product_id.id))
        return self.env["product.product"].with_context(active_test=False).search(domain, order="default_code, name")

    def action_print_report(self):
        self.ensure_one()
        warehouses = self._get_report_warehouses()
        products = self._get_products()
        data = {
            "wizard_id": self.id,
            "warehouse_ids": warehouses.ids,
            "product_ids": products.ids,
        }
        return self.env.ref("kio_branch_inventory.action_report_branch_product_stock").report_action(products, data=data)
