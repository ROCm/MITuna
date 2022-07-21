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
"""This module implements basic metrics on the tuna database by creating
a view on the job table and running basic reports on the view
"""
import datetime

from tuna.utils.logger import setup_logger
from tuna.sql import DbCursor
from tuna.parse_args import TunaArgs, setup_arg_parser

LOGGER = setup_logger('TunaMetrics')


def parse_args():
  """Parse arguments supplied to the script"""
  parser = setup_arg_parser('Consume text perf-db and create table entries',
                            [TunaArgs.ARCH, TunaArgs.NUM_CU])
  parser.add_argument('-c',
                      '--commit_hash',
                      dest='commit_hash',
                      type=str,
                      default=None,
                      required=False,
                      help='commit_hash to search for')
  args = parser.parse_args()
  return args


def create_view(cur):
  """Creates view to query for information later"""
  #c.execute("DROP VIEW IF EXISTS `metrics`;")
  view = """CREATE OR REPLACE VIEW `metrics` AS \
					SELECT c1.id, j2.arch, j2.num_cu, j2.started, j2.completed, \
							timestampdiff(SECOND, j2.started, j2.completed) AS duration, j2.machine_id, j2.gpu_id, \
              j2.state, j2.commit_hash, \
							CASE j2.reason when j2.reason like \'recurring\' THEN 1 ELSE 0 END AS recurring \
							FROM `config` c1 \
					INNER JOIN job j2 ON c1.id=j2.config and j2.state=\"completed\" and \
          j2.commit_hash IS NOT NULL;"""
  cur.execute(view)


def get_arch_numbers(cur, arch, num_cu):
  """Calaculate runtime for architecture/num_cu pair """
  LOGGER.info("Calculating runtime for arch %s with num_cu %s ...\n", arch,
              num_cu)
  cur.execute(
      "SELECT sum(duration), commit_hash, count(id) from `metrics` where arch='{}' \
      and num_cu={} and recurring=1 group by commit_hash;".format(arch, num_cu))
  all_commits = cur.fetchall()
  for sum_c, hash_c, count_c in all_commits:
    print("Total time(sec) to run [{0: <5}] configs was: [{1: <10}] for hash " \
          "[{2}] --- with average [{3}] sec per config" \
          .format(count_c, str(datetime.timedelta(
              seconds=int(sum_c))).rjust(17, '-'),
                  hash_c[:5], str(round(sum_c/count_c, 2)).rjust(10, '-')))


def get_detailed_arch_numbers(cur, arch, num_cu):
  """Compute detailed statistics for each arch/num_cu pair"""
  LOGGER.info("Looking for details on arch/num_cu combination...\n")
  cur.execute("Select commit_hash, arch, num_cu, machine_id, gpu_id," \
              "sum(duration), count(id) from `metrics` where arch='{}'" \
              "and num_cu='{}' and recurring=1  and state='completed' "\
              "group by commit_hash, arch, num_cu, machine_id, gpu_id;"
              .format(arch, num_cu))
  hashes = cur.fetchall()
  last_hash = hashes[0][0]
  for row in hashes:
    if row[0] != last_hash:
      print("\n\n")
      last_hash = row[0]
    print("For hash [{}] where arch={} and num_cu={} for machine_id={} " \
          "on gpu_id={} it took on average {} sec per config"
          .format(row[0], row[1], row[2], row[3], row[4],
                  str(datetime.timedelta(
                      seconds=int(row[5] / row[6]))).rjust(10, ' ')))


def get_detailed_arch_numbers_by_commit(cur, arch, num_cu, commit_hash):
  """Compute detail wrt arch/num_cu and MIOpen commit hash"""
  LOGGER.info(
      "Looking for details on arch/num_cu combination for hash [%s]...\n",
      commit_hash)
  cur.execute("Select commit_hash, arch, num_cu, machine_id, gpu_id, " \
              "sum(duration), count(id) from `metrics` where arch='{}' " \
              "and num_cu='{}' and recurring=1  and state='completed' and "\
              "commit_hash='{}' group by commit_hash, arch, num_cu, " \
              "machine_id, gpu_id;"
              .format(arch, num_cu, commit_hash))
  hashes = cur.fetchall()
  last_machineid = hashes[0][3]
  for row in hashes:
    if row[3] != last_machineid:
      print("\n\n")
      last_machineid = row[3]
    print("For hash [{}] where arch={} and num_cu={} for machine_id={} " \
          "on gpu_id={} it took on average {} sec per config;"
          .format(row[0], row[1], row[2], row[3], row[4],
                  str(datetime.timedelta(seconds=int(row[5] / row[6]))).rjust(
                      10, ' ')))


def main():
  """ Main entry function """
  args = parse_args()
  options = "1. Total runtime for a specific architecture/num_cu \n" \
           "2. Detailed machine/GPU information for each commit hash " \
            "for a specific architecture/num_cu "
  print(options)
  inp = ""
  while True:
    try:
      inp = int(input("Enter number for query: "))
    except ValueError:
      LOGGER.error("ERR: Please enter a number")
      print(options)
      continue
    else:
      break

  #LOGGER.info("\n")
  with DbCursor() as cur:
    create_view(cur)
    if inp == 1:
      if args.commit_hash:
        LOGGER.warning("Note: commit_hash ignored")
      get_arch_numbers(cur, args.arch, args.num_cu)
    elif inp == 2:
      if args.commit_hash:
        get_detailed_arch_numbers_by_commit(cur, args.arch, args.num_cu,
                                            args.commit_hash)
      else:
        get_detailed_arch_numbers(cur, args.arch, args.num_cu)


if __name__ == '__main__':
  main()
