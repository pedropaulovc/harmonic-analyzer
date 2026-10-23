"""Offline behavior of the measured-native reference-text shelf core.

Every fixture is a native-shaped audit record (the layout-audit dump shape):
the recovered clamp SupplierHeadHeight primitives and the actual jam-nut RD1
across-flats row from the 2026-10-22 rolling-main layout audit. No COM, no
source-feature inventory, no callback bookkeeping: only measured geometry,
read-back behavior and late native mutation.
"""

from __future__ import annotations

import copy
import gc
import json
import weakref
from math import cos, isfinite, pi, sin
from types import SimpleNamespace

import pytest

import _supplier_reference_text as core
from _layout_audit import annotation_geometry, calibrate_sheet_advance
from _layout_geometry import Box, segment_box_distance


_TOL = 1e-5
_LABEL = "reference text"


# --------------------------------------------------------------------------
# native records
# --------------------------------------------------------------------------


def _recovered_head_height():
    # 4dcfee recovered SupplierHeadHeight display data, metres, 2026-10-21.
    # Vertical outside-arrow short row: witnesses are the horizontal runs at
    # each tip, tails run on past the arrowheads.
    z = 0.0000125
    return {
        "type": 4,
        "name": "SupplierHeadHeight",
        "visible": 1,
        "pos": (0.1029834, 0.2350132, z),
        "display": {
            "lines": [
                [0, 0, 0, 0, 0.1135714, 0.2347655, z, 0.1019834, 0.2347655, z],
                [0, 0, 0, 0, 0.1135714, 0.2352608, z, 0.1019834, 0.2352608, z],
                [0, 0, 0, 0, 0.1029834, 0.2347655, z, 0.1029834, 0.2284155, z],
                [0, 0, 0, 0, 0.1029834, 0.2352608, z, 0.1029834, 0.2416108, z],
            ],
            "arrows": [
                [0.1029834, 0.2347655, z, 0, -1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
                [0.1029834, 0.2352608, z, 0, 1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
            ],
            "texts": [
                {
                    "t": " (0.156 in) ",
                    "pos": (0.0916157, 0.232235, z),
                    "h": 0.0035,
                    "w": 0.0227354,
                    "ref": 1,
                    "ang": 0.0,
                }
            ],
        },
    }


def _nut_rd1():
    # pn-vn-pen-hanger-jam-nut Front view RD1, rolling-main-post-v44 run
    # d534525e, 2026-10-22: the actual "(1/4" in) / ACROSS FLATS" across-flats
    # row. Five text runs (fraction numerator and denominator are their own
    # runs), six lines (lines[0] is the fraction bar, drawn INSIDE the text
    # font union), two outside arrows with 6.35 mm tails.
    z = -0.0059531
    return {
        "type": 4,
        "name": "RD1",
        "visible": 1,
        "owner_type": 0,
        "pos": (0.115, 0.1661689, z),
        "layer": "",
        "display": {
            "lines": [
                [0, 0, 0, 0, 0.1099372, 0.169306, z, 0.113549, 0.169306, z],
                [0, 0, 0, 0, 0.099125, 0.1444154, z, 0.099125, 0.1598138, z],
                [0, 0, 0, 0, 0.130875, 0.1444154, z, 0.130875, 0.1598138, z],
                [0, 0, 0, 0, 0.099125, 0.1588138, z, 0.092775, 0.1588138, z],
                [0, 0, 0, 0, 0.099125, 0.1588138, z, 0.130875, 0.1588138, z],
                [0, 0, 0, 0, 0.130875, 0.1588138, z, 0.137225, 0.1588138, z],
            ],
            "arrows": [
                [0.099125, 0.1588138, z, -1.0, -0.0, 0.0, 0.003556, 0.000762, 0, 0, 0, 1],
                [0.130875, 0.1588138, z, 1.0, 0.0, -0.0, 0.003556, 0.000762, 0, 0, 0, 1],
            ],
            "texts": [
                _nut_text("(", (0.1077035, 0.1664411, z), 0.0017208),
                _nut_text("1", (0.11045, 0.1689983, z), 0.0025861),
                _nut_text("4", (0.11045, 0.16437, z), 0.0025861),
                _nut_text('" in)', (0.1140618, 0.1664411, z), 0.0082347),
                _nut_text("ACROSS FLATS", (0.0988757, 0.1588138, z), 0.0322486),
            ],
        },
        "dim": {"hole_callout": False},
    }


def _nut_text(text, pos, width):
    return {
        "t": text,
        "pos": pos,
        "h": 0.0035,
        "ref": 1,
        "ang": 0.0,
        "font": "Century Gothic",
        "ls": 0.001,
        "w": width,
    }


_NUT_FRACTION_BAR = 0  # lines index
_NUT_TAIL_END = 0.137225
_NUT_SPAN = 0.130875 - 0.099125
_NUT_UNION_WIDTH = 0.0322486


def _long_length():
    # A vertical reference with 50 mm of native span: more than enough room
    # for its own text, so the default rule leaves it on its line.
    record = _recovered_head_height()
    record["name"] = "SupplierLength"
    data = record["display"]
    data["arrows"][0][1] = 0.210
    data["arrows"][1][1] = 0.260
    data["lines"][0][5] = data["lines"][0][8] = 0.210
    data["lines"][1][5] = data["lines"][1][8] = 0.260
    data["lines"][2:] = [
        [0, 0, 0, 0, 0.1029834, 0.210, 0, 0.1029834, 0.229, 0],
        [0, 0, 0, 0, 0.1029834, 0.242, 0, 0.1029834, 0.260, 0],
    ]
    data["texts"][0]["t"] = "(1.25 in)"
    return record


def _text_box(record):
    """The all-run font union SolidWorks reports: every run, lower-left along
    its baseline, ``h`` tall and ``w`` wide. No glyph estimate."""
    runs = record["display"]["texts"]
    assert all(float(row["w"]) > 0.0 and float(row["h"]) > 0.0 for row in runs)
    return Box(
        min(row["pos"][0] for row in runs),
        min(row["pos"][1] for row in runs),
        max(row["pos"][0] + row["w"] for row in runs),
        max(row["pos"][1] + row["h"] for row in runs),
    )


def _physical_ink(geometry):
    """Native ink the shelved text must clear: every tip-incident line and
    arrowhead plus each measured witness run. The fraction bar is text."""
    record = geometry["record"]
    axis = geometry["axis"]
    ink = annotation_geometry(
        record, owner=record["name"], advance=calibrate_sheet_advance((record,))
    )
    assert ink is not None and ink.segments
    stations = [tip[axis] for tip in geometry["tips"]]
    physical = []
    for segment in ink.segments:
        if segment.role == "arrow" or segment.role == "dim-line":
            physical.append(segment)
        elif segment.role == "ext-line" and any(
            abs((segment.x0 if axis == 0 else segment.y0) - station) <= _TOL
            and abs((segment.x1 - segment.x0) if axis == 0 else (segment.y1 - segment.y0))
            < 1e-7
            for station in stations
        ):
            physical.append(segment)
    assert len(physical) >= 2 + len(stations)
    return physical


# --------------------------------------------------------------------------
# native-shaped display
# --------------------------------------------------------------------------


class _Display:
    """Bounded native model following the thumb/clamp measured-offset
    behavior: text moves independently; enabling OffsetText snaps the native
    line to its seeded transverse anchor; later text moves leave it fixed.
    ``attached`` lines (a fraction bar) travel with the text."""

    def __init__(self, record, axis, *, attached=(), defect=None):
        self.record = record
        self.name = record["name"]
        self.axis = axis
        self.attached = tuple(attached)
        self.defect = defect
        self.position = tuple(record["pos"])
        self.original_position = self.position
        self._offset = False
        self.enable_count = 0

    def GetAnnotation(self):
        return self

    def GetPosition(self):
        return self.position

    @property
    def OffsetText(self):
        return self._offset

    @OffsetText.setter
    def OffsetText(self, enabled):
        if self.defect == "ignored-offset":
            return  # Native setter silently keeps the row on its line.
        if enabled and not self._offset:
            self.enable_count += 1
            transverse = 1 - self.axis
            delta = (
                self.position[transverse]
                - self.record["display"]["arrows"][0][transverse]
            )
            self.shift_stations(transverse, delta)
            if self.defect == "enable-drifts-stations":
                self.shift_stations(self.axis, 0.0001)
        self._offset = enabled

    def shift_stations(self, axis, delta):
        data = self.record["display"]
        for index, row in enumerate(data["lines"]):
            if index in self.attached:
                continue
            row[4 + axis] += delta
            row[7 + axis] += delta
        for row in data["arrows"]:
            row[axis] += delta

    def move_text(self, dx, dy):
        data = self.record["display"]
        for row in data["texts"]:
            px, py, pz = row["pos"]
            row["pos"] = (px + dx, py + dy, pz)
        for index in self.attached:
            row = data["lines"][index]
            row[4] += dx
            row[5] += dy
            row[7] += dx
            row[8] += dy

    def SetPosition2(self, x, y, z):
        phase = "shelf" if self.OffsetText else "seed"
        if self.defect == f"ignored-{phase}":
            return True  # Native success is not proof of a settled move.
        if self.defect == f"refused-{phase}":
            return False
        delta = (x - self.position[0], y - self.position[1])
        self.move_text(*delta)
        self.position = (x, y, z)
        self.record["pos"] = self.position
        if (
            self.defect == "station-drift"
            and self.OffsetText
            and abs(delta[self.axis]) > 0.001
        ):
            self.shift_stations(self.axis, 0.0001)
        return True


@pytest.fixture
def native_reads(monkeypatch):
    """Core reads each display's current record through the audit reader;
    rebuilds are free; early binding is identity."""
    errors = {}
    monkeypatch.setattr(
        core, "_Reader", lambda _adapter: SimpleNamespace(take_errors=lambda: dict(errors))
    )
    monkeypatch.setattr(
        core,
        "_dump_annotation",
        lambda _reader, annotation: copy.deepcopy(annotation.record),
    )
    monkeypatch.setattr(core, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(core, "_early_bound", lambda obj, _interface: obj)
    return errors


def _static(record):
    return SimpleNamespace(GetAnnotation=lambda: SimpleNamespace(record=record))


@pytest.fixture(
    params=((_nut_rd1, 0, 1), (_recovered_head_height, 1, 0)),
    ids=("horizontal-nut", "vertical-clamp"),
)
def witness_case(request):
    factory, axis, index = request.param
    return SimpleNamespace(record=factory(), axis=axis, index=index)


def _witness_pieces(row, axis, intervals):
    """Native line pieces at fractional positions on the original witness.

    Fractions may arrive reversed, duplicated, overlapping or out of order;
    the source row's station, Z coordinates and native header stay intact.
    """
    across = 1 - axis
    low, high = sorted((row[4 + across], row[7 + across]))
    pieces = []
    for start, end in intervals:
        piece = list(row)
        piece[4 + across] = low + start * (high - low)
        piece[7 + across] = low + end * (high - low)
        pieces.append(piece)
    return pieces


@pytest.fixture
def physical_case(witness_case):
    case = witness_case
    return SimpleNamespace(
        record=case.record, axis=case.axis, index=3 if case.axis == 0 else 2
    )


def _physical_pieces(row, axis, intervals):
    # The existing native fragmentation helper varies its transverse axis.
    return _witness_pieces(row, 1 - axis, intervals)


def _centre_native_fragment(row, *, reference, angle, centre):
    """Encode one known physical text centre using swTextPosition_e anchors."""
    fx, fy = {
        0: (0.0, 1.0), 1: (0.0, 0.0), 2: (0.5, 0.5),
        3: (1.0, 1.0), 4: (1.0, 0.0), 5: (0.5, 1.0),
    }[reference]
    dx, dy = (fx - 0.5) * row["w"], (fy - 0.5) * row["h"]
    row["ref"] = reference
    row["ang"] = angle
    row["pos"] = (
        centre[0] + dx * cos(angle) - dy * sin(angle),
        centre[1] + dx * sin(angle) + dy * cos(angle),
        row["pos"][2],
    )


# --------------------------------------------------------------------------
# measure_reference_text
# --------------------------------------------------------------------------


def test_measure_reads_actual_nut_fraction_row_as_all_native_fragments(native_reads):
    record = _nut_rd1()
    original = copy.deepcopy(record)
    geometry = core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)

    assert geometry["axis"] == 0
    assert geometry["tips"] == ((0.099125, 0.1588138), (0.130875, 0.1588138))
    assert geometry["witnesses"] == (
        (0.099125, 0.1444154, 0.1598138),
        (0.130875, 0.1444154, 0.1598138),
    )
    # Reach is the actual tail end, past the arrowhead base (0.134431).
    assert geometry["reach"] == pytest.approx(_NUT_TAIL_END)
    assert geometry["reach"] > 0.130875 + 0.003556
    # The text box is the union of ALL five reported runs, no glyph estimate:
    # "ACROSS FLATS" sets the width, the numerator "1" the top.
    text = geometry["text"]
    assert text == _text_box(record)
    assert text.width == pytest.approx(_NUT_UNION_WIDTH)
    assert text.ymax == pytest.approx(0.1689983 + 0.0035)
    assert text.width + 2 * (core.CLEAR_GAP_M + core.PLACE_SETTLE_M) > _NUT_SPAN
    # The fraction bar sits inside the font union; it is retained, not a
    # witness, not rejected, and the record is handed back whole.
    bar = record["display"]["lines"][_NUT_FRACTION_BAR]
    assert text.xmin < bar[4] < bar[7] < text.xmax
    assert text.ymin < bar[5] < text.ymax
    assert geometry["record"] == original
    assert len(geometry["record"]["display"]["lines"]) == 6
    assert len(geometry["record"]["display"]["texts"]) == 5
    assert record == original


def test_measure_reads_recovered_vertical_head_height(native_reads):
    record = _recovered_head_height()
    geometry = core.measure_reference_text(None, _static(record), axis=1, label=_LABEL)
    assert geometry["axis"] == 1
    assert geometry["tips"] == ((0.1029834, 0.2347655), (0.1029834, 0.2352608))
    assert geometry["witnesses"] == (
        (0.2347655, 0.1019834, 0.1135714),
        (0.2352608, 0.1019834, 0.1135714),
    )
    assert geometry["reach"] == pytest.approx(0.2416108)
    assert geometry["text"] == _text_box(record)
    assert geometry["text"].height == pytest.approx(0.0035)
    assert geometry["record"] == record


def test_measure_reports_actual_physical_lines_and_normal_bounds(native_reads, physical_case):
    case = physical_case
    before = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    expected = (
        ((0.1588138, 0.1588138, 0.092775, 0.137225),)
        if case.axis == 0
        else (
            (0.1029834, 0.1029834, 0.2284155, 0.2347655),
            (0.1029834, 0.1029834, 0.2352608, 0.2416108),
        )
    )
    assert isinstance(before["physical_lines"], tuple)
    assert len(before["physical_lines"]) == len(expected)
    for actual, interval in zip(before["physical_lines"], expected, strict=True):
        assert isinstance(actual, tuple)
        assert actual == pytest.approx(interval)
        assert len(actual) == 4 and all(isfinite(value) for value in actual)

    row = case.record["display"]["lines"][case.index]
    normal = 1 - case.axis
    support = row[4 + normal]
    row[4 + normal] = support + 0.8 * _TOL
    row[7 + normal] = support + 0.9 * _TOL
    measured = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    assert measured["physical_lines"][0][:2] == pytest.approx(
        (support if case.axis == 0 else support + 0.8 * _TOL, support + 0.9 * _TOL)
    )
    # Real normal bounds survive axial union; neither snapping to the support
    # nor averaging the endpoints is a faithful physical measurement.
    row[4 + normal] = support - 0.9 * _TOL
    row[7 + normal] = support - 0.8 * _TOL
    moved = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    assert moved["tips"] == measured["tips"]
    assert moved["witnesses"] == measured["witnesses"]
    with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
        core.assert_reference_text_stations(measured, moved, label=_LABEL)


def test_stations_reject_actual_100um_free_tail_mutation(native_reads, physical_case):
    case = physical_case
    display = _static(case.record)
    original = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    healthy = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    core.assert_reference_text_stations(original, healthy, label=_LABEL)
    # Move only the negative/free tail end, not the arrow tip, witnesses or
    # positive reach. Deliberately do not read the new field before refusal:
    # the old production core must expose DidNotRaise, not a missing-field error.
    row = case.record["display"]["lines"][case.index]
    row[7 + case.axis] -= 0.0001
    moved = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    for key in ("tips", "witnesses", "reach"):
        assert moved[key] == original[key]
    with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
        core.assert_reference_text_stations(original, moved, label=_LABEL)


@pytest.mark.parametrize(
    "axial_gap_half", (4.0e-6, 4.9e-6), ids=("radial-inside", "radial-outside")
)
def test_measure_tip_incidence_uses_actual_fragments_not_gap_closed_union(
    native_reads, physical_case, axial_gap_half
):
    case = physical_case
    record = case.record
    original = core.measure_reference_text(
        None, _static(record), axis=case.axis, label=_LABEL
    )
    tip = original["tips"][0]
    axis, normal = case.axis, 1 - case.axis
    lines = record["display"]["lines"]
    tail = list(lines[case.index])
    low = min(tail[4 + axis], tail[7 + axis])
    # Horizontal RD1 also has an unbroken inter-tip run, which must not
    # accidentally supply healthy ink at the tested tip. Replace that run
    # with the positive-side fragment, keeping the other tip's ink intact.
    high = (
        max(lines[4][4 + axis], lines[4][7 + axis])
        if axis == 0 else tip[axis] + 0.0001
    )
    pieces = []
    for start, end in (
        (low, tip[axis] - axial_gap_half),
        (tip[axis] + axial_gap_half, high),
    ):
        piece = list(tail)
        piece[4 + axis], piece[7 + axis] = start, end
        piece[4 + normal] = piece[7 + normal] = tip[normal] + 9e-6
        pieces.append(piece)
    lines[case.index:case.index + (2 if axis == 0 else 1)] = pieces
    retained = copy.deepcopy(record)
    # Both fragments pass support selection and their axial gap closes at
    # the existing 10 um union tolerance. Nevertheless, the nearest ACTUAL
    # endpoint is sqrt(9**2 + 4.9**2) > 10 um in the negative case; the
    # gap-closed rectangle's 9 um distance is not native line incidence.
    assert 2 * axial_gap_half <= _TOL
    assert original["tips"] == tuple(
        sorted(tuple(arrow[:2]) for arrow in record["display"]["arrows"])
    )
    if axial_gap_half == 4.9e-6:
        with pytest.raises(RuntimeError, match="lost.*native.*(?:witness|line)"):
            core.measure_reference_text(None, _static(record), axis=axis, label=_LABEL)
    else:
        measured = core.measure_reference_text(
            None, _static(record), axis=axis, label=_LABEL
        )
        assert measured["tips"] == original["tips"]
        assert measured["witnesses"] == original["witnesses"]
        assert measured["reach"] == original["reach"]
        assert measured["physical_lines"][0] == pytest.approx(
            (
                tip[normal] if axis == 0 else tip[normal] + 9e-6,
                tip[normal] + 9e-6,
                low,
                original["physical_lines"][0][3] if axis == 0 else high,
            )
        )
        assert measured["record"] == retained
    assert record == retained


@pytest.mark.parametrize("factor", (0.999, 1.0, 1.001), ids=("below", "at", "above"))
def test_measure_actual_tip_distance_uses_exact_existing_radial_tolerance(
    native_reads, physical_case, factor
):
    case = physical_case
    axis, normal = case.axis, 1 - case.axis
    display = _Display(case.record, axis)
    # Translate the actual native tip to zero on BOTH axes before constructing
    # the 6-8-10 um radial boundary, avoiding large-sheet subtraction noise.
    tip = tuple(case.record["display"]["arrows"][0][:2])
    display.shift_stations(0, -tip[0])
    display.shift_stations(1, -tip[1])
    original = core.measure_reference_text(None, display, axis=axis, label=_LABEL)
    assert original["tips"][0] == (0.0, 0.0)
    lines = case.record["display"]["lines"]
    tail = list(lines[case.index])
    low = min(tail[4 + axis], tail[7 + axis])
    high = (
        max(lines[4][4 + axis], lines[4][7 + axis])
        if axis == 0 else 0.0001
    )
    pieces = []
    for nearest, farthest in ((-8e-6 * factor, low), (8e-6 * factor, high)):
        piece = list(tail)
        # Start each segment at its nearest endpoint: the segment-distance
        # projection clamps to zero without subtracting its far endpoint.
        piece[4 + axis], piece[7 + axis] = nearest, farthest
        piece[4 + normal] = piece[7 + normal] = 6e-6 * factor
        pieces.append(piece)
    lines[case.index:case.index + (2 if axis == 0 else 1)] = pieces
    retained = copy.deepcopy(case.record)
    if factor > 1.0:
        with pytest.raises(RuntimeError, match="lost.*native.*(?:witness|line)"):
            core.measure_reference_text(None, display, axis=axis, label=_LABEL)
    else:
        measured = core.measure_reference_text(None, display, axis=axis, label=_LABEL)
        for key in ("tips", "witnesses", "reach"):
            assert measured[key] == original[key]
        # This 16 um gap is genuinely disjoint; successful native incidence
        # must come from an actual fragment, never from union gap closing.
        assert len(measured["physical_lines"]) == len(original["physical_lines"]) + 1
        assert measured["record"] == retained
    assert case.record == retained


@pytest.mark.parametrize(
    "intervals",
    (
        ((0.0, 0.25), (0.25, 0.7), (0.7, 1.0)),
        ((0.8, 0.3), (1.0, 0.6), (0.4, 0.0), (0.8, 0.3), (0.2, 0.25)),
    ),
    ids=("touching-splits", "reversed-overlaps-duplicates-nesting"),
)
def test_physical_union_accepts_equivalent_native_fragmentation(
    native_reads, physical_case, intervals
):
    case = physical_case
    lines = case.record["display"]["lines"]
    original = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    lines[case.index:case.index + 1] = _physical_pieces(
        lines[case.index], case.axis, intervals
    )
    lines.reverse()
    case.record["display"]["arrows"].reverse()
    fragmented = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    assert fragmented["physical_lines"] == original["physical_lines"]
    core.assert_reference_text_stations(original, fragmented, label=_LABEL)
    # Coalesce the entire horizontal coverage: both tips are now INSIDE the
    # segment rather than native endpoints. Vertical coverage keeps its gap.
    retained = copy.deepcopy(case.record)
    lines[:] = [
        row for row in lines
        if abs(row[4 + (1 - case.axis)] - original["tips"][0][1 - case.axis]) > _TOL
        or abs(row[7 + (1 - case.axis)] - original["tips"][0][1 - case.axis]) > _TOL
    ]
    template = retained["display"]["lines"][-1]
    for normal_low, normal_high, low, high in original["physical_lines"]:
        row = list(template)
        row[4 + case.axis], row[7 + case.axis] = high, low
        row[4 + (1 - case.axis)] = normal_high
        row[7 + (1 - case.axis)] = normal_low
        lines.append(row)
    coalesced = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    assert coalesced["physical_lines"] == original["physical_lines"]
    core.assert_reference_text_stations(original, coalesced, label=_LABEL)


@pytest.mark.parametrize("defect", ("missing-component", "interior-gap", "moved-gap"))
def test_physical_union_retains_disjoint_coverage_and_refuses_loss(
    native_reads, physical_case, defect
):
    case = physical_case
    lines = case.record["display"]["lines"]
    row = list(lines[case.index])
    intervals = ((0.0, 0.25), (0.4, 0.6), (0.8, 1.0))
    lines[case.index:case.index + 1] = _physical_pieces(row, case.axis, intervals)
    original = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    low, high = sorted((row[4 + case.axis], row[7 + case.axis]))
    support = row[4 + (1 - case.axis)]
    assert len(original["physical_lines"]) == (3 if case.axis == 0 else 4)
    for actual, (start, end) in zip(original["physical_lines"][:3], intervals, strict=True):
        assert actual == pytest.approx(
            (support, support, low + start * (high - low), low + end * (high - low))
        )
    changed = {
        "missing-component": ((0.0, 0.25), (0.8, 1.0)),
        "interior-gap": ((0.0, 0.25), (0.4, 0.46), (0.54, 0.6), (0.8, 1.0)),
        "moved-gap": ((0.0, 0.3), (0.45, 0.6), (0.8, 1.0)),
    }[defect]
    lines[case.index:case.index + 3] = _physical_pieces(row, case.axis, changed)
    after = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    for key in ("tips", "witnesses", "reach"):
        assert after[key] == original[key]
    assert after["physical_lines"][0][2] == original["physical_lines"][0][2]
    assert after["physical_lines"][-1][3] == original["physical_lines"][-1][3]
    with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
        core.assert_reference_text_stations(original, after, label=_LABEL)


@pytest.mark.parametrize("factor", (0.999, 1.0, 1.001), ids=("below", "at", "above"))
def test_physical_union_gap_uses_single_existing_tolerance(native_reads, physical_case, factor):
    case = physical_case
    # Put the split at zero so the exact boundary is not perturbed by
    # subtracting two large native sheet coordinates.
    display = _Display(case.record, case.axis)
    row = case.record["display"]["lines"][case.index]
    midpoint = (row[4 + case.axis] + row[7 + case.axis]) / 2
    display.shift_stations(case.axis, -midpoint)
    original = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    lines = case.record["display"]["lines"]
    pieces = _physical_pieces(lines[case.index], case.axis, ((0.0, 0.5), (0.5, 1.0)))
    pieces[0][7 + case.axis] = 0.0
    pieces[1][4 + case.axis] = factor * _TOL
    lines[case.index:case.index + 1] = pieces
    after = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    if factor <= 1.0:
        assert after["physical_lines"] == original["physical_lines"]
        core.assert_reference_text_stations(original, after, label=_LABEL)
    else:
        assert len(after["physical_lines"]) == len(original["physical_lines"]) + 1
        with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
            core.assert_reference_text_stations(original, after, label=_LABEL)


@pytest.mark.parametrize("factor", (0.999, 1.0, 1.001), ids=("below", "at", "above"))
def test_physical_station_distance_uses_existing_tolerance(factor):
    original = dict(
        tips=((0.0, 0.0), (0.01, 0.0)),
        witnesses=((0.0, -0.01, 0.01), (0.01, -0.01, 0.01)),
        physical_lines=((0.0, 0.0, 0.0, 0.02),),
    )
    after = dict(original, physical_lines=((0.0, 0.0, -factor * _TOL, 0.02),))
    if factor <= 1.0:
        core.assert_reference_text_stations(original, after, label=_LABEL)
    else:
        with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
            core.assert_reference_text_stations(original, after, label=_LABEL)


def test_physical_lines_exclude_true_off_support_strokes_but_keep_raw_record(
    native_reads, physical_case
):
    case = physical_case
    original = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    normal = 1 - case.axis
    row = case.record["display"]["lines"][case.index]
    underline, connector = list(row), list(row)
    underline[4 + normal] += 2 * _TOL
    underline[7 + normal] += 2 * _TOL
    # One endpoint on support is insufficient, even for a tiny diagonal.
    connector[7 + normal] += 2 * _TOL
    case.record["display"]["lines"].extend((underline, connector))
    after = core.measure_reference_text(
        None, _static(case.record), axis=case.axis, label=_LABEL
    )
    assert after["record"] == case.record
    assert after["record"]["display"]["lines"][-2:] == [underline, connector]
    assert after["physical_lines"] == original["physical_lines"]
    core.assert_reference_text_stations(original, after, label=_LABEL)


def test_measure_keeps_offset_ink_in_record_but_out_of_witnesses(native_reads):
    record = _recovered_head_height()
    display = _static(record)
    before = core.measure_reference_text(None, display, axis=1, label=_LABEL)
    z = record["pos"][2]
    # Native OffsetText draws a connector and an underline as display lines.
    # The underline is at neither arrow station; the diagonal connector is
    # not a witness even where it starts on an arrow tip.
    offset_rows = [
        [0, 0, 0, 0, 0.0916157, 0.250, z, 0.1143511, 0.250, z],
        [0, 0, 0, 0, 0.1029834, 0.2352608, z, 0.0916157, 0.250, z],
    ]
    record["display"]["lines"].extend(offset_rows)
    for row in record["display"]["lines"][:2]:
        row[4:7], row[7:10] = row[7:10], row[4:7]
    with_offset = copy.deepcopy(record)
    after = core.measure_reference_text(None, display, axis=1, label=_LABEL)
    for key in ("tips", "witnesses", "reach"):
        assert after[key] == before[key]
    assert after["record"] == with_offset
    assert after["record"]["display"]["lines"][-2:] == offset_rows
    core.assert_reference_text_stations(before, after, label=_LABEL)


@pytest.mark.parametrize(
    ("defect", "message"),
    (
        ("zero-width", "native size"),
        ("nan-height", "native size"),
        ("negative-width", "native size"),
        ("missing-width", "native size"),
        ("one-arrow", "arrow"),
        ("short-arrow-row", "arrow"),
        ("nan-arrow-tip", "arrow"),
        ("transverse-skew", "orientation"),
        ("coincident-tips", "orientation"),
        ("lost-witness", "witness"),
        ("witness-off-station", "witness"),
        ("lost-tip-lines", "witness"),
        ("not-a-dimension", "unreadable"),
        ("read-errors", "unreadable"),
        ("three-arrows", "arrow"),
        ("longest-pos-x-nan", "finite|native|unreadable"),
        ("longest-pos-y-inf", "finite|native|unreadable"),
        ("angle-nan", "finite|native|unreadable"),
        ("missing-pos", "finite|native|unreadable"),
    ),
)
def test_measure_rejects_unmeasured_or_broken_native_geometry(
    native_reads, defect, message
):
    record = _nut_rd1()
    data = record["display"]
    if defect == "zero-width":
        data["texts"][1]["w"] = 0.0  # the fraction numerator alone
    elif defect == "nan-height":
        data["texts"][4]["h"] = float("nan")
    elif defect == "negative-width":
        data["texts"][0]["w"] = -0.0017208
    elif defect == "missing-width":
        del data["texts"][3]["w"]
    elif defect == "one-arrow":
        del data["arrows"][1]
    elif defect == "short-arrow-row":
        data["arrows"][1] = data["arrows"][1][:7]
    elif defect == "nan-arrow-tip":
        data["arrows"][0][0] = float("nan")
    elif defect == "transverse-skew":
        data["arrows"][1][1] += 0.001
    elif defect == "coincident-tips":
        data["arrows"][1][0] = data["arrows"][0][0]
    elif defect == "lost-witness":
        del data["lines"][2]
    elif defect == "witness-off-station":
        data["lines"][1][4] = data["lines"][1][7] = 0.099125 + 0.0001
    elif defect == "lost-tip-lines":
        # Only the fraction bar and witnesses remain: no tip-incident line.
        del data["lines"][3:]
    elif defect == "not-a-dimension":
        record["type"] = 14
    elif defect == "read-errors":
        native_reads["GetLineAtIndex3"] = "E_FAIL"
    elif defect == "three-arrows":
        data["arrows"].append(list(data["arrows"][1]))
    else:
        _corrupt_text(data["texts"][4], defect)
    with pytest.raises(RuntimeError, match=message) as exc:
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)
    assert str(exc.value).startswith(_LABEL)


def test_measure_witnesses_are_perpendicular_runs_on_actual_stations(native_reads):
    # A run on the station but along the axis is tail/line ink, never a
    # witness; the station's perpendicular run is required even then.
    record = _nut_rd1()
    data = record["display"]
    data["lines"][1] = [0, 0, 0, 0, 0.099125, 0.1444154, 0, 0.104, 0.1444154, 0]
    with pytest.raises(RuntimeError, match="witness"):
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)


