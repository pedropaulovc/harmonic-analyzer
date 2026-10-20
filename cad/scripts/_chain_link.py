r"""Shared authoring for configured chain members and the connecting link.

A roller chain is alternating INNER links (2 inner plates + 2 bushings) and
OUTER links (2 outer plates + 2 pins). Both are an obround side-plate pair
spanning one LINK_PITCH (pin centres at local x=0 and x=P) plus two round
bodies at the pin stations; only the plate z, the plate hole, and the round
body (bored bushing vs solid pin) differ -- so one builder takes the deltas.

Each link is authored in its own frame: plates in the Front (XY) plane, the
pin axis along local Z. Two named reference axes -- Axis1 at the x=0 station,
Axis2 at the x=P station -- are the chain pattern's PathLink1/PathLink2 (their
spacing IS the pattern pitch). See _chain.py for the clearance rationale (all
gaps >= 0.25 mm; the links float as disconnected multibody solids).

InnerLink and OuterLink are configurations of one McMaster-Carr ANSI #25
chain part, cut to the loop's pitch count with an inner link at each end.
A separately purchased connecting link closes it (the OUTER-link stand-in;
its spring clip is not modelled). The two native purchase identities carry
their registry stock data and member-specific reference-sheet notes.
"""

from __future__ import annotations

import math
from typing import Any

import _config

import sh_vn_chain_link_spec as chain_spec
from _chain import LINK_COUNT, LINK_PITCH, PLATE_HALF_H, PLATE_THICK
from _appearance import BAR_STEEL, apply_color, apply_material
from _check import check
from _custom_properties import apply_custom_properties
from _drawing_marks import apply_drawing_properties
from _extrude import extrude_at_offset
from _feature_tree import feature_name_by_type
from _part_checks import report_mass_properties
from _part_save import save_part_and_images
from _saved_part_guard import require_saved_drawing_properties
from _sketch import ensure_fully_defined, set_sketch_direct_db
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry

import _telemetry

_ROWS = {
    "sh-vn-chain-link": _config.parts("sh-vn-chain-link"),
    "pd-vn-chain-connecting-link": _config.parts("pd-vn-chain-connecting-link"),
}
(CHAIN_SKU,) = _ROWS["sh-vn-chain-link"]["supplier_skus"]
(CONNECTING_LINK_SKU,) = _ROWS["pd-vn-chain-connecting-link"]["supplier_skus"]
# Inner links per loop; the cut chain holds one outer link fewer, and the
# connecting link closes the loop as the last outer link.
LINKS_PER_KIND = LINK_COUNT // 2
# The chain is sold by the foot; the loop is LINK_COUNT whole pitches of it.
CHAIN_ORDER_FEET = math.ceil(LINK_COUNT * LINK_PITCH / 304.8)
# One line each: the purchased sheet reserves ~0.21 m for the note. The
# connecting link's clip orientation is an assembly fact (MHA-PD-00 step).
DRAWING_NOTES = {
    chain_spec.INNER_LINK_CONFIGURATION: (
        f"BREAK {CHAIN_ORDER_FEET} FT OF {CHAIN_SKU} TO {LINKS_PER_KIND} INNER + "
        f"{LINKS_PER_KIND - 1} OUTER LINKS; {CONNECTING_LINK_SKU} CLOSES "
        f"{LINK_COUNT} PITCHES."
    ),
    chain_spec.OUTER_LINK_CONFIGURATION: (
        f"{LINKS_PER_KIND - 1} PER LOOP, ALL IN THE CUT {CHAIN_SKU} CHAIN."
    ),
    "pd-vn-chain-connecting-link": (
        f"1 PER LOOP: JOINS THE TWO INNER-LINK ENDS OF THE CUT {CHAIN_SKU}."
    ),
}
# Everything the purchased-part sheet reads from the saved part.
DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Stock Name",
    "Supplier",
    "Supplier SKUs",
    "Manufacturing Notes",
)


