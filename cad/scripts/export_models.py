"""Export one complete recipe-keyed neutral cache: STL + STEP + scene + GLB.

doit task: ``export`` (on the COM spine). Normally invoked via ``doit export``
or as a prerequisite of ``doit release``; runnable standalone too.


For every built part: AP214 STEP, per-part STL, and the build-owned isometric
PNG certified in ``reports/release-neutral.json``. For every built assembly:
a boxes/scene JSON and a composed glTF binary. The release task validates and
stages that complete set without reopening native documents. This is also the
offline-render feed consumed by render_offline.py —

* parts: fine binary STL in MILLIMETRES, untranslated (cad/out/stl/<dashed>.STL)
  plus an appearance colour in cad/out/stl/colors.json;
* assemblies: cad/out/gltf/<dashed>.glb — SolidWorks' own glTF exporter
  (SaveAs3, format inferred from the .glb extension; SW2023+), which carries
  metre units, per-component nodes named after the components, and the
  appearance colours as glTF materials — plus cad/out/boxes/<dashed>.json with
  per-component bounding boxes (framing) and a scene graph: one entry per
  visible leaf component with its part stem, assembly-space transform
  (IMathTransform.ArrayData, row-vector convention, translation in
  millimetres) and RGB. The old monolithic per-assembly STL SaveAs3 is
  retired — nothing ever read its mesh bytes, and the GLB carries colours +
  component identity it never had. (The scene JSON is slated to be retired in
  favour of reading the GLB directly — issue #338.) Every referenced part gets
  its own STL, shared across assemblies and instanced by the Blender worker
  (so 20 cone gears cost one mesh). STL geometry is in millimetres (mesh
  units == the scene-graph transform units, so they pair directly).

Colours cascade: component-level override -> part doc colour -> the
material-name table below (the build scripts only ever assign database
materials) -> gray.

Run after any --rebuild so the render cache tracks geometry:

    uv run python cad\\scripts\\export_models.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CAD_ROOT,
    PREF_STL_QUALITY,
    PREF_STL_UNITS,
    TOGGLE_STL_BINARY,
    TOGGLE_STL_NO_TRANSLATE,
    TOGGLE_STL_ONE_FILE,
    TOGGLE_STL_SHOW_INFO,
    _early_bound,
    _read_member,
    check,
    log,
    run_build,
    set_isometric_view,
)
from _buildgraph import ASSEMBLY_ORDER, part_stems  # noqa: E402

import _telemetry  # noqa: E402

OUT_GLTF = CAD_ROOT / "out" / "gltf"
OUT_STL = CAD_ROOT / "out" / "stl"
OUT_STEP = CAD_ROOT / "out" / "step"
OUT_BOXES = CAD_ROOT / "out" / "boxes"
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
OUT_SLDASM = CAD_ROOT / "out" / "sldasm"
OUT_PNG = CAD_ROOT / "out" / "png"
COLORS = OUT_STL / "colors.json"
# Per-output source-recipe digests: ``mesh|dashed-assembly -> digest`` recorded at
# export time so a re-export fires iff the SOURCE's recipe changed. Keyed on doit's
# churn-immune ``_stable_artefact_digest`` (below), NOT the .SLDPRT/.SLDASM mtime,
# which SolidWorks bumps on every save-cascade / cache-restore and made every export
# look stale each release.
SRC_DIGESTS = OUT_STL / "export-src.json"
# Sentinel key in that file recording the EXPORTER's own version (this module's
# source). The per-source recipe digest is blind to the export/format/scene/colour
# logic here, so without this a change to the exporter would leave every output
# looking fresh and ship stale STEP/STL/scene JSON (codex review). A sentinel
# mismatch invalidates the whole cache -> full regeneration through the new logic.
_EXPORTER_KEY = "__exporter__"
NEUTRAL_MANIFEST = CAD_ROOT / "out" / "reports" / "release-neutral.json"
NEUTRAL_SCHEMA = "harmonic-analyzer/release-neutral@3"
TOP_ASSEMBLY = "harmonic-analyzer"

# Comparison gallery, produced by THIS export stage from the STLs written above
# (so `doit export` yields an up-to-date gallery for the release to bundle). Both
# are PEP-723 scripts run via `uv run`; render_offline drives Blender (no
# SolidWorks). See refresh_comparison_gallery -- best-effort (Blender is on a
# separate GPU seat), and cut_release.stage_comparisons ships the result.
REPO = CAD_ROOT.parent
COMPARISONS_DIR = CAD_ROOT / "comparisons"
RENDER_OFFLINE = COMPARISONS_DIR / "tools" / "render_offline.py"
BLENDER_WORKER = COMPARISONS_DIR / "tools" / "blender_worker.py"
COMPOSITE_PY = COMPARISONS_DIR / "tools" / "composite.py"
GALLERY_PY = COMPARISONS_DIR / "tools" / "gallery.py"
GALLERY_STAMP = CAD_ROOT / "out" / "reports" / "comparison-gallery.json"

# swconst ids (extracted from the installed swconst.tlb, R2026x). The STL ids
# live in _common (shared with the part-build STL export); STEP is export-only.
PREF_STEP_AP = 75            # int: swStepAP -> 214 (carries colours)

# Workbench-friendly equivalents of the SolidWorks material appearances
# actually used by the build scripts (see _common.apply_material).
MATERIAL_RGB = {
    "plain carbon steel": (0.55, 0.56, 0.57),
    "brass": (0.72, 0.60, 0.30),
    "gray cast iron": (0.38, 0.39, 0.40),
    "alloy steel": (0.48, 0.50, 0.52),
    "chrome stainless steel": (0.78, 0.79, 0.80),
    "oak": (0.62, 0.44, 0.24),
}
DEFAULT_RGB = (0.55, 0.55, 0.55)

INT_PREFS = {PREF_STL_QUALITY: 2, PREF_STEP_AP: 214, PREF_STL_UNITS: 0}
TOGGLES = {TOGGLE_STL_BINARY: True, TOGGLE_STL_ONE_FILE: True, TOGGLE_STL_NO_TRANSLATE: True}
TOGGLES[TOGGLE_STL_SHOW_INFO] = False
SW_SAVE_OPTS = 1 | 8  # swSaveAsOptions_Silent | AvoidRebuildOnSave


def _nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _certified_outputs() -> dict[Path, dict[str, Any]]:
    """Return source-path keyed records from the current neutral certificate.

    A certificate from another exporter revision is not evidence about this
    exporter's bytes: ``exporter_untrusted`` already forces those outputs to be
    regenerated.  Malformed or partial certificates likewise contribute no
    freshness evidence and are replaced after a successful export.
    """
    try:
        manifest = json.loads(NEUTRAL_MANIFEST.read_text(encoding="utf-8"))
        if (manifest.get("schema") != NEUTRAL_SCHEMA
                or manifest.get("exporter") != _exporter_digest()):
            return {}
        records = manifest.get("files")
        if not isinstance(records, dict):
            return {}
        certified: dict[Path, dict[str, Any]] = {}
        for record in records.values():
            if not isinstance(record, dict) or not record.get("source"):
                return {}
            certified[(REPO / str(record["source"])).resolve()] = record
        return certified
    except Exception:
        return {}


def _certified_output_changed(
    path: Path, certified: dict[Path, dict[str, Any]],
    cache: dict[Path, bool] | None = None,
) -> bool:
    """True when an existing certificate proves ``path`` was modified.

    Source recipe digests establish *which geometry* should have been exported;
    this check establishes that the already-exported bytes still are the bytes
    that were certified.  Without both, a same-recipe cache corruption could be
    hashed into a replacement certificate and silently become trusted.
    """
    resolved = path.resolve()
    if cache is not None and resolved in cache:
        return cache[resolved]
    record = certified.get(resolved)
    if record is None:
        if cache is not None:
            cache[resolved] = True
        return True
    changed = (
        not _nonempty(path)
        or path.stat().st_size != record.get("bytes")
        or _file_sha256(path) != record.get("sha256")
    )
    if cache is not None:
        cache[resolved] = changed
    return changed


def _png_needs_export(
    path: Path, force: bool, neutral_changed: Callable[[Path], bool],
) -> bool:
    return force or not _nonempty(path) or bool(neutral_changed(path))


def manifest_models() -> list[str]:
    manifest = json.loads(
        (CAD_ROOT / "comparisons" / "manifest.json").read_text(encoding="utf-8")
    )
    return sorted({p["model"] for p in manifest["pairs"]})


def set_export_prefs(adapter: Any) -> dict:
    sw = adapter.swApp
    old = {
        "ints": {k: int(sw.GetUserPreferenceIntegerValue(k)) for k in INT_PREFS},
        "toggles": {k: bool(sw.GetUserPreferenceToggle(k)) for k in TOGGLES},
    }
    for k, v in INT_PREFS.items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in TOGGLES.items():
        sw.SetUserPreferenceToggle(k, v)
    log(f"export prefs set (were {old})")
    return old


def restore_export_prefs(adapter: Any, old: dict) -> None:
    sw = adapter.swApp
    for k, v in old["ints"].items():
        sw.SetUserPreferenceIntegerValue(k, v)
    for k, v in old["toggles"].items():
        sw.SetUserPreferenceToggle(k, v)


def _valid_rgb(values: Any) -> tuple[float, float, float] | None:
    try:
        r, g, b = (float(v) for v in values[:3])
    except Exception:
        return None
    if all(0.0 <= v <= 1.0 for v in (r, g, b)):
        return r, g, b
    return None  # SolidWorks reports -1 for "unset"


def doc_rgb(doc: Any) -> tuple[float, float, float]:
    """Part-doc colour: explicit colour override, else material-name table."""
    rgb = _valid_rgb(_read_member(doc, "MaterialPropertyValues") or ())
    if rgb:
        return rgb
    doc = _early_bound(doc, "IPartDoc")
    name = ""
    try:
        # Early-bound IPartDoc::GetMaterialPropertyName2(ConfigName) returns the
        # material name as the retval plus the [out] Database in the tuple
        # (name, database). ConfigName "" = active config. Passing a second
        # positional (the old dummy Database) collides with the [out] byref slot.
        res = doc.GetMaterialPropertyName2("")
        names = list(res) if isinstance(res, (tuple, list)) else [res]
        # pywin32 may return (name, [out] database) in either order
        name = next((s for s in names
                     if isinstance(s, str) and s.strip().lower() in MATERIAL_RGB), "")
    except Exception:
        pass
    return MATERIAL_RGB.get(name.strip().lower(), DEFAULT_RGB)


def comp_rgb(comp: Any) -> tuple[float, float, float] | None:
    """Component-level appearance override, or None when unset.

    Most components carry NO override (SolidWorks displays the part-doc
    colour cascade), so None is the common case — the scene writer fills it
    from the part-doc colours after the part exports refresh them."""
    try:
        return _valid_rgb(comp.GetMaterialPropertyValues2(1, None) or ())
    except Exception:
        return None


def _safe_cfg(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.strip().lower()).strip("-")


def mesh_key(stem: str, cfg: str) -> str:
    """STL cache key: configured components get their own mesh per config
    (e.g. the 20 cone gears are one part with 20 tooth-count configs).
    Separator is a double dash — SolidWorks SaveAs3 rejects '@' in file
    names (swFileSaveError 8, swFileNameContainsAtSign)."""
    if not cfg or cfg.lower() == "default":
        return stem
    return f"{stem}--{_safe_cfg(cfg)}"


def comp_xform(comp: Any) -> list[float] | None:
    try:
        xf = _read_member(comp, "Transform2")
        arr = _read_member(xf, "ArrayData") if xf is not None else None
        if arr and len(arr) >= 13:
            return [float(v) for v in arr[:13]]
    except Exception:
        pass
    try:  # deprecated but math-object-free
        arr = comp.GetXform()
        if arr and len(arr) >= 13:
            return [float(v) for v in arr[:13]]
    except Exception:
        pass
    return None


def scan_assembly(adapter: Any, part_colors: dict) -> tuple[list, list, set[tuple]]:
    """(boxes, scene components, referenced (stem, cfg, mesh) keys).

    The SolidWorks API reports boxes and transforms in metres (system units);
    they are scaled to MILLIMETRES here so the persisted scene graph matches the
    millimetre STL meshes it is rendered against."""
    model = _early_bound(adapter.currentModel, "IAssemblyDoc")  # IAssemblyDoc for GetComponents (same dispatch)
    comps = model.GetComponents(False) or []
    boxes, scene, stems = [], [], set()
    for i, comp in enumerate(comps, 1):
        if i % 50 == 0:
            log(f"component scan {i}/{len(comps)} ...")
        # Early-bind to IComponent2 so the members read below (GetPathName,
        # GetXform, Name2/Visible/Transform2 properties, GetBox/GetModelDoc2/
        # GetMaterialPropertyValues2) invoke by DISPID; off-interface members
        # fall through the wrapper's late-bound fallback.
        comp = _early_bound(comp, "IComponent2")
        try:
            name = str(_read_member(comp, "Name2") or "")
            box = comp.GetBox(False, False)
        except Exception:
            continue
        if not box:
            continue  # suppressed / no graphics
        short = name.split("/")[-1].lower()
        boxes.append((short, tuple(float(v) * 1000.0 for v in box)))  # m -> mm
        try:
            path = Path(str(comp.GetPathName()))
        except Exception:
            continue
        if path.suffix.lower() != ".sldprt":
            continue  # subassembly containers: their children scan separately
        if not bool(_read_member(comp, "Visible")):
            continue
        xform = comp_xform(comp)
        if not xform:
            log(f"  !! no transform for {name}, skipped")
            continue
        # translation (xform[9:12]) m -> mm; rotation [0:9] and scale [12] unitless
        xform = [*xform[:9], xform[9] * 1000.0, xform[10] * 1000.0,
                 xform[11] * 1000.0, *xform[12:]]
        stem = path.stem.lower()
        cfg = str(_read_member(comp, "ReferencedConfiguration") or "")
        mesh = mesh_key(stem, cfg)
        if mesh not in part_colors:
            # Opportunistic part-doc read: GetModelDoc2 returns None for a
            # LIGHTWEIGHT component — seed nothing then, so a lightweight scan
            # can't pollute colors.json with defaults; the scene writer fills
            # missing colours from the part exports' authoritative doc reads.
            try:
                doc = comp.GetModelDoc2()
                if doc:
                    part_colors[mesh] = doc_rgb(doc)
            except Exception:
                pass
        stems.add((stem, cfg, mesh))
        override = comp_rgb(comp)
        scene.append({
            "name": short,
            "part": stem,
            "cfg": cfg,
            "mesh": mesh,
            "xform": xform,
            "rgb": list(override) if override else None,
        })
    return boxes, scene, stems


def load_colors() -> dict:
    if COLORS.exists():
        try:
            return {k: tuple(v) for k, v in
                    json.loads(COLORS.read_text(encoding="utf-8")).items()}
        except Exception:
            _telemetry.warn(f"invalid colours cache will be rebuilt: {COLORS}")
    return {}


def save_colors(colors: dict) -> None:
    COLORS.write_text(json.dumps(
        {k: list(v) for k, v in sorted(colors.items())}, indent=1), encoding="utf-8")


def _exporter_digest() -> str:
    """Digest of the exporter's own source CLOSURE -- this module plus every repo-local
    helper it transitively imports (_common's STL
    preference constants, ...) -- stamped into the cache so a change to ANY export /
    format / scene / colour logic invalidates every recorded output even when no CAD
    recipe changed (codex review). Best-effort: if the closure can't be resolved, fall
    back to this module alone; if even that can't be read, '' (a stable, round-tripping
    value) -- never blocking an export."""
    self_path = Path(__file__).resolve()
    try:
        from _buildgraph import module_deps_of
        files = sorted({self_path, *(Path(p).resolve()
                                     for p in module_deps_of(self_path))})
        h = hashlib.md5()
        for f in files:
            h.update(f.read_bytes())
        return h.hexdigest()
    except Exception:
        try:
            return hashlib.md5(self_path.read_bytes()).hexdigest()
        except Exception:
            return ""


def load_src_digests() -> dict[str, str]:
    """Recorded source digests -- but ONLY if written by this same exporter version.
    A changed exporter (its ``__exporter__`` sentinel no longer matches) invalidates
    the whole cache, so every output regenerates through the new format logic."""
    if not SRC_DIGESTS.exists():
        return {}
    try:
        data = dict(json.loads(SRC_DIGESTS.read_text(encoding="utf-8")))
    except Exception:
        # ANY unusable sidecar -- unreadable, invalid JSON, or valid-but-not-an-object
        # (`null`/`0` -> dict() TypeError) from an interrupted save / partial copy --
        # must not abort the export. Return {} so the untrusted/force path regenerates
        # and rewrites a valid file (mirrors exporter_untrusted's broad guard).
        return {}
    if data.pop(_EXPORTER_KEY, None) != _exporter_digest():
        return {}
    return data


def save_src_digests(digests: dict[str, str]) -> None:
    out = {k: v for k, v in digests.items() if k != _EXPORTER_KEY}
    out[_EXPORTER_KEY] = _exporter_digest()
    SRC_DIGESTS.write_text(
        json.dumps(dict(sorted(out.items())), indent=1), encoding="utf-8")


def exporter_untrusted() -> bool:
    """True when the existing outputs are NOT known to have been produced by THIS
    exporter version -- the ``export-src.json`` sentinel is absent (first run, or the
    cache was deleted) OR does not match the current exporter/helper closure.
    ``load_src_digests`` already empties the digest map on a mismatch, which re-exports
    every DECLARED target (its recipe digest no longer matches ``{}``) -- but an
    UNDECLARED target (a generated stretch-spring mesh, ``src_digest`` -> None) is
    mtime-gated and ignores the map, so an old STL newer than its ``.SLDPRT`` would still
    read fresh. main() folds this into ``force`` so an untrusted cache regenerates EVERY
    mesh through the current logic (codex review). A missing sentinel counts as untrusted
    because pre-sentinel outputs carry no proof of which exporter made them."""
    if not SRC_DIGESTS.exists():
        return True
    try:
        stored = json.loads(SRC_DIGESTS.read_text(encoding="utf-8")).get(_EXPORTER_KEY)
    except Exception:
        return True
    return stored != _exporter_digest()


def _import_dodo() -> Any:
    """dodo.py (repo root, off cad/scripts' path) is doit's build graph plus the
    exact recipe digest its ContentChecker + remote-cache key use. Reusing it makes
    export's staleness immune to SolidWorks' save-metadata byte churn and cache-restore
    mtime churn -- the same reason verify.py's freshness guard imports dodo -- so a
    part/assembly re-exports iff doit itself would consider it rebuilt. export_models.py
    always runs as its own process, so this never races the orchestrator."""
    repo_root = str(CAD_ROOT.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    import dodo  # noqa: PLC0415

    return dodo


def src_digest(src: Path) -> str | None:
    """Churn-immune recipe digest of a built ``.SLDPRT``/``.SLDASM`` (``None`` when it
    is not a declared build target -- the caller then falls back to mtime)."""
    try:
        return _import_dodo()._stable_artefact_digest(str(src.resolve()))
    except Exception:
        return None


def scene_part_meshes(scene_path: Path | None = None) -> dict[str, list[tuple[str, str]]]:
    """Return every ``(configuration, mesh)`` referenced by a scene.

    The release inventory is derived from the scene graph instead of duplicating a
    cone/transgear configuration registry.  A missing or malformed scene is never
    interpreted as an empty set: that would silently omit configured or assembly-
    generated meshes.
    """
    path = scene_path or OUT_BOXES / f"{TOP_ASSEMBLY}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("unit") != "mm":
        raise RuntimeError(f"release scene has invalid/missing mm unit: {path}")
    components = data.get("components")
    if not isinstance(components, list) or not components:
        raise RuntimeError(f"release scene has no components: {path}")
    by_stem: dict[str, list[tuple[str, str]]] = {}
    for comp in components:
        stem = str(comp.get("part") or "")
        mesh = str(comp.get("mesh") or "")
        if not stem or not mesh:
            raise RuntimeError(f"release scene component lacks part/mesh: {comp!r}")
        entry = (str(comp.get("cfg") or ""), mesh)
        bucket = by_stem.setdefault(stem, [])
        if entry not in bucket:
            bucket.append(entry)
    return {stem: sorted(entries) for stem, entries in sorted(by_stem.items())}


def all_scene_part_meshes(
    scene_assemblies: set[str],
) -> dict[str, list[tuple[str, str]]]:
    """Union the mesh inventories of every comparison scene assembly."""
    by_stem: dict[str, list[tuple[str, str]]] = {}
    for assembly in sorted(scene_assemblies):
        dashed = assembly.replace("_", "-")
        for stem, entries in scene_part_meshes(OUT_BOXES / f"{dashed}.json").items():
            bucket = by_stem.setdefault(stem, [])
            for entry in entries:
                if entry not in bucket:
                    bucket.append(entry)
    return {stem: sorted(entries) for stem, entries in sorted(by_stem.items())}


def scene_is_valid(scene_path: Path) -> bool:
    try:
        scene_part_meshes(scene_path)
    except Exception:
        return False
    return True


def scene_sources_exist(scene_path: Path) -> bool:
    """Whether every part named by a parseable scene still has a native source.

    A missing mesh can be repaired by reopening its part.  A missing part source
    means the cached scene itself names a retired/bogus component, so its owning
    assembly must be rescanned instead of attempting to open a nonexistent file.
    """
    try:
        stems = scene_part_meshes(scene_path)
    except Exception:
        return False
    return all((OUT_SLDPRT / f"{stem}.SLDPRT").is_file() for stem in stems)


def scene_config_meshes(scene_path: Path | None = None) -> dict[str, list[tuple[str, str]]]:
    """The scene's non-default mesh aliases (23 cone/transgear configurations)."""
    return {
        stem: [(cfg, mesh) for cfg, mesh in entries if mesh != stem]
        for stem, entries in scene_part_meshes(scene_path).items()
        if any(mesh != stem for _cfg, mesh in entries)
    }


def _release_inventory(
    parts: list[str], assemblies: list[str], scene_meshes: dict[str, list[tuple[str, str]]],
    scene_assemblies: set[str],
) -> dict[str, Path]:
    """Exact bundle-relative neutral inventory and its cache-owned source files."""
    files: dict[str, Path] = {}
    for stem in parts:
        dashed = stem.replace("_", "-")
        files[f"step/{dashed}.STEP"] = OUT_STEP / f"{dashed}.STEP"
        files[f"stl/{dashed}.STL"] = OUT_STL / f"{dashed}.STL"
        files[f"png/{dashed}/{dashed}_isometric.png"] = (
            OUT_PNG / dashed / f"{dashed}_isometric.png"
        )
    for stem in assemblies:
        dashed = stem.replace("_", "-")
        files[f"gltf/{dashed}.glb"] = OUT_GLTF / f"{dashed}.glb"
        files[f"png/{dashed}/{dashed}_isometric.png"] = (
            OUT_PNG / dashed / f"{dashed}_isometric.png"
        )
    for entries in scene_meshes.values():
        for _cfg, mesh in entries:
            files[f"stl/{mesh}.STL"] = OUT_STL / f"{mesh}.STL"
    for stem in sorted(scene_assemblies):
        dashed = stem.replace("_", "-")
        files[f"boxes/{dashed}.json"] = OUT_BOXES / f"{dashed}.json"
    return dict(sorted(files.items()))


def _release_sources(
    parts: list[str], assemblies: list[str],
    scene_meshes: dict[str, list[tuple[str, str]]] | None = None,
) -> dict[str, Path]:
    sources = {
        stem.replace("_", "-"): OUT_SLDPRT / f"{stem.replace('_', '-')}.SLDPRT"
        for stem in parts
    }
    sources.update({
        stem.replace("_", "-"): OUT_SLDASM / f"{stem.replace('_', '-')}.SLDASM"
        for stem in assemblies
    })
    for stem in (scene_meshes or {}):
        sources.setdefault(stem, OUT_SLDPRT / f"{stem}.SLDPRT")
    return dict(sorted(sources.items()))


def _source_fingerprint(source: Path) -> str | None:
    if not source.is_file():
        return None
    recipe = src_digest(source)
    if recipe is not None:
        return recipe
    return _file_sha256(source)


def write_release_neutral_manifest(
    parts: list[str], assemblies: list[str],
    scene_meshes: dict[str, list[tuple[str, str]]],
    scene_assemblies: set[str],
    colors: dict[str, Any], digests: dict[str, str],
) -> None:
    """Atomically certify a complete, current neutral set for ``cut_release``.

    The exporter writes this only after every requested SaveAs and configuration
    distinctness guard succeeds.  Source recipe digests prove freshness without
    trusting volatile SolidWorks mtimes; exact file names, sizes, and hashes prove the
    set is complete and unchanged.  PNGs are the render outputs owned by the
    corresponding build tasks.
    """
    sources = _release_sources(parts, assemblies, scene_meshes)
    source_records: dict[str, str] = {}
    for dashed, source in sources.items():
        if not source.is_file():
            raise RuntimeError(f"release neutral source missing: {source}")
        current = _source_fingerprint(source)
        recipe = src_digest(source)
        if current is None or (recipe is not None and digests.get(dashed) != recipe):
            raise RuntimeError(
                f"release neutral source is not export-current: {source.name}"
            )
        source_records[dashed] = current
    for stem, entries in scene_meshes.items():
        source = OUT_SLDPRT / f"{stem}.SLDPRT"
        recipe = src_digest(source)
        if source_records.get(stem) is None:
            raise RuntimeError(f"release scene references non-manifest part: {stem}")
        for _cfg, mesh in entries:
            fresh = (digests.get(mesh) == recipe if recipe is not None
                     else not part_stl_stale(stem, mesh, colors, digests))
            if not fresh:
                raise RuntimeError(f"release scene mesh is stale: {mesh}")

    inventory = _release_inventory(parts, assemblies, scene_meshes, scene_assemblies)
    file_records: dict[str, dict[str, Any]] = {}
    for destination, source in inventory.items():
        if not source.is_file() or source.stat().st_size == 0:
            raise RuntimeError(f"release neutral output missing/empty: {source}")
        file_records[destination] = {
            "source": source.resolve().relative_to(REPO.resolve()).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": _file_sha256(source),
        }

    manifest = {
        "schema": NEUTRAL_SCHEMA,
        "exporter": _exporter_digest(),
        "sources": source_records,
        "files": file_records,
    }
    NEUTRAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temporary = NEUTRAL_MANIFEST.with_suffix(".json.partial")
    temporary.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    temporary.replace(NEUTRAL_MANIFEST)
    _telemetry.event(
        "export.neutral_manifest",
        documents=len(sources),
        files=len(file_records),
        config_meshes=sum(
            mesh != stem for stem, entries in scene_meshes.items()
            for _cfg, mesh in entries
        ),
    )


def _validate_release_sources(
    expected: dict[str, Path], recorded: dict[str, str],
) -> None:
    with _telemetry.span("release.neutral_validate_sources", documents=len(expected)):
        for dashed, source in expected.items():
            current = _source_fingerprint(source)
            if current is None or recorded.get(dashed) != current:
                raise RuntimeError(
                    f"release neutral source changed: {source.name}; rerun doit export"
                )


def _copy_release_files(
    stage: Path, expected: dict[str, Path], recorded: dict[str, dict[str, Any]],
) -> None:
    with _telemetry.span("release.neutral_copy", files=len(expected)):
        for destination, expected_source in expected.items():
            record = recorded[destination]
            source = REPO / str(record.get("source") or "")
            if source.resolve() != expected_source.resolve():
                raise RuntimeError(f"release neutral source path drifted for {destination}")
            if not _nonempty(source) or source.stat().st_size != record.get("bytes"):
                raise RuntimeError(f"release neutral output changed: {source}; rerun doit export")
            output = stage / destination
            output.parent.mkdir(parents=True, exist_ok=True)
            partial = output.with_name(f"{output.name}.partial")
            partial.unlink(missing_ok=True)
            digest = hashlib.sha256()
            try:
                with source.open("rb") as src, partial.open("wb") as dst:
                    for chunk in iter(lambda: src.read(1 << 20), b""):
                        digest.update(chunk)
                        dst.write(chunk)
                if digest.hexdigest() != record.get("sha256"):
                    raise RuntimeError(
                        f"release neutral output digest changed: {source}; "
                        "rerun doit export"
                    )
                shutil.copystat(source, partial)
                partial.replace(output)
            except Exception:
                partial.unlink(missing_ok=True)
                raise


def stage_release_neutral(stage: Path) -> dict[str, int]:
    """Validate and copy the certified neutral set without touching SolidWorks."""
    try:
        manifest = json.loads(NEUTRAL_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"release neutral manifest missing/unreadable: {NEUTRAL_MANIFEST}; "
            "run `uv run python -m doit export`"
        ) from exc
    if manifest.get("schema") != NEUTRAL_SCHEMA:
        raise RuntimeError("release neutral manifest schema is stale; rerun doit export")
    if manifest.get("exporter") != _exporter_digest():
        raise RuntimeError("release neutral exporter changed; rerun doit export")

    parts = part_stems()
    assemblies = list(ASSEMBLY_ORDER)
    # Every assembly is scene-bearing: each ships a boxes/scene JSON + a GLB
    # composed from it (the old manifest-only subset predated the GLB export).
    scene_assemblies = set(assemblies)
    scene_meshes = all_scene_part_meshes(scene_assemblies)
    cfg_meshes = {
        stem: [(cfg, mesh) for cfg, mesh in entries if mesh != stem]
        for stem, entries in scene_meshes.items()
        if any(mesh != stem for _cfg, mesh in entries)
    }
    expected_sources = _release_sources(parts, assemblies, scene_meshes)
    recorded_sources = manifest.get("sources")
    if not isinstance(recorded_sources, dict) or set(recorded_sources) != set(expected_sources):
        raise RuntimeError("release neutral source inventory drifted; rerun doit export")

    expected_files = _release_inventory(
        parts, assemblies, scene_meshes, scene_assemblies,
    )
    recorded_files = manifest.get("files")
    if not isinstance(recorded_files, dict) or set(recorded_files) != set(expected_files):
        raise RuntimeError("release neutral file inventory drifted; rerun doit export")

    with _telemetry.span(
        "release.neutral_stage",
        documents=len(expected_sources),
        files=len(expected_files),
    ) as sp:
        _validate_release_sources(expected_sources, recorded_sources)
        _copy_release_files(stage, expected_files, recorded_files)
        sp.set_attribute("config_meshes", sum(len(v) for v in cfg_meshes.values()))

    return {
        "documents": len(expected_sources),
        "parts": len(parts),
        "assemblies": len(assemblies),
        "pngs": len(parts) + len(assemblies),
        "views": 1,
        "config_meshes": sum(len(entries) for entries in cfg_meshes.values()),
    }


def _save_as(doc: Any, out: Path) -> int:
    """SaveAs3 to ``out``, guaranteeing THIS call produced a REAL file: remove any prior
    output first, so a SaveAs3 that fails (a locked / read-only path) leaves NO file and
    raises -- instead of silently leaving a stale export that the existence check would
    pass and a fresh digest would then stamp current. Also reject a zero-byte placeholder
    (SolidWorks can drop one before an export failure) -- the release exporter already
    treats size 0 as a failed save; the digest-cached path must too, or the empty output
    gets recorded fresh (codex review). Returns the SaveAs3 status for logging."""
    with _telemetry.span(
        "export.save_as",
        output=str(out),
        format=out.suffix.lstrip(".").lower(),
    ) as sp:
        out.unlink(missing_ok=True)
        _telemetry.info(f"SaveAs3 starting -> {out.name}")
        ok = doc.SaveAs3(str(out), 0, SW_SAVE_OPTS)
        sp.set_attribute("save.rc", int(ok))
        if not out.exists() or out.stat().st_size == 0:
            out.unlink(missing_ok=True)  # never leave a zero-byte placeholder behind
            raise RuntimeError(f"SaveAs3 produced no/empty file: {out} (rc={ok})")
        if out.suffix.lower() == ".glb":
            dropped = sanitize_glb(out)
            sp.set_attribute("glb.attributes_dropped", len(dropped))
            if dropped:
                _telemetry.event("glb.sanitized", dropped=json.dumps(dropped))
                _telemetry.warn(
                    f"{out.name}: dropped {len(dropped)} attribute accessor(s) whose "
                    f"count differs from POSITION (SolidWorks glTF exporter quirk; "
                    f"Blender's importer would raise IndexError): {dropped}"
                )
        return ok


def sanitize_glb(path: Path) -> list[dict[str, Any]]:
    """Repair a SolidWorks-exported glTF binary in place so Blender can import it.

    SolidWorks' glTF exporter (``SOLIDWORKSGLTF``) can write a primitive whose
    ``TEXCOORD_0`` accessor has a DIFFERENT element count from its ``POSITION``
    accessor (seen on textured cast-iron faces: harmonic-base 850 UVs / 450
    positions, top-frame 576 / 580 in the v31 bundle). Blender's importer
    indexes the UV array by the vertex indices and dies with
    ``IndexError: index 576 is out of bounds for axis 0 with size 576`` --
    which meshprobe then surfaced as a worker timeout. The spec requires every
    attribute accessor of a primitive to share one count, so the mismatched
    attribute is dropped (its buffer bytes stay, unreferenced); a primitive
    left textured without UVs gets an untextured clone of its material so the
    file stays valid. Returns one record per dropped attribute (empty when the
    file was already clean) -- the caller logs them; a clean file is not
    rewritten at all."""
    with path.open("rb") as fh:
        magic, version, _length = struct.unpack("<III", fh.read(12))
        json_len, json_type = struct.unpack("<II", fh.read(8))
        gltf = json.loads(fh.read(json_len))
        rest = fh.read()
    if magic != 0x46546C67:  # b"glTF"
        raise ValueError(f"not a glTF binary: {path}")
    accessors = gltf.get("accessors", [])
    materials = gltf.setdefault("materials", [])
    dropped: list[dict[str, Any]] = []
    untextured: dict[int, int] = {}
    for mesh_index, mesh in enumerate(gltf.get("meshes", [])):
        for prim_index, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes", {})
            if "POSITION" not in attrs:
                continue
            n_pos = accessors[attrs["POSITION"]]["count"]
            for key in list(attrs):
                if key == "POSITION":
                    continue
                n_attr = accessors[attrs[key]]["count"]
                if n_attr == n_pos:
                    continue
                del attrs[key]
                dropped.append(
                    {
                        "mesh": mesh_index,
                        "primitive": prim_index,
                        "attribute": key,
                        "count": n_attr,
                        "positions": n_pos,
                    }
                )
                if key.startswith("TEXCOORD") and "material" in prim:
                    src = prim["material"]
                    if src not in untextured:
                        clone = json.loads(json.dumps(materials[src]))
                        pbr = clone.get("pbrMetallicRoughness", {})
                        pbr.pop("baseColorTexture", None)
                        pbr.pop("metallicRoughnessTexture", None)
                        for tex_key in ("normalTexture", "occlusionTexture", "emissiveTexture"):
                            clone.pop(tex_key, None)
                        clone["name"] = f"{clone.get('name') or 'material'}-untextured"
                        materials.append(clone)
                        untextured[src] = len(materials) - 1
                    prim["material"] = untextured[src]
    if not dropped:
        return dropped
    payload = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    total = 12 + 8 + len(payload) + len(rest)
    with path.open("wb") as fh:
        fh.write(struct.pack("<III", magic, version, total))
        fh.write(struct.pack("<II", len(payload), json_type))
        fh.write(payload)
        fh.write(rest)
    return dropped



@_telemetry.traced("export.build_png", label_param="stem")
async def export_build_png(adapter: Any, stem: str) -> None:
    """Repair the build-owned isometric render from an already-open native doc."""
    output = OUT_PNG / stem / f"{stem}_isometric.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    set_isometric_view(adapter)
    check(
        f"export_image isometric -> {output.name}",
        await adapter.export_image({
            "file_path": str(output.resolve()),
            "format_type": "png",
            "width": 1600,
            "height": 1000,
            "view_orientation": "isometric",
        }),
    )
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"isometric render repair produced no/empty file: {output}")


