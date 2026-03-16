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
""" Module for tagging and importing configs """
import os
import logging
import argparse
from typing import Any, Optional, Union, Tuple, List
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.db_utility import connect_db, ENGINE
from tuna.utils.logger import setup_logger
from tuna.miopen.parse_miopen_args import get_import_cfg_parser
from tuna.miopen.db.tables import ConfigType
from tuna.miopen.driver.convolution import DriverConvolution
from tuna.miopen.driver.base import DriverBase
from tuna.miopen.driver.batchnorm import DriverBatchNorm
from tuna.miopen.db.tables import MIOpenDBTables
from tuna.miopen.db.benchmark import Framework, Model
from tuna.miopen.db.tensortable import TensorTable
from tuna.utils.db_utility import build_dict_val_key


def create_query(tag: str, mark_recurrent: bool, config_id: int) -> dict:
  """Helper function to build query to add tag"""
  query_dict: dict
  if tag is None and mark_recurrent:
    query_dict = {"config": config_id, "recurrent": 1}
  elif tag is not None and not mark_recurrent:
    query_dict = {"config": config_id, "tag": tag}
  else:
    query_dict = {"config": config_id, "tag": tag, "recurrent": 1}
  return query_dict


def tag_config_v2(driver: DriverBase,
                  counts: dict,
                  dbt: MIOpenDBTables,
                  args: argparse.Namespace,
                  logger: logging.Logger,
                  new_cf: Union[DriverBase, None] = None) -> bool:
  """Adds tag for a config formatted from the fds structure.
        If mark_recurrent is ussed then it also marks it as such.
        Updates counter for tagged configs"""
  c_id = None
  if new_cf is None:
    c_id = driver.get_db_obj(keep_id=True).id
  else:
    c_id = new_cf.id

  with DbSession() as session:
    try:
      query_dict = create_query(args.tag, args.mark_recurrent, c_id)
      session.merge(dbt.config_tags_table(**query_dict))
      session.commit()
      counts['cnt_tagged_configs'].add(c_id)
    except IntegrityError as err:
      #if config/tag already exist we update recurrent=1 if required
      session.rollback()
      if "recurrent" in query_dict.keys():
        query_dict.pop("recurrent")
        #session doesnt support ON DUPLICATE KEY UPDATE, so we have to use the engine to execute
        with ENGINE.connect() as conn:
          conn.execute(dbt.config_tags_table.__table__.update().where(
              (dbt.config_tags_table.config == query_dict["config"]) &
              (dbt.config_tags_table.tag == query_dict["tag"])).values(
                  recurrent="1"))
      if "Duplicate" in str(err):
        logger.warning("Config/tag already present in %s\n",
                       dbt.config_tags_table.__tablename__)
      else:
        logger.error('Err occurred: %s', str(err))

  return True


def insert_config(driver: DriverBase, counts: dict, dbt: MIOpenDBTables,
                  args: argparse.Namespace,
                  logger: logging.Logger) -> Optional[Any]:
  """Inserts new config in the DB computed from the fds structure.
        Tags the newly inserted config. It config already exists,
        it will only tag it and log a warning for duplication."""
  new_cf = driver.get_db_obj(keep_id=True)

  with DbSession() as session:
    if new_cf.id is None:
      try:
        session.add(new_cf)
        session.commit()
        counts['cnt_configs'] += 1
        session.refresh(new_cf)
      except IntegrityError as err:
        logger.warning("Err occurred: %s", err)
        session.rollback()

    if args.mark_recurrent or args.tag:
      _ = tag_config_v2(driver, counts, dbt, args, logger, new_cf)

  return new_cf.id


def process_config_line_v2(driver: DriverBase, args: argparse.Namespace,
                           counts: dict, dbt: MIOpenDBTables,
                           logger: logging.Logger) -> bool:
  """Assumes config passed already exists and will skip the insert step
        if tag_only present. Otherwise it will first try and insert and
        then tag."""
  if args.tag_only:
    _ = tag_config_v2(driver, counts, dbt, args, logger, new_cf=None)
    return False

  _ = insert_config(driver, counts, dbt, args, logger)
  return True


