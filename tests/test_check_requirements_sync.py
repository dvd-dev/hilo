"""Unit tests for scripts/check_requirements_sync.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_requirements_sync import (
    MANIFEST,
    PYPROJECT,
    _find_requirement_mismatches,
    _normalize_package_name,
    _normalize_specifier,
)


@pytest.mark.parametrize(
    ("req", "expected"),
    [
        ("python-hilo==2026.9.1", "python-hilo"),
        ("python_hilo>=1.0", "python-hilo"),
        ("PyYAML>=6.0.2", "pyyaml"),
        ("pytest-cov", "pytest-cov"),
    ],
)
def test_normalize_package_name(req: str, expected: str) -> None:
    assert _normalize_package_name(req) == expected


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("python-hilo == 2026.9.1", "python-hilo==2026.9.1"),
        ("pyyaml >= 6.0", "pyyaml>=6.0"),
    ],
)
def test_normalize_specifier(spec: str, expected: str) -> None:
    assert _normalize_specifier(spec) == expected


def test_repository_requirements_are_in_sync() -> None:
    assert _find_requirement_mismatches(MANIFEST, PYPROJECT) == []


def test_find_mismatches_no_errors(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    pyproject = tmp_path / "pyproject.toml"

    manifest.write_text(
        json.dumps({"requirements": ["python-hilo==2026.9.1"]}),
        encoding="utf-8",
    )
    pyproject.write_text(
        '[project]\ndependencies = ["python-hilo==2026.9.1"]\n',
        encoding="utf-8",
    )

    assert _find_requirement_mismatches(manifest, pyproject) == []


@pytest.mark.parametrize(
    ("manifest_reqs", "pyproject_reqs", "expected_error"),
    [
        (
            ["python-hilo==2026.9.1"],
            ["python-hilo==2026.9.2"],
            "does not match pyproject.toml",
        ),
        (
            ["python-hilo==2026.9.1"],
            ["requests>=2.0"],
            "is not declared in pyproject.toml",
        ),
    ],
)
def test_find_mismatches_detects_errors(
    tmp_path: Path,
    manifest_reqs: list[str],
    pyproject_reqs: list[str],
    expected_error: str,
) -> None:
    manifest = tmp_path / "manifest.json"
    pyproject = tmp_path / "pyproject.toml"

    manifest.write_text(json.dumps({"requirements": manifest_reqs}), encoding="utf-8")
    deps = ", ".join(f'"{r}"' for r in pyproject_reqs)
    pyproject.write_text(f"[project]\ndependencies = [{deps}]\n", encoding="utf-8")

    errors = _find_requirement_mismatches(manifest, pyproject)
    assert len(errors) == 1
    assert expected_error in errors[0]


def test_find_mismatches_with_optional_dependencies(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    pyproject = tmp_path / "pyproject.toml"

    manifest.write_text(
        json.dumps({"requirements": ["python-hilo==2026.9.1"]}),
        encoding="utf-8",
    )
    pyproject.write_text(
        '[project.optional-dependencies]\nextra = ["python-hilo==2026.9.1"]\n',
        encoding="utf-8",
    )

    assert _find_requirement_mismatches(manifest, pyproject) == []
