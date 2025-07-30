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
from sqlalchemy.exc import OperationalError
from tuna.miopen.db.get_db_tables import get_miopen_tables
from tuna.miopen.db.triggers import get_miopen_triggers, drop_miopen_triggers
from tuna.db_engine import ENGINE
from tuna.utils.logger import setup_logger
from tuna.utils.db_utility import create_tables

#pylint: disable=too-few-public-methods
LOGGER = setup_logger('miopen_db_tables')


def recreate_triggers(drop_triggers, create_triggers):
  """Drop and recreate triggers"""

  with ENGINE.connect() as conn:
    for dtg in drop_triggers:
      conn.execute(f"drop trigger if exists {dtg}")
    for trg in create_triggers:
      try:
        conn.execute(trg)
      except OperationalError as oerr:
        LOGGER.warning("Operational Error occurred while adding trigger: '%s'",
                       trg)
        LOGGER.info('%s \n', oerr)
        continue

  return True


def main():
  """Main script function"""
  #setup MIOpen DB
  ret_t = create_tables(get_miopen_tables())
  LOGGER.info('DB creation successful: %s', ret_t)
  recreate_triggers(drop_miopen_triggers(), get_miopen_triggers())


if __name__ == '__main__':
  main()
