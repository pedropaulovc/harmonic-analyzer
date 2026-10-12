r"""Create the one-sheet magnifier assembly drawing.

The sheet holds the Front, Right and Isometric orientation views at 1:4 and
two cropped side-view details of the wheel axle. Each detail prints one
assembly setting as the assembly's own model dimension
(mg_magnifier_assembly_spec):
- AXLE AS PRESSED (2:1) shows only the bar and the axle. It prints the press
  gauge from the bar's front face to the shank step. The wheel hub hides the
  step once it is fitted.
- WHEEL ENDSHAKE (4:1) shows the stack. It prints the endshake between the
  wheel's spigot face and the front washer.

Each detail is a cropped *Right model view, dimensioned while uncropped and
cropped after. On a native detail, the targeted import delivered nothing
(the ch-amplitude-bar finding). The dimensions belong to a construction chain
the assembly saves blanked. Each detail shows the chain in that view only
before importing (the ms-measuring-stick ClampedSetting pattern).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import sys
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)

import _telemetry
import mg_magnifier_assembly_spec as stack
from _check import check
from _com import _early_bound
from _drawing_balloons import isolate_drawing_view_components
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from mg_wheel_axle_spec import TIP_Y
from mg_wheel_bar_geom import BORE_ROW_HEIGHT


SPEC = DRAWINGS_BY_NAME["mg_magnifier_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
PDF_TITLE = "Magnifier Assembly Drawing"

SHEET_SCALE = (1.0, 4.0)
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.225, 0.140)
PRESS_NOTE_XY = (0.018, 0.064)
PRESS_NOTE_CHAR_HEIGHT = 0.0028


def _annotate_collar_press(adapter: Any) -> None:
    add_property_linked_note(
        adapter,
        "Drawing Notes",
        *PRESS_NOTE_XY,
        char_height=PRESS_NOTE_CHAR_HEIGHT,
    )

CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
# A detail's label note: its top-left corner this far under the detail's
# lowest ink and left of the circle's centre.
LABEL_GAP = 0.004
LABEL_INSET = 0.016


@dataclass(frozen=True)
class StackDetail:
    """One cropped *Right model view of the axle station.

    On the Right view, sheet x runs with machine -z (away from the bar) and
    sheet y with machine y. ``centre_d`` is the circle's centre as a stack
    station d (from the bar front face, on the axle line); ``centre`` is where
    that point lands on the sheet. ``ink_drop_mm`` is how far below the axle
    the detail's lowest printed edge stands, in model mm; the crop circle
    itself does not print.
    """

    title: str
    scale: tuple[int, int]
    centre_d: float
    radius_mm: float
    centre: tuple[float, float]
    stems: frozenset[str]
    ink_drop_mm: float
    # The parts the detail sets, named under its title (a blind reviewer of
    # run 20261012T192552713Z could not tell what the gauge presses).
    parts: str = ""

    @property
    def mm(self) -> float:
        """Sheet metres per model millimetre."""
        return self.scale[0] / self.scale[1] / 1000.0

    def sheet_xy(self, d: float, rise: float = 0.0) -> tuple[float, float]:
        """Stack station ``d``, ``rise`` mm above the axle, on the sheet."""
        return (
            self.centre[0] + (d - self.centre_d) * self.mm,
            self.centre[1] + rise * self.mm,
        )

    @property
    def model_centre_m(self) -> tuple[float, float, float]:
        return (
            stack.AXLE_X / 1000.0,
            stack.AXLE_Y / 1000.0,
            (stack.BAR_FRONT_Z - self.centre_d) / 1000.0,
        )

    @property
    def crop_radius(self) -> float:
        return self.radius_mm * self.mm

    @property
    def label_text(self) -> str:
        lines = (self.title, self.parts, f"SCALE {self.scale[0]} : {self.scale[1]}")
        return "\n".join(line for line in lines if line)

    @property
    def label_xy(self) -> tuple[float, float]:
        return (
            self.centre[0] - LABEL_INSET,
            self.centre[1] - self.ink_drop_mm * self.mm - LABEL_GAP,
        )


# The free field right of the isometric, above the title block. The gauge
# detail spans the bar's front face to past the step; its lowest edge is the
# bar's underside, the bore row height below the axle. The endshake detail
# spans the spigot face to the axle's tip; the hub and drum fill the circle
# up to the spigot face, so its lowest edge is the circle's chord there.
PRESSED = StackDetail(
    "AXLE AS PRESSED",
    (2, 1),
    stack.PRESS_GAUGE / 2.0,
    16.0,
    (0.330, 0.200),
    frozenset({"mg-wheel-bar", "mg-wheel-axle"}),
    BORE_ROW_HEIGHT,
    "MG-WHEEL-AXLE PRESSED\nINTO MG-WHEEL-BAR",
)
_ENDSHAKE_CENTRE_D = (stack.HUB_FRONT_D + TIP_Y) / 2.0
_ENDSHAKE_RADIUS = 7.0
ENDSHAKE = StackDetail(
    "WHEEL ENDSHAKE",
    (4, 1),
    _ENDSHAKE_CENTRE_D,
    _ENDSHAKE_RADIUS,
    (0.330, 0.112),
    frozenset(
        {
            "mg-wheel-bar",
            "mg-wheel-axle",
            "vn-wheel-axle-back-washer",
            "mg-magnifying-wheel",
            "mg-wheel-drum",
            "vn-wheel-axle-front-washer",
            "vn-wheel-axle-nut",
        }
    ),
    math.sqrt(_ENDSHAKE_RADIUS**2 - (_ENDSHAKE_CENTRE_D - stack.HUB_FRONT_D) ** 2),
)
# The gauge's dimension line runs above the bar, inside the circle, its
# callout above the value; the endshake's text stands right of the stack,
# above the nuts and past the crop, with its callout below.
GAUGE_RISE = 12.0
ENDSHAKE_RISE = 5.5
PRESSED_KEEP = {
    stack.PRESS_GAUGE_DIMENSION: PRESSED.sheet_xy(stack.PRESS_GAUGE / 2.0, GAUGE_RISE),
}
ENDSHAKE_KEEP = {
    stack.ENDSHAKE_DIMENSION: (
        ENDSHAKE.centre[0] + 0.055,
        ENDSHAKE.sheet_xy(stack.HUB_FRONT_D, ENDSHAKE_RISE)[1],
    ),
}
CALLOUT_LOCATION = {
    stack.PRESS_GAUGE_DIMENSION: "above",
    stack.ENDSHAKE_DIMENSION: "below",
}
# swDimensionTextParts_e: the compartment each location writes and reads.
CALLOUT_TEXT_PART = {"above": 3, "below": 4}


def _printable_callouts() -> dict[str, str]:
    """The callouts, refused if an above one holds a line break.

    SolidWorks keeps a line break in the above compartment, and GetText reads
    it back, yet prints none of that callout: the gauge's two-line callout in
    run 20261012T185729782Z, like the thumbnut's and the cone-gear shaft's
    before it. Below-callout line breaks print.
    """
    broken = sorted(
        name
        for name, location in CALLOUT_LOCATION.items()
        if location == "above" and "\n" in stack.DIMENSION_CALLOUTS[name]
    )
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return {name: stack.DIMENSION_CALLOUTS[name] for name in CALLOUT_LOCATION}


def _assert_callouts(displays: list[tuple[str, Any]], callouts: dict[str, str]) -> None:
    """Each setting's callout reads back from its own compartment."""
    for name, display in displays:
        part = CALLOUT_TEXT_PART[CALLOUT_LOCATION[name]]
        text = str(display.GetText(part) or "")
        if text.replace("\r\n", "\n") != callouts[name]:
            raise RuntimeError(
                f"{name}: {CALLOUT_LOCATION[name]} callout reads {text!r}, "
                f"not {callouts[name]!r}"
            )


