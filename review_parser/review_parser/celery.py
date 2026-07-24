import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from datetime import timedelta


load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'review_parser.settings')

app = Celery('review_parser')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.result_backend = 'django-db'
app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_retry = True
app.conf.broker_connection_max_retries = 1


app.conf.broker_transport_options = {
    'visibility_timeout': 3600, 
    'socket_connect_timeout': 10, 
    'socket_keepalive': True,     
    'retry_on_timeout': True,    
    'max_retries': 3,             
}
# Настройка периодических задач
app.conf.beat_schedule = {
    'weekly-sunday-6am-task': {
        'task': 'common_parser.tasks.weekly_parsing',
        'schedule': crontab(hour=6, minute=0, day_of_week='sun'),
    },
    # Disable cleanup task by scheduling to run every ~1000 years
    'backend_cleanup': {
        'task': 'celery.backend_cleanup',
        'schedule': timedelta(days=365*1000),
        'relative': True,
    },
}


app.autodiscover_tasks()