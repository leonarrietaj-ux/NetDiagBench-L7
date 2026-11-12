"""
NetDiagBench-L7 Structured Logger
"""

import logging

from rich.logging import RichHandler


def get_logger(name: str = "NetDiagBench") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        rich_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=False
        )
        formatter = logging.Formatter(
            fmt="%(message)s",
            datefmt="[%X]"
        )
        rich_handler.setFormatter(formatter)
        logger.addHandler(rich_handler)
    return logger


logger = get_logger()

