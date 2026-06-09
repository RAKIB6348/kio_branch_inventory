# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError


_BRANCH_INVENTORY_QUANT_DOMAIN_APPLIED = "branch_inventory_quant_domain_applied"


class StockQuant(models.Model):
    _inherit = "stock.quant"

    branch_inventory_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        related="location_id.warehouse_id",
        store=True,
        index=True,
        readonly=True,
    )

    branch_inventory_available_product = fields.Boolean(
        string="Available Product",
        compute="_compute_branch_inventory_available_product",
        store=True,
        index=True,
        readonly=True,
    )

    @api.depends("quantity", "reserved_quantity")
    def _compute_branch_inventory_available_product(self):
        for quant in self:
            quant.branch_inventory_available_product = (
                quant.quantity - quant.reserved_quantity
            ) > 0

    @api.model
    def action_branch_increment_inventory_by_barcode(self, barcode, domain=None):
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please scan a valid product barcode."))

        products = self.env["product.product"].search([("barcode", "=", barcode)])
        if not products:
            packaging = self.env["product.packaging"].search([("barcode", "=", barcode)], limit=1)
            products = packaging.product_id if packaging else products
        if not products:
            raise UserError(_("No product found for barcode %s.") % barcode)

        active_warehouse_id = self.env.context.get("branch_inventory_active_warehouse_id")
        if not active_warehouse_id:
            raise UserError(_("Please select one warehouse before scanning."))

        warehouse = self.env["stock.warehouse"].browse(active_warehouse_id).exists()
        if not warehouse:
            raise UserError(_("The selected warehouse is no longer available."))
        product = products[:1]
        location = warehouse.lot_stock_id

        quant_domain = [
            ("branch_inventory_warehouse_id", "=", warehouse.id),
            ("location_id", "=", location.id),
            ("product_id", "=", product.id),
        ]
        quant = self.search(quant_domain, limit=1)
        if not quant:
            quant = self.with_context(inventory_mode=True).create({
                "product_id": product.id,
                "location_id": location.id,
                "inventory_quantity": 0,
            })

        counted_quantity = quant.inventory_quantity if quant.inventory_quantity_set else 0
        quant.inventory_quantity = counted_quantity + 1
        return {
            "product": quant.product_id.display_name,
            "counted_quantity": quant.inventory_quantity,
            "location": quant.location_id.display_name,
            "warehouse": quant.branch_inventory_warehouse_id.display_name,
        }

    def action_branch_approve_inventory(self):
        quants_to_apply = self.filtered("inventory_quantity_set")
        if not self:
            quants_to_apply = self.search([
                ("inventory_quantity_set", "=", True),
                ("location_id.usage", "=", "internal"),
            ])
        if not quants_to_apply:
            raise UserError(_("Please save a counted quantity before approving."))

        log_values = []
        for quant in quants_to_apply:
            if fields.Float.is_zero(
                quant.inventory_diff_quantity,
                precision_rounding=quant.product_uom_id.rounding,
            ):
                continue
            log_values.append({
                "quant_id": quant.id,
                "product_id": quant.product_id.id,
                "warehouse_id": quant.branch_inventory_warehouse_id.id,
                "location_id": quant.location_id.id,
                "previous_quantity": quant.quantity,
                "counted_quantity": quant.inventory_quantity,
                "difference_quantity": quant.inventory_diff_quantity,
                "product_uom_id": quant.product_uom_id.id,
                "approved_by_id": self.env.user.id,
                "company_id": quant.company_id.id,
            })

        result = quants_to_apply.action_apply_inventory()
        if not result and log_values:
            self.env["kio.branch.inventory.quant.update.log"].sudo().create(log_values)
        return result

    @api.model
    def _branch_inventory_location_domain(self):
        user = self.env.user
        if (
            not user.has_group("kio_branch_inventory.group_branch_inventory_user")
            or user.has_group("kio_branch_inventory.group_branch_inventory_admin")
        ):
            return []

        location_ids = self.env["kio.branch.warehouse.user"].sudo().search([
            ("user_id", "=", user.id),
            ("active", "=", True),
            ("location_id", "!=", False),
        ]).mapped("location_id").ids

        if not location_ids:
            return [("id", "=", 0)]
        return [("location_id", "child_of", location_ids)]

    @api.model
    def _branch_inventory_normalize_domain(self, domain):
        if not domain:
            return []

        normalized = []
        for item in domain:
            if isinstance(item, (list, tuple)) and item:
                if isinstance(item[0], (list, tuple)):
                    normalized.append(self._branch_inventory_normalize_domain(item))
                    continue
                if not isinstance(item[0], str):
                    left = item[0]
                    operator = item[1] if len(item) > 1 else "="
                    right = item[2] if len(item) > 2 else True
                    is_true = (operator == "=" and left == right) or (operator == "!=" and left != right)
                    normalized.append(("id", "!=", 0) if is_true else ("id", "=", 0))
                    continue
            normalized.append(item)
        return normalized

    @api.model
    def _apply_branch_inventory_location_domain(self, domain):
        domain = self._branch_inventory_normalize_domain(domain or [])
        if self.env.context.get(_BRANCH_INVENTORY_QUANT_DOMAIN_APPLIED):
            return domain
        return expression.AND([
            domain,
            self._branch_inventory_location_domain(),
        ])

    def _with_branch_inventory_domain_applied(self):
        return self.with_context(**{_BRANCH_INVENTORY_QUANT_DOMAIN_APPLIED: True})

    @api.model
    def action_view_inventory(self):
        action = super().action_view_inventory()
        location_domain = self._branch_inventory_location_domain()
        if location_domain:
            context = dict(action.get("context") or {})
            context.pop("search_default_my_count", None)
            action["context"] = context
        action["domain"] = expression.AND([
            action.get("domain") or [],
            location_domain,
        ])
        return action

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        domain = self._apply_branch_inventory_location_domain(domain)
        return super(
            StockQuant,
            self._with_branch_inventory_domain_applied(),
        ).search(domain, offset=offset, limit=limit, order=order)

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        domain = self._apply_branch_inventory_location_domain(domain)
        return super(
            StockQuant,
            self._with_branch_inventory_domain_applied(),
        ).search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    @api.model
    def search_count(self, domain, limit=None):
        domain = self._apply_branch_inventory_location_domain(domain)
        return super(
            StockQuant,
            self._with_branch_inventory_domain_applied(),
        ).search_count(domain, limit=limit)

    @api.model
    def _search(self, domain, *args, **kwargs):
        domain = self._apply_branch_inventory_location_domain(domain)
        return super(
            StockQuant,
            self._with_branch_inventory_domain_applied(),
        )._search(domain, *args, **kwargs)

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        domain = self._apply_branch_inventory_location_domain(domain)
        return super(
            StockQuant,
            self._with_branch_inventory_domain_applied(),
        ).read_group(
            domain,
            fields,
            groupby,
            offset=offset,
            limit=limit,
            orderby=orderby,
            lazy=lazy,
        )

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None):
        domain = self._apply_branch_inventory_location_domain(domain)
        return super(
            StockQuant,
            self._with_branch_inventory_domain_applied(),
        )._read_group(
            domain,
            groupby=groupby,
            aggregates=aggregates,
            having=having,
            offset=offset,
            limit=limit,
            order=order,
        )


