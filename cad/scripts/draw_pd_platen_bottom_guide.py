r"""Create the machinist drawing for MHA-PD-27, the platen's bottom guide.

The 1:1 front view carries the rail's length, height and the four printed
lock taps' stations; the top view above it shows the four rack-screw
counterbores; the right view carries the depth's native LIMITs. Each hole
family has one native Hole Wizard callout: the lock taps plain, the five
platen-screw taps transferred from MHA-PD-02 and the four rack-screw holes
struck from MHA-PD-26, both at MHA-PD-00 (owner rulings 2026-11-13 and
delegated rulings 2026-11-14, #2410). The sheet prints decimal inch (#290).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_platen_bottom_guide.py pd-platen-bottom-guide
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
)

import _config
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
import _telemetry
from pd_platen_bottom_guide_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_DEPTH_CALLOUT,
    GUIDE_LENGTH,
    LOCK_TAP_SPEC,
    LOCK_TAP_X,
    PLATEN_TAP_SPEC,
    PLATEN_TAP_X,
    SCREW_CBORE_DIA,
    SCREW_CBORE_FRONT_WALL_TEXT,
    SCREW_HOLE_X,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen_bottom_guide"]
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

# The 1:1 front view centred at sheet x 0.190 (the 10.62 rail spans
# ~0.055..0.325); the top view stands over it (third angle), the right view
# beside it, the isometric at 1:2 in the field over the right view.
FRONT_CENTER = (0.190, 0.120)
TOP_CENTER = (FRONT_CENTER[0], 0.160)
RIGHT_CENTER = (0.390, 0.120)
ISO_CENTER = (0.355, 0.215)
ISO_SCALE = (1, 2)
ISO_NOTE_XY = (0.3245, 0.180)
_LEFT_X = FRONT_CENTER[0] - GUIDE_LENGTH / 2000.0
FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], 0.080),
    "Height": (0.354, FRONT_CENTER[1]),
    # The lock taps' stations stack under the view, the row left of it.
    "LockTap1X": (_LEFT_X + LOCK_TAP_X[0] / 2000.0, 0.104),
    "LockTap2X": (_LEFT_X + LOCK_TAP_X[1] / 2000.0, 0.098),
    "LockTap3X": (_LEFT_X + LOCK_TAP_X[2] / 2000.0, 0.092),
    "LockTap4X": (_LEFT_X + LOCK_TAP_X[3] / 2000.0, 0.086),
    "LockTapY": (_LEFT_X - 0.012, FRONT_CENTER[1]),
}
# The depth's limits and clearance text are wider than the 10 mm right view:
# centred over it (r3, r4) both extension lines ran up into CLEAR MHA-PD-19,
# so the text stands left of the left extension line, the dimension line
# carried out, clear right of the top view and above the height's arrow.
RIGHT_KEEP = {"Depth": (0.358, 0.153)}
# The height's .XXX band is half of the counterbore floor's band, which the
# rack screws' worst engagement pays (pd_feed_rack_spec.SCREW_FLOOR_BAND); the
# band names its mate by number (rule 4, r4), two lines that fit between the
# front and right views.
SCREW_NUMBER = _config.parts("sh-vn-fillister-screw-91794a055")["number"]
HEIGHT_CALLOUT = f"SETS ENGAGEMENT\nOF {SCREW_NUMBER}"
# Both front-view tap callouts sit between the views, clear under the top
# view (its underside ~0.155) so the counterbore leader into it runs past
# them; the platen-tap leader takes the middle hole, right of the lock taps,
# so the two leaders never cross (first farm render, r2).
LOCK_CALLOUT_XY = (0.090, 0.1435)
PLATEN_CALLOUT_XY = (0.215, 0.1435)
PLATEN_CALLOUT_HOLE = len(PLATEN_TAP_X) // 2
SCREW_CALLOUT_XY = (0.150, 0.200)
PLATEN_NUMBER = _config.parts("pd-platen")["number"]
RACK_NUMBER = _config.parts("pd-feed-rack")["number"]
LOCK_NUMBER = _config.parts("pd-guide-lock")["number"]
LOCK_CALLOUT_BELOW = f"FOR {LOCK_NUMBER} LOCKS"
PLATEN_CALLOUT_BELOW = f"TRANSFER FROM {PLATEN_NUMBER} AT ASSEMBLY"
SCREW_CALLOUT_BELOW = (
    f"TRANSFER FROM {RACK_NUMBER} AT ASSEMBLY\n{SCREW_CBORE_FRONT_WALL_TEXT}"
)
TAPPED_HOLE_NOTE = "Tapped Hole"
_TAP_DRILL = blind_cut_dia_mm(LOCK_TAP_SPEC)


def _rim(view: Any, station: float, diameter: float, *, label: str) -> Any:
    """The one visible circular rim of ``diameter`` at model-X ``station``
    (draw_pd_platen_guide._hole_rim_entities)."""
    matches = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        parameters = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        if abs(parameters[0] - station) <= 0.02 and abs(parameters[6] - diameter / 2.0) <= 0.02:
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"{label}: {len(matches)} rims at {station:g} mm; expected 1")
    return matches[0]


@_telemetry.traced("drawing.hole_callout_below")
def _set_callout_below(display: Any, text: str, *, label: str) -> None:
    """Write ``text`` under a native hole callout and read it back
    (draw_sm_gooseneck_end_plug._set_tap_callout_below)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(f"{label} callout rows did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open bottom-guide source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Isometric View Note",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        layout=SPEC.layout,
        decimals=3,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Bottom Guide Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen bottom guide; manufacturing drawing; #4-40 UNC; #0 rack screws",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The depth's one-sided band and the height's .XXX band name what they
    # protect (rule 4).
    set_dimension_callouts(
        adapter, annotations, {"Depth": GUIDE_DEPTH_CALLOUT, "Height": HEIGHT_CALLOUT}
    )
    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")

    for view, station, diameter, xy, below, label in (
        (front, LOCK_TAP_X[0], _TAP_DRILL, LOCK_CALLOUT_XY, LOCK_CALLOUT_BELOW,
         f"lock taps ({LOCK_TAP_SPEC.size})"),
        (front, PLATEN_TAP_X[PLATEN_CALLOUT_HOLE], _TAP_DRILL, PLATEN_CALLOUT_XY,
         PLATEN_CALLOUT_BELOW,
         f"platen-screw taps ({PLATEN_TAP_SPEC.size})"),
        (top, SCREW_HOLE_X[0], SCREW_CBORE_DIA, SCREW_CALLOUT_XY, SCREW_CALLOUT_BELOW,
         "rack-screw counterbores"),
    ):
        callout = add_native_hole_callout(
            adapter,
            view,
            edge=_rim(view, station, diameter, label=label),
            callout_xy=xy,
            label=label,
        )
        if "tap" in label:
            omit_title_block_thread_class(callout, label=label)
        _set_callout_below(callout, below, label=label)
    rebuild_drawing(adapter, label="bottom-guide hole callouts")
    removed = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed} automatic tapped-hole label(s)")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Bottom Guide Manufacturing Drawing",
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
