"""Author the drive-train's named exploded presentation (DRIVE_TRAIN_EXPLODED).

``_explode.author_explode_steps`` authors and proves each step of
``dt_drive_train_assembly_spec.plan_explode`` along a global axis or along the
cone axis (the stationary post's journal); the saved operational pose (the
free kinematic model) is proven unchanged after collapse. The small exploded
views reference the teeth/thread-free Default Simplified copy.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import _explode
import _telemetry
from _com import _early_bound
from _component_references import component_reference_names
from _explode import Direction, Step, Transform
from cone_line import COS_I, SIN_I
from dt_drive_train_assembly_spec import (
    COMPONENT_IDENTITIES,
    CONE_AXIS_SOURCE,
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    Role,
    plan_explode,
)

# On the seat the post's journal reads on the layout's exact axis: deviation
# 5.3e-16 in farm run 20260929T174651337Z.  A wrong axis is degrees off.  The
# readback moves along the MEASURED axis, the one the rotor is mated to, so
# this bound only has to tell the journal from anything else.
_CONE_AXIS_TOLERANCE = 1e-5


def _cone_direction(
    adapter: Any,
    instances: Sequence[Instance],
    by_name: Mapping[str, Any],
    baseline: Mapping[str, Transform],
) -> Direction:
    """The post journal's axis in world space, positive toward the cone tip.

    Read off the part and carried through the post's saved transform: the
    rotor is mated to this axis, so it is the line the rotor withdraws along.
    """
    from solidworks_mcp.adapters.solidworks.assembly import _qualify_entity_name

    stem, feature_name = CONE_AXIS_SOURCE
    owners = [instance.name for instance in instances if instance.stem == stem]
    if len(owners) != 1:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: cone axis needs one {stem}, found {owners!r}"
        )
    owner = owners[0]
    part = _early_bound(by_name[owner].GetModelDoc2(), "IPartDoc")
    if part is None:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: {owner} has no resolved part document"
        )
    label = f"{feature_name}@{owner}"
    local = _explode.axis_vector(
        _early_bound(part.FeatureByName(feature_name), "IFeature"), label
    )
    rows = baseline[owner]
    world = tuple(
        local[0] * rows[i] + local[1] * rows[3 + i] + local[2] * rows[6 + i]
        for i in range(3)
    )
    length = math.sqrt(sum(value * value for value in world))
    layout = (SIN_I, 0.0, COS_I)
    positive = sum(world[i] * layout[i] for i in range(3)) > 0.0
    sense = 1.0 if positive else -1.0
    unit = (
        sense * world[0] / length,
        sense * world[1] / length,
        sense * world[2] / length,
    )
    deviation = max(abs(unit[i] - layout[i]) for i in range(3))
    _telemetry.event(
        "assembly.drive_train_explode.cone_axis",
        axis=label,
        unit=unit,
        positive=positive,
        deviation=deviation,
    )
    if deviation > _CONE_AXIS_TOLERANCE:
        raise RuntimeError(
            f"{label}: world direction {unit!r} is not the cone axis {layout!r} "
            f"(deviation {deviation:.3g})"
        )
    return Direction(_qualify_entity_name(adapter, label), positive, unit)


def create_drive_train_explode(
    adapter: Any, roles: Mapping[str, Role], configuration_name: str
) -> None:
    """Author the released presentation in the active ``configuration_name``
    (Default or Default Simplified) and restore the free working model.

    ``roles`` maps returned native component names to their insertion roles.
    The two same-stock screw roles are also read back from persisted native
    references, proving the map against file/configuration associations.
    """

    def plan(
        model: Any, components: Any, baseline: Mapping[str, Transform]
    ) -> list[Step]:
        by_name = dict(components)
        unknown_roles = sorted(set(roles) - set(by_name))
        if unknown_roles:
            raise ValueError(f"roles name absent components {unknown_roles!r}")
        reference_names = component_reference_names(model, COMPONENT_IDENTITIES)
        for selector, name in reference_names.items():
            if roles.get(name) != selector[1:]:
                raise ValueError(f"{selector!r} disagrees with insertion role map")
        instances = [
            Instance(
                name=name,
                stem=Path(str(component.GetPathName() or "")).stem.casefold(),
                origin_mm=tuple(value * 1000.0 for value in baseline[name][9:12]),
                role=roles.get(name),
            )
            for name, component in components
        ]
        steps = plan_explode(instances)
        cone = _cone_direction(adapter, instances, by_name, baseline)
        return [
            Step(
                step.label,
                tuple(names),
                cone if step.axis == "cone" else step.axis,
                step.distance_mm,
            )
            for step, names in steps
        ]

    _explode.author_explode_steps(
        adapter,
        configuration_name,
        view=EXPLODED_VIEW_NAME,
        source=SOURCE_CONFIGURATION,
        step_prefix="DRIVE TRAIN",
        plan=plan,
    )
