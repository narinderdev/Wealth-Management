(function () {
  const appRoot = document.getElementById('data-sheet-app');
  if (!appRoot) return;

  const bootstrap = window.CORA_DATA_SHEET || {};
  const defaultEntity = bootstrap.defaultEntity || appRoot.dataset.defaultEntity || 'companies';

  const currencyFormat = (v) => (typeof v === 'number' && !Number.isNaN(v) ? `$${v.toLocaleString()}` : '-');
  const pctFormat = (v) => (typeof v === 'number' && !Number.isNaN(v) ? `${v.toFixed(2)}%` : '-');
  const dateFormat = (v) => (v ? new Date(v).toLocaleDateString() : '-');

  const entityConfigs = {
    companies: {
      title: 'Companies',
      columns: [
        { key: 'company', label: 'Company Name' },
        { key: 'industry', label: 'Industry' },
        { key: 'primary_naics', label: 'Primary NAICS' },
        { key: 'website', label: 'Website' },
      ],
      fields: [
        { key: 'company', label: 'Company Name', type: 'text', required: true },
        { key: 'industry', label: 'Industry', type: 'text' },
        { key: 'primary_naics', label: 'Primary NAICS', type: 'number' },
        { key: 'website', label: 'Website', type: 'text' },
      ],
    },
    borrowers: {
      title: 'Borrowers',
      columns: [
        { key: 'primary_contact', label: 'Primary Contact' },
        { key: 'primary_contact_email', label: 'Email' },
        { key: 'primary_contact_phone', label: 'Phone' },
        { key: 'lender', label: 'Lender' },
        { key: 'update_interval', label: 'Update Interval' },
        { key: 'current_update', label: 'Current Update', format: dateFormat },
      ],
      fields: [
        { key: 'company', label: 'Company', type: 'text', required: true },
        { key: 'primary_contact', label: 'Primary Contact', type: 'text', required: true },
        { key: 'primary_contact_phone', label: 'Phone', type: 'text' },
        { key: 'primary_contact_email', label: 'Email', type: 'email' },
        {
          key: 'update_interval',
          label: 'Update Interval',
          type: 'select',
          options: [
            { value: 'Daily', label: 'Daily' },
            { value: 'Weekly', label: 'Weekly' },
            { value: 'Monthly', label: 'Monthly' },
            { value: 'Quarterly', label: 'Quarterly' },
          ],
        },
        { key: 'current_update', label: 'Current Update', type: 'date' },
        { key: 'previous_update', label: 'Previous Update', type: 'date' },
        { key: 'next_update', label: 'Next Update', type: 'date' },
        { key: 'lender', label: 'Lender', type: 'text' },
        { key: 'lender_id', label: 'Lender ID', type: 'number' },
      ],
    },
    specificIndividuals: {
      title: 'Specific Individuals',
      columns: [
        { key: 'specific_individual', label: 'Name' },
        { key: 'specific_id', label: 'Specific ID' },
        { key: 'borrower_id', label: 'Borrower ID' },
      ],
      fields: [
        { key: 'borrower_id', label: 'Borrower ID', type: 'text', required: true },
        { key: 'specific_individual', label: 'Name', type: 'text', required: true },
        { key: 'specific_id', label: 'Specific ID', type: 'number' },
      ],
    },
    collateralOverview: {
      title: 'Collateral Overview',
      columns: [
        { key: 'main_type', label: 'Main Type' },
        { key: 'sub_type', label: 'Sub Type' },
        { key: 'beginning_collateral', label: 'Beginning Collateral', format: currencyFormat },
        { key: 'ineligibles', label: 'Ineligibles', format: currencyFormat },
        { key: 'eligible_collateral', label: 'Eligible Collateral', format: currencyFormat },
        { key: 'nolv_pct', label: 'NOLV %', format: pctFormat },
        { key: 'net_collateral', label: 'Net Collateral', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        {
          key: 'main_type',
          label: 'Main Type',
          type: 'select',
          options: [
            { value: 'Accounts Receivable', label: 'Accounts Receivable' },
            { value: 'Inventory', label: 'Inventory' },
            { value: 'Other Collateral', label: 'Other Collateral' },
          ],
        },
        { key: 'sub_type', label: 'Sub Type', type: 'text' },
        { key: 'beginning_collateral', label: 'Beginning Collateral', type: 'number' },
        { key: 'ineligibles', label: 'Ineligibles', type: 'number' },
        { key: 'eligible_collateral', label: 'Eligible Collateral', type: 'number' },
        { key: 'nolv_pct', label: 'NOLV %', type: 'number' },
        { key: 'dilution_rate', label: 'Dilution Rate %', type: 'number' },
        { key: 'advanced_rate', label: 'Advanced Rate %', type: 'number' },
        { key: 'rate_limit', label: 'Rate Limit %', type: 'number' },
        { key: 'utilized_rate', label: 'Utilized Rate %', type: 'number' },
        { key: 'pre_reserve_collateral', label: 'Pre-Reserve Collateral', type: 'number' },
        { key: 'reserves', label: 'Reserves', type: 'number' },
        { key: 'net_collateral', label: 'Net Collateral', type: 'number' },
      ],
    },
    machineryEquipment: {
      title: 'Machinery & Equipment',
      columns: [
        { key: 'equipment_type', label: 'Equipment Type' },
        { key: 'manufacturer', label: 'Manufacturer' },
        { key: 'serial_number', label: 'Serial Number' },
        { key: 'year', label: 'Year' },
        { key: 'condition', label: 'Condition' },
        { key: 'fair_market_value', label: 'FMV', format: currencyFormat },
        { key: 'orderly_liquidation_value', label: 'OLV', format: currencyFormat },
        { key: 'estimated_fair_market_value', label: 'Est. FMV', format: currencyFormat },
        { key: 'estimated_orderly_liquidation_value', label: 'Est. OLV', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'equipment_type', label: 'Equipment Type', type: 'text', required: true },
        { key: 'manufacturer', label: 'Manufacturer', type: 'text' },
        { key: 'serial_number', label: 'Serial Number', type: 'text' },
        { key: 'year', label: 'Year', type: 'number' },
        {
          key: 'condition',
          label: 'Condition',
          type: 'select',
          options: [
            { value: 'Excellent', label: 'Excellent' },
            { value: 'Very Good', label: 'Very Good' },
            { value: 'Good', label: 'Good' },
            { value: 'Fair', label: 'Fair' },
            { value: 'Poor', label: 'Poor' },
          ],
        },
        { key: 'fair_market_value', label: 'Fair Market Value', type: 'number' },
        { key: 'orderly_liquidation_value', label: 'Orderly Liquidation Value', type: 'number' },
        { key: 'estimated_fair_market_value', label: 'Estimated Fair Market Value', type: 'number' },
        { key: 'estimated_orderly_liquidation_value', label: 'Estimated Orderly Liquidation Value', type: 'number' },
      ],
    },
    agingComposition: {
      title: 'Aging Composition',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'As Of Date', format: dateFormat },
        { key: 'bucket', label: 'Bucket' },
        { key: 'pct_of_total', label: '% of Total', format: pctFormat },
        { key: 'amount', label: 'Amount', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        {
          key: 'bucket',
          label: 'Bucket',
          type: 'select',
          options: [
            { value: 'Current', label: 'Current' },
            { value: '0-30', label: '0-30' },
            { value: '31-60', label: '31-60' },
            { value: '61-90', label: '61-90' },
            { value: '91+', label: '91+' },
          ],
        },
        { key: 'pct_of_total', label: '% of Total', type: 'number' },
        { key: 'amount', label: 'Amount', type: 'number' },
      ],
    },
    arMetrics: {
      title: 'AR Metrics',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'As Of Date', format: dateFormat },
        { key: 'balance', label: 'Balance', format: currencyFormat },
        { key: 'dso', label: 'DSO' },
        { key: 'pct_past_due', label: '% Past Due', format: pctFormat },
        { key: 'current_amt', label: 'Current Amt', format: currencyFormat },
        { key: 'past_due_amt', label: 'Past Due Amt', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'balance', label: 'Balance', type: 'number' },
        { key: 'dso', label: 'DSO', type: 'number' },
        { key: 'pct_past_due', label: '% Past Due', type: 'number' },
        { key: 'current_amt', label: 'Current Amount', type: 'number' },
        { key: 'past_due_amt', label: 'Past Due Amount', type: 'number' },
      ],
    },
    ineligibleTrend: {
      title: 'Ineligible Trend',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'total_ar', label: 'Total AR', format: currencyFormat },
        { key: 'total_ineligible', label: 'Total Ineligible', format: currencyFormat },
        { key: 'ineligible_pct_of_ar', label: 'Ineligible % of AR', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'total_ar', label: 'Total AR', type: 'number' },
        { key: 'total_ineligible', label: 'Total Ineligible', type: 'number' },
        { key: 'ineligible_pct_of_ar', label: 'Ineligible % of AR', type: 'number' },
      ],
    },
    ineligibleOverview: {
      title: 'Ineligible Overview',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'past_due_gt_90_days', label: 'Past Due >90', format: currencyFormat },
        { key: 'dilution', label: 'Dilution', format: currencyFormat },
        { key: 'total_ineligible', label: 'Total Ineligible', format: currencyFormat },
        { key: 'ineligible_pct_of_ar', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'past_due_gt_90_days', label: 'Past Due >90 Days', type: 'number' },
        { key: 'dilution', label: 'Dilution', type: 'number' },
        { key: 'cross_age', label: 'Cross Age', type: 'number' },
        { key: 'concentration_over_cap', label: 'Concentration Over Cap', type: 'number' },
        { key: 'foreign', label: 'Foreign', type: 'number' },
        { key: 'government', label: 'Government', type: 'number' },
        { key: 'intercompany', label: 'Intercompany', type: 'number' },
        { key: 'contra', label: 'Contra', type: 'number' },
        { key: 'other', label: 'Other', type: 'number' },
        { key: 'total_ineligible', label: 'Total Ineligible', type: 'number' },
        { key: 'ineligible_pct_of_ar', label: 'Ineligible % of AR', type: 'number' },
      ],
    },
    concentrationADODSO: {
      title: 'Concentration ADO/DSO',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'customer', label: 'Customer' },
        { key: 'current_concentration_pct', label: 'Concentration %', format: pctFormat },
        { key: 'current_ado_days', label: 'ADO Days' },
        { key: 'current_dso_days', label: 'DSO Days' },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'customer', label: 'Customer', type: 'text', required: true },
        { key: 'current_concentration_pct', label: 'Current Concentration %', type: 'number' },
        { key: 'avg_ttm_concentration_pct', label: 'Avg TTM Concentration %', type: 'number' },
        { key: 'variance_concentration_pp', label: 'Variance Concentration (pp)', type: 'number' },
        { key: 'current_ado_days', label: 'Current ADO Days', type: 'number' },
        { key: 'avg_ttm_ado_days', label: 'Avg TTM ADO Days', type: 'number' },
        { key: 'variance_ado_days', label: 'Variance ADO Days', type: 'number' },
        { key: 'current_dso_days', label: 'Current DSO Days', type: 'number' },
        { key: 'avg_ttm_dso_days', label: 'Avg TTM DSO Days', type: 'number' },
        { key: 'variance_dso_days', label: 'Variance DSO Days', type: 'number' },
      ],
    },
    fgInventoryMetrics: {
      title: 'FG Inventory Metrics',
      columns: [
        { key: 'inventory_type', label: 'Type' },
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'Date', format: dateFormat },
        { key: 'total_inventory', label: 'Total Inventory', format: currencyFormat },
        { key: 'ineligible_inventory', label: 'Ineligible', format: currencyFormat },
        { key: 'available_inventory', label: 'Available', format: currencyFormat },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible % of Inventory', type: 'number' },
      ],
    },
    fgIneligibleDetail: {
      title: 'FG Ineligible Detail',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'slow_moving_obsolete', label: 'Slow Moving', format: currencyFormat },
        { key: 'total_ineligible', label: 'Total Ineligible', format: currencyFormat },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'slow_moving_obsolete', label: 'Slow-Moving/Obsolete', type: 'number' },
        { key: 'aged', label: 'Aged', type: 'number' },
        { key: 'off_site', label: 'Off Site', type: 'number' },
        { key: 'consigned', label: 'Consigned', type: 'number' },
        { key: 'in_transit', label: 'In-Transit', type: 'number' },
        { key: 'damaged_non_saleable', label: 'Damaged/Non-Saleable', type: 'number' },
        { key: 'total_ineligible', label: 'Total Ineligible', type: 'number' },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible % of Inventory', type: 'number' },
      ],
    },
    fgComposition: {
      title: 'FG Composition',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'Date', format: dateFormat },
        { key: 'fg_available', label: 'FG Available', format: currencyFormat },
        { key: 'inline_pct', label: 'Inline %', format: pctFormat },
        { key: 'excess_pct', label: 'Excess %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'fg_available', label: 'FG Available', type: 'number' },
        { key: 'fg_0_13', label: 'FG 0-13 Weeks', type: 'number' },
        { key: 'fg_13_26', label: 'FG 13-26 Weeks', type: 'number' },
        { key: 'fg_26_39', label: 'FG 26-39 Weeks', type: 'number' },
        { key: 'fg_39_52', label: 'FG 39-52 Weeks', type: 'number' },
        { key: 'fg_52_plus', label: 'FG 52+ Weeks', type: 'number' },
        { key: 'fg_no_sales', label: 'FG No Sales', type: 'number' },
        { key: 'inline_pct', label: 'Inline %', type: 'number' },
        { key: 'excess_pct', label: 'Excess %', type: 'number' },
      ],
    },
    fgInlineCategoryAnalysis: {
      title: 'FG Inline Category Analysis',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'fg_total', label: 'FG Total', format: currencyFormat },
        { key: 'fg_available', label: 'FG Available', format: currencyFormat },
        { key: 'gm_pct', label: 'GM %', format: pctFormat },
        { key: 'weeks_of_supply', label: 'WOS' },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'fg_total', label: 'FG Total', type: 'number' },
        { key: 'fg_ineligible', label: 'FG Ineligible', type: 'number' },
        { key: 'fg_available', label: 'FG Available', type: 'number' },
        { key: 'pct_of_available', label: '% of Available', type: 'number' },
        { key: 'sales', label: 'Sales', type: 'number' },
        { key: 'cogs', label: 'COGS', type: 'number' },
        { key: 'gm', label: 'GM', type: 'number' },
        { key: 'gm_pct', label: 'GM %', type: 'number' },
        { key: 'weeks_of_supply', label: 'Weeks of Supply', type: 'number' },
      ],
    },
    salesGMTrend: {
      title: 'Sales/GM Trend',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'Date', format: dateFormat },
        { key: 'net_sales', label: 'Net Sales', format: currencyFormat },
        { key: 'gross_margin_pct', label: 'GM %', format: pctFormat },
        { key: 'gross_margin_dollars', label: 'GM $', format: currencyFormat },
        { key: 'ttm_sales', label: 'TTM Sales', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'net_sales', label: 'Net Sales', type: 'number' },
        { key: 'gross_margin_pct', label: 'Gross Margin %', type: 'number' },
        { key: 'gross_margin_dollars', label: 'Gross Margin $', type: 'number' },
        { key: 'ttm_sales', label: 'TTM Sales', type: 'number' },
        { key: 'ttm_sales_prior', label: 'TTM Sales Prior', type: 'number' },
        { key: 'trend_ttm_pct', label: 'Trend TTM %', type: 'number' },
        { key: 'ma3', label: 'MA3', type: 'number' },
        { key: 'ma3_prior', label: 'MA3 Prior', type: 'number' },
        { key: 'trend_3_m_pct', label: 'Trend 3M %', type: 'number' },
      ],
    },
    fgInlineExcessByCategory: {
      title: 'FG Inline Excess By Category',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'fg_available', label: 'FG Available', format: currencyFormat },
        { key: 'inline_dollars', label: 'Inline $', format: currencyFormat },
        { key: 'inline_pct', label: 'Inline %', format: pctFormat },
        { key: 'excess_dollars', label: 'Excess $', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'fg_available', label: 'FG Available', type: 'number' },
        { key: 'inline_dollars', label: 'Inline Dollars', type: 'number' },
        { key: 'inline_pct', label: 'Inline %', type: 'number' },
        { key: 'excess_dollars', label: 'Excess Dollars', type: 'number' },
        { key: 'excess_pct', label: 'Excess %', type: 'number' },
      ],
    },
    rmInventoryMetrics: {
      title: 'RM Inventory Metrics',
      columns: [
        { key: 'inventory_type', label: 'Type' },
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'Date', format: dateFormat },
        { key: 'total_inventory', label: 'Total', format: currencyFormat },
        { key: 'available_inventory', label: 'Available', format: currencyFormat },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', type: 'number' },
      ],
    },
    rmIneligibleOverview: {
      title: 'RM Ineligible Overview',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'slow_moving_obsolete', label: 'Slow Moving', format: currencyFormat },
        { key: 'total_ineligible', label: 'Total Ineligible', format: currencyFormat },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'slow_moving_obsolete', label: 'Slow-Moving/Obsolete', type: 'number' },
        { key: 'aged', label: 'Aged', type: 'number' },
        { key: 'off_site', label: 'Off Site', type: 'number' },
        { key: 'consigned', label: 'Consigned', type: 'number' },
        { key: 'in_transit', label: 'In-Transit', type: 'number' },
        { key: 'damaged_non_saleable', label: 'Damaged/Non-Saleable', type: 'number' },
        { key: 'total_ineligible', label: 'Total Ineligible', type: 'number' },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', type: 'number' },
      ],
    },
    rmCategoryHistory: {
      title: 'RM Category History',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'total_inventory', label: 'Total', format: currencyFormat },
        { key: 'available_inventory', label: 'Available', format: currencyFormat },
        { key: 'pct_available', label: 'Available %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'pct_available', label: '% Available', type: 'number' },
      ],
    },
    wipInventoryMetrics: {
      title: 'WIP Inventory Metrics',
      columns: [
        { key: 'inventory_type', label: 'Type' },
        { key: 'division', label: 'Division' },
        { key: 'as_of_date', label: 'Date', format: dateFormat },
        { key: 'total_inventory', label: 'Total', format: currencyFormat },
        { key: 'available_inventory', label: 'Available', format: currencyFormat },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', type: 'number' },
      ],
    },
    wipIneligibleOverview: {
      title: 'WIP Ineligible Overview',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'slow_moving_obsolete', label: 'Slow Moving', format: currencyFormat },
        { key: 'total_ineligible', label: 'Total Ineligible', format: currencyFormat },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'slow_moving_obsolete', label: 'Slow-Moving/Obsolete', type: 'number' },
        { key: 'aged', label: 'Aged', type: 'number' },
        { key: 'off_site', label: 'Off Site', type: 'number' },
        { key: 'consigned', label: 'Consigned', type: 'number' },
        { key: 'in_transit', label: 'In-Transit', type: 'number' },
        { key: 'damaged_non_saleable', label: 'Damaged/Non-Saleable', type: 'number' },
        { key: 'total_ineligible', label: 'Total Ineligible', type: 'number' },
        { key: 'ineligible_pct_of_inventory', label: 'Ineligible %', type: 'number' },
      ],
    },
    wipCategoryHistory: {
      title: 'WIP Category History',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'total_inventory', label: 'Total', format: currencyFormat },
        { key: 'available_inventory', label: 'Available', format: currencyFormat },
        { key: 'pct_available', label: 'Available %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'pct_available', label: '% Available', type: 'number' },
      ],
    },
    fgGrossRecoveryHistory: {
      title: 'FG Gross Recovery History',
      columns: [
        { key: 'as_of_date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'cost', label: 'Cost', format: currencyFormat },
        { key: 'gross_recovery', label: 'Gross Recovery', format: currencyFormat },
        { key: 'pct_of_cost', label: '% of Cost', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'category', label: 'Category', type: 'text' },
        { key: 'type', label: 'Type', type: 'text' },
        { key: 'cost', label: 'Cost', type: 'number' },
        { key: 'selling_price', label: 'Selling Price', type: 'number' },
        { key: 'gross_recovery', label: 'Gross Recovery', type: 'number' },
        { key: 'pct_of_cost', label: '% of Cost', type: 'number' },
        { key: 'pct_of_sp', label: '% of SP', type: 'number' },
        { key: 'wos', label: 'WOS', type: 'number' },
        { key: 'gm_pct', label: 'GM %', type: 'number' },
      ],
    },
    wipRecovery: {
      title: 'WIP Recovery',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'total_inventory', label: 'Total', format: currencyFormat },
        { key: 'gross_recovery', label: 'Gross Recovery', format: currencyFormat },
        { key: 'recovery_pct', label: 'Recovery %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'category', label: 'Category', type: 'text' },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'pct_available', label: '% Available', type: 'number' },
        { key: 'recovery_pct', label: 'Recovery %', type: 'number' },
        { key: 'gross_recovery', label: 'Gross Recovery', type: 'number' },
      ],
    },
    rawMaterialRecovery: {
      title: 'Raw Material Recovery',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'category', label: 'Category' },
        { key: 'total_inventory', label: 'Total', format: currencyFormat },
        { key: 'gross_recovery', label: 'Gross Recovery', format: currencyFormat },
        { key: 'recovery_pct', label: 'Recovery %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'inventory_type', label: 'Inventory Type', type: 'text' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'category', label: 'Category', type: 'text' },
        { key: 'total_inventory', label: 'Total Inventory', type: 'number' },
        { key: 'ineligible_inventory', label: 'Ineligible Inventory', type: 'number' },
        { key: 'available_inventory', label: 'Available Inventory', type: 'number' },
        { key: 'pct_available', label: '% Available', type: 'number' },
        { key: 'recovery_pct', label: 'Recovery %', type: 'number' },
        { key: 'gross_recovery', label: 'Gross Recovery', type: 'number' },
      ],
    },
    nolvTable: {
      title: 'NOLV Table',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'division', label: 'Division' },
        { key: 'line_item', label: 'Line Item' },
        { key: 'fg_usd', label: 'FG $', format: currencyFormat },
        { key: 'rm_usd', label: 'RM $', format: currencyFormat },
        { key: 'wip_usd', label: 'WIP $', format: currencyFormat },
        { key: 'total_usd', label: 'Total $', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'line_item', label: 'Line Item', type: 'text', required: true },
        { key: 'fg_usd', label: 'FG $', type: 'number' },
        { key: 'fg_pct_cost', label: 'FG % Cost', type: 'number' },
        { key: 'rm_usd', label: 'RM $', type: 'number' },
        { key: 'rm_pct_cost', label: 'RM % Cost', type: 'number' },
        { key: 'wip_usd', label: 'WIP $', type: 'number' },
        { key: 'wip_pct_cost', label: 'WIP % Cost', type: 'number' },
        { key: 'total_usd', label: 'Total $', type: 'number' },
        { key: 'total_pct_cost', label: 'Total % Cost', type: 'number' },
      ],
    },
    riskSubfactors: {
      title: 'Risk Subfactors',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'main_category', label: 'Main Category' },
        { key: 'sub_risk', label: 'Sub Risk' },
        { key: 'risk_score', label: 'Risk Score' },
        { key: 'high_impact_factor', label: 'High Impact Factor' },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'main_category', label: 'Main Category', type: 'text', required: true },
        { key: 'sub_risk', label: 'Sub Risk', type: 'text' },
        { key: 'risk_score', label: 'Risk Score', type: 'number' },
        { key: 'high_impact_factor', label: 'High Impact Factor', type: 'text' },
      ],
    },
    compositeIndex: {
      title: 'Composite Index',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'overall_score', label: 'Overall Score' },
        { key: 'ar_risk', label: 'AR Risk' },
        { key: 'inventory_risk', label: 'Inventory Risk' },
        { key: 'company_risk', label: 'Company Risk' },
        { key: 'industry_risk', label: 'Industry Risk' },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'overall_score', label: 'Overall Score', type: 'number' },
        { key: 'ar_risk', label: 'AR Risk', type: 'number' },
        { key: 'inventory_risk', label: 'Inventory Risk', type: 'number' },
        { key: 'company_risk', label: 'Company Risk', type: 'number' },
        { key: 'industry_risk', label: 'Industry Risk', type: 'number' },
        { key: 'weight_ar', label: 'Weight AR', type: 'number' },
        { key: 'weight_inventory', label: 'Weight Inventory', type: 'number' },
        { key: 'weight_company', label: 'Weight Company', type: 'number' },
        { key: 'weight_industry', label: 'Weight Industry', type: 'number' },
      ],
    },
    forecast: {
      title: 'Forecast',
      columns: [
        { key: 'as_of_date', label: 'As Of Date', format: dateFormat },
        { key: 'period', label: 'Period', format: dateFormat },
        { key: 'actual_forecast', label: 'Actual/Forecast' },
        { key: 'available_collateral', label: 'Available Collateral', format: currencyFormat },
        { key: 'loan_balance', label: 'Loan Balance', format: currencyFormat },
        { key: 'revolver_availability', label: 'Revolver Availability', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'as_of_date', label: 'As Of Date', type: 'date' },
        { key: 'period', label: 'Period', type: 'date' },
        {
          key: 'actual_forecast',
          label: 'Actual/Forecast',
          type: 'select',
          options: [
            { value: 'Actual', label: 'Actual' },
            { value: 'Forecast', label: 'Forecast' },
          ],
        },
        { key: 'available_collateral', label: 'Available Collateral', type: 'number' },
        { key: 'loan_balance', label: 'Loan Balance', type: 'number' },
        { key: 'revolver_availability', label: 'Revolver Availability', type: 'number' },
        { key: 'net_sales', label: 'Net Sales', type: 'number' },
        { key: 'gross_margin_pct', label: 'Gross Margin %', type: 'number' },
        { key: 'ar', label: 'AR', type: 'number' },
        { key: 'finished_goods', label: 'Finished Goods', type: 'number' },
        { key: 'raw_materials', label: 'Raw Materials', type: 'number' },
        { key: 'work_in_process', label: 'Work In Process', type: 'number' },
      ],
    },
    availabilityForecast: {
      title: 'Availability Forecast',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'category', label: 'Category' },
        { key: 'week_1', label: 'Week 1', format: currencyFormat },
        { key: 'week_2', label: 'Week 2', format: currencyFormat },
        { key: 'week_3', label: 'Week 3', format: currencyFormat },
        { key: 'week_4', label: 'Week 4', format: currencyFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'x', label: 'X', type: 'number' },
        { key: 'week_1', label: 'Week 1', type: 'number' },
        { key: 'week_2', label: 'Week 2', type: 'number' },
        { key: 'week_3', label: 'Week 3', type: 'number' },
        { key: 'week_4', label: 'Week 4', type: 'number' },
        { key: 'week_5', label: 'Week 5', type: 'number' },
        { key: 'week_6', label: 'Week 6', type: 'number' },
        { key: 'week_7', label: 'Week 7', type: 'number' },
        { key: 'week_8', label: 'Week 8', type: 'number' },
        { key: 'week_9', label: 'Week 9', type: 'number' },
        { key: 'week_10', label: 'Week 10', type: 'number' },
        { key: 'week_11', label: 'Week 11', type: 'number' },
        { key: 'week_12', label: 'Week 12', type: 'number' },
        { key: 'week_13', label: 'Week 13', type: 'number' },
      ],
    },
    currentWeekVariance: {
      title: 'Current Week Variance',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'category', label: 'Category' },
        { key: 'projected', label: 'Projected', format: currencyFormat },
        { key: 'actual', label: 'Actual', format: currencyFormat },
        { key: 'variance', label: 'Variance', format: currencyFormat },
        { key: 'variance_pct', label: 'Variance %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'projected', label: 'Projected', type: 'number' },
        { key: 'actual', label: 'Actual', type: 'number' },
        { key: 'variance', label: 'Variance', type: 'number' },
        { key: 'variance_pct', label: 'Variance %', type: 'number' },
      ],
    },
    cumulativeVariance: {
      title: 'Cumulative Variance',
      columns: [
        { key: 'date', label: 'Date', format: dateFormat },
        { key: 'category', label: 'Category' },
        { key: 'projected', label: 'Projected', format: currencyFormat },
        { key: 'actual', label: 'Actual', format: currencyFormat },
        { key: 'variance', label: 'Variance', format: currencyFormat },
        { key: 'variance_pct', label: 'Variance %', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'date', label: 'Date', type: 'date' },
        { key: 'category', label: 'Category', type: 'text', required: true },
        { key: 'projected', label: 'Projected', type: 'number' },
        { key: 'actual', label: 'Actual', type: 'number' },
        { key: 'variance', label: 'Variance', type: 'number' },
        { key: 'variance_pct', label: 'Variance %', type: 'number' },
      ],
    },
    collateralLimits: {
      title: 'Collateral Limits',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'collateral_type', label: 'Collateral Type' },
        { key: 'collateral_sub_type', label: 'Sub Type' },
        { key: 'usd_limit', label: '$ Limit', format: currencyFormat },
        { key: 'pct_limit', label: '% Limit', format: pctFormat },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'collateral_type', label: 'Collateral Type', type: 'text', required: true },
        { key: 'collateral_sub_type', label: 'Collateral Sub-Type', type: 'text' },
        { key: 'usd_limit', label: '$ Limit', type: 'number' },
        { key: 'pct_limit', label: '% Limit', type: 'number' },
      ],
    },
    ineligibles: {
      title: 'Ineligibles Configuration',
      columns: [
        { key: 'division', label: 'Division' },
        { key: 'collateral_type', label: 'Collateral Type' },
        { key: 'collateral_sub_type', label: 'Sub Type' },
      ],
      fields: [
        { key: 'report_id', label: 'Report ID', type: 'text', required: true },
        { key: 'division', label: 'Division', type: 'text' },
        { key: 'collateral_type', label: 'Collateral Type', type: 'text', required: true },
        { key: 'collateral_sub_type', label: 'Collateral Sub-Type', type: 'text' },
      ],
    },
  };

  const initialData = {
    companies: [
      {
        id: '1',
        company: 'BrightNest Consumer Brands',
        company_id: 987654321,
        industry: 'Consumer Goods',
        primary_naics: 448410,
        website: 'www.brightnest.com',
      },
    ],
    borrowers: [
      {
        id: '1',
        company_id: '1',
        primary_contact: 'Billy Bob',
        primary_contact_phone: '401-321-7654',
        primary_contact_email: 'bbob@DEF.com',
        update_interval: 'Monthly',
        current_update: '2025-11-28',
        previous_update: '2025-10-31',
        next_update: '2025-12-31',
        lender: 'J.P. Morgan Chase',
        lender_id: 67891,
      },
    ],
    specificIndividuals: [
      { id: '1', borrower_id: '1', specific_individual: 'Alex Parisi', specific_id: 456 },
    ],
    borrowerReports: [
      { id: '1', borrower_id: '1', source_file: 'Report_Nov2025.xlsx', report_date: '2025-11-28' },
    ],
    collateralOverview: [
      {
        id: '1',
        report_id: '1',
        main_type: 'Accounts Receivable',
        sub_type: 'Accounts Receivable',
        beginning_collateral: 24026412,
        ineligibles: -2599692,
        eligible_collateral: 21426721,
        nolv_pct: 90,
        dilution_rate: 100,
        advanced_rate: 90,
        rate_limit: 90,
        utilized_rate: 90,
        pre_reserve_collateral: 19284049,
        reserves: -1748857,
        net_collateral: 17535192,
      },
      {
        id: '2',
        report_id: '1',
        main_type: 'Inventory',
        sub_type: 'Finished Goods',
        beginning_collateral: 17244592,
        ineligibles: -1379567,
        eligible_collateral: 15865024,
        nolv_pct: 64.3,
        dilution_rate: 85,
        advanced_rate: 54.6,
        rate_limit: 100,
        utilized_rate: 54.6,
        pre_reserve_collateral: 8667214,
        reserves: 0,
        net_collateral: 8667214,
      },
    ],
    machineryEquipment: [
      {
        id: '1',
        report_id: '1',
        equipment_type: 'Ribbon Blender',
        manufacturer: 'Munson',
        serial_number: 'MUNS-85013',
        year: 2019,
        condition: 'Good',
        fair_market_value: 319810,
        orderly_liquidation_value: 248940,
      },
      {
        id: '2',
        report_id: '1',
        equipment_type: 'Mixing Kettle',
        manufacturer: 'Lee',
        serial_number: 'LEE-93336',
        year: 2021,
        condition: 'Good',
        fair_market_value: 845620,
        orderly_liquidation_value: 631890,
      },
    ],
    agingComposition: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        bucket: 'Current',
        pct_of_total: 65,
        amount: 15617168,
      },
      {
        id: '2',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        bucket: '0-30',
        pct_of_total: 20,
        amount: 4805282,
      },
    ],
    arMetrics: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        balance: 24026412,
        dso: 45.2,
        pct_past_due: 15,
        current_amt: 20422450,
        past_due_amt: 3603962,
      },
    ],
    ineligibleTrend: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        division: 'Main',
        total_ar: 24026412,
        total_ineligible: 2599692,
        ineligible_pct_of_ar: 10.82,
      },
    ],
    ineligibleOverview: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        division: 'Main',
        past_due_gt_90_days: 1200000,
        dilution: 350000,
        cross_age: 200000,
        concentration_over_cap: 400000,
        foreign: 150000,
        government: 0,
        intercompany: 100000,
        contra: 50000,
        other: 149692,
        total_ineligible: 2599692,
        ineligible_pct_of_ar: 10.82,
      },
    ],
    concentrationADODSO: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        customer: 'ABC Corp',
        current_concentration_pct: 12.5,
        avg_ttm_concentration_pct: 11.8,
        variance_concentration_pp: 0.7,
        current_ado_days: 42,
        avg_ttm_ado_days: 40,
        variance_ado_days: 2,
        current_dso_days: 45,
        avg_ttm_dso_days: 43,
        variance_dso_days: 2,
      },
    ],
    fgInventoryMetrics: [
      {
        id: '1',
        report_id: '1',
        inventory_type: 'FG',
        division: 'Main',
        as_of_date: '2025-11-28',
        total_inventory: 17244592,
        ineligible_inventory: 1379567,
        available_inventory: 15865024,
        ineligible_pct_of_inventory: 8,
      },
    ],
    fgIneligibleDetail: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'FG',
        division: 'Main',
        slow_moving_obsolete: 500000,
        aged: 300000,
        off_site: 200000,
        consigned: 100000,
        in_transit: 150000,
        damaged_non_saleable: 129567,
        total_ineligible: 1379567,
        ineligible_pct_of_inventory: 8,
      },
    ],
    fgComposition: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        fg_available: 15865024,
        fg_0_13: 8000000,
        fg_13_26: 4000000,
        fg_26_39: 2000000,
        fg_39_52: 1000000,
        fg_52_plus: 500000,
        fg_no_sales: 365024,
        inline_pct: 75,
        excess_pct: 25,
      },
    ],
    fgInlineCategoryAnalysis: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        category: 'Electronics',
        fg_total: 5000000,
        fg_ineligible: 400000,
        fg_available: 4600000,
        pct_of_available: 29,
        sales: 12000000,
        cogs: 8400000,
        gm: 3600000,
        gm_pct: 30,
        weeks_of_supply: 28.5,
      },
    ],
    salesGMTrend: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        net_sales: 3500000,
        gross_margin_pct: 32,
        gross_margin_dollars: 1120000,
        ttm_sales: 42000000,
        ttm_sales_prior: 40000000,
        trend_ttm_pct: 5,
        ma3: 3400000,
        ma3_prior: 3300000,
        trend_3_m_pct: 3,
      },
    ],
    fgInlineExcessByCategory: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        as_of_date: '2025-11-28',
        category: 'Electronics',
        fg_available: 4600000,
        inline_dollars: 3450000,
        inline_pct: 75,
        excess_dollars: 1150000,
        excess_pct: 25,
      },
    ],
    rmInventoryMetrics: [
      {
        id: '1',
        report_id: '1',
        inventory_type: 'RM',
        division: 'Main',
        as_of_date: '2025-11-28',
        total_inventory: 8427622,
        ineligible_inventory: 1531374,
        available_inventory: 6896248,
        ineligible_pct_of_inventory: 18.2,
      },
    ],
    rmIneligibleOverview: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'RM',
        division: 'Main',
        slow_moving_obsolete: 600000,
        aged: 400000,
        off_site: 200000,
        consigned: 100000,
        in_transit: 150000,
        damaged_non_saleable: 81374,
        total_ineligible: 1531374,
        ineligible_pct_of_inventory: 18.2,
      },
    ],
    rmCategoryHistory: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'RM',
        division: 'Main',
        category: 'Metals',
        total_inventory: 3000000,
        ineligible_inventory: 500000,
        available_inventory: 2500000,
        pct_available: 83.3,
      },
    ],
    wipInventoryMetrics: [
      {
        id: '1',
        report_id: '1',
        inventory_type: 'WIP',
        division: 'Main',
        as_of_date: '2025-11-28',
        total_inventory: 2964502,
        ineligible_inventory: 507921,
        available_inventory: 2456581,
        ineligible_pct_of_inventory: 17.1,
      },
    ],
    wipIneligibleOverview: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'WIP',
        division: 'Main',
        slow_moving_obsolete: 200000,
        aged: 150000,
        off_site: 50000,
        consigned: 30000,
        in_transit: 40000,
        damaged_non_saleable: 37921,
        total_ineligible: 507921,
        ineligible_pct_of_inventory: 17.1,
      },
    ],
    wipCategoryHistory: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'WIP',
        division: 'Main',
        category: 'Assembly',
        total_inventory: 1500000,
        ineligible_inventory: 250000,
        available_inventory: 1250000,
        pct_available: 83.3,
      },
    ],
    fgGrossRecoveryHistory: [
      {
        id: '1',
        report_id: '1',
        as_of_date: '2025-11-28',
        division: 'Main',
        category: 'Electronics',
        type: 'Standard',
        cost: 5000000,
        selling_price: 7500000,
        gross_recovery: 4800000,
        pct_of_cost: 96,
        pct_of_sp: 64,
        wos: 12,
        gm_pct: 33,
      },
    ],
    wipRecovery: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'WIP',
        division: 'Main',
        category: 'Assembly',
        total_inventory: 1500000,
        ineligible_inventory: 250000,
        available_inventory: 1250000,
        pct_available: 83.3,
        recovery_pct: 45,
        gross_recovery: 562500,
      },
    ],
    rawMaterialRecovery: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        inventory_type: 'RM',
        division: 'Main',
        category: 'Metals',
        total_inventory: 3000000,
        ineligible_inventory: 500000,
        available_inventory: 2500000,
        pct_available: 83.3,
        recovery_pct: 60,
        gross_recovery: 1500000,
      },
    ],
    nolvTable: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        division: 'Main',
        line_item: 'Available Inventory',
        fg_usd: 15865024,
        fg_pct_cost: 92,
        rm_usd: 6896248,
        rm_pct_cost: 81.8,
        wip_usd: 2456581,
        wip_pct_cost: 82.9,
        total_usd: 25217853,
        total_pct_cost: 88.1,
      },
    ],
    riskSubfactors: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        main_category: 'Credit Risk',
        sub_risk: 'Customer Concentration',
        risk_score: 7.2,
        high_impact_factor: 'Top 5 customers >40%',
      },
    ],
    compositeIndex: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        overall_score: 72,
        ar_risk: 6.5,
        inventory_risk: 7.0,
        company_risk: 6.8,
        industry_risk: 5.5,
        weight_ar: 0.35,
        weight_inventory: 0.3,
        weight_company: 0.2,
        weight_industry: 0.15,
      },
    ],
    forecast: [
      {
        id: '1',
        report_id: '1',
        as_of_date: '2025-11-28',
        period: '2025-12-31',
        actual_forecast: 'Forecast',
        available_collateral: 43879560,
        loan_balance: 35000000,
        revolver_availability: 8879560,
        net_sales: 3800000,
        gross_margin_pct: 33,
        ar: 25000000,
        finished_goods: 18000000,
        raw_materials: 8500000,
        work_in_process: 3000000,
      },
    ],
    availabilityForecast: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        category: 'Total Availability',
        x: 1,
        week_1: 43500000,
        week_2: 44000000,
        week_3: 44500000,
        week_4: 45000000,
        week_5: 45500000,
        week_6: 46000000,
        week_7: 46500000,
        week_8: 47000000,
        week_9: 47500000,
        week_10: 48000000,
        week_11: 48500000,
        week_12: 49000000,
        week_13: 49500000,
      },
    ],
    currentWeekVariance: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        category: 'AR',
        projected: 24500000,
        actual: 24026412,
        variance: -473588,
        variance_pct: -1.93,
      },
    ],
    cumulativeVariance: [
      {
        id: '1',
        report_id: '1',
        date: '2025-11-28',
        category: 'AR',
        projected: 24500000,
        actual: 24026412,
        variance: -473588,
        variance_pct: -1.93,
      },
    ],
    collateralLimits: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        collateral_type: 'Accounts Receivable',
        collateral_sub_type: 'Trade AR',
        usd_limit: 30000000,
        pct_limit: 90,
      },
    ],
    ineligibles: [
      {
        id: '1',
        report_id: '1',
        division: 'Main',
        collateral_type: 'Accounts Receivable',
        collateral_sub_type: 'Past Due >90',
      },
    ],
  };

  const environment = {
    modalRoot: document.getElementById('ds-modal-root'),
    toastRoot: document.getElementById('ds-toast-root'),
    confirmFn:
      (window.CORA && window.CORA.confirm && ((opts) => window.CORA.confirm(opts))) ||
      ((opts) => Promise.resolve(window.confirm(opts.message))),
  };

  const state = {
    currentEntity: entityConfigs[defaultEntity] ? defaultEntity : 'companies',
  };

  const componentCache = {};
  let activeComponent = null;
  let activeStyleNode = null;

  const entityGroupMap = {
    companies: 'core',
    borrowers: 'core',
    specificIndividuals: 'core',
    borrowerReports: 'core',
    collateralOverview: 'receivables',
    machineryEquipment: 'receivables',
    agingComposition: 'receivables',
    arMetrics: 'receivables',
    ineligibleTrend: 'receivables',
    ineligibleOverview: 'receivables',
    concentrationADODSO: 'receivables',
    fgInventoryMetrics: 'inventoryFG',
    fgIneligibleDetail: 'inventoryFG',
    fgComposition: 'inventoryFG',
    fgInlineCategoryAnalysis: 'inventoryFG',
    salesGMTrend: 'inventoryFG',
    fgInlineExcessByCategory: 'inventoryFG',
    rmInventoryMetrics: 'inventoryRM',
    rmIneligibleOverview: 'inventoryRM',
    rmCategoryHistory: 'inventoryRM',
    wipInventoryMetrics: 'inventoryWIP',
    wipIneligibleOverview: 'inventoryWIP',
    wipCategoryHistory: 'inventoryWIP',
    fgGrossRecoveryHistory: 'recovery',
    wipRecovery: 'recovery',
    rawMaterialRecovery: 'recovery',
    nolvTable: 'risk',
    riskSubfactors: 'risk',
    compositeIndex: 'risk',
    forecast: 'forecast',
    availabilityForecast: 'forecast',
    currentWeekVariance: 'forecast',
    cumulativeVariance: 'forecast',
    collateralLimits: 'settings',
    ineligibles: 'settings',
  };

  const groupMeta = {
    core: {
      label: 'Core Entities',
      description: 'Maintain the foundational company and borrower records for this workspace.',
      color: '#2563eb',
    },
    receivables: {
      label: 'Accounts Receivable',
      description: 'Review collateral, ineligibles, and trend data powering AR insights.',
      color: '#0ea5e9',
    },
    inventoryFG: {
      label: 'FG Inventory',
      description: 'Finished goods analyses and inline/excess breakouts.',
      color: '#a855f7',
    },
    inventoryRM: {
      label: 'RM Inventory',
      description: 'Raw material monitoring and category history snapshots.',
      color: '#ec4899',
    },
    inventoryWIP: {
      label: 'WIP Inventory',
      description: 'Track work-in-progress balances, categories, and ineligible detail.',
      color: '#f97316',
    },
    recovery: {
      label: 'Recovery',
      description: 'Model gross recovery behavior across FG, WIP, and raw materials.',
      color: '#fb7185',
    },
    risk: {
      label: 'Risk & Analytics',
      description: 'Composite indices, NOLV tables, and factor scoring live here.',
      color: '#f59e0b',
    },
    forecast: {
      label: 'Forecasting',
      description: 'Availability outlooks, trend variances, and plan vs actuals.',
      color: '#14b8a6',
    },
    settings: {
      label: 'Settings',
      description: 'Collaboration controls for collateral limits and eligibility rules.',
      color: '#475569',
    },
  };

  const entityMeta = buildEntityMeta(entityGroupMap, groupMeta);

  function buildEntityMeta(assignments, groups) {
    const meta = {};
    Object.keys(assignments).forEach((entity) => {
      const groupKey = assignments[entity];
      const group = groups[groupKey];
      if (!group) return;
      meta[entity] = {
        eyebrow: group.label,
        description: group.description,
        styles: buildAccentStyles(entity, group.color),
      };
    });
    return meta;
  }

  function buildAccentStyles(entity, color) {
    if (!color) return '';
    const soft = hexToRgba(color, 0.12);
    return `
      .ds-panel[data-entity="${entity}"] .ds-button.primary{
        background:${color};
      }
      .ds-panel[data-entity="${entity}"] .ds-inline-btn.edit{
        background:${soft};
        color:${color};
      }
    `;
  }

  function hexToRgba(hex, alpha) {
    const normalized = hex.replace('#', '');
    if (normalized.length !== 6) return `rgba(0,0,0,${alpha})`;
    const bigint = parseInt(normalized, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  const escapeHtml = (str) =>
    String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

  const generateId = () => Math.random().toString(36).slice(2, 10);

  function formatValue(value, formatter) {
    if (value === undefined || value === null || value === '') return '-';
    return formatter ? formatter(value) : typeof value === 'number' ? value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : value;
  }

  function buildFieldMarkup(field, value) {
    const required = field.required ? 'required' : '';
    const base = `name="${field.key}" id="field-${field.key}" ${required}`;
    const safeValue = escapeHtml(value ?? '');
    if (field.type === 'select') {
      const options = (field.options || [])
        .map((opt) => `<option value="${escapeHtml(opt.value)}"${opt.value === value ? ' selected' : ''}>${escapeHtml(opt.label)}</option>`)
        .join('');
      return `<select ${base}>${options}</select>`;
    }
    if (field.type === 'textarea') {
      return `<textarea ${base}>${safeValue}</textarea>`;
    }
    const type = field.type === 'number' ? 'number' : field.type;
    const step = field.type === 'number' ? 'step="any"' : '';
    return `<input type="${type}" ${base} value="${safeValue}" ${step} />`;
  }

  function createDataSheetComponent(entity, config, options) {
    const meta = options.meta || {};
    const rows = JSON.parse(JSON.stringify(options.initialRows || []));
    const ctx = {
      rows,
      host: null,
      modalHandler: null,
    };

    function render() {
      if (!ctx.host) return;
      const tableRows = (ctx.rows || [])
        .map((item) => {
          const cells = config.columns.map((col) => `<td>${escapeHtml(formatValue(item[col.key], col.format))}</td>`).join('');
          return `
            <tr>
              ${cells}
              <td>
                <div class="ds-actions-inline">
                  <button class="ds-inline-btn edit" data-action="edit" data-id="${item.id}" title="Edit record">Edit</button>
                  <button class="ds-inline-btn delete" data-action="delete" data-id="${item.id}" title="Delete record">Del</button>
                </div>
              </td>
            </tr>
          `;
        })
        .join('');

      const description = meta.description || `Review static records, simulate updates, or launch the quick add modal for ${config.title.toLowerCase()}.`;

      ctx.host.innerHTML = `
        <div class="ds-panel" aria-live="polite" data-entity="${entity}">
          <div class="ds-panel-head">
            <div class="ds-title-block">
              <span class="ds-eyebrow">${meta.eyebrow || `Entity ${entity}`}</span>
              <div class="ds-heading">${config.title}</div>
              <p class="ds-subtext">${description}</p>
            </div>
            <div class="ds-actions">
              <button class="ds-button primary" data-action="add">
                <span>＋</span>
                Add New
              </button>
            </div>
          </div>
          <div class="ds-table-wrap">
            <table class="ds-table">
              <thead>
                <tr>
                  ${config.columns.map((col) => `<th>${col.label}</th>`).join('')}
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows || `<tr><td colspan="${config.columns.length + 1}"><div class="ds-table-empty">No data available. Use “Add New” to seed an entry.</div></td></tr>`}
              </tbody>
            </table>
          </div>
          <div class="ds-footer">
            Showing ${(ctx.rows || []).length} record(s)
          </div>
        </div>
      `;

      const addButton = ctx.host.querySelector('[data-action="add"]');
      if (addButton) addButton.addEventListener('click', () => openModal());

      ctx.host.querySelectorAll('[data-action="edit"]').forEach((btn) =>
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-id');
          const target = (ctx.rows || []).find((item) => item.id === id);
          if (target) openModal(target);
        }),
      );

      ctx.host.querySelectorAll('[data-action="delete"]').forEach((btn) =>
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-id');
          const match = (ctx.rows || []).find((entry) => entry.id === id);
          if (!match) return;
          const title = config.title.endsWith('s') ? config.title.slice(0, -1) : config.title;
          environment.confirmFn({
            title: `Delete ${title}?`,
            message: 'This action cannot be undone.',
            confirmLabel: 'Delete',
            cancelLabel: 'Cancel',
            tone: 'danger',
          }).then((accepted) => {
            if (!accepted) return;
            ctx.rows = (ctx.rows || []).filter((entry) => entry.id !== id);
            render();
            pushToast('Record deleted');
          });
        }),
      );
    }

    function openModal(item) {
      if (!environment.modalRoot) return;
      const formFields = config.fields
        .map(
          (field) => `
            <div class="ds-field">
              <label for="field-${field.key}">${field.label}${field.required ? ' *' : ''}</label>
              ${buildFieldMarkup(field, item ? item[field.key] : '')}
            </div>
          `,
        )
        .join('');
      environment.modalRoot.innerHTML = `
        <div class="ds-modal" role="dialog" aria-modal="true" aria-label="${item ? 'Edit' : 'Add'} ${config.title}">
          <div class="ds-title-block">
            <span class="ds-eyebrow">${config.title}</span>
            <h3>${item ? 'Edit record' : 'Create record'}</h3>
          </div>
          <form id="ds-form">
            <div class="ds-form-grid">
              ${formFields}
            </div>
            <div class="ds-modal-actions">
              <button type="button" class="ds-button secondary" data-dismiss>Cancel</button>
              <button type="submit" class="ds-button primary">${item ? 'Update' : 'Create'}</button>
            </div>
          </form>
        </div>
      `;
      environment.modalRoot.classList.add('open');
      environment.modalRoot.setAttribute('aria-hidden', 'false');

      if (ctx.modalHandler) {
        environment.modalRoot.removeEventListener('click', ctx.modalHandler);
      }
      ctx.modalHandler = (event) => {
        if (event.target === environment.modalRoot) closeModal();
      };
      environment.modalRoot.addEventListener('click', ctx.modalHandler);

      const form = environment.modalRoot.querySelector('#ds-form');
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const payload = {};
        config.fields.forEach((field) => {
          const raw = formData.get(field.key);
          if (field.type === 'number') {
            payload[field.key] = raw === '' ? null : parseFloat(raw);
          } else {
            payload[field.key] = raw || '';
          }
        });
        if (item) {
          payload.id = item.id;
          ctx.rows = (ctx.rows || []).map((entry) => (entry.id === item.id ? { ...entry, ...payload } : entry));
          pushToast('Record updated');
        } else {
          ctx.rows = [...(ctx.rows || []), { ...payload, id: generateId() }];
          pushToast('Record created');
        }
        closeModal();
        render();
      });
      environment.modalRoot.querySelector('[data-dismiss]').addEventListener('click', closeModal);
    }

    function closeModal() {
      if (!environment.modalRoot) return;
      if (ctx.modalHandler) {
        environment.modalRoot.removeEventListener('click', ctx.modalHandler);
        ctx.modalHandler = null;
      }
      environment.modalRoot.classList.remove('open');
      environment.modalRoot.setAttribute('aria-hidden', 'true');
      environment.modalRoot.innerHTML = '';
    }

    function pushToast(message) {
      if (!environment.toastRoot) return;
      const toast = document.createElement('div');
      toast.className = 'ds-toast';
      toast.textContent = message;
      environment.toastRoot.appendChild(toast);
      setTimeout(() => toast.remove(), 2600);
    }

    return {
      id: entity,
      styles: meta.styles || '',
      mount(target) {
        ctx.host = target;
        render();
      },
      unmount() {
        if (ctx.host) {
          ctx.host.innerHTML = '';
        }
        ctx.host = null;
        closeModal();
      },
    };
  }

  function ensureComponent(entity) {
    if (componentCache[entity]) return componentCache[entity];
    const config = entityConfigs[entity];
    if (!config) return null;
    const component = createDataSheetComponent(entity, config, {
      initialRows: initialData[entity] || [],
      meta: entityMeta[entity] || {},
    });
    componentCache[entity] = component;
    return component;
  }

  function applyComponentStyles(css, entity) {
    if (activeStyleNode) {
      activeStyleNode.remove();
      activeStyleNode = null;
    }
    if (css) {
      const style = document.createElement('style');
      style.dataset.componentStyle = entity;
      style.textContent = css;
      document.head.appendChild(style);
      activeStyleNode = style;
    }
  }

  function renderUnavailable(entity) {
    appRoot.innerHTML = `
      <div class="ds-panel">
        <div class="ds-empty-state">
          <h3>Component unavailable</h3>
          <p>${escapeHtml(entity)} has not been wired up yet.</p>
        </div>
      </div>
    `;
  }

  function activateComponent(entity, node) {
    const component = ensureComponent(entity);
    if (!component) {
      renderUnavailable(entity);
      return;
    }
    if (activeComponent && activeComponent !== component) {
      activeComponent.unmount();
    }
    applyComponentStyles(component.styles, entity);
    component.mount(appRoot);
    activeComponent = component;
    state.currentEntity = entity;
    setSidebarActive(entity, node || null);
  }

  function setSidebarActive(entity, node) {
    const candidates = document.querySelectorAll('[data-entity]');
    candidates.forEach((el) => {
      const isMatch = node ? el === node : el.getAttribute('data-entity') === entity;
      el.classList.toggle('active', isMatch);
    });
  }

  function wireSidebar() {
    document.querySelectorAll('[data-entity]').forEach((node) => {
      node.addEventListener('click', (event) => {
        const entity = node.getAttribute('data-entity');
        if (!entityConfigs[entity]) return;
        event.preventDefault();
        activateComponent(entity, node);
      });
    });
    setSidebarActive(state.currentEntity);
  }

  wireSidebar();
  activateComponent(state.currentEntity);
})();
