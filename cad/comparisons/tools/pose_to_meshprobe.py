#!/usr/bin/env python
"""Convert pose_studio camera poses into runnable meshprobe commands.

pose_studio.py fits a book-photo camera and writes the euler pose into
``cad/comparisons/manifest.json`` (per pair) — and, when part-fitting, echoes the same
pose into ``cad/comparisons/findings/<pair>_deltas.json``. This tool reads either and
emits the ``meshprobe`` command sequence that reproduces that vantage on a release
GLB, so a pose fitted in Blender can be re-inspected head-less in meshprobe.

    uv run cad/comparisons/tools/pose_to_meshprobe.py               # every manifest pair
    uv run cad/comparisons/tools/pose_to_meshprobe.py --pair p002   # id substring filter
    uv run cad/comparisons/tools/pose_to_meshprobe.py cad/comparisons/findings/ch30-p003_deltas.json
    uv run cad/comparisons/tools/pose_to_meshprobe.py --format json # machine-readable params

Coordinate frames — pose_studio/blender_worker is the source of truth:
  * MODEL (SolidWorks/machine) mm, +Y up; az 0 / el 0 looks from +Z (SW Front),
    +az swings the camera toward +X (see blender_worker.camera_axes).
  * meshprobe WORLD is right-handed, Z-up; scene.open reports the GLTF->world map
    (GLTF +X->+X, +Y->+Z, +Z->-Y), i.e. model (x, y, z) -> world (x, -z, y).
Under that rotation the orbit angles fall out exactly:
    azimuth   = az_deg - 90   (world +X toward +Y about +Z)
    elevation = el_deg        (above the world XY plane toward +Z)
    roll      = -roll_deg     (OPPOSITE sense to Blender's; MEASURED, see convert())
    target_mm(world) = (tx, -tz, ty)   from the model-space framing centre
    distance_mm      = blender_worker's fitted cam_dist (reproduced below)

Units: SolidWorks exports the GLB in METRES (glTF spec; see memory/sw-gltf-export).
meshprobe auto-detects that (open receipt: units=meter, unit_scale=1.0) and reports
AND accepts every distance in millimetres, so the default --unit-scale of 1.0 is
correct and --target/--distance line up 1:1 with the model mm here. Confirmed against
the v24 machine GLB: open's root_bounds read [457.2, 404.7, 1394.0] mm and its
source_to_world is exactly the (x,-z,y) map used below. (Override --unit-scale only
for a mis-authored asset whose open bounds come back 1000x off.)

The framing math below MIRRORS cad/comparisons/tools/blender_worker.py (its bpy-free
half). blender_worker imports bpy at module scope so it cannot be imported here;
keep the two copies in sync.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[2]
CAD_OUT = REPO / "cad" / "out"

# Book camera: Nikon D60, APS-C "DX" sensor 23.6 x 15.8 mm (long, short edge).
DX_SENSOR_LONG_MM = 23.6
DX_SENSOR_SHORT_MM = 15.8
DEFAULT_OBJECT_SIZES_AWAY = 4.0


# --------------------------------------------------------------------------- #
# framing math — MIRROR of blender_worker.py (bpy-free half); keep in sync
# --------------------------------------------------------------------------- #
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _proj_extent(lo, hi, axis):
    vals = [axis[0] * x + axis[1] * y + axis[2] * z
            for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return max(vals) - min(vals)


def lens_params(cam):
    """(focal_length_mm, sensor_long_mm) for a perspective pair, else None (ortho)."""
    p = cam.get("perspective")
    if not p:
        return None
    s = DX_SENSOR_LONG_MM
    if p.get("focal_length_mm") is not None:
        return float(p["focal_length_mm"]), float(p.get("sensor_dim_mm", s))
    return float(p.get("object_sizes_away", DEFAULT_OBJECT_SIZES_AWAY)) * s, s


def camera_axes(az_deg, el_deg, roll_deg=0.0):
    az, el, roll = (math.radians(v) for v in (az_deg, el_deg, roll_deg))
    o = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    if abs(math.cos(el)) < 1e-9:
        up = (0.0, 0.0, -1.0) if el > 0 else (0.0, 0.0, 1.0)
    else:
        up = (0.0, 1.0, 0.0)
    r = _norm(_cross(up, o))
    u0 = _cross(o, r)
    cr, sr = math.cos(roll), math.sin(roll)
    rr = tuple(cr * a + sr * b for a, b in zip(r, u0))
    uu = tuple(-sr * a + cr * b for a, b in zip(r, u0))
    return rr, uu, o


def resolve_framing(cam, boxes, mesh_lo, mesh_hi):
    focus = cam.get("frame_components") or []
    target = None
    zoom = float(cam.get("zoom") or 1.0)
    if focus and boxes:
        pats = [re.compile(re.escape(f.replace("_", "-")) + r"(-\d+)?$") for f in focus]
        hits = [b for n, b in boxes if any(p.fullmatch(n.split("/")[-1].lower()) for p in pats)]
        if hits:
            lo = tuple(min(b[i] for b in hits) for i in range(3))
            hi = tuple(max(b[i + 3] for b in hits) for i in range(3))
            r, u, _o = camera_axes(cam.get("az_deg", 0.0), cam.get("el_deg", 0.0),
                                   cam.get("roll_deg", 0.0))
            z = min(_proj_extent(mesh_lo, mesh_hi, r) / max(_proj_extent(lo, hi, r), 1e-9),
                    _proj_extent(mesh_lo, mesh_hi, u) / max(_proj_extent(lo, hi, u), 1e-9))
            zoom = max(1.0, min(0.75 * z, 15.0))
            target = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    if target is None:
        tm = cam.get("target_mm")
        target = (tuple(float(v) for v in tm) if tm is not None
                  else tuple((mesh_lo[i] + mesh_hi[i]) / 2 for i in range(3)))
    return target, zoom


def compute_framing(cam, boxes, mesh_lo, mesh_hi, ext, w, h):
    r, u, o = camera_axes(cam.get("az_deg", 0.0), cam.get("el_deg", 0.0), cam.get("roll_deg", 0.0))
    target, zoom = resolve_framing(cam, boxes, mesh_lo, mesh_hi)
    need_w = max(_proj_extent(mesh_lo, mesh_hi, r), _proj_extent(mesh_lo, mesh_hi, u) * w / h)
    frame_w = need_w * 1.05 / zoom
    lp = lens_params(cam)
    if lp is None:
        cam_dist = ext * 3
    else:
        lens_mm, sensor_long = lp
        fit_span = frame_w * h / w if h >= w else frame_w
        cam_dist = fit_span * lens_mm / sensor_long
    return {"r": r, "u": u, "o": o, "target": target, "zoom": zoom,
            "frame_w": frame_w, "cam_dist": cam_dist, "lens": lp}


# --------------------------------------------------------------------------- #
# input normalisation
# --------------------------------------------------------------------------- #
def normalize_camera(cam: dict) -> dict:
    """Accept a manifest pair camera OR a findings-deltas camera; canonicalise.

    The manifest nests the lens as a ``perspective`` dict (``focal_length_mm``,
    or the ``object_sizes_away`` + ``sensor_dim_mm`` form ``lens_params`` also
    handles); the deltas export flattens it to a top-level ``focal_length_mm``
    (null for ortho). Carry the whole perspective dict through so a non-focal
    spec is not silently downgraded to orthographic.
    """
    persp = cam.get("perspective")
    if persp is None and cam.get("focal_length_mm"):  # deltas flattened the lens
        persp = {"focal_length_mm": float(cam["focal_length_mm"])}
    return {
        "az_deg": float(cam.get("az_deg", 0.0)),
        "el_deg": float(cam.get("el_deg", 0.0)),
        "roll_deg": float(cam.get("roll_deg", 0.0)),
        "zoom": float(cam.get("zoom") or 1.0),
        "target_mm": cam.get("target_mm"),
        "perspective": persp,
        "frame_components": cam.get("frame_components"),
    }


def load_pairs(path: Path) -> tuple[list[dict], str]:
    """Return ([{id, model, camera}], kind) from a manifest / deltas / bare-camera JSON."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and isinstance(doc.get("pairs"), list):
        pairs = [dict(p, model=p.get("model", "harmonic_analyzer"))
                 for p in doc["pairs"] if p.get("camera")]
        return pairs, "manifest"
    if isinstance(doc, dict) and "camera" in doc:  # findings/<pair>_deltas.json
        pid = doc.get("pair") or path.stem
        pair = {"id": pid, "model": "harmonic_analyzer", "camera": doc["camera"]}
        _enrich_from_manifest(pair)  # recover reference/model for canvas sizing
        return [pair], "deltas"
    if isinstance(doc, dict) and {"az_deg", "el_deg"} & doc.keys():  # bare camera dict
        return [{"id": path.stem, "model": "harmonic_analyzer", "camera": doc}], "camera"
    raise SystemExit(f"{path}: not a manifest, deltas, or camera JSON")


