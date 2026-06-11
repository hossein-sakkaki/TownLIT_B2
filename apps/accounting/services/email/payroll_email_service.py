# apps/accounting/services/email/payroll_email_service.py

from django.conf import settings
from django.utils import timezone

from apps.accounting.models import PayStub
from apps.accounting.services.payroll.paystub_pdf_service import PayStubPDFService
from apps.accounting.services.payroll.vacation_pay_pdf_service import VacationPayPDFService
from apps.accounting.services.payroll.payroll_type_service import is_vacation_pay_stub
from utils.email.email_tools import send_custom_email


class PayrollEmailService:
    """
    Sends payroll-related employee emails.
    """

    def send_pay_stub_approved_email(self, *, pay_stub: PayStub) -> bool:
        """
        Send pay stub or vacation pay statement after approval.
        """

        if pay_stub.pay_stub_emailed_at:
            return True

        if is_vacation_pay_stub(pay_stub=pay_stub):
            return self._send_vacation_pay_approved_email(pay_stub=pay_stub)

        return self._send_salary_pay_stub_approved_email(pay_stub=pay_stub)

    def send_salary_payment_confirmation_email(self, *, pay_stub: PayStub) -> bool:
        """
        Send salary or vacation payment confirmation after payment is posted.
        """

        if pay_stub.payment_confirmation_emailed_at:
            return True

        if is_vacation_pay_stub(pay_stub=pay_stub):
            return self._send_vacation_pay_payment_confirmation_email(pay_stub=pay_stub)

        return self._send_salary_payment_confirmation_email(pay_stub=pay_stub)

    def _send_salary_pay_stub_approved_email(self, *, pay_stub: PayStub) -> bool:
        """
        Send regular salary pay stub email.
        """

        recipient = self._get_employee_email(pay_stub=pay_stub)
        if not recipient:
            return False

        pdf_content = PayStubPDFService().build_pdf(pay_stub=pay_stub)

        subject = f"TownLIT Pay Stub - {pay_stub.pay_run.pay_period.end_date.strftime('%B %Y')}"

        context = self._base_context(pay_stub=pay_stub)
        context.update(
            {
                "email_title": "Your TownLIT pay stub is ready",
                "message_intro": "Your payroll has been approved and your pay stub is attached.",
                "statement_type": "Pay Stub",
            }
        )

        success = send_custom_email(
            to=recipient,
            subject=subject,
            template_path="emails/accounting/pay_stub_approved.html",
            context=context,
            attachments=[
                {
                    "filename": f"pay_stub_{pay_stub.pay_run.run_number}.pdf",
                    "content": pdf_content,
                    "mime_type": "application/pdf",
                }
            ],
        )

        if success:
            self._mark_pay_stub_emailed(pay_stub=pay_stub)

        return success

    def _send_vacation_pay_approved_email(self, *, pay_stub: PayStub) -> bool:
        """
        Send vacation pay statement email.
        """

        recipient = self._get_employee_email(pay_stub=pay_stub)
        if not recipient:
            return False

        pdf_content = VacationPayPDFService().build_pdf(pay_stub=pay_stub)

        subject = f"TownLIT Vacation Pay Statement - {pay_stub.pay_run.pay_period.end_date.strftime('%B %Y')}"

        context = self._base_context(pay_stub=pay_stub)
        context.update(
            {
                "email_title": "Your TownLIT vacation pay statement is ready",
                "message_intro": (
                    "Your vacation pay has been approved and your vacation pay statement is attached. "
                    "This statement shows the gross vacation pay, payroll deductions, and net vacation pay."
                ),
                "statement_type": "Vacation Pay Statement",
                "vacation_pay_paid": pay_stub.vacation_pay_paid,
            }
        )

        success = send_custom_email(
            to=recipient,
            subject=subject,
            template_path="emails/accounting/vacation_pay_approved.html",
            context=context,
            attachments=[
                {
                    "filename": f"vacation_pay_statement_{pay_stub.pay_run.run_number}.pdf",
                    "content": pdf_content,
                    "mime_type": "application/pdf",
                }
            ],
        )

        if success:
            self._mark_pay_stub_emailed(pay_stub=pay_stub)

        return success

    def _send_salary_payment_confirmation_email(self, *, pay_stub: PayStub) -> bool:
        """
        Send regular salary payment confirmation.
        """

        recipient = self._get_employee_email(pay_stub=pay_stub)
        if not recipient:
            return False

        pdf_content = PayStubPDFService().build_pdf(pay_stub=pay_stub)

        subject = f"TownLIT Salary Payment Confirmation - {pay_stub.pay_run.pay_period.end_date.strftime('%B %Y')}"

        context = self._base_context(pay_stub=pay_stub)
        context.update(
            {
                "email_title": "Your TownLIT salary payment has been recorded",
                "message_intro": "This email confirms that your salary payment has been recorded.",
                "statement_type": "Salary Payment Confirmation",
            }
        )

        success = send_custom_email(
            to=recipient,
            subject=subject,
            template_path="emails/accounting/salary_payment_confirmation.html",
            context=context,
            attachments=[
                {
                    "filename": f"pay_stub_{pay_stub.pay_run.run_number}.pdf",
                    "content": pdf_content,
                    "mime_type": "application/pdf",
                }
            ],
        )

        if success:
            self._mark_payment_confirmation_emailed(pay_stub=pay_stub)

        return success

    def _send_vacation_pay_payment_confirmation_email(self, *, pay_stub: PayStub) -> bool:
        """
        Send vacation pay payment confirmation.
        """

        recipient = self._get_employee_email(pay_stub=pay_stub)
        if not recipient:
            return False

        pdf_content = VacationPayPDFService().build_pdf(pay_stub=pay_stub)

        subject = f"TownLIT Vacation Pay Payment Confirmation - {pay_stub.pay_run.pay_period.end_date.strftime('%B %Y')}"

        context = self._base_context(pay_stub=pay_stub)
        context.update(
            {
                "email_title": "Your TownLIT vacation pay payment has been recorded",
                "message_intro": (
                    "This email confirms that your net vacation pay payment has been recorded."
                ),
                "statement_type": "Vacation Pay Payment Confirmation",
                "vacation_pay_paid": pay_stub.vacation_pay_paid,
            }
        )

        success = send_custom_email(
            to=recipient,
            subject=subject,
            template_path="emails/accounting/vacation_pay_payment_confirmation.html",
            context=context,
            attachments=[
                {
                    "filename": f"vacation_pay_statement_{pay_stub.pay_run.run_number}.pdf",
                    "content": pdf_content,
                    "mime_type": "application/pdf",
                }
            ],
        )

        if success:
            self._mark_payment_confirmation_emailed(pay_stub=pay_stub)

        return success

    def _base_context(self, *, pay_stub: PayStub) -> dict:
        """
        Shared payroll email context.
        """

        pay_period = pay_stub.pay_run.pay_period

        return {
            "employee": pay_stub.employee,
            "pay_stub": pay_stub,
            "pay_run": pay_stub.pay_run,
            "pay_period": pay_period,
            "period_start": pay_period.start_date,
            "period_end": pay_period.end_date,
            "pay_date": pay_period.pay_date,
            "gross_salary": pay_stub.gross_salary,
            "vacation_pay_paid": pay_stub.vacation_pay_paid,
            "total_employee_deductions": pay_stub.total_employee_deductions,
            "net_pay": pay_stub.net_pay,
            "actual_paid": pay_stub.actual_paid,
            "net_salary_payable": pay_stub.net_salary_payable,
            "salary_paid_on": pay_stub.salary_paid_on,
            "salary_payment_reference": pay_stub.salary_payment_reference,
            "salary_payment_method": pay_stub.get_salary_payment_method_display()
            if pay_stub.salary_payment_method
            else "",
            "site_domain": getattr(settings, "SITE_URL", ""),
            "logo_base_url": getattr(settings, "EMAIL_LOGO_URL", ""),
            "current_year": timezone.now().year,
        }

    def _get_employee_email(self, *, pay_stub: PayStub) -> str:
        """
        Resolve payroll employee email.
        """

        if pay_stub.employee.email:
            return pay_stub.employee.email

        if pay_stub.employee.user and pay_stub.employee.user.email:
            return pay_stub.employee.user.email

        return ""

    def _mark_pay_stub_emailed(self, *, pay_stub: PayStub) -> None:
        """
        Mark statement email as sent.
        """

        pay_stub.pay_stub_emailed_at = timezone.now()
        pay_stub.save(update_fields=["pay_stub_emailed_at", "updated_at"])

    def _mark_payment_confirmation_emailed(self, *, pay_stub: PayStub) -> None:
        """
        Mark payment confirmation email as sent.
        """

        pay_stub.payment_confirmation_emailed_at = timezone.now()
        pay_stub.save(
            update_fields=[
                "payment_confirmation_emailed_at",
                "updated_at",
            ]
        )