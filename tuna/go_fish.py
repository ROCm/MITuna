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
"""Script to launch tuning jobs, or execute commands on available machines"""
from multiprocessing import Value, Lock, Queue as mpQueue
from subprocess import Popen, PIPE
import sys

from tuna.machine import Machine
from tuna.utils.logger import setup_logger
from tuna.builder import Builder
from tuna.evaluator import Evaluator
from tuna.dbBase.sql_alchemy import DbSession
from tuna.parse_args import TunaArgs, setup_arg_parser
from tuna.tables import ConfigType
from tuna.metadata import MIOPEN_ALG_LIST
from tuna.helper import print_solvers
from tuna.miopen_tables import FinStep

from tuna.fin_class import FinClass
from tuna.utils.utility import get_env_vars
from tuna.fin_builder import FinBuilder
from tuna.fin_eval import FinEvaluator
from tuna.worker_interface import WorkerInterface
from tuna.session import Session

# Setup logging
LOGGER = setup_logger('go_fish')


def parse_args():
  # pylint: disable=too-many-statements
  """Function to parse arguments"""
  parser = setup_arg_parser('Run Performance Tuning on a certain ' \
      'architecture', [TunaArgs.ARCH, TunaArgs.NUM_CU, TunaArgs.VERSION,
                       TunaArgs.CONFIG_TYPE])
  parser.add_argument('-d',
                      '--docker_exec',
                      dest='execute_docker_cmd',
                      type=str,
                      default=None,
                      help='execute in a docker on each machine')
  parser.add_argument('-e',
                      '--exec',
                      dest='execute_cmd',
                      type=str,
                      default=None,
                      help='execute on each machine')
  parser.add_argument('--docker_name',
                      dest='docker_name',
                      type=str,
                      default='miopentuna',
                      help='Select a docker to run on. (default miopentuna)')
  parser.add_argument('--ticket',
                      dest='ticket',
                      type=str,
                      default=None,
                      help='Specify tuning ticket number')
  parser.add_argument('-i',
                      '--reset_interval',
                      type=int,
                      dest='reset_interval',
                      required=False,
                      help='Restart interval for job in hours.')
  parser.add_argument('-l',
                      '--label',
                      dest='label',
                      type=str,
                      default=None,
                      help='Specify label for jobs')
  parser.add_argument('-m',
                      '--machines',
                      dest='machines',
                      type=str,
                      default=None,
                      required=False,
                      help='Specify machine ids to use, comma separated')
  parser.add_argument('--local_machine',
                      dest='local_machine',
                      action='store_true',
                      default=False,
                      help='Run the process on this machine')
  parser.add_argument('-r',
                      '--restart',
                      dest='restart_machine',
                      action='store_true',
                      default=False,
                      help='Restart machines')
  parser.add_argument('-s',
                      '--status',
                      dest='check_status',
                      action='store_true',
                      default=False,
                      help='Check the status of machines')
  parser.add_argument('--dynamic_solvers_only',
                      dest='dynamic_solvers_only',
                      action='store_true',
                      default=False,
                      help='Only tune dynamic solvers.')
  parser.add_argument(
      '--fin_steps',
      type=str,
      dest='fin_steps',
      help='Specify fin steps. Multiple steps should be comma separated.')
  parser.add_argument(
      '--find_mode',
      dest='find_mode',
      type=int,
      default=1,
      help='Set the MIOPEN_FIND_MODE environment variable for MIOpen',
      choices=[1, 3])
  parser.add_argument(
      '--session_id',
      action='store',
      type=int,
      dest='session_id',
      help=
      'Session ID to be used as tuning tracker. Allows to correlate DB results to tuning sessions'
  )
  parser.add_argument('--init_session',
                      action='store_true',
                      dest='init_session',
                      help='Set up a new tuning session.')
  parser.add_argument(
      '--solver_id',
      type=int,
      dest='solver_id',
      default=None,
      help='Specify solver_id. Use --list_solvers to see options')
  parser.add_argument(
      '-B',
      '--blacklist',
      dest='blacklist',
      type=str,
      default=None,
      help='MIOpen blacklist algorithm, if multiple then comma separate')

  group = parser.add_mutually_exclusive_group()
  group.add_argument('--list_solvers',
                     action='store_true',
                     dest='list_solvers',
                     help='List of solvers from the solver table')
  group.add_argument('-f',
                     '--find_enforce',
                     type=str,
                     dest='find_enforce',
                     default=None,
                     help='MIOPEN_FIND_ENFORCE value',
                     choices=['1', '3', '4'])

  group.add_argument('--compile',
                     dest='compile',
                     action="store_true",
                     help='Compile jobs.')
  group.add_argument('--run_perf',
                     dest='run_perf',
                     action="store_true",
                     help='Run perfdb update.')
  group.add_argument('--run_find',
                     dest='run_find',
                     action="store_true",
                     help='Run finddb update.')
  group.add_argument('--bin_cache',
                     dest='bin_cache',
                     action="store_true",
                     help='Run binary cache generation.')
  # JD: implement the following two using fin_steps
  parser.add_argument('--update_solvers',
                      dest='update_solvers',
                      action='store_true',
                      help='Update the list of solvers in the database')
  parser.add_argument('--update_applicability',
                      dest='update_applicability',
                      action='store_true',
                      help='Update the applicability table in the database')
  parser.add_argument(
      '--arch_num_cu_list',
      type=str,
      default=None,
      dest='arch_num_cu_list',
      help='comma delimited list of arch-skew for applicability')

  args = parser.parse_args()

  if args.list_solvers:
    print_solvers()

  if args.arch_num_cu_list:
    args.arch_num_cu_list = args.arch_num_cu_list.split(',')

  if args.fin_steps:
    check_fin_args(args, parser)

  if args.bin_cache:
    args.find_mode = 3

  if args.find_mode is None and not (args.check_status or
                                     args.restart_machine or args.execute_cmd or
                                     args.execute_docker_cmd):
    parser.error('find_mode must be specified for a tuning run')

  if args.blacklist:
    check_blacklist(args, parser)

  if args.machines is not None:
    args.machines = [int(x) for x in args.machines.split(',')
                    ] if ',' in args.machines else [int(args.machines)]

  if args.init_session and not (args.arch and args.num_cu and args.label and
                                args.local_machine):
    parser.error(
        "When setting up a new tunning session the following must be specified: "\
        "arch, num_cu, reason, local_machine.")

  fin_session_steps = [
      'miopen_find_compile', 'miopen_find_eval', 'miopen_perf_compile',
      'miopen_perf_eval', 'get_applicability', 'find_compile', 'find_eval'
  ]
  has_fin = False
  if args.fin_steps:
    has_fin = all(x in fin_session_steps for x in args.fin_steps)

  if (args.update_applicability or has_fin or args.compile or
      args.run_perf) and not args.session_id:
    parser.error("session_id must be specified with this operation")

  return args


