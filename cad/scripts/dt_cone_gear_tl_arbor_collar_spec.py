r"""Pure-data contract for the keyed arbor's backing collars (MHA-DT-03-TL-04).

Shop tooling (issue #2465). One collar stands between each keyed blank and
the 1/4-28 arbor nut on MHA-DT-03-TL-03's pilot, the largest that clears that
blank's root circle (``dt_cone_gear_tl_keyed_arbor_spec.COLLAR_BY_GEAR``): the
nut's 7/16 face alone does not cover a Ø.376 bore's annulus. One native model,
three named members by outside diameter, each its own disc (feature
suppression, ``_purchased_part_variants``): C050 for T030..T048, C100 for
T054..T084, C175 for T090..T120 and the 64T. Each is round bar left at stock
diameter, faced to length and drilled through with an L drill.

Frame: axis +Z; the face on the blank at z = 0 (the Front Plane), the face
under the nut at z = LENGTH.
"""

from __future__ import annotations

import math

import _config
import dt_cone_gear_tl_keyed_arbor_spec as arbor
from _package_units import drawing_unit

PART_NAME = "dt-cone-gear-tl-arbor-collar"
_ROW = _config.parts("dt-cone-gear-tl-arbor-collar")
if PART_NAME != "dt-cone-gear-tl-arbor-collar":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/dt-cone-gear-tl-arbor-collar", _ROW)
INCH = arbor.INCH

CONFIGURATIONS = ("C175", "C100", "C050")
if (
    _ROW.get("default_configuration") != CONFIGURATIONS[0]
    or tuple(_ROW.get("configuration_quantities", {})) != CONFIGURATIONS
):
    raise AssertionError("the registry's collar members differ from the spec's order")
OD_BY_CONFIGURATION: dict[str, float] = {
    "C050": arbor.COLLAR_DIAS[0],
    "C100": arbor.COLLAR_DIAS[1],
    "C175": arbor.COLLAR_DIAS[2],
}
for _name, _od in OD_BY_CONFIGURATION.items():
    if _name != f"C{round(_od / INCH * 100):03d}":
        raise AssertionError(f"member {_name} is not named for its {_od} mm diameter")
LENGTH = arbor.COLLAR_LENGTH
BORE = arbor.COLLAR_BORE
# Each outside diameter is round bar left at stock (1/2, 1, 1-3/4).

GEARS_BY_CONFIGURATION: dict[str, tuple[str, ...]] = {
    name: tuple(
        tag
        for tag, index in arbor.COLLAR_BY_GEAR.items()
        if arbor.COLLAR_DIAS[index] == od
    )
    for name, od in OD_BY_CONFIGURATION.items()
}
if sorted(t for tags in GEARS_BY_CONFIGURATION.values() for t in tags) != sorted(
    arbor.COLLAR_BY_GEAR
):
    raise AssertionError("every keyed blank takes exactly one collar")


def disc_feature(configuration: str) -> str:
    return f"Disc{configuration}"


def disc_sketch(configuration: str) -> str:
    return f"Disc{configuration}Profile"


def od_name(configuration: str) -> str:
    return f"OD{configuration}"


def bore_name(configuration: str) -> str:
    return f"Bore{configuration}"


def length_name(configuration: str) -> str:
    return f"Length{configuration}"


# Each member owns only its own disc; no feature is shared.
CONFIGURATION_FEATURES: dict[str, tuple[str, ...]] = {
    name: (disc_feature(name),) for name in CONFIGURATIONS
}
CONFIGURATION_DESCRIPTIONS: dict[str, str] = {
    name: f"COLLAR Ø{OD_BY_CONFIGURATION[name] / INCH:.2f}".replace("Ø0.", "Ø.")
    for name in CONFIGURATIONS
}
V_BY_CONFIGURATION: dict[str, float] = {
    name: math.pi / 4.0 * (od**2 - BORE**2) * LENGTH
    for name, od in OD_BY_CONFIGURATION.items()
}

GLOBALS: dict[str, float] = {
    **{od_name(name): od for name, od in OD_BY_CONFIGURATION.items()},
    "CollarBore": BORE,
    "CollarLength": LENGTH,
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    **{disc_sketch(name): {od_name(name), bore_name(name)} for name in CONFIGURATIONS},
    **{disc_feature(name): {length_name(name)} for name in CONFIGURATIONS},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    **{
        disc_sketch(name): {od_name(name): 2, bore_name(name): 3}
        for name in CONFIGURATIONS
    },
    **{disc_feature(name): {length_name(name): 2} for name in CONFIGURATIONS},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
for _feature, _names in DRAWING_DIMENSIONS.items():
    if set(DRAWING_PRECISION[_feature]) != _names:
        raise AssertionError(
            f"{_feature}: every marked dimension needs authored places"
        )
for _value, _places in (
    *((od, 2) for od in OD_BY_CONFIGURATION.values()),
    (BORE, 3),
    (LENGTH, 2),
):
    if abs(arbor.inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_value} mm is off its printed grid")

# Sheet words: the bore is a plain drilled hole (the title block's DRILLED
# HOLES row), through. One Number, three members (the base bar's form, no
# new part numbers): each member's sheet names its member as the kit's parts
# list calls it up (its Description of the one Number) with its quantity,
# then the gears it backs, each by its own drawing number (rule 4).
BORE_CALLOUT = "THRU"
STOCK_CALLOUT = "STOCK OK"
SHEET_NAMES: tuple[str, ...] = tuple(f"COLLAR {name}" for name in CONFIGURATIONS)
QUANTITY_BY_CONFIGURATION: dict[str, int] = {
    name: int(quantity) for name, quantity in _ROW["configuration_quantities"].items()
}
_GEAR_NUMBERS = {blank.tag: blank.number for blank in arbor.KEYED_GEARS}
# The arbor shares this part's MHA-DT-03 parent: its short form (rule 4).
ARBOR_SHORT = arbor.PART_NUMBER.removeprefix(
    PART_NUMBER[: PART_NUMBER.index("-TL-") + 1]
)
if ARBOR_SHORT == arbor.PART_NUMBER or not ARBOR_SHORT.startswith("TL-"):
    raise AssertionError("the arbor no longer shares the collar's parent number")


def member_label(configuration: str) -> str:
    """The member this sheet draws, as the kit's parts list names it."""
    return (
        f"{CONFIGURATION_DESCRIPTIONS[configuration]} OF {PART_NUMBER}, "
        f"QTY {QUANTITY_BY_CONFIGURATION[configuration]}"
    )


def member_note(configuration: str) -> str:
    """The member's label over its one note: which blanks it backs."""
    tags = GEARS_BY_CONFIGURATION[configuration]
    cones = [_GEAR_NUMBERS[t] for t in tags if t.startswith("T")]
    crank = [_GEAR_NUMBERS[t] for t in tags if not t.startswith("T")]
    backed = f"{cones[0]} TO {cones[-1]}" if len(cones) > 1 else cones[0]
    if crank:
        backed += f" AND {crank[0]}"
    return f"{member_label(configuration)}\n1. BACKS {backed} ON {ARBOR_SHORT}."


ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
