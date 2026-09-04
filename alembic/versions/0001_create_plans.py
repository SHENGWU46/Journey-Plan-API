"""create plans table

Revision ID: 0001_create_plans
Revises:
Create Date: 2026-09-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_create_plans'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('destination', sa.String(length=100), nullable=True),
        sa.Column('depart_date', sa.Date(), nullable=True),
        sa.Column('return_date', sa.Date(), nullable=True),
        sa.Column('people_count', sa.Integer(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('total_budget', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_plans')),
    )


def downgrade() -> None:
    op.drop_table('plans')