@pytest.mark.parametrize("reference", range(6))
@pytest.mark.parametrize("angle", (0.0, pi / 2, pi / 6), ids=("level", "vertical", "oblique"))
def test_measure_uses_native_anchor_and_rotated_measured_extent(
    native_reads, reference, angle
):
    record = _recovered_head_height()
    row = record["display"]["texts"][0]
    width, height = row["w"], row["h"]
    cx, cy = row["pos"][0] + width / 2, row["pos"][1] + height / 2
    _centre_native_fragment(row, reference=reference, angle=angle, centre=(cx, cy))
    original = copy.deepcopy(record)
    geometry = core.measure_reference_text(None, _static(record), axis=1, label=_LABEL)

    # Projection of a known centred rectangle, independently of its native
    # anchor. All six anchors must describe this same physical font extent.
    extent_x = width * abs(cos(angle)) + height * abs(sin(angle))
    extent_y = width * abs(sin(angle)) + height * abs(cos(angle))
    text = geometry["text"]
    assert (text.xmin, text.ymin, text.xmax, text.ymax) == pytest.approx(
        (cx - extent_x / 2, cy - extent_y / 2, cx + extent_x / 2, cy + extent_y / 2)
    )
    assert geometry["record"] == original
    assert record == original

    dx, dy = 0.021, -0.017
    display = _Display(record, 1)
    display.move_text(dx, dy)
    translated = core.measure_reference_text(None, display, axis=1, label=_LABEL)
    moved = translated["text"]
    assert (moved.xmin, moved.ymin, moved.xmax, moved.ymax) == pytest.approx(
        (text.xmin + dx, text.ymin + dy, text.xmax + dx, text.ymax + dy)
    )
    assert translated["tips"] == geometry["tips"]
    assert translated["witnesses"] == geometry["witnesses"]


