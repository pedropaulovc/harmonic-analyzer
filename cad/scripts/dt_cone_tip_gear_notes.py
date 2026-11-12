"""Model-stamped data and print text of the cone tip gear, MHA-DT-37.

The leaves' cutting and inspection data come from the cone family's finite
cutter authority (``dt_cone_gear_spec``, six teeth); the backlash reference is
the closed-form check of the drum mesh (``dt_mesh_checks``). The DT6-FORM1
grinding profile is stamped into the part's "Cutter Profile" property, and the
sheet's callouts and numbered notes name each mate once (rules 4 and 7).
"""

from __future__ import annotations

import math
import re
import textwrap
from dataclasses import replace

import _config
import cone_set_stack
import cone_tip_cluster
import dt_cone_gear_spec as family
import dt_cone_tip_gear_spec as spec
import dt_mesh_checks

CYLINDER_MATE_NUMBER = "MHA-DT-12"
SHAFT_MATE_NUMBER = "MHA-DT-04"
# The stem bores of T012 and T018: configurations of the MHA-DT-03 family,
# named by their sheets' own numbers.
STEM_BORE_MATES = tuple(
    family.configuration_number(str(_config.parts("dt-cone-gear")["number"]), teeth)
    for teeth in (12, 18)
)
BUSHING_MATE_NUMBER = "MHA-DT-38"
END_SCREW_MATE_NUMBER = "MHA-DT-39"
BUSHING_MATE_TITLE = str(_config.parts("dt-cone-tip-bushing")["title"]).upper()
END_SCREW_MATE_TITLE = str(_config.parts("dt-cone-tip-end-screw")["title"]).upper()

# Sheet 2 is the T006 tooth space the DT6-FORM1 tool is ground to.
SHEET_NAMES = ("T006", "DT6-FORM1")
CUTTER_DETAIL_SHEET = SHEET_NAMES[1]
CUTTER_DETAIL_SHEET_NUMBER = 2
CUTTER_DETAIL_LINE_CHARS = 108
# The teeth's do-not-cut (rule 7): flagged to the teeth in note 2.
TOOTH_EDGE_NOTE = "NO EDGE BREAK ON TEETH."

# Numbered notes (rule 7): note 1 the pivot's matched press fit, linked from
# the pivot diameter; note 2 the teeth's mesh and fit route, linked from the
# tip, thickness and root; note 3 the turner's centres.
PIVOT_NOTE_NUMBER = 1
TEETH_NOTE_NUMBER = 2
PIVOT_NOTE_FLAG = f"SEE NOTE {PIVOT_NOTE_NUMBER}"
TEETH_NOTE_FLAG = f"SEE NOTE {TEETH_NOTE_NUMBER}"
# The gear width's callout, in MHA-DT-03's form (draw_dt_cone_gear): the
# .2934 nominal is the stack closure of the touching faces, and the callout
# names that stack at the dimension (machinist review, farm run
# 20261112T053742990Z: behind a note flag it read as an off-grid nominal).
FACE_STACK_CALLOUT = f"20-GEAR STACK\nON {SHAFT_MATE_NUMBER}"


def sheet_notes() -> str:
    """The sheet's numbered notes.

    Note 1 is the pivot's two fits (rule 4): the bushing presses over its root
    and the end screw's reamed hole runs on its end, one diameter for both.
    Its .0003 band is under the turned-diameter row, so the pivot is made to
    the measured MHA-DT-38 bore, the interference the parts' limits give; the
    end screw's hole then runs on it with the clearance its limits give. Note
    2 names the mesh and the fit route of the tip, thickness and root bands,
    with the teeth's do-not-cut. Note 3: the stems are turned between centres,
    and a centre hole in either end harms nothing (rule 11).
    """
    interference = spec.inch_range(spec.PIVOT_PRESS_INTERFERENCE_MM)
    clearance = spec.inch_range(spec.PIVOT_RUNNING_CLEARANCE_MM)
    return "\n".join(
        (
            f"{PIVOT_NOTE_NUMBER}. PIVOT: PRESS FIT IN {BUSHING_MATE_NUMBER} {BUSHING_MATE_TITLE}, "
            f"MADE TO ITS MEASURED BORE (INTERFERENCE {interference});",
            f"   ITS END RUNS IN {END_SCREW_MATE_NUMBER} {END_SCREW_MATE_TITLE} "
            f"(DIAMETRAL CLEARANCE {clearance}).",
            f"{TEETH_NOTE_NUMBER}. TEETH MESH WITH {CYLINDER_MATE_NUMBER}: ACCEPT OVER PINS, "
            "THEN BY BACKLASH AT ASSEMBLY,",
            f"   PER GEAR DATA. {TOOTH_EDGE_NOTE}",
            "3. CENTRES OK.",
        )
    )


