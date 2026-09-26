from django.contrib import admin
from .models import StadiumSector, Seat, Event, EventSeat, Order


@admin.register(StadiumSector)
class StadiumSectorAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ['id', 'sector', 'row_number', 'seat_number']
    list_filter = ['sector', 'row_number']
    search_fields = ['seat_number']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'is_active']
    list_filter = ['is_active', 'date']
    actions = ['generate_tickets_for_event']

    @admin.action(description="Tanlangan o'yin uchun chiptalarni (sektor narxlari bilan) generatsiya qilish")
    def generate_tickets_for_event(self, request, queryset):

        for event in queryset:
            all_seats = Seat.objects.all().select_related('sector__group')
            event_seats_to_create = []

            existing_seat_ids = EventSeat.objects.filter(event=event).values_list('seat_id', flat=True)

            for seat in all_seats:
                if seat.id not in existing_seat_ids:
                    seat_price = getattr(seat.sector.group, 'default_price', 50000.00)

                    event_seats_to_create.append(
                        EventSeat(
                            event=event,
                            seat=seat,
                            price=seat_price,
                            status='AVAILABLE'
                        )
                    )

            if event_seats_to_create:
                EventSeat.objects.bulk_create(event_seats_to_create)
                self.message_user(request,
                                  f"{event.title} uchun {len(event_seats_to_create)} ta chipta sektor narxlari bilan yaratildi!")
            else:
                self.message_user(request, f"{event.title} uchun chiptalar allaqachon generatsiya qilingan.",
                                  level='WARNING')


@admin.register(EventSeat)
class EventSeatAdmin(admin.ModelAdmin):
    list_display = ['event', 'get_sector', 'get_row', 'get_seat_no', 'price', 'status']
    list_filter = ['event', 'status', 'seat__sector']
    search_fields = ['seat__seat_number']
    readonly_fields = ['status']

    def get_sector(self, obj): return obj.seat.sector.name

    def get_row(self, obj): return f"{obj.seat.row_number}-qator"

    def get_seat_no(self, obj): return f"{obj.seat.seat_number}-joy"

    get_sector.short_description = 'Sektor'
    get_row.short_description = 'Qator'
    get_seat_no.short_description = 'O\'rindiq raqami'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at']
