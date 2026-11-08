"""Native carrier hole table: source/view/edge/tag/row identity, never typed XY.

Every physical top-face hole is tagged and tabled, the in-situ HUB tap
included (machinist review r8: an untagged hole on the tagged view read as
unexplained). TL-00 step 10 drills and taps that ordinary #8-32 receiver at
assembly, so its row's X/Y are REF and its NOTE says so and points at the
HUB CLAMP sheet, whose parenthesized references from A1 are the same
source position. Every hole is identified against the source body. The
generated SIZE column is hidden (its stacked REAM band prints at the
document's two places); each tag's size and process is written into its own
NOTE cell instead (machinist review r7, rules 9 and 10: the size once per
tag group in the table, never deferred to a callout sheet), with the mate it
serves (r8, rule 10: one column naming the mate).

Owner review 2026-11-07 (rule 10): X/Y LOC run from the plate's lower-left
corner, where the left end meets the -Y edge, which an edge finder picks up;
never from a hole centre. The holes whose stacks assume a station from A1
(B1, A2, B2, CL, CR, R1-R4: the spec's pin intervals, station and riser-wall
errors) keep that one relation at ±.005 in flagged NOTE 2 (coordinator
ruling 2026-11-07, option (b)); NOTE 1 keeps A2/B2's Y .964 ±.002 from the
A1-B1 axis line.

Creation and settled readback have separate operation-level tracing spans;
individual hole/row traversal stays inside those spans.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from solidworks_mcp.adapters.solidworks.drawing import visible_component_entities
from solidworks_mcp.adapters.sw_type_info import constant

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_notes import add_note, add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_tables import insert_hole_table
import _config
import _telemetry
import ch_rocker_arm_tl_oblique_carrier_spec as spec
from ch_rocker_arm_tl_oblique_callouts import CALLOUT_PLACES

# The corner datum's X arrow stands ~15 mm under the plate's bottom edge
# (old-base farm r3, 20261108T014606685Z: it ran through the first row at a
# top 11 mm under it), so the table's top sits ~5 mm under the arrow. Both
# rise with the HOLE TABLE view (draw_..._carrier TABLE_VIEW_CENTER, r8):
# thirteen ~11 mm rows (the hidden two-row SIZE cells set the row height,
# farm 20261108T055431582Z) and the header run ~147 mm, which a .158 top
# would have put through the .015 floor.
TABLE_ANCHOR = (0.020, 0.173)
# NOTE at 150 (TAG/X/Y narrowed to 11/17/17 mm: "19.395" prints ~14 mm):
# the render prints ~2.41 mm a glyph (farm 20261108T055431582Z: the 34-glyph
# pin row ran 82 mm), so NOTE_MAX_GLYPHS lines need ~140 mm. Right edge
# 20 + 195 = 215 mm, inside the title block's lane at 216.
TABLE_WIDTHS = (0.011, 0.017, 0.017, 0.078, 0.150)
# The longest NOTE line, in printed glyphs (each <MOD-DIAM> prints one).
NOTE_MAX_GLYPHS = 58
# The physical columns, in the IncludeHidden=True index domain every read
# and write below uses: SIZE stays generated (and compared) while hidden.
COLUMNS = ("TAG", "X LOC", "Y LOC", "SIZE", "NOTE")
SIZE_COLUMN = COLUMNS.index("SIZE")
TABLED_HOLES = dict(spec.TABLE_HOLES)
# Sheet metres relative to the actual projected hole centre. Keep the close
# A1/A2 and B1/B2 pairs on opposite sides of their respective rows; A2's tag
# sits up-right, off the datum's Y axis label (82129 review read it "AY2").
# The HUB's sits down-right, clear of R1's and R2's above.
TAG_OFFSETS = {
    "A1": (-.012, -.008), "B1": (.008, -.008),
    "A2": (.007, .009), "B2": (.008, .009),
    "CL": (.006, -.010), "CR": (.009, .010),
    "R1": (-.008, .010), "R2": (.003, .010),
    "R3": (-.010, .009), "R4": (.005, .009),
    "L1": (.008, .003), "L2": (.008, -.005),
    "HUB": (.007, -.009),
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
# relate to the -Y edge only; the HUB's X/Y are REF.
A1_RELATED = ("B1", "A2", "B2", "CL", "CR", "R1", "R2", "R3", "R4")
A1_RELATION_NOTE = (
    "B1, A2, B2, CL, CR, R1-R4: LOCATE FROM A1 IN X AND\n"
    "FROM THE A1-B1 AXIS LINE IN Y WITHIN \u00b1.005"
)
ORIGIN_NOTE = "X/Y LOC FROM THE LOWER-LEFT PLATE CORNER"


def _tap_size(drill: float, thread: str) -> str:
    """A tap row's size as its sheet-1 callout prints it: the tap drill at
    the callout's places, then the thread, both through."""
    return (
        f"<MOD-DIAM>{spec.inch_text(drill, CALLOUT_PLACES)} THRU, "
        f"{thread.lstrip('#')} UNC THRU"
    )


