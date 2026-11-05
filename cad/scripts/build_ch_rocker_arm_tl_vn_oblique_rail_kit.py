r"""Configured NUIBBYED HGR15 rail kit, Amazon B0C4DJNL33 (MHA-CH-06-TL-VN-83).

One purchased kit owns the jig's two native members, each modelled on its
HIWIN reference STEP (the member specs record every source):

* ``Rail`` (default): the end-face ``SECTION`` on the Right plane extruded 450
  along +X, then the eight Ø4.5 holes through and their Ø7.5 counterbores
  down from the top. Every hole is placed from the -X end face (rule 10:
  baseline, never chained); the extrusion's ``Length`` and the eight
  ``Station<n>`` dimensions are marked for the receipt sheet, each station
  carrying the base bar's receipt band as its native tolerance. Frame: origin
  at the -X end face, on the seat face, on the rail centreline.
* ``Carriage``: ``EndCaps`` (``CAP_OUTLINE`` mid-plane over L 61.4),
  ``SteelBody`` (``BODY_OUTLINE`` over L1 39.4), the offset rail ``Channel``
  cut through, four Ø3.242 x 5 ``M4Bores`` down from the mounting face, and
  the ``GreaseNipple`` (+X) and ``PortPlug`` (-X) envelopes. Frame: origin at
  mid-length, on the rail centreline, at the rail seat level.

Both frames put +X along the rail and +Z up, so the jig mates each member on
the default planes. The Right plane's sketch reads model (-Z, Y); profiles
map through the sketch's own transform, so only that orientation is assumed,
and it is checked. Member-owned features, planes included, are suppressed in
the other configuration. Each member carries its own installed quantity,
material specification, note and native BOM key under the kit's one Number;
saving, reopening and per-member export are ``save_member_part``'s, and its
readback never repairs native state.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_vn_oblique_rail_kit.py
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import _config
import _telemetry
import ch_rocker_arm_tl_vn_oblique_rail_kit_carriage_spec as carriage
import ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec as rail
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _custom_properties import apply_custom_properties
from _com import _early_bound
from _dimensions import name_dimensions
from _document_units import apply_package_model_units
from _drawing_marks import apply_drawing_properties, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_bodies,
    require_member_colour,
    require_member_configurations,
    save_member_part,
    select_member_features,
    set_member_suppression,
)
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain
from _sketch_circle import define_circle
from _visibility import assert_reference_geometry_hidden, blank_reference_geometry

PART_NAME = "ch-rocker-arm-tl-vn-oblique-rail-kit"
RAIL_CONFIGURATION = rail.CONFIGURATION
CARRIAGE_CONFIGURATION = carriage.CONFIGURATION
CONFIGURATIONS = (RAIL_CONFIGURATION, CARRIAGE_CONFIGURATION)
if rail.MATERIAL != carriage.MATERIAL:
    raise AssertionError("the kit's members share one SOLIDWORKS library material")
MATERIAL = rail.MATERIAL
_PART = _config.parts(PART_NAME)
if rail.MATERIAL_SPECIFICATION != _PART["material_specification"]:
    raise AssertionError("the kit row's material specification is the default Rail's")
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}
MEMBER_SPECS = {RAIL_CONFIGURATION: rail, CARRIAGE_CONFIGURATION: carriage}
# Parent sketches and planes precede their dependent features; no feature is
# shared by the two members.
MEMBER_FEATURES = {
    RAIL_CONFIGURATION: (
        "RailSection",
        "Rail",
        "BoltHoleProfile",
        "BoltHoles",
        "RailTop",
        "CounterboreProfile",
        "Counterbores",
    ),
    CARRIAGE_CONFIGURATION: (
        "EndCapSection",
        "EndCaps",
        "SteelBodySection",
        "SteelBody",
        "ChannelSection",
        "Channel",
        "MountingFace",
        "M4BoreProfile",
        "M4Bores",
        "NippleEnd",
        "GreaseNippleProfile",
        "GreaseNipple",
        "PlugEnd",
        "PortPlugProfile",
        "PortPlug",
    ),
}
MEMBER_PLANES = {
    RAIL_CONFIGURATION: ("RailTop",),
    CARRIAGE_CONFIGURATION: ("MountingFace", "NippleEnd", "PlugEnd"),
}
MEMBER_DESCRIPTIONS = {
    configuration: spec.BOM_DESCRIPTION for configuration, spec in MEMBER_SPECS.items()
}
MEMBER_PROPERTIES = {
    configuration: {
        **STOCK_PROPERTIES,
        "Material Specification": spec.MATERIAL_SPECIFICATION,
        "Finish": str(_PART["finish"]),
        "Manufacturing Notes": spec.DRAWING_NOTES,
    }
    for configuration, spec in MEMBER_SPECS.items()
}
MEMBER_NOTE_PROPERTIES = {
    f"{configuration} Manufacturing Notes": spec.DRAWING_NOTES
    for configuration, spec in MEMBER_SPECS.items()
}
SAVED_DRAWING_PROPERTIES = (
    "Number", "Material Specification", "Finish", "Quantity",
    *STOCK_PROPERTIES, *MEMBER_NOTE_PROPERTIES,
)

# --- Rail -----------------------------------------------------------------------
RAIL_THROUGH_CUT_DEPTH = 2.0 * rail.HEIGHT
# The through cut runs the rail's full height; the counterbores then remove
# only their annulus around the hole (the spec's V_HOLES stops at the floor).
V_FULL_HOLES = rail.V_HOLES * rail.HEIGHT / (rail.HEIGHT - rail.CBORE_DEPTH)
V_CBORE_ANNULI = rail.V_CBORES - (V_FULL_HOLES - rail.V_HOLES)

# --- Carriage -------------------------------------------------------------------
# Mid-plane through cut, longer than the block so both end faces open.
CHANNEL_CUT_DEPTH = 2.0 * carriage.LENGTH


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    The pivot block's mapper (build_ch_rocker_arm_tl_oblique_pivot_block):
    points go through ``ModelToSketchTransform`` so only the orientation is
    assumed, and it is checked here.
    """
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


