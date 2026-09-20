# E2E protocol-4 shallow-source canary 20260919: drawing recipe, geometry unchanged.
r"""Create the curated machinist drawing for the lever fulcrum shaft."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from typing import Any, Iterator

import _drawing_common
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from fulcrum_shaft_spec import (
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SHAFT_DIA,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_shaft"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
END_VIEW_SCALE = 2.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)
# 1:2, like the near-identical 187 arbor on MHA-028: at 1:1 the 182 shaft's
# isometric is a ~136 mm diagonal bar whose outline ran x=0.287..0.423 -- over
# the right zone border (0.4191) AND far enough left to swallow the right-end
# perpendicularity frame at x=0.296, so that frame's leader was read as crossing
# the isometric.  At 1:2 the outline is ~x=0.321..0.389: inside the border, and
# clear of the frame.
ISO_SCALE = (1, 2)

# Left of the end circle, ON its centre height so the diameter line runs
# horizontally through the centre instead of diagonally.  x=0.030, not the old
# bbox-derived 0.0173: the callout is centred on its anchor and ~22 mm wide now
# that it renders horizontally, so 0.0173 printed it across the border rule at
# ~0.0126.  The layout audit cannot catch that: it boxes a dim as a nominal 4 mm
# half-square (_NOMINAL_DIM_HALF_M), far narrower than the real text, and even
# that box cleared the 12.7 mm zone margin at 0.0173.
FRONT_KEEP = {
    "ShaftDia": (0.030, FRONT_CENTER[1]),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
# The shaft fit lives on the source-model dimension.
DIMENSION_CALLOUTS: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# ONE-OFF SELECTION PROBE -- validation/multi-drawing-20260919 only, never    #
# merged.  Leaf 2026-09-19T23:59:06Z failed at the production coordinate pick #
# `SelectByID2("", "EDGE", 0.282, 0.205)` for minus_z_end_perpendicularity   #
# on the *Right view, BEFORE InsertGtol; the same inputs passed earlier on    #
# worker 4.  This wraps `_drawing_common._select_view_entity` for the         #
# duration of `project_part_pmi` and, without changing the production call:  #
#   1. records the live view state (name, position, scale, outline,           #
#      referenced model, transforms, viewport pixel size) and the projected   #
#      sheet position of the shaft's end centres next to the expected pick;   #
#   2. calls the ORIGINAL selection exactly once (no nudges, no retries) and   #
#      records the result and the selection-manager state;                    #
#   3. for the failing label only, on False: sweeps the view's visible edges  #
#      (`scan_view_edges`), resolves the UNIQUE -Z end circle semantically    #
#      (centre (0,0,-L/2), r=D/2, axis Z), records the source-correspondence  #
#      round trip, and performs ONE explicit `IEntity.Select4` with           #
#      `ISelectData.View`, verifying count==1, type==EDGE, IsSame==1.         #
#      Success continues (loudly) through the normal InsertGtol/rebuild/      #
#      export so the entity path is proven end to end; failure raises with    #
#      the measured candidate evidence.                                       #
# Every record is one `!!  [selection-probe] <stage> {json}` console line     #
# (visible at any HARMONIC_VERBOSITY) plus a `drawing.selection_probe` span   #
# event with the same payload.                                                #
# --------------------------------------------------------------------------- #
_PROBE_LABEL = "fulcrum shaft PMI minus_z_end_perpendicularity"
_PROBE_TAG = "[selection-probe]"
_PROBE_MAX_EDGES = 32
_SEL_EDGES = 1  # swSelectType_e.swSelEDGES
_OBJECT_SAME = 1  # swObjectEquality_e.swObjectSame
# Same identification bounds ViewEdges.circle_at applies by default.
_PROBE_CENTER_TOL_MM = 0.02
_PROBE_RADIUS_TOL_MM = 0.01
_MINUS_Z_CONTROL = next(
    control
    for control in GEOMETRIC_CONTROLS
    if control.key == "minus_z_end_perpendicularity"
)
# The -Z end face's rim: the PlanarFace normal scaled by its offset is the
# circle centre; the shaft radius is its radius; the plane normal its axis.
_MINUS_Z_CENTER_MM = tuple(
    component * _MINUS_Z_CONTROL.face.offset_mm
    for component in _MINUS_Z_CONTROL.face.normal
)
_PLUS_Z_CENTER_MM = tuple(-component for component in _MINUS_Z_CENTER_MM)
_END_RADIUS_MM = SHAFT_DIA / 2.0
_PROBE_MODEL_POINTS_MM = {
    "minus_z_center": _MINUS_Z_CENTER_MM,
    "minus_z_top": (
        _MINUS_Z_CENTER_MM[0],
        _MINUS_Z_CENTER_MM[1] + _END_RADIUS_MM,
        _MINUS_Z_CENTER_MM[2],
    ),
    "plus_z_center": _PLUS_Z_CENTER_MM,
}


def _num(value: Any, places: int) -> float | None:
    number = float(value)
    return round(number, places) if math.isfinite(number) else None


def _nums(values: Any, places: int, limit: int = 16) -> list[float | None]:
    return [_num(value, places) for value in list(values or ())[:limit]]


def _probe_record(stage: str, **payload: Any) -> None:
    text = json.dumps(payload, sort_keys=True, default=str)
    _telemetry.warn(f"{_PROBE_TAG} {stage} {text}")
    _telemetry.event("drawing.selection_probe", stage=stage, payload=text)


def _probe_attempt(operation: Any) -> Any:
    """Return the operation's value, or the exception's text -- never raise.

    Probe READS must not turn the probe itself into the failure being probed.
    """
    try:
        return operation()
    except Exception as exc:  # noqa: BLE001 -- diagnostic read
        return f"<error {type(exc).__name__}: {exc}>"


def _probe_view_state(
    adapter: Any, view: Any, *, expected_xy: tuple[float, float], label: str
) -> dict[str, Any]:
    iview = _early_bound(view, "IView")
    state: dict[str, Any] = {
        "label": label,
        "expected_xy_m": [_num(expected_xy[0], 6), _num(expected_xy[1], 6)],
        "name": _probe_attempt(lambda: str(iview.GetName2() or "")),
        "orientation": _probe_attempt(lambda: str(iview.GetOrientationName() or "")),
        "type": _probe_attempt(lambda: int(iview.Type)),
        "position_m": _probe_attempt(lambda: _nums(iview.Position, 6)),
        "scale_ratio": _probe_attempt(lambda: _nums(iview.ScaleRatio, 6)),
        "scale_decimal": _probe_attempt(lambda: _num(iview.ScaleDecimal, 6)),
        "use_sheet_scale": _probe_attempt(lambda: int(iview.UseSheetScale)),
        "outline_m": _probe_attempt(lambda: _nums(iview.GetOutline(), 6)),
        "referenced_model": _probe_attempt(
            lambda: str(iview.GetReferencedModelName() or "")
        ),
        "view_xform": _probe_attempt(lambda: _nums(iview.GetViewXform(), 9)),
        "model_to_view": _probe_attempt(
            lambda: _nums(
                _early_bound(iview.ModelToViewTransform, "IMathTransform").ArrayData, 9
            )
        ),
        "viewport_pixel_m": _probe_attempt(
            lambda: _nums(_drawing_common.drawing_viewport_pixel_size(adapter), 9)
        ),
    }

    def _referenced_path() -> str:
        reference = iview.ReferencedDocument
        if reference is None or reference == "":
            return ""
        return str(_early_bound(reference, "IModelDoc2").GetPathName() or "")

    state["referenced_path"] = _probe_attempt(_referenced_path)
    for name, point_mm in _PROBE_MODEL_POINTS_MM.items():
        projected = _probe_attempt(
            lambda point_mm=point_mm: _drawing_common.model_point_in_view(
                adapter,
                view,
                tuple(value / 1000.0 for value in point_mm),
                label=f"{label} probe {name}",
            )
        )
        state[f"proj_{name}_m"] = (
            projected if isinstance(projected, str) else _nums(projected, 6)
        )
        if not isinstance(projected, str):
            state[f"proj_{name}_minus_expected_mm"] = [
                _num((projected[0] - expected_xy[0]) * 1000.0, 3),
                _num((projected[1] - expected_xy[1]) * 1000.0, 3),
            ]
    return state


def _probe_selection_state(adapter: Any) -> dict[str, Any]:
    manager = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
    count = _probe_attempt(lambda: int(manager.GetSelectedObjectCount2(-1)))
    state: dict[str, Any] = {"selected_count": count}
    if isinstance(count, int) and count > 0:
        state["selected_types"] = [
            _probe_attempt(lambda i=i: int(manager.GetSelectedObjectType3(i, -1)))
            for i in range(1, min(count, 8) + 1)
        ]
    return state


def _probe_edge_inventory(
    adapter: Any, view: Any, edges: Any, *, label: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in edges.edges[:_PROBE_MAX_EDGES]:
        row: dict[str, Any]
        points_mm: tuple[tuple[float, float, float], ...]
        if item.line is not None:
            start, end = item.line
            row = {"kind": "line", "start_mm": _nums(start, 4), "end_mm": _nums(end, 4)}
            points_mm = (start, end)
        elif item.circle is not None:
            cx, cy, cz, nx, ny, nz, radius = item.circle
            row = {
                "kind": "circle",
                "center_mm": _nums((cx, cy, cz), 4),
                "axis": _nums((nx, ny, nz), 6),
                "radius_mm": _num(radius, 4),
            }
            points_mm = ((cx, cy, cz),)
        else:
            row = {"kind": "other"}
            points_mm = ()
        row["sheet_m"] = [
            _probe_attempt(
                lambda point=point: _nums(
                    _drawing_common.model_point_in_view(
                        adapter,
                        view,
                        tuple(value / 1000.0 for value in point),
                        label=f"{label} probe edge",
                    ),
                    6,
                )
            )
            for point in points_mm
        ]
        rows.append(row)
    return rows


def _probe_minus_z_candidates(edges: Any) -> list[int]:
    """Indices of visible circles matching the -Z rim within circle_at's bounds."""
    matches = []
    for index, item in enumerate(edges.edges):
        if item.circle is None:
            continue
        cx, cy, cz, nx, ny, nz, radius = item.circle
        center_error = sum(abs(a - b) for a, b in zip((cx, cy, cz), _MINUS_Z_CENTER_MM))
        axis_error = 1.0 - abs(nx * 0.0 + ny * 0.0 + nz * 1.0)
        if (
            center_error <= _PROBE_CENTER_TOL_MM
            and abs(radius - _END_RADIUS_MM) <= _PROBE_RADIUS_TOL_MM
            and axis_error <= 1e-6
        ):
            matches.append(index)
    return matches


