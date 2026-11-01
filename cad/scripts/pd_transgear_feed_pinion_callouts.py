"""Dimension text the MHA-PD-10 part authors on its marked dimensions.

The part builder writes every lane below on its source dimension; the
drawing imports them verbatim and only reads them back.  Setting dimension
text from the drawing writes through to the imported source dimension, and
the drawing's native save then saves the dirtied part outside its own recipe
(fleet issue #1942, the #1936/#1939 pattern).  Kept out of
``pd_transgear_feed_pinion_spec``, which the hub, the cluster fit and the
paper-drive assembly import: this module reads the hub's spec for the fits
it names.

Every band tighter than its title-block row names its mate or the stack it
sets at its own callout (drawing-guidelines.md rule 4; 2026-10-24 ENFORCE
review of the sheet).
"""

from __future__ import annotations

import pd_transgear_disc_hub_spec as HUB
from pd_cluster_stack_band import STACK_NAME
from pd_rack_pinion_spec import inch_text
from pd_transgear_feed_pinion_spec import (
    BORE_CALLOUT,
    HUB_NUMBER,
    RACK_NUMBER,
    TEETH,
)
from pd_transgear_pin_spec import FRONT_BUSHING_NUMBER

TEXT_PREFIX = 1  # swDimensionTextPrefix
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow

# The tip and the two-tooth span are set by the rack mesh.
MESH_CALLOUT = f"MESHES {RACK_NUMBER} RACK"
# The boss is the hub's locating fit, +.0005/.0000 under its +.0010/+.0005 bore.
# The clearances are literal text in the sheet's inches (codjiflo P2 on
# 65a022125: the document converts dimension values, never text).
BOSS_CALLOUT = "\n".join(
    (
        f"LOCATES {HUB_NUMBER},",
        f"{inch_text(HUB.BOSS_CLEARANCE_LIMITS[0], 4)}-"
        f"{inch_text(HUB.BOSS_CLEARANCE_LIMITS[1], 4)} DIA CLR",
    )
)
# The flat drives the hub's D-bore.
FLAT_CALLOUT = "\n".join(
    (
        f"DRIVES {HUB_NUMBER},",
        f"{inch_text(HUB.FLAT_CLEARANCE[0], 4)}-{inch_text(HUB.FLAT_CLEARANCE[1], 4)} CLR",
    )
)
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
# edge of the section, which cuts through teeth, so they print on the
# outside view.  The full depth's teeth cover the rack's whole reach
# (build_pd_paper_drive_assembly.RACK_FRONT_FROM_SLEEVE_REAR_WORST), so it
# names the rack (2026-10-27 ENFORCE review, r2, r3: no stated function).
FULL_DEPTH_CALLOUT = "\n".join((f"{TEETH}T FULL DEPTH", f"COVERS {RACK_NUMBER} RACK"))
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