# Each tag's size and process (rules 9, 10): the reamed pins at their limits
# in ASME Y14.5's single-line limit form, low limit first (the sheet-1 4X
# REAM's .3750 +.0015/+.0010), the taps as drill and thread.
PIN_SIZE = (
    f"<MOD-DIAM>{spec.inch_text(spec.PIN_HOLE_DIA + min(spec.PIN_HOLE_BAND), 4)}-"
    f"{spec.inch_text(spec.PIN_HOLE_DIA + max(spec.PIN_HOLE_BAND), 4)} REAM THRU"
)
ROW_SIZES = {
    **dict.fromkeys(spec.PIN_HOLES, PIN_SIZE),
    **dict.fromkeys(spec.END_CLAMPS, _tap_size(spec.CLAMP_TAP_DRILL, spec.CLAMP_THREAD)),
    **{f"R{i}": _tap_size(spec.RISER_TAP_DRILL, spec.RISER_THREAD) for i in range(1, 5)},
    **{f"L{i}": _tap_size(spec.LEVER_TAP_DRILL, spec.LEVER_THREAD) for i in range(1, 3)},
    "HUB": _tap_size(spec.CLAMP_TAP_DRILL, spec.HUB_THREAD),
}
# Each row's flagged notes: NOTE 1 on A2/B2, NOTE 2 on A1_RELATED.
ROW_FLAGS = {
    tag: tuple(
        number for number, tags in ((1, ("A2", "B2")), (2, A1_RELATED)) if tag in tags
    )
    for tag in TABLED_HOLES
}
# Each tag group's mate, once in the table (machinist review r8, rule 10),
# MHA-CH-06's own parts by their same-parent short TL- form.
_PARENT_PREFIX = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"].rsplit(
    "TL-", 1
)[0]


def _short(number: str) -> str:
    return number.removeprefix(_PARENT_PREFIX)


FEED_LEVER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-feed-lever")["number"]
ROW_MATES = {
    **dict.fromkeys(spec.PIN_HOLES, f"{_short(spec.PIN_NUMBER)} RUNNING FIT"),
    **dict.fromkeys(spec.END_CLAMPS, f"CLAMPS {spec.STRAP_NUMBER}"),
    **{f"R{i}": f"HOLDS {_short(spec.RISER_NUMBER)}" for i in range(1, 5)},
    **{f"L{i}": f"HOLDS {_short(FEED_LEVER_NUMBER)}" for i in range(1, 3)},
    "HUB": f"CLAMPS {spec.STRAP_NUMBER} HUB",
}
# The HUB is drilled and tapped at assembly (TL-00 step 10, its HUB CLAMP
# sheet callout): its row's X/Y are REF, said on a second line (one line
# would run ~70 glyphs). TABLE_ANCHOR's floor budget leaves ~10 mm should
# that row grow.
ROW_EXTRA = {"HUB": "DRILL AND TAP AT ASSEMBLY, SHEET 3; LOC REF"}


