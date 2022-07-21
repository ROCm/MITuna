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
""" Module for creating DB tables"""
import os
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy import create_engine
from tuna.miopen_tables import get_miopen_tables
from tuna.miopen_db_helpers import get_miopen_triggers, drop_miopen_triggers
from tuna.miopen_db_helpers import get_miopen_indices
from tuna.db_engine import ENV_VARS, ENGINE
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars

#pylint: disable=too-few-public-methods
LOGGER = setup_logger('db_tables')
ENV_VARS = get_env_vars()
ENGINE = create_engine("mysql+pymysql://{}:{}@{}:3306/{}".format(
    ENV_VARS['user_name'], ENV_VARS['user_password'], ENV_VARS['db_hostname'],
    ENV_VARS['db_name']),
                       encoding="utf8")


def connect_db():
  """Create DB if it doesnt exist"""
  db_name = None
  if 'TUNA_DB_NAME' in os.environ:
    db_name = os.environ['TUNA_DB_NAME']
  else:
    raise ValueError('DB name must be specified in env variable: TUNA_DB_NAME')

  try:
    ENGINE.execute('Use {}'.format(db_name))
    return
  except OperationalError:  # as err:
    LOGGER.warning('Database %s does not exist, attempting to create database',
                   db_name)

  try:
    ENGINE.execute('Create database if not exists {}'.format(db_name))
  except OperationalError as err:
    LOGGER.error('Database creation failed %s for username: %s', err,
                 ENV_VARS['user_name'])
  ENGINE.execute('Use {}'.format(db_name))
  ENGINE.execute('SET GLOBAL max_allowed_packet=4294967296')


def recreate_triggers(drop_triggers, create_triggers):
  """Drop and recreate triggers"""

  with ENGINE.connect() as conn:
    for dtg in drop_triggers:
      conn.execute("drop trigger if exists {}".format(dtg))
    for trg in create_triggers:
      try:
        conn.execute(trg)
      except OperationalError as oerr:
        LOGGER.warning("Operational Error occured while adding trigger: '%s'",
                       trg)
        LOGGER.info('%s \n', oerr)
        continue

  return True


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

  return True


def main():
  """Main script function"""
  #setup MIOpen DB
  ret_t = create_tables(get_miopen_tables())
  LOGGER.info('DB creation successful: %s', ret_t)
  ret_idx = create_indices(get_miopen_indices())
  LOGGER.info('DB Index creation successful: %s', ret_idx)
  recreate_triggers(drop_miopen_triggers(), get_miopen_triggers())


if __name__ == '__main__':
  main()
