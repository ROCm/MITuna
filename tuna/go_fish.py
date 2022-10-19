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
"""! @brief Script to launch tuning jobs, or execute commands on available machines"""
import argparse
import sys
from tuna.utils.logger import setup_logger
from tuna.libraries import Library
from tuna.miopen.miopen_lib import MIOpen

# Setup logging
LOGGER = setup_logger('go_fish')


def parse_args():
  """Function to parse arguments"""
  parser = argparse.ArgumentParser()

  parser.add_argument('lib',
                      nargs='?',
                      default=Library.MIOPEN,
                      type=Library,
                      help="Specify library to run",
                      choices=Library)

  args, _ = parser.parse_known_args()
  return vars(args)


def setup_library(args):
  """Return Library class based on args"""
  if 'lib' not in args.keys() or args['lib'].value.lower(
  ) == Library.MIOPEN.value.lower():
    library = MIOpen()
  else:
    raise ValueError("Not implemented")

  return library


def main():
  """Main function to start Tuna"""
  LOGGER.info(sys.argv)
  args = parse_args()
  library = setup_library(args)

  try:

    #returns a list of workers/processes it started
    worker_lst = library.run()
    if worker_lst is None:
      return

    for worker in worker_lst:
      worker.join()
      LOGGER.warning('Process finished')
  except KeyboardInterrupt:
    LOGGER.warning('Interrupt signal caught')


if __name__ == '__main__':
  main()