def _flags(numbers: tuple[int, ...]) -> str:
    if not numbers:
        return ""
    label = "NOTE" if len(numbers) == 1 else "NOTES"
    return f"; {label} {', '.join(map(str, numbers))}"


ROW_NOTES = {
    tag: "\n".join(
        (f"{ROW_SIZES[tag]}; {ROW_MATES[tag]}{_flags(ROW_FLAGS[tag])}",
         *((ROW_EXTRA[tag],) if tag in ROW_EXTRA else ()))
    )
    for tag in TABLED_HOLES
}
if set(ROW_SIZES) != set(TABLED_HOLES) or set(ROW_MATES) != set(TABLED_HOLES) or any(
    len(line.replace("<MOD-DIAM>", "\u00d8")) > NOTE_MAX_GLYPHS
    for note in ROW_NOTES.values()
    for line in note.splitlines()
):
    raise AssertionError("every tabled row needs a size and mate that fit the NOTE column")
# SolidWorks may read the diameter code back as its glyph (the riser's
# native SIZE cells: draw_ch_rocker_arm_tl_oblique_riser), and a cell's
# line break as CR LF.
_DIAMETER = re.compile("\u2300|\u00d8")


def _note_text(text: str) -> str:
    """A NOTE cell's text with the diameter glyph in its code form and its
    line breaks as LF."""
    return _DIAMETER.sub("<MOD-DIAM>", text.replace("\r\n", "\n"))


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


def _cell(table: Any, row: int, column: int) -> str:
    """One generated cell in the physical (IncludeHidden=True) domain."""
    return str(table.DisplayedText2(row, column, True) or "").strip()


def _inventory(table: Any) -> tuple[int, int]:
    """Physical rows/columns, hidden SIZE included (Total*Count)."""
    return int(table.TotalRowCount), int(table.TotalColumnCount)


def _rows(table: Any) -> dict[str, tuple[int, tuple[str, ...]]]:
    """Exact generated tag/coordinate bijection, not a nearest-coordinate guess."""
    rows_total, columns = _inventory(table)
    if rows_total != len(TABLED_HOLES) + 1 or columns not in (4, 5):
        raise RuntimeError("carrier table has the wrong row/column inventory")
    rows = {}
    expected = _location_expected()
    for row in range(1, rows_total):
        cells = tuple(_cell(table, row, col) for col in range(columns))
        tag = cells[0]
        if tag not in TABLED_HOLES or tag in rows:
            raise RuntimeError(f"carrier table has an extra/duplicate native tag: {tag!r}")
        values = tuple(map(_location_value, cells[1:3]))
        if values != expected[tag]:
            raise RuntimeError(f"carrier table {tag} is not measured from the corner: {cells!r}")
        _location_display(tag, cells[1:3])
        _size_semantics(tag, cells[SIZE_COLUMN])
        rows[tag] = (row, cells)
    if set(rows) != set(TABLED_HOLES):
        raise RuntimeError("carrier table omitted a tagged hole")
    return rows


_LOCATION = re.compile(r"-?(?:\d+\.?\d*|\.\d+)")


def _location_value(text: str) -> Decimal:
    """The exact printed number of a generated location cell.

    SolidWorks redisplays ``.000`` as ``0.000`` after a column insert (farm
    957501d1, then the reverse in a7547069). Leading/trailing zeros and the
    zero sign (``.120``/``0.12``/``-0.000``) are display format, not data:
    the .XXX format is set and read back natively (``_hole_table_format``,
    ``IHoleTable.SetHoleLocationPrecision``), and the cells are compared by
    value, so a rounding that changes the value (``.123`` -> ``.12``) fails.
    """
    if not _LOCATION.fullmatch(text):
        raise RuntimeError(f"carrier table location is not a number: {text!r}")
    return Decimal(text)


