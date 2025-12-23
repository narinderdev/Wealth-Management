from django import forms

from .models import (
    ARMetricsRow,
    AgingCompositionRow,
    Borrower,
    CollateralOverviewRow,
    Company,
    ConcentrationADODSORow,
    FGCompositionRow,
    FGIneligibleDetailRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    FGInventoryMetricsRow,
    FGGrossRecoveryHistoryRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    ForecastRow,
    AvailabilityForecastRow,
    CurrentWeekVarianceRow,
    CummulativeVarianceRow,
    CollateralLimitsRow,
    IneligiblesRow,
    NOLVTableRow,
    RawMaterialRecoveryRow,
    CompositeIndexRow,
    RiskSubfactorsRow,
    RMCategoryHistoryRow,
    RMIneligibleOverviewRow,
    RMInventoryMetricsRow,
    SalesGMTrendRow,
    SpecificIndividual,
    WIPCategoryHistoryRow,
    WIPIneligibleOverviewRow,
    WIPInventoryMetricsRow,
    WIPRecoveryRow,
)


class StyledModelForm(forms.ModelForm):
    """
    Adds a shared class to inputs for consistent styling inside the custom admin.
    """

    input_class = "component-input"
    required_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in getattr(self, "required_fields", ()):
            if name in self.fields:
                self.fields[name].required = True
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{classes} {self.input_class}".strip()
            if getattr(field.widget, "input_type", "") == "password":
                field.widget.attrs["data-password-input"] = "true"
            if field.required:
                field.widget.attrs.setdefault("required", "required")
                field.widget.attrs["data-required"] = "true"
                field.widget.attrs.setdefault("aria-required", "true")
                if field.label:
                    field.widget.attrs.setdefault("data-field-label", str(field.label))


