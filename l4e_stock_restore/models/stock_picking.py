import logging

from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_production_only_user = fields.Boolean(
        string="Is Production Only User",
        compute="_compute_is_production_only_user",
        help="Technical flag: True if current user has Production User role but not Store User or Stock Manager.",
    )

    @api.depends_context("uid")
    def _compute_is_production_only_user(self):
        user = self.env.user
        is_prod_only = bool(
            user.is_production_user
            and not user.is_store_user
            and not user.has_group("stock.group_stock_manager")
        )
        for picking in self:
            picking.is_production_only_user = is_prod_only

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        for picking in pickings:
            if picking.picking_type_code == "internal":
                try:
                    picking._notify_store_users_stock_restore()
                except Exception as e:
                    _logger.exception("Error sending stock restore notification on picking create: %s", e)
        return pickings

    def action_confirm(self):
        for picking in self:
            if picking.picking_type_code == "internal" and picking.is_production_only_user:
                raise UserError(
                    _("Production users can only create Internal Transfers in Draft stage. "
                      "Store users will process and validate this transfer.")
                )
        return super().action_confirm()

    def button_validate(self):
        for picking in self:
            if picking.picking_type_code == "internal" and picking.is_production_only_user:
                raise UserError(
                    _("Production users cannot validate Internal Transfers. "
                      "Store users will process and validate this transfer.")
                )
        return super().button_validate()

    def _notify_store_users_stock_restore(self):
        self.ensure_one()
        # Only notify if created by a user with the Production User role
        if not self.env.user.is_production_user:
            return

        # Find all active Store users
        notify_users = self.env["res.users"].sudo().search(
            [
                ("active", "=", True),
                ("is_store_user", "=", True),
            ]
        )
        # Exclude the creator if they happen to be flagged with both roles
        notify_users = notify_users.filtered(lambda u: u.id != self.env.user.id and u.partner_id)
        if not notify_users:
            return

        partner_ids = notify_users.mapped("partner_id").ids

        # Build product lines list
        lines_html = ""
        moves = self.move_ids_without_package or self.move_ids
        if moves:
            item_rows = []
            for move in moves:
                uom = getattr(move, "product_uom", None) or getattr(move, "product_uom_id", None)
                uom_name = uom.name if uom else ""
                prod_name = move.product_id.display_name or move.name or "Item"
                qty = getattr(move, "product_uom_qty", 0)
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
            f"<li><b>Created By (Production):</b> {created_by}</li>"
            f"<li><b>Source Location:</b> {source_loc}</li>"
            f"<li><b>Destination Location:</b> {dest_loc}</li>"
            f"<li><b>Scheduled Date:</b> {sched_date}</li>"
            f"<li><b>State:</b> Draft</li>"
            f"</ul>"
            f"{lines_html}"
            f"<p><i>Please go to <b>Inventory → Operations → Internal Transfers</b> to process and validate.</i></p>"
        )
        subject = f"Stock Restore Request: {picking_name}"

        # 1. Post to transfer chatter
        message = self.message_post(
            body=body,
            subject=subject,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids,
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
            except Exception:
                pass

            # 3. Direct Message in Discuss chat with each store user
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