@pytest.mark.parametrize("reference", (None, -1, 6, True, 1.0, "1"))
def test_measure_refuses_unknown_or_non_native_text_reference(native_reads, reference):
    record = _nut_rd1()
    # A valid widest run cannot hide an unreadable fraction fragment.
    record["display"]["texts"][1]["ref"] = reference
    with pytest.raises(RuntimeError, match="reference|fragment"):
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)


def test_native_bounds_preserve_every_fragment_in_raw_order():
    texts = _nut_rd1()["display"]["texts"]
    expected = []
    for row, reference, angle in zip(
        texts, (3, 0, 4, 2, 5), (0.0, pi / 2, pi / 6, 0.0, pi / 6), strict=True
    ):
        width, height = row["w"], row["h"]
        cx, cy = row["pos"][0] + width / 2, row["pos"][1] + height / 2
        extent_x = width * abs(cos(angle)) + height * abs(sin(angle))
        extent_y = width * abs(sin(angle)) + height * abs(cos(angle))
        expected.append(
            (cx - extent_x / 2, cy - extent_y / 2, cx + extent_x / 2, cy + extent_y / 2)
        )
        _centre_native_fragment(row, reference=reference, angle=angle, centre=(cx, cy))
    # Duplicate ink is still a distinct raw fragment for downstream leader
    # checks; the public helper must not deduplicate or reorder it.
    texts.append(copy.deepcopy(texts[1]))
    expected.append(expected[1])
    original = copy.deepcopy(texts)
    bounds, fragments = core.measured_native_text_bounds(texts, label=_LABEL)

    assert len(fragments) == len(texts) == len(expected)
    for fragment, box in zip(fragments, expected, strict=True):
        assert (fragment.xmin, fragment.ymin, fragment.xmax, fragment.ymax) == pytest.approx(box)
    assert (bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax) == pytest.approx((
        min(box[0] for box in expected), min(box[1] for box in expected),
        max(box[2] for box in expected), max(box[3] for box in expected),
    ))
    assert texts == original


