"""Offline contracts for the MHA-CH-13-TL-VN-52 hub washer (McMaster 96659A104).

Owner rulings 2026-11-23: the fixture's washer is one #10 SAE washer picked
by measurement from the owned pack ("OD .505 or under and bore .220 or
under"), in place of the turned MHA-CH-13-TL-03. These checks pin the
selection limits to the strap plan's hub keep-out and the mirrors to their
authorities.
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import pytest

import _config
import _shop_equipment
import _mcmaster_91255a267 as screw
import build_ch_rocker_strap_tl_vn_hub_washer as part
import ch_rocker_hub_fit
import ch_rocker_strap_spec as strap
import ch_rocker_strap_tl_hub_plug_spec as plug
import ch_rocker_strap_tl_sub_plate_spec as plate
import ch_rocker_strap_tl_vn_hub_washer_spec as spec
import hardware_schedule
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_catalog import FASTENERS
from _mcmaster_96659a104 import DIMS
from _stock_recipe import recipe_declaration
from diagnostics import diag_build_96659A104 as recipe

STEM = "ch-rocker-strap-tl-vn-hub-washer"
IN = 25.4
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]
PLAN = ROOT / "cad" / "process" / "ch_rocker_strap" / "plan.toml"


def _plan() -> dict:
    return tomllib.loads(PLAN.read_text(encoding="utf-8"))["parameters"]


def _shop_record() -> dict:
    return _shop_equipment.load()["fixtures"]["strap-hub-washer"]


def test_catalogue_row_is_the_registered_mcmaster_washer() -> None:
    row = _config.parts(STEM)
    stock = FASTENERS[STEM]
    assert part.SPEC is stock and part.PART_NAME == STEM == spec.PART_NAME
    assert stock.skus == tuple(row["supplier_skus"]) == (spec.SKU,) == ("96659A104",)
    assert stock.supplier == row["supplier"] == "McMaster-Carr"
    assert stock.stock_name == row["stock_name"]
    assert stock.material == row["material"]
    assert row["number"] == spec.PART_NUMBER == "MHA-CH-13-TL-VN-52"
    assert row["process"] == "purchased"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    metadata = recipe_declaration(spec.SKU, recipe.build_96659A104)
    assert metadata.module == recipe.__name__
    assert metadata.threaded is False


def test_the_made_washer_is_gone_without_an_alias() -> None:
    """Owner ruling 2026-11-23: "The made washer, its drawing and its lathe
    traveler are deleted." """
    old = "ch_rocker_strap_tl_hub_washer"
    assert not list(SCRIPTS.glob(f"*{old}*"))
    assert not (ROOT / "cad" / "process" / old).exists()
    assert not (
        ROOT / "cad" / "config" / "parts" / f"{old.replace('_', '-')}.yaml"
    ).exists()
    assert old not in DRAWINGS_BY_NAME
    assert old.replace("_", "-") not in FASTENERS


def test_modelled_washer_is_the_catalogue_nominal() -> None:
    assert spec.OUTER_DIA == pytest.approx(0.500 * IN)
    assert spec.BORE_DIA == pytest.approx(0.219 * IN)
    assert spec.THICKNESS_MIN == pytest.approx(0.036 * IN)
    assert spec.THICKNESS_MAX == pytest.approx(0.065 * IN)
    assert spec.THICKNESS_MIN < spec.THICKNESS < spec.THICKNESS_MAX
    assert spec.washer_volume() == pytest.approx(
        math.pi / 4 * (DIMS.od**2 - DIMS.id**2) * DIMS.thickness
    )


def test_selection_limits_are_the_owners_inside_the_standards_bands() -> None:
    """Owner ruling 2026-11-23: "OD .505 or under and bore .220 or under"."""
    assert spec.SELECT_OD_MAX == pytest.approx(0.505 * IN)
    assert spec.SELECT_BORE_MAX == pytest.approx(0.220 * IN)
    assert (spec.SELECT_OD_TEXT, spec.SELECT_BORE_TEXT) == (".505", ".220")
    # ASME B18.21.1 Table 11, No. 10: OD .495-.515, ID .214-.227.
    assert (DIMS.od_min, DIMS.od_max) == pytest.approx((0.495 * IN, 0.515 * IN))
    assert (DIMS.id_min, DIMS.id_max) == pytest.approx((0.214 * IN, 0.227 * IN))
    assert DIMS.od_min < spec.SELECT_OD_MAX < DIMS.od_max
    assert DIMS.id_min < spec.SELECT_BORE_MAX < DIMS.id_max
    assert spec.SELECT_BORE_MIN > screw.MAJOR_DIA


def test_mirrors_agree_with_their_authorities() -> None:
    plan = _plan()
    assert spec.PLAN_FLANGE_DIA == plan["bushing_flange_dia_mm"]
    assert spec.PLAN_CLEARANCE == plan["bushing_clearance_mm"]
    assert spec.PLAN_STACK_HEIGHT == plan["bushing_stack_height_mm"]
    assert spec.STRAP_HOLE_DIA_MAX == pytest.approx(
        strap.HOLE_DIA + ch_rocker_hub_fit.STRAP_HOLE_BAND[0]
    )
    assert spec.HUB_LOCATION_TOL == plate.HUB_LOCATION_TOL
    assert spec.PLUG_LOCATING_ERROR_MAX == pytest.approx(plug.HUB_LOCATING_ERROR_MAX)
    assert plug.WASHER_NUMBER == spec.PART_NUMBER
    assert part.SKU == spec.SKU
    # The selection limits' copies: the strap traveler and the fixture record.
    assert plan["washer_od_max_mm"] == pytest.approx(spec.SELECT_OD_MAX)
    assert plan["washer_bore_no_go_mm"] == pytest.approx(spec.SELECT_BORE_MAX)
    record = _shop_record()
    assert record["select_od_max_mm"] == pytest.approx(spec.SELECT_OD_MAX)
    assert record["select_bore_max_mm"] == pytest.approx(spec.SELECT_BORE_MAX)
    for text in (spec.SELECT_OD_TEXT, spec.SELECT_BORE_TEXT):
        assert text in record["purchase"]


