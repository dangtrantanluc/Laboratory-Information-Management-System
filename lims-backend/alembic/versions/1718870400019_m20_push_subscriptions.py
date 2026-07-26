"""M20 — Web Push (VAPID): push_subscriptions.

Đăng ký thiết bị/trình duyệt của user để gửi popup thông báo desktop qua
Web Push API. Không cần RBAC riêng — STRICT SELF (user_id == current user),
giống pattern notifications.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400019"
down_revision: Union[str, None] = "1718870400018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            endpoint     TEXT NOT NULL,
            p256dh       TEXT NOT NULL,
            auth         TEXT NOT NULL,
            user_agent   VARCHAR(255),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_push_sub_endpoint UNIQUE (endpoint)
        );
        CREATE INDEX IF NOT EXISTS idx_push_sub_user ON push_subscriptions(user_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS push_subscriptions CASCADE;")