def _enrich_from_manifest(pair: dict) -> None:
    """Best-effort: a deltas file carries no ``reference``, so canvas_for would fall
    back to the landscape default and distort the distance. Pull the reference/model
    from the manifest pair this delta derives from (by id) when available."""
    mf = REPO / "cad" / "comparisons" / "manifest.json"
    if not mf.exists():
        return
    try:
        pairs = json.loads(mf.read_text(encoding="utf-8")).get("pairs", [])
    except (ValueError, OSError):
        return
    match = next((p for p in pairs if p.get("id") == pair["id"]), None)
    if not match:
        return
    if match.get("reference"):
        pair["reference"] = match["reference"]
    pair["model"] = match.get("model", pair["model"])


def scene_bbox(model: str, boxes_path: Path | None, glb_hint: str | None,
               fetch: bool, tag: str | None, unit_scale: float) -> tuple[tuple, tuple, float, list]:
    """(mesh_lo, mesh_hi, ext, boxes) in meshprobe mm space for the framing math.

    The bbox MUST come from the same geometry ``open`` will load, or target/distance
    are computed against different geometry than is rendered. So the source tracks
    the resolved GLB: an explicit ``--boxes`` wins (per-part boxes for
    ``frame_components``); else an explicit ``--glb`` derives from that file; else
    ``--fetch-glb`` pulls the release's own boxes (matching the fetched GLB); else
    the local build's boxes JSON, falling back to the local GLB. Deriving from a GLB
    gives boxes=[], so ``frame_components`` framing needs a boxes JSON.
    A metre-authored GLB * 1000 is an identical mm bbox to its boxes JSON.

    ``open --unit-scale S`` scales the imported geometry, so meshprobe reports/accepts
    mm as real_mm * S; the whole bbox is scaled by S here so target/distance land in
    that same space (no-op at the default S=1.0)."""
    dashed = model.replace("_", "-")
    if boxes_path and boxes_path.exists():
        bbox = _bbox_from_boxes(boxes_path)
    elif glb_hint and Path(glb_hint).exists():
        bbox = _bbox_from_glb(Path(glb_hint))
    elif fetch:
        bbox = _bbox_from_boxes(release_member(f"boxes/{dashed}.json", tag))
    elif (CAD_OUT / "boxes" / f"{dashed}.json").exists():
        bbox = _bbox_from_boxes(CAD_OUT / "boxes" / f"{dashed}.json")
    elif (CAD_OUT / "gltf" / f"{dashed}.glb").exists():
        bbox = _bbox_from_glb(CAD_OUT / "gltf" / f"{dashed}.glb")
    else:
        raise SystemExit(
            f"no scene bbox for {model}: no boxes JSON (cad/out/boxes/{dashed}.json) and no "
            f"GLB (cad/out/gltf/{dashed}.glb). Pass --boxes/--glb, --fetch-glb to pull from "
            f"the latest release, or build locally (doit export / export_glb.py).")
    return _scale_bbox(bbox, unit_scale)