def parse_line(args: argparse.Namespace, line: str, counts: dict,
               dbt: MIOpenDBTables, logger: logging.Logger) -> bool:
  """parse a driver line or fdb line from an input file and insert the config"""
  if args.config_type == ConfigType.batch_norm:
    driver = DriverBatchNorm(line, args.command)
  else:
    driver = DriverConvolution(line, args.command)

  if not args.batch_list:
    process_config_line_v2(driver, args, counts, dbt, logger)
  else:
    for bsz in args.batch_list:
      logger.info('Batchsize: %s', bsz)
      driver.batchsize = bsz
      process_config_line_v2(driver, args, counts, dbt, logger)

  return True


def batch_insert_tensors(session, tensor_dicts: List[dict], logger: logging.Logger) -> dict:
  """Insert tensors in batch with duplicate handling. Returns dict mapping tensor_key -> tensor_id"""
  if not tensor_dicts:
    return {}
  
  tensor_map = {}
  
  # Get existing tensors to avoid duplicates
  tensor_keys = [build_dict_val_key(TensorTable(**td)) for td in tensor_dicts]
  unique_dicts = {build_dict_val_key(TensorTable(**td)): td for td in tensor_dicts}
  
  # Query existing tensors
  existing_tensors = session.query(TensorTable).all()
  for tensor in existing_tensors:
    key = build_dict_val_key(tensor)
    if key in unique_dicts:
      tensor_map[key] = tensor.id
  
  # Filter out already existing tensors
  new_tensor_dicts = [td for key, td in unique_dicts.items() if key not in tensor_map]
  
  if new_tensor_dicts:
    try:
      # Bulk insert new tensors
      session.bulk_insert_mappings(TensorTable, new_tensor_dicts, return_defaults=True)
      session.flush()
      
      # Query back to get IDs
      for td in new_tensor_dicts:
        key = build_dict_val_key(TensorTable(**td))
        result = session.query(TensorTable.id).filter_by(**td).first()
        if result:
          tensor_map[key] = result[0]
    except IntegrityError as err:
      logger.warning(f"Bulk tensor insert failed, falling back to individual inserts: {err}")
      session.rollback()
      
      # Fallback: insert one by one
      for td in new_tensor_dicts:
        try:
          tensor = TensorTable(**td)
          tensor.valid = 1
          session.add(tensor)
          session.flush()
          key = build_dict_val_key(tensor)
          tensor_map[key] = tensor.id
        except IntegrityError:
          session.rollback()
          # Already exists, query it
          result = session.query(TensorTable.id).filter_by(**td).first()
          if result:
            key = build_dict_val_key(TensorTable(**td))
            tensor_map[key] = result[0]
  
  return tensor_map


def batch_insert_configs(session, drivers: List[DriverBase], dbt: MIOpenDBTables, 
                        logger: logging.Logger) -> Tuple[int, List]:
  """Insert configs in batch with duplicate handling. Returns (count_inserted, list_of_config_objects)"""
  if not drivers:
    return 0, []
  
  # Get config objects
  config_objs = [driver.get_db_obj(keep_id=True) for driver in drivers]
  
  # Filter out configs that already have IDs (already in DB)
  new_configs = [c for c in config_objs if c.id is None]
  
  if not new_configs:
    return 0, config_objs
  
  # Get MD5s of new configs to check for existing
  new_md5s = [c.md5 for c in new_configs]
  existing_md5s = session.query(dbt.config_table.md5).filter(
      dbt.config_table.md5.in_(new_md5s)
  ).all()
  existing_md5_set = {row[0] for row in existing_md5s}
  
  # Filter to only truly new configs
  truly_new_configs = [c for c in new_configs if c.md5 not in existing_md5_set]
  
  inserted_count = 0
  if truly_new_configs:
    try:
      # Try bulk insert
      session.bulk_save_objects(truly_new_configs, return_defaults=True)
      session.flush()
      inserted_count = len(truly_new_configs)
    except IntegrityError as err:
      logger.warning(f"Bulk config insert failed, falling back to individual inserts: {err}")
      session.rollback()
      
      # Fallback: insert one by one
      for config in truly_new_configs:
        try:
          session.add(config)
          session.flush()
          inserted_count += 1
        except IntegrityError:
          session.rollback()
  
  # Refresh all configs to get IDs
  for config in config_objs:
    if config.id is None:
      # Query to get ID
      result = session.query(dbt.config_table.id).filter_by(md5=config.md5).first()
      if result:
        config.id = result[0]
  
  return inserted_count, config_objs


