import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger("authforge")
logger.setLevel(logging.DEBUG)

# File handler with rotation
log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
)
file_handler.setLevel(logging.DEBUG)

# Console handler for INFO and above
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Formatter: %(filename)s shows 'main.py', %(funcName)s shows 'run', %(lineno)d shows line number
formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-5s | %(filename)s:%(funcName)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Avoid duplicate logs if handlers are already added
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

__all__ = ["logger"]