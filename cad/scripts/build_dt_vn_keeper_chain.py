r"""Purchased keeper chain: McMaster-Carr 3603T354 #18 brass jack chain (MHA-DT-VN-65).

The chain tying the crank's removable taper pin to the arm (ch11 p.14; the
original is lost), cut to ``dt_vn_keeper_chain_spec.LINK_COUNT`` links and
modelled in its installed rest pose. It is authored in machine axes with its
origin on the end link's centre (``dt_vn_keeper_chain_spec.CHAIN_PART_ORIGIN``),
and the drive train places it there with an identity rotation.

Recipe:

1. ``CatalogueReference``, a blanked Right-plane sketch: one circle at the
   origin, the end link's neck section, whose diameter carries the catalogue
   wire size the purchased-part sheet imports.
2. For every link (D1), three circular-profile sweeps of the wire along 3D
   cubic-Bezier paths (``_pivot_retention_stock_geometry.circular_sweep``):
   ``LinkNNNear`` and ``LinkNNFar``, the two eyes (closed four-quarter-arc
   circles, square to each other), and ``LinkNNNeck``, the straight neck
   between them along the link axis. Each sweep is its own body: the part is
   one multibody of 3 x LINK_COUNT bodies, each link's three meeting where the
   neck runs into the eyes' wire.

Feature, curve-driven and sketch-driven patterns only translate, and every
link here has its own orientation, so each is swept in place.

The body count, the volume (the bodies' sum: two tori and a cylinder per
link) and the centre of mass (each link is symmetric about its centre, so the
mean of the link centres) are proved against the spec's analytic values.

Run with SolidWorks open::

    uv run python cad\scripts\build_dt_vn_keeper_chain.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _dimensions import name_dimensions
from _drawing_marks import apply_drawing_properties, mark_dimensions_for_drawing
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _pivot_retention_stock_geometry import circular_sweep, line_bezier
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import blank_reference_sketches, ensure_fully_defined
from _sketch_circle import define_circle
from dt_vn_keeper_chain_spec import (
    CATALOGUE_REFERENCE,
    CATALOGUE_WIRE_DIMENSION,
    CHAIN_DRAWING_NOTES,
    CHAIN_PART_LINKS,
    DRAWING_DIMENSIONS,
    EYE_CENTRE_SPACING,
    EYE_MEAN_R,
    LINK_COUNT,
    NECK_LEN,
    WIRE_DIA,
    WIRE_R,
)

PART_NAME = "dt-vn-keeper-chain"
MATERIAL = "Brass"
_PART = _config.parts(PART_NAME)
STOCK_PROPERTIES = {
    "Stock Name": str(_PART["stock_name"]),
    "Supplier": str(_PART["supplier"]),
    "Supplier SKUs": ", ".join(str(sku) for sku in _PART["supplier_skus"]),
}

# Pappus: the wire's section swept round the eye's mean circle, and along
# the neck.
V_EYE = 2.0 * math.pi**2 * EYE_MEAN_R * WIRE_R**2
V_NECK = math.pi * WIRE_R**2 * NECK_LEN
V_LINK = 2.0 * V_EYE + V_NECK
V_CHAIN = LINK_COUNT * V_LINK
BODY_COUNT = 3 * LINK_COUNT
# A quarter circle's cubic-Bezier handle, as a fraction of the radius (its
# radial error is under 0.03 %).
_KAPPA = 4.0 / 3.0 * math.tan(math.pi / 8.0)


def _com_expected() -> tuple[float, float, float]:
    """Centre of mass of the bodies: every link has the same volume and is
    symmetric about its centre, so it is the mean link centre."""
    return tuple(
        sum(link.centre[k] for link in CHAIN_PART_LINKS) / LINK_COUNT for k in range(3)
    )


def _add(*vectors):
    return tuple(sum(values) for values in zip(*vectors))


def _scale(v, s):
    return tuple(value * s for value in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _eye_segments(centre, normal, axis):
    """Four cubic-Bezier quarter arcs closing the eye's wire centreline: radius
    EYE_MEAN_R about ``centre``, in the plane of ``axis`` and normal x axis."""
    side = _cross(normal, axis)

    def point(k):
        a = k * math.pi / 2.0
        return _add(centre, _scale(axis, EYE_MEAN_R * math.cos(a)), _scale(side, EYE_MEAN_R * math.sin(a)))

    def tangent(k):
        a = k * math.pi / 2.0
        return _add(_scale(axis, -math.sin(a)), _scale(side, math.cos(a)))

    handle = _KAPPA * EYE_MEAN_R
    return [
        (
            point(k),
            _add(point(k), _scale(tangent(k), handle)),
            _add(point(k + 1), _scale(tangent(k + 1), -handle)),
            point(k + 1),
        )
        for k in range(4)
    ]


def _body_count(adapter) -> int:
    return len(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, True) or ())


async def _catalogue_reference(adapter) -> None:
    """The neck's section at the origin, carrying the catalogue wire size."""
    check(f"create_sketch {CATALOGUE_REFERENCE}", await adapter.create_sketch("Right"))
    await define_circle(adapter, 0.0, 0.0, WIRE_R, "catalogue wire")
    await ensure_fully_defined(adapter, CATALOGUE_REFERENCE)
    check(f"exit_sketch {CATALOGUE_REFERENCE}", await adapter.exit_sketch())
    name_last_feature(adapter, CATALOGUE_REFERENCE)
    name_dimensions(adapter, CATALOGUE_REFERENCE, [CATALOGUE_WIRE_DIMENSION])
    mark_dimensions_for_drawing(
        adapter, CATALOGUE_REFERENCE, DRAWING_DIMENSIONS[CATALOGUE_REFERENCE]
    )


