from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import FileExtensionValidator
from django.db import models


# =========================
# Helpers
# =========================
def MoneyField():
    return models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

def PctField():
    return models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# =========================
# Core entities (from 'Borrower Overview')
# =========================
class Company(TimeStampedModel):
    company = models.CharField(max_length=255, null=True, blank=True)
    company_id = models.BigIntegerField(unique=True)
    industry = models.CharField(max_length=255, null=True, blank=True)
    primary_naics = models.CharField(max_length=255, null=True, blank=True)
    website = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True, db_column="company_email")
    password = models.CharField(max_length=128, null=True, blank=True, db_column="company_password")
    specific_individual = models.CharField(max_length=255, null=True, blank=True)
    specific_individual_id = models.CharField(max_length=255, null=True, blank=True)
    lender_name = models.CharField(max_length=255, null=True, blank=True)
    lender_identifier = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.company or str(self.company_id)

    def set_password(self, raw_password, save=True):
        self.password = make_password(raw_password)
        if save:
            self.save(update_fields=["password"])

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    @property
    def company_email(self):
        return self.email

    @company_email.setter
    def company_email(self, value):
        self.email = value

    @property
    def company_password(self):
        return self.password

    @company_password.setter
    def company_password(self, value):
        self.password = value

    def save(self, *args, **kwargs):
        if not self.company_id:
            from django.db.models import Max

            last_id = Company.objects.aggregate(max_id=Max("company_id")).get("max_id")
            self.company_id = (last_id or 0) + 1
        super().save(*args, **kwargs)


