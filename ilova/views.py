from django.views.generic import ListView, TemplateView
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import HttpResponse
import environ

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from .models import Event, EventSeat, Order, Ticket, StadiumSector, SectorGroup, Seat
from .serializers import CustomerEventSeatListSerializer
from .services import reserve_seats_service, confirm_fake_payment_service, release_expired_reservations
from .utils import render_to_pdf


class UserRegisterView(View):
    def get(self, request):
        return render(request, 'register.html', {'next': request.GET.get('next', '')})

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')

        if User.objects.filter(username=username).exists():
            return render(request, 'register.html',
                          {'error': 'Ushbu foydalanuvchi nomi allaqachon mavjud.', 'next': next_url})

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        if next_url:
            return redirect(next_url)
        return redirect('home')


class UserLoginView(View):
    def get(self, request):
        return render(request, 'login.html', {'next': request.GET.get('next', '')})

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect('home')
        return render(request, 'login.html', {'error': 'Foydalanuvchi nomi yoki parol xato!', 'next': next_url})


class UserLogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('home')



class CustomerEventListView(View):
    def get(self, request):
        events = Event.objects.filter(is_active=True).order_by('date')
        return render(request, 'home.html', {'events': events})


class TicketPurchasePageView(LoginRequiredMixin, View):
    def get(self, request, event_id):
        event = get_object_or_404(Event, id=event_id, is_active=True)
        return render(request, 'ticket_purchase.html', {'event': event})


import environ
from django.views import View
from django.shortcuts import render, get_object_or_404

env = environ.Env()


class FakePaymentView(LoginRequiredMixin, View):
    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.is_expired():
            order.status = 'EXPIRED'
            order.save()

        real_bank_url = env('YOUR_REAL_BANK_P2P_URL', default='')

        context = {
            'amount': order.total_amount,
            'order_id': order.id,
            'bank_url': real_bank_url,
            'order': order,
        }
        return render(request, 'fake_payment.html', context)

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        if order.status == 'PAID':
            return redirect('my_tickets')
        try:
            confirm_fake_payment_service(order.id)
        except ValidationError as e:
            return render(request, 'fake_payment.html', {
                'amount': order.total_amount,
                'order_id': order.id,
                'bank_url': env('YOUR_REAL_BANK_P2P_URL', default=''),
                'order': order,
                'error': str(e.detail) if hasattr(e, 'detail') else str(e),
            })
        except Order.DoesNotExist:
            return redirect('home')
        return redirect('my_tickets')


class MyTicketsView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'my_tickets.html'
    context_object_name = 'tickets'

    def get_queryset(self):
        return Ticket.objects.filter(order__user=self.request.user, order__status='PAID').order_by('-created_at')



class EventSeatListView(APIView):
    def get(self, request, event_id, sector_number):
        release_expired_reservations()
        sector = get_object_or_404(StadiumSector, name=str(sector_number))
        seats = (
            EventSeat.objects
            .filter(event_id=event_id, seat__sector=sector)
            .select_related('seat')
            .order_by('seat__row_number', 'seat__seat_number')
        )
        data = CustomerEventSeatListSerializer(seats, many=True).data
        return Response(data)


class ReserveSeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        event_seat_ids = request.data.get('event_seat_ids', [])
        if not event_seat_ids:
            return Response({"error": "Sektor ichidan kamida bitta o'rindiq tanlang."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            order = reserve_seats_service(request.user, event_seat_ids)
            return Response({"status": "success", "order_id": str(order.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CheckTicketQRAPIView(APIView):
    permission_classes = []

    def post(self, request):
        ticket_uid = request.data.get('ticket_uid')
        if not ticket_uid:
            return Response({"status": "error", "message": "QR-kod ma'lumoti chala!"},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ticket = Ticket.objects.filter(ticket_uid=ticket_uid).select_related('event_seat__event',
                                                                                 'event_seat__seat__sector').first()

            if not ticket:
                return Response({"status": "error", "message": "BU CHIPTA SOXTA! Bazadan topilmadi."},
                                status=status.HTTP_404_NOT_FOUND)

            if ticket.is_used:
                return Response({
                    "status": "error",
                    "message": "KIRISH TAQIQLANADI! Ushbu chipta bilan allaqachon stadionga kirilgan."
                }, status=status.HTTP_400_BAD_REQUEST)

            ticket.is_used = True
            ticket.save()

        return Response({
            "status": "success",
            "message": "Ruxsat berildi!",
            "event": ticket.event_seat.event.title,
            "seat": f"Sektor: {ticket.event_seat.seat.sector.name}, Qator: {ticket.event_seat.seat.row_number}, Joy: {ticket.event_seat.seat.seat_number}"
        }, status=status.HTTP_200_OK)


class AdminDashboardEventCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        title = request.data.get('title')
        description = request.data.get('description', '')
        date = request.data.get('date')
        sector_prices = request.data.get('sector_prices', {})

        if not title or not date:
            return Response({"error": "Uchrashuv nomi va vaqti majburiy!"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            event = Event.objects.create(title=title, description=description, date=date)
            all_seats = Seat.objects.all().select_related('sector')

            event_seats = []
            for seat in all_seats:
                sector_name = seat.sector.name
                price = (
                        sector_prices.get(f"{sector_name}-sektor") or
                        sector_prices.get(sector_name) or
                        getattr(seat.sector.group, 'default_price', 50000.00)
                )

                event_seats.append(
                    EventSeat(
                        event=event,
                        seat=seat,
                        price=float(price),
                        status='AVAILABLE'
                    )
                )

            EventSeat.objects.bulk_create(event_seats)

        return Response({"message": f"Yangi uchrashuv va {len(event_seats)} ta chipta generatsiya qilindi."},
                        status=status.HTTP_201_CREATED)


class AdminDashboardEventListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        events = Event.objects.all().order_by('-date')
        return Response([{"id": e.id, "title": e.title, "date": e.date.strftime("%Y-%m-%d %H:%M")} for e in events])


class AdminSectorGroupConfigView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        groups = [{"id": g.id, "name": g.name, "color_class": g.color_class, "default_price": float(g.default_price),
                   "sector_ids": list(g.sectors.values_list('id', flat=True))} for g in SectorGroup.objects.all()]
        sectors = [{"id": s.id, "name": s.name, "group_id": s.group_id} for s in StadiumSector.objects.all()]
        return Response({"groups": groups, "sectors": sectors})

    def post(self, request):
        name = request.data.get('name')
        color_class = request.data.get('color_class')
        sector_ids = request.data.get('sector_ids', [])

        group, _ = SectorGroup.objects.update_or_create(name=name, defaults={"color_class": color_class})
        if sector_ids:
            StadiumSector.objects.filter(id__in=sector_ids).update(group=group)
        return Response({"message": "Saqlandi"})

class DownloadTicketPDFView(LoginRequiredMixin, View):
    def get(self, request, ticket_uid):
            ticket = get_object_or_404(
                Ticket.objects.select_related('event_seat__seat__sector', 'event_seat__event', 'order__user'),
                ticket_uid=ticket_uid,
                order__user=request.user,
            )

            context = {
                'ticket': ticket,
                'event': ticket.event_seat.event,
                'seat': ticket.event_seat.seat,
                'sector': ticket.event_seat.seat.sector,
            }

            pdf = render_to_pdf('ticket_pdf_template.html', context)

            if pdf:
                response = pdf
                filename = f"Chipta_Sektor_{ticket.event_seat.seat.sector.name}_Joy_{ticket.event_seat.seat.seat_number}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

            return HttpResponse("❌ PDF fayl generatsiya qilishda xatolik yuz berdi.", status=400)

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
        template_name = 'dashboard.html'

        def test_func(self):
            return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)

        def handle_no_permission(self):
            if self.request.user.is_authenticated:
                return redirect('/?error=Sizda_admin_panelga_kirish_huquqi_yoq')

            return redirect('/auth/login/?next=/dashboard/')



class GateScannerView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'scanner.html'

    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            return redirect('/?error=Sizda_darvoza_nazorati_tizimiga_kirish_huquqi_yoq')

        return redirect('/auth/login/?next=/gate-control/scanner/')


