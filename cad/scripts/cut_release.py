r"""Cut a tagged release of the harmonic-analyzer and attach its CAD bundle.

doit task: ``release`` (opt-in) -- ``doit release -- [vNN] [--draft]``
forwards args here. Runnable standalone too.


The repository is source-of-truth: ``.SLDPRT/.SLDASM`` are gitignored build
artefacts (Part E). A *release* is therefore the one place a binary snapshot is
published -- a git tag pins the exact source state, and a SolidWorks Pack-and-Go
zip (the top assembly + every referenced part, flattened) is attached to the
matching GitHub release so a consumer can open the model without rebuilding.

What it does, in order:

  1. Resolve the version (``vNN``): explicit positional, or increment the latest
     compact release tag (``v31`` -> ``v32``), and require
     ``cad/config/release.yaml`` to reserve that same CAD Revision.
  2. Pre-flight: tag must not already exist; the committed tree must be clean
     (``--allow-dirty`` to override); harmonic-analyzer.SLDASM must be built.
  3. Stage the bundle. This script opens NO SolidWorks document and needs NO
     seat: ``package_native.py`` (doit task ``package:release``, dispatchable to
     the farm) already ran every Pack-and-Go and left a PREPARED native tree
     under ``cad/out/release/native/`` -- ``solidworks/`` + ``slddrw/`` plus
     ``native-package.json``, the sidecar carrying every COM-derived fact (the
     SolidWorks revision, the referenced-document count, the per-drawing
     members). Here those directories are COPIED in, and the complete
     recipe-keyed neutral set produced by the prerequisite ``export`` task is
     validated and staged: AP214 STEP for every part, fine binary STL for every
     part/assembly plus distinct configurations, and the build-owned isometric
     PNG for every document. Also copies the millimetre
     scene graph (``cad/out/boxes/harmonic-analyzer.json`` from export_models.py)
     so the comparison gallery renders from the bundle with no SolidWorks.
     Everything is staged and zipped into ONE bundle
     ``cad/out/release/harmonic-analyzer-<version>.zip`` (``solidworks/`` native +
     ``step/`` + ``stl/`` + ``boxes/`` + ``png/`` + ``diff/``). Records the SW
     revision. (Build logs ship as a SEPARATE logs asset, not in this zip.)
  4. diff: render the changed-parts highlight (this staged bundle vs the previous
     release, fetched from GitHub) into ``stage/diff`` so it ships in the zip.
  5. git: annotated tag at HEAD, pushed to origin.
  6. gh: create the GitHub release for the tag (auto-generated notes header + our
     provenance block + an inline changed-parts gallery) and upload the bundle,
     the diff PNGs, and a LOGS asset -- the per-task build logs (``cad/out/logs``,
     teed by dodo.py) plus this run's ``*-release.log``, zipped into
     ``<top>-<version>-logs.zip`` when there are several (a lone log goes up
     as-is). ``--no-publish`` runs everything EXCEPT this step (no git tag/push,
     no gh) and just reports the assets it would have uploaded.
  7. Before publication, validate and stage the ``release.yaml`` next-revision
     update. On successful publication, install it atomically and warn the release
     agent to commit and merge that tracked version bump. A failed post-publication
     install reports the published version and required manual ``next_revision``.

Run (no SolidWorks needed -- but ``doit package:release`` must have produced
``cad/out/release/native/`` first, on a seat or on a farm worker):

    uv run python cad\scripts\cut_release.py [vNN] [--allow-dirty] [--draft]

``--draft`` makes the GitHub release a draft (asset uploaded, not published).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from _common import CAD_ROOT, OUT_SLDASM, log
import _config
from _drawing_registry import DRAWINGS
from export_models import stage_release_neutral

import _telemetry

REPO_ROOT = CAD_ROOT.parent
TOP_ASSEMBLY = "harmonic-analyzer"
RELEASE_DIR = CAD_ROOT / "out" / "release"
# Per-task build/verify logs teed by dodo.py:_run (part-*, assembly-*, verify-*,
# check-*). Shipped as a SEPARATE GitHub-release LOGS asset (zipped together with
# this script's own *-release.log when there are several) -- see _logs_asset. Kept
# OUT of the main CAD bundle so they aren't buried in a 100s-of-MB zip.
LOGS_DIR = CAD_ROOT / "out" / "logs"
# Geometry-diff renderer (offscreen pyvista, isolated PEP-723 deps via `uv run`):
# highlights parts whose geometry changed vs the previous release. No SolidWorks.
RENDER_DIFF = CAD_ROOT / "comparisons" / "tools" / "render_diff.py"
# export_models.py render cache: the millimetre scene graph (component transforms
# + per-config mesh keys + colours) that lets a consumer render the bundle with
# cad/comparisons/tools/render_offline.py without SolidWorks.
SCENE_JSON = CAD_ROOT / "out" / "boxes" / f"{TOP_ASSEMBLY}.json"
DRAWING_OUTPUTS = {drawing.name: drawing.outputs for drawing in DRAWINGS}

# Comparison gallery (reference-photo overlays). PRODUCED BY THE ``gallery`` TASK
# (`export_models.py --comparisons`: a SolidWorks-free offline Blender render off
# the stable STLs, which `release` depends on); this module only STAGES the
# result into the bundle's ``cad/comparisons/`` so each release ships an up-to-date
# showcase. The DERIVED refs/renders/composites/scores/index are gitignored +
# regenerable (nothing tracked is touched); the manifest (pose/align source of
# truth) and ATTRIBUTION.md (CC BY credits for the shipped reference imagery) ride
# along so the downloaded bundle is standalone + compliant.
COMPARISONS_DIR = CAD_ROOT / "comparisons"
_GALLERY_STAGE = (
    "ref",
    "render",
    "composite",
    "scores.json",
    "index.html",
    "manifest.json",
    "ATTRIBUTION.md",
)
_VERSION_RE = re.compile(r"^v([1-9]\d*)$")
RELEASE_VERSION_FILE = (CAD_ROOT / "config" / "release.yaml").resolve()

# The prepared native tree + sidecar produced by cad/scripts/package_native.py
# (doit task ``package:release``) -- the release's ONLY SolidWorks work, which is
# why it lives in its own task: it can be dispatched to a farm worker while this
# publisher runs on a machine with no seat. ``PurePosixPath`` everywhere below:
# every path in the sidecar is repo-relative POSIX, written on a worker and read
# here.
NATIVE_PACKAGE_DIR = RELEASE_DIR / "native"
NATIVE_PACKAGE_FILE = NATIVE_PACKAGE_DIR / "native-package.json"
NATIVE_PACKAGE_SCHEMA = 1
_NATIVE_PACKAGE_FIX = "uv run python -m doit package:release"


# --------------------------------------------------------------------------- #
# git / gh helpers (plain subprocess -- no SolidWorks involvement)
# --------------------------------------------------------------------------- #
def _git(*args: str, check_rc: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if check_rc and proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _gh(*args: str) -> str:
    proc = subprocess.run(
        ["gh", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _existing_tags() -> list[int]:
    raw = _git("tag", "--list", "v*").splitlines()
    out: list[int] = []
    for line in raw:
        m = _VERSION_RE.match(line.strip())
        if m:
            out.append(int(m[1]))
    return sorted(out)


def resolve_version(explicit: str | None) -> str:
    """Validate an explicit compact tag, or increment the latest one."""
    if explicit is not None:
        if not _VERSION_RE.match(explicit):
            raise SystemExit(f"!!  version must look like vNN, got {explicit!r}")
        return explicit

    tags = _existing_tags()
    if not tags:
        return "v1"
    return f"v{tags[-1] + 1}"


def configured_revision() -> str:
    """Return the tracked CAD revision reserved for the next release."""
    value = _config.release_revision()
    if not _VERSION_RE.fullmatch(value):
        raise RuntimeError(f"invalid configured CAD revision: {value!r}")
    return value


def require_configured_revision(version: str) -> None:
    """Ensure the release tag matches the revision stamped into native CAD."""
    expected = configured_revision()
    if expected != version:
        raise SystemExit(
            f"!!  release {version} does not match configured CAD Revision {expected}; "
            "update cad/config/release.yaml and rebuild the CAD before cutting it"
        )


class _PreparedRevisionAdvance:
    """A validated next-revision write held until the release is published."""

    def __init__(self, source: Path, temporary: Path, next_version: str) -> None:
        self.source = source
        self.temporary: Path | None = temporary
        self.next_version = next_version

    def commit(self) -> str:
        """Atomically install the prepared revision file."""
        assert self.temporary is not None
        os.replace(self.temporary, self.source)
        self.temporary = None
        return self.next_version

    def discard(self) -> None:
        """Remove an uncommitted prepared revision file."""
        if self.temporary is None:
            return
        try:
            self.temporary.unlink(missing_ok=True)
        except OSError:
            pass
        finally:
            self.temporary = None


def prepare_configured_revision_advance(version: str) -> _PreparedRevisionAdvance:
    """Validate and stage the next revision before publishing the release."""
    require_configured_revision(version)
    next_version = f"v{int(version[1:]) + 1}"
    source = RELEASE_VERSION_FILE
    text = source.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(?m)^(\s*next_revision:\s*)v[1-9]\d*(\s*)$",
        rf"\g<1>{next_version}\g<2>",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"could not advance next_revision in {source}")

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=source.parent,
            prefix=f".{source.name}.",
            suffix=".tmp",
            delete=False,
        ) as target:
            temporary = Path(target.name)
            target.write(updated)
            target.flush()
            os.fsync(target.fileno())
    except OSError as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"could not prepare next_revision update in {source}: {exc}"
        ) from exc
    return _PreparedRevisionAdvance(source, temporary, next_version)


def advance_configured_revision(version: str) -> str:
    """Advance the tracked next-release revision after a published release."""
    prepared = prepare_configured_revision_advance(version)
    try:
        return prepared.commit()
    finally:
        prepared.discard()


def previous_tag(version: str) -> str | None:
    """Highest existing compact tag strictly below ``version`` (or None)."""
    m = _VERSION_RE.match(version)
    assert m is not None, f"previous_tag: version must match vNN, got {version!r}"
    cur = int(m[1])
    prior = [t for t in _existing_tags() if t < cur]
    if not prior:
        return None
    return f"v{prior[-1]}"


def _repo_slug() -> str:
    """``owner/repo`` from the origin remote, for building asset URLs."""
    url = _git("config", "--get", "remote.origin.url", check_rc=False)
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url or "")
    return m.group(1) if m else "pedropaulovc/harmonic-analyzer"


def render_diff(stage: Path, prev_tag: str) -> dict[str, Any]:
    """Render the changed-parts diff (this staged bundle vs the previous release).

    Runs ``cad/comparisons/tools/render_diff.py`` via ``uv run`` (isolated deps): the
    NEW side is this on-disk stage (the release isn't published yet), the OLD side
    is the previous release fetched from GitHub over HTTP ranges. Writes PNGs +
    ``diff_summary.json`` into ``stage/diff`` so they ride inside the bundle zip.
    FATAL: any render error (non-zero exit or missing summary) raises so the
    release is blocked rather than shipping with an empty/absent diff. The diff is
    only skipped *upstream* (caller passes no ``prev_tag``) for the first release.
    """
    diff_dir = stage / "diff"
    summary = diff_dir / "diff_summary.json"
    log(f"rendering changed-parts diff vs {prev_tag} ...")
    # Stream the renderer's stdout line-by-line: the geometry verify (a
    # brute-force Hausdorff per changed mesh) and the per-view render take
    # minutes, so capturing-and-swallowing left the release looking hung.
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            str(RENDER_DIFF),
            "--old-release",
            prev_tag,
            "--new-local",
            str(stage),
            "--out",
            str(diff_dir),
            "--summary-json",
            str(summary),
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    tail: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        log(f"    diff| {line}")
        tail.append(line)
        if len(tail) > 50:
            del tail[0]
    if proc.wait() != 0 or not summary.exists():
        raise RuntimeError(
            f"diff render FAILED (release blocked): {' / '.join(tail)[-400:]}"
        )
    data = json.loads(summary.read_text(encoding="utf-8"))
    data["prev"] = prev_tag
    data["image_paths"] = [diff_dir / n for n in data.get("images", [])]
    log(
        f"diff render: {len(data.get('changed_parts', []))} changed parts, "
        f"{len(data['image_paths'])} views"
    )
    return data


def stage_comparisons(stage: Path) -> dict[str, Any]:
    """Stage the comparison gallery -- PRODUCED BY THE ``gallery`` TASK -- into the
    bundle (``stage/comparisons``), so each release ships an up-to-date "this
    model vs Michelson's ch30 photos" showcase.

    The gallery is refreshed upstream by ``export_models.py --comparisons`` (the
    SolidWorks-free ``gallery`` task: an offline Blender render off the stable
    STLs); here we only COPY the result in. Every gallery output is gitignored +
    regenerable (reference crops included -- re-derived from the pinned
    ``references`` submodule), so nothing TRACKED is staged and the tagged tree
    stays clean.

    Fail loud, NOT best-effort: ``release`` depends on ``gallery``, which exits
    non-zero on any render/composite/scoring fault, so by the time we stage there
    is no legitimate path to a missing, incomplete or stale gallery -- warning and
    shipping anyway would hide a pipeline bug and publish a stale showcase.
    """
    with _telemetry.span("release.comparisons") as sp:
        scores_file = COMPARISONS_DIR / "scores.json"
        # COMPLETE and CURRENT, or the release stops here. A partial gallery
        # (render_offline succeeded but gallery.py/composite died, or an
        # interrupted run left renders without index.html) must not ship: the
        # notes point users at index.html and the reveal slider needs every
        # overlay. Validate the full per-manifest file set + a parseable
        # scores.json covering every pair.
        manifest = json.loads(
            (COMPARISONS_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        ids = [p["id"] for p in manifest["pairs"]]
        required = [COMPARISONS_DIR / "index.html", scores_file]
        for pid in ids:
            required += [
                COMPARISONS_DIR / "render" / f"{pid}.jpg",
                COMPARISONS_DIR / "composite" / f"{pid}_cad.jpg",
                COMPARISONS_DIR / "composite" / f"{pid}_blend.jpg",
                COMPARISONS_DIR / "ref" / f"{pid}.jpg",
            ]
        missing = [
            str(p.relative_to(COMPARISONS_DIR)) for p in required if not p.exists()
        ]
        scores: dict[str, Any] = {}
        if scores_file.exists():
            try:
                scores = json.loads(scores_file.read_text(encoding="utf-8"))
            except ValueError:
                missing.append("scores.json (unparseable)")
        missing += [f"scores.json[{pid}]" for pid in ids if pid not in scores]
        if missing:
            _telemetry.event(
                "comparisons.skipped",
                reason=f"incomplete: {', '.join(missing[:8])}"[:200],
            )
            sp.set_attribute("staged", False)
            raise SystemExit(
                f"!!  comparison gallery absent/incomplete -- {len(missing)} "
                f"missing, e.g. {', '.join(missing[:4])}; the `gallery` task "
                "owns it and fails loud, so this means it never ran (or its "
                "output was deleted) -- regenerate it with "
                "`uv run python -m doit gallery`"
            )

        # Honesty guard: a gallery older than the exported scene graph OR the
        # manifest does not reflect this release (a pose/align/crop edit landed
        # after the last refresh, or the geometry was re-exported since), and a
        # stale showcase is exactly what a release must never publish.
        if scores_file.stat().st_mtime < max(
            SCENE_JSON.stat().st_mtime,
            (COMPARISONS_DIR / "manifest.json").stat().st_mtime,
        ):
            sp.set_attribute("stale", True)
            raise SystemExit(
                "!!  comparison gallery is OLDER than the exported scene graph or "
                "the manifest -- it does not reflect this release's "
                "geometry/poses; refresh it with `uv run python -m doit gallery`"
            )

        dst = stage / "comparisons"
        dst.mkdir(exist_ok=True)
        staged = 0
        for name in _GALLERY_STAGE:
            src = COMPARISONS_DIR / name
            if not src.exists():
                continue
            if src.is_dir():
                shutil.copytree(src, dst / name, dirs_exist_ok=True)
                staged += sum(1 for p in (dst / name).rglob("*") if p.is_file())
            else:
                shutil.copy2(src, dst / name)
                staged += 1

        vals = [v for v in scores.values() if isinstance(v, (int, float))]
        facts = {
            "pairs": len(scores),
            "mean_score": round(sum(vals) / len(vals), 1) if vals else None,
            "files": staged,
        }
        sp.set_attribute("staged", True)
        sp.set_attribute("pairs", facts["pairs"])
        log(
            f"comparison gallery: staged {facts['pairs']} pairs"
            + (f" (mean RMS score {facts['mean_score']})" if vals else "")
            + f", {staged} files"
        )
        return facts


def preflight(version: str, allow_dirty: bool) -> None:
    """Fail fast before staging or creating anything."""
    require_configured_revision(version)
    if _git("tag", "--list", version):
        raise SystemExit(f"!!  tag {version} already exists -- pick another version")

    # Only the COMMITTED state matters for what a tag pins; cad/out artefacts are
    # gitignored, so --untracked-files=no keeps the build outputs from tripping it.
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty and not allow_dirty:
        raise SystemExit(
            "!!  working tree has uncommitted changes -- commit first (or "
            f"--allow-dirty):\n{dirty}"
        )

    top = OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"
    if not top.exists():
        raise SystemExit(f"!!  {top} not built -- run doit first")

    # The bundle ships the render-cache scene graph; it must exist, be in the
    # post-normalization millimetre units (so it pairs with the mm STLs), and be
    # no older than the assembly it describes.
    if not SCENE_JSON.exists():
        raise SystemExit(f"!!  {SCENE_JSON} missing -- run export_models.py first")
    scene = json.loads(SCENE_JSON.read_text(encoding="utf-8"))
    if scene.get("unit") != "mm":
        raise SystemExit(
            f"!!  {SCENE_JSON.name} unit={scene.get('unit')!r}, expected 'mm' -- "
            "re-run export_models.py (post mm-normalization)"
        )
    if SCENE_JSON.stat().st_mtime < top.stat().st_mtime:
        raise SystemExit(
            f"!!  {SCENE_JSON.name} older than {top.name} -- re-run export_models.py"
        )


# --------------------------------------------------------------------------- #
# Prepared native tree (produced on the COM seat by package_native.py)
# --------------------------------------------------------------------------- #
def load_native_package() -> dict[str, Any]:
    """Read ``native-package.json`` -- the COM-derived facts this publisher cannot
    obtain itself, because it runs on a machine with no SolidWorks seat.

    Written by ``cad/scripts/package_native.py`` beside the prepared tree it
    describes; every path inside is repo-relative POSIX, so a sidecar produced on
    a farm worker reads correctly here.
    """
    if not NATIVE_PACKAGE_FILE.is_file():
        raise SystemExit(
            f"!!  {NATIVE_PACKAGE_FILE} missing -- the native Pack-and-Go tree is "
            f"the release's only SolidWorks work and it runs as its own task; "
            f"produce it with `{_NATIVE_PACKAGE_FIX}`"
        )
    package = json.loads(NATIVE_PACKAGE_FILE.read_text(encoding="utf-8"))
    schema = package.get("schema")
    if schema != NATIVE_PACKAGE_SCHEMA:
        raise SystemExit(
            f"!!  {NATIVE_PACKAGE_FILE} has schema={schema!r}, expected "
            f"{NATIVE_PACKAGE_SCHEMA} -- regenerate it with "
            f"`{_NATIVE_PACKAGE_FIX}`"
        )
    log(
        f"native package: {package['documents']} referenced documents, "
        f"SolidWorks revision {package['solidworks_revision']} "
        f"(packaged {package['packaged_utc']})"
    )
    return package


def _copy_prepared(
    stage: Path, package: dict[str, Any], dir_key: str, count_key: str
) -> Path:
    """Copy one prepared directory into the stage, keeping its own name.

    The prepared tree mirrors the bundle's layout (``solidworks/``, ``slddrw/``),
    so publishing is a directory copy with no path rewriting. The recorded file
    count is the guard that the tree restored from the remote cache is whole.
    """
    source = REPO_ROOT / package[dir_key]
    if not source.is_dir():
        raise SystemExit(
            f"!!  prepared native directory missing: {source} -- regenerate the "
            f"tree with `{_NATIVE_PACKAGE_FIX}`"
        )
    relative = PurePosixPath(package[dir_key]).relative_to(package["out_dir"])
    target = stage / relative
    shutil.copytree(source, target)
    staged = sum(1 for path in target.iterdir() if path.is_file())
    if staged != package[count_key]:
        raise RuntimeError(
            f"prepared native directory {source} holds {staged} files, "
            f"{NATIVE_PACKAGE_FILE.name} recorded {package[count_key]} -- "
            f"regenerate the tree with `{_NATIVE_PACKAGE_FIX}`"
        )
    return target


def stage_native(stage: Path, package: dict[str, Any]) -> dict[str, str]:
    """Stage the prepared native tree and return the drawings' staged paths.

    COM-free by construction: ``package_native.py`` already ran the top assembly's
    Pack-and-Go, every drawing's Pack-and-Go and the merge/dedup between them.
    """
    _copy_prepared(stage, package, "native_dir", "native_files")
    _copy_prepared(stage, package, "drawing_dir", "drawing_files")

    staged: dict[str, str] = {}
    for drawing_name, entry in package["drawings"].items():
        for fact, member_key in (
            ("solidworks_slddrw", "native_slddrw"),
            ("slddrw", "portable_slddrw"),
        ):
            relative = PurePosixPath(entry[member_key]).relative_to(
                package["out_dir"]
            )
            member = stage / relative
            if not member.is_file() or member.stat().st_size == 0:
                raise RuntimeError(
                    f"prepared native tree is missing the {drawing_name} member "
                    f"{relative}; regenerate it with `{_NATIVE_PACKAGE_FIX}`"
                )
            staged[f"{drawing_name}:{fact}"] = relative.as_posix()
    log(
        f"native tree: staged {package['native_files']} native files + "
        f"{package['drawing_files']} drawing files for "
        f"{len(package['drawings'])} drawings"
    )
    return staged


# --------------------------------------------------------------------------- #
# Provenance manifest (ships INSIDE the zip)
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _dirty_paths(porcelain: str) -> list[str]:
    """Paths from ``git status --porcelain`` output. Splits on the 2-col status
    field rather than slicing fixed columns: ``_git`` strips its output, so the
    first line loses its leading status space and a column slice would clip a char.
    (Paths with spaces are git-quoted; the model has none, so maxsplit=1 is safe.)
    """
    rows = (ln.split(maxsplit=1) for ln in porcelain.splitlines())
    return [parts[1] for parts in rows if len(parts) == 2]


def _git_provenance(version: str) -> dict[str, Any]:
    """Exact source identity of this build. ``tree_clean`` is the load-bearing
    field: when True the tag pins the precise bytes that produced the bundle; the
    dirty file list is recorded (not hidden) when a build is cut with --allow-dirty
    so a consumer can see the build did not come from a pristine checkout.
    """
    dirty = _git("status", "--porcelain", "--untracked-files=no", check_rc=False)
    remote = _git("config", "--get", "remote.origin.url", check_rc=False)
    return {
        "commit": _git("rev-parse", "HEAD"),
        "commit_short": _git("rev-parse", "--short", "HEAD"),
        "describe": _git("describe", "--tags", "--always", "--dirty", check_rc=False),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", check_rc=False),
        "remote": remote.removesuffix(".git"),
        "commit_utc": _git("show", "-s", "--format=%cI", "HEAD", check_rc=False),
        "subject": _git("show", "-s", "--format=%s", "HEAD", check_rc=False),
        "tag": version,
        "tree_clean": not dirty,
        "dirty_files": _dirty_paths(dirty),
    }


def write_provenance(
    stage: Path, version: str, revision: str, facts: dict[str, Any]
) -> dict[str, Any]:
    """Write ``SHA256SUMS.txt`` + ``PROVENANCE.json`` into the stage so they ride
    inside the release zip. The manifest hashes every *other* shipped file (the two
    provenance files exclude themselves -- self-reference is impossible); the JSON
    then pins the manifest's own hash as the single root-of-trust a verifier checks.
    """
    diff = facts.get("diff") or {}
    prov = {
        "schema": "harmonic-analyzer/provenance@1",
        "release": {
            "version": version,
            "previous": diff.get("prev"),
            "build_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "git": _git_provenance(version),
        "toolchain": {
            "solidworks_revision": revision,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "builder": (
                f"{_git('config', '--get', 'user.name', check_rc=False)} "
                f"<{_git('config', '--get', 'user.email', check_rc=False)}>"
            ),
            "entrypoint": "doit release",
        },
        "model": {
            "documents": facts.get("documents"),
            "native_documents": facts.get("native_documents"),
            "parts": facts.get("parts"),
            "assemblies": facts.get("assemblies"),
            "config_meshes": facts.get("config_meshes"),
            "solidworks_files": facts.get("solidworks_files"),
            "changed_vs_previous": diff.get("changed_meshes", {}),
        },
    }

    # SHA256SUMS over every staged file except the two provenance files themselves.
    manifest = stage / "SHA256SUMS.txt"
    prov_json = stage / "PROVENANCE.json"
    files = sorted(
        p for p in stage.rglob("*") if p.is_file() and p not in (manifest, prov_json)
    )
    lines = [f"{_sha256(p)}  {p.relative_to(stage).as_posix()}" for p in files]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    prov["integrity"] = {
        "manifest": manifest.name,
        "manifest_sha256": _sha256(manifest),
        "file_count": len(files),
        "algorithm": "sha256",
    }
    prov_json.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    log(
        f"provenance: commit {prov['git']['commit_short']} "
        f"(tree {'clean' if prov['git']['tree_clean'] else 'DIRTY'}), "
        f"{prov['integrity']['file_count']} files hashed"
    )
    return prov


# --------------------------------------------------------------------------- #
# Bundle assembly (single zip)
# --------------------------------------------------------------------------- #
def stage_drawings(stage: Path) -> dict[str, str]:
    """Copy required manufacturing drawings into their release directories."""
    staged: dict[str, str] = {}
    for drawing_name, outputs in DRAWING_OUTPUTS.items():
        for kind, source in outputs.items():
            if kind == "slddrw":
                continue
            if not source.is_file() or source.stat().st_size == 0:
                raise RuntimeError(f"required drawing output is missing: {source}")
            destination_dir = stage / kind
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / source.name
            shutil.copy2(source, destination)
            staged[f"{drawing_name}:{kind}"] = str(
                destination.relative_to(stage)
            ).replace("\\", "/")
    return staged


OPERATING_DOC = "device-operation.md"  # what READOUT.md's arithmetic is and why


def operating_docs() -> list[str]:
    """``OPERATING_DOC`` plus the ``cad/docs`` pages reachable from it through
    ``./`` markdown links (the tolerance policy, the GD&T assessment, the DFM
    notes, the 1898 benchmark): the closure a bundle reader can follow without
    the repository. Links out to config/scripts name repo paths at the tag.

    Every page must be TRACKED: preflight and provenance read the tree with
    ``--untracked-files=no``, so an untracked page would ship inside a bundle
    the manifest calls a clean, tag-pinned tree."""
    seen: list[str] = []
    todo = [OPERATING_DOC]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        require_tracked(f"cad/docs/{name}", name)
        seen.append(name)
        text = (CAD_ROOT / "docs" / name).read_text(encoding="utf-8")
        todo.extend(re.findall(r"\]\(\./([^)#]+)", text))
    return seen


def require_tracked(rel: str, who: str) -> None:
    """Raise unless repo-relative ``rel`` is tracked (i.e. present at the tag)."""
    if not _git("ls-files", "--", rel, check_rc=False).strip():
        raise RuntimeError(f"{who}: not tracked at the tag: {rel}")


_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\((?!https?:|mailto:|#)([^)\s]+)([^)]*)\)")


def portable_links(text: str, name: str, tag: str, staged: set[str]) -> str:
    """Make every RELATIVE link in a staged doc resolve outside the repository.

    A ``./`` link to another staged page stays as-is. Anything else points at a
    file the bundle does not carry (``../config/*.yaml``, ``../scripts/*.py``)
    or cannot carry (the ``references`` submodule's third-party scans -- the
    2014 book is non-commercial, so the release must not redistribute them):

    - a path inside THIS repository becomes a blob URL at the release tag, so
      the reader gets the exact revision the bundle was cut from;
    - a path inside the ``references`` submodule becomes plain text naming the
      source, since a blob URL of a submodule path does not resolve (and an
      image embed would render broken).

    Raises on a ``./`` link with no staged target -- a broken in-bundle link
    must fail the release, not ship."""
    repo_url = f"https://github.com/{_repo_slug()}/blob/{tag}"

    def fix(m: re.Match[str]) -> str:
        bang, label, target, rest = m.groups()
        if target.startswith("./"):
            page = target[2:].split("#", 1)[0]
            if page not in staged:
                raise RuntimeError(
                    f"{name}: ./{page} is linked but not staged in the bundle"
                )
            return m.group(0)
        path, _, frag = target.partition("#")
        rel = os.path.relpath((CAD_ROOT / "docs" / path).resolve(), REPO_ROOT)
        rel = rel.replace(os.sep, "/")
        if rel.startswith(".."):
            raise RuntimeError(f"{name}: link escapes the repository: {target}")
        if rel.startswith("references/"):
            bare = label.strip("`").split("/")[-1]
            if rel.endswith(bare):
                return f"`{rel}` (pinned references submodule)"
            return f"{label} (`{rel}`, pinned references submodule)"
        require_tracked(rel, f"{name}: link target {target}")
        anchor = f"#{frag}" if frag else ""
        return f"{bang}[{label}]({repo_url}/{rel}{anchor}{rest})"

    return _LINK_RE.sub(fix, text)


# The bundle's docs quote the 2014 Hammack/Kranz/Carpenter book (short,
# attributed excerpts) and cite the pinned reference scans. The repository and
# this release are the project's OPEN, non-commercial artefacts -- the boundary
# kickstarter/campaign/risks.md draws is against the commercial book/campaign,
# which reproduce no book text or photograph. Ship that boundary WITH the zip so
# a downloader cannot mistake the bundle for a commercially reusable set.
NOTICE = """# Notice -- sources and permitted use

**Everything this project made is MIT-licensed** -- see `LICENSE` beside this
file. The CAD, the drawings, the neutral geometry and the derived numbers in
`READOUT.md` and `docs/` are this project's own work, built from `cad/config` +
`cad/scripts`, and you may use them commercially under the MIT terms.

**The machine is public domain.** Michelson and Stratton published in 1898;
Wm. Gaertner & Co. built the instruments between 1896 and 1923.

**The restrictions below apply ONLY to the third-party sources those pages
cite** -- never to the project's own artefacts:

- A. A. Michelson and S. W. Stratton, *A New Harmonic Analyzer*,
  *Am. J. Sci.* 4th ser. vol. V (1898) pp. 1-13 -- public domain; the
  benchmark tables in `docs/michelson-1898-trial-accuracy.md` are read from it.
- B. Hammack, S. Kranz and B. Carpenter, *Albert Michelson's Harmonic
  Analyzer* (2014) -- (c) 2014, distributed free **for non-commercial purposes
  only**. `docs/` quotes short attributed excerpts and cites it generously; no
  photograph or drawing from it is reproduced here, and nothing from it may be
  used commercially.
- Reference scans and photographs live in the pinned `references` submodule and
  are NOT included in this bundle; `docs/` cites them by repository path.
- Comparison-gallery imagery is CC BY -- credits in
  `comparisons/ATTRIBUTION.md` (present when the gallery shipped).
"""


def stage_readout_procedure(stage: Path, tag: str) -> list[str]:
    """Write the operating/readout procedure (error_budget.readout_procedure)
    into the bundle root as ``READOUT.md``, plus the repository ``LICENSE``,
    ``NOTICE`` (what is MIT, and the permitted use of each third-party source the
    staged pages quote) and ``operating_docs()`` under
    ``docs/`` so every ``./`` cross-link resolves inside the bundle and every
    other relative link is rewritten to the repository at ``tag``
    (``portable_links``). Not COM: the model is offline. Returns the staged
    relative paths."""
    import error_budget

    dst = stage / "READOUT.md"
    dst.write_text(
        error_budget.readout_procedure(error_budget.build_report()),
        encoding="utf-8",
    )
    staged = [dst.name]
    docs = stage / "docs"
    docs.mkdir(exist_ok=True)
    names = operating_docs()
    for name in names:
        text = (CAD_ROOT / "docs" / name).read_text(encoding="utf-8")
        (docs / name).write_text(
            portable_links(text, name, tag, set(names)), encoding="utf-8"
        )
        staged.append(f"docs/{name}")
    (stage / "NOTICE.md").write_text(NOTICE, encoding="utf-8")
    staged.append("NOTICE.md")
    # NOTICE points at it, and a zip-only consumer has no repository to look in
    require_tracked("LICENSE", "release LICENSE")
    shutil.copyfile(REPO_ROOT / "LICENSE", stage / "LICENSE")
    staged.append("LICENSE")
    return staged


def bundle(
    version: str, prev_tag: str | None = None
) -> tuple[Path, dict[str, Any]]:
    """Assemble the single release zip: prepared native tree + cached neutral set.

    One ``harmonic-analyzer-<version>.zip`` with everything a consumer needs:
    ``solidworks/`` the native Pack-and-Go files (open as-is in SolidWorks),
    ``step/`` + ``stl/`` neutral geometry, ``png/`` multi-angle previews. Staged
    under the gitignored release dir, then zipped whole.

    Opens nothing in SolidWorks: every native document came out of
    ``package_native.py``, whose prepared tree + sidecar this reads.
    """
    # 0. The COM-derived half. Read FIRST: a missing or stale sidecar is the one
    #    prerequisite failure that must not cost a staging rebuild.
    package = load_native_package()
    revision = package["solidworks_revision"]

    stage = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}"
    if stage.exists():
        shutil.rmtree(stage)  # regenerate-don't-repair: stale staging never shipped
    stage.mkdir(parents=True)

    # 1. Copy the prepared native tree (stage/solidworks + stage/slddrw) so the
    #    native files ride in the one bundle. Two counts, two keys:
    #    ``native_documents`` is the Pack-and-Go referenced set (COM-derived,
    #    from the sidecar); ``documents`` is the neutral export inventory
    #    ``stage_release_neutral`` reports below. They are NOT the same number,
    #    and one shared key let the neutral count overwrite the native one and
    #    mislabel it in the release notes (CodeRabbit, PR #770).
    facts: dict[str, Any] = {
        "native_documents": package["documents"],
        "sw_revision": revision,
    }
    native_drawings = stage_native(stage, package)
    sw_dir = stage / "solidworks"

    # 2. Validate + stage the complete export cache.
    facts.update(stage_release_neutral(stage))
    facts["drawings"] = stage_drawings(stage)
    facts["drawings"].update(native_drawings)
    facts["solidworks_files"] = sum(1 for path in sw_dir.iterdir() if path.is_file())

    # 3. Scene graph (mm): per-component transforms + mesh keys + colours. The
    #    certified neutral inventory staged it above; never overwrite it from a
    #    live cache path after validation.
    staged_scene = stage / "boxes" / SCENE_JSON.name
    if not staged_scene.is_file() or staged_scene.stat().st_size == 0:
        raise RuntimeError(f"certified release scene missing: {staged_scene}")
    facts["scene_json"] = SCENE_JSON.name

    # 4. Changed-parts diff render vs the previous release (into stage/diff, so
    #    it ships inside the bundle). Optional: skipped for the first release or
    #    a previous release that predates the neutral bundle.
    facts["diff"] = render_diff(stage, prev_tag) if prev_tag else None

    # 4b. Comparison gallery: ship the gallery the `gallery` task produced (offline
    #     Blender render off the stable STLs) under stage/comparisons. Both that
    #     task and this staging fail loud, so a release cannot ship a missing,
    #     incomplete or stale showcase.
    facts["comparisons"] = stage_comparisons(stage)

    # 4c. Operating/readout procedure: the release ships the drawings, and the
    #     accuracy those drawings' limits are derived from (check:budget) is
    #     reached only by the calibration + correction procedure the budget
    #     assumes -- generated from the same model so it cannot drift.
    facts["readout_procedure"] = stage_readout_procedure(stage, version)

    # 5. Provenance manifest LAST -- it hashes everything staged above, so it must
    #    run after the diff is written and before the zip is sealed. (Build logs
    #    are NOT staged here: they ship as a separate logs asset, see _logs_asset.)
    facts["provenance"] = write_provenance(stage, version, revision, facts)

    # 6. One zip of the whole stage.
    zip_path = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=str(stage))
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError(f"release bundle not produced at {zip_path}")
    facts["size_mb"] = zip_path.stat().st_size / 1e6
    log(
        f"release bundle: {zip_path.name} ({facts['size_mb']:.1f} MB) -- "
        f"solidworks/ + {facts['parts']} part STEP+STL + {facts['assemblies']} "
        f"assembly glTF (+{facts['config_meshes']} per-config STLs) + "
        f"{facts['pngs']} PNGs + boxes/"
    )
    return zip_path, facts


# --------------------------------------------------------------------------- #
# Release notes + publish
# --------------------------------------------------------------------------- #
def _diff_section(version: str, diff: dict[str, Any] | None) -> str:
    """Markdown 'changed parts' block with inline diff renders, or ''.

    Images are embedded by their release-asset download URL -- deterministic from
    tag + filename, so the notes can reference assets uploaded in the same
    ``gh release create`` call. GitHub renders ``![](.../releases/download/...)``
    image assets inline, so no extra attachment-upload extension is needed.
    """
    if not diff:
        return ""
    changed = diff.get("changed_parts", [])
    if not changed:
        return (
            f"\n## Changed parts vs {diff['prev']}\n\n"
            f"No part geometry changed since `{diff['prev']}`.\n"
        )
    base = f"https://github.com/{_repo_slug()}/releases/download/{version}"
    parts = ", ".join(f"`{p}`" for p in changed)
    imgs = "".join(
        f'<img src="{base}/{name}" width="420" alt="diff {name}">\n'
        for name in diff.get("images", [])[:2]
    )
    extra = diff.get("images", [])[2:]
    more = "".join(f'<img src="{base}/{n}" width="420">\n' for n in extra)
    return (
        f"\n## Changed parts vs {diff['prev']}\n\n"
        f"**{len(changed)} part(s)** changed geometry "
        f"(red = changed, confirmed by Hausdorff distance; tessellation/byte "
        f"noise excluded): {parts}\n\n"
        f"{imgs}"
        + (
            f"<details><summary>more views</summary>\n\n{more}</details>\n"
            if extra
            else ""
        )
        + "\n_Generated by `cad/comparisons/tools/render_diff.py`; renders also ship "
        "in the bundle under `diff/`._\n"
    )


def release_notes(version: str, facts: dict[str, Any]) -> str:
    return (
        f"Scripted SolidWorks reproduction of Michelson's 20-channel harmonic "
        f"analyzer.\n\n"
        f"The repository is source-of-truth (`doit` regenerates every "
        f"part). This release attaches a single **CAD bundle** "
        f"`harmonic-analyzer-{version}.zip` so the model can be opened without "
        f"rebuilding -- with or without SolidWorks:\n\n"
        f"- `solidworks/` -- native Pack-and-Go ({facts['native_documents']} referenced "
        f"documents, flattened): open `{TOP_ASSEMBLY}.SLDASM` as-is\n"
        f"- `step/` -- AP214 STEP for {facts['parts']} parts; `stl/` fine binary "
        f"STL (mm) for all {facts['parts']} parts "
        f"plus {facts['config_meshes']} per-configuration STLs (cone gears / "
        f"transgears)\n"
        f"- `gltf/` -- glTF binary (.glb) for all {facts['assemblies']} assemblies "
        f"(metre units, per-component named nodes, appearance materials): drop "
        f"`{TOP_ASSEMBLY}.glb` into any glTF viewer\n"
        f"- `boxes/{TOP_ASSEMBLY}.json` -- assembly scene graph (mm): per-component "
        f"transform, mesh key and colour, so the comparison gallery renders from "
        f"this bundle with `cad/comparisons/tools/render_offline.py` (no SolidWorks)\n"
        f"- `png/` -- isometric preview renders "
        f"({facts['pngs']} images)\n"
        + (
            f"- `comparisons/` -- this model overlaid on Michelson's ch30 photos "
            f"({facts['comparisons']['pairs']} pairs"
            + (
                f", mean RMS score {facts['comparisons']['mean_score']}"
                if facts["comparisons"]["mean_score"] is not None
                else ""
            )
            + "; open `comparisons/index.html`)\n"
        )
        + (
            f"- `diff/` -- changed-parts diff renders vs "
            f"{facts['diff']['prev']} (see below)\n"
            if facts.get("diff")
            else ""
        )
        + f"- Size: {facts['size_mb']:.1f} MB\n"
        + _diff_section(version, facts.get("diff"))
        + "\n**Provenance**\n"
        + _provenance_section(facts)
        + (
            f"\n**Logs**: `{facts['logs_asset']}` -- the per-task build logs "
            f"(parts, assemblies, verify/check gates) plus the full release log -- "
            f"is attached as a separate asset.\n"
            if facts.get("logs_asset")
            else ""
        )
    )


def _provenance_section(facts: dict[str, Any]) -> str:
    """Human-readable provenance for the release notes, mirroring the machine
    ``PROVENANCE.json`` that ships inside the bundle."""
    prov = facts.get("provenance") or {}
    git = prov.get("git", {})
    integ = prov.get("integrity", {})
    commit = git.get("commit", "")
    remote = git.get("remote", "")
    link = (
        f"[`{git.get('commit_short', sha_fallback(commit))}`]({remote}/commit/{commit})"
        if commit
        else f"`{sha_fallback(commit)}`"
    )
    tree = "clean" if git.get("tree_clean") else "**DIRTY** (see PROVENANCE.json)"
    return (
        f"- Source commit: {link} ({git.get('describe', '?')}), "
        f"working tree {tree}\n"
        f"- Built with SOLIDWORKS 3DEXPERIENCE R2026x, revision "
        f"`{facts['sw_revision']}`\n"
        f"- `PROVENANCE.json` + `SHA256SUMS.txt` ship inside the bundle "
        f"({integ.get('file_count', '?')} files hashed; verify with "
        f"`sha256sum -c SHA256SUMS.txt`)\n"
    )


def sha_fallback(commit: str) -> str:
    return commit[:7] if commit else _git("rev-parse", "--short", "HEAD")


def _logs_asset(version: str, log_path: Path | None) -> Path | None:
    """The single GitHub-release LOGS asset, or None when there is no log.

    Gathers every per-task build log (``cad/out/logs/*.log``, teed by dodo.py's
    ``_run``) plus this run's ``*-release.log``. With 2+ logs they are packed into
    ``<top>-<version>-logs.zip`` -- one tidy asset instead of a scatter of loose
    files; a lone log is attached as-is. Each build log reflects its task's MOST
    RECENT run (doit skips up-to-date tasks), so on an incremental release a log
    may predate this tag.
    """
    logs = sorted(LOGS_DIR.glob("*.log")) if LOGS_DIR.exists() else []
    if log_path is not None and log_path.exists() and log_path not in logs:
        logs.append(log_path)
    if not logs:
        log("logs: none to attach")
        return None
    if len(logs) == 1:
        log(f"logs: 1 file -> attaching loose ({logs[0].name})")
        return logs[0]
    zip_path = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}-logs.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for lg in logs:
            zf.write(lg, lg.name)
    log(
        f"logs: {len(logs)} files -> {zip_path.name} "
        f"({zip_path.stat().st_size / 1e3:.0f} KB)"
    )
    return zip_path


def _gh_assets(
    version: str, zip_path: Path, facts: dict[str, Any], log_path: Path | None
) -> list[str]:
    """Asset paths for the release: the CAD bundle, the diff PNGs (embedded in the
    notes by deterministic download URL), and the LOGS asset. Records the logs
    asset name in ``facts`` so release_notes can reference it. Building the logs
    asset here (not in bundle()) keeps the *-release.log as fresh as possible --
    it is finalized right before the upload."""
    assets = [str(zip_path)]
    if facts.get("diff"):
        assets += [str(p) for p in facts["diff"]["image_paths"]]
    logs = _logs_asset(version, log_path)
    if logs is not None:
        facts["logs_asset"] = logs.name
        assets.append(str(logs))
    return assets


def publish(
    version: str,
    zip_path: Path,
    facts: dict[str, Any],
    draft: bool,
    log_path: Path | None = None,
) -> str:
    """Annotated tag -> push -> gh release + asset upload. Returns release URL."""
    log(f"tagging {version} at HEAD")
    _git("tag", "-a", version, "-m", f"Release {version}")
    _git("push", "origin", version)

    assets = _gh_assets(version, zip_path, facts, log_path)
    args = [
        "release",
        "create",
        version,
        *assets,
        "--title",
        f"harmonic-analyzer {version}",
        "--notes",
        release_notes(version, facts),
    ]
    if draft:
        args.append("--draft")
    url = _gh(*args)
    log(f"release published: {url}")
    return url


def report_no_publish(
    version: str, zip_path: Path, facts: dict[str, Any], log_path: Path | None = None
) -> None:
    """``--no-publish``: build the assets (incl. the logs zip) and REPORT them.
    No git tag/push, no gh -- nothing leaves the machine. Used to dry-run a real
    release (e.g. validate the bundle + logs zip) without publishing."""
    assets = _gh_assets(version, zip_path, facts, log_path)
    log("--no-publish: would `gh release create` with these assets (NOT uploaded):")
    for a in assets:
        log(f"    asset: {a}")
    log("release-notes preview follows:")
    print(release_notes(version, facts), flush=True)


# --------------------------------------------------------------------------- #
# Release log capture (the whole run's output, shipped as a standalone asset)
# --------------------------------------------------------------------------- #
class _Tee:
    """Write-through to several text streams at once (the real console + the
    release-log file). Flushes every write so a backgrounded release never looks
    hung and the log file is already current when ``gh`` uploads it mid-run."""

    def __init__(self, *streams: Any) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            s.write(data)
            s.flush()
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()


def _start_release_log(version: str) -> tuple[Path, Any]:
    """Tee this run's stdout+stderr into a per-version ``*-release.log`` so the
    full progress trace (preflight, Pack-and-Go, neutral export, diff render,
    provenance) ships as a release asset for post-mortems.

    Returns ``(log_path, restore)``; ``restore()`` puts the original streams back
    and closes the file (call it in a ``finally``). The uploaded copy necessarily
    stops at the ``gh release create`` that uploads it -- the publish tail and the
    final summary print after it are not in the asset (they go to the console).
    """
    log_path = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}-release.log"
    fh = log_path.open("w", encoding="utf-8")
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout = _Tee(saved_out, fh)
    sys.stderr = _Tee(saved_err, fh)

    def restore() -> None:
        sys.stdout, sys.stderr = saved_out, saved_err
        fh.flush()
        fh.close()

    return log_path, restore


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Cut a tagged harmonic-analyzer release.")
    ap.add_argument(
        "version", nargs="?", help="release tag vNN (default: next compact tag)"
    )
    ap.add_argument(
        "--allow-dirty",
        action="store_true",
        help="tag even with uncommitted (tracked) changes",
    )
    ap.add_argument(
        "--draft", action="store_true", help="create the GitHub release as a draft"
    )
    ap.add_argument(
        "--no-publish",
        action="store_true",
        help="build the bundle + logs zip but do NOT tag/push/gh "
        "(dry run -- nothing leaves the machine)",
    )
    opts = ap.parse_args()

    version = resolve_version(opts.version)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    # Tee everything below to the per-version release log BEFORE preflight, so the
    # asset captures the whole run (including a preflight bail-out). restore() in
    # the finally puts the real streams back and closes the file no matter what.
    log_path, restore = _start_release_log(version)
    try:
        # Advertise "release" as this process's telemetry resource (Aspire "resource"
        # column); fallback-only, so dodo's inherited OTEL_SERVICE_NAME wins under the
        # spine and this self-labels a standalone `cut_release.py` run.
        _telemetry.set_service("release")
        # Wrap the whole release in a span; run_pipeline_span extracts the
        # TRACEPARENT dodo._run injected (under `doit release`), so the release
        # staging + logs continue the doit task span instead of being detached.
        with _telemetry.run_pipeline_span("release", version=version) as rel:
            _telemetry.info(f"cutting release {version}")
            preflight(version, opts.allow_dirty)

            prev = previous_tag(version)
            log(f"previous release for diff: {prev or '(none -- first bundle)'}")

            started = time.perf_counter()
            try:
                zip_path, facts = bundle(version, prev)
            except Exception as exc:
                # Mark the span ERROR before the early return, else the caught
                # failure would exit the span cleanly and trace as success.
                rel.record_exception(exc)
                rel.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
                traceback.print_exc()
                return 1

            if opts.no_publish:
                report_no_publish(version, zip_path, facts, log_path)
                url = None
            else:
                prepared = prepare_configured_revision_advance(version)
                try:
                    url = publish(version, zip_path, facts, opts.draft, log_path)
                except Exception:
                    prepared.discard()
                    raise
                try:
                    next_revision = prepared.commit()
                except Exception as exc:
                    prepared.discard()
                    message = (
                        f"release {version} was published at {url}, but could not "
                        f"advance {RELEASE_VERSION_FILE}; manually set "
                        f"next_revision: {prepared.next_version} and commit/merge "
                        "that version bump before cutting the next release"
                    )
                    _telemetry.error(message)
                    rel.record_exception(exc)
                    rel.set_status(
                        _telemetry.Status(_telemetry.StatusCode.ERROR, message)
                    )
                    raise RuntimeError(message) from exc
                _telemetry.warn(
                    f"VERSION BUMP REQUIRED: {RELEASE_VERSION_FILE} now contains "
                    f"{next_revision}; commit and merge this version bump before "
                    "cutting the next release"
                )
            _telemetry.success(f"Done in {time.perf_counter() - started:.1f}s.")
            _telemetry.info(f"version: {version}")
            _telemetry.info(
                f"bundle:  {zip_path} ({facts['size_mb']:.1f} MB) -- solidworks/ + "
                f"{facts['parts']} parts x STEP+STL + {facts['assemblies']} "
                f"assembly glTF (+{facts['config_meshes']} "
                f"per-config) + {facts['pngs']} PNGs + boxes/"
            )
            _telemetry.info(f"log:     {log_path}")
            if facts.get("logs_asset"):
                _telemetry.info(f"logs:    {RELEASE_DIR / facts['logs_asset']}")
            _telemetry.info(f"release: {url or '(--no-publish: not published)'}")
            return 0
    finally:
        restore()


if __name__ == "__main__":
    sys.exit(main())
