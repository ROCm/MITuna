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
import mysql.connector  # pylint: disable=unused-import


class DbConnection():
  """ Resource manager class for a SQL connection """

  def __init__(self):
    '''
        Importing in a function may be a thorny subject.
        Please see
        http://stackoverflow.com/questions/477096/python-import-coding-style/4789963#4789963
        for my reason to use this.
        '''
    import os
    if 'TUNA_DB_USER_NAME' in os.environ:
      self.db_user_name = os.environ['TUNA_DB_USER_NAME']
    else:
      self.db_user_name = ''
    if 'TUNA_DB_USER_PASSWORD' in os.environ:
      self.db_user_password = os.environ['TUNA_DB_USER_PASSWORD']
    else:
      self.db_user_password = ''
    if 'TUNA_DB_HOSTNAME' in os.environ:
      self.db_host_name = os.environ['TUNA_DB_HOSTNAME']
    else:
      self.db_host_name = 'localhost'
    if 'TUNA_DB_NAME' in os.environ:
      self.db_name = os.environ['TUNA_DB_NAME']
    else:
      self.db_name = ''
    self.connection = None

  def get_connection(self):
    """ return a cached connection if one exists, else create a new one
    and return that instead """
    if self.connection is not None and self.connection.is_connected():
      return self.connection

    self.connection = mysql.connector.connect(user=self.db_user_name,
                                              password=self.db_user_password,
                                              host=self.db_host_name,
                                              database=self.db_name)
    self.connection.autocommit = False
    if not self.connection.is_connected():
      raise ValueError('Could not connect to the DB instance')
    return self.connection

  def close_connection(self):
    """ Close a SQL connection after commiting the changes """
    self.connection.commit()
    self.connection.close()
    return True

  def __enter__(self):
    return self.get_connection()

  def __exit__(self, type_t, value, traceback):
    self.close_connection()


class DbCursor():
  """Resource manager class for a SQL cursor"""

  def __init__(self):
    self.cnx = None
    self.sql_connection = None
    self.cur = None

  def __enter__(self):
    self.cnx = DbConnection()
    self.sql_connection = self.cnx.get_connection()
    self.cur = self.sql_connection.cursor()
    return self.cur

  def __exit__(self, type_t, value, traceback):
    self.cur.close()
    self.cnx.close_connection()