def batch_insert_tags(session, config_ids: List[int], dbt: MIOpenDBTables,
                     args: argparse.Namespace, logger: logging.Logger) -> int:
  """Insert tags in batch with duplicate handling. Returns count of tags inserted"""
  if not config_ids or not (args.tag or args.mark_recurrent):
    return 0
  
  # Build tag dictionaries
  tag_dicts = []
  for config_id in config_ids:
    tag_dict = create_query(args.tag, args.mark_recurrent, config_id)
    tag_dicts.append(tag_dict)
  
  if not tag_dicts:
    return 0
  
  # Get existing tags to avoid duplicates
  if args.tag:
    existing_tags = session.query(dbt.config_tags_table.config).filter(
        dbt.config_tags_table.config.in_(config_ids),
        dbt.config_tags_table.tag == args.tag
    ).all()
    existing_config_ids = {row[0] for row in existing_tags}
    tag_dicts = [td for td in tag_dicts if td['config'] not in existing_config_ids]
  
  inserted_count = 0
  if tag_dicts:
    try:
      # Try bulk insert
      session.bulk_insert_mappings(dbt.config_tags_table, tag_dicts)
      session.flush()
      inserted_count = len(tag_dicts)
    except IntegrityError as err:
      logger.warning(f"Bulk tag insert failed, falling back to individual inserts: {err}")
      session.rollback()
      
      # Fallback: insert one by one
      for tag_dict in tag_dicts:
        try:
          tag_obj = dbt.config_tags_table(**tag_dict)
          session.merge(tag_obj)
          session.flush()
          inserted_count += 1
        except IntegrityError:
          session.rollback()
  
  return inserted_count


def get_or_create_tensor_ids(session, tensor_dicts: List[dict], logger: logging.Logger) -> dict:
  """Get or create tensor IDs in bulk. Returns dict mapping tensor_key -> tensor_id"""
  if not tensor_dicts:
    return {}
  
  import time
  t0 = time.time()
  
  # Build unique tensor dict map
  unique_tensors = {}
  for td in tensor_dicts:
    td['valid'] = 1
    key = build_dict_val_key(TensorTable(**td))
    unique_tensors[key] = td
  
  logger.info("Found %d unique tensors to process", len(unique_tensors))
  
  # Query existing tensors in bulk
  existing_tensors = session.query(TensorTable).all()
  tensor_id_map = {}
  for tensor in existing_tensors:
    key = build_dict_val_key(tensor)
    if key in unique_tensors:
      tensor_id_map[key] = tensor.id
  
  logger.info("Found %d existing tensors in DB (%.2fs)", len(tensor_id_map), time.time() - t0)
  
  # Insert new tensors
  new_tensors = [td for key, td in unique_tensors.items() if key not in tensor_id_map]
  if new_tensors:
    t0 = time.time()
    try:
      session.bulk_insert_mappings(TensorTable, new_tensors)
      session.flush()
      logger.info("Bulk inserted %d new tensors (%.2fs)", len(new_tensors), time.time() - t0)
      
      # Query back to get IDs
      for td in new_tensors:
        result = session.query(TensorTable.id).filter_by(**td).first()
        if result:
          key = build_dict_val_key(TensorTable(**td))
          tensor_id_map[key] = result[0]
    except IntegrityError as err:
      logger.warning(f"Bulk tensor insert failed: {err}")
      session.rollback()
      # Fallback to individual
      for td in new_tensors:
        try:
          tensor = TensorTable(**td)
          session.add(tensor)
          session.flush()
          key = build_dict_val_key(tensor)
          tensor_id_map[key] = tensor.id
        except IntegrityError:
          session.rollback()
          result = session.query(TensorTable.id).filter_by(**td).first()
          if result:
            key = build_dict_val_key(TensorTable(**td))
            tensor_id_map[key] = result[0]
  
  return tensor_id_map


