from __future__ import annotations

import re
from pathlib import Path

from _fastener_catalog import DriveStyle, FASTENERS, Finish, HeadStyle


_THREADED_BUILDERS = {
    "bracket-screw",
    "clamp-screw",
    "cone-lock-knob",
    "cone-pivot-screw",
    "cone-tip-adjuster",
    "cone-tip-pinch-screw",
    "fillister-screw",
    "foot-screw",
    "hanger-screw",
    "hex-bolt",
    "lag-screw",
    "pen-set-screw",
    "slotted-screw",
    "swing-stop-screw",
    "thumb-screw",
}


def test_catalog_covers_every_threaded_fastener_builder() -> None:
    scripts = Path(__file__).parent
    missing_scripts = {
        stem for stem in _THREADED_BUILDERS
        if not (scripts / f"build_{stem.replace('-', '_')}.py").is_file()
    }
    assert not missing_scripts
    assert set(FASTENERS) == _THREADED_BUILDERS


def test_catalog_uses_us_customary_unc_threads() -> None:
    designation = re.compile(r"^(?:#[0-9]+|[0-9]+/[0-9]+)-[0-9]+$")
    assert all(designation.fullmatch(spec.thread) for spec in FASTENERS.values())


def test_catalog_material_and_finish_are_consistent() -> None:
    for spec in FASTENERS.values():
        assert spec.length_mm > 0
        assert spec.model_diameter_mm > 0
        if spec.material == "Brass":
            assert spec.finish is Finish.BRASS
        if spec.finish is Finish.BRASS:
            assert spec.material == "Brass"


def test_period_fasteners_keep_their_visible_drive_style() -> None:
    slotted = {
        "bracket-screw",
        "clamp-screw",
        "cone-pivot-screw",
        "cone-tip-adjuster",
        "cone-tip-pinch-screw",
        "fillister-screw",
        "foot-screw",
        "lag-screw",
        "slotted-screw",
        "swing-stop-screw",
    }
    assert {name for name, spec in FASTENERS.items() if spec.drive is DriveStyle.SLOT} == slotted
    assert FASTENERS["hanger-screw"].head is HeadStyle.HEX
