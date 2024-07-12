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
import os
import sys
import copy
from time import sleep
from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.machine_utility import load_machines
from tuna.miopen.db.tables import MIOpenDBTables
from utils import CfgImportArgs, LdJobArgs, GoFishArgs, add_test_jobs, add_test_session
from tuna.miopen.miopen_lib import MIOpen
from tuna.utils.logger import setup_logger
from tuna.miopen.utils.config_type import ConfigType
from tuna.utils.utility import serialize_job_config_row
from tuna.miopen.celery_tuning.celery_tasks import prep_kwargs
from tuna.machine import Machine
from tuna.libraries import Operation
from tuna.celery_app.celery_workers import launch_celery_worker, launch_worker_per_node
from tuna.celery_app.utility import get_q_name
from tuna.parse_args import TunaArgs, setup_arg_parser, args_check
from tuna.miopen.celery_tuning.celery_tasks import prep_worker
from tuna.celery_app.celery_app import app, purge_queue


def test_celery_workers():
  miopen = MIOpen()
  miopen.args = GoFishArgs()
  miopen.args.label = 'tuna_pytest_celery'
  miopen.args.session_id = add_test_session(label=miopen.args.label)

  #load jobs
  dbt = MIOpenDBTables(config_type=ConfigType.convolution)
  num_jobs = add_test_jobs(miopen, miopen.args.session_id, dbt,
                           miopen.args.label, miopen.args.label,
                           ['miopen_perf_compile'], 'test_add_celery_compile_job',
                           'miopenConvolutionAlgoGEMM')
  assert (num_jobs)

  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  miopen.operation = Operation.COMPILE
  miopen.dbt = MIOpenDBTables(session_id=miopen.args.session_id,
                              config_type=ConfigType.convolution)
  miopen.args.enqueue_only = False
  db_name = os.environ['TUNA_DB_NAME']

  q_name = get_q_name(miopen, op_compile=True)
  assert q_name == f"compile_q_{db_name}_sess_{miopen.args.session_id}"
  q_name = get_q_name(miopen, op_eval=True)
  assert q_name == f"eval_q_{db_name}_sess_{miopen.args.session_id}"
  _, subp_list = miopen.prep_tuning()
  assert subp_list
  for subp in subp_list:
    print(subp.pid)
    subp.kill()

  miopen.args.enqueue_only = True
  _, subp_list = miopen.prep_tuning()
  assert subp_list == []


  cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -n tuna_HOSTNAME_sess_{miopen.args.session_id} -Q test_{db_name}"  #pylint: disable=line-too-long
  subp_list = launch_worker_per_node([machine], cmd, True)
  sleep(2)
  assert subp_list
  for subp in subp_list:
    print(subp.pid)
    subp.kill()

  miopen.args.fin_steps = "miopen_perf_compile"
  miopen.db_name = "test_db"
  parser = setup_arg_parser(
      'Run Performance Tuning on a certain architecture', [
          TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION,
          TunaArgs.CONFIG_TYPE, TunaArgs.SESSION_ID, TunaArgs.MACHINES,
          TunaArgs.REMOTE_MACHINE, TunaArgs.LABEL, TunaArgs.RESTART_MACHINE,
          TunaArgs.DOCKER_NAME, TunaArgs.SHUTDOWN_WORKERS
      ])

  miopen.check_fin_args(parser)
  miopen.set_prefix()
  assert (miopen.prefix ==
          f"d_test_db_sess_{miopen.args.session_id}_miopen_perf_compile")

  miopen.update_operation()
  assert 'new' in miopen.fetch_state
  assert miopen.set_state == 'compile_start'
  assert miopen.operation == Operation.COMPILE

  assert miopen.has_tunable_operation()

  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)\
                             .filter(dbt.job_table.reason=='tuna_pytest_celery')
    job_query.update({dbt.job_table.state: 'compile_start'})
    session.commit()
    miopen.reset_job_state_on_ctrl_c()
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='new').count()
    assert count == num_jobs

  with DbSession() as session:
    jobs = miopen.get_jobs(session, miopen.fetch_state, miopen.set_state,
                           miopen.args.session_id)
    assert jobs
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
        'operation': miopen.operation,
        'arch': miopen.dbt.session.arch,
        'num_cu': miopen.dbt.session.num_cu,
        'kwargs': kwargs,
        'fdb_attr': fdb_attr
    }

    worker = prep_worker(copy.deepcopy(context))
    worker.dbt = miopen.dbt
    worker.fin_steps = miopen.args.fin_steps
    fin_json = worker.run()
    res_set.append((fin_json, context))

  with DbSession() as session:
    for fin_json, context in res_set:
      miopen.process_fin_builder_results(session, fin_json, context)
    count = session.query(dbt.find_db_table).filter(
        dbt.find_db_table.session == miopen.args.session_id).count()
    #assert (count == num_jobs)

  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)\
                             .filter(dbt.job_table.reason=='tuna_pytest_celery')
    job_query.update({dbt.job_table.state: 'new'})
    session.commit()

  db_name = os.environ['TUNA_DB_NAME']
  miopen.enqueue_jobs(1, f"test_{db_name}")
  print('Done enqueue')
  with DbSession() as session:
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='compile_start').count()
  assert count == 4
