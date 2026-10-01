"""Offline contracts for the transgear stud (MHA-082) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_stub as part
import draw_transgear_stub as drawing
import transgear_stub_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _fit_limits import SHAFT_H
from _surface_finish import MACHINED_UM

SW_TOL_MAX = 6  # swTolType_e.swTolMAX


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-stub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-stub.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-stub_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_stub"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_once_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_only_the_functional_sizes_carry_model_bands() -> None:
    """The journal's running fit, its length (the cluster float) and each
    relief's width (the 1.0-1.2 window) carry native bands from the spec;
    every other size prints its places and the title block governs it."""
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "JournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("StudProfile", "JournalLength"): "JOURNAL_LENGTH_TOL",
        ("StudProfile", "ReliefWidth"): "RELIEF_WIDTH_TOL",
        ("StudProfile", "RearReliefWidth"): "REAR_RELIEF_WIDTH_TOL",
    }
    assert spec.JOURNAL_DIA_BAND == SHAFT_H
    assert spec.DRAWING_PRECISION_BY_NAME["JournalDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["JournalLength"] == 2


def test_thread_relief_prints_a_max_under_the_thread_root() -> None:
    """swTolMAX prints the nominal then MAX, so the nominal is the band's top;
    that top stays under the #6-32 basic root and the 2A minor, and the width
    window charges the cap engagement at most 1.2."""
    assert spec.RELIEF_DIA_TOL_TYPE == SW_TOL_MAX
    assert spec.RELIEF_DIA == spec.RELIEF_DIA_MAX
    assert spec.RELIEF_DIA_MAX < spec.FRONT_THREAD_ROOT_BASIC
    assert spec.RELIEF_DIA_MAX < spec.FRONT_THREAD_MINOR_UNR_2A
    assert 1.0 <= spec.RELIEF_WIDTH_MIN < spec.RELIEF_WIDTH_MAX <= 1.2


def test_rear_relief_is_a_groove_under_the_10_32_root_at_the_seat() -> None:
    """R9-65: the rear thread runs out into a standard relief groove on the
    stud at its seat, Ø3.7 MAX under the #10-32 basic root (3.795) and the 2A
    minor (3.827), 1.1 ±0.1 wide -- not a face relief bored into the collar
    over the thread's crest."""
    assert spec.REAR_RELIEF_DIA == spec.REAR_RELIEF_DIA_MAX == 3.7
    assert spec.REAR_RELIEF_DIA_MIN == pytest.approx(3.4)
    assert spec.REAR_RELIEF_DIA_MAX < spec.REAR_THREAD_ROOT_BASIC
    assert spec.REAR_THREAD_ROOT_BASIC == pytest.approx(3.795, abs=5e-4)
    assert spec.REAR_RELIEF_DIA_MAX < spec.REAR_THREAD_MINOR_UNR_2A
    assert spec.SCREW_CUT_RUNOUT <= spec.REAR_RELIEF_WIDTH_MIN
    assert spec.REAR_RELIEF_WIDTH_MAX == pytest.approx(1.2)


def test_every_feature_is_visible_so_the_side_view_hides_no_lines() -> None:
    """The face relief inside the collar was the sheet's one hidden feature,
    and the 8.2 to its floor ended on a hidden step; the groove is visible."""
    calls = {
        node.func.id
        for node in ast.walk(ast.parse(Path(drawing.__file__).read_text("utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "set_hidden_lines_visible" not in calls
    assert not any("FaceRelief" in name for name in drawing.SIDE_KEEP)


@pytest.mark.parametrize(
    ("station", "machine_z"),
    [
        (0.0, -127.45),
        (spec.SLEEVE_THRUST_STATION, -135.15),
        (spec.CAP_SHOULDER_STATION, -158.05),
        (spec.TIP_STATION, -166.35),
    ],
)
def test_cluster_interfaces_sit_at_their_machine_stations(
    station: float, machine_z: float
) -> None:
    assert spec.SEAT_MACHINE_Z - station == pytest.approx(machine_z, abs=1e-9)


def test_journal_length_is_the_step_to_shoulder_span() -> None:
    assert spec.CAP_SHOULDER_STATION - spec.SLEEVE_THRUST_STATION == pytest.approx(
        spec.JOURNAL_LENGTH
    )
    assert spec.JOURNAL_LENGTH_MAX - spec.JOURNAL_LENGTH_MIN == pytest.approx(
        2.0 * spec.JOURNAL_LENGTH_TOL
    )


# Each axial dimension's text centres between its two stations; its extension
# lines rise from those stations' x and end 3.8 mm under its row.
_AXIAL_STATIONS = {
    "StepLength": ("COLLAR_FRONT_X", "THRUST_X"),
    "JournalLength": ("THRUST_X", "SHOULDER_X"),
    "ThrustStation": ("SEAT_X", "THRUST_X"),
    "FrontThreadEnd": ("SHOULDER_X", "FRONT_END_X"),
    "RearThreadEnd": ("REAR_END_X", "SEAT_X"),
}
_EXTENSION_PAST_ROW_M = 0.0038
# A dome radius's shoulder, from its text point: 7.5 mm left to 5.9 mm right,
# 2.8 mm under (runs 20261001T051043622Z and 19e33c6c2).
_RADIUS_SHOULDER = (-0.0075, 0.0059, -0.0028)


def test_dome_radius_shoulders_cross_no_axial_extension_line() -> None:
    """The layout audit refuses a shoulder that crosses another dimension's
    line.  At 19e33c6c2 the rear dome's R3.4 shoulder ran across the rear
    thread's end line, which runs down to row 2; every dome shoulder keeps
    2 mm off each extension line that reaches below it."""
    lines = []
    for name, stations in _AXIAL_STATIONS.items():
        x, row_y = drawing.SIDE_KEEP[name]
        xs = [getattr(drawing, station) for station in stations]
        assert x == pytest.approx(sum(xs) / 2.0), name
        lines.extend((station_x, row_y - _EXTENSION_PAST_ROW_M) for station_x in xs)
    left, right, drop = _RADIUS_SHOULDER
    for name in ("FrontDomeR", "RearDomeR"):
        x, y = drawing.SIDE_KEEP[name]
        shoulder_y = y + drop
        for line_x, line_bottom in lines:
            if line_bottom >= shoulder_y:
                continue
            gap = max(x + left - line_x, line_x - (x + right))
            assert gap >= 0.002, (name, line_x, gap)


def test_the_journal_carries_the_one_machined_finish() -> None:
    (journal,) = spec.SURFACE_FINISHES
    assert journal.key == "journal"
    assert journal.roughness_um == MACHINED_UM
    assert journal.face.diameter_mm == spec.JOURNAL_DIA
    assert (
        spec.SLEEVE_THRUST_STATION
        < journal.face.contains_z_mm
        < spec.CAP_SHOULDER_STATION
    )


def test_registry_row_is_the_turned_steel_mha_082() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-082"
    assert int(row["quantity"]) == 1
    assert "12L14" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
