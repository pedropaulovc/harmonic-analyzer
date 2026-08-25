from __future__ import annotations

import _config
from _fastener_catalog import FASTENERS
from _drawing_registry import RETIRED_PURCHASED_DRAWING_ARTIFACT_STEMS


_EXPECTED = {
    # Stable production stem: (McMaster SKU(s), MHA number, fleet quantity).
    "bracket-screw": (("90280A194",), "MHA-108", 2),
    "clamp-screw": (("90280A201",), "MHA-107", 6),
    "cone-lock-knob": (("91882A412",), "MHA-093", 1),
    "cone-pivot-screw": (("91829A560",), "MHA-094", 1),
    "cone-tip-adjuster": (("94025A150",), "MHA-097", 1),
    "cone-tip-pinch-screw": (("90280A108",), "MHA-098", 1),
    "fillister-screw": (("90114A511",), "MHA-030", 22),
    "foot-screw": (("90280A108",), "MHA-103", 3),
    "frame-side-screw": (("90280A194",), "MHA-117", 6),
    "gooseneck-set-screw": (("91410A538",), "MHA-118", 1),
    "hanger-screw": (("93075A194",), "MHA-034", 1),
    "hex-bolt": (("92865A585",), "MHA-036", None),
    "knife-hanger-stud": (("91247A720",), "MHA-119", 2),
    "lag-screw": (("91783A722",), "MHA-039", 4),
    "pen-set-screw": (("99607A213",), "MHA-052", 1),
    "slotted-screw": (("90280A199",), "MHA-101", 4),
    "swing-stop-screw": (("90280A196",), "MHA-095", 1),
    "thumb-screw": (("91882A221",), "MHA-075", 2),
    "knife-hanger-washer": (("90126A211",), "MHA-121", 2),
}


def test_catalog_carries_only_purchased_mcmaster_identities() -> None:
    assert set(FASTENERS) == set(_EXPECTED)
    for stem, (skus, _number, _quantity) in _EXPECTED.items():
        spec = FASTENERS[stem]
        assert spec.part_name == stem
        assert spec.supplier == "McMaster-Carr"
        assert spec.skus == skus
        assert spec.stock_name.strip()
        assert spec.material in {"Plain Carbon Steel", "AISI 304", "Brass"}


def test_purchased_config_preserves_bom_identity_and_quantity() -> None:
    for stem, (skus, number, quantity) in _EXPECTED.items():
        row = _config.parts(stem)
        assert row["number"] == number
        assert tuple(row["supplier_skus"]) == skus
        assert row["supplier"] == "McMaster-Carr"
        assert row["stock_name"] == FASTENERS[stem].stock_name
        assert row["process"] == "purchased"
        if quantity is None:
            assert "quantity" not in row
        else:
            assert int(row["quantity"]) == quantity


def test_special_bom_titles_remain_machine_specific() -> None:
    assert _config.parts("knife-hanger-stud")["title"] == "Knife-Hanger Bolt"
    assert _config.parts("knife-hanger-washer")["title"] == "Knife-Hanger Washer"
    assert _config.parts("lag-screw")["title"] == "Rocker-Support Hold-Down Screw"


def test_removed_custom_drawings_have_output_tombstones() -> None:
    assert set(RETIRED_PURCHASED_DRAWING_ARTIFACT_STEMS) == (
        set(_EXPECTED) - {"hex-bolt", "knife-hanger-washer"}
    )
