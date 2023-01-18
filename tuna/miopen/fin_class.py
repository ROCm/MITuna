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
"""Module to handle Fin work"""

import json
import os
import tempfile
import functools
import random
import types
from time import sleep
import paramiko
try:
  import queue
except ImportError:
  import Queue as queue
from sqlalchemy import func as sqlalchemy_func
from sqlalchemy.exc import IntegrityError, InvalidRequestError  #pylint: disable=wrong-import-order
from sqlalchemy.inspection import inspect

from tuna.worker_interface import WorkerInterface
from tuna.dbBase.sql_alchemy import DbSession
from tuna.metadata import FIN_CACHE
from tuna.metadata import INVERS_DIR_MAP
from tuna.miopen.tables import MIOpenDBTables
from tuna.miopen.fin_utils import compose_config_obj
from tuna.miopen.fin_utils import get_fin_slv_status
from tuna.config_type import ConfigType
from tuna.utils.db_utility import session_retry
from tuna.utils.db_utility import get_solver_ids, get_id_solvers
from tuna.utils.utility import split_packets
from tuna.utils.db_utility import gen_select_objs, gen_insert_query, gen_update_query
from tuna.utils.db_utility import get_class_by_tablename, has_attr_set

MAX_JOB_RETRIES = 10


class FinClass(WorkerInterface):
  """Class to provide Tuna support for Fin"""

  # pylint: disable=too-many-instance-attributes
  # pylint: disable=too-many-public-methods

  def __init__(self, **kwargs):
    """Constructor"""
    allowed_keys = set(
        ['fin_steps', 'local_file', 'fin_infile', 'fin_outfile', 'config_type'])
    self.__dict__.update((key, None) for key in allowed_keys)

    self.supported_fin_steps = ["get_solvers", "applicability"]
    self.fin_steps = []
    _, self.local_file = tempfile.mkstemp()
    self.fin_infile = self.local_file.split("/tmp/", 1)[1] + ".json"
    _, self.local_output = tempfile.mkstemp()
    self.fin_outfile = self.local_output.split("/tmp/", 1)[1] + ".json"

    self.solver_id_map = get_solver_ids()
    _, self.id_solver_map = get_id_solvers(
    )  #hyphenated names used by miopen::solver.ToString()
    self.all_configs = []
    self.fin_list = []
    self.multiproc = False
    self.pending = []
    self.first_pass = True

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.config_type = ConfigType.convolution if self.config_type is None else self.config_type

    #call to set_db_tables in super must come after config_type is set
    super().__init__(**kwargs)

    self.config = types.SimpleNamespace()
    self.cfg_attr = [column.name for column in inspect(self.dbt.config_table).c]

    # dict of relationship_column : dict{local_key, foreign_table_name, foreign_key, [remote_attr]}
    self.cfg_rel = {
        key: {
            'key': list(val.local_columns)[0].name,
            'ftble': str(list(val.remote_side)[0]).split('.', maxsplit=1)[0],
            'fkey': str(list(val.remote_side)[0]).split('.')[1]
        } for key, val in inspect(self.dbt.config_table).relationships.items()
    }
    for key, val in self.cfg_rel.items():
      rel_attr = [
          column.name
          for column in inspect(get_class_by_tablename(val['ftble'])).c
      ]
      val['fattr'] = rel_attr

    self.fdb_attr = [
        column.name for column in inspect(self.dbt.find_db_table).c
    ]
    self.fdb_attr.remove("insert_ts")
    self.fdb_attr.remove("update_ts")

  def chk_abort_file(self):
    """Checking presence of abort file to terminate processes immediately"""
    abort_reason = []
    if os.path.exists(f'/tmp/miopen_abort_{self.machine.arch}'):
      abort_reason.append(self.machine.arch)

    if os.path.exists(f'/tmp/miopen_abort_mid_{self.machine.id}'):
      abort_reason.append('mid_' + str(self.machine.id))
    if abort_reason:
      for reason in abort_reason:
        self.logger.warning('/tmp/mipen_abort_%s file found, returning', reason)
      return True

    return False

  def set_db_tables(self):
    """Initialize tables"""
    self.dbt = MIOpenDBTables(session_id=self.session_id,
                              config_type=self.config_type)

  def compose_work_objs(self, session, conds):
    """query for fin command and config"""
    ret = []
    if self.fin_steps:
      conds.append(f"fin_step like '%{self.fin_steps[0]}%'")
    else:
      conds.append("fin_step='not_fin'")

    job_entries = super().compose_work_objs(session, conds)

    if job_entries:
      id_str = ','.join([str(job.config) for job in job_entries])
      cfg_cond_str = f"where valid=1 and id in ({id_str})"
      cfg_entries = gen_select_objs(session, self.cfg_attr,
                                    self.dbt.config_table.__tablename__,
                                    cfg_cond_str)

      #attach tensor relationship information to config entries
      for cfg in cfg_entries:
        for key, val in self.cfg_rel.items():
          rel_val = getattr(cfg, val['key'])
          rel_cond_str = f"where {val['fkey']}={rel_val}"
          setattr(
              cfg, key,
              gen_select_objs(session, val['fattr'], val['ftble'],
                              rel_cond_str)[0])

      cfg_map = {cfg.id: cfg for cfg in cfg_entries}

      for job in job_entries:
        ret.append([job, cfg_map[job.config]])

    return ret

  #pylint: disable=R0801
  def check_jobs_found(self, job_rows, find_state, imply_end):
    """check for end of jobs"""
    if not job_rows:
      # we are done
      self.logger.warning('No %s jobs found, fin_step: %s, session %s',
                          find_state, self.fin_steps, self.session_id)
      if imply_end:
        self.logger.warning("set end")
        self.end_jobs.value = 1
      return False
    return True

  #pylint: enable=R0801

  def job_queue_pop(self):
    """load job & config from top of job queue"""
    self.job, self.config = self.job_queue.get(True, 1)
    self.logger.info("Got job %s %s %s", self.job.id, self.job.state,
                     self.job.reason)

  def __compose_fincmd(self):
    """Helper function to compose fin docker cmd"""
    if self.machine.local_machine:
      # Skip the copy and use the /tmp/* version of the files
      fin_ifile = self.local_file
      fin_ofile = self.local_output
    else:
      fin_ifile = FIN_CACHE + "/" + self.fin_infile
      #Currently not used, but will be used in the future
      #machine_cfg = get_qts_machine_data(self.machine.id, self.machine.hostname,
      #                                   self.logger)
      try:
        self.logger.info("Fin: copying local fin input_file: %s to remote %s",
                         self.local_file, fin_ifile)
        # TODO: remove redundant file copies  # pylint: disable=fixme
        self.cnx.ssh.open_sftp().put(self.local_file, fin_ifile)
        self.logger.info("Fin: Successfully copied to remote")
      except paramiko.ssh_exception.SSHException:
        self.logger.warning('unable to connect to remote %s', fin_ifile)
      except IOError:
        self.logger.warning('unable to receive file: %s skipping ... ',
                            fin_ifile)

      fin_ofile = FIN_CACHE + "/" + self.fin_outfile
    bash_cmd = f"/opt/rocm/bin/fin -i {fin_ifile} -o {fin_ofile}"
    self.logger.info('Executing fin cmd: %s', bash_cmd)
    return bash_cmd

  def get_solvers(self):
    """Getting solvers from MIOpen to update Tuna DB"""
    self.fin_steps = ['get_solvers']
    solvers = self.__get_fin_results()
    if solvers is None:
      return False
    if 'all_solvers' not in solvers[1]:
      self.logger.error('all_solvers key not found in fin output')
    self.__parse_solvers(solvers[1]['all_solvers'])

    return True

  def __get_fin_results(self):
    """Helper function to launch fin docker cmd, cat output of the cmd and parse the json"""
    # pylint: disable=broad-except
    result = None

    if self.__prep_fin_input(self.local_file, to_file=True):
      fin_cmd = self.__compose_fincmd()
      ret_code, out, err = self.exec_docker_cmd(fin_cmd)
      if ret_code > 0:
        self.logger.warning('Err executing cmd: %s', fin_cmd)
        self.logger.warning(out)
        raise Exception(
            f'Failed to execute fin cmd: {fin_cmd} err: {err.read()}')

      result = self.__parse_out()

    return result

  def __parse_out(self):
    """Parse fin output helper function"""
    # pylint: disable=broad-except
    result = None
    if not self.machine.local_machine:
      fin_outfile = FIN_CACHE + "/" + self.fin_outfile
      # TODO: This should be copied back out using cat is bad # pylint: disable=fixme
      _, ssh_stdout, _ = self.exec_command(f"cat {fin_outfile}")
      result_json = []

      for line in ssh_stdout:
        result_json.append(line)
      try:
        result = json.loads('\n'.join(result_json))
      except Exception as err:
        self.logger.warning('Err loading fin json: %s', err)
        return None
    else:
      with open(self.local_output) as out_file:  # pylint: disable=unspecified-encoding
        try:
          result = json.load(out_file)
        except Exception as err:
          self.logger.error('Unable to load fin json file %s', err)
          for line in out_file:
            self.logger.error(line)
          return None

    return result

  def applicability(self):
    """Getting applicability from MIOpen to update Tuna DB"""
    self.fin_steps = ['applicability']
    applic_res = self.__get_fin_results()
    if applic_res is None:
      return False

    self.__parse_applicability(applic_res)

    return True

  def __set_all_configs(self, idx=0, num_blk=1):
    """Gathering all configs from Tuna DB to set up fin input file"""
    if idx == 0:
      with DbSession() as session:
        query = session.query(self.dbt.config_table)\
                          .filter(self.dbt.config_table.valid == 1)

        if self.label:
          query = query.filter(self.dbt.config_table.id == self.dbt.config_tags_table.config)\
              .filter(self.dbt.config_tags_table.tag == self.label)

        #order by id for splitting configs into blocks
        query = query.order_by(self.dbt.config_table.id)
        rows = query.all()

        master_cfg_list = []
        for row in rows:
          r_dict = compose_config_obj(row, self.config_type)
          if self.config_type == ConfigType.batch_norm:
            r_dict['direction'] = row.get_direction()
          master_cfg_list.append(r_dict)

        block_size = len(rows) // num_blk  #size of the config block
        extra = len(rows) % num_blk  #leftover configs, don't divide evenly
        self.logger.info(
            "cfg workdiv: num_blocks: %s, block_size: %s, extra: %s", num_blk,
            block_size, extra)
        for i in range(num_blk):
          start = i * block_size  #start of a process block
          end = (i + 1) * block_size
          #distributing leftover configs to processes
          if i < extra:
            start += i
            end += 1 + i
          else:
            start += extra
            end += extra

          if start >= len(rows):
            break

          self.logger.info("cfg workdiv: start %s, end %s", start, end)

          self.job_queue.put(master_cfg_list[start:end])
    try:
      self.all_configs = self.job_queue.get(True, 30)
    except queue.Empty:
      self.logger.warning('No jobs found for process %s...', idx)
      self.all_configs = []

    if not self.all_configs:
      return False

    return True

  def __create_dumplist(self):
    """Creating json dump to be used as fin input file"""
    self.fin_list = []
    if len(self.fin_steps) == 1 and self.fin_steps == ["get_solvers"]:
      self.fin_list = [{"steps": self.fin_steps}]
      self.logger.info("Creating dumplist for: %s", self.fin_steps[0])
      return True

    if "applicability" in self.fin_steps:
      self.logger.info("Creating dumplist for: %s", self.fin_steps[0])
      idx = 0
      num_blk = 1
      if self.multiproc:
        idx = self.gpu_id
        num_blk = self.num_procs.value

      if not self.__set_all_configs(idx, num_blk):
        return False
      return self.__compose_fin_list()

    self.logger.error("Fin steps not recognized: %s", self.fin_steps)
    self.logger.info("Fin steps recognized are: %s", self.supported_fin_steps)
    return False

  def __compose_fin_list(self):
    """Helper function to set fin_list for dump"""

    arch = self.dbt.session.arch
    ncu = self.dbt.session.num_cu
    for cfg in self.all_configs:
      self.fin_list.append({
          "steps": self.fin_steps,
          "arch": arch,
          "num_cu": ncu,
          "config_tuna_id": cfg["id"],
          "config": cfg,
          "direction": int(INVERS_DIR_MAP[cfg["direction"]])
      })
    return True

  def __dump_json(self, outfile, to_file=True):
    """Dumping json to outfile"""
    if to_file is True:
      if not os.path.exists(outfile):
        os.mknod(outfile)
      with open(outfile, 'w') as fout:  # pylint: disable=unspecified-encoding
        fout.write("[\n")
        i = 0
        while i < len(self.fin_list):
          json_out = json.dumps(self.fin_list[i])
          fout.write(json_out)
          if i != len(self.fin_list) - 1:
            fout.write(',\n')
          i += 1

        fout.write("\n]")
      self.logger.info('Fin input file written to %s', outfile)
    else:
      jdump = json.dumps(self.fin_list)
      return jdump

    return True

  def __prep_fin_input(self, outfile=None, to_file=True):
    """Main function in Fin that produces Fin input file"""

    self.cnx = self.machine.connect(self.chk_abort_file())
    ret = False
    if outfile is None:
      outfile = "fin_input.json"
    if self.__create_dumplist():
      ret = self.__dump_json(outfile, to_file)
    else:
      self.logger.warning("Could not create dumplist for Fin input file")

    return ret

  def __insert_applicability(self, session, json_in):
    """write applicability to sql"""
    inserts = []
    for elem in json_in:
      if "applicable_solvers" in elem.keys():
        cfg_id = elem["input"]["config_tuna_id"]
        # pylint: disable=comparison-with-callable
        app_query = session.query(self.dbt.solver_app)\
          .filter(self.dbt.solver_app.session == self.session_id)\
          .filter(self.dbt.solver_app.config == cfg_id)
        # pylint: enable=comparison-with-callable

        if not elem["applicable_solvers"]:
          self.logger.warning("No applicable solvers for %s", cfg_id)

        app_slv_ids = []
        for solver in elem["applicable_solvers"]:
          try:
            solver_id = self.solver_id_map[solver]
            app_slv_ids.append(solver_id)
          except KeyError:
            self.logger.warning('Solver %s not found in solver table', solver)
            self.logger.info("Please run 'go_fish.py --update_solver' first")
            return False

        #remove old applicability
        not_app_query = app_query.filter(
            self.dbt.solver_app.solver.notin_(app_slv_ids))
        not_app_query.update({self.dbt.solver_app.applicable: 0},
                             synchronize_session='fetch')

        for solver_id in app_slv_ids:
          obj = app_query.filter(
              self.dbt.solver_app.solver == solver_id).first()  # pylint: disable=W0143
          if obj:
            obj.applicable = 1
          else:
            inserts.append((cfg_id, solver_id))

    #commit updates
    session.commit()

    #bulk inserts
    with self.job_queue_lock:
      self.logger.info('Commit bulk inserts, please wait')
      for cfg_id, solver_id in inserts:
        new_entry = self.dbt.solver_app(solver=solver_id,
                                        config=cfg_id,
                                        session=self.session_id,
                                        applicable=1)
        session.add(new_entry)
      session.commit()

    return True

  def __parse_applicability(self, json_in):
    """Function to parse fin outputfile and populate DB with results"""
    self.logger.info('Parsing fin solver applicability output...')
    if json_in is None:
      self.logger.error("JSON file returned from Fin is empty")
      return False

    all_packs = split_packets(json_in, 10000)

    with DbSession() as session:

      def actuator(func, pack):
        return func(session, pack)

      for pack in all_packs:
        session_retry(session, self.__insert_applicability,
                      functools.partial(actuator, pack=pack), self.logger)

      query = session.query(sqlalchemy_func.count(self.dbt.solver_app.id))
      query = query.filter(self.dbt.solver_app.session == self.session_id)  # pylint: disable=W0143
      sapp_count = query.one()[0]
      self.logger.warning(
          "Finished parsing solver applicability, new session size: %d entries",
          sapp_count)
    return True

  def __invalidate_solvers(self, sids, max_id):
    """Helper function to invalidate solver in DB that are not present in Fin outputfile"""
    solver_ids_invalid = []
    with DbSession() as session:
      i = 1
      try:
        while i <= max_id:
          #if solver has been removed
          if i not in sids:
            solver_ids_invalid.append(i)
            session.query(self.dbt.solver_table).filter(
                self.dbt.solver_table.id == i).update(
                    {self.dbt.solver_table.valid: 0})
            session.commit()
          i += 1
      except IntegrityError as err:
        self.logger.warning("DB err occurred %s", err)

    return solver_ids_invalid

  def __add_new_solvers(self, solvers):
    """Add new solvers to db and return the key for latest solver"""

    max_id = 1
    sids = []
    with DbSession() as session:
      for slv_map in solvers:
        idx = int(slv_map['id'])
        solver = slv_map['name']
        tunable = int(slv_map['tunable'])
        config_type = slv_map['type']
        try:
          sids.append(idx)
          if idx > max_id:
            max_id = idx

          new_s = self.dbt.solver_table(id=idx,
                                        solver=solver,
                                        valid=1,
                                        tunable=tunable,
                                        config_type=config_type,
                                        is_dynamic=slv_map['dynamic'])
          session.add(new_s)
          session.commit()
        except IntegrityError:
          self.logger.info(
              "Duplicate entry, updating solver %s: valid=1, tunable=%s",
              solver, tunable)
          session.rollback()
          session.query(self.dbt.solver_table).filter(
              self.dbt.solver_table.id == idx).update({
                  self.dbt.solver_table.valid: 1,
                  self.dbt.solver_table.solver: solver,
                  self.dbt.solver_table.tunable: tunable
              })
          session.commit()
        except InvalidRequestError as err2:
          self.logger.info("DB err occurred: %s", err2)

    return max_id, sids

  def __parse_solvers(self, solvers):
    """Function to parse solvers from fin output file"""
    # TODO: Refactor such that we query all the solvers # pylint: disable=fixme
    # from the db once then only insert/invalidate the new/invalid one
    max_id, sids = self.__add_new_solvers(solvers)

    solver_ids_invalid = []
    if len(sids) != max_id:
      solver_ids_invalid = self.__invalidate_solvers(sids, max_id)
      self.logger.info("invalid solvers: %s", solver_ids_invalid)

    s_count = 0
    with DbSession() as session:
      query = session.query(sqlalchemy_func.count(self.dbt.solver_table.id))
      s_count = query.one()[0]

    if max_id != s_count:
      #Note: we canot update invalid solvers missing from DB bc MIOpen does not report these
      self.logger.info(
          "Solver table missing some invalid solvers, please check MIOpens solver.cpp \
          file for solvers that have been invalidated and are missing from your DB"
      )
      self.logger.info("Current invalid solvers: %s", solver_ids_invalid)

    return True

  def get_fdb_entry(self, session, solver):
    """ Get FindDb entry from db """
    obj = None
    fdb_entry = None

    conds = [
        f"session={self.dbt.session.id}", f"config={self.config.id}",
        f"solver={solver}", "opencl=0"
    ]
    cond_str = f"where {' AND '.join(conds)}"
    entries = gen_select_objs(session, self.fdb_attr,
                              self.dbt.find_db_table.__tablename__, cond_str)

    if entries:
      assert len(entries) == 1
      obj = entries[0]
    else:
      fdb_entry = types.SimpleNamespace()
      for attr in self.fdb_attr:
        setattr(fdb_entry, attr, None)
      setattr(fdb_entry, 'session', self.dbt.session.id)
      setattr(fdb_entry, 'config', self.config.id)
      setattr(fdb_entry, 'solver', solver)
      setattr(fdb_entry, 'opencl', False)
      setattr(fdb_entry, 'logger', self.logger)

    return obj, fdb_entry

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

    fdb_entry.kernel_group = self.job.id

    return fdb_entry

  def __compose_kernel_entry(self, session, fdb_obj, fdb_entry):
    """Compose a new Kernel Cache entry from fin input"""
    # Now we have the ID, lets add the binary cache objects
    for kern_obj in fdb_obj['kernel_objects']:
      kernel_obj = self.dbt.kernel_cache()
      self.populate_kernels(kern_obj, kernel_obj)
      kernel_obj.kernel_group = fdb_entry.kernel_group
      session.add(kernel_obj)
    return True

  def populate_kernels(self, kern_obj, kernel_obj):
    """populate kernel object"""
    kernel_obj.kernel_name = kern_obj['kernel_file']
    kernel_obj.kernel_args = kern_obj['comp_options']
    kernel_obj.kernel_blob = bytes(kern_obj['blob'], 'utf-8')
    kernel_obj.kernel_hash = kern_obj['md5_sum']
    kernel_obj.uncompressed_size = kern_obj['uncompressed_size']
    return kernel_obj

  def __update_fdb_w_kernels(self,
                             session,
                             fin_json,
                             result_str='miopen_find_compile_result',
                             check_str='find_compiled'):
    """update find db + kernels from json results"""
    status = []
    if fin_json[result_str]:
      for fdb_obj in fin_json[result_str]:
        slv_stat = get_fin_slv_status(fdb_obj, check_str)
        status.append(slv_stat)

        if fdb_obj[check_str]:
          #returned entry is added to the table
          fdb_entry = self.__compose_fdb_entry(session, fin_json, fdb_obj)
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

  def __add_sql_objs(self, session, obj_list):
    """add sql objects to the table"""
    for obj in obj_list:
      if isinstance(obj, types.SimpleNamespace):
        if has_attr_set(obj, self.fdb_attr):
          query = gen_insert_query(obj, self.fdb_attr,
                                   self.dbt.find_db_table.__tablename__)
          session.execute(query)
        else:
          return False
      else:
        session.add(obj)
    session.commit()
    return True

  def __result_queue_commit(self, session, close_job):
    """commit the result queue and set mark job complete"""
    while not self.result_queue.empty():
      obj_list = []
      res_list = self.result_queue.get(True, 1)
      res_job = res_list[0][0]
      for _, obj in res_list:
        obj_list.append(obj)

      self.logger.info("commit pending job %s, #objects: %s", res_job.id,
                       len(obj_list))
      status = session_retry(session, self.__add_sql_objs,
                             lambda x: x(session, obj_list), self.logger)
      if not status:
        self.logger.error("Failed commit pending job %s", res_job.id)
        return False

      this_job = self.job

      #set job states after successful commit
      self.job = res_job
      close_job()

      self.job = this_job

    return True

  def close_job(self):
    """mark a job complete"""

  def result_queue_drain(self):
    """check for lock and commit the result queue"""
    if self.result_queue_lock.acquire(block=False):
      with DbSession() as session:
        self.__result_queue_commit(session, self.close_job)
      self.result_queue_lock.release()
      return True
    return False

  def reset_job_state(self):
    """finish committing result queue"""
    super().reset_job_state()
    self.result_queue_drain()

  def init_check_env(self):
    """check environment on the first run"""
    if self.first_pass:
      self.first_pass = False
      try:
        self.check_env()
      except ValueError as verr:
        self.logger.error(verr)
        return False
    return True

  def run_fin_cmd(self):
    """Run a fin command after generating the JSON"""
    fin_output = self.machine.make_temp_file()
    cmd = []

    env_str = " ".join(self.envmt)
    cmd.append(env_str)
    cmd.extend(
        ['/opt/rocm/bin/fin', '-i',
         self.get_fin_input(), '-o', fin_output])  # pylint: disable=no-member

    for i in range(MAX_JOB_RETRIES):
      ret_code, _, err = self.exec_docker_cmd(cmd)

      if ret_code != 0:
        self.logger.error('Error executing command: %s', ' '.join(cmd))
        if err:
          err_str = err.read()
          self.logger.error('%s : %s', ret_code, err_str)
          if "disk I/O error" in err_str:
            self.logger.error('fin retry : %u', i)
            sleep(random.randint(1, 10))
          else:
            break
        else:
          self.logger.error('err code : %s', ret_code)
          break
      else:
        break

    if ret_code != 0:
      return None

    # load the output json file and strip the env
    fin_json = json.loads(self.machine.read_file(fin_output))[1:]
    assert len(fin_json) == 1
    # JD: if we implement multiple jobs per fin launch, this would be a loop
    fin_json = fin_json[0]
    return fin_json

  def step(self):
    """Inner loop for Process run defined in worker_interface"""
    self.multiproc = True
    if "applicability" in self.fin_steps:
      self.applicability()

    self.multiproc = False
    return False
