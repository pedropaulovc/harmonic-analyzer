r"""Purchased MHA-PD-VN-70 transgear collar flat pin: McMaster 90145A414.

A 1/16 x 3/16 18-8 stainless dowel (``pd_vn_transgear_collar_flat_pin_spec``).
One is pressed to the floor of the blind ream on local -Y of the knob drive
collar MHA-PD-22; its crest is the collar's drive flat on the MHA-PD-08 knob
shaft's D-flat.  The pin is unhardened: where it stands past the collar's
fitted rear face it is faced flush with it when the collar is faced to fit.
The stock recipe ``diagnostics/diag_build_90145A414.py`` models the nominal
catalogue cylinder, catalogue-only (no vendor model).

Configurations (the ``build_pd_vn_transgear_pivot_screw`` precedent): the
default one is faced to ``pd_transgear_drive_collar_spec.FLAT_PIN_LENGTH``,
flush with the collar model's rear face, and carries the collar's rear 45°
break cut through its crest corner (``CrestBreak``, a cone about the collar
axis); it is the one the assembly places.  ``AS SUPPLIED STOCK`` suppresses
both cuts and is the catalogue pin the purchased sheet documents.

Frame: pin axis +Y, the end pressed to the floor at y = 0 (the Top Plane),
the other end at y = LENGTH as supplied.  The axis is published as
``ScrewAxis`` (Front ∩ Right), the stock-part mate contract the paper drive
keys it by.  The assembly turns the pin +90° about X onto the collar's -Y
ream, so the collar's axis is the pin-frame line x = 0, z = -FLAT_PIN_CENTRE.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_transgear_collar_flat_pin.py
"""

from __future__ import annotations

import math
import sys
from functools import wraps
from typing import Any, Callable

from _appearance import POLISHED_STEEL
from _check import check
from _com import _early_bound
from _configuration_material import require_material_in_every_configuration
from _fastener_catalog import fastener
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import volume_check
from _part_save import save_part_and_images
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_pin_model import author_supplier_dowel_references
from diagnostics.diag_build_90145A414 import build_90145A414
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from pd_transgear_drive_collar_spec import BORE_DIA, FLAT_PIN_CENTRE, REAR_BREAK
from pd_transgear_drive_collar_spec import FLAT_PIN_LENGTH as FACED_LENGTH
from pd_transgear_drive_collar_spec import cone_cylinder_volume
from pd_vn_transgear_collar_flat_pin_spec import (
    DIA,
    LENGTH,
    SKU,
    SUPPLIER_REFERENCE,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_SUPPRESSED_FEATURES,
)

PART_NAME = "pd-vn-transgear-collar-flat-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

if not 0.0 < FACED_LENGTH <= LENGTH:
    raise AssertionError("the faced collar flat pin is not a length of the stock pin")
V_FACED = math.pi * (DIA / 2.0) ** 2 * FACED_LENGTH
V_STOCK = math.pi * (DIA / 2.0) ** 2 * LENGTH
# The collar's rear break, a 45° cone about the collar axis opening to the
# bore's radius plus its leg at the rear face, through the pin's crest corner.
_BREAK_FACE_R = BORE_DIA / 2.0 + REAR_BREAK
V_CREST_BREAK = cone_cylinder_volume(
    _BREAK_FACE_R, _BREAK_FACE_R, DIA / 2.0, FLAT_PIN_CENTRE
)
V_FACED_BROKEN = V_FACED - V_CREST_BREAK


