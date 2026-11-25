"""Tests for connection settings built directly or from a Postgres URL."""

import pytest

from brutal_sql.db.connection_settings import (
    ConnectionSettings,
    connection_settings_from_url,
)
from brutal_sql.errors import ProcessingError

SECRET_USER = "fakeuserfakeuser"
SECRET_PASSWORD = "fakepasswordfakepassword"
URL_WITH_CREDENTIALS = (
    f"postgresql://{SECRET_USER}:{SECRET_PASSWORD}@db.local:6543/shop"
)


def assert_no_credentials(text: str) -> None:
    leaked = SECRET_USER in text or SECRET_PASSWORD in text
    assert not leaked, "text contains a database username or password"


def make_settings(**changes: object) -> ConnectionSettings:
    values: dict[str, object] = {
        "host": "db.local",
        "port": 6543,
        "database": "shop",
        "schema_name": "public",
        "username": SECRET_USER,
        "password": SECRET_PASSWORD,
    }
    values.update(changes)
    return ConnectionSettings(**values)  # type: ignore[arg-type]


def test_settings_describe_database_as_host_port_name() -> None:
    assert make_settings().describe_database() == "db.local:6543/shop"


def test_settings_repr_and_str_hide_credentials() -> None:
    settings = make_settings()
    assert_no_credentials(repr(settings))
    assert_no_credentials(str(settings))
    assert_no_credentials(settings.describe_database())


def test_settings_build_psycopg_url() -> None:
    url = make_settings().to_sqlalchemy_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.host, url.port, url.database) == ("db.local", 6543, "shop")
    assert SECRET_PASSWORD not in repr(url), "URL repr shows the password"


@pytest.mark.parametrize(
    "changes",
    [
        {"host": ""},
        {"database": "  "},
        {"schema_name": ""},
        {"port": 0},
        {"port": 70000},
        {"port": "5432"},
        {"port": True},
    ],
)
def test_settings_reject_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(ProcessingError):
        make_settings(**changes)


def test_from_url_reads_credentials_from_url() -> None:
    settings = connection_settings_from_url(URL_WITH_CREDENTIALS, "sales")
    assert settings.describe_database() == "db.local:6543/shop"
    assert settings.schema_name == "sales"
    assert (settings.username, settings.password) == (SECRET_USER, SECRET_PASSWORD)


def test_from_url_explicit_credentials_override_url() -> None:
    settings = connection_settings_from_url(
        URL_WITH_CREDENTIALS, "sales", username="other", password="other-pw"
    )
    assert (settings.username, settings.password) == ("other", "other-pw")


def test_from_url_without_credentials_or_port_uses_defaults() -> None:
    settings = connection_settings_from_url("postgresql+psycopg://db.local/shop", "s")
    assert settings.port == 5432
    assert settings.username is None and settings.password is None


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        f"mysql://{SECRET_USER}:{SECRET_PASSWORD}@db.local/shop",
        f"postgresql://{SECRET_USER}:{SECRET_PASSWORD}@db.local:notaport/shop",
        f"postgresql://{SECRET_USER}:{SECRET_PASSWORD}@db.local:6543/",
        "postgresql:///shop",
    ],
)
def test_from_url_rejects_bad_urls_without_leaking(url: str) -> None:
    with pytest.raises(ProcessingError) as caught:
        connection_settings_from_url(url, "public")
    assert_no_credentials(str(caught.value))
    assert_no_credentials(str(caught.value.__cause__ or ""))


def test_from_url_rejects_non_string_url() -> None:
    with pytest.raises(ProcessingError):
        connection_settings_from_url(None, "public")  # type: ignore[arg-type]
