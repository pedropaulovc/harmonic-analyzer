"""Offline contracts for the rocker hub (MHA-CH-12) drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_hub as part
import ch_rocker_arm_spec as rocker
import ch_rocker_hub_fit as fit
import ch_rocker_hub_notes as notes
import ch_rocker_hub_spec as spec
import draw_ch_rocker_hub as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_FLOOR_MM


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-hub.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-hub.pdf")
    assert DRAWINGS_BY_NAME["ch_rocker_hub"].script == Path(drawing.__file__).resolve()
    assert "draw_ch_rocker_hub.py" in PRECISION_MIGRATED_DRAWINGS


def test_press_fit_bands_hold_interference_at_both_ends() -> None:
    # .400 strap hole +.0005/.0000, hub land +.0013/+.0009: .0004-.0013 in.
    assert rocker.HUB_DIA == pytest.approx(0.400 * 25.4)
    assert fit.STRAP_HOLE_BAND == (0.0127, 0.0)
    assert fit.HUB_LAND_BAND == (0.03302, 0.02286)
    assert fit.PRESS_INTERFERENCE == pytest.approx((0.01016, 0.03302))


@pytest.mark.parametrize(
    "land_band",
    [(0.0254, 0.0127), (0.0127, 0.0)],
    ids=["line-to-line", "loose"],
)
def test_a_press_that_can_go_line_to_line_is_refused(land_band) -> None:
    # +.0010/+.0005 in the +.0005/.0000 hole: the smallest land meets the
    # largest hole at .0000.
    with pytest.raises(AssertionError, match="line-to-line or loose"):
        fit.press_interference(land_band, fit.STRAP_HOLE_BAND)


def test_supply_sizes_derive_from_the_finished_rocker() -> None:
    assert spec.LAND_DIA == rocker.HUB_DIA
    # The bore is drilled under the finished ream; the drilled-hole row's
    # +.004 still leaves stock.
    assert spec.SUPPLY_BORE_DIA == pytest.approx(0.246 * 25.4)
    assert spec.SUPPLY_BORE_DIA + spec.DRILLED_PLUS < rocker.PIVOT_HOLE_DIA
    # The length leaves FACE_STOCK at each end over the finished top limit.
    finished_max = rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
    assert spec.SUPPLY_LENGTH_MIN == pytest.approx(0.32 * 25.4)
    assert spec.SUPPLY_LENGTH_MIN >= finished_max + 2.0 * spec.FACE_STOCK
    assert spec.SUPPLY_LENGTH_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.SUPPLY_WALL_MIN >= WALL_FLOOR_MM
    assert part.V_HUB == pytest.approx(
        math.pi
        * ((spec.LAND_DIA / 2.0) ** 2 - (spec.SUPPLY_BORE_DIA / 2.0) ** 2)
        * spec.SUPPLY_LENGTH_MIN
    )


def test_the_sheet_never_repeats_a_finished_size() -> None:
    printed = " ".join(
        (
            notes.DRAWING_NOTES,
            *drawing.DIMENSION_CALLOUTS.values(),
            notes.SUPPLY_LENGTH_PREFIX,
        )
    )
    for value, places in (
        (rocker.PIVOT_HOLE_DIA, 3),
        (rocker.HUB_LENGTH, 2),
        (rocker.HUB_LENGTH, 4),
    ):
        assert f"{value / 25.4:.{places}f}".removeprefix("0") not in printed
    assert notes.DRAWING_NOTES == (
        "1. BORE AND LENGTH ARE FINISHED AFTER JOINING TO MHA-CH-13; SEE MHA-CH-06."
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source


def test_every_band_is_native_and_named() -> None:
    assert model_toleranced_dimensions(part) == {
        ("HubProfile", "LandDia"): "*deviations(HUB_LAND_BAND)",
    }
    build = Path(part.__file__).read_text(encoding="utf-8")
    # The supply length's single MIN limit (build_ch_rod_pivot_pin precedent).
    assert "tolerance.Type = SUPPLY_LENGTH_TOL_TYPE" in build
    assert "tolerance.SetValues(0.0, 0.0)" in build
    assert notes.SUPPLY_BORE_CALLOUT.splitlines() == [
        "DRILL THRU",
        "SUPPLY SIZE",
        "WALL .075 MIN",
    ]
    # The stated wall is the spec's worst case, rounded down (rule 20).
    assert 0.075 <= spec.SUPPLY_WALL_MIN / 25.4 < 0.076


def test_drawing_quality_and_no_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    names = set(_calls(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish",
    }
    assert "move_model_dimension" in names
    assert "add_view_centerline" in names


def test_registry_row() -> None:
    row = _config.parts("ch-rocker-hub")
    assert row["number"] == spec.NUMBER == "MHA-CH-12"
    assert row["component_of"] == "ch-rocker-arm"
    assert int(row["quantity"]) == int(_config.parts("ch-rocker-arm")["quantity"])
    assert "1018" in str(row["material_specification"])
    assert len(str(row["material_specification"])) <= 36
    assert len(str(row["finish"])) <= 36
    assert part.MATERIAL == "Plain Carbon Steel"


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None, part.PART_NAME, {"Manufacturing Notes": notes.DRAWING_NOTES}
    )
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
    assert set(required) <= set(part._SAVED_DRAWING_PROPERTIES)