def import_cfgs_batch_ultra(args: argparse.Namespace, dbt: MIOpenDBTables,
                           logger: logging.Logger, batch_size: int = 1000) -> dict:
  """Ultra-optimized batch import bypassing get_db_obj()"""
  import time
  import hashlib
  from tuna.miopen.utils.metadata import TENSOR_PRECISION
  
  connect_db()
  
  counts = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()
  
  # Step 1: Read and parse
  start_time = time.time()
  logger.info("Reading and parsing config file...")
  drivers_to_process = []
  unique_lines = set()
  
  with open(os.path.expanduser(args.file_name), "r") as infile:
    for line in infile:
      line = line.strip()
      if line:
        unique_lines.add(line)
  
  for line in unique_lines:
    try:
      if args.config_type == ConfigType.batch_norm:
        driver = DriverBatchNorm(line, args.command)
      else:
        driver = DriverConvolution(line, args.command)
      
      if not args.batch_list:
        drivers_to_process.append(driver)
      else:
        for bsz in args.batch_list:
          driver_copy = DriverBatchNorm(line, args.command) if args.config_type == ConfigType.batch_norm else DriverConvolution(line, args.command)
          driver_copy.batchsize = bsz
          drivers_to_process.append(driver_copy)
    except ValueError as err:
      logger.warning(f"Error parsing line: {err}")
  
  parse_time = time.time() - start_time
  logger.info("Parsed %u driver objects (took %.2fs)", len(drivers_to_process), parse_time)
  
  # Step 2: Collect all unique tensors
  start_time = time.time()
  logger.info("Collecting tensor dictionaries...")
  all_tensor_dicts = []
  for driver in drivers_to_process:
    input_t = driver._MIOpenDriver__compose_input_t() if hasattr(driver, '_MIOpenDriver__compose_input_t') else {}
    weight_t = driver.compose_weight_t()
    all_tensor_dicts.extend([input_t, weight_t])
  
  logger.info("Collected %d tensor dicts (took %.2fs)", len(all_tensor_dicts), time.time() - start_time)
  
  # Step 3: Batch process tensors and configs
  total_drivers = len(drivers_to_process)
  logger.info(f"Starting ultra-optimized batch import (batch size: {batch_size})...")
  overall_start = time.time()
  
  for batch_start in range(0, total_drivers, batch_size):
    batch_end = min(batch_start + batch_size, total_drivers)
    batch = drivers_to_process[batch_start:batch_end]
    
    with DbSession() as session:
      # Collect tensors for this batch
      batch_tensor_dicts = []
      for driver in batch:
        input_t = driver._MIOpenDriver__compose_input_t() if hasattr(driver, '_MIOpenDriver__compose_input_t') else {}
        weight_t = driver.compose_weight_t()
        batch_tensor_dicts.extend([input_t, weight_t])
      
      # Get/create tensor IDs
      tensor_id_map = get_or_create_tensor_ids(session, batch_tensor_dicts, logger)
      
      # Build config dictionaries manually (bypass get_db_obj)
      config_dicts = []
      for driver in batch:
        try:
          # Get tensor IDs
          input_t = driver._MIOpenDriver__compose_input_t() if hasattr(driver, '_MIOpenDriver__compose_input_t') else {}
          weight_t = driver.compose_weight_t()
          input_t['valid'] = 1
          weight_t['valid'] = 1
          
          input_key = build_dict_val_key(TensorTable(**input_t))
          weight_key = build_dict_val_key(TensorTable(**weight_t))
          
          if input_key not in tensor_id_map or weight_key not in tensor_id_map:
            logger.warning("Missing tensor IDs for config, skipping")
            continue
          
          # Build config dict manually
          config_dict = {
            'batchsize': driver.batchsize,
            'spatial_dim': driver.spatial_dim,
            'pad_h': driver.pad_h,
            'pad_w': driver.pad_w,
            'pad_d': driver.pad_d,
            'conv_stride_h': driver.conv_stride_h,
            'conv_stride_w': driver.conv_stride_w,
            'conv_stride_d': driver.conv_stride_d,
            'dilation_h': driver.dilation_h,
            'dilation_w': driver.dilation_w,
            'dilation_d': driver.dilation_d,
            'group_count': driver.group_count,
            'mode': driver.mode,
            'pad_mode': driver.pad_mode,
            'trans_output_pad_h': driver.trans_output_pad_h,
            'trans_output_pad_w': driver.trans_output_pad_w,
            'trans_output_pad_d': driver.trans_output_pad_d,
            'direction': driver.direction,
            'input_tensor': tensor_id_map[input_key],
            'weight_tensor': tensor_id_map[weight_key],
            'out_layout': driver.out_layout,
            'driver': str(driver)
          }
          
          # Compute MD5
          dict_copy = config_dict.copy()
          dict_copy.pop('driver')
          md5_str = str(sorted(dict_copy.items()))
          config_dict['md5'] = hashlib.md5(md5_str.encode()).hexdigest()
          
          config_dicts.append(config_dict)
        except Exception as err:
          logger.warning(f"Error building config dict: {err}")
      
      # Bulk insert configs
      if config_dicts:
        # Check for existing
        md5s = [cd['md5'] for cd in config_dicts]
        existing = session.query(dbt.config_table.md5).filter(
          dbt.config_table.md5.in_(md5s)
        ).all()
        existing_set = {row[0] for row in existing}
        
        new_configs = [cd for cd in config_dicts if cd['md5'] not in existing_set]
        
        if new_configs:
          try:
            session.bulk_insert_mappings(dbt.config_table, new_configs)
            session.flush()
            counts['cnt_configs'] += len(new_configs)
          except IntegrityError as err:
            logger.warning(f"Bulk config insert failed: {err}")
            session.rollback()
        
        # Get config IDs for tagging
        if args.tag or args.mark_recurrent:
          config_ids = []
          for cd in config_dicts:
            result = session.query(dbt.config_table.id).filter_by(md5=cd['md5']).first()
            if result:
              config_ids.append(result[0])
          
          if config_ids:
            tag_dicts = [create_query(args.tag, args.mark_recurrent, cid) for cid in config_ids]
            
            # Filter existing tags
            if args.tag:
              existing_tags = session.query(dbt.config_tags_table.config).filter(
                dbt.config_tags_table.config.in_(config_ids),
                dbt.config_tags_table.tag == args.tag
              ).all()
              existing_tag_set = {row[0] for row in existing_tags}
              tag_dicts = [td for td in tag_dicts if td['config'] not in existing_tag_set]
            
            if tag_dicts:
              try:
                session.bulk_insert_mappings(dbt.config_tags_table, tag_dicts)
                session.flush()
                counts['cnt_tagged_configs'].update([td['config'] for td in tag_dicts])
              except IntegrityError:
                session.rollback()
      
      session.commit()
    
    if batch_end % 1000 == 0 or batch_end == total_drivers:
      logger.info(f"Processed {batch_end}/{total_drivers} configs")
  
  total_time = time.time() - overall_start
  logger.info("Ultra-optimized import complete (took %.2fs, %.2f configs/sec)", 
              total_time, total_drivers / total_time if total_time > 0 else 0)
  return counts


