"""The release's HARDWARE.md: the Master Hardware Schedule for standard COTS
hardware, and the three-tier classification of every purchased part (#2886).

ASME Y14.24 separates purchased items by what a builder needs to buy or make a
substitute: standard normative hardware is fully defined by a generic
designation (tier 1, a schedule row), a proprietary or non-standard item by its
functional interface and performance bounds (tier 2, a specification-control
sheet), and a shop-altered item by its blank plus the shop's cuts (tier 3, an
altered-item sheet). ``TIERS`` classifies every purchased part with the reason;
``SCHEDULE`` carries each tier-1 row's generic designation and the pure
per-SKU sources of its seat envelope.

Nothing here is copied from a sheet or typed as a dimension: numbers, titles,
SKUs, quantities and suppliers are read from the part registry
(``cad/config/parts``) and the pure ``_mcmaster_*`` / ``*_spec`` providers the
part recipes already consume; assembly membership is the build graph's.
cut_release stages the document beside ASSEMBLY.md; run this module to print
it. Reads source and YAML only: no SolidWorks.
"""

from __future__ import annotations

import importlib
import math
import re
from dataclasses import dataclass
from enum import IntEnum
from functools import cache
from typing import Any

import _buildgraph as bg
import _config

DOCUMENT_NAME = "HARDWARE.md"
MM_PER_IN = 25.4


class Tier(IntEnum):
    STANDARD = 1  # schedule row in HARDWARE.md
    SPEC_CONTROL = 2  # specification-control sheet: interface + performance only
    ALTERED = 3  # altered-item sheet: MAKE FROM blank + shop cuts


