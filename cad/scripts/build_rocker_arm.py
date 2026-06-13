r"""Reproduction script: rocker arm (book ch. 14, pp. 26-29; 20 used).

Thin matte-black steel strap that see-saws on its pivot shaft atop the
tapered support castings. Top edge concave upward with R = 800 mm (the
book states the radius equals the amplitude-bar length, minimizing
nonlinearity as the bar slides); bottom edge concentric, giving a uniform
16 mm depth (p.29 photo callout spans the end face). Plate thickness
2.5 mm (p.27 callout - the M1 table misread this as a 12.5 mm "arm
width"). Mid-pivot SEESAW, symmetric +/-88 mm: the amplitude bar rides
either side of the pivot up to the measuring stick's 80 mm span (positive
one side, negative the other - ch. 15 text); the connecting rod pins at
+25.4 (1") on the +X side, closing the vertical-rod geometry against the
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

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_rocker_arm.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "rocker-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

CURVE_RADIUS = 800.0  # DIMENSIONS.md ch14: = amplitude bar length (stated)
ARM_DEPTH = 16.0  # ch14: p.29 photo callout, end-face height (annotated)
ARM_THICKNESS = 2.5  # ch14: p.27 photo callout (annotated)
ROD_SPAN = 88.0  # pivot -> rod-side end: 80 amplitude travel + 8 margin (derived)
TAIL_SPAN = 88.0  # pivot -> opposite end, symmetric seesaw (derived)
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

    tail_b = _bottom_point(-TAIL_SPAN)
    rod_b = _bottom_point(ROD_SPAN)
    tail_t = _top_point_radial(-TAIL_SPAN)
    rod_t = _top_point_radial(ROD_SPAN)

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
    await anchor_point_to_origin(
        adapter, f"{bottom_arc}.center", 0.0, CENTER_Y, "arc centre"
    )
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
    check(
        "top radius",
        await adapter.add_sketch_dimension(top_arc, None, "radial", R_TOP),
    )
    check(
        "tail span",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.start", "origin", "horizontal_distance", TAIL_SPAN
        ),
    )
    check(
        "rod span",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.end", "origin", "horizontal_distance", ROD_SPAN
        ),
    )
    for label, line in (("rod end", rod_end), ("tail end", tail_end)):
        check(
            f"{label} radial",
            await adapter.add_sketch_constraint(
                f"{bottom_arc}.center", line, "coincident"
            ),
        )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ARM_THICKNESS, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after strap: {res.data.volume:.1f} mm^3")
    # expected: asin(88/816) * (816^2 - 800^2) * 2.5 = ~6,985 mm^3

    # Pivot pin hole at the origin, mid-depth.
    check("create_sketch pivot hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, _mid_y(0.0), PIVOT_HOLE_DIA / 2.0, "pivot hole")
    await ensure_fully_defined(adapter, "pivot hole sketch")
    check("exit_sketch pivot hole", await adapter.exit_sketch())
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    # Named axis through the pivot bore (Axis1): assembly mates select it by
    # NAME (Right ∩ Top+8), view-independent -- an internal bore wall never
    # selects by screen-projected point. See _common.name_bore_axis.
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", _mid_y(0.0), "pivot bore"
    )

    # Connecting-rod pin hole 1 inch from the pivot, mid-depth.
    rod_x = ROD_HOLE_X
    check("create_sketch rod hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, rod_x, _mid_y(rod_x), ROD_HOLE_DIA / 2.0, "rod hole")
    await ensure_fully_defined(adapter, "rod hole sketch")
    check("exit_sketch rod hole", await adapter.exit_sketch())
    check(
        "cut rod hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    # Named axis through the rod-pin bore (Axis2 = (Right+rod_x) ∩ (Top+mid_y)).
    await name_bore_axis(
        adapter, "Right Plane", rod_x, "Top Plane", _mid_y(rod_x), "rod bore"
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
