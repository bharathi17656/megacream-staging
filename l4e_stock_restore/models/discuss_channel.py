# -*- coding: utf-8 -*-

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _get_or_create_chat(self, partners_to, pin=True):
        """
        Find or create a 1-to-1 direct chat channel between the current user and the partner(s) in partners_to.
        Ensures the recipient's channel membership is pinned and folded so that the chat bubble
        pops up in the bottom-right corner of their screen.
        """
        if not partners_to:
            return self.env["discuss.channel"]

        current_partner = self.env.user.partner_id
        target_partner_ids = [pid for pid in list(set(partners_to)) if pid != current_partner.id]
        if not target_partner_ids:
            return self.env["discuss.channel"]

        all_partner_ids = list(set(target_partner_ids + [current_partner.id]))
        channel = None

        # 1. Try standard channel_get
        if hasattr(self, "channel_get"):
            try:
                author_user = self.env["res.users"].sudo().search([("partner_id", "=", current_partner.id)], limit=1)
                ctx_model = self.with_user(author_user) if author_user else self
                res = ctx_model.channel_get(target_partner_ids)
                cid = res.get("id") if isinstance(res, dict) else getattr(res, "id", None)
                if cid:
                    channel = self.browse(cid)
            except Exception as e:
                _logger.debug("channel_get failed: %s", e)

        # 2. Fallback: Search for existing 1-on-1 chat channel
        if not channel:
            try:
                candidates = self.search([
                    ("channel_type", "=", "chat"),
                    ("channel_partner_ids", "in", [current_partner.id]),
                ])
                for cand in candidates:
                    if set(cand.channel_partner_ids.ids) == set(all_partner_ids):
                        channel = cand
                        break
            except Exception as e:
                _logger.debug("channel search failed: %s", e)

        # 3. Fallback: Create new direct chat channel
        if not channel:
            try:
                names = [self.env["res.partner"].browse(pid).name or "User" for pid in all_partner_ids]
                channel = self.create({
                    "name": ", ".join(names),
                    "channel_type": "chat",
                    "channel_partner_ids": [(6, 0, all_partner_ids)],
                })
            except Exception as e:
                _logger.exception("Failed to create direct chat channel: %s", e)
                return self.env["discuss.channel"]

        # 4. Pin and set fold_state to 'folded' for the target recipient(s)
        # This triggers the floating chat bubble in the bottom-right corner of their screen!
        try:
            for pid in target_partner_ids:
                member = channel.channel_member_ids.filtered(lambda m: m.partner_id.id == pid)
                if not member:
                    member = self.env["discuss.channel.member"].create({
                        "channel_id": channel.id,
                        "partner_id": pid,
                        "is_pinned": bool(pin),
                        "fold_state": "folded",
                    })
                else:
                    member_vals = {}
                    if pin and not member.is_pinned:
                        member_vals["is_pinned"] = True
                    if "fold_state" in member._fields and member.fold_state != "folded":
                        member_vals["fold_state"] = "folded"
                    if member_vals:
                        member.write(member_vals)
        except Exception as e:
            _logger.debug("Failed to pin/fold channel for member %s: %s", target_partner_ids, e)

        return channel
