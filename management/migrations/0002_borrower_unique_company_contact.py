from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="borrower",
            constraint=models.UniqueConstraint(
                fields=("company", "primary_contact"),
                name="unique_borrower_company_contact",
            ),
        ),
    ]
