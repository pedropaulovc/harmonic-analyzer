"""Model-stamped cutting and inspection data from the finite cutter authority,
and the part's print maps (which feature's dimension each sheet prints).

Every value comes from dt_cone_gear_spec; the backlash reference is the
closed-form standard check of the drum mesh (dt_mesh_checks).
"""

from __future__ import annotations

import math

import cone_set_stack
import dt_cone_gear_spec as spec
import dt_mesh_checks

CYLINDER_MATE_NUMBER = "MHA-DT-12"
# The teeth's do-not-cut (rule 7): flagged to the teeth in sheet note 2, not
# an unflagged line in the general block (repeat review of 218c85b6).
TOOTH_EDGE_NOTE = "NO EDGE BREAK ON TEETH."

# The tip diameter prints across the side view, beside the face width (rule
# 11, turned parts read like the lathe; repeat review of 218c85b6). Its owner
# there is a hidden Right-plane witness, dt_alignment_pinion's
# OutsideDiaReference: a diametric BlankDia driven by the blank's own 2 * "Ra"
# and banded like it. dt_cone_gear_spec lists the model owner, BlankProfile's
# driving circle; this part prints the witness instead, so its print maps are
# the spec's with that one dimension moved.
BLANK_DIA_REFERENCE_SKETCH = "BlankDiaReference"
_BLANK_DIA_MODEL_OWNER = "BlankProfile"
if "BlankDia" not in spec.DRAWING_DIMENSIONS[_BLANK_DIA_MODEL_OWNER]:
    raise AssertionError("dt_cone_gear_spec no longer marks BlankDia on BlankProfile")


def _print_owner(feature: str, name: str) -> str:
    if (feature, name) == (_BLANK_DIA_MODEL_OWNER, "BlankDia"):
        return BLANK_DIA_REFERENCE_SKETCH
    return feature


DRAWING_DIMENSIONS: dict[str, set[str]] = {}
for _feature, _names in spec.DRAWING_DIMENSIONS.items():
    for _name in sorted(_names):
        DRAWING_DIMENSIONS.setdefault(_print_owner(_feature, _name), set()).add(_name)
DRAWING_PRECISION: dict[str, dict[str, int]] = {}
for _feature, _places in spec.DRAWING_PRECISION.items():
    for _name, _decimals in _places.items():
        DRAWING_PRECISION.setdefault(_print_owner(_feature, _name), {})[_name] = _decimals
REFERENCE_SKETCHES = (*spec.REFERENCE_SKETCHES, BLANK_DIA_REFERENCE_SKETCH)


def root_to_bore_web_min_mm(teeth: int) -> float:
    """Print-worst radial ligament: to the keyway's top corner on a keyed
    gear, to the largest printed round bore on T012..T024."""
    return spec.web_min_mm(teeth)


def cutter_description(teeth: int) -> str:
    # A numbered stock cutter is ground for the lowest count of its range,
    # so its number and range say all a handbook reader needs; "TEMPLATE nT"
    # was a private phrase (rule 26, screen of f21dfcdd2ba7).
    template = spec.stock_form_profile(teeth).template
    minimum, maximum = template.teeth_range
    teeth_range = f"{minimum}T AND UP" if maximum is None else f"{minimum}-{maximum}T"
    return f"#{template.cutter_number} INVOLUTE GEAR CUTTER, {teeth_range}"


# Standard words only (rule 26): the stock cutter's own form is what it cuts,
# so "FINITE", "RADIAL BELOW BASE" and "ABOVE-BASE ROOT ARC" told the builder
# nothing a handbook defines.
TOOTH_FORM = "INVOLUTE, AS CUT BY THE CUTTER"


def gear_data(teeth: int) -> str:
    """One physical recipe with its reference sizes, in decimal inch."""
    spec.material_specification(teeth)  # MHA-DT-03 configurations only
    profile = spec.stock_form_profile(teeth)
    mesh = dt_mesh_checks.cone_check(teeth)
    inch = spec.inch_text
    # Conservative reference reporting: round the backlash range and web
    # outward. These rows do not replace native toleranced sizes. Backlash
    # runs from the feel set's floor (no bind) to the loosest running centre
    # (dt_mesh_checks, owner direction 2026-11-11).
    minimum = spec.inch_grid_mm(max(0.0, mesh.backlash_floor_mm), 3, math.floor)
    maximum = spec.inch_grid_mm(mesh.backlash_max_mm, 3, math.ceil)
    web = spec.inch_grid_mm(root_to_bore_web_min_mm(teeth), 4, math.floor)
    whole_depth_max = spec.inch_grid_mm(max(
        corner.blank_radius_mm - corner.root_radius_min_mm
        for corner in spec.manufacturing_corner_profiles(teeth)
    ), 4, math.ceil)
    low, high = spec.over_pins_limits_mm(teeth)
    pin = spec.over_pins_pin_dia_mm(teeth)
    rows = (
        ("CONFIGURATION / TEETH", f"T{teeth:03d} / {teeth}"),
        ("DIAMETRAL PITCH / PRESSURE ANGLE", f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f}\u00b0"),
        # The circle the circular tooth thickness is measured on (its callout
        # no longer names it: rule 7 allows two lines of words).
        ("PITCH DIAMETER (REF)", inch(teeth * spec.MODULE_MM, 4)),
        ("CUTTER", cutter_description(teeth)),
        # The cutter's own radial offset is a setup quantity, not something
        # the shop needs: the plunge from the blank OD is (ENFORCE round 1 of
        # #971: "TOOL T" was undefined).
        ("CUTTER PLUNGE FROM BLANK OD (REF)", inch(profile.plunge_mm, 4)),
        # The arc is the cutter template's, which is the gear's own only on
        # the custom-cutter sheets (ENFORCE round 3 of #971).
        ("WHOLE DEPTH MAX / CUTTER ROOT ARC R (REF)",
         f"{inch(whole_depth_max, 4)} / {inch(profile.template.root_radius_mm, 4)}"),
        ("TOOTH FORM", TOOTH_FORM),
        ("MATE", f"{CYLINDER_MATE_NUMBER}, 120T"),
        # The fit route of the tip, thickness and root bands (drawing-
        # guidelines "What the shop holds"): the cone mesh is set by feel at
        # assembly, so its backlash is accepted there, from no binding up.
        ("BACKLASH WITH MATE, ACCEPT AT ASSEMBLY",
         f"{inch(minimum, 3)} TO {inch(maximum, 3)}"),
        # The bore's worst ligament (RV-03 on T012, RV-07 on T030).
        ("WEB MIN (REF)", inch(web, 4)),
        # cone_set_stack books each gear's tooth runout about its bore.
        ("TOOTH CUTTING SETUP, ACCEPT AT SETUP",
         f"{inch(cone_set_stack.TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX TO FINISHED BORE"),
        # The measurable acceptance of the circular tooth thickness band
        # (spec.over_pins_limits_mm): every sheet (ENFORCE round 1 of #971).
        (
            f"OVER 2 PINS \u00d8{inch(pin, 3)}, OPPOSITE GAPS",
            f"{inch(low, spec.OVER_PINS_PLACES)} TO {inch(high, spec.OVER_PINS_PLACES)}",
        ),
    )
    return "\n".join(("GEAR DATA", *(f"{label}:  {value}" for label, value in rows)))


DRAWING_NOTES = "QTY 1 PER DRAWING NUMBER."


def drawing_notes(teeth: int) -> str:
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    return DRAWING_NOTES