def stock_properties(part_name: str) -> dict[str, str]:
    """The registry's purchase identity, stamped for the reference sheet."""
    row = _ROWS[part_name]
    return {
        "Stock Name": str(row["stock_name"]),
        "Supplier": str(row["supplier"]),
        "Supplier SKUs": ", ".join(str(sku) for sku in row["supplier_skus"]),
    }


async def _sketch_plate(adapter: Any, hole_r: float) -> None:
    """Front-plane obround side-plate outline (one LINK_PITCH long) with a
    clearance hole at each pin station; fully defined, ready to extrude."""
    from _sketch import anchor_point_to_origin

    p, h = LINK_PITCH, PLATE_HALF_H
    check("create_sketch plate", await adapter.create_sketch("Front"))
    # ALL geometry under direct-db (suppress inference snapping at the
    # origin/axes), then constraints with it off.
    set_sketch_direct_db(adapter, True)
    # CCW obround: bottom line, right end-arc (+x bulge), top line, left
    # end-arc (-x bulge). Endpoints share exact coords so they merge.
    line_bot = check("plate bottom", await adapter.add_line(0.0, -h, p, -h))
    arc_right = check("plate right arc", await adapter.add_arc(p, 0.0, p, -h, p, h))
    line_top = check("plate top", await adapter.add_line(p, h, 0.0, h))
    arc_left = check("plate left arc", await adapter.add_arc(0.0, 0.0, 0.0, h, 0.0, -h))
    hole0 = check("plate hole 0", await adapter.add_circle(0.0, 0.0, hole_r))
    holep = check("plate hole P", await adapter.add_circle(p, 0.0, hole_r))
    set_sketch_direct_db(adapter, False)
    # Outline: both end-arc centres anchored, both radii, all 4 junction
    # tangents (the proven chain-loop recipe -- tangency makes the two lines
    # the circles' common external tangents, i.e. horizontal).
    await anchor_point_to_origin(adapter, f"{arc_left}.center", 0.0, 0.0, "left arc")
    await anchor_point_to_origin(adapter, f"{arc_right}.center", p, 0.0, "right arc")
    for label, arc in (("left", arc_left), ("right", arc_right)):
        check(
            f"plate {label} arc radius",
            await adapter.add_sketch_dimension(arc, None, "radial", h),
        )
    for label, e1, e2 in (
        ("bot-right", line_bot, arc_right),
        ("right-top", arc_right, line_top),
        ("top-left", line_top, arc_left),
        ("left-bot", arc_left, line_bot),
    ):
        check(
            f"plate tangent {label}",
            await adapter.add_sketch_constraint(e1, e2, "tangent"),
        )
    # Pin-station clearance holes (concentric with the end arcs).
    for label, circle, cx in (("0", hole0, 0.0), ("P", holep, p)):
        await anchor_point_to_origin(adapter, f"{circle}.center", cx, 0.0, f"hole {label}")
        check(
            f"plate hole {label} diameter",
            await adapter.add_sketch_dimension(circle, None, "diameter", 2.0 * hole_r),
        )
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())


async def _sketch_round_bodies(adapter: Any, outer_r: float, bore_r: float | None) -> None:
    """Front-plane circles at both pin stations -- a bored tube (bushing) when
    ``bore_r`` is given (nested circle = even-odd hole), else a solid disc."""
    p = LINK_PITCH
    check("create_sketch bodies", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for label, cx in (("0", 0.0), ("P", p)):
        await define_circle(adapter, cx, 0.0, outer_r, f"body outer {label}")
        if bore_r is not None:
            await define_circle(adapter, cx, 0.0, bore_r, f"body bore {label}")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "round bodies sketch")
    check("exit_sketch bodies", await adapter.exit_sketch())


