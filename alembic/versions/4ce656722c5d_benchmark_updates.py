"""benchmark_updates

Revision ID: 4ce656722c5d
Revises: 054211043da5
Create Date: 2022-11-04 09:09:25.819380

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision = '4ce656722c5d'
down_revision = '054211043da5'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.drop_column('conv_config_tags', "model")
  op.add_column('benchmark',
                Column('config', Integer, ForeignKey('conv_config.id')))
  op.rename_table('benchmark', 'conv_benchmark')
  op.drop_unique_constraint('uq_idx', 'benchmark')
  op.create_unique_constraint(
      "uq_idx", "conv_benchmark",
      ["framework", "model", "batchsize", "gpu_number", "config"])

  op.create_table(
      'bn_benchmark',
      sa.Column('id', sa.Integer, primary_key=True),
      sa.Column('insert_ts',
                DateTime,
                nullable=False,
                server_default=sqla_func.now()),
      sa.Column(
          'update_ts',
          DateTime,
          nullable=False,
          server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
      sa.Column('valid', TINYINT(1), nullable=False, server_default="1"),
      sa.Column('framework',
                Integer,
                ForeignKey("framework.id"),
                nullable=False),
      sa.Column('model', Integer, ForeignKey("model.id"), nullable=False),
      sa.Column('batchsize', Integer, nullable=False, server_default="32"),
      sa.Column('gpu_number', Integer, nullable=True, server_default="1"),
      sa.Column('driver_cmd', String(length=128), nullable=False),
      sa.Column('config', Integer, ForeignKey("bn_config.id"), nullable=False),
  )
  op.create_unique_constraint(
      "uq_idx", "bn_benchmark",
      ["framework", "model", "batchsize", "gpu_number", "config"])


def downgrade() -> None:
  op.drop_constraint("benchmark_ibfk_3", "benchmark", type_="foreignkey")
  op.drop_column('benchmark', "config")
  op.add_column('conv_config_tags',
                Column('model', Integer, ForeignKey('model.id')))
  op.rename_table('conv_benchmark', 'benchmark')
  op.drop_table('bn_bechmark')
