from odoo import fields, models




class ScheduleLine(models.Model):
    _name = 'attendance_advance.schedule_line'
    _description = 'Work schedule line per day'


    work_schedule_id = fields.Many2one('attendance_advance.work_schedule', ondelete='cascade')
    day = fields.Selection([
    ('0', 'Sunday'),
    ('1', 'Monday'),
    ('2', 'Tuesday'),
    ('3', 'Wednesday'),
    ('4', 'Thursday'),
    ('5', 'Friday'),
    ('6', 'Saturday'),
    ], required=True)
    start_time = fields.Float(string='Start Time (hours)', help='Hour in decimal, e.g. 9.5 for 09:30')
    end_time = fields.Float(string='End Time (hours)')
    min_working_hours = fields.Float(string='Minimum Working Hours', default=0.0)
    normal_working_hours = fields.Float(string='Normal Working Hours', default=8.0)
    pattern_type = fields.Selection([('all', 'All'), ('alternate', 'Alternate'), ('custom', 'Custom')], default='all')
    alternate_pattern = fields.Char(string='Alternate Pattern', help='Custom pattern reference, e.g. "1,3 work;2,4 off"')

