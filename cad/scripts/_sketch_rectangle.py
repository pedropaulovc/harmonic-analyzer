"""Fully-defined centred rectangle recipes.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _check import check
from _com import _early_bound, _read_member
from _sketch import SketchDims, add_line_chain, dimension_between


@_telemetry.traced("sketch.rectangle", label_param="label")
async def define_centered_rectangle(
    adapter: Any,
    half_x: float,
    half_z: float,
    label: str,
    *,
    dims: "SketchDims | None" = None,
    name_width: str | None = None,
    name_depth: str | None = None,
    drive_width: str | None = None,
    drive_depth: str | None = None,
) -> list[str]:
    """Draw an origin-centred rectangle with two construction diagonals.

    The midpoint of one corner-to-corner diagonal is coincident with the sketch
    origin, so width and depth are the only driving dimensions. This mirrors a
    native center rectangle without its cursor-inference side effects: an exact
    square passed to ``CreateCenterRectangle`` can acquire a redundant SAME
    LENGTH relation or duplicate origin coincidence and turn dimensions into
    references, which later makes equation assignment warn or fail.
    """
    if abs(half_x - half_z) >= 1e-9:
        sketch_mgr = adapter.currentSketchManager
        previous_add_to_db = bool(sketch_mgr.AddToDB)
        sketch_mgr.AddToDB = False
        try:
            raw = sketch_mgr.CreateCenterRectangle(
                0.0, 0.0, 0.0, half_x / 1000.0, half_z / 1000.0, 0.0
            )
        finally:
            sketch_mgr.AddToDB = previous_add_to_db
        segments = list(raw or [])
        edges: list[tuple[str, float, float]] = []
        diagonal_id: str | None = None
        for segment in segments:
            if bool(_read_member(segment, "ConstructionGeometry")):
                # CreateCenterRectangle returns two corner-to-corner construction
                # diagonals; keep one to anchor the centre to the origin below.
                if diagonal_id is None:
                    diagonal_id = adapter._register_sketch_entity("Line", segment)
                continue
            entity_id = adapter._register_sketch_entity("Line", segment)
            start = _read_member(segment, "GetStartPoint2")
            end = _read_member(segment, "GetEndPoint2")
            dx = (
                float(_read_member(end, "X")) - float(_read_member(start, "X"))
            ) * 1000.0
            dz = (
                float(_read_member(end, "Y")) - float(_read_member(start, "Y"))
            ) * 1000.0
            edges.append((entity_id, dx, dz))
        if len(edges) != 4:
            raise RuntimeError(
                f"{label}: center rectangle returned {len(edges)} profile edges, expected 4"
            )
        horizontal = next(
            (row for row in edges if abs(row[1]) > 1e-9 and abs(row[2]) < 1e-9),
            None,
        )
        vertical = next(
            (row for row in edges if abs(row[2]) > 1e-9 and abs(row[1]) < 1e-9),
            None,
        )
        if horizontal is None or vertical is None:
            raise RuntimeError(
                f"{label}: native center rectangle has no orthogonal edge pair"
            )
        await dimension_between(
            adapter,
            f"{horizontal[0]}.start",
            f"{horizontal[0]}.end",
            "horizontal_distance",
            abs(horizontal[1]),
            f"{label} width",
        )
        await dimension_between(
            adapter,
            f"{vertical[0]}.start",
            f"{vertical[0]}.end",
            "vertical_distance",
            abs(vertical[2]),
            f"{label} depth",
        )
        # Deterministically anchor the rectangle centre to the origin.
        # SolidWorks only auto-adds the centre->origin coincidence when the
        # "add constraints to sketched rectangles" system option
        # (swSketchAddConstToRectEntity) is ON. It is OFF on some seats, which
        # leaves the native centre rectangle free to translate (under_defined)
        # even with width+depth dims — the build must not depend on a per-seat
        # UI toggle. If the profile is not already fully defined, pin one
        # construction diagonal's midpoint to the origin. Idempotent: skipped
        # when the native anchor already fixed it, so it never over-defines the
        # seat where the option is on.
        rect_state = await adapter.check_sketch_fully_defined()
        already_defined = bool(
            rect_state.is_success
            and rect_state.data
            and rect_state.data.get("definition_state") == "fully_defined"
        )
        if not already_defined:
            _telemetry.warn(
                f"{label}: native centre rectangle under-defined after width+depth "
                "dims — the seat's 'add constraints to sketched rectangles' option "
                "(swSketchAddConstToRectEntity) is off, so no centre->origin anchor "
                "was auto-added; pinning one construction diagonal's midpoint to the "
                "origin explicitly."
            )
            if diagonal_id is not None:
                check(
                    f"{label} centre -> origin",
                    await adapter.add_sketch_constraint(
                        "origin", diagonal_id, "midpoint"
                    ),
                )
        if dims is not None:
            dims.record(name_width, drive_width)
            dims.record(name_depth, drive_depth)
        return [entity_id for entity_id, _, _ in edges]

    points = [
        (-half_x, -half_z),
        (half_x, -half_z),
        (half_x, half_z),
        (-half_x, half_z),
    ]
    edges = await add_line_chain(adapter, points)
    sketch_mgr = adapter.currentSketchManager
    previous_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    diagonals: list[str] = []
    try:
        for start, end in ((points[0], points[2]), (points[1], points[3])):
            result = await adapter.add_line(*start, *end)
            diagonal_id = check(f"add construction diagonal {label}", result)
            # ConstructionGeometry is declared on the base ISketchSegment, not the
            # derived ISketchLine the entity is bound as — rebind before the set.
            diagonal = _early_bound(
                adapter._sketch_entities[diagonal_id], "ISketchSegment"
            )
            diagonal.ConstructionGeometry = True
            diagonals.append(diagonal_id)
    finally:
        sketch_mgr.AddToDB = previous_add_to_db
    for edge, direction in zip(
        edges, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
    ):
        check(
            f"{label} {direction} {edge}",
            await adapter.add_sketch_constraint(edge, None, direction),
        )
    check(
        f"{label} midpoint -> origin",
        await adapter.add_sketch_constraint("origin", diagonals[0], "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{edges[0]}.start",
        f"{edges[0]}.end",
        "horizontal_distance",
        2.0 * half_x,
        f"{label} width",
    )
    await dimension_between(
        adapter,
        f"{edges[1]}.start",
        f"{edges[1]}.end",
        "vertical_distance",
        2.0 * half_z,
        f"{label} depth",
    )
    if dims is not None:
        dims.record(name_width, drive_width)
        dims.record(name_depth, drive_depth)
    return edges
