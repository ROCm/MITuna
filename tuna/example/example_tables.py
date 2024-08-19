#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
from typing import List, Tuple
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy import Text, Enum
from sqlalchemy.ext.declarative import declared_attr

from tuna.dbBase.base_class import BASE
from tuna.machine import Machine
from tuna.example.session import SessionExample

#pylint: disable=too-few-public-methods


class JobEnum(enum.Enum):
  """Represents job_enum column in config table"""
  # pylint: disable=invalid-name ; names represent entries in job_enum column
  # pylint: disable=duplicate-code
  new = 1
  running = 3
  completed = 4
  error = 5


class Job(BASE):
  """Represents class for job table"""
  __tablename__: str = "job"
  __table_args__: Tuple[UniqueConstraint] = (UniqueConstraint('reason',
                                                              'session',
                                                              name="uq_idx"),)

  @declared_attr
  def session(self) -> Column:
    """session key"""
    return Column(Integer, ForeignKey("session_example.id"), nullable=False)

  reason = Column(String(length=60), nullable=False, server_default="")
  state = Column(Enum(JobEnum), nullable=False, server_default="new")
  retries = Column(Integer, nullable=False, server_default="0")
  result = Column(Text, nullable=True)
  gpu_id = Column(Integer, nullable=False, server_default="-1")
  machine_id = Column(Integer, nullable=False, server_default="-1")


def get_tables() -> List[BASE]:
  """Returns a list of all Example lib DB tables"""
  tables: List[BASE] = []
  tables.append(SessionExample())
  tables.append(Machine(local_machine=True))
  tables.append(Job())

  return tables