def validated_outputs(
    parts: list[str], assemblies: list[str], scene_assemblies: set[str] | None = None,
) -> set[Path]:
    """Every render-cache output whose freshness THIS run establishes for the current
    manifest: each manifest part's STL + STEP; each manifest assembly's boxes JSON +
    composed GLB and every part-mesh STL its scene references; plus the colours /
    digests sidecars. Only existing files are returned. Used to SCOPE the stamp so it
    can't refresh a non-manifest leftover (a stale subassembly scene) it never checked."""
    out: set[Path] = {COLORS, SRC_DIGESTS}
    for m in parts:
        d = m.replace("_", "-")
        out |= {OUT_STL / f"{d}.STL", OUT_STEP / f"{d}.STEP"}
    scene_assemblies = set(assemblies) if scene_assemblies is None else scene_assemblies
    for m in assemblies:
        d = m.replace("_", "-")
        bj = OUT_BOXES / f"{d}.json"
        out.add(OUT_GLTF / f"{d}.glb")
        if m in scene_assemblies:
            out.add(bj)
        if m in scene_assemblies and bj.exists():
            try:
                comps = json.loads(bj.read_text(encoding="utf-8")).get("components") or []
                out |= {OUT_STL / f"{c['mesh']}.STL" for c in comps if c.get("mesh")}
            except Exception:
                pass
    return {p for p in out if p.is_file()}


