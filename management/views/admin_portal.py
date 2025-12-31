from datetime import date

from django.core.exceptions import FieldDoesNotExist
from django.core.paginator import Paginator
from django.db import ProgrammingError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import select_template

from management.forms import (
    ARMetricsForm,
    AgingCompositionForm,
    AvailabilityForecastForm,
    BorrowerForm,
    CashForecastForm,
    CashFlowForecastForm,
    CollateralLimitsForm,
    CollateralOverviewForm,
    CompanyForm,
    CompositeIndexForm,
    ConcentrationADODSOForm,
    CurrentWeekVarianceForm,
    CumulativeVarianceForm,
    FGCompositionForm,
    FGIneligibleDetailForm,
    FGInlineCategoryAnalysisForm,
    FGInlineExcessByCategoryForm,
    FGInventoryMetricsForm,
    FGGrossRecoveryHistoryForm,
    ForecastForm,
    IneligiblesForm,
    IneligibleOverviewForm,
    IneligibleTrendForm,
    MachineryEquipmentForm,
    NOLVTableForm,
    RawMaterialRecoveryForm,
    RiskSubfactorsForm,
    RMCategoryHistoryForm,
    RMIneligibleOverviewForm,
    RMInventoryMetricsForm,
    SalesGMTrendForm,
    SnapshotSummaryForm,
    SpecificIndividualForm,
    WIPCategoryHistoryForm,
    WIPIneligibleOverviewForm,
    WIPInventoryMetricsForm,
    WIPRecoveryForm,
    BorrowingBaseReportForm,
    CompleteAnalysisReportForm,
    CashFlowReportForm,
)
from management.models import (
    ARMetricsRow,
    AgingCompositionRow,
    AvailabilityForecastRow,
    Borrower,
    BorrowerReport,
    CashForecastRow,
    CashFlowForecastRow,
    CollateralLimitsRow,
    CollateralOverviewRow,
    Company,
    CompositeIndexRow,
    ConcentrationADODSORow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,
    FGCompositionRow,
    FGIneligibleDetailRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    FGInventoryMetricsRow,
    FGGrossRecoveryHistoryRow,
    ForecastRow,
    IneligiblesRow,
    IneligibleTrendRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    NOLVTableRow,
    RawMaterialRecoveryRow,
    RiskSubfactorsRow,
    RMCategoryHistoryRow,
    RMIneligibleOverviewRow,
    RMInventoryMetricsRow,
    SalesGMTrendRow,
    SnapshotSummaryRow,
    SpecificIndividual,
    WIPCategoryHistoryRow,
    WIPIneligibleOverviewRow,
    WIPInventoryMetricsRow,
    WIPRecoveryRow,
    ReportUpload,
)
from management.views.collateral_dynamic import _other_collateral_context


