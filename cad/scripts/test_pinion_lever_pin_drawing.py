"""Offline contracts for the pinion lever retention pin (MHA-135) drawing."""

from __future__ import annotations

from pathlib import Path

import _config
import build_pinion_lever_pin as pin
import draw_pinion_lever_pin as drawing
import pinion_lever_geometry as lever
import pinion_lever_pin_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_lift_rod_spec import ROD_DIA

_WEB_TARGET = 2.0  # U27: webs >= 2.0 at the printed worst case
_HOLE_OVERSIZE = float(_config.title_block("drilled_hole")["plus_mm"])


def test_required_drawing_paths_and_registry_row() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lever-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lever-pin.pdf")
    assert (
        DRAWINGS_BY_NAME["pinion_lever_pin"].script == Path(drawing.__file__).resolve()
    )
    assert "draw_pinion_lever_pin.py" in PRECISION_MIGRATED_DRAWINGS
    row = _config.parts("pinion-lever-pin")
    assert row["number"] == "MHA-135"
    assert row["material"] == row["material_specification"]
    assert "1/16" in row["material_specification"]
    assert int(row["quantity"]) == 1


def test_pin_fills_the_match_drilled_hole_and_spans_the_hub() -> None:
    assert spec.PIN_DIA == lever.PIN_HOLE_DIA == 25.4 / 16.0
    # Codex P1 (#844): the SHORTEST printed pin still stands a peen allowance
    # proud of each face of the LARGEST printed hub (both at .X).
    import pinion_lever_spec
    from pinion_lever_pin_geometry import PEEN_ALLOWANCE

    shortest_pin = spec.PIN_LEN - 0.8
    largest_hub = lever.HUB_OD + 0.8
    assert pinion_lever_spec.DRAWING_PRECISION_BY_NAME["HubOd"] == 1
    assert spec.DRAWING_PRECISION_BY_NAME["Depth"] == 1
    assert (shortest_pin - largest_hub) / 2.0 >= PEEN_ALLOWANCE >= 0.5
    assert "TRIM AND PEEN" in spec.ASSEMBLY_STEP


def test_cross_hole_webs_clear_two_millimetres_at_the_worst_case() -> None:
    hole = lever.PIN_HOLE_DIA + _HOLE_OVERSIZE
    rod_web = (ROD_DIA - hole) / 2.0
    hub_wall = (lever.HUB_OD - lever.BORE) / 2.0
    to_floor = lever.PIN_HOLE_FROM_MOUTH - hole / 2.0
    assert rod_web >= _WEB_TARGET - 0.05  # 2.33 with the drill's +0.10
    assert hub_wall >= _WEB_TARGET + 1.0
    assert to_floor >= _WEB_TARGET + 1.0
    assert lever.ROD_PIN_HOLE_FROM_END == lever.PIN_HOLE_FROM_MOUTH == 4.0


def test_marked_set_bands_and_places_come_from_the_spec() -> None:
    assert pin.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert model_toleranced_dimensions(pin) == {
        ("PinProfile", "PinDia"): "*deviations(PIN_DIA_BAND)"
    }
    assert spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 3, "Depth": 1}


def test_the_pin_sheet_has_no_notes_and_the_mates_carry_the_match_drill() -> None:
    """Rule 6 (Main's eye-pass sweep): the drive, trim and peen sequence is
    the pinion fit-up step; the match-drill rides both mates' hole callouts,
    so the pin sheet carries no general notes at all."""
    import pinion_lever_spec
    import pinion_lift_rod_spec

    assert not hasattr(spec, "DRAWING_NOTES")
    step = spec.ASSEMBLY_STEP
    assert spec.LEVER_NUMBER in step and spec.LIFT_ROD_NUMBER in step
    assert "MATCH-DRILLED" in step and "PEEN" in step
    for callout in (
        pinion_lever_spec.PIN_HOLE_CALLOUT,
        pinion_lift_rod_spec.PIN_HOLE_CALLOUT,
    ):
        assert "MATCH-DRILL THRU AT ASSEMBLY" in callout
        assert "MHA-135" in callout
    for script in (pin, drawing):
        assert "Manufacturing Notes" not in Path(script.__file__).read_text(
            encoding="utf-8"
        )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame" not in source
    assert "SetPrecision3" not in source
