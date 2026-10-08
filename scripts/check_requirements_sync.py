#!/usr/bin/env python3
"""Check that manifest.json requirements match the pins in pyproject.toml.

Home Assistant installs the integration's dependencies from manifest.json,
while tests and the dev environment use pyproject.toml / uv.lock. Dependabot
only bumps pyproject.toml, so the two can silently drift apart.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "custom_components" / "hilo" / "manifest.json"
PYPROJECT = ROOT / "pyproject.toml"


def _normalize_package_name(requirement: str) -> str:
    """Return the normalized (PEP 503) distribution name of a requirement."""
    name = re.split(r"[\s\[<>=!~;@]", requirement, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def _normalize_specifier(requirement: str) -> str:
    """Strip all whitespace from a requirement string for comparison."""
    return re.sub(r"\s+", "", requirement)


def _find_requirement_mismatches(
    manifest_path: Path, pyproject_path: Path
) -> list[str]:
    """Compare dependencies between manifest.json and pyproject.toml.

    Returns a list of error description strings if any requirements are missing
    or have mismatched version pins.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    pyproject_reqs: dict[str, set[str]] = {}
    groups = [pyproject.get("project", {}).get("dependencies", [])]
    groups += pyproject.get("project", {}).get("optional-dependencies", {}).values()
    groups += pyproject.get("dependency-groups", {}).values()
    for group in groups:
        for req in group:
            if isinstance(req, str):  # Skip {include-group = "..."} entries.
                pyproject_reqs.setdefault(_normalize_package_name(req), set()).add(
                    _normalize_specifier(req)
                )

    errors = []
    for req in manifest.get("requirements", []):
        pkg_name = _normalize_package_name(req)
        found = pyproject_reqs.get(pkg_name)
        if not found:
            errors.append(f"'{req}' is not declared in pyproject.toml")
        elif found != {_normalize_specifier(req)}:
            errors.append(
                f"'{req}' in manifest.json does not match pyproject.toml: "
                + ", ".join(sorted(found))
            )

    return errors


def main() -> int:
    """Entry point for checking requirement synchronization."""
    errors = _find_requirement_mismatches(MANIFEST, PYPROJECT)
    for error in errors:
        print(f"{MANIFEST.relative_to(ROOT)}: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
