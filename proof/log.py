"""Logging setup for proof scripts."""

from __future__ import annotations

import logging
import sys

from proof.config import LOG_DATE_FORMAT, LOG_FORMAT, LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger. Call once per script."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return logger
