"""Initial schema - alla tabeller

Revision ID: 001
Revises: 
Create Date: 2026-06-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alla tabeller skapas via Base.metadata.create_all i seed.py
    # Den har migrationen markerar bara att vi har ett startschema
    pass


def downgrade() -> None:
    pass