def test_native_bounds_preserve_historical_4fd_pd_thickness_caption():
    # Historical actual4fd PD thickness readback, not the current 5da failure.
    # The second BSTR has no visible ink but has measured font advance.
    texts = [
        {"t": text, "pos": (x, y, 0.0), "w": width,
         "h": 0.0035, "ref": 1, "ang": 0.0}
        for text, x, y, width in (
            (" (0.50 ", 0.1060793, 0.1403535, 0.0133583),
            (" ", 0.1195665, 0.1448257, 0.0012931),
            ("-", 0.1194377, 0.1403, 0.0015507),
            ("0.00", 0.1209883, 0.1448257, 0.0090514),
            ("0.05", 0.1209883, 0.1403, 0.0090514),
            (" mm) ", 0.1300397, 0.1403535, 0.0130569),
        )
    ]
    original = copy.deepcopy(texts)
    expected = (
        (0.1060793, 0.1403535, 0.1194376, 0.1438535),
        (0.1195665, 0.1448257, 0.1208596, 0.1483257),
        (0.1194377, 0.1403, 0.1209884, 0.1438),
        (0.1209883, 0.1448257, 0.1300397, 0.1483257),
        (0.1209883, 0.1403, 0.1300397, 0.1438),
        (0.1300397, 0.1403535, 0.1430966, 0.1438535),
    )
    bounds, fragments = core.measured_native_text_bounds(texts, label=_LABEL)

    assert isinstance(fragments, tuple)
    assert len(fragments) == 6
    for fragment, box in zip(fragments, expected, strict=True):
        assert (fragment.xmin, fragment.ymin, fragment.xmax, fragment.ymax) == pytest.approx(box)
    assert fragments[1].width == pytest.approx(0.0012931)
    assert fragments[1].height == pytest.approx(0.0035)
    assert (bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax) == pytest.approx(
        (0.1060793, 0.1403, 0.1430966, 0.1483257)
    )
    assert texts == original


@pytest.mark.parametrize("text", ("", " "), ids=("empty-bstr", "space-bstr"))
def test_native_bounds_blank_font_advance_expands_full_union(text):
    texts = [
        _nut_text("visible", (0.1, 0.2, 0.0), 0.01),
        _nut_text(text, (0.08, 0.19, 0.0), 0.05),
    ]
    texts[1]["h"] = 0.02
    original = copy.deepcopy(texts)
    bounds, fragments = core.measured_native_text_bounds(texts, label=_LABEL)

    assert len(fragments) == 2
    assert (fragments[0].xmin, fragments[0].ymin,
            fragments[0].xmax, fragments[0].ymax) == pytest.approx(
        (0.1, 0.2, 0.11, 0.2035)
    )
    assert (fragments[1].xmin, fragments[1].ymin,
            fragments[1].xmax, fragments[1].ymax) == pytest.approx(
        (0.08, 0.19, 0.13, 0.21)
    )
    # The blank alone extends all four sides beyond the visible run.
    assert bounds.xmin < fragments[0].xmin
    assert bounds.ymin < fragments[0].ymin
    assert bounds.xmax > fragments[0].xmax
    assert bounds.ymax > fragments[0].ymax
    assert (bounds.xmin, bounds.ymin, bounds.xmax, bounds.ymax) == pytest.approx(
        (0.08, 0.19, 0.13, 0.21)
    )
    assert texts == original


@pytest.mark.parametrize(
    "defect", ("missing", "none", "integer", "boolean", "bytes", "list")
)
def test_native_bounds_refuse_unreadable_native_text_in_later_fragment(defect):
    texts = _nut_rd1()["display"]["texts"]
    if defect == "missing":
        del texts[1]["t"]
    else:
        texts[1]["t"] = {
            "none": None, "integer": 1, "boolean": True,
            "bytes": b"1", "list": ["1"],
        }[defect]
    with pytest.raises(RuntimeError, match="unreadable native text") as exc:
        core.measured_native_text_bounds(texts, label=_LABEL)
    assert str(exc.value).startswith(f"{_LABEL} fragment 1 ref=")


def test_measure_fontbox_failure_note_uses_held_whitespace_fragment(
    native_reads, monkeypatch
):
    record = _nut_rd1()
    bad = record["display"]["texts"][1]
    bad["t"] = " "
    bad["w"] = float("nan")
    later_record = _recovered_head_height()
    later_record["name"] = "different second-generation annotation"
    records = iter((record, later_record))
    monkeypatch.setattr(core, "_dump_annotation", lambda *_args: next(records))

    with pytest.raises(RuntimeError, match=f"{_LABEL} fragment 1 ref=") as exc:
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)

    prefix = "supplier_reference_native_fontbox_fields "
    note, = exc.value.__notes__
    assert note.startswith(prefix)
    census = json.loads(note[len(prefix):])
    assert census["label"] == _LABEL
    assert census["axis"] == 0
    assert census["annotation"] == {
        "type": 4, "name": "RD1", "owner_type": 0,
        "pos": {"items": [0.115, 0.1661689, -0.0059531], "omitted_items": 0},
        "visible": 1, "layer": "",
    }
    assert census["fragment_count"] == 5
    assert census["omitted_fragments"] == 0
    assert [fragment["index"] for fragment in census["fragments"]] == list(range(5))
    assert census["fragments"][1] == {
        "index": 1,
        "raw": {
            "fields": {
                "t": " ",
                "pos": {"items": [0.11045, 0.1689983, -0.0059531],
                        "omitted_items": 0},
                "h": 0.0035, "ref": 1, "ang": 0.0,
                "font": "Century Gothic", "ls": 0.001,
                "w": {"non_finite": "nan"},
            },
            "omitted_fields": 0,
        },
        "reference_python_type": "int",
    }
    # The census belongs to the failing read, not a reacquired annotation.
    assert next(records) is later_record


def test_measure_fontbox_failure_note_never_reprs_opaque_native_text(native_reads):
    class OpaqueText:
        def __repr__(self):
            raise AssertionError("native text must not be inspected")

    record = _nut_rd1()
    record["display"]["texts"][1]["t"] = OpaqueText()
    with pytest.raises(RuntimeError, match="unreadable native text") as exc:
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)

    assert str(exc.value).startswith(f"{_LABEL} fragment 1 ref=")
    note, = exc.value.__notes__
    prefix = "supplier_reference_native_fontbox_fields "
    assert note.startswith(prefix)
    census = json.loads(note[len(prefix):])
    assert census["fragments"][1]["raw"]["fields"]["t"] == {
        "unreadable_type": "OpaqueText"
    }


def test_measure_fontbox_failure_note_reports_bounded_text_and_fragment_omissions(
    native_reads,
):
    record = _nut_rd1()
    texts = record["display"]["texts"]
    texts[1]["t"] = "x" * 145
    texts[1]["w"] = 0.0
    texts.extend(copy.deepcopy(texts[0]) for _ in range(12))
    with pytest.raises(RuntimeError, match=f"{_LABEL} fragment 1 ref=") as exc:
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)

    note, = exc.value.__notes__
    prefix = "supplier_reference_native_fontbox_fields "
    assert note.startswith(prefix)
    census = json.loads(note[len(prefix):])
    assert census["fragment_count"] == 17
    assert census["omitted_fragments"] == 1
    assert [fragment["index"] for fragment in census["fragments"]] == list(range(16))
    assert census["fragments"][1]["raw"]["fields"]["t"] == {
        "prefix": "x" * 128, "omitted_characters": 17
    }


def test_measure_fontbox_census_formatting_failure_retains_primary_error(
    native_reads, monkeypatch
):
    record = _nut_rd1()
    record["display"]["texts"][1]["w"] = 0.0
    with pytest.raises(RuntimeError) as primary:
        core.measured_native_text_bounds(record["display"]["texts"], label=_LABEL)

    def fail_census(*_args, **_kwargs):
        raise ValueError("diagnostic formatting fault")

    monkeypatch.setattr(core, "_fontbox_failure_note", fail_census)
    with pytest.raises(RuntimeError) as exc:
        core.measure_reference_text(None, _static(record), axis=0, label=_LABEL)

    assert str(exc.value) == str(primary.value)
    assert type(exc.value.__cause__) is type(primary.value.__cause__)
    assert str(exc.value.__cause__) == str(primary.value.__cause__)
    assert exc.value.__notes__ == [
        "supplier reference fontbox field census formatting failed "
        "(ValueError); original failure retained"
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("w", 0.0), ("w", -0.001), ("w", float("nan")), ("w", float("inf")),
        ("h", 0.0), ("h", -0.001), ("h", float("nan")), ("h", float("inf")),
        ("pos", (0.1, 0.2)),
        ("pos", (float("nan"), 0.2, 0.0)),
        ("pos", (0.1, float("inf"), 0.0)),
        ("pos", (0.1, 0.2, float("nan"))),
        ("ang", None), ("ang", float("nan")), ("ang", float("inf")),
        ("ref", None), ("ref", -1), ("ref", 6),
        ("ref", True), ("ref", 1.0), ("ref", "1"),
    ),
)
@pytest.mark.parametrize("text", ("1", "", " "), ids=("visible", "empty-bstr", "space-bstr"))
def test_native_bounds_refuse_unreadable_later_fragment_with_identity(field, value, text):
    texts = _nut_rd1()["display"]["texts"]
    texts[1]["t"] = text
    texts[1][field] = value
    with pytest.raises(RuntimeError, match=f"{_LABEL} fragment 1 ref="):
        core.measured_native_text_bounds(texts, label=_LABEL)


