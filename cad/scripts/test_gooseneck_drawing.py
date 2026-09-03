"""Offline contracts for the gooseneck drawing."""

from __future__ import annotations

import re
from pathlib import Path

import build_gooseneck as part
import draw_gooseneck as drawing
import gooseneck_geom as geom
import gooseneck_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/gooseneck.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/gooseneck.pdf")
    assert drawing.PNG.as_posix().endswith("/png/gooseneck_drawing.png")
    assert DRAWINGS_BY_NAME["gooseneck"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is gooseneck_spec.DRAWING_DIMENSIONS
    marked = set().union(*gooseneck_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_describe_the_chrome_tube_and_bend() -> None:
    notes = gooseneck_spec.DRAWING_NOTES
    assert "2.0 WALL" in notes
    assert "SILVER-BRAZE" in notes
    assert "AISI 1018" in notes
    assert "FAYING-SURFACE PENETRATION" in notes
    assert "CHROME" not in notes
    assert "X.XX" not in notes
    # 2026-09-02 photo re-derive (ch19 p.45 close-up): the spring hangs on a
    # slotted screw driven axially into the plugged arm end, not on a lug +
    # cross-pin. The notes must schedule plug, tap and screw -- and must
    # match the modelled nominals so the print and the part cannot drift.
    assert "END PLUG" in notes
    assert "#6-32" in notes
    assert "SLOTTED ROUND HEAD" in notes
    assert (
        f"DIAGONAL DRIVER SLOT {geom.SCREW_SLOT_W:.2f} WIDE"
        f" X {geom.SCREW_SLOT_D:.2f} DEEP."
    ) in notes
    assert not re.search(r"\bLUG\b", notes)  # \b: the end PLUG stays
    assert not re.search(r"\bPIN\b", notes)
    assert f"X {geom.PLUG_T:.2f}, FLUSH" in notes
    assert f"HEAD <MOD-DIAM>{geom.SCREW_HEAD_DIA:.2f} X {geom.SCREW_HEAD_T:.2f}" in notes
    assert f"{geom.SCREW_SHANK_LEN:.2f}\n   +/-0.25 SHANK EXPOSED" in notes
    leg = part.LEG_TOP - part.LEG_BOTTOM
    assert f"{leg:g} STRAIGHT LEG" in notes
    assert f"{part.ARM_RUN:g} STRAIGHT ARM" in notes
    assert len(notes.splitlines()) <= 22
    assert max(len(line) for line in notes.splitlines()) <= 60


def test_part_reimports_the_geometry_nominals_assemblies_read() -> None:
    # gooseneck_geom is the prose-free import surface for build_summing_assembly
    # (codex #361 pattern, like boss_hook_geom); the part build must use the
    # SAME objects so the hang proof and the geometry can never drift.
    for name in (
        "ARM_END_X", "ARM_Y", "PLUG_T", "SCREW_HEAD_DIA", "SCREW_HEAD_T",
        "SCREW_SHANK_DIA", "SCREW_SHANK_LEN", "SCREW_SLOT_ANGLE_DEG",
        "SCREW_SLOT_D", "SCREW_SLOT_W", "TUBE_DIA", "WALL_T",
    ):
        assert getattr(part, name) == getattr(geom, name), name
    assert abs(part.LEG_TOP - (geom.ARM_Y - part.BEND_R)) < 1e-6
    # The eye must clear the head shoulder and the end face along the shank,
    # with room for the head to exist beyond the eye.
    assert 0.0 < geom.SCREW_SHANK_LEN
    assert geom.SCREW_SHANK_DIA < geom.SCREW_HEAD_DIA
    # The head must RETAIN a slack eye: wider than the eye's inner diameter.
    import counter_spring_spec as spring

    assert geom.SCREW_HEAD_DIA > spring.COIL_ID
    assert geom.SCREW_SHANK_DIA + 2 * 0.25 <= spring.COIL_ID  # 0.25 radial air
    assert 0.0 < geom.SCREW_SLOT_W < geom.SCREW_HEAD_DIA
    assert 0.0 < geom.SCREW_SLOT_D < geom.SCREW_HEAD_T
    assert geom.SCREW_SLOT_ANGLE_DEG == 45.0
    assert geom.PLUG_T > 0.0
    assert part.PLUG_DIA < geom.TUBE_DIA  # never coincident with the tube OD
    assert part.PLUG_DIA > geom.TUBE_DIA - 2.0 * geom.WALL_T  # real wall overlap
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert '"Manufacturing Notes", 0.016, 0.114' in source


def test_axial_end_screw_has_a_real_diagonal_driver_slot() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for global_name in (
        "ScrewSlotW",
        "ScrewSlotD",
        "ScrewSlotAngle",
        "ScrewSlotSpan",
    ):
        assert f'set_global(adapter, "{global_name}"' in source
    slot_source = source.split("# 4. Diagonal driver slot", 1)[1].split(
        "# Apply the deferred drive equations", 1
    )[0]

    # The profile belongs on the screw's negative-X axial face, not on the
    # cylindrical head wall, and the cut must run inward toward +X.
    assert 'base_plane="Right Plane", offset=SCREW_TIP_X' in slot_source
    assert (
        'name_dimensions(\n'
        '        adapter, "ScrewDriverFace", ["DriverFaceOffset"]'
    ) in slot_source
    assert (
        '\'-"ArmEndX" + "ScrewShankLen" + "ScrewHeadT"\''
        in slot_source
    )
    assert 'await adapter.create_sketch("ScrewDriverFace")' in slot_source
    assert 'name_last_feature(adapter, "DriverSlotProfile")' in slot_source
    assert "adapter.create_cut_extrude(" in slot_source
    assert "reverse_direction=True" in slot_source
    assert 'name_last_feature(adapter, "DriverSlot")' in slot_source

    # Both the 45-degree profile and blind depth remain equation-driven.
    assert 'cos("ScrewSlotAngle")' in slot_source
    assert 'sin("ScrewSlotAngle")' in slot_source
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in slot_source
    assert 'drive_jobs.append((slot_depth_name, \'"ScrewSlotD"\'))' in slot_source

    # The final expected solid volume must lose the real circle/strip cut.
    assert "slot_strip_area(HEAD_R, SCREW_SLOT_W) * SCREW_SLOT_D" in slot_source
    assert "vol - v_slot" in slot_source

    # The offset construction plane must not leak into saved part/drawing views.
    assert '"ScrewDriverFace", "PLANE"' in slot_source
    assert "null_callout()" in slot_source
    assert "model.BlankRefGeom()" in slot_source
    assert slot_source.count("model.ClearSelection2(True)") >= 2


def test_view_scale_is_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 3)" in source
    assert "scale=(1, 4)" in source
    # The arm-end detail view was intentionally dropped (see the "NO end-screw
    # detail view" rationale in draw_gooseneck.py): assert no detail-view CALL
    # exists, not the historical mention in the explanatory comment.
    assert "CreateDetailViewAt4(" not in source
    assert "NO end-screw detail view" in source
    assert gooseneck_spec.ELEVATION_VIEW_NOTE == "ELEVATION SCALE 1:3"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("gooseneck")
    assert config["material"] == "AISI 1010 seamless steel tube"
    assert config["material"] == config["material_specification"]
    assert "chrome" not in str(config["material_specification"]).lower()
    assert "ASTM B456 SC2" in str(config["finish"])
    assert int(config["quantity"]) == 1
