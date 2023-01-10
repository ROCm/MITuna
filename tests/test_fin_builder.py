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

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.miopen_utility import load_machines
from tuna.miopen.tables import MIOpenDBTables
from tuna.miopen.fin_class import FinClass
from tuna.utils.db_utility import connect_db
from import_configs import import_cfgs
from load_job import test_tag_name as tag_name_test, add_jobs
from utils import CfgImportArgs, LdJobArgs, GoFishArgs
from utils import get_worker_args, add_test_session
from tuna.miopen.miopen_lib import MIOpen
from tuna.metadata import ALG_SLV_MAP
from tuna.utils.db_utility import get_solver_ids


def add_cfgs():
  #import configs
  args = CfgImportArgs()
  args.tag = 'test_fin_builder'
  args.mark_recurrent = True
  args.file_name = f"{this_path}/../utils/configs/conv_configs_NCHW.txt"

  dbt = MIOpenDBTables(config_type=args.config_type)
  counts = import_cfgs(args, dbt)
  return dbt


def add_fin_find_compile_job(session_id, dbt):
  #load jobs
  args = LdJobArgs
  args.label = 'tuna_pytest_fin_builder'
  args.tag = 'test_fin_builder'
  args.fin_steps = ['miopen_find_compile', 'miopen_find_eval']
  args.session_id = session_id

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
  return add_jobs(args, dbt)


def test_fin_builder():
  args = GoFishArgs()
  machine_lst = load_machines(args)
  machine = machine_lst[0]
  args.session_id = add_test_session()
  miopen = MIOpen()
  miopen.args = args

  #update solvers
  kwargs = get_worker_args(args, machine, miopen)
  fin_worker = FinClass(**kwargs)
  assert (fin_worker.get_solvers())

  #get applicability
  dbt = add_cfgs()
  args.update_applicability = True
  args.label = 'tuna_pytest_fin_builder'
  worker_lst = miopen.compose_worker_list(machine_lst, args)
  for worker in worker_lst:
    worker.join()

  #load jobs
  num_jobs = add_fin_find_compile_job(args.session_id, dbt)
  print('num_jobs: {}'.format(num_jobs))

  #compile
  args.update_applicability = False
  args.fin_steps = ["miopen_find_compile"]
  args.label = 'tuna_pytest_fin_builder'
  worker_lst = miopen.compose_worker_list(machine_lst, args)
  for worker in worker_lst:
    worker.join()

  with DbSession() as session:
    valid_fin_err = session.query(dbt.job_table).filter(dbt.job_table.session==args.session_id)\
                                         .filter(dbt.job_table.state=='errored')\
                                         .filter(dbt.job_table.result.contains('%Find Compile: No results%'))\
                                         .count()
    #ommiting valid Fin/MIOpen errors
    num_jobs = (num_jobs - valid_fin_err)
    count = session.query(dbt.job_table).filter(dbt.job_table.session==args.session_id)\
                                         .filter(dbt.job_table.state=='compiled').count()
    assert (count == num_jobs)
