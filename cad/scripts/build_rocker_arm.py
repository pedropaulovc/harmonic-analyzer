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
  * A 0.22" (5.588 mm) 45deg chamfer breaks each top-outer tip corner.

The perpendicular top-to-bottom DEPTH stays 16 mm (p.29 end-face callout); the
plate THICKNESS (Z) stays 2.5 mm (p.27 callout).

Mid-pivot SEESAW, symmetric about the pivot. The 11.5" top span was measured
manually from the ch.30 back view (supersedes the p.29 broadside photo-scaled
4.5"/9" read and the indirect M6.3 "80 mm bar travel + 8 mm margin" = 88); the
10.5" bottom arc + 0.22" tip chamfer come from the same ch.30 back-view sketch.
The connecting rod pins at +25.4 (1") on the +X side (photo-confirmed at
+25 mm), closing the vertical-rod geometry against the cylinder arbor (M6.3,
DIMENSIONS.md ch. 14 layout table). The amplitude bar rides the top edge either
side of the pivot (ch. 15: the bar "can slide completely off the rocker").

This supersedes the legacy `oscilating-arms` part (no surviving source) and the
M2 asymmetric 100/70 rod-at-tip geometry (refuted in M6.3).

Dimensions: cad/DIMENSIONS.md "Chapter 14" - annotated thickness/depth, stated
curvature, ch.30 back-view arc lengths + tip chamfer (med).

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

PART_NAME = "rocker-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

CURVE_RADIUS = 800.0  # DIMENSIONS.md ch14: top edge R = amplitude bar length (stated)
ARM_DEPTH = 16.0  # ch14: p.29 photo callout, perpendicular top-to-bottom depth
ARM_THICKNESS = 2.5  # ch14: p.27 photo callout (plate thickness, Z)
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view, manual)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
CHAMFER = 5.588  # 0.22" tip chamfer, top-outer corners (ch.30 back-view sketch)
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft (DIMENSIONS.md ch14, derived)
ROD_HOLE_DIA = 2.0  # connecting-rod pin (photo-scaled, low)
ROD_HOLE_X = 25.4  # rod pin 1" from the pivot, +X side (derived, M6.3)
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


def _bottom_point(x: float) -> tuple[float, float]:
    return (x, CENTER_Y - math.sqrt(R_BOTTOM**2 - x * x))


def _mid_y(x: float) -> float:
    by = _bottom_point(x)[1]
    ty = CENTER_Y - math.sqrt(R_TOP**2 - x * x)
    return (by + ty) / 2.0


