import logging
import sys
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{self.BOLD}{levelname:8}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        return formatted


def setup_logging(log_level: str = "INFO"):
    """Set up the logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO.
    """
    # Create a logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Convert string to logging level
    level = getattr(logging, log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Check if handlers already exist - if so, skip setup
    if root_logger.handlers:
        # Update existing handlers' levels if needed
        for handler in root_logger.handlers:
            handler.setLevel(level)
        return

    # Create formatters with consistent spacing
    # Format: YYYY-MM-DD HH:MM:SS | LEVEL    | module.name              | message
    console_formatter = ColoredFormatter(
        "%(asctime)s | %(levelname)s | %(name)-24s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(level)

    # File handler without colors
    file_handler = logging.FileHandler(log_dir / "edusphere-ai.log")
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(level)

    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set consistent format for third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING)  # Reduce access log noise
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING)  # Reduce SQL query noise

    # Set debug level for core code to match root logger level
    logging.getLogger("main").setLevel(level)
    logging.getLogger("services").setLevel(level)
    logging.getLogger("utils").setLevel(level)
    logging.getLogger("models").setLevel(level)
