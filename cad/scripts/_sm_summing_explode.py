"""The summing assembly's builder-owned named explode (SM_EXPLODED).

``create_summing_explode`` has ``_explode_steps.author_explode_steps`` author
and prove ``sm_summing_explode_spec.EXPLODE_STEPS`` along the assembly's
native world axes, leaving the operational model collapsed. A step that names
a knife-mount station moves only the instances on that side of the lever's
centre plane, read from the collapsed pose.
"""

from __future__ import annotations

from typing import Any, Mapping

import _explode_steps
import sm_summing_assembly_spec as spec
import sm_summing_explode_spec as explode
from _cone_axis_constants import SUMMING_Z
from _explode_steps import Step, Transform


def station_of(z_mm: float) -> str:
    """The knife-mount station an instance at world ``z_mm`` belongs to."""
    if abs(z_mm - SUMMING_Z) < 1.0:
        raise ValueError(f"z {z_mm:.3f} sits on the lever centre plane, not a station")
    return explode.STATIONS[0] if z_mm > SUMMING_Z else explode.STATIONS[1]


def _plan(
    _model: Any, components: Any, baseline: Mapping[str, Transform]
) -> list[Step]:
    groups = _explode_steps.stem_groups(components, spec.QUANTITIES)
    steps = []
    for label, stems, station, key, distance_mm in explode.EXPLODE_STEPS:
        moved = tuple(
            name
            for stem in stems
            for name in groups[stem]
            if station is None or station_of(baseline[name][11] * 1000.0) == station
        )
        if station is not None and len(moved) != sum(
            spec.QUANTITIES[stem] // len(explode.STATIONS) for stem in stems
        ):
            raise ValueError(f"{label}: {station} station holds {len(moved)} instances")
        steps.append(Step(label, moved, key, distance_mm))
    return steps


def create_summing_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``explode.EXPLODE_STEPS`` in the active ``configuration_name``
    (Default or Default Simplified) and leave the operational model collapsed."""
    _explode_steps.author_explode_steps(
        adapter,
        configuration_name,
        view=explode.EXPLODED_VIEW_NAME,
        source=explode.SOURCE_CONFIGURATION,
        step_prefix="SM",
        plan=_plan,
    )
