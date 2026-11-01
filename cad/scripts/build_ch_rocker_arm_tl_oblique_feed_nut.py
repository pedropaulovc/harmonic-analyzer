r"""Build the oblique-trammel jig's feed nut (MHA-CH-06-TL-27; shop fixture).

A brass 360-H02 3/4 x 1-1/4 in rectangle bar, faced to .40 long, carrying
the Tr8x2 RH bore and the two #4 loose-clearance holes of its two screws into
TL-32's lug (``ch_rocker_arm_tl_oblique_feed_nut_spec``).

Layout (the spec's model frame): ONE Front-plane rectangle from the origin
corner, extruded +Z by the length; the bore (its letter C tap drill) and the
two holes are plain circles cut THRU from the seat face, each sketch's
centre dimensioned from the origin corner. The printed hole stations (the
first from the bore, the second from the first) live on a hidden reference
sketch, ``HolePatternReference``, of construction circles on the real ones
(``_oblique_pivot_block_model``'s ``NutPatternReference``); the faced length
on another, ``NutLengthReference`` (a drawing view cannot attach the
extrusion's depth; TL-28's ``BracketThickReference``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_feed_nut.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import name_dimensions
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
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
    anchor_point_to_point,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
import ch_rocker_arm_tl_oblique_feed_nut_spec as spec

PART_NAME = "ch-rocker-arm-tl-oblique-feed-nut"
assert PART_NAME == spec.PART_NAME
MATERIAL = "Brass"  # C36000 free-cutting brass bar (the registry row names it)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

V_NUT = spec.WIDTH * spec.HEIGHT * spec.LENGTH
V_BORE = math.pi * (spec.BORE_DRILL / 2.0) ** 2 * spec.LENGTH
V_HOLES = len(spec.HOLE_X) * math.pi * (spec.HOLE_DIA / 2.0) ** 2 * spec.LENGTH
# Tight enough that a missing hole (about 107 mm^3) fails.
_V_TOL = 10.0
# swDimensionTextParts_e: the model owns its callout rows.
_TEXT_PREFIX, _TEXT_SUFFIX, _TEXT_CALLOUT_BELOW = 1, 2, 4


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch entity as construction geometry."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _construction_circle(adapter, x: float, y: float, dia: float, label: str) -> str:
    """One construction circle on a real hole, drawn without inference."""
    set_sketch_direct_db(adapter, True)
    try:
        circle = check(label, await adapter.add_circle(x, y, dia / 2.0))
    finally:
        set_sketch_direct_db(adapter, False)
    _as_construction(adapter, circle)
    return circle


async def _cut_circles(adapter, profile: str, feature: str, circles) -> float:
    """Front-plane circles (x, y, dia, names), cut THRU the nut from its seat
    face toward +Z (the NutFace precedent: the body lies on the sketch
    plane's normal side, so the cut runs reversed). Returns the cut volume."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check(f"create_sketch {profile}", await adapter.create_sketch("Front"))
    for x, y, dia, names in circles:
        await define_circle(adapter, x, y, dia / 2.0, profile, dims=dims, names=names)
    await ensure_fully_defined(adapter, profile)
    check(f"exit_sketch {profile}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)
    check(
        feature,
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=spec.LENGTH * 2.0, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, feature)
    return sum(math.pi * (dia / 2.0) ** 2 * spec.LENGTH for _x, _y, dia, _n in circles)


async def _hole_pattern_reference(adapter) -> None:
    """The hidden sketch carrying the printed hole stations: construction
    circles on the bore and both holes, the first hole from the bore, the
    second from the first, all on the bore's line."""
    feature = "HolePatternReference"
    dims = SketchDims()
    check(f"create_sketch {feature}", await adapter.create_sketch("Front"))
    bore = await _construction_circle(
        adapter, spec.BORE_X, spec.BORE_Y, spec.BORE_DRILL, f"{feature} bore"
    )
    await anchor_point_to_origin(
        adapter, f"{bore}.center", spec.BORE_X, spec.BORE_Y, f"{feature} bore centre"
    )
    dims.record("RefBoreX")
    dims.record("RefBoreY")
    check(
        f"{feature} bore diameter",
        await adapter.add_sketch_dimension(bore, None, "diameter", spec.BORE_DRILL),
    )
    dims.record("RefBoreDia")
    base, base_x = bore, spec.BORE_X
    for index, (x, name) in enumerate(
        zip(spec.HOLE_X, ("HoleOffset", "HoleSpacing"), strict=True), start=1
    ):
        hole = await _construction_circle(
            adapter, x, spec.HOLE_Y, spec.HOLE_DIA, f"{feature} hole {index}"
        )
        await anchor_point_to_point(
            adapter, f"{base}.center", f"{hole}.center", abs(x - base_x), 0.0,
            f"{feature} hole {index} station",
        )
        dims.record(name)
        check(
            f"{feature} hole {index} diameter",
            await adapter.add_sketch_dimension(hole, None, "diameter", spec.HOLE_DIA),
        )
        dims.record(f"RefHole{index}Dia")
        base, base_x = hole, x
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


async def _length_reference(adapter) -> None:
    """The faced length: one plain line along the -X / bottom edge on the
    Right plane, sketch (u, v) = model (-Z, Y) (TL-28's thickness witness)."""
    feature = "NutLengthReference"
    dims = SketchDims()
    check(f"create_sketch {feature}", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    witness = check(
        f"{feature} witness line", await adapter.add_line(0.0, 0.0, -spec.LENGTH, 0.0)
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{witness}.start", 0.0, 0.0, f"{feature} foot")
    check(
        f"{feature} along Z",
        await adapter.add_sketch_constraint(witness, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{witness}.start", f"{witness}.end", "distance", spec.LENGTH, feature
    )
    dims.record("NutLength")
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    dims.apply(adapter, feature)


def _set_model_callouts(adapter) -> None:
    """Thread identity, counts and mate rows belong to the saved model."""
    for channel, callouts in (
        (_TEXT_PREFIX, spec.CALLOUTS_PREFIX),
        (_TEXT_SUFFIX, spec.CALLOUTS_SUFFIX),
        (_TEXT_CALLOUT_BELOW, spec.CALLOUTS_BELOW),
    ):
        for name, text in callouts.items():
            owners = [
                feature
                for feature, names in spec.DRAWING_DIMENSIONS.items()
                if name in names
            ]
            if len(owners) != 1:
                raise RuntimeError(f"{name}: expected one native callout owner")
            display, _ = _named_dimension(adapter, owners[0], name)
            display.SetText(channel, text)
            if str(display.GetText(channel) or "") != text:
                raise RuntimeError(f"{name}: model callout did not persist")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # --- Nut: Front-plane rectangle from the origin corner, +Z ----------------
    profile = SketchDims()
    check("create_sketch nut", await adapter.create_sketch("Front"))
    points = [(0.0, 0.0), (spec.WIDTH, 0.0), (spec.WIDTH, spec.HEIGHT), (0.0, spec.HEIGHT)]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter, lines, points, label="nut profile", dims=profile,
        names=["NutWidth", "NutHeight"],
    )
    await ensure_fully_defined(adapter, "nut profile")
    check("exit_sketch nut", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    profile.apply(adapter, "NutProfile")
    check("extrude nut", await adapter.create_extrusion(ExtrusionParameters(depth=spec.LENGTH)))
    name_last_feature(adapter, "Nut")
    name_dimensions(adapter, "Nut", ["NutDepth"])
    volume = await volume_check(adapter, "nut", V_NUT, _V_TOL)

    # --- The Tr8x2 bore (its letter C tap drill) and the #4 loose pair --------
    volume -= await _cut_circles(
        adapter, "BoreProfile", "Bore",
        [(spec.BORE_X, spec.BORE_Y, spec.BORE_DRILL, ("BoreX", "BoreY", "BoreDia"))],
    )
    volume = await volume_check(adapter, "nut with bore", volume, _V_TOL)
    volume -= await _cut_circles(
        adapter, "HoleProfile", "Holes",
        # The printed 2X Ø.144 is the +X hole's (the sheet's callout side).
        [
            (x, spec.HOLE_Y, spec.HOLE_DIA, (f"Hole{k}X", f"Hole{k}Y", "HoleDia" if k == 2 else "Hole1Dia"))
            for k, x in enumerate(spec.HOLE_X, start=1)
        ],
    )
    volume = await volume_check(adapter, "nut with screw holes", volume, _V_TOL)
    await volume_check(adapter, "finished nut", V_NUT - V_BORE - V_HOLES, _V_TOL)

    await _hole_pattern_reference(adapter)
    await _length_reference(adapter)
    _require_one_solid_body(adapter, label="feed nut")
    await force_rebuild(adapter)
    await volume_check(adapter, "rebuilt feed nut", volume, _V_TOL)

    # Every model edit -- material, places, callouts, marked set -- precedes
    # the save.
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    _set_model_callouts(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE}
    )
    # The reference sketches own printed dimensions but no geometry: hidden,
    # the drawing shows each in the view that imports its dimension.
    blank_reference_sketches(adapter, spec.REFERENCE_SKETCHES)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
