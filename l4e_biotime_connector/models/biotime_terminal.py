from odoo import models, fields

class BiotimeTerminal(models.Model):
    _name = "biotime.terminal"
    _description = "Biotime Terminal"
    _rec_name = "terminal_name"

    biotime_id = fields.Integer(index=True)
    sn = fields.Char()
    ip_address = fields.Char()
    alias = fields.Char()
    terminal_name = fields.Char()
    fw_ver = fields.Char()
    push_ver = fields.Char()
    state = fields.Integer()
    terminal_tz = fields.Integer()
    last_activity = fields.Datetime()
    user_count = fields.Integer()
    fp_count = fields.Integer()
    face_count = fields.Integer()
    palm_count = fields.Integer()
    transaction_count = fields.Integer()
    push_time = fields.Datetime()
    transfer_time = fields.Char()
    transfer_interval = fields.Integer()
    is_attendance = fields.Boolean()
    area_name = fields.Char()
    company_uid = fields.Char()