class Borrower(TimeStampedModel):
    UPDATE_INTERVAL_CHOICES = [
        ("Annual", "Annual"),
        ("Semi-Annual", "Semi-Annual"),
        ("Quarterly", "Quarterly"),
        ("Monthly", "Monthly"),
        ("Weekly", "Weekly"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='borrowers')
    primary_contact = models.CharField(max_length=255, null=True, blank=True)
    primary_contact_phone = models.CharField(max_length=30, null=True, blank=True)
    primary_contact_email = models.EmailField(max_length=255, null=True, blank=True)
    update_interval = models.CharField(max_length=50, choices=UPDATE_INTERVAL_CHOICES, null=True, blank=True)
    current_update = models.DateField(null=True, blank=True)
    previous_update = models.DateField(null=True, blank=True)
    next_update = models.DateField(null=True, blank=True)
    lender = models.CharField(max_length=255, null=True, blank=True)
    lender_id = models.CharField(max_length=255, null=True, blank=True)
    primary_specific_individual = models.ForeignKey(
        "SpecificIndividual",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_for_borrowers",
    )
    industry = models.CharField(max_length=255, null=True, blank=True)
    primary_naics = models.CharField(max_length=255, null=True, blank=True)
    website = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        label = self.primary_contact
        if not label and self.primary_specific_individual:
            label = self.primary_specific_individual.specific_individual
        return f"{self.company} - {label or 'Borrower'}"


# Removed BorrowerUser to ensure Borrower cannot log in

class BorrowerReport(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    source_file = models.CharField(max_length=255, null=True, blank=True)
    report_date = models.DateField(null=True, blank=True)


class ReportRow(TimeStampedModel):
    class Meta:
        abstract = True


class SpecificIndividual(TimeStampedModel):
    borrower = models.ForeignKey(Borrower, on_delete=models.CASCADE, related_name='specific_individuals')
    specific_individual = models.CharField(max_length=255, null=True, blank=True)
    specific_id = models.BigIntegerField(null=True, blank=True)


# -------------------------
# Sheet: Borrower Overview
# -------------------------
class BorrowerOverviewRow(TimeStampedModel):
    company = models.CharField(max_length=255, null=True, blank=True)  # Company
    company_id = models.BigIntegerField(null=True, blank=True)  # Company ID
    industry = models.CharField(max_length=255, null=True, blank=True)  # Industry
    primary_naics = MoneyField()  # Primary NAICS
    website = models.CharField(max_length=255, null=True, blank=True)  # Website
    primary_contact = models.CharField(max_length=255, null=True, blank=True)  # Primary Contact
    primary_contact_phone = models.CharField(max_length=30, null=True, blank=True)  # Primary Contact Phone
    primary_contact_email = models.EmailField(max_length=255, null=True, blank=True)  # Primary Contact Email
    update_interval = models.DateField(null=True, blank=True)  # Update Interval 
    current_update = models.DateField(null=True, blank=True)  # Current Update
    previous_update = models.DateField(null=True, blank=True)  # Previous Update
    next_update = models.DateField(null=True, blank=True)  # Next Update 
    lender = models.CharField(max_length=255, null=True, blank=True)  # Lender
    lender_id = models.BigIntegerField(null=True, blank=True)  # Lender ID
    specific_individual = models.CharField(max_length=255, null=True, blank=True)  # Specific Individual
    specific_id = models.BigIntegerField(null=True, blank=True)  # Specific ID

    class Meta:
        db_table = 'borrower_overview'


# -------------------------
# Sheet: Collateral Overview
# -------------------------
class CollateralOverviewRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="collateral_overview_rows",
        null=True,
        blank=True,
    )
    main_type = models.CharField(max_length=255, null=True, blank=True)  # Main Type
    sub_type = models.CharField(max_length=255, null=True, blank=True)  # SubType
    beginning_collateral = MoneyField()  # Beginning Collateral
    ineligibles = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Ineligibles
    eligible_collateral = MoneyField()  # Eligible Collateral
    nolv_pct = PctField()  # NOLV %
    dilution_rate = PctField()  # Dilution Rate
    advanced_rate = PctField()  # Advanced Rate
    rate_limit = PctField()  # Rate Limit
    utilized_rate = PctField()  # Utilized Rate
    pre_reserve_collateral = MoneyField()  # Pre-Reserve Collateral
    reserves = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Reserves
    net_collateral = MoneyField()  # Net Collateral
    snapshot_summary = models.TextField(null=True, blank=True, verbose_name="Snapshot Summary")

    class Meta:
        db_table = 'collateral_overview'


# -------------------------
# Snapshot Summaries
# -------------------------
class SnapshotSummaryRow(TimeStampedModel):
    SECTION_ACCOUNTS_RECEIVABLE = "accounts_receivable"
    SECTION_INVENTORY_SUMMARY = "inventory_summary"
    SECTION_OTHER_COLLATERAL = "other_collateral"
    SECTION_RISK = "risk"
    SECTION_FORECAST_LIQUIDITY = "forecast_liquidity"
    SECTION_FORECAST_SALES_GM = "forecast_sales_gm"
    SECTION_FORECAST_AR = "forecast_ar"
    SECTION_FORECAST_INVENTORY = "forecast_inventory"
    SECTION_WEEK_SUMMARY = "week_summary"

    SECTION_CHOICES = [
        (SECTION_ACCOUNTS_RECEIVABLE, "Accounts Receivable"),
        (SECTION_INVENTORY_SUMMARY, "Inventory Summary"),
        (SECTION_OTHER_COLLATERAL, "Other Collateral"),
        (SECTION_RISK, "Risk"),
        (SECTION_FORECAST_LIQUIDITY, "Forecast - Liquidity"),
        (SECTION_FORECAST_SALES_GM, "Forecast - Sales & Gross Margin"),
        (SECTION_FORECAST_AR, "Forecast - Accounts Receivable"),
        (SECTION_FORECAST_INVENTORY, "Forecast - Inventory"),
        (SECTION_WEEK_SUMMARY, "Weekly Summary"),
    ]

    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="snapshot_summaries",
    )
    section = models.CharField(max_length=64, choices=SECTION_CHOICES)
    summary_text = models.TextField(null=True, blank=True, verbose_name="Snapshot Summary")

    class Meta:
        db_table = "snapshot_summaries"
        unique_together = ("borrower", "section")

    def __str__(self):
        borrower_label = str(self.borrower) if self.borrower_id else "Unknown borrower"
        return f"{borrower_label} - {self.get_section_display()}"


