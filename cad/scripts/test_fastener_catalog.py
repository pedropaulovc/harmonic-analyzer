from __future__ import annotations

from pathlib import Path

import _config
from _fastener_catalog import FASTENERS


_EXPECTED = {
    # Canonical production stem: (supplier SKU(s), MHA number, installed quantity).
    "sh-vn-arbor-set-screw": (("91375A106",), "MHA-SH-VN-54", 4),
    "sm-vn-boss-hook": (("9490T1",), "MHA-SM-VN-50", 1),
    "ch-vn-bracket-hold-down-screw": (("90280A196",), "MHA-CH-VN-57", 2),
    "sh-vn-clamp-screw": (("90280A201",), "MHA-SH-VN-53", 6),
    "dt-vn-cone-lock-knob": (("93585A190",), "MHA-DT-VN-51", 1),
    "dt-vn-cone-pivot-screw": (("91829A560",), "MHA-DT-VN-52", 1),
    "dt-vn-cone-tip-adjuster": (("94025A164",), "MHA-DT-VN-55", 1),
    "dt-vn-cone-tip-block-screw": (("91251A108",), "MHA-DT-VN-60", 1),
    "dt-vn-cone-tip-pinch-screw": (("91794A112",), "MHA-DT-VN-56", 1),
    "dt-vn-crank-seat-drive-pin": (("98381A434",), "MHA-DT-VN-67", 2),
    "sh-vn-brass-fillister-screw": (("90114A511",), "MHA-SH-VN-51", 15),
    "sh-vn-fillister-screw-90280a108": (("90280A108",), "MHA-SH-VN-52", 4),
    "pd-vn-guide-lock-screw": (("91792A108",), "MHA-PD-VN-60", 8),
    "ch-vn-frame-side-screw": (("91794A080",), "MHA-CH-VN-52", 2),
    "ch-vn-fulcrum-set-screw": (("91375A942",), "MHA-CH-VN-55", 2),
    "fr-vn-frame-cross-screw": (("90280A837",), "MHA-FR-VN-53", 8),
    "fr-vn-gooseneck-set-screw": (("91410A540",), "MHA-FR-VN-52", 1),
    "pn-vn-hanger-screw": (("93075A199",), "MHA-PN-VN-50", 1),
    "sm-vn-knife-hanger-stud": (("92314A253",), "MHA-SM-VN-52", 2),
    "sm-vn-knife-hanger-washer": (("96659A104",), "MHA-SM-VN-54", 2),
    "sm-vn-knife-mount-dowel": (("98381A473",), "MHA-SM-VN-53", 4),
    "mg-vn-magnifying-bracket-screw": (("91794A078",), "MHA-MG-VN-53", 2),
    "ms-vn-stop-plate-screw": (("90114A124",), "MHA-MS-VN-51", 2),
    "fr-vn-lag-screw": (("92240A540",), "MHA-FR-VN-51", 4),
    "dt-vn-pedestal-hold-down-screw": (("90280A197",), "MHA-DT-VN-62", 2),
    "pn-vn-pen-set-screw": (("99607A213",), "MHA-PN-VN-51", 1),
    "pn-vn-pen-rod-set-screw": (("91375A105",), "MHA-PN-VN-52", 1),
    "pn-vn-pen-adjust-nut": (("92671A115",), "MHA-PN-VN-53", 1),
    "pn-vn-pen-hanger-nut": (("90480A009",), "MHA-PN-VN-54", 1),
    "pn-vn-pen-hanger-jam-nut": (("90760A009",), "MHA-PN-VN-55", 1),
    "sm-vn-boss-hook-jam-nut": (("90760A140",), "MHA-SM-VN-55", 1),
    "pd-vn-platen-clip-screw": (("92446A077",), "MHA-PD-VN-65", 4),
    "dt-vn-pinion-strap-pin": (("98296A027",), "MHA-DT-VN-63", 3),
    "dt-vn-post-mount-screw": (("40923906",), "MHA-DT-VN-61", 2),
    "dt-vn-slotted-screw": (("90280A203",), "MHA-DT-VN-57", 4),
    "sh-vn-thumb-screw": (("91882A221",), "MHA-SH-VN-55", 3),
    "pd-vn-transgear-arm-plate-screw": (("91790A199",), "MHA-PD-VN-56", 2),
    "pd-vn-transgear-arm-plate-locating-pin": (("93600A189",), "MHA-PD-VN-64", 2),
    "pd-vn-transgear-knob-drive-pin": (("98381A433",), "MHA-PD-VN-54", 2),
    "pd-vn-transgear-knob-cup-pin": (("98296A031",), "MHA-PD-VN-62", 1),
    "pd-vn-transgear-disc-screw": (("91794A055",), "MHA-PD-VN-55", 3),
    "pd-vn-transgear-latch-pin": (("98381A474",), "MHA-PD-VN-58", 1),
    "pd-vn-transgear-pivot-screw": (("90325A174",), "MHA-PD-VN-57", 1),
    "pd-vn-transgear-retaining-ring": (("97431A260",), "MHA-PD-VN-61", 1),
    "pd-vn-transgear-pivot-spring": (("9715K43",), "MHA-PD-VN-63", 1),
    "pd-vn-transgear-pivot-shim": (("98055A098",), "MHA-PD-VN-67", 1),
    "dt-vn-cylinder-bank-spring": (("9714K392",), "MHA-DT-VN-68", 1),
    "ch-vn-rocker-bank-spring": (("9714K24",), "MHA-CH-VN-54", 1),
    "ch-vn-rocker-thrust-washer": (("3088A429",), "MHA-CH-VN-56", 2),
    "mg-vn-wheel-axle-nut": (("92671A005",), "MHA-MG-VN-52", 2),
    "mg-vn-wheel-axle-back-washer": (("92916A480",), "MHA-MG-VN-54", 1),
    "mg-vn-wheel-axle-front-washer": (("92916A250",), "MHA-MG-VN-55", 1),
    "ch-vn-spring-hook": (("9489T111",), "MHA-CH-VN-51", 20),
    "fr-vn-tube-frame-cap": (("9275K141",), "MHA-FR-VN-54", 4),
    # The oblique trammel jig's modelled bought hardware (shop fixture, TL Numbers).
    "ch-rocker-arm-tl-vn-oblique-bearing": (("5972K41",), "MHA-CH-06-TL-VN-52", 4),
    "ch-rocker-arm-tl-vn-oblique-cl-dowel": (("91595A452",), "MHA-CH-06-TL-VN-53", 1),
    "ch-rocker-arm-tl-vn-oblique-rail-screw": (("91251A197",), "MHA-CH-06-TL-VN-61", 14),
    "ch-rocker-arm-tl-vn-oblique-bracket-screw": (("91251A196",), "MHA-CH-06-TL-VN-62", 8),
    "ch-rocker-arm-tl-vn-oblique-block-screw": (("91251A188",), "MHA-CH-06-TL-VN-63", 2),
    "ch-rocker-arm-tl-vn-oblique-carriage-screw": (("91290A168",), "MHA-CH-06-TL-VN-64", 8),
    "ch-rocker-arm-tl-vn-oblique-kp08-screw": (
        ("91251A150",),
        "MHA-CH-06-TL-VN-65",
        4,
    ),
    "ch-rocker-arm-tl-vn-oblique-nut-screw": (("4C50BHCA",), "MHA-CH-06-TL-VN-66", 4),
    "ch-rocker-arm-tl-vn-oblique-riser-screw": (("91771A112",), "MHA-CH-06-TL-VN-67", 4),
    "ch-rocker-arm-tl-vn-oblique-clamp-screw": (("91251A541",), "MHA-CH-06-TL-VN-68", 1),
    "ch-rocker-arm-tl-vn-oblique-lever-screw": (("91251A583",), "MHA-CH-06-TL-VN-69", 2),
    "ch-rocker-arm-tl-vn-oblique-block-washer": (
        ("91812A215",),
        "MHA-CH-06-TL-VN-70",
        2,
    ),
    "ch-rocker-arm-tl-vn-oblique-lever-washer": (
        ("91812A230",),
        "MHA-CH-06-TL-VN-71",
        2,
    ),
}
# The post-mount screw's 1/4-20 x 4 in stock is sourced from MSC; the jig's nut
# screws are Olander button heads (owner ruling 2026-10-20).
_SUPPLIERS = {
    "dt-vn-post-mount-screw": "MSC Industrial Supply",
    "ch-rocker-arm-tl-vn-oblique-nut-screw": "Olander",
}