# Every purchased part (``-vn-`` stems, plus fabricated parts made from a
# bought blank) with its tier and why. The oblique trammel jig's vendor parts
# are excluded: the jig family is being retired (owner ruling 2026-11-16).
TIERS: dict[str, tuple[Tier, str]] = {
    "ch-vn-bracket-hold-down-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "ch-vn-frame-side-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "ch-vn-fulcrum-set-screw": (
        Tier.STANDARD,
        "ASME B18.3 socket set screw, used as supplied",
    ),
    "ch-vn-rocker-thrust-washer": (
        Tier.STANDARD,
        "commodity ring shim defined by ID, OD and thickness",
    ),
    "dt-cone-gear-tl-vn-arbor-nut": (
        Tier.STANDARD,
        "ASME B18.2.2 hex nut, used as supplied",
    ),
    "dt-vn-cone-tip-block-screw": (
        Tier.STANDARD,
        "ASME B18.3 socket head cap screw, used as supplied",
    ),
    "dt-vn-cone-tip-pinch-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "dt-vn-crank-seat-drive-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "dt-vn-keeper-chain-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "dt-vn-locating-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "dt-vn-pedestal-hold-down-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "dt-vn-pinion-strap-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 slotted spring pin, used as supplied",
    ),
    "dt-vn-slotted-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "fr-vn-frame-cross-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "fr-vn-gooseneck-set-screw": (
        Tier.STANDARD,
        "ASME B18.6.2 square head set screw, used as supplied",
    ),
    "fr-vn-lag-screw": (Tier.STANDARD, "ASME B18.2.1 hex head screw, used as supplied"),
    "mg-vn-magnifying-bracket-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "mg-vn-wheel-axle-back-washer": (
        Tier.STANDARD,
        "commodity flat washer defined by ID, OD and thickness",
    ),
    "mg-vn-wheel-axle-front-washer": (
        Tier.STANDARD,
        "commodity flat washer defined by ID, OD and thickness",
    ),
    "mg-vn-wheel-axle-nut": (
        Tier.STANDARD,
        "ASME B18.6.3 machine screw nut, used as supplied",
    ),
    "ms-vn-stop-plate-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "pd-vn-chain-connecting-link": (
        Tier.STANDARD,
        "ASME B29.1 No. 25 connecting link, used as supplied",
    ),
    "pd-vn-guide-lock-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "pd-vn-platen-clip-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "pd-vn-transgear-arm-plate-locating-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "pd-vn-transgear-arm-plate-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "pd-vn-transgear-cluster-shim": (
        Tier.STANDARD,
        "commodity shim defined by ID, OD and thickness",
    ),
    "pd-vn-transgear-collar-flat-pin": (
        Tier.STANDARD,
        "commodity 18-8 dowel pin defined by diameter and length",
    ),
    "pd-vn-transgear-hub-key-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "pd-vn-transgear-knob-cup-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 slotted spring pin, used as supplied",
    ),
    "pd-vn-transgear-knob-drive-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "pd-vn-transgear-latch-pin": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "pd-vn-transgear-retaining-ring": (
        Tier.STANDARD,
        "commodity E-style external ring sized by its shaft",
    ),
    "pn-vn-hanger-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 hex head machine screw, used as supplied",
    ),
    "pn-vn-pen-adjust-nut": (
        Tier.STANDARD,
        "ASME B18.6.3 machine screw nut, used as supplied",
    ),
    "pn-vn-pen-hanger-jam-nut": (
        Tier.STANDARD,
        "commodity thin hex nut defined by thread, AF and thickness",
    ),
    "pn-vn-pen-hanger-nut": (
        Tier.STANDARD,
        "ASME B18.6.3 machine screw nut, used as supplied",
    ),
    "sh-vn-arbor-set-screw": (
        Tier.STANDARD,
        "ASME B18.3 socket set screw, used as supplied",
    ),
    "sh-vn-brass-fillister-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "sh-vn-chain-link": (
        Tier.STANDARD,
        "ASME B29.1 No. 25 roller chain, used as supplied",
    ),
    "sh-vn-clamp-screw": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "sh-vn-fillister-screw-90280a108": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "sh-vn-fillister-screw-91794a055": (
        Tier.STANDARD,
        "ASME B18.6.3 slotted machine screw, used as supplied",
    ),
    "sh-vn-music-wire": (
        Tier.STANDARD,
        "ASTM A228 music wire; cut and formed in the assembly steps",
    ),
    "sh-vn-pivot-pin": (
        Tier.STANDARD,
        "commodity 18-8 dowel pin defined by diameter and length",
    ),
    "sm-vn-knife-hanger-washer": (
        Tier.STANDARD,
        "ASME B18.21.1 SAE plain washer, used as supplied",
    ),
    "sm-vn-knife-mount-dowel": (
        Tier.STANDARD,
        "ASME B18.8.2 hardened dowel pin, used as supplied",
    ),
    "ch-vn-channel-spring-installed": (
        Tier.SPEC_CONTROL,
        "extension spring: rate, free length, hook form and max OD govern",
    ),
    "ch-vn-rocker-bank-spring": (
        Tier.SPEC_CONTROL,
        "wave disc spring: load at working height, ID/OD govern",
    ),
    "dt-vn-cylinder-bank-spring": (
        Tier.SPEC_CONTROL,
        "wave disc spring: load at working height, ID/OD govern",
    ),
    "pd-vn-transgear-pivot-spring": (
        Tier.SPEC_CONTROL,
        "curved disc spring: load at working height, ID/OD govern",
    ),
    "sm-vn-counter-spring": (
        Tier.SPEC_CONTROL,
        "extension spring: rate, free length, loop form and max OD govern",
    ),
    "dt-vn-cone-lock-knob": (
        Tier.SPEC_CONTROL,
        "knurled thumb screw: no dimensional standard; head and thread govern",
    ),
    "sh-vn-thumb-screw": (
        Tier.SPEC_CONTROL,
        "knurled thumb screw: no dimensional standard; head and thread govern",
    ),
    "pn-vn-pen-set-screw": (
        Tier.SPEC_CONTROL,
        "flared-collar thumb screw: no dimensional standard",
    ),
    "dt-vn-cone-pivot-screw": (
        Tier.SPEC_CONTROL,
        "slotted precision shoulder screw: no ASME standard; shoulder fit governs",
    ),
    "sm-vn-gooseneck-shoulder-screw": (
        Tier.SPEC_CONTROL,
        "slotted precision shoulder screw: no ASME standard; shoulder fit governs",
    ),
    "dt-vn-keeper-chain": (
        Tier.SPEC_CONTROL,
        "jack chain trade size: no dimensional standard",
    ),
    "fr-vn-tube-frame-cap": (
        Tier.SPEC_CONTROL,
        "push-on tube cap: fit on the tube OD governs",
    ),
    "pn-vn-pen-marker": (
        Tier.SPEC_CONTROL,
        "proprietary marker: barrel diameter and tip govern",
    ),
    "ch-vn-spring-hook": (Tier.ALTERED, "eyebolt shank cut and its nut discarded"),
    "sm-vn-boss-hook": (Tier.ALTERED, "eyebolt shank trimmed"),
    "dt-vn-post-mount-screw": (Tier.ALTERED, "screw stock cut to length"),
    "dt-vn-crank-hub-pin": (Tier.ALTERED, "dowel cut to length"),
    "dt-vn-cone-shaft-key": (Tier.ALTERED, "key stock cut to length"),
    "sm-vn-knife-hanger-stud": (Tier.ALTERED, "hex screw cut to length"),
    "pd-vn-transgear-pivot-screw": (Tier.ALTERED, "shoulder screw faced to fit"),
    "sh-vn-clamping-kit-hardware": (
        Tier.ALTERED,
        "kit hold-down stud reworked; other members as supplied",
    ),
    "dt-cone-tip-end-screw": (
        Tier.ALTERED,
        "fillister screw drilled and reamed (MHA-DT-39)",
    ),
    "pd-feed-rack": (
        Tier.ALTERED,
        "rack stock cut to length, drilled and tapped (MHA-PD-26)",
    ),
    "pd-transgear-removable": (
        Tier.ALTERED,
        "sprocket blanks: hub turned, bored and drilled (MHA-PD-09)",
    ),
}


