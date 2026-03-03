import logging
import sys
from typing import Optional, TextIO

import colorlog

LOG_FORMAT = (
    "%(white)s%(asctime)s %(log_color)s[%(levelname)s] "
    "%(cyan)s%(name)s%(reset)s: %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_COLORS = {
    "DEBUG": "thin_cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


def setup_logging(
    logger_name: Optional[str] = None,
    level: int = logging.INFO,
    stream: Optional[TextIO] = None,
    propagate: Optional[bool] = None,
) -> logging.Logger:
    """
    Configure colorized logging for a logger.

    Args:
        logger_name: Logger name to configure. If None, configures root logger.
        level: Log level to apply.
        stream: Output stream for logs. Defaults to sys.stdout.
        propagate: Optional propagate override for the configured logger.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    has_configured_handler = any(
        getattr(handler, "_compliance_color_handler", False)
        for handler in logger.handlers
    )
    if not has_configured_handler:
        handler = colorlog.StreamHandler(stream or sys.stdout)
        formatter = colorlog.ColoredFormatter(
            fmt=LOG_FORMAT,
            datefmt=DATE_FORMAT,
            log_colors=LOG_COLORS,
        )
        handler.setFormatter(formatter)
        setattr(handler, "_compliance_color_handler", True)
        logger.addHandler(handler)

    if propagate is not None:
        logger.propagate = propagate

    return logger