def _location_expected() -> dict[str, tuple[Decimal, Decimal]]:
    """Each tabled tag's source X/Y from the corner, at the table's .XXX places, by value."""
    return {
        tag: tuple(Decimal(repr(round(value / spec.trammel.INCH, spec.TABLE_LOCATION_PLACES)))
                   for value in table_location(tag))
        for tag in TABLED_HOLES
    }


def _location_display(tag: str, texts: tuple[str, ...]) -> None:
    """Log (never refuse) a value-correct location not printed as .XXX."""
    if not all(re.fullmatch(r"-?\d*\.\d{3}", text) for text in texts):
        _telemetry.info(f"carrier table {tag} location display {tuple(texts)!r} is not .XXX (value-equal)")


_SIZE_TOKENS = re.compile(r"<[^<>]*>|[+-]?\d*\.\d+|\S")
_STACKS = re.compile(r"(?:\s*<STACK\b[^<>]*>.*?</STACK>)+", re.IGNORECASE | re.DOTALL)
_STACK = re.compile(r"<STACK\b[^<>]*>(.*?)<OVER>(.*?)</STACK>", re.IGNORECASE | re.DOTALL)
_NUMBER = re.compile(r"[+-]?\d*\.\d+")


def _value(token: str) -> Any:
    """A printed number as its exact Decimal value (``.38 == 0.38 == .380``);
    anything else as text. Printed places are the format preferences' job."""
    return Decimal(token) if _NUMBER.fullmatch(token) else token


def _tolerance(block: str) -> tuple[Any, ...]:
    """One run of adjacent ``<STACK>`` cells as its (upper, lower) printed
    values. SolidWorks splits a band across stacks of signs and of values
    (``+/+`` then ``.00/.00``) or keeps one (``+ .00/- .00``): the tops and
    the bottoms concatenate in order, and the stack attributes are layout.
    A band whose two values are both zero is no band: ``()``, as plain SIZE.
    A stack of another shape is kept whole (whitespace aside) as data.
    """
    pairs = _STACK.findall(block)
    if len(pairs) != len(re.findall(r"<STACK\b", block, re.IGNORECASE)):
        return (("STACK", "".join(block.split())),)
    band = tuple(_value("".join("".join(pair[i].split()) for pair in pairs)) for i in (0, 1))
    if all(isinstance(value, Decimal) and value == 0 for value in band):
        return ()
    return (("TOL", *band),)


def _size_semantics(tag: str, text: str) -> tuple[Any, ...]:
    """A generated SIZE cell as SolidWorks symbol tokens, characters, each
    number's exact Decimal value and each tolerance band's printed (upper,
    lower); whitespace, leading/trailing zeros and stack layout are
    formatting, not data (the format itself is set and read back by
    ``_hole_table_format``).

    Farm a7547069 printed the pin rows' REAM band at the document's two
    places as ``+.00/+.00`` stacks, then ``+ .00/- .00`` after the NOTE
    column; 957501d1 printed the same rows plain. An all-zero band equals the
    plain size; a nonzero band is kept, so any changed value still differs.
    """
    if not text:
        raise RuntimeError(f"carrier table {tag} has no native SIZE")
    tokens: list[Any] = []
    at = 0
    for match in _STACKS.finditer(text):
        tokens += [_value(token) for token in _SIZE_TOKENS.findall(text[at:match.start()])]
        tokens += _tolerance(match.group())
        at = match.end()
    tokens += [_value(token) for token in _SIZE_TOKENS.findall(text[at:])]
    return tuple(tokens)


