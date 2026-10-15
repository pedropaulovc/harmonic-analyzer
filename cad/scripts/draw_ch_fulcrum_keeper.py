r"""Create the curated machinist drawing for the fulcrum-shaft end keeper.

The SLDPRT remains authoritative.  This recipe supplies only the keeper's
views, dimension layout, hole callout, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The sheet runs at 2:1 (the bracket is ~16.5 x 32.2 x 14); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Four
views: the side profile (front), the plan (top, which carries the foot
screw's stations and the counterbored screw-hole and crown set-screw tap
callouts), the end view (right, which carries the width / shaft-axis-height /
crown / bore stack), and the isometric.  A bracket carries no frames and no
datums (drawing-guidelines.md): every location is a plain coordinate
dimension off a named face.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_fulcrum_keeper.py ch-fulcrum-keeper
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_channel_assembly_steps as steps
from ch_fulcrum_keeper_spec import (
    BORE_PAIR_CALLOUT,
    CBORE_DIA_MM,
    CORNER_R_MAX,
    CORNER_R_TOL_TYPE,
    CROWN_ABOUT_BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    FOOT_SCREW_SIDE_CALLOUT,
    FOOT_TIP_X,
    KEEPER_WIDTH,
    LUG_HALF_T,
    LUG_THICKNESS_CALLOUT,
    REFERENCE_DIMENSIONS,
    SCREW_X,
    SET_SCREW_HOLE_SPEC,
    SET_SCREW_STATION_CALLOUT,
    SUPPLY_HEIGHT_CALLOUT,
    SUPPLY_HEIGHT_MIN,
    SUPPLY_HEIGHT_TOL_TYPE,
)


SPEC = DRAWINGS_BY_NAME["ch_fulcrum_keeper"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The front (side-profile) view's model bbox is
# X -3..+13.5 (lug inner face to foot tip) by Y 0..32.2; at 2:1 that is
# ~33 x 64.4 mm.  Third angle: the plan (top view) rides above the front,
# the end view (right) sits to its right, the isometric top-right.
FRONT_CENTER = (0.110, 0.130)
TOP_CENTER = (0.110, 0.228)
RIGHT_CENTER = (0.225, 0.130)
ISO_CENTER = (0.330, 0.190)

# Model bbox centre the projected views are laid out around (front and plan
# share model X).
_X_MID = (-LUG_HALF_T + FOOT_TIP_X) / 2.0  # 5.25


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (2:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - _X_MID) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
HOLE_X_SHEET = _front_x(SCREW_X)  # screw-hole station, shared by the top view
CBORE_R_SHEET = CBORE_DIA_MM * SHEET_SCALE[0] / 2000.0
# The crown tap seen end-on in the plan, on the lug mid-plane (x = 0).
TAP_X_SHEET = _front_x(0.0)
TAP_R_SHEET = blind_cut_dia_mm(SET_SCREW_HOLE_SPEC) * SHEET_SCALE[0] / 2000.0
# The foot-hole callout stands below-right of the plan, so its leader drops
# from the text's left end to the counterbore's lower-right rim and leaves
# the plan through its bottom edge ~6 mm in from the foot-tip corner, away
# from the crown tap left of the hole. Text left of the plan (x 40..62 mm at
# y 238) laid the leader across the plan at y ~229 and through the tap's
# end-on circle, where it crossed the tap callout's leader at (99.7, 229.3)
# mm (leader-crosses-leader, farm run r8, HEAD c126e34b). The block's left
# end, x 126, keeps clear of the ScrewFromSide extension at y 228 above and
# of the front view's crown stack (x <= 108) and foot below.
FOOT_HOLE_CALLOUT_XY = (0.126, 0.202)
# The keeper is supplied undrilled (BORE_PAIR_CALLOUT), so the crown tap,
# which stops at the bore, is cut after the pair-ream, on the bore's axis
# (MR-fleet r2, 0eca37c: "TAP TO BORE" with no bore yet left the stage
# open, and the 7.000 off the side face read as locating it); its mouth is
# staked over the seated set screw at the channel assembly
# (drawing-guidelines.md rule 23 (lock threaded joints exposed to operating
# loads)'s lock, joint_retention).  The native sizes lead and say where they
# stop (both "<hw-thru>" extents read TO BORE; the thread class is the title
# block's), and the place, stage and staking step close the thread's own
# part (draw_ch_pivot_bracket's apex tap; MR-fleet r3, cb6e11e: seven rows
# mixing sequence, staking and size buried the thread on the last row).
# Machinist review r13: as two 86 mm rows centred at x 50 the block ran
# 5.7 mm past the left inner border (x 12.7).  Five rows of at most 24
# characters (~61 mm printed, 2.56 mm a character in r13) centred at x 58
# start at x ~27, ~14 mm in from it, and end ~4 mm left of the plan's inner
# face (x 93.5), in the band between the front view and the plan.  The tap's
# station prints above the plan (MR-fleet r1, 991a56e: in the front view its
# text sat 1 mm under this block's shoulder and the two read as one), so
# nothing else stands in that band.
SET_SCREW_EXTENT = "TO BORE"
SET_SCREW_QUALIFIER = (
    "ON BORE AXIS AFTER REAM;\n"
    "STAKE AT ASSEMBLY PER\n"
    f"{steps.step_ref(steps.SET_SCREWS_STAKED_KEY)}"
)
SET_SCREW_CALLOUT_XY = (0.058, 0.196)
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)
# The two keepers' bores are drilled and reamed through in one pass at their
# installed spacing (one straight line whatever LugRise prints) and each crown
# is then rounded about its own bore: bench instructions of the pair-ream
# step, so each rides its own dimension.
_PAIR_REAM_STEP = steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)
DIMENSION_CALLOUTS = {
    "BoreDia": f"{BORE_PAIR_CALLOUT},\nPER {_PAIR_REAM_STEP}",
    "CrownDia": f"{CROWN_ABOUT_BORE_CALLOUT},\nPER {_PAIR_REAM_STEP}",
}
# Each three-place size states the function that holds it there (rule 4,
# machinist review baseline: 6.000 / 3.000 / 7.000 printed with neither a
# band nor a reason): the tap's station off the DRO-set inner lug face puts
# the set screw on its shaft flat; the lug thickness holds the tap's outer
# web (MR-fleet r1: chained with the station it read as doing no work); the
# foot hole's side station centres the transferred frame tap in its web.
# The supplied blank's least height states what it is (MR-fleet r3: the
# square-topped blank's height was printed nowhere).
FRONT_CALLOUTS = {
    "LugThickness": LUG_THICKNESS_CALLOUT,
    "SupplyHeight": SUPPLY_HEIGHT_CALLOUT,
}
TOP_CALLOUTS = {
    "SetScrewLocation": SET_SCREW_STATION_CALLOUT,
    "ScrewFromSide": FOOT_SCREW_SIDE_CALLOUT,
}

# Per-view survivors of the marked-dimension import: parametric name ->
# sheet position.  The front view carries the lug thickness chained left of
# the foot length below the seat, its text and function out to the left
# over the notes, and under both the overall length (a reference, MR-fleet
# r3: the chain printed no overall), ~8 mm under the 6.000's dimension line
# (r4: 3.6 mm under it, its own line sat on the 6.000's arrows) and above
# the notes; the finished height (a reference) left of the lug and the
# supplied height (single limit MIN) outside it, the larger size outermost
# (r4: the supply size alone left its extension line in empty space above
# the drawn top); the foot height right of the foot tip; the foot-to-lug
# corner's R MAX up in the open corner, ~16 mm along the foot and up the lug
# (the ch_pivot_bracket placement), so its leader runs through the round's
# centre onto the arc.
# The plan carries the crown tap's station off the inner lug face above the
# plan, its text and function out to the left under the sheet border
# (MR-fleet r1: in the front view its extension line off the tap axis ended
# in mid-air; the plan sees the tap end-on), the foot screw's station off the
# foot tip (above the plan) and off the -Z side face, the latter's text and
# function under its extension lines right of the foot tip, clear of the
# foot-hole callout.  The end view carries the width plus the shaft-axis /
# crown stack, the reamed bore and the bore's place off a side face (a
# reference) above it.
FRONT_KEEP = {
    "LugThickness": (0.066, 0.086),
    "FootLength": (_front_x(SCREW_X), 0.086),
    "OverallLength": (FRONT_CENTER[0], 0.068),
    "FootRise": (0.140, 0.106),
    "OverallHeight": (0.080, FRONT_CENTER[1]),
    "SupplyHeight": (0.042, FRONT_CENTER[1]),
    "CornerRadius": (0.122, 0.130),
}
# The manufacturing notes' top-left corner's height (MR-fleet r4: 4 mm lower
# to make room for the overall length above them).
NOTES_TOP = 0.058
TOP_KEEP = {
    "SetScrewLocation": (0.068, 0.2535),
    "ScrewFromTip": (_front_x((FOOT_TIP_X + SCREW_X) / 2.0), 0.252),
    "ScrewFromSide": (0.178, 0.214),
}
# The end view's diameters take the near-side leader style (one arrow on the
# rim facing the text, no chord through the bore) and stand in clear paper on
# either side of the view; the width moves under it.  Machinist review r13
# (and its layout audit): with the width dimension above the crown, the crown
# callout over it and the bore callout right of the crown, the three texts
# overlapped one another and the crown/bore outline, and the Ø14 chord ran
# through the bore and across the 14.0 dimension line.  A diametric leader
# runs from the shoulder end facing the centre straight at it (r13: 30.1 and
# 32.0 deg, both exactly the bend-to-centre bearing), so:
# - Depth: below the foot; its extension lines leave the bottom corners (r13
#   drew them up from y 98.8) and stop ~7 mm under the view.
# - CrownDia: above-left, between the front view's crown stack (x <= 112)
#   and the end view; the leader lands on the crown arc at ~124 deg, clear of
#   every other line, the block ~9 mm under the foot-hole callout.
# - BoreDia: below-right, under the isometric note (>= 4 mm air; MR-fleet r1's
#   supply-condition row made it a row taller, so it sits 1.5 mm lower); the
#   leader leaves the bore at ~-55 deg and crosses only the lug's right edge.
RIGHT_KEEP = {
    "Depth": (0.225, 0.090),
    "LugRise": (0.196, 0.126),
    "CrownDia": (0.168, 0.180),
    "BoreDia": (0.304, 0.1225),
    # Above the crown, between the bore axis and the sheet-right side face
    # (the Right plane's +u): clear of the crown leader, which leaves the
    # arc up-left.
    "BoreFromSide": (
        RIGHT_CENTER[0] + KEEPER_WIDTH * SHEET_SCALE[0] / 4000.0,
        0.172,
    ),
}
NEAR_SIDE_DIAMETERS = ("CrownDia", "BoreDia")


def _one(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _require_single_limit(
    adapter: Any, annotations: list[Any], name: str, tol_type: int, limit_mm: float
) -> Any:
    """Prove ``name`` prints the part's single limit: measuring ``limit_mm``
    and carrying the native swTolMAX / swTolMIN type the part set."""
    annotation = _early_bound(_one(adapter, annotations, name), "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != tol_type:
        raise RuntimeError(
            f"{name} lost its native single-limit type {tol_type}: {int(tolerance.Type)}"
        )
    if not math.isclose(float(dimension.SystemValue), limit_mm / 1000.0, abs_tol=1e-9):
        raise RuntimeError(f"{name} does not measure its {limit_mm:g} mm limit")
    _telemetry.info(
        f"{name}: text {display.GetText(1)!r}, single-limit type {tol_type}"
    )
    return display


@_telemetry.traced("drawing.fulcrum_keeper.corner_radius")
def _dress_corner_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove the front view's CornerRadius prints the part's R MAX and stop
    its leader at the arc (draw_ch_pivot_bracket's corner radius).

    ``ArcExtensionLineOrOppositeSide`` False keeps the leader from running on
    through the arc into the part.
    """
    display = _require_single_limit(
        adapter, annotations, "CornerRadius", CORNER_R_TOL_TYPE, CORNER_R_MAX
    )
    display.ArcExtensionLineOrOppositeSide = False
    if bool(display.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("CornerRadius leader still runs to the opposite side")


def set_screw_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Rewrite the native crown-tap callout's definition parts (5..8).

    Both ``<hw-thru>`` extents become TO BORE, the thread class goes (the
    title block states it), and the place, stage and staking step close the
    thread's own part, which prints last (draw_ch_pivot_bracket's
    set_screw_callout_definitions). Every Hole Wizard size variable stays.
    """
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    if "\n".join(definitions.values()).count("<hw-thru>") != 2:
        raise RuntimeError(f"tap callout lacks its two native extents: {definitions!r}")
    updated = {
        part: text.replace("<hw-thru>", SET_SCREW_EXTENT)
        for part, text in definitions.items()
    }
    thread_parts = [
        part for part, text in updated.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(f"tap thread line is not in one callout part: {updated!r}")
    part = thread_parts[0]
    without_class = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", updated[part]))
    updated[part] = f"{without_class.rstrip()}\n{SET_SCREW_QUALIFIER}"
    return updated


@_telemetry.traced("drawing.fulcrum_keeper.tap_callout_text")
def _set_tap_callout_text(display: Any) -> None:
    """Write the rewritten definitions and prove they persisted."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = set_screw_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(native.GetText(part) or "") for part in (1, 2, 3, 4)}
    joined = "\n".join(resolved.values())
    if (
        persisted != updated
        or joined.count(SET_SCREW_EXTENT) != 2
        or "2B" in joined
        or not any(
            text.rstrip().endswith(SET_SCREW_QUALIFIER) for text in resolved.values()
        )
    ):
        raise RuntimeError(
            "crown tap callout text did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"crown tap callout: {resolved!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-keeper source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Keeper Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum keeper; shaft end bracket; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The tap and foot-screw stations and the two references are owned by
    # reference sketches the part saves blanked
    # (ch_fulcrum_keeper_spec.REFERENCE_SKETCHES); the hidden-owner curate
    # shows each in the view that dimensions it.
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for name in NEAR_SIDE_DIAMETERS:
        set_near_side_diameter(_one(adapter, right_annotations, name), f"keeper {name}")
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)
    _dress_corner_radius(adapter, front_annotations)
    _require_single_limit(
        adapter,
        front_annotations,
        "SupplyHeight",
        SUPPLY_HEIGHT_TOL_TYPE,
        SUPPLY_HEIGHT_MIN,
    )
    set_dimension_callouts(adapter, top_annotations, TOP_CALLOUTS)
    kept = [*front_annotations, *right_annotations]
    for name in REFERENCE_DIMENSIONS:
        set_reference_dimension(
            adapter, _one(adapter, kept, name), label=f"keeper {name}"
        )

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")

    # Counterbored screw hole ships as the native wizard callout on the plan
    # view, where it projects as its true circles.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(HOLE_X_SHEET, TOP_CENTER[1] + CBORE_R_SHEET),
        callout_xy=FOOT_HOLE_CALLOUT_XY,
        label="keeper foot screw hole",
    )
    # Crown set-screw tap: the plan sees it end-on at the crown top on the
    # lug mid-plane; its callout sits in the band between the front view
    # and the plan, left of both.
    tap_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TAP_X_SHEET - TAP_R_SHEET, TOP_CENTER[1]),
        callout_xy=SET_SCREW_CALLOUT_XY,
        label="crown set-screw tap",
    )
    _set_tap_callout_text(tap_callout)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, NOTES_TOP)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.150)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Keeper Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#1-72 Tapped Hole" note to the front view
        # once the crown tap carries a hole callout; the callout already
        # states the thread, and the note's leader ran through the
        # SetScrewLocation text (leader-through-text, farm run r8).
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
