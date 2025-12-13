import math

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from management.models import BorrowerReport, CollateralOverviewRow
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
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
    }
    return render(request, "collateral_dynamic/inventory_page.html", context)


@login_required(login_url="login")
def collateral_static_view(request):
    return render(
        request,
        "collateral_dynamic/static_insights.html",
        {"active_tab": "collateral_static"},
    )


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

    if not borrower:
        return context

    latest_report = (
        BorrowerReport.objects.filter(borrower=borrower).order_by("-report_date").first()
    )
    if not latest_report:
        return context

    collateral_rows = list(
        CollateralOverviewRow.objects.filter(report=latest_report).order_by("id")
    )

    inventory_rows = [
        row for row in collateral_rows if row.main_type and "inventory" in row.main_type.lower()
    ]
    if not inventory_rows:
        return context

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