def _frozen_rows(
    table: Any, generated: dict[str, tuple[str, ...]], *,
    notes: dict[str, str] | None, stage: str,
) -> dict[str, tuple[int, tuple[str, ...]]]:
    """TAG/X/Y/SIZE as first generated, plus the NOTE column, by tag.

    ``notes=None`` requires the freshly inserted NOTE cells to be empty. The
    row's identity is its tag at its exact corner location (``_rows``); X/Y
    compare by printed decimal value and SIZE by ``_size_semantics``, never
    by serialization. TAG/NOTE compare byte for byte. Failures name the row,
    expected and actual cells.
    """
    rows = _rows(table)
    columns = _inventory(table)[1]
    if columns != len(COLUMNS):
        raise RuntimeError(f"carrier table has {columns} columns {stage}; expected TAG/X/Y/SIZE/NOTE")
    for tag, (row, cells) in rows.items():
        expected = (*generated[tag], "" if notes is None else notes[tag])
        if (cells[0], *map(_location_value, cells[1:3]), _size_semantics(tag, cells[3]),
                _note_text(cells[4])) != (
                expected[0], *map(_location_value, expected[1:3]),
                _size_semantics(tag, expected[3]), _note_text(expected[4])):
            raise RuntimeError(
                f"carrier generated row or flag changed {stage}: {tag} (row {row}) "
                f"expected={expected!r} actual={cells!r}"
            )
    return rows


def _row_holes(table: Any) -> dict[int, str]:
    """Each generated row's physical hole, from its own native corner cells.

    The .XXX source location pairs of the thirteen tabled holes are distinct,
    so a row's printed values identify exactly one hole or the table is refused.
    """
    rows_total = _inventory(table)[0]
    if rows_total != len(TABLED_HOLES) + 1:
        raise RuntimeError("carrier table has the wrong row inventory")
    expected = _location_expected()
    if len(set(expected.values())) != len(expected):
        raise AssertionError("two carrier holes print the same table location")
    holes: dict[int, str] = {}
    for row in range(1, rows_total):
        texts = tuple(_cell(table, row, col) for col in (1, 2))
        values = tuple(map(_location_value, texts))
        matches = [tag for tag, location in expected.items() if location == values]
        if len(matches) != 1 or matches[0] in holes.values():
            raise RuntimeError(
                f"carrier table row {row} is not exactly one hole from the corner: {texts!r}"
            )
        _location_display(matches[0], texts)
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
    """Rename SolidWorks' default A1..A12 tags to the owner tags, collision-free.

    InsertHoleTable3's manual tags are prefixes that SolidWorks numbers per
    prefix (farm 4d: "A1" printed as "A11"). The documented IHoleTable.HoleTag
    setter takes the exact tag but refuses a name another row still holds, and
    the defaults A1/A2 are also owner tags. Every row is therefore first moved
    to an unused temporary, then to its owner tag, each write read back.
    """
    holes = _row_holes(table)
    current = {row: _cell(table, row, 0) for row in holes}
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


