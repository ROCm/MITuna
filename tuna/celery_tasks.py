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
"""Interface class to set up and launch tuning functionality"""

from typing import List, Tuple
import logging
from sqlalchemy.inspection import inspect
from sqlalchemy.exc import NoInspectionAvailable

from tuna.utils.logger import setup_logger
from tuna.utils.db_utility import gen_select_objs, has_attr_set, get_class_by_tablename
from tuna.utils.utility import SimpleDict
from tuna.dbBase.sql_alchemy import DbSession
from tuna.tables_interface import DBTablesInterface
#from tuna.utils.miopen_utility import load_machines
from tuna.machine import Machine
from tuna.miopen.worker.fin_builder import FinBuilder
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.worker.fin_eval import FinEvaluator
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.mituna_interface import MITunaInterface
from tuna.celery_app.celery import app, celery_task
from celery.result import AsyncResult

LOGGER: logging.Logger = setup_logger('celery_tasks')
MAX_JOB_RETRIES = 10


def tune(library):
  """tuning loop to spin out celery tasks"""

  #load machines
  #machines = load_machines(library.args)
  #get jobs
  job_tables = []
  worker = None
  #Alex: currently hardcoding GPU idx 0???
  f_vals = library.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = library.get_kwargs(0, f_vals)

  if library.is_tunable_operation():
    job_config_rows = library.get_jobs(library.fetch_state)

    #job_config_rows[0] is job
    #job_config_rows[1] is its related config
    for elem in job_config_rows:
      print
      #print("TASK: %s", elem)
      print(library.worker_type)
      job_dict = {}

      #launching task
      for key, value in elem[1].to_dict().items():
        print(key, value)
        if type(value) == SimpleDict:
          print(key, value.to_dict())
          job_dict[key] = value.to_dict()
        else:
          job_dict[key] = value

      result = celery_task.delay(
          [elem[0].to_dict(), job_dict, library.worker_type], kwargs)
      print('result: %s', result)
      print('result_id: %s', result.id)
      print('result_status: %s', result.status)

      res = AsyncResult(result.id, app=app)
      #calling get waits for job to terminate
      print('final res %s', res.get())
      #print('final state %s', res.state)
      print()
  else:
    result = celery_task.delay([None, None, library.worker_type], kwargs)
    print('result: %s', result)
    print('result_id: %s', result.id)
    print('result_status: %s', result.status)

    res = AsyncResult(result.id, app=app)
    #calling get waits for job to terminate
    #print('final res %s', res.get())
    #print('final state %s', res.state)
    print()

  return False
