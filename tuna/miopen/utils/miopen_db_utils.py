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
"""Utility module for miopem solver helper functions"""

import logging
import random
from time import sleep

from typing import Callable, Any
import pymysql
from sqlalchemy.exc import IntegrityError, OperationalError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.miopen_tables import Solver
from tuna.utils.logger import setup_logger
from tuna.utils.metadata import NUM_SQL_RETRIES

LOGGER = setup_logger('miopen_db_utility')


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


def session_retry(session: DbSession,
                  callback: Callable,
                  actuator: Callable,
                  logger: logging.Logger = LOGGER) -> Any:
  """retry handling for a callback function using an actuator (lamda function with params)"""
  for idx in range(NUM_SQL_RETRIES):
    try:
      return actuator(callback)
    except OperationalError as error:
      logger.warning('%s, DB contention sleeping (%s)...', error, idx)
      session.rollback()
      sleep(random.randint(1, 30))
    except pymysql.err.OperationalError as error:
      logger.warning('%s, DB contention sleeping (%s)...', error, idx)
      session.rollback()
      sleep(random.randint(1, 30))
    except IntegrityError as error:
      logger.error('Query failed: %s', error)
      session.rollback()
      return False

  logger.error('All retries have failed.')
  return False