COMPONENT_REGISTRY = {
    "companies": {
        "title": "Users",
        "template": "admin/components/companies.html",
        "nav_key": "company",
        "description": "Manage user/company accounts connected to borrowers.",
    },
    "borrowers": {
        "title": "Borrowers",
        "template": "admin/components/borrowers.html",
        "nav_key": "borrower",
        "description": "Maintain borrower contacts and update cadence.",
    },
    "specificIndividuals": {
        "title": "Specific Individuals",
        "template": "admin/components/specificIndividuals.html",
        "nav_key": "individual",
        "description": "Track individuals tied to KYC or underwriting tasks.",
    },
    "collateralOverview": {
        "title": "Collateral Overview",
        "template": "admin/components/collateralOverview.html",
        "nav_key": "collateral_overview",
    },
    "snapshotSummaries": {
        "title": "Snapshot Summaries",
        "template": "admin/components/snapshotSummaries.html",
        "nav_key": "snapshot_summaries",
        "description": "Manage borrower snapshot summaries displayed across dashboards.",
    },
    "machineryEquipment": {
        "title": "Machinery & Equipment",
        "template": "admin/components/machineryEquipment.html",
        "nav_key": "machinery_equipment",
    },
    "agingComposition": {
        "title": "Aging Composition",
        "template": "admin/components/agingComposition.html",
        "nav_key": "accounts_aging",
    },
    "arMetrics": {
        "title": "AR Metrics",
        "template": "admin/components/arMetrics.html",
        "nav_key": "accounts_metrics",
    },
    "ineligibleTrend": {
        "title": "Ineligible Trend",
        "template": "admin/components/ineligibleTrend.html",
        "nav_key": "accounts_ineligible_trend",
    },
    "ineligibleOverview": {
        "title": "Ineligible Overview",
        "template": "admin/components/ineligibleOverview.html",
        "nav_key": "accounts_ineligible_overview",
    },
    "concentrationADODSO": {
        "title": "Concentration ADO/DSO",
        "template": "admin/components/concentrationADODSO.html",
        "nav_key": "accounts_concentration",
    },
    "fgInventoryMetrics": {
        "title": "FG Inventory Metrics",
        "template": "admin/components/fgInventoryMetrics.html",
        "nav_key": "fg_inventory",
    },
    "fgIneligibleDetail": {
        "title": "FG Ineligible Detail",
        "template": "admin/components/fgIneligibleDetail.html",
        "nav_key": "fg_ineligible_detail",
    },
    "fgComposition": {
        "title": "FG Composition",
        "template": "admin/components/fgComposition.html",
        "nav_key": "fg_composition",
    },
    "fgInlineCategoryAnalysis": {
        "title": "FG Inline Category Analysis",
        "template": "admin/components/fgInlineCategoryAnalysis.html",
        "nav_key": "fg_inline_category",
    },
    "salesGMTrend": {
        "title": "Sales/GM Trend",
        "template": "admin/components/salesGMTrend.html",
        "nav_key": "sales_gm_trend",
    },
    "fgInlineExcessByCategory": {
        "title": "FG Inline Excess By Category",
        "template": "admin/components/fgInlineExcessByCategory.html",
        "nav_key": "fg_inline_excess",
    },
    "rmInventoryMetrics": {
        "title": "RM Inventory Metrics",
        "template": "admin/components/rmInventoryMetrics.html",
        "nav_key": "rm_inventory",
    },
    "rmIneligibleOverview": {
        "title": "RM Ineligible Overview",
        "template": "admin/components/rmIneligibleOverview.html",
        "nav_key": "rm_ineligible_overview",
    },
    "rmCategoryHistory": {
        "title": "RM Category History",
        "template": "admin/components/rmCategoryHistory.html",
        "nav_key": "rm_category_history",
    },
    "wipInventoryMetrics": {
        "title": "WIP Inventory Metrics",
        "template": "admin/components/wipInventoryMetrics.html",
        "nav_key": "wip_inventory",
    },
    "wipIneligibleOverview": {
        "title": "WIP Ineligible Overview",
        "template": "admin/components/wipIneligibleOverview.html",
        "nav_key": "wip_ineligible_overview",
    },
    "wipCategoryHistory": {
        "title": "WIP Category History",
        "template": "admin/components/wipCategoryHistory.html",
        "nav_key": "wip_category_history",
    },
    "fgGrossRecoveryHistory": {
        "title": "FG Gross Recovery History",
        "template": "admin/components/fgGrossRecoveryHistory.html",
        "nav_key": "fg_recovery_history",
    },
    "wipRecovery": {
        "title": "WIP Recovery",
        "template": "admin/components/wipRecovery.html",
        "nav_key": "wip_recovery",
    },
    "rawMaterialRecovery": {
        "title": "Raw Material Recovery",
        "template": "admin/components/rawMaterialRecovery.html",
        "nav_key": "raw_material_recovery",
    },
    "borrowingBaseReport": {
        "title": "Borrowing Base Report",
        "template": "admin/components/reportUpload.html",
        "nav_key": "reports_borrowing_base",
        "description": "Upload Borrowing Base reports in PDF format.",
    },
    "completeAnalysisReport": {
        "title": "Complete Analysis Report",
        "template": "admin/components/reportUpload.html",
        "nav_key": "reports_complete_analysis",
        "description": "Upload Complete Analysis PDF reports.",
    },
    "cashFlowReport": {
        "title": "Cash Flow Report",
        "template": "admin/components/reportUpload.html",
        "nav_key": "reports_cash_flow",
        "description": "Upload Cash Flow PDF reports.",
    },
    "cashFlow": {
        "title": "13-Week Cash Flow",
        "template": "admin/components/cashFlow.html",
        "nav_key": "liquidation_cash_flow",
    },
    "cashForecast": {
        "title": "Cash Forecast",
        "template": "admin/components/cashForecast.html",
        "nav_key": "cash_forecast",
    },
    "availabilityForecast": {
        "title": "Availability Forecast",
        "template": "admin/components/availabilityForecast.html",
        "nav_key": "availability_forecast",
    },
    "nolvTable": {
        "title": "NOLV Table",
        "template": "admin/components/nolvTable.html",
        "nav_key": "nolv_table",
    },
    "riskSubfactors": {
        "title": "Risk Subfactors",
        "template": "admin/components/riskSubfactors.html",
        "nav_key": "risk_subfactors",
    },
    "compositeIndex": {
        "title": "Composite Index",
        "template": "admin/components/compositeIndex.html",
        "nav_key": "risk_composite_index",
    },
    "forecastAccountsReceivable": {
        "title": "Accounts Receivable Forecast",
        "template": "admin/components/forecastAsset.html",
        "nav_key": "forecast_ar",
        "value_field": "ar",
        "value_label": "Accounts Receivable",
        "value_format": "currency",
    },
    "forecastFinishedGoods": {
        "title": "Finished Goods Forecast",
        "template": "admin/components/forecastAsset.html",
        "nav_key": "forecast_fg",
        "value_field": "finished_goods",
        "value_label": "Finished Goods",
        "value_format": "currency",
    },
    "forecastRawMaterials": {
        "title": "Raw Materials Forecast",
        "template": "admin/components/forecastAsset.html",
        "nav_key": "forecast_rm",
        "value_field": "raw_materials",
        "value_label": "Raw Materials",
        "value_format": "currency",
    },
    "forecastWeeksOfSupply": {
        "title": "Weeks Of Supply Forecast",
        "template": "admin/components/forecastAsset.html",
        "nav_key": "forecast_wos",
        "value_field": "weeks_of_supply",
        "value_label": "Weeks of Supply",
        "value_format": "number",
    },
    "forecastWorkInProcess": {
        "title": "Work-In-Process Forecast",
        "template": "admin/components/forecastAsset.html",
        "nav_key": "forecast_wip",
        "value_field": "work_in_process",
        "value_label": "Work-In-Process",
        "value_format": "currency",
    },
    "forecast": {
        "title": "Forecast",
        "template": "admin/components/forecast.html",
        "nav_key": "forecast",
    },
    "currentWeekVariance": {
        "title": "Current Week Variance",
        "template": "admin/components/currentWeekVariance.html",
        "nav_key": "current_week_variance",
    },
    "cumulativeVariance": {
        "title": "Cumulative Variance",
        "template": "admin/components/cumulativeVariance.html",
        "nav_key": "cumulative_variance",
    },
    "collateralLimits": {
        "title": "Collateral Limits",
        "template": "admin/components/collateralLimits.html",
        "nav_key": "collateral_limits",
    },
    "ineligibles": {
        "title": "Ineligibles",
        "template": "admin/components/ineligibles.html",
        "nav_key": "settings_ineligibles",
    },
}
class ModelComponentHandler:
    page_size = 15

    def __init__(
        self,
        *,
        slug,
        model,
        form_class,
        ordering=None,
        select_related=None,
        filters=None,
        require_borrower=False,
    ):
        self.slug = slug
        self.model = model
        self.form_class = form_class
        self.ordering = ordering or ["-created_at"]
        self.select_related = select_related or []
        self.filters = filters or []
        self.require_borrower = require_borrower

    def build_filters(self, request, queryset):
        filter_defs = []
        for spec in self.filters:
            options = [{"value": "", "label": "All"}]
            values = []
            label_format = spec.get("label_format")
            month_year = spec.get("month_year")

            def format_label(value):
                if label_format and value and hasattr(value, "strftime"):
                    try:
                        return value.strftime(label_format)
                    except (TypeError, ValueError):
                        pass
                return str(value)

            if month_year:
                values = (
                    self.model.objects.order_by()
                    .values_list(spec["field"], flat=True)
                    .distinct()
                )
                month_year_values = set()
                for value in values:
                    if not value:
                        continue
                    try:
                        month_year_values.add((value.year, value.month))
                    except AttributeError:
                        continue
                for year_value, month_value in sorted(month_year_values, reverse=True):
                    label_date = date(year_value, month_value, 1)
                    label = (
                        label_date.strftime(label_format)
                        if label_format
                        else label_date.strftime("%b %Y")
                    )
                    options.append(
                        {
                            "value": f"{year_value:04d}-{month_value:02d}",
                            "label": label,
                        }
                    )
            elif spec.get("queryset"):
                values = list(spec["queryset"])
                for item in values:
                    options.append({"value": str(getattr(item, "pk", "")), "label": format_label(item)})
            elif spec.get("choices"):
                for value, label in spec["choices"]:
                    options.append({"value": value, "label": label})
            else:
                values = (
                    self.model.objects.order_by()
                    .values_list(spec["field"], flat=True)
                    .distinct()
                )
                for value in values:
                    if value is None or value == "":
                        continue
                    options.append({"value": str(value), "label": format_label(value)})
            selected = request.GET.get(spec["param"], "")
            if selected:
                if month_year:
                    try:
                        year_value, month_value = selected.split("-", 1)
                        queryset = queryset.filter(
                            **{
                                f"{spec['field']}__year": int(year_value),
                                f"{spec['field']}__month": int(month_value),
                            }
                        )
                    except (ValueError, TypeError):
                        selected = ""
                else:
                    queryset = queryset.filter(**{spec["field"]: selected})
            filter_defs.append(
                {
                    "param": spec["param"],
                    "label": spec["label"],
                    "options": options,
                    "selected": selected,
                }
            )
        return queryset, filter_defs

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.select_related:
            qs = qs.select_related(*self.select_related)
        return qs.order_by(*self.ordering)

    def apply_global_borrower_filter(self, request, queryset):
        borrower_id = request.GET.get("borrower")
        if not borrower_id:
            return queryset
        if self.model is Borrower:
            return queryset.filter(pk=borrower_id)
        if self.model is Company:
            return queryset.filter(borrowers__id=borrower_id).distinct()
        try:
            self.model._meta.get_field("borrower")
            return queryset.filter(borrower_id=borrower_id)
        except FieldDoesNotExist:
            pass
        try:
            report_field = self.model._meta.get_field("report")
        except FieldDoesNotExist:
            report_field = None
        if report_field and report_field.related_model is BorrowerReport:
            return queryset.filter(report__borrower_id=borrower_id)
        return queryset

    def redirect(self):
        return redirect("admin_component", component_slug=self.slug)

    def handle(self, request):
        create_form = self.form_class()
        edit_form = None
        edit_instance = None
        edit_id = request.GET.get("edit")
        borrower_id = request.GET.get("borrower")
        borrower_selected = bool(borrower_id)
        data_list = []
        db_error = None
        table_ready = True
        page_obj = None
        params = request.GET.copy()
        params.pop("page", None)
        page_query = params.urlencode()
        page_query_prefix = f"{page_query}&" if page_query else ""

        qs = self.get_queryset()
        qs = self.apply_global_borrower_filter(request, qs)
        if self.require_borrower and not borrower_selected:
            qs = qs.none()
        filter_defs = []
        if table_ready:
            try:
                qs, filter_defs = self.build_filters(request, qs)
            except ProgrammingError as exc:
                table_ready = False
                db_error = str(exc)
        if table_ready:
            try:
                paginator = Paginator(qs, self.page_size)
                page_number = request.GET.get("page", 1)
                page_obj = paginator.get_page(page_number)
                data_list = list(page_obj.object_list)
            except ProgrammingError as exc:
                table_ready = False
                db_error = str(exc)

        if table_ready and edit_id:
            edit_instance = get_object_or_404(self.model, pk=edit_id)
            edit_form = self.form_class(instance=edit_instance)

        if table_ready and request.method == "POST":
            action = request.POST.get("_action", "create")
            if action == "delete":
                obj_id = request.POST.get("object_id")
                if obj_id:
                    self.model.objects.filter(pk=obj_id).delete()
                return self.redirect()

            instance = None
            if action == "update":
                obj_id = request.POST.get("object_id")
                instance = get_object_or_404(self.model, pk=obj_id)
            form = self.form_class(request.POST or None, request.FILES or None, instance=instance)
            if form.is_valid():
                form.save()
                return self.redirect()
            if action == "update":
                edit_form = form
                edit_instance = instance
                edit_id = str(instance.pk)
            else:
                create_form = form

        return {
            "list": data_list,
            "form": create_form,
            "edit_form": edit_form,
            "edit_instance": edit_instance,
            "edit_id": edit_id,
            "slug": self.slug,
            "db_error": db_error,
            "filters": filter_defs,
            "page_obj": page_obj,
            "page_query": page_query,
            "page_query_prefix": page_query_prefix,
            "borrower_selected": borrower_selected,
            "borrower_id": borrower_id,
        }