def _sweep_link(adapter, index: int, link) -> None:
    half = EYE_CENTRE_SPACING / 2.0
    near = _add(link.centre, _scale(link.axis, -half))
    far = _add(link.centre, _scale(link.axis, half))
    neck = NECK_LEN / 2.0
    label = f"Link{index:02d}"
    with _telemetry.span("feature.keeper_link", label=label):
        circular_sweep(adapter, _eye_segments(near, link.near_normal, link.axis), WIRE_DIA, f"{label}Near")
        circular_sweep(adapter, _eye_segments(far, link.far_normal, link.axis), WIRE_DIA, f"{label}Far")
        circular_sweep(
            adapter,
            [
                line_bezier(
                    _add(link.centre, _scale(link.axis, -neck)),
                    _add(link.centre, _scale(link.axis, neck)),
                )
            ],
            WIRE_DIA,
            f"{label}Neck",
        )
    if _body_count(adapter) != 3 * (index + 1):
        raise RuntimeError(
            f"{label}: {_body_count(adapter)} bodies after its sweeps, expected {3 * (index + 1)}"
        )


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await _catalogue_reference(adapter)
    for index, link in enumerate(CHAIN_PART_LINKS):
        _sweep_link(adapter, index, link)
    await force_rebuild(adapter)
    if _body_count(adapter) != BODY_COUNT:
        raise RuntimeError(f"keeper chain has {_body_count(adapter)} bodies, expected {BODY_COUNT}")
    await volume_check(adapter, "keeper chain", V_CHAIN, 0.005 * V_CHAIN)
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"keeper chain: get_mass_properties failed: {mass.error}")
    got = [float(c) for c in mass.data.center_of_mass]
    want = _com_expected()
    # A misplaced link moves the centre of mass by ~1/LINK_COUNT of its error;
    # 0.02 mm sits far above the Bezier circles' noise.
    if max(abs(g - w) for g, w in zip(got, want)) > 0.02:
        raise RuntimeError(f"keeper chain centre of mass {got} != analytic {want}")
    _telemetry.success(f"keeper chain: centre of mass {got} matches {want}")
    blank_reference_sketches(adapter, (CATALOGUE_REFERENCE,))
    await apply_material(adapter, MATERIAL)
    apply_custom_properties(adapter, STOCK_PROPERTIES)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": CHAIN_DRAWING_NOTES})
    await report_mass_properties(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
