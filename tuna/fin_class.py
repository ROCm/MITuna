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
import paramiko
from sqlalchemy import func as sqlalchemy_func
from sqlalchemy.exc import IntegrityError, InvalidRequestError  #pylint: disable=wrong-import-order

from tuna.db_tables import connect_db
from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger
from tuna.metadata import get_solver_ids, FIN_CACHE
from tuna.metadata import DOCKER_CMD, LOG_TIMEOUT, INVERS_DIR_MAP
from tuna.fin_utils import compose_config_obj
from tuna.tables import DBTables
from tuna.config_type import ConfigType


class FinClass():
  """Class to provide Tuna support for Fin"""

  # pylint: disable=too-many-instance-attributes

  def __init__(self, **kwargs):
    """Constructor"""
    # super().__init__(**kwargs)
    allowed_keys = set([
        'fin_steps', 'arch_num_cu_list', 'local_file', 'fin_outfile',
        'fin_infile', 'machine', 'docker_name', 'version', 'config_type',
        'label', 'session_id'
    ])
    self.__dict__.update((key, None) for key in allowed_keys)

    self.logger = setup_logger('fin_class')
    connect_db()
    self.all_configs = []
    self.jobid_to_config = {}
    self.fin_list = []
    self.arch_list = []
    self.supported_fin_steps = ["get_solvers", "applicability"]
    _, self.local_file = tempfile.mkstemp()
    self.fin_infile = self.local_file.split("/tmp/", 1)[1] + ".json"
    _, self.local_output = tempfile.mkstemp()
    self.fin_outfile = self.local_output.split("/tmp/", 1)[1] + ".json"
    self.arch_num_cu_list = None
    self.fin_steps = []
    self.machine = None
    self.docker_name = None
    self.cnx = None
    self.config_type = ConfigType.convolution if self.config_type is None else self.config_type
    self.label = None
    self.session_id = None

    self.__dict__.update(
        (key, value) for key, value in kwargs.items() if key in allowed_keys)

    self.dbt = DBTables(session_id=self.session_id,
                        config_type=self.config_type)

  def chk_abort_file(self):
    """Checking presence of abort file to terminate processes immediately"""
    abort_reason = []
    if os.path.exists('/tmp/miopen_abort_{}'.format(self.machine.arch)):
      abort_reason.append(self.machine.arch)

    if os.path.exists('/tmp/miopen_abort_mid_{}'.format(self.machine.id)):
      abort_reason.append('mid_' + str(self.machine.id))
    if abort_reason:
      for reason in abort_reason:
        self.logger.warning('/tmp/mipen_abort_%s file found, returning', reason)
      return True

    return False

  def exec_command(self, cmd, timeout=LOG_TIMEOUT):
    """Definiting cmd execution process"""
    ins, out, err = self.cnx.exec_command(cmd, timeout, self.chk_abort_file())
    if err is not None and hasattr(err, 'channel'):
      err.channel.settimeout(LOG_TIMEOUT)
    return ins, out, err

  def compose_fincmd(self):
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
    bash_cmd = "/opt/rocm/bin/fin -i {0} -o {1}".format(fin_ifile, fin_ofile)
    self.logger.info('Executing fin cmd: %s', bash_cmd)
    return bash_cmd

  def get_solvers(self):
    """Getting solvers from MIOpen to update Tuna DB"""
    self.fin_steps = ['get_solvers']
    solvers = self.get_fin_results()
    if solvers is None:
      return False
    if 'all_solvers' not in solvers[1]:
      self.logger.error('all_solvers key not found in fin output')
    self.parse_solvers(solvers[1]['all_solvers'])

    return True

  def get_fin_results(self):
    """Helper function to launch fin docker cmd, cat output of the cmd and parse the json"""
    # pylint: disable=broad-except
    result = None

    self.run(self.local_file, to_file=True)
    fin_cmd = self.compose_fincmd()
    if not self.machine.local_machine:
      fin_cmd = DOCKER_CMD.format(self.docker_name, fin_cmd)
    ret_code, out, _ = self.exec_command(fin_cmd)
    if ret_code > 0:
      self.logger.warning('Err executing cmd: %s', fin_cmd)
      self.logger.warning(out.read())

    while True:
      line = out.readline()
      if line == '' and not self.cnx.is_alive():
        break
      if line:
        self.logger.info(line.strip())

    result = self.parse_out()

    return result

  def parse_out(self):
    """Parse fin output helper function"""
    # pylint: disable=broad-except
    result = None
    if not self.machine.local_machine:
      fin_outfile = FIN_CACHE + "/" + self.fin_outfile
      # TODO: This should be copied back out using cat is bad # pylint: disable=fixme
      _, ssh_stdout, _ = self.exec_command("cat {}".format(fin_outfile))
      result_json = []

      for line in ssh_stdout:
        result_json.append(line)
      try:
        result = json.loads('\n'.join(result_json))
      except Exception as err:
        self.logger.warning('Err loading fin json: %s', err)
        return None
    else:
      with open(self.local_output) as out_file:
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
    applic_res = self.get_fin_results()
    if applic_res is None:
      return False

    self.parse_applicability(applic_res)

    return True

  def set_all_configs(self):
    """Gathering all configs from Tuna DB to set up fin input file"""
    with DbSession() as session:
      query = session.query(
          self.dbt.config_table).filter(self.dbt.config_table.valid == 1)

      if self.label:
        query_cfgs = session.query(self.dbt.job_table)\
            .filter(self.dbt.job_table.reason == self.label)
        rows = query_cfgs.all()
        ids = tuple([str(job_row.config) for job_row in rows])
        query = query.filter(self.dbt.config_table.id.in_(ids))

      rows = query.all()
      for row in rows:
        r_dict = compose_config_obj(row, self.config_type)
        if self.config_type == ConfigType.batch_norm:
          r_dict['direction'] = row.get_direction()
        self.all_configs.append(r_dict)
    return True

  def create_dumplist(self):
    """Creating json dump to be used as fin input file"""
    self.fin_list = []
    if len(self.fin_steps) == 1 and self.fin_steps == ["get_solvers"]:
      self.fin_list = [{"steps": self.fin_steps}]
      self.logger.info("Creating dumplist for: %s", self.fin_steps[0])
      return True

    if "applicability" in self.fin_steps:
      self.logger.info("Creating dumplist for: %s", self.fin_steps[0])
      if not self.set_all_configs():
        return False
      assert self.all_configs is not None
      return self.compose_fin_list()

    self.logger.error("Fin steps not recognized: %s", self.fin_steps)
    self.logger.info("Fin steps recognized are: %s", self.supported_fin_steps)
    return False

  def compose_fin_list(self):
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

  def dump_json(self, outfile, to_file=True):
    """Dumping json to outfile"""
    if to_file is True:
      if not os.path.exists(outfile):
        os.mknod(outfile)
      fout = open(outfile, 'w')
      fout.write("[\n")
      i = 0
      while i < len(self.fin_list):
        json_out = json.dumps(self.fin_list[i])
        fout.write(json_out)
        if i != len(self.fin_list) - 1:
          fout.write(',\n')
        i += 1

      fout.write("\n]")
      fout.close()
      self.logger.info('Fin input file written to %s', outfile)
    else:
      jdump = json.dumps(self.fin_list)
      return jdump

    return True

  def run(self, outfile=None, to_file=True):
    """Main function in Fin that produces Fin input file"""

    self.cnx = self.machine.connect(self.chk_abort_file())
    ret = ''
    if outfile is None:
      outfile = "fin_input.json"
    if self.create_dumplist():
      ret = self.dump_json(outfile, to_file)
    else:
      self.logger.error("Could not create dumplist for Fin input file")

    return ret

  def parse_applicability(self, json_in):
    """Function to parse fin outputfile and populate DB with results"""
    self.logger.info('Parsing fin solver applicability output...')
    _, solver_id_map_h = get_solver_ids()
    if json_in is None:
      self.logger.error("JSON file returned from Fin is empty")
      return False
    idx = 0
    with DbSession() as session:
      for elem in json_in:
        if idx % 100 == 0:
          self.logger.info('.')
        idx += 1
        if "applicable_solvers" in elem.keys():
          #remove old applicability
          session.execute(
              'delete from {} where config={} and session={}'.format(
                  self.dbt.solver_app.__tablename__,
                  elem["input"]["config_tuna_id"], self.dbt.session.id))
          for solver in elem["applicable_solvers"]:
            try:
              new_entry = self.dbt.solver_app(
                  solver=solver_id_map_h[solver],
                  config=elem["input"]["config_tuna_id"],
                  session=self.session_id)
              session.add(new_entry)
            except KeyError:
              self.logger.warning('Solver %s not found in solver table', solver)
              self.logger.info("Please run 'go_fish.py --update_solver' first")
              return False
      self.logger.info('Commit bulk transaction, please wait')
      try:
        session.commit()
      except IntegrityError as err:
        self.logger.warning("DB err occurred commiting bulk transaction %s",
                            err)

    with DbSession() as session:
      query = session.query(sqlalchemy_func.count(self.dbt.solver_app.id))
      sapp_count = query.one()[0]
      self.logger.info("Solver applicability table updated to %d entries",
                       sapp_count)
    self.logger.info('Done parsing fin solver applicability output')
    return True

  def invalidate_solvers(self, sids, max_id):
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

  def add_new_solvers(self, solvers):
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

  def parse_solvers(self, solvers):
    """Function to parse solvers from fin output file"""
    # TODO: Refactor such that we query all the solvers # pylint: disable=fixme
    # from the db once then only insert/invalidate the new/invalid one
    max_id, sids = self.add_new_solvers(solvers)

    solver_ids_invalid = []
    if len(sids) != max_id:
      solver_ids_invalid = self.invalidate_solvers(sids, max_id)
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
