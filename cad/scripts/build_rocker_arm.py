r"""Reproduction script: rocker arm (book ch. 14, pp. 26-29; 20 used).

Thin matte-black steel strap that see-saws on its pivot shaft atop the
tapered support castings. Top edge concave upward with R = 800 mm (the
book states the radius equals the amplitude-bar length, minimizing
nonlinearity as the bar slides); bottom edge concentric, giving a uniform
16 mm depth (p.29 photo callout spans the end face). Plate thickness
2.5 mm (p.27 callout - the M1 table misread this as a 12.5 mm "arm
width"). Mid-pivot SEESAW, symmetric +/-146.05 mm (5.75", 11.5" total arm): measured
MANUALLY from the ch. 30 back view. The prior photo-scaled value was
+/-114.3 mm (4.5"), read off the p.29 broadside photo (img id 285) - pivot
ball, rod-pin hole and the 16 mm depth callout gave a dual scale
(~8.1-8.6 px/mm), pivot->tip span 113-119 mm (central ~116), rounded then to
a clean imperial 4.5" (9" total); the ch. 30 back view resolves the tips more
directly. Still supersedes the indirect "80 mm bar travel + 8 mm margin"
estimate (88) the M6.3 row used.
The amplitude bar rides either side of the pivot the full half-length
(positive one side, negative the other - ch. 15 text: the bar "can slide
completely off the rocker"); the connecting rod pins at
+25.4 (1") on the +X side (photo-confirmed at +25 mm), closing the
vertical-rod geometry against the
cylinder arbor (M6.3, DIMENSIONS.md ch. 14 layout table). The "stepped
blocks" at the arm tips on p.29 are amplitude-bar feet parked near max
amplitude, not part of this strap.

This supersedes the legacy `oscilating-arms` part (no surviving source)
and the M2 asymmetric 100/70 rod-at-tip geometry (refuted in M6.3).

Dimensions: cad/DIMENSIONS.md "Chapter 14" - annotated thickness/depth,
stated curvature, derived spans/pin positions (med).

Layout: pivot at the origin, arm along X (+X = connecting-rod side), arc
center 816 mm above, extruded mid-plane in Z; holes cut through Z. The
pivot hole centre sits at local (0, 8) - assembly scripts must offset
placements accordingly.

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

CURVE_RADIUS = 800.0  # DIMENSIONS.md ch14: = amplitude bar length (stated)
ARM_DEPTH = 16.0  # ch14: p.29 photo callout, end-face height (annotated)
ARM_THICKNESS = 2.5  # ch14: p.27 photo callout (annotated)
ROD_SPAN = 146.05  # pivot -> rod-side end = 5.75" (11.5" total arm, user override)
TAIL_SPAN = 146.05  # pivot -> opposite end, symmetric seesaw (ch.15)
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft (DIMENSIONS.md ch14, derived)
ROD_HOLE_DIA = 2.0  # connecting-rod pin (photo-scaled, low)
ROD_HOLE_X = 25.4  # rod pin 1" from the pivot, +X side (derived, M6.3)
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > thickness

# Arc centre sits ARM_DEPTH above the pivot's bottom edge: bottom edge is
# an R816 arc, top edge the concentric R800 arc through (0, 16).
CENTER_Y = CURVE_RADIUS + ARM_DEPTH
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH


def _bottom_point(x: float) -> tuple[float, float]:
    return (x, CENTER_Y - math.sqrt(R_BOTTOM**2 - x * x))


def _top_point_radial(x: float) -> tuple[float, float]:
    """Top-edge point on the same radial ray as the bottom point at ``x``."""
    bx, by = _bottom_point(x)
    scale = R_TOP / R_BOTTOM
    return (bx * scale, CENTER_Y - (CENTER_Y - by) * scale)


def _mid_y(x: float) -> float:
    by = _bottom_point(x)[1]
    ty = CENTER_Y - math.sqrt(R_TOP**2 - x * x)
    return (by + ty) / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive every
    # sketch dimension below. A GUI fine-tune edits THESE (Tools > Equations) --
    # e.g. CurveRadius or RodSpan -- never an auto "D3@Sketch1". The mm suffix is
    # load-bearing: this is an INCH document and the equation manager evaluates
    # BARE numbers in document units, so an unsuffixed "800" would read as 800
    # inches and blow the part up 25.4x. The derived globals (RTop/RBottom/CenterY
    # = the concentric arc radii + their shared centre height) are equations of
    # the primitives, so the two arcs stay concentric and ArmDepth-apart when a
    # primitive changes.
    await set_global(adapter, "CurveRadius", f"{CURVE_RADIUS}mm")
    await set_global(adapter, "ArmDepth", f"{ARM_DEPTH}mm")
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "RodSpan", f"{ROD_SPAN}mm")
    await set_global(adapter, "TailSpan", f"{TAIL_SPAN}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    await set_global(adapter, "RodHoleDia", f"{ROD_HOLE_DIA}mm")
    await set_global(adapter, "RodHoleX", f"{ROD_HOLE_X}mm")
    await set_global(adapter, "ThroughCutDepth", f"{THROUGH_CUT_DEPTH}mm")
    await set_global(adapter, "RTop", '"CurveRadius"')
    await set_global(adapter, "RBottom", '"CurveRadius" + "ArmDepth"')
    await set_global(adapter, "CenterY", '"CurveRadius" + "ArmDepth"')

    # Each sketch DECLARES its dim names + drive equations as it records them; the
    # drive equations are collected here and applied in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    tail_b = _bottom_point(-TAIL_SPAN)
    rod_b = _bottom_point(ROD_SPAN)
    tail_t = _top_point_radial(-TAIL_SPAN)
    rod_t = _top_point_radial(ROD_SPAN)

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
    bottom_arc, rod_end, top_arc, tail_end = entities
    # 10-DOF profile of two concentric arcs + two radial end lines:
    # bottom centre anchored on the axis, top centre coincident with it,
    # one radial dim each, the bottom endpoints spanned from the origin;
    # each end line is a radial ray, so a point-on-line coincident with
    # the centre pins the top endpoints' angles (the lines themselves
    # ride their merged ends).
    # Dim EMISSION ORDER for the strap profile (record each into ``strap`` as the
    # display dim is created): the centre's vertical_distance (x is on-axis, so
    # anchor_point_to_origin emits ONE dim = CenterY), then bottom radius, top
    # radius, tail span, rod span -- FIVE display dims. The two ``coincident``
    # relations (concentric arcs, radial end lines) are RELATIONS, not dims.
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
    # Tail endpoint is at x = -TailSpan; the horizontal_distance dim displays the
    # MAGNITUDE, so its drive must be POSITIVE -- "TailSpan" is already +.
    check(
        "tail span",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.start", "origin", "horizontal_distance", TAIL_SPAN
        ),
    )
    strap.record("TailSpan", '"TailSpan"')
    check(
        "rod span",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.end", "origin", "horizontal_distance", ROD_SPAN
        ),
    )
    strap.record("RodSpan", '"RodSpan"')
    for label, line in (("rod end", rod_end), ("tail end", tail_end)):
        check(
            f"{label} radial",
            await adapter.add_sketch_constraint(
                f"{bottom_arc}.center", line, "coincident"
            ),
        )
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
    # Annular sector (two concentric arcs + radial ends): area =
    # 1/2 * 2*asin(span/RBottom) * (RBottom^2 - RTop^2), x thickness.
    v_strap = (
        math.asin(ROD_SPAN / R_BOTTOM)
        * (R_BOTTOM**2 - R_TOP**2)
        * ARM_THICKNESS
    )
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
    v_final = v_strap - v_pivot - v_rod
    await volume_check(adapter, "bored strap", v_final, 0.01 * v_strap)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rocker-arm (equations neutral)", v_final, 0.01 * v_strap
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
