# import io
# import xlsxwriter
# from odoo import http
# from odoo.http import request, content_disposition

# class PaymentReportController(http.Controller):

#     @http.route('/payment/report/xlsx', type='http', auth='user')
#     def download_payment_report(self, wizard_id=None, **kwargs):
#         wizard = request.env['payment.report.wizard'].browse(int(wizard_id))

#         date_from    = wizard.date_from
#         date_to      = wizard.date_to
#         payment_type = wizard.payment_type

#         # Fetch payslips
#         domain = [
#             ('date_from', '>=', date_from),
#             ('date_to',   '<=', date_to),
#             ('state', 'in', ['draft', 'verify', 'done', 'paid']),
#         ]
#         payslips = request.env['hr.payslip'].search(domain)

#         # Build report lines
#         lines = []
#         for slip in payslips:
#             emp      = slip.employee_id
#             # Skip inactive employees
#             if not emp.active:
#                 continue

#             cash_amt = emp.cash_amount or 0.0
#             bank_amt = emp.bank_amount or 0.0

#             if payment_type == 'cash' and cash_amt <= 0:
#                 continue
#             if payment_type == 'bank' and bank_amt <= 0:
#                 continue

#              #Contract start date from hr.employee
#             contract_date = emp.contract_date_start or ''
#             if contract_date:
#                 contract_date = str(contract_date)  # convert date to string

#             lines.append({
#                 'name' : emp.name,
#                 'contract_date' : contract_date,
#                 'cash' : cash_amt if payment_type in ('cash', 'all') else 0.0,
#                 'bank' : bank_amt if payment_type in ('bank', 'all') else 0.0,
#             })

#         # Generate XLSX
#         output    = io.BytesIO()
#         workbook  = xlsxwriter.Workbook(output, {'in_memory': True})
#         worksheet = workbook.add_worksheet('Payment Report')

#         # Formats
#         title_fmt = workbook.add_format({
#             'bold': True, 'font_size': 14,
#             'align': 'center', 'valign': 'vcenter',
#         })
#         header_fmt = workbook.add_format({
#             'bold': True, 'bg_color': '#4B0082',
#             'font_color': 'white', 'border': 1,
#             'align': 'center',
#         })
#         cell_fmt        = workbook.add_format({'border': 1})
#         money_fmt       = workbook.add_format({'border': 1, 'num_format': '0.00'})
#         total_label_fmt = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#E8E8E8'})
#         total_money_fmt = workbook.add_format({'bold': True, 'border': 1, 'num_format': '0.00', 'bg_color': '#E8E8E8'})
#         label_fmt       = workbook.add_format({'bold': True})

#         # Column widths
#         worksheet.set_column(0, 0, 30)  # Employee
#         worksheet.set_column(1, 1, 20)  #Contract Date
#         worksheet.set_column(2, 2, 20)  #Cash Amount
#         worksheet.set_column(3, 3, 20)  #Bank Amount

#         # Row 1 - Title
#         if payment_type == 'all':
#             worksheet.merge_range('A1:D1', 'Payment Report', title_fmt)
#         else:
#             worksheet.merge_range('A1:C1', 'Payment Report', title_fmt)

#         # Row 2 - Period
#         worksheet.write('A2', 'Period :', label_fmt)
#         worksheet.write('B2', '%s  to  %s' % (date_from, date_to))

#         # Row 3 - Filter
#         ptype_label = {'bank': 'Bank Transfer', 'cash': 'Cash Payment', 'all': 'All'}
#         worksheet.write('A3', 'Filter :', label_fmt)
#         worksheet.write('B3', ptype_label.get(payment_type, ''))

#         # Row 5 - Headers
#         worksheet.write(4, 0, 'Employee',     header_fmt)
#         worksheet.write(4, 1, 'Contract Date',  header_fmt)
#         if payment_type == 'all':
#             worksheet.write(4, 2, 'Cash Amount',  header_fmt)
#             worksheet.write(4, 3, 'Bank Amount',  header_fmt)
#         elif payment_type == 'cash':
#             worksheet.write(4, 2, 'Cash Amount',  header_fmt)
#         elif payment_type == 'bank':
#             worksheet.write(4, 2, 'Bank Amount',  header_fmt)

