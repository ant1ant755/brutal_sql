"""UI tests for the Brutal SQL landing page, using Streamlit AppTest."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from brutal_sql.app import APP_TAGLINE, APP_TITLE

APP_PATH = Path(__file__).with_name("app.py")


@pytest.fixture
def landing_page() -> AppTest:
    """Run the app once and return the rendered AppTest."""
    app_test = AppTest.from_file(str(APP_PATH))
    return app_test.run()


def test_landing_page_shows_title(landing_page: AppTest) -> None:
    assert len(landing_page.title) == 1
    assert landing_page.title[0].value == APP_TITLE


def test_landing_page_shows_tagline(landing_page: AppTest) -> None:
    assert landing_page.caption[0].value == APP_TAGLINE


def test_landing_page_title_is_not_empty(landing_page: AppTest) -> None:
    assert landing_page.title[0].value.strip() != ""


def test_landing_page_raises_no_exceptions(landing_page: AppTest) -> None:
    assert len(landing_page.exception) == 0
    assert len(landing_page.error) == 0


def test_missing_app_file_fails_to_load() -> None:
    missing_path = APP_PATH.with_name("does_not_exist.py")
    with pytest.raises(FileNotFoundError):
        AppTest.from_file(str(missing_path))
