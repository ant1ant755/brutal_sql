"""Checks that pyproject.toml declares the expected dependency layout."""

import re
import tomllib
from pathlib import Path

import pytest

PYPROJECT_PATH = Path(__file__).with_name("pyproject.toml")


def normalize_package_name(name: str) -> str:
    """Normalize a package name per PEP 503 (lowercase; runs of -_. become -)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_package_names(requirements: list[str]) -> set[str]:
    """Return normalized package names (no extras or versions) from requirements."""
    return {
        normalize_package_name(re.split(r"[\s\[(<>=]", item, maxsplit=1)[0])
        for item in requirements
    }


@pytest.fixture(scope="module")
def pyproject() -> dict:
    """Parsed pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as file:
        return tomllib.load(file)


def test_main_dependencies_are_declared(pyproject: dict) -> None:
    main_packages = read_package_names(pyproject["project"]["dependencies"])
    assert {"streamlit", "sqlalchemy", "psycopg"} <= main_packages


def test_pytest_is_a_dev_dependency(pyproject: dict) -> None:
    dev_packages = read_package_names(pyproject["dependency-groups"]["dev"])
    assert "pytest" in dev_packages


def test_pytest_is_not_a_main_dependency(pyproject: dict) -> None:
    main_packages = read_package_names(pyproject["project"]["dependencies"])
    assert "pytest" not in main_packages


def test_lock_file_exists() -> None:
    assert PYPROJECT_PATH.with_name("poetry.lock").is_file()


def test_read_package_names_strips_extras_and_versions() -> None:
    names = read_package_names(["psycopg[binary] (>=3.3,<4.0)", "black (>=26)"])
    assert names == {"psycopg", "black"}


def test_read_package_names_normalizes_case_and_separators() -> None:
    names = read_package_names(
        ["SQLAlchemy (>=2.1)", "Typing_Extensions", "zope.interface"]
    )
    assert names == {"sqlalchemy", "typing-extensions", "zope-interface"}


def test_normalize_package_name_collapses_separator_runs() -> None:
    assert normalize_package_name("Foo__Bar.-Baz") == "foo-bar-baz"


def test_normalize_package_name_leaves_normalized_name_unchanged() -> None:
    assert normalize_package_name("streamlit") == "streamlit"


def test_read_package_names_of_empty_list_is_empty() -> None:
    assert read_package_names([]) == set()
