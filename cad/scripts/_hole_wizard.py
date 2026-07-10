"""Project-owned Hole Wizard helpers for period fastener patterns.

The vendored adapter currently exposes only one ANSI-inch, one-point, through
tap path.  These helpers keep the additional BSI/BA behaviour local to the
parts that use it, so drawing-only/manufacturing changes do not invalidate the
entire SolidWorks adapter digest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from _common import (
    _display_dimensions,
    _read_member,
    check,
    dimension_between,
    ensure_fully_defined,
)
from render_compare import _flag

SW_FM_HOLE_WZD = 25
SW_WZD_TAP = 4
SW_STANDARD_BSI = 2
SW_BSI_TAPPED_HOLE = 58
SW_BSI_BOTTOMING_TAPPED_HOLE = 57
SW_END_BLIND = 0
SW_END_THROUGH_ALL = 1


class TapEnd(str, Enum):
    THROUGH = "through"
    BOTTOMING = "bottoming"


@dataclass(frozen=True)
class TapSpec:
    designation: str
    wizard_seed: str
    major_diameter_mm: float
    pitch_mm: float
    angle_deg: float

    @property
    def radial_depth_mm(self) -> float:
        return 0.6 * self.pitch_mm

    @property
    def tap_diameter_mm(self) -> float:
        return self.major_diameter_mm - 2.0 * self.radial_depth_mm

    @property
    def crest_root_radius_mm(self) -> float:
        return 0.18083 * self.pitch_mm


# The stock SolidWorks 2026 BSI Hole Wizard table on this seat contains metric
# sizes only.  M2.5 is used solely to mint a native HoleWzd feature; every
# manufacturing value is then overwritten and read-validated against 6 BA.
BA6 = TapSpec("6 BA", "M2.5x0.45", 2.80, 0.53, 47.5)


@dataclass(frozen=True)
class CreatedTapPattern:
    feature: Any
    tap_diameter_mm: float
    thread_diameter_mm: float


def _part_faces(model: Any) -> Iterable[Any]:
    part = model
    _flag(part, "IPartDoc")
    for body in part.GetBodies2(0, True) or []:
        _flag(body, "IBody2")
        for face in body.GetFaces() or []:
            _flag(face, "IFace2")
            yield face


def _find_xy_face(
    model: Any,
    points_xy: tuple[tuple[float, float], ...],
    z_face_mm: float,
    normal_sign: int,
) -> Any:
    best = None
    for face in _part_faces(model):
        try:
            normal = tuple(face.Normal)
            box = [float(v) * 1000.0 for v in face.GetBox()]
        except Exception:  # noqa: BLE001 - a non-planar face has no stable normal
            continue
        if abs(normal[0]) > 0.01 or abs(normal[1]) > 0.01:
            continue
        if normal_sign * normal[2] < 0.99:
            continue
        if abs(box[2] - z_face_mm) > 0.1 or abs(box[5] - z_face_mm) > 0.1:
            continue
        if not all(
            box[0] - 0.1 <= x <= box[3] + 0.1
            and box[1] - 0.1 <= y <= box[4] + 0.1
            for x, y in points_xy
        ):
            continue
        if best is None or face.GetArea() > best.GetArea():
            best = face
    if best is None:
        raise RuntimeError(
            f"Hole Wizard: no XY face at z={z_face_mm:g} mm spans {points_xy!r}"
        )
    return best


def _placement_sketch(feature: Any) -> tuple[Any, Any]:
    sub = _read_member(feature, "GetFirstSubFeature")
    while sub is not None:
        if str(_read_member(sub, "GetTypeName2")) == "ProfileFeature":
            sketch = _read_member(sub, "GetSpecificFeature2")
            _flag(sketch, "ISketch")
            if len(sketch.GetSketchPoints2() or []) == 1:
                return sub, sketch
        sub = _read_member(sub, "GetNextSubFeature")
    raise RuntimeError("Hole Wizard: one-point positioning sketch not found")


def _name_dimensions(feature: Any, names: list[str]) -> None:
    dimensions = list(_display_dimensions(feature, str(feature.Name)))
    if len(dimensions) != len(names):
        raise RuntimeError(
            f"Hole Wizard locator dimensions: expected {len(names)}, found {len(dimensions)}"
        )
    for dimension, name in zip(dimensions, names, strict=True):
        dimension.Name = name


async def create_tapped_pattern(
    adapter: Any,
    *,
    name: str,
    points_xy: tuple[tuple[float, float], ...],
    z_face_mm: float,
    normal_sign: int,
    end: TapEnd,
    tap: TapSpec = BA6,
    hole_depth_mm: float | None = None,
    thread_depth_mm: float | None = None,
) -> CreatedTapPattern:
    """Create one native BSI Hole Wizard feature with dimensioned points."""
    if not points_xy:
        raise ValueError("Hole Wizard pattern needs at least one point")
    if end is TapEnd.BOTTOMING and (hole_depth_mm is None or thread_depth_mm is None):
        raise ValueError("bottoming taps require hole_depth_mm and thread_depth_mm")

    import pythoncom
    from win32com.client import VARIANT
    from solidworks_mcp.adapters import sw_type_info
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    feature_manager = model.FeatureManager
    _flag(feature_manager, "IFeatureManager")
    data = feature_manager.CreateDefinition(SW_FM_HOLE_WZD)
    if data is None:
        raise RuntimeError("Hole Wizard CreateDefinition returned None")
    _flag(data, "IWizardHoleFeatureData2")

    fastener = (
        SW_BSI_TAPPED_HOLE if end is TapEnd.THROUGH else SW_BSI_BOTTOMING_TAPPED_HOLE
    )
    condition = SW_END_THROUGH_ALL if end is TapEnd.THROUGH else SW_END_BLIND
    data.InitializeHole(SW_WZD_TAP, SW_STANDARD_BSI, fastener, tap.wizard_seed, condition)
    face = _find_xy_face(model, points_xy, z_face_mm, normal_sign)
    model.ClearSelection2(True)
    if not face.Select2(False, 0):
        raise RuntimeError(f"Hole Wizard {name}: face selection failed")
    feature = feature_manager.CreateFeature(data)
    if feature is None:
        raise RuntimeError(
            f"Hole Wizard {name}: BSI seed size {tap.wizard_seed!r} is unavailable"
        )
    feature.Name = name

    # A freshly initialized feature-data object reports several table-backed
    # values as zero until CreateFeature commits it.  Re-open the saved feature
    # definition, force the research-derived BA form/depths, commit, then read it
    # back.  This keeps the native 6 BA designation while making the exact period
    # geometry explicit in the SLDPRT rather than trusting a seat-local table.
    typed_feature = sw_type_info.early_bound(feature, "IFeature")
    definition = typed_feature.GetDefinition()
    typed_definition = sw_type_info.early_bound(definition, "IWizardHoleFeatureData2")
    if not typed_definition.AccessSelections(model, None):
        raise RuntimeError(f"Hole Wizard {name}: AccessSelections failed")
    typed_definition.HoleDiameter = tap.tap_diameter_mm / 1000.0
    typed_definition.Diameter = tap.tap_diameter_mm / 1000.0
    typed_definition.TapDrillDiameter = tap.tap_diameter_mm / 1000.0
    typed_definition.ThreadDiameter = tap.major_diameter_mm / 1000.0
    typed_definition.ThreadAngle = math.radians(tap.angle_deg)
    if end is TapEnd.BOTTOMING:
        typed_definition.TapDrillDepth = float(hole_depth_mm) / 1000.0
        typed_definition.ThreadDepth = float(thread_depth_mm) / 1000.0
        typed_definition.EndCondition = SW_END_BLIND
        typed_definition.ThreadEndCondition = SW_END_BLIND
    if not typed_feature.ModifyDefinition(definition, model, None):
        raise RuntimeError(f"Hole Wizard {name}: ModifyDefinition failed")
    model.EditRebuild3()

    typed_feature = sw_type_info.early_bound(model.FeatureByName(name), "IFeature")
    checked = typed_feature.GetDefinition()
    checked_typed = sw_type_info.early_bound(checked, "IWizardHoleFeatureData2")
    if not checked_typed.AccessSelections(model, None):
        raise RuntimeError(f"Hole Wizard {name}: read-back AccessSelections failed")
    readback = {
        "standard": int(checked_typed.Standard2),
        "fastener": int(checked_typed.FastenerType2),
        "size": str(checked_typed.FastenerSize),
        # HoleDiameter is the cut diameter persisted by this BSI HoleWzd
        # family.  TapDrillDiameter is exposed by COM but reads zero here.
        "tap_diameter_mm": float(checked_typed.HoleDiameter) * 1000.0,
        "diameter_mm": float(checked_typed.Diameter) * 1000.0,
        "tap_drill_diameter_mm": float(checked_typed.TapDrillDiameter) * 1000.0,
        "thread_diameter_mm": float(checked_typed.ThreadDiameter) * 1000.0,
        "thread_angle_rad": float(checked_typed.ThreadAngle),
        "hole_depth_mm": float(checked_typed.TapDrillDepth) * 1000.0,
        "thread_depth_mm": float(checked_typed.ThreadDepth) * 1000.0,
    }
    checked_typed.ReleaseSelectionAccess()
    expected_size = tap.wizard_seed.replace(" ", "").upper()
    actual_size = readback["size"].replace(" ", "").upper()
    if readback["standard"] != SW_STANDARD_BSI or actual_size != expected_size:
        raise RuntimeError(f"Hole Wizard {name}: wrong standard/size {readback!r}")
    for key, actual, expected in (
        ("thread diameter", readback["thread_diameter_mm"], tap.major_diameter_mm),
    ):
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-5):
            raise RuntimeError(
                f"Hole Wizard {name}: {key} {actual:g} != {expected:g}; "
                f"read-back={readback!r}"
            )
    if end is TapEnd.BOTTOMING:
        for key, actual, expected in (
            ("hole depth", readback["hole_depth_mm"], float(hole_depth_mm)),
            ("thread depth", readback["thread_depth_mm"], float(thread_depth_mm)),
        ):
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-5):
                raise RuntimeError(f"Hole Wizard {name}: {key} {actual:g} != {expected:g}")

    position_feature, position_sketch = _placement_sketch(feature)
    position_feature.Name = f"{name}Locations"
    math_utility = adapter.swApp.GetMathUtility()
    _flag(math_utility, "IMathUtility")
    transform = position_sketch.ModelToSketchTransform
    _flag(transform, "IMathTransform")

    def sketch_point(x_mm: float, y_mm: float) -> tuple[float, float, float]:
        array = VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            [x_mm / 1000.0, y_mm / 1000.0, z_face_mm / 1000.0],
        )
        point = math_utility.CreatePoint(array)
        _flag(point, "IMathPoint")
        mapped = point.MultiplyTransform(transform)
        _flag(mapped, "IMathPoint")
        return tuple(mapped.ArrayData[:3])

    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(position_feature.Name), "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"Hole Wizard {name}: cannot edit positioning sketch")
    model.EditSketch()
    sketch_manager = model.SketchManager
    _flag(sketch_manager, "ISketchManager")
    adapter.currentSketchManager = sketch_manager
    adapter.currentSketch = position_sketch

    auto = (position_sketch.GetSketchPoints2() or [None])[0]
    if auto is None:
        raise RuntimeError(f"Hole Wizard {name}: automatic point missing")
    _flag(auto, "ISketchPoint")
    sx, sy, sz = sketch_point(*points_xy[0])
    auto.SetCoords(sx, sy, sz)
    point_objects = [auto]
    for x_mm, y_mm in points_xy[1:]:
        sx, sy, sz = sketch_point(x_mm, y_mm)
        point_objects.append(sketch_manager.CreatePoint(sx, sy, sz))

    locator_names: list[str] = []
    for index, ((x_mm, y_mm), point) in enumerate(
        zip(points_xy, point_objects, strict=True)
    ):
        ref = adapter._register_sketch_entity("Point", point)
        await dimension_between(
            adapter, ref, "origin", "horizontal_distance", x_mm, f"{name} P{index} X"
        )
        await dimension_between(
            adapter, ref, "origin", "vertical_distance", y_mm, f"{name} P{index} Y"
        )
        locator_names.extend((f"P{index}X", f"P{index}Y"))
    await ensure_fully_defined(adapter, f"{name} locations")
    check(f"exit {name} locations", await adapter.exit_sketch())
    _name_dimensions(position_feature, locator_names)
    model.EditRebuild3()

    if len(position_sketch.GetSketchPoints2() or []) != len(points_xy):
        raise RuntimeError(f"Hole Wizard {name}: placement-point count changed")
    return CreatedTapPattern(
        feature=feature,
        tap_diameter_mm=tap.tap_diameter_mm,
        thread_diameter_mm=readback["thread_diameter_mm"],
    )
