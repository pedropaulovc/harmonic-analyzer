"""Render SolidWorks models from camera poses aligned with reference photos.

Reads ``comparisons/manifest.json`` (see comparisons/tools/composite.py for
the artefact layout), groups pairs by model so each part/assembly is opened
once, stages the camera, and captures via the adapter's 1:1
``view_orientation="current"`` export. Composites and scores are refreshed
through comparisons/tools/composite.py after each capture.

Camera spec per pair (manifest ``camera``):
    mode "named":  view = front|back|left|right|top|bottom|isometric|dimetric|trimetric
    mode "euler":  az_deg/el_deg/roll_deg (az 0 = SolidWorks Front, +az =
                   camera moves to the model's right/+X side, el = elevation),
                   optional target_mm [x,y,z] (model point to centre),
                   zoom (multiplier on the zoom-to-fit scale),
                   perspective {"focal_length_mm": F} (real-lens model, see
                   lens_object_sizes_away) or {"object_sizes_away": N} (raw
                   SolidWorks value) or null (orthographic).

Orientation mechanism (IModelView.Orientation3 doc recipe): compose a
transform from the camera right/up/out axes in model space and assign its
inverse; translation = (-Scale2 * target) through that same transform.

Usage (sibling venv):
    python cad/scripts/render_compare.py [--only id1,id2] [--model m]
                                         [--stale-only] [--selftest]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    OUT_SLDASM,
    OUT_SLDPRT,
    CAD_ROOT,
    _read_member,
    check,
    log,
    run_build,
)

import _telemetry  # noqa: E402

REPO = CAD_ROOT.parent
COMP = REPO / "comparisons"
sys.path.insert(0, str(COMP / "tools"))
import composite  # type: ignore[import-not-found]  # noqa: E402  -- added to sys.path above at runtime

VIEW_CONSTANTS = {
    "front": 1, "back": 2, "left": 3, "right": 4, "top": 5,
    "bottom": 6, "isometric": 7, "dimetric": 8, "trimetric": 9,
}


def _flag(obj: Any, iface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info

    try:
        sw_type_info.flag_methods(obj, iface)
    except Exception:
        pass


def _flag_only(obj: Any, *method_names: str) -> None:
    """Flag ONLY the named zero-arg methods on ``obj`` -- not its whole
    interface. Avoids the ~165-round-trip whole-interface ``IComponent2`` flag
    in per-component loops when only one or two zero-arg methods are called
    (issue #87). ``_FlagAsMethod`` is a pywin32 ``CDispatch`` method, so this
    needs no gen_py wrapper; unknown names raise inside it and are skipped."""
    flag = getattr(obj, "_FlagAsMethod", None)
    if flag is None:
        return
    for name in method_names:
        try:
            flag(name)
        except Exception:
            pass


def _put_object(obj: Any, prop: str, value: Any) -> None:
    """Assign an object-valued COM property, escalating to PROPERTYPUTREF."""
    try:
        setattr(obj, prop, value)
    except Exception:
        import pythoncom

        dispid = obj._oleobj_.GetIDsOfNames(0, prop)
        obj._oleobj_.Invoke(
            dispid, 0,
            pythoncom.DISPATCH_PROPERTYPUT | pythoncom.DISPATCH_PROPERTYPUTREF,
            0, value,
        )


def model_path(model: str) -> Path:
    dashed = model.replace("_", "-")
    for p in (OUT_SLDASM / f"{dashed}.SLDASM", OUT_SLDPRT / f"{dashed}.SLDPRT"):
        if p.exists():
            return p
    raise FileNotFoundError(f"no artefact for model {model!r} ({dashed})")


# --- camera math -----------------------------------------------------------

def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def camera_axes(az_deg: float, el_deg: float, roll_deg: float = 0.0):
    """Right/up/out unit vectors (model space) for the camera.

    az=0,el=0 -> out=+Z (SolidWorks Front); az=90 -> camera at +X (Right
    view); el=90 -> camera above (Top view, screen-up = -Z like SolidWorks).
    """
    az, el, roll = (math.radians(v) for v in (az_deg, el_deg, roll_deg))
    o = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    if abs(math.cos(el)) < 1e-9:  # straight up/down: SolidWorks' top/bottom screen-up
        up_hint = (0.0, 0.0, -1.0) if el > 0 else (0.0, 0.0, 1.0)
    else:
        up_hint = (0.0, 1.0, 0.0)
    r0 = _norm(_cross(up_hint, o))
    u0 = _cross(o, r0)
    cr, sr = math.cos(roll), math.sin(roll)
    r = tuple(cr * a + sr * b for a, b in zip(r0, u0, strict=True))
    u = tuple(-sr * a + cr * b for a, b in zip(r0, u0, strict=True))
    return r, u, o


# --- perspective / lens model ----------------------------------------------

# The book (references/.../31_Notes_on_the_Design) states nearly all photos
# were shot on a Nikon D60 dSLR -- APS-C "DX" sensor, 23.6 x 15.8 mm -- with a
# Tokina 100 mm f/2.8 macro lens. SolidWorks has no focal-length camera;
# IModelView parameterises perspective as ObjectSizesAway = (eye->object
# distance) / (object size), "the smaller the value, the greater the amount of
# perspective distortion" (API docs). For a lens of focal length f framing a
# subject that fills a sensor dimension d, that distance/size ratio reduces to
# f / d (the half-angle tangents cancel), so ObjectSizesAway = f / d. We
# reference the sensor's LONG edge (23.6 mm): a photographer orients the long
# edge along the subject's long axis (the tall machine is shot portrait), so
# the subject's long dimension -- which dominates the bounding size SolidWorks
# uses -- fills the frame's long edge at the lens's long-axis angle of view.
# This is also the dimension comparisons/tools/blender_worker.py fits, so both
# engines reproduce the same lens.
DX_SENSOR_MM = (23.6, 15.8)                      # Nikon D60 APS-C (long, short)
DX_SENSOR_LONG_MM = DX_SENSOR_MM[0]              # 23.6 mm -- long edge
BOOK_FOCAL_LENGTH_MM = 100.0                     # Tokina 100 mm macro
DEFAULT_OBJECT_SIZES_AWAY = 4.0                  # fallback if spec gives neither


def lens_object_sizes_away(focal_length_mm: float,
                           sensor_dim_mm: float = DX_SENSOR_LONG_MM) -> float:
    """SolidWorks ObjectSizesAway that mimics a real lens.

    ObjectSizesAway is distance/size (smaller = stronger perspective). A lens
    of focal length f framing a subject that fills sensor dimension d sits at
    distance/size = f / d, so the book's 100 mm lens on the DX long edge gives
    ~4.24 (13.5 deg long-axis angle of view) -- a weak, near-orthographic
    perspective matching the flat telephoto look of the reference photos.
    """
    return focal_length_mm / sensor_dim_mm


def resolve_object_sizes_away(persp: dict) -> float:
    """ObjectSizesAway for a manifest perspective spec.

    ``focal_length_mm`` (real-lens model, optional ``sensor_dim_mm`` defaulting
    to the DX long edge) takes precedence over a raw ``object_sizes_away``.
    """
    if persp.get("focal_length_mm") is not None:
        return lens_object_sizes_away(
            float(persp["focal_length_mm"]),
            float(persp.get("sensor_dim_mm", DX_SENSOR_LONG_MM)),
        )
    return float(persp.get("object_sizes_away", DEFAULT_OBJECT_SIZES_AWAY))


# --- viewport background -----------------------------------------------------

# swconst values extracted from the installed swconst.tlb (R2026x):
SW_PREF_BG_APPEARANCE = 305  # swUserPreferenceIntegerValue_e.swColorsBackgroundAppearance
SW_PREF_VIEWPORT_BG = 99     # swUserPreferenceIntegerValue_e.swSystemColorsViewportBackground
SW_TOGGLE_GRADIENT_BG = 68   # swUserPreferenceToggle_e.swColorsGradientPartBackground
BG_PLAIN = 0                 # swColorsBackgroundAppearance_e.swColorsBackgroundAppearance_Plain


def force_plain_white_background(adapter: Any) -> dict:
    """Plain white viewport for the whole capture session; returns old prefs.

    The default scene background is a gradient with an elliptical highlight,
    which defeats both content trimming and the blend's background knockout.
    """
    sw = adapter.swApp
    _flag(sw, "ISldWorks")
    old = {
        "appearance": int(sw.GetUserPreferenceIntegerValue(SW_PREF_BG_APPEARANCE)),
        "viewport": int(sw.GetUserPreferenceIntegerValue(SW_PREF_VIEWPORT_BG)),
        "gradient": bool(sw.GetUserPreferenceToggle(SW_TOGGLE_GRADIENT_BG)),
    }
    sw.SetUserPreferenceIntegerValue(SW_PREF_BG_APPEARANCE, BG_PLAIN)
    sw.SetUserPreferenceIntegerValue(SW_PREF_VIEWPORT_BG, 0xFFFFFF)
    sw.SetUserPreferenceToggle(SW_TOGGLE_GRADIENT_BG, False)
    log(f"viewport background -> plain white (was {old})")
    return old


def restore_background(adapter: Any, old: dict) -> None:
    sw = adapter.swApp
    sw.SetUserPreferenceIntegerValue(SW_PREF_BG_APPEARANCE, old["appearance"])
    sw.SetUserPreferenceIntegerValue(SW_PREF_VIEWPORT_BG, old["viewport"])
    sw.SetUserPreferenceToggle(SW_TOGGLE_GRADIENT_BG, old["gradient"])
    log("viewport background restored")


# --- component framing -------------------------------------------------------

def component_boxes(adapter: Any) -> list[tuple[str, tuple[float, ...]]]:
    """(instance name's last path segment lowercased, assembly-space box in
    metres) for every component at every level. Suppressed/graphics-less
    instances return no box and are skipped."""
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    _flag(model, "IAssemblyDoc")
    try:
        comps = model.GetComponents(False)
    except Exception as exc:
        log(f"GetComponents failed ({exc}); framing disabled")
        return []
    out = []
    total = len(comps or [])
    for i, comp in enumerate(comps or [], 1):
        if i % 50 == 0:
            log(f"component boxes {i}/{total} ...")
        # No flag: Name2 is a property read and GetBox is called WITH args, so
        # late binding dispatches it as a method unambiguously (issue #87).
        try:
            name = str(_read_member(comp, "Name2") or "")
            box = comp.GetBox(False, False)
        except Exception:
            continue
        if not box:
            continue
        out.append((name.split("/")[-1].lower(), tuple(float(v) for v in box)))
    return out


def _union_box(boxes: list[tuple[float, ...]]) -> tuple[float, ...]:
    return tuple(min(b[i] for b in boxes) for i in range(3)) + tuple(
        max(b[i + 3] for b in boxes) for i in range(3)
    )


def _proj_extent(box: tuple[float, ...], axis: tuple[float, ...]) -> float:
    vals = [
        axis[0] * x + axis[1] * y + axis[2] * z
        for x in (box[0], box[3])
        for y in (box[1], box[4])
        for z in (box[2], box[5])
    ]
    return max(vals) - min(vals)


def resolve_framing(cam: dict, boxes: list[tuple[str, tuple[float, ...]]]) -> dict:
    """Turn camera.frame_components into a concrete target_mm + zoom.

    References shot in-context show a component mounted in the complete
    machine, so the pair renders the full assembly with the camera centred on
    the focus components' union box, zoomed so it fills ~75% of the frame.
    Instance names match `<dashed>(-N)?` so cone_gear matches cone-gear-12 but
    not cone-gear-shaft-1.
    """
    focus = cam.get("frame_components") or []
    if not focus or not boxes:
        return cam
    pats = [re.compile(re.escape(f.replace("_", "-")) + r"(-\d+)?$") for f in focus]
    hits = [b for seg, b in boxes if any(p.fullmatch(seg) for p in pats)]
    if not hits:
        log(f"frame_components {focus}: no instances matched; zoom-to-fit fallback")
        return {**cam, "target_mm": None, "zoom": 1.0}
    u = _union_box(hits)
    whole = _union_box([b for _, b in boxes])
    r, up, _o = camera_axes(cam.get("az_deg", 0.0), cam.get("el_deg", 0.0), cam.get("roll_deg", 0.0))
    zoom = min(
        _proj_extent(whole, r) / max(_proj_extent(u, r), 1e-6),
        _proj_extent(whole, up) / max(_proj_extent(u, up), 1e-6),
    )
    zoom = max(1.0, min(0.75 * zoom, 15.0))
    target = [(u[i] + u[i + 3]) / 2 * 1000.0 for i in range(3)]
    return {**cam, "target_mm": target, "zoom": round(zoom, 2)}


# --- SolidWorks view staging -----------------------------------------------

def set_camera(adapter: Any, cam: dict) -> None:
    from solidworks_mcp.adapters.com_variant import double_array

    model = adapter.currentModel
    _flag(model, "IModelDoc2")

    if cam.get("mode", "euler") == "named":
        model.ShowNamedView2("", VIEW_CONSTANTS[cam["view"]])
        model.ViewZoomToFit2()
        model.GraphicsRedraw2()
        return

    view = _read_member(model, "ActiveView")
    _flag(view, "IModelView")
    mu = adapter.swApp.GetMathUtility()
    _flag(mu, "IMathUtility")

    r, u, o = camera_axes(cam.get("az_deg", 0.0), cam.get("el_deg", 0.0), cam.get("roll_deg", 0.0))
    vecs = [mu.CreateVector(double_array(list(v))) for v in (r, u, o)]
    origin_vec = mu.CreateVector(double_array([0.0, 0.0, 0.0]))
    xform = mu.ComposeTransform(*vecs, origin_vec, 1.0)
    _flag(xform, "IMathTransform")
    orient = _read_member(xform, "Inverse")
    _put_object(view, "Orientation3", orient)
    model.ViewZoomToFit2()  # normalise Scale2/Translation3 for the new rotation

    scale = float(_read_member(view, "Scale2"))
    zoom = float(cam.get("zoom", 1.0) or 1.0)
    if zoom != 1.0:
        scale *= zoom
        view.Scale2 = scale
    target = cam.get("target_mm")
    if target:
        # Doc recipe: Translation3 = (target * -Scale2) through the orientation.
        # View-space coords of the target are plain dot products with the
        # camera axes, so no COM math-object chaining is needed.
        t = [c / 1000.0 for c in target]
        tv = [-scale * sum(a * b for a, b in zip(axis, t, strict=True)) for axis in (r, u, o)]
        _put_object(view, "Translation3", mu.CreateVector(double_array(tv)))

    persp = cam.get("perspective")
    has = bool(_read_member(view, "HasPerspective"))
    if persp:
        if not has:
            view.AddPerspective()  # ObjectSizesAway is settable only with perspective on
        osa = resolve_object_sizes_away(persp)
        view.ObjectSizesAway = osa
        log(f"perspective on: ObjectSizesAway={osa:.3f}")
    elif has:
        view.RemovePerspective()
    model.GraphicsRedraw2()


async def capture(adapter: Any, out_img: Path, width: int, height: int) -> None:
    out_img.parent.mkdir(parents=True, exist_ok=True)
    check(
        f"export {out_img.name}",
        await adapter.export_image(
            {
                "file_path": str(out_img),
                "format_type": out_img.suffix.lstrip(".").lower(),
                "width": width,
                "height": height,
                "view_orientation": "current",
            }
        ),
    )


# --- staleness ---------------------------------------------------------------

def _sidecar(pair_id: str) -> Path:
    return COMP / "render" / f"{pair_id}.meta.json"


def pair_size(ref_png: Path, max_side: int) -> tuple[int, int]:
    """Capture canvas: ref aspect, oversized 1.4x (capped) — the capture is
    trimmed to content afterwards, so the slack buys content resolution."""
    from PIL import Image

    with Image.open(ref_png) as img:
        rw, rh = img.size
    scale = min(max_side * 1.4, 2400) / max(rw, rh)
    return max(1, round(rw * scale)), max(1, round(rh * scale))


def is_stale(pair: dict, mpath: Path) -> bool:
    img = composite.pair_paths(pair["id"])["render"]
    sc = _sidecar(pair["id"])
    if not img.exists() or not sc.exists():
        return True
    meta = json.loads(sc.read_text(encoding="utf-8"))
    return (
        meta.get("camera") != pair["camera"]
        or meta.get("reference") != pair["reference"]
        or meta.get("model_mtime") != mpath.stat().st_mtime
    )


def write_sidecar(pair: dict, mpath: Path, size: tuple[int, int]) -> None:
    _sidecar(pair["id"]).write_text(
        json.dumps({"camera": pair["camera"], "reference": pair["reference"],
                    "size": list(size), "model_mtime": mpath.stat().st_mtime,
                    "engine": "solidworks",
                    # captures run under force_plain_white_background --
                    # composite._content_mask seeds its knockout flood from it
                    "render_bg": "white"}),
        encoding="utf-8",
    )


# --- self-test ---------------------------------------------------------------

SELFTEST_VIEWS = {
    "front": (0.0, 0.0),
    "right": (90.0, 0.0),
    "top": (0.0, 90.0),
    "isometric": (45.0, math.degrees(math.atan(1 / math.sqrt(2)))),
}


async def selftest(adapter: Any) -> dict[str, str]:
    """Named view vs euler equivalent must capture near-identical pixels."""
    old_bg = force_plain_white_background(adapter)
    try:
        return await _selftest(adapter)
    finally:
        restore_background(adapter, old_bg)


async def _selftest(adapter: Any) -> dict[str, str]:
    mpath = OUT_SLDPRT / "crank-arm.SLDPRT"
    if not mpath.exists():
        mpath = next(OUT_SLDPRT.glob("*.SLDPRT"))
    check(f"open {mpath.name}", await adapter.open_model(str(mpath)))
    tmp = COMP / "render" / "_selftest"
    failures = []
    for name, (az, el) in SELFTEST_VIEWS.items():
        a, b = tmp / f"{name}_named.png", tmp / f"{name}_euler.png"
        set_camera(adapter, {"mode": "named", "view": name})
        await capture(adapter, a, 800, 500)
        set_camera(adapter, {"mode": "euler", "az_deg": az, "el_deg": el})
        await capture(adapter, b, 800, 500)
        rms = _pixel_rms(a, b)
        status = "OK" if rms < 3.0 else "FAIL"
        log(f"selftest {name}: rms {rms:.2f} {status}")
        if rms >= 3.0:
            failures.append(f"{name} rms={rms:.2f}")
    if failures:
        raise RuntimeError("selftest failed: " + ", ".join(failures))
    return {"selftest": "passed", "dir": str(tmp)}


def _pixel_rms(a: Path, b: Path) -> float:
    from PIL import Image

    ia, ib = Image.open(a).convert("L"), Image.open(b).convert("L")
    if ia.size != ib.size:
        ib = ib.resize(ia.size)
    total = 0
    for va, vb in zip(ia.getdata(), ib.getdata(), strict=True):  # type: ignore[call-overload]  # ImagingCore is iterable but PIL stubs don't declare it
        d = va - vb
        total += d * d
    return (total / (ia.width * ia.height)) ** 0.5


# --- main --------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated pair ids")
    ap.add_argument("--model", help="only pairs of this model")
    ap.add_argument("--stale-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return run_build(selftest)

    manifest = composite.load_manifest()
    defaults = manifest.get("defaults", {})
    width = int(defaults.get("width", 1600))
    height = int(defaults.get("height", 1000))
    only = set(args.only.split(",")) if args.only else None

    by_model: dict[str, list[dict]] = {}
    for pair in manifest["pairs"]:
        if only and pair["id"] not in only:
            continue
        if args.model and pair["model"] != args.model:
            continue
        mpath = model_path(pair["model"])
        if args.stale_only and not is_stale(pair, mpath):
            continue
        by_model.setdefault(pair["model"], []).append(pair)

    if not by_model:
        _telemetry.info("nothing to render")
        return 0
    # Parts before assemblies (assemblies are the slow opens).
    order = sorted(by_model, key=lambda m: (model_path(m).suffix.lower() == ".sldasm", m))
    n_pairs = sum(len(v) for v in by_model.values())
    _telemetry.info(f"rendering {n_pairs} pairs across {len(order)} models")

    async def build(adapter: Any) -> dict[str, str]:
        old_bg = force_plain_white_background(adapter)
        try:
            return await _render_all(adapter)
        finally:
            restore_background(adapter, old_bg)

    async def _render_all(adapter: Any) -> dict[str, str]:
        done: dict[str, str] = {}
        n = 0
        for mi, model in enumerate(order, 1):
            mpath = model_path(model)
            log(f"model {mi}/{len(order)}: {model} ({len(by_model[model])} pairs)")
            check(f"open {mpath.name}", await adapter.open_model(str(mpath)))
            # Shaded WITHOUT edges: the book plates have no outline strokes,
            # and edge ink swamps fine geometry at capture scale (the fluted
            # columns render solid black from 32 full-length groove edges).
            mdl = adapter.currentModel
            _flag(mdl, "IModelDoc2")
            mdl.ViewDisplayShaded()
            boxes = []
            if mpath.suffix.lower() == ".sldasm" and any(
                p["camera"].get("frame_components") for p in by_model[model]
            ):
                log(f"{model}: scanning component boxes for framing "
                    "(slow COM pass, ~0.4s/component, viewport idle)")
                boxes = component_boxes(adapter)
                log(f"{model}: {len(boxes)} component boxes")
            for pair in by_model[model]:
                pid = pair["id"]
                n += 1
                # Capture at the reference's aspect so side-by-side panels and
                # the blend overlay compare 1:1 (portrait refs would otherwise
                # letterbox inside a landscape viewport).
                ref_png = composite.prepare_reference(pair)
                w, h = pair_size(ref_png, max(width, height))
                cam = resolve_framing(pair["camera"], boxes)
                tgt = cam.get("target_mm")
                log(f"[{n}/{n_pairs}] {pid}: az {cam.get('az_deg', 0):g} "
                    f"el {cam.get('el_deg', 0):g} zoom {cam.get('zoom', 1):g}"
                    + (f" target ({tgt[0]:.0f},{tgt[1]:.0f},{tgt[2]:.0f})mm" if tgt else "")
                    + f" {w}x{h}")
                set_camera(adapter, cam)
                await capture(adapter, composite.pair_paths(pid)["render"], w, h)
                # captures run under force_plain_white_background
                composite.trim_render_file(composite.pair_paths(pid)["render"],
                                           background="white")
                write_sidecar(pair, mpath, (w, h))
                done[pid] = "rendered"
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
            log(f"closed {model} ({n}/{n_pairs} pairs done)")
        composite.regenerate(set(done))  # composites + scores in one pass
        return done

    return run_build(build)


if __name__ == "__main__":
    raise SystemExit(main())
