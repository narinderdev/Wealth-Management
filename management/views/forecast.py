
from decimal import Decimal
from datetime import date

import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from management.models import ForecastRow, SnapshotSummaryRow
from management.views.summary import (
    _build_borrower_summary,
    get_borrower_status_context,
    get_preferred_borrower,
    _to_decimal,
    get_snapshot_summary_map,
)


def _format_row_label(row):
    date_val = row.as_of_date or row.period
    if hasattr(date_val, "strftime"):
        return date_val.strftime("%b %y")
    if date_val is not None:
        return str(date_val)
    return f"Entry {row.id}"


def _row_date(row):
    return row.as_of_date or row.period


def _classify_row(row, today):
    flag = (row.actual_forecast or "").lower()
    if "forecast" in flag or "project" in flag or "plan" in flag:
        return "forecast"
    if "actual" in flag or "historical" in flag:
        return "actual"
    row_date = _row_date(row)
    if hasattr(row_date, "__gt__") and row_date is not None:
        if row_date > today:
            return "forecast"
    return "actual"


def _build_series(rows, accessor):
    return [_to_decimal(accessor(row)) for row in rows]


def _build_chart_data(rows):
    if not rows:
        return {}

    ordered_rows = sorted(
        rows,
        key=lambda r: (
            r.as_of_date or r.period or r.created_at or r.id,
            r.id,
        ),
    )
    today = date.today()
    classifications = [(row, _classify_row(row, today)) for row in ordered_rows]
    actual_rows = [row for row, kind in classifications if kind == "actual"]
    forecast_rows = [row for row, kind in classifications if kind == "forecast"]
    if not actual_rows:
        actual_rows = [ordered_rows[0]]
        actual_ids = {row.id for row in actual_rows}
        forecast_rows = [row for row in ordered_rows if row.id not in actual_ids]
    else:
        actual_ids = {row.id for row in actual_rows}
        if not forecast_rows:
            forecast_rows = [row for row in ordered_rows if row.id not in actual_ids]

    labels = [_format_row_label(row) for row in ordered_rows]

    def _value(attr, row):
        return _to_decimal(getattr(row, attr))

    def _value_liquidity(row):
        return _to_decimal(row.available_collateral) + _to_decimal(row.revolver_availability)

    def _value_weeks(row):
        sales = _to_decimal(row.net_sales)
        finished = _to_decimal(row.finished_goods)
        if sales:
            return (finished / sales) * Decimal("52")
        return Decimal("0")

    specs = {
        "availableCollateral": {
            "getter": lambda row: _value("available_collateral", row),
            "title": "Available Collateral",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 5,
        },
        "revolverBalance": {
            "getter": lambda row: _value("revolver_availability", row),
            "title": "Revolver Balance",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 5,
        },
        "availableLiquidity": {
            "getter": _value_liquidity,
            "title": "Available Liquidity",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 6,
        },
        "sales": {
            "getter": lambda row: _value("net_sales", row),
            "title": "Sales",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 5,
        },
        "grossMargin": {
            "getter": lambda row: _value("gross_margin_pct", row) * Decimal("100"),
            "title": "Gross Margin",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "",
            "yFormat": "pct",
            "yTicks": 5,
        },
        "accountsReceivable": {
            "getter": lambda row: _value("ar", row),
            "title": "Accounts Receivable",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 6,
        },
        "finishedGoods": {
            "getter": lambda row: _value("finished_goods", row),
            "title": "Finished Goods",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 5,
        },
        "weeksOfSupply": {
            "getter": _value_weeks,
            "title": "Weeks of Supply",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "",
            "yFormat": "num",
            "yTicks": 5,
        },
        "rawMaterials": {
            "getter": lambda row: _value("raw_materials", row),
            "title": "Raw Materials",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 5,
        },
        "workInProcess": {
            "getter": lambda row: _value("work_in_process", row),
            "title": "Work In Process",
            "pastLabel": "Actual",
            "forecastLabel": "Forecast",
            "yPrefix": "$",
            "yFormat": "short",
            "yTicks": 5,
        },
    }

    charts = {}
    for key, spec in specs.items():
        actual_vals = [spec["getter"](row) for row in actual_rows]
        forecast_vals = [spec["getter"](row) for row in forecast_rows] if forecast_rows else []
        charts[key] = {
            "title": spec["title"],
            "labels": labels,
            "actual": [float(val) for val in actual_vals],
            "forecast": [float(val) for val in forecast_vals],
            "pastLabel": spec.get("pastLabel", "Actual"),
            "forecastLabel": spec.get("forecastLabel", "Forecast"),
            "yPrefix": spec.get("yPrefix", ""),
            "yFormat": spec.get("yFormat", "short"),
            "yTicks": spec.get("yTicks", 5),
        }
    return charts