# -------------------------
# Sheet: Machinery & Equipment 
# -------------------------
class MachineryEquipmentRow(TimeStampedModel):
    equipment_type = models.CharField(max_length=255, null=True, blank=True)  # Equipment Type
    manufacturer = models.CharField(max_length=255, null=True, blank=True)  # Manufacturer
    serial_number = models.CharField(max_length=255, null=True, blank=True)  # Serial Number
    year = models.IntegerField(null=True, blank=True)  # Year
    condition = models.CharField(max_length=255, null=True, blank=True)  # Condition
    fair_market_value = MoneyField()  # Fair Market Value
    orderly_liquidation_value = models.BigIntegerField(null=True, blank=True)  # Orderly Liquidation Value
    total_asset_count = models.IntegerField(null=True, blank=True)  # Total Asset Count 
    total_fair_market_value = MoneyField()  # Total Fair Market Value 
    total_orderly_liquidation_value = models.BigIntegerField(null=True, blank=True)  # Total Orderly Liquidation Value 
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="machinery_equipment_rows",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'machinery_and_equipment'


# -------------------------
# Sheet: Aging Composition
# -------------------------
class AgingCompositionRow(TimeStampedModel):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    bucket = models.CharField(max_length=255, null=True, blank=True)  # Bucket
    pct_of_total = PctField()  # PctOfTotal
    amount = MoneyField()  # Amount
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="aging_composition_rows",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'aging_composition'


# -------------------------
# Sheet: AR_Metrics
# -------------------------
class ARMetricsRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="ar_metrics_rows",
        null=True,
        blank=True,
    )
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    balance = MoneyField()  # Balance
    dso = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # DSO
    pct_past_due = PctField()  # PctPastDue
    current_amt = MoneyField()  # CurrentAmt
    past_due_amt = MoneyField()  # PastDueAmt

    class Meta:
        db_table = 'ar_metrics'


