"""Offline contracts for the transgear pin (MHA-179) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_pin as part
import draw_transgear_pin as drawing
import transgear_pin_spec as spec
import transgear_retaining_ring_spec as ring
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-pin_drawing.png")
    row = DRAWINGS_BY_NAME["transgear_pin"]
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


def test_only_the_shank_and_the_ring_groove_carry_model_bands() -> None:
    """The ground shank (running fit and arm press) and the groove's
    catalogue Ø and width carry native bands; the groove station prints
    .XXX and every other size its places under the title block."""
    assert model_toleranced_dimensions(part) == {
        ("PinProfile", "ShankDia"): "*deviations(DIA_BAND)",
        ("PinProfile", "GrooveDia"): "*deviations(GROOVE_DIA_BAND)",
        ("PinProfile", "GrooveWidth"): "*deviations(GROOVE_WIDTH_BAND)",
    }
    assert spec.DRAWING_PRECISION_BY_NAME["ShankDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["GrooveStation"] == 3


def test_the_groove_holds_the_ring_at_every_printed_limit() -> None:
    """The ring grips at the groove's largest Ø and still clears the shank;
    the ring's thickness never binds in the narrowest groove."""
    groove_max = spec.GROOVE_DIA + spec.GROOVE_DIA_BAND[0]
    groove_min = spec.GROOVE_DIA + spec.GROOVE_DIA_BAND[1]
    assert ring.FREE_DIA < groove_min
    assert groove_max < spec.DIA_MIN
    assert spec.GROOVE_WIDTH + spec.GROOVE_WIDTH_BAND[1] > (
        ring.THICKNESS + ring.THICKNESS_TOL
    )


def test_the_groove_callout_names_the_ring_on_one_line() -> None:
    """An above-callout with a line break is stored but never printed."""
    (text,) = drawing.DIMENSION_CALLOUTS_ABOVE.values()
    assert "\n" not in text
    assert spec.RING_NUMBER in text and ring.SKU in text
    with pytest.raises(RuntimeError):
        drawing._printable_above_callouts({"GrooveDia": "A\nB"})


@pytest.mark.parametrize(
    ("station", "machine_z"),
    [
        (-spec.HEAD_HEIGHT, -114.4625),
        (0.0, -116.4625),
        (spec.GROOVE_STATION, -163.7125),
        (spec.LENGTH, -166.7125),
    ],
)
def test_the_pin_sits_at_its_machine_stations(station: float, machine_z: float) -> None:
    assert spec.HEAD_SEAT_MACHINE_Z - station == pytest.approx(machine_z, abs=1e-9)


def test_the_functional_station_runs_from_the_head_seat_to_the_load_wall() -> None:
    """The station's extension lines rise from the seat and the groove's
    FRONT wall (paper-left of the rear wall), not from its rear wall."""
    x, _ = drawing.SIDE_KEEP["GrooveStation"]
    assert x == pytest.approx((drawing.SEAT_X + drawing.LOAD_WALL_X) / 2.0)
    assert drawing.LOAD_WALL_X < drawing.GROOVE_REAR_X < drawing.SEAT_X


def test_the_shank_carries_the_one_machined_finish() -> None:
    (shank,) = spec.SURFACE_FINISHES
    assert shank.key == "journal"
    assert shank.roughness_um == MACHINED_UM
    assert shank.face.diameter_mm == spec.DIA
    assert 0.0 < shank.face.contains_z_mm < spec.GROOVE_REAR_STATION


def test_notes_fit_the_sheet_limits() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_steel_mha_179() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == spec.PIN_NUMBER
    assert int(row["quantity"]) == 1
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
