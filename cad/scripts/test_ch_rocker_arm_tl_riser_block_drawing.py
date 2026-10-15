"""Offline contracts for the rocker riser blocks (MHA-CH-006-TL-10)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import _config
import _drawing_contract
import _process_plans as plans
import ch_rocker_arm_tl_riser_block_spec as spec
import draw_ch_rocker_arm_tl_riser_block as drawing
import export_features

STEM = "ch_rocker_arm_tl_riser_block"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _record() -> dict:
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    return inventory["fixtures"]["rocker-riser-blocks"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.configuration_keep(spec.DEFAULT_CONFIG) == {
        "BlockLength": drawing.FRONT_KEEP["BlockLength"]
    }


def test_every_configuration_gets_a_labelled_view_with_its_quantity() -> None:
    assert set(drawing.CONFIGURATION_VIEW_CENTERS) == set(spec.LENGTHS)
    assert spec.QUANTITIES == {"L036": 4, "L045": 2}
    assert (
        spec.QUANTITY == _config.parts("ch-rocker-arm-tl-riser-block")["quantity"] == 6
    )
    number = _config.parts("ch-rocker-arm-tl-riser-block")["number"]
    assert drawing.configuration_label(number, "L045") == "MHA-CH-006-TL-10-L045  QTY 2"


def test_inventory_record_takes_its_solids_from_this_spec() -> None:
    record = _record()
    assert record["cad"] == STEM
    assert "solids" not in record
    assert f"{STEM}_spec" in plans.shop_spec_modules()


def test_prechips_solids_are_the_validated_six_block_layout() -> None:
    table, *risers = spec.PRECHIPS_SOLIDS
    assert table["name"] == "table"
    assert table["at_mm"] == [-419.1, -97.975, -68.5]
    assert table["size_mm"] == [838.2, 209.55, 50.0]
    layout = {solid["name"]: (solid["at_mm"], solid["size_mm"]) for solid in risers}
    assert layout == {
        "left end riser": ([-178.0, -12.4, -18.5], [36.0, 38.1, 18.5]),
        "left outer riser": ([-138.0, -12.4, -18.5], [36.0, 38.1, 18.5]),
        "left inner riser": ([-75.0, -12.4, -18.5], [45.0, 38.1, 18.5]),
        "right inner riser": ([30.0, -12.4, -18.5], [45.0, 38.1, 18.5]),
        "right outer riser": ([102.0, -12.4, -18.5], [36.0, 38.1, 18.5]),
        "right end riser": ([142.0, -12.4, -18.5], [36.0, 38.1, 18.5]),
    }
    # Every block stands on the table top and carries the work at z = 0.
    for solid in risers:
        assert solid["at_mm"][2] == table["at_mm"][2] + table["size_mm"][2]
        assert solid["at_mm"][2] + solid["size_mm"][2] == 0.0
        assert solid["measured"]["by"]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-riser-block")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_places_are_model_authored_and_the_sheet_is_pure() -> None:
    script = Path(drawing.__file__)
    assert script.name in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    assert not _drawing_contract.drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
            checked += 1
    assert checked


def test_exported_height_features_carry_the_matched_set_requirement() -> None:
    """The six-block matched set the sheet prints is exported, not just the band."""
    features = _features()
    printed = ", ".join(
        (drawing.CALLOUTS_ABOVE["BlockHeight"], drawing.CALLOUTS_BELOW["BlockHeight"])
    )
    assert printed == f"MATCHED SET OF SIX, EQUAL WITHIN {spec.SET_EQUALITY:.2f}"
    for name in ("support_top", "table_seat"):
        assert "note" in features[name]["requirements"]
        assert features[name]["note"] == printed
