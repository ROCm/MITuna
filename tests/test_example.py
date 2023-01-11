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

import os
import sys
#import pytest
from multiprocessing import Value, Lock, Queue
from subprocess import Popen, PIPE

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.machine import Machine
from tuna.sql import DbCursor
from tuna.utils.db_utility import connect_db
from tuna.example.example_lib import Example
from tuna.db_engine import ENGINE
from tuna.utils.logger import setup_logger
from utils import ExampleArgs
from tuna.utils.miopen_utility import load_machines
from tuna.dbBase.sql_alchemy import DbSession
from tuna.example.session import SessionExample


def test_example():
  args = ExampleArgs()
  example = Example()
  assert (example.add_tables())

  res = load_machines(args)
  res = example.compose_worker_list(res, args)
  with DbSession() as session:
    query = session.query(SessionExample)
    res = query.all()
  assert len(res) is not None

  return True


def create_db():
  with ENGINE.connect() as conn:
    try:
      conn.execute(f"drop database if exists example_db")
      conn.execute(f"create database example_db")
    except OperationalError as oerr:
      LOGGER.info('%s \n', oerr)