@dataclass(frozen=True, slots=True)
class Row:
    """One tier-1 schedule row: the generic designation a builder buys to, the
    governing standard, and the seat envelope as ``(label, module, expr)``
    sources. ``expr`` names a module attribute (``HEAD_DIA``, ``DIMS.od_max``,
    ``FILLISTER_SIZE[3]``, ``2*ROLLER_R``) or a ``Supplier*`` reference
    dimension; every value
    is in millimetres."""

    designation: str
    standard: str
    envelope: tuple[tuple[str, str, str], ...]


def _head(
    module: str, width: str = "SupplierHeadDiameter", corners: int = 0
) -> tuple[tuple[str, str, str], ...]:
    """Head envelope: its diameter, or across the corners of a ``corners``-sided
    head given across flats."""
    if corners:
        across = ("head AC", module, f"{1 / math.cos(math.pi / corners)!r}*{width}")
    else:
        across = ("head Ø", module, width)
    return (across, ("head H", module, "SupplierHeadHeight"))


def _pin(module: str, size: str = "DOWEL_SIZE") -> tuple[tuple[str, str, str], ...]:
    return (("Ø", module, f"{size}[0]"), ("L", module, f"{size}[1]"))


def _nut(module: str) -> tuple[tuple[str, str, str], ...]:
    hex_corners = f"{1 / math.cos(math.pi / 6)!r}*ACROSS_FLATS"
    return (("AC", module, hex_corners), ("T", module, "THICKNESS"))


