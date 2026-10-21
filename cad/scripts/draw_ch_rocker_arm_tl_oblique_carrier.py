r"""Create the drawing for the oblique-trammel jig's carrier plate (MHA-CH-06-TL-21).

The top view at 1:2 carries the outline, the reamed pin holes, the two
centre-drill spots and every tap station. Position chains: X from the HUB
spot's axis (the plate's centreline, 260.0 from the left end), A1 by 225.07
from it and B1 from A1 by the spacing; Y from the A1-B1 pin line (the reamed
pair's own axes), 45.00 above the -Y edge. Every location dimension stands
outside the outline in its own lane: X stations above and below, Y stations
left and right, so no extension line crosses a text.
Section A-A at 3:1 cuts along the pin line, is cropped to A1, and carries
the finished thickness and underside chamfer. A native reference dimension
measures the actual straight bore wall; its own callout requires 10.50 MIN.
The real underside edge is identified in the section. The complete resultant
axis-shift acceptance belongs to the native 4X REAM callout, not a separate
leader. Native geometry readbacks use that underside plane's normal for all
four bore-axis vectors. The shaded isometric stands above the title block.

One sheet holds it: the left lanes need ~75 mm of the 79 between the outline
and the border, the right lanes ~63 of 67.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    curate_dimensions,
    dimension_name,
    place_view,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _early_bound
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _drawing_common import (
    rebuild_drawing,
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_detail_projection import settle_detail_projection
import _drawing_hidden_sketches as hidden_sketches
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_carrier_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_face import unit_vector
from _gtol_face_read import face_geometry
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_oblique_carrier_spec import (
    CALLOUT_PREFIXES,
    CALLOUT_SUFFIXES,
    CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_carrier"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 520 x 130 x 12 plate: 1:2 puts the top view at 260 x 65 across the sheet
# (B landscape: border 12.7..419.1 x 12.7..266.7, title block x >= 216 and
# y <= 65). The outline lands on sheet x 92..352, y 152.5..217.5.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
ISO_SCALE = part_spec.ISOMETRIC_VIEW_SCALE
TOP_CENTER = (0.222, 0.185)
# The iso (~58 x 34 mm at 1:8) right of section A-A and its note under it,
# both above the title block (jig-r3: the note ran into it).
ISO_CENTER = (0.386, 0.103)
ISO_NOTE_XY = (0.356, 0.082)


def _xy(x: float, y: float) -> tuple[float, float, float]:
    """Carrier (X, Y) on the top face as model mm (model Z = -carrier Y)."""
    return (x, 0.0, -y)


# Dimension lanes, carrier mm (1:2: sheet x = 222 + X/2, y = 175 + Y/2). Y
# stations stand left (-X half) and right (+X half), ~17-19 apart (8.5-9.5 on
# the sheet: a multi-row text beside its lane and its clearance), the
# 3-row riser and pin-chain texts on the outward side. X stations stand above
# and below, each text in a gap of the other lanes' extension lines. Carrier
# r11: the 45.53 HUB and 44.287 riser extension lines ran 0.62 apart on the
# left and the 130.0 width's line ran through the B2DY text, so HUB moved to
# the right lanes, the width innermost and B2DY beside it, and the riser
# stations name the riser (RISER_STATION_CALLOUT). Carrier r13: the CL 29.35
# text (centred on its lane, 12.9 wide) touched the outline at x 92, so its
# lane stands at x 83 and A2DY's at 74.5, the text 2 clear of both.
_LEFT = (-278.0, -295.0, -312.0, -329.0, -350.0)  # sheet x 83 .. 47
_RIGHT = (279.0, 298.0, 317.0, 336.0, 355.0, 374.0)  # sheet x 361.5 .. 409
_A1 = part_spec.PIN_HOLES["A1"]
# Every text position is a MODEL point (mm), mapped onto its view at run time.
# A horizontal dimension's last row stands on its lane, its rows stacking up
# 5.56 sheet mm apart, so a keep Y below is the lane plus its rows.
TOP_KEEP: dict[str, tuple[float, float, float]] = {
    # Outline: the length outermost below, the HUB axis from the left end
    # below the pin chain, the width innermost right, the pin line from the
    # -Y edge outermost left.
    "PlateLength": _xy(56.0, -194.4),  # lane y 75
    "PlateHalfLength": _xy(-164.0, -149.4),  # lane y 97.5
    "PlateWidth": _xy(_RIGHT[0], -8.0),
    "PlateNearY": _xy(_LEFT[4], -24.0),
    # The pin chain: A1 from the HUB axis, B1 from A1, A2/B2 from A1/B1.
    "A1X": _xy(-112.0, -136.4),  # lane y 104
    "PinSpacing": _xy(172.0, -170.3),  # lane y 81.5
    "A2DX": _xy(-193.0, 110.7),  # lane y 222
    # Review 88c6d (r1/r2/r3.clarity.1): centred on its 3.6 mm span, B2DX's
    # three rows were struck by both B1/B2 extension lines. Its rows stand
    # wholly outboard of them and of the 520.0's +X extension line (sheet x
    # 352), text ~358..386 x 131..147, above the isometric (top ~121) and
    # below the 130.0's lower extension line (152.5); only its dimension line
    # runs out under the text, crossing extension lines (rule 14 allows).
    "B2DX": _xy(300.0, -72.0),
    # Carrier r11: A2DY's text crossed the top border; it stands ~17 under it.
    "A2DY": _xy(_LEFT[1], 139.0),
    "B2DY": _xy(_RIGHT[1], 70.7),
    "PinHoleDia": _xy(-332.0, -74.3),
    # The spots: each its own diameter callout; HUB by Y right, CL by X
    # below and Y left.
    "SpotDia": _xy(50.0, 98.0),
    "SpotDiaCl": _xy(-190.0, 142.0),
    # Carrier r13: a single-row text within its span stands clear of both
    # arrows (3.56 long): at y 192 the 45.53's top arrow ran into it and at
    # 161.5 the 38.00's bottom arrow struck it. HUB's text is at y 189, 3.7
    # over CR's (181.5); the 38.00's at 163.5, 2.5 under the 22.00's (169.5).
    "HubY": _xy(_RIGHT[3], 28.0),
    "ClX": _xy(-204.0, -87.4),  # lane y 128.5, its text left of CL
    "ClY": _xy(_LEFT[0], 14.0),
    # The taps: the riser stations above and below in the gaps of the pin
    # chain's lines, their Y stations left; CR and the levers right.
    "CrX": _xy(80.0, -54.4),  # lane y 145
    "CrY": _xy(_RIGHT[2], 13.0),
    "RiserX1": _xy(46.0, 129.0),  # lane y 231.2
    "RiserX1R": _xy(-45.0, -111.3),  # lane y 111
    "RiserY1": _xy(_LEFT[3], 65.8),
    "RiserX2": _xy(-60.0, 160.7),  # lane y 247
    "RiserX2R": _xy(165.0, -91.3),  # lane y 121
    "RiserY2": _xy(_LEFT[2], 102.4),
    "LeverY1": _xy(_RIGHT[4], -11.0),
    "LeverY2": _xy(_RIGHT[5], -23.0),
}

# Section A-A along the pin line (model Z = 0), at 3:1, +Y up, its cut
# direction SolidWorks' own, cropped to A1's slab. It is a FULL section: the
# carrier-diag farm probe (run 20261017T063649278Z) measured that the PARTIAL
# section through a short interior line imports nothing at all (no marked
# dimension even from the entire model; selected SectionReference or Plate
# through the base view: an empty array), while a full section through the
# same line, same selection, imports PinChamferSize and StockThick. A full
# section's line must still cross the part: through that 18 mm interior line
# carrier r11 printed the slab uncut (unhatched, no bore), its stock
# extension lines ~800 mm long over the iso and the title block
# (_drawing_sections.create_section_view: a short line does not close the
# cut). So the line runs past both plate ends: its right end (sheet x 415)
# beyond the right lanes, its left (x 51) between the two outer left lanes.
# A full section at 3:1 is 1.6 m wide, so a Crop2 fence keeps the cut's own
# span (fr_nameplate's _crop_section). The finished thickness is the native
# SectionReference StockThick dimension (driven from Plate's depth). Its dimensions
# are imported BEFORE the crop: cropped (jig-r9, c4-r4), the same import
# delivered PinChamferSize but not StockThick, whose stock line stands 0.5 mm
# inside the fence's +X end and whose sketch text stands 5 mm past it.
# Already imported, they are placed again once the cropped view is centred.
# Carrier r11 and r13 printed the 12.0's extension lines from ~863 mm right
# of the slab (over the title block, past the border) wherever the view and
# its text stood, so the thickness text stands on A1's -X side and its
# extension lines are capped (STOCK_WITNESS_MAX_M, draw_dt_pinion_cam's
# _limit_witness_lines) to run from its dimension line to just short of the
# slab's -X end: from that side an origin anywhere at A1's +X side, the far
# one or the true stock line, leaves the same short pair.
SECTION_SCALE = (3, 1)
_SECTION_HALF = part_spec.SECTION_HALF_SPAN  # about A1's axis, model mm
_SECTION_LINE_X = (386.0, -342.0)  # carrier X, +X end first
SECTION_LINE_MODEL_MM = tuple((x, 0.0, 0.0) for x in _SECTION_LINE_X)
# The crop fence's corners, model mm on the cut plane: the cut's span, the
# stock's thickness and 1 mm above and below it.
SECTION_CROP_MODEL_MM = (
    (_A1[0] - _SECTION_HALF, -part_spec.THICKNESS - 1.0, 0.0),
    (_A1[0] + _SECTION_HALF, 1.0, 0.0),
)
_SECTION_ANCHOR_MM = (_A1[0], -part_spec.THICKNESS / 2.0, 0.0)
# Carrier r13 (4:1) squeezed the slab between the 260.0/520.0 lanes and the
# border, its caption cut off from it by the 520.0's extension line and the
# chamfer text against the border. At 3:1 the band under the bottom lanes
# (75) holds, left to right on one row: the caption (x ~20..66), the
# thickness text (lane x 79), the slab (91..145 x 27..63) and the chamfer
# text (~150..209, left of the title block at x 216).
SECTION_CENTER = (0.118, 0.045)
_STOCK_TEXT_DX = 13.0  # A1's axis to the thickness lane, model mm (-X side)
SECTION_KEEP_MODEL_MM: dict[str, tuple[float, float, float]] = {
    "StockThick": (_A1[0] - _STOCK_TEXT_DX, -part_spec.THICKNESS / 2.0, 0.0),
    # 20.5 mm beside A1's axis on the +X side (61.5 on the sheet), clear of
    # the slab: the text block ~150..209 x 24..46, its dimension line (the
    # last row's lane) 3 mm under the underside, running back under the slab
    # to the -X chamfer.
    "PinChamferSize": (_A1[0] + 20.5, -part_spec.THICKNESS + 2.7, 0.0),
}
# The thickness's extension lines from its lane (4 model mm, 12 sheet mm,
# outside the slab's -X end) stop 1.5 sheet mm short of the slab: sheet m.
STOCK_WITNESS_MAX_M = (
    (_STOCK_TEXT_DX - _SECTION_HALF) * SECTION_SCALE[0] / SECTION_SCALE[1] - 1.5
) / 1000.0
# Top centre of the caption: left of the thickness text, level with the slab.
SECTION_CAPTION_XY = (0.043, 0.052)

# Sheet metres: each callout block's centre; its leader lands on the near end
# of the first line. CR up-right into the margin above the right lanes; the
# risers from the outermost +X screw straight up, right of the HUB callout,
# their four rows (the native two and RISER_TAP_CALLOUT's two) ~238..258,
# under the border; the feed lever (the -Y hole) down-left, its three rows
# (with LEVER_TAP_CALLOUT) between the CrX and ClX lanes.
CR_CALLOUT_XY = (0.377, 0.230)
# The riser callout 2 mm right of jig-r10's 0.310: its leader from riser
# screw 4 then passes clear right of the Ø3.00 spot text.
RISER_CALLOUT_XY = (0.312, 0.248)
LEVER_CALLOUT_XY = (0.179, 0.143)

part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
)

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
    requirements=("length", "width"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "length": (limits(part_spec.PLATE_LENGTH, 1), ("PLATE_LENGTH", "OUTLINE_X")),
        "length_nominal": (part_spec.PLATE_LENGTH, ("PLATE_LENGTH",)),
        "width": (limits(part_spec.PLATE_WIDTH, 1), ("PLATE_WIDTH", "OUTLINE_Y")),
        "width_nominal": (part_spec.PLATE_WIDTH, ("PLATE_WIDTH",)),
    },
    precision={"length": 1, "width": 1},
)

requirement(
    "bottom_face",
    kind="face",
    # PlanarFace.offset_mm is n·p: the underside (y = -12) along -Y is +12.
    faces=(PlanarFace((0.0, -1.0, 0.0), part_spec.THICKNESS),),
    requirements=("height",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": -part_spec.THICKNESS},
            ("THICKNESS",),
        ),
        "height": (limits(part_spec.THICKNESS, 1), ("THICKNESS",)),
        "height_nominal": (part_spec.THICKNESS, ("THICKNESS",)),
    },
    precision={"height": 1},
)

# The pin chain's tight bands, each on its printed (rounded) nominal: B1 from
# A1 by the spacing; A2/B2 from A1/B1 by (dX, dY).
_BAND = (part_spec.POSITION_BAND, -part_spec.POSITION_BAND)
_D1 = round(part_spec.D1, 3)
_DX = round(abs(part_spec.A2_DX), 3)
_DY = round(part_spec.A2_DY, 3)
# A1 from the HUB axis (the X datum) at the title block's .XX band.
_A1X = round(abs(_A1[0]), 2)
_CHAIN: dict[str, dict[str, tuple[Any, tuple[Any, ...]]]] = {
    "A1": {
        "station": (limits(_A1X, 2), ("PIN_HOLES",)),
        "station_nominal": (_A1X, ("PIN_HOLES",)),
    },
    "B1": {
        "station": (limits(_D1, 3, _BAND), ("D1", "POSITION_BAND")),
        "station_nominal": (_D1, ("D1",)),
        "parent": ("pin_hole_a1", ("PIN_HOLES",)),
    },
}
for _key, _base in (("A2", "a1"), ("B2", "b1")):
    _CHAIN[_key] = {
        "station": (limits(_DX, 3, _BAND), ("A2_DX", "POSITION_BAND")),
        "station_nominal": (_DX, ("A2_DX",)),
        "parent": (f"pin_hole_{_base}", ("PIN_HOLES",)),
        "height": (limits(_DY, 3, _BAND), ("A2_DY", "POSITION_BAND")),
        "height_nominal": (_DY, ("A2_DY",)),
        "height_from": (f"pin_hole_{_base}", ("PIN_HOLES",)),
    }

for _key, (_x, _y) in part_spec.PIN_HOLES.items():
    _chain = _CHAIN[_key]
    requirement(
        f"pin_hole_{_key.lower()}",
        kind="hole",
        faces=(
            CylinderFace(part_spec.PIN_HOLE_DIA, contains_x_mm=_x, contains_z_mm=-_y),
        ),
        requirements=(
            "dia",
            "thru",
            "note",
            *(name for name in ("station", "height") if name in _chain),
        ),
        fields={
            "at": ([_x, 0.0, -_y], ("PIN_HOLES",)),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "dia": (
                limits(part_spec.PIN_HOLE_DIA, 3, part_spec.PIN_HOLE_BAND),
                ("PIN_HOLE_DIA", "PIN_HOLE_BAND"),
            ),
            "dia_nominal": (part_spec.PIN_HOLE_DIA, ("PIN_HOLE_DIA",)),
            "thru": (True, ("PIN_HOLE_CALLOUT",)),
            "note": (
                " ".join(
                    (
                        part_spec.CALLOUTS_BELOW["PinHoleDia"]
                        + "\n"
                        + part_spec.PIN_LAND_CALLOUT
                    ).splitlines()
                ),
                (
                    "CALLOUTS_BELOW",
                    "PIN_HOLE_CALLOUT",
                    "PIN_MATE",
                    "PIN_AXIS_CALLOUT",
                    "PIN_LAND_CALLOUT",
                    "PIN_AXIS_DEVIATION_MAX",
                    "PIN_AXIS_MEASUREMENT_SPAN",
                ),
            ),
            **_chain,
        },
        precision={
            "dia": 3,
            **{
                name: 2 if _key == "A1" else 3
                for name in ("station", "height")
                if name in _chain
            },
        },
    )

for _prefix, (_x, _y) in part_spec.SPOTS.items():
    requirement(
        f"{_prefix.lower()}_spot",
        kind="seat",
        faces=(ConeFace(part_spec.SPOT_ANGLE / 2.0, contains_x_mm=_x),),
        # The printed stations are inspected too (Codex #1582).
        requirements=("dia", "angle_deg", "station", "height"),
        fields={
            "at": ([_x, 0.0, -_y], ("SPOTS", "HUB", "CL")),
            "dia": (limits(part_spec.SPOT_DIA, 2), ("SPOT_DIA",)),
            "dia_nominal": (part_spec.SPOT_DIA, ("SPOT_DIA",)),
            "angle_deg": (part_spec.SPOT_ANGLE, ("SPOT_ANGLE", "CALLOUT_SUFFIXES")),
            "station": (limits(round(_x, 2), 2), ("SPOTS",)),
            "height": (limits(round(_y, 2), 2), ("SPOTS",)),
        },
        precision={"dia": 2, "angle_deg": 0, "station": 2, "height": 2},
    )

# (stem, points, thread, tap drill, spec name, station places)
_TAPS = (
    (
        "cr_tap",
        (part_spec.CR,),
        part_spec.CR_THREAD,
        part_spec.CR_TAP_DRILL,
        "CR_SPEC",
        2,
    ),
    (
        "riser_tap",
        part_spec.RISER_SCREWS,
        part_spec.RISER_THREAD,
        part_spec.RISER_TAP_DRILL,
        "RISER_SPEC",
        part_spec.RISER_STATION_PLACES,
    ),
    (
        "lever_tap",
        part_spec.LEVER_HOLES,
        part_spec.LEVER_THREAD,
        part_spec.LEVER_TAP_DRILL,
        "LEVER_SPEC",
        2,
    ),
)
for _stem, _points, _thread, _drill, _spec_name, _places in _TAPS:
    for _index, (_x, _y) in enumerate(_points, start=1):
        requirement(
            f"{_stem}_{_index}",
            kind="hole",
            faces=(CylinderFace(_drill, contains_x_mm=_x, contains_z_mm=-_y),),
            requirements=("thread", "dia", "station", "height", "thru"),
            fields={
                "at": ([_x, 0.0, -_y], (_spec_name,)),
                "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
                "thread": (f"{_thread} UNC-2B", (_spec_name,)),
                "tap_drill_mm": (_drill, (_spec_name,)),
                "dia": (
                    limits(round(_drill, 2), 2, part_spec.DRILLED_BAND),
                    (_spec_name, "DRILLED_BAND"),
                ),
                "dia_nominal": (round(_drill, 2), (_spec_name,)),
                "thru": (True, (_spec_name,)),
                "station": (limits(round(_x, _places), _places), (_spec_name,)),
                "station_nominal": (round(_x, _places), (_spec_name,)),
                "height": (limits(round(_y, _places), _places), (_spec_name,)),
                "height_nominal": (round(_y, _places), (_spec_name,)),
            },
            precision={"dia": 2, "station": _places, "height": _places},
        )


# Copied from _trammel_block_drawing (the old trammel kit is being retired;
# the new jig must not import it).
def _circle_edge(
    adapter: Any,
    view: Any,
    diameter_mm: float,
    label: str,
    *,
    center_x_mm: float | None = None,
    center_y_mm: float | None = None,
) -> Any:
    """The first visible circular edge of ``diameter_mm`` in ``view``.

    ``center_x_mm`` / ``center_y_mm`` (carrier X / Y; model Z = -Y) pick one
    of several equal holes, as draw_dt_cone_pivot_post's ``_circular_edge``
    does: without them SolidWorks' enumeration order chooses, and a leader
    routed for one hole can cross another callout to reach the other.
    """
    radius_m = diameter_mm / 2000.0
    for component in (
        adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    ):
        for raw in visible_component_entities(view, component, 1) or ():
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = curve.CircleParams
            if abs(float(params[6]) - radius_m) > 1e-6:
                continue
            if (
                center_x_mm is not None
                and abs(float(params[0]) * 1000.0 - center_x_mm) > 0.05
            ):
                continue
            if (
                center_y_mm is not None
                and abs(-float(params[2]) * 1000.0 - center_y_mm) > 0.05
            ):
                continue
            return edge
    raise RuntimeError(f"carrier view shows no {label}")


def _assert_pin_axis_geometry(source_model: Any) -> dict[str, float]:
    """Read actual bore vectors/straight lands against the actual underside.

    The allowable tilt is atan(deviation/normal height). Independent X/Z
    comparisons would admit sqrt(2) times the resultant shift at 45 degrees.
    Circular trim rims, not the cylinder's approximate bounding box, define
    the true straight land clear of the chamfer.
    """
    underside = PlanarFace((0.0, -1.0, 0.0), part_spec.THICKNESS)
    faces = resolve_faces(
        source_model,
        {
            "underside": underside,
            **{
                key: CylinderFace(
                    part_spec.PIN_HOLE_DIA, contains_x_mm=x, contains_z_mm=-y
                )
                for key, (x, y) in part_spec.PIN_HOLES.items()
            },
        },
    )
    plane = face_geometry(faces["underside"])
    if plane is None or not underside.matches(plane):
        raise RuntimeError("pin-axis control lost its native underside plane")
    normal = unit_vector(plane.outward_normal)
    if not all(math.isfinite(value) for value in (*normal, *plane.parameters)):
        raise RuntimeError("pin-axis control has an unreadable underside plane")
    angle_max = math.atan(
        part_spec.PIN_AXIS_DEVIATION_MAX / part_spec.PIN_AXIS_MEASUREMENT_SPAN
    )
    lands = {}
    for key in part_spec.PIN_HOLES:
        geometry = face_geometry(faces[key])
        if geometry is None or len(geometry.parameters) != 7:
            raise RuntimeError(f"{key}: unreadable native pin-bore cylinder")
        origin = geometry.parameters[:3]
        axis = unit_vector(geometry.parameters[3:6])
        if not all(math.isfinite(value) for value in geometry.parameters):
            raise RuntimeError(f"{key}: nonfinite native pin-bore cylinder")
        dot = abs(sum(a * n for a, n in zip(axis, normal)))
        cross = (
            axis[1] * normal[2] - axis[2] * normal[1],
            axis[2] * normal[0] - axis[0] * normal[2],
            axis[0] * normal[1] - axis[1] * normal[0],
        )
        angle = math.atan2(math.hypot(*cross), dot)
        if angle > angle_max + 1e-12:
            raise RuntimeError(
                f"{key}: native axis exceeds resultant shift "
                f"{part_spec.PIN_AXIS_DEVIATION_MAX:g} per "
                f"{part_spec.PIN_AXIS_MEASUREMENT_SPAN:g} normal height"
            )
        stations = []
        for raw_edge in _early_bound(faces[key], "IFace2").GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if len(circle) != 7 or not all(math.isfinite(v) for v in circle):
                raise RuntimeError(f"{key}: unreadable straight-land rim")
            rim_axis = unit_vector(circle[3:6])
            if (
                abs(circle[6] - geometry.parameters[6]) > 1e-8
                or abs(sum(a * b for a, b in zip(axis, rim_axis))) < 1.0 - 1e-8
            ):
                raise RuntimeError(f"{key}: straight-land rim is not on its cylinder")
            station = sum((p - o) * a for p, o, a in zip(circle[:3], origin, axis))
            if not any(abs(station - other) <= 1e-8 for other in stations):
                stations.append(station)
        if len(stations) != 2:
            raise RuntimeError(f"{key}: expected two actual straight-land rim stations")
        land = abs(stations[1] - stations[0]) * 1000.0
        if land + 1e-8 < part_spec.PIN_AXIS_MEASUREMENT_SPAN:
            raise RuntimeError(f"{key}: native straight land {land:g} is below 10.50 MIN")
        lands[key] = land
    return lands


def _assert_ream_control(adapter: Any, annotation: Any) -> None:
    """The complete acceptance must remain on the real banded bore dimension."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        str(owner.Name) != "PinHoleProfile"
        or str(dimension.FullName).split("@")[:2] != ["PinHoleDia", "PinHoleProfile"]
        or int(display.Type2) != 6  # swDiameterDimension
        or not math.isclose(
            float(dimension.SystemValue), part_spec.PIN_HOLE_DIA / 1000.0,
            abs_tol=1e-12, rel_tol=0.0,
        )
        or not math.isclose(
            float(tolerance.GetMinValue()), part_spec.PIN_HOLE_BAND[1] / 1000.0,
            abs_tol=1e-12, rel_tol=0.0,
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), part_spec.PIN_HOLE_BAND[0] / 1000.0,
            abs_tol=1e-12, rel_tol=0.0,
        )
        or not display.ShowDimensionValue
        or int(annotation.Visible) != 1
        or annotation.IsDangling()
        or str(display.GetText(8) or "") != CALLOUTS_BELOW["PinHoleDia"]
        or str(display.GetText(4) or "") != CALLOUTS_BELOW["PinHoleDia"]
    ):
        raise RuntimeError("4X REAM lost its native bore size, fit or complete axis control")


