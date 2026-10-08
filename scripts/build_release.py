#!/usr/bin/env python3
"""Package the Hilo custom component into a HACS-compatible release zip."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

# Pattern for Home Assistant-style Calendar Versioning: YYYY.M.N (e.g. 2026.10.1)
# with an optional pre-release suffix (e.g. 2026.10.1b1).
VERSION_PATTERN = re.compile(r"^[0-9]{4}\.[0-9]{1,2}\.[0-9]+(b[0-9]+)?$")
ROOT = Path(__file__).resolve().parent.parent
COMPONENT_DIR = ROOT / "custom_components" / "hilo"
EXCLUDED_NAMES = {".DS_Store"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _clean_version_from_tag(tag: str) -> str:
    """Validate a release tag and strip the leading 'v' prefix.

    Raises ValueError if the tag does not follow the expected version format.
    """
    version = tag.removeprefix("v")
    if not VERSION_PATTERN.match(version):
        raise ValueError(
            f"Release tag '{tag}' must match version format vYYYY.M.N "
            "(e.g. v2026.10.1 or v2026.10.1b1)"
        )
    return version


def _get_next_version_name(reference_date: datetime | None = None) -> str:
    """Calculate the next version name (YYYY.M.N) from existing git tags.

    Inspects git tags for the current UTC year and month. If tags exist, increments
    the highest patch number; otherwise starts at patch 1 (e.g. 2026.10.1).
    """
    now = reference_date or datetime.now(timezone.utc)
    prefix = f"{now.year}.{now.month}"

    try:
        output = subprocess.check_output(
            ["git", "tag", "--list", f"v{prefix}.*"],
            cwd=ROOT,
            text=True,
        )
        tags = output.splitlines()
    except (subprocess.SubprocessError, FileNotFoundError):
        tags = []

    # Only match stable tags so that pre-releases (e.g. v2026.10.1b1)
    # do not prematurely advance the stable version they are preparing (v2026.10.1).
    pattern = re.compile(rf"^v{re.escape(prefix)}\.([0-9]+)$")
    patches = [int(m.group(1)) for tag in tags if (m := pattern.match(tag.strip()))]
    next_patch = max(patches, default=0) + 1
    return f"{prefix}.{next_patch}"


def _build_release_zip(version: str, output_path: Path) -> None:
    """Build a HACS release zip archive containing the component files.

    Stamps the specified version into manifest.json in-memory without
    modifying the workspace on disk. Excludes cache and metadata files.
    """
    manifest_path = COMPONENT_DIR / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing {manifest_path}")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["version"] = version
    stamped_manifest = json.dumps(manifest_data, indent=2) + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(COMPONENT_DIR.rglob("*")):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts:
                continue
            if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
                continue

            rel_path = path.relative_to(COMPONENT_DIR)
            if rel_path == Path("manifest.json"):
                zf.writestr("manifest.json", stamped_manifest)
            else:
                zf.write(path, arcname=str(rel_path))

    print(f"Successfully packaged {output_path} (version: {version})")


def main() -> int:
    """Parse CLI arguments to package a release or display the next version."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--next-version",
        action="store_true",
        help="Print the next version name (e.g. 2026.10.1) and exit",
    )
    parser.add_argument(
        "--tag",
        help="Release tag, e.g. v2026.10.1 or v2026.10.1b1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path where the zip archive should be written",
    )
    args = parser.parse_args()

    if args.next_version:
        print(_get_next_version_name())
        return 0

    if not args.tag or not args.output:
        parser.error("--tag and --output are required when packaging a release")

    try:
        version = _clean_version_from_tag(args.tag)
        _build_release_zip(version, args.output.resolve())
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