# -------------------------
# Sheet: Top20_By_Total_AR
# -------------------------
class Top20ByTotalARRow(TimeStampedModel):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    customer = models.CharField(max_length=255, null=True, blank=True)  # Customer
    current = MoneyField()  # Current
    col_0_30 = MoneyField()  # 0-30
    col_31_60 = MoneyField()  # 31-60
    col_61_90 = MoneyField()  # 61-90
    col_91_plus = MoneyField()  # 91+
    total_ar = MoneyField()  # TotalAR
    coverage_pct_of_division_ar = PctField()  # CoveragePctOfDivisionAR
    report = models.ForeignKey(
        "BorrowerReport",
        on_delete=models.CASCADE,
        related_name="%(class)s_rows",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'top20_by_total_ar'


# -------------------------
# Sheet: Top20_By_PastDue
# -------------------------
class Top20ByPastDueRow(TimeStampedModel):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    customer = models.CharField(max_length=255, null=True, blank=True)  # Customer
    current = MoneyField()  # Current
    col_0_30 = MoneyField()  # 0-30
    col_31_60 = MoneyField()  # 31-60
    col_61_90 = MoneyField()  # 61-90
    col_91_plus = MoneyField()  # 91+
    total_ar = MoneyField()  # TotalAR
    total_past_due = MoneyField()  # TotalPastDue
    coverage_pct_of_division_past_due = PctField()  # CoveragePctOfDivisionPastDue
    report = models.ForeignKey(
        "BorrowerReport",
        on_delete=models.CASCADE,
        related_name="%(class)s_rows",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'top20_by_past_due'


# -------------------------
# Sheet: Ineligible_Trend
# -------------------------
class IneligibleTrendRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    total_ar = MoneyField()  # Total AR
    total_ineligible = MoneyField()  # Total Ineligible
    ineligible_pct_of_ar = PctField()  # Ineligible % of AR
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="ineligible_trend",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'ineligible_trend'


# -------------------------
# Sheet: Ineligible_Overview
# -------------------------
class IneligibleOverviewRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    past_due_gt_90_days = MoneyField()  # Past Due >90 Days
    dilution = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Dilution
    cross_age = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Cross Age
    concentration_over_cap = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Concentration Over Cap
    foreign = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Foreign
    government = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Government
    intercompany = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Intercompany
    contra = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Contra
    other = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Other
    total_ineligible = MoneyField()  # Total Ineligible
    ineligible_pct_of_ar = PctField()  # Ineligible % of AR
    borrower = models.ForeignKey(   
        "Borrower",
        on_delete=models.CASCADE,
        related_name="ineligible_overview",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'ineligible_overview'


# -------------------------
# Sheet: Concentration_ADO_DSO
# -------------------------
class ConcentrationADODSORow(TimeStampedModel):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    customer = models.CharField(max_length=255, null=True, blank=True)  # Customer
    current_concentration_pct = PctField()  # Current Concentration %
    avg_ttm_concentration_pct = PctField()  # Avg TTM Concentration %
    variance_concentration_pp = MoneyField()  # Variance Concentration (pp)
    current_ado_days = MoneyField()  # Current ADO (Days)
    avg_ttm_ado_days = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Avg TTM ADO (Days)
    variance_ado_days = MoneyField()  # Variance ADO (Days)
    current_dso_days = MoneyField()  # Current DSO (Days)
    avg_ttm_dso_days = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Avg TTM DSO (Days)
    variance_dso_days = MoneyField()  # Variance DSO (Days)
    borrower = models.ForeignKey(   
        "Borrower",
        on_delete=models.CASCADE,
        related_name="concentration_ado_dso",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'concentration_ado_dso'


# -------------------------
# Sheet: FG_Inventory_Metrics
# -------------------------
class FGInventoryMetricsRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_inventory_metrics_rows",
        null=True,
        blank=True,
    )
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    ineligible_pct_of_inventory = PctField()  # IneligiblePctOfInventory
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_inventory_metrics",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'fg_inventory_metrics'


# -------------------------
# Sheet: FG_Ineligible_detail
# -------------------------
class FGIneligibleDetailRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_ineligible_detail_rows",
        null=True,
        blank=True,
    )
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    slow_moving_obsolete = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Slow-Moving/Obsolete
    aged = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Aged
    off_site = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Off Site
    consigned = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Consigned
    in_transit = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # In-Transit
    damaged_non_saleable = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Damaged/Non-Saleable
    total_ineligible = MoneyField()  # Total Ineligible
    ineligible_pct_of_inventory = PctField()  # Ineligible % of Inventory
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_ineligible_detail",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'fg_ineligible_detail'

# -------------------------
# Sheet: FG_Composition
# -------------------------
class FGCompositionRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_composition_rows",
        null=True,
        blank=True,
    )
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    fg_available = MoneyField()  # FG_Available
    fg_0_13 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FG_0_13
    fg_13_26 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FG_13_26
    fg_26_39 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FG_26_39
    fg_39_52 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FG_39_52
    fg_52_plus = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FG_52Plus
    fg_no_sales = MoneyField()  # FG_NoSales
    inline_pct = PctField()  # InlinePct
    excess_pct = PctField()  # ExcessPct
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_composition",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'fg_composition'


# -------------------------
# Sheet: FG_Inline_Category_Analysis
# -------------------------
class FGInlineCategoryAnalysisRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_inline_category_analysis_rows",
        null=True,
        blank=True,
    )
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    fg_total = MoneyField()  # FG_Total
    fg_ineligible = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FG_Ineligible
    fg_available = MoneyField()  # FG_Available
    pct_of_available = PctField()  # % of Available
    sales = MoneyField()  # Sales
    cogs = MoneyField()  # COGS
    gm = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # GM
    gm_pct = PctField()  # GM%
    weeks_of_supply = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Weeks_of_Supply
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_inline_category_analysis",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'fg_inline_category_analysis'