def _probe_source_roundtrip(adapter: Any, view: Any, edge: Any) -> dict[str, Any]:
    """Drawing edge -> source model edge -> drawing edge, as _native_axis_datum does."""
    app = adapter.swApp
    iview = _early_bound(view, "IView")
    result: dict[str, Any] = {
        "edge_self_same": _probe_attempt(lambda: int(app.IsSame(edge, edge))),
    }

    def _roundtrip() -> dict[str, Any]:
        reference = iview.ReferencedDocument
        if reference is None or reference == "":
            return {"canonical": "no referenced document"}
        model = _early_bound(reference, "IModelDoc2")
        extension = _early_bound(model.Extension, "IModelDocExtension")
        canonical = extension.GetCorrespondingEntity2(edge)
        if canonical is None:
            return {"canonical": "missing"}
        canonical_circle = _probe_attempt(
            lambda: _nums(
                _early_bound(
                    _early_bound(canonical, "IEdge").GetCurve(), "ICurve"
                ).CircleParams,
                6,
            )
        )
        back = iview.GetCorrespondingEntity(canonical)
        return {
            "canonical": "present",
            "canonical_circle_m": canonical_circle,
            "roundtrip": "missing" if back is None else "present",
            "roundtrip_same": None if back is None else int(app.IsSame(back, edge)),
        }

    outcome = _probe_attempt(_roundtrip)
    if isinstance(outcome, dict):
        result.update(outcome)
    else:
        result["roundtrip_error"] = outcome
    return result


