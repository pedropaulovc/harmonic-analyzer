r"""Create the curated machinist drawing for the v2 cone pivot post.

The SLDPRT remains authoritative.  This recipe places the plan, the front
elevation, a true-shape cone-journal view, a native section through the cone
bore plane and a pictorial isometric on one sheet, and imports exactly the
model dimensions ``cone_pivot_post_spec.DRAWING_DIMENSIONS`` marks;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The casting has two axes and they are not parallel: the crank journal runs
along part +Z and the cone journal follows the configured cone-line incline
about the vertical body axis. The part persists a view looking exactly down the
cone axis.  That view retains the boss end face and shows its Ø17.2 OD and
Ø12.281 bore as separate true-shape circles.  A native section in the
horizontal cone-bore plane removes the head from the projection and exposes
the raised boss corners beyond the Ø42 body, together with the boss's axial
length, in a hatched solid-line profile; the elevation keeps the crank
journal, whose own sketch plane is parallel to it.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_pivot_post.py dt-cone-pivot-post
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import UTC, datetime
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)

import _surface_finish
import dt_cone_gear_shaft_spec as cone_shaft
import dt_cone_pivot_post_spec as cone
from dt_cone_post_envelope import BLOCK_DIA
from _feature_requirements import part_metadata, requirement
from _printed_limits import drilled_limits as _drilled_band
from _printed_limits import limits as _band
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_basic_dimensions,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_gdt import PmiDrawingPlacement, project_part_pmi
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_owner_dimensions,
    part_sketches_shown,
)
from _drawing_hole_callout import (
    add_native_hole_callout,
    compose_hole_callout_prefix,
    set_hole_callout_precision,
)
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import set_near_side_diameter
from _part_properties import part_drawing_unit
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
import _seat_forensics
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_cone_gear_shaft_spec import POST_JOURNAL_RIM_BREAK
from dt_cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DIA,
    ATTACHMENT_X,
    BASIC_DIMENSIONS,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CONE_AXIS_VIEW,
    CONE_BOSS_DIA,
    CONE_BOSS_LENGTH,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    CRANK_BOSS_END_Z,
    CRANK_BOSS_START_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_CONTROLS,
    INCLINE_DEG,
    PART_DATUMS,
    SURFACE_FINISHES,
)


SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post"]
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

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SHEET_SCALE = (1.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0

# Third-angle: the plan sits above the front elevation, both at sheet scale.
FRONT_CENTER = (0.098, 0.112)
TOP_CENTER = (0.098, 0.209)
JOURNAL_CENTER = (0.235, 0.160)
ISO_CENTER = (0.360, 0.150)
SECTION_CENTER = (0.295, 0.230)
# Top-centre of the native caption: it stands under View B's letter arrow,
# which runs south off the section's lower boss end (#848), and a caption
# height clear of View B's Ø17.2 callout (at 0.191 they were 7.54 mm apart,
# r3 view-crowding).
SECTION_CAPTION = (0.295, 0.1925)
SECTION_LABEL_SCALE_TEXT = "SCALE"
SECTION_SCALE = (1, 1)

# The landscape template's FINISH rules print at x=215.900/308.328 mm and
# y=33.584/44.485 mm (sheet origin at lower left).  Round inward rather than
# granting a PDF-coordinate rounding tolerance outside the cell.  The old
# x=218 mm limit rejected the correctly contained note starting at 217.8 mm.
# Keep all four boundaries checked so wrapping cannot spill into MATERIAL.
_FINISH_CELL = (0.21595, 0.03360, 0.30830, 0.04445)

# ``place_view`` centres a view on its projected bounding box, so the model
# origin is offset from the view centre by half that box.  The elevation's box
# runs y=0..BLOCK_HEIGHT; the plan's runs the crank boss's full z extent.
_TOP_Z_CENTER = (CRANK_BOSS_START_Z + CRANK_BOSS_END_Z) / 2.0


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


def _front_x(model_x: float) -> float:
    return FRONT_CENTER[0] + model_x * _S


# The manufacturing notes hang from their top-left anchor and grow down.
NOTES_ANCHOR = (0.014, 0.0555)
# Datum B tags the foot seat below the elevation, and its frame hangs 7.0 mm
# down from the tag point (measured on leaf w3-1026: point at 60.0 mm, frame
# 53.0..60.0).  At model y -9 the frame sat on the notes' first line; the tag
# point now sits a frame height plus clearance above the notes' top, still
# below the foot (model y 0) so the leader reaches the seat.
_DATUM_TAG_FRAME_HEIGHT = 0.007
_DATUM_NOTES_CLEARANCE = 0.0015
DATUM_B_TAG_XY = (
    _front_x(-16.0),
    NOTES_ANCHOR[1] + _DATUM_TAG_FRAME_HEIGHT + _DATUM_NOTES_CLEARANCE,
)
if not DATUM_B_TAG_XY[1] < _front_y(0.0):
    raise AssertionError("datum B's tag no longer sits below the foot seat it tags")

# View C: datum A and the bore's Ra stand OFF the post's face, each on a
# leader (r13 machinist review, rule 14: inside the body outline they read
# as features of the face).  The bore's Ø12.281 leaves the lower-right rim
# (about -21 degrees) for its text right of the view, so both stand right
# of the view below that text, each leader landing further round the rim
# than the one above it, so none crosses another:
# - the Ra lands at -42 degrees, its symbol under the size's text;
# - datum A lands at -62 degrees, its frame under the Ra, right of VIEW C's
#   title.  A tag on a circle lands on the rim facing its leader's junction
#   (the position), whatever rim point is picked: r16's pick at -70 printed
#   at -46, facing its junction at (0.275, 0.112), on the Ra's landing (r16
#   machinist review, non-gating).  So the junction stands on the -62
#   bearing, below the body.  The rim is still picked by SHEET POINT on that
#   bearing: tagged by the edge object, the tag kept its default drop inside
#   the body whatever the request (r14 sheet; solidworks-drawing-layout-
#   tuning.md "a datum tag that will not leave its attachment").  The frame
#   prints right of the junction, past a 6.4 mm shoulder (r16 sheet).
DATUM_A_TAG_XY = (0.266, 0.098)
DATUM_A_LANDING_DEG = -62.0
JOURNAL_BORE_FINISH_XY = (0.272, 0.127)
JOURNAL_BORE_FINISH_DEG = -42.0

FOOT_SEAT = requirement(
    "foot_seat", kind="face", faces=(cone.SURFACE_FINISHES[0].face,),
    requirements=("finish_ra",), fields={
        "normal": ([0.0, -1.0, 0.0], ("SURFACE_FINISHES",)),
        "finish_ra": (_surface_finish.SEAT_UM, ("SURFACE_FINISHES",)),
        "datum": ("B", ("PART_DATUMS",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
    }, precision={"finish_ra": 1},
)
part_metadata(datums={
    "B": ({"feature": "foot_seat", "surface": "foot seat plane"}, ("PART_DATUMS",)),
})


def _top_x(model_x: float) -> float:
    return TOP_CENTER[0] + model_x * _S


def _top_y(model_z: float) -> float:
    # The *Top orientation looks down -Y: model +Z runs DOWN the sheet.
    return TOP_CENTER[1] + (_TOP_Z_CENTER - model_z) * _S

# The A-A cutting plane is horizontal at the cone bore's model-Y station.  It
# therefore contains the inclined cone axis, while removing the head that
# hides the boss in the ordinary Top projection.  Its section shows the angled
# 42 x 17.2 boss strip extending past the Ø42 body circle at all four corners.
_CONE_SECTION_HALF_SPAN_MM = 25.0
CONE_SECTION_LINE = (
    (
        _front_x(-_CONE_SECTION_HALF_SPAN_MM),
        _front_y(BORE_HEIGHT),
    ),
    (
        _front_x(_CONE_SECTION_HALF_SPAN_MM),
        _front_y(BORE_HEIGHT),
    ),
)


def _cone_source_frames() -> dict[str, tuple[dict[str, Any], tuple[str, ...]]]:
    """Rigid copies of model on authored axes, never setups or fixture choices."""
    normal = cone.SURFACE_FINISHES[3].face.normal
    axis = (-normal[0], -normal[2])
    note = "geometry-only source frame on an authored spec axis; not a setup"
    return {
        "body_axis": (
            {"origin": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 0.0, -1.0], "z": [0.0, 1.0, 0.0], "note": note},
            ("__frame__", "BLOCK_HEIGHT", "HEAD_BASE_Y", "HEAD_HEIGHT"),
        ),
        "crank_axis": (
            {"origin": [0.0, cone.CRANK_BORE_HEIGHT, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0], "note": note},
            ("CRANK_BORE_HEIGHT", "CRANK_BOSS_START_Z", "CRANK_BOSS_LENGTH"),
        ),
        "cone_axis": (
            {"origin": [0.0, cone.BORE_HEIGHT, 0.0], "x": [axis[1], 0.0, -axis[0]], "y": [0.0, 1.0, 0.0], "z": [axis[0], 0.0, axis[1]], "note": note},
            ("BORE_HEIGHT", "INCLINE_DEG", "SURFACE_FINISHES"),
        ),
    }


_P = cone.DRAWING_PRECISION_BY_NAME
_NORMAL = cone.SURFACE_FINISHES[3].face.normal
_HEAD_SOURCES = ("HEAD_BASE_Y", "BLOCK_HEIGHT", "HEAD_HEIGHT")
_CRANK_END_SOURCES = ("CRANK_BOSS_START_Z", "CRANK_BOSS_NORTH_FACE", "HEAD_DIA", "CRANK_BOSS_END_Z", "CRANK_BOSS_LENGTH", "CRANK_BOSS_LENGTH_IN")
part_metadata(
    fields={"volume_mm3": (cone.HARVESTED_VOLUME_MM3, ("HARVESTED_VOLUME_MM3",))},
    frames=_cone_source_frames(), model_sources=("BLOCK_HEIGHT",),
    precision_sources=("DRAWING_PRECISION_BY_NAME", "GEOMETRIC_CONTROLS", ("_surface_finish", "ra")),
)


def _size_requirement(
    kind: str, dimensions: dict[str, tuple[str, str]],
    extras: dict[str, tuple[Any, tuple[str, ...]]] | None = None,
) -> dict[str, Any]:
    values = {}
    precision = {}
    for key, (constant, dimension) in dimensions.items():
        model = getattr(cone, constant)
        values[key] = (_band(model, _P[dimension]), (constant,))
        values[f"{key}_nominal"] = (model, (constant,))
        precision[key] = _P[dimension]
    values.update(extras or {})
    return {"kind": kind, "requirements": tuple(dimensions), "fields": values, "precision": precision}


FRONT_KEEP = {
    "MainBodyHt": (0.040, FRONT_CENTER[1]),
    "MainBodyDia": (0.150, 0.080),
    # A REFERENCE since U31: the crank bore is located from the cone bore
    # (View B), so its height above the foot only follows that chain.
    "CrankAxisY": (0.060, _front_y(CRANK_BORE_HEIGHT / 2.0)),
    # Out past the angularity frame, text level with its top: at x=0.150 its
    # extension lines fenced the frame off the crank bore (leader-crosses-line,
    # af13), and at y=0.1475 its text sat 0.44 mm under View B's labelled
    # 38.10 (r3 view-crowding).
    "HeadHt": (0.166, 0.1440),
    # On the boss's end circle, near-side leader (r5), as in r8's SHIP: its
    # horizontal text centres on the given x; from x=0.132 the head's right
    # edge ran through CRANK BOSS's C (r6 sheet).  Not the plan: see TOP_KEEP.
    "CrankBossDia": (0.1355, 0.120),
    # Held one text height (13.6 mm) left of View C's labelled 38.10: with
    # "THRU, RUNS ON ..." below the size the box ran x 117.7..180.7 mm, 1.42 mm
    # from the 38.10 box at x 173.1 (r4 view-crowding).  THRU rides the size line
    # (DIMENSION_SUFFIXES), so the widest line is the 49 mm mate; centred at
    # x=0.1344 it ends 14.1 mm short of the 38.10 (at 0.1356, 12.94 mm: r6
    # view-crowding), the 13° arrow's tip ~1 mm off its size line's left end
    # (r5 layout audit, advisory), and at y=0.169 its near-side leader rises
    # from the bore's upper-right rim under the 13° arc.  The head's Ø is not
    # given here: its extension lines run the head's full height and the
    # crank-bore Ra's leader crossed the left one (r9 leader-crosses-leader).
    # The inch ream's four-place band widened the box to x 109.3..160.3 mm,
    # 12.66 mm from View C's 38.10 (#290 batch 0 view-crowding): 1.4 mm
    # left, and 1.5 mm down so the 13° extension line, which ends at y 171.6,
    # stops above the text's left end.
    "CrankBoreDia": (0.1330, 0.1675),
}

# The plan's angled ray is the cone bore's axis; its basic 13° runs to it
# from the crank axis.  A pointer note names it, the text right of the head
# circle above the 13° box and below the counterbore callout's leader, its
# tip on the ray inside the head circle, below the right counterbore's
# centre mark (r13 machinist review: "an unlabelled thin dash-dot ray").
CONE_AXIS_LABEL = "CONE BORE AXIS"
CONE_AXIS_LABEL_TIP_RADIUS_MM = 16.0
CONE_AXIS_LABEL_XY = (0.122, 0.2095)

BODY = requirement(
    "body", faces=(CylinderFace(BLOCK_DIA),),
    kind="boss", requirements=("dia", "height"), fields={
        "dia": (_band(BLOCK_DIA, _P["MainBodyDia"]), (("dt_cone_post_envelope", "BLOCK_DIA"),)),
        "dia_nominal": (BLOCK_DIA, (("dt_cone_post_envelope", "BLOCK_DIA"),)),
        "height": (_band(cone.BLOCK_HEIGHT, _P["MainBodyHt"]), ("BLOCK_HEIGHT",)),
        "height_nominal": (cone.BLOCK_HEIGHT, ("BLOCK_HEIGHT",)),
        "frame": ("body_axis", (*_HEAD_SOURCES, ("draw_dt_cone_pivot_post", "_cone_source_frames"), ("draw_dt_cone_pivot_post", "build"))),
        "z_mm": ([0.0, round(cone.HEAD_BASE_Y, 12)], _HEAD_SOURCES),
    }, precision={"dia": _P["MainBodyDia"], "height": _P["MainBodyHt"]},
)
HEAD = requirement(
    "head", faces=(CylinderFace(cone.HEAD_DIA), PlanarFace((0, 1, 0), cone.BLOCK_HEIGHT)),
    **_size_requirement("boss", {"dia": ("HEAD_DIA", "HeadDia"), "height": ("HEAD_HEIGHT", "HeadHt")}, {
        "frame": ("body_axis", (*_HEAD_SOURCES, ("draw_dt_cone_pivot_post", "_cone_source_frames"), ("draw_dt_cone_pivot_post", "build"))),
        "z_mm": ([round(cone.HEAD_BASE_Y, 12), round(cone.BLOCK_HEIGHT, 12)], _HEAD_SOURCES),
    }),
)
CRANK_BOSS = requirement(
    "crank_boss", faces=(CylinderFace(cone.CRANK_BOSS_DIA),),
    **_size_requirement("boss", {"dia": ("CRANK_BOSS_DIA", "CrankBossDia")}, {
        "frame": ("crank_axis", ("CRANK_BORE_HEIGHT", ("draw_dt_cone_pivot_post", "_cone_source_frames"), ("draw_dt_cone_pivot_post", "build"))),
        "z_mm": ([round(cone.CRANK_BOSS_START_Z, 12), round(cone.CRANK_BOSS_END_Z, 12)], _CRANK_END_SOURCES),
    }),
)
CRANK_BORE = requirement(
    "crank_bore", kind="hole", faces=(cone.SURFACE_FINISHES[1].face,),
    requirements=("dia", "thru", "finish_ra", "separation", "angularity_dia", "angularity_datums"), fields={
        "at": ([0.0, cone.CRANK_BORE_HEIGHT, 0.0], ("CRANK_BORE_HEIGHT",)),
        "axis": ([0.0, 0.0, 1.0], ("INCLINE_DEG",)),
        "dia": (_band(cone.CRANK_BORE_DIA, _P["CrankBoreDia"], cone.RUNNING_BORE_BAND), ("CRANK_BORE_DIA", "RUNNING_BORE_BAND")),
        "nominal_dia": (cone.CRANK_BORE_DIA, ("CRANK_BORE_DIA",)), "thru": (True, (("draw_dt_cone_pivot_post", "DIMENSION_SUFFIXES"),)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "separation": (_band(cone.CRANK_ABOVE_CONE, _P["CrankAboveCone"], cone.CRANK_ABOVE_CONE_BAND), ("CRANK_ABOVE_CONE", "CRANK_ABOVE_CONE_BAND")),
        "height_from": ("journal_bore", (("draw_dt_cone_pivot_post", "build"),)),
        "height_nominal": (cone.CRANK_BORE_HEIGHT, ("CRANK_BORE_HEIGHT",)),
        "angularity_dia": (cone.CRANK_BORE_ANGULARITY_MM, ("CRANK_BORE_ANGULARITY_MM", "GEOMETRIC_CONTROLS")),
        "angularity_datums": (list(cone.GEOMETRIC_CONTROLS[0].datums), ("GEOMETRIC_CONTROLS",)),
        "dimension_type": ("basic", ("BASIC_DIMENSIONS",)),
        "land_angle_nominal_deg": (cone.INCLINE_DEG, ("INCLINE_DEG", "BASIC_DIMENSIONS")),
        "angle_tol_deg": (cone.CRANK_BORE_ANGLE_LIMIT_DEG, ("CRANK_BORE_ANGLE_LIMIT_DEG",)),
    }, precision={
        "dia": _P["CrankBoreDia"], "finish_ra": 1, "separation": _P["CrankAboveCone"],
        "angularity_dia": len(cone.GEOMETRIC_CONTROLS[0].tolerance.partition(".")[2]),
        "land_angle_nominal_deg": _P["InclineAngle"],
    },
)
# The plan's hidden-owner import shows JournalPlanReference's rays for the
# plan angle and CrankBossStationReference's ray for the crank boss's
# north-face station, the face the crank boss length is taken from.
TOP_KEEP = {
    # The crank boss's Ø is not given here: its profile sketch stands on the
    # boss's north face, so the plan's extension lines ran from that face
    # through the head circle to a size line below the head, reading as boss
    # edges seen through the head (r13 machinist review).  It stands on its
    # end circle in the elevation (FRONT_KEEP).
    # The length stands outboard of the station so the station's stacked
    # label clears its dimension line: with the v36 boss face 2.5 further
    # north, a one-line label spanning both lines was crossed by the length.
    "CrankBossLen": (0.040, TOP_CENTER[1]),
    # The station stands between the crank-boss length and the circle, its
    # value on its own dimension line.  On the right its upper witness line
    # ran level with the counterbore callout's shelf and that callout's
    # leader crossed its dimension line, so its text had to be offset to a
    # distant shelf, where a blind reader took it for a note.
    "CrankBossStartZ": (0.062, 0.2338),
    "MountEastX": (0.075, 0.2525),
    # Outboard of its extension line, mirroring MountEastX: centred between
    # the lines at x=0.110 that line ran up through the text (r5 review).
    "MountWestX": (0.121, 0.2525),
    # The basic angle's below-text is cleared when it is boxed BASIC
    # (set_basic_dimension), so the ray it runs to is named by a leader note
    # instead (CONE_AXIS_LABEL; r13 machinist review: unlabelled ray).
    "InclineAngle": (0.142, _top_y(28.0)),
}

CRANK_BOSS_FACES = requirement(
    "crank_boss_faces", faces=(
        PlanarFace((0, 0, -1), cone.CRANK_BOSS_NORTH_FACE),
        PlanarFace((0, 0, 1), cone.CRANK_BOSS_END_Z),
    ),
    **_size_requirement("face", {"length": ("CRANK_BOSS_LENGTH", "CrankBossLen"), "station": ("CRANK_BOSS_NORTH_FACE", "CrankBossStartZ")}),
)
for _side, _x, _dim in (("west", -cone.ATTACHMENT_X, "MountWestX"), ("east", cone.ATTACHMENT_X, "MountEastX")):
    _name = f"mount_{_side}"
    requirement(
        _name, kind="hole", faces=(CylinderFace(cone.ATTACHMENT_THRU_DIA, contains_x_mm=_x),),
        requirements=("dia", "thru", "station"), fields={
            "at": ([_x, cone.BLOCK_HEIGHT, 0.0], ("ATTACHMENT_X", "BLOCK_HEIGHT")), "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "dia": (_drilled_band(cone.ATTACHMENT_THRU_DIA, _P[_dim]), ("ATTACHMENT_THRU_DIA", ("_drawing_hole_callout", "add_native_hole_callout"))),
            "nominal_dia": (cone.ATTACHMENT_THRU_DIA, ("ATTACHMENT_THRU_DIA",)), "thru": (True, (("draw_dt_cone_pivot_post", "build"),)),
            "station": (_band(_x, _P[_dim]), ("ATTACHMENT_X",)), "station_nominal": (_x, ("ATTACHMENT_X",)),
        }, precision={"dia": _P[_dim], "station": _P[_dim]},
    )
    requirement(
        f"{_name}_counterbore", kind="counterbore", faces=(
            CylinderFace(cone.ATTACHMENT_CBORE_DIA, contains_x_mm=_x),
            PlanarFace((0, 1, 0), cone.BLOCK_HEIGHT - cone.ATTACHMENT_CBORE_DEPTH, contains_x_mm=_x),
        ),
        requirements=("dia", "depth"), fields={
            "parent": (_name, (("draw_dt_cone_pivot_post", "build"),)),
            "dia": (_band(cone.ATTACHMENT_CBORE_DIA, _P[_dim]), ("ATTACHMENT_CBORE_DIA",)), "nominal_dia": (cone.ATTACHMENT_CBORE_DIA, ("ATTACHMENT_CBORE_DIA",)),
            "depth": (_band(cone.ATTACHMENT_CBORE_DEPTH, _P[_dim]), ("ATTACHMENT_CBORE_DEPTH",)), "depth_ref": (cone.ATTACHMENT_CBORE_DEPTH, ("ATTACHMENT_CBORE_DEPTH",)),
        }, precision={"dia": _P[_dim], "depth": _P[_dim]},
    )
# The collar thrust face's station stands above the section's upper (north
# face) extension line, its four rows clear of the plan's callouts on the
# left and the north face's finish symbol on the right: between the
# extension lines (y=0.230, 0.234) one line or the other struck its text
# (r3 sheet, r5 review).
SECTION_KEEP = {
    "ConeBossLen": (0.355, 0.235),
    "ConeBossNorthZ": (0.2325, 0.2544),
}
# The crank bore is located from the cone bore (U31), so its spacing chains
# off the cone-axis height on the same dimension line, in the one view that
# shows both bores.  Its toleranced text stands off the line like 33.37's,
# between the crank-bore size callout and the section-axes label.
JOURNAL_KEEP = {
    "JournalAxisY": (0.208, 0.156),
    "CrankAboveCone": (0.208, 0.170),
    # One row (DIMENSION_SUFFIXES), 3.5 mm tall, centred 1 mm over this y.
    # The bore's five-line block below is centred on ITS y, so its band tops
    # out at 167.1 mm (r17 layout audit); a two-row box here (9.1 mm) had no
    # slot between that and SECTION A-A's caption at 184.5 mm, because the
    # crowding check wants the smaller box's full height of air between
    # views (r17: 0.70 mm overlap at 0.172; r18: 5.47 mm under the caption's
    # 8.10 at 0.1755).  One row needs 3.5 mm: it prints 170.2..173.7, 3.1 mm
    # over the band and 10.8 mm under the caption.
    "ConeBossDia": (0.292, 0.173),
    # View C sees the head side-on above the crank boss: its Ø stands over
    # the head, text out left of the head and below the A-A thrust-face
    # station's lower extension line (y ~217-222 over the head).
    "HeadDia": (0.200, 0.2135),
    # 0.5 mm under y=0.153, where its band stood 1.52 mm under the boss
    # OD's text, short of the audit's 1.78 mm of air (r5 layout audit).
    "JournalBoreDia": (0.292, 0.1525),
}

CONE_BOSS = requirement(
    "cone_boss", faces=(CylinderFace(cone.CONE_BOSS_DIA),),
    **_size_requirement("boss", {"dia": ("CONE_BOSS_DIA", "ConeBossDia")}, {
        "frame": ("cone_axis", ("BORE_HEIGHT", "INCLINE_DEG", "SURFACE_FINISHES", ("draw_dt_cone_pivot_post", "_cone_source_frames"), ("draw_dt_cone_pivot_post", "build"))),
        "z_mm": ([round(-cone.CONE_BOSS_LENGTH / 2, 12), round(cone.CONE_BOSS_LENGTH / 2, 12)], ("CONE_BOSS_LENGTH", ("dt_cone_post_envelope", "BLOCK_DIA"))),
    }),
)
JOURNAL_BORE = requirement(
    "journal_bore", kind="hole", faces=(cone.SURFACE_FINISHES[2].face,),
    requirements=("dia", "thru", "finish_ra", "height", "unknown"), fields={
        "at": ([0.0, cone.BORE_HEIGHT, 0.0], ("BORE_HEIGHT",)),
        "axis": ([-_NORMAL[0], 0.0, -_NORMAL[2]], ("INCLINE_DEG",)),
        "dia": (_band(cone.BORE_DIA, _P["JournalBoreDia"], cone.JOURNAL_BORE_BAND), ("BORE_DIA", "JOURNAL_BORE_BAND")),
        "nominal_dia": (cone.BORE_DIA, ("BORE_DIA",)), "thru": (True, (("draw_dt_cone_pivot_post", "DIMENSION_CALLOUTS"),)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
        "height": (_band(cone.BORE_HEIGHT, _P["JournalAxisY"], (cone.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM, -cone.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM)), ("BORE_HEIGHT", "JOURNAL_AXIS_HEIGHT_TOLERANCE_MM")),
        "height_from": ("foot_seat", ("BORE_HEIGHT",)), "datum": ("A", ("PART_DATUMS",)),
        # No rim-break field exists: keep the sourced note and unknown inspection.
        "note": (cone_shaft.POST_JOURNAL_RIM_BREAK, (("dt_cone_gear_shaft_spec", "POST_JOURNAL_RIM_BREAK"), ("dt_cone_gear_shaft_spec", "THRUST_EDGE_BREAK_MAX"))),
    }, precision={"dia": _P["JournalBoreDia"], "finish_ra": 1, "height": _P["JournalAxisY"]},
)
part_metadata(datums={
    "A": ({"feature": "journal_bore", "surface": "cone journal bore cylinder"}, ("PART_DATUMS",)),
})
# Both chained heights share the dimension line at JOURNAL_KEEP's x, and the
# crank spacing's extension line runs up it past the 33.37's text, so that text
# must end left of the line.  Its x here is only a start:
# ``_clear_journal_axis_text`` moves it by the box the layout check itself
# reads once the sheet is complete.  That box is an estimate (glyph count x
# height x an advance calibrated from the sheet's notes), so it outruns the
# printed ink and moves when any note on the sheet changes: leaf w3-1026 read
# it 34.0 mm wide, the 8f4aea333 control 36.0 mm over 27.1 mm of printed ink.
# A width fixed from one reading crossed the line on the next.
_TEXT_LINE_CLEARANCE = 0.002
JOURNAL_TEXT_OFFSETS = {
    "JournalAxisY": (0.1856, 0.157),
    "CrankAboveCone": (0.193, 0.183),
}
# The non-preferred bore limits tell the shop what to inspect without imposing
# a particular cutting method.  Ø21.9 is the crank boss OD, given across the
# boss where the plan sees it side-on, and Ø42.8 the head's, given across the
# head where View C sees it side-on (rule 11: turned diameters on the side
# view, not the end view; r8 machinist review) -- and the plan's
# station locates the boss's north face from the post axis; that face stands
# on the head's tangent plane, so no depth is taken against the curved head.
# The station is labelled: Main's rim-8339 ruling found the spot-face era's
# bare 18.88 station was not read as one.
# The cone bore's rims bound the thrust ring the shaft collar bears on, with
# the collar's OD edge (cone_gear_shaft_spec: ring - 2 x break >= 1.5), so the
# bore's callout prints the same break as the collar instead of the title
# block's 0.25, and says why under it (r16 machinist review, rules 4 and 7:
# a break tighter than the title block's needs its reason at the callout).
# That line grows the block both ways from its centre, so the boss OD's
# callout above it went to one row (DIMENSION_SUFFIXES, JOURNAL_KEEP).
# Each running bore names the shaft that runs in it, the crank-above-cone
# spacing the mesh it sets, the cone-axis height the tip block whose adjuster
# cup the shaft's tip must enter, and the cone boss's north-face station the
# part whose collar thrusts on that face (r1 and r5 machinist reviews, rule 4:
# its ±0.25 is the stacks' half band, cone_pivot_post_spec).
DIMENSION_CALLOUTS = {
    "CrankBossDia": "CRANK BOSS",
    "CrankBossLen": "CRANK BOSS\nLENGTH",
    "CrankBossStartZ": "CRANK BOSS\nFACE",
    "CrankBoreDia": "RUNS ON MHA-DT-11",
    "JournalBoreDia": f"CONE BORE THRU\nRUNS ON MHA-DT-04\n{POST_JOURNAL_RIM_BREAK}\nFOR COLLAR SEAT",
    "ConeBossLen": "CONE BOSS FACE-TO-FACE",
    "ConeBossNorthZ": "THRUST FACE FOR\nMHA-DT-04 COLLAR,\nFROM POST AXIS",
    "CrankAboveCone": "16T:64T\nMESH",
    "JournalAxisY": "AXIS MATCHES\nMHA-DT-21",
}
# Text after the size and its band, on the same line: one row keeps the
# head's Ø in the narrow band between View C's head and the A-A station,
# and the cone boss's Ø between the bore's block and SECTION A-A's caption
# (named as Section A-A's CONE BOSS FACE-TO-FACE names the same boss).
DIMENSION_SUFFIXES = {
    "CrankBoreDia": " THRU",
    "HeadDia": " HEAD",
    "ConeBossDia": " CONE BOSS OD",
}
# Diameters given on their circles land one arrow on the near rim, the line
# kept off the centre: two leaders through one centre crossed there (the
# crank bore's and the crank boss's in r5, the cone bore's and its boss's in
# r8; machinist reviews).
NEAR_SIDE_DIAMETERS = ("CrankBossDia", "CrankBoreDia", "ConeBossDia", "JournalBoreDia")
_DIMENSION_TEXT_SUFFIX = 2  # swDimensionTextParts_e.swDimensionTextSuffix


# COM edge-scan match slack; a selection aid, not product definition.
_EDGE_MATCH_TOLERANCE_MM = 0.01


def _circular_edge(
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
    center_x_mm: float | None = None,
) -> Any:
    """Return the model circular edge matching a radius and a model-Y height.

    ``center_x_mm`` breaks the tie between the two mounting counterbores,
    which differ only in X; without it the scan returns whichever SolidWorks
    enumerated first, and a leader routed for one hole then crosses the plan
    to reach the other.
    """
    candidates: list[tuple[float, Any]] = []
    for raw in visible_view_entities(view, 1, label="pivot-post circular edges"):
        edge = _early_bound(raw, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        error = abs(params[6] * 1000.0 - radius_mm) + abs(
            params[1] * 1000.0 - center_y_mm
        )
        if center_x_mm is not None:
            error += abs(params[0] * 1000.0 - center_x_mm)
        candidates.append((error, edge))
    if not candidates:
        raise RuntimeError("view has no circular model edges")
    error, edge = min(candidates, key=lambda item: item[0])
    if error > _EDGE_MATCH_TOLERANCE_MM:
        where = f"at height {center_y_mm:.4f} mm"
        if center_x_mm is not None:
            where += f", x {center_x_mm:.4f} mm"
        raise RuntimeError(
            f"no circular edge matches radius {radius_mm:.4f} mm {where}"
        )
    return edge


@_telemetry.traced("drawing.bore_rim_scan")
def _bore_rim_edge(view: Any, *, diameter_mm: float) -> Any:
    """Return a rim adjacent to the unique cylindrical bore of this diameter."""
    expected_radius_m = diameter_mm / 2000.0
    for raw in visible_view_entities(view, 1, label="pivot-post bore rims"):
        edge = _early_bound(raw, "IEdge")
        for face in edge.GetTwoAdjacentFaces2() or []:
            if face is None:
                continue
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            if abs(float(surface.CylinderParams[6]) - expected_radius_m) > 1e-6:
                continue
            return edge
    raise RuntimeError(f"view has no rim adjacent to a {diameter_mm:g} mm bore")


# The collar's Ra symbol sits just above and left of its leader's landing
# point: clear of the face-to-face dimension on the section's right, and
# above the thrust-face station's extension line, which runs left along the
# north face (sheet metres).
_NORTH_BOSS_FINISH_OFFSET = (-0.006, 0.008)


CONE_BOSS_NORTH_FACE = requirement(
    "cone_boss_north_face", kind="face", faces=(cone.SURFACE_FINISHES[3].face,),
    requirements=("length", "station", "finish_ra"), fields={
        "length": (_band(cone.CONE_BOSS_LENGTH, _P["ConeBossLen"]), ("CONE_BOSS_LENGTH",)),
        "length_nominal": (cone.CONE_BOSS_LENGTH, ("CONE_BOSS_LENGTH",)),
        # The collar's thrust face from the post axis, at the stacks' half
        # band (DIMENSION_CALLOUTS names the collar).
        "station": (_band(cone.CONE_BOSS_NORTH_STATION, _P["ConeBossNorthZ"], (cone.CONE_BOSS_NORTH_STATION_TOLERANCE_MM, -cone.CONE_BOSS_NORTH_STATION_TOLERANCE_MM)), ("CONE_BOSS_NORTH_STATION", "CONE_BOSS_NORTH_STATION_TOLERANCE_MM")),
        "station_nominal": (cone.CONE_BOSS_NORTH_STATION, ("CONE_BOSS_NORTH_STATION",)),
        "normal": (list(_NORMAL), ("SURFACE_FINISHES",)),
        "finish_ra": (_surface_finish.MACHINED_UM, ("SURFACE_FINISHES",)),
    }, precision={"length": _P["ConeBossLen"], "station": _P["ConeBossNorthZ"]},
)
CONE_BOSS_SOUTH_FACE = requirement(
    "cone_boss_south_face", kind="face",
    faces=(PlanarFace(tuple(-v for v in _NORMAL), cone.CONE_BOSS_LENGTH / 2),),
    requirements=(), fields={"normal": (tuple(-v for v in _NORMAL), ("SURFACE_FINISHES",))},
)


def _north_boss_end_edge(section: Any) -> Any:
    """Return the sheet-left cut edge of the north cone-boss end face.

    The A-A cut runs through the journal axis, so the north end face shows as
    two short edges split by the bore.  Both vertices of each must lie on the
    controlled plane at the bore height; finding exactly two proves the scan
    found the boss end and not some other plane.
    """
    normal = surface_finish_by_key(SURFACE_FINISHES, "cone_boss_north_face").face.normal
    offset = CONE_BOSS_LENGTH / 2.0
    candidates: list[tuple[float, Any]] = []
    for raw in visible_view_entities(section, 1, label="north cone boss end edges"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        points = [
            tuple(float(v) * 1000.0 for v in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in (start, end)
        ]
        if all(
            abs(sum(p[i] * normal[i] for i in range(3)) - offset)
            <= _EDGE_MATCH_TOLERANCE_MM
            and abs(p[1] - BORE_HEIGHT) <= _EDGE_MATCH_TOLERANCE_MM
            for p in points
        ):
            candidates.append((0.5 * (points[0][0] + points[1][0]), edge))
    if len(candidates) != 2:
        raise RuntimeError(
            f"section shows {len(candidates)} north cone boss end edges, expected two"
        )
    return min(candidates, key=lambda item: item[0])[1]


def _north_boss_finish_anchor(
    adapter: Any, section: Any, edge: Any
) -> tuple[float, float]:
    """Sheet point mid-way along the edge, proven to be the section's top left."""
    points = [
        tuple(float(v) for v in _early_bound(vertex, "IVertex").GetPoint())
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
    ]
    middle = tuple(0.5 * (points[0][i] + points[1][i]) for i in range(3))
    anchor = model_point_in_view(adapter, section, middle, label="north boss end midpoint")
    centre = model_point_in_view(
        adapter, section, (0.0, BORE_HEIGHT / 1000.0, 0.0), label="cone section centre"
    )
    if not (anchor[0] < centre[0] and anchor[1] > centre[1]):
        raise RuntimeError(
            f"north cone boss end {anchor!r} is not up-left of the section "
            f"centre {centre!r}; the symbol offset assumes it is"
        )
    return (anchor[0], anchor[1])