def stamp_render_cache_current(outputs: set[Path]) -> None:
    """Downstream freshness guards (``render_offline``, ``cut_release``) assert each
    render-cache output is no OLDER than its SolidWorks source BY MTIME. But the remote
    cache restore bumps a restored native's mtime to now (safety), so a legitimately
    fresh, digest-unchanged output we (correctly) did NOT rewrite can look older and
    trip those guards. A SUCCESSFUL export means the render cache is current, so re-stamp
    the outputs THIS run proved fresh / regenerated to now -- a truthful post-condition,
    not a rebuild. Scoped to ``outputs`` (see :func:`validated_outputs`), NOT a blanket
    glob, so a non-manifest leftover this run never checked is never falsely refreshed
    (codex review). Best-effort: a utime failure never fails the export."""
    now = time.time()
    for f in outputs:
        try:
            if f.is_file():
                os.utime(f, (now, now))
        except OSError:
            pass


def _source_changed(stem: str, mesh: str, digests: dict[str, str]) -> bool:
    """True when ``<stem>``'s recipe digest differs from the one ``mesh`` was exported
    at. Falls back to STL-vs-SLDPRT mtime only when the part is not a declared target
    (digest unavailable) -- churn-immune otherwise."""
    src = OUT_SLDPRT / f"{stem}.SLDPRT"
    # A vanished native is STALE, never fresh: the recipe digest is content-free (it
    # would still resolve for a declared target whose .SLDPRT was deleted), so without
    # this a matching recorded digest reports fresh and the old STL gets stamped
    # current -- then render_offline fails on the missing part source. Stale -> the
    # export tries to open it and fails loud instead (codex review).
    if not src.exists():
        return True
    cur = src_digest(src)
    if cur is None:
        stl = OUT_STL / f"{mesh}.STL"
        return not _nonempty(stl) or stl.stat().st_mtime < src.stat().st_mtime
    return digests.get(mesh) != cur