_SHARED_MEMBERS = {
    "sh-vn-chain-link": (
        "McMaster-Carr", "6261K171", "MHA-SH-VN-50",
        {"InnerLink": 34, "OuterLink": 33},
    ),
    "sh-vn-music-wire": (
        "McMaster-Carr", "9666K56", "MHA-SH-VN-56",
        {"LeverWire": 1, "PenWire": 1},
    ),
    "sh-vn-clamping-kit-hardware": (
        "Precision Matthews", "52PCCK-9/16-14mm", "MHA-SH-VN-57",
        {"HoldDownStud": 4, "TNut": 4, "FlangeNut": 4},
    ),
}

_SHARED_PROPERTIES = {
    # Material, supplier specification, finish, tolerance class, fit class.
    "sh-vn-chain-link": (
        "Plain Carbon Steel", "Steel, McMaster-Carr 6261K171",
        "as supplied; supplier states no coating", "machined_block", None,
    ),
    "sh-vn-brass-fillister-screw": (
        "Brass", "Brass, McMaster-Carr 90114A511",
        "plain", "machined_block", "fastener_clearance",
    ),
    "sh-vn-fillister-screw-90280a108": (
        "Plain Carbon Steel", "Steel, McMaster-Carr 90280A108",
        "zinc plated", "machined_block", "fastener_clearance",
    ),
    "sh-vn-clamp-screw": (
        "Plain Carbon Steel", "Steel, McMaster-Carr 90280A201",
        "zinc plated", "machined_block", "fastener_clearance",
    ),
    "sh-vn-arbor-set-screw": (
        "Alloy Steel", "Alloy steel, black oxide, Rockwell C45; McMaster-Carr 91375A106",
        "black oxide", "machined_block", "fastener_clearance",
    ),
    "sh-vn-thumb-screw": (
        "Plain Carbon Steel", "Steel, McMaster-Carr 91882A221",
        "as supplied", "machined_block", "fastener_clearance",
    ),
    "sh-vn-music-wire": (
        "ASTM A228 music wire", "ASTM A228 music wire, 0.031 in; McMaster-Carr 9666K56",
        "phosphate coated, as supplied", "machined_block", None,
    ),
    "sh-vn-clamping-kit-hardware": (
        "Plain Carbon Steel", "Hardened steel",
        "black oxide, as supplied", "visual_noncritical", None,
    ),
}

