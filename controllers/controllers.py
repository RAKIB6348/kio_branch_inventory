# -*- coding: utf-8 -*-
# from odoo import http


# class KioBranchInventory(http.Controller):
#     @http.route('/kio_branch_inventory/kio_branch_inventory', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/kio_branch_inventory/kio_branch_inventory/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('kio_branch_inventory.listing', {
#             'root': '/kio_branch_inventory/kio_branch_inventory',
#             'objects': http.request.env['kio_branch_inventory.kio_branch_inventory'].search([]),
#         })

#     @http.route('/kio_branch_inventory/kio_branch_inventory/objects/<model("kio_branch_inventory.kio_branch_inventory"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('kio_branch_inventory.object', {
#             'object': obj
#         })

