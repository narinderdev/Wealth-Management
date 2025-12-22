from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from management.models import (
    CollateralLimitsRow,
    CollateralOverviewRow,
)
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
    get_preferred_borrower,
)


def _borrower_context(request):
    borrower = get_preferred_borrower(request)
    return {
        "borrower": borrower,
        "borrower_summary": _build_borrower_summary(borrower),
    }


@login_required(login_url="login")
def limits_view(request):
    context = _borrower_context(request)
    context["active_tab"] = "limits"
    borrower = context.get("borrower")
    limits = []
    if borrower:
        for row in CollateralLimitsRow.objects.filter(borrower=borrower).order_by("id"):
            limits.append({
                "division": row.division or "—",
                "collateral_type": row.collateral_type or "—",
                "collateral_sub_type": row.collateral_sub_type or "—",
                "usd_limit": _format_currency(row.usd_limit),
                "pct_limit": _format_pct(row.pct_limit),
            })
        ineligibles = []
        for row in CollateralOverviewRow.objects.filter(borrower=borrower):
            if not row.ineligibles:
                continue
            ineligibles.append({
                "division": getattr(row, "division", None) or row.main_type or "—",
                "collateral_type": row.main_type or "—",
                "collateral_sub_type": row.sub_type or "—",
            })
    else:
        ineligibles = []
    limits_page_number = request.GET.get("limits_page", 1)
    ineligibles_page_number = request.GET.get("ineligibles_page", 1)
    limits_paginator = Paginator(limits, 20)
    ineligibles_paginator = Paginator(ineligibles, 20)
    context["limit_page"] = limits_paginator.get_page(limits_page_number)
    context["ineligible_page"] = ineligibles_paginator.get_page(ineligibles_page_number)
    return render(request, "limits/limits.html", context)