def _assert_land_control(adapter: Any, display: Any, vertices: tuple[Any, Any]) -> None:
    """A native, unbanded REF measures actual wall endpoints, not 10.50."""
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) not in (2, 11, 12):
        raise RuntimeError("straight-land reference is not a native linear dimension")
    assert_dimension_measures(
        adapter, display, expected_mm=part_spec.PIN_STRAIGHT_LAND,
        label="pin straight land", entities=vertices, entity_types=("VERTEX", "VERTEX"),
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        int(tolerance.Type) != 0
        or int(dimension.DrivenState) != 1
        or not display.ShowDimensionValue
        or int(_early_bound(display.GetAnnotation(), "IAnnotation").Visible) != 1
        or (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")")
        or int(display.GetPrimaryPrecision2())
        != part_spec.DRAWING_REFERENCE_PRECISION["PinStraightLand"]
        or str(display.GetText(8) or "") != part_spec.PIN_LAND_CALLOUT
        or str(display.GetText(4) or "") != part_spec.PIN_LAND_CALLOUT
    ):
        raise RuntimeError("straight land lost its native reference or 4X minimum acceptance")


def _add_pin_land_control(adapter: Any, section: Any):
    """Dimension the actual straight wall and identify the physical underside."""
    edges = scan_view_edges(section, label="carrier straight land and underside")
    wall_x = _A1[0] + part_spec.PIN_HOLE_DIA / 2.0
    points = (
        (wall_x, 0.0, 0.0),
        (wall_x, -part_spec.THICKNESS + part_spec.PIN_CHAMFER, 0.0),
    )
    vertices = tuple(
        edges.exact_vertex_at(point, label="A1 straight-wall endpoint") for point in points
    )
    projected = model_points_in_view(
        adapter, section, [_metres(point) for point in points], label="A1 straight land"
    )
    text_xy = model_point_in_view(
        adapter, section, _metres((_A1[0], -2.5, 0.0)), label="straight-land text"
    )
    display = _early_bound(
        add_edge_dimension(
            adapter, section, p0=projected[0], p1=projected[1], text_xy=text_xy,
            label="pin straight land", orientation="vertical",
            entities=vertices, entity_types=("VERTEX", "VERTEX"),
        ),
        "IDisplayDimension",
    )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1
    set_reference_dimension(adapter, display.GetAnnotation(), label="pin straight land")
    display.SetPrecision3(part_spec.DRAWING_REFERENCE_PRECISION["PinStraightLand"], -1, -1, -1)
    display.SetText(4, part_spec.PIN_LAND_CALLOUT)
    _assert_land_control(adapter, display, vertices)

    x_axis, _y_axis = _section_axes(adapter, section)
    underside_point = (
        _A1[0] - math.copysign(7.0, x_axis[0]), -part_spec.THICKNESS, 0.0
    )
    underside = edges.exact_line_through(
        underside_point, label="actual underside-plane section edge"
    ).edge
    under_xy = model_point_in_view(
        adapter, section, _metres(underside_point), label="underside label"
    )
    note = add_attached_note(
        adapter, section, text="UNDERSIDE", entity_xy=under_xy, attached_to=underside,
        note_xy=(under_xy[0] - 0.020, under_xy[1] - 0.007),
        label="carrier underside plane",
    )
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")

    def settled() -> None:
        if str(note.GetText() or "") != "UNDERSIDE" or int(annotation.Visible) != 1:
            raise RuntimeError("carrier underside plane lost its visible native label")
        _assert_land_control(adapter, display, vertices)
        _assert_attached_to(
            adapter, annotation, underside, entity_type="EDGE",
            what="underside-plane label", label="carrier underside plane",
        )
        _assert_leader_lands(
            annotation, under_xy, what="underside-plane label", label="carrier underside plane"
        )

    return settled


