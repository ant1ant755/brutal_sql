"""Where and how to connect to a Postgres schema, without leaking credentials."""

from dataclasses import dataclass, field

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from brutal_sql.errors import ProcessingError

POSTGRES_DRIVER = "postgresql+psycopg"
POSTGRES_BACKENDS = frozenset({"postgresql", "postgres"})
DEFAULT_POSTGRES_PORT = 5432
HIGHEST_PORT = 65535
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5


def _require_text(value: object, field_name: str) -> None:
    """Raise ProcessingError unless value is a string with non-blank text."""
    if not isinstance(value, str) or not value.strip():
        raise ProcessingError(f"{field_name} must be a non-blank string")


def _require_port(port: object) -> None:
    """Raise ProcessingError unless port is an integer from 1 to 65535."""
    if isinstance(port, bool) or not isinstance(port, int):
        raise ProcessingError(f"port must be an integer, got {port!r}")
    if not 1 <= port <= HIGHEST_PORT:
        raise ProcessingError(f"port must be between 1 and {HIGHEST_PORT}")


def _require_connect_timeout(seconds: object) -> None:
    """Raise ProcessingError unless seconds is a positive integer."""
    if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds < 1:
        raise ProcessingError(
            f"connect_timeout_seconds must be a positive integer, got {seconds!r}"
        )


@dataclass(frozen=True)
class ConnectionSettings:
    """Host, port, database and schema to read, plus credentials kept out of repr."""

    host: str
    port: int
    database: str
    schema_name: str
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        _require_text(self.host, "host")
        _require_port(self.port)
        _require_text(self.database, "database")
        _require_text(self.schema_name, "schema_name")
        _require_connect_timeout(self.connect_timeout_seconds)

    def describe_database(self) -> str:
        """Return 'host:port/database', the only form allowed in messages."""
        return f"{self.host}:{self.port}/{self.database}"

    def to_sqlalchemy_url(self) -> URL:
        """Return the SQLAlchemy URL for psycopg 3. Never log or print it."""
        return URL.create(
            POSTGRES_DRIVER,
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        )


def _parse_url(url: str) -> URL:
    """Parse a database URL; errors never repeat the URL text."""
    if not isinstance(url, str) or not url.strip():
        raise ProcessingError("database URL must be a non-blank string")
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError) as error:
        raise ProcessingError("could not parse the database URL") from error
    if parsed.get_backend_name() not in POSTGRES_BACKENDS:
        raise ProcessingError("database URL must be a postgresql:// URL")
    return parsed


def connection_settings_from_url(
    url: str,
    schema_name: str,
    username: str | None = None,
    password: str | None = None,
    connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> ConnectionSettings:
    """Build settings from a Postgres URL; given credentials override the URL's."""
    parsed = _parse_url(url)
    if not parsed.host or not parsed.database:
        raise ProcessingError("database URL must name a host and a database")
    return ConnectionSettings(
        host=parsed.host,
        port=parsed.port or DEFAULT_POSTGRES_PORT,
        database=parsed.database,
        schema_name=schema_name,
        username=username if username is not None else parsed.username,
        password=password if password is not None else parsed.password,
        connect_timeout_seconds=connect_timeout_seconds,
    )
