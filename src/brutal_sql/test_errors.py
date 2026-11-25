"""Tests for the project-wide error types."""

import pytest

from brutal_sql.errors import ProcessingError, SanitizedDriverError


def test_processing_error_keeps_its_cause() -> None:
    cause = SanitizedDriverError("OperationalError: connection refused")
    with pytest.raises(ProcessingError) as caught:
        raise ProcessingError("reading failed") from cause
    assert caught.value.__cause__ is cause
    assert str(caught.value) == "reading failed"


def test_processing_error_is_not_a_value_error() -> None:
    assert not issubclass(ProcessingError, ValueError)
    with pytest.raises(ProcessingError):
        raise ProcessingError("boom")
