"""Structured-ish file + console logging.

Everything the platform does that matters for an audit trail (auth attempts, exam
lifecycle, proctor flags, grading decisions) is logged through the ``exam`` logger so a
single file tells the story of a session.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys

from app.core.config import settings

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """Configure the root ``exam`` logger once; safe to call repeatedly."""
    global _CONFIGURED
    logger = logging.getLogger("exam")
    if _CONFIGURED:
        return logger

    log_dir = settings.log_path
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.setLevel(settings.LOG_LEVEL.upper())
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 5 MB x 5 files keeps a couple of weeks of a small deployment's history.
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "backend.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Proctoring gets its own file - it is high volume and reviewed separately.
    proctor_handler = logging.handlers.RotatingFileHandler(
        log_dir / "proctor.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    proctor_handler.setFormatter(formatter)
    proctor_logger = logging.getLogger("exam.proctor")
    proctor_logger.addHandler(proctor_handler)

    _CONFIGURED = True
    logger.info("Logging initialised -> %s", log_dir)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the ``exam`` logger, e.g. get_logger('auth')."""
    setup_logging()
    return logging.getLogger(f"exam.{name}")
