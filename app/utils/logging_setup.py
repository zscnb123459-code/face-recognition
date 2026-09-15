"""Logging configuration that never writes biometric values to disk."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(data_dir: Path) -> logging.Logger:
    """Configure the root logger with console and rotating file handlers."""

    logger = logging.getLogger("facevault")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "facevault.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("无法创建日志文件，程序将继续使用控制台日志")

    logger.propagate = False
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"facevault.{name}" if name else "facevault")
