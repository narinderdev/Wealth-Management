from datetime import datetime, date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (
    AgingCompositionForm,
    BorrowerForm,
    CollateralOverviewForm,
    CompanyForm,
)
from .models import (
    ARMetricsRow,
    Borrower,
    CollateralOverviewRow,
    Company,
    FGInlineExcessByCategoryRow,
    HistoricalTop20SKUsRow,
)
from .views.summary import _delta_payload, get_kpi_timeseries, _previous_month
from .views.summary import compute_inventory_breakdown
from .views.collateral_dynamic import _finished_goals_context


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

    def test_borrower_form_auto_creates_company(self):
        form = BorrowerForm(
            data={
                "primary_contact": "Acme Borrower",
                "primary_contact_phone": "",
                "primary_contact_email": "borrower@example.com",
                "update_interval": "Monthly",
            }
        )
        self.assertTrue(form.is_valid())
        borrower = form.save()
        self.assertIsNotNone(borrower.company_id)
        borrower.refresh_from_db()
        self.assertEqual(borrower.company.company, "Acme Borrower")

    def test_borrower_form_does_not_overwrite_company_email(self):
        company = Company.objects.create(company="Legacy Co", email="legacy@example.com")
        form = BorrowerForm(
            data={
                "company": company.pk,
                "primary_contact": "New Borrower",
                "primary_contact_phone": "",
                "primary_contact_email": "newborrower@example.com",
                "update_interval": "Monthly",
            }
        )
        self.assertTrue(form.is_valid())
        borrower = form.save()
        borrower.refresh_from_db()
        company.refresh_from_db()
        self.assertEqual(company.email, "legacy@example.com")
        self.assertEqual(borrower.company_id, company.id)

    def test_borrower_form_does_not_modify_auth_user_emails(self):
        User = get_user_model()
        user_a = User.objects.create_user(username="user_a", email="user_a@example.com", password="pass")
        user_b = User.objects.create_user(username="user_b", email="user_b@example.com", password="pass")
        form = BorrowerForm(
            data={
                "primary_contact": "Borrower Contact",
                "primary_contact_phone": "",
                "primary_contact_email": "borrower@example.com",
                "update_interval": "Monthly",
            }
        )
        self.assertTrue(form.is_valid())
        form.save()
        user_a.refresh_from_db()
        user_b.refresh_from_db()
        self.assertEqual(user_a.email, "user_a@example.com")
        self.assertEqual(user_b.email, "user_b@example.com")

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


class SummaryMonthHelpersTests(TestCase):
    def test_previous_month_accepts_tuple(self):
        self.assertEqual(_previous_month((2024, 1)), (2023, 12))
        self.assertEqual(_previous_month((2024, 5)), (2024, 4))

    def test_previous_month_accepts_date(self):
        self.assertEqual(_previous_month(date(2024, 1, 15)), date(2023, 12, 15))
        self.assertEqual(_previous_month(date(2024, 3, 31)), date(2024, 2, 29))


class InventoryBreakdownConsistencyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(company="Acme Corp")
        self.borrower = Borrower.objects.create(
            company=self.company,
            primary_contact="Owner",
            update_interval="Monthly",
        )
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="tester", password="pass1234")
        self.client.force_login(self.user)

    def _set_created_at(self, row, year, month, day):
        dt = timezone.make_aware(datetime(year, month, day, 12, 0, 0))
        row.__class__.objects.filter(pk=row.pk).update(created_at=dt)
        row.refresh_from_db()

    def test_inventory_category_totals_match_summary_and_inventory_pages(self):
        fg = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="Finished Goods",
            eligible_collateral="1000.00",
            ineligibles="100.00",
            net_collateral="900.00",
        )
        rm = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="Raw Materials",
            eligible_collateral="700.00",
            ineligibles="50.00",
            net_collateral="650.00",
        )
        wip = CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="Work In Progress",
            eligible_collateral="500.00",
            ineligibles="25.00",
            net_collateral="475.00",
        )
        for row in (fg, rm, wip):
            self._set_created_at(row, 2024, 6, 15)

        summary_response = self.client.get(
            reverse("dashboard"),
            {"borrower_id": self.borrower.id},
        )
        inventory_response = self.client.get(
            reverse("collateral_dynamic"),
            {"section": "inventory", "inventory_tab": "summary", "borrower_id": self.borrower.id},
        )

        summary_totals = summary_response.context["inventory_category_totals"]
        inventory_totals = inventory_response.context["inventory_category_totals"]

        for key in ("finished_goods", "raw_materials", "work_in_progress"):
            self.assertEqual(
                summary_totals[key]["raw"]["eligible_collateral"],
                inventory_totals[key]["raw"]["eligible_collateral"],
            )

    def test_inventory_breakdown_helper_signs(self):
        total, ineligible, available = compute_inventory_breakdown("8427622", "1531374", "6896248")
        self.assertEqual(total, Decimal("8427622"))
        self.assertEqual(ineligible, Decimal("-1531374"))
        self.assertEqual(available, Decimal("6896248"))

    def test_inventory_metrics_use_signed_ineligible(self):
        rows = [
            ("Finished Goods", "1100.00", "100.00", "1000.00"),
            ("Raw Materials", "750.00", "50.00", "700.00"),
            ("Work In Progress", "525.00", "25.00", "500.00"),
        ]
        for label, eligible, ineligible, net in rows:
            row = CollateralOverviewRow.objects.create(
                borrower=self.borrower,
                main_type="Inventory",
                sub_type=label,
                beginning_collateral=eligible,
                eligible_collateral=net,
                ineligibles=ineligible,
                net_collateral=net,
            )
            self._set_created_at(row, 2024, 6, 15)

        response = self.client.get(
            reverse("collateral_dynamic"),
            {"section": "inventory", "inventory_tab": "summary", "borrower_id": self.borrower.id},
        )

        def parse_currency(value):
            cleaned = value.replace("$", "").replace(",", "").strip()
            return Decimal(cleaned)

        def assert_metric(metric_list):
            metrics = {item["label"]: item["value"] for item in metric_list}
            total = parse_currency(metrics["Total Inventory"])
            ineligible = parse_currency(metrics["Ineligible Inventory"])
            available = parse_currency(metrics["Available Inventory"])
            self.assertGreaterEqual(total, 0)
            self.assertLessEqual(ineligible, 0)
            self.assertGreaterEqual(available, 0)
            self.assertEqual(available, total + ineligible)

        assert_metric(response.context["finished_goals_metrics"])
        assert_metric(response.context["raw_materials_metrics"])
        assert_metric(response.context["work_in_progress_metrics"])

    def test_inline_excess_by_category_totals(self):
        FGInlineExcessByCategoryRow.objects.create(
            borrower=self.borrower,
            category="Cabinets",
            fg_available="1000.00",
            inline_dollars="700.00",
            inline_pct="70.0",
            excess_dollars="300.00",
            excess_pct="30.0",
        )
        FGInlineExcessByCategoryRow.objects.create(
            borrower=self.borrower,
            category="Doors",
            fg_available="2000.00",
            inline_dollars="1200.00",
            inline_pct="60.0",
            excess_dollars="800.00",
            excess_pct="40.0",
        )

        response = self.client.get(
            reverse("collateral_dynamic"),
            {"section": "inventory", "inventory_tab": "finished_goods", "borrower_id": self.borrower.id},
        )

        rows = response.context["finished_goals_inline_excess_by_category"]
        totals = response.context["finished_goals_inline_excess_totals"]

        def parse_currency(value):
            cleaned = value.replace("$", "").replace(",", "").strip()
            return Decimal(cleaned)

        row_total = sum(parse_currency(row["total_amount"]) for row in rows)
        self.assertEqual(row_total, parse_currency(totals["total_amount"]))

        for row in rows:
            self.assertEqual(
                parse_currency(row["inline_total_amount"]),
                parse_currency(row["new_amount"]) + parse_currency(row["inline_0_52_amount"]),
            )
            self.assertEqual(
                parse_currency(row["excess_total_amount"]),
                parse_currency(row["week_52_amount"]) + parse_currency(row["no_sales_amount"]),
            )


class TopSkuLatestMonthTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(company="Acme Corp")
        self.borrower = Borrower.objects.create(
            company=self.company,
            primary_contact="Owner",
            update_interval="Monthly",
        )
        CollateralOverviewRow.objects.create(
            borrower=self.borrower,
            main_type="Inventory",
            sub_type="Finished Goods",
            beginning_collateral="1000.00",
            eligible_collateral="900.00",
            ineligibles="100.00",
        )

    def test_finished_goods_top_sku_uses_latest_month_only(self):
        HistoricalTop20SKUsRow.objects.create(
            borrower=self.borrower,
            as_of_date=date(2024, 1, 31),
            item_number="100",
            category="Cabinets",
            description="Older SKU",
            cost="100.00",
            cogs="40.00",
            gm="60.00",
        )
        HistoricalTop20SKUsRow.objects.create(
            borrower=self.borrower,
            as_of_date=date(2024, 2, 29),
            item_number="100",
            category="Cabinets",
            description="Latest SKU",
            cost="50.00",
            cogs="20.00",
            gm="30.00",
        )

        context = _finished_goals_context(self.borrower, range_key="today", division="all")
        top_skus = context["finished_goals_top_skus"]

        self.assertEqual(len(top_skus), 1)
        self.assertEqual(top_skus[0]["cost"], "$50.00")
