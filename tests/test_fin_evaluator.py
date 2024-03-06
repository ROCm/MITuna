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
import json
import os
import sys
from multiprocessing import Value, Lock, Queue
from sqlalchemy.inspection import inspect

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from dummy_machine import DummyMachine
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.worker.fin_eval import FinEvaluator
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.miopen_lib import MIOpen
from tuna.miopen.subcmd.import_configs import import_cfgs
from tuna.miopen.subcmd.load_job import add_jobs
from tuna.miopen.utils.config_type import ConfigType
from tuna.miopen.utils.metadata import ALG_SLV_MAP
from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.db.solver import get_solver_ids
from tuna.utils.db_utility import connect_db, get_db_obj_by_id
from tuna.utils.logger import setup_logger
from tuna.utils.miopen_utility import load_machines
from tuna.machine import Machine
from tuna.miopen.utils.helper import prep_kwargs
from tuna.miopen.utils.lib_helper import get_worker
from tuna.utils.utility import serialize_job_config_row
from utils import CfgImportArgs, LdJobArgs, GoFishArgs
from utils import get_worker_args, add_test_session
#from tuna.miopen.utils.json_to_sql import process_fdb_eval
from tuna.celery_tasks import set_job_state

solver_id_map = get_solver_ids()


def add_cfgs():
  #import configs
  args = CfgImportArgs()
  args.tag = 'tuna_pytest_fin_eval'
  args.mark_recurrent = True
  args.file_name = f"{this_path}/../utils/configs/conv_configs_NCHW.txt"

  dbt = MIOpenDBTables(config_type=args.config_type)
  import_cfgs(args, dbt, setup_logger('test_fin_eval'))
  return dbt


def add_fin_find_eval_job(session_id, dbt):
  #load jobs
  args = LdJobArgs
  args.label = 'tuna_pytest_fin_eval'
  args.tag = 'tuna_pytest_fin_eval'
  args.fin_steps = ['miopen_find_eval']
  args.session_id = session_id
  logger = setup_logger('test_add_fin_find_eval_job')

  #limit job scope
  args.algo = "miopenConvolutionAlgoDirect"
  solver_arr = ALG_SLV_MAP[args.algo]
  if solver_arr:
    solver_ids = []
    for solver in solver_arr:
      sid = solver_id_map.get(solver, None)
      solver_ids.append((solver, sid))
    args.solvers = solver_ids

  connect_db()
  return add_jobs(args, dbt, logger)


def add_fake_fdb_entries(job_query, dbt, kernel_group):

  with DbSession() as session:
    kernel_obj = dbt.kernel_cache()

    kernel_obj.kernel_group = kernel_group
    kernel_obj.kernel_name = 'placeholder'
    kernel_obj.kernel_args = 'no-args'
    kernel_obj.kernel_blob = bytes('nothing_here', 'utf-8')
    kernel_obj.kernel_hash = '0'
    kernel_obj.uncompressed_size = '0'

    session.add(kernel_obj)
    session.commit()

    job_entries = job_query.all()
    for entry in job_entries:
      fdb_entry = dbt.find_db_table()
      fdb_entry.config = entry.config
      fdb_entry.solver = solver_id_map.get(entry.solver)
      fdb_entry.opencl = False
      fdb_entry.session = dbt.session.id
      fdb_entry.fdb_key = 'nil'
      fdb_entry.params = 'nil'
      fdb_entry.kernel_time = -1
      fdb_entry.workspace_sz = 0
      fdb_entry.kernel_group = kernel_group
      session.add(fdb_entry)

    session.commit()


