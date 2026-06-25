r"""Cut a tagged release of the harmonic-analyzer and attach its CAD bundle.

doit task: ``release`` (spine tail, opt-in) -- ``doit release -- v0.2.0 [--draft]``
forwards args here. Runnable standalone too.


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
     STEP + fine binary STL + multi-angle PNG previews. The STL set is
     one-per-part plus a per-configuration STL for the parts whose configs are
     distinct geometry (cone gears / transgears). Also copies the millimetre
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

Run (SolidWorks already open, NOTHING else driving it -- single STA COM server,
a concurrent build_all/verify deadlocks):

    uv run python cad\scripts\cut_release.py [vX.Y.Z] [--bump patch|minor|major] [--allow-dirty] [--draft]

``--draft`` makes the GitHub release a draft (asset uploaded, not published).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any

from _common import CAD_ROOT, OUT_SLDASM, OUT_SLDPRT, OUT_STL, log

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
RENDER_DIFF = REPO_ROOT / "comparisons" / "tools" / "render_diff.py"
# export_models.py render cache: the millimetre scene graph (component transforms
# + per-config mesh keys + colours) that lets a consumer render the bundle with
# comparisons/tools/render_offline.py without SolidWorks.
SCENE_JSON = CAD_ROOT / "out" / "boxes" / f"{TOP_ASSEMBLY}.json"
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
# carries colours; STL is fine binary, in MILLIMETRES (viewer/slicer-friendly),
# with the model origin preserved so assembly STLs keep their components aligned.
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

# Incremental PNG render cache (gitignored, under the release dir). Rendering the
# multi-angle previews is the single most expensive release step (~550 s for 486
# PNGs in v0.9.1) AND the only step that genuinely needs the SolidWorks seat (SaveBMP
# of the live viewport -- STEP/STL are copied from cad/out). Each document's PNG set
# is cached under a key derived from its RESOLVED geometry, so a release whose
# geometry is unchanged (the common case: most releases touch a handful of parts, and
# v0.9.1 touched none) reuses the prior renders and opens nothing. A cache MISS only
# ever costs a re-render -- it can never ship a wrong image.
PNG_CACHE_DIR = RELEASE_DIR / "png-cache"
# Bump when _export_pngs' rendering (views, pixel size, framing) changes so a code
# change invalidates every cached render rather than shipping a stale-format image.
PNG_RENDER_REV = "1"


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


def previous_tag(version: str) -> str | None:
    """Highest existing ``vX.Y.Z`` tag strictly below ``version`` (or None)."""
    m = _VERSION_RE.match(version)
    assert m is not None, f"previous_tag: version must match vX.Y.Z, got {version!r}"
    cur = (int(m[1]), int(m[2]), int(m[3]))
    prior = [t for t in _existing_tags() if t < cur]
    if not prior:
        return None
    a, b, c = prior[-1]
    return f"v{a}.{b}.{c}"


def _repo_slug() -> str:
    """``owner/repo`` from the origin remote, for building asset URLs."""
    url = _git("config", "--get", "remote.origin.url", check_rc=False)
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url or "")
    return m.group(1) if m else "pedropaulovc/harmonic-analyzer"


def render_diff(stage: Path, prev_tag: str) -> dict[str, Any]:
    """Render the changed-parts diff (this staged bundle vs the previous release).

    Runs ``comparisons/tools/render_diff.py`` via ``uv run`` (isolated deps): the
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
        ["uv", "run", str(RENDER_DIFF),
         "--old-release", prev_tag, "--new-local", str(stage),
         "--out", str(diff_dir), "--summary-json", str(summary)],
        cwd=str(REPO_ROOT), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1,
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
            f"diff render FAILED (release blocked): {' / '.join(tail)[-400:]}")
    data = json.loads(summary.read_text(encoding="utf-8"))
    data["prev"] = prev_tag
    data["image_paths"] = [diff_dir / n for n in data.get("images", [])]
    log(f"diff render: {len(data.get('changed_parts', []))} changed parts, "
        f"{len(data['image_paths'])} views")
    return data


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
            f"!!  {top} not built -- run doit first")

    # The bundle ships the render-cache scene graph; it must exist, be in the
    # post-normalization millimetre units (so it pairs with the mm STLs), and be
    # no older than the assembly it describes.
    if not SCENE_JSON.exists():
        raise SystemExit(
            f"!!  {SCENE_JSON} missing -- run export_models.py first")
    scene = json.loads(SCENE_JSON.read_text(encoding="utf-8"))
    if scene.get("unit") != "mm":
        raise SystemExit(
            f"!!  {SCENE_JSON.name} unit={scene.get('unit')!r}, expected 'mm' -- "
            "re-run export_models.py (post mm-normalization)")
    if SCENE_JSON.stat().st_mtime < top.stat().st_mtime:
        raise SystemExit(
            f"!!  {SCENE_JSON.name} older than {top.name} -- re-run export_models.py")


# --------------------------------------------------------------------------- #
# SolidWorks Pack-and-Go (COM via comtypes)
# --------------------------------------------------------------------------- #
def _close_active_documents(sw: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    Close the active doc by its TITLE, not the empty string: although
    ``CloseDoc("")`` is documented to close the active doc, in 3DX R2026x it
    silently NO-OPS on any assembly that has loaded components (it only closes a
    standalone part) -- so an export that relied on it left every assembly + its
    components resident. ``CloseDoc(GetTitle())`` closes the assembly AND its
    hidden components (document count drops to 0), and ``CloseDoc`` still discards
    a dirty document without saving, so no save modal appears. Loop until no
    document is active; bounded so a misbehaving session can't spin.

    Refuse an empty title: ``CloseDoc("")`` is the very no-op trap above, so
    falling back to it would silently spin this loop and leave the doc resident.
    Fail loud instead of regressing invisibly.
    """
    for _ in range(500):
        doc = sw.IActiveDoc2
        if doc is None:
            break
        title = doc.GetTitle()
        if not title:
            raise RuntimeError(
                f"active document has an empty title ({title!r}) -- refusing "
                f"CloseDoc(''), which silently no-ops on assemblies and would "
                f"leave the document resident")
        sw.CloseDoc(title)


def _discard_open_documents(sw: Any) -> None:
    """Close every open document WITHOUT a "Save Modified Documents" prompt.

    ``CloseAllDocuments(True)`` still pops that modal in 3DX R2026x when an open
    assembly has a DIRTY referenced child -- e.g. after a ``verify.py --suite
    motion`` run re-solved a child, or an interrupted build left a doc un-saved.
    Headless, that modal hangs the release forever.

    Discard the active docs first (above), then ``CloseAllDocuments(True)`` as a
    backstop -- with nothing dirty left, it has nothing to prompt about.
    """
    _close_active_documents(sw)
    sw.CloseAllDocuments(True)


def _open_and_verify(sw: Any, src: Path, doc_type: int) -> Any:
    """Open ``src`` and return its document, asserting it IS the active doc.

    With every prior document fully closed (see _close_active_documents),
    ``OpenDoc6`` of a non-resident file opens AND displays it, so ``IActiveDoc2``
    is ``src``. The identity assertion is a fail-loud guard: if a document were
    ever left resident, ``OpenDoc6`` would NOT re-display it (per the SolidWorks
    docs: "calling OpenDoc6 does not activate nor display the file [already open in
    memory], [so] IActiveDoc2 will not return a pointer to this document") and
    ``IActiveDoc2`` would point at the stale prior doc -- exactly how v0.8.0 shipped
    summing/magnifier/pen/paper-drive as byte-copies of the harmonic-analyzer
    (hero) render. Crash here rather than silently export a mislabelled
    STEP/STL/PNG.
    """
    sw.OpenDoc6(str(src), doc_type, SW_OPEN_SILENT, "", 0, 0)
    doc = sw.IActiveDoc2
    if doc is None:
        raise RuntimeError(f"failed to open {src.name} (no active document)")
    active = Path(str(doc.GetPathName())).name
    if active.casefold() != src.name.casefold():
        raise RuntimeError(
            f"active document {active!r} != expected {src.name!r} after open"
            f" -- refusing to export a mislabelled STEP/STL/PNG")
    return doc


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
    # prior motion verify) would make CloseAllDocuments(True) prompt.
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
    # suppressed in the active config so no part is dropped from the archive.
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


def _active_config(doc: Any) -> str:
    """Name of the document's active configuration ('' if unreadable)."""
    try:
        ac = doc.ConfigurationManager.ActiveConfiguration
        return str(ac.Name or "") if ac is not None else ""
    except Exception:  # noqa: BLE001
        return ""


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


def _assert_configs_distinct(stem: str, crc_by_mesh: dict[str, str]) -> None:
    """Every configuration of a multi-config part is distinct geometry by design
    (cone-gear / transgear tooth counts all differ). Two configs hashing equal
    means the per-config export captured a stale, un-rebuilt configuration -- fail
    loud rather than ship a mislabelled mesh (the lazy-regenerate race that shipped
    --t18 as 12-tooth in v0.5.1)."""
    if len(crc_by_mesh) < 2:
        return
    seen: dict[str, str] = {}
    for mesh, h in crc_by_mesh.items():
        if h in seen:
            raise RuntimeError(
                f"{stem}: per-config STLs {seen[h]!r} and {mesh!r} are "
                f"byte-identical -- the config switch did not rebuild before "
                f"export; the mesh holds a stale configuration")
        seen[h] = mesh


def _models(folder: Path, ext: str) -> list[Path]:
    """Built documents of one type, excluding SolidWorks ~$ lock files."""
    return sorted(p for p in folder.glob(f"*.{ext}") if not p.name.startswith("~"))


def _cfg_meshes_from_scene() -> dict[str, list[tuple[str, str]]]:
    """part-stem -> [(cfg, mesh)] for the multi-config parts whose configurations are
    distinct geometry the scene graph references (the 20 cone gears, the 3 transgears);
    one-per-part covers everything else. Mesh keys match the scene graph so
    render_offline resolves them."""
    scene = json.loads(SCENE_JSON.read_text(encoding="utf-8"))
    cfg_meshes: dict[str, list[tuple[str, str]]] = {}
    for comp in scene.get("components", []):
        mesh = comp.get("mesh")
        if mesh and mesh != comp["part"]:
            entry = (comp.get("cfg") or "", mesh)
            bucket = cfg_meshes.setdefault(comp["part"], [])
            if entry not in bucket:
                bucket.append(entry)
    return cfg_meshes


def _png_key(src: Path, stl_paths: list[Path], colors_digest: str) -> str:
    """Cache key for a document's PNG set: a fingerprint of exactly what gets rendered.

    Folds the just-exported STL(s) for this document -- the RESOLVED geometry (for an
    assembly the monolithic STL bakes in every child, so a changed child re-renders
    it) -- plus the source SLDPRT/SLDASM bytes (mates + stored appearance) and the
    shared colors.json (any other appearance change), plus the render revision/params.
    A miss can only ever re-render; it can never serve a wrong image."""
    h = hashlib.sha256()
    h.update(PNG_RENDER_REV.encode())
    h.update(repr((PNG_VIEWS, PNG_WIDTH, PNG_HEIGHT)).encode())
    h.update(_sha256(src).encode())
    for p in stl_paths:
        h.update(_sha256(p).encode())
    h.update(colors_digest.encode())
    return h.hexdigest()


def _staged_pngs(doc: Any, stem: str, png_root: Path, key: str) -> bool:
    """Fill ``png_root/stem`` with this document's PNG_VIEWS set. Reuse the cached
    render for ``key`` when present (no SaveBMP); otherwise render the OPEN ``doc`` and
    populate the cache. Returns True on a cache hit. The caller has the doc open for
    STEP/STL regardless, so this saves only the SaveBMP/zoom render work -- but that is
    the bulk of release time, so a geometry-unchanged release skips all 486 renders."""
    cache_dir = PNG_CACHE_DIR / key
    names = [f"{stem}_{view}.png" for view, _ in PNG_VIEWS]
    dst = png_root / stem
    dst.mkdir(parents=True, exist_ok=True)
    if cache_dir.is_dir() and all((cache_dir / n).exists() for n in names):
        for n in names:
            shutil.copy2(cache_dir / n, dst / n)
        return True
    _export_pngs(doc, dst, stem)
    # Publish into the cache atomically (rename) so a crash mid-render never leaves a
    # half-populated key a later run would mistake for a hit.
    tmp = PNG_CACHE_DIR / f"_{key}.partial"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    for n in names:
        shutil.copy2(dst / n, tmp / n)
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    tmp.rename(cache_dir)
    return False


def export_neutral(sw: Any, stage: Path) -> dict[str, Any]:
    """Export every built part and assembly to STEP + STL + PNGs under ``stage``.

    Alongside the Pack-and-Go native files (``stage/solidworks``), this fills the
    *neutral* CAD a consumer without SolidWorks can open -- ``stage/step`` AP214 STEP
    (exact archival B-rep, colours carried), ``stage/stl`` fine binary STL (mm), and
    ``stage/png`` a multi-angle PNG preview set (PNG_VIEWS), one of each per part and
    per assembly. The caller zips the whole ``stage`` into the single release bundle.

    Each document is opened from cad/out and SaveAs3-exported; assemblies write a
    monolithic STL + assembly STEP, multi-config parts (cone gears / transgears) an
    extra STL per referenced config. STEP/STL are exported HERE, not copied from
    cad/out: cad/out is the manifest-driven render cache (per-mesh STLs + only the top
    assembly's STEP -- see export_models), NOT the full 81-document neutral set the
    bundle ships.

    The PNGs -- the bulk of the old release wall time (~550 s / 486 renders) and the
    only step that genuinely needs the seat (SaveBMP of the live viewport) -- are
    CACHED by a resolved-geometry fingerprint (the exported STL(s) + source doc +
    colors.json), so a release whose geometry is unchanged renders nothing. Each file
    is closed with CloseDoc (discards unsaved changes) so an under-defined config that
    re-solves on open never pops a save modal.
    """
    step_dir, stl_dir, png_root = stage / "step", stage / "stl", stage / "png"
    for d in (step_dir, stl_dir, png_root):
        d.mkdir(parents=True, exist_ok=True)
    PNG_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Close the top assembly Pack-and-Go left open BEFORE enumerating: while an
    # assembly is loaded SolidWorks writes a per-component lock file (~$<name>)
    # alongside each .SLDPRT, which would otherwise double the work list.
    _discard_open_documents(sw)

    # parts first (assemblies reference them), each (path, swDocType).
    parts = _models(OUT_SLDPRT, "SLDPRT")
    assemblies = _models(OUT_SLDASM, "SLDASM")
    docs = [(p, SW_DOC_PART) for p in parts] + [(a, SW_DOC_ASSEMBLY) for a in assemblies]
    log(f"neutral export: {len(parts)} parts + {len(assemblies)} assemblies")

    cfg_meshes = _cfg_meshes_from_scene()
    log(f"neutral export: {sum(len(v) for v in cfg_meshes.values())} per-config "
        f"meshes across {len(cfg_meshes)} parts")

    colors_json = OUT_STL / "colors.json"
    colors_digest = _sha256(colors_json) if colors_json.exists() else ""

    old_prefs = _set_export_prefs(sw)
    pngs = cfg_done = hits = 0
    used_keys: set[str] = set()
    try:
        for i, (src, doc_type) in enumerate(docs, 1):
            doc = _open_and_verify(sw, src, doc_type)
            stl_out = stl_dir / f"{src.stem}.STL"
            for out in (step_dir / f"{src.stem}.STEP", stl_out):
                rc = doc.SaveAs3(str(out), 0, SW_SAVE_OPTS)
                if not out.exists() or out.stat().st_size == 0:
                    raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={rc})")
            # one extra STL per referenced configuration (cone gears / transgears)
            stl_paths = [stl_out]
            cfg_crc: dict[str, str] = {}
            for cfg, mesh in cfg_meshes.get(src.stem, ()):
                # ShowConfiguration2 returns False when cfg is ALREADY active (the part
                # opened in it) -- a real failure only if it's still not active after.
                if _active_config(doc) != cfg and not doc.ShowConfiguration2(cfg) \
                        and _active_config(doc) != cfg:
                    raise RuntimeError(f"{src.name}: ShowConfiguration2({cfg!r}) failed")
                # Config switches regenerate LAZILY: force a full rebuild so SaveAs3
                # captures THIS config, not the prior one's stale tessellation (the
                # race that shipped --t18 as 12-tooth geometry in v0.5.1).
                doc.ForceRebuild3(False)
                doc.EditRebuild3()
                out = stl_dir / f"{mesh}.STL"
                rc = doc.SaveAs3(str(out), 0, SW_SAVE_OPTS)
                if not out.exists() or out.stat().st_size == 0:
                    raise RuntimeError(f"SaveAs3 produced no file: {out} (rc={rc})")
                cfg_crc[mesh] = _sha256(out)
                stl_paths.append(out)
                cfg_done += 1
            _assert_configs_distinct(src.stem, cfg_crc)

            # PNGs: reuse the cached render when this doc's resolved geometry is unchanged.
            key = _png_key(src, stl_paths, colors_digest)
            used_keys.add(key)
            if _staged_pngs(doc, src.stem, png_root, key):
                hits += 1
            pngs += len(PNG_VIEWS)

            _close_active_documents(sw)  # CloseDoc -> discards, never prompts
            if i % 10 == 0 or i == len(docs):
                log(f"neutral export: {i}/{len(docs)} documents "
                    f"({pngs} PNGs, {hits} render-cache hits)")
    finally:
        _restore_export_prefs(sw, old_prefs)

    # Prune cache keys not used this run (best-effort): an unused key is geometry no
    # longer in the model; partial dirs are crash leftovers. Never fatal.
    for d in PNG_CACHE_DIR.iterdir():
        if d.is_dir() and d.name not in used_keys:
            shutil.rmtree(d, ignore_errors=True)
    log(f"neutral export: {len(docs) - hits} document(s) rendered on the seat, "
        f"{hits} reused from the PNG cache")

    return {
        "documents": len(docs),
        "parts": len(parts),
        "assemblies": len(assemblies),
        "pngs": pngs,
        "views": len(PNG_VIEWS),
        "config_meshes": cfg_done,
    }


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


def write_provenance(stage: Path, version: str, revision: str,
                     facts: dict[str, Any]) -> dict[str, Any]:
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
            "builder": (f'{_git("config", "--get", "user.name", check_rc=False)} '
                        f'<{_git("config", "--get", "user.email", check_rc=False)}>'),
            "entrypoint": "doit release",
        },
        "model": {
            "documents": facts.get("documents"),
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
    files = sorted(p for p in stage.rglob("*")
                   if p.is_file() and p not in (manifest, prov_json))
    lines = [f"{_sha256(p)}  {p.relative_to(stage).as_posix()}" for p in files]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    prov["integrity"] = {
        "manifest": manifest.name,
        "manifest_sha256": _sha256(manifest),
        "file_count": len(files),
        "algorithm": "sha256",
    }
    prov_json.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    log(f"provenance: commit {prov['git']['commit_short']} "
        f"(tree {'clean' if prov['git']['tree_clean'] else 'DIRTY'}), "
        f"{prov['integrity']['file_count']} files hashed")
    return prov


# --------------------------------------------------------------------------- #
# Bundle assembly (single zip)
# --------------------------------------------------------------------------- #
def bundle(sw: Any, revision: str, version: str,
           prev_tag: str | None = None) -> tuple[Path, dict[str, Any]]:
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

    # 3. Scene graph (mm): per-component transforms + mesh keys + colours, so a
    #    consumer can render the bundle with render_offline.py (no SolidWorks).
    boxes_dst = stage / "boxes"
    boxes_dst.mkdir(exist_ok=True)
    shutil.copy2(SCENE_JSON, boxes_dst / SCENE_JSON.name)
    facts["scene_json"] = SCENE_JSON.name

    # 4. Changed-parts diff render vs the previous release (into stage/diff, so
    #    it ships inside the bundle). Optional: skipped for the first release or
    #    a previous release that predates the neutral bundle.
    facts["diff"] = render_diff(stage, prev_tag) if prev_tag else None

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
    log(f"release bundle: {zip_path.name} ({facts['size_mb']:.1f} MB) -- "
        f"solidworks/ + {facts['documents']} docs x STEP+STL "
        f"(+{facts['config_meshes']} per-config STLs) + {facts['pngs']} PNGs + boxes/")
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
        return (f"\n## Changed parts vs {diff['prev']}\n\n"
                f"No part geometry changed since `{diff['prev']}`.\n")
    base = (f"https://github.com/{_repo_slug()}/releases/download/{version}")
    parts = ", ".join(f"`{p}`" for p in changed)
    imgs = "".join(
        f'<img src="{base}/{name}" width="420" alt="diff {name}">\n'
        for name in diff.get("images", [])[:2])
    extra = diff.get("images", [])[2:]
    more = ("".join(f'<img src="{base}/{n}" width="420">\n' for n in extra))
    return (
        f"\n## Changed parts vs {diff['prev']}\n\n"
        f"**{len(changed)} part(s)** changed geometry "
        f"(red = changed, confirmed by Hausdorff distance; tessellation/byte "
        f"noise excluded): {parts}\n\n"
        f"{imgs}"
        + (f"<details><summary>more views</summary>\n\n{more}</details>\n"
           if extra else "")
        + "\n_Generated by `comparisons/tools/render_diff.py`; renders also ship "
        "in the bundle under `diff/`._\n")


def release_notes(version: str, facts: dict[str, Any]) -> str:
    return (
        f"Scripted SolidWorks reproduction of Michelson's 20-channel harmonic "
        f"analyzer.\n\n"
        f"The repository is source-of-truth (`doit` regenerates every "
        f"part). This release attaches a single **CAD bundle** "
        f"`harmonic-analyzer-{version}.zip` so the model can be opened without "
        f"rebuilding -- with or without SolidWorks:\n\n"
        f"- `solidworks/` -- native Pack-and-Go ({facts['documents']} referenced "
        f"documents, flattened): open `{TOP_ASSEMBLY}.SLDASM` as-is\n"
        f"- `step/` -- AP214 STEP + `stl/` fine binary STL (mm), one per "
        f"document ({facts['parts']} parts + {facts['assemblies']} assemblies) "
        f"plus {facts['config_meshes']} per-configuration STLs (cone gears / "
        f"transgears)\n"
        f"- `boxes/{TOP_ASSEMBLY}.json` -- assembly scene graph (mm): per-component "
        f"transform, mesh key and colour, so the comparison gallery renders from "
        f"this bundle with `comparisons/tools/render_offline.py` (no SolidWorks)\n"
        f"- `png/` -- {facts['views']}-angle preview renders "
        f"({facts['pngs']} images)\n"
        + (f"- `diff/` -- changed-parts diff renders vs "
           f"{facts['diff']['prev']} (see below)\n" if facts.get("diff") else "")
        + f"- Size: {facts['size_mb']:.1f} MB\n"
        + _diff_section(version, facts.get("diff"))
        + "\n**Provenance**\n"
        + _provenance_section(facts)
        + (f"\n**Logs**: `{facts['logs_asset']}` -- the per-task build logs "
           f"(parts, assemblies, verify/check gates) plus the full release log -- "
           f"is attached as a separate asset.\n" if facts.get("logs_asset") else "")
    )


def _provenance_section(facts: dict[str, Any]) -> str:
    """Human-readable provenance for the release notes, mirroring the machine
    ``PROVENANCE.json`` that ships inside the bundle."""
    prov = facts.get("provenance") or {}
    git = prov.get("git", {})
    integ = prov.get("integrity", {})
    commit = git.get("commit", "")
    remote = git.get("remote", "")
    link = (f"[`{git.get('commit_short', sha_fallback(commit))}`]"
            f"({remote}/commit/{commit})" if commit else f"`{sha_fallback(commit)}`")
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
    log(f"logs: {len(logs)} files -> {zip_path.name} "
        f"({zip_path.stat().st_size / 1e3:.0f} KB)")
    return zip_path


def _gh_assets(version: str, zip_path: Path, facts: dict[str, Any],
               log_path: Path | None) -> list[str]:
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


def publish(version: str, zip_path: Path, facts: dict[str, Any], draft: bool,
            log_path: Path | None = None) -> str:
    """Annotated tag -> push -> gh release + asset upload. Returns release URL."""
    log(f"tagging {version} at HEAD")
    _git("tag", "-a", version, "-m", f"Release {version}")
    _git("push", "origin", version)

    assets = _gh_assets(version, zip_path, facts, log_path)
    args = [
        "release", "create", version, *assets,
        "--title", f"harmonic-analyzer {version}",
        "--notes", release_notes(version, facts),
    ]
    if draft:
        args.append("--draft")
    url = _gh(*args)
    log(f"release published: {url}")
    return url


def report_no_publish(version: str, zip_path: Path, facts: dict[str, Any],
                      log_path: Path | None = None) -> None:
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
    ap.add_argument("version", nargs="?", help="release tag vX.Y.Z (default: auto-bump)")
    ap.add_argument("--bump", choices=("major", "minor", "patch"), default="patch",
                    help="how to bump the latest tag when version is omitted")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="tag even with uncommitted (tracked) changes")
    ap.add_argument("--draft", action="store_true",
                    help="create the GitHub release as a draft")
    ap.add_argument("--no-publish", action="store_true",
                    help="build the bundle + logs zip but do NOT tag/push/gh "
                         "(dry run -- nothing leaves the machine)")
    opts = ap.parse_args()

    version = resolve_version(opts.version, opts.bump)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    # Tee everything below to the per-version release log BEFORE preflight, so the
    # asset captures the whole run (including a preflight bail-out). restore() in
    # the finally puts the real streams back and closes the file no matter what.
    log_path, restore = _start_release_log(version)
    try:
        # Wrap the whole release in a span; run_pipeline_span extracts the
        # TRACEPARENT dodo._run injected (under `doit release`), so the release
        # COM work + logs continue the doit task span instead of being detached.
        with _telemetry.run_pipeline_span("release", version=version) as rel:
            _telemetry.info(f"cutting release {version}")
            preflight(version, opts.allow_dirty)

            prev = previous_tag(version)
            log(f"previous release for diff: {prev or '(none -- first bundle)'}")

            started = time.perf_counter()
            try:
                sw, revision = attach_solidworks()
                zip_path, facts = bundle(sw, revision, version, prev)
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
                url = publish(version, zip_path, facts, opts.draft, log_path)
            _telemetry.success(f"Done in {time.perf_counter() - started:.1f}s.")
            _telemetry.info(f"version: {version}")
            _telemetry.info(f"bundle:  {zip_path} ({facts['size_mb']:.1f} MB) -- solidworks/ + "
                            f"{facts['documents']} docs x STEP+STL (+{facts['config_meshes']} "
                            f"per-config) + {facts['pngs']} PNGs + boxes/")
            _telemetry.info(f"log:     {log_path}")
            if facts.get("logs_asset"):
                _telemetry.info(f"logs:    {RELEASE_DIR / facts['logs_asset']}")
            _telemetry.info(f"release: {url or '(--no-publish: not published)'}")
            return 0
    finally:
        restore()


if __name__ == "__main__":
    sys.exit(main())
