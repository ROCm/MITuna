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
""" Database resource manager """

from typing import Optional, Type
from types import TracebackType
from sqlalchemy.orm.session import Session
from mysql.connector.cursor import MySQLCursor
from tuna.db_engine import SESSION_FACTORY


class DbConnection():
  """ Resource manager class for a SQL connection """

  def __init__(self):
    self.session: Session = None

  def get_session(self) -> Session:
    """ return a cached connection if one exists, else create a new one
    and return that instead """
    if self.session is not None and self.session.is_active():
      return self.session

    self.session = SESSION_FACTORY()
    return self.session

  def __enter__(self):
    return self.get_session()

  def __exit__(self, type_t, value, traceback):
    return self.session.close()


class DbSession():
  """Resource manager class for a SQL cursor"""

  def __init__(self):
    self.cnx: DbConnection = None
    self.sql_session: Session = None
    self.cur: MySQLCursor = None

  def __enter__(self) -> Session:
    self.cnx = DbConnection()
    self.sql_session = self.cnx.get_session()
    return self.sql_session

  def __exit__(self, type_t: Optional[Type[BaseException]],
               value: Optional[BaseException], \
               traceback: Optional[TracebackType]) -> None:
    self.sql_session.close()
