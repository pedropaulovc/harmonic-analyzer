"""MHA-VN-071 crank seat shim pack: McMaster 3088A carbon-steel ring shims.

PURE DATA, no SolidWorks/COM imports, and nothing from the drive train: the
part's cache key is the catalogue and the modelled pack only.  The gap the
pack fills, and the proof that this rule covers it, live in
``dt_crank_seat_gap``.

Purchased 12 mm ID x 18 mm OD shims (``_mcmaster_3088a_12x18``) in six
thicknesses, 0.1/0.2/0.5/1/1.5/2.  The fitter measures the gap between the
MHA-DT-011 collar's rear face and the MHA-DT-005 crank boss's south face and
stacks at most STACK_MAX of them to within FIT_RESIDUAL_MAX under it
(MHA-DT-000 continuation sheet).  STACK_MAX is the catalogue's own limit:
more than four may shift.

The model is the pack selected for the nominal gap, ``PACK``: one solid body
per shim, thickest on the collar.

Part frame: axis +Y (``ScrewAxis``, Front Plane x Right Plane); Top Plane is
the pack's collar face, y = THICKNESS its boss face.
"""

from __future__ import annotations

import math
from itertools import combinations_with_replacement

from _mcmaster_3088a_12x18 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_MATERIAL as CATALOG_MATERIAL,
    CATALOG_MATERIAL_NOTE as CATALOG_MATERIAL_NOTE,
    CATALOG_STACK_MAX,
    FAMILY_TABLE_URL as FAMILY_TABLE_URL,
    LIVE_ROW_URL as LIVE_ROW_URL,
    SHIMS,
    SKUS as SKUS,
    THICKNESS_NOMINAL,
)

COUNT = 1  # one pack; its shim count is selected at assembly
STACK_MAX = CATALOG_STACK_MAX
# The pack is never thicker than the gap and at most this much thinner.
FIT_RESIDUAL_MAX = 0.10

ID = SHIMS[SKUS[0]].id
OD = SHIMS[SKUS[0]].od
ID_MIN = SHIMS[SKUS[0]].id_min
ID_MAX = SHIMS[SKUS[0]].id_max
OD_MIN = SHIMS[SKUS[0]].od_min
OD_MAX = SHIMS[SKUS[0]].od_max
if any(
    (dims.id, dims.od, dims.id_min, dims.id_max, dims.od_min, dims.od_max)
    != (ID, OD, ID_MIN, ID_MAX, OD_MIN, OD_MAX)
    for dims in SHIMS.values()
):
    raise AssertionError("the 3088A pack rows do not share one ID/OD band")

# Every catalogue thickness is a whole number of tenths, so packs are
# compared exactly in tenths.
_TENTHS = {sku: round(thickness * 10) for sku, thickness in THICKNESS_NOMINAL.items()}
if any(abs(_TENTHS[sku] - 10 * THICKNESS_NOMINAL[sku]) > 1e-9 for sku in SKUS):
    raise AssertionError("a 3088A thickness is not a whole number of tenths")
_THICK_FIRST = tuple(sorted(SKUS, key=lambda sku: -_TENTHS[sku]))


def _preferred_packs() -> dict[int, tuple[str, ...]]:
    """Each reachable pack thickness (tenths) and the pack that makes it:
    the fewest shims, then the thickest ones, listed thickest first."""
    packs: dict[int, tuple[str, ...]] = {}
    for count in range(1, STACK_MAX + 1):
        # combinations_with_replacement keeps _THICK_FIRST order inside each
        # pack, and yields a count's packs thickest-first, so the first pack
        # found for a total is the preferred one.
        for pack in combinations_with_replacement(_THICK_FIRST, count):
            packs.setdefault(sum(_TENTHS[sku] for sku in pack), pack)
    return dict(sorted(packs.items()))


PACKS = _preferred_packs()


def pack_thickness(pack: tuple[str, ...]) -> float:
    """Nominal stacked thickness of ``pack``, mm."""
    return sum(_TENTHS[sku] for sku in pack) / 10.0


def pack_for(gap: float) -> tuple[str, ...]:
    """The thickest pack of at most STACK_MAX shims not thicker than ``gap``;
    empty when even the thinnest shim does not fit."""
    fits = [total for total in PACKS if total <= math.floor(gap * 10 + 1e-9)]
    return PACKS[fits[-1]] if fits else ()


def worst_residual(gap_min: float, gap_max: float) -> float:
    """Supremum over gaps in [gap_min, gap_max] of gap - pack_for(gap).

    Between two consecutive reachable totals the residual grows to (but never
    reaches) their difference, so the worst case is the widest step between
    the pack chosen at gap_min and gap_max, or gap_max's own residual."""
    first = pack_for(gap_min)
    if not first:
        return math.inf
    totals = [pack_thickness(first)] + [
        total / 10.0
        for total in PACKS
        if gap_min + 1e-9 < total / 10.0 <= gap_max + 1e-9
    ]
    steps = [high - low for low, high in zip(totals, totals[1:])]
    return max([gap_max - totals[-1], *steps])


def check_coverage(gap_min: float, gap_max: float) -> None:
    """Refuse a gap range some pack of at most STACK_MAX shims cannot fill
    to within FIT_RESIDUAL_MAX."""
    worst = worst_residual(gap_min, gap_max)
    if worst > FIT_RESIDUAL_MAX + 1e-9:
        raise AssertionError(
            f"MHA-VN-071 packs of at most {STACK_MAX} shims leave up to "
            f"{worst:.3f} over {gap_min:.3f}-{gap_max:.3f}, above the "
            f"{FIT_RESIDUAL_MAX} fit residual"
        )


# The modelled pack, for the nominal crank-seat gap (2.833 at print nominals;
# dt_crank_seat_gap refuses a nominal this pack no longer fills), stacked
# from the collar face: 2 + 0.5 + 0.2 + 0.1.
PACK: tuple[str, ...] = ("3088A207", "3088A066", "3088A026", "3088A006")
if PACK != PACKS[sum(_TENTHS[sku] for sku in PACK)]:
    raise AssertionError(f"MHA-VN-071 model pack {PACK} is not the preferred pack")
# The stock build names each shim's features by its SKU.
if len(set(PACK)) != len(PACK):
    raise AssertionError("MHA-VN-071 model pack repeats a SKU")
THICKNESS = pack_thickness(PACK)
# Each shim's collar-side face, from the pack's collar face.
LAYER_Y: tuple[float, ...] = tuple(
    pack_thickness(PACK[:index]) for index in range(len(PACK))
)
BOTTOM_Y = 0.0
TOP_Y = THICKNESS


def shim_volume(sku: str) -> float:
    """Nominal annulus volume of one shim, mm^3."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS_NOMINAL[sku]


def pack_volume() -> float:
    """Nominal volume of the modelled pack, mm^3."""
    return sum(shim_volume(sku) for sku in PACK)
