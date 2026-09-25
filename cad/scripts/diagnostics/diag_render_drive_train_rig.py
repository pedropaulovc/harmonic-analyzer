r"""Diagnostic: off-axis renders of the pinion rig in the built drive-train.

The drive-train leaf saves one isometric, and at that scale the MHA-114 return
spring (behind the back strap) and the MHA-144 collar pin are invisible.  This
opens the built ``drive-train.SLDASM`` -- never saving it -- and captures three
oblique close-ups under ``cad/out/png/diag/drive-train-rig/``:

  a. from behind the back strap, the strap hidden (display only), so the
     spring blade and the face it pushes are in view;
  b. the collar and its pin hole against MHA-102 and the front strap;
  c. the whole rig in context.

The camera is an explicit ``IModelView.Orientation3``: the matrix layout is
proven on MathUtility before it is applied and read back after, and the zoom
box is each target's ``GetBox`` corners carried into view space (the
``ViewZoomTo2`` convention).  A layout that fails the proof falls back to the
named isometric and says so in the report, so one farm leaf always yields
pictures.  Throwaway: lives on diag/dt-rig-render, never merged.

Run: uv run python -m doit diag:drive_train_rig
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad" / "scripts"))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    OUT_PNG,
    OUT_SLDASM,
    _early_bound,
    _read_member,
    check,
    discard_open_documents,
    run_build,
)
from solidworks_mcp.adapters.com_variant import double_array  # noqa: E402

ASSEMBLY = OUT_SLDASM / "drive-train.SLDASM"
OUT_DIR = OUT_PNG / "diag" / "drive-train-rig"
REPORT = OUT_DIR / "drive-train-rig.json"
VIEW_FILES = {
    "a": "drive-train-rig-a-spring-behind-back-strap.png",
    "b": "drive-train-rig-b-collar-pin.png",
    "c": "drive-train-rig-c-rig-context.png",
}
RIG_STEMS = (
    "alignment-pinion",
    "pinion-bracket",
    "pinion-pivot-block",
    "pinion-pivot-shaft",
    "pinion-lift-rod",
    "pinion-spring",
    "pinion-cam-pin",
    "pinion-cam",
    "pinion-lever",
    "pinion-lever-pin",
    "pinion-handle",
    "pinion-arbor",
    "pinion-arbor-collar",
)
SW_TOP, SW_FRONT, SW_ISOMETRIC = 5, 1, 7  # swStandardViews_e
SW_HIDDEN = 0  # swComponentVisibilityState_e.swComponentHidden
WIDTH, HEIGHT = 1600, 1000


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _close(a, b) -> bool:
    return all(abs(x - y) < 1e-4 for x, y in zip(a, b, strict=True))


def _stem(name: str) -> str:
    return name.rsplit("-", 1)[0] if name.rsplit("-", 1)[-1].isdigit() else name


def _box(component) -> tuple[float, ...]:
    raw = [float(v) for v in component.GetBox(False, False)]
    lo = tuple(min(raw[i], raw[i + 3]) for i in range(3))
    hi = tuple(max(raw[i], raw[i + 3]) for i in range(3))
    return lo + hi


def _union(boxes, pad_m: float) -> tuple[float, ...]:
    lo = tuple(min(b[i] for b in boxes) - pad_m for i in range(3))
    hi = tuple(max(b[i + 3] for b in boxes) + pad_m for i in range(3))
    return lo + hi


def _centre(box) -> tuple[float, ...]:
    return tuple((box[i] + box[i + 3]) / 2.0 for i in range(3))


def _side(value: float) -> float:
    return 1.0 if value >= 0.0 else -1.0


class _Camera:
    """Orientation3 authoring with the matrix layout proven, not assumed."""

    def __init__(self, adapter, model) -> None:
        self.model = model
        self.utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
        self.layout: str | None = None
        self.proven = False
        self.calibration: dict[str, object] = {}

    def view(self):
        return _early_bound(self.model.ActiveView, "IModelView")

    def _map(self, xyz, transform) -> tuple[float, ...]:
        vector = _early_bound(
            self.utility.CreateVector(double_array(list(xyz))), "IMathVector"
        )
        mapped = _early_bound(vector.MultiplyTransform(transform), "IMathVector")
        return tuple(float(c) for c in mapped.ArrayData)

    def _point(self, xyz, transform) -> tuple[float, ...]:
        point = _early_bound(
            self.utility.CreatePoint(double_array(list(xyz))), "IMathPoint"
        )
        mapped = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        return tuple(float(c) for c in mapped.ArrayData)

    def calibrate(self) -> None:
        """Record the named Top/Front orientations: the top camera looks down
        model -Y, so model +Y must read view +Z (toward the viewer)."""
        with _telemetry.span("diag.calibrate") as sp:
            for name, const in (("top", SW_TOP), ("front", SW_FRONT)):
                self.model.ShowNamedView2("", const)
                orient = _early_bound(self.view().Orientation3, "IMathTransform")
                self.calibration[name] = {
                    "array": [float(v) for v in orient.ArrayData],
                    "model_x": self._map((1, 0, 0), orient),
                    "model_y": self._map((0, 1, 0), orient),
                    "model_z": self._map((0, 0, 1), orient),
                }
            top_up = _unit(self.calibration["top"]["model_y"])
            sp.set_attribute("top_model_y_in_view", str(top_up))
            _telemetry.info(f"calibration: {json.dumps(self.calibration)}")
            # The vector mapping stands in for the view's own; only a named view
            # that reads the way SolidWorks draws it proves they agree.
            self.proven = _close(top_up, (0.0, 0.0, 1.0))
            if not self.proven:
                _telemetry.warn(f"named Top maps model +Y to {top_up}, not view +Z")

    def _candidate(self, xs, ys, zs, layout: str):
        rows = (
            (*xs, *ys, *zs)
            if layout == "rows"
            else (xs[0], ys[0], zs[0], xs[1], ys[1], zs[1], xs[2], ys[2], zs[2])
        )
        data = [*rows, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
        return _early_bound(
            self.utility.CreateTransform(double_array(data)), "IMathTransform"
        )

    def aim(self, toward_viewer) -> str:
        """Point the camera so ``toward_viewer`` (model coords) faces the viewer
        with model +Y up the screen; returns how the camera was set."""
        zs = _unit(toward_viewer)
        xs = _unit(_cross((0.0, 1.0, 0.0), zs))
        ys = _cross(zs, xs)
        for layout in ("rows", "columns") if self.proven else ():
            transform = self._candidate(xs, ys, zs, layout)
            if not _close(self._map(zs, transform), (0, 0, 1)):
                continue
            if not _close(self._map(xs, transform), (1, 0, 0)):
                continue
            view = self.view()
            view.Orientation3 = transform
            readback = _early_bound(view.Orientation3, "IMathTransform")
            got = _unit(self._map(zs, readback))
            if not _close(got, (0, 0, 1)):
                _telemetry.warn(f"Orientation3 readback maps the camera axis to {got}")
                break
            self.layout = layout
            return f"orientation3-{layout}"
        _telemetry.warn(
            "no proven Orientation3 layout; falling back to named isometric"
        )
        self.model.ShowNamedView2("", SW_ISOMETRIC)
        return "fallback-isometric"

    def zoom(self, box) -> list[float]:
        """ViewZoomTo2 takes view-space corners: carry all eight box corners
        through the current orientation and frame their extent."""
        orient = _early_bound(self.view().Orientation3, "IMathTransform")
        corners = [
            self._point((x, y, z), orient)
            for x in (box[0], box[3])
            for y in (box[1], box[4])
            for z in (box[2], box[5])
        ]
        lo = [min(c[i] for c in corners) for i in range(3)]
        hi = [max(c[i] for c in corners) for i in range(3)]
        self.model.ViewZoomTo2(*lo, *hi)
        self.model.GraphicsRedraw2()
        return [*lo, *hi]


async def _capture(adapter, camera: _Camera, key: str, toward, box, report) -> None:
    path = (OUT_DIR / VIEW_FILES[key]).resolve()
    async with _telemetry.aspan("diag.camera", view=key) as sp:
        how = camera.aim(toward)
        zoom = camera.zoom(box)
        sp.set_attribute("camera", how)
    async with _telemetry.aspan("diag.save", view=key, path=str(path)):
        check(
            f"export_image {key}",
            await adapter.export_image(
                {
                    "file_path": str(path),
                    "format_type": "png",
                    "width": WIDTH,
                    "height": HEIGHT,
                    "view_orientation": "current",
                }
            ),
        )
    orient = _early_bound(camera.view().Orientation3, "IMathTransform")
    report["views"][key] = {
        "file": str(path),
        "camera": how,
        "toward_viewer": list(_unit(toward)),
        "model_box_m": list(box),
        "view_zoom_box": zoom,
        "orientation3": [float(v) for v in orient.ArrayData],
        "scale2": float(_read_member(camera.view(), "Scale2") or 0.0),
    }
    _telemetry.success(f"view {key}: {how} -> {path.name}")


async def build(adapter) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*"):
        stale.unlink()
    with _telemetry.span("diag.open", path=str(ASSEMBLY)):
        check("open drive-train", await adapter.open_model(str(ASSEMBLY)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
        rig: dict[str, list] = {}
        for raw in asm.GetComponents(True) or ():
            component = _early_bound(raw, "IComponent2")
            stem = _stem(str(_read_member(component, "Name2")))
            if stem in RIG_STEMS:
                rig.setdefault(stem, []).append(component)
        missing = [
            stem
            for stem in (
                "pinion-spring",
                "pinion-bracket",
                "pinion-arbor-collar",
                "pinion-arbor",
                "pinion-lever",
            )
            if stem not in rig
        ]
        if missing:
            raise RuntimeError(f"drive-train lacks rig components {missing}")
    boxes = {stem: [_box(c) for c in comps] for stem, comps in rig.items()}
    spring = boxes["pinion-spring"][0]
    straps = sorted(
        zip(boxes["pinion-bracket"], rig["pinion-bracket"]), key=lambda s: s[0][5]
    )
    back_strap = straps[-1]  # machine back is +Z
    collar = boxes["pinion-arbor-collar"][0]
    lever = boxes["pinion-lever"][0]
    report: dict[str, object] = {
        "assembly": str(ASSEMBLY),
        "components": {
            stem: [str(_read_member(c, "Name2")) for c in comps]
            for stem, comps in rig.items()
        },
        "boxes_m": boxes,
        "views": {},
    }

    camera = _Camera(adapter, model)
    camera.calibrate()
    report["calibration"] = camera.calibration

    away_from_lever = _side(_centre(collar)[0] - _centre(lever)[0])
    everything = [b for group in boxes.values() for b in group]
    await _capture(
        adapter,
        camera,
        "c",
        (away_from_lever, 0.7, -1.0),
        _union(everything, 0.010),
        report,
    )
    await _capture(
        adapter,
        camera,
        "b",
        (away_from_lever, 0.5, -1.0),
        _union([collar], 0.012),
        report,
    )

    # (a) looks from the machine back (+Z) past the hidden back strap, from the
    # strap's side of the spring, onto the blade face that pushes the strap.
    strap_side = _side(_centre(back_strap[0])[0] - _centre(spring)[0])
    back_strap[1].Visible = SW_HIDDEN
    report["hidden"] = [str(_read_member(back_strap[1], "Name2"))]
    await _capture(
        adapter,
        camera,
        "a",
        (0.8 * strap_side, 0.6, 1.0),
        _union([spring, back_strap[0]], 0.005),
        report,
    )

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with _telemetry.span("diag.close"):
        discard_open_documents(adapter)  # never saved: the hide is display-only
    return {key: str(OUT_DIR / name) for key, name in VIEW_FILES.items()}


if __name__ == "__main__":
    sys.exit(run_build(build))
