r"""Reproduction script: tube frame column (legacy part; book ch. 5-6).

Hollow brass column carrying the upper frame rails: Ø1.375 in tube with a
0.12 in wall (legacy SLDPRT, interrogated live - no source survives).
Length corrected to the book: ch. 6 states the frame columns are 107 cm
tall, while the legacy file was 1016 mm (40 in); the book annotation wins
per the M1 source hierarchy, so this re-author uses 1070 mm.

M4 finishing pass: the photogrammetry (PHOTOS.md 195108425/195123524)
shows the columns fluted/reeded, not plain round. Modeled as 16 shallow
Ø3 mm full-length grooves (one seed cut at the OD, circular-patterned
about the column axis): both photos show ~5-6 ridges across the visible
face, ~16 around (estimate, cosmetic -- groove depth 1.5 mm stays well
inside the 3.05 mm wall).

Dimensions: cad/DIMENSIONS.md "Legacy part audit" - legacy diameters
(med), book length (stated, high), flute count/size photo-estimated (low).

Layout: tube axis along +Y (column standing upright), annulus sketched on
the Top plane at the origin, extruded upward.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_tube_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    measure_check,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "tube-frame"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

OUTER_DIA = 1.375 * IN  # legacy: Ø34.925 (no book numerics)
WALL_THICKNESS = 0.12 * IN  # legacy: 3.048 wall -> Ø28.829 bore
COLUMN_LENGTH = 1070.0  # ch.6: 107 cm column height (supersedes legacy 1016)

INNER_DIA = OUTER_DIA - 2.0 * WALL_THICKNESS

FLUTE_COUNT = 16  # photo estimate: ~5-6 ridges per visible face (low)
FLUTE_DIA = 3.0  # groove cutter dia; depth ~1.5 < 3.05 wall (low)


def flute_lens_area() -> float:
    """Cross-section area one groove removes (two-circle lens, mm^2).

    Intersection of the Ø3 cutter circle (centred ON the OD, so d = R)
    with the outer circle. At the OD the 16 grooves sit pi*34.925/16 =
    6.86 mm apart, ~3 mm wide each -> no overlap, areas simply add.
    """
    r = FLUTE_DIA / 2.0
    big = OUTER_DIA / 2.0
    d = big
    a_small = r * r * math.acos((d * d + r * r - big * big) / (2.0 * d * r))
    a_big = big * big * math.acos((d * d + big * big - r * r) / (2.0 * d * big))
    a_tri = 0.5 * math.sqrt(
        (-d + r + big) * (d + r - big) * (d - r + big) * (d + r + big)
    )
    return a_small + a_big - a_tri


async def volume_check(adapter, label: str, expected: float, tol: float) -> None:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {res.error}")
    volume = float(res.data.volume)
    if abs(volume - expected) > tol:
        raise RuntimeError(
            f"{label}: volume {volume:.1f} mm^3, expected {expected:.1f} (+/- {tol:.1f})"
        )
    print(f"  OK  {label}: volume {volume:.1f} mm^3 (analytic {expected:.1f})")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    check("create_sketch annulus", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, 0.0, 0.0, OUTER_DIA / 2.0, "outer circle")
    await define_circle(adapter, 0.0, 0.0, INNER_DIA / 2.0, "bore circle")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "annulus sketch")
    check("exit_sketch annulus", await adapter.exit_sketch())
    check(
        "extrude column",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLUMN_LENGTH)),
    )
    v_annulus = (
        math.pi * ((OUTER_DIA / 2.0) ** 2 - (INNER_DIA / 2.0) ** 2) * COLUMN_LENGTH
    )
    await volume_check(adapter, "annulus column", v_annulus, 0.001 * v_annulus)

    # M4 fluting: one Ø3 mm groove cut on the OD, patterned about the
    # column (Y) axis. See the docstring for the photo rationale.
    check("create_sketch flute", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, OUTER_DIA / 2.0, 0.0, FLUTE_DIA / 2.0, "flute seed")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "flute sketch")
    check("exit_sketch flute", await adapter.exit_sketch())
    flute_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=COLUMN_LENGTH)
    )
    check("cut flute seed", flute_cut)
    v_flute = flute_lens_area() * COLUMN_LENGTH
    await volume_check(adapter, "seed flute", v_annulus - v_flute, 0.01 * v_flute)

    check(
        "create_axis Y (Front x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Front Plane", "Right Plane"])
        ),
    )
    adapter._zoom_to_fit(adapter.currentModel)
    pattern = None
    for axis_point in (
        [0.0, COLUMN_LENGTH / 2.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.0, COLUMN_LENGTH, 0.0],
    ):
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=axis_point,
                features=[flute_cut.data.name],
                count=FLUTE_COUNT,
                geometry_pattern=True,
            )
        )
        if res.is_success:
            print(f"  OK  circular pattern axis via point {axis_point}")
            pattern = res
            break
        print(f"  ..  axis candidate {axis_point} failed: {res.error}")
    if pattern is None:
        raise RuntimeError("flute pattern: no axis candidate selectable")
    v_fluted = v_annulus - FLUTE_COUNT * v_flute
    await volume_check(
        adapter, "fluted column", v_fluted, 0.01 * FLUTE_COUNT * v_flute
    )

    await apply_material(adapter, MATERIAL)

    # Verify the book-stated 107 cm column height (the dim that
    # contradicted the legacy part) via the end annulus faces.
    mid_r = (OUTER_DIA + INNER_DIA) / 4.0
    await measure_check(
        adapter,
        "column length (stated 107 cm)",
        [
            {"entity_type": "FACE", "point": [mid_r, 0.0, 0.0]},
            {"entity_type": "FACE", "point": [mid_r, COLUMN_LENGTH, 0.0]},
        ],
        "normal_distance",
        COLUMN_LENGTH,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
