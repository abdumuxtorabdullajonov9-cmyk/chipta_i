import qrcode
import io
from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from django.core.files import File


class SectorGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color_class = models.CharField(max_length=50, default="text-slate-400")
    default_price = models.DecimalField(max_digits=10, decimal_places=2, default=50000.00)

    def __str__(self):
        return self.name


class StadiumSector(models.Model):
    name = models.CharField(max_length=50)
    group = models.ForeignKey(SectorGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='sectors')

    def __str__(self):
        return f"{self.name}-sektor"


class Seat(models.Model):
    sector = models.ForeignKey(StadiumSector, on_delete=models.CASCADE, related_name='seats')
    row_number = models.IntegerField()
    seat_number = models.IntegerField()

    class Meta:
        unique_together = ('sector', 'row_number', 'seat_number')

    def __str__(self):
        return f"{self.sector.name} | {self.row_number}-qator, {self.seat_number}-joy"


class Event(models.Model):
    title = models.CharField(max_length=200, help_text="Masalan: Neftchi vs Navbahor")
    description = models.TextField(blank=True)
    date = models.DateTimeField(help_text="O'yin boshlanish vaqti")
    gates_open_at = models.DateTimeField(null=True, blank=True, help_text="Eshiklar ochilish vaqti")
    poster = models.ImageField(upload_to="posters/", null=True, blank=True, help_text="O'yin afishasi")
    team1_logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    team2_logo = models.ImageField(upload_to="logos/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    @property
    def available_seats_count(self):
        return self.event_seats.filter(status='AVAILABLE').count()

    @property
    def min_price(self):
        lowest_seat = self.event_seats.filter(status='AVAILABLE').order_by('price').first()
        return lowest_seat.price if lowest_seat else 0.00


class EventSeat(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Bo\'sh'),
        ('RESERVED', 'Bron qilingan'),
        ('SOLD', 'Sotilgan'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='event_seats')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    reserved_at = models.DateTimeField(null=True, blank=True)  # 10 daqiqalik taymer uchun

    class Meta:
        unique_together = ('event', 'seat')

    def __str__(self):
        return f"{self.event.title} - {self.seat} ({self.get_status_display()})"


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'To\'lov kutilmoqda'),
        ('PAID', 'To\'langan'),
        ('EXPIRED', 'Muddati o\'tgan'),
        ('CANCELLED', 'Bekor qilingan'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    event_seats = models.ManyToManyField(EventSeat, related_name='orders')

    def __str__(self):
        return f"Buyurtma {self.id} - {self.status}"

    def is_expired(self):
        if self.status == 'PENDING' and timezone.now() > self.created_at + timezone.timedelta(minutes=10):
            return True
        return False


class Ticket(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tickets')
    event_seat = models.OneToOneField(EventSeat, on_delete=models.CASCADE, related_name='ticket')
    ticket_uid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    qr_code_image = models.ImageField(upload_to='tickets/qr_codes/', blank=True, null=True)

    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if not self.qr_code_image and self.ticket_uid:
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(str(self.ticket_uid))
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')

            filename = f"qr_{self.ticket_uid}.png"
            self.qr_code_image.save(filename, File(buffer), save=False)

        super().save(*args, **kwargs)