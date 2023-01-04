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
"""Session table and its associate functionality"""
from sqlalchemy import Column, Integer, String, UniqueConstraint, ForeignKey

from tuna.dbBase.base_class import BASE
from tuna.utils.logger import setup_logger
from tuna.session_mixin import SessionMixin
from tuna.utils.db_utility import insert_session

LOGGER = setup_logger('session')


class Session(BASE, SessionMixin):
  """Session table to keep track of tunning sesions"""
  #pylint: disable=attribute-defined-outside-init
  #pylint: disable=too-many-instance-attributes

  __tablename__ = "session"
  __table_args__ = (UniqueConstraint("arch",
                                     "num_cu",
                                     "miopen_v",
                                     "rocm_v",
                                     "reason",
                                     "ticket",
                                     "docker",
                                     "solver_id",
                                     name="uq_idx"),)

  miopen_v = Column(String(length=64), nullable=False)
  solver_id = Column(Integer,
                     ForeignKey("solver.id",
                                onupdate="CASCADE",
                                ondelete="CASCADE"),
                     nullable=True)

  def get_query(self, sess, sess_obj, entry):
    """get session matching this object"""
    query = sess.query(sess_obj)\
        .filter(sess_obj.arch == entry.arch)\
        .filter(sess_obj.num_cu == entry.num_cu)\
        .filter(sess_obj.miopen_v == entry.miopen_v)\
        .filter(sess_obj.rocm_v == entry.rocm_v)\
        .filter(sess_obj.reason == entry.reason)\
        .filter(sess_obj.ticket == entry.ticket)\
        .filter(sess_obj.docker == entry.docker)\
        .filter(sess_obj.solver_id == entry.solver_id)\

    return query

  def add_new_session(self, args, worker):
    """Add new session entry"""
    super().add_new_session(args, worker)

    if hasattr(args, 'miopen_v') and args.miopen_v:
      self.miopen_v = args.miopen_v
    else:
      self.miopen_v = worker.get_miopen_v()

    if args.solver_id:
      self.solver_id = args.solver_id

    return insert_session(self)
