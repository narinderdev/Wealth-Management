from collections import defaultdict
import datetime as dt
import math
import re
from decimal import Decimal

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

from management.models import (
    Company,
    Borrower,
    SpecificIndividual,
    BorrowerReport,

    BorrowerOverviewRow,
    CollateralOverviewRow,
    MachineryEquipmentRow,
    ValueTrendRow,
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
    CashFlowForecastRow,
    CashForecastRow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,

    CollateralLimitsRow,
    IneligiblesRow,
)



BLANK_STRINGS = {"", "-", "nan", "none"}


def is_nan(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def is_blank(v):
    if is_nan(v):
        return True
    if isinstance(v, str):
        s = v.strip().lower()
        if s in BLANK_STRINGS:
            return True
        if s in {"\u2013", "\u2014"}:
            return True
    return False


def normalize_header_value(value) -> str:
    if is_blank(value):
        return ""
    s = str(value).replace("\n", " ").replace("\r", " ")
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def to_date(v):
    if is_blank(v):
        return None
    if isinstance(v, (dt.date, dt.datetime, pd.Timestamp)):
        return v.date() if hasattr(v, "date") else v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 <= v <= 60000:
            try:
                return pd.to_datetime(v, unit="D", origin="1899-12-30").date()
            except Exception:
                return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        dayfirst = False
        if "/" in s:
            parts = s.split("/")
            if parts and parts[0].isdigit():
                dayfirst = int(parts[0]) > 12
        dt_val = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)
        return None if pd.isna(dt_val) else dt_val.date()
    try:
        dt_val = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(dt_val) else dt_val.date()
    except Exception:
        return None


def to_decimal(v):
    if is_blank(v):
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return Decimal(str(v))
        except Exception:
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s or s.lower() in BLANK_STRINGS:
            return None
        is_negative = s.startswith("(") and s.endswith(")")
        if is_negative:
            s = s[1:-1].strip()
        s = s.replace(",", "")
        pct = s.endswith("%")
        if pct:
            s = s[:-1].strip()
        try:
            dec = Decimal(s)
        except Exception:
            return None
        if is_negative:
            dec = -dec
        if pct:
            dec = dec / Decimal("100")
        return dec
    try:
        return Decimal(str(v))
    except Exception:
        return None


def to_int(v):
    if is_blank(v):
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        try:
            return int(v)
        except Exception:
            return None
    if isinstance(v, str):
        dec = to_decimal(v)
        if dec is None:
            return None
        try:
            return int(dec)
        except Exception:
            return None
    try:
        return int(v)
    except Exception:
        return None


def normalize_header(h: str) -> str:
    h = normalize_header_value(h)

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
    h2 = h2.replace("(", " ").replace(")", " ")

    # spaces -> underscore
    h2 = re.sub(r"\s+", "_", h2.strip())
    h2 = re.sub(r"_+", "_", h2).strip("_")
    h2 = h2.lower()

    # columns like 0_30, 91_plus => col_0_30, col_91_plus
    if re.match(r"^\d", h2):
        h2 = f"col_{h2}"

    return h2


GENERIC_HEADER_TOKENS = {
    "date",
    "category",
    "division",
    "customer",
    "total",
    "period",
    "week",
    "projected",
    "actual",
    "variance",
}
GROUP_PREFIXES = ("forecast", "actual", "budget")


def get_model_fields(model_cls):
    fields = {
        f.name
        for f in model_cls._meta.fields
        if f.name not in {"id", "created_at", "updated_at"}
    }
    return fields


def expected_headers_for_model(model_cls):
    expected = set(GENERIC_HEADER_TOKENS)
    for name in get_model_fields(model_cls):
        if name in {"report", "borrower"}:
            continue
        expected.add(name)
    return expected


def normalize_for_match(value, expected):
    token = normalize_header(value)
    if token in expected:
        return token
    for prefix in GROUP_PREFIXES:
        if token.startswith(prefix + "_"):
            candidate = token[len(prefix) + 1 :]
            if candidate in expected:
                return candidate
    return token