class ReportUploadHandler(ModelComponentHandler):
    def __init__(self, *, report_type, **kwargs):
        super().__init__(**kwargs)
        self.report_type = report_type

    def get_queryset(self):
        return super().get_queryset().filter(report_type=self.report_type)


class MachineryEquipmentHandler(ModelComponentHandler):
    def handle(self, request):
        data = super().handle(request)
        borrower = None
        borrower_id = request.GET.get("borrower")
        if borrower_id:
            borrower = Borrower.objects.filter(pk=borrower_id).select_related("company").first()

        value_context = {
            "rows": [],
            "monitor_cards": [],
            "trend": None,
            "message": "Select a borrower to see value analysis.",
        }
        if borrower:
            collateral_context = _other_collateral_context(borrower, None)
            rows = collateral_context.get("other_collateral_value_analysis_rows") or []
            value_context["rows"] = rows
            value_context["monitor_cards"] = collateral_context.get("other_collateral_value_monitor") or []
            value_context["trend"] = collateral_context.get("other_collateral_value_trend_config")
            value_context["message"] = (
                "No value analysis available for this borrower yet."
                if not rows
                else ""
            )

        data.update(
            {
                "value_analysis": value_context,
                "value_analysis_borrower": borrower,
            }
        )
        return data


HANDLERS = {
    "companies": ModelComponentHandler(
        slug="companies",
        model=Company,
        form_class=CompanyForm,
        ordering=["company"],
    ),
    "borrowers": ModelComponentHandler(
        slug="borrowers",
        model=Borrower,
        form_class=BorrowerForm,
        ordering=["company__company", "primary_contact"],
        select_related=["company"],
    ),
    "specificIndividuals": ModelComponentHandler(
        slug="specificIndividuals",
        model=SpecificIndividual,
        form_class=SpecificIndividualForm,
        ordering=["borrower__company__company", "specific_individual"],
        select_related=["borrower", "borrower__company"],
    ),
    "collateralOverview": ModelComponentHandler(
        slug="collateralOverview",
        model=CollateralOverviewRow,
        form_class=CollateralOverviewForm,
        ordering=["id"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "main_type", "label": "Main Type", "field": "main_type"},
            {"param": "sub_type", "label": "Sub Type", "field": "sub_type"},
        ],
    ),
    "snapshotSummaries": ModelComponentHandler(
        slug="snapshotSummaries",
        model=SnapshotSummaryRow,
        form_class=SnapshotSummaryForm,
        ordering=["borrower__company__company", "borrower__primary_contact", "section"],
        select_related=["borrower", "borrower__company"],
    ),
    "machineryEquipment": MachineryEquipmentHandler(
        slug="machineryEquipment",
        model=MachineryEquipmentRow,
        form_class=MachineryEquipmentForm,
        ordering=["equipment_type"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "equipment_type", "label": "Type", "field": "equipment_type"},
            {"param": "year", "label": "Year", "field": "year"},
            {"param": "condition", "label": "Condition", "field": "condition"},
        ],
    ),
    "agingComposition": ModelComponentHandler(
        slug="agingComposition",
        model=AgingCompositionRow,
        form_class=AgingCompositionForm,
        ordering=["-as_of_date", "division", "bucket"],
    ),
    "arMetrics": ModelComponentHandler(
        slug="arMetrics",
        model=ARMetricsRow,
        form_class=ARMetricsForm,
        ordering=["-as_of_date", "division"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "year", "label": "Year", "field": "as_of_date__year"},
        ],
    ),
    "ineligibleTrend": ModelComponentHandler(
        slug="ineligibleTrend",
        model=IneligibleTrendRow,
        form_class=IneligibleTrendForm,
        ordering=["-date", "division"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "year", "label": "Year", "field": "date__year"},
        ],
    ),
    "ineligibleOverview": ModelComponentHandler(
        slug="ineligibleOverview",
        model=IneligibleOverviewRow,
        form_class=IneligibleOverviewForm,
        ordering=["-date", "division"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
        ],
    ),
    "concentrationADODSO": ModelComponentHandler(
        slug="concentrationADODSO",
        model=ConcentrationADODSORow,
        form_class=ConcentrationADODSOForm,
        ordering=["-as_of_date", "division", "customer"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
        ],
    ),
    "fgInventoryMetrics": ModelComponentHandler(
        slug="fgInventoryMetrics",
        model=FGInventoryMetricsRow,
        form_class=FGInventoryMetricsForm,
        ordering=["-as_of_date", "inventory_type", "division"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "as_of_date", "label": "As Of Date", "field": "as_of_date", "label_format": "%b %Y"},
        ],
    ),
    "fgIneligibleDetail": ModelComponentHandler(
        slug="fgIneligibleDetail",
        model=FGIneligibleDetailRow,
        form_class=FGIneligibleDetailForm,
        ordering=["-date", "inventory_type", "division"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "date", "label": "Date", "field": "date", "label_format": "%b %Y"},
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
        ],
    ),
    "fgComposition": ModelComponentHandler(
        slug="fgComposition",
        model=FGCompositionRow,
        form_class=FGCompositionForm,
        ordering=["-as_of_date", "division"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "as_of_date", "label": "As Of Date", "field": "as_of_date", "label_format": "%b %Y"},
        ],
    ),
    "fgInlineCategoryAnalysis": ModelComponentHandler(
        slug="fgInlineCategoryAnalysis",
        model=FGInlineCategoryAnalysisRow,
        form_class=FGInlineCategoryAnalysisForm,
        ordering=["-as_of_date", "division", "category"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "salesGMTrend": ModelComponentHandler(
        slug="salesGMTrend",
        model=SalesGMTrendRow,
        form_class=SalesGMTrendForm,
        ordering=["-as_of_date", "division"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "year", "label": "Year", "field": "as_of_date__year"},
        ],
    ),
    "fgInlineExcessByCategory": ModelComponentHandler(
        slug="fgInlineExcessByCategory",
        model=FGInlineExcessByCategoryRow,
        form_class=FGInlineExcessByCategoryForm,
        ordering=["-as_of_date", "division", "category"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "category", "label": "Category", "field": "category"},
            {"param": "year", "label": "Year", "field": "as_of_date__year"},
        ],
    ),
    "rmInventoryMetrics": ModelComponentHandler(
        slug="rmInventoryMetrics",
        model=RMInventoryMetricsRow,
        form_class=RMInventoryMetricsForm,
        ordering=["-as_of_date", "inventory_type", "division"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "year", "label": "Year", "field": "as_of_date__year"},
        ],
    ),
    "rmIneligibleOverview": ModelComponentHandler(
        slug="rmIneligibleOverview",
        model=RMIneligibleOverviewRow,
        form_class=RMIneligibleOverviewForm,
        ordering=["-date", "inventory_type", "division"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "year", "label": "Year", "field": "date__year"},
        ],
    ),
    "rmCategoryHistory": ModelComponentHandler(
        slug="rmCategoryHistory",
        model=RMCategoryHistoryRow,
        form_class=RMCategoryHistoryForm,
        ordering=["-date", "inventory_type", "division", "category"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "category", "label": "Category", "field": "category"},
            {"param": "year", "label": "Year", "field": "date__year"},
        ],
    ),
    "wipInventoryMetrics": ModelComponentHandler(
        slug="wipInventoryMetrics",
        model=WIPInventoryMetricsRow,
        form_class=WIPInventoryMetricsForm,
        ordering=["-as_of_date", "inventory_type", "division"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
        ],
    ),
    "wipIneligibleOverview": ModelComponentHandler(
        slug="wipIneligibleOverview",
        model=WIPIneligibleOverviewRow,
        form_class=WIPIneligibleOverviewForm,
        ordering=["-date", "inventory_type", "division"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
        ],
    ),
    "wipCategoryHistory": ModelComponentHandler(
        slug="wipCategoryHistory",
        model=WIPCategoryHistoryRow,
        form_class=WIPCategoryHistoryForm,
        ordering=["-date", "inventory_type", "division", "category"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "category", "label": "Category", "field": "category"},
            {"param": "year", "label": "Year", "field": "date__year"},
        ],
    ),
    "fgGrossRecoveryHistory": ModelComponentHandler(
        slug="fgGrossRecoveryHistory",
        model=FGGrossRecoveryHistoryRow,
        form_class=FGGrossRecoveryHistoryForm,
        ordering=["-as_of_date", "division", "category"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "category", "label": "Category", "field": "category"},
            {"param": "type", "label": "Type", "field": "type"},
            {"param": "year", "label": "Year", "field": "as_of_date__year"},
        ],
    ),
    "wipRecovery": ModelComponentHandler(
        slug="wipRecovery",
        model=WIPRecoveryRow,
        form_class=WIPRecoveryForm,
        ordering=["-date", "division", "category"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "rawMaterialRecovery": ModelComponentHandler(
        slug="rawMaterialRecovery",
        model=RawMaterialRecoveryRow,
        form_class=RawMaterialRecoveryForm,
        ordering=["-date", "division", "category"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "inventory_type", "label": "Inventory Type", "field": "inventory_type"},
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "cashFlow": ModelComponentHandler(
        slug="cashFlow",
        model=CashFlowForecastRow,
        form_class=CashFlowForecastForm,
        ordering=["-date", "category"],
        select_related=["report", "report__borrower", "report__borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "report__borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "report_date",
                "label": "Report Date",
                "field": "report__report_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "entry_date",
                "label": "Entry Date",
                "field": "date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "cashForecast": ModelComponentHandler(
        slug="cashForecast",
        model=CashForecastRow,
        form_class=CashForecastForm,
        ordering=["-date", "category"],
        select_related=["borrower", "borrower__company", "report"],
        require_borrower=True,
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "entry_date",
                "label": "Entry Date",
                "field": "date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "availabilityForecast": ModelComponentHandler(
        slug="availabilityForecast",
        model=AvailabilityForecastRow,
        form_class=AvailabilityForecastForm,
        ordering=["-date", "category"],
        select_related=["borrower", "borrower__company"],
        require_borrower=True,
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "entry_date",
                "label": "Entry Date",
                "field": "date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "nolvTable": ModelComponentHandler(
        slug="nolvTable",
        model=NOLVTableRow,
        form_class=NOLVTableForm,
        ordering=["-date", "division", "line_item"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
        ],
    ),
    "riskSubfactors": ModelComponentHandler(
        slug="riskSubfactors",
        model=RiskSubfactorsRow,
        form_class=RiskSubfactorsForm,
        ordering=["-date", "main_category", "sub_risk"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "main_category", "label": "Category", "field": "main_category"},
            {"param": "sub_risk", "label": "Sub Risk", "field": "sub_risk"},
            {"param": "high_impact_factor", "label": "High Impact Factor", "field": "high_impact_factor"},
        ],
    ),
    "compositeIndex": ModelComponentHandler(
        slug="compositeIndex",
        model=CompositeIndexRow,
        form_class=CompositeIndexForm,
        ordering=["-date"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "year", "label": "Year", "field": "date__year"},
        ],
    ),
    "forecastAccountsReceivable": ModelComponentHandler(
        slug="forecastAccountsReceivable",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "as_of_date",
                "label": "As Of",
                "field": "as_of_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "period",
                "label": "Period",
                "field": "period",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "actual_forecast", "label": "Actual/Forecast", "field": "actual_forecast"},
        ],
    ),
    "forecastFinishedGoods": ModelComponentHandler(
        slug="forecastFinishedGoods",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "as_of_date",
                "label": "As Of",
                "field": "as_of_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "period",
                "label": "Period",
                "field": "period",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "actual_forecast", "label": "Actual/Forecast", "field": "actual_forecast"},
        ],
    ),
    "forecastRawMaterials": ModelComponentHandler(
        slug="forecastRawMaterials",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "as_of_date",
                "label": "As Of",
                "field": "as_of_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "period",
                "label": "Period",
                "field": "period",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "actual_forecast", "label": "Actual/Forecast", "field": "actual_forecast"},
        ],
    ),
    "forecastWeeksOfSupply": ModelComponentHandler(
        slug="forecastWeeksOfSupply",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "as_of_date",
                "label": "As Of",
                "field": "as_of_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "period",
                "label": "Period",
                "field": "period",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "actual_forecast", "label": "Actual/Forecast", "field": "actual_forecast"},
        ],
    ),
    "forecastWorkInProcess": ModelComponentHandler(
        slug="forecastWorkInProcess",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "as_of_date",
                "label": "As Of",
                "field": "as_of_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "period",
                "label": "Period",
                "field": "period",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "actual_forecast", "label": "Actual/Forecast", "field": "actual_forecast"},
        ],
    ),
    "forecast": ModelComponentHandler(
        slug="forecast",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {
                "param": "as_of_date",
                "label": "As Of",
                "field": "as_of_date",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {
                "param": "period",
                "label": "Period",
                "field": "period",
                "label_format": "%b %Y",
                "month_year": True,
            },
            {"param": "actual_forecast", "label": "Actual/Forecast", "field": "actual_forecast"},
        ],
    ),
    "currentWeekVariance": ModelComponentHandler(
        slug="currentWeekVariance",
        model=CurrentWeekVarianceRow,
        form_class=CurrentWeekVarianceForm,
        ordering=["-date", "category"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "year", "label": "Year", "field": "date__year"},
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "cumulativeVariance": ModelComponentHandler(
        slug="cumulativeVariance",
        model=CummulativeVarianceRow,
        form_class=CumulativeVarianceForm,
        ordering=["-date", "category"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "year", "label": "Year", "field": "date__year"},
            {"param": "category", "label": "Category", "field": "category"},
        ],
    ),
    "collateralLimits": ModelComponentHandler(
        slug="collateralLimits",
        model=CollateralLimitsRow,
        form_class=CollateralLimitsForm,
        ordering=["division", "collateral_type", "collateral_sub_type"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "collateral_type", "label": "Collateral Type", "field": "collateral_type"},
            {"param": "collateral_sub_type", "label": "Collateral Sub-Type", "field": "collateral_sub_type"},
        ],
    ),
    "ineligibles": ModelComponentHandler(
        slug="ineligibles",
        model=IneligiblesRow,
        form_class=IneligiblesForm,
        ordering=["division", "collateral_type", "collateral_sub_type"],
        select_related=["borrower", "borrower__company"],
        filters=[
            {
                "param": "borrower",
                "label": "Borrower",
                "field": "borrower__id",
                "queryset": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
            },
            {"param": "division", "label": "Division", "field": "division"},
            {"param": "collateral_type", "label": "Collateral Type", "field": "collateral_type"},
            {"param": "collateral_sub_type", "label": "Collateral Sub-Type", "field": "collateral_sub_type"},
        ],
    ),
    "borrowingBaseReport": ReportUploadHandler(
        slug="borrowingBaseReport",
        model=ReportUpload,
        form_class=BorrowingBaseReportForm,
        ordering=["-created_at"],
        report_type=ReportUpload.BORROWING_BASE,
    ),
    "completeAnalysisReport": ReportUploadHandler(
        slug="completeAnalysisReport",
        model=ReportUpload,
        form_class=CompleteAnalysisReportForm,
        ordering=["-created_at"],
        report_type=ReportUpload.COMPLETE_ANALYSIS,
    ),
    "cashFlowReport": ReportUploadHandler(
        slug="cashFlowReport",
        model=ReportUpload,
        form_class=CashFlowReportForm,
        ordering=["-created_at"],
        report_type=ReportUpload.CASH_FLOW,
    ),
}


