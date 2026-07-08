"""Export render-cache geometry from SolidWorks: STL + STEP + scene JSON.

doit task: ``export`` (on the COM spine). Normally invoked via ``doit export``
or as a prerequisite of ``doit release``; runnable standalone too.


For every model referenced by comparisons/manifest.json: AP214 STEP (exact
archival geometry) and the offline-render feed consumed by
comparisons/tools/render_offline.py —

* parts: fine binary STL in MILLIMETRES, untranslated (cad/out/stl/<dashed>.STL)
  plus an appearance colour in cad/out/stl/colors.json;
* assemblies: a monolithic cad/out/stl/<dashed>.STL and cad/out/boxes/
  <dashed>.json with per-component bounding boxes (framing) plus a scene
  graph: one entry per visible leaf component with its part stem,
  assembly-space transform (IMathTransform.ArrayData, row-vector
  convention, translation in millimetres) and RGB. Every referenced part gets
  its own STL, shared across assemblies and instanced by the Blender
  worker (so 20 cone gears cost one mesh). All geometry is in millimetres
  (mesh units == the scene-graph transform units, so they pair directly).

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
import sys
import time
import zlib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CAD_ROOT,
    PREF_STL_QUALITY,
    PREF_STL_UNITS,
    TOGGLE_STL_BINARY,
    TOGGLE_STL_NO_TRANSLATE,
    TOGGLE_STL_ONE_FILE,
    check,
    log,
    run_build,
)
from render_compare import _flag, _flag_only, _read_member, model_path  # noqa: E402

import _telemetry  # noqa: E402

OUT_STL = CAD_ROOT / "out" / "stl"
OUT_STEP = CAD_ROOT / "out" / "step"
OUT_BOXES = CAD_ROOT / "out" / "boxes"
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
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


def manifest_models() -> list[str]:
    manifest = json.loads(
        (CAD_ROOT.parent / "comparisons" / "manifest.json").read_text(encoding="utf-8")
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
    _flag(doc, "IPartDoc")
    name = ""
    try:
        res = doc.GetMaterialPropertyName2("", "")
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
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")
    comps = model.GetComponents(False) or []
    boxes, scene, stems = [], [], set()
    for i, comp in enumerate(comps, 1):
        if i % 50 == 0:
            log(f"component scan {i}/{len(comps)} ...")
        # Flag ONLY the zero-arg methods called below (GetPathName always;
        # GetXform in comp_xform's fallback). Name2/Visible/Transform2 are
        # property reads and GetBox/GetMaterialPropertyValues2 take args, so
        # none of those need flagging (issue #87 -- not the 165-method flag).
        _flag_only(comp, "GetPathName", "GetXform")
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
        return {k: tuple(v) for k, v in
                json.loads(COLORS.read_text(encoding="utf-8")).items()}
    return {}


def save_colors(colors: dict) -> None:
    COLORS.write_text(json.dumps(
        {k: list(v) for k, v in sorted(colors.items())}, indent=1), encoding="utf-8")


def _exporter_digest() -> str:
    """Digest of the exporter's own source CLOSURE -- this module plus every repo-local
    helper it transitively imports (render_compare's scene extraction, _common's STL
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


def _save_as(doc: Any, out: Path) -> int:
    """SaveAs3 to ``out``, guaranteeing THIS call produced a REAL file: remove any prior
    output first, so a SaveAs3 that fails (a locked / read-only path) leaves NO file and
    raises -- instead of silently leaving a stale export that the existence check would
    pass and a fresh digest would then stamp current. Also reject a zero-byte placeholder
    (SolidWorks can drop one before an export failure) -- the release exporter already
    treats size 0 as a failed save; the digest-cached path must too, or the empty output
    gets recorded fresh (codex review). Returns the SaveAs3 status for logging."""
    out.unlink(missing_ok=True)
    ok = doc.SaveAs3(str(out), 0, 0)
    if not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)  # never leave a zero-byte placeholder behind
        raise RuntimeError(f"SaveAs3 produced no/empty file: {out} (rc={ok})")
    return ok


def validated_outputs(parts: list[str], assemblies: list[str]) -> set[Path]:
    """Every render-cache output whose freshness THIS run establishes for the current
    manifest: each manifest part's STL + STEP; each manifest assembly's boxes JSON +
    mono STL + STEP and every part-mesh STL its scene references; plus the colours /
    digests sidecars. Only existing files are returned. Used to SCOPE the stamp so it
    can't refresh a non-manifest leftover (a stale subassembly scene) it never checked."""
    out: set[Path] = {COLORS, SRC_DIGESTS}
    for m in parts:
        d = m.replace("_", "-")
        out |= {OUT_STL / f"{d}.STL", OUT_STEP / f"{d}.STEP"}
    for m in assemblies:
        d = m.replace("_", "-")
        bj = OUT_BOXES / f"{d}.json"
        out |= {bj, OUT_STL / f"{d}.STL", OUT_STEP / f"{d}.STEP"}
        if bj.exists():
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
        return not stl.exists() or stl.stat().st_mtime < src.stat().st_mtime
    return digests.get(mesh) != cur


