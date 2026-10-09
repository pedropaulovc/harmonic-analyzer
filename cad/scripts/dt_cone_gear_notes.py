"""Model-stamped cutting and inspection data from the finite cutter authority.

Nonconjugate meshes print STOCK-FORM COVERAGE, never an ideal contact ratio.
The part-local specification replays the original numerical receipt and current
native geometry. Drawing references are not current installed-mesh authority.
"""

from __future__ import annotations

import math
import re
import textwrap
from dataclasses import replace

import dt_cone_gear_spec as spec

CYLINDER_MATE_NUMBER = "MHA-DT-012"
CUTTER_DETAIL_SHEET = "DT6-FORM1"
CUTTER_DETAIL_LINE_CHARS = 108


def root_to_bore_web_min_mm(teeth: int) -> float:
    """Print-worst radial ligament; the fitted D-flat only leaves more metal."""
    minimum, _maximum = spec.floor_limits_mm(teeth)
    scale = 10**spec.BORE_BAND_PLACES
    bore_maximum = math.ceil(
        (spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[0]) * scale - 1e-9
    ) / scale
    return (minimum - bore_maximum) / 2.0


def cutter_description(teeth: int) -> str:
    template = spec.stock_form_profile(teeth).template
    if template.cutter_number is None:
        return f"{template.name}; CUSTOM TEMPLATE {template.reference_teeth}T; NOT STOCK"
    minimum, maximum = template.teeth_range
    upper = "UP" if maximum is None else str(maximum)
    return f"#{template.cutter_number} {minimum}-{upper}T; TEMPLATE {template.reference_teeth}T"


def gear_data(teeth: int) -> str:
    """One physical recipe with explicitly recorded, not installed, references."""
    profile = spec.stock_form_profile(teeth)
    mesh = spec.stock_form_reference_data(teeth)
    if mesh["qualification"] != "geometry-qualified-reference":
        raise ValueError(f"T{teeth:03d}: cutter geometry reference is not qualified")
    minimum, maximum = spec.BACKLASH_ACCEPTANCE_MM
    # Conservative reference reporting: round coverage/reserve/web down and
    # error/gap bounds up. These rows do not replace native toleranced sizes.
    coverage = math.floor(mesh["coverage_min"] * 100.0) / 100.0
    reserve = math.floor(mesh["phase_reserve_rad"] * 1e6) / 1e6
    gap = math.ceil(mesh["noncarrying_gap_mm"] * 1e4) / 1e4
    te = math.ceil(mesh["te_bound_rad"] * 1e6) / 1e6
    web = math.floor(root_to_bore_web_min_mm(teeth) * 100.0) / 100.0
    whole_depth_max = math.ceil(max(
        corner.blank_radius_mm - corner.root_radius_min_mm
        for corner in spec.manufacturing_corner_profiles(teeth)
    ) * 1e4) / 1e4
    rows = (
        ("CONFIGURATION / TEETH", f"T{teeth:03d} / {teeth}"),
        ("DIAMETRAL PITCH / PRESSURE ANGLE", f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("CUTTER", cutter_description(teeth)),
        ("TOOL T / PLUNGE (mm, REF)", f"{profile.radial_translation_mm:.4f} / {profile.plunge_mm:.4f}"),
        ("WHOLE DEPTH MAX / ROOT ARC R (mm, REF)", f"{whole_depth_max:.4f} / {profile.template.root_radius_mm:.4f}"),
        ("TOOTH FORM", "FINITE INVOLUTE; RADIAL BELOW BASE" if profile.template.root_radius_mm < profile.template.base_radius_mm else "FINITE INVOLUTE; ABOVE-BASE ROOT ARC"),
        ("MATE", f"{CYLINDER_MATE_NUMBER}, 120T; INCLINED AXES"),
        ("MESH REFERENCE SCOPE", "RECORDED SOURCE RECEIPT; CURRENT INSTALLED SOURCE REBIND REQUIRED"),
        ("BACKLASH AT ASSEMBLY (mm)", f"{minimum:.2f} TO {maximum:.2f}"),
        ("ACTUAL 3D STOCK-FORM COVERAGE MIN (REF)", f"{coverage:.2f}"),
        ("PHASE RESERVE (rad, REF)", f"{reserve:.6f}"),
        ("NONCARRYING GAP MAX (mm, REF)", f"{gap:.4f}"),
        ("UNTARED 21-STALL SIGNED TE BOUND (+/-rad, REF)", f"{te:.6f}"),
        ("ROOT RADIAL MIN/MAX (mm, REF)", f"{profile.root_radius_min_mm:.3f} / {profile.root_radius_max_mm:.3f}"),
        ("WEB MIN (mm, REF)", f"{web:.2f}"),
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
        "RAISED ROOT; RADIAL ROOT-TO-BASE; N6 WORKING INVOLUTE",
        "LOWER FLANK MIRRORS UPPER; ALL SEGMENTS REQUIRED",
    ]
    for segment in tool.native_segments(unit_scale=1.0, clearance_radius_mm=template.tip_radius_mm + 1.0):
        if segment.kind not in {"root_arc", "radial", "flank"}:
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
