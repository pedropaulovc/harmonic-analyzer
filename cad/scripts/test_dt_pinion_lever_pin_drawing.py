"""Offline contracts for the pinion lever retention pin (MHA-DT-30) drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_dt_pinion_lever_pin as pin
import draw_dt_pinion_lever_pin as drawing
import dt_pinion_lever_geometry as lever
import dt_pinion_lever_pin_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from dt_pinion_lift_rod_spec import ROD_DIA

_WEB_TARGET = WALL_TARGET_MM  # U27: webs >= .080 at the printed worst case
_HOLE_OVERSIZE = drilled_oversize_mm(unit="in")


def test_required_drawing_paths_and_registry_row() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-lever-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-lever-pin.pdf")
    assert (
        DRAWINGS_BY_NAME["dt_pinion_lever_pin"].script == Path(drawing.__file__).resolve()
    )
    assert "draw_dt_pinion_lever_pin.py" in PRECISION_MIGRATED_DRAWINGS
    row = _config.parts("dt-pinion-lever-pin")
    assert row["number"] == "MHA-DT-30"
    assert row["material"] == row["material_specification"]
    assert "1/16" in row["material_specification"]
    assert int(row["quantity"]) == 1


def test_pin_fills_the_match_drilled_hole_and_spans_the_hub() -> None:
    # #290 fit F15: the 1/16 drill rod (+/-.0003) slips into the .064 hole.
    assert spec.PIN_DIA == 25.4 / 16.0
    assert lever.PIN_HOLE_DIA == pytest.approx(0.064 * 25.4)
    assert spec.PIN_DIA_BAND == pytest.approx((0.0003 * 25.4, -0.0003 * 25.4))
    assert spec.PIN_DIA + spec.PIN_DIA_BAND[0] < lever.PIN_HOLE_DIA
    # Codex P1 (#844): the SHORTEST printed pin still stands a peen allowance
    # proud of each face of the LARGEST printed hub (both at .XX).
    import dt_pinion_lever_spec
    from dt_pinion_lever_pin_geometry import PEEN_ALLOWANCE

    xx_band = printed_band_mm(2, unit="in")
    shortest_pin = spec.PIN_LEN - xx_band
    largest_hub = lever.HUB_OD + xx_band
    assert dt_pinion_lever_spec.DRAWING_PRECISION_BY_NAME["HubOd"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["PinLen"] == 2
    assert (shortest_pin - largest_hub) / 2.0 >= PEEN_ALLOWANCE >= 0.5
    assert "TRIM BOTH ENDS AND PEEN FLUSH" in spec.ASSEMBLY_STEP


def test_cross_hole_webs_clear_two_millimetres_at_the_worst_case() -> None:
    hole = lever.PIN_HOLE_DIA + _HOLE_OVERSIZE
    rod_web = (ROD_DIA - hole) / 2.0
    hub_wall = (lever.HUB_OD - lever.BORE) / 2.0
    to_floor = lever.PIN_HOLE_FROM_MOUTH - hole / 2.0
    assert rod_web >= _WEB_TARGET  # 2.32 with the drill's +.004
    assert hub_wall >= _WEB_TARGET + 1.0
    assert to_floor >= _WEB_TARGET + 1.0
    assert lever.ROD_PIN_HOLE_FROM_END == lever.PIN_HOLE_FROM_MOUTH
    assert lever.PIN_HOLE_FROM_MOUTH == pytest.approx(0.16 * 25.4)


def test_marked_set_bands_and_places_come_from_the_spec() -> None:
    assert pin.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert set(drawing.FRONT_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert model_toleranced_dimensions(pin) == {
        ("PinProfile", "PinDia"): "PIN_DIA_BAND[0]"
    }
    assert spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 4, "PinLen": 2}


def test_the_diameter_prints_on_the_side_view_beside_the_length() -> None:
    """Machinist review of 7f7fc1717 (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned parts): the Ø sat alone
    on the end view.  Both dimensions now come from the one revolved
    half-profile the *Front side view shows, and the end view keeps nothing."""
    assert spec.DRAWING_DIMENSIONS == {"PinProfile": {"PinDia", "PinLen"}}
    assert not hasattr(drawing, "RIGHT_KEEP")
    source = Path(pin.__file__).read_text(encoding="utf-8")
    assert 'create_sketch("Front")' in source
    assert "add_diametric_linear_dimension" in source
    assert "create_revolve" in source and "create_extrusion" not in source
    # The diameter's text sits above the side view, clear of the pin outline.
    assert drawing.FRONT_KEEP["PinDia"][1] > drawing.FRONT_CENTER[1] + drawing.HALF_DIA
    assert drawing.FRONT_KEEP["PinLen"][1] < drawing.FRONT_CENTER[1] - drawing.HALF_DIA


def test_the_pin_sheet_has_no_notes_and_the_mates_carry_the_match_drill() -> None:
    """drawing-guidelines.md rule 7 (notes: few, flagged, never a method) (Main's eye-pass sweep): the insert, trim and peen sequence is
    the pinion fit-up step; the match-drill rides both mates' hole callouts
    as the hole specification only (Main, 2026-09-26), so the pin sheet
    carries no general notes at all."""
    import dt_pinion_lever_spec
    import dt_pinion_lift_rod_spec

    assert not hasattr(spec, "DRAWING_NOTES")
    step = spec.ASSEMBLY_STEP
    assert step.startswith(f"{spec.LEVER_PIN_SET_NAME}: ")
    # #1064: a slip pin in a drilled hole, retained by its peened heads, is
    # inserted, not driven.
    assert f"INSERT {spec.PIN_NUMBER}" in step and "DRIVE" not in step
    assert spec.PIN_NUMBER == _config.parts("dt-pinion-lever-pin")["number"]
    for callout in (
        dt_pinion_lever_spec.PIN_HOLE_CALLOUT,
        dt_pinion_lift_rod_spec.PIN_HOLE_CALLOUT,
    ):
        assert callout.startswith("MATCH-DRILL THRU AT ASSEMBLY")
        assert "MHA-DT-30" not in callout
    for script in (pin, drawing):
        assert "Manufacturing Notes" not in Path(script.__file__).read_text(
            encoding="utf-8"
        )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame" not in source
    assert "SetPrecision3" not in source


def test_every_model_edit_precedes_the_installed_split() -> None:
    # pc-lever-pin-diag and -diag2: tolerancing PinDia, then setting the
    # material, after the INSTALLED configuration was rebuilt left INSTALLED
    # stale in the saved part.  Every model edit precedes the configuration
    # split, so both configurations rebuild after the last one.
    import build_dt_pinion_lever_pin as part

    source = Path(part.__file__).read_text(encoding="utf-8")
    split = source.index("create_configuration {INSTALLED_CONFIG}")
    for edit in (
        "set_dimension_symmetric_tolerance(",
        "clear_dimensions_for_drawing(adapter)",
        "mark_dimensions_for_drawing(adapter,",
        "apply_drawing_precision(adapter,",
        "apply_material(adapter,",
        "apply_color(adapter,",
    ):
        assert source.count(edit) == 1, edit
        assert source.index(edit) < split, edit


class _MaterialPart:
    """Early-bound IPartDoc: GetMaterialPropertyName2 returns (name, database)."""

    def __init__(self, materials: dict[str, str]) -> None:
        self.materials = materials

    def GetMaterialPropertyName2(self, config: str):
        return self.materials[config], "solidworks materials"


def test_every_configuration_must_carry_the_pin_material() -> None:
    # apply_material sets the active configuration only; a configuration
    # without it gives drive-train the wrong MHA-DT-30 mass.
    from types import SimpleNamespace

    import build_dt_pinion_lever_pin as part
    from _configuration_material import require_material_in_every_configuration

    configs = ("Default", part.INSTALLED_CONFIG)
    good = SimpleNamespace(
        currentModel=_MaterialPart(dict.fromkeys(configs, part.MATERIAL))
    )
    require_material_in_every_configuration(good, part.PART_NAME, part.MATERIAL, configs)
    bare = SimpleNamespace(
        currentModel=_MaterialPart(
            {"Default": part.MATERIAL, part.INSTALLED_CONFIG: ""}
        )
    )
    with pytest.raises(RuntimeError, match=part.INSTALLED_CONFIG):
        require_material_in_every_configuration(bare, part.PART_NAME, part.MATERIAL, configs)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "require_material_in_every_configuration(\n        adapter, PART_NAME, MATERIAL," in source.replace("\r\n", "\n")
