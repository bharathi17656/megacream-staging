from odoo import models, fields, api , _

import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance' 

    activity = fields.Char(string="Activity")

    

   
