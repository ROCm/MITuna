import pdb
import sys

import tuna.gen_finddb as G0
import tuna.gen_fastdb as G1
import tuna.gen_tunadata as G2
from tuna.utils.fdb_key_utils import explode_fdb_keys
import tuna.utils.tools.df as df_tools

findDB = G0.gen_findDB(arch='gfx908')  # findDB for gfx908 (tuna_v="1.0.0")
assert (not findDB['arch'].unique() or findDB['arch'].unique() == ['gfx908'])

findDB = findDB.iloc[:100000, :]

fastDB = G1.findDB_to_nonthresholded_fastDB(findDB,
                                            cols_with_conv_params=['fdb_key'])
uniques = fastDB['fdb_key'].unique()
for i, fdb_key in enumerate(uniques):
  sys.stdout.write(
      f'\r{i}/{len(uniques)}                                       ')
  fastest = fastDB[fastDB['fdb_key'] == fdb_key]
  assert len(fastest) == 1  # there can be only 1 fastest entry per config
  for kernel_time in findDB[findDB['fdb_key'] == fdb_key]['kernel_time']:
    assert kernel_time >= float(
        fastest['kernel_time'])  # assert that the claimed
    # fastest entry is indeed the fastest

exploded_fdb_keys = explode_fdb_keys(findDB['fdb_key'])
rest_of_findDB = findDB.loc[:, findDB.columns != 'fdb_key']
explodedFindDB = df_tools.combine(exploded_fdb_keys, rest_of_findDB)

assert len(explodedFindDB) == len(findDB)

cols_with_conv_params = [x for x in exploded_fdb_keys.columns]
explodedFastDB = G1.findDB_to_nonthresholded_fastDB(
    explodedFindDB, cols_with_conv_params=cols_with_conv_params)
assert len(explodedFastDB) == len(fastDB)
uniques2 = df_tools.unique_combinations(explodedFastDB,
                                        columns=cols_with_conv_params)
for i, conv_params in enumerate(uniques2):
  sys.stdout.write(
      f'\r{i}/{len(uniques)}                                       ')
  fastest = df_tools.select_multiple(explodedFastDB, conv_params)
  assert len(fastest) == 1  # there can be only 1 fastest entry per config
  for entry in df_tools.select_multiple(explodedFindDB, conv_params).iterrows():
    assert entry[1]['kernel_time'] >= float(
        fastest['kernel_time'])  # assert that the claimed
    # fastest entry is indeed the fastest

mlDB, encodings = G2.gen_mlDB(fastDB)
