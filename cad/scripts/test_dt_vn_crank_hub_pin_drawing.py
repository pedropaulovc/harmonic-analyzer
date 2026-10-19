"""Offline release contracts for the MHA-DT-VN-59 axial arm-to-hub seam pin."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import dt_crank_hub_geometry as geometry
import dt_vn_crank_hub_pin_native as pin_native
import dt_vn_crank_hub_pin_spec as pin_spec
import draw_dt_vn_crank_hub_pin as drawing
from _drawing_edges import ViewEdge, ViewEdges
from _drawing_registry import DRAWINGS_BY_NAME


def test_pin_length_is_half_the_shared_arm_thickness() -> None:
    assert pin_spec.PIN_LEN == geometry.ARM_THICKNESS / 2.0 == 4.0


def test_six_oclock_seam_leaves_the_u27_web_without_a_matched_check() -> None:
    assert geometry.HUB_SEAT_DIA_MIN_GENERAL == pytest.approx(18.6)
    assert geometry.AXIAL_PIN_DIA_STOCK_MAX == pytest.approx(4.012)
    assert geometry.HUB_BORE_DIA_MAX == pytest.approx(9.58)
    assert geometry.SEAM_WEB_WORST_MM >= geometry.WALL_TARGET_MM
    assert "DOWEL STOCK" in pin_spec.DRAWING_NOTES
    assert len(pin_spec.DRAWING_NOTES.splitlines()) <= 4


def test_pull_thread_is_unified_through_with_distinct_nominal_walls() -> None:
    assert pin_spec.PULL_THREAD == "#0-80"
    assert pin_spec.PULL_THREAD_TPI == 80
    assert pin_spec.PULL_THREAD_MAJOR_IN == 0.060
    assert pin_spec.PULL_THREAD_TAP_DRILL_IN == 0.0465
    assert pin_spec.PULL_THREAD_TAP_DRILL_DESIGNATION == "#56"
    assert pin_spec.PULL_THREAD_MAJOR == pytest.approx(1.524)
    assert pin_spec.PULL_THREAD_TAP_DRILL == pytest.approx(1.1811)
    assert pin_spec.PULL_THREAD_LEN == pin_spec.PIN_LEN == 4.0
    assert pin_spec.PULL_THREAD_NOMINAL_LENGTH_DIAMETERS == pytest.approx(4.0 / 1.524)
    assert pin_spec.PULL_THREAD_TAP_DRILL_WALL == pytest.approx(1.40945)
    assert pin_spec.PULL_THREAD_MAJOR_WALL == pytest.approx(1.238)
    assert pin_spec.PULL_THREAD_TAP_DRILL_WALL > pin_spec.PULL_THREAD_MAJOR_WALL
    assert pin_spec.PULL_THREAD_HOLE.kind == "tapped"
    assert pin_spec.PULL_THREAD_HOLE.size == pin_spec.PULL_THREAD
    assert pin_spec.PULL_THREAD_HOLE.end == "through_all"
    assert pin_spec.PULL_THREAD_HOLE.thread_class == "2B"
    assert pin_spec.PULL_THREAD_HOLE.overrides_mm == {
        "ThruTapDrillDiameter": pin_spec.PULL_THREAD_TAP_DRILL
    }
    # Rule 7: the thread is a view callout, and notes carry no method/sizes.
    assert "#0-80" not in pin_spec.DRAWING_NOTES
    assert "O'CLOCK" not in pin_spec.DRAWING_NOTES
    assert "DRILL" not in pin_spec.DRAWING_NOTES


def test_pull_thread_rule18_full_engagement_uses_printed_worst_case() -> None:
    import _config
    from _printed_tolerance import printed_band_mm

    places = pin_spec.DRAWING_PRECISION["PinProfile"]["PinLen"]
    assert places == 1
    band = printed_band_mm(places)
    mouth_break = float(_config.title_block("edge_break")["chamfer_max_mm"])
    length_min = pin_spec.PIN_LEN - band
    pitch = 25.4 / pin_spec.PULL_THREAD_TPI
    full_thread = length_min - 2.0 * mouth_break - pitch
    required = 1.5 * pin_spec.PULL_THREAD_MAJOR
    assert band == pytest.approx(0.8)
    assert length_min == pytest.approx(3.2)
    assert mouth_break == pytest.approx(0.25)
    assert pitch == pytest.approx(0.3175)
    assert full_thread == pytest.approx(2.3825)
    assert required == pytest.approx(2.286)
    assert pin_spec.PULL_THREAD_MIN_FULL_DIAMETERS == 1.5
    assert pin_spec.PIN_LEN_MIN_MM == pytest.approx(length_min)
    assert pin_spec.PULL_THREAD_FULL_PROFILE_WORST_MM == pytest.approx(full_thread)
    assert pin_spec.PULL_THREAD_FULL_PROFILE_REQUIRED_MM == pytest.approx(required)
    assert full_thread >= required
    assert pin_spec.PULL_THREAD_FULL_PROFILE_MARGIN_MM == pytest.approx(0.0965)


def test_pull_thread_uses_supported_native_inch_factory_contract() -> None:
    from _holes import _KINDS, _standard, _through_tap_metadata

    hole = pin_spec.PULL_THREAD_HOLE
    assert _standard(hole.kind) == 0  # swStandardAnsiInch
    assert _KINDS[hole.kind] == (4, 27)  # swWzdTap, AnsiInchTappedHole
    assert _through_tap_metadata(hole) == [
        ("ThreadClass", "2B"), ("ThreadEndCondition", 1)
    ]


def test_pw01_accepts_only_this_computed_nominal_wall() -> None:
    import _config
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(CAD_ROOT / "config", "vn_crank_hub_pin", "part")
    assert (entry.id, entry.kind) == ("PW-01", "minor")
    assert pin_spec.PULL_THREAD_HOLE.size + " UNF" in entry.where
    assert "MHA-VN-029 only" in entry.where
    assert f"{pin_spec.PULL_THREAD_MAJOR_WALL:.3f} mm" in entry.finding
    assert pin_spec.PULL_THREAD_WALL_CALLOUT in entry.finding
    assert entry.reason.startswith("OWNER ACCEPTED 2026-10-19:")
    assert f"{pin_spec.PULL_THREAD_MAJOR_WALL:.3f} mm nominal" in entry.reason
    assert "not a minimum-wall guarantee" in entry.reason
    assert "not a guaranteed full-profile engagement" in entry.reason
    assert "1.0 mm" not in entry.reason
    process = _config.parts("vn-crank-hub-pin")["process"]
    assert pin_spec.PULL_THREAD_HOLE.size + " UNF" in process
    assert "#56 tap drill" in process


def test_wall_fact_uses_nominal_major_wall_not_tap_drill_wall() -> None:
    nominal_major_wall = (pin_spec.PIN_DIA - pin_spec.PULL_THREAD_MAJOR) / 2.0
    assert pin_spec.PULL_THREAD_MAJOR_WALL == nominal_major_wall
    assert pin_spec.PULL_THREAD_WALL_CALLOUT == (
        f"THREAD-MAJOR WALL {nominal_major_wall:.2f} NOM"
    )
    assert pin_spec.PULL_THREAD_WALL_CALLOUT == "THREAD-MAJOR WALL 1.24 NOM"
    assert "MIN" not in pin_spec.PULL_THREAD_WALL_CALLOUT
    assert nominal_major_wall == pytest.approx(1.238)


def _callout_text(definitions: dict[int, str], part: int) -> str:
    """Synthetic repo-contract layouts, not observed native pin lane data."""
    if part in (5, 6, 7, 8):
        return definitions[part]
    return (
        definitions[part + 4]
        .replace("<hw-threaddesc>", "#0-80")
        .replace("<hw-thrutapdrldia>", "1.1811")
        .replace("<hw-threadclass>", "2B")
        .replace("<hw-thru>", "THRU ALL")
        .replace("<HW-THRUTAPDRLDIA>", "1.1811")
        .replace("<HW-THRU>", "THRU ALL")
    )


@pytest.mark.parametrize("below", ["", "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>"])
def test_wall_fact_appends_without_replacing_native_thread_or_drill(
    monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definitions = {
        5: "<hw-threaddesc> UNF - <hw-threadclass>",
        6: " <hw-thru>",
        7: "",
        8: below,
    }
    original = dict(definitions)

    def set_text(part, text):
        # Native API's writable below lane maps to definition lane 8.
        assert part == 4
        definitions[8] = text

    display = SimpleNamespace(
        GetText=lambda part: _callout_text(definitions, part),
        SetText=set_text,
    )
    drawing._append_pull_thread_wall(display)
    assert {part: definitions[part] for part in (5, 6, 7)} == {
        part: original[part] for part in (5, 6, 7)
    }
    expected = "\n".join(filter(None, (below, pin_spec.PULL_THREAD_WALL_CALLOUT)))
    assert definitions[8] == expected
    assert pin_spec.PULL_THREAD_WALL_CALLOUT in display.GetText(4)
    assert display.GetText(1) == "#0-80 UNF - 2B"
    assert display.GetText(4) == _callout_text({**original, 8: expected}, 4)


@pytest.mark.parametrize("drill_part", [5, 6, 7, 8])
@pytest.mark.parametrize("uppercase", [False, True])
def test_numbered_drill_preserves_all_native_fields_and_logs_originals(
    monkeypatch: pytest.MonkeyPatch, drill_part: int, uppercase: bool
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    # Exercise synthetic lane permutations, not a claimed native pin layout.
    thread_part = 7 if drill_part == 5 else 5
    definitions = {part: "" for part in (5, 6, 7, 8)}
    definitions[thread_part] = "<hw-threaddesc> UNF - <hw-threadclass> <hw-thru>"
    drill = "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>  "
    definitions[drill_part] = drill.upper() if uppercase else drill
    original = {part: _callout_text(definitions, part) for part in range(1, 9)}
    info = []
    events = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **attrs: info.append((message, attrs)))
    monkeypatch.setattr(drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs)))
    monkeypatch.setattr(drawing._telemetry, "warn", lambda *_args, **_kwargs: pytest.fail("no new WARN"))
    writes = []

    def set_text(part, text):
        writes.append((part, text))
        definitions[part + 4] = text

    display = SimpleNamespace(
        GetText=lambda part: _callout_text(definitions, part), SetText=set_text
    )
    drawing._name_pull_thread_drill(display)
    prefix = pin_spec.PULL_THREAD_TAP_DRILL_DESIGNATION + " DRILL "
    assert writes == [(drill_part - 4, prefix + original[drill_part])]
    for part in range(1, 9):
        expected = original[part]
        if part in (drill_part, drill_part - 4):
            expected = prefix + expected
        assert display.GetText(part) == expected
    attributes = {
        **{f"definition_{part}": original[part] for part in (5, 6, 7, 8)},
        **{f"resolved_{part}": original[part] for part in (1, 2, 3, 4)},
    }
    assert len(info) == 1
    assert info[0][1] == attributes
    assert events == [("drawing.pull_thread_callout", attributes)]
    assert sum(text.lower().count("<hw-thru>") for text in definitions.values()) == 2
    drawing._append_pull_thread_wall(display)
    assert pin_spec.PULL_THREAD_WALL_CALLOUT in display.GetText(4)
    assert definitions[thread_part].startswith(original[thread_part])


@pytest.mark.parametrize(
    "drill_rows",
    [
        {},
        {7: "<MOD-DIAM> <hw-thruholedia> <hw-thru>"},
        {7: "<hw-thrutapdrldia> <hw-thru>"},
        {6: "<MOD-DIAM>", 7: "<hw-thrutapdrldia> <hw-thru>"},
        {7: "<MOD-DIAM><hw-thrutapdrldia><hw-thrutapdrldia>"},
        {7: "<MOD-DIAM><MOD-DIAM><hw-thrutapdrldia>"},
        {7: "<MOD-DIAM><hw-thrutapdrldia>", 8: "<MOD-DIAM><hw-thrutapdrldia>"},
        {7: "<MOD-DIAM><hw-thrutapdrldia>", 8: "<hw-thrutapdrldia>"},
        {7: "<MOD-DIAM>\n<hw-thrutapdrldia> <hw-thru>"},
        {7: "<hw-threaddesc> <hw-thru>\n<MOD-DIAM><hw-thrutapdrldia> <hw-thru>"},
    ],
)
def test_numbered_drill_refuses_missing_or_ambiguous_native_tokens(
    monkeypatch: pytest.MonkeyPatch, drill_rows: dict[int, str]
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definitions = {5: "<hw-threaddesc> <hw-thru>", 6: "", 7: "", 8: ""}
    definitions.update(drill_rows)
    logs = []
    events = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda _message, **attrs: logs.append(attrs))
    monkeypatch.setattr(drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs)))
    display = SimpleNamespace(
        GetText=lambda part: _callout_text(definitions, part),
        SetText=lambda *_args: pytest.fail("ambiguous callout must not be written"),
    )
    with pytest.raises(RuntimeError, match="no unique"):
        drawing._name_pull_thread_drill(display)
    assert len(logs) == 1
    assert len(logs[0]) == 8
    assert all(isinstance(value, str) for value in logs[0].values())
    assert events == [("drawing.pull_thread_callout", logs[0])]


@pytest.mark.parametrize("corrupt_part", [None, 1, 2, 3, 4, 5, 6, 7, 8])
def test_numbered_drill_refuses_ignored_or_corrupt_setter_in_every_field(
    monkeypatch: pytest.MonkeyPatch, corrupt_part: int | None
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definitions = {
        5: "<hw-threaddesc> UNF - <hw-threadclass> <hw-thru>",
        6: "",
        7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
        8: "",
    }
    written = False

    def set_text(part, text):
        nonlocal written
        written = True
        if corrupt_part is not None:
            definitions[part + 4] = text

    def get_text(part):
        text = _callout_text(definitions, part)
        return text + " CORRUPT" if written and part == corrupt_part else text

    display = SimpleNamespace(GetText=get_text, SetText=set_text)
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._name_pull_thread_drill(display)


@pytest.mark.parametrize(
    "failure",
    [
        "unchanged", "corrupt_thread", "unresolved",
        "corrupt_resolved_thread", "corrupt_resolved_drill",
    ],
)
def test_wall_fact_refuses_failed_or_destructive_native_append(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definitions = {
        5: "<hw-threaddesc> UNF - <hw-threadclass>",
        6: " <hw-thru>",
        7: "",
        8: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
    }
    original_below = definitions[8]

    def set_text(_part, text):
        if failure == "unchanged":
            return None
        definitions[8] = text
        if failure == "corrupt_thread":
            definitions[5] = "#1-72 UNF - 2B"

    def get_text(part):
        if part == 4:
            if failure == "unresolved":
                return original_below
            if failure == "corrupt_resolved_drill" and definitions[8] != original_below:
                return _callout_text(definitions, part).replace("1.1811", "1.191")
        if part == 1 and failure == "corrupt_resolved_thread" and definitions[8] != original_below:
            return "#1-72 UNF - 2B"
        return _callout_text(definitions, part)

    display = SimpleNamespace(GetText=get_text, SetText=set_text)
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._append_pull_thread_wall(display)



def test_pull_tap_outer_end_and_callout_layout() -> None:
    import math

    import build_vn_crank_hub_pin as build

    assert build.TAP_R == pytest.approx(1.1811 / 2.0)
    assert build.V_TAP == pytest.approx(math.pi * (1.1811 / 2.0)**2 * pin_spec.PIN_LEN)
    assert build.PULL_THREAD_ENTRY_POINT == (0.0, 0.0, 0.0)
    assert build.PULL_THREAD_ENTRY_NORMAL == (0.0, 0.0, -1.0)

    # Callout above the pin outline and left of the right view's PinDia text.
    assert drawing.THREAD_NOTE_XY[1] > drawing.END_CENTER[1] + drawing.HALF_DIA
    assert drawing.THREAD_NOTE_XY[0] + 0.035 < drawing.RIGHT_KEEP["PinDia"][0] - 0.018
    # The 26-glyph fact is slightly wider than the measured 25-glyph / 67 mm row.
    assert drawing.THREAD_NOTE_XY == pytest.approx((0.122, 0.216))
    assert drawing.THREAD_NOTE_XY[0] + (0.067 * 26.0 / 25.0) / 2.0 < (
        drawing.RIGHT_KEEP["PinDia"][0] - 0.020
    )


def _circle(
    center_mm: tuple[float, float, float],
    radius_mm: float,
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> ViewEdge:
    return ViewEdge(
        edge=object(), line=None, circle=(*center_mm, *axis, radius_mm), vertices=None
    )


def test_pull_thread_callout_selects_entry_not_coincident_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import build_vn_crank_hub_pin as build

    entry = _circle(build.PULL_THREAD_ENTRY_POINT, pin_spec.PULL_THREAD_TAP_DRILL / 2.0)
    exit_rim = _circle((0.0, 0.0, pin_spec.PIN_LEN), entry.circle[6])
    outer = _circle(build.PULL_THREAD_ENTRY_POINT, pin_spec.PIN_DIA / 2.0)
    rims = ViewEdges(label="extraction end", edges=(exit_rim, outer, entry))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, **_kwargs: rims)
    assert drawing._pull_thread_entry_edge(object()) is entry.edge


@pytest.mark.parametrize(
    "rim",
    [
        _circle((0.0, 0.0, pin_spec.PIN_LEN), pin_spec.PULL_THREAD_TAP_DRILL / 2.0),
        _circle((0.0, 0.0, 0.0), pin_spec.PIN_DIA / 2.0),
        _circle((0.0, 0.0, 0.0), pin_spec.PULL_THREAD_MAJOR / 2.0),
        _circle((0.0, 0.0, 0.0), pin_spec.PULL_THREAD_TAP_DRILL / 2.0, (1.0, 0.0, 0.0)),
    ],
)
def test_pull_thread_entry_refuses_wrong_visible_rim(
    monkeypatch: pytest.MonkeyPatch, rim: ViewEdge
) -> None:
    rims = ViewEdges(label="wrong end", edges=(rim,))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, **_kwargs: rims)
    with pytest.raises(RuntimeError, match="no visible circle"):
        drawing._pull_thread_entry_edge(object())



@pytest.fixture
def saved_pull_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    """Only COM wrapper conversion is replaced; validators read the data."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="#0-80",
        FastenerType2=-1,  # Observed on worker 5; Type there was not recorded.
        Standard2=0,
        Type=33,  # swTapThru, not the generic initialization type swWzdTap=4
        EndCondition=1,
        ThreadEndCondition=1,
        ThreadClass="2B",
        ThruTapDrillDiameter=0.0011811,
    )
    feature = SimpleNamespace(
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: definition,
    )
    model = SimpleNamespace(
        FeatureByName=lambda name: feature if name == "PullThread" else None
    )
    return model, definition


