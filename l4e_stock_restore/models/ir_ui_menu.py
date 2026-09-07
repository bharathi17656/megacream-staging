# -*- coding: utf-8 -*-

from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        # If the current user does NOT have the Production User flag,
        # blacklist the Stock restore menu so it does not appear in Manufacturing
        if not self.env.user.is_production_user:
            stock_restore_menu = self.env.ref(
                "l4e_stock_restore.menu_mrp_stock_restore", raise_if_not_found=False
            )
            if stock_restore_menu:
                res = list(res) if res is not None else []
                if stock_restore_menu.id not in res:
                    res.append(stock_restore_menu.id)
        return res
