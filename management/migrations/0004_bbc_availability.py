from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0003_machinery_equipment_estimated_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="BBCAvailabilityRow",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.DateField(blank=True, null=True)),
                ("net_collateral", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("outstanding_balance", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("availability", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("borrower", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="bbc_availability_rows", to="management.borrower")),
            ],
            options={
                "db_table": "bbc_availability",
                "unique_together": {("borrower", "period")},
            },
        ),
    ]