@pytest.mark.parametrize("reference", (1, 3), ids=("hull-overflow", "anchor-overflow"))
@pytest.mark.parametrize("text", ("later", "", " "), ids=("visible", "empty-bstr", "space-bstr"))
def test_native_bounds_refuse_nonfinite_derived_fragment_before_union(reference, text):
    texts = [_nut_rd1()["display"]["texts"][0]]
    coordinate = 1e308 if reference == 1 else -1e308
    later = _nut_text(text, (coordinate, coordinate, 0.0), 1e308)
    later.update(h=1e308, ref=reference)
    texts.append(later)
    with pytest.raises(RuntimeError, match=f"{_LABEL} fragment 1 ref={reference}"):
        core.measured_native_text_bounds(texts, label=_LABEL)


def test_measure_retains_each_disjoint_witness_interval(native_reads, witness_case):
    case = witness_case
    record = case.record
    before = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
    lines = record["display"]["lines"]
    row = lines[case.index]
    pieces = _witness_pieces(row, case.axis, ((1.0, 0.7), (0.2, 0.0), (0.5, 0.35)))
    lines[case.index:case.index + 1] = pieces
    original = copy.deepcopy(record)
    after = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)

    station, low, high = before["witnesses"][0]
    extent = high - low
    expected = (
        (station, low, low + 0.2 * extent),
        (station, low + 0.35 * extent, low + 0.5 * extent),
        (station, low + 0.7 * extent, high),
        before["witnesses"][1],
    )
    assert len(after["witnesses"]) == len(expected)
    for actual, interval in zip(after["witnesses"], expected, strict=True):
        assert actual == pytest.approx(interval)
        assert len(actual) == 3 and all(isfinite(value) for value in actual)
    assert after["tips"] == before["tips"]
    assert after["reach"] == before["reach"]
    assert after["record"] == original
    assert record == original


@pytest.mark.parametrize(
    "intervals",
    (
        ((0.0, 0.25), (0.25, 0.7), (0.7, 1.0)),
        ((1.0, 0.6), (0.6, 0.2), (0.2, 0.0)),
        ((0.8, 0.3), (1.0, 0.6), (0.4, 0.0), (0.8, 0.3), (0.2, 0.25)),
    ),
    ids=("touching-splits", "reversed-pieces", "overlaps-duplicates-nesting"),
)
def test_measure_and_assert_accept_equivalent_witness_coverage(
    native_reads, witness_case, intervals
):
    case = witness_case
    record = case.record
    before = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
    lines = record["display"]["lines"]
    lines[case.index:case.index + 1] = _witness_pieces(
        lines[case.index], case.axis, intervals
    )
    lines.reverse()
    record["display"]["arrows"].reverse()
    original = copy.deepcopy(record)
    after = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)

    assert after["witnesses"] == before["witnesses"]
    assert after["tips"] == before["tips"]
    assert after["reach"] == before["reach"]
    assert after["record"] == original
    core.assert_reference_text_stations(before, after, label=_LABEL)


@pytest.mark.parametrize("gap", (0.5 * _TOL, 1.5 * _TOL), ids=("readback", "real-gap"))
def test_witness_union_uses_existing_station_tolerance(native_reads, witness_case, gap):
    case = witness_case
    record = case.record
    before = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
    lines = record["display"]["lines"]
    row = lines[case.index]
    extent = before["witnesses"][0][2] - before["witnesses"][0][1]
    lines[case.index:case.index + 1] = _witness_pieces(
        row, case.axis, ((0.0, 0.4), (0.4 + gap / extent, 1.0))
    )
    after = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)

    if gap < _TOL:
        assert after["witnesses"] == before["witnesses"]
        core.assert_reference_text_stations(before, after, label=_LABEL)
    else:
        assert len(after["witnesses"]) == len(before["witnesses"]) + 1
        with pytest.raises(RuntimeError, match="witnesses moved"):
            core.assert_reference_text_stations(before, after, label=_LABEL)


@pytest.mark.parametrize("skew", (0.5e-7, 2e-7), ids=("collinear", "noncollinear"))
def test_measure_keeps_strict_perpendicular_collinearity(
    native_reads, witness_case, skew
):
    case = witness_case
    record = case.record
    before = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
    record["display"]["lines"][case.index][7 + case.axis] += skew
    if skew < 1e-7:
        after = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
        core.assert_reference_text_stations(before, after, label=_LABEL)
    else:
        with pytest.raises(RuntimeError, match="lost a native witness"):
            core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)


# --------------------------------------------------------------------------
# assert_reference_text_stations
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", ("tips", "witnesses"))
def test_stations_reject_drift_beyond_tolerance(key):
    original = dict(
        tips=((0.1, 0.2), (0.1, 0.204)),
        witnesses=((0.2, 0.099, 0.11), (0.204, 0.099, 0.11)),
        physical_lines=((0.1, 0.1, 0.2, 0.204),),
    )
    core.assert_reference_text_stations(original, copy.deepcopy(original), label=_LABEL)
    settled = copy.deepcopy(original)
    settled[key] = (
        tuple(value + 0.4e-5 for value in original[key][0]),
        *original[key][1:],
    )
    core.assert_reference_text_stations(original, settled, label=_LABEL)
    moved = copy.deepcopy(original)
    moved[key] = (
        tuple(value + 0.0001 for value in original[key][0]),
        *original[key][1:],
    )
    with pytest.raises(RuntimeError, match=f"{key} moved") as exc:
        core.assert_reference_text_stations(original, moved, label=_LABEL)
    assert str(exc.value).startswith(_LABEL)


def test_stations_reject_witness_run_shortening(native_reads):
    record = _recovered_head_height()
    before = core.measure_reference_text(None, _static(record), axis=1, label=_LABEL)
    record["display"]["lines"][0][4] -= 0.0001  # one witness run grows outward
    after = core.measure_reference_text(None, _static(record), axis=1, label=_LABEL)
    assert after["tips"] == before["tips"]
    with pytest.raises(RuntimeError, match="witnesses moved"):
        core.assert_reference_text_stations(before, after, label=_LABEL)


def test_stations_reject_lost_station():
    before = dict(
        tips=((0.1, 0.2), (0.1, 0.204)),
        witnesses=((0.2, 0.0, 0.1), (0.204, 0.0, 0.1)),
        physical_lines=((0.1, 0.1, 0.2, 0.204),),
    )
    after = dict(before, tips=before["tips"][:1])
    with pytest.raises(RuntimeError, match="tips moved"):
        core.assert_reference_text_stations(before, after, label=_LABEL)


def test_stations_reject_interior_gap_with_unchanged_extrema(native_reads, witness_case):
    case = witness_case
    record = case.record
    before = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
    lines = record["display"]["lines"]
    lines[case.index:case.index + 1] = _witness_pieces(
        lines[case.index], case.axis, ((0.0, 0.3), (0.6, 1.0))
    )
    after = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)

    assert after["tips"] == before["tips"]
    assert after["reach"] == before["reach"]
    assert after["witnesses"][0][1] == before["witnesses"][0][1]
    assert after["witnesses"][1][2] == before["witnesses"][0][2]
    with pytest.raises(RuntimeError, match="witnesses moved"):
        core.assert_reference_text_stations(before, after, label=_LABEL)


def test_stations_reject_same_count_moved_gap(native_reads, witness_case):
    case = witness_case
    row = case.record["display"]["lines"][case.index]
    captures = []
    for intervals in (((0.0, 0.3), (0.5, 1.0)), ((0.0, 0.4), (0.6, 1.0))):
        record = copy.deepcopy(case.record)
        record["display"]["lines"][case.index:case.index + 1] = _witness_pieces(
            row, case.axis, intervals
        )
        captures.append(
            core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
        )
    before, after = captures

    assert len(before["witnesses"]) == len(after["witnesses"]) == 3
    assert before["tips"] == after["tips"]
    assert before["reach"] == after["reach"]
    assert before["witnesses"][0][1] == after["witnesses"][0][1]
    assert before["witnesses"][1][2] == after["witnesses"][1][2]
    with pytest.raises(RuntimeError, match="witnesses moved"):
        core.assert_reference_text_stations(before, after, label=_LABEL)


@pytest.mark.parametrize("defect", ("noncollinear-connector", "off-station-line"))
def test_unrelated_ink_cannot_restore_missing_witness_coverage(
    native_reads, witness_case, defect
):
    case = witness_case
    record = case.record
    before = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)
    lines = record["display"]["lines"]
    row = lines[case.index]
    bridge = _witness_pieces(row, case.axis, ((0.3, 0.6),))[0]
    if defect == "noncollinear-connector":
        # Inside station tolerance, but NOT the stricter perpendicular test.
        bridge[7 + case.axis] += 2e-7
    else:
        bridge[4 + case.axis] += 2 * _TOL
        bridge[7 + case.axis] += 2 * _TOL
    lines[case.index:case.index + 1] = [
        *_witness_pieces(row, case.axis, ((0.0, 0.3), (0.6, 1.0))),
        bridge,
    ]
    after = core.measure_reference_text(None, _static(record), axis=case.axis, label=_LABEL)

    assert len(after["witnesses"]) == 3
    assert after["record"]["display"]["lines"] == lines
    assert after["tips"] == before["tips"]
    with pytest.raises(RuntimeError, match="witnesses moved"):
        core.assert_reference_text_stations(before, after, label=_LABEL)


# --------------------------------------------------------------------------
# shelve_reference_text
# --------------------------------------------------------------------------


def _fleet(defect=None):
    """Two short rows that must shelf (vertical recovered, horizontal actual
    nut fraction) and one long vertical row that fits its native span."""
    displays = {
        "SupplierHeadHeight": _Display(
            _recovered_head_height(), 1, defect=defect
        ),
        "RD1": _Display(_nut_rd1(), 0, attached=(_NUT_FRACTION_BAR,), defect=defect),
        "SupplierLength": _Display(_long_length(), 1),
    }
    axes = {"SupplierHeadHeight": 1, "RD1": 0, "SupplierLength": 1}
    return displays, axes


def _measure_all(displays, axes):
    return {
        name: core.measure_reference_text(None, display, axis=axes[name], label=name)
        for name, display in displays.items()
    }


def _assert_shelved(display, before, after):
    axis = display.axis
    text = after["text"]
    low = text.xmin if axis == 0 else text.ymin
    assert display.OffsetText is True
    for key in ("tips", "witnesses"):
        assert after[key] == before[key]
    # Beyond the actual outside-arrow tail, not merely the arrowhead.
    assert low - after["reach"] >= core.CLEAR_GAP_M
    assert low - after["reach"] == pytest.approx(core.CLEAR_GAP_M + core.PLACE_SETTLE_M)
    # Every physical native run clears the entire all-run font union.
    assert all(
        segment_box_distance(segment, text) >= core.CLEAR_GAP_M
        for segment in _physical_ink(after)
    )
    # The text moved along the axis only; its transverse station is kept.
    assert display.position[1 - axis] == pytest.approx(display.original_position[1 - axis])
    assert display.position[axis] != display.original_position[axis]
    assert (text.ymin if axis == 0 else text.xmin) == pytest.approx(
        before["text"].ymin if axis == 0 else before["text"].xmin
    )


def _assert_untouched(display, before, after):
    assert display.OffsetText is False
    assert display.position == display.original_position
    assert after["record"] == before["record"]


