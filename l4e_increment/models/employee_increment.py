from odoo import models, fields, api, _
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeIncrement(models.Model):
    _name = 'hr.employee.increment'
    _description = 'Employee Increment / Decrement'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        ondelete='cascade',
        index=True,
    )

    allowance_type = fields.Selection(
        selection=[
            ('cash_salary', 'Cash Salary'),
            ('bank_salary', 'Bank Salary'),
        ],
        string='Type of Allowance',
        required=True,
    )

    is_increment = fields.Boolean(string='Increment', default=True)

    applicable_date = fields.Date(string='Applicable Date')

    approver_ids = fields.Many2many(
        comodel_name='hr.employee',
        relation='hr_employee_increment_approver_rel',
        column1='increment_id',
        column2='employee_id',
        string='Approvers',
    )

    amount = fields.Monetary(string='Amount', currency_field='currency_id')

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='employee_id.currency_id',
        store=True,
    )

    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('applied', 'Applied'),
        ],
        string='Status',
        default='pending',
        readonly=True,
        tracking=True,
    )

    is_current_user_approver = fields.Boolean(
        string='Is Current User Approver',
        compute='_compute_is_current_user_approver',
    )

    @api.depends('approver_ids')
    def _compute_is_current_user_approver(self):
        for rec in self:
            current_employee = self.env['hr.employee'].search(
                [('user_id', '=', self.env.uid)], limit=1
            )
            rec.is_current_user_approver = current_employee in rec.approver_ids

    def _get_allowance_field(self):
        mapping = {
            'cash_salary': 'cash_amount',
            'bank_salary': 'bank_amount',
        }
        return mapping.get(self.allowance_type)

    def _send_increment_notification(self):
        self.ensure_one()

        recipients = self.approver_ids.filtered('work_email')
        if not recipients:
            _logger.info('Increment record — no approvers with work_email, skipping.')
            return

        employee_name = self.employee_id.name or _('Unknown')
        allowance_label = dict(self._fields['allowance_type'].selection).get(self.allowance_type, '')
        inc_dec = _('Increment') if self.is_increment else _('Decrement')
        amount_str = str(self.amount)
        date_str = self.applicable_date.strftime('%d %B %Y') if self.applicable_date else _('N/A')

        subject = _('\u2709 Approval Required: %s %s for %s', inc_dec, allowance_label, employee_name)

        body_html = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9; border-radius: 8px;">
  <div style="background-color: #3949ab; padding: 20px 24px; border-radius: 6px 6px 0 0; text-align: center;">
    <h1 style="color: #ffffff; margin: 0; font-size: 22px;">&#x2709; Approval Required</h1>
  </div>
  <div style="background-color: #ffffff; padding: 28px 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 6px 6px;">
    <p style="font-size: 15px; color: #333333; margin-top: 0;">Hello,</p>
    <p style="font-size: 15px; color: #333333;">
      A new <strong>%(inc_dec)s</strong> request has been created and requires your approval.
    </p>
    <table style="width: 100%%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
      <tr style="background-color: #f2f2f2;">
        <td style="padding: 10px 14px; font-weight: bold; color: #555; width: 40%%; border: 1px solid #ddd;">Employee</td>
        <td style="padding: 10px 14px; color: #222; border: 1px solid #ddd;">%(employee)s</td>
      </tr>
      <tr>
        <td style="padding: 10px 14px; font-weight: bold; color: #555; border: 1px solid #ddd;">Type</td>
        <td style="padding: 10px 14px; color: #222; border: 1px solid #ddd;">%(inc_dec)s</td>
      </tr>
      <tr style="background-color: #f2f2f2;">
        <td style="padding: 10px 14px; font-weight: bold; color: #555; border: 1px solid #ddd;">Allowance Type</td>
        <td style="padding: 10px 14px; color: #222; border: 1px solid #ddd;">%(allowance)s</td>
      </tr>
      <tr>
        <td style="padding: 10px 14px; font-weight: bold; color: #555; border: 1px solid #ddd;">Amount</td>
        <td style="padding: 10px 14px; color: #222; font-weight: bold; border: 1px solid #ddd;">%(amount)s</td>
      </tr>
      <tr style="background-color: #f2f2f2;">
        <td style="padding: 10px 14px; font-weight: bold; color: #555; border: 1px solid #ddd;">Applicable Date</td>
        <td style="padding: 10px 14px; color: #222; border: 1px solid #ddd;">%(date)s</td>
      </tr>
    </table>
    <p style="font-size: 13px; color: #888; margin-top: 28px; border-top: 1px solid #eee; padding-top: 14px;">
      Please log in to the HR system to review and approve this request.
    </p>
  </div>
