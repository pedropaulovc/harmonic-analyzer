"""Offline contracts for the rocker riser blocks (MHA-CH-06-TL-10)."""

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
    assert drawing.configuration_label(number, "L045") == "MHA-CH-06-TL-10-L045  QTY 2"


def test_every_other_length_reads_its_depth_and_height_on_the_sheet() -> None:
    """L045's view shows only its length; the shared sizes must still reach it."""
    # The one 38.1 width dimension states that it is both lengths' depth.
    assert drawing.CALLOUTS_BELOW["BlockWidth"] == "STOCK, BOTH LENGTHS"
    for configuration in set(spec.LENGTHS) - {spec.DEFAULT_CONFIG}:
        x, y = drawing.CONFIGURATION_VIEW_CENTERS[configuration]
        keep = drawing.configuration_keep(configuration)
        # Its height repeats as a native reference, left of its own view.
        assert set(keep) == {"BlockLength", "BlockHeight"}
        assert keep["BlockHeight"] == (drawing.FRONT_KEEP["BlockHeight"][0], y)
        half_length = spec.LENGTHS[configuration] * drawing._S / 2000.0
        assert keep["BlockHeight"][0] < x - half_length
    assert drawing.CONFIGURATION_HEIGHT_CALLOUT == "MATCHED SET"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_reference_height(adapter, curated, configuration)" in source


def test_inventory_record_takes_its_solids_from_this_spec() -> None:
    record = _record()
    assert record["cad"] == STEM
    assert "solids" not in record
    assert f"{STEM}_spec" in plans.shop_spec_modules()


def test_prechips_solids_are_the_validated_six_block_layout() -> None:
    table, *risers = [solid for solid in spec.PRECHIPS_SOLIDS if not solid.get("void")]
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


def test_pm30mv_table_models_share_the_manual_slot_section() -> None:
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    for solids in (
        inventory["fixtures"]["pm30mv-table"]["solids"],
        spec.PRECHIPS_SOLIDS,
    ):
        table = next(solid for solid in solids if solid["name"] == "table")
        slots = [solid for solid in solids if solid.get("void")]
        assert len(slots) == 6
        table_top = table["at_mm"][2] + table["size_mm"][2]
        centre_y = table["at_mm"][1] + table["size_mm"][1] / 2
        sections = []
        for slot in slots:
            assert slot["cuts"] == ["table"]
            assert slot["at_mm"][0] < table["at_mm"][0]
            assert slot["at_mm"][0] + slot["size_mm"][0] > (
                table["at_mm"][0] + table["size_mm"][0]
            )
            sections.append(
                (
                    round(slot["at_mm"][1] + slot["size_mm"][1] / 2 - centre_y, 3),
                    slot["size_mm"][1],
                    round(table_top - slot["at_mm"][2], 3),
                    slot["size_mm"][2],
                )
            )
        assert sorted(sections) == sorted(
            (centre, width, depth, height)
            for centre in (-63.5, 0.0, 63.5)
            for width, depth, height in ((14.0, 14.0, 15.0), (25.0, 24.0, 10.0))
        )


def test_rocker_mill_clamp_studs_enter_the_centre_t_slot() -> None:
    plan = tomllib.loads(plans.plan_path("ch_rocker_arm").read_text(encoding="utf-8"))
    members = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )["fixtures"]["clamping-kit-pm-52pcck-14mm"]["members"]
    checked = 0
    for setup in plan["setups"]:
        hold = setup["hold"]
        if hold["fixture"] != "rocker-riser-blocks":
            continue
        hold_pose = hold["pose"]
        table_y = (
            hold_pose["origin_mm"][1] + hold_pose["x"][0] * spec.TABLE_SLOT_CENTRES_Y[1]
        )
        table_top = hold_pose["origin_mm"][2] - spec.BLOCK_HEIGHT
        for clamp in hold["clamps"]:
            kit, member = (
                clamp["ref"].split("/", 1) if "/" in clamp["ref"] else ("", "")
            )
            if kit != "clamping-kit-pm-52pcck-14mm":
                continue
            assert member == (
                "strap-pad-mill-raised" if setup["id"] == "S1" else "strap-pad-mill"
            )
            solids = members[member]["solids"]
            stud = next(solid for solid in solids if solid["name"] == "stud")
            assert stud["length_mm"] == 101.6
            pose = clamp["pose"]
            stud_y = pose["origin_mm"][1] + stud["at_mm"][0] * pose["x"][1]
            assert abs(stud_y - table_y) + stud["dia_mm"] / 2 < 7.0
            bottom = pose["origin_mm"][2] + stud["at_mm"][2]
            assert table_top - 24.0 < bottom < table_top - 14.0
            foot = next(solid for solid in solids if solid["name"] == "T-nut foot")
            foot_top = pose["origin_mm"][2] + foot["at_mm"][2] + foot["size_mm"][2]
            assert abs(foot_top - (table_top - 14.0)) < 1e-9
            foot_width = (
                abs(pose["x"][1]) * foot["size_mm"][0]
                + abs(pose["x"][0]) * foot["size_mm"][1]
            )
            assert foot_width < 25.0
            checked += 1
    assert checked == 8


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
