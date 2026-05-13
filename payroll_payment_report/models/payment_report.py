from odoo import models, api

class PaymentReport(models.AbstractModel):
    _name = 'report.payroll_payment_report.payment_report_template'
    _description = 'Payment Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        date_from = data.get('date_from')
        date_to   = data.get('date_to')
        ptype     = data.get('payment_type')

        # Search confirmed/done payslips in date range
        domain = [
            ('date_from', '>=', date_from),
            ('date_to',   '<=', date_to),
            ('state', 'in', ['done', 'paid']),
        ]
        payslips = self.env['hr.payslip'].search(domain)

        report_lines = []
        for slip in payslips:
            employee   = slip.employee_id
            cash_amt   = employee.cash_amount or 0.0
            bank_amt   = employee.bank_amount or 0.0
            net_wage   = slip.net_wage

            if ptype == 'cash' and cash_amt <= 0:
                continue
            if ptype == 'bank' and bank_amt <= 0:
                continue

            report_lines.append({
                'employee_name' : employee.name,
                'department'    : employee.department_id.name or '',
                'net_wage'      : net_wage,
                'cash_amount'   : cash_amt if ptype in ('cash', 'all') else 0.0,
                'bank_amount'   : bank_amt if ptype in ('bank', 'all') else 0.0,
                'payslip_ref'   : slip.number or '',
            })

        totals = {
            'net_wage'    : sum(l['net_wage']     for l in report_lines),
            'cash_amount' : sum(l['cash_amount']  for l in report_lines),
            'bank_amount' : sum(l['bank_amount']  for l in report_lines),
        }

        return {
            'doc_ids'      : docids,
            'doc_model'    : 'payment.report.wizard',
            'lines'        : report_lines,
            'totals'       : totals,
            'date_from'    : date_from,
            'date_to'      : date_to,
            'payment_type' : ptype,
        }