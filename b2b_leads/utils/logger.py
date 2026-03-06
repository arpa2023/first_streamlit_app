# utils/logger.py
import logging
import sys
from pathlib import Path
from datetime import datetime


def get_logger(name: str, log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """Erstellt einen konfigurierten Logger mit File- und Console-Handler."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Bereits konfiguriert

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler (täglich rotierend)
    today = datetime.now().strftime("%Y-%m-%d")
    fh = logging.FileHandler(log_path / f"b2b_leads_{today}.log", encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
