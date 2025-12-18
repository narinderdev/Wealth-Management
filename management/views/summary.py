import math

from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

from django.db.models import Max, Q

from management.models import (
    ARMetricsRow,
    Borrower,
    CollateralLimitsRow,
    CollateralOverviewRow,
    Company,
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


def _format_datetime(value):
    if not value:
        return "—"
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime("%Y-%m-%d %H:%M:%S")


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


def get_preferred_borrower(request):
    borrower_id = request.session.get("selected_borrower_id")
    if borrower_id:
        borrower = Borrower.objects.filter(pk=borrower_id).first()
        if borrower:
            return borrower
    borrower_profile = getattr(request.user, "borrower_profile", None)
    return borrower_profile.borrower if borrower_profile else None


def get_active_company(request):
    company_id = request.session.get("company_id")
    if not company_id:
        return None
    company = Company.objects.filter(pk=company_id).first()
    if not company:
        request.session.pop("company_id", None)
        return None
    return company


def _user_can_access_borrower(user, borrower, company):
    if not borrower:
        return False
    if company:
        return borrower.company_id == company.id
    borrower_profile = getattr(user, "borrower_profile", None)
    if borrower_profile and borrower_profile.borrower_id:
        return borrower.pk == borrower_profile.borrower_id
    return user.is_staff or user.is_superuser


CHART_X_POSITIONS = [0, 40, 80, 120, 160, 200, 220]


def _build_line_series(base_value, global_max, x_positions=CHART_X_POSITIONS):
    base = float(_to_decimal(base_value))
    reference = _to_decimal(global_max or Decimal("1"))
    if reference <= 0:
        reference = Decimal("1")
    ref_float = float(reference)
    if ref_float == 0:
        ref_float = 1.0
    base_ratio = max(0.0, min(1.0, base / ref_float))

    points = []
    points_list = []
    total_steps = max(1, len(x_positions) - 1)
    for idx, x in enumerate(x_positions):
        jitter = math.sin(idx / total_steps * math.pi) * 0.12
        ratio = max(0.0, min(1.0, base_ratio + jitter))
        y = 90 - ratio * 50
        y_rounded = round(y, 1)
        points.append(f"{x},{y_rounded}")
        points_list.append({"x": x, "y": y_rounded})

    return {
        "points": " ".join(points),
        "points_list": points_list,
    }


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


def _build_company_summary(company):
    if not company:
        return None
    website = company.website if company else None
    if website and not website.startswith(("http://", "https://")):
        website_url = f"https://{website.lstrip('/')}"
    else:
        website_url = website
    return {
        "name": _safe_str(company.company if company else None),
        "company_id": _safe_str(company.company_id if company else None),
        "industry": _safe_str(company.industry if company else None),
        "primary_naics": _safe_str(company.primary_naics if company else None),
        "website": _safe_str(website),
        "website_url": website_url,
    }


def _build_limit_map(limit_rows):
    limit_map = {}
    for row in limit_rows:
        key = (row.collateral_type or "").strip().lower()
        if not key:
            continue
        limit_map.setdefault(key, []).append(row)
    return limit_map


def _collateral_row_payload(row, limit_map=None):
    return {
        "label": _safe_str(row.main_type),
        "detail": row.sub_type or "",
        "beginning_collateral": _format_currency(row.beginning_collateral),
        "ineligibles": _format_currency(row.ineligibles),
        "eligible_collateral": _format_currency(row.eligible_collateral),
        "nolv_pct": _format_pct(row.nolv_pct),
        "dilution_rate": _format_pct(row.dilution_rate),
        "advanced_rate": _format_pct(row.advanced_rate),
        "rate_limit": _format_pct(
            _resolve_rate_limit(row, limit_map) or row.rate_limit
        ),
        "utilized_rate": _format_pct(row.utilized_rate),
        "pre_reserve_collateral": _format_currency(row.pre_reserve_collateral),
        "reserves": _format_currency(row.reserves),
        "net_collateral": _format_currency(row.net_collateral),
    }


def _resolve_rate_limit(row, limit_map):
    if not limit_map:
        return None
    candidates = []
    if row.main_type:
        candidates.append(row.main_type.strip().lower())
    if row.sub_type:
        candidates.append(row.sub_type.strip().lower())
    for key in candidates:
        entries = limit_map.get(key)
        if entries:
            entry = entries[0]
            return entry.pct_limit
    return None


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
    company = get_active_company(request)
    selected_id = request.GET.get("select")
    if selected_id:
        selected_borrower = Borrower.objects.filter(pk=selected_id).first()
        if _user_can_access_borrower(request.user, selected_borrower, company):
            request.session["selected_borrower_id"] = selected_borrower.id
            request.session.modified = True
        return redirect("dashboard")

    borrower = get_preferred_borrower(request)
    if not borrower:
        return redirect("borrower_portfolio")

    borrower_summary = _build_borrower_summary(borrower)

    latest_collateral_time = (
        CollateralOverviewRow.objects.filter(borrower=borrower)
        .aggregate(time=Max("created_at"))["time"]
    )
    collateral_rows = (
        list(
            CollateralOverviewRow.objects.filter(
                borrower=borrower,
                created_at=latest_collateral_time,
            )
        )
        if latest_collateral_time
        else []
    )
    limit_rows = list(CollateralLimitsRow.objects.filter(borrower=borrower))
    limit_map = _build_limit_map(limit_rows)
    net_total = sum((_to_decimal(row.net_collateral) for row in collateral_rows), Decimal("0"))
    eligible_total = sum((_to_decimal(row.eligible_collateral) for row in collateral_rows), Decimal("0"))
    ineligibles_total = sum((_to_decimal(row.ineligibles) for row in collateral_rows), Decimal("0"))

    ar_row = (
        ARMetricsRow.objects.filter(borrower=borrower)
        .order_by("-as_of_date", "-created_at")
        .first()
    )

    collateral_data = [
        _collateral_row_payload(row, limit_map=limit_map) for row in collateral_rows
    ]

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

    global_max_value = max(
        net_total,
        available_total,
        ar_row.balance if ar_row and ar_row.balance is not None else Decimal("0"),
        Decimal("1"),
    )
    net_chart = _build_line_series(net_total, global_max_value)
    outstanding_chart = _build_line_series(
        ar_row.balance if ar_row and ar_row.balance is not None else None,
        global_max_value,
    )
    availability_chart = _build_line_series(available_total, global_max_value)

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
        "active_tab": "summary",
        "net_chart": net_chart,
        "outstanding_chart": outstanding_chart,
        "availability_chart": availability_chart,
    }
    return render(request, "dashboard/summary.html", context)


