#!/usr/bin/env python3
###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
"""
Progress tracker that monitors job progress from database
and caches results in Redis for distributors to read.

This eliminates the need for each distributor to query the database,
reducing query load and preventing database deadlocks.
"""

import json
import logging
import os
import sys
import time

import redis
from sqlalchemy import text

from tuna.dbBase.sql_alchemy import DbSession
from tuna.utils.logger import setup_logger


class ProgressTracker:
  """Tracks job progress by querying database and caching in Redis"""

  def __init__(self, session_id, prefix, dbt, poll_interval=60):
    """Initialize progress tracker
    
    Args:
        session_id: Database session ID to track
        prefix: Redis key prefix for this session
        dbt: Database tables interface
        poll_interval: How often to query database (seconds)
    """
    self.session_id = session_id
    self.prefix = prefix
    self.dbt = dbt
    self.poll_interval = poll_interval
    self.logger = setup_logger('progress_tracker', add_streamhandler=True)

    # Remove any existing handlers to avoid duplicates
    self.logger.handlers.clear()

    # Add StreamHandler that writes to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    stdout_handler.setFormatter(formatter)
    self.logger.addHandler(stdout_handler)
    self.logger.setLevel(logging.INFO)

    # Connect to Redis
    backend_port = int(os.environ.get('TUNA_CELERY_BACKEND_PORT', 6379))
    backend_host = os.environ.get('TUNA_CELERY_BACKEND_HOST', 'localhost')

    try:
      self.redis = redis.Redis(host=backend_host,
                               port=backend_port,
                               db=0,
                               decode_responses=True)
      # Test connection
      self.redis.ping()
      self.logger.info("Connected to Redis at %s:%s", backend_host,
                       backend_port)
    except Exception as err:
      self.logger.error("Failed to connect to Redis: %s", err)
      raise

  def run(self):
    """Main loop: query database and update Redis"""
    self.logger.info("Progress tracker started for session %s (prefix: %s)",
                     self.session_id, self.prefix)
    self.logger.info("Polling interval: %d seconds", self.poll_interval)

    iteration = 0
    
    # Make an immediate first query to populate Redis before distributors start fetching
    try:
      self.logger.info("Making initial progress query to populate Redis...")
      progress = self.query_progress()
      self.update_redis(progress)
      self.logger.info("Initial progress: %s", progress['states'])
    except Exception as err:  # pylint: disable=broad-exception-caught
      self.logger.error("Error in initial progress query: %s", err)
    
    while True:
      iteration += 1
      try:
        progress = self.query_progress()
        self.update_redis(progress)

        # Log every 10 iterations or when interesting
        if iteration % 10 == 1 or self.is_interesting(progress):
          self.logger.info("Iteration %d - Progress: %s", iteration,
                           progress['states'])

      except KeyboardInterrupt:
        self.logger.info("Progress tracker shutting down (KeyboardInterrupt)")
        break
      except Exception as err:  # pylint: disable=broad-exception-caught
        self.logger.error("Error in progress tracker iteration %d: %s",
                          iteration, err)

      time.sleep(self.poll_interval)

    self.logger.info("Progress tracker stopped after %d iterations", iteration)

  def query_progress(self):
    """Query database for job progress
    
    Returns:
        dict: Progress summary with job counts by state
    """
    with DbSession() as session:
      # Single aggregated query - much faster than per-job queries
      query = f"""
                SELECT 
                    state,
                    COUNT(*) as count
                FROM {self.dbt.job_table.__tablename__}
                WHERE session = {self.session_id}
                AND valid = 1
                GROUP BY state
            """
      results = session.execute(text(query)).fetchall()

      progress = {
          'timestamp': time.time(),
          'session_id': self.session_id,
          'states': {row[0]: row[1] for row in results}
      }

      return progress

  def update_redis(self, progress):
    """Write progress to Redis with TTL
    
    Args:
        progress: Progress dictionary to cache
    """
    key = f"{self.prefix}:progress"
    # Set with 2 minute TTL (in case tracker dies)
    self.redis.setex(key, 120, json.dumps(progress))

  def is_interesting(self, progress):
    """Determine if progress is worth logging
    
    Args:
        progress: Progress dictionary
        
    Returns:
        bool: True if progress has changed significantly
    """
    states = progress.get('states', {})

    # Log if there are jobs in active states
    active_jobs = states.get('eval_start', 0) + states.get('compile_start', 0)
    if active_jobs > 0:
      return True

    # Log if there are new jobs
    if states.get('new', 0) > 0:
      return True

    return False


def run_progress_tracker(session_id, prefix, dbt, poll_interval=60):
  """Entry point for running progress tracker as a separate process
  
  Args:
      session_id: Database session ID
      prefix: Redis key prefix
      dbt: Database tables interface
      poll_interval: Polling interval in seconds
  """
  tracker = ProgressTracker(session_id, prefix, dbt, poll_interval)
  tracker.run()
