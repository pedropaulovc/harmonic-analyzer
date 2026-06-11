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
                   perspective {"object_sizes_away": N} or null.

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

REPO = CAD_ROOT.parent
COMP = REPO / "comparisons"
sys.path.insert(0, str(COMP / "tools"))
import composite  # noqa: E402  (PEP-723 header is inert on import)

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
            view.AddPerspective()
        view.ObjectSizesAway = float(persp.get("object_sizes_away", 4.0))
    elif has:
        view.RemovePerspective()
    model.GraphicsRedraw2()


async def capture(adapter: Any, out_png: Path, width: int, height: int) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    check(
        f"export {out_png.name}",
        await adapter.export_image(
            {
                "file_path": str(out_png),
                "format_type": "png",
                "width": width,
                "height": height,
                "view_orientation": "current",
            }
        ),
    )


# --- staleness ---------------------------------------------------------------

def _sidecar(pair_id: str) -> Path:
    return COMP / "render" / f"{pair_id}.meta.json"


def is_stale(pair: dict, mpath: Path) -> bool:
    png = COMP / "render" / f"{pair['id']}.png"
    sc = _sidecar(pair["id"])
    if not png.exists() or not sc.exists():
        return True
    meta = json.loads(sc.read_text(encoding="utf-8"))
    return meta.get("camera") != pair["camera"] or meta.get("model_mtime") != mpath.stat().st_mtime


def write_sidecar(pair: dict, mpath: Path) -> None:
    _sidecar(pair["id"]).write_text(
        json.dumps({"camera": pair["camera"], "model_mtime": mpath.stat().st_mtime}),
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
    for va, vb in zip(ia.getdata(), ib.getdata(), strict=True):
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
        print("nothing to render")
        return 0
    # Parts before assemblies (assemblies are the slow opens).
    order = sorted(by_model, key=lambda m: (model_path(m).suffix.lower() == ".sldasm", m))
    n_pairs = sum(len(v) for v in by_model.values())
    print(f"rendering {n_pairs} pairs across {len(order)} models")

    async def build(adapter: Any) -> dict[str, str]:
        done: dict[str, str] = {}
        for model in order:
            mpath = model_path(model)
            check(f"open {mpath.name}", await adapter.open_model(str(mpath)))
            for pair in by_model[model]:
                pid = pair["id"]
                set_camera(adapter, pair["camera"])
                await capture(adapter, COMP / "render" / f"{pid}.png", width, height)
                write_sidecar(pair, mpath)
                composite.prepare_reference(pair)
                composite.side_by_side(pid)
                composite.blend_overlay(pid, pair.get("align"))
                done[pid] = "rendered"
            adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
            log(f"closed {model}")
        composite.regenerate(set(done))  # refresh scores.json for what changed
        return done

    return run_build(build)


if __name__ == "__main__":
    raise SystemExit(main())
