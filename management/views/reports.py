import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from management.models import BorrowerReport
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
    return {
        "borrower": borrower,
        "borrower_summary": _build_borrower_summary(borrower),
    }


def _resolve_report_path(report):
    if not report.source_file:
        return None
    candidates = []
    source_value = report.source_file
    if os.path.isabs(source_value):
        candidates.append(source_value)
    base_upload = os.path.join(settings.BASE_DIR, "uploads")
    candidates.append(os.path.join(base_upload, os.path.basename(source_value)))
    candidates.append(os.path.join(base_upload, source_value))
    candidates.append(os.path.join(settings.BASE_DIR, source_value))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


@login_required(login_url="login")
def reports_download(request, report_id):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    report = get_object_or_404(BorrowerReport, id=report_id, borrower=borrower)
    file_path = _resolve_report_path(report)
    if not file_path:
        raise Http404("Report file not found")
    file_name = os.path.basename(report.source_file)
    response = FileResponse(
        open(file_path, "rb"),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@login_required(login_url="login")
def reports_view(request):
    requested_report = request.GET.get("report", "borrowing_base")
    if requested_report not in REPORT_SECTIONS:
        requested_report = "borrowing_base"

    context = _borrower_context(request)
    borrower = context.get("borrower")
    borrower_reports = (
        BorrowerReport.objects.filter(borrower=borrower).order_by("-report_date")[:5]
        if borrower
        else []
    )
    report_section = dict(REPORT_SECTIONS[requested_report])
    if requested_report == "borrowing_base":
        company_label = context["borrower_summary"].get("company_name", "Borrower")
        rows = []
        for idx, report in enumerate(borrower_reports):
            label = report.report_date.strftime("%m/%d/%Y") if report.report_date else "Unknown"
            rows.append({
                "name": f"{company_label} – BBC – {label}",
                "highlight": idx == 0,
                "report_date": report.report_date,
                "source_file": report.source_file,
                "download_url": reverse("reports_download", args=[report.id]),
            })
        if not rows:
            rows = [{"name": "No borrower reports uploaded yet", "highlight": False}]
        report_section["rows"] = rows

    context.update({
        "active_tab": "reports",
        "report_menu": REPORT_MENU,
        "active_report": requested_report,
        "report_section": report_section,
    })
    return render(request, "reports/borrowing_base.html", context)
