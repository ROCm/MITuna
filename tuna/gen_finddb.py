import os
import argparse
import pandas as pd
from enum import Enum
from sqlalchemy import and_

from tuna.utils import logging
import tuna.utils.tools.io as io_tools
import tuna.utils.tools.df as df_tools
from tuna.utils.helpers import pretty_list
from tuna.dbBase.sql_alchemy import DbSession
from tuna.find_db import FindDB, ConvolutionFindDB


_DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'findDB_')

_FINDDB_TABLE = { '0.1.0': FindDB,                      # Deprecated
                  '1.0.0': ConvolutionFindDB }

def load_findDB(findDB_pickle_filename, tag=''):
  findDB = io_tools.safe_load(None, findDB_pickle_filename, df_tools.from_pickle)
  describe_findDB(findDB, tag)
  return findDB


def describe_findDB(findDB, tag=''):
  if len(findDB) == 0:
    logging.warning(f'FindDB empty!')
  else:
    logging.info(f'{tag}FindDB corresponds to session IDs: %s' % pretty_list(findDB['session'].unique()))
    logging.info(f'Total entries in {tag}FindDB: %d' % len(findDB))
    logging.info(f'Total unique solvers in {tag}FindDB: %d' % len(findDB['solver'].unique()))


def gen_findDB(session_ids=None, valid=None, opencl=None, tuna_v='1.0.0'):
  if tuna_v not in _FINDDB_TABLE:
    raise ValueError(f'invalid tuna_v: only tuna versions {_FINDDB_TABLE.keys()} supported')

  findDB = _FINDDB_TABLE[tuna_v]
  logging.info(f'tuna version: {tuna_v}')
  logging.info(f'tuna database name: {os.environ["TUNA_DB_NAME"]}')
  logging.info(f'findDB table name: {findDB.__tablename__}')

  with DbSession() as session:
    logging.log(f'quering {findDB.__tablename__}...', end_char='\r')
    query = session.query(findDB)
    query = query.filter(and_(findDB.kernel_time != -1, 
                 findDB.workspace_sz != -1))
    if session_ids is not None:
      for session_id in session_ids:
        query = query.filter(findDB.session == session_id)
    if valid is not None:
      query = query.filter(findDB.valid == valid)
    if opencl is not None:
      query = query.filter(findDB.opencl == opencl)

    query = query.order_by(
        findDB.update_ts.desc(), 
        findDB.config ) 

    logging.reset_line()
    logging.success('query processed!')

    logging.log('reading query into a dataframe...', end_char='\r')
    df = pd.read_sql(query.statement, session.bind)
    logging.reset_line()

    describe_findDB(df)

    return df


class FindDBParsing:
  SIGNATURE = '__hasFindDBArgs__'

  class ARGNAMES(Enum):
    SESSION_IDS = 'session_ids'
    VALID = 'valid'
    OPENCL = 'opencl'
    TUNA_V = 'tuna_v'

  @classmethod
  def set_findDB_args(cls, parser):
    # SESSION_IDS
    parser.add_argument(f'--{FindDBParsing.ARGNAMES.SESSION_IDS.value}', 
        type=int, nargs='*', default=None, dest=FindDBParsing.ARGNAMES.SESSION_IDS.value,
        help='IDs of tuning sessions to fetch findDB for (default: all tuning sessions)')
    # VALID
    parser.add_argument(f'--{FindDBParsing.ARGNAMES.VALID.value}', 
        action='store_true', default=True, dest=FindDBParsing.ARGNAMES.VALID.value,
        help='only dump valid kernels (default: True)')
    # OPENCL
    parser.add_argument(f'--{FindDBParsing.ARGNAMES.OPENCL.value}', 
        action='store_true', default=False, dest=FindDBParsing.ARGNAMES.OPENCL.value,
        help='use OpenCL extension (default: False)')
    # TUNA_V
    parser.add_argument(f'--{FindDBParsing.ARGNAMES.TUNA_V.value}', 
        type=str, default='1.0.0', dest=FindDBParsing.ARGNAMES.TUNA_V.value,
        help='tuna version (default: 1.0.0)',
        choices=_FINDDB_TABLE.keys())

    # sign the parser
    setattr(parser, FindDBParsing.SIGNATURE, True)

  @classmethod
  def get_findDB_args(cls, args):
    return {argname.value: getattr(args, argname.value) for argname in FindDBParsing.ARGNAMES}


if __name__ == '__main__':
  default_out_dirname = _DEFAULT_OUTPUT_DIR

  parser = argparse.ArgumentParser(description='Fetches FindDB and exports it as a Pandas DataFrame')
  parser.add_argument('-o', '--out', type=str, default=default_out_dirname,
    help=f'directory for the output pickled Pandas Dataframe (current: {default_out_dirname})')
  FindDBParsing.set_findDB_args(parser)

  args = parser.parse_args()

  findDB = gen_findDB( **FindDBParsing.get_findDB_args(args) )

  io_tools.safe_save(findDB, os.path.join(args.out, 'findDB.pkl'), df_tools.to_pickle)
  logging.dump_logs(os.path.join(args.out, 'gen_finddb.log'))
