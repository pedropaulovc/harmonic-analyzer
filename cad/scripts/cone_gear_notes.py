"""Drawing-only text for the cone-gear configuration sheets.

This module deliberately performs no ``_config`` reads because the cone-gear
constants are imported by assemblies.  Every configuration sheet receives its
own native dimensions and a tooth-system block for that configuration.  The
shaft joint's text lives here too, for the drive-train assembly step that makes
the joint; no part sheet prints it.
"""

from __future__ import annotations

import cone_gear_spec as spec


CYLINDER_MATE_NUMBER = "MHA-027"


def _floor_limits(teeth: int, floor_dia: float) -> str:
    if teeth not in spec.FLOOR_LIMITS_MM:
        return f"{floor_dia:.3f} MIN"
    minimum, maximum = spec.FLOOR_LIMITS_MM[teeth]
    return f"{minimum:.3f} MIN / {maximum:.3f} MAX"


def gear_data(teeth: int) -> str:
    """Return the complete tooth-system block for one configuration sheet."""
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    minimum, maximum = spec.BACKLASH_ACCEPTANCE_MM
    pitch_dia = teeth * spec.MODULE_MM
    floor_dia = 2.0 * spec.floor_radius_mm(teeth)
    rows = (
        ("CONFIGURATION", f"T{teeth:03d}"),
        ("NUMBER OF TEETH", f"{teeth}"),
        ("DIAMETRAL PITCH", f"{spec.DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE (mm, REF)", f"{spec.MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{pitch_dia:.2f}"),
        # U40: the floor is a limit, not a reference -- cutting deeper for a
        # thinner tooth would thin the root-to-bore web.
        ("GAP FLOOR DIAMETER (mm)", _floor_limits(teeth, floor_dia)),
        ("TOOTH FORM", spec.TOOTH_FORM),
        (
            "MATES WITH",
            f"CYLINDER GEAR {CYLINDER_MATE_NUMBER}, 120T, FULL STANDARD THICKNESS",
        ),
        # The drive-train cone is backed off its drum on inclined axes, so the
        # 120T tips never reach the reference-centre-distance depth; the cone
        # reaches deeper through its own oversize blank and thickened tooth
        # (U38 option 1b).  Say so where the mate is named, so a blind review
        # does not read the tip or the thickness as an error.
        ("OPERATING MESH", "LONG ADDENDUM, PARTIAL DEPTH ON INCLINED AXES"),
        (
            f"BACKLASH WITH {CYLINDER_MATE_NUMBER}, ACCEPT AT ASSEMBLY (mm)",
            f"{minimum:.2f} TO {maximum:.2f}",
        ),
        # Rule 6: the sheet states results, never how to cut them.  TOOTH
        # FORM (floor any shape, not below the floor diameter), the floor
        # limits, the tooth-thickness band and the assembly backlash are the
        # whole acceptance for the thickened tooth's narrow gap.
        ("TOOTH THICKNESS IN VIEW", "ARC LENGTH AT PITCH DIAMETER"),
    )
    return "\n".join(["GEAR DATA", *(f"{label}:  {value}" for label, value in rows)])


# The user approved either a metallurgical joint or a retaining-compound joint
# for every cone gear.  Joining is a method, so rule 6 keeps it off the part
# sheets: the drive-train assembly step that fixes each gear to its shaft
# imports this constant rather than retyping it.  There is no key, pin, set
# screw, or hub in the evidence or model.
ATTACHMENT = "SOLDER, SILVER-BRAZE OR LOCTITE 638/648"
SHAFT_MATE_NUMBER = "MHA-014"

# The named rule-12 exceptions (user rulings U42 and U40, 2026-09-23) are a
# design-review record the machinist cannot act on, so no sheet prints them.
# They live in cone_gear_spec as CONTACT_RATIO_EXCEPTION_TEETH and
# WEB_EXCEPTIONS_MM, each pinned to its derivation by test_cone_gear_mesh_design
# and test_cone_gear_drawing.
DRAWING_NOTES = "\n".join(
    (
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        "MAKE ONE GEAR FROM EACH SHEET IN THIS PACKAGE.",
        "PLAIN BORE, NO KEYWAY.",
    )
)


def drawing_notes(teeth: int) -> str:
    """Return one configuration sheet's manufacturing notes."""
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    return DRAWING_NOTES
