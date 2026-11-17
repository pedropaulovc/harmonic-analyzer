"""The named ``PN_EXPLODED`` presentation of pn-pen.SLDASM (MHA-PN-00).

``_explode.author_explode_steps`` authors and proves each step of
``pn_pen_explode_spec.EXPLODE_STEPS`` (every instance of the named stems)
along a global axis, and leaves the operational model collapsed with its
transforms unchanged.
"""

from __future__ import annotations

from typing import Any

import _explode
from _component_references import component_reference_names
from _explode import Step
from pn_pen_assembly_spec import QUANTITIES
from pn_pen_explode_spec import EXPLODE_STEPS, EXPLODED_VIEW_NAME, SOURCE_CONFIGURATION
from sh_vn_music_wire_pen_geom import CONFIGURATION as PEN_WIRE_CONFIGURATION


def _plan(model: Any, components: Any, _baseline: Any) -> list[Step]:
    component_reference_names(
        model, {"@PenWire:1": ("sh-vn-music-wire", PEN_WIRE_CONFIGURATION)}
    )
    groups = _explode.stem_groups(components, QUANTITIES)
    return [
        Step(
            label,
            tuple(name for stem in stems for name in groups[stem]),
            key,
            distance_mm,
        )
        for label, stems, key, distance_mm in EXPLODE_STEPS
    ]


def create_pn_explode(adapter: Any, configuration_name: str) -> None:
    """Author the presentation in the active ``configuration_name`` (Default or
    Default Simplified) and leave the operational model collapsed."""
    _explode.author_explode_steps(
        adapter,
        configuration_name,
        view=EXPLODED_VIEW_NAME,
        source=SOURCE_CONFIGURATION,
        step_prefix="PN",
        plan=_plan,
    )