async def _centroid_check(
    adapter: Any, label: str, expected: tuple[float, float, float], tol: float
) -> None:
    """Fail if the solid grew to the wrong side of a sketch plane."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    com = tuple(float(c) for c in mass.data.center_of_mass[:3])
    if any(abs(c - e) > tol for c, e in zip(com, expected, strict=True)):
        raise RuntimeError(
            f"{label}: centre of mass {com!r} mm, expected {expected!r} +/- {tol}"
        )
    _telemetry.success(f"{label}: centre of mass {com!r} mm")


async def _section_sketch(
    adapter: Any, section: tuple[tuple[float, float], ...], label: str
) -> None:
    """A closed (y, z) section on the Right plane (model x = 0)."""
    check(f"create_sketch {label}", await adapter.create_sketch("Right"))
    to_right = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=label)
    points = [to_right((0.0, y, z)) for y, z in section]
    # Off the inference engine: the grooves' and channel's chords are short.
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, lines, points, label=label)
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def _hole_circles(
    adapter: Any,
    plane: str,
    z: float,
    dia: float,
    label: str,
    *,
    names: tuple[str, ...] | None = None,
):
    """One circle per rail hole station, on ``plane`` at model height ``z``,
    each placed from the -X end face (the sketch origin) the way the receipt
    sheet states it; ``names`` names those station dimensions."""
    if names is not None and len(names) != len(rail.HOLE_X):
        raise ValueError(f"{label}: one station name per hole")
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label=label)
    for index, x in enumerate(rail.HOLE_X):
        await define_circle(
            adapter,
            *to_sketch((x, 0.0, z)),
            dia / 2.0,
            f"{label} {index + 1}",
            dims=dims,
            names=(None if names is None else names[index], None, None),
        )
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    return dims


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


async def _author_rail(adapter: Any) -> None:
    """The HGR15 rail: section, eight through holes, eight counterbores."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    await _section_sketch(adapter, rail.SECTION, "rail section")
    name_last_feature(adapter, "RailSection")
    check(
        "extrude rail",
        await adapter.create_extrusion(ExtrusionParameters(depth=rail.LENGTH)),
    )
    name_last_feature(adapter, "Rail")
    name_dimensions(adapter, "Rail", ["Length"])
    volume = await volume_check(adapter, "rail prism", rail.V_PRISM, 5e-4 * rail.V_PRISM)
    # The prism's centroid catches a profile mapped to the wrong side of an
    # axis or extruded the wrong way along X.
    await _centroid_check(
        adapter, "rail prism", (rail.LENGTH / 2.0, 0.0, rail.SECTION_CENTROID_Z), 0.01
    )

    # --- Holes: Ø4.5 through, from the seat face both ways ---------------------
    hole_dims = await _hole_circles(
        adapter, "Front", 0.0, rail.HOLE_DIA, "bolt hole",
        names=rail.STATION_DIMENSIONS,
    )
    name_last_feature(adapter, "BoltHoleProfile")
    hole_dims.apply(adapter, "BoltHoleProfile")
    check(
        "cut bolt holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=RAIL_THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "BoltHoles")
    volume = await volume_check(
        adapter, "bolt holes", volume - V_FULL_HOLES, 0.01 * V_FULL_HOLES
    )

    # --- Counterbores: Ø7.5, down from the top face ------------------------------
    check(
        "create_plane RailTop",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=rail.HEIGHT
            )
        ),
    )
    name_last_feature(adapter, "RailTop")
    blank_reference_geometry(adapter, (("RailTop", "PLANE"),))
    await _hole_circles(adapter, "RailTop", rail.HEIGHT, rail.CBORE_DIA, "counterbore")
    name_last_feature(adapter, "CounterboreProfile")
    # A cut on a plane runs against its normal by default: down from RailTop.
    check(
        "cut counterbores",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=rail.CBORE_DEPTH)),
    )
    name_last_feature(adapter, "Counterbores")
    await volume_check(
        adapter, "counterbores", volume - V_CBORE_ANNULI, 0.01 * V_CBORE_ANNULI
    )
    await _rail_checks(adapter)

    # The receipt sheet's check of the kit rail (the spec's DRAWING_DIMENSIONS):
    # the stations at the base bar's places with its receipt band, the length
    # in whole millimetres, imported into the hole face.
    apply_drawing_precision(adapter, rail.DRAWING_PRECISION)
    for name in rail.STATION_DIMENSIONS:
        set_dimension_symmetric_tolerance(
            adapter,
            "BoltHoleProfile",
            name,
            rail.RECEIPT_BAND,
            places=rail.RECEIPT_PLACES,
        )
    for feature_name, names in rail.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, names)


