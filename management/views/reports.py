import os
from io import BytesIO
from datetime import datetime, timezone

import pandas as pd

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse

from management.models import (
    ARMetricsRow,
    BorrowerOverviewRow,
    CollateralOverviewRow,
)
from management.views.summary import _build_borrower_summary, get_preferred_borrower

REPORT_MENU = [
    {"key": "borrowing_base", "label": "Borrowing Base Report", "icon": "document"},
    {"key": "complete_analysis", "label": "Complete Analysis Report", "icon": "chart"},
    {"key": "cashflow", "label": "Cash Flow Forecast", "icon": "cash"},
]

REPORT_SECTIONS = {
    "borrowing_base": {
        "title": "Borrowing Base Reports",
        "description": "Latest BBC-style snapshots generated from the live borrower data.",
        "rows": [],
    },
    "complete_analysis": {
        "title": "Report Title",
        "rows": [],
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
    borrower = get_preferred_borrower(request)
    return {
        "borrower": borrower,
        "borrower_summary": _build_borrower_summary(borrower),
    }


PREFIX_MAP = {
    "borrowing_base": "BBC",
    "complete_analysis": "CORA Analysis",
    "cashflow": "Cash Flow",
}


def _borrower_report_timestamps(borrower, limit=5):
    timestamps = (
        CollateralOverviewRow.objects.filter(borrower=borrower)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .distinct()
    )
    return list(timestamps[:limit])


def _build_report_rows(report_type, timestamps, company_label):
    prefix = PREFIX_MAP.get(report_type, "Report")
    rows = []
    for idx, ts in enumerate(timestamps):
        label = ts.strftime("%m/%d/%Y %H:%M") if ts else "Unknown"
        rows.append({
            "name": f"{company_label} – {prefix} – {label}",
            "highlight": idx == 0,
            "report_date": ts,
            "download_url": reverse("reports_generate_bbc") if report_type == "borrowing_base" else reverse("reports_download", args=[idx]),
        })
    if not rows:
        rows = [{"name": "No borrower reports available", "highlight": False}]
    return rows


@login_required(login_url="login")
def reports_download(request, report_id):
    borrower = get_preferred_borrower(request)
    if not borrower:
        raise Http404("No borrower selected")
    timestamps = _borrower_report_timestamps(borrower)
    if report_id < 0 or report_id >= len(timestamps):
        raise Http404("Report not found")
    workbook = _build_bbc_workbook(borrower)
    report_date = timestamps[report_id]
    file_name = f"{borrower.company.company if borrower and borrower.company else 'BBC'} - BBC {report_date or 'latest'}.xlsx"
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


def _build_bbc_workbook(borrower):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _write_sheet(
            writer,
            "Borrower Overview",
            BorrowerOverviewRow.objects.filter(company_id=borrower.company.company_id if borrower.company else None),
        )
        _write_sheet(writer, "Collateral Overview", CollateralOverviewRow.objects.filter(borrower=borrower))
        _write_sheet(writer, "AR Metrics", ARMetricsRow.objects.filter(borrower=borrower))
    buffer.seek(0)
    return buffer


@login_required(login_url="login")
def reports_generate_bbc(request):
    borrower = get_preferred_borrower(request)
    if not borrower:
        raise Http404("No BBC report available")
    workbook = _build_bbc_workbook(borrower)
    timestamps = _borrower_report_timestamps(borrower, limit=1)
    latest_timestamp = timestamps[0] if timestamps else None
    file_name = f"{borrower.company.company if borrower and borrower.company else 'BBC'} - BBC {latest_timestamp or 'latest'}.xlsx"
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
    if not borrower:
        borrower_reports = []
    else:
        borrower_reports = _borrower_report_timestamps(borrower)
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
