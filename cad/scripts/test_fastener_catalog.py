from __future__ import annotations

from pathlib import Path

import _config
from _fastener_catalog import FASTENERS


_EXPECTED = {
    # Stable production stem: (supplier SKU(s), MHA number, fleet quantity).
    "vn-arbor-set-screw": (("91375A106",), "MHA-VN-034", 2),
    "vn-boss-hook": (("9490T1",), "MHA-VN-001", 1),
    "vn-clamp-screw": (("90280A201",), "MHA-VN-021", 6),
    "vn-cone-lock-knob": (("93585A190",), "MHA-VN-013", 1),
    "vn-cone-pivot-screw": (("91829A560",), "MHA-VN-014", 1),
    "vn-cone-tip-adjuster": (("94025A164",), "MHA-VN-017", 1),
    "vn-cone-tip-block-screw": (("91251A108",), "MHA-VN-030", 1),
    "vn-cone-tip-collar": (("9414T1",), "MHA-VN-016", 1),
    "vn-cone-tip-pinch-screw": (("91794A112",), "MHA-VN-018", 1),
    "vn-crank-seat-drive-pin": (("98381A434",), "MHA-VN-044", 2),
    "vn-fillister-screw": (("90114A511",), "MHA-VN-006", 19),
    "vn-foot-screw": (("90280A108",), "MHA-VN-020", 1),
    "vn-guide-lock-screw": (("91255A108",), "MHA-VN-046", 8),
    "vn-frame-side-screw": (("90280A194",), "MHA-VN-022", 2),
    "vn-frame-cross-screw": (("90280A837",), "MHA-VN-027", 8),
    "vn-gooseneck-set-screw": (("91410A538",), "MHA-VN-023", 1),
    "vn-hanger-screw": (("93075A194",), "MHA-VN-007", 1),
    "vn-hex-bolt": (("92865A585",), "MHA-VN-008", None),
    "vn-knife-hanger-stud": (("91247A720",), "MHA-VN-024", 2),
    "vn-latch-hook-bracket-screw": (("90280A108",), "MHA-VN-043", 2),
    "vn-magnifying-bracket-screw": (("91794A077",), "MHA-VN-050", 2),
    "vn-lag-screw": (("92240A540",), "MHA-VN-009", 4),
    "vn-pedestal-hold-down-screw": (("90280A197",), "MHA-VN-032", 6),
    "vn-pen-set-screw": (("99607A213",), "MHA-VN-010", 1),
    "vn-pinion-strap-pin": (("98296A027",), "MHA-VN-033", 3),
    "vn-post-mount-screw": (("40923906",), "MHA-VN-031", 2),
    "vn-slotted-screw": (("90280A201",), "MHA-VN-019", 4),
    "vn-swing-stop-screw": (("90280A108",), "MHA-VN-015", 1),
    "vn-thumb-screw": (("91882A221",), "MHA-VN-011", 2),
    "vn-transgear-arm-plate-screw": (("91790A196",), "MHA-VN-040", 2),
    "vn-transgear-collar-cross-pin": (("98296A026",), "MHA-VN-037", 1),
    "vn-transgear-knob-drive-pin": (("98381A433",), "MHA-VN-038", 2),
    "vn-transgear-knob-cup-pin": (("98296A031",), "MHA-VN-048", 1),
    "vn-transgear-disc-screw": (("91794A055",), "MHA-VN-039", 3),
    "vn-transgear-latch-pin": (("98381A474",), "MHA-VN-042", 1),
    "vn-transgear-pivot-screw": (("91829A205",), "MHA-VN-041", 1),
    "vn-transgear-retaining-ring": (("97431A260",), "MHA-VN-047", 1),
    "vn-transgear-pivot-spring": (("9715K43",), "MHA-VN-049", 1),
    "vn-knife-hanger-washer": (("90126A211",), "MHA-VN-026", 2),
    "vn-spring-hook": (("9489T111",), "MHA-VN-012", 20),
    "vn-tube-frame-cap": (("9275K141",), "MHA-VN-028", 4),
}
# The post-mount screw's 1/4-20 x 4 in stock is sourced from MSC.
_SUPPLIERS = {"vn-post-mount-screw": "MSC Industrial Supply"}


def _supplier(stem: str) -> str:
    return _SUPPLIERS.get(stem, "McMaster-Carr")


def test_catalog_carries_only_purchased_supplier_identities() -> None:
    assert set(FASTENERS) == set(_EXPECTED)
    for stem, (skus, _number, _quantity) in _EXPECTED.items():
        spec = FASTENERS[stem]
        assert spec.part_name == stem
        assert spec.supplier == _supplier(stem)
        assert spec.skus == skus
        assert spec.stock_name.strip()
        assert spec.material in {
            "Plain Carbon Steel",
            "AISI 304",
            "Brass",
            "Alloy Steel",
            "1100-O Rod (SS)",
        }


