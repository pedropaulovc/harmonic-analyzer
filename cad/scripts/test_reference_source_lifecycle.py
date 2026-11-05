"""Shared supplier-source lifecycle stays outside every drawing family's closure."""

from __future__ import annotations

from pathlib import Path

from _buildgraph import module_deps_of

SCRIPTS = Path(__file__).resolve().parent
_SPRING_MODULES = frozenset(
    {"_supplier_spring_drawing.py", "_supplier_extension_spring.py"}
)


def _closure(script: Path) -> frozenset[str]:
    return frozenset(Path(dep).name for dep in module_deps_of(script))


def test_source_lifecycle_helper_does_not_reach_spring_modules() -> None:
    closure = _closure(SCRIPTS / "_reference_source_lifecycle.py")
    assert not closure & _SPRING_MODULES, sorted(closure & _SPRING_MODULES)


def test_configured_purchased_drawings_do_not_depend_on_spring_drawing() -> None:
    """A spring-sheet edit must not invalidate configured purchased-kit cache keys."""
    configured = {
        script.name: _closure(script)
        for script in sorted(SCRIPTS.glob("draw_*.py"))
        if "_purchased_variant_drawing.py" in _closure(script)
    }
    assert {
        "draw_ch_rocker_arm_tl_vn_oblique_rail_kit.py",
        "draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit.py",
        "draw_sh_vn_clamping_kit_hardware.py",
    } <= set(configured)
    for name, closure in configured.items():
        assert "_reference_source_lifecycle.py" in closure, name
        assert not closure & _SPRING_MODULES, (name, sorted(closure & _SPRING_MODULES))
