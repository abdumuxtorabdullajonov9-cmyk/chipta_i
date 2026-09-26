from django.urls import path
from .views import (
    AdminDashboardEventCreateView,
    AdminDashboardEventListView,
    AdminSectorGroupConfigView,
    ReserveSeatView,
    DownloadTicketPDFView,
    EventSeatListView,
)

urlpatterns = [
    path('admin-dashboard/events/create/', AdminDashboardEventCreateView.as_view(), name='admin_event_create'),
    path('admin-dashboard/events/', AdminDashboardEventListView.as_view(), name='admin_event_list'),
    path('admin-dashboard/groups/config/', AdminSectorGroupConfigView.as_view(), name='admin_groups_config'),
    path('tickets/<uuid:ticket_uid>/download-pdf/', DownloadTicketPDFView.as_view(), name='download_ticket_pdf'),
    path('tickets/reserve/', ReserveSeatView.as_view(), name='ticket_reserve'),
    path('events/<int:event_id>/sectors/<int:sector_number>/seats/', EventSeatListView.as_view(),
         name='event_sector_seats'),
]
