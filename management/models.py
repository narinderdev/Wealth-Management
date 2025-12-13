from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
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
    primary_naics = models.BigIntegerField(null=True, blank=True)
    website = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.company or str(self.company_id)


class Borrower(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='borrowers')
    primary_contact = models.CharField(max_length=255, null=True, blank=True)
    primary_contact_phone = models.CharField(max_length=30, null=True, blank=True)
    primary_contact_email = models.EmailField(max_length=255, null=True, blank=True)
    update_interval = models.CharField(max_length=50, null=True, blank=True)
    current_update = models.DateField(null=True, blank=True)
    previous_update = models.DateField(null=True, blank=True)
    next_update = models.DateField(null=True, blank=True)
    lender = models.CharField(max_length=255, null=True, blank=True)
    lender_id = models.BigIntegerField(null=True, blank=True)
    password = models.CharField(max_length=128, null=True, blank=True)

    def __str__(self):
        return f"{self.company} - {self.primary_contact or 'Borrower'}"

    def set_password(self, raw_password, save=True):
        self.password = make_password(raw_password)
        if save:
            self.save(update_fields=['password'])

    def check_password(self, raw_password):
        if not self.password:
            return False
        return check_password(raw_password, self.password)


class BorrowerUser(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrower_profile",
    )
    borrower = models.OneToOneField(
        Borrower,
        on_delete=models.CASCADE,
        related_name="login_user",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} -> {self.borrower.company}"


class SpecificIndividual(TimeStampedModel):
    borrower = models.ForeignKey(Borrower, on_delete=models.CASCADE, related_name='specific_individuals')
    specific_individual = models.CharField(max_length=255, null=True, blank=True)
    specific_id = models.BigIntegerField(null=True, blank=True)


class BorrowerReport(TimeStampedModel):
    """One XLSX upload = one report. All sheet rows link to this."""
    borrower = models.ForeignKey(Borrower, on_delete=models.CASCADE, related_name='reports')
    source_file = models.CharField(max_length=255, null=True, blank=True)
    report_date = models.DateField(null=True, blank=True)


class ReportRow(TimeStampedModel):
    report = models.ForeignKey(BorrowerReport, on_delete=models.CASCADE, related_name='%(class)s_rows')

    class Meta:
        abstract = True


# -------------------------
# Sheet: Borrower Overview
# -------------------------
class BorrowerOverviewRow(ReportRow):
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
class CollateralOverviewRow(ReportRow):
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

    class Meta:
        db_table = 'collateral_overview'


# -------------------------
# Sheet: Machinery & Equipment 
# -------------------------
class MachineryEquipmentRow(ReportRow):
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

    class Meta:
        db_table = 'machinery_and_equipment'


# -------------------------
# Sheet: Aging Composition
# -------------------------
class AgingCompositionRow(ReportRow):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    bucket = models.CharField(max_length=255, null=True, blank=True)  # Bucket
    pct_of_total = PctField()  # PctOfTotal
    amount = MoneyField()  # Amount

    class Meta:
        db_table = 'aging_composition'


# -------------------------
# Sheet: AR_Metrics
# -------------------------
class ARMetricsRow(ReportRow):
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
class Top20ByTotalARRow(ReportRow):
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

    class Meta:
        db_table = 'top20_by_total_ar'


# -------------------------
# Sheet: Top20_By_PastDue
# -------------------------
class Top20ByPastDueRow(ReportRow):
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

    class Meta:
        db_table = 'top20_by_past_due'


# -------------------------
# Sheet: Ineligible_Trend
# -------------------------
class IneligibleTrendRow(ReportRow):
    date = models.DateField(null=True, blank=True)  # Date
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    total_ar = MoneyField()  # Total AR
    total_ineligible = MoneyField()  # Total Ineligible
    ineligible_pct_of_ar = PctField()  # Ineligible % of AR

    class Meta:
        db_table = 'ineligible_trend'


# -------------------------
# Sheet: Ineligible_Overview
# -------------------------
class IneligibleOverviewRow(ReportRow):
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

    class Meta:
        db_table = 'ineligible_overview'


# -------------------------
# Sheet: Concentration_ADO_DSO
# -------------------------
class ConcentrationADODSORow(ReportRow):
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

    class Meta:
        db_table = 'concentration_ado_dso'


# -------------------------
# Sheet: FG_Inventory_Metrics
# -------------------------
class FGInventoryMetricsRow(ReportRow):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    ineligible_pct_of_inventory = PctField()  # IneligiblePctOfInventory

    class Meta:
        db_table = 'fg_inventory_metrics'


# -------------------------
# Sheet: FG_Ineligible_detail
# -------------------------
class FGIneligibleDetailRow(ReportRow):
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

    class Meta:
        db_table = 'fg_ineligible_detail'


# -------------------------
# Sheet: FG_Composition
# -------------------------
class FGCompositionRow(ReportRow):
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

    class Meta:
        db_table = 'fg_composition'


# -------------------------
# Sheet: FG_Inline_Category_Analysis
# -------------------------
class FGInlineCategoryAnalysisRow(ReportRow):
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

    class Meta:
        db_table = 'fg_inline_category_analysis'


# -------------------------
# Sheet: Sales_GM_Trend
# -------------------------
class SalesGMTrendRow(ReportRow):
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

    class Meta:
        db_table = 'sales_gm_trend'


