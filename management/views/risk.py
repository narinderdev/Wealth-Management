from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from management.models import (
    ARMetricsRow,
    CollateralOverviewRow,
    CompositeIndexRow,
    RiskSubfactorsRow,
)
from management.views.summary import (
    _build_borrower_summary,
    _format_currency,
    _format_pct,
    _normalize_pct,
    _to_decimal,
    get_borrower_status_context,
    get_preferred_borrower,
)


def _borrower_context(request):
    borrower = get_preferred_borrower(request)
    return {
        "borrower": borrower,
        "borrower_summary": _build_borrower_summary(borrower),
        **get_borrower_status_context(request),
    }


@login_required(login_url="login")
def risk_view(request):
    context = _borrower_context(request)
    borrower = context.get("borrower")
    if not borrower:
        return redirect("borrower_portfolio")
    ar_row = (
        ARMetricsRow.objects.filter(borrower=borrower)
        .order_by("-as_of_date", "-created_at")
        .first()
    )
    composite_rows = list(
        CompositeIndexRow.objects.filter(borrower=borrower).order_by("date")
    )
    composite_latest = composite_rows[-1] if composite_rows else None

    overall_score = _to_decimal(
        getattr(composite_latest, "overall_score", None)
    )
    rating_pct = float(min(max(overall_score / Decimal("5"), Decimal("0")), Decimal("1")) * 100) if overall_score else 0
    pill_list = []
    if composite_latest:
        pill_colors = ["blue", "navy", "lt", "wt"]
        weights = [
            ("Accounts Receivable", composite_latest.weight_ar),
            ("Inventory", composite_latest.weight_inventory),
            ("Company", composite_latest.weight_company),
            ("Industry", composite_latest.weight_industry),
        ]
        for idx, (label, weight) in enumerate(weights):
            pill_list.append({
                "label": label,
                "value": _format_pct(weight),
                "class": pill_colors[idx % len(pill_colors)],
            })
    ineligibles_sum = sum(
        (_to_decimal(row.ineligibles) for row in CollateralOverviewRow.objects.filter(borrower=borrower))
    )
    snapshot_text = (
        f"Risk levels remain manageable, though shifts in AR timing and a buildup of slower-moving inventory warrant closer monitoring. Core operations and liquidity are stable, and industry demand remains in line with recent trends. Continued focus on collections and inventory reduction will help maintain a balanced risk profile.· "
        
    )

    trend_points = []
    trend_axis = []
    trend_coords = []
    trend_values = []
    trend_data = []
    for idx, row in enumerate(composite_rows[-8:]):
        score = _to_decimal(row.overall_score) if row.overall_score else Decimal("0")
        ratio = float(min(max(score / Decimal("5"), Decimal("0")), Decimal("1")))
        x = 18 + idx * 37
        y = 90 - ratio * 40
        trend_points.append(f"{x},{y}")
        trend_coords.append({"x": x, "y": y})
        label = row.date.strftime("%b") if row.date else str(idx + 1)
        trend_axis.append(label)
        trend_values.append(f"{score:.1f}")
        trend_data.append({"x": x, "y": y, "label": label, "score": f"{score:.1f}"})

    high_factors = []
    prior_scores = {}
    history_map = {}
    for row in RiskSubfactorsRow.objects.filter(borrower=borrower).order_by("-risk_score", "-date")[:12]:
        key = (row.sub_risk or row.high_impact_factor or row.main_category or "Risk").strip()
        if not key:
            continue
        current = _normalize_pct(row.risk_score) or Decimal("0")
        prior = prior_scores.get(key, None)
        change = (current - prior) if prior is not None else None
        direction = "up" if change and change > 0 else "down" if change and change < 0 else ""
        change_display = (
            f"{'▲ ' if direction == 'up' else '▼ ' if direction == 'down' else ''}{abs(change):.1f}"
            if change is not None and change != 0
            else "—"
        )
        history_map[key.lower()] = {
            "risk": key,
            "current": f"{current:.1f}",
            "prior": f"{prior:.1f}" if prior is not None else "—",
            "change": change_display,
            "direction": direction,
        }
        prior_scores[key] = current

    desired_high_impacts = [
        "Inventory Velocity & Turn",
        "Excess & Obsolete",
        "Sales Trend",
        "Seasonality",
        "Sector Level Distress",
    ]

    for label in desired_high_impacts:
        entry = history_map.get(label.lower())
        if entry:
            high_factors.append(entry)
        else:
            high_factors.append({
                "risk": label,
                "current": "—",
                "prior": "—",
                "change": "—",
                "direction": "",
            })

    def bar_width(value):
        pct = float(min(max(value or 0, 0), 1) * 100)
        return f"{pct:.1f}%"

    ar_past_due_pct = _normalize_pct(ar_row.pct_past_due) if ar_row and ar_row.pct_past_due is not None else Decimal("0")
    ar_score = max(Decimal("0"), min(Decimal("5"), Decimal("5") - (ar_past_due_pct / Decimal("20"))))

    risk_rows = list(
        RiskSubfactorsRow.objects.filter(borrower=borrower).order_by("main_category", "sub_risk")
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

    order_definitions = {
        "accounts receivable": [
            "DSO Trend",
            "Past Due % AR",
            "Concentration",
            "Dilution",
            "Write-off",
            "Sales Volatility",
            "Dispute Frequency",
            "Eligibility Impact",
            "Process Risk",
            "Cross Aging Risk",
        ],
        "inventory": [
            "Inventory Velocity & Turn",
            "Excess & Obsolete",
            "Margin Volatility",
            "Cost Inflation",
            "Write Down & Scrap",
            "Inventory Mix",
            "WIP & RM Build",
            "SKU Concentration",
            "Seasonality",
            "Customer Specific Exposure",
            "Lead Time & Supply Disruption",
            "Vendor Concentration",
            "Production Lead Time",
        ],
        "company": [
            "Liquidity",
            "Profitability",
            "Cash Flow Stability",
            "DPO Trend",
            "Sales Trends",
            "Customer Health",
            "Vendor Health",
            "Liquidation Channel Risk",
            "Inventory Count Accuracy",
            "System Risk",
            "Data Quality & Integrity",
            "Customer Relationship Strength",
            "Operational Risk",
        ],
        "industry": [
            "Demand Volatility",
            "Input Cost Variability",
            "Competitive Pressure",
            "Sector Level Distress",
            "Industry Seasonality",
            "Inflation & Deflation Risk",
            "Regulatory Stability",
            "Disruption Risk",
            "Supply Chain Stability",
            "Geopolitical Risk",
            "End Market Outlook",
            "Competitive Risk",
        ],
    }

    def _build_metric(label, fallback_score, ordering=None):
        rows = _metric_rows(label)
        bars_dict = {}
        score_vals = []
        for row in rows:
            metric_label = _row_label(row)
            if metric_label in bars_dict:
                continue
            score = _to_decimal(row.risk_score)
            score_vals.append(score)
            pct = float(min(max(score / Decimal("5"), Decimal("0")), Decimal("1")) * 100)
            bars_dict[metric_label] = f"{pct:.1f}%"

        if ordering:
            bars = []
            for name in ordering:
                if name in bars_dict:
                    bars.append({"label": name, "width": bars_dict.pop(name)})
            for remaining, width in bars_dict.items():
                bars.append({"label": remaining, "width": width})
        else:
            bars = [{"label": name, "width": width} for name, width in bars_dict.items()]

        if not bars:
            bars = [
                {"label": "Trend", "width": "35%"},
                {"label": "Pressure", "width": "55%"},
            ]

        if score_vals:
            score_val = sum(score_vals) / Decimal(len(score_vals))
        else:
            score_val = fallback_score
        return {"label": label, "score": score_val, "bars": bars}

    metric_definitions = [
        {"label": "Accounts Receivable", "fallback": max(ar_score, Decimal("3")), "color": "#f59e0b"},
        {"label": "Inventory", "fallback": _to_decimal(composite_latest.inventory_risk) if composite_latest else Decimal("3"), "color": "#fbbf24"},
        {"label": "Company", "fallback": _to_decimal(composite_latest.company_risk) if composite_latest else Decimal("2.5"), "color": "#22c55e"},
        {"label": "Industry", "fallback": _to_decimal(composite_latest.industry_risk) if composite_latest else Decimal("2"), "color": "#facc15"},
    ]

    def _risk_color(score):
        palette = ["#7EC459", "#D7C63C", "#FBB82E", "#FC8F2E", "#F74C34"]
        dec_score = _to_decimal(score)
        if dec_score <= 0:
            return palette[2]
        bucket = int(dec_score.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        bucket = max(1, min(5, bucket))
        return palette[bucket - 1]

    risk_metrics = []
    for defn in metric_definitions:
        metric = _build_metric(
            defn["label"],
            defn["fallback"],
            ordering=order_definitions.get(defn["label"].lower()),
        )
        metric["donut_color"] = _risk_color(metric.get("score") or defn["fallback"])
        metric["donut_bg"] = "#e5e7eb"
        metric["fill_color"] = "#0b57d0"
        risk_metrics.append(metric)
    processed_metrics = []
    for metric in risk_metrics:
        score_val = _to_decimal(metric.get("score")) if metric.get("score") is not None else Decimal("0")
        norm = float(min(max(score_val / Decimal("5"), Decimal("0")), Decimal("1")) * 100)
        metric["score_display"] = f"{score_val:.1f}"
        metric["donut_dash"] = f"{norm:.1f} {max(0.0, 100.0 - norm):.1f}"
        metric["bars"] = metric.get("bars", [])
        metric["donut_color"] = _risk_color(score_val)
        processed_metrics.append(metric)

    rating_color = _risk_color(overall_score)

    context.update({
        "active_tab": "risk",
        "risk": {
            "rating_score": f"{overall_score:.1f}",
            "rating_position": rating_pct,
            "rating_dasharray": f"{rating_pct:.1f} {max(0.0, 100.0 - rating_pct):.1f}",
            "rating_color": rating_color,
            "snapshot": snapshot_text,
            "pills": pill_list,
            "trend_points": " ".join(trend_points) if trend_points else "0,80 40,70 80,75",
            "trend_coords": trend_coords or [
                {"x": 18, "y": 72}, {"x": 55, "y": 60}, {"x": 92, "y": 46}, {"x": 129, "y": 44},
                {"x": 166, "y": 52}, {"x": 203, "y": 66}, {"x": 240, "y": 84}, {"x": 277, "y": 70},
            ],
            "trend_axis": trend_axis or ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug"],
            "trend_values": trend_values or ["3.5","3.7","3.9","4.0","4.1","4.2","4.3","3.9"],
            "trend_data": trend_data or [
                {"x": 18, "y": 72, "label": "Jan", "score": "3.5"},
                {"x": 55, "y": 60, "label": "Feb", "score": "3.7"},
            ],
            "high_impact": high_factors,
            "metrics": processed_metrics,
        },
    })
    return render(request, "risk/risk.html", context)
