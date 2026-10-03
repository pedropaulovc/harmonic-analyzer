r"""Shared recipe for the McMaster 98381A* alloy-steel dowel pins.

Catalogue: each size's own McMaster product page, read live 2026-09-30 in a
headless browser (dt-logs transgear-evidence/mcmaster-skus.md R6): alloy
steel, unplated, diameter +0.0001 to +0.0003 in over nominal, end shape
"Round x Chamfer".  The pages state neither the end radius nor the chamfer.

98381A433 and 98381A434 have no vendor .SLDPRT, so the recipe models them as
the plain nominal cylinder (the ``diag_build_98296A027`` convention for
unstated end forms) rather than inventing either end, and their standalone
runs (``diag_build_98381A43*.py``) are catalog-only: they build the recipe,
check the solid and save it under cad/out/reference.

98381A473 (1/8 x 3/4) has a user-supplied vendor model
(``cad/references/mcmaster/98381A473.SLDPRT``, harvested 2026-09-30 on amet
into ``cad/out/reports/mcmaster-98381A473-dump.json``), so its end forms are
the model's (``DOWEL_ENDS``) and its standalone run is the replica gate.  The
harvest is one Revolve1 of five faces: a flat Ø0.115 end face and a cone at
16 deg to the axis at one end (the chamfer), the Ø0.125 cylinder, and a
0.016 radius tangent to the cylinder down to a flat Ø0.093 end face at the
other (the round end).  Its diameter band is the family's, read on the
98381A433/434/489 pages; the model is drawn at nominal.

98381A474 (1/8 x 7/8, the MHA-VN-042 latch pin since R9-50) is [INFERENCE]: the
7/8 in length of the 1/8 series (98381A467 1/8 in through 98381A479
1-3/4 in, dt-logs mcmaster-skus.md "Round 6 - additions"; a reseller lists
98381A474 as 1/8 x 7/8,
https://www.kvmtools.com/products/mcmaster-98381a474-dowel-pin-pack-of-50-alloy-steel-1-8-diameter-7-8-long),
not yet read live and with no vendor model.  It carries the 98381A473
harvest's end forms [INFERENCE: same diameter and end shape in the series],
and its standalone run is catalog-only until a vendor check replaces both.

Frame: the pin section revolved about model Y, the pressed (chamfered) end
face at y = 0 and the rounded lead end at y = length.  The vendor revolves
about its X axis centred on the origin, chamfer at -x.

The size table is pure data: module import pulls in no SolidWorks helper,
so the pin specs read it.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MM_PER_IN = 25.4

DOWEL_SIZES = {
    # part:        (nominal dia, length), mm
    "98381A433": (3.0 / 32.0 * MM_PER_IN, 3.0 / 16.0 * MM_PER_IN),  # 3/32 x 3/16
    "98381A434": (3.0 / 32.0 * MM_PER_IN, 0.25 * MM_PER_IN),  # 3/32 x 1/4
    "98381A473": (0.125 * MM_PER_IN, 0.75 * MM_PER_IN),  # 1/8 x 3/4
    "98381A474": (0.125 * MM_PER_IN, 0.875 * MM_PER_IN),  # 1/8 x 7/8 [INFERENCE]
}
# Catalogue diameter tolerance over nominal, in inches (every size above).
DIA_BAND_IN = (0.0001, 0.0003)


@dataclass(frozen=True)
class DowelEnds:
    """A vendor-modelled Round x Chamfer pair of end forms, mm and degrees."""

    point_dia: float  # the chamfered end's flat face
    chamfer_deg: float  # the chamfer cone's angle to the pin axis
    crown_r: float  # the round end's radius, tangent to the diameter

    def chamfer_len(self, dia: float) -> float:
        """Axial length of the chamfer cone on a pin of ``dia``."""
        return (dia - self.point_dia) / 2.0 / math.tan(math.radians(self.chamfer_deg))


# Read off the 98381A473 harvest (Sketch2 "Point Diameter" 2.921, D3 16 deg,
# "Crown Radius" 0.4064; Revolve1 faces: cone x -9.525..-9.0821, torus
# x 9.1186..9.525, end faces Ø2.921 and Ø2.3622).
_ROUND_X_CHAMFER_1_8 = DowelEnds(
    point_dia=0.115 * MM_PER_IN, chamfer_deg=16.0, crown_r=0.016 * MM_PER_IN
)
DOWEL_ENDS = {
    "98381A473": _ROUND_X_CHAMFER_1_8,
    # [INFERENCE] the 1/8 series' end forms, read off the 98381A473 harvest.
    "98381A474": _ROUND_X_CHAMFER_1_8,
}


def dowel_volume(part_no: str) -> float:
    """The recipe's solid volume, mm^3: the nominal cylinder less the chamfer
    ring and the round end's corner ring (Pappus, each about the pin axis)."""
    dia, length = DOWEL_SIZES[part_no]
    radius = dia / 2.0
    volume = math.pi * radius**2 * length
    ends = DOWEL_ENDS.get(part_no)
    if ends is None:
        return volume
    step = radius - ends.point_dia / 2.0
    chamfer_area = 0.5 * step * ends.chamfer_len(dia)
    volume -= 2.0 * math.pi * (radius - step / 3.0) * chamfer_area
    r = ends.crown_r
    corner_area = (1.0 - math.pi / 4.0) * r**2
    corner_centroid = radius - r + (r / 6.0) / (1.0 - math.pi / 4.0)
    volume -= 2.0 * math.pi * corner_centroid * corner_area
    return volume


