from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence, Union

from django.utils import timezone

from management.models import (
    Borrower,
    CollateralOverviewRow,
    FGIneligibleDetailRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    FGInventoryMetricsRow,
    HistoricalTop20SKUsRow,
    SalesGMTrendRow,
)


DecimalInput = Union[Decimal, int, float, str]


def _d(value: DecimalInput) -> Decimal:
    return Decimal(str(value))


@dataclass
class _CollateralSnapshot:
    sub_type: str
    beginning: Decimal
    eligible: Decimal
    ineligible: Decimal
    pre_reserve: Decimal
    reserve: Decimal
    nolv_pct: Decimal
    advanced_rate: Decimal


def _collateral_rows() -> Sequence[_CollateralSnapshot]:
    return [
        _CollateralSnapshot(
            sub_type="Finished Goods",
            beginning=_d("1450000"),
            eligible=_d("1250000"),
            ineligible=_d("180000"),
            pre_reserve=_d("50000"),
            reserve=_d("25000"),
            nolv_pct=_d("0.68"),
            advanced_rate=_d("0.85"),
        ),
        _CollateralSnapshot(
            sub_type="Raw Materials",
            beginning=_d("510000"),
            eligible=_d("450000"),
            ineligible=_d("60000"),
            pre_reserve=_d("15000"),
            reserve=_d("10000"),
            nolv_pct=_d("0.6"),
            advanced_rate=_d("0.75"),
        ),
        _CollateralSnapshot(
            sub_type="Work-in-Progress",
            beginning=_d("300000"),
            eligible=_d("245000"),
            ineligible=_d("40000"),
            pre_reserve=_d("10000"),
            reserve=_d("5000"),
            nolv_pct=_d("0.55"),
            advanced_rate=_d("0.65"),
        ),
    ]


def _ensure_collateral_overview(borrower: Borrower) -> None:
    for snapshot in _collateral_rows():
        net_value = snapshot.eligible - snapshot.ineligible - snapshot.reserve
        CollateralOverviewRow.objects.create(
            borrower=borrower,
            main_type="Inventory",
            sub_type=snapshot.sub_type,
            beginning_collateral=snapshot.beginning,
            ineligibles=snapshot.ineligible,
            eligible_collateral=snapshot.eligible,
            nolv_pct=snapshot.nolv_pct,
            advanced_rate=snapshot.advanced_rate,
            pre_reserve_collateral=snapshot.pre_reserve,
            reserves=snapshot.reserve,
            net_collateral=net_value if net_value > 0 else _d("0"),
        )


def _ensure_fg_metrics(borrower: Borrower, as_of: date) -> None:
    total_inventory = _d("1450000")
    ineligible_inventory = _d("180000")
    available_inventory = total_inventory - ineligible_inventory
    FGInventoryMetricsRow.objects.create(
        borrower=borrower,
        inventory_type="Finished Goods",
        division="All",
        as_of_date=as_of,
        total_inventory=total_inventory,
        ineligible_inventory=ineligible_inventory,
        available_inventory=available_inventory,
        ineligible_pct_of_inventory=ineligible_inventory / total_inventory,
    )


def _ensure_ineligible_detail(borrower: Borrower, as_of: date) -> None:
    FGIneligibleDetailRow.objects.create(
        borrower=borrower,
        division="All",
        inventory_type="Finished Goods",
        date=as_of,
        slow_moving_obsolete=_d("62000"),
        aged=_d("42000"),
        off_site=_d("21000"),
        consigned=_d("16000"),
        in_transit=_d("12000"),
        damaged_non_saleable=_d("19000"),
        total_ineligible=_d("180000"),
        ineligible_pct_of_inventory=_d("0.12"),
    )


def _ensure_inline_category_rows(borrower: Borrower, as_of: date) -> None:
    data = [
        {
            "category": "Core Apparel",
            "fg_total": _d("520000"),
            "fg_ineligible": _d("64000"),
            "fg_available": _d("456000"),
            "sales": _d("610000"),
            "cogs": _d("420000"),
            "gm": _d("190000"),
            "gm_pct": _d("0.31"),
            "weeks": _d("10"),
        },
        {
            "category": "Outdoor",
            "fg_total": _d("380000"),
            "fg_ineligible": _d("38000"),
            "fg_available": _d("342000"),
            "sales": _d("460000"),
            "cogs": _d("295000"),
            "gm": _d("165000"),
            "gm_pct": _d("0.36"),
            "weeks": _d("8"),
        },
        {
            "category": "Electronics",
            "fg_total": _d("350000"),
            "fg_ineligible": _d("42000"),
            "fg_available": _d("308000"),
            "sales": _d("500000"),
            "cogs": _d("315000"),
            "gm": _d("185000"),
            "gm_pct": _d("0.37"),
            "weeks": _d("7"),
        },
    ]
    for row in data:
        pct = row["fg_available"] / _d("1250000")
        FGInlineCategoryAnalysisRow.objects.create(
            borrower=borrower,
            division="All",
            as_of_date=as_of,
            category=row["category"],
            fg_total=row["fg_total"],
            fg_ineligible=row["fg_ineligible"],
            fg_available=row["fg_available"],
            pct_of_available=pct,
            sales=row["sales"],
            cogs=row["cogs"],
            gm=row["gm"],
            gm_pct=row["gm_pct"],
            weeks_of_supply=row["weeks"],
        )


