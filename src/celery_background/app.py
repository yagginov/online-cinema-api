from typing import cast

from celery import Celery

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