@login_required(login_url="login")
def borrower_portfolio_view(request):
    company = get_active_company(request)
    borrower_profile = getattr(request.user, "borrower_profile", None)
    selected_id = request.GET.get("select")
    if selected_id:
        selected_borrower = Borrower.objects.filter(pk=selected_id).first()
        if _user_can_access_borrower(request.user, selected_borrower, company):
            request.session["selected_borrower_id"] = selected_borrower.id
            request.session.modified = True
        return redirect("dashboard")

    search_term = request.GET.get("q", "").strip()
    borrowers_qs = Borrower.objects.select_related("company").order_by("id")
    if company:
        borrowers_qs = borrowers_qs.filter(company=company)
    elif borrower_profile and borrower_profile.borrower_id:
        borrowers_qs = borrowers_qs.filter(pk=borrower_profile.borrower_id)
    if search_term:
        borrowers_qs = borrowers_qs.filter(
            Q(company__company__icontains=search_term)
            | Q(primary_contact__icontains=search_term)
            | Q(primary_contact_email__icontains=search_term)
        )

    borrower_rows = []
    for borrower in borrowers_qs:
        latest_collateral_time = (
            CollateralOverviewRow.objects.filter(borrower=borrower)
            .aggregate(time=Max("created_at"))["time"]
        )
        collateral_rows = (
            list(
                CollateralOverviewRow.objects.filter(
                    borrower=borrower,
                    created_at=latest_collateral_time,
                )
            )
            if latest_collateral_time
            else []
        )
        net_total = sum((_to_decimal(row.net_collateral) for row in collateral_rows), Decimal("0"))
        eligible_total = sum((_to_decimal(row.eligible_collateral) for row in collateral_rows), Decimal("0"))
        ineligibles_total = sum((_to_decimal(row.ineligibles) for row in collateral_rows), Decimal("0"))
        available_total = eligible_total - ineligibles_total
        if available_total < Decimal("0"):
            available_total = Decimal("0")
        ar_row = (
            ARMetricsRow.objects.filter(borrower=borrower)
            .order_by("-as_of_date", "-created_at")
            .first()
        )
        availability_pct = (available_total / net_total) if net_total else None
        last_updated_dt = (
            latest_collateral_time
            or (ar_row.as_of_date if ar_row and getattr(ar_row, "as_of_date", None) else None)
            or borrower.updated_at
        )
        borrower_rows.append(
            {
                "id": borrower.id,
                "borrower_label": borrower.primary_contact or borrower.company.company or "Borrower",
                "company_name": borrower.company.company if borrower.company else "—",
                "contact_name": _safe_str(borrower.primary_contact),
                "contact_phone": borrower.primary_contact_phone,
                "contact_email": borrower.primary_contact_email,
                "update_interval": borrower.update_interval or "—",
                "updated_at": _format_datetime(borrower.updated_at),
                "last_updated": last_updated_dt.strftime("%Y-%m-%d") if last_updated_dt else "-",
                "net_collateral": _format_currency(net_total),
                "outstanding_balance": _format_currency(ar_row.balance if ar_row else None),
                "availability": _format_currency(available_total),
                "availability_pct": _format_pct(availability_pct),
            }
        )

    current_borrower = get_preferred_borrower(request)
    company_for_summary = company or (current_borrower.company if current_borrower else None)
    company_summary = _build_company_summary(company_for_summary) if company_for_summary else None

    context = {
        "borrowers": borrower_rows,
        "selected_borrower_id": str(request.session.get("selected_borrower_id", "")),
        "search_term": search_term,
        "active_tab": "portfolio",
        "company_summary": company_summary,
        "is_company_context": bool(company),
    }
    return render(request, "dashboard/borrower_portfolio.html", context)
