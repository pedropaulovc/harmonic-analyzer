"""Drawing-only text for the cone-gear configuration sheets.

The part builder passes the configured fit values into :func:`gear_data`; this
module deliberately performs no ``_config`` reads because ``build_cone_gear``
is imported by the other gear recipes.  Every configuration sheet receives its
own native dimensions and a tooth-system block for that configuration.
"""

from __future__ import annotations

from collections.abc import Sequence

import cone_gear_spec as spec


CYLINDER_MATE_NUMBER = "MHA-027"


def tooth_thickness_band(backlash_mm: Sequence[float]) -> tuple[float, float]:
    """Return the native tooth-thickness ``(upper, lower)`` deviations.

    The cylinder gear is cut to full standard thickness, so the cone gear gives
    the pair its configured backlash by removing the minimum-to-maximum backlash
    from the standard circular tooth thickness.
    """
    if len(backlash_mm) != 2:
        raise ValueError("gear-mesh backlash must contain minimum and maximum")
    minimum, maximum = (float(value) for value in backlash_mm)
    if minimum <= 0.0 or maximum <= minimum:
        raise ValueError(f"invalid gear-mesh backlash band {tuple(backlash_mm)!r}")
    return -minimum, -maximum


def gear_data(teeth: int, backlash_mm: Sequence[float]) -> str:
    """Return the complete tooth-system block for one configuration sheet."""
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    minimum, maximum = (float(value) for value in backlash_mm)
    # Validate the configured band through the same derivation used by the part.
    tooth_thickness_band((minimum, maximum))
    pitch_dia = teeth * spec.MODULE_MM
    whole_depth = 2.157 * spec.MODULE_MM
    rows = (
        ("CONFIGURATION", f"T{teeth:03d}"),
        ("NUMBER OF TEETH", f"{teeth}"),
        ("DIAMETRAL PITCH", f"{spec.DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE (mm, REF)", f"{spec.MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{pitch_dia:.2f}"),
        ("WHOLE DEPTH (mm, REF)", f"{whole_depth:.2f}"),
        ("TOOTH FORM", "STRAIGHT SPUR INVOLUTE, FULL DEPTH"),
        (
            "MATES WITH",
            f"CYLINDER GEAR {CYLINDER_MATE_NUMBER}, 120T, FULL STANDARD THICKNESS",
        ),
        (
            f"BACKLASH WITH {CYLINDER_MATE_NUMBER}, ACCEPT AT ASSEMBLY (mm)",
            f"{minimum:.2f} TO {maximum:.2f}",
        ),
    )
    return "\n".join(["GEAR DATA", *(f"{label}:  {value}" for label, value in rows)])


# The user approved either a metallurgical joint or a retaining-compound joint
# for every cone gear.  There is no key, pin, set screw, or hub in the evidence
# or model; the plain fitted bore is the whole attachment interface.
ATTACHMENT_PROCESS = "SOLDER OR SILVER-BRAZE TO"
ATTACHMENT_ALTERNATIVE = "LOCTITE 638 OR 648 RETAINING COMPOUND ACCEPTABLE"
SHAFT_MATE_NUMBER = "MHA-014"

DRAWING_NOTES = "\n".join(
    (
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        "MAKE ONE GEAR FROM EACH SHEET IN THIS PACKAGE.",
        f"PLAIN BORE, NO KEYWAY: {ATTACHMENT_PROCESS} THE {SHAFT_MATE_NUMBER}",
        f"SHAFT SEAT AT ASSEMBLY; OR USE {ATTACHMENT_ALTERNATIVE}.",
    )
)
