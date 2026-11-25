"""Remove database usernames and passwords from text before it is shown."""

import re

from brutal_sql.db.connection_settings import ConnectionSettings

MASK = "***"
URL_CREDENTIALS = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")


def mask_credentials(text: str, settings: ConnectionSettings) -> str:
    """Return text with any URL credentials and the settings' secrets masked.

    Example: 'password authentication failed for user "alice"' becomes
    'password authentication failed for user "***"'.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")
    masked = URL_CREDENTIALS.sub(rf"\g<scheme>{MASK}@", text)
    for secret in (settings.password, settings.username):
        if secret:
            masked = masked.replace(secret, MASK)
    return masked
