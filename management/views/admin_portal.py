from django.db import ProgrammingError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import select_template

from management.forms import (
    ARMetricsForm,
    AgingCompositionForm,
    BorrowerForm,
    CollateralOverviewForm,
    SnapshotSummaryForm,
    CompanyForm,
    ConcentrationADODSOForm,
    FGCompositionForm,
    FGIneligibleDetailForm,
    FGInlineCategoryAnalysisForm,
    FGInlineExcessByCategoryForm,
    FGInventoryMetricsForm,
    FGGrossRecoveryHistoryForm,
    ForecastForm,
    CurrentWeekVarianceForm,
    CumulativeVarianceForm,
    CollateralLimitsForm,
    IneligiblesForm,
    WIPRecoveryForm,
    RawMaterialRecoveryForm,
    NOLVTableForm,
    RiskSubfactorsForm,
    CompositeIndexForm,
    RMCategoryHistoryForm,
    RMIneligibleOverviewForm,
    RMInventoryMetricsForm,
    IneligibleOverviewForm,
    IneligibleTrendForm,
    MachineryEquipmentForm,
    WIPCategoryHistoryForm,
    WIPIneligibleOverviewForm,
    WIPInventoryMetricsForm,
    SalesGMTrendForm,
    SpecificIndividualForm,
)
from management.models import (
    ARMetricsRow,
    AgingCompositionRow,
    Borrower,
    CollateralOverviewRow,
    SnapshotSummaryRow,
    Company,
    ConcentrationADODSORow,
    FGCompositionRow,
    FGIneligibleDetailRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    FGInventoryMetricsRow,
    FGGrossRecoveryHistoryRow,
    ForecastRow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,
    CollateralLimitsRow,
    IneligiblesRow,
    WIPRecoveryRow,
    RawMaterialRecoveryRow,
    NOLVTableRow,
    RiskSubfactorsRow,
    CompositeIndexRow,
    RMCategoryHistoryRow,
    RMIneligibleOverviewRow,
    RMInventoryMetricsRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    WIPCategoryHistoryRow,
    WIPIneligibleOverviewRow,
    WIPInventoryMetricsRow,
    SalesGMTrendRow,
    SpecificIndividual,
)


COMPONENT_REGISTRY = {
    "companies": {
        "title": "Companies",
        "template": "admin/components/companies.html",
        "nav_key": "company",
        "description": "Manage companies connected to borrowers.",
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
        "nav_key": "accounts_snapshot_summaries",
        "description": "Manage borrower snapshot summaries displayed across dashboards.",
    },
    "machineryEquipment": {
        "title": "Machinery & Equipment",
        "template": "admin/components/machineryEquipment.html",
        "nav_key": "accounts_machinery",
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
    def __init__(self, *, slug, model, form_class, ordering=None, select_related=None, filters=None):
        self.slug = slug
        self.model = model
        self.form_class = form_class
        self.ordering = ordering or ["-created_at"]
        self.select_related = select_related or []
        self.filters = filters or []

    def build_filters(self, request, queryset):
        filter_defs = []
        for spec in self.filters:
            options = [{"value": "", "label": "All"}]
            values = []
            if spec.get("queryset"):
                values = list(spec["queryset"])
                for item in values:
                    options.append({"value": str(getattr(item, "pk", "")), "label": str(item)})
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
                    options.append({"value": str(value), "label": str(value)})
            selected = request.GET.get(spec["param"], "")
            if selected:
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

    def redirect(self):
        return redirect("admin_component", component_slug=self.slug)

    def handle(self, request):
        create_form = self.form_class()
        edit_form = None
        edit_instance = None
        edit_id = request.GET.get("edit")
        data_list = []
        db_error = None
        table_ready = True

        qs = self.get_queryset()
        filter_defs = []
        if table_ready:
            try:
                qs, filter_defs = self.build_filters(request, qs)
            except ProgrammingError as exc:
                table_ready = False
                db_error = str(exc)
        if table_ready:
            try:
                data_list = list(qs)
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
            form = self.form_class(request.POST, instance=instance)
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
        }


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
    ),
    "snapshotSummaries": ModelComponentHandler(
        slug="snapshotSummaries",
        model=SnapshotSummaryRow,
        form_class=SnapshotSummaryForm,
        ordering=["borrower__company__company", "borrower__primary_contact", "section"],
        select_related=["borrower", "borrower__company"],
    ),
    "machineryEquipment": ModelComponentHandler(
        slug="machineryEquipment",
        model=MachineryEquipmentRow,
        form_class=MachineryEquipmentForm,
        ordering=["equipment_type"],
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
            {"param": "division", "label": "Division", "field": "division"},
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
            {"param": "division", "label": "Division", "field": "division"},
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
            {"param": "division", "label": "Division", "field": "division"},
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
            {"param": "division", "label": "Division", "field": "division"},
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
        ],
    ),
    "compositeIndex": ModelComponentHandler(
        slug="compositeIndex",
        model=CompositeIndexRow,
        form_class=CompositeIndexForm,
        ordering=["-date"],
        select_related=["borrower", "borrower__company"],
    ),
    "forecast": ModelComponentHandler(
        slug="forecast",
        model=ForecastRow,
        form_class=ForecastForm,
        ordering=["-as_of_date", "-period"],
    ),
    "currentWeekVariance": ModelComponentHandler(
        slug="currentWeekVariance",
        model=CurrentWeekVarianceRow,
        form_class=CurrentWeekVarianceForm,
        ordering=["-date", "category"],
    ),
    "cumulativeVariance": ModelComponentHandler(
        slug="cumulativeVariance",
        model=CummulativeVarianceRow,
        form_class=CumulativeVarianceForm,
        ordering=["-date", "category"],
    ),
    "collateralLimits": ModelComponentHandler(
        slug="collateralLimits",
        model=CollateralLimitsRow,
        form_class=CollateralLimitsForm,
        ordering=["division", "collateral_type", "collateral_sub_type"],
        select_related=["borrower", "borrower__company"],
    ),
    "ineligibles": ModelComponentHandler(
        slug="ineligibles",
        model=IneligiblesRow,
        form_class=IneligiblesForm,
        ordering=["division", "collateral_type", "collateral_sub_type"],
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
