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
plate THICKNESS (Z) stays 2.5 mm (p.27 callout).

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

    uv run python cad\scripts\build_rocker_arm.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes

PART_NAME = "rocker-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

CURVE_RADIUS = 800.0  # DIMENSIONS.md ch14: top edge R = amplitude bar length (stated)
ARM_DEPTH = 16.0  # ch14: p.29 photo callout, perpendicular top-to-bottom depth
ARM_THICKNESS = 2.5  # ch14: p.27 photo callout (plate thickness, Z)
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view, manual)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # 0.22" tip face, PERPENDICULAR to the top edge (ch.30 sketch)
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft (DIMENSIONS.md ch14, derived)
# rod pin hole: was Ø2.0 drill, now #47 (Ø1.994) native Hole Wizard feature
ROD_HOLE_X = 127.3738  # rod pin near the +X (rod-side) tip, 5.4 inboard of the
# bottom-arc end (132.76): solved so the pin sits DIRECTLY ABOVE the phased cam
# lobe (machine -54.474 = drum -54.7 + ECC 8.64 x sin 1.5 deg, lobe UP at the
# cos-mode home pose) with the pivot at the seesaw mid-span (+72.9) and the arm
# LEVEL -- the ch30 photos show every connecting rod hanging PLUMB from the arm
# tip onto its cam, the ch14 end views show the 0-crank tip row dead level, and
# the GT rocker-corner triangulation puts the rod-side arm end at machine x -60
# (bottom-arc end predicts -59.9 at the level pose). Supersedes 127.49, the
# same plumb solve at the pre-ROM-fit lobe-down phase (ring x 54.78), and
# M6.3's 25.4 ("1 inch from the pivot", pre-ch30 arbor-47.5 layout).
ROD_HOLE_ABOVE_BOTTOM = 5.3  # rod-pin hole centre above the arm's BOTTOM edge:
# the ch14 fan photo (p.26, 16 mm callout scale) puts the pin in the arm's lower
# third -- 10.7 below the top edge = 5.3 above the bottom -- with the rod's
# tombstone head lapping the face below the top edge. Supersedes the mid-depth
# (8.0-equivalent) placement.
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > thickness

# Arc centre sits ARM_DEPTH above the pivot's bottom edge: bottom edge is an
# R816 arc, top edge the concentric R800 arc through (0, 16).
CENTER_Y = CURVE_RADIUS + ARM_DEPTH
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH

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


# Rod-pin hole centre: LOW in the strap (ch14 fan photo), not mid-depth like
# the pivot. Assembly scripts import this (imported-not-copied, like _mid_y).
ROD_HOLE_Y = _bottom_point(ROD_HOLE_X)[1] + ROD_HOLE_ABOVE_BOTTOM  # 15.303


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
    await set_global(adapter, "RodHoleX", f"{ROD_HOLE_X}mm")
    # (The old RodHoleDia/RodHoleX knobs are gone: the rod pin hole is now a native
    # Hole Wizard #47 feature whose diameter comes from the drill standard; its
    # location rides the ROD_HOLE_X/ROD_HOLE_Y module constants that the channel
    # assembly imports.)
    await set_global(adapter, "ThroughCutDepth", f"{THROUGH_CUT_DEPTH}mm")
    await set_global(adapter, "RTop", '"CurveRadius"')
    await set_global(adapter, "RBottom", '"CurveRadius" + "ArmDepth"')
    await set_global(adapter, "CenterY", '"CurveRadius" + "ArmDepth"')
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
    # top-rod x, rod-tip length, tail-tip length -- NINE display dims. The
    # ``coincident`` concentric + the two radial relations are RELATIONS, not dims.
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
    v_strap = _strap_area() * ARM_THICKNESS
    await volume_check(adapter, "strap", v_strap, 0.01 * v_strap)

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
    # selects by screen-projected point. See _common.name_bore_axis.
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", _mid_y(0.0), "pivot bore"
    )

    # Connecting-rod pin hole near the rod-side tip, LOW in the strap (5.3 above
    # the bottom edge, ch14 fan photo -- the pivot hole stays mid-depth): was a
    # plain Ø2.0 cut, now a native Hole Wizard #47 number drill (Ø1.994) drilled
    # +Z through the 2.5 strap at (ROD_HOLE_X, ROD_HOLE_Y)
    # (memory/fastener-policy-us-customary). The pivot hole stays a Ø6.5 circle
    # cut. Through-all is geometrically identical to the old mid-plane cut.
    rod_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[ROD_HOLE_X, ROD_HOLE_Y, ARM_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        "rod pin hole (#47)",
        name="RodHole",
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

    # Both bores are full-thickness through the 2.5 strap, entirely inside the
    # material, so each removes pi*r^2*thickness.
    rod_dia = NUMBER_DRILL_MM["#47"]
    v_pivot = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * ARM_THICKNESS
    v_rod = math.pi * (rod_dia / 2.0) ** 2 * ARM_THICKNESS
    # The tip faces are cut into the SKETCH profile (not a 3D chamfer feature), so
    # _strap_area already accounts for them: the bored-strap volume is tight.
    v_measured = await volume_check(
        adapter, "bored strap", v_strap - v_pivot - v_rod, 0.01 * v_strap
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
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
