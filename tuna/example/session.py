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
"""Session table and its associate functionality"""

import argparse
from typing import Tuple
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm.session import Session
from sqlalchemy.orm.query import Query
from tuna.dbBase.base_class import BASE
from tuna.db.session_mixin import SessionMixin
from tuna.worker_interface import WorkerInterface


class SessionExample(BASE, SessionMixin):
  """Session table to keep track of tuning sessions"""
  #pylint: disable=attribute-defined-outside-init

  __tablename__: str = "session_example"
  __table_args__: Tuple[UniqueConstraint] = (UniqueConstraint("arch",
                                                              "num_cu",
                                                              "rocm_v",
                                                              "reason",
                                                              "docker",
                                                              name="uq_idx"),)

  def get_query(self, sess: Session, sess_obj: SessionMixin,
                entry: argparse.Namespace) -> Query:
    """get session matching this object"""
    query = sess.query(sess_obj.id)\
        .filter(sess_obj.arch == entry.arch)\
        .filter(sess_obj.num_cu == entry.num_cu)\
        .filter(sess_obj.rocm_v == entry.rocm_v)\
        .filter(sess_obj.reason == entry.reason)\
        .filter(sess_obj.docker == entry.docker)\

    return query

  def add_new_session(self, args: argparse.Namespace,
                      worker: WorkerInterface) -> int:
    """Add new session entry"""
    super().add_new_session(args, worker)
    return self.insert_session()
