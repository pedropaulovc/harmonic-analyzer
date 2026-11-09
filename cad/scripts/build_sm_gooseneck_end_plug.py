r"""Build MHA-SM-05, the gooseneck end plug: a turned 1018 plug, tapped #10-24.

Owner rulings 2026-11-08 (Pedro), #2315: the end plug is its own part, with
its own drawing and MHA-SM-00 BOM row, bonded into MHA-SM-01's faced arm end
with LOCTITE 638 at MHA-SM-00.  A solid head Ø PLUG_DIA, flush with the tube,
runs PLUG_HEAD_LENGTH from the end face to the tube end; a spigot Ø
PLUG_SHANK_DIA (turned to the measured tube bore, ``sm_gooseneck_spring_joint``)
runs PLUG_SHANK_LENGTH beyond it into the bore.  The head is tapped #10-24
UNC-2B BLIND before bonding for the purchased MHA-SM-VN-56 shoulder screw
(owner ruling 2026-11-08 (Pedro), #2144 item 11.4: plain tap, no counterbore).
Decimal-inch document and sheet (#290, the registry row's drawing_unit).

One solid body, built in this order:

1. ``EndPlug``: one revolve of ``EndPlugProfile``, the half-section on the
   Front plane about the plug's axis (model X): the head from the end face
   (x 0) along +X, then the spigot.
2. ``ThreadBore``: the native blind bottoming tap from ``TAP_SPEC``, started
   on the end face at its centre, both depths from it.
3. ``SpringScrewAxis``: the plug's axis (Front Plane x Top Plane), hidden,
   the assembly's reference for the screw.

Layout (mm): origin at the end face's centre, the plug along +X to
PLUG_LENGTH; the end face faces -X.  The summing assembly places the plug at
the gooseneck's end face with the gooseneck's own rotation, so the spigot
runs into the tube.  Edges are broken by the title block's .010 note; none
is modelled (as MHA-SM-01's end piece before it).

Run on a SolidWorks worker::

    uv run python cad\scripts\build_sm_gooseneck_end_plug.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimensions, apply_drawing_precision
from _feature_tree import name_last_feature
from _holes import blind_hole_volume_mm3, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from sm_gooseneck_end_plug_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PROFILE,
    REFERENCE_DIMENSIONS,
)
from sm_gooseneck_geom import (
    PLUG_DIA,
    PLUG_HEAD_LENGTH,
    PLUG_LENGTH,
    PLUG_SHANK_LENGTH,
)
from sm_gooseneck_spring_joint import (
    PLUG_SHANK_DIA,
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_SPEC,
)

PART_NAME = "sm-gooseneck-end-plug"
# AISI 1018 cold-drawn round (the registry row's material specification).
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

PLUG_R = PLUG_DIA / 2.0
SHANK_R = PLUG_SHANK_DIA / 2.0
TAP_DRILL_R = TAP_DRILL_DIA / 2.0

if not TAP_DRILL_R < SHANK_R < PLUG_R:
    raise AssertionError("gooseneck end plug's spigot does not step down from its head")

# Analytic volumes, mm^3.
V_PLUG = math.pi * (PLUG_R**2 * PLUG_HEAD_LENGTH + SHANK_R**2 * PLUG_SHANK_LENGTH)
V_TAP = blind_hole_volume_mm3(TAP_DRILL_DIA, TAP_DRILL_DEPTH)
V_FINAL = V_PLUG - V_TAP


def _finite(label: str, volume: float) -> float:
    # NaN passes every |vol - expected| > tol comparison (the shared
    # volume_check's included), so a non-finite read stops the build
    # (codjiflo rounds 5 and 6 on #1997).
    if not math.isfinite(volume):
        raise RuntimeError(f"{label}: non-finite volume {volume!r}")
    return volume


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"mass properties: {res.error}")
    return _finite("volume", float(res.data.volume))


async def _volume_check(adapter, label: str, expected: float, tol: float) -> float:
    return _finite(label, await volume_check(adapter, label, expected, tol))


@_telemetry.traced("part.dimension_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist each printed callout below its source dimension: the drawing
    imports and reads them back, never writing them itself."""
    # swDimensionTextCalloutBelow = 4.
    for feature, callouts in DIMENSION_CALLOUTS.items():
        resolved = _named_dimensions(adapter, feature, set(callouts))
        for name, text in callouts.items():
            display, _dimension = resolved[name]
            display.SetText(4, text)
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}@{feature}: callout did not persist")


