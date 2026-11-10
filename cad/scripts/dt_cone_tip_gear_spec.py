r"""Pure-data contract of the cone tip gear, MHA-DT-37, and its drawing.

T006 as its own part (owner decision C1 keyed, 2026-11-09, PR #1992): the
six leaves cut by the DT6-FORM1 fly cutter, an integral Ø.0625 spigot running
south and an integral Ø.0625 pivot running north. Every tooth number is the
cone family's own (``dt_cone_gear_spec``, its tooth-form layer for six teeth);
the stems are ``cone_tip_cluster``'s.

Frame (a dt-cone-gear configuration's, so the drive train mates it the same
way): origin on the axis at the leaves' south face, the Front Plane; local
+Z north along the axis; tooth zero on local +X, so the Right Plane carries
the tooth phase. The leaves span z 0..FACE_WIDTH, the spigot
-SPIGOT_LENGTH_MM..0 and the pivot FACE_WIDTH..FACE_WIDTH + PIVOT_LENGTH_MM.
``PATTERN_AXIS`` is the gear axis the assembly mates, ``LEAVES_NORTH_PLANE``
the leaves' north face the MHA-DT-38 bushing seats on.

Both stems sit under the leaves' root at every printed limit, so the fly
cutter runs off over them (``CUTTER_RUNOFF_MM``). Lengths in mm; bands are
(upper, lower).
"""

from __future__ import annotations

import math

import _config
import cone_tip_cluster as cluster
import dt_cone_gear_spec as family
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_cone_gear_notes import BLANK_DIA_REFERENCE_SKETCH

PART_NAME = "dt-cone-tip-gear"
_ROW = _config.parts("dt-cone-tip-gear")
PART_NUMBER = str(_ROW["number"])
# The sheet's unit (the registry row's drawing_unit), as the family's.
UNIT = drawing_unit("parts/dt-cone-tip-gear", _ROW)
if PART_NAME != "dt-cone-tip-gear":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
MM_PER_IN = family.MM_PER_IN

# The four tip gears are the family's harder alloy (dimensions.yaml ch.12
# p.21); this part's title block prints it.
MATERIAL_SPEC = str(_ROW["material_specification"])
if MATERIAL_SPEC != family.TIP_MATERIAL_SPEC:
    raise AssertionError(
        f"{PART_NAME} material {MATERIAL_SPEC!r} is not the family's tip alloy "
        f"{family.TIP_MATERIAL_SPEC!r}"
    )

# --- The leaves: the family's T006, number for number ------------------------
TEETH = 6
PROFILE = family.stock_form_profile(TEETH)
TEMPLATE = PROFILE.template
if TEMPLATE.cutter_number is not None or TEMPLATE.name != "DT6-FORM1":
    raise AssertionError("T006 must be cut by the DT6-FORM1 custom fly cutter")
OUTSIDE_DIA = family.outside_dia_mm(TEETH)
BLANK_DIA_BAND = family.blank_dia_band(TEETH)
TOOTH_THICKNESS = family.tooth_thickness_mm(TEETH)
TOOTH_THICKNESS_BAND = family.tooth_thickness_band(TEETH)
FLOOR_LIMITS_MM = family.floor_limits_mm(TEETH)
FLOOR_DEVIATIONS_MM = family.gap_floor_deviations_mm(TEETH)
# The construction witness of the root envelope sits at the modelled floor.
FLOOR_DIA = 2.0 * family.floor_radius_min_mm(TEETH)
FACE_WIDTH = family.FACE_WIDTH
FACE_WIDTH_BAND = family.FACE_WIDTH_BAND
DIAMETRAL_PITCH = family.DIAMETRAL_PITCH
# The gap profile, its through cut and the six-gap pattern: the family's names
# for six teeth, the features the "Default Simplified" configuration
# suppresses (the assembly's small line views print the blank).
TOOTH_FEATURES = family.tooth_features(TEETH)
SIMPLIFIED_FEATURES = TOOTH_FEATURES[1:]
# The pattern's Top x Right reference axis: the part's first axis, the gear
# axis every assembly mate references (a dt-cone-gear configuration's Axis1).
PATTERN_AXIS = "Axis1"

# --- The stems ----------------------------------------------------------------
STEM_DIA_MM = cluster.STEM_DIA_MM
SPIGOT_DIA_BAND = cluster.SPIGOT_DIA_BAND
PIVOT_DIA_BAND = cluster.PIVOT_DIA_BAND
SPIGOT_LENGTH_MM = cluster.SPIGOT_LENGTH_MM
PIVOT_LENGTH_MM = cluster.PIVOT_LENGTH_MM
STEM_PLACES = cluster.STEM_PLACES
# The two stem lengths print at the title block's .XX.
STEM_LENGTH_PLACES = 2

SPIGOT_END_Z_MM = -SPIGOT_LENGTH_MM
LEAVES_NORTH_Z_MM = FACE_WIDTH
PIVOT_END_Z_MM = FACE_WIDTH + PIVOT_LENGTH_MM
OVERALL_LENGTH_MM = SPIGOT_LENGTH_MM + FACE_WIDTH + PIVOT_LENGTH_MM
LEAVES_NORTH_PLANE = "LeavesNorthPlane"

