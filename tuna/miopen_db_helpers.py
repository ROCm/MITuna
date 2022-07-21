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
""" Module for creating DB tables"""

from tuna.utils.logger import setup_logger

LOGGER = setup_logger('miopen_db_helpers')

GET_JOB_IDX = [
    "valid", "reason", "arch", "num_cu", "fin_step", "retries", "state",
    "config"
]
GET_COMPILE_JOB_IDX = ["valid", "state", "reason", "arch", "num_cu"]


def get_timestamp_trigger():
  """setting up for job table triggers"""
  trigger_timestamp = """CREATE trigger timestamp_trigger before UPDATE on conv_job
  for each row
  begin
   if NEW.state='compiled' then set NEW.compile_end=now();
   elseif NEW.state='compiling' then set NEW.compile_start=now();
   elseif NEW.state='evaluating' then set NEW.eval_start=now();
   elseif NEW.state='evaluated' then set NEW.eval_end=now();
   end if;
  end;"""

  return trigger_timestamp


def get_conv_config_triggers():
  """setting up trigger for conv_config table"""
  conv_trigger_insert = "CREATE trigger md5_trigger_conv_config_insert before INSERT  \
  on conv_config for each row set \
  NEW.md5=MD5(CONCAT(NEW.batchsize, NEW.spatial_dim, NEW.pad_h, \
  NEW.pad_w, NEW.pad_d, NEW.conv_stride_h, NEW.conv_stride_w, NEW.conv_stride_d, \
  NEW.dilation_h, NEW.dilation_w, NEW.dilation_d, \
  NEW.group_count, NEW.conv_mode, NEW.pad_mode, NEW.trans_output_pad_h, \
  NEW.trans_output_pad_w, NEW.trans_output_pad_d, NEW.direction, NEW.input_tensor, NEW.weight_tensor, \
  NEW.out_layout));"

  conv_trigger_update = "CREATE trigger md5_trigger_conv_config_update before UPDATE \
  on conv_config for each row set \
  NEW.md5=MD5(CONCAT(NEW.batchsize, NEW.spatial_dim, NEW.pad_h, \
  NEW.pad_w, NEW.pad_d, NEW.conv_stride_h, NEW.conv_stride_w, NEW.conv_stride_d, \
  NEW.dilation_h, NEW.dilation_w, NEW.dilation_d, \
  NEW.group_count, NEW.conv_mode, NEW.pad_mode, NEW.trans_output_pad_h, \
  NEW.trans_output_pad_w, NEW.trans_output_pad_d, NEW.direction, NEW.input_tensor, NEW.weight_tensor, \
  NEW.out_layout));"

  return conv_trigger_insert, conv_trigger_update


def get_miopen_indices():
  """Return MIOpen Tuna DB specific indices"""
  idx = []
  idx.append(
      "create index idx_get_job on conv_job(valid, reason, arch, num_cu, fin_step, \
                retries, state, config);")

  idx.append(
      "create index idx_get_compile on conv_job(valid, state, reason, arch, \
                        num_cu);")
  return idx


def get_miopen_triggers():
  """add triggers for updating md5 fields"""
  md5_trg = []

  conv_config_ti, conv_config_tu = get_conv_config_triggers()
  md5_trg.append(conv_config_ti)
  md5_trg.append(conv_config_tu)

  return md5_trg


def drop_miopen_triggers():
  """Drop triggers if they exist"""
  #workaround for triggers not supported in ORM
  drop_triggers = []
  drop_triggers.append("md5_trigger;")
  drop_triggers.append("md5_trigger_update;")
  drop_triggers.append("md5_trigger_conv_config_insert;")
  drop_triggers.append("md5_trigger_conv_config_update;")

  return drop_triggers
