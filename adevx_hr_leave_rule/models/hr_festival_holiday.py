# models/hr_festival_holiday.py
from odoo import api, fields, models


class HrFestivalHoliday(models.Model):
    _name = 'hr.festival.holiday'
    _description = 'Yearly Festival Holidays'
    _order = 'date'

    name = fields.Char(string='Holiday Name', required=True)
    date = fields.Date(string='Date', required=True)
    year = fields.Integer(string='Year', compute='_compute_year', store=True)

    @api.depends('date')
    def _compute_year(self):
        for rec in self:
            rec.year = rec.date.year if rec.date else 0

    def name_get(self):
        return [(rec.id, f"{rec.name} ({rec.date})") for rec in self]