# The fly cutter runs off over both stems: the largest stem stands under the
# smallest printed root envelope at every limit (research: (.0840 - .0625)/2
# = .0108 in radial).
STEM_MAX_DIA_MM = STEM_DIA_MM + max(SPIGOT_DIA_BAND[0], PIVOT_DIA_BAND[0])
CUTTER_RUNOFF_MM = (FLOOR_LIMITS_MM[0] - STEM_MAX_DIA_MM) / 2.0
if CUTTER_RUNOFF_MM <= 0.0:
    raise AssertionError(
        f"a stem reaches the T006 root envelope: {CUTTER_RUNOFF_MM:.4f} mm radial"
    )
# The actual cutter corners (not only the printed MIN) clear the stems too.
_ACTUAL_ROOT_MIN_MM = min(
    corner.root_radius_min_mm for corner in family.manufacturing_corner_profiles(TEETH)
)
if _ACTUAL_ROOT_MIN_MM <= STEM_MAX_DIA_MM / 2.0:
    raise AssertionError("a DT6-FORM1 corner cuts into a stem")
# Each stem is a separate turned shoulder off its own face of the leaves.
if not 0.0 < STEM_MAX_DIA_MM < OUTSIDE_DIA + BLANK_DIA_BAND[1]:
    raise AssertionError("the stems must stand inside the leaves' blank")

# --- Fits, read from the cluster's proofs (REF on the sheet) ------------------
# The spigot's bond in the MHA-DT-04 socket and the T012/T018 stem bores.
SPIGOT_BOND_CLEARANCE_MM = cluster.SPIGOT_BOND_CLEARANCE_MM
# The pivot: the MHA-DT-38 bushing's press, then its run in MHA-DT-39's hole.
PIVOT_PRESS_INTERFERENCE_MM = cluster.BUSHING_PRESS_INTERFERENCE_MM
PIVOT_RUNNING_CLEARANCE_MM = cluster.PIVOT_RUNNING_CLEARANCE_MM
if max(SPIGOT_BOND_CLEARANCE_MM) > cluster.RETAINING_COMPOUND_MAX_GAP_MM:
    raise AssertionError("the spigot's bond gap exceeds the retaining compound's")

# The pivot runs in MHA-DT-39's reamed hole: rule 6's running-journal finish.
# Its cylinder shares the spigot's diameter, so the selector names its span.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_journal",
        MACHINED_UM,
        CylinderFace(STEM_DIA_MM, contains_z_mm=FACE_WIDTH + PIVOT_LENGTH_MM / 2.0),
        display_unit=UNIT,
    ),
)

# --- Native drawing contract ---------------------------------------------------
# The construction-only authoring sketches the part saves hidden; the front
# view shows the tooth and floor witnesses again, the side view the tip one.
TOOTH_REFERENCE_SKETCH = family.TOOTH_REFERENCE_SKETCH
GAP_FLOOR_SKETCH = family.GAP_FLOOR_SKETCH
REFERENCE_SKETCHES = (
    TOOTH_REFERENCE_SKETCH,
    GAP_FLOOR_SKETCH,
    BLANK_DIA_REFERENCE_SKETCH,
)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    BLANK_DIA_REFERENCE_SKETCH: {"BlankDia"},
    "Blank": {"FaceWidth"},
    TOOTH_REFERENCE_SKETCH: {"ToothThickness"},
    GAP_FLOOR_SKETCH: {"FloorDia"},
    "SpigotProfile": {"SpigotDia"},
    "Spigot": {"SpigotLength"},
    "PivotProfile": {"PivotDia"},
    "Pivot": {"PivotLength"},
}
# Places are the part's (drawing-simplicity-policy.md): the family's four on
# the tip, face, thickness and root; the stems' fitted diameters at the
# cluster's four; their lengths at the title block's two.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    BLANK_DIA_REFERENCE_SKETCH: {
        "BlankDia": family.DRAWING_PRECISION["BlankProfile"]["BlankDia"]
    },
    "Blank": {"FaceWidth": family.DRAWING_PRECISION["Blank"]["FaceWidth"]},
    TOOTH_REFERENCE_SKETCH: {
        "ToothThickness": family.DRAWING_PRECISION[TOOTH_REFERENCE_SKETCH][
            "ToothThickness"
        ]
    },
    GAP_FLOOR_SKETCH: {
        "FloorDia": family.DRAWING_PRECISION[GAP_FLOOR_SKETCH]["FloorDia"]
    },
    "SpigotProfile": {"SpigotDia": STEM_PLACES},
    "Spigot": {"SpigotLength": STEM_LENGTH_PLACES},
    "PivotProfile": {"PivotDia": STEM_PLACES},
    "Pivot": {"PivotLength": STEM_LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION) != set(DRAWING_DIMENSIONS) or any(
    set(DRAWING_PRECISION[feature]) != DRAWING_DIMENSIONS[feature]
    for feature in DRAWING_DIMENSIONS
):
    raise AssertionError("every printed dimension needs its places, and only those")
# The spigot-end-to-pivot-end overall prints as a reference at .XX: the sum
# of the three toleranced lengths, for the stock.
DRAWING_REFERENCE_PRECISION = STEM_LENGTH_PLACES


def inch_text(value_mm: float, places: int) -> str:
    """Decimal-inch print text, the family's form (``.0625``, ``1.23``)."""
    return family.inch_text(value_mm, places)


def inch_range(limits_mm: tuple[float, float], places: int = 4) -> str:
    """A REF fit range on the inch grid, rounded outward: ``.0002-.0010``."""
    low = family.inch_grid_mm(limits_mm[0], places, math.floor)
    high = family.inch_grid_mm(limits_mm[1], places, math.ceil)
    return f"{inch_text(low, places)}-{inch_text(high, places)}"
