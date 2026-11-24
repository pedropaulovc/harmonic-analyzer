"""Text the MHA-PD-10 part authors: its marked dimensions' lanes and its sheet
property (the tooth-space inspection callout).

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(fleet issue #1942, the #1936/#1939 pattern).  Kept out of
``pd_transgear_feed_pinion_spec``, which the hub, the cluster fit and the
paper-drive assembly import, so rewording the sheet re-keys only this part
and its drawing: this module reads the spec and the hub's spec for every
value it prints.

Every REAM and every band tighter than its title-block row names its mate
and its fit at its own callout (drawing-guidelines.md rule 4): a standard
fit name on the mate's drawing number, or the mate's name and number with
an acceptance by the mate, and what the fit protects.  The teeth (tip and span)
serve one mesh: each links the GEAR DATA block, which names the rack once
and the span's matched fit.  That block is the drawing's own note
(draw_pd_transgear_feed_pinion.GEAR_DATA_NOTE): its span row cites the
MHA-PD-00 step that sets the mesh, so the assembly's numbering never re-keys
this part.
"""

from __future__ import annotations

import _config
import pd_transgear_disc_hub_spec as HUB
from pd_cluster_stack_band import STACK_NAME
from pd_rack_pinion_spec import inch_floor_mm, inch_text
from pd_transgear_feed_pinion_spec import (
    BORE_DATUM,
    HUB_NUMBER,
    PIN_NUMBER,
    TEETH,
    TOOTHSPACE_GAUGE_DIA_MM,
    TOOTH_SPACE_RUNOUT_TIR_MM,
)
from pd_transgear_pin_spec import FRONT_BUSHING_NUMBER

# The screwed feed rack (#2410), read from its registry row.  It lives here,
# not in the spec, so naming it re-keys only this sheet; the spec's unread
# RACK_NUMBER is the retired strip's (#2820).
RACK_NUMBER = _config.parts("pd-feed-rack")["number"]

TEXT_PREFIX = 1  # swDimensionTextPrefix
TEXT_SUFFIX = 2  # swDimensionTextSuffix
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow


# The reamed bore runs on the MHA-PD-23 pin's 1/8 shank.  It prints the
# reamer's size and no band (drawing-guidelines rule 4, form 2): the pin is
# turned to it, and the pin's sheet carries the
# pair's one acceptance (MHA-PD-23 note 1: each bore turns free with no
# shake; machinist review r1 of the fit batch: an acceptance printed on
# both members, and three rows of words under the size).  The callout is
# the process row and the mate, with that it is turned to this bore (a
# bare fit name is not enough).  Why it is reamed (play cocks the sleeve
# and tilts the MHA-PD-06 disc into the drive collar:
# pd_cluster_air.COLLAR_AIR) is in the part's necessity file (owner ruling
# 2026-11-24: "In the part's registry file, not on the sheet";
# cad/config/necessity/pd-transgear-feed-pinion.yaml).  The block stays
# clear of the gear data
# (test_section_values_and_bands_print_clear_of_each_other).
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = f"{PIN_NUMBER} IS TURNED TO THIS BORE"
BORE_CALLOUT = f"{BORE_PROCESS_CALLOUT}\n{BORE_FIT_CALLOUT}"
# The tip serves the rack mesh, named once in the gear data block.  The
# two-tooth span's .0008 band is under the milled row and still controls (it
# sets the cutter's radial setting limits, pd_transgear_feed_pinion_spec), so
# its callout names its fit route as MHA-PD-06's and MHA-PD-08's spans do: a
# matched fit, the block's span row naming how the mesh is set.
MESH_CALLOUT = "SEE GEAR DATA"
SPAN_CALLOUT = "MATCHED FIT,\nSEE GEAR DATA"
# The hub as the shop reads it (its config title's last words; hard-coded
# like HUB_NUMBER, checked against the registry by the drawing test).
HUB_NAME = "DISC HUB"
# The boss is made to fit (rule 4): turned last to the hub's reamed bore,
# accepted by feel, so its size prints REF (parenthesised by the prefix and
# suffix lanes, _drawing_dimensions.set_reference_dimension's texts) and
# the callout names the mate by name and number and the acceptance.
BOSS_REF_PREFIX = "(<MOD-DIAM>"
BOSS_REF_SUFFIX = ")"
BOSS_CALLOUT = f"TURN TO {HUB_NAME} {HUB_NUMBER}: SLIDES ON, NO ROCK"
# #2409: the flat takes the side of the hub's MHA-PD-VN-69 chord key pin,
# which keys hub and disc to the sleeve; the hub's plain bore fits the boss
# only.  The pin bears across the flat, so the pin is the mate it names.
# Its ±.002 is under the title block's row for the pin's gap to the flat
# (pd_transgear_disc_hub_spec.KEY_PIN_FLAT_AIR, .0006 least); the reason is
# in the part's necessity file, not on the sheet (owner ruling 2026-11-24).
# Two rows no wider than the pin's number: VIEW E prints the text right of
# its dimension line on a shelf as long as its widest row, and the boss's
# dimension line stands 40 mm right of it.  "KEYS MHA-PD-VN-69", five
# characters wider, ran that shelf across the boss's line (leaf
# 20261124T014755Z, layout audit shoulder-crosses-line: the drawing leaf
# failed).
FLAT_CALLOUT = "\n".join(("KEYS PIN", HUB.KEY_PIN_NUMBER))
# The step seats the hub's spigot: the tooth length places hub and disc.  Its
# ±band is a term of the disc cluster's printed stack (transgear_cluster_fit.TL):
# it keeps the hub's front face .000-.006 behind the sleeve's nose
# (RECESS_RANGE; .004 proud at the title block's ±.005), the reason its
# necessity file gives.  The row names the mate the step seats.
FACE_WIDTH_CALLOUT = f"SEATS {HUB_NUMBER} SPIGOT"
# The overall sets the hub's recess behind the nose and carries the front
# bushing's thrust: a term of the disc cluster's printed stack
# (transgear_cluster_fit.OL).
OVERALL_CALLOUT = "\n".join((f"SETS {HUB_NUMBER}, {FRONT_BUSHING_NUMBER}", STACK_NAME))
# The cutter stations name themselves under their values: neither ends at an
# edge of the section, which cuts through teeth, so they print on view C.
# The full depth's teeth cover the rack's whole reach
# (build_pd_paper_drive_assembly.RACK_FRONT_FROM_SLEEVE_REAR_WORST), its
# function (2026-10-27 ENFORCE review, r2, r3), the rack named by number.
FULL_DEPTH_CALLOUT = "\n".join(
    (f"{TEETH}T FULL DEPTH", f"COVERS {RACK_NUMBER} RACK WIDTH")
)
# The run-out limit is where the gaps may run out on to the boss, past the
# step, and the teeth between the full depth and the step may be cut short
# of full depth.  Owner ruling 2026-11-20 (#2423, option A): stated in
# product terms, not as a cutter station ("CUTTER RUN-OUT" read as the
# cutter's own run-out to the O.D.), and with no method words.  The ruling's
# "ACCEPTED" is a governance word the sheet may not print
# (test_printed_text_rulings), so the row says ALLOWED; the row above names
# the gaps, so this one fits left of VIEW C clear of B-B's caption.
CUTTER_RUNOUT_CALLOUT = "\n".join(
    ("GAP RUN-OUT ON BOSS", "PARTIAL DEPTH TO STEP ALLOWED")
)
# The prefix lane replaces SolidWorks' own diameter symbol, so it carries it
# (run 20261027T032128736Z printed a bare "ROOT 7.93 min.").  The translated
# cutter's root arcs are not concentric: the MIN bounds every root point, not
# only the gap bisectors the arrows land on (codjiflo P2 on ebde256dc); the
# prefix names it in standard words, not a coined "envelope" (final-head
# review, run 20261108T014931710Z).
ROOT_PREFIX = "ROOT DIAMETER <MOD-DIAM>"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    TEXT_PREFIX: {
        ("RootProfile", "RootDia"): ROOT_PREFIX,
        ("SleeveProfile", "BossDia"): BOSS_REF_PREFIX,
    },
    TEXT_SUFFIX: {("SleeveProfile", "BossDia"): BOSS_REF_SUFFIX},
    CALLOUT_BELOW: {
        ("SleeveProfile", "BoreDia"): BORE_CALLOUT,
        ("SleeveProfile", "OutsideDia"): MESH_CALLOUT,
        ("SpanProfile", "ToothSpan"): SPAN_CALLOUT,
        ("SleeveProfile", "BossDia"): BOSS_CALLOUT,
        ("FlatReference", "FlatToAxis"): FLAT_CALLOUT,
        ("GearBlank", "FaceWidth"): FACE_WIDTH_CALLOUT,
        ("SleeveProfile", "OverallLength"): OVERALL_CALLOUT,
        ("SleeveProfile", "FullDepth"): FULL_DEPTH_CALLOUT,
        ("SleeveProfile", "CutterRunout"): CUTTER_RUNOUT_CALLOUT,
    },
}

# The tooth-space runout limit: the shared grade
# (fits.stock_form_quality.toothspace_runout_tir_mm, the .002 inch step), at
# three places and floored, so the print never exceeds the booked grade.
TOOTH_SPACE_RUNOUT_TIR_TEXT = inch_text(inch_floor_mm(TOOTH_SPACE_RUNOUT_TIR_MM, 3), 3)
TOOTH_SPACE_CALLOUT = "\n".join(
    (
        f"TOOTH SPACE RUNOUT {TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR TO {BORE_DATUM}",
        f"\u00d8{inch_text(TOOTHSPACE_GAUGE_DIA_MM, 4)} PIN, ALL {TEETH} SPACES",
    )
)


def authored_text() -> dict[str, dict[str, dict[int, str]]]:
    """feature -> dimension -> lane -> text: everything the part writes."""
    authored: dict[str, dict[str, dict[int, str]]] = {}
    for lane, rows in CALLOUTS.items():
        for (feature, name), text in rows.items():
            authored.setdefault(feature, {}).setdefault(name, {})[lane] = text
    return authored


def authored_by_name() -> dict[str, dict[int, str]]:
    """dimension name -> lane -> text (the drawing's identity is the name)."""
    return {
        name: lanes
        for by_name in authored_text().values()
        for name, lanes in by_name.items()
    }


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))
