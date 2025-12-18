import json
import math

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from management.models import (
    ARMetricsRow,
    AgingCompositionRow,
    AvailabilityForecastRow,
    CollateralOverviewRow,
    ConcentrationADODSORow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,
    FGIneligibleDetailRow,
    FGInventoryMetricsRow,
    FGInlineCategoryAnalysisRow,
    FGGrossRecoveryHistoryRow,
    ForecastRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    NOLVTableRow,
    RiskSubfactorsRow,
)
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
    _format_date,
    _safe_str,
    _to_decimal,
)


@login_required(login_url="login")
def collateral_dynamic_view(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None

    section = request.GET.get("section", "inventory")
    allowed_sections = {"overview", "accounts_receivable", "inventory"}
    if section not in allowed_sections:
        section = "inventory"

    inventory_tab = request.GET.get("inventory_tab", "summary")
    allowed_inventory_tabs = {
        "summary",
        "finished_goods",
        "raw_materials",
        "work_in_progress",
        "liquidation_model",
        "other_collateral",
    }
    if inventory_tab not in allowed_inventory_tabs:
        inventory_tab = "summary"

    context = {
        "borrower_summary": _build_borrower_summary(borrower),
        "active_section": section,
        "inventory_tab": inventory_tab,
        "active_tab": "collateral_dynamic",
        **_inventory_context(borrower),
        **_accounts_receivable_context(borrower),
        **_finished_goals_context(borrower),
        **_raw_materials_context(borrower),
        **_work_in_progress_context(borrower),
        **_other_collateral_context(borrower),
        **_liquidation_model_context(borrower),
    }
    return render(request, "collateral_dynamic/accounts_receivable.html", context)


@login_required(login_url="login")
def collateral_static_view(request):
    borrower_profile = getattr(request.user, "borrower_profile", None)
    borrower = borrower_profile.borrower if borrower_profile else None
    context = {
        "active_tab": "collateral_static",
        "week_summary": _week_summary_context(borrower),
    }
    return render(request, "week_summary.html", context)


def _week_summary_context(borrower):
    placeholder_stats = [
        {"label": "Beginning Cash", "value": "$—"},
        {"label": "Total Receipts", "value": "$—"},
        {"label": "Total Disbursement", "value": "$—"},
        {"label": "Net Cash Flow", "value": "$—"},
        {"label": "Ending Cash", "value": "$—"},
    ]

    def _make_placeholders():
        return {"name": "—", "value": "$—"}

    def _format_money(value):
        formatted = _format_currency(value)
        return formatted if formatted != "—" else "$—"

    def _find_variance_row(rows, keywords):
        keywords = [kw.lower() for kw in keywords]
        for row in rows:
            if not row.category:
                continue
            cat = row.category.lower()
            if any(keyword in cat for keyword in keywords):
                return row
        return None

    def _collect_top_receipts(rows, limit=5):
        sorted_rows = sorted(
            rows,
            key=lambda row: _to_decimal(row.total_ar or 0),
            reverse=True,
        )
        output = []
        for row in sorted_rows[:limit]:
            name = _safe_str(row.customer) if row.customer else "Customer"
            amount = _format_money(row.total_ar)
            output.append({"name": name, "value": amount})
        while len(output) < limit:
            output.append(_make_placeholders())
        return output

    def _collect_top_spend(rows, limit=5):
        spend_candidates = [
            row
            for row in rows
            if row.category
            and not any(
                keyword in row.category.lower()
                for keyword in ("receipt", "collection", "cash", "net")
            )
        ]
        sorted_spend = sorted(
            spend_candidates,
            key=lambda row: _to_decimal(row.actual or row.projected or 0),
            reverse=True,
        )
        output = []
        for row in sorted_spend[:limit]:
            name = _safe_str(row.category)
            amount = _format_money(row.actual or row.projected)
            output.append({"name": name, "value": amount})
        while len(output) < limit:
            output.append(_make_placeholders())
        return output

    def _build_chart_rows(rows, max_points=9):
        if not rows:
            return [
                {
                    "label": None,
                    "collections": Decimal("0"),
                    "disbursements": Decimal("0"),
                }
                for _ in range(max_points)
            ]
        values = []
        for row in rows:
            def _pick_value(attr_names):
                for attr in attr_names:
                    val = getattr(row, attr, None)
                    if val is not None:
                        return _to_decimal(val)
                return Decimal("0")

            values.append(
                {
                    "label": row.period or row.as_of_date or getattr(row.report, "report_date", None),
                    "collections": _pick_value(["net_sales", "ar", "available_collateral"]),
                    "disbursements": _pick_value(["loan_balance", "available_collateral"]),
                }
            )
        return values[-max_points:]

    def _format_chart_label(value):
        if isinstance(value, str):
            return value
        if hasattr(value, "strftime"):
            return value.strftime("%b %d")
        return "Week"

    def _sort_forecast_rows(rows):
        def _row_key(row):
            date_val = row.period or row.as_of_date
            if not date_val and getattr(row, "report", None):
                date_val = getattr(row.report, "report_date", None)
            has_date = 1 if date_val else 0
            key_date = date_val if date_val else getattr(row, "id", 0)
            return (has_date, key_date, getattr(row, "id", 0))

        return sorted(rows, key=_row_key)

    def _prepare_column_entries(sorted_rows):
        if not sorted_rows:
            return [], []
        actual_candidates = [
            row for row in sorted_rows if row.actual_forecast and "actual" in row.actual_forecast.lower()
        ]
        actual_row = actual_candidates[0] if actual_candidates else sorted_rows[0]
        ordered_rows = [actual_row] + [
            row for row in sorted_rows if row is not actual_row
        ]
        column_rows = ordered_rows[:13]
        entries = []
        for idx, row in enumerate(column_rows):
            date_val = row.period or row.as_of_date
            if not date_val and getattr(row, "report", None):
                date_val = getattr(row.report, "report_date", None)
            if idx == 0:
                label = f"Actual<br/>{_format_date(date_val)}" if date_val else "Actual"
            else:
                week_number = idx
                formatted = _format_date(date_val) if date_val else None
                label = (
                    f"Forecast<br/>Week {week_number}<br/>{formatted}"
                    if formatted
                    else f"Forecast<br/>Week {week_number}"
                )
            entries.append({"row": row, "label": label, "is_actual": idx == 0})
        return entries, ordered_rows

    context = {
        "stats": placeholder_stats[:],
        "period_label": None,
        "top_receipts": [_make_placeholders() for _ in range(5)],
        "top_spend": [_make_placeholders() for _ in range(5)],
        "chart": {"collections_bars": [], "disbursement_bars": [], "labels": []},
        "cashflow_actual_label": "Actual",
        "cashflow_forecast_labels": [],
        "cashflow_table_rows": [],
        "cashflow_cash_rows": [],
        "availability_actual_label": "Actual",
        "availability_week_labels": [f"Week {i}" for i in range(1, 14)],
        "availability_rows": [],
        "liquidity_series": [],
        "liquidity_labels": [],
        "variance_current_rows": [],
        "variance_cumulative_rows": [],
    }

    def _latest_report_info():
        candidates = []
        report_models = [
            ForecastRow,
            CurrentWeekVarianceRow,
            CummulativeVarianceRow,
            AvailabilityForecastRow,
        ]
        for model in report_models:
            row = (
                model.objects.filter(report__borrower=borrower)
                .order_by(
                    "-report__report_date",
                    "-report__created_at",
                    "-report_id",
                )
                .values(
                    "report_id",
                    "report__report_date",
                    "report__created_at",
                )
                .first()
            )
            if not row or not row.get("report_id"):
                continue
            timestamp = row.get("report__report_date") or row.get("report__created_at")
            if timestamp is None:
                timestamp = 0
            candidates.append(
                {
                    "report_id": row["report_id"],
                    "date": timestamp,
                }
            )
        if not candidates:
            return None
        candidates.sort(key=lambda entry: entry["date"], reverse=True)
        return candidates[0]

    if not borrower:
        return context
    latest_info = _latest_report_info()
    if not latest_info:
        return context
    report_id = latest_info["report_id"]
    report_date = latest_info["date"]
    cw_rows = list(
        CurrentWeekVarianceRow.objects.filter(report_id=report_id).order_by("category", "id")
    )
    cum_rows = list(
        CummulativeVarianceRow.objects.filter(report_id=report_id).order_by("category", "id")
    )
    forecast_rows = list(ForecastRow.objects.filter(report_id=report_id))
    availability_rows_qs = list(
        AvailabilityForecastRow.objects.filter(report_id=report_id).order_by("id")
    )
    stats = []
    summary_map = [
        ("Beginning Cash", ["beginning cash"]),
        ("Total Receipts", ["total receipts"]),
        ("Total Disbursement", ["total disbursement", "total disbursements"]),
        ("Net Cash Flow", ["net cash flow"]),
        ("Ending Cash", ["ending cash"]),
    ]
    for label, keywords in summary_map:
        row = _find_variance_row(cw_rows, keywords)
        value = (
            row.actual
            if row and row.actual is not None
            else row.projected
            if row
            else None
        )
        stats.append({"label": label, "value": _format_money(value)})

    sorted_forecast_rows = _sort_forecast_rows(forecast_rows)
    column_entries, ordered_forecast_rows = _prepare_column_entries(sorted_forecast_rows)
    chart_rows = _build_chart_rows(ordered_forecast_rows or sorted_forecast_rows)
    actual_bars, forecast_bars, chart_labels = _build_chart_bars(chart_rows)

    if column_entries:
        cashflow_actual_label = column_entries[0]["label"]
        cashflow_forecast_labels = [entry["label"] for entry in column_entries[1:]]
    else:
        cashflow_actual_label = "Actual"
        cashflow_forecast_labels = []

    while len(cashflow_forecast_labels) < 12:
        cashflow_forecast_labels.append("Forecast")

    base_forecast_row = (
        column_entries[0]["row"]
        if column_entries
        else sorted_forecast_rows[-1]
        if sorted_forecast_rows
        else None
    )
    fallback_stats = _build_forecast_stats(base_forecast_row)
    if fallback_stats and not any(_has_valid_stat(stat) for stat in stats):
        stats = fallback_stats

    def _get_column_value(accessor, index):
        if not column_entries or index >= len(column_entries):
            return None
        row = column_entries[index]["row"]
        if not row or not accessor:
            return None
        value = accessor(row)
        return _to_decimal(value) if value is not None else None

    def _build_table_row(label, accessor=None, row_class=""):
        actual_val = _get_column_value(accessor, 0)
        forecast_vals = [
            _get_column_value(accessor, idx + 1)
            for idx in range(max(0, len(column_entries) - 1))
        ]
        total_candidates = [val for val in ([actual_val] + forecast_vals) if val is not None]
        total_val = sum(total_candidates, Decimal("0")) if total_candidates else None
        return {
            "label": label,
            "actual": _format_money(actual_val),
            "forecasts": [_format_money(val) for val in forecast_vals],
            "total": _format_money(total_val),
            "row_class": row_class,
        }

    def _value_for_field(row, field):
        if not row:
            return None
        value = getattr(row, field, None)
        return _to_decimal(value) if value is not None else None

    def _sum_fields(row, fields):
        total = Decimal("0")
        present = False
        for field in fields:
            value = getattr(row, field, None)
            if value is not None:
                total += _to_decimal(value)
                present = True
        return total if present else None

    def _difference_fields(row, positive_fields, negative_fields):
        positive = Decimal("0")
        negative = Decimal("0")
        has_positive = False
        has_negative = False
        for field in positive_fields:
            value = getattr(row, field, None)
            if value is not None:
                positive += _to_decimal(value)
                has_positive = True
        for field in negative_fields:
            value = getattr(row, field, None)
            if value is not None:
                negative += _to_decimal(value)
                has_negative = True
        if not has_positive and not has_negative:
            return None
        return positive - negative

    def _has_valid_stat(stat):
        return stat.get("value") not in (None, "$—", "—")

    def _build_forecast_stats(row):
        if not row:
            return None
        beginning = _value_for_field(row, "available_collateral")
        receipts = _sum_fields(row, ["net_sales", "ar"])
        disbursements = _value_for_field(row, "loan_balance")
        net_cash_flow = _difference_fields(row, ["net_sales", "ar"], ["loan_balance"])
        ending = beginning
        return [
            {"label": "Beginning Cash", "value": _format_money(beginning)},
            {"label": "Total Receipts", "value": _format_money(receipts)},
            {"label": "Total Disbursement", "value": _format_money(disbursements)},
            {"label": "Net Cash Flow", "value": _format_money(net_cash_flow)},
            {"label": "Ending Cash", "value": _format_money(ending)},
        ]

    cashflow_metric_defs = [
        ("Collections", lambda row: _value_for_field(row, "net_sales"), ""),
        ("Other Receipts", lambda row: _value_for_field(row, "ar"), ""),
        (
            "Total Receipts",
            lambda row: _sum_fields(row, ["net_sales", "ar"]),
            "title-row",
        ),
        (
            "Operating Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        ("Payroll", lambda row: None, ""),
        ("Rent", lambda row: None, ""),
        ("Utilities", lambda row: None, ""),
        ("Property Tax", lambda row: None, ""),
        ("Insurance", lambda row: None, ""),
        ("Professional Services", lambda row: None, ""),
        ("Software Expenses", lambda row: None, ""),
        ("Repairs / Maintenance", lambda row: None, ""),
        ("Other Disbursements", lambda row: None, ""),
        (
            "Total Operating Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        ("Non-Operating Disbursements", lambda row: None, "title-row"),
        ("Interest Expense", lambda row: None, ""),
        ("Non-Recurring Tax Payments", lambda row: None, ""),
        ("One-Time Professional Fees", lambda row: None, ""),
        ("Total Non-Operating Disbursements", lambda row: None, "title-row"),
        (
            "Total Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        (
            "Net Cash Flow",
            lambda row: _difference_fields(row, ["net_sales", "ar"], ["loan_balance"]),
            "title-row",
        ),
    ]
    cashflow_table_rows = [
        _build_table_row(label, accessor, row_class)
        for label, accessor, row_class in cashflow_metric_defs
    ]
    cashflow_cash_defs = [
        ("Beginning Cash", lambda row: _value_for_field(row, "available_collateral"), ""),
        (
            "Net Cash Flow",
            lambda row: _difference_fields(row, ["net_sales", "ar"], ["loan_balance"]),
            "",
        ),
        (
            "Revolver Draw / Paydown",
            lambda row: _value_for_field(row, "revolver_availability"),
            "",
        ),
        ("Ending Cash", lambda row: _value_for_field(row, "available_collateral"), ""),
        ("Minimum Cash Requirement", lambda row: None, ""),
        ("Cash Cushion / Deficit", lambda row: None, ""),
    ]
    cashflow_cash_rows = [
        _build_table_row(label, accessor, row_class)
        for label, accessor, row_class in cashflow_cash_defs
    ]

    availability_rows = []
    week_fields = [f"week_{i}" for i in range(1, 14)]
    for row in availability_rows_qs:
        week_values = [
            _format_money(getattr(row, field)) for field in week_fields
        ]
        total_val = sum(
            (_to_decimal(getattr(row, field)) for field in week_fields if getattr(row, field) is not None),
            Decimal("0"),
        )
        availability_rows.append(
            {
                "label": _safe_str(row.category, default="Availability"),
                "actual": _format_money(row.x),
                "weeks": week_values,
                "total": _format_money(total_val),
            }
        )

    if availability_rows:
        context["availability_actual_label"] = cashflow_actual_label

    liquidity_fields = [
        ("available_collateral", "#2563eb"),
        ("revolver_availability", "#6574cd"),
        ("net_sales", "#1d4ed8"),
    ]
    liquidity_series = []
    label_points = []
    trend_rows = ordered_forecast_rows[-len(TREND_X_POSITIONS) :]
    if not trend_rows:
        trend_rows = ordered_forecast_rows[-1:] if ordered_forecast_rows else sorted_forecast_rows[-1:]
    period_labels = [
        _format_chart_label(
            getattr(row, "period", None)
            or getattr(row, "as_of_date", None)
            or getattr(getattr(row, "report", None), "report_date", None)
        )
        for row in trend_rows
    ]
    for field, color in liquidity_fields:
        values = [
            float(
                _to_decimal(getattr(row, field, None) or Decimal("0"))
            )
            for row in trend_rows
        ]
        if not values:
            values = [0.0]
        trend = _build_trend_points(values, labels=period_labels)
        liquidity_series.append({"points": trend["points"], "color": color})
        if not label_points:
            label_points = trend["labels"]

    def _variance_rows(rows):
        output = []
        for row in rows:
            category = _safe_str(row.category, default="—")
            proj = _format_money(row.projected)
            actual = _format_money(row.actual)
            variance_amount = _format_money(row.variance)
            variance_pct = _format_pct(row.variance_pct)
            variance_text = f"{variance_amount} / {variance_pct}"
            row_class = "title-row" if "total" in category.lower() or "net" in category.lower() else ""
            output.append(
                {
                    "category": category,
                    "projected": proj,
                    "actual": actual,
                    "variance": variance_text,
                    "row_class": row_class,
                }
            )
        if not output:
            output.append(
                {
                    "category": "—",
                    "projected": "$—",
                    "actual": "$—",
                    "variance": "$— / —%",
                    "row_class": "",
                }
            )
        return output

    variance_current = _variance_rows(cw_rows)
    variance_cumulative = _variance_rows(cum_rows)

    context.update(
        {
            "stats": stats,
            "period_label": _format_date(
                chart_rows[-1]["label"]
                if chart_rows and chart_rows[-1]["label"]
                else report_date
            )
            if chart_rows or report_date
            else None,
            "top_spend": _collect_top_spend(cw_rows),
            "chart": {
                "collections_bars": actual_bars,
                "disbursement_bars": forecast_bars,
                "labels": chart_labels,
                "legend": [
                    {"label": "Collections", "color": "#1d4ed8"},
                    {"label": "Disbursements", "color": "#f97316"},
                ],
            },
            "cashflow_actual_label": cashflow_actual_label,
            "cashflow_forecast_labels": cashflow_forecast_labels,
            "cashflow_table_rows": cashflow_table_rows,
            "cashflow_cash_rows": cashflow_cash_rows,
            "availability_rows": availability_rows,
            "liquidity_series": liquidity_series,
            "liquidity_labels": label_points,
            "variance_current_rows": variance_current,
            "variance_cumulative_rows": variance_cumulative,
            "ar_risk_rows": _accounts_receivable_risk_rows(borrower),
        }
    )
    return context


MONTH_POSITIONS = [80, 135, 190, 245, 300, 355, 410, 465, 520, 575, 630, 685]
TREND_X_POSITIONS = [80, 140, 200, 260, 320, 380, 440, 500, 560, 620, 680]
CIRCUMFERENCE = Decimal(str(2 * math.pi * 45))

CATEGORY_CONFIG = [
    {
        "key": "finished_goods",
        "label": "Finished Goods",
        "match": ("finished", "finished goods", "finish goods", "finish-goods", "fg"),
        "bar_class": "navy",
        "color": "#0b2a66",
    },
    {
        "key": "raw_materials",
        "label": "Raw Materials",
        "match": ("raw", "raw materials", "raw-materials", "raw_material"),
        "bar_class": "mid",
        "color": "#4f63ff",
    },
    {
        "key": "work_in_progress",
        "label": "Work-in-Progress",
        "match": ("work", "work in progress", "work-in-progress", "wip"),
        "bar_class": "bright",
        "color": "#0b66ff",
    },
]

def _build_spark_points(values, width=260, height=64, padding=10):
    if not values:
        values = [50, 50, 50, 50]
    float_values = [float(v) if v is not None else 0.0 for v in values]
    min_val = min(float_values)
    max_val = max(float_values)
    span = width - padding * 2
    step = span / max(1, len(float_values) - 1)
    range_val = max_val - min_val
    if range_val == 0:
        range_val = max(abs(min_val), 1.0)

    points = []
    dots = []
    for idx, value in enumerate(float_values):
        ratio = (value - min_val) / range_val if range_val else 0.5
        ratio = max(0.0, min(1.0, ratio))
        x = padding + idx * step
        y = padding + (1 - ratio) * (height - padding * 2)
        points.append(f"{x:.2f},{y:.2f}")
        dots.append({"cx": round(x, 1), "cy": round(y, 1)})

    return {"points": " ".join(points), "dots": dots}


def _build_trend_chart(values, width=260, height=120, padding=18):
    if not values:
        return {"points": "", "dots": []}
    decimals = [_to_decimal(v) for v in values]
    max_val = max(decimals)
    min_val = min(decimals)
    span = max_val - min_val
    if span == 0:
        span = Decimal("1")
    point_count = len(decimals)
    step = (width - 2 * padding) / (point_count - 1 if point_count > 1 else 1)
    points = []
    dots = []
    for idx, val in enumerate(decimals):
        ratio = (val - min_val) / span
        x = padding + step * idx
        y = height - padding - float(ratio) * (height - 2 * padding)
        points.append(f"{x:.2f},{y:.2f}")
        dots.append({"cx": round(x, 1), "cy": round(y, 1)})
    return {"points": " ".join(points), "dots": dots}


def _build_trend_points(values, labels=None, width=520, height=210, left=50, top=50, bottom=40):
    if not values:
        return {"points": "", "dots": [], "labels": []}
    float_values = [float(v if v is not None else 0.0) for v in values]
    total_width = width - left - 20
    step = total_width / max(1, len(float_values) - 1)
    baseline_y = height - bottom
    chart_height = baseline_y - top
    max_value = max(float_values + [100.0]) or 1.0

    points = []
    dots = []
    label_points = []
    for idx, value in enumerate(float_values):
        ratio = max(0.0, min(1.0, value / max_value))
        x = left + idx * step
        y = baseline_y - ratio * chart_height
        points.append(f"{x:.1f},{y:.1f}")
        dots.append({"cx": round(x, 1), "cy": round(y, 1)})
        label_text = labels[idx] if labels and idx < len(labels) else ""
        label_points.append({"x": round(x, 1), "text": label_text})

    return {"points": " ".join(points), "dots": dots, "labels": label_points}


def _format_variance(value, suffix=""):
    if value is None:
        return "—"
    val = float(_to_decimal(value))
    return f"{val:+.1f}{suffix}"


def _get_category_definition(key):
    return next((category for category in CATEGORY_CONFIG if category["key"] == key), None)

def _filter_inventory_rows_by_key(state, key):
    category_def = _get_category_definition(key)
    if not category_def:
        return []
    return [row for row in state["inventory_rows"] if _matches_category(row, category_def["match"])]


def _empty_summary_entry(label):
    return {
        "label": label,
        "total": "—",
        "ineligible": "—",
        "available": "—",
        "pct_available": "—",
    }

RAW_CATEGORY_DEFINITIONS = [
    ("Metal Coils & Sheet", ["coil", "sheet", "metal"]),
    ("Lumber Components", ["lumber", "wood"]),
    ("PVC & Vinyl Resin", ["pvc", "vinyl"]),
    ("Glass & Window Components", ["glass", "window"]),
    ("Resin & Polymers", ["resin", "polymer"]),
    ("Fiber & Insulation Inputs", ["fiber", "insulation"]),
    ("Paints & Coating Base", ["paint", "coating", "primer"]),
    ("Fasteners & Hardware", ["fastener", "hardware", "bolt", "screw"]),
    ("Packaging Materials", ["packaging", "box", "container"]),
    ("Adhesives & Sealants", ["adhesive", "sealant"]),
]


def _matches_category(row, keywords):
    text = " ".join(
        filter(
            None,
            [
                (row.sub_type or "").strip().lower(),
                (row.main_type or "").strip().lower(),
            ],
        )
    )
    return any(keyword in text for keyword in keywords)


def _inventory_state(borrower):
    if not borrower:
        return None

    latest_report = BorrowerReport.objects.filter(borrower=borrower).order_by("-report_date").first()
    if not latest_report:
        return None

    collateral_rows = list(
        CollateralOverviewRow.objects.filter(borrower=borrower).order_by("id")
    )
    inventory_rows = [
        row for row in collateral_rows if row.main_type and "inventory" in row.main_type.lower()
    ]
    if not inventory_rows:
        return None

    inventory_total = Decimal("0")
    inventory_ineligible = Decimal("0")
    inventory_net_total = Decimal("0")

    category_metrics = {
        category["key"]: {
            "eligible": Decimal("0"),
            "beginning": Decimal("0"),
            "net": Decimal("0"),
            "pre_reserve": Decimal("0"),
            "reserves": Decimal("0"),
            "nolv_numerator": Decimal("0"),
            "nolv_denominator": Decimal("0"),
            "trend_numerator": Decimal("0"),
            "trend_denominator": Decimal("0"),
            "has_data": False,
            "trend_pct": Decimal("0"),
        }
        for category in CATEGORY_CONFIG
    }

    for row in inventory_rows:
        eligible = _to_decimal(row.eligible_collateral)
        inventory_total += eligible
        inventory_ineligible += _to_decimal(row.ineligibles)
        net_collateral = _to_decimal(row.net_collateral)
        inventory_net_total += net_collateral
        for category in CATEGORY_CONFIG:
            if _matches_category(row, category["match"]):
                metrics = category_metrics[category["key"]]
                metrics["eligible"] += eligible
                row_beginning = _to_decimal(row.beginning_collateral)
                metrics["beginning"] += row_beginning
                metrics["net"] += net_collateral
                metrics["pre_reserve"] += _to_decimal(row.pre_reserve_collateral)
                metrics["reserves"] += _to_decimal(row.reserves)
                metrics["has_data"] = True

                if eligible > 0:
                    metrics["nolv_numerator"] += _to_decimal(row.nolv_pct) * eligible
                    metrics["nolv_denominator"] += eligible
                if row_beginning > 0:
                    metrics["trend_numerator"] += net_collateral - row_beginning
                    metrics["trend_denominator"] += row_beginning
                break

    inventory_available_total = inventory_total - inventory_ineligible
    if inventory_available_total < 0:
        inventory_available_total = Decimal("0")

    return {
        "latest_report": latest_report,
        "inventory_rows": inventory_rows,
        "inventory_total": inventory_total,
        "inventory_ineligible": inventory_ineligible,
        "inventory_net_total": inventory_net_total,
        "inventory_available_total": inventory_available_total,
        "category_metrics": category_metrics,
    }


def _format_signed_pct(value):
    if value is None:
        return "—"
    try:
        pct = Decimal(value)
    except (TypeError, ValueError):
        try:
            pct = Decimal(str(value))
        except Exception:
            return "—"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _inventory_context(borrower):
    empty_mix = [
        {"label": item["label"], "percentage_display": "0%", "bar_class": item["bar_class"]}
        for item in CATEGORY_CONFIG
    ]
    empty_breakdown = [
        {
            "label": item["label"],
            "available_inventory": "—",
            "gross_recovery": "—",
            "cogs": "—",
            "liquidation_cost": "—",
            "net_recovery_trend": "—",
        }
        for item in CATEGORY_CONFIG
    ]

    context = {
        "snapshot_text": "Inventory snapshots will populate here once the latest collateral data arrives.",
        "inventory_available_display": "—",
        "inventory_mix": empty_mix,
        "inventory_breakdown": empty_breakdown,
        "inventory_donut_segments": [],
        "inventory_mix_chart_columns": [],
        "inventory_trend_series": [],
    }

    state = _inventory_state(borrower)
    if not state:
        return context

    inventory_total = state["inventory_total"]
    inventory_ineligible = state["inventory_ineligible"]
    inventory_net_total = state["inventory_net_total"]
    inventory_available_total = state["inventory_available_total"]
    inventory_rows = state["inventory_rows"]
    category_metrics = state["category_metrics"]

    inventory_available_display = _format_currency(inventory_available_total)
    ineligible_display = _format_currency(inventory_ineligible)
    snapshot_text = (
        f"{inventory_available_display} of inventory is currently available with "
        f"{ineligible_display} marked ineligible across {len(inventory_rows)} snapshots. "
        f"Net collateral totals {_format_currency(inventory_net_total)}."
    )

    mix_total = inventory_total if inventory_total > 0 else Decimal("0")

    inventory_mix = []
    for category in CATEGORY_CONFIG:
        metrics = category_metrics[category["key"]]
        if mix_total > 0:
            pct_ratio = metrics["eligible"] / mix_total
        else:
            pct_ratio = Decimal("0")
        metrics["mix_pct"] = pct_ratio
        inventory_mix.append(
            {
                "label": category["label"],
                "percentage_display": _format_pct(pct_ratio),
                "bar_class": category["bar_class"],
                "percentage_value": float(pct_ratio),
            }
        )

    inventory_breakdown = []
    for category in CATEGORY_CONFIG:
        metrics = category_metrics[category["key"]]
        if not metrics["has_data"]:
            inventory_breakdown.append(
                {
                    "label": category["label"],
                    "available_inventory": "—",
                    "gross_recovery": "—",
                    "cogs": "—",
                    "liquidation_cost": "—",
                    "net_recovery_trend": "—",
                }
            )
            continue

        cogs_value = (
            metrics["nolv_numerator"] / metrics["nolv_denominator"]
            if metrics["nolv_denominator"] > 0
            else None
        )
        trend_pct = (
            (metrics["trend_numerator"] / metrics["trend_denominator"]) * Decimal("100")
            if metrics["trend_denominator"] > 0
            else None
        )
        liquidation_budget = metrics["pre_reserve"] or metrics["reserves"]

        inventory_breakdown.append(
            {
                "label": category["label"],
                "available_inventory": _format_currency(metrics["eligible"]),
                "gross_recovery": _format_currency(metrics["beginning"]),
                "cogs": _format_pct(cogs_value),
                "liquidation_cost": _format_currency(-liquidation_budget)
                if liquidation_budget
                else "—",
                "net_recovery_trend": _format_signed_pct(trend_pct),
            }
        )
        metrics["trend_pct"] = trend_pct or Decimal("0")

    category_percentages = {}
    for category in CATEGORY_CONFIG:
        metrics = category_metrics[category["key"]]
        mix_pct = metrics.get("mix_pct", Decimal("0"))
        category_percentages[category["key"]] = mix_pct

    donut_segments = []
    offset = Decimal("0")
    for category in CATEGORY_CONFIG:
        pct = category_percentages[category["key"]]
        dash = pct * CIRCUMFERENCE
        remainder = CIRCUMFERENCE - dash
        donut_segments.append(
            {
                "color": category["color"],
                "dasharray": f"{float(dash):.2f} {float(remainder):.2f}",
                "dashoffset": float(offset),
            }
        )
        offset -= dash

    chart_height = Decimal("150")
    base_y = Decimal("18")
    inventory_mix_chart_columns = []
    for idx, base_x in enumerate(MONTH_POSITIONS):
        column_bars = []
        for bucket_index, category in enumerate(CATEGORY_CONFIG):
            pct = category_percentages[category["key"]]
            variation = Decimal(idx % 3 - 1) * Decimal("0.02")
            height_pct = max(Decimal("0"), min(Decimal("1"), pct + variation))
            height_decimal = height_pct * chart_height
            column_bars.append(
                {
                    "x": base_x + bucket_index * 15,
                    "y": float(base_y + (chart_height - height_decimal)),
                    "height": float(height_decimal),
                    "width": 10,
                    "color": category["color"],
                }
            )
        inventory_mix_chart_columns.append({"bars": column_bars})

    inventory_trend_series = []
    for category in CATEGORY_CONFIG:
        metrics = category_metrics[category["key"]]
        trend_base = metrics.get("trend_pct") or Decimal("0")
        points = []
        points_list = []
        for idx, x in enumerate(TREND_X_POSITIONS):
            jitter = Decimal(idx - len(TREND_X_POSITIONS) // 2) * Decimal("0.5")
            value = trend_base + jitter
            value = max(min(value, Decimal("10")), Decimal("-10"))
            y_value = Decimal("192") - value * Decimal("4")
            y_value = max(min(y_value, Decimal("192")), Decimal("22"))
            points.append(f"{x},{float(y_value):.1f}")
            points_list.append({"x": x, "y": float(y_value)})
        inventory_trend_series.append(
            {
                "color": category["color"],
                "points": " ".join(points),
                "points_list": points_list,
            }
        )

    return {
        "snapshot_text": snapshot_text,
        "inventory_available_display": inventory_available_display,
        "inventory_mix": inventory_mix,
        "inventory_breakdown": inventory_breakdown,
        "inventory_donut_segments": donut_segments,
        "inventory_mix_chart_columns": inventory_mix_chart_columns,
        "inventory_trend_series": inventory_trend_series,
    }

def _accounts_receivable_context(borrower):
    base_context = {
        "ar_borrowing_base_kpis": [],
        "ar_aging_chart_buckets": [],
        "ar_current_vs_past_due_trend": {"bars": [], "labels": []},
        "ar_ineligible_overview_rows": [],
        "ar_ineligible_overview_total": None,
        "ar_ineligible_trend": {"points": "", "dots": [], "labels": []},
        "ar_concentration_rows": [],
        "ar_ado_rows": [],
        "ar_dso_rows": [],
        "ar_risk_rows": [],
    }

    if not borrower:
        return base_context

def _accounts_receivable_risk_rows(borrower):
    if not borrower:
        return []
    return list(
        RiskSubfactorsRow.objects.filter(
            borrower=borrower,
            main_category__iexact="Accounts Receivable",
        ).order_by("sub_risk")
    )

    latest_report = (
        BorrowerReport.objects.filter(borrower=borrower)
        .order_by("-report_date", "-created_at")
        .first()
    )
    if not latest_report:
        return base_context

    ar_rows_latest = list(ARMetricsRow.objects.filter(report=latest_report))
    if not ar_rows_latest:
        return base_context

    aging_rows = list(AgingCompositionRow.objects.filter(report=latest_report))
    ineligible_overview = (
        IneligibleOverviewRow.objects.filter(report=latest_report)
        .order_by("-date", "-id")
        .first()
    )
    concentration_rows = list(
        ConcentrationADODSORow.objects.filter(report=latest_report)
    )
    ineligible_trend_rows = list(
        IneligibleTrendRow.objects.filter(report__borrower=borrower)
        .order_by("date", "id")
    )

    def _aggregate_ar_rows(rows):
        total_balance = Decimal("0")
        total_current = Decimal("0")
        total_past_due = Decimal("0")
        weighted_dso = Decimal("0")
        for row in rows:
            balance = _to_decimal(row.balance)
            total_balance += balance
            current_amt = _to_decimal(row.current_amt)
            past_due_amt = _to_decimal(row.past_due_amt)
            total_current += current_amt
            total_past_due += past_due_amt
            weighted_dso += _to_decimal(row.dso) * balance
        avg_dso = weighted_dso / total_balance if total_balance else Decimal("0")
        total_amount = total_current + total_past_due
        past_due_pct = (
            (total_past_due / total_amount * Decimal("100")) if total_amount else Decimal("0")
        )
        current_pct = (
            (total_current / total_amount * Decimal("100")) if total_amount else Decimal("0")
        )
        return {
            "total_balance": total_balance,
            "avg_dso": avg_dso,
            "past_due_pct": past_due_pct,
            "current_pct": current_pct,
            "total_current_amt": total_current,
            "total_past_due_amt": total_past_due,
        }

    history = []
    reports = BorrowerReport.objects.filter(borrower=borrower).order_by(
        "report_date", "created_at"
    )
    for report in reports:
        rows = list(ARMetricsRow.objects.filter(report=report))
        if not rows:
            continue
        payload = _aggregate_ar_rows(rows)
        if not (
            payload["total_balance"]
            or payload["total_current_amt"]
            or payload["total_past_due_amt"]
        ):
            continue
        label_date = report.report_date or report.created_at
        label = label_date.strftime("%b %y") if label_date else f"Report {report.id}"
        history.append({**payload, "label": label})
    if not history:
        return base_context
    max_history = 12
    if len(history) > max_history:
        history = history[-max_history:]

    def _format_days(value):
        if value is None:
            return "—"
        return f"{int(round(_to_decimal(value))):,}"

    def _format_pct_display(value):
        if value is None:
            return "—"
        pct = _to_decimal(value)
        if pct > Decimal("1"):
            pct /= Decimal("100")
        return _format_pct(pct)

    def _delta_payload(current, previous, improvement_on_increase=True):
        if previous is None or previous == 0:
            return None
        curr = _to_decimal(current)
        prev = _to_decimal(previous)
        if prev == 0:
            return None
        diff = (curr - prev) / prev * Decimal("100")
        is_positive = diff >= 0
        symbol = "▲" if is_positive else "▼"
        value = f"{abs(diff):.1f}%"
        if not improvement_on_increase:
            is_positive = not is_positive
        return {
            "symbol": symbol,
            "value": value,
            "delta_class": "up" if is_positive else "down",
        }

    current_snapshot = history[-1]
    previous_snapshot = history[-2] if len(history) > 1 else None
    kpi_specs = [
        {
            "label": "Balance",
            "key": "total_balance",
            "formatter": lambda value: _format_currency(_to_decimal(value)),
            "color": "var(--blue-3)",
            "improvement_on_increase": True,
        },
        {
            "label": "Days Sales Outstanding",
            "key": "avg_dso",
            "formatter": lambda value: _format_days(value),
            "color": "var(--purple)",
            "improvement_on_increase": False,
        },
        {
            "label": "% of total past due",
            "key": "past_due_pct",
            "formatter": lambda value: _format_pct_display(value),
            "color": "var(--teal)",
            "improvement_on_increase": False,
        },
    ]
    kpis = []
    for spec in kpi_specs:
        spark = _build_spark_points([row[spec["key"]] for row in history])
        chart = _build_trend_chart([row[spec["key"]] for row in history])
        delta = _delta_payload(
            current_snapshot[spec["key"]],
            previous_snapshot[spec["key"]] if previous_snapshot else None,
            spec["improvement_on_increase"],
        )
        kpis.append(
            {
                "label": spec["label"],
                "value": spec["formatter"](current_snapshot[spec["key"]]),
                "color": spec["color"],
                "spark_points": spark["points"],
                "spark_dots": spark["dots"],
                "delta": delta["value"] if delta else None,
                "symbol": delta["symbol"] if delta else "",
                "delta_class": delta["delta_class"] if delta else "",
                "chart_points": chart["points"],
                "chart_dots": chart["dots"],
            }
        )

    AGING_BUCKET_DEFS = [
        {"key": "current", "label": "Current", "color": "#1b2a55"},
        {"key": "0-30", "label": "0-30", "color": "rgba(43,111,247,.35)"},
        {"key": "31-60", "label": "31-60", "color": "rgba(43,111,247,.25)"},
        {"key": "61-90", "label": "61-90", "color": "rgba(43,111,247,.30)"},
        {"key": "90+", "label": "90+", "color": "rgba(43,111,247,.20)"},
    ]

    def _bucket_key(bucket_label):
        if not bucket_label:
            return None
        normalized = bucket_label.lower().replace(" ", "")
        if "current" in normalized:
            return "current"
        if normalized.startswith("0"):
            return "0-30"
        if normalized.startswith("31") or "31-60" in normalized:
            return "31-60"
        if normalized.startswith("61") or "61-90" in normalized:
            return "61-90"
        if "90" in normalized:
            return "90+"
        return None

    bucket_amounts = {bucket["key"]: Decimal("0") for bucket in AGING_BUCKET_DEFS}
    bucket_pct_overrides = {}
    for row in aging_rows:
        key = _bucket_key(row.bucket)
        if not key:
            continue
        bucket_amounts[key] += _to_decimal(row.amount)
        if row.pct_of_total is not None:
            bucket_pct_overrides[key] = _to_decimal(row.pct_of_total)

    total_amount = sum(bucket_amounts.values())
    bucket_positions = [70, 140, 210, 280, 350]
    aging_buckets = []
    for idx, bucket in enumerate(AGING_BUCKET_DEFS):
        amount = bucket_amounts[bucket["key"]]
        percent_override = bucket_pct_overrides.get(bucket["key"])
        if percent_override is not None:
            percent_ratio = percent_override
        else:
            percent_ratio = amount / total_amount if total_amount else Decimal("0")
        if percent_ratio > Decimal("1"):
            percent_ratio /= Decimal("100")
        ratio_float = float(percent_ratio) if percent_ratio else 0.0
        height_value = max(8.0, min(110.0, ratio_float * 110))
        y_position = 140 - height_value
        aging_buckets.append(
            {
                "x": bucket_positions[idx],
                "y": y_position,
                "height": height_value,
                "width": 40,
                "color": bucket["color"],
                "percent_display": _format_pct(percent_ratio),
                "label": bucket["label"],
                "percent_y": max(24, y_position - 6),
                "label_y": 160,
                "text_x": bucket_positions[idx] + 20,
            }
        )

    trend_bars = []
    trend_labels = []
    for idx, entry in enumerate(history):
        past_pct = float(entry["past_due_pct"])
        current_pct = float(entry["current_pct"])
        past_height = min(120.0, max(8.0, past_pct))
        current_height = min(120.0, max(8.0, current_pct))
        past_y = 140 - past_height
        current_y = 140 - current_height
        past_x = 58 + idx * 34
        current_x = past_x + 12
        label_x = past_x + 6
        trend_bars.append(
            {
                "past_due_x": past_x,
                "past_due_y": past_y,
                "past_due_height": past_height,
                "current_x": current_x,
                "current_y": current_y,
                "current_height": current_height,
            }
        )
        trend_labels.append({"x": label_x, "text": entry["label"]})

    ineligible_rows = []
    ineligible_total_row = None
    if ineligible_overview:
        total_ineligible = _to_decimal(ineligible_overview.total_ineligible)
        categories = [
            ("Past Due Over 60 Days", ineligible_overview.past_due_gt_90_days),
            ("Dilution", ineligible_overview.dilution),
            ("Cross Age", ineligible_overview.cross_age),
            ("Concentration Over Cap", ineligible_overview.concentration_over_cap),
            ("Foreign Receivable", ineligible_overview.foreign),
            ("Government Receivable", ineligible_overview.government),
            ("Intercompany Receivable", ineligible_overview.intercompany),
            ("Contra Receivable", ineligible_overview.contra),
            ("Other", ineligible_overview.other),
        ]
        for label, amount in categories:
            amount_value = _to_decimal(amount)
            pct = amount_value / total_ineligible if total_ineligible else Decimal("0")
            ineligible_rows.append(
                {
                    "label": label,
                    "amount": _format_currency(amount_value),
                    "pct": _format_pct(pct),
                }
            )
        ineligible_total_row = {
            "label": "Total",
            "amount": _format_currency(total_ineligible),
            "pct": _format_pct(Decimal("1")),
        }

    trend_points = []
    trend_texts = []
    for row in ineligible_trend_rows:
        value = float(_to_decimal(row.ineligible_pct_of_ar) * Decimal("100"))
        trend_points.append(value)
        label_date = row.date
        label = label_date.strftime("%b %y") if label_date else f"Point {row.id}"
        trend_texts.append(label)
    max_trend = 12
    if len(trend_points) > max_trend:
        trend_points = trend_points[-max_trend:]
        trend_texts = trend_texts[-max_trend:]
    trend_chart = _build_trend_points(trend_points, trend_texts)

    concentration_entries = []
    for row in sorted(
        concentration_rows,
        key=lambda r: _to_decimal(r.current_concentration_pct),
        reverse=True,
    )[:10]:
        concentration_entries.append(
            {
                "customer": _safe_str(row.customer),
                "current": _format_pct(row.current_concentration_pct),
                "average": _format_pct(row.avg_ttm_concentration_pct),
                "variance": _format_variance(row.variance_concentration_pp, suffix="pp"),
            }
        )

    ado_entries = []
    for row in sorted(
        concentration_rows,
        key=lambda r: _to_decimal(r.current_ado_days),
        reverse=True,
    )[:10]:
        ado_entries.append(
            {
                "current": _format_days(row.current_ado_days),
                "average": _format_days(row.avg_ttm_ado_days),
                "variance": _format_variance(row.variance_ado_days, suffix="d"),
            }
        )

    dso_entries = []
    for row in sorted(
        concentration_rows,
        key=lambda r: _to_decimal(r.current_dso_days),
        reverse=True,
    )[:10]:
        dso_entries.append(
            {
                "current": _format_days(row.current_dso_days),
                "average": _format_days(row.avg_ttm_dso_days),
                "variance": _format_variance(row.variance_dso_days, suffix="d"),
            }
        )

    return {
        "ar_borrowing_base_kpis": kpis,
        "ar_aging_chart_buckets": aging_buckets,
        "ar_current_vs_past_due_trend": {"bars": trend_bars, "labels": trend_labels},
        "ar_ineligible_overview_rows": ineligible_rows,
        "ar_ineligible_overview_total": ineligible_total_row,
        "ar_ineligible_trend": {
            "points": trend_chart["points"],
            "dots": trend_chart["dots"],
            "labels": trend_chart["labels"],
        },
        "ar_concentration_rows": concentration_entries,
        "ar_ado_rows": ado_entries,
        "ar_dso_rows": dso_entries,
    }


def _finished_goals_context(borrower):
    base_context = {
        "finished_goals_metrics": [],
        "finished_goals_highlights": [],
        "finished_goals_chart_config": {},
        "finished_goals_ar_concentration": [],
        "finished_goals_ar_aging": {
            "buckets": [],
            "amounts": [],
            "shares": [],
            "total_amount": "—",
            "total_share": "—",
        },
        "finished_goals_stock": [],
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    inventory_total = state["inventory_total"]
    inventory_available_total = state["inventory_available_total"]
    inventory_ineligible = state["inventory_ineligible"]
    inventory_net_total = state["inventory_net_total"]
    category_metrics = state["category_metrics"]
    inventory_rows = state["inventory_rows"]
    latest_report = state["latest_report"]

    ar_row = (
        ARMetricsRow.objects.filter(report=latest_report).order_by("-as_of_date").first()
        if latest_report
        else None
    )

    metric_defs = [
        ("Total Inventory", inventory_total, None),
        ("Raw Materials", category_metrics["raw_materials"]["eligible"], None),
        ("Work in Process", category_metrics["work_in_progress"]["eligible"], None),
        ("Finished Goods", category_metrics["finished_goods"]["eligible"], None),
    ]

    metrics = []
    for label, amount, delta in metric_defs:
        metrics.append(
            {
                "label": label,
                "value": _format_currency(amount),
                "delta": delta,
                "delta_class": "good" if delta and delta.startswith("▲") else "bad"
                if delta
                else "",
            }
        )

    total_base = float(inventory_total or Decimal("0"))
    net_base = float(inventory_net_total or Decimal("1"))
    turnover = total_base / net_base if net_base else 0
    days_outstanding = 365 / turnover if turnover else None
    aged_share = inventory_ineligible / (inventory_total or Decimal("1"))

    highlights = [
        {"label": "Inventory Turnover", "value": f"{turnover:.1f}x"},
        {
            "label": "Days Inventory Outstanding",
            "value": f"{days_outstanding:.0f}" if days_outstanding else "—",
        },
        {"label": "Aged Stock (>180d)", "value": _format_pct(aged_share)},
        {
            "label": "Receivables DSO",
            "value": f"{float(_to_decimal(ar_row.dso)):.0f}" if ar_row and ar_row.dso else "—",
        },
        {
            "label": "Top Customer Concentration",
            "value": _format_pct(
                max(
                    (
                        metrics_def["eligible"] / (inventory_total or Decimal("1"))
                        for metrics_def in category_metrics.values()
                    ),
                    default=Decimal("0"),
                )
            ),
        },
    ]

    def _series(base, variance, length=12, scale=1):
        base_value = float(base or 0)
        return [
            max(0, base_value + math.sin(i / 2.0) * float(variance) * scale)
            for i in range(length)
        ]

    chart_config = {
        "inventoryTrend": {
            "type": "line",
            "title": "Inventory Trend",
            "labels": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
            "values": _series(total_base/1e6 if total_base else 0.5, 0.2),
            "yPrefix": "$",
            "ySuffix": "M",
            "yTicks": 5,
        },
        "agedStock": {
            "type": "bar",
            "title": "Aged Stock",
            "labels": ["0-30","31-60","61–90","91–120","121–180","180+"],
            "values": _series(float(inventory_ineligible)/1e6 if inventory_ineligible else 0.25, 0.15, length=6),
            "highlightIndex": 3,
            "yPrefix": "$",
            "ySuffix": "M",
            "yTicks": 4,
        },
        "agedStockTrend": {
            "type": "line",
            "title": "Aged Stock Trend",
            "labels": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
            "values": _series(float(aged_share * Decimal("20")), 1.2),
            "yPrefix": "$",
            "ySuffix": "M",
            "yTicks": 4,
        },
        "inboundOutbound": {
            "type": "bar",
            "title": "In-Bound vs Outbound",
            "labels": ["W1","W2","W3","W4","W5","W6"],
            "values": _series(float(inventory_available_total)/1e6 if inventory_available_total else 0.3, 0.2, length=6),
            "highlightIndex": 3,
            "yPrefix": "$",
            "ySuffix": "M",
            "yTicks": 4,
        },
        "inboundOutboundTrend": {
            "type": "line",
            "title": "In-Bound vs Outbound Trend",
            "labels": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
            "values": _series(
                float(
                    (inventory_available_total / inventory_total if inventory_total else Decimal("0.4"))
                    * Decimal("10")
                ),
                0.8,
            ),
            "yPrefix": "$",
            "ySuffix": "M",
            "yTicks": 4,
        },
    }

    share_labels = ["Current","1–30","31–60","61–90","91–120","120+"]
    bucket_bases = [0.45, 0.15, 0.1, 0.09, 0.08, 0.13]
    bucket_amounts = [
        _format_currency(Decimal(str(base)) * (inventory_total or Decimal("0")))
        for base in bucket_bases
    ]
    bucket_shares = [f"{base * 100:.0f}%" for base in bucket_bases]

    ar_concentration = []
    sorted_categories = sorted(
        CATEGORY_CONFIG,
        key=lambda item: category_metrics[item["key"]]["eligible"],
        reverse=True,
    )
    for idx, category in enumerate(sorted_categories):
        metrics_def = category_metrics[category["key"]]
        share = (
            metrics_def["eligible"] / (inventory_total or Decimal("1"))
        ) if inventory_total else Decimal("0")
        ar_concentration.append(
            {
                "customer": category["label"],
                "balance": _format_currency(metrics_def["eligible"]),
                "share": _format_pct(share),
                "avg_days": 30 + idx * 4,
                "status": "Current",
                "last_payment": "—",
                "notes": "—",
            }
        )

    stock_rows = sorted(
        inventory_rows,
        key=lambda row: _to_decimal(row.eligible_collateral),
        reverse=True,
    )[:6]
    stock_data = []
    for row in stock_rows:
        eligible = _to_decimal(row.eligible_collateral)
        beginning = _to_decimal(row.beginning_collateral)
        turns = (
            float(beginning / eligible)
            if eligible and eligible != 0
            else 0
        )
        stock_data.append(
            {
                "sku": row.sub_type or row.main_type or "Item",
                "category": row.main_type or "Inventory",
                "description": row.sub_type or row.main_type or "Collateral",
                "on_hand": _format_currency(beginning),
                "unit_cost": _format_currency(
                    eligible and beginning / eligible or beginning
                ),
                "value": _format_currency(_to_decimal(row.net_collateral)),
                "age": f"{int((_to_decimal(row.nolv_pct) or Decimal('0')) * Decimal('365'))}",
                "turns": f"{turns:.1f}",
                "status": "Current" if _to_decimal(row.net_collateral) >= 0 else "At Risk",
            }
        )

    return {
        "finished_goals_metrics": metrics,
        "finished_goals_highlights": highlights,
        "finished_goals_chart_config": chart_config,
        "finished_goals_chart_config_json": json.dumps(chart_config),
        "finished_goals_ar_concentration": ar_concentration,
        "finished_goals_ar_aging": {
            "buckets": share_labels,
            "amounts": bucket_amounts,
            "shares": bucket_shares,
            "total_amount": _format_currency(inventory_total),
            "total_share": "100%",
        },
        "finished_goals_stock": stock_data,
    }


ICON_SVGS = {
    "Total Inventory": """
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <path d="M6 17V10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M12 17V7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M18 17v-5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
    """,
    "Ineligible Inventory": """
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <path d="M7 7h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M7 12h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M7 17h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
    """,
    "Available Inventory": """
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <path d="M6 18V6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M6 18h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M9 14l3-3 3 2 4-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
}

REASON_ORDER = [
    ("slow-moving/obsolete", ["slow", "obsolete"]),
    ("aged", ["aged"]),
    ("work-in-progress", ["work", "wip"]),
    ("consigned", ["consign"]),
    ("in-transit", ["in-transit", "in transit"]),
    ("damaged/non-saleable", ["damage", "non-saleable", "non saleable"]),
]

def _raw_materials_context(borrower):
    base_context = {
        "raw_materials_metrics": [],
        "raw_materials_ineligible_detail": [],
        "raw_materials_chart_config": {},
        "raw_materials_category_rows": [],
        "raw_materials_category_footer": {},
        "raw_materials_top_skus": [],
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    inventory_total = state["inventory_total"]
    inventory_available_total = state["inventory_available_total"]
    inventory_ineligible = state["inventory_ineligible"]
    category_metrics = state["category_metrics"]
    inventory_rows = state["inventory_rows"]

    available_pct = (
        (inventory_available_total / inventory_total) if inventory_total else Decimal("0")
    )

    available_delta = available_pct - Decimal("0.5")
    available_symbol = "▲" if available_delta >= 0 else "▼"
    available_delta_text = f"{abs(available_delta * Decimal('100')):.1f}%"
    metrics = [
        {
            "label": "Total Inventory",
            "value": _format_currency(inventory_total),
            "delta": -abs(available_delta * Decimal("100")) if inventory_total else None,
            "delta_class": "danger",
            "symbol": "▼",
        },
        {
            "label": "Ineligible Inventory",
            "value": _format_currency(inventory_ineligible),
            "delta": -abs(available_delta * Decimal("100")) if inventory_ineligible else None,
            "delta_class": "danger",
            "symbol": "▼",
        },
        {
            "label": "Available Inventory",
            "value": _format_pct(available_pct),
            "delta": available_delta * Decimal("100"),
            "delta_class": "success" if available_delta >= 0 else "danger",
            "symbol": "▲" if available_delta >= 0 else "▼",
        },
    ]

    formatted_metrics = []
    for metric in metrics:
        delta = metric.get("delta")
        if delta is not None:
            delta_display = f"{abs(delta):.2f}%"
        else:
            delta_display = None
        formatted_metrics.append(
            {
                "label": metric["label"],
                "value": metric["value"],
                "delta": delta_display,
                "delta_class": metric.get("delta_class", ""),
                "symbol": metric.get("symbol", ""),
                "icon": ICON_SVGS.get(metric["label"], ICON_SVGS["Total Inventory"]),
            }
        )

    reason_map = {label: Decimal("0") for label, _ in REASON_ORDER}

    def _categorize_reason(text):
        value = (text or "").lower()
        for label, keywords in REASON_ORDER:
            if any(keyword in value for keyword in keywords):
                return label
        return "slow-moving/obsolete"

    for row in inventory_rows:
        amount = _to_decimal(row.ineligibles)
        if amount <= 0:
            continue
        text = " ".join(filter(None, [(row.sub_type or ""), (row.main_type or "")]))
        reason_key = _categorize_reason(text)
        reason_map[reason_key] += amount

    ineligible_detail = []
    for label, _ in REASON_ORDER:
        amount = reason_map.get(label, Decimal("0"))
        pct = (amount / inventory_ineligible) if inventory_ineligible else Decimal("0")
        ineligible_detail.append(
            {
                "reason": label.replace("-", " ").title(),
                "amount": _format_currency(amount),
                "pct": _format_pct(pct),
            }
        )

    category_metrics = {label: {"eligible": Decimal("0"), "beginning": Decimal("0")} for label, _ in RAW_CATEGORY_DEFINITIONS}
    OTHER_LABEL = "Other items"
    category_metrics[OTHER_LABEL] = {"eligible": Decimal("0"), "beginning": Decimal("0")}

    total_beginning = Decimal("0")
    total_available = Decimal("0")
    total_ineligible_calc = Decimal("0")

    for row in inventory_rows:
        beginning = _to_decimal(row.beginning_collateral)
        available = _to_decimal(row.eligible_collateral)
        total_beginning += beginning
        total_available += available
        text = " ".join(filter(None, [(row.sub_type or ""), (row.main_type or "")])).lower()
        matched_label = None
        for label, keywords in RAW_CATEGORY_DEFINITIONS:
            if any(keyword in text for keyword in keywords):
                matched_label = label
                break
        if not matched_label:
            matched_label = OTHER_LABEL
        metrics = category_metrics.setdefault(matched_label, {"eligible": Decimal("0"), "beginning": Decimal("0")})
        metrics["eligible"] += available
        metrics["beginning"] += beginning

    cat_rows = []
    for label, _ in RAW_CATEGORY_DEFINITIONS:
        metrics = category_metrics.get(label, {"eligible": Decimal("0"), "beginning": Decimal("0")})
        beginning = metrics["beginning"]
        available = metrics["eligible"]
        ineligible = max(beginning - available, Decimal("0"))
        total_ineligible_calc += ineligible
        pct_available = available / beginning if beginning else Decimal("0")
        cat_rows.append(
            {
                "label": label,
                "total": _format_currency(beginning),
                "ineligible": _format_currency(ineligible),
                "available": _format_currency(available),
                "pct_available": _format_pct(pct_available),
            }
        )

    other_metrics = category_metrics.get(OTHER_LABEL, {"eligible": Decimal("0"), "beginning": Decimal("0")})
    other_beginning = other_metrics["beginning"]
    other_available = other_metrics["eligible"]
    other_ineligible = max(other_beginning - other_available, Decimal("0"))
    total_ineligible_calc += other_ineligible
    other_pct_available = other_available / other_beginning if other_beginning else Decimal("0")

    category_other_row = {
        "label": OTHER_LABEL.title(),
        "total": _format_currency(other_beginning),
        "ineligible": _format_currency(other_ineligible),
        "available": _format_currency(other_available),
        "pct_available": _format_pct(other_pct_available),
    }

    footer = {
        "total": _format_currency(total_beginning),
        "ineligible": _format_currency(total_ineligible_calc),
        "available": _format_currency(total_available),
        "pct_available": _format_pct(
            total_available / total_beginning if total_beginning else Decimal("0")
        ),
    }

    top10_beginning = sum(category_metrics[label]["beginning"] for label, _ in RAW_CATEGORY_DEFINITIONS)
    top10_available = sum(category_metrics[label]["eligible"] for label, _ in RAW_CATEGORY_DEFINITIONS)
    top10_row = {
        "label": "Top 10 Total",
        "total": _format_currency(top10_beginning),
        "ineligible": _format_currency(max(top10_beginning - top10_available, Decimal("0"))),
        "available": _format_currency(top10_available),
        "pct_available": _format_pct(
            (top10_available / top10_beginning) if top10_beginning else Decimal("0")
        ),
    }

    sku_rows = sorted(
        inventory_rows,
        key=lambda row: _to_decimal(row.eligible_collateral),
        reverse=True,
    )
    top25_rows = sku_rows[:25]
    raw_skus = []
    top25_amount = Decimal("0")
    top25_available = Decimal("0")
    total_amount = Decimal("0")
    total_available = Decimal("0")
    for row in sku_rows:
        total_amount += _to_decimal(row.beginning_collateral)
        total_available += _to_decimal(row.eligible_collateral)
    for row in top25_rows:
        eligible = _to_decimal(row.eligible_collateral)
        beginning = _to_decimal(row.beginning_collateral)
        pct_available = (
            (eligible / beginning) if beginning else Decimal("0")
        )
        unit_count = max(int(eligible), 0)
        value_per_unit = eligible / unit_count if unit_count else Decimal("0")
        raw_skus.append(
            {
                "sku": f"RM-{row.id}",
                "category": row.main_type or "Inventory",
                "description": row.sub_type or row.main_type or "Raw Material",
                "amount": _format_currency(beginning),
                "units": f"{unit_count:,}" if unit_count else "—",
                "per_unit": f"${value_per_unit:.2f}" if unit_count else "—",
                "pct_available": _format_pct(pct_available),
                "status": "Current" if _to_decimal(row.net_collateral) >= 0 else "At Risk",
            }
        )
        top25_amount += beginning
        top25_available += eligible
    top25_total = {
        "label": "Top 25 Total",
        "total": _format_currency(top25_amount),
        "ineligible": _format_currency(max(top25_amount - top25_available, Decimal("0"))),
        "available": _format_currency(top25_available),
        "pct_available": _format_pct(
            (top25_available / top25_amount) if top25_amount else Decimal("0")
        ),
    }

    other_amount = total_amount - top25_amount
    other_available = total_available - top25_available
    sku_other_row = {
        "label": "Other items",
        "total": _format_currency(other_amount if other_amount > 0 else Decimal("0")),
        "ineligible": _format_currency(max(other_amount - other_available, Decimal("0"))),
        "available": _format_currency(other_available if other_available > 0 else Decimal("0")),
        "pct_available": _format_pct(
            (other_available / other_amount) if other_amount else Decimal("0")
        ),
    }

    sku_grand_total = {
        "label": "Total",
        "total": _format_currency(total_amount),
        "ineligible": _format_currency(max(total_amount - total_available, Decimal("0"))),
        "available": _format_currency(total_available),
        "pct_available": _format_pct(
            (total_available / total_amount) if total_amount else Decimal("0")
        ),
    }

    def _line_values(base, length=13):
        values = []
        for idx in range(length):
            variation = math.sin(idx / 2.0) * 4
            val = max(10.0, min(100.0, base + variation))
            values.append(val)
        return values

    base_pct = float(available_pct * Decimal("100")) if isinstance(available_pct, Decimal) else 50.0
    chart_values = _line_values(base_pct)
    chart_config = {
        "rawInventoryTrend": {
            "type": "line",
            "title": "Inventory Trend",
            "labels": [
                "Feb 2024",
                "Mar 2024",
                "Apr 2024",
                "May 2024",
                "Jun 2024",
                "Jul 2024",
                "Aug 2024",
                "Sep 2024",
                "Oct 2024",
                "Nov 2024",
                "Dec 2024",
                "Jan 2025",
                "Feb 2025",
            ],
            "values": chart_values,
            "yPrefix": "%",
            "ySuffix": "",
            "yTicks": 6,
        }
    }

    return {
        "raw_materials_metrics": formatted_metrics,
        "raw_materials_ineligible_detail": ineligible_detail,
        "raw_materials_chart_config": chart_config,
        "raw_materials_chart_config_json": json.dumps(chart_config),
        "raw_materials_category_rows": cat_rows,
        "raw_materials_category_top10": top10_row,
        "raw_materials_category_other": category_other_row,
        "raw_materials_category_footer": footer,
        "raw_materials_top_skus": raw_skus,
        "raw_materials_top25_total": top25_total,
        "raw_materials_top_skus_other": sku_other_row,
        "raw_materials_top_skus_total": sku_grand_total,
    }


def _work_in_progress_context(borrower):
    base_context = {
        "work_in_progress_metrics": [],
        "work_in_progress_ineligible_detail": [],
        "work_in_progress_chart_config_json": "{}",
        "work_in_progress_category_rows": [],
        "work_in_progress_category_top10": _empty_summary_entry("Top 10 Total"),
        "work_in_progress_category_other": _empty_summary_entry("Other items"),
        "work_in_progress_category_footer": _empty_summary_entry("Total"),
        "work_in_progress_top_skus": [],
        "work_in_progress_top25_total": _empty_summary_entry("Top 25 Total"),
        "work_in_progress_top_skus_other": _empty_summary_entry("Other items"),
        "work_in_progress_top_skus_total": _empty_summary_entry("Total"),
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    wip_rows = _filter_inventory_rows_by_key(state, "work_in_progress")
    if not wip_rows:
        return base_context

    total_beginning = Decimal("0")
    total_available = Decimal("0")
    total_ineligible = Decimal("0")
    for row in wip_rows:
        beginning = _to_decimal(row.beginning_collateral)
        eligible = _to_decimal(row.eligible_collateral)
        total_beginning += beginning
        total_available += eligible
        total_ineligible += max(beginning - eligible, Decimal("0"))

    available_pct = (total_available / total_beginning) if total_beginning else Decimal("0")
    available_delta = available_pct - Decimal("0.5")

    metric_defs = [
        {
            "label": "Total Inventory",
            "value": _format_currency(total_beginning),
            "delta": -abs(available_delta * Decimal("100")) if total_beginning else None,
            "delta_class": "danger",
            "symbol": "▼",
        },
        {
            "label": "Ineligible Inventory",
            "value": _format_currency(total_ineligible),
            "delta": -abs(available_delta * Decimal("100")) if total_ineligible else None,
            "delta_class": "danger",
            "symbol": "▼",
        },
        {
            "label": "Available Inventory",
            "value": _format_pct(available_pct),
            "delta": available_delta * Decimal("100"),
            "delta_class": "success" if available_delta >= 0 else "danger",
            "symbol": "▲" if available_delta >= 0 else "▼",
        },
    ]

    formatted_metrics = []
    for metric in metric_defs:
        delta = metric.get("delta")
        if delta is not None:
            delta_display = f"{abs(delta):.2f}%"
        else:
            delta_display = None
        formatted_metrics.append(
            {
                "label": metric["label"],
                "value": metric["value"],
                "delta": delta_display,
                "delta_class": metric.get("delta_class", ""),
                "symbol": metric.get("symbol", ""),
                "icon": ICON_SVGS.get(metric["label"], ICON_SVGS["Total Inventory"]),
            }
        )

    reason_map = {label: Decimal("0") for label, _ in REASON_ORDER}
    for row in wip_rows:
        amount = _to_decimal(row.ineligibles)
        if amount <= 0:
            continue
        text = " ".join(filter(None, [(row.sub_type or ""), (row.main_type or "")]))
        for label, keywords in REASON_ORDER:
            if any(keyword in text.lower() for keyword in keywords):
                reason_map[label] += amount
                break

    ineligible_detail = []
    for label, _ in REASON_ORDER:
        amount = reason_map.get(label, Decimal("0"))
        pct = (amount / total_ineligible) if total_ineligible else Decimal("0")
        ineligible_detail.append(
            {
                "reason": label.replace("-", " ").title(),
                "amount": _format_currency(amount),
                "pct": _format_pct(pct),
            }
        )

    category_groups = {}
    for row in wip_rows:
        key = (row.sub_type or row.main_type or "Other").strip() or "Other"
        label = key.title()
        if label not in category_groups:
            category_groups[label] = {"total": Decimal("0"), "available": Decimal("0")}
        beginning = _to_decimal(row.beginning_collateral)
        eligible = _to_decimal(row.eligible_collateral)
        category_groups[label]["total"] += beginning
        category_groups[label]["available"] += eligible

    category_rows = []
    for label, metrics in category_groups.items():
        total = metrics["total"]
        available = metrics["available"]
        ineligible = max(total - available, Decimal("0"))
        pct_available = available / total if total else Decimal("0")
        category_rows.append(
            {
                "label": label,
                "total": _format_currency(total),
                "ineligible": _format_currency(ineligible),
                "available": _format_currency(available),
                "pct_available": _format_pct(pct_available),
                "_total_value": total,
                "_available_value": available,
            }
        )

    category_rows.sort(key=lambda item: item.get("_total_value", Decimal("0")), reverse=True)

    top10_slice = category_rows[:10]
    top10_total = sum(item.get("_total_value", Decimal("0")) for item in top10_slice)
    top10_available = sum(item.get("_available_value", Decimal("0")) for item in top10_slice)
    top10_row = {
        "label": "Top 10 Total",
        "total": _format_currency(top10_total),
        "ineligible": _format_currency(max(top10_total - top10_available, Decimal("0"))),
        "available": _format_currency(top10_available),
        "pct_available": _format_pct(
            (top10_available / top10_total) if top10_total else Decimal("0")
        ),
    }

    other_total = sum(item.get("_total_value", Decimal("0")) for item in category_rows[10:])
    other_available = sum(item.get("_available_value", Decimal("0")) for item in category_rows[10:])
    category_other = {
        "label": "Other items",
        "total": _format_currency(other_total),
        "ineligible": _format_currency(max(other_total - other_available, Decimal("0"))),
        "available": _format_currency(other_available),
        "pct_available": _format_pct(
            (other_available / other_total) if other_total else Decimal("0")
        ),
    }

    footer = {
        "total": _format_currency(total_beginning),
        "ineligible": _format_currency(total_ineligible),
        "available": _format_currency(total_available),
        "pct_available": _format_pct(
            total_available / total_beginning if total_beginning else Decimal("0")
        ),
    }

    sku_rows = sorted(
        wip_rows,
        key=lambda row: _to_decimal(row.eligible_collateral),
        reverse=True,
    )
    top25_rows = sku_rows[:25]
    raw_skus = []
    top25_amount = Decimal("0")
    top25_available = Decimal("0")
    sku_total_amount = Decimal("0")
    sku_total_available = Decimal("0")
    for row in sku_rows:
        sku_total_amount += _to_decimal(row.beginning_collateral)
        sku_total_available += _to_decimal(row.eligible_collateral)
    for row in top25_rows:
        eligible = _to_decimal(row.eligible_collateral)
        beginning = _to_decimal(row.beginning_collateral)
        pct_available = (eligible / beginning) if beginning else Decimal("0")
        units = max(int(eligible), 0)
        value_per_unit = eligible / units if units else Decimal("0")
        raw_skus.append(
            {
                "sku": f"RM-{row.id}",
                "category": row.main_type or "Inventory",
                "description": row.sub_type or row.main_type or "Work-in-Progress",
                "amount": _format_currency(beginning),
                "units": f"{units:,}" if units else "—",
                "per_unit": f"${value_per_unit:.2f}" if units else "—",
                "pct_available": _format_pct(pct_available),
                "status": "Current" if _to_decimal(row.net_collateral) >= 0 else "At Risk",
            }
        )
        top25_amount += beginning
        top25_available += eligible

    top25_total = {
        "label": "Top 25 Total",
        "total": _format_currency(top25_amount),
        "ineligible": _format_currency(max(top25_amount - top25_available, Decimal("0"))),
        "available": _format_currency(top25_available),
        "pct_available": _format_pct(
            (top25_available / top25_amount) if top25_amount else Decimal("0")
        ),
    }

    sku_other_row = {
        "label": "Other items",
        "total": _format_currency(max(sku_total_amount - top25_amount, Decimal("0"))),
        "ineligible": _format_currency(
            max(max(sku_total_amount - top25_amount, Decimal("0")) - (sku_total_available - top25_available), Decimal("0"))
        ),
        "available": _format_currency(max(sku_total_available - top25_available, Decimal("0"))),
        "pct_available": _format_pct(
            ((sku_total_available - top25_available) / max(sku_total_amount - top25_amount, Decimal("1")))
            if (sku_total_amount - top25_amount)
            else Decimal("0")
        ),
    }

    sku_grand_total = {
        "label": "Total",
        "total": _format_currency(sku_total_amount),
        "ineligible": _format_currency(max(sku_total_amount - sku_total_available, Decimal("0"))),
        "available": _format_currency(sku_total_available),
        "pct_available": _format_pct(
            (sku_total_available / sku_total_amount) if sku_total_amount else Decimal("0")
        ),
    }

    def _line_values(base, length=13):
        values = []
        for idx in range(length):
            variation = math.sin(idx / 2.0) * 4
            val = max(10.0, min(100.0, base + variation))
            values.append(val)
        return values

    base_pct = float(available_pct * Decimal("100")) if isinstance(available_pct, Decimal) else 50.0
    chart_values = _line_values(base_pct)
    chart_config = {
        "workInventoryTrend": {
            "type": "line",
            "title": "Inventory Trend",
            "labels": [
                "May 2019",
                "Jun 2019",
                "Jul 2019",
                "Aug 2019",
                "Sep 2019",
                "Oct 2019",
                "Nov 2019",
                "Dec 2019",
                "Jan 2020",
                "Feb 2020",
                "Mar 2020",
                "Apr 2020",
                "May 2020",
            ],
            "values": chart_values,
            "yPrefix": "%",
            "ySuffix": "",
            "yTicks": 6,
        }
    }

    return {
        "work_in_progress_metrics": formatted_metrics,
        "work_in_progress_ineligible_detail": ineligible_detail,
        "work_in_progress_chart_config_json": json.dumps(chart_config),
        "work_in_progress_category_rows": category_rows,
        "work_in_progress_category_top10": top10_row,
        "work_in_progress_category_other": category_other,
        "work_in_progress_category_footer": footer,
        "work_in_progress_top_skus": raw_skus,
        "work_in_progress_top25_total": top25_total,
        "work_in_progress_top_skus_other": sku_other_row,
        "work_in_progress_top_skus_total": sku_grand_total,
    }


DEFAULT_OTHER_COLLATERAL_CHART = {
    "title": "Value Trend",
    "labels": [
        "May 23",
        "Jun 23",
        "Jul 23",
        "Aug 23",
        "Sep 23",
        "Oct 23",
        "Nov 23",
        "Dec 23",
        "Jan 24",
        "Feb 24",
        "Mar 24",
    ],
    "estimated": [32, 48, 58, 52, 46, 12, 32, 34, 35, 38, 38],
    "appraisal": [62, 66, 69, 68, 67, 43, 50, 54, 58, 64, 70],
}


def _other_collateral_context(borrower):
    base_context = {
        "other_collateral_value_monitor": [],
        "other_collateral_value_trend_config": DEFAULT_OTHER_COLLATERAL_CHART.copy(),
        "other_collateral_value_analysis_rows": [],
        "other_collateral_asset_rows": [],
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    latest_report = state["latest_report"]
    equipment_rows = list(
        MachineryEquipmentRow.objects.filter(report=latest_report).order_by("id")
    )
    if not equipment_rows:
        return base_context

    total_fmv = sum(_to_decimal(row.fair_market_value) for row in equipment_rows)
    total_olv = sum(_to_decimal(row.orderly_liquidation_value) for row in equipment_rows)
    estimated_fmv_total = total_fmv * Decimal("0.97")
    estimated_olv_total = total_olv * Decimal("0.95")

    previous_report = (
        BorrowerReport.objects.filter(borrower=borrower)
        .exclude(pk=latest_report.pk)
        .order_by("-report_date")
        .first()
    )
    prev_total_fmv = None
    prev_total_olv = None
    if previous_report:
        prev_rows = MachineryEquipmentRow.objects.filter(report=previous_report)
        if prev_rows:
            prev_total_fmv = sum(_to_decimal(row.fair_market_value) for row in prev_rows)
            prev_total_olv = sum(_to_decimal(row.orderly_liquidation_value) for row in prev_rows)

    def _delta_payload(label, current, previous, fallback):
        delta = _format_delta(current, previous)
        if not delta and fallback is not None:
            delta = _format_delta(current, fallback)
        if not delta:
            return None
        return {
            "label": label,
            "symbol": delta["sign"],
            "value": delta["value"],
            "delta_class": "good" if delta["is_positive"] else "",
        }

    delta_fmv = _delta_payload("Fair Market Value", total_fmv, prev_total_fmv, estimated_fmv_total)
    delta_olv = _delta_payload(
        "Orderly Liquidation Value", total_olv, prev_total_olv, estimated_olv_total
    )

    value_monitor_cards = [
        {
            "title": "Appraised Values",
            "big": "Fair Market Value",
            "rows": [
                {"label": "Fair Market Value", "value": _format_currency(total_fmv)},
                {"label": "Orderly Liquidation Value", "value": _format_currency(total_olv)},
            ],
            "info": "i",
            "deltas": [],
        },
        {
            "title": "Estimated Values",
            "big": "Fair Market Value",
            "rows": [
                {"label": "Fair Market Value", "value": _format_currency(estimated_fmv_total)},
                {"label": "Orderly Liquidation Value", "value": _format_currency(estimated_olv_total)},
            ],
            "info": "i",
            "deltas": [],
        },
        {
            "title": "Change in Value",
            "big": "Fair Market Value",
            "rows": [],
            "info": "i",
            "deltas": [delta for delta in (delta_fmv, delta_olv) if delta],
        },
    ]

    value_analysis_rows = []
    asset_rows = []
    for row in equipment_rows:
        fmv = _to_decimal(row.fair_market_value)
        olv = _to_decimal(row.orderly_liquidation_value)
        estimated_fmv = fmv * Decimal("0.98")
        estimated_olv = olv * Decimal("0.96")
        variance_amount = fmv - estimated_fmv
        variance_pct = (
            variance_amount / estimated_fmv if estimated_fmv else Decimal("0")
        )
        value_analysis_rows.append(
            {
                "id": row.id,
                "equipment_type": row.equipment_type or "—",
                "manufacturer": row.manufacturer or "—",
                "fmv": _format_currency(fmv),
                "olv": _format_currency(olv),
                "estimated_fmv": _format_currency(estimated_fmv),
                "estimated_olv": _format_currency(estimated_olv),
                "variance_amount": _format_currency(variance_amount),
                "variance_pct": _format_pct(variance_pct),
            }
        )
        asset_rows.append(
            {
                "id": row.id,
                "equipment_type": row.equipment_type or "—",
                "manufacturer": row.manufacturer or "—",
                "serial_number": _safe_str(row.serial_number),
                "year": row.year or "—",
                "condition": row.condition or "—",
                "fmv": _format_currency(fmv),
                "olv": _format_currency(olv),
            }
        )

    chart_reports = BorrowerReport.objects.filter(borrower=borrower).order_by("report_date")
    labels = []
    estimated_series = []
    appraisal_series = []
    for report in chart_reports:
        rows = MachineryEquipmentRow.objects.filter(report=report)
        if not rows:
            continue
        report_fmv = sum(_to_decimal(row.fair_market_value) for row in rows)
        report_olv = sum(_to_decimal(row.orderly_liquidation_value) for row in rows)
        if report_fmv == 0 and report_olv == 0:
            continue
        report_date = report.report_date or report.created_at
        if report_date:
            label = report_date.strftime("%b %y")
        else:
            label = f"Report {report.id}"
        labels.append(label)
        appraisal_series.append(float(report_olv))
        estimated_series.append(float(report_olv * Decimal("0.96")))

    max_points = 12
    if len(labels) > max_points:
        start = len(labels) - max_points
        labels = labels[start:]
        estimated_series = estimated_series[start:]
        appraisal_series = appraisal_series[start:]

    chart_config = DEFAULT_OTHER_COLLATERAL_CHART.copy()
    if labels:
        chart_config = {
            "title": "Value Trend",
            "labels": labels,
            "estimated": [float(v) for v in estimated_series],
            "appraisal": [float(v) for v in appraisal_series],
        }

    return {
        "other_collateral_value_monitor": value_monitor_cards,
        "other_collateral_value_trend_config": chart_config,
        "other_collateral_value_analysis_rows": value_analysis_rows,
        "other_collateral_asset_rows": asset_rows,
    }


def _format_delta(current, previous):
    if previous is None or previous == 0:
        return None
    prev = Decimal(previous)
    curr = Decimal(current)
    if prev == 0:
        return None
    diff = (curr - prev) / prev * Decimal("100")
    sign = "▲" if diff >= 0 else "▼"
    return {
        "value": f"{abs(diff):.2f}%",
        "sign": sign,
        "is_positive": diff >= 0,
    }


def _build_liquidation_metrics(current, previous=None):
    if not current:
        return []

    metrics = []
    gross_recovery = _to_decimal(current.total_inventory)
    gross_previous = _to_decimal(previous.total_inventory if previous else 0)
    gross_delta = _format_delta(gross_recovery, gross_previous)
    metrics.append(
        {
            "label": "Gross Recovery",
            "value": _format_currency(gross_recovery),
            "delta": gross_delta["value"] if gross_delta else None,
            "symbol": gross_delta["sign"] if gross_delta else "",
            "delta_class": "success" if gross_delta and gross_delta["is_positive"] else "danger",
            "icon": ICON_SVGS["Total Inventory"],
        }
    )

    units = _to_decimal(current.available_inventory if current else 0)
    units_prev = _to_decimal(previous.available_inventory if previous else 0)
    units_delta = _format_delta(units, units_prev)
    metrics.append(
        {
            "label": "Gross Recovery Units",
            "value": f"{int(units)}" if units else "0",
            "delta": units_delta["value"] if units_delta else None,
            "symbol": units_delta["sign"] if units_delta else "",
            "delta_class": "success" if units_delta and units_delta["is_positive"] else "danger",
            "icon": ICON_SVGS["Available Inventory"],
        }
    )

    liquidation_pct = _to_decimal(current.ineligible_pct_of_inventory if current else 0)
    liquidation_prev = _to_decimal(previous.ineligible_pct_of_inventory if previous else 0)
    liquidation_delta = _format_delta(liquidation_pct, liquidation_prev)
    metrics.append(
        {
            "label": "Liquidation Costs",
            "value": _format_pct(liquidation_pct),
            "delta": liquidation_delta["value"] if liquidation_delta else None,
            "symbol": liquidation_delta["sign"] if liquidation_delta else "",
            "delta_class": "success" if liquidation_delta and liquidation_delta["is_positive"] else "danger",
            "icon": ICON_SVGS["Ineligible Inventory"],
        }
    )

    net_pct = Decimal("0")
    net_prev_pct = Decimal("0")
    if current and current.total_inventory:
        net_pct = _to_decimal(current.available_inventory) / _to_decimal(current.total_inventory)
    if previous and previous.total_inventory:
        net_prev_pct = _to_decimal(previous.available_inventory) / _to_decimal(previous.total_inventory)
    net_delta = _format_delta(net_pct, net_prev_pct)
    metrics.append(
        {
            "label": "Net Recovery",
            "value": _format_pct(net_pct),
            "delta": net_delta["value"] if net_delta else None,
            "symbol": net_delta["sign"] if net_delta else "",
            "delta_class": "success" if net_delta and net_delta["is_positive"] else "danger",
            "icon": ICON_SVGS["Available Inventory"],
        }
    )

    return metrics


def _filter_rows_by_keyword(rows, keyword):
    keyword = keyword.lower()
    return [row for row in rows if (row.main_type or "").lower().find(keyword) >= 0]


def _build_liquidation_category_table(rows, max_rows=5):
    total = sum((_to_decimal(row.beginning_collateral) or Decimal("0")) for row in rows)
    sorted_rows = sorted(rows, key=lambda row: _to_decimal(row.beginning_collateral), reverse=True)
    table = []
    aggregated = Decimal("0")
    last_gr_pct = "0%"
    for idx, row in enumerate(sorted_rows[:max_rows]):
        cost = _to_decimal(row.beginning_collateral)
        eligible = _to_decimal(row.eligible_collateral)
        pct_cost = cost / total if total else Decimal("0")
        gr_pct = eligible / cost if cost else Decimal("0")
        table.append(
            {
                "rank": idx + 1,
                "cost": _format_currency(cost),
                "percent": f"{pct_cost * 100:.0f}%",
                "gr_pct": _format_pct(gr_pct),
            }
        )
        aggregated += cost
        last_gr_pct = table[-1]["gr_pct"]
    other_cost = total - aggregated
    if other_cost > 0:
      table.append(
        {
          "rank": "Other",
          "cost": _format_currency(other_cost),
          "percent": f"{(other_cost / total * 100):.0f}%" if total else "0%",
          "gr_pct": last_gr_pct,
        }
      )
    table.append(
      {
        "rank": "Total",
            "cost": _format_currency(total),
            "percent": "100%",
            "gr_pct": _format_pct(sum(_to_decimal(r.eligible_collateral) for r in rows) / total if total else Decimal("0")),
        }
    )
    return table


def _liquidation_model_context(borrower):
    base_context = {
        "liquidation_summary_metrics": [],
        "liquidation_expense_groups": [],
        "liquidation_finished_rows": [],
        "liquidation_finished_footer": {
            "cost": "—",
            "selling": "—",
            "gross": "—",
            "pct_cost": "—",
            "pct_sp": "—",
            "wos": "—",
            "gr_pct": "—",
        },
        "fg_gross_recovery_history_rows": [],
        "fg_gross_recovery_history_totals": {
            "cost": "—",
            "selling": "—",
            "gross": "—",
            "pct_cost": "—",
            "pct_sp": "—",
            "wos": "—",
            "gr_pct": "—",
        },
        "liquidation_category_tables": {"raw_materials": [], "work_in_progress": []},
        "liquidation_net_orderly_rows": [],
        "liquidation_net_orderly_footer": {
            "label": "Net Orderly Liquidated Value",
            "fg": "—",
            "fg_pct": "—",
            "rm": "—",
            "rm_pct": "—",
            "wip": "—",
            "wip_pct": "—",
            "total": "—",
            "total_pct": "—",
        },
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    latest_report = state["latest_report"]
    metrics_rows = list(
        FGInventoryMetricsRow.objects.filter(borrower=borrower).order_by("-as_of_date")
    )
    current_metrics = metrics_rows[0] if metrics_rows else None
    previous_metrics = metrics_rows[1] if len(metrics_rows) > 1 else None

    summary_metrics = _build_liquidation_metrics(current_metrics, previous_metrics)

    fg_expenses = (
        FGIneligibleDetailRow.objects.filter(borrower=borrower).order_by("-date").first()
    )
    groups = []
    if fg_expenses:
        reason_fields = [
            ("Payroll Expenses", ["slow_moving_obsolete", "aged"]),
            ("Opportunity Expenses", ["consigned", "in_transit", "off_site"]),
            ("Liquidation Expenses", ["damaged_non_saleable"]),
        ]
        for title, fields in reason_fields:
            items = []
            total_amount = Decimal("0")
            for field in fields:
                value = getattr(fg_expenses, field, None)
                amount = _to_decimal(value)
                total_amount += amount
                items.append(
                    {
                        "label": field.replace("_", " ").title(),
                        "amount": _format_currency(amount),
                    }
                )
            groups.append(
                {
                    "title": title,
                    "items": items,
                    "total": _format_currency(total_amount),
                }
            )

    finished_rows = [
        row
        for row in state["inventory_rows"]
        if row.main_type and "finished" in (row.main_type or "").lower()
    ]
    liquidation_finished_rows = []
    for row in sorted(finished_rows, key=lambda r: _to_decimal(r.eligible_collateral), reverse=True)[:5]:
        cost = _to_decimal(row.beginning_collateral)
        eligible = _to_decimal(row.eligible_collateral)
        selling = cost + (_to_decimal(row.reserves) or Decimal("0")) + (_to_decimal(row.pre_reserve_collateral) or Decimal("0"))
        pct_cost = eligible / cost if cost else Decimal("0")
        wos = (_to_decimal(row.nolv_pct) or Decimal("0")) * Decimal("365") / Decimal("7")
        liquidation_finished_rows.append(
            {
                "vendor": row.sub_type or f"{row.main_type} {row.id}",
                "cost": _format_currency(cost),
                "selling": _format_currency(selling),
                "gross": _format_currency(eligible),
                "pct_cost": _format_pct(pct_cost),
                "pct_sp": _format_pct(pct_cost),
                "wos": f"{int(wos):,}",
                "gr_pct": _format_pct(pct_cost),
            }
        )

    finished_footer = {
        "cost": _format_currency(sum(_to_decimal(row.beginning_collateral) for row in finished_rows)),
        "selling": _format_currency(sum((_to_decimal(row.beginning_collateral) or Decimal("0")) + (_to_decimal(row.reserves) or Decimal("0")) + (_to_decimal(row.pre_reserve_collateral) or Decimal("0")) for row in finished_rows)),
        "gross": _format_currency(sum(_to_decimal(row.eligible_collateral) for row in finished_rows)),
        "pct_cost": "90%",
        "pct_sp": "85%",
        "wos": f"{int(sum((_to_decimal(row.nolv_pct) or Decimal('0')) for row in finished_rows) * Decimal('52')):,}",
        "gr_pct": _format_pct(
            sum(_to_decimal(row.eligible_collateral) for row in finished_rows)
            / sum(_to_decimal(row.beginning_collateral) for row in finished_rows)
            if finished_rows
            else Decimal("0")
        ),
    }

    raw_rows = [
        row
        for row in state["inventory_rows"]
        if row.main_type and "raw" in (row.main_type or "").lower()
    ]
    wip_rows = [
        row
        for row in state["inventory_rows"]
        if row.main_type and "work" in (row.main_type or "").lower()
    ]

    category_tables = {
        "raw_materials": _build_liquidation_category_table(raw_rows),
        "work_in_progress": _build_liquidation_category_table(wip_rows),
    }
    category_tabs = [
        {"key": "raw_materials", "label": "Raw Material", "rows": category_tables["raw_materials"]},
        {"key": "work_in_progress", "label": "Work-In-Process", "rows": category_tables["work_in_progress"]},
    ]

    categories = state["category_metrics"]
    def _cat_value(key):
        metrics = categories.get(key, {})
        return metrics.get("beginning", Decimal("0")), metrics.get("eligible", Decimal("0"))

    finished_totals = _cat_value("finished_goods")
    raw_totals = _cat_value("raw_materials")
    wip_totals = _cat_value("work_in_progress")
    scrap_rows = [
        row
        for row in state["inventory_rows"]
        if "scrap" in (row.sub_type or "").lower() or "scrap" in (row.main_type or "").lower()
    ]
    scrap_total = sum(_to_decimal(row.beginning_collateral) for row in scrap_rows)
    scrap_recovery = sum(_to_decimal(row.eligible_collateral) for row in scrap_rows)

    total_available_cost = (
        finished_totals[0] + raw_totals[0] + wip_totals[0] + scrap_total
    )
    total_gross_recovery = (
        finished_totals[1] + raw_totals[1] + wip_totals[1] + scrap_recovery
    )

    net_rows = [
        {
            "label": "Available Inventory at Cost",
            "fg": _format_currency(finished_totals[0]),
            "fg_pct": "",
            "rm": _format_currency(raw_totals[0]),
            "rm_pct": "",
            "wip": _format_currency(wip_totals[0]),
            "wip_pct": "",
            "total": _format_currency(total_available_cost),
            "total_pct": "",
        },
        {
            "label": "Gross Recovery",
            "fg": _format_currency(finished_totals[1]),
            "fg_pct": "",
            "rm": _format_currency(raw_totals[1]),
            "rm_pct": "",
            "wip": _format_currency(wip_totals[1]),
            "wip_pct": "",
            "total": _format_currency(total_gross_recovery),
            "total_pct": "",
        },
    ]

    def _add_cost_row(label, factor):
        pct_display = f"-{factor * 100:.1f}%"
        return {
            "label": label,
            "fg": _format_currency(finished_totals[0] * factor),
            "fg_pct": pct_display,
            "rm": _format_currency(raw_totals[0] * factor),
            "rm_pct": pct_display,
            "wip": _format_currency(wip_totals[0] * factor),
            "wip_pct": pct_display,
            "total": _format_currency(total_available_cost * factor),
            "total_pct": pct_display,
        }

    net_rows.append(_add_cost_row("Liquidation / Sales Fees", Decimal("0.024")))
    net_rows.append(_add_cost_row("Storage / Handling", Decimal("0.016")))
    net_rows.append(_add_cost_row("Opportunity / Utilization Costs", Decimal("0.010")))
    net_rows.append(_add_cost_row("Transport / Logistics", Decimal("0.012")))

    net_footer = {
        "label": "Net Orderly Liquidated Value",
        "fg": _format_currency(finished_totals[1] * Decimal("0.8")),
        "fg_pct": "54.8%",
        "rm": _format_currency(raw_totals[1] * Decimal("0.8")),
        "rm_pct": "54.8%",
        "wip": _format_currency(wip_totals[1] * Decimal("0.8")),
        "wip_pct": "54.8%",
        "total": _format_currency(total_gross_recovery * Decimal("0.8")),
        "total_pct": "54.8%",
    }

    nolv_entries = list(NOLVTableRow.objects.filter(report=latest_report).order_by("id"))
    liquidation_net_orderly_rows = net_rows
    liquidation_net_orderly_footer = net_footer
    if nolv_entries:
        total_fg = Decimal("0")
        total_rm = Decimal("0")
        total_wip = Decimal("0")
        total_total = Decimal("0")
        dynamic_rows = []
        for entry in nolv_entries:
            fg_value = _to_decimal(entry.fg_usd)
            rm_value = _to_decimal(entry.rm_usd)
            wip_value = _to_decimal(entry.wip_usd)
            total_value = _to_decimal(entry.total_usd)
            total_fg += fg_value
            total_rm += rm_value
            total_wip += wip_value
            total_total += total_value
            dynamic_rows.append(
                {
                    "label": _safe_str(entry.line_item),
                    "fg": _format_currency(entry.fg_usd),
                    "fg_pct": _format_pct(entry.fg_pct_cost),
                    "rm": _format_currency(entry.rm_usd),
                    "rm_pct": _format_pct(entry.rm_pct_cost),
                    "wip": _format_currency(entry.wip_usd),
                    "wip_pct": _format_pct(entry.wip_pct_cost),
                    "total": _format_currency(entry.total_usd),
                    "total_pct": _format_pct(entry.total_pct_cost),
                }
            )
        fg_pct_value = total_fg / total_total if total_total else None
        rm_pct_value = total_rm / total_total if total_total else None
        wip_pct_value = total_wip / total_total if total_total else None
        total_pct_value = Decimal("1") if total_total else None
        liquidation_net_orderly_rows = dynamic_rows
        liquidation_net_orderly_footer = {
            "label": "Net Orderly Liquidated Value",
            "fg": _format_currency(total_fg),
            "fg_pct": _format_pct(fg_pct_value),
            "rm": _format_currency(total_rm),
            "rm_pct": _format_pct(rm_pct_value),
            "wip": _format_currency(total_wip),
            "wip_pct": _format_pct(wip_pct_value),
            "total": _format_currency(total_total),
            "total_pct": _format_pct(total_pct_value),
        }
    history_rows = []
    total_cost = Decimal("0")
    total_selling = Decimal("0")
    total_gross = Decimal("0")
    for history_row in FGGrossRecoveryHistoryRow.objects.filter(borrower=borrower).order_by("id"):
        raw_cost = history_row.cost
        raw_selling = history_row.selling_price
        raw_gross = history_row.gross_recovery
        cost = _to_decimal(raw_cost)
        selling = _to_decimal(raw_selling)
        gross = _to_decimal(raw_gross)
        total_cost += cost
        total_selling += selling
        total_gross += gross
        if history_row.wos is not None:
            wos_value = _to_decimal(history_row.wos)
            wos_display = f"{wos_value:,.1f}"
        else:
            wos_display = "—"
        history_rows.append(
            {
                "date": _format_date(history_row.as_of_date),
                "division": _safe_str(history_row.division),
                "category": _safe_str(history_row.category),
                "type": _safe_str(history_row.type),
                "cost": _format_currency(raw_cost),
                "selling": _format_currency(raw_selling),
                "gross": _format_currency(raw_gross),
                "pct_cost": _format_pct(history_row.pct_of_cost),
                "pct_sp": _format_pct(history_row.pct_of_sp),
                "wos": wos_display,
                "gr_pct": _format_pct(history_row.gm_pct),
            }
        )
    history_totals = {
        "cost": "—",
        "selling": "—",
        "gross": "—",
        "pct_cost": "—",
        "pct_sp": "—",
        "wos": "—",
        "gr_pct": "—",
    }
    if history_rows:
        pct_cost_value = total_gross / total_cost if total_cost else None
        pct_sp_value = total_gross / total_selling if total_selling else None
        history_totals = {
            "cost": _format_currency(total_cost),
            "selling": _format_currency(total_selling),
            "gross": _format_currency(total_gross),
            "pct_cost": _format_pct(pct_cost_value),
            "pct_sp": _format_pct(pct_sp_value),
            "wos": "—",
            "gr_pct": "—",
        }

    return {
        "liquidation_summary_metrics": summary_metrics,
        "liquidation_expense_groups": groups,
        "liquidation_finished_rows": liquidation_finished_rows,
        "liquidation_finished_footer": finished_footer,
        "liquidation_category_tables": category_tables,
        "liquidation_category_tabs": category_tabs,
        "liquidation_net_orderly_rows": liquidation_net_orderly_rows,
        "liquidation_net_orderly_footer": liquidation_net_orderly_footer,
        "fg_gross_recovery_history_rows": history_rows,
        "fg_gross_recovery_history_totals": history_totals,
    }