def row_score(row, expected):
    cells = [c for c in row if not is_blank(c)]
    if not cells:
        return -1
    string_cells = [c for c in cells if isinstance(c, str)]
    if not string_cells:
        return -1
    normalized = [normalize_for_match(c, expected) for c in string_cells]
    unique_ratio = len(set(normalized)) / max(len(normalized), 1)
    matches = sum(1 for c in normalized if c in expected)
    score = matches * 3 + len(string_cells) + unique_ratio * 2
    if matches == 0 and unique_ratio < 0.4:
        score -= 5
    return score


def is_group_row(row, expected):
    cells = [c for c in row if not is_blank(c)]
    string_cells = [c for c in cells if isinstance(c, str)]
    if not string_cells:
        return False
    normalized = [normalize_for_match(c, expected) for c in string_cells]
    unique_ratio = len(set(normalized)) / max(len(normalized), 1)
    matches = sum(1 for c in normalized if c in expected)
    return matches == 0 and unique_ratio < 0.5


def make_unique_headers(headers):
    counts = defaultdict(int)
    result = []
    for h in headers:
        base = h or "unnamed"
        counts[base] += 1
        if counts[base] == 1:
            result.append(base)
        else:
            result.append(f"{base}_{counts[base]}")
    return result


def combine_header_rows(group_row, header_row):
    group = [normalize_header_value(c) for c in group_row]
    header = [normalize_header_value(c) for c in header_row]

    ffilled = []
    last = ""
    for c in group:
        if c:
            last = c
        ffilled.append(last)

    base_norm = [normalize_header(c) for c in header]
    dupes = {x for x in base_norm if x and base_norm.count(x) > 1}

    combined = []
    for idx, h in enumerate(header):
        g = ffilled[idx] if idx < len(ffilled) else ""
        if not h and g:
            combined.append(g)
        elif h and g and normalize_header(h) in dupes:
            combined.append(f"{g} {h}")
        else:
            combined.append(h or g)
    return combined


def apply_header_aliases(columns, model_fields):
    used = set()
    renamed = {}
    for col in columns:
        candidate = col
        if candidate not in model_fields:
            for prefix in GROUP_PREFIXES:
                if candidate.startswith(prefix + "_"):
                    stripped = candidate[len(prefix) + 1 :]
                    if stripped in model_fields and stripped not in used:
                        candidate = stripped
                        break
        if candidate in model_fields and candidate not in used:
            renamed[col] = candidate
            used.add(candidate)
    return renamed


def read_sheet_df(xlsx_path, sheet_name, model_cls, header_hint=None):
    raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None, dtype=object)
    expected = expected_headers_for_model(model_cls)
    max_scan = min(12, len(raw))

    header_idx = None
    if header_hint is not None and header_hint < len(raw):
        header_idx = header_hint
    else:
        scored = []
        for idx in range(max_scan):
            score = row_score(raw.iloc[idx].tolist(), expected)
            scored.append((score, idx))
        scored.sort(reverse=True)
        header_idx = scored[0][1] if scored and scored[0][0] >= 0 else 0

    header_rows = [header_idx]
    group_idx = header_idx - 1
    if group_idx >= 0 and is_group_row(raw.iloc[group_idx].tolist(), expected):
        header_rows = [group_idx, header_idx]

    if len(header_rows) == 2:
        headers_raw = combine_header_rows(
            raw.iloc[header_rows[0]].tolist(),
            raw.iloc[header_rows[1]].tolist(),
        )
    else:
        headers_raw = raw.iloc[header_rows[0]].tolist()

    headers = [normalize_header(c) for c in headers_raw]
    headers = make_unique_headers(headers)

    data_start = max(header_rows) + 1
    while data_start < len(raw) and all(is_blank(v) for v in raw.iloc[data_start].tolist()):
        data_start += 1

    rows = []
    empty_streak = 0
    for idx in range(data_start, len(raw)):
        row = raw.iloc[idx].tolist()
        if all(is_blank(v) for v in row):
            empty_streak += 1
            if empty_streak >= 20:
                break
            continue
        empty_streak = 0
        rows.append(row)

    df = pd.DataFrame(rows, columns=headers)
    df = df.dropna(axis=1, how="all")

    model_fields = get_model_fields(model_cls)
    rename_map = apply_header_aliases(df.columns, model_fields)
    if rename_map:
        df = df.rename(columns=rename_map)

    return df, {
        "header_rows": [r + 1 for r in header_rows],
        "data_start_row": data_start + 1 if data_start < len(raw) else None,
        "columns": list(df.columns),
    }


