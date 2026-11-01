r"""Reproduction script: rocker arm (book ch. 14, pp. 26-29; 20 used).

Thin matte-black steel strap that see-saws on its pivot shaft atop the
tapered support castings. The FRONT PROFILE is now two concentric arcs of
DIFFERENT arc length (a tapered curved strap), per the ch.30 back-view
sketch:

  * Top edge  = concave-up arc, R = 800 mm (= amplitude-bar length, the book's
    nonlinearity rationale), arc length 11.5" (292.1 mm).
  * Bottom edge = concentric arc, R = 816 mm (top + 16 mm depth), arc length
    10.5" (266.7 mm).
  * Because the two arcs subtend DIFFERENT angles on their radii, the end faces
    are NOT radial -- they slant inward, so the strap TAPERS toward each tip
    (the "square ends" of the sketch are approximate; a shorter lower edge below
    a longer upper edge is only possible with inward-tapering ends).
  * Each tip has a 0.22" (5.588 mm) face PERPENDICULAR to the top edge (a radial
    segment, the sketch's 90deg right-angle mark), cut into the front profile --
    not a 3D chamfer feature.

The perpendicular top-to-bottom DEPTH stays 16 mm (p.29 end-face callout); the
plate THICKNESS (Z) is the p.27 callout's 2.5 mm on the inch grid, .098.

Mid-pivot SEESAW, symmetric about the pivot. The 11.5" top span was measured
manually from the ch.30 back view (supersedes the p.29 broadside photo-scaled
4.5"/9" read and the indirect M6.3 "80 mm bar travel + 8 mm margin" = 88); the
10.5" bottom arc + 0.22" perpendicular tip face come from the same ch.30 sketch.
The connecting rod pins at +127.37 on the +X side, just inboard of the rod-side
tip and LOW in the strap (5.3 above the bottom edge, ch14 fan photo) -- directly
above the phased cam lobe, so the rod hangs PLUMB with the arm LEVEL (ch30
photos + GT rocker-corner triangulation + the ch14 end views' flat 0-crank tip
row; supersedes M6.3's "1 inch from the pivot", which was tied to the pre-ch30
arbor-47.5 layout). The amplitude bar rides the top edge either side of the
pivot (ch. 15: the bar "can slide completely off the rocker").

This supersedes the legacy `oscilating-arms` part (no surviving source). M2's
rod-at-tip reading is thus partially vindicated; its asymmetric 100/70 profile
stays refuted (the strap is a symmetric mid-pivot seesaw).

Dimensions: cad/DIMENSIONS.md "Chapter 14" - annotated thickness/depth, stated
curvature, ch.30 back-view arc lengths + perpendicular tip face (med).

Layout: pivot at the origin, arm along X (+X = connecting-rod side), arc center
816 mm above, extruded mid-plane in Z; holes cut through Z. The pivot hole
centre sits at local (0, 8) - assembly scripts must offset placements
accordingly.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _document_units import apply_package_model_units
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from _part_properties import part_drawing_unit
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_dimension_insert import add_angular_reference_dimension
from _drawing_prefix import set_dimension_prefix
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance, set_dimension_symmetric_tolerance
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE, RIGHT_VIEW_NOTE
from ch_rocker_arm_notes import HUB_ROOT_PREFIX, HUB_ROOT_R_BAND, HUB_ROOT_R_TOL_TYPE
from ch_rocker_arm_notes import DRAWING_DIMENSIONS, DRAWING_PRECISION
from _rocker_interface import (
    ARM_DEPTH,
    CENTER_Y,
    CURVE_RADIUS,
    PIVOT_MID_Y,
    R_BOTTOM,
    ROD_HOLE_X,
    ROD_HOLE_Y,
)
from ch_rocker_arm_spec import (
    ARM_THICKNESS as SPEC_ARM_THICKNESS,
    ARM_THICKNESS_BAND,
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    HUB_ROOT_RADIUS_MAX,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    ROD_HOLE_SPEC,
    SURFACE_FINISHES,
    TOP_EDGE_ABOVE_PIVOT,
    TOP_EDGE_BAND,
    UNIT,
)
import _config

PART_NAME = "ch-rocker-arm"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

ARM_THICKNESS = 2.4892  # .098; ch14: p.27 photo callout 2.5 mm (plate thickness, Z)
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view, manual)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # 0.22" tip face, PERPENDICULAR to the top edge (ch.30 sketch)
# The hub length IS the station pitch: hub faces of neighbouring arms touch.
if abs(HUB_LENGTH - _config.machine("channels", "station_pitch_mm")) > 1e-6:
    raise AssertionError("ch_rocker_arm_spec.HUB_LENGTH must equal the channel station pitch")
HUB_PROUD = (HUB_LENGTH - ARM_THICKNESS) / 2.0  # 2.278 each face
if ARM_THICKNESS != SPEC_ARM_THICKNESS:
    raise AssertionError("ch_rocker_arm_spec.ARM_THICKNESS drifted from the build")
# The rod-pin native drill identity is part-owned by ch_rocker_arm_spec.
# The interface's rod-pin position follows the bottom-arc end (132.76): solved
# so the pin sits DIRECTLY ABOVE the phased cam
# lobe (machine X is DRUM_X + ECC*sin(1.5 deg), lobe UP at the
# cos-mode home pose) with the pivot at the seesaw mid-span (+72.9) and the arm
# LEVEL -- the ch30 photos show every connecting rod hanging PLUMB from the arm
# tip onto its cam, the ch14 end views show the 0-crank tip row dead level, and
# the GT rocker-corner triangulation puts the rod-side arm end at machine x -60
# (bottom-arc end predicts -59.9 at the level pose). Supersedes 127.49, the
# same plumb solve at the pre-ROM-fit lobe-down phase (ring x 54.78), and
# M6.3's 25.4 ("1 inch from the pivot", pre-ch30 arbor-47.5 layout).
# ROD_HOLE_ABOVE_BOTTOM preserves the old 15.302534 world/local Y
# after the X re-anchor moves along the curved bottom edge. This keeps the
# unchanged-length rod plumb and the neutral arm level.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > thickness

# Arc centre sits ARM_DEPTH above the pivot's bottom edge: bottom edge is an
# R816 arc, top edge the concentric R800 arc through (0, 16).
R_TOP = CURVE_RADIUS
if abs(CENTER_Y - PIVOT_MID_Y - R_TOP - TOP_EDGE_ABOVE_PIVOT) > 1e-9:
    raise AssertionError("the CenterY equation must rebuild the modelled centre")

# Half-angle each arc subtends (arc_len / 2 / radius); the two differ, which is
# what tapers the ends. Endpoint coords: on the circle centred at (0, CENTER_Y).
_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = R_BOTTOM * math.sin(_ALPHA_BOT)
BOT_END_Y = CENTER_Y - R_BOTTOM * math.cos(_ALPHA_BOT)

# Each tip has a short face PERPENDICULAR to the top edge (the sketch's 90deg
# right-angle mark): a radial segment (perpendicular to the arc = along the
# radius) of length TIP_FACE, running from the top-arc endpoint outward (away
# from the centre) to where the tapered end face begins. Outward radial unit at
# the +X top endpoint = (endpoint - centre)/R_TOP.
_RAD_X = TOP_END_X / R_TOP  # = sin(alpha_top)
_RAD_Y = (TOP_END_Y - CENTER_Y) / R_TOP  # = -cos(alpha_top)
ROD_TIP_X = TOP_END_X + TIP_FACE * _RAD_X
ROD_TIP_Y = TOP_END_Y + TIP_FACE * _RAD_Y


def _bottom_point(x: float) -> tuple[float, float]:
    return (x, CENTER_Y - math.sqrt(R_BOTTOM**2 - x * x))


def _mid_y(x: float) -> float:
    by = _bottom_point(x)[1]
    ty = CENTER_Y - math.sqrt(R_TOP**2 - x * x)
    return (by + ty) / 2.0


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchLine the entity registry binds -- rebind before the set
    (build_dt_crank_arm's helper).
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _tip_land_angle_reference(adapter, rod_tip_line: str, dims: SketchDims) -> None:
    """Measure the real +X radial land from vertical in StrapProfile.

    The land is already constrained through the common arc centre. Only a
    construction ray is added: its root follows the land's top endpoint,
    while vertical plus a length dimension fully define its free endpoint.
    The angular dimension is driven, so neither the solid outline nor the
    existing profile dimensions acquire another driving constraint.
    """
    set_sketch_direct_db(adapter, True)
    vertical = check(
        "tip land vertical reference",
        await adapter.add_line(
            TOP_END_X, TOP_END_Y, TOP_END_X, TOP_END_Y - TIP_FACE
        ),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, vertical)
    check(
        "tip land vertical reference root",
        await adapter.add_sketch_constraint(
            f"{vertical}.start", f"{rod_tip_line}.start", "coincident"
        ),
    )
    check(
        "tip land vertical reference direction",
        await adapter.add_sketch_constraint(vertical, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{vertical}.start",
        f"{vertical}.end",
        "vertical_distance",
        TIP_FACE,
        "tip land vertical reference length",
    )
    dims.record("TipLandVerticalLength", '"TipFaceLen"')
    # Place text in the acute downward wedge; AddSpecificDimension measures
    # the selected real land and reference ray, never a numeric text override.
    await add_angular_reference_dimension(
        adapter,
        vertical,
        rod_tip_line,
        (
            TOP_END_X + 2.0 * TIP_FACE * math.sin(_ALPHA_TOP / 2.0),
            TOP_END_Y - 2.0 * TIP_FACE * math.cos(_ALPHA_TOP / 2.0),
        ),
        "tip land from vertical",
        expected_degrees=math.degrees(_ALPHA_TOP),
    )
    dims.record("TipLandAngle")


# The hub-to-strap root fillet (Opus #1020 r2 C2): one full circle on each
# strap face, a concave corner of section (1 - pi/4) R^2 whose centroid sits
# R (10 - 3 pi) / (12 - 3 pi) out from the hub wall (Pappus).
_HUB_ROOT_SECTION = (1.0 - math.pi / 4.0) * HUB_ROOT_RADIUS_MAX**2
_HUB_ROOT_CENTROID_R = HUB_DIA / 2.0 + HUB_ROOT_RADIUS_MAX * (10.0 - 3.0 * math.pi) / (
    12.0 - 3.0 * math.pi
)
V_HUB_ROOT = 2.0 * 2.0 * math.pi * _HUB_ROOT_CENTROID_R * _HUB_ROOT_SECTION


def _hub_root_radius_max_limit(adapter) -> None:
    """HubRootRadius as the single limit "R.008 MAX" carrying the band's
    deviations (build_ch_pivot_bracket._corner_radius_max_limit's recipe)."""
    lower, upper = deviations(HUB_ROOT_R_BAND)
    _, dimension = _named_dimension(adapter, "HubRoot", "HubRootRadius")
    label = "HubRootRadius@HubRoot"
    value = float(dimension.SystemValue)
    if not math.isclose(value, HUB_ROOT_RADIUS_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max {HUB_ROOT_RADIUS_MAX}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = HUB_ROOT_R_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != HUB_ROOT_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")


def _strap_area() -> float:
    """Cross-section area of the tapered strap (two arcs + two perpendicular tip
    faces + two tapered end faces) by shoelace over a densely-sampled boundary --
    exact enough for the volume gate, and correct for the non-annular shape the
    differing arc lengths + tip faces produce.

    Boundary order: bottom arc rod->tail, tail end face (up to tail_tip), tail
    tip face (the transition into the top arc's first point = tail_t), top arc
    tail->rod, rod tip face (rod_t -> rod_tip), then the wrap rod_tip -> rod_b is
    the rod end face."""
    n = 200
    pts: list[tuple[float, float]] = []
    for i in range(n + 1):  # bottom arc, rod (+alpha) -> tail (-alpha)
        a = _ALPHA_BOT - 2.0 * _ALPHA_BOT * i / n
        pts.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    pts.append((-ROD_TIP_X, ROD_TIP_Y))  # tail end face: tail_b -> tail_tip
    for i in range(n + 1):  # top arc, tail (-alpha) -> rod (+alpha)
        a = -_ALPHA_TOP + 2.0 * _ALPHA_TOP * i / n
        pts.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
    pts.append((ROD_TIP_X, ROD_TIP_Y))  # rod tip face: rod_t -> rod_tip
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs: named globals in the equation manager that drive every
    # sketch dimension below. A GUI fine-tune edits THESE (Tools > Equations) --
    # e.g. TopEndX or CurveRadius -- never an auto "D3@Sketch1". The mm suffix is
    # load-bearing: this is an INCH document and the equation manager evaluates
    # BARE numbers in document units, so an unsuffixed "800" would read as 800
    # inches and blow the part up 25.4x. The derived globals RTop/RBottom/CenterY
    # (concentric arc radii + shared centre height) are equations of the
    # primitives, so the two arcs stay concentric and ArmDepth-apart.
    #
    # TopEndX/BottomEndX are each arc's endpoint x = R*sin(arclen / 2 / R),
    # computed HERE in Python (not as an SW equation): the tip x IS the editable
    # knob. Trig lives in the equation manager unreliably -- a live
    # sin("arclen"/2/"R") re-evaluates on rebuild to a geometry-breaking value
    # (radians-vs-degrees + length/length dimensionality), so the arc length is a
    # Python constant (TOP_ARC_LEN / BOT_ARC_LEN, = 11.5" / 10.5") folded into the
    # tip x here. To re-cut to a different arc length, edit those constants.
    await set_global(adapter, "CurveRadius", f"{CURVE_RADIUS}mm")
    await set_global(adapter, "ArmDepth", f"{ARM_DEPTH}mm")
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "TipFaceLen", f"{TIP_FACE}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "HubLength", f"{HUB_LENGTH}mm")
    await set_global(adapter, "HubRootR", f"{HUB_ROOT_RADIUS_MAX}mm")
    await set_global(adapter, "RodHoleX", f"{ROD_HOLE_X}mm")
    # (The old RodHoleDia/RodHoleX knobs are gone: the rod pin hole is now a native
    # Hole Wizard #47 feature whose diameter comes from the drill standard; its
    # location rides the ROD_HOLE_X/ROD_HOLE_Y module constants that the channel
    # assembly imports.)
    await set_global(adapter, "ThroughCutDepth", f"{THROUGH_CUT_DEPTH}mm")
    # The top edge's height over the pivot axis is the print's controlled
    # value (ch_rocker_arm_spec.TOP_EDGE_BAND), so the arcs' shared centre is
    # derived from it: the pivot (ArmDepth / 2), up to the top edge, up R800.
    await set_global(adapter, "TopAbovePivot", f"{TOP_EDGE_ABOVE_PIVOT}mm")
    await set_global(adapter, "RTop", '"CurveRadius"')
    await set_global(adapter, "RBottom", '"CurveRadius" + "ArmDepth"')
    await set_global(
        adapter, "CenterY", '"ArmDepth" / 2 + "TopAbovePivot" + "CurveRadius"'
    )
    await set_global(adapter, "TopEndX", f"{TOP_END_X}mm")
    await set_global(adapter, "BottomEndX", f"{BOT_END_X}mm")

    # Each sketch DECLARES its dim names + drive equations as it records them; the
    # drive equations are collected here and applied in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    tail_b = (-BOT_END_X, BOT_END_Y)
    rod_b = (BOT_END_X, BOT_END_Y)
    tail_t = (-TOP_END_X, TOP_END_Y)
    rod_t = (TOP_END_X, TOP_END_Y)
    rod_tip = (ROD_TIP_X, ROD_TIP_Y)
    tail_tip = (-ROD_TIP_X, ROD_TIP_Y)

    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "strap bottom arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_b, *rod_b),
        ),
        check(
            "strap top arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_t, *rod_t),
        ),
        # Rod tip: a short radial face (rod_t -> rod_tip) square to the top edge,
        # then the tapered end face down to the bottom arc (rod_tip -> rod_b).
        check("strap rod tip", await adapter.add_line(*rod_t, *rod_tip)),
        check("strap rod end", await adapter.add_line(*rod_tip, *rod_b)),
        check("strap tail tip", await adapter.add_line(*tail_t, *tail_tip)),
        check("strap tail end", await adapter.add_line(*tail_tip, *tail_b)),
    ]
    set_sketch_direct_db(adapter, False)
    bottom_arc, top_arc, rod_tip_line, _rod_end, tail_tip_line, _tail_end = entities
    # Two concentric arcs (top R800, bottom R816), each tip a short face square to
    # the top edge, then a tapered end face down to the bottom arc. The top arc
    # (11.5" arc-len) and bottom arc (10.5") subtend DIFFERENT angles on their
    # radii, so the end faces slant inward (the profile tapers). The tip faces are
    # PERPENDICULAR to the top edge: each is made radial by a coincident relation
    # pinning the top arc's CENTRE onto the tip line (a line through the centre is
    # along the radius = normal to the arc), then a linear length dim = TipFaceLen.
    # Dim EMISSION ORDER (record each as its display dim is created): the centre's
    # vertical_distance (x on-axis, so anchor_point_to_origin emits ONE dim =
    # CenterY), bottom radius, top radius, bottom-tail x, bottom-rod x, top-tail x,
    # top-rod x, rod-tip length, tail-tip length -- NINE outline display dims.
    # The vertical construction ray and its driven angle follow those dims.
    # The ``coincident`` concentric + the two radial relations are not dims.
    await anchor_point_to_origin(
        adapter, f"{bottom_arc}.center", 0.0, CENTER_Y, "arc centre"
    )
    # CenterY is at +y, so the unsigned vertical_distance drives positive.
    strap.record("CenterY", '"CenterY"')
    check(
        "concentric arcs",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", f"{bottom_arc}.center", "coincident"
        ),
    )
    check(
        "bottom radius",
        await adapter.add_sketch_dimension(bottom_arc, None, "radial", R_BOTTOM),
    )
    strap.record("BottomRadius", '"RBottom"')
    check(
        "top radius",
        await adapter.add_sketch_dimension(top_arc, None, "radial", R_TOP),
    )
    strap.record("TopRadius", '"RTop"')
    # Endpoint x dims: horizontal_distance shows the MAGNITUDE, so each drives
    # POSITIVE against its arc's endpoint global (both tips share one magnitude ->
    # symmetric seesaw).
    check(
        "bottom tail x",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.start", "origin", "horizontal_distance", BOT_END_X
        ),
    )
    strap.record("BottomTailX", '"BottomEndX"')
    check(
        "bottom rod x",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.end", "origin", "horizontal_distance", BOT_END_X
        ),
    )
    strap.record("BottomRodX", '"BottomEndX"')
    check(
        "top tail x",
        await adapter.add_sketch_dimension(
            f"{top_arc}.start", "origin", "horizontal_distance", TOP_END_X
        ),
    )
    strap.record("TopTailX", '"TopEndX"')
    check(
        "top rod x",
        await adapter.add_sketch_dimension(
            f"{top_arc}.end", "origin", "horizontal_distance", TOP_END_X
        ),
    )
    strap.record("TopRodX", '"TopEndX"')
    # Tip faces square to the top edge: pin the top arc's centre onto each tip
    # line (=> the line is radial => perpendicular to the arc), then a length dim.
    check(
        "rod tip radial",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", rod_tip_line, "coincident"
        ),
    )
    check(
        "rod tip length",
        await adapter.add_sketch_dimension(rod_tip_line, None, "linear", TIP_FACE),
    )
    strap.record("RodTipLen", '"TipFaceLen"')
    check(
        "tail tip radial",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", tail_tip_line, "coincident"
        ),
    )
    check(
        "tail tip length",
        await adapter.add_sketch_dimension(tail_tip_line, None, "linear", TIP_FACE),
    )
    strap.record("TailTipLen", '"TipFaceLen"')
    await _tip_land_angle_reference(adapter, rod_tip_line, strap)
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ARM_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Strap")
    # The strap thickness prints natively at three places (ARM_THICKNESS_BAND,
    # Main ruling 2026-10 option b): each inter-arm gap holds one tine of each
    # neighbouring rod fork. Named so the drawing selects it by name.
    strap_thickness_dim = name_dimensions(adapter, "Strap", ["StrapThickness"])
    drive_jobs.append((strap_thickness_dim[0], '"ArmThickness"'))
    v_strap = _strap_area() * ARM_THICKNESS
    await volume_check(adapter, "strap", v_strap, 0.01 * v_strap)

    # Integral pivot hub (2026-09-02, ch14 p.28): a Ø.400 boss coaxial with the
    # pivot bore, HUB_LENGTH long mid-plane (= the station pitch), so it stands
    # HUB_PROUD of each strap face and touches the neighbour arms' hubs. The
    # circle (r 5 about (0, ArmDepth/2)) lies inside the 16-deep strap, so the
    # boss only ADDS the two proud discs. Cut BEFORE the pivot hole so the bore
    # runs through hub + strap.
    hub = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, _mid_y(0.0), HUB_DIA / 2.0, "hub",
        dims=hub,
        names=("HubX", "HubZ", "HubDia"),
        drives=(None, '"ArmDepth" / 2', '"HubDia"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Hub")
    hub_length_dim = name_dimensions(adapter, "Hub", ["HubLength"])
    drive_jobs.append((hub_length_dim[0], '"HubLength"'))
    v_hub = math.pi * (HUB_DIA / 2.0) ** 2 * (HUB_LENGTH - ARM_THICKNESS)
    v_hub_measured = await volume_check(
        adapter, "strap + hub", v_strap + v_hub, 0.01 * v_strap
    )

    # Hub-to-strap root (Opus #1020 r2 C2, drawing-guidelines rule 16): the
    # circle where the hub meets each strap face, filleted AT the largest
    # radius the MHA-CH-01 foot cheeks clear (test_rocker_bank_layout), the
    # radius the print gives as a single MAX limit.
    check(
        "fillet hub roots",
        await adapter.add_fillet(
            HUB_ROOT_RADIUS_MAX,
            [
                [HUB_DIA / 2.0, _mid_y(0.0), ARM_THICKNESS / 2.0],
                [HUB_DIA / 2.0, _mid_y(0.0), -ARM_THICKNESS / 2.0],
            ],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "HubRoot")
    hub_root_dim = name_dimensions(adapter, "HubRoot", ["HubRootRadius"])
    drive_jobs.append((hub_root_dim[0], '"HubRootR"'))
    v_hub += V_HUB_ROOT
    await volume_check(
        adapter, "hub root fillets", v_hub_measured + V_HUB_ROOT, 0.1 * V_HUB_ROOT
    )

    # Pivot pin hole on the axis (x 0), mid-depth. On-axis centre: define_circle
    # records only the centre-Z dim (the X is a relation) + the diameter -- TWO
    # dims, so the "X" name/drive slot is ignored. The centre sits at
    # _mid_y(0) = ArmDepth/2 (positive), so its unsigned dim drives positive.
    pivot = SketchDims()
    check("create_sketch pivot hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, _mid_y(0.0), PIVOT_HOLE_DIA / 2.0, "pivot hole",
        dims=pivot,
        names=("PivotX", "PivotZ", "PivotDia"),
        drives=(None, '"ArmDepth" / 2', '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pivot hole sketch")
    check("exit_sketch pivot hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotHoleProfile")
    drive_jobs += pivot.apply(adapter, "PivotHoleProfile")
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotHole")
    # Named axis through the pivot bore (Axis1): assembly mates select it by
    # NAME (Right ∩ Top+8), view-independent -- an internal bore wall never
    # selects by screen-projected point. See _bore_axis.name_bore_axis.
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", _mid_y(0.0), "pivot bore"
    )

    # REFERENCE sketch (drawing-simplicity-policy.md `How the repository implements the guidelines`, Codex #936 PRRT_kwDOPHDy386mV3AO): the
    # sheet prints the top edge's height over the pivot axis with a one-sided
    # band, yet no strap dimension carries it (the arcs are placed by their
    # shared centre). A construction line on the mirror axis, from the pivot
    # centre to the top edge: its foot's height is the pivot's (ArmDepth / 2),
    # and its length IS the printed value, the global CenterY is derived from.
    # Direct-to-DB keeps inference from adding relations the explicit ones
    # below would over-define.
    top_ref = SketchDims()
    check("create_sketch top edge reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    top_line = check(
        "top edge reference line",
        await adapter.add_line(
            0.0, PIVOT_MID_Y, 0.0, PIVOT_MID_Y + TOP_EDGE_ABOVE_PIVOT
        ),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, top_line)
    check(
        "top edge reference vertical",
        await adapter.add_sketch_constraint(top_line, None, "vertical"),
    )
    # Dimensions in creation order; SketchDims renames them by that order.
    await anchor_point_to_origin(
        adapter, f"{top_line}.start", 0.0, PIVOT_MID_Y, "top edge reference foot"
    )
    top_ref.record("PivotY", '"ArmDepth" / 2')
    await dimension_between(
        adapter,
        f"{top_line}.start",
        f"{top_line}.end",
        "vertical_distance",
        TOP_EDGE_ABOVE_PIVOT,
        "top edge above the pivot",
    )
    top_ref.record("TopAbovePivot", '"TopAbovePivot"')
    await ensure_fully_defined(adapter, "top edge reference sketch")
    check("exit_sketch top edge reference", await adapter.exit_sketch())
    name_last_feature(adapter, "TopEdgeReference")
    drive_jobs += top_ref.apply(adapter, "TopEdgeReference")

    # Connecting-rod pin hole near the rod-side tip, low in the strap.
    rod_cut = wizard_holes(
        adapter,
        ROD_HOLE_SPEC,
        [[ROD_HOLE_X, ROD_HOLE_Y, ARM_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        f"rod pin hole ({ROD_HOLE_SPEC.size})",
        name="RodHole",
        expect_dia_mm=blind_cut_dia_mm(ROD_HOLE_SPEC),
        placement_dims=[(("RodPinX", '"RodHoleX"'), (None, None))],
    )
    drive_jobs += rod_cut.placement_drive_jobs
    # Named axis through the rod-pin bore (Axis2 = (Right+ROD_HOLE_X) ∩ (Top+hole_y)).
    await name_bore_axis(
        adapter,
        "Right Plane",
        ROD_HOLE_X,
        "Top Plane",
        ROD_HOLE_Y,
        "rod bore",
        drive_a='"RodHoleX"',
        drive_jobs=drive_jobs,
    )
    # Named axis on the R800 top-edge arc CENTRE (Axis3 = Right ∩ Top+816, a
    # free-space datum 808 above the pivot bore, along Z like the bores). The
    # channel assembly holds the amplitude bar's foot axis at its as-solved
    # radius from this line (the J5 foot-on-arc coupling), so swinging the
    # rocker drives the bar + channel lever. Tied to "CenterY" so a GUI edit
    # of the arc radius/depth moves the coupling with it.
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", CENTER_Y, "arc centre",
        drive_b='"CenterY"', drive_jobs=drive_jobs,
    )

    # The pivot bore runs the full hub length; the rod bore only the strap.
    rod_dia = blind_cut_dia_mm(ROD_HOLE_SPEC)
    v_pivot = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * HUB_LENGTH
    v_rod = math.pi * (rod_dia / 2.0) ** 2 * ARM_THICKNESS
    # The tip faces are cut into the SKETCH profile (not a 3D chamfer feature), so
    # _strap_area already accounts for them: the bored-strap volume is tight.
    v_measured = await volume_check(
        adapter, "bored strap + hub", v_strap + v_hub - v_pivot - v_rod, 0.01 * v_strap
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below (tight, vs the
    # MEASURED pre-drive volume) is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rocker-arm (equations neutral)", v_measured, 0.005 * v_strap
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    # The strap is centred (mid-plane extrude) and its band symmetric, so it
    # prints +/- at three places.
    strap_lower, strap_upper = deviations(ARM_THICKNESS_BAND)
    if strap_lower != -strap_upper:
        raise AssertionError("ch_rocker_arm_spec.ARM_THICKNESS_BAND must be symmetric")
    set_dimension_symmetric_tolerance(
        adapter, "Strap", "StrapThickness", strap_upper, display_unit=UNIT
    )
    # The hub length only comes out long (#743 PR2): four places hold it.
    set_dimension_bilateral_tolerance(
        adapter, "Hub", "HubLength", *deviations(HUB_LENGTH_BAND), display_unit=UNIT
    )
    # The top edge may only come out high (ch_rocker_arm_spec.TOP_EDGE_BAND).
    set_dimension_bilateral_tolerance(
        adapter, "TopEdgeReference", "TopAbovePivot", *deviations(TOP_EDGE_BAND),
        display_unit=UNIT,
    )
    # The hub roots print as the single limit "2X R.008 MAX": both strap faces.
    _hub_root_radius_max_limit(adapter)
    set_dimension_prefix(adapter, "HubRoot", "HubRootRadius", HUB_ROOT_PREFIX)
    # The reamed pivot bore's band rides its Ø.2560 natively (drawing-guidelines.md rule 3 (decimal places carry the tolerance));
    # note 6 keeps only the REAM process word.
    set_dimension_bilateral_tolerance(
        adapter, "PivotHoleProfile", "PivotDia", *deviations(PIVOT_HOLE_BAND),
        display_unit=UNIT,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Right View Note": RIGHT_VIEW_NOTE,
        },
    )
    # The reference sketch owns a printed dimension but no geometry: hide it
    # so no assembly instance renders it (#880). The drawing shows it in its
    # view through _drawing_hidden_sketches to import its dimension.
    blank_sketch(adapter, "TopEdgeReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Isometric View Note", "Right View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