def test_native_metadata_reader_logs_all_fields_and_reads_each_once(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _model, definition = saved_pull_thread
    seen = []
    messages = []
    warnings = []
    events = []

    def capture_warning(message, **attributes):
        messages.append(message)
        warnings.append(attributes)

    monkeypatch.setattr(pin_native._telemetry, "warn", capture_warning)
    monkeypatch.setattr(
        pin_native._telemetry,
        "event",
        lambda name, **attributes: events.append((name, attributes)),
    )

    class ReadOnce:
        def __getattr__(self, name: str) -> object:
            seen.append(name)
            return getattr(definition, name)

    data = pin_native.read_hole_wizard_metadata(ReadOnce(), label="inch tap control")
    assert vars(data) == vars(definition)
    assert len(seen) == len(set(seen)) == len(vars(definition))
    assert set(seen) == set(vars(definition))
    assert len(messages) == 1
    assert "inch tap control" in messages[0]
    assert "drill in metres" in messages[0]
    for member, value in vars(data).items():
        assert f"{member!r}: {value!r}" in messages[0]
    expected = {"label": "inch tap control", "drill_units": "m", **vars(data)}
    assert warnings == [expected]
    assert events == [("hole_wizard.native_metadata", expected)]


def test_native_reader_logs_other_fields_before_reraising_property_failure(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _model, definition = saved_pull_thread
    read_error = RuntimeError("unavailable FastenerType2")
    seen = []
    messages = []
    monkeypatch.setattr(
        pin_native._telemetry,
        "warn",
        lambda message, **_fields: messages.append(message),
    )

    class PartialRead:
        def __getattr__(self, name: str) -> object:
            seen.append(name)
            if name == "FastenerType2":
                raise read_error
            return getattr(definition, name)

    with pytest.raises(RuntimeError) as caught:
        pin_native.read_hole_wizard_metadata(PartialRead(), label="inch tap control")
    assert caught.value is read_error
    assert len(seen) == len(set(seen)) == len(vars(definition))
    assert set(seen) == set(vars(definition))
    assert len(messages) == 1
    assert "RuntimeError: unavailable FastenerType2" in messages[0]
    for member, value in vars(definition).items():
        if member != "FastenerType2":
            assert f"{member!r}: {value!r}" in messages[0]


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("Type", 4),
        ("Standard2", 1),
        ("FastenerSize", "#1-72"),
        ("ThreadClass", "3B"),
        ("ThruTapDrillDiameter", 0.001191),
        ("EndCondition", 2),
        ("ThreadEndCondition", 2),
    ],
)
def test_native_tuple_is_logged_before_any_release_assertion(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    monkeypatch: pytest.MonkeyPatch,
    member: str,
    value: object,
) -> None:
    import build_vn_crank_hub_pin as builder

    _model, definition = saved_pull_thread
    setattr(definition, member, value)
    messages = []
    monkeypatch.setattr(
        pin_native._telemetry,
        "warn",
        lambda message, **_fields: messages.append(message),
    )
    for validator in (
        builder._require_pull_thread_definition,
        drawing._require_pull_thread_definition,
    ):
        messages.clear()
        with pytest.raises(RuntimeError):
            validator(definition)
        assert len(messages) == 1
        for field, actual in vars(definition).items():
            assert f"{field!r}: {actual!r}" in messages[0]


