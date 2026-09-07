# -*- coding: utf-8 -*-
from . import models


def _post_init_hook(env):
    """Ensure all existing users with is_production_user=True are added to group_production_user."""
    group = env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
    if group:
        prod_users = env["res.users"].sudo().search([("is_production_user", "=", True)])
        for user in prod_users:
            groups_field = "group_ids" if hasattr(user, "group_ids") else "groups_id"
            if group not in getattr(user, groups_field):
                setattr(user, groups_field, [(4, group.id)])
