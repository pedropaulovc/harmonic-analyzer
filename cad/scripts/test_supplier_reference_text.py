"""Offline behavior of the measured-native reference-text shelf core.

Every fixture is a native-shaped audit record (the layout-audit dump shape):
the recovered clamp SupplierHeadHeight primitives and the actual jam-nut RD1
across-flats row from the 2026-10-22 rolling-main layout audit. No COM, no
source-feature inventory, no callback bookkeeping: only measured geometry,
read-back behavior and late native mutation.
"""

from __future__ import annotations

import copy
from math import isfinite
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


# --------------------------------------------------------------------------
# assert_reference_text_stations
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", ("tips", "witnesses"))
def test_stations_reject_drift_beyond_tolerance(key):
    original = dict(
        tips=((0.1, 0.2), (0.1, 0.204)),
        witnesses=((0.2, 0.099, 0.11), (0.204, 0.099, 0.11)),
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
    before = dict(tips=((0.1, 0.2), (0.1, 0.204)), witnesses=((0.2, 0.0, 0.1), (0.204, 0.0, 0.1)))
    after = dict(tips=before["tips"][:1], witnesses=before["witnesses"])
    with pytest.raises(RuntimeError, match="tips moved"):
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
