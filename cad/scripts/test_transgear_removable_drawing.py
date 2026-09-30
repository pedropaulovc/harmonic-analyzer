"""Offline contracts for the removable #25 sprocket (MHA-081) drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import _config
import build_transgear_removable as part
import draw_transgear_removable as drawing
import transgear_removable_notes as notes
import transgear_removable_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-removable.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-removable.pdf")
    assert (
        DRAWINGS_BY_NAME["transgear_removable"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    # The part marks exactly what the sheet imports.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    # Every callout lands on a dimension the sheet keeps.
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_pin_locations_hold_the_shared_band_at_three_places() -> None:
    """Each hole is located like the shafts' pins, so the slip clearance
    absorbs both parts' spacing error; the size rows print routine .XX."""
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinNegY"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["BoreDiaDim"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosDia"] == 2
    import crankshaft_spec

    assert crankshaft_spec.DRIVE_PIN_OFFSET_TOL == spec.DRIVE_PIN_OFFSET_TOL
    assert crankshaft_spec.DRIVE_PIN_OFFSET_PLACES == spec.DRIVE_PIN_OFFSET_PLACES


def test_the_bands_live_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BlankProfile", "BlankWidth"): "*deviations(spec.PLATE_BAND)",
        ("BorePinsProfile", "PinPosY"): "spec.DRIVE_PIN_OFFSET_TOL",
        ("BorePinsProfile", "PinNegY"): "spec.DRIVE_PIN_OFFSET_TOL",
    }
    # Faced to thickness, never over nominal.
    assert max(spec.PLATE_BAND) == 0.0 > min(spec.PLATE_BAND)


def test_web_worst_case_is_the_printed_limits() -> None:
    """Both holes at the DRILLED HOLES maximum and the pin centre moved its
    full band toward the bore; floored so the sheet never states more web."""
    drilled = _config.title_block("drilled_hole")
    assert drilled["minus_mm"] == 0.0
    oversize = drilled["plus_mm"]
    web = (
        spec.PIN_CIRCLE_DIA / 2.0
        - spec.DRIVE_PIN_OFFSET_TOL
        - (spec.PIN_HOLE_DIA + oversize) / 2.0
        - (spec.BORE_DIA + oversize) / 2.0
    )
    assert notes.BORE_PIN_WEB_WORST <= web < notes.BORE_PIN_WEB_WORST + 0.01
    assert 0.0 < notes.BORE_PIN_WEB_WORST < spec.BORE_PIN_WEB < 1.5
    assert notes.BORE_PIN_WEB_NOTE == "BORE TO DRIVE-PIN HOLE WEB 0.47 MIN."
    assert notes.BORE_PIN_WEB_NOTE in notes.DRAWING_NOTES.splitlines()


def test_sprocket_data_lists_every_configuration() -> None:
    rows = dict(
        line.split(":  ", 1) for line in notes.GEAR_DATA.splitlines() if ":  " in line
    )

    def values(label: str) -> list[str]:
        return rows[label].split("  /  ")

    assert values("CONFIGURATION") == [name for name, _teeth in spec.CONFIGS]
    assert values("NUMBER OF TEETH") == [str(teeth) for _name, teeth in spec.CONFIGS]
    # T12 hand check: p / sin 15 deg = 6.35 / 0.258819 = 24.535.
    assert values("PITCH DIAMETER (mm, REF)")[0] == "24.53"
    assert values("OUTSIDE DIAMETER (mm)") == ["27.5", "39.8", "52.0"]
    assert values("BOTTOM DIAMETER (mm, REF)") == [
        f"{spec.seat_bottom_dia(teeth):.2f}" for _name, teeth in spec.CONFIGS
    ]
    assert rows["CHAIN"] == "ANSI #25 ROLLER, PITCH 6.35, ROLLER Ø3.30"


def test_notes_stay_within_four_lines_and_never_restate_the_title_block() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4
    text = notes.DRAWING_NOTES.upper()
    assert "DEBUR" not in text and "+0.10" not in text
    assert "DEBUR" not in str(_config.parts("transgear-removable")["finish"]).upper()


def test_gears_carry_no_frames_or_datums() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    called = {
        getattr(node.func, "id", getattr(node.func, "attr", ""))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not called & {"add_feature_control_frame", "add_datum_feature"}


def test_registry_row_is_mha_081_one_of_each() -> None:
    row = _config.parts("transgear-removable")
    assert row["number"] == "MHA-081"
    assert int(row["quantity"]) == 1
    assert "1 EACH" in row["description"]


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
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
    extra = {"Gear Data": notes.GEAR_DATA, "Manufacturing Notes": notes.DRAWING_NOTES}
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []


@pytest.mark.parametrize("name", ["PinPosY", "PinNegY"])
def test_pin_chain_sits_right_of_the_teeth(name: str) -> None:
    """The location chain stands clear of the T24 tips on the face view."""
    tip_x = drawing.FRONT_CENTER[0] + spec.outside_dia(24) / 2.0 * drawing._S / 1000.0
    assert drawing.FRONT_KEEP[name][0] > tip_x + 0.005


class _Result:
    is_success = True
    data = None
    error = None


class _Tolerance:
    def __init__(self, kind: int, lower_mm: float, upper_mm: float) -> None:
        self.Type = kind
        self._limits = (lower_mm / 1000.0, upper_mm / 1000.0)

    def GetMinValue(self) -> float:
        return self._limits[0]

    def GetMaxValue(self) -> float:
        return self._limits[1]


class _Configurations:
    """A part whose tolerances are read per active configuration."""

    def __init__(self, bands: dict[str, dict]) -> None:
        self.bands = bands
        self.active = spec.DEFAULT_CONFIG
        self.visited: list[str] = []

    async def set_active_configuration(self, name: str) -> _Result:
        self.active = name
        self.visited.append(name)
        return _Result()


def _readback(monkeypatch, adapter: _Configurations) -> None:
    import asyncio
    from types import SimpleNamespace

    def named(_adapter, feature: str, dimension: str):
        band = adapter.bands[adapter.active][(feature, dimension)]
        return None, SimpleNamespace(Tolerance=_Tolerance(*band))

    monkeypatch.setattr(part, "_named_dimension", named)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    asyncio.run(part.assert_bands_in_every_configuration(adapter))


def test_every_configuration_must_read_the_family_bands_back(monkeypatch) -> None:
    """The sheet prints the plate and pin-location bands once for all three
    sprockets, so the build reads them back in each configuration."""
    bands = part.family_bands()
    assert bands[("BlankProfile", "BlankWidth")][1:] == (-0.10, 0.0)
    adapter = _Configurations({name: dict(bands) for name, _teeth in spec.CONFIGS})
    _readback(monkeypatch, adapter)
    assert adapter.visited == [name for name, _teeth in spec.CONFIGS] + [
        spec.DEFAULT_CONFIG
    ]
    # Negative control: a band that stayed in the default configuration only
    # (T12 untoleranced) must stop the build.
    untoleranced = {name: dict(bands) for name, _teeth in spec.CONFIGS}
    untoleranced["T12"][("BlankProfile", "BlankWidth")] = (0, 0.0, 0.0)
    with pytest.raises(RuntimeError, match=r"T12: BlankWidth@BlankProfile"):
        _readback(monkeypatch, _Configurations(untoleranced))
