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

import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy import create_engine

from tuna.dbBase.sql_alchemy import DbConnection, DbSession
from tuna.utils.logger import setup_logger
from tuna.utils.utility import get_env_vars
from tuna.dbBase.base_class import BASE

LOGGER = setup_logger('test_db')
ENV_VARS = get_env_vars()

ENGINE = create_engine("mysql+pymysql://{}:{}@{}:3306/{}".format(
    ENV_VARS['user_name'], ENV_VARS['user_password'], ENV_VARS['db_hostname'],
    ENV_VARS['db_name']))


def connect_db():
  """Create DB if it does not exist"""
  db_name = ENV_VARS['db_name']
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


def test_create_table():
  connect_db()
  dummy_table = DUMMY_TABLE()
  try:
    dummy_table.__table__.create(ENGINE)
    LOGGER.info("Created: %s", dummy_table.__tablename__)

  except OperationalError as err:
    LOGGER.warning('Err occurred %s', err)
    LOGGER.warning('Failed to create table %s \n', dummy_table.__tablename__)


class DUMMY_TABLE(BASE):
  """Table class"""
  __tablename__ = "dummy_table"
  id = Column(Integer, primary_key=True)
  created_date = Column(DateTime, default=datetime.datetime.utcnow)


def test_DbSession():
  with DbSession() as session:
    try:
      result = session.execute('desc dummy_table')
      for row in result:
        print(row)
    except IntegrityError as ierr:
      LOGGER.error('Something went wrong in current db session %s', ierr)
      return False


def test_DbConnection():
  with DbConnection() as conn:
    try:
      conn.execute('desc dummy_table')
    except IntegrityError as ierr:
      LOGGER.error('Something went wrong in current db session %s', ierr)
      return False
