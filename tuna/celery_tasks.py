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
import logging
from celery.result import AsyncResult

from tuna.utils.logger import setup_logger
from tuna.utils.utility import serialize_job
from tuna.celery_app.celery import app, celery_enqueue_gfx908_120, celery_enqueue_gfx1030_36
from tuna.machine import Machine

LOGGER: logging.Logger = setup_logger('tune')
MAX_JOB_RETRIES = 10

TUNING_QUEUE = {
    "gfx908-120": celery_enqueue_gfx908_120,
    "gfx1030-36": celery_enqueue_gfx1030_36
}


def tune(library):
  """tuning loop to spin out celery tasks"""

  f_vals = library.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = library.get_kwargs(0, f_vals, tuning=True)

  job_config_rows = library.get_jobs(library.fetch_state,
                                     library.args.session_id)
  if not job_config_rows:
    return False

  for elem in job_config_rows:
    job_dict = serialize_job(elem)

    result = TUNING_QUEUE[library.dbt.session.arch + '-' +
                          str(library.dbt.session.num_cu)].delay([
                              elem[0].to_dict(), job_dict, library.worker_type
                          ], kwargs)
    print('result: %s', result)
    print('result_id: %s', result.id)
    LOGGER.info('result_status: %s', result.status)

    res = AsyncResult(result.id, app=app)
    #calling get waits for job to terminate
    #LOGGER.info('final res %s', res.get())
    LOGGER.info('final state %s', res.state)

  return False
