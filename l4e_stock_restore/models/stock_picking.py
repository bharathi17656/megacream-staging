# -*- coding: utf-8 -*-

import logging

from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_stock_restore = fields.Boolean(
        string="Is Stock Restore",
        default=False,
        help="Technical flag: True if this transfer was created via Stock Restore in Manufacturing.",
    )

    is_production_only_user = fields.Boolean(
        string="Is Production Only User",
        compute="_compute_is_production_only_user",
        help="Technical flag: True if current user is a Production User and not a Store User.",
    )

    stock_restore_notified = fields.Boolean(
        string="Stock Restore Notified",
        default=False,
        copy=False,
        help="Technical flag: True if store users have already been notified for this transfer.",
    )

    @api.depends_context("uid")
    def _compute_is_production_only_user(self):
        user = self.env.user
        is_admin = user._is_admin() or user.has_group("base.group_system")
        is_prod_only = bool(user.is_production_user and not user.is_store_user and not is_admin)
        for picking in self:
            picking.is_production_only_user = is_prod_only

    def _is_stock_restore_transfer(self):
        """Determine if a picking represents a Stock Restore request."""
        self.ensure_one()
        if self.is_stock_restore:
            return True
        if self.env.context.get("is_stock_restore") or self.env.context.get("default_is_stock_restore"):
            return True
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        if (self.env.user.is_production_user and not self.env.user.is_store_user and not is_admin) and self.picking_type_code == "internal":
            return True
        # Check if this is an internal transfer to Production location
        if (
            self.picking_type_code == "internal"
            and self.location_dest_id
            and (self.location_dest_id.usage == "production" or "Production" in (self.location_dest_id.name or ""))
        ):
            return True
        return False

    def _get_stock_restore_picking_type(self):
        """Find the Internal Transfer operation type for the current company/warehouse."""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "in", [self.env.company.id, False])],
            limit=1,
        )
        if warehouse and warehouse.int_type_id:
            return warehouse.int_type_id

        return self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("company_id", "in", [self.env.company.id, False]),
            ],
            limit=1,
        )

    def _get_stock_restore_source_location(self):
        """Find WH/Stock or main internal stock location."""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "in", [self.env.company.id, False])],
            limit=1,
        )
        if warehouse and warehouse.lot_stock_id:
            return warehouse.lot_stock_id

        return self.env["stock.location"].search(
            [
                ("company_id", "in", [self.env.company.id, False]),
                ("usage", "=", "internal"),
                ("complete_name", "ilike", "WH/Stock"),
            ],
            limit=1,
        ) or self.env["stock.location"].search(
            [
                ("company_id", "in", [self.env.company.id, False]),
                ("usage", "=", "internal"),
                ("name", "ilike", "Stock"),
            ],
            limit=1,
        )

    def _get_stock_restore_dest_location(self):
        """Find WH/Production or production location."""
        return self.env["stock.location"].search(
            [
                ("company_id", "in", [self.env.company.id, False]),
                ("usage", "=", "production"),
                ("complete_name", "ilike", "WH/Production"),
            ],
            limit=1,
        ) or self.env["stock.location"].search(
            [
                ("company_id", "in", [self.env.company.id, False]),
                ("usage", "=", "production"),
            ],
            limit=1,
        ) or self.env["stock.location"].search(
            [
                ("company_id", "in", [self.env.company.id, False]),
                ("name", "ilike", "Production"),
            ],
            limit=1,
        )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        is_restore = (
            self.env.context.get("is_stock_restore")
            or self.env.context.get("default_is_stock_restore")
            or (self.env.user.is_production_user and not self.env.user.is_store_user and not is_admin and res.get("picking_type_code") == "internal")
        )
        if is_restore:
            res["is_stock_restore"] = True
            if "picking_type_id" not in res or not res.get("picking_type_id"):
                picking_type = self._get_stock_restore_picking_type()
                if picking_type:
                    res["picking_type_id"] = picking_type.id
            src_loc = self._get_stock_restore_source_location()
            if src_loc:
                res["location_id"] = src_loc.id
            dest_loc = self._get_stock_restore_dest_location()
            if dest_loc:
                res["location_dest_id"] = dest_loc.id
        return res

    @api.depends("picking_type_id", "partner_id")
    def _compute_location_id(self):
        super()._compute_location_id()
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        for picking in self:
            is_restore = (
                picking.is_stock_restore
                or self.env.context.get("is_stock_restore")
                or self.env.context.get("default_is_stock_restore")
                or (self.env.user.is_production_user and not self.env.user.is_store_user and not is_admin and picking.picking_type_code == "internal")
            )
            if is_restore and picking.state == "draft":
                src_loc = self._get_stock_restore_source_location()
                if src_loc:
                    picking.location_id = src_loc.id
                dest_loc = self._get_stock_restore_dest_location()
                if dest_loc:
                    picking.location_dest_id = dest_loc.id

    @api.model_create_multi
    def create(self, vals_list):
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        for vals in vals_list:
            is_restore = (
                vals.get("is_stock_restore")
                or self.env.context.get("is_stock_restore")
                or self.env.context.get("default_is_stock_restore")
            )
            # Check if destination location is production
            if not is_restore and vals.get("location_dest_id"):
                loc_dest = self.env["stock.location"].browse(vals["location_dest_id"])
                if loc_dest.usage == "production" or "Production" in (loc_dest.name or ""):
                    is_restore = True

            if not is_restore and (self.env.user.is_production_user and not self.env.user.is_store_user and not is_admin):
                is_restore = True

            if is_restore:
                vals["is_stock_restore"] = True
                if not vals.get("location_id"):
                    src_loc = self._get_stock_restore_source_location()
                    if src_loc:
                        vals["location_id"] = src_loc.id
                if not vals.get("location_dest_id"):
                    dest_loc = self._get_stock_restore_dest_location()
                    if dest_loc:
                        vals["location_dest_id"] = dest_loc.id
                if not vals.get("picking_type_id"):
                    pt = self._get_stock_restore_picking_type()
                    if pt:
                        vals["picking_type_id"] = pt.id

        pickings = super().create(vals_list)
        for picking in pickings:
            if picking._is_stock_restore_transfer():
                if not picking.is_stock_restore:
                    picking.sudo().write({"is_stock_restore": True})
                try:
                    picking._notify_store_users_stock_restore()
                except Exception as e:
                    _logger.exception("Error sending stock restore notification on picking create: %s", e)
        return pickings

    def action_confirm(self):
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        for picking in self:
            if not is_admin and picking.picking_type_code == "internal" and (
                picking.is_production_only_user or (self.env.user.is_production_user and not self.env.user.is_store_user)
            ):
                raise UserError(
                    _("Production users can only create Internal Transfers in Draft stage. "
                      "Store users will process and validate this transfer.")
                )
        return super().action_confirm()

    def button_validate(self):
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        for picking in self:
            if not is_admin and picking.picking_type_code == "internal" and (
                picking.is_production_only_user or (self.env.user.is_production_user and not self.env.user.is_store_user)
            ):
                raise UserError(
                    _("Production users cannot validate Internal Transfers. "
                      "Store users will process and validate this transfer.")
                )
        return super().button_validate()

    def action_assign(self):
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        for picking in self:
            if not is_admin and picking.picking_type_code == "internal" and (
                picking.is_production_only_user or (self.env.user.is_production_user and not self.env.user.is_store_user)
            ):
                raise UserError(
                    _("Production users cannot check availability on Internal Transfers. "
                      "Store users will process and validate this transfer.")
                )
        return super().action_assign()

    def write(self, vals):
        is_admin = self.env.is_admin() or self.env.user.has_group("base.group_system")
        if not is_admin and "state" in vals and vals["state"] != "draft":
            for picking in self:
                if picking.picking_type_code == "internal" and (
                    picking.is_production_only_user or (self.env.user.is_production_user and not self.env.user.is_store_user)
                ):
                    raise UserError(
                        _("Production users can only maintain Internal Transfers in Draft stage.")
                    )
        res = super().write(vals)
        for picking in self:
            if (
                picking._is_stock_restore_transfer()
                and not picking.stock_restore_notified
                and "move_ids" in vals
            ):
                try:
                    picking._notify_store_users_stock_restore()
                except Exception as e:
                    _logger.exception("Error sending stock restore notification on picking write: %s", e)
        return res

    def _notify_store_users_stock_restore(self):
        self.ensure_one()
        if not self._is_stock_restore_transfer():
            return

        if self.stock_restore_notified:
            return

        # Find all active users with is_store_user = True
        notify_users = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                ("is_store_user", "=", True),
            ]
        ).filtered(lambda u: u.partner_id)

        # Fallback: If no users have is_store_user=True, notify users in Inventory group
        if not notify_users:
            stock_group = self.env.ref("stock.group_stock_user", raise_if_not_found=False)
            if stock_group:
                group_users = stock_group.user_ids if "user_ids" in stock_group._fields else getattr(stock_group, "users", self.env["res.users"])
                notify_users = group_users.filtered(lambda u: u.active and u.partner_id)

        if not notify_users:
            _logger.warning("Stock Restore: No store or inventory users found to notify for picking %s.", self.name)
            return

        _logger.info(
            "Stock Restore: Notifying %s store users (%s) for picking %s",
            len(notify_users),
            notify_users.mapped("name"),
            self.name,
        )

        partner_ids = notify_users.mapped("partner_id").ids
        author_id = self.env.user.partner_id.id if self.env.user.partner_id else False

        # Build product lines list
        lines_html = ""
        moves = getattr(self, "move_ids", None)
        if moves:
            item_rows = []
            for move in moves:
                uom = getattr(move, "product_uom_id", None) or getattr(move, "product_uom", None)
                uom_name = uom.name if uom else ""
                prod_name = move.product_id.display_name or move.name or "Item"
                qty = getattr(move, "product_uom_qty", 0) or getattr(move, "quantity", 0)
                item_rows.append(
                    f"<li><b>{prod_name}</b>: {qty} {uom_name}</li>"
                )
            if item_rows:
                lines_html = f"<p><b>Items Requested:</b></p><ul>{''.join(item_rows)}</ul>"

        source_loc = self.location_id.display_name or ""
        dest_loc = self.location_dest_id.display_name or ""
        created_by = self.env.user.name or ""
        sched_date = self.scheduled_date or ""
        picking_name = self.name or "Draft Internal Transfer"

        body = Markup(
            f"<p><b>New Stock Restore Request Created (Draft)</b></p>"
            f"<ul>"
            f"<li><b>Transfer:</b> {picking_name}</li>"
            f"<li><b>Created By:</b> {created_by}</li>"
            f"<li><b>Source Location:</b> {source_loc}</li>"
            f"<li><b>Destination Location:</b> {dest_loc}</li>"
            f"<li><b>Scheduled Date:</b> {sched_date}</li>"
            f"<li><b>State:</b> Draft</li>"
            f"</ul>"
            f"{lines_html}"
            f"<p><i>Please go to <b>Inventory → Operations → Internal Transfers</b> to process and validate.</i></p>"
        )
        subject = f"Stock Restore Request: {picking_name}"

        # 1. Post to transfer chatter using sudo() and author_id
        message = self.sudo().message_post(
            body=body,
            subject=subject,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids,
            author_id=author_id,
        )

        # 2. Force inbox notification for each store user in Discuss Inbox
        for user in notify_users:
            notif = self.env["mail.notification"].sudo().search(
                [
                    ("mail_message_id", "=", message.id),
                    ("res_partner_id", "=", user.partner_id.id),
                ],
                limit=1,
            )
            if notif:
                notif.sudo().write({"notification_type": "inbox", "is_read": False})
            else:
                self.env["mail.notification"].sudo().create(
                    {
                        "mail_message_id": message.id,
                        "res_partner_id": user.partner_id.id,
                        "notification_type": "inbox",
                        "notification_status": "sent",
                        "is_read": False,
                    }
                )

            # Bus notification for real-time Discuss Inbox update
            try:
                from odoo.addons.mail.tools.discuss import Store

                store = Store(bus_channel=user).add(message.with_user(user))
                user._bus_send(
                    "mail.message/inbox",
                    {
                        "message_id": message.id,
                        "store_data": store.get_result(),
                    },
                )
            except Exception as e:
                _logger.debug("Bus send error: %s", e)

            # 3. Direct Message in Discuss chat with each store user (if different partner)
            if user.partner_id.id != author_id:
                try:
                    chat = self.env["discuss.channel"].sudo()._get_or_create_chat(
                        partners_to=[user.partner_id.id], pin=True
                    )
                    if chat:
                        chat.sudo().message_post(
                            body=body,
                            message_type="comment",
                            subtype_xmlid="mail.mt_comment",
                            author_id=author_id,
                        )
                except Exception as e:
                    _logger.warning("Could not send chat message to store user %s: %s", user.name, e)

        # Mark as notified to avoid duplicate alerts
        self.sudo().write({"stock_restore_notified": True, "is_stock_restore": True})
