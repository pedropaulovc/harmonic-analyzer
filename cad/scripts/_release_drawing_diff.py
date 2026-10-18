"""Published-release PDF inventory for the separate drawing-diff asset.

Only ZIP metadata and selected PDF members are fetched. Authentication, HTTP,
archive and identity errors are fatal: they are not an empty first release.
"""

from __future__ import annotations

import importlib.util
import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

_VERSION = re.compile(r"v([1-9]\d*)\Z")
_TOOLS = Path(__file__).resolve().parents[1] / "comparisons" / "tools"


def previous_published_release(
    version: str, repo: str, gh: Callable[..., str]
) -> dict[str, Any] | None:
    """Highest published compact release below the target, not an orphan tag.

    Fetch every page: GitHub lists by creation date, not numeric CAD revision.
    A draft, prerelease or malformed API response must never become a baseline.
    """
    current = _VERSION.fullmatch(version)
    if current is None:
        raise ValueError(f"invalid drawing-diff release version: {version!r}")
    candidates: dict[int, dict[str, Any]] = {}
    page = 1
    while True:
        releases = json.loads(gh("api", f"repos/{repo}/releases?per_page=100&page={page}"))
        if not isinstance(releases, list):
            raise ValueError("GitHub releases API did not return a release list")
        for release in releases:
            if not isinstance(release, dict):
                raise ValueError("GitHub releases API returned a malformed release")
            tag = release.get("tag_name")
            if (
                not isinstance(tag, str)
                or not isinstance(release.get("draft"), bool)
                or not isinstance(release.get("prerelease"), bool)
            ):
                raise ValueError("GitHub release is missing tag/draft/prerelease metadata")
            match = _VERSION.fullmatch(tag)
            if release["draft"] or release["prerelease"] or match is None:
                continue
            if not isinstance(release.get("published_at"), str):
                raise ValueError(f"published GitHub release {tag} has no publication date")
            number = int(match[1])
            if number < int(current[1]):
                if number in candidates:
                    raise ValueError(f"duplicate published GitHub release {tag}")
                candidates[number] = release
        if len(releases) < 100:
            break
        page += 1
    return candidates[max(candidates)] if candidates else None


def extract_release_pdfs(release: dict[str, Any], destination: Path) -> Path:
    """Extract actual ``pdf/**/*.pdf`` members without flattening identities.

    The existing comparison tool owns ZIP/ZIP64 range parsing and decompression.
    This consumer additionally rejects unsafe or case-ambiguous PDF names before
    writing any member, including Windows drive/ADS and reserved device names.
    A valid historical bundle with no PDFs is a genuine empty drawing baseline;
    a missing CAD asset or unreadable archive is not.
    """
    tag = release["tag_name"]
    expected = f"harmonic-analyzer-{tag}.zip"
    assets = release.get("assets")
    if not isinstance(assets, list) or any(not isinstance(asset, dict) for asset in assets):
        raise ValueError(f"published release {tag} has malformed asset metadata")
    matches = [asset for asset in assets if asset.get("name") == expected]
    if len(matches) != 1:
        raise ValueError(f"published release {tag} must have exactly one {expected} asset")
    url = matches[0].get("browser_download_url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError(f"published release {tag} has no HTTPS CAD asset URL")

    spec = importlib.util.spec_from_file_location("_drawing_release_zip", _TOOLS / "release_diff.py")
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    directory = reader.central_dir(url)
    selected: dict[str, tuple[PurePosixPath, dict[str, Any]]] = {}
    for name, entry in directory.items():
        if not name.lower().replace("\\", "/").startswith("pdf/") or not name.lower().endswith(".pdf"):
            continue
        components = name.split("/")
        if (
            "\\" in name
            or any(
                part in ("", ".", "..")
                or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                or part.endswith((" ", "."))
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                for part in components
            )
        ):
            raise ValueError(f"unsafe release PDF member: {name!r}")
        relative = PurePosixPath(*components[1:])
        identity = relative.as_posix().casefold()
        if identity in selected:
            raise ValueError(f"duplicate release PDF identity: {name!r}")
        selected[identity] = (relative, entry)

    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    for relative, entry in selected.values():
        target = destination.joinpath(*relative.parts)
        if not target.resolve().is_relative_to(root):
            raise ValueError(f"release PDF member escapes destination: {entry['name']!r}")
        reader.extract(url, entry, target)
    return destination