def _scale_bbox(bbox: tuple, s: float) -> tuple[tuple, tuple, float, list]:
    if s == 1.0:
        return bbox
    lo, hi, ext, boxes = bbox
    return (tuple(v * s for v in lo), tuple(v * s for v in hi), ext * s,
            [(n, [c * s for c in b]) for n, b in boxes])


def _bbox_from_boxes(path: Path) -> tuple[tuple, tuple, float, list]:
    """Scene AABB in mm (+ per-part boxes) from a boxes/scene JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    boxes = [(e["name"], e["box"]) for e in data.get("boxes", [])]
    if not boxes:
        raise SystemExit(f"{path}: no boxes[] to derive the scene bbox from")
    lo = tuple(min(b[i] for _n, b in boxes) for i in range(3))
    hi = tuple(max(b[i + 3] for _n, b in boxes) for i in range(3))
    return lo, hi, max(hi[i] - lo[i] for i in range(3)), boxes


def _bbox_from_glb(glb: Path) -> tuple[tuple, tuple, float, list]:
    """Scene AABB in mm from a metre-authored GLB (SW glTF export)."""
    import trimesh
    scene = trimesh.load(str(glb))
    lo, hi = scene.bounds  # metres, untranslated model coords
    lo = tuple(float(v) * 1000.0 for v in lo)
    hi = tuple(float(v) * 1000.0 for v in hi)
    return lo, hi, max(hi[i] - lo[i] for i in range(3)), []


# --------------------------------------------------------------------------- #
# conversion
# --------------------------------------------------------------------------- #
def model_to_world(p) -> tuple[float, float, float]:
    """model (x, y, z) mm -> meshprobe world (x, -z, y) mm."""
    return (p[0], -p[2], p[1])


def projection_json(lens, w: int, h: int) -> dict:
    """meshprobe perspective projection mirroring aim_camera's DX-long-edge fit."""
    lens_mm, sensor_long = lens
    if h >= w:  # portrait: long edge runs vertically
        return {"mode": "perspective", "focal_length_mm": lens_mm, "sensor_fit": "vertical",
                "sensor_width_mm": DX_SENSOR_SHORT_MM, "sensor_height_mm": sensor_long}
    return {"mode": "perspective", "focal_length_mm": lens_mm, "sensor_fit": "horizontal",
            "sensor_width_mm": sensor_long, "sensor_height_mm": DX_SENSOR_SHORT_MM}


