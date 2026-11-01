"""Drawing-only crank-drive gear text, above the shared geometry specs.

The cone-swing platform consumes the tip circle without importing these notes.
Exact stock tangent-span limits come from the part spec; the crossed mesh's
standard check lives in crank_mesh_stack.
"""

from __future__ import annotations

import math

import _config
import dt_crank_drive_gear_spec as spec
from dt_crank_drive_gear_spec import inch_text


# Keep the part's stock-form geometry independent of assembly diagnostics.
GEAR_MESH_BACKLASH_MM = tuple(_config.fit("gear_mesh", "backlash_mm"))


def gear_data_note(rows: list[tuple[str, str]], *, title: str = "GEAR DATA") -> str:
    """Render an aligned gear/sprocket data block for a property-linked note."""
    return "\n".join([title] + [f"{label}:  {value}" for label, value in rows])


def accept_limits_text(limits_mm: tuple[float, float], places: int) -> str:
    """Millimetre acceptance limits printed in inches, rounded INWARD to
    ``places``: an accepted part never leaves the limits the design checks."""
    scale = 10.0**places
    low = math.ceil(round(limits_mm[0] / spec.MM_PER_IN * scale, 6)) / scale
    high = math.floor(round(limits_mm[1] / spec.MM_PER_IN * scale, 6)) / scale
    if not low < high:
        raise AssertionError(
            f"inward inch rounding closes {limits_mm} at {places} places"
        )
    return f"{inch_text(low * spec.MM_PER_IN, places)} TO {inch_text(high * spec.MM_PER_IN, places)}"


# drawing-guidelines.md rule 7 (notes: few, flagged, never a method)'s compact data identifies the standard normal full-depth CUTTER.
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
        ("PITCH DIAMETER (REF)", inch_text(spec.PITCH_DIA, 3)),
        # One rounded REF root: the envelope's .0001 in spread is not a
        # range a turner can read (machinist review r1 of #1641), and the
        # plunge row below carries the cut depth.
        ("ROOT DIAMETER (REF)", inch_text(spec.ROOT_DIA_MIN, 3)),
        # The title block's ±1° governs (HELIX_ANGLE_TOLERANCE_DEG); the row
        # does not restate it (machinist review).
        (
            "HELIX AT PITCH DIA",
            f"{spec.HELIX_ANGLE_DEG:.{spec.GEAR_DATA_HELIX_PLACES}f} DEG {spec.HELIX_HAND}",
        ),
        (
            "LEAD (in/rev, REF)",
            inch_text(spec.HELIX_LEAD_MM, spec.GEAR_DATA_REFERENCE_PLACES),
        ),
        (
            f"BASE TANGENT SPAN OVER {spec.BASE_TANGENT_SPAN_TEETH} TEETH, NORMAL, ACCEPT ON THIS PART",
            accept_limits_text(spec.BASE_TANGENT_SPAN_LIMITS_MM, 4),
        ),
        (
            "ACTUAL TRANSVERSE CIRCULAR PITCH THICKNESS (REF)",
            inch_text(spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS, 4),
        ),
        ("NORMAL TOOL PLUNGE (REF)", inch_text(spec.TOOL_PLUNGE_MM, 4)),
        (
            "TRANSVERSE BACKLASH WITH MHA-DT-10, ACCEPT AT ASSEMBLY",
            accept_limits_text(GEAR_MESH_BACKLASH_MM, 3),
        ),
        (
            "TOOTH CUTTING SETUP, ACCEPT AT SETUP",
            f"{inch_text(spec.TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX TO FINISHED BORE",
        ),
        ("TOOTH FORM", "HELICAL INVOLUTE, FULL DEPTH, AS CUT BY THE FORM CUTTER"),
        # The title block's general edge break would erase too much of these
        # fine teeth; the requirement is a tooth fact, so it reads with them
        # (machinist review r1 of #1641: a free-floating note).
        ("TOOTH EDGES", "DO NOT BREAK OR CHAMFER FLANKS, TIPS OR ROOTS"),
        ("MATES WITH", "CRANK PINION MHA-DT-10, 16T SPUR"),
    ]
)

# The local +X flat and the paired shaft seat are defined by the native
# BoreAF and BoreDia dimensions; the assembly's stack locates this gear.
# The seat's owner, quoted only to identify the mate (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)). Hard-coded
# rather than read from ``_config.parts``: this module is in the part's
# rebuild closure, and a cross-part config read would make cone-gear-shaft.yaml
# a rebuild dependency of this gear. ``test_crank_drive_gear_drawing`` checks
# it against the registry offline, where a cross-check costs nothing.
SHAFT_MATE_NUMBER = "MHA-DT-04"
