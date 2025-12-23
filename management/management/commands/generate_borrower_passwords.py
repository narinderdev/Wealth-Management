import secrets
import string

from django.core.management.base import BaseCommand

from management.models import Borrower


def _generate_password(length):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = "Generate and store passwords for borrowers so they can log in via the borrower table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--length",
            type=int,
            default=12,
            help="Length of the generated password (default: 12).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing borrower passwords.",
        )

    def handle(self, *args, **options):
        length = options["length"]
        force = options["force"]

        borrowers = Borrower.objects.all().order_by("id")
        if not borrowers:
            self.stdout.write("No borrowers in the database.")
            return

        for borrower in borrowers:
            if borrower.password and not force:
                self.stdout.write(
                    f"skip  {borrower.id}: already has password (use --force to regenerate)"
                )
                continue

            raw_password = _generate_password(length)
            borrower.set_password(raw_password, save=False)
            borrower.save(update_fields=["password"])
            self.stdout.write(
                f"{borrower.id}\t{borrower.company or '—'}\t"
                f"{borrower.primary_contact_email or '—'}\t{raw_password}"
            )
