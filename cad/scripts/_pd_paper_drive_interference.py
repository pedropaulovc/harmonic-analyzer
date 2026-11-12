"""Explicit, volume-bounded interference-fit contract for the paper drive.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_pd_paper_drive_assembly (and the
assemblies that contain it) and verify_soundness:pd_paper_drive fold this
module, so it imports only what its own pairs need.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from _sprocket_seat_geometry import DRIVE_PIN_DIA as _SEAT_PIN_DIA
from _sprocket_seat_geometry import DRIVE_PIN_HOLE_DIA as _SEAT_PIN_HOLE_DIA


def _cross_pin_overlap_mm3(pin_od: float, pin_id: float, shaft_d: float) -> float:
    """Volume a tube pin lying diametrally across a solid shaft shares with it:
    the perpendicular-cylinder intersection at its OD less that at its ID.
    _holes.cross_hole_volume_mm3's trapezoid integral, restated so this
    table stays clear of the Hole Wizard helpers."""

    def solid(pin_d: float, n: int = 20001) -> float:
        r, big_r = pin_d / 2.0, shaft_d / 2.0
        dx = 2.0 * r / (n - 1)
        total = 0.0
        for i in range(n):
            x = -r + i * dx
            weight = 0.5 if i in (0, n - 1) else 1.0
            total += (
                weight
                * 4.0
                * math.sqrt(max(big_r**2 - x * x, 0.0))
                * math.sqrt(max(r**2 - x * x, 0.0))
            )
        return total * dx

    return solid(pin_od) - solid(pin_id)


# MHA-PD-VN-62 (98296A031), a 1/16-in tube with a 0.012-in wall, 5/8 long, lies
# diametrally across the MHA-PD-08 journal's rear end and the MHA-PD-16 cup ring,
# in a hole match-drilled through both at assembly and not modelled (R9-70,
# K-1): its chord through the journal, and the rest of its length in the cup
# (its ends stay inside the cup's O.D.).
_CUP_PIN_OD = 25.4 / 16.0
_CUP_PIN_ID = _CUP_PIN_OD - 2.0 * 0.012 * 25.4
_CUP_PIN_JOURNAL_MM3 = _cross_pin_overlap_mm3(_CUP_PIN_OD, _CUP_PIN_ID, 6.3246)
_CUP_PIN_CUP_MM3 = (
    math.pi / 4.0 * (_CUP_PIN_OD**2 - _CUP_PIN_ID**2) * (5.0 * 25.4 / 8.0)
    - _CUP_PIN_JOURNAL_MM3
)

# MHA-PD-VN-61, McMaster 97431A240: three prong arcs on its free diameter,
# atan(3/4) of the turn each (diag_build_97431A240's outline, the 97431A260
# replica's law: the window prongs from 90 to 126.87 deg, the far one
# +/-atan(1/3)).
_RING_PRONG_SHARE = 3.0 * math.atan(0.75) / (2.0 * math.pi)


# Pattern instances are numbered by seed creation while the two backs and
# guides are numbered by insertion order, so their suffixes cross or interleave.
#
# The transgear rows (CONTRACT-paper-drive round 10, R9-68): every stock
# screw carries its thread at the basic major, and every receiving tap is
# cut at its tap drill, so each bound is the smooth annulus over the span
# where the major body lies inside the receiver.  Sizes and spans are
# literals, as the drive train's MHA-DT-32 row, so this table does not re-key
# on a transgear spec; test_pd_paper_drive_interference_contracts pins each to
# its owner.
# Pairs with NO row, modelled line to line or with clearance, which the gate
# reads as contact: the MHA-PD-17 hub's plain bore on the sleeve's Ø9 boss,
# the MHA-PD-VN-69 key pin's side clear of the sleeve's flat (#2409), the
# MHA-PD-VN-58 dowel in the arm's Ø3.175 ream, the sleeve and both
# bushings on the MHA-PD-23 pin (Ø3.9), the disc bore on the boss (Ø9), the
# knob journal in the plate bore (Ø6.3246), the drive collar's round bore on
# the core (Ø4.8768), the MHA-PD-VN-70 pin's crest clear of the core's flat
# and its faced rear end flush on F, the MHA-PD-VN-54 dowels in the T24's Ø2.5
# holes, every screw in its
# clearance hole, and the MHA-PD-14 latch hook: its base on the bar's back
# face under the MHA-PD-VN-59 heads, their shanks through its Ø3.2 holes, and
# the MHA-PD-VN-58 pin through its Ø3.3 pin hole.
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    # The bar-clamp screws: the receiver length past bar, front arc and the
    # 0.5 grip gap (build_pd_paper_drive_assembly's clamp stack).
    **numbered_pairs(
        "sh-vn-clamp-screw",
        range(1, 3),
        "sh-column-clamp-back",
        smooth_annulus_limit_mm3(4.1656, 3.454, 8.5124),
        second_number=2,
    ),
    **numbered_pairs(
        "sh-vn-clamp-screw",
        range(3, 5),
        "sh-column-clamp-back",
        smooth_annulus_limit_mm3(4.1656, 3.454, 8.5124),
    ),
    # MHA-PD-VN-65 #2-56 clip screws: 6.35 shank - 0.8 clip sheet = 5.55 in the
    # platen's through tap (3.85 plate + 1.70 rear boss).
    **numbered_pairs(
        "pd-vn-platen-clip-screw",
        range(1, 5),
        "pd-platen",
        smooth_annulus_limit_mm3(THREAD_MAJOR_MM["#2-56"], TAP_DRILL_MM["#2-56"], 5.55),
    ),
    # MHA-PD-VN-52 guide screws: seed -1, then the grid -2..-10, alternating
    # between the two guide rails.
    **numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(1, 11, 2),
        "pd-platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
    ),
    **numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(2, 11, 2),
        "pd-platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
        second_number=2,
    ),
    # MHA-PD-VN-60 guide-lock screws (R9-31, R9-48): seeds -1/-2, then the grid
    # -3..-8; each 9.525 shank passes the 1.5875 (1/16 sheet) lock plate into
    # the guide's rear through tap.
    **numbered_pairs(
        "pd-vn-guide-lock-screw",
        (1, 2, 4, 7),
        "pd-platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 7.9375),
    ),
    **numbered_pairs(
        "pd-vn-guide-lock-screw",
        (3, 5, 6, 8),
        "pd-platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 7.9375),
        second_number=2,
    ),
    # MHA-PD-VN-56 #8-32 x 5/8 (pd_vn_transgear_arm_plate_screw_spec; from the top of the
    # oval head's bevel, flush in the plate's countersink) through the 5.0038
    # plate's Ø5.7912 clearance, cut flush with the arm's front face (R9-44): the
    # cut length 12.9413 - 5.0038 = the arm's 7.9375 in its #29 through tap.
    **numbered_pairs(
        "pd-vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm",
        smooth_annulus_limit_mm3(4.1656, 3.454, 12.9413 - 5.0038),
    ),
    # MHA-PD-VN-57 (pd_vn_transgear_pivot_screw_spec, 90325A174 faced to fit) in the
    # support bar's THROUGH #8-32 tap: its fitted 9.144 thread less the 1.1938
    # neck flat under the shoulder, whose Ø3.02 stays inside the #29 drill --
    # the full thread plus the 45° ramp back to the major (the MHA-DT-32 row's
    # relief-and-lead-cone reading), 7.9502 of overlap; the faced tip stands
    # inside the front face. The contract's engagement (transgear_hanger_joints)
    # counts full thread only, less one pitch at the faced tip.
    frozenset(
        ("pd-vn-transgear-pivot-screw-1", "pd-support-bar-1")
    ): smooth_annulus_limit_mm3(4.1656, 3.454, 9.144 - 1.1938),
    # MHA-SH-VN-52 #4-40 x 3/8 (pd_latch_hook_bracket_screw_spec) through the
    # MHA-PD-14 hook's .032 base (Ø.128 clearance): 9.525 - 0.8128 = 8.7122 in
    # the support bar's #43 taps.
    **numbered_pairs(
        "sh-vn-fillister-screw-90280a108",
        range(1, 3),
        "pd-support-bar",
        smooth_annulus_limit_mm3(2.8448, 2.261, 9.525 - 0.8128),
    ),
    # MHA-PD-23's press land (pd_transgear_pin_spec, Ø.1266 REF) pressed into
    # the arm's .126 ream (pd_transgear_arm_geometry) over its 7.366 length:
    # the press (#2415; the journal passes the ream clear).
    frozenset(("pd-transgear-pin-1", "pd-transgear-arm-1")): smooth_annulus_limit_mm3(
        3.21564, 3.2004, 7.366
    ),
    # The two MHA-PD-VN-64 dowels (pd_vn_transgear_arm_plate_locating_pin_spec,
    # 3/32 = Ø2.38125 model) pressed into the arm's Ø2.3622 through reams
    # (pd_transgear_arm_geometry); _transgear_arm_plate_locating_interface
    # owns the 1.7018 proud set in their 7.9375 - 1.7018 insertion: the press.
    # They slip in the plate's Ø2.4003 holes, so that pair has no row.
    **numbered_pairs(
        "pd-vn-transgear-arm-plate-locating-pin",
        range(1, 3),
        "pd-transgear-arm",
        smooth_annulus_limit_mm3(2.38125, 2.3622, 7.9375 - 1.7018),
    ),
    # MHA-PD-20 (pd_transgear_pivot_spacer_spec, Ø.1850 ream) pressed on the
    # MHA-PD-VN-57 Ø4.7625 shoulder over its whole 5.0 length (R9-71): the press.
    frozenset(("pd-transgear-pivot-spacer-1", "pd-vn-transgear-pivot-screw-1")): (
        smooth_annulus_limit_mm3(4.7625, 4.699, 5.0)
    ),
    # MHA-PD-VN-61 (pd_vn_transgear_retaining_ring_spec, McMaster 97431A240)
    # in the MHA-PD-23 groove: the ring as McMaster ships it, its prongs on
    # the Ø2.3876 free diameter, 0.0127 inside the Ø2.413 groove floor: the
    # grip, over the prong arcs (above) and the 0.381 thickness.  The
    # prong-corner fillets only shorten the arcs (the 97431A260 replica's run
    # 20261002T153039266Z read 0.72 of its bound).
    frozenset(
        ("pd-vn-transgear-retaining-ring-1", "pd-transgear-pin-1")
    ): _RING_PRONG_SHARE * smooth_annulus_limit_mm3(2.413, 2.3876, 0.381),
    # MHA-PD-VN-55 #0-80 x 1/4 (pd_vn_transgear_disc_screw_spec) through the hub
    # flange's #51 (.067) clearance into the disc's 3/64 taps (pd_rack_pinion_spec),
    # cut at assembly (R9-47) to 5.2832 under the head: 5.2832 - 2.3876 = 2.8956
    # (.114) of the .118 face.
    **numbered_pairs(
        "pd-vn-transgear-disc-screw",
        range(1, 4),
        "pd-rack-pinion",
        smooth_annulus_limit_mm3(1.524, 1.191, 5.2832 - 2.3876),
    ),
    # MHA-PD-VN-69 1/16 x 5/16 key pin (pd_vn_transgear_hub_key_pin_spec,
    # #2409) pressed along the hub's .0615 (1.5621) chord ream to its stop:
    # bounded over the pin's whole 7.9375 length, of which the bore's window
    # over the flat takes part.
    frozenset(
        ("pd-vn-transgear-hub-key-pin-1", "pd-transgear-disc-hub-1")
    ): smooth_annulus_limit_mm3(1.5875, 1.5621, 7.9375),
    # MHA-PD-VN-62 through the knob shaft's journal and the cup (above).
    frozenset(("pd-vn-transgear-knob-cup-pin-1", "pd-transgear-knob-shaft-1")): 1.10
    * _CUP_PIN_JOURNAL_MM3,
    frozenset(("pd-vn-transgear-knob-cup-pin-1", "pd-transgear-knob-cup-1")): 1.10
    * _CUP_PIN_CUP_MM3,
    # Seats modelled line to line that the gate read as solid overlap on run
    # 20261001T035353825Z (assembly:paper_drive, R9-35): each MHA-PD-VN-56 oval
    # head in its 82-degree countersink (0.00809 mm^3).  Sub-micron slivers
    # of coincident faces; the observed reading plus ten percent, so a head
    # sunk even 1 um into its seat (~0.05 mm^3) still fails.
    **numbered_pairs(
        "pd-vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm-plate",
        1.10 * 0.00809042475,
    ),
    # MHA-PD-13's #8-32 tap drill 3.454 on MHA-PD-08's Ø4.064 thread blank:
    # on the .243 nominal collar 6.1722, whose rear reacts on F (its faced
    # remainder is air at its front), the nut seats on the pilot 2.9016 in
    # front of the collar. The overlap is 23.876 - 6.1722 - 2.9016 =
    # 14.8022, entirely on the blank, which starts 7.62 in front of F, behind
    # the nut's seat at 9.0738.
    frozenset(
        ("pd-transgear-thumbnut-1", "pd-transgear-knob-shaft-1")
    ): smooth_annulus_limit_mm3(4.064, 3.454, 23.876 - 6.1722 - 2.9016),
    # The two MHA-PD-VN-54 dowels pressed into the MHA-PD-22 collar's through reams,
    # the crank-seat twin (the collar's PIN_HOLE_DIA is the seat interface's
    # DRIVE_PIN_HOLE_DIA): the pin's length behind the seat face, 2.3625
    # (pd_vn_transgear_knob_drive_pin_spec.PRESS_DEPTH; a literal, so this
    # table does not re-key on that purchased pin's registry row).
    **numbered_pairs(
        "pd-vn-transgear-knob-drive-pin",
        range(1, 3),
        "pd-transgear-drive-collar",
        smooth_annulus_limit_mm3(_SEAT_PIN_DIA, _SEAT_PIN_HOLE_DIA, 2.3625),
    ),
    # MHA-PD-VN-70 (pd_vn_transgear_collar_flat_pin_spec, Ø1/16 = 1.5875 model)
    # pressed into the collar's Ø.0615 (1.5621) blind ream from the floor
    # .080 (2.032) behind the seat face to the rear, faced flush with the .243
    # model collar: FLAT_PIN_LENGTH 4.1402 (#2409). The press, bounded over the
    # whole length although the bore's air takes the crest side.
    frozenset(
        ("pd-vn-transgear-collar-flat-pin-1", "pd-transgear-drive-collar-1")
    ): smooth_annulus_limit_mm3(1.5875, 1.5621, 4.1402),
    # Chain-mesh contact at the closing station: the MHA-PD-VN-66 connecting
    # link closes the chain at station 67, whose forward pin is pin 0 on the
    # T24's pitch circle, the same seated-chain mesh the gate allows every
    # MHA-SH-VN-50 InnerLink/OuterLink member on a mounted removable. The
    # separate connecting-link SKU remains excluded from the generic shared
    # native-member exemption: only this exact bounded pair is intentional.
    # Two bodies, 3.512 + 2.105 = 5.617 mm^3 on run 20261015T010201208Z
    # (assembly:pd_paper_drive); the reading plus ten percent, so a deeper
    # seat or a clash with any other part still fails.
    frozenset(("pd-transgear-removable-1", "pd-vn-chain-connecting-link-1")): 1.10
    * 5.61663709,
}
