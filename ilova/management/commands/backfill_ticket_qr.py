from django.core.management.base import BaseCommand

from ilova.models import Ticket


class Command(BaseCommand):
    help = (
        "QR-kod logikasi qo'shilishidan OLDIN yaratilgan (yoki rasm fayli diskdan "
        "yo'qolgan) eski chiptalar uchun qr_code_image maydonini avtomat to'ldiradi. "
        "Ticket.save() da allaqachon mavjud bo'lgan 'agar qr_code_image bo'sh bo'lsa, "
        "chizib qo'y' logikasidan foydalanadi — shuning uchun bu yerda faqat "
        "shunday chiptalarni topib, ularni qayta saqlash kifoya."
    )

    def handle(self, *args, **options):
        broken_tickets = Ticket.objects.filter(qr_code_image='')
        total = broken_tickets.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Barcha chiptalarda QR-kod allaqachon mavjud. Hech narsa qilinmadi."))
            return

        self.stdout.write(self.style.WARNING(f"{total} ta chiptada QR-kod topilmadi. Generatsiya boshlanmoqda..."))

        fixed = 0
        for ticket in broken_tickets:
            ticket.save()
            fixed += 1

        self.stdout.write(self.style.SUCCESS(f"Tayyor! {fixed} ta chipta uchun QR-kod generatsiya qilindi."))
