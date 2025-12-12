from django.contrib import admin

from management.models import Amount, Borrower, Collateral, Company, Division, Equipment, EquipmentValue, LiquidationValue, SpecificIndividual

# Register your models here.
admin.site.register(Company)
admin.site.register(Borrower)
admin.site.register(SpecificIndividual)
admin.site.register(Collateral)
admin.site.register(Equipment)
admin.site.register(EquipmentValue)
admin.site.register(LiquidationValue)
admin.site.register(Division)
admin.site.register(Amount)