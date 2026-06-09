from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    branch_warehouse_user_ids = fields.One2many(
        "kio.branch.warehouse.user",
        "user_id",
        string="Allowed Branch Warehouses",
    )
    branch_inventory_location_ids = fields.Many2many(
        "stock.location",
        compute="_compute_branch_inventory_location_ids",
        compute_sudo=True,
        string="Allowed Branch Inventory Locations",
    )

    @api.depends(
        "branch_warehouse_user_ids.active",
        "branch_warehouse_user_ids.location_id",
    )
    def _compute_branch_inventory_location_ids(self):
        assignments = self.env["kio.branch.warehouse.user"].sudo().search([
            ("user_id", "in", self.ids),
            ("active", "=", True),
            ("location_id", "!=", False),
        ])
        locations_by_user = {user.id: self.env["stock.location"].browse() for user in self}
        for assignment in assignments:
            locations_by_user[assignment.user_id.id] |= assignment.location_id
        for user in self:
            user.branch_inventory_location_ids = locations_by_user[user.id]
