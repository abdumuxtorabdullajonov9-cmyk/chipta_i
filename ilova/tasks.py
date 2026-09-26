from celery import shared_task
from .services import release_expired_reservations


@shared_task
def cleanup_expired_reservations():
    release_expired_reservations()