def import_cfgs_batch(args: argparse.Namespace, dbt: MIOpenDBTables,
                     logger: logging.Logger, batch_size: int = 1000) -> dict:
  """Optimized batch import of configs with proper tensor handling"""
  import time
  from tuna.utils.db_utility import get_session_val_map
  from tuna.miopen.driver.base import MIOpenDriver
  
  connect_db()
  
  counts = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()
  unique_lines = set()
  
  # Step 1: Read and deduplicate file
  start_time = time.time()
  logger.info("Reading and deduplicating config file...")
  with open(os.path.expanduser(args.file_name), "r") as infile:
    for line_cnt, line in enumerate(infile, 1):
      line = line.strip()
      if line:
        unique_lines.add(line)
        if line_cnt % 10000 == 0:
          logger.info("Parsed: %u lines, unique configs: %u", line_cnt, len(unique_lines))
  
  parse_time = time.time() - start_time
  logger.info("File parsing complete. Total lines: %u, unique configs: %u (took %.2fs)", 
              line_cnt, len(unique_lines), parse_time)
  
  # Step 2: Pre-load tensor cache to avoid repeated queries
  start_time = time.time()
  logger.info("Pre-loading tensor cache...")
  with DbSession() as session:
    tensor_attr = [column.name for column in TensorTable.__table__.columns]
    MIOpenDriver.tensor_id_map = get_session_val_map(session, TensorTable, tensor_attr)
  cache_time = time.time() - start_time
  logger.info("Tensor cache loaded with %u entries (took %.2fs)", 
              len(MIOpenDriver.tensor_id_map), cache_time)
  
  # Step 3: Parse all driver objects
  start_time = time.time()
  logger.info("Parsing driver commands...")
  drivers_to_process = []
  for line in unique_lines:
    try:
      if args.config_type == ConfigType.batch_norm:
        driver = DriverBatchNorm(line, args.command)
      else:
        driver = DriverConvolution(line, args.command)
      
      if not args.batch_list:
        drivers_to_process.append(driver)
      else:
        for bsz in args.batch_list:
          driver_copy = DriverBatchNorm(line, args.command) if args.config_type == ConfigType.batch_norm else DriverConvolution(line, args.command)
          driver_copy.batchsize = bsz
          drivers_to_process.append(driver_copy)
    except ValueError as err:
      logger.warning(f"Error parsing line: {err}")
  
  driver_parse_time = time.time() - start_time
  logger.info("Parsed %u driver objects to import (took %.2fs)", 
              len(drivers_to_process), driver_parse_time)
  
  # Step 4: Process in batches with true batch operations
  total_drivers = len(drivers_to_process)
  start_time = time.time()
  logger.info(f"Starting batch import (batch size: {batch_size})...")
  
  batch_times = {'get_db_obj': 0, 'check_existing': 0, 'insert_configs': 0, 'insert_tags': 0, 'commit': 0}
  
  for batch_start in range(0, total_drivers, batch_size):
    batch_end = min(batch_start + batch_size, total_drivers)
    batch = drivers_to_process[batch_start:batch_end]
    batch_start_time = time.time()
    
    with DbSession() as session:
      # Collect all config objects for this batch
      t0 = time.time()
      config_objs = []
      for driver in batch:
        try:
          config_obj = driver.get_db_obj(keep_id=True)
          config_objs.append((driver, config_obj))
        except ValueError as err:
          logger.warning(f"Error creating config object: {err}")
      batch_times['get_db_obj'] += time.time() - t0
      
      if not args.tag_only:
        # Batch insert configs
        t0 = time.time()
        new_configs = [c for d, c in config_objs if c.id is None]
        
        if new_configs:
          # Check for existing configs by MD5
          new_md5s = [c.md5 for c in new_configs]
          existing_md5s = session.query(dbt.config_table.md5).filter(
              dbt.config_table.md5.in_(new_md5s)
          ).all()
          existing_md5_set = {row[0] for row in existing_md5s}
          batch_times['check_existing'] += time.time() - t0
          
          # Filter to truly new configs
          truly_new = [c for c in new_configs if c.md5 not in existing_md5_set]
          
          if truly_new:
            t0 = time.time()
            try:
              session.bulk_save_objects(truly_new, return_defaults=True)
              session.flush()
              counts['cnt_configs'] += len(truly_new)
            except IntegrityError as err:
              logger.warning(f"Bulk insert failed, using individual inserts: {err}")
              session.rollback()
              for config in truly_new:
                try:
                  session.add(config)
                  session.flush()
                  counts['cnt_configs'] += 1
                except IntegrityError:
                  session.rollback()
            batch_times['insert_configs'] += time.time() - t0
          
          # Refresh configs to get IDs
          for config in new_configs:
            if config.id is None:
              result = session.query(dbt.config_table.id).filter_by(md5=config.md5).first()
              if result:
                config.id = result[0]
      
      # Batch insert tags
      if args.tag or args.mark_recurrent:
        t0 = time.time()
        config_ids = [c.id for d, c in config_objs if c.id is not None]
        
        if config_ids:
          tag_dicts = [create_query(args.tag, args.mark_recurrent, cid) for cid in config_ids]
          
          # Filter out existing tags
          if args.tag:
            existing_tags = session.query(dbt.config_tags_table.config).filter(
                dbt.config_tags_table.config.in_(config_ids),
                dbt.config_tags_table.tag == args.tag
            ).all()
            existing_set = {row[0] for row in existing_tags}
            tag_dicts = [td for td in tag_dicts if td['config'] not in existing_set]
          
          if tag_dicts:
            try:
              session.bulk_insert_mappings(dbt.config_tags_table, tag_dicts)
              session.flush()
              counts['cnt_tagged_configs'].update([td['config'] for td in tag_dicts])
            except IntegrityError as err:
              logger.warning(f"Bulk tag insert failed, using individual inserts: {err}")
              session.rollback()
              for tag_dict in tag_dicts:
                try:
                  tag_obj = dbt.config_tags_table(**tag_dict)
                  session.merge(tag_obj)
                  session.flush()
                  counts['cnt_tagged_configs'].add(tag_dict['config'])
                except IntegrityError:
                  session.rollback()
        batch_times['insert_tags'] += time.time() - t0
      
      # Commit the entire batch
      t0 = time.time()
      try:
        session.commit()
      except IntegrityError as err:
        logger.error(f"Batch commit failed: {err}")
        session.rollback()
      batch_times['commit'] += time.time() - t0
    
    if batch_end % 1000 == 0 or batch_end == total_drivers:
      batch_elapsed = time.time() - batch_start_time
      logger.info(f"Processed {batch_end}/{total_drivers} configs (batch took {batch_elapsed:.2f}s)")
  
  total_import_time = time.time() - start_time
  logger.info("Database import complete (took %.2fs)", total_import_time)
  logger.info("Timing breakdown: get_db_obj=%.2fs, check_existing=%.2fs, insert_configs=%.2fs, insert_tags=%.2fs, commit=%.2fs",
              batch_times['get_db_obj'], batch_times['check_existing'], 
              batch_times['insert_configs'], batch_times['insert_tags'], batch_times['commit'])
  
  logger.info("Database import complete.")
  return counts


def import_cfgs(args: argparse.Namespace, dbt: MIOpenDBTables,
                logger: logging.Logger) -> dict:
  """import configs to mysql from file with driver invocations"""
  connect_db()

  counts: dict = {}
  counts['cnt_configs'] = 0
  counts['cnt_tagged_configs'] = set()
  unique_lines = set()
  
  logger.info("Reading and deduplicating config file...")
  with open(os.path.expanduser(args.file_name), "r") as infile:  # pylint: disable=unspecified-encoding
    for line_cnt, line in enumerate(infile, 1):
      line = line.strip()
      if line:  # Skip empty lines
        unique_lines.add(line)
        if line_cnt % 10000 == 0:
          logger.info("Parsed: %u lines, unique configs: %u", line_cnt, len(unique_lines))
  
  logger.info("File parsing complete. Total lines: %u, unique configs: %u", line_cnt, len(unique_lines))
  logger.info("Starting database import...")
  
  for idx, line in enumerate(unique_lines, 1):
    try:
      parse_line(args, line, counts, dbt, logger)
      if idx % 1000 == 0:
        logger.info("Processed %u/%u unique configs", idx, len(unique_lines))
    except ValueError as err:
      logger.warning(err)
  
  logger.info("Database import complete.")
  return counts


def set_import_cfg_batches(args: argparse.Namespace):
  """Setting batches for import_configs subcommands"""
  #import configs
  if args.batches is not None:
    args.batch_list = [int(x) for x in args.batches.split(',')]
  else:
    args.batch_list = []


