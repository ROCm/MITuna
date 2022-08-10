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
"""Utility module for DB helper functions"""

import enum
import random
import pymysql
from time import sleep
from sqlalchemy.exc import OperationalError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen_tables import Solver
from tuna.utils.logger import setup_logger
from tuna.metadata import NUM_SQL_RETRIES

LOGGER = setup_logger('db_utility')


def get_id_solvers():
  """DB solver id to name map"""
  solver_id_map_c = {}
  solver_id_map_h = {}
  with DbSession() as session:
    query = session.query(Solver.solver, Solver.id).filter(Solver.valid == 1)
    for slv, sid in query.all():
      solver_id_map_c[slv] = sid
      solver_id_map_h[slv.replace(', ', '-')] = sid
    id_solver_map_c = {val: key for key, val in solver_id_map_c.items()}
    id_solver_map_h = {val: key for key, val in solver_id_map_h.items()}

  return id_solver_map_c, id_solver_map_h


def session_retry(session, callback, actuator, logger=LOGGER):
  """retry handling for a callback function using an actuator (lamda function with params)"""
  for idx in range(NUM_SQL_RETRIES):
    try:
      return actuator(callback)
    except OperationalError as error:
      logger.warning('%s, maybe DB contention sleeping (%s)...', error, idx)
      session.rollback()
      sleep(random.randint(1, 30))
    except pymysql.err.OperationalError as error:
      logger.warning('%s, maybe DB contention sleeping (%s)...', error, idx)
      session.rollback()
      sleep(random.randint(1, 30))

  logger.error('All retries have failed.')
  return None


class DB_Type(enum.Enum):
  FIND_DB = 1
  KERN_DB = 2
  PERF_DB = 3
