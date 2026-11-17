"""Build purchased MHA-SM-VN-56, the gooseneck shoulder screw (McMaster 91829A566).

Datasheet-built nominal envelope, as the oblique trammel's pivot screw
(build_ch_rocker_arm_tl_vn_oblique_pivot_screw): no vendor CAD, and no
unreported edge, neck or undercut form is inferred.  Axis +Z, origin on the
shoulder end face; the nominal 10-24 thread envelope extends -Z, and the
straight driver slot (the spec's SLOT_WIDTH x SLOT_DEPTH) is cut across the
head's end face, as build_dt_crank_handle_pivot_screw's.  Supplier sizes are
model-owned construction references in a Right-plane sketch, in the final
part frame, not claims of helical attachment.
"""
from __future__ import annotations

import math
import sys

import _config
import sm_vn_gooseneck_shoulder_screw_spec as part
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bought_revolve import stock_properties
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import mark_dimensions_for_drawing
from _drawing_precision import _named_dimension
from _fastener_catalog import fastener
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _session import run_build
from _sketch import SketchDims, blank_reference_sketches, ensure_fully_defined
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _supplier_screw_reference import _linear
from _visibility import blank_reference_geometry

PART_NAME = "sm-vn-gooseneck-shoulder-screw"
if PART_NAME != part.PART_NAME:
    raise AssertionError(f"builder PART_NAME {PART_NAME!r} != spec {part.PART_NAME!r}")
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
AXIS_NAME = part.AXIS_NAME
THREAD_FEATURE = "ThreadEnvelope"
SLOT_FEATURE = "DriverSlot"
# The slot runs along model X past the head on both sides.
SLOT_SPAN = part.HEAD_DIA + 2.0
_HEAD_R = part.HEAD_DIA / 2.0
_SLOT_HALF = part.SLOT_WIDTH / 2.0
# The head's chord strip under the slot, |y| <= SLOT_WIDTH / 2.
SLOT_VOLUME = part.SLOT_DEPTH * 2.0 * (
    _SLOT_HALF * math.sqrt(_HEAD_R**2 - _SLOT_HALF**2)
    + _HEAD_R**2 * math.asin(_SLOT_HALF / _HEAD_R)
)
MODEL_VOLUME = math.pi / 4.0 * (
    part.SHOULDER_DIA**2 * part.SHOULDER_LENGTH
    + part.HEAD_DIA**2 * part.HEAD_HEIGHT
    + part.MAJOR_DIA**2 * part.THREAD_LENGTH
) - SLOT_VOLUME


def _ring(adapter, name, od, bore, length, *, offset=0.0, reverse=False):
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    plane = "Front"
    if offset:
        check(name + " plane", adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=offset)
        ))
        plane = "HeadPlane"
        name_last_feature(adapter, "HeadPlane")
        blank_reference_geometry(adapter, (("HeadPlane", "PLANE"),))
    check(name + " sketch", adapter.create_sketch(plane))
    define_circle(adapter, 0.0, 0.0, od / 2.0, name + " OD")
    if bore:
        define_circle(adapter, 0.0, 0.0, bore / 2.0, name + " bore")
    ensure_fully_defined(adapter, name)
    check(name + " exit", adapter.exit_sketch())
    name_last_feature(adapter, name + "Profile")
    check(name + " extrusion", adapter.create_extrusion(
        ExtrusionParameters(depth=length, reverse_direction=reverse)
    ))
    name_last_feature(adapter, name)


def _driver_slot(adapter):
    """Cut the straight slot down from the head's end face (z = LENGTH)."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("slot plane", adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=part.LENGTH)
    ))
    name_last_feature(adapter, "SlotPlane")
    blank_reference_geometry(adapter, (("SlotPlane", "PLANE"),))
    check("slot sketch", adapter.create_sketch("SlotPlane"))
    define_centered_rectangle(adapter, SLOT_SPAN / 2.0, _SLOT_HALF, "driver slot")
    ensure_fully_defined(adapter, "driver slot")
    check("slot exit", adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    # From the head's end face down into the head (-Z); a cut into air
    # removes nothing, and the volume check after it refuses that.
    check(SLOT_FEATURE, adapter.create_cut_extrude(
        ExtrusionParameters(depth=part.SLOT_DEPTH, reverse_direction=False)
    ))
    name_last_feature(adapter, SLOT_FEATURE)


def _supplier_references(adapter):
    """Right-plane construction carriers (sketch x is model -z), marked for drawing."""
    feature = part.REFERENCE_FEATURE
    check(f"create {feature}", adapter.create_sketch("Right"))
    recorded = SketchDims()
    for name, value, orientation in part.REFERENCE_DIMENSIONS:
        _linear(adapter, recorded, name, value, orientation, part.REFERENCE_STARTS[name])
    ensure_fully_defined(adapter, feature)
    check(f"exit {feature}", adapter.exit_sketch())
    name_last_feature(adapter, feature)
    recorded.apply(adapter, feature)
    for name, value, _orientation in part.REFERENCE_DIMENSIONS:
        display, native = _named_dimension(adapter, feature, name)
        if not math.isclose(float(native.SystemValue) * 1000.0, value, abs_tol=1e-5):
            raise RuntimeError(name + ": nominal carrier value changed")
        precision = part.REFERENCE_FORMATS[name][0]
        if display.SetPrecision3(precision, -1, -1, -1) != 0:
            raise RuntimeError(name + ": source precision rejected")
        if (int(display.GetPrimaryPrecision2()) != precision
                or int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0):
            raise RuntimeError(name + ": source presentation did not persist")
    mark_dimensions_for_drawing(adapter, feature, {name for name, _, _ in part.REFERENCE_DIMENSIONS})
    blank_reference_sketches(adapter, (feature,))


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check("create_part", adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    _ring(adapter, "Shoulder", part.SHOULDER_DIA, 0.0, part.SHOULDER_LENGTH)
    _ring(adapter, "Head", part.HEAD_DIA, 0.0, part.HEAD_HEIGHT, offset=part.SHOULDER_LENGTH)
    _ring(adapter, THREAD_FEATURE, part.MAJOR_DIA, 0.0, part.THREAD_LENGTH, reverse=True)
    _driver_slot(adapter)
    check("publish axis", adapter.create_axis(CreateAxisParameters(
        mode="two_planes", planes=["Top Plane", "Right Plane"]
    )))
    name_last_feature(adapter, AXIS_NAME)
    blank_reference_geometry(adapter, ((AXIS_NAME, "AXIS"),))
    volume_check(adapter, PART_NAME, MODEL_VOLUME, max(0.01, MODEL_VOLUME * 1e-5))
    bbox_extent_check(adapter, PART_NAME, "z", part.LENGTH + part.THREAD_LENGTH)
    apply_material(adapter, MATERIAL)
    # Passivated 18-8 stainless renders as the polished steel tone.
    apply_color(adapter, POLISHED_STEEL)
    apply_custom_properties(adapter, stock_properties(_config.parts(PART_NAME)))
    _supplier_references(adapter)
    report_mass_properties(adapter)
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
