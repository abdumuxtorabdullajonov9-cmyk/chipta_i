"""
URL configuration for chipta_uz project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from ilova.views import (
    CustomerEventListView,
    AdminDashboardView,
    MyTicketsView,
    FakePaymentView,
    TicketPurchasePageView,
    UserRegisterView,
    UserLoginView,
    UserLogoutView, GateScannerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('ilova.urls')),
    path('', CustomerEventListView.as_view(), name='home'),
    path('dashboard/', AdminDashboardView.as_view(), name='dashboard_page'),
    path('ticket-3d/<int:event_id>/', TicketPurchasePageView.as_view(), name='ticket_3d_page'),
    path('accounts/', include('allauth.urls')),
    path('auth/register/', UserRegisterView.as_view(), name='register'),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('auth/logout/', UserLogoutView.as_view(), name='logout'),
    path('my-tickets/', MyTicketsView.as_view(), name='my_tickets'),
    path('orders/pay-fake/<uuid:order_id>/', FakePaymentView.as_view(), name='fake_payment'),
    path('gate-control/scanner/', GateScannerView.as_view(), name='gate_scanner'),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]