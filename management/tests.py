from django.test import TestCase

from .forms import (
    AgingCompositionForm,
    BorrowerForm,
    CollateralOverviewForm,
    CompanyForm,
)
from .models import Borrower, Company


class FormValidationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(company="Acme Corp")

    def test_company_form_requires_name(self):
        form = CompanyForm(
            data={
                "company": "",
                "industry": "Manufacturing",
                "primary_naics": "",
                "website": "",
                "email": "admin@example.com",
                "password": "secret123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("company", form.errors)

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
