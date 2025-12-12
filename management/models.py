from django.db import models

# Company Model
class Company(models.Model):
    company_name = models.CharField(max_length=255)
    company_id = models.BigIntegerField(unique=True)
    industry = models.CharField(max_length=255)
    primary_naics = models.CharField(max_length=10)

    def __str__(self):
        return self.company_name

# Borrower Overview Model
class Borrower(models.Model):
    company = models.ForeignKey(Company, related_name='borrowers', on_delete=models.CASCADE)
    website = models.URLField(max_length=255)
    primary_contact_name = models.CharField(max_length=255)
    primary_contact_phone = models.CharField(max_length=20)
    primary_contact_email = models.EmailField(max_length=255)
    update_interval = models.CharField(max_length=50)
    current_update = models.DateField()
    previous_update = models.DateField()
    next_update = models.DateField()
    lender_name = models.CharField(max_length=255)
    lender_id = models.BigIntegerField()

    def __str__(self):
        return f"{self.primary_contact_name} - {self.company.company_name}"

# Specific Individual Model
class SpecificIndividual(models.Model):
    borrower = models.ForeignKey(Borrower, related_name='specific_individuals', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    individual_id = models.CharField(max_length=50)

    def __str__(self):
        return self.name

# Collateral Model (Main Types, Subtypes, Values)
class Collateral(models.Model):
    borrower = models.ForeignKey(Borrower, related_name='collaterals', on_delete=models.CASCADE)
    main_type = models.CharField(max_length=255)
    sub_type = models.CharField(max_length=255)
    beginning_value = models.DecimalField(max_digits=15, decimal_places=2)
    ineligibles_value = models.DecimalField(max_digits=15, decimal_places=2)
    eligible_value = models.DecimalField(max_digits=15, decimal_places=2)
    nolv_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    dilution_rate = models.DecimalField(max_digits=5, decimal_places=2)
    advanced_rate = models.DecimalField(max_digits=5, decimal_places=2)
    rate_limit = models.DecimalField(max_digits=5, decimal_places=2)
    utilized_rate = models.DecimalField(max_digits=5, decimal_places=2)
    pre_reserve_collateral = models.DecimalField(max_digits=15, decimal_places=2)
    collateral_reserves = models.DecimalField(max_digits=15, decimal_places=2)
    net_collateral = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.main_type} - {self.sub_type}"

# Equipment Model
class Equipment(models.Model):
    borrower = models.ForeignKey(Borrower, related_name='equipments', on_delete=models.CASCADE)
    equipment_type = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.equipment_type} - {self.manufacturer}"

# Equipment Value Model
class EquipmentValue(models.Model):
    equipment = models.ForeignKey(Equipment, related_name='equipment_values', on_delete=models.CASCADE)
    year = models.IntegerField()
    condition = models.CharField(max_length=50)
    fair_market_value = models.DecimalField(max_digits=15, decimal_places=2)
    orderly_liquidation_value = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"{self.equipment.equipment_type} - {self.year}"

# Liquidation Value Model
class LiquidationValue(models.Model):
    borrower = models.ForeignKey(Borrower, related_name='liquidation_values', on_delete=models.CASCADE)
    total_orderly_liquidation_value = models.DecimalField(max_digits=15, decimal_places=2)
    total_asset_count = models.IntegerField()

    def __str__(self):
        return f"Liquidation Value for {self.borrower.company.company_name}"

# Division Model
class Division(models.Model):
    company = models.ForeignKey(Company, related_name='divisions', on_delete=models.CASCADE)
    division_name = models.CharField(max_length=255)
    as_of_date = models.DateField()
    bucket = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.division_name} - {self.as_of_date}"

# Amount Model
class Amount(models.Model):
    division = models.ForeignKey(Division, related_name='amounts', on_delete=models.CASCADE)
    pct_of_total = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return f"Amount for {self.division.division_name} - {self.pct_of_total}%"
