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
"""Utility module for helper functions"""
from subprocess import Popen, PIPE
from sqlalchemy.exc import InterfaceError
from tuna.dbBase.sql_alchemy import DbSession
from tuna.machine import Machine
from tuna.utils.logger import setup_logger
from tuna.utils.db_utility import session_retry

LOGGER = setup_logger('machine_utility')


def load_machines(args, logger=LOGGER):
  """! Function to get available machines from the DB
     @param args The command line arguments
  """
  cmd = 'hostname'
  with Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True) as subp:
    hostname = subp.stdout.readline().strip()
  logger.info('hostname = %s', hostname)
  try:
    with DbSession() as session:
      query = session.query(Machine)
      if args.arch:
        query = query.filter(Machine.arch == args.arch)
      if args.num_cu:
        query = query.filter(Machine.num_cu == args.num_cu)
      if not args.machines and not args.local_machine:
        query = query.filter(Machine.available == 1)
      if args.machines:
        query = query.filter(Machine.id.in_(args.machines))
      if args.local_machine:
        query = query.filter(Machine.remarks == hostname)

      res = session_retry(session, query.all, lambda x: x(), logger)

      if args.local_machine:
        if res:
          res[0].local_machine = True
        else:
          res = [Machine(hostname=hostname, local_machine=True)]
          logger.info(
              'Local machine not in database, continue with incomplete details')

      if not res:
        logger.info('No machine found for specified requirements')
  except InterfaceError as ierr:
    logger.warning(ierr)
    session.rollback()

  return res
