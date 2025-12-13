from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

import pandas as pd
import math
from decimal import Decimal
import re

from management.models import (
    Company,
    Borrower,
    SpecificIndividual,
    BorrowerReport,

    BorrowerOverviewRow,
    CollateralOverviewRow,
    MachineryEquipmentRow,
    AgingCompositionRow,
    ARMetricsRow,
    Top20ByTotalARRow,
    Top20ByPastDueRow,
    IneligibleTrendRow,
    IneligibleOverviewRow,
    ConcentrationADODSORow,

    FGInventoryMetricsRow,
    FGIneligibleDetailRow,
    FGCompositionRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    SalesGMTrendRow,
    HistoricalTop20SKUsRow,

    RMInventoryMetricsRow,
    RMIneligibleOverviewRow,
    RMCategoryHistoryRow,
    RMTop20HistoryRow,

    WIPInventoryMetricsRow,
    WIPIneligibleOverviewRow,
    WIPCategoryHistoryRow,
    WIPTop20HistoryRow,
    WIPRecoveryRow,

    RawMaterialRecoveryRow,
    FGGrossRecoveryHistoryRow,

    NOLVTableRow,
    RiskSubfactorsRow,
    CompositeIndexRow,

    ForecastRow,
    AvailabilityForecastRow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,

    CollateralLimitsRow,
    IneligiblesRow,
)



