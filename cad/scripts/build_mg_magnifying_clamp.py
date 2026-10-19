r"""Reproduction script: magnifying-lever clamp (MHA-MG-02; book ch. 20 p. 48).

A vertical length of 7/16 in hex brass that slides along the magnifying lever
(#1559 owner ruling): the Ø6 lever passes through it across the corners, the
knurled #4-40 thumb screw enters the top face on the hex axis and pinches the
lever, and the MHA-MG-04 vertical rod screws into a blind #4-40 tap in the
bottom face, on the same axis, until its shoulder seats on that face.

Layout (part frame, ``mg_magnifying_clamp_geom``): origin at the bottom-face
centre, hex axis +Y, corners on +/-X, flats square to +/-Z.

* ``HexProfile``: the 7/16 hex on the Top plane (sketch (x, y) -> model
  (X, -Z)), corners on the sketch's horizontal axis, extruded +Y as ``Block``
  (``Height``).  Equal flats either side of the origin centre the hex axis,
  so neither the bore nor the taps need a location from a flat.
* ``LeverBoreProfile``: the Ø6.2 drilled lever bore, a Right-plane circle on
  the hex axis at ``LeverBoreYDim``, cut mid-plane through both corners.
* ``ThumbTap``: blind Hole Wizard #4-40 from the top face on the hex axis,
  thread ending at the bore, drill to the bore axis.
* ``RodTap``: blind Hole Wizard #4-40 from the bottom face on the hex axis
  (``mg_rod_clamp_joint.ROD_TAP_SPEC``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_clamp.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _holes import blind_hole_volume_mm3, cross_hole_volume_mm3, wizard_holes
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from mg_magnifying_clamp_geom import (
    BLOCK_HEIGHT,
    HEX_AC,
    HEX_AF,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_TAP_DRILL_DIA,
    THUMB_TAP_DRILL_DEPTH,
    THUMB_TAP_SPEC,
)
from mg_magnifying_clamp_spec import (
    AREA_HATCH_STYLE_PATTERN,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PREF_MATERIAL_HATCH_PATTERN,
    PREF_MATERIAL_HATCH_STYLE,
    PREF_NO_OPTION,
    SECTION_HATCH_PATTERN,
)
from mg_rod_clamp_joint import ROD_TAP_DRILL_DEPTH, ROD_TAP_SPEC

PART_NAME = "mg-magnifying-clamp"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

HEX_CORNER_RADIUS = HEX_AC / 2.0
BORE_R = LEVER_BORE_DIA / 2.0
DRILL_R = ROD_TAP_DRILL_DIA / 2.0
# The lever bore's mid-plane cut: past both corners.
BORE_CUT_DEPTH = HEX_AC + 2.0
# The corner radius is the flats over sqrt(3): the hex sketch's equation.
_CORNER_PER_AF = 1.0 / math.sqrt(3.0)

# --- Analytic volumes (mm^3) ---------------------------------------------------
V_HEX = math.sqrt(3.0) / 2.0 * HEX_AF**2 * BLOCK_HEIGHT
# The bore across the corners: over its cross-section the hex's chord along X
# is 2(R - |z|/sqrt(3)), so it removes 2R·πr² less (2/sqrt(3))·(4/3)r³
# (build_mg_output_fixture._bore_volume).
V_BORE = 2.0 * math.pi * HEX_CORNER_RADIUS * BORE_R**2 - 8.0 * BORE_R**3 / (
    3.0 * math.sqrt(3.0)
)
# The thumb tap drill to the bore axis, less its share of the bore's upper
# half; its point stops in the bore's air (mg_magnifying_clamp_spec proves it).
V_THUMB = (
    math.pi * DRILL_R**2 * THUMB_TAP_DRILL_DEPTH
    - cross_hole_volume_mm3(ROD_TAP_DRILL_DIA, LEVER_BORE_DIA) / 2.0
)
# The rod tap: a blind drill and point, wholly in solid under the bore.
V_ROD_TAP = blind_hole_volume_mm3(ROD_TAP_DRILL_DIA, ROD_TAP_DRILL_DEPTH)
V_TOTAL = V_HEX - V_BORE - V_THUMB - V_ROD_TAP


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("HexAf", HEX_AF),
        ("BlockHeight", BLOCK_HEIGHT),
        ("LeverBoreDia", LEVER_BORE_DIA),
        ("LeverBoreY", LEVER_BORE_Y),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Hex block: the bar's section on the Top plane, extruded up +Y --------
    drive_jobs += await _hex_profile(adapter)
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    (height,) = name_dimensions(adapter, "Block", ["Height"])
    drive_jobs.append((height, '"BlockHeight"'))
    volume = await volume_check(adapter, "hex block", V_HEX, 0.005 * V_HEX)
    await bbox_extent_check(adapter, "block height", "y", BLOCK_HEIGHT)
    await bbox_extent_check(adapter, "hex across the flats", "z", HEX_AF)
    await bbox_extent_check(adapter, "hex across the corners", "x", HEX_AC)

    # --- Lever bore along X through both corners ---------------------------------
    # On the hex axis (sketch x = 0 is model Z = 0), so define_circle emits the
    # height then the diameter -- the x slot is ignored.
    lever = SketchDims()
    check("create_sketch lever bore", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        LEVER_BORE_Y,
        BORE_R,
        "lever bore",
        dims=lever,
        names=("LeverCz", "LeverBoreYDim", "LeverBoreDiaDim"),
        drives=(None, '"LeverBoreY"', '"LeverBoreDia"'),
    )
    await ensure_fully_defined(adapter, "lever bore sketch")
    check("exit_sketch lever bore", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverBoreProfile")
    drive_jobs += lever.apply(adapter, "LeverBoreProfile")
    check(
        "cut lever bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBore")
    volume = await volume_check(adapter, "lever bore", volume - V_BORE, 0.01 * V_BORE)

    # --- Thumb-screw tap: top face, hex axis, into the lever bore ---------------
    thumb = wizard_holes(
        adapter,
        THUMB_TAP_SPEC,
        [[0.0, BLOCK_HEIGHT, 0.0]],
        (0.0, 1.0, 0.0),
        f"thumb-screw tap ({THUMB_TAP_SPEC.size} into the lever bore)",
        name="ThumbTap",
        expect_dia_mm=ROD_TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += thumb.placement_drive_jobs
    volume = await volume_check(
        adapter, "thumb-screw tap", volume - V_THUMB, 0.03 * V_THUMB
    )

    # --- Rod tap: bottom face (outward normal -Y), hex axis, blind -------------
    rod = wizard_holes(
        adapter,
        ROD_TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"vertical-rod tap ({ROD_TAP_SPEC.size} blind, MHA-MG-04 seat)",
        name="RodTap",
        expect_dia_mm=ROD_TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += rod.placement_drive_jobs
    volume = await volume_check(
        adapter, "vertical-rod tap", volume - V_ROD_TAP, 0.03 * V_ROD_TAP
    )

    # Named lever-bore axis (local X through (y=LEVER_BORE_Y, z=0)) so the clamp
    # rides the magnifying lever as a concentric slider in the assembly.
    await name_bore_axis(
        adapter, "Top Plane", LEVER_BORE_Y, "Front Plane", 0.0, "lever bore axis",
        drive_a='"LeverBoreY"', drive_jobs=drive_jobs,
    )

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven magnifying clamp (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    await apply_material(adapter, MATERIAL)
    _set_section_hatch(adapter)
    # ch20 p.47 (img07) + p.46: the clamp block is BLACKENED brass (reads
    # dark against the bright lever rod and the bright thumb screw).
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)

    # Places are the tolerance statement (drawing-guidelines.md rule 3): the
    # part carries them, the drawing reads them back.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


def _set_section_hatch(adapter: Any) -> None:
    """Give the part's Material Properties crosshatch the section pattern,
    after the material (which applies its own), and prove it by read-back:
    the drawing's section hatches from it (mg_magnifying_clamp_spec)."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    extension.SetUserPreferenceInteger(
        PREF_MATERIAL_HATCH_STYLE, PREF_NO_OPTION, AREA_HATCH_STYLE_PATTERN
    )
    extension.SetUserPreferenceString(
        PREF_MATERIAL_HATCH_PATTERN, PREF_NO_OPTION, SECTION_HATCH_PATTERN
    )
    style = int(
        extension.GetUserPreferenceInteger(PREF_MATERIAL_HATCH_STYLE, PREF_NO_OPTION)
    )
    pattern = str(
        extension.GetUserPreferenceString(PREF_MATERIAL_HATCH_PATTERN, PREF_NO_OPTION)
    )
    if style != AREA_HATCH_STYLE_PATTERN or pattern != SECTION_HATCH_PATTERN:
        raise RuntimeError(
            f"clamp material crosshatch read back style {style}, pattern "
            f"{pattern!r}; wanted {AREA_HATCH_STYLE_PATTERN}, {SECTION_HATCH_PATTERN!r}"
        )


