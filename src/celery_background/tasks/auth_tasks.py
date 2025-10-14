from typing import Type

from sqlalchemy import delete, func
from sqlalchemy.orm import Session
from celery.utils.log import get_task_logger

from celery_background.app import celery_app
from database.session_postgresql import sync_postgresql_engine
from database.models.accounts import ActivationToken, PasswordResetToken, RefreshToken
from database.models.base import Base

logger = get_task_logger(__name__)


def _cleanup_expired_tokens(model_class: Type[Base], token_type: str) -> dict:
    with Session(sync_postgresql_engine) as session:
        result = session.execute(delete(model_class).where(model_class.expires_at < func.now()))
        session.commit()
        deleted_count = result.rowcount

    logger.info(f"Successfully deleted {deleted_count} expired {token_type}")
    return {"status": "success", "deleted": deleted_count, "type": token_type}


@celery_app.task(name="cleanup_expired_activation_tokens")
def cleanup_expired_activation_tokens():
    try:
        return _cleanup_expired_tokens(ActivationToken, "activation_tokens")
    except Exception as e:
        logger.error(f"Error cleaning up activation tokens: {str(e)}")
        raise


@celery_app.task(name="cleanup_expired_password_reset_tokens")
def cleanup_expired_password_reset_tokens():
    try:
        return _cleanup_expired_tokens(PasswordResetToken, "password_reset_tokens")
    except Exception as e:
        logger.error(f"Error cleaning up password reset tokens: {str(e)}")
        raise


@celery_app.task(name="cleanup_expired_refresh_tokens")
def cleanup_expired_refresh_tokens():
    try:
        return _cleanup_expired_tokens(RefreshToken, "refresh_tokens")
    except Exception as e:
        logger.error(f"Error cleaning up refresh tokens: {str(e)}")
        raise
