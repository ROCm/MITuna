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
""" Module for creating DB tables interfaces"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy import Column, Integer, DateTime, text


class BASE(object):
  """Base class for our own common functionalities among tables"""
  __table_args__ = {'mysql_engine': 'InnoDB'}
  __mapper_args__ = {'always_refresh': True}

  id = Column(Integer, primary_key=True)
  insert_ts = Column(DateTime, nullable=False, server_default=sqla_func.now())
  update_ts = Column(
      DateTime,
      nullable=False,
      server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
  valid = Column(TINYINT(1), nullable=False, server_default="1")

  def to_dict(self, ommit_ts=True, ommit_valid=False):
    """Helper function"""
    copy_dict = {}
    for key, val in self.__dict__.items():
      copy_dict[key] = val
    exclude_cols = [
        '_sa_instance_state', 'md5', 'valid', 'input_tensor', 'weight_tensor'
    ]
    if ommit_valid:
      exclude_cols.remove('valid')

    for col in exclude_cols:
      if col in self.__dict__.keys():
        copy_dict.pop(col)

    if ommit_ts:
      if 'update_ts' in self.__dict__.keys():
        copy_dict.pop('update_ts')
      if 'insert_ts' in self.__dict__.keys():
        copy_dict.pop('insert_ts')
    return copy_dict

  def __repr__(self):
    return "Table name: {0}\nTable columns: {1}".format(self.__table__,
                                                        self.__table__.columns)


BASE = declarative_base(cls=BASE)
