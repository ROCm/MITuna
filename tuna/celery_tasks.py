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
from tuna.utils.db_utility import gen_select_objs, has_attr_set
from tuna.utils.utility import SimpleDict
from tuna.dbBase.sql_alchemy import DbSession
from tuna.tables_interface import DBTablesInterface
#from tuna.utils.miopen_utility import load_machines
from tuna.machine import Machine
from tuna.miopen.worker.fin_builder import FinBuilder
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.worker.fin_eval import FinEvaluator

LOGGER: logging.Logger = setup_logger('celery_tasks')
MAX_JOB_RETRIES = 10


def get_jobs(find_state: str, label: str, dbt: DBTablesInterface,
             session_id: int) -> bool:
  """Interface function to get jobs based on session and find_state"""
  job_rows: List[Tuple[SimpleDict, ...]]
  job_tables: List[SimpleDict]
  ids: list
  row: SimpleDict
  job_attr: List[str]
  try:
    job_attr = [column.name for column in inspect(dbt.job_table).c]
    job_attr.remove("insert_ts")
    job_attr.remove("update_ts")
  except NoInspectionAvailable as error:
    LOGGER.warning("Ignoring error for init_session: %s", error)

  with DbSession() as session:
    job_rows = get_job_objs(session, find_state, label, dbt, job_attr)

    if not check_jobs_found(job_rows, find_state, session_id):
      return False

    job_tables = get_job_tables(job_rows, job_attr)
    ids = [row.id for row in job_tables]
    LOGGER.info("%s jobs %s", find_state, ids)

  return job_tables


def get_job_objs(session: DbSession,
                 find_state: str,
                 label: str,
                 dbt: DBTablesInterface,
                 job_attr: List[str],
                 fin_steps: List[str] = None) -> List[Tuple[SimpleDict, ...]]:
  """Get list of job objects"""
  entries: List[Tuple[SimpleDict, ...]]
  conds: List[str] = [f"session={dbt.session.id}", "valid=1"]

  if label:
    conds.append(f"reason='{label}'")

  conds.append(f"retries<{MAX_JOB_RETRIES}")
  conds.append(f"state='{find_state}'")

  entries = compose_work_objs(session, conds, dbt, job_attr, fin_steps)
  return entries


def compose_work_objs(
    session: DbSession,
    conds: List[str],
    dbt: DBTablesInterface,
    job_attr: List[str],
    fin_steps: List[str] = None) -> List[Tuple[SimpleDict, ...]]:
  """Query a job list for update"""
  if fin_steps:
    conds.append(f"fin_step like '%{fin_steps[0]}%'")
  else:
    conds.append("fin_step='not_fin'")

  cond_str = ' AND '.join(conds)
  if cond_str:
    cond_str = f"WHERE {cond_str}"
  cond_str += " ORDER BY retries,config ASC"
  #try once without waiting for lock
  entries = gen_select_objs(session, job_attr, dbt.job_table.__tablename__,
                            cond_str)

  if fin_steps:
    ret = compose_work_objs_fin(session, entries, dbt)
    return ret

  return [(job,) for job in entries]


def compose_work_objs_fin(session, job_entries, dbt):
  """Return jobs for fin work"""
  ret = []
  if job_entries:
    id_str = ','.join([str(job[0].config) for job in job_entries])
    cfg_cond_str = f"where valid=1 and id in ({id_str})"
    cfg_attr = [column.name for column in inspect(dbt.config_table).c]
    cfg_entries = gen_select_objs(session, cfg_attr,
                                  dbt.config_table.__tablename__, cfg_cond_str)

    #attach tensor relationship information to config entries
    cfg_rel = {
        key: {
            'key': list(val.local_columns)[0].name,
            'ftble': str(list(val.remote_side)[0]).split('.', maxsplit=1)[0],
            'fkey': str(list(val.remote_side)[0]).split('.')[1]
        } for key, val in inspect(dbt.config_table).relationships.items()
    }
    for cfg in cfg_entries:
      for key, val in cfg_rel.items():
        rel_val = getattr(cfg, val['key'])
        rel_cond_str = f"where {val['fkey']}={rel_val}"
        setattr(
            cfg, key,
            gen_select_objs(session, val['fattr'], val['ftble'],
                            rel_cond_str)[0])

    cfg_map = {cfg.id: cfg for cfg in cfg_entries}

    for job in job_entries:
      ret.append((job[0], cfg_map[job[0].config]))

  return ret


def check_jobs_found(job_rows: List[SimpleDict], find_state: str,
                     session_id: int) -> bool:
  """check for end of jobs"""
  if not job_rows:
    # we are done
    LOGGER.warning('No %s jobs found, session %s', find_state, session_id)
    return False
  return True


def get_job_tables(job_rows: List[Tuple[SimpleDict, ...]],
                   job_attr: List[str]) -> List[SimpleDict]:
  """find job tables in query results"""
  if has_attr_set(job_rows[0], job_attr):
    job_tables: List[SimpleDict] = job_rows
  else:
    job_i: int = 0
    tble: SimpleDict
    for i, tble in enumerate(job_rows[0]):
      if has_attr_set(tble, job_attr):
        job_i = i
        break
    job_tables = [row[job_i] for row in job_rows]

  return job_tables


def tune(library):
  """tuning loop to spin out celery tasks"""

  #load machines
  #machines = load_machines(library.args)
  #get jobs
  job_tables = []
  worker = None
  #Alex: currently hardcoding GPU idx 0???
  f_vals = library.get_f_vals(Machine(), range(0))
  kwargs = library.get_kwargs(0, f_vals)

  if library.args.fin_steps:
    if 'miopen_find_compile' in library.args.fin_steps \
    or 'miopen_perf_compile' in library.args.fin_steps:
      kwargs['fetch_state'] = ['new']
      worker = FinBuilder(**kwargs)
      job_tables = get_jobs('new', library.dbt, library.args.session_id, None)
    elif 'miopen_find_eval' in library.args.fin_steps or 'miopen_perf_eval' in library.args.fin_steps:
      kwargs['fetch_state'] = ['compiled']
      worker = FinEvaluator(**kwargs)
      job_tables = get_jobs('compiled', library.dbt, library.args.session_id, None)
    else:
      raise ValueError('Unsupported fin step')
    #worker.start()
    #worker_lst.append(worker)
    return True
  if library.args.update_applicability:
    kwargs['fin_steps'] = ['applicability']
    worker = FinClass(**kwargs)
    job_tables = get_jobs('new', library.dbt, library.args.session_id, library.args.fin_steps)
    #worker.start()
    #worker_lst.append(worker)
    return True
  for elem in job_tables:
    print(elem)
    celery_task(worker, elem)

  return False


def celery_task(worker, job):
  """defines a celery task"""
  print(worker.session_id)
  print(job)
