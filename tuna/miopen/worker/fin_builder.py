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
"""Builder class implements the worker interface. The purpose of this class is to run fin
jobs in compile mode"""
import json

from sqlalchemy.inspection import inspect

from tuna.miopen.worker.fin_class import FinClass
from tuna.miopen.worker.fin_utils import fin_job


class FinBuilder(FinClass):
  """ The Builder class implementes the worker class. Its purpose is to compile jobs. It picks up
  new jobs and when completed, sets the state to compiled. """

  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.jcache_attr = [
        column.name for column in inspect(self.dbt.fin_cache_table).c
    ]
    self.jcache_attr.remove("insert_ts")
    self.jcache_attr.remove("update_ts")
    self.jcache_attr.remove("valid")  #use default, don't specify
    self.worker_type = "fin_build_worker"

  def get_fin_input(self):
    """Create the input dict for fin, serialize to json and write to machine
       Returns the filename on machine"""
    # convert self.job and self.config to a json string
    fjob = fin_job(self.fin_steps, self.dynamic_solvers_only, self.job,
                   self.config, self.dbt)

    fjob = [fjob]

    fin_input = self.machine.write_file(json.dumps(fjob, indent=2).encode(),
                                        is_temp=True)
    return fin_input

  def compose_job_cache_entrys(self, session, pdb_obj):
    """Compose new pdb kernel cache entry from fin input"""
    for kern_obj in pdb_obj['kernel_objects']:
      kernel_obj = self.dbt.fin_cache_table()
      self.populate_kernels(kern_obj, kernel_obj)
      kernel_obj.solver_id = self.solver_id_map[pdb_obj['solver_name']]
      kernel_obj.job_id = self.job.id

      session.add(kernel_obj)
    session.commit()

    return True

  def step(self):
    """Main functionality of the builder class. It picks up jobs in new state and compiles them"""

    if not self.init_check_env():
      return False

    fin_json = self.run_fin_cmd()
    return fin_json
