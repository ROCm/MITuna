"""conv_mode_to_mode

Revision ID: f3c8db790f9e
Revises: 3dc38e5e11c3
Create Date: 2022-09-23 15:18:55.221619

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f3c8db790f9e'
down_revision = '3dc38e5e11c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.alter_column('conv_config',
                  'conv_mode',
                  new_column_name='mode',
                  existing_type=sa.VARCHAR(40),
                  nullable=False,
                  server_default="conv")


def downgrade() -> None:
  pass