def dowel_section(part_no: str) -> list[tuple[float, float]]:
    """The half-section's corners (radius, y), mm: from the round end's flat
    face rim round the axis and the chamfered end to the round end's tangent
    point.  The round end's arc closes it from the last point to the first."""
    dia, length = DOWEL_SIZES[part_no]
    radius = dia / 2.0
    ends = DOWEL_ENDS[part_no]
    r = ends.crown_r
    return [
        (radius - r, length),
        (0.0, length),
        (0.0, 0.0),
        (ends.point_dia / 2.0, 0.0),
        (radius, ends.chamfer_len(dia)),
        (radius, length - r),
    ]


def _dowel_com_map(part_no: str):
    """Vendor frame (axis X, centred, chamfer at -x) -> replica frame (axis
    Y, chamfered end face at y = 0)."""
    half = DOWEL_SIZES[part_no][1] / 2.0
    return lambda v: [v[1], v[0] + half, v[2]]


async def build_dowel(adapter, part_no: str) -> None:
    from _common import add_line_chain, check, name_last_feature, volume_check
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    dia, length = DOWEL_SIZES[part_no]
    radius = dia / 2.0
    ends = DOWEL_ENDS.get(part_no)
    check("create_sketch pin section", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk_mgr.CreateCenterLine(0.0, 0.0, 0.0, 0.0, length / 1000.0, 0.0) is None:
            raise RuntimeError(f"{part_no} pin section: CreateCenterLine failed")
        if ends is None:
            await add_line_chain(
                adapter,
                [(0.0, 0.0), (radius, 0.0), (radius, length), (0.0, length)],
            )
        else:
            prev_db = bool(sk_mgr.AddToDB)
            sk_mgr.AddToDB = True
            try:
                r = ends.crown_r
                # The round end: CCW from the cylinder's tangent point to the
                # rim of the flat end face.
                arc = sk_mgr.CreateArc(
                    (radius - r) / 1000.0,
                    (length - r) / 1000.0,
                    0.0,
                    radius / 1000.0,
                    (length - r) / 1000.0,
                    0.0,
                    (radius - r) / 1000.0,
                    length / 1000.0,
                    0.0,
                    1,
                )
                if arc is None:
                    raise RuntimeError(f"{part_no} pin section: round-end arc failed")
                await add_line_chain(adapter, dowel_section(part_no), close=False)
            finally:
                sk_mgr.AddToDB = prev_db
    check("exit_sketch pin section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    check(
        "revolve pin",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "PinBody")
    volume = dowel_volume(part_no)
    await volume_check(adapter, "dowel pin", volume, 0.005 * volume)
    if ends is not None:
        adapter._mcm_com_map = _dowel_com_map(part_no)


async def build_catalog(adapter, part_no: str) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
    from _common import check
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=part_no):
        check(f"create_part {part_no}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, part_no)
        await build_dowel(adapter, part_no)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{part_no} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{part_no}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{part_no}-catalog"))
        _telemetry.success(
            f"{part_no} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts
