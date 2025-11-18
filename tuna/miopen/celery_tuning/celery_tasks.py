#!/usr/bin/env python3

###############################################################################
#
# MIT License
#
# Copyright (c) 2024 Advanced Micro Devices, Inc.
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
"""Module to register MIOpen celery tasks"""
import os
import copy
from celery.signals import celeryd_after_setup
from celery.utils.log import get_task_logger
from sqlalchemy.exc import IntegrityError
from tuna.celery_app.celery_app import app
from tuna.libraries import Operation
from tuna.machine import Machine
from tuna.miopen.utils.lib_helper import get_worker
from tuna.utils.utility import SimpleDict
from tuna.utils.celery_utils import prep_default_kwargs, get_cached_worker
from tuna.miopen.miopen_lib import Q_NAME
from tuna.dbBase.sql_alchemy import DbSession

logger = get_task_logger(__name__)


def check_hostname_unique_constraint(session):
  """Check if hostname has a unique constraint on the machine table"""
  try:
    from sqlalchemy import text
    result = session.execute(text(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() "
        "AND table_name = 'machine' "
        "AND column_name = 'hostname' "
        "AND non_unique = 0"
    )).scalar()
    return result > 0
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.warning("Could not check for hostname unique constraint: %s", e)
    return None  # Unknown state


@celeryd_after_setup.connect
def capture_worker_name(sender, instance, **kwargs):  #pylint: disable=unused-argument
  """Capture worker name and ensure machine is registered"""
  app.worker_name = sender
  
  # Ensure this machine is in the database
  global cached_machine
  with DbSession() as session:
    # Check for unique constraint on hostname (only check once)
    if not check_hostname_unique_constraint(session):
      logger.warning(
          "WARNING: The 'machine' table does not have a UNIQUE constraint on 'hostname'. "
          "This may lead to duplicate machine entries and race conditions. "
          "Please run: ALTER TABLE machine ADD UNIQUE INDEX idx_hostname (hostname(255)); "
          "Or apply the Alembic migration: alembic upgrade head"
      )
    
    # Check if machine exists by hostname
    existing = session.query(Machine).filter(
        Machine.hostname == cached_machine.hostname
    ).first()
    
    if not existing:
      # Create a new machine object for database insertion
      # Don't use cached_machine directly as it has id=0 hardcoded
      new_machine = Machine(
          hostname=cached_machine.hostname,
          user=os.getenv('USER', 'unknown'),
          password='',
          arch=cached_machine.arch,
          num_cu=cached_machine.num_cu,
          avail_gpus=','.join(map(str, cached_machine.avail_gpus)) if isinstance(cached_machine.avail_gpus, list) else str(cached_machine.avail_gpus)
      )
      
      try:
        # Insert the machine and let database auto-assign ID
        session.add(new_machine)
        session.commit()
        session.refresh(new_machine)
        cached_machine.id = new_machine.id
        logger.info("Registered machine %s with id %s", cached_machine.hostname, cached_machine.id)
      except IntegrityError:
        # Race condition: another worker beat us to it
        # Rollback and query again to get the existing record
        session.rollback()
        logger.info("Race condition detected during machine registration, querying existing record")
        existing = session.query(Machine).filter(
            Machine.hostname == cached_machine.hostname
        ).first()
        if existing:
          cached_machine.id = existing.id
          logger.info("Using existing machine %s with id %s (from race condition recovery)", cached_machine.hostname, cached_machine.id)
        else:
          # This should never happen, but log it if it does
          logger.error("Failed to find machine after IntegrityError - this should not happen!")
          raise
    else:
      # Use existing machine id
      cached_machine.id = existing.id
      logger.info("Using existing machine %s with id %s", cached_machine.hostname, cached_machine.id)


cached_machine = Machine(local_machine=True)


def prep_kwargs(kwargs, args):
  """Populate kwargs with serialized job, config and machine"""
  kwargs = prep_default_kwargs(kwargs, args[0], cached_machine)
  kwargs["config"] = SimpleDict(**args[1])

  return kwargs


cached_worker = {}


def prep_worker(context):
  """Creating tuna worker object based on context"""
  operation = context['operation']
  if operation in cached_worker:
    worker = get_cached_worker(context, cached_worker)
    worker.config = SimpleDict(**context['config'])
  else:
    args = [context['job'], context['config'], context['operation']]
    kwargs = prep_kwargs(context['kwargs'], args)
    worker = get_worker(kwargs, args[2])
    cached_worker[operation] = worker
  return worker


@app.task(trail=True, reply_to=Q_NAME)
def celery_enqueue(context):
  """Defines a celery task"""
  kwargs = context['kwargs']
  operation = context['operation']

  if operation == Operation.EVAL:
    gpu_id = int((app.worker_name).split('gpu_id_')[1])
    kwargs['gpu_id'] = gpu_id
    context['job']['gpu_id'] = gpu_id
    logger.info("Enqueueing worker %s: gpu(%s), job %s", app.worker_name,
                gpu_id, context['job'])
  else:
    logger.info("Enqueueing worker %s: job %s", app.worker_name, context['job'])

  worker = prep_worker(copy.deepcopy(context))
  ret = worker.run()
  
  # Add machine_id to the context before returning
  context['machine_id'] = cached_machine.id
  
  return {"ret": ret, "context": context}
