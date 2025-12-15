import json
import math

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from management.models import (
    ARMetricsRow,
    BorrowerReport,
    CollateralOverviewRow,
    FGIneligibleDetailRow,
    FGInventoryMetricsRow,
    FGInlineCategoryAnalysisRow,
)
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
        **_finished_goals_context(borrower),
        **_raw_materials_context(borrower),
        **_work_in_progress_context(borrower),
        **_liquidation_model_context(borrower),
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
        CollateralOverviewRow.objects.filter(report=latest_report).order_by("id")
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
        "liquidation_category_tables": {"raw_materials": [], "work_in_progress": []},
        "liquidation_net_orderly_rows": [],
        "liquidation_net_orderly_footer": {
            "label": "Net Orderly Liquidated Value",
            "finished": "—",
            "raw": "—",
            "wip": "—",
            "scrap": "—",
            "pct": "—",
        },
    }

    state = _inventory_state(borrower)
    if not state:
        return base_context

    latest_report = state["latest_report"]
    metrics_rows = list(FGInventoryMetricsRow.objects.filter(report=latest_report).order_by("-as_of_date"))
    current_metrics = metrics_rows[0] if metrics_rows else None
    previous_metrics = metrics_rows[1] if len(metrics_rows) > 1 else None

    summary_metrics = _build_liquidation_metrics(current_metrics, previous_metrics)

    fg_expenses = FGIneligibleDetailRow.objects.filter(report=latest_report).order_by("-date").first()
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

    net_rows = [
        {
            "label": "Available Inventory at Cost",
            "finished": _format_currency(finished_totals[0]),
            "raw": _format_currency(raw_totals[0]),
            "wip": _format_currency(wip_totals[0]),
            "scrap": _format_currency(scrap_total),
        },
        {
            "label": "Gross Recovery",
            "finished": _format_currency(finished_totals[1]),
            "raw": _format_currency(raw_totals[1]),
            "wip": _format_currency(wip_totals[1]),
            "scrap": _format_currency(scrap_recovery),
        },
    ]

    def _add_cost_row(label, factor):
        return {
            "label": label,
            "finished": _format_currency(finished_totals[0] * factor),
            "raw": _format_currency(raw_totals[0] * factor),
            "wip": _format_currency(wip_totals[0] * factor),
            "scrap": _format_currency(scrap_total * factor),
            "pct": f"-{factor*100:.1f}%",
        }

    net_rows.append(_add_cost_row("Liquidation / Sales Fees", Decimal("0.024")))
    net_rows.append(_add_cost_row("Storage / Handling", Decimal("0.016")))
    net_rows.append(_add_cost_row("Opportunity / Utilization Costs", Decimal("0.010")))
    net_rows.append(_add_cost_row("Transport / Logistics", Decimal("0.012")))

    net_footer = {
        "label": "Net Orderly Liquidated Value",
        "finished": _format_currency(finished_totals[1] * Decimal("0.8")),
        "raw": _format_currency(raw_totals[1] * Decimal("0.8")),
        "wip": _format_currency(wip_totals[1] * Decimal("0.8")),
        "scrap": _format_currency(scrap_recovery * Decimal("0.8")),
        "pct": "54.8%",
    }

    return {
        "liquidation_summary_metrics": summary_metrics,
        "liquidation_expense_groups": groups,
        "liquidation_finished_rows": liquidation_finished_rows,
        "liquidation_finished_footer": finished_footer,
        "liquidation_category_tables": category_tables,
        "liquidation_category_tabs": category_tabs,
        "liquidation_net_orderly_rows": net_rows,
        "liquidation_net_orderly_footer": net_footer,
    }