_RETIRED = {
    "pd-vn-chain-inner-link", "pd-vn-chain-outer-link",
    "dt-vn-fillister-screw", "fr-vn-fillister-screw", "pd-vn-fillister-screw",
    "dt-vn-foot-screw", "dt-vn-swing-stop-screw", "pd-vn-latch-hook-bracket-screw",
    "mg-vn-clamp-screw", "pd-vn-clamp-screw",
    "ch-vn-arbor-set-screw", "dt-vn-arbor-set-screw",
    "mg-vn-thumb-screw", "ms-vn-thumb-screw",
    "mg-vn-lever-wire", "pn-vn-pen-wire",
    "ch-rocker-arm-tl-vn-oblique-hold-down-stud",
    "ch-rocker-arm-tl-vn-oblique-t-nut",
    "ch-rocker-arm-tl-vn-oblique-flange-nut",
}


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

    # Raised pinion blocks use #8-32 x 1-1/2; clamp screws retain x 1-1/4.
    # The swing stop and paper-drive latch hook share the foot screw SKU,
    # while the magnifying bracket takes two #2-56 x 1/4 (MHA-MG-VN-53). The
    # four platen-clip screws left the brass #4-40 x 1/4 for a brass #2-56
    # x 1/4 (MHA-PD-VN-65), whose head fits inside the clip's rail, and then
    # the #2-56 fillister for the pan head, whose least head bears on the
    # clip around its loose hole; the measuring stick's stop plate keeps the
    # brass #2-56 fillister (MHA-MS-VN-51).
    assert fleet_quantity("90280A199") == 0
    assert fleet_quantity("90280A108") == 4
    assert fleet_quantity("91794A078") == 2
    assert fleet_quantity("90280A201") == 6
    assert fleet_quantity("90280A203") == 4
    assert fleet_quantity("90114A511") == 15
    assert fleet_quantity("90114A124") == 2
    assert fleet_quantity("92446A077") == 4
    assert fleet_quantity("91375A106") == 4
    assert fleet_quantity("91882A221") == 3


def test_shared_skus_have_one_canonical_supplier_identity() -> None:
    shared_screws = {stem for stem in _EXPECTED if stem.startswith("sh-vn-")}
    assert len(shared_screws) == 5
    assert {stem for stem in FASTENERS if stem.startswith("sh-vn-")} == shared_screws
    registry = _config.parts()
    shared = shared_screws | set(_SHARED_MEMBERS)
    assert {stem for stem in registry if stem.startswith("sh-vn-")} == shared
    assert len(shared) == 8
    assert not _RETIRED.intersection(registry)
    assert not _RETIRED.intersection(FASTENERS)
    for stem in _RETIRED:
        assert not (_config.CONFIG_DIR / "parts" / f"{stem}.yaml").exists()
    for stem in shared_screws:
        row = _config.parts(stem)
        assert row["default_configuration"] == "Default"
        assert "configuration_quantities" not in row
        assert row.get("usage_scope", "machine") == "machine"
        spec = FASTENERS[stem]
        assert [
            name for name, other in FASTENERS.items()
            if other.supplier == spec.supplier and other.skus == spec.skus
        ] == [stem]


def test_registry_rejects_duplicate_supplier_qualified_skus() -> None:
    owners: dict[tuple[str, str], str] = {}
    for stem, row in _config.parts().items():
        for sku in row.get("supplier_skus", ()):
            key = (row["supplier"], str(sku))
            assert key not in owners, (key, owners.get(key), stem)
            owners[key] = stem