# Callouts under the value. A callout keeps at most two lines of words
# (rule 7); a mate serving several dimensions is named once, in a flagged
# note (rule 4).
DIMENSION_CALLOUTS = {
    # The spigot's band is the turned-diameter row's width, so it needs no
    # fit route: the bonded fit with its compound (rule 26's fit name, as
    # MHA-DT-04's note prints it) and its three mates.
    "SpigotDia": (
        f"BONDED FIT, {cone_tip_cluster.RETAINING_COMPOUND}, IN {SHAFT_MATE_NUMBER} SOCKET\n"
        f"AND {STEM_BORE_MATES[0]}, {STEM_BORE_MATES[1]}"
    ),
    # One diameter carries both of note 1's fits.
    "PivotDia": f"PRESS AND RUNNING FIT\n{PIVOT_NOTE_FLAG}",
    "ToothThickness": TEETH_NOTE_FLAG,
    # The origin circle is an inspection witness, not the off-centre root arc.
    "FloorDia": f"ROOT ENVELOPE\n{TEETH_NOTE_FLAG}",
    # The leaves are one face of the twenty-gear cone stack (dt_cone_gear_stack)
    # on the cone shaft.  At the .2934 face the two short lines stand inside
    # the width's own extension lines, which the pivot's and spigot's lengths
    # share (rule 14).
    "FaceWidth": FACE_STACK_CALLOUT,
}
# Text over the value, one line each (a multi-line callout above a value
# drops from the print, draw_dt_cone_gear).
CALLOUTS_ABOVE = {
    "ToothThickness": "CIRCULAR TOOTH THICKNESS",
    "BlankDia": TEETH_NOTE_FLAG,
}
if any("\n" in text for text in CALLOUTS_ABOVE.values()):
    raise AssertionError("an above-callout with a line break does not print")
# At most two lines of words per callout (rule 7).
if any(len(text.splitlines()) > 2 for text in DIMENSION_CALLOUTS.values()):
    raise AssertionError("a callout carries at most two lines of words")


def cutter_description() -> str:
    # The tool is ground to the T006 tooth space; sheet 2 defines that space.
    return f"NOT STOCK; FORM = TOOTH SPACE, SHEET {CUTTER_DETAIL_SHEET_NUMBER}"


def tooth_form() -> str:
    return (
        f"INVOLUTE; RELIEF BELOW R{spec.inch_text(spec.TEMPLATE.relief_junction_radius_mm, 4)}"
        f", SHEET {CUTTER_DETAIL_SHEET_NUMBER}"
    )


def gear_data() -> str:
    """The leaves' recipe with its reference sizes, in decimal inch: the cone
    family's T006 Gear Data less the bore's web."""
    teeth = spec.TEETH
    profile = spec.PROFILE
    mesh = dt_mesh_checks.cone_check(teeth)
    inch = spec.inch_text
    # Conservative reference reporting: round the backlash range outward,
    # from the feel set's floor (no bind) to the loosest running centre.
    minimum = family.inch_grid_mm(max(0.0, mesh.backlash_floor_mm), 3, math.floor)
    maximum = family.inch_grid_mm(mesh.backlash_max_mm, 3, math.ceil)
    whole_depth_max = family.inch_grid_mm(
        max(
            corner.blank_radius_mm - corner.root_radius_min_mm
            for corner in family.manufacturing_corner_profiles(teeth)
        ),
        4,
        math.ceil,
    )
    low, high = family.over_pins_limits_mm(teeth)
    pin = family.over_pins_pin_dia_mm(teeth)
    rows = (
        ("TEETH", str(teeth)),
        (
            "DIAMETRAL PITCH / PRESSURE ANGLE",
            f"{family.DIAMETRAL_PITCH:.2f} / {family.PRESSURE_ANGLE_DEG:.1f}\u00b0",
        ),
        ("PITCH DIAMETER (REF)", inch(teeth * family.MODULE_MM, 4)),
        ("CUTTER", cutter_description()),
        ("CUTTER PLUNGE FROM BLANK OD (REF)", inch(profile.plunge_mm, 4)),
        (
            "WHOLE DEPTH MAX / CUTTER ROOT ARC R (REF)",
            f"{inch(whole_depth_max, 4)} / {inch(profile.template.root_radius_mm, 4)}",
        ),
        ("TOOTH FORM", tooth_form()),
        ("MATE", f"{CYLINDER_MATE_NUMBER}, 120T"),
        # Reference only: MHA-DT-00 check 4 sets the mesh by feel and
        # measures no backlash (#2586).
        (
            "BACKLASH WITH MATE (REF), FEEL SET AT ASSEMBLY",
            f"{inch(minimum, 3)} TO {inch(maximum, 3)}",
        ),
        # cone_set_stack books each gear's tooth runout about its seat; this
        # gear's seat is its own stems, between whose centres it is cut.
        (
            "TOOTH CUTTING SETUP, ACCEPT AT SETUP",
            f"{inch(cone_set_stack.TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX TO BOTH "
            f"\u00d8{inch(spec.STEM_DIA_MM, 4)} ENDS",
        ),
        (
            f"OVER 2 PINS \u00d8{inch(pin, 3)}, OPPOSITE GAPS",
            f"{inch(low, family.OVER_PINS_PLACES)} TO {inch(high, family.OVER_PINS_PLACES)}",
        ),
    )
    return "\n".join(("GEAR DATA", *(f"{label}:  {value}" for label, value in rows)))


