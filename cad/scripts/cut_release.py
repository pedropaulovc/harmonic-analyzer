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
  3. SolidWorks (COM): open harmonic-analyzer.SLDASM, run Pack-and-Go flattened,
     and -- in the same session -- export every built part and assembly to AP214
     STEP + fine binary STL + multi-angle PNG previews. Everything is staged and
     zipped into ONE bundle ``cad/out/release/harmonic-analyzer-<version>.zip``
     (``solidworks/`` native + ``step/`` + ``stl/`` + ``png/``). Records the SW
     revision for the notes.
  4. git: annotated tag at HEAD, pushed to origin.
  5. gh: create the GitHub release for the tag (auto-generated notes header +
     our provenance block) and upload the bundle as the release asset.

Run (SolidWorks already open, NOTHING else driving it -- single STA COM server,
a concurrent build_all/verify deadlocks):

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\cut_release.py [vX.Y.Z] [--bump patch|minor|major] [--allow-dirty] [--draft]

``--draft`` makes the GitHub release a draft (asset uploaded, not published).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from _common import CAD_ROOT, OUT_SLDASM, OUT_SLDPRT, log

REPO_ROOT = CAD_ROOT.parent
TOP_ASSEMBLY = "harmonic-analyzer"
RELEASE_DIR = CAD_ROOT / "out" / "release"
_VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# SolidWorks COM type library (SldWorks); the version pins the same revision the
# pywin32 gen_py module exposes (...x0x34x0) so comtypes generates matching stubs.
SW_TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_TYPELIB_VER = (34, 0)
SW_DOC_PART = 1  # swDocumentTypes_e.swDocPART
SW_DOC_ASSEMBLY = 2  # swDocumentTypes_e.swDocASSEMBLY
SW_OPEN_SILENT = 1  # swOpenDocOptions_e.swOpenDocOptions_Silent

# SaveAs3 Options bitmask (swSaveAsOptions_e): Silent suppresses the "rebuild the
# document before saving?" modal that a cold-opened assembly pops (its flexible
# configs re-solve on open -> dirty); AvoidRebuildOnSave skips the needless
# rebuild (the on-disk geometry is what the release ships).
SW_SAVE_SILENT = 1  # swSaveAsOptions_Silent
SW_SAVE_AVOID_REBUILD = 8  # swSaveAsOptions_AvoidRebuildOnSave
SW_SAVE_OPTS = SW_SAVE_SILENT | SW_SAVE_AVOID_REBUILD

# Neutral-format export user preferences (swUserPreferenceIntegerValue_e /
# swUserPreferenceToggle_e ids, mirrored from export_models.py). STEP AP214
# carries colours; STL is fine binary, in MILLIMETRES (viewer/slicer-friendly --
# the release ships consumer geometry, NOT the metre-unit render cache), with the
# model origin preserved so assembly STLs keep their components aligned.
PREF_STL_QUALITY = 78        # int: swSTLQuality -> 2 = fine
PREF_STEP_AP = 75            # int: swStepAP -> 214 (carries colours)
PREF_STL_UNITS = 211         # int: swExportStlUnits -> 0 = swMM
TOGGLE_STL_BINARY = 69       # swSTLBinaryFormat
TOGGLE_STL_SHOW_INFO = 70    # swSTLShowInfoOnSave: the "Save <name>.STL?" modal
TOGGLE_STL_ONE_FILE = 72     # swSTLComponentsIntoOneFile (monolithic asm STL)
TOGGLE_STL_NO_TRANSLATE = 71  # swSTLDontTranslateToPositive: keep model origin
_EXPORT_INTS = {PREF_STL_QUALITY: 2, PREF_STEP_AP: 214, PREF_STL_UNITS: 0}
# swSTLShowInfoOnSave -> False: SaveAs3 to .STL otherwise pops a per-file
# triangle-count info dialog that hangs the headless export on the first part.
_EXPORT_TOGGLES = {TOGGLE_STL_BINARY: True, TOGGLE_STL_ONE_FILE: True,
                   TOGGLE_STL_NO_TRANSLATE: True, TOGGLE_STL_SHOW_INFO: False}

# Preview renders per document: (name, swStandardViews_e id). SaveBMP captures
# the active viewport at an exact pixel size (the only screenshot API that does);
# Pillow then transcodes the BMP to compressed PNG.
PNG_VIEWS = (
    ("isometric", 7), ("front", 1), ("back", 2),
    ("left", 3), ("right", 4), ("top", 5),
)
PNG_WIDTH, PNG_HEIGHT = 1600, 1000


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
# SolidWorks Pack-and-Go (COM via comtypes)
# --------------------------------------------------------------------------- #
def _close_active_documents(sw: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    ``CloseDoc`` closes a dirty document WITHOUT saving it (documented: a dirty
    name "closes the document without saving it"), and ``CloseDoc("")`` closes the
    ACTIVE doc (plus hidden/referenced ones). Loop it until no document is active.
    Bounded so a misbehaving session can't spin.
    """
    for _ in range(500):
        if sw.IActiveDoc2 is None:
            break
        sw.CloseDoc("")  # "" -> close the ACTIVE doc, discarding unsaved changes


def _discard_open_documents(sw: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    ``CloseAllDocuments(True)`` still pops that modal in 3DX R2026x when an open
    assembly has a DIRTY referenced child -- e.g. after a ``verify.py --suite
    engagement/motion`` run (or a manual config switch) activated the flexible
    ``operating`` / ``pinion_engaged`` config, which re-solves and dirties the
    drive-train child. Headless, that modal hangs the release forever.

    Discard the active docs first (above), then ``CloseAllDocuments(True)`` as a
    backstop -- with nothing dirty left, it has nothing to prompt about.
    """
    _close_active_documents(sw)
    sw.CloseAllDocuments(True)


def attach_solidworks() -> tuple[Any, str]:
    """Attach to the running SolidWorks via comtypes; return (ISldWorks, revision).

    Uses comtypes, NOT the pywin32 adapter: ``GetPackAndGo`` returns an
    ``[out, retval] IPackAndGo**`` param that win32com cannot marshal (it returns
    null across every invocation style -- pywin32 issues #1303/#622), whereas
    comtypes generates correct [out,retval] handling straight from the typelib.
    GetActiveObject attaches to the SW instance the user already launched from the
    3DEXPERIENCE Platform shortcut (never start sldworks.exe -- the Makers seat
    rejects a COM-launched instance as unlicensed).
    """
    import comtypes
    import comtypes.client

    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
    sw = comtypes.client.GetActiveObject("SldWorks.Application", interface=mod.ISldWorks)
    revision = sw.RevisionNumber()
    log(f"attached to SolidWorks, revision {revision}")
    return sw, revision


def package(sw: Any, revision: str, zip_path: Path) -> dict[str, Any]:
    """Pack-and-Go the top assembly into ``zip_path``.

    Pack-and-Go bundles a document with every file it references; SetSaveToName2
    with a ``.zip`` target writes a single archive, FlattenToSingleFolder drops
    the original folder tree so the zip opens cleanly anywhere.
    """
    top = OUT_SLDASM / f"{TOP_ASSEMBLY}.SLDASM"

    # Discard any open docs silently first: a dirty referenced child (left by a
    # prior engagement/motion verify) would make CloseAllDocuments(True) prompt.
    _discard_open_documents(sw)
    log("discarded any open documents (clean session)")
    sw.OpenDoc6(str(top), SW_DOC_ASSEMBLY, SW_OPEN_SILENT, "", 0, 0)
    log(f"opened {TOP_ASSEMBLY}")

    ext = sw.IActiveDoc2.Extension
    pg = ext.GetPackAndGo()
    if pg is None:
        raise RuntimeError("GetPackAndGo returned None")

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

    return {
        "zip": zip_path,
        "size_mb": zip_path.stat().st_size / 1e6,
        "documents": names_count,
        "sw_revision": revision,
    }


def _set_export_prefs(sw: Any) -> dict[str, dict[int, Any]]:
    """Apply the neutral-format export preferences, returning the prior values."""
    old = {
        "ints": {k: int(sw.GetUserPreferenceIntegerValue(k)) for k in _EXPORT_INTS},
        "toggles": {k: bool(sw.GetUserPreferenceToggle(k)) for k in _EXPORT_TOGGLES},
    }
    for k, v in _EXPORT_INTS.items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in _EXPORT_TOGGLES.items():
        sw.SetUserPreferenceToggle(k, v)
    return old


def _restore_export_prefs(sw: Any, old: dict[str, dict[int, Any]]) -> None:
    for k, v in old["ints"].items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in old["toggles"].items():
        sw.SetUserPreferenceToggle(k, v)


def _export_pngs(doc: Any, png_dir: Path, stem: str) -> int:
    """Render the active document to a PNG per PNG_VIEWS angle; return the count.

    SaveBMP is the only screenshot API honouring an explicit pixel size, but it
    only writes BMP; capture to a temp .bmp at PNG_WIDTH x PNG_HEIGHT then
    transcode to PNG with Pillow (kills the ~5x-larger BMP). ShowNamedView2 sets
    the standard view, ViewZoomToFit2 frames the model before each shot.
    """
    from PIL import Image

    png_dir.mkdir(parents=True, exist_ok=True)
    for name, view_const in PNG_VIEWS:
        doc.ShowNamedView2("", view_const)
        doc.ViewZoomToFit2()
        bmp = png_dir / f"{stem}_{name}.bmp"
        if not doc.SaveBMP(str(bmp), PNG_WIDTH, PNG_HEIGHT) or not bmp.exists():
            raise RuntimeError(f"SaveBMP produced no file: {bmp}")
        with Image.open(bmp) as img:
            img.save(png_dir / f"{stem}_{name}.png")
        bmp.unlink()
    return len(PNG_VIEWS)


def export_neutral(sw: Any, stage: Path) -> dict[str, Any]:
    """Export every built part and assembly to STEP + STL + PNGs under ``stage``.

    Alongside the Pack-and-Go native files (``stage/solidworks``), this fills the
    *neutral* CAD a consumer without SolidWorks can open -- ``stage/step`` AP214
    STEP (exact archival B-rep, colours carried), ``stage/stl`` fine binary STL
    (mesh, for viewers/slicers), and ``stage/png`` a multi-angle PNG preview set
    (PNG_VIEWS), one of each per part and per assembly. The caller zips the whole
    ``stage`` into the single release bundle.

    Opens each document with the comtypes session already attached for
    Pack-and-Go and SaveAs3-exports it; assemblies write a monolithic STL and a
    single assembly STEP (all components). Staged under the gitignored release
    dir -- NEVER cad/out/stl, whose metre-unit untranslated meshes the render
    cache (stl_bbox_mm / MIRROR_PLANE) depends on. Each file is closed with
    CloseDoc (discards unsaved changes) so an under-defined config that re-solves
    on open never pops a save modal.
    """
    step_dir = stage / "step"
    stl_dir = stage / "stl"
    png_root = stage / "png"
    for d in (step_dir, stl_dir, png_root):
        d.mkdir(parents=True, exist_ok=True)

    # Close the top assembly Pack-and-Go left open BEFORE enumerating: while an
    # assembly is loaded SolidWorks writes a per-component lock file (~$<name>)
    # alongside each .SLDPRT, which would otherwise double the work list.
    _discard_open_documents(sw)

    def _models(folder: Path, ext: str) -> list[Path]:
        return sorted(p for p in folder.glob(f"*.{ext}") if not p.name.startswith("~"))

    # parts first (assemblies reference them), each (path, swDocType).
    parts = _models(OUT_SLDPRT, "SLDPRT")
    assemblies = _models(OUT_SLDASM, "SLDASM")
    docs = [(p, SW_DOC_PART) for p in parts] + [(a, SW_DOC_ASSEMBLY) for a in assemblies]
    log(f"neutral export: {len(parts)} parts + {len(assemblies)} assemblies")

    old_prefs = _set_export_prefs(sw)
    exported = pngs = 0
    try:
        for i, (src, doc_type) in enumerate(docs, 1):
            sw.OpenDoc6(str(src), doc_type, SW_OPEN_SILENT, "", 0, 0)
            doc = sw.IActiveDoc2
            if doc is None:
                raise RuntimeError(f"failed to open {src.name}")
            for out in (step_dir / f"{src.stem}.STEP", stl_dir / f"{src.stem}.STL"):
                rc = doc.SaveAs3(str(out), 0, SW_SAVE_OPTS)
                if not out.exists() or out.stat().st_size == 0:
                    raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={rc})")
            pngs += _export_pngs(doc, png_root / src.stem, src.stem)
            _close_active_documents(sw)  # CloseDoc -> discards, never prompts
            if i % 10 == 0 or i == len(docs):
                log(f"neutral export: {i}/{len(docs)} documents ({pngs} PNGs)")
        exported = len(docs)
    finally:
        _restore_export_prefs(sw, old_prefs)

    return {
        "documents": exported,
        "parts": len(parts),
        "assemblies": len(assemblies),
        "pngs": pngs,
        "views": len(PNG_VIEWS),
    }


# --------------------------------------------------------------------------- #
# Bundle assembly (single zip)
# --------------------------------------------------------------------------- #
def bundle(sw: Any, revision: str, version: str) -> tuple[Path, dict[str, Any]]:
    """Assemble the single release zip: Pack-and-Go + neutral STEP/STL/PNG.

    One ``harmonic-analyzer-<version>.zip`` with everything a consumer needs:
    ``solidworks/`` the native Pack-and-Go files (open as-is in SolidWorks),
    ``step/`` + ``stl/`` neutral geometry, ``png/`` multi-angle previews. Staged
    under the gitignored release dir, then zipped whole.
    """
    stage = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}"
    if stage.exists():
        shutil.rmtree(stage)  # regenerate-don't-repair: stale staging never shipped
    stage.mkdir(parents=True)

    # 1. Pack-and-Go writes a .zip (the proven comtypes path); extract it flat
    #    into stage/solidworks so the native files ride in the one bundle.
    pg_tmp = RELEASE_DIR / f"_{TOP_ASSEMBLY}-{version}-packandgo.zip"
    if pg_tmp.exists():
        pg_tmp.unlink()
    facts = package(sw, revision, pg_tmp)
    sw_dir = stage / "solidworks"
    sw_dir.mkdir()
    shutil.unpack_archive(str(pg_tmp), str(sw_dir), "zip")
    pg_tmp.unlink()
    facts["solidworks_files"] = sum(1 for _ in sw_dir.iterdir())

    # 2. Neutral exports (STEP / STL / PNG) into the same stage.
    facts.update(export_neutral(sw, stage))

    # 3. One zip of the whole stage.
    zip_path = RELEASE_DIR / f"{TOP_ASSEMBLY}-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=str(stage))
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise RuntimeError(f"release bundle not produced at {zip_path}")
    facts["size_mb"] = zip_path.stat().st_size / 1e6
    log(f"release bundle: {zip_path.name} ({facts['size_mb']:.1f} MB) -- "
        f"solidworks/ + {facts['documents']} docs x STEP+STL + {facts['pngs']} PNGs")
    return zip_path, facts


