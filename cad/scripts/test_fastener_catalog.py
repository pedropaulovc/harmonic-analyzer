from __future__ import annotations

from pathlib import Path

import _config
from _fastener_catalog import FASTENERS


_EXPECTED = {
    # Stable production stem: (supplier SKU(s), MHA number, fleet quantity).
    "arbor-set-screw": (("91375A106",), "MHA-147", 2),
    "boss-hook": (("9490T1",), "MHA-005", 1),
    "bracket-screw": (("90280A194",), "MHA-108", 2),
    "clamp-screw": (("90280A201",), "MHA-107", 6),
    "cone-lock-knob": (("91882A425",), "MHA-093", 1),
    "cone-pivot-screw": (("91829A560",), "MHA-094", 1),
    "cone-tip-adjuster": (("94025A164",), "MHA-097", 1),
    "cone-tip-block-nut": (("90631A007",), "MHA-146", 1),
    "cone-tip-block-screw": (("93075A150",), "MHA-140", 1),
    "cone-tip-pinch-screw": (("91794A112",), "MHA-098", 1),
    "fillister-screw": (("90114A511",), "MHA-030", 27),
    "foot-screw": (("90280A108",), "MHA-103", 1),
    "frame-side-screw": (("90280A194",), "MHA-117", 2),
    "frame-cross-screw": (("90280A837",), "MHA-132", 8),
    "gooseneck-set-screw": (("91410A538",), "MHA-118", 1),
    "hanger-screw": (("93075A194",), "MHA-034", 1),
    "hex-bolt": (("92865A585",), "MHA-036", None),
    "knife-hanger-stud": (("91247A720",), "MHA-119", 2),
    "lag-screw": (("92240A540",), "MHA-039", 4),
    "pedestal-hold-down-screw": (("90280A197",), "MHA-143", 2),
    "pen-set-screw": (("99607A213",), "MHA-052", 1),
    "post-mount-screw": (("40923898",), "MHA-142", 2),
    "slotted-screw": (("90280A201",), "MHA-101", 4),
    "swing-stop-screw": (("90280A199",), "MHA-095", 1),
    "thumb-screw": (("91882A221",), "MHA-075", 2),
    "knife-hanger-washer": (("90126A211",), "MHA-131", 2),
    "spring-hook": (("9489T111",), "MHA-090", 20),
    "tube-frame-cap": (("9275K141",), "MHA-133", 4),
}
# U37c: McMaster carries no 1/4-20 x 3-1/2 steel slotted fillister.
_SUPPLIERS = {"post-mount-screw": "MSC Industrial Supply"}


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
    # the clamp screws' #8-32 x 1-1/4, leaving the swing stop on the x 1.
    assert fleet_quantity("90280A199") == 1
    assert fleet_quantity("90280A201") == 10


def test_special_bom_titles_remain_machine_specific() -> None:
    assert _config.parts("knife-hanger-stud")["title"] == "Knife-Hanger Bolt"
    assert _config.parts("knife-hanger-washer")["title"] == "Knife-Hanger Washer"
    assert _config.parts("lag-screw")["title"] == "Rocker-Support Hold-Down Screw"


def test_fastener_refuses_rows_outside_the_builds_cache_key(monkeypatch):
    """Under doit, HARMONIC_FASTENER_ROWS names the rows the task's cache key
    folds; any other row read must fail rather than reuse a stale artefact."""
    import pytest

    from _fastener_catalog import fastener

    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "bracket-screw,clamp-screw")
    assert fastener("clamp-screw").part_name == "clamp-screw"
    with pytest.raises(KeyError, match="outside this build's cache key"):
        fastener("lag-screw")
    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "")
    with pytest.raises(KeyError, match="outside this build's cache key"):
        fastener("bracket-screw")
    monkeypatch.delenv("HARMONIC_FASTENER_ROWS")
    assert fastener("lag-screw").part_name == "lag-screw"


def test_vendor_readme_carries_no_unfilled_harvest_evidence() -> None:
    # Every catalog-spec figure comes from a real replica report; a
    # placeholder token (HARVEST plus underscore) marks one never measured.
    readme = Path(__file__).resolve().parents[1] / "references" / "mcmaster" / "README.md"
    assert "HARVEST" + "_" not in readme.read_text(encoding="utf-8")


def test_arbor_set_screw_is_the_verified_black_oxide_cup_point() -> None:
    """#743: MHA-147 is McMaster 91375A106 (alloy, C45, black oxide, plain
    cup), which bites the spotted steel arbor where an 18-8 cup would not.
    No "PN TO VERIFY" survives in its identity."""
    row = _config.parts("arbor-set-screw")
    assert FASTENERS["arbor-set-screw"].material == "Alloy Steel"
    assert "91375A106" in row["material_specification"]
    for value in row.values():
        assert "TO VERIFY" not in str(value).upper()


def test_every_catalog_fastener_has_a_reference_sheet() -> None:
    """Main on #743: every catalogue fastener ships a purchased reference
    sheet, MHA-147 included, and a plain set screw's sheet is the shared
    purchased-fastener builder's."""
    from pathlib import Path

    from _drawing_registry import DRAWINGS

    sheets = {spec.artifact_stem: spec for spec in DRAWINGS}
    assert set(FASTENERS) <= set(sheets)
    spec = sheets["arbor-set-screw"]
    assert (spec.name, spec.part) == ("arbor_set_screw", "arbor_set_screw")
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
