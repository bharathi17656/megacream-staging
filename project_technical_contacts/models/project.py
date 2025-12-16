from odoo import models, fields

class ProjectProject(models.Model):
    _inherit = 'project.project'

    show_field = fields.Integer(default=0)
    contact_1 = fields.Char("Contact 1")
    contact_2 = fields.Char("Contact 2")
    contact_3 = fields.Char("Contact 3")
    contact_4 = fields.Char("Contact 4")
    contact_5 = fields.Char("Contact 5")
    contact_6 = fields.Char("Contact 6")
    contact_7 = fields.Char("Contact 7")
    contact_8 = fields.Char("Contact 8")
    contact_9 = fields.Char("Contact 9")
    contact_10 = fields.Char("Contact 10")

    def action_add_contact_field(self):
        for rec in self:
            if rec.show_field < 10:
                rec.show_field += 1

    def action_remove_contact_field(self):
        for rec in self:
            if rec.show_field > 0:
                last_field = f"contact_{rec.show_field}"
                rec[last_field] = False
                rec.show_field -= 1
