"""benchmark

Revision ID: 054211043da5
Revises: 219858383a66
Create Date: 2022-10-25 13:58:39.007795

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func as sqla_func
from sqlalchemy import Column, Integer, DateTime, text, ForeignKey, String
from tuna.miopen.benchmark import ModelEnum, FrameworkEnum
from sqlalchemy.dialects.mysql import TINYINT, DOUBLE, MEDIUMBLOB, LONGBLOB
from sqlalchemy import Float, BigInteger, String
from sqlalchemy import Enum

# revision identifiers, used by Alembic.
revision = '054211043da5'
down_revision = '219858383a66'
branch_labels = None
depends_on = None


def upgrade() -> None:
  #Model table
  op.create_table(
      'model',
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
      sa.Column('model', Enum(ModelEnum), nullable=False),
      sa.Column('version', Float, nullable=False),
  )
  op.create_unique_constraint("uq_idx", "model", ["model", "version"])

  #Framework table
  op.create_table(
      'framework',
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
      sa.Column('framework', Enum(FrameworkEnum), nullable=False),
  )
  op.create_unique_constraint("uq_idx", "framework", ["framework"])

  #Benchmark table
  op.create_table(
      'benchmark',
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
  )
  op.create_unique_constraint(
      "uq_idx", "benchmark",
      ["framework", "model", "batchsize", "gpu_number", "driver_cmd"])

  op.add_column('conv_config_tags',
                Column('model', Integer, ForeignKey('model.id')))
  op.add_column('bn_config_tags',
                Column('model', Integer, ForeignKey('model.id')))


def downgrade() -> None:
  op.drop_constraint("conv_config_tags_ibfk_2",
                     "conv_config_tags",
                     type_="foreignkey")
  op.drop_constraint("bn_config_tags_ibfk_2",
                     "bn_config_tags",
                     type_="foreignkey")
  op.drop_column('conv_config_tags', "model")
  op.drop_column('bn_config_tags', "model")
  op.drop_table('benchmark')
  op.drop_table('model')
  op.drop_table('framework')
