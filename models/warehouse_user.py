# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BranchWarehouseUser(models.Model):
    _name = "kio.branch.warehouse.user"
    _description = "Warehouse User"
    _rec_name = "user_id"

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
        ondelete="cascade",
        help="Select the specific warehouse to which the user is being assigned.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="warehouse_id.company_id",
        store=True,
        readonly=True,
        help="The company associated with the selected warehouse. This is automatically determined.",
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Stock Location",
        required=True,
        ondelete="cascade",
        help="Select the specific internal stock location within the chosen warehouse.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="cascade",
        help="The user who is being granted access to this warehouse and stock location.",
    )
    active = fields.Boolean(
        default=True,
        help="If unchecked, it will allow you to hide the record without deleting it.",
    )

    _sql_constraints = [
        (
            "warehouse_user_unique",
            "unique(warehouse_id, location_id, user_id)",
            "This user is already assigned to this warehouse location.",
        ),
    ]

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        domain = [("usage", "=", "internal")]
        if self.warehouse_id:
            domain.append(("warehouse_id", "=", self.warehouse_id.id))
            self.location_id = self.warehouse_id.lot_stock_id
        else:
            self.location_id = False
        return {"domain": {"location_id": domain}}

    @api.constrains("warehouse_id", "location_id")
    def _check_location_warehouse(self):
        for record in self:
            if (
                record.warehouse_id
                and record.location_id
                and record.location_id.warehouse_id
                and record.location_id.warehouse_id != record.warehouse_id
            ):
                raise ValidationError("Stock Location must belong to the selected Warehouse.")

    @api.depends("warehouse_id", "location_id", "user_id")
    def _compute_display_name(self):
        for record in self:
            if record.warehouse_id and record.location_id and record.user_id:
                record.display_name = "%s - %s - %s" % (
                    record.warehouse_id.display_name,
                    record.location_id.display_name,
                    record.user_id.display_name,
                )
            else:
                record.display_name = record.user_id.display_name or record.location_id.display_name or record.warehouse_id.display_name