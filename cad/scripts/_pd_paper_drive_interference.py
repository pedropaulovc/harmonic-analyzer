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
# one-diameter MHA-PD-23
# pin bonded in the arm's Ø3.2004 ream (a slip fit, fit audit 2026-11-23:
# nothing presses), the sleeve and both
# bushings on the MHA-PD-23 pin (Ø3.175 in Ø3.2004), the disc bore on the boss (Ø9), the
# knob journal in the MHA-PD-28 bush's bore (Ø6.3246), the bush pressed in
# the plate's ream (both modelled line to line at Ø11.1379; owner ruling
# 2026-11-20, #2425), the drive collar's drilled round bore on the core made
# to fit it (both modelled line to line at Ø4.8514, the #11 drill; fit audit
# 2026-11-23), the MHA-PD-VN-70 pin's crest clear of the core's flat
# and its faced rear end flush on F, the MHA-PD-VN-54 dowels in the T24's Ø2.5
# holes, every screw in its clearance hole (the MHA-PD-VN-71 shank in the
# MHA-PD-16 cup web's #33 hole among them), and the MHA-PD-14 latch hook: its
# base on the bar's back face under the MHA-PD-VN-59 heads, their shanks
# through its Ø3.2 holes, and the MHA-PD-VN-58 pin through its Ø3.3 pin hole.
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
    # MHA-PD-VN-65 #2-56 clip screws: the 6.35 shank passes the 0.8 clip sheet
    # and the 3.85 platen's through tap, its tip proud of the back (#2411).
    **numbered_pairs(
        "pd-vn-platen-clip-screw",
        range(1, 5),
        "pd-platen",
        smooth_annulus_limit_mm3(THREAD_MAJOR_MM["#2-56"], TAP_DRILL_MM["#2-56"], 3.85),
    ),
    # MHA-PD-VN-52 guide screws: seed -1, then the grid -2..-10, alternating
    # between the bottom rail (MHA-PD-27, odd) and the top rail (MHA-PD-11,
    # even); the bottom rail's platen taps are transferred THROUGH at the same
    # #4-40 size and depth, so both rails take one bound.
    **numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(1, 11, 2),
        "pd-platen-bottom-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
    ),
    **numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(2, 11, 2),
        "pd-platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
    ),
    # MHA-PD-VN-60 guide-lock screws (R9-31, R9-48): seeds -1/-2, then the grid
    # -3..-8; each 9.525 shank passes the 1.5875 (1/16 sheet) lock plate into
    # the rail's rear through tap (bottom rail MHA-PD-27, top rail MHA-PD-11).
    **numbered_pairs(
        "pd-vn-guide-lock-screw",
        (1, 2, 4, 7),
        "pd-platen-bottom-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 7.9375),
    ),
    **numbered_pairs(
        "pd-vn-guide-lock-screw",
        (3, 5, 6, 8),
        "pd-platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 7.9375),
    ),
    # MHA-PD-VN-72 91794A060 #0-80 x 1/2 (pd_feed_rack_screw_spec, #3738),
    # heads on MHA-PD-27's counterbore floors 10.287 (.405) above the strip,
    # through the rail's #51 clearance into the MHA-PD-26 strip's taps drilled
    # 1.191: 12.7 - 10.287 = 2.413 in the strip.
    **numbered_pairs(
        "pd-vn-feed-rack-screw",
        range(1, 5),
        "pd-feed-rack",
        smooth_annulus_limit_mm3(1.524, 1.191, 12.7 - 10.287),
    ),
    # MHA-PD-VN-56 #8-32 x 5/8 (pd_vn_transgear_arm_plate_screw_spec; from the top of the
    # oval head's bevel, flush in the plate's countersink) through the 5.0038
    # plate's Ø5.7912 clearance, cut flush with the arm's front face (R9-44): the
    # cut length 14.5288 - 5.0038 = the arm's 9.525 in its #29 through tap.
    **numbered_pairs(
        "pd-vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm",
        smooth_annulus_limit_mm3(4.1656, 3.454, 14.5288 - 5.0038),
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
    # The two MHA-PD-VN-64 dowels (pd_vn_transgear_arm_plate_locating_pin_spec,
    # 1/8 = Ø3.175 model) pressed into the arm's Ø3.1496 through reams
    # (pd_transgear_arm_geometry); _transgear_arm_plate_locating_interface
    # owns the 1.7018 proud set in their 7.9375 - 1.7018 insertion: the press.
    # They slip in the plate's Ø3.2004 holes, so that pair has no row.
    **numbered_pairs(
        "pd-vn-transgear-arm-plate-locating-pin",
        range(1, 3),
        "pd-transgear-arm",
        smooth_annulus_limit_mm3(3.175, 3.1496, 7.9375 - 1.7018),
    ),
    # The MHA-PD-VN-58 latch pin (pd_vn_transgear_latch_pin_spec, 1/8 =
    # Ø3.175 model) pressed its 8.5 PRESS_DEPTH into the arm's Ø3.1496 blind
    # ream (pd_transgear_arm_geometry, the .1240 set reamer's size): the
    # press.
    frozenset(
        ("pd-vn-transgear-latch-pin-1", "pd-transgear-arm-1")
    ): smooth_annulus_limit_mm3(3.175, 3.1496, 8.5),
    # MHA-PD-VN-61 (pd_vn_transgear_retaining_ring_spec, McMaster 97431A240)
    # in the MHA-PD-23 groove: the ring as McMaster ships it, its prongs on
    # the Ø2.3876 free diameter, 0.0127 inside the Ø2.413 groove floor: the
    # grip, over the prong arcs (above) and the 0.381 thickness.  The
    # prong-corner fillets only shorten the arcs (the 97431A260 replica's run
    # 20261002T153039266Z read 0.72 of its bound).
    frozenset(
        ("pd-vn-transgear-retaining-ring-1", "pd-transgear-pin-1")
    ): _RING_PRONG_SHARE * smooth_annulus_limit_mm3(2.413, 2.3876, 0.381),
    # MHA-SH-VN-59 91794A055 #0-80 x 1/4 (pd_transgear_disc_screw_spec)
    # through the hub flange's #51 (.067) clearance into the disc's 3/64 taps
    # (pd_rack_pinion_spec), cut at assembly (R9-47) to 5.2832 under the head:
    # 5.2832 - 2.3876 = 2.8956 (.114) of the .118 face.
    **numbered_pairs(
        "sh-vn-fillister-screw-91794a055",
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
    # MHA-PD-VN-71 #2-56 x 3/8 fillister, modelled plain at the thread major
    # (pd_vn_transgear_knob_cup_screw_spec, 91794A079) under-head on the
    # MHA-PD-16 cup web's rear face, 3.048 (.120)
    # behind the journal's end (the web's .252 from the cup front less the
    # fitted .132 pilot), into the MHA-PD-08 journal's blind #2-56 tap at its
    # #50 drill: 9.525 - 3.048 = 6.477 in the tap.
    frozenset(
        ("pd-vn-transgear-knob-cup-screw-1", "pd-transgear-knob-shaft-1")
    ): smooth_annulus_limit_mm3(
        THREAD_MAJOR_MM["#2-56"], TAP_DRILL_MM["#2-56"], 9.525 - 3.048
    ),
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
