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
import types
from time import sleep
from datetime import datetime
import pymysql
from sqlalchemy.exc import OperationalError, IntegrityError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.dbBase.base_class import BASE
from tuna.miopen.miopen_tables import Solver
from tuna.utils.logger import setup_logger
from tuna.metadata import NUM_SQL_RETRIES

LOGGER = setup_logger('db_utility')


def get_solver_ids():
  """DB solver name to id map"""
  # TODO: Get this info from the SQLAlchemy class  # pylint: disable=fixme
  solver_id_map = {}
  with DbSession() as session:
    query = session.query(Solver.solver, Solver.id).filter(Solver.valid == 1)
    for slv, sid in query.all():
      solver_id_map[slv] = sid
      solver_id_map[slv.replace(', ', '-')] = sid

  return solver_id_map


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
    except IntegrityError as error:
      logger.error('Query failed: %s', error)
      session.rollback()
      return False

  logger.error('All retries have failed.')
  return False


def gen_update_query(obj, attribs, tablename):
  """Create a query string updating all attributes for the input object"""
  set_arr = []
  for attr in attribs:
    val = getattr(obj, attr)
    if val is None:
      val='NULL'
    elif isinstance(val, str) or isinstance(val, datetime):
      val=f"'{val}'"
    set_arr.append(f"{attr}={val}" )

  set_str = ','.join(set_arr)
  query = f"update {tablename} set {set_str}"\
          f" where id={obj.id};"
  return query

def gen_select_objs(session, attribs, tablename, cond_str):
  """create a select query and generate name space objects for the results"""
  attr_str = ','.join(attribs)
  query = f"select {attr_str} from {tablename}"\
          f" {cond_str};"
  #LOGGER.info('Query Select: %s', query)
  ret = session.execute(query)
  entries = []
  for row in ret:
    #LOGGER.info('select_row: %s', row)
    entry = types.SimpleNamespace()
    for i, col in enumerate(attribs):
      setattr(entry, col, row[i])
    entries.append(entry)
  return entries

def has_attr_set(obj, attribs):
  """test if a namespace as the supplied attributes"""
  for attr in attribs:
    if not hasattr(obj, attr):
      return False
  return True

def get_class_by_tablename(tablename):
  """use tablename to find class"""
  for c in BASE._decl_class_registry.values():
    if hasattr(c, '__tablename__') and c.__tablename__ == tablename:
      return c

class DB_Type(enum.Enum):  # pylint: disable=invalid-name ; @chris rename, maybe?
  """@alex defines the types of databases produced in tuning sessions?"""
  FIND_DB = 1
  KERN_DB = 2
  PERF_DB = 3