# -------------------------
# Sheet: Sales_GM_Trend
# -------------------------
class SalesGMTrendRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="sales_gm_trend_rows",
        null=True,
        blank=True,
    )
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    net_sales = MoneyField()  # NetSales
    gross_margin_pct = PctField()  # GrossMarginPct
    gross_margin_dollars = MoneyField()  # GrossMarginDollars
    ttm_sales = MoneyField()  # TTM_Sales
    ttm_sales_prior = MoneyField()  # TTM_Sales_Prior
    trend_ttm_pct = PctField()  # Trend_TTM_Pct
    ma3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # MA3
    ma3_prior = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # MA3_prior
    trend_3_m_pct = PctField()  # Trend_3M_Pct
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="sales_gm_trend",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'sales_gm_trend'


# -------------------------
# Sheet: FG_Inline_Excess_By_Category
# -------------------------
class FGInlineExcessByCategoryRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_inline_excess_by_category_rows",
        null=True,
        blank=True,
    )
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    fg_available = MoneyField()  # FG_Available
    new_dollars = MoneyField()  # New_Dollars
    new_pct = PctField()  # New_Pct
    inline_dollars = MoneyField()  # Inline_Dollars
    inline_pct = PctField()  # Inline_Pct
    excess_dollars = MoneyField()  # Excess_Dollars
    excess_pct = PctField()  # Excess_Pct
    no_sales_dollars = MoneyField()  # NoSales_Dollars
    no_sales_pct = PctField()  # NoSales_Pct
    total_inline_dollars = MoneyField()  # TotalInline_Dollars
    total_inline_pct = PctField()  # TotalInline_Pct
    total_excess_dollars = MoneyField()  # TotalExcess_Dollars
    total_excess_pct = PctField()  # TotalExcess_Pct
    total_dollars = MoneyField()  # Total_Dollars
    total_pct = PctField()  # Total_Pct
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_inline_excess_by_category",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'fg_inline_excess_by_category'

    def save(self, *args, **kwargs):
        def to_dec(value):
            if value is None:
                return Decimal("0")
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except Exception:
                return Decimal("0")

        new_amount = to_dec(self.new_dollars)
        inline_amount = to_dec(self.inline_dollars)
        excess_amount = to_dec(self.excess_dollars)
        no_sales_amount = to_dec(self.no_sales_dollars)

        total_inline = new_amount + inline_amount
        total_excess = excess_amount + no_sales_amount
        total_amount = total_inline + total_excess

        def pct_of_total(amount):
            if total_amount <= 0:
                return Decimal("0")
            return amount / total_amount

        self.total_inline_dollars = total_inline
        self.total_excess_dollars = total_excess
        self.total_dollars = total_amount

        self.new_pct = pct_of_total(new_amount)
        self.inline_pct = pct_of_total(inline_amount)
        self.excess_pct = pct_of_total(excess_amount)
        self.no_sales_pct = pct_of_total(no_sales_amount)
        self.total_inline_pct = pct_of_total(total_inline)
        self.total_excess_pct = pct_of_total(total_excess)
        self.total_pct = Decimal("1") if total_amount > 0 else Decimal("0")

        super().save(*args, **kwargs)

    def _to_dec(self, value):
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def computed_total_inline_dollars(self):
        return self._to_dec(self.new_dollars) + self._to_dec(self.inline_dollars)

    def computed_total_excess_dollars(self):
        return self._to_dec(self.excess_dollars) + self._to_dec(self.no_sales_dollars)

    def computed_total_dollars(self):
        return self.computed_total_inline_dollars() + self.computed_total_excess_dollars()

    def _pct_of_total(self, amount):
        total = self.computed_total_dollars()
        if total <= 0:
            return Decimal("0")
        return amount / total

    def computed_total_pct(self):
        return Decimal("1") if self.computed_total_dollars() > 0 else Decimal("0")

    def computed_new_pct(self):
        return self._pct_of_total(self._to_dec(self.new_dollars))

    def computed_inline_pct(self):
        return self._pct_of_total(self._to_dec(self.inline_dollars))

    def computed_excess_pct(self):
        return self._pct_of_total(self._to_dec(self.excess_dollars))

    def computed_no_sales_pct(self):
        return self._pct_of_total(self._to_dec(self.no_sales_dollars))


