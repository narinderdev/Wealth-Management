from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.text import slugify

from management.models import (
    ARMetricsRow,
    BorrowerReport,
    CollateralOverviewRow,
)


def _format_currency(value):
    if value is None:
        return "—"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        try:
            amount = Decimal(str(value))
        except Exception:
            return "—"
    return f"${amount:,.2f}"


def _format_pct(value):
    if value is None:
        return "—"
    try:
        pct = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        try:
            pct = Decimal(str(value))
        except Exception:
            return "—"

    if pct <= Decimal("1"):
        pct *= Decimal("100")

    return f"{pct:.1f}%"


def _normalize_pct(value):
    if value is None:
        return None
    try:
        pct = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        try:
            pct = Decimal(str(value))
        except Exception:
            return None

    if pct <= Decimal("1"):
        pct *= Decimal("100")

    return pct


def _format_date(value):
    if not value:
        return "—"
    return value.strftime("%m/%d/%Y")


def _safe_str(value, default="—"):
    if value is None or value == "":
        return default
    return str(value)


def _to_decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")


def _build_borrower_summary(borrower):
    if not borrower:
        return {
            "company_name": "—",
            "company_id": "—",
            "industry": "—",
            "primary_naics": "—",
            "website": "—",
            "website_url": None,
            "primary_contact": "—",
            "primary_contact_phone": "—",
            "primary_contact_email": "—",
            "update_interval": "—",
            "current_update": "—",
            "previous_update": "—",
            "next_update": "—",
            "lender": "—",
        }

    company = borrower.company
    website = company.website if company else None
    if website and not website.startswith(("http://", "https://")):
        website_href = f"https://{website.lstrip('/')}"
    else:
        website_href = website
    return {
        "company_name": _safe_str(company.company if company else None),
        "company_id": _safe_str(company.company_id if company else None),
        "industry": _safe_str(company.industry if company else None),
        "primary_naics": _safe_str(company.primary_naics if company else None),
        "website": _safe_str(website),
        "website_url": website_href,
        "primary_contact": _safe_str(borrower.primary_contact),
        "primary_contact_phone": _safe_str(borrower.primary_contact_phone),
        "primary_contact_email": _safe_str(borrower.primary_contact_email),
        "update_interval": _safe_str(borrower.update_interval),
        "current_update": _format_date(borrower.current_update),
        "previous_update": _format_date(borrower.previous_update),
        "next_update": _format_date(borrower.next_update),
        "lender": _safe_str(borrower.lender),
    }


def _collateral_row_payload(row):
    return {
        "label": _safe_str(row.main_type),
        "detail": row.sub_type or "",
        "beginning_collateral": _format_currency(row.beginning_collateral),
        "ineligibles": _format_currency(row.ineligibles),
        "eligible_collateral": _format_currency(row.eligible_collateral),
        "nolv_pct": _format_pct(row.nolv_pct),
        "dilution_rate": _format_pct(row.dilution_rate),
        "advanced_rate": _format_pct(row.advanced_rate),
        "rate_limit": _format_pct(row.rate_limit),
        "utilized_rate": _format_pct(row.utilized_rate),
        "pre_reserve_collateral": _format_currency(row.pre_reserve_collateral),
        "reserves": _format_currency(row.reserves),
        "net_collateral": _format_currency(row.net_collateral),
    }


def _build_collateral_tree(collateral_rows):
    tree = []
    parents = {}

    for row in collateral_rows:
        label = row.get("label") or "collateral"
        detail = (row.get("detail") or "").strip()
        node_id = slugify(label)
        if not detail:
            node = {
                "id": node_id,
                "row": row,
                "children": [],
            }
            parents[label] = node
            tree.append(node)

    for row in collateral_rows:
        label = row.get("label") or "collateral"
        detail = (row.get("detail") or "").strip()
        node_id = slugify(f"{label}-{detail}") if detail else slugify(label)
        if detail:
            parent = parents.get(label)
            if not parent:
                parent = {
                    "id": node_id,
                    "row": row,
                    "children": [],
                }
                parents[label] = parent
                tree.append(parent)
            parent["children"].append({
                "id": node_id,
                "row": row,
            })

    return tree