def test_shelve_moves_short_rows_beyond_actual_tails_and_keeps_long_row(native_reads):
    displays, axes = _fleet()
    before = _measure_all(displays, axes)
    nut_runs = tuple(row["t"] for row in displays["RD1"].record["display"]["texts"])
    proof = core.shelve_reference_text(
        None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
    )
    after = _measure_all(displays, axes)
    _assert_shelved(displays["SupplierHeadHeight"], before["SupplierHeadHeight"], after["SupplierHeadHeight"])
    _assert_shelved(displays["RD1"], before["RD1"], after["RD1"])
    _assert_untouched(displays["SupplierLength"], before["SupplierLength"], after["SupplierLength"])
    assert displays["SupplierHeadHeight"].enable_count == 1
    assert displays["RD1"].enable_count == 1

    # The nut's whole union, including "(" and the fraction, sits past the
    # actual right tail end plus the existing gap; the fraction bar travelled
    # with the text and is still inside its union, still in the record.
    nut = after["RD1"]
    assert nut["text"].xmin >= _NUT_TAIL_END + core.CLEAR_GAP_M
    assert nut["text"].width == pytest.approx(_NUT_UNION_WIDTH)
    assert tuple(row["t"] for row in nut["record"]["display"]["texts"]) == nut_runs
    assert "ACROSS FLATS" in nut_runs and "1" in nut_runs and "4" in nut_runs
    bar = nut["record"]["display"]["lines"][_NUT_FRACTION_BAR]
    assert nut["text"].xmin < bar[4] < bar[7] < nut["text"].xmax
    assert len(nut["record"]["display"]["lines"]) == 6
    # The nut's native line kept its y station: enabling offset mode at the
    # seeded tip-transverse anchor moved nothing.
    assert nut["tips"][0][1] == pytest.approx(0.1588138)

    proof()  # Execute the returned proof: it reacquires and re-measures.
    assert _measure_all(displays, axes) == after


def test_shelve_refuses_gap_created_by_native_shelf(native_reads, witness_case):
    case = witness_case
    display = _Display(
        case.record, case.axis, attached=(_NUT_FRACTION_BAR,) if case.axis == 0 else ()
    )
    original = list(case.record["display"]["lines"][case.index])
    move = display.SetPosition2

    def loses_interior_coverage(x, y, z):
        was_offset = display.OffsetText
        previous = display.position[case.axis]
        ok = move(x, y, z)
        if was_offset and abs(display.position[case.axis] - previous) > 0.001:
            lines = display.record["display"]["lines"]
            lines[case.index:case.index + 1] = _witness_pieces(
                original, case.axis, ((0.0, 0.3), (0.6, 1.0))
            )
        return ok

    display.SetPosition2 = loses_interior_coverage
    # The final native move still reports success and preserves both extrema.
    # A post-shelf recapture must NOT become the station proof's baseline.
    with pytest.raises(RuntimeError, match="witnesses moved"):
        core.shelve_reference_text(
            None,
            reacquire=lambda: {display.name: display},
            axes={display.name: case.axis},
            label=_LABEL,
        )


@pytest.mark.parametrize("phase", ("seed", "enable", "shelf"))
def test_shelve_refuses_physical_tail_mutation_during_each_transition(
    native_reads, physical_case, phase
):
    case = physical_case

    class TailMovingDisplay(_Display):
        def move_tail(self):
            self.record["display"]["lines"][case.index][7 + self.axis] -= 0.0001

        def SetPosition2(self, x, y, z):
            stage = "shelf" if self.OffsetText else "seed"
            result = super().SetPosition2(x, y, z)
            if stage == phase:
                self.move_tail()
            return result

        @property
        def OffsetText(self):
            return _Display.OffsetText.fget(self)

        @OffsetText.setter
        def OffsetText(self, enabled):
            _Display.OffsetText.fset(self, enabled)
            if enabled and phase == "enable":
                self.move_tail()

    display = TailMovingDisplay(
        case.record, case.axis, attached=(_NUT_FRACTION_BAR,) if case.axis == 0 else ()
    )
    with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
        core.shelve_reference_text(
            None, reacquire=lambda: {display.name: display},
            axes={display.name: case.axis}, label=_LABEL,
        )


@pytest.mark.parametrize("late_delta", (0.0001, 0.6 * _TOL), ids=("100um", "cumulative"))
def test_retained_physical_proof_uses_original_baseline_after_fragmentation(
    native_reads, physical_case, late_delta
):
    case = physical_case
    lines = case.record["display"]["lines"]
    row = list(lines[case.index])
    lines[case.index:case.index + 1] = _physical_pieces(
        row, case.axis, ((0.0, 0.3), (0.6, 1.0))
    )
    display = _Display(
        case.record, case.axis, attached=(_NUT_FRACTION_BAR,) if case.axis == 0 else ()
    )
    original = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    frozen_original = copy.deepcopy(original)
    move = display.SetPosition2

    def settles_with_small_tail_readback(x, y, z):
        was_offset = display.OffsetText
        result = move(x, y, z)
        if was_offset:
            # Accepted once against the original, NOT a new station baseline.
            display.record["display"]["lines"][case.index][4 + case.axis] -= 0.6 * _TOL
        return result

    display.SetPosition2 = settles_with_small_tail_readback
    found = {display.name: display}
    proof = core.shelve_reference_text(
        None, reacquire=lambda: dict(found), axes={display.name: case.axis}, label=_LABEL
    )
    proof()
    settled = copy.deepcopy(display.record)
    fresh = copy.copy(display)
    fresh.record = copy.deepcopy(settled)
    found[display.name] = fresh
    fresh_lines = fresh.record["display"]["lines"]
    for index in (case.index + 1, case.index):
        fresh_lines[index:index + 1] = _physical_pieces(
            fresh_lines[index], case.axis,
            ((1.0, 0.5), (0.5, 0.0), (0.2, 0.7), (0.2, 0.7)),
        )
    fresh_lines.reverse()
    fresh.record["display"]["arrows"].reverse()
    equivalent = copy.deepcopy(fresh.record)
    proof()
    assert fresh.record == equivalent
    assert original == frozen_original
    # Fresh reads still compare to the pre-seed baseline. In the cumulative
    # case both successive changes are individually within tolerance, but
    # their total displacement is not.
    fresh.record = copy.deepcopy(settled)
    fresh.record["display"]["lines"][case.index][4 + case.axis] -= late_delta
    for _ in range(2):
        with pytest.raises(RuntimeError, match="supplier reference native physical_lines moved"):
            proof()
    fresh.record = copy.deepcopy(equivalent)
    proof()
    assert original == frozen_original


def test_shelve_and_proof_preserve_original_disjoint_coverage(native_reads, witness_case):
    case = witness_case
    record = case.record
    lines = record["display"]["lines"]
    original = list(lines[case.index])
    lines[case.index:case.index + 1] = _witness_pieces(
        original, case.axis, ((0.0, 0.3), (0.6, 1.0))
    )
    display = _Display(
        record, case.axis, attached=(_NUT_FRACTION_BAR,) if case.axis == 0 else ()
    )
    found = {display.name: display}
    before = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    proof = core.shelve_reference_text(
        None, reacquire=lambda: dict(found), axes={display.name: case.axis}, label=_LABEL
    )
    after = core.measure_reference_text(None, display, axis=case.axis, label=_LABEL)
    _assert_shelved(display, before, after)
    settled_record = copy.deepcopy(display.record)

    replacement = copy.copy(display)
    replacement.record = copy.deepcopy(settled_record)
    found[display.name] = replacement
    lines = replacement.record["display"]["lines"]
    lines[case.index:case.index + 2] = _witness_pieces(
        original, case.axis, ((0.3, 0.1), (0.1, 0.0), (0.6, 0.8), (1.0, 0.8))
    )
    lines.reverse()
    replacement.record["display"]["arrows"].reverse()
    equivalent_record = copy.deepcopy(replacement.record)
    proof()
    assert replacement.record == equivalent_record

    replacement.record = copy.deepcopy(settled_record)
    replacement.record["display"]["lines"][case.index:case.index + 2] = _witness_pieces(
        original, case.axis, ((0.0, 0.4), (0.7, 1.0))
    )
    # Same interval count and extrema, but the original gap has moved.
    for _ in range(2):
        with pytest.raises(RuntimeError, match="witnesses moved"):
            proof()
    replacement.record = copy.deepcopy(equivalent_record)
    proof()


def test_shelve_force_shelves_long_row_too(native_reads):
    displays, axes = _fleet()
    before = _measure_all(displays, axes)
    length = displays["SupplierLength"]
    extent = before["SupplierLength"]["text"].height
    span = before["SupplierLength"]["tips"][1][1] - before["SupplierLength"]["tips"][0][1]
    assert extent + 2 * (core.CLEAR_GAP_M + core.PLACE_SETTLE_M) <= span
    proof = core.shelve_reference_text(
        None,
        reacquire=lambda: dict(displays),
        axes=axes,
        label=_LABEL,
        force=("SupplierLength",),
    )
    after = _measure_all(displays, axes)
    for name in displays:
        _assert_shelved(displays[name], before[name], after[name])
    # Forced long row: beyond its upper arrowhead base, not a text-height guess.
    assert after["SupplierLength"]["reach"] == pytest.approx(0.260 + 0.003556)
    assert length.enable_count == 1
    proof()


def test_shelve_with_nothing_selected_only_measures(native_reads):
    displays = {"SupplierLength": _Display(_long_length(), 1)}
    axes = {"SupplierLength": 1}
    before = _measure_all(displays, axes)
    proof = core.shelve_reference_text(
        None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
    )
    after = _measure_all(displays, axes)
    _assert_untouched(displays["SupplierLength"], before["SupplierLength"], after["SupplierLength"])
    proof()
    # The unselected row is still station-proven afterwards.
    displays["SupplierLength"].shift_stations(1, 0.0001)
    with pytest.raises(RuntimeError, match="moved"):
        proof()


@pytest.mark.parametrize(
    ("defect", "message"),
    (
        ("ignored-seed", "did not settle"),
        ("refused-seed", "cannot"),
        ("refused-shelf", "cannot"),
        ("ignored-shelf", "crowds"),
        ("station-drift", "moved"),
    ),
)
def test_shelve_rejects_native_refusal_no_op_and_drift(native_reads, defect, message):
    displays, axes = _fleet(defect)
    with pytest.raises(RuntimeError, match=message):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
        )


def test_shelve_refuses_shelf_when_offset_mode_does_not_take(native_reads):
    # The native setter answers nothing; read-back still says False. The
    # core must refuse BEFORE the shelf SetPosition2, which would otherwise
    # drag the line and witnesses along with the text.
    displays, axes = _fleet()
    nut = displays["RD1"]
    nut.defect = "ignored-offset"
    before = core.measure_reference_text(None, nut, axis=0, label="RD1")
    with pytest.raises(RuntimeError, match="offset|enable"):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
        )
    assert nut.OffsetText is False
    after = core.measure_reference_text(None, nut, axis=0, label="RD1")
    core.assert_reference_text_stations(before, after, label="RD1")
    # Seeded at the tips' transverse station, never shelved along the axis.
    assert nut.position[0] == pytest.approx(nut.original_position[0])
    assert nut.position[1] == pytest.approx(before["tips"][0][1])


