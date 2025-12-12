from django.contrib import admin

from .models import (
    Amount,
    Borrower,
    Collateral,
    Company,
    Division,
    Equipment,
    EquipmentValue,
    LiquidationValue,
    SpecificIndividual,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("company_name", "company_id", "industry", "primary_naics")


@admin.register(Borrower)
class BorrowerAdmin(admin.ModelAdmin):
    list_display = (
        "primary_contact_name",
        "company",
        "primary_contact_email",
        "update_interval",
    )


admin.site.register(SpecificIndividual)
admin.site.register(Collateral)
admin.site.register(Equipment)
admin.site.register(EquipmentValue)
admin.site.register(LiquidationValue)
admin.site.register(Division)
admin.site.register(Amount)
