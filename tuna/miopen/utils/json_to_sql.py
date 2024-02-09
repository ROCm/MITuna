#!/usr/bin/env python3
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
"""Utility module for helper functions"""

LOGGER = setup_logger('parse_results')


def __update_fdb_w_kernels(self,
                           session: DbSession,
                           fin_json: dict,
                           result_str: str = 'miopen_find_compile_result',
                           check_str: str = 'find_compiled') -> list:
  """update find db + kernels from json results"""
  status = []
  if fin_json[result_str]:
    for fdb_obj in fin_json[result_str]:
      slv_stat = get_fin_slv_status(fdb_obj, check_str)
      status.append(slv_stat)

      if fdb_obj[check_str]:
        #returned entry is added to the table
        fdb_entry = self.__compose_fdb_entry(session, fin_json, fdb_obj)
        self.__check_layout_mismatch(fdb_entry, slv_stat)
        if not self.pending:
          query = gen_update_query(fdb_entry, self.fdb_attr,
                                   self.dbt.find_db_table.__tablename__)
          session.execute(query)
        else:
          assert len(self.pending) == 1
          self.pending.pop()
          query = gen_insert_query(fdb_entry, self.fdb_attr,
                                   self.dbt.find_db_table.__tablename__)
          session.execute(query)

          fdb_entry = self.__update_fdb_entry(
              session, self.solver_id_map[fdb_obj['solver_name']])
          fdb_entry.kernel_group = fdb_entry.id
          query = gen_update_query(fdb_entry, ['kernel_group'],
                                   self.dbt.find_db_table.__tablename__)
          session.execute(query)

        if fdb_obj['reason'] == 'Success':
          self.__compose_kernel_entry(session, fdb_obj, fdb_entry)
          self.logger.info('Updating find Db(Build) for job_id=%s',
                           self.job.id)
        else:
          # JD: add info about reason to the logs table
          fdb_entry.valid = False
      else:
        self.logger.warning("Failed find_db compile, cfg_id: %s, obj: %s",
                            fin_json['config_tuna_id'], fdb_obj)
  else:
    status = [{
        'solver': 'all',
        'success': False,
        'result': 'Find Compile: No results'
    }]

  session.commit()

  return status

def populate_kernels(kern_obj, kernel_obj):
  """populate kernel object"""
  kernel_obj.kernel_name = kern_obj['kernel_file']
  kernel_obj.kernel_args = kern_obj['comp_options']
  kernel_obj.kernel_blob = bytes(kern_obj['blob'], 'utf-8')
  kernel_obj.kernel_hash = kern_obj['md5_sum']
  kernel_obj.uncompressed_size = kern_obj['uncompressed_size']
  return kernel_obj

def __check_layout_mismatch(self, fdb_entry: SimpleDict,
                            status: dict) -> bool:
  """Check that the fdb key returned by fin matches the config being tuned,
  states to error if not"""
  fdb_key = fdb_entry.fdb_key
  fds, vals, _, _ = parse_pdb_key(fdb_key)
  key_layout = vals[fds.index('out_layout')]
  cfg_layout = self.config.out_layout

  if cfg_layout != key_layout:
    status['success'] = False
    status['result'] = f"fdb_key layout mismatch with config"\
                       f" {key_layout} != {cfg_layout}"
    fdb_entry.valid = False
    return False

  return True

def __compose_kernel_entry(self, session, fdb_obj, fdb_entry):
  """Compose a new Kernel Cache entry from fin input"""
  # Now we have the ID, lets add the binary cache objects
  for kern_obj in fdb_obj['kernel_objects']:
    kernel_obj = self.dbt.kernel_cache()
    self.populate_kernels(kern_obj, kernel_obj)
    kernel_obj.kernel_group = fdb_entry.kernel_group
    session.add(kernel_obj)
  return True

def __update_fdb_entry(self, session, solver):
  """ Add a new entry to fdb if there isnt one already """
  obj, fdb_entry = self.get_fdb_entry(session, solver)
  if obj:  # existing entry in db
    # This can be removed if we implement the delete orphan cascade
    fdb_entry = obj
    session.query(
        self.dbt.kernel_cache).filter(self.dbt.kernel_cache.kernel_group ==
                                      fdb_entry.kernel_group).delete()
  else:
    # Bundle Insert for later
    self.pending.append((self.job, fdb_entry))
  return fdb_entry

def __compose_fdb_entry(self, session, fin_json, fdb_obj):
  """Compose a FindDB table entry from fin_output"""
  solver = self.solver_id_map[fdb_obj['solver_name']]
  fdb_entry = self.__update_fdb_entry(session, solver)
  fdb_entry.fdb_key = fin_json['db_key']
  fdb_entry.alg_lib = fdb_obj['algorithm']
  fdb_entry.params = fdb_obj['params']
  fdb_entry.workspace_sz = fdb_obj['workspace']
  fdb_entry.valid = True

  fdb_entry.kernel_time = -1
  if 'time' in fdb_obj:
    fdb_entry.kernel_time = fdb_obj['time']

  fdb_entry.kernel_group = fdb_entry.id

  return fdb_entry

def process_fdb_w_kernels(self,
                          session,
                          fin_json,
                          result_str='miopen_find_compile_result',
                          check_str='find_compiled'):
  """initiate find db update"""

  callback = self.__update_fdb_w_kernels
  status = session_retry(
      session, callback,
      lambda x: x(session, fin_json, result_str, check_str), self.logger)

  if not status:
    self.logger.warning('Fin: Unable to update Database')
    status = [{
        'solver': 'all',
        'success': False,
        'result': 'Fin: Unable to update Database'
    }]

  return status
