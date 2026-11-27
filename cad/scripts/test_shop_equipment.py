"""_shop_equipment: the inventory files merge into one document, a record key
lives in one file, ownership is the one ``status`` enum, and every plan's
hand-tap stack leaves room for the recorded tap guide."""

from __future__ import annotations

import tomllib

import pytest

import _shop_equipment
from _paths import CAD_ROOT

STATUSES = {"on_hand", "not_received", "to_order", "to_make"}
STOCK_STATUSES = {"on_hand", "not_received", "to_order"}


def test_sections_merge_across_files(tmp_path) -> None:
    (tmp_path / "a.toml").write_text(
        '[tools.a]\nstatus = "on_hand"\n', encoding="utf-8"
    )
    (tmp_path / "b.toml").write_text(
        '[tools.b]\nstatus = "to_order"\n[stock.bar]\nstatus = "on_hand"\n',
        encoding="utf-8",
    )
    assert _shop_equipment.load(tmp_path) == {
        "tools": {"a": {"status": "on_hand"}, "b": {"status": "to_order"}},
        "stock": {"bar": {"status": "on_hand"}},
    }


def test_a_record_in_two_files_is_refused(tmp_path) -> None:
    (tmp_path / "a.toml").write_text("[tools.same]\n", encoding="utf-8")
    (tmp_path / "b.toml").write_text("[tools.same]\n", encoding="utf-8")
    with pytest.raises(_shop_equipment.DuplicateRecordError, match="a.toml and b.toml"):
        _shop_equipment.load(tmp_path)


