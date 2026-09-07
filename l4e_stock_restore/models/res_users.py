# -*- coding: utf-8 -*-

from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        group = self.env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
        if group:
            for user in users:
                if user.is_production_user and group not in user.groups_id:
                    user.groups_id = [(4, group.id)]
        return users

    def write(self, vals):
        res = super().write(vals)
        if "is_production_user" in vals:
            group = self.env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
            if group:
                for user in self:
                    if user.is_production_user and group not in user.groups_id:
                        user.groups_id = [(4, group.id)]
                    elif not user.is_production_user and group in user.groups_id:
                        user.groups_id = [(3, group.id)]
        return res