# -------------------------
# Sheet: Historical_Top_20_SKUs
# -------------------------
class HistoricalTop20SKUsRow(TimeStampedModel):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    item_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # ItemNumber
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    description = models.TextField(null=True, blank=True)  # Description
    cost = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Cost
    pct_of_total = PctField()  # % of Total
    cogs = MoneyField()  # COGS
    gm = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # GM
    gm_pct = PctField()  # GM%
    wos = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # WOS
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="historical_top_20_sk_us",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'historical_top_20_sk_us'


# -------------------------
# Sheet: RM_Inventory_Metrics
# -------------------------
class RMInventoryMetricsRow(TimeStampedModel):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    ineligible_pct_of_inventory = PctField()  # IneligiblePctOfInventory
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="rm_inventory_metrics",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'rm_inventory_metrics'


# -------------------------
# Sheet: RM_Ineligible_Overview
# -------------------------
class RMIneligibleOverviewRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    slow_moving_obsolete = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Slow-Moving/Obsolete
    aged = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Aged
    off_site = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Off Site
    consigned = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Consigned
    in_transit = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # In-Transit
    damaged_non_saleable = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Damaged/Non-Saleable
    total_ineligible = MoneyField()  # Total Ineligible
    ineligible_pct_of_inventory = PctField()  # Ineligible % of Inventory
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="rm_ineligible_overview",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'rm_ineligible_overview'


# -------------------------
# Sheet: RM_Category_History
# -------------------------
class RMCategoryHistoryRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    pct_available = PctField()  # %Available
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="rm_category_history",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'rm_category_history'


# -------------------------
# Sheet: RM_Top20_History
# -------------------------
class RMTop20HistoryRow(TimeStampedModel):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    sku = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # SKU
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    description = models.TextField(null=True, blank=True)  # Description
    amount = MoneyField()  # Amount
    units = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Units
    usd_unit = MoneyField()  # $/Unit
    pct_available = PctField()  # %Available
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="rm_top20_history",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'rm_top20_history'



# -------------------------
# Sheet: WIP_Inventory_Metrics
# -------------------------
class WIPInventoryMetricsRow(TimeStampedModel):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    ineligible_pct_of_inventory = PctField()  # IneligiblePctOfInventory
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="wip_inventory_metrics",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'wip_inventory_metrics'


# -------------------------
# Sheet: WIP_Ineligible_Overview
# -------------------------
class WIPIneligibleOverviewRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    slow_moving_obsolete = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Slow-Moving/Obsolete
    aged = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Aged
    off_site = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Off Site
    consigned = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Consigned
    in_transit = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # In-Transit
    damaged_non_saleable = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Damaged/Non-Saleable
    total_ineligible = MoneyField()  # Total Ineligible
    ineligible_pct_of_inventory = PctField()  # Ineligible % of Inventory
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="wip_ineligible_overview",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'wip_ineligible_overview'


# -------------------------
# Sheet: WIP_Category_History
# -------------------------
class WIPCategoryHistoryRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    pct_available = PctField()  # %Available
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="wip_category_history",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'wip_category_history'


# -------------------------
# Sheet: WIP_Top20_History
# -------------------------
class WIPTop20HistoryRow(TimeStampedModel):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    sku = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # SKU
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    description = models.TextField(null=True, blank=True)  # Description
    amount = MoneyField()  # Amount
    units = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Units
    usd_unit = MoneyField()  # $/Unit
    pct_available = PctField()  # %Available
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="wip_top20_history",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'wip_top20_history'


# -------------------------
# Sheet: FG_Gross_Recovery_History
# -------------------------
class FGGrossRecoveryHistoryRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_gross_recovery_history_rows",
        null=True,
        blank=True,
    )
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    type = models.CharField(max_length=255, null=True, blank=True)  # Type
    cost = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Cost
    selling_price = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # SellingPrice
    gross_recovery = MoneyField()  # GrossRecovery
    pct_of_cost = PctField()  # Pct_of_Cost
    pct_of_sp = PctField()  # Pct_of_SP
    wos = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # WOS
    gm_pct = PctField()  # GM%
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="fg_gross_recovery_history",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'fg_gross_recovery_history'