def test_shelve_requires_offset_text_off_before_seeding(native_reads):
    displays, axes = _fleet()
    displays["RD1"]._offset = True
    with pytest.raises(RuntimeError, match="seed"):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
        )


def test_shelve_requires_a_settled_anchor_before_enabling(native_reads):
    # Native SetPosition2 answers True but the read-back lands elsewhere.
    displays, axes = _fleet()
    nut = displays["RD1"]
    settle = nut.SetPosition2

    def wobbly(x, y, z):
        ok = settle(x, y, z)
        if not nut.OffsetText:
            nut.position = (x, y + 0.0001, z)
            nut.record["pos"] = nut.position
        return ok

    nut.SetPosition2 = wobbly
    with pytest.raises(RuntimeError, match="did not settle"):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
        )


def test_shelve_refuses_when_enabling_offset_mode_moves_stations(native_reads):
    # Native OffsetText enable drags the line along the axis: the core must
    # refuse at that read-back, before the final along-axis text move.
    displays, axes = _fleet()
    nut = displays["RD1"]
    nut.defect = "enable-drifts-stations"
    with pytest.raises(RuntimeError, match="moved"):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
        )
    assert nut.position[0] == pytest.approx(nut.original_position[0])
    assert nut.position[1] == pytest.approx(0.1588138)


def _boundary_row(span):
    """A vertical 3.5 mm native row centred on the origin inside ``span`` of
    outside-arrow dimension line: tails past each tip, witnesses on each
    station. Centred at 0.0 the font box height and the tip span are exact
    doubles (2 * h/2, 2 * span/2), so the boundary comparison is exact."""
    record = _recovered_head_height()
    record["name"] = "SupplierBoundary"
    text = record["display"]["texts"][0]
    text["pos"] = (-text["w"] / 2, -text["h"] / 2, 0.0)
    low, high = -span / 2, span / 2
    record["pos"] = (0.0, 0.0, 0.0)
    record["display"]["lines"] = [
        [0, 0, 0, 0, 0.0106, low, 0, -0.0010, low, 0],
        [0, 0, 0, 0, 0.0106, high, 0, -0.0010, high, 0],
        [0, 0, 0, 0, 0.0, low, 0, 0.0, low - 0.00635, 0],
        [0, 0, 0, 0, 0.0, high, 0, 0.0, high + 0.00635, 0],
        [0, 0, 0, 0, 0.0, low, 0, 0.0, high, 0],
    ]
    record["display"]["arrows"] = [
        [0.0, low, 0, 0, -1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
        [0.0, high, 0, 0, 1, 0, 0.003556, 0.000762, 0, 0, 0, 1],
    ]
    return record


@pytest.mark.parametrize(
    ("span_mm", "shelved"),
    ((7.8, True), (7.9, False), (7.9375, False), (8.0, False), (8.331, False)),
    ids=("below", "exact", "near-boundary", "above", "wide"),
)
def test_shelve_default_rule_is_full_extent_plus_both_gaps_on_each_side(
    native_reads, span_mm, shelved
):
    # 3.5 mm font: the row stays on its line only when the whole extent plus
    # gap and settle on BOTH sides fit the arrow span, i.e. 7.9 mm exactly.
    # A missing or halved allowance keeps the 7.8 mm row; a strict inequality
    # shelves the exact one.
    display = _Display(_boundary_row(span_mm / 1000), 1)
    axes = {"SupplierBoundary": 1}
    before = core.measure_reference_text(None, display, axis=1, label="row")
    extent = before["text"].height
    span = before["tips"][1][1] - before["tips"][0][1]
    assert extent == 0.0035
    assert span == span_mm / 1000
    if span_mm == 7.9:
        assert extent + 0.0044 == span  # exact doubles, not approx
    proof = core.shelve_reference_text(
        None, reacquire=lambda: {"SupplierBoundary": display}, axes=axes, label="row"
    )
    after = core.measure_reference_text(None, display, axis=1, label="row")
    if shelved:
        _assert_shelved(display, before, after)
    else:
        _assert_untouched(display, before, after)
    proof()


@pytest.mark.parametrize("axis", (0, 1), ids=("horizontal", "vertical"))
@pytest.mark.parametrize("reference", range(6))
@pytest.mark.parametrize("angle", (0.0, pi / 2, pi / 6), ids=("level", "vertical", "oblique"))
@pytest.mark.parametrize("origin", ((0.0, 0.0), (0.041, -0.063)), ids=("origin", "translated"))
@pytest.mark.parametrize("margin", (-0.0001, 0.0001), ids=("must-shelf", "fits"))
def test_shelve_fit_boundary_uses_physical_anchored_rotated_extent(
    native_reads, axis, reference, angle, margin, origin
):
    width, height = 0.0035, 0.0025
    extent_x = width * abs(cos(angle)) + height * abs(sin(angle))
    extent_y = width * abs(sin(angle)) + height * abs(cos(angle))
    extent = (extent_x, extent_y)[axis]
    span = extent + 2 * (core.CLEAR_GAP_M + core.PLACE_SETTLE_M) + margin
    record = _boundary_row(span)
    if axis == 0:
        for line in record["display"]["lines"]:
            line[4], line[5] = line[5], line[4]
            line[7], line[8] = line[8], line[7]
        for arrow in record["display"]["arrows"]:
            arrow[0], arrow[1] = arrow[1], arrow[0]
            arrow[3], arrow[4] = arrow[4], arrow[3]
    record["pos"] = (*origin, record["pos"][2])
    for line in record["display"]["lines"]:
        for coordinate in (0, 1):
            line[4 + coordinate] += origin[coordinate]
            line[7 + coordinate] += origin[coordinate]
    for arrow in record["display"]["arrows"]:
        arrow[0] += origin[0]
        arrow[1] += origin[1]
    row = record["display"]["texts"][0]
    row["w"], row["h"] = width, height
    _centre_native_fragment(row, reference=reference, angle=angle, centre=origin)
    original = copy.deepcopy(record)
    display = _Display(record, axis)
    proof = core.shelve_reference_text(
        None, reacquire=lambda: {display.name: display}, axes={display.name: axis}, label=_LABEL
    )
    after = core.measure_reference_text(None, display, axis=axis, label=_LABEL)

    assert display.OffsetText is (margin < 0.0)
    if margin < 0.0:
        # Compute the REAL lower edge from the known physical text centre,
        # not from the core's claimed bounds. Upper/right/centre references
        # cannot win a false-clear proof by measuring their anchor as ink.
        physical_low = display.position[axis] - extent / 2
        assert physical_low - after["reach"] >= core.CLEAR_GAP_M
        assert physical_low - after["reach"] == pytest.approx(
            core.CLEAR_GAP_M + core.PLACE_SETTLE_M
        )
        assert (after["text"].xmin if axis == 0 else after["text"].ymin) == pytest.approx(
            physical_low
        )
    else:
        assert display.position == display.original_position
        assert display.record == original
    assert row["ref"] == reference
    assert row["ang"] == angle
    settled_record = copy.deepcopy(display.record)
    proof()
    assert display.record == settled_record


@pytest.mark.parametrize(
    ("axes", "force", "message"),
    (
        ({}, (), "axes"),
        ({"RD1": True}, (), r"ax(?:is|es)"),
        ({"RD1": 2}, (), r"ax(?:is|es)"),
        ({"RD1": -1}, (), r"ax(?:is|es)"),
        ({"RD1": 0}, ("SupplierLength",), "force"),
    ),
)
def test_shelve_rejects_invalid_axes_and_force(native_reads, axes, force, message):
    displays, _axes = _fleet()
    with pytest.raises(ValueError, match=message):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL, force=force
        )
    assert all(display.OffsetText is False for display in displays.values())
    assert all(
        display.position == display.original_position for display in displays.values()
    )


@pytest.mark.parametrize("phase", ("initial", "seeded", "enabled", "shelved"))
def test_shelve_requires_every_named_display_each_phase(native_reads, phase):
    # Initial measurement plus the three batched transition read-backs each
    # reacquire; a handle lost at any of them refuses the whole shelf.
    displays, axes = _fleet()
    reads = []

    def reacquire():
        reads.append(1)
        found = dict(displays)
        stage = {"initial": 1, "seeded": 2, "enabled": 3, "shelved": 4}[phase]
        if len(reads) >= stage:
            found["RD1"] = None
        return found

    with pytest.raises(RuntimeError, match="RD1"):
        core.shelve_reference_text(None, reacquire=reacquire, axes=axes, label=_LABEL)


def test_proof_requires_every_named_display(native_reads):
    displays, axes = _fleet()
    found = dict(displays)
    proof = core.shelve_reference_text(
        None, reacquire=lambda: dict(found), axes=axes, label=_LABEL
    )
    proof()
    del found["RD1"]
    with pytest.raises(RuntimeError, match="RD1"):
        proof()


def test_shelve_requires_every_axis_name_in_reacquire(native_reads):
    displays, axes = _fleet()
    del displays["RD1"]
    with pytest.raises(RuntimeError, match="RD1"):
        core.shelve_reference_text(
            None, reacquire=lambda: dict(displays), axes=axes, label=_LABEL
        )


# --------------------------------------------------------------------------
# same-checkpoint raw records for the caller's read-only layout audit
# --------------------------------------------------------------------------


