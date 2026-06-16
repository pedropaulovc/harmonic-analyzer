r"""Cut a tagged release of the harmonic-analyzer and attach its CAD bundle.

The repository is source-of-truth: ``.SLDPRT/.SLDASM`` are gitignored build
artefacts (Part E). A *release* is therefore the one place a binary snapshot is
published -- a git tag pins the exact source state, and a SolidWorks Pack-and-Go
zip (the top assembly + every referenced part, flattened) is attached to the
matching GitHub release so a consumer can open the model without rebuilding.

What it does, in order:

  1. Resolve the version (``vX.Y.Z``): explicit positional, or auto-bump the
     latest ``v*`` tag (``--bump major|minor|patch``, default patch).
  2. Pre-flight: tag must not already exist; the committed tree must be clean
     (``--allow-dirty`` to override); harmonic-analyzer.SLDASM must be built.
  3. SolidWorks (COM): open harmonic-analyzer.SLDASM, run Pack-and-Go flattened
     into ``cad/out/release/harmonic-analyzer-<version>.zip``. Records the SW
     revision for the notes.
  4. git: annotated tag at HEAD, pushed to origin.
  5. gh: create the GitHub release for the tag (auto-generated notes header +
     our provenance block) and upload the zip as a release asset.

Run (SolidWorks already open, NOTHING else driving it -- single STA COM server,
a concurrent build_all/verify deadlocks):

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\cut_release.py [vX.Y.Z] [--bump patch|minor|major] [--allow-dirty] [--draft]

``--draft`` makes the GitHub release a draft (asset uploaded, not published).
"""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from _common import CAD_ROOT, OUT_SLDASM, check, log

REPO_ROOT = CAD_ROOT.parent
TOP_ASSEMBLY = "harmonic-analyzer"
RELEASE_DIR = CAD_ROOT / "out" / "release"
_VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


# --------------------------------------------------------------------------- #
# git / gh helpers (plain subprocess -- no SolidWorks involvement)
# --------------------------------------------------------------------------- #
def _git(*args: str, check_rc: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )
    if check_rc and proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _gh(*args: str) -> str:
    proc = subprocess.run(
        ["gh", *args], cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )
    if proc.returncode:
        raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _existing_tags() -> list[tuple[int, int, int]]:
    raw = _git("tag", "--list", "v*").splitlines()
    out = []
    for line in raw:
        m = _VERSION_RE.match(line.strip())
        if m:
            out.append((int(m[1]), int(m[2]), int(m[3])))
    return sorted(out)


def resolve_version(explicit: str | None, bump: str) -> str:
    """Pick the release tag: validate an explicit one, else bump the latest."""
    if explicit is not None:
        if not _VERSION_RE.match(explicit):
            raise SystemExit(f"!!  version must look like vX.Y.Z, got {explicit!r}")
        return explicit

    tags = _existing_tags()
    if not tags:
        return "v0.1.0"
    major, minor, patch = tags[-1]
    if bump == "major":
        return f"v{major + 1}.0.0"
    if bump == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def preflight(version: str, allow_dirty: bool) -> None:
    """Fail fast before touching SolidWorks or creating anything."""
    if _git("tag", "--list", version):
        raise SystemExit(f"!!  tag {version} already exists -- pick another version")

    # Only the COMMITTED state matters for what a tag pins; cad/out artefacts are
    # gitignored, so --untracked-files=no keeps the build outputs from tripping it.
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    if dirty and not allow_dirty:
        raise SystemExit(
            "!!  working tree has uncommitted changes -- commit first (or "
            f"--allow-dirty):\n{dirty}")

    top = OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"
    if not top.exists():
        raise SystemExit(
            f"!!  {top} not built -- run build_all.py first")