def _format_currency_with_cents(value):
    if value is None:
        return "—"
    try:
        amount = Decimal(value)
    except (TypeError, ValueError):
        try:
            amount = Decimal(str(value))
        except Exception:
            return "—"
    return f"${amount:,.2f}"


def _format_pct_change(value):
    if value is None:
        return "—"
    try:
        pct = Decimal(value)
    except (TypeError, ValueError):
        try:
            pct = Decimal(str(value))
        except Exception:
            return "—"
    return f"{pct:.2f}%"


def _price_target_snapshot():
    snapshot = {
        "analyst_count": 42,
        "months": 12,
        "company": "Meta Platforms",
        "window_months": 3,
        "avg_target": Decimal("846.48"),
        "high_target": Decimal("1117.00"),
        "low_target": Decimal("655.15"),
        "last_price": Decimal("609.46"),
    }
    change_pct = None
    if snapshot["last_price"]:
        change_pct = (
            (snapshot["avg_target"] - snapshot["last_price"])
            / snapshot["last_price"]
            * Decimal("100")
        )
    snapshot.update(
        {
            "avg_target_display": _format_currency_with_cents(snapshot["avg_target"]),
            "high_target_display": _format_currency_with_cents(snapshot["high_target"]),
            "low_target_display": _format_currency_with_cents(snapshot["low_target"]),
            "last_price_display": _format_currency_with_cents(snapshot["last_price"]),
            "change_pct_display": _format_pct_change(change_pct),
        }
    )
    return snapshot


def _borrower_context(request):
    borrower = get_preferred_borrower(request)
    return {"borrower_summary": _build_borrower_summary(borrower)}


@login_required(login_url="login")
def forecast_view(request):
    borrower = get_preferred_borrower(request)
    rows = []
    if borrower:
        rows = (
            ForecastRow.objects.filter(borrower=borrower)
            .order_by("as_of_date", "period", "created_at", "id")
        )
    snapshot_sections = [
        SnapshotSummaryRow.SECTION_FORECAST_LIQUIDITY,
        SnapshotSummaryRow.SECTION_FORECAST_SALES_GM,
        SnapshotSummaryRow.SECTION_FORECAST_AR,
        SnapshotSummaryRow.SECTION_FORECAST_INVENTORY,
    ]
    snapshot_map = get_snapshot_summary_map(borrower, snapshot_sections)
    context = _borrower_context(request)
    context.update(get_borrower_status_context(request))
    context["forecast_charts"] = _build_chart_data(rows)
    context["active_tab"] = "forecast"
    context["forecast_charts_json"] = json.dumps(context["forecast_charts"])
    context["price_target"] = _price_target_snapshot()
    context["forecast_snapshots"] = {
        "liquidity": snapshot_map.get(SnapshotSummaryRow.SECTION_FORECAST_LIQUIDITY),
        "sales_gm": snapshot_map.get(SnapshotSummaryRow.SECTION_FORECAST_SALES_GM),
        "ar": snapshot_map.get(SnapshotSummaryRow.SECTION_FORECAST_AR),
        "inventory": snapshot_map.get(SnapshotSummaryRow.SECTION_FORECAST_INVENTORY),
    }
    return render(request, "forecast/forecast.html", context)
