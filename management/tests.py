from datetime import datetime, date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .forms import (
    AgingCompositionForm,
    BorrowerForm,
    CollateralOverviewForm,
    CompanyForm,
)
from .models import ARMetricsRow, Borrower, CollateralOverviewRow, Company
from .views.summary import _delta_payload, get_kpi_timeseries


class FormValidationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(company="Acme Corp")

    def test_company_form_requires_name(self):
        form = CompanyForm(
            data={
                "specific_individual": "",
                "specific_individual_id": "",
                "lender_name": "",
                "lender_identifier": "",
                "email": "",
                "password": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("specific_individual", form.errors)
        self.assertIn("specific_individual_id", form.errors)
        self.assertIn("lender_name", form.errors)
        self.assertIn("lender_identifier", form.errors)
        self.assertIn("email", form.errors)
        self.assertIn("password", form.errors)

    def test_borrower_form_requires_contact_method(self):
        form = BorrowerForm(
            data={
                "company": self.company.pk,
                "primary_contact": "Jane Doe",
                "primary_contact_phone": "",
                "primary_contact_email": "",
                "update_interval": "Monthly",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_borrower_form_valid_with_email(self):
        form = BorrowerForm(
            data={
                "company": self.company.pk,
                "primary_contact": "Jane Doe",
                "primary_contact_phone": "",
                "primary_contact_email": "jane@example.com",
                "update_interval": "Monthly",
            }
        )
        self.assertTrue(form.is_valid())

    def test_borrower_required_on_metric_forms(self):
        borrower = Borrower.objects.create(company=self.company, primary_contact="Owner", update_interval="Monthly")
        form = AgingCompositionForm(
            data={
                "borrower": "",
                "division": "North",
                "as_of_date": "2024-01-01",
                "bucket": "0-30",
                "pct_of_total": "10.0",
                "amount": "1000.00",
            }
        )
        self.assertFalse(form.is_valid())
        form_with_borrower = AgingCompositionForm(
            data={
                "borrower": borrower.pk,
                "division": "North",
                "as_of_date": "2024-01-01",
                "bucket": "0-30",
                "pct_of_total": "10.0",
                "amount": "1000.00",
            }
        )
        self.assertTrue(form_with_borrower.is_valid())

    def test_collateral_overview_requires_main_and_sub(self):
        borrower = Borrower.objects.create(company=self.company, primary_contact="Owner", update_interval="Monthly")
        form = CollateralOverviewForm(
            data={
                "borrower": borrower.pk,
                "main_type": "",
                "sub_type": "",
                "beginning_collateral": "1000.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("main_type", form.errors)
        self.assertIn("sub_type", form.errors)


class SummaryKpiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(company="Acme Corp")
        self.borrower = Borrower.objects.create(
            company=self.company,
            primary_contact="Owner",
            update_interval="Monthly",
        )

    def _set_created_at(self, row, year, month, day):
        dt = timezone.make_aware(datetime(year, month, day, 12, 0, 0))
        row.__class__.objects.filter(pk=row.pk).update(created_at=dt)
        row.refresh_from_db()

    def test_availability_series_uses_net_minus_outstanding(self):
        net_row = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="FG",
            net_collateral="100.00",
        )
        self._set_created_at(net_row, 2024, 1, 15)
        ARMetricsRow.objects.create(
            borrower=self.borrower,
            as_of_date=date(2024, 1, 31),
            balance="30.00",
        )

        availability = get_kpi_timeseries(
            "availability",
            self.borrower,
            range_start=date(2024, 1, 1),
            range_end=date(2024, 1, 31),
            max_points=1,
        )

        self.assertEqual(availability["labels"], ["01/24"])
        self.assertEqual(availability["values"], [Decimal("70.00")])

    def test_percent_change_formula(self):
        delta = _delta_payload("110", "100")
        self.assertIsNotNone(delta)
        self.assertEqual(delta["value"], "10.00%")
        self.assertEqual(delta["symbol"], "▲")
        self.assertEqual(delta["class"], "up")

    def test_series_labels_are_unique_and_sorted(self):
        first = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="FG",
            net_collateral="100.00",
        )
        second = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="RM",
            net_collateral="150.00",
        )
        third = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="WIP",
            net_collateral="200.00",
        )
        self._set_created_at(first, 2024, 1, 5)
        self._set_created_at(second, 2024, 1, 20)
        self._set_created_at(third, 2024, 2, 10)

        series = get_kpi_timeseries(
            "net",
            self.borrower,
            range_start=date(2024, 1, 1),
            range_end=date(2024, 2, 28),
            max_points=2,
        )

        self.assertEqual(series["labels"], ["01/24", "02/24"])
        self.assertEqual(series["values"], [Decimal("150.00"), Decimal("200.00")])
