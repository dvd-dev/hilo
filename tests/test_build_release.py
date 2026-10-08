"""Unit tests for scripts/build_release.py."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

import pytest

from scripts.build_release import (
    _build_release_zip,
    _clean_version_from_tag,
    _get_next_version_name,
    main,
)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v2026.10.1", "2026.10.1"),
        ("2026.10.1", "2026.10.1"),
        ("v2026.10.1b2", "2026.10.1b2"),
        ("v2025.5.12", "2025.5.12"),
    ],
)
def test_clean_version_from_tag_valid(tag: str, expected: str) -> None:
    assert _clean_version_from_tag(tag) == expected


@pytest.mark.parametrize(
    "invalid_tag",
    [
        "v1.0.0",
        "invalid",
        "v2026.10",
        "v2026.10.",
        "v2026.10.1rc1",
        "v2026.10.1-beta",
    ],
)
def test_clean_version_from_tag_invalid(invalid_tag: str) -> None:
    with pytest.raises(ValueError, match="must match version format"):
        _clean_version_from_tag(invalid_tag)


@pytest.mark.parametrize(
    ("existing_tags", "expected"),
    [
        ("", "2026.10.1"),
        ("v2026.10.1b1\n", "2026.10.1"),
        ("v2026.10.1\nv2026.10.2\n", "2026.10.3"),
        ("v2026.10.1\nv2026.10.2b1\n", "2026.10.2"),
    ],
)
def test_get_next_version_name(existing_tags: str, expected: str) -> None:
    ref_date = datetime(2026, 10, 5, tzinfo=timezone.utc)
    with patch("subprocess.check_output", return_value=existing_tags):
        assert _get_next_version_name(reference_date=ref_date) == expected


@pytest.fixture
def release_zip(tmp_path: Path) -> zipfile.ZipFile:
    out_zip = tmp_path / "hilo.zip"
    _build_release_zip("2026.10.99", out_zip)
    with zipfile.ZipFile(out_zip) as zf:
        yield zf


def test_build_release_zip_stamps_manifest_version(
    release_zip: zipfile.ZipFile,
) -> None:
    manifest = json.loads(release_zip.read("manifest.json"))
    assert manifest["version"] == "2026.10.99"


def test_build_release_zip_includes_component_files(
    release_zip: zipfile.ZipFile,
) -> None:
    namelist = release_zip.namelist()
    assert "manifest.json" in namelist
    assert "__init__.py" in namelist


@pytest.mark.parametrize("pattern", ["__pycache__", ".pyc", ".DS_Store"])
def test_build_release_zip_excludes_artifacts(
    release_zip: zipfile.ZipFile, pattern: str
) -> None:
    assert not any(pattern in name for name in release_zip.namelist())


def test_main_cli_next_version(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("sys.argv", ["build_release.py", "--next-version"]):
        with patch(
            "scripts.build_release._get_next_version_name", return_value="2026.10.1"
        ):
            assert main() == 0
            assert capsys.readouterr().out.strip() == "2026.10.1"


def test_main_cli_invalid_tag(tmp_path: Path) -> None:
    with patch(
        "sys.argv",
        ["build_release.py", "--tag", "invalid", "--output", str(tmp_path / "out.zip")],
    ):
        assert main() == 1


def test_main_cli_missing_args() -> None:
    with patch("sys.argv", ["build_release.py"]):
        with pytest.raises(SystemExit):
            main()
