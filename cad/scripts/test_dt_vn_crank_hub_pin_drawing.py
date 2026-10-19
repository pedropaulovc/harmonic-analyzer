"""Offline release contracts for the MHA-DT-VN-59 axial arm-to-hub seam pin."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import dt_crank_hub_geometry as geometry
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
    assert pin_spec.PULL_THREAD_MAJOR == pytest.approx(1.524)
    assert pin_spec.PULL_THREAD_TAP_DRILL == pytest.approx(1.1811)
    assert pin_spec.PULL_THREAD_LEN == pin_spec.PIN_LEN == 4.0
    assert pin_spec.PULL_THREAD_NOMINAL_LENGTH_DIAMETERS == pytest.approx(4.0 / 1.524)
    assert pin_spec.PULL_THREAD_NOMINAL_LENGTH_DIAMETERS >= 2.0
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
    """Model native definition lanes separately from their resolved getters."""
    if part in (5, 6, 7, 8):
        return definitions[part]
    return (
        definitions[part + 4]
        .replace("<hw-threadsize>", "#0-80")
        .replace("<hw-thruholedia>", "1.1811")
    )


@pytest.mark.parametrize("below", ["", "<MOD-DIAM> <hw-thruholedia> THRU ALL"])
def test_wall_fact_appends_without_replacing_native_thread_or_drill(
    monkeypatch: pytest.MonkeyPatch, below: str
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definitions = {
        5: "<hw-threadsize> UNF - 2B",
        6: " THRU ALL",
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
    assert display.GetText(4) == expected.replace("<hw-thruholedia>", "1.1811")


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
        5: "<hw-threadsize> UNF - 2B",
        6: " THRU ALL",
        7: "",
        8: "<MOD-DIAM> <hw-thruholedia> THRU ALL",
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
            5: "<hw-threadsize> UNF - 2B",
            6: " THRU ALL",
            7: "",
            8: "<MOD-DIAM> <hw-thruholedia> THRU ALL",
        }

        def set_text(part, text):
            # Only the additive below lane is writable; thread replacement fails.
            assert part == 4
            assert text == (
                "<MOD-DIAM> <hw-thruholedia> THRU ALL\n"
                + pin_spec.PULL_THREAD_WALL_CALLOUT
            )
            definitions[8] = text
            if lose_thread_after_append:
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
            5: "<hw-threadsize> UNF - 2B",
            6: " THRU ALL",
            7: "",
            8: "<MOD-DIAM> <hw-thruholedia> THRU ALL\n"
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
