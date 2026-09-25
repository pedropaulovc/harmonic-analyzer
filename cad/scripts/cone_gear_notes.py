"""Drawing-only text for the cone-gear configuration sheets.

This module deliberately performs no ``_config`` reads because the cone-gear
constants are imported by assemblies.  Every configuration sheet receives its
own native dimensions and a tooth-system block for that configuration.
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
        ("TOOTH THICKNESS IN VIEW", "ARC LENGTH AT PITCH DIAMETER"),
        # The thickened tooth leaves a gap narrower than any catalogue
        # cutter's, and no catalogue cutter exists at 49.82 DP: a 48 DP cutter
        # plunged to this tooth thickness would leave the floor about 0.5 high.
        # The tooth-thickness band and the assembly backlash are the acceptance.
        ("GAP CUTTER", "SINGLE-POINT FLY CUTTER GROUND TO THE GAP FORM"),
        ("CUTTING", "PLUNGE TO FLOOR; WIDEN BY INDEXING, NEVER BY SINKING"),
    )
    return "\n".join(["GEAR DATA", *(f"{label}:  {value}" for label, value in rows)])


# The user approved either a metallurgical joint or a retaining-compound joint
# for every cone gear.  State the required bonded interface first, then list
# the accepted joint systems without turning one process into the part's
# definition.  There is no key, pin, set screw, or hub in the evidence or model.
ATTACHMENT_PROCESS = "SOLDER OR SILVER-BRAZE"
ATTACHMENT_ALTERNATIVE = "LOCTITE 638 OR LOCTITE 648"
SHAFT_MATE_NUMBER = "MHA-014"

# Named rule-12 exceptions (user rulings U42 and U40, 2026-09-23), each
# printed only on the sheets it covers: the blind review reads every other
# sheet without it.
CONTACT_RATIO_EXCEPTION = (
    f"CONTACT RATIO BELOW 1.1 ON T{spec.CONTACT_RATIO_EXCEPTION_TEETH[0]:03d}"
    f"-T{spec.CONTACT_RATIO_EXCEPTION_TEETH[-1]:03d}: "
    "ACCEPTED EXCEPTION (BOOK FIDELITY)."
)


def web_exception(teeth: int) -> str:
    """Return the sheet line naming one gear's accepted thin web."""
    return (
        f"ROOT-TO-BORE WEB {spec.WEB_EXCEPTIONS_MM[teeth]:.2f} MIN, BELOW 1.5: "
        "ACCEPTED EXCEPTION (BOOK FIDELITY)."
    )


_COMMON_NOTES = (
    "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
    "MAKE ONE GEAR FROM EACH SHEET IN THIS PACKAGE.",
    f"PLAIN BORE, NO KEYWAY; BOND TO {SHAFT_MATE_NUMBER} SHAFT SEAT AT ASSEMBLY.",
    f"ACCEPTABLE BONDS: {ATTACHMENT_PROCESS}, OR {ATTACHMENT_ALTERNATIVE}.",
)


def drawing_notes(teeth: int) -> str:
    """Return one configuration sheet's manufacturing notes."""
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    lines = list(_COMMON_NOTES)
    if teeth in spec.CONTACT_RATIO_EXCEPTION_TEETH:
        lines.append(CONTACT_RATIO_EXCEPTION)
    if teeth in spec.WEB_EXCEPTIONS_MM:
        lines.append(web_exception(teeth))
    return "\n".join(lines)