def _strap_area() -> float:
    """Cross-section area of the tapered strap (two arcs + two end lines) by
    shoelace over a densely-sampled boundary -- exact enough for the volume
    gate, and correct for the non-annular (tapered) shape the differing arc
    lengths produce."""
    n = 200
    pts: list[tuple[float, float]] = []
    # bottom arc, rod (+alpha) -> tail (-alpha)
    for i in range(n + 1):
        a = _ALPHA_BOT - 2.0 * _ALPHA_BOT * i / n
        pts.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    # top arc, tail (-alpha) -> rod (+alpha); the two arc-list transitions ARE
    # the tail-end and (wrap) rod-end lines, so shoelace closes the profile.
    for i in range(n + 1):
        a = -_ALPHA_TOP + 2.0 * _ALPHA_TOP * i / n
        pts.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
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
    await set_global(adapter, "ChamferSize", f"{CHAMFER}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    await set_global(adapter, "RodHoleDia", f"{ROD_HOLE_DIA}mm")
    await set_global(adapter, "RodHoleX", f"{ROD_HOLE_X}mm")
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

    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "strap bottom arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_b, *rod_b),
        ),
        check("strap rod end", await adapter.add_line(*rod_b, *rod_t)),
        check(
            "strap top arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_t, *rod_t),
        ),
        check("strap tail end", await adapter.add_line(*tail_b, *tail_t)),
    ]
    set_sketch_direct_db(adapter, False)
    bottom_arc, _rod_end, top_arc, _tail_end = entities
    # Two concentric arcs (top R800, bottom R816) + two tapered end lines. The
    # top arc (11.5" arc-len) and bottom arc (10.5") subtend DIFFERENT angles on
    # their radii, so the end lines slant inward (the profile tapers) -- the
    # radial end-line relations of the old uniform-depth strap are GONE. Each
    # arc's two endpoints are pinned by a horizontal_distance dim (x from the
    # origin, unsigned magnitude); the end lines ride the merged endpoints.
    # Dim EMISSION ORDER (record each as its display dim is created): the centre's
    # vertical_distance (x on-axis, so anchor_point_to_origin emits ONE dim =
    # CenterY), bottom radius, top radius, bottom-tail x, bottom-rod x, top-tail x,
    # top-rod x -- SEVEN display dims. The ``coincident`` concentric relation is a
    # RELATION, not a dim.
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

    # Connecting-rod pin hole 1 inch from the pivot, mid-depth. Off-axis centre:
    # define_circle emits centre-X, centre-Z, then diameter -- THREE dims. X is at
    # +RodHoleX (positive, drives "RodHoleX"); the centre-Z is the trig-derived
    # mid-height on the radial ray (no clean global knob) -> name/drive left None.
    rod_x = ROD_HOLE_X
    rod = SketchDims()
    check("create_sketch rod hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, rod_x, _mid_y(rod_x), ROD_HOLE_DIA / 2.0, "rod hole",
        dims=rod,
        names=("RodPinX", None, "RodHoleDia"),
        drives=('"RodHoleX"', None, '"RodHoleDia"'),
    )
    await ensure_fully_defined(adapter, "rod hole sketch")
    check("exit_sketch rod hole", await adapter.exit_sketch())
    name_last_feature(adapter, "RodHoleProfile")
    drive_jobs += rod.apply(adapter, "RodHoleProfile")
    check(
        "cut rod hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RodHole")
    # Named axis through the rod-pin bore (Axis2 = (Right+rod_x) ∩ (Top+mid_y)).
    await name_bore_axis(
        adapter, "Right Plane", rod_x, "Top Plane", _mid_y(rod_x), "rod bore"
    )

    # Both bores are full-thickness through the 2.5 strap, entirely inside the
    # material, so each removes pi*r^2*thickness.
    v_pivot = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * ARM_THICKNESS
    v_rod = math.pi * (ROD_HOLE_DIA / 2.0) ** 2 * ARM_THICKNESS
    await volume_check(
        adapter, "bored strap", v_strap - v_pivot - v_rod, 0.01 * v_strap
    )

    # 0.22" tip chamfers on the two top-outer corners (top arc meets the end
    # line), located by a point at mid-thickness (z 0) on each vertical corner
    # edge. Literal CHAMFER (not equation-driven): "ChamferSize" documents the
    # value; the chamfer feature's own dim is a simple GUI edit.
    check(
        "chamfer tips",
        await adapter.add_chamfer(
            CHAMFER, [[TOP_END_X, TOP_END_Y, 0.0], [-TOP_END_X, TOP_END_Y, 0.0]]
        ),
    )
    name_last_feature(adapter, "TipChamfer")
    # The tip corner is ~45deg (top-arc tangent vs end line), so the 45deg
    # angle-distance chamfer removes ~ a d^2/2 x thickness wedge per corner; the
    # corner-angle approximation is why the post-chamfer gate runs LOOSE (3%)
    # while the neutrality re-check below is tight against the MEASURED value.
    v_cham = 2.0 * 0.5 * CHAMFER**2 * ARM_THICKNESS
    v_measured = await volume_check(
        adapter,
        "chamfered rocker-arm",
        v_strap - v_pivot - v_rod - v_cham,
        0.03 * v_strap,
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