def check_fin_args(args, parser):
  """Helper function for fin args"""
  valid_fin_steps = list(k for k in FinStep.__members__)
  if ',' in args.fin_steps:
    parser.error('Multiple fin_steps currently not supported')
  f_steps = args.fin_steps.split(',')
  args.fin_steps = f_steps
  for step in args.fin_steps:
    if step not in valid_fin_steps:
      parser.error("Supported fin steps are: {}".format(valid_fin_steps))
  assert len(args.fin_steps) == 1


def check_blacklist(args, parser):
  """Helper function"""
  args.blacklist = args.blacklist.split(',')
  for sol in args.blacklist:
    if sol not in MIOPEN_ALG_LIST:
      parser.error("Incorrect blacklist value")


def load_machines(args):
  """Function to get available machines from the DB"""
  cmd = 'hostname'
  subp = Popen(cmd, stdout=PIPE, shell=True, universal_newlines=True)
  hostname = subp.stdout.readline().strip()
  LOGGER.info('hostname = %s', hostname)
  with DbSession() as session:
    query = session.query(Machine)
    if args.arch:
      query = query.filter(Machine.arch == args.arch)
    if args.num_cu:
      query = query.filter(Machine.num_cu == args.num_cu)
    if not args.machines and not args.local_machine:
      query = query.filter(Machine.available == 1)
    if args.machines:
      query = query.filter(Machine.id.in_(args.machines))
    if args.local_machine:
      query = query.filter(Machine.remarks == hostname)

    res = query.all()

    if args.local_machine:
      if res:
        res[0].local_machine = True
      else:
        res = [Machine(hostname=hostname, local_machine=True)]
        LOGGER.info(
            'Local machine not in database, continue with incomplete details')

    if not res:
      LOGGER.info('No machine found for specified requirements')

  return res


