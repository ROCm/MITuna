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
""" Module to centralize command line argument parsing """
import sys
import argparse
from enum import Enum
from typing import List, Optional
import jsonargparse
from tuna.miopen.utils.config_type import ConfigType
from tuna.libraries import Library


class TunaArgs(Enum):
  """ Enumeration of all the common argument supported by setup_arg_parser """
  ARCH: str = 'arch'
  NUM_CU: str = 'num_cu'
  DIRECTION: str = 'direction'
  VERSION: str = 'version'
  CONFIG_TYPE: str = 'config_type'
  SESSION_ID: str = 'session_id'
  MACHINES: str = 'machines'
  REMOTE_MACHINE: str = 'remote_machine'
  LABEL: str = 'label'
  RESTART_MACHINE: str = 'restart_machine'
  DOCKER_NAME: str = 'docker_name'


def setup_arg_parser(desc: str,
                     arg_list: List[TunaArgs],
                     parser: argparse.Namespace = None,
                     with_yaml: bool = True) -> Optional[argparse.Namespace]:
  """ function to aggregate common command line args """
  parser = jsonargparse.ArgumentParser(description=desc)

  if parser is not None:
    if with_yaml:
      parser.add_argument('--yaml', action=jsonargparse.ActionConfigFile)

    if TunaArgs.ARCH in arg_list:
      parser.add_argument(
          '-a',
          '--arch',
          type=str,
          dest='arch',
          default=None,
          required=False,
          help='Architecture of machines',
          choices=['gfx900', 'gfx906', 'gfx908', 'gfx1030', 'gfx90a'])
    if TunaArgs.NUM_CU in arg_list:
      parser.add_argument('-n',
                          '--num_cu',
                          dest='num_cu',
                          type=int,
                          default=None,
                          required=False,
                          help='Number of CUs on GPU',
                          choices=['36', '56', '60', '64', '104', '110', '120'])
    if TunaArgs.DIRECTION in arg_list:
      parser.add_argument(
          '-d',
          '--direction',
          type=str,
          dest='direction',
          default=None,
          help='Direction of tunning, None means all (fwd, bwd, wrw), \
                          fwd = 1, bwd = 2, wrw = 4.',
          choices=[None, '1', '2', '4'])
    if TunaArgs.CONFIG_TYPE in arg_list:
      parser.add_argument('-C',
                          '--config_type',
                          dest='config_type',
                          help='Specify configuration type',
                          default=ConfigType.convolution,
                          choices=[cft.value for cft in ConfigType],
                          type=ConfigType)
    # pylint: disable=duplicate-code
    if TunaArgs.SESSION_ID in arg_list:
      parser.add_argument('--session_id',
                          dest='session_id',
                          type=int,
                          help='Session ID to be used as tuning tracker.\
        Allows to correlate DB results to tuning sessions')
    # pylint: enable=duplicate-code
    if TunaArgs.MACHINES in arg_list:
      parser.add_argument('-m',
                          '--machines',
                          dest='machines',
                          type=str,
                          default=None,
                          required=False,
                          help='Specify machine ids to use, comma separated')
    if TunaArgs.REMOTE_MACHINE in arg_list:
      parser.add_argument('--remote_machine',
                          dest='remote_machine',
                          action='store_true',
                          default=False,
                          help='Run the process on a network machine')
    if TunaArgs.LABEL in arg_list:
      parser.add_argument('-l',
                          '--label',
                          dest='label',
                          type=str,
                          default=None,
                          help='Specify label for jobs')
    if TunaArgs.RESTART_MACHINE in arg_list:
      parser.add_argument('-r',
                          '--restart',
                          dest='restart_machine',
                          action='store_true',
                          default=False,
                          help='Restart machines')
    if TunaArgs.DOCKER_NAME in arg_list:
      parser.add_argument(
          '--docker_name',
          dest='docker_name',
          type=str,
          default='miopentuna',
          help='Select a docker to run on. (default miopentuna)')

  return parser


def clean_args() -> None:
  """clean arguments"""
  libs: List[Library] = [elem.value for elem in Library]
  for lib in libs:
    if lib in sys.argv:
      sys.argv.remove(lib)


def args_check(args: argparse.Namespace, parser: argparse.Namespace) -> None:
  """Common scripts args check function"""
  if args.machines is not None:
    args.machines = [int(x) for x in args.machines.split(',')
                    ] if ',' in args.machines else [int(args.machines)]

  args.local_machine = not args.remote_machine

  if args.init_session and not args.label:
    parser.error(
        "When setting up a new tunning session the following must be specified: "\
        "label.")


# type: ignore
def get_import_cfg_parser(
    with_yaml: bool = True) -> jsonargparse.ArgumentParser:
  """Return parser for import_configs subcommand"""

  parser = setup_arg_parser(
      'Import MIOpenDriver commands and MIOpen performance DB entries.',
      [TunaArgs.VERSION, TunaArgs.CONFIG_TYPE],
      with_yaml=with_yaml)

  group = parser.add_mutually_exclusive_group()

  group.add_argument('--print_models',
                     dest='print_models',
                     action='store_true',
                     help='Print models from table')

  parser.add_argument('-b',
                      '--batches',
                      type=str,
                      dest='batches',
                      help='Batch sizes to iterate over in the given configs')
  parser.add_argument('--batchsize',
                      dest='batchsize',
                      type=int,
                      default=None,
                      required=False,
                      help='Specify model batchsize')
  parser.add_argument(
      '-c',
      '--command',
      type=str,
      dest='command',
      default=None,
      help='Command override: run a different command on the imported configs',
      choices=[None, 'conv', 'convfp16', 'convbfp16'])
  parser.add_argument('-d',
                      '--driver',
                      dest='driver',
                      type=str,
                      default=None,
                      help='Specify driver cmd')
  parser.add_argument('-f',
                      '--file_name',
                      type=str,
                      dest='file_name',
                      help='File to import')
  parser.add_argument('--fw_version',
                      dest='fw_version',
                      type=int,
                      default=None,
                      required=False,
                      help='Specify framework version')
  parser.add_argument('-g',
                      '--gpu_count',
                      dest='gpu_count',
                      type=int,
                      default=None,
                      required=False,
                      help='Specify number of gpus the benchmark runs on')
  parser.add_argument(
      '--mark_recurrent',
      dest='mark_recurrent',
      action="store_true",
      help='Indicate whether you want the configs to be marked as recurrent')
  parser.add_argument('--md_version',
                      dest='md_version',
                      type=int,
                      default=None,
                      required=False,
                      help='Specify model version')
  parser.add_argument('-t',
                      '--tag',
                      type=str,
                      dest='tag',
                      help='Tag to mark the origin of this \
                      config, if config not present it will insert. No wildcard columns for \
                      tagging.')
  parser.add_argument(
      '-T',
      '--tag_only',
      action='store_true',
      dest='tag_only',
      help=
      'Tag to mark the origin of this config but skips the insert new config \
                      step in case the config does not exist in the table. Wildcard columns \
                      allowed for tagging')

  return parser
