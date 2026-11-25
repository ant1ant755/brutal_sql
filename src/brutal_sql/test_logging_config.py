"""Tests for the project logging setup."""

import logging

import pytest

from brutal_sql.logging_config import configure_logging


@pytest.mark.parametrize("level", ["DEBUG", "info", "Warning"])
def test_configure_logging_sets_root_level(level: str) -> None:
    configure_logging(level)
    assert logging.getLogger().level == logging.getLevelName(level.upper())


def test_configure_logging_defaults_to_info() -> None:
    configure_logging()
    assert logging.getLogger().level == logging.INFO


@pytest.mark.parametrize("level", ["LOUD", "", 10, None])
def test_configure_logging_rejects_unknown_level(level: object) -> None:
    with pytest.raises(ValueError):
        configure_logging(level)  # type: ignore[arg-type]
