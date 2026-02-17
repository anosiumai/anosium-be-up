"""remove_clinic_id_from_appointments

Revision ID: 8b732f780191
Revises: None
Create Date: 2026-02-17 23:41:44.636517

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '8b732f780191'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove ONLY clinic_id column from appointments table."""
    op.drop_column('appointments', 'clinic_id')


def downgrade() -> None:
    """Re-add clinic_id column to appointments table."""
    op.add_column(
        'appointments',
        sa.Column('clinic_id', sa.Integer(), nullable=True)
    )