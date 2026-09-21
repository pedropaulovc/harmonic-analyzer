"""Drawing-only text for the crank-drive gear, excluded from the assemblies'
shared geometry imports.

``crank_drive_gear_spec`` is imported by ``cone_swing_platform_spec`` (it needs
the tip circle to lay the platform out), so anything the spec reads becomes a
rebuild dependency of every assembly above it. The tooth-thickness requirement
below is sourced from a FIT CLASS (``fits.gear_mesh.backlash_mm``), and fit
classes must not reach the frame's recipe (test_dodo_recipe's fine-grained
config contract) -- so the text that needs them lives here, exactly as
``cylinder_gear_notes`` does for the cylinder gear.
"""

from __future__ import annotations

import math

import _config
import crank_drive_gear_spec as spec


# The mesh's permitted backlash, from the named fit class ("zero-backlash-in-CAD
# gears bind in brass"). cad/docs/tolerance-policy.md puts gear teeth in the
# critical group and says the backlash comes from ``_config.fit`` -- so this is
# the one place the tooth-thickness requirement can come from.
BACKLASH_MM = _config.fit("gear_mesh", "backlash_mm")

# Standard full-depth thickness at the pitch circle, before any thinning.
STANDARD_TOOTH_THICKNESS = math.pi * spec.MODULE_MM / 2.0

# Tooth thickness is this part's ONE tooth-system acceptance size, so it is a
# toleranced requirement, not a REF consequence of the cutter: the pinion it
# runs against is cut to full thickness, so every thousandth of backlash in the
# pair comes off THIS gear's flanks. The band is the fit class read backwards --
# a tooth this much thicker still leaves the minimum backlash, one this much
# thinner still stays inside the maximum -- which is why it is asymmetric about
# the nominal the model is cut to.
TOOTH_THICKNESS_DEVIATIONS = (
    round(spec.BACKLASH_MM - BACKLASH_MM[0], 3),
    round(-(BACKLASH_MM[1] - spec.BACKLASH_MM), 3),
)


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


# Rule 6's gear-data block: the tooth system a cut-gear drawing cannot express
# as dimensions. Every GENERATING number is REF -- the cutter, its depth of cut
# and the helix setting produce them, and the acceptance sizes are the three
# native dimensions on the views. The two rows that are NOT REF are the pair's
# requirement, and each names WHERE it is accepted: the tooth thickness is
# checked on this part, the backlash it exists to produce is checked when the
# pair is assembled (the operating centre distance and shaft angle live on the
# assembly, not here -- codex's iter1 blocker was that the sheet claimed a
# backlash range a part inspector cannot establish alone).
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{spec.TEETH}"),
        ("DIAMETRAL PITCH, TRANSVERSE", f"{spec.DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE, TRANSVERSE (mm, REF)", f"{spec.MODULE_MM:.3f}"),
        ("PRESSURE ANGLE, TRANSVERSE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{spec.PITCH_DIA:.2f}"),
        ("ROOT DIAMETER (mm, REF)", f"{spec.ROOT_DIA:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{spec.WHOLE_DEPTH:.2f}"),
        (
            "HELIX ANGLE AT PITCH DIAMETER",
            f"{spec.HELIX_ANGLE_DEG:.1f} DEG {spec.HELIX_HAND}",
        ),
        (
            "CIRCULAR TOOTH THICKNESS AT PITCH DIA, TRANSVERSE (mm), ACCEPT ON THIS PART",
            f"{spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} "
            f"+{TOOTH_THICKNESS_DEVIATIONS[0]:.3f} / {TOOTH_THICKNESS_DEVIATIONS[1]:.3f}",
        ),
        (
            "TRANSVERSE BACKLASH WITH MHA-025, ACCEPT AT ASSEMBLY (mm)",
            f"{BACKLASH_MM[0]:.2f} TO {BACKLASH_MM[1]:.2f}",
        ),
        ("TOOTH FORM", "HELICAL INVOLUTE, FULL DEPTH, ARC ROOT FLOOR"),
        ("MATES WITH", "CRANK PINION MHA-025, 16T STRAIGHT SPUR, FULL THICKNESS"),
    ]
)

# How this gear is held to its shaft. The bore is a plain slip fit and the
# part carries no key, keyway, pin, set screw or hub, so the joint to the
# shaft land IS the whole torque path -- the case where rule 6 allows a
# process word on the print. The rule-11 flag closed 2026-09-21
# (C:/src/dt-logs/geometry-decisions.md) on ch12 p.20/p.21 evidence: fixed
# like the 20 cone gears. Each permitted method is ONE constant, so
# re-deciding the joint is a one-line change; the first carries the verb and
# its preposition so any replacement still reads as a sentence.
ATTACHMENT_PROCESS = "SOLDER OR SILVER-BRAZE TO"

# The user-approved alternative (2026-09-21): a Ø9.525 H-band slip joint with
# a 0.025..0.075 mm diametral clearance is inside the cure gap of both
# high-strength retaining compounds, so the shop may pick either route. It is
# stated as a permission, not an instruction -- the requirement is that the
# gear ends up fixed to the seat.
ATTACHMENT_ALTERNATIVE = "LOCTITE 638 OR 648 RETAINING COMPOUND ACCEPTABLE"

# The seat's owner, quoted only to identify the mate (rule 6). Hard-coded
# rather than read from ``_config.parts``: this module is in the part's
# rebuild closure, and a cross-part config read would make cone-gear-shaft.yaml
# a rebuild dependency of this gear. ``test_crank_drive_gear_drawing`` checks
# it against the registry offline, where a cross-check costs nothing.
SHAFT_MATE_NUMBER = "MHA-014"

# Notes: the part-specific facts a machinist cannot read off the views
# (drawing-simplicity-policy.md rule 6, budget four short lines). The first is
# the one thing the title block gets wrong for a fine-pitch gear -- a 0.25
# break is more than a tenth of this tooth's whole depth. The rest are the
# attachment. No line carries a dimension: the bore's size and limits print on
# the face view, and the axial station belongs to the assembly (the model
# leaves ~1.1 mm of air to T120, so this gear butts nothing).
DRAWING_NOTES = "\n".join(
    (
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        f"PLAIN BORE, NO KEYWAY: {ATTACHMENT_PROCESS} THE {SHAFT_MATE_NUMBER}"
        " SHAFT SEAT AT ASSEMBLY;",
        f"{ATTACHMENT_ALTERNATIVE}.",
    )
)