def test_purchased_config_preserves_bom_identity_and_quantity() -> None:
    for stem, (skus, number, quantity) in _EXPECTED.items():
        row = _config.parts(stem)
        assert row["number"] == number
        assert tuple(row["supplier_skus"]) == skus
        assert row["supplier"] == _supplier(stem)
        assert row["stock_name"] == FASTENERS[stem].stock_name
        assert row["process"] == "purchased"
        if quantity is None:
            assert "quantity" not in row
        else:
            assert int(row["quantity"]) == quantity


def test_fillister_stock_is_shared_across_the_fleet() -> None:
    def fleet_quantity(sku: str) -> int:
        return sum(
            int(_config.parts(stem)["quantity"])
            for stem, spec in FASTENERS.items()
            if sku in spec.skus
        )

    # Rule 12 (E10): the four pinion-block screws moved from the #8-32 x 1 to
    # the clamp screws' #8-32 x 1-1/4; the swing stop then left the x 1 for
    # the foot screw's #4-40 x 3/8 (2026-09-29), retiring 90280A199; the
    # paper drive's latch hook takes two more (MHA-VN-043, ruling 2),
    # while the magnifying bracket takes two #2-56 x 1/4 (MHA-VN-050).
    assert fleet_quantity("90280A199") == 0
    assert fleet_quantity("90280A108") == 4
    assert fleet_quantity("91794A077") == 2
    assert fleet_quantity("90280A201") == 10


def test_special_bom_titles_remain_machine_specific() -> None:
    assert _config.parts("vn-knife-hanger-stud")["title"] == "Knife-Hanger Bolt"
    assert _config.parts("vn-knife-hanger-washer")["title"] == "Knife-Hanger Washer"
    assert _config.parts("vn-lag-screw")["title"] == "Rocker-Support Hold-Down Screw"


def test_fastener_refuses_rows_outside_the_builds_cache_key(monkeypatch):
    """Under doit, HARMONIC_FASTENER_ROWS names the rows the task's cache key
    folds; any other row read must fail rather than reuse a stale artefact."""
    import pytest

    from _fastener_catalog import fastener

    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "vn-frame-side-screw,vn-clamp-screw")
    assert fastener("vn-clamp-screw").part_name == "vn-clamp-screw"
    with pytest.raises(KeyError, match="outside this build's cache key"):
        fastener("vn-lag-screw")
    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "")
    with pytest.raises(KeyError, match="outside this build's cache key"):
        fastener("vn-frame-side-screw")
    monkeypatch.delenv("HARMONIC_FASTENER_ROWS")
    assert fastener("vn-lag-screw").part_name == "vn-lag-screw"


def test_vendor_readme_carries_no_unfilled_harvest_evidence() -> None:
    # Every catalog-spec figure comes from a real replica report; a
    # placeholder token (HARVEST plus underscore) marks one never measured.
    readme = Path(__file__).resolve().parents[1] / "references" / "mcmaster" / "README.md"
    assert "HARVEST" + "_" not in readme.read_text(encoding="utf-8")


def test_arbor_set_screw_is_the_verified_black_oxide_cup_point() -> None:
    """#743: MHA-VN-034 is McMaster 91375A106 (alloy, C45, black oxide, plain
    cup), which bites the spotted steel arbor where an 18-8 cup would not.
    No "PN TO VERIFY" survives in its identity."""
    row = _config.parts("vn-arbor-set-screw")
    assert FASTENERS["vn-arbor-set-screw"].material == "Alloy Steel"
    assert "91375A106" in row["material_specification"]
    for value in row.values():
        assert "TO VERIFY" not in str(value).upper()


def test_every_catalog_fastener_has_a_reference_sheet() -> None:
    """Main on #743: every catalogue fastener ships a purchased reference
    sheet, MHA-VN-034 included, and a plain set screw's sheet is the shared
    purchased-fastener builder's."""
    from pathlib import Path

    from _drawing_registry import DRAWINGS

    sheets = {spec.artifact_stem: spec for spec in DRAWINGS}
    assert set(FASTENERS) <= set(sheets)
    spec = sheets["vn-arbor-set-screw"]
    assert (spec.name, spec.part) == ("vn_arbor_set_screw", "vn_arbor_set_screw")
    script = Path(__file__).resolve().parent / spec.script_name
    assert "build_purchased_fastener_drawing" in script.read_text(encoding="utf-8")


def test_every_catalog_fastener_stamps_its_supplier_identity() -> None:
    """build_purchased_fastener_drawing refuses a source part without the
    Stock Name / Supplier / Supplier SKUs properties; a builder that does not
    go through build_stock_fastener must stamp them itself."""
    from pathlib import Path

    scripts = Path(__file__).resolve().parent
    for stem in FASTENERS:
        source = (scripts / f"build_{stem.replace('-', '_')}.py").read_text(
            encoding="utf-8"
        )
        if "build_stock_fastener" in source:
            continue
        for name in ('"Stock Name"', '"Supplier"', '"Supplier SKUs"'):
            assert name in source, (stem, name)
