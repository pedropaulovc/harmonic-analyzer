"""Drawing-only text for the cone-gear configuration sheets.

This module deliberately performs no ``_config`` reads because the cone-gear
constants are imported by assemblies.  Every configuration sheet receives its
own native dimensions and a tooth-system block for that configuration.  The
shaft joint's text lives here too, for the drive-train assembly step that makes
the joint; no part sheet prints it.
"""

from __future__ import annotations

import math

import cone_gear_spec as spec


CYLINDER_MATE_NUMBER = "MHA-027"


def _floor_limits(teeth: int) -> str:
    minimum, maximum = spec.floor_limits_mm(teeth)
    return f"{minimum:.3f} MIN / {maximum:.3f} MAX"


# The U42 gears' worst-case transverse contact ratio with MHA-027, rounded
# DOWN to two places so no sheet claims more than the part has.  Sheet text, so it lives here and not in
# cone_gear_spec (which the drive-train imports);
# test_cone_gear_mesh_design re-derives every value from the drive-train pose
# and the printed bands, over exactly spec.CONTACT_RATIO_EXCEPTION_TEETH.
WORST_CONTACT_RATIO: dict[int, float] = {
    6: 0.17,
    12: 0.42,
    18: 0.60,
    24: 0.74,
    30: 0.86,
    36: 0.96,
    42: 1.05,
}


def root_to_bore_web_min_mm(teeth: int) -> float:
    """Return the thinnest root-to-bore web the printed limits allow."""
    floor_min, _floor_max = spec.floor_limits_mm(teeth)
    return (floor_min - (spec.bore_dia_mm(teeth) + spec.BORE_DIA_BAND[0])) / 2.0


# The named shortfalls print as plain facts on the sheets they affect, so a
# blind reviewer reads them off the package; the governance lives in the
# policy's Named exceptions table and in these tags, never on the sheet.  The
# row says HOLE, not BORE: the bore is a native dimension, and GEAR DATA
# carries no parallel BORE row.
# Named exception: MHA-013 web (drawing-simplicity-policy.md, "Named exceptions").
def web_row(teeth: int) -> tuple[str, str]:
    """Return the GEAR DATA row stating one gear's thinnest web as a MIN."""
    # rounded DOWN: the sheet never states more web than the limits give
    web = math.floor(root_to_bore_web_min_mm(teeth) * 100.0) / 100.0
    return ("WEB, GAP FLOOR TO HOLE (mm, REF)", f"{web:.2f} MIN")


# Named exception: MHA-013 contact ratio (drawing-simplicity-policy.md, "Named exceptions").
def contact_ratio_row(teeth: int) -> tuple[str, str]:
    """Return the GEAR DATA row stating one gear's worst-case contact ratio."""
    return (
        f"CONTACT RATIO WITH {CYLINDER_MATE_NUMBER}, WORST CASE (REF)",
        f"{WORST_CONTACT_RATIO[teeth]:.2f}",
    )


def gear_data(teeth: int) -> str:
    """Return the complete tooth-system block for one configuration sheet."""
    if teeth not in spec.CONFIGURATION_TEETH:
        raise ValueError(f"unsupported cone-gear tooth count {teeth}")
    minimum, maximum = spec.BACKLASH_ACCEPTANCE_MM
    pitch_dia = teeth * spec.MODULE_MM
    rows = (
        ("CONFIGURATION", f"T{teeth:03d}"),
        ("NUMBER OF TEETH", f"{teeth}"),
        ("DIAMETRAL PITCH", f"{spec.DIAMETRAL_PITCH:.2f} (NONSTANDARD)"),
        ("MODULE (mm, REF)", f"{spec.MODULE_MM:.3f}"),
        ("PRESSURE ANGLE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{pitch_dia:.2f}"),
        # U40: the floor is a limit, not a reference -- cutting deeper for a
        # thinner tooth would thin the root-to-bore web, and a floor above MAX
        # would rub the drum tip.
        ("GAP FLOOR DIAMETER (mm)", _floor_limits(teeth)),
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
    if teeth in spec.WEB_EXCEPTIONS_MM:
        rows += (web_row(teeth),)
    if teeth in WORST_CONTACT_RATIO:
        rows += (contact_ratio_row(teeth),)
    return "\n".join(["GEAR DATA", *(f"{label}:  {value}" for label, value in rows)])


# The user approved either a metallurgical joint or a retaining-compound joint
# for every cone gear.  Joining is a method, so rule 6 keeps it off the part
# sheets: the drive-train assembly step that fixes each gear to its shaft
# imports this constant rather than retyping it.  There is no key, pin, set
# screw, or hub in the evidence or model.
ATTACHMENT = "SOLDER, SILVER-BRAZE OR LOCTITE 638/648"
SHAFT_MATE_NUMBER = "MHA-014"

# The named shortfalls (user rulings U42 and U40, 2026-09-23) print once each,
# as GEAR DATA rows (web_row, contact_ratio_row), never again in these notes.
# Which gears carry them stays in cone_gear_spec (CONTACT_RATIO_EXCEPTION_TEETH,
# WEB_EXCEPTIONS_MM); each printed value is pinned to its derivation by
# test_cone_gear_mesh_design and test_cone_gear_drawing.
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