def get_envmt(args):
  """Function to construct environment var"""
  envmt = ["MIOPEN_LOG_LEVEL=4"]

  envmt.append("MIOPEN_SQLITE_KERN_CACHE=ON")
  envmt.append("MIOPEN_DEBUG_IMPLICIT_GEMM_FIND_ALL_SOLUTIONS=1")

  if args.find_mode:
    envmt.append("MIOPEN_FIND_MODE={}".format(args.find_mode))

  if args.compile:
    #env set in builder
    envmt.append("MIOPEN_DEBUG_CONV_GEMM=0")
    envmt.append("MIOPEN_DEBUG_COMPILE_ONLY=1")
  elif args.run_perf:
    envmt.append("MIOPEN_FIND_ENFORCE=4")
    #envmt.append("MIOPEN_DEBUG_CONV_GEMM=0")
  elif args.bin_cache:
    #find = 1
    pass
  elif args.find_enforce == '3':
    envmt.append("MIOPEN_FIND_ENFORCE=3")
  elif args.find_enforce == '4':
    envmt.extend(["MIOPEN_FIND_ENFORCE=4", "MIOPEN_DISABLE_CACHE=1"])

  if args.blacklist:
    bk_str = ", ".join(["{}=0".format(arg) for arg in args.blacklist])
    for bk_var in bk_str.split(','):
      envmt.append(bk_var)

  return envmt


def check_docker(worker, dockername="miopentuna"):
  """Checking for docker"""
  LOGGER.warning("docker not installed or requires sudo .... ")
  _, out2, _ = worker.exec_command("sudo docker info")
  while not out2.channel.exit_status_ready():
    LOGGER.warning(out2.readline())
  if out2.channel.exit_status > 0:
    LOGGER.warning("docker not installed or failed to run with sudo .... ")
  else:
    _, out, _ = worker.exec_command(
        "sudo docker images | grep {}".format(dockername))
    line = None
    for line in out.readlines():
      if line.find(dockername) != -1:
        LOGGER.warning('%s docker image exists', dockername)
        break
    if line is None:
      LOGGER.warning('%s docker image does not exist', dockername)


def check_status(worker, b_first, gpu_idx, machine, dockername="miopentuna"):
  """Function to check gpu_status"""

  if machine.chk_gpu_status(worker.gpu_id):
    LOGGER.info('Machine: (%s, %u) GPU_ID: %u OK', machine.hostname,
                machine.port, gpu_idx)
  else:
    LOGGER.info('Machine: (%s, %u) GPU_ID: %u ERROR', machine.hostname,
                machine.port, gpu_idx)

  if not b_first:
    return False
  b_first = False
  _, out, _ = worker.exec_command("docker info")
  while not out.channel.exit_status_ready():
    pass

  if out.channel.exit_status > 0:
    check_docker(worker, dockername)
  else:
    _, out, _ = worker.exec_command(
        "docker images | grep {}".format(dockername))
    line = None
    for line in out.readlines():
      if line.find(dockername) != -1:
        LOGGER.warning('%s docker image exists', dockername)
        break
    if line is None:
      LOGGER.warning('%s docker image does not exist', dockername)

  return True


def execute_docker(worker, docker_cmd, machine):
  """Function to executed docker cmd"""
  LOGGER.info('Running on host: %s port: %u', machine.hostname, machine.port)
  _, _, _ = worker.exec_docker_cmd(docker_cmd + " 2>&1")
  #logger output already printed by exec_docker_cmd
  #LOGGER.info(docker_cmd)
  #while not out.channel.exit_status_ready():
  #  lines = out.readline()
  #  LOGGER.info(lines.rstrip())
  #for line in out.readlines():
  #  LOGGER.info(line.rstrip())

  return True


def get_kwargs(gpu_idx, f_vals, args):
  """Helper function to set up kwargs for worker instances"""
  envmt = f_vals["envmt"].copy()
  # JD: Move it down to the evaluator class
  if not args.compile:
    #compile don't use the gpu
    envmt.append("HIP_VISIBLE_DEVICES={}".format(gpu_idx))
  if args.config_type is None:
    args.config_type = ConfigType.convolution

  kwargs = {
      'machine': f_vals["machine"],
      'gpu_id': gpu_idx,
      'num_procs': f_vals["num_procs"],
      'barred': f_vals["barred"],
      'bar_lock': f_vals["bar_lock"],
      'envmt': envmt,
      'reset_interval': args.reset_interval,
      'fin_steps': args.fin_steps,
      'dynamic_solvers_only': args.dynamic_solvers_only,
      'job_queue': f_vals["job_queue"],
      'queue_lock': f_vals["queue_lock"],
      'label': args.label,
      'docker_name': args.docker_name,
      'bin_cache': args.bin_cache,
      'end_jobs': f_vals['end_jobs'],
      'config_type': args.config_type,
      'arch_num_cu_list': args.arch_num_cu_list,
      'session_id': args.session_id
  }

  return kwargs


