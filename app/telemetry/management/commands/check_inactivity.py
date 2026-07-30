from django.core.management.base import BaseCommand

from telemetry.services import check_device_inactivity


class Command(BaseCommand):
    help = 'Check all devices for inactivity and create/resolve failure records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output of flagged/resolved devices',
        )

    def handle(self, *args, **options):
        result = check_device_inactivity()
        flagged = result['flagged']
        resolved = result['resolved']

        self.stdout.write(
            self.style.SUCCESS(
                f'Flagged {len(flagged)} devices, resolved {len(resolved)} devices'
            )
        )

        if options['verbose']:
            for failure in flagged:
                self.stdout.write(
                    f'  Flagged: {failure.device.dev_eui} (inactivity)'
                )
            for failure in resolved:
                self.stdout.write(
                    f'  Resolved: {failure.device.dev_eui} (inactivity)'
                )
