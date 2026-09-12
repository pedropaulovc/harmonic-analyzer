"""Native ANSI tap positive control: #2-56 versus #0-80 on identical coupons.

Run through dodo._run(com=True). Never use this diagnostic to bypass a
production diameter gate: its independent BREP/volume checks are the evidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (
    CAD_ROOT, _early_bound, check, define_centered_rectangle,
    ensure_fully_defined, force_rebuild, name_last_feature, run_build,
)
from _hole_spec import HoleSpec, TAP_DRILL_MM
from _holes import wizard_holes

REPORT = CAD_ROOT / "out" / "reports" / "pivot-tap-readback.json"
THICKNESS = 2.5
HALF_WIDTH = 4.0


def _property(definition, name):
    try:
        value = getattr(definition, name)
        return {"value": value}
    except Exception as exc:
        return {"exception_type": type(exc).__name__, "exception": str(exc)}


async def _case(adapter, size):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(f"create coupon {size}", await adapter.create_part())
    check("coupon sketch", await adapter.create_sketch("Front"))
    await define_centered_rectangle(adapter, HALF_WIDTH, HALF_WIDTH, "coupon")
    await ensure_fully_defined(adapter, "coupon")
    check("exit coupon sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "CouponProfile")
    check("extrude coupon", await adapter.create_extrusion(ExtrusionParameters(
        depth=THICKNESS, both_directions=True,
    )))
    name_last_feature(adapter, "Coupon")
    # Deliberately omit ONLY the production property-based expect_dia_mm gate.
    # Independently gate the actual cut geometry after recording all readbacks.
    result = wizard_holes(
        adapter, HoleSpec("tapped", size, thread_class="2B"),
        [[0.0, 0.0, -THICKNESS / 2.0]], (0.0, 0.0, -1.0),
        f"tap positive control {size}", name="ProbeTap",
    )
    await force_rebuild(adapter)
    model = adapter.currentModel
    feature = _early_bound(_early_bound(model, "IPartDoc").FeatureByName("ProbeTap"), "IFeature")
    definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
    properties = {
        name: _property(definition, name)
        for name in (
            "Type", "FastenerSize", "ThreadClass", "ThreadEndCondition",
            "Standard2", "EndCondition", "CosmeticThreadType",
            "HoleDiameter", "ThruHoleDiameter", "TapDrillDiameter", "ThruTapDrillDiameter",
        )
    }
    class_readback = {"fresh_definition": _property(definition, "ThreadClass")}
    if class_readback["fresh_definition"].get("value") != "2B":
        raise RuntimeError(
            f"production wizard helper did not author 2B: {class_readback!r}"
        )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    coupon_path = REPORT.parent / f"pivot-tap-class-{size.lstrip('#')}.SLDPRT"
    coupon_path.unlink(missing_ok=True)
    check("save class probe coupon", await adapter.save_file(str(coupon_path)))
    if not coupon_path.is_file() or coupon_path.stat().st_size == 0:
        raise RuntimeError(f"class probe coupon not saved: {coupon_path}")
    check("close class probe coupon", await adapter.close_model(save=False))
    check("reopen class probe coupon", await adapter.open_model(str(coupon_path)))
    model = adapter.currentModel
    feature = _early_bound(_early_bound(model, "IPartDoc").FeatureByName("ProbeTap"), "IFeature")
    definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
    class_readback["after_reopen"] = _property(definition, "ThreadClass")
    class_readback["saved_coupon"] = str(coupon_path)
    error = feature.GetErrorCode2()
    bodies = _early_bound(model, "IPartDoc").GetBodies2(0, False) or ()
    cylinders = []
    for body in bodies:
        for face in _early_bound(body, "IBody2").GetFaces() or ():
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface.IsCylinder():
                parameters = tuple(float(value) for value in surface.CylinderParams)
                cylinders.append({
                    "axis_origin_mm": [value * 1000.0 for value in parameters[:3]],
                    "axis_direction": parameters[3:6],
                    "diameter_mm": 2.0 * parameters[6] * 1000.0,
                    "face_box_mm": [float(value) * 1000.0 for value in face.GetBox()],
                })
    mass = check("coupon mass properties", await adapter.get_mass_properties())
    volume = float(mass.volume)
    expected_diameter = TAP_DRILL_MM[size]
    expected_removed = math.pi / 4.0 * expected_diameter**2 * THICKNESS
    removed = (2.0 * HALF_WIDTH)**2 * THICKNESS - volume
    on_axis = [
        cylinder for cylinder in cylinders
        if math.hypot(*cylinder["axis_origin_mm"][:2]) < 1e-5
        and abs(cylinder["axis_direction"][2]) > 0.999999
    ]
    diameter_matches = [
        cylinder for cylinder in on_axis
        if abs(cylinder["diameter_mm"] - expected_diameter) < 0.005
    ]
    valid = (
        len(bodies) == 1 and len(diameter_matches) == 1
        and abs(removed - expected_removed) < 0.01
    )
    return {
        "requested_size": size,
        "coupon_mm": [2.0 * HALF_WIDTH, 2.0 * HALF_WIDTH, THICKNESS],
        "entry_mm": [0.0, 0.0, -THICKNESS / 2.0],
        "feature_type_name": str(feature.GetTypeName2()),
        "feature_error_code_and_warning": error,
        "definition": properties,
        "thread_class_readback": class_readback,
        "thread_class_persisted": (
            class_readback["fresh_definition"].get("value") == "2B"
            and class_readback["after_reopen"].get("value") == "2B"
        ),
        "helper_reported_diameter_mm": result.hole_dia_mm,
        "solid_body_count": len(bodies),
        "cylindrical_brep": cylinders,
        "expected_diameter_mm": expected_diameter,
        "removed_volume_mm3": removed,
        "expected_removed_volume_mm3": expected_removed,
        "native_geometry_matches": valid,
    }


async def build(adapter):
    cases = []
    for size in ("#2-56", "#0-80"):
        try:
            cases.append(await _case(adapter, size))
        except Exception as exc:
            cases.append({
                "requested_size": size, "exception_type": type(exc).__name__,
                "exception": str(exc), "traceback": traceback.format_exc(),
                "native_geometry_matches": None,
            })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")
    if any("exception" in case for case in cases):
        raise RuntimeError(f"tap positive-control diagnostic failed before completing measurement; inspect {REPORT}")
    if not all(case["native_geometry_matches"] for case in cases):
        raise RuntimeError(f"tap positive control has a native mismatch; inspect {REPORT}")
    if not all(case["thread_class_persisted"] for case in cases):
        raise RuntimeError(f"native tap thread class did not persist; inspect {REPORT}")
    return {"report": str(REPORT)}


if __name__ == "__main__":
    sys.exit(run_build(build))
