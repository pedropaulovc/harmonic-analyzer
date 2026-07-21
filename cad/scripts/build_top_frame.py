r"""Reproduction script: top frame ring (ch. 30 eight-views; NEW part, 1 used).

Green cast rectangular ring clamping the four brass columns just below
their tops: rails 22 wide x 41 tall, corner bosses Ø48 bored Ø25.5 around
the Ø25.4 columns (OD rederived from the ch30 8-views, M6.11) at (x, z) =
(+/-197, +/-112). In the machine it sits
at y 999.7..1040.7; its west rail carries the two ball mounts of the
top-lever fulcrum shaft (seat 1040.7 + ball rise 25.2 = axis 1065.9) and
the summing lever hangs below it (M6.4). One rail carries a Ø17 clearance
bore at mid-span (z 0) for the counter-spring gooseneck post, which slides
through and drops below the plate (ch. 19; the real corner casting is bored
for the post). Summing places the post at machine x -197 (COLUMN_X, with a
composed Ry(180)), so the bore is cut at part x -197 to meet it (M6.12).
Identified in M6.3 from the
eight views (green ring at y ~ 1010-1055 in every view, columns
continuing above to their caps); no book chapter covers it directly.

Dimensions: cad/DIMENSIONS.md "Channel & top-frame layout" (med; boss OD
scaled, low).

Layout: plan profile in XZ centred on the origin, ring mid-plane extruded
both ways in Y (y -20.5..+20.5) - the assembly lifts it to 1020.2. Build
order: outer slab, window cut, THEN corner bosses, then column bores -
bosses after the window so the full Ø48 cylinder survives at the window
corners (the window rectangle passes within 15.6 of the boss centres,
well inside the Ø48 boss). All Top-plane sketches are symmetric in both
axes, so the (x, y) -> (X, -Z) handedness never matters. Boss volume
contribution is verified against a grid-integrated plan area (the
boss/band/window overlaps have no tidy closed form).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_top_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from top_frame_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    TOP_VIEW_NOTE,
)

PART_NAME = "top-frame"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

COLUMN_X = 197.0  # column stations (frame.SLDASM, M6.1)
COLUMN_Z = 112.0
RAIL_WIDTH = 22.0  # DIMENSIONS.md top-frame row (photo, med)
RING_HEIGHT = 41.0  # DIMENSIONS.md top-frame row (photo, med)
BOSS_DIA = 48.0  # corner boss around the column (scaled, low)
BORE_DIA = 25.5  # clamps the Ø25.4 column (0.1 slip; OD rederived from 8-views)
GOOSENECK_BORE_DIA = 17.0  # clearance for the Ø16 counter-spring post sliding
# through the rail mid-span (build_gooseneck); the post drops below the
# plate, gripped by the gooseneck-clamp above -- ch. 19. Fully inside the rail
# band (|x| 197 in 186..208), so a clean cylindrical cut.
GOOSENECK_X = -COLUMN_X  # The counter-spring post body sits at machine
# x -197: summing places the gooseneck at its COLUMN_X = -197 (with a
# composed Ry(180)), so the clearance bore is cut at x -COLUMN_X to coincide
# with the post body. At +COLUMN_X it bored the opposite rail and the post
# drilled solid casting (full Ø16x41 = 8243 mm^3 top-level interference,
# M6.12).
GOOSENECK_Z = 0.0  # rail mid-span (sketch y -> machine -Z; 0 is handedness-free)

OUTER_X = COLUMN_X + RAIL_WIDTH / 2.0  # 208
OUTER_Z = COLUMN_Z + RAIL_WIDTH / 2.0  # 123
INNER_X = COLUMN_X - RAIL_WIDTH / 2.0  # 186
INNER_Z = COLUMN_Z - RAIL_WIDTH / 2.0  # 101
THROUGH_CUT_DEPTH = 60.0  # mid-plane total; > ring height


def _boss_extra_area() -> float:
    """Plan area one boss adds beyond the rail band, grid-integrated.

    Inside the Ø48 circle but outside the band (outer rect minus window):
    the boss bulges past the outer corner AND into the window corner.
    """
    r = BOSS_DIA / 2.0
    step = 0.05
    n = int(2.0 * r / step)
    extra = 0.0
    for i in range(n):
        x = COLUMN_X - r + (i + 0.5) * step
        half_chord = r * r - (x - COLUMN_X) ** 2
        if half_chord <= 0.0:
            continue
        dz = math.sqrt(half_chord)
        z0, z1 = COLUMN_Z - dz, COLUMN_Z + dz
        for j in range(int((z1 - z0) / step) + 1):
            z = z0 + (j + 0.5) * step
            if z >= z1:
                break
            in_band = (abs(x) <= OUTER_X and abs(z) <= OUTER_Z) and not (
                abs(x) < INNER_X and abs(z) < INNER_Z
            )
            if not in_band:
                extra += step * step
    return extra


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive every
    # dimension below. A GUI fine-tune edits THESE (Tools > Equations) -- e.g.
    # RailWidth or BossDia -- never an auto "D7@Sketch3". The derived spans
    # (Outer*/Inner*) are equations of the primitives, so the rail band stays
    # centred on the column stations when a primitive changes.
    # Primitives carry an explicit ``mm`` unit: this is an INCH document (like
    # the rest of the codebase) and the equation manager evaluates BARE numbers
    # in document units, so an unsuffixed "416" would be read as 416 inches and
    # blow the part up 25.4x in-plane. Length-valued globals keep the arithmetic
    # in mm; the derived globals and dimension equations inherit the unit.
    await set_global(adapter, "ColumnX", f"{COLUMN_X}mm")
    await set_global(adapter, "ColumnZ", f"{COLUMN_Z}mm")
    await set_global(adapter, "RailWidth", f"{RAIL_WIDTH}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "GooseneckBoreDia", f"{GOOSENECK_BORE_DIA}mm")
    await set_global(adapter, "OuterX", '"ColumnX" + "RailWidth" / 2')
    await set_global(adapter, "OuterZ", '"ColumnZ" + "RailWidth" / 2')
    await set_global(adapter, "InnerX", '"ColumnX" - "RailWidth" / 2')
    await set_global(adapter, "InnerZ", '"ColumnZ" - "RailWidth" / 2')

    # Each sketch DECLARES its dim names + drive equations inline at the
    # define_* call; a per-sketch SketchDims records each dim in the exact order
    # the helper emits it, so naming lands structurally -- no positional list to
    # keep in lockstep with the helper, and a drift fails loud in apply(). The
    # drive equations are collected here and applied in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Outer slab. Name the sketch + its dims BEFORE the extrude absorbs it (an
    # absorbed sketch drops off the top-level tree the namer walks).
    outer = SketchDims()
    check("create_sketch outer", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, OUTER_X, OUTER_Z, "outer rectangle", dims=outer,
        name_width="Width", drive_width='2 * "OuterX"',
        name_depth="Depth", drive_depth='2 * "OuterZ"',
    )
    await ensure_fully_defined(adapter, "outer rectangle")
    check("exit_sketch outer", await adapter.exit_sketch())
    name_last_feature(adapter, "OuterProfile")
    drive_jobs += outer.apply(adapter, "OuterProfile")
    check(
        "extrude slab",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "OuterSlab")
    v_slab = 4.0 * OUTER_X * OUTER_Z * RING_HEIGHT
    await volume_check(adapter, "slab", v_slab, 0.001 * v_slab)

    # Window, leaving the 22-wide rail band.
    window = SketchDims()
    check("create_sketch window", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, INNER_X, INNER_Z, "window rectangle", dims=window,
        name_width="Width", drive_width='2 * "InnerX"',
        name_depth="Depth", drive_depth='2 * "InnerZ"',
    )
    await ensure_fully_defined(adapter, "window rectangle")
    check("exit_sketch window", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowProfile")
    drive_jobs += window.apply(adapter, "WindowProfile")
    check(
        "cut window",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WindowCut")
    v_ring = v_slab - 4.0 * INNER_X * INNER_Z * RING_HEIGHT
    await volume_check(adapter, "rail band", v_ring, 0.001 * v_ring)

    # Corner bosses (full Ø48 cylinders; restore the window corners). One circle
    # per corner, each driven to the column stations + BossDia.
    bosses = SketchDims()
    check("create_sketch bosses", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter, sx * COLUMN_X, sz * COLUMN_Z, BOSS_DIA / 2.0,
                f"boss ({sx:+.0f}, {sz:+.0f})", dims=bosses,
                names=(f"C{n}X", f"C{n}Z", f"C{n}Dia"),
                drives=('"ColumnX"', '"ColumnZ"', '"BossDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "bosses sketch")
    check("exit_sketch bosses", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += bosses.apply(adapter, "BossProfile")
    check(
        "extrude bosses",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CornerBosses")
    v_boss_extra = 4.0 * _boss_extra_area() * RING_HEIGHT
    v_bossed = v_ring + v_boss_extra
    await volume_check(adapter, "bosses", v_bossed, 0.005 * v_boss_extra + 50.0)

    # Column bores (entirely inside the bosses).
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter, sx * COLUMN_X, sz * COLUMN_Z, BORE_DIA / 2.0,
                f"bore ({sx:+.0f}, {sz:+.0f})", dims=bores,
                names=(f"C{n}X", f"C{n}Z", f"C{n}Dia"),
                drives=('"ColumnX"', '"ColumnZ"', '"BoreDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bores.apply(adapter, "BoreProfile")
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ColumnBores")
    v_bores = 4.0 * math.pi * (BORE_DIA / 2.0) ** 2 * RING_HEIGHT
    v_bored = v_bossed - v_bores
    await volume_check(adapter, "bored ring", v_bored, 0.005 * v_boss_extra + 50.0)

    # Counter-spring (gooseneck) clearance bore through the east rail mid-span:
    # the post slides through here and drops below the plate (build_gooseneck).
    # On-axis centre (z 0): only X + diameter are dims (the Z is a relation), so
    # define_circle records just those two -- the "Z" slot is ignored.
    gooseneck = SketchDims()
    check("create_sketch gooseneck bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, GOOSENECK_X, GOOSENECK_Z, GOOSENECK_BORE_DIA / 2.0, "gooseneck bore",
        dims=gooseneck,
        names=("X", "Z", "Dia"),
        drives=('"ColumnX"', None, '"GooseneckBoreDia"'),
    )
    await ensure_fully_defined(adapter, "gooseneck bore sketch")
    check("exit_sketch gooseneck bore", await adapter.exit_sketch())
    name_last_feature(adapter, "GooseneckProfile")
    drive_jobs += gooseneck.apply(adapter, "GooseneckProfile")
    check(
        "cut gooseneck bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "GooseneckBore")
    v_gn = math.pi * (GOOSENECK_BORE_DIA / 2.0) ** 2 * RING_HEIGHT
    v_final = v_bored - v_gn
    await volume_check(adapter, "gooseneck bore", v_final, 0.005 * v_boss_extra + 50.0)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven ring (equations neutral)", v_final, 0.005 * v_boss_extra + 50.0)

    # RingTop datum: a reference plane on the ring's TOP face (Y = +RingHeight/2 from
    # the mid-plane origin). frame.SLDASM mates it COINCIDENT to a column's TopEnd so
    # the ring caps the columns at the flush joint -- a physical seat, no distance mate.
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        "create_plane RingTop (Top Plane, +RingHeight/2)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=RING_HEIGHT / 2.0
            )
        ),
    )
    name_last_feature(adapter, "RingTop")
    # The plane remains selectable for the frame assembly mate while hidden in
    # part/assembly renders; shown reference geometry was visibly crossing the
    # otherwise clean isometric output.
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "RingTop", "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot select RingTop to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Top View Note": TOP_VIEW_NOTE,
            "Front View Note": FRONT_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
