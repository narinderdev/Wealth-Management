from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0004_bbc_availability"),
    ]

    operations = [
        migrations.CreateModel(
            name="NetRecoveryTrendRow",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.DateField(blank=True, null=True)),
                ("fg_net_recovery_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("rm_net_recovery_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("wip_net_recovery_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("borrower", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="net_recovery_trend_rows", to="management.borrower")),
            ],
            options={
                "db_table": "net_recovery_trend",
                "unique_together": {("borrower", "period")},
            },
        ),
    ]
