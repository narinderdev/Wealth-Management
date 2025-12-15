from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from management.models import (
    BorrowerReport,
    CollateralLimitsRow,
    CollateralOverviewRow,
)
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
)


def _borrower_context(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    return {
        "borrower": borrower,
        "borrower_summary": _build_borrower_summary(borrower),
    }


@login_required(login_url="login")
def limits_view(request):
    context = _borrower_context(request)
    context["active_tab"] = "limits"
    borrower = context.get("borrower")
    latest_report = (
        BorrowerReport.objects.filter(borrower=borrower).order_by("-report_date").first()
        if borrower
        else None
    )
    limits = []
    if latest_report:
        for row in CollateralLimitsRow.objects.filter(report=latest_report).order_by("id"):
            limits.append({
                "division": row.division or "—",
                "collateral_type": row.collateral_type or "—",
                "collateral_sub_type": row.collateral_sub_type or "—",
                "usd_limit": _format_currency(row.usd_limit),
                "pct_limit": _format_pct(row.pct_limit),
            })
        ineligibles = []
        for row in CollateralOverviewRow.objects.filter(report=latest_report):
            if not row.ineligibles:
                continue
            ineligibles.append({
                "division": getattr(row, "division", None) or row.main_type or "—",
                "collateral_type": row.main_type or "—",
                "collateral_sub_type": row.sub_type or "—",
            })
    else:
        ineligibles = []
    context["limit_rows"] = limits
    context["ineligible_rows"] = ineligibles
    return render(request, "limits/limits.html", context)
