"""Native carrier hole table: source/view/edge/tag/row identity, never typed XY.

#2151 owner Option B; owner review 2026-11-07 (rule 10): X/Y LOC run from the
plate's lower-left corner, where the left end meets the -Y edge, which an
edge finder picks up; never from a hole centre. The holes whose stacks
assume a station from A1 (B1, A2, B2, CL, CR, R1-R4: the spec's pin
intervals, station and riser-wall errors) keep that one relation at ±.005
in flagged NOTE 2 (coordinator ruling 2026-11-07, option (b)); NOTE 1 keeps
A2/B2's Y .964 ±.002 from the A1-B1 axis line. The generated HUB
coordinates remain untouched and are explicitly REF in the NOTE column:
TL-00 step 10 taps that ordinary #8-32 receiver in situ at the HUB DRO
setting and alone owns its location.

Creation and settled readback have separate operation-level tracing spans;
individual hole/row traversal stays inside those spans.
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
import _telemetry
import ch_rocker_arm_tl_oblique_carrier_spec as spec

TABLE_ANCHOR = (0.020, 0.175)
TABLE_WIDTHS = (0.012, 0.019, 0.019, 0.078, 0.065)
# Sheet metres relative to the actual projected hole centre. Keep the close
# A1/A2 and B1/B2 pairs on opposite sides of their respective rows.
TAG_OFFSETS = {
    "A1": (-.012, -.008), "B1": (.008, -.008),
    "A2": (-.012, .009), "B2": (.008, .009),
    "CL": (.006, -.010), "CR": (.009, .010),
    "R1": (-.008, .010), "R2": (.003, .010),
    "R3": (-.010, .009), "R4": (.005, .009),
    "L1": (.008, .003), "L2": (.008, -.005), "HUB": (.009, .009),
}
# _hole_spec pins each cut diameter to 3-decimal mm. The Hole Wizard cuts
# the exact inch drill: farm build 26bb read CL's #29 (.1360 in) as radius
# 1.7272 mm against the pinned 3.454 diameter. Size identifies a hole only
# within that pinned rounding (half a 3rd-decimal unit); centre and axis
# stay exact, and every hole still maps one-to-one.
PINNED_DIAMETER_TOLERANCE_M = 0.5e-6
_EXACT_M = 1e-8
# The table's origin: the plate's lower-left corner (carrier mm).
ORIGIN = (spec.OUTLINE_X[0], spec.OUTLINE_Y[0])
# NOTE 2's rows: every hole whose stack assumes one ±.005 station from A1
# (spec.table_coordinate_errors, pin_coordinate_intervals). The lever taps
# relate to the -Y edge only; the HUB is REF.
A1_RELATED = ("B1", "A2", "B2", "CL", "CR", "R1", "R2", "R3", "R4")
A1_RELATION_NOTE = (
    "B1, A2, B2, CL, CR, R1-R4: LOCATE FROM A1 IN X AND\n"
    "FROM THE A1-B1 AXIS LINE IN Y WITHIN \u00b1.005"
)
ORIGIN_NOTE = "X/Y LOC FROM THE LOWER-LEFT PLATE CORNER"
HUB_NOTE = "HUB LOCATION REF \u2014 TAP IN SITU AT TL-00 STEP 10"
# Each row's NOTE cell: the pass it sets or its function, and its flags.
ROW_NOTES = {
    "A1": "R800 / MHA-CH-13",
    "B1": "R800 / MHA-CH-13; NOTE 2",
    "A2": "R816 / MHA-CH-13; NOTES 1, 2",
    "B2": "R816 / MHA-CH-13; NOTES 1, 2",
    "CL": "END CLAMP; NOTE 2",
    "CR": "END CLAMP; NOTE 2",
    **{f"R{i}": "LOCATES TL-24 RISER; NOTE 2" for i in range(1, 5)},
    **{f"L{i}": "FEED LEVER; SEE CALLOUT" for i in range(1, 3)},
    "HUB": spec.TABLE_ROW_NOTES["HUB"],
}
if set(ROW_NOTES) != set(spec.TABLE_HOLES) or any(
    ("NOTE 2" in note or "NOTES 1, 2" in note) != (tag in A1_RELATED)
    for tag, note in ROW_NOTES.items()
):
    raise AssertionError("NOTE 2's rows, and only those, carry its flag")


def table_location(tag: str) -> tuple[float, float]:
    """A hole's X/Y LOC from the table's corner origin, carrier mm."""
    x, y, _diameter = spec.TABLE_HOLES[tag]
    return x - ORIGIN[0], y - ORIGIN[1]


def _hole_tag(values: tuple[float, ...]) -> str | None:
    """The one table hole whose exact centre/axis and pinned size fit ``values``."""
    matches = [
        tag for tag, (x, y, diameter) in spec.TABLE_HOLES.items()
        if max(abs(values[0] - x / 1000.0), abs(values[2] + y / 1000.0),
               abs(values[3]), abs(abs(values[4]) - 1.0), abs(values[5])) <= _EXACT_M
        and abs(2.0 * values[6] - diameter / 1000.0) <= PINNED_DIAMETER_TOLERANCE_M + 1e-12
    ]
    return matches[0] if len(matches) == 1 else None


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
            tag = _hole_tag(values)
            if tag is None or tag in found:
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
            found[tag] = _early_bound(raw, "IEdge")
    if set(found) != set(spec.TABLE_HOLES):
        raise RuntimeError(f"carrier table is missing physical holes: {set(spec.TABLE_HOLES) - set(found)}")
    return found


def _rows(table: Any) -> dict[str, tuple[int, tuple[str, ...]]]:
    """Exact generated tag/coordinate bijection, not a nearest-coordinate guess."""
    if int(table.RowCount) != len(spec.TABLE_HOLES) + 1 or int(table.ColumnCount) not in (4, 5):
        raise RuntimeError("carrier table has the wrong row/column inventory")
    rows = {}
    for row in range(1, int(table.RowCount)):
        cells = tuple(str(table.DisplayedText2(row, col, False) or "").strip()
                      for col in range(int(table.ColumnCount)))
        tag = cells[0]
        if tag not in spec.TABLE_HOLES or tag in rows:
            raise RuntimeError(f"carrier table has an extra/duplicate native tag: {tag!r}")
        for text, nominal in zip(cells[1:3], table_location(tag), strict=True):
            if not re.fullmatch(r"-?\d*\.\d{3}", text):
                raise RuntimeError(f"carrier table {tag} lost .XXX precision: {text!r}")
            if abs(float(text) - round(nominal / spec.trammel.INCH, spec.TABLE_LOCATION_PLACES)) > 1e-9:
                raise RuntimeError(f"carrier table {tag} is not measured from the corner: {cells!r}")
        if not cells[3]:
            raise RuntimeError(f"carrier table {tag} has no native SIZE")
        rows[tag] = (row, cells)
    if set(rows) != set(spec.TABLE_HOLES):
        raise RuntimeError("carrier table omitted a tagged hole")
    return rows


def _row_holes(table: Any) -> dict[int, str]:
    """Each generated row's physical hole, from its own native corner cells.

    The printed .XXX location pairs of the thirteen holes are distinct, so a
    row identifies exactly one hole or the table is refused.
    """
    if int(table.RowCount) != len(spec.TABLE_HOLES) + 1:
        raise RuntimeError("carrier table has the wrong row inventory")
    expected = {
        tag: tuple(round(value / spec.trammel.INCH, spec.TABLE_LOCATION_PLACES)
                   for value in table_location(tag))
        for tag in spec.TABLE_HOLES
    }
    if len(set(expected.values())) != len(expected):
        raise AssertionError("two carrier holes print the same table location")
    holes: dict[int, str] = {}
    for row in range(1, int(table.RowCount)):
        texts = tuple(str(table.DisplayedText2(row, col, False) or "").strip() for col in (1, 2))
        if not all(re.fullmatch(r"-?\d*\.\d{3}", text) for text in texts):
            raise RuntimeError(f"carrier table row {row} lost .XXX precision: {texts!r}")
        matches = [
            tag for tag, location in expected.items()
            if all(abs(float(text) - value) <= 1e-9 for text, value in zip(texts, location, strict=True))
        ]
        if len(matches) != 1 or matches[0] in holes.values():
            raise RuntimeError(
                f"carrier table row {row} is not exactly one hole from the corner: {texts!r}"
            )
        holes[row] = matches[0]
    return holes


def _hole_tag_reader(feature: Any, current: dict[int, str]) -> int:
    """Measured offset of IHoleTable.HoleTag's index from the table row index."""
    offsets = []
    for offset in (1, 0):
        try:
            if all(str(feature.HoleTag(row - offset) or "").strip() == tag
                   for row, tag in current.items()):
                offsets.append(offset)
        except Exception:  # an out-of-range probe index is simply not this convention
            continue
    if len(offsets) != 1:
        raise RuntimeError("carrier HoleTag does not read back the generated TAG cells")
    return offsets[0]