SCHEDULE: dict[str, Row] = {
    "ch-vn-bracket-hold-down-screw": Row(
        "#8-32 UNC-2A x 5/8 slotted narrow fillister head machine screw, zinc-plated steel",
        "ASME B18.6.3",
        _head("_mcmaster_90280a196"),
    ),
    "ch-vn-frame-side-screw": Row(
        "#2-56 UNC-2A x 7/16 slotted fillister head machine screw, 18-8 stainless",
        "ASME B18.6.3",
        _head("_mcmaster_91794a080"),
    ),
    "ch-vn-fulcrum-set-screw": Row(
        "#1-72 UNF-3A x 5/32 hex socket set screw, cup point, alloy steel",
        "ASME B18.3",
        (("L", "_mcmaster_91375a942", "SupplierLength"),),
    ),
    "ch-vn-rocker-thrust-washer": Row(
        "Ring shim 1/4 ID x 3/8 OD x .031, carbon steel",
        "—",
        (
            ("OD", "_mcmaster_3088a429", "DIMS.od_max"),
            ("T", "_mcmaster_3088a429", "DIMS.thickness_max"),
        ),
    ),
    "dt-cone-gear-tl-vn-arbor-nut": Row(
        "1/4-28 UNF-2B hex nut, zinc-plated steel",
        "ASME B18.2.2",
        _nut("_mcmaster_95462a505"),
    ),
    "dt-vn-cone-tip-block-screw": Row(
        "#4-40 UNC-3A x 3/8 hex socket head cap screw, black-oxide alloy steel",
        "ASME B18.3",
        _head("_mcmaster_91251a108"),
    ),
    "dt-vn-cone-tip-pinch-screw": Row(
        "#4-40 UNC-2A x 5/8 slotted fillister head machine screw, 18-8 stainless",
        "ASME B18.6.3",
        _head("_mcmaster_91794a112"),
    ),
    "dt-vn-crank-seat-drive-pin": Row(
        "Ø3/32 x 1/4 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a434"),
    ),
    "dt-vn-keeper-chain-screw": Row(
        "#2-56 UNC-2A x 1/4 slotted binding head machine screw, brass",
        "ASME B18.6.3",
        _head("_mcmaster_92443a077"),
    ),
    "dt-vn-locating-pin": Row(
        "Ø1/16 x 3/8 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a417"),
    ),
    "dt-vn-pedestal-hold-down-screw": Row(
        "#8-32 UNC-2A x 3/4 slotted narrow fillister head machine screw, zinc-plated steel",
        "ASME B18.6.3",
        _head("_mcmaster_90280a197"),
    ),
    "dt-vn-pinion-strap-pin": Row(
        "Ø1/16 x 1/2 slotted spring pin, spring steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98296a027", "SPRING_PIN_SIZE"),
    ),
    "dt-vn-slotted-screw": Row(
        "#8-32 UNC-2A x 1-1/2 slotted narrow fillister head machine screw, zinc-plated steel",
        "ASME B18.6.3",
        _head("_mcmaster_90280a203"),
    ),
    "fr-vn-frame-cross-screw": Row(
        "#10-32 UNF-2A x 1-3/4 slotted narrow fillister head machine screw, zinc-plated steel",
        "ASME B18.6.3",
        _head("_mcmaster_90280a837"),
    ),
    "fr-vn-gooseneck-set-screw": Row(
        "1/4-20 UNC-2A x 3/4 square head set screw, cup point, steel",
        "ASME B18.6.2",
        _head("_mcmaster_91410a540", "SupplierHeadWidth", corners=4),
    ),
    "fr-vn-lag-screw": Row(
        "1/4-20 UNC-2A x 3/4 hex head screw, fully threaded, 18-8 stainless",
        "ASME B18.2.1",
        _head("_mcmaster_92240a540", "SupplierHeadWidth", corners=6),
    ),
    "mg-vn-magnifying-bracket-screw": Row(
        "#2-56 UNC-2A x 1/4 slotted fillister head machine screw, 18-8 stainless",
        "ASME B18.6.3",
        _head("_mcmaster_91794a078"),
    ),
    "mg-vn-wheel-axle-back-washer": Row(
        "#10 flat washer, brass",
        "—",
        (
            ("OD", "mg_vn_wheel_axle_back_washer_spec", "OD"),
            ("T", "mg_vn_wheel_axle_back_washer_spec", "THICKNESS_MAX"),
        ),
    ),
    "mg-vn-wheel-axle-front-washer": Row(
        "#4 flat washer, brass",
        "—",
        (
            ("OD", "mg_vn_wheel_axle_front_washer_spec", "OD"),
            ("T", "mg_vn_wheel_axle_front_washer_spec", "THICKNESS_MAX"),
        ),
    ),
    "mg-vn-wheel-axle-nut": Row(
        "#4-40 UNC-2B hex machine screw nut, brass",
        "ASME B18.6.3",
        _nut("mg_vn_wheel_axle_nut_spec"),
    ),
    "ms-vn-stop-plate-screw": Row(
        "#2-56 UNC-2A x 1/4 slotted fillister head machine screw, brass",
        "ASME B18.6.3",
        _head("_mcmaster_90114a124"),
    ),
    "pd-vn-chain-connecting-link": Row(
        "No. 25 roller chain connecting link, spring-clip type, steel", "ASME B29.1", ()
    ),
    "pd-vn-guide-lock-screw": Row(
        "#4-40 UNC-2A x 3/8 slotted pan head machine screw, 18-8 stainless",
        "ASME B18.6.3",
        _head("_mcmaster_91792a108"),
    ),
    "pd-vn-platen-clip-screw": Row(
        "#2-56 UNC-2A x 1/4 slotted pan head machine screw, brass",
        "ASME B18.6.3",
        _head("_mcmaster_92446a077"),
    ),
    "pd-vn-transgear-arm-plate-locating-pin": Row(
        "Ø3/32 x 5/16 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a435"),
    ),
    "pd-vn-transgear-arm-plate-screw": Row(
        "#8-32 UNC-2A x 1 slotted oval head machine screw, 18-8 stainless",
        "ASME B18.6.3",
        (
            ("head Ø", "pd_vn_transgear_arm_plate_screw_spec", "HEAD_DIA"),
            ("head H", "pd_vn_transgear_arm_plate_screw_spec", "HEAD_H"),
        ),
    ),
    "pd-vn-transgear-cluster-shim": Row(
        "Shoulder-screw shim 1/8 ID x 1/4 OD x .005, 18-8 stainless",
        "—",
        (
            ("OD", "_mcmaster_94773a606", "DIMS.od_max"),
            ("T", "_mcmaster_94773a606", "DIMS.thickness_max"),
        ),
    ),
    "pd-vn-transgear-collar-flat-pin": Row(
        "Ø1/16 x 3/16 dowel pin, 18-8 stainless", "—", _pin("_mcmaster_90145a414")
    ),
    "pd-vn-transgear-hub-key-pin": Row(
        "Ø1/16 x 5/16 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a416"),
    ),
    "pd-vn-transgear-knob-cup-pin": Row(
        "Ø1/16 x 5/8 slotted spring pin, spring steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98296a031", "SPRING_PIN_SIZE"),
    ),
    "pd-vn-transgear-knob-drive-pin": Row(
        "Ø3/32 x 3/16 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a433"),
    ),
    "pd-vn-transgear-latch-pin": Row(
        "Ø1/8 x 7/8 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a474"),
    ),
    "pd-vn-transgear-retaining-ring": Row(
        "E-style external retaining ring for Ø1/8 shaft, spring steel",
        "—",
        (
            ("OD", "pd_vn_transgear_retaining_ring_spec", "OD"),
            ("T", "pd_vn_transgear_retaining_ring_spec", "THICKNESS"),
        ),
    ),
    "pn-vn-hanger-screw": Row(
        "#8-32 UNC-2A x 1 hex head machine screw, fully threaded, zinc-plated steel",
        "ASME B18.6.3",
        _head("_mcmaster_93075a199", "SupplierHeadWidth", corners=6),
    ),
    "pn-vn-pen-adjust-nut": Row(
        "#0-80 UNF-2B hex machine screw nut, brass",
        "ASME B18.6.3",
        _nut("_mcmaster_92671a115"),
    ),
    "pn-vn-pen-hanger-jam-nut": Row(
        "#8-32 UNC-2B thin hex nut, zinc-plated steel", "—", _nut("_mcmaster_90760a009")
    ),
    "pn-vn-pen-hanger-nut": Row(
        "#8-32 UNC-2B hex machine screw nut, zinc-plated steel",
        "ASME B18.6.3",
        _nut("_mcmaster_90480a009"),
    ),
    "sh-vn-arbor-set-screw": Row(
        "#4-40 UNC-3A x 1/4 hex socket set screw, cup point, alloy steel",
        "ASME B18.3",
        (("L", "sh_vn_arbor_set_screw_spec", "LENGTH"),),
    ),
    "sh-vn-brass-fillister-screw": Row(
        "#4-40 UNC-2A x 1/4 slotted fillister head machine screw, brass",
        "ASME B18.6.3",
        (
            ("head Ø", "sh_vn_brass_fillister_screw_spec", "HEAD_DIA"),
            ("head H", "sh_vn_brass_fillister_screw_spec", "HEAD_H"),
        ),
    ),
    "sh-vn-chain-link": Row(
        "No. 25 single-strand roller chain, 1/4 pitch, steel",
        "ASME B29.1",
        (
            ("plate H", "_chain", "PLATE_HEIGHT"),
            ("over pins", "sh_vn_chain_link_spec", "2*PIN_HALF_LEN"),
        ),
    ),
    "sh-vn-clamp-screw": Row(
        "#8-32 UNC-2A x 1-1/4 slotted narrow fillister head machine screw, zinc-plated steel",
        "ASME B18.6.3",
        (
            ("head Ø", "sh_vn_clamp_screw_spec", "FILLISTER_SIZE[3]"),
            ("head H", "sh_vn_clamp_screw_spec", "FILLISTER_SIZE[2]"),
        ),
    ),
    "sh-vn-fillister-screw-90280a108": Row(
        "#4-40 UNC-2A x 3/8 slotted narrow fillister head machine screw, zinc-plated steel",
        "ASME B18.6.3",
        (
            ("head Ø", "dt_swing_stop_screw_spec", "HEAD_DIA_MAX_MM"),
            ("head H", "dt_swing_stop_screw_spec", "HEAD_TOTAL_MAX_MM"),
        ),
    ),
    "sh-vn-fillister-screw-91794a055": Row(
        "#0-80 UNF-2A x 1/4 slotted fillister head machine screw, 18-8 stainless",
        "ASME B18.6.3",
        _head("_mcmaster_91794a055"),
    ),
    "sh-vn-music-wire": Row(
        "Ø.008 music wire, ASTM A228 spring steel",
        "ASTM A228",
        (("Ø", "_mcmaster_9666k142", "DIA_MAX"),),
    ),
    "sh-vn-pivot-pin": Row(
        "Ø5/64 x 5/16 dowel pin, 18-8 stainless",
        "—",
        (
            ("Ø", "sh_vn_pivot_pin_spec", "PIN_DIA_LIMITS[1]"),
            ("L", "sh_vn_pivot_pin_spec", "PIN_LENGTH"),
        ),
    ),
    "sm-vn-knife-hanger-washer": Row(
        "#10 SAE plain washer, 18-8 stainless",
        "ASME B18.21.1",
        (
            ("OD", "_mcmaster_96659a104", "DIMS.od_max"),
            ("T", "_mcmaster_96659a104", "DIMS.thickness_max"),
        ),
    ),
    "sm-vn-knife-mount-dowel": Row(
        "Ø1/8 x 3/4 hardened dowel pin, alloy steel",
        "ASME B18.8.2",
        _pin("_mcmaster_98381a473"),
    ),
}

