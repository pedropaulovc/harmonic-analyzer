r"""Create the curated machinist drawing for the amplitude bar.

The SLDPRT remains authoritative.  This recipe supplies only the amplitude-bar
views, dimension layout, and manufacturing notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length only), a 4:1 top end view for the square
section, and a small 1:8 isometric; the two tiny end notches and the top pin
hole are dimensioned in the notes.  The sheet runs at 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_amplitude_bar.py amplitude-bar
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from amplitude_bar_spec import (
    BAR_LENGTH,
    BAR_WIDTH,
    BOTTOM_NOTCH_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    TOP_NOTCH_HEIGHT,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view, view_name


SPEC = DRAWINGS_BY_NAME["amplitude_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 4.0)  # 1:4
FRONT_CENTER = (0.110, 0.140)
TOP_CENTER = (0.220, 0.150)  # square-section end view (4:1)
ISO_CENTER = (0.330, 0.140)


FRONT_KEEP = {
    "BarLength": (0.075, FRONT_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}


@dataclass(frozen=True)
class NotchDetail:
    """A native detail of one end notch, off the 1:4 front view.

    ``fence_mm`` is the fence centre in part (x, y) -- the Front-plane profile
    frame the front view shows unrotated, bar width along x from the origin
    corner, length along y -- and ``centre`` where that point lands on the
    sheet.
    """

    label: str
    scale: tuple[int, int]
    fence_mm: tuple[float, float]
    radius_mm: float
    centre: tuple[float, float]

    @property
    def mm(self) -> float:
        """Sheet metres per part millimetre in the detail."""
        return self.scale[0] / self.scale[1] / 1000.0

    def sheet_xy(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        return (
            self.centre[0] + (x_mm - self.fence_mm[0]) * self.mm,
            self.centre[1] + (y_mm - self.fence_mm[1]) * self.mm,
        )

    @property
    def label_xy(self) -> tuple[float, float]:
        """The native label's top centre, under the fence."""
        return (self.centre[0], self.centre[1] - self.radius_mm * self.mm - 0.004)


# At 1:4 an end notch is under a millimetre on the sheet, so each end's width
# and depth -- the foot notch's with its one-sided band (Codex #936
# PRRT_kwDOPHDy386mWF0L) -- print in a native detail. DETAIL A (the foot, 4:1)
# sits under the end view, left of the title block; DETAIL B (the 12.7-deep top
# notch, 2:1) over the isometric, right of the notes.
DETAIL_A = NotchDetail("A", (4, 1), (BAR_WIDTH / 2.0, 2.0), 5.5, (0.165, 0.095))
DETAIL_B = NotchDetail(
    "B", (2, 1), (BAR_WIDTH / 2.0, BAR_LENGTH - 6.0), 8.0, (0.300, 0.222)
)
# A callout's text stands this far outside the bar's edge or end.
DETAIL_TEXT_GAP = 0.010
DETAIL_A_KEEP = {
    # Left of the bar, level with the notch: the depth and its band.
    "BottomNotchHeight": (
        DETAIL_A.sheet_xy(0.0, 0.0)[0] - DETAIL_TEXT_GAP,
        DETAIL_A.sheet_xy(0.0, BOTTOM_NOTCH_HEIGHT / 2.0)[1],
    ),
    # Under the open end: its witnesses run down through the notch's air.
    "BottomNotchWidth": (
        DETAIL_A.centre[0],
        DETAIL_A.sheet_xy(0.0, 0.0)[1] - 0.008,
    ),
}
DETAIL_B_KEEP = {
    "TopNotchHeight": (
        DETAIL_B.sheet_xy(BAR_WIDTH, 0.0)[0] + DETAIL_TEXT_GAP,
        DETAIL_B.sheet_xy(0.0, BAR_LENGTH - TOP_NOTCH_HEIGHT / 2.0)[1],
    ),
    "TopNotchWidth": (
        DETAIL_B.centre[0],
        DETAIL_B.sheet_xy(0.0, BAR_LENGTH)[1] + 0.008,
    ),
}


def _notch_detail(adapter: Any, front: Any, detail: NotchDetail) -> Any:
    """A native detail of one end notch (the MHA-065 DETAIL A recipe)."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not drawing.ActivateView(view_name(adapter, front)):
        raise RuntimeError(f"failed to activate detail {detail.label}'s parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        (detail.fence_mm[0] / 1000.0, detail.fence_mm[1] / 1000.0, 0.0),
        label=f"detail {detail.label} centre",
    )
    radius = detail.radius_mm * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError(f"failed to create detail {detail.label}'s fence")
    view = drawing.CreateDetailViewAt4(
        *detail.centre,
        0.0,
        0,  # swDetViewSTANDARD
        *detail.scale,
        detail.label,
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if view is None:
        raise RuntimeError(f"failed to create detail {detail.label}")
    view = _early_bound(view, "IView")
    view.ScaleRatio = double_array([float(value) for value in detail.scale])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in view.GetOutline())
    position = tuple(float(value) for value in view.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError(f"detail {detail.label} has invalid bounds")
    target = [
        position[axis] + detail.centre[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to position detail {detail.label}")
    draw.EditRebuild3()
    notes = tuple(_read_member(view, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(
            f"expected one native detail {detail.label} label, found {len(notes)}"
        )
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*detail.label_xy, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError(f"failed to position detail {detail.label}'s label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"detail {detail.label}'s label did not persist: {actual}")
    return view


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open amplitude-bar source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Amplitude Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "amplitude bar; chrome steel; coefficient bar",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 4))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 8))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    # By feature: the profile owns every printed dimension, so the front view
    # keeps the length and hands the notch sizes to the details.
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for detail, keep in ((DETAIL_A, DETAIL_A_KEEP), (DETAIL_B, DETAIL_B_KEEP)):
        view = _notch_detail(adapter, front, detail)
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=f"detail {detail.label}",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    # Decimal places (and so the band each dimension claims) are authored on
    # the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    # The projected end outline is not a selectable topological EDGE after the
    # end notches are overlaid. The manufacturing note owns the explicit 6.35
    # square section; this enlarged end view confirms its shape without a
    # duplicate, topology-fragile dimension.

    add_property_linked_note(adapter, "Manufacturing Notes", 0.150, 0.230)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.070)
    # The end view runs 16x the sheet scale -- label it or "do not scale
    # drawing" leaves its size unreadable.
    # Below the 4:1 end view -- the manufacturing-notes block above descends
    # to ~y=0.175 and owns the old 0.180 spot (layout audit).
    add_property_linked_note(adapter, "End View Note", 0.205, 0.120)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Amplitude Bar Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