# --------------------------------------------------------------------------- #
# Release notes + publish
# --------------------------------------------------------------------------- #
def release_notes(version: str, facts: dict[str, Any]) -> str:
    sha = _git("rev-parse", "--short", "HEAD")
    return (
        f"Scripted SolidWorks reproduction of Michelson's 20-channel harmonic "
        f"analyzer.\n\n"
        f"The repository is source-of-truth (`build_all.py` regenerates every "
        f"part). This release attaches a single **CAD bundle** "
        f"`harmonic-analyzer-{version}.zip` so the model can be opened without "
        f"rebuilding -- with or without SolidWorks:\n\n"
        f"- `solidworks/` -- native Pack-and-Go ({facts['documents']} referenced "
        f"documents, flattened): open `{TOP_ASSEMBLY}.SLDASM` as-is\n"
        f"- `step/` -- AP214 STEP + `stl/` fine binary STL (mm), one of each per "
        f"document: {facts['parts']} parts + {facts['assemblies']} assemblies\n"
        f"- `png/` -- {facts['views']}-angle preview renders "
        f"({facts['pngs']} images)\n"
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

    started = time.perf_counter()
    try:
        sw, revision = attach_solidworks()
        zip_path, facts = bundle(sw, revision, version)
    except Exception:
        traceback.print_exc()
        return 1

    url = publish(version, zip_path, facts, opts.draft)
    print(f"\nDone in {time.perf_counter() - started:.1f}s.", flush=True)
    print(f"  version: {version}")
    print(f"  bundle:  {zip_path} ({facts['size_mb']:.1f} MB) -- solidworks/ + "
          f"{facts['documents']} docs x STEP+STL + {facts['pngs']} PNGs")
    print(f"  release: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
