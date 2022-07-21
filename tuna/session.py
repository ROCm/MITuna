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
from sqlalchemy.exc import IntegrityError

from tuna.dbBase.sql_alchemy import DbSession
from tuna.dbBase.base_class import BASE
from tuna.utils.logger import setup_logger

LOGGER = setup_logger('session')


class Session(BASE):
  """Session table to keep track of tunning sesions"""
  # pylint: disable=too-many-instance-attributes

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

  arch = Column(String(length=20), nullable=False, server_default="")
  num_cu = Column(Integer, nullable=False)
  rocm_v = Column(String(length=64), nullable=False)
  miopen_v = Column(String(length=64), nullable=False)
  reason = Column(String(length=60), nullable=False)
  ticket = Column(String(length=64), nullable=False, server_default="N/A")
  docker = Column(String(length=64),
                  nullable=False,
                  server_default="miopentuna")
  solver_id = Column(Integer,
                     ForeignKey("solver.id",
                                onupdate="CASCADE",
                                ondelete="CASCADE"),
                     nullable=True)

  def add_new_session(self, args, worker):
    """Add new session entry"""
    self.arch = args.arch
    self.num_cu = args.num_cu
    self.rocm_v = worker.get_rocm_v()
    self.miopen_v = worker.get_branch_hash()
    self.reason = args.label
    if args.ticket:
      self.ticket = args.ticket
    self.docker = args.docker_name
    if args.solver_id:
      self.solver_id = args.solver_id

    with DbSession() as session:
      try:
        session.add(self)
        session.commit()
        LOGGER.info('Added new session_id: %s', self.id)
      except IntegrityError as err:
        LOGGER.warning("Err occurred trying to add new session: %s \n %s", err,
                       self)

    return self.id