def custom_cutter_detail() -> str:
    """Complete finite DT6-FORM1 grinding profile, stamped into the native model.

    Coordinates are the uninstalled normal tool plane, not a guessed ideal-N
    or extrapolated profile. Each equation is copied verbatim from the same
    core descriptors used by the native cut, at T=0 and finite tool-tip support.
    Only the outside-blank sketch-closing rays/arc are omitted from the grind.
    """
    installed = spec.PROFILE
    template = installed.template
    if template.cutter_number is not None or template.name != CUTTER_DETAIL_SHEET:
        raise ValueError("T006 must use the specified DT6-FORM1 custom cutter")
    tool = replace(
        installed, blank_radius_mm=template.tip_radius_mm, radial_translation_mm=0.0
    )
    lines = [
        "DT6-FORM1 - FINITE CUSTOM GROUND FORM",
        "NORMAL TOOL PLANE; GAP BISECTOR +X; X,Y IN mm",
        "t=0..1 ON EACH SEGMENT; NO UPPER CONTINUATION",
        "TRIGONOMETRIC ARGUMENTS IN RADIANS",
        f"DP={template.diametral_pitch:.17g}; PA={template.pressure_angle_deg:.17g} DEG",
        f"N={template.reference_teeth}; ROOT R={template.root_radius_mm:.17g}",
        f"BASE R={template.base_radius_mm:.17g}; FINITE TIP R={template.tip_radius_mm:.17g}",
        f"TOOL PITCH TOOTH THICKNESS={tool.pitch_tooth_thickness_mm:.17g}",
        "ROOT ARC; DRUM-TIP TROCHOID RELIEF TO TIF; N6 WORKING INVOLUTE",
        f"TIF R={template.relief_junction_radius_mm:.4f}",
        "LOWER FLANK MIRRORS UPPER; ALL SEGMENTS REQUIRED",
    ]
    for segment in tool.native_segments(
        unit_scale=1.0, clearance_radius_mm=template.tip_radius_mm + 1.0
    ):
        if segment.kind not in {"root_arc", "relief", "flank"}:
            continue
        lines.append(f"{segment.name} ({segment.kind})")
        for coordinate, equation in (("X", segment.x), ("Y", segment.y)):
            # Break only between tokens: never split a numeric literal or an
            # exponent. Removing whitespace recovers the exact core expression.
            tokens = re.findall(
                r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[^\s]",
                equation,
            )
            lines.extend(
                textwrap.wrap(
                    f"{coordinate}(t)= " + " ".join(tokens),
                    width=CUTTER_DETAIL_LINE_CHARS,
                    subsequent_indent="  ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
    lines.extend(
        (
            "INSTALLED T, PLUNGE, BLANK OD AND GRADES: SHEET 1",
            "INDEX GAP BY pi/6 FROM +X TOOTH ZERO",
        )
    )
    lines.extend(
        textwrap.wrap(
            f"PROFILE SOURCE: {template.source}",
            width=CUTTER_DETAIL_LINE_CHARS,
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False,
        )
    )
    return "\n".join(lines)
