r"""Create the curated machinist drawing for the channel (top) lever.

The SLDPRT remains authoritative.  Every size, location and band prints from
its native model dimension (``ch_channel_lever_notes.DRAWING_DIMENSIONS``, at
the places the part authors); this recipe supplies only the views, the
placement of those dimensions, the function each tight band serves, the hole
callouts and one reference overall length.
Sheet/template and export behaviour lives in ``_drawing_common``.

The lever is a long thin third-class lever (7.29 in over the hub, .37 in
tall to a 5.50 taper start, then tapering to an R.167 tip, .118 in thick); the sheet
prints decimal inch (the part's ``drawing_unit: in``).  The sheet runs at
1:1: the front view carries the profile, bore, hub, both arms from the
fulcrum bore and the overall length; the top view the plate thickness and
the hub length; a 1:2 isometric.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_channel_lever.py ch-channel-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
# The plate offset is owned by a reference sketch the part saves hidden.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _printed_limits import drilled_limits, limits
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm, drill_process
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from ch_channel_lever_notes import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_PRECISION_BY_NAME,
    ROOT_CORNER_R,
    ROOT_CORNER_REASON,
)
from ch_channel_lever_spec import (
    BAR_PIN_HOLE_SPEC,
    BAR_PIN_X,
    BAR_TALL,
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    LEVER_SPRING_X,
    LEVER_THICKNESS,
    LEVER_THICKNESS_BAND,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    PIVOT_HOLE_SPEC,
    PLATE_OFFSET,
    PLATE_OFFSET_TOLERANCE,
    SPRING_EYE_HOLE_SPEC,
    TAPER_START_X,
    TIP_ARC_CX,
    TIP_END_X,
    TIP_RADIUS,
    TIP_WALL_TEXT,
    UNIT,
    taper_tangent_point,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["ch_channel_lever"]
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

SHEET_SCALE = (1.0, 1.0)  # 1:1
ISO_SCALE = (1, 2)

_HUB_R = HUB_DIA / 2.0
_BBOX_CX = (-_HUB_R + TIP_END_X) / 2.0  # both 1:1 views centre on the hub..tip span
_SPRING_HOLE_DIA = blind_cut_dia_mm(SPRING_EYE_HOLE_SPEC)
_BAR_PIN_DIA = blind_cut_dia_mm(BAR_PIN_HOLE_SPEC)

FRONT_CENTER = (0.150, 0.155)
TOP_CENTER = (0.150, 0.220)  # above the profile: plate thickness, hub length
ISO_CENTER = (0.345, 0.215)
ISO_NOTE_XY = (0.315, 0.185)  # left end: centres the label under the iso


def _name_hole_mate(display: Any, *, label: str) -> None:
    """Add the hole's mate under its native callout.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, size and depth definitions
    stay untouched, so the Hole Wizard variables stay associative
    (draw_ch_rocker_arm_tl_profile_fixture._locate_pivot_tap_depths)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    below = definitions[8].rstrip()
    mate = HOLE_MATES[label]
    updated = f"{below}\n{mate}" if below else mate
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            f"{label}: hole callout mate or native definitions did not persist: "
            f"{[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