def print_models(logger: logging.Logger) -> bool:
  """Display models from the db table"""
  with DbSession() as session:
    models = session.query(Model).all()
    for model in models:
      logger.info('model %s version %s ', model.model, model.version)
  return True


def add_model(args: argparse.Namespace, logger: logging.Logger) -> bool:
  """Add new model and version to the db table"""
  with DbSession() as session:
    new_model = Model(model=args.add_model, version=args.md_version)
    try:
      session.add(new_model)
      session.commit()
      logger.info('Added model %s with version %s ', args.add_model,
                  str(args.md_version))
    except IntegrityError as err:
      logger.error(err)
      return False

  return True


def add_frameworks(args: argparse.Namespace, logger: logging.Logger) -> bool:
  """Bring DB table up to speed with enums defined in FrameworkEnum"""
  with DbSession() as session:
    new_framework = Framework(framework=args.add_framework,
                              version=args.fw_version)
    try:
      session.add(new_framework)
      session.commit()
      logger.info('Added framework %s with version %s ', args.add_framework,
                  str(args.fw_version))
    except IntegrityError as err:
      logger.error(err)
      return False

  return True


def get_database_id(framework: Framework, fw_version: int, model: int,
                    md_version: float, dbt: MIOpenDBTables,
                    logger: logging.Logger) -> Tuple[int, int]:
  """Get DB id of item"""

  mid = -1
  fid = -1
  with DbSession() as session:
    try:
      res = session.query(
          dbt.framework.id).filter(dbt.framework.framework == framework)\
                           .filter(dbt.framework.version == fw_version).one()
      fid = res.id
    except NoResultFound as dberr:
      logger.error(dberr)
      logger.error(
          "Framework not present in the DB. Please run 'import_benchmark.py --add_framework' "\
     "to populate the DB table"
      )
    try:
      res = session.query(dbt.model.id).filter(dbt.model.model == model)\
                                       .filter(dbt.model.version == md_version).one()
      mid = res.id
    except NoResultFound as dberr:
      logger.error(
          "Model not present in the DB. Please run 'import_config.py --add_model' to "\
     "populate the DB table"
      )
      logger.error(dberr)
  return mid, fid


def add_benchmark(args: argparse.Namespace, dbt: MIOpenDBTables,
                  logger: logging.Logger) -> bool:
  """Add new benchmark"""
  mid, fid = get_database_id(args.framework, args.fw_version, args.model,
                             args.md_version, dbt, logger)
  if mid is None:
    logger.error('Could not find DB entry for model:%s, version:%s', args.model,
                 args.md_version)
    return False
  if fid is None:
    logger.error('Could not find DB entry for framework:%s, version:%s',
                 args.framework, args.fw_version)
    return False
  commands = []
  if args.driver:
    commands.append(args.driver)
  else:
    with open(os.path.expanduser(args.file_name), "r") as infile:  # pylint: disable=unspecified-encoding
      for line in infile:
        commands.append(line)

  count = 0

  with DbSession() as session:
    for cmd in commands:
      try:
        if args.config_type == ConfigType.convolution:
          driver = DriverConvolution(line=cmd)
        else:
          driver = DriverBatchNorm(line=cmd)
        db_obj = driver.get_db_obj(keep_id=True)
        if db_obj.id is None:
          logger.error('Config not present in the DB: %s', str(driver))
          logger.error('Please use import_configs.py to import configs')

        benchmark = dbt.benchmark()
        benchmark.framework = fid
        benchmark.model = mid
        benchmark.config = db_obj.id
        benchmark.gpu_number = args.gpu_count
        benchmark.driver_cmd = str(driver)
        benchmark.batchsize = driver.batchsize
        session.add(benchmark)
        session.commit()
        count += 1
      except (ValueError, IntegrityError) as verr:
        logger.warning(verr)
        session.rollback()
  logger.info('Benchmarked %s configs', count)
  return True


def check_import_benchmark_args(args: argparse.Namespace) -> None:
  """Checking args for import_benchmark subcommand"""
  if args.add_model and not args.md_version:
    raise ValueError('Version needs to be specified with model')
  if args.add_benchmark and not (args.model and args.framework and
                                 args.gpu_count and args.md_version and
                                 args.fw_version and
                                 (args.driver or args.file_name)):
    raise ValueError(
        """Model, md_version, framework, fw_version, driver(or filename), \n
         and gpus need to all be specified to add a new benchmark""")


# pylint: disable=too-many-return-statements
def run_import_configs(args: argparse.Namespace,
                       logger: logging.Logger) -> bool:
  """Main function"""
  dbt = MIOpenDBTables(session_id=None, config_type=args.config_type)

  if args.print_models or args.add_model or args.add_framework or args.add_benchmark:
    check_import_benchmark_args(args)

  if args.print_models:
    print_models(logger)
    return True
  if args.add_model:
    add_model(args, logger)
    return True
  if args.add_framework:
    add_frameworks(args, logger)
    return True
  if args.add_benchmark:
    add_benchmark(args, dbt, logger)
    return True

  set_import_cfg_batches(args)
  
  # Use batch import by default unless disabled or tag_only mode
  use_batch = not getattr(args, 'disable_batch_import', False) and not args.tag_only
  batch_size = getattr(args, 'batch_size', 1000)
  
  if use_batch:
    logger.info("Using optimized batch import (batch_size=%d)", batch_size)
    counts = import_cfgs_batch(args, dbt, logger, batch_size)
  else:
    if args.tag_only:
      logger.info("Using original import (tag_only mode)")
    else:
      logger.info("Using original import (batch import disabled)")
    counts = import_cfgs(args, dbt, logger)

  logger.info('New configs added: %u', counts['cnt_configs'])
  if args.tag or args.tag_only:
    logger.info('Tagged configs: %u', len(counts['cnt_tagged_configs']))

  return True


def main():
  """ main """
  parser = get_import_cfg_parser(with_yaml=False)
  args = parser.parse_args()
  run_import_configs(args, setup_logger('import_configs'))


if __name__ == '__main__':
  main()
