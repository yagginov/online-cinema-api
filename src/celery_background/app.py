from typing import cast

from celery import Celery
from celery.schedules import crontab

from config import Settings, get_settings

settings = cast(Settings, get_settings())

celery_app = Celery(
    "online_cinema",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "cleanup-activation-tokens-daily": {
        "task": "cleanup_expired_activation_tokens",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup-password-reset-tokens-daily": {
        "task": "cleanup_expired_password_reset_tokens",
        "schedule": crontab(hour=2, minute=15),
    },
    "cleanup-refresh-tokens-daily": {
        "task": "cleanup_expired_refresh_tokens",
        "schedule": crontab(hour=2, minute=30),
    },
}