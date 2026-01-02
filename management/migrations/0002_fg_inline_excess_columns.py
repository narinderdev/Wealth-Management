from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="new_dollars",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="new_pct",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="no_sales_dollars",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="no_sales_pct",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="total_inline_dollars",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="total_inline_pct",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="total_excess_dollars",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="total_excess_pct",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="total_dollars",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="fginlineexcessbycategoryrow",
            name="total_pct",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True),
        ),
    ]