</div>
""" % {
            'inc_dec': inc_dec,
            'employee': employee_name,
            'allowance': allowance_label,
            'amount': amount_str,
            'date': date_str,
        }

        for approver in recipients:
            try:
                self.env['mail.mail'].sudo().create({
                    'subject': subject,
                    'body_html': body_html,
                    'email_to': approver.work_email,
                }).sudo().send()
                _logger.info('Increment approval email sent to %s.', approver.work_email)
            except Exception as e:
                _logger.error('Failed to send increment email to %s: %s', approver.work_email, e)

        partner_ids = (
            self.approver_ids
            .filtered(lambda e: e.user_id and e.user_id.partner_id)
            .mapped('user_id.partner_id.id')
        )

        if partner_ids:
            internal_body = Markup(
                "<p><strong>Approval Required — %(inc_dec)s Request</strong></p>"
                "<ul>"
                "<li><b>Employee:</b> %(employee)s</li>"
                "<li><b>Allowance Type:</b> %(allowance)s</li>"
                "<li><b>Amount:</b> %(amount)s</li>"
                "<li><b>Applicable Date:</b> %(date)s</li>"
                "</ul>"
                "<p>Please log in to review and approve.</p>"
            ) % {
                'inc_dec': inc_dec,
                'employee': employee_name,
                'allowance': allowance_label,
                'amount': amount_str,
                'date': date_str,
            }
            try:
                self.message_notify(
                    subject=subject,
                    body=internal_body,
                    partner_ids=partner_ids,
                )
                _logger.info(
                    'Internal notification sent for increment to partner ids %s.', partner_ids
                )
            except Exception as e:
                _logger.error('Failed to send internal notification for increment: %s', e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._send_increment_notification()
        return records

    def action_approve(self):
        for rec in self:
            current_employee = self.env['hr.employee'].search(
                [('user_id', '=', self.env.uid)], limit=1
            )
            if current_employee not in rec.approver_ids:
                continue
            if rec.status in ('approved', 'applied'):
                continue
            if not rec._get_allowance_field() or not rec.employee_id:
                continue
            rec.status = 'approved'

    def _apply_increment(self):
        self.ensure_one()
        field_name = self._get_allowance_field()
        if not field_name or not self.employee_id:
            return
        employee = self.employee_id
        current_value = getattr(employee, field_name) or 0.0
        current_wage = employee.wage or 0.0
        if self.is_increment:
            new_value = current_value + self.amount
            new_wage = current_wage + self.amount
        else:
            new_value = max(current_value - self.amount, 0.0)
            new_wage = max(current_wage - self.amount, 0.0)
        employee.sudo().with_context(skip_allowance_check=True).write({
            'wage': new_wage,
            field_name: new_value,
        })
        self.status = 'applied'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model_create_multi
    def create(self, vals_list):
        payslips = super().create(vals_list)
        for payslip in payslips:
            if not payslip.employee_id or not payslip.date_from or not payslip.date_to:
                continue
            due_increments = self.env['hr.employee.increment'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('status', '=', 'approved'),
                ('applicable_date', '>=', payslip.date_from),
                ('applicable_date', '<=', payslip.date_to),
            ])
            for rec in due_increments:
                rec._apply_increment()
        return payslips