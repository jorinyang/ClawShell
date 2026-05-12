"""Loguru logging setup with standard logging bridge.

Design: Based on MacOS v2.1 loguru_setup.py.
Bridges loguru with Python standard logging for backward compatibility.
"""
from __future__ import annotations
import sys
import logging
from typing import Optional

try:
    from loguru import logger
    _LOGURU_AVAILABLE = True
except ImportError:
    _LOGURU_AVAILABLE = False
    import logging as _logging
    logger = _logging.getLogger("clawshell")


def setup_logging(level: str = "INFO", verbose: bool = False):
    """Configure loguru as primary logger with standard logging bridge.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        verbose: Enable more detailed output
    """
    if not _LOGURU_AVAILABLE:
        logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
        return logger
    
    # Remove default handler
    logger.remove()
    
    # Console output with colored format
    log_format = (
        "<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
    )
    
    # Bridge standard logging → loguru
    class LoguruHandler(logging.Handler):
        def emit(self, record):
            level_map = {
                logging.DEBUG: logger.debug,
                logging.INFO: logger.info,
                logging.WARNING: logger.warning,
                logging.ERROR: logger.error,
                logging.CRITICAL: logger.critical,
            }
            level_fn = level_map.get(record.levelno, logger.info)
            level_fn(record.getMessage())
    
    handler = LoguruHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    return logger


def get_logger(name: Optional[str] = None):
    """Get a logger instance (loguru or standard logging)."""
    if _LOGURU_AVAILABLE and name:
        return logger.bind(name=name)
    return logger
