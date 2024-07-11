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
from sqlalchemy.inspection import inspect

from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.tables import MIOpenDBTables
from utils import GoFishArgs
from utils import add_test_session, add_test_jobs
from tuna.miopen.miopen_lib import MIOpen
from tuna.miopen.utils.config_type import ConfigType
from tuna.utils.utility import serialize_job_config_row
from tuna.miopen.celery_tuning.celery_tasks import prep_kwargs
from tuna.libraries import Operation
from tuna.miopen.celery_tuning.celery_tasks import prep_worker
from tuna.parse_args import TunaArgs, setup_arg_parser, args_check
from tuna.miopen.worker.fin_utils import get_fin_result
from tuna.celery_app.celery_app import app, purge_queue


def test_fin_builder():
  miopen = MIOpen()
  miopen.args = GoFishArgs()
  miopen.args.label = 'tuna_pytest_fin_builder'
  miopen.args.session_id = add_test_session(label=miopen.args.label)

  #load jobs
  dbt = MIOpenDBTables(config_type=ConfigType.convolution)
  num_jobs = add_test_jobs(miopen, miopen.args.session_id, dbt,
                           miopen.args.label, miopen.args.label,
                           ['miopen_find_compile', 'miopen_find_eval'],
                           'test_add_fin_find_compile_job',
                           'miopenConvolutionAlgoGEMM')
  #assert (num_jobs)
  num_jobs = 3
  return

  #testing process_pdb_compile in process_fin_builder_results
  miopen.args.update_applicability = False
  miopen.args.fin_steps = ["miopen_find_compile"]
  miopen.fetch_state.add('new')
  miopen.operation = Operation.COMPILE
  miopen.set_state = 'compile_start'
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

  with DbSession() as session:
    valid_fin_err = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='errored')\
                                         .filter(dbt.job_table.result.contains('%Find Compile: No results%'))\
                                         .count()
    #ommiting valid Fin/MIOpen errors
    num_jobs = (num_jobs - valid_fin_err)
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='compiled').count()
    #assert (count == num_jobs)

  miopen.args.fin_steps = "miopen_find_compile"
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
          f"d_test_db_sess_{miopen.args.session_id}_miopen_find_compile")

  miopen.update_operation()
  assert 'new' in miopen.fetch_state
  assert miopen.set_state == 'compile_start'
  assert miopen.operation == Operation.COMPILE

  assert miopen.has_tunable_operation()

  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)\
                             .filter(dbt.job_table.reason=='tuna_pytest_fin_builder')
    job_query.update({dbt.job_table.state: 'compile_start'})
    session.commit()
    miopen.reset_job_state_on_ctrl_c()
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='new').count()
    #assert count == num_jobs

  #testing process_pdb_compile in process_fin_builder_results
  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)\
                             .filter(dbt.job_table.reason=='tuna_pytest_fin_builder')
    job_query.update({dbt.job_table.fin_step: 'miopen_perf_compile'})
  miopen.args.fin_steps = "miopen_perf_compile"

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
                             .filter(dbt.job_table.reason=='tuna_pytest_fin_builder')
    job_query.update({dbt.job_table.state: 'new'})
    session.commit()
    count = session.query(dbt.find_db_table).filter(
        dbt.find_db_table.session == miopen.args.session_id).count()
    #assert (count == num_jobs)
    print(count)

  with DbSession() as session:
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='compile_start').count()
  print(count)
  db_name = os.environ['TUNA_DB_NAME']
  miopen.enqueue_jobs(1, f"test_{db_name}")
  print('Done enqueue')
  ins = app.control.inspect()
  with DbSession() as session:
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='compile_start').count()
  assert count == 4
  print(ins.active())
  print(ins.scheduled())
  print(ins.registered)
  #q_name == f"compile_q_{db_name}_sess_{miopen.args.session_id}"
  #purge_queue([q_name])