class BranchInventoryQuantUpdateLog(models.Model):
    _name = "kio.branch.inventory.quant.update.log"
    _description = "Branch Inventory Quantity Update Log"
    _order = "approved_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Reference", compute="_compute_name", store=True)
    quant_id = fields.Many2one("stock.quant", string="Quant", readonly=True, ondelete="set null")
    product_id = fields.Many2one("product.product", string="Product", required=True, readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", readonly=True)
    location_id = fields.Many2one("stock.location", string="Location", required=True, readonly=True)
    previous_quantity = fields.Float(string="Previous Quantity", readonly=True, digits="Product Unit of Measure")
    counted_quantity = fields.Float(string="Approved Quantity", readonly=True, digits="Product Unit of Measure")
    difference_quantity = fields.Float(string="Difference", readonly=True, digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", string="UoM", readonly=True)
    approved_by_id = fields.Many2one("res.users", string="Updated By", required=True, readonly=True)
    approved_date = fields.Datetime(string="Updated On", default=fields.Datetime.now, required=True, readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)

    @api.depends("product_id", "approved_date")
    def _compute_name(self):
        for log in self:
            product_name = log.product_id.display_name or _("Quantity Update")
            if log.approved_date:
                log.name = _("%s on %s") % (product_name, log.approved_date)
            else:
                log.name = product_name


class BranchPhysicalInventoryWarehouseWizard(models.TransientModel):
    _name = "kio.branch.physical.inventory.warehouse.wizard"
    _description = "Select Warehouse for Physical Inventory"

    allowed_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        compute="_compute_allowed_warehouse_ids",
        string="Allowed Warehouses",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
    )

    @api.depends_context("uid")
    def _compute_allowed_warehouse_ids(self):
        user = self.env.user
        if (
            user.has_group("kio_branch_inventory.group_branch_inventory_user")
            and not user.has_group("kio_branch_inventory.group_branch_inventory_admin")
        ):
            warehouses = self.env["kio.branch.warehouse.user"].sudo().search([
                ("user_id", "=", user.id),
                ("active", "=", True),
                ("warehouse_id", "!=", False),
            ]).mapped("warehouse_id")
        else:
            warehouses = self.env["stock.warehouse"].search([])
        for wizard in self:
            wizard.allowed_warehouse_ids = warehouses

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        user = self.env.user
        if (
            user.has_group("kio_branch_inventory.group_branch_inventory_user")
            and not user.has_group("kio_branch_inventory.group_branch_inventory_admin")
        ):
            warehouses = self.env["kio.branch.warehouse.user"].sudo().search([
                ("user_id", "=", user.id),
                ("active", "=", True),
                ("warehouse_id", "!=", False),
            ]).mapped("warehouse_id")
        else:
            warehouses = self.env["stock.warehouse"].search([])
        if len(warehouses) == 1:
            values["warehouse_id"] = warehouses.id
        return values

    def action_open_physical_inventory(self):
        self.ensure_one()
        action = self.env.ref("kio_branch_inventory.action_branch_physical_inventory").read()[0]
        action_domain = action.get("domain") or []
        if isinstance(action_domain, str):
            action_domain = safe_eval(action_domain)
        action["domain"] = expression.AND([
            action_domain,
            [("branch_inventory_warehouse_id", "=", self.warehouse_id.id)],
        ])

        action_context = action.get("context") or {}
        if isinstance(action_context, str):
            action_context = safe_eval(action_context)
        context = dict(action_context)
        context.pop("search_default_not_counted", None)
        context.update({
            "inventory_mode": True,
            "branch_inventory_active_warehouse_id": self.warehouse_id.id,
        })
        action["context"] = context
        action["name"] = _("Physical Inventory Audit - %s") % self.warehouse_id.display_name
        return action
