"""Drawing-only crank-drive gear text, above the shared geometry specs.

The cone-swing platform consumes the tip circle without importing these notes.
Exact stock tangent-span limits come from the part spec. Assembly requirements
are stated as requirements, not a certificate for the unqualified crossed mesh.
"""

from __future__ import annotations

import _config
from crank_mesh_requirements import HANDOVER_JUMP_MAX_MM, STOCK_FORM_COVERAGE_MIN
import dt_crank_drive_gear_spec as spec


# Keep the part's stock-form geometry independent of assembly diagnostics.
GEAR_MESH_BACKLASH_MM = tuple(_config.fit("gear_mesh", "backlash_mm"))


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


STOCK_FORM_COVERAGE_ROW = (
    "STOCK-FORM COVERAGE WITH MHA-DT-010, ACCEPT AT ASSEMBLY",
    f"{STOCK_FORM_COVERAGE_MIN:.2f} MIN; NO UNCOVERED PHASE; "
    f"HANDOVER JUMP {HANDOVER_JUMP_MAX_MM:.3f} mm MAX",
)


# Rule 6's compact data identifies the standard normal full-depth CUTTER.
# The supported blank's actual cut depth and root envelope are separately REF.
# The primary exact normal span controls the part, not an ideal tooth caliper.
GEAR_DATA = gear_data_note(
    [
        ("NUMBER OF TEETH", f"{spec.TEETH}"),
        (
            "DIAMETRAL PITCH, NORMAL (CUTTER)",
            f"{spec.CUTTER_DIAMETRAL_PITCH:.2f}",
        ),
        (
            "PRESSURE ANGLE, NORMAL (CUTTER)",
            f"{spec.CUTTER_PRESSURE_ANGLE_DEG:.1f} DEG",
        ),
        (
            "FORM CUTTER / REFERENCE TEETH / VIRTUAL TEETH (REF)",
            f"#{spec.CUTTER_NUMBER}, {spec.CUTTER_TEETH_RANGE[0]}-"
            f"{spec.CUTTER_TEETH_RANGE[1]}T / "
            f"{spec.CUTTER_TEMPLATE.reference_teeth} / "
            f"{spec.VIRTUAL_TEETH:.{spec.GEAR_DATA_REFERENCE_PLACES}f}",
        ),
        ("DIAMETRAL PITCH, TRANSVERSE (REF)", f"{spec.DIAMETRAL_PITCH:.2f}"),
        ("PRESSURE ANGLE, TRANSVERSE (REF)", f"{spec.PRESSURE_ANGLE_DEG:.2f} DEG"),
        ("PITCH DIAMETER (mm, REF)", f"{spec.PITCH_DIA:.2f}"),
        (
            "ACTUAL ROOT DIA MIN-MAX / MAX CUT DEPTH (mm, REF)",
            f"{spec.ROOT_DIA_MIN:.3f}-{spec.ROOT_DIA_MAX:.3f} / {spec.WHOLE_DEPTH:.3f}",
        ),
        (
            "HELIX AT PITCH DIA / LEAD (mm/rev, REF)",
            f"{spec.HELIX_ANGLE_DEG:.{spec.GEAR_DATA_HELIX_PLACES}f} DEG "
            f"{spec.HELIX_HAND} / "
            f"{spec.HELIX_LEAD_MM:.{spec.GEAR_DATA_REFERENCE_PLACES}f}",
        ),
        (
            f"BASE TANGENT SPAN OVER {spec.BASE_TANGENT_SPAN_TEETH} TEETH, NORMAL (mm), ACCEPT ON THIS PART",
            f"{spec.BASE_TANGENT_SPAN_LIMITS_MM[0]:.{spec.BASE_TANGENT_SPAN_PLACES}f} TO "
            f"{spec.BASE_TANGENT_SPAN_LIMITS_MM[1]:.{spec.BASE_TANGENT_SPAN_PLACES}f}",
        ),
        (
            "ACTUAL TRANSVERSE CIRCULAR PITCH THICKNESS (mm, REF)",
            f"{spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f}",
        ),
        ("NORMAL TOOL PLUNGE (mm, REF)", f"{spec.TOOL_PLUNGE_MM:.3f}"),
        (
            "TRANSVERSE BACKLASH WITH MHA-DT-010, ACCEPT AT ASSEMBLY (mm)",
            f"{GEAR_MESH_BACKLASH_MM[0]:.2f} TO {GEAR_MESH_BACKLASH_MM[1]:.2f}",
        ),
        (
            "TOOTH CUTTING SETUP, ACCEPT AT SETUP",
            f"{spec.TOOTH_RUNOUT_TIR_MM:.2f} TIR MAX TO FINISHED BORE",
        ),
        (
            "TOOTH FORM",
            f"FULL-DEPTH NORMAL-{spec.CUTTER_DIAMETRAL_PITCH:g}DP "
            f"PA{spec.CUTTER_PRESSURE_ANGLE_DEG:g} STOCK #{spec.CUTTER_NUMBER}/"
            f"{spec.CUTTER_TEMPLATE.reference_teeth}T; NOMINAL NORMAL-SECTION SCREW SWEEP",
        ),
        ("MATES WITH", "CRANK PINION MHA-DT-010, 16T STOCK #7/14T STRAIGHT SPUR"),
        STOCK_FORM_COVERAGE_ROW,
    ]
)

# The local +X flat and the paired shaft seat are defined by the native
# BoreAF and BoreDia dimensions; the assembly's stack locates this gear.
# The seat's owner, quoted only to identify the mate (rule 6). Hard-coded
# rather than read from ``_config.parts``: this module is in the part's
# rebuild closure, and a cross-part config read would make cone-gear-shaft.yaml
# a rebuild dependency of this gear. ``test_crank_drive_gear_drawing`` checks
# it against the registry offline, where a cross-check costs nothing.
SHAFT_MATE_NUMBER = "MHA-DT-004"

# Rule 6's only note: the standard title-block edge break would erase too
# much of these fine teeth. The D-bore, its AF band and its shaft mate are
# defined by the model dimensions and fit callout, not by another note.
DRAWING_NOTES = "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
