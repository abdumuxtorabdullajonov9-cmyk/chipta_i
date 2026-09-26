import uuid

from django_redis import get_redis_connection
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import EventSeat, Order, Ticket
import qrcode
from io import BytesIO
from django.core.files import File


def release_expired_reservations():
    expiration_time = timezone.now() - timedelta(minutes=10)
    expired_orders = Order.objects.filter(status='PENDING', created_at__lte=expiration_time)

    redis_conn = get_redis_connection("default")
    for order in expired_orders:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order.id)
            if order.status != 'PENDING':
                continue
            for event_seat in order.event_seats.all():
                if event_seat.status == 'RESERVED':
                    event_seat.status = 'AVAILABLE'
                    event_seat.reserved_at = None
                    event_seat.save()
                redis_conn.delete(f"lock:event_seat:{event_seat.id}")
            order.status = 'EXPIRED'
            order.save()


def reserve_seats_service(user, event_seat_ids):
    release_expired_reservations()

    redis_conn = get_redis_connection("default")
    lock_ttl = 600  # 10 daqiqa taymer


    acquired_locks = []

    try:
        for seat_id in event_seat_ids:
            lock_key = f"lock:event_seat:{seat_id}"
            is_locked = redis_conn.set(lock_key, user.id, nx=True, ex=lock_ttl)
            if not is_locked:
                raise ValidationError(
                    f"Kechirasiz, tanlangan o'rindiqlardan biri hozirgina boshqa foydalanuvchi tomonidan band qilindi.")
            acquired_locks.append(lock_key)
    except Exception:
        for lock_key in acquired_locks:
            redis_conn.delete(lock_key)
        raise

    try:
        with transaction.atomic():
            seats = EventSeat.objects.select_for_update().filter(id__in=event_seat_ids)
            for seat in seats:
                if seat.status != 'AVAILABLE':
                    raise ValidationError(f"Joy bo'sh emas.")
                seat.status = 'RESERVED'
                seat.reserved_at = timezone.now()
                seat.save()

            total_price = sum(seat.price for seat in seats)
            order = Order.objects.create(
                user=user,
                status='PENDING',
                total_amount=total_price
            )
            order.event_seats.set(seats)
            return order
    except Exception as e:
        for seat_id in event_seat_ids:
            redis_conn.delete(f"lock:event_seat:{seat_id}")
        raise e


def confirm_fake_payment_service(order_id):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order_id)
        if order.status != 'PENDING':
            raise ValidationError("Bu buyurtma to'lov kutish holatida emas.")

        order.status = 'PAID'
        order.save()

        for event_seat in order.event_seats.all():
            event_seat.status = 'SOLD'
            event_seat.save()

            ticket = Ticket.objects.create(
                order=order,
                event_seat=event_seat,
                ticket_uid=uuid.uuid4(),
            )

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(str(ticket.ticket_uid))
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            blob = BytesIO()
            img.save(blob, 'PNG')
            ticket.qr_code_image.save(f"qr_{ticket.ticket_uid}.png", File(blob), save=False)
            ticket.save()

        redis_conn = get_redis_connection("default")
        for seat in order.event_seats.all():
            redis_conn.delete(f"lock:event_seat:{seat.id}")

        return order