def test_pushed_to_one_side_the_selected_washer_stays_inside_the_guarded_radius() -> (
    None
):
    """Half the OD, the bore's play on the smallest class 3A screw (major
    .1840, ASME B1.1), the standard's whole OD-to-ID runout and the tapped
    hole's position band, against the radius cam.py keeps the cutter's edge
    out of (flange / 2 + clearance)."""
    play = (0.220 - 0.1840) / 2.0 * IN
    assert spec.RADIAL_PLAY_MAX == pytest.approx(play)
    assert spec.RUNOUT_MAX == pytest.approx(0.013 * IN)
    reach = 0.505 / 2.0 * IN + play + 0.013 * IN + 0.002 * IN * math.sqrt(2.0)
    assert spec.REACH_MAX == pytest.approx(reach)
    assert spec.KEEP_RADIUS == pytest.approx(7.358)
    assert spec.REACH_MAX <= spec.KEEP_RADIUS
    # Owner ruling 2026-11-24: "Accept as is: centre the washer by eye, 0.5 mm
    # centred, 0.22 mm worst case; the traveler says to centre it and to
    # watch the first level." Pushed fully aside it is 0.22 mm (to the
    # hundredth) from the cutter's nearest edge, not the plan's 0.5.
    assert spec.WORST_CLEARANCE == pytest.approx(7.49 - reach)
    assert round(spec.WORST_CLEARANCE, 2) == spec.ACCEPTED_WORST_CLEARANCE == 0.22
    assert spec.WORST_CLEARANCE < spec.PLAN_CLEARANCE
    # Centred by eye the rim stays inside the plan's flange diameter, so the
    # cutter passes its whole 0.5 mm off.
    assert spec.REACH_CENTRED_MAX <= spec.PLAN_FLANGE_DIA / 2.0
    text = PLAN.read_text(encoding="utf-8")
    assert "centred on the hub hole by eye" in text
    assert "watch the first level pass outside the washer" in text
    # An unselected washer (the standard's largest OD and bore) would not.
    worst = DIMS.od_max / 2.0 + (DIMS.id_max - screw.MAJOR_DIA_MIN) / 2.0
    assert worst + spec.RUNOUT_MAX + spec.SCREW_AXIS_ERROR_MAX > spec.KEEP_RADIUS


def test_the_washer_covers_the_hub_hole_with_slop_counted() -> None:
    assert spec.BEARING_LAND_CENTRED_MIN == pytest.approx((0.495 - 0.4005) / 2.0 * IN)
    assert spec.BEARING_LAND_CENTRED_MIN > 1.0
    assert spec.BEARING_LAND_MIN == pytest.approx(
        spec.BEARING_LAND_CENTRED_MIN
        - spec.RADIAL_PLAY_MAX
        - spec.RUNOUT_MAX
        - spec.SCREW_AXIS_ERROR_MAX
        - spec.PLUG_LOCATING_ERROR_MAX
    )
    assert 0.25 < spec.BEARING_LAND_MIN < spec.BEARING_LAND_CENTRED_MIN
    assert spec.HEAD_LAND_MIN > 0.5


def test_stack_stays_under_the_plans_hub_stack_height() -> None:
    assert spec.STACK_HEIGHT_MAX == pytest.approx((0.065 + 0.101) * IN)
    assert spec.STACK_HEIGHT_MAX <= _plan()["bushing_stack_height_mm"]


def test_stock_build_turns_the_recipe_axis_onto_part_z(monkeypatch) -> None:
    seen: dict = {}
    monkeypatch.setattr(part, "build_stock_fastener", lambda _a, **kw: seen.update(kw))
    part.build(None)
    (component,) = seen["components"]
    assert component.sku == spec.SKU
    assert component.author is recipe.build_96659A104
    assert component.transform.rotation_radians == pytest.approx(
        (math.pi / 2.0, 0.0, 0.0)
    )
    assert seen["material"] == part.SPEC.material
    assert seen["screw_axis_planes"] == ("Top Plane", "Right Plane")


def test_tier_one_schedule_row_and_no_sheet() -> None:
    # Standard hardware is its HARDWARE.md row, not a sheet (owner, #2886).
    row = hardware_schedule.SCHEDULE[STEM]
    assert row["standard"] == "ASME B18.21.1"
    assert row["designation"].startswith("#10 SAE plain washer")
    assert hardware_schedule.envelope_mm(row["envelope"]["OD"]) == pytest.approx(
        DIMS.od_max
    )
    assert hardware_schedule.envelope_mm(row["envelope"]["T"]) == pytest.approx(
        DIMS.thickness_max
    )
    assert all(
        sheet.part != STEM.replace("-", "_") for sheet in DRAWINGS_BY_NAME.values()
    )
    assert not (SCRIPTS / "draw_ch_rocker_strap_tl_vn_hub_washer.py").exists()
