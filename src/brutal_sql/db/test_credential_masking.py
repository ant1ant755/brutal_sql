"""Tests for masking database credentials in text."""

import pytest

from brutal_sql.db.connection_settings import ConnectionSettings
from brutal_sql.db.credential_masking import MASK, mask_credentials

SECRET_USER = "fakeuserfakeuser"
SECRET_PASSWORD = "fakepasswordfakepassword"


def make_settings(username: str | None, password: str | None) -> ConnectionSettings:
    return ConnectionSettings("db.local", 5432, "shop", "public", username, password)


def assert_no_credentials(text: str) -> None:
    leaked = SECRET_USER in text or SECRET_PASSWORD in text
    assert not leaked, "masked text still contains a username or password"


def test_masks_username_and_password_in_driver_text() -> None:
    text = (
        f'password authentication failed for user "{SECRET_USER}" '
        f"(tried {SECRET_PASSWORD})"
    )
    masked = mask_credentials(text, make_settings(SECRET_USER, SECRET_PASSWORD))
    assert_no_credentials(masked)
    assert f'user "{MASK}"' in masked


def test_masks_credentials_inside_any_url() -> None:
    text = "failed: postgresql+psycopg://someone:hunter2@db.local:5432/shop"
    masked = mask_credentials(text, make_settings(None, None))
    assert "someone" not in masked and "hunter2" not in masked, "URL creds leaked"
    assert f"postgresql+psycopg://{MASK}@db.local:5432/shop" in masked


def test_leaves_text_without_credentials_unchanged() -> None:
    text = 'database "shop" does not exist'
    settings = make_settings(SECRET_USER, SECRET_PASSWORD)
    assert mask_credentials(text, settings) == text


def test_empty_credentials_change_nothing() -> None:
    text = "connection refused"
    assert mask_credentials(text, make_settings("", "")) == text


def test_rejects_non_string_text() -> None:
    with pytest.raises(TypeError):
        mask_credentials(None, make_settings(None, None))  # type: ignore[arg-type]
