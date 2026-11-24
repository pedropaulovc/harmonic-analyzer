r"""Create the curated machinist drawing for the connecting rod.

The SLDPRT remains authoritative.  This recipe supplies only the connecting-rod
views, dimension layout, callout text, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``; the
side view's reference sketch, which the part saves hidden, is shown there by
``_drawing_hidden_sketches``.

The rod is a tall thin lollipop (~184 mm ring-bottom to fork crown), so the
sheet runs at 1:1 with a 1:2 isometric; the fork's side profile (tines, slot
and the shank's near face located from one fork face, and the shank's
thickness) prints in a 3:1 detail of the side view, and the side view carries
the ring's near face from that same fork face, the ring's thickness and the
overall length as a reference.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_connecting_rod.py ch-connecting-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

import _config
from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_crop import native_circle_geometry
from _drawing_detail_projection import settle_detail_projection
# The ring's near face is owned by a reference sketch the part saves hidden.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import face_silhouettes_through
from _drawing_finish import add_surface_finish
from _drawing_precision import set_dimension_display_precision
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import limits
from _printed_tolerance import inside_corner_radius_mm
from _session import run_build
from _surface_finish import MACHINED_UM, surface_finish_by_key
import _telemetry
from ch_connecting_rod_notes import (
    CAM_SLOT_NOTE_NUMBER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_FIT_NOTE_NUMBER,
    PIN_NUMBER,
    SHANK_CORNER_CALLOUT,
    SHANK_CORNER_COUNT,
    SHANK_CORNER_R,
    SLOT_FIT_NOTE_NUMBER,
)
from ch_connecting_rod_spec import (
    CENTER_DISTANCE,
    FORK_BASE_Y,
    FORK_CROTCH_Y,
    FORK_SLOT_BAND,
    FORK_SLOT_WIDTH,
    FORK_THICKNESS,
    FORK_THICKNESS_BAND,
    FORK_TOP_Y,
    FORK_WIDTH,
    GEOMETRIC_TOLERANCES_IN,
    GEOMETRIC_TOLERANCES_MM,
    PIN_HOLE_DIA,
    PIN_HOLE_LIMITS,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_BOTTOM_Y,
    RING_FACE_BAND,
    RING_FACE_NEAR,
    RING_OUTER_DIA,
    RING_OUTER_RADIUS,
    RING_THICKNESS,
    RING_THICKNESS_BAND,
    SHANK_FACE_BAND,
    SHANK_FACE_NEAR,
    SHANK_THICKNESS,
    SHANK_THICKNESS_BAND,
    SHANK_WIDTH,
    STRAP_DIAMETRAL_CLEARANCE,
    SURFACE_FINISHES,
    TINE_BAND,
    TINE_THICKNESS,
    UNIT,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["ch_connecting_rod"]
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
_PIN_HOLE_DIA = PIN_HOLE_DIA

SHEET_SCALE = (1.0, 1.0)  # 1:1
# The BASIC centre distance (6.235): three inch places hold the printed value
# within .0005 of the closure, well inside the pin's Ø.014 position zone.
CENTRE_DISTANCE_PLACES = 3

# Front-view model bbox: X symmetric about 0, Y from the ring bottom up to the
# fork crown.  The left view shares it (Z symmetric about the mid-plane).
_BBOX_CY = (RING_BOTTOM_Y + FORK_TOP_Y) / 2.0

FRONT_CENTER = (0.180, 0.135)
# Third-angle left view, aligned with the front view: it shows the stepped
# thickness and carries the fork detail's circle.
LEFT_CENTER = (0.080, FRONT_CENTER[1])
ISO_CENTER = (0.398, 0.212)
# Over the isometric: below it, the detail's boss-length witness runs out.
ISO_NOTE_XY = (0.352, 0.262)
# The pin hole's matched-fit note (upper-left): top centre, between the side
# view's detail letter and the isometric's label, over the reamed hole's
# callout.
NOTES_XY = (0.110, 0.262)

# The mates the tight bands name (drawing-guidelines.md rule 7).
CAM_NUMBER = str(_config.parts("dt-cylinder-gear")["number"])


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:1)."""
    return (
        FRONT_CENTER[0] + mx / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


def _left_xy(offset: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) ``offset`` mm right of the left view's mid-plane at model
    height ``my`` (1:1)."""
    return (
        LEFT_CENTER[0] + offset / 1000.0,
        LEFT_CENTER[1] + (my - _BBOX_CY) / 1000.0,
    )


FRONT_KEEP = {
    # Both ring diameters stand outside the ring, down-left, their leaders
    # meeting the rims (inside the ring the texts sat on the ring's ink). The
    # outer's text stands clear right of the centre distance's line (r1).
    "RingOuterDia": (0.145, 0.100),
    "StrapBoreDia": (0.130, 0.040),
    # Right of the shank, so the flanks never strike the value.
    "ShankWidthDim": (0.198, 0.150),
    "ForkWidthDim": _sheet_xy(0.0, FORK_TOP_Y + 8.0),
    # The reamed pin hole's value stands right of the fork, below the position
    # FCF's level leader, so the two leaders cannot cross.
    "PinHoleDia": (0.218, 0.196),
    # The shank's four corners, 4X R.065 (owner ruling 2026-11-23, tool audit
    # Q9): up-right of the ring, right of the shank, its leader down-left to
    # the right-hand flank's corner on the ring (the ShankCorners fillet's
    # first edge, build_ch_connecting_rod); its two reason lines stand above
    # the bore's finish symbol, clear of the ring's ink.
    "ShankCornerR": (0.214, 0.106),
}
# One arrow on the rim nearest each text (set_near_side_diameter).
NEAR_SIDE_DIAMETERS = ("RingOuterDia", "StrapBoreDia")
# Descriptive text beneath each native value/band: the strap bore and its
# cam, named by the standard fit with its clearance as REF (rule 4); the
# fork's crown, a full round on the pin tangent to its sides; the reamed
# press hole, size then process (rules 12 and 26) and the flag of the note
# that names its pin and the matched fit once (rule 4, fan-out round 4: named
# at the callout too, the mate printed twice).
_CLEARANCE_LEAST, _CLEARANCE_MOST = STRAP_DIAMETRAL_CLEARANCE


def _inch(value_mm: float, places: int) -> str:
    """A millimetre value as inch text at ``places``, no leading zero."""
    return f"{value_mm / 25.4:.{places}f}".removeprefix("0")


FRONT_CALLOUTS = {
    "StrapBoreDia": (
        f"BORE\nRUNNING FIT ON {CAM_NUMBER}\n"
        f"(CLEARANCE {_inch(_CLEARANCE_LEAST, 3)}-{_inch(_CLEARANCE_MOST, 3)})"
    ),
    "ForkWidthDim": "FULL R",
    "PinHoleDia": f"REAM THRU\nSEE NOTE {PIN_FIT_NOTE_NUMBER}",
    "ShankCornerR": SHANK_CORNER_CALLOUT,
}

# The side view at 1:1, below the ring (#3114: the ring is the sliding fit in
# the cam slot, so its two bands print at the ring). Nearest the ring, the
# ring's near face from the fork's datum face: one witness drops from the
# fork's root corner down the whole shank, the other from the ring's bottom
# corner. Under it the ring's thickness (#982 review r1), its witnesses
# dropping from the ring's two bottom corners. Both values stand out to the
# left, the thickness's further out and lower, so neither text block (value
# and flag) stands over the other and the thickness's dimension line passes
# under the offset's flag.
_RING_BOTTOM_SHEET_Y = _left_xy(0.0, RING_BOTTOM_Y)[1]
LEFT_KEEP = {
    "RingFaceNear": (0.060, _RING_BOTTOM_SHEET_Y - 0.007),
    "RingThick": (0.032, _RING_BOTTOM_SHEET_Y - 0.017),
}
# Each band's one short line flags the note that names the cam slot the ring
# slides in (fan-out round 2: both bands serve that fit; long lines ran into
# the sheet border, r2).
LEFT_CALLOUTS = {
    "RingFaceNear": f"SEE NOTE {CAM_SLOT_NOTE_NUMBER}",
    "RingThick": f"SEE NOTE {CAM_SLOT_NOTE_NUMBER}",
}
# The overall length, ring bottom to crown top, as a reference: the side
# view's ring-bottom silhouette and the far tine's crown-top silhouette,
# named by their faces and projected model points (a coordinate hit-test on
# the 2 mm ring bottom missed on the farm, r2), right of the side view, clear
# of the detail circle's letter on its left. Model points in mm.
OVERALL_LENGTH = FORK_TOP_Y - RING_BOTTOM_Y
OVERALL_BOTTOM_MM = (0.0, RING_BOTTOM_Y, 0.0)
OVERALL_TOP_MM = (0.0, FORK_TOP_Y, (FORK_THICKNESS + FORK_SLOT_WIDTH) / 4.0)
OVERALL_FACES = {
    "ring bottom": CylinderFace(2.0 * RING_OUTER_RADIUS),
    # The slot splits the crown's full round into one face per tine.
    "crown top": CylinderFace(FORK_WIDTH, contains_z_mm=OVERALL_TOP_MM[2]),
}
OVERALL_TEXT_XY = (0.100, 0.175)

# DETAIL C: the fork's side profile at 3:1. At 1:1 the tines, slot and shank
# faces are 1.3-2.7 mm features and their dimensions crowded the side view
# (baseline review). The fence centres on the rod axis midway between the
# crown top and the shank-face reference's lower end and takes in both.
DETAIL_SCALE = (3, 1)
# 12.5: the fence the passing layouts printed (an inferred draw had snapped
# the authored 11.0 out to ~12.4), clear of the slot depth's text inside it.
DETAIL_RADIUS_MM = 12.5
DETAIL_FENCE_Y_MM = (FORK_TOP_Y + FORK_BASE_Y - 2.0) / 2.0
# Right of the front view's pin-hole callout and FCF, below the isometric,
# above the title block.
DETAIL_CENTER = (0.325, 0.135)
# How far the fence centre may print from DETAIL_CENTER once placed (the
# 0.5 mm the section and detail settle reads allow, draw_dt_cone_swing_platform).
DETAIL_PLACEMENT_TOL_M = 0.0005
_DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
_DETAIL_FENCE_R = DETAIL_RADIUS_MM * _DETAIL_MM
if DETAIL_RADIUS_MM <= math.hypot(FORK_THICKNESS / 2.0, FORK_TOP_Y - DETAIL_FENCE_Y_MM):
    raise AssertionError("DETAIL C's fence must take in the whole crown top")
# The label stands right of the fence, between the boss length's witnesses.
DETAIL_LABEL_XY = (0.395, 0.140)
# The fence's letter on the side view, up-left of its circle.
DETAIL_LETTER_XY = (
    LEFT_CENTER[0] - DETAIL_RADIUS_MM / 1000.0 - 0.006,
    LEFT_CENTER[1] + (DETAIL_FENCE_Y_MM - _BBOX_CY + DETAIL_RADIUS_MM) / 1000.0,
)


def _detail_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of side-view point (model z, model y) in DETAIL C: the
    *Left view runs model +Z to the right, so the datum fork face (model -Z,
    the build's sketch +x) stands on the LEFT."""
    return (
        DETAIL_CENTER[0] + z_mm * _DETAIL_MM,
        DETAIL_CENTER[1] + (y_mm - DETAIL_FENCE_Y_MM) * _DETAIL_MM,
    )


_FACE_X = _detail_xy(-FORK_THICKNESS / 2.0, FORK_TOP_Y)[0]
_FAR_X = _detail_xy(FORK_THICKNESS / 2.0, FORK_TOP_Y)[0]
_TINE_TOP_Y = _detail_xy(0.0, FORK_TOP_Y)[1]
_ROOT_Y = _detail_xy(0.0, FORK_BASE_Y)[1]
# The shank-face reference's lower end (build_ch_connecting_rod).
_REF_END_Y = _detail_xy(0.0, FORK_BASE_Y - 2.0)[1]
DETAIL_KEEP = {
    # Over the tines, nearest first: the near tine (text wholly left of the
    # datum face's witness), the slot (text right of the far face), the
    # reference thickness centred over the fork.
    "TineNear": (_FACE_X - 0.030, _TINE_TOP_Y + 0.012),
    "SlotWidth": (_FAR_X + 0.030, _TINE_TOP_Y + 0.016),
    "ForkThick": (DETAIL_CENTER[0], _TINE_TOP_Y + 0.028),
    # Down the right-hand side from the crown top: the slot depth inside, the
    # boss length outside.
    "SlotDepth": (_FAR_X + 0.016, (_TINE_TOP_Y + _ROOT_Y) / 2.0 + 0.004),
    "ForkBossLength": (_FAR_X + 0.034, (_TINE_TOP_Y + _ROOT_Y) / 2.0),
    # Under the fork (#3114). Nearer it, from the datum face: the shank's
    # near face, text left of the datum face. Below that, the shank's
    # thickness across its two faces, text right of the far face. Two rows,
    # so the offset's outside arrow never lies on the thickness's line.
    "ShankFaceNear": (_FACE_X - 0.024, _REF_END_Y - 0.010),
    "ShankThick": (_FAR_X + 0.013, _REF_END_Y - 0.018),
}
# Each tight band links the note naming the mate it serves (rule 4; fan-out
# rounds 1-2: the arm named at both the slot and the tine wall printed twice,
# named at one the other band had none). The tine wall's printed lower limit
# is the tines' known shortfall against the .080 wall target, named TINE
# WALL (rule 20; MHA-CH-03 RV-02). The slot and the walls that locate it link
# note 2 (running fit on the arm). The near tine's band also locates the slot
# from the datum face and, with the far tine's, holds the gap to the next
# channel's rod (#982 review r2). The shank's two dimensions take the title
# block's .XX and fit nothing, so they carry no flag; the ring's two bands
# link note 3 in the side view (LEFT_CALLOUTS).
DETAIL_CALLOUTS = {
    "TineNear": f"2X TINE WALL\nSEE NOTE {SLOT_FIT_NOTE_NUMBER}",
    "SlotWidth": f"SEE NOTE {SLOT_FIT_NOTE_NUMBER}",
}


def _kept_precision(keep: dict[str, tuple[float, float]]) -> dict[str, int]:
    """The part-authored decimal places of the dimensions a view keeps."""
    places = {
        name: digits
        for by_name in DRAWING_PRECISION.values()
        for name, digits in by_name.items()
    }
    return {name: places[name] for name in keep}


BORE_FINISH_EDGE = _sheet_xy(RING_BORE_DIA / 2.0, 0.0)
# At the plate's 2.5 mm character height (the default printed 5 mm and its
# roughness text ran into the detail's lower-left callout, r1 and r2).
BORE_FINISH_SYMBOL = (BORE_FINISH_EDGE[0] + 0.020, BORE_FINISH_EDGE[1] + 0.015)
BORE_FINISH_CHAR_HEIGHT = 0.0025
# Datum A on the strap bore at 5 o'clock, its tag below the ring: at 9
# o'clock its leader lay on the centre distance's witness (r1); inside the
# bore (r2) the tag crowded the two diameters' leaders and the centre lines.
# The edge attachment lands where the tag's leader meets the bore, so the
# tag stands on the pick's ray, between the outer diameter's leader (-55
# deg) and the vertical centre line.
_DATUM_A_ANGLE = math.radians(-72.0)
DATUM_A_EDGE = _sheet_xy(
    RING_BORE_DIA / 2.0 * math.cos(_DATUM_A_ANGLE),
    RING_BORE_DIA / 2.0 * math.sin(_DATUM_A_ANGLE),
)
_DATUM_A_TAG_R = 34.0
DATUM_A_SYMBOL = _sheet_xy(
    _DATUM_A_TAG_R * math.cos(_DATUM_A_ANGLE),
    _DATUM_A_TAG_R * math.sin(_DATUM_A_ANGLE),
)
# Datum B on the shank's left flank. The tag's edge attachment re-solves
# square to the flank, so its leader runs level at the tag's height, 4.5 mm
# above the shank width's dimension line (its text stands right of the shank).
DATUM_B_EDGE = _sheet_xy(-SHANK_WIDTH / 2.0, 100.0)
DATUM_B_SYMBOL = (DATUM_B_EDGE[0] - 0.016, FRONT_KEEP["ShankWidthDim"][1] + 0.0045)
# The .16 BASIC (datum B to the pin axis) runs on the shank, its text out
# to the left: over the pin its line lay on the position FCF's level leader
# and under the ream leader (baseline review); inside the head it crowded
# the hole and the ream callout's leader crossed it (#982 review r3); just
# below the fork root the leader still crossed its right-hand arrow
# (ENFORCE review). Below the ream callout's lowest line the leader, which
# runs up-left from that line to the hole, cannot reach it; above datum B's
# tag. On the shank its arrow lands on the flank itself, datum B's edge.
PIN_OFFSET_TEXT_XY = (0.150, _sheet_xy(0.0, 111.0)[1])
# The .16 BASIC from datum A (the bore axis) to datum B (the shank's left
# flank) completes the frame (ENFORCE review: nothing placed B sideways from
# A): its witness rises from the bore centre up the shank, its text out to
# the left on the shank above the ring, clear over the ring OD's text.
DATUM_B_FROM_A_TEXT_XY = (0.150, _sheet_xy(0.0, 55.0)[1])

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame (_sheet_xy
# and _detail_xy: the strap bore's axis on Z at the origin, the rod up +Y to
# the pin at CENTER_DISTANCE, X across, Z through the thickness with the
# fork's datum face at -Z). Every Z face and the slot locate from that datum
# face; a band is the dimension's own native band, else the title block's row
# for its printed places. The declarations print nothing.
_P = {name: places for by in DRAWING_PRECISION.values() for name, places in by.items()}
_SELF = "draw_ch_connecting_rod"
_SPEC = "ch_connecting_rod_spec"
_NOTES = "ch_connecting_rod_notes"
_FRAME = ((_SELF, "_sheet_xy"), (_SELF, "_detail_xy"))
_Z = (0.0, 0.0, 1.0)
_DATUM_Z = -FORK_THICKNESS / 2.0
_SLOT_HALF = FORK_SLOT_WIDTH / 2.0
_RING_NEAR_Z = _DATUM_Z + RING_FACE_NEAR
_SHANK_NEAR_Z = _DATUM_Z + SHANK_FACE_NEAR
# The rod's one geometric tolerance, the pin hole's position zone (its FCF
# below subscripts the same row): unpacked, so a second row fails here.
(_PIN_POSITION_MM,) = GEOMETRIC_TOLERANCES_MM.values()


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    model_sources=(
        *_FRAME,
        (_SPEC, "CENTER_DISTANCE"),
        (_SPEC, "FORK_THICKNESS"),
        (_SPEC, "RING_OUTER_DIA"),
    ),
    precision_sources=((_NOTES, "DRAWING_PRECISION"),),
)
# The fork's datum face (model -Z, the near tine's outer face): the near
# tine, the slot, the ring's near face and the shank's near face all run from
# it (DETAIL_KEEP, LEFT_KEEP).
requirement(
    "datum_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -_DATUM_Z),),
    requirements=("plane",),
    fields={"plane": (_plane("z", _DATUM_Z), (*_FRAME, (_SPEC, "FORK_THICKNESS")))},
)
# The other faces normal to Z, each one band from the face it runs from: the
# fork over the tines, .240, as their reference sum with its worst-case
# spread (DETAIL_KEEP "ForkThick"); the ring's near face .035 +/-.002 from the
# datum face and its thickness .170 +/-.002 (LEFT_KEEP, note 3: its sliding
# fit in the cam slot); the stepped shank's near face .05 from the datum face
# and its thickness .13, both at the title block's .XX (DETAIL_KEEP).
_Z_FACES = (
    # (feature, z, field, printed dimension, nominal, source, from, keep)
    ("fork_far_face", -_DATUM_Z, "thickness", "ForkThick", FORK_THICKNESS,
     "FORK_THICKNESS", "datum_face", "DETAIL_KEEP"),
    ("ring_near_face", _RING_NEAR_Z, "offset", "RingFaceNear", RING_FACE_NEAR,
     "RING_FACE_NEAR", "datum_face", "LEFT_KEEP"),
    ("ring_far_face", _RING_NEAR_Z + RING_THICKNESS, "thickness", "RingThick",
     RING_THICKNESS, "RING_THICKNESS", "ring_near_face", "LEFT_KEEP"),
    ("shank_near_face", _SHANK_NEAR_Z, "offset", "ShankFaceNear", SHANK_FACE_NEAR,
     "SHANK_FACE_NEAR", "datum_face", "DETAIL_KEEP"),
    ("shank_far_face", _SHANK_NEAR_Z + SHANK_THICKNESS, "thickness", "ShankThick",
     SHANK_THICKNESS, "SHANK_THICKNESS", "shank_near_face", "DETAIL_KEEP"),
)
_Z_BANDS = {
    "ForkThick": FORK_THICKNESS_BAND,
    "RingFaceNear": RING_FACE_BAND,
    "RingThick": RING_THICKNESS_BAND,
    "ShankFaceNear": SHANK_FACE_BAND,
    "ShankThick": SHANK_THICKNESS_BAND,
}
for _name, _z, _field, _dim, _nominal, _source, _from, _keep in _Z_FACES:
    _fields: dict[str, Any] = {
        "plane": (_plane("z", _z), (*_FRAME, (_SPEC, _source))),
        _field: (
            limits(_nominal, _P[_dim], _Z_BANDS[_dim]),
            ((_SPEC, _source), (_SELF, "_Z_BANDS"), (_SELF, _keep)),
        ),
        f"{_field}_nominal": (_nominal, ((_SPEC, _source),)),
        f"{_field}_from": (_from, ((_SELF, _keep),)),
    }
    if _dim in LEFT_CALLOUTS:
        _fields["callout"] = (LEFT_CALLOUTS[_dim], ((_SELF, "LEFT_CALLOUTS"),))
    if _dim == "ForkThick":
        _fields["dimension_type"] = ("reference", ((_SELF, "DETAIL_KEEP"),))
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace((0.0, 0.0, math.copysign(1.0, _z)), abs(_z)),),
        requirements=(_field,),
        fields=_fields,
        precision={_field: _P[_dim]},
    )
