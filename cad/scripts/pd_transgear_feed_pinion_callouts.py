"""Text the MHA-PD-10 part authors: its marked dimensions' lanes and its sheet
properties (the gear data block and the tooth-space inspection callout).

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
mate's drawing number and the clearance as REF, or a bench acceptance where
a clearance would be ambiguous.  The teeth (tip and span) serve one mesh:
each links the GEAR DATA block, which names the rack once with the backlash
acceptance that is the span band's fit route.
"""

from __future__ import annotations

import math

import pd_transgear_disc_hub_spec as HUB
from pd_cluster_stack_band import STACK_NAME
from pd_rack_pinion_spec import inch_floor_mm, inch_text
from pd_transgear_feed_pinion_spec import (
    BORE_DATUM,
    BORE_DIAMETRAL_CLEARANCE,
    CUTTER_NUMBER,
    CUTTER_TOOTH_RANGE,
    DIAMETRAL_PITCH,
    HUB_NUMBER,
    MM_PER_IN,
    PIN_NUMBER,
    PITCH_DIA,
    PRESSURE_ANGLE_DEG,
    RACK_BACKLASH_RANGE,
    RACK_NUMBER,
    TEETH,
    TOOTHSPACE_GAUGE_DIA_MM,
    TOOTH_SPACE_RUNOUT_TIR_MM,
    WHOLE_DEPTH,
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
# The tip and the two-tooth span serve the rack mesh, named once in the
# gear data block.
MESH_CALLOUT = "SEE GEAR DATA"
# The boss is the hub's locating fit, +.0005/.0000 under its +.0010/+.0005
# bore: a band under the turned-diameter row, so it is turned to the hub's
# bore (the matched-fit route, rule 4), both parts' limits still applying.
BOSS_CALLOUT = "\n".join(
    (
        f"LOCATIONAL CLEARANCE FIT IN {HUB_NUMBER},",
        f"TURN TO BORE {_clearance(HUB.BOSS_CLEARANCE_LIMITS)}",
    )
)
# The flat drives the hub's D-bore flat.  Its clearance is plane to plane,
# which "CLEARANCE" alone leaves ambiguous against the boss's diametral one,
# so the fit is accepted on the bench against the hub (2026-11-07 screen).
FLAT_CALLOUT = "\n".join(("SLIDING FIT IN", f"{HUB_NUMBER}, NO ROCK"))
# The step seats the hub's spigot: the tooth length places hub and disc.  Its
# ±band is a term of the disc cluster's printed stack (transgear_cluster_fit.TL).
FACE_WIDTH_CALLOUT = "\n".join((f"SEATS {HUB_NUMBER} SPIGOT", STACK_NAME))
# The overall sets the hub's recess behind the nose and carries the front
# bushing's thrust: a term of the disc cluster's printed stack
# (transgear_cluster_fit.OL).
OVERALL_CALLOUT = "\n".join((f"SETS {HUB_NUMBER}, {FRONT_BUSHING_NUMBER}", STACK_NAME))
# The flat's end wall stands clear behind the hub's flat
# (pd_transgear_disc_hub_spec.FLAT_END_CLEARANCE_WORST).
FLAT_END_CALLOUT = f"CLEARS {HUB_NUMBER} FLAT"
# The cutter stations name themselves under their values: neither ends at an
# edge of the section, which cuts through teeth, so they print on view C.
# The full depth's teeth cover the rack's whole reach
# (build_pd_paper_drive_assembly.RACK_FRONT_FROM_SLEEVE_REAR_WORST), its
# function (2026-10-27 ENFORCE review, r2, r3); the rack is the gear data's
# mate, named there once (2026-11-07 screen).
FULL_DEPTH_CALLOUT = "\n".join((f"{TEETH}T FULL DEPTH", "COVERS RACK WIDTH"))
CUTTER_RUNOUT_CALLOUT = "CUTTER RUN-OUT"
# The prefix lane replaces SolidWorks' own diameter symbol, so it carries it
# (run 20261027T032128736Z printed a bare "ROOT 7.93 min.").  The translated
# cutter's root arcs are not concentric: the MIN bounds every root point, not
# the gap bisectors the arrows land on, so it names itself an envelope
# (codjiflo P2 on ebde256dc).
ROOT_PREFIX = "ROOT ENVELOPE <MOD-DIAM>"

# lane -> (feature, dimension) -> text.
CALLOUTS: dict[int, dict[tuple[str, str], str]] = {
    TEXT_PREFIX: {("RootProfile", "RootDia"): ROOT_PREFIX},
    CALLOUT_BELOW: {
        ("SleeveProfile", "BoreDia"): BORE_CALLOUT,
        ("SleeveProfile", "OutsideDia"): MESH_CALLOUT,
        ("SpanProfile", "ToothSpan"): MESH_CALLOUT,
        ("SleeveProfile", "BossDia"): BOSS_CALLOUT,
        ("FlatProfile", "FlatToAxis"): FLAT_CALLOUT,
        ("GearBlank", "FaceWidth"): FACE_WIDTH_CALLOUT,
        ("SleeveProfile", "OverallLength"): OVERALL_CALLOUT,
        ("FlatProfile", "FlatEnd"): FLAT_END_CALLOUT,
        ("SleeveProfile", "FullDepth"): FULL_DEPTH_CALLOUT,
        ("SleeveProfile", "CutterRunout"): CUTTER_RUNOUT_CALLOUT,
    },
}

# The rack mesh's datum backlash band (pd_transgear_feed_pinion_spec, the
# band paper_drive_mesh_check.feed_rack_mesh gates and MHA-PD-00 sets as
# platen shake on a dial), rounded inward onto the plain .0005 in dial step
# (MHA-PD-00 prints the same window) so the printed window never admits a
# backlash the mesh check refuses.
_BACKLASH_STEP_IN = 0.0005
BACKLASH_ACCEPT_MM = (
    math.ceil(RACK_BACKLASH_RANGE[0] / MM_PER_IN / _BACKLASH_STEP_IN - 1e-9)
    * _BACKLASH_STEP_IN
    * MM_PER_IN,
    math.floor(RACK_BACKLASH_RANGE[1] / MM_PER_IN / _BACKLASH_STEP_IN + 1e-9)
    * _BACKLASH_STEP_IN
    * MM_PER_IN,
)
if not (
    RACK_BACKLASH_RANGE[0] <= BACKLASH_ACCEPT_MM[0]
    < BACKLASH_ACCEPT_MM[1] <= RACK_BACKLASH_RANGE[1]
):
    raise AssertionError(
        f"MHA-PD-10 backlash acceptance {BACKLASH_ACCEPT_MM} leaves the mesh "
        f"band {RACK_BACKLASH_RANGE}"
    )


def _step_text(value_mm: float) -> str:
    """A .0005-step inch value without a padding zero: ``.005``, ``.0055``."""
    return inch_text(value_mm, 4).rstrip("0")


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# What a machinist needs to cut and check the teeth; design parameters stay
# in the spec (Main ruling 2026-10-10).  The two-tooth span prints on the end
# view with its limits, so the block does not repeat it; the rack is named
# here once, with the backlash acceptance that is the span band's fit route
# (rule 4; 2026-11-07 screen).
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{TEETH}"),
        ("DIAMETRAL PITCH", f"{DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE", f"{PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", inch_text(PITCH_DIA, 4)),
        ("WHOLE DEPTH (REF)", inch_text(WHOLE_DEPTH, 4)),
        ("CUTTER", f"#{CUTTER_NUMBER}, {CUTTER_TOOTH_RANGE[0]}-{CUTTER_TOOTH_RANGE[1]}T"),
        ("MATES WITH", f"PLATEN RACK {RACK_NUMBER}"),
        (
            "BACKLASH WITH MATE (DIAL)",
            "-".join(_step_text(value) for value in BACKLASH_ACCEPT_MM),
        ),
    ]
)

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