#         # Row 6 onwards - Data
#         row = 5
#         for line in lines:
#             worksheet.write(row, 0, line['name'], cell_fmt)
#             worksheet.write(row, 1, line['contract_date'], cell_fmt)
#             if payment_type == 'all':
#                 worksheet.write(row, 2, line['cash'],  money_fmt)
#                 worksheet.write(row, 3, line['bank'],  money_fmt)
#             elif payment_type == 'cash':
#                 worksheet.write(row, 2, line['cash'],  money_fmt)
#             elif payment_type == 'bank':
#                 worksheet.write(row, 2, line['bank'],  money_fmt)
#             row += 1

#         # Total row
#         worksheet.write(row, 0, 'TOTAL',                       total_label_fmt)
#         worksheet.write(row, 1, '',                            total_label_fmt)
#         if payment_type == 'all':
#             worksheet.write(row, 2, sum(l['cash'] for l in lines), total_money_fmt)
#             worksheet.write(row, 3, sum(l['bank'] for l in lines), total_money_fmt)
#         elif payment_type == 'cash':
#             worksheet.write(row, 2, sum(l['cash'] for l in lines), total_money_fmt)
#         elif payment_type == 'bank':
#             worksheet.write(row, 2, sum(l['bank'] for l in lines), total_money_fmt)

#         workbook.close()
#         output.seek(0)
#         xlsx_data = output.read()

#         filename = 'Payment_Report_%s_%s.xlsx' % (date_from, date_to)
#         return request.make_response(
#             xlsx_data,
#             headers=[
#                 ('Content-Type',
#                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
#                 ('Content-Disposition', content_disposition(filename)),
#             ]
#         )






###############3---------------------------------------------
import io
import xlsxwriter
from calendar import monthrange
from odoo import http
from odoo.http import request, content_disposition


