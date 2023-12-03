
#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2022 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
""" Module for defining Solver and model enums  """

from sqlalchemy import Column, String, UniqueConstraint
from sqlalchemy import Enum
from sqlalchemy.dialects.mysql import TINYINT
from tuna.dbBase.base_class import BASE
from tuna.miopen.utils.config_type import ConfigType

class Solver(BASE):
  """Represents solver table"""
  __tablename__ = "solver"
  __table_args__ = (UniqueConstraint("solver", name="uq_idx"),)

  solver = Column(String(length=128), unique=True, nullable=False)
  tunable = Column(TINYINT(1), nullable=False, server_default="1")
  config_type = Column(Enum(ConfigType),
                       nullable=False,
                       server_default="convolution")
  is_dynamic = Column(TINYINT(1), nullable=False, server_default="0")

def get_id_solvers():
  """DB solver id to name map"""
  solver_id_map_c = {}
  solver_id_map_h = {}
  with DbSession() as session:
    query = session.query(Solver.solver, Solver.id).filter(Solver.valid == 1)
    res = session_retry(session, query.all, lambda x: x(), LOGGER)
    for slv, sid in res:
      solver_id_map_c[slv] = sid
      solver_id_map_h[slv.replace(', ', '-')] = sid
    id_solver_map_c = {val: key for key, val in solver_id_map_c.items()}
    id_solver_map_h = {val: key for key, val in solver_id_map_h.items()}

  return id_solver_map_c, id_solver_map_h


def get_solver_ids():
  """DB solver name to id map"""
  # TODO: Get this info from the SQLAlchemy class  # pylint: disable=fixme
  solver_id_map = {}
  with DbSession() as session:
    query = session.query(Solver.solver, Solver.id).filter(Solver.valid == 1)
    res = session_retry(session, query.all, lambda x: x(), LOGGER)
    for slv, sid in res:
      solver_id_map[slv] = sid
      solver_id_map[slv.replace(', ', '-')] = sid

  return solver_id_map