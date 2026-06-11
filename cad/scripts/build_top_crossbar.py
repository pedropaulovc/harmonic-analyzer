r"""Reproduction script: top crossbar (book ch. 18, pp. 42-43).

The green cast bar spanning the top-frame ring front-to-back (along Z)
at the machine's x mid-line: it carries the knife-mount stud that hangs
the summing-lever knife bar. Same 22 x 41 section as the ring rails
(build_top_frame.py), 202 long: its ends sit face-flush on the ring
window's north/south faces at z +/-101 (INNER_Z; the M6.4 372 span used
the ring's inner X span by mistake and buried both ends in the rails).
A O8.2 vertical hole at its centre passes the O8 stud.

Layout: origin on the stud-hole axis at the bar's bottom face (machine
(15, 999.7, 0)); bar +Y 41, +-Z 186. Dimensions: cad/DIMENSIONS.md
ch. 18 (rail section med, hole low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_top_crossbar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "top-crossbar"
MATERIAL = "Gray Cast Iron"  # green casting

BAR_HALF_X = 11.0  # rail section 22 wide (DIMENSIONS.md ch6, med)
BAR_HEIGHT = 41.0  # rail section 41 tall (med)
BAR_HALF_Z = 101.0  # ends flush on the ring window faces at z +/-101 (derived)
HOLE_DIA = 8.2  # knife-mount O8 stud passes through (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch bar", await adapter.create_sketch("Front"))
    outline = await add_line_chain(
        adapter,
        [
            (-BAR_HALF_X, 0.0),
            (BAR_HALF_X, 0.0),
            (BAR_HALF_X, BAR_HEIGHT),
            (-BAR_HALF_X, BAR_HEIGHT),
        ],
    )
    await ensure_fully_defined(adapter, "bar sketch", fix_entities=outline)
    check("exit_sketch bar", await adapter.exit_sketch())
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * BAR_HALF_Z, both_directions=True)
        ),
    )

    check("create_sketch stud hole", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, HOLE_DIA / 2.0, "stud hole")
    await ensure_fully_defined(adapter, "stud hole sketch")
    check("exit_sketch stud hole", await adapter.exit_sketch())
    check(
        "cut stud hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_HEIGHT + 10.0, both_directions=True)
        ),
    )

    expected = (
        2.0 * BAR_HALF_X * BAR_HEIGHT * 2.0 * BAR_HALF_Z
        - math.pi * (HOLE_DIA / 2.0) ** 2 * BAR_HEIGHT
    )
    res = await adapter.get_mass_properties()
    vol = float(res.data.volume) if res.is_success else float("nan")
    print(f"  volume: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"volume {vol:.1f} != analytic {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