def asm_source_changed(dashed: str, src: Path, digests: dict[str, str]) -> bool:
    """True when the assembly's recipe digest differs from the one its boxes/scene were
    exported at. Falls back to boxes-JSON-vs-SLDASM mtime only when the digest is
    unavailable (dodo import failed) -- so a broken import degrades to the old behaviour,
    never a silent skip."""
    if not src.exists():  # vanished native -> stale, never a silent fresh (see above)
        return True
    cur = src_digest(src)
    if cur is None:
        # Digest-unavailable fallback: check EVERY assembly output's mtime vs the
        # source, not just the boxes JSON -- a fresh scene JSON alongside a stale mono
        # STL/STEP must still read stale (codex review).
        outs = (OUT_BOXES / f"{dashed}.json", OUT_STL / f"{dashed}.STL",
                OUT_STEP / f"{dashed}.STEP")
        return any(not o.exists() or o.stat().st_mtime < src.stat().st_mtime
                   for o in outs)
    return digests.get(dashed) != cur


def part_stl_stale(stem: str, mesh: str, colors: dict, digests: dict[str, str]) -> bool:
    """Referenced-part STL freshness: the STL is present, its colour is cached, and the
    source part's recipe is unchanged. Referenced-only parts get NO per-part STEP (only
    manifest parts + assemblies do), so a STEP is NOT required here -- requiring one made
    every referenced part re-export forever once the manifest held only the assembly."""
    stl = OUT_STL / f"{mesh}.STL"
    return (not stl.exists() or mesh not in colors
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
    if not step.exists() or part_stl_stale(stem, stem, colors, digests):
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
    models = manifest_models()
    colors = load_colors()
    digests = load_src_digests()

    parts = [m for m in models if model_path(m).suffix.lower() == ".sldprt"]
    assemblies = [m for m in models if m not in parts]

    stale_parts = [m for m in parts if force
                   or manifest_part_stale(m.replace("_", "-"), colors, digests)]
    stale_asms = []
    for m in assemblies:
        src, dashed = model_path(m), m.replace("_", "-")
        bj = OUT_BOXES / f"{dashed}.json"
        mono, step = OUT_STL / f"{dashed}.STL", OUT_STEP / f"{dashed}.STEP"
        # Assembly source (its .SLDASM digest folds every referenced part, recursively),
        # so any leaf-part recipe change flips it -> re-export. Missing outputs re-export
        # regardless (why the export task runs `uptodate: False`).
        if (force or not bj.exists() or not mono.exists() or not step.exists()
                or asm_source_changed(dashed, src, digests)):
            stale_asms.append(m)
            continue
        data = json.loads(bj.read_text(encoding="utf-8"))
        comps = data.get("components") or []
        if (not comps or any("mesh" not in c for c in comps) or any(
                part_stl_stale(c["part"], c["mesh"], colors, digests) for c in comps)):
            stale_asms.append(m)

    if not stale_parts and not stale_asms:
        _telemetry.info("all exports fresh")
        stamp_render_cache_current(validated_outputs(parts, assemblies))
        return 0
    _telemetry.info(f"exporting parts={stale_parts or '[]'} assemblies={stale_asms or '[]'}")
    for d in (OUT_STL, OUT_STEP, OUT_BOXES):
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

        async def export_part_stls(stem: str, cfg_meshes: list[tuple[str, str]]) -> None:
            """One open per part; one STL per referenced configuration."""
            src = OUT_SLDPRT / f"{stem}.SLDPRT"
            check(f"open {src.name}", await adapter.open_model(str(src)))
            doc = adapter.currentModel
            crc_by_mesh: dict[str, int] = {}
            for cfg, mesh in cfg_meshes:
                if cfg and cfg.lower() != "default" and active_cfg(doc) != cfg:
                    ok_cfg = doc.ShowConfiguration2(cfg)
                    # ShowConfiguration2 returns False when cfg was already
                    # active — only fail if it's genuinely not active now
                    if not ok_cfg and active_cfg(doc) != cfg:
                        try:
                            names = list(doc.GetConfigurationNames() or [])
                        except Exception:
                            names = None
                        raise RuntimeError(
                            f"{stem}: ShowConfiguration2({cfg!r}) failed (has {names})")
                # Config switches regenerate LAZILY (see build_cone_gear): without a
                # forced rebuild SaveAs3 captures the PRIOR config's still-tessellated
                # solid, so a config's STL non-deterministically holds an adjacent
                # configuration (observed: --t18.STL carrying 12-tooth geometry). Force
                # a full rebuild so THIS config is applied before the mesh is written.
                adapter._attempt(lambda: doc.ForceRebuild3(False), default=None)
                adapter._attempt(lambda: doc.EditRebuild3(), default=None)
                out = OUT_STL / f"{mesh}.STL"
                _save_as(doc, out)
                crc_by_mesh[mesh] = zlib.crc32(out.read_bytes()) & 0xFFFFFFFF
                colors[mesh] = doc_rgb(doc)
                log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB) rgb={colors[mesh]}")
            assert_configs_distinct(stem, crc_by_mesh)
            # Stamp the source recipe digest AFTER the distinctness proof passes, so a
            # bad (stale-config) export is never recorded fresh. All configs share one
            # source part, hence one digest.
            d = src_digest(src) if record else None
            if d is not None:
                for _cfg, mesh in cfg_meshes:
                    digests[mesh] = d
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

        try:
            for m in stale_parts:
                dashed = m.replace("_", "-")
                src = model_path(m)
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                for out in (OUT_STL / f"{dashed}.STL", OUT_STEP / f"{dashed}.STEP"):
                    _save_as(doc, out)
                    log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
                colors[dashed] = doc_rgb(doc)
                log(f"colour {dashed}: {colors[dashed]}")
                d = src_digest(src) if record else None
                if d is not None:
                    digests[dashed] = d
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
                done[m] = "exported"

            for m in stale_asms:
                dashed = m.replace("_", "-")
                src = model_path(m)
                check(f"open {src.name}", await adapter.open_model(str(src)))
                doc = adapter.currentModel
                out = OUT_STEP / f"{dashed}.STEP"
                _save_as(doc, out)
                log(f"saved {out.name} ({out.stat().st_size / 1e6:.1f} MB)")
                mono = OUT_STL / f"{dashed}.STL"  # mm, like every other STL
                _save_as(doc, mono)
                log(f"saved {mono.name} ({mono.stat().st_size / 1e6:.1f} MB, mm)")
                # fresh cache: only resolved-component doc reads land in
                # scan_colors (a lightweight scan seeds nothing), so stale
                # colors.json entries are refreshed, never masked
                scan_colors: dict = {}
                boxes, scene, stems = scan_assembly(adapter, scan_colors)
                colors.update(scan_colors)
                adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)

                # Group ALL configs per stem, and re-export the WHOLE group whenever
                # ANY of its configs is stale: export_part_stls' assert_configs_distinct
                # (the stale-tessellation guard) needs >=2 sibling CRCs to catch a
                # config that failed to rebuild, so a single-config partial refresh
                # (one deleted --tNN.STL / missing colour) must still bring its siblings
                # along (codex review). Single-config parts are unaffected (one entry).
                all_by_stem: dict[str, list[tuple[str, str]]] = {}
                stale_stems: set[str] = set()
                for stem, cfg, mesh in sorted(stems):
                    all_by_stem.setdefault(stem, []).append((cfg, mesh))
                    if force or part_stl_stale(stem, mesh, colors, digests):
                        stale_stems.add(stem)
                for stem in sorted(stale_stems):
                    await export_part_stls(stem, all_by_stem[stem])

                # Scene colours are written AFTER the part exports so a
                # component without an appearance override gets the part-doc
                # colour those exports just (re-)read — the cascade SolidWorks
                # actually displays. A lightweight scan (GetModelDoc2 = None,
                # appearance reads unset) therefore no longer greys the scene.
                for c in scene:
                    c["rgb"] = c["rgb"] or list(colors.get(c["mesh"], DEFAULT_RGB))
                (OUT_BOXES / f"{dashed}.json").write_text(json.dumps({
                    "unit": "mm",
                    "boxes": [{"name": n, "box": list(b)} for n, b in boxes],
                    "components": scene,
                }), encoding="utf-8")
                log(f"saved boxes+scene {dashed}.json "
                    f"({len(boxes)} boxes, {len(scene)} instances, {len(stems)} meshes)")
                # Stamp the assembly digest only after its scene JSON is actually
                # on disk with final colours.
                d = src_digest(src) if record else None
                if d is not None:
                    digests[dashed] = d
                done[m] = "exported"
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
    if rc == 0:  # cache is current -> keep mtime-based downstream guards satisfied
        stamp_render_cache_current(validated_outputs(parts, assemblies))
    return rc


if __name__ == "__main__":
    # Advertise "export" as this process's telemetry resource (Aspire "resource"
    # column). Fallback-only: dodo already set OTEL_SERVICE_NAME=export under the
    # spine, so this keeps it; standalone it self-labels.
    _telemetry.set_service("export")
    raise SystemExit(main())
