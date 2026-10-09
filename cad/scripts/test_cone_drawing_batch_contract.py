"""Cross-sheet offline contracts for the six cone-cluster drawing packages."""

from __future__ import annotations

import _config
import dt_arbor_pedestal_spec
import dt_cone_gear_notes
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec
import dt_cone_pivot_post_spec
import dt_cone_tip_block_spec
import dt_cone_swing_platform_spec


SHEETS = (
    ("dt-arbor-pedestal", dt_arbor_pedestal_spec),
    ("dt-cone-gear", dt_cone_gear_notes),
    ("dt-cone-gear-shaft", dt_cone_gear_shaft_spec),
    ("dt-cone-pivot-post", dt_cone_pivot_post_spec),
    ("dt-cone-tip-block", dt_cone_tip_block_spec),
    ("dt-cone-swing-platform", dt_cone_swing_platform_spec),
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK SHARP",
    "DEBUR",
    "DRAWING UNITS",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "UNLESS OTHERWISE SPECIFIED",
    "UNITS:",
    " UOS",
)


def test_notes_do_not_repeat_title_block_metadata() -> None:
    # Feature-specific edge limits remain valid exceptions to the title block's
    # general edge treatment.  Pivot-ball-mount intentionally tightens its two
    # functional shoulders to 0.10 max, rather than repeating the UOS 0.25 max.
    for part_name, spec in SHEETS:
        notes = getattr(spec, "DRAWING_NOTES", "").upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_every_cone_sheet_names_the_actual_finite_cutting_system() -> None:
    spec = dt_cone_gear_spec
    assert spec.DIAMETRAL_PITCH == _config.machine("gear_train", "diametral_pitch")
    assert spec.PRESSURE_ANGLE_DEG == _config.machine(
        "gear_train", "pressure_angle_deg"
    )
    assert len(spec.CONFIGURATION_TEETH) == 20
    for teeth in spec.CONFIGURATION_TEETH:
        data = dt_cone_gear_notes.gear_data(teeth)
        assert f"T{teeth:03d}" in data
        assert (
            f"DIAMETRAL PITCH / PRESSURE ANGLE:  "
            f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f} DEG"
        ) in data
        assert "CUTTER:" in data
        assert "PLUNGE" in data
        assert "WHOLE DEPTH" in data
        assert "STOCK-FORM COVERAGE" in data
        assert "CONTACT RATIO" not in data
        assert "RANGE ONLY" not in data
        assert "MATCH FLANKS" not in data
        assert "APPROVED" not in data
        assert "EXCEPTION" not in data
        assert "RULING" not in data
