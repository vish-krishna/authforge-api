import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

# Path resolutions from src/logger/logger.py:
# .parent        -> src/logger
# .parent.parent -> src
# .parent.parent.parent -> project root (authforge-api)
LOGGER_DIR = Path(__file__).resolve().parent
SRC_DIR = LOGGER_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


class ProjectPathFormatter(logging.Formatter):
    """Formats log records with relative file paths from the project root (e.g., src/app.py)."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            record.src_path = Path(record.pathname).relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            record.src_path = record.filename
        return super().format(record)


logger = logging.getLogger("authforge")
logger.setLevel(logging.DEBUG)

# Rotating file handler
log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.handlers.RotatingFileHandler(
    log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
)

# Console handler
console_handler = logging.StreamHandler()

# Formatter with src_path
formatter = ProjectPathFormatter(
    fmt="%(asctime)s | %(levelname)-7s | %(src_path)s:%(funcName)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Avoid duplicate logs if handlers are already added
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def set_log_level(level_name: str | None) -> None:
    """Updates log levels for both logger and handlers at runtime (e.g. from Config)."""
    if not level_name:
        return

    level = getattr(logging, level_name.strip().upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

    logger.info(f"Log level updated to: {logging.getLevelName(level)}")


__all__ = ["logger", "set_log_level"]