class BorrowerModelForm(StyledModelForm):
    required_fields = ("borrower",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "borrower" in self.fields:
            borrower_field = self.fields["borrower"]
            borrower_field.queryset = (
                Borrower.objects.select_related("company")
                .order_by("company__company", "primary_contact")
            )
            borrower_field.label = "Borrower (from global selection)"
            borrower_field.help_text = "Borrower is set from the global selector in the header."
            borrower_field.widget.attrs.update(
                {
                    "data-global-borrower": "true",
                    "data-global-borrower-label": "Borrower (from global selection)",
                }
            )


class CompanyForm(StyledModelForm):
    required_fields = ("company", "email", "password")

    class Meta:
        model = Company
        fields = ["company", "industry", "primary_naics", "website", "email", "password"]
        widgets = {
            "password": forms.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["password"].required = True
        # Prevent hashed value from appearing in edit forms.
        self.fields["password"].initial = ""
        self.initial["password"] = ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            instance.set_password(password, save=False)
        if commit:
            instance.save()
        return instance


class BorrowerForm(StyledModelForm):
    required_fields = ("company", "primary_contact", "update_interval")

    class Meta:
        model = Borrower
        fields = [
            "company",
            "primary_contact",
            "primary_contact_phone",
            "primary_contact_email",
            "update_interval",
            "current_update",
            "previous_update",
            "next_update",
            "lender",
            "lender_id",
        ]
        widgets = {
            "current_update": forms.DateInput(attrs={"type": "date"}),
            "previous_update": forms.DateInput(attrs={"type": "date"}),
            "next_update": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = Company.objects.order_by("company")

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("primary_contact_email")
        phone = cleaned_data.get("primary_contact_phone")
        if not email and not phone:
            raise forms.ValidationError("Provide an email or phone for the primary contact.")
        return cleaned_data


class SpecificIndividualForm(StyledModelForm):
    required_fields = ("borrower", "specific_individual")

    class Meta:
        model = SpecificIndividual
        fields = ["borrower", "specific_individual", "specific_id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower"].queryset = Borrower.objects.select_related("company").order_by("company__company")


class CollateralOverviewForm(BorrowerModelForm):
    required_fields = ("borrower", "main_type", "sub_type")

    class Meta:
        model = CollateralOverviewRow
        fields = [
            "borrower",
            "main_type",
            "sub_type",
            "beginning_collateral",
            "ineligibles",
            "eligible_collateral",
            "nolv_pct",
            "dilution_rate",
            "advanced_rate",
            "rate_limit",
            "utilized_rate",
            "pre_reserve_collateral",
            "reserves",
            "net_collateral",
        ]


class MachineryEquipmentForm(BorrowerModelForm):
    required_fields = ("borrower", "equipment_type", "manufacturer", "serial_number")

    class Meta:
        model = MachineryEquipmentRow
        fields = [
            "borrower",
            "equipment_type",
            "manufacturer",
            "serial_number",
            "year",
            "condition",
            "fair_market_value",
            "orderly_liquidation_value",
            "total_asset_count",
            "total_fair_market_value",
            "total_orderly_liquidation_value",
        ]


class AgingCompositionForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "bucket", "division")

    class Meta:
        model = AgingCompositionRow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "bucket",
            "pct_of_total",
            "amount",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class ARMetricsForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "balance")

    class Meta:
        model = ARMetricsRow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "balance",
            "dso",
            "pct_past_due",
            "current_amt",
            "past_due_amt",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class IneligibleTrendForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "division")

    class Meta:
        model = IneligibleTrendRow
        fields = [
            "borrower",
            "date",
            "division",
            "total_ar",
            "total_ineligible",
            "ineligible_pct_of_ar",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class IneligibleOverviewForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "division")

    class Meta:
        model = IneligibleOverviewRow
        fields = [
            "borrower",
            "date",
            "division",
            "past_due_gt_90_days",
            "dilution",
            "cross_age",
            "concentration_over_cap",
            "foreign",
            "government",
            "intercompany",
            "contra",
            "other",
            "total_ineligible",
            "ineligible_pct_of_ar",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class ConcentrationADODSOForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "customer", "division")

    class Meta:
        model = ConcentrationADODSORow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "customer",
            "current_concentration_pct",
            "avg_ttm_concentration_pct",
            "variance_concentration_pp",
            "current_ado_days",
            "avg_ttm_ado_days",
            "variance_ado_days",
            "current_dso_days",
            "avg_ttm_dso_days",
            "variance_dso_days",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class FGInventoryMetricsForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "inventory_type", "total_inventory")

    class Meta:
        model = FGInventoryMetricsRow
        fields = [
            "borrower",
            "inventory_type",
            "division",
            "as_of_date",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "ineligible_pct_of_inventory",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class FGIneligibleDetailForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division")

    class Meta:
        model = FGIneligibleDetailRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "slow_moving_obsolete",
            "aged",
            "off_site",
            "consigned",
            "in_transit",
            "damaged_non_saleable",
            "total_ineligible",
            "ineligible_pct_of_inventory",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class FGCompositionForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "division")

    class Meta:
        model = FGCompositionRow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "fg_available",
            "fg_0_13",
            "fg_13_26",
            "fg_26_39",
            "fg_39_52",
            "fg_52_plus",
            "fg_no_sales",
            "inline_pct",
            "excess_pct",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class FGInlineCategoryAnalysisForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "category", "division")

    class Meta:
        model = FGInlineCategoryAnalysisRow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "category",
            "fg_total",
            "fg_ineligible",
            "fg_available",
            "pct_of_available",
            "sales",
            "cogs",
            "gm",
            "gm_pct",
            "weeks_of_supply",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class SalesGMTrendForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "division", "net_sales")

    class Meta:
        model = SalesGMTrendRow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "net_sales",
            "gross_margin_pct",
            "gross_margin_dollars",
            "ttm_sales",
            "ttm_sales_prior",
            "trend_ttm_pct",
            "ma3",
            "ma3_prior",
            "trend_3_m_pct",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class FGInlineExcessByCategoryForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "category", "division")

    class Meta:
        model = FGInlineExcessByCategoryRow
        fields = [
            "borrower",
            "division",
            "as_of_date",
            "category",
            "fg_available",
            "inline_dollars",
            "inline_pct",
            "excess_dollars",
            "excess_pct",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class RMInventoryMetricsForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "inventory_type", "total_inventory")

    class Meta:
        model = RMInventoryMetricsRow
        fields = [
            "inventory_type",
            "borrower",
            "division",
            "as_of_date",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "ineligible_pct_of_inventory",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class RMIneligibleOverviewForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division")

    class Meta:
        model = RMIneligibleOverviewRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "slow_moving_obsolete",
            "aged",
            "off_site",
            "consigned",
            "in_transit",
            "damaged_non_saleable",
            "total_ineligible",
            "ineligible_pct_of_inventory",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class RMCategoryHistoryForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division", "category")

    class Meta:
        model = RMCategoryHistoryRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "category",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "pct_available",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class WIPInventoryMetricsForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "inventory_type", "total_inventory", "division")

    class Meta:
        model = WIPInventoryMetricsRow
        fields = [
            "inventory_type",
            "borrower",
            "division",
            "as_of_date",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "ineligible_pct_of_inventory",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class WIPIneligibleOverviewForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division")

    class Meta:
        model = WIPIneligibleOverviewRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "slow_moving_obsolete",
            "aged",
            "off_site",
            "consigned",
            "in_transit",
            "damaged_non_saleable",
            "total_ineligible",
            "ineligible_pct_of_inventory",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class WIPCategoryHistoryForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division", "category")

    class Meta:
        model = WIPCategoryHistoryRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "category",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "pct_available",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class FGGrossRecoveryHistoryForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "division", "category", "type", "cost")

    class Meta:
        model = FGGrossRecoveryHistoryRow
        fields = [
            "borrower",
            "as_of_date",
            "division",
            "category",
            "type",
            "cost",
            "selling_price",
            "gross_recovery",
            "pct_of_cost",
            "pct_of_sp",
            "wos",
            "gm_pct",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
        }


class WIPRecoveryForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division", "category", "total_inventory")

    class Meta:
        model = WIPRecoveryRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "category",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "pct_available",
            "recovery_pct",
            "gross_recovery",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class RawMaterialRecoveryForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "inventory_type", "division", "category", "total_inventory")

    class Meta:
        model = RawMaterialRecoveryRow
        fields = [
            "borrower",
            "date",
            "inventory_type",
            "division",
            "category",
            "total_inventory",
            "ineligible_inventory",
            "available_inventory",
            "pct_available",
            "recovery_pct",
            "gross_recovery",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class NOLVTableForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "division", "line_item")

    class Meta:
        model = NOLVTableRow
        fields = [
            "borrower",
            "date",
            "division",
            "line_item",
            "fg_usd",
            "fg_pct_cost",
            "rm_usd",
            "rm_pct_cost",
            "wip_usd",
            "wip_pct_cost",
            "total_usd",
            "total_pct_cost",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class RiskSubfactorsForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "main_category", "sub_risk")

    class Meta:
        model = RiskSubfactorsRow
        fields = [
            "borrower",
            "date",
            "main_category",
            "sub_risk",
            "risk_score",
            "high_impact_factor",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class CompositeIndexForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "overall_score")

    class Meta:
        model = CompositeIndexRow
        fields = [
            "borrower",
            "date",
            "overall_score",
            "ar_risk",
            "inventory_risk",
            "company_risk",
            "industry_risk",
            "weight_ar",
            "weight_inventory",
            "weight_company",
            "weight_industry",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
class ForecastForm(BorrowerModelForm):
    required_fields = ("borrower", "as_of_date", "period", "actual_forecast", "available_collateral", "loan_balance")

    class Meta:
        model = ForecastRow
        fields = [
            "borrower",
            "as_of_date",
            "period",
            "actual_forecast",
            "available_collateral",
            "loan_balance",
            "revolver_availability",
            "net_sales",
            "gross_margin_pct",
            "ar",
            "finished_goods",
            "raw_materials",
            "work_in_process",
        ]
        widgets = {
            "as_of_date": forms.DateInput(attrs={"type": "date"}),
            "period": forms.DateInput(attrs={"type": "date"}),
        }


class AvailabilityForecastForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "category", "x")

    class Meta:
        model = AvailabilityForecastRow
        fields = [
            "borrower",
            "date",
            "category",
            "x",
            "week_1",
            "week_2",
            "week_3",
            "week_4",
            "week_5",
            "week_6",
            "week_7",
            "week_8",
            "week_9",
            "week_10",
            "week_11",
            "week_12",
            "week_13",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class CurrentWeekVarianceForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "category", "projected", "actual")

    class Meta:
        model = CurrentWeekVarianceRow
        fields = [
            "borrower",
            "date",
            "category",
            "projected",
            "actual",
            "variance",
            "variance_pct",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class CumulativeVarianceForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "category", "projected", "actual")

    class Meta:
        model = CummulativeVarianceRow
        fields = [
            "borrower",
            "date",
            "category",
            "projected",
            "actual",
            "variance",
            "variance_pct",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class CollateralLimitsForm(BorrowerModelForm):
    required_fields = ("borrower", "collateral_type", "usd_limit")

    class Meta:
        model = CollateralLimitsRow
        fields = [
            "borrower",
            "division",
            "collateral_type",
            "collateral_sub_type",
            "usd_limit",
            "pct_limit",
        ]


class IneligiblesForm(BorrowerModelForm):
    required_fields = ("borrower", "collateral_type")

    class Meta:
        model = IneligiblesRow
        fields = [
            "borrower",
            "division",
            "collateral_type",
            "collateral_sub_type",
        ]
