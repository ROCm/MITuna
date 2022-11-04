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
  op.drop_constraint("conv_benchmark_perf_ibfk_1",
                     "conv_benchmark_perf",
                     type_="foreignkey")
  try:
    op.drop_constraint("conv_benchmark_perf_ibfk_4",
                       "conv_benchmark_perf",
                       type_="foreignkey")
  except OperationalError as oerr:
    continue
  op.drop_column('conv_benchmark_perf', "config")
  op.drop_column('conv_config_tags', "model")
  op.add_column('benchmark',
                Column('config', Integer, ForeignKey('conv_config.id')))


def downgrade() -> None:
  op.add_column('conv_benchmark_perf',
                Column('config', Integer, ForeignKey('conv_config.id')))
  op.create_foreign_key("conv_benchmark_perf_ibfk_1", "conv_benchmark_perf",
                        "conv_config", ["config"], ["id"])
  op.drop_constraint("conv_benchmark_perf_ibfk_4",
                     "conv_benchmark_perf",
                     type_="foreignkey")
  op.drop_constraint("benchmark_ibfk_3", "benchmark", type_="foreignkey")
  op.drop_column('benchmark', "config")
  op.add_column('conv_config_tags',
                Column('model', Integer, ForeignKey('model.id')))
