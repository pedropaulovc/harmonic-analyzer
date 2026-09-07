"""Explicit owned-pilot inputs and existing production readback contracts.

Initial hashes pin exact native inputs observed on 2026-09-06. Matching execution
tokens were read for the two shafts; this does not prove builder provenance.
Alignment's explicit 2026-09-07 production-builder migration is recorded in
diagnostics/alignment_source_manifest.md. Six gear migrations from the real
7f070434 builds are recorded in diagnostics/gear_source_manifest.md.
Two fastener production-builder inputs are explicitly enrolled in
diagnostics/fastener_source_manifest.md; no prior target pin is changed.
The seventeenth target is the actual whole-text-authored fillister output from
the 7f070434 production part build. Full drawing/cold/printed acceptance is
separate; this enrollment only pins those observed bytes and four dimensions.
No recipe, geometry, output path or production layout policy lives here.
"""

from dataclasses import dataclass, field
from importlib import import_module

import channel_lever_spec
import cone_pivot_screw_spec
import cone_tip_adjuster_spec
import fillister_screw_spec
import fulcrum_shaft_spec
import pivot_shaft_spec
import rocker_arm_notes
from diagnostics._recipe_view_roles import VIEW_ROLES, ViewRole
from diagnostics._model_dimension_coverage import ModelDimensionRole, SemanticCoverage


@dataclass(frozen=True)
class RecipeTarget:
    source_sha256: str
    spec_module: str
    dimensions: dict[str, set[str]]
    basic: dict[str, set[str]] = field(default_factory=dict)
    entity_labels: dict[str, str] = field(default_factory=dict)
    view_roles: dict[str, ViewRole] = field(default_factory=dict)
    coverage: SemanticCoverage = SemanticCoverage.GEOMETRY
    model_dimensions: tuple[ModelDimensionRole, ...] = ()
    model_views: tuple[str, ...] = ()


def _shaft_labels(stem, spec):
    return {
        **{
            f"{stem} shaft PMI {row.key}": row.key
            for row in (
                *spec.PART_DATUMS,
                *spec.GEOMETRIC_CONTROLS,
            )
        },
        f"{stem} bearing finish": "bearing_finish",
    }


TARGETS = {
    "rocker_arm": RecipeTarget(
        "3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0",
        "rocker_arm_notes",
        rocker_arm_notes.DRAWING_DIMENSIONS,
    ),
    "channel_lever": RecipeTarget(
        "6a994561f19487029c938cd7cca5047acbdfbf686020514be538ef5a632e0841",
        "channel_lever_spec",
        channel_lever_spec.DRAWING_DIMENSIONS,
        channel_lever_spec.SOURCE_BASIC_DIMENSIONS,
    ),
    "fulcrum_shaft": RecipeTarget(
        "73eeb75dcb1f24ca70b5f5ad2212d7b829a94af3a518b7c3830ff6c58e47d740",
        "fulcrum_shaft_spec",
        fulcrum_shaft_spec.DRAWING_DIMENSIONS,
        entity_labels=_shaft_labels("fulcrum", fulcrum_shaft_spec),
    ),
    "pivot_shaft": RecipeTarget(
        "e5bcdb79849aac9ce6068188ccf0c6e2fd1222e82f1d8b4d75e0fd2723f01dc5",
        "pivot_shaft_spec",
        pivot_shaft_spec.DRAWING_DIMENSIONS,
        entity_labels=_shaft_labels("pivot", pivot_shaft_spec),
    ),
    "cone_tip_adjuster": RecipeTarget(
        "18d0c1669c8de923420655d621f58d24afe404bc1d3a5a787930ebeeb2fefbf2",
        "cone_tip_adjuster_spec",
        cone_tip_adjuster_spec.DRAWING_DIMENSIONS,
    ),
    "cone_pivot_screw": RecipeTarget(
        "515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36",
        "cone_pivot_screw_spec",
        cone_pivot_screw_spec.DRAWING_DIMENSIONS,
    ),
    "fillister_screw": RecipeTarget(
        "e7b48995c9f2e87af473219edfca1500a14e77bd353a330c64883011ab4fb60d",
        "fillister_screw_spec",
        fillister_screw_spec.DRAWING_DIMENSIONS,
        coverage=SemanticCoverage.MODEL_DIMENSIONS_ONLY,
        model_views=("*Right", "*Back", "*Isometric"),
        model_dimensions=(
            ModelDimensionRole("HeadProfile", "HeadDia", "*Back", 6, (10,)),
            ModelDimensionRole(
                "ShankProfile",
                "ShankDia",
                "*Right",
                6,
                (10,),
                (fillister_screw_spec.THREAD_DESIGNATION,),
            ),
            ModelDimensionRole("Head", "HeadHt", "*Right", 2, ()),
            ModelDimensionRole(
                "Shank",
                "ShankLg",
                "*Right",
                2,
                (),
                (fillister_screw_spec.SIDE_DIMENSION_CALLOUTS["ShankLg"],),
            ),
        ),
    ),
}


# Source provenance is recorded per migration above. The remaining historical
# pins were compared with execution tokens on 2026-09-06, not built by the probe.
_VIEW_SOURCE_HASHES = {
    # Actual authored production output; historical 858dc... receipts stay intact.
    "alignment_pinion": "9e09613dcdfeadcd76cfa4e28f2c9b6035ea1736bdb1bbcca1a7ecc3239c0632",
    "cone_gear_shaft": "8df108cb4053bd47bcc1acc8b83fede6e3a52a9d3c4f6341c1ab3702d512b0ab",
    "crank_drive_gear": "a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f",
    "crank_pinion": "1b3a9dc571e1256459a10dd7e2d0815d35d41c284bf8665a9546751ac242ef24",
    "crankshaft": "3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94",
    "cylinder_gear": "b436e33215ced1c3791cfd4095f49b376258edc1d4896f86656cd1b569a966f9",
    "rack_pinion": "6591e6a5abf67a5a541ae8d4ee9542795bf37b5bfcb18121ee4636e963096fa7",
    "spring_hook": "29c04a0919e0f720915527bd62cdb90eed909de6d14e74b9068c106baa42ace5",
    "transgear_feed_pinion": "93bc3466e0066f267d66223fc6ac2eed020ebdc10b665981f6685f1947f33d74",
    "transgear_pinion": "989b42c133984a367517dfeb43f96bdf4201a2c899c4b2c9801d8ab7cb41e6c0",
}
for _target, _hash in _VIEW_SOURCE_HASHES.items():
    _spec_name = "spring_hook_notes" if _target == "spring_hook" else f"{_target}_spec"
    _spec = import_module(_spec_name)
    TARGETS[_target] = RecipeTarget(
        _hash,
        _spec_name,
        _spec.DRAWING_DIMENSIONS,
        view_roles=VIEW_ROLES[_target],
    )