class PaymentReportController(http.Controller):

    @http.route('/payment/report/xlsx', type='http', auth='user')
    def download_payment_report(self, wizard_id=None, **kwargs):
        wizard       = request.env['payment.report.wizard'].browse(int(wizard_id))
        date_from    = wizard.date_from
        date_to      = wizard.date_to
        payment_type = wizard.payment_type

        # Fetch payslips in date range
        domain = [
            ('date_from', '>=', date_from),
            ('date_to',   '<=', date_to),
            ('state', 'in', ['draft', 'verify', 'done', 'paid']),
        ]
        payslips = request.env['hr.payslip'].search(domain)

        # Helper: get worked days by code
        def get_worked_days(slip, code):
            for wd in slip.worked_days_line_ids:
                if wd.code == code:
                    return wd.number_of_days
            return 0.0

        # Helper: get payslip line total by code
        def get_line_total(slip, code):
            for line in slip.line_ids:
                if line.code == code:
                    return line.total
            return 0.0

        # Build report lines
        cash_lines = []
        bank_lines = []

        for slip in payslips:
            emp = slip.employee_id

            # Skip inactive employees
            if not emp.active:
                continue

            gross   = emp.wage or 0.0
            days    = slip.total_days_in_month or monthrange(slip.date_from.year, slip.date_from.month)[1]
            per_day = round(gross / 31, 2) if days else 0.0

            ab      = get_worked_days(slip, 'LOP')
            adj     = get_worked_days(slip, 'PAIDLEAVE')
            work100 = get_worked_days(slip, 'WORK100')
            sunday  = get_worked_days(slip, 'SUNDAY')
            present = work100 + sunday

            cash_amt = get_line_total(slip, 'cash')
            bank_amt = get_line_total(slip, 'bank')
            esic     = get_line_total(slip, 'ESI')
            epfo     = get_line_total(slip, 'PF_DED')
            net      = get_line_total(slip, 'NET')

            # sunday_work_amt = round(sunday * per_day, 2)
            # Get employee working hours calendar name
            calendar_name = emp.resource_calendar_id.name or ''

            # Double pay for Group 2 and Group 3 (7-Day = Double Pay)
            if 'Group 2' in calendar_name or 'Group 3' in calendar_name:
                sunday_multiplier = 2
            else:
                sunday_multiplier = 1

            sunday_work_amt = round(sunday * per_day * sunday_multiplier, 2)
            esic_epfo_total = round(esic + epfo, 2)

            base = {
                'name'       : emp.name,
                'gross'      : gross,
                'days'       : days,
                'per_day'    : per_day,
                'ab'         : ab,
                'adj'        : adj,
                'present'    : present,
                'sunday_amt' : sunday_work_amt,
                'esic'       : esic,
                'epfo'       : epfo,
                'esic_epfo'  : esic_epfo_total,
                'net'        : net,
            }

            if payment_type in ('cash', 'all') and cash_amt > 0:
                cash_lines.append({**base, 'amt': cash_amt})

            if payment_type in ('bank', 'all') and bank_amt > 0:
                bank_lines.append({**base, 'amt': bank_amt})

        # ── XLSX generation ───────────────────────────────────────────
        output   = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # ── Shared Formats ────────────────────────────────────────────
        company_fmt = workbook.add_format({
            'bold': True, 'font_size': 13,
            'align': 'center', 'valign': 'vcenter', 'border': 1,
        })
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 11,
            'align': 'center', 'valign': 'vcenter', 'border': 1,
        })
        header_fmt = workbook.add_format({
            'bold': True, 'border': 1,
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
        })
        sno_fmt         = workbook.add_format({'border': 1, 'align': 'center'})
        cell_fmt        = workbook.add_format({'border': 1})
        num_fmt         = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_label_fmt = workbook.add_format({'bold': True, 'border': 1})
        total_num_fmt   = workbook.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00'})

        # month_label  = date_from.strftime('%B %Y').upper()
        from_label = date_from.strftime('%B %Y').upper()
        to_label   = date_to.strftime('%B %Y').upper()

        if from_label == to_label:
            month_label = from_label  # same month: MARCH 2026
        else:
            month_label = '%s  -  %s' % (from_label, to_label)  # JANUARY 2026  -  MAY 2026
            
        company_name = 'MEGA CREAM AND FOOD CENTRE'

        # ══════════════════════════════════════════════════════════════
        # CASH SHEET
        # ══════════════════════════════════════════════════════════════
        if payment_type in ('cash', 'all'):
            ws = workbook.add_worksheet('Cash Payment')

            ws.set_column(0,  0,  5)
            ws.set_column(1,  1,  22)
            ws.set_column(2,  2,  10)
            ws.set_column(3,  3,  6)
            ws.set_column(4,  4,  10)
            ws.set_column(5,  5,  5)
            ws.set_column(6,  6,  5)
            ws.set_column(7,  7,  8)
            ws.set_column(8,  8,  10)
            ws.set_column(9,  9,  12)
            ws.set_column(10, 10, 10)
            ws.set_column(11, 11, 10)

            # Row 1 - Company name
            ws.merge_range(0, 0, 0, 11, company_name, company_fmt)
            ws.set_row(0, 22)

            # Row 2 - Report title
            ws.merge_range(1, 0, 1, 11, 'CASH SALARY %s' % month_label, title_fmt)
            ws.set_row(1, 18)

            # Row 3 - Headers
            ws.set_row(2, 30)
            for col, h in enumerate(['S NO', 'NAME', 'GROSS', 'DAYS', 'PER DAY',
                                     'AB', 'ADJ', 'PRESENT', 'AMT',
                                     'SALARY\nADVANCE', 'SUNDAY\nWORK', 'NET PAID']):
                ws.write(2, col, h, header_fmt)

            # Data rows
            row = 3
            for i, line in enumerate(cash_lines, start=1):
                ws.write(row, 0,  i,                  sno_fmt)
                ws.write(row, 1,  line['name'],        cell_fmt)
                ws.write(row, 2,  line['gross'],       num_fmt)
                ws.write(row, 3,  line['days'],        sno_fmt)
                ws.write(row, 4,  line['per_day'],     num_fmt)
                ws.write(row, 5,  line['ab'],          sno_fmt)
                ws.write(row, 6,  line['adj'],         sno_fmt)
                ws.write(row, 7,  line['present'],     sno_fmt)
                ws.write(row, 8,  line['amt'],         num_fmt)
                ws.write(row, 9,  '',                  cell_fmt)   # Salary Advance - manual
                ws.write(row, 10, line['sunday_amt'],  num_fmt)
                ws.write(row, 11, line['net'],         num_fmt)
                row += 1

            # Total row
            for col in range(8):
                ws.write(row, col, 'TOTAL' if col == 7 else '', total_label_fmt)
            ws.write(row, 8,  sum(l['amt']        for l in cash_lines), total_num_fmt)
            ws.write(row, 9,  '',                                        total_label_fmt)
            ws.write(row, 10, sum(l['sunday_amt'] for l in cash_lines), total_num_fmt)
            ws.write(row, 11, sum(l['net']        for l in cash_lines), total_num_fmt)

        # ══════════════════════════════════════════════════════════════
        # BANK SHEET
        # ══════════════════════════════════════════════════════════════
        if payment_type in ('bank', 'all'):
            ws2 = workbook.add_worksheet('Bank Transfer')

            ws2.set_column(0,  0,  5)
            ws2.set_column(1,  1,  22)
            ws2.set_column(2,  2,  10)
            ws2.set_column(3,  3,  6)
            ws2.set_column(4,  4,  10)
            ws2.set_column(5,  5,  5)
            ws2.set_column(6,  6,  5)
            ws2.set_column(7,  7,  8)
            ws2.set_column(8,  8,  10)
            ws2.set_column(9,  9,  8)
            ws2.set_column(10, 10, 8)
            ws2.set_column(11, 11, 10)
            ws2.set_column(12, 12, 10)
            ws2.set_column(13, 13, 10)

            # Row 1 - Company name
            ws2.merge_range(0, 0, 0, 13, company_name, company_fmt)
            ws2.set_row(0, 22)

            # Row 2 - Report title
            ws2.merge_range(1, 0, 1, 13, 'BANK SALARY %s' % month_label, title_fmt)
            ws2.set_row(1, 18)

            # Row 3 - Headers
            ws2.set_row(2, 30)
            for col, h in enumerate(['S NO', 'NAME', 'GROSS', 'DAYS', '/DAY',
                                     'AB', 'ADJ', 'PRE', 'AMT',
                                     'ESIC', 'EPFO', 'TOTAL\nDED', 'ADV', 'NET PAID']):
                ws2.write(2, col, h, header_fmt)

            # Data rows
            row2 = 3
            for i, line in enumerate(bank_lines, start=1):
                ws2.write(row2, 0,  i,                 sno_fmt)
                ws2.write(row2, 1,  line['name'],       cell_fmt)
                ws2.write(row2, 2,  line['gross'],      num_fmt)
                ws2.write(row2, 3,  line['days'],       sno_fmt)
                ws2.write(row2, 4,  line['per_day'],    num_fmt)
                ws2.write(row2, 5,  line['ab'],         sno_fmt)
                ws2.write(row2, 6,  line['adj'],        sno_fmt)
                ws2.write(row2, 7,  line['present'],    sno_fmt)
                ws2.write(row2, 8,  line['amt'],        num_fmt)
                ws2.write(row2, 9,  line['esic'],       num_fmt)
                ws2.write(row2, 10, line['epfo'],       num_fmt)
                ws2.write(row2, 11, line['esic_epfo'],  num_fmt)
                ws2.write(row2, 12, '',                 cell_fmt)  # ADV - manual
                ws2.write(row2, 13, line['net'],        num_fmt)
                row2 += 1

            # Total row
            ws2.write(row2, 0,  '',                                          total_label_fmt)
            ws2.write(row2, 1,  '',                                          total_label_fmt)
            ws2.write(row2, 2,  sum(l['gross']     for l in bank_lines),     total_num_fmt)
            ws2.write(row2, 3,  '',                                          total_label_fmt)
            ws2.write(row2, 4,  '',                                          total_label_fmt)
            ws2.write(row2, 5,  '',                                          total_label_fmt)
            ws2.write(row2, 6,  '',                                          total_label_fmt)
            ws2.write(row2, 7,  '',                                          total_label_fmt)
            ws2.write(row2, 8,  sum(l['amt']       for l in bank_lines),     total_num_fmt)
            ws2.write(row2, 9,  sum(l['esic']      for l in bank_lines),     total_num_fmt)
            ws2.write(row2, 10, sum(l['epfo']      for l in bank_lines),     total_num_fmt)
            ws2.write(row2, 11, sum(l['esic_epfo'] for l in bank_lines),     total_num_fmt)
            ws2.write(row2, 12, '',                                          total_label_fmt)
            ws2.write(row2, 13, sum(l['net']       for l in bank_lines),     total_num_fmt)

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