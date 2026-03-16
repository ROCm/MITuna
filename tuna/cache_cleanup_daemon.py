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
"""Periodic cache cleanup daemon to prevent lock contention during job processing"""

import os
import sys
import time
import logging
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from tuna.utils.logger import setup_logger
from tuna.dbBase.sql_alchemy import DbSession
from tuna.miopen.db.tables import MIOpenDBTables

LOGGER = setup_logger('cache_cleanup_daemon')


def cleanup_invalid_kernel_cache(session_id, dbt):
  """Clean up invalid kernel cache entries
  
  This function removes kernel_cache entries marked as invalid (valid=0).
  It's designed to run periodically to avoid lock contention during job processing.
  
  Returns:
      int: Number of entries deleted, or -1 on error
  """
  with DbSession() as session:
    try:
      # Delete invalid kernel cache entries
      # Use LIMIT to avoid long-running locks
      batch_size = int(os.environ.get('TUNA_CLEANUP_BATCH_SIZE', '1000'))
      
      query = text(f"""
        DELETE FROM {dbt.kernel_cache.__tablename__}
        WHERE valid = 0
        LIMIT {batch_size}
      """)
      
      result = session.execute(query)
      deleted_count = result.rowcount
      session.commit()
      
      if deleted_count > 0:
        LOGGER.info('Cleaned up %d invalid kernel_cache entries', deleted_count)
      else:
        LOGGER.debug('No invalid kernel_cache entries to clean')
      
      return deleted_count
      
    except OperationalError as err:
      session.rollback()
      LOGGER.warning('Unable to clean kernel_cache: %s', err)
      return -1


def run_cleanup_daemon(session_id):
  """Run periodic cleanup daemon
  
  Args:
      session_id: Session ID to clean up for
  """
  # Configuration from environment variables
  cleanup_interval = int(os.environ.get('TUNA_CLEANUP_INTERVAL', '300'))  # 5 minutes default
  max_iterations = int(os.environ.get('TUNA_CLEANUP_MAX_ITERATIONS', '0'))  # 0 = infinite
  
  LOGGER.info('Starting cache cleanup daemon for session %d', session_id)
  LOGGER.info('Cleanup interval: %d seconds', cleanup_interval)
  LOGGER.info('Max iterations: %s', 'infinite' if max_iterations == 0 else max_iterations)
  
  # Initialize database tables
  dbt = MIOpenDBTables(session_id=session_id)
  
  iteration = 0
  total_cleaned = 0
  
  try:
    while True:
      iteration += 1
      
      # Check if we should stop
      if max_iterations > 0 and iteration > max_iterations:
        LOGGER.info('Reached max iterations (%d), stopping cleanup daemon', max_iterations)
        break
      
      LOGGER.info('Cleanup iteration %d - sleeping for %d seconds', iteration, cleanup_interval)
      time.sleep(cleanup_interval)
      
      # Perform cleanup
      LOGGER.info('Running cleanup iteration %d', iteration)
      deleted = cleanup_invalid_kernel_cache(session_id, dbt)
      
      if deleted > 0:
        total_cleaned += deleted
        LOGGER.info('Iteration %d: Deleted %d entries (total: %d)', 
                   iteration, deleted, total_cleaned)
      elif deleted == 0:
        LOGGER.debug('Iteration %d: No entries to clean', iteration)
      else:
        LOGGER.warning('Iteration %d: Cleanup failed', iteration)
      
  except KeyboardInterrupt:
    LOGGER.info('Cleanup daemon interrupted by user')
  except Exception as err:  # pylint: disable=broad-exception-caught
    LOGGER.error('Cleanup daemon error: %s', err)
    raise
  finally:
    LOGGER.info('Cleanup daemon stopped after %d iterations (total cleaned: %d)', 
               iteration, total_cleaned)


def main():
  """Main entry point"""
  if len(sys.argv) < 2:
    print("Usage: cache_cleanup_daemon.py <session_id>")
    sys.exit(1)
  
  session_id = int(sys.argv[1])
  run_cleanup_daemon(session_id)


if __name__ == '__main__':
  main()
