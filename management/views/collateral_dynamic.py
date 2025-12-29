import json
import math
from collections import OrderedDict
from datetime import date, datetime, timedelta

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from management.models import (
    ARMetricsRow,
    AgingCompositionRow,
    AvailabilityForecastRow,
    BorrowerReport,
    CashFlowForecastRow,
    CashForecastRow,
    CollateralOverviewRow,
    ConcentrationADODSORow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,
    FGIneligibleDetailRow,
    FGCompositionRow,
    FGInventoryMetricsRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    FGGrossRecoveryHistoryRow,
    HistoricalTop20SKUsRow,
    ForecastRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    RMCategoryHistoryRow,
    RMTop20HistoryRow,
    NOLVTableRow,
    RMIneligibleOverviewRow,
    RiskSubfactorsRow,
    SalesGMTrendRow,
    SnapshotSummaryRow,
    WIPCategoryHistoryRow,
    WIPIneligibleOverviewRow,
    WIPTop20HistoryRow,
)
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
    _format_date,
    _safe_str,
    _to_decimal,
    get_snapshot_summary_map,
    get_borrower_status_context,
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

    finished_goals_range = request.GET.get("finished_goals_range", "last_12_months")
    finished_goals_division = request.GET.get(
        "finished_goals_division",
        request.GET.get("finished_goals_view", "all"),
    )
    ar_range = request.GET.get("ar_range", "last_12_months")
    ar_division = request.GET.get("ar_division", "all")
    raw_materials_range = request.GET.get("raw_materials_range", "last_12_months")
    raw_materials_division = request.GET.get("raw_materials_division", "all")
    work_in_progress_range = request.GET.get("work_in_progress_range", "last_12_months")
    work_in_progress_division = request.GET.get("work_in_progress_division", "all")

    snapshot_sections = [
        SnapshotSummaryRow.SECTION_ACCOUNTS_RECEIVABLE,
        SnapshotSummaryRow.SECTION_INVENTORY_SUMMARY,
        SnapshotSummaryRow.SECTION_OTHER_COLLATERAL,
    ]
    snapshot_map = get_snapshot_summary_map(borrower, snapshot_sections)

    inline_excess_pad_ratio = None
    pad_override = request.GET.get("inline_excess_pad")
    if pad_override:
        try:
            pad_value = float(pad_override)
        except (TypeError, ValueError):
            pad_value = None
        if pad_value in (0.05, 0.1, 0.10):
            inline_excess_pad_ratio = pad_value

    inventory_trend_pad_ratio = None
    inventory_pad_override = request.GET.get("inventory_trend_pad")
    if inventory_pad_override:
        try:
            pad_value = float(inventory_pad_override)
        except (TypeError, ValueError):
            pad_value = None
        if pad_value in (0.05, 0.1, 0.10):
            inventory_trend_pad_ratio = pad_value

    context = {
        "borrower_summary": _build_borrower_summary(borrower),
        "active_section": section,
        "inventory_tab": inventory_tab,
        "active_tab": "collateral_dynamic",
        **get_borrower_status_context(request),
        **_inventory_context(
            borrower,
            snapshot_text=snapshot_map.get(SnapshotSummaryRow.SECTION_INVENTORY_SUMMARY),
        ),
        **_accounts_receivable_context(
            borrower,
            ar_range,
            ar_division,
            snapshot_summary=snapshot_map.get(SnapshotSummaryRow.SECTION_ACCOUNTS_RECEIVABLE),
        ),
        **_finished_goals_context(
            borrower,
            finished_goals_range,
            finished_goals_division,
            inline_excess_pad_ratio=inline_excess_pad_ratio,
            inventory_trend_pad_ratio=inventory_trend_pad_ratio,
        ),
        **_raw_materials_context(borrower, raw_materials_range, raw_materials_division),
        **_work_in_progress_context(borrower, work_in_progress_range, work_in_progress_division),
        **_other_collateral_context(
            borrower,
            snapshot_summary=snapshot_map.get(SnapshotSummaryRow.SECTION_OTHER_COLLATERAL),
        ),
        **_liquidation_model_context(borrower),
    }
    return render(request, "collateral_dynamic/accounts_receivable.html", context)