def convert(pair: dict, bbox, w: int, h: int) -> dict:
    mesh_lo, mesh_hi, ext, boxes = bbox
    cam = normalize_camera(pair["camera"])
    # frame_components framing zooms/centres on the union of named part boxes; a
    # GLB-derived bbox has none, so it would silently fall through to whole-scene
    # framing and emit a pose that no longer matches render_offline. Fail loud.
    if cam.get("frame_components") and not boxes:
        raise SystemExit(
            f"{pair['id']}: camera uses frame_components {cam['frame_components']} but the "
            f"bbox came from a GLB (no per-part boxes); pass --boxes <scene.json> "
            f"(cad/out/boxes/<model>.json) for focused framing")
    f = compute_framing(cam, boxes, mesh_lo, mesh_hi, ext, w, h)

    target_world = model_to_world(f["target"])
    azimuth = cam["az_deg"] - 90.0
    elevation = cam["el_deg"]

    # Cross-check the closed-form angles against the transformed view axis; a
    # mismatch means the mirror drifted from blender_worker.camera_axes.
    ow = model_to_world(f["o"])
    assert abs(math.sin(math.radians(elevation)) - ow[2]) < 1e-6, "elevation mirror drift"
    az_from_o = math.degrees(math.atan2(ow[1], ow[0]))
    assert abs((az_from_o - azimuth + 180) % 360 - 180) < 1e-6, "azimuth mirror drift"

    out = {
        "id": pair["id"], "model": pair["model"],
        "target_mm": [round(v, 3) for v in target_world],
        "azimuth_deg": round(azimuth, 4),
        "elevation_deg": round(elevation, 4),
        # NEGATED: meshprobe's view-orbit --roll turns the camera the opposite way
        # to blender_worker's roll_deg, so passing it through tilts the image the
        # wrong way (a post leans by 2x roll vs the Blender render). Measured on
        # ch11-p002-img05 (roll_deg=-1.81): the dominant vertical-line tilt reads
        # +1.812 deg in cad/comparisons/render/<pair>.jpg and -1.813 deg in the
        # meshprobe render of the un-negated pose. Re-check with the Radon scan in
        # test_pose_to_meshprobe.py if either renderer's convention changes.
        "roll_deg": round(-cam["roll_deg"], 4),
        "distance_mm": round(f["cam_dist"], 3),
        "aspect_ratio": round(w / h, 5),
        "canvas": [w, h],
    }
    out["projection"] = projection_json(f["lens"], w, h) if f["lens"] else None
    # meshprobe ortho scale_mm -> Blender ortho_scale, fitted horizontally for a
    # landscape canvas (aspect >= 1) and vertically for portrait; render_offline
    # fixes the HORIZONTAL extent at frame_w, so only portrait converts width->height.
    out["ortho_scale_mm"] = (None if f["lens"]
                             else round(f["frame_w"] if w >= h else f["frame_w"] * h / w, 3))
    return out


