# apps/accounting/api/dashboard_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounting.dashboard.service import AccountingDashboardService


class AccountingDashboardView(APIView):
    """
    Financial dashboard endpoint.
    """

    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]
    dashboard_service = AccountingDashboardService()

    def get(self, request):
        payload = self.dashboard_service.get_dashboard()

        return Response(
            {
                "currency": payload.currency,
                "kpis": [
                    {
                        "key": item.key,
                        "label": item.label,
                        "value": item.value,
                        "currency": item.currency,
                        "status": item.status,
                    }
                    for item in payload.kpis
                ],
                "monthly_trend": [
                    {
                        "period": row.period,
                        "revenue_total": str(row.revenue_total),
                        "expense_total": str(row.expense_total),
                        "net_result": str(row.net_result),
                    }
                    for row in payload.monthly_trend
                ],
                "fund_balances": [
                    {
                        "fund_code": row.fund_code,
                        "fund_name": row.fund_name,
                        "fund_type": row.fund_type,
                        "revenue_total": str(row.revenue_total),
                        "expense_total": str(row.expense_total),
                        "remaining_balance": str(row.remaining_balance),
                        "total_awarded": str(row.total_awarded),
                    }
                    for row in payload.fund_balances
                ],
                "reconciliation_alerts": [
                    {
                        "bank_account_code": row.bank_account_code,
                        "bank_account_name": row.bank_account_name,
                        "period_start": row.period_start,
                        "period_end": row.period_end,
                        "unreconciled_difference": str(row.unreconciled_difference),
                        "status": row.status,
                    }
                    for row in payload.reconciliation_alerts
                ],
            }
        )