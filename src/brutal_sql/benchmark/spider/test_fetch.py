"""Tests for fetching the Spider archive, using a small fake archive (no network)."""

import hashlib
import subprocess
import urllib.error
import zipfile
from pathlib import Path

import pytest

from brutal_sql.benchmark.spider.fetch import (
    MARKER_FILE_NAME,
    REPOSITORY_ROOT,
    ArchiveSource,
    SpiderFetchError,
    download_file,
    fetch_spider,
    sha256_of_file,
    unpack_archive,
    verify_archive,
)

FAKE_ENTRIES = {
    "spider_data/tables.json": "[]",
    "spider_data/database/shop/shop.sqlite": "not really sqlite",
    "__MACOSX/spider_data/._tables.json": "mac metadata",
    "spider_data/.DS_Store": "finder metadata",
}


def make_fake_archive(path: Path, entries: dict[str, str] = FAKE_ENTRIES) -> str:
    """Write a zip with entries to path and return its SHA-256."""
    with zipfile.ZipFile(path, "w") as zip_file:
        for name, text in entries.items():
            zip_file.writestr(name, text)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeDownloader:
    """Copies a local archive instead of downloading, and counts calls."""

    def __init__(self, archive: Path) -> None:
        self.archive = archive
        self.calls = 0

    def __call__(self, url: str, destination: Path) -> None:
        self.calls += 1
        destination.write_bytes(self.archive.read_bytes())


def file_hashes(directory: Path) -> dict[str, str]:
    """Return relative path -> SHA-256 for every file under directory."""
    return {
        str(path.relative_to(directory)): sha256_of_file(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


@pytest.fixture
def fake_source(tmp_path: Path) -> tuple[ArchiveSource, FakeDownloader]:
    """A source pointing at a fake archive, with a downloader that copies it."""
    archive = tmp_path / "upstream.zip"
    sha256 = make_fake_archive(archive)
    source = ArchiveSource("https://example.invalid/spider.zip", sha256, "spider.zip")
    return source, FakeDownloader(archive)


def test_fetch_unpacks_data_and_skips_mac_metadata(
    tmp_path: Path, fake_source: tuple[ArchiveSource, FakeDownloader]
) -> None:
    source, downloader = fake_source
    data = fetch_spider(tmp_path / "data", source, downloader)
    assert (data / "spider_data" / "tables.json").read_text() == "[]"
    assert (data / "spider_data" / "database" / "shop" / "shop.sqlite").is_file()
    assert not (data / "__MACOSX").exists()
    assert not (data / "spider_data" / ".DS_Store").exists()
    assert (data / MARKER_FILE_NAME).read_text().strip() == source.sha256


def test_second_run_skips_download_and_keeps_same_files(
    tmp_path: Path, fake_source: tuple[ArchiveSource, FakeDownloader]
) -> None:
    source, downloader = fake_source
    data = fetch_spider(tmp_path / "data", source, downloader)
    first = file_hashes(data)
    fetch_spider(tmp_path / "data", source, downloader)
    assert downloader.calls == 1
    assert file_hashes(data) == first


def test_existing_archive_is_verified_and_unpacked_without_download(
    tmp_path: Path, fake_source: tuple[ArchiveSource, FakeDownloader]
) -> None:
    source, downloader = fake_source
    data = tmp_path / "data"
    data.mkdir()
    (data / source.file_name).write_bytes(downloader.archive.read_bytes())
    fetch_spider(data, source, downloader)
    assert downloader.calls == 0
    assert (data / "spider_data" / "tables.json").is_file()


def test_wrong_hash_stops_with_clear_error(
    tmp_path: Path, fake_source: tuple[ArchiveSource, FakeDownloader]
) -> None:
    source, downloader = fake_source
    wrong = ArchiveSource(source.url, "0" * 64, source.file_name)
    data = tmp_path / "data"
    with pytest.raises(SpiderFetchError, match=f"SHA-256 {source.sha256}.*expected 0"):
        fetch_spider(data, wrong, downloader)
    assert not (data / source.file_name).exists()
    assert not (data / MARKER_FILE_NAME).exists()
    assert not (data / "spider_data").exists()


def test_marker_with_other_hash_triggers_a_new_fetch(
    tmp_path: Path, fake_source: tuple[ArchiveSource, FakeDownloader]
) -> None:
    source, downloader = fake_source
    data = tmp_path / "data"
    data.mkdir()
    (data / MARKER_FILE_NAME).write_text("stale\n")
    fetch_spider(data, source, downloader)
    assert downloader.calls == 1


def test_verify_archive_accepts_matching_hash(tmp_path: Path) -> None:
    archive = tmp_path / "a.zip"
    sha256 = make_fake_archive(archive)
    verify_archive(archive, sha256)
    assert archive.is_file()


def test_unpack_rejects_entry_outside_destination(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    make_fake_archive(archive, {"../escaped.txt": "x"})
    with pytest.raises(SpiderFetchError, match="points outside"):
        unpack_archive(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_unpack_rejects_a_file_that_is_not_a_zip(tmp_path: Path) -> None:
    archive = tmp_path / "broken.zip"
    archive.write_text("not a zip")
    with pytest.raises(zipfile.BadZipFile):
        unpack_archive(archive, tmp_path / "out")


def test_sha256_of_file_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    path.write_bytes(b"spider")
    assert sha256_of_file(path) == hashlib.sha256(b"spider").hexdigest()


def test_sha256_of_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sha256_of_file(tmp_path / "absent.zip")


def test_download_file_copies_url_contents(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    destination = tmp_path / "copy.bin"
    download_file(source.as_uri(), destination)
    assert destination.read_bytes() == b"payload"
    assert not (tmp_path / "copy.bin.part").exists()


def test_download_failure_names_the_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(url: str, timeout: int) -> None:
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(SpiderFetchError, match="downloading https://x.invalid/a"):
        download_file("https://x.invalid/a", tmp_path / "a.zip")
    assert not (tmp_path / "a.zip.part").exists()


@pytest.mark.parametrize(
    "path", ["data/spider/spider_data.zip", "data/spider/spider_data/tables.json"]
)
def test_spider_files_are_ignored_by_git(path: str) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", path], cwd=REPOSITORY_ROOT, check=False
    )
    assert result.returncode == 0, f"{path} is not gitignored"