async def _face_to_collar(adapter) -> None:
    """Cut the stock pin back to ``FACED_LENGTH`` from its pressed end: a
    rectangle in the pin's axial (Front) plane from the faced station past
    the stock end, cut through both ways."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    radius = DIA / 2.0
    top = LENGTH + DIA
    with no_sketch_inference(adapter):
        check("create facing sketch", await adapter.create_sketch("Front"))
        lines = await add_line_chain(
            adapter,
            [
                (-2.0 * radius, FACED_LENGTH),
                (2.0 * radius, FACED_LENGTH),
                (2.0 * radius, top),
                (-2.0 * radius, top),
            ],
        )
        for line, direction in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                "facing profile relation",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        dims = SketchDims()
        await anchor_point_to_origin(
            adapter,
            f"{lines[0]}.start",
            -2.0 * radius,
            FACED_LENGTH,
            "facing cutter corner",
        )
        dims.record("CutterLeft")
        dims.record("FacedLength")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            4.0 * radius,
            "facing cutter width",
        )
        dims.record("CutterWidth")
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            f"{lines[1]}.end",
            "vertical_distance",
            top - FACED_LENGTH,
            "facing cutter height",
        )
        dims.record("CutterHeight")
        await ensure_fully_defined(adapter, "stock facing profile")
        check("exit facing sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "StockFacingProfile")
        dims.apply(adapter, "StockFacingProfile")
        check(
            "face stock pin to the collar's rear face",
            await adapter.create_cut_extrude(
                ExtrusionParameters(depth=4.0 * DIA, both_directions=True)
            ),
        )
        name_last_feature(adapter, "StockFacing")
    await volume_check(adapter, "faced collar flat pin", V_FACED, 0.005 * V_FACED)


def _right_plane_sketch(
    adapter: Any,
) -> tuple[Callable[[float, float], tuple[float, float]], bool]:
    """Map pin-frame points of the Right plane (x = 0), given as (model y,
    model z), into the ACTIVE sketch through ``ModelToSketchTransform``
    (build_pd_transgear_arm's pin-section idiom), so the collar axis's side
    follows the model, not an assumed sketch sign.  Returns the mapper and
    whether the pin axis (model Y) runs along sketch u."""
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("collar flat pin crest break: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(y_mm: float, z_mm: float) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                [0.0, y_mm / 1000.0, z_mm / 1000.0],
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    origin = raw(0.0, 0.0)
    if max(map(abs, origin)) > 1e-6:
        raise RuntimeError(
            f"collar flat pin crest break: sketch origin maps to {origin!r}"
        )
    along_y = tuple(c - o for c, o in zip(raw(1.0, 0.0), origin, strict=True))
    along_z = tuple(c - o for c, o in zip(raw(0.0, 1.0), origin, strict=True))

    def axis_of(delta: tuple[float, ...]) -> int:
        hits = [i for i in (0, 1) if abs(abs(delta[i]) - 1.0) < 1e-6]
        if len(hits) != 1 or abs(delta[1 - hits[0]]) > 1e-6 or abs(delta[2]) > 1e-6:
            raise RuntimeError(f"collar flat pin crest break: axis maps to {delta!r}")
        return hits[0]

    axial = axis_of(along_y)
    if axis_of(along_z) == axial:
        raise RuntimeError(
            "collar flat pin crest break: Y and Z map to one sketch axis"
        )

    def to_sketch(y_mm: float, z_mm: float) -> tuple[float, float]:
        u, v, _w = raw(y_mm, z_mm)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch, axial == 0


async def _break_crest(adapter) -> None:
    """Cut the collar's rear 45° break through the faced pin's crest corner:
    in the Right plane, a triangle from the cone's apex on the collar axis
    (z = -FLAT_PIN_CENTRE) out to its 45° line past the faced end, revolved
    about that axis.  Only the crest corner is metal inside the cone."""
    from solidworks_mcp.adapters.base import RevolveParameters

    overrun = DIA
    axis_z = -FLAT_PIN_CENTRE
    beyond = FACED_LENGTH + overrun
    reach = _BREAK_FACE_R + overrun
    with no_sketch_inference(adapter):
        check("create crest break sketch", await adapter.create_sketch("Right"))
        to_sketch, axial_on_u = _right_plane_sketch(adapter)
        axial, radial = (
            ("horizontal", "vertical") if axial_on_u else ("vertical", "horizontal")
        )
        apex = to_sketch(FACED_LENGTH - _BREAK_FACE_R, axis_z)
        profile = [apex, to_sketch(beyond, axis_z + reach), to_sketch(beyond, axis_z)]
        axis = check(
            "crest break axis",
            await adapter.add_centerline(
                *profile[2], *to_sketch(beyond + overrun, axis_z)
            ),
        )
        slant, top, axis_side = await add_line_chain(adapter, profile)
        for line, relation in ((top, radial), (axis_side, axial), (axis, axial)):
            check(
                f"crest break {relation} {line}",
                await adapter.add_sketch_constraint(line, None, relation),
            )
        check(
            "crest break axis on the profile",
            await adapter.add_sketch_constraint(
                f"{axis}.start", f"{axis_side}.start", "coincident"
            ),
        )
        dims = SketchDims()
        await anchor_point_to_origin(
            adapter, f"{slant}.start", *apex, "crest break apex"
        )
        dims.record("BreakApexU")
        dims.record("BreakApexV")
        await dimension_between(
            adapter,
            f"{top}.start",
            f"{top}.end",
            f"{radial}_distance",
            reach,
            "crest break reach past the faced end",
        )
        dims.record("BreakReach")
        await dimension_between(
            adapter,
            f"{axis_side}.start",
            f"{axis_side}.end",
            f"{axial}_distance",
            reach,
            "crest break depth along the collar axis",
        )
        dims.record("BreakDepth")
        check(
            "crest break axis length",
            await adapter.add_sketch_dimension(axis, None, "linear", overrun),
        )
        dims.record("BreakAxisLength")
        await ensure_fully_defined(adapter, "crest break profile")
        check("exit crest break sketch", await adapter.exit_sketch())
        name_last_feature(adapter, "CrestBreakProfile")
        dims.apply(adapter, "CrestBreakProfile")
        check(
            "revolve-cut the collar's rear break through the crest",
            await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
        )
        name_last_feature(adapter, "CrestBreak")
    await volume_check(
        adapter, "crest-broken collar flat pin", V_FACED_BROKEN, 0.1 * V_CREST_BREAK
    )


@wraps(build_90145A414)
async def _build_faced_pin(adapter, truth=None):
    await build_90145A414(adapter, truth)
    await author_supplier_dowel_references(adapter, SUPPLIER_REFERENCE)
    await _face_to_collar(adapter)
    await _break_crest(adapter)


async def _add_stock_configuration(adapter) -> None:
    """Restore the as-supplied catalogue pin in its own configuration (the
    build_ch_bar_pivot_pin configuration idiom): suppress the facing and the
    crest break there, prove each configuration's solid by volume and leave
    the faced one active."""
    from solidworks_mcp.adapters.base import CreateConfigurationParameters
    from solidworks_mcp.adapters.com_variant import bstr_array

    faced = active_configuration_name(adapter)
    if not faced or faced == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("collar flat pin has no faced configuration")
    check(
        f"create_configuration {SUPPLIER_STOCK_CONFIGURATION}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=SUPPLIER_STOCK_CONFIGURATION,
                comment=f"McMaster {SKU} as supplied; facing and crest break suppressed",
            )
        ),
    )
    check(
        f"activate {SUPPLIER_STOCK_CONFIGURATION}",
        await adapter.set_active_configuration(SUPPLIER_STOCK_CONFIGURATION),
    )
    for name in SUPPLIER_STOCK_SUPPRESSED_FEATURES:
        feature = _feature_by_name(adapter, name)
        if feature is None:
            raise RuntimeError(f"{name}: assembly cut not found")
        # swSuppressFeature in swSpecifyConfiguration: this configuration only.
        if not feature.SetSuppression2(
            0, 3, bstr_array([SUPPLIER_STOCK_CONFIGURATION])
        ):
            raise RuntimeError(f"{name}: cannot suppress the assembly cut in stock")
    await force_rebuild(adapter)
    await volume_check(adapter, "as-supplied collar flat pin", V_STOCK, 0.005 * V_STOCK)
    check(f"re-activate {faced}", await adapter.set_active_configuration(faced))
    await force_rebuild(adapter)
    await volume_check(
        adapter, "crest-broken collar flat pin", V_FACED_BROKEN, 0.1 * V_CREST_BREAK
    )
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (faced, SUPPLIER_STOCK_CONFIGURATION)
    )


async def build(adapter) -> dict[str, str]:
    # Defined here so the saved-cache proof (save, reopen, tripwire) reads in
    # build() itself, as test_part_save_rebuild audits a configuration author.
    async def save_with_stock_configuration(adapter, part_name: str) -> dict[str, str]:
        await _add_stock_configuration(adapter)
        artefacts = await save_part_and_images(adapter, part_name)
        # The assembly places the faced configuration and the purchased sheet
        # the as-supplied one, each from its saved cache: reopen and prove
        # both the way they load it (cg-fx1).
        adapter.swApp.CloseDoc(
            str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
        )
        adapter.currentModel = None
        check(
            "reopen saved collar flat pin", await adapter.open_model(artefacts["part"])
        )
        assert_saved_configurations_regenerate(adapter, part_name)
        return artefacts

    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_build_faced_pin),),
        material=MATERIAL,
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
        save_unthreaded_part=save_with_stock_configuration,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
