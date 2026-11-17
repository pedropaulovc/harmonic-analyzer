"""Author the magnifier's named exploded presentation (MG_MAGNIFIER_EXPLODED).

``_explode_steps.author_explode_steps`` authors and proves each step of
``mg_magnifier_explode_spec.plan_explode`` along a global axis; the lever wire
and the second clamp screw (a native pattern follower) must read unmoved. The
measured aggregate world translations are stored as file-level custom
properties during this builder-owned preparation: the drawing need not
activate a configuration or show an explode on the released source to project
its associative balloons. The exploded sheets use the thread-free Default
Simplified copy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _explode_steps
from _com import _early_bound
from _component_references import component_reference_names
from _custom_properties import apply_custom_properties
from _explode_steps import Step
from mg_magnifier_explode_spec import (
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    encode_explode_offsets,
    explode_offsets_property,
    plan_explode,
)
from sh_vn_music_wire_lever_geom import CONFIGURATION as LEVER_WIRE_CONFIGURATION


def create_mg_magnifier_explode(adapter: Any, configuration_name: str) -> None:
    """Author the released presentation in the active ``configuration_name``
    (Default or Default Simplified), restore the working model and publish the
    verified offsets."""
    instances: list[Instance] = []

    def plan(model: Any, components: Any, _baseline: Any) -> list[Step]:
        component_reference_names(
            model, {"@LeverWire:1": ("sh-vn-music-wire", LEVER_WIRE_CONFIGURATION)}
        )
        instances.extend(
            Instance(
                name=name, stem=Path(str(component.GetPathName() or "")).stem.casefold()
            )
            for name, component in components
        )
        return [
            Step(step.label, tuple(names), step.axis, step.distance_mm)
            for step, names in plan_explode(instances)
        ]

    offsets = _explode_steps.author_explode_steps(
        adapter,
        configuration_name,
        view=EXPLODED_VIEW_NAME,
        source=SOURCE_CONFIGURATION,
        step_prefix="MG",
        plan=plan,
    )
    apply_custom_properties(
        adapter,
        {
            explode_offsets_property(configuration_name): encode_explode_offsets(
                configuration_name, offsets, instances
            )
        },
        model=_early_bound(adapter.currentModel, "IModelDoc2"),
    )
