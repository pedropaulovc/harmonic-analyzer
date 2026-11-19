"""_shop_equipment: the inventory files merge into one document, a record key
lives in one file, and ownership is the one ``status`` enum."""

from __future__ import annotations

import pytest

import _shop_equipment

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