@pytest.mark.parametrize("native_type", [33, 34, 35, 36, 48, 49, 50, 51, 52, 53, 54, 55])
def test_saved_pull_thread_accepts_correct_native_data(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    native_type: int,
) -> None:
    model, _definition = saved_pull_thread
    _definition.Type = native_type
    drawing._require_saved_pull_thread(model)
    import build_vn_crank_hub_pin as build

    build._require_pull_thread_definition(_definition)


@pytest.mark.parametrize(
    ("member", "value"),
    [
        ("FastenerSize", "#1-72"),
        ("Standard2", 1),
        ("Standard2", -1),
        ("Type", -1),
        ("Type", 4),  # swCounterDrilled, NOT a native swWzdTap feature subtype
        ("Type", 25),  # swHoleThru: a plain drill is not a tap
        ("Type", 31),  # swTapBlind
        ("Type", 39),  # swPipeTapThru
        ("Type", 46),  # swTapBlindCosmeticThread
        ("EndCondition", 0),
        ("EndCondition", 2),
        ("ThreadEndCondition", 0),
        ("ThreadEndCondition", 2),
        ("ThreadClass", "3B"),
        ("ThruTapDrillDiameter", 0.001191),
        ("ThruTapDrillDiameter", float("nan")),
    ],
)
def test_saved_pull_thread_rejects_wrong_native_data(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    member: str,
    value: object,
) -> None:
    model, definition = saved_pull_thread
    setattr(definition, member, value)
    with pytest.raises(RuntimeError):
        drawing._require_saved_pull_thread(model)
    import build_vn_crank_hub_pin as build

    with pytest.raises(RuntimeError):
        build._require_pull_thread_definition(definition)