_THREAD_LABEL_LAYER = "OBLIQUE-CARRIER-THREAD-LABEL-HIDDEN"


def _hide_thread_labels(adapter: Any, view: Any) -> int:
    """Hide a view's cosmetic-thread labels; the hole callouts already state
    every thread (draw_dt_cone_tip_block's hidden-layer recipe, as in
    draw_ch_rocker_arm_tl_inspection_box)."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    if (
        manager.GetLayer(_THREAD_LABEL_LAYER) is None
        and int(
            manager.AddLayer(_THREAD_LABEL_LAYER, "duplicate thread labels", 0, 0, 0)
        )
        != 1
    ):
        raise RuntimeError("failed to add the carrier thread-label layer")
    layer = _early_bound(manager.GetLayer(_THREAD_LABEL_LAYER), "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("carrier thread-label layer is not hidden")
    hidden = 0
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        kind = int(annotation.GetType())
        # swCosmeticThread, or the thread's own "Tapped Hole" label note.
        if kind != 1 and not (
            kind == 6
            and "Tapped Hole"
            in str(
                _early_bound(annotation.GetSpecificAnnotation(), "INote").GetText()
                or ""
            )
        ):
            continue
        annotation.Layer = _THREAD_LABEL_LAYER
        if str(annotation.Layer or "") != _THREAD_LABEL_LAYER:
            raise RuntimeError("carrier cosmetic thread refused the hidden layer")
        hidden += 1
    rebuild_drawing(adapter, label="hide carrier thread labels")
    return hidden


# draw_pd_transgear_arm's tap_callout_definitions: the title block's
# "THREADS UNC/UNF CLASS 2A/2B" already states the class.
_THREAD_CLASS = re.compile(r"\s*(?:-\s*)?<hw-threadclass>\s*", re.IGNORECASE)


def _thread_class_free_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Drop the one native thread-class token; every Hole Wizard variable
    stays."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected tap callout parts: {definitions!r}")
    thread_parts = [
        part for part, text in definitions.items() if "<hw-threadclass>" in text.lower()
    ]
    if len(thread_parts) != 1:
        raise RuntimeError(
            f"tap thread line is not in one callout part: {definitions!r}"
        )
    part = thread_parts[0]
    without_class = re.sub(r" {2,}", " ", _THREAD_CLASS.sub(" ", definitions[part]))
    updated = dict(definitions)
    updated[part] = without_class.rstrip()
    return updated


def _strip_thread_class(display: Any, *, label: str, thread: str) -> None:
    """Print a tap callout without its title-block thread class, loudly; the
    resolved callout must still name its thread (``4-40 UNC``, not only the
    tap drill)."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _thread_class_free_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])
    persisted = {part: str(native.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = "\n".join(str(native.GetText(part) or "") for part in (1, 2, 3, 4))
    if (
        persisted != updated
        or re.search(r"\b2B\b", resolved)
        or f"{thread.lstrip('#')} UNC" not in resolved
    ):
        raise RuntimeError(
            f"{label} must name its thread without the class: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _append_callout_below(display: Any, text: str, *, label: str) -> None:
    """Append ``text`` as rows under a native callout's own, through the same
    IDisplayDimension text parts ``_strip_thread_class`` edits (definition 8,
    writable 4: callout below), loudly."""
    native = _early_bound(display, "IDisplayDimension")
    existing = str(native.GetText(8) or "")
    updated = f"{existing}\n{text}" if existing else text
    native.SetText(4, updated)
    persisted = str(native.GetText(8) or "")
    resolved = str(native.GetText(4) or "")
    if persisted != updated or not resolved.endswith(text):
        raise RuntimeError(
            f"{label} did not take its function rows: "
            f"definition={persisted!r}, resolved={resolved!r}"
        )


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _set_callout_texts(
    adapter: Any, annotations: list[Any], texts: dict[str, str], *, part: int
) -> None:
    """Write each named dimension's native prefix (part 1,
    swDimensionTextPrefix) or suffix (part 2) and read it back
    (draw_ch_rocker_arm_tl_trammel_pivot_plate)."""
    remaining = dict(texts)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        text = remaining.pop(dimension_name(adapter, annotation), None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(part, text)
        got = str(display.GetText(part) or "")
        if got != text:
            raise RuntimeError(f"dimension text {text!r} did not persist: {got!r}")
    if remaining:
        raise RuntimeError(f"dimension texts not applied: {sorted(remaining)}")


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model +X and +Y (1 mm each) in section A-A, read
    behind the projection barrier (draw_pn_pen_v_block ``_section_axes``)."""
    native.UpdateViewDisplayGeometry()
    x, y, z = _SECTION_ANCHOR_MM
    origin, plus_x, plus_y = model_points_in_view(
        adapter,
        native,
        (_metres((x, y, z)), _metres((x + 1.0, y, z)), _metres((x, y + 1.0, z))),
        label="carrier section A-A axes",
        names=("origin", "plus x", "plus y"),
    )
    return (
        (plus_x[0] - origin[0], plus_x[1] - origin[1]),
        (plus_y[0] - origin[0], plus_y[1] - origin[1]),
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Turn section A-A until model +Y runs up the sheet (draw_pd_platen
    ``_orient_section``), keeping the cut direction SolidWorks gives it: a
    reversed section showing its far side imported nothing (jig-r4).
    +X then reads right or left; the layout holds either way, and the log
    says which."""
    native = _early_bound(section, "IView")
    right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(up[1], up[0])
    rebuild_drawing(adapter, label="carrier section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        up[1] <= 0.0
        or abs(up[0]) > tolerance
        or abs(right[1]) > tolerance
        or abs(right[0]) <= tolerance
    ):
        raise RuntimeError(f"carrier section A-A is not +Y up: {right=}, {up=}")
    _telemetry.info(
        f"carrier section A-A angle={float(native.Angle):.6f} rad, "
        f"+X reads {'right' if right[0] > 0.0 else 'left'} (cut not reversed)"
    )


def _crop_section(adapter: Any, section: Any) -> None:
    """Crop the full section A-A to SECTION_CROP_MODEL_MM, the cut's own span
    through A1 (draw_fr_nameplate ``_crop_section``'s sequence): a rectangle
    sketched in the view's own sketch round the projected fence corners, no
    crop outline, so the cut face stops where the partial cut used to."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    rebuild_drawing(adapter, label="carrier section before crop")
    sheet_corners = model_points_in_view(
        adapter,
        native,
        [_metres(point) for point in SECTION_CROP_MODEL_MM],
        label="carrier section A-A crop corners",
    )
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate carrier section A-A for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native.GetOutline())
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for x, y in sheet_corners:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        corners.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    segments = tuple(
        sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
    )
    if len(segments) != 4:
        raise RuntimeError(
            f"carrier section A-A crop fence has {len(segments)} segments"
        )
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the carrier section A-A crop fence")
    # Crop2(jagged, no outline, intensity) returns swCropViewErrors_e; 1 is
    # NoError.
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="carrier section crop")
    native.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in native.GetOutline())
    _telemetry.info(
        f"carrier section A-A Crop2 status {status}: outline {before!r} -> "
        f"{outline!r}, fence corners {sheet_corners!r}"
    )
    # The outline carries a margin past the fence (fr_nameplate r3: +19 mm on
    # a 69 mm fence; jig-r8 here: +25.6 mm on 72 mm), so it is not held to
    # the fence's width: the proof is that it still contains the fence and
    # shrank from the 2.1 m full cut.
    width = 2.0 * _SECTION_HALF * SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0
    fence_x = sorted(float(x) for x, _ in sheet_corners)
    fence_y = sorted(float(y) for _, y in sheet_corners)
    contains = (
        outline[0] <= fence_x[0]
        and outline[2] >= fence_x[-1]
        and outline[1] <= fence_y[0]
        and outline[3] >= fence_y[-1]
    )
    if (
        status != 1
        or not bool(native.IsCropped())
        or not contains
        or outline[2] - outline[0] > 0.25 * (before[2] - before[0])
    ):
        raise RuntimeError(
            f"carrier section A-A did not crop to its {width * 1000.0:.1f} mm "
            f"fence: status {status}, outline {before!r} -> {outline!r}, "
            f"fence corners {sheet_corners!r}"
        )


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the cut's centre (A1's axis at mid-thickness) on SECTION_CENTER:
    a section's Position is its cut-plane origin, not its outline's centre
    (draw_pn_pen_v_block ``_centre_section``)."""
    native = _early_bound(section, "IView")
    anchor = _metres(_SECTION_ANCHOR_MM)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"carrier section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre carrier section A-A")
        rebuild_drawing(adapter, label="carrier section re-centred")
    settle_detail_projection(
        adapter,
        native,
        anchor,
        ink_xy=SECTION_CENTER,
        tolerance_xy=(0.0005, 0.0005),
        label="carrier section A-A",
    )


def _section_keep(adapter: Any, section: Any) -> dict[str, tuple[float, float]]:
    return {
        name: model_point_in_view(
            adapter, section, _metres(point), label=f"section A-A {name} text"
        )
        for name, point in SECTION_KEEP_MODEL_MM.items()
    }


def _reposition_section_dimensions(
    adapter: Any, section: Any, annotations: list[Any]
) -> list[Any]:
    """Place the dimensions imported into the uncropped section again on
    their SECTION_KEEP_MODEL_MM points of the cropped, centred view, prove the
    crop kept every one of them, visible, and cap the thickness's extension
    lines (STOCK_WITNESS_MAX_M) at the slab's -X end."""
    keep = _section_keep(adapter, section)
    placed = curate_dimensions(adapter, annotations, reposition=keep)
    states = {
        dimension_name(adapter, annotation): int(
            _early_bound(annotation, "IAnnotation").Visible
        )
        for annotation in placed
    }
    if set(states) != set(keep) or any(state != 1 for state in states.values()):
        raise RuntimeError(
            f"carrier section A-A lost dimensions to its crop: kept {states}, "
            f"want {sorted(keep)} visible"
        )
    (stock,) = (a for a in placed if dimension_name(adapter, a) == "StockThick")
    display = _early_bound(
        _early_bound(stock, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    display.MaxWitnessLineLength = STOCK_WITNESS_MAX_M
    rebuild_drawing(adapter, label="carrier stock witness cap")
    if abs(float(display.MaxWitnessLineLength) - STOCK_WITNESS_MAX_M) > 1e-9:
        raise RuntimeError(
            "carrier section A-A: finished thickness witness cap did not persist"
        )
    return placed


def _pin_section(adapter: Any, source_model: Any, top: Any) -> tuple[list[Any], Any]:
    """Full section A-A along the pin line, cropped to A1's slab, carrying the
    finished thickness and the chamfer leg, both from SectionReference.

    The hidden owner sketch lies in the cutting plane; a derived view takes it
    from the part as it stands when cut and selects it through its base view,
    so the section is cut and curated while the part shows it (draw_pd_platen
    ``_floor_section``). Full, not partial: through a short interior line the
    partial cut imported nothing (carrier-diag); the line crosses the whole
    plate, so the cut closes (carrier r11). Curated before it is
    cropped (the cropped import dropped StockThick), then cropped (fr_nameplate
    A-A), centred, and its dimensions placed again. A section shows no hidden
    lines.
    """
    line = [
        model_point_in_view(adapter, top, _metres(point), label="section A-A line")
        for point in SECTION_LINE_MODEL_MM
    ]
    with hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        (part_spec.SECTION_REFERENCE,),
        label="section A-A reference",
        base_view=top,
    ):
        section = create_section_view(
            adapter,
            top,
            line_start=line[0],
            line_end=line[1],
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            partial=False,
            label="pin-hole chamfer section",
        )
        _orient_section(adapter, section)
        set_hidden_lines_removed(adapter, section)
        annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=_section_keep(adapter, section),
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _crop_section(adapter, section)
        _centre_section(adapter, section)
        annotations = _reposition_section_dimensions(adapter, section, annotations)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="carrier section A-A"
    )
    return annotations, section


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open carrier source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    _assert_pin_axis_geometry(source_model)
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Carrier Plate Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel carrier plate; 6061-T651; MHA-CH-06-TL-21",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # swDetailingSectionViewLineStyleDisplay (542) = StandardWithoutConnector
    # (1): A-A's line prints its end segments only (draw_fr_rocker_arm_support).
    # Carrier-r1 review: drawn whole along the pin line, it read as the origin
    # of every Y dimension instead of the reamed holes' axes.
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set the end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)

    on_top = _view_mapper(adapter, top)
    # The spot stations and Ø3 live on SpotReference, a sketch the part saves
    # hidden: _drawing_hidden_sketches shows it in the view that imports it.
    annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep={name: on_top(xyz) for name, xyz in TOP_KEEP.items()},
        view_label="top view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations, section = _pin_section(adapter, source_model, top)
    annotations.extend(section_annotations)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _set_callout_texts(adapter, annotations, CALLOUT_PREFIXES, part=1)
    _set_callout_texts(adapter, annotations, CALLOUT_SUFFIXES, part=2)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    ream = [
        item for item in annotations if dimension_name(adapter, item) == "PinHoleDia"
    ]
    if len(ream) != 1:
        raise RuntimeError("expected one actual 4X REAM size dimension")
    _assert_ream_control(adapter, ream[0])
    land_settled = _add_pin_land_control(adapter, section)

    # Native Hole Wizard callouts, no process words (the base bar's TL-20
    # convention: "4X Ø2.26 THRU ALL / #4-40 UNC THRU ALL"); the riser taps'
    # add the function their 3-place stations serve (rule 4), the lever taps
    # their full-thread shortfall (rule 20).
    for label, xy, drill, (x, y), thread, function in (
        (
            "CR clamp tap",
            CR_CALLOUT_XY,
            part_spec.CR_TAP_DRILL,
            part_spec.CR,
            part_spec.CR_THREAD,
            None,
        ),
        (
            "riser screw taps",
            RISER_CALLOUT_XY,
            part_spec.RISER_TAP_DRILL,
            part_spec.RISER_SCREWS[3],
            part_spec.RISER_THREAD,
            part_spec.RISER_TAP_CALLOUT,
        ),
        (
            "feed lever taps",
            LEVER_CALLOUT_XY,
            part_spec.LEVER_TAP_DRILL,
            part_spec.LEVER_HOLES[1],
            part_spec.LEVER_THREAD,
            part_spec.LEVER_TAP_CALLOUT,
        ),
    ):
        callout = add_native_hole_callout(
            adapter,
            top,
            callout_xy=xy,
            label=label,
            edge=_circle_edge(adapter, top, drill, label, center_x_mm=x, center_y_mm=y),
        )
        _strip_thread_class(callout, label=f"{label} callout", thread=thread)
        if function is not None:
            _append_callout_below(callout, function, label=f"{label} callout")

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    import_cosmetic_threads(adapter, iso)
    for view in (top, iso):
        _hide_thread_labels(adapter, view)

    def pin_controls_settled() -> None:
        _assert_pin_axis_geometry(source_model)
        _assert_ream_control(adapter, ream[0])
        land_settled()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Carrier Plate Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(pin_controls_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
