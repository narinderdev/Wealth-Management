import math
from collections import OrderedDict, defaultdict
from datetime import timedelta

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.urls import reverse
from django.utils.text import slugify

from django.db.models import Max, Q

from management.models import (
    ARMetricsRow,
    Borrower,
    CollateralLimitsRow,
    CollateralOverviewRow,
    Company,
    CompositeIndexRow,
    RiskSubfactorsRow,
    SnapshotSummaryRow,
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
    return f"${amount:,.0f}"


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


def get_active_borrower_id(request):
    return request.GET.get("borrower_id") or request.session.get("selected_borrower_id")


def get_preferred_borrower(request):
    borrower_id = get_active_borrower_id(request)
    if borrower_id:
        borrower = Borrower.objects.filter(pk=borrower_id).first()
        if borrower:
            return borrower
        request.session.pop("selected_borrower_id", None)
    borrower_profile = getattr(request.user, "borrower_profile", None)
    return borrower_profile.borrower if borrower_profile else None


SNAPSHOT_EMPTY_MESSAGE = "No snapshot summary available."
SNAPSHOT_NO_BORROWER_MESSAGE = "No snapshot summary available."


def get_snapshot_summary_map(
    borrower,
    sections,
    *,
    empty_message=SNAPSHOT_EMPTY_MESSAGE,
    no_borrower_message=SNAPSHOT_NO_BORROWER_MESSAGE,
):
    if not sections:
        return {}
    if not borrower:
        return {section: no_borrower_message for section in sections}
    def _normalize_section(value):
        if not value:
            return ""
        cleaned = []
        for char in str(value).lower():
            if char.isalnum():
                cleaned.append(char)
            else:
                cleaned.append("_")
        normalized = "_".join(part for part in "".join(cleaned).split("_") if part)
        return normalized

    normalized_map = {
        _normalize_section(section): section for section in sections
    }
    summary_map = {}
    summaries = SnapshotSummaryRow.objects.filter(borrower=borrower).order_by("-updated_at", "-id")
    for row in summaries:
        normalized_section = _normalize_section(row.section)
        section_key = normalized_map.get(normalized_section)
        if not section_key or section_key in summary_map:
            continue
        text = (row.summary_text or "").strip()
        summary_map[section_key] = text
    return {
        section: (summary_map.get(section) or empty_message)
        for section in sections
    }


def get_borrower_status_context(request):
    has_borrowers = Borrower.objects.exists()
    borrower = get_preferred_borrower(request)
    if not has_borrowers:
        return {
            "borrower_message": "No borrowers exist yet. Create a borrower to begin.",
            "borrower_action_url": reverse("admin_component", args=["borrowers"]),
            "borrower_action_label": "Create Borrower",
        }
    if not borrower:
        return {
            "borrower_message": "Please select a borrower to view data.",
            "borrower_action_url": reverse("borrower_portfolio"),
            "borrower_action_label": "Select Borrower",
        }
    return {}


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


def _format_axis_value(value):
    val = float(value)
    abs_val = abs(val)
    if abs_val >= 1_000_000_000:
        return f"${val / 1_000_000_000:.0f}B"
    if abs_val >= 1_000_000:
        return f"${val / 1_000_000:.0f}M"
    if abs_val >= 1_000:
        return f"${val / 1_000:.0f}k"
    return f"${val:,.0f}"


def _nice_step(value):
    if value <= 0:
        return 1.0
    exponent = math.floor(math.log10(value))
    magnitude = 10 ** exponent
    fraction = value / magnitude
    if fraction <= 1:
        nice = 1
    elif fraction <= 2:
        nice = 2
    elif fraction <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def _format_chart_label(label, index):
    if label is None:
        return f"{index + 1:02d}"
    text = str(label)
    if text.isdigit() and len(text) == 1:
        return f"0{text}"
    return text


def _normalize_labels(labels, target_len):
    labels = [label for label in labels if label is not None]
    if not labels:
        return [f"{idx + 1:02d}" for idx in range(target_len)]
    labels = [_format_chart_label(label, idx) for idx, label in enumerate(labels)]
    if len(labels) < target_len:
        prefix = [f"{idx + 1:02d}" for idx in range(target_len - len(labels))]
        labels = prefix + labels
    elif len(labels) > target_len:
        labels = labels[-target_len:]
    return labels


def _normalize_series(values, target_len, fallback_value):
    values = [_to_decimal(val) for val in values if val is not None]
    if not values:
        values = [_to_decimal(fallback_value)]
    if len(values) < target_len:
        padding = [values[0]] * (target_len - len(values))
        values = padding + values
    elif len(values) > target_len:
        values = values[-target_len:]
    return values


def _build_line_series(values, labels, series_label=None, width=220, height=140):
    values = [float(_to_decimal(val)) for val in values] if values else [0.0]
    labels = labels or [f"{idx + 1:02d}" for idx in range(len(values))]

    max_value = max(values)
    min_value = min(values)
    if max_value == min_value:
        max_value = max_value if max_value != 0 else 1.0
        min_value = max_value * 0.85 if max_value else 0

    left = 50
    right = 16
    top = 12
    bottom = 12
    tick_count = 5
    value_range = max_value - min_value
    step_value = _nice_step(value_range / max(1, tick_count - 1))
    axis_max = math.ceil(max_value / step_value) * step_value
    axis_min = axis_max - step_value * (tick_count - 1)
    if axis_min > min_value:
        axis_min = math.floor(min_value / step_value) * step_value
        axis_max = axis_min + step_value * (tick_count - 1)
    if axis_min < 0:
        axis_min = 0
        axis_max = axis_min + step_value * (tick_count - 1)

    axis_range = axis_max - axis_min if axis_max != axis_min else 1.0

    plot_width = width - left - right
    plot_height = height - top - bottom
    plot_left = left
    plot_top = top
    baseline_y = plot_top + plot_height
    step_x = plot_width / max(1, len(values) - 1)

    x_positions = []
    x_labels = []
    points = []
    points_list = []
    for idx, val in enumerate(values):
        x = plot_left + idx * step_x
        ratio = (val - axis_min) / axis_range if axis_range else 0
        ratio = max(0.0, min(1.0, ratio))
        y = baseline_y - ratio * plot_height
        x_positions.append(round(x, 1))
        x_labels.append({"x": round(x, 1), "text": labels[idx]})
        points.append(f"{x:.1f},{y:.1f}")
        label = f"{series_label} · {labels[idx]}" if series_label else labels[idx]
        points_list.append(
            {
                "x": round(x, 1),
                "y": round(y, 1),
                "label": label,
                "value": _format_currency(val),
            }
        )

    y_ticks = []
    for idx in range(tick_count):
        ratio = idx / (tick_count - 1)
        value = axis_max - step_value * idx
        y = plot_top + plot_height * ratio
        y_ticks.append({"y": round(y, 1), "label": _format_axis_value(value)})

    return {
        "points": " ".join(points),
        "points_list": points_list,
        "y_ticks": y_ticks,
        "x_labels": x_labels,
        "x_grid": x_positions,
        "grid": {
            "left": round(plot_left, 1),
            "right": round(plot_left + plot_width, 1),
            "top": round(plot_top, 1),
            "bottom": round(baseline_y, 1),
        },
        "label_x": round(plot_left - 45, 1),
        "label_y": round(baseline_y + 8, 1),
    }


def _range_dates(range_key):
    today = timezone.localdate()
    if range_key == "last_12_months":
        return today - timedelta(days=364), today
    if range_key == "last_6_months":
        return today - timedelta(days=182), today
    if range_key == "last_3_months":
        return today - timedelta(days=89), today
    if range_key == "last_1_month":
        return today - timedelta(days=29), today
    return today - timedelta(days=364), today


def _apply_date_filter(qs, field_name, start_date, end_date):
    if start_date and end_date:
        return qs.filter(**{f"{field_name}__range": (start_date, end_date)})
    return qs


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


def _sum_collateral_field(rows, field_name):
    values = [getattr(row, field_name) for row in rows if getattr(row, field_name) is not None]
    if not values:
        return None
    return sum((_to_decimal(value) for value in values), Decimal("0"))


def _weighted_collateral_pct(rows, value_fn, weight_field="eligible_collateral"):
    weighted_sum = Decimal("0")
    total_weight = Decimal("0")
    values = []
    for row in rows:
        raw_value = value_fn(row)
        if raw_value is None:
            continue
        value = _to_decimal(raw_value)
        values.append(value)
        raw_weight = getattr(row, weight_field, None)
        weight = _to_decimal(raw_weight) if raw_weight is not None else Decimal("0")
        weighted_sum += value * weight
        total_weight += weight
    if total_weight > 0:
        return weighted_sum / total_weight
    if values:
        return sum(values) / Decimal(len(values))
    return None


def _build_collateral_parent_payload(label, rows, limit_map=None):
    def resolved_rate(row):
        return _resolve_rate_limit(row, limit_map) or row.rate_limit

    beginning = _sum_collateral_field(rows, "beginning_collateral")
    ineligibles = _sum_collateral_field(rows, "ineligibles")
    eligible = _sum_collateral_field(rows, "eligible_collateral")
    pre_reserve = _sum_collateral_field(rows, "pre_reserve_collateral")
    reserves = _sum_collateral_field(rows, "reserves")
    net = _sum_collateral_field(rows, "net_collateral")

    return {
        "label": _safe_str(label, default="Collateral"),
        "detail": "",
        "beginning_collateral": _format_currency(beginning),
        "ineligibles": _format_currency(ineligibles),
        "eligible_collateral": _format_currency(eligible),
        "nolv_pct": _format_pct(
            _weighted_collateral_pct(rows, lambda row: row.nolv_pct)
        ),
        "dilution_rate": _format_pct(
            _weighted_collateral_pct(rows, lambda row: row.dilution_rate)
        ),
        "advanced_rate": _format_pct(
            _weighted_collateral_pct(rows, lambda row: row.advanced_rate)
        ),
        "rate_limit": _format_pct(
            _weighted_collateral_pct(rows, resolved_rate)
        ),
        "utilized_rate": _format_pct(
            _weighted_collateral_pct(rows, lambda row: row.utilized_rate)
        ),
        "pre_reserve_collateral": _format_currency(pre_reserve),
        "reserves": _format_currency(reserves),
        "net_collateral": _format_currency(net),
    }


def _build_collateral_child_payload(row, limit_map=None, detail_override=None):
    payload = _collateral_row_payload(row, limit_map=limit_map)
    if detail_override:
        payload["detail"] = detail_override
    return payload


def _build_collateral_tree(collateral_rows, limit_map=None):
    grouped = OrderedDict()
    for row in collateral_rows:
        raw_label = _safe_str(row.main_type, default="Collateral").strip()
        normalized_label = " ".join(raw_label.split()).lower()
        if normalized_label not in grouped:
            grouped[normalized_label] = {
                "label": raw_label or "Collateral",
                "rows": [],
            }
        grouped[normalized_label]["rows"].append(row)

    tree = []
    for entry in grouped.values():
        label = entry["label"]
        rows = entry["rows"]
        node = {
            "id": slugify(label),
            "row": _build_collateral_parent_payload(label, rows, limit_map=limit_map),
            "children": [],
        }
        has_details = any((row.sub_type or "").strip() for row in rows)
        if len(rows) > 1 or has_details:
            children = []
            for idx, row in enumerate(rows, start=1):
                payload = _build_collateral_child_payload(
                    row,
                    limit_map=limit_map,
                    detail_override=(row.sub_type or f"Line {idx}"),
                )
                children.append({
                    "id": slugify(f"{label}-{payload['detail']}-{idx}"),
                    "row": payload,
                })
            node["children"] = children
        tree.append(node)

    return tree


def _risk_direction(score):
    if score is None:
        return "up"
    return "down" if score >= Decimal("3.5") else "up"


def _risk_color(score):
    palette = ["#7EC459", "#D7C63C", "#FBB82E", "#FC8F2E", "#F74C34"]
    dec_score = _to_decimal(score)
    if dec_score <= 0:
        return palette[2]
    bucket = int(dec_score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    bucket = max(1, min(5, bucket))
    return palette[bucket - 1]


def _build_summary_risk_metrics(borrower, ar_row, composite_latest):
    ar_past_due_pct = (
        _normalize_pct(ar_row.pct_past_due)
        if ar_row and ar_row.pct_past_due is not None
        else Decimal("0")
    )
    ar_score = max(
        Decimal("0"),
        min(Decimal("5"), Decimal("5") - (ar_past_due_pct / Decimal("20"))),
    )

    risk_rows = list(
        RiskSubfactorsRow.objects.filter(borrower=borrower).order_by(
            "main_category", "sub_risk"
        )
    )
    rows_by_category = defaultdict(list)
    for row in risk_rows:
        key = (row.main_category or "").strip().lower()
        if not key:
            continue
        rows_by_category[key].append(row)

    def _metric_rows(label):
        key = label.lower()
        if key in rows_by_category:
            return rows_by_category[key]
        for stored_key in rows_by_category:
            if stored_key.startswith(key) or key.startswith(stored_key):
                return rows_by_category[stored_key]
        return []

    def _row_label(row):
        return row.sub_risk or row.high_impact_factor or row.main_category or "Metric"

    def _metric_score(label, fallback_score):
        rows = _metric_rows(label)
        score_vals = []
        seen = set()
        for row in rows:
            metric_label = _row_label(row)
            if metric_label in seen:
                continue
            seen.add(metric_label)
            score_vals.append(_to_decimal(row.risk_score))
        if score_vals:
            return sum(score_vals) / Decimal(len(score_vals))
        return fallback_score

    metric_definitions = [
        ("Accounts Receivable", max(ar_score, Decimal("3"))),
        (
            "Inventory",
            _to_decimal(getattr(composite_latest, "inventory_risk", None))
            if composite_latest
            else Decimal("3"),
        ),
        (
            "Company",
            _to_decimal(getattr(composite_latest, "company_risk", None))
            if composite_latest
            else Decimal("2.5"),
        ),
        (
            "Industry",
            _to_decimal(getattr(composite_latest, "industry_risk", None))
            if composite_latest
            else Decimal("2"),
        ),
    ]

    risk_metrics = []
    for label, fallback in metric_definitions:
        score = _metric_score(label, fallback)
        risk_metrics.append({
            "label": label,
            "detail": f"{score:.1f}",
            "direction": _risk_direction(score),
            "color": _risk_color(score),
        })
    return risk_metrics


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

    range_options = [
        {"value": "last_12_months", "label": "12 Months"},
        {"value": "last_6_months", "label": "6 Months"},
        {"value": "last_3_months", "label": "3 Months"},
        {"value": "last_1_month", "label": "1 Month"},
    ]
    range_aliases = {
        "last_12_months": "last_12_months",
        "last12months": "last_12_months",
        "last 12 months": "last_12_months",
        "12 months": "last_12_months",
        "last_6_months": "last_6_months",
        "last6months": "last_6_months",
        "last 6 months": "last_6_months",
        "6 months": "last_6_months",
        "last_3_months": "last_3_months",
        "last3months": "last_3_months",
        "last 3 months": "last_3_months",
        "3 months": "last_3_months",
        "last_1_month": "last_1_month",
        "last1month": "last_1_month",
        "last 1 month": "last_1_month",
        "1 month": "last_1_month",
    }

    summary_range = request.GET.get("summary_range", "last_12_months")
    normalized_range = range_aliases.get(str(summary_range).strip().lower(), "last_12_months")
    summary_division = request.GET.get("summary_division", "all")
    normalized_division = str(summary_division).strip()
    if normalized_division.lower() in {"all", "all divisions", "all_divisions"}:
        normalized_division = "all"

    range_start, range_end = _range_dates(normalized_range)

    division_values = (
        ARMetricsRow.objects.filter(borrower=borrower)
        .exclude(division__isnull=True)
        .exclude(division__exact="")
        .values_list("division", flat=True)
        .distinct()
    )
    division_options = [{"value": "all", "label": "All Divisions"}]
    division_set = sorted({str(value).strip() for value in division_values if str(value).strip()})
    division_options.extend(
        {"value": value, "label": value}
        for value in division_set
        if value.lower() != "all divisions"
    )
    if normalized_division != "all" and normalized_division not in division_set:
        normalized_division = "all"

    collateral_base_qs = CollateralOverviewRow.objects.filter(borrower=borrower)
    collateral_range_qs = _apply_date_filter(
        collateral_base_qs, "created_at__date", range_start, range_end
    )
    latest_collateral_time = collateral_range_qs.aggregate(time=Max("created_at"))["time"]
    latest_collateral_date = latest_collateral_time.date() if latest_collateral_time else None
    collateral_rows = (
        list(collateral_range_qs.filter(created_at__date=latest_collateral_date))
        if latest_collateral_date
        else []
    )
    limit_rows = list(CollateralLimitsRow.objects.filter(borrower=borrower))
    limit_map = _build_limit_map(limit_rows)
    net_total = sum((_to_decimal(row.net_collateral) for row in collateral_rows), Decimal("0"))
    eligible_total = sum((_to_decimal(row.eligible_collateral) for row in collateral_rows), Decimal("0"))
    ineligibles_total = sum((_to_decimal(row.ineligibles) for row in collateral_rows), Decimal("0"))

    ar_qs = ARMetricsRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        ar_qs = ar_qs.filter(division__iexact=normalized_division)
    ar_qs = _apply_date_filter(ar_qs, "as_of_date", range_start, range_end)
    ar_recent = list(ar_qs.order_by("-as_of_date", "-created_at", "-id")[:2])
    ar_row = ar_recent[0] if ar_recent else None
    ar_prev_row = ar_recent[1] if len(ar_recent) > 1 else None
    risk_ar_row = (
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

    previous_collateral_rows = []
    if latest_collateral_time:
        previous_collateral_time = (
            collateral_range_qs.filter(created_at__lt=latest_collateral_time)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if previous_collateral_time:
            previous_collateral_rows = list(
                collateral_range_qs.filter(created_at=previous_collateral_time)
            )

    previous_net_total = sum(
        (_to_decimal(row.net_collateral) for row in previous_collateral_rows),
        Decimal("0"),
    )
    previous_eligible_total = sum(
        (_to_decimal(row.eligible_collateral) for row in previous_collateral_rows),
        Decimal("0"),
    )
    previous_ineligibles_total = sum(
        (_to_decimal(row.ineligibles) for row in previous_collateral_rows),
        Decimal("0"),
    )
    previous_available_total = previous_eligible_total - previous_ineligibles_total
    if previous_available_total < Decimal("0"):
        previous_available_total = Decimal("0")

    chart_points = 5
    collateral_history = list(
        _apply_date_filter(
            CollateralOverviewRow.objects.filter(borrower=borrower)
            .exclude(created_at__isnull=True),
            "created_at__date",
            range_start,
            range_end,
        )
        .order_by("-created_at")[:200]
    )
    collateral_labels = []
    net_series = []
    availability_series = []
    if collateral_history:
        buckets = {}
        for row in collateral_history:
            date_key = row.created_at.date()
            bucket = buckets.setdefault(
                date_key,
                {"net": Decimal("0"), "eligible": Decimal("0"), "ineligible": Decimal("0")},
            )
            bucket["net"] += _to_decimal(row.net_collateral)
            bucket["eligible"] += _to_decimal(row.eligible_collateral)
            bucket["ineligible"] += _to_decimal(row.ineligibles)
        for date_key in sorted(buckets.keys())[-chart_points:]:
            bucket = buckets[date_key]
            net_series.append(bucket["net"])
            available = bucket["eligible"] - bucket["ineligible"]
            if available < Decimal("0"):
                available = Decimal("0")
            availability_series.append(available)
            collateral_labels.append(date_key.strftime("%m/%d"))

    ar_rows = list(
        ar_qs.order_by("-as_of_date", "-created_at")[:chart_points]
    )
    ar_labels = []
    outstanding_series = []
    if ar_rows:
        for idx, row in enumerate(reversed(ar_rows)):
            date_value = row.as_of_date or (row.created_at.date() if row.created_at else None)
            ar_labels.append(date_value.strftime("%m/%d") if date_value else f"{idx + 1:02d}")
            outstanding_series.append(_to_decimal(row.balance))

    base_labels = _normalize_labels(collateral_labels or ar_labels, chart_points)
    net_series = _normalize_series(net_series, chart_points, net_total)
    availability_series = _normalize_series(availability_series, chart_points, available_total)
    outstanding_series = _normalize_series(
        outstanding_series,
        chart_points,
        ar_row.balance if ar_row and ar_row.balance is not None else Decimal("0"),
    )

    def _delta_payload(current, previous):
        if current is None or previous is None:
            return None
        curr = _to_decimal(current)
        prev = _to_decimal(previous)
        if prev == 0:
            return None
        diff = (curr - prev) / prev * Decimal("100")
        is_positive = diff >= 0
        return {
            "symbol": "▲" if is_positive else "▼",
            "value": f"{abs(diff):.2f}%",
            "class": "up" if is_positive else "down",
        }

    insights["net"]["delta"] = _delta_payload(net_total, previous_net_total if previous_collateral_rows else None)
    insights["outstanding"]["delta"] = _delta_payload(
        ar_row.balance if ar_row else None,
        ar_prev_row.balance if ar_prev_row else None,
    )
    insights["availability"]["delta"] = _delta_payload(
        available_total if collateral_rows else None,
        previous_available_total if previous_collateral_rows else None,
    )

    net_chart = _build_line_series(
        net_series,
        base_labels,
        series_label="Net Collateral",
    )
    outstanding_chart = _build_line_series(
        outstanding_series,
        base_labels,
        series_label="Outstanding Balance",
    )
    availability_chart = _build_line_series(
        availability_series,
        base_labels,
        series_label="Availability",
    )

    inventory_rows = [
        row for row in collateral_rows if row.main_type and "inventory" in row.main_type.lower()
    ]
    inventory_eligible = sum((_to_decimal(row.eligible_collateral) for row in inventory_rows), Decimal("0"))
    inventory_ineligible = sum((_to_decimal(row.ineligibles) for row in inventory_rows), Decimal("0"))
    inventory_total_base = inventory_eligible + inventory_ineligible
    inventory_ratio = (inventory_ineligible / inventory_total_base) if inventory_total_base else None

    composite_latest = (
        CompositeIndexRow.objects.filter(borrower=borrower)
        .order_by("-date", "-created_at", "-id")
        .first()
    )
    risk_metrics = _build_summary_risk_metrics(borrower, risk_ar_row, composite_latest)

    inventory_pct_text = _format_pct(inventory_ratio) if inventory_ratio is not None else "—"
    ar_pct_text = (
        _format_pct(risk_ar_row.pct_past_due)
        if risk_ar_row and risk_ar_row.pct_past_due is not None
        else "—"
    )
    risk_profile_score = _to_decimal(getattr(composite_latest, "overall_score", None))
    risk_profile_detail = f"AR past due {ar_pct_text} · Inventory ineligible {inventory_pct_text}"

    risk_profile_position = float(
        min(max(risk_profile_score / Decimal("5"), Decimal("0")), Decimal("1")) * 100
    )

    context = {
        "borrower_summary": borrower_summary,
        "collateral_rows": collateral_data,
        "collateral_tree": _build_collateral_tree(collateral_rows, limit_map=limit_map),
        "insights": insights,
        "risk_metrics": risk_metrics,
        "user": request.user,
        "active_tab": "summary",
        "net_chart": net_chart,
        "outstanding_chart": outstanding_chart,
        "availability_chart": availability_chart,
        "risk_profile_value": f"{risk_profile_score:.1f}",
        "risk_profile_detail": risk_profile_detail,
        "risk_profile_position": f"{risk_profile_position:.0f}",
        "summary_range_options": range_options,
        "summary_selected_range": normalized_range,
        "summary_division_options": division_options,
        "summary_selected_division": normalized_division,
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
        latest_collateral_date = latest_collateral_time.date() if latest_collateral_time else None
        collateral_rows = (
            list(
                CollateralOverviewRow.objects.filter(
                    borrower=borrower,
                    created_at__date=latest_collateral_date,
                )
            )
            if latest_collateral_date
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