# -------------------------
# Sheet: WIP_Recovery
# -------------------------
class WIPRecoveryRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    pct_available = PctField()  # %Available
    recovery_pct = PctField()  # RecoveryPct
    gross_recovery = MoneyField()  # GrossRecovery
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="wip_recovery",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'wip_recovery'


# -------------------------
# Sheet: Raw_Material_Recovery
# -------------------------
class RawMaterialRecoveryRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    pct_available = PctField()  # %Available
    recovery_pct = PctField()  # RecoveryPct
    gross_recovery = MoneyField()  # GrossRecovery
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="raw_material_recovery",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'raw_material_recovery'


# -------------------------
# Sheet: NOLV_Table
# -------------------------
class NOLVTableRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    line_item = models.CharField(max_length=255, null=True, blank=True)  # LineItem
    fg_usd = MoneyField()  # FG_$
    fg_pct_cost = PctField()  # FG_%Cost
    rm_usd = MoneyField()  # RM_$
    rm_pct_cost = PctField()  # RM_%Cost
    wip_usd = MoneyField()  # WIP_$
    wip_pct_cost = PctField()  # WIP_%Cost
    total_usd = MoneyField()  # Total_$
    total_pct_cost = PctField()  # Total_%Cost
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="nolv_table",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'nolv_table'


# -------------------------
# Sheet: Risk_Subfactors
# -------------------------
class RiskSubfactorsRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="risk_subfactors_rows",
        null=True,
        blank=True,
    )
    date = models.DateField(null=True, blank=True)  # Date
    main_category = models.CharField(max_length=255, null=True, blank=True)  # MainCategory
    sub_risk = models.CharField(max_length=255, null=True, blank=True)  # SubRisk
    risk_score = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # RiskScore
    high_impact_factor = models.CharField(max_length=255, null=True, blank=True)  # HighImpactFactor

    class Meta:
        db_table = 'risk_subfactors'


# -------------------------
# Sheet: Composite_Index
# -------------------------
class CompositeIndexRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="composite_index_rows",
        null=True,
        blank=True,
    )
    date = models.DateField(null=True, blank=True)  # Date
    overall_score = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # OverallScore
    ar_risk = MoneyField()  # AR_Risk
    inventory_risk = MoneyField()  # Inventory_Risk
    company_risk = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Company_Risk
    industry_risk = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Industry_Risk
    weight_ar = MoneyField()  # Weight_AR
    weight_inventory = MoneyField()  # Weight_Inventory
    weight_company = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Weight_Company
    weight_industry = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Weight_Industry

    class Meta:
        db_table = 'composite_index'


# -------------------------
# Sheet: Forecast
# -------------------------
class ForecastRow(TimeStampedModel):
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    period = models.DateField(null=True, blank=True)  # Period
    actual_forecast = models.CharField(max_length=255, null=True, blank=True)  # ActualForecast
    available_collateral = MoneyField()  # Available_Collateral
    loan_balance = MoneyField()  # Loan_Balance
    revolver_availability = MoneyField()  # Revolver_Availability
    net_sales = MoneyField()  # NetSales
    gross_margin_pct = PctField()  # GrossMarginPct
    ar = MoneyField()  # AR
    finished_goods = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # FinishedGoods
    raw_materials = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # RawMaterials
    work_in_process = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # WorkInProcess
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="forecast",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'forecast'

# -------------------------
# Sheet: Availability Forecast
class AvailabilityForecastRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    x = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # X
    week_1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 1
    week_2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 2
    week_3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 3
    week_4 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 4
    week_5 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 5
    week_6 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 6
    week_7 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 7
    week_8 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 8
    week_9 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 9
    week_10 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 10
    week_11 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 11
    week_12 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 12
    week_13 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 13
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="availability_forecast",
        null=True,
        blank=True,
    )
    

    class Meta:
        db_table = 'availability_forecast'