_PATH = re.compile(r"(\w+)|\[(\d+)\]")


def envelope_mm(module: str, expr: str) -> float:
    """One envelope value from its pure provider, in millimetres."""
    provider = importlib.import_module(module)
    factor, _, path = expr.rpartition("*")
    if path.startswith("Supplier"):
        found = [
            abs(value)
            for name, value, *_ in provider.SUPPLIER_REFERENCE_DIMENSIONS
            if name == path
        ]
        if len(found) != 1:
            raise KeyError(f"{module}: no single {path} supplier reference dimension")
        return float(found[0]) * float(factor or 1)
    value: Any = provider
    for name, index in _PATH.findall(path):
        value = getattr(value, name) if name else value[int(index)]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{module}.{expr} is not a positive length: {value!r}")
    return float(value) * float(factor or 1)


def _envelope_text(row: Row) -> str:
    if not row.envelope:
        return f"per {row.standard}"
    return " x ".join(
        f"{label} {math.ceil(envelope_mm(module, expr) / MM_PER_IN * 1000 - 1e-6) / 1000:.3f}"
        for label, module, expr in row.envelope
    )


@cache
def used_in() -> dict[str, tuple[str, ...]]:
    """Dashed part stem -> dashed assemblies whose builder references it. A
    machine part lists machine assemblies only; tooling lists its fixture."""
    found: dict[str, list[str]] = {}
    for assembly in bg.ASSEMBLY_ORDER:
        for stem in bg.references_of(assembly):
            if bg.is_shop_fixture(assembly) and not bg.is_shop_fixture(stem):
                continue
            found.setdefault(stem.replace("_", "-"), []).append(
                assembly.replace("_", "-")
            )
    return {stem: tuple(assemblies) for stem, assemblies in found.items()}


