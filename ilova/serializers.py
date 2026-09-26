from rest_framework import serializers
from .models import Event, Seat
from .models import EventSeat



class AdminEventCreateSerializer(serializers.ModelSerializer):
    sector_prices = serializers.JSONField(write_only=True)

    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'date', 'sector_prices']

    def create(self, validated_data):
        sector_prices = validated_data.pop('sector_prices')

        event = Event.objects.create(**validated_data)

        all_seats = Seat.objects.select_related('sector').all()
        event_seats_to_create = []

        for seat in all_seats:
            price = sector_prices.get(seat.sector.name, 50000.00)

            event_seats_to_create.append(
                EventSeat(
                    event=event,
                    seat=seat,
                    price=price,
                    status='AVAILABLE'
                )
            )

        EventSeat.objects.bulk_create(event_seats_to_create)
        return event


class CustomerEventSeatListSerializer(serializers.ModelSerializer):
    sector_name = serializers.CharField(source='seat.sector.name', read_only=True)
    row_number = serializers.IntegerField(source='seat.row_number', read_only=True)
    seat_number = serializers.IntegerField(source='seat.seat_number', read_only=True)

    class Meta:
        model = EventSeat
        fields = ['id', 'sector_name', 'row_number', 'seat_number', 'price', 'status']
