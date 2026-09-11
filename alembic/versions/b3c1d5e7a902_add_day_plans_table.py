"""add day_plans table

Revision ID: b3c1d5e7a902
Revises: fbad72d356ed
Create Date: 2026-09-06 10:00:00.000000

每日计划表（原型 STEP4 单日详情 FR-DY-02~06）：
每计划每天一条，存放 AI 生成的天气、用户自填的游玩时间/当日预算，
以及已选入路线的景点（JSON 数组文本）。约束命名遵循 Base.metadata 的
naming_convention，避免 autogenerate 产生假差异。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c1d5e7a902'
down_revision: Union[str, None] = 'fbad72d356ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'day_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('day_index', sa.Integer(), nullable=False),
        sa.Column('day_date', sa.Date(), nullable=False),
        sa.Column('weather', sa.String(length=50), nullable=True),
        sa.Column('tour_time', sa.String(length=50), nullable=True),
        sa.Column('daily_budget', sa.Integer(), nullable=True),
        sa.Column('attractions', sa.Text(), nullable=True),
        sa.Column('ai_generated', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_day_plans')),
        sa.ForeignKeyConstraint(
            ['plan_id'], ['plans.id'],
            name=op.f('fk_day_plans_plan_id_plans'),
        ),
        sa.UniqueConstraint(
            'plan_id', 'day_index',
            name=op.f('uq_day_plans_plan_id_day_index'),
        ),
    )
    op.create_index(
        op.f('ix_day_plans_plan_id'), 'day_plans', ['plan_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_day_plans_plan_id'), table_name='day_plans')
    op.drop_table('day_plans')
