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
""" test all generator scripts """
import pdb
import sys

import tuna.gen_finddb as G0
import tuna.gen_fastdb as G1
import tuna.gen_tunadata as G2
from tuna.utils.fdb_key_utils import explode_fdb_keys
import tuna.utils.tools.df as df_tools

finddb_args = G0.FinddbParsing.get_default_finddb_args()
finddb_args[G0.FinddbParsing.ARGS.SESSION_IDS.name] = [15
                                                      ]  # set session id to 15

finddb = G0.gen_finddb(**finddb_args)  # generate finddb for session_id 15
assert (not finddb['session'].unique() or finddb['session'].unique() == [15])

finddb = finddb.iloc[:100000, :]  # get a small subset of finddb for testing

fastdb = G1.finddb_to_nonthresholded_fastdb(finddb,
                                            cols_with_conv_params=['fdb_key'])
uniques = fastdb['fdb_key'].unique()
for i, fdb_key in enumerate(uniques):
  sys.stdout.write(
      f'\r{i}/{len(uniques)}                                       ')
  fastest = fastdb[fastdb['fdb_key'] == fdb_key]
  assert len(fastest) == 1  # there can be only 1 fastest entry per config
  for kernel_time in finddb[finddb['fdb_key'] == fdb_key]['kernel_time']:
    assert kernel_time >= float(
        fastest['kernel_time'])  # assert that the claimed
    # fastest entry is indeed the fastest

exploded_fdb_keys = explode_fdb_keys(finddb['fdb_key'])
rest_of_finddb = finddb.loc[:, finddb.columns != 'fdb_key']
explodedfinddb = df_tools.combine(exploded_fdb_keys, rest_of_finddb)

assert len(explodedfinddb) == len(finddb)

cols_with_conv_params = [x for x in exploded_fdb_keys.columns]
explodedfastdb = G1.finddb_to_nonthresholded_fastdb(
    explodedfinddb, cols_with_conv_params=cols_with_conv_params)
assert len(explodedfastdb) == len(fastdb)
uniques2 = df_tools.unique_combinations(explodedfastdb,
                                        columns=cols_with_conv_params)
for i, conv_params in enumerate(uniques2):
  sys.stdout.write(
      f'\r{i}/{len(uniques)}                                       ')
  fastest = df_tools.select_multiple(explodedfastdb, conv_params)
  assert len(fastest) == 1  # there can be only 1 fastest entry per config
  for entry in df_tools.select_multiple(explodedfinddb, conv_params).iterrows():
    assert entry[1]['kernel_time'] >= float(
        fastest['kernel_time'])  # assert that the claimed
    # fastest entry is indeed the fastest

mldb, encodings = G2.gen_mldb(fastdb)
