r"""Build the cone pivot post's saw cradle (MHA-DT-005-TL-02; shop fixture).

A 1018 block the bandsaw vise grips: two saddles bored on one axis carry the
post body, a pad between them carries the cone sleeve's north cap, and two
3/8-16 taps take the cap-bridge studs
(``dt_cone_pivot_post_tl_saw_cradle_spec``). One is made.

Layout (spec frame: X along the post, Y up from the underside, Z across from
the base side face; the origin is the base corner, so every sketch dimension
runs from a touchable edge):

* base: a Top-plane rectangle from the origin corner, extruded +Y;
* saddles: two Front-plane rectangles standing on the underside line,
  extruded across the base; their stations and the overall height run from
  the origin corner;
* seats: one Right-plane circle cut through both saddles. A construction
  witness from its centre to its lowest point carries the seat-bottom
  height, so the print measures the touchable seat line, not the axis;
* pad: a Top-plane land under the cone cap, left proud of the seat bottoms
  as fitting stock (a matched fit to the post's cap), added after the seat
  cut so the cut never grazes it; its ends stop short of the bridge studs;
* relief: one Right-plane cut trims the saddles to the saddle width,
  measured from the base side face;
* stud taps: one native 3/8-16 Hole Wizard feature through the base.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_pivot_post_tl_saw_cradle.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _hole_spec import blind_cut_dia_mm
from _holes import SharedCoordinate, wizard_holes
from _saved_part_guard import require_saved_drawing_properties
from dt_cone_pivot_post_tl_saw_cradle_spec import (
    BASE_HT,
    BASE_LENGTH,
    BASE_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FOOT_SADDLE_X,
    HEAD_SADDLE_X,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_HT,
    PAD_HT,
    PAD_X0,
    PAD_X1,
    PAD_Z0,
    PAD_Z1,
    SADDLE_Z,
    SEAT_BOTTOM_Y,
    SEAT_CENTRE_Y,
    SEAT_DIA,
    SEAT_Z,
    STUD_TAP_SPEC,
    STUD_X,
    STUD_Z,
)

PART_NAME = "dt-cone-pivot-post-tl-saw-cradle"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1018 bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# The relief cut's rectangles overrun the base ends in Z and the saddle tops
# in Y so no cut face lies on a body face.
_RELIEF_OVERRUN = 5.0
_RELIEF_TOP = OVERALL_HT + 6.0

_SADDLE_LENGTH = (HEAD_SADDLE_X[1] - HEAD_SADDLE_X[0]) + (FOOT_SADDLE_X[1] - FOOT_SADDLE_X[0])
_PAD_AREA = (PAD_X1 - PAD_X0) * (PAD_Z1 - PAD_Z0)
_TRIMMED_Z = BASE_WIDTH - (SADDLE_Z[1] - SADDLE_Z[0])
V_BASE = BASE_LENGTH * BASE_WIDTH * BASE_HT
V_SADDLES = V_BASE + _SADDLE_LENGTH * (OVERALL_HT - BASE_HT) * BASE_WIDTH


def _seat_segment_area() -> float:
    """Area of the seat circle below the saddle tops (one saddle's cut)."""
    radius = SEAT_DIA / 2.0
    rise = SEAT_CENTRE_Y - OVERALL_HT
    return radius**2 * math.acos(rise / radius) - rise * math.sqrt(radius**2 - rise**2)


V_SEATED = V_SADDLES - _seat_segment_area() * _SADDLE_LENGTH
V_PADDED = V_SEATED + _PAD_AREA * (PAD_HT - BASE_HT)
# The seats and the pad lie inside the saddle width, so the relief never
# reaches them.
V_RELIEVED = V_PADDED - _TRIMMED_Z * _SADDLE_LENGTH * (OVERALL_HT - BASE_HT)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch segment as construction geometry.

    ``ConstructionGeometry`` lives on ISketchSegment, not the derived
    ISketchLine bound by the entity registry. The seat-bottom witness carries
    its native dimension while staying out of the cut profile.
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _rectangle(adapter, points: list[tuple[float, float]], label: str) -> list[str]:
    """An axis-parallel closed rectangle; the caller supplies its four
    position relations/dimensions. Lines run points[i] -> points[i + 1]."""
    lines = await add_line_chain(adapter, points)
    for index, line in enumerate(lines):
        relation = "horizontal" if index % 2 == 0 else "vertical"
        check(
            f"{label} {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    return lines


async def _dimension(
    adapter, dims: SketchDims, ref: str, kind: str, value: float, name: str | None,
    drive: str | None,
) -> None:
    await dimension_between(adapter, "origin", ref, kind, value, name or kind)
    dims.record(name, drive)


async def _relate(adapter, first: str, second: str, relation: str, label: str) -> None:
    check(label, await adapter.add_sketch_constraint(first, second, relation))


async def _saddle_profile(adapter, dims: SketchDims) -> None:
    """Both saddles standing on the underside line (Front sketch = model XY).

    Lines run bottom, right, top, left, so ``lines[3].start`` is the top-left
    corner and ``lines[2].start`` the top-right: the stations and the overall
    height are measured to the saddle tops from the origin corner.
    """
    head = await _rectangle(
        adapter,
        [(HEAD_SADDLE_X[0], 0.0), (HEAD_SADDLE_X[1], 0.0),
         (HEAD_SADDLE_X[1], OVERALL_HT), (HEAD_SADDLE_X[0], OVERALL_HT)],
        "head saddle",
    )
    foot = await _rectangle(
        adapter,
        [(FOOT_SADDLE_X[0], 0.0), (FOOT_SADDLE_X[1], 0.0),
         (FOOT_SADDLE_X[1], OVERALL_HT), (FOOT_SADDLE_X[0], OVERALL_HT)],
        "foot saddle",
    )
    await _dimension(adapter, dims, f"{head[3]}.start", "horizontal_distance",
                     HEAD_SADDLE_X[0], "HeadSaddleX0", '"HeadSaddleX0"')
    await _dimension(adapter, dims, f"{head[3]}.start", "vertical_distance",
                     OVERALL_HT, "OverallHt", '"OverallHt"')
    await _dimension(adapter, dims, f"{head[2]}.start", "horizontal_distance",
                     HEAD_SADDLE_X[1], "HeadSaddleX1", '"HeadSaddleX1"')
    await _dimension(adapter, dims, f"{foot[3]}.start", "horizontal_distance",
                     FOOT_SADDLE_X[0], "FootSaddleX0", '"FootSaddleX0"')
    await _dimension(adapter, dims, f"{foot[2]}.start", "horizontal_distance",
                     FOOT_SADDLE_X[1], "FootSaddleX1", '"FootSaddleX1"')
    await _relate(adapter, f"{head[0]}.start", "origin", "horizontal_points",
                  "head saddle on the underside line")
    await _relate(adapter, f"{foot[0]}.start", "origin", "horizontal_points",
                  "foot saddle on the underside line")
    await _relate(adapter, f"{foot[3]}.start", f"{head[3]}.start", "horizontal_points",
                  "foot saddle top level with the head saddle's")


async def _pad_profile(adapter, dims: SketchDims) -> None:
    """The cap pad's plan (Top sketch (u, v) = model (X, -Z)).

    Lines run from the near-end, head-side corner, so ``lines[0].start`` is
    (PadX0, PadZ0), ``lines[1].start`` (PadX1, PadZ0) and ``lines[3].start``
    (PadX0, PadZ1): every station runs from the origin corner, the X stations
    to the end nearer the view's top edge and the Z stations to the head side.
    """
    pad = await _rectangle(
        adapter,
        [(PAD_X0, -PAD_Z0), (PAD_X1, -PAD_Z0), (PAD_X1, -PAD_Z1), (PAD_X0, -PAD_Z1)],
        "cap pad",
    )
    await _dimension(adapter, dims, f"{pad[0]}.start", "horizontal_distance",
                     PAD_X0, "PadX0", '"PadX0"')
    await _dimension(adapter, dims, f"{pad[0]}.start", "vertical_distance",
                     PAD_Z0, "PadZ0", '"PadZ0"')
    await _dimension(adapter, dims, f"{pad[1]}.start", "horizontal_distance",
                     PAD_X1, "PadX1", '"PadX1"')
    await _dimension(adapter, dims, f"{pad[3]}.start", "vertical_distance",
                     PAD_Z1, "PadZ1", '"PadZ1"')


async def _relief_profile(adapter, dims: SketchDims) -> None:
    """Trim the saddles to the saddle width (Right sketch (u, v) =
    model (-Z, Y)), measured to the base-top corners from the origin corner."""
    near = await _rectangle(
        adapter,
        [(_RELIEF_OVERRUN, BASE_HT), (-SADDLE_Z[0], BASE_HT),
         (-SADDLE_Z[0], _RELIEF_TOP), (_RELIEF_OVERRUN, _RELIEF_TOP)],
        "near relief",
    )
    far_edge = BASE_WIDTH + _RELIEF_OVERRUN
    far = await _rectangle(
        adapter,
        [(-SADDLE_Z[1], BASE_HT), (-far_edge, BASE_HT),
         (-far_edge, _RELIEF_TOP), (-SADDLE_Z[1], _RELIEF_TOP)],
        "far relief",
    )
    await _dimension(adapter, dims, f"{near[1]}.start", "horizontal_distance",
                     SADDLE_Z[0], "SaddleZ0", '"SaddleZ0"')
    await _dimension(adapter, dims, f"{near[1]}.start", "vertical_distance",
                     BASE_HT, "ReliefFloorHt", '"BaseHt"')
    await _dimension(adapter, dims, f"{near[3]}.start", "horizontal_distance",
                     _RELIEF_OVERRUN, None, None)
    await _dimension(adapter, dims, f"{near[3]}.start", "vertical_distance",
                     _RELIEF_TOP, None, None)
    await _dimension(adapter, dims, f"{far[0]}.start", "horizontal_distance",
                     SADDLE_Z[1], "SaddleZ1", '"SaddleZ1"')
    await _dimension(adapter, dims, f"{far[1]}.start", "horizontal_distance",
                     far_edge, None, None)
    await _relate(adapter, f"{far[0]}.start", f"{near[1]}.start", "horizontal_points",
                  "far relief floor level with the near one's")
    await _relate(adapter, f"{far[2]}.start", f"{near[3]}.start", "horizontal_points",
                  "far relief top level with the near one's")


async def _seat_profile(adapter, dims: SketchDims) -> None:
    """The seat circle, located by its touchable lowest line.

    Right-sketch (u, v) -> model (-Z, Y). The construction witness runs from
    the circle centre straight down to the circle, so its end is the seat
    bottom the post body lies on.
    """
    radius = SEAT_DIA / 2.0
    set_sketch_direct_db(adapter, True)
    try:
        circle = check(
            "seat circle", await adapter.add_circle(-SEAT_Z, SEAT_CENTRE_Y, radius)
        )
        witness = check(
            "seat-bottom witness",
            await adapter.add_line(-SEAT_Z, SEAT_CENTRE_Y, -SEAT_Z, SEAT_BOTTOM_Y),
        )
    finally:
        set_sketch_direct_db(adapter, False)
    _as_construction(adapter, witness)
    await _relate(adapter, f"{witness}.start", f"{circle}.center", "coincident",
                  "witness from the seat centre")
    check("witness vertical", await adapter.add_sketch_constraint(witness, None, "vertical"))
    await _relate(adapter, f"{witness}.end", circle, "coincident", "witness ends on the seat")
    await _dimension(adapter, dims, f"{circle}.center", "horizontal_distance",
                     SEAT_Z, "SeatZ", '"SeatZ"')
    await _dimension(adapter, dims, f"{witness}.end", "vertical_distance",
                     SEAT_BOTTOM_Y, "SeatBottomHt", '"SeatBottomHt"')
    check(
        "seat diameter",
        await adapter.add_sketch_dimension(circle, None, "diameter", SEAT_DIA),
    )
    dims.record("SeatDia", '"SeatDia"')


async def _sketch_feature(adapter, plane: str, label: str, profile, name: str) -> list[tuple[str, str]]:
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await profile(adapter, dims)
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, name)
    return dims.apply(adapter, name)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BaseLength", BASE_LENGTH),
        ("BaseWidth", BASE_WIDTH),
        ("BaseHt", BASE_HT),
        ("OverallHt", OVERALL_HT),
        ("HeadSaddleX0", HEAD_SADDLE_X[0]),
        ("HeadSaddleX1", HEAD_SADDLE_X[1]),
        ("FootSaddleX0", FOOT_SADDLE_X[0]),
        ("FootSaddleX1", FOOT_SADDLE_X[1]),
        ("SaddleZ0", SADDLE_Z[0]),
        ("SaddleZ1", SADDLE_Z[1]),
        ("SeatZ", SEAT_Z),
        ("SeatBottomHt", SEAT_BOTTOM_Y),
        ("SeatDia", SEAT_DIA),
        ("PadX0", PAD_X0),
        ("PadX1", PAD_X1),
        ("PadZ0", PAD_Z0),
        ("PadZ1", PAD_Z1),
        ("PadHt", PAD_HT),
        ("StudX", STUD_X),
        ("StudNearZ", STUD_Z[0]),
        ("StudFarZ", STUD_Z[1]),
    ):
        await set_global(adapter, name, f"{value}mm")

    # Base: the rectangle's first corner is the origin, so only its two
    # sizes are dimensions (Top sketch (u, v) = model (X, -Z)).
    base = SketchDims()
    check("create_sketch base", await adapter.create_sketch("Top"))
    base_rect = [(0.0, 0.0), (BASE_LENGTH, 0.0), (BASE_LENGTH, -BASE_WIDTH), (0.0, -BASE_WIDTH)]
    base_lines = await add_line_chain(adapter, base_rect)
    await define_rectilinear_chain(
        adapter,
        base_lines,
        base_rect,
        label="base",
        dims=base,
        names=["BaseLength", "BaseWidth"],
        drives=['"BaseLength"', '"BaseWidth"'],
    )
    await ensure_fully_defined(adapter, "base sketch")
    check("exit_sketch base", await adapter.exit_sketch())
    name_last_feature(adapter, "BaseProfile")
    drive_jobs = base.apply(adapter, "BaseProfile")
    check("extrude base", await adapter.create_extrusion(ExtrusionParameters(depth=BASE_HT)))
    name_last_feature(adapter, "Base")
    drive_jobs.append((name_dimensions(adapter, "Base", ["BaseHt"])[0], '"BaseHt"'))
    await volume_check(adapter, "base", V_BASE, 0.005 * V_BASE)

    drive_jobs += await _sketch_feature(
        adapter, "Front", "saddles", _saddle_profile, "SaddleProfile"
    )
    check(
        "extrude saddles",
        await adapter.create_extrusion(ExtrusionParameters(depth=BASE_WIDTH)),
    )
    name_last_feature(adapter, "Saddles")
    drive_jobs.append(
        (name_dimensions(adapter, "Saddles", ["SaddleDepth"])[0], '"BaseWidth"')
    )
    await volume_check(adapter, "saddles", V_SADDLES, 0.005 * V_SADDLES)

    drive_jobs += await _sketch_feature(adapter, "Right", "seat", _seat_profile, "SeatProfile")
    check(
        "cut seats",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BASE_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Seats")
    await volume_check(adapter, "seats", V_SEATED, 0.005 * V_SEATED)

    # The pad rises from the underside plane to its unfitted reference height;
    # the print's callout fits it to the post's cap.
    drive_jobs += await _sketch_feature(adapter, "Top", "cap pad", _pad_profile, "PadProfile")
    check("extrude pad", await adapter.create_extrusion(ExtrusionParameters(depth=PAD_HT)))
    name_last_feature(adapter, "Pad")
    drive_jobs.append((name_dimensions(adapter, "Pad", ["PadHt"])[0], '"PadHt"'))
    await volume_check(adapter, "pad", V_PADDED, 0.005 * V_PADDED)

    drive_jobs += await _sketch_feature(
        adapter, "Right", "relief", _relief_profile, "ReliefProfile"
    )
    check(
        "cut relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BASE_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Relief")
    await volume_check(adapter, "relief", V_RELIEVED, 0.005 * V_RELIEVED)

    # Cap-bridge stud taps: ONE native 3/8-16 feature, two through-all
    # instances from the base top beside the saddles. The far stud shares the
    # near one's X station by relation, so one printed "2X" StudX locates both.
    tap_drill = blind_cut_dia_mm(STUD_TAP_SPEC)
    taps = wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[STUD_X, BASE_HT, z] for z in STUD_Z],
        (0.0, 1.0, 0.0),
        "cap-bridge stud taps (3/8-16 UNC-2B)",
        name="StudTaps",
        expect_dia_mm=tap_drill,
        placement_dims=[
            (("StudX", '"StudX"'), ("StudNearZ", '"StudNearZ"')),
            (SharedCoordinate(0), ("StudFarZ", '"StudFarZ"')),
        ],
    )
    drive_jobs += taps.placement_drive_jobs
    v_taps = 2.0 * math.pi * (tap_drill / 2.0) ** 2 * BASE_HT
    expected = V_RELIEVED - v_taps
    await volume_check(adapter, "stud taps", expected, 0.02 * v_taps)
    _require_one_solid_body(adapter, label="cradle")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cradle (equations neutral)", expected, 0.005 * expected
    )
    _require_one_solid_body(adapter, label="driven cradle")
    for axis, extent in (("x", BASE_LENGTH), ("y", OVERALL_HT), ("z", BASE_WIDTH)):
        await bbox_extent_check(adapter, f"cradle {axis} extent", axis, extent)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
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
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
