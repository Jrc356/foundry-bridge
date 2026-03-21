import logging
import os


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds background colors to log lines."""

    # ANSI color codes - subtle muted backgrounds
    COLORS = {
        "DEBUG": "\033[100m",  # Bright black/dark gray background
        "INFO": "\033[48;5;17m",  # Very dark blue background
        "WARNING": "\033[48;5;58m",  # Very dark yellow/brown background
        "ERROR": "\033[48;5;88m",  # Medium dark red background
        "CRITICAL": "\033[48;5;88m",  # Medium dark red background
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        color_code = self.COLORS.get(levelname, "")
        formatted = super().format(record)
        if color_code:
            formatted = f"{color_code}{formatted}{self.COLORS['RESET']}"
        return formatted


def setup_logging() -> None:
    """Configure the root logger from the LOG_LEVEL env var (default: INFO).
    
    Colors are enabled by default (LOG_COLOR=true), and can be disabled with LOG_COLOR=false.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Check if colors are enabled (default: true)
    use_colors = os.environ.get("LOG_COLOR", "true").lower() in ("true", "1", "yes")

    # Create formatter
    format_string = "%(asctime)s\t%(levelname)s\t[%(name)s]\t%(message)s"
    if use_colors:
        formatter = ColoredFormatter(format_string)
    else:
        formatter = logging.Formatter(format_string)

    # Clear any existing handlers
    logging.root.handlers.clear()
    
    # Configure root logger
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
