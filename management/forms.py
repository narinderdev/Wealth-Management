from decimal import Decimal

from django import forms

UPDATE_INTERVAL_CHOICES = [
    ("Annual", "Annual"),
    ("Semi-Annual", "Semi-Annual"),
    ("Quarterly", "Quarterly"),
    ("Monthly", "Monthly"),
    ("Weekly", "Weekly"),
]

from .models import (
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
    CummulativeVarianceRow,
    CurrentWeekVarianceRow,
    FGCompositionRow,
    FGIneligibleDetailRow,
    FGInlineCategoryAnalysisRow,
    FGInlineExcessByCategoryRow,
    FGInventoryMetricsRow,
    FGGrossRecoveryHistoryRow,
    ForecastRow,
    IneligibleOverviewRow,
    IneligibleTrendRow,
    MachineryEquipmentRow,
    BBCAvailabilityRow,
    NetRecoveryTrendRow,
    ValueTrendRow,
    NOLVTableRow,
    RawMaterialRecoveryRow,
    ReportUpload,
    RiskSubfactorsRow,
    RMCategoryHistoryRow,
    RMIneligibleOverviewRow,
    RMInventoryMetricsRow,
    SalesGMTrendRow,
    SnapshotSummaryRow,
    SpecificIndividual,
    IneligiblesRow,
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


class CompanyChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        label_parts = []
        if obj.specific_individual:
            label_parts.append(obj.specific_individual)
        if obj.company:
            label_parts.append(obj.company)
        if obj.lender_name:
            label_parts.append(f"Lender: {obj.lender_name}")
        if obj.specific_individual_id:
            label_parts.append(f"ID {obj.specific_individual_id}")
        if obj.lender_identifier:
            label_parts.append(f"Lender ID {obj.lender_identifier}")
        return " • ".join(label_parts) if label_parts else f"Company {obj.company_id or obj.pk}"


class CompanyAttributeChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, attr=None, fallback_attr=None, prefix="", suffix="", empty_label=None, **kwargs):
        self.attr = attr
        self.fallback_attr = fallback_attr or "specific_individual"
        self.prefix = prefix or ""
        self.suffix = suffix or ""
        super().__init__(*args, empty_label=empty_label, **kwargs)

    def label_from_instance(self, obj):
        value = getattr(obj, self.attr, None) if self.attr else None
        if not value and self.fallback_attr:
            value = getattr(obj, self.fallback_attr, None)
        if not value:
            value = obj.company or f"Company {obj.company_id or obj.pk}"
        return f"{self.prefix}{value}{self.suffix}"


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
    required_fields = (
        "specific_individual",
        "specific_individual_id",
        "lender_name",
        "lender_identifier",
        "email",
        "password",
    )

    class Meta:
        model = Company
        fields = [
            "specific_individual",
            "specific_individual_id",
            "lender_name",
            "lender_identifier",
            "email",
            "password",
        ]
        widgets = {
            "password": forms.PasswordInput(render_value=False),
        }
        labels = {
            "specific_individual": "Specific Individual",
            "specific_individual_id": "Specific Individual ID",
            "lender_name": "Lender (Bank)",
            "lender_identifier": "Lender ID",
            "email": "Email",
            "password": "Password",
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
            "lender",
            "lender_id",
            "company",
            "primary_contact",
            "primary_contact_phone",
            "primary_contact_email",
            "industry",
            "primary_naics",
            "website",
            "update_interval",
            "current_update",
            "previous_update",
            "next_update",
        ]
        widgets = {
            "industry": forms.TextInput(),
            "primary_naics": forms.TextInput(),
            "website": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_company_selector()
        self._configure_update_interval_field()
        self._configure_date_fields()
        self._mark_required_hints()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("primary_contact_email")
        phone = cleaned_data.get("primary_contact_phone")
        if not email and not phone:
            raise forms.ValidationError("Provide an email or phone for the primary contact.")
        company_name = (cleaned_data.get("company_name") or "").strip()
        if company_name:
            cleaned_data["company_name"] = company_name

        selector_fields = [
            "user_specific_individual",
            "user_specific_individual_id",
            "user_lender",
            "user_lender_id",
        ]
        selected_companies = []
        for field_name in selector_fields:
            company = cleaned_data.get(field_name)
            if company:
                selected_companies.append(company)
        if cleaned_data.get("company"):
            selected_companies.append(cleaned_data["company"])
        if not selected_companies and not company_name:
            raise forms.ValidationError("Select a company or enter a company name.")
        if selected_companies:
            base_company = selected_companies[0]
            mismatch = False
            for field_name in selector_fields:
                company = cleaned_data.get(field_name)
                if company and company.pk != base_company.pk:
                    mismatch = True
                    self.add_error(field_name, "Must match the selected specific individual.")
            if cleaned_data.get("company") and cleaned_data["company"].pk != base_company.pk:
                mismatch = True
            if mismatch:
                raise forms.ValidationError("Specific Individual, IDs, and lender selections must match.")
            if company_name and base_company.company:
                base_name = base_company.company.strip()
                if base_name and base_name.lower() != company_name.lower():
                    self.add_error(
                        "company_name",
                        "Company name must match the selected company. Clear the selection to create a new company.",
                    )
                    raise forms.ValidationError("Company selection does not match the entered company name.")
            cleaned_data["company"] = base_company
        return cleaned_data

    def _configure_company_selector(self):
        queryset = Company.objects.order_by("specific_individual", "company")
        company_field = CompanyChoiceField(
            queryset=queryset,
            required=False,
            empty_label="Select user",
        )
        company_field.widget = forms.HiddenInput()
        company_field.help_text = ""
        self.fields["company"] = company_field

        selector_config = [
            ("user_lender", "Lender", "lender_name", ""),
            ("user_lender_id", "Lender ID", "lender_identifier", ""),
            ("user_specific_individual", "Specific Individual", "specific_individual", ""),
            ("user_specific_individual_id", "Specific Individual ID", "specific_individual_id", "ID "),
        ]
        for field_name, label, attr, prefix in selector_config:
            self.fields[field_name] = CompanyAttributeChoiceField(
                queryset=queryset,
                attr=attr,
                prefix=prefix or "",
                empty_label="Select",
                required=False,
                label=label,
            )
        self.fields["company_name"] = forms.CharField(
            label="Company Name",
            required=False,
        )

        initial_company = None
        if not self.is_bound and self.instance.pk and self.instance.company_id:
            initial_company = self.instance.company
        elif not self.is_bound and self.initial.get("company"):
            initial_company = self.initial.get("company")

        if initial_company:
            company_field.initial = initial_company.pk
            for field_name, *_ in selector_config:
                self.fields[field_name].initial = initial_company.pk
            self.fields["company_name"].initial = initial_company.company

        for hidden in ("lender", "lender_id", "company"):
            if hidden in self.fields:
                self.fields[hidden].widget = forms.HiddenInput()
                self.fields[hidden].required = False

    def _configure_update_interval_field(self):
        if "update_interval" in self.fields:
            choices = [("", "Select Interval")] + list(UPDATE_INTERVAL_CHOICES)
            self.fields["update_interval"] = forms.ChoiceField(
                label="Update Interval",
                choices=choices,
                required=True,
            )

    def _configure_date_fields(self):
        date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
        for field_name in ("current_update", "previous_update", "next_update"):
            field = self.fields.get(field_name)
            if field:
                field.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
                field.input_formats = date_formats

        desired_order = [
            "user_lender",
            "user_lender_id",
            "user_specific_individual",
            "user_specific_individual_id",
            "company_name",
            "primary_contact",
            "primary_contact_phone",
            "primary_contact_email",
            "industry",
            "primary_naics",
            "website",
            "update_interval",
            "current_update",
            "previous_update",
            "next_update",
        ]
        self.order_fields([name for name in desired_order if name in self.fields])

    def clean_company(self):
        return self.cleaned_data.get("company")

    def _mark_required_hints(self):
        conditional_fields = (
            "user_lender",
            "user_lender_id",
            "user_specific_individual",
            "user_specific_individual_id",
            "company_name",
            "primary_contact_email",
            "primary_contact_phone",
        )
        for field_name in conditional_fields:
            field = self.fields.get(field_name)
            if field:
                field.show_required_hint = True

    def _apply_company_defaults(self, borrower):
        company = borrower.company
        if not company:
            return
        if not borrower.primary_contact and company.specific_individual:
            borrower.primary_contact = company.specific_individual
        if not borrower.primary_contact_email and company.email:
            borrower.primary_contact_email = company.email
        if not borrower.lender and company.lender_name:
            borrower.lender = company.lender_name
        if not borrower.lender_id and company.lender_identifier:
            borrower.lender_id = company.lender_identifier

    def _normalize_specific_id(self, value):
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            return None

    def _ensure_primary_specific_individual(self, borrower):
        company = borrower.company
        current = borrower.primary_specific_individual
        name = None
        specific_id = None
        if company:
            name = company.specific_individual or borrower.primary_contact
            specific_id = self._normalize_specific_id(company.specific_individual_id)
        elif borrower.primary_contact:
            name = borrower.primary_contact

        if current:
            updated = False
            if name and not current.specific_individual:
                current.specific_individual = name
                updated = True
            if specific_id and not current.specific_id:
                current.specific_id = specific_id
                updated = True
            if updated:
                current.save(update_fields=["specific_individual", "specific_id"])
            return current

        if not name and not specific_id:
            return None

        individual = SpecificIndividual.objects.create(
            borrower=borrower,
            specific_individual=name,
            specific_id=specific_id,
        )
        borrower.primary_specific_individual = individual
        borrower.save(update_fields=["primary_specific_individual"])
        return individual

    def save(self, commit=True):
        borrower = super().save(commit=False)
        is_new = borrower.pk is None
        self._apply_company_defaults(borrower)
        company_name = (self.cleaned_data.get("company_name") or "").strip()
        if company_name:
            borrower.company = Company.objects.filter(company__iexact=company_name).first()
            if not borrower.company:
                borrower.company = Company.objects.create(company=company_name)
        if commit:
            borrower.save()
            self.save_m2m()
            self._ensure_primary_specific_individual(borrower)
            if is_new:
                from management.services.borrower_defaults import bootstrap_default_borrower_data

                bootstrap_default_borrower_data(borrower)
        return borrower


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


class SnapshotSummaryForm(BorrowerModelForm):
    required_fields = ("borrower", "section")

    class Meta:
        model = SnapshotSummaryRow
        fields = ["borrower", "section", "summary_text"]
        widgets = {
            "summary_text": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Add snapshot summary text for this section...",
                }
            ),
        }

    def clean_summary_text(self):
        value = self.cleaned_data.get("summary_text")
        if value is None:
            return value
        trimmed = value.strip()
        return trimmed or None


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
            "estimated_fair_market_value",
            "estimated_orderly_liquidation_value",
            "total_asset_count",
            "total_fair_market_value",
            "total_orderly_liquidation_value",
        ]


class BBCAvailabilityForm(BorrowerModelForm):
    required_fields = ("borrower", "period")

    class Meta:
        model = BBCAvailabilityRow
        fields = [
            "borrower",
            "period",
            "net_collateral",
            "outstanding_balance",
            "availability",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["availability_pct"] = forms.DecimalField(
            label="Availability %",
            required=False,
            decimal_places=2,
            max_digits=12,
        )
        period_field = self.fields.get("period")
        if period_field:
            period_field.widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
            period_field.input_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
        availability_field = self.fields.get("availability")
        if availability_field:
            availability_field.widget.attrs["readonly"] = "readonly"
        availability_pct_field = self.fields.get("availability_pct")
        if availability_pct_field:
            availability_pct_field.widget.attrs["readonly"] = "readonly"
        if self.instance and self.instance.pk:
            availability = self.instance.availability
            net_collateral = self.instance.net_collateral
            if availability is not None and net_collateral:
                availability_pct_field.initial = (availability / net_collateral) * Decimal("100")
            else:
                availability_pct_field.initial = Decimal("0")
        self.order_fields(
            [
                "borrower",
                "period",
                "net_collateral",
                "outstanding_balance",
                "availability",
                "availability_pct",
            ]
        )

    def clean(self):
        cleaned_data = super().clean()
        net_collateral = cleaned_data.get("net_collateral") or Decimal("0")
        outstanding_balance = cleaned_data.get("outstanding_balance") or Decimal("0")
        cleaned_data["availability"] = net_collateral - outstanding_balance
        cleaned_data["availability_pct"] = (
            (cleaned_data["availability"] / net_collateral) * Decimal("100")
            if net_collateral
            else Decimal("0")
        )
        return cleaned_data


class NetRecoveryTrendForm(BorrowerModelForm):
    required_fields = ("borrower", "period")

    class Meta:
        model = NetRecoveryTrendRow
        fields = [
            "borrower",
            "period",
            "fg_net_recovery_pct",
            "rm_net_recovery_pct",
            "wip_net_recovery_pct",
        ]

    def _validate_pct(self, field):
        value = self.cleaned_data.get(field)
        if value is None:
            return value
        if value < 0 or value > 100:
            raise forms.ValidationError("Percentage must be between 0 and 100.")
        return value

    def clean_fg_net_recovery_pct(self):
        return self._validate_pct("fg_net_recovery_pct")

    def clean_rm_net_recovery_pct(self):
        return self._validate_pct("rm_net_recovery_pct")

    def clean_wip_net_recovery_pct(self):
        return self._validate_pct("wip_net_recovery_pct")
class ValueTrendForm(BorrowerModelForm):
    required_fields = ("borrower", "date")

    class Meta:
        model = ValueTrendRow
        fields = [
            "borrower",
            "date",
            "estimated_olv",
            "appraised_olv",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


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
            "new_dollars",
            "new_pct",
            "inline_dollars",
            "inline_pct",
            "excess_dollars",
            "excess_pct",
            "no_sales_dollars",
            "no_sales_pct",
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
        labels = {
            "x": "Actual",
        }


class CashForecastForm(BorrowerModelForm):
    required_fields = ("borrower", "date", "category", "x")

    class Meta:
        model = CashForecastRow
        fields = [
            "borrower",
            "report",
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
        labels = {
            "x": "Actual",
            "report": "Borrower Report",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "report" in self.fields:
            self.fields["report"].queryset = (
                BorrowerReport.objects.select_related("borrower", "borrower__company")
                .order_by("borrower__company__company", "-report_date")
            )

    def clean(self):
        cleaned_data = super().clean()
        borrower = cleaned_data.get("borrower")
        report = cleaned_data.get("report")

        if report and borrower and report.borrower_id != borrower.id:
            self.add_error("report", "Selected report must match the borrower.")

        if borrower and not report and not self.instance.pk:
            latest_report = (
                BorrowerReport.objects.filter(borrower=borrower)
                .order_by("-report_date", "-created_at", "-id")
                .first()
            )
            if latest_report:
                cleaned_data["report"] = latest_report
        return cleaned_data


class CashFlowForecastForm(StyledModelForm):
    required_fields = ("report", "category")

    class Meta:
        model = CashFlowForecastRow
        fields = [
            "report",
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
            "total",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "report" in self.fields:
            self.fields["report"].queryset = (
                BorrowerReport.objects.select_related("borrower", "borrower__company")
                .order_by("borrower__company__company", "-report_date")
            )
            self.fields["report"].label = "Borrower Report"


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


class BaseReportUploadForm(StyledModelForm):
    report_type = None

    class Meta:
        model = ReportUpload
        fields = ["name", "file"]
        labels = {
            "name": "Report Name",
            "file": "Report PDF",
        }
        widgets = {
            "file": forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
        }
        help_texts = {
            "file": "Upload a PDF file.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "file" in self.fields:
            self.fields["file"].required = True
        if "name" in self.fields:
            self.fields["name"].widget.attrs.setdefault("placeholder", "Example: October BBC")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.report_type:
            instance.report_type = self.report_type
        if commit:
            instance.save()
        return instance


class BorrowingBaseReportForm(BaseReportUploadForm):
    report_type = ReportUpload.BORROWING_BASE


class CompleteAnalysisReportForm(BaseReportUploadForm):
    report_type = ReportUpload.COMPLETE_ANALYSIS


class CashFlowReportForm(BaseReportUploadForm):
    report_type = ReportUpload.CASH_FLOW
