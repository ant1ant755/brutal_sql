"""Errors shared across the project."""


class ProcessingError(Exception):
    """Raised when fetching a schema or building its entity graph fails.

    Wraps lower level errors (driver, SQLAlchemy, graph validation) so callers
    handle one type. Messages name a database only by host, port and name.
    """


class SanitizedDriverError(Exception):
    """Stand-in cause for a database driver error, with credentials masked.

    Chained as the cause of a ProcessingError instead of the raw driver error,
    so tracebacks never print a username or password.
    """
