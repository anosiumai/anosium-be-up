"""remove_clinic_id_from_appointments

Revision ID: 8b732f780191
Revises: None
Create Date: 2026-02-17 23:41:44.636517

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '8b732f780191'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = [col['name'] for col in inspect(bind).get_columns('appointments')]
    if 'clinic_id' in columns:
        op.drop_column('appointments', 'clinic_id')


def downgrade() -> None:
    bind = op.get_bind()
    columns = [col['name'] for col in inspect(bind).get_columns('appointments')]
    if 'clinic_id' not in columns:
        op.add_column('appointments', sa.Column('clinic_id', sa.Integer(), nullable=True))