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
import copy
import json
import pytest
from time import sleep
from multiprocessing import Value
import aioredis
import pytest_asyncio
from sqlalchemy.inspection import inspect

from utils import GoFishArgs, add_test_jobs, add_test_session
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.machine_utility import load_machines
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.miopen_lib import MIOpen
from tuna.miopen.utils.config_type import ConfigType
from tuna.utils.utility import serialize_job_config_row, arch2targetid
from tuna.miopen.celery_tuning.celery_tasks import prep_kwargs
from tuna.machine import Machine
from tuna.libraries import Operation
from tuna.celery_app.celery_workers import launch_worker_per_node
from tuna.celery_app.utility import get_q_name
from tuna.celery_app.celery_app import get_broker_env, get_backend_env
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.miopen.celery_tuning.celery_tasks import prep_worker
from tuna.miopen.worker.fin_utils import compose_config_obj, fin_job
from tuna.miopen.utils.lib_helper import get_worker


@pytest.mark.asyncio
async def test_celery_workers():
  miopen = MIOpen()
  miopen.args = GoFishArgs()
  miopen.args.label = 'tuna_pytest_celery'
  miopen.args.session_id = add_test_session(label=miopen.args.label)

  #load jobs
  dbt = MIOpenDBTables(config_type=ConfigType.convolution)
  num_jobs = add_test_jobs(miopen, miopen.args.session_id, dbt,
                           miopen.args.label, miopen.args.label,
                           ['miopen_perf_compile'],
                           'test_add_celery_compile_job',
                           'miopenConvolutionAlgoGEMM')
  #assert num_jobs
  num_jobs = 4

  machine_lst = load_machines(miopen.args)
  machine = machine_lst[0]
  miopen.operation = Operation.COMPILE
  miopen.dbt = MIOpenDBTables(session_id=miopen.args.session_id,
                              config_type=ConfigType.convolution)
  miopen.args.enqueue_only = False
  db_name = os.environ['TUNA_DB_NAME']

  #testing get_q_name
  q_name = get_q_name(miopen, op_compile=True)
  assert q_name == f"compile_q_{db_name}_sess_{miopen.args.session_id}"
  q_name = get_q_name(miopen, op_eval=True)
  assert q_name == f"eval_q_{db_name}_sess_{miopen.args.session_id}"
  # Test else branch (neither op_compile nor op_eval)
  q_name = get_q_name(miopen, op_compile=False, op_eval=False)
  assert q_name == f"unknown_op_{db_name}_sess_{miopen.args.session_id}"

  #testing prep_tuning
  _, subp_list = miopen.prep_tuning()
  assert subp_list
  for subp in subp_list:
    subp.kill()

  miopen.args.enqueue_only = True
  _, subp_list = miopen.prep_tuning()
  assert subp_list == []


  cmd = f"celery -A tuna.celery_app.celery_app worker -l info -E -n tuna_HOSTNAME_sess_{miopen.args.session_id} -Q {q_name}"  #pylint: disable=line-too-long
  #testing launch_worker_per_node
  subp_list = launch_worker_per_node([machine], cmd, True)
  #wait for workers to finish launch
  sleep(5)
  assert subp_list
  assert miopen.cancel_consumer(q_name)
  #wait for celery worker shutdown
  sleep(5)

  for subp in subp_list:
    print(subp.pid)
    assert subp.poll()
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

  #testing check_fin_args
  miopen.check_fin_args(parser)
  #testing set_prefix
  miopen.set_prefix()
  assert (miopen.prefix ==
          f"d_test_db_sess_{miopen.args.session_id}_miopen_perf_compile")

  #testing update_operation
  miopen.update_operation()
  assert 'new' in miopen.fetch_state
  assert miopen.set_state == 'compile_start'
  assert miopen.operation == Operation.COMPILE

  #testing has_tunable operation
  assert miopen.has_tunable_operation()

  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)\
                             .filter(dbt.job_table.reason=='tuna_pytest_celery')
    job_query.update({dbt.job_table.state: 'compile_start'})
    session.commit()
    #testing reset_job_staet_on_ctrl_c
    miopen.reset_job_state_on_ctrl_c()
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='new').count()
    assert count == num_jobs

  with DbSession() as session:
    jobs = miopen.get_jobs(session, miopen.fetch_state, miopen.set_state,
                           miopen.args.session_id)
    assert jobs
    #testing get_context_list
    context_list = miopen.get_context_list(session, [job for job in jobs])
    assert context_list
    assert len(context_list) == 4

    #testing serialized_job call
    serialized_jobs = miopen.serialize_jobs(session, [job for job in jobs])
    assert serialized_jobs

    #testing build_context call
    context_l = miopen.build_context(serialized_jobs)
    assert context_l

  #testing get_context_items
  assert miopen.get_context_items()
  #testing get_fdb_attr
  assert miopen.get_fdb_attr()

  entries = [job for job in jobs]

  job_config_rows = miopen.compose_work_objs_fin(session, entries, miopen.dbt)
  assert job_config_rows

  job_dct, config_dct = serialize_job_config_row(job_config_rows[0])
  #testing arch2targetid
  arch = arch2targetid(miopen.dbt.session.arch)
  assert arch == "gfx90a:sram-ecc+:xnack-"
  steps = ['alloc_buf', 'fill_buf', miopen.args.fin_steps[0]]

  #testing fin_job
  fjob = fin_job(steps, True, job_config_rows[0][0], job_config_rows[0][1],
                 miopen.dbt)
  assert fjob
  f_vals = miopen.get_f_vals(machine, range(0))
  kwargs = miopen.get_kwargs(0, f_vals, tuning=True)
  kwargs['job'] = job_dct
  kwargs['config'] = config_dct
  kwargs['avail_gpus'] = 1
  fdb_attr = [column.name for column in inspect(miopen.dbt.find_db_table).c]
  fdb_attr.remove("insert_ts")
  fdb_attr.remove("update_ts")
  context = {
      'job': job_dct,
      'config': config_dct,
      'operation': Operation.EVAL,
      'arch': miopen.dbt.session.arch,
      'num_cu': miopen.dbt.session.num_cu,
      'kwargs': kwargs,
      'fdb_attr': fdb_attr
  }

  worker = prep_worker(copy.deepcopy(context))
  worker_kwargs = prep_kwargs(
      context['kwargs'],
      [context['job'], context['config'], context['operation']])
  assert worker_kwargs['config']
  assert worker_kwargs['job']
  assert worker_kwargs['fin_steps'] == ['miopen_perf_compile']
  miopen.operation = Operation.EVAL
  fin_eval = get_worker(worker_kwargs, miopen.operation)

  #testing fin_job
  fjob = fin_job(steps, True, job_config_rows[0][0], job_config_rows[0][1],
                 miopen.dbt)
  #testing fin_pdb_input
  f_job = fin_eval.fin_pdb_input(fjob)
  assert f_job[0]['solvers'] == ['GemmBwd1x1_stride2']
  assert f_job[0]['miopen_perf_compile_result'] == [{
      'solver_name': 'GemmBwd1x1_stride2',
      'perf_compiled': False,
      'kernel_objects': []
  }]

  #testing fin_fdb_input
  steps = ['alloc_buf', 'fill_buf', ['miopen_find_compile']]
  f_job = fin_eval.fin_fdb_input(fjob)
  assert f_job
  assert f_job[0]['miopen_find_compile_result'] == [{
      'solver_name': 'GemmBwd1x1_stride2',
      'find_compiled': False,
      'kernel_objects': []
  }]

  #testing compose_config_obj
  conf_obj = compose_config_obj(job_config_rows[0][1], ConfigType.convolution)
  assert conf_obj
  assert conf_obj[
      'driver'] == "./bin/MIOpenDriver conv --batchsize 128 --spatial_dim 2 --pad_h 0 --pad_w 0 --pad_d 0 --conv_stride_h 2 --conv_stride_w 2 --conv_stride_d 0 --dilation_h 1 --dilation_w 1 --dilation_d 0 --group_count 1 --mode conv --pad_mode default --trans_output_pad_h 0 --trans_output_pad_w 0 --trans_output_pad_d 0 --out_layout NCHW --in_layout NCHW --fil_layout NCHW --in_d 1 --in_h 14 --in_w 14 --fil_d 1 --fil_h 1 --fil_w 1 --in_channels 1024 --out_channels 2048 --forw 2"

  miopen.operation = Operation.COMPILE
  f_vals = miopen.get_f_vals(Machine(local_machine=True), range(0))
  kwargs = miopen.get_kwargs(0, f_vals, tuning=True)
  fdb_attr = [column.name for column in inspect(miopen.dbt.find_db_table).c]
  fdb_attr.remove("insert_ts")
  fdb_attr.remove("update_ts")

  backend_host = os.environ['TUNA_CELERY_BACKEND_HOST']
  redis = await aioredis.from_url(f"redis://{backend_host}:6379/15")
  print('Established redis connection')
  counter = 1

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
    await redis.set(f"celery-task-meta-{counter}", json.dumps(fin_json))
    counter += 1

  print('Consuming from redis')
  assert miopen.consume(job_counter=counter, prefix=None)
  await redis.close()

  with DbSession() as session:
    for fin_json, context in res_set:
      #testing process_compile_results
      miopen.process_compile_results(session, fin_json, context)
    count = session.query(dbt.job_table).filter(
        dbt.job_table.session == miopen.args.session_id).count()
    assert count == num_jobs

  with DbSession() as session:
    job_query = session.query(
        dbt.job_table).filter(dbt.job_table.session == miopen.args.session_id)\
                             .filter(dbt.job_table.reason=='tuna_pytest_celery')
    job_query.update({dbt.job_table.state: 'new'})
    session.commit()

  db_name = os.environ['TUNA_DB_NAME']
  #testing enqueue_jobs
  job_counter = Value('i', 4)
  miopen.enqueue_jobs(job_counter, 1, f"test_{db_name}")
  print('Done enqueue')
  with DbSession() as session:
    count = session.query(dbt.job_table).filter(dbt.job_table.session==miopen.args.session_id)\
                                         .filter(dbt.job_table.state=='compile_start').count()
  assert count == 4


TUNA_CELERY_BROKER_HOST, TUNA_CELERY_BROKER_PORT, TUNA_CELERY_BROKER_USER, TUNA_CELERY_BROKER_PWD = get_broker_env(
)
assert TUNA_CELERY_BROKER_HOST
assert TUNA_CELERY_BROKER_PORT
assert TUNA_CELERY_BROKER_USER
assert TUNA_CELERY_BROKER_PWD

TUNA_CELERY_BACKEND_PORT, TUNA_CELERY_BACKEND_HOST = get_backend_env()
assert TUNA_CELERY_BACKEND_PORT
assert TUNA_CELERY_BACKEND_HOST


def test_launch_worker_per_node_exception():
  """Test exception handling in launch_worker_per_node"""
  from tuna.celery_app.celery_workers import launch_worker_per_node
  from unittest.mock import Mock

  # Create a mock machine with hostname
  machine = Mock()
  machine.hostname = "test_host"

  # Test with invalid command that will cause subprocess.Popen to fail
  # Using a command with null bytes which will raise an exception
  cmd = "test\x00command"
  result = launch_worker_per_node([machine], cmd, formatted=True)
  assert result is False


def test_launch_worker_per_gpu():
  """Test launch_worker_per_gpu function"""
  from tuna.celery_app.celery_workers import launch_worker_per_gpu
  from unittest.mock import Mock
  from time import sleep

  # Test 1: Normal execution with formatted=True
  machine = Mock()
  machine.hostname = "test_host"
  machine.get_avail_gpus = Mock(return_value=[0, 1])

  cmd = "echo test_HOSTNAME_GPUID"
  result = launch_worker_per_gpu([machine], cmd, formatted=True)
  assert result is not False
  assert isinstance(result, list)
  assert len(result) == 2

  # Clean up subprocesses
  for subp in result:
    subp.kill()
    subp.wait()
  sleep(0.1)

  # Test 2: No GPUs available
  machine_no_gpu = Mock()
  machine_no_gpu.hostname = "test_host"
  machine_no_gpu.get_avail_gpus = Mock(return_value=[])

  result = launch_worker_per_gpu([machine_no_gpu], cmd, formatted=True)
  assert result is False

  # Test 3: Exception during command replacement
  machine_error = Mock()
  machine_error.hostname = None  # This will cause an exception in replace()
  machine_error.get_avail_gpus = Mock(return_value=[0])

  result = launch_worker_per_gpu([machine_error], cmd, formatted=True)
  assert result is False

  # Test 4: Exception during subprocess creation
  machine_subprocess_error = Mock()
  machine_subprocess_error.hostname = "test_host"
  machine_subprocess_error.get_avail_gpus = Mock(return_value=[0])

  # Command with null bytes that will cause subprocess.Popen to fail
  bad_cmd = "test\x00command_HOSTNAME_GPUID"
  result = launch_worker_per_gpu([machine_subprocess_error],
                                 bad_cmd,
                                 formatted=True)
  assert result is False

  # Test 5: Unformatted command
  result = launch_worker_per_gpu([machine], "echo test", formatted=False)
  assert result is not False
  assert isinstance(result, list)

  # Clean up subprocesses
  for subp in result:
    subp.kill()
    subp.wait()
  sleep(0.1)


