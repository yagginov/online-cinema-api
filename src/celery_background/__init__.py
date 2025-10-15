from .app import celery_app
from .tasks import auth_tasks

__all__ = ["celery_app"]
