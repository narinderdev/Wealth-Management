import os
from io import BytesIO
from datetime import datetime, timezone

import pandas as pd

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from management.models import (
    ARMetricsRow,
    BorrowerOverviewRow,
    BorrowerReport,
    CollateralOverviewRow,
)
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
        "title": "Report title",
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


PREFIX_MAP = {
    "borrowing_base": "BBC",
    "complete_analysis": "CORA Analysis",
    "cashflow": "Cash Flow",
}


def _build_report_rows(report_type, borrower_reports, company_label):
    prefix = PREFIX_MAP.get(report_type, "Report")
    rows = []
    for idx, report in enumerate(borrower_reports):
        label = report.report_date.strftime("%m/%d/%Y") if report.report_date else "Unknown"
        rows.append({
            "name": f"{company_label} – {prefix} – {label}",
            "highlight": idx == 0,
            "report_date": report.report_date,
            "download_url": reverse("reports_generate_bbc") if report_type == "borrowing_base" else reverse("reports_download", args=[report.id]),
        })
    if not rows:
        rows = [{"name": "No borrower reports uploaded yet", "highlight": False}]
    return rows


@login_required(login_url="login")
def reports_download(request, report_id):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    report = get_object_or_404(BorrowerReport, id=report_id, borrower=borrower)
    workbook = _build_bbc_workbook(report)
    file_name = f"{borrower.company.company if borrower and borrower.company else 'BBC'} - BBC {report.report_date or 'latest'}.xlsx"
    response = FileResponse(
        workbook,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


def _write_sheet(writer, name, queryset):
    df = pd.DataFrame(list(queryset.values()))
    if df.empty:
        df = pd.DataFrame([{"info": "no data"}])
    sheet_name = name[:31]
    df = df.applymap(_ensure_naive)
    df.to_excel(writer, sheet_name=sheet_name, index=False)


def _ensure_naive(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _build_bbc_workbook(report):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _write_sheet(writer, "Borrower Overview", BorrowerOverviewRow.objects.filter(report=report))
        _write_sheet(writer, "Collateral Overview", CollateralOverviewRow.objects.filter(report=report))
        _write_sheet(writer, "AR Metrics", ARMetricsRow.objects.filter(report=report))
    buffer.seek(0)
    return buffer


@login_required(login_url="login")
def reports_generate_bbc(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    report = (
        BorrowerReport.objects.filter(borrower=borrower).order_by("-report_date").first()
        if borrower
        else None
    )
    if not borrower or not report:
        raise Http404("No BBC report available")
    workbook = _build_bbc_workbook(report)
    file_name = f"{borrower.company.company if borrower and borrower.company else 'BBC'} - BBC {report.report_date or 'latest'}.xlsx"
    response = FileResponse(
        workbook,
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
    report_section["rows"] = _build_report_rows(
        requested_report,
        borrower_reports,
        context["borrower_summary"].get("company_name", "Borrower"),
    )

    context.update({
        "active_tab": "reports",
        "report_menu": REPORT_MENU,
        "active_report": requested_report,
        "report_section": report_section,
    })
    return render(request, "reports/borrowing_base.html", context)
