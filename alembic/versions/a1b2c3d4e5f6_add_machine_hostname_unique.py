"""add_machine_hostname_unique

Revision ID: a1b2c3d4e5f6
Revises: 219858383a66
Create Date: 2025-11-18 02:38:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '219858383a66'
branch_labels = None
depends_on = None


def upgrade() -> None:
  # First, remove any duplicate hostnames if they exist
  # Keep the oldest entry (lowest id) for each hostname
  op.execute("""
    DELETE m1 FROM machine m1
    INNER JOIN machine m2 
    WHERE m1.id > m2.id 
    AND m1.hostname = m2.hostname
  """)

  # Then add the unique constraint on hostname
  # Using prefix length of 255 since hostname is TEXT type
  op.create_index('idx_hostname',
                  'machine', ['hostname'],
                  unique=True,
                  mysql_length={'hostname': 255})


def downgrade() -> None:
  # Remove the unique constraint
  op.drop_index('idx_hostname', 'machine')