def _ensure_inline_excess_rows(borrower: Borrower, as_of: date) -> None:
    data = [
        {
            "category": "Core Apparel",
            "available": _d("456000"),
            "inline": _d("360000"),
            "excess": _d("96000"),
        },
        {
            "category": "Outdoor",
            "available": _d("342000"),
            "inline": _d("270000"),
            "excess": _d("72000"),
        },
        {
            "category": "Electronics",
            "available": _d("308000"),
            "inline": _d("232000"),
            "excess": _d("76000"),
        },
    ]
    for row in data:
        FGInlineExcessByCategoryRow.objects.create(
            borrower=borrower,
            division="All",
            as_of_date=as_of,
            category=row["category"],
            fg_available=row["available"],
            inline_dollars=row["inline"],
            inline_pct=row["inline"] / row["available"] if row["available"] else _d("0"),
            excess_dollars=row["excess"],
            excess_pct=row["excess"] / row["available"] if row["available"] else _d("0"),
        )


def _ensure_sales_trend(borrower: Borrower, as_of: date) -> None:
    SalesGMTrendRow.objects.create(
        borrower=borrower,
        division="All",
        as_of_date=as_of,
        net_sales=_d("1575000"),
        gross_margin_pct=_d("0.35"),
        gross_margin_dollars=_d("551250"),
        ttm_sales=_d("18000000"),
        ttm_sales_prior=_d("16600000"),
        trend_ttm_pct=_d("0.084"),
        ma3=_d("0.34"),
        ma3_prior=_d("0.31"),
        trend_3_m_pct=_d("0.045"),
    )


def _ensure_top_skus(borrower: Borrower, as_of: date) -> None:
    items = [
        {
            "item_number": _d("1001"),
            "category": "Core Apparel",
            "description": "Premium fleece jacket",
            "cost": _d("42000"),
            "pct": _d("0.09"),
            "cogs": _d("76000"),
            "gm": _d("28000"),
            "gm_pct": _d("0.27"),
            "wos": _d("6"),
        },
        {
            "item_number": _d("1002"),
            "category": "Outdoor",
            "description": "Weatherproof tent",
            "cost": _d("38000"),
            "pct": _d("0.08"),
            "cogs": _d("69000"),
            "gm": _d("31000"),
            "gm_pct": _d("0.31"),
            "wos": _d("7"),
        },
        {
            "item_number": _d("1003"),
            "category": "Electronics",
            "description": "Portable speaker",
            "cost": _d("32000"),
            "pct": _d("0.07"),
            "cogs": _d("61000"),
            "gm": _d("25000"),
            "gm_pct": _d("0.29"),
            "wos": _d("5"),
        },
    ]
    for item in items:
        HistoricalTop20SKUsRow.objects.create(
            borrower=borrower,
            division="All",
            as_of_date=as_of,
            item_number=item["item_number"],
            category=item["category"],
            description=item["description"],
            cost=item["cost"],
            pct_of_total=item["pct"],
            cogs=item["cogs"],
            gm=item["gm"],
            gm_pct=item["gm_pct"],
            wos=item["wos"],
        )


def bootstrap_default_borrower_data(borrower: Borrower) -> None:
    """
    Populate a lightweight finished-goods snapshot so freshly created borrowers
    show meaningful data without running an import.
    """
    if not borrower or CollateralOverviewRow.objects.filter(borrower=borrower).exists():
        return

    as_of = timezone.localdate()
    _ensure_collateral_overview(borrower)
    _ensure_fg_metrics(borrower, as_of)
    _ensure_ineligible_detail(borrower, as_of)
    _ensure_inline_category_rows(borrower, as_of)
    _ensure_inline_excess_rows(borrower, as_of)
    _ensure_sales_trend(borrower, as_of)
    _ensure_top_skus(borrower, as_of)
