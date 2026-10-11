"""Source-state identity: Git executable, HEAD sha, build id and commit year.

Separate from ``_part_properties`` so a drawing, which stamps only the
build id, does not fold the part-registry and tolerance stamping code into
its recipe.
"""

from __future__ import annotations

import functools
import shutil
from pathlib import Path

from _paths import CAD_ROOT


@functools.lru_cache(maxsize=1)
def _git_executable() -> str:
    """Absolute Git executable used by fixed, repository-internal commands."""
    executable = shutil.which("git")
    if executable is None:
        raise FileNotFoundError("git executable not found on PATH")
    return str(Path(executable).resolve())


@functools.lru_cache(maxsize=1)
def _git_sha() -> str:
    """Short HEAD sha (+ '-dirty'), for a reproducible Generator stamp.

    Deterministic per source state — no wall-clock — so a rebuild from the same
    commit writes the same property (see Part D determinism decision).
    """
    import subprocess

    try:
        sha = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
            [_git_executable(), "rev-parse", "--short", "HEAD"],
            cwd=str(CAD_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
            [_git_executable(), "status", "--porcelain"],
            cwd=str(CAD_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}"
    except Exception:  # noqa: BLE001 -- not in a git checkout / no git
        return "unknown"


def _build_id() -> str:
    """``<next release>[-dirty]`` -- the release designator, marked when dirty.

    The title block's REV cell is the formal release designator
    (``release.yaml``); a sheet also stamps this on itself
    (``$PRP:{BUILD_ID}``) so a print made from an uncommitted working tree can
    be told from a clean release print by eye.  Source-derived like
    :func:`_git_sha` (no wall clock) and deliberately history-free: only the
    working-tree state is read, never a tag, a commit count or a sha, so a
    shallow checkout -- what every farm leaf clones -- stamps exactly what the
    same commit stamps in a full clone.  Stamped only when a drawing task
    actually runs -- git state is in no cache key or file_dep, so a commit
    never rebuilds anything; a restored sheet keeps the id of the build that
    made it.
    """
    import subprocess

    import _config

    try:
        dirty = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
            [_git_executable(), "status", "--porcelain", "--untracked-files=normal"],
            cwd=str(CAD_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "cannot determine Git working-tree state for the build id"
        ) from exc
    return f"{_config.release_revision()}{'-dirty' if dirty else ''}"


def _git_commit_year() -> str:
    """Year of the HEAD commit, for the title block's copyright line.

    Same determinism rule as :func:`_git_sha`: derived from the source state,
    never the wall clock, so a rebuild from the same commit stamps the same
    year and a cache restore cannot disagree with a fresh build.  Outside a
    git checkout there is no source-derived year, so fail loud rather than
    stamp a guess into every part.
    """
    import subprocess

    date = subprocess.run(  # noqa: S603 -- resolved Git; fixed internal argv
        [_git_executable(), "log", "-1", "--format=%cs"],
        cwd=str(CAD_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    year = date[:4]
    if not (len(year) == 4 and year.isdigit()):
        raise RuntimeError(f"HEAD commit date is not ISO-dated: {date!r}")
    return year
