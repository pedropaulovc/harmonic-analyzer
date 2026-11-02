r"""Create the manufacturing drawing for the channel anchor jam nut (MHA-CH-14).

The sheet prints decimal inch (the part's ``drawing_unit: in``).  The face
view is ``*Front``, looking at the driven face: the drive cut runs across it,
and it carries the slot width and the native #6-32 UNC-2B through-thread
callout, its tap drill at three places.  The side view (``*Right``) looks
along the cut, so the notch shows in profile: the thickness, the cut depth
and the O.D. print there (drawing-guidelines.md rule 11 (turned parts read
like the lathe)).  No general note and no roughness symbol.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_anchor_jam_nut.py ch-anchor-jam-nut
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_anchor_jam_nut_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    OD,
    OD_CALLOUT,
    OD_WALL_CALLOUT,
    SLOT_CALLOUT,
    TAP_DRILL_DIA,
    THICKNESS,
    THICKNESS_CALLOUT,
    THREAD,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_anchor_jam_nut"]
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

# A small round nut (about .26 across, .14 thick) at 5:1: the face view, the
# side view and the isometric on one row midway between the top border and
# the title block.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
FRONT_CENTER = (0.090, 0.155)
RIGHT_CENTER = (0.215, 0.155)
ISO_CENTER = (0.375, 0.155)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
_HALF_OD = OD / 2.0 * _S
_HALF_T = THICKNESS / 2.0 * _S

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# The O.D. and the slot width both import on the face view.  The slot width
# stays there, left of the face across the cut, its value and callout hung
# below the lower arrow (farm r7: centred between the arrows, both extension
# lines ran through the value); the O.D. is a donor there (its line would
# cross the cut and the thread callout) and moves onto the side view, right
# of the nut.  The side view looks along the cut (the driven face on its
# left): the thickness hangs under it, the cut depth sits over the notch
# above it.
FRONT_KEEP = {
    "NutOd": (FRONT_CENTER[0] - _HALF_OD - 0.020, FRONT_CENTER[1] - 0.040),
    "SlotWidth": (FRONT_CENTER[0] - _HALF_OD - 0.012, FRONT_CENTER[1] - 0.012),
}
RIGHT_KEEP = {
    # Hung right of the side view, arrows in from outside: its
    # engagement line is wider than the 18 mm between the extension lines,
    # which ran through it when centred (review r8).
    "NutThickness": (
        RIGHT_CENTER[0] + _HALF_T + 0.042,
        RIGHT_CENTER[1] - _HALF_OD - 0.018,
    ),
    # Left of the driven face, arrows in from outside (farm r7: centred over
    # the 5 mm notch, the floor's extension line ran through the value).
    "SlotDepth": (
        RIGHT_CENTER[0] - _HALF_T - 0.009,
        RIGHT_CENTER[1] + _HALF_OD + 0.018,
    ),
}
# Far enough right that the O.D.'s callouts, centred on its value (the
# neighbour line is about 0.104 wide), clear the side view's face and the
# thickness extension line (review r10); the isometric stands off past them.
OD_ON_SIDE = (RIGHT_CENTER[0] + _HALF_T + 0.058, RIGHT_CENTER[1])
THREAD_CALLOUT_XY = (FRONT_CENTER[0] + _HALF_OD + 0.012, FRONT_CENTER[1] + 0.035)
# Rule 12 (hole and slot callouts say what to do); rule 4: the O.D.'s tight
# band names what bounds it on both sides; rule 20: the thin nut's
# engagement is stated as a fact on its thickness.
DIMENSION_CALLOUTS = {
    "SlotWidth": SLOT_CALLOUT,
    "NutOd": OD_CALLOUT,
    "NutThickness": THICKNESS_CALLOUT,
}
DIMENSION_CALLOUTS_ABOVE = {"NutOd": OD_WALL_CALLOUT}
# The through tap's native drill diameter prints .XXX (#36, .1065).
THREAD_CALLOUT_PRECISION = {"hw-thrutapdrldia": 3}


def _assert_native_thread(display: Any) -> None:
    """Read the real Hole Wizard callout; never substitute typed dimensions."""
    display = _early_bound(display, "IDisplayDimension")
    texts = [display.GetText(part) for part in (1, 2, 3, 4)]
    if any(not isinstance(text, str) for text in texts):
        raise RuntimeError("jam nut native thread callout has an invalid readback")
    resolved = "".join(texts).replace(" ", "").replace("#", "").upper()
    if (
        THREAD.replace("#", "") not in resolved
        or "UNC" not in resolved
        or "2B" not in resolved
    ):
        raise RuntimeError(
            f"jam nut native thread callout does not carry the source thread: {texts!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open jam nut source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-anchor-jam-nut"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Channel Anchor Jam Nut Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "Channel Anchor Jam Nut; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [a for a in front_annotations if dimension_name(adapter, a) == "NutOd"]
    if len(od_donors) != 1:
        raise RuntimeError("expected one jam nut O.D. donor dimension")
    moved_od = move_model_dimension(
        adapter, od_donors[0], right, OD_ON_SIDE, source_view=front
    )
    annotations = [
        *(a for a in front_annotations if dimension_name(adapter, a) != "NutOd"),
        *right_annotations,
        moved_od,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the jam nut face view")
    # The tap-drill edge: the one visible circle of the Hole Wizard feature
    # from the driven face.
    thread_callout = add_native_hole_callout(
        adapter,
        front,
        edge=visible_circle_edge(adapter, front, TAP_DRILL_DIA),
        callout_xy=THREAD_CALLOUT_XY,
        label=f"{THREAD} UNC-2B through thread",
    )
    _assert_native_thread(thread_callout)
    set_hole_callout_precision(
        thread_callout, THREAD_CALLOUT_PRECISION, label="jam nut through tap"
    )
    # The face view shows the tap's major-diameter arc too (machinist review).
    import_cosmetic_threads(adapter, front)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Anchor Jam Nut Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own tapped-hole note to the face view once the
        # real native callout exists (the transgear thumbnut's measured
        # behaviour); it repeats the same thread, so finalize removes it.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