@contextlib.contextmanager
def _selection_probe(adapter: Any) -> Iterator[None]:
    """Wrap `_drawing_common._select_view_entity` for one `project_part_pmi`."""
    original = _drawing_common._select_view_entity

    def probed(
        adapter: Any,
        view: Any,
        entity_type: str,
        xy: tuple[float, float] | None,
        *,
        label: str,
        entity: Any | None = None,
    ) -> Any:
        if xy is None or entity is not None:
            return original(adapter, view, entity_type, xy, label=label, entity=entity)
        _probe_record(
            "view_state_before_select",
            **_probe_view_state(adapter, view, expected_xy=xy, label=label),
        )
        try:
            # The exact production call: ActivateView, ClearSelection2,
            # UpdateViewDisplayGeometry, SelectByID2("", type, x, y).
            selected = original(adapter, view, entity_type, xy, label=label)
        except RuntimeError as exc:
            coordinate_error = exc
            selected = None
        else:
            coordinate_error = None
        _probe_record(
            "coordinate_select",
            label=label,
            entity_type=entity_type,
            xy_m=[_num(xy[0], 6), _num(xy[1], 6)],
            returned=coordinate_error is None,
            error="" if coordinate_error is None else str(coordinate_error),
            **_probe_selection_state(adapter),
        )
        if label != _PROBE_LABEL:
            if coordinate_error is not None:
                raise coordinate_error
            return selected

        # Failing label: what edges does the view ACTUALLY show, and which one
        # is the -Z rim?  Read before touching the selection again.
        edges = _drawing_common.scan_view_edges(view, label=f"{label} probe")
        candidates = _probe_minus_z_candidates(edges)
        _probe_record(
            "visible_edges",
            label=label,
            edge_count=len(edges.edges),
            line_count=len(edges.lines),
            circle_count=len(edges.circles),
            target_center_mm=_nums(_MINUS_Z_CENTER_MM, 4),
            target_radius_mm=_num(_END_RADIUS_MM, 4),
            minus_z_candidate_indices=candidates,
            edges=_probe_edge_inventory(adapter, view, edges, label=label),
        )
        app = adapter.swApp
        if coordinate_error is None:
            # Passed this time: say WHICH edge the coordinate pick landed on.
            _probe_record(
                "coordinate_select_identity",
                label=label,
                same_as_candidate=[
                    _probe_attempt(
                        lambda i=i: int(app.IsSame(selected, edges.edges[i].edge))
                    )
                    for i in candidates
                ],
            )
            return selected

        if len(candidates) != 1:
            raise RuntimeError(
                f"{coordinate_error}; probe found {len(candidates)} visible -Z rim "
                f"candidates (indices {candidates}) among {len(edges.edges)} edges "
                f"-- see {_PROBE_TAG} visible_edges"
            ) from coordinate_error
        # circle_at is the production semantic resolver; it must agree with the
        # uniqueness count above and fails loud with the nearest numbers if not.
        candidate = edges.circle_at(
            _MINUS_Z_CENTER_MM,
            _END_RADIUS_MM,
            axis=(0.0, 0.0, 1.0),
            label=f"{label} probe",
        )
        if candidate is not edges.edges[candidates[0]]:
            raise RuntimeError(
                f"{coordinate_error}; probe: circle_at resolved a different edge than "
                f"the unique candidate index {candidates[0]}"
            ) from coordinate_error
        _probe_record(
            "candidate_roundtrip",
            label=label,
            candidate_index=candidates[0],
            **_probe_source_roundtrip(adapter, view, candidate.edge),
        )
        # ONE explicit native selection through the existing entity path:
        # ActivateView, ClearSelection2, CreateSelectData, data.View = view,
        # IEntity.Select4(False, data), count must be exactly 1.
        try:
            explicit = original(
                adapter,
                view,
                "EDGE",
                None,
                label=f"{label} [probe entity path]",
                entity=candidate.edge,
            )
        except RuntimeError as exc:
            _probe_record(
                "entity_select",
                label=label,
                returned=False,
                error=str(exc),
                **_probe_selection_state(adapter),
            )
            raise RuntimeError(
                f"{coordinate_error}; probe: explicit IEntity.Select4 on the unique "
                f"-Z rim also failed: {exc}"
            ) from coordinate_error
        manager = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
        selected_type = int(manager.GetSelectedObjectType3(1, -1))
        same = int(app.IsSame(explicit, candidate.edge))
        _probe_record(
            "entity_select",
            label=label,
            returned=True,
            selected_type=selected_type,
            same_as_candidate=same,
            **_probe_selection_state(adapter),
        )
        if selected_type != _SEL_EDGES or same != _OBJECT_SAME:
            raise RuntimeError(
                f"{coordinate_error}; probe: explicit Select4 selected type "
                f"{selected_type} same={same}, expected EDGE/same"
            ) from coordinate_error
        _telemetry.warn(
            f"{_PROBE_TAG} DIAGNOSTIC-ONLY CONTINUATION: {label} coordinate pick at "
            f"({xy[0]:g}, {xy[1]:g}) returned False; continuing into InsertGtol on "
            f"the explicitly selected -Z rim edge to prove the entity path. "
            f"This drawing is probe output, not a release artefact."
        )
        return explicit

    _drawing_common._select_view_entity = probed
    try:
        yield
    finally:
        _drawing_common._select_view_entity = original


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-shaft source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    end_radius = SHAFT_DIA * END_VIEW_SCALE / 2000.0
    end_circle = (
        FRONT_CENTER[0] + end_radius,
        FRONT_CENTER[1],
    )
    left_end = (RIGHT_CENTER[0] - SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    end_top = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + SHAFT_DIA * END_VIEW_SCALE / 2000.0,
    )
    end_upper = (
        FRONT_CENTER[0] + end_radius * math.cos(math.radians(50.0)),
        FRONT_CENTER[1] + end_radius * math.sin(math.radians(50.0)),
    )
    # GD&T is model PMI (fulcrum_shaft_spec.PART_DATUMS/GEOMETRIC_CONTROLS,
    # authored by build_fulcrum_shaft) — project it and place it where the
    # hand-authored symbols used to sit (sheet-LEFT of the *Right view is the
    # model +Z end, so the +Z squareness frame takes the left-end spot). Which
    # VIEW receives each annotation depends on its attachment (a datum tag
    # only lands in a view aligned with its face), and the projection fails
    # loud on any mismatch.
    # PROBE (this branch only): every coordinate pick inside this call is
    # instrumented; the minus-Z pick falls through to ONE explicit Select4.
    with _selection_probe(adapter):
        project_part_pmi(
            adapter,
            placements={
                "datum:A": PmiDrawingPlacement(
                    view=front,
                    position=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024),
                    attachment_xy=end_top,
                ),
                "bearing_cylindricity": PmiDrawingPlacement(
                    view=front, position=(0.065, 0.250), attachment_xy=end_upper
                ),
                "plus_z_end_perpendicularity": PmiDrawingPlacement(
                    view=right,
                    position=(left_end[0] - 0.042, 0.180),
                    attachment_xy=left_end,
                ),
                "minus_z_end_perpendicularity": PmiDrawingPlacement(
                    view=right,
                    position=(right_end[0] + 0.014, 0.180),
                    attachment_xy=right_end,
                ),
            },
            datums=PART_DATUMS,
            controls=GEOMETRIC_CONTROLS,
            label="fulcrum shaft PMI",
        )
    # Up-RIGHT of the end circle, on the same side as the `end_circle` pick
    # (the circle's RIGHTMOST point), so the leader comes in from the right and
    # never crosses the circle.  Two constraints forced this side:
    #   * it used to sit at RIGHT_CENTER[0] and drag a 130 mm diagonal leader
    #     back to this circle; and
    #   * placing it up-LEFT instead only traded that for a leader that raked
    #     across the circle and landed on the datum A tag -- which rests ON the
    #     circle at ~(0.052..0.058, 0.211..0.218) and cannot be moved away.
    #     IAnnotation::SetPosition2 on a DATUM FEATURE symbol sets the "point
    #     where the leader hits the symbol", so a tag that attaches straight to
    #     its edge ignores the requested Y and sits against the geometry.
    # The symbol's ARM extends left of the anchor and its TEXT renders ABOVE the
    # arm and to the RIGHT (ASME Y14.36): ~x=0.072..0.111 / y=0.222..0.237,
    # which clears the side view (it tops out at y=0.208) and leaves the arm at
    # 0.072, right of the cylindricity frame's near-vertical leader above.
    add_surface_finish(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(0.075, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="fulcrum bearing finish",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)
    # The iso renders at 1:2 while the title block reads 1:1, so the pictorial
    # needs its own scale callout or the sheet misstates it. Placed at the same
    # offset from ISO_CENTER that cylinder-gear-shaft uses for its identical 1:2
    # iso (dx -0.030, dy -0.048), so the two sibling shafts read alike.
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.157)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
