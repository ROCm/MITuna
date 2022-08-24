#Copyright 2009-2021 Sony Pictures Imageworks, Inc. and
#Industrial Light and Magic, a division of Lucasfilm Entertainment Company Ltd.

"""create account table

Revision ID: 3dc38e5e11c3
Revises: 
Create Date: 2022-08-23 14:17:57.009323

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3dc38e5e11c3'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
  #op.add_column('conv_job', sa.Column('last_transaction_date', sa.DateTime))
  pass


def downgrade() -> None:
  pass