def import_sheet_rows(model_cls, df, report, borrower=None, debug=False, debug_limit=10):
    """
    Generic importer:
    - Only sets fields that exist on model
    - Converts types for Date/Decimal/Int where needed
    """
    model_fields = {f.name: f for f in model_cls._meta.fields}
    allowed = set(model_fields.keys()) - {"id", "created_at", "updated_at", "report"}
    has_report_field = "report" in model_fields

    required_fields = []
    for field in model_cls._meta.fields:
        if field.name in {"id", "created_at", "updated_at", "report", "borrower"}:
            continue
        if not field.null and not field.blank and not field.auto_created:
            required_fields.append(field.name)

    missing_required_columns = [
        f for f in required_fields if f not in df.columns
    ]
    if missing_required_columns:
        return 0, len(df), {"missing_required_columns": len(df)}, []

    objs = []
    skipped = 0
    reasons = defaultdict(int)
    debug_messages = []

    for row_idx, row in df.iterrows():
        data = {}
        row_errors = []
        if has_report_field:
            data["report"] = report
        if borrower and "borrower" in allowed:
            data["borrower"] = borrower

        for k in allowed:
            if k not in df.columns:
                continue
            val = row.get(k)
            field = model_fields[k]
            internal = field.get_internal_type()

            if internal == "DateField":
                parsed = to_date(val)
            elif internal == "DecimalField":
                parsed = to_decimal(val)
            elif internal in ("IntegerField", "BigIntegerField"):
                parsed = to_int(val)
            else:
                parsed = None if is_blank(val) else val

            if parsed is None and not is_blank(val):
                row_errors.append(f"{k}:parse_error")
            data[k] = parsed

        missing_required = [
            f for f in required_fields if data.get(f) in (None, "")
        ]
        if missing_required:
            skipped += 1
            reasons["missing_required_fields"] += 1
            if debug and len(debug_messages) < debug_limit:
                debug_messages.append(
                    f"Row {row_idx + 1}: missing required {missing_required}"
                )
            continue

        non_empty = any(
            v not in (None, "")
            for kk, v in data.items()
            if not (has_report_field and kk == "report")
        )
        if not non_empty:
            skipped += 1
            reasons["empty_rows"] += 1
            continue

        if row_errors and debug and len(debug_messages) < debug_limit:
            debug_messages.append(f"Row {row_idx + 1}: {', '.join(row_errors)}")

        objs.append(model_cls(**data))

    if objs:
        model_cls.objects.bulk_create(objs, batch_size=1000)

    return len(objs), skipped, reasons, debug_messages


def _clear_imported_data(borrower, company_id, model_classes, stdout=None):
    def log(message):
        if stdout:
            stdout.write(message)

    if borrower:
        BorrowerReport.objects.filter(borrower=borrower).delete()
        log("Cleared borrower reports.")

    if company_id:
        BorrowerOverviewRow.objects.filter(company_id=company_id).delete()
        log("Cleared borrower overview rows.")

    for model_cls in model_classes:
        if model_cls in (BorrowerOverviewRow, BorrowerReport):
            continue
        field_names = {f.name for f in model_cls._meta.fields}
        if "borrower" in field_names and borrower:
            model_cls.objects.filter(borrower=borrower).delete()
            log(f"Cleared {model_cls.__name__}.")


