"""gemmgemm_config transC transO gemmO

Revision ID: a1b2c3d4e5f6
Revises: 4ce656722c5d
Create Date: 2026-03-05

Add transpose_C, transpose_O, gemm_o to rocmlir_gemmgemm_config for compatibility
with rocMLIR tier1-gemmgemm-configs format (-transC, -transO, -gemmO).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '4ce656722c5d'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
      'rocmlir_gemmgemm_config',
      sa.Column('transpose_C', sa.Boolean(), nullable=False, server_default='0'))
  op.add_column(
      'rocmlir_gemmgemm_config',
      sa.Column('transpose_O', sa.Boolean(), nullable=False, server_default='0'))
  op.add_column(
      'rocmlir_gemmgemm_config',
      sa.Column('gemm_o', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
  op.drop_column('rocmlir_gemmgemm_config', 'gemm_o')
  op.drop_column('rocmlir_gemmgemm_config', 'transpose_O')
  op.drop_column('rocmlir_gemmgemm_config', 'transpose_C')
