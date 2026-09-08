# -*- coding: utf-8 -*-

from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def init(self):
        super().init()
        # Automatically sync res_groups_users_rel for all users with is_production_user = True
        # and remove any users who do not have is_production_user = True
        self.env.cr.execute("""
            INSERT INTO res_groups_users_rel (gid, uid)
            SELECT g.id, u.id
            FROM res_users u
            CROSS JOIN (
                SELECT res_id AS id
                FROM ir_model_data
                WHERE module = 'l4e_stock_restore' AND name = 'group_production_user'
            ) g
            WHERE u.is_production_user = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM res_groups_users_rel rel WHERE rel.gid = g.id AND rel.uid = u.id
              );
            DELETE FROM res_groups_users_rel
            WHERE gid IN (
                SELECT res_id
                FROM ir_model_data
                WHERE module = 'l4e_stock_restore' AND name = 'group_production_user'
            )
            AND uid IN (
                SELECT id FROM res_users WHERE is_production_user IS NOT TRUE
            );
        """)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        group = self.env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
        if group:
            user_field = "user_ids" if "user_ids" in group._fields else "users"
            to_add = users.filtered(lambda u: u.is_production_user)
            if to_add:
                group.sudo().write({user_field: [(4, u.id) for u in to_add]})
        return users

    def write(self, vals):
        res = super().write(vals)
        if "is_production_user" in vals:
            group = self.env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
            if group:
                user_field = "user_ids" if "user_ids" in group._fields else "users"
                current_members = group[user_field]
                commands = []
                for user in self:
                    if user.is_production_user and user not in current_members:
                        commands.append((4, user.id))
                    elif not user.is_production_user and user in current_members:
                        commands.append((3, user.id))
                if commands:
                    group.sudo().write({user_field: commands})
            # Invalidate menu cache so the Stock restore menu immediately shows/hides
            self.env["ir.ui.menu"].clear_caches()
            self.env.registry.clear_cache()
        return res