@login_required(login_url="login")
def collateral_static_view(request):
    borrower = get_preferred_borrower(request)
    context = {
        "active_tab": "collateral_static",
        **get_borrower_status_context(request),
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
    snapshot_map = get_snapshot_summary_map(
        borrower,
        [SnapshotSummaryRow.SECTION_WEEK_SUMMARY],
    )
    snapshot_summary = snapshot_map.get(SnapshotSummaryRow.SECTION_WEEK_SUMMARY)

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

    def _collect_top_receipts(rows, limit=5, forecast_row=None, total_receipts=None, concentration_rows=None):
        def _row_amount(row):
            if row is None:
                return Decimal("0")
            if getattr(row, "actual", None) is not None:
                return _to_decimal(row.actual)
            if getattr(row, "projected", None) is not None:
                return _to_decimal(row.projected)
            return Decimal("0")

        def _is_receipt_row(row):
            category = (row.category or "").lower() if getattr(row, "category", None) else ""
            return any(keyword in category for keyword in ("receipt", "collection", "customer"))

        def _is_spend_row(row):
            category = (row.category or "").lower() if getattr(row, "category", None) else ""
            spend_terms = (
                "disbursement",
                "payroll",
                "rent",
                "utilities",
                "tax",
                "insurance",
                "professional",
                "service",
                "maintenance",
                "operating",
                "non-operating",
                "net cash",
            )
            return any(term in category for term in spend_terms)

        receipts_amount = total_receipts
        if receipts_amount is None and forecast_row:
            receipts_amount = _to_decimal(getattr(forecast_row, "net_sales", None) or 0) + _to_decimal(
                getattr(forecast_row, "ar", None) or 0
            )

        if concentration_rows:
            top_customers = sorted(
                concentration_rows,
                key=lambda r: _to_decimal(getattr(r, "current_concentration_pct", None)),
                reverse=True,
            )[:limit]
            weights = []
            for row in top_customers:
                weight = _to_decimal(getattr(row, "current_concentration_pct", None))
                if weight > Decimal("1"):
                    weight /= Decimal("100")
                weights.append(max(weight, Decimal("0")))
            total_weight = sum(weights)
            if total_weight <= 0:
                weights = [Decimal("1") for _ in top_customers]
                total_weight = Decimal(len(top_customers))
            output = []
            for idx, row in enumerate(top_customers):
                ratio = weights[idx] / total_weight if total_weight else Decimal("0")
                amount_val = receipts_amount * ratio if receipts_amount is not None else Decimal("0")
                name = _safe_str(getattr(row, "customer", None), default=f"Customer {idx + 1}")
                output.append({"name": name, "value": _format_money(amount_val)})
            while len(output) < limit:
                output.append({"name": f"Customer {len(output) + 1}", "value": _format_money(Decimal("0"))})
            return output

        candidates = [row for row in rows if _is_receipt_row(row) and not _is_spend_row(row)]
        if not candidates:
            candidates = [row for row in rows if getattr(row, "category", None) and not _is_spend_row(row)]
        sorted_rows = sorted(
            candidates,
            key=lambda row: _row_amount(row),
            reverse=True,
        )
        output = []
        for row in sorted_rows[:limit]:
            name = _safe_str(
                getattr(row, "category", None) or getattr(row, "customer", None),
                default="Customer",
            )
            amount = _format_money(_row_amount(row))
            output.append({"name": name, "value": amount})
        if not output and forecast_row:
            collections = getattr(forecast_row, "net_sales", None)
            receipts_total = _to_decimal(collections or 0) if collections is not None else None
            fallback_items = [
                ("Collections", collections),
                ("Total Receipts", receipts_total),
            ]
            for label, value in fallback_items:
                if value is not None:
                    output.append({"name": label, "value": _format_money(value)})
        while len(output) < limit:
            output.append({"name": "Receipt", "value": _format_money(Decimal("0"))})
        return output

    def _collect_top_spend(rows, limit=5):
        target_categories = [
            ("Payroll", ["payroll"]),
            ("Rent & Utility", ["rent", "utility", "utilities"]),
            ("Professional Services", ["professional"]),
            ("Debt Service", ["debt"]),
            ("Freight & Logistics", ["freight", "logistic"]),
        ]

        def _row_amount(row):
            if not row:
                return None
            if getattr(row, "actual", None) is not None:
                return _to_decimal(row.actual)
            if getattr(row, "projected", None) is not None:
                return _to_decimal(row.projected)
            return None

        def _is_spend_row(row):
            if not row or not row.category:
                return False
            category = row.category.lower()
            blocked_terms = ("receipt", "collection", "cash", "net", "total", "disbursement")
            return not any(term in category for term in blocked_terms)

        spend_pool = [row for row in rows if _is_spend_row(row)]
        # First pass: match by keywords to keep intended labels
        output = []
        used_rows = set()
        for label, keywords in target_categories[:limit]:
            match = next(
                (
                    row
                    for row in spend_pool
                    if row not in used_rows
                    and any(keyword in row.category.lower() for keyword in keywords)
                ),
                None,
            )
            amount_val = _row_amount(match)
            if match and amount_val is not None:
                used_rows.add(match)
            output.append({"name": label, "value": amount_val})

        # Second pass: fill any missing amounts with the highest remaining spend rows
        remaining_rows = [
            row for row in spend_pool if row not in used_rows and _row_amount(row) is not None
        ]
        remaining_rows.sort(key=lambda row: _row_amount(row) or Decimal("0"), reverse=True)
        for idx, entry in enumerate(output):
            if entry["value"] is None and remaining_rows:
                fill_row = remaining_rows.pop(0)
                output[idx]["value"] = _row_amount(fill_row)

        # Third pass: if still missing, allow any remaining rows (including totals) to avoid blanks
        if any(entry["value"] is None for entry in output):
            extra_rows = [
                row
                for row in rows
                if row not in used_rows and _row_amount(row) is not None
            ]
            extra_rows.sort(key=lambda row: _row_amount(row) or Decimal("0"), reverse=True)
            for idx, entry in enumerate(output):
                if entry["value"] is None and extra_rows:
                    fill_row = extra_rows.pop(0)
                    output[idx]["value"] = _row_amount(fill_row)

        while len(output) < limit:
            output.append({"name": "Expense", "value": Decimal("0")})

        return [
            {
                "name": item["name"],
                "value": _format_money(item["value"] if item["value"] is not None else Decimal("0")),
            }
            for item in output[:limit]
        ]

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
                    "collections": _pick_value(["net_sales", "available_collateral"]),
                    "disbursements": _pick_value(["loan_balance", "available_collateral"]),
                }
            )
        return values[-max_points:]

    def _build_cashflow_chart_rows(rows, week_fields):
        if not week_fields:
            week_fields = [f"week_{i}" for i in range(1, 14)]

        def _find_row(keywords):
            for row in rows:
                label = (getattr(row, "category", "") or "").strip().lower()
                if any(keyword in label for keyword in keywords):
                    return row
            return None

        def _row_values(row):
            values = []
            for field in week_fields:
                val = getattr(row, field, None) if row else None
                values.append(_to_decimal(val) if val is not None else Decimal("0"))
            return values

        collections_row = _find_row(["total receipts", "total receipt"])
        if not collections_row:
            collections_row = _find_row(["total collections", "collections", "collection"])

        disbursement_row = _find_row(
            ["total disbursements", "total disbursement"]
        )
        if not disbursement_row:
            disbursement_row = _find_row(["disbursements", "disbursement"])
        if not disbursement_row:
            disbursement_row = _find_row(
                ["operating disbursements", "non-operating disbursements"]
            )

        collections_values = _row_values(collections_row)
        disbursement_values = _row_values(disbursement_row)

        return [
            {
                "label": f"Week {idx + 1}",
                "collections": collections_values[idx] if idx < len(collections_values) else Decimal("0"),
                "disbursements": disbursement_values[idx] if idx < len(disbursement_values) else Decimal("0"),
            }
            for idx in range(len(week_fields))
        ]

    def _format_chart_label(value):
        if isinstance(value, str):
            return value
        if hasattr(value, "strftime"):
            return value.strftime("%b %d")
        return "Week"

    def _format_liquidity_label(value, year_override=None, fallback_date=None):
        label_date = value if hasattr(value, "strftime") else fallback_date
        if not label_date:
            return "—"
        if year_override:
            try:
                label_date = label_date.replace(year=year_override)
            except ValueError:
                label_date = label_date.replace(year=year_override, day=28)
        return label_date.strftime("%b %Y")

    def _liquidity_year_offset(values, base_date):
        if not base_date:
            return 0
        first_date = next(
            (val for val in values if hasattr(val, "year") and hasattr(val, "month")),
            None,
        )
        if not first_date:
            return 0
        diff_months = (first_date.year - base_date.year) * 12 + (first_date.month - base_date.month)
        if diff_months > 6:
            return -1
        if diff_months < -6:
            return 1
        return 0

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

    def _build_chart_bars(
        rows,
        label_texts=None,
        width=1080,
        height=300,
        left=80,
        right=50,
        top=30,
        bottom=60,
    ):
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
        bar_gap = 6
        bar_width = min(12, max(6, (group_width - bar_gap) / 2))
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
            if label_texts and idx < len(label_texts):
                label_text = label_texts[idx]
            else:
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
        "cashflow_empty_state": "",
        "cashforecast_empty_state": "",
        "cashflow_table_colspan": 0,
        "cashflow_cash_colspan": 0,
        "availability_actual_label": "Actual",
        "availability_week_labels": [f"Week {i}" for i in range(1, 14)],
        "availability_rows": [],
        "liquidity_series": [],
        "liquidity_labels": [],
        "liquidity_ticks": [],
        "liquidity_legend": [],
        "variance_current_rows": [],
        "variance_cumulative_rows": [],
        "snapshot_summary": snapshot_summary,
    }

    default_weeks = 13

    if not borrower:
        context["cashflow_empty_state"] = "Please select a borrower to view forecast data."
        context["cashforecast_empty_state"] = "Please select a borrower to view forecast data."
        context["cashflow_table_colspan"] = default_weeks + 3
        context["cashflow_cash_colspan"] = default_weeks + 2
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

    concentration_qs = ConcentrationADODSORow.objects.filter(borrower=borrower)
    latest_concentration = (
        concentration_qs.exclude(as_of_date__isnull=True)
        .order_by("-as_of_date", "-created_at", "-id")
        .first()
    )
    if latest_concentration and latest_concentration.as_of_date:
        concentration_rows = list(
            concentration_qs.filter(as_of_date=latest_concentration.as_of_date).order_by("id")
        )
    else:
        concentration_rows = list(concentration_qs.order_by("id"))

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

    report_qs = BorrowerReport.objects.filter(borrower=borrower).order_by(
        "-report_date",
        "-created_at",
        "-id",
    )
    latest_report = report_qs.exclude(report_date__isnull=True).first() or report_qs.first()

    cashflow_rows = []
    cash_rows = []
    cashflow_report_date = None

    if latest_report:
        cashflow_rows = list(
            CashFlowForecastRow.objects.filter(report=latest_report).order_by("id")
        )
        cash_rows = list(
            CashForecastRow.objects.filter(report=latest_report).order_by("id")
        )
        cashflow_report_date = latest_report.report_date
    else:
        latest_cashflow = (
            CashFlowForecastRow.objects.filter(report__borrower=borrower)
            .order_by("-date", "-created_at", "-id")
            .first()
        )
        if latest_cashflow and latest_cashflow.date:
            cashflow_rows = list(
                CashFlowForecastRow.objects.filter(
                    report__borrower=borrower,
                    date=latest_cashflow.date,
                ).order_by("id")
            )
            cashflow_report_date = latest_cashflow.date
        else:
            cashflow_rows = list(
                CashFlowForecastRow.objects.filter(report__borrower=borrower).order_by("id")
            )

        latest_cash = (
            CashForecastRow.objects.filter(report__borrower=borrower)
            .order_by("-date", "-created_at", "-id")
            .first()
        )
        if latest_cash and latest_cash.date:
            cash_rows = list(
                CashForecastRow.objects.filter(
                    report__borrower=borrower,
                    date=latest_cash.date,
                ).order_by("id")
            )
            if not cashflow_report_date:
                cashflow_report_date = latest_cash.date
        else:
            cash_rows = list(
                CashForecastRow.objects.filter(report__borrower=borrower).order_by("id")
            )

    report_date_candidates = []
    if latest_forecast:
        report_date_candidates.append(latest_forecast.as_of_date or latest_forecast.period)
    if latest_cw:
        report_date_candidates.append(latest_cw.date)
    if latest_cum:
        report_date_candidates.append(latest_cum.date)
    if latest_availability:
        report_date_candidates.append(latest_availability.date)
    if cashflow_report_date:
        report_date_candidates.append(cashflow_report_date)
    report_date = next((val for val in report_date_candidates if val), None)
    summary_map = [
        ("Beginning Cash", ["beginning cash"]),
        ("Total Receipts", ["total receipts"]),
        ("Total Disbursement", ["total disbursement", "total disbursements"]),
        ("Net Cash Flow", ["net cash flow"]),
        ("Ending Cash", ["ending cash"]),
    ]
    def _stat_value_from_row(row):
        if not row:
            return None
        if getattr(row, "actual", None) is not None:
            return _to_decimal(row.actual)
        if getattr(row, "projected", None) is not None:
            return _to_decimal(row.projected)
        return None

    stat_values = {}
    for label, keywords in summary_map:
        row = _find_variance_row(cw_rows, keywords)
        stat_values[label] = _stat_value_from_row(row)

    def _stat_delta(label, keywords):
        row = _find_variance_row(cw_rows, keywords)
        pct = None
        if row:
            pct_val = getattr(row, "variance_pct", None)
            if pct_val is not None:
                pct = _to_decimal(pct_val)
                if abs(pct) < Decimal("1"):
                    pct *= Decimal("100")
            else:
                actual = getattr(row, "actual", None)
                projected = getattr(row, "projected", None)
                if projected is not None and _to_decimal(projected) != 0:
                    pct = (_to_decimal(actual or 0) - _to_decimal(projected)) / _to_decimal(projected) * Decimal("100")
        if pct is None:
            pct = Decimal("0")
        delta_class = "up" if pct > 0 else "down" if pct < 0 else ""
        symbol = "▲" if pct > 0 else "▼" if pct < 0 else ""
        value = f"{abs(pct):.2f}%"
        text = f"{symbol} {value}" if symbol else value
        return text, delta_class

    def _sum_present(values):
        total = Decimal("0")
        has_value = False
        for val in values:
            if val is None:
                continue
            total += _to_decimal(val)
            has_value = True
        return total if has_value else None

    sorted_forecast_rows = _sort_forecast_rows(forecast_rows)
    column_entries, ordered_forecast_rows = _prepare_column_entries(sorted_forecast_rows)
    chart_rows = []
    chart_week_labels = []
    actual_bars = []
    forecast_bars = []
    chart_labels = []
    chart_ticks = []

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

    base_beginning = (
        _to_decimal(getattr(base_forecast_row, "available_collateral", None))
        if base_forecast_row and getattr(base_forecast_row, "available_collateral", None) is not None
        else None
    )
    base_receipts = (
        _sum_present([getattr(base_forecast_row, "net_sales", None), getattr(base_forecast_row, "ar", None)])
        if base_forecast_row
        else None
    )
    base_disbursements = (
        _to_decimal(getattr(base_forecast_row, "loan_balance", None))
        if base_forecast_row and getattr(base_forecast_row, "loan_balance", None) is not None
        else None
    )

    if stat_values.get("Total Receipts") is None and base_receipts is not None:
        stat_values["Total Receipts"] = base_receipts

    if stat_values.get("Total Disbursement") is None and base_disbursements is not None:
        stat_values["Total Disbursement"] = base_disbursements

    if stat_values.get("Beginning Cash") is None and base_beginning is not None:
        stat_values["Beginning Cash"] = base_beginning

    receipts_val = stat_values.get("Total Receipts")
    disbursement_val = stat_values.get("Total Disbursement")
    net_cash_val = stat_values.get("Net Cash Flow")
    if net_cash_val is None and (receipts_val is not None or disbursement_val is not None):
        net_cash_val = (receipts_val or Decimal("0")) - (disbursement_val or Decimal("0"))
        stat_values["Net Cash Flow"] = net_cash_val

    if stat_values.get("Ending Cash") is None:
        if stat_values.get("Beginning Cash") is not None and stat_values.get("Net Cash Flow") is not None:
            stat_values["Ending Cash"] = stat_values["Beginning Cash"] + stat_values["Net Cash Flow"]
        elif base_beginning is not None:
            stat_values["Ending Cash"] = base_beginning

    stats = [
        {"label": label, "value": _format_money(stat_values.get(label))}
        for label, _ in summary_map
    ]

    def _get_column_value(accessor, index):
        if not column_entries or index >= len(column_entries):
            return None
        row = column_entries[index]["row"]
        if not row or not accessor:
            return None
        value = accessor(row)
        return _to_decimal(value) if value is not None else None

    def _build_table_row(label, accessor=None, row_class=""):
        def _normalize(val):
            return _to_decimal(val) if val is not None else Decimal("0")

        actual_val = _normalize(_get_column_value(accessor, 0))
        forecast_vals = [
            _normalize(_get_column_value(accessor, idx + 1))
            for idx in range(max(0, len(column_entries) - 1))
        ]
        total_val = sum([actual_val] + forecast_vals, Decimal("0"))
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
        receipts = _sum_fields(row, ["net_sales"])
        disbursements = _value_for_field(row, "loan_balance")
        net_cash_flow = _difference_fields(row, ["net_sales"], ["loan_balance"])
        if beginning is not None and net_cash_flow is not None:
            ending = beginning + net_cash_flow
        elif net_cash_flow is not None:
            ending = net_cash_flow
        else:
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

    # Allocate disbursements across category rows using current-week variance weights when available
    disbursement_rows = [
        row
        for row in cw_rows
        if row.category
        and not any(keyword in row.category.lower() for keyword in ("receipt", "collection", "net cash", "total"))
    ]
    total_disb_weight = sum(
        (_to_decimal(getattr(row, "actual", None) or getattr(row, "projected", None)) for row in disbursement_rows),
        Decimal("0"),
    )
    weight_map = {}
    for row in disbursement_rows:
        amount = _to_decimal(getattr(row, "actual", None) or getattr(row, "projected", None))
        if amount < 0:
            amount = Decimal("0")
        label = (row.category or "").strip().lower()
        weight_map[label] = amount

    def _alloc_disbursement(label, total_value):
        if total_value is None:
            return None
        label_key = label.strip().lower()
        weight = weight_map.get(label_key)
        if weight is None and total_disb_weight > 0:
            # try partial match
            for key, val in weight_map.items():
                if label_key in key or key in label_key:
                    weight = val
                    break
        if weight is None:
            weight = Decimal("1")
        denom = total_disb_weight if total_disb_weight > 0 else Decimal(str(len(weight_map) or 1))
        return _to_decimal(total_value) * (weight / denom)

    cashflow_table_rows = [
        _section_row("Receipts"),
        _build_table_row("Collections", lambda row: _value_for_field(row, "net_sales"), ""),
        _build_table_row(
            "Total Receipts",
            lambda row: _sum_fields(row, ["net_sales"]),
            "title-row",
        ),
        _section_row("Operating Disbursements"),
        _build_table_row("Payroll", lambda row: _alloc_disbursement("payroll", _value_for_field(row, "loan_balance")), ""),
        _build_table_row("Professional Services", lambda row: _alloc_disbursement("professional services", _value_for_field(row, "loan_balance")), ""),
        _build_table_row("Software Expenses", lambda row: _alloc_disbursement("software expenses", _value_for_field(row, "loan_balance")), ""),
        _build_table_row("Repairs / Maintenance", lambda row: _alloc_disbursement("repairs / maintenance", _value_for_field(row, "loan_balance")), ""),
        _build_table_row("Other Disbursements", lambda row: _alloc_disbursement("other disbursements", _value_for_field(row, "loan_balance")), ""),
        _build_table_row(
            "Total Operating Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        _section_row("Non-Operating Disbursements"),
        _build_table_row("Total Non-Operating Disbursements", lambda row: _alloc_disbursement("non-operating disbursements", _value_for_field(row, "loan_balance")), "title-row"),
        _build_table_row(
            "Total Disbursements",
            lambda row: _value_for_field(row, "loan_balance"),
            "title-row",
        ),
        _build_table_row(
            "Net Cash Flow",
            lambda row: _difference_fields(row, ["net_sales"], ["loan_balance"]),
            "title-row",
        ),
    ]
    cashflow_cash_defs = [
        ("Beginning Cash", lambda row: _value_for_field(row, "available_collateral"), ""),
        (
            "Net Cash Flow",
            lambda row: _difference_fields(row, ["net_sales"], ["loan_balance"]),
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

    def _resolve_week_fields(rows, default_weeks=13):
        week_fields = [f"week_{i}" for i in range(1, 14)]
        max_week = 0
        for idx, field in enumerate(week_fields, 1):
            if any(getattr(row, field, None) is not None for row in rows):
                max_week = idx
        if max_week == 0:
            max_week = default_weeks
        return week_fields[:max_week]

    def _sum_optional(values):
        total = Decimal("0")
        has_value = False
        for val in values:
            if val is None:
                continue
            total += _to_decimal(val)
            has_value = True
        return total if has_value else None

    def _cashflow_row_class(label):
        label_lower = (label or "").strip().lower()
        if label_lower in {
            "receipts",
            "operating disbursements",
            "non-operating disbursements",
        }:
            return "section-row"
        if "total" in label_lower or "net cash flow" in label_lower or "ending cash" in label_lower:
            return "title-row"
        return ""

    def _build_cash_rows(rows, week_fields, total_field=None):
        output = []
        for row in rows:
            label = _safe_str(getattr(row, "category", None), default="—")
            actual_val = getattr(row, "x", None)
            forecasts = [getattr(row, field, None) for field in week_fields]
            total_val = getattr(row, total_field, None) if total_field else None
            if total_val is None:
                total_val = _sum_optional([actual_val] + forecasts)
            output.append(
                {
                    "label": label,
                    "actual": _format_money(actual_val),
                    "forecasts": [_format_money(val) for val in forecasts],
                    "total": _format_money(total_val),
                    "row_class": _cashflow_row_class(label),
                }
            )
        return output

    cashflow_week_fields = _resolve_week_fields(cashflow_rows)
    cash_week_fields = _resolve_week_fields(cash_rows)
    max_weeks = max(len(cashflow_week_fields), len(cash_week_fields))
    week_fields = [f"week_{i}" for i in range(1, max_weeks + 1)]

    cashflow_table_rows = _build_cash_rows(
        cashflow_rows,
        week_fields,
        total_field="total",
    )
    cashflow_cash_rows = _build_cash_rows(cash_rows, week_fields)

    def _normalize_label(value):
        text = (value or "").strip().lower()
        cleaned = []
        last_space = False
        for char in text:
            if char.isalnum():
                cleaned.append(char)
                last_space = False
            else:
                if not last_space:
                    cleaned.append(" ")
                    last_space = True
        return "".join(cleaned).strip()

    variance_label_map = {}
    variance_order = [
        _normalize_label(row.get("label"))
        for row in cashflow_table_rows
        if row.get("label")
    ]
    current_section = None
    for row in cashflow_table_rows:
        label = row.get("label")
        norm = _normalize_label(label)
        entry = variance_label_map.setdefault(
            norm or label,
            {
                "label": label,
                "row_class": row.get("row_class") or "",
                "children": [],
            },
        )
        if (row.get("row_class") or "") == "section-row":
            current_section = norm
        elif current_section:
            parent_entry = variance_label_map.get(current_section)
            if parent_entry is not None:
                if norm not in parent_entry["children"]:
                    parent_entry["children"].append(norm)
    if not variance_order:
        variance_order = [
            _normalize_label(label)
            for label in [
                "Receipts",
                "Collections",
                "Total Receipts",
                "Operating Disbursements",
                "Payroll",
                "Professional Services",
                "Software Expenses",
                "Repairs / Maintenance",
                "Other Disbursements",
                "Total Operating Disbursements",
                "Non-Operating Disbursements",
                "Total Non-Operating Disbursements",
                "Total Disbursements",
                "Net Cash Flow",
            ]
        ]

    actual_date = None
    if cashflow_rows:
        actual_date = cashflow_rows[0].date or cashflow_report_date
    elif cash_rows:
        actual_date = cash_rows[0].date or cashflow_report_date

    if actual_date:
        cashflow_actual_label = f"Actual<br/>{_format_date(actual_date)}"
        cashflow_forecast_labels = [
            f"Forecast<br/>Week {idx} {_format_date(actual_date + timedelta(days=7 * idx))}"
            for idx in range(1, len(week_fields) + 1)
        ]
    else:
        cashflow_actual_label = "Actual"
        cashflow_forecast_labels = [f"Forecast<br/>Week {idx}" for idx in range(1, len(week_fields) + 1)]

    chart_week_fields = [f"week_{i}" for i in range(1, 14)]
    chart_rows = _build_cashflow_chart_rows(cashflow_rows, chart_week_fields)
    chart_week_labels = [row["label"] for row in chart_rows]
    actual_bars, forecast_bars, chart_labels, chart_ticks = _build_chart_bars(
        chart_rows,
        label_texts=chart_week_labels,
    )

    context["cashflow_table_colspan"] = len(week_fields) + 3
    context["cashflow_cash_colspan"] = len(week_fields) + 2

    if not cashflow_table_rows:
        context["cashflow_empty_state"] = "No forecast data available. Please import the Excel file."
    if not cashflow_cash_rows:
        context["cashforecast_empty_state"] = "No forecast data available. Please import the Excel file."

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
        ("available_collateral", "Collateral Availability", "#0ea5e9"),
        ("revolver_availability", "Revolver Availability", "#7c3aed"),
        ("net_sales", "Revolver Availability + Cash", "#1d4ed8"),
    ]
    liquidity_series = []
    liquidity_labels = []
    liquidity_ticks = []
    liquidity_legend = []
    trend_rows = ordered_forecast_rows[-len(TREND_X_POSITIONS) :]
    if not trend_rows:
        trend_rows = ordered_forecast_rows[-1:] if ordered_forecast_rows else sorted_forecast_rows[-1:]
    period_values = [
        getattr(row, "period", None)
        or getattr(row, "as_of_date", None)
        or getattr(getattr(row, "report", None), "report_date", None)
        for row in trend_rows
    ]
    current_year = date.today().year
    base_date = report_date or date.today()
    period_labels = [
        _format_liquidity_label(
            value,
            year_override=current_year,
            fallback_date=base_date + timedelta(days=7 * idx),
        )
        for idx, value in enumerate(period_values)
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
        chart = _build_liquidity_chart(series_values, period_labels, height=240)
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

    def _variance_rows(rows, label_map=None):
        label_map = label_map or {}
        section_headers = {
            "receipts",
            "operating disbursements",
            "non-operating disbursements",
        }

        def _build_entry(
            label,
            row_class="",
            projected="$—",
            actual="$—",
            variance_amount="$—",
            variance_pct="—%",
            raw_projected=None,
            raw_actual=None,
            raw_variance=None,
            raw_variance_pct=None,
        ):
            return {
                "category": label,
                "projected": projected,
                "actual": actual,
                "variance_amount": variance_amount,
                "variance_pct": variance_pct,
                "_projected": raw_projected,
                "_actual": raw_actual,
                "_variance": raw_variance,
                "_variance_pct": raw_variance_pct,
                "row_class": row_class,
            }

        label_keys = list(label_map.keys())

        def _match_label(norm_value):
            if not norm_value:
                return norm_value
            if norm_value in label_map:
                return norm_value
            for candidate in label_keys:
                if not candidate:
                    continue
                if candidate in norm_value or norm_value in candidate:
                    return candidate
            return norm_value

        normalized_entries = {}
        extras = []
        for row in rows:
            category = _safe_str(row.category, default="—")
            normalized = _match_label(_normalize_label(category))
            raw_projected = _to_decimal(row.projected)
            raw_actual = _to_decimal(row.actual)
            raw_variance = _to_decimal(row.variance)
            raw_variance_pct = _to_decimal(row.variance_pct) if getattr(row, "variance_pct", None) is not None else None
            proj = _format_money(raw_projected)
            actual = _format_money(raw_actual)
            variance_amount = _format_money(raw_variance)
            variance_pct = _format_pct(raw_variance_pct)
            category_lower = category.lower()
            row_class = ""
            if category_lower in section_headers:
                row_class = "section-row"
            elif "total" in category_lower or "net" in category_lower:
                row_class = "title-row"
            entry = _build_entry(
                category,
                row_class=row_class,
                projected=proj,
                actual=actual,
                variance_amount=variance_amount,
                variance_pct=variance_pct,
                raw_projected=raw_projected,
                raw_actual=raw_actual,
                raw_variance=raw_variance,
                raw_variance_pct=raw_variance_pct,
            )
            if normalized:
                normalized_entries.setdefault(normalized, []).append(entry)
            else:
                extras.append(entry)

        def _apply_label(entry, norm_key):
            mapped = label_map.get(norm_key)
            if mapped:
                entry["category"] = mapped.get("label") or entry["category"]
                mapped_class = mapped.get("row_class")
                if mapped_class:
                    entry["row_class"] = mapped_class
            return entry

        output = []
        ordered_keys = variance_order or list(normalized_entries.keys())
        ordered_keys = [_match_label(key) for key in ordered_keys]
        seen_keys = set()
        for norm_key in ordered_keys:
            if norm_key in seen_keys:
                continue
            seen_keys.add(norm_key)
            if norm_key in normalized_entries and normalized_entries[norm_key]:
                entry = normalized_entries[norm_key].pop(0)
                output.append(_apply_label(entry, norm_key))
                seen_keys.add(norm_key)
                if not normalized_entries[norm_key]:
                    normalized_entries.pop(norm_key, None)
            else:
                mapped = label_map.get(norm_key)
                if mapped:
                    output.append(
                        _build_entry(
                            mapped.get("label") or "—",
                            row_class=mapped.get("row_class") or "",
                        )
                    )
                elif norm_key:
                    output.append(_build_entry(norm_key.title()))

        for norm_key, entries in normalized_entries.items():
            for entry in entries:
                output.append(_apply_label(entry, norm_key))

        output.extend(extras)

        entry_lookup = {}
        for entry in output:
            norm = _match_label(_normalize_label(entry["category"]))
            if norm:
                entry_lookup.setdefault(norm, []).append(entry)

        cleaned_output = []
        for entry in output:
            norm = _match_label(_normalize_label(entry["category"]))
            map_entry = label_map.get(norm or "")
            if not map_entry:
                cleaned_output.append(entry)
                continue
            children = map_entry.get("children") or []
            if not children:
                cleaned_output.append(entry)
                continue
            child_entries = []
            for child_norm in children:
                child_entries.extend(entry_lookup.get(_match_label(child_norm)) or [])
            if not child_entries:
                continue

            def _sum_values(field):
                total = Decimal("0")
                has_value = False
                for child in child_entries:
                    value = child.get(field)
                    if value is None:
                        continue
                    total += value
                    has_value = True
                return total if has_value else None

            summed_projected = _sum_values("_projected")
            summed_actual = _sum_values("_actual")
            summed_variance = _sum_values("_variance")
            if summed_variance is None and summed_projected is not None and summed_actual is not None:
                summed_variance = summed_actual - summed_projected
            if summed_projected in (None, Decimal("0")) or summed_variance is None:
                summed_variance_pct = None
            else:
                summed_variance_pct = (summed_variance / summed_projected) * Decimal("100")

            entry["_projected"] = summed_projected
            entry["_actual"] = summed_actual
            entry["_variance"] = summed_variance
            entry["_variance_pct"] = summed_variance_pct
            entry["projected"] = _format_money(summed_projected)
            entry["actual"] = _format_money(summed_actual)
            entry["variance_amount"] = _format_money(summed_variance)
            entry["variance_pct"] = _format_pct(summed_variance_pct)

            def _has_values(inner_entry):
                return any(
                    inner_entry.get(field) not in (None, "$—", "—%")
                    for field in ("projected", "actual", "variance_amount", "variance_pct")
                )

            if _has_values(entry):
                cleaned_output.append(entry)
        output = cleaned_output

        if not output:
            output.append(
                _build_entry("—")
            )
        return output

    variance_current = _variance_rows(cw_rows, variance_label_map)
    variance_cumulative = _variance_rows(cum_rows, variance_label_map)

    context.update(
        {
            "stats": stats,
            "summary_cards": [
                {
                    "label": "Ending Cash",
                    "value": next((s["value"] for s in stats if s["label"] == "Ending Cash"), "—"),
                    "delta": _stat_delta("Ending Cash", ["ending cash"])[0],
                    "delta_class": _stat_delta("Ending Cash", ["ending cash"])[1],
                },
                {
                    "label": "Total Receipts",
                    "value": next((s["value"] for s in stats if s["label"] == "Total Receipts"), "—"),
                    "delta": _stat_delta("Total Receipts", ["total receipts"])[0],
                    "delta_class": _stat_delta("Total Receipts", ["total receipts"])[1],
                },
                {
                    "label": "Total Disbursement",
                    "value": next((s["value"] for s in stats if s["label"] == "Total Disbursement"), "—"),
                    "delta": _stat_delta("Total Disbursement", ["total disbursement", "total disbursements"])[0],
                    "delta_class": _stat_delta("Total Disbursement", ["total disbursement", "total disbursements"])[1],
                },
            ],
            "forecast_updated_label": _format_date(report_date) if report_date else "—",
            "snapshot_summary": snapshot_summary,
            "period_label": _format_date(actual_date or report_date)
            if actual_date or report_date
            else None,
            "top_spend": _collect_top_spend(cw_rows),
            "top_receipts": _collect_top_receipts(
                cw_rows,
                forecast_row=base_forecast_row,
                total_receipts=stat_values.get("Total Receipts"),
                concentration_rows=concentration_rows,
            ),
            "chart": {
                "collections_bars": actual_bars,
                "disbursement_bars": forecast_bars,
                "labels": chart_labels,
                "ticks": chart_ticks,
                "legend": [
                    {"label": "Collections", "color": "#1889E6"},
                    {"label": "Disbursements", "color": "#FC912E"},
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
CIRCUMFERENCE = Decimal(str(2 * math.pi * 52))

CATEGORY_CONFIG = [
    {
        "key": "finished_goods",
        "label": "Finished Goods",
        "match": ("finished", "finished goods", "finish goods", "finish-goods", "fg"),
        "bar_class": "navy",
        "color": "#116BFD",
    },
    {
        "key": "raw_materials",
        "label": "Raw Materials",
        "match": ("raw", "raw materials", "raw-materials", "raw_material"),
        "bar_class": "mid",
        "color": "#0753B2",
    },
    {
        "key": "work_in_progress",
        "label": "Work-in-Progress",
        "match": ("work", "work in progress", "work-in-progress", "wip"),
        "bar_class": "bright",
        "color": "#CADFEF",
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


def _build_trend_points(
    values,
    labels=None,
    width=520,
    height=210,
    left=50,
    top=50,
    bottom=40,
    min_value=None,
    max_value=None,
    tick_count=5,
    value_formatter=None,
):
    if not values:
        return {"points": "", "dots": [], "labels": []}
    float_values = [float(v if v is not None else 0.0) for v in values]
    total_width = width - left - 20
    step = total_width / max(1, len(float_values) - 1)
    baseline_y = height - bottom
    chart_height = baseline_y - top
    axis_min = min_value if min_value is not None else 0.0
    axis_max = max_value if max_value is not None else max(float_values + [100.0])
    if axis_max is None or axis_max <= axis_min:
        axis_max = axis_min + 1.0
    axis_range = axis_max - axis_min or 1.0
    formatter = value_formatter or (lambda v: f"{v:.0f}")

    points = []
    dots = []
    label_points = []
    for idx, value in enumerate(float_values):
        ratio = max(0.0, min(1.0, (value - axis_min) / axis_range))
        x = left + idx * step
        y = baseline_y - ratio * chart_height
        points.append(f"{x:.1f},{y:.1f}")
        dots.append({"cx": round(x, 1), "cy": round(y, 1)})
        label_text = labels[idx] if labels and idx < len(labels) else ""
        label_points.append({"x": round(x, 1), "text": label_text})

    ticks = []
    if tick_count > 1:
        for idx in range(tick_count):
            ratio = idx / (tick_count - 1)
            value = axis_max - axis_range * ratio
            y = top + chart_height * ratio
            ticks.append({"y": round(y, 1), "label": formatter(value)})
    return {
        "points": " ".join(points),
        "dots": dots,
        "labels": label_points,
        "ticks": ticks,
    }


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


def _inventory_state(borrower, start_date=None, end_date=None):
    if not borrower:
        return None

    collateral_qs = CollateralOverviewRow.objects.filter(borrower=borrower)
    if start_date and end_date:
        collateral_qs = collateral_qs.filter(created_at__date__range=(start_date, end_date))
    collateral_rows = list(collateral_qs.order_by("id"))
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


def _format_item_number_value(value):
    if value is None:
        return "—"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "—"
        try:
            dec = Decimal(text)
        except Exception:
            return text
    else:
        try:
            dec = Decimal(value)
        except Exception:
            try:
                dec = Decimal(str(value))
            except Exception:
                return str(value)
    try:
        if dec == dec.to_integral_value():
            return str(int(dec))
    except Exception:
        pass
    return f"{dec.normalize():f}"


def _format_compact_currency(value):
    if value is None:
        return "—"
    val = _to_decimal(value)
    sign = "-" if val < 0 else ""
    abs_val = abs(val)

    def _trim(value):
        text = f"{value:.1f}"
        return text.rstrip("0").rstrip(".")

    if abs_val >= Decimal("1000000000"):
        return f"{sign}${_trim(abs_val / Decimal('1000000000'))}B"
    if abs_val >= Decimal("1000000"):
        return f"{sign}${_trim(abs_val / Decimal('1000000'))}M"
    if abs_val >= Decimal("1000"):
        return f"{sign}${_trim(abs_val / Decimal('1000'))}k"
    return _format_currency(val)


def _inventory_context(borrower, snapshot_text=None):
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

    resolved_snapshot = snapshot_text or "No snapshot summary available."
    context = {
        "snapshot_text": resolved_snapshot,
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

    def _format_cost_pct(amount, base):
        if amount is None:
            return "—"
        base_val = _to_decimal(base)
        if base_val <= 0:
            return "—"
        return _format_pct(_to_decimal(amount) / base_val)

    inventory_breakdown = []
    for category in CATEGORY_CONFIG:
        metrics = category_metrics[category["key"]]
        if not metrics["has_data"]:
            inventory_breakdown.append(
                {
                    "label": category["label"],
                    "available_value": "—",
                    "gross_value": "—",
                    "gross_pct": "—",
                    "liquidation_value": "—",
                    "liquidation_pct": "—",
                    "net_value": "—",
                    "net_pct": "—",
                }
            )
            continue

        trend_pct = (
            (metrics["trend_numerator"] / metrics["trend_denominator"]) * Decimal("100")
            if metrics["trend_denominator"] > 0
            else None
        )
        liquidation_budget = metrics["pre_reserve"] or metrics["reserves"]
        liquidation_amount = None
        if liquidation_budget is not None:
            liquidation_amount = -_to_decimal(liquidation_budget)

        inventory_breakdown.append(
            {
                "label": category["label"],
                "available_value": _format_currency(metrics["eligible"]),
                "gross_value": _format_currency(metrics["beginning"]),
                "gross_pct": _format_cost_pct(metrics["beginning"], metrics["eligible"]),
                "liquidation_value": _format_currency(liquidation_amount),
                "liquidation_pct": _format_cost_pct(liquidation_amount, metrics["eligible"]),
                "net_value": _format_currency(metrics["net"]),
                "net_pct": _format_cost_pct(metrics["net"], metrics["eligible"]),
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
    bar_width = 8

    y_ticks = []
    for idx in range(tick_count):
        ratio = idx / (tick_count - 1)
        value = axis_max * Decimal(str(1 - ratio))
        y = top + plot_height * ratio
        y_ticks.append({"y": round(y, 1), "label": _format_short_currency(value)})

    x_labels = []
    x_grid = []
    columns = []
    bar_gap = 4.0
    for idx, label in enumerate(series_labels):
        x_center = left + idx * step_x
        x = x_center - bar_width / 2
        month_label, year_label = label.split(" ", 1) if " " in label else (label, "")
        x_labels.append({"x": round(x_center, 1), "month": month_label, "year": year_label})
        x_grid.append(round(x_center, 1))

        heights = []
        values = []
        for category in CATEGORY_CONFIG:
            value = series_values[category["key"]][idx] if series_values[category["key"]] else Decimal("0")
            height = float(_to_decimal(value) / axis_max) * plot_height
            heights.append(height)
            values.append(value)

        nonzero_indices = [i for i, height in enumerate(heights) if height > 0]
        total_height = sum(heights)
        gap_count = max(len(nonzero_indices) - 1, 0)
        gap = min(bar_gap, total_height / (gap_count + 1)) if gap_count and total_height > 0 else 0.0
        scale = ((total_height - (gap * gap_count)) / total_height) if total_height > 0 else 0.0

        stacked_height = 0.0
        column_bars = []
        for index, category in enumerate(CATEGORY_CONFIG):
            height = heights[index] * scale
            y = baseline_y - stacked_height - height
            column_bars.append(
                {
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "height": round(height, 1),
                    "width": bar_width,
                    "color": category["color"],
                    "series_label": category["label"],
                    "value_display": _format_currency(values[index]),
                    "month_label": label,
                }
            )
            stacked_height += height
            if index in nonzero_indices and index != nonzero_indices[-1]:
                stacked_height += gap
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
    chart_bottom = Decimal("192")
    chart_top = Decimal("22")
    chart_height = chart_bottom - chart_top

    pct_values = []
    pct_labels = {}
    for category in CATEGORY_CONFIG:
        metrics = category_metrics[category["key"]]
        eligible = metrics.get("eligible") or Decimal("0")
        pct_ratio = (metrics["net"] / eligible) if eligible else Decimal("0")
        pct_ratio = max(pct_ratio, Decimal("0"))
        pct_values.append(pct_ratio)
        pct_labels[category["key"]] = _format_pct(pct_ratio)

    if pct_values:
        min_pct = min(pct_values)
        max_pct = max(pct_values)
        pct_range = max_pct - min_pct
        padding = max(pct_range * Decimal("0.05"), Decimal("0.05"))
        axis_min_pct = max(min_pct - padding, Decimal("0"))
        axis_max_pct = min(max_pct + padding, Decimal("1"))
        if axis_max_pct <= axis_min_pct:
            axis_max_pct = axis_min_pct + Decimal("0.10")
            axis_max_pct = min(axis_max_pct, Decimal("1"))
    else:
        axis_min_pct = Decimal("0")
        axis_max_pct = Decimal("1")

    axis_range_pct = axis_max_pct - axis_min_pct if axis_max_pct != axis_min_pct else Decimal("1")

    for category in CATEGORY_CONFIG:
        pct_ratio = Decimal("0")
        for cat, value in zip(CATEGORY_CONFIG, pct_values):
            if cat["key"] == category["key"]:
                pct_ratio = value
                break
        pct_ratio = max(min(pct_ratio, axis_max_pct), axis_min_pct)
        normalized = (pct_ratio - axis_min_pct) / axis_range_pct if axis_range_pct else Decimal("0")
        y_value = chart_bottom - (normalized * chart_height)
        y_value = max(min(y_value, chart_bottom), chart_top)
        points = []
        points_list = []
        for idx, x in enumerate(TREND_X_POSITIONS):
            value_label = TREND_LABELS[idx] if idx < len(TREND_LABELS) else f"Point {idx+1}"
            points.append(f"{x},{float(y_value):.1f}")
            points_list.append(
                {
                    "x": x,
                    "y": float(y_value),
                    "label": value_label,
                    "value": pct_labels.get(category["key"], _format_pct(pct_ratio)),
                }
            )
        inventory_trend_series.append(
            {
                "color": category["color"],
                "points": " ".join(points),
                "points_list": points_list,
            }
        )

    return {
        "snapshot_text": resolved_snapshot,
        "inventory_available_display": inventory_available_display,
        "inventory_mix": inventory_mix,
        "inventory_breakdown": inventory_breakdown,
        "inventory_donut_segments": donut_segments,
        "inventory_mix_trend_chart": inventory_mix_trend_chart,
        "inventory_trend_series": inventory_trend_series,
    }

def _accounts_receivable_context(borrower, range_key="today", division="all", snapshot_summary=None):
    normalized_range = _normalize_range(range_key)
    normalized_division = _normalize_division(division)
    resolved_snapshot = snapshot_summary or "No snapshot summary available."
    base_context = {
        "ar_borrowing_base_kpis": [],
        "ar_aging_chart_buckets": [],
        "ar_current_vs_past_due_trend": {"bars": [], "labels": []},
        "ar_ineligible_overview_rows": [],
        "ar_ineligible_overview_total": None,
        "ar_ineligible_trend": {
            "points": "",
            "dots": [],
            "labels": [],
            "ticks": [],
            "series_values": [],
            "series_labels": [],
            "axis_min": 0.0,
            "axis_max": 100.0,
        },
        "ar_concentration_rows": [],
        "ar_ado_rows": [],
        "ar_dso_rows": [],
        "ar_range_options": RANGE_OPTIONS,
        "ar_selected_range": normalized_range,
        "ar_division_options": [{"value": "all", "label": "All Divisions"}],
        "ar_selected_division": normalized_division,
        "accounts_receivable_snapshot_summary": resolved_snapshot,
    }

    if not borrower:
        return base_context

    division_sources = [
        ARMetricsRow,
        AgingCompositionRow,
        ConcentrationADODSORow,
        IneligibleOverviewRow,
        IneligibleTrendRow,
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
        base_context["ar_division_options"] = [
            {"value": "all", "label": "All Divisions"},
            *(
                {"value": item, "label": item}
                for item in sorted(divisions)
            ),
        ]
        if normalized_division != "all" and normalized_division not in divisions:
            normalized_division = "all"
            base_context["ar_selected_division"] = normalized_division

    start_date, end_date = _range_dates(normalized_range)

    def _apply_date_filter(qs, field_name):
        if start_date and end_date:
            return qs.filter(**{f"{field_name}__range": (start_date, end_date)})
        return qs

    def _apply_division_filter(qs):
        if normalized_division != "all":
            return qs.filter(division__iexact=normalized_division)
        return qs

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
        _apply_date_filter(
            _apply_division_filter(ARMetricsRow.objects.filter(borrower=borrower)),
            "as_of_date",
        ).order_by("as_of_date", "created_at", "id")
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

    def _format_currency_millions(value):
        if value is None:
            return "—"
        val = _to_decimal(value)
        return f"${val:,.1f}M"

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

    def _format_axis_currency_millions(value):
        val = float(value)
        return f"${_trim_axis_value(val)}M"

    def _format_axis_days(value):
        return f"{int(round(value)):,}"

    def _format_axis_pct(value):
        return f"{_trim_axis_value(value)}%"

    def _pct_to_points(value):
        if value is None:
            return None
        pct = _to_decimal(value)
        if pct <= Decimal("1"):
            pct *= Decimal("100")
        return pct

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

    def _compute_axis(values, tick_count, pad_ratio=0.12, clamp_min=None, clamp_max=None):
        min_val = min(values)
        max_val = max(values)
        if min_val == max_val:
            pad = max(abs(min_val) * 0.1, 1.0)
            min_val -= pad
            max_val += pad
        else:
            pad = (max_val - min_val) * pad_ratio
            min_val -= pad
            max_val += pad
        if clamp_min is not None:
            min_val = max(min_val, clamp_min)
        if clamp_max is not None:
            max_val = min(max_val, clamp_max)
        if max_val <= min_val:
            max_val = min_val + 1.0
        step = _nice_step((max_val - min_val) / max(1, tick_count - 1))
        if step <= 0:
            step = 1.0
        axis_min = math.floor(min_val / step) * step
        axis_max = math.ceil(max_val / step) * step
        if axis_max - axis_min < step * (tick_count - 1):
            axis_max = axis_min + step * (tick_count - 1)
        if clamp_min is not None:
            axis_min = max(axis_min, clamp_min)
        if clamp_max is not None:
            axis_max = min(axis_max, clamp_max)
        if axis_max <= axis_min:
            axis_max = axis_min + step
        return axis_min, axis_max

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

    def _build_kpi_chart(values, labels, axis_formatter, value_formatter, pad_ratio=0.12, clamp_min=None, clamp_max=None):
        values, labels = _normalize_chart_values(values, labels)
        width = 260
        height = 140
        left = 55
        right = 12
        top = 16
        bottom = 26
        plot_width = width - left - right
        plot_height = height - top - bottom
        tick_count = 4
        axis_min, axis_max = _compute_axis(values, tick_count, pad_ratio, clamp_min, clamp_max)
        axis_range = axis_max - axis_min if axis_max != axis_min else 1.0
        if axis_max <= 0:
            axis_max = axis_min + axis_range
        step_x = plot_width / max(1, len(values) - 1)
        baseline_y = top + plot_height
        points = []
        dots = []
        x_positions = []
        x_labels = []
        for idx, value in enumerate(values):
            ratio = (value - axis_min) / axis_range if axis_range else 0
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
            value = axis_max - (axis_range * ratio)
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
            "label_x": left - 18,
            "label_y": round(baseline_y + 20, 1),
        }

    def _delta_payload(current, previous):
        if previous is None or previous == 0:
            return None
        curr = _to_decimal(current)
        prev = _to_decimal(previous)
        if prev == 0:
            return None
        diff = (curr - prev) / prev * Decimal("100")
        is_positive = diff >= 0
        value = f"{abs(diff):.1f}%"
        symbol = "▲" if is_positive else "▼"
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
            "chart_formatter": lambda value: _format_currency_millions(value),
            "scale": Decimal("1000000"),
            "axis_formatter": _format_axis_currency_millions,
            "pad_ratio": 0.14,
            "color": "var(--blue-3)",
            "icon": "images/balance.svg",
            "improvement_on_increase": True,
        },
        {
            "label": "Days Sales Outstanding",
            "key": "avg_dso",
            "formatter": lambda value: _format_days(value),
            "chart_formatter": lambda value: _format_days(value),
            "axis_formatter": _format_axis_days,
            "pad_ratio": 0.18,
            "clamp_min": 0,
            "color": "var(--purple)",
            "icon": "images/sales_outstanding.svg",
            "improvement_on_increase": False,
        },
        {
            "label": "% of total past due",
            "key": "past_due_pct",
            "formatter": lambda value: _format_pct_display(value),
            "chart_formatter": lambda value: _format_pct_display(value),
            "axis_formatter": _format_axis_pct,
            "pad_ratio": 0.2,
            "clamp_min": 0,
            "color": "var(--teal)",
            "icon": "images/total_pastdue_icon.svg",
            "improvement_on_increase": False,
        },
    ]
    kpis = []
    chart_points = 7
    chart_history = history[-chart_points:] if len(history) > chart_points else history[:]
    chart_labels = [f"{idx + 1:02d}" for idx in range(len(chart_history))]
    for spec in kpi_specs:
        series_values = [_to_decimal(row[spec["key"]]) for row in chart_history]
        scale = spec.get("scale") or Decimal("1")
        scaled_values = []
        for value in series_values:
            if spec["key"] == "past_due_pct":
                pct_value = _pct_to_points(value)
                scaled_values.append(float(pct_value) if pct_value is not None else 0.0)
            else:
                scaled_values.append(float(value / scale))
        chart = _build_kpi_chart(
            scaled_values,
            chart_labels,
            axis_formatter=spec["axis_formatter"],
            value_formatter=spec.get("chart_formatter") or spec["formatter"],
            pad_ratio=spec.get("pad_ratio", 0.12),
            clamp_min=spec.get("clamp_min"),
            clamp_max=spec.get("clamp_max"),
        )
        delta = _delta_payload(
            current_snapshot[spec["key"]],
            previous_snapshot[spec["key"]] if previous_snapshot else None,
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
        _apply_date_filter(
            _apply_division_filter(AgingCompositionRow.objects.filter(borrower=borrower)),
            "as_of_date",
        ).order_by("-as_of_date", "-created_at", "-id")
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
    aging_axis_left = Decimal("40")
    aging_axis_right = Decimal("500")
    aging_axis_top = Decimal("20")
    aging_axis_bottom = Decimal("140")
    aging_plot_height = aging_axis_bottom - aging_axis_top
    bucket_count = len(AGING_BUCKET_DEFS)
    bar_width = Decimal("32")
    plot_width = aging_axis_right - aging_axis_left
    if bucket_count > 1:
        gap = (plot_width - (bar_width * bucket_count)) / Decimal(bucket_count - 1)
        if gap <= 0:
            gap = Decimal("8")
            bar_width = max(Decimal("10"), (plot_width - gap * (bucket_count - 1)) / Decimal(bucket_count))
    else:
        gap = Decimal("0")
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
        plot_height = float(aging_plot_height)
        height_value = max(8.0, min(plot_height, ratio_float * plot_height))
        y_position = float(aging_axis_bottom) - height_value
        label_primary = bucket["label"]
        label_secondary = ""
        if bucket["key"] != "current":
            label_primary = "91+" if bucket["key"] == "90+" else bucket["label"]
            label_secondary = "Past Due"
        x_position = aging_axis_left + (bar_width + gap) * idx
        text_x = x_position + (bar_width / 2)
        label_y = float(aging_axis_bottom + Decimal("12"))
        label_secondary_y = float(aging_axis_bottom + Decimal("18"))
        percent_y = max(float(aging_axis_top) + 4, y_position - 6)
        aging_buckets.append(
            {
                "key": bucket["key"],
                "x": float(x_position),
                "y": y_position,
                "height": height_value,
                "width": float(bar_width),
                "color": bucket["color"],
                "percent_display": _format_pct(percent_ratio),
                "amount_display": _format_currency(amount),
                "label": bucket["label"],
                "label_primary": label_primary,
                "label_secondary": label_secondary,
                "percent_y": percent_y,
                "label_y": label_y,
                "label_secondary_y": label_secondary_y,
                "text_x": float(text_x),
            }
        )

    trend_bars = []
    trend_labels = []
    baseline_y = Decimal("140")
    plot_height = Decimal("120")
    bar_width = Decimal("8")
    spacing = Decimal("36")
    stack_gap = Decimal("4")
    max_amount = max(
        (
            _to_decimal(item.get("total_current_amt")) + _to_decimal(item.get("total_past_due_amt"))
            for item in history
        ),
        default=Decimal("0"),
    )
    scale = (plot_height / max_amount) if max_amount > 0 else Decimal("0")

    def _height_from_amount(amount):
        amt = _to_decimal(amount)
        if amt <= 0 or scale == 0:
            return Decimal("0")
        height = amt * scale
        return max(Decimal("6"), height)

    for idx, entry in enumerate(history):
        past_amt = _to_decimal(entry.get("total_past_due_amt"))
        current_amt = _to_decimal(entry.get("total_current_amt"))
        past_height = _height_from_amount(past_amt)
        current_height = _height_from_amount(current_amt)
        past_y = baseline_y - past_height if past_height else baseline_y
        gap = stack_gap if past_height and current_height else Decimal("0")
        current_y = past_y - gap - current_height if current_height else past_y
        bar_x = Decimal("58") + spacing * idx
        label_x = bar_x + (bar_width / 2)
        trend_bars.append(
            {
                "x": float(bar_x),
                "width": float(bar_width),
                "past_due_y": float(past_y),
                "past_due_height": float(past_height),
                "current_y": float(current_y),
                "current_height": float(current_height),
                "past_due_value": _format_currency(past_amt),
                "current_value": _format_currency(current_amt),
                "label": entry["label"],
            }
        )
        label_text = entry["label"]
        month_label = label_text
        year_label = ""
        if label_text and " " in label_text:
            month_label, year_label = label_text.split(" ", 1)
        trend_labels.append(
            {
                "x": float(label_x),
                "text": label_text,
                "month": month_label,
                "year": year_label,
            }
        )

    trend_ticks = []
    tick_steps = 4
    for i in range(tick_steps + 1):
        value = max_amount * Decimal(i) / Decimal(tick_steps)
        y = baseline_y - (value * scale if scale else Decimal("0"))
        trend_ticks.append(
            {
                "y": float(y),
                "label": _format_axis_currency(value),
            }
        )

    # Tables for customer aging composition views
    bucket_columns = ["Current", "0-30", "31-60", "61-90", "91+"]
    bucket_total_rows = []
    bucket_past_due_rows = []
    total_balance_sum = Decimal("0")
    total_past_due_sum = Decimal("0")
    latest_pct = current_snapshot.get("past_due_pct") if current_snapshot else None
    past_due_ratio = (
        (latest_pct / Decimal("100")) if latest_pct is not None else Decimal("0")
    )

    concentration_qs = _apply_division_filter(
        ConcentrationADODSORow.objects.filter(borrower=borrower)
    )
    concentration_rows = list(
        _apply_date_filter(concentration_qs, "as_of_date")
        .order_by("-as_of_date", "-created_at", "-id")
    )

    def _latest_snapshot_rows(rows):
        if not rows:
            return []
        latest_date = next((row.as_of_date for row in rows if row.as_of_date), None)
        if latest_date:
            return [row for row in rows if row.as_of_date == latest_date]
        return rows

    def _rows_with_values(rows, fields):
        return [
            row for row in rows
            if any(getattr(row, field, None) is not None for field in fields)
        ]

    def _latest_rows_with_values(rows, fields):
        if not rows:
            return []
        grouped = OrderedDict()
        for row in rows:
            key = row.as_of_date or (row.created_at and row.created_at.date())
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)
        for group_rows in grouped.values():
            if _rows_with_values(group_rows, fields):
                return group_rows
        return next(iter(grouped.values()))

    latest_concentration_rows = _latest_snapshot_rows(concentration_rows)

    concentration_source = [
        row for row in latest_concentration_rows if row.current_concentration_pct is not None
    ]
    if not concentration_source:
        concentration_source = latest_concentration_rows
    top_customers = sorted(
        concentration_source,
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
                    "total_value": total_value,
                }
            )
            bucket_past_due_rows.append(
                {
                    "customer": customer_name,
                    "values": past_values,
                    "total": _format_currency(past_total_value),
                    "total_value": past_total_value,
                }
            )
            total_balance_sum += total_value
            total_past_due_sum += past_total_value

    if total_balance_sum > 0:
        for row in bucket_total_rows:
            ratio = _to_decimal(row.get("total_value")) / total_balance_sum
            row["percent_total"] = _format_pct(ratio)
            row.pop("total_value", None)
    else:
        for row in bucket_total_rows:
            row["percent_total"] = "—"
            row.pop("total_value", None)

    if total_past_due_sum > 0:
        for row in bucket_past_due_rows:
            ratio = _to_decimal(row.get("total_value")) / total_past_due_sum
            row["percent_total"] = _format_pct(ratio)
            row.pop("total_value", None)
    else:
        for row in bucket_past_due_rows:
            row["percent_total"] = "—"
            row.pop("total_value", None)

    ineligible_overview = (
        _apply_date_filter(
            _apply_division_filter(IneligibleOverviewRow.objects.filter(borrower=borrower)),
            "date",
        )
        .order_by("-date", "-id")
        .first()
    )
    ineligible_trend_rows = list(
        _apply_date_filter(
            _apply_division_filter(IneligibleTrendRow.objects.filter(borrower=borrower)),
            "date",
        ).order_by("date", "id")
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
        if row.ineligible_pct_of_ar is None:
            continue
        value = float(_to_decimal(row.ineligible_pct_of_ar) * Decimal("100"))
        trend_points.append(value)
        label_date = row.date
        label = label_date.strftime("%b %y") if label_date else f"Point {row.id}"
        trend_texts.append(label)
    max_trend = 12
    if len(trend_points) > max_trend:
        trend_points = trend_points[-max_trend:]
        trend_texts = trend_texts[-max_trend:]
    axis_min = 0.0
    axis_max = 100.0
    if trend_points:
        min_val = min(trend_points)
        max_val = max(trend_points)
        if min_val == max_val:
            pad = 1.0
            axis_min = max(min_val - pad, 0.0)
            axis_max = max_val + pad
        else:
            pad_ratio = 0.10
            axis_min = min_val - (abs(min_val) * pad_ratio)
            axis_max = max_val + (abs(max_val) * pad_ratio)
            axis_min = max(axis_min, 0.0)
            if axis_max <= axis_min:
                axis_max = axis_min + 1.0
    trend_chart = _build_trend_points(
        trend_points,
        trend_texts,
        height=260,
        top=40,
        bottom=40,
        left=60,
        min_value=axis_min,
        max_value=axis_max,
        tick_count=5,
        value_formatter=_format_axis_pct,
    )
    trend_chart["series_values"] = [round(value, 4) for value in trend_points]
    trend_chart["series_labels"] = list(trend_texts)
    trend_chart["axis_min"] = round(axis_min, 4)
    trend_chart["axis_max"] = round(axis_max, 4)
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

    TOP_CUSTOMER_COUNT = 20
    concentration_entries = []
    for row in sorted(
        concentration_source,
        key=lambda r: _to_decimal(r.current_concentration_pct),
        reverse=True,
    )[:TOP_CUSTOMER_COUNT]:
        variance_pp = row.variance_concentration_pp
        if variance_pp is None:
            current_pp = _pct_to_points(row.current_concentration_pct)
            avg_pp = _pct_to_points(row.avg_ttm_concentration_pct)
            if current_pp is not None and avg_pp is not None:
                variance_pp = current_pp - avg_pp
        concentration_entries.append(
            {
                "customer": _safe_str(row.customer),
                "current": _format_pct(row.current_concentration_pct),
                "average": _format_pct(row.avg_ttm_concentration_pct),
                "variance": _format_variance(variance_pp),
            }
        )

    ado_fields = ["current_ado_days", "avg_ttm_ado_days", "variance_ado_days"]
    ado_source = _latest_rows_with_values(concentration_rows, ado_fields)
    if not _rows_with_values(ado_source, ado_fields):
        concentration_rows_all = list(
            concentration_qs.order_by("-as_of_date", "-created_at", "-id")
        )
        ado_source = _latest_rows_with_values(concentration_rows_all, ado_fields)
    ado_entries = []
    for row in sorted(
        ado_source,
        key=lambda r: _to_decimal(r.current_ado_days),
        reverse=True,
    )[:TOP_CUSTOMER_COUNT]:
        current_ado = _to_decimal(row.current_ado_days) if row.current_ado_days is not None else None
        avg_ado = _to_decimal(row.avg_ttm_ado_days) if row.avg_ttm_ado_days is not None else None
        variance_ado = _to_decimal(row.variance_ado_days) if row.variance_ado_days is not None else None
        if variance_ado is None and current_ado is not None and avg_ado is not None:
            variance_ado = current_ado - avg_ado
        if avg_ado is None and current_ado is not None and variance_ado is not None:
            avg_ado = current_ado - variance_ado
        if current_ado is None and avg_ado is not None and variance_ado is not None:
            current_ado = avg_ado + variance_ado
        ado_entries.append(
            {
                "customer": _safe_str(row.customer),
                "current": _format_days(current_ado),
                "average": _format_days(avg_ado),
                "variance": _format_variance(variance_ado),
            }
        )

    dso_fields = ["current_dso_days", "avg_ttm_dso_days", "variance_dso_days"]
    dso_source = _latest_rows_with_values(concentration_rows, dso_fields)
    if not _rows_with_values(dso_source, dso_fields):
        concentration_rows_all = list(
            concentration_qs.order_by("-as_of_date", "-created_at", "-id")
        )
        dso_source = _latest_rows_with_values(concentration_rows_all, dso_fields)
    dso_entries = []
    for row in sorted(
        dso_source,
        key=lambda r: _to_decimal(r.current_dso_days),
        reverse=True,
    )[:TOP_CUSTOMER_COUNT]:
        current_dso = _to_decimal(row.current_dso_days) if row.current_dso_days is not None else None
        avg_dso = _to_decimal(row.avg_ttm_dso_days) if row.avg_ttm_dso_days is not None else None
        variance_dso = _to_decimal(row.variance_dso_days) if row.variance_dso_days is not None else None
        if variance_dso is None and current_dso is not None and avg_dso is not None:
            variance_dso = current_dso - avg_dso
        if avg_dso is None and current_dso is not None and variance_dso is not None:
            avg_dso = current_dso - variance_dso
        if current_dso is None and avg_dso is not None and variance_dso is not None:
            current_dso = avg_dso + variance_dso
        dso_entries.append(
            {
                "customer": _safe_str(row.customer),
                "current": _format_days(current_dso),
                "average": _format_days(avg_dso),
                "variance": _format_variance(variance_dso),
            }
        )

    return {
        "ar_borrowing_base_kpis": kpis,
        "ar_aging_chart_buckets": aging_buckets,
        "ar_current_vs_past_due_trend": {
            "bars": trend_bars,
            "labels": trend_labels,
            "ticks": trend_ticks,
        },
        "ar_ineligible_overview_rows": ineligible_rows,
        "ar_ineligible_overview_total": ineligible_total_row,
        "ar_ineligible_trend": {
            "points": trend_chart["points"],
            "dots": trend_chart["dots"],
            "labels": trend_chart["labels"],
            "ticks": trend_chart.get("ticks", []),
        },
        "ar_concentration_rows": concentration_entries,
        "ar_ado_rows": ado_entries,
        "ar_dso_rows": dso_entries,
        "ar_customer_aging_total_rows": bucket_total_rows,
        "ar_customer_aging_past_due_rows": bucket_past_due_rows,
        "ar_range_options": base_context["ar_range_options"],
        "ar_selected_range": base_context["ar_selected_range"],
        "ar_division_options": base_context["ar_division_options"],
        "ar_selected_division": base_context["ar_selected_division"],
        "accounts_receivable_snapshot_summary": base_context["accounts_receivable_snapshot_summary"],
    }


RANGE_OPTIONS = [
    {"value": "last_12_months", "label": "12 Months"},
    {"value": "last_6_months", "label": "6 Months"},
    {"value": "last_3_months", "label": "3 Months"},
    {"value": "last_1_month", "label": "1 Month"},
]

RANGE_ALIASES = {
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

def _normalize_range(range_key):
    normalized_range = (range_key or "last_12_months").strip().lower()
    return RANGE_ALIASES.get(normalized_range, "last_12_months")

def _range_dates(range_key):
    today = date.today()
    if range_key == "last_12_months":
        return today - timedelta(days=364), today
    if range_key == "last_6_months":
        return today - timedelta(days=182), today
    if range_key == "last_3_months":
        return today - timedelta(days=89), today
    if range_key == "last_1_month":
        return today - timedelta(days=29), today
    return today - timedelta(days=364), today

def _normalize_division(division):
    normalized_division = (division or "all").strip()
    if normalized_division.lower() in {"all", "all divisions", "all_divisions"}:
        return "all"
    return normalized_division


def _finished_goals_context(
    borrower,
    range_key="today",
    division="all",
    inline_excess_pad_ratio=None,
    inventory_trend_pad_ratio=None,
):
    normalized_range = _normalize_range(range_key)
    normalized_division = _normalize_division(division)
    base_context = {
        "finished_goals_metrics": [],
        "finished_goals_sales_insights": [],
        "finished_goals_highlights": [],
        "finished_goals_chart_config": {},
        "finished_goals_chart_config_json": "{}",
        "finished_goals_inline_category_rows": [],
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
        "finished_goals_range_options": RANGE_OPTIONS,
        "finished_goals_selected_range": normalized_range,
        "finished_goals_division_options": [{"value": "all", "label": "All Divisions"}],
        "finished_goals_selected_division": normalized_division,
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    start_date, end_date = _range_dates(normalized_range)

    def _apply_date_filter(qs, field_name):
        if start_date and end_date:
            return qs.filter(**{f"{field_name}__range": (start_date, end_date)})
        return qs

    def _apply_date_filter_or_latest(qs, field_name):
        filtered = _apply_date_filter(qs, field_name)
        return filtered if filtered.exists() else qs

    def _month_bounds(value):
        if value is None:
            return None, None
        if isinstance(value, datetime):
            value = value.date()
        month_start = value.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        return month_start, month_end

    def _filter_to_latest_month(qs, field_name, fallback_field=None):
        latest_value = (
            qs.exclude(**{f"{field_name}__isnull": True})
            .order_by(f"-{field_name}")
            .values_list(field_name, flat=True)
            .first()
        )
        filter_field = field_name
        if latest_value is None and fallback_field:
            latest_value = (
                qs.exclude(**{f"{fallback_field}__isnull": True})
                .order_by(f"-{fallback_field}")
                .values_list(fallback_field, flat=True)
                .first()
            )
            filter_field = fallback_field if latest_value is not None else field_name
        start, end = _month_bounds(latest_value)
        if not start or not end:
            return qs, None
        if fallback_field and filter_field == fallback_field:
            return qs.filter(**{f"{filter_field}__date__range": (start, end)}), (start, end)
        return qs.filter(**{f"{filter_field}__range": (start, end)}), (start, end)

    def _apply_division_filter(qs):
        if normalized_division != "all":
            return qs.filter(division__iexact=normalized_division)
        return qs

    trend_scale = Decimal("1000000")

    def _build_year_series(month_map, year, *, scale=None):
        if not month_map:
            return [], []
        values = []
        for month in range(1, 13):
            val = month_map.get((year, month))
            if val is None:
                values.append(None)
                continue
            if scale is not None:
                if isinstance(val, Decimal):
                    if val < 0:
                        val = Decimal("0")
                    values.append(float(val / scale))
                else:
                    if val < 0:
                        val = 0.0
                    values.append(float(val) / float(scale))
            else:
                if val < 0:
                    val = 0.0
                values.append(float(val))
        first_idx = next((i for i, v in enumerate(values) if v is not None), None)
        if first_idx is None:
            return [], []
        first_val = values[first_idx]
        for idx in range(first_idx):
            values[idx] = first_val
        for idx in range(first_idx + 1, len(values)):
            if values[idx] is None:
                values[idx] = values[idx - 1]
        labels = [date(year, month, 1).strftime("%b\n%Y") for month in range(1, 13)]
        return labels, values

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
    metrics_qs = _apply_date_filter_or_latest(metrics_qs, "as_of_date")
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
        ("Available Inventory", _format_currency(inventory_available_total), available_delta),
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
    ineligible_division_qs = _apply_division_filter(ineligible_qs)
    ineligible_filtered_qs = _apply_date_filter(ineligible_division_qs, "date")
    ineligible_row = ineligible_filtered_qs.order_by("-date", "-created_at", "-id").first()
    if not ineligible_row:
        ineligible_row = ineligible_division_qs.order_by("-date", "-created_at", "-id").first()
    if not ineligible_row and normalized_division != "all":
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
    elif inventory_ineligible:
        total_ineligible = _to_decimal(inventory_ineligible)
        if total_ineligible < 0:
            total_ineligible = -total_ineligible
        fallback_fields = [
            ("Slow-Moving/Obsolete", Decimal("0.32")),
            ("Aged", Decimal("0.2")),
            ("Off Site", Decimal("0.12")),
            ("Consigned", Decimal("0.1")),
            ("In-Transit", Decimal("0.1")),
            ("Damaged/Non-Saleable", Decimal("0.16")),
        ]
        for label, weight in fallback_fields:
            amount = total_ineligible * weight
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

    sales_trend_base = SalesGMTrendRow.objects.filter(borrower=borrower)
    sales_trend_base = _apply_division_filter(sales_trend_base)
    sales_trend_qs = _apply_date_filter_or_latest(sales_trend_base, "as_of_date")
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
        trend_3m_value = latest_sales.trend_3_m_pct
        trend_3m_delta = (
            _pct_point_change(
                latest_sales.trend_3_m_pct, previous_sales.trend_3_m_pct
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
            {
                "label": "3 Month Sales Trend",
                "value": _format_pct(trend_3m_value),
                **_delta_payload(trend_3m_delta),
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
            {
                "label": "3 Month Sales Trend",
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
    inline_rows = _apply_date_filter_or_latest(inline_rows, "as_of_date")
    inline_rows, _ = _filter_to_latest_month(
        inline_rows,
        "as_of_date",
        fallback_field="created_at",
    )
    inline_rows = inline_rows.order_by("-fg_available", "id")
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

    inline_category_rows = []
    if inline_rows:
        category_totals = OrderedDict()
        total_available = Decimal("0")
        for row in inline_rows:
            category = (row.category or "—").strip()
            if category not in category_totals:
                category_totals[category] = {
                    "fg_total": Decimal("0"),
                    "fg_ineligible": Decimal("0"),
                    "fg_available": Decimal("0"),
                    "sales": Decimal("0"),
                    "cogs": Decimal("0"),
                }
            category_totals[category]["fg_total"] += _to_decimal(row.fg_total)
            category_totals[category]["fg_ineligible"] += _to_decimal(row.fg_ineligible)
            category_totals[category]["fg_available"] += _to_decimal(row.fg_available)
            category_totals[category]["sales"] += _to_decimal(row.sales)
            category_totals[category]["cogs"] += _to_decimal(row.cogs)
            total_available += _to_decimal(row.fg_available)

        sorted_categories = sorted(
            category_totals.items(),
            key=lambda item: item[1]["fg_available"],
            reverse=True,
        )
        for category, totals in sorted_categories:
            sales_total = totals["sales"]
            cogs_total = totals["cogs"]
            gm_value = sales_total - cogs_total
            gm_pct = (gm_value / sales_total) if sales_total else None
            weeks_supply = None
            if sales_total:
                weeks_supply = totals["fg_available"] / sales_total * Decimal("52")
            pct_available = (
                totals["fg_available"] / total_available if total_available else None
            )
            inline_category_rows.append(
                {
                    "category": category,
                    "fg_total": _format_currency(totals["fg_total"]),
                    "fg_ineligible": _format_currency(totals["fg_ineligible"]),
                    "fg_available": _format_currency(totals["fg_available"]),
                    "pct_of_available": _format_pct(pct_available),
                    "sales": _format_currency(sales_total),
                    "cogs": _format_currency(totals["cogs"]),
                    "gm": _format_currency(gm_value),
                    "gm_pct": _format_pct(gm_pct),
                    "weeks_supply": _format_wos(weeks_supply),
                }
            )

    def _build_trend_series(month_map):
        if not month_map:
            return [], [], 0
        month_count = len(month_map)
        if month_count < 2:
            return [], [], month_count
        latest_year = max(year for year, _ in month_map.keys())
        labels, values = _build_year_series(month_map, latest_year)
        return labels, values, month_count

    inline_excess_trend_labels = []
    inline_excess_trend_values = []
    inline_excess_trend_source = "none"
    trend_candidates = []

    inline_excess_trend_rows = FGInlineExcessByCategoryRow.objects.filter(
        borrower=borrower
    ).exclude(as_of_date__isnull=True)
    inline_excess_trend_rows = _apply_division_filter(inline_excess_trend_rows)
    inline_excess_trend_rows = _apply_date_filter_or_latest(inline_excess_trend_rows, "as_of_date")
    inline_excess_trend_rows = list(inline_excess_trend_rows.order_by("as_of_date", "id"))
    inline_excess_trend_row_count = len(inline_excess_trend_rows)
    inline_excess_month_map = OrderedDict()
    for row in inline_excess_trend_rows:
        dt = row.as_of_date
        if not dt:
            continue
        key = (dt.year, dt.month)
        if key not in inline_excess_month_map:
            inline_excess_month_map[key] = {"weighted": Decimal("0"), "weight": Decimal("0")}
        pct_value = None
        if row.inline_pct is not None:
            pct_value = _to_decimal(row.inline_pct)
            if abs(pct_value) <= 1:
                pct_value *= Decimal("100")
        elif row.fg_available is not None:
            available = _to_decimal(row.fg_available)
            if available:
                pct_value = (_to_decimal(row.inline_dollars) / available) * Decimal("100")
        if pct_value is None:
            continue
        weight = _to_decimal(row.fg_available) if row.fg_available is not None else Decimal("1")
        if weight <= 0:
            weight = Decimal("1")
        inline_excess_month_map[key]["weighted"] += pct_value * weight
        inline_excess_month_map[key]["weight"] += weight

    inline_excess_pct_map = OrderedDict()
    for key, entry in inline_excess_month_map.items():
        if entry["weight"] > 0:
            inline_excess_pct_map[key] = float(entry["weighted"] / entry["weight"])

    inline_excess_trend_candidate_labels, inline_excess_trend_candidate_values, inline_excess_month_count = _build_trend_series(
        inline_excess_pct_map
    )
    trend_candidates.append(
        {
            "source": "fg_inline_excess_by_category",
            "labels": inline_excess_trend_candidate_labels,
            "values": inline_excess_trend_candidate_values,
            "month_count": inline_excess_month_count,
        }
    )

    inline_trend_rows = FGInlineCategoryAnalysisRow.objects.filter(borrower=borrower).exclude(
        as_of_date__isnull=True
    )
    inline_trend_rows = _apply_division_filter(inline_trend_rows)
    inline_trend_rows = _apply_date_filter_or_latest(inline_trend_rows, "as_of_date")
    inline_trend_rows = list(inline_trend_rows.order_by("as_of_date", "id"))
    inline_trend_row_count = len(inline_trend_rows)
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

    inline_trend_month_map = OrderedDict()
    for dt, totals in inline_trend_map.items():
        key = (dt.year, dt.month)
        if key not in inline_trend_month_map:
            inline_trend_month_map[key] = {"total": Decimal("0"), "inline": Decimal("0")}
        inline_trend_month_map[key]["total"] += totals["total"]
        inline_trend_month_map[key]["inline"] += totals["inline"]

    inline_pct_map = OrderedDict()
    for key, totals in inline_trend_month_map.items():
        pct = (totals["inline"] / totals["total"] * Decimal("100")) if totals["total"] else Decimal("0")
        inline_pct_map[key] = float(pct)

    inline_trend_labels, inline_trend_values, inline_trend_month_count = _build_trend_series(
        inline_pct_map
    )
    trend_candidates.append(
        {
            "source": "inline_category_analysis",
            "labels": inline_trend_labels,
            "values": inline_trend_values,
            "month_count": inline_trend_month_count,
        }
    )

    composition_qs = FGCompositionRow.objects.filter(borrower=borrower)
    composition_qs = _apply_division_filter(composition_qs)
    composition_qs = _apply_date_filter_or_latest(composition_qs, "as_of_date")
    composition_rows = list(
        composition_qs.exclude(as_of_date__isnull=True).order_by("as_of_date", "id")
    )
    composition_row_count = len(composition_rows)
    composition_inline_pct_series = OrderedDict()
    composition_pct_map = OrderedDict()
    composition_inline_month_count = 0
    composition_bucket_month_count = 0
    if composition_rows:
        composition_map = OrderedDict()
        composition_inline_pct_map = OrderedDict()
        for row in composition_rows:
            dt = row.as_of_date
            if dt not in composition_map:
                composition_map[dt] = {
                    "available": Decimal("0"),
                    "new": Decimal("0"),
                    "0 - 13": Decimal("0"),
                    "13 - 26": Decimal("0"),
                    "26 - 39": Decimal("0"),
                    "39 - 52": Decimal("0"),
                    "52+": Decimal("0"),
                    "No Sales": Decimal("0"),
                }
            totals = composition_map[dt]
            totals["available"] += _to_decimal(row.fg_available)
            totals["0 - 13"] += _to_decimal(row.fg_0_13)
            totals["13 - 26"] += _to_decimal(row.fg_13_26)
            totals["26 - 39"] += _to_decimal(row.fg_26_39)
            totals["39 - 52"] += _to_decimal(row.fg_39_52)
            totals["52+"] += _to_decimal(row.fg_52_plus)
            totals["No Sales"] += _to_decimal(row.fg_no_sales)
            if row.inline_pct is not None:
                key = (dt.year, dt.month)
                weight = _to_decimal(row.fg_available)
                weight = weight if weight > 0 else Decimal("1")
                pct_value = _to_decimal(row.inline_pct)
                if abs(pct_value) <= 1:
                    pct_value *= Decimal("100")
                entry = composition_inline_pct_map.get(key)
                if not entry:
                    entry = {"weighted": Decimal("0"), "weight": Decimal("0")}
                    composition_inline_pct_map[key] = entry
                entry["weighted"] += pct_value * weight
                entry["weight"] += weight

        def _composition_total(totals):
            bucket_total = (
                totals["new"]
                + totals["0 - 13"]
                + totals["13 - 26"]
                + totals["26 - 39"]
                + totals["39 - 52"]
                + totals["52+"]
                + totals["No Sales"]
            )
            return totals["available"] if totals["available"] > 0 else bucket_total

        latest_totals = list(composition_map.values())[-1]
        total_amount = _composition_total(latest_totals)
        inline_excess_values = []
        inline_excess_value_labels = []
        for label in inline_excess_labels:
            amount = latest_totals.get(label, Decimal("0"))
            pct = (amount / total_amount * Decimal("100")) if total_amount else Decimal("0")
            inline_excess_values.append(float(pct))
            inline_excess_value_labels.append(f"{pct:.0f}%")

        composition_pct_map = OrderedDict()
        for dt, totals in composition_map.items():
            total_amount = _composition_total(totals)
            inline_amount = (
                totals["new"]
                + totals["0 - 13"]
                + totals["13 - 26"]
                + totals["26 - 39"]
                + totals["39 - 52"]
            )
            pct = (inline_amount / total_amount * Decimal("100")) if total_amount else Decimal("0")
            composition_pct_map[(dt.year, dt.month)] = float(pct)
        if composition_inline_pct_map:
            for key, entry in composition_inline_pct_map.items():
                if entry["weight"] > 0:
                    composition_inline_pct_series[key] = float(entry["weighted"] / entry["weight"])
            composition_inline_month_count = len(composition_inline_pct_series)
        if composition_pct_map:
            composition_bucket_month_count = len(composition_pct_map)

    composition_inline_labels, composition_inline_values, _ = _build_trend_series(
        composition_inline_pct_series
    )
    trend_candidates.append(
        {
            "source": "fg_composition_inline_pct",
            "labels": composition_inline_labels,
            "values": composition_inline_values,
            "month_count": composition_inline_month_count,
        }
    )

    composition_bucket_labels, composition_bucket_values, _ = _build_trend_series(
        composition_pct_map
    )
    trend_candidates.append(
        {
            "source": "fg_composition_buckets",
            "labels": composition_bucket_labels,
            "values": composition_bucket_values,
            "month_count": composition_bucket_month_count,
        }
    )

    trend_priority = {
        "fg_inline_excess_by_category": 4,
        "fg_composition_inline_pct": 3,
        "inline_category_analysis": 2,
        "fg_composition_buckets": 1,
    }
    scored_candidates = [
        candidate
        for candidate in trend_candidates
        if candidate["month_count"] >= 2 and candidate["labels"] and candidate["values"]
    ]
    if scored_candidates:
        max_months = max(candidate["month_count"] for candidate in scored_candidates)
        top_candidates = [
            candidate for candidate in scored_candidates if candidate["month_count"] == max_months
        ]
        selected = max(
            top_candidates,
            key=lambda candidate: trend_priority.get(candidate["source"], 0),
        )
        inline_excess_trend_labels = selected["labels"]
        inline_excess_trend_values = selected["values"]
        inline_excess_trend_source = selected["source"]

    inline_excess_trend_axis_min = None
    inline_excess_trend_axis_max = None
    inline_excess_trend_values_clean = [
        value for value in inline_excess_trend_values if value is not None
    ]
    if inline_excess_trend_values_clean:
        min_val = min(inline_excess_trend_values_clean)
        max_val = max(inline_excess_trend_values_clean)
        if min_val == max_val:
            pad = 1.0
            inline_excess_trend_axis_min = max(min_val - pad, 0.0)
            inline_excess_trend_axis_max = max_val + pad
        else:
            pad_ratio = (
                inline_excess_pad_ratio
                if inline_excess_pad_ratio in (0.05, 0.1, 0.10)
                else 0.10
            )
            inline_excess_trend_axis_min = min_val - (abs(min_val) * pad_ratio)
            inline_excess_trend_axis_max = max_val + (abs(max_val) * pad_ratio)
            inline_excess_trend_axis_min = max(inline_excess_trend_axis_min, 0.0)
            if inline_excess_trend_axis_max <= inline_excess_trend_axis_min:
                inline_excess_trend_axis_max = inline_excess_trend_axis_min + 1.0

    inline_excess_trend_debug = {
        "source": inline_excess_trend_source,
        "pad_ratio": (
            inline_excess_pad_ratio
            if inline_excess_pad_ratio in (0.05, 0.1, 0.10)
            else 0.10
        ),
        "inline_excess_rows": inline_excess_trend_row_count,
        "inline_excess_months": inline_excess_month_count,
        "inline_category_rows": inline_trend_row_count,
        "inline_category_months": inline_trend_month_count,
        "composition_rows": composition_row_count,
        "composition_inline_months": composition_inline_month_count,
        "composition_bucket_months": composition_bucket_month_count,
        "range": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
        },
        "division": normalized_division,
    }

    inventory_trend_labels = []
    inventory_trend_values = []
    metrics_trend_rows = (
        metrics_qs.exclude(as_of_date__isnull=True)
        .order_by("as_of_date", "id")
    )
    metrics_trend_map = OrderedDict()
    for row in metrics_trend_rows:
        dt = row.as_of_date
        if not dt:
            continue
        key = (dt.year, dt.month)
        if key not in metrics_trend_map:
            metrics_trend_map[key] = Decimal("0")
        metrics_trend_map[key] += _to_decimal(row.available_inventory)
    if metrics_trend_map:
        latest_year = max(year for year, _ in metrics_trend_map.keys())
        inventory_trend_labels, inventory_trend_values = _build_year_series(
            metrics_trend_map,
            latest_year,
            scale=trend_scale,
        )
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
            key = (dt.year, dt.month)
            if key not in inventory_trend_map:
                inventory_trend_map[key] = {"eligible": Decimal("0"), "total": Decimal("0")}
            inventory_trend_map[key]["eligible"] += _to_decimal(row.eligible_collateral)
            inventory_trend_map[key]["total"] += _to_decimal(row.beginning_collateral)

        if inventory_trend_map:
            latest_year = max(year for year, _ in inventory_trend_map.keys())
            series_map = {
                key: totals["eligible"]
                for key, totals in inventory_trend_map.items()
            }
            inventory_trend_labels, inventory_trend_values = _build_year_series(
                series_map,
                latest_year,
                scale=trend_scale,
            )
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

            base_value = float(inventory_available_total / trend_scale) if inventory_available_total else 0.0
            for idx in range(12):
                inventory_trend_labels.append(_month_label(idx, 12))
                variation = math.sin(idx / 2.0) * 0.06
                value = max(0.0, base_value * (1 + variation))
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

        base_value = float(inventory_available_total / trend_scale) if inventory_available_total else 0.0
        inventory_trend_labels = [_month_label(idx, 12) for idx in range(12)]
        inventory_trend_values = [
            max(0.0, base_value * (1 + math.sin(idx / 2.0) * 0.06))
            for idx in range(12)
        ]

    trend_values_clean = [value for value in inventory_trend_values if value is not None]
    trend_min = min(trend_values_clean) if trend_values_clean else 0
    trend_max = max(trend_values_clean) if trend_values_clean else 0
    pad_ratio = (
        inventory_trend_pad_ratio
        if inventory_trend_pad_ratio in (0.05, 0.1, 0.10)
        else 0.10
    )
    if trend_values_clean:
        if trend_min == trend_max:
            pad = abs(trend_min) * pad_ratio
            if pad == 0:
                pad = 1.0
            trend_y_min = trend_min - pad
            trend_y_max = trend_max + pad
        else:
            trend_y_min = trend_min - (abs(trend_min) * pad_ratio)
            trend_y_max = trend_max + (abs(trend_max) * pad_ratio)
            if trend_y_max <= trend_y_min:
                trend_y_max = trend_y_min + max(1.0, abs(trend_max) * pad_ratio)
    else:
        trend_y_min = 0
        trend_y_max = 1
    trend_tick_values = None

    trend_rows_all = list(
        sales_trend_qs.exclude(as_of_date__isnull=True)
        .order_by("as_of_date", "created_at", "id")
    )
    sales_rows = [row for row in trend_rows_all if row.net_sales is not None]
    gm_rows = [row for row in trend_rows_all if row.gross_margin_pct is not None]

    sales_labels = []
    sales_values = []
    if sales_rows:
        sales_month_map = OrderedDict()
        for row in sales_rows:
            dt = row.as_of_date
            if not dt:
                continue
            sales_month_map[(dt.year, dt.month)] = _to_millions(row.net_sales)
        if sales_month_map:
            latest_year = max(year for year, _ in sales_month_map.keys())
            sales_labels, sales_values = _build_year_series(sales_month_map, latest_year)
    if not sales_values:
        sales_rows = sales_rows[-12:]
        sales_labels = [row.as_of_date.strftime("%b\n%Y") for row in sales_rows]
        sales_values = [_to_millions(row.net_sales) for row in sales_rows]

    gross_labels = []
    gross_values = []
    if gm_rows:
        gm_month_map = OrderedDict()
        for row in gm_rows:
            dt = row.as_of_date
            if not dt:
                continue
            gm_month_map[(dt.year, dt.month)] = _to_pct_value(row.gross_margin_pct)
        if gm_month_map:
            latest_year = max(year for year, _ in gm_month_map.keys())
            gross_labels, gross_values = _build_year_series(gm_month_map, latest_year)
    if not gross_values:
        gm_rows = gm_rows[-12:]
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
    # Hide the secondary (percentage) axis on the Sales Trend chart
    sales_right = None

    chart_config = {
        "inventoryTrend": {
            "type": "line",
            "title": "Inventory Trend",
            "labels": inventory_trend_labels,
            "values": inventory_trend_values,
            "yPrefix": "$",
            "ySuffix": "M",
            "yLabel": "",
            "yMin": trend_y_min,
            "yMax": trend_y_max,
            "yTicks": 6,
            "yTickValues": trend_tick_values,
            "yDecimals": 1,
            "showAllPoints": True,
            "pointRadius": 3,
            "xStep": 1,
            "xLabelDedupe": False,
        },
        "agedStock": {
            "type": "bar",
            "title": "Sales Trend",
            "labels": sales_labels,
            "values": sales_values,
            "barClass": "bar-strong",
            "barWidth": 6,
            "barGap": 46,
            "yPrefix": "$",
            "ySuffix": "M",
            "yMin": 0 if sales_values else None,
            "yMax": sales_axis_max,
            "yTicks": sales_ticks,
            "yDecimals": 0,
            "yRight": sales_right,
            "xStep": 1,
            "xLabelDedupe": False,
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
            "xStep": 1,
            "xLabelDedupe": False,
        },
        "inlineExcess": {
            "type": "bar",
            "title": "In-line vs Excess",
            "labels": inline_excess_labels,
            "values": inline_excess_values,
            "valueLabels": inline_excess_value_labels,
            "showValueLabels": True,
            "highlightIndex": 3,
            "height": 360,
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
            "yMin": inline_excess_trend_axis_min,
            "yMax": inline_excess_trend_axis_max,
            "yTicks": 6,
            "yDecimals": 0,
            "yLabel": "% Of Inventory",
            "xStep": 1,
            "xLabelDedupe": False,
            "debug": inline_excess_trend_debug,
        },
    }

    inline_excess_qs = FGInlineExcessByCategoryRow.objects.filter(borrower=borrower)
    inline_excess_qs = _apply_division_filter(inline_excess_qs)
    inline_excess_qs = _apply_date_filter_or_latest(inline_excess_qs, "as_of_date")
    inline_excess_qs, _ = _filter_to_latest_month(
        inline_excess_qs,
        "as_of_date",
        fallback_field="created_at",
    )
    inline_excess_rows = list(inline_excess_qs.order_by("category", "id"))
    inline_excess_by_category = []
    inline_excess_totals = {}
    if inline_excess_rows:
        category_totals = OrderedDict()
        total_available = Decimal("0")
        total_inline = Decimal("0")
        total_excess = Decimal("0")
        for row in inline_excess_rows:
            category = (row.category or "Category").strip()
            if category not in category_totals:
                category_totals[category] = {
                    "available": Decimal("0"),
                    "inline": Decimal("0"),
                    "excess": Decimal("0"),
                }
            category_totals[category]["available"] += _to_decimal(row.fg_available)
            category_totals[category]["inline"] += _to_decimal(row.inline_dollars)
            category_totals[category]["excess"] += _to_decimal(row.excess_dollars)
            total_available += _to_decimal(row.fg_available)
            total_inline += _to_decimal(row.inline_dollars)
            total_excess += _to_decimal(row.excess_dollars)

        raw_entries = []
        for category, totals in category_totals.items():
            available = totals["available"]
            inline_value = totals["inline"]
            excess_value = totals["excess"]
            inline_pct_value = (inline_value / available) if available else None
            excess_pct_value = (excess_value / available) if available else None
            raw_entries.append(
                {
                    "category": category,
                    "inline_amount": inline_value,
                    "inline_pct": inline_pct_value,
                    "excess_amount": excess_value,
                    "excess_pct": excess_pct_value,
                }
            )

        raw_entries.sort(key=lambda entry: entry["inline_amount"], reverse=True)

        for entry in raw_entries:
            inline_amount = _format_currency(entry["inline_amount"])
            inline_pct = (
                _format_pct(entry["inline_pct"]) if entry["inline_pct"] is not None else "—"
            )
            excess_amount = _format_currency(entry["excess_amount"])
            excess_pct = (
                _format_pct(entry["excess_pct"]) if entry["excess_pct"] is not None else "—"
            )
            inline_excess_by_category.append(
                {
                    "category": entry["category"],
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

    TOP_SKU_LIMIT = 20
    top_sku_rows = []
    sku_query = HistoricalTop20SKUsRow.objects.filter(borrower=borrower)
    sku_query = _apply_division_filter(sku_query)
    sku_query = _apply_date_filter_or_latest(sku_query, "as_of_date")
    sku_rows = []
    sku_dated = sku_query.exclude(as_of_date__isnull=True)
    if sku_dated.exists():
        if start_date and end_date:
            sku_rows = list(
                sku_dated.filter(as_of_date__range=(start_date, end_date))
            )
        if not sku_rows:
            latest_date = sku_dated.order_by("-as_of_date").values_list("as_of_date", flat=True).first()
            if latest_date:
                fallback_start = latest_date - timedelta(days=364)
                sku_rows = list(
                    sku_dated.filter(as_of_date__range=(fallback_start, latest_date))
                )
    if not sku_rows:
        sku_rows = list(sku_query.order_by("-created_at", "-id"))

    if sku_rows:
        sku_totals = OrderedDict()
        total_cost = Decimal("0")
        for row in sku_rows:
            item_number = _format_item_number(row.item_number)
            description = row.description or "—"
            category = row.category or "—"
            key = (item_number, description, category)
            if key not in sku_totals:
                sku_totals[key] = {
                    "item_number": item_number,
                    "description": description,
                    "category": category,
                    "cost": Decimal("0"),
                    "cogs": Decimal("0"),
                    "gm": Decimal("0"),
                    "wos_weighted": Decimal("0"),
                    "wos_weight": Decimal("0"),
                }
            cost = _to_decimal(row.cost)
            cogs = _to_decimal(row.cogs)
            gm = _to_decimal(row.gm)
            sku_totals[key]["cost"] += cost
            sku_totals[key]["cogs"] += cogs
            sku_totals[key]["gm"] += gm
            total_cost += cost
            wos_val = _dec_or_none(row.wos)
            if wos_val is not None:
                weight = cost if cost > 0 else Decimal("1")
                sku_totals[key]["wos_weighted"] += wos_val * weight
                sku_totals[key]["wos_weight"] += weight

        sorted_skus = sorted(
            sku_totals.values(),
            key=lambda entry: entry["cost"],
            reverse=True,
        )
        unique_sorted_skus = []
        seen_keys = set()
        for entry in sorted_skus:
            key = (
                entry["item_number"],
                entry["description"],
                entry["category"],
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_sorted_skus.append(entry)
        top_sku_entries = unique_sorted_skus[:TOP_SKU_LIMIT]
        total_cost = sum((entry["cost"] for entry in top_sku_entries), Decimal("0"))
        total_cogs = sum((entry["cogs"] for entry in top_sku_entries), Decimal("0"))
        total_gm = sum((entry["gm"] for entry in top_sku_entries), Decimal("0"))

        for entry in top_sku_entries:
            pct_total = entry["cost"] / total_cost if total_cost else None
            gm_pct = entry["gm"] / entry["cogs"] if entry["cogs"] else None
            wos_value = (
                entry["wos_weighted"] / entry["wos_weight"]
                if entry["wos_weight"]
                else None
            )
            top_sku_rows.append(
                {
                    "item_number": entry["item_number"],
                    "category": entry["category"],
                    "description": entry["description"],
                    "cost": _format_currency(entry["cost"]),
                    "pct_of_total": _format_pct(pct_total),
                    "cogs": _format_currency(entry["cogs"]),
                    "gm": _format_currency(entry["gm"]),
                    "gm_pct": _format_pct(gm_pct),
                    "wos": _format_wos(wos_value),
                }
            )
        finished_goals_top_sku_total = {
            "cost": _format_currency(total_cost),
            "cogs": _format_currency(total_cogs),
            "gm": _format_currency(total_gm),
        }
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
        for desc in sample_desc[:TOP_SKU_LIMIT]:
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
        finished_goals_top_sku_total = None

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
        "finished_goals_inline_category_rows": inline_category_rows,
        "finished_goals_inline_excess_by_category": inline_excess_by_category,
        "finished_goals_inline_excess_totals": inline_excess_totals,
        "finished_goals_top_skus": top_sku_rows,
        "finished_goals_top_sku_total": finished_goals_top_sku_total,
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

def _raw_materials_context(borrower, range_key="today", division="all"):
    normalized_range = _normalize_range(range_key)
    normalized_division = _normalize_division(division)
    base_context = {
        "raw_materials_metrics": [],
        "raw_materials_ineligible_detail": [],
        "raw_materials_chart_config": {},
        "raw_materials_category_rows": [],
        "raw_materials_category_footer": {},
        "raw_materials_top_skus": [],
        "raw_materials_range_options": RANGE_OPTIONS,
        "raw_materials_selected_range": normalized_range,
        "raw_materials_division_options": [{"value": "all", "label": "All Divisions"}],
        "raw_materials_selected_division": normalized_division,
    }

    if normalized_division != "all":
        normalized_division = "all"
        base_context["raw_materials_selected_division"] = normalized_division

    start_date, end_date = _range_dates(normalized_range)
    state = _inventory_state(borrower, start_date, end_date)
    if not state:
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
            "value": _format_currency(inventory_available_total),
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

    ineligible_detail = []
    rm_ineligible_qs = RMIneligibleOverviewRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        rm_ineligible_qs = rm_ineligible_qs.filter(division__iexact=normalized_division)
    if start_date and end_date:
        rm_ineligible_qs = rm_ineligible_qs.filter(date__range=(start_date, end_date))
    rm_ineligible_row = rm_ineligible_qs.order_by("-date", "-created_at", "-id").first()
    if not rm_ineligible_row and normalized_division != "all":
        rm_ineligible_row = RMIneligibleOverviewRow.objects.filter(borrower=borrower).order_by(
            "-date", "-created_at", "-id"
        ).first()
    if rm_ineligible_row:
        reason_fields = [
            ("Slow Moving/Obsolete", getattr(rm_ineligible_row, "slow_moving_obsolete", None)),
            ("Aged", getattr(rm_ineligible_row, "aged", None)),
            (
                "Work In Progress",
                getattr(rm_ineligible_row, "work_in_progress", None)
                or getattr(rm_ineligible_row, "wip", None)
                or getattr(rm_ineligible_row, "off_site", None),
            ),
            ("Consigned", getattr(rm_ineligible_row, "consigned", None)),
            ("In Transit", getattr(rm_ineligible_row, "in_transit", None)),
            ("Damaged/Non Saleable", getattr(rm_ineligible_row, "damaged_non_saleable", None)),
        ]
        total_ineligible = _to_decimal(getattr(rm_ineligible_row, "total_ineligible", None))
        if total_ineligible <= 0:
            total_ineligible = sum(_to_decimal(value) for _, value in reason_fields if value is not None)
        for label, value in reason_fields:
            amount = _to_decimal(value)
            pct = (amount / total_ineligible) if total_ineligible else Decimal("0")
            ineligible_detail.append(
                {
                    "reason": label,
                    "amount": _format_currency(amount),
                    "pct": _format_pct(pct),
                }
            )
    else:
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

    category_rows = []
    top10_row = _empty_summary_entry("Top 10 Total")
    category_other_row = _empty_summary_entry("Other items")
    footer = _empty_summary_entry("Total")

    category_base_qs = RMCategoryHistoryRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        category_base_qs = category_base_qs.filter(division__iexact=normalized_division)
    category_qs = category_base_qs
    if start_date and end_date:
        range_qs = category_base_qs.filter(date__range=(start_date, end_date))
        if range_qs.exists():
            category_qs = range_qs

    category_totals = OrderedDict()
    for row in category_qs:
        label = (row.category or "—").strip()
        if label not in category_totals:
            category_totals[label] = {
                "total": Decimal("0"),
                "available": Decimal("0"),
                "ineligible": Decimal("0"),
            }
        total = _to_decimal(row.total_inventory)
        available = _to_decimal(row.available_inventory)
        ineligible = _to_decimal(row.ineligible_inventory)
        if ineligible <= 0 and total:
            ineligible = max(total - available, Decimal("0"))
        category_totals[label]["total"] += total
        category_totals[label]["available"] += available
        category_totals[label]["ineligible"] += ineligible

    if category_totals:
        for label, totals in category_totals.items():
            total = totals["total"]
            available = totals["available"]
            ineligible = totals["ineligible"]
            pct_ratio = (available / total) if total else Decimal("0")
            category_rows.append(
                {
                    "label": label,
                    "total": _format_currency(total),
                    "ineligible": _format_currency(ineligible),
                    "available": _format_currency(available),
                    "pct_available": _format_pct(pct_ratio),
                    "_total_value": total,
                    "_available_value": available,
                    "_ineligible_value": ineligible,
                }
            )

        category_rows.sort(
            key=lambda item: item.get("_total_value", Decimal("0")), reverse=True
        )

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
        other_available = sum(
            item.get("_available_value", Decimal("0")) for item in category_rows[10:]
        )
        category_other_row = {
            "label": "Other items",
            "total": _format_currency(other_total),
            "ineligible": _format_currency(max(other_total - other_available, Decimal("0"))),
            "available": _format_currency(other_available),
            "pct_available": _format_pct(
                (other_available / other_total) if other_total else Decimal("0")
            ),
        }

        total_beginning = sum(item.get("_total_value", Decimal("0")) for item in category_rows)
        total_available = sum(item.get("_available_value", Decimal("0")) for item in category_rows)
        total_ineligible_calc = sum(item.get("_ineligible_value", Decimal("0")) for item in category_rows)
        footer = {
            "total": _format_currency(total_beginning),
            "ineligible": _format_currency(total_ineligible_calc),
            "available": _format_currency(total_available),
            "pct_available": _format_pct(
                total_available / total_beginning if total_beginning else Decimal("0")
            ),
        }

        for item in category_rows:
            item.pop("_total_value", None)
            item.pop("_available_value", None)
            item.pop("_ineligible_value", None)
    else:
        category_metrics = {
            label: {"eligible": Decimal("0"), "beginning": Decimal("0")}
            for label, _ in RAW_CATEGORY_DEFINITIONS
        }
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
            metrics = category_metrics.setdefault(
                matched_label, {"eligible": Decimal("0"), "beginning": Decimal("0")}
            )
            metrics["eligible"] += available
            metrics["beginning"] += beginning

        for label, _ in RAW_CATEGORY_DEFINITIONS:
            metrics = category_metrics.get(label, {"eligible": Decimal("0"), "beginning": Decimal("0")})
            beginning = metrics["beginning"]
            available = metrics["eligible"]
            ineligible = max(beginning - available, Decimal("0"))
            total_ineligible_calc += ineligible
            pct_available = available / beginning if beginning else Decimal("0")
            category_rows.append(
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

        top10_beginning = sum(
            category_metrics[label]["beginning"] for label, _ in RAW_CATEGORY_DEFINITIONS
        )
        top10_available = sum(
            category_metrics[label]["eligible"] for label, _ in RAW_CATEGORY_DEFINITIONS
        )
        top10_row = {
            "label": "Top 10 Total",
            "total": _format_currency(top10_beginning),
            "ineligible": _format_currency(max(top10_beginning - top10_available, Decimal("0"))),
            "available": _format_currency(top10_available),
            "pct_available": _format_pct(
                (top10_available / top10_beginning) if top10_beginning else Decimal("0")
            ),
        }

    raw_skus = []
    top20_total = _empty_summary_entry("Top 20 Total")
    sku_other_row = _empty_summary_entry("Other items")
    sku_grand_total = _empty_summary_entry("Total")

    sku_base_qs = RMTop20HistoryRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        sku_base_qs = sku_base_qs.filter(division__iexact=normalized_division)
    sku_qs = sku_base_qs
    if start_date and end_date:
        range_qs = sku_base_qs.filter(as_of_date__range=(start_date, end_date))
        if range_qs.exists():
            sku_qs = range_qs
    sku_rows = []
    sku_dated = sku_qs.exclude(as_of_date__isnull=True)
    if sku_dated.exists():
        if start_date and end_date:
            sku_rows = list(sku_dated.filter(as_of_date__range=(start_date, end_date)))
        if not sku_rows:
            latest_date = sku_dated.order_by("-as_of_date").values_list("as_of_date", flat=True).first()
            if latest_date:
                fallback_start = latest_date - timedelta(days=364)
                sku_rows = list(
                    sku_dated.filter(as_of_date__range=(fallback_start, latest_date))
                )
    if not sku_rows:
        sku_rows = list(sku_qs)

    if sku_rows:
        sku_totals = OrderedDict()
        sku_meta = {}
        total_amount = Decimal("0")
        total_available = Decimal("0")
        top_label = "Top 20 Total"
        for row in sku_rows:
            item_number = _format_item_number_value(row.sku)
            category = row.category or "—"
            description = row.description or "—"
            key = item_number
            if key not in sku_totals:
                sku_totals[key] = {
                    "item_number": item_number,
                    "amount": Decimal("0"),
                    "available": Decimal("0"),
                    "units": Decimal("0"),
                }
                sku_meta[key] = {
                    "category": category,
                    "description": description,
                    "row_key": (
                        row.as_of_date or date.min,
                        row.created_at or datetime.min,
                        row.id or 0,
                    ),
                }
            else:
                row_key = (
                    row.as_of_date or date.min,
                    row.created_at or datetime.min,
                    row.id or 0,
                )
                existing_key = sku_meta.get(key)
                if existing_key and row_key > existing_key["row_key"]:
                    existing_key.update(
                        {
                            "category": category,
                            "description": description,
                            "row_key": row_key,
                        }
                    )
            amount = _to_decimal(row.amount)
            pct_value = _to_decimal(row.pct_available)
            pct_ratio = pct_value / Decimal("100") if pct_value > 1 else pct_value
            available_amount = amount * pct_ratio
            sku_totals[key]["amount"] += amount
            sku_totals[key]["available"] += available_amount
            sku_totals[key]["units"] += _to_decimal(row.units)
            total_amount += amount
            total_available += available_amount

        sorted_skus = sorted(
            sku_totals.values(),
            key=lambda entry: entry["amount"],
            reverse=True,
        )
        top20_skus = sorted_skus[:20]
        top_label = f"Top {len(top20_skus)} Total"
        top20_total_amount = Decimal("0")
        top20_available_amount = Decimal("0")
        for entry in top20_skus:
            meta = sku_meta.get(entry["item_number"], {})
            units_display = "—"
            if entry["units"] and entry["units"] > 0:
                if entry["units"] == entry["units"].to_integral_value():
                    units_display = f"{entry['units']:,.0f}"
                else:
                    units_display = f"{entry['units']:,.2f}"
            per_unit_value = (
                entry["amount"] / entry["units"] if entry["units"] else None
            )
            pct_available = (
                entry["available"] / entry["amount"] if entry["amount"] else None
            )
            raw_skus.append(
                {
                    "item_number": entry["item_number"],
                    "category": meta.get("category", "—"),
                    "description": meta.get("description", "—"),
                    "amount": _format_currency(entry["amount"]),
                    "units": units_display,
                    "per_unit": _format_currency(per_unit_value),
                    "pct_available": _format_pct(pct_available),
                    "status": "Current",
                }
            )
            top20_total_amount += entry["amount"]
            top20_available_amount += entry["available"]

        total_pct = (
            top20_available_amount / top20_total_amount
            if top20_total_amount
            else Decimal("0")
        )
        top20_total = {
            "label": top_label,
            "total": _format_currency(top20_total_amount),
            "ineligible": "—",
            "available": _format_currency(top20_available_amount),
            "pct_available": _format_pct(total_pct),
        }

        other_amount = total_amount - top20_total_amount
        other_available = total_available - top20_available_amount
        sku_other_row = {
            "label": "Other items",
            "total": _format_currency(other_amount if other_amount > 0 else Decimal("0")),
            "ineligible": "—",
            "available": _format_currency(other_available if other_available > 0 else Decimal("0")),
            "pct_available": _format_pct(
                (other_available / other_amount) if other_amount else Decimal("0")
            ),
        }
        sku_grand_total = {
            "label": "Total",
            "total": _format_currency(total_amount),
            "ineligible": "—",
            "available": _format_currency(total_available),
            "pct_available": _format_pct(
                (total_available / total_amount) if total_amount else Decimal("0")
            ),
        }
    else:
        sku_rows = sorted(
            inventory_rows,
            key=lambda row: _to_decimal(row.eligible_collateral),
            reverse=True,
        )
        top20_rows = sku_rows[:20]
        top20_amount = Decimal("0")
        top20_available = Decimal("0")
        total_amount = Decimal("0")
        total_available = Decimal("0")
        for row in sku_rows:
            total_amount += _to_decimal(row.beginning_collateral)
            total_available += _to_decimal(row.eligible_collateral)
        for row in top20_rows:
            eligible = _to_decimal(row.eligible_collateral)
            beginning = _to_decimal(row.beginning_collateral)
            pct_available = (eligible / beginning) if beginning else Decimal("0")
            unit_count = max(int(eligible), 0)
            value_per_unit = eligible / unit_count if unit_count else Decimal("0")
            raw_skus.append(
                {
                    "item_number": f"RM-{row.id}",
                    "category": row.main_type or "Inventory",
                    "description": row.sub_type or row.main_type or "Raw Material",
                    "amount": _format_currency(beginning),
                    "units": f"{unit_count:,}" if unit_count else "—",
                    "per_unit": f"${value_per_unit:.2f}" if unit_count else "—",
                    "pct_available": _format_pct(pct_available),
                    "status": "Current" if _to_decimal(row.net_collateral) >= 0 else "At Risk",
                }
            )
            top20_amount += beginning
            top20_available += eligible
        top20_total = {
            "label": "Top 20 Total",
            "total": _format_currency(top20_amount),
            "ineligible": _format_currency(max(top20_amount - top20_available, Decimal("0"))),
            "available": _format_currency(top20_available),
            "pct_available": _format_pct(
                (top20_available / top20_amount) if top20_amount else Decimal("0")
            ),
        }

        other_amount = total_amount - top20_amount
        other_available = total_available - top20_available
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

    raw_skus = raw_skus[:20]

    def _line_values(base, length=13):
        values = []
        for idx in range(length):
            variation = math.sin(idx / 2.0) * 0.04
            val = max(0.0, base * (1 + variation))
            values.append(val)
        return values

    base_value = float(inventory_available_total) if inventory_available_total else 0.0
    chart_values = _line_values(base_value)
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
            "yPrefix": "$ ",
            "ySuffix": "M",
            "yScale": 1_000_000,
            "yTicks": 6,
            "yDecimals": 1,
        }
    }

    return {
        "raw_materials_metrics": formatted_metrics,
        "raw_materials_ineligible_detail": ineligible_detail,
        "raw_materials_chart_config": chart_config,
        "raw_materials_chart_config_json": json.dumps(chart_config),
        "raw_materials_category_rows": category_rows,
        "raw_materials_category_top10": top10_row,
        "raw_materials_category_other": category_other_row,
        "raw_materials_category_footer": footer,
        "raw_materials_top_skus": raw_skus,
        "raw_materials_top20_total": top20_total,
        "raw_materials_top_skus_other": sku_other_row,
        "raw_materials_top_skus_total": sku_grand_total,
        "raw_materials_range_options": base_context["raw_materials_range_options"],
        "raw_materials_selected_range": base_context["raw_materials_selected_range"],
        "raw_materials_division_options": base_context["raw_materials_division_options"],
        "raw_materials_selected_division": base_context["raw_materials_selected_division"],
    }


def _work_in_progress_context(borrower, range_key="today", division="all"):
    normalized_range = _normalize_range(range_key)
    normalized_division = _normalize_division(division)
    base_context = {
        "work_in_progress_metrics": [],
        "work_in_progress_ineligible_detail": [],
        "work_in_progress_chart_config_json": "{}",
        "work_in_progress_category_rows": [],
        "work_in_progress_category_top10": _empty_summary_entry("Top 10 Total"),
        "work_in_progress_category_other": _empty_summary_entry("Other items"),
        "work_in_progress_category_footer": _empty_summary_entry("Total"),
        "work_in_progress_top_skus": [],
        "work_in_progress_top20_total": _empty_summary_entry("Top 20 Total"),
        "work_in_progress_top_skus_other": _empty_summary_entry("Other items"),
        "work_in_progress_top_skus_total": _empty_summary_entry("Total"),
        "work_in_progress_range_options": RANGE_OPTIONS,
        "work_in_progress_selected_range": normalized_range,
        "work_in_progress_division_options": [{"value": "all", "label": "All Divisions"}],
        "work_in_progress_selected_division": normalized_division,
    }

    if normalized_division != "all":
        normalized_division = "all"
        base_context["work_in_progress_selected_division"] = normalized_division

    start_date, end_date = _range_dates(normalized_range)
    state = _inventory_state(borrower, start_date, end_date)
    if not state:
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
            "value": _format_currency(total_available),
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

    ineligible_detail = []
    wip_ineligible_qs = WIPIneligibleOverviewRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        wip_ineligible_qs = wip_ineligible_qs.filter(division__iexact=normalized_division)
    if start_date and end_date:
        wip_ineligible_qs = wip_ineligible_qs.filter(date__range=(start_date, end_date))
    wip_ineligible_row = wip_ineligible_qs.order_by("-date", "-created_at", "-id").first()
    if not wip_ineligible_row and normalized_division != "all":
        wip_ineligible_row = WIPIneligibleOverviewRow.objects.filter(borrower=borrower).order_by(
            "-date", "-created_at", "-id"
        ).first()
    if wip_ineligible_row:
        total_ineligible_row = _to_decimal(getattr(wip_ineligible_row, "total_ineligible", None))
        slow_moving = _to_decimal(getattr(wip_ineligible_row, "slow_moving_obsolete", None))
        aged = _to_decimal(getattr(wip_ineligible_row, "aged", None))
        off_site = _to_decimal(getattr(wip_ineligible_row, "off_site", None))
        consigned = _to_decimal(getattr(wip_ineligible_row, "consigned", None))
        in_transit = _to_decimal(getattr(wip_ineligible_row, "in_transit", None))
        damaged = _to_decimal(getattr(wip_ineligible_row, "damaged_non_saleable", None))
        if total_ineligible_row <= 0:
            total_ineligible_row = slow_moving + aged + off_site + consigned + in_transit + damaged
        work_in_progress = max(
            total_ineligible_row - (slow_moving + aged + off_site + consigned + in_transit + damaged),
            Decimal("0"),
        )
        reason_fields = [
            ("Slow Moving/Obsolete", slow_moving),
            ("Aged", aged),
            ("Work In Progress", work_in_progress),
            ("Consigned", consigned),
            ("In Transit", in_transit),
            ("Damaged/Non Saleable", damaged),
        ]
        for label, amount in reason_fields:
            pct = (amount / total_ineligible_row) if total_ineligible_row else Decimal("0")
            ineligible_detail.append(
                {
                    "reason": label,
                    "amount": _format_currency(amount),
                    "pct": _format_pct(pct),
                }
            )
    else:
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

    category_rows = []
    top10_row = _empty_summary_entry("Top 10 Total")
    category_base_qs = WIPCategoryHistoryRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        category_base_qs = category_base_qs.filter(division__iexact=normalized_division)
    category_qs = category_base_qs
    if start_date and end_date:
        range_qs = category_base_qs.filter(date__range=(start_date, end_date))
        if range_qs.exists():
            category_qs = range_qs

    category_latest_rows = OrderedDict()
    for row in category_qs:
        label = row.category or "—"
        row_key = (
            row.date or date.min,
            row.created_at or datetime.min,
            row.id or 0,
        )
        existing = category_latest_rows.get(label)
        if existing is None:
            category_latest_rows[label] = (row_key, row)
            continue
        if row_key > existing[0]:
            category_latest_rows[label] = (row_key, row)

    if category_latest_rows:
        for _, row in category_latest_rows.values():
            total = _to_decimal(row.total_inventory)
            available = _to_decimal(row.available_inventory)
            ineligible = _to_decimal(row.ineligible_inventory)
            if ineligible <= 0 and total:
                ineligible = max(total - available, Decimal("0"))
            pct_value = _to_decimal(row.pct_available)
            if pct_value <= 0 and total:
                pct_value = available / total
            pct_ratio = pct_value / Decimal("100") if pct_value > 1 else pct_value
            category_rows.append(
                {
                    "label": row.category or "—",
                    "total": _format_currency(total),
                    "ineligible": _format_currency(ineligible),
                    "available": _format_currency(available),
                    "pct_available": _format_pct(pct_ratio),
                    "_total_value": total,
                    "_available_value": available,
                }
            )
        category_rows.sort(
            key=lambda item: item.get("_total_value", Decimal("0")), reverse=True
        )
        top10_slice = category_rows[:10]
        top10_total = sum(item.get("_total_value", Decimal("0")) for item in top10_slice)
        top10_available = sum(
            item.get("_available_value", Decimal("0")) for item in top10_slice
        )
        top10_row = {
            "label": "Top 10 Total",
            "total": _format_currency(top10_total),
            "ineligible": _format_currency(max(top10_total - top10_available, Decimal("0"))),
            "available": _format_currency(top10_available),
            "pct_available": _format_pct(
                (top10_available / top10_total) if top10_total else Decimal("0")
            ),
        }
        for item in category_rows:
            item.pop("_total_value", None)
            item.pop("_available_value", None)
    else:
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
        category_rows.sort(
            key=lambda item: item.get("_total_value", Decimal("0")), reverse=True
        )
        top10_slice = category_rows[:10]
        top10_total = sum(item.get("_total_value", Decimal("0")) for item in top10_slice)
        top10_available = sum(
            item.get("_available_value", Decimal("0")) for item in top10_slice
        )
        top10_row = {
            "label": "Top 10 Total",
            "total": _format_currency(top10_total),
            "ineligible": _format_currency(max(top10_total - top10_available, Decimal("0"))),
            "available": _format_currency(top10_available),
            "pct_available": _format_pct(
                (top10_available / top10_total) if top10_total else Decimal("0")
            ),
        }
        for item in category_rows:
            item.pop("_total_value", None)
            item.pop("_available_value", None)

    raw_skus = []
    top20_total = _empty_summary_entry("Top 20 Total")
    sku_base_qs = WIPTop20HistoryRow.objects.filter(borrower=borrower)
    if normalized_division != "all":
        sku_base_qs = sku_base_qs.filter(division__iexact=normalized_division)
    sku_qs = sku_base_qs
    if start_date and end_date:
        range_qs = sku_base_qs.filter(as_of_date__range=(start_date, end_date))
        if range_qs.exists():
            sku_qs = range_qs
    sku_rows = []
    sku_dated = sku_qs.exclude(as_of_date__isnull=True)
    if sku_dated.exists():
        if start_date and end_date:
            sku_rows = list(sku_dated.filter(as_of_date__range=(start_date, end_date)))
        if not sku_rows:
            latest_date = sku_dated.order_by("-as_of_date").values_list("as_of_date", flat=True).first()
            if latest_date:
                fallback_start = latest_date - timedelta(days=364)
                sku_rows = list(
                    sku_dated.filter(as_of_date__range=(fallback_start, latest_date))
                )
    if not sku_rows:
        sku_rows = list(sku_qs)

    if sku_rows:
        sku_totals = OrderedDict()
        sku_meta = {}
        total_amount = Decimal("0")
        total_available = Decimal("0")
        for row in sku_rows:
            item_number = _format_item_number_value(row.sku)
            category = row.category or "—"
            description = row.description or "—"
            key = item_number
            if key not in sku_totals:
                sku_totals[key] = {
                    "item_number": item_number,
                    "amount": Decimal("0"),
                    "available": Decimal("0"),
                    "units": Decimal("0"),
                }
                sku_meta[key] = {
                    "category": category,
                    "description": description,
                    "row_key": (
                        row.as_of_date or date.min,
                        row.created_at or datetime.min,
                        row.id or 0,
                    ),
                }
            else:
                row_key = (
                    row.as_of_date or date.min,
                    row.created_at or datetime.min,
                    row.id or 0,
                )
                existing_key = sku_meta.get(key)
                if existing_key and row_key > existing_key["row_key"]:
                    existing_key.update(
                        {
                            "category": category,
                            "description": description,
                            "row_key": row_key,
                        }
                    )
            amount = _to_decimal(row.amount)
            pct_value = _to_decimal(row.pct_available)
            pct_ratio = pct_value / Decimal("100") if pct_value > 1 else pct_value
            available_amount = amount * pct_ratio
            sku_totals[key]["amount"] += amount
            sku_totals[key]["available"] += available_amount
            sku_totals[key]["units"] += _to_decimal(row.units)
            total_amount += amount
            total_available += available_amount

        sorted_skus = sorted(
            sku_totals.values(),
            key=lambda entry: entry["amount"],
            reverse=True,
        )
        top20_skus = sorted_skus[:20]
        top20_total_amount = Decimal("0")
        top20_available_amount = Decimal("0")
        for entry in top20_skus:
            meta = sku_meta.get(entry["item_number"], {})
            units_display = "—"
            if entry["units"] and entry["units"] > 0:
                if entry["units"] == entry["units"].to_integral_value():
                    units_display = f"{entry['units']:,.0f}"
                else:
                    units_display = f"{entry['units']:,.2f}"
            per_unit_value = (
                entry["amount"] / entry["units"] if entry["units"] else None
            )
            pct_available = (
                entry["available"] / entry["amount"] if entry["amount"] else None
            )
            raw_skus.append(
                {
                    "item_number": entry["item_number"],
                    "category": meta.get("category", "—"),
                    "description": meta.get("description", "—"),
                    "amount": _format_currency(entry["amount"]),
                    "units": units_display,
                    "per_unit": _format_currency(per_unit_value),
                    "pct_available": _format_pct(pct_available),
                    "status": "Current",
                }
            )
            top20_total_amount += entry["amount"]
            top20_available_amount += entry["available"]

        total_pct = (
            top20_available_amount / top20_total_amount
            if top20_total_amount
            else Decimal("0")
        )
        top20_total = {
            "label": "Top 20 Total",
            "total": _format_currency(top20_total_amount),
            "ineligible": "—",
            "available": _format_currency(top20_available_amount),
            "pct_available": _format_pct(total_pct),
        }

        other_amount = total_amount - top20_total_amount
        other_available = total_available - top20_available_amount
        sku_other_row = {
            "label": "Other items",
            "total": _format_currency(other_amount if other_amount > 0 else Decimal("0")),
            "ineligible": "—",
            "available": _format_currency(other_available if other_available > 0 else Decimal("0")),
            "pct_available": _format_pct(
                (other_available / other_amount) if other_amount else Decimal("0")
            ),
        }
        sku_grand_total = {
            "label": "Total",
            "total": _format_currency(total_amount),
            "ineligible": "—",
            "available": _format_currency(total_available),
            "pct_available": _format_pct(
                (total_available / total_amount) if total_amount else Decimal("0")
            ),
        }
    else:
        sku_rows = sorted(
            wip_rows,
            key=lambda row: _to_decimal(row.eligible_collateral),
            reverse=True,
        )
        top20_rows = sku_rows[:20]
        top20_amount = Decimal("0")
        top20_available = Decimal("0")
        for row in top20_rows:
            eligible = _to_decimal(row.eligible_collateral)
            beginning = _to_decimal(row.beginning_collateral)
            pct_available = (eligible / beginning) if beginning else Decimal("0")
            units = max(int(eligible), 0)
            value_per_unit = eligible / units if units else Decimal("0")
            raw_skus.append(
                {
                    "item_number": f"RM-{row.id}",
                    "category": row.main_type or "Inventory",
                    "description": row.sub_type or row.main_type or "Work-in-Progress",
                    "amount": _format_currency(beginning),
                    "units": f"{units:,}" if units else "—",
                    "per_unit": f"${value_per_unit:.2f}" if units else "—",
                    "pct_available": _format_pct(pct_available),
                    "status": "Current" if _to_decimal(row.net_collateral) >= 0 else "At Risk",
                }
            )
            top20_amount += beginning
            top20_available += eligible

        top20_total = {
            "label": "Top 20 Total",
            "total": _format_currency(top20_amount),
            "ineligible": _format_currency(max(top20_amount - top20_available, Decimal("0"))),
            "available": _format_currency(top20_available),
            "pct_available": _format_pct(
                (top20_available / top20_amount) if top20_amount else Decimal("0")
            ),
        }

    raw_skus = raw_skus[:20]

    category_other = base_context["work_in_progress_category_other"]
    footer = base_context["work_in_progress_category_footer"]
    sku_other_row = base_context["work_in_progress_top_skus_other"]
    sku_grand_total = base_context["work_in_progress_top_skus_total"]

    def _line_values(base, length=13):
        values = []
        for idx in range(length):
            variation = math.sin(idx / 2.0) * 0.04
            val = max(0.0, base * (1 + variation))
            values.append(val)
        return values

    base_value = float(total_available) if total_available else 0.0
    chart_values = _line_values(base_value)
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
            "yPrefix": "$ ",
            "ySuffix": "M",
            "yScale": 1_000_000,
            "yTicks": 6,
            "yDecimals": 1,
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
        "work_in_progress_top20_total": top20_total,
        "work_in_progress_top_skus_other": sku_other_row,
        "work_in_progress_top_skus_total": sku_grand_total,
        "work_in_progress_range_options": base_context["work_in_progress_range_options"],
        "work_in_progress_selected_range": base_context["work_in_progress_selected_range"],
        "work_in_progress_division_options": base_context["work_in_progress_division_options"],
        "work_in_progress_selected_division": base_context["work_in_progress_selected_division"],
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


def _other_collateral_context(borrower, snapshot_summary=None):
    if not borrower:
        resolved_snapshot = "Select a borrower to view snapshot summary."
    else:
        resolved_snapshot = snapshot_summary or "No snapshot summary available."
    base_context = {
        "other_collateral_snapshot_summary": resolved_snapshot,
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

    if not borrower:
        return base_context

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
        total_fmv_values = [
            _to_decimal(row.total_fair_market_value)
            for row in rows
            if getattr(row, "total_fair_market_value", None) is not None
        ]
        total_olv_values = [
            _to_decimal(row.total_orderly_liquidation_value)
            for row in rows
            if getattr(row, "total_orderly_liquidation_value", None) is not None
        ]
        total_fmv = max(total_fmv_values) if total_fmv_values else sum(
            _to_decimal(row.fair_market_value) for row in rows
        )
        total_olv = max(total_olv_values) if total_olv_values else sum(
            _to_decimal(row.orderly_liquidation_value) for row in rows
        )
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

    def _change_value(current, previous, fallback):
        baseline = previous if previous not in (None, 0) else fallback
        if baseline is None:
            return None
        return current - baseline

    change_fmv = _change_value(total_fmv, prev_total_fmv, estimated_fmv_total)
    change_olv = _change_value(total_olv, prev_total_olv, estimated_olv_total)
    change_rows = [
        {
            "label": "Fair Market Value",
            "value": _format_currency(change_fmv) if change_fmv is not None else "—",
            "delta": delta_fmv["value"] if delta_fmv else None,
            "delta_symbol": delta_fmv["symbol"] if delta_fmv else "",
            "delta_class": delta_fmv["delta_class"] if delta_fmv else "",
        },
        {
            "label": "Orderly Liquidation Value",
            "value": _format_currency(change_olv) if change_olv is not None else "—",
            "delta": delta_olv["value"] if delta_olv else None,
            "delta_symbol": delta_olv["symbol"] if delta_olv else "",
            "delta_class": delta_olv["delta_class"] if delta_olv else "",
        },
    ]

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
            "rows": change_rows,
            "info": "i",
            "deltas": [delta for delta in (delta_fmv, delta_olv) if delta],
            "row_deltas": True,
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
        variance_olv_amount = olv - estimated_olv
        variance_olv_pct = (
            variance_olv_amount / estimated_olv if estimated_olv else Decimal("0")
        )
        value_analysis_rows.append(
            {
                "db_id": row.pk,
                "equipment_type": row.equipment_type or "—",
                "manufacturer": row.manufacturer or "—",
                "fmv": _format_currency(fmv),
                "olv": _format_currency(olv),
                "estimated_fmv": _format_currency(estimated_fmv),
                "estimated_olv": _format_currency(estimated_olv),
                "variance_amount": _format_currency(variance_amount),
                "variance_pct": _format_pct(variance_pct),
                "variance_olv_amount": _format_currency(variance_olv_amount),
                "variance_olv_pct": _format_pct(variance_olv_pct),
            }
        )
        asset_rows.append(
            {
                "item_id": row.pk,
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

    month_map = OrderedDict()
    for key in snapshot_keys:
        rows = snapshots[key]
        _, olv = _aggregate(rows)
        if hasattr(key, "year") and hasattr(key, "month"):
            month_map[(key.year, key.month)] = float(olv)
        else:
            month_map[key] = float(olv)

    labels = []
    appraisal_series = []
    if month_map:
        latest_year = max(year for year, _ in month_map.keys())
        values = []
        for month in range(1, 13):
            values.append(month_map.get((latest_year, month)))
        first_idx = next((i for i, v in enumerate(values) if v is not None), None)
        if first_idx is not None:
            first_val = values[first_idx]
            for idx in range(first_idx):
                values[idx] = first_val
            for idx in range(first_idx + 1, len(values)):
                if values[idx] is None:
                    values[idx] = values[idx - 1]
            labels = [date(latest_year, month, 1).strftime("%b %Y") for month in range(1, 13)]
            appraisal_series = [float(v) for v in values]

    if not labels:
        max_points = 12
        values = []
        for key in snapshot_keys:
            rows = snapshots[key]
            _, olv = _aggregate(rows)
            values.append(
                {
                    "label": _label_from_timestamp(key),
                    "olv": float(olv),
                }
            )
        values = values[-max_points:]
        labels = [entry["label"] for entry in values]
        appraisal_series = [entry["olv"] for entry in values]

    estimated_series = [val * 0.96 for val in appraisal_series]
    chart_config = {
        "title": "Value Trend",
        "labels": labels,
        "estimated": [float(v) for v in estimated_series],
        "appraisal": [float(v) for v in appraisal_series],
    } if labels else base_context["other_collateral_value_trend_config"]

    return {
        **base_context,
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
    available_inventory = _to_decimal(current.available_inventory if current else 0)
    available_prev = _to_decimal(previous.available_inventory if previous else 0)
    available_delta = _format_delta(available_inventory, available_prev)
    metrics.append(
        {
            "label": "Available Inventory",
            "value": _format_currency(available_inventory),
            "delta": available_delta["value"] if available_delta else None,
            "symbol": available_delta["sign"] if available_delta else "",
            "delta_class": "success" if available_delta and available_delta["is_positive"] else "danger",
            "icon": ICON_SVGS["Available Inventory"],
        }
    )

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

    liquidation_costs = _to_decimal(current.ineligible_inventory if current else 0)
    liquidation_prev = _to_decimal(previous.ineligible_inventory if previous else 0)
    liquidation_delta = _format_delta(liquidation_costs, liquidation_prev)
    if liquidation_delta:
        liquidation_delta = {
            **liquidation_delta,
            "sign": "▲" if not liquidation_delta["is_positive"] else "▼",
        }
    metrics.append(
        {
            "label": "Liquidation Costs",
            "value": _format_currency(liquidation_costs),
            "delta": liquidation_delta["value"] if liquidation_delta else None,
            "symbol": liquidation_delta["sign"] if liquidation_delta else "",
            "delta_class": "danger" if liquidation_delta and liquidation_delta["is_positive"] else "success",
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


def _strip_inventory_prefix(text):
    if not text:
        return ""
    label = text.strip()
    if not label:
        return ""
    if label.lower().startswith("inventory"):
        label = label[len("inventory"):].lstrip(" -:/")
    return label.strip()


def _liquidation_item_label(row, default_label=None):
    for value in (row.sub_type, row.main_type):
        cleaned = _strip_inventory_prefix(value)
        if cleaned:
            return cleaned
    return default_label or "Item"


def _build_liquidation_category_table(rows, max_rows=5, default_label=None):
    total = sum((_to_decimal(row.beginning_collateral) or Decimal("0")) for row in rows)
    total_gross = sum((_to_decimal(row.eligible_collateral) or Decimal("0")) for row in rows)
    sorted_rows = sorted(rows, key=lambda row: _to_decimal(row.beginning_collateral), reverse=True)
    table = []
    aggregated = Decimal("0")
    aggregated_gross = Decimal("0")
    last_gr_pct = "0%"
    for idx, row in enumerate(sorted_rows[:max_rows]):
        cost = _to_decimal(row.beginning_collateral)
        eligible = _to_decimal(row.eligible_collateral)
        pct_cost = cost / total if total else Decimal("0")
        gr_pct = eligible / cost if cost else Decimal("0")
        item_label = _liquidation_item_label(row, default_label)
        table.append(
            {
                "rank": idx + 1,
                "item": item_label,
                "cost": _format_currency(cost),
                "gross": _format_currency(eligible),
                "percent": f"{pct_cost * 100:.0f}%",
                "gr_pct": _format_pct(gr_pct),
            }
        )
        aggregated += cost
        aggregated_gross += eligible
        last_gr_pct = table[-1]["gr_pct"]
    other_cost = total - aggregated
    other_gross = total_gross - aggregated_gross
    if other_cost > 0:
        other_gr_pct = other_gross / other_cost if other_cost else Decimal("0")
        table.append(
            {
                "rank": "Other",
                "item": "Other",
                "cost": _format_currency(other_cost),
                "gross": _format_currency(other_gross),
                "percent": f"{(other_cost / total * 100):.0f}%" if total else "0%",
                "gr_pct": _format_pct(other_gr_pct) if other_cost else last_gr_pct,
            }
        )
    table.append(
        {
            "rank": "Total",
            "item": "Total",
            "cost": _format_currency(total),
            "gross": _format_currency(total_gross),
            "percent": "100%",
            "gr_pct": _format_pct(total_gross / total if total else Decimal("0")),
        }
    )
    return table


def _latest_category_rows(qs):
    latest = qs.exclude(date__isnull=True).order_by("-date", "-created_at", "-id").first()
    if latest and latest.date:
        qs = qs.filter(date=latest.date)
    return list(qs)


def _build_liquidation_category_history_table(rows, default_label=None):
    if not rows:
        return []
    aggregated = {}
    for row in rows:
        label = row.category or default_label or "Item"
        cost = _to_decimal(row.total_inventory)
        gross = _to_decimal(row.available_inventory)
        bucket = aggregated.setdefault(
            label,
            {
                "cost": Decimal("0"),
                "gross": Decimal("0"),
            },
        )
        bucket["cost"] += cost
        bucket["gross"] += gross

    sorted_rows = sorted(
        aggregated.items(),
        key=lambda item: item[1]["cost"],
        reverse=True,
    )
    total = Decimal("0")
    total_gross = Decimal("0")
    table = []
    for label, values in sorted_rows:
        cost = values["cost"]
        gross = values["gross"]
        gr_pct = gross / cost if cost else Decimal("0")
        table.append(
            {
                "rank": None,
                "item": label,
                "cost": _format_currency(cost),
                "gross": _format_currency(gross),
                "percent": "",
                "gr_pct": _format_pct(gr_pct),
            }
        )
        total += cost
        total_gross += gross
    table.append(
        {
            "rank": "Total",
            "item": "Total",
            "cost": _format_currency(total),
            "gross": _format_currency(total_gross),
            "percent": "",
            "gr_pct": _format_pct(total_gross / total if total else Decimal("0")),
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
        "liquidation_payroll_rows": [],
        "liquidation_payroll_totals": {
            "fg": "—",
            "rm": "—",
            "wip": "—",
            "total": "—",
        },
        "liquidation_operating_rows": [],
        "liquidation_operating_totals": {
            "fg": "—",
            "rm": "—",
            "wip": "—",
            "total": "—",
        },
        "liquidation_liquidation_rows": [],
        "liquidation_liquidation_totals": {
            "fg": "—",
            "rm": "—",
            "wip": "—",
            "total": "—",
        },
        "liquidation_total_expenses": "—",
    }

    def _format_payroll_value(value):
        return _format_currency(value)

    def _decimal_or_none(value):
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(value)
        except Exception:
            try:
                return Decimal(str(value))
            except Exception:
                return None

    def _pct_ratio(value):
        pct = _decimal_or_none(value)
        if pct is None:
            return None
        return (pct / Decimal("100")) if pct > 1 else pct

    def _normalize_label(text):
        return (text or "").strip().lower()

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
    expense_groups = [
        {
            "title": "Payroll Expenses",
            "dropdown": False,
            "items": [
                ("Distribution Payroll", "distribution_payroll"),
                ("Administration Payroll", "administration_payroll"),
                ("Selling Payroll", "selling_payroll"),
                ("Commissions", "commissions"),
                ("Employee Incentive and Retention Bonus", "employee_incentive_bonus"),
                ("Employee Benefits and Taxes", "employee_benefits_taxes"),
            ],
        },
        {
            "title": "Operating Costs",
            "dropdown": True,
            "items": [
                ("Occupancy and Utilities", "occupancy_utilities"),
                ("Third Party Warehouse Costs", "third_party_warehouse_costs"),
                ("Independent Inventory Costs", "independent_inventory_costs"),
                ("Shipping Costs", "shipping_costs"),
                ("Royalty Costs", "royalty_costs"),
                ("Miscellaneous Costs", "miscellaneous_costs"),
            ],
        },
        {
            "title": "Liquidation Expenses",
            "dropdown": True,
            "items": [
                ("Advertising and Promotional", "advertising_promotional"),
                ("On-Site Management", "on_site_management"),
                ("Agent Commissions", "agent_commissions"),
            ],
        },
    ]
    groups = []
    for group in expense_groups:
        items = []
        total_amount = Decimal("0")
        for label, field in group["items"]:
            value = getattr(fg_expenses, field, None) if fg_expenses else None
            amount = _to_decimal(value)
            total_amount += amount
            items.append(
                {
                    "label": label,
                    "amount": _format_currency(amount),
                }
            )
        groups.append(
            {
                "title": group["title"],
                "dropdown": group["dropdown"],
                "items": items,
                "total": _format_currency(total_amount),
                "total_value": total_amount,
            }
        )

    fallback_groups = {group["title"]: group for group in groups}

    def _fallback_rows(title):
        group = fallback_groups.get(title)
        if not group:
            return [], Decimal("0"), {"fg": "—", "rm": "—", "wip": "—", "total": "—"}
        rows = [{"label": item["label"], "total": item["amount"]} for item in group["items"]]
        totals = {"fg": "—", "rm": "—", "wip": "—", "total": group["total"]}
        return rows, group["total_value"], totals

    payroll_rows, payroll_total_value, payroll_totals = _fallback_rows("Payroll Expenses")
    operating_rows, operating_total_value, operating_totals = _fallback_rows("Operating Costs")
    liquidation_rows, liquidation_total_value, liquidation_totals = _fallback_rows("Liquidation Expenses")

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

    raw_rows = _filter_inventory_rows_by_key(state, "raw_materials")
    wip_rows = _filter_inventory_rows_by_key(state, "work_in_progress")

    def _latest_created_rows(rows):
        dated_rows = [row for row in rows if row.created_at]
        if not dated_rows:
            return rows
        latest_date = max(row.created_at for row in dated_rows).date()
        return [row for row in rows if row.created_at and row.created_at.date() == latest_date]

    raw_rows_latest = _latest_created_rows(raw_rows)

    raw_category_qs = RMCategoryHistoryRow.objects.filter(borrower=borrower)
    wip_category_qs = WIPCategoryHistoryRow.objects.filter(borrower=borrower)
    raw_category_rows = _latest_category_rows(raw_category_qs)
    wip_category_rows = _latest_category_rows(wip_category_qs)

    category_tables = {
        "raw_materials": _build_liquidation_category_history_table(
            raw_category_rows, default_label="Raw Materials"
        )
        if raw_category_rows
        else _build_liquidation_category_table(raw_rows_latest, default_label="Raw Materials"),
        "work_in_progress": _build_liquidation_category_history_table(
            wip_category_rows, default_label="Work-In-Process"
        )
        if wip_category_rows
        else _build_liquidation_category_table(wip_rows, default_label="Work-In-Process"),
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

    # payroll_rows/operating_rows/liquidation_rows already seeded from expense groups

    nolv_entries = list(NOLVTableRow.objects.filter(borrower=borrower).order_by("-date", "-id"))
    liquidation_net_orderly_rows = net_rows
    liquidation_net_orderly_footer = net_footer
    if nolv_entries:
        payroll_rows = []
        operating_rows = []
        liquidation_rows = []
        payroll_totals = {"fg": "—", "rm": "—", "wip": "—", "total": "—"}
        operating_totals = {"fg": "—", "rm": "—", "wip": "—", "total": "—"}
        liquidation_totals = {"fg": "—", "rm": "—", "wip": "—", "total": "—"}
        payroll_total_value = Decimal("0")
        operating_total_value = Decimal("0")
        liquidation_total_value = Decimal("0")

        total_fg = Decimal("0")
        total_rm = Decimal("0")
        total_wip = Decimal("0")
        total_total = Decimal("0")
        dynamic_rows = []
        payroll_targets = [
            {"label": "Distribution Payroll", "aliases": ["distribution payroll"]},
            {"label": "Administration Payroll", "aliases": ["administration payroll"]},
            {"label": "Selling Payroll", "aliases": ["selling payroll"]},
            {
                "label": "Commissions",
                "aliases": ["commissions", "commission"],
            },
            {
                "label": "Employee Incentive and Retention Bonus",
                "aliases": [
                    "employee incentive and retention",
                    "employee incentive & retention",
                    "employee incentive and retention bonus",
                    "employee incentive & retention bonus",
                ],
            },
            {
                "label": "Employee Benefits and Taxes",
                "aliases": [
                    "employee benefits and taxes",
                    "employee benefits & taxes",
                ],
            },
        ]
        operating_targets = [
            {"label": "Occupancy and Utilities", "aliases": ["occupancy and utilities", "occupancy & utilities"]},
            {"label": "Third Party Warehouse Costs", "aliases": ["third party warehouse costs", "3rd party warehouse costs"]},
            {"label": "Independent Inventory Costs", "aliases": ["independent inventory costs"]},
            {"label": "Shipping Costs", "aliases": ["shipping costs", "shipping"]},
            {"label": "Royalty Costs", "aliases": ["royalty costs", "royalties"]},
            {"label": "Miscellaneous Costs", "aliases": ["miscellaneous costs", "misc costs", "miscellaneous"]},
        ]
        liquidation_targets = [
            {
                "label": "Advertising & Promotional Costs",
                "aliases": [
                    "advertising and promotional",
                    "advertising & promotional",
                    "advertising",
                    "advertising and promotional cost",
                    "advertising & promotional cost",
                    "advertising and promotional costs",
                    "advertising & promotional costs",
                ],
            },
            {"label": "On-Site Management", "aliases": ["on-site management", "on site management"]},
            {
                "label": "Agent Commission Costs",
                "aliases": [
                    "agent commissions",
                    "agent commission",
                    "agent commissions cost",
                    "agent commission cost",
                    "agent commission costs",
                ],
            },
        ]
        nolv_by_label = {}
        for entry in nolv_entries:
            fg_value = _to_decimal(entry.fg_usd)
            rm_value = _to_decimal(entry.rm_usd)
            wip_value = _to_decimal(entry.wip_usd)
            total_value = _to_decimal(entry.total_usd)
            total_fg += fg_value
            total_rm += rm_value
            total_wip += wip_value
            total_total += total_value
            norm_label = _normalize_label(entry.line_item)
            if norm_label and norm_label not in nolv_by_label:
                nolv_by_label[norm_label] = entry
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
        payroll_totals_raw = {"fg": Decimal("0"), "rm": Decimal("0"), "wip": Decimal("0"), "total": Decimal("0")}
        matches = 0
        for target in payroll_targets:
            entry = None
            for alias in target["aliases"]:
                entry = nolv_by_label.get(_normalize_label(alias))
                if entry:
                    break
            if entry:
                matches += 1
                fg_value = _to_decimal(entry.fg_usd)
                rm_value = _to_decimal(entry.rm_usd)
                wip_value = _to_decimal(entry.wip_usd)
                total_value = _to_decimal(entry.total_usd)
                payroll_totals_raw["fg"] += fg_value
                payroll_totals_raw["rm"] += rm_value
                payroll_totals_raw["wip"] += wip_value
                payroll_totals_raw["total"] += total_value
                payroll_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(fg_value),
                        "rm": _format_payroll_value(rm_value),
                        "wip": _format_payroll_value(wip_value),
                        "total": _format_payroll_value(total_value),
                    }
                )
            else:
                payroll_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(None),
                        "rm": _format_payroll_value(None),
                        "wip": _format_payroll_value(None),
                        "total": _format_payroll_value(None),
                    }
                )
        if matches:
            payroll_totals = {
                "fg": _format_payroll_value(payroll_totals_raw["fg"]),
                "rm": _format_payroll_value(payroll_totals_raw["rm"]),
                "wip": _format_payroll_value(payroll_totals_raw["wip"]),
                "total": _format_payroll_value(payroll_totals_raw["total"]),
            }
            payroll_total_value = payroll_totals_raw["total"]
        operating_totals_raw = {"fg": Decimal("0"), "rm": Decimal("0"), "wip": Decimal("0"), "total": Decimal("0")}
        operating_matches = 0
        for target in operating_targets:
            entry = None
            for alias in target["aliases"]:
                entry = nolv_by_label.get(_normalize_label(alias))
                if entry:
                    break
            if entry:
                operating_matches += 1
                fg_value = _to_decimal(entry.fg_usd)
                rm_value = _to_decimal(entry.rm_usd)
                wip_value = _to_decimal(entry.wip_usd)
                total_value = _to_decimal(entry.total_usd)
                operating_totals_raw["fg"] += fg_value
                operating_totals_raw["rm"] += rm_value
                operating_totals_raw["wip"] += wip_value
                operating_totals_raw["total"] += total_value
                operating_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(fg_value),
                        "rm": _format_payroll_value(rm_value),
                        "wip": _format_payroll_value(wip_value),
                        "total": _format_payroll_value(total_value),
                    }
                )
            else:
                operating_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(None),
                        "rm": _format_payroll_value(None),
                        "wip": _format_payroll_value(None),
                        "total": _format_payroll_value(None),
                    }
                )
        if operating_matches:
            operating_totals = {
                "fg": _format_payroll_value(operating_totals_raw["fg"]),
                "rm": _format_payroll_value(operating_totals_raw["rm"]),
                "wip": _format_payroll_value(operating_totals_raw["wip"]),
                "total": _format_payroll_value(operating_totals_raw["total"]),
            }
            operating_total_value = operating_totals_raw["total"]
        liquidation_totals_raw = {"fg": Decimal("0"), "rm": Decimal("0"), "wip": Decimal("0"), "total": Decimal("0")}
        liquidation_matches = 0
        liquidation_fallback_fields = {
            "Advertising & Promotional Costs": "advertising_promotional",
            "On-Site Management": "on_site_management",
            "Agent Commission Costs": "agent_commissions",
        }
        for target in liquidation_targets:
            entry = None
            for alias in target["aliases"]:
                entry = nolv_by_label.get(_normalize_label(alias))
                if entry:
                    break
            fallback_value = Decimal("0")
            if not entry and fg_expenses:
                fallback_field = liquidation_fallback_fields.get(target["label"])
                if fallback_field:
                    fallback_value = _to_decimal(getattr(fg_expenses, fallback_field, None))
            if entry:
                liquidation_matches += 1
                fg_value = _to_decimal(entry.fg_usd)
                rm_value = _to_decimal(entry.rm_usd)
                wip_value = _to_decimal(entry.wip_usd)
                total_value = _to_decimal(entry.total_usd)
                liquidation_totals_raw["fg"] += fg_value
                liquidation_totals_raw["rm"] += rm_value
                liquidation_totals_raw["wip"] += wip_value
                liquidation_totals_raw["total"] += total_value
                liquidation_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(fg_value),
                        "rm": _format_payroll_value(rm_value),
                        "wip": _format_payroll_value(wip_value),
                        "total": _format_payroll_value(total_value),
                    }
                )
            elif fallback_value:
                liquidation_matches += 1
                liquidation_totals_raw["total"] += fallback_value
                liquidation_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(None),
                        "rm": _format_payroll_value(None),
                        "wip": _format_payroll_value(None),
                        "total": _format_payroll_value(fallback_value),
                    }
                )
            else:
                liquidation_rows.append(
                    {
                        "label": target["label"],
                        "fg": _format_payroll_value(None),
                        "rm": _format_payroll_value(None),
                        "wip": _format_payroll_value(None),
                        "total": _format_payroll_value(None),
                    }
                )
        if liquidation_matches:
            liquidation_totals = {
                "fg": _format_payroll_value(liquidation_totals_raw["fg"]),
                "rm": _format_payroll_value(liquidation_totals_raw["rm"]),
                "wip": _format_payroll_value(liquidation_totals_raw["wip"]),
                "total": _format_payroll_value(liquidation_totals_raw["total"]),
            }
            liquidation_total_value = liquidation_totals_raw["total"]

    total_expenses_value = payroll_total_value + operating_total_value + liquidation_total_value
    if total_expenses_value:
        liquidation_total_expenses = _format_currency(total_expenses_value)
    else:
        liquidation_total_expenses = "—"

    def _blank_nolv_row(label):
        return {
            "label": label,
            "fg": "—",
            "fg_pct": "—",
            "rm": "—",
            "rm_pct": "—",
            "wip": "—",
            "wip_pct": "—",
            "total": "—",
            "total_pct": "—",
        }

    def _parse_money(value):
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        text = str(value).strip()
        if not text or text == "—":
            return None
        cleaned = text.replace("$", "").replace(",", "")
        try:
            return Decimal(cleaned)
        except Exception:
            return None

    def _sum_nolv_rows(rows):
        totals = {"fg": Decimal("0"), "rm": Decimal("0"), "wip": Decimal("0"), "total": Decimal("0")}
        has_values = False
        for row in rows:
            for key in ("fg", "rm", "wip", "total"):
                val = _parse_money(row.get(key))
                if val is None:
                    continue
                totals[key] += val
                has_values = True
        return totals if has_values else None

    def _build_nolv_row_from_amounts(label, totals):
        if not totals:
            return _blank_nolv_row(label)

        def _pct(val, base):
            if val is None or base <= 0:
                return "—"
            return _format_pct(val / base)

        fg_val = totals.get("fg")
        rm_val = totals.get("rm")
        wip_val = totals.get("wip")
        total_val = totals.get("total")
        return {
            "label": label,
            "fg": _format_currency(fg_val) if fg_val is not None else "—",
            "fg_pct": _pct(fg_val, finished_totals[0]),
            "rm": _format_currency(rm_val) if rm_val is not None else "—",
            "rm_pct": _pct(rm_val, raw_totals[0]),
            "wip": _format_currency(wip_val) if wip_val is not None else "—",
            "wip_pct": _pct(wip_val, wip_totals[0]),
            "total": _format_currency(total_val) if total_val is not None else "—",
            "total_pct": _pct(total_val, total_available_cost),
        }

    def _pick_nolv_row(rows_by_label, label, aliases=None):
        for key in [label] + (aliases or []):
            match = rows_by_label.get(_normalize_label(key))
            if match:
                row = dict(match)
                row["label"] = label
                return row
        return _blank_nolv_row(label)

    nolv_rows_by_label = {
        _normalize_label(row.get("label")): row
        for row in liquidation_net_orderly_rows
        if row.get("label")
    }
    payroll_totals_row = _build_nolv_row_from_amounts(
        "Total Payroll Costs",
        _sum_nolv_rows(payroll_rows),
    )
    operating_totals_row = _build_nolv_row_from_amounts(
        "Total Operating Costs", _sum_nolv_rows(operating_rows)
    )
    liquidation_totals_row = _build_nolv_row_from_amounts(
        "Total Liquidation Costs", _sum_nolv_rows(liquidation_rows)
    )
    liquidation_nolv_sections = [
        {"type": "row", "row": _pick_nolv_row(
            nolv_rows_by_label,
            "Available Inventory at Cost",
            aliases=["Available Inventory", "Inventory at Cost"],
        )},
        {"type": "row", "row": _pick_nolv_row(nolv_rows_by_label, "Gross Recovery")},
        {"type": "heading", "label": "Liquidation Expenses"},
        {"type": "subheading", "label": "Payroll Costs"},
    ]
    for label, aliases in [
        ("Distribution Payroll", ["distribution payroll"]),
        ("Administration Payroll", ["administration payroll"]),
        ("Selling Payroll", ["selling payroll"]),
        ("Commissions", ["commissions", "commission"]),
        (
            "Employee Incentive & Retention",
            ["employee incentive and retention", "employee incentive and retention bonus"],
        ),
        ("Employee Benefits and Taxes", ["employee benefits and taxes", "employee benefits & taxes"]),
    ]:
        liquidation_nolv_sections.append(
            {"type": "row", "row": _pick_nolv_row(nolv_rows_by_label, label, aliases=aliases)}
        )
    liquidation_nolv_sections.append({"type": "row", "row": payroll_totals_row})
    liquidation_nolv_sections.append({"type": "subheading", "label": "Operating Costs"})
    for label, aliases in [
        ("Occupancy and Utilities", ["occupancy and utilities", "occupancy & utilities"]),
        ("Third Party Warehouse Costs", ["third party warehouse costs", "3rd party warehouse costs"]),
        ("Independent Inventory Costs", ["independent inventory costs"]),
        ("Shipping Costs", ["shipping costs", "shipping"]),
        ("Royalty Costs", ["royalty costs", "royalties"]),
        ("Miscellaneous Costs", ["miscellaneous costs", "miscellaneous", "misc costs"]),
    ]:
        liquidation_nolv_sections.append(
            {"type": "row", "row": _pick_nolv_row(nolv_rows_by_label, label, aliases=aliases)}
        )
    liquidation_nolv_sections.append({"type": "row", "row": operating_totals_row})
    liquidation_nolv_sections.append(
        {
            "type": "row",
            "row": _pick_nolv_row(
                nolv_rows_by_label,
                "Advertising & Promotional Costs",
                aliases=["advertising & promotional costs", "advertising and promotional costs"],
            ),
        }
    )
    for label, aliases in [
        ("On-Site Management", ["on-site management", "on site management"]),
        ("Agent Commissions", ["agent commission costs", "agent commission cost", "agent commissions"]),
        ("Net Recovery", ["net recovery", "net orderly liquidated value"]),
    ]:
        liquidation_nolv_sections.append(
            {"type": "row", "row": _pick_nolv_row(nolv_rows_by_label, label, aliases=aliases)}
        )
    liquidation_nolv_sections.insert(
        len(liquidation_nolv_sections) - 1,
        {"type": "row", "row": liquidation_totals_row},
    )
    history_rows = []
    history_summary_rows = []
    total_cost = Decimal("0")
    total_selling = Decimal("0")
    total_gross = Decimal("0")
    def _pick_fg_history_label(history_row):
        category = _safe_str(history_row.category)
        type_label = _safe_str(history_row.type)
        generic = {
            "in-line",
            "inline",
            "in line",
            "total in-line",
            "total inline",
            "total in line",
            "excess",
            "total",
        }
        category_lower = category.lower()
        type_lower = type_label.lower()
        if category:
            if category_lower in generic and type_label:
                return type_label
            return category
        if type_label:
            return type_label
        if history_row.division:
            return _safe_str(history_row.division)
        return _format_date(history_row.as_of_date)

    for history_row in FGGrossRecoveryHistoryRow.objects.filter(borrower=borrower).order_by("id"):
        cost_value = _decimal_or_none(history_row.cost)
        selling_value = _decimal_or_none(history_row.selling_price)
        gross_value = _decimal_or_none(history_row.gross_recovery)
        pct_cost_ratio = _pct_ratio(history_row.pct_of_cost)
        pct_sp_ratio = _pct_ratio(history_row.pct_of_sp)
        gm_ratio = _pct_ratio(history_row.gm_pct)

        if gross_value is None and cost_value is not None and pct_cost_ratio:
            gross_value = cost_value * pct_cost_ratio
        if cost_value is None and gross_value is not None and pct_cost_ratio:
            cost_value = gross_value / pct_cost_ratio if pct_cost_ratio else None
        if selling_value is None and gross_value is not None and pct_sp_ratio:
            selling_value = gross_value / pct_sp_ratio if pct_sp_ratio else None
        if pct_cost_ratio is None and cost_value and gross_value:
            pct_cost_ratio = gross_value / cost_value if cost_value else None
        if pct_sp_ratio is None and selling_value and gross_value:
            pct_sp_ratio = gross_value / selling_value if selling_value else None
        if gm_ratio is None and selling_value and cost_value:
            gm_ratio = (selling_value - cost_value) / selling_value if selling_value else None

        cost_value = cost_value or Decimal("0")
        selling_value = selling_value or Decimal("0")
        gross_value = gross_value or Decimal("0")
        pct_cost_ratio = pct_cost_ratio or Decimal("0")
        pct_sp_ratio = pct_sp_ratio or Decimal("0")
        gm_ratio = gm_ratio or Decimal("0")

        total_cost += cost_value or Decimal("0")
        total_selling += selling_value or Decimal("0")
        total_gross += gross_value or Decimal("0")
        if history_row.wos is not None:
            wos_value = _to_decimal(history_row.wos)
            wos_display = f"{wos_value:,.1f}"
        else:
            wos_display = "0"
        label = _pick_fg_history_label(history_row)
        history_rows.append(
            {
                "date": _format_date(history_row.as_of_date),
                "division": _safe_str(history_row.division),
                "category": label,
                "type": _safe_str(history_row.type),
                "cost": _format_currency(cost_value),
                "selling": _format_currency(selling_value),
                "gross": _format_currency(gross_value),
                "pct_cost": _format_pct(pct_cost_ratio),
                "pct_sp": _format_pct(pct_sp_ratio),
                "wos": wos_display,
                "gr_pct": _format_pct(gm_ratio),
                "_row_key": (
                    history_row.as_of_date or date.min,
                    history_row.created_at or datetime.min,
                    history_row.id or 0,
                ),
                "_label": label,
            }
        )

    def _clean_history_row(row, label_override=None):
        cleaned = {key: value for key, value in row.items() if not key.startswith("_")}
        if label_override:
            cleaned["category"] = label_override
        return cleaned

    def _blank_history_row(label):
        return {
            "category": label,
            "cost": "—",
            "selling": "—",
            "gross": "—",
            "pct_cost": "—",
            "pct_sp": "—",
            "wos": "—",
            "gr_pct": "—",
        }

    primary_order = [
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
        "Other",
    ]
    tail_order = [
        "Total In-Line",
        "Excess",
        "Total",
    ]
    display_order = primary_order + tail_order

    if history_rows:

        def _normalize_fg_key(text):
            cleaned = "".join(ch if ch.isalnum() else " " for ch in (text or "").strip().lower())
            tokens = [token[:-1] if token.endswith("s") and len(token) > 1 else token for token in cleaned.split()]
            return " ".join(tokens).strip()

        def _alias_match(normalized_value, alias_norm):
            if not normalized_value or not alias_norm:
                return False
            if normalized_value == alias_norm or alias_norm in normalized_value:
                return True
            value_tokens = normalized_value.split()
            alias_tokens = alias_norm.split()
            alias_index = 0
            for token in value_tokens:
                if alias_tokens[alias_index] == token:
                    alias_index += 1
                    if alias_index == len(alias_tokens):
                        return True
            return False

        key_aliases = {
            "Cabinets": ["cabinet", "cabinets"],
            "Doors": ["door", "doors"],
            "Flooring Products": ["flooring product", "flooring products", "flooring"],
            "Moulding & Trim": ["moulding trim", "molding trim", "moulding and trim", "molding and trim"],
            "Decking": ["decking", "deck"],
            "Roofing": ["roofing", "roof"],
            "Windows": ["window", "windows"],
            "Hardware": ["hardware"],
            "Insulation": ["insulation"],
            "Tools": ["tools", "tool"],
            "Other": ["other", "others"],
            "Total In-Line": ["total in line", "total inline", "total in-line", "total inline"],
            "Excess": ["excess"],
            "Total": ["total"],
        }

        row_lookup = {}
        unmatched_lookup = {}
        for row in history_rows:
            label = row.get("_label") or ""
            normalized = _normalize_fg_key(label)
            if not normalized:
                existing = unmatched_lookup.get(label)
                if not existing or row.get("_row_key") > existing.get("_row_key", (date.min, datetime.min, 0)):
                    unmatched_lookup[label] = row
                continue
            matched_key = None
            for key in display_order:
                aliases = key_aliases.get(key, [])
                for alias in aliases:
                    alias_norm = _normalize_fg_key(alias)
                    if not alias_norm:
                        continue
                    if _alias_match(normalized, alias_norm):
                        matched_key = key
                        break
                if matched_key:
                    break
            if matched_key:
                existing = row_lookup.get(matched_key)
                if not existing or row.get("_row_key") > existing.get("_row_key", (date.min, datetime.min, 0)):
                    row_lookup[matched_key] = row
            else:
                label_key = row.get("_label") or row.get("category") or "—"
                existing = unmatched_lookup.get(label_key)
                if not existing or row.get("_row_key") > existing.get("_row_key", (date.min, datetime.min, 0)):
                    unmatched_lookup[label_key] = row

        primary_rows = []
        tail_rows = []
        for label in display_order:
            match = row_lookup.get(label)
            if match:
                cleaned = _clean_history_row(match, label)
                if label in tail_order:
                    tail_rows.append(cleaned)
                else:
                    primary_rows.append(cleaned)
        history_summary_rows = primary_rows

        extra_rows = [
            row
            for label, row in unmatched_lookup.items()
            if label not in row_lookup
        ]
        extra_rows.sort(key=lambda row: row.get("_row_key", (date.min, datetime.min, 0)), reverse=True)
        for row in extra_rows:
            history_summary_rows.append(_clean_history_row(row))

        history_summary_rows.extend(tail_rows)

        def _ensure_tail_row(label):
            if any(row.get("category") == label for row in history_summary_rows):
                return
            history_summary_rows.append(_blank_history_row(label))

        for label in ["Total In-Line", "Excess", "Total"]:
            _ensure_tail_row(label)

    else:
        history_summary_rows = []
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
        total_row_found = False
        for row in history_summary_rows:
            if row.get("category") == "Total":
                row.update(history_totals)
                row["category"] = "Total"
                total_row_found = True
                break
        if not total_row_found:
            filled_total = dict(history_totals)
            filled_total["category"] = "Total"
            history_summary_rows.append(filled_total)

    return {
        "liquidation_summary_metrics": summary_metrics,
        "liquidation_expense_groups": groups,
        "liquidation_finished_rows": liquidation_finished_rows,
        "liquidation_finished_footer": finished_footer,
        "liquidation_category_tables": category_tables,
        "liquidation_category_tabs": category_tabs,
        "liquidation_net_orderly_rows": liquidation_net_orderly_rows,
        "liquidation_net_orderly_footer": liquidation_net_orderly_footer,
        "liquidation_nolv_sections": liquidation_nolv_sections,
        "fg_gross_recovery_history_rows": history_summary_rows,
        "fg_gross_recovery_history_totals": history_totals,
        "liquidation_payroll_rows": payroll_rows,
        "liquidation_payroll_totals": payroll_totals,
        "liquidation_operating_rows": operating_rows,
        "liquidation_operating_totals": operating_totals,
        "liquidation_liquidation_rows": liquidation_rows,
        "liquidation_liquidation_totals": liquidation_totals,
        "liquidation_total_expenses": liquidation_total_expenses,
    }
