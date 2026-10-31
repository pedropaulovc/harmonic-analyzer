"""Model-stamped cutting and inspection data from the finite cutter authority.

Every value comes from dt_cone_gear_spec; the backlash reference is the
closed-form standard check of the drum mesh (dt_mesh_checks).
"""

from __future__ import annotations

import math
import re
import textwrap
from dataclasses import replace

import cone_set_stack
import dt_cone_gear_spec as spec
import dt_mesh_checks

CYLINDER_MATE_NUMBER = "MHA-DT-12"
CUTTER_DETAIL_SHEET = "DT6-FORM1"
CUTTER_DETAIL_LINE_CHARS = 108


def root_to_bore_web_min_mm(teeth: int) -> float:
    """Print-worst radial ligament; the fitted D-flat only leaves more metal."""
    minimum, _maximum = spec.floor_limits_mm(teeth)
    bore_maximum = spec.inch_grid_mm(
        spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[0], spec.BORE_BAND_PLACES, math.ceil
    )
    return (minimum - bore_maximum) / 2.0


def cutter_description(teeth: int) -> str:
    template = spec.stock_form_profile(teeth).template
    if template.cutter_number is None:
        # The tool is ground to the T006 tooth space; sheet 21 defines that
        # space as T006 geometry (ENFORCE round 1 of #971: as a tool sheet it
        # carried the gear's title block and no tool material).
        return f"NOT STOCK; FORM = TOOTH SPACE, SHEET {len(spec.CONFIGURATION_TEETH) + 1}"
    minimum, maximum = template.teeth_range
    upper = "UP" if maximum is None else str(maximum)
    return f"#{template.cutter_number} {minimum}-{upper}T; TEMPLATE {template.reference_teeth}T"


def _tooth_form(template) -> str:
    if template.relief is not None:
        return f"FINITE INVOLUTE; RELIEF BELOW R{spec.inch_text(template.relief_junction_radius_mm, 4)}"
    if template.root_radius_mm < template.base_radius_mm:
        return "FINITE INVOLUTE; RADIAL BELOW BASE"
    return "FINITE INVOLUTE; ABOVE-BASE ROOT ARC"


def gear_data(teeth: int) -> str:
    """One physical recipe with its reference sizes, in decimal inch."""
    profile = spec.stock_form_profile(teeth)
    mesh = dt_mesh_checks.cone_check(teeth)
    inch = spec.inch_text
    # Conservative reference reporting: round the backlash range and web
    # outward. These rows do not replace native toleranced sizes. Backlash is
    # the set-at-assembly mesh's RSS band about its nominal (dt_mesh_checks).
    spread = mesh.backlash_nominal_mm - mesh.backlash_rss_mm
    minimum = spec.inch_grid_mm(mesh.backlash_rss_mm, 3, math.floor)
    maximum = spec.inch_grid_mm(mesh.backlash_nominal_mm + spread, 3, math.ceil)
    web = spec.inch_grid_mm(root_to_bore_web_min_mm(teeth), 4, math.floor)
    whole_depth_max = spec.inch_grid_mm(max(
        corner.blank_radius_mm - corner.root_radius_min_mm
        for corner in spec.manufacturing_corner_profiles(teeth)
    ), 4, math.ceil)
    low, high = spec.over_pins_limits_mm(teeth)
    pin = spec.over_pins_pin_dia_mm(teeth)
    rows = (
        ("CONFIGURATION / TEETH", f"T{teeth:03d} / {teeth}"),
        ("DIAMETRAL PITCH / PRESSURE ANGLE", f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("CUTTER", cutter_description(teeth)),
        # The cutter's own radial offset is a setup quantity, not something
        # the shop needs: the plunge from the blank OD is (ENFORCE round 1 of
        # #971: "TOOL T" was undefined).
        ("CUTTER PLUNGE FROM BLANK OD (REF)", inch(profile.plunge_mm, 4)),
        # The arc is the cutter template's, which is the gear's own only on
        # the custom-cutter sheets (ENFORCE round 3 of #971).
        ("WHOLE DEPTH MAX / CUTTER ROOT ARC R (REF)",
         f"{inch(whole_depth_max, 4)} / {inch(profile.template.root_radius_mm, 4)}"),
        ("TOOTH FORM", _tooth_form(profile.template)),
        ("MATE", f"{CYLINDER_MATE_NUMBER}, 120T; INCLINED AXES"),
        ("BACKLASH WITH MATE (REF)", f"{inch(minimum, 3)} TO {inch(maximum, 3)}"),
        ("ROOT RADIAL MIN/MAX (REF)",
         f"{inch(profile.root_radius_min_mm, 4)} / {inch(profile.root_radius_max_mm, 4)}"),
        # Pending exception ruling: MHA-DT-03 web (#971).
        ("WEB MIN (REF)", inch(web, 4)),
        # cone_set_stack books each gear's tooth runout about its bore.
        ("TOOTH CUTTING SETUP, ACCEPT AT SETUP",
         f"{inch(cone_set_stack.TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX TO FINISHED BORE"),
        # The measurable acceptance of the circular tooth thickness band
        # (spec.over_pins_limits_mm): every sheet, not only T006 (ENFORCE
        # round 1 of #971).
        (
            f"OVER 2 PINS \u00d8{inch(pin, 3)}, OPPOSITE GAPS",
            f"{inch(low, spec.OVER_PINS_PLACES)} TO {inch(high, spec.OVER_PINS_PLACES)}",
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
    installed = spec.stock_form_profile(6)
    template = installed.template
    if template.cutter_number is not None or template.name != CUTTER_DETAIL_SHEET:
        raise ValueError("T006 must use the specified DT6-FORM1 custom cutter")
    tool = replace(installed, blank_radius_mm=template.tip_radius_mm, radial_translation_mm=0.0)
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
    for segment in tool.native_segments(unit_scale=1.0, clearance_radius_mm=template.tip_radius_mm + 1.0):
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
            lines.extend(textwrap.wrap(
                f"{coordinate}(t)= " + " ".join(tokens),
                width=CUTTER_DETAIL_LINE_CHARS, subsequent_indent="  ",
                break_long_words=False, break_on_hyphens=False,
            ))
    lines.extend((
        "INSTALLED T, PLUNGE, BLANK OD AND GRADES: SHEET T006",
        "INDEX GAP BY pi/6 FROM D-FLAT NORMAL (+X TOOTH ZERO)",
    ))
    lines.extend(textwrap.wrap(
        f"PROFILE SOURCE: {template.source}", width=CUTTER_DETAIL_LINE_CHARS,
        subsequent_indent="  ", break_long_words=False, break_on_hyphens=False,
    ))
    return "\n".join(lines)


DRAWING_NOTES = "\n".join((
    "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
    "MAKE ONE GEAR FROM EACH T-CONFIGURATION SHEET.",
))


def drawing_notes(teeth: int) -> str:
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    return DRAWING_NOTES