# The shank's flanks, .32 apart (FRONT_KEEP "ShankWidthDim"): the left one is
# datum B, .16 BASIC from datum A (DATUM_B_FROM_A_TEXT_XY). Both flanks round
# into the ring's OD and onto the fork's step at 4X R.065, .060-.070 at the
# title block's .XXX (FRONT_KEEP "ShankCornerR"; owner ruling 2026-11-23,
# tool audit Q9), the 1/8 in end mill's radius.
requirement(
    "shank_left_flank",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), SHANK_WIDTH / 2.0),),
    requirements=("plane", "basic_from_a"),
    fields={
        "plane": (_plane("x", -SHANK_WIDTH / 2.0), (*_FRAME, (_SPEC, "SHANK_WIDTH"))),
        "datum": ("B", ((_SELF, "DATUM_B_EDGE"),)),
        "basic_from_a": (
            SHANK_WIDTH / 2.0,
            ((_SPEC, "SHANK_WIDTH"), (_SELF, "DATUM_B_FROM_A_TEXT_XY")),
        ),
    },
)
requirement(
    "shank_right_flank",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), SHANK_WIDTH / 2.0),),
    requirements=("width", "corner_r"),
    fields={
        "plane": (_plane("x", SHANK_WIDTH / 2.0), (*_FRAME, (_SPEC, "SHANK_WIDTH"))),
        "width": (
            limits(SHANK_WIDTH, _P["ShankWidthDim"], unit=UNIT),
            ((_SPEC, "SHANK_WIDTH"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "width_nominal": (SHANK_WIDTH, ((_SPEC, "SHANK_WIDTH"),)),
        "width_from": ("shank_left_flank", ((_SELF, "FRONT_KEEP"),)),
        "corner_r": (
            limits(SHANK_CORNER_R, _P["ShankCornerR"], unit=UNIT),
            ((_NOTES, "SHANK_CORNER_R"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "corner_r_nominal": (SHANK_CORNER_R, ((_NOTES, "SHANK_CORNER_R"),)),
        "corner_count": (SHANK_CORNER_COUNT, ((_NOTES, "DIMENSION_PREFIXES"),)),
        "corner_callout": (SHANK_CORNER_CALLOUT, ((_SELF, "FRONT_CALLOUTS"),)),
    },
    precision={"width": _P["ShankWidthDim"], "corner_r": _P["ShankCornerR"]},
)
# The ring's outside, 1.61 (FRONT_KEEP "RingOuterDia"), concentric with the
# strap bore.
requirement(
    "ring",
    kind="boss",
    faces=(CylinderFace(RING_OUTER_DIA),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, 0.0], _FRAME),
        "axis": (_Z, _FRAME),
        "dia": (
            limits(RING_OUTER_DIA, _P["RingOuterDia"], unit=UNIT),
            ((_SPEC, "RING_OUTER_DIA"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "dia_nominal": (RING_OUTER_DIA, ((_SPEC, "RING_OUTER_DIA"),)),
        # Covered material, for the stock check: no face bounds Y, and the
        # ring is the widest across X.
        "extent_x": (
            [-RING_OUTER_RADIUS, RING_OUTER_RADIUS],
            ((_SPEC, "RING_OUTER_RADIUS"),),
        ),
        "extent_y": (
            [-RING_OUTER_RADIUS, RING_OUTER_RADIUS],
            ((_SPEC, "RING_OUTER_RADIUS"),),
        ),
    },
    precision={"dia": _P["RingOuterDia"]},
)
# The fork's outside: its flanks .39 apart with the full-round crown on the
# pin (FRONT_KEEP "ForkWidthDim", FULL R) and the boss's underside .71 below
# the crown top (DETAIL_KEEP "ForkBossLength"). The overall length, ring
# bottom to crown top, is a reference (OVERALL_TEXT_XY).
requirement(
    "fork",
    kind="profile",
    faces=(
        PlanarFace((1.0, 0.0, 0.0), FORK_WIDTH / 2.0),
        PlanarFace((-1.0, 0.0, 0.0), FORK_WIDTH / 2.0),
        CylinderFace(FORK_WIDTH),
        PlanarFace((0.0, -1.0, 0.0), -FORK_BASE_Y),
    ),
    requirements=("width", "boss_length"),
    fields={
        "width": (
            limits(FORK_WIDTH, _P["ForkWidthDim"], unit=UNIT),
            ((_SPEC, "FORK_WIDTH"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "width_nominal": (FORK_WIDTH, ((_SPEC, "FORK_WIDTH"),)),
        "callout": (FRONT_CALLOUTS["ForkWidthDim"], ((_SELF, "FRONT_CALLOUTS"),)),
        "crown_at": ([0.0, CENTER_DISTANCE, 0.0], ((_SPEC, "CENTER_DISTANCE"),)),
        "boss_length": (
            limits(FORK_TOP_Y - FORK_BASE_Y, _P["ForkBossLength"], unit=UNIT),
            ((_SPEC, "FORK_BASE_BELOW_PIN"), (_SPEC, "UNIT"), (_SELF, "DETAIL_KEEP")),
        ),
        "boss_length_nominal": (
            FORK_TOP_Y - FORK_BASE_Y,
            ((_SPEC, "FORK_BASE_BELOW_PIN"),),
        ),
        "overall_length_ref": (
            OVERALL_LENGTH,
            ((_SPEC, "FORK_TOP_Y"), (_SPEC, "RING_BOTTOM_Y"), (_SELF, "OVERALL_LENGTH")),
        ),
        # Covered material: the fork from its boss's underside to the crown.
        "extent_x": ([-FORK_WIDTH / 2.0, FORK_WIDTH / 2.0], ((_SPEC, "FORK_WIDTH"),)),
        "extent_y": ([FORK_BASE_Y, FORK_TOP_Y], ((_SPEC, "FORK_BASE_Y"), (_SPEC, "FORK_TOP_Y"))),
    },
    precision={"width": _P["ForkWidthDim"], "boss_length": _P["ForkBossLength"]},
)
# The slot between the tines: its two walls and its floor. The near tine
# .067 +/-.002 from the datum face locates it; the slot .106 +/-.002; the far
# tine the same size from the far face (2X TINE WALL); its depth .58 from the
# crown top; its floor corners at the title block's INSIDE CORNERS R.040 MAX
# (DETAIL_KEEP, DETAIL_CALLOUTS, note 2).
_TINE = limits(TINE_THICKNESS, _P["TineNear"], TINE_BAND)
_DETAIL = ((_SELF, "DETAIL_KEEP"), (_SELF, "DETAIL_CALLOUTS"))
requirement(
    "fork_slot",
    kind="slot",
    faces=(
        PlanarFace(_Z, -_SLOT_HALF),
        PlanarFace((0.0, 0.0, -1.0), -_SLOT_HALF),
        PlanarFace((0.0, 1.0, 0.0), FORK_CROTCH_Y),
    ),
    requirements=("width", "near_tine", "far_tine", "depth", "corner_radius_max"),
    fields={
        "open_to": ("crown", _FRAME),
        "thru": (True, _DETAIL),
        "width": (
            limits(FORK_SLOT_WIDTH, _P["SlotWidth"], FORK_SLOT_BAND),
            ((_SPEC, "FORK_SLOT_WIDTH"), (_SPEC, "FORK_SLOT_BAND"), *_DETAIL),
        ),
        "width_nominal": (FORK_SLOT_WIDTH, ((_SPEC, "FORK_SLOT_WIDTH"),)),
        "near_tine": (_TINE, ((_SPEC, "TINE_THICKNESS"), (_SPEC, "TINE_BAND"), *_DETAIL)),
        "near_tine_nominal": (TINE_THICKNESS, ((_SPEC, "TINE_THICKNESS"),)),
        "near_tine_from": ("datum_face", _DETAIL),
        "far_tine": (_TINE, ((_SPEC, "TINE_THICKNESS"), (_SPEC, "TINE_BAND"), *_DETAIL)),
        "far_tine_nominal": (TINE_THICKNESS, ((_SPEC, "TINE_THICKNESS"),)),
        "far_tine_from": ("fork_far_face", _DETAIL),
        "depth": (
            limits(FORK_TOP_Y - FORK_CROTCH_Y, _P["SlotDepth"], unit=UNIT),
            ((_SPEC, "FORK_CROTCH_BELOW_PIN"), (_SPEC, "UNIT"), *_DETAIL),
        ),
        "depth_nominal": (FORK_TOP_Y - FORK_CROTCH_Y, ((_SPEC, "FORK_CROTCH_BELOW_PIN"),)),
        "depth_from": ("fork", _DETAIL),
        "corner_radius_max": (
            inside_corner_radius_mm(unit=UNIT),
            (("_printed_tolerance", "inside_corner_radius_mm"), (_SPEC, "UNIT")),
        ),
        "tine_callout": (DETAIL_CALLOUTS["TineNear"], _DETAIL),
        "width_callout": (DETAIL_CALLOUTS["SlotWidth"], _DETAIL),
    },
    precision={
        "width": _P["SlotWidth"],
        "near_tine": _P["TineNear"],
        "far_tine": _P["TineNear"],
        "depth": _P["SlotDepth"],
    },
)
# The strap bore (datum A): 1.213 +.003/.000, Ra, running on the cam
# (FRONT_KEEP "StrapBoreDia").
requirement(
    "strap_bore",
    kind="hole",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "strap_bore").face,),
    requirements=("dia", "thru", "finish_ra", "process"),
    fields={
        "at": ([0.0, 0.0, 0.0], _FRAME),
        "axis": (_Z, _FRAME),
        "dia": (
            limits(RING_BORE_DIA, _P["StrapBoreDia"], RING_BORE_DIA_BAND),
            ((_SPEC, "RING_BORE_DIA"), (_SPEC, "RING_BORE_DIA_BAND"), (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (RING_BORE_DIA, ((_SPEC, "RING_BORE_DIA"),)),
        "thru": (True, ((_SELF, "FRONT_CALLOUTS"),)),
        "process": ("bore", ((_SELF, "FRONT_CALLOUTS"),)),
        "finish_ra": (MACHINED_UM, ((_SPEC, "SURFACE_FINISHES"),)),
        "datum": ("A", ((_SELF, "DATUM_A_EDGE"),)),
        "callout": (FRONT_CALLOUTS["StrapBoreDia"], ((_SELF, "FRONT_CALLOUTS"),)),
    },
    precision={"dia": _P["StrapBoreDia"], "finish_ra": 1},
)
# The reamed press hole through both tines on the rod axis: the .0775
# reamer's size, no band, and REAM THRU / SEE NOTE 1 (owner ruling
# 2026-11-24, fit audit question 3), at the BASIC centre distance from A and
# .16 BASIC from B, inside a diameter-.014 position zone to A and B. "dia" is
# the spec's ANALYSIS band (what the reamer is modelled to cut), not a
# printed limit.
requirement(
    "pin_hole",
    kind="hole",
    faces=(CylinderFace(PIN_HOLE_DIA),),
    requirements=("dia", "thru", "process", "position_dia"),
    fields={
        "at": ([0.0, CENTER_DISTANCE, 0.0], ((_SPEC, "CENTER_DISTANCE"),)),
        "axis": (_Z, _FRAME),
        "dia": (
            list(PIN_HOLE_LIMITS),
            ((_SPEC, "PIN_HOLE_LIMITS"), (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (PIN_HOLE_DIA, ((_SPEC, "PIN_HOLE_DIA"),)),
        "thru": (True, ((_SELF, "FRONT_CALLOUTS"),)),
        "process": ("ream", ((_SELF, "FRONT_CALLOUTS"),)),
        "callout": (FRONT_CALLOUTS["PinHoleDia"], ((_SELF, "FRONT_CALLOUTS"),)),
        "press_fit_on": (PIN_NUMBER, ((_NOTES, "PIN_NUMBER"),)),
        "basic_from_a": (
            CENTER_DISTANCE,
            ((_SPEC, "CENTER_DISTANCE"), (_SELF, "CENTRE_DISTANCE_PLACES")),
        ),
        "basic_from_b": (
            SHANK_WIDTH / 2.0,
            ((_SPEC, "SHANK_WIDTH"), (_SELF, "PIN_OFFSET_TEXT_XY")),
        ),
        "position_dia": (
            _PIN_POSITION_MM,
            ((_SPEC, "GEOMETRIC_TOLERANCES_MM"), (_SPEC, "GEOMETRIC_TOLERANCES_IN")),
        ),
        "position_datums": (["A", "B"], ((_SELF, "build"),)),
    },
    precision={"dia": _P["PinHoleDia"]},
)


def _fork_detail(adapter: Any, left: Any) -> Any:
    """DETAIL C: a native 3:1 detail of the side view's fork."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(left, "IView")
    if not drawing.ActivateView(view_name(adapter, left)):
        raise RuntimeError("failed to activate the fork detail's parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        left,
        (0.0, DETAIL_FENCE_Y_MM / 1000.0, 0.0),
        label="fork detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    # ENFORCE farm runs: an inferred circle snapped in screen space (a 12.4
    # and then a 9.7 mm fence, each off the rod axis), so the detail's fork
    # wandered under its fixed texts and their lines struck them. The fence
    # goes straight to the database and is read back before the detail
    # selects it (draw_dt_pinion_lever._hub_detail's recipe).
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError("failed to create the fork detail fence")
    placed_centre, placed_radius = native_circle_geometry(fence, label="fork detail fence")
    if math.dist(placed_centre[:2], points[0][:2]) > 1e-9 or not math.isclose(
        placed_radius, math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError("the fork detail fence moved from where it was placed")
    draw.ClearSelection2(True)
    if not _early_bound(fence, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select the fork detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "C",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create the fork detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    # A fresh detail's display geometry can lag its creation
    # (_drawing_detail_projection): refresh it before its outline places it.
    detail.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("the fork detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position the fork detail")
    draw.EditRebuild3()
    # DETAIL_KEEP assumes the fence centre (on the rod axis) prints at
    # DETAIL_CENTER: read it back through the settled detail.
    settle_detail_projection(
        adapter,
        detail,
        (0.0, DETAIL_FENCE_Y_MM / 1000.0, 0.0),
        ink_xy=DETAIL_CENTER,
        tolerance_xy=(DETAIL_PLACEMENT_TOL_M, DETAIL_PLACEMENT_TOL_M),
        label="fork detail fence centre",
    )
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position the fork detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"the fork detail label did not persist: {actual}")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one detail circle on the side view, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    circle.SetLabelPosition(*DETAIL_LETTER_XY)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in circle.GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, DETAIL_LETTER_XY) > 1e-8:
        raise RuntimeError(f"the detail circle's letter did not persist: {letter}")
    return detail


def _land_shank_corner_leader(adapter: Any, annotations: list[Any]) -> None:
    """Carry ShankCornerR's leader onto the corner it measures.

    SolidWorks ends a radial leader at the circle point facing its text and
    does not carry it through the centre; the 4X R.065 text stands up-right
    of the ring, off the corner's arc, so the arrow met the circle in air
    (farm r1 of #3445). ``ArcExtensionLineOrOppositeSide`` True draws the
    arc's extension out to that point (draw_mg_magnifying_vertical_rod's
    relief roots)."""
    found = [a for a in annotations if dimension_name(adapter, a) == "ShankCornerR"]
    if len(found) != 1:
        raise RuntimeError(f"expected one ShankCornerR dimension, found {len(found)}")
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported shank corner radius is not radial")
    display.ArcExtensionLineOrOppositeSide = True
    if not bool(display.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("ShankCornerR refused its arc extension line")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open connecting-rod source", adapter.open_model(str(SOURCE)))
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
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-connecting-rod"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Connecting Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting rod; 1018 steel; fork and cam strap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    # The 1:1 left view (third angle: placed LEFT of the front) shows the
    # stepped thicknesses -- the .170 ring, the .13 shank inside both its
    # faces, and the .240 fork split by its slot into two tines -- and carries
    # DETAIL C's circle. The right-hand column belongs to the title block, so
    # the side view lives on the left.
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, left, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Each view imports only features whose marked dimensions it keeps: the
    # side view the ring's reference sketch (RingFaceReference, shown in this
    # view alone) and the ring, the detail the fork's and the shank's.
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _fork_detail(adapter, left)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="fork detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The bands import with their named model dimensions, at the part's
    # places; the drawing owns only the callout text beneath them.
    assert_imported_precision(
        adapter,
        front_annotations,
        DRAWING_PRECISION["PinHoleProfile"],
    )
    assert_imported_precision(
        adapter, front_annotations, DRAWING_PRECISION["ShankCorners"]
    )
    assert_imported_precision(adapter, left_annotations, _kept_precision(LEFT_KEEP))
    assert_imported_precision(
        adapter, detail_annotations, _kept_precision(DETAIL_KEEP)
    )
    set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)
    set_dimension_callouts(adapter, left_annotations, LEFT_CALLOUTS)
    set_dimension_callouts(adapter, detail_annotations, DETAIL_CALLOUTS)
    # Native, both ring diameters ran rim to rim through the bore's centre and
    # crossed there, under datum A's leader (#982 review r2): one arrow each on
    # the rim nearest its text keeps the bore clear.
    for name in NEAR_SIDE_DIAMETERS:
        matches = [
            annotation
            for annotation in front_annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"ring {name}")
    _land_shank_corner_leader(adapter, front_annotations)
    rebuild_drawing(adapter, label="ring diameters' and shank corner leaders")
    # Two tines and the slot set the fork over the tines: it prints as a
    # reference.
    fork_thick = [
        annotation
        for annotation in detail_annotations
        if dimension_name(adapter, annotation) == "ForkThick"
    ]
    if len(fork_thick) != 1:
        raise RuntimeError("fork detail does not carry exactly one fork thickness")
    set_reference_dimension(adapter, fork_thick[0], label="fork over the tines")
    # Overall length, ring bottom to crown top: the side view's two
    # horizontal silhouettes, so the dimension is their plain distance (two
    # circle picks in the front view would dimension centre to centre).
    picks = model_points_in_view(
        adapter,
        left,
        [
            tuple(v / 1000.0 for v in point)
            for point in (OVERALL_BOTTOM_MM, OVERALL_TOP_MM)
        ],
        label="overall length picks",
        names=tuple(OVERALL_FACES),
    )
    silhouettes = face_silhouettes_through(
        adapter,
        left,
        {
            key: (face, xy)
            for (key, face), xy in zip(OVERALL_FACES.items(), picks, strict=True)
        },
        label="overall length",
    )
    ends = tuple(silhouettes[key] for key in OVERALL_FACES)
    overall = add_edge_dimension(
        adapter,
        left,
        p0=picks[0],
        p1=picks[1],
        text_xy=OVERALL_TEXT_XY,
        label="overall length",
        orientation="vertical",
        entity_type="SILHOUETTE",
        entities=ends,
    )
    assert_dimension_measures(
        adapter,
        overall,
        expected_mm=OVERALL_LENGTH,
        label="overall length",
        entities=ends,
        entity_types=("SILHOUETTE", "SILHOUETTE"),
    )
    overall = _early_bound(overall, "IDisplayDimension")
    set_reference_dimension(adapter, overall.GetAnnotation(), label="overall length")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    # Centre distance: ring bore edge to the rocker-pin bore edge (SolidWorks
    # dimensions circle edges centre-to-centre); box it BASIC.  Pick each bore's
    # LEFT rim -- the pin bore is tiny and sits inside the fork crown, so a TOP
    # pick snapped to the crown arc (read 145.07); the left rim is on the pin
    # circle, clear of the wider crown.
    ring_rim = _sheet_xy(-RING_BORE_DIA / 2.0, 0.0)
    pin_rim = _sheet_xy(-_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    centre_distance = add_edge_dimension(
        adapter,
        front,
        p0=ring_rim,
        p1=pin_rim,
        text_xy=(0.125, FRONT_CENTER[1]),
        label="rod centre distance",
    )
    assert_dimension_measures(
        adapter,
        centre_distance,
        expected_mm=CENTER_DISTANCE,
        label="rod centre distance",
    )
    # A sheet-made dimension takes the document's two places (6.24, .005 in
    # off the closure, most of the pin's Ø.014 zone's radius); it prints at
    # CENTRE_DISTANCE_PLACES, read back.
    set_dimension_display_precision(
        adapter,
        "front view",
        "rod centre distance",
        CENTRE_DISTANCE_PLACES,
        display=centre_distance,
    )
    set_basic_dimension(adapter, centre_distance, label="rod centre distance")

    # Datum A on the strap bore axis (picked at 5 o'clock, the tag below the
    # ring), Ra on the bore at 3 o'clock, and a position FCF tying the rocker
    # pin hole to A.
    add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_A_EDGE,
        symbol_xy=DATUM_A_SYMBOL,
        datum="A",
        label="strap bore axis",
    )
    # Datum B: the shank's left flank.  A alone leaves rotation about the bore
    # axis unconstrained, so the pin-hole position (and the centre distance's
    # direction) could not be inspected; B clocks the rod, the .16 BASIC from
    # A places B, and the .16 BASIC from B places the pin on the shank
    # centreline.
    add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_B_EDGE,
        symbol_xy=DATUM_B_SYMBOL,
        datum="B",
        label="shank left flank",
    )
    # Both .16 BASICs run from the flank to a circle's CENTRE (datum A's bore,
    # the pin's axis), set explicitly rather than left to the arc condition the
    # pick resolves to. Value-only: both picks are coordinate hits.
    datum_b_offset = add_edge_dimension(
        adapter,
        front,
        p0=DATUM_B_EDGE,
        p1=ring_rim,
        text_xy=DATUM_B_FROM_A_TEXT_XY,
        label="datum B from datum A",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, datum_b_offset, label="datum B from datum A")
    assert_dimension_measures(
        adapter,
        datum_b_offset,
        expected_mm=SHANK_WIDTH / 2.0,
        label="datum B from datum A",
    )
    set_basic_dimension(adapter, datum_b_offset, label="datum B from datum A")
    pin_offset = add_edge_dimension(
        adapter,
        front,
        p0=DATUM_B_EDGE,
        p1=pin_rim,
        text_xy=PIN_OFFSET_TEXT_XY,
        label="pin C/L from shank flank",
        orientation="horizontal",
    )
    set_arc_endpoints_to_center(adapter, pin_offset, label="pin C/L from shank flank")
    assert_dimension_measures(
        adapter,
        pin_offset,
        expected_mm=SHANK_WIDTH / 2.0,
        label="pin C/L from shank flank",
    )
    set_basic_dimension(adapter, pin_offset, label="pin C/L from shank flank")
    add_surface_finish(
        adapter,
        front,
        edge_xy=BORE_FINISH_EDGE,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "strap_bore"),
        label="strap bore finish",
        char_height=BORE_FINISH_CHAR_HEIGHT,
    )
    # The position FCF attaches at the reamed pin hole's 3-o'clock rim with a
    # level leader, above the Ø callout's lane.
    pin_fcf_rim = _sheet_xy(_PIN_HOLE_DIA / 2.0, CENTER_DISTANCE)
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=pin_fcf_rim,
        frame_xy=(0.222, 0.222),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["rocker pin hole position"],
        datums=("A", "B"),
        diameter=True,
        label="rocker pin hole position",
    )

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Connecting Rod Manufacturing Drawing",
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
