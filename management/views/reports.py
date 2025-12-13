from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from management.views.summary import _build_borrower_summary

REPORT_MENU = [
    {"key": "borrowing_base", "label": "Borrowing Base Report", "icon": "document"},
    {"key": "complete_analysis", "label": "Complete Analysis Report", "icon": "chart"},
    {"key": "cashflow", "label": "Cash Flow Forecast", "icon": "cash"},
]

REPORT_SECTIONS = {
    "borrowing_base": {
        "title": "Borrowing Base Reports",
        "description": "Latest BBC packages generated for BlueRidge Materials Group.",
        "rows": [
            {"name": "BlueRidge Materials Group – BBC – 10/31/2025"},
            {"name": "BlueRidge Materials Group – BBC – 11/07/2025"},
            {"name": "BlueRidge Materials Group – BBC – 11/14/2025"},
        ],
    },
    "complete_analysis": {
        "title": "Report Title",
        "description": "Comprehensive collateral analytics for credit committee review.",
        "rows": [
            {
                "name": "BlueRidge Materials Group – CORA Analysis – 10/31/2025",
                "highlight": True,
            },
            {"name": "BlueRidge Materials Group – CORA Analysis – 11/7/2025"},
            {"name": "BlueRidge Materials Group – CORA Analysis – 11/14/2025"},
        ],
    },
    "cashflow": {
        "title": "Cash Flow Forecast",
        "description": "Projected inflow/outflow summary for the upcoming quarter.",
        "forecast": [
            {"period": "Nov 2025", "inflow": "$4.8M", "outflow": "$3.7M", "net": "$1.1M"},
            {"period": "Dec 2025", "inflow": "$4.4M", "outflow": "$3.5M", "net": "$0.9M"},
            {"period": "Jan 2026", "inflow": "$4.2M", "outflow": "$3.8M", "net": "$0.4M"},
        ],
    },
}


def _borrower_context(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    return {"borrower_summary": _build_borrower_summary(borrower)}


@login_required(login_url="login")
def reports_view(request):
    requested_report = request.GET.get("report", "borrowing_base")
    if requested_report not in REPORT_SECTIONS:
        requested_report = "borrowing_base"

    context = _borrower_context(request)
    context.update({
        "active_tab": "reports",
        "report_menu": REPORT_MENU,
        "active_report": requested_report,
        "report_section": REPORT_SECTIONS[requested_report],
    })
    return render(request, "reports/borrowing_base.html", context)
