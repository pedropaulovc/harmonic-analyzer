"""Native carrier hole table: source/view/edge/tag/row identity, never typed XY.

#2151 owner Option B. The generated HUB coordinates remain untouched and are
explicitly REF in the NOTE column; TL-00 step 10 alone owns their acceptance.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable

from solidworks_mcp.adapters.solidworks.drawing import visible_component_entities

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_notes import add_note, add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_tables import insert_hole_table
import ch_rocker_arm_tl_oblique_carrier_spec as spec

TABLE_ANCHOR = (0.020, 0.175)
TABLE_WIDTHS = (0.012, 0.019, 0.019, 0.078, 0.065)
# Sheet metres relative to the actual projected hole centre. Keep the close
# A1/A2 and B1/B2 pairs on opposite sides of their respective rows.
TAG_OFFSETS = {
    "A1": (-.012, -.008), "B1": (.008, -.008),
    "A2": (-.012, .009), "B2": (.008, .009),
    "LEFT": (-.013, .012), "CL": (.006, -.010), "CR": (.009, .010),
    "R1": (-.008, .010), "R2": (.003, .010),
    "R3": (-.010, .009), "R4": (.005, .009),
    "L1": (.008, .003), "L2": (.008, -.005), "HUB": (.009, .009),
}


def _point(adapter: Any, view: Any, x: float, y: float) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, (x / 1000.0, 0.0, -y / 1000.0), label="carrier hole-table station"
    )


def _circle_parameters(edge: Any) -> tuple[float, ...] | None:
    curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
    if not curve.IsCircle():
        return None
    values = tuple(float(v) for v in curve.CircleParams)
    if len(values) != 7 or not all(math.isfinite(v) for v in values):
        raise RuntimeError("carrier table edge has invalid circle parameters")
    return values


def _source_edges(adapter: Any, view: Any, model: Any, source: Path) -> dict[str, Any]:
    """A bijection of ALL top-face holes to canonical source-body edges."""
    if (
        view.ReferencedDocument is None
        or int(adapter.swApp.IsSame(view.ReferencedDocument, model)) != 1
        or Path(str(model.GetPathName())).resolve() != source.resolve()
        or Path(str(view.GetReferencedModelName())).resolve() != source.resolve()
        or str(view.ReferencedConfiguration) != str(model.ConfigurationManager.ActiveConfiguration.Name)
        or int(model.GetType()) != 1
    ):
        raise RuntimeError("carrier table view lost its source part/configuration identity")
    for document in (model, adapter.currentModel):
        extension = _early_bound(document.Extension, "IModelDocExtension")
        if (int(extension.GetUserPreferenceInteger(47, 0)) != 3
                or int(extension.GetUserPreferenceInteger(48, 0)) != 1):
            raise RuntimeError("carrier table source/drawing is not decimal inches")
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("carrier table source does not have exactly one solid")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    found = {}
    for component in view.GetVisibleComponents() or ():
        for raw in visible_component_entities(view, component, 1) or ():
            values = _circle_parameters(raw)
            if values is None or abs(values[1]) > 1e-8:
                continue
            matches = [
                tag for tag, (x, y, diameter) in spec.TABLE_HOLES.items()
                if max(abs(values[0] - x / 1000.0), abs(values[2] + y / 1000.0),
                       abs(values[6] - diameter / 2000.0), abs(values[3]),
                       abs(abs(values[4]) - 1.0), abs(values[5])) <= 1e-8
            ]
            if len(matches) != 1 or matches[0] in found:
                raise RuntimeError(f"carrier table has extra/duplicate/unidentified top circle: {values}")
            canonical = extension.GetCorrespondingEntity2(raw)
            if canonical is None:
                raise RuntimeError("carrier table edge has no source counterpart")
            edge = _early_bound(canonical, "IEdge")
            roundtrip = view.GetCorrespondingEntity(edge)
            if (roundtrip is None or int(adapter.swApp.IsSame(roundtrip, raw)) != 1
                    or int(adapter.swApp.IsSame(edge.GetBody(), bodies[0])) != 1
                    or _circle_parameters(edge) != values):
                raise RuntimeError("carrier table source/view edge correspondence failed")
            found[matches[0]] = _early_bound(raw, "IEdge")
    if set(found) != set(spec.TABLE_HOLES):
        raise RuntimeError(f"carrier table is missing physical holes: {set(spec.TABLE_HOLES) - set(found)}")
    return found


def _rows(table: Any) -> dict[str, tuple[int, tuple[str, ...]]]:
    """Exact generated tag/coordinate bijection, not a nearest-coordinate guess."""
    if int(table.RowCount) != len(spec.TABLE_HOLES) + 1 or int(table.ColumnCount) not in (4, 5):
        raise RuntimeError("carrier table has the wrong row/column inventory")
    rows = {}
    a1x, a1y = spec.PIN_HOLES["A1"]
    for row in range(1, int(table.RowCount)):
        cells = tuple(str(table.DisplayedText2(row, col, False) or "").strip()
                      for col in range(int(table.ColumnCount)))
        tag = cells[0]
        if tag not in spec.TABLE_HOLES or tag in rows:
            raise RuntimeError(f"carrier table has an extra/duplicate native tag: {tag!r}")
        x, y, _diameter = spec.TABLE_HOLES[tag]
        for text, nominal in zip(cells[1:3], (x - a1x, y - a1y), strict=True):
            if not re.fullmatch(r"-?\d*\.\d{3}", text):
                raise RuntimeError(f"carrier table {tag} lost .XXX precision: {text!r}")
            if abs(float(text) - round(nominal / spec.trammel.INCH, spec.TABLE_LOCATION_PLACES)) > 1e-9:
                raise RuntimeError(f"carrier table {tag} is not measured from A1: {cells!r}")
        if not cells[3]:
            raise RuntimeError(f"carrier table {tag} has no native SIZE")
        rows[tag] = (row, cells)
    if set(rows) != set(spec.TABLE_HOLES):
        raise RuntimeError("carrier table omitted a tagged hole")
    return rows


def _tags(adapter: Any, view: Any, edges: dict[str, Any], *, place: bool) -> None:
    found = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in edges:
            if re.fullmatch(r"(?:[A-Z]+\d+|LEFT|HUB|CL|CR)", tag):
                raise RuntimeError(f"orphan native carrier hole tag: {tag}")
            continue
        if tag in found:
            raise RuntimeError(f"duplicate native carrier hole tag: {tag}")
        found[tag] = annotation
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (len(attached) != 1 or attached[0] is None
                or int(adapter.swApp.IsSame(attached[0], edges[tag])) != 1
                or annotation.IsDangling()):
            raise RuntimeError(f"carrier tag {tag} is not attached to its physical hole")
        x, y, _diameter = spec.TABLE_HOLES[tag]
        px, py = _point(adapter, view, x, y)
        dx, dy = TAG_OFFSETS[tag]
        if place:
            if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
                raise RuntimeError(f"carrier tag {tag} leader rejected")
            if not annotation.SetPosition2(px + dx, py + dy, 0.0):
                raise RuntimeError(f"carrier tag {tag} position rejected")
        if int(annotation.Visible) != 1 or int(annotation.GetLeaderCount()) != 1:
            raise RuntimeError(f"carrier tag {tag} is hidden or lacks one leader")
    if set(found) != set(edges):
        raise RuntimeError(f"carrier view is missing table tags: {set(edges) - set(found)}")


def _outer_row_source(model: Any) -> None:
    for name in ("A2DY", "B2DY"):
        raw = model.Parameter(f"{name}@PinHoleProfile")
        if raw is None:
            raise RuntimeError(f"carrier has no model-owned {name} control")
        dimension = _early_bound(raw, "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        nominal = float(dimension.SystemValue) * 1000.0
        actual = (nominal + float(tolerance.GetMinValue()) * 1000.0,
                  nominal + float(tolerance.GetMaxValue()) * 1000.0)
        expected = (spec.OUTER_Y_NOMINAL - spec.OUTER_Y_BAND,
                    spec.OUTER_Y_NOMINAL + spec.OUTER_Y_BAND)
        if (int(tolerance.Type) != 2 or abs(nominal - spec.A2_DY) > 1e-6
                or any(abs(a - b) > 1e-6 for a, b in zip(actual, expected, strict=True))):
            raise RuntimeError(f"carrier {name} does not own the flagged .964 ±.002 limits")


def create_carrier_hole_table(
    adapter: Any, view: Any, model: Any, source: Path,
) -> Callable[[], None]:
    view = _early_bound(view, "IView")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    table_sheet = str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
    model = _early_bound(model, "IModelDoc2")
    edges = _source_edges(adapter, view, model, source)
    _outer_row_source(model)
    # Insert against a real corner, then use the documented IDatumOrigin
    # reattachment to the actual A1 circular edge. No constructed datum point.
    order = sorted(spec.TABLE_HOLES, key=lambda tag: spec.TABLE_HOLES[tag][:2])
    table = insert_hole_table(
        adapter, view,
        datum_xy=_point(adapter, view, spec.OUTLINE_X[0], spec.OUTLINE_Y[0]),
        hole_points=[_point(adapter, view, x + diameter / 2.0, y)
                     for x, y, diameter in (spec.TABLE_HOLES[tag] for tag in order)],
        hole_entities=[edges[tag] for tag in order],
        anchor_xy=TABLE_ANCHOR, basic_locations=False, label="carrier A1 baseline",
        unit=spec.UNIT, location_places=spec.TABLE_LOCATION_PLACES, manual_tags=order,
    )
    feature = _early_bound(_early_bound(table, "IHoleTableAnnotation").HoleTable, "IHoleTable")
    origin = _early_bound(feature.DatumOrigin, "IDatumOrigin")
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = _early_bound(manager.CreateSelectData(), "ISelectData")
    data.View = view
    if not _early_bound(edges["A1"], "IEntity").Select4(False, data) or not origin.Reattach():
        raise RuntimeError("carrier hole-table origin could not attach to the actual A1 axis")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="carrier A1 table datum")
    rows = _rows(table)
    generated = {tag: cells[:4] for tag, (_row, cells) in rows.items()}
    if not table.InsertColumn2(3, 3, "NOTE", 0):  # swTableItemInsertPosition_After
        raise RuntimeError("carrier table refused the NOTE column")
    if not table.SetColumnTitle2(4, "NOTE", False):
        raise RuntimeError("carrier table refused the NOTE title")
    for tag, (row, _cells) in rows.items():
        if not table.IsCellTextEditable(row, 4):
            raise RuntimeError(f"carrier {tag} NOTE cell is not editable")
        table.SetText2(row, 4, False, spec.TABLE_ROW_NOTES[tag])
    for column, width in enumerate(TABLE_WIDTHS):
        actual = float(table.SetColumnWidth(column, width, 0))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(f"carrier table column {column} rejected its width")
    _tags(adapter, view, edges, place=True)
    # NOTE 1 is flagged in the A2/B2 rows; the exact owner text is linked to
    # the saved model property and checked against both native local controls.
    add_note(adapter, "1", .225, .163)
    flagged = add_property_linked_note(adapter, "Outer Pin Row Note", .235, .163)
    add_note(adapter, "HOLE LOCATIONS FROM A1; +X ALONG A1-B1", .225, .143)
    add_note(adapter, "HUB LOCATIONS REF — FINISH AT TL-00 STEP 10", .225, .128)
    rebuild_drawing(adapter, label="carrier table and tags")

    def check_active_table() -> None:
        current = _source_edges(adapter, view, model, source)
        _outer_row_source(model)
        rows_now = _rows(table)
        if (feature.CombineSameSize or feature.CombineTags
                or bool(feature.GetHoleLocationUseDocPrecision())
                or int(feature.GetHoleLocationPrecision()) != spec.TABLE_LOCATION_PLACES):
            raise RuntimeError("carrier table lost individual .XXX rows")
        annotation = _early_bound(origin.GetAnnotation(), "IAnnotation")
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (len(attached) != 1 or attached[0] is None
                or int(adapter.swApp.IsSame(attached[0], current["A1"])) != 1
                or annotation.IsDangling()):
            raise RuntimeError("carrier table datum no longer owns A1's actual axis")
        for tag, (_row, cells) in rows_now.items():
            if cells[:4] != generated[tag] or cells[4] != spec.TABLE_ROW_NOTES[tag]:
                raise RuntimeError(f"carrier generated row or flag changed: {tag}")
        _tags(adapter, view, current, place=False)
        if str(_early_bound(flagged, "INote").GetText()).strip() != spec.OUTER_Y_NOTE:
            raise RuntimeError("carrier flagged note differs from its model-owned limits")
        height = sum(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
        width = sum(float(table.GetColumnWidth(col)) for col in range(int(table.ColumnCount)))
        if TABLE_ANCHOR[1] - height < .015 or TABLE_ANCHOR[0] + width > .216:
            raise RuntimeError("carrier table crosses the border or title-block lane")
        native_tables = tuple(view.GetTableAnnotations() or ())
        if len(native_tables) != 1 or int(adapter.swApp.IsSame(native_tables[0], table)) != 1:
            raise RuntimeError("carrier tagged view does not own exactly this one native table")

    def settled() -> None:
        previous = str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
        if not drawing.ActivateSheet(table_sheet):
            raise RuntimeError("carrier table sheet cannot be activated for final readback")
        try:
            check_active_table()
        finally:
            if not drawing.ActivateSheet(previous):
                raise RuntimeError("carrier table readback could not restore the active sheet")

    settled()
    return settled
