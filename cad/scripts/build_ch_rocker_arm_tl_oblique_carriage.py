r"""Purchased HIWIN HGH15CA Z0 carriage (MHA-CH-006-TL-31).

The oblique trammel jig's two carriages (vendor-checked against HIWIN's own
HGH15CAZ0C STEP; ``ch_rocker_arm_tl_oblique_carriage_spec`` records every
source), one solid body:

1. ``EndCaps``: ``CAP_OUTLINE`` on the Right plane, mid-plane over L 61.4
   (the end caps and seals' section).
2. ``SteelBody``: ``BODY_OUTLINE``, mid-plane over L1 39.4 (wider and
   taller; the cap section lies inside it).
3. ``Channel``: the rail section offset 0.1, cut through.
4. ``M4Bores``: four Ø3.242 (M4x0.7 minor) x 5 bores down from the mounting
   face; M4 has no tap-drill row and the wizard is inch-only, so they are
   plain bores (CONTRACT.md modelling rule).
5. ``GreaseNipple`` on the +X end and ``PortPlug`` on the -X end: cylinder
   envelopes on the nipple axis.

Frame: origin at mid-length, on the rail centreline, at the rail seat level;
+X along the rail, +Z up. The Right plane's sketch reads model (-Z, Y); the
profiles map through the sketch's own transform, so only that orientation
is assumed, and it is checked.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_carriage.py
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import _config
import _telemetry
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import add_line_chain, ensure_fully_defined, set_sketch_direct_db
from _sketch_chains import define_polygon_chain
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_carriage_spec import (
    BODY_LENGTH,
    BODY_OUTLINE,
    BOLT_POINTS,
    BORE_DEPTH,
    BORE_DIA,
    CAP_OUTLINE,
    CENTROID,
    CHANNEL,
    DRAWING_NOTES,
    LENGTH,
    MATERIAL,
    MOUNTING_FACE_Z,
    NIPPLE_DIA,
    NIPPLE_FACE_X,
    NIPPLE_PROUD,
    NIPPLE_Z,
    PLUG_DIA,
    PLUG_FACE_X,
    PLUG_PROUD,
    UNDERSIDE_Z,
    V_BODY_EXTRA,
    V_BORES,
    V_CAPS,
    V_CHANNEL,
    V_NIPPLE,
    V_PLUG,
    VOLUME_MM3,
    VOLUME_TOL_MM3,
    WIDTH,
)

PART_NAME = "ch-rocker-arm-tl-oblique-carriage"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}
# Mid-plane through cut, longer than the block so both end faces open.
CHANNEL_CUT_DEPTH = 2.0 * LENGTH


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


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
    # Off the inference engine: the channel's chords and chamfers are short.
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, lines, points, label=label)
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def _end_circle(
    adapter: Any, plane: str, x: float, dia: float, label: str
) -> None:
    """One circle on the nipple axis, on an end plane at model ``x``."""
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    to_sketch = _sketch_mapper(adapter, u_axis=2, v_axis=1, label=label)
    await define_circle(adapter, *to_sketch((x, 0.0, NIPPLE_Z)), dia / 2.0, label)
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # --- End caps and seals: the cap section over the whole length -------------
    await _section_sketch(adapter, CAP_OUTLINE, "end cap section")
    name_last_feature(adapter, "EndCapSection")
    check(
        "extrude end caps",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "EndCaps")
    volume = await volume_check(adapter, "end caps", V_CAPS, 5e-4 * V_CAPS)

    # --- Steel body: wider and taller, over L1 -----------------------------------
    await _section_sketch(adapter, BODY_OUTLINE, "steel body section")
    name_last_feature(adapter, "SteelBodySection")
    check(
        "extrude steel body",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BODY_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SteelBody")
    volume = await volume_check(
        adapter, "steel body", volume + V_BODY_EXTRA, 0.01 * V_BODY_EXTRA
    )

    # --- Rail channel: the offset rail section, through --------------------------
    await _section_sketch(adapter, CHANNEL, "channel section")
    name_last_feature(adapter, "ChannelSection")
    check(
        "cut channel",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CHANNEL_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Channel")
    volume = await volume_check(
        adapter, "channel", volume - V_CHANNEL, 0.01 * V_CHANNEL
    )

    # --- M4 x 5 bores, down from the mounting face --------------------------------
    check(
        "create_plane MountingFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=MOUNTING_FACE_Z
            )
        ),
    )
    name_last_feature(adapter, "MountingFace")
    check("create_sketch M4 bores", await adapter.create_sketch("MountingFace"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="M4 bores")
    for index, (x, y) in enumerate(BOLT_POINTS, start=1):
        await define_circle(
            adapter,
            *to_top((x, y, MOUNTING_FACE_Z)),
            BORE_DIA / 2.0,
            f"M4 bore {index}",
        )
    await ensure_fully_defined(adapter, "M4 bores")
    check("exit_sketch M4 bores", await adapter.exit_sketch())
    name_last_feature(adapter, "M4BoreProfile")
    # A cut on a plane runs against its normal by default: down from MountingFace.
    check(
        "cut M4 bores",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=BORE_DEPTH)),
    )
    name_last_feature(adapter, "M4Bores")
    volume = await volume_check(adapter, "M4 bores", volume - V_BORES, 0.01 * V_BORES)

    # --- Grease nipple (+X end) and port plug (-X end) ------------------------------
    # Right-plane offsets keep the +X normal, so a boss runs +X by default:
    # the nipple outward as is, the plug outward reversed.
    for name, face_x, dia, proud, reverse, added in (
        ("NippleEnd", NIPPLE_FACE_X, NIPPLE_DIA, NIPPLE_PROUD, False, V_NIPPLE),
        ("PlugEnd", PLUG_FACE_X, PLUG_DIA, PLUG_PROUD, True, V_PLUG),
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

    await volume_check(adapter, "carriage", VOLUME_MM3, VOLUME_TOL_MM3)
    await _centroid_check(adapter, "carriage", CENTROID, 0.01)
    await bbox_extent_check(
        adapter, "carriage length", "x", LENGTH + NIPPLE_PROUD + PLUG_PROUD
    )
    await bbox_extent_check(adapter, "carriage width", "y", WIDTH)
    await bbox_extent_check(
        adapter, "carriage height", "z", MOUNTING_FACE_Z - UNDERSIDE_Z
    )
    _require_one_solid_body(adapter, label="carriage")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