# --------------------------------------------------------------------------- #
# canvas sizing (drives distance via the portrait/landscape fit)
# --------------------------------------------------------------------------- #
def _size_from(img_path: Path, max_side: int):
    """(w, h) scaled so the long side is ~pair_size(max_side); None on failure."""
    try:
        from PIL import Image
        with Image.open(img_path) as img:
            rw, rh = img.size
    except Exception as exc:  # noqa: BLE001 - best effort
        print(f"!! could not size from {img_path.name} ({exc})", file=sys.stderr)
        return None
    scale = min(max_side * 1.4, 2400) / max(rw, rh)  # mirrors render_offline.pair_size
    return max(1, round(rw * scale)), max(1, round(rh * scale))


def canvas_for(pair: dict, max_side: int, override) -> tuple[int, int, str]:
    """Canvas WxH — distance depends on its portrait/landscape aspect.

    Priority: explicit override > the exact prepared ref (cad/comparisons/ref, what
    render_offline uses) > the raw source photo's aspect (approximate — the
    manifest crop may differ) > the landscape default (warns; likely wrong for a
    portrait plate, so pass --canvas)."""
    if override:
        return override[0], override[1], "override"
    prepared = REPO / "cad" / "comparisons" / "ref" / f"{pair['id']}.jpg"
    if prepared.exists():
        wh = _size_from(prepared, max_side)
        if wh:
            return wh[0], wh[1], "prepared-ref"
    ref_rel = (pair.get("reference") or {}).get("path")
    if ref_rel:
        src = REPO / ref_rel
        if src.exists():
            wh = _size_from(src, max_side)
            if wh:
                return wh[0], wh[1], "source-ref (approx crop)"
    print(f"!! {pair['id']}: no reference image found - distance uses the landscape "
          f"default aspect and is likely wrong; pass --canvas WxH", file=sys.stderr)
    return max_side, round(max_side * 1000 / 1600), "default"


# --------------------------------------------------------------------------- #
# GLB resolution — "use latest release"
# --------------------------------------------------------------------------- #
def resolve_glb(model: str, explicit: str | None, fetch: bool, tag: str | None) -> tuple[str, str]:
    dashed = model.replace("_", "-")
    if explicit:
        return explicit, "explicit"
    # --fetch-glb wins over a local GLB so the opened geometry matches the release
    # boxes scene_bbox pulls under the same flag (else open local / frame release).
    if fetch:
        return str(release_member(f"gltf/{dashed}.glb", tag)), f"release {tag or 'latest'}"
    local = CAD_OUT / "gltf" / f"{dashed}.glb"
    if local.exists():
        return str(local), "local build"
    return str(local), "EXPECTED (local build missing; pass --fetch-glb for the release GLB)"


def release_member(member: str, tag: str | None) -> Path:
    """Extract one bundle member (e.g. gltf/<m>.glb, boxes/<m>.json) from the release."""
    tag = tag or _gh(["release", "view", "--json", "tagName", "-q", ".tagName"]).strip()
    cache = CAD_OUT / "release-cache" / tag
    dest = cache / member
    if dest.exists():
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    asset = _gh(["release", "view", tag, "--json", "assets",
                 "-q", '.assets[].name | select(endswith(".zip") and (contains("logs")|not))']).strip()
    if not asset:
        raise SystemExit(f"release {tag}: no bundle .zip asset found")
    bundle = cache / asset
    if not bundle.exists():
        _gh(["release", "download", tag, "-p", asset, "--dir", str(cache), "--clobber"])
    with zipfile.ZipFile(bundle) as zf:
        if member not in zf.namelist():
            raise SystemExit(
                f"release {tag} bundles no {member} - GLB export landed after some tags "
                f"(PR #339); tag {tag} predates it. Build locally (doit export) or pass --glb.")
        zf.extract(member, cache)
    return dest


def _gh(args: list[str]) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, cwd=REPO)
    if proc.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


# --------------------------------------------------------------------------- #
# emission
# --------------------------------------------------------------------------- #
# -- shared per-op command lines (session-scoped) --------------------------- #
def _open_line(mp: list[str], session: str, glb: str, unit_scale: float,
               blender: str | None, aspect: float) -> str:
    cmd = [*mp, "-s", session, "open", glb, "--aspect-ratio", f"{aspect:.5f}"]
    if blender:  # omit so meshprobe discovers Blender (Linux/macOS) when unknown
        cmd += ["--blender", blender]
    if unit_scale != 1.0:
        cmd += ["--unit-scale", str(unit_scale)]
    return _fmt(cmd)


