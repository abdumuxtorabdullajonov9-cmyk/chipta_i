from django.core.management.base import BaseCommand

from ilova.models import StadiumSector, Seat, SectorGroup


class Command(BaseCommand):
    help = "Istiqlol stadioni 32 ta sektorini va har biriga 625 (25x25) o'rindiqni bazada avtomat yaratadi"

    GROUP_RANGES = [
        ("1-8-sektorlar", 1, 8, 30000.00, "text-sky-400"),
        ("9-16-sektorlar", 9, 16, 50000.00, "text-amber-400"),
        ("17-24-sektorlar", 17, 24, 40000.00, "text-emerald-400"),
        ("25-32-sektorlar", 25, 32, 45000.00, "text-slate-400"),
    ]

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Stadion strukturasini yaratish boshlandi (32 sektor x 625 joy)..."))

        groups_by_number = {}
        for group_name, start, end, price, color_class in self.GROUP_RANGES:
            group, _ = SectorGroup.objects.get_or_create(
                name=group_name,
                defaults={"color_class": color_class, "default_price": price},
            )
            for n in range(start, end + 1):
                groups_by_number[n] = group

        for i in range(1, 33):
            sector, created = StadiumSector.objects.get_or_create(
                name=str(i),
                defaults={"group": groups_by_number[i]},
            )

            if not created:
                self.stdout.write(self.style.WARNING(f"{i}-sektor allaqachon mavjud, o'tkazib yuborildi."))
                continue

            seats_to_create = [
                Seat(sector=sector, row_number=row, seat_number=seat_no)
                for row in range(1, 26)
                for seat_no in range(1, 26)
            ]
            Seat.objects.bulk_create(seats_to_create)
            self.stdout.write(self.style.SUCCESS(f"{i}-sektor yaratildi: 625 ta o'rindiq qo'shildi."))

        self.stdout.write(self.style.SUCCESS(
            "Tabriklayman! Istiqlol stadioni (32 sektor x 625 joy = 20 000 o'rindiq) bazaga to'liq kiritildi."
        ))
