"""add candidate_cards to day_plans

Revision ID: c4d2f6a8b001
Revises: b3c1d5e7a902
Create Date: 2026-09-10 12:00:00.000000

候选景点池：承载「已推荐 / 手动添加但未加入路线」的卡片，使其退出单日计划再进入时
仍可恢复（此前仅 attractions 落库，未入路线的卡片刷新即丢失）。
字段为 JSON 文本，读取时由 DayPlanOut 反序列化为景点对象数组。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d2f6a8b001"
down_revision: Union[str, None] = "b3c1d5e7a902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "day_plans",
        sa.Column("candidate_cards", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("day_plans", "candidate_cards")
