r"""Reproduction script: amplitude bar (book ch. 15, pp. 30-33).

One of the 20 chrome-finished bars (~80 cm long, 1/4" square) that set each
channel's Fourier coefficient. The bottom-end notch rides the rocker arm;
the deeper top-end notch straddles the channel lever and hangs from its Ø2
bar pin through the top pin hole (M6.3 layout: bars run UP the spine from
the rocker bank to the top-lever bank).

Dimensions: cad/DIMENSIONS.md "Chapter 15" — width 6.35 mm is book-annotated,
length ~80 cm book-stated (legacy 32" = 812.8 mm consistent, used exactly);
notch sizes are uncontradicted legacy values; top pin hole derived (M6.3).
Audit verdict: PASS.

Profile (on the Front plane, bar length along +Y, origin at bottom-left
corner) is a single 12-segment chain; both notches are centred slots in the
end faces. Extruded by the bar depth (+Z, 0..6.35). The top pin hole runs
along global X through the top-slot cheeks at 6.35 below the bar top,
mid-depth (Z = 3.175): a Right-plane sketch maps local +X -> global -Z, so
the circle centre sits at sketch_x = -BarDepth/2 to land inside the body, and
the removed volume is asserted against analytic so a wrong side fails loud.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_amplitude_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    add_line_chain,
    apply_material,
    apply_color,
    BAR_STEEL,
    check,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    bbox_extent_check,
    measure_check,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes

import _telemetry

PART_NAME = "amplitude-bar"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

BAR_LENGTH = 32.0 * IN  # 812.8  DIMENSIONS.md ch15: ~80 cm stated; legacy 32" (high)
BAR_WIDTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: annotated (high)
BAR_DEPTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: legacy, square section (med)
BOTTOM_NOTCH_WIDTH = 0.125 * IN  # 3.175  DIMENSIONS.md ch15: legacy (med)
BOTTOM_NOTCH_HEIGHT = 0.09375 * IN  # 2.381  DIMENSIONS.md ch15: legacy 3/32" (med)
TOP_NOTCH_WIDTH = 0.125 * IN  # 3.175  DIMENSIONS.md ch15: legacy (med)
TOP_NOTCH_HEIGHT = 0.5 * IN  # 12.7   DIMENSIONS.md ch15: legacy (med)
# top pin hole: was Ø2.0 drill, now #47 (Ø1.994) native Hole Wizard feature
TOP_PIN_DROP = 0.25 * IN  # 6.35  DIMENSIONS.md ch15: hole centre below bar top (derived)

NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # notches centred on width


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the bar envelope, both notch sizes,
    # the top pin hole, and its drop below the bar top. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 812.8 = 812.8 in, 25.4x
    # too big). NotchOffset is derived (the notches are centred on the width),
    # so it tracks BarWidth/BottomNotchWidth edits.
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarWidth", f"{BAR_WIDTH}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BottomNotchWidth", f"{BOTTOM_NOTCH_WIDTH}mm")
    await set_global(adapter, "BottomNotchHeight", f"{BOTTOM_NOTCH_HEIGHT}mm")
    await set_global(adapter, "TopNotchWidth", f"{TOP_NOTCH_WIDTH}mm")
    await set_global(adapter, "TopNotchHeight", f"{TOP_NOTCH_HEIGHT}mm")
    # TopPinDrop stays a live knob: the top-pin bore AXIS drive references it
    # ('"BarLength" - "TopPinDrop"'). The pin DIAMETER is now the #47 drill
    # standard (Hole Wizard), so the old TopPinHoleDia knob is gone.
    await set_global(adapter, "TopPinDrop", f"{TOP_PIN_DROP}mm")
    await set_global(
        adapter, "NotchOffset", '("BarWidth" - "BottomNotchWidth") / 2'
    )

    # Each sketch's dim names + drive equations are recorded inline as the dims
    # are created (a per-sketch SketchDims), then renamed immediately; the drive
    # equations are collected here and applied in one deferred batch at the end
    # (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))

    # Clockwise from the origin at the bottom-left corner.
    points = [
        (0.0, 0.0),
        (NOTCH_OFFSET, 0.0),
        (NOTCH_OFFSET, BOTTOM_NOTCH_HEIGHT),
        (NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH, BOTTOM_NOTCH_HEIGHT),
        (NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH, 0.0),
        (BAR_WIDTH, 0.0),
        (BAR_WIDTH, BAR_LENGTH),
        (BAR_WIDTH - NOTCH_OFFSET, BAR_LENGTH),
        (BAR_WIDTH - NOTCH_OFFSET, BAR_LENGTH - TOP_NOTCH_HEIGHT),
        (BAR_WIDTH - NOTCH_OFFSET - TOP_NOTCH_WIDTH, BAR_LENGTH - TOP_NOTCH_HEIGHT),
        (BAR_WIDTH - NOTCH_OFFSET - TOP_NOTCH_WIDTH, BAR_LENGTH),
        (0.0, BAR_LENGTH),
    ]
    lines = await add_line_chain(adapter, points)

    horizontal = lines[0::2]  # even-index segments run along X
    vertical = lines[1::2]  # odd-index segments run along Y
    for ent in horizontal:
        check("constraint horizontal", await adapter.add_sketch_constraint(ent, None, "horizontal"))
    for ent in vertical:
        check("constraint vertical", await adapter.add_sketch_constraint(ent, None, "vertical"))

    # Ten driving dimensions; the last horizontal + closing vertical segment
    # lengths follow from profile closure. Each is recorded into ``profile`` in
    # creation order (= emission order) with its friendly name + drive equation;
    # all ten are positive segment lengths, so the drives evaluate positive (no
    # unsigned-distance negation needed). The notch ledges/widths/heights all
    # reference their globals; the two repeated spans (notch returns, the three
    # NotchOffset ledges) reuse the same global, so a single edit moves both
    # sides together.
    dims = [
        (lines[0], NOTCH_OFFSET, "bottom-left ledge", "BottomLeftLedge", '"NotchOffset"'),
        (lines[1], BOTTOM_NOTCH_HEIGHT, "bottom notch height", "BottomNotchHeight", '"BottomNotchHeight"'),
        (lines[2], BOTTOM_NOTCH_WIDTH, "bottom notch width", "BottomNotchWidth", '"BottomNotchWidth"'),
        (lines[3], BOTTOM_NOTCH_HEIGHT, "bottom notch return", "BottomNotchReturn", '"BottomNotchHeight"'),
        (lines[4], NOTCH_OFFSET, "bottom-right ledge", "BottomRightLedge", '"NotchOffset"'),
        (lines[5], BAR_LENGTH, "bar length", "BarLength", '"BarLength"'),
        (lines[6], NOTCH_OFFSET, "top-right ledge", "TopRightLedge", '"NotchOffset"'),
        (lines[7], TOP_NOTCH_HEIGHT, "top notch height", "TopNotchHeight", '"TopNotchHeight"'),
        (lines[8], TOP_NOTCH_WIDTH, "top notch width", "TopNotchWidth", '"TopNotchWidth"'),
        (lines[9], TOP_NOTCH_HEIGHT, "top notch return", "TopNotchReturn", '"TopNotchHeight"'),
    ]
    for ent, value, label, name, drive in dims:
        check(
            f"dimension {label} = {value:g}",
            await adapter.add_sketch_dimension(ent, None, "linear", value),
        )
        profile.record(name, drive)

    # The chain's first vertex sits on the origin; with the h/v relations
    # and the ten dims (closure covers the last two segment lengths) this
    # single anchor completes the 24-DOF profile.
    check(
        "anchor profile corner",
        await adapter.add_sketch_constraint(f"{lines[0]}.start", "origin", "coincident"),
    )
    await ensure_fully_defined(adapter, "bar profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    # Name + record-rename the profile BEFORE the extrude absorbs it (an
    # absorbed sketch drops off the top-level tree the namer walks). The anchor
    # is a coincident RELATION, not a display dim, so it is not recorded -- the
    # ten linear dims above are the full count apply() asserts against.
    name_last_feature(adapter, "BarProfile")
    drive_jobs += profile.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAR_DEPTH)),
    )
    name_last_feature(adapter, "Bar")
    # Drive the bar's extrude depth from BarDepth too (D1 is the blind-extrude
    # depth dim). The top-pin cut is driven to BarDepth/2 and the mate axes below
    # track BarDepth, so the BODY depth must move with them -- otherwise a GUI
    # edit of BarDepth leaves the hole/axes referencing a thickness the bar no
    # longer has. Evaluates to the as-built BAR_DEPTH, so it stays neutral.
    drive_jobs.append(("D1@Bar", '"BarDepth"'))

    # Top pin hole: was a plain Ø2.0 cut, now a native Hole Wizard #47 number
    # drill (Ø1.994) along global X through the top-slot cheeks, hanging the bar
    # from the channel lever's bar pin (memory/fastener-policy-us-customary).
    # Drilled from the +X side face (a clean planar face, normal +X) at mid-depth;
    # through-all clears both cheeks, and the slot gap between them removes nothing.
    # The removed volume is asserted against the two-cheek analytic (±2), so a
    # mislocated hole fails LOUD.
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    _telemetry.info(f"volume before top pin hole: {vol_before:.1f} mm^3")
    pin_y = BAR_LENGTH - TOP_PIN_DROP
    pin_dia = NUMBER_DRILL_MM["#47"]
    # cheeks total = bar width - slot width (the bore removes material only in the
    # two cheeks; the slot gap between them is already void)
    expected_removed = math.pi * (pin_dia / 2.0) ** 2 * (BAR_WIDTH - TOP_NOTCH_WIDTH)
    wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[BAR_WIDTH, pin_y, BAR_DEPTH / 2.0]],
        (1.0, 0.0, 0.0),
        "top pin hole (#47)",
        name="TopPinHole",
    )
    res = await adapter.get_mass_properties()
    removed = vol_before - res.data.volume
    if abs(removed - expected_removed) >= 2.0:
        raise RuntimeError(
            f"top pin cut removed {removed:.1f} mm^3, expected"
            f" {expected_removed:.1f} — hole misplaced/resized or wrong side"
        )
    _telemetry.success(
        f"top pin hole removed {removed:.1f} mm^3 (analytic {expected_removed:.1f})"
    )
    vol_final = res.data.volume

    # Named axes (parallel to the top-pin bore, view-independent selection):
    # Axis1 = top-pin bore at (y = pin_y, z = mid-depth) -- the hole runs along
    # local X, so the axis is (Top + pin_y) ∩ (Front + depth/2); Axis2 = a foot
    # reference axis at the bar bottom (y = 0), an ~806 mm lever arm from the
    # top pin that the assembly spin driver uses to pin the bar's swing.
    # Tie each axis's offset planes to the same globals that drive the bore/body,
    # so a GUI edit moves the named axes (and the channel-assembly mates to them)
    # in lockstep. pin_y = BarLength - TopPinDrop; mid-depth = BarDepth / 2. The
    # foot axis sits on the Top plane (offset 0, no dim to drive). Each equation
    # equals the as-built offset, so the placement stays neutral.
    await name_bore_axis(
        adapter, "Top Plane", pin_y, "Front Plane", BAR_DEPTH / 2.0, "top pin bore",
        drive_a='"BarLength" - "TopPinDrop"', drive_b='"BarDepth" / 2',
        drive_jobs=drive_jobs,
    )
    await name_bore_axis(
        adapter, "Top Plane", 0.0, "Front Plane", BAR_DEPTH / 2.0, "foot axis",
        drive_b='"BarDepth" / 2', drive_jobs=drive_jobs,
    )

    # Mid-width reference plane (local x = BarWidth/2, parallel to the Right
    # plane). The bar straddles the rocker arm and channel lever symmetrically,
    # so in the assembly -- placed Ry(90) at z_mid + BarWidth/2 -- THIS plane
    # lands exactly on the channel mid-plane (z_mid). Naming it lets the channel
    # assembly seat the bar by a COINCIDENT mate to the rocker/lever mid-plane (a
    # semantic "same channel slice" contact) instead of a bare distance to the
    # assembly datum. Driven by "BarWidth"/2 so a GUI width edit moves the plane
    # -- and the assembly mate to it -- in lockstep.
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        RenameFeatureParameters,
    )

    mid_plane = check(
        f"plane mid-width (Right + {BAR_WIDTH / 2.0:g})",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=BAR_WIDTH / 2.0
            )
        ),
    ).name
    check(
        "rename mid-width plane -> MidWidth",
        await adapter.rename_feature(
            RenameFeatureParameters(old_name=mid_plane, new_name="MidWidth")
        ),
    )
    drive_jobs.append(('D1@MidWidth', '"BarWidth" / 2'))

    # Apply the deferred drive equations now -- after the whole model + a
    # rebuild exists, so every target (BarProfile + TopPinProfile) resolves.
    # Each equation evaluates to the value just built, so the geometry must not
    # move; the volume re-check is the neutrality proof (vol_final is the
    # post-cut volume read back above).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven amplitude bar (equations neutral)", vol_final, 0.005 * vol_final
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, BAR_STEEL)  # ch30 plates: see _common palette

    # Verify the two book-sourced dims on the built solid (ch. 15).
    mid_y = BAR_LENGTH / 2.0
    await bbox_extent_check(adapter, "bar width (annotated 6.35)", "x", BAR_WIDTH)
    # End-face pair selection fails (the far face is hidden in the active
    # view and point picking is screen-projected) — use a long silhouette
    # edge instead; the notches only cut the end faces, so it runs full
    # length.
    await measure_check(
        adapter,
        "bar length (stated ~80 cm / legacy 32 in)",
        [{"entity_type": "EDGE", "point": [0.0, mid_y, BAR_DEPTH]}],
        "length",
        BAR_LENGTH,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
