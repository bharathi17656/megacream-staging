# -*- coding: utf-8 -*-
from . import models


def _post_init_hook(env):
    """Ensure all existing users with is_production_user=True are in group_production_user and others removed."""
    group = env.ref("l4e_stock_restore.group_production_user", raise_if_not_found=False)
    if group:
        prod_users = env["res.users"].sudo().search([("is_production_user", "=", True)])
        non_prod_users = env["res.users"].sudo().search([("is_production_user", "!=", True)])
        if prod_users:
            group.sudo().write({"users": [(4, u.id) for u in prod_users]})
        if non_prod_users:
            group.sudo().write({"users": [(3, u.id) for u in non_prod_users]})