def _illum_line(mp: list[str], session: str) -> str:
    # High-key white background so SW-exported PBR metals do not render near-black.
    return _fmt([*mp, "-s", session, "illumination-set", "high_key",
                 "--background-rgb", "1", "1", "1"])


def _orbit_line(mp: list[str], session: str, cvt: dict) -> str:
    cmd = [*mp, "-s", session, "view-orbit",
           "--target", *[f"{v:g}" for v in cvt["target_mm"]],
           "--azimuth", f"{cvt['azimuth_deg']:g}",
           "--elevation", f"{cvt['elevation_deg']:g}",
           "--distance", f"{cvt['distance_mm']:g}",
           "--roll", f"{cvt['roll_deg']:g}",
           "--aspect-ratio", f"{cvt['aspect_ratio']:.5f}"]
    if cvt["projection"]:
        cmd += ["--projection-json", json.dumps(cvt["projection"], separators=(",", ":"))]
    else:
        cmd += ["--ortho-scale", f"{cvt['ortho_scale_mm']:g}"]
    return _fmt(cmd)


def _render_line(mp: list[str], session: str, cvt: dict, out_dir: str) -> str:
    out_png = str(Path(out_dir) / f"{cvt['id']}.png")
    # screen_edges is meshprobe's own default: a GPU depth/normal edge pass that runs
    # on the graphics device (EEVEE, device=graphics_hardware in the render receipt).
    # Swap to shaded_edges for extra fidelity — Freestyle traces geometry-aware lines
    # and separates same-colour adjacent parts far better — but it is CPU-bound and
    # SINGLE-THREADED, and its cost scales with the visible component count, not the
    # output resolution. Measured on the full machine at 945x2240: screen_edges 7.3 s
    # vs shaded_edges 31.8 s per frame (plain shaded, no edges at all, 6.8 s) — so the
    # GPU edge pass is ~free and Freestyle is ~25 s of view-map computation per frame.
    return _fmt([*mp, "-s", session, "render-image", "--style", "screen_edges",
                 "--width", str(cvt["canvas"][0]), "--height", str(cvt["canvas"][1]),
                 "--output", out_png])


def _pose_comment(cvt: dict) -> str:
    return (f"# {cvt['id']}  (az={cvt['azimuth_deg']:g} el={cvt['elevation_deg']:g} "
            f"roll={cvt['roll_deg']:g} dist={cvt['distance_mm']:g}mm)")


def emit_commands(mp: list[str], cvt: dict, glb: str, glb_src: str, unit_scale: float,
                  blender: str, out_dir: str) -> list[str]:
    """Per-pair isolation: a dedicated session that opens the GLB for this pair alone."""
    session = cvt["id"].split("--")[-1] or cvt["id"]
    header = f"{_pose_comment(cvt)}\n# glb: {glb}  [{glb_src}]"
    return [header,
            _open_line(mp, session, glb, unit_scale, blender, cvt["aspect_ratio"]),
            _orbit_line(mp, session, cvt),
            _illum_line(mp, session),
            _render_line(mp, session, cvt, out_dir), ""]


def emit_batch(mp: list[str], results: list[dict], glb_cache: dict, unit_scale: float,
               blender: str, out_dir: str, session: str) -> list[str]:
    """Single shared session per model: open the GLB ONCE, then pose+render per pair.

    Avoids re-importing the (large) GLB for every pair. Pairs spanning multiple
    models get one session each (``<session>-<model>``); each view-orbit carries
    its own aspect/projection and each render its own size, so differing canvases
    coexist in one open."""
    models: list[str] = []
    for cvt in results:
        if cvt["model"] not in models:
            models.append(cvt["model"])
    multi = len(models) > 1
    lines: list[str] = []
    for model in models:
        cvts = [c for c in results if c["model"] == model]
        glb, glb_src = glb_cache[model]
        sess = f"{session}-{model.replace('_', '-')}" if multi else session
        lines.append(f"# batch session '{sess}': {len(cvts)} pose(s), one open")
        lines.append(f"# glb: {glb}  [{glb_src}]")
        lines.append(_open_line(mp, sess, glb, unit_scale, blender, cvts[0]["aspect_ratio"]))
        lines.append(_illum_line(mp, sess))
        for cvt in cvts:
            lines.append(_pose_comment(cvt))
            lines.append(_orbit_line(mp, sess, cvt))
            lines.append(_render_line(mp, sess, cvt, out_dir))
        lines.append(_fmt([*mp, "-s", sess, "close"]))
        lines.append("")
    return lines


def _fmt(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", default=str(REPO / "cad" / "comparisons" / "manifest.json"),
                    help="pose_studio JSON: manifest.json, findings/<pair>_deltas.json, "
                         "or a bare camera dict (default: cad/comparisons/manifest.json)")
    ap.add_argument("--pair", help="only pairs whose id contains this substring")
    ap.add_argument("--boxes", type=Path, help="scene/boxes JSON for the mm bbox "
                                                "(default: cad/out/boxes/<model>.json)")
    ap.add_argument("--canvas", help="force render canvas WxH (else sized from the prepared ref)")
    ap.add_argument("--glb", help="GLB to open (default: local build, else --fetch-glb release)")
    ap.add_argument("--fetch-glb", action="store_true",
                    help="download+extract gltf/<model>.glb from the latest release bundle")
    ap.add_argument("--release-tag", help="release tag for --fetch-glb (default: latest)")
    ap.add_argument("--unit-scale", type=float, default=1.0,
                    help="meshprobe open --unit-scale (default 1.0; see units note in the header)")
    ap.add_argument("--blender", default=None,
                    help="Blender >= 5.2 path to pass to meshprobe open; omitted by default "
                         "so meshprobe locates Blender itself (pass this only to override)")
    ap.add_argument("--out-dir", default="cad/comparisons/render/meshprobe",
                    help="render-image --output directory")
    ap.add_argument("--format", choices=["sh", "json"], default="sh",
                    help="emit meshprobe commands (sh) or the computed params (json)")
    ap.add_argument("--batch", action="store_true",
                    help="emit ONE shared session per model (open the GLB once, then "
                         "view-orbit+render per pair) instead of a session + re-open per pair")
    ap.add_argument("--session", help="shared session name for --batch (implies --batch; "
                                      "default 'poses'); suffixed per model when pairs span models")
    ap.add_argument("--meshprobe", default="uv run meshprobe",
                    help="meshprobe invocation in the emitted commands (default 'uv run "
                         "meshprobe' so `... | bash` works in-project; use 'meshprobe' for a "
                         "global install)")
    args = ap.parse_args()

    batch = args.batch or bool(args.session)
    session = args.session or "poses"
    mp = shlex.split(args.meshprobe)
    blender = args.blender  # meshprobe locates Blender itself when this is None

    override = None
    if args.canvas:
        cw, ch = args.canvas.lower().split("x")
        override = (int(cw), int(ch))

    pairs, kind = load_pairs(Path(args.input))
    if args.pair:
        pairs = [p for p in pairs if args.pair in p["id"]]
    if not pairs:
        raise SystemExit("no matching pairs")
    print(f"# {len(pairs)} pair(s) from {kind}: {args.input}", file=sys.stderr)

    bbox_cache: dict[str, tuple] = {}
    glb_cache: dict[str, tuple] = {}
    results, blocks = [], []
    for pair in pairs:
        model = pair["model"]
        if model not in bbox_cache:
            bbox_cache[model] = scene_bbox(model, args.boxes, args.glb, args.fetch_glb,
                                           args.release_tag, args.unit_scale)
        w, h, src = canvas_for(pair, 1600, override)
        cvt = convert(pair, bbox_cache[model], w, h)
        cvt["canvas_source"] = src
        results.append(cvt)
        if args.format == "sh" and model not in glb_cache:
            glb_cache[model] = resolve_glb(model, args.glb, args.fetch_glb, args.release_tag)
        if args.format == "sh" and not batch:
            glb, glb_src = glb_cache[model]
            blocks += emit_commands(mp, cvt, glb, glb_src, args.unit_scale,
                                    blender, args.out_dir)

    if args.format == "json":
        print(json.dumps(results, indent=2))
        return 0
    if batch:
        blocks = emit_batch(mp, results, glb_cache, args.unit_scale, blender,
                            args.out_dir, session)
    print("\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
