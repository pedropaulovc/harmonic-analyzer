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

Every band tighter than its title-block row names its mate and its fit at
its own callout (drawing-guidelines.md rule 4): a standard fit name, the
mate's name and drawing number and the clearance as REF, or a bench
acceptance where a clearance would be ambiguous.  The teeth (tip and span)
serve one mesh: each links the GEAR DATA block, which names the rack once
and the span's matched fit.  That block is the drawing's own note
(draw_pd_transgear_feed_pinion.GEAR_DATA_NOTE): its span row cites the
MHA-PD-00 step that sets the mesh, so the assembly's numbering never re-keys
this part.
"""

from __future__ import annotations

import pd_transgear_disc_hub_spec as HUB
from pd_cluster_stack_band import STACK_NAME
from pd_rack_pinion_spec import inch_floor_mm, inch_text
from pd_transgear_feed_pinion_spec import (
    BORE_DATUM,
    BORE_DIAMETRAL_CLEARANCE,
    HUB_NUMBER,
    PIN_NUMBER,
    RACK_NUMBER,
    TEETH,
    TOOTHSPACE_GAUGE_DIA_MM,
    TOOTH_SPACE_RUNOUT_TIR_MM,
)
from pd_transgear_pin_spec import FRONT_BUSHING_NUMBER

TEXT_PREFIX = 1  # swDimensionTextPrefix
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow


def _clearance(limits_mm: tuple[float, float]) -> str:
    """A fit's (least, greatest) clearance as REF in the sheet's inches.

    Literal text: the document converts dimension values, never text
    (codjiflo P2 on 65a022125)."""
    return f"(CLEARANCE {inch_text(limits_mm[0], 4)}-{inch_text(limits_mm[1], 4)} REF)"


# The reamed bore runs on the MHA-PD-23 pin's 1/8 shank.
BORE_PROCESS_CALLOUT = "REAM THRU"
BORE_FIT_CALLOUT = "\n".join(
    (f"RUNNING FIT ON {PIN_NUMBER}", _clearance(BORE_DIAMETRAL_CLEARANCE))
)
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
# The boss is the hub's locating fit, +.0005/.0000 under its +.0010/+.0005
# bore: a band under the turned-diameter row, so it is turned to the hub's
# bore (the matched-fit route, rule 4: the mate by name and number), both
# parts' limits still applying.
BOSS_CALLOUT = "\n".join(
    (
        f"LOCATIONAL CLEARANCE FIT IN {HUB_NAME} {HUB_NUMBER},",
        f"TURN TO BORE {_clearance(HUB.BOSS_CLEARANCE_LIMITS)}",
    )
)
# #2409: the flat takes the side of the hub's MHA-PD-VN-69 chord key pin,
# which keys hub and disc to the sleeve; the hub's plain bore fits the boss
# only.  The pin bears across the flat, so the pin is the mate it names.
FLAT_CALLOUT = "\n".join(("KEYS PIN", HUB.KEY_PIN_NUMBER))
# The step seats the hub's spigot: the tooth length places hub and disc.  Its
# ±band is a term of the disc cluster's printed stack (transgear_cluster_fit.TL),
# named once, on the overall (r8 machinist review, rule 7: a second reason).
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
CUTTER_RUNOUT_CALLOUT = "CUTTER RUN-OUT"
# The prefix lane replaces SolidWorks' own diameter symbol, so it carries it
# (run 20261027T032128736Z printed a bare "ROOT 7.93 min.").  The translated
# cutter's root arcs are not concentric: the MIN bounds every root point, not
# only the gap bisectors the arrows land on (codjiflo P2 on ebde256dc); the
# prefix names it in standard words, not a coined "envelope" (final-head
# review, run 20261108T014931710Z).
ROOT_PREFIX = "ROOT DIAMETER <MOD-DIAM>"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    TEXT_PREFIX: {("RootProfile", "RootDia"): ROOT_PREFIX},
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
