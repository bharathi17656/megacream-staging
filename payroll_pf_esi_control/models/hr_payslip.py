# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        res = super(HrPayslip, self).compute_sheet()

        for payslip in self:
            employee = payslip.employee_id
            if not employee:
                continue

            original_pf = payslip.pf_deduction or 0.0
            original_esi = payslip.esi_deduction or 0.0

            pf_deduction = original_pf if employee.pf_eligible else 0.0
            esi_deduction = original_esi if employee.esi_eligible else 0.0

            # The base module deducts PF/ESI from bank payable. Rebuild the
            # bank payable before deduction, then subtract only enabled items.
            bank_before_pf_esi = round(
                (payslip.bank_payable or 0.0) + original_pf + original_esi,
                2,
            )
            final_pf = round(pf_deduction, 2)
            final_esi = round(esi_deduction, 2)
            final_bank = round(bank_before_pf_esi - final_pf - final_esi, 2)
            final_cash = round(payslip.cash_payable or 0.0, 2)
            final_net = round(final_bank + final_cash, 2)

            payslip.write({
                'pf_deduction': final_pf,
                'esi_deduction': final_esi,
                'bank_payable': final_bank,
                'cash_payable': final_cash,
                'net_payable': final_net,
                'paid_amount': final_net,
            })

            payslip._sync_pf_esi_salary_lines()

            _logger.debug(
                "Payslip %s PF/ESI toggle applied: PF=%s ESI=%s Bank=%s Cash=%s Net=%s",
                payslip.id,
                payslip.pf_deduction,
                payslip.esi_deduction,
                payslip.bank_payable,
                payslip.cash_payable,
                payslip.net_payable,
            )

        return res

    def _sync_pf_esi_salary_lines(self):
        line_amounts = {
            'PF': self.pf_deduction,
            'PF_DED': self.pf_deduction,
            'ESI': self.esi_deduction,
            'BANK': self.bank_payable,
            'CASH': self.cash_payable,
            'NET': self.net_payable,
        }
        line_names = {
            'PF': self.pf_deduction,
            'ESI': self.esi_deduction,
            'BANK': self.bank_payable,
            'CASH': self.cash_payable,
            'NET SALARY': self.net_payable,
        }

        for line in self.line_ids:
            code = (line.code or '').upper()
            name = (line.name or '').upper()
            amount = line_amounts.get(code)
            if amount is None:
                amount = line_names.get(name)
            if amount is None:
                continue
            line.amount = round(amount or 0.0, 2)
            line.total = round(amount or 0.0, 2)