async def author_link_references(adapter: Any) -> None:
    """The unchanged two pin-station axes shared by every member."""
    from solidworks_mcp.adapters.base import CreateAxisParameters, CreatePlaneParameters

    station_plane = check(
        "create_plane @ x=P",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=LINK_PITCH
            )
        ),
    )
    station_plane_name = getattr(station_plane, "name", station_plane)
    for label, second_plane in (("Axis1", "Right Plane"), ("Axis2", station_plane_name)):
        axis = check(
            f"create_axis {label}",
            await adapter.create_axis(
                CreateAxisParameters(mode="two_planes", planes=["Top Plane", second_plane])
            ),
        )
        if axis.name != label:
            raise RuntimeError(f"pin-station axis is {axis.name!r}, expected {label!r}")
    blank_reference_geometry(
        adapter,
        ((station_plane_name, "PLANE"), ("Axis1", "AXIS"), ("Axis2", "AXIS")),
    )


async def author_link_geometry(
    adapter: Any,
    *,
    plate_z: float,
    plate_hole_r: float,
    body_outer_r: float,
    body_bore_r: float | None,
    body_half_len: float,
) -> tuple[str, ...]:
    """Author the existing plate/bushing-or-pin shape in the active member.

    Return sketches before their owning bosses so member suppression can run
    in reverse dependency order. The physical geometry is the legacy recipe.
    """
    features: list[str] = []
    for sign in (1.0, -1.0):
        await _sketch_plate(adapter, plate_hole_r)
        features.append(feature_name_by_type(adapter, "ProfileFeature"))
        z_lo = sign * plate_z - PLATE_THICK / 2.0
        features.append(extrude_at_offset(adapter, PLATE_THICK, z_lo))
    await _sketch_round_bodies(adapter, body_outer_r, body_bore_r)
    features.append(feature_name_by_type(adapter, "ProfileFeature"))
    features.append(extrude_at_offset(adapter, 2.0 * body_half_len, -body_half_len))
    _gate_volume(
        await _volume(adapter), plate_hole_r, body_outer_r, body_bore_r, body_half_len
    )
    return tuple(features)


async def build_link(
    adapter: Any,
    *,
    part_name: str,
    material: str,
    plate_z: float,
    plate_hole_r: float,
    body_outer_r: float,
    body_bore_r: float | None,
    body_half_len: float,
) -> dict[str, str]:
    """Build the separately purchased connecting link with the same authoring."""
    check("create_part", await adapter.create_part())
    await author_link_references(adapter)
    await author_link_geometry(
        adapter,
        plate_z=plate_z,
        plate_hole_r=plate_hole_r,
        body_outer_r=body_outer_r,
        body_bore_r=body_bore_r,
        body_half_len=body_half_len,
    )
    await apply_material(adapter, material)
    await apply_color(adapter, BAR_STEEL)
    apply_custom_properties(adapter, stock_properties(part_name))
    apply_drawing_properties(
        adapter, part_name, {"Manufacturing Notes": DRAWING_NOTES[part_name]}
    )
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, part_name)
    require_saved_drawing_properties(adapter, DRAWING_PROPERTIES)
    return artefacts


async def _volume(adapter: Any) -> float:
    res = await adapter.get_mass_properties()
    volume = float(check("chain member mass properties", res).volume)
    if not math.isfinite(volume):
        raise RuntimeError(f"chain member volume is not finite: {volume!r}")
    return volume


def _gate_volume(
    vol: float,
    hole_r: float,
    outer_r: float,
    bore_r: float | None,
    half_len: float,
) -> None:
    h, p, t = PLATE_HALF_H, LINK_PITCH, PLATE_THICK
    plate_area = 2.0 * h * p + math.pi * h * h - 2.0 * math.pi * hole_r * hole_r
    plates = 2.0 * plate_area * t
    ring = math.pi * (outer_r * outer_r - (bore_r * bore_r if bore_r else 0.0))
    bodies = 2.0 * ring * (2.0 * half_len)
    expected = plates + bodies
    _telemetry.info(f"volume: {vol:.2f} mm^3 (analytic {expected:.2f})")
    if abs(vol - expected) > 0.02 * expected:
        raise RuntimeError(f"link volume {vol:.2f} != {expected:.2f}")


# The distinct connecting-link SKU retains the outer envelope without the clip.
CONNECTING_LINK = dict(chain_spec.OUTER_LINK)