@pytest.mark.parametrize(
    ("text", "section"),
    [('[[stock]]\nform = "flat_bar"\n', "stock"), ('note = "loose"\n', "note")],
)
def test_a_top_level_value_that_is_not_a_table_is_refused(
    tmp_path, text, section
) -> None:
    (tmp_path / "a.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=f"a.toml: {section} is a"):
        _shop_equipment.load(tmp_path)


def test_ownership_is_the_status_enum() -> None:
    # A record without ``status`` is unrecorded in every reader; one with it
    # carries an enum value.
    inventory = _shop_equipment.load()
    for section, records in inventory.items():
        allowed = STOCK_STATUSES if section == "stock" else STATUSES
        for key, record in records.items():
            assert not {"present", "shop_made", "use"} & set(record), (section, key)
            if "status" in record:
                assert record["status"] in allowed, (section, key)
            assert record.get("supply", "shop_made") == "shop_made", (section, key)
            if record.get("status") == "to_make":
                assert record.get("supply") == "shop_made", (section, key)
            for member in record.get("members", {}).values():
                assert "use" not in member, (section, key)


def test_every_hand_tap_stop_leaves_room_for_the_tap_guide() -> None:
    # Owner ruling 2026-11-21: the mill's hand-tap stops use the Fisher spring
    # tap guide. A plan holding it measures only the tap in its wrench against
    # tap_wrench_reach_max_mm: its guide-and-tap stack less the guide's
    # overall length, rounded down to .01 in.
    guide = _shop_equipment.load()["tools"]["tap-guide-fisher"]
    guide_mm = guide["overall_length_in"] * 25.4
    holders = []
    for path in sorted((CAD_ROOT / "process").glob("*/plan.toml")):
        plan = tomllib.loads(path.read_text(encoding="utf-8"))
        if not any(
            tool.get("ref") == "tap-guide-fisher" for tool in plan.get("tools", [])
        ):
            continue
        holders.append(path.parent.name)
        # A family plan (cad/process/README.md) keeps the tapped part's
        # numbers in that part's own table, laid over the plan's.
        tables = [
            plan["parameters"] | part.get("parameters", {})
            for part in plan.get("parts", [{}])
        ]
        tapped = [table for table in tables if "tap_stack_max_mm" in table]
        assert tapped, path.parent.name
        for parameters in tapped:
            room = parameters["tap_stack_max_mm"] - guide_mm
            assert 0 <= room - parameters["tap_wrench_reach_max_mm"] < 0.254, (
                path.parent.name
            )
            # A setup picture draws the guide from the plan's restatement of
            # its shank and point, which must be the record's.
            for key, field in (
                ("tap_guide_dia_mm", "shank_dia_in"),
                ("tap_guide_point_dia_mm", "point_dia_in"),
            ):
                if key in parameters:
                    assert parameters[key] == pytest.approx(guide[field] * 25.4), (
                        path.parent.name,
                        key,
                    )
    assert len(holders) >= 10, holders


def _verify_pm30mv_spindle_envelope(machines: dict, repo_root) -> list[str]:
    import re

    mill = machines["pm-30mv"]
    if not (0.0 < mill["spindle_nose_od_in"] < mill["quill_collar_od_in"]):
        raise ValueError("spindle_nose_od_in must be positive and smaller than quill_collar_od_in")
    if not (
        0.0
        < mill["spindle_wrench_flat_shoulder_below_quill_ring_in"]
        < mill["spindle_below_head_housing_in"]
    ):
        raise ValueError(
            "spindle_wrench_flat_shoulder_below_quill_ring_in must be positive and smaller than spindle_below_head_housing_in"
        )

    cited_paths: list[str] = []
    for entry in mill.get("cite", ()):
        for rel in re.findall(
            r"research/shop-evidence/[0-9-]+/[A-Za-z0-9._-]+\.jpg",
            entry,
        ):
            target = repo_root / rel
            if not (target.is_file() and target.stat().st_size > 0):
                raise FileNotFoundError(rel)
            cited_paths.append(rel)
    if len(cited_paths) < 4:
        raise ValueError(f"expected at least 4 cited PM-30MV evidence photos, got {cited_paths}")
    return cited_paths


def test_pm30mv_spindle_envelope_and_cited_evidence_files_exist() -> None:
    repo_root = CAD_ROOT.parent
    machines = _shop_equipment.load()["machines"]
    cited_paths = _verify_pm30mv_spindle_envelope(machines, repo_root)
    assert set(cited_paths) == {
        "research/shop-evidence/2026-11-26/pm30mv-spindle-nose-od.jpg",
        "research/shop-evidence/2026-11-26/pm30mv-spindle-below-collar.jpg",
        "research/shop-evidence/2026-11-26/pm30mv-quill-collar-od.jpg",
        "research/shop-evidence/2026-11-26/pm30mv-spindle-below-head.jpg",
    }


def test_pm30mv_spindle_envelope_rejects_inverted_bounds_or_missing_photo(
    tmp_path,
) -> None:
    photo = tmp_path / "research/shop-evidence/2026-11-26/pm30mv-a.jpg"
    photo.parent.mkdir(parents=True)
    for suffix in ("a", "b", "c", "d"):
        (photo.parent / f"pm30mv-{suffix}.jpg").write_bytes(b"jpeg")

    valid_mill = {
        "spindle_nose_od_in": 1.736,
        "quill_collar_od_in": 4.2415,
        "spindle_wrench_flat_shoulder_below_quill_ring_in": 0.551,
        "spindle_below_head_housing_in": 1.9995,
        "cite": [
            " ".join(
                f"research/shop-evidence/2026-11-26/pm30mv-{s}.jpg"
                for s in ("a", "b", "c", "d")
            )
        ],
    }
    assert len(_verify_pm30mv_spindle_envelope({"pm-30mv": valid_mill}, tmp_path)) == 4

    with pytest.raises(ValueError, match="spindle_nose_od_in"):
        _verify_pm30mv_spindle_envelope(
            {"pm-30mv": valid_mill | {"spindle_nose_od_in": 5.0}}, tmp_path
        )
    with pytest.raises(
        ValueError, match="spindle_wrench_flat_shoulder_below_quill_ring_in"
    ):
        _verify_pm30mv_spindle_envelope(
            {
                "pm-30mv": valid_mill
                | {"spindle_wrench_flat_shoulder_below_quill_ring_in": 2.5}
            },
            tmp_path,
        )
    (photo.parent / "pm30mv-d.jpg").unlink()
    with pytest.raises(FileNotFoundError, match="pm30mv-d.jpg"):
        _verify_pm30mv_spindle_envelope({"pm-30mv": valid_mill}, tmp_path)