def _assign_tags(feature: Any, table: Any) -> None:
    """Rename SolidWorks' default A1..A13 tags to the owner tags, collision-free.

    InsertHoleTable3's manual tags are prefixes that SolidWorks numbers per
    prefix (farm 4d: "A1" printed as "A11"). The documented IHoleTable.HoleTag
    setter takes the exact tag but refuses a name another row still holds, and
    the defaults A1/A2 are also owner tags. Every row is therefore first moved
    to an unused temporary, then to its owner tag, each write read back.
    """
    holes = _row_holes(table)
    current = {row: str(table.DisplayedText2(row, 0, False) or "").strip() for row in holes}
    if len(set(current.values())) != len(current) or not all(current.values()):
        raise RuntimeError(f"carrier table generated duplicate or empty tags: {current!r}")
    offset = _hole_tag_reader(feature, current)
    temporary = {row: f"TMP{row}" for row in holes}
    if set(temporary.values()) & (set(current.values()) | set(spec.TABLE_HOLES)):
        raise AssertionError("carrier temporary tags collide with a live or owner tag")
    feature.EnableUpdate = False
    try:
        for names in (temporary, holes):
            for row, name in names.items():
                feature.SetHoleTag(row - offset, name)
                if str(feature.HoleTag(row - offset) or "").strip() != name:
                    raise RuntimeError(f"carrier hole tag {name!r} was not assigned to row {row}")
    finally:
        feature.EnableUpdate = True