def _resolve_component(component_slug: str):
    meta = COMPONENT_REGISTRY.get(component_slug, {}).copy()
    if not meta:
        meta = {
            "title": component_slug.replace("_", " ").title(),
            "template": f"admin/components/{component_slug}.html",
            "nav_key": "company",
            "description": "",
        }
    meta["slug"] = component_slug
    template_name = meta.get("template") or f"admin/components/{component_slug}.html"
    try:
        select_template([template_name])
    except TemplateDoesNotExist:
        template_name = "admin/components/_missing.html"
    meta["template"] = template_name
    return meta


def admin_component_view(request, component_slug: str):
    component_meta = _resolve_component(component_slug)
    handler = HANDLERS.get(component_slug)
    component_data = {}
    has_borrowers = Borrower.objects.exists()
    if handler:
        handler_data = handler.handle(request)
        if isinstance(handler_data, HttpResponse):
            return handler_data
        component_data = handler_data or {}
    context = {
        "component_meta": component_meta,
        "active_nav": component_meta.get("nav_key", "company"),
        "component_data": component_data,
        "borrower_options": Borrower.objects.select_related("company").order_by("company__company", "primary_contact"),
        "has_borrowers": has_borrowers,
    }
    return render(request, "admin/component_base.html", context)


def admin_dashboard_view(request):
    return admin_component_view(request, component_slug="companies")


def admin_company_view(request):
    return admin_component_view(request, component_slug="companies")