# --------------------------------------------------------------------------- #
# SolidWorks Pack-and-Go (COM)
# --------------------------------------------------------------------------- #
async def _pack_and_go(adapter: Any, zip_path: Path) -> dict[str, Any]:
    """Open the top assembly and Pack-and-Go it (flattened) into ``zip_path``.

    Pack-and-Go bundles a document with every file it references; SetSaveToName2
    with a ``.zip`` target writes a single archive, FlattenToSingleFolder drops
    the original folder tree so the zip opens cleanly anywhere.
    """
    top = OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"
    check(f"open {TOP_ASSEMBLY}", await adapter.open_model(str(top)))
    model = adapter.currentModel

    # pywin32 late binding resolves zero-arg COM methods (GetPackAndGo,
    # GetDocumentNamesCount) as tuple-valued PROPERTIES -- calling them then
    # raises, and wrapping in adapter._attempt silently masks it to None. Bind
    # both dispatches EARLY (dispid invoke via the makepy wrapper) so every
    # member resolves, and call directly so any COM error surfaces in the
    # traceback. (Fork learning #2 / the GetMotionStudyManager case documented
    # in sw_type_info.early_bound.)
    from solidworks_mcp.adapters import sw_type_info

    ext = sw_type_info.early_bound(model.Extension, "IModelDocExtension")
    pg = ext.GetPackAndGo()
    if pg is None:
        raise RuntimeError("GetPackAndGo returned None (assembly not active?)")
    pg = sw_type_info.early_bound(pg, "IPackAndGo")

    names_count = pg.GetDocumentNamesCount()
    log(f"pack-and-go: {names_count} referenced documents")

    # Bundle exactly the CAD: no drawings/sim/toolbox, but DO include components
    # suppressed in the active config so every engagement config's parts ship.
    pg.IncludeDrawings = False
    pg.IncludeSimulationResults = False
    pg.IncludeToolboxComponents = False
    pg.IncludeSuppressed = True
    pg.FlattenToSingleFolder = True

    if not pg.SetSaveToName2(True, str(zip_path)):
        raise RuntimeError(f"SetSaveToName2 rejected {zip_path}")

    statuses = ext.SavePackAndGo(pg)
    log(f"pack-and-go: SavePackAndGo statuses = {statuses}")

    # Run-don't-build: the only proof Pack-and-Go succeeded is the file on disk.
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError(f"Pack-and-Go produced no zip at {zip_path}")

    revision = adapter._attempt(lambda: adapter.swApp.RevisionNumber(), default="unknown")
    return {
        "zip": zip_path,
        "size_mb": zip_path.stat().st_size / 1e6,
        "documents": names_count,
        "sw_revision": revision,
    }


def package(zip_path: Path) -> dict[str, Any]:
    """Connect, Pack-and-Go, disconnect; return the bundle facts."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    async def _run() -> dict[str, Any]:
        adapter = PyWin32Adapter({})
        print("Connecting to SolidWorks ...", flush=True)
        await adapter.connect()
        log("connected")
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
        log("CloseAllDocuments (clean session)")
        try:
            return await _pack_and_go(adapter, zip_path)
        finally:
            try:
                await adapter.disconnect()
                print("Disconnected.", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN disconnect failed: {exc}", flush=True)

    return asyncio.run(_run())


# --------------------------------------------------------------------------- #
# Release notes + publish
# --------------------------------------------------------------------------- #
def release_notes(version: str, facts: dict[str, Any]) -> str:
    sha = _git("rev-parse", "--short", "HEAD")
    return (
        f"Scripted SolidWorks reproduction of Michelson's 20-channel harmonic "
        f"analyzer.\n\n"
        f"The repository is source-of-truth (`build_all.py` regenerates every "
        f"part). This release attaches a **Pack-and-Go CAD bundle** so the model "
        f"can be opened without rebuilding.\n\n"
        f"**Bundle** `harmonic-analyzer-{version}.zip`\n"
        f"- Top assembly: `{TOP_ASSEMBLY}.SLDASM` + {facts['documents']} "
        f"referenced documents (flattened)\n"
        f"- Size: {facts['size_mb']:.1f} MB\n\n"
        f"**Provenance**\n"
        f"- Commit: `{sha}`\n"
        f"- Built with SOLIDWORKS 3DEXPERIENCE R2026x, revision "
        f"`{facts['sw_revision']}`\n"
    )


def publish(version: str, zip_path: Path, facts: dict[str, Any], draft: bool) -> str:
    """Annotated tag -> push -> gh release + asset upload. Returns release URL."""
    log(f"tagging {version} at HEAD")
    _git("tag", "-a", version, "-m", f"Release {version}")
    _git("push", "origin", version)

    args = [
        "release", "create", version, str(zip_path),
        "--title", f"harmonic-analyzer {version}",
        "--notes", release_notes(version, facts),
    ]
    if draft:
        args.append("--draft")
    url = _gh(*args)
    log(f"release published: {url}")
    return url


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Cut a tagged harmonic-analyzer release.")
    ap.add_argument("version", nargs="?", help="release tag vX.Y.Z (default: auto-bump)")
    ap.add_argument("--bump", choices=("major", "minor", "patch"), default="patch",
                    help="how to bump the latest tag when version is omitted")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="tag even with uncommitted (tracked) changes")
    ap.add_argument("--draft", action="store_true",
                    help="create the GitHub release as a draft")
    opts = ap.parse_args()

    version = resolve_version(opts.version, opts.bump)
    print(f"==  cutting release {version}", flush=True)
    preflight(version, opts.allow_dirty)

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()  # regenerate-don't-repair: stale bundle never shipped

    started = time.perf_counter()
    try:
        facts = package(zip_path)
    except Exception:
        traceback.print_exc()
        return 1

    url = publish(version, zip_path, facts, opts.draft)
    print(f"\nDone in {time.perf_counter() - started:.1f}s.", flush=True)
    print(f"  version: {version}")
    print(f"  bundle:  {zip_path} ({facts['size_mb']:.1f} MB)")
    print(f"  release: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
