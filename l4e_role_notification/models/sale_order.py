# -*- coding: utf-8 -*-

from markupsafe import Markup
from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            order._notify_store_production_users(event="created")
        return orders

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order._notify_store_production_users(event="confirmed")
        return res

    def _notify_store_production_users(self, event="created"):
        self.ensure_one()
        # Check if the creator/salesperson is a Sales User
        is_sales = self.env.user.is_sales_user or (self.user_id and self.user_id.is_sales_user)
        if not is_sales:
            return

        # Find all active Store and Production users
        notify_users = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                "|",
                ("is_store_user", "=", True),
                ("is_production_user", "=", True),
            ]
        )
        # Exclude the current user if they are in the list
        notify_users = notify_users.filtered(lambda u: u.id != self.env.user.id and u.partner_id)
        if not notify_users:
            return

        partner_ids = notify_users.mapped("partner_id").ids
        event_label = "Created" if event == "created" else "Confirmed"

        # Build order items list
        lines_html = ""
        order_lines = self.order_line.filtered(lambda l: not l.display_type)
        if order_lines:
            item_rows = "".join(
                f"<li><b>{line.product_id.display_name or line.name}</b>: {line.product_uom_qty} {line.product_uom.name or ''}</li>"
                for line in order_lines
            )
            lines_html = f"<p><b>Items:</b></p><ul>{item_rows}</ul>"

        currency_name = self.currency_id.symbol or self.currency_id.name or ""
        customer_name = self.partner_id.name or ""
        salesperson_name = self.user_id.name or self.env.user.name or ""
        order_date = self.date_order or ""

        body = Markup(
            f"<p><b>Sales Order {event_label}</b></p>"
            f"<ul>"
            f"<li><b>Order:</b> {self.name}</li>"
            f"<li><b>Customer:</b> {customer_name}</li>"
            f"<li><b>Salesperson:</b> {salesperson_name}</li>"
            f"<li><b>Order Date:</b> {order_date}</li>"
            f"<li><b>Total:</b> {self.amount_total} {currency_name}</li>"
            f"</ul>"
            f"{lines_html}"
        )
        subject = f"Sales Order {event_label}: {self.name}"

        # 1. Post to order chatter
        message = self.message_post(
            body=body,
            subject=subject,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids,
        )

        # 2. Force inbox notification for each recipient so Discuss Inbox receives it
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
            except Exception:
                pass

            # 3. Direct Message in Discuss chat with each user
            try:
                chat = self.env["discuss.channel"].sudo()._get_or_create_chat(
                    partners_to=[user.partner_id.id], pin=True
                )
                if chat:
                    chat.message_post(
                        body=body,
                        message_type="comment",
                        subtype_xmlid="mail.mt_comment",
                    )
            except Exception:
                pass