def asm_source_changed(
    dashed: str, src: Path, digests: dict[str, str], *, require_scene: bool = True,
) -> bool:
    """True when the assembly's recipe digest differs from the one its boxes/scene were
    exported at. Falls back to boxes-JSON-vs-SLDASM mtime only when the digest is
    unavailable (dodo import failed) -- so a broken import degrades to the old behaviour,
    never a silent skip."""
    if not src.exists():  # vanished native -> stale, never a silent fresh (see above)
        return True
    cur = src_digest(src)
    if cur is None:
        # Digest-unavailable fallback: check every assembly output that is still
        # produced. Assembly STEP was retired; requiring it here would make every
        # standalone export stale forever.
        outs = [OUT_GLTF / f"{dashed}.glb"]
        if require_scene:
            outs.append(OUT_BOXES / f"{dashed}.json")
        return any(not _nonempty(o) or o.stat().st_mtime < src.stat().st_mtime
                   for o in outs)
    return digests.get(dashed) != cur


def part_stl_stale(stem: str, mesh: str, colors: dict, digests: dict[str, str]) -> bool:
    """Referenced-part STL freshness: the STL is present, its colour is cached, and the
    source part's recipe is unchanged. Referenced-only parts get NO per-part STEP (only
    manifest parts + assemblies do), so a STEP is NOT required here -- requiring one made
    every referenced part re-export forever once the manifest held only the assembly."""
    stl = OUT_STL / f"{mesh}.STL"
    return (not _nonempty(stl) or mesh not in colors
            or _source_changed(stem, mesh, digests))


