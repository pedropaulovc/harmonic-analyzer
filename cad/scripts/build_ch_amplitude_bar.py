r"""Reproduction script: amplitude bar (book ch. 15, pp. 30-33).

One of the 20 chrome-finished bars (~81 cm long, 1/4" square) that set each
channel's Fourier coefficient. The bottom-end notch rides the rocker arm;
the deeper top-end notch straddles the channel lever and hangs from the
MHA-CH-011 bar pivot pin pressed through the top pin hole (M6.3 layout: bars
run UP the spine from the rocker bank to the top-lever bank).

Dimensions: cad/DIMENSIONS.md "Chapter 15" — width 6.35 mm is book-annotated,
length legacy 32" = 812.8 mm SHORTENED 4.5 at the top to 808.3 by the
2026-08-02 top-frame rederive (fulcrum chain -4.5: bar top 1067.75, top pin
1061.4; foot/arc contact unchanged, level d=0 rest pose preserved);
notch sizes are uncontradicted legacy values; top pin hole derived (M6.3).
Audit verdict: PASS.

Profile (on the Front plane, bar length along +Y, origin at bottom-left
corner) is a single 12-segment chain; both notches are centred slots in the
end faces. Extruded by the bar depth (+Z, 0..6.35). The top pin hole -- a
Ø1.968 +0.010/0 reamed press hole for the 5/64 pin -- runs along global X
through the top-slot cheeks at 6.35 below the bar top, mid-depth
(Z = 3.175): a Right-plane sketch maps local +X -> global -Z, so the circle
centre sits at sketch_x = -BarDepth/2 to land inside the body, and the
removed volume is asserted against analytic so a wrong side fails loud.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_amplitude_bar.py
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
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    bbox_extent_check,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from ch_amplitude_bar_drawing_spec import SURFACE_FINISHES
from ch_amplitude_bar_notes import DRAWING_NOTES, END_VIEW_NOTE, ISOMETRIC_VIEW_NOTE
from ch_amplitude_bar_spec import (
    BOTTOM_NOTCH_DEPTH_BAND,
    BOTTOM_NOTCH_OFFSET,
    BOTTOM_NOTCH_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    NOTCH_OFFSET_TOLERANCE_MM,
    NOTCH_WIDTH_BAND,
    TOP_NOTCH_OFFSET,
    TOP_NOTCH_WIDTH,
    TOP_PIN_HOLE_BAND,
    TOP_PIN_HOLE_DIA,
)

import _telemetry

PART_NAME = "ch-amplitude-bar"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

BAR_LENGTH = 32.0 * IN - 4.5  # 808.3: legacy 32" minus the 4.5 top-frame-rederive
# top trim (fulcrum chain -4.5, 2026-08-02; foot end untouched). MUST equal
# ch_amplitude_bar_spec.BAR_LENGTH.
BAR_WIDTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: annotated (high)
BAR_DEPTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: legacy, square section (med)
# Notch widths: ch_amplitude_bar_spec derives each from the plate it straddles
# (was the legacy 1/8" = 3.175; user ruling 2026-09-27, #1038).
BOTTOM_NOTCH_HEIGHT = 0.09375 * IN  # 2.381  DIMENSIONS.md ch15: legacy 3/32" (med)
TOP_NOTCH_HEIGHT = 0.5 * IN  # 12.7   DIMENSIONS.md ch15: legacy (med)
# top pin hole: was Ø2.0 drill, then #47 (Ø1.994) Hole Wizard; now the
# Ø1.968 +0.010/0 reamed press hole for the MHA-CH-011 pin (a sketch cut: the
# Hole Wizard has no reamed-size table)
TOP_PIN_DROP = 0.25 * IN  # 6.35  DIMENSIONS.md ch15: hole centre below bar top (derived)
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > the bar width


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the bar envelope, both notch sizes,
    # the top pin hole, and its drop below the bar top. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 812.8 = 812.8 in, 25.4x
    # too big). Each end's NotchOffset is derived (the notches are centred on
    # the width), so it tracks BarWidth and its own notch width.
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarWidth", f"{BAR_WIDTH}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BottomNotchWidth", f"{BOTTOM_NOTCH_WIDTH}mm")
    await set_global(adapter, "BottomNotchHeight", f"{BOTTOM_NOTCH_HEIGHT}mm")
    await set_global(adapter, "TopNotchWidth", f"{TOP_NOTCH_WIDTH}mm")
    await set_global(adapter, "TopNotchHeight", f"{TOP_NOTCH_HEIGHT}mm")
    # TopPinDrop stays a live knob: the top-pin bore AXIS drive references it
    # ('"BarLength" - "TopPinDrop"'). TopPinDia is the reamed press hole.
    await set_global(adapter, "TopPinDrop", f"{TOP_PIN_DROP}mm")
    await set_global(adapter, "TopPinDia", f"{TOP_PIN_HOLE_DIA}mm")
    await set_global(
        adapter, "BottomNotchOffset", '("BarWidth" - "BottomNotchWidth") / 2'
    )
    await set_global(adapter, "TopNotchOffset", '("BarWidth" - "TopNotchWidth") / 2')

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
        (BOTTOM_NOTCH_OFFSET, 0.0),
        (BOTTOM_NOTCH_OFFSET, BOTTOM_NOTCH_HEIGHT),
        (BOTTOM_NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH, BOTTOM_NOTCH_HEIGHT),
        (BOTTOM_NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH, 0.0),
        (BAR_WIDTH, 0.0),
        (BAR_WIDTH, BAR_LENGTH),
        (BAR_WIDTH - TOP_NOTCH_OFFSET, BAR_LENGTH),
        (BAR_WIDTH - TOP_NOTCH_OFFSET, BAR_LENGTH - TOP_NOTCH_HEIGHT),
        (BAR_WIDTH - TOP_NOTCH_OFFSET - TOP_NOTCH_WIDTH, BAR_LENGTH - TOP_NOTCH_HEIGHT),
        (BAR_WIDTH - TOP_NOTCH_OFFSET - TOP_NOTCH_WIDTH, BAR_LENGTH),
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
    # reference their globals; the repeated spans (notch returns, the two
    # BottomNotchOffset ledges) reuse the same global, so a single edit moves
    # both sides together.
    dims = [
        (lines[0], BOTTOM_NOTCH_OFFSET, "bottom-left ledge", "BottomLeftLedge", '"BottomNotchOffset"'),
        (lines[1], BOTTOM_NOTCH_HEIGHT, "bottom notch height", "BottomNotchHeight", '"BottomNotchHeight"'),
        (lines[2], BOTTOM_NOTCH_WIDTH, "bottom notch width", "BottomNotchWidth", '"BottomNotchWidth"'),
        (lines[3], BOTTOM_NOTCH_HEIGHT, "bottom notch return", "BottomNotchReturn", '"BottomNotchHeight"'),
        (lines[4], BOTTOM_NOTCH_OFFSET, "bottom-right ledge", "BottomRightLedge", '"BottomNotchOffset"'),
        (lines[5], BAR_LENGTH, "bar length", "BarLength", '"BarLength"'),
        (lines[6], TOP_NOTCH_OFFSET, "top-right ledge", "TopRightLedge", '"TopNotchOffset"'),
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

    # Reamed press hole through the top-slot cheeks. The removed volume is
    # asserted against both cheeks so a misplaced hole fails loud.
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    _telemetry.info(f"volume before top pin hole: {vol_before:.1f} mm^3")
    pin_y = BAR_LENGTH - TOP_PIN_DROP
    expected_removed = (
        math.pi * (TOP_PIN_HOLE_DIA / 2.0) ** 2 * (BAR_WIDTH - TOP_NOTCH_WIDTH)
    )
    pin_hole = SketchDims()
    check("create_sketch top pin hole", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        -BAR_DEPTH / 2.0,
        pin_y,
        TOP_PIN_HOLE_DIA / 2.0,
        "top pin hole",
        dims=pin_hole,
        names=("TopPinX", "TopPinY", "TopPinDia"),
        drives=('"BarDepth" / 2', '"BarLength" - "TopPinDrop"', '"TopPinDia"'),
    )
    await ensure_fully_defined(adapter, "top pin hole sketch")
    check("exit_sketch top pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "TopPinProfile")
    drive_jobs += pin_hole.apply(adapter, "TopPinProfile")
    check(
        "cut top pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "TopPinHole")
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
    # reference axis at the bar bottom (y = 0), an ~802 mm lever arm from the
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
    blank_reference_geometry(adapter, (("MidWidth", "PLANE"),))

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
    await bbox_extent_check(adapter, "bar width (annotated 6.35)", "x", BAR_WIDTH)
    # A point-picked long edge is view-dependent: the back silhouette is hidden
    # in some SolidWorks sessions and selection then fails before measurement.
    # The end notches do not change the Y extent, so the bounding box is the
    # direct, view-independent proof of the book-sourced overall length.
    await bbox_extent_check(
        adapter,
        "bar length (32 in - 4.5 top trim = 808.3)",
        "y",
        BAR_LENGTH,
    )

    await report_mass_properties(adapter)

    # Manufacturing drawing support: the foot notch may only come out shallow
    # (ch_amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND), natively on its depth;
    # each notch may only come out wider than the plate it straddles
    # (NOTCH_WIDTH_BAND, #1038) and is centred by the band on the ledge its
    # detail prints; author every printed dimension's places, mark exactly
    # the print's dimensions and stamp the make-critical title-block properties.
    set_dimension_bilateral_tolerance(
        adapter,
        "BarProfile",
        "BottomNotchHeight",
        *deviations(BOTTOM_NOTCH_DEPTH_BAND),
    )
    set_dimension_bilateral_tolerance(
        adapter, "BarProfile", "BottomNotchWidth", *deviations(NOTCH_WIDTH_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BarProfile", "TopNotchWidth", *deviations(NOTCH_WIDTH_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "BarProfile", "BottomLeftLedge", NOTCH_OFFSET_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter, "BarProfile", "TopRightLedge", NOTCH_OFFSET_TOLERANCE_MM
    )
    # The reamed press hole's band rides natively on its diameter; the sheet
    # states it in note 3 (the hole is dimensioned in the notes).
    set_dimension_bilateral_tolerance(
        adapter, "TopPinProfile", "TopPinDia", *deviations(TOP_PIN_HOLE_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The foot notch floor's roughness lives on the MODEL as a plain annotation.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "End View Note": END_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Isometric View Note", "End View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