def test_launch_celery_worker():
  """Test launch_celery_worker function"""
  from tuna.celery_app.celery_workers import launch_celery_worker
  from tuna.libraries import Operation
  from time import sleep

  args = GoFishArgs()

  # Test 1: Operation.COMPILE (already tested via launch_worker_per_node)
  cmd = "echo test_compile"
  result = launch_celery_worker(Operation.COMPILE, cmd, args, formatted=False)
  assert result is not False
  assert isinstance(result, list)
  for subp in result:
    subp.kill()
    subp.wait()
  sleep(0.1)

  # Test 2: Operation.EVAL
  # Need to create a machine with GPUs for this test
  from unittest.mock import patch, Mock

  mock_machine = Mock()
  mock_machine.hostname = "test_host"
  mock_machine.get_avail_gpus = Mock(return_value=[0])

  with patch('tuna.celery_app.celery_workers.load_machines',
             return_value=[mock_machine]):
    cmd = "echo test_eval"
    result = launch_celery_worker(Operation.EVAL, cmd, args, formatted=False)
    assert result is not False
    assert isinstance(result, list)
    for subp in result:
      subp.kill()
      subp.wait()
    sleep(0.1)

  # Test 3: Invalid operation (should raise ValueError)
  import pytest
  with pytest.raises(
      ValueError, match='Operation does not support launching celery workers'):
    # Using an arbitrary string that's not a valid Operation
    invalid_op = "INVALID_OPERATION"
    launch_celery_worker(invalid_op, cmd, args, formatted=False)
