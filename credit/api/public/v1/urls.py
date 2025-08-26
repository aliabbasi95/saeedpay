from django.urls import path
from .views.credit import (
    CreditLimitListView,
    CreditLimitDetailView,
    StatementListView,
    StatementDetailView,
    StatementLineListView,
    AddPurchaseView,
    AddPaymentView,
    ApplyPenaltyView,
    CloseStatementView,
    RiskScoreView,
)

urlpatterns = [
    path("credit-limits/", CreditLimitListView.as_view(), name="credit_limit_list"),
    path(
        "credit-limits/<int:pk>/",
        CreditLimitDetailView.as_view(),
        name="credit_limit_detail",
    ),
    path("statements/", StatementListView.as_view(), name="statement_list"),
    path("statements/<int:pk>/", StatementDetailView.as_view(), name="statement_detail"),
    path("statement-lines/", StatementLineListView.as_view(), name="statement_line_list"),
    path("add-purchase/", AddPurchaseView.as_view(), name="add_purchase"),
    path("add-payment/", AddPaymentView.as_view(), name="add_payment"),
    path("apply-penalty/", ApplyPenaltyView.as_view(), name="apply_penalty"),
    path("close-statement/", CloseStatementView.as_view(), name="close_statement"),
    path("risk-score/", RiskScoreView.as_view(), name="risk_score"),
]
