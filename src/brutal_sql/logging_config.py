"""Project-wide logging setup."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger with the project format and a level name.

    Raises ValueError for an unknown level name such as "LOUD".
    """
    if not isinstance(level, str):
        raise ValueError(f"log level must be a level name, got {level!r}")
    level_number = logging.getLevelNamesMapping().get(level.upper())
    if level_number is None:
        raise ValueError(f"unknown log level {level!r}")
    logging.basicConfig(level=level_number, format=LOG_FORMAT, force=True)