def manifest_part_stale(stem: str, colors: dict, digests: dict[str, str]) -> bool:
    """Manifest-part freshness: additionally requires the archival ``<stem>.STEP`` (the
    STL and STEP are written together in the top-level parts loop). The recipe-digest
    check already re-exports a rebuilt part -- refreshing STL AND STEP AND colour -- so
    the old STL-vs-STEP mtime race (codex review #11) no longer needs a mtime clause --
    EXCEPT on the digest-unavailable fallback (``src_digest`` is None, e.g. a standalone
    run that cannot import dodo), where ``_source_changed`` compares only the STL mtime;
    there the STEP-vs-source mtime guard is re-added so a rebuilt part with a fresh STL
    but a stale STEP is not treated as fresh (codex review)."""
    step = OUT_STEP / f"{stem}.STEP"
    if not _nonempty(step) or part_stl_stale(stem, stem, colors, digests):
        return True
    src = OUT_SLDPRT / f"{stem}.SLDPRT"
    if src.exists() and src_digest(src) is None:
        return step.stat().st_mtime < src.stat().st_mtime
    return False


def assert_configs_distinct(stem: str, crc_by_mesh: dict[str, int]) -> None:
    """Every configuration of a multi-config part is distinct geometry by design
    (the cone-gear / transgear tooth counts all differ). Two configs sharing a
    byte-identical STL means the per-config export captured a stale, un-rebuilt
    configuration — fail loud rather than ship a mislabelled mesh (the
    non-deterministic lazy-regenerate race that shipped --t18 as 12-tooth in
    v0.5.1; see build_cone_gear's ForceRebuild3 note)."""
    if len(crc_by_mesh) < 2:
        return
    seen: dict[int, str] = {}
    for mesh, crc in crc_by_mesh.items():
        if crc in seen:
            raise RuntimeError(
                f"{stem}: per-config STLs {seen[crc]!r} and {mesh!r} are "
                f"byte-identical (crc {crc:#010x}) — the config switch did not "
                f"rebuild before export; the mesh holds a stale configuration")
        seen[crc] = mesh


