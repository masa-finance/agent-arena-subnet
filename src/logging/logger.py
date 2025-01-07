import logging
import sys
from typing import Optional
from enum import Enum

class Colors:
    HEADER = '\033[95m'
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class ColoredFormatter(logging.Formatter):
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    FORMATS = {
        logging.DEBUG: Colors.HEADER + format_str + Colors.ENDC,
        logging.INFO: Colors.INFO + format_str + Colors.ENDC,
        logging.WARNING: Colors.WARNING + format_str + Colors.ENDC,
        logging.ERROR: Colors.ERROR + format_str + Colors.ENDC,
        logging.CRITICAL: Colors.ERROR + Colors.BOLD + format_str + Colors.ENDC
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logger(
    name: str,
    level: LogLevel = LogLevel.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level.value)

    # Console handler with color formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # File handler if log_file is specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(file_handler)

    return logger 