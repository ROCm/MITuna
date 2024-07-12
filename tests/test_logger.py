import logging
from tuna.utils.logger import setup_logger


# TODO: Add pytest integration testing for logstash. 

LOGGER: logging.Logger = setup_logger('testing_tuna_loggers')

LOGGER.info('Testing Tuna Logging')
LOGGER.warning('Tuna is on fire')
LOGGER.error('Tuna is not working')