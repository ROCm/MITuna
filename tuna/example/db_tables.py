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
from tuna.example.example_tables import get_tables
from tuna.db_engine import ENV_VARS, ENGINE
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars

#pylint: disable=too-few-public-methods
LOGGER = setup_logger('db_tables')
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

  return True


def main():
  """Main script function"""
  #setup MIOpen DB
  ret_t = create_tables(get_tables())
  LOGGER.info('DB creation successful: %s', ret_t)


if __name__ == '__main__':
  main()