def test_fin_evaluator():
  miopen = MIOpen()
  miopen.args = GoFishArgs()
  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  miopen.args.label = 'tuna_pytest_fin_eval'
  miopen.args.session_id = add_test_session(label='tuna_pytest_fin_eval')

  #update solvers
  kwargs = get_worker_args(miopen.args, machine, miopen)
  fin_worker = FinClass(**kwargs)
  assert (fin_worker.get_solvers())

  add_cfgs()
  dbt = MIOpenDBTables(config_type=ConfigType.convolution,
                       session_id=miopen.args.session_id)

  #set all applicable
  with DbSession() as session:
    configs = session.query(dbt.config_tags_table.config).filter(
        dbt.config_tags_table.tag == 'tuna_pytest_fin_eval').all()
    configs = [x[0] for x in configs]
    for solver in solver_id_map.values():
      for config in configs:
        slv_app_entry = dbt.solver_app()
        slv_app_entry.config = config
        slv_app_entry.solver = solver
        slv_app_entry.session = dbt.session_id
        slv_app_entry.applicable = True
        session.add(slv_app_entry)
    session.commit()

  #load jobs
  miopen.args.label = 'tuna_pytest_fin_eval'
  num_jobs = add_fin_find_eval_job(miopen.args.session_id, dbt)

  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)
    job_query.update({dbt.job_table.state: 'compiled'})
    print(job_query)
    session.commit()

    add_fake_fdb_entries(job_query, dbt, job_query.first().id)

  miopen.args.fin_steps = ["miopen_find_eval"]
  miopen.args.label = 'tuna_pytest_fin_eval'
  miopen.fetch_state.add('compiled')
  miopen.worker_type = 'fin_eval_worker'
  miopen.set_state = 'eval_start'
  miopen.dbt = MIOpenDBTables(session_id=miopen.args.session_id,
                              config_type=ConfigType.convolution)
  with DbSession() as session:
    jobs = miopen.get_jobs(session, miopen.fetch_state, miopen.set_state,
                           miopen.args.session_id)
  entries = [job for job in jobs]
  job_config_rows = miopen.compose_work_objs_fin(session, entries, miopen.dbt)
  assert (len(job_config_rows) == 80)

  f_vals = miopen.get_f_vals(machine, range(0))
  print('f_vals: %s', f_vals)
  kwargs = miopen.get_kwargs(0, f_vals, tuning=True)
  assert (kwargs['fin_steps'] == ['miopen_find_eval'])
  print('kwargs: %s', kwargs)

  num_gpus = Value('i', 1)
  v = Value('i', 0)
  e = Value('i', 0)
  kwargs['num_procs'] = num_gpus
  kwargs['avail_gpus'] = 1

  job_config = job_config_rows[0]
  job_dict, config_dict = serialize_job_config_row(job_config)
  worker_kwargs = prep_kwargs(kwargs,
                              [job_dict, config_dict, miopen.worker_type])
  assert (worker_kwargs['config'])
  assert (worker_kwargs['job'])
  assert (worker_kwargs['fin_steps'] == ['miopen_find_eval'])
  fin_eval = get_worker(worker_kwargs, miopen.worker_type)
  assert (fin_eval.worker_type == 'fin_eval_worker')
  fin_eval.set_job_state('evaluating')
  with DbSession() as session:
    count = session.query(dbt.job_table).filter(dbt.job_table.state=='evaluating')\
                                         .filter(dbt.job_table.reason=='tuna_pytest_fin_eval')\
                                         .filter(dbt.job_table.session==dbt.session_id).count()
    assert (count == 1)

  # test check gpu with "good" GPU
  # the job state will remain 'evaluated'
  fin_eval.set_job_state('evaluated')
  with DbSession() as session:
    count = session.query(dbt.job_table).filter(dbt.job_table.state=='evaluated')\
                                         .filter(dbt.job_table.reason=='tuna_pytest_fin_eval')\
                                         .filter(dbt.job_table.session==dbt.session_id).count()
    assert (count == 1)

  fin_eval.check_gpu()

  # test get_fin_input
  file_name = fin_eval.get_fin_input()
  assert (file_name)

  with DbSession() as session:
    session.query(dbt.job_table).filter(dbt.job_table.session==dbt.session_id)\
                                         .filter(dbt.job_table.state=='compiled')\
                                         .filter(dbt.job_table.reason=='tuna_pytest_fin_eval')\
                                         .filter(dbt.job_table.session==dbt.session_id)\
                                         .update({dbt.job_table.state: 'evaluated'})
    session.commit()

  #test get_job false branch

  find_eval_file = f"{this_path}/../utils/test_files/fin_output_find_eval.json"
  fin_json = json.loads(machine.read_file(find_eval_file))[1:]
  assert len(fin_json) == 1
  fin_json = fin_json[0]
  job = get_db_obj_by_id(job_dict['id'], miopen.dbt.job_table)
  config = get_db_obj_by_id(config_dict['id'], miopen.dbt.config_table)
  fdb_attr = [column.name for column in inspect(miopen.dbt.find_db_table).c]
  fdb_attr.remove("insert_ts")
  fdb_attr.remove("update_ts")

  #status = process_fdb_eval(fin_json, solver_id_map, config, miopen.dbt,
  #                          miopen.dbt.session_id, fdb_attr, job)
  #for obj in status:
  #  print(obj)
  #  assert (obj['success'] == True)

  #test FinEvaluator close_job
  with DbSession() as session:
    session.query(
        dbt.job_table).filter(dbt.job_table.id == fin_eval.job.id).update(
            {dbt.job_table.state: 'compiled'})
    session.commit()
    assert ('compiled' == session.query(dbt.job_table.state).filter(
        dbt.job_table.id == fin_eval.job.id).first()[0].name)

  set_job_state(session, job, miopen.dbt, 'evaluated')
  with DbSession() as session:
    assert ('evaluated' == session.query(dbt.job_table.state).filter(
        dbt.job_table.id == fin_eval.job.id).first()[0].name)
