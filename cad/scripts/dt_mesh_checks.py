"""Standard closed-form checks for the drum meshes (cone family and alignment).

Every value comes from the part specs and config:

* cone T006..T120 against the 120T drum: cone_line places each cone's pitch
  section ``edge_slack_mm`` clear of the drum's pitch circle at mid-face, so
  the nominal centre is the standard (N + 120) * m / 2 plus that slack, and
  ``centre_opening_mm`` is the total booked opening (runout and bearings);
* the 32T alignment pinion against the drum at its configured engaged centre
  plus/minus its configured radial stack.

The crossed 16T:64T crank check lives with its stack in crank_mesh_stack.
"""
from __future__ import annotations

import functools

import _config
import dt_alignment_pinion_spec as alignment
import dt_cone_gear_spec as cone
import dt_cylinder_gear_spec as drum
from standard_mesh_checks import MeshCheck, check_mesh, plane_gear

EDGE_SLACK_MM = float(_config.fit("cone_drum_oblique_mesh", "edge_slack_mm"))
CENTRE_OPENING_MM = float(_config.fit("cone_drum_oblique_mesh", "centre_opening_mm"))


@functools.cache
def _drum_corners():
    return tuple(plane_gear(p, drum.MODULE_MM) for p in drum.manufacturing_corner_profiles())


def cone_centre_range_mm(teeth: int) -> tuple[float, float]:
    nominal = (teeth + drum.TEETH) * cone.MODULE_MM / 2.0 + EDGE_SLACK_MM
    return nominal, nominal + CENTRE_OPENING_MM


@functools.cache
def cone_check(teeth: int) -> MeshCheck:
    centre = cone_centre_range_mm(teeth)
    return check_mesh(
        f"cone T{teeth:03d}/drum",
        (plane_gear(cone.stock_form_profile(teeth), cone.MODULE_MM),
         plane_gear(drum.STOCK_FORM, drum.MODULE_MM), centre[0]),
        [plane_gear(p, cone.MODULE_MM) for p in cone.manufacturing_corner_profiles(teeth)],
        _drum_corners(),
        centre,
        cone.PRESSURE_ANGLE_DEG,
        cone.MODULE_MM,
    )


@functools.cache
def alignment_check() -> MeshCheck:
    nominal = alignment.ENGAGED_CENTER_DISTANCE_MM
    stack = alignment.ENGAGED_CENTER_RADIAL_STACK_MM
    return check_mesh(
        "alignment 32T/drum",
        (plane_gear(alignment.STOCK_FORM, alignment.MODULE_MM),
         plane_gear(drum.STOCK_FORM, drum.MODULE_MM), nominal),
        [plane_gear(p, alignment.MODULE_MM) for p in alignment.manufacturing_corner_profiles()],
        _drum_corners(),
        (nominal - stack, nominal + stack),
        alignment.PRESSURE_ANGLE_DEG,
        alignment.MODULE_MM,
    )


def cone_checks() -> tuple[MeshCheck, ...]:
    return tuple(cone_check(teeth) for teeth in cone.CONFIGURATION_TEETH)
