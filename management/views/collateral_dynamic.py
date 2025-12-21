import json
import math
from collections import OrderedDict
from datetime import date, timedelta

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
    FGInlineExcessByCategoryRow,
    FGGrossRecoveryHistoryRow,
    HistoricalTop20SKUsRow,
    ForecastRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    NOLVTableRow,
    RiskSubfactorsRow,
    SalesGMTrendRow,
)
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
    _format_date,
    _safe_str,
    _to_decimal,
    get_preferred_borrower,
)


@login_required(login_url="login")
def collateral_dynamic_view(request):
    borrower = get_preferred_borrower(request)

    section = request.GET.get("section", "accounts_receivable")
    allowed_sections = {"overview", "accounts_receivable", "inventory"}
    if section not in allowed_sections:
        section = "accounts_receivable"

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

    finished_goals_range = request.GET.get("finished_goals_range", "today")
    finished_goals_division = request.GET.get(
        "finished_goals_division",
        request.GET.get("finished_goals_view", "all"),
    )

    context = {
        "borrower_summary": _build_borrower_summary(borrower),
        "active_section": section,
        "inventory_tab": inventory_tab,
        "active_tab": "collateral_dynamic",
        **_inventory_context(borrower),
        **_accounts_receivable_context(borrower),
        **_finished_goals_context(borrower, finished_goals_range, finished_goals_division),
        **_raw_materials_context(borrower),
        **_work_in_progress_context(borrower),
        **_other_collateral_context(borrower),
        **_liquidation_model_context(borrower),
    }
    return render(request, "collateral_dynamic/accounts_receivable.html", context)


