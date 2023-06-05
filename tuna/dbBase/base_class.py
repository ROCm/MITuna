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
from typing import Dict, Any, List
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy.sql import func as sqla_func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy import Column, Integer, DateTime, text


class BASE():
  """Base class for our own common functionalities among tables"""

  __table__: Column = None
  __table_args__: Dict[str, str] = {'mysql_engine': 'InnoDB'}
  __mapper_args__: Dict[str, bool] = {'always_refresh': True}

  id = Column(Integer, primary_key=True)
  insert_ts = Column(DateTime, nullable=False, server_default=sqla_func.now())
  update_ts = Column(
      DateTime,
      nullable=False,
      server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
  valid = Column(TINYINT(1), nullable=False, server_default="1")

  def to_dict(self,
              ommit_ts: bool = True,
              ommit_valid: bool = False) -> Dict[str, Any]:
    """Helper function"""
    copy_dict: Dict[str, Any] = {}
    for key, val in vars(self).items():
      copy_dict[key] = val
    exclude_cols: List[str] = [
        '_sa_instance_state', 'md5', 'valid', 'input_tensor', 'weight_tensor'
    ]
    if not ommit_valid:
      exclude_cols.remove('valid')

    for col in exclude_cols:
      if col in vars(self):
        copy_dict.pop(col)

    if ommit_ts:
      if 'update_ts' in vars(self):
        copy_dict.pop('update_ts')
      if 'insert_ts' in vars(self):
        copy_dict.pop('insert_ts')
    return copy_dict

  def __repr__(self) -> str:
    return f"Table name: {self.__table__}\nTable columns: {self.__table__.columns}"


BASE: DeclarativeMeta = declarative_base(cls=BASE)  #type: ignore
