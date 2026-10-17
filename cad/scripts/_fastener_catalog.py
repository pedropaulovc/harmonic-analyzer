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
    # The same C45 black-oxide cup point, #1-72 x 5/32, on the fulcrum shaft's
    # flat in each ch-fulcrum-keeper crown.
    "vn-fulcrum-set-screw": _stock(
        "vn-fulcrum-set-screw",
        "Alloy Steel Cup-Tip Set Screw",
        "91375A942",
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
    # R9-31: the eight platen-riding guide-lock screws; a low slotted pan head
    # (2026-10-11, as the book's lock plates show) clears the hanger arm where
    # the MHA-VN-006 fillister head would not. R9-48: 3/8 long, so the guide's
    # through tap holds 1.5D at the worst case.
    "vn-guide-lock-screw": _stock(
        "vn-guide-lock-screw",
        "18-8 Stainless Steel Pan Head Slotted Screw",
        "91792A108",
        material="AISI 304",
    ),
    "vn-latch-hook-bracket-screw": _stock(
        "vn-latch-hook-bracket-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    "vn-magnifying-bracket-screw": _stock(
        "vn-magnifying-bracket-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A078",
        material="AISI 304",
    ),
    "vn-ms-stop-plate-screw": _stock(
        "vn-ms-stop-plate-screw",
        "Brass Fillister Head Slotted Screw",
        "90114A124",
        material="Brass",
    ),
    "vn-frame-side-screw": _stock(
        "vn-frame-side-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A080",
        material="AISI 304",
    ),
    "vn-frame-cross-screw": _stock(
        "vn-frame-cross-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A837",
    ),
    "vn-gooseneck-set-screw": _stock(
        "vn-gooseneck-set-screw",
        "Steel Square-Head Cup-Point Set Screw",
        "91410A540",
    ),
    # #8-32 x 1 through the pen-hanger strap's clearance hole into the
    # MHA-VN-063 nut and MHA-VN-064 jam nut on the strap front.
    "vn-hanger-screw": _stock(
        "vn-hanger-screw",
        "Low-Strength Zinc-Plated Steel Hex Head Screw",
        "93075A199",
    ),
    "vn-knife-hanger-stud": _stock(
        "vn-knife-hanger-stud",
        "Knife-Hanger Bolt (18-8 Stainless Hex Screw, Cut to Length)",
        "92314A253",
        material="AISI 304",
    ),
    "vn-knife-hanger-washer": _stock(
        "vn-knife-hanger-washer",
        "18-8 Stainless Steel SAE No. 10 Flat Washer",
        "96659A104",
        material="AISI 304",
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
    "vn-bracket-hold-down-screw": _stock(
        "vn-bracket-hold-down-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A196",
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
    # The C45 black-oxide cup point, #4-40 x 3/16, locking the pen rod's
    # turned pivot end in the v-block.
    "vn-pen-rod-set-screw": _stock(
        "vn-pen-rod-set-screw",
        "Alloy Steel Cup-Tip Set Screw",
        "91375A105",
        material="Alloy Steel",
    ),
    # Brass #0-80 jam nut on the pen rod's top adjuster stud.
    "vn-pen-adjust-nut": _stock(
        "vn-pen-adjust-nut",
        "Brass Hex Nut",
        "92671A115",
        material="Brass",
    ),
    # Zinc-plated steel #8-32 hex nut on the hanger screw at the pen-hanger
    # strap's front face, and the thin small-pattern nut jammed against it.
    "vn-pen-hanger-nut": _stock(
        "vn-pen-hanger-nut",
        "Low-Strength Zinc-Plated Steel Hex Nut",
        "90480A009",
    ),
    "vn-pen-hanger-jam-nut": _stock(
        "vn-pen-hanger-jam-nut",
        "Zinc-Plated Steel Narrow-Profile Hex Nut",
        "90760A009",
    ),
    # Thin zinc-plated steel #10-24 nut jammed against the MHA-SM-003 boss
    # top face, locking the MHA-VN-001 counter anchor.
    "vn-boss-hook-jam-nut": _stock(
        "vn-boss-hook-jam-nut",
        "#10-24 Zinc-Plated Steel Narrow-Profile Hex Nut",
        "90760A140",
    ),
    # The four platen-clip screws: brass #2-56 x 1/4, whose head stays inside
    # the clip's rail where the MHA-VN-006 #4-40 head would overhang.  A pan
    # head (2026-10-15): the 90114A124 fillister's least head left 0.05 mm of
    # bearing land over the clip's largest drilled #2 loose hole.
    "vn-platen-clip-screw": _stock(
        "vn-platen-clip-screw",
        "Brass Pan Head Slotted Screw",
        "92446A077",
        material="Brass",
    ),
    # MSC 40923906: 1/4-20 x 4 in (101.6 mm) supplied stock. Only the
    # MHA-VN-031 modification applies vn_post_mount_screw_spec.CUT_LENGTH_MM
    # as a reference trim, then matched-hole cut-to-fit/deburr acceptance.
    "vn-post-mount-screw": _stock(
        "vn-post-mount-screw",
        "Zinc-Plated Steel Slotted Fillister Head Machine Screw",
        "40923906",
        supplier="MSC Industrial Supply",
    ),
    # McMaster 90280A203: #8-32 x 1-1/2 in (38.1 mm) supplied stock.
    # The former 31.75-mm geometry was not this SKU's verified stock length.
    "vn-slotted-screw": _stock(
        "vn-slotted-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A203",
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
        "91790A199",
        material="AISI 304",
    ),
    "vn-transgear-arm-plate-locating-pin": _stock(
        "vn-transgear-arm-plate-locating-pin",
        "Passivated 316 Stainless Steel ISO 2338-m6 Dowel Pin",
        "93600A189",
        material="AISI 304",  # native library stand-in; purchased grade remains 316
    ),
    "vn-transgear-pivot-screw": _stock(
        "vn-transgear-pivot-screw",
        "Transgear Pivot Screw (18-8 Stainless Socket Shoulder Screw, Faced to Fit)",
        "90325A174",
        material="AISI 304",
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
    # MHA-VN-069: one DIN 988 shim under the MHA-VN-041 head, on the spring (it
    # restores the spring room after the 9.5 bar's rearward growth); spring
    # steel, the library's plain carbon steel.
    "vn-transgear-pivot-shim": _stock(
        "vn-transgear-pivot-shim",
        "DIN 988 Spring Steel Shim",
        "98055A098",
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
    "vn-rocker-thrust-washer": _stock(
        "vn-rocker-thrust-washer",
        "Carbon Steel Ring Shim, 1/4 ID x 3/8 OD x 0.031",
        "3088A429",
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
    # MHA-CH-006-TL-32: the oblique trammel jig's pivot bearings, a pair
    # pressed into each pivot block (shop fixture hardware, modelled so the
    # jig assembly can mate them and run native interference).
    "ch-rocker-arm-tl-oblique-bearing": _stock(
        "ch-rocker-arm-tl-oblique-bearing",
        "Steel Ball Bearing, Sealed, Trade No. 6200-2RS",
        "5972K41",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-33: the oblique trammel jig's CL locator, pressed flush
    # into the carrier's in-place-finished CL hole (shop fixture hardware,
    # modelled so the jig assembly can mate it and run native interference).
    "ch-rocker-arm-tl-oblique-cl-dowel": _stock(
        "ch-rocker-arm-tl-oblique-cl-dowel",
        "52100 Alloy Steel Dowel Pin, Ø6 x 20 mm",
        "91595A452",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-41: the oblique trammel jig's #8-32 X 3/4 SHCS (the
    # fastener table's RAIL_TO_BAR row); shop fixture hardware, modelled so
    # the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-rail-screw": _stock(
        "ch-rocker-arm-tl-oblique-rail-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A197",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-42: the oblique trammel jig's #8-32 X 5/8 SHCS (the
    # fastener table's BRACKET_TO_BAR row); shop fixture hardware, modelled so
    # the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-bracket-screw": _stock(
        "ch-rocker-arm-tl-oblique-bracket-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A196",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-43: the oblique trammel jig's #8-32 X 1-7/8 SHCS (the
    # fastener table's NUT_BRACKET_TO_BLOCK row); shop fixture hardware,
    # modelled so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-block-screw": _stock(
        "ch-rocker-arm-tl-oblique-block-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A188",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-44: the oblique trammel jig's M4 X 20 SHCS (the
    # fastener table's BLOCK_TO_CARRIAGE row); shop fixture hardware,
    # modelled so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-carriage-screw": _stock(
        "ch-rocker-arm-tl-oblique-carriage-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91290A168",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-45: the oblique trammel jig's M4 X 12 SHCS (the
    # fastener table's KP08_TO_BRACKET row); shop fixture hardware, modelled
    # so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-kp08-screw": _stock(
        "ch-rocker-arm-tl-oblique-kp08-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91290A148",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-46: the oblique trammel jig's M3 X 10 SHCS (the
    # fastener table's NUT_TO_NUT_BRACKET row); shop fixture hardware,
    # modelled so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-nut-screw": _stock(
        "ch-rocker-arm-tl-oblique-nut-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91290A115",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-47: the oblique trammel jig's #4-40 X 1/2 flat head (the
    # fastener table's RISER_TO_CARRIER row); shop fixture hardware, modelled
    # so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-riser-screw": _stock(
        "ch-rocker-arm-tl-oblique-riser-screw",
        "Stainless Steel Phillips Flat Head Screw",
        "91771A110",
        material="AISI 304",
    ),
    # MHA-CH-006-TL-48: the oblique trammel jig's 1/4-20 X 3/4 SHCS (the
    # fastener table's CR_CLAMP row); shop fixture hardware, modelled so
    # the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-clamp-screw": _stock(
        "ch-rocker-arm-tl-oblique-clamp-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A540",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-49: the oblique trammel jig's 5/16-18 X 7/8 SHCS (the
    # fastener table's LEVER_TO_CARRIER row); shop fixture hardware, modelled
    # so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-lever-screw": _stock(
        "ch-rocker-arm-tl-oblique-lever-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A582",
        material="Alloy Steel",
    ),
    # MHA-CH-006-TL-50: the oblique trammel jig's #8 wedge-lock washer pairs
    # under the TL-43 block screws' heads (the fastener table's
    # BLOCK_LOCK_WASHER row); shop fixture hardware, modelled so the jig
    # assembly can mate it and run native interference.
    "ch-rocker-arm-tl-oblique-block-washer": _stock(
        "ch-rocker-arm-tl-oblique-block-washer",
        "Extreme-Vibration-Resistant Wedge Lock Washer",
        "91812A215",
        material="AISI 304",  # native library stand-in; purchased grade is 316
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
