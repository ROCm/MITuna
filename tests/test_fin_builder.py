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
import copy

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.worker.fin_class import FinClass
from tuna.utils.db_utility import connect_db
from tuna.miopen.subcmd.import_configs import import_cfgs
from tuna.miopen.subcmd.load_job import add_jobs
from utils import CfgImportArgs, LdJobArgs, GoFishArgs
from utils import get_worker_args, add_test_session
from tuna.miopen.miopen_lib import MIOpen
from tuna.miopen.utils.metadata import ALG_SLV_MAP
from tuna.miopen.db.solver import get_solver_ids
from tuna.utils.logger import setup_logger
from tuna.miopen.utils.config_type import ConfigType
from tuna.utils.utility import serialize_job_config_row
from tuna.miopen.utils.helper import prep_kwargs
from tuna.machine import Machine
from tuna.miopen.utils.lib_helper import get_worker
from tuna.celery_tasks import process_fin_builder_results


def add_cfgs():
  #import configs
  args = CfgImportArgs()
  args.tag = 'tuna_pytest_fin_builder'
  args.mark_recurrent = True
  args.file_name = f"{this_path}/../utils/configs/conv_configs_NCHW.txt"

  dbt = MIOpenDBTables(config_type=args.config_type)
  counts = import_cfgs(args, dbt, setup_logger('test_fin_builder'))
  return dbt


def add_fin_find_compile_job(session_id, dbt):
  #load jobs
  args = LdJobArgs
  args.label = 'tuna_pytest_fin_builder'
  args.tag = 'tuna_pytest_fin_builder'
  args.fin_steps = ['miopen_find_compile', 'miopen_find_eval']
  args.session_id = session_id
  logger = setup_logger('test_add_fin_find_compile_job')

  #limit job scope
  args.algo = "miopenConvolutionAlgoGEMM"
  solver_arr = ALG_SLV_MAP[args.algo]
  solver_id_map = get_solver_ids()
  if solver_arr:
    solver_ids = []
    for solver in solver_arr:
      sid = solver_id_map.get(solver, None)
      solver_ids.append((solver, sid))
    args.solvers = solver_ids
  args.only_applicable = True

  connect_db()
  return add_jobs(args, dbt, logger)


def test_fin_builder():
  miopen = MIOpen()
  miopen.args = GoFishArgs()
  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  miopen.args.label = 'tuna_pytest_fin_builder'
  miopen.args.session_id = add_test_session(label='tuna_pytest_fin_builder')

  #update solvers
  kwargs = get_worker_args(miopen.args, machine, miopen)
  fin_worker = FinClass(**kwargs)
  assert (fin_worker.get_solvers())

  #get applicability
  dbt = add_cfgs()
  miopen.args.update_applicability = True
  worker_lst = miopen.compose_worker_list(machine_lst)
  for worker in worker_lst:
    worker.join()

  #load jobs
  miopen.args.label = 'tuna_pytest_fin_builder'
  num_jobs = add_fin_find_compile_job(miopen.args.session_id, dbt)
  assert (num_jobs)

  #compile
  miopen.args.update_applicability = False
  miopen.args.fin_steps = ["miopen_find_compile"]
  miopen.args.label = 'tuna_pytest_fin_builder'
  miopen.fetch_state.add('new')
  miopen.set_state = 'compile_start'
  miopen.worker_type = 'fin_build_worker'
  miopen.dbt = MIOpenDBTables(session_id=miopen.args.session_id,
                              config_type=ConfigType.convolution)
  jobs = None
  with DbSession() as session:
    jobs = miopen.get_jobs(session, miopen.fetch_state, miopen.set_state,
                           miopen.args.session_id)
  entries = [job for job in jobs]
  job_config_rows = miopen.compose_work_objs_fin(session, entries, miopen.dbt)
  assert (job_config_rows)

  f_vals = miopen.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = miopen.get_kwargs(0, f_vals, tuning=True)
  fdb_attr = [column.name for column in inspect(miopen.dbt.find_db_table).c]
  fdb_attr.remove("insert_ts")
  fdb_attr.remove("update_ts")

  res_set = []
  for elem in job_config_rows:
    job_dict, config_dict = serialize_job_config_row(elem)
    context = {
        'job': job_dict,
        'config': config_dict,
        'worker_type': miopen.worker_type,
        'arch': miopen.dbt.session.arch,
        'num_cu': miopen.dbt.session.num_cu,
        'kwargs': kwargs,
        'fdb_attr': fdb_attr
    }
    worker_kwargs = prep_kwargs(copy.deepcopy(context),
                                [job_dict, config_dict, miopen.worker_type])

    worker = get_worker(worker_kwargs, miopen.worker_type)
    worker.dbt = miopen.dbt
    worker.fin_steps = miopen.args.fin_steps
    fin_json = worker.run()
    res_set.append((fin_json, context))

  for fin_json, context in res_set:
    process_fin_builder_results(fin_json, context, miopen.dbt)

  with DbSession() as session:
    valid_fin_err = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='errored')\
                                         .filter(dbt.job_table.result.contains('%Find Compile: No results%'))\
                                         .count()
    #ommiting valid Fin/MIOpen errors
    num_jobs = (num_jobs - valid_fin_err)
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='compiled').count()
    assert (count == num_jobs)