async def _hex_profile(adapter: Any) -> list[tuple[str, str]]:
    """The 7/16 hex on the Top plane, corners on the sketch's horizontal axis.

    The ``build_mg_output_fixture._hex_profile`` technique turned a quarter:
    both corners sit on the horizontal through the origin (model X), each a
    corner radius off it; each flat is horizontal (model Z = +/-AF/2), with
    equal sides either side of it.  The two flats equal centre the origin
    between them; the corner radius tied to the flats makes the section
    regular.  The flats are dimensioned point to point across the hex, between
    the ends of the two flats at -X: in the projected top view those are its
    upper vertices, so the dimension above it draws no extension line along a
    flat and leaves the right-hand flat clear for the thumb tap's leader.
    """
    half_af, corner = HEX_AF / 2.0, HEX_CORNER_RADIUS
    points = [
        (corner, 0.0),
        (corner / 2.0, half_af),
        (-corner / 2.0, half_af),
        (-corner, 0.0),
        (-corner / 2.0, -half_af),
        (corner / 2.0, -half_af),
    ]
    hexd = SketchDims()
    check("create_sketch hex", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for flat in (lines[1], lines[4]):
        check(
            f"hex flat {flat} horizontal",
            await adapter.add_sketch_constraint(flat, None, "horizontal"),
        )
    for first, second in ((0, 1), (1, 2), (3, 4), (4, 5)):
        check(
            f"hex sides {first}={second}",
            await adapter.add_sketch_constraint(lines[first], lines[second], "equal"),
        )
    # Equal flats, equal halves: the hex axis centred between the flats.
    check(
        "hex flats equal (axis centred)",
        await adapter.add_sketch_constraint(lines[1], lines[4], "equal"),
    )
    corner_drive = f'"HexAf" * {_CORNER_PER_AF!r}'
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", corner, 0.0, "hex +X corner")
    hexd.record("HexCornerPlus", corner_drive)
    await anchor_point_to_origin(adapter, f"{lines[3]}.start", -corner, 0.0, "hex -X corner")
    hexd.record("HexCornerMinus", corner_drive)
    await dimension_between(
        adapter,
        f"{lines[1]}.end",
        f"{lines[4]}.start",
        "vertical_distance",
        HEX_AF,
        "hex across the flats",
    )
    hexd.record("HexAf", '"HexAf"')
    await ensure_fully_defined(adapter, "hex profile")
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    return hexd.apply(adapter, "HexProfile")


if __name__ == "__main__":
    sys.exit(run_build(build))
