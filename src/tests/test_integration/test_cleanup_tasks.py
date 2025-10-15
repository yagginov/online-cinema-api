from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from celery_background.tasks.auth_tasks import (
    cleanup_expired_activation_tokens,
    cleanup_expired_password_reset_tokens,
    cleanup_expired_refresh_tokens,
)
from database.models.accounts import (
    ActivationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserGroup,
    UserGroupEnum,
)
from security import hash_password


class TestCleanupActivationTokens:

    def test_cleanup_no_expired_tokens(self, sync_db_session: Session):
        group = UserGroup(name=UserGroupEnum.USER)
        sync_db_session.add(group)
        sync_db_session.commit()

        user = User(
            email="test@test.com",
            _hashed_password=hash_password("Pass123!"),
            is_active=False,
            group_id=group.id,
        )
        sync_db_session.add(user)
        sync_db_session.commit()

        valid_token = ActivationToken(
            user_id=user.id,
            token="valid_token",
            expires_at=datetime(2030, 12, 31, tzinfo=timezone.utc),
        )
        sync_db_session.add(valid_token)
        sync_db_session.commit()

        with patch("celery_background.tasks.auth_tasks.sync_postgresql_engine", sync_db_session.bind):
            result = cleanup_expired_activation_tokens()

        assert result["status"] == "success"
        assert result["deleted"] == 0
        assert result["type"] == "activation_tokens"

        tokens_count = sync_db_session.scalar(select(func.count()).select_from(ActivationToken))
        assert tokens_count == 1

    def test_cleanup_expired_tokens_only(self, sync_db_session: Session):
        group = UserGroup(name=UserGroupEnum.USER)
        sync_db_session.add(group)
        sync_db_session.commit()

        user1 = User(
            email="expired@test.com",
            _hashed_password=hash_password("Pass123!"),
            is_active=False,
            group_id=group.id,
        )
        sync_db_session.add(user1)
        sync_db_session.commit()

        expired_token = ActivationToken(
            user_id=user1.id,
            token="expired_token",
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        sync_db_session.add(expired_token)
        sync_db_session.commit()

        user2 = User(
            email="valid@test.com",
            _hashed_password=hash_password("Pass123!"),
            is_active=False,
            group_id=group.id,
        )
        sync_db_session.add(user2)
        sync_db_session.commit()

        valid_token = ActivationToken(
            user_id=user2.id,
            token="valid_token",
            expires_at=datetime(2030, 12, 31, tzinfo=timezone.utc),
        )
        sync_db_session.add(valid_token)
        sync_db_session.commit()

        with patch(
            "celery_background.tasks.auth_tasks.sync_postgresql_engine",
            sync_db_session.bind,
        ):
            result = cleanup_expired_activation_tokens()

        assert result["deleted"] == 1

        tokens = sync_db_session.scalars(select(ActivationToken)).all()
        assert len(tokens) == 1
        assert tokens[0].token == "valid_token"

    def test_cleanup_multiple_expired_tokens(self, sync_db_session: Session):
        group = UserGroup(name=UserGroupEnum.USER)
        sync_db_session.add(group)
        sync_db_session.commit()

        expired_dates = [
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2020, 2, 1, tzinfo=timezone.utc),
            datetime(2020, 3, 1, tzinfo=timezone.utc),
        ]

        for i, exp_date in enumerate(expired_dates):
            user = User(
                email=f"test{i}@test.com",
                _hashed_password=hash_password("Pass123!"),
                is_active=False,
                group_id=group.id,
            )
            sync_db_session.add(user)
            sync_db_session.commit()

            token = ActivationToken(
                user_id=user.id,
                token=f"expired_token_{i}",
                expires_at=exp_date,
            )
            sync_db_session.add(token)
            sync_db_session.commit()

        with patch(
            "celery_background.tasks.auth_tasks.sync_postgresql_engine",
            sync_db_session.bind,
        ):
            result = cleanup_expired_activation_tokens()

        assert result["deleted"] == 3
        tokens_count = sync_db_session.scalar(select(func.count()).select_from(ActivationToken))
        assert tokens_count == 0


class TestCleanupPasswordResetTokens:

    def test_cleanup_expired_password_tokens(self, sync_db_session: Session):
        group = UserGroup(name=UserGroupEnum.USER)
        sync_db_session.add(group)
        sync_db_session.commit()

        user = User(
            email="test@test.com",
            _hashed_password=hash_password("Pass123!"),
            is_active=False,
            group_id=group.id,
        )
        sync_db_session.add(user)
        sync_db_session.commit()

        expired_token = PasswordResetToken(
            user_id=user.id, token="expired_reset_token", expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
        sync_db_session.add(expired_token)
        sync_db_session.commit()

        with patch("celery_background.tasks.auth_tasks.sync_postgresql_engine", sync_db_session.bind):
            result = cleanup_expired_password_reset_tokens()

        assert result["status"] == "success"
        assert result["deleted"] == 1
        assert result["type"] == "password_reset_tokens"


class TestCleanupRefreshTokens:

    def test_cleanup_expired_refresh_tokens(self, sync_db_session: Session):
        group = UserGroup(name=UserGroupEnum.USER)
        sync_db_session.add(group)
        sync_db_session.commit()

        user = User(
            email="test@test.com",
            _hashed_password=hash_password("Pass123!"),
            is_active=False,
            group_id=group.id,
        )
        sync_db_session.add(user)
        sync_db_session.commit()

        expired_token = RefreshToken(
            user_id=user.id,
            token="expired_refresh_token",
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        sync_db_session.add(expired_token)
        sync_db_session.commit()

        with patch("celery_background.tasks.auth_tasks.sync_postgresql_engine", sync_db_session.bind):
            result = cleanup_expired_refresh_tokens()

        assert result["status"] == "success"
        assert result["deleted"] == 1
        assert result["type"] == "refresh_tokens"


class TestCleanupTasksErrorHandling:

    def test_cleanup_handles_database_error(self):
        with patch("celery_background.tasks.auth_tasks.Session") as mock_session:
            mock_session.return_value.__enter__.return_value.execute.side_effect = Exception("DB Error")

            with pytest.raises(Exception, match="DB Error"):
                cleanup_expired_activation_tokens()
