"""Project-owned helpers for period British Association tapped holes.

Unprovisioned SolidWorks seats have no BA rows in the stock BSI Hole Wizard
database.  A metric HoleWzd seed would leave contradictory M2.5 metadata in the
authoritative model, so BA holes are explicit core-diameter cuts with model-owned
6 BA cosmetic threads.  The build-seat provisioner creates a project-owned copy
of the Toolbox database with the same 6 BA data for native interactive use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import _telemetry

from _common import (
    SketchDims,
    check,
    define_circle,
    ensure_fully_defined,
    name_last_feature,
    set_sketch_direct_db,
)


class TapEnd(str, Enum):
    THROUGH = "through"
    BOTTOMING = "bottoming"


@dataclass(frozen=True)
class TapSpec:
    designation: str
    major_diameter_mm: float
    pitch_mm: float
    angle_deg: float

    @property
    def radial_depth_mm(self) -> float:
        return 0.6 * self.pitch_mm

    @property
    def core_diameter_mm(self) -> float:
        return self.major_diameter_mm - 2.0 * self.radial_depth_mm

    @property
    def crest_root_radius_mm(self) -> float:
        return 0.18083 * self.pitch_mm


BA6 = TapSpec("6 BA", 2.80, 0.53, 47.5)


@dataclass(frozen=True)
class CreatedTapPattern:
    feature: Any
    core_diameter_mm: float
    thread_diameter_mm: float
    drive_jobs: tuple[tuple[str, str], ...]


async def add_cosmetic_ba_threads(
    adapter: Any,
    *,
    points_xy: tuple[tuple[float, float], ...],
    z_face_mm: float,
    end: TapEnd,
    tap: TapSpec = BA6,
    thread_depth_mm: float | None = None,
) -> None:
    """Attach read-validated 6 BA cosmetic threads to drilled circular edges."""
    from solidworks_mcp.adapters.solidworks.features import (
        _flag_feature_methods,
        _read_member,
        _select_edges_geometric,
    )
    from solidworks_mcp.adapters import sw_type_info
    from solidworks_mcp.adapters.solidworks.manufacturing import (
        _THREAD_END_TYPES,
        _THREAD_STANDARDS,
    )
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    if end is TapEnd.BOTTOMING and thread_depth_mm is None:
        raise ValueError("bottoming cosmetic threads require thread_depth_mm")
    for index, (x_mm, y_mm) in enumerate(points_xy):
        edge_point = [
            x_mm + tap.core_diameter_mm / 2.0,
            y_mm,
            z_face_mm,
        ]
        if not _select_edges_geometric(adapter, [edge_point], tol_mm=0.1):
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1}: "
                f"circular edge not found at {edge_point}"
            )
        manager = adapter.currentModel.FeatureManager
        _flag_feature_methods(manager, "IFeatureManager")
        feature = manager.InsertCosmeticThread3(
            _THREAD_STANDARDS["none"],
            "British Association",
            tap.designation,
            tap.major_diameter_mm / 1000.0,
            _THREAD_END_TYPES["through" if end is TapEnd.THROUGH else "blind"],
            0.0 if end is TapEnd.THROUGH else float(thread_depth_mm) / 1000.0,
            "",  # the drawing owns the two grouped, leadered shop callouts
        )
        if feature is None:
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1} creation failed"
            )
        _flag_feature_methods(feature, "IFeature")
        data = feature.GetDefinition()
        if data is None:
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1} has no definition"
            )
        data = sw_type_info.flagged(data, "ICosmeticThreadFeatureData")
        model = adapter.currentModel
        accessed = bool(data.AccessSelections(model, null_callout()))
        if not accessed:
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1} selections unavailable"
            )
        try:
            thread_callout = (
                f"{tap.designation}, {tap.pitch_mm:.2f} PITCH, "
                f"{tap.angle_deg:.1f} DEG INCLUDED ANGLE"
            )
            data.Standard = _THREAD_STANDARDS["bsi"]
            data.StandardType = "British Association"
            data.Size = tap.designation
            data.ThreadCallout = thread_callout
            data.Diameter = tap.major_diameter_mm / 1000.0
            data.EndCondition = _THREAD_END_TYPES[
                "through" if end is TapEnd.THROUGH else "blind"
            ]
            if end is TapEnd.BOTTOMING:
                data.BlindDepth = float(thread_depth_mm) / 1000.0
            if not feature.ModifyDefinition(data, model, null_callout()):
                raise RuntimeError(
                    f"{tap.designation} cosmetic thread {index + 1} metadata rejected"
                )
        finally:
            data.ReleaseSelectionAccess()

        feature.Name = f"{tap.designation} {end.value.title()} Thread {index + 1}"
        reread = feature.GetDefinition()
        if reread is None:
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1} read-back unavailable"
            )
        reread = sw_type_info.flagged(reread, "ICosmeticThreadFeatureData")
        expected_end = _THREAD_END_TYPES[
            "through" if end is TapEnd.THROUGH else "blind"
        ]
        expected_depth = 0.0 if end is TapEnd.THROUGH else float(thread_depth_mm)
        actual_depth = float(reread.BlindDepth) * 1000.0
        fields_match = (
            reread.Standard == _THREAD_STANDARDS["bsi"]
            and reread.ThreadCallout == thread_callout
            and abs(float(reread.Diameter) * 1000.0 - tap.major_diameter_mm) < 1e-6
            and reread.EndCondition == expected_end
            and (
                end is TapEnd.THROUGH
                or abs(actual_depth - expected_depth) < 1e-6
            )
        )
        if not fields_match:
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1} metadata read-back "
                f"failed: standard={reread.Standard!r}, "
                f"type={reread.StandardType!r}, size={reread.Size!r}, "
                f"callout={reread.ThreadCallout!r}, "
                f"diameter_mm={float(reread.Diameter) * 1000.0!r}, "
                f"end={reread.EndCondition!r}, depth_mm={actual_depth!r}"
            )
        feature_name = str(_read_member(feature, "Name") or "")
        if not feature_name:
            raise RuntimeError(
                f"{tap.designation} cosmetic thread {index + 1} has no feature name"
            )
        adapter.currentModel.ClearSelection2(True)
        _telemetry.success(f"added {tap.designation} cosmetic thread {index + 1}")


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
    add_threads: bool = True,
    diameter_drive: str | None = None,
) -> CreatedTapPattern:
    """Cut bottoming tap drills and apply model-owned BA cosmetic threads."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    if not points_xy:
        raise ValueError("tapped pattern needs at least one point")
    if end is not TapEnd.BOTTOMING:
        raise ValueError("through BA patterns use an explicit through cut")
    if hole_depth_mm is None or thread_depth_mm is None:
        raise ValueError("bottoming taps require hole_depth_mm and thread_depth_mm")
    if abs(z_face_mm) > 1e-9 or normal_sign != -1:
        raise ValueError("bottoming BA helper currently supports the Front face")

    dimensions = SketchDims()
    check(f"create_sketch {name} thread cores", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for index, (x_mm, y_mm) in enumerate(points_xy):
        await define_circle(
            adapter,
            x_mm,
            y_mm,
            tap.core_diameter_mm / 2.0,
            f"{tap.designation} core ({x_mm:g}, {y_mm:g})",
            dims=dimensions,
            names=(f"{name}P{index}X", f"{name}P{index}Y", f"{name}P{index}Dia"),
            drives=(None, None, diameter_drive),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, f"{name} thread-core sketch")
    check(f"exit_sketch {name} thread cores", await adapter.exit_sketch())
    profile_name = f"{name}CoreProfile"
    name_last_feature(adapter, profile_name)
    drive_jobs = tuple(dimensions.apply(adapter, profile_name))
    check(
        f"cut {name} thread cores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * float(hole_depth_mm), both_directions=True
            )
        ),
    )
    feature_name = f"{name}CoreHoles"
    name_last_feature(adapter, feature_name)
    feature = adapter.currentModel.FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"created thread-core feature {feature_name!r} is missing")
    if add_threads:
        await add_cosmetic_ba_threads(
            adapter,
            points_xy=points_xy,
            z_face_mm=z_face_mm,
            end=end,
            tap=tap,
            thread_depth_mm=thread_depth_mm,
        )
    return CreatedTapPattern(
        feature=feature,
        core_diameter_mm=tap.core_diameter_mm,
        thread_diameter_mm=tap.major_diameter_mm,
        drive_jobs=drive_jobs,
    )