# -------------------------
# Sheet: FG_Inline_Excess_By_Category
# -------------------------
class FGInlineExcessByCategoryRow(ReportRow):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    fg_available = MoneyField()  # FG_Available
    inline_dollars = MoneyField()  # Inline_Dollars
    inline_pct = PctField()  # Inline_Pct
    excess_dollars = MoneyField()  # Excess_Dollars
    excess_pct = PctField()  # Excess_Pct

    class Meta:
        db_table = 'fg_inline_excess_by_category'


# -------------------------
# Sheet: Historical_Top_20_SKUs
# -------------------------
class HistoricalTop20SKUsRow(ReportRow):
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

    class Meta:
        db_table = 'historical_top_20_sk_us'


# -------------------------
# Sheet: RM_Inventory_Metrics
# -------------------------
class RMInventoryMetricsRow(ReportRow):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    ineligible_pct_of_inventory = PctField()  # IneligiblePctOfInventory

    class Meta:
        db_table = 'rm_inventory_metrics'


# -------------------------
# Sheet: RM_Ineligible_Overview
# -------------------------
class RMIneligibleOverviewRow(ReportRow):
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

    class Meta:
        db_table = 'rm_ineligible_overview'


# -------------------------
# Sheet: RM_Category_History
# -------------------------
class RMCategoryHistoryRow(ReportRow):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    pct_available = PctField()  # %Available

    class Meta:
        db_table = 'rm_category_history'


# -------------------------
# Sheet: RM_Top20_History
# -------------------------
class RMTop20HistoryRow(ReportRow):
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

    class Meta:
        db_table = 'rm_top20_history'


# -------------------------
# Sheet: WIP_Inventory_Metrics
# -------------------------
class WIPInventoryMetricsRow(ReportRow):
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    as_of_date = models.DateField(null=True, blank=True)  # AsOfDate
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    ineligible_pct_of_inventory = PctField()  # IneligiblePctOfInventory

    class Meta:
        db_table = 'wip_inventory_metrics'


# -------------------------
# Sheet: WIP_Ineligible_Overview
# -------------------------
class WIPIneligibleOverviewRow(ReportRow):
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

    class Meta:
        db_table = 'wip_ineligible_overview'


# -------------------------
# Sheet: WIP_Category_History
# -------------------------
class WIPCategoryHistoryRow(ReportRow):
    date = models.DateField(null=True, blank=True)  # Date
    inventory_type = models.CharField(max_length=255, null=True, blank=True)  # InventoryType
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    total_inventory = MoneyField()  # TotalInventory
    ineligible_inventory = MoneyField()  # IneligibleInventory
    available_inventory = MoneyField()  # AvailableInventory
    pct_available = PctField()  # %Available

    class Meta:
        db_table = 'wip_category_history'


# -------------------------
# Sheet: WIP_Top20_History
# -------------------------
class WIPTop20HistoryRow(ReportRow):
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

    class Meta:
        db_table = 'wip_top20_history'


# -------------------------
# Sheet: FG_Gross_Recovery_History
# -------------------------
class FGGrossRecoveryHistoryRow(ReportRow):
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

    class Meta:
        db_table = 'fg_gross_recovery_history'


# -------------------------
# Sheet: WIP_Recovery
# -------------------------
class WIPRecoveryRow(ReportRow):
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

    class Meta:
        db_table = 'wip_recovery'


# -------------------------
# Sheet: Raw_Material_Recovery
# -------------------------
class RawMaterialRecoveryRow(ReportRow):
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

    class Meta:
        db_table = 'raw_material_recovery'


# -------------------------
# Sheet: NOLV_Table
# -------------------------
class NOLVTableRow(ReportRow):
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

    class Meta:
        db_table = 'nolv_table'


# -------------------------
# Sheet: Risk_Subfactors
# -------------------------
class RiskSubfactorsRow(ReportRow):
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
class CompositeIndexRow(ReportRow):
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
class ForecastRow(ReportRow):
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

    class Meta:
        db_table = 'forecast'



# -------------------------
# Sheet: Availability Forecast
# -------------------------
class AvailabilityForecastRow(ReportRow):
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

    class Meta:
        db_table = 'availability_forecast'


# -------------------------
# Sheet: Current Week Variance
# -------------------------
class CurrentWeekVarianceRow(ReportRow):
    date = models.DateField(null=True, blank=True)  # Date 
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    projected = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Projected
    actual = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Actual
    variance = MoneyField()  # Variance
    variance_pct = PctField()  # Variance %

    class Meta:
        db_table = 'current_week_variance'


# -------------------------
# Sheet: Cummulative Variance
# -------------------------
class CummulativeVarianceRow(ReportRow):
    date = models.DateField(null=True, blank=True)  # Date 
    category = models.CharField(max_length=255, null=True, blank=True)  # Category
    projected = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Projected
    actual = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)  # Actual
    variance = MoneyField()  # Variance
    variance_pct = PctField()  # Variance %

    class Meta:
        db_table = 'cummulative_variance'


# -------------------------
# Sheet: Collateral Limits 
# -------------------------
class CollateralLimitsRow(ReportRow):
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
class IneligiblesRow(ReportRow):
    division = models.CharField(max_length=255, null=True, blank=True)  # Division
    collateral_type = models.CharField(max_length=255, null=True, blank=True)  # Collateral Type 
    collateral_sub_type = models.CharField(max_length=255, null=True, blank=True)  # Collateral Sub-Type 

    class Meta:
        db_table = 'ineligibles'
