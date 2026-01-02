from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0002_fg_inline_excess_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="machineryequipmentrow",
            name="estimated_fair_market_value",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="machineryequipmentrow",
            name="estimated_orderly_liquidation_value",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