def launch_worker(gpu_idx, f_vals, worker_lst, args):
  """Function to launch worker"""
  # pylint: disable=too-many-branches
  worker = None
  kwargs = get_kwargs(gpu_idx, f_vals, args)

  if args.compile:
    kwargs['fetch_state'] = ['new']
    worker = Builder(**kwargs)
  elif args.run_perf:
    #if no compiled jobs go ahead and start compiling on eval machine
    kwargs['fetch_state'] = ['compiled']
    worker = Evaluator(**kwargs)
  elif args.run_find or args.bin_cache:
    kwargs['fetch_state'] = ['new']
    worker = Evaluator(**kwargs)
  elif args.fin_steps:
    if 'miopen_find_compile' in args.fin_steps or 'miopen_perf_compile' in args.fin_steps:
      kwargs['fetch_state'] = ['new']
      worker = FinBuilder(**kwargs)
    elif 'miopen_find_eval' in args.fin_steps or 'miopen_perf_eval' in args.fin_steps:
      kwargs['fetch_state'] = ['compiled']
      worker = FinEvaluator(**kwargs)
    else:
      raise ValueError('Unsupported fin step')
  elif args.init_session:
    worker = WorkerInterface(**kwargs)
    Session().add_new_session(args, worker)
    return True
  else:
    kwargs['fetch_state'] = ['new']
    worker = Evaluator(**kwargs)

  ret = False
  if args.check_status:
    if not check_status(worker, f_vals["b_first"], gpu_idx, f_vals["machine"],
                        args.docker_name):
      ret = True
  elif args.execute_cmd:
    # JD: Move the worker.exec_command to machine
    LOGGER.info(args.execute_cmd)
    _, _, _ = worker.exec_command(args.execute_cmd + " 2>&1 ")
    #log printed by exec_command
    #for line in out.readlines():
    #  LOGGER.info(line.rstrip())
    ret = False
  elif args.execute_docker_cmd:
    execute_docker(worker, args.execute_docker_cmd, f_vals["machine"])
    ret = False
  else:
    worker.start()
    worker_lst.append(worker)
    ret = True

  return ret


def do_fin_work(args, gpu, f_vals):
  """Helper function to execute job independendent fin work"""
  kwargs = get_kwargs(gpu, f_vals, args)
  fin_worker = FinClass(**kwargs)

  if args.update_solvers:
    if not fin_worker.get_solvers():
      LOGGER.error('No solvers returned from Fin class')

  if args.update_applicability:
    if not fin_worker.applicability():
      LOGGER.error('Applicability not returned from Fin class')

  return True


def compose_f_vals(args, machine):
  """Compose dict for WorkerInterface constructor"""
  f_vals = {}
  f_vals["barred"] = Value('i', 0)
  f_vals["bar_lock"] = Lock()
  f_vals["queue_lock"] = Lock()
  #multiprocess queue for jobs, shared on machine
  f_vals["job_queue"] = mpQueue()
  f_vals["machine"] = machine
  f_vals["envmt"] = get_envmt(args)
  f_vals["b_first"] = True
  f_vals["end_jobs"] = Value('i', 0)

  return f_vals


def compose_worker_list(res, args):
  # pylint: disable=too-many-branches
  """Helper function to compose worker_list"""
  worker_lst = []
  fin_work_done = False
  for machine in res:
    if args.restart_machine:
      machine.restart_server(wait=False)
      continue
    if args.compile:
      #determine number of processes by compute capacity
      env = get_env_vars()
      if env['slurm_cpus'] > 0:
        num_procs = int(env['slurm_cpus'])
      else:
        # JD: This sould be the responsibility of the machine class
        num_procs = int(machine.get_num_cpus())
      if num_procs <= 0:
        LOGGER.error('num_procs must be bigger than zero to launch worker')
        LOGGER.error('Cannot launch worker on machine: %s', machine.id)
        return None
      worker_ids = range(num_procs)
    else:
      worker_ids = machine.avail_gpus

    f_vals = compose_f_vals(args, machine)
    if worker_ids:  # This machine has GPUs
      f_vals["num_procs"] = Value('i', len(worker_ids))
    else:
      f_vals["num_procs"] = Value('i', machine.get_num_cpus())
      worker_ids = range(machine.get_num_cpus())

    if (args.update_solvers or args.update_applicability) and not fin_work_done:
      do_fin_work(args, 0, f_vals)
      fin_work_done = True
      break

    for gpu_idx in worker_ids:
      LOGGER.info('launch mid %u, proc %u', machine.id, gpu_idx)
      if not launch_worker(gpu_idx, f_vals, worker_lst, args):
        break
      if args.init_session:
        break

  return worker_lst


def main():
  """Main function to start Tuna"""
  LOGGER.info(sys.argv)
  args = parse_args()

  if args.list_solvers:
    return

  try:
    res = load_machines(args)

    worker_lst = compose_worker_list(res, args)
    if worker_lst is None:
      return

    for worker in worker_lst:
      worker.join()
      LOGGER.warning('Process finished')
  except KeyboardInterrupt:
    LOGGER.warning('Interrupt signal caught')


if __name__ == '__main__':
  main()