async def _rail_checks(adapter: Any) -> None:
    await volume_check(adapter, "rail", rail.VOLUME_MM3, rail.VOLUME_TOL_MM3)
    await _centroid_check(adapter, "rail", rail.CENTROID, 0.01)
    await bbox_extent_check(adapter, "rail length", "x", rail.LENGTH)
    await bbox_extent_check(adapter, "rail width", "y", rail.WIDTH)
    await bbox_extent_check(adapter, "rail height", "z", rail.HEIGHT)
    _require_one_solid_body(adapter, label="rail")


async def _end_circle(
    adapter: Any, plane: str, x: float, dia: float, label: str
) -> None:
    """One circle on the nipple axis, on an end plane at model ``x``."""
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    to_sketch = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=label)
    await define_circle(
        adapter, *to_sketch((x, 0.0, carriage.NIPPLE_Z)), dia / 2.0, label
    )
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def _author_carriage(adapter: Any) -> None:
    """The HGH15CA carriage: caps, body, channel, M4 bores, nipple and plug."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    # --- End caps and seals: the cap section over the whole length -------------
    await _section_sketch(adapter, carriage.CAP_OUTLINE, "end cap section")
    name_last_feature(adapter, "EndCapSection")
    check(
        "extrude end caps",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=carriage.LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "EndCaps")
    volume = await volume_check(
        adapter, "end caps", carriage.V_CAPS, 5e-4 * carriage.V_CAPS
    )

    # --- Steel body: wider and taller, over L1 -----------------------------------
    await _section_sketch(adapter, carriage.BODY_OUTLINE, "steel body section")
    name_last_feature(adapter, "SteelBodySection")
    check(
        "extrude steel body",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=carriage.BODY_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SteelBody")
    volume = await volume_check(
        adapter,
        "steel body",
        volume + carriage.V_BODY_EXTRA,
        0.01 * carriage.V_BODY_EXTRA,
    )

    # --- Rail channel: the offset rail section, through --------------------------
    await _section_sketch(adapter, carriage.CHANNEL, "channel section")
    name_last_feature(adapter, "ChannelSection")
    check(
        "cut channel",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CHANNEL_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Channel")
    volume = await volume_check(
        adapter, "channel", volume - carriage.V_CHANNEL, 0.01 * carriage.V_CHANNEL
    )

    # --- M4 x 5 bores, down from the mounting face --------------------------------
    check(
        "create_plane MountingFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=carriage.MOUNTING_FACE_Z,
            )
        ),
    )
    name_last_feature(adapter, "MountingFace")
    check("create_sketch M4 bores", await adapter.create_sketch("MountingFace"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="M4 bores")
    for index, (x, y) in enumerate(carriage.BOLT_POINTS, start=1):
        await define_circle(
            adapter,
            *to_top((x, y, carriage.MOUNTING_FACE_Z)),
            carriage.BORE_DIA / 2.0,
            f"M4 bore {index}",
        )
    await ensure_fully_defined(adapter, "M4 bores")
    check("exit_sketch M4 bores", await adapter.exit_sketch())
    name_last_feature(adapter, "M4BoreProfile")
    # A cut on a plane runs against its normal by default: down from MountingFace.
    check(
        "cut M4 bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=carriage.BORE_DEPTH)
        ),
    )
    name_last_feature(adapter, "M4Bores")
    volume = await volume_check(
        adapter, "M4 bores", volume - carriage.V_BORES, 0.01 * carriage.V_BORES
    )

    # --- Grease nipple (+X end) and port plug (-X end) ------------------------------
    # Right-plane offsets keep the +X normal, so a boss runs +X by default:
    # the nipple outward as is, the plug outward reversed.
    for name, face_x, dia, proud, reverse, added in (
        (
            "NippleEnd", carriage.NIPPLE_FACE_X, carriage.NIPPLE_DIA,
            carriage.NIPPLE_PROUD, False, carriage.V_NIPPLE,
        ),
        (
            "PlugEnd", carriage.PLUG_FACE_X, carriage.PLUG_DIA,
            carriage.PLUG_PROUD, True, carriage.V_PLUG,
        ),
    ):
        check(
            f"create_plane {name}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Right Plane", offset=face_x
                )
            ),
        )
        name_last_feature(adapter, name)
        feature = "GreaseNipple" if name == "NippleEnd" else "PortPlug"
        await _end_circle(adapter, name, face_x, dia, feature)
        name_last_feature(adapter, f"{feature}Profile")
        check(
            f"extrude {feature}",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=proud, reverse_direction=reverse)
            ),
        )
        name_last_feature(adapter, feature)
        volume = await volume_check(adapter, feature, volume + added, 0.01 * added)
    blank_reference_geometry(
        adapter,
        (("MountingFace", "PLANE"), ("NippleEnd", "PLANE"), ("PlugEnd", "PLANE")),
    )
    await _carriage_checks(adapter)


async def _carriage_checks(adapter: Any) -> None:
    await volume_check(
        adapter, "carriage", carriage.VOLUME_MM3, carriage.VOLUME_TOL_MM3
    )
    await _centroid_check(adapter, "carriage", carriage.CENTROID, 0.01)
    await bbox_extent_check(
        adapter,
        "carriage length",
        "x",
        carriage.LENGTH + carriage.NIPPLE_PROUD + carriage.PLUG_PROUD,
    )
    await bbox_extent_check(adapter, "carriage width", "y", carriage.WIDTH)
    await bbox_extent_check(
        adapter,
        "carriage height",
        "z",
        carriage.MOUNTING_FACE_Z - carriage.UNDERSIDE_Z,
    )
    _require_one_solid_body(adapter, label="carriage")


MEMBER_AUTHORS = {
    RAIL_CONFIGURATION: _author_rail,
    CARRIAGE_CONFIGURATION: _author_carriage,
}
MEMBER_CHECKS = {
    RAIL_CONFIGURATION: _rail_checks,
    CARRIAGE_CONFIGURATION: _carriage_checks,
}


async def _readback(adapter: Any, configuration: str) -> None:
    """Assert the selected member without authoring, repairing or saving it."""
    assert_member_suppression(adapter, configuration, MEMBER_FEATURES)
    require_member_bodies(adapter, configuration, 1, MEMBER_PLANES[configuration])
    await MEMBER_CHECKS[configuration](adapter)
    assert_member_properties(
        adapter,
        PART_NAME,
        configuration,
        MEMBER_DESCRIPTIONS[configuration],
        MEMBER_PROPERTIES[configuration],
    )
    require_member_colour(adapter, configuration, POLISHED_STEEL)
    assert_reference_geometry_hidden(adapter, f"{PART_NAME} [{configuration}]")


async def build(adapter) -> dict[str, str]:
    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)

    authored = []
    for configuration in CONFIGURATIONS:
        await activate_member(adapter, configuration)
        # Foreign solids must be absent during authoring: otherwise an
        # extrusion or a cut can merge with, or cut into, another member.
        for previous in reversed(authored):
            set_member_suppression(adapter, MEMBER_FEATURES[previous], suppressed=True)
        await MEMBER_AUTHORS[configuration](adapter)
        authored.append(configuration)

    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, MEMBER_NOTE_PROPERTIES)
    for configuration in CONFIGURATIONS:
        await select_member_features(adapter, configuration, MEMBER_FEATURES)
        blank_reference_geometry(
            adapter, tuple((plane, "PLANE") for plane in MEMBER_PLANES[configuration])
        )
        await apply_material(adapter, MATERIAL)
        await apply_color(adapter, POLISHED_STEEL)
        apply_member_properties(
            adapter,
            PART_NAME,
            configuration,
            MEMBER_DESCRIPTIONS[configuration],
            MEMBER_PROPERTIES[configuration],
        )
        await report_mass_properties(adapter)

    artefacts = await save_member_part(
        adapter, PART_NAME, CONFIGURATIONS, material=MATERIAL, readback=_readback
    )
    require_saved_drawing_properties(adapter, SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
