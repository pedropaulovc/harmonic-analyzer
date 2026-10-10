"""Purchased fastener identities used by the production CAD fleet.

The part stems are stable machine/BOM identities.  ``stock_name`` and ``skus``
identify the supplier's hardware represented by each generated SLDPRT
(McMaster-Carr unless ``supplier`` names another);
``material`` is the SOLIDWORKS library material used for production rendering
and mass properties.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PurchasedFastenerSpec:
    part_name: str
    stock_name: str
    skus: tuple[str, ...]
    material: str
    supplier: str = "McMaster-Carr"


def _stock(
    part_name: str,
    stock_name: str,
    *skus: str,
    material: str = "Plain Carbon Steel",
    supplier: str = "McMaster-Carr",
) -> PurchasedFastenerSpec:
    return PurchasedFastenerSpec(part_name, stock_name, skus, material, supplier)


FASTENERS: dict[str, PurchasedFastenerSpec] = {
    # #743: C45 alloy cup point, black oxide -- it bites the spotted steel
    # arbor where an 18-8 (B80) cup would not.
    "vn-arbor-set-screw": _stock(
        "vn-arbor-set-screw",
        "Alloy Steel Cup-Tip Set Screw",
        "91375A106",
        material="Alloy Steel",
    ),
    "vn-clamp-screw": _stock(
        "vn-clamp-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A201",
    ),
    "vn-cone-lock-knob": _stock(
        "vn-cone-lock-knob",
        "Stainless Steel High-Profile Knurled-Head Thumb Screw",
        "93585A190",
        material="AISI 304",
    ),
    "vn-cone-pivot-screw": _stock(
        "vn-cone-pivot-screw",
        "Slotted 18-8 Stainless Steel Precision Shoulder Screw",
        "91829A560",
        material="AISI 304",
    ),
    "vn-cone-tip-block-screw": _stock(
        "vn-cone-tip-block-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A108",
        material="Alloy Steel",
    ),
    "vn-cone-tip-adjuster": _stock(
        "vn-cone-tip-adjuster",
        "18-8 Stainless Steel Slotted Cup-Tip Set Screw",
        "94025A164",
        material="AISI 304",
    ),
    "vn-cone-tip-pinch-screw": _stock(
        "vn-cone-tip-pinch-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A112",
        material="AISI 304",
    ),
    "vn-crank-seat-drive-pin": _stock(
        "vn-crank-seat-drive-pin",
        "Alloy Steel Dowel Pin",
        "98381A434",
        material="Alloy Steel",
    ),
    "vn-fillister-screw": _stock(
        "vn-fillister-screw",
        "Brass Fillister Head Slotted Screw",
        "90114A511",
        material="Brass",
    ),
    "vn-foot-screw": _stock(
        "vn-foot-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    # R9-31: the eight platen-riding guide-lock screws; a button head clears
    # the hanger arm where the MHA-VN-006 fillister head would not. R9-48: 3/8
    # long, so the guide's through tap holds 1.5D at the worst case.
    "vn-guide-lock-screw": _stock(
        "vn-guide-lock-screw",
        "Black-Oxide Alloy Steel Button Head Hex Drive Screw",
        "91255A108",
        material="Alloy Steel",
    ),
    "vn-latch-hook-bracket-screw": _stock(
        "vn-latch-hook-bracket-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    "vn-magnifying-bracket-screw": _stock(
        "vn-magnifying-bracket-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A077",
        material="AISI 304",
    ),
    "vn-frame-side-screw": _stock(
        "vn-frame-side-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A194",
    ),
    "vn-frame-cross-screw": _stock(
        "vn-frame-cross-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A837",
    ),
    "vn-gooseneck-set-screw": _stock(
        "vn-gooseneck-set-screw",
        "Steel Square-Head Cup-Point Set Screw",
        "91410A538",
    ),
    "vn-hanger-screw": _stock(
        "vn-hanger-screw",
        "Low-Strength Zinc-Plated Steel Hex Head Screw",
        "93075A194",
    ),
    "vn-hex-bolt": _stock(
        "vn-hex-bolt",
        "Medium-Strength Grade 5 Steel Hex Head Screw",
        "92865A585",
    ),
    "vn-knife-hanger-stud": _stock(
        "vn-knife-hanger-stud",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A157",
        material="Alloy Steel",
    ),
    "vn-knife-mount-dowel": _stock(
        "vn-knife-mount-dowel",
        "Alloy Steel Dowel Pin",
        "98381A473",
        material="Alloy Steel",
    ),
    "vn-lag-screw": _stock(
        "vn-lag-screw",
        "18-8 Stainless Steel Hex Head Screw",
        "92240A540",
        material="AISI 304",
    ),
    "vn-pedestal-hold-down-screw": _stock(
        "vn-pedestal-hold-down-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A197",
    ),
    "vn-pinion-strap-pin": _stock(
        "vn-pinion-strap-pin",
        "1050-1095 Spring Steel Slotted Spring Pin",
        "98296A027",
    ),
    "vn-pen-set-screw": _stock(
        "vn-pen-set-screw",
        "Stainless Steel Flared-Collar Knurled-Head Thumb Screw",
        "99607A213",
        material="AISI 304",
    ),
    "vn-post-mount-screw": _stock(
        "vn-post-mount-screw",
        "Zinc-Plated Steel Slotted Fillister Head Machine Screw",
        "40923898",
        supplier="MSC Industrial Supply",
    ),
    "vn-slotted-screw": _stock(
        "vn-slotted-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A201",
    ),
    "vn-swing-stop-screw": _stock(
        "vn-swing-stop-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    "vn-thumb-screw": _stock(
        "vn-thumb-screw",
        "Steel Raised Knurled-Head Thumb Screw",
        "91882A221",
    ),
    "vn-spring-hook": _stock(
        "vn-spring-hook",
        "Black-Oxide Steel #6-32 Routing Eyebolt (Trimmed Shank, Supplied Nut Omitted)",
        "9489T111",
    ),
    "vn-boss-hook": _stock(
        "vn-boss-hook",
        "Zinc-Plated Steel #10-24 Open Routing Eyebolt (Trimmed Shank)",
        "9490T1",
    ),
    "vn-cone-tip-collar": _stock(
        "vn-cone-tip-collar",
        "Black-Oxide Carbon Steel Set Screw Shaft Collar",
        "9414T1",
    ),
    "vn-transgear-knob-drive-pin": _stock(
        "vn-transgear-knob-drive-pin",
        "Alloy Steel Dowel Pin",
        "98381A433",
        material="Alloy Steel",
    ),
    "vn-transgear-disc-screw": _stock(
        "vn-transgear-disc-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A055",
        material="AISI 304",
    ),
    "vn-transgear-arm-plate-screw": _stock(
        "vn-transgear-arm-plate-screw",
        "18-8 Stainless Steel Oval Head Slotted Screw",
        "91790A196",
        material="AISI 304",
    ),
    "vn-transgear-pivot-screw": _stock(
        "vn-transgear-pivot-screw",
        "Slotted 18-8 Stainless Steel Precision Shoulder Screw",
        "91829A205",
        material="AISI 304",
    ),
    "vn-transgear-collar-cross-pin": _stock(
        "vn-transgear-collar-cross-pin",
        "1050-1095 Spring Steel Slotted Spring Pin",
        "98296A026",
    ),
    "vn-transgear-knob-cup-pin": _stock(
        "vn-transgear-knob-cup-pin",
        "1050-1095 Spring Steel Slotted Spring Pin",
        "98296A031",
    ),
    "vn-transgear-latch-pin": _stock(
        "vn-transgear-latch-pin",
        "Alloy Steel Dowel Pin",
        "98381A474",
        material="Alloy Steel",
    ),
    # R9-68: E-style ring closing the disc cluster's float on the MHA-PD-023 pin.
    "vn-transgear-retaining-ring": _stock(
        "vn-transgear-retaining-ring",
        "Side-Mount External Retaining Ring",
        "97431A260",
    ),
    # MHA-VN-049: one curved disc spring under the MHA-VN-041 pivot screw's head;
    # high-carbon steel, the library's plain carbon steel.
    "vn-transgear-pivot-spring": _stock(
        "vn-transgear-pivot-spring",
        "Curved Disc Spring",
        "9715K43",
    ),
    # MHA-VN-052 / -053 (#948 ruling R): one wave disc spring preloading each
    # bank north on its datum; steel and high-carbon steel, the library's
    # plain carbon steel.
    "vn-cylinder-bank-spring": _stock(
        "vn-cylinder-bank-spring",
        "Wave Disc Spring",
        "9714K392",
    ),
    "vn-rocker-bank-spring": _stock(
        "vn-rocker-bank-spring",
        "Wave Disc Spring",
        "9714K24",
    ),
    # MHA-VN-025 / -054 / -055 (mg wheel rev 10): the magnifying wheel's
    # brass #4-40 nut and locknut and the two brass washers either side of
    # its hub.
    "vn-wheel-axle-nut": _stock(
        "vn-wheel-axle-nut",
        "Brass Hex Nut",
        "92671A005",
        material="Brass",
    ),
    "vn-wheel-axle-back-washer": _stock(
        "vn-wheel-axle-back-washer",
        "Brass Washer for Number 10 Screw Size",
        "92916A480",
        material="Brass",
    ),
    "vn-wheel-axle-front-washer": _stock(
        "vn-wheel-axle-front-washer",
        "Brass Washer for Number 4 Screw Size",
        "92916A250",
        material="Brass",
    ),
    "vn-tube-frame-cap": _stock(
        "vn-tube-frame-cap",
        "Metal Round Cap",
        "9275K141",
    ),
}


def fastener(part_name: str) -> PurchasedFastenerSpec:
    """Return one purchased fastener identity, failing loud if unregistered.

    Under doit, ``HARMONIC_FASTENER_ROWS`` names the only rows this build's cache
    key folds (``dodo._narrow_fastener_catalog``); reading any other row would
    let an edit to that row reuse this artefact, so it fails instead.
    """
    allowed = os.environ.get("HARMONIC_FASTENER_ROWS")
    if allowed is not None and part_name not in allowed.split(","):
        raise KeyError(
            f"fastener row {part_name!r} is outside this build's cache key "
            f"(HARMONIC_FASTENER_ROWS={allowed!r}); read it through a literal "
            "fastener(...) call so the build graph can see it"
        )
    try:
        return FASTENERS[part_name]
    except KeyError as exc:
        raise KeyError(f"purchased fastener is not registered: {part_name}") from exc