@_telemetry.traced("drawing.carrier_hole_table.ownership")
def _owned_table(adapter: Any, view: Any, feature: Any, table: Any) -> None:
    """The tagged view's one HoleTableFeat is this table, the sheet's only one.

    Ownership follows the API example "Get and Set Table Anchor of Hole
    Table": ``FeatureByName(view.Name).GetFirstSubFeature`` walks the model
    view's sub-features to ``GetTypeName2 = "HoleTableFeat"``, whose
    ``IHoleTable.GetTableAnnotations`` are its annotations. Table enumeration
    instead scans the current sheet from ``IDrawingDoc.GetFirstView`` (the
    sheet/root view) through every ``GetNextView``, so a table listed by the
    root rather than the source view (farm bf1c82f4) is found, and any other
    hole table on the sheet is refused. Identity is ``ISldWorks.IsSame``,
    whose documented states are 1 same, 0 not same, -1 undetermined
    (example "Compare Selected Objects..."); only 1 matches, never proxy
    ``==``. Failures print the actual names and IsSame states.
    """
    app = adapter.swApp
    view = _early_bound(view, "IView")
    feature = _early_bound(feature, "IHoleTable")
    table = _early_bound(table, "ITableAnnotation")
    expected = _early_bound(table.GetAnnotation(), "IAnnotation")
    view_name = str(view.GetName2())
    # FeatureByName is declared on IDrawingDoc for drawings, not IModelDoc2
    # (farm 114c1622); GetFirstView is IDrawingDoc too.
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    view_feature = drawing.FeatureByName(view_name)
    hole_features = []
    sub = None if view_feature is None else _early_bound(view_feature, "IFeature").GetFirstSubFeature()
    while sub is not None:
        sub = _early_bound(sub, "IFeature")
        if str(sub.GetTypeName2()) == "HoleTableFeat":
            hole_features.append(sub)
        sub = sub.GetNextSubFeature()
    feature_same = [(str(item.Name), int(app.IsSame(item, feature.GetFeature()))) for item in hole_features]
    own = [_early_bound(_early_bound(raw, "ITableAnnotation").GetAnnotation(), "IAnnotation")
           for raw in feature.GetTableAnnotations() or ()]
    own_same = [(str(item.GetName()), int(app.IsSame(item, expected))) for item in own]
    sheet_views, listed = [], []
    # GetFirstView is the sheet (root) view; GetNextView walks its model views.
    current, index = drawing.GetFirstView(), 0
    while current is not None:
        current = _early_bound(current, "IView")
        name = str(current.GetName2())
        if index:
            sheet_views.append((name, int(app.IsSame(current, view))))
        for raw in current.GetTableAnnotations() or ():
            native = _early_bound(raw, "ITableAnnotation")
            if int(native.Type) == 1:  # swTableAnnotation_HoleChart
                annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
                listed.append((name, str(annotation.GetName()), int(app.IsSame(annotation, expected))))
        current, index = current.GetNextView(), index + 1
    if ([same for _name, same in feature_same] != [1] or [same for _name, same in own_same] != [1]
            or [same for _name, same in sheet_views].count(1) != 1
            or not listed or any(same != 1 for _view, _name, same in listed)):
        raise RuntimeError(
            f"carrier tagged view does not own exactly this one native table: view={view_name!r} "
            f"expected={str(expected.GetName())!r} HoleTableFeat={feature_same} "
            f"feature_annotations={own_same} sheet_views={sheet_views} sheet_hole_tables={listed}"
        )


# Document Properties > Tables > Hole (DP_Tables-Hole.md), drawing-document
# scope only, set before the table exists: new tables take these defaults.
# One serialization for every read (farm 957501d1 and a7547069 printed
# '.000' and '0.000' in opposite order across the NOTE-column rebuild):
# no leading zero (ASME inch, as draw_fr_rocker_arm_support), trailing zeros
# shown so .XXX keeps three places, no dual display.
HOLE_TABLE_FORMAT = (
    ("Integer", "swDetailingLeadingZero", "swDetailingHoleTable", "swLeadingZero_DoNotShow"),
    ("Integer", "swDetailingDimTrailingZero", "swDetailingHoleTable", "swDimShowTrailingZeroes"),
    ("Toggle", "swTableHoleDualDimensionDisplay", "swDetailingNoOptionSpecified", False),
)


def _hole_table_format(adapter: Any) -> None:
    """Set and read back HOLE_TABLE_FORMAT on the active drawing document."""
    extension = _early_bound(_early_bound(adapter.currentModel, "IModelDoc2").Extension, "IModelDocExtension")
    for kind, preference, option, value in HOLE_TABLE_FORMAT:
        wanted = value if isinstance(value, bool) else constant(value)
        name, scope = constant(preference), constant(option)
        set_ok = getattr(extension, f"SetUserPreference{kind}")(name, scope, wanted)
        actual = getattr(extension, f"GetUserPreference{kind}")(name, scope)
        actual = bool(actual) if kind == "Toggle" else int(actual)
        # SetUserPreferenceToggle returns the resulting state, not success.
        if (kind == "Integer" and not set_ok) or actual != wanted:
            raise RuntimeError(
                f"carrier hole-table {preference}@{option} did not take: "
                f"expected={value!r} ({wanted!r}) actual={actual!r}"
            )
    # Recorded, not set: an auto-updating table could re-add an unselected
    # hole on a model change (DP_Tables-Hole.md); _rows/_tags refuse an extra row.
    automatic = extension.GetUserPreferenceToggle(
        constant("swHoleTableAutomaticUpdate"), constant("swDetailingNoOptionSpecified")
    )
    _telemetry.info(f"carrier hole-table automatic update={automatic!r}")


