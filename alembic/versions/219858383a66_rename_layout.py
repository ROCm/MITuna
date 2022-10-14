"""rename_layout

Revision ID: 219858383a66
Revises: f3c8db790f9e
Create Date: 2022-10-13 14:24:29.935681

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '219858383a66'
down_revision = 'f3c8db790f9e'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.alter_column('bn_config',
                  'out_layout',
                  new_column_name='in_layout',
                  existing_type=sa.VARCHAR(60),
                  nullable=False,
                  server_default="NCHW")
  op.add_column('conv_config', sa.Column('driver', sa.String(512)))
  op.add_column('bn_config', sa.Column('driver', sa.String(512)))


def downgrade() -> None:
  op.alter_column('bn_config',
                  'in_layout',
                  new_column_name='out_layout',
                  existing_type=sa.VARCHAR(60),
                  nullable=False,
                  server_default="NCHW")
  op.drop_column('conv_config', "driver")
  op.drop_column('bn_config', "driver")