def _run_tool(cmd: list[str], tag: str) -> list[str]:
    """Run a PEP-723 comparison tool via ``uv run`` from the repo root, streaming
    its output line-by-line (a Blender render takes minutes) and raising on a
    non-zero exit (kept for the caller's best-effort catch)."""
    proc = subprocess.Popen(cmd, cwd=str(REPO), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    output: list[str] = []
    tail: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        log(f"    {tag}| {line}")
        output.append(line)
        tail.append(line)
        if len(tail) > 40:
            del tail[0]
    if proc.wait() != 0:
        raise RuntimeError(f"{tag} exited non-zero: {' / '.join(tail)[-400:]}")
    return output


def _gallery_inputs(manifest: dict[str, Any]) -> list[Path]:
    paths = {
        COMPARISONS_DIR / "manifest.json",
        RENDER_OFFLINE,
        BLENDER_WORKER,
        COMPOSITE_PY,
        GALLERY_PY,
    }
    paths.update(REPO / str(pair["reference"]["path"])
                 for pair in manifest.get("pairs", []))
    return sorted(paths, key=lambda path: path.as_posix())


def _gallery_input_digest(manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for path in _gallery_inputs(manifest):
        if not path.is_file():
            raise FileNotFoundError(f"comparison gallery input missing: {path}")
        try:
            label = path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            label = path.resolve().as_posix()
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _gallery_output_paths(manifest: dict[str, Any]) -> set[Path]:
    required = {
        COMPARISONS_DIR / "scores.json",
        COMPARISONS_DIR / "index.html",
    }
    for pair in manifest.get("pairs", []):
        pair_id = str(pair["id"])
        required.update({
            COMPARISONS_DIR / "ref" / f"{pair_id}.jpg",
            COMPARISONS_DIR / "render" / f"{pair_id}.jpg",
            COMPARISONS_DIR / "render" / f"{pair_id}.meta.json",
            COMPARISONS_DIR / "composite" / f"{pair_id}_cad.jpg",
            COMPARISONS_DIR / "composite" / f"{pair_id}_blend.jpg",
        })
    return required


def _gallery_outputs_complete(manifest: dict[str, Any]) -> bool:
    pair_ids = {str(pair["id"]) for pair in manifest.get("pairs", [])}
    scores_path = COMPARISONS_DIR / "scores.json"
    try:
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(scores, dict) or not pair_ids.issubset(scores):
        return False

    return all(_nonempty(path) for path in _gallery_output_paths(manifest))


def _stamp_gallery_outputs_current(manifest: dict[str, Any]) -> None:
    """Restamp the complete, digest-matched gallery after a stale-only no-op.

    Export restamps its certified scene/mesh cache, so release staging's mtime
    honesty guard needs the gallery certificate to move with that post-condition.
    This is safe only on the branch where the input digest matches and every
    required output was validated as complete.
    """
    now = time.time()
    stamped = 0
    for path in _gallery_output_paths(manifest):
        try:
            os.utime(path, (now, now))
            stamped += 1
        except OSError:
            pass
    _telemetry.event("comparisons.restamped", outputs=stamped)


def _gallery_stamp_digest() -> str | None:
    try:
        data = json.loads(GALLERY_STAMP.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("inputs")
    return str(value) if value else None


def _write_gallery_stamp(input_digest: str) -> None:
    GALLERY_STAMP.parent.mkdir(parents=True, exist_ok=True)
    temporary = GALLERY_STAMP.with_suffix(".json.partial")
    temporary.write_text(json.dumps({"inputs": input_digest}, indent=1), encoding="utf-8")
    temporary.replace(GALLERY_STAMP)


def _rendered_pair_ids(lines: list[str]) -> set[str]:
    rendered: set[str] = set()
    for line in lines:
        text = line.strip()
        if text.startswith("REFRESHED  "):
            rendered.add(text.removeprefix("REFRESHED  ").strip())
            continue
        if not text.startswith("OK  "):
            continue
        pair_id = text[4:].strip()
        if pair_id.startswith("["):
            continue  # composite.py progress, not a newly rendered pair
        rendered.add(pair_id)
    return rendered


def _prune_stale_gallery() -> None:
    """Delete generated gallery artefacts (render/composite/ref files + scores
    entries) whose pair id is no longer in the manifest, so a removed/renamed
    pair leaves nothing stale for the release to stage and ``len(scores)`` stays
    honest. TARGETED -- it keeps the current pairs, so it does NOT force a full
    re-render; ``render_offline --stale-only`` then re-renders only the pairs
    whose geometry actually changed."""
    manifest = json.loads((COMPARISONS_DIR / "manifest.json").read_text(encoding="utf-8"))
    ids = {p["id"] for p in manifest.get("pairs", [])}
    expected: set[str] = set()
    for pid in ids:
        expected |= {f"render/{pid}.jpg", f"render/{pid}.meta.json",
                     f"composite/{pid}_cad.jpg", f"composite/{pid}_blend.jpg",
                     f"ref/{pid}.jpg"}
    for sub in ("render", "composite", "ref"):
        d = COMPARISONS_DIR / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and f"{sub}/{f.name}" not in expected:
                f.unlink()
                log(f"pruned stale gallery file {sub}/{f.name}")
    scores_f = COMPARISONS_DIR / "scores.json"
    if scores_f.exists():
        try:
            scores = json.loads(scores_f.read_text(encoding="utf-8"))
        except ValueError:
            # An interrupted run can leave the (ignored, regenerable) file
            # malformed; raising here would ride refresh_comparison_gallery's
            # best-effort catch and block regeneration forever. Delete it —
            # the composite pass rewrites it from scratch.
            scores_f.unlink()
            log("deleted corrupt scores.json (composite pass regenerates it)")
            return
        kept = {k: v for k, v in scores.items() if k in ids}
        if len(kept) != len(scores):
            scores_f.write_text(json.dumps(dict(sorted(kept.items())), indent=1),
                                encoding="utf-8")
            log(f"pruned {len(scores) - len(kept)} stale score entr"
                f"{'y' if len(scores) - len(kept) == 1 else 'ies'}")


def refresh_comparison_gallery() -> bool:
    """Produce the offline comparison gallery from the STLs this export just
    wrote, so ``doit export`` yields an up-to-date gallery that the release then
    bundles (cut_release.stage_comparisons). Returns True if refreshed.

    Runs render_offline (Blender, no SolidWorks) ``--stale-only`` when the
    content-keyed gallery inputs are unchanged, so only pairs whose geometry
    changed re-render. A manifest/reference/tool change forces a full render
    because render_offline's own stale predicate does not include renderer code.
    The renderer already composites every pair it renders; a separate full
    composite pass is needed only when outputs remain incomplete. Gallery HTML
    is rebuilt only when renders or gallery inputs changed.

    Blender is a release prerequisite: a missing renderer fails the export loudly
    rather than silently producing a bundle without its comparison gallery. Other
    renderer failures remain best-effort so a transient comparison fault does not
    discard certified CAD exports.
    """
    with _telemetry.span("export.comparisons") as sp:
        try:
            manifest = json.loads(
                (COMPARISONS_DIR / "manifest.json").read_text(encoding="utf-8")
            )
            input_digest = _gallery_input_digest(manifest)
            inputs_changed = _gallery_stamp_digest() != input_digest
            _prune_stale_gallery()
            render_cmd = ["uv", "run", str(RENDER_OFFLINE)]
            if not inputs_changed:
                render_cmd.append("--stale-only")
            render_lines = _run_tool(render_cmd, "cmp")
            rendered = _rendered_pair_ids(render_lines)
            pair_count = len(manifest.get("pairs", []))
            outputs_complete = _gallery_outputs_complete(manifest)
            full_composite = (
                not outputs_complete
                or (inputs_changed and len(rendered) < pair_count)
            )
            if full_composite:
                _run_tool(["uv", "run", str(COMPOSITE_PY)], "composite")
            refreshed = bool(rendered or inputs_changed or not outputs_complete)
            if refreshed:
                _run_tool(["uv", "run", str(GALLERY_PY)], "gallery")
            else:
                _stamp_gallery_outputs_current(manifest)
                _telemetry.info("comparison gallery already current")
                _telemetry.event("comparisons.current", pairs=pair_count)
            _write_gallery_stamp(input_digest)
            sp.set_attribute("rendered_pairs", len(rendered))
            sp.set_attribute("full_composite", full_composite)
            sp.set_attribute("outcome", "refreshed" if refreshed else "current")
        except Exception as exc:  # noqa: BLE001 -- renderer faults are best-effort
            if "BLENDER_UNAVAILABLE:" in str(exc):
                raise RuntimeError(
                    "comparison gallery requires Blender, but none was found; "
                    "install Blender or set $HARMONIC_BLENDER"
                ) from exc
            _telemetry.warn(
                f"comparison gallery not refreshed ({exc}); export continues -- "
                "refresh on a Blender-equipped seat with "
                "`uv run cad/comparisons/tools/render_offline.py`.")
            _telemetry.event("comparisons.skipped", reason=str(exc)[:200])
            sp.set_attribute("outcome", "skipped")
            return False
        if refreshed:
            _telemetry.info("comparison gallery refreshed from exported STLs")
        return True


def main() -> int:
    # An untrusted cache (sentinel absent or mismatched) forces a FULL export so even
    # mtime-gated undeclared targets regenerate through the current logic, not just the
    # digest-gated declared ones (codex review).
    force = "--force" in sys.argv[1:] or exporter_untrusted()
    # Only RECORD source digests when the caller vouches the natives are current --
    # i.e. the doit ``export`` task, which runs on the COM spine AFTER every part /
    # assembly is (re)built (dodo passes ``--record-digests``). A bare standalone run
    # may export a not-yet-rebuilt native, so stamping its recipe digest would make a
    # later same-recipe build's fresh geometry look already-exported and get skipped
    # (codex review). Standalone still READS the cache (fast "all fresh"); it just
    # never writes, so it can never poison it.
    record = "--record-digests" in sys.argv[1:]
    colors = load_colors()
    digests = load_src_digests()
    certified = _certified_outputs()
    certified_drift: dict[Path, bool] = {}

    def neutral_changed(path: Path) -> bool:
        return _certified_output_changed(path, certified, certified_drift)

    parts = part_stems()
    assemblies = list(ASSEMBLY_ORDER)
    # Every assembly is scene-bearing (boxes/scene JSON + composed GLB) — the
    # comparison manifest no longer scopes which assemblies get a scene.
    scene_assemblies = set(assemblies)

    missing_asm_png = {
        stem for stem in assemblies
        if _png_needs_export(
            OUT_PNG / stem.replace("_", "-")
            / f"{stem.replace('_', '-')}_isometric.png",
            force,
            neutral_changed,
        )
    }
    stale_asms: list[str] = []
    for stem in assemblies:
        dashed = stem.replace("_", "-")
        src = OUT_SLDASM / f"{dashed}.SLDASM"
        scene_path = OUT_BOXES / f"{dashed}.json"
        scene_invalid = (
            not scene_is_valid(scene_path)
            or not scene_sources_exist(scene_path)
            or neutral_changed(scene_path)
        )
        if (force or stem in missing_asm_png or scene_invalid
                or not _nonempty(OUT_GLTF / f"{dashed}.glb")
                or neutral_changed(OUT_GLTF / f"{dashed}.glb")
                or asm_source_changed(dashed, src, digests)):
            stale_asms.append(stem)

    missing_part_png = {
        stem.replace("_", "-") for stem in parts
        if _png_needs_export(
            OUT_PNG / stem.replace("_", "-")
            / f"{stem.replace('_', '-')}_isometric.png",
            force,
            neutral_changed,
        )
    }
    stale_parts = [
        stem for stem in parts
        if (force or stem.replace("_", "-") in missing_part_png
            or neutral_changed(OUT_STL / f"{stem.replace('_', '-')}.STL")
            or neutral_changed(OUT_STEP / f"{stem.replace('_', '-')}.STEP")
            or manifest_part_stale(stem.replace("_", "-"), colors, digests))
    ]
    stale_scene_mesh_stems: set[str] = set()
    scene_meshes: dict[str, list[tuple[str, str]]] = {}
    if not any(stem in scene_assemblies for stem in stale_asms):
        scene_meshes = all_scene_part_meshes(scene_assemblies)
        for stem, entries in scene_meshes.items():
            if force or any(
                part_stl_stale(stem, mesh, colors, digests)
                or neutral_changed(OUT_STL / f"{mesh}.STL")
                for _cfg, mesh in entries
            ):
                stale_scene_mesh_stems.add(stem)

    if not stale_parts and not stale_asms and not stale_scene_mesh_stems:
        _telemetry.info("all exports fresh")
        stamp_render_cache_current(validated_outputs(parts, assemblies, scene_assemblies))
        if record:
            write_release_neutral_manifest(
                parts, assemblies, scene_meshes, scene_assemblies, colors, digests,
            )
        # Geometry unchanged, but still reconcile the gallery (cheap: --stale-only
        # is a no-op when nothing drifted) so `doit export` always leaves an
        # up-to-date gallery for the release to bundle.
        refresh_comparison_gallery()
        return 0
    _telemetry.info(
        f"exporting parts={stale_parts or sorted(stale_scene_mesh_stems) or '[]'} "
        f"assemblies={stale_asms or '[]'}"
    )
    for d in (OUT_STL, OUT_STEP, OUT_BOXES, OUT_GLTF):
        d.mkdir(parents=True, exist_ok=True)

    async def build(adapter: Any) -> dict[str, str]:
        old = set_export_prefs(adapter)
        done: dict[str, str] = {}

        def active_cfg(doc: Any) -> str:
            try:
                cm = _read_member(doc, "ConfigurationManager")
                ac = _read_member(cm, "ActiveConfiguration") if cm is not None else None
                return str(_read_member(ac, "Name") or "") if ac is not None else ""
            except Exception:
                return ""

        def switch_configuration(doc: Any, stem: str, cfg: str) -> bool:
            if not cfg or active_cfg(doc).casefold() == cfg.casefold():
                return False
            ok_cfg = doc.ShowConfiguration2(cfg)
            if not ok_cfg and active_cfg(doc).casefold() != cfg.casefold():
                try:
                    names = list(doc.GetConfigurationNames() or [])
                except Exception:
                    names = None
                raise RuntimeError(
                    f"{stem}: ShowConfiguration2({cfg!r}) failed (has {names})"
                )
            adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
            adapter._attempt(lambda: doc.EditRebuild3(), default=None)
            return True

        def scene_stems(data: dict[str, Any]) -> set[tuple[str, str, str]]:
            return {
                (str(comp["part"]), str(comp.get("cfg") or ""), str(comp["mesh"]))
                for comp in data.get("components") or []
                if comp.get("part") and comp.get("mesh")
            }

        try:
            pending_scenes: dict[str, tuple[list, list, set[tuple[str, str, str]]]] = {}
            all_scene_stems: set[tuple[str, str, str]] = set()
            for stem in stale_asms:
                dashed = stem.replace("_", "-")
                src = OUT_SLDASM / f"{dashed}.SLDASM"
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                # Assembly STEP is deliberately omitted: native Pack-and-Go plus
                # the scene graph + glTF cover assembly consumption, while
                # assembly STEP was the dominant export cost (413 s top, 379 s frame
                # in v0.20.0). Part STEP remains the archival exact-BREP surface.
                # The old monolithic assembly STL is retired too (nothing read its
                # mesh bytes) — assemblies export SolidWorks' own glTF binary
                # instead: metre units, per-component named nodes (pattern-
                # generated instances lose their friendly name — SW exporter
                # quirk), appearance materials.
                (OUT_STEP / f"{dashed}.STEP").unlink(missing_ok=True)
                (OUT_STL / f"{dashed}.STL").unlink(missing_ok=True)
                glb = OUT_GLTF / f"{dashed}.glb"
                _save_as(doc, glb)
                log(f"saved {glb.name} ({glb.stat().st_size / 1e6:.1f} MB)")
                # Fresh cache: only resolved-component doc reads land in
                # scan_colors, so a lightweight scan never masks a stale colour.
                scan_colors: dict = {}
                boxes, scene, stems = scan_assembly(adapter, scan_colors)
                colors.update(scan_colors)
                pending_scenes[stem] = (boxes, scene, stems)
                all_scene_stems.update(stems)
                if stem in missing_asm_png:
                    await export_build_png(adapter, dashed)
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
                done[stem] = "exported"

            for stem in sorted(scene_assemblies - set(pending_scenes)):
                path = OUT_BOXES / f"{stem.replace('_', '-')}.json"
                all_scene_stems.update(scene_stems(json.loads(path.read_text(encoding="utf-8"))))

            all_by_stem: dict[str, list[tuple[str, str]]] = {}
            for stem, cfg, mesh in sorted(all_scene_stems):
                all_by_stem.setdefault(stem, []).append((cfg, mesh))
            default_stale = {
                stem.replace("_", "-") for stem in parts
                if (force
                    or neutral_changed(OUT_STL / f"{stem.replace('_', '-')}.STL")
                    or neutral_changed(OUT_STEP / f"{stem.replace('_', '-')}.STEP")
                    or manifest_part_stale(
                        stem.replace("_", "-"), colors, digests,
                    ))
            }
            scene_stale = {
                stem for stem, entries in all_by_stem.items()
                if force or any(
                    part_stl_stale(stem, mesh, colors, digests)
                    or neutral_changed(OUT_STL / f"{mesh}.STL")
                    for _cfg, mesh in entries
                )
            }

            # Open each part at most once. Default STEP/STL and the whole referenced
            # configuration family are emitted in that one session; exporting all
            # siblings preserves the distinct-CRC stale-tessellation guard.
            for stem in sorted(default_stale | scene_stale | missing_part_png):
                src = OUT_SLDPRT / f"{stem}.SLDPRT"
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                render_cfg = active_cfg(doc)
                if stem in default_stale:
                    for out in (OUT_STL / f"{stem}.STL", OUT_STEP / f"{stem}.STEP"):
                        _save_as(doc, out)
                        log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
                    colors[stem] = doc_rgb(doc)

                entries = all_by_stem.get(stem, []) if stem in scene_stale else []
                crc_by_mesh: dict[str, int] = {}
                for cfg, mesh in entries:
                    switch_configuration(doc, stem, cfg)
                    out = OUT_STL / f"{mesh}.STL"
                    if not (mesh == stem and stem in default_stale):
                        _save_as(doc, out)
                    crc_by_mesh[mesh] = zlib.crc32(out.read_bytes()) & 0xFFFFFFFF
                    colors[mesh] = doc_rgb(doc)
                    log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB) "
                        f"rgb={colors[mesh]}")
                assert_configs_distinct(stem, crc_by_mesh)
                if stem in missing_part_png:
                    switch_configuration(doc, stem, render_cfg)
                    await export_build_png(adapter, stem)

                d = src_digest(src) if record else None
                if d is not None:
                    if stem in default_stale:
                        digests[stem] = d
                    for _cfg, mesh in entries:
                        digests[mesh] = d
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
                done[stem] = "exported"

            # Fill component colours only after part exports, then publish each scene
            # and its assembly digest. A partial failure never certifies the manifest.
            for stem, (boxes, scene, stems) in pending_scenes.items():
                dashed = stem.replace("_", "-")
                for component in scene:
                    component["rgb"] = component["rgb"] or list(
                        colors.get(component["mesh"], DEFAULT_RGB)
                    )
                (OUT_BOXES / f"{dashed}.json").write_text(json.dumps({
                    "unit": "mm",
                    "boxes": [{"name": n, "box": list(b)} for n, b in boxes],
                    "components": scene,
                }), encoding="utf-8")
                log(f"saved boxes+scene {dashed}.json "
                    f"({len(boxes)} boxes, {len(scene)} instances, {len(stems)} meshes)")
                d = src_digest(OUT_SLDASM / f"{dashed}.SLDASM") if record else None
                if d is not None:
                    digests[dashed] = d
            # Persist the digest cache + exporter sentinel ONLY on a fully successful
            # export -- inside the `finally` a partial failure would stamp the current
            # sentinel, so the next run's exporter_untrusted() goes false and skips the
            # not-yet-regenerated fallback meshes (codex review).
            if record:
                save_src_digests(digests)
            return done
        finally:
            save_colors(colors)
            restore_export_prefs(adapter, old)

    rc = run_build(build)
    # Only produce the gallery once the glTF/STL/boxes export actually succeeded --
    # a failed COM export leaves the render cache half-written (fail loud there);
    # the stamp keeps mtime-based downstream guards satisfied.
    if rc == 0:
        stamp_render_cache_current(validated_outputs(parts, assemblies, scene_assemblies))
        if record:
            write_release_neutral_manifest(
                parts, assemblies, all_scene_part_meshes(scene_assemblies),
                scene_assemblies, colors, digests,
            )
        refresh_comparison_gallery()
    return rc


if __name__ == "__main__":
    # Advertise "export" as this process's telemetry resource (Aspire "resource"
    # column). Fallback-only: dodo already set OTEL_SERVICE_NAME=export under the
    # spine, so this keeps it; standalone it self-labels.
    _telemetry.set_service("export")
    raise SystemExit(main())
