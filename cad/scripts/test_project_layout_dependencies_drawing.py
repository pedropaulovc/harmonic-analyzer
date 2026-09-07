"""Native-layout changes invalidate migrated pilots, not all manufacturing prints."""

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
}
NATIVE_LAYOUT_HELPERS = {
    "_drawing_annotation_bounds.py",
    "_drawing_leader_clearance.py",
    "_drawing_measurement_handoff.py",
    "_drawing_native_callouts.py",
    "_drawing_native_gtol.py",
    "_drawing_native_layout.py",
    "_drawing_view_packing.py",
}


def test_common_framework_has_no_transitive_native_layout_dependency():
    closure = {
        Path(path).name for path in module_deps_of(SCRIPTS / "_drawing_common.py")
    }
    assert not closure & (NATIVE_LAYOUT_HELPERS | {"_drawing_project_layout.py"})


@pytest.mark.parametrize(
    "script", sorted(SCRIPTS.glob("draw_*.py")), ids=lambda p: p.name
)
def test_only_explicit_native_layout_pilots_include_the_full_native_helper_closure(
    script,
):
    closure = {Path(path).name for path in module_deps_of(script)}
    expected = NATIVE_LAYOUT_HELPERS | {"_drawing_project_layout.py"}
    if script.name in PILOTS:
        assert expected <= closure
        return
    assert not closure & expected


def test_every_declared_pilot_is_an_actual_recipe():
    assert PILOTS <= {path.name for path in SCRIPTS.glob("draw_*.py")}
