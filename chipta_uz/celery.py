import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chipta_uz.settings')

app = Celery('chipta_uz')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'cleanup-expired-reservations-every-2-minutes': {
        'task': 'ilova.tasks.cleanup_expired_reservations',
        'schedule': crontab(minute='*/2'),
    },
}
