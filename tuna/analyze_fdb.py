import argparse
import sqlite3

from tuna.parsing import parse_fdb_line
from tuna.analyze_parse_db import get_sqlite_table
from tuna.driver_conv import DriverConvolution
from tuna.helper import valid_cfg_dims
from tuna.import_db import get_cfg_driver
from tuna.utils.logger import setup_logger

LOGGER = setup_logger('analyze_fdb')

def parse_args():
  """command line parsing"""
  parser = argparse.ArgumentParser(
      description='Merge Performance DBs once tunning is finished')
  parser.add_argument('-f',
                      '--fdb_file',
                      type=str,
                      dest='fdb_file',
                      required=True,
                      help='Analyze this find db file.')
  parser.add_argument('-p',
                      '--pdb_file',
                      type=str,
                      dest='pdb_file',
                      required=True,
                      help='Compare with this perf db file.')
  parser.add_argument('-o',
                      '--out_file',
                      type=str,
                      default='scan_results.txt',
                      dest='out_file',
                      help='Compare with this perf db file.')

  args = parser.parse_args()

  return args


def compare(fdb_file, pdb_file, outfile):
  cnx_pdb = sqlite3.connect(pdb_file)
  perf_rows, perf_cols = get_sqlite_table(cnx_pdb, 'perf_db', include_id=True)
  cfg_rows, cfg_cols = get_sqlite_table(cnx_pdb, 'config', include_id=True)

  perf_db = {}
  for row in perf_rows:
    perf_entry = dict(zip(perf_cols, row))
    perf_db[perf_entry['id']] = perf_entry

  cfg_db = {}
  for row in cfg_rows:
    cfg_entry = dict(zip(cfg_cols, row))
    cfg_db[cfg_entry['id']] = cfg_entry

  cfg_group = {}
  for item in perf_db:
    cfg_id = item['config']

    sqlite_cfg = valid_cfg_dims(cfg_db[cfg_id])
    driver = get_cfg_driver(sqlite_cfg)
    cfg_drv = tuple(sorted(driver.vars()))

    cfg_entry = cfg_group[cfg_drv]
    cfg_entry['config'] = cfg_db[cfg_id]
    cfg_entry['pdb'][item['solver']] = item

  line_count = 0
  find_db = {}
  with open(fdb_file) as fdb_fp:
    for line in fdb_fp:
      line_count += 1
      driver = DriverConvolution(line)
      cfg_drv = tuple(sorted(driver.vars()))
      assert(cfg_drv not in find_db)
      find_db[cfg_drv]['fdb'] = parse_fdb_line(line)
      find_db[cfg_drv]['line#'] = line_count


  err_list = []
  for cfg_drv, fdb_obj in find_db.items():
    if cfg_drv not in cfg_group:
      err = {'line': fdb_obj['line#'],
             'msg': f"No pdb entries for key: {fdb_obj['fdb'].key()}"
             }
      err_list.append(err)
      LOGGER.error('%s', err['err'])
      continue
    pdb_group = cfg_group[cfg_drv]['pdb']
    for fdb_key, alg_list in fdb_obj['fdb'].items():
      for alg in alg_list:
        alg_nm = alg['alg_lib']
        solver_nm = alg['solver']
        if solver_nm not in pdb_group.keys():
          err = {'line': fdb_obj['line#'],
                 'msg': f"No pdb entries for key: {fdb_key}, solver: {alg_nm}:{solver_nm}"
                }
          err_list.append(err)
          LOGGER.error('%s', err['err'])

  with open(outfile, 'w') as out_fp:  # pylint: disable=unspecified-encoding
    for err in err_list:
      out_fp.write(f'fdb {err["line"]}: {err["err"]}\n')


def main():
  """main"""
  args = parse_args()
  compare(args.fdb_file, args.pdb_file, args.out_file)


if __name__ == '__main__':
  main()
