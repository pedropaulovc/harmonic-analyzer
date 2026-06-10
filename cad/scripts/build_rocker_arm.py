r"""Reproduction script: rocker arm (book ch. 14, pp. 26-29; 20 used).

Thin matte-black steel strap that see-saws on a knife-edge pivot atop the
A-frame supports. Top edge concave upward with R = 800 mm (the book states
the radius equals the amplitude-bar length, minimizing nonlinearity as the
bar slides); bottom edge concentric, giving a uniform 16 mm depth (p.29
photo callout spans the end face). Plate thickness 2.5 mm (p.27 callout -
the M1 table misread this as a 12.5 mm "arm width"; corrected with this
script). Pivot-asymmetric: ~100 mm to the connecting-rod end, ~70 mm tail
for the amplitude bar's 180-degree phase-reversal side (p.29 bottom photo;
the working half matches the measuring stick's 10 x 8 mm divisions,
ch. 16). The stepped blocks visible at the arm tips on p.29 are the
connecting rods' flattened upper ends - separate part, not this strap.

This supersedes the legacy `oscilating-arms` part (no surviving source;
its audit row carried the misread 12.5 mm width).

Dimensions: cad/DIMENSIONS.md "Chapter 14" - annotated thickness/depth,
stated curvature, photo-scaled lengths (low-med).

Layout: pivot at the origin, arm along X (+X = connecting-rod end), arc
center 816 mm above, extruded mid-plane in Z; holes cut through Z.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_rocker_arm.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "rocker-arm"

CURVE_RADIUS = 800.0  # DIMENSIONS.md ch14: = amplitude bar length (stated)
ARM_DEPTH = 16.0  # ch14: p.29 photo callout, end-face height (annotated)
ARM_THICKNESS = 2.5  # ch14: p.27 photo callout (annotated)
ROD_SPAN = 100.0  # pivot -> connecting-rod end (photo-scaled, low)
TAIL_SPAN = 70.0  # pivot -> phase-reversal tail end (photo-scaled, low)
PIVOT_HOLE_DIA = 3.0  # pivot pin (photo-scaled, low)
ROD_HOLE_DIA = 2.0  # connecting-rod pin (photo-scaled, low)
ROD_HOLE_INSET = 6.0  # hole centre from the rod end
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
    await ensure_fully_defined(adapter, "strap sketch", fix_entities=entities)
    check("exit_sketch strap", await adapter.exit_sketch())
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ARM_THICKNESS, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after strap: {res.data.volume:.1f} mm^3")
    # expected: ~0.2086/2 * (816^2 - 800^2) * 2.5 = ~6,742 mm^3

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

    # Connecting-rod pin hole near the rod end, mid-depth.
    rod_x = ROD_SPAN - ROD_HOLE_INSET
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

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
