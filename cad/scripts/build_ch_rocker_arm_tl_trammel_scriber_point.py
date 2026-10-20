r"""Build the rocker template trammel's scriber point (MHA-CH-06-TL-16; shop tooling).

A 1/4 in O1 drill-rod point cut to length with a 30 degree tip cone and a
stated tip flat (``ch_rocker_arm_tl_trammel_scriber_point_spec``). Layout:

* ``PointProfile`` on the Front plane, revolved 360 degrees about model +X:
  the cone from the theoretical sharp apex at the origin to the rod O.D., the
  rod to the faced back end. It carries the overall length, the rod O.D. and
  the cone's half-angle (the title block's angular band halved, symmetric).
* ``TipFlatProfile`` on the Front plane, revolve-cut: the tip flat, its
  diameter a MAX-limit dimension and its station driven from that diameter
  and the half-angle so the flat always sits on the cone.
* ``HardenedZoneReference``: a hidden construction line from the apex,
  dimensioned to the hardened zone's extent for the print.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_trammel_scriber_point.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_angular_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from ch_rocker_arm_tl_trammel_scriber_point_spec import (
    CONE_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HARDENED_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    POINT_LENGTH,
    ROD_DIA,
    ROD_R,
    TIP_FLAT_DIA,
    TIP_FLAT_DIA_BAND,
    TIP_FLAT_DIA_MAX,
    TIP_FLAT_DIA_TOL_TYPE,
    TIP_FLAT_STATION,
    TIP_HALF_ANGLE,
    TIP_HALF_ANGLE_TOL_DEG,
)

PART_NAME = "ch-rocker-arm-tl-trammel-scriber-point"
MATERIAL = "Alloy Steel"  # the registry row names the O1 drill rod
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

FLAT_R = TIP_FLAT_DIA / 2.0
# The tip-flat cutter reaches back past the apex and out past the rod.
_CUTTER_BACK = 1.0
_CUTTER_HEIGHT = ROD_R + 1.0

_ROD_AREA = math.pi * ROD_R**2
V_TURNED = _ROD_AREA * (POINT_LENGTH - CONE_LENGTH) + _ROD_AREA * CONE_LENGTH / 3.0
V_TIP = math.pi * FLAT_R**2 * TIP_FLAT_STATION / 3.0
V_TOTAL = V_TURNED - V_TIP


def _one_solid_body(adapter, *, label: str):
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )
    return bodies[0]


def _face_count(adapter, *, label: str) -> int:
    body = _one_solid_body(adapter, label=label)
    return int(_early_bound(body, "IBody2").GetFaceCount())


def _set_tip_flat_max_limit(adapter) -> None:
    """The tip flat as the single limit "MAX" (swTolMAX; drawing-guidelines
    rule 16): SolidWorks prints the nominal then the limit word, so the
    nominal is the limit; the deviations stay on the native tolerance as the
    model's record of the band. Copied from the knob shaft's run-out limit.

    The nominal check holds to 1 um, not 1 pm: the equation manager stores the
    "TipFlatDia" global in inches to eight places (0.1 mm reads back as
    0.00393701 in, 0.100000054 mm), so the driven value is never bit-exact.
    """
    lower, upper = deviations(TIP_FLAT_DIA_BAND)
    _, dimension = _named_dimension(adapter, "TipFlatProfile", "TipFlatDia")
    label = "TipFlatDia@TipFlatProfile"
    value_m = float(dimension.SystemValue)
    if not math.isclose(value_m, TIP_FLAT_DIA_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value_m * 1000.0:.9f} mm is not the printed "
            f"maximum {TIP_FLAT_DIA_MAX:g} mm"
        )
    raw_tolerance = dimension.Tolerance
    if raw_tolerance is None:
        raise RuntimeError(f"{label}: native dimension has no tolerance")
    tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
    tolerance.Type = TIP_FLAT_DIA_TOL_TYPE
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != TIP_FLAT_DIA_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {TIP_FLAT_DIA_MAX:g} MAX")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("PointLength", POINT_LENGTH),
        ("RodDia", ROD_DIA),
        ("TipFlatDia", TIP_FLAT_DIA),
        ("HardenedLength", HARDENED_LENGTH),
    ):
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "TipHalfAngle", f"{TIP_HALF_ANGLE}deg")

    # --- Turned point: apex at the origin, axis along +X -------------------
    profile = SketchDims()
    drive_jobs: list[tuple[str, str]] = []
    check("create_sketch point profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "point axis", await adapter.add_centerline(0.0, 0.0, POINT_LENGTH, 0.0)
    )
    lines = await add_line_chain(
        adapter,
        [(0.0, 0.0), (CONE_LENGTH, ROD_R), (POINT_LENGTH, ROD_R), (POINT_LENGTH, 0.0)],
    )
    set_sketch_direct_db(adapter, False)
    cone, outline, back, axis_line = lines
    for i in range(len(lines)):
        check(
            f"point profile junction {i}",
            await adapter.add_sketch_constraint(
                f"{lines[i]}.end", f"{lines[(i + 1) % len(lines)]}.start", "coincident"
            ),
        )
    for label, first, second, relation in (
        ("point axis horizontal", axis, None, "horizontal"),
        ("point axis at the apex", f"{axis}.start", "origin", "coincident"),
        ("point axis at the back face", f"{axis}.end", f"{back}.end", "coincident"),
        ("apex at the origin", f"{cone}.start", "origin", "coincident"),
        ("rod outline horizontal", outline, None, "horizontal"),
        ("back face vertical", back, None, "vertical"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    await dimension_between(
        adapter,
        f"{cone}.start",
        f"{back}.start",
        "horizontal_distance",
        POINT_LENGTH,
        "point length, apex to back face",
    )
    profile.record("PointLength", '"PointLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        outline,
        text_xy=(POINT_LENGTH / 2.0, ROD_R + 4.0),
        label="rod diameter",
    )
    profile.record("RodDia", '"RodDia"')
    check(
        "tip half-angle",
        await adapter.add_sketch_dimension(cone, axis_line, "angular", TIP_HALF_ANGLE),
    )
    profile.record("TipHalfAngle", '"TipHalfAngle"')
    await ensure_fully_defined(adapter, "point profile")
    check("exit_sketch point profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PointProfile")
    drive_jobs += profile.apply(adapter, "PointProfile")
    check("revolve point", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Point")
    await volume_check(adapter, "turned point", V_TURNED, 0.005 * V_TURNED)
    faces_turned = _face_count(adapter, label="turned point")

    # --- Tip flat (rule 16): a revolve cut square to the axis --------------
    flat = SketchDims()
    check("create_sketch tip flat", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    flat_axis = check(
        "tip flat axis", await adapter.add_centerline(0.0, 0.0, TIP_FLAT_STATION, 0.0)
    )
    cutter = await add_line_chain(
        adapter,
        [
            (TIP_FLAT_STATION, 0.0),
            (TIP_FLAT_STATION, FLAT_R),
            (TIP_FLAT_STATION, _CUTTER_HEIGHT),
            (-_CUTTER_BACK, _CUTTER_HEIGHT),
            (-_CUTTER_BACK, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    flat_face, flat_run, cutter_top, cutter_back, cutter_base = cutter
    for i in range(len(cutter)):
        check(
            f"tip flat junction {i}",
            await adapter.add_sketch_constraint(
                f"{cutter[i]}.end",
                f"{cutter[(i + 1) % len(cutter)]}.start",
                "coincident",
            ),
        )
    for label, first, second, relation in (
        ("tip flat axis horizontal", flat_axis, None, "horizontal"),
        ("tip flat axis at the apex", f"{flat_axis}.start", "origin", "coincident"),
        (
            "tip flat axis at the flat",
            f"{flat_axis}.end",
            f"{flat_face}.start",
            "coincident",
        ),
        ("tip flat vertical", flat_face, None, "vertical"),
        ("cutter face vertical", flat_run, None, "vertical"),
        ("cutter top horizontal", cutter_top, None, "horizontal"),
        ("cutter back vertical", cutter_back, None, "vertical"),
        ("cutter base horizontal", cutter_base, None, "horizontal"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    await add_diametric_linear_dimension(
        adapter,
        flat_axis,
        f"{flat_face}.end",
        text_xy=(TIP_FLAT_STATION - 2.0, FLAT_R + 2.0),
        label="tip flat diameter",
    )
    flat.record("TipFlatDia", '"TipFlatDia"')
    # The flat sits on the cone: its station follows the diameter and the
    # half-angle, so neither can move it off the cone.
    await dimension_between(
        adapter,
        f"{flat_axis}.start",
        f"{flat_axis}.end",
        "horizontal_distance",
        TIP_FLAT_STATION,
        "tip flat station from the apex",
    )
    flat.record("TipFlatStation", f'"TipFlatDia" / 2 / tan({TIP_HALF_ANGLE:g})')
    await dimension_between(
        adapter,
        f"{cutter_back}.start",
        f"{cutter_back}.end",
        "vertical_distance",
        _CUTTER_HEIGHT,
        "tip flat cutter height",
    )
    flat.record("CutterHeight")
    await dimension_between(
        adapter,
        f"{cutter_back}.end",
        "origin",
        "horizontal_distance",
        _CUTTER_BACK,
        "tip flat cutter overrun behind the apex",
    )
    flat.record("CutterOverrun")
    await ensure_fully_defined(adapter, "tip flat profile")
    check("exit_sketch tip flat", await adapter.exit_sketch())
    name_last_feature(adapter, "TipFlatProfile")
    drive_jobs += flat.apply(adapter, "TipFlatProfile")
    check(
        "revolve-cut tip flat",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "TipFlat")
    # The flat's volume is far below any volume tolerance; the new planar
    # face proves the cut took.
    faces_flat = _face_count(adapter, label="tip flat")
    if faces_flat != faces_turned + 1:
        raise RuntimeError(
            f"tip flat: expected {faces_turned + 1} faces, found {faces_flat}"
        )

    # --- Hardened zone: hidden construction line from the apex -------------
    # Drawing-only: the hardened extent reads from the theoretical apex, the
    # same origin as the overall length. The part saves the sketch hidden; the
    # drawing shows it in the profile view to import the dimension.
    hardened = SketchDims()
    check("create_sketch hardened zone", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    zone = check(
        "hardened zone line", await adapter.add_line(0.0, 0.0, HARDENED_LENGTH, 0.0)
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[zone], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("hardened zone line did not take construction flag")
    check(
        "hardened zone horizontal",
        await adapter.add_sketch_constraint(zone, None, "horizontal"),
    )
    check(
        "hardened zone starts at the apex",
        await adapter.add_sketch_constraint(f"{zone}.start", "origin", "coincident"),
    )
    await dimension_between(
        adapter,
        f"{zone}.start",
        f"{zone}.end",
        "horizontal_distance",
        HARDENED_LENGTH,
        "hardened zone from the apex",
    )
    hardened.record("HardenedLength", '"HardenedLength"')
    await ensure_fully_defined(adapter, "hardened zone sketch")
    check("exit_sketch hardened zone", await adapter.exit_sketch())
    name_last_feature(adapter, "HardenedZoneReference")
    drive_jobs += hardened.apply(adapter, "HardenedZoneReference")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven scriber point (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    if _face_count(adapter, label="driven scriber point") != faces_flat:
        raise RuntimeError("driven scriber point lost its tip flat")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    _set_tip_flat_max_limit(adapter)
    set_dimension_symmetric_angular_tolerance(
        adapter, "PointProfile", "TipHalfAngle", TIP_HALF_ANGLE_TOL_DEG
    )
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
    blank_sketch(adapter, "HardenedZoneReference")
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