@_telemetry.traced("part.reference_dimensions")
def _author_reference_dimensions(adapter) -> None:
    """Bracket each reference dimension on its source: it prints as a
    reference, untoleranced (the drawing imports it as it is).

    ``ShowParenthesis`` brackets the whole text block, so a reference that
    carries a callout below (the spigot's fit note) would read its
    requirement as reference too (machinist review of 6b67c9516).  That one
    brackets only its value with a "(" prefix and ")" suffix, carrying
    SolidWorks' own "<MOD-DIAM>" token since a custom prefix replaces the Ø
    glyph."""
    open_paren = "(<MOD-DIAM>"
    for feature, names in REFERENCE_DIMENSIONS.items():
        resolved = _named_dimensions(adapter, feature, set(names))
        for name in names:
            display, _dimension = resolved[name]
            if name in DIMENSION_CALLOUTS.get(feature, {}):
                display.SetText(1, open_paren)  # swDimensionTextPrefix
                display.SetText(2, ")")  # swDimensionTextSuffix
                if (str(display.GetText(1)), str(display.GetText(2))) != (
                    open_paren,
                    ")",
                ):
                    raise RuntimeError(
                        f"{name}@{feature}: reference brackets did not persist"
                    )
                continue
            display.ShowParenthesis = True
            if not bool(display.ShowParenthesis):
                raise RuntimeError(
                    f"{name}@{feature}: reference parentheses did not persist"
                )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable globals drive the profile below; the native tap's thread
    # identity comes from TAP_SPEC.  The ``mm`` suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("PlugDia", PLUG_DIA),
        ("PlugHeadLength", PLUG_HEAD_LENGTH),
        ("PlugShankLength", PLUG_SHANK_LENGTH),
        ("PlugShankDia", PLUG_SHANK_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "PlugLength", '"PlugHeadLength" + "PlugShankLength"')

    # Per-sketch dim names + drive equations are declared inline at each
    # record call; their drive jobs apply in one deferred batch after the
    # whole model and a rebuild exist (every equation target must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # 1. The plug: one revolve of the half-section on the Front plane (sketch
    # (u, v) is model (x, y)), about a centreline on the axis.  The chain runs
    # from the spigot's end on the axis round to the end face's centre at
    # the origin, and closes along the axis.
    profile = SketchDims()
    points = [
        (PLUG_LENGTH, 0.0),
        (PLUG_LENGTH, SHANK_R),
        (PLUG_HEAD_LENGTH, SHANK_R),
        (PLUG_HEAD_LENGTH, PLUG_R),
        (0.0, PLUG_R),
        (0.0, 0.0),
    ]
    check("create_sketch end plug", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    try:
        axis = check(
            "end plug axis centerline",
            await adapter.add_centerline(0.0, 0.0, PLUG_LENGTH, 0.0),
        )
        lines = await add_line_chain(adapter, points)
    finally:
        # Session state on the seat: a failed segment must not leave sketch
        # inference off for the next leaf.
        set_sketch_direct_db(adapter, False)
    spigot_end, spigot_side, head_step, head_side, end_face, floor = lines
    for line, relation in (
        (spigot_end, "vertical"),
        (spigot_side, "horizontal"),
        (head_step, "vertical"),
        (head_side, "horizontal"),
        (end_face, "vertical"),
        (floor, "horizontal"),
    ):
        check(
            f"end plug {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    # The end face's centre IS the origin: a coincident relation, no dim.
    await anchor_point_to_origin(adapter, f"{end_face}.end", 0.0, 0.0, "end face centre")
    await dimension_between(
        adapter,
        f"{head_side}.start",
        f"{head_side}.end",
        "horizontal_distance",
        PLUG_HEAD_LENGTH,
        "end plug head length",
    )
    profile.record("PlugHeadLength", '"PlugHeadLength"')
    # The overall length runs between the two top corners, so its extension
    # lines rise from the part's outline, not from the axis.
    await dimension_between(
        adapter,
        f"{head_side}.end",
        f"{spigot_side}.start",
        "horizontal_distance",
        PLUG_LENGTH,
        "end plug overall length",
    )
    profile.record("PlugLength", '"PlugLength"')
    for name, line, u_mid, radius in (
        ("PlugDia", head_side, PLUG_HEAD_LENGTH / 2.0, PLUG_R),
        ("PlugShankDia", spigot_side, PLUG_HEAD_LENGTH + PLUG_SHANK_LENGTH / 2.0, SHANK_R),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 4.0), name
        )
        profile.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "end plug sketch")
    check("exit_sketch end plug", await adapter.exit_sketch())
    name_last_feature(adapter, PROFILE)
    drive_jobs += profile.apply(adapter, PROFILE)
    check(
        "revolve end plug",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "EndPlug")
    vol = await _volume_check(adapter, "solid end plug", V_PLUG, 0.005 * V_PLUG)

    # 2. The native blind bottoming tap, started on the end face (facing -X)
    # at its centre, both depths from it (sm_gooseneck_spring_joint; owner
    # ruling 2026-11-08 (Pedro), #2144 item 11.4: plain tap, no counterbore).
    # If the wizard's table drill differs from TAP_DRILL_DIA, wizard_holes
    # fails loud (the joint's walls are budgeted on that drill).
    tap = wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (-1.0, 0.0, 0.0),
        f"gooseneck end plug ({TAP_SPEC.size} blind)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    if abs(tap.depth_mm - TAP_DRILL_DEPTH) > 0.005:
        raise RuntimeError(
            f"gooseneck end plug tap drill depth {tap.depth_mm:.3f} != "
            f"{TAP_DRILL_DEPTH:.3f} mm"
        )
    drive_jobs += tap.placement_drive_jobs
    vol = await _volume_check(adapter, "end plug blind tap", vol - V_TAP, 0.02 * V_TAP)

    # 3. The plug's axis, model X: hidden, selectable by name for the
    # assembly's screw.
    await name_bore_axis(
        adapter, "Front Plane", 0.0, "Top Plane", 0.0, "spring screw"
    )
    name_last_feature(adapter, "SpringScrewAxis")

    # Apply the deferred drive equations now -- after the whole model + a
    # rebuild exists, so every target resolves.  Each equation evaluates to
    # the value just built, so the geometry must not move; the re-check below
    # is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    final_vol = await _volume_check(
        adapter, "driven end plug (equations neutral)", vol, 0.001 * vol
    )
    _telemetry.info(f"end plug volume {final_vol:.1f} mm^3 (analytic {V_FINAL:.1f})")
    if abs(final_vol - V_FINAL) > 0.01 * V_FINAL:
        raise RuntimeError(f"end plug volume {final_vol:.1f} != {V_FINAL:.1f}")
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"end plug: expected one solid body, found {len(bodies)}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _author_dimension_callouts(adapter)
    _author_reference_dimensions(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