def _tags(adapter: Any, view: Any, edges: dict[str, Any], *, place: bool) -> None:
    found = {}
    for raw in view.GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in edges:
            if re.fullmatch(r"(?:[A-Z]+\d+|HUB|CL|CR)", tag):
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


@_telemetry.traced("drawing.carrier_hole_table.create")
def create_carrier_hole_table(
    adapter: Any, view: Any, model: Any, source: Path,
) -> Callable[[], None]:
    view = _early_bound(view, "IView")
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    table_sheet = str(_early_bound(drawing.GetCurrentSheet(), "ISheet").GetName())
    model = _early_bound(model, "IModelDoc2")
    edges = _source_edges(adapter, view, model, source)
    _outer_row_source(model)
    # The origin is the plate's real lower-left corner vertex (rule 10: a
    # corner the shop picks up with an edge finder, never a hole centre). No
    # constructed datum point. Default alphanumeric tags, renamed below from
    # each row's own corner cells.
    order = sorted(spec.TABLE_HOLES, key=lambda tag: spec.TABLE_HOLES[tag][:2])
    table = insert_hole_table(
        adapter, view,
        datum_xy=_point(adapter, view, *ORIGIN),
        hole_points=[_point(adapter, view, x + diameter / 2.0, y)
                     for x, y, diameter in (spec.TABLE_HOLES[tag] for tag in order)],
        hole_entities=[edges[tag] for tag in order],
        anchor_xy=TABLE_ANCHOR, basic_locations=False, label="carrier corner baseline",
        unit=spec.UNIT, location_places=spec.TABLE_LOCATION_PLACES,
    )
    feature = _early_bound(_early_bound(table, "IHoleTableAnnotation").HoleTable, "IHoleTable")
    origin = _early_bound(feature.DatumOrigin, "IDatumOrigin")
    _assign_tags(feature, table)
    rebuild_drawing(adapter, label="carrier owner tags")
    rows = _rows(table)
    generated = {tag: cells[:4] for tag, (_row, cells) in rows.items()}
    if not table.InsertColumn2(3, 3, "NOTE", 0):  # swTableItemInsertPosition_After
        raise RuntimeError("carrier table refused the NOTE column")
    if not table.SetColumnTitle2(4, "NOTE", False):
        raise RuntimeError("carrier table refused the NOTE title")
    for tag, (row, _cells) in rows.items():
        if not table.IsCellTextEditable(row, 4):
            raise RuntimeError(f"carrier {tag} NOTE cell is not editable")
        table.SetText2(row, 4, False, ROW_NOTES[tag])
    for column, width in enumerate(TABLE_WIDTHS):
        actual = float(table.SetColumnWidth(column, width, 0))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(f"carrier table column {column} rejected its width")
    _tags(adapter, view, edges, place=True)
    # NOTE 1 is flagged in the A2/B2 rows; the exact owner text is linked to
    # the saved model property and checked against both native local controls.
    # NOTE 2 (A1_RELATION_NOTE) is flagged in its own rows.
    add_note(adapter, "1", .225, .163)
    flagged = add_property_linked_note(adapter, "Outer Pin Row Note", .235, .163)
    add_note(adapter, "2", .225, .153)
    add_note(adapter, A1_RELATION_NOTE, .235, .153)
    add_note(adapter, ORIGIN_NOTE, .225, .133)
    add_note(adapter, HUB_NOTE, .225, .123)
    rebuild_drawing(adapter, label="carrier table and tags")

    def check_active_table() -> None:
        current = _source_edges(adapter, view, model, source)
        _outer_row_source(model)
        rows_now = _rows(table)
        if (feature.CombineSameSize or feature.CombineTags
                or bool(feature.GetHoleLocationUseDocPrecision())
                or int(feature.GetHoleLocationPrecision()) != spec.TABLE_LOCATION_PLACES):
            raise RuntimeError("carrier table lost individual .XXX rows")
        # The rows' corner cells prove where the origin is; its mark stays
        # on the one corner vertex it was inserted on, not on a hole edge.
        annotation = _early_bound(origin.GetAnnotation(), "IAnnotation")
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (len(attached) != 1 or attached[0] is None
                or any(int(adapter.swApp.IsSame(attached[0], edge)) == 1
                       for edge in current.values())
                or annotation.IsDangling()):
            raise RuntimeError("carrier table datum left its corner vertex")
        for tag, (_row, cells) in rows_now.items():
            if cells[:4] != generated[tag] or cells[4] != ROW_NOTES[tag]:
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

    @_telemetry.traced("drawing.carrier_hole_table.settled")
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