# -------------------------
# Sheet: Cash Forecast
# -------------------------
class CashForecastRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    x = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # X
    week_1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 1
    week_2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 2
    week_3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 3
    week_4 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 4
    week_5 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 5
    week_6 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 6
    week_7 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 7
    week_8 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 8
    week_9 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 9
    week_10 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 10
    week_11 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 11
    week_12 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 12
    week_13 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 13
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="cash_forecast",
        null=True,
        blank=True,
    )
    report = models.ForeignKey(
        "BorrowerReport",
        on_delete=models.CASCADE,
        related_name="%(class)s_rows",
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if not self.borrower_id and self.report_id:
            self.borrower = self.report.borrower
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'cash_forecast'
        indexes = [
            models.Index(fields=["borrower", "report"]),
        ]


# -------------------------
# Sheet: Cash Flow Forecast
# -------------------------
class CashFlowForecastRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    x = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # X
    week_1 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 1
    week_2 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 2
    week_3 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 3
    week_4 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 4
    week_5 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 5
    week_6 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 6
    week_7 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 7
    week_8 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 8
    week_9 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 9
    week_10 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 10
    week_11 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 11
    week_12 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 12
    week_13 = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Week 13
    total = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Total
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="cash_flow_forecast",
        null=True,
        blank=True,
    )
    report = models.ForeignKey(
        "BorrowerReport",
        on_delete=models.CASCADE,
        related_name="%(class)s_rows",
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if not self.borrower_id and self.report_id:
            self.borrower = self.report.borrower
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'cash_flow_forecast'
        indexes = [
            models.Index(fields=["borrower", "report"]),
        ]

# -------------------------
# Sheet: Current Week Variance
# -------------------------
class CurrentWeekVarianceRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date 
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    projected = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Projected
    actual = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Actual
    variance = MoneyField()  # Variance
    variance_pct = PctField()  # Variance %
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="current_week_variance",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'current_week_variance'


# -------------------------
# Sheet: Cummulative Variance
# -------------------------
class CummulativeVarianceRow(TimeStampedModel):
    date = models.DateField(null=True, blank=True)  # Date 
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    projected = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Projected
    actual = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Actual
    variance = MoneyField()  # Variance
    variance_pct = PctField()  # Variance %
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="cummulative_variance",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'cummulative_variance'


# -------------------------
# Sheet: Collateral Limits 
# -------------------------
class CollateralLimitsRow(TimeStampedModel):
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="collateral_limits_rows",
        null=True,
        blank=True,
    )
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    collateral_type = models.CharField(max_length=255, null=True, blank=True)  # Collateral Type 
    collateral_sub_type = models.CharField(max_length=255, null=True, blank=True)  # Collateral Sub-Type 
    usd_limit = MoneyField()  # $ Limit
    pct_limit = PctField()  # % Limit

    class Meta:
        db_table = 'collateral_limits'


# -------------------------
# Sheet: Ineligibles
# -------------------------
class IneligiblesRow(TimeStampedModel):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    collateral_type = models.CharField(max_length=255, null=True, blank=True)  # Collateral Type 
    collateral_sub_type = models.CharField(max_length=255, null=True, blank=True)  # Collateral Sub-Type 
    borrower = models.ForeignKey(
        "Borrower",
        on_delete=models.CASCADE,
        related_name="ineligibles_rows",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'ineligibles'


# -------------------------
# Uploaded Reports
# -------------------------
class ReportUpload(TimeStampedModel):
    BORROWING_BASE = "borrowing_base"
    COMPLETE_ANALYSIS = "complete_analysis"
    CASH_FLOW = "cash_flow"
    REPORT_CHOICES = [
        (BORROWING_BASE, "Borrowing Base Report"),
        (COMPLETE_ANALYSIS, "Complete Analysis Report"),
        (CASH_FLOW, "Cash Flow Report"),
    ]

    report_type = models.CharField(max_length=32, choices=REPORT_CHOICES)
    name = models.CharField(max_length=255)
    file = models.FileField(
        upload_to="reports/%Y/%m",
        validators=[FileExtensionValidator(["pdf"])],
    )

    class Meta:
        db_table = "uploaded_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_report_type_display()}: {self.name}"
