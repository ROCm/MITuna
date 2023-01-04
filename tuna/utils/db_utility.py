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
from time import sleep
import pymysql
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy import create_engine

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.miopen_tables import Solver
from tuna.utils.logger import setup_logger
from tuna.metadata import NUM_SQL_RETRIES

LOGGER = setup_logger('db_utility')

ENV_VARS = get_env_vars()

ENGINE = create_engine(f"mysql+pymysql://{ENV_VARS['user_name']}:{ENV_VARS['user_password']}" +\
                         f"@{ENV_VARS['db_hostname']}:3306/{ENV_VARS['db_name']}",
                       encoding="utf8")


def connect_db():
  """Create DB if it doesnt exist"""
  db_name = None
  if 'TUNA_DB_NAME' in os.environ:
    db_name = os.environ['TUNA_DB_NAME']
  else:
    raise ValueError('DB name must be specified in env variable: TUNA_DB_NAME')

  try:
    ENGINE.execute(f'Use {db_name}')
    return
  except OperationalError:  # as err:
    LOGGER.warning('Database %s does not exist, attempting to create database',
                   db_name)

  try:
    ENGINE.execute(f'Create database if not exists {db_name}')
  except OperationalError as err:
    LOGGER.error('Database creation failed %s for username: %s', err,
                 ENV_VARS['user_name'])
  ENGINE.execute(f'Use {db_name}')
  ENGINE.execute('SET GLOBAL max_allowed_packet=4294967296')


def create_tables(all_tables):
  """Function to create or sync DB tables/triggers"""
  #pylint: disable=too-many-locals
  connect_db()
  for table in all_tables:
    try:
      table.__table__.create(ENGINE)
      LOGGER.info("Created: %s", table.__tablename__)

    except (OperationalError, ProgrammingError) as err:
      LOGGER.warning('Err occurred %s \n For table: %s.', err, table)
      LOGGER.warning(
          'Schema migration not implemented, please udpate schema manually')
      continue

  return True


def create_indices(all_indices):
  """Create indices from index list"""
  with ENGINE.connect() as conn:
    for idx in all_indices:
      try:
        conn.execute(idx)
        LOGGER.info('Idx created successfully: %s', idx)
      except (OperationalError, ProgrammingError) as oerr:
        LOGGER.info('%s \n', oerr)
        continue


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


def insert_session(session_obj):
  """Insert new session obj and return its id"""
  with DbSession() as session:
    try:
      session.add(session_obj)
      session.commit()
      LOGGER.info('Added new session_id: %s', session_obj.id)
    except IntegrityError as err:
      LOGGER.warning("Err occurred trying to add new session: %s \n %s", err,
                     session_obj)
      session.rollback()
      entry = session_obj.get_query(session, Session, session_obj).one()
      return entry.id

  return session_obj.id


class DB_Type(enum.Enum):  # pylint: disable=invalid-name ; @chris rename, maybe?
  """@alex defines the types of databases produced in tuning sessions?"""
  FIND_DB = 1
  KERN_DB = 2
  PERF_DB = 3
