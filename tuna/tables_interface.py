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
"""Module that encapsulates the DB representation for a library"""

from tuna.dbBase.sql_alchemy import DbSession


#pylint: disable=too-few-public-methods
class DBTablesInterface():
  """Represents db tables interface class"""

  def __init__(self, **kwargs):
    """Constructor"""
    super().__init__()
    allowed_keys = set(['session_id'])
    self.__dict__.update((key, None) for key in allowed_keys)

    #for pylint
    self.job_table = None
    self.session_id = None
    self.session = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

  def set_tables(self, sess_class):
    """Set appropriate tables based on requirements"""
    if self.session_id is not None:
      with DbSession() as session:
        query = session.query(sess_class).filter(
            sess_class.id == self.session_id)
        self.session = query.one()
    return True