def purchased_parts() -> frozenset[str]:
    """Registry stems a tier must cover: every ``-vn-`` part and every
    fabricated part whose registry row names a bought supplier SKU, outside the
    retired oblique trammel jig. ``TIERS`` may name more (a reworked blank the
    registry describes only in prose, such as MHA-PD-09)."""
    return frozenset(
        stem
        for stem, row in _config.parts().items()
        if "-tl-vn-oblique-" not in stem
        and ("-vn-" in stem or row.get("supplier_skus"))
    )


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|")


def markdown() -> str:
    lines = [
        "# Master Hardware Schedule",
        "",
        "Standard hardware the machine uses as supplied (ASME Y14.24 tier 1). "
        "Buy to the generic designation; the example SKU is the part the CAD "
        "models. Fits (thread, pin diameter) come from the designation and its "
        "standard. The seat envelope bounds the space the part may occupy "
        "(heads and nuts across corners): the catalogue maximum where its "
        "dimension provider records one, otherwise the modelled catalogue size "
        "the assembly clearance checks use, rounded up to 0.001 in; a substitute "
        "must not exceed it. Inches.",
        "",
        "| Number | Part | Designation | Standard | Seat envelope (in) | Qty | Used in | Example SKU |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for stem, row in sorted(
        SCHEDULE.items(), key=lambda item: _config.parts(item[0])["number"]
    ):
        part = _config.parts(stem)
        skus = ", ".join(str(sku) for sku in part.get("supplier_skus", ()))
        supplier = part.get("supplier", "McMaster-Carr")
        lines.append(
            "| "
            + " | ".join(
                _cell(cell)
                for cell in (
                    part["number"],
                    part.get("title") or part.get("stock_name"),
                    row.designation,
                    row.standard,
                    _envelope_text(row),
                    part["quantity"],
                    ", ".join(used_in().get(stem, ())) or "—",
                    f"{supplier} {skus}",
                )
            )
            + " |"
        )
    lines += [
        "",
        "Qty is the registry total. Used in lists the machine assemblies that "
        "use the part; a shop-tooling (`TL`) part lists its fixture instead.",
        "",
        "Non-standard purchased items (tier 2) and shop-altered purchased items "
        "(tier 3) have their own drawing sheets in `slddrw/`:",
        "",
        "| Part | Tier | Why |",
        "|---|---:|---|",
    ]
    for stem, (tier, reason) in sorted(
        TIERS.items(), key=lambda item: (item[1][0], item[0])
    ):
        if tier is not Tier.STANDARD:
            lines.append(
                f"| {_config.parts(stem)['number']} `{stem}` | {int(tier)} | {_cell(reason)} |"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(markdown(), end="")
