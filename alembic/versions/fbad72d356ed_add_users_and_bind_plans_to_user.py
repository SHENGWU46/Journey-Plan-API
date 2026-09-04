"""add users and bind plans to user

Revision ID: fbad72d356ed
Revises: 0001_create_plans
Create Date: 2026-09-02 10:42:31.554674

变更内容：
1. 新建 users 表（username 唯一、password_hash bcrypt、created_at）。
2. plans.user_id 加索引；并加外键指向 users.id（可选，失败不阻断）。

兼容性处理：
- SQLite 不支持 ALTER TABLE ADD CONSTRAINT，必须用 batch_alter_table（copy-and-move）；
  直接使用 op.create_foreign_key 会抛 NotImplementedError。
- MySQL 的 batch 模式会退化为普通 ALTER，同样安全。
- 0001 迁移给 plans.user_id 带 server_default='1'，与新模型（无默认值）会在
  autogenerate 下产生差异；这里显式清掉该默认值，避免后续 alembic check 报漂移。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fbad72d356ed"
down_revision: Union[str, None] = "0001_create_plans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )

    op.create_index(op.f("ix_plans_user_id"), "plans", ["user_id"], unique=False)

    # batch 模式：SQLite 走建新表+搬数据+重命名，MySQL 走 ALTER，两端均可用。
    # recreate="always" 让 MySQL 也走重建，确保 server_default 被真正清除。
    with op.batch_alter_table("plans", recreate="always") as batch_op:
        batch_op.alter_column("user_id", server_default=None)
        batch_op.create_foreign_key(
            op.f("fk_plans_user_id_users"), "users", ["user_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("plans", recreate="always") as batch_op:
        batch_op.drop_constraint(op.f("fk_plans_user_id_users"), type_="foreignkey")
        # 回退到 0001 的默认值，保证 down→up 可逆
        batch_op.alter_column("user_id", server_default=sa.text("1"))

    op.drop_index(op.f("ix_plans_user_id"), table_name="plans")
    op.drop_table("users")
