# -*- coding: utf-8 -*-

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _get_or_create_chat(self, partners_to, pin=True):
        """
        Extend standard _get_or_create_chat to ensure target recipient(s) have
        their channel membership pinned and folded so chat bubbles appear.
        """
        channel = super()._get_or_create_chat(partners_to, pin=pin)
        if channel:
            try:
                current_partner_id = self.env.user.partner_id.id
                target_pids = [pid for pid in (partners_to or []) if pid != current_partner_id]
                for pid in target_pids:
                    member = channel.channel_member_ids.filtered(lambda m: m.partner_id.id == pid)
                    if member:
                        member_vals = {}
                        if pin and not member.is_pinned:
                            member_vals["is_pinned"] = True
                        if "fold_state" in member._fields and member.fold_state != "folded":
                            member_vals["fold_state"] = "folded"
                        if member_vals:
                            member.sudo().write(member_vals)
            except Exception as e:
                _logger.debug("Failed to set pin/fold state on channel: %s", e)
        return channel
