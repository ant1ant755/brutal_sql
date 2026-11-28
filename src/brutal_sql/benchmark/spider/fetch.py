"""Download the Spider dataset into the gitignored data/spider folder.

Run from anywhere in the repository::

    poetry run python -m brutal_sql.benchmark.spider.fetch [--data-dir DIR]

The archive's SHA-256 is pinned below (see SOURCE.md). A second run finds the
marker file and does nothing; if only the archive is there, it is re-checked and
unpacked without downloading again.
"""

import argparse
import hashlib
import logging
import shutil
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from brutal_sql.errors import ProcessingError
from brutal_sql.logging_config import configure_logging

logger = logging.getLogger(__name__)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIRECTORY = REPOSITORY_ROOT / "data" / "spider"
MARKER_FILE_NAME = ".fetched"
SKIPPED_ARCHIVE_ENTRIES = ("__MACOSX/",)
SKIPPED_FILE_NAMES = (".DS_Store",)
CHUNK_SIZE = 1024 * 1024


class SpiderFetchError(ProcessingError):
    """Raised when the Spider archive can't be downloaded, verified or unpacked."""


@dataclass(frozen=True)
class ArchiveSource:
    """Where to download an archive from and the SHA-256 it must have."""

    url: str
    sha256: str
    file_name: str


SPIDER_SOURCE = ArchiveSource(
    url=(
        "https://drive.usercontent.google.com/download"
        "?id=1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J&export=download&confirm=t"
    ),
    sha256="00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b",
    file_name="spider_data.zip",
)

Downloader = Callable[[str, Path], None]


def sha256_of_file(path: Path) -> str:
    """Return the hex SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    """Download url to destination via a .part file, renamed when complete."""
    partial = destination.with_name(destination.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            with partial.open("wb") as output:
                shutil.copyfileobj(response, output, CHUNK_SIZE)
    except (urllib.error.URLError, TimeoutError) as error:
        partial.unlink(missing_ok=True)
        raise SpiderFetchError(f"downloading {url} failed: {error}") from error
    partial.replace(destination)


def verify_archive(path: Path, expected_sha256: str) -> None:
    """Raise SpiderFetchError (and delete the file) if its hash is not expected."""
    actual = sha256_of_file(path)
    if actual != expected_sha256:
        path.unlink()
        raise SpiderFetchError(
            f"{path.name} has SHA-256 {actual}, expected {expected_sha256}; "
            "the file was deleted. If the source changed on purpose, update "
            "SPIDER_SOURCE and SOURCE.md."
        )


def _is_skipped(name: str) -> bool:
    """True for macOS metadata entries that carry no data."""
    return name.startswith(SKIPPED_ARCHIVE_ENTRIES) or (
        PurePosixPath(name).name in SKIPPED_FILE_NAMES
    )


def _require_inside(name: str, destination: Path) -> None:
    """Raise SpiderFetchError if an entry would be written outside destination."""
    target = (destination / name).resolve()
    if not target.is_relative_to(destination.resolve()):
        raise SpiderFetchError(f"archive entry {name!r} points outside {destination}")


def unpack_archive(archive: Path, destination: Path) -> None:
    """Extract every data entry of a zip archive into destination."""
    with zipfile.ZipFile(archive) as zip_file:
        members = [name for name in zip_file.namelist() if not _is_skipped(name)]
        for name in members:
            _require_inside(name, destination)
        zip_file.extractall(destination, members=members)


def fetch_spider(
    data_directory: Path = DEFAULT_DATA_DIRECTORY,
    source: ArchiveSource = SPIDER_SOURCE,
    download: Downloader = download_file,
) -> Path:
    """Make sure the verified, unpacked archive is in data_directory; return it.

    Skips everything when the marker file records the expected hash, and skips
    the download when the archive is already there.
    """
    marker = data_directory / MARKER_FILE_NAME
    if marker.is_file() and marker.read_text().strip() == source.sha256:
        logger.info("Spider already fetched into %s; nothing to do", data_directory)
        return data_directory
    data_directory.mkdir(parents=True, exist_ok=True)
    archive = data_directory / source.file_name
    if not archive.is_file():
        logger.info("Downloading %s", source.url)
        download(source.url, archive)
    verify_archive(archive, source.sha256)
    unpack_archive(archive, data_directory)
    marker.write_text(source.sha256 + "\n")
    logger.info("Spider unpacked into %s", data_directory)
    return data_directory


def main(arguments: list[str] | None = None) -> None:
    """Command line entry point: fetch Spider into --data-dir."""
    parser = argparse.ArgumentParser(description="Download the Spider dataset.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIRECTORY)
    configure_logging()
    fetch_spider(parser.parse_args(arguments).data_dir)


if __name__ == "__main__":
    main()
