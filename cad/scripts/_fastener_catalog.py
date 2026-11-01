"""Purchased fastener identities used by the production CAD fleet.

Part stems identify canonical machine/BOM and native models; supplier SKUs
shared by several consumers have one Shared vendor identity.
``stock_name`` and ``skus`` identify the supplier's hardware represented by each
generated SLDPRT (McMaster-Carr unless ``supplier`` names another);
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
    "sh-vn-arbor-set-screw": _stock(
        "sh-vn-arbor-set-screw",
        "Alloy Steel Cup-Tip Set Screw",
        "91375A106",
        material="Alloy Steel",
    ),
    # The same C45 black-oxide cup point, #1-72 x 5/32, on the fulcrum shaft's
    # flat in each ch-fulcrum-keeper crown.
    "ch-vn-fulcrum-set-screw": _stock(
        "ch-vn-fulcrum-set-screw",
        "Alloy Steel Cup-Tip Set Screw",
        "91375A942",
        material="Alloy Steel",
    ),
    "sh-vn-clamp-screw": _stock(
        "sh-vn-clamp-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A201",
    ),
    "dt-vn-cone-lock-knob": _stock(
        "dt-vn-cone-lock-knob",
        "Stainless Steel High-Profile Knurled-Head Thumb Screw",
        "93585A190",
        material="AISI 304",
    ),
    "dt-vn-cone-pivot-screw": _stock(
        "dt-vn-cone-pivot-screw",
        "Slotted 18-8 Stainless Steel Precision Shoulder Screw",
        "91829A560",
        material="AISI 304",
    ),
    "dt-vn-cone-tip-block-screw": _stock(
        "dt-vn-cone-tip-block-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A108",
        material="Alloy Steel",
    ),
    "dt-vn-cone-tip-adjuster": _stock(
        "dt-vn-cone-tip-adjuster",
        "18-8 Stainless Steel Slotted Cup-Tip Set Screw",
        "94025A164",
        material="AISI 304",
    ),
    "dt-vn-cone-tip-pinch-screw": _stock(
        "dt-vn-cone-tip-pinch-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A112",
        material="AISI 304",
    ),
    "dt-vn-crank-seat-drive-pin": _stock(
        "dt-vn-crank-seat-drive-pin",
        "Alloy Steel Dowel Pin",
        "98381A434",
        material="Alloy Steel",
    ),
    "sh-vn-brass-fillister-screw": _stock(
        "sh-vn-brass-fillister-screw",
        "Brass Fillister Head Slotted Screw",
        "90114A511",
        material="Brass",
    ),
    "sh-vn-fillister-screw-90280a108": _stock(
        "sh-vn-fillister-screw-90280a108",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A108",
    ),
    # R9-31: the eight platen-riding guide-lock screws; a low slotted pan head
    # (2026-10-11, as the book's lock plates show) clears the hanger arm where
    # the MHA-PD-VN-52 fillister head would not. R9-48: 3/8 long, so the guide's
    # through tap holds 1.5D at the worst case.
    "pd-vn-guide-lock-screw": _stock(
        "pd-vn-guide-lock-screw",
        "18-8 Stainless Steel Pan Head Slotted Screw",
        "91792A108",
        material="AISI 304",
    ),
    "mg-vn-magnifying-bracket-screw": _stock(
        "mg-vn-magnifying-bracket-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A078",
        material="AISI 304",
    ),
    "ms-vn-stop-plate-screw": _stock(
        "ms-vn-stop-plate-screw",
        "Brass Fillister Head Slotted Screw",
        "90114A124",
        material="Brass",
    ),
    "ch-vn-frame-side-screw": _stock(
        "ch-vn-frame-side-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A080",
        material="AISI 304",
    ),
    "fr-vn-frame-cross-screw": _stock(
        "fr-vn-frame-cross-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A837",
    ),
    "fr-vn-gooseneck-set-screw": _stock(
        "fr-vn-gooseneck-set-screw",
        "Steel Square-Head Cup-Point Set Screw",
        "91410A540",
    ),
    # #8-32 x 1 through the pen-hanger strap's clearance hole into the
    # MHA-PN-VN-54 nut and MHA-PN-VN-55 jam nut on the strap front.
    "pn-vn-hanger-screw": _stock(
        "pn-vn-hanger-screw",
        "Low-Strength Zinc-Plated Steel Hex Head Screw",
        "93075A199",
    ),
    "sm-vn-knife-hanger-stud": _stock(
        "sm-vn-knife-hanger-stud",
        "Knife-Hanger Bolt (18-8 Stainless Hex Screw, Cut to Length)",
        "92314A253",
        material="AISI 304",
    ),
    "sm-vn-knife-hanger-washer": _stock(
        "sm-vn-knife-hanger-washer",
        "18-8 Stainless Steel SAE No. 10 Flat Washer",
        "96659A104",
        material="AISI 304",
    ),
    "sm-vn-knife-mount-dowel": _stock(
        "sm-vn-knife-mount-dowel",
        "Alloy Steel Dowel Pin",
        "98381A473",
        material="Alloy Steel",
    ),
    "fr-vn-lag-screw": _stock(
        "fr-vn-lag-screw",
        "18-8 Stainless Steel Hex Head Screw",
        "92240A540",
        material="AISI 304",
    ),
    "ch-vn-bracket-hold-down-screw": _stock(
        "ch-vn-bracket-hold-down-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A196",
    ),
    "dt-vn-pedestal-hold-down-screw": _stock(
        "dt-vn-pedestal-hold-down-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A197",
    ),
    "dt-vn-pinion-strap-pin": _stock(
        "dt-vn-pinion-strap-pin",
        "1050-1095 Spring Steel Slotted Spring Pin",
        "98296A027",
    ),
    "pn-vn-pen-set-screw": _stock(
        "pn-vn-pen-set-screw",
        "Stainless Steel Flared-Collar Knurled-Head Thumb Screw",
        "99607A213",
        material="AISI 304",
    ),
    # The C45 black-oxide cup point, #4-40 x 3/16, locking the pen rod's
    # turned pivot end in the v-block.
    "pn-vn-pen-rod-set-screw": _stock(
        "pn-vn-pen-rod-set-screw",
        "Alloy Steel Cup-Tip Set Screw",
        "91375A105",
        material="Alloy Steel",
    ),
    # Brass #0-80 jam nut on the pen rod's top adjuster stud.
    "pn-vn-pen-adjust-nut": _stock(
        "pn-vn-pen-adjust-nut",
        "Brass Hex Nut",
        "92671A115",
        material="Brass",
    ),
    # Zinc-plated steel #8-32 hex nut on the hanger screw at the pen-hanger
    # strap's front face, and the thin small-pattern nut jammed against it.
    "pn-vn-pen-hanger-nut": _stock(
        "pn-vn-pen-hanger-nut",
        "Low-Strength Zinc-Plated Steel Hex Nut",
        "90480A009",
    ),
    "pn-vn-pen-hanger-jam-nut": _stock(
        "pn-vn-pen-hanger-jam-nut",
        "Zinc-Plated Steel Narrow-Profile Hex Nut",
        "90760A009",
    ),
    # Thin zinc-plated steel #10-24 nut jammed against the MHA-SM-03 boss
    # top face, locking the MHA-SM-VN-50 counter anchor.
    "sm-vn-boss-hook-jam-nut": _stock(
        "sm-vn-boss-hook-jam-nut",
        "#10-24 Zinc-Plated Steel Narrow-Profile Hex Nut",
        "90760A140",
    ),
    # The four platen-clip screws: brass #2-56 x 1/4, whose head stays inside
    # the clip's rail where the MHA-PD-VN-52 #4-40 head would overhang. A pan
    # head (2026-10-15): the 90114A124 fillister's least head left 0.05 mm of
    # bearing land over the clip's largest drilled #2 loose hole.
    "pd-vn-platen-clip-screw": _stock(
        "pd-vn-platen-clip-screw",
        "Brass Pan Head Slotted Screw",
        "92446A077",
        material="Brass",
    ),
    # MSC 40923906: 1/4-20 x 4 in (101.6 mm) supplied stock. Only the
    # MHA-DT-VN-61 modification applies dt_vn_post_mount_screw_spec.CUT_LENGTH_MM
    # as a reference trim, then matched-hole cut-to-fit/deburr acceptance.
    "dt-vn-post-mount-screw": _stock(
        "dt-vn-post-mount-screw",
        "Zinc-Plated Steel Slotted Fillister Head Machine Screw",
        "40923906",
        supplier="MSC Industrial Supply",
    ),
    # McMaster 90280A203: #8-32 x 1-1/2 in (38.1 mm) supplied stock.
    # The former 31.75-mm geometry was not this SKU's verified stock length.
    "dt-vn-slotted-screw": _stock(
        "dt-vn-slotted-screw",
        "Steel Narrow Fillister Head Slotted Screw",
        "90280A203",
    ),
    "sh-vn-thumb-screw": _stock(
        "sh-vn-thumb-screw",
        "Steel Raised Knurled-Head Thumb Screw",
        "91882A221",
    ),
    "ch-vn-spring-hook": _stock(
        "ch-vn-spring-hook",
        "Black-Oxide Steel #6-32 Routing Eyebolt (Trimmed Shank, Supplied Nut Omitted)",
        "9489T111",
    ),
    "sm-vn-boss-hook": _stock(
        "sm-vn-boss-hook",
        "Zinc-Plated Steel #10-24 Open Routing Eyebolt (Trimmed Shank)",
        "9490T1",
    ),
    "pd-vn-transgear-knob-drive-pin": _stock(
        "pd-vn-transgear-knob-drive-pin",
        "Alloy Steel Dowel Pin",
        "98381A433",
        material="Alloy Steel",
    ),
    "pd-vn-transgear-disc-screw": _stock(
        "pd-vn-transgear-disc-screw",
        "18-8 Stainless Steel Fillister Head Slotted Screw",
        "91794A055",
        material="AISI 304",
    ),
    "pd-vn-transgear-arm-plate-screw": _stock(
        "pd-vn-transgear-arm-plate-screw",
        "18-8 Stainless Steel Oval Head Slotted Screw",
        "91790A199",
        material="AISI 304",
    ),
    "pd-vn-transgear-arm-plate-locating-pin": _stock(
        "pd-vn-transgear-arm-plate-locating-pin",
        "Passivated 316 Stainless Steel ISO 2338-m6 Dowel Pin",
        "93600A189",
        material="AISI 304",  # native library stand-in; purchased grade remains 316
    ),
    "pd-vn-transgear-pivot-screw": _stock(
        "pd-vn-transgear-pivot-screw",
        "Transgear Pivot Screw (18-8 Stainless Socket Shoulder Screw, Faced to Fit)",
        "90325A174",
        material="AISI 304",
    ),
    "pd-vn-transgear-knob-cup-pin": _stock(
        "pd-vn-transgear-knob-cup-pin",
        "1050-1095 Spring Steel Slotted Spring Pin",
        "98296A031",
    ),
    "pd-vn-transgear-latch-pin": _stock(
        "pd-vn-transgear-latch-pin",
        "Alloy Steel Dowel Pin",
        "98381A474",
        material="Alloy Steel",
    ),
    # R9-68: E-style ring closing the disc cluster's float on the MHA-PD-23 pin.
    "pd-vn-transgear-retaining-ring": _stock(
        "pd-vn-transgear-retaining-ring",
        "Side-Mount External Retaining Ring",
        "97431A260",
    ),
    # MHA-PD-VN-63: one curved disc spring under the MHA-PD-VN-57 pivot screw's head;
    # high-carbon steel, the library's plain carbon steel.
    "pd-vn-transgear-pivot-spring": _stock(
        "pd-vn-transgear-pivot-spring",
        "Curved Disc Spring",
        "9715K43",
    ),
    # MHA-PD-VN-67: one DIN 988 shim under the MHA-PD-VN-57 head, on the spring (it
    # restores the spring room after the 9.5 bar's rearward growth); spring
    # steel, the library's plain carbon steel.
    "pd-vn-transgear-pivot-shim": _stock(
        "pd-vn-transgear-pivot-shim",
        "DIN 988 Spring Steel Shim",
        "98055A098",
    ),
    # MHA-DT-VN-68 / MHA-CH-VN-54 (#948 ruling R): one wave disc spring preloading each
    # bank north on its datum; steel and high-carbon steel, the library's
    # plain carbon steel.
    "dt-vn-cylinder-bank-spring": _stock(
        "dt-vn-cylinder-bank-spring",
        "Wave Disc Spring",
        "9714K392",
    ),
    "ch-vn-rocker-bank-spring": _stock(
        "ch-vn-rocker-bank-spring",
        "Wave Disc Spring",
        "9714K24",
    ),
    "ch-vn-rocker-thrust-washer": _stock(
        "ch-vn-rocker-thrust-washer",
        "Carbon Steel Ring Shim, 1/4 ID x 3/8 OD x 0.031",
        "3088A429",
    ),
    # MHA-MG-VN-52 / MHA-MG-VN-54 / MHA-MG-VN-55 (mg wheel rev 10): the magnifying wheel's
    # brass #4-40 nut and locknut and the two brass washers either side of
    # its hub.
    "mg-vn-wheel-axle-nut": _stock(
        "mg-vn-wheel-axle-nut",
        "Brass Hex Nut",
        "92671A005",
        material="Brass",
    ),
    "mg-vn-wheel-axle-back-washer": _stock(
        "mg-vn-wheel-axle-back-washer",
        "Brass Washer for Number 10 Screw Size",
        "92916A480",
        material="Brass",
    ),
    "mg-vn-wheel-axle-front-washer": _stock(
        "mg-vn-wheel-axle-front-washer",
        "Brass Washer for Number 4 Screw Size",
        "92916A250",
        material="Brass",
    ),
    "fr-vn-tube-frame-cap": _stock(
        "fr-vn-tube-frame-cap",
        "Metal Round Cap",
        "9275K141",
    ),
    # MHA-CH-06-TL-VN-53: the oblique trammel jig's CL locator, press-set above
    # the actual riser in the carrier's in-place-finished CL hole (shop
    # fixture hardware modelled for native mates and interference).
    "ch-rocker-arm-tl-vn-oblique-cl-dowel": _stock(
        "ch-rocker-arm-tl-vn-oblique-cl-dowel",
        "Alloy Steel Dowel Pin, 1/4 x 1 in",
        "98381A542",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-61: the oblique trammel jig's #8-32 X 3/4 SHCS (the
    # fastener table's RAIL_TO_BAR row); shop fixture hardware, modelled so
    # the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-vn-oblique-rail-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-rail-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A197",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-62: the oblique trammel jig's #8-32 X 5/8 SHCS (the
    # fastener table's BRACKET_TO_BAR row); shop fixture hardware, modelled so
    # the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-vn-oblique-bracket-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-bracket-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A196",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-64: the oblique trammel jig's M4 X 20 SHCS (the
    # fastener table's BLOCK_TO_CARRIAGE row); shop fixture hardware,
    # modelled so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-vn-oblique-carriage-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-carriage-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91290A168",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-65: the oblique trammel jig's #6-32 X 5/8 SHCS (the
    # fastener table's KP08_TO_BRACKET row); shop fixture hardware, modelled
    # so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-vn-oblique-kp08-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-kp08-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A150",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-66: the oblique trammel jig's #4-40 X 1/2 BHCS (the
    # fastener table's NUT_TO_FEED_BLOCK row), Olander 4C50BHCA; shop fixture
    # hardware, modelled so the jig assembly can mate it and run native
    # interference.
    "ch-rocker-arm-tl-vn-oblique-nut-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-nut-screw",
        "Alloy Steel Button Head Socket Cap Screw",
        "4C50BHCA",
        material="Alloy Steel",
        supplier="Olander",
    ),
    # MHA-CH-06-TL-VN-67: the oblique trammel jig's #4-40 X 5/8 flat head (the
    # fastener table's RISER_TO_CARRIER row), installed as bought; shop
    # fixture hardware, modelled so the jig assembly can mate it and run
    # native interference.
    "ch-rocker-arm-tl-vn-oblique-riser-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-riser-screw",
        "Stainless Steel Phillips Flat Head Screw",
        "91771A112",
        material="AISI 304",
    ),
    # MHA-CH-06-TL-VN-68: the oblique trammel jig's 1/4-20 X 7/8 SHCS (the
    # fastener table's CR_CLAMP row), used full length; shop fixture
    # hardware, modelled so the jig assembly can mate it and run native
    # interference.
    "ch-rocker-arm-tl-vn-oblique-clamp-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-clamp-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A541",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-69: the oblique trammel jig's 5/16-18 X 1 SHCS (the
    # fastener table's LEVER_TO_CARRIER row); shop fixture hardware, modelled
    # so the jig assembly can mate it and run native interference.
    "ch-rocker-arm-tl-vn-oblique-lever-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-lever-screw",
        "Black-Oxide Alloy Steel Socket Head Screw",
        "91251A583",
        material="Alloy Steel",
    ),
    # MHA-CH-06-TL-VN-71: the oblique trammel jig's 5/16 wedge-lock washer pairs
    # under the TL-VN-69 feed lever screws' heads (the fastener table's
    # LEVER_LOCK_WASHER row); shop fixture hardware, modelled so the jig
    # assembly can mate it and run native interference.
    "ch-rocker-arm-tl-vn-oblique-lever-washer": _stock(
        "ch-rocker-arm-tl-vn-oblique-lever-washer",
        "Extreme-Vibration-Resistant Wedge Lock Washer",
        "91812A230",
        material="AISI 304",  # native library stand-in; purchased grade is 316
    ),
    # AISI 304 below is a native-library surrogate for appearance/approximate
    # mass only. Supplier authority for the screw is 18-8 stainless, not a
    # certified 304 grade; the YAML material_specification owns it.
    "ch-rocker-arm-tl-vn-oblique-pivot-screw": _stock(
        "ch-rocker-arm-tl-vn-oblique-pivot-screw",
        "18-8 Stainless Steel Precision Shoulder Screw, Extended Thread, 3/8 x 1-1/2 in, 5/16-18",
        "BLTS40-0375-1500188P",
        material="AISI 304",
        supplier="Huyett",
    ),
    "ch-rocker-arm-tl-vn-oblique-pivot-spacer": _stock(
        "ch-rocker-arm-tl-vn-oblique-pivot-spacer",
        "6061 Aluminum Round Spacer, .382 ID x .625 OD x .625 in",
        "AS62-18-40",
        material="6061 Alloy",
        supplier="AluminumSpacers.com",
    ),
    # Full-hard low-carbon steel shims: the library's plain carbon steel (default).
    # The .004/.020 fitting stock is named on the sheet's FITTING STOCK line and
    # bought by the jig's buy list, not as this part.
    "ch-rocker-arm-tl-vn-oblique-pivot-shim": _stock(
        "ch-rocker-arm-tl-vn-oblique-pivot-shim",
        "Steel Shim, 3/8 ID x 5/8 OD x .008 in",
        "SHIM-0375-008",
        supplier="Huyett",
    ),
    # Hardened tool-steel gauge pin: the library's Alloy Steel stand-in.
    "ch-rocker-arm-tl-vn-oblique-hub-pin": _stock(
        "ch-rocker-arm-tl-vn-oblique-hub-pin",
        "Class Z Plug Gauge, NO-GO, size .4000 in, 2 in supply, cut to .79 in",
        "23065A855-23065A4",
        material="Alloy Steel",
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
