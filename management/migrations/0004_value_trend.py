from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0003_machinery_equipment_estimated_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ValueTrendRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField(blank=True, null=True)),
                ("estimated_olv", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                ("appraised_olv", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True)),
                (
                    "borrower",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="value_trend_rows",
                        to="management.borrower",
                    ),
                ),
            ],
            options={
                "db_table": "value_trend",
            },
        ),
    ]
