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
import enum
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy import Text, Enum
from sqlalchemy.ext.declarative import declared_attr


#pylint: disable=too-few-public-methods
class JobEnum(enum.Enum):
  """Represents job_enum column in config table"""
  # pylint: disable=invalid-name ; names represent entries in job_enum column
  # pylint: disable=duplicate-code
  new = 1
  started = 2
  running = 3
  completed = 4
  timeout = 5
  error_status = 6
  no_update = 7
  errored = 8
  bad_param = 9
  error = 10
  transfer_error = 11
  eval_start = 12
  evaluating = 13
  evaluated = 14
  evaluate_error = 15
  compile_start = 16
  compiling = 17
  compiled = 18
  compile_error = 19
  not_applicable = 20
  aborted = 21
  not_tunable = 22
  compiled_pend = 23
  evaluated_pend = 24


class JobMixin():
  """Represents Mixin class for job tables"""

  @declared_attr
  def session(self):
    """session key"""
    return Column(Integer, ForeignKey("session.id"), nullable=False)

  reason = Column(String(length=60), nullable=False, server_default="")
  state = Column(Enum(JobEnum), nullable=False, server_default="new")
  retries = Column(Integer, nullable=False, server_default="0")
  result = Column(Text, nullable=True)

  gpu_id = Column(Integer, nullable=False, server_default="-1")
  machine_id = Column(Integer, nullable=False, server_default="-1")
  cache_loc = Column(Text)