@login_required(login_url="login")
def collateral_static_view(request):
    borrower = get_preferred_borrower(request)
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

            label_value = row.period or row.as_of_date or f"Week {row.id}"
            values.append(
                {
                    "label": label_value,
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

    def _trim_axis_value(value):
        text = f"{value:.1f}"
        return text.rstrip("0").rstrip(".")

    def _format_axis_value(value):
        val = float(value)
        abs_val = abs(val)
        if abs_val >= 1_000_000_000:
            return f"${_trim_axis_value(val / 1_000_000_000)}B"
        if abs_val >= 1_000_000:
            return f"${_trim_axis_value(val / 1_000_000)}M"
        if abs_val >= 1_000:
            return f"${_trim_axis_value(val / 1_000)}k"
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

    def _build_chart_bars(rows, width=620, height=280, left=60, right=40, top=40, bottom=60):
        if not rows:
            return [], [], [], []
        max_value = max(
            [_to_decimal(row.get("collections")) for row in rows]
            + [_to_decimal(row.get("disbursements")) for row in rows]
            + [Decimal("0")]
        )
        if max_value <= 0:
            max_value = Decimal("1")
        max_float = float(max_value)
        magnitude = 10 ** max(0, int(math.floor(math.log10(max_float))) - 1)
        step = magnitude if magnitude else 1
        axis_max = math.ceil(max_float / step) * step if step else max_float
        if axis_max <= 0:
            axis_max = 1
        plot_width = width - left - right
        plot_height = height - top - bottom
        group_count = len(rows)
        group_width = plot_width / max(group_count, 1)
        bar_gap = 4
        bar_width = min(16, max(6, (group_width - bar_gap) / 2))
        baseline_y = top + plot_height
        collections_bars = []
        disbursement_bars = []
        label_points = []
        ticks = []
        tick_count = 6
        for idx in range(tick_count):
            ratio = idx / (tick_count - 1)
            value = axis_max * (1 - ratio)
            y = top + plot_height * ratio
            ticks.append({"y": y, "label": _format_axis_value(value)})
        for idx, row in enumerate(rows):
            group_x = left + idx * group_width
            total_bar_width = bar_width * 2 + bar_gap
            start_x = group_x + max(0, (group_width - total_bar_width) / 2)
            collections_val = _to_decimal(row.get("collections"))
            disbursement_val = _to_decimal(row.get("disbursements"))
            collections_height = float(collections_val / Decimal(str(axis_max))) * plot_height
            disbursement_height = float(disbursement_val / Decimal(str(axis_max))) * plot_height
            label_text = _format_chart_label(row.get("label"))
            collections_bars.append(
                {
                    "x": start_x,
                    "y": baseline_y - collections_height,
                    "width": bar_width,
                    "height": collections_height,
                    "label": label_text,
                    "value": _format_money(collections_val),
                }
            )
            disbursement_bars.append(
                {
                    "x": start_x + bar_width + bar_gap,
                    "y": baseline_y - disbursement_height,
                    "width": bar_width,
                    "height": disbursement_height,
                    "label": label_text,
                    "value": _format_money(disbursement_val),
                }
            )
            label_points.append(
                {
                    "x": start_x + bar_width + bar_gap / 2,
                    "text": label_text,
                }
            )
        return collections_bars, disbursement_bars, label_points, ticks

    def _build_liquidity_chart(series_values, labels, width=800, height=280, left=70, right=60, top=40, bottom=40):
        if not series_values or not labels:
            return {"series": [], "labels": [], "ticks": []}
        all_values = [value for series in series_values for value in series]
        max_value = max(all_values + [0.0])
        if max_value <= 0:
            max_value = 1.0
        tick_count = 5
        step_value = _nice_step(max_value / (tick_count - 1))
        axis_max = step_value * (tick_count - 1)
        if axis_max <= 0:
            axis_max = max_value
        total_width = width - left - right
        step_x = total_width / max(1, len(labels) - 1)
        chart_height = height - top - bottom
        ticks = []
        for idx in range(tick_count):
            value = axis_max * (tick_count - 1 - idx) / (tick_count - 1)
            y = top + (chart_height * idx / (tick_count - 1))
            ticks.append({"y": round(y, 1), "label": _format_axis_value(value)})
        label_points = []
        for idx, label in enumerate(labels):
            label_points.append({"x": round(left + idx * step_x, 1), "text": label})
        series_output = []
        for series in series_values:
            points = []
            dots = []
            for idx, value in enumerate(series):
                ratio = value / axis_max if axis_max else 0
                ratio = max(0.0, min(1.0, ratio))
                x = left + idx * step_x
                y = top + (1 - ratio) * chart_height
                points.append(f"{x:.1f},{y:.1f}")
                dots.append(
                    {
                        "cx": round(x, 1),
                        "cy": round(y, 1),
                        "label": label_points[idx]["text"] if idx < len(label_points) else "",
                        "value": _format_currency(value),
                    }
                )
            series_output.append({"points": " ".join(points), "dots": dots})
        return {"series": series_output, "labels": label_points, "ticks": ticks}

    def _sort_forecast_rows(rows):
        def _row_key(row):
            date_val = row.period or row.as_of_date or getattr(row, "id", None)
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
            date_val = row.period or row.as_of_date or getattr(row, "id", None)
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
        "liquidity_ticks": [],
        "liquidity_legend": [],
        "variance_current_rows": [],
        "variance_cumulative_rows": [],
    }

    if not borrower:
        return context

    forecast_qs = ForecastRow.objects.filter(borrower=borrower)
    latest_forecast = (
        forecast_qs.exclude(as_of_date__isnull=True)
        .order_by("-as_of_date", "-created_at", "-id")
        .first()
    )
    if latest_forecast and latest_forecast.as_of_date:
        forecast_rows = list(forecast_qs.filter(as_of_date=latest_forecast.as_of_date))
    else:
        forecast_rows = list(forecast_qs.order_by("created_at", "id"))

    cw_qs = CurrentWeekVarianceRow.objects.filter(borrower=borrower)
    latest_cw = (
        cw_qs.exclude(date__isnull=True)
        .order_by("-date", "-created_at", "-id")
        .first()
    )
    if latest_cw and latest_cw.date:
        cw_rows = list(cw_qs.filter(date=latest_cw.date).order_by("category", "id"))
    else:
        cw_rows = list(cw_qs.order_by("created_at", "id"))

    cum_qs = CummulativeVarianceRow.objects.filter(borrower=borrower)
    latest_cum = (
        cum_qs.exclude(date__isnull=True)
        .order_by("-date", "-created_at", "-id")
        .first()
    )
    if latest_cum and latest_cum.date:
        cum_rows = list(cum_qs.filter(date=latest_cum.date).order_by("category", "id"))
    else:
        cum_rows = list(cum_qs.order_by("created_at", "id"))

    availability_qs = AvailabilityForecastRow.objects.filter(borrower=borrower)
    latest_availability = (
        availability_qs.exclude(date__isnull=True)
        .order_by("-date", "-created_at", "-id")
        .first()
    )
    if latest_availability and latest_availability.date:
        availability_rows_qs = list(
            availability_qs.filter(date=latest_availability.date).order_by("id")
        )
    else:
        availability_rows_qs = list(availability_qs.order_by("id"))

    report_date_candidates = []
    if latest_forecast:
        report_date_candidates.append(latest_forecast.as_of_date or latest_forecast.period)
    if latest_cw:
        report_date_candidates.append(latest_cw.date)
    if latest_cum:
        report_date_candidates.append(latest_cum.date)
    if latest_availability:
        report_date_candidates.append(latest_availability.date)
    report_date = next((val for val in report_date_candidates if val), None)
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
    actual_bars, forecast_bars, chart_labels, chart_ticks = _build_chart_bars(chart_rows)

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

    def _has_valid_stat(stat):
        return stat.get("value") not in (None, "$—", "—")

    fallback_stats = _build_forecast_stats(base_forecast_row)
    if fallback_stats and not any(_has_valid_stat(stat) for stat in stats):
        stats = fallback_stats

    def _section_row(label):
        return {
            "label": label,
            "actual": "",
            "forecasts": ["" for _ in range(max(0, len(column_entries) - 1))],
            "total": "",
            "row_class": "section-row",
        }

    cashflow_table_rows = [
        _section_row("Receipts"),
        _build_table_row("Collections", lambda row: _value_for_field(row, "net_sales"), ""),
        _build_table_row("Other Receipts", lambda row: _value_for_field(row, "ar"), ""),
        _build_table_row(
            "Total Receipts",
            lambda row: _sum_fields(row, ["net_sales", "ar"]),
            "title-row",
        ),
        _section_row("Operating Disbursements"),
        _build_table_row("Payroll", lambda row: None, ""),
        _build_table_row("Rent", lambda row: None, ""),
        _build_table_row("Utilities", lambda row: None, ""),
        _build_table_row("Property Tax", lambda row: None, ""),
        _build_table_row("Insurance", lambda row: None, ""),
        _build_table_row("Professional Services", lambda row: None, ""),
        _build_table_row("Software Expenses", lambda row: None, ""),
        _build_table_row("Repairs / Maintenance", lambda row: None, ""),
        _build_table_row("Other Disbursements", lambda row: None, ""),
        _build_table_row(
            "Total Operating Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        _section_row("Non-Operating Disbursements"),
        _build_table_row("Interest Expense", lambda row: None, ""),
        _build_table_row("Non-Recurring Tax Payments", lambda row: None, ""),
        _build_table_row("One-Time Professional Fees", lambda row: None, ""),
        _build_table_row("Total Non-Operating Disbursements", lambda row: None, "title-row"),
        _build_table_row(
            "Total Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        _build_table_row(
            "Net Cash Flow",
            lambda row: _difference_fields(row, ["net_sales", "ar"], ["loan_balance"]),
            "title-row",
        ),
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
        ("available_collateral", "Collateral Availability", "#2563eb"),
        ("revolver_availability", "Revolver Availability", "#6574cd"),
        ("net_sales", "Revolver Availability + Cash", "#1d4ed8"),
    ]
    liquidity_series = []
    liquidity_labels = []
    liquidity_ticks = []
    liquidity_legend = []
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
    series_values = []
    for field, label, color in liquidity_fields:
        values = [
            float(_to_decimal(getattr(row, field, None) or Decimal("0")))
            for row in trend_rows
        ]
        if not values:
            values = [0.0]
        series_values.append(values)
        liquidity_legend.append({"label": label, "color": color})
    if series_values and period_labels:
        chart = _build_liquidity_chart(series_values, period_labels)
        liquidity_labels = chart["labels"]
        liquidity_ticks = chart["ticks"]
        for idx, (_, label, color) in enumerate(liquidity_fields):
            series_entry = chart["series"][idx] if idx < len(chart["series"]) else {"points": "", "dots": []}
            liquidity_series.append(
                {
                    "points": series_entry["points"],
                    "dots": series_entry["dots"],
                    "color": color,
                    "label": label,
                }
            )

    def _variance_rows(rows):
        output = []
        section_headers = {
            "receipts",
            "operating disbursements",
            "non-operating disbursements",
        }
        for row in rows:
            category = _safe_str(row.category, default="—")
            proj = _format_money(row.projected)
            actual = _format_money(row.actual)
            variance_amount = _format_money(row.variance)
            variance_pct = _format_pct(row.variance_pct)
            category_lower = category.lower()
            row_class = ""
            if category_lower in section_headers:
                row_class = "section-row"
            elif "total" in category_lower or "net" in category_lower:
                row_class = "title-row"
            output.append(
                {
                    "category": category,
                    "projected": proj,
                    "actual": actual,
                    "variance_amount": variance_amount,
                    "variance_pct": variance_pct,
                    "row_class": row_class,
                }
            )
        if not output:
            output.append(
                {
                    "category": "—",
                    "projected": "$—",
                    "actual": "$—",
                    "variance_amount": "$—",
                    "variance_pct": "—%",
                    "row_class": "",
                }
            )
        return output

    variance_current = _variance_rows(cw_rows)
    variance_cumulative = _variance_rows(cum_rows)

    context.update(
        {
            "stats": stats,
            "summary_cards": [
                {"label": "Ending Cash", "value": next((s["value"] for s in stats if s["label"] == "Ending Cash"), "—")},
                {"label": "Total Receipts", "value": next((s["value"] for s in stats if s["label"] == "Total Receipts"), "—")},
                {"label": "Total Disbursement", "value": next((s["value"] for s in stats if s["label"] == "Total Disbursement"), "—")},
            ],
            "forecast_updated_label": _format_date(report_date) if report_date else "—",
            "snapshot_summary": (
                f"Collections total {_format_money(sum((_to_decimal(row.get('collections')) for row in chart_rows), Decimal('0')))} "
                f"with disbursements {_format_money(sum((_to_decimal(row.get('disbursements')) for row in chart_rows), Decimal('0')))} "
                f"across {len(chart_rows)} weeks."
                if chart_rows else "Snapshot summary not available."
            ),
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
                "ticks": chart_ticks,
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
            "liquidity_labels": liquidity_labels,
            "liquidity_ticks": liquidity_ticks,
            "liquidity_legend": liquidity_legend,
            "variance_current_rows": variance_current,
            "variance_cumulative_rows": variance_cumulative,
        }
    )
    return context


COLUMN_MONTH_LABELS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
TREND_LABELS = [
    "May 2019","Jun 2019","Jul 2019","Aug 2019","Sep 2019","Oct 2019",
    "Nov 2019","Dec 2019","Jan 2020","Feb 2020","Mar 2020"
]
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
        "inventory_mix_trend_chart": {
            "columns": [],
            "y_ticks": [],
            "x_labels": [],
            "x_grid": [],
            "grid": {"left": 60, "right": 738, "top": 24, "bottom": 174},
            "plot_width": 678,
            "plot_height": 148,
            "label_x": 48,
            "label_y": 188,
        },
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
        f"Inventory levels increased this period, primarily in finished goods, while turns softened due to slower sales velocity. Excess and obsolete inventory ticked up, raising the risk profile and influencing NOLV recovery expectations. Raw materials and WIP remained steady with no significant swings"
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

    def _format_short_currency(value):
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

    def _iter_months(end_date, count):
        year = end_date.year
        month = end_date.month
        months = []
        for _ in range(count):
            months.append(date(year, month, 1))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return list(reversed(months))

    category_keys = [category["key"] for category in CATEGORY_CONFIG]
    history_map = OrderedDict()
    for row in inventory_rows:
        created_at = getattr(row, "created_at", None)
        if not created_at:
            continue
        date_key = created_at.date()
        for category in CATEGORY_CONFIG:
            if _matches_category(row, category["match"]):
                bucket = history_map.setdefault(
                    date_key, {key: Decimal("0") for key in category_keys}
                )
                bucket[category["key"]] += _to_decimal(row.eligible_collateral)
                break

    series_values = {key: [] for key in category_keys}
    series_labels = []
    if len(history_map) > 1:
        sorted_dates = sorted(history_map.keys())[-12:]
        for date_key in sorted_dates:
            bucket = history_map[date_key]
            series_labels.append(date_key.strftime("%b %Y"))
            for key in category_keys:
                series_values[key].append(bucket.get(key, Decimal("0")))
    else:
        base_values = {
            key: category_metrics[key]["eligible"] for key in category_keys
        }
        synthetic_months = _iter_months(date.today(), 12)
        for idx, month_date in enumerate(synthetic_months):
            series_labels.append(month_date.strftime("%b %Y"))
            for key_index, key in enumerate(category_keys):
                base = base_values[key]
                factor = 1 + (math.sin((idx + key_index) * 0.6) * 0.08) + ((idx % 4) - 1.5) * 0.01
                value = base * Decimal(str(factor))
                if value < 0:
                    value = Decimal("0")
                series_values[key].append(value)

    totals = []
    for idx in range(len(series_labels)):
        totals.append(sum((series_values[key][idx] for key in category_keys), Decimal("0")))
    max_total = max(totals) if totals else Decimal("1")
    if max_total <= 0:
        max_total = Decimal("1")

    tick_count = 4
    step_value = Decimal(str(_nice_step(float(max_total) / max(1, tick_count - 1))))
    axis_max = step_value * Decimal(str(tick_count - 1))
    if axis_max <= 0:
        axis_max = max_total

    chart_width = 760
    chart_height = 210
    left = 60
    right = 22
    top = 24
    bottom = 38
    plot_width = chart_width - left - right
    plot_height = chart_height - top - bottom
    baseline_y = top + plot_height
    step_x = plot_width / max(1, len(series_labels) - 1) if series_labels else plot_width
    bar_width = 12

    y_ticks = []
    for idx in range(tick_count):
        ratio = idx / (tick_count - 1)
        value = axis_max * Decimal(str(1 - ratio))
        y = top + plot_height * ratio
        y_ticks.append({"y": round(y, 1), "label": _format_short_currency(value)})

    x_labels = []
    x_grid = []
    columns = []
    for idx, label in enumerate(series_labels):
        x_center = left + idx * step_x
        x = x_center - bar_width / 2
        month_label, year_label = label.split(" ", 1) if " " in label else (label, "")
        x_labels.append({"x": round(x_center, 1), "month": month_label, "year": year_label})
        x_grid.append(round(x_center, 1))

        stacked_height = 0.0
        column_bars = []
        for category in CATEGORY_CONFIG:
            value = series_values[category["key"]][idx] if series_values[category["key"]] else Decimal("0")
            height = float(_to_decimal(value) / axis_max) * plot_height
            y = baseline_y - stacked_height - height
            column_bars.append(
                {
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "height": round(height, 1),
                    "width": bar_width,
                    "color": category["color"],
                    "series_label": category["label"],
                    "value_display": _format_currency(value),
                    "month_label": label,
                }
            )
            stacked_height += height
        columns.append({"month_label": label, "bars": column_bars})

    inventory_mix_trend_chart = {
        "columns": columns,
        "y_ticks": y_ticks,
        "x_labels": x_labels,
        "x_grid": x_grid,
        "grid": {
            "left": left,
            "right": left + plot_width,
            "top": top,
            "bottom": baseline_y,
        },
        "plot_width": plot_width,
        "plot_height": plot_height,
        "label_x": left - 12,
        "label_y": baseline_y + 16,
    }

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
            value_label = TREND_LABELS[idx] if idx < len(TREND_LABELS) else f"Point {idx+1}"
            points.append(f"{x},{float(y_value):.1f}")
            points_list.append({
                "x": x,
                "y": float(y_value),
                "label": value_label,
                "value": _format_pct(value),
            })
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
        "inventory_mix_trend_chart": inventory_mix_trend_chart,
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
    }

    if not borrower:
        return base_context

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

    ar_rows = list(
        ARMetricsRow.objects.filter(borrower=borrower).order_by("as_of_date", "created_at", "id")
    )
    if not ar_rows:
        return base_context

    grouped = OrderedDict()
    for row in ar_rows:
        key = row.as_of_date or (row.created_at and row.created_at.date())
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(row)

    history = []
    for label_date, rows in grouped.items():
        payload = _aggregate_ar_rows(rows)
        if isinstance(label_date, date):
            formatted_label = label_date.strftime("%b %y")
        elif hasattr(label_date, "strftime"):
            formatted_label = label_date.strftime("%b %y")
        else:
            formatted_label = "Snapshot"
        history.append({**payload, "label": formatted_label})

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

    def _trim_axis_value(value):
        text = f"{value:.1f}"
        return text.rstrip("0").rstrip(".")

    def _format_axis_currency(value):
        val = float(value)
        abs_val = abs(val)
        if abs_val >= 1_000_000_000:
            return f"${_trim_axis_value(val / 1_000_000_000)}B"
        if abs_val >= 1_000_000:
            return f"${_trim_axis_value(val / 1_000_000)}M"
        if abs_val >= 1_000:
            return f"${_trim_axis_value(val / 1_000)}k"
        return f"${val:,.0f}"

    def _format_axis_days(value):
        return f"{int(round(value)):,}"

    def _format_axis_pct(value):
        return f"{_trim_axis_value(value)}%"

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

    def _normalize_chart_values(values, labels):
        values = [float(_to_decimal(val)) for val in values if val is not None]
        if not values:
            values = [0.0]
        if len(values) < 2:
            values = values + [values[-1]]
        if not labels:
            labels = [f"{idx + 1:02d}" for idx in range(len(values))]
        elif len(labels) < len(values):
            extra = [f"{idx + len(labels) + 1:02d}" for idx in range(len(values) - len(labels))]
            labels = labels + extra
        elif len(labels) > len(values):
            labels = labels[-len(values):]
        return values, labels

    def _build_kpi_chart(values, labels, axis_formatter, value_formatter):
        values, labels = _normalize_chart_values(values, labels)
        width = 260
        height = 140
        left = 30
        right = 12
        top = 14
        bottom = 26
        plot_width = width - left - right
        plot_height = height - top - bottom
        max_val = max(values)
        if max_val <= 0:
            max_val = 1.0
        tick_count = 4
        step_value = _nice_step(max_val / max(1, tick_count - 1))
        axis_max = step_value * (tick_count - 1)
        if axis_max <= 0:
            axis_max = max_val
        step_x = plot_width / max(1, len(values) - 1)
        baseline_y = top + plot_height
        points = []
        dots = []
        x_positions = []
        x_labels = []
        for idx, value in enumerate(values):
            ratio = value / axis_max if axis_max else 0
            ratio = max(0.0, min(1.0, ratio))
            x = left + idx * step_x
            y = baseline_y - ratio * plot_height
            points.append(f"{x:.1f},{y:.1f}")
            x_positions.append(round(x, 1))
            x_labels.append({"x": round(x, 1), "text": labels[idx]})
            dots.append(
                {
                    "cx": round(x, 1),
                    "cy": round(y, 1),
                    "label": labels[idx],
                    "value": value_formatter(value),
                }
            )
        y_ticks = []
        for idx in range(tick_count):
            ratio = idx / (tick_count - 1)
            value = axis_max * (1 - ratio)
            y = top + plot_height * ratio
            y_ticks.append({"y": round(y, 1), "label": axis_formatter(value)})
        return {
            "points": " ".join(points),
            "dots": dots,
            "x_labels": x_labels,
            "y_ticks": y_ticks,
            "x_grid": x_positions,
            "grid": {
                "left": left,
                "right": round(left + plot_width, 1),
                "top": top,
                "bottom": round(baseline_y, 1),
            },
            "label_x": left - 6,
            "label_y": round(baseline_y + 16, 1),
        }

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
            "icon": "images/balance.svg",
            "axis_formatter": _format_axis_currency,
            "improvement_on_increase": True,
        },
        {
            "label": "Days Sales Outstanding",
            "key": "avg_dso",
            "formatter": lambda value: _format_days(value),
            "color": "var(--purple)",
            "icon": "images/sales_outstanding.svg",
            "axis_formatter": _format_axis_days,
            "improvement_on_increase": False,
        },
        {
            "label": "% of total past due",
            "key": "past_due_pct",
            "formatter": lambda value: _format_pct_display(value),
            "color": "var(--teal)",
            "icon": "images/total_pastdue_icon.svg",
            "axis_formatter": _format_axis_pct,
            "improvement_on_increase": False,
        },
    ]
    kpis = []
    chart_points = 7
    chart_history = history[-chart_points:] if len(history) > chart_points else history[:]
    chart_labels = [f"{idx + 1:02d}" for idx in range(len(chart_history))]
    for spec in kpi_specs:
        series_values = [row[spec["key"]] for row in chart_history]
        chart = _build_kpi_chart(
            series_values,
            chart_labels,
            axis_formatter=spec["axis_formatter"],
            value_formatter=spec["formatter"],
        )
        delta = _delta_payload(
            current_snapshot[spec["key"]],
            previous_snapshot[spec["key"]] if previous_snapshot else None,
            improvement_on_increase=spec["improvement_on_increase"],
        )
        kpis.append(
            {
                "label": spec["label"],
                "value": spec["formatter"](current_snapshot[spec["key"]]),
                "color": spec["color"],
                "icon": spec["icon"],
                "delta": delta["value"] if delta else None,
                "symbol": delta["symbol"] if delta else "",
                "delta_class": delta["delta_class"] if delta else "",
                "chart": chart,
            }
        )

    aging_rows = list(
        AgingCompositionRow.objects.filter(borrower=borrower).order_by("-as_of_date", "-created_at", "-id")
    )
    AGING_BUCKET_DEFS = [
        {"key": "current", "label": "Current", "color": "#1b2a55"},
        {"key": "0-30", "label": "0-30", "color": "rgba(43,111,247,.35)"},
        {"key": "31-60", "label": "31-60", "color": "rgba(43,111,247,.25)"},
        {"key": "61-90", "label": "61-90", "color": "rgba(43,111,247,.30)"},
        {"key": "90+", "label": "91+", "color": "rgba(43,111,247,.20)"},
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
        if "90" in normalized or "91" in normalized:
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
    bucket_positions = [60, 140, 220, 300, 380]
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
        label_primary = bucket["label"]
        label_secondary = ""
        if bucket["key"] != "current":
            label_primary = "91+" if bucket["key"] == "90+" else bucket["label"]
            label_secondary = "Past Due"
        bar_width = 30
        aging_buckets.append(
            {
                "x": bucket_positions[idx],
                "y": y_position,
                "height": height_value,
                "width": bar_width,
                "color": bucket["color"],
                "percent_display": _format_pct(percent_ratio),
                "amount_display": _format_currency(amount),
                "label": bucket["label"],
                "label_primary": label_primary,
                "label_secondary": label_secondary,
                "percent_y": max(24, y_position - 6),
                "label_y": 156,
                "label_secondary_y": 168,
                "text_x": bucket_positions[idx] + (bar_width / 2),
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
                "past_due_pct": f"{past_pct:.1f}%",
                "current_pct": f"{current_pct:.1f}%",
                "label": entry["label"],
            }
        )
        trend_labels.append({"x": label_x, "text": entry["label"]})

    # Tables for customer aging composition views
    bucket_columns = ["Current", "0-30", "31-60", "61-90", "91+"]
    bucket_total_rows = []
    bucket_past_due_rows = []
    latest_pct = current_snapshot.get("past_due_pct") if current_snapshot else None
    past_due_ratio = (
        (latest_pct / Decimal("100")) if latest_pct is not None else Decimal("0")
    )

    concentration_rows = list(
        ConcentrationADODSORow.objects.filter(borrower=borrower)
    )
    top_customers = sorted(
        concentration_rows,
        key=lambda r: _to_decimal(r.current_concentration_pct),
        reverse=True,
    )[:20]
    if top_customers:
        weights = []
        for row in top_customers:
            weight = _to_decimal(row.current_concentration_pct)
            if weight > Decimal("1"):
                weight /= Decimal("100")
            weights.append(max(weight, Decimal("0")))
        total_weight = sum(weights)
        if total_weight <= 0:
            weights = [Decimal("1") for _ in top_customers]
            total_weight = Decimal(len(top_customers))
        for idx, row in enumerate(top_customers):
            ratio = weights[idx] / total_weight if total_weight else Decimal("0")
            values = []
            past_values = []
            total_value = Decimal("0")
            past_total_value = Decimal("0")
            for column in bucket_columns:
                key = "90+" if column == "91+" else column
                amount = bucket_amounts.get(key, Decimal("0"))
                customer_amount = amount * ratio
                past_amount = customer_amount * past_due_ratio
                values.append(_format_currency(customer_amount))
                past_values.append(_format_currency(past_amount))
                total_value += customer_amount
                past_total_value += past_amount
            customer_name = _safe_str(row.customer) or f"Customer {idx + 1}"
            bucket_total_rows.append(
                {
                    "customer": customer_name,
                    "values": values,
                    "total": _format_currency(total_value),
                }
            )
            bucket_past_due_rows.append(
                {
                    "customer": customer_name,
                    "values": past_values,
                    "total": _format_currency(past_total_value),
                }
            )

    ineligible_overview = (
        IneligibleOverviewRow.objects.filter(borrower=borrower)
        .order_by("-date", "-id")
        .first()
    )
    ineligible_trend_rows = list(
        IneligibleTrendRow.objects.filter(borrower=borrower).order_by("date", "id")
    )
    ineligible_rows = []
    ineligible_total_row = None
    if ineligible_overview:
        total_ineligible = _to_decimal(ineligible_overview.total_ineligible)
        categories = [
            ("Past Due Over 60 Days", ineligible_overview.past_due_gt_90_days),
            ("Dilution", ineligible_overview.dilution),
            ("Cross Age", ineligible_overview.cross_age),
            ("Concentration Over Cap", ineligible_overview.concentration_over_cap),
            ("Foreign", ineligible_overview.foreign),
            ("Government", ineligible_overview.government),
            ("Intercompany", ineligible_overview.intercompany),
            ("Contra", ineligible_overview.contra),
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
    trend_chart = _build_trend_points(
        trend_points,
        trend_texts,
        height=230,
        top=40,
        bottom=30,
        left=60,
    )
    formatted_labels = []
    for label in trend_chart["labels"]:
        text = label.get("text") or ""
        month = text
        year = ""
        if " " in text:
            month, year = text.split(" ", 1)
            if year.isdigit() and len(year) == 2:
                year = f"20{year}"
        formatted_labels.append(
            {
                "x": round(label["x"] + 6, 1),
                "month": month,
                "year": year,
            }
        )
    trend_chart["labels"] = formatted_labels
    trend_dots = []
    for idx, dot in enumerate(trend_chart["dots"]):
        value = trend_points[idx] if idx < len(trend_points) else None
        label = trend_texts[idx] if idx < len(trend_texts) else ""
        trend_dots.append(
            {
                "cx": dot["cx"],
                "cy": dot["cy"],
                "label": label,
                "value": f"{value:.1f}%" if value is not None else "—",
            }
        )
    trend_chart["dots"] = trend_dots

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
        "ar_customer_aging_total_rows": bucket_total_rows,
        "ar_customer_aging_past_due_rows": bucket_past_due_rows,
    }


def _finished_goals_context(borrower, range_key="today", division="all"):
    range_options = [
        {"value": "today", "label": "Today"},
        {"value": "yesterday", "label": "Yesterday"},
        {"value": "last_7_days", "label": "Last 7 Days"},
        {"value": "last_14_days", "label": "Last 14 Days"},
        {"value": "last_30_days", "label": "Last 30 Days"},
        {"value": "last_90_days", "label": "Last 90 Days"},
    ]

    range_aliases = {
        "today": "today",
        "yesterday": "yesterday",
        "last_7_days": "last_7_days",
        "last_14_days": "last_14_days",
        "last_30_days": "last_30_days",
        "last_90_days": "last_90_days",
        "last7days": "last_7_days",
        "last14days": "last_14_days",
        "last30days": "last_30_days",
        "last90days": "last_90_days",
        "last 7 days": "last_7_days",
        "last 14 days": "last_14_days",
        "last 30 days": "last_30_days",
        "last 90 days": "last_90_days",
    }

    normalized_range = (range_key or "today").strip().lower()
    normalized_range = range_aliases.get(normalized_range, "today")

    normalized_division = (division or "all").strip()
    if normalized_division.lower() in {"all", "all divisions", "all_divisions"}:
        normalized_division = "all"
    base_context = {
        "finished_goals_metrics": [],
        "finished_goals_sales_insights": [],
        "finished_goals_highlights": [],
        "finished_goals_chart_config": {},
        "finished_goals_inline_excess_by_category": [],
        "finished_goals_inline_excess_totals": {},
        "finished_goals_top_skus": [],
        "finished_goals_ar_concentration": [],
        "finished_goals_ineligible_detail": [],
        "finished_goals_ar_aging": {
            "buckets": [],
            "amounts": [],
            "shares": [],
            "total_amount": "—",
            "total_share": "—",
        },
        "finished_goals_stock": [],
        "finished_goals_range_options": range_options,
        "finished_goals_selected_range": normalized_range,
        "finished_goals_division_options": [{"value": "all", "label": "All Divisions"}],
        "finished_goals_selected_division": normalized_division,
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    def _range_dates(key):
        today = date.today()
        if key == "yesterday":
            day = today - timedelta(days=1)
            return day, day
        if key == "last_7_days":
            return today - timedelta(days=6), today
        if key == "last_14_days":
            return today - timedelta(days=13), today
        if key == "last_30_days":
            return today - timedelta(days=29), today
        if key == "last_90_days":
            return today - timedelta(days=89), today
        return today, today

    start_date, end_date = _range_dates(normalized_range)

    def _apply_date_filter(qs, field_name):
        if start_date and end_date:
            return qs.filter(**{f"{field_name}__range": (start_date, end_date)})
        return qs

    def _apply_division_filter(qs):
        if normalized_division != "all":
            return qs.filter(division__iexact=normalized_division)
        return qs

    division_sources = [
        FGInventoryMetricsRow,
        FGIneligibleDetailRow,
        FGInlineCategoryAnalysisRow,
        FGInlineExcessByCategoryRow,
        SalesGMTrendRow,
        HistoricalTop20SKUsRow,
    ]
    divisions = set()
    for model in division_sources:
        for value in (
            model.objects.filter(borrower=borrower)
            .exclude(division__isnull=True)
            .exclude(division__exact="")
            .values_list("division", flat=True)
            .distinct()
        ):
            cleaned = str(value).strip()
            if cleaned:
                divisions.add(cleaned)
    if divisions:
        base_context["finished_goals_division_options"] = [
            {"value": "all", "label": "All Divisions"},
            *(
                {"value": item, "label": item}
                for item in sorted(divisions)
            ),
        ]
        if normalized_division != "all" and normalized_division not in divisions:
            normalized_division = "all"
            base_context["finished_goals_selected_division"] = normalized_division

    inventory_total = state["inventory_total"]
    inventory_available_total = state["inventory_available_total"]
    inventory_ineligible = state["inventory_ineligible"]
    inventory_net_total = state["inventory_net_total"]
    category_metrics = state["category_metrics"]
    inventory_rows = state["inventory_rows"]

    metrics_qs = FGInventoryMetricsRow.objects.filter(borrower=borrower)
    fg_type_qs = metrics_qs.filter(inventory_type__icontains="finished")
    if fg_type_qs.exists():
        metrics_qs = fg_type_qs
    metrics_qs = _apply_division_filter(metrics_qs)
    metrics_qs = _apply_date_filter(metrics_qs, "as_of_date")
    metrics_row = metrics_qs.order_by("-as_of_date", "-created_at", "-id").first()
    if metrics_row:
        inventory_total = _to_decimal(metrics_row.total_inventory)
        inventory_ineligible = _to_decimal(metrics_row.ineligible_inventory)
        inventory_available_total = _to_decimal(metrics_row.available_inventory)
        inventory_net_total = inventory_available_total

    ar_row = (
        ARMetricsRow.objects.filter(borrower=borrower)
        .order_by("-as_of_date", "-created_at", "-id")
        .first()
    )

    available_pct = (
        (inventory_available_total / inventory_total) if inventory_total else Decimal("0")
    )
    ineligible_pct = (
        (inventory_ineligible / inventory_total) if inventory_total else Decimal("0")
    )
    total_quality = (
        (inventory_net_total / inventory_total) if inventory_total else Decimal("0")
    )

    total_delta = (
        (total_quality - Decimal("0.8")) * Decimal("100") if inventory_total else None
    )
    ineligible_delta = (
        (Decimal("0.2") - ineligible_pct) * Decimal("100") if inventory_total else None
    )
    available_delta = (
        (available_pct - Decimal("0.5")) * Decimal("100") if inventory_total else None
    )

    metric_defs = [
        ("Total Inventory", _format_currency(inventory_total), total_delta),
        ("Ineligible Inventory", _format_currency(inventory_ineligible), ineligible_delta),
        ("Available Inventory", _format_pct(available_pct), available_delta),
    ]

    metrics = []
    for label, value, delta in metric_defs:
        metrics.append(
            {
                "label": label,
                "value": value,
                "delta": f"{abs(delta):.2f}%" if delta is not None else None,
                "delta_class": "good" if delta is not None and delta >= 0 else "bad"
                if delta is not None
                else "",
                "icon": ICON_SVGS.get(label, ICON_SVGS["Total Inventory"]),
            }
        )

    ineligible_detail_rows = []
    ineligible_qs = FGIneligibleDetailRow.objects.filter(borrower=borrower)
    ineligible_qs = _apply_division_filter(ineligible_qs)
    ineligible_qs = _apply_date_filter(ineligible_qs, "date")
    ineligible_row = ineligible_qs.order_by("-date", "-created_at", "-id").first()
    if ineligible_row:
        total_ineligible = _to_decimal(ineligible_row.total_ineligible)
        reason_fields = [
            ("Slow-Moving/Obsolete", "slow_moving_obsolete"),
            ("Aged", "aged"),
            ("Off Site", "off_site"),
            ("Consigned", "consigned"),
            ("In-Transit", "in_transit"),
            ("Damaged/Non-Saleable", "damaged_non_saleable"),
        ]
        for label, field in reason_fields:
            amount = _to_decimal(getattr(ineligible_row, field, None))
            pct = (amount / total_ineligible) if total_ineligible else Decimal("0")
            ineligible_detail_rows.append(
                {
                    "reason": label,
                    "amount": _format_currency(amount),
                    "pct": _format_pct(pct),
                }
            )

    def _dec_or_none(value):
        if value is None:
            return None
        try:
            return Decimal(value)
        except Exception:
            try:
                return Decimal(str(value))
            except Exception:
                return None

    def _format_item_number(value):
        dec = _dec_or_none(value)
        if dec is None:
            return "—"
        try:
            if dec == dec.to_integral_value():
                return str(int(dec))
        except Exception:
            pass
        return f"{dec.normalize():f}"

    def _format_wos(value):
        dec = _dec_or_none(value)
        if dec is None:
            return "—"
        return f"{dec:.1f}"

    def _pct_change(current, previous):
        curr = _dec_or_none(current)
        prev = _dec_or_none(previous)
        if curr is None or prev is None or prev == 0:
            return None
        return (curr - prev) / abs(prev) * Decimal("100")

    def _pct_point_change(current, previous):
        curr = _dec_or_none(current)
        prev = _dec_or_none(previous)
        if curr is None or prev is None:
            return None
        if abs(curr) <= 1 and abs(prev) <= 1:
            return (curr - prev) * Decimal("100")
        return curr - prev

    def _delta_payload(delta):
        if delta is None:
            return {"delta": None, "delta_class": ""}
        return {
            "delta": f"{abs(delta):.2f}%",
            "delta_class": "good" if delta >= 0 else "bad",
        }

    sales_trend_qs = SalesGMTrendRow.objects.filter(borrower=borrower)
    sales_trend_qs = _apply_division_filter(sales_trend_qs)
    sales_trend_qs = _apply_date_filter(sales_trend_qs, "as_of_date")
    sales_rows = list(
        sales_trend_qs.order_by("-as_of_date", "-created_at", "-id")[:2]
    )
    latest_sales = sales_rows[0] if sales_rows else None
    previous_sales = sales_rows[1] if len(sales_rows) > 1 else None

    if latest_sales:
        net_sales_delta = (
            _pct_change(latest_sales.net_sales, previous_sales.net_sales)
            if previous_sales
            else None
        )
        gross_margin_delta = (
            _pct_point_change(
                latest_sales.gross_margin_pct, previous_sales.gross_margin_pct
            )
            if previous_sales
            else None
        )
        trend_value = (
            latest_sales.trend_ttm_pct
            if latest_sales.trend_ttm_pct is not None
            else _pct_change(latest_sales.ttm_sales, latest_sales.ttm_sales_prior)
        )
        trend_delta = (
            _pct_point_change(
                latest_sales.trend_ttm_pct, previous_sales.trend_ttm_pct
            )
            if previous_sales
            else None
        )

        sales_insights = [
            {
                "label": "Total Net Sales",
                "value": _format_currency(latest_sales.net_sales),
                **_delta_payload(net_sales_delta),
            },
            {
                "label": "Gross Margin",
                "value": _format_pct(latest_sales.gross_margin_pct),
                **_delta_payload(gross_margin_delta),
            },
            {
                "label": "12 Months Sales Trend",
                "value": _format_pct(trend_value),
                **_delta_payload(trend_delta),
            },
        ]
    else:
        sales_insights = [
            {"label": "Total Net Sales", "value": "—", "delta": None, "delta_class": ""},
            {"label": "Gross Margin", "value": "—", "delta": None, "delta_class": ""},
            {
                "label": "12 Months Sales Trend",
                "value": "—",
                "delta": None,
                "delta_class": "",
            },
        ]

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

    def _to_millions(value):
        return float(_to_decimal(value) / Decimal("1000000"))

    def _to_pct_value(value):
        pct = _to_decimal(value)
        if abs(pct) <= 1:
            pct *= Decimal("100")
        return float(pct)

    inline_excess_labels = [
        "New",
        "0 - 13",
        "13 - 26",
        "26 - 39",
        "39 - 52",
        "52+",
        "No Sales",
    ]

    inline_bucket_totals = OrderedDict((label, Decimal("0")) for label in inline_excess_labels)
    inline_rows = FGInlineCategoryAnalysisRow.objects.filter(borrower=borrower)
    inline_rows = _apply_division_filter(inline_rows)
    inline_rows = _apply_date_filter(inline_rows, "as_of_date")
    inline_latest = inline_rows.exclude(as_of_date__isnull=True).order_by("-as_of_date").first()
    if inline_latest and inline_latest.as_of_date:
        inline_rows = inline_rows.filter(as_of_date=inline_latest.as_of_date)
    inline_total = Decimal("0")
    for row in inline_rows:
        amount = _to_decimal(row.fg_available or row.fg_total)
        inline_total += amount
        sales = _to_decimal(row.sales)
        wos = _dec_or_none(row.weeks_of_supply)
        if sales <= 0:
            bucket = "No Sales"
        elif wos is None:
            bucket = "New"
        elif wos <= 0:
            bucket = "New"
        elif wos <= 13:
            bucket = "0 - 13"
        elif wos <= 26:
            bucket = "13 - 26"
        elif wos <= 39:
            bucket = "26 - 39"
        elif wos <= 52:
            bucket = "39 - 52"
        else:
            bucket = "52+"
        inline_bucket_totals[bucket] += amount

    inline_excess_values = []
    inline_excess_value_labels = []
    for label in inline_excess_labels:
        amount = inline_bucket_totals[label]
        pct = (amount / inline_total * Decimal("100")) if inline_total else Decimal("0")
        inline_excess_values.append(float(pct))
        inline_excess_value_labels.append(f"{pct:.0f}%")

    inline_excess_trend_labels = []
    inline_excess_trend_values = []
    inline_trend_rows = (
        FGInlineCategoryAnalysisRow.objects.filter(borrower=borrower)
        .exclude(as_of_date__isnull=True)
    )
    inline_trend_rows = _apply_division_filter(inline_trend_rows)
    inline_trend_rows = _apply_date_filter(inline_trend_rows, "as_of_date")
    inline_trend_rows = inline_trend_rows.order_by("as_of_date", "id")
    inline_trend_map = OrderedDict()
    for row in inline_trend_rows:
        dt = row.as_of_date
        if dt not in inline_trend_map:
            inline_trend_map[dt] = {"total": Decimal("0"), "inline": Decimal("0")}
        amount = _to_decimal(row.fg_available or row.fg_total)
        inline_trend_map[dt]["total"] += amount
        sales = _to_decimal(row.sales)
        wos = _dec_or_none(row.weeks_of_supply)
        if sales > 0 and wos is not None and wos <= 52:
            inline_trend_map[dt]["inline"] += amount

    for dt, totals in list(inline_trend_map.items())[-10:]:
        inline_excess_trend_labels.append(dt.strftime("%b\n%Y"))
        pct = (totals["inline"] / totals["total"] * Decimal("100")) if totals["total"] else Decimal("0")
        inline_excess_trend_values.append(float(pct))

    inventory_trend_labels = []
    inventory_trend_values = []
    metrics_trend_rows = (
        metrics_qs.exclude(as_of_date__isnull=True)
        .order_by("as_of_date", "id")
    )
    metrics_trend_items = list(metrics_trend_rows)[-11:]
    if metrics_trend_items:
        for row in metrics_trend_items:
            label = row.as_of_date.strftime("%b\n%Y")
            inventory_trend_labels.append(label)
            total = _to_decimal(row.total_inventory)
            available = _to_decimal(row.available_inventory)
            pct = (available / total * Decimal("100")) if total else Decimal("0")
            pct = max(Decimal("0"), min(Decimal("100"), pct))
            inventory_trend_values.append(float(pct))
    else:
        inventory_rows_all = CollateralOverviewRow.objects.filter(
            borrower=borrower,
            main_type__icontains="inventory",
        ).exclude(created_at__isnull=True)
        inventory_rows_all = _apply_date_filter(inventory_rows_all, "created_at")
        inventory_rows_all = inventory_rows_all.order_by("created_at", "id")
        inventory_trend_map = OrderedDict()
        for row in inventory_rows_all:
            dt = row.created_at.date()
            if dt not in inventory_trend_map:
                inventory_trend_map[dt] = {"eligible": Decimal("0"), "total": Decimal("0")}
            inventory_trend_map[dt]["eligible"] += _to_decimal(row.eligible_collateral)
            inventory_trend_map[dt]["total"] += _to_decimal(row.beginning_collateral)

        inventory_trend_items = list(inventory_trend_map.items())[-11:]
        if inventory_trend_items:
            for dt, totals in inventory_trend_items:
                label = dt.strftime("%b\n%Y")
                inventory_trend_labels.append(label)
                total = totals["total"]
                pct = (totals["eligible"] / total * Decimal("100")) if total else Decimal("0")
                pct = max(Decimal("0"), min(Decimal("100"), pct))
                inventory_trend_values.append(float(pct))
        else:
            def _month_label(idx, total):
                base = date.today().replace(day=1)
                offset = total - idx - 1
                month = base.month - offset
                year = base.year
                while month <= 0:
                    month += 12
                    year -= 1
                return date(year, month, 1).strftime("%b\n%Y")

            base_pct = float(available_pct * Decimal("100")) if isinstance(available_pct, Decimal) else 50.0
            for idx in range(11):
                inventory_trend_labels.append(_month_label(idx, 11))
                variation = math.sin(idx / 2.0) * 6
                value = max(10.0, min(100.0, base_pct + variation))
                inventory_trend_values.append(value)

    if len(inventory_trend_values) < 2:
        def _month_label(idx, total):
            base = date.today().replace(day=1)
            offset = total - idx - 1
            month = base.month - offset
            year = base.year
            while month <= 0:
                month += 12
                year -= 1
            return date(year, month, 1).strftime("%b\n%Y")

        base_pct = float(available_pct * Decimal("100")) if isinstance(available_pct, Decimal) else 50.0
        inventory_trend_labels = [_month_label(idx, 11) for idx in range(11)]
        inventory_trend_values = [
            max(10.0, min(100.0, base_pct + math.sin(idx / 2.0) * 6))
            for idx in range(11)
        ]

    trend_min = min(inventory_trend_values) if inventory_trend_values else 0
    trend_max = max(inventory_trend_values) if inventory_trend_values else 100
    if trend_min >= 10 and trend_max <= 100:
        trend_y_min = 10
        trend_y_max = 100
        trend_tick_values = [100, 90, 70, 50, 30, 10]
    else:
        trend_y_min = max(0, math.floor(trend_min / 10) * 10)
        trend_y_max = math.ceil(trend_max / 10) * 10 or 100
        if trend_y_max == trend_y_min:
            trend_y_max += 10
        trend_tick_values = None

    trend_rows_all = list(
        sales_trend_qs.exclude(as_of_date__isnull=True)
        .order_by("as_of_date", "created_at", "id")
    )
    sales_rows = [row for row in trend_rows_all if row.net_sales is not None][-9:]
    gm_rows = [row for row in trend_rows_all if row.gross_margin_pct is not None][-11:]

    sales_labels = [row.as_of_date.strftime("%b\n%Y") for row in sales_rows]
    sales_values = [_to_millions(row.net_sales) for row in sales_rows]
    gross_labels = [row.as_of_date.strftime("%b\n%Y") for row in gm_rows]
    gross_values = [_to_pct_value(row.gross_margin_pct) for row in gm_rows]

    sales_axis_max = None
    sales_ticks = None
    if sales_values:
        sales_max = max(sales_values)
        sales_axis_max = max(2, math.ceil(sales_max / 2) * 2) if sales_max else 2
        if sales_axis_max <= 6:
            sales_ticks = 4
        elif sales_axis_max <= 10:
            sales_ticks = 6
        else:
            sales_ticks = 5

    gross_axis_min = None
    gross_axis_max = None
    gross_ticks = None
    if gross_values:
        gross_min = min(gross_values)
        gross_max = max(gross_values)
        gross_axis_min = max(0, math.floor(gross_min / 10) * 10)
        gross_axis_max = math.ceil(gross_max / 10) * 10
        if gross_axis_min == gross_axis_max:
            gross_axis_min = max(0, gross_axis_min - 10)
            gross_axis_max = gross_axis_max + 10
        gross_ticks = 5

    sales_right_values = [
        _to_pct_value(row.gross_margin_pct)
        for row in sales_rows
        if row.gross_margin_pct is not None
    ]
    sales_right = None
    if sales_right_values:
        right_min = max(0, math.floor(min(sales_right_values) / 10) * 10)
        right_max = math.ceil(max(sales_right_values) / 10) * 10
        if right_min == right_max:
            right_min = max(0, right_min - 10)
            right_max = right_max + 10
        sales_right = {
            "min": right_min,
            "max": right_max,
            "ticks": 4,
            "suffix": "%",
            "decimals": 0,
        }

    chart_config = {
        "inventoryTrend": {
            "type": "line",
            "title": "Inventory Trend",
            "labels": inventory_trend_labels,
            "values": inventory_trend_values,
            "ySuffix": "%",
            "yLabel": "% of Inventory",
            "yMin": trend_y_min,
            "yMax": trend_y_max,
            "yTicks": 6,
            "yTickValues": trend_tick_values,
            "yDecimals": 0,
            "showAllPoints": True,
            "pointRadius": 3,
        },
        "agedStock": {
            "type": "bar",
            "title": "Sales Trend",
            "labels": sales_labels,
            "values": sales_values,
            "barClass": "bar-strong",
            "barWidth": 14,
            "barGap": 18,
            "yPrefix": "$",
            "ySuffix": "M",
            "yMin": 0 if sales_values else None,
            "yMax": sales_axis_max,
            "yTicks": sales_ticks,
            "yDecimals": 0,
            "yRight": sales_right,
        },
        "agedStockTrend": {
            "type": "line",
            "title": "Gross Margin Trend",
            "labels": gross_labels,
            "values": gross_values,
            "showAllPoints": True,
            "pointRadius": 2.6,
            "ySuffix": "%",
            "yMin": gross_axis_min,
            "yMax": gross_axis_max,
            "yTicks": gross_ticks,
            "yDecimals": 0,
        },
        "inlineExcess": {
            "type": "bar",
            "title": "In-line vs Excess",
            "labels": inline_excess_labels,
            "values": inline_excess_values,
            "valueLabels": inline_excess_value_labels,
            "showValueLabels": True,
            "highlightIndex": 3,
            "ySuffix": "%",
            "yMin": 0,
            "yMax": 100,
            "yTicks": 6,
            "yDecimals": 0,
        },
        "inlineExcessTrend": {
            "type": "line",
            "title": "In-Line vs Excess Trend",
            "labels": inline_excess_trend_labels,
            "values": inline_excess_trend_values,
            "ySuffix": "%",
            "yMin": 0,
            "yMax": 100,
            "yTicks": 6,
            "yDecimals": 0,
            "yLabel": "% Of Inventory",
        },
    }

    inline_excess_qs = FGInlineExcessByCategoryRow.objects.filter(borrower=borrower)
    inline_excess_qs = _apply_division_filter(inline_excess_qs)
    inline_excess_qs = _apply_date_filter(inline_excess_qs, "as_of_date")
    inline_excess_rows = list(
        inline_excess_qs.order_by("category", "id")
    )
    inline_excess_by_category = []
    inline_excess_totals = {}
    if inline_excess_rows:
        total_available = Decimal("0")
        total_inline = Decimal("0")
        total_excess = Decimal("0")
        for row in inline_excess_rows:
            inline_amount = _format_currency(row.inline_dollars)
            inline_pct = _format_pct(row.inline_pct)
            excess_amount = _format_currency(row.excess_dollars)
            excess_pct = _format_pct(row.excess_pct)
            inline_excess_by_category.append(
                {
                    "category": row.category or "Category",
                    "new_amount": inline_amount,
                    "new_pct": inline_pct,
                    "inline_0_52_amount": inline_amount,
                    "inline_0_52_pct": inline_pct,
                    "inline_total_amount": inline_amount,
                    "inline_total_pct": inline_pct,
                    "week_52_amount": excess_amount,
                    "week_52_pct": excess_pct,
                    "no_sales_amount": excess_amount,
                    "no_sales_pct": excess_pct,
                    "excess_total_amount": excess_amount,
                    "excess_total_pct": excess_pct,
                }
            )
            total_available += _to_decimal(row.fg_available)
            total_inline += _to_decimal(row.inline_dollars)
            total_excess += _to_decimal(row.excess_dollars)

        inline_total_pct = (
            _format_pct(total_inline / total_available) if total_available else "—"
        )
        excess_total_pct = (
            _format_pct(total_excess / total_available) if total_available else "—"
        )
        inline_excess_totals = {
            "new_amount": _format_currency(total_inline),
            "new_pct": inline_total_pct,
            "inline_0_52_amount": _format_currency(total_inline),
            "inline_0_52_pct": inline_total_pct,
            "inline_total_amount": _format_currency(total_inline),
            "inline_total_pct": inline_total_pct,
            "week_52_amount": _format_currency(total_excess),
            "week_52_pct": excess_total_pct,
            "no_sales_amount": _format_currency(total_excess),
            "no_sales_pct": excess_total_pct,
            "excess_total_amount": _format_currency(total_excess),
            "excess_total_pct": excess_total_pct,
        }
    else:
        sample_categories = [
            "Cabinets",
            "Doors",
            "Flooring Products",
            "Moulding & Trim",
            "Decking",
            "Roofing",
            "Windows",
            "Hardware",
            "Insulation",
            "Tools",
            "Others",
        ]
        sample_amount = "$976"
        sample_pct = "75.0%"
        for category in sample_categories:
            inline_excess_by_category.append(
                {
                    "category": category,
                    "new_amount": sample_amount,
                    "new_pct": sample_pct,
                    "inline_0_52_amount": sample_amount,
                    "inline_0_52_pct": sample_pct,
                    "inline_total_amount": sample_amount,
                    "inline_total_pct": sample_pct,
                    "week_52_amount": sample_amount,
                    "week_52_pct": sample_pct,
                    "no_sales_amount": sample_amount,
                    "no_sales_pct": sample_pct,
                    "excess_total_amount": sample_amount,
                    "excess_total_pct": sample_pct,
                }
            )
        inline_excess_totals = {
            "new_amount": sample_amount,
            "new_pct": sample_pct,
            "inline_0_52_amount": sample_amount,
            "inline_0_52_pct": sample_pct,
            "inline_total_amount": sample_amount,
            "inline_total_pct": sample_pct,
            "week_52_amount": sample_amount,
            "week_52_pct": sample_pct,
            "no_sales_amount": sample_amount,
            "no_sales_pct": sample_pct,
            "excess_total_amount": sample_amount,
            "excess_total_pct": sample_pct,
        }

    top_sku_rows = []
    sku_query = HistoricalTop20SKUsRow.objects.filter(borrower=borrower)
    sku_query = _apply_division_filter(sku_query)
    sku_query = _apply_date_filter(sku_query, "as_of_date")
    latest_sku_row = sku_query.order_by("-as_of_date", "-created_at", "-id").first()
    if latest_sku_row and latest_sku_row.as_of_date:
        sku_rows = list(
            sku_query.filter(as_of_date=latest_sku_row.as_of_date)
            .order_by("-pct_of_total", "id")[:20]
        )
    else:
        sku_rows = list(sku_query.order_by("-created_at", "-id")[:20])

    if sku_rows:
        for row in sku_rows:
            top_sku_rows.append(
                {
                    "item_number": _format_item_number(row.item_number),
                    "category": row.category or "—",
                    "description": row.description or "—",
                    "cost": _format_currency(row.cost),
                    "pct_of_total": _format_pct(row.pct_of_total),
                    "cogs": _format_currency(row.cogs),
                    "gm": _format_currency(row.gm),
                    "gm_pct": _format_pct(row.gm_pct),
                    "wos": _format_wos(row.wos),
                }
            )
    else:
        sample_desc = [
            "Premium Maple W...",
            "Solid Core Interior Door",
            "6-Panel Exterior Door",
            "Engineered Hardwood",
            "Laminate Flooring Bundle",
            "Bamboo Flooring",
            "Single Hung Window",
            "Double Hung Window",
            "Ceramic Tile 12x24",
            "Concrete Mix Bag",
            "Asphalt Shingles",
            "Synthetic Underlay...",
            "Roof Ridge Vent",
            "Decorative Trim 8ft",
            "Colonial Baseboard",
            "Shoe Moulding 4ft",
            "Composite Deck Board",
            "Pressure-Treated W...",
            "Outdoor Trim",
            "Bamboo Plank Flooring",
        ]
        for desc in sample_desc:
            top_sku_rows.append(
                {
                    "item_number": "128986",
                    "category": "Cabinets",
                    "description": desc,
                    "cost": "32",
                    "pct_of_total": "0.1%",
                    "cogs": "1,175",
                    "gm": "525",
                    "gm_pct": "30.9%",
                    "wos": "4.2",
                }
            )

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
        "finished_goals_sales_insights": sales_insights,
        "finished_goals_highlights": highlights,
        "finished_goals_chart_config": chart_config,
        "finished_goals_chart_config_json": json.dumps(chart_config),
        "finished_goals_inline_excess_by_category": inline_excess_by_category,
        "finished_goals_inline_excess_totals": inline_excess_totals,
        "finished_goals_top_skus": top_sku_rows,
        "finished_goals_ar_concentration": ar_concentration,
        "finished_goals_ineligible_detail": ineligible_detail_rows,
        "finished_goals_ar_aging": {
            "buckets": share_labels,
            "amounts": bucket_amounts,
            "shares": bucket_shares,
            "total_amount": _format_currency(inventory_total),
            "total_share": "100%",
        },
        "finished_goals_stock": stock_data,
        "finished_goals_range_options": base_context["finished_goals_range_options"],
        "finished_goals_selected_range": base_context["finished_goals_selected_range"],
        "finished_goals_division_options": base_context["finished_goals_division_options"],
        "finished_goals_selected_division": base_context["finished_goals_selected_division"],
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
        "other_collateral_value_trend_config": {
            "title": "Value Trend",
            "labels": [],
            "estimated": [],
            "appraisal": [],
        },
        "other_collateral_value_analysis_rows": [],
        "other_collateral_asset_rows": [],
    }

    equipment_rows = list(
        MachineryEquipmentRow.objects.filter(borrower=borrower).order_by("created_at", "id")
    )
    if not equipment_rows:
        return base_context

    snapshots = OrderedDict()
    for row in equipment_rows:
        ts = row.created_at.date() if row.created_at else row.id
        snapshots.setdefault(ts, []).append(row)

    if not snapshots:
        return base_context

    snapshot_keys = sorted(snapshots.keys(), key=lambda key: key)
    latest_key = snapshot_keys[-1]
    latest_rows = snapshots[latest_key]
    prev_rows = snapshots[snapshot_keys[-2]] if len(snapshot_keys) > 1 else []

    def _aggregate(rows):
        total_fmv = sum(_to_decimal(row.fair_market_value) for row in rows)
        total_olv = sum(_to_decimal(row.orderly_liquidation_value) for row in rows)
        return total_fmv, total_olv

    total_fmv, total_olv = _aggregate(latest_rows)
    prev_total_fmv, prev_total_olv = _aggregate(prev_rows) if prev_rows else (None, None)
    estimated_fmv_total = total_fmv * Decimal("0.97")
    estimated_olv_total = total_olv * Decimal("0.95")

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

    def _label_from_timestamp(ts):
        if hasattr(ts, "strftime"):
            return ts.strftime("%b %y")
        return str(ts)

    max_points = 12
    values = []
    for key in snapshot_keys:
        rows = snapshots[key]
        fmv, olv = _aggregate(rows)
        values.append(
            {
                "label": _label_from_timestamp(key),
                "olv": float(olv),
            }
        )
    values = values[-max_points:]
    labels = [entry["label"] for entry in values]
    appraisal_series = [entry["olv"] for entry in values]
    estimated_series = [entry["olv"] * 0.96 for entry in values]
    chart_config = {
        "title": "Value Trend",
        "labels": labels,
        "estimated": [float(v) for v in estimated_series],
        "appraisal": [float(v) for v in appraisal_series],
    } if labels else base_context["other_collateral_value_trend_config"]

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

    nolv_entries = list(NOLVTableRow.objects.filter(borrower=borrower).order_by("-date", "-id"))
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