@pytest.fixture
def native_record_checkpoints(native_reads, monkeypatch):
    found, axes = _fleet()
    case = SimpleNamespace(
        found=found,
        axes={name: axes[name] for name in ("SupplierLength", "SupplierHeadHeight", "RD1")},
        generation=0,
        source_valid=True,
        dumps=[],
        audits=[],
        layout_error=RuntimeError("long supplier reference text crosses native line"),
    )
    dump = core._dump_annotation

    def reacquire():
        if not case.source_valid:
            raise RuntimeError("supplier source identity changed")
        case.generation += 1
        fresh = {}
        for name, display in case.found.items():
            replacement = copy.copy(display)
            replacement.record = copy.deepcopy(display.record)
            fresh[name] = replacement
        case.found.clear()
        case.found.update(fresh)
        return dict(fresh)

    def native_dump(reader, annotation):
        assert annotation is case.found[annotation.name]
        record = dump(reader, annotation)
        case.dumps.append((case.generation, record["name"], record))
        return record

    def primitive(value):
        if isinstance(value, dict):
            assert all(isinstance(key, str) for key in value)
            for child in value.values():
                primitive(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                primitive(child)
        else:
            assert type(value) in (str, int, float, bool, type(None))

    def audit_records(records):
        current = [
            (name, record) for generation, name, record in case.dumps
            if generation == case.generation
        ]
        assert len(current) == len(case.axes)
        assert set(records) == set(case.axes)
        for name, record in current:
            assert records[name] is record  # No second read or expensive raw copy.
        primitive(records)
        case.audits.append((case.generation, records))

        # A real caller-only layout constraint: the long row is not shelved,
        # so its unchanged stations alone cannot prove its text clear.
        record = records["SupplierLength"]
        ink = annotation_geometry(
            record, owner="SupplierLength", advance=calibrate_sheet_advance((record,))
        )
        assert ink is not None
        text = _text_box(record)
        if any(
            segment.role == "dim-line" and segment_box_distance(segment, text) == 0.0
            for segment in ink.segments
        ):
            raise case.layout_error

    monkeypatch.setattr(core, "_dump_annotation", native_dump)
    case.reacquire = reacquire
    case.audit_records = audit_records
    return case


def test_record_audit_reuses_fresh_checkpoint_and_releases_old_native_handles(
    native_record_checkpoints,
):
    case = native_record_checkpoints
    proof = core.shelve_reference_text(
        None, reacquire=case.reacquire, axes=case.axes, label=_LABEL,
        audit_records=case.audit_records,
    )
    assert len(case.audits) == 1
    # Existing four batched inventories: full measurement, anchor read-back,
    # enabled-mode measurement, and final proof. The audit adds none.
    assert case.generation == 4
    assert len(case.dumps) == 2 * len(case.axes) + 2
    initial_generation, initial_records = case.audits[0]
    initial_text_count = len(initial_records["RD1"]["display"]["texts"])
    previous_handles = [weakref.ref(display) for display in case.found.values()]

    texts = case.found["RD1"].record["display"]["texts"]
    far = max(row["pos"][0] + row["w"] for row in texts)
    texts.append(_nut_text("later", (far + 0.001, texts[0]["pos"][1], 0.0), 0.004))
    dumps_before = len(case.dumps)
    assert proof() is None
    generation, records = case.audits[-1]
    assert len(case.audits) == 2
    assert generation == initial_generation + 1
    assert len(case.dumps) - dumps_before == len(case.axes)
    assert records is not initial_records
    assert all(records[name] is not initial_records[name] for name in case.axes)
    assert len(records["RD1"]["display"]["texts"]) == initial_text_count + 1
    assert len(initial_records["RD1"]["display"]["texts"]) == initial_text_count
    gc.collect()
    assert all(handle() is None for handle in previous_handles)


@pytest.mark.parametrize("phase", ("initial", "later"))
def test_record_audit_propagates_native_layout_failure(native_record_checkpoints, phase):
    case = native_record_checkpoints
    if phase == "later":
        proof = core.shelve_reference_text(
            None, reacquire=case.reacquire, axes=case.axes, label=_LABEL,
            audit_records=case.audit_records,
        )
    row = case.found["SupplierLength"].record["display"]["texts"][0]
    row["pos"] = (row["pos"][0], 0.2255, row["pos"][2])
    with pytest.raises(RuntimeError, match="text crosses native line") as error:
        if phase == "initial":
            core.shelve_reference_text(
                None, reacquire=case.reacquire, axes=case.axes, label=_LABEL,
                audit_records=case.audit_records,
            )
        else:
            proof()
    assert error.value is case.layout_error
    assert len(case.audits) == (1 if phase == "initial" else 2)


@pytest.mark.parametrize(
    ("defect", "message"),
    (
        ("source", "source identity"),
        ("inventory", "inventory changed"),
        ("station", "native tips moved"),
        ("gap", "native witnesses moved"),
        ("shelf", "crowds its native line"),
        ("offset", "crowds its native line"),
        ("transverse", "transverse position moved"),
        ("fragment", "native reference position"),
    ),
)
def test_record_audit_waits_for_every_strict_native_guard(
    native_record_checkpoints, defect, message
):
    case = native_record_checkpoints
    proof = core.shelve_reference_text(
        None, reacquire=case.reacquire, axes=case.axes, label=_LABEL,
        audit_records=case.audit_records,
    )
    assert len(case.audits) == 1
    display = case.found["RD1"]
    if defect == "source":
        case.source_valid = False
    elif defect == "inventory":
        del case.found["SupplierLength"]
    elif defect == "station":
        display.shift_stations(0, 0.0001)
    elif defect == "gap":
        lines = display.record["display"]["lines"]
        lines[1:2] = _witness_pieces(lines[1], 0, ((0.0, 0.3), (0.6, 1.0)))
    elif defect == "shelf":
        display.move_text(-0.1, 0.0)
    elif defect == "offset":
        display._offset = False
    elif defect == "transverse":
        display.move_text(0.0, 0.0001)
        x, y, z = display.position
        display.position = (x, y + 0.0001, z)
        display.record["pos"] = display.position
    else:
        display.record["display"]["texts"][1]["ref"] = 6
    with pytest.raises(RuntimeError, match=message):
        proof()
    assert len(case.audits) == 1


# --------------------------------------------------------------------------
# returned proof: reacquiring, read-only, late native mutation
# --------------------------------------------------------------------------


@pytest.fixture
def shelved(native_reads):
    displays, axes = _fleet()
    found = dict(displays)
    proof = core.shelve_reference_text(
        None, reacquire=lambda: dict(found), axes=axes, label=_LABEL
    )
    proof()
    return SimpleNamespace(displays=displays, found=found, axes=axes, proof=proof)


def _recaptured(case, name):
    """A fresh native handle for ``name`` with its own record copy, as a
    later reacquire would return: the proof must measure this one."""
    old = case.displays[name]
    replacement = copy.copy(old)
    replacement.record = copy.deepcopy(old.record)
    case.found[name] = replacement
    return replacement


@pytest.mark.parametrize("name", ("SupplierHeadHeight", "RD1", "SupplierLength"))
def test_proof_rejects_late_interior_gap_on_every_measured_row(shelved, name):
    replacement = _recaptured(shelved, name)
    index = 1 if name == "RD1" else 0
    lines = replacement.record["display"]["lines"]
    lines[index:index + 1] = _witness_pieces(
        lines[index], replacement.axis, ((0.0, 0.3), (0.6, 1.0))
    )
    for _ in range(2):
        with pytest.raises(RuntimeError, match="witnesses moved"):
            shelved.proof()


def test_proof_reacquires_and_rejects_text_back_on_its_line(shelved):
    replacement = _recaptured(shelved, "SupplierHeadHeight")
    replacement.record["display"]["texts"][0]["pos"] = (0.0916157, 0.232235, 0)
    with pytest.raises(RuntimeError, match="crowds"):
        shelved.proof()


def test_proof_rejects_offset_mode_dropped(shelved):
    replacement = _recaptured(shelved, "RD1")
    replacement._offset = False
    with pytest.raises(RuntimeError, match="crowds"):
        shelved.proof()


@pytest.mark.parametrize("name", ("SupplierHeadHeight", "RD1", "SupplierLength"))
def test_proof_rejects_late_station_drift_on_every_measured_row(shelved, name):
    replacement = _recaptured(shelved, name)
    replacement.shift_stations(replacement.axis, 0.0001)
    with pytest.raises(RuntimeError, match="moved"):
        shelved.proof()


def test_proof_rejects_late_transverse_drift(shelved):
    # The native line and witnesses stay put; the text block (with its
    # attached fraction bar) and the annotation position creep across the
    # line. Station proof passes; the transverse proof must refuse it.
    replacement = _recaptured(shelved, "RD1")
    stations = core.measure_reference_text(None, replacement, axis=0, label="RD1")

    def creep(delta):
        replacement.move_text(0.0, delta)
        x, y, z = replacement.position
        replacement.position = (x, y + delta, z)
        replacement.record["pos"] = replacement.position

    creep(2e-5)
    drifted = core.measure_reference_text(None, replacement, axis=0, label="RD1")
    core.assert_reference_text_stations(stations, drifted, label="RD1")
    with pytest.raises(RuntimeError, match="transverse"):
        shelved.proof()
    creep(-2e-5 + 0.5e-5)
    shelved.proof()


def test_proof_rejects_late_wider_font_crowding_the_tail(shelved):
    # A re-rendered nut row prints wider: SolidWorks centres the row, so
    # the run's start moves back toward the tail by half the growth. Growth
    # away from the tail alone is fine; growth that eats the gap is not.
    replacement = _recaptured(shelved, "RD1")
    flats = replacement.record["display"]["texts"][4]
    flats["w"] += 0.001
    shelved.proof()
    x, y, z = flats["pos"]
    flats["pos"] = (x - core.CLEAR_GAP_M, y, z)
    flats["w"] += 2 * core.CLEAR_GAP_M
    with pytest.raises(RuntimeError, match="crowds"):
        shelved.proof()


def test_proof_rejects_late_extra_fragment_crowding_the_tail(shelved):
    replacement = _recaptured(shelved, "RD1")
    texts = replacement.record["display"]["texts"]
    reach = _NUT_TAIL_END
    texts.insert(0, _nut_text("Ø", (reach + core.CLEAR_GAP_M / 2, texts[0]["pos"][1], texts[0]["pos"][2]), 0.0025))
    with pytest.raises(RuntimeError, match="crowds"):
        shelved.proof()


def test_proof_accepts_late_fragment_beyond_the_gap(shelved):
    replacement = _recaptured(shelved, "RD1")
    texts = replacement.record["display"]["texts"]
    far = max(row["pos"][0] + row["w"] for row in texts)
    texts.append(_nut_text("NOM", (far + 0.001, texts[0]["pos"][1], texts[0]["pos"][2]), 0.008))
    shelved.proof()


def test_proof_refuses_late_unknown_fragment_anchor(shelved):
    replacement = _recaptured(shelved, "RD1")
    replacement.record["display"]["texts"][1]["ref"] = 6
    with pytest.raises(RuntimeError, match="reference|fragment"):
        shelved.proof()


def test_proof_rejects_late_unmeasured_fragment(shelved):
    replacement = _recaptured(shelved, "RD1")
    replacement.record["display"]["texts"][2]["w"] = 0.0
    with pytest.raises(RuntimeError, match="native size"):
        shelved.proof()


@pytest.mark.parametrize(
    "defect", ("longest-pos-x-nan", "longest-pos-y-inf", "angle-nan", "missing-pos")
)
def test_proof_rejects_late_non_finite_longest_fragment(shelved, defect):
    # A NaN start on the widest run would vanish inside min()/max() and leave
    # a plausible union; the proof must refuse the recapture outright.
    replacement = _recaptured(shelved, "RD1")
    _corrupt_text(replacement.record["display"]["texts"][4], defect)
    with pytest.raises(RuntimeError, match="finite|native|unreadable"):
        shelved.proof()


def _corrupt_text(row, defect):
    x, y, z = row["pos"]
    if defect == "longest-pos-x-nan":
        row["pos"] = (float("nan"), y, z)
    elif defect == "longest-pos-y-inf":
        row["pos"] = (x, float("inf"), z)
    elif defect == "angle-nan":
        row["ang"] = float("nan")
    elif defect == "missing-pos":
        row["pos"] = (x, y)
    else:
        raise AssertionError(defect)


def test_proof_rejects_lost_witness_on_unselected_row(shelved):
    replacement = _recaptured(shelved, "SupplierLength")
    del replacement.record["display"]["lines"][0]
    with pytest.raises(RuntimeError, match="witness"):
        shelved.proof()


def test_proof_never_moves_enables_or_rebuilds(shelved, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("proof must be read-only")

    class _ReadOnly(_Display):
        OffsetText = property(
            lambda self: self._offset,
            lambda self, _enabled: refuse(),
        )

    monkeypatch.setattr(core, "rebuild_drawing", refuse)
    for name in shelved.displays:
        replacement = _recaptured(shelved, name)
        replacement.__class__ = _ReadOnly
        replacement.SetPosition2 = refuse
        replacement.shift_stations = refuse
    offsets = {name: d.OffsetText for name, d in shelved.found.items()}
    positions = {name: d.position for name, d in shelved.found.items()}
    shelved.proof()
    assert {name: d.OffsetText for name, d in shelved.found.items()} == offsets
    assert {name: d.position for name, d in shelved.found.items()} == positions
    assert all(isfinite(v) for position in positions.values() for v in position)
