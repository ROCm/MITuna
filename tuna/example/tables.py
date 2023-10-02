#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2023 Advanced Micro Devices, Inc.
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
"""Module that encapsulates the DB representation"""

from typing import Dict, Any, Type
from tuna.tables_interface import DBTablesInterface
from tuna.example.example_tables import Job
from tuna.example.session import SessionExample


#pylint: disable=too-few-public-methods
class ExampleDBTables(DBTablesInterface):
  """Represents db tables for example lib"""

  def __init__(self, **kwargs: Dict[str, Any]) -> None:
    """Constructor"""
    super().__init__(**kwargs)

    #for pylint
    self.job_table: Type[Job] = Job
    self.session_table: Type[SessionExample] = SessionExample

    self.set_tables()

  def set_tables(self, sess_class=SessionExample) -> None:
    """Set appropriate tables based on requirements"""
    super().set_tables(sess_class)
    self.job_table = Job
