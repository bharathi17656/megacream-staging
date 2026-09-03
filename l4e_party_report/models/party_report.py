# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class L4ePartyReport(models.Model):
    _name = "l4e.party.report"
    _description = "Party & Customer Inactivity Report"
    _auto = False
    _order = "days_since_last_order desc nulls last, last_order_date desc"

    partner_id = fields.Many2one("res.partner", string="Customer / Party", readonly=True)
    phone = fields.Char(string="Phone", readonly=True)
    email = fields.Char(string="Email", readonly=True)
    city = fields.Char(string="City", readonly=True)
    state_id = fields.Many2one("res.country.state", string="State", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    is_party_order = fields.Boolean(string="Party Order", readonly=True)
    last_order_id = fields.Many2one("sale.order", string="Last Sale Order", readonly=True)
    last_order_date = fields.Date(string="Last Order Date", readonly=True)
    days_since_last_order = fields.Integer(string="Days Inactive", readonly=True)
    inactivity_duration = fields.Char(string="Last Purchased", readonly=True)
    order_count = fields.Integer(string="Total Orders", readonly=True)
    total_spent = fields.Float(string="Total Spent", readonly=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )
    inactivity_status = fields.Selection(
        [
            ("active", "Active (< 1 Month)"),
            ("inactive_30", "1–2 Months Inactive"),
            ("inactive_60", "2–3 Months Inactive"),
            ("dormant_90", "3+ Months Inactive"),
            ("never_ordered", "Never Ordered"),
        ],
        string="Inactivity Tier",
        readonly=True,
    )

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW l4e_party_report AS (
                WITH latest_orders AS (
                    SELECT DISTINCT ON (so.partner_id)
                        so.partner_id,
                        so.id AS last_order_id,
                        so.date_order::date AS last_order_date,
                        so.user_id AS last_user_id
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done')
                    ORDER BY so.partner_id, so.date_order DESC, so.id DESC
                ),
                order_stats AS (
                    SELECT 
                        so.partner_id,
                        COUNT(so.id) AS order_count,
                        SUM(so.amount_total) AS total_spent
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done')
                    GROUP BY so.partner_id
                )
                SELECT 
                    p.id AS id,
                    p.id AS partner_id,
                    p.phone AS phone,
                    p.email AS email,
                    p.city AS city,
                    p.state_id AS state_id,
                    COALESCE(p.user_id, lo.last_user_id) AS user_id,
                    p.company_id AS company_id,
                    FALSE AS is_party_order,
                    lo.last_order_id AS last_order_id,
                    lo.last_order_date AS last_order_date,
                    CASE 
                        WHEN lo.last_order_date IS NOT NULL THEN (CURRENT_DATE - lo.last_order_date)::integer
                        ELSE NULL
                    END AS days_since_last_order,
                    CASE
                        WHEN lo.last_order_date IS NULL THEN 'Never Ordered'
                        WHEN (CURRENT_DATE - lo.last_order_date) = 0 THEN 'Today'
                        WHEN (CURRENT_DATE - lo.last_order_date) = 1 THEN 'Yesterday'
                        WHEN (CURRENT_DATE - lo.last_order_date) < 30 THEN CONCAT((CURRENT_DATE - lo.last_order_date), ' days ago')
                        WHEN (CURRENT_DATE - lo.last_order_date) < 60 THEN '1 Month ago'
                        WHEN (CURRENT_DATE - lo.last_order_date) < 90 THEN '2 Months ago'
                        WHEN (CURRENT_DATE - lo.last_order_date) < 180 THEN '3–5 Months ago'
                        WHEN (CURRENT_DATE - lo.last_order_date) < 365 THEN '6–11 Months ago'
                        ELSE '1+ Year ago'
                    END AS inactivity_duration,
                    COALESCE(os.order_count, 0) AS order_count,
                    COALESCE(os.total_spent, 0.0) AS total_spent,
                    CASE
                        WHEN lo.last_order_date IS NULL THEN 'never_ordered'
                        WHEN (CURRENT_DATE - lo.last_order_date) <= 30 THEN 'active'
                        WHEN (CURRENT_DATE - lo.last_order_date) <= 60 THEN 'inactive_30'
                        WHEN (CURRENT_DATE - lo.last_order_date) <= 90 THEN 'inactive_60'
                        ELSE 'dormant_90'
                    END AS inactivity_status
                FROM res_partner p
                LEFT JOIN latest_orders lo ON lo.partner_id = p.id
                LEFT JOIN order_stats os ON os.partner_id = p.id
                WHERE p.active = TRUE 
                  AND (lo.last_order_id IS NOT NULL OR p.customer_rank > 0 OR p.is_company = TRUE OR p.parent_id IS NULL)
            )
        """)

    def action_view_partner(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.partner_id.name,
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_create_quotation(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Quotation"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_user_id": self.user_id.id or self.env.uid,
            },
        }
