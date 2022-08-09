""" findDB_like objects are findDB, explodedFindDB, fastDB, explodedFastDB """

from tuna.utils.db_utility import get_id_solvers
from tuna.utils.helpers import sort_dict, invert_dict


_, _ID_TO_SOLVER = get_id_solvers()
_SOLVER_TO_ID = invert_dict(_ID_TO_SOLVER)


def get_solver_counts(findDB_like, use_id=False):
  """ returns a dictionary that maps a given solver name to the 
  number of times it occurs in FindDB-like Database """
  solver_counts = findDB_like['solver'].value_counts()
  solver_counts_dict = {}
  for solver_id, count in solver_counts.iteritems():
    if use_id:
      solver_counts_dict[ solver_id ] = count
    else:
      solver_counts_dict[ _ID_TO_SOLVER[solver_id] ] = count
  return sort_dict(solver_counts_dict)