@login_required(login_url="login")
def summary_view(request):
    borrower = getattr(request.user, "borrower_profile", None)
    borrower = borrower.borrower if borrower else None
    borrower_summary = _build_borrower_summary(borrower)

    latest_report = (
        BorrowerReport.objects.filter(borrower=borrower).order_by("-report_date").first()
        if borrower
        else None
    )
    collateral_rows = (
        list(CollateralOverviewRow.objects.filter(report=latest_report).order_by("id"))
        if latest_report
        else []
    )

    net_total = sum((_to_decimal(row.net_collateral) for row in collateral_rows), Decimal("0"))
    eligible_total = sum((_to_decimal(row.eligible_collateral) for row in collateral_rows), Decimal("0"))
    ineligibles_total = sum((_to_decimal(row.ineligibles) for row in collateral_rows), Decimal("0"))

    ar_row = (
        ARMetricsRow.objects.filter(report=latest_report)
        .order_by("-as_of_date")
        .first()
        if latest_report
        else None
    )

    collateral_data = [_collateral_row_payload(row) for row in collateral_rows]

    available_total = eligible_total - ineligibles_total
    if available_total < Decimal("0"):
        available_total = Decimal("0")

    insights = {
        "net": {
            "amount": _format_currency(net_total),
            "detail": f"Ineligibles { _format_currency(ineligibles_total) } across {len(collateral_rows)} rows",
        },
        "outstanding": {
            "amount": _format_currency(ar_row.balance if ar_row else None),
            "detail": f"As of {ar_row.as_of_date.strftime('%m/%d/%Y')}" if ar_row and ar_row.as_of_date else "Awaiting AR snapshot",
        },
        "availability": {
            "amount": _format_currency(available_total if collateral_rows else None),
            "detail": f"{len(collateral_rows)} collateral entries",
        },
    }

    inventory_rows = [
        row for row in collateral_rows if row.main_type and "inventory" in row.main_type.lower()
    ]
    inventory_eligible = sum((_to_decimal(row.eligible_collateral) for row in inventory_rows), Decimal("0"))
    inventory_ineligible = sum((_to_decimal(row.ineligibles) for row in inventory_rows), Decimal("0"))
    inventory_total_base = inventory_eligible + inventory_ineligible
    inventory_ratio = (inventory_ineligible / inventory_total_base) if inventory_total_base else None
    inventory_ratio_pct = inventory_ratio * Decimal("100") if inventory_ratio is not None else None

    risk_metrics = []
    if ar_row:
        ar_pct = _normalize_pct(ar_row.pct_past_due)
        direction = "down" if ar_pct and ar_pct >= Decimal("5") else "up"
        detail = f"{_format_currency(ar_row.balance)} · {_format_pct(ar_row.pct_past_due)} past due"
    else:
        direction = "up"
        detail = "No AR metrics yet"
    risk_metrics.append({
        "label": "Accounts Receivable",
        "detail": detail,
        "direction": direction,
    })

    if inventory_rows and inventory_ratio is not None:
        direction = "down" if inventory_ratio_pct and inventory_ratio_pct > Decimal("15") else "up"
        detail = f"{_format_currency(inventory_eligible)} eligible · {_format_pct(inventory_ratio)} ineligible"
    else:
        direction = "up"
        detail = "Inventory snapshot pending"
    risk_metrics.append({
        "label": "Inventory",
        "detail": detail,
        "direction": direction,
    })

    if borrower:
        contact_parts = [
            part
            for part in (
                borrower.primary_contact,
                borrower.primary_contact_phone,
                borrower.primary_contact_email,
            )
            if part
        ]
        company_detail = " · ".join(contact_parts) if contact_parts else "Contact info pending"
    else:
        company_detail = "Contact info pending"
    risk_metrics.append({
        "label": "Company",
        "detail": company_detail,
        "direction": "up",
    })

    industry_detail = borrower_summary["industry"]
    if borrower and borrower.company and borrower.company.primary_naics:
        industry_detail = f"{industry_detail} · NAICS {borrower.company.primary_naics}"
    risk_metrics.append({
        "label": "Industry",
        "detail": industry_detail,
        "direction": "up",
    })

    context = {
        "borrower_summary": borrower_summary,
        "collateral_rows": collateral_data,
        "collateral_tree": _build_collateral_tree(collateral_data),
        "insights": insights,
        "risk_metrics": risk_metrics,
        "user": request.user,
    }
    return render(request, "dashboard/summary.html", context)