def run_cora_import(
    xlsx_path,
    source_file=None,
    report_date=None,
    debug=False,
    clear=False,
    stdout=None,
):
    source_file = source_file or xlsx_path.split("/")[-1]
    summary = []
    errors = []

    def log(message):
        if stdout:
            stdout.write(message)

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

    if clear:
        _clear_imported_data(
            borrower,
            company_id,
            [
                CollateralOverviewRow,
                MachineryEquipmentRow,
                ValueTrendRow,
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
                SalesGMTrendRow,
                FGInlineExcessByCategoryRow,
                HistoricalTop20SKUsRow,
                RMInventoryMetricsRow,
                RMIneligibleOverviewRow,
                RMCategoryHistoryRow,
                RMTop20HistoryRow,
                WIPInventoryMetricsRow,
                WIPIneligibleOverviewRow,
                WIPCategoryHistoryRow,
                WIPTop20HistoryRow,
                FGGrossRecoveryHistoryRow,
                WIPRecoveryRow,
                RawMaterialRecoveryRow,
                NOLVTableRow,
                RiskSubfactorsRow,
                CompositeIndexRow,
                ForecastRow,
                AvailabilityForecastRow,
                CashFlowForecastRow,
                CashForecastRow,
                CurrentWeekVarianceRow,
                CummulativeVarianceRow,
                CollateralLimitsRow,
                IneligiblesRow,
            ],
            stdout=stdout,
        )

    # optional: Specific Individual from Borrower Overview
    si_name = overview.get("Specific Individual")
    si_id = overview.get("Specific ID")
    if si_name or si_id:
        individual, _ = SpecificIndividual.objects.get_or_create(
            borrower=borrower,
            specific_individual=str(si_name) if si_name else None,
            specific_id=to_int(si_id),
        )
        if not borrower.primary_specific_individual_id:
            borrower.primary_specific_individual = individual
            borrower.save(update_fields=["primary_specific_individual"])

    # report_date preference: CLI -> Current Update -> today
    report_date = report_date or ""
    report_date = pd.to_datetime(report_date).date() if report_date else (to_date(overview.get("Current Update")) or now().date())

    report = BorrowerReport.objects.create(
        borrower=borrower,
        source_file=source_file,
        report_date=report_date,
    )

    # also store Borrower Overview into borrower_overview table
    bo_df = pd.read_excel(xlsx_path, sheet_name="Borrower Overview", header=1).dropna(how="all")
    bo_df.columns = [normalize_header(c) for c in bo_df.columns]
    import_sheet_rows(BorrowerOverviewRow, bo_df, report, borrower=borrower, debug=debug)

    # ---------------------------
    # 2) Map other sheets -> models
    # ---------------------------
    sheet_model_map = {
        "Collateral Overview": CollateralOverviewRow,
        "Machinery & Equipment ": MachineryEquipmentRow,
        "Value Trend": ValueTrendRow,
        "Value_Trend": ValueTrendRow,
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
        "Cash Flow Forecast": CashFlowForecastRow,
        "Cash Forecast": CashForecastRow,

        "Current Week Variance": CurrentWeekVarianceRow,
        "Cummulative Variance": CummulativeVarianceRow,

        "Collateral Limits ": CollateralLimitsRow,
        "Ineligibles": IneligiblesRow,
    }

    header_hints = {
        "Cash Flow Forecast": 1,
        "Cash Forecast": 1,
        "Availability Forecast": 1,
    }

    workbook = pd.ExcelFile(xlsx_path)
    for sheet in workbook.sheet_names:
        if sheet == "Borrower Overview":
            continue
        if sheet not in sheet_model_map:
            if ">>>" in sheet:
                if debug:
                    log(f"Skipping section marker sheet: {sheet}")
            else:
                log(f"Skipping unmapped sheet: {sheet}")
            continue

    for sheet, model_cls in sheet_model_map.items():
        if sheet not in workbook.sheet_names:
            summary.append(
                {
                    "sheet": sheet,
                    "model": model_cls.__name__,
                    "imported": 0,
                    "skipped": 0,
                    "header_rows": None,
                    "data_start": None,
                    "status": "missing",
                    "message": "Missing sheet in workbook",
                }
            )
            continue
        try:
            df, meta = read_sheet_df(
                xlsx_path,
                sheet,
                model_cls,
                header_hint=header_hints.get(sheet),
            )
        except Exception as exc:
            message = f"{exc}"
            errors.append({"sheet": sheet, "error": message})
            summary.append(
                {
                    "sheet": sheet,
                    "model": model_cls.__name__,
                    "imported": 0,
                    "skipped": 0,
                    "header_rows": None,
                    "data_start": None,
                    "status": "failed",
                    "message": message,
                }
            )
            continue

        if df.empty:
            summary.append(
                {
                    "sheet": sheet,
                    "model": model_cls.__name__,
                    "imported": 0,
                    "skipped": 0,
                    "header_rows": meta.get("header_rows"),
                    "data_start": meta.get("data_start_row"),
                    "status": "empty",
                    "message": "No data rows detected",
                }
            )
            continue

        if debug:
            log(f"{sheet}: detected columns {meta.get('columns')}")
            model_fields = sorted(get_model_fields(model_cls))
            used_columns = sorted(
                c for c in meta.get("columns", []) if c in model_fields
            )
            log(f"{sheet}: used columns {used_columns}")

        imported, skipped, reasons, debug_msgs = import_sheet_rows(
            model_cls,
            df,
            report,
            borrower=borrower,
            debug=debug,
        )

        if debug_msgs:
            for msg in debug_msgs:
                log(f"{sheet}: {msg}")

        if reasons and skipped:
            log(f"{sheet}: skipped reasons {dict(reasons)}")

        summary.append(
            {
                "sheet": sheet,
                "model": model_cls.__name__,
                "imported": imported,
                "skipped": skipped,
                "header_rows": meta.get("header_rows"),
                "data_start": meta.get("data_start_row"),
                "status": "ok",
                "message": "",
            }
        )

    if summary:
        log("Import summary:")
        for row in summary:
            log(
                f"{row['sheet']} | {row['model']} | imported={row['imported']} "
                f"| skipped={row['skipped']} | header_row={row['header_rows']} "
                f"| data_start={row['data_start']}"
            )

    total_imported = sum(row.get("imported", 0) for row in summary)
    total_skipped = sum(row.get("skipped", 0) for row in summary)
    failed_sheets = [row for row in summary if row.get("status") == "failed"]
    warning_sheets = [
        row
        for row in summary
        if row.get("status") in {"missing", "empty"}
    ]
    if failed_sheets:
        status = "failed" if total_imported == 0 else "partial"
    elif warning_sheets:
        status = "partial" if total_imported > 0 else "failed"
    else:
        status = "success"

    return {
        "report_id": report.id,
        "borrower_id": borrower.id if borrower else None,
        "summary": summary,
        "errors": errors,
        "status": status,
        "total_imported": total_imported,
        "total_skipped": total_skipped,
    }


class Command(BaseCommand):
    help = "Import CORA multi-sheet XLSX into Postgres using BorrowerReport + *Row models"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to XLSX file")
        parser.add_argument("--source-file", default="", help="Original filename (optional)")
        parser.add_argument("--report-date", default="", help="YYYY-MM-DD (optional)")
        parser.add_argument("--debug", action="store_true", help="Verbose import logging")
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing imported data for this borrower before import",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        xlsx_path = opts["file"]
        result = run_cora_import(
            xlsx_path,
            source_file=opts.get("source_file") or xlsx_path.split("/")[-1],
            report_date=opts.get("report_date") or "",
            debug=opts.get("debug", False),
            clear=opts.get("clear", False),
            stdout=self.stdout,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Imported XLSX into report_id={result.get('report_id')} "
                f"for borrower_id={result.get('borrower_id')}"
            )
        )
