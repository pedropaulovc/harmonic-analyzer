"""Offline plug/tap and legacy-drawing contracts; no joint geometry approval."""

from __future__ import annotations

import ast
from pathlib import Path
import re

import build_sm_gooseneck as part
import draw_sm_gooseneck as drawing
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec
import sm_gooseneck_spring_joint as joint


def test_physical_plug_and_modelling_overlap_are_distinct() -> None:
    tube_id = geom.TUBE_DIA - 2.0 * geom.WALL_T

    assert joint.PLUG_DIA == part.PLUG_DIA == tube_id
    assert tube_id < part.PLUG_OVERLAP_DIA < geom.TUBE_DIA
    assert part.PLUG_OVERLAP_DIA == geom.TUBE_DIA - geom.WALL_T
    assert part.PLUG_LENGTH == geom.PLUG_LENGTH


def test_receiver_uses_the_shared_native_through_tap() -> None:
    assert part.TAP_SPEC is drawing.TAP_SPEC is spec.TAP_SPEC is joint.TAP_SPEC
    assert part.TAP_DRILL_DIA == drawing.TAP_DRILL_DIA == joint.TAP_DRILL_DIA
    assert joint.TAP_SPEC.kind == "tapped"
    assert joint.TAP_SPEC.end == "through_all"
    assert joint.TAP_SPEC.thread_class == "2B"

    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    taps = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "wizard_holes"
    ]
    assert len(taps) == 1
    assert isinstance(taps[0].args[1], ast.Name)
    assert taps[0].args[1].id == "TAP_SPEC"
    assert any(
        keyword.arg == "name" and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == "ThreadBore"
        for keyword in taps[0].keywords
    )
    # Through-all must be upstream of the curved tube: otherwise the drill
    # exits the straight bore and perforates the bend's far wall as well.
    sweeps = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "create_sweep"
    ]
    assert sweeps
    assert taps[0].lineno < min(node.lineno for node in sweeps)


def test_both_tap_breaks_reduce_the_printed_full_thread_length() -> None:
    assert joint.ENGAGEMENT_NOMINAL == geom.PLUG_LENGTH - 2.0 * joint.EDGE_BREAK
    assert joint.ENGAGEMENT_MIN == joint.ENGAGEMENT_NOMINAL - joint.PLUG_LENGTH_BAND

    notes = " ".join(spec.DRAWING_NOTES.split())
    assert re.search(r"BREAK BOTH TAP ENDS\s+" + f"{joint.EDGE_BREAK:.2f}", notes)
    assert re.search(
        r"FULL THREAD\s+" + f"{joint.ENGAGEMENT_NOMINAL:.2f}"
        + r"\s+NOMINAL;\s+" + f"{joint.ENGAGEMENT_MIN:.2f}" + r"\s+MIN",
        notes,
    )


def test_plug_print_uses_physical_size_and_shared_loose_bands() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split())
    plug = re.search(
        r"END PLUG:.*?<MOD-DIAM>([\d.]+)\s+\+/-([\d.]+)"
        r"\s+X\s+([\d.]+)\s+\+/-([\d.]+)",
        notes,
    )
    assert plug is not None
    assert tuple(map(float, plug.groups())) == (
        joint.PLUG_DIA, joint.PLUG_DIAMETER_BAND,
        geom.PLUG_LENGTH, joint.PLUG_LENGTH_BAND,
    )
    assert re.search(
        r"THREAD AXIS TO TUBE AXIS\s+\+/-" + f"{joint.THREAD_AXIS_OFFSET_MAX:.2f}",
        notes,
    )
    assert re.search(r"DRILL WANDER\s+" + f"{joint.DRILL_WANDER_MAX:.2f}" + r"\s+MAX", notes)
    assert f"{joint.TAP_SPEC.size} UNC-{joint.TAP_SPEC.thread_class} THRU PLUG" in notes
    assert "SILVER-BRAZE" in notes


def test_weldment_no_longer_owns_an_integral_screw() -> None:
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    obsolete = {
        "PLUG_T", "SCREW_SHANK_DIA", "SCREW_SHANK_LEN", "SCREW_HEAD_DIA",
        "SCREW_HEAD_T", "SCREW_TIP_X", "SHANK_R", "HEAD_R", "HEAD_X",
        "v_shank", "v_head", "v_screw",
    }
    assert not names & obsolete
    notes = " ".join(spec.DRAWING_NOTES.split()).upper()
    assert "MHA-VN-054" in notes and "PURCHASED" in notes
    assert "NOT INCLUDED IN THIS WELDMENT" in notes
    assert "MODELED INTEGRAL" not in notes
    assert "SHANK EXPOSED" not in notes and "SLOT" not in notes
    assert "THREADLOCKER" not in notes  # spring-eye clamping belongs to the assembly


def test_legacy_drawing_imports_only_the_marked_form_dimensions() -> None:
    assert set(drawing.FRONT_KEEP) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert spec.DRAWING_DIMENSIONS == {"BendPath": {"BendRadius", "ArmRun"}}
