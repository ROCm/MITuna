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
from multiprocessing import Value

sys.path.append("../tuna")
sys.path.append("tuna")

this_path = os.path.dirname(__file__)

from tuna.dbBase.sql_alchemy import DbSession
from tuna.go_fish import load_machines, compose_worker_list, compose_f_vals, get_kwargs
from tuna.worker_interface import WorkerInterface
from tuna.fin_class import FinClass
from tuna.session import Session
from tuna.tables import DBTables, ConfigType
from tuna.db_tables import connect_db
from import_configs import import_cfgs
from load_job import test_tag_name as tag_name_test, add_jobs


class CfgImportArgs():
  config_type = ConfigType.convolution,
  command = None
  batches = None
  batch_list = []
  file_name = None
  mark_recurrent = False
  tag = None
  tag_only = False


class LdJobArgs():
  config_type = ConfigType.convolution,
  tag = None
  all_configs = False
  algo = None
  solvers = [('', None)]
  only_app = False
  tunable = False
  cmd = None
  label = None
  fin_steps = None
  session_id = None


def add_fin_find_compile_job(session):
  #import configs
  args = CfgImportArgs()
  args.tag = 'test_fin_builder'
  args.mark_recurrent = True
  args.file_name = f"{this_path}/../utils/configs/conv_configs_NCHW.txt"

  dbt = DBTables(session_id=session, config_type=args.config_type)
  counts = import_cfgs(args, dbt)

  #load jobs
  args = LdJobArgs
  args.label = 'tuna_pytest_fin_builder'
  args.tag = 'test_fin_builder'
  args.fin_steps = ['miopen_find_compile', 'miopen_find_eval']
  args.session_id = session

  connect_db()
  counts = {}
  counts['cnt_jobs'] = 0
  dbt = DBTables(session_id=None, config_type=args.config_type)
  if args.tag:
    try:
      tag_name_test(args.tag, dbt)
    except ValueError as terr:
      LOGGER.error(terr)

  add_jobs(args, counts, dbt)


class GoFishArgs():
  local_machine = True
  fin_steps = None
  session_id = None
  arch = None
  num_cu = None
  machines = None
  restart_machine = None
  update_applicability = None
  find_mode = None
  blacklist = None
  update_solvers = None
  config_type = None
  reset_interval = None
  dynamic_solvers_only = False
  label = 'pytest_fin_builder'
  docker_name = None
  ticket = None
  solver_id = None


def test_fin_builder():
  args = GoFishArgs()
  machine_lst = load_machines(args)
  machine = machine_lst[0]

  #create a session
  worker_ids = range(machine.get_num_cpus())
  f_vals = compose_f_vals(args, machine)
  f_vals["num_procs"] = Value('i', len(worker_ids))
  kwargs = get_kwargs(0, f_vals, args)
  worker = WorkerInterface(**kwargs)
  worker.machine.arch='gfx908'
  worker.machine.num_cu=120
  args.session_id = Session().add_new_session(args, worker)
  assert (args.session_id)

  #update solvers
  kwargs = get_kwargs(0, f_vals, args)
  fin_worker = FinClass(**kwargs)
  assert (fin_worker.get_solvers())

  #load jobs
  add_fin_find_compile_job(args.session_id)
  num_jobs = 0
  with DbSession() as session:
    get_jobs = f"SELECT count(*) from conv_job where session={args.session_id} and state='new';"
    res = session.execute(get_jobs)
    for row in res:
      assert (row[0] > 0)
      num_jobs = row[0]

  #get applicability
  args.update_applicability = True
  args.label = None
  worker_lst = compose_worker_list(machine_lst, args)
  for worker in worker_lst:
    worker.join()

  #compile
  args.update_applicability = False
  args.fin_steps = ["miopen_find_compile"]
  worker_lst = compose_worker_list(machine_lst, args)
  for worker in worker_lst:
    worker.join()

  with DbSession() as session:
    get_jobs = f"SELECT count(*) from conv_job where session={args.session_id} and state in ('compiled');"
    row = session.execute(get_jobs)
    for row in res:
      assert (row[0] == num_jobs)