def _size_column_hidden(table: Any, stage: str) -> None:
    """Exactly the generated SIZE column is hidden; every row and every other
    physical column shows. ``ColumnHidden``/``RowHidden`` must be BOOL."""
    rows_total, columns = _inventory(table)
    header = tuple(_cell(table, 0, column).upper() for column in range(columns))
    hidden = tuple(table.ColumnHidden(column) for column in range(columns))
    rows_hidden = tuple(table.RowHidden(row) for row in range(rows_total))
    if (header != COLUMNS
            or any(type(state) is not bool for state in (*hidden, *rows_hidden))
            or hidden != tuple(column == SIZE_COLUMN for column in range(columns))
            or any(rows_hidden)):
        raise RuntimeError(
            f"carrier table visibility {stage} is not SIZE-only hidden: header={header!r} "
            f"columns_hidden={hidden!r} rows_hidden={rows_hidden!r}"
        )


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
    _hole_table_format(adapter)
    # The origin is the plate's real lower-left corner vertex (rule 10: a
    # corner the shop picks up with an edge finder, never a hole centre). No
    # constructed datum point. Default alphanumeric tags, renamed below from
    # each row's own corner cells.
    # Every physical hole is selected, the in-situ HUB included (r8): the
    # native table holds all thirteen that _source_edges maps.
    order = sorted(TABLED_HOLES, key=lambda tag: TABLED_HOLES[tag][:2])
    table = insert_hole_table(
        adapter, view,
        datum_xy=_point(adapter, view, *ORIGIN),
        hole_points=[_point(adapter, view, x + diameter / 2.0, y)
                     for x, y, diameter in (TABLED_HOLES[tag] for tag in order)],
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
    # The native SIZE readback, raw and semantic, for the record: a zero
    # band stack is accepted as the plain size (a7547069 printed one on the
    # pin rows). The column is hidden below; its data is still compared.
    stacked = {tag: cells[3] for tag, cells in generated.items() if "<STACK" in cells[3].upper()}
    _telemetry.info(
        f"carrier hole-table SIZE readback: {len(stacked)} row(s) with a tolerance stack "
        f"{ {tag: (text, _size_semantics(tag, text)) for tag, text in stacked.items()}!r}"
    )
    if not table.InsertColumn2(3, 3, "NOTE", 0):  # swTableItemInsertPosition_After
        raise RuntimeError("carrier table refused the NOTE column")
    if not table.SetColumnTitle2(4, "NOTE", False):
        raise RuntimeError("carrier table refused the NOTE title")
    rebuild_drawing(adapter, label="carrier NOTE column")
    # Re-identify rows after the structural edit: a regenerated hole table may
    # reorder them, so NOTE text is written by each tag's CURRENT row only.
    rows = _frozen_rows(table, generated, notes=None, stage="after the NOTE column")
    for tag, (row, _cells) in rows.items():
        if not table.IsCellTextEditable(row, 4):
            raise RuntimeError(f"carrier {tag} NOTE cell (row {row}) is not editable")
        note = ROW_NOTES[tag]
        table.SetText2(row, 4, True, note)  # void put: read back below
        written = (str(table.Text2(row, 4, True) or ""), _cell(table, row, 4))
        if tuple(map(_note_text, written)) != (note, note):
            raise RuntimeError(
                f"carrier {tag} NOTE (row {row}) did not take: expected={note!r} "
                f"driving/displayed={written!r}"
            )
    for column, width in enumerate(TABLE_WIDTHS):
        actual = float(table.SetColumnWidth(column, width, 0))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(
                f"carrier table column {column} rejected its width: expected={width} actual={actual}"
            )
    # Each tag's size and process is in its NOTE cell (ROW_SIZES); the
    # generated SIZE column, at the document's places, is hidden.
    # SetColumnHidden is VT_VOID; the BOOL readback proves it after rebuild.
    table.SetColumnHidden(SIZE_COLUMN, True)
    tabled_edges = {tag: edges[tag] for tag in TABLED_HOLES}
    _tags(adapter, view, tabled_edges, place=True)
    # NOTE 1 is flagged in the A2/B2 rows; the exact owner text is linked to
    # the saved model property and checked against both native local controls.
    # NOTE 2 (A1_RELATION_NOTE) is flagged in its own rows.
    # The notes stand beside the table's top, risen with it (TABLE_ANCHOR).
    add_note(adapter, "1", .225, .178)
    flagged = add_property_linked_note(adapter, "Outer Pin Row Note", .235, .178)
    add_note(adapter, "2", .225, .168)
    add_note(adapter, A1_RELATION_NOTE, .235, .168)
    add_note(adapter, ORIGIN_NOTE, .225, .148)
    rebuild_drawing(adapter, label="carrier table and tags")
    _size_column_hidden(table, "after its rebuild")

    def check_active_table() -> None:
        current = _source_edges(adapter, view, model, source)
        _outer_row_source(model)
        if (feature.CombineSameSize or feature.CombineTags
                or bool(feature.GetHoleLocationUseDocPrecision())
                or int(feature.GetHoleLocationPrecision()) != spec.TABLE_LOCATION_PLACES):
            raise RuntimeError("carrier table lost individual .XXX rows")
        # The rows' corner cells prove where the origin is; its mark stays
        # on the one corner vertex it was inserted on, never on a hole edge.
        annotation = _early_bound(origin.GetAnnotation(), "IAnnotation")
        attached = tuple(annotation.GetAttachedEntities3() or ())
        if (len(attached) != 1 or attached[0] is None
                or any(int(adapter.swApp.IsSame(attached[0], edge)) == 1
                       for edge in current.values())
                or annotation.IsDangling()):
            raise RuntimeError("carrier table datum left its corner vertex")
        _frozen_rows(table, generated, notes=ROW_NOTES, stage="at settled readback")
        _size_column_hidden(table, "at settled readback")
        # Every tag, the HUB's included, stays on its own physical hole.
        _tags(adapter, view, {tag: current[tag] for tag in TABLED_HOLES}, place=False)
        if str(_early_bound(flagged, "INote").GetText()).strip() != spec.OUTER_Y_NOTE:
            raise RuntimeError("carrier flagged note differs from its model-owned limits")
        rows_total, columns = _inventory(table)
        height = sum(float(table.GetRowHeight(row)) for row in range(rows_total))
        # GetColumnWidth indexes VISIBLE positions, not the hidden-inclusive
        # domain (native BOM evidence, _drawing_tables._bom_physical_columns):
        # with SIZE hidden, positions 0..3 are TAG/X/Y/NOTE.
        visible = tuple(width for column, width in enumerate(TABLE_WIDTHS) if column != SIZE_COLUMN)
        widths = tuple(float(table.GetColumnWidth(position)) for position in range(columns - 1))
        if any(abs(actual - expected) > 1e-6 for actual, expected in zip(widths, visible, strict=True)):
            raise RuntimeError(f"carrier visible column widths {widths!r}, expected {visible!r}")
        if TABLE_ANCHOR[1] - height < .015 or TABLE_ANCHOR[0] + sum(widths) > .216:
            raise RuntimeError(
                f"carrier table crosses the border or title-block lane: "
                f"{sum(widths) * 1000:.1f} x {height * 1000:.1f} mm from {TABLE_ANCHOR}"
            )
        _owned_table(adapter, view, feature, table)

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
