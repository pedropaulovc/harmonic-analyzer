"""Purchased fastener identities used by the production CAD fleet.

The part stems are stable machine/BOM identities.  ``stock_name`` and ``skus``
identify the McMaster-Carr hardware represented by each generated SLDPRT;
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
) -> PurchasedFastenerSpec:
    return PurchasedFastenerSpec(part_name, stock_name, skus, material)


FASTENERS: dict[str, PurchasedFastenerSpec] = {
    "bracket-screw": _stock(
        "bracket-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A194",
    ),
    "clamp-screw": _stock(
        "clamp-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A201",
    ),
    "cone-lock-knob": _stock(
        "cone-lock-knob",
        "Steel Raised Knurled-Head Thumb Screw",
        "91882A425",
    ),
    "cone-pivot-screw": _stock(
        "cone-pivot-screw",
        "Slotted 18-8 Stainless Steel Precision Shoulder Screw",
        "91829A560",
        material="AISI 304",
    ),
    "cone-tip-adjuster": _stock(
        "cone-tip-adjuster",
        "18-8 Stainless Steel Slotted Cup-Tip Set Screw",
        "94025A150",
        material="AISI 304",
    ),
    "cone-tip-pinch-screw": _stock(
        "cone-tip-pinch-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    "fillister-screw": _stock(
        "fillister-screw",
        "Brass Fillister Head Slotted Screw",
        "90114A511",
        material="Brass",
    ),
    "foot-screw": _stock(
        "foot-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    "frame-side-screw": _stock(
        "frame-side-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A194",
    ),
    "frame-cross-screw": _stock(
        "frame-cross-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A837",
    ),
    "gooseneck-set-screw": _stock(
        "gooseneck-set-screw",
        "Steel Square-Head Cup-Point Set Screw",
        "91410A538",
    ),
    "hanger-screw": _stock(
        "hanger-screw",
        "Low-Strength Zinc-Plated Steel Hex Head Screw",
        "93075A194",
    ),
    "hex-bolt": _stock(
        "hex-bolt",
        "Medium-Strength Grade 5 Steel Hex Head Screw",
        "92865A585",
    ),
    "knife-hanger-stud": _stock(
        "knife-hanger-stud",
        "Medium-Strength Grade 5 Steel Hex Head Screw",
        "91247A720",
    ),
    "knife-hanger-washer": _stock(
        "knife-hanger-washer",
        "Zinc-Plated Steel SAE Washer",
        "90126A211",
    ),
    "lag-screw": _stock(
        "lag-screw",
        "18-8 Stainless Steel Hex Head Screw",
        "92240A539",
        material="AISI 304",
    ),
    "pinion-strap-pin": _stock(
        "pinion-strap-pin",
        "1050-1095 Spring Steel Slotted Spring Pin",
        "98296A027",
    ),
    "pen-set-screw": _stock(
        "pen-set-screw",
        "Stainless Steel Flared-Collar Knurled-Head Thumb Screw",
        "99607A213",
        material="AISI 304",
    ),
    "slotted-screw": _stock(
        "slotted-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A201",
    ),
    "swing-stop-screw": _stock(
        "swing-stop-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A199",
    ),
    "thumb-screw": _stock(
        "thumb-screw",
        "Steel Raised Knurled-Head Thumb Screw",
        "91882A221",
    ),
    "spring-hook": _stock(
        "spring-hook",
        "Black-Oxide Steel #6-32 Routing Eyebolt (Trimmed Shank, Supplied Nut Omitted)",
        "9489T111",
    ),
    "boss-hook": _stock(
        "boss-hook",
        "Zinc-Plated Steel #10-24 Open Routing Eyebolt (Trimmed Shank)",
        "9490T1",
    ),
    "tube-frame-cap": _stock(
        "tube-frame-cap",
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
