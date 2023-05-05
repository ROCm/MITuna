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

import logging
import argparse
from sqlalchemy import Column, Integer, String
from sqlalchemy.exc import IntegrityError
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger

LOGGER: logging.Logger = setup_logger('session')


class SessionMixin():
  """Session Mixin to provide interface for the session table"""
  #pylint: disable=too-few-public-methods
  #pylint: disable=too-many-instance-attributes

  arch: str = Column(String(length=20), nullable=False, server_default="")
  num_cu: int = Column(Integer, nullable=False)
  rocm_v: str = Column(String(length=64), nullable=False)
  reason: str = Column(String(length=60), nullable=False)
  ticket: str = Column(String(length=64), nullable=False, server_default="N/A")
  docker: str = Column(String(length=64),
                       nullable=False,
                       server_default="miopentuna")

  def __init__(self):
    self.session_id = 0

  def add_new_session(self, args: argparse.Namespace, worker) -> None:
    """Add new session entry"""
    self.reason = args.label
    self.docker = args.docker_name
    if hasattr(args, 'arch') and args.arch:
      self.arch = args.arch
    else:
      self.arch = worker.machine.arch

    if hasattr(args, 'num_cu') and args.num_cu:
      self.num_cu = args.num_cu
    else:
      self.num_cu = worker.machine.num_cu

    if hasattr(args, 'rocm_v') and args.rocm_v:
      self.rocm_v = args.rocm_v
    else:
      self.rocm_v = worker.get_rocm_v()

    if hasattr(args, 'ticket') and args.ticket:
      self.ticket = args.ticket
    else:
      self.ticket = 'N/A'

  def insert_session(self) -> int:
    """Insert new session obj and return its id"""
    with DbSession() as session:
      try:
        session.add(self)
        session.commit()
        LOGGER.info('Added new session_id: %s', self.session_id)
      except IntegrityError as err:
        LOGGER.warning("Err occurred trying to add new session: %s \n %s", err,
                       self)
        session.rollback()
        entry = self.get_query(session, type(self), self).one()  #type: ignore
        LOGGER.warning('Session for these values already exists: %s', entry.id)
        return entry.id

    return self.session_id
