from django.contrib import admin

from management import models


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "specific_individual",
        "specific_individual_id",
        "lender_name",
        "lender_identifier",
        "company_id",
        "industry",
        "website",
        "email",
        "created_at",
    )
    search_fields = (
        "company",
        "specific_individual",
        "specific_individual_id",
        "lender_name",
        "lender_identifier",
        "company_id",
        "industry",
        "email",
    )
    list_filter = ("industry",)


@admin.register(models.Borrower)
class BorrowerAdmin(admin.ModelAdmin):
    list_display = (
        "primary_contact",
        "company",
        "primary_contact_phone",
        "primary_contact_email",
        "update_interval",
    )
    search_fields = ("primary_contact", "company__company", "primary_contact_email")
    list_filter = ("update_interval",)


class BaseBorrowerModelAdmin(admin.ModelAdmin):
    autocomplete_fields = ("borrower",)
    search_fields = ("borrower__primary_contact", "borrower__company__company")


@admin.register(models.ARMetricsRow)
class ARMetricsRowAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "division",
        "as_of_date",
        "balance",
        "dso",
        "pct_past_due",
        "current_amt",
        "past_due_amt",
    )
    list_filter = ("division", "as_of_date")
    date_hierarchy = "as_of_date"


@admin.register(models.AgingCompositionRow)
class AgingCompositionRowAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "division",
        "as_of_date",
        "bucket",
        "amount",
        "pct_of_total",
    )
    list_filter = ("division", "bucket")
    date_hierarchy = "as_of_date"


@admin.register(models.IneligibleOverviewRow)
class IneligibleOverviewAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "division",
        "date",
        "total_ineligible",
        "past_due_gt_90_days",
        "dilution",
    )
    list_filter = ("division",)
    date_hierarchy = "date"


@admin.register(models.IneligibleTrendRow)
class IneligibleTrendAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "division",
        "date",
        "ineligible_pct_of_ar",
        "total_ar",
        "total_ineligible",
    )
    list_filter = ("division",)
    date_hierarchy = "date"


@admin.register(models.ConcentrationADODSORow)
class ConcentrationADODSORowAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "division",
        "as_of_date",
        "customer",
        "current_concentration_pct",
        "current_ado_days",
        "current_dso_days",
    )
    list_filter = ("division",)
    date_hierarchy = "as_of_date"


@admin.register(models.MachineryEquipmentRow)
class MachineryEquipmentRowAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "equipment_type",
        "manufacturer",
        "year",
        "fair_market_value",
        "orderly_liquidation_value",
        "estimated_fair_market_value",
        "estimated_orderly_liquidation_value",
    )
    list_filter = ("equipment_type",)


@admin.register(models.BBCAvailabilityRow)
class BBCAvailabilityRowAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "period",
        "net_collateral",
        "outstanding_balance",
        "availability",
    )
    list_filter = ("period",)
    date_hierarchy = "period"


@admin.register(models.ValueTrendRow)
class ValueTrendRowAdmin(BaseBorrowerModelAdmin):
    list_display = (
        "borrower",
        "date",
        "estimated_olv",
        "appraised_olv",
    )
    list_filter = ("date",)
    date_hierarchy = "date"


@admin.register(models.FGGrossRecoveryHistoryRow)
class FGGrossRecoveryHistoryRowAdmin(BaseBorrowerModelAdmin):
    list_display = ("borrower", "division", "as_of_date", "category", "gross_recovery")
    list_filter = ("division",)
    date_hierarchy = "as_of_date"