def test_saved_pull_thread_rejects_missing_feature(
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
) -> None:
    model, _definition = saved_pull_thread
    model.FeatureByName = lambda _name: None
    with pytest.raises(RuntimeError, match="feature is missing"):
        drawing._require_saved_pull_thread(model)


@pytest.mark.parametrize(
    ("texts", "valid"),
    [
        (("#0-80 UNF - 2B", "THRU ALL"), True),
        (("#0 - 80 UNF - 2B", "THRU"), True),
        (("0-80 UNF - 2B", "THRU ALL"), True),
        (("<MOD-DIAM>  1.18 THRU ALL 0-80 UNF - 2B THRU ALL",), True),
        (("10-80 UNF - 2B", "THRU ALL"), False),
        (("#1-72 UNF - 2B", "THRU ALL"), False),
        (("#0-800 UNF - 2B", "THRU ALL"), False),
        (("#0-80 UNC - 2B", "THRU ALL"), False),
        (("#0-80 UNF - 3B", "THRU ALL"), False),
        (("#0-80 UNF", "THRU ALL"), False),
        (("#0-80 UNF", "NOTTHRU"), False),
        (("#0-80 UNF", "<HOLE-DEPTH> 4.0"), False),
        (("<MOD-DIAM> 1.1811 THRU ALL",), False),
        (("#0-80 UNF Tapped Hole",), False),
        (("#0-80 UNF THRU ALL", "<HOLE-DEPTH> 0.0"), False),
        ((), False),
    ],
)
def test_native_pull_thread_callout_validates_rendered_text(
    monkeypatch: pytest.MonkeyPatch, texts: tuple[str, ...], valid: bool
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    data = SimpleNamespace(
        GetTextCount=lambda: len(texts),
        GetTextAtIndex=lambda index: texts[index],
    )
    annotation = SimpleNamespace(GetDisplayData=lambda: data)
    display = SimpleNamespace(GetAnnotation=lambda: annotation)
    if valid:
        drawing._require_pull_thread_callout(display)
    else:
        with pytest.raises(RuntimeError, match="through semantics"):
            drawing._require_pull_thread_callout(display)


@pytest.mark.parametrize("drill_only", [False, True])
@pytest.mark.parametrize("lose_thread_after_append", [False, True])
def test_build_uses_entry_native_callout_and_exact_automatic_note_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    saved_pull_thread: tuple[SimpleNamespace, SimpleNamespace],
    drill_only: bool,
    lose_thread_after_append: bool,
) -> None:
    """Exercise authoring, unchanged rendered-text refusal and finalizer policy."""
    model, _definition = saved_pull_thread
    source = tmp_path / "vn-crank-hub-pin.SLDPRT"
    source.write_bytes(b"offline source sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    adapter = SimpleNamespace(currentModel=model, open_model=AsyncMock())
    entry = _circle((0.0, 0.0, 0.0), pin_spec.PULL_THREAD_TAP_DRILL / 2.0)
    exit_rim = _circle((0.0, 0.0, pin_spec.PIN_LEN), pin_spec.PULL_THREAD_TAP_DRILL / 2.0)
    outer = _circle((0.0, 0.0, 0.0), pin_spec.PIN_DIA / 2.0)

    def place_view(_adapter, _source, orientation, *_center, **_kwargs):
        # Front looks from +Z onto the exit; Back sees the Z=0 entry.
        visible = {"*Back": (outer, entry), "*Front": (outer, exit_rim)}
        return ViewEdges(label=orientation, edges=visible.get(orientation, ()))

    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, **_kwargs: view)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kwargs: (object(), object()))
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: [])
    for name in (
        "check", "read_required_properties", "stamp_drawing_summary",
        "set_hidden_lines_removed", "assert_imported_precision",
        "set_reference_dimensions", "add_view_centerline", "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *_args, **_kwargs: None)
    centre_marks = []

    def auto_center_marks(_adapter, view, **_kwargs):
        centre_marks.append(view)
        return True

    monkeypatch.setattr(drawing, "auto_center_marks", auto_center_marks)
    native_calls = []
    authored_callouts = []

    def add_native_hole_callout(_adapter, view, *, edge, callout_xy, label):
        native_calls.append((view, edge, callout_xy))
        texts = list(
            ("<MOD-DIAM> 1.1811 THRU ALL",)
            if drill_only else ("#0-80 UNF - 2B THRU ALL", "<MOD-DIAM> 1.1811 THRU ALL")
        )
        data = SimpleNamespace(
            GetTextCount=lambda: len(texts), GetTextAtIndex=lambda index: texts[index]
        )
        annotation = SimpleNamespace(GetDisplayData=lambda: data)
        definitions = {
            5: "<hw-threaddesc> UNF - <hw-threadclass> <hw-thru>",
            6: "",
            7: "",
            8: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
        }

        def set_text(part, text):
            # Both local operations preserve the native drill's definition.
            assert part == 4
            named_drill = "#56 DRILL <MOD-DIAM> <hw-thrutapdrldia> <hw-thru>"
            assert text == (
                named_drill if not definitions[8].startswith("#56 DRILL ")
                else named_drill + "\n" + pin_spec.PULL_THREAD_WALL_CALLOUT
            )
            definitions[8] = text
            texts[-1] = _callout_text(definitions, 4)
            if lose_thread_after_append and pin_spec.PULL_THREAD_WALL_CALLOUT in text:
                texts[:] = ["<MOD-DIAM> 1.1811 THRU ALL", pin_spec.PULL_THREAD_WALL_CALLOUT]

        display = SimpleNamespace(
            GetAnnotation=lambda: annotation,
            GetText=lambda part: _callout_text(definitions, part),
            SetText=set_text,
        )
        authored_callouts.append((display, definitions))
        return display

    monkeypatch.setattr(drawing, "add_native_hole_callout", add_native_hole_callout)
    finalize = AsyncMock(return_value={"pdf": str(drawing.PDF)})
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    if drill_only or lose_thread_after_append:
        with pytest.raises(RuntimeError, match="through semantics"):
            asyncio.run(drawing.build(adapter))
        finalize.assert_not_awaited()
    else:
        assert asyncio.run(drawing.build(adapter)) == {"pdf": str(drawing.PDF)}
        finalize.assert_awaited_once()
        options = finalize.await_args.kwargs
        assert options["pdf_title"] == "Crank Hub Axial Pin Manufacturing Drawing"
        assert options["redundant_note_substrings"] == ("Tapped Hole",)
        assert options["expected_redundant_notes"] == 1
        [(_display, definitions)] = authored_callouts
        assert definitions == {
            5: "<hw-threaddesc> UNF - <hw-threadclass> <hw-thru>",
            6: "",
            7: "",
            8: "#56 DRILL <MOD-DIAM> <hw-thrutapdrldia> <hw-thru>\n"
            + pin_spec.PULL_THREAD_WALL_CALLOUT,
        }
    [(view, edge, xy)] = native_calls
    assert edge is entry.edge
    assert xy == drawing.THREAD_NOTE_XY
    assert centre_marks == [view]



def test_drawing_registry_and_native_dimensions_are_complete() -> None:
    assert DRAWINGS_BY_NAME["dt_vn_crank_hub_pin"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-vn-crank-hub-pin.SLDDRW")
    assert set(drawing.RIGHT_KEEP) == set().union(*pin_spec.DRAWING_DIMENSIONS.values())
    assert pin_spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 1, "PinLen": 1}


def test_assembly_places_pin_axially_at_six_oclock() -> None:
    import build_dt_drive_train_assembly as assembly

    assert assembly.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        (
            assembly.X_CRANK,
            assembly.Y_CRANK - geometry.AXIAL_PIN_RADIUS_FROM_AXIS,
            assembly.CRANK_FACE_Z,
        )
    )
    assert assembly.CRANK_HUB_PIN_ROWS[2] == pytest.approx((0.0, 0.0, 1.0))