def is_nan(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def to_date(v):
    if is_nan(v):
        return None
    # pandas Timestamp -> date
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def to_decimal(v):
    if is_nan(v):
        return None
    try:
        # avoid float scientific noise
        return Decimal(str(v))
    except Exception:
        return None


def to_int(v):
    if is_nan(v):
        return None
    try:
        return int(v)
    except Exception:
        return None


def normalize_header(h: str) -> str:
    h = str(h).strip()

    # special cases first
    special = {
        "AsOfDate": "as_of_date",
        "PctOfTotal": "pct_of_total",
        "PctPastDue": "pct_past_due",
        "CurrentAmt": "current_amt",
        "PastDueAmt": "past_due_amt",
        "ActualForecast": "actual_forecast",
        "GrossMarginPct": "gross_margin_pct",
        "GrossMarginDollars": "gross_margin_dollars",
        "TTM_Sales": "ttm_sales",
        "TTM_Sales_Prior": "ttm_sales_prior",
        "Collateral Type": "collateral_type",
        "Collateral Sub-Type": "collateral_sub_type",
        "$ Limit": "usd_limit",
        "% Limit": "pct_limit",
        "FG_$": "fg_usd",
        "FG_%Cost": "fg_pct_cost",
        "RM_$": "rm_usd",
        "RM_%Cost": "rm_pct_cost",
        "WIP_$": "wip_usd",
        "WIP_%Cost": "wip_pct_cost",
        "Total_$": "total_usd",
        "Total_%Cost": "total_pct_cost",
    }
    if h in special:
        return special[h]

    # CamelCase -> snake
    h2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", h)

    # symbols
    h2 = h2.replace("%", " pct ")
    h2 = h2.replace("$", " usd ")
    h2 = h2.replace("-", "_")
    h2 = h2.replace("/", "_")
    h2 = h2.replace("+", "_plus")

    # spaces -> underscore
    h2 = re.sub(r"\s+", "_", h2.strip())
    h2 = re.sub(r"_+", "_", h2).strip("_")
    h2 = h2.lower()

    # columns like 0_30, 91_plus => col_0_30, col_91_plus
    if re.match(r"^\d", h2):
        h2 = f"col_{h2}"

    return h2


def read_df(xlsx_path, sheet_name):
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    # drop fully empty rows
    df = df.dropna(how="all")
    # normalize headers
    df.columns = [normalize_header(c) for c in df.columns]
    return df


def import_sheet_rows(model_cls, df, report):
    """
    Generic importer:
    - Only sets fields that exist on model
    - Converts types for Date/Decimal/Int where needed
    """
    model_fields = {f.name: f for f in model_cls._meta.fields}
    allowed = set(model_fields.keys()) - {"id", "created_at", "updated_at", "report"}

    objs = []
    for _, row in df.iterrows():
        data = {"report": report}

        for k in allowed:
            if k in df.columns:
                val = row.get(k)

                field = model_fields[k]
                internal = field.get_internal_type()

                if internal in ("DateField",):
                    data[k] = to_date(val)
                elif internal in ("DecimalField",):
                    data[k] = to_decimal(val)
                elif internal in ("IntegerField", "BigIntegerField"):
                    data[k] = to_int(val)
                else:
                    # CharField/TextField/EmailField etc
                    data[k] = None if is_nan(val) else val

        # skip rows where everything (except report) is empty
        non_empty = any(v not in (None, "") for kk, v in data.items() if kk != "report")
        if non_empty:
            objs.append(model_cls(**data))

    if objs:
        model_cls.objects.bulk_create(objs, batch_size=1000)


class Command(BaseCommand):
    help = "Import CORA multi-sheet XLSX into Postgres using BorrowerReport + *Row models"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to XLSX file")
        parser.add_argument("--source-file", default="", help="Original filename (optional)")
        parser.add_argument("--report-date", default="", help="YYYY-MM-DD (optional)")

    @transaction.atomic
    def handle(self, *args, **opts):
        xlsx_path = opts["file"]
        source_file = opts["source_file"] or xlsx_path.split("/")[-1]

        # ---------------------------
        # 1) Borrower Overview (special format)
        # ---------------------------
        bo = pd.read_excel(xlsx_path, sheet_name="Borrower Overview", header=None).dropna(how="all")
        # row 1 = headers, row 2 = values (based on your file format)
        headers = [str(x).strip() for x in bo.iloc[1].tolist()]
        values = bo.iloc[2].tolist()
        overview = dict(zip(headers, values))

        company_id = to_int(overview.get("Company ID"))
        if not company_id:
            raise Exception("Borrower Overview sheet missing Company ID")

        company, _ = Company.objects.get_or_create(
            company_id=company_id,
            defaults={
                "company": overview.get("Company"),
                "industry": overview.get("Industry"),
                "primary_naics": to_int(overview.get("Primary NAICS")),
                "website": overview.get("Website"),
            },
        )

        borrower, _ = Borrower.objects.get_or_create(
            company=company,
            defaults={
                "primary_contact": overview.get("Primary Contact"),
                "primary_contact_phone": overview.get("Primary Contact Phone"),
                "primary_contact_email": overview.get("Primary Contact Email"),
                "update_interval": overview.get("Update Interval"),
                "current_update": to_date(overview.get("Current Update")),
                "previous_update": to_date(overview.get("Previous Update")),
                "next_update": to_date(overview.get("Next Update")),
                "lender": overview.get("Lender"),
                "lender_id": to_int(overview.get("Lender ID")),
            },
        )

        # optional: Specific Individual from Borrower Overview
        si_name = overview.get("Specific Individual")
        si_id = overview.get("Specific ID")
        if si_name or si_id:
            SpecificIndividual.objects.get_or_create(
                borrower=borrower,
                specific_individual=str(si_name) if si_name else None,
                specific_id=to_int(si_id),
            )

        # report_date preference: CLI -> Current Update -> today
        report_date = opts["report_date"]
        report_date = pd.to_datetime(report_date).date() if report_date else (to_date(overview.get("Current Update")) or now().date())

        report = BorrowerReport.objects.create(
            borrower=borrower,
            source_file=source_file,
            report_date=report_date,
        )

        # also store Borrower Overview into borrower_overview table
        bo_df = pd.read_excel(xlsx_path, sheet_name="Borrower Overview", header=1).dropna(how="all")
        bo_df.columns = [normalize_header(c) for c in bo_df.columns]
        import_sheet_rows(BorrowerOverviewRow, bo_df, report)

        # ---------------------------
        # 2) Map other sheets -> models
        # ---------------------------
        sheet_model_map = {
    "Collateral Overview": CollateralOverviewRow,
    "Machinery & Equipment ": MachineryEquipmentRow,
    "Aging Composition": AgingCompositionRow,
    "AR_Metrics": ARMetricsRow,
    "Top20_By_Total_AR": Top20ByTotalARRow,
    "Top20_By_PastDue": Top20ByPastDueRow,
    "Ineligible_Trend": IneligibleTrendRow,
    "Ineligible_Overview": IneligibleOverviewRow,
    "Concentration_ADO_DSO": ConcentrationADODSORow,

    "FG_Inventory_Metrics": FGInventoryMetricsRow,
    "FG_Ineligible_detail": FGIneligibleDetailRow,
    "FG_Composition": FGCompositionRow,
    "FG_Inline_Category_Analysis": FGInlineCategoryAnalysisRow,
    "Sales_GM_Trend": SalesGMTrendRow,
    "FG_Inline_Excess_By_Category": FGInlineExcessByCategoryRow,
    "Historical_Top_20_SKUs": HistoricalTop20SKUsRow,

    "RM_Inventory_Metrics": RMInventoryMetricsRow,
    "RM_Ineligible_Overview": RMIneligibleOverviewRow,
    "RM_Category_History": RMCategoryHistoryRow,
    "RM_Top20_History": RMTop20HistoryRow,

    "WIP_Inventory_Metrics": WIPInventoryMetricsRow,
    "WIP_Ineligible_Overview": WIPIneligibleOverviewRow,
    "WIP_Category_History": WIPCategoryHistoryRow,
    "WIP_Top20_History": WIPTop20HistoryRow,

    "FG_Gross_Recovery_History": FGGrossRecoveryHistoryRow,
    "WIP_Recovery": WIPRecoveryRow,
    "Raw_Material_Recovery": RawMaterialRecoveryRow,

    "NOLV_Table": NOLVTableRow,
    "Risk_Subfactors": RiskSubfactorsRow,
    "Composite_Index": CompositeIndexRow,

    "Forecast": ForecastRow,
    "Availability Forecast": AvailabilityForecastRow,

    "Current Week Variance": CurrentWeekVarianceRow,
    "Cummulative Variance": CummulativeVarianceRow,

    "Collateral Limits ": CollateralLimitsRow,
    "Ineligibles": IneligiblesRow,
}


        for sheet, model_cls in sheet_model_map.items():
            try:
                df = read_df(xlsx_path, sheet)
            except Exception:
                continue

            if df.empty:
                continue

            import_sheet_rows(model_cls, df, report)

        self.stdout.write(self.style.SUCCESS(f"✅ Imported XLSX into report_id={report.id} for borrower_id={borrower.id}"))