def _add_centerline(
    adapter: Any, view: Any, points: tuple[tuple[float, float], ...], label: str
) -> None:
    """InsertCenterLine2 on the two edges through ``points`` (part mm)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the front view for the {label}")
    draw.ClearSelection2(True)
    for index, (mx, my) in enumerate(points):
        x, y = model_point_in_view(
            adapter,
            view,
            (mx / 1000.0, my / 1000.0, 0.0),
            label=f"{label} edge {index + 1}",
        )
        if not draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError(f"failed to select {label} edge {index + 1}")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to insert the {label} between its edges")


def _add_bar_centerlines(adapter: Any, view: Any) -> None:
    """Draw the lever's longitudinal axis from the hub to the tip.

    The fulcrum bore, the bar-pin hole and the spring-eye hole lie on the
    bar's mid-height axis; the line through their centre marks prints that,
    and the .37 bar and the taper symmetric about it, so the three holes'
    cross-bar position is drawn, not implied (r5 machinist review, clarity).
    draw_dt_crank_arm's recipe, twice: InsertCenterLine2 on the two
    full-depth edges (between the hub and the bar-pin hole) bisects them up
    to the 5.50 taper start, and on the two taper edges (symmetric about the
    same axis) carries it on to the #21 hole (#3113 code review).
    """
    _add_centerline(
        adapter,
        view,
        tuple((BAR_PIN_X / 2.0, side * BAR_TALL / 2.0) for side in (-1.0, 1.0)),
        "bar centreline",
    )
    tangent_x, tangent_y = taper_tangent_point()
    mid_x = (TAPER_START_X + tangent_x) / 2.0
    mid_y = (BAR_TALL / 2.0 + tangent_y) / 2.0
    _add_centerline(
        adapter,
        view,
        tuple((mid_x, side * mid_y) for side in (-1.0, 1.0)),
        "taper centreline",
    )
    count = int(_early_bound(view, "IView").GetCenterLineCount())
    if count != 2:
        raise RuntimeError(f"front view carries {count} centrelines, expected 2")


def _sheet_x(mx: float) -> float:
    """Sheet x of a model x in either 1:1 view (both are bbox-centred)."""
    return FRONT_CENTER[0] + (mx - _BBOX_CX) / 1000.0


# --- Mates and functions named on the bands' own callouts (rules 4 and 7). ---
SHAFT_NUMBER = _config.parts("ch-fulcrum-shaft")["number"]
BAR_NUMBER = _config.parts("ch-amplitude-bar")["number"]
PIN_NUMBER = _config.parts("sh-vn-pivot-pin")["number"]
SPRING_NUMBER = _config.parts("ch-vn-channel-spring-installed")["number"]
STATIONS = _config.machine("channels", "count")

# The bar-to-hub roots print their own 2X R.065 (owner ruling 2026-11-23,
# tool audit Q9: over the title block's INSIDE CORNERS R.040 MAX), so the
# radius names why nothing needs them small. A hole location carries its
# value and band only (rule 7): each drilled hole's mate rides its own hole
# callout. The fulcrum bore is drilled F at the DRILLED HOLES row (owner
# ruling 2026-11-24, fit audit question 1): its callout names the drill and
# the shaft it runs on, and prints no number of its own (rule 4, form 1).
FRONT_CALLOUTS = {
    "FulcrumDia": f"{drill_process(PIVOT_HOLE_SPEC)} THRU\nRUNNING CLEARANCE ON {SHAFT_NUMBER}",
    # The taper is drawn and dimensioned, not narrated (#3113 r4 review): the
    # .37 sits on the kink and the kink has its own location. The radius
    # prints three places for the #21 hole's wall, so it states that wall
    # once (rules 3 and 20; MHA-CH-02 RV-04).
    "TipRadius": f"TANGENT TO EDGES\n{TIP_WALL_TEXT}",
    "RootCornerR": ROOT_CORNER_REASON,
}
# What engages each drilled hole rides its own hole callout (machinist r5:
# on the arm's location it did not say the hole is a running bore).
HOLE_MATES = {
    "bar-pin hole": f"RUNS ON PIN\n{PIN_NUMBER}",
    # The two arms' ratio is the channel's lever ratio (error_budget gain).
    "spring-eye hole": f"HOOKS {SPRING_NUMBER};\nSETS LEVER RATIO",
}
# Each drilled hole's native size prints the exact decimal of its named drill
# (rule 3: #47 is .0785, #21 is .159).
HOLE_PRECISION = {"bar-pin hole": {"hw-diam": 4}, "spring-eye hole": {"hw-diam": 3}}
# The hub length's +.001/.000 is narrower than the shop's turned-length row
# (+/-.001); it names the stack it sets (rule 4) and nothing more. The 20-hub
# stack's length and end play between the MHA-CH-07 keepers are the channel
# assembly's acceptance (MHA-CH-00), not this part's (machinist r1: a second
# line here was assembly narration), and the band is accepted on RV-03.
# The plate's .091 +/-.002 offset in the hub is a tight band, so it names
# what it serves (rule 4; ch-fab-2 r2: 3/3 runs asked for the mate, and a
# second reason on the .118 read as narration): each bar rides its lever's
# plate, so the offset spaces neighbouring bars in the stack
# (sh_vn_pivot_pin_bar_spec). The offset is a location, so its dimension
# carries only a flag to the numbered note that names the mate (rule 7;
# dfm-2340 r12: 2/3 runs).
PLATE_OFFSET_NOTE_NUMBER = 1
PLATE_OFFSET_NOTE = f"{PLATE_OFFSET_NOTE_NUMBER}. SPACES {BAR_NUMBER} BARS IN STACK."
# The sheet's one numbered note, as the feature export reads it: kept here,
# not in ch_channel_lever_notes, which the part build imports.
DRAWING_NOTES = PLATE_OFFSET_NOTE
TOP_CALLOUTS = {
    "LeverThick": f"SLIDING FIT IN NOTCH\nOF {BAR_NUMBER}",
    "PlateOffset": f"SEE NOTE {PLATE_OFFSET_NOTE_NUMBER}",
    "HubLength": f"SETS PITCH OF {STATIONS}X\nSTACK ON {SHAFT_NUMBER}",
}

FRONT_KEEP = {
    # Left of the hub, just above its axis: the near-side leader stops on the
    # left rim, clear of the overall length's extension line below the hub
    # and of the drill leader, which lands from the upper right.
    "HubDia": (0.033, 0.165),
    # The F drill's three rows centre on this point, ~87 mm wide (widest,
    # RUNNING CLEARANCE ON MHA-CH-04; measured on run 6586e65b). At x .050
    # the row and its shelf began at x 6.6 mm, left of the inner border at
    # 12.7 (rule 13); at .059 they begin 15.6 mm, 2.9 mm inside, and end at
    # ~103 mm, 50 mm short of the #47 callout. 2 mm higher, the leader still
    # lands on the upper-right rim.
    "FulcrumDia": (0.059, 0.192),
    # Above the bar on the taper start it measures, so its extension lines are
    # the kink's own vertices (#3113 r4 review: offset, it read as measured on
    # the slope), clear of the #47 leader to its left and the #21 leader's
    # shelf above.
    "BarHeight": (_sheet_x(TAPER_START_X), 0.168),
    # Right of and below the #21 callout's shelf (the three-line text grows
    # up from here; at (0.272, 0.172) the shelf ran into "R.167", R.167
    # review 3/3), clear of the spring-hole location's extension line below
    # the tip (#3113 r3) and of the isometric label to its right.
    "TipRadius": (0.285, 0.166),
    "BarPinCx": (_sheet_x(BAR_PIN_X / 2.0), 0.126),
    # The taper start's row between the bar-pin and spring-hole rows.
    "TaperStartX": (_sheet_x(TAPER_START_X / 2.0), 0.115),
    "SpringCx": (_sheet_x(LEVER_SPRING_X / 2.0 + 25.0), 0.104),
    # The root corners' 2X R.065 below the bar, right of the hub and
    # above the 5.000 row, its leader up-left to the bottom root (the
    # fillet's first edge, build_ch_channel_lever): the drill leader runs
    # through the top root, so the bottom one carries the radius.
    "RootCornerR": (0.143, 0.1405),
}
TOP_KEEP = {
    # Above the plate: its arrows come in from outside the 3.00 span.
    "LeverThick": (0.264, TOP_CENTER[1] + 0.032),
    # Both above the hub, their lines just right of it (left of the hub there
    # is no room inside the border).  Each text runs right from its own line
    # (r2 render), so the outer (right) line carries the lower text and
    # neither line runs through the other's text.
    "HubLength": (0.075, TOP_CENTER[1] + 0.032),
    # Its value row sits under the hub length's shelf (ch-fab-2 r3: at +0.018
    # that shelf struck the offset value); its one row of words and its shelf still
    # stand ~4 mm above its own arrows over the plate.
    "PlateOffset": (0.095, TOP_CENTER[1] + 0.014),
}
OVERALL_TEXT_XY = (FRONT_CENTER[0], 0.082)
BAR_PIN_CALLOUT_XY = (0.170, 0.188)
SPRING_CALLOUT_XY = (0.240, 0.188)
# Lower left, below the overall length and clear of the title block.
PLATE_OFFSET_NOTE_XY = (0.020, 0.055)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame (the build
# docstring's layout: the fulcrum bore's axis on Z at the origin, the lever
# along +X, the bar height in Y, the plate mid-plane in Z; the plate offset's
# reference line runs from the hub face at -Z). A band is the dimension's own
# native band, else the title block's row for its printed places. The
# declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_ch_channel_lever"
_SPEC = "ch_channel_lever_spec"
_NOTES = "ch_channel_lever_notes"
_FRAME = ((_SPEC, "__frame__"), (_SPEC, "taper_tangent_point"))
_Z = (0.0, 0.0, 1.0)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    fields={
        "material.thickness": (HUB_LENGTH, ((_SPEC, "HUB_LENGTH"),)),
    },
    model_sources=(
        (_SPEC, "__frame__"),
        (_SPEC, "HUB_LENGTH"),
        (_SPEC, "LEVER_THICKNESS"),
        (_SPEC, "TIP_END_X"),
    ),
    precision_sources=(
        (_NOTES, "DRAWING_PRECISION"),
        (_NOTES, "DRAWING_PRECISION_BY_NAME"),
        (_SELF, "HOLE_PRECISION"),
    ),
)
# The hub's two faces, the stack's pitch between them (TOP_KEEP "HubLength",
# +.001/.000); the plate's near face .091 +/-.002 from the hub face at -Z
# (TOP_KEEP "PlateOffset", note 1) and its far face .118 +.002/-.004 from it
# (TOP_KEEP "LeverThick"). The plate is centred in the hub.
requirement(
    "hub_near_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), HUB_LENGTH / 2.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", -HUB_LENGTH / 2.0), (*_FRAME, (_SPEC, "HUB_LENGTH")))},
)
requirement(
    "hub_far_face",
    kind="face",
    faces=(PlanarFace(_Z, HUB_LENGTH / 2.0),),
    requirements=("length",),
    fields={
        "plane": (_plane("z", HUB_LENGTH / 2.0), (*_FRAME, (_SPEC, "HUB_LENGTH"))),
        "length": (
            limits(HUB_LENGTH, _P["HubLength"], HUB_LENGTH_BAND),
            ((_SPEC, "HUB_LENGTH"), (_SPEC, "HUB_LENGTH_BAND"), (_SELF, "TOP_KEEP")),
        ),
        "length_nominal": (HUB_LENGTH, ((_SPEC, "HUB_LENGTH"),)),
        "length_from": ("hub_near_face", ((_SELF, "TOP_KEEP"),)),
        "callout": (TOP_CALLOUTS["HubLength"], ((_SELF, "TOP_CALLOUTS"),)),
    },
    precision={"length": _P["HubLength"]},
)
requirement(
    "plate_near_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), LEVER_THICKNESS / 2.0),),
    requirements=("offset",),
    fields={
        "plane": (
            _plane("z", -LEVER_THICKNESS / 2.0),
            (*_FRAME, (_SPEC, "LEVER_THICKNESS")),
        ),
        "offset": (
            limits(
                PLATE_OFFSET,
                _P["PlateOffset"],
                (PLATE_OFFSET_TOLERANCE, -PLATE_OFFSET_TOLERANCE),
            ),
            (
                (_SPEC, "PLATE_OFFSET"),
                (_SPEC, "PLATE_OFFSET_TOLERANCE"),
                (_SELF, "TOP_KEEP"),
            ),
        ),
        "offset_nominal": (PLATE_OFFSET, ((_SPEC, "PLATE_OFFSET"),)),
        "offset_from": ("hub_near_face", ((_SELF, "TOP_KEEP"),)),
        "callout": (TOP_CALLOUTS["PlateOffset"], ((_SELF, "TOP_CALLOUTS"),)),
        "note": (PLATE_OFFSET_NOTE, ((_SELF, "PLATE_OFFSET_NOTE"),)),
    },
    precision={"offset": _P["PlateOffset"]},
)
requirement(
    "plate_far_face",
    kind="face",
    faces=(PlanarFace(_Z, LEVER_THICKNESS / 2.0),),
    requirements=("thickness",),
    fields={
        "plane": (
            _plane("z", LEVER_THICKNESS / 2.0),
            (*_FRAME, (_SPEC, "LEVER_THICKNESS")),
        ),
        "thickness": (
            limits(LEVER_THICKNESS, _P["LeverThick"], LEVER_THICKNESS_BAND),
            (
                (_SPEC, "LEVER_THICKNESS"),
                (_SPEC, "LEVER_THICKNESS_BAND"),
                (_SELF, "TOP_KEEP"),
            ),
        ),
        "thickness_nominal": (LEVER_THICKNESS, ((_SPEC, "LEVER_THICKNESS"),)),
        "thickness_from": ("plate_near_face", ((_SELF, "TOP_KEEP"),)),
        "callout": (TOP_CALLOUTS["LeverThick"], ((_SELF, "TOP_CALLOUTS"),)),
    },
    precision={"thickness": _P["LeverThick"]},
)
# The hub's turned-looking round, .48 at the title block's .XX (FRONT_KEEP
# "HubDia"), concentric with the fulcrum bore; the plate splits it.
requirement(
    "hub",
    kind="boss",
    faces=(CylinderFace(HUB_DIA),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, 0.0], (*_FRAME,)),
        "axis": (_Z, (*_FRAME,)),
        "dia": (
            limits(HUB_DIA, _P["HubDia"], unit=UNIT),
            ((_SPEC, "HUB_DIA"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "dia_nominal": (HUB_DIA, ((_SPEC, "HUB_DIA"),)),
        # Covered material, for the stock check: no face bounds X or Y.
        "extent_x": ([-HUB_DIA / 2.0, HUB_DIA / 2.0], ((_SPEC, "HUB_DIA"),)),
        "extent_y": ([-HUB_DIA / 2.0, HUB_DIA / 2.0], ((_SPEC, "HUB_DIA"),)),
    },
    precision={"dia": _P["HubDia"]},
)
# The outline beyond the hub: the bar's two straight edges, .37 apart (at the
# taper start, FRONT_KEEP "BarHeight"), the taper start 5.50 from the bore
# (FRONT_KEEP "TaperStartX"), the two taper edges tangent to the full-round
# tip, and the tip R.167 about the #21 hole (FRONT_KEEP "TipRadius"); the two
# roots where the bar's edges meet the hub, 2X R.065 (FRONT_KEEP
# "RootCornerR", the outline cutter's own radius). The overall length over
# the hub and the tip is a reference (OVERALL_TEXT_XY).
_TANGENT_X, _TANGENT_Y = taper_tangent_point()
_TAPER_NX = (_TANGENT_X - TIP_ARC_CX) / TIP_RADIUS
_TAPER_NY = _TANGENT_Y / TIP_RADIUS
_TAPER_OFFSET = _TAPER_NX * _TANGENT_X + _TAPER_NY * _TANGENT_Y
_OUTLINE_SOURCES = ((_SPEC, "taper_tangent_point"), (_SPEC, "TIP_RADIUS"))
requirement(
    "outline",
    kind="profile",
    faces=(
        PlanarFace((0.0, 1.0, 0.0), BAR_TALL / 2.0),
        PlanarFace((0.0, -1.0, 0.0), BAR_TALL / 2.0),
        PlanarFace((_TAPER_NX, _TAPER_NY, 0.0), _TAPER_OFFSET),
        PlanarFace((_TAPER_NX, -_TAPER_NY, 0.0), _TAPER_OFFSET),
        CylinderFace(2.0 * TIP_RADIUS),
    ),
    requirements=("bar_height", "taper_start", "tip_radius", "root_corner_r"),
    fields={
        "bar_height": (
            limits(BAR_TALL, _P["BarHeight"], unit=UNIT),
            ((_SPEC, "BAR_TALL"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "bar_height_nominal": (BAR_TALL, ((_SPEC, "BAR_TALL"),)),
        "taper_start": (
            limits(TAPER_START_X, _P["TaperStartX"], unit=UNIT),
            ((_SPEC, "TAPER_START_X"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "taper_start_nominal": (TAPER_START_X, ((_SPEC, "TAPER_START_X"),)),
        "taper_start_from": ("fulcrum_bore", ((_SELF, "FRONT_KEEP"),)),
        "taper_tangent_at": (
            [_TANGENT_X, _TANGENT_Y, 0.0],
            _OUTLINE_SOURCES,
        ),
        "tip_radius": (
            limits(TIP_RADIUS, _P["TipRadius"], unit=UNIT),
            ((_SPEC, "TIP_RADIUS"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "tip_radius_nominal": (TIP_RADIUS, ((_SPEC, "TIP_RADIUS"),)),
        "tip_at": ([TIP_ARC_CX, 0.0, 0.0], ((_SPEC, "TIP_ARC_CX"),)),
        "tip_callout": (FRONT_CALLOUTS["TipRadius"], ((_SELF, "FRONT_CALLOUTS"),)),
        "root_corner_r": (
            limits(ROOT_CORNER_R, _P["RootCornerR"], unit=UNIT),
            ((_NOTES, "ROOT_CORNER_R"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "root_corner_r_nominal": (ROOT_CORNER_R, ((_NOTES, "ROOT_CORNER_R"),)),
        "root_corner_count": (2, ((_NOTES, "ROOT_CORNER_PREFIX"),)),
        "root_corner_callout": (
            FRONT_CALLOUTS["RootCornerR"], ((_SELF, "FRONT_CALLOUTS"),)
        ),
        "overall_length_ref": (
            TIP_END_X + HUB_DIA / 2.0,
            ((_SPEC, "TIP_END_X"), (_SPEC, "HUB_DIA"), (_SELF, "OVERALL_TEXT_XY")),
        ),
        # Covered material: the bar from the fulcrum axis to the tip's end.
        "extent_x": ([0.0, TIP_END_X], ((_SPEC, "TIP_END_X"),)),
        "extent_y": ([-BAR_TALL / 2.0, BAR_TALL / 2.0], ((_SPEC, "BAR_TALL"),)),
    },
    precision={
        "bar_height": _P["BarHeight"],
        "taper_start": _P["TaperStartX"],
        "tip_radius": _P["TipRadius"],
        "root_corner_r": _P["RootCornerR"],
    },
)
# The F-drilled fulcrum bore (FRONT_KEEP "FulcrumDia", the DRILLED HOLES row)
# and the two drilled holes on the bar's axis, each located from the bore at
# .XXX with its native Hole Wizard callout and the mate under it (HOLE_MATES).
requirement(
    "fulcrum_bore",
    kind="hole",
    faces=(CylinderFace(PIVOT_HOLE_DIA),),
    requirements=("dia", "thru", "process"),
    fields={
        "at": ([0.0, 0.0, 0.0], (*_FRAME,)),
        "axis": (_Z, (*_FRAME,)),
        "dia": (
            limits(PIVOT_HOLE_DIA, _P["FulcrumDia"], PIVOT_HOLE_BAND),
            ((_SPEC, "PIVOT_HOLE_DIA"), (_SPEC, "PIVOT_HOLE_BAND"), (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (PIVOT_HOLE_DIA, ((_SPEC, "PIVOT_HOLE_DIA"),)),
        "drill": (PIVOT_HOLE_SPEC.size, ((_SPEC, "PIVOT_HOLE_SPEC"),)),
        "thru": (True, ((_SELF, "FRONT_CALLOUTS"),)),
        "process": (drill_process(PIVOT_HOLE_SPEC), ((_SELF, "FRONT_CALLOUTS"),)),
        "callout": (FRONT_CALLOUTS["FulcrumDia"], ((_SELF, "FRONT_CALLOUTS"),)),
    },
    precision={"dia": _P["FulcrumDia"]},
)
for _name, _label, _spec, _x, _location, _callout_xy, _sources in (
    (
        "bar_pin_hole",
        "bar-pin hole",
        BAR_PIN_HOLE_SPEC,
        BAR_PIN_X,
        "BarPinCx",
        "BAR_PIN_CALLOUT_XY",
        ((_SPEC, "BAR_PIN_HOLE_SPEC"), (_SPEC, "BAR_PIN_X")),
    ),
    (
        "spring_hole",
        "spring-eye hole",
        SPRING_EYE_HOLE_SPEC,
        LEVER_SPRING_X,
        "SpringCx",
        "SPRING_CALLOUT_XY",
        ((_SPEC, "SPRING_EYE_HOLE_SPEC"), (_SPEC, "LEVER_SPRING_X")),
    ),
):
    _dia = blind_cut_dia_mm(_spec)
    _places = HOLE_PRECISION[_label]["hw-diam"]
    requirement(
        _name,
        kind="hole",
        faces=(CylinderFace(_dia),),
        requirements=("dia", "thru", "location", "process"),
        fields={
            "at": ([_x, 0.0, 0.0], _sources),
            "axis": (_Z, (*_FRAME,)),
            "dia": (
                drilled_limits(_dia, _places, unit=UNIT),
                (*_sources, (_SPEC, "UNIT"), (_SELF, "HOLE_PRECISION")),
            ),
            "nominal_dia": (_dia, _sources),
            "drill": (_spec.size, _sources),
            "thru": (True, ((_SELF, _callout_xy),)),
            "process": (drill_process(_spec), _sources),
            "location": (
                limits(_x, _P[_location], unit=UNIT),
                (*_sources, (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
            ),
            "location_nominal": (_x, _sources),
            "location_from": ("fulcrum_bore", ((_SELF, "FRONT_KEEP"),)),
            "mate": (HOLE_MATES[_label], ((_SELF, "HOLE_MATES"),)),
        },
        precision={"dia": _places, "location": _P[_location]},
    )


def _land_root_corner_leader(adapter: Any, annotations: list[Any]) -> None:
    """Carry RootCornerR's leader onto the root it measures.

    SolidWorks ends a radial leader at the circle point facing its text and
    does not carry it through the centre; the 2X R.065 text stands below the
    bar, off the root's short arc, so the arrow met the circle in air (farm r1
    of #3445). ``ArcExtensionLineOrOppositeSide`` True draws the arc's
    extension out to that point (draw_mg_magnifying_vertical_rod's relief
    roots)."""
    found = [a for a in annotations if dimension_name(adapter, a) == "RootCornerR"]
    if len(found) != 1:
        raise RuntimeError(f"expected one RootCornerR dimension, found {len(found)}")
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported root corner radius is not radial")
    display.ArcExtensionLineOrOppositeSide = True
    if not bool(display.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("RootCornerR refused its arc extension line")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open channel-lever source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
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
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-channel-lever"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Channel Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "channel lever; 1018 steel; third-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The integral Ø.48 x .300 fulcrum hub hides the whole plate section
    # in an end view, so the plate thickness and the hub length read here.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

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
    # The bands import with their named model dimensions, at the part's
    # places; the drawing owns only the callout text beneath them.
    assert_imported_precision(
        adapter,
        front_annotations,
        {
            **DRAWING_PRECISION["LeverOutline"],
            **DRAWING_PRECISION["HubProfile"],
            **DRAWING_PRECISION["FulcrumProfile"],
            **DRAWING_PRECISION["BarPinHole"],
            **DRAWING_PRECISION["SpringHole"],
            **DRAWING_PRECISION["RootCorners"],
        },
    )
    assert_imported_precision(
        adapter,
        top_annotations,
        {
            **DRAWING_PRECISION["LeverBody"],
            **DRAWING_PRECISION["Hub"],
            **DRAWING_PRECISION["PlateOffsetReference"],
        },
    )
    # Native, the Ø.48 line runs rim to rim through the hub centre and
    # crosses the drill leader there (review r3): one arrow on the near rim.
    hub_dia = [a for a in front_annotations if dimension_name(adapter, a) == "HubDia"]
    if len(hub_dia) != 1:
        raise RuntimeError(f"expected one HubDia dimension, found {len(hub_dia)}")
    set_near_side_diameter(hub_dia[0], "hub diameter")
    _land_root_corner_leader(adapter, front_annotations)
    rebuild_drawing(adapter, label="hub diameter and root corner leaders")
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)
    set_dimension_callouts(adapter, top_annotations, TOP_CALLOUTS)

    # Overall length over the hub and the full-round tip, for the stock cut:
    # a reference (the hub, the spring-hole location and the bar's full round
    # set it).  Both ends are arcs in the front view, each selected as its own
    # edge on the part's geometry (the tip is concentric with the #21 hole and
    # just outside its rim, so a sheet pick hit-tests the hole: #3113 first
    # farm run) and re-anchored to its extreme (an arc dimension resolves to
    # the centre by default and would read the 175.05 spring arm).
    front_edges = scan_view_edges(front, label="channel lever front")
    hub_arc = front_edges.circle_at(
        (0.0, 0.0, HUB_LENGTH / 2.0), _HUB_R, axis=(0.0, 0.0, 1.0), label="hub circle"
    ).edge
    tip_arc = front_edges.circle_at(
        (TIP_ARC_CX, 0.0, LEVER_THICKNESS / 2.0),
        TIP_RADIUS,
        axis=(0.0, 0.0, 1.0),
        label="full-round tip arc",
    ).edge
    overall = add_edge_dimension(
        adapter,
        front,
        p0=(0.0, 0.0),
        p1=(0.0, 0.0),
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="horizontal",
        entities=(hub_arc, tip_arc),
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length")
    assert_dimension_measures(
        adapter,
        overall,
        expected_mm=_HUB_R + TIP_END_X,
        label="overall length",
        entities=(hub_arc, tip_arc),
    )
    overall = _sw_type_info.early_bound_or_flag(
        overall, "IDisplayDimension", "GetAnnotation"
    )
    set_reference_dimension(adapter, overall.GetAnnotation(), label="overall length")

    # Hole callouts (bar-pin #47, spring-eye #21) say DRILL ahead of the native
    # size.  Pick a point ON each hole's rim, not its centre: edge selection
    # only catches the circular edge within tolerance of the rim.  The spring
    # eye is picked at 9 o'clock, clear of the concentric full-round tip.
    bar_pin_edge = model_point_in_view(
        adapter, front, (BAR_PIN_X / 1000.0, _BAR_PIN_DIA / 2000.0, 0.0),
        label="bar-pin hole rim",
    )
    spring_edge = model_point_in_view(
        adapter,
        front,
        ((LEVER_SPRING_X - _SPRING_HOLE_DIA / 2.0) / 1000.0, 0.0, 0.0),
        label="spring-eye hole rim",
    )
    bar_pin_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=bar_pin_edge,
        callout_xy=BAR_PIN_CALLOUT_XY,
        label="bar-pin hole",
        process=drill_process(BAR_PIN_HOLE_SPEC) + "\n",
    )
    _name_hole_mate(bar_pin_callout, label="bar-pin hole")
    set_hole_callout_precision(
        bar_pin_callout, HOLE_PRECISION["bar-pin hole"], label="bar-pin hole"
    )
    spring_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=spring_edge,
        callout_xy=SPRING_CALLOUT_XY,
        label="spring-eye hole",
        process=drill_process(SPRING_EYE_HOLE_SPEC) + "\n",
    )
    _name_hole_mate(spring_callout, label="spring-eye hole")
    set_hole_callout_precision(
        spring_callout, HOLE_PRECISION["spring-eye hole"], label="spring-eye hole"
    )
    rebuild_drawing(adapter, label="hole callout mates")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    _add_bar_centerlines(adapter, front)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    if add_note(adapter, PLATE_OFFSET_NOTE, *PLATE_OFFSET_NOTE_XY) is None:
        raise RuntimeError("failed to create the plate-offset note")

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Lever Manufacturing Drawing",
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