def test_shared_member_quantities_are_installed_occurrences() -> None:
    for stem, (supplier, sku, number, quantities) in _SHARED_MEMBERS.items():
        assert stem not in FASTENERS  # Generic purchased path, not fastener scope.
        row = _config.parts(stem)
        assert row["supplier"] == supplier
        assert row["supplier_skus"] == [sku]
        assert row["number"] == number
        assert row["process"] == "purchased"
        assert row["configuration_quantities"] == quantities
        assert row["quantity"] == sum(quantities.values())
        assert row["default_configuration"] == next(iter(quantities))
        scope = "tooling" if stem == "sh-vn-clamping-kit-hardware" else "machine"
        assert row.get("usage_scope", "machine") == scope
        assert "installation_notes" not in row
    assert _config.parts("sh-vn-chain-link")["quantity"] == 67
    assert _config.parts("sh-vn-music-wire")["quantity"] == 2
    assert _config.parts("sh-vn-clamping-kit-hardware")["quantity"] == 12


def test_shared_vendor_material_finish_and_fit_are_preserved() -> None:
    registry = _config.parts()
    for stem, expected in _SHARED_PROPERTIES.items():
        row = registry[stem]
        assert tuple(
            row.get(field)
            for field in (
                "material", "material_specification", "finish",
                "tolerance_class", "fit_class",
            )
        ) == expected
        assert row["process"] == "purchased"


def test_special_bom_titles_remain_machine_specific() -> None:
    assert _config.parts("sm-vn-knife-hanger-stud")["title"] == "Knife-Hanger Bolt"
    assert _config.parts("sm-vn-knife-hanger-washer")["title"] == "Knife-Hanger Washer"
    assert _config.parts("sm-vn-knife-mount-dowel")["title"] == "Knife-Mount Dowel"
    assert _config.parts("fr-vn-lag-screw")["title"] == "Rocker-Support Hold-Down Screw"


def test_fastener_refuses_rows_outside_the_builds_cache_key(monkeypatch):
    """Under doit, HARMONIC_FASTENER_ROWS names the rows the task's cache key
    folds; any other row read must fail rather than reuse a stale artefact."""
    import pytest

    from _fastener_catalog import fastener

    monkeypatch.setenv(
        "HARMONIC_FASTENER_ROWS", "ch-vn-frame-side-screw,sh-vn-clamp-screw"
    )
    assert fastener("sh-vn-clamp-screw").part_name == "sh-vn-clamp-screw"
    with pytest.raises(KeyError, match="outside this build's cache key"):
        fastener("fr-vn-lag-screw")
    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "")
    with pytest.raises(KeyError, match="outside this build's cache key"):
        fastener("ch-vn-frame-side-screw")
    monkeypatch.delenv("HARMONIC_FASTENER_ROWS")
    assert fastener("fr-vn-lag-screw").part_name == "fr-vn-lag-screw"


def test_vendor_readme_carries_no_unfilled_harvest_evidence() -> None:
    # Every catalog-spec figure comes from a real replica report; a
    # placeholder token (HARVEST plus underscore) marks one never measured.
    readme = Path(__file__).resolve().parents[1] / "references" / "mcmaster" / "README.md"
    assert "HARVEST" + "_" not in readme.read_text(encoding="utf-8")


def test_arbor_set_screw_is_the_verified_black_oxide_cup_point() -> None:
    """#743: the shared McMaster 91375A106 is alloy, C45, black oxide,
    plain cup, which bites the spotted steel arbor where an 18-8 cup would not.
    No "PN TO VERIFY" survives in its canonical identity."""
    stem = "sh-vn-arbor-set-screw"
    row = _config.parts(stem)
    assert FASTENERS[stem].material == row["material"] == "Alloy Steel"
    assert row["material_specification"] == (
        "Alloy steel, black oxide, Rockwell C45; McMaster-Carr 91375A106"
    )
    assert row["finish"] == "black oxide"
    for value in row.values():
        assert "TO VERIFY" not in str(value).upper()


def test_every_catalog_fastener_has_a_reference_sheet() -> None:
    """Every catalogue fastener ships a purchased reference sheet, including
    the shared arbor set screw; its plain set-screw sheet uses the shared
    purchased-fastener builder."""
    from pathlib import Path

    from _drawing_registry import DRAWINGS

    sheets = {spec.artifact_stem: spec for spec in DRAWINGS}
    assert set(FASTENERS) <= set(sheets)
    for stem in ("sh-vn-arbor-set-screw",):
        spec = sheets[stem]
        assert (spec.name, spec.part) == (stem.replace("-", "_"),) * 2
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