def _activate(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _placed_detail(adapter: Any, detail: StackDetail) -> Any:
    """``detail`` uncropped: a *Right model view at its scale, moved so its
    circle's centre lands on ``detail.centre``."""
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Right", *detail.centre, scale=detail.scale),
        "IView",
    )
    label = f"{detail.title} centre"
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=detail.title)
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + detail.centre[axis] - centre[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move {detail.title} onto its spot")
    adapter.currentModel.EditRebuild3()
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    if max(abs(a - b) for a, b in zip(centre, detail.centre)) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"{detail.title} centre sits at {centre!r}, not {detail.centre!r}"
        )
    set_hidden_lines_removed(adapter, view)
    isolate_drawing_view_components(
        adapter, view, visible_stems=detail.stems, label=detail.title
    )
    return view


def _crop(adapter: Any, view: Any, detail: StackDetail) -> None:
    """Crop ``view`` to the circle round ``detail.centre``: sketch the circle
    in the active view's own sketch and Crop2 while it is still selected."""
    view = _early_bound(view, "IView")
    _activate(adapter, view, label=detail.title)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (
        detail.centre,
        (detail.centre[0] + detail.crop_radius, detail.centre[1]),
    ):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"failed to sketch the {detail.title} crop circle")
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"magnifier: {detail.title} Crop2 status {status}, IsCropped {cropped}",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{detail.title} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )


def _dimensioned_detail(
    adapter: Any, detail: StackDetail, keep: dict[str, tuple[float, float]]
) -> list[Any]:
    """Place ``detail``, show the stack chain in it, import ``keep``, crop it
    and prove the kept dimensions survived the crop."""
    view = _placed_detail(adapter, detail)
    _show_base_view_sketches(adapter, view, (stack.FEATURE,), label=detail.title)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep=keep,
        view_label=detail.title,
        dimensions_by_feature=stack.DRAWING_DIMENSIONS,
    )
    _crop(adapter, view, detail)
    kept = {
        dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
        for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
    }
    lost = sorted(set(keep) - kept)
    if lost:
        raise RuntimeError(
            f"{detail.title} lost {lost} to its crop; kept {sorted(kept)}"
        )
    _activate(adapter, view, label=detail.title)
    if add_note(adapter, detail.label_text, *detail.label_xy) is None:
        raise RuntimeError(f"failed to label {detail.title}")
    return annotations


def _stack_dimensions(adapter: Any) -> Callable[[], None]:
    """Both settings, with their callouts, places and bands read back once
    both details are cropped; the returned check re-reads the bands and the
    callouts once the drawing has settled."""
    callouts = _printable_callouts()
    annotations = [
        *_dimensioned_detail(adapter, PRESSED, PRESSED_KEEP),
        *_dimensioned_detail(adapter, ENDSHAKE, ENDSHAKE_KEEP),
    ]
    for name, location in CALLOUT_LOCATION.items():
        set_dimension_callouts(
            adapter, annotations, {name: callouts[name]}, location=location
        )
    precision = {
        name: places
        for names in stack.DRAWING_PRECISION.values()
        for name, places in names.items()
    }
    assert_imported_precision(adapter, annotations, precision)
    displays = [
        (
            dimension_name(adapter, annotation),
            _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            ),
        )
        for annotation in annotations
    ]
    if sorted(name for name, _ in displays) != sorted(stack.DIMENSION_TOLERANCES):
        raise RuntimeError(f"stack details imported {sorted(n for n, _ in displays)}")
    _assert_callouts(displays, callouts)

    def settled() -> None:
        for name, display in displays:
            band_m = stack.DIMENSION_TOLERANCES[name] / 1000.0
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            if (
                int(tolerance.Type) != 4  # swTolSYMMETRIC
                or abs(float(tolerance.GetMaxValue()) - band_m) > 1e-9
                or abs(float(tolerance.GetMinValue()) + band_m) > 1e-9
                or int(display.GetPrimaryTolPrecision2()) != stack.TOLERANCE_PRECISION
            ):
                raise RuntimeError(f"{name}: settled band changed")
        _assert_callouts(displays, callouts)

    return settled


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    check("open assembly drawing source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    for name, centre in (
        ("*Front", FRONT_CENTER),
        ("*Right", RIGHT_CENTER),
        ("*Isometric", ISO_CENTER),
    ):
        view = place_view(adapter, str(SOURCE), name, *centre, scale=SHEET_SCALE)
        # Front and Right print the simplified configuration at 1:4; the
        # isometric is the full-detail view.
        role = ViewRole.FULL_DETAIL if name == "*Isometric" else ViewRole.PLAIN
        apply_view_configuration(adapter, view, role=role, label=f"{PDF_TITLE} {name}")
    assert_full_detail_view(adapter, label=PDF_TITLE)
    settled = _stack_dimensions(adapter)
    _annotate_collar_press(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title=PDF_TITLE,
        scale=SHEET_SCALE,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
