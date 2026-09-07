# -*- coding: utf-8 -*-
from . import models


def _post_init_hook(env):
    """Ensure all existing users with is_production_user=True are added to group_production_user."""
    group = env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
    if group:
        prod_users = env["res.users"].sudo().search([("is_production_user", "=", True)])
        for user in prod_users:
            if group not in user.groups_id:
                user.groups_id = [(4, group.id)]
