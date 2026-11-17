"""Author the channel's named exploded presentation (CHANNEL_EXPLODED).

``_explode_steps.author_explode_steps`` authors and proves each step of
``ch_channel_explode_spec.plan_explode`` along a global axis; the pressed pins
and the mated chain must read unmoved. The exploded sheet's view at 1:7
references the Default Simplified copy.
"""

from __future__ import annotations

from typing import Any

import _explode_steps
from _component_references import component_identity
from _explode_steps import Step
from ch_channel_explode_spec import (
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    member_family,
    plan_explode,
)


def _plan(_model: Any, components: Any, baseline: Any) -> list[Step]:
    # Pairs split on their side of the bank by their saved z (transform
    # translation, metres): plan_explode refuses a pair that is not one a side.
    # The pivot pin's members share a file: each is keyed by its member.
    instances = [
        Instance(
            name=name,
            stem=member_family(*component_identity(component)),
            z_mm=baseline[name][11] * 1000.0,
        )
        for name, component in components
    ]
    return [
        Step(step.label, tuple(names), step.axis, step.distance_mm)
        for step, names in plan_explode(instances)
    ]


def create_channel_explode(adapter: Any, configuration_name: str) -> None:
    """Author the released presentation in the active ``configuration_name``
    (Default or Default Simplified) and restore the working model."""
    _explode_steps.author_explode_steps(
        adapter,
        configuration_name,
        view=EXPLODED_VIEW_NAME,
        source=SOURCE_CONFIGURATION,
        step_prefix="CHANNEL",
        plan=_plan,
    )
