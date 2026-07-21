# Save as: accounts/management/commands/enforce_alumni_verification.py
# (create the folders accounts/management/ and accounts/management/commands/,
#  each with an empty __init__.py)
#
# Run daily via cron / Celery beat / Windows Task Scheduler:
#   python manage.py enforce_alumni_verification

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User


class Command(BaseCommand):
    help = "Bans unverified alumni after 30 days, deletes them after a further 30-day ban."

    def handle(self, *args, **options):
        now = timezone.now()

        # Step 1: unverified alumni past their 30-day verify window -> ban for 30 days
        to_ban = User.objects.filter(
            role='ALUMNI',
            is_verified=False,
            is_suspended=False,
            created_at__lte=now - timedelta(days=30),
        )
        banned_count = to_ban.count()
        to_ban.update(is_suspended=True, banned_until=now + timedelta(days=30))

        # Step 2: still unverified once the ban period itself has expired -> delete
        to_delete = User.objects.filter(
            role='ALUMNI',
            is_verified=False,
            is_suspended=True,
            banned_until__lte=now,
        )
        deleted_count = to_delete.count()
        to_delete.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Banned {banned_count} unverified alumni account(s). "
            f"Deleted {deleted_count} account(s) past their ban period."
        ))