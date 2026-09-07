"""All drawings validate prepared defaults; placement remains pilot-only."""

from pathlib import Path

import pytest

from _buildgraph import module_deps_of


SCRIPTS = Path(__file__).resolve().parent
PILOTS = {
    "draw_arbor_pedestal.py",
    "draw_channel_lever.py",
    "draw_cone_gear.py",
    "draw_cone_pivot_screw.py",
    "draw_pen_marker.py",
    "draw_pen_v_block.py",
    "draw_rocker_arm.py",
    "draw_slotted_screw.py",
}
NATIVE_LAYOUT_HELPERS = {
    "_drawing_leader_clearance.py",
    "_drawing_measurement_handoff.py",
    "_drawing_native_callouts.py",
    "_drawing_native_gtol.py",
    "_drawing_native_layout.py",
}
TEMPLATE_MEASUREMENT_HELPERS = {
    "_drawing_annotation_bounds.py",
    "_drawing_view_packing.py",
}


def test_common_framework_has_no_transitive_native_layout_dependency():
    closure = {
        Path(path).name for path in module_deps_of(SCRIPTS / "_drawing_common.py")
    }
    assert not closure & (
        NATIVE_LAYOUT_HELPERS
        | TEMPLATE_MEASUREMENT_HELPERS
        | {"_drawing_project_layout.py"}
    )


@pytest.mark.parametrize(
    "script", sorted(SCRIPTS.glob("draw_*.py")), ids=lambda p: p.name
)
def test_only_explicit_native_layout_pilots_include_the_full_native_helper_closure(
    script,
):
    closure = {Path(path).name for path in module_deps_of(script)}
    # Every recipe genuinely calls prepared-default validation on a miss. These
    # measurement/Rect modules are now drawing inputs, not placement opt-in.
    assert TEMPLATE_MEASUREMENT_HELPERS <= closure
    assert {
        "_drawing_build.py",
        "_drawing_prepared_template.py",
        "_drawing_template_defaults.py",
    } <= closure
    expected = NATIVE_LAYOUT_HELPERS | {"_drawing_project_layout.py"}
    if script.name in PILOTS:
        assert expected <= closure
        return
    assert not closure & expected


def test_every_declared_pilot_is_an_actual_recipe():
    assert PILOTS <= {path.name for path in SCRIPTS.glob("draw_*.py")}