# #848: View B looks down the cone axis at the SOUTH boss end face, so it is
# named by a letter arrow (draw_dt_cone_tip_block's recipe) in Section A-A,
# the one view that shows that axis true length: the leader runs north along
# the axis onto the face's sheet-left cut edge, mid-wall, and the letter
# stands square to the face, centred on the tail (sheet metres).  The sheet
# letters it C: datum B is the foot, and a view lettered B read as that
# datum (r5 machinist review); "View B" stays this script's internal name.
JOURNAL_VIEW_LETTER = "C"
VIEW_LETTER_HEIGHT = 0.005
_VIEW_B_ARROW_LENGTH = 0.008
_VIEW_LETTER_HALF_WIDTH = 0.0018


def _view_b_arrow(
    adapter: Any, section: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """(note upper-left, leader tip) of View B's arrow on Section A-A."""
    normal = surface_finish_by_key(SURFACE_FINISHES, "cone_boss_north_face").face.normal
    south = (-normal[0], 0.0, -normal[2])
    across = (south[2], 0.0, -south[0])
    half = CONE_BOSS_LENGTH / 2000.0
    wall = (BORE_DIA + CONE_BOSS_DIA) / 4000.0
    axis_y = BORE_HEIGHT / 1000.0

    def sheet(point: tuple[float, float, float], label: str) -> tuple[float, float]:
        x, y = model_point_in_view(adapter, section, point, label=label)[:2]
        return (x, y)

    tip = min(
        (
            sheet(
                (
                    half * south[0] + side * wall * across[0],
                    axis_y,
                    half * south[2] + side * wall * across[2],
                ),
                f"view B arrow tip candidate {side:+.0f}",
            )
            for side in (-1.0, 1.0)
        ),
        key=lambda point: point[0],
    )
    centre = sheet((0.0, axis_y, 0.0), "cone section centre")
    face = sheet((half * south[0], axis_y, half * south[2]), "south boss end centre")
    run = (face[0] - centre[0], face[1] - centre[1])
    length = math.hypot(*run)
    if not run[1] < 0.0:
        raise RuntimeError(
            f"south cone boss end {face!r} is not below the section centre {centre!r}"
        )
    tail = (
        tip[0] + run[0] / length * _VIEW_B_ARROW_LENGTH,
        tip[1] + run[1] / length * _VIEW_B_ARROW_LENGTH,
    )
    return (tail[0] - _VIEW_LETTER_HALF_WIDTH, tail[1]), tip


def _add_view_b_arrow(adapter: Any, section: Any) -> None:
    text_xy, tip_xy = _view_b_arrow(adapter, section)
    note = add_leader_note(
        adapter,
        JOURNAL_VIEW_LETTER,
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=section,
        label="view B viewing arrow",
    )
    # add_note leaves text at the document height; size the letter to the
    # A-A cutting-plane letters and prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("view B arrow note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError("failed to size the view B arrow letter")
    rebuild_drawing(adapter, label="view B arrow letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError("view B arrow tip moved when its letter was sized")
    _telemetry.info(
        f"view B arrow: tip=({tip_xy[0]:.4f}, {tip_xy[1]:.4f}) "
        f"letter=({text_xy[0]:.4f}, {text_xy[1]:.4f})"
    )


def _model_face_evidence(
    model: Any,
) -> dict[str, list[tuple[str, tuple[float, ...]]]]:
    """Read the final BREP surfaces behind the four disputed callouts."""
    rows: dict[str, list[tuple[str, tuple[float, ...]]]] = {}
    part = _early_bound(model, "IPartDoc")
    for name in (
        "CrankSprocketBoss",
        "CrankBore",
        "ConeShaftBoss",
        "ConeShaftBore",
    ):
        feature = part.FeatureByName(name)
        if feature is None:
            raise RuntimeError(f"missing model feature for drawing evidence: {name}")
        feature = _early_bound(feature, "IFeature")
        surfaces = []
        seen = set()
        for raw_face in feature.GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface.IsCylinder():
                item = (
                    "cylinder",
                    tuple(round(float(value), 9) for value in surface.CylinderParams),
                )
            elif surface.IsPlane():
                item = (
                    "plane",
                    tuple(round(float(value), 9) for value in surface.PlaneParams),
                )
            else:
                continue
            if item not in seen:
                seen.add(item)
                surfaces.append(item)
        if not surfaces:
            raise RuntimeError(f"{name} exposes no planar/cylindrical BREP surfaces")
        rows[name] = surfaces
    for feature, surfaces in rows.items():
        _telemetry.info(
            f"cone pivot post final BREP {feature}: {surfaces!r}"
        )
    return rows


def _plane_centres(
    face_evidence: dict[str, list[tuple[str, tuple[float, ...]]]],
    feature_name: str,
    count: int,
) -> list[tuple[float, float, float]]:
    """A feature's plane root points (model metres)."""
    centres = [
        (values[3], values[4], values[5])
        for kind, values in face_evidence[feature_name]
        if kind == "plane"
    ]
    if len(centres) != count:
        raise RuntimeError(
            f"{feature_name} has {len(centres)} BREP face centres, expected {count}"
        )
    return centres


def _crank_face_centres(
    face_evidence: dict[str, list[tuple[str, tuple[float, ...]]]],
) -> list[tuple[float, float, float]]:
    """The crank boss's north (head-tangent) face and far face, in that order.

    CrankSprocketBoss owns exactly two planes (faces on one surface are listed
    once, so the head's tangent line cannot split the count), and each stands
    at its printed station.
    """
    near, far = sorted(
        _plane_centres(face_evidence, "CrankSprocketBoss", 2), key=lambda p: p[2]
    )
    for label, centre, station in (
        ("north", near, CRANK_BOSS_START_Z),
        ("far", far, CRANK_BOSS_END_Z),
    ):
        if abs(centre[2] * 1000.0 - station) > 1e-3:
            raise RuntimeError(
                f"crank boss {label} face at z={centre[2] * 1000.0:.4f} mm, "
                f"expected {station:.4f}"
            )
    return [near, far]


def _assert_view_geometry(
    adapter: Any,
    *,
    front: Any,
    top: Any,
    journal: Any,
    iso: Any,
    face_evidence: dict[str, list[tuple[str, tuple[float, ...]]]],
) -> None:
    """Prove which bore axis each manufacturing view is normal to."""
    incline = math.radians(INCLINE_DEG)
    crank_axis = (0.0, 0.0, 1.0)
    cone_axis = (math.sin(incline), 0.0, math.cos(incline))
    crank_center = (0.0, CRANK_BORE_HEIGHT / 1000.0, 0.0)
    cone_center = (0.0, BORE_HEIGHT / 1000.0, 0.0)
    sample = 0.040

    rows = {}
    for label, raw_view in (
        ("front", front),
        ("top", top),
        ("journal", journal),
        ("isometric", iso),
    ):
        view = _early_bound(raw_view, "IView")
        transform = _early_bound(view.ModelToViewTransform, "IMathTransform")
        matrix = tuple(round(float(value), 9) for value in transform.ArrayData)

        def projected(
            center: tuple[float, float, float],
            axis: tuple[float, float, float],
        ) -> tuple[float, float]:
            origin = model_point_in_view(
                adapter, view, center, label=f"{label} bore-axis origin"
            )
            endpoint = model_point_in_view(
                adapter,
                view,
                tuple(center[i] + sample * axis[i] for i in range(3)),
                label=f"{label} bore-axis endpoint",
            )
            return tuple(endpoint[i] - origin[i] for i in range(2))

        rows[label] = {
            "transform": matrix,
            "crank_center": model_point_in_view(
                adapter, view, crank_center, label=f"{label} crank centre"
            ),
            "cone_center": model_point_in_view(
                adapter, view, cone_center, label=f"{label} cone centre"
            ),
            "crank_axis": projected(crank_center, crank_axis),
            "cone_axis": projected(cone_center, cone_axis),
        }

    def length(vector: tuple[float, float]) -> float:
        return math.hypot(*vector)

    if length(rows["front"]["crank_axis"]) > 1e-8:
        raise RuntimeError(f"front is not normal to crank bore: {rows['front']!r}")
    if length(rows["journal"]["cone_axis"]) > 1e-8:
        raise RuntimeError(
            f"cone journal view is not normal to cone bore: {rows['journal']!r}"
        )
    top_crank = rows["top"]["crank_axis"]
    top_cone = rows["top"]["cone_axis"]
    cosine = sum(a * b for a, b in zip(top_crank, top_cone)) / (
        length(top_crank) * length(top_cone)
    )
    acute = math.degrees(math.acos(max(-1.0, min(1.0, abs(cosine)))))
    if abs(acute - INCLINE_DEG) > 0.01:
        raise RuntimeError(
            f"top-view bore-axis angle {acute:.6f} != {INCLINE_DEG:.6f}"
        )
    iso_crank = rows["isometric"]["crank_center"]
    iso_cone = rows["isometric"]["cone_center"]
    if iso_crank[1] <= iso_cone[1]:
        raise RuntimeError(
            "isometric feature identity is inverted: "
            f"crank y={iso_crank[1]!r}, cone y={iso_cone[1]!r}"
        )
    for label, evidence in rows.items():
        _telemetry.info(
            f"cone pivot post native view {label}: {evidence!r}"
        )
    _telemetry.info(
        "cone pivot post isometric feature identity: "
        f"upper centre={iso_crank!r} is CrankSprocketBoss/CrankBore at "
        f"model Y={CRANK_BORE_HEIGHT:.3f}mm; lower centre={iso_cone!r} is "
        f"ConeShaftBoss/ConeShaftBore at model Y={BORE_HEIGHT:.3f}mm; "
        f"top acute axis angle={acute:.6f} deg"
    )
    crank_face_centres = _crank_face_centres(face_evidence)
    cone_face_centres = sorted(
        _plane_centres(face_evidence, "ConeShaftBoss", 2),
        key=lambda point: sum(point[i] * cone_axis[i] for i in range(3)),
    )
    iso_face_centres = {
        "crank_north_face": model_point_in_view(
            adapter,
            iso,
            crank_face_centres[0],
            label="isometric crank north-face centre",
        ),
        "crank_far_face": model_point_in_view(
            adapter,
            iso,
            crank_face_centres[1],
            label="isometric crank far-face centre",
        ),
        "cone_minus_face": model_point_in_view(
            adapter,
            iso,
            cone_face_centres[0],
            label="isometric cone minus-face centre",
        ),
        "cone_plus_face": model_point_in_view(
            adapter,
            iso,
            cone_face_centres[1],
            label="isometric cone plus-face centre",
        ),
    }
    crank_face_y = (
        iso_face_centres["crank_north_face"][1],
        iso_face_centres["crank_far_face"][1],
    )
    cone_face_y = (
        iso_face_centres["cone_minus_face"][1],
        iso_face_centres["cone_plus_face"][1],
    )
    if min(crank_face_y) <= max(cone_face_y):
        raise RuntimeError(
            "isometric projected face bands overlap or invert: "
            f"{iso_face_centres!r}"
        )
    _telemetry.info(
        "cone pivot post isometric projected face centres (sheet metres): "
        f"{iso_face_centres!r}; both CrankSprocketBoss face centres are above "
        "both ConeShaftBoss face centres"
    )

def _prepare_cone_section(adapter: Any, view: Any) -> None:
    """Keep only the full cut surface at an explicitly independent 1:2 scale."""
    bound = _early_bound(view, "IView")
    bound.UseParentScale = False
    bound.UseSheetScale = 0
    bound.ScaleRatio = double_array(
        [float(SECTION_SCALE[0]), float(SECTION_SCALE[1])]
    )
    section = _early_bound(bound.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    section.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="cone boss cut surface and independent scale")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    uses_parent = bool(bound.UseParentScale)
    uses_sheet = int(bound.UseSheetScale)
    if uses_parent or uses_sheet != 0 or not math.isclose(
        ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]
    ):
        raise RuntimeError(
            "independent cone-section scale did not persist: "
            f"{ratio=}, {uses_parent=}, {uses_sheet=}"
        )
    if not bool(section.GetDisplayOnlySurfaceCut()):
        raise RuntimeError("cone boss section retained geometry beyond the cut")
    if bool(section.GetPartialSection()):
        raise RuntimeError("cone boss section cutting line did not close")


# ASME Y14.2 runs a centerline a short, uniform distance past the feature it
# marks; 3 mm clears the boss end faces without reaching the 42.0 witness lines.
_CENTERLINE_OVERSHOOT_MM = 3.0
_SW_LINE_CENTER = 4  # swLineStyles_e.swLineCENTER


def _add_cone_section_centerline(adapter: Any, view: Any) -> None:
    """Draw the cone-bore axis through Section A-A.

    The section is a surface-only cut, so it has no bore face to hand
    ``InsertCenterLine2``; without the axis a blind reader saw two unrelated
    hatched islands.  The endpoints are the model axis projected through the
    section's own transform into sheet space, so the line is the bore axis
    itself, and it runs a centerline overshoot past each boss end face.
    """
    incline = math.radians(INCLINE_DEG)
    reach = (CONE_BOSS_LENGTH / 2.0 + _CENTERLINE_OVERSHOOT_MM) / 1000.0
    centre = (0.0, BORE_HEIGHT / 1000.0, 0.0)
    ends = [
        model_point_in_view(
            adapter,
            view,
            (
                sign * reach * math.sin(incline),
                centre[1],
                sign * reach * math.cos(incline),
            ),
            label=f"cone section axis end {sign:+d}",
        )
        for sign in (-1, 1)
    ]
    middle = model_point_in_view(adapter, view, centre, label="cone section axis")
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if not (outline[0] < middle[0] < outline[2] and outline[1] < middle[1] < outline[3]):
        raise RuntimeError(
            f"cone section axis {middle!r} falls outside the section {outline!r}"
        )
    printed = math.dist(*ends) * 1000.0 / (SECTION_SCALE[0] / SECTION_SCALE[1])
    if abs(printed - 2.0 * reach * 1000.0) > 0.01:
        raise RuntimeError(
            f"cone section axis projects foreshortened: {printed:.4f} mm"
        )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    # EditSheet makes the line sheet-owned; the endpoints are already in sheet
    # space, so it stays coincident with the projected model axis.
    drawing.EditSheet()
    sketch_manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        ends[0][0], ends[0][1], 0.0, ends[1][0], ends[1][1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to create the cone-bore centerline in Section A-A")
    # A sheet sketch line otherwise prints in the under-defined sketch blue;
    # override the layer so it prints like every native centerline.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0  # COLORREF black
    segment.Style = _SW_LINE_CENTER
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="cone section bore axis")
    if int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER:
        raise RuntimeError(
            "cone-bore centerline did not keep black centerline font: "
            f"color={int(segment.Color)}, style={int(segment.Style)}"
        )
    _telemetry.info(
        f"cone section bore axis drawn {ends[0]!r} -> {ends[1]!r} through {middle!r}"
    )


def _configure_section_caption(drawing_model: Any) -> None:
    """Make the native section caption print its view-specific scale."""
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    # swDetailingSectionViewLabels_{PerStandard,Scale,CustomScale} =
    # 242/247/84 and swDetailingViewLabelsScale_SCALEcustom = 3 on R2026x.
    if not extension.SetUserPreferenceToggle(242, 0, False):
        raise RuntimeError("failed to release standard section-label defaults")
    if not extension.SetUserPreferenceInteger(247, 0, 3):
        raise RuntimeError("failed to select custom section-label scale text")
    if not extension.SetUserPreferenceString(84, 0, SECTION_LABEL_SCALE_TEXT):
        raise RuntimeError("failed to write section-label scale text")
    if (
        extension.GetUserPreferenceToggle(242, 0)
        or int(extension.GetUserPreferenceInteger(247, 0)) != 3
        or str(extension.GetUserPreferenceString(84, 0))
        != SECTION_LABEL_SCALE_TEXT
    ):
        raise RuntimeError("native section-label scale text did not persist")


def _show_section_scale_in_caption(adapter: Any, view: Any) -> None:
    """Retain the linked native caption fields and place them clear.

    The section is drawn at the sheet scale, so its caption states no scale:
    ASME Y14.3 asks for one only when a view differs from the title block.
    """
    candidates = []
    for raw_note in _early_bound(view, "IView").GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>")):
            candidates.append(note)
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one native cone-section caption, found {len(candidates)}"
        )
    expected = "<VLNAME> <VLLABEL>"
    note = candidates[0]
    note.PropertyLinkedText = expected
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*SECTION_CAPTION, 0.0):
        raise RuntimeError("failed to position native cone-section caption")
    rebuild_drawing(adapter, label="show and position cone-section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], SECTION_CAPTION) > 1e-6:
        raise RuntimeError("native cone-section caption position did not persist")
    if str(note.PropertyLinkedText or "") != expected:
        raise RuntimeError("native cone-section scale caption did not persist")


def _view_outline(view: Any) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4:
        raise RuntimeError(f"view has an invalid outline: {outline!r}")
    return outline


def journal_axis_text_shift(sheet: Any) -> tuple[Any, float, float]:
    """The 33.37 text box the layout check reads, the crank spacing line
    beside it, and the x shift that leaves the box ``_TEXT_LINE_CLEARANCE``
    left of that line (negative moves it left)."""
    from _layout_geometry import union_boxes

    texts = [a for a in sheet.annotations if a.label == "JournalAxisY"]
    if len(texts) != 1:
        raise RuntimeError(
            f"expected one JournalAxisY on the sheet, found {len(texts)}"
        )
    box = union_boxes(list(texts[0].text_boxes))
    if box is None:
        raise RuntimeError("JournalAxisY has no text box to place")
    spacings = [a for a in sheet.annotations if a.label == "CrankAboveCone"]
    if len(spacings) != 1:
        raise RuntimeError(
            f"expected one CrankAboveCone on the sheet, found {len(spacings)}"
        )
    beside = [
        segment.x0
        for segment in spacings[0].segments
        if abs(segment.x1 - segment.x0) < 1e-9
        and segment.x0 > box.xmin
        and min(segment.y0, segment.y1) < box.ymax
        and max(segment.y0, segment.y1) > box.ymin
    ]
    if not beside:
        raise RuntimeError(
            "no vertical CrankAboveCone line beside the JournalAxisY text "
            f"{box.format_mm()}: the 33.37 placement premise no longer holds"
        )
    line_x = min(beside)
    return box, line_x, line_x - _TEXT_LINE_CLEARANCE - box.xmax


def _clear_journal_axis_text(adapter: Any, journal_annotations: list[Any]) -> None:
    """Move the 33.37 text so the box the layout check reads on this finished
    sheet ends ``_TEXT_LINE_CLEARANCE`` left of the crank spacing line."""
    from diagnostics.drawing_layout_audit import collect_document

    sheets = collect_document(adapter)
    if len(sheets) != 1:
        raise RuntimeError(
            f"cone pivot post must have one drawing sheet: {len(sheets)}"
        )
    box, line_x, shift = journal_axis_text_shift(sheets[0])
    dimensions = [
        annotation
        for annotation in journal_annotations
        if dimension_name(adapter, annotation) == "JournalAxisY"
    ]
    if len(dimensions) != 1:
        raise RuntimeError(
            f"expected one JournalAxisY in the cone journal view, found {len(dimensions)}"
        )
    annotation = _early_bound(dimensions[0], "IAnnotation")
    position = tuple(float(value) for value in annotation.GetPosition())
    if len(position) < 2:
        raise RuntimeError(f"JournalAxisY text has no position: {position!r}")
    if not annotation.SetPosition2(position[0] + shift, position[1], 0.0):
        raise RuntimeError("failed to move the JournalAxisY text clear of its line")
    rebuild_drawing(adapter, label="clear the 33.37 text of the crank spacing line")
    _telemetry.info(
        f"JournalAxisY text box {box.format_mm()} vs line x={line_x * 1000.0:.2f} mm: "
        f"moved text {shift * 1000.0:+.2f} mm from x={position[0] * 1000.0:.2f} mm"
    )


def _set_dimension_suffixes(adapter: Any, annotations: list[Any]) -> None:
    """Write each ``DIMENSION_SUFFIXES`` text after its dimension's size and
    band, failing loud unless every named dimension takes it exactly once."""
    applied: dict[str, int] = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        suffix = DIMENSION_SUFFIXES.get(name)
        if suffix is None:
            continue
        annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(_DIMENSION_TEXT_SUFFIX, suffix)
        actual = str(display.GetText(_DIMENSION_TEXT_SUFFIX) or "")
        if actual != suffix:
            raise RuntimeError(
                f"{name}: suffix {suffix!r} did not persist, read {actual!r}"
            )
        applied[name] = applied.get(name, 0) + 1
    if applied != dict.fromkeys(DIMENSION_SUFFIXES, 1):
        raise RuntimeError(
            f"expected each of {sorted(DIMENSION_SUFFIXES)} suffixed once, got {applied}"
        )


# The mounting holes' process, on its own row above the native through row
# (rule 12: "2X Ø7.14 THRU ALL" left drill against ream unsaid, r5 machinist
# review; draw_ch_fulcrum_keeper's foot-hole recipe).
MOUNT_HOLE_PROCESS = "DRILL\n"
# IDisplayDimension text definitions (5..8) and the parts SetText writes them
# through (1..4).
_HOLE_CALLOUT_DEFINITION_PARTS = ((5, 1), (6, 2), (7, 3), (8, 4))
# Hole Wizard callouts print three inch places (#290): the drill and the
# counterbore's diameter and depth.
MOUNT_HOLE_PRECISION = dict.fromkeys(
    ("hw-thruholedia", "hw-cbdia", "hw-cbdepth"), cone.MOUNT_HOLE_CALLOUT_PLACES
)


def mount_hole_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Put MOUNT_HOLE_PROCESS ahead of the one definition holding THRU.

    The counterbored callout's through row and its counterbore row live in
    different parts, so ``add_native_hole_callout(process=...)`` -- which
    writes the Prefix part whichever row that is -- could put DRILL ahead of
    the counterbore; ahead of the THRU part it stands on its own row first.
    """
    if set(definitions) != {part for part, _ in _HOLE_CALLOUT_DEFINITION_PARTS}:
        raise RuntimeError(f"unexpected mounting-hole callout parts: {definitions!r}")
    thru_parts = [part for part, text in definitions.items() if "THRU" in text.upper()]
    if len(thru_parts) != 1:
        raise RuntimeError(
            f"mounting-hole THRU row is not in one part: {definitions!r}"
        )
    part = thru_parts[0]
    return {
        **definitions,
        part: compose_hole_callout_prefix(MOUNT_HOLE_PROCESS, definitions[part]),
    }


def _set_mount_hole_process(display: Any) -> None:
    """Write the mounting holes' process row and prove it persisted first."""
    native = _early_bound(display, "IDisplayDimension")
    parts = [part for part, _ in _HOLE_CALLOUT_DEFINITION_PARTS]
    definitions = {part: str(native.GetText(part) or "") for part in parts}
    updated = mount_hole_callout_definitions(definitions)
    for definition_part, writable_part in _HOLE_CALLOUT_DEFINITION_PARTS:
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in parts}
    resolved = {
        part: str(native.GetText(part) or "")
        for _, part in _HOLE_CALLOUT_DEFINITION_PARTS
    }
    # The CalloutAbove part (3) prints ahead of the Prefix part (1).
    first = resolved[3] or resolved[1]
    if persisted != updated or not first.startswith(MOUNT_HOLE_PROCESS):
        raise RuntimeError(
            "mounting-hole process row did not persist first: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )
    _telemetry.info(f"mounting-hole callout: {resolved!r}")


def _pin_sheet_scale(adapter: Any) -> None:
    """Re-pin the sheet's scale before the native gate reads (or its failure
    PDF prints) the title block.

    Inserting a model view drifts the sheet scale; ``finalize_drawing``
    re-pins it before export, but the native gate and its evidence PDF come
    first, and rim-8339's evidence printed "SCALE: 1:2" on a 1:1 sheet.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    numerator, denominator = SHEET_SCALE
    if not sheet.SetScale(float(numerator), float(denominator), False, False):
        raise RuntimeError(f"failed to pin the sheet at {numerator:g}:{denominator:g}")


def _assert_native_layout_with_evidence(
    adapter: Any,
    journal: Any,
    *,
    expected_finish: str,
) -> None:
    """The native layout gate, leaving the failing sheet as a PDF.  The
    evidence never masks the failure: the gate's own error is re-raised
    whatever the export does."""
    try:
        _assert_native_layout(adapter, journal, expected_finish=expected_finish)
    except RuntimeError:
        try:
            _export_failure_pdf(adapter, "native-layout")
        except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
            _telemetry.warn(f"native-layout failure PDF raised: {exc!r}")
        raise


def _export_failure_pdf(adapter: Any, stage: str) -> None:
    """Export the failing sheet under the forensic tree the farm uploads."""
    try:
        folder = (
            _seat_forensics.OUT_FAILURES
            / f"dt-cone-pivot-post-{stage}"
            / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        folder.mkdir(parents=True, exist_ok=True)
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        path = folder / "dt-cone-pivot-post.pdf"
        model.SaveAs3(str(path), 0, 0)
        paths = [path]
    except Exception as exc:  # noqa: BLE001 - evidence must not mask the failure
        _telemetry.warn(f"{stage}-failure PDF export failed: {exc!r}")
        return
    for path in paths:
        if not path.is_file():
            _telemetry.warn(f"{stage}-failure PDF export produced no file: {path}")
            continue
        _telemetry.event("drawing.failure_pdf", stage=stage, path=str(path))
        _telemetry.info(f"{stage}-failure evidence PDF: {path}")


def view_placement_problems(
    outlines: Mapping[str, tuple[float, float, float, float]],
    region: Any,
    keep_outs: tuple[tuple[str, Any], ...],
) -> list[str]:
    """Views that leave the inner border or reach into a keep-out (the
    title block).  The text audit reads annotations, not view outlines."""
    from _layout_geometry import DEFAULT_TEXT_TOUCH_TOL_M, Box

    problems = []
    for label, outline in outlines.items():
        box = Box(*outline)
        escape = box.escape(region)
        if escape is not None:
            problems.append(f"{label} leaves the inner border: {box.format_mm()}, {escape=}")
        for keep_out_name, keep_out in keep_outs:
            if box.overlaps(keep_out, tol=DEFAULT_TEXT_TOUCH_TOL_M) is not None:
                problems.append(
                    f"{label} reaches into the {keep_out_name}: "
                    f"{box.format_mm()} vs {keep_out.format_mm()}"
                )
    return problems


def _assert_native_layout(
    adapter: Any,
    journal: Any,
    *,
    expected_finish: str,
) -> None:
    """Prove the final live sheet geometry before spending an export."""
    from _layout_geometry import (
        DEFAULT_TEXT_TOUCH_TOL_M,
        Box,
        audit_sheet,
        format_findings,
        segment_box_overlap_length,
    )
    from diagnostics.drawing_layout_audit import collect_document

    sheets = collect_document(adapter)
    if len(sheets) != 1:
        raise RuntimeError(f"cone pivot post must have one drawing sheet: {len(sheets)}")
    sheet = sheets[0]

    journal_box = Box(*_view_outline(journal))
    placement = view_placement_problems(
        {"cone journal view": _view_outline(journal)}, sheet.region, ()
    )
    if placement:
        raise RuntimeError("cone pivot post view placement failed:\n" + "\n".join(placement))
    # Hiding a sketch in a view hides the dimensions imported from it
    # (rim-aba9 lost the crank boss station that way), so the plan's two
    # hidden-owner dimensions and Section A-A's must each still print, once.
    labels = [annotation.label for annotation in sheet.annotations]
    missing = [
        name
        for name in ("CrankBossStartZ", "InclineAngle", "ConeBossNorthZ")
        if labels.count(name) != 1
    ]
    if missing:
        raise RuntimeError(
            f"the sheet must print each of {missing} once: {sorted(labels)}"
        )

    finish_notes = []
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet_view = _early_bound(drawing.GetFirstView(), "IView")
    for raw_annotation in sheet_view.GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        linked = str(note.PropertyLinkedText or "")
        if "$prp" in linked.casefold() and "finish" in linked.casefold():
            finish_notes.append(note)
    if len(finish_notes) != 1:
        raise RuntimeError(
            "landscape template must expose exactly one linked Finish note: "
            f"{len(finish_notes)}"
        )
    finish_note = finish_notes[0]
    actual_finish = str(finish_note.GetText() or "").replace("\r\n", "\n")
    if actual_finish != expected_finish:
        raise RuntimeError(
            "Finish title-block readback mismatch: "
            f"{actual_finish!r} != {expected_finish!r}"
        )
    extent = tuple(float(value) for value in finish_note.GetExtent())
    if len(extent) != 6:
        raise RuntimeError(f"Finish title-block note has invalid extent: {extent!r}")
    finish_box = Box(
        min(extent[0], extent[3]),
        min(extent[1], extent[4]),
        max(extent[0], extent[3]),
        max(extent[1], extent[4]),
    )
    finish_cell = Box(*_FINISH_CELL)
    if (
        finish_box.xmin < finish_cell.xmin
        or finish_box.ymin < finish_cell.ymin
        or finish_box.xmax > finish_cell.xmax
        or finish_box.ymax > finish_cell.ymax
    ):
        raise RuntimeError(
            "Finish title-block note leaves its authored cell: "
            f"note={finish_box.format_mm()}, cell={finish_cell.format_mm()}"
        )

    surface_boxes = [
        box
        for annotation in sheet.annotations
        if annotation.kind == "surface-finish"
        for box in annotation.text_boxes
    ]
    if len(surface_boxes) != len(SURFACE_FINISHES):
        raise RuntimeError(
            f"cone pivot post must expose {len(SURFACE_FINISHES)} native Ra "
            f"text boxes: {len(surface_boxes)}"
        )
    own_overlaps = {}
    for label in ("JournalAxisY", "CrankAboveCone"):
        dimensions = [
            annotation for annotation in sheet.annotations if annotation.label == label
        ]
        if len(dimensions) != 1:
            raise RuntimeError(
                f"expected one visible native {label} annotation, found "
                f"{len(dimensions)}"
            )
        dimension = dimensions[0]
        text_interiors = [
            Box(
                box.xmin + DEFAULT_TEXT_TOUCH_TOL_M,
                box.ymin + DEFAULT_TEXT_TOUCH_TOL_M,
                box.xmax - DEFAULT_TEXT_TOUCH_TOL_M,
                box.ymax - DEFAULT_TEXT_TOUCH_TOL_M,
            )
            for box in dimension.text_boxes
        ]
        own_overlap = max(
            (
                segment_box_overlap_length(segment, box)
                for box in text_interiors
                for segment in dimension.segments
            ),
            default=0.0,
        )
        if own_overlap > DEFAULT_TEXT_TOUCH_TOL_M:
            raise RuntimeError(
                f"{label}'s own dimension ink crosses its text by "
                f"{own_overlap * 1000.0:.3f} mm"
            )
        own_overlaps[label] = round(own_overlap * 1000.0, 3)
    findings = audit_sheet(sheet)
    if findings:
        raise RuntimeError(
            "cone pivot post native annotation layout failed:\n"
            f"{format_findings(findings)}"
        )
    axis_box, line_x, shift = journal_axis_text_shift(sheet)
    if shift < -1e-4:
        raise RuntimeError(
            f"JournalAxisY text {axis_box.format_mm()} ends "
            f"{(line_x - axis_box.xmax) * 1000.0:.2f} mm left of the crank spacing "
            f"line at x={line_x * 1000.0:.2f} mm; it must clear it by "
            f"{_TEXT_LINE_CLEARANCE * 1000.0:.2f} mm"
        )
    _telemetry.info(
        "cone pivot post native layout: "
        f"journal={journal_box.format_mm()}; "
        f"finish={finish_box.format_mm()} in {finish_cell.format_mm()}; "
        f"Ra={[box.format_mm() for box in surface_boxes]}; "
        f"self-overlap mm={own_overlaps}; "
        f"JournalAxisY text={axis_box.format_mm()} clears x={line_x * 1000.0:.2f} "
        f"by {(line_x - axis_box.xmax) * 1000.0:.2f} mm"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-pivot-post source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    face_evidence = _model_face_evidence(adapter.currentModel)
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cone-pivot-post"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Pivot Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "bossed cast-iron post; inclined cone journal; crank journal",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    journal = place_view(
        adapter,
        str(SOURCE),
        CONE_AXIS_VIEW,
        *JOURNAL_CENTER,
        scale=(1, 1),
    )
    _configure_section_caption(drawing_model)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # ConeBossStationReference lies in A-A's cutting plane, saved hidden: a
    # derived view takes it from the part as it stands when it is cut and
    # selects it through its base view, so the section is cut and curated
    # while the part shows it (draw_fr_rocker_arm_support's recipe).  In the
    # elevation the ray lies on the A-A line itself.
    with part_sketches_shown(
        adapter,
        source_model,
        ("ConeBossStationReference",),
        label="section A-A cone boss station",
        base_view=front,
    ):
        section = create_section_view(
            adapter,
            front,
            line_start=CONE_SECTION_LINE[0],
            line_end=CONE_SECTION_LINE[1],
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            label="cone boss bore-plane profile",
        )
        _prepare_cone_section(adapter, section)
        set_hidden_lines_removed(adapter, section)
        section_annotations = curate_hidden_owner_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="cone boss bore-plane section",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    # The named journal view looks exactly down the inclined model axis.  Unlike
    # the bore-plane section, it retains the uncut boss end face, so its Ø17.2
    # OD and Ø12.281 bore are two visible concentric circles with clear leaders.
    # The isometric too (PR #1436): a newly placed view may already read as
    # shaded, so the final shaded-with-edges call alone can be a no-op that
    # leaves its edges at draft quality.
    for view in (front, top, journal, iso):
        set_hidden_lines_removed(adapter, view)
    _assert_view_geometry(
        adapter,
        front=front,
        top=top,
        journal=journal,
        iso=iso,
        face_evidence=face_evidence,
    )

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The part saves its reference sketches hidden.  The plan dimensions the
    # plan angle and the crank boss station and View B the bore spacing, so
    # each shows its owning sketch (JournalPlanReference's two rays,
    # CrankBossStationReference's ray, BoreSpacingReference's centreline
    # joining the bores) in that view only; Section A-A (above) shows
    # ConeBossStationReference's rays the same way.
    top_annotations = curate_hidden_owner_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    journal_annotations = curate_hidden_owner_dimensions(
        adapter,
        journal,
        keep=JOURNAL_KEEP,
        view_label="cone journal",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *journal_annotations,
        *section_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _set_dimension_suffixes(adapter, annotations)
    near_side = {name: 0 for name in NEAR_SIDE_DIAMETERS}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in near_side:
            set_near_side_diameter(annotation, f"{name} near-side leader")
            near_side[name] += 1
    if set(near_side.values()) != {1}:
        raise RuntimeError(f"expected each near-side diameter once, got {near_side}")
    crank_height = [
        annotation
        for annotation in front_annotations
        if dimension_name(adapter, annotation) == "CrankAxisY"
    ]
    if len(crank_height) != 1:
        raise RuntimeError(
            f"expected one CrankAxisY in the front view, found {len(crank_height)}"
        )
    set_reference_dimension(
        adapter, crank_height[0], label="crank axis height reference"
    )
    # #906: the plan angle feeds the crank bore's angularity frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)).
    set_basic_dimensions(adapter, annotations, BASIC_DIMENSIONS)
    # The part authored these places (cone_pivot_post_spec.DRAWING_PRECISION);
    # this sheet only proves they survived the import.  A silent fallback to
    # the drawing document's two places would print the running bores without
    # the third place their fit band is written in.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    offset_dimension_text(
        adapter,
        journal_annotations,
        JOURNAL_TEXT_OFFSETS,
    )
    for view, label in ((front, "front"), (top, "top"), (journal, "cone journal")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")
    add_view_centerline(
        adapter,
        front,
        face_xy=(_front_x(0.0), _front_y(20.0)),
        label="main body axis",
    )
    add_view_centerline(
        adapter,
        top,
        face_xy=(_top_x(0.0), _top_y(35.0)),
        label="crank boss axis",
    )
    _add_cone_section_centerline(adapter, section)
    _add_view_b_arrow(adapter, section)

    mount_callout = add_native_hole_callout(
        adapter,
        top,
        edge=_circular_edge(
            top,
            radius_mm=ATTACHMENT_CBORE_DIA / 2.0,
            center_y_mm=BLOCK_HEIGHT,
            center_x_mm=ATTACHMENT_X,
        ),
        # Its three rows (DRILL on its own) run 61 mm wide; at x=0.160 they
        # stood 10 mm from the section's thrust-face station, under one text
        # height (r6 view-crowding).
        callout_xy=(0.155, 0.250),
        label="mounting counterbores",
    )
    _set_mount_hole_process(mount_callout)
    set_hole_callout_precision(
        mount_callout, MOUNT_HOLE_PRECISION, label="mounting counterbores"
    )

    # The seat is the elevation's bottom line: the O42.011 foot rim seen
    # edge-on.  A coordinate pick on that line failed on the farm (the two
    # mounting-hole exit rims project onto the same line, so the hit-test has
    # nothing unambiguous to return), so the rim is found by its geometry --
    # the ONE circular edge of body radius centred at y=0.  Its leader lands
    # on the seat's left quarter while the symbol sits clear of the body at right.
    add_surface_finish(
        adapter,
        front,
        edge_entity=_circular_edge(front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0),
        symbol_xy=(_front_x(30.0), _front_y(-6.0)),
        leader_attach_xy=(_front_x(-10.0), _front_y(0.0)),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
    )
    # The crank-bore Ra stands left of the head, between the crank-height
    # reference and the body's top witness: a symbol above the view crossed
    # that top witness (leader-crosses-line, ha-perf-parts audit).  Its
    # leader runs level with the rim landing, above the (81.20) reference's
    # upper extension line at the crank axis: from y=0.1447 it crossed that
    # line (r1 machinist review).
    add_surface_finish(
        adapter,
        front,
        edge_entity=_bore_rim_edge(front, diameter_mm=CRANK_BORE_DIA),
        symbol_xy=(0.050, 0.1505),
        leader_attach_xy=model_point_in_view(
            adapter,
            front,
            (
                -(CRANK_BORE_DIA / 2.0) / math.sqrt(2.0) / 1000.0,
                (
                    CRANK_BORE_HEIGHT
                    + (CRANK_BORE_DIA / 2.0) / math.sqrt(2.0)
                )
                / 1000.0,
                0.0,
            ),
            label="crank bore finish anchor",
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "crank_bore"),
        label="crank bore finish",
        char_height=0.0025,
    )
    # The journal bore's Ra lands on its lower-right rim below the size's
    # leader, the symbol right of the view (JOURNAL_BORE_FINISH_XY).
    journal_centre = model_point_in_view(
        adapter,
        journal,
        (0.0, BORE_HEIGHT / 1000.0, 0.0),
        label="cone journal bore centre",
    )
    journal_top = model_point_in_view(
        adapter,
        journal,
        (0.0, (BORE_HEIGHT + BORE_DIA / 2.0) / 1000.0, 0.0),
        label="cone journal bore top rim",
    )
    journal_radius = math.dist(journal_centre[:2], journal_top[:2])
    finish_bearing = math.radians(JOURNAL_BORE_FINISH_DEG)
    add_surface_finish(
        adapter,
        journal,
        edge_entity=_bore_rim_edge(journal, diameter_mm=BORE_DIA),
        symbol_xy=JOURNAL_BORE_FINISH_XY,
        leader_attach_xy=(
            journal_centre[0] + journal_radius * math.cos(finish_bearing),
            journal_centre[1] + journal_radius * math.sin(finish_bearing),
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "journal_bore"),
        label="cone journal bore finish",
        char_height=0.0025,
    )
    # The shaft collar's thrust face (#914).  Every other view sees it hidden
    # behind the body, so it is called out on its A-A cut edge.
    north_edge = _north_boss_end_edge(section)
    north_anchor = _north_boss_finish_anchor(adapter, section, north_edge)
    add_surface_finish(
        adapter,
        section,
        symbol_xy=(
            north_anchor[0] + _NORTH_BOSS_FINISH_OFFSET[0],
            north_anchor[1] + _NORTH_BOSS_FINISH_OFFSET[1],
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "cone_boss_north_face"),
        label="north cone boss end finish",
        char_height=0.0025,
        entity=north_edge,
        leader_attach_xy=north_anchor,
    )
    # #906 (USER RULING 2026-09-26): the crank bore's angularity to the cone
    # journal, model PMI (cone_pivot_post_spec.PART_DATUMS /
    # GEOMETRIC_CONTROLS) projected here.  Datum A tags the journal bore in
    # View C, the only view that shows it true; datum B tags the foot seat
    # edge-on in the elevation, left of the body and clear of the foot-seat
    # finish on the right; the frame hangs off the crank bore rim in the
    # elevation, right of the body and below the bore callout.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=journal,
                position=DATUM_A_TAG_XY,
                attachment_xy=(
                    journal_centre[0]
                    + journal_radius * math.cos(math.radians(DATUM_A_LANDING_DEG)),
                    journal_centre[1]
                    + journal_radius * math.sin(math.radians(DATUM_A_LANDING_DEG)),
                ),
            ),
            "datum:B": PmiDrawingPlacement(
                view=front,
                position=DATUM_B_TAG_XY,
                edge_entity=_circular_edge(
                    front, radius_mm=BLOCK_DIA / 2.0, center_y_mm=0.0
                ),
            ),
            # The frame sits right of the head between HeadHt's extension
            # lines, 3.7 mm below the crank axis, so it rides with the head
            # when the post's height moves (a fixed y=0.138 met HeadHt's lower
            # witness once the inch-train body grew to 94.7). Its leader lands
            # on the bore rim at -28 degrees, below the bore's own near-side
            # leader and clear of the centre-mark arm:
            # from (0.160, 0.128) to the natural lower-left landing it
            # crossed HeadHt's and CrankBossDia's lines (leader-crosses-line,
            # af13).  A sheet-point pick sets the landing; explicit leader
            # placement detached a GTol from its edge (fulcrum 1149f227f).
            "crank_bore_angularity": PmiDrawingPlacement(
                view=front,
                position=(0.124, _front_y(CRANK_BORE_HEIGHT) - 0.0037),
                attachment_xy=(
                    _front_x(CRANK_BORE_DIA / 2.0 * math.cos(math.radians(-28.0))),
                    _front_y(
                        CRANK_BORE_HEIGHT
                        + CRANK_BORE_DIA / 2.0 * math.sin(math.radians(-28.0))
                    ),
                ),
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="cone pivot post PMI",
    )
    add_note(
        adapter,
        f"VIEW {JOURNAL_VIEW_LETTER} - CONE JOURNAL\nLOOK ALONG CONE AXIS",
        0.202,
        0.104,
    )
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method) caps the block at four lines (about 18 mm); the anchor keeps the
    # r7 clearance to the bottom inner border.
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_ANCHOR)
    # Last of the notes: a view-owned note leaves its view active, and a
    # sheet note inserted after it joins that view (the notes block did, and
    # crowded datum B across views: r14 view-crowding).
    incline = math.radians(cone.INCLINE_DEG)
    add_leader_note(
        adapter,
        CONE_AXIS_LABEL,
        text_xy=CONE_AXIS_LABEL_XY,
        attach_xy=(
            _top_x(CONE_AXIS_LABEL_TIP_RADIUS_MM * math.sin(incline)),
            _top_y(CONE_AXIS_LABEL_TIP_RADIUS_MM * math.cos(incline)),
        ),
        view=top,
        label="plan cone bore axis label",
    )

    # Attaching dimensions and symbols can leave a stale hidden-line display.
    # Reassert each manufacturing view after its final annotation.
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, top)
    set_hidden_lines_removed(adapter, journal)
    set_hidden_lines_removed(adapter, section)
    _pin_sheet_scale(adapter)
    rebuild_drawing(adapter, label="final cone pivot post native layout")
    _show_section_scale_in_caption(adapter, section)
    _clear_journal_axis_text(adapter, journal_annotations)
    _assert_native_layout_with_evidence(
        adapter,
        journal,
        expected_finish=source_properties["Finish"],
    )

    set_high_quality_shaded_with_edges(adapter, iso, label="pictorial isometric")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Pivot Post Manufacturing Drawing",
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
