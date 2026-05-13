import io
import xlsxwriter
from odoo import http
from odoo.http import request, content_disposition

class PaymentReportController(http.Controller):

    @http.route('/payment/report/xlsx', type='http', auth='user')
    def download_payment_report(self, wizard_id=None, **kwargs):
        wizard = request.env['payment.report.wizard'].browse(int(wizard_id))

        date_from    = wizard.date_from
        date_to      = wizard.date_to
        payment_type = wizard.payment_type

        # Fetch payslips
        domain = [
            ('date_from', '>=', date_from),
            ('date_to',   '<=', date_to),
            ('state', 'in', ['draft', 'verify', 'done', 'paid']),
        ]
        payslips = request.env['hr.payslip'].search(domain)

        # Build report lines
        lines = []
        for slip in payslips:
            emp      = slip.employee_id
            # Skip inactive employees
            if not emp.active:
                continue

            cash_amt = emp.cash_amount or 0.0
            bank_amt = emp.bank_amount or 0.0

            if payment_type == 'cash' and cash_amt <= 0:
                continue
            if payment_type == 'bank' and bank_amt <= 0:
                continue

             #Contract start date from hr.employee
            contract_date = emp.contract_date_start or ''
            if contract_date:
                contract_date = str(contract_date)  # convert date to string

            lines.append({
                'name' : emp.name,
                'contract_date' : contract_date,
                'cash' : cash_amt if payment_type in ('cash', 'all') else 0.0,
                'bank' : bank_amt if payment_type in ('bank', 'all') else 0.0,
            })

        # Generate XLSX
        output    = io.BytesIO()
        workbook  = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Payment Report')

        # Formats
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14,
            'align': 'center', 'valign': 'vcenter',
        })
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#4B0082',
            'font_color': 'white', 'border': 1,
            'align': 'center',
        })
        cell_fmt        = workbook.add_format({'border': 1})
        money_fmt       = workbook.add_format({'border': 1, 'num_format': '0.00'})
        total_label_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#E8E8E8'})
        total_money_fmt = workbook.add_format({'bold': True, 'border': 1, 'num_format': '0.00', 'bg_color': '#E8E8E8'})
        label_fmt       = workbook.add_format({'bold': True})

        # Column widths
        worksheet.set_column(0, 0, 30)  # Employee
        worksheet.set_column(1, 1, 20)  #Contract Date
        worksheet.set_column(1, 1, 20)  #Cash Amount
        worksheet.set_column(2, 2, 20)  #Bank Amount

        # Row 1 - Title
        worksheet.merge_range('A1:C1', 'Payment Report', title_fmt)

        # Row 2 - Period
        worksheet.write('A2', 'Period :', label_fmt)
        worksheet.write('B2', '%s  to  %s' % (date_from, date_to))

        # Row 3 - Filter
        ptype_label = {'bank': 'Bank Transfer', 'cash': 'Cash Payment', 'all': 'All'}
        worksheet.write('A3', 'Filter :', label_fmt)
        worksheet.write('B3', ptype_label.get(payment_type, ''))

        # Row 5 - Headers
        worksheet.write(4, 0, 'Employee',     header_fmt)
        worksheet.write(4, 1, 'Contract Date',  header_fmt)
        worksheet.write(4, 1, 'Cash Amount',  header_fmt)
        worksheet.write(4, 2, 'Bank Amount',  header_fmt)

        # Row 6 onwards - Data
        row = 5
        for line in lines:
            worksheet.write(row, 0, line['name'], cell_fmt)
            worksheet.write(row, 1, line['contract_date'], cell_fmt)
            worksheet.write(row, 1, line['cash'],  money_fmt)
            worksheet.write(row, 2, line['bank'],  money_fmt)
            row += 1

        # Total row
        worksheet.write(row, 0, 'TOTAL',                       total_label_fmt)
        worksheet.write(row, 1, '',                            total_label_fmt)
        worksheet.write(row, 1, sum(l['cash'] for l in lines), total_money_fmt)
        worksheet.write(row, 2, sum(l['bank'] for l in lines), total_money_fmt)

        workbook.close()
        output.seek(0)
        xlsx_data = output.read()

        filename = 'Payment_Report_%s_%s.xlsx' % (date_from, date_to)
        return request.make_response(
            xlsx_data,
            headers=[
                ('Content-Type',
                 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename)),
            ]
        )