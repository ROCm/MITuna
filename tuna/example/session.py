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
from sqlalchemy import UniqueConstraint

from tuna.dbBase.base_class import BASE
from tuna.utils.logger import setup_logger
from tuna.session_mixin import SessionMixin

LOGGER = setup_logger('session_example')


class SessionExample(BASE, SessionMixin):
  """Session table to keep track of tunning sesions"""
  #pylint: disable=attribute-defined-outside-init

  __tablename__ = "session_example"
  __table_args__ = (UniqueConstraint("arch",
                                     "num_cu",
                                     "rocm_v",
                                     "reason",
                                     "ticket",
                                     "docker",
                                     name="uq_idx"),)

  def get_query(self, sess, sess_obj, entry):
    """get session matching this object"""
    query = sess.query(sess_obj)\
        .filter(sess_obj.arch == entry.arch)\
        .filter(sess_obj.num_cu == entry.num_cu)\
        .filter(sess_obj.rocm_v == entry.rocm_v)\
        .filter(sess_obj.reason == entry.reason)\
        .filter(sess_obj.ticket == entry.ticket)\
        .filter(sess_obj.docker == entry.docker)\

    return query

  def add_new_session(self, args, worker):
    """Add new session entry"""
    super().add_new_session(args, worker)
    return self.insert_session(session_class=self)
