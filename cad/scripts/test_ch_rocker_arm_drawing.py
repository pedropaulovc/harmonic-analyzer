"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import replace

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ch_rocker_arm_notes
import ch_rocker_arm_spec
import _rocker_interface as rocker_interface
import draw_ch_rocker_arm as drawing
import build_ch_rocker_arm as arm
import _drawing_detail_crop as detail_crop
from _drawing_layout_check import DrawableRegion
from _gtol_frame import gtol_frame_signature, gtol_frame_xml
from _layout_geometry import AnnotationGeometry, Box, Segment, segment_box_distance, text_overlap
from _drawing_registry import DRAWINGS_BY_NAME
from _cone_axis_constants import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


def _native(*interfaces, **members):
    """Declare a producer's interfaces; never infer ownership from its members."""
    if {"IAnnotation", "IDisplayDimension"} <= set(interfaces):
        raise AssertionError("annotation and display dimension require distinct objects")
    return SimpleNamespace(_native_interfaces=interfaces, **members)


def _bind_owner(native, interface, *_members):
    """NULL survives binding; unknown and wrong interfaces fail without COM."""
    if native is None:
        return None
    owners = getattr(native, "_native_interfaces", ())
    if interface not in owners:
        raise RuntimeError(f"native owner mismatch: {owners!r} cannot bind {interface}")
    query = getattr(native, "_native_query", None)
    return query(interface) if query is not None else native


def _front_xy(mx: float, my: float) -> tuple[float, float]:
    """Offline projection fixture, never production or native layout evidence."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    return (drawing.FRONT_CENTER[0] + mx * scale,
            drawing.FRONT_CENTER[1] + (my - drawing.TOP_END_Y / 2.0) * scale)


def _end_xy(mx: float, my: float) -> tuple[float, float]:
    scale = drawing.END_SCALE[0] / drawing.END_SCALE[1] / 1000.0
    cx = (drawing.BOT_END_X + drawing.ROD_TIP_X) / 2.0
    cy = (drawing._BOT_END_Y + drawing.TOP_END_Y) / 2.0
    return (drawing.END_CENTER[0] + (mx - cx) * scale,
            drawing.END_CENTER[1] + (my - cy) * scale)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["ch_rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_rocker_arm_notes.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.HUB_KEEP, drawing.END_KEEP, drawing.RIGHT_KEEP)
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(map(len, keeps)) == len(marked)
    assert not hasattr(drawing, "TOP_KEEP")


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_interface.ROD_HOLE_X,
        ch_rocker_arm_spec.TOP_END_Y,
    )
    assert ch_rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert ch_rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert ch_rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert ch_rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert arm.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(ch_rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        rocker_interface.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(rocker_interface.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    # View F is labelled as its own removed view (MR #1020), from a stamped
    # part property the drawing requires, right after the iso caption; its
    # caption names the front's viewing arrow and the scale the view is placed
    # at (3:1 since Opus #1020 r2, so the hub width and datum G read apart).
    assert "scale=RIGHT_SCALE" in source
    assert drawing.RIGHT_SCALE == (ch_rocker_arm_notes.RIGHT_VIEW_SCALE, 1)
    assert ch_rocker_arm_notes.RIGHT_VIEW_NOTE.endswith(
        f"SCALE {drawing.RIGHT_SCALE[0]}:{drawing.RIGHT_SCALE[1]}"
    )
    assert f"VIEW {ch_rocker_arm_notes.VIEW_ARROW_LETTER} " in ch_rocker_arm_notes.RIGHT_VIEW_NOTE
    # The caption sits under view F's silhouette, inside the sheet border.
    scale = drawing.RIGHT_SCALE[0] / drawing.RIGHT_SCALE[1]
    view_bottom = drawing.RIGHT_CENTER[1] - ch_rocker_arm_spec.TOP_END_Y * scale / 2000.0
    assert drawing.RIGHT_CAPTION_XY[1] < view_bottom - 0.02
    assert drawing.RIGHT_CAPTION_XY[0] > 0.0125
    assert (
        'add_property_linked_note(adapter, "Isometric View Note", *ISO_CAPTION_XY)\n'
        '    add_property_linked_note(adapter, "Right View Note", *RIGHT_CAPTION_XY)'
    ) in source
    build = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    reads = [
        node for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "read_required_properties"
    ]
    assert len(reads) == 1
    (_model, names), keywords = reads[0].args, {k.arg: k.value for k in reads[0].keywords}
    assert "Right View Note" in ast.literal_eval(names)
    assert "Right View Note" in ast.literal_eval(keywords["required"])
    part = Path(arm.__file__).read_text(encoding="utf-8")
    assert '"Right View Note"' in part and "RIGHT_VIEW_NOTE" in part


def test_view_arrow_names_the_removed_right_view_from_the_notes_letter() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    statements = [ast.unparse(node) for node in build.body]
    profiles = statements.index("arc_profiles = _add_arc_profiles(adapter, front)")
    assert statements[profiles + 1] == "_add_view_arrow(adapter, front)"
    # The caption and the arrow share one letter, owned by the notes module.
    letter = ch_rocker_arm_notes.VIEW_ARROW_LETTER
    assert f"VIEW {letter} " in ch_rocker_arm_notes.RIGHT_VIEW_NOTE
    arrow = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_add_view_arrow"
    )
    assert "rocker_notes.VIEW_ARROW_LETTER" in ast.unparse(arrow)
    assert not any(
        isinstance(node, ast.Constant) and node.value == letter
        for node in ast.walk(arrow)
    )
    assert drawing.add_leader_note.__module__ == "_drawing_leader_notes"


def test_hub_width_callout_names_the_fit_up_step_that_takes_up_the_stack() -> None:
    """r5 Opus C2 (rule 19): 20 hubs at +0.05/0 can run 1.0 long; the sheet
    names the MHA-CH-00 step whose stack acceptance re-faces a long stack."""
    import ch_channel_assembly_steps as channel_steps
    import draw_ch_channel_assembly as channel_sheet
    import rocker_bank_layout as bank

    key = drawing.ROCKER_STACK_STEP_KEY
    assert drawing.HUB_LENGTH_TEXT.startswith(ch_rocker_arm_notes.HUB_LENGTH_CALLOUT)
    assert drawing.HUB_LENGTH_TEXT.endswith(f"PER\n{channel_steps.step_ref(key)}")
    number = channel_steps.step_number(key)
    printed = " ".join(channel_sheet.FITUP_STEPS.split())
    step = printed.split(f" {number}. ", 1)[1].split(f" {number + 1}. ", 1)[0]
    assert "RE-FACE A LONG STACK" in step
    # The MHA-CH-00 fitter package prints the acceptance band on the rocker
    # bank view's native stack dimension (drawing policy: no limits in note
    # text), so the step names that dimension and the dimension carries
    # STACK_L20_ACCEPT.
    asm = channel_sheet.asm
    assert "TO THE ROCKER BANK VIEW'S STACK DIMENSION" in step
    lower, upper = asm.DIMENSION_TOLERANCES[asm.STACK_LENGTH_DIMENSION]
    nominal = asm.PIVOT_CHAIN_Z[3] - asm.PIVOT_CHAIN_Z[2]
    assert (nominal + lower, nominal + upper) == pytest.approx(bank.STACK_L20_ACCEPT)


def test_native_gdt_and_finish_present() -> None:
    """Native print arguments retain the part-owned limit and A-B-C frame."""
    from _drawing_hole_callout import add_native_hole_callout

    assert drawing.add_native_hole_callout is add_native_hole_callout
    assert drawing.ROD_HOLE.fields["dia"][1] == (
        "ROD_HOLE_SPEC",
        "UNIT",
        ("_hole_spec", "NUMBER_DRILL_MM"),
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), G = the hub's -Z
    # end face: edge tags. C is the rod-pin hole, tagged on its own position
    # frame (option 4), which references only A|B.
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_frame_datum_feature(\n            adapter, end, rod_position_gtol,") == 1
    assert drawing.ROD_HOLE.fields["datum"][0] == "C"
    # Datum A's leader runs oblique, 45 deg off both centre-mark axes.
    assert math.degrees(drawing.PIVOT_DATUM_ANGLE) % 90.0 == pytest.approx(45.0)
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    tree = ast.parse(source)
    frames = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_feature_control_frame"
        and any(
            keyword.arg == "characteristic"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "position"
            for keyword in node.keywords
        )
    ]
    assert len(frames) == 1
    keywords = {keyword.arg: keyword.value for keyword in frames[0].keywords}
    # Evaluate the actual native print-call arguments without invoking COM.
    printed_datums = eval(
        compile(ast.Expression(keywords["datums"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert printed_datums == ("A", "B")
    printed_tolerance = eval(
        compile(ast.Expression(keywords["tolerance"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert (
        printed_tolerance
        == ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN["rod-pin hole position"]
    )
    assert drawing.ROD_HOLE.fields["position_dia"][0] == pytest.approx(float(printed_tolerance) * 25.4)
    assert ast.unparse(keywords["diameter"]) == "True"
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    # r743-p1s-B: both rod-pin annotations take the diameter-picked edge.
    assert "edge_xy=rod_rim" not in source
    assert source.count("edge=rod_hole_edge") == 1
    assert source.count("edge_entity=rod_hole_edge") == 1


def test_profile_nominals_are_kept_natively_without_note_only_duplicates() -> None:
    names = {"TopRadius", "BottomRadius", "TopAbovePivot"}
    assert drawing.BASIC_PROFILE_DIMENSIONS == names
    assert names <= drawing.FRONT_KEEP.keys()
    assert not hasattr(drawing, "NOTE_ONLY_DIMENSIONS")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    definitions = {
        node.name: node for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for caller, callee, arguments in (
        ("build", "_add_rocker_outline_dimensions", ("adapter", "front")),
        ("_add_rocker_outline_dimensions", "_basic_profile_dimensions", ("adapter", "annotations")),
    ):
        calls = [
            node for node in ast.walk(definitions[caller])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == callee
        ]
        assert len(calls) == 1
        assert tuple(ast.unparse(arg) for arg in calls[0].args) == arguments
    assert "_add_arc_profiles(adapter, front)" in source


def test_basic_radius_text_positions_are_outside_their_parent_circles() -> None:
    """Inside-circle R800 placement retained a centre tail on the native sheet."""
    centre_model_y = (
        drawing.PIVOT_MID_Y + ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT + drawing.R_TOP
    )
    centre = _front_xy(0.0, centre_model_y)
    for name, radius in (
        ("TopRadius", drawing.R_TOP),
        ("BottomRadius", drawing.R_BOTTOM),
    ):
        rendered_radius = math.dist(
            centre, _front_xy(0.0, centre_model_y + radius)
        )
        assert math.dist(centre, drawing.FRONT_KEEP[name]) > rendered_radius
    # Negative control: the former top label lay inside the same nominal circle.
    top_rendered_radius = math.dist(
        centre, _front_xy(0.0, centre_model_y + drawing.R_TOP)
    )
    assert math.dist(centre, (0.130, 0.218)) < top_rendered_radius


def test_radius_text_positions_are_outside_their_parent_circles() -> None:
    """Inside-circle R800 placement retained a centre tail on the native sheet."""
    centre_model_y = (
        drawing.PIVOT_MID_Y + ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT + drawing.R_TOP
    )
    centre = _front_xy(0.0, centre_model_y)
    for name, radius in (
        ("TopRadius", drawing.R_TOP),
        ("BottomRadius", drawing.R_BOTTOM),
    ):
        rendered_radius = math.dist(
            centre, _front_xy(0.0, centre_model_y + radius)
        )
        assert math.dist(centre, drawing.FRONT_KEEP[name]) > rendered_radius
    # Negative control: the former top label lay inside the same nominal circle.
    top_rendered_radius = math.dist(
        centre, _front_xy(0.0, centre_model_y + drawing.R_TOP)
    )
    assert math.dist(centre, (0.130, 0.218)) < top_rendered_radius


def test_r20_local_requests_leave_views_geometry_and_strict_caption_air_unchanged() -> None:
    """Placement hypotheses from R19 ink, not proof of the next native render."""
    assert drawing.FRONT_CENTER == (0.180, 0.175)
    assert drawing.ISO_CENTER == (0.345, 0.205)
    assert drawing.HUB_CENTER == (0.180, 0.095)
    assert drawing.END_CENTER == (0.330, 0.110)
    assert drawing.HUB_SCALE == (4.0, 1.0)
    assert drawing.END_SCALE == (2.0, 1.0)
    assert drawing.DETAIL_NO_OUTLINE == {"D": True, "E": False}
    assert drawing.DETAIL_STYLE == {"D": 2, "E": 2}  # swDetViewLEADER connects each source circle.
    assert drawing.DETAIL_LETTER_XY == {"D": (0.188, 0.161), "E": (0.264, 0.155)}
    assert drawing.ROD_CALLOUT_XY == (0.279, 0.115)
    assert drawing.FCF_XY == (0.262, 0.1001)
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert drawing.DETAIL_GEOMETRY_TOL_M == 0.00005
    # R816 moves left; the RD2 arrow and full witness stay at physical A's X.
    radius_dx = drawing.FRONT_KEEP["BottomRadius"][0] - 0.170
    assert 0.180 - (0.1784 + radius_dx) >= 0.002
    # Hole callout and DOT FCF requests: physical circular edge remains unchanged.
    pin_xy = _end_xy(drawing.ROD_HOLE_X, drawing.ROD_HOLE_Y)
    assert math.dist(drawing.ROD_CALLOUT_XY, pin_xy) < math.dist((0.270, 0.145), pin_xy)


def _view_f_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """View F (Right view) sheet point of model (z, y): +Z prints left."""
    scale = drawing.RIGHT_SCALE[0] / drawing.RIGHT_SCALE[1]
    return (
        drawing.RIGHT_CENTER[0] - z_mm * scale / 1000.0,
        drawing.RIGHT_CENTER[1] + (y_mm - ch_rocker_arm_spec.TOP_END_Y / 2.0) * scale / 1000.0,
    )


def test_datum_b_sits_on_the_projected_broad_face_above_the_hub_and_thickness_block() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    broad = next(
        node for node in build.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(name, ast.Name) and name.id == "broad_face"
            for target in node.targets for name in ast.walk(target)
        )
    )
    call = next(
        node for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_datum_feature"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "broad face"
            for keyword in node.keywords
        )
    )
    calls, projected = [], []
    right = object()

    def project(_adapter, view, points, **_kwargs):
        assert view is right
        projected.extend(points)
        return [_view_f_xy(z * 1000.0, y * 1000.0) for _x, y, z in points]

    namespace = dict(
        adapter=object(), right=right, _project=project,
        ARM_THICKNESS=drawing.ARM_THICKNESS,
        DATUM_B_PICK_MODEL_Y=drawing.DATUM_B_PICK_MODEL_Y,
        DATUM_B_SYMBOL_XY=drawing.DATUM_B_SYMBOL_XY,
        STRAP_DATUM_B=drawing.STRAP_DATUM_B,
        add_datum_feature=lambda *_args, **kwargs: calls.append(kwargs),
    )
    module = ast.Module(body=[broad, ast.Expr(value=call)], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), drawing.__file__, "exec"), namespace)
    assert len(calls) == 1
    assert calls[0]["datum"] == drawing.STRAP_DATUM_B.fields["datum"][0] == "B"
    # The pick is a model point on the +Z broad face, projected natively at
    # view F's scale, above the hub band (the hub hides the flank there) and
    # inside the strap's height.
    ((_x, pick_y, pick_z),) = projected
    assert pick_z * 1000.0 == pytest.approx(ch_rocker_arm_spec.ARM_THICKNESS / 2.0)
    hub_top = rocker_interface.PIVOT_MID_Y + ch_rocker_arm_spec.HUB_DIA / 2.0
    assert hub_top + 5.0 < pick_y * 1000.0 < ch_rocker_arm_spec.TOP_END_Y - 0.5
    assert calls[0]["edge_xy"] == _view_f_xy(pick_z * 1000.0, pick_y * 1000.0)
    # The tag box (~7 mm) hangs up-left of the pick, above the strap
    # thickness block (value + three mate rows, centred on its request).
    symbol_x, symbol_y = calls[0]["symbol_xy"]
    assert symbol_x < calls[0]["edge_xy"][0]
    rows = 1 + len(ch_rocker_arm_notes.STRAP_FIT_CALLOUT.splitlines())
    block_top = drawing.STRAP_THICKNESS_TEXT_XY[1] + (rows - 1) * RENDERED_ROW_PITCH / 2 + 0.00175
    assert symbol_y - 0.0035 - block_top >= 0.003
    assert symbol_y + 0.0035 < DRAWABLE.ymax



class _ProfileDisplay:
    """Model COM property writes, including silently ignored setters."""

    _native_interfaces = ("IDisplayDimension",)

    def __init__(self, ignored: str | None = None) -> None:
        self.ignored = ignored
        self.writes: list[tuple[str, object]] = []
        object.__setattr__(self, "text", {})
        object.__setattr__(self, "ShortenedRadius", True)
        object.__setattr__(self, "ArcExtensionLineOrOppositeSide", True)
        object.__setattr__(self, "ArrowSide", 0)
        object.__setattr__(self, "SolidLeader", True)

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"ShortenedRadius", "ArcExtensionLineOrOppositeSide", "ArrowSide", "SolidLeader"}:
            self.writes.append((name, value))
            if name == self.ignored:
                return
        object.__setattr__(self, name, value)

    def SetText(self, which: int, value: str) -> None:
        self.writes.append((f"text{which}", value))
        if self.ignored != "text":
            self.text[which] = value

    def GetText(self, which: int) -> str:
        return self.text.get(which, "")


def _profile_annotations(monkeypatch: pytest.MonkeyPatch, displays: dict) -> list:
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    return [
        _native("IAnnotation", name=name, GetSpecificAnnotation=lambda display=display: display)
        for name, display in displays.items()
    ]


def test_basic_profile_dimensions_converts_all_three_nominals_only(
    bound: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = object()
    displays = {
        name: _ProfileDisplay()
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot", "PivotDia")
    }
    annotations = _profile_annotations(monkeypatch, displays)
    calls = []
    monkeypatch.setattr(
        drawing, "set_basic_dimension",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    drawing._basic_profile_dimensions(adapter, annotations)
    assert calls == [
        ((adapter, displays[name]), {"label": f"arc-system {name}"})
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
    ]
    # Leader dressing is _dress_arc_radii's job, not the BASIC conversion's.
    assert all(display.writes == [] for display in displays.values())


@pytest.mark.parametrize("missing", ["TopRadius", "BottomRadius", "TopAbovePivot"])
def test_basic_profile_dimensions_rejects_each_missing_nominal(
    bound: None, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    displays = {
        name: _ProfileDisplay()
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
        if name != missing
    }
    annotations = _profile_annotations(monkeypatch, displays)
    monkeypatch.setattr(drawing, "set_basic_dimension", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match=f"BASIC dimensions missing:.*{missing}"):
        drawing._basic_profile_dimensions(object(), annotations)


@pytest.mark.parametrize("radius", ["TopRadius", "BottomRadius"])
def test_dress_arc_radii_rejects_an_unpersisted_centre_callout(
    bound: None, monkeypatch: pytest.MonkeyPatch, radius: str,
) -> None:
    displays = {
        name: _ProfileDisplay("text" if name == radius else None)
        for name in ("TopRadius", "BottomRadius")
    }
    annotations = _profile_annotations(monkeypatch, displays)
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._dress_arc_radii(object(), annotations)


@pytest.mark.parametrize("missing", ["TopRadius", "BottomRadius"])
def test_dress_arc_radii_rejects_each_missing_radius(
    bound: None, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    displays = {
        name: _ProfileDisplay()
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
        if name != missing
    }
    annotations = _profile_annotations(monkeypatch, displays)
    with pytest.raises(RuntimeError, match=f"arc radius dimensions missing:.*{missing}"):
        drawing._dress_arc_radii(object(), annotations)


@pytest.mark.parametrize("radius", ["TopRadius", "BottomRadius"])
@pytest.mark.parametrize("ignored", [
    "ShortenedRadius", "ArcExtensionLineOrOppositeSide", "ArrowSide", "SolidLeader",
])
def test_dress_arc_radii_rejects_ignored_radius_flags(
    bound: None, monkeypatch: pytest.MonkeyPatch, radius: str, ignored: str,
) -> None:
    displays = {
        name: _ProfileDisplay(ignored if name == radius else None)
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
    }
    annotations = _profile_annotations(monkeypatch, displays)
    with pytest.raises(RuntimeError, match=f"{radius} retained its centre-directed radius leader"):
        drawing._dress_arc_radii(object(), annotations)


def test_arc_profiles_attach_two_native_frames_to_nominal_circle_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, front = object(), object()
    monkeypatch.setattr(drawing, "_project", lambda _adapter, _view, points, **_kwargs: [
        _front_xy(x * 1000.0, y * 1000.0) for x, y, _z in points
    ])
    edges = {1600.0: object(), 1632.0: object()}
    picks, frames = [], []

    def circle_edge(actual_adapter, actual_view, diameter):
        assert actual_adapter is adapter
        assert actual_view is front
        picks.append(diameter)
        return edges[diameter]

    monkeypatch.setattr(drawing, "visible_circle_edge", circle_edge)
    native_frames = {"TopRadius": object(), "BottomRadius": object()}

    def add_frame(*args, **kwargs):
        frames.append((args, kwargs))
        return native_frames[("TopRadius", "BottomRadius")[len(frames) - 1]]

    monkeypatch.setattr(drawing, "add_feature_control_frame", add_frame)
    between, letters = [], []
    monkeypatch.setattr(drawing, "_set_profile_between", lambda a, gtol: between.append((a, gtol)))
    monkeypatch.setattr(
        drawing, "add_leader_note",
        lambda a, text, **kwargs: letters.append((a, text, kwargs)) or text,
    )
    assert drawing._add_arc_profiles(adapter, front) == native_frames
    assert picks == [1600.0, 1632.0]
    assert len(frames) == 2
    # Only the lower (Ⓤ0) frame carries J↔K: its zone runs over both lands.
    assert between == [(adapter, native_frames["BottomRadius"])]
    assert [text for _a, text, _kw in letters] == ["J", "K"]
    for (_a, letter, kwargs), sign in zip(letters, (-1.0, 1.0)):
        assert kwargs["view"] is front
        assert kwargs["attach_xy"] == pytest.approx(_front_xy(sign * drawing.TOP_END_X, drawing.TOP_END_Y))
        dx, dy = drawing.BETWEEN_POINT_OFFSET[letter]
        assert kwargs["text_xy"] == pytest.approx((kwargs["attach_xy"][0] + dx, kwargs["attach_xy"][1] + dy))
    # J sits outboard of its corner; K's outboard side holds view F's arrow
    # letter, so K rises above its corner with its text left of the corner.
    assert drawing.BETWEEN_POINT_OFFSET["J"][0] < 0.0
    k_dx, k_dy = drawing.BETWEEN_POINT_OFFSET["K"]
    assert k_dx + 0.0025 < 0.0 < k_dy  # K's ~2.2 mm glyph ends left of its corner
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    for (args, kwargs), name, radius, model_x, frame_xy, outside, quantity in zip(
        frames,
        ("TopRadius", "BottomRadius"),
        (800.0, 816.0),
        (-130.0, 40.0),
        # View F holds the sheet's left band: the lower frame sits under the
        # strap's right half, between the D and E detail letters.
        ((0.130, 0.211), (0.197, 0.163)),
        (".020", "0"),
        (ch_rocker_arm_notes.TOP_EDGE_MATE_CALLOUT, ""),
    ):
        assert args == (adapter, front)
        assert kwargs["edge_entity"] is edges[2.0 * radius]
        assert kwargs["characteristic"] == "profile_surface"
        assert kwargs["tolerance"] == ".020"
        assert kwargs["outside_disposition"] == outside
        assert kwargs["datums"] == ("A", "B", "C")
        assert not kwargs.get("diameter", False)
        assert not kwargs.get("all_around", False)
        assert "edge_xy" not in kwargs
        assert kwargs["label"] == f"arc-system {name} profile"
        # The top frame names the mate that rides the edge, below the frame.
        assert kwargs["quantity"] == quantity
        assert ("MHA-CH-01" in kwargs["quantity"]) is (name == "TopRadius")
        assert kwargs["frame_xy"] == frame_xy
        sheet_x, sheet_y = kwargs["leader_attach_xy"]
        x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
        y = (sheet_y - drawing.FRONT_CENTER[1]) / scale + drawing.TOP_END_Y / 2.0
        assert x == pytest.approx(model_x)
        assert y < rocker_interface.CENTER_Y
        assert math.hypot(x, y - rocker_interface.CENTER_Y) == pytest.approx(radius)


class _BetweenGtol:
    def __init__(self, stored: tuple[bool, str, str] | None = None) -> None:
        self.calls: list[tuple[bool, str, str]] = []
        self.stored = stored

    def SetBetweenTwoPoints(self, between: bool, text_from: str, text_to: str) -> None:
        self.calls.append((between, text_from, text_to))

    def _state(self) -> tuple[bool, str, str]:
        return self.stored if self.stored is not None else self.calls[-1]

    def GetBetweenTwoPoints(self) -> bool:
        return self._state()[0]

    def GetBetweenTwoPointsText(self, index: int) -> str:
        return self._state()[1 + index]


@pytest.mark.parametrize("stored", [None, (False, "", ""), (True, "K", "J"), (True, "J", "")])
def test_profile_between_symbol_is_set_and_read_back(
    monkeypatch: pytest.MonkeyPatch, stored: tuple[bool, str, str] | None,
) -> None:
    gtol, rebuilds = _BetweenGtol(stored), []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda _a, **kw: rebuilds.append(kw["label"]))
    if stored is None:
        drawing._set_profile_between(object(), gtol)
    else:
        with pytest.raises(RuntimeError, match="lower profile between symbol read back"):
            drawing._set_profile_between(object(), gtol)
    assert gtol.calls == [(True, "J", "K")]
    assert rebuilds == ["lower profile between symbol"]


_REAM_ROW = Box(0.1040, 0.1444, 0.1561, 0.1480)
_R816_ROW = Box(0.0815, 0.1512, 0.1032, 0.1547)
# R8 native readbacks at the former (20,134) request, not a frame-width guess.
_R8_LOWER_FRAME_WIDTH_M = 0.047339
_R8_RIGHT_SHOULDER_M = 0.006350
_R8_LOWER_LANDING = (0.130000, 0.170752)


@pytest.mark.parametrize("junction", [(0.1056, 0.1185), (0.0937, 0.1015)])
def test_observed_r6_r7_profile_junctions_intersect_ream_row(junction) -> None:
    """Recorded native junctions, not a side inferred from the frame request."""
    segment = Segment(*junction, 0.1300, 0.1708, "leader")
    target = AnnotationGeometry("REAM +0.03", "hole-callout", "front")
    assert segment_box_distance(segment, _REAM_ROW) == 0.0
    penetration, _span = text_overlap(segment, target, _REAM_ROW)
    assert penetration > 0.0036


def test_r7_cannot_be_proved_clear_from_a_guessed_left_junction() -> None:
    guessed = Segment(0.040 - 0.0064, 0.105 - 0.0035, 0.130, 0.1708, "leader")
    observed = Segment(0.0937, 0.1015, 0.130, 0.1708, "leader")
    assert segment_box_distance(guessed, _REAM_ROW) > drawing.ARC_PROFILE_TEXT_CLEARANCE_M
    assert segment_box_distance(observed, _REAM_ROW) == 0.0


def test_observed_r8_profile_route_intersects_actual_basic_r816_row() -> None:
    observed = Segment(0.073689, 0.130500, *_R8_LOWER_LANDING, "leader")
    target = AnnotationGeometry("BASIC R816", "dim", "front")
    assert segment_box_distance(observed, _R816_ROW) == 0.0
    penetration, _span = text_overlap(observed, target, _R816_ROW)
    assert penetration > 0.0
    assert segment_box_distance(observed, _REAM_ROW) > drawing.ARC_PROFILE_TEXT_CLEARANCE_M


def test_historical_r9_prediction_clears_both_r8_rows_independent_of_r10() -> None:
    """Historical observed-algorithm regression, not proof of current placement."""
    assert drawing.ARC_PROFILE_TEXT_CLEARANCE_M == 0.001
    frame_x, frame_y = (0.020, 0.129)
    head = (frame_x + _R8_LOWER_FRAME_WIDTH_M, frame_y - 0.0035)
    elbow = (head[0] + _R8_RIGHT_SHOULDER_M, head[1])
    assert head == pytest.approx((0.067339, 0.125500))
    assert elbow == pytest.approx((0.073689, 0.125500))
    predicted = (Segment(*head, *elbow, "leader"), Segment(*elbow, *_R8_LOWER_LANDING, "leader"))
    for box, predicted_gap_mm in ((_REAM_ROW, 1.448), (_R816_ROW, 1.547)):
        distance = min(segment_box_distance(segment, box) for segment in predicted)
        assert distance >= drawing.ARC_PROFILE_TEXT_CLEARANCE_M
        assert distance * 1000.0 == pytest.approx(predicted_gap_mm, abs=0.002)


def _native_line(x0, y0, x1, y1):
    return [0, 0, 0, 0, x0, y0, 0, x1, y1, 0]


class _ClearanceDisplayData:
    """Method-shaped native reads; the real dump/parser are NOT replaced."""

    _native_interfaces = ("IDisplayData",)

    def __init__(self, texts, lines, *, primitives=None):
        self.texts, self.lines = texts, lines
        self.primitives = {} if primitives is None else primitives

    def GetLineCount(self):  # noqa: N802
        return len(self.lines)

    def GetLineAtIndex3(self, index):  # noqa: N802
        return self.lines[index]

    def GetTextCount(self):  # noqa: N802
        return len(self.texts)

    def GetTextAtIndex(self, index):  # noqa: N802
        return self.texts[index]["t"]

    def GetTextPositionAtIndex(self, index):  # noqa: N802
        return self.texts[index]["pos"]

    def GetTextHeightAtIndex(self, index):  # noqa: N802
        return self.texts[index]["h"]

    def GetTextRefPositionAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("ref", 1)

    def GetTextAngleAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("ang", 0.0)

    def GetTextFontAtIndex(self, index):  # noqa: N802
        return "Arial"

    def GetTextLineSpacingAtIndex(self, index):  # noqa: N802
        return 0.0

    def GetTextInBoxWidthAtIndex(self, index):  # noqa: N802
        return self.texts[index].get("w", 0.0)

    def __getattr__(self, name):
        # Unused primitive classes have an authoritative zero count, not None.
        primitives = {
            "GetArcCount": ("arcs", "GetArcAtIndex2"),
            "GetArrowHeadCount": ("arrows", "GetArrowHeadAtIndex2"),
            "GetPolyLineCount": ("polylines", "GetPolylineAtIndex2"),
            "GetPolygonCount": ("polygons", "GetPolygonAtIndex"),
            "GetTriangleCount": ("triangles", "GetTriangleAtIndex"),
            "GetEllipseCount": ("ellipses", "GetEllipseAtIndex2"),
        }
        for count_name, (key, getter_name) in primitives.items():
            if name == count_name:
                return lambda: len(self.primitives.get(key, ()))
            if name == getter_name:
                return lambda index: self.primitives.get(key, ())[index]
        raise AttributeError(name)


class _ClearanceAnnotation:
    _native_interfaces = ("IAnnotation",)
    OwnerType, Visible, Layer = 0, 1, ""

    def __init__(self, name, position, data, *, leaders=(), kind=5, hole_callout=True):
        self.name, self.position, self.data = name, position, data
        self.leaders, self.kind = list(leaders), kind
        self.hole_callout = hole_callout

    def GetName(self):  # noqa: N802
        return self.name

    def GetType(self):  # noqa: N802
        return self.kind

    def GetPosition(self):  # noqa: N802
        return self.position

    def GetDisplayData(self):  # noqa: N802
        return self.data

    def GetLeaderCount(self):  # noqa: N802
        return len(self.leaders)

    def GetLeaderPointsAtIndex(self, index):  # noqa: N802
        return self.leaders[index]

    def GetSpecificAnnotation(self):  # noqa: N802
        return _native("IDisplayDimension", IsHoleCallout=lambda: self.hole_callout)


# IDisplayData's documented rows, not shortened fixtures accepted by tolerant
# parsers. Metadata is unitless; all point/size values below are in metres.
_NATIVE_CALLOUT_ROWS = {
    "lines": _native_line(0.03, 0.04, 0.05, 0.04),
    "arcs": [-1, 0, 0, 0, 0.03, 0.04, 0, 0.04, 0.05, 0,
             0.03, 0.05, 0, 0, 0, 1, -1],
    "polylines": [0, 0, 0, 0, 0, 0, 3,
                  0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0],
    "polygons": [0, 0, 0, 0, 3,
                 0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0],
    "triangles": [0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0, -1, 0],
    "arrows": [0.06, 0.05, 0, -1, 0, 0, 0.003, 0.002, 0, 0, 0, 1],
    "ellipses": [-1, 0, 0, 0, 0.03, 0.04, 0, 0.03, 0.04, 0,
                 0.04, 0.04, 0, 0.05, 0.04, 0, 0.04, 0.045, 0],
}


@pytest.fixture
def native_callout_record(monkeypatch):
    """Exercise actual record production without importing/activating COM."""
    import _drawing_layout_audit

    monkeypatch.setattr(_drawing_layout_audit, "_early_bound", _bind_owner)
    data = _ClearanceDisplayData(
        [{"t": "REAM +0.03", "pos": [0.08, 0.09, 0],
          "h": 0.0035, "ref": 1, "ang": 0.0}],
        [],
    )
    annotation = _ClearanceAnnotation("OrdinaryCallout", (0.08, 0.09, 0), data, kind=4)

    def dump():
        reader = _drawing_layout_audit._Reader(object())
        record = _drawing_layout_audit._dump_annotation(reader, annotation)
        assert reader.take_errors() == {}
        assert record is not None
        return record

    return SimpleNamespace(data=data, annotation=annotation, dump=dump)


def test_arc_callout_accepts_native_empty_primitive_sets_and_no_leaders(native_callout_record):
    record = native_callout_record.dump()
    assert set(record["display"]) == {"texts"}
    assert "leaders" not in record
    geometry = drawing._arc_callout_geometry(record, 0.62)
    assert geometry.text_boxes
    assert geometry.segments == ()


@pytest.mark.parametrize("key", tuple(_NATIVE_CALLOUT_ROWS))
def test_arc_callout_accepts_each_documented_primitive_without_array_alignment(
    native_callout_record, key,
):
    case = native_callout_record
    row = list(_NATIVE_CALLOUT_ROWS[key])
    if key == "lines":
        case.data.lines = [row, list(row)]
    else:
        case.data.primitives[key] = [row, list(row)]
    record = case.dump()
    assert len(record["display"][key]) == 2
    assert len(record["display"]["texts"]) == 1
    expected = drawing.annotation_geometry(record, owner="front", advance=0.62)
    snapshot = json.dumps(record, sort_keys=True)
    actual = drawing._arc_callout_geometry(record, 0.62)
    assert actual == expected
    assert json.dumps(record, sort_keys=True) == snapshot


def test_arc_callout_accepts_documented_line_fallback(native_callout_record):
    case = native_callout_record
    row = _native_line(0.03, 0.04, 0.05, 0.04)
    case.data.lines = [row]
    case.data.GetLineAtIndex3 = lambda _index: None
    case.data.GetLineAtIndex2 = lambda index: case.data.lines[index]
    record = case.dump()
    assert record["display"]["lines"] == [row]
    assert drawing._arc_callout_geometry(record, 0.62).segments


@pytest.mark.parametrize("container", [list, tuple])
def test_arc_callout_accepts_explicit_empty_dump_collections(native_callout_record, container):
    record = native_callout_record.dump()
    for key in _NATIVE_CALLOUT_ROWS:
        record["display"][key] = container()
    record["leaders"] = container()
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


@pytest.mark.parametrize("key", tuple(_NATIVE_CALLOUT_ROWS))
@pytest.mark.parametrize("defect", ["empty", "short", "long", "nonfinite", "bool", "string"])
def test_arc_callout_rejects_malformed_primitive_before_tolerant_parser(
    native_callout_record, monkeypatch, key, defect,
):
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS[key])
    if defect == "empty":
        row = []
    elif defect == "short":
        row.pop()
    elif defect == "long":
        row.append(0.0)
    elif defect == "nonfinite":
        row[-1] = float("inf")
    elif defect == "bool":
        row[-1] = True
    elif defect == "string":
        row[-1] = "0.0"
    record["display"][key] = [row]
    monkeypatch.setattr(
        drawing, "annotation_geometry",
        lambda *_a, **_k: pytest.fail("malformed primitive reached tolerant parser"),
    )
    with pytest.raises(ValueError, match=f"invalid native {key} geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("key,index,header", [
    ("polylines", 6, 7), ("polygons", 4, 5),
])
@pytest.mark.parametrize("points", [0, 1, 2, 3])
def test_arc_callout_accepts_complete_variable_point_sequences(
    native_callout_record, key, index, header, points,
):
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS[key][:header + 3 * points])
    row[index] = float(points)
    record["display"][key] = [row]
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


@pytest.mark.parametrize("key,index", [("polylines", 6), ("polygons", 4)])
@pytest.mark.parametrize("invalid_count", [-1.0, 1.5, float("nan"), float("inf"), True, "3"])
def test_arc_callout_rejects_invalid_variable_counts(native_callout_record, key, index, invalid_count):
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS[key])
    row[index] = invalid_count
    record["display"][key] = [row]
    with pytest.raises(ValueError, match=f"invalid native {key} geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("key,index,header", [
    ("polylines", 6, 7), ("polygons", 4, 5),
])
@pytest.mark.parametrize("defect", ["missing-header", "missing-point", "extra-point", "extra-scalar"])
def test_arc_callout_rejects_incomplete_or_extra_variable_sequences(
    native_callout_record, key, index, header, defect,
):
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS[key])
    if defect == "missing-header":
        row = row[:header - 1]
    elif defect == "missing-point":
        row = row[:-3]
    elif defect == "extra-point":
        row.extend([0.07, 0.06, 0.0])
    elif defect == "extra-scalar":
        row.append(0.0)
    record["display"][key] = [row]
    with pytest.raises(ValueError, match=f"invalid native {key} geometry") as caught:
        drawing._arc_callout_geometry(record, 0.62)
    if key == "polylines":
        for evidence in ("header=", "type=", "DataSize=", "N=", f"row_length={len(row)}",
                         "documented length=7+3*N", "GeomData layout unproven"):
            assert evidence in str(caught.value)


@pytest.mark.parametrize("kind,data_size", [(1.0, 0.0), (1.0, 7.0), (1.0, 12.0)])
def test_arc_callout_accepts_documented_polyline_header_without_guessing_geomdata(
    native_callout_record, kind, data_size,
):
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS["polylines"])
    row[:2] = [kind, data_size]
    record["display"]["polylines"] = [row]
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


@pytest.mark.parametrize("index,value", [
    (0, -1.0), (0, 0.5), (0, 2.0), (0, True),
    (1, -1.0), (1, 0.5), (1, 1.0), (1, float("inf")), (1, True),
])
def test_arc_callout_rejects_invalid_polyline_type_or_data_size(native_callout_record, index, value):
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS["polylines"])
    row[index] = value
    record["display"]["polylines"] = [row]
    with pytest.raises(ValueError, match="invalid native polylines geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("points", [0, 2, 3])
def test_arc_callout_accepts_only_documented_leader_point_shapes(native_callout_record, points):
    record = native_callout_record.dump()
    row = [0.03, 0.04, 0, 0.05, 0.04, 0, 0.06, 0.05, 0][:3 * points]
    record["leaders"] = [row] if points else []
    geometry = drawing._arc_callout_geometry(record, 0.62)
    assert sum(segment.role == "leader" for segment in geometry.segments) == max(0, points - 1)


@pytest.mark.parametrize("row", [
    [], [0.0], [0.0] * 3, [0.0] * 5, [0.0] * 7, [0.0] * 8, [0.0] * 10, [0.0] * 12,
    [0.0, 0.0, 0.0, float("nan"), 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, float("inf"), 0.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, True, 0.0, 0.0],
    [0.0, 0.0, 0.0, "0.1", 0.0, 0.0],
])
def test_arc_callout_rejects_truncated_nonfinite_or_non_scalar_leaders(
    native_callout_record, monkeypatch, row,
):
    record = native_callout_record.dump()
    record["leaders"] = [row]
    monkeypatch.setattr(
        drawing, "annotation_geometry",
        lambda *_a, **_k: pytest.fail("malformed leader reached tolerant parser"),
    )
    with pytest.raises(ValueError, match="invalid native leader geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("reference", range(6))
@pytest.mark.parametrize("angle", [0.0, math.pi / 2, -math.pi])
def test_arc_callout_accepts_every_documented_text_reference_and_radian_angle(
    native_callout_record, reference, angle,
):
    record = native_callout_record.dump()
    record["display"]["texts"][0].update(ref=reference, ang=angle)
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


@pytest.mark.parametrize("width", [None, 0.0, 0.021])
def test_arc_callout_accepts_absent_or_nonnegative_optional_width(native_callout_record, width):
    record = native_callout_record.dump()
    if width is not None:
        record["display"]["texts"][0]["w"] = width
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


@pytest.mark.parametrize("field,value", [
    ("t", None), ("t", 17), ("t", lambda: "REAM"), ("t", " \n "),
    ("pos", []), ("pos", [0.08, 0.09]), ("pos", [0.08, 0.09, 0.0, 0.0]),
    ("pos", [0.08, float("nan"), 0.0]), ("pos", [0.08, True, 0.0]),
    ("pos", [0.08, "0.09", 0.0]),
    ("h", 0.0), ("h", -0.001), ("h", float("inf")), ("h", True), ("h", "0.0035"),
    ("ang", float("nan")), ("ang", True), ("ang", "0.0"),
    ("ref", -1), ("ref", 6), ("ref", 1.0), ("ref", True), ("ref", "1"),
    ("w", -0.001), ("w", float("nan")), ("w", float("inf")), ("w", True), ("w", "0.02"),
    ("ls", float("nan")), ("ls", float("inf")), ("ls", True), ("ls", "0.0"),
])
def test_arc_callout_rejects_invalid_text_fields_before_tolerant_parser(
    native_callout_record, monkeypatch, field, value,
):
    record = native_callout_record.dump()
    record["display"]["texts"][0][field] = value
    monkeypatch.setattr(
        drawing, "annotation_geometry",
        lambda *_a, **_k: pytest.fail("malformed text reached tolerant parser"),
    )
    with pytest.raises(ValueError, match="invalid native text geometry|missing native callout text"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("field", ["t", "pos", "h", "ang", "ref"])
def test_arc_callout_rejects_missing_required_text_fields(native_callout_record, field):
    record = native_callout_record.dump()
    del record["display"]["texts"][0][field]
    with pytest.raises(ValueError, match="invalid native text geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("position", [
    None, [], [0.0, 0.0], [0.0] * 4, [float("inf"), 0.0, 0.0],
    [0.0, True, 0.0], [0.0, "0.1", 0.0],
])
def test_arc_callout_rejects_invalid_annotation_position(native_callout_record, position):
    record = native_callout_record.dump()
    record["pos"] = position
    with pytest.raises(ValueError, match="invalid native GetPosition"):
        drawing._arc_callout_geometry(record, 0.62)


def test_arc_callout_preserves_native_null_rows_for_zero_counts(native_callout_record):
    case = native_callout_record
    for member in (
        "GetLineAtIndex3", "GetLineAtIndex2", "GetArcAtIndex2", "GetArrowHeadAtIndex2",
        "GetPolylineAtIndex2", "GetPolygonAtIndex", "GetTriangleAtIndex", "GetEllipseAtIndex2",
    ):
        setattr(case.data, member, lambda _index: None)
    case.annotation.GetLeaderPointsAtIndex = lambda _index: None
    record = case.dump()
    assert set(record["display"]) == {"texts"}
    assert "leaders" not in record
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


def test_arc_callout_preserves_documented_degenerate_primitive_rows(native_callout_record):
    record = native_callout_record.dump()
    record["display"]["lines"] = [_native_line(0.0, 0.0, 0.0, 0.0)]
    record["leaders"] = [[0.0] * 6]
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


@pytest.mark.parametrize("key", tuple(_NATIVE_CALLOUT_ROWS))
@pytest.mark.parametrize("row", [None, 3.0, "row", {}, [0.0, [0.0]]])
def test_arc_callout_rejects_non_array_or_nested_primitive_rows(native_callout_record, key, row):
    record = native_callout_record.dump()
    record["display"][key] = [row]
    with pytest.raises(ValueError, match=f"invalid native {key} geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.mark.parametrize("texts", [[], None, "REAM", {}, [None], [17], ["REAM"]])
def test_arc_callout_rejects_malformed_text_collection(native_callout_record, texts):
    record = native_callout_record.dump()
    record["display"]["texts"] = texts
    with pytest.raises(ValueError, match="missing native callout text|invalid native text geometry"):
        drawing._arc_callout_geometry(record, 0.62)


@pytest.fixture
def native_profile_clearance(monkeypatch):
    # Historical native records intentionally stay independent of R10 anchors.
    import _drawing_layout_audit

    monkeypatch.setattr(_drawing_layout_audit, "_early_bound", _bind_owner)
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)

    def frame(name, xy, points, width):
        x, y = xy
        corners = [(x, y), (x + width, y), (x + width, y - 0.007), (x, y - 0.007)]
        lines = [_native_line(*a, *b) for a, b in zip(corners, corners[1:] + corners[:1])]
        data = _ClearanceDisplayData(
            [{"t": "PROFILE", "pos": [x + 0.001, y - 0.004, 0.0], "h": 0.002}],
            lines,
        )
        return _ClearanceAnnotation(name, (*xy, 0.00125), data, leaders=[points])

    top = frame(
        "DetailTop", (0.114, 0.228),
        [0.114, 0.2245, 0.00125, 0.10765, 0.2245, 0.00125, 0.125, 0.179476, 0.000625],
        width=0.0512,
    )
    bottom = frame(
        "DetailBottom", (0.020, 0.129),
        [0.067339, 0.1255, 0.00125, 0.073689, 0.1255, 0.00125, *_R8_LOWER_LANDING, 0.000625],
        width=_R8_LOWER_FRAME_WIDTH_M,
    )
    ream = _ClearanceAnnotation(
        "PivotReam", (0.13005, 0.1462, 0),
        _ClearanceDisplayData(
            [{"t": "REAM +0.03", "pos": [0.104, 0.1444, 0], "h": 0.0036}],
            [_native_line(0.104, 0.1444, 0.1561, 0.1444)],
        ),
        kind=4,
    )
    # Synthetic native text runs reproduce R8's actual row bbox. Individual
    # run origins are fake data, not additional observations from the seat.
    r816 = _ClearanceAnnotation(
        "BasicR816", (0.0815, 0.1512, 0.00125),
        _ClearanceDisplayData(
            [
                {"t": "R", "pos": [0.0815, 0.1512, 0.00125], "h": 0.0035},
                {"t": "816.00", "pos": [0.09018, 0.1512, 0.00125], "h": 0.0035},
            ],
            [],
        ),
        kind=4, hole_callout=False,
    )
    annotations = [top, bottom, ream, r816]
    front = _native("IView", GetAnnotationCount=lambda: len(annotations), GetAnnotations=lambda: annotations)
    profiles = {
        "TopRadius": _native("IGtol", GetAnnotation=lambda: top),
        "BottomRadius": _native("IGtol", GetAnnotation=lambda: bottom),
    }
    return SimpleNamespace(
        adapter=object(), front=front, profiles=profiles, top=top, bottom=bottom,
        ream=ream, r816=r816, annotations=annotations, logs=logs,
    )


def test_native_profile_guard_logs_actual_position_frame_and_leaders(native_profile_clearance):
    case = native_profile_clearance
    case.bottom.position = (0.021, 0.130, 0.00125)  # request != native readback
    drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    text = "\n".join(case.logs)
    assert "requested_frame_mm=(197.0, 163.0)" in text
    assert "actual_GetPosition_mm=(21.0, 130.0, 1.25)" in text
    assert "native_frame_ink_bbox_mm=" in text
    assert "native_leader_points_mm=" in text
    assert "landing_mm=[(130.0, 170.752, 0.625)]" in text
    assert "minimum_clearance_mm=" in text
    assert "required_clearance_mm=1.000" in text
    assert "PivotReam" in text


@pytest.mark.parametrize("frame_request,junction", [
    ((0.112, 0.122), (0.1056, 0.1185)),
    ((0.040, 0.105), (0.0937, 0.1015)),
])
def test_native_profile_guard_refuses_observed_crossings(
    native_profile_clearance, monkeypatch, frame_request, junction,
):
    case = native_profile_clearance
    monkeypatch.setitem(drawing.ARC_PROFILE_FRAME_XY, "BottomRadius", frame_request)
    case.bottom.position = (*frame_request, 0)
    case.bottom.leaders = [[
        junction[0] - 0.003, junction[1], 0, *junction, 0, 0.130, 0.1708, 0,
    ]]
    with pytest.raises(RuntimeError) as exc:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    message = str(exc.value)
    for evidence in (
        "BottomRadius", "PivotReam", "requested_frame_mm=", "actual_GetPosition_mm=",
        "native_leader_points_mm=", "bbox_mm=[104.0,144.4]..[156.1,148.0]mm",
        "minimum_clearance_mm=0.000", "penetration_mm=", "native_segment=",
    ):
        assert evidence in message
    assert any("native_frame_ink_bbox_mm=" in log for log in case.logs)


def test_native_profile_guard_refuses_r8_basic_radius_crossing(
    native_profile_clearance, monkeypatch,
):
    case = native_profile_clearance
    monkeypatch.setitem(drawing.ARC_PROFILE_FRAME_XY, "BottomRadius", (0.020, 0.134))
    case.bottom.position = (0.020, 0.134, 0.00125)
    case.bottom.leaders = [[
        0.067339, 0.1305, 0.00125, 0.073689, 0.1305, 0.00125,
        *_R8_LOWER_LANDING, 0.000625,
    ]]
    for line in case.bottom.data.lines:
        line[5] += 0.005
        line[8] += 0.005
    case.bottom.data.texts[0]["pos"][1] += 0.005
    with pytest.raises(RuntimeError) as exc:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    message = str(exc.value)
    for evidence in (
        "requested_frame_mm=(20.0, 134.0)", "actual_GetPosition_mm=(20.0, 134.0, 1.25)",
        "BasicR816", "bbox_mm=[81.5,151.2]..[103.2,154.7]mm",
        "minimum_clearance_mm=0.000", "penetration_mm=",
        "native_frame_ink_bbox_mm=[20.0,127.0]..[67.3,134.0]mm",
    ):
        assert evidence in message


@pytest.mark.parametrize("gap,passes", [(0.001, True), (0.000999, False), (0.001001, True)])
def test_native_profile_guard_enforces_one_mm_minimum(native_profile_clearance, gap, passes):
    case = native_profile_clearance
    # Horizontal native route below a real foreign callout: no intersection.
    y = 0.1444 - gap
    case.bottom.leaders = [[0.100, y, 0, 0.103, y, 0, 0.160, y, 0]]
    if passes:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    else:
        with pytest.raises(RuntimeError, match="minimum_clearance_mm=0.999"):
            drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    assert any("penetration_mm=0.000" in log for log in case.logs)


def test_native_profile_guard_checks_non_ream_foreign_callout(native_profile_clearance):
    case = native_profile_clearance
    case.ream.name = "NativeRodCallout"
    case.ream.data.texts = [{"t": "DRILL", "pos": [0.108, 0.156, 0], "h": 0.003}]
    case.ream.data.lines = [_native_line(0.108, 0.156, 0.125, 0.156)]
    with pytest.raises(RuntimeError, match="NativeRodCallout"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


@pytest.mark.parametrize("defect", [
    "missing-frame", "missing-annotation", "empty-view", "refused-view",
    "missing-leader", "refused-leader", "short-leader", "nonfinite-leader",
    "zero-segment", "missing-position", "invalid-position", "missing-frame-lines",
    "missing-other-text", "invalid-other-height", "invalid-other-position",
    "unknown-other-anchor", "invalid-other-line", "refused-other-display",
    "refused-position", "wrong-frame-kind", "wrong-frame-owner", "hidden-frame",
    "duplicate-frame-name", "zero-frame-lines",
])
def test_native_profile_guard_fails_closed(native_profile_clearance, defect):
    case = native_profile_clearance
    if defect == "missing-frame":
        del case.profiles["BottomRadius"]
    elif defect == "missing-annotation":
        case.profiles["BottomRadius"].GetAnnotation = lambda: None
    elif defect == "empty-view":
        case.front.GetAnnotations = lambda: []
        case.front.GetAnnotationCount = lambda: 0
    elif defect == "refused-view":
        case.front.GetAnnotations = lambda: None
    elif defect == "missing-leader":
        case.bottom.leaders = []
    elif defect == "refused-leader":
        case.bottom.GetLeaderPointsAtIndex = lambda _index: None
    elif defect == "short-leader":
        case.bottom.leaders = [[0.02, 0.129, 0, 0.03]]
    elif defect == "nonfinite-leader":
        case.bottom.leaders[0][3] = float("nan")
    elif defect == "zero-segment":
        case.bottom.leaders[0][:3] = case.bottom.leaders[0][3:6]
    elif defect == "missing-position":
        case.bottom.position = None
    elif defect == "invalid-position":
        case.bottom.position = (float("inf"), 0.129, 0)
    elif defect == "missing-frame-lines":
        case.bottom.data.lines = []
    elif defect == "missing-other-text":
        case.ream.data.texts = []
    elif defect == "invalid-other-height":
        case.ream.data.texts[0]["h"] = 0.0
    elif defect == "invalid-other-position":
        case.ream.data.texts[0]["pos"] = [float("nan"), 0.1444, 0]
    elif defect == "unknown-other-anchor":
        case.ream.data.texts[0]["ref"] = -1
    elif defect == "invalid-other-line":
        case.ream.data.lines = [[1, 2]]
    elif defect == "refused-other-display":
        case.ream.GetDisplayData = lambda: None
    elif defect == "refused-position":
        def refused_position():
            raise RuntimeError("native COM refused GetPosition")
        case.bottom.GetPosition = refused_position
    elif defect == "wrong-frame-kind":
        case.bottom.kind = 7
    elif defect == "wrong-frame-owner":
        case.bottom.OwnerType = 1
    elif defect == "hidden-frame":
        case.bottom.Visible = 3
    elif defect == "duplicate-frame-name":
        case.bottom.name = case.top.name
    elif defect == "zero-frame-lines":
        case.bottom.data.lines = [_native_line(0.020, 0.129, 0.020, 0.129)]
    # Count/array disagreement refuses before individual frame records exist.
    expected = ("arc profile front annotations: native annotation count 4 returned no annotation array"
                if defect == "refused-view" else "rocker arc-profile native clearance failed")
    with pytest.raises(RuntimeError, match=expected) as exc:
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    if defect != "refused-view":
        assert "BottomRadius" in str(exc.value)
    assert case.logs or defect in ("empty-view", "refused-view")


def test_native_profile_guard_excludes_only_its_own_frame_text(native_profile_clearance):
    case = native_profile_clearance
    case.bottom.data.texts[0]["pos"] = [0.067339, 0.1255, 0]
    drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    case.bottom.leaders = [[0.110, 0.224, 0, 0.113, 0.224, 0, 0.130, 0.224, 0]]
    with pytest.raises(RuntimeError, match="DetailTop"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


@pytest.mark.parametrize("read,answer", [
    ("GetName", ""),
    ("GetName", lambda: "method-shaped answer"),
    ("GetPosition", [0.02, 0.129]),
    ("GetLeaderCount", -1),
])
def test_native_profile_guard_refuses_invalid_native_scalar_contracts(
    native_profile_clearance, read, answer,
):
    case = native_profile_clearance
    setattr(case.bottom, read, lambda: answer)
    with pytest.raises(RuntimeError, match="rocker arc-profile native clearance failed"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


def test_native_profile_guard_is_after_rebuild_and_before_export() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [
        (node.func.id, node.lineno)
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    guard = next(line for name, line in calls if name == "_require_arc_profile_clearance")
    layout = next(line for name, line in calls if name == "check_drawing_layout")
    export = next(line for name, line in calls if name == "finalize_drawing")
    assert max(line for name, line in calls if name == "rebuild_drawing") < guard < layout < export


def test_profile_zone_mirror_station_envelopes_and_template_aim() -> None:
    """Only at the mirror station is the arc normal vertical. These limits
    do not assert a rigid vertical offset of the curve at its ends."""
    centre = rocker_interface.CENTER_Y
    assert (ch_rocker_arm_spec.R_TOP, rocker_interface.R_BOTTOM) == (800.0, 816.0)
    nominal_top = centre - ch_rocker_arm_spec.R_TOP - rocker_interface.PIVOT_MID_Y
    nominal_bottom = centre - rocker_interface.R_BOTTOM
    assert nominal_top == pytest.approx(8.0)
    assert nominal_bottom == pytest.approx(0.0)
    assert drawing.TOP_EDGE_BAND is ch_rocker_arm_spec.TOP_EDGE_BAND
    assert drawing.ARC_PROFILE_ZONE_MM == f"{ch_rocker_arm_spec.TOP_EDGE_BAND[0]:g}"
    assert drawing.ARC_PROFILE_OUTSIDE_MM == {
        "TopRadius": drawing.ARC_PROFILE_ZONE_MM,
        "BottomRadius": f"{ch_rocker_arm_spec.TOP_EDGE_BAND[1]:g}",
    }
    zone = float(drawing.ARC_PROFILE_ZONE_MM)
    top_outside = float(drawing.ARC_PROFILE_OUTSIDE_MM["TopRadius"])
    bottom_inside = zone - float(drawing.ARC_PROFILE_OUTSIDE_MM["BottomRadius"])
    assert zone == top_outside == bottom_inside == 0.508
    assert (nominal_top, nominal_top + top_outside) == pytest.approx((8.0, 8.508))
    assert (nominal_bottom, nominal_bottom + bottom_inside) == pytest.approx((0.0, 0.508))
    template_aim = nominal_top + zone / 2.0
    assert template_aim == pytest.approx(8.254)
    # The printed frames read the same zone in inch.
    assert drawing.ARC_PROFILE_ZONE_TEXT == ".020"
    assert drawing.ARC_PROFILE_OUTSIDE_TEXT == {"TopRadius": ".020", "BottomRadius": "0"}



def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-rocker-arm")
    assert spec["material_specification"] == "AISI 1018 low-carbon steel"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = ch_rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == ch_rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == ch_rocker_arm_spec.PIVOT_HOLE_DIA
    part_source = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bore")' in sheet_source
    )
    assert "roughness_ra=" not in sheet_source


def test_every_view_keep_map_is_curated_on_its_own_view() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRk__): RIGHT_KEEP promised HubLength but
    build() curated only the front view, so the hub length never printed. Each
    non-empty <VIEW>_KEEP must be curated on that view, and curation fails
    loud on a missing kept dimension, so the print carries every one."""

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    curated = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "curate_view_dimensions"
        ):
            continue
        keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
        curated[keywords["keep"]] = (ast.unparse(node.args[1]), keywords)
    for keep_name, view in (
        ("FRONT_KEEP", "front"),
        ("RIGHT_KEEP", "right"),
        ("HUB_KEEP", "hub"),
        ("END_KEEP", "end"),
    ):
        if not getattr(drawing, keep_name):
            continue
        assert keep_name in curated, keep_name
        assert curated[keep_name][0] == view
    # Both views import by feature: only Hub's dimensions arrive in the end
    # view, only the pivot bore's in the front (r743-3: the front's
    # entire-model fallback warned on the leaf).
    assert curated["RIGHT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert curated["FRONT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert drawing.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS


def test_hub_length_prints_its_one_sided_band() -> None:
    """#743 PR2: the hubs are a solid stack whose north end is the rocker
    bank's datum, so each hub may only come out long and the print says so
    natively; rocker_bank_layout's L20 acceptance caps the sum."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Hub"] == {"HubLength"}
    assert "HubLength" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(arm)[("Hub", "HubLength")] == (
        "*deviations(HUB_LENGTH_BAND)"
    )
    assert ch_rocker_arm_spec.HUB_LENGTH_BAND == (0.0508, 0.0)
    assert f"{ch_rocker_arm_spec.HUB_LENGTH:.2f}" not in ch_rocker_arm_notes.DRAWING_NOTES


def test_strap_thickness_prints_its_band_natively() -> None:
    """Main ruling 2026-10, option b: each inter-arm gap holds one tine of
    each neighbouring rod fork, so the strap prints 2.500 +/-0.025 at three
    places on the Strap extrude's own depth (drawing-simplicity-policy.md `How the repository implements the guidelines`), selected by
    feature and dimension name in the end view, and no note repeats it."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_spec.ARM_THICKNESS_BAND == (0.0254, -0.0254)
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Strap"] == {"StrapThickness"}
    assert ch_rocker_arm_notes.DRAWING_PRECISION["Strap"]["StrapThickness"] == 3
    assert "StrapThickness" in drawing.RIGHT_KEEP
    assert "StrapThickness" not in drawing.FRONT_KEEP
    assert model_toleranced_dimensions(arm)[("Strap", "StrapThickness")] == "strap_upper"
    build = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert 'name_dimensions(adapter,"Strap",["StrapThickness"])' in build
    assert "strap_lower,strap_upper=deviations(ARM_THICKNESS_BAND)" in build
    assert "(strap_thickness_dim[0],'\"ArmThickness\"')" in build
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ALL HOLES THRU" not in joined
    assert "STRAP 2.50" not in joined
    assert "THICK" not in joined
    assert "GROUND" not in joined  # the strap faces are milled (plan op 20)


def _callout_block(xy: tuple[float, float], callout: str) -> Box:
    """Predicted native block: value row plus below-text rows, centred on the request."""
    rows = [""] + callout.splitlines()
    half_w = max(len(row) for row in rows) * CAPTION_CHAR_WIDTH / 2.0
    half_h = (len(rows) - 1) * RENDERED_ROW_PITCH / 2.0 + 0.00175
    return Box(xy[0] - half_w, xy[1] - half_h, xy[0] + half_w, xy[1] + half_h)


def test_view_f_size_blocks_stand_left_of_the_view_on_the_strap_and_under_it() -> None:
    """Opus #1020 r2 C3: the 2.500 line crosses the strap alone, not the hub;
    the hub width's line runs under the view."""
    assert drawing.RIGHT_KEEP == {
        "HubLength": drawing.HUB_LENGTH_TEXT_XY,
        "StrapThickness": drawing.STRAP_THICKNESS_TEXT_XY,
        "HubRootRadius": drawing.HUB_ROOT_TEXT_XY,
    }
    strap = _callout_block(drawing.STRAP_THICKNESS_TEXT_XY, ch_rocker_arm_notes.STRAP_FIT_CALLOUT)
    hub = _callout_block(drawing.HUB_LENGTH_TEXT_XY, drawing.HUB_LENGTH_TEXT)
    hub_end_x, _ = _view_f_xy(ch_rocker_arm_spec.HUB_LENGTH / 2.0, 0.0)
    strap_left_x, _ = _view_f_xy(ch_rocker_arm_spec.ARM_THICKNESS / 2.0, 0.0)
    _, view_bottom = _view_f_xy(0.0, 0.0)
    _, view_top = _view_f_xy(0.0, ch_rocker_arm_spec.TOP_END_Y)
    _, hub_top = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y + ch_rocker_arm_spec.HUB_DIA / 2.0)
    for block in (strap, hub):
        assert block.xmin - DRAWABLE.xmin >= 0.005
    # Each block clears the ink level with it: the strap's (above the hub)
    # only the strap face, the hub width's the hub end.
    assert strap_left_x - strap.xmax >= 0.002
    assert hub_end_x - hub.xmax >= 0.002
    # Native runs each dimension line along the block's bottom: the strap's
    # crosses the strap above the hub, the hub width's runs under the view.
    assert strap.ymin - hub_top >= 0.010
    assert strap.ymin < view_top
    assert hub.ymin < view_bottom
    assert strap.ymin - hub.ymax >= 0.020
    # The hub-root radius reads left of the view between the two blocks: under
    # the strap's position frame (one ~5 mm row under its line), over the hub
    # block and the hub top, and left of the hub end, so its leader runs
    # short down-right to the +Z root corner it measures, crossing no part.
    root_x, root_y = drawing.HUB_ROOT_TEXT_XY
    root_text = f"{ch_rocker_arm_notes.HUB_ROOT_PREFIX}{ch_rocker_arm_spec.HUB_ROOT_RADIUS_MAX:.1f} MAX"
    half_w = len(root_text) * CAPTION_CHAR_WIDTH / 2.0
    root = Box(root_x - half_w, root_y - 0.00175, root_x + half_w, root_y + 0.00175)
    assert root.xmin - DRAWABLE.xmin >= 0.005
    assert hub_end_x - root.xmax >= 0.002
    assert (strap.ymin - 0.005) - root.ymax >= 0.003
    assert root.ymin - hub.ymax >= 0.010
    assert hub_top < root.ymin


def test_right_view_caption_sits_under_view_f_clear_of_the_hub_width() -> None:
    caption = ch_rocker_arm_notes.RIGHT_VIEW_NOTE
    left, top = drawing.RIGHT_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    assert left > DRAWABLE.xmin
    # Under the view, its row spanning the view's centre line.
    assert left < drawing.RIGHT_CENTER[0] < right
    hub = _callout_block(drawing.HUB_LENGTH_TEXT_XY, drawing.HUB_LENGTH_TEXT)
    # The caption reads well under the hub width's line.
    assert hub.ymin - top >= 0.020
    # Inside the bottom border.
    assert top - 0.0035 > BORDER_BOTTOM


def test_datum_g_and_its_basic_stand_right_of_the_hub_minus_z_face() -> None:
    """#1579 option 1: G's box out right of the -Z face's lower half, the
    BASIC's boxed text out right above the hub, both short of the front
    view's 132.8 left witness and clear of each other."""
    spec = ch_rocker_arm_spec
    face_x, landing_y = _view_f_xy(
        -spec.HUB_LENGTH / 2.0, drawing.HUB_FACE_DATUM_LANDING_Y_MM
    )
    _, hub_bottom = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y - spec.HUB_DIA / 2.0)
    _, pivot = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y)
    _, hub_top = _view_f_xy(0.0, rocker_interface.PIVOT_MID_Y + spec.HUB_DIA / 2.0)
    assert hub_bottom < landing_y < pivot
    witness = drawing.FRONT_LEFT_WITNESS_X - drawing.ARROW_TEXT_CLEARANCE_M
    # The tag's box (~7 mm) leads straight out right from its landing.
    g_left = face_x + drawing.HUB_FACE_DATUM_STANDOFF_M
    g = Box(g_left, landing_y - 0.0035, g_left + 0.007, landing_y + 0.0035)
    assert g.xmin - face_x >= 0.005
    assert g.xmax <= witness
    # The BASIC's text, centred on its request, clears the face's extension
    # line, the witness, the hub top and G.
    places = drawing.HUB_FACES.precision["length"]
    text = ch_rocker_arm_spec.inch_text(drawing.HUB_FACE_BASIC_MM, places)
    text_x, text_y = drawing.HUB_FACE_BASIC_TEXT_XY
    half_w = len(text) * CAPTION_CHAR_WIDTH / 2.0
    basic = Box(text_x - half_w, text_y - 0.00175, text_x + half_w, text_y + 0.00175)
    assert basic.xmin - face_x >= drawing.ARROW_TEXT_CLEARANCE_M
    assert basic.xmax <= witness
    assert basic.ymin - hub_top >= 0.005
    assert basic.ymin - g.ymax >= 0.020


def test_top_edge_model_band_is_unchanged_by_the_basic_drawing_override() -> None:
    """The source keeps its existing height band and centre equation; the
    drawing's imported height is BASIC and governed by surface profile."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = ch_rocker_arm_spec.TOP_EDGE_BAND
    assert lower == 0.0 < upper == 0.508
    assert ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT == pytest.approx(8.0)
    assert not hasattr(ch_rocker_arm_notes, "TOP_EDGE_BAND")
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["TopEdgeReference"] == {"TopAbovePivot"}
    assert model_toleranced_dimensions(arm)[("TopEdgeReference", "TopAbovePivot")] == (
        "*deviations(TOP_EDGE_BAND)"
    )
    assert "TopAbovePivot" in drawing.FRONT_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ABOVE THE PIVOT" not in joined
    assert f"+{upper:.2f}/0" not in joined
    build = Path(arm.__file__).read_text(encoding="utf-8")
    # The source centre remains an equation of the model height; the drawing
    # override changes presentation, not the source geometry or its band.
    assert '"ArmDepth" / 2 + "TopAbovePivot" + "CurveRadius"' in build
    assert ch_rocker_arm_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"] == 3


def test_pivot_bore_ream_band_rides_its_diameter_not_a_note() -> None:
    """Codex #936 sweep (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): note 6 printed "REAM +0.03/0, Ra
    1.6" while the O6.50 printed bare. The band is now native on PivotDia and
    the Ra is the bore's own symbol; the note keeps only REAM."""
    from _drawing_contract import model_toleranced_dimensions

    assert model_toleranced_dimensions(arm)[("PivotHoleProfile", "PivotDia")] == (
        "*deviations(PIVOT_HOLE_BAND)"
    )
    assert "PivotDia" in drawing.HUB_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "+0.03" not in joined
    assert "Ra 1.6" not in joined
    assert any(
        control.key == "pivot_bore" for control in ch_rocker_arm_spec.SURFACE_FINISHES
    )


def test_no_rocker_note_carries_a_tolerance_band() -> None:
    """No size/profile band is duplicated in prose. Hub coaxiality remains
    a plain note by Main's ruling (2026-09-26)."""
    for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines():
        if "COAXIAL" in line or "WITHIN" in line:
            continue
        assert not re.search(r"\+\d|[-+]0\.\d+/|±|\+/-", line), line


def test_top_edge_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880 / #950: a reference sketch owns a printed dimension but no
    # geometry, so the part saves it hidden (no assembly instance renders it)
    # and the drawing shows it per view through _drawing_hidden_sketches.
    build = Path(arm.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "TopEdgeReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source


def _tip_angle_reference_case(monkeypatch, *, defect=None):
    """Real carrier and angular helper over a SolidWorks-free native boundary."""
    import _drawing_dimension_insert
    from solidworks_mcp.adapters import sw_type_info

    selected, relations, lengths, native_calls = [], [], [], []

    def result(data=True, *, success=True):
        return SimpleNamespace(is_success=success, data=data, error="native refusal")

    class SketchLine:
        _native_interfaces = ("ISketchSegment",)

        def __init__(self, start, end):
            self.start, self.end = start, end
            self.construction = False

        @property
        def ConstructionGeometry(self):
            return self.construction

        @ConstructionGeometry.setter
        def ConstructionGeometry(self, value):
            if defect != "construction":
                self.construction = value

        def Select4(self, append, data):
            assert append and data.Mark == 0
            selected.append(self)
            return True

    class ModelDimension:
        _native_interfaces = ("IDimension",)
        SystemValue = 0.0
        driven = 0

        @property
        def DrivenState(self):
            return self.driven

        @DrivenState.setter
        def DrivenState(self, value):
            if defect != "driven":
                self.driven = value

    dimension = ModelDimension()
    display = _native(
        "IDisplayDimension", GetDimension2=lambda index: dimension,
        SupplementaryAngle=lambda: False,
        SetText=lambda *_args: pytest.fail("model angle must not override its value"),
    )

    def add_specific(x, y, z, kind, error):
        assert kind == 3 and z == 0.0 and error == 0
        native_calls.append((tuple(selected), (x, y)))
        first, second = selected
        a = (first.end[0] - first.start[0], first.end[1] - first.start[1])
        b = (second.end[0] - second.start[0], second.end[1] - second.start[1])
        cosine = sum(u * v for u, v in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))
        dimension.SystemValue = math.acos(max(-1.0, min(1.0, cosine)))
        if defect == "value":
            dimension.SystemValue += 0.01
        return (None if defect == "creation" else display), 0

    class Adapter:
        currentSketchManager = SimpleNamespace(AddToDB=False)

        def __init__(self):
            start = (arm.TOP_END_X, arm.TOP_END_Y)
            end = (
                start[0] + arm.TIP_FACE * math.sin(arm._ALPHA_TOP),
                start[1] - arm.TIP_FACE * math.cos(arm._ALPHA_TOP),
            )
            self._sketch_entities = {"real-land": SketchLine(start, end)}
            self.currentModel = _native(
                "IModelDoc2", ClearSelection2=lambda _all: selected.clear(),
                SelectionManager=_native(
                    "ISelectionMgr", CreateSelectData=lambda: SimpleNamespace(Mark=None),
                ),
                Extension=_native("IModelDocExtension", AddSpecificDimension=add_specific),
            )

        def _attempt(self, fn, default=None):
            return fn()

        async def add_line(self, x1, y1, x2, y2):
            assert self.currentSketchManager.AddToDB
            self._sketch_entities["vertical"] = SketchLine((x1, y1), (x2, y2))
            return result("vertical")

        async def add_sketch_constraint(self, *args):
            relations.append(args)
            return result(success=defect != "relation")

        async def add_sketch_dimension(self, *args):
            lengths.append(args)
            return result("length")

    monkeypatch.setattr(arm, "_early_bound", _bind_owner)
    monkeypatch.setattr(_drawing_dimension_insert, "_early_bound", _bind_owner)
    monkeypatch.setattr(sw_type_info, "early_bound", _bind_owner)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    return SimpleNamespace(
        adapter=Adapter(), dims=arm.SketchDims(), dimension=dimension,
        relations=relations, lengths=lengths, native_calls=native_calls,
    )


@pytest.mark.parametrize("alpha", [ch_rocker_arm_spec._ALPHA_TOP, 0.24])
def test_tip_angle_measures_real_radial_land_from_vertical_without_driving_it(monkeypatch, alpha):
    import asyncio

    monkeypatch.setattr(arm, "_ALPHA_TOP", alpha)
    monkeypatch.setattr(arm, "TOP_END_X", arm.R_TOP * math.sin(alpha))
    monkeypatch.setattr(arm, "TOP_END_Y", arm.CENTER_Y - arm.R_TOP * math.cos(alpha))
    case = _tip_angle_reference_case(monkeypatch)
    land = case.adapter._sketch_entities["real-land"]
    original = (land.start, land.end)
    asyncio.run(arm._tip_land_angle_reference(case.adapter, "real-land", case.dims))
    vertical = case.adapter._sketch_entities["vertical"]
    assert (land.start, land.end) == original
    assert not land.ConstructionGeometry and vertical.ConstructionGeometry
    assert vertical.start == land.start
    assert vertical.end == (land.start[0], land.start[1] - arm.TIP_FACE)
    assert case.relations == [
        ("vertical.start", "real-land.start", "coincident"),
        ("vertical", None, "vertical"),
    ]
    assert case.lengths == [
        ("vertical.start", "vertical.end", "vertical_distance", arm.TIP_FACE),
    ]
    assert case.dims._rows == [
        ("TipLandVerticalLength", '"TipFaceLen"'), ("TipLandAngle", None),
    ]
    assert case.native_calls[0][0] == (vertical, land)
    assert case.dimension.SystemValue == pytest.approx(alpha)
    assert case.dimension.DrivenState == 1
    assert case.adapter.currentSketchManager.AddToDB is False


@pytest.mark.parametrize("defect", ["construction", "relation", "creation", "driven", "value"])
def test_tip_angle_carrier_rejects_native_authoring_refusals(monkeypatch, defect):
    import asyncio

    case = _tip_angle_reference_case(monkeypatch, defect=defect)
    with pytest.raises(RuntimeError):
        asyncio.run(arm._tip_land_angle_reference(case.adapter, "real-land", case.dims))


def test_tip_angle_is_recorded_before_the_unchanged_profile_definition_and_extrusion():
    tree = ast.parse(Path(arm.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    angle = next(node for node in calls if isinstance(node.func, ast.Name)
                 and node.func.id == "_tip_land_angle_reference")
    defined = next(node for node in calls if isinstance(node.func, ast.Name)
                   and node.func.id == "ensure_fully_defined"
                   and ast.literal_eval(node.args[1]) == "strap sketch")
    extrusion = next(node for node in calls if isinstance(node.func, ast.Attribute)
                     and node.func.attr == "create_extrusion")
    assert [ast.unparse(arg) for arg in angle.args] == ["adapter", "rod_tip_line", "strap"]
    assert angle.lineno < defined.lineno < extrusion.lineno
    assert arm._ALPHA_TOP == pytest.approx(ch_rocker_arm_spec._ALPHA_TOP)
    land_angle = math.atan2(
        ch_rocker_arm_spec.ROD_TIP_X - ch_rocker_arm_spec.TOP_END_X,
        ch_rocker_arm_spec.TIP_FACE * math.cos(ch_rocker_arm_spec._ALPHA_TOP),
    )
    assert land_angle == pytest.approx(arm._ALPHA_TOP)


def test_top_basic_height_is_off_the_pin_x_witness() -> None:
    assert drawing.FRONT_KEEP["TopAbovePivot"] == (0.165, 0.191)
    assert drawing.FRONT_KEEP["TopAbovePivot"][0] != drawing.FRONT_CENTER[0]
    assert drawing.PIN_X_TEXT_XY[1] == 0.197
    assert drawing.TAPER_INTERSECTION_TEXT_XY[1] == 0.137
    land_rows = max(
        drawing.LAND_LOCATION_TEXT_XY[1], drawing.LEFT_LAND_LOCATION_TEXT_XY[1]
    )
    assert drawing.OVERALL_WIDTH_TEXT_XY[1] > land_rows + RENDERED_ROW_PITCH
    assert drawing.OVERALL_WIDTH_TEXT_XY[1] + 0.0035 < DRAWABLE.ymax


_PIVOT_CENTRE = drawing.HUB_CENTER
_DETAIL_BORE_R = ch_rocker_arm_spec.PIVOT_HOLE_DIA / 2000.0 * (
    drawing.HUB_SCALE[0] / drawing.HUB_SCALE[1]
)


class _Tag:
    _native_interfaces = ("IDatumTag",)
    def __init__(self, attached: tuple, dangling: bool = False) -> None:
        self.annotation = _native("IAnnotation", GetAttachedEntities3=lambda: attached, IsDangling=lambda: dangling,)

    def GetAnnotation(self) -> SimpleNamespace:
        return self.annotation


_BORE, _HUB = object(), object()
_APP = _native("ISldWorks", IsSame=lambda a, b: 1 if a is b else 0)


@pytest.fixture
def bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass native wrapping for offline logic only, not native-binding proof."""
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(detail_crop, "_early_bound", _bind_owner)
    import _drawing_layout_audit

    monkeypatch.setattr(_drawing_layout_audit, "_early_bound", _bind_owner)
    # Caption refusals must never probe this host's real seat in an offline test.
    def capture(_adapter, _label, _message, *, exception, **_context):
        raise exception
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)


@pytest.fixture
def pivot_precision_bound(monkeypatch: pytest.MonkeyPatch, bound: None) -> None:
    """Keep shared dimension-name lookup offline with explicit native owners."""
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)


class _PrecisionAdapter:
    @staticmethod
    def _attempt(operation, default=None):
        try:
            return operation()
        except Exception:
            return default

    def _get_attr_or_call(self, obj, name):
        member = self._attempt(lambda: getattr(obj, name))
        return self._attempt(member) if callable(member) else member


class _PrecisionDisplay:
    _native_interfaces = ("IDisplayDimension",)

    def __init__(self, primary, name="PivotDia") -> None:
        self.primary = primary
        self.dimension = _native("IDimension", Name=name)

    def GetDimension(self):
        return self.dimension

    def GetPrimaryPrecision2(self):
        return self.primary


class _PrecisionAnnotation:
    _native_interfaces = ("IAnnotation",)

    def __init__(self, display) -> None:
        self.display = display

    def GetSpecificAnnotation(self):
        return self.display


class _PrecisionExtension:
    _native_interfaces = ("IModelDocExtension",)

    def __init__(self, precision) -> None:
        self.precision = precision
        self.calls: list[tuple[int, int]] = []

    def GetUserPreferenceInteger(self, preference: int, option: int):
        self.calls.append((preference, option))
        return self.precision


_PIVOT_P = drawing.PIVOT_BORE.precision["dia"]


def _pivot_precision_case(primary, document_precision=_PIVOT_P, name="PivotDia"):
    """Method-shaped scalar getters model the typelib, not a live COM binding."""
    display = _PrecisionDisplay(primary, name)
    annotation = _PrecisionAnnotation(display)
    extension = _PrecisionExtension(document_precision)
    model = _native("IModelDoc2", Extension=extension)
    return _PrecisionAdapter(), model, annotation, extension


@pytest.mark.parametrize("primary", [_PIVOT_P, -2], ids=["explicit", "inherited"])
def test_pivot_precision_matching_places_passes(pivot_precision_bound: None, primary) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(primary)
    drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if primary == -2 else [])


@pytest.mark.parametrize("primary", [3, -2], ids=["explicit", "inherited"])
def test_pivot_precision_three_places_fails(pivot_precision_bound: None, primary) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(primary, 3)
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*effective 3"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if primary == -2 else [])


@pytest.mark.parametrize(
    ("primary", "document_precision", "calls"),
    [
        (None, _PIVOT_P, []),
        (-2, None, [(24, 204)]),
        (-2, -2, [(24, 204)]),
    ],
    ids=["raw-missing", "document-missing", "document-still-sentinel"],
)
def test_pivot_precision_missing_readback_fails(
    pivot_precision_bound: None, primary, document_precision, calls
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        primary, document_precision
    )
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == calls


@pytest.mark.parametrize("inherited", [False, True], ids=["raw", "document"])
@pytest.mark.parametrize(
    "unreadable",
    [True, 2.0, "2", Mock(), _PrecisionDisplay(2).GetPrimaryPrecision2],
    ids=["bool", "float", "string", "mock", "bound-method"],
)
def test_pivot_precision_never_coerces_unreadable_values(
    pivot_precision_bound: None, inherited: bool, unreadable
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        -2 if inherited else unreadable, unreadable
    )
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if inherited else [])


@pytest.mark.parametrize("empty", [True, False], ids=["empty", "other-dimension"])
def test_pivot_precision_missing_dimension_fails(pivot_precision_bound: None, empty: bool) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        _PIVOT_P, name="TopAbovePivot"
    )
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*missing dimension"):
        drawing._assert_pivot_precision(adapter, model, [] if empty else [annotation])
    assert extension.calls == []


@pytest.mark.parametrize("stage", ["annotation", "dimension", "primary", "document"])
def test_pivot_precision_getter_exceptions_fail_closed(
    pivot_precision_bound: None, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(-2)

    def fail(*_args):
        raise RuntimeError("native getter failed")

    target, member = {
        "annotation": (annotation, "GetSpecificAnnotation"),
        "dimension": (annotation.display, "GetDimension"),
        "primary": (annotation.display, "GetPrimaryPrecision2"),
        "document": (extension, "GetUserPreferenceInteger"),
    }[stage]
    monkeypatch.setattr(target, member, fail)
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])


@pytest.mark.parametrize("stage", ["display", "dimension", "name", "extension"])
def test_pivot_precision_unavailable_native_state_fails_closed(
    pivot_precision_bound: None, stage: str
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(-2)
    if stage == "display":
        annotation.display = None
    elif stage == "dimension":
        annotation.display.dimension = None
    elif stage == "name":
        annotation.display.dimension.Name = None
    else:
        model.Extension = None
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == []


@pytest.mark.parametrize(
    "interface",
    ["IAnnotation", "IDisplayDimension", "IModelDoc2", "IModelDocExtension"],
)
def test_pivot_precision_binding_failures_fail_closed(
    pivot_precision_bound: None, monkeypatch: pytest.MonkeyPatch, interface: str
) -> None:
    adapter, model, annotation, _extension = _pivot_precision_case(-2)

    def bind(obj, requested):
        if requested == interface:
            raise RuntimeError("native binding unavailable")
        return obj

    monkeypatch.setattr(drawing, "_early_bound", bind)
    with pytest.raises(RuntimeError, match=f"PivotDia.*expected {_PIVOT_P}.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])


def test_build_keeps_pivot_out_of_strict_part_precision() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    strict_call = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "assert_imported_precision"
    )
    precision = dict(zip(
        (ast.literal_eval(key) for key in strict_call.args[2].keys),
        (ast.unparse(value) for value in strict_call.args[2].values),
    ))
    assert set(precision) == {
        "TopAbovePivot",
        "HubLength",
        "StrapThickness",
        "HubRootRadius",
        "TipLandAngle",
    }
    # The hub-root single limit prints the part's places ("R.008 MAX").
    assert precision["HubRootRadius"] == (
        "rocker_notes.DRAWING_PRECISION['HubRoot']['HubRootRadius']"
    )
    assert precision["TipLandAngle"] == (
        "rocker_notes.DRAWING_PRECISION['StrapProfile']['TipLandAngle']"
    )
    front_import = next(
        node for node in build.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_add_rocker_outline_dimensions"
    )
    assert isinstance(front_import.targets[0], ast.Tuple)
    assert front_import.targets[0].elts[0].id == "front_annotations"
    imported = next(
        node.value for node in build.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "imported_annotations" for target in node.targets)
    )
    assert [item.value.id for item in imported.elts] == [
        "front_annotations", "hub_annotations", "end_annotations", "right_annotations",
    ]


def test_datum_a_attached_to_the_bore_passes(bound: None) -> None:
    drawing._require_datum_on_bore(_APP, _Tag((_BORE,)), _BORE)


def test_datum_a_refuses_null_native_annotation(bound: None) -> None:
    tag = _Tag((_BORE,))
    tag.annotation = None
    with pytest.raises(RuntimeError, match="datum A has no native annotation"):
        drawing._require_datum_on_bore(_APP, tag, _BORE)


@pytest.mark.parametrize(
    ("attached", "dangling", "match"),
    [
        ((_HUB,), False, "other than the O6.5 pivot bore"),
        ((), False, "has 0"),
        ((_BORE, _HUB), False, "has 2"),
        ((_BORE,), True, "dangling"),
    ],
)
def test_datum_a_off_the_bore_fails(
    bound: None, attached: tuple, dangling: bool, match: str
) -> None:
    """r743-4D: the rim pick attached datum A to the concentric O10 hub,
    which changes what the A-B-C frame controls."""
    with pytest.raises(RuntimeError, match=match):
        drawing._require_datum_on_bore(_APP, _Tag(attached, dangling), _BORE)


def _picker(monkeypatch: pytest.MonkeyPatch, resolve) -> list:
    """Route each EDGE pick through ``resolve(fraction of the bore radius)``."""
    picks: list = []

    def select(_adapter, _view, entity_type, xy, *, label):
        assert entity_type == "EDGE" and xy is not None
        fraction = round(math.dist(xy, _PIVOT_CENTRE) / _DETAIL_BORE_R, 6)
        picks.append((fraction, xy))
        return resolve(fraction)

    monkeypatch.setattr(drawing, "_select_view_entity", select)
    return picks


_ADAPTER = SimpleNamespace(
    swApp=_APP, currentModel=SimpleNamespace(ClearSelection2=lambda _all: True)
)


def test_pivot_pick_takes_the_bore_rim_on_the_datum_ray(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda _fraction: _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE, _DETAIL_BORE_R)
    assert [fraction for fraction, _ in picks] == [1.0]
    bearing = math.atan2(xy[1] - _PIVOT_CENTRE[1], xy[0] - _PIVOT_CENTRE[0])
    assert bearing == pytest.approx(drawing.PIVOT_DATUM_ANGLE)
    assert math.dist(xy, _PIVOT_CENTRE) == pytest.approx(_DETAIL_BORE_R)


def test_pivot_pick_moves_inward_when_the_rim_resolves_to_the_hub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda fraction: _HUB if fraction == 1.0 else _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE, _DETAIL_BORE_R)
    assert [fraction for fraction, _ in picks] == list(drawing.PIVOT_PICK_FRACTIONS)
    assert xy == picks[-1][1]
    # Inward points stay inside the bore, further from the hub rim.
    assert all(0.0 < f <= 1.0 for f in drawing.PIVOT_PICK_FRACTIONS)


def test_pivot_pick_that_never_finds_the_bore_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve(fraction: float) -> object:
        if fraction == 1.0:
            return _HUB
        raise RuntimeError("failed to select pivot bore datum pick edge")

    _picker(monkeypatch, resolve)
    with pytest.raises(RuntimeError, match="no pick on datum A's ray"):
        drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE, _DETAIL_BORE_R)




def test_detail_d_leaders_use_four_separate_quadrants(bound, monkeypatch) -> None:
    def project(_adapter, _view, points, **_kwargs):
        return [(drawing.HUB_CENTER[0] + x * 4.0,
                 drawing.HUB_CENTER[1] + (y - drawing.PIVOT_MID_Y / 1000.0) * 4.0)
                for x, y, _z in points]

    monkeypatch.setattr(drawing, "_project", project)
    rim, symbol = drawing._pivot_finish_placement(object(), object())
    datum = drawing._pivot_datum_request(_PIVOT_CENTRE, _DETAIL_BORE_R)
    points = [drawing.HUB_KEEP["HubDia"], datum, drawing.HUB_KEEP["PivotDia"], symbol]
    quadrants = [
        int((math.atan2(y - _PIVOT_CENTRE[1], x - _PIVOT_CENTRE[0]) % math.tau) // (math.pi / 2.0))
        for x, y in points
    ]
    assert quadrants == [0, 1, 2, 3]
    assert math.dist(rim, _PIVOT_CENTRE) == pytest.approx(_DETAIL_BORE_R)
    assert symbol[0] > rim[0] and symbol[1] < rim[1]
    assert drawing.HUB_KEEP["PivotDia"] == (0.117, 0.086)
    assert drawing.HUB_KEEP["HubDia"] == (0.212, 0.108)


def test_both_bores_are_picked_by_diameter_not_by_a_rim_coordinate() -> None:
    """r743-p1s-B: a coordinate pick on the #47 rod-hole rim resolved to the
    strap's tapered end-face line, so AddHoleCallout2 returned None. Every
    annotation on the rod-pin hole takes the diameter-picked edge."""

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    picks = {}
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "visible_circle_edge"
            ):
                picks[node.targets[0].id] = ast.unparse(call.args[2])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
            if (
                node.func.id in {"add_native_hole_callout", "add_edge_dimension", "add_feature_control_frame"}
                and ("rod_hole_edge" in keywords.get("edge", "")
                     or "rod_hole_edge" in keywords.get("edge_entity", "")
                     or "rod_hole_edge" in keywords.get("entities", ""))
            ):
                uses.append((node.func.id, keywords))
    assert picks["rod_hole_edge"] == "_ROD_HOLE_DIA"
    assert picks["pivot_bore_edge"] == "PIVOT_HOLE_DIA"
    kinds = {name for name, _ in uses}
    assert kinds == {
        "add_native_hole_callout",
        "add_edge_dimension",
        "add_feature_control_frame",
    }
    for name, keywords in uses:
        assert "edge_xy" not in keywords, name
        if name == "add_native_hole_callout":
            assert keywords["edge"] == "rod_hole_edge"
        elif name == "add_edge_dimension":
            assert keywords["entities"] == "(pivot_bore_edge, rod_hole_edge)"
        else:
            assert keywords["edge_entity"] == "rod_hole_edge"


# Measured on the r743-p1s-B2 render (5100x3300 px on 431.8x279.4 mm): the
# drawable region ends 12.7 mm above the sheet's bottom edge, the linked
# notes pitch ~4.14 mm a line, and the iso caption runs ~2.5 mm a character.
BORDER_BOTTOM = 0.0127
NOTE_LINE_PITCH = 0.0042
CAPTION_CHAR_WIDTH = 0.0026
# The general notes' rendered advance: r3c's 40-character row spans ~106 mm.
NOTES_CHAR_WIDTH = 0.0027


def _notes_fit_left_of_the_title_block(notes: str) -> bool:
    """Opus #1020 r3 C3 (rule 7's four lines): the notes run full width under
    the front view, every row ending 10 mm short of the title block."""
    widest = max(map(len, notes.splitlines()))
    title_left = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_left_m
    return drawing.NOTES_LEFT + widest * NOTES_CHAR_WIDTH <= title_left - 0.010


# Dimension value + callout rows as the r1 farm render printed them (strap
# thickness: value ~0.183 to last row ~0.166 over three pitches).
RENDERED_ROW_PITCH = 0.0056
RIGHT_BORDER = 0.415
DRAWABLE = DrawableRegion(0.0127, BORDER_BOTTOM, 0.4191, 0.2667)


class _FakeAnnotation:
    _native_interfaces = ("IAnnotation",)
    def __init__(self, position: tuple[float, float]) -> None:
        self.position = position

    def GetPosition(self) -> tuple[float, float, float]:
        return (*self.position, 0.0)

    def SetPosition(self, x: float, y: float, _z: float) -> bool:
        self.position = (x, y)
        return True


class _FakeNote:
    """A top-left-anchored text block whose box sits off its insertion point
    and follows a move only ``tracking`` of the way, as SolidWorks' does."""

    _native_interfaces = ("INote",)

    def __init__(
        self, anchor: tuple[float, float], height: float, tracking: float = 1.0
    ) -> None:
        self.annotation = _FakeAnnotation(anchor)
        self.anchor = anchor
        self.height = height
        self.tracking = tracking

    def GetAnnotation(self) -> _FakeAnnotation:
        return self.annotation

    def GetExtent(self) -> tuple[float, ...]:
        x, y = (
            a + (p - a) * self.tracking
            for a, p in zip(self.anchor, self.annotation.position)
        )
        x0, y1 = x + 0.0008, y - 0.0011
        return (x0, y1 - self.height, 0.0, x0 + 0.180, y1, 0.0)


def _seat(monkeypatch: pytest.MonkeyPatch, note: _FakeNote) -> tuple[float, ...]:
    adapter = SimpleNamespace(
        currentModel=_native("IModelDoc2", GraphicsRedraw2=lambda: None)
    )
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(
        drawing, "sheet_drawable_region", lambda *_args, **_kwargs: DRAWABLE
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    return drawing._seat_notes_on_border(adapter, note, sheet=object())


@pytest.mark.parametrize("tracking", [1.0, 0.8])
def test_general_notes_bottom_is_seated_inside_the_frame(
    monkeypatch: pytest.MonkeyPatch, tracking: float
) -> None:
    """r743-p1s-B2: anchored by its top at 0.082, the 18-line block ran two
    lines past the bottom border. Seated from its measured extent, its bottom
    lands on the drawable region's clearance line and its left on NOTES_LEFT,
    whatever the insertion point's offset from the rendered box."""
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
    note = _FakeNote(
        (drawing.NOTES_LEFT, drawing.NOTES_CEILING),
        lines * NOTE_LINE_PITCH,
        tracking,
    )
    x0, y0, _x1, y1 = _seat(monkeypatch, note)
    assert y0 >= DRAWABLE.ymin
    assert y0 == pytest.approx(
        DRAWABLE.ymin + drawing.NOTES_BORDER_CLEARANCE,
        abs=0.0005,
    )
    assert x0 == pytest.approx(drawing.NOTES_LEFT, abs=0.0005)
    assert y1 < drawing.NOTES_CEILING
    # The shorter notes need no historical line-count overflow assumption:
    # the rendered extent, not an old insertion point, governs seating.


# r743-3 (4ca562169, w4): the 21-line block rendered 16.06..110.76 mm, i.e.
# 94.70 mm tall, 0.76 over NOTES_CEILING -- ~4.51 mm a line of rendered
# extent (box margins included), well above the 4.14 line pitch B2 measured.
R743_3_RENDERED_PITCH = 0.09470 / 21


def test_general_notes_leave_a_full_line_of_headroom() -> None:
    """Main (r743-3): the line estimate undercounted, so the block must fit
    the band with one full rendered line to spare at the measured pitch."""
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    assert (lines + 1) * R743_3_RENDERED_PITCH <= band
    # Every row ends short of the title block.
    assert _notes_fit_left_of_the_title_block(ch_rocker_arm_notes.DRAWING_NOTES)
    assert len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines()) <= 4


def test_general_notes_too_tall_for_the_band_fail_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    note = _FakeNote((drawing.NOTES_LEFT, drawing.NOTES_CEILING), band + 0.002)
    with pytest.raises(RuntimeError, match="do not fit"):
        _seat(monkeypatch, note)


def test_an_unresolved_notes_link_fails_instead_of_seating_one_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extent of an unresolved property link is one line of token text;
    seating that box would put the real block's bottom through the border."""
    note = _FakeNote((drawing.NOTES_LEFT, drawing.NOTES_CEILING), NOTE_LINE_PITCH)
    with pytest.raises(RuntimeError, match="has not resolved"):
        _seat(monkeypatch, note)


def test_iso_caption_sits_under_the_iso_clear_of_the_frame_and_end_view() -> None:
    caption = ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE
    left, top = drawing.ISO_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    assert top < drawing.ISO_CENTER[1] - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right




def test_land_and_hub_sizes_are_marked_model_dimensions_at_normal_precision() -> None:
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["StrapProfile"] == {
        "TopRadius", "BottomRadius", "RodTipLen", "TipLandAngle",
    }
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["HubProfile"] == {"HubDia"}
    assert set(drawing.END_KEEP) == {"RodTipLen", "TipLandAngle"}
    assert ch_rocker_arm_notes.DRAWING_PRECISION["StrapProfile"]["TipLandAngle"] == 2
    assert "TipLandVerticalLength" not in set().union(
        *ch_rocker_arm_notes.DRAWING_DIMENSIONS.values()
    )
    assert set(drawing.HUB_KEEP) == {"PivotDia", "HubDia"}
    assert not {"RodTipLen", "HubDia"} & set(drawing.FRONT_KEEP)
    assert ch_rocker_arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"] == 2
    assert ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION == 2
    assert ch_rocker_arm_spec.LINEAR_2PL == pytest.approx(0.254)
    assert ch_rocker_arm_spec.STRAP_HUB_SYMMETRY == pytest.approx(0.1016)
    # Strap symmetry is a position zone on the strap width to the hub width's
    # datum (Main's option B): no chained hub-end-to-strap offset survives.
    assert ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN["strap position to hub"] == ".004"
    letter = drawing.HUB_FACES.fields["datum"][0]
    assert drawing.STRAP_FACES.fields["position_datums"][0] == [letter]
    # Its letter names nothing else on the sheet (Opus #1020 r3 C4: datum D
    # read against detail D) and avoids ASME's barred I, O and Q.
    taken = {"A", "B", "C", *drawing.DETAIL_LETTER_XY, ch_rocker_arm_notes.VIEW_ARROW_LETTER}
    assert letter not in taken | {"I", "O", "Q"}
    assert not any("Offset" in name for names in ch_rocker_arm_notes.DRAWING_DIMENSIONS.values() for name in names)
    assert "StrapOffset" not in drawing.RIGHT_KEEP
    joined = " ".join(ch_rocker_arm_notes.DRAWING_NOTES.split())
    assert "STRAP SYMMETRIC" not in joined


def test_new_measured_quantities_follow_the_source_geometry_equations() -> None:
    spec = ch_rocker_arm_spec
    alpha = spec.TOP_ARC_LEN / (2.0 * rocker_interface.CURVE_RADIUS)
    assert spec._ALPHA_TOP == pytest.approx(alpha)
    assert 2.0 * spec.ROD_TIP_X == pytest.approx(
        2.0 * (rocker_interface.CURVE_RADIUS + spec.TIP_FACE) * math.sin(alpha),
    )
    assert spec.BOT_END_X == pytest.approx(
        (rocker_interface.CURVE_RADIUS + rocker_interface.ARM_DEPTH)
        * math.sin(spec.BOT_ARC_LEN / (2.0 * (rocker_interface.CURVE_RADIUS + rocker_interface.ARM_DEPTH))),
    )
    assert spec.TIP_FACE == pytest.approx(5.588)
    assert spec.HUB_DIA == pytest.approx(10.16)
    assert (spec.HUB_LENGTH - spec.ARM_THICKNESS) / 2.0 == pytest.approx(2.28365)


def test_rod_hole_keeps_its_normal_wall_to_the_real_k_taper_at_printed_bands():
    """Rule 17: the finite oblique taper, not horizontal edge distance.

    Charge the entire lower profile zone against the wall, conservatively
    ignoring its material-adding disposition. This short through hole in
    the .098 plate needs no deep-hole drill-wander allowance.
    """
    from _inch_wall_limits import WALL_TARGET_MM
    from _printed_tolerance import drilled_oversize_mm

    spec = ch_rocker_arm_spec
    centre = (rocker_interface.ROD_HOLE_X, rocker_interface.ROD_HOLE_Y)
    tip = (
        spec.ROD_TIP_X,
        spec.TOP_END_Y + spec.TIP_FACE * (spec.TOP_END_Y - rocker_interface.CENTER_Y) / spec.R_TOP,
    )
    bottom = (
        spec.BOT_END_X,
        rocker_interface.CENTER_Y - math.sqrt(rocker_interface.R_BOTTOM**2 - spec.BOT_END_X**2),
    )
    direction = (bottom[0] - tip[0], bottom[1] - tip[1])
    fraction = sum(
        (centre[index] - tip[index]) * direction[index] for index in range(2)
    ) / sum(value**2 for value in direction)
    assert fraction == pytest.approx(0.78133996267)
    assert 0.0 < fraction < 1.0
    closest = tuple(tip[index] + fraction * direction[index] for index in range(2))
    normal_distance = math.dist(centre, closest)
    taper_face = drawing._RIGHT[1]
    face_distance = abs(
        sum(taper_face.normal[index] * centre[index] for index in range(2))
        - taper_face.offset_mm
    )
    assert normal_distance == pytest.approx(face_distance)
    assert normal_distance == pytest.approx(3.81835328575)
    hole_nominal = blind_cut_dia_mm(spec.ROD_HOLE_SPEC)
    # A named drill retains its real size even when its numeric callout rounds.
    # Charge the larger of the native and displayed (inch, rounded up) nominal.
    places = drawing.ROD_HOLE.precision["dia"]
    displayed = math.ceil(hole_nominal / 25.4 * 10**places - 1e-9) / 10**places * 25.4
    conservative_hole_max = max(hole_nominal, displayed) + drilled_oversize_mm(unit=spec.UNIT)
    assert conservative_hole_max == pytest.approx(2.1082)
    position_diameter = float(spec.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    assert position_diameter == drawing.ROD_HOLE.fields["position_dia"][0]
    profile_allowance = float(drawing.ARC_PROFILE_ZONE_MM)
    worst_wall = normal_distance - conservative_hole_max / 2.0 - position_diameter / 2.0 - profile_allowance
    assert worst_wall == pytest.approx(2.15465328575)
    assert worst_wall >= WALL_TARGET_MM, f"rod-pin hole to K-taper normal wall is only {worst_wall:g} mm"


@pytest.mark.parametrize("ignored_part", [None, 1, 2])
def test_native_reference_parentheses_never_replace_the_measured_nominal(
    monkeypatch: pytest.MonkeyPatch, ignored_part: int | None,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    text = {1: "", 2: ""}
    writes = []
    model = _native("IDimension", SystemValue=0.00227825)

    def set_text(part, value):
        writes.append((part, value))
        if part != ignored_part:
            text[part] = value

    display = _native("IDisplayDimension", SetText=set_text, GetText=lambda part: text[part],
    GetDimension2=lambda _index: model,)
    annotation = _native("IAnnotation", GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    if ignored_part is None:
        assert _drawing_dimensions.set_reference_dimension(
            adapter, annotation, label="strap offset",
        ) is display
        assert text == {1: "(", 2: ")"}
    else:
        with pytest.raises(RuntimeError, match="failed to parenthesize"):
            _drawing_dimensions.set_reference_dimension(
                adapter, annotation, label="strap offset",
            )
    assert writes == [(1, "("), (2, ")")]
    assert model.SystemValue == 0.00227825


def test_rod_drill_identifier_and_native_callout_process_share_the_hole_spec() -> None:
    from _hole_spec import drill_process

    assert ch_rocker_arm_spec.ROD_HOLE_SPEC.kind == "drilled_number"
    assert ch_rocker_arm_spec.ROD_HOLE_SPEC.size == "#47"
    assert drill_process(ch_rocker_arm_spec.ROD_HOLE_SPEC) == "#47 DRILL"
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "add_native_hole_callout"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in calls[0].keywords}
    assert keywords["process"] == (
        "rocker_notes.ROD_PIN_MATE_CALLOUT + '\\n' + drill_process(ROD_HOLE_SPEC) + '\\n'"
    )
    # The pin that runs in the hole is named over the drill (Opus #1020 r3 C5).
    assert "MHA-CH-10" in ch_rocker_arm_notes.ROD_PIN_MATE_CALLOUT
    assert drawing.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC


@pytest.mark.parametrize("quantity,expected", [
    ("overall", 2.0 * ch_rocker_arm_spec.ROD_TIP_X),
    ("land", ch_rocker_arm_spec.TIP_FACE),
    ("taper", ch_rocker_arm_spec.BOT_END_X),
    ("hub", ch_rocker_arm_spec.HUB_DIA),
    ("offset", (ch_rocker_arm_spec.HUB_LENGTH - ch_rocker_arm_spec.ARM_THICKNESS) / 2.0),
])
@pytest.mark.parametrize("defect", [
    None, "wrong", "missing", "neighbour", "dangling", "nan", "inf", "no_value",
])
def test_native_linear_measurement_reads_the_model_and_named_attachments(
    monkeypatch: pytest.MonkeyPatch, quantity: str, expected: float, defect: str | None,
) -> None:
    import _drawing_edge_dimensions
    from solidworks_mcp.adapters import sw_type_info

    first, second, neighbour = object(), object(), object()
    model = None if defect == "missing" else _native("IDimension", SystemValue=(expected + (0.1 if defect == "wrong" else 0.0)) / 1000.0, )
    if defect in {"nan", "inf", "no_value"}:
        model.SystemValue = None if defect == "no_value" else float(defect)
    attached = (first, neighbour if defect == "neighbour" else second)
    annotation = _native("IAnnotation", GetAttachedEntities3=lambda: attached, GetAttachedEntityTypes=lambda: (1, 1),
    IsDangling=lambda: defect == "dangling",)
    display = _native("IDisplayDimension", GetDimension2=lambda _index: model, GetAnnotation=lambda: annotation,)
    adapter = SimpleNamespace(swApp=_APP)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", _bind_owner)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, wanted, _kind: actual is wanted,
    )
    kwargs = dict(expected_mm=expected, label=quantity, entities=(first, second))
    if defect is None:
        assert _drawing_edge_dimensions.assert_dimension_measures(
            adapter, display, **kwargs,
        ) == pytest.approx(expected)
    else:
        with pytest.raises((RuntimeError, AttributeError)):
            _drawing_edge_dimensions.assert_dimension_measures(adapter, display, **kwargs)


@pytest.mark.parametrize("retained", [True, False])
def test_native_reference_precision_reads_back_normal_two_places(
    monkeypatch: pytest.MonkeyPatch, retained: bool,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    state = {"precision": 3}
    calls = []

    def set_precision(primary, dual, tolerance, dual_tolerance):
        calls.append((primary, dual, tolerance, dual_tolerance))
        if retained:
            state["precision"] = primary
        return 0  # SetPrecision3 returns native integer status, not VT_BOOL.

    display = _native("IDisplayDimension", SetPrecision3=set_precision, GetPrimaryPrecision2=lambda: state["precision"],)
    annotation = _native("IAnnotation", GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: "offset")
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    kwargs = {"offset": ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION}
    if retained:
        _drawing_dimensions.set_dimension_precision(adapter, [annotation], kwargs)
        assert state["precision"] == 2
    else:
        with pytest.raises(RuntimeError, match="did not take"):
            _drawing_dimensions.set_dimension_precision(adapter, [annotation], kwargs)
    assert calls == [(2, -1, -1, -1)]


def test_rocker_native_helpers_use_the_extracted_owners() -> None:
    import _drawing_edge_dimensions
    import _drawing_gdt
    import _drawing_hole_callout

    assert drawing.add_edge_dimension is _drawing_edge_dimensions.add_edge_dimension
    assert drawing.add_datum_feature is _drawing_gdt.add_datum_feature
    assert drawing.add_feature_control_frame is _drawing_gdt.add_feature_control_frame
    assert drawing.add_native_hole_callout is _drawing_hole_callout.add_native_hole_callout


@pytest.mark.parametrize("defect", [None, "one_place", "missing", "no_display"])
@pytest.mark.parametrize("feature,name", [("HubProfile", "HubDia"), ("StrapProfile", "TipLandAngle")])
def test_imported_native_dimensions_cannot_lose_the_model_two_place_precision(
    monkeypatch: pytest.MonkeyPatch, defect: str | None, feature: str, name: str,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    display = _native("IDisplayDimension", GetPrimaryPrecision2=lambda: 1 if defect == "one_place" else 2, SetPrecision3=lambda *_: pytest.fail("imported precision is part-owned"),)
    annotation = _native("IAnnotation", GetSpecificAnnotation=lambda: None if defect == "no_display" else display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: name)
    annotations = [] if defect == "missing" else [annotation]
    precision = {name: ch_rocker_arm_notes.DRAWING_PRECISION[feature][name]}
    if defect is None:
        _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)
    else:
        with pytest.raises(RuntimeError):
            _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)


@pytest.mark.parametrize("name", [
    "ROD_TIP_X", "TIP_FACE", "_ALPHA_TOP", "BOT_END_X", "HUB_DIA",
    "ARM_THICKNESS",
])
def test_measured_dimension_expectations_import_the_geometry_source(name: str) -> None:
    assert getattr(drawing, name) == getattr(ch_rocker_arm_spec, name)


class _NativeQuantityAnnotation:
    """IAnnotation owns specific-object lookup and dimension attachment reads."""

    _native_interfaces = ("IAnnotation",)

    def __init__(self, display):
        self.display = display
        self.name = display.name

    def GetSpecificAnnotation(self):
        return self.display

    def GetAttachedEntities3(self):
        return self.display.attached

    def GetAttachedEntityTypes(self):
        return tuple(1 for _ in self.display.attached)

    def IsDangling(self):
        return self.display.dangling


class _NativeQuantity:
    """IDisplayDimension retaining independent text and model-size bands."""

    _native_interfaces = ("IDisplayDimension",)

    def __init__(self, name: str, mm: float, *, precision: int = 2) -> None:
        self.name = name
        self.precision = precision
        self.text = {
            1: "<MOD-DIAM>" if name in {"PivotDia", "HubDia"} else "", 2: "",
            3: "<native-upper>", 4: "<native-lower>",
        }
        self.writes = []
        self.ignored_text = None
        self.ignored_precision = False
        self.ShowDimensionValue = True
        self.SolidLeader = True
        self.ArrowSide = 0
        self.second_arrow = (True, True)
        self.Type2 = 6 if name in {"PivotDia", "HubDia"} else 1
        self.band = tuple(v / 1000.0 for v in ch_rocker_arm_spec.PIVOT_HOLE_BAND)
        self.tolerance_type = 4 if name == "PivotDia" else 0
        self.attached = ()
        self.dangling = False
        self.arc_conditions = {1: 2, 2: 0}
        self.annotation = _NativeQuantityAnnotation(self)
        self.model = _native("IDimension", SystemValue=mm / 1000.0, Type2=6 if name in {"PivotDia", "HubDia"} else 1,
        SetToleranceType=self._set_tolerance_type,
        GetToleranceType=lambda: self.tolerance_type,
        Tolerance=_native("IDimensionTolerance", GetMaxValue=lambda: self.band[0], GetMinValue=lambda: self.band[1]),
        GetArcEndCondition=lambda index: self.arc_conditions[index],
        SetArcEndCondition=self._set_arc_condition,)

    def _set_tolerance_type(self, kind):
        self.tolerance_type = kind
        return True

    def GetAnnotation(self):
        return self.annotation

    def GetDimension2(self, _index):
        return self.model

    def GetDimension(self):
        return self.model

    def _set_arc_condition(self, index, condition):
        self.arc_conditions[index] = condition
        return 0

    def GetText(self, part):
        return self.text[{5: 1, 6: 2, 7: 3, 8: 4}.get(part, part)]

    def SetText(self, part, value):
        self.writes.append((part, value))
        if part != self.ignored_text:
            self.text[part] = value

    def SetPrecision3(self, primary, _dual, _primary_tolerance, _dual_tolerance):
        if not self.ignored_precision:
            self.precision = primary
        return 0  # Native integer status, not VT_BOOL.

    def GetPrimaryPrecision2(self):
        return self.precision

    def SetSecondArrow(self, use_doc, enabled):
        self.second_arrow = (use_doc, enabled)

    def GetUseDocSecondArrow(self):
        return self.second_arrow[0]

    def GetSecondArrow(self):
        return self.second_arrow[1]


class _IgnoredLocatorCap(_NativeQuantity):
    """Native cap setter accepts the call without retaining the requested value."""

    def __setattr__(self, name, value):
        super().__setattr__(name, 0.100 if name == "MaxWitnessLineLength" else value)


def _imported_native_quantities(monkeypatch: pytest.MonkeyPatch):
    from solidworks_mcp.adapters import sw_type_info
    import _drawing_dimensions
    import _drawing_edge_dimensions

    displays = {
        "PivotDia": _NativeQuantity("PivotDia", ch_rocker_arm_spec.PIVOT_HOLE_DIA),
        "RodTipLen": _NativeQuantity("RodTipLen", ch_rocker_arm_spec.TIP_FACE, precision=1),
        "HubDia": _NativeQuantity("HubDia", ch_rocker_arm_spec.HUB_DIA),
        "TipLandAngle": _NativeQuantity("TipLandAngle", 0.0),
    }
    angle = displays["TipLandAngle"]
    angle.Type2 = angle.model.Type2 = 3
    angle.model.SystemValue = ch_rocker_arm_spec._ALPHA_TOP
    adapter = SimpleNamespace(
        _attempt=lambda fn, **_kwargs: fn(), swApp=_APP,
        currentModel=_native("IModelDoc2", GraphicsRedraw2=lambda: None),
    )
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", _bind_owner)
    monkeypatch.setattr(_drawing_dimensions, "_early_bound", _bind_owner)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", _bind_owner)
    def name(_adapter, annotation):
        return _bind_owner(annotation, "IAnnotation").name
    monkeypatch.setattr(drawing, "dimension_name", name)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", name)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    return adapter, displays


def test_front_native_process_keeps_the_nominal_token_and_model_bore_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    before = {name: display.model.SystemValue for name, display in displays.items()}
    drawing._dress_detail_dimensions(adapter, [display.GetAnnotation() for display in displays.values()], keep={**drawing.HUB_KEEP, **drawing.END_KEEP})
    pivot = displays["PivotDia"]
    assert pivot.text[1].startswith("REAM ")
    assert "<MOD-DIAM>" in pivot.text[1]
    assert pivot.text[2] == " THRU"
    assert not any(part == 0 for part, _text in pivot.writes)
    assert not any(nominal in text for _part, text in pivot.writes for nominal in (
        "6.50", "5.588", "10.20", "+0.03",
    ))
    assert {name: display.model.SystemValue for name, display in displays.items()} == before
    assert displays["HubDia"].precision == 2
    assert pivot.band == tuple(v / 1000.0 for v in ch_rocker_arm_spec.PIVOT_HOLE_BAND)
    assert pivot.model.GetToleranceType() == 4
    # Both tip lands ride the one BASIC 5.59 (main-r1: no mirror note).
    assert displays["RodTipLen"].text[1] == ch_rocker_arm_notes.TIP_LAND_PREFIX == "2X "
    assert displays["RodTipLen"].model.GetToleranceType() == 1
    angle = displays["TipLandAngle"]
    assert angle.model.SystemValue == pytest.approx(ch_rocker_arm_spec._ALPHA_TOP)
    assert angle.text[1] == ch_rocker_arm_notes.TIP_LAND_ANGLE_PREFIX == "2X "
    assert angle.model.GetToleranceType() == 1
    assert angle.ShowDimensionValue is True
    assert not any(part == 0 for part, _text in angle.writes)
    assert pivot.ShowDimensionValue is True
    # The ream band reads as clearance on its named mate (MR #1020).
    assert (pivot.text[3], pivot.text[4]) == ("<native-upper>", ch_rocker_arm_notes.PIVOT_FIT_CALLOUT)
    assert ch_rocker_arm_notes.PIVOT_FIT_CALLOUT == (
        "(.0060-.0078 DIAMETRAL\nCLEARANCE ON PIVOT\nSHAFT MHA-CH-05)"
    )


@pytest.mark.parametrize("name", ["PivotDia", "RodTipLen", "HubDia", "TipLandAngle"])
@pytest.mark.parametrize("defect", ["missing", "wrong", "nan", "inf", "no_value"])
def test_imported_front_sizes_require_each_sourced_native_readback(
    monkeypatch: pytest.MonkeyPatch, name: str, defect: str,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    if defect == "missing":
        del displays[name]
    else:
        model = displays[name].model
        model.SystemValue = (
            model.SystemValue + 0.0001 if defect == "wrong"
            else None if defect == "no_value"
            else float(defect)
        )
    with pytest.raises(RuntimeError):
        drawing._dress_detail_dimensions(adapter, [display.GetAnnotation() for display in displays.values()], keep={**drawing.HUB_KEEP, **drawing.END_KEEP})


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("offset,accepted", [(0.0, True), (5e-9, True), (2e-8, False)])
def test_tip_angle_import_preserves_the_builder_signed_readback_contract(
    monkeypatch: pytest.MonkeyPatch, sign: int, offset: float, accepted: bool,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    angle = displays["TipLandAngle"]
    actual = sign * (ch_rocker_arm_spec._ALPHA_TOP + offset)
    angle.model.SystemValue = actual
    annotations = [displays[name].GetAnnotation() for name in drawing.END_KEEP]
    if not accepted:
        with pytest.raises(RuntimeError, match="native radial-land measurement"):
            drawing._dress_detail_dimensions(adapter, annotations, keep=drawing.END_KEEP)
        return
    drawing._dress_detail_dimensions(adapter, annotations, keep=drawing.END_KEEP)
    assert angle.model.SystemValue == actual
    assert angle.model.GetToleranceType() == 1
    assert angle.text[1] == ch_rocker_arm_notes.TIP_LAND_ANGLE_PREFIX
    assert not any(part == 0 for part, _text in angle.writes)


@pytest.mark.parametrize("defect", ["linear", "prefix", "basic"])
def test_tip_angle_native_dressing_refuses_wrong_kind_and_ignored_setters(monkeypatch, defect):
    adapter, displays = _imported_native_quantities(monkeypatch)
    angle = displays["TipLandAngle"]
    if defect == "linear":
        angle.Type2 = 1
    elif defect == "prefix":
        angle.ignored_text = 1
    else:
        angle.model.SetToleranceType = lambda _kind: True
    with pytest.raises(RuntimeError):
        drawing._dress_detail_dimensions(
            adapter, [displays[name].GetAnnotation() for name in drawing.END_KEEP],
            keep=drawing.END_KEEP,
        )


@pytest.mark.parametrize("ignored", ["prefix", "suffix", "hub_precision", "fit_callout"])
def test_front_native_dressing_rejects_ignored_text_or_lost_hub_precision(
    monkeypatch: pytest.MonkeyPatch, ignored: str,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    if ignored == "hub_precision":
        displays["HubDia"].precision = 1
    elif ignored == "fit_callout":
        displays["PivotDia"].ignored_text = 4
    else:
        displays["PivotDia"].ignored_text = 1 if ignored == "prefix" else 2
    with pytest.raises(RuntimeError):
        drawing._dress_detail_dimensions(adapter, [display.GetAnnotation() for display in displays.values()], keep=drawing.HUB_KEEP)


@pytest.fixture
def native_front(monkeypatch: pytest.MonkeyPatch):
    """CAD-owned endpoints feed fake creation; real selectors/readback stay live."""
    import _drawing_edge_dimensions
    from _drawing_edges import ViewEdge, ViewEdges

    adapter, imported = _imported_native_quantities(monkeypatch)
    vertex_points = {}
    rows = []
    for z in (-drawing.ARM_THICKNESS / 2.0, drawing.ARM_THICKNESS / 2.0):
        for sign in (-1, 1):
            upper = (sign * drawing.TOP_END_X, drawing.TOP_END_Y, z)
            outer = (sign * drawing.ROD_TIP_X, drawing._ROD_TIP_Y, z)
            lower = (sign * drawing.BOT_END_X, drawing._BOT_END_Y, z)
            vertices = [object() for _ in range(3)]
            vertex_points.update(zip(vertices, (upper, outer, lower)))
            rows.extend((
                ViewEdge(object(), (upper, outer), None, tuple(vertices[:2])),
                ViewEdge(object(), (outer, lower), None, tuple(vertices[1:])),
            ))
    scan = ViewEdges("front native CAD", tuple(rows))
    land = scan.exact_line_through(
        (drawing._TIP_FACE_MID_X, drawing._TIP_FACE_MID_Y, drawing.ARM_THICKNESS / 2.0),
        label="fixture front radial land",
    )
    pivot = object()
    state = SimpleNamespace(
        adapter=adapter, imported=imported, scan=scan, land=land,
        displays={}, calls=[], basic_calls=[], radius_calls=[],
        defect_label=None, defect=None,
    )

    def project(_adapter, _view, points, *, label):
        return [_front_xy(x * 1000.0, y * 1000.0) for x, y, _z in points]

    def create(_adapter, _front, **kwargs):
        state.calls.append(kwargs)
        label = kwargs["label"]
        entities = kwargs["entities"]
        if label == "rocker overall width":
            value_mm = abs(vertex_points[entities[1]][0] - vertex_points[entities[0]][0])
        elif label in {"taper intersection X", "left taper intersection X", "tip land X location", "left tip land X location"}:
            value_mm = abs(vertex_points[entities[1]][0])
        else:
            pytest.fail(f"unowned native dimension {label}")
        display = _NativeQuantity(label, value_mm)
        display.attached = entities
        if state.defect_label == label:
            if state.defect == "creation":
                raise RuntimeError(f"native dimension refused: {label}")
            if state.defect == "wrong":
                display.model.SystemValue += 0.0001
            elif state.defect in {"nan", "inf"}:
                display.model.SystemValue = float(state.defect)
            elif state.defect == "missing":
                display.model.SystemValue = None
            elif state.defect == "attachment":
                display.attached = (entities[0], object())
            elif state.defect == "null-annotation":
                display.GetAnnotation = lambda: None
            elif state.defect == "uncentred":
                display.model.SetArcEndCondition = lambda *_a: 0
            elif state.defect == "basic":
                display.model.SetToleranceType = lambda _kind: True
            elif state.defect == "text":
                display.ignored_text = 4
            elif state.defect == "cap":
                display.__class__ = _IgnoredLocatorCap
        state.displays[label] = display
        return display

    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_a, **_k: [display.GetAnnotation() for display in imported.values()])
    monkeypatch.setattr(
        drawing, "_basic_profile_dimensions",
        lambda _adapter, annotations: state.basic_calls.append(annotations),
    )
    monkeypatch.setattr(
        drawing, "_dress_arc_radii",
        lambda _adapter, annotations: state.radius_calls.append(annotations),
    )
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_k: scan)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "_project", project)
    monkeypatch.setattr(drawing, "visible_circle_edge", lambda *_: pivot)
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, expected, _kind: actual is expected,
    )
    return state


def test_outline_dimensions_measure_real_endpoints_and_choose_exact_positive_z_land(
    native_front,
) -> None:
    state = native_front
    drawing._add_rocker_outline_dimensions(state.adapter, object())
    assert state.basic_calls
    assert state.radius_calls == state.basic_calls
    assert all(point[2] == ch_rocker_arm_spec.ARM_THICKNESS / 2.0 for point in state.land.line)
    expected = {
        "rocker overall width": 2.0 * ch_rocker_arm_spec.ROD_TIP_X / 1000.0,
        "taper intersection X": ch_rocker_arm_spec.BOT_END_X / 1000.0,
        "left taper intersection X": ch_rocker_arm_spec.BOT_END_X / 1000.0,
        "tip land X location": ch_rocker_arm_spec.ROD_TIP_X / 1000.0,
        "left tip land X location": ch_rocker_arm_spec.ROD_TIP_X / 1000.0,
    }
    assert {
        label: display.model.SystemValue for label, display in state.displays.items()
    } == pytest.approx(expected)
    width, taper, left_taper, land, left_land = state.calls
    assert width["entity_types"] == ("VERTEX", "VERTEX")
    assert "entity_type" not in width
    assert taper["entity_types"] == ("EDGE", "VERTEX")
    assert state.displays["taper intersection X"].arc_conditions[1] == 1
    # The mirrored left taper vertex: its own one-place row from centred A.
    assert left_taper["orientation"] == "horizontal"
    assert left_taper["text_xy"] == drawing.LEFT_TAPER_TEXT_XY
    assert left_taper["entity_types"] == ("EDGE", "VERTEX")
    assert left_taper["entities"][0] is taper["entities"][0]
    assert left_taper["p0"] == taper["p0"]
    assert left_taper["entities"][1] is not taper["entities"][1]
    assert state.scan.exact_vertex_at(
        (-drawing.BOT_END_X, drawing._BOT_END_Y, drawing.ARM_THICKNESS / 2.0), label="left taper",
    ) is left_taper["entities"][1]
    assert land["orientation"] == "horizontal"
    assert land["text_xy"] == drawing.LAND_LOCATION_TEXT_XY == (0.219, 0.242)
    assert land["entity_types"] == ("EDGE", "VERTEX")
    assert land["entities"] == (taper["entities"][0], width["entities"][1])
    assert land["p0"] == taper["p0"] and land["p1"] == width["p1"]
    locator = state.displays["tip land X location"]
    assert locator.arc_conditions[1] == 1
    assert locator.model.GetToleranceType() == 1
    assert locator.ShowDimensionValue is True
    assert locator.text[1] == locator.text[2] == ""
    assert locator.text[4] == drawing.LAND_LABEL == "LAND"
    assert locator.writes[-2:] == [(4, ""), (4, "LAND")]
    assert locator.MaxWitnessLineLength == drawing.TAPER_WITNESS_LENGTH
    # The J land's mirrored BASIC LAND row from the same centred A (main-r1).
    assert left_land["orientation"] == "horizontal"
    assert left_land["text_xy"] == drawing.LEFT_LAND_LOCATION_TEXT_XY == (0.141, 0.242)
    assert left_land["entity_types"] == ("EDGE", "VERTEX")
    assert left_land["entities"] == (taper["entities"][0], width["entities"][0])
    assert left_land["p0"] == taper["p0"] and left_land["p1"] == width["p0"]
    assert 2.0 * drawing.FRONT_CENTER[0] - drawing.LEFT_LAND_LOCATION_TEXT_XY[0] == pytest.approx(drawing.LAND_LOCATION_TEXT_XY[0])
    left_locator = state.displays["left tip land X location"]
    assert left_locator.arc_conditions[1] == 1
    assert left_locator.model.GetToleranceType() == 1
    assert left_locator.text[1] == left_locator.text[2] == ""
    assert left_locator.writes[-2:] == [(4, ""), (4, "LAND")]
    assert left_locator.MaxWitnessLineLength == drawing.TAPER_WITNESS_LENGTH
    width_display = state.displays["rocker overall width"]
    assert (width_display.text[1], width_display.text[2]) == ("(", ")")
    assert width_display.model.GetToleranceType() == 0
    # Both taper feet are J↔K profile stations: BASIC, the zone is their band.
    for label in ("taper intersection X", "left taper intersection X"):
        display = state.displays[label]
        assert display.arc_conditions[1] == 1
        assert display.model.GetToleranceType() == 1
        assert display.text[4] == drawing.TAPER_LABEL == "R32.126/TAPER"
        assert display.writes[-1] == (4, drawing.TAPER_LABEL)
        assert display.MaxWitnessLineLength == drawing.TAPER_WITNESS_LENGTH


@pytest.mark.parametrize("label", [
    "rocker overall width", "taper intersection X", "left taper intersection X",
    "tip land X location", "left tip land X location",
])
@pytest.mark.parametrize("defect", ["creation", "wrong", "missing", "nan", "inf", "attachment"])
def test_each_new_outline_measurement_fails_closed(native_front, label, defect) -> None:
    native_front.defect_label = label
    native_front.defect = defect
    with pytest.raises(RuntimeError):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())


@pytest.mark.parametrize("label", [
    "taper intersection X", "left taper intersection X", "tip land X location",
    "left tip land X location",
])
@pytest.mark.parametrize("defect", ["uncentred", "basic", "text", "cap"])
def test_land_locator_rejects_ignored_native_setters(native_front, label, defect):
    native_front.defect_label = label
    native_front.defect = defect
    with pytest.raises(RuntimeError):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())


@pytest.mark.parametrize("defect", [
    None, "wrong", "missing-value", "nan", "inf", "attachment", "missing-attachment",
    "uncentred", "basic", "text", "hidden-value", "reference", "cap", "nan-cap",
    "missing", "duplicate", "wrong-view", "unnamed",
])
def test_land_locator_final_rebuild_readback_and_exact_front_census(
    native_front, monkeypatch, defect,
):
    case = native_front
    front, other = object(), object()
    _front_annotations, _taper, _taper_entities, display, entities = drawing._add_rocker_outline_dimensions(case.adapter, front)
    annotations = {front: [display.annotation], other: []}
    monkeypatch.setattr(drawing, "_bound_view_annotations", lambda view, **_k: annotations[view])
    if defect in {"wrong", "missing-value", "nan", "inf"}:
        display.model.SystemValue = (
            display.model.SystemValue + 0.0001 if defect == "wrong"
            else None if defect == "missing-value" else float(defect)
        )
    elif defect == "attachment":
        display.attached = (entities[0], object())
    elif defect == "missing-attachment":
        display.attached = ()
    elif defect == "uncentred":
        display.arc_conditions[1] = 2
    elif defect == "basic":
        display.tolerance_type = 0
    elif defect == "text":
        display.text[4] = ""
    elif defect == "hidden-value":
        display.ShowDimensionValue = False
    elif defect == "reference":
        display.text[1], display.text[2] = "(", ")"
    elif defect in {"cap", "nan-cap"}:
        display.MaxWitnessLineLength = 0.100 if defect == "cap" else float("nan")
    elif defect == "missing":
        annotations[front] = []
    elif defect == "duplicate":
        annotations[front].append(display.annotation)
    elif defect == "wrong-view":
        annotations[other] = annotations.pop(front)
        annotations[front] = []
    elif defect == "unnamed":
        display.annotation.name = ""
    if defect is None:
        drawing._require_land_location(case.adapter, (("front", front), ("detail E", other)), display, entities)
    else:
        with pytest.raises(RuntimeError):
            drawing._require_land_location(case.adapter, (("front", front), ("detail E", other)), display, entities)


def test_land_locator_expected_value_is_sourced_and_rejects_stale_native_geometry(
    native_front, monkeypatch,
):
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert any(
        isinstance(node, ast.ImportFrom) and node.module == "ch_rocker_arm_spec"
        and any(alias.name == "ROD_TIP_X" for alias in node.names)
        for node in tree.body
    )
    for name in ("_add_rocker_outline_dimensions", "_require_land_location"):
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        checks = [
            node for node in ast.walk(function) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == "assert_dimension_measures"
            and any(k.arg == "label" and isinstance(k.value, ast.Constant)
                    and k.value.value == "tip land X location" for k in node.keywords)
        ]
        assert len(checks) == 1
        assert next(ast.unparse(k.value) for k in checks[0].keywords if k.arg == "expected_mm") == "ROD_TIP_X"
    front = object()
    _front_annotations, _taper, _taper_entities, display, entities = drawing._add_rocker_outline_dimensions(native_front.adapter, front)
    monkeypatch.setattr(drawing, "_bound_view_annotations", lambda *_a, **_k: [display.annotation])
    monkeypatch.setattr(drawing, "ROD_TIP_X", ch_rocker_arm_spec.ROD_TIP_X + 0.1)
    with pytest.raises(RuntimeError):
        drawing._require_land_location(native_front.adapter, (("front", front),), display, entities)


def test_land_locator_guard_runs_after_final_rebuild_and_preserves_marked_census():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "build")
    calls = [
        node for node in ast.walk(build) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    ]
    guards = [node for node in calls if node.func.id == "_require_land_location"]
    assert len(guards) == 1
    guard = guards[0]
    final_rebuild = next(
        node for node in calls if node.func.id == "rebuild_drawing"
        and any(k.arg == "label" and isinstance(k.value, ast.Constant)
                and k.value.value == "rocker-arm layout audit" for k in node.keywords)
    )
    census = next(node for node in calls if node.func.id == "_require_dimension_census")
    assert final_rebuild.lineno < census.lineno < guard.lineno
    assert [ast.unparse(arg) for arg in guard.args[2:]] == ["land_dimension", "land_entities"]
    assert set(drawing.FRONT_KEEP) == drawing.BASIC_PROFILE_DIMENSIONS | set(drawing.ARC_RADIUS_NAMES)


@pytest.mark.parametrize("source", ["ROD_TIP_X", "TIP_FACE", "BOT_END_X", "HUB_DIA"])
def test_source_geometry_change_invalidates_stale_front_measurements(
    native_front, monkeypatch: pytest.MonkeyPatch, source: str,
) -> None:
    monkeypatch.setattr(drawing, source, getattr(drawing, source) + 0.1)
    with pytest.raises(RuntimeError):
        if source == "TIP_FACE":
            drawing._dress_detail_dimensions(native_front.adapter, [display.GetAnnotation() for display in native_front.imported.values()], keep=drawing.END_KEEP)
        elif source == "HUB_DIA":
            drawing._dress_detail_dimensions(native_front.adapter, [display.GetAnnotation() for display in native_front.imported.values()], keep=drawing.HUB_KEEP)
        else:
            drawing._add_rocker_outline_dimensions(native_front.adapter, object())


def test_datum_c_hangs_under_the_rod_pin_frame_after_its_dot_is_configured() -> None:
    # Y14.5: a feature of size's datum feature symbol sits on its frame.
    frame_left, frame_top = drawing.FCF_XY
    width, height = drawing.ROD_FRAME_SIZE
    x, y = drawing.ROD_DATUM_C_XY
    assert x == pytest.approx(frame_left + width / 2.0)
    assert y == pytest.approx(frame_top - height - 0.005 - drawing.DATUM_TAG_BOX)
    assert width == pytest.approx(0.0351)  # ⌖|Ø0.20|A|B cells on v43, C removed
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    (tag,) = [node for node in calls if node.func.id == "add_frame_datum_feature"]
    (dot,) = [node for node in calls if node.func.id == "_configure_rod_position_dot"]
    assert dot.lineno < tag.lineno
    assert [ast.unparse(arg) for arg in tag.args] == ["adapter", "end", "rod_position_gtol"]
    keywords = {k.arg: ast.unparse(k.value) for k in tag.keywords}
    assert keywords["datum"] == "ROD_HOLE.fields['datum'][0]"
    assert keywords["symbol_xy"] == "ROD_DATUM_C_XY"
    assert not any(node.func.id == "_add_land_datum" for node in calls)
    assert not hasattr(drawing, "_add_land_datum") and not hasattr(drawing, "LAND_DATUM_STANDOFF")


class _HubRootDisplay(_NativeQuantity):
    """View F's imported HubRootRadius: a radial display with a native MAX band."""

    def __init__(self) -> None:
        super().__init__("HubRootRadius", ch_rocker_arm_spec.HUB_ROOT_RADIUS_MAX, precision=1)
        self.Diametric = False
        self.ignore_leader = False
        self.ArcExtensionLineOrOppositeSide = True
        self.text[1] = ch_rocker_arm_notes.HUB_ROOT_PREFIX  # stamped by the part
        self.model.Tolerance = _native("IDimensionTolerance", Type=ch_rocker_arm_notes.HUB_ROOT_R_TOL_TYPE)

    def __setattr__(self, name, value):
        if name == "ArcExtensionLineOrOppositeSide" and getattr(self, "ignore_leader", False):
            return
        super().__setattr__(name, value)


@pytest.fixture
def native_hub_root(monkeypatch: pytest.MonkeyPatch):
    adapter, _imported = _imported_native_quantities(monkeypatch)
    root = _HubRootDisplay()
    neighbours = [
        _NativeQuantity("HubLength", ch_rocker_arm_spec.HUB_LENGTH),
        _NativeQuantity("StrapThickness", ch_rocker_arm_spec.ARM_THICKNESS),
    ]
    return SimpleNamespace(
        adapter=adapter, display=root,
        annotations=[neighbours[0].annotation, root.annotation, neighbours[1].annotation],
    )


def test_hub_root_prints_the_part_max_limit_with_a_trimmed_leader(native_hub_root) -> None:
    """Opus #1020 r2 C2 (rule 16): the hub-to-strap roots carry 2X R0.2 MAX."""
    drawing._dress_hub_root(native_hub_root.adapter, native_hub_root.annotations)
    display = native_hub_root.display
    assert display.ArcExtensionLineOrOppositeSide is False
    # The part owns the value, its MAX type and the 2X; the sheet adds only
    # the mate the limit protects.
    assert display.writes == [(4, ch_rocker_arm_notes.HUB_ROOT_CALLOUT)]
    assert ch_rocker_arm_notes.HUB_ROOT_R_BAND == (0.0, -ch_rocker_arm_spec.HUB_ROOT_RADIUS_MAX)


@pytest.mark.parametrize("defect", ["zero", "two", "diametric", "type", "value", "prefix", "leader"])
def test_hub_root_refuses_a_lost_limit_or_leader(native_hub_root, defect: str) -> None:
    display = native_hub_root.display
    annotations = native_hub_root.annotations
    if defect == "zero":
        annotations = [ann for ann in annotations if ann is not display.annotation]
    elif defect == "two":
        annotations = [*annotations, _HubRootDisplay().annotation]
    elif defect == "diametric":
        display.Diametric = True
    elif defect == "type":
        display.model.Tolerance.Type = 0  # swTolNONE: the MAX band did not import
    elif defect == "value":
        display.model.SystemValue += 0.0001
    elif defect == "prefix":
        display.text[1] = ""
    else:
        display.ignore_leader = True
    with pytest.raises(RuntimeError, match="HubRootRadius|hub root"):
        drawing._dress_hub_root(native_hub_root.adapter, annotations)


@pytest.fixture
def view_f_dimension(monkeypatch: pytest.MonkeyPatch):
    """View F's imported hub width / strap width, re-resolved and selected
    natively, with a frame annotation to attach to it."""
    calls: list = []
    state: dict = {}

    def display(selection: str, full_name: str):
        annotation = _native("IAnnotation", GetType=lambda: state["annotation_type"])
        dimension = _native("IDimension", FullName=full_name)
        return _native(
            "IDisplayDimension", GetNameForSelection=lambda: selection,
            GetDimension2=lambda _index: dimension, GetAnnotation=lambda: annotation,
        )

    wanted = display("RD3@Drawing View2", "HubLength@Hub@ch-rocker-arm.Part")
    fresh = display("RD3@Drawing View2", "HubLength@Hub@ch-rocker-arm.Part")
    other = display("RD4@Drawing View2", "StrapThickness@Strap@ch-rocker-arm.Part")
    imported = _native("IAnnotation", GetSpecificAnnotation=lambda: wanted)

    def set_attached(entities) -> bool:
        (target,) = entities
        calls.append(("SetAttachedEntities", target))
        if target in state["accepts"]:
            state["attached_count"] = 1
            return True
        return False

    attached = _native(
        "IAnnotation",
        GetAttachedEntityCount3=lambda: state["attached_count"],
        SetAttachedEntities=set_attached,
        GetAttachedEntityTypes=lambda: state["types"],
        GetAttachedEntities3=lambda: (state["attached"],),
        IsDangling=lambda: state["dangling"],
    )

    def set_xml(xml: str) -> bool:
        calls.append("SetSymbolXml")
        if state["xml_ok"]:
            state["xml"] = xml
        return state["xml_ok"]

    frame = _native("IGtolFrame", SetSymbolXml=set_xml, GetSymbolXml=lambda: state["xml"])
    gtol = _native(
        "IGtol", GetFrameCount=lambda: 1, GetFrame=lambda _index: frame,
        GetFormat=lambda: state["format"], GetAnnotation=lambda: attached,
    )

    def select(*args):
        calls.append(("SelectByID2", args[:2]))
        return state["selected"]

    def insert(kind: str):
        def call():
            calls.append(kind)
            return state[kind]
        return call

    model = _native(
        "IModelDoc2", "IDrawingDoc",
        ActivateView=lambda name: name == "Drawing View2",
        ClearSelection2=lambda _all: calls.append("ClearSelection2"),
        InsertGtol=insert("InsertGtol"),
        Extension=_native("IModelDocExtension", SelectByID2=select),
        SelectionManager=_native(
            "ISelectionMgr",
            GetSelectedObjectCount2=lambda _mark: state["count"],
            GetSelectedObjectType3=lambda _index, _mark: state["kind"],
            GetSelectedObject6=lambda _index, _mark: state["picked"],
        ),
    )
    adapter = SimpleNamespace(currentModel=model, swApp=_APP)
    view = _native("IView", GetDisplayDimensions=lambda: state["displays"])
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "Drawing View2")
    monkeypatch.setattr(drawing, "null_callout", lambda: None)
    monkeypatch.setattr(drawing, "dispatch_array", tuple)
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda _adapter, *, label: calls.append(("rebuild", label)),
    )

    def reset(**changes) -> None:
        state.update(
            displays=(other, fresh),
            annotation_type=4,
            selected=True,
            count=1,
            kind=14,
            picked=fresh,
            types=(14,),
            attached=fresh,
            attached_count=1,
            accepts=(),
            dangling=False,
            InsertGtol=gtol,
            xml_ok=True,
            xml="",
            format=2,
        )
        state.update(changes)
        calls.clear()

    reset()
    return SimpleNamespace(
        adapter=adapter,
        view=view,
        imported=imported,
        fresh=fresh,
        other=other,
        gtol=gtol,
        calls=calls,
        state=state,
        reset=reset,
    )


def test_strap_position_frame_locates_the_strap_width_to_g_on_its_size(view_f_dimension) -> None:
    """#948 ruling R's 0.10 symmetry as a native position frame to G."""
    env = view_f_dimension
    assert drawing._strap_position_frame(env.adapter, env.view, env.imported) is env.gtol
    expected = gtol_frame_signature(gtol_frame_xml(
        "position", ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN["strap position to hub"],
        datums=("G",),
    ))
    assert gtol_frame_signature(env.state["xml"]) == expected
    assert ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_MM["strap position to hub"] == pytest.approx(
        ch_rocker_arm_spec.STRAP_HUB_SYMMETRY
    )
    assert env.calls == [
        "ClearSelection2", ("SelectByID2", ("RD3@Drawing View2", "DIMENSION")),
        "InsertGtol", "SetSymbolXml", "ClearSelection2", ("rebuild", "strap position to G"),
    ]


@pytest.mark.parametrize("defect,message", [
    ({"InsertGtol": None}, "InsertGtol returned nothing"),
    ({"xml_ok": False}, "rejected the frame XML"),
    ({"format": 1}, "frame did not persist"),
    ({"types": (1,)}, "not attached to its dimension"),
    ({"attached": "other"}, "attached to another dimension"),
])
def test_strap_position_frame_refuses_an_unproven_frame(
    view_f_dimension, defect: dict, message: str,
) -> None:
    env = view_f_dimension
    env.reset(**{key: env.other if value == "other" else value for key, value in defect.items()})
    with pytest.raises(RuntimeError, match=message):
        drawing._strap_position_frame(env.adapter, env.view, env.imported)


def test_dimension_frame_left_unattached_is_offered_the_display_then_its_annotation(
    view_f_dimension,
) -> None:
    """A frame inserted on a selected dimension can attach to nothing; it is
    offered the display dimension, then that dimension's annotation."""
    env = view_f_dimension
    env.reset(attached_count=0, accepts=(env.fresh.GetAnnotation(),))
    drawing._strap_position_frame(env.adapter, env.view, env.imported)
    assert [call[1] for call in env.calls if call[0] == "SetAttachedEntities"] == [
        env.fresh,
        env.fresh.GetAnnotation(),
    ]


class _CentrePlaneLine:
    _native_interfaces = ("ISketchLine", "ISketchSegment")

    def __init__(self, start, end, *, keeps_colour=True):
        self.ends = (start, end)
        self.keeps_colour = keeps_colour
        self._colour = 0xFF0000

    def _point(self, xyz):
        return _native("ISketchPoint", X=xyz[0], Y=xyz[1], Z=xyz[2])

    def GetStartPoint2(self):
        return self._point(self.ends[0])

    def GetEndPoint2(self):
        return self._point(self.ends[1])

    @property
    def Color(self):
        return self._colour

    @Color.setter
    def Color(self, value):
        if self.keeps_colour:
            self._colour = value


def _centre_plane_env(monkeypatch, defect=None):
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "Drawing View2")
    rebuilds = []
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda _adapter, *, label: rebuilds.append(label)
    )
    view = _DetailParent()
    monkeypatch.setattr(
        drawing,
        "model_points_in_view",
        lambda _adapter, native, points, **_kwargs: [native.project(p) for p in points],
    )
    created = []

    def create(*xyz):
        if defect == "none":
            return None
        start, end = tuple(xyz[:3]), tuple(xyz[3:])
        if defect == "drift":
            end = (end[0] + 1e-6, *end[1:])
        line = _CentrePlaneLine(start, end, keeps_colour=defect != "colour")
        created.append((tuple(xyz), line))
        return line

    manager = _native("ISketchManager", AddToDB=False, CreateCenterLine=create)
    doc = _native(
        "IModelDoc2",
        "IDrawingDoc",
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: None,
        SketchManager=manager,
    )
    utility = _native("IMathUtility", CreatePoint=_DetailMathPoint)
    adapter = SimpleNamespace(
        currentModel=doc, swApp=_native("ISldWorks", GetMathUtility=lambda: utility)
    )
    return SimpleNamespace(
        adapter=adapter, view=view, created=created, manager=manager, rebuilds=rebuilds
    )


def test_view_f_draws_the_strap_centre_plane_the_g_basic_runs_to(monkeypatch) -> None:
    """The strap frame's located plane, which G's BASIC is dimensioned to
    (#1579): one black centreline on model Z = 0 over the whole view F."""
    env = _centre_plane_env(monkeypatch)
    line = drawing._strap_centre_plane(env.adapter, env.view)
    ((xyz, created),) = env.created
    assert line is created and created.Color == 0
    assert env.manager.AddToDB is False  # restored after the direct-to-DB insert
    assert env.rebuilds == ["view F hub/strap centre plane"]
    assert drawing.CENTRE_PLANE_Y_MM == (-1.0, drawing.TOP_END_Y + 1.0)
    expected = [
        env.view.transform.apply((*env.view.project((0.0, y / 1000.0, 0.0)), 0.0))
        for y in drawing.CENTRE_PLANE_Y_MM
    ]
    assert xyz == pytest.approx((*expected[0], *expected[1]))
    # Both planes are centred on the model's Z = 0: the hub and the strap.
    hub_lower, strap_lower = (
        faces.fields["lower_z"][0] for faces in (drawing.HUB_FACES, drawing.STRAP_FACES)
    )
    assert hub_lower == -ch_rocker_arm_spec.HUB_LENGTH / 2
    assert strap_lower == -ch_rocker_arm_spec.ARM_THICKNESS / 2


@pytest.mark.parametrize(
    "defect,message",
    [
        ("none", "CreateCenterLine returned nothing"),
        ("drift", "GetEndPoint2 sits at"),
        ("colour", "black colour did not persist"),
    ],
)
def test_view_f_centre_plane_refuses_an_unproven_line(
    monkeypatch, defect, message
) -> None:
    env = _centre_plane_env(monkeypatch, defect)
    with pytest.raises(RuntimeError, match=message):
        drawing._strap_centre_plane(env.adapter, env.view)
    assert env.rebuilds == []


def test_datum_g_basic_is_the_half_hub_length_off_the_face_requirements() -> None:
    """#1579 option 1: G is the hub's -Z end face, and the strap frame's
    BASIC runs from it to the strap's centre plane, derived, never typed."""
    assert drawing.HUB_FACE_BASIC_MM == pytest.approx(
        ch_rocker_arm_spec.HUB_LENGTH / 2.0
    )
    places = drawing.HUB_FACES.precision["length"]
    assert ch_rocker_arm_spec.inch_text(drawing.HUB_FACE_BASIC_MM, places) == ".1389"
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert not [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, float)
        and abs(node.value - drawing.HUB_FACE_BASIC_MM) < 0.001
    ]
    assert drawing.HUB_FACES.fields["datum"] == (
        "G",
        (("draw_ch_rocker_arm", "_hub_face_datum"),),
    )
    (g,) = [
        meta.datums["G"] for meta in drawing._FEATURE_METADATA if "G" in meta.datums
    ]
    assert g[0] == {
        "feature": "hub_faces",
        "surface": "-Z hub end face (20X stack registration)",
    }
    assert g[1] == (("draw_ch_rocker_arm", "_hub_face_datum"),)
    assert drawing.STRAP_FACES.fields["position_datums"][0] == ["G"]


def test_datum_g_lands_on_the_minus_z_face_then_basics_and_reads_back(
    monkeypatch,
) -> None:
    view, plane, hub_length, tag, face = (
        object(),
        object(),
        object(),
        object(),
        object(),
    )
    basic_annotation = object()
    basic = SimpleNamespace(GetAnnotation=lambda: basic_annotation)
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append(("circle", center, radius, axis))
        return SimpleNamespace(edge=face)

    monkeypatch.setattr(
        drawing,
        "scan_view_edges",
        lambda native, *, label: (
            SimpleNamespace(circle_at=circle_at) if native is view else None
        ),
    )
    monkeypatch.setattr(
        drawing,
        "_project",
        lambda _adapter, native, points, *, label: [
            _view_f_xy(z * 1000.0, y * 1000.0) for _x, y, z in points
        ],
    )
    monkeypatch.setattr(
        drawing,
        "_hub_face_datum",
        lambda _adapter, native, edge, landing: (
            calls.append(("datum", edge, landing)) or tag
        ),
    )
    monkeypatch.setattr(
        drawing,
        "_hub_face_basic",
        lambda _adapter, native, centre, edge, *, picks: (
            calls.append(("basic", centre, edge, picks)) or basic
        ),
    )
    monkeypatch.setattr(
        drawing,
        "_assert_hub_face_datum_clear",
        lambda _adapter, native_tag, neighbours, *, face_x, label: calls.append(
            ("clear", native_tag, neighbours, face_x)
        ),
    )
    assert drawing._hub_face_datum_g(None, view, plane, hub_length) == (tag, basic)
    face_z = -ch_rocker_arm_spec.HUB_LENGTH / 2.0
    landing = _view_f_xy(face_z, drawing.HUB_FACE_DATUM_LANDING_Y_MM)
    plane_point = _view_f_xy(0.0, drawing.HUB_FACE_DATUM_LANDING_Y_MM)
    assert calls == [
        (
            "circle",
            (0.0, rocker_interface.PIVOT_MID_Y, face_z),
            ch_rocker_arm_spec.HUB_DIA / 2.0,
            (0.0, 0.0, 1.0),
        ),
        ("datum", face, landing),
        ("basic", plane, face, (plane_point, landing)),
        (
            "clear",
            tag,
            {"G BASIC": basic_annotation, "hub width": hub_length},
            landing[0],
        ),
    ]


def test_datum_g_tag_stands_on_its_face_rim_out_right_of_the_landing(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        drawing,
        "add_datum_feature",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "tag",
    )
    face, landing = object(), (0.0856, 0.1674)
    assert drawing._hub_face_datum("adapter", "view", face, landing) == "tag"
    assert calls == [
        (
            ("adapter", "view"),
            {
                "edge_entity": face,
                "leader_attach_xy": landing,
                "symbol_xy": (
                    landing[0] + drawing.HUB_FACE_DATUM_STANDOFF_M,
                    landing[1],
                ),
                "datum": "G",
                "label": "hub -Z end face datum G",
            },
        )
    ]


class _GBasicDisplay:
    _native_interfaces = ("IDisplayDimension",)

    def __init__(self, annotation, *, takes_precision=True):
        self.annotation = annotation
        self.takes_precision = takes_precision
        self.precision = 2
        self.requested = []

    def GetAnnotation(self):
        return self.annotation

    def SetPrecision3(self, *values):
        self.requested.append(values)
        if self.takes_precision:
            self.precision = values[0]

    def GetPrimaryPrecision2(self):
        return self.precision


def _g_basic_env(
    monkeypatch, *, entities=None, types=(10, 1), dangling=False, takes_precision=True
):
    plane, face = object(), object()
    annotation = _native(
        "IAnnotation",
        GetAttachedEntities3=lambda: (
            (plane, face) if entities is None else entities(plane, face)
        ),
        GetAttachedEntityTypes=lambda: types,
        IsDangling=lambda: dangling,
    )
    display = _GBasicDisplay(annotation, takes_precision=takes_precision)
    calls = []
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(
        drawing,
        "add_edge_dimension",
        lambda _adapter, view, **kwargs: (
            calls.append(("dimension", view, kwargs)) or display
        ),
    )
    monkeypatch.setattr(
        drawing,
        "assert_dimension_measures",
        lambda _adapter, dimension, **kwargs: calls.append(
            ("measures", dimension, kwargs)
        ),
    )
    monkeypatch.setattr(
        drawing,
        "set_basic_dimension",
        lambda _adapter, dimension, *, label: calls.append(("basic", dimension, label)),
    )
    adapter = SimpleNamespace(swApp=_APP)
    return SimpleNamespace(
        adapter=adapter, plane=plane, face=face, display=display, calls=calls
    )


def test_datum_g_basic_spans_the_centreline_and_the_minus_z_rim(monkeypatch) -> None:
    env = _g_basic_env(monkeypatch)
    picks = ((0.075, 0.1674), (0.0856, 0.1674))
    result = drawing._hub_face_basic(
        env.adapter, "view", env.plane, env.face, picks=picks
    )
    assert result is env.display
    label = "datum G to strap centre plane BASIC"
    places = drawing.HUB_FACES.precision["length"]
    assert env.calls == [
        (
            "dimension",
            "view",
            {
                "p0": picks[0],
                "p1": picks[1],
                "text_xy": drawing.HUB_FACE_BASIC_TEXT_XY,
                "label": label,
                "orientation": "horizontal",
                "entity_types": ("SKETCHSEGMENT", "EDGE"),
                "entities": (env.plane, env.face),
            },
        ),
        (
            "measures",
            env.display,
            {"expected_mm": drawing.HUB_FACE_BASIC_MM, "label": label},
        ),
        ("basic", env.display, label),
    ]
    assert env.display.requested == [(places, -1, -1, -1)]


@pytest.mark.parametrize(
    "defect,message",
    [
        (
            {"entities": lambda plane, _face: (plane, object())},
            "not the dimension from the centreline",
        ),
        (
            {
                "entities": lambda plane, face: (plane, face, object()),
                "types": (10, 1, 1),
            },
            "not the dimension",
        ),
        ({"types": (10, 10)}, "not the dimension"),
        ({"dangling": True}, "dangling=True"),
        ({"takes_precision": False}, "did not take 4 places"),
    ],
)
def test_datum_g_basic_refuses_an_unproven_span(
    monkeypatch, defect: dict, message: str
) -> None:
    env = _g_basic_env(monkeypatch, **defect)
    with pytest.raises(RuntimeError, match=message):
        drawing._hub_face_basic(
            env.adapter, "view", env.plane, env.face, picks=((0, 0), (0, 0))
        )
    assert not [call for call in env.calls if call[0] == "basic"]


# View F's -Z face prints at x 0.0856; G's letter and triangle out right of
# it, the BASIC's arrows and text above the hub, the hub width's -Z arrow
# under the view (run 20261017T024838726Z's audit numbers).
_G_FACE_X = 0.085585
_G_LETTER = Box(0.0951, 0.1656, 0.0981, 0.1692)
_G_TRIANGLE = Segment(0.0856, 0.1674, 0.0876, 0.1674, "arrow")
_G_BASIC_TEXT = Box(0.0890, 0.1975, 0.1000, 0.2010)
_G_BASIC_ARROW = Segment(0.0856, 0.1965, 0.0826, 0.1965, "arrow")
_HUB_WIDTH_ARROW = Segment(0.0856, 0.1422, 0.0820, 0.1418, "arrow")


def _g_clear_env(
    monkeypatch,
    *,
    letter=_G_LETTER,
    basic_text=_G_BASIC_TEXT,
    dangling=False,
    errors=None,
):
    datum = AnnotationGeometry(
        "datum G",
        "datum",
        "right",
        text_boxes=(letter,) if letter is not None else (),
        segments=(_G_TRIANGLE,),
    )
    basic = AnnotationGeometry(
        "dim RD9",
        "dim",
        "right",
        text_boxes=(basic_text,),
        segments=(_G_BASIC_ARROW, Segment(0.075, 0.1965, 0.0856, 0.1965, "dim-line")),
    )
    width = AnnotationGeometry(
        "dim HubLength",
        "dim",
        "right",
        text_boxes=(Box(0.030, 0.150, 0.050, 0.160),),
        segments=(_HUB_WIDTH_ARROW,),
    )
    geometry = {"G": datum, "RD9": basic, "HubLength": width}
    records = {
        "tag": {"name": "G"},
        "basic": {"name": "RD9"},
        "width": {"name": "HubLength"},
    }
    tag_annotation = _native("IAnnotation", IsDangling=lambda: dangling)
    tag = _native("IDatumTag", GetAnnotation=lambda: tag_annotation)
    monkeypatch.setattr(drawing, "_early_bound", _bind_owner)
    monkeypatch.setattr(
        drawing,
        "_Reader",
        lambda _adapter: SimpleNamespace(take_errors=lambda: errors or {}),
    )
    monkeypatch.setattr(
        drawing,
        "_dump_annotation",
        lambda _reader, raw: records["tag"] if raw is tag_annotation else records[raw],
    )
    monkeypatch.setattr(drawing, "calibrate_sheet_advance", lambda _records: 0.6)
    monkeypatch.setattr(
        drawing,
        "annotation_geometry",
        lambda record, *, owner, advance: geometry[record["name"]],
    )
    return tag


def _clear_g(tag):
    return drawing._assert_hub_face_datum_clear(
        None,
        tag,
        {"G BASIC": "basic", "hub width": "width"},
        face_x=_G_FACE_X,
        label="hub -Z end face datum G",
    )


def test_datum_g_read_back_clear_of_its_neighbours_passes(monkeypatch) -> None:
    assert _clear_g(_g_clear_env(monkeypatch)) == _G_LETTER


def _moved(box: Box, dx: float = 0.0, dy: float = 0.0) -> Box:
    return Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)


@pytest.mark.parametrize(
    "change,message",
    [
        # Collapsed onto the BASIC's arrow, as the hub-width tag once was.
        ({"letter": Box(0.0870, 0.1950, 0.0900, 0.1986)}, "crowds the G BASIC"),
        (
            {"letter": _moved(_G_LETTER, dx=-0.0140)},
            "letter not out right of the -Z face",
        ),
        ({"letter": _moved(_G_LETTER, dx=0.0062)}, "front view's left witness"),
        ({"basic_text": Box(0.0700, 0.1690, 0.0850, 0.1720)}, "crowds the G BASIC"),
        ({"basic_text": _moved(_G_BASIC_TEXT, dx=0.0040)}, "G BASIC text runs onto"),
        ({"letter": None}, "no printed letter"),
        ({"errors": {"tag": "unreadable"}}, "cannot measure its ink"),
        ({"dangling": True}, "dangling after its placement"),
    ],
)
def test_datum_g_that_does_not_read_back_clear_fails_the_leaf(
    monkeypatch, change: dict, message: str
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _clear_g(_g_clear_env(monkeypatch, **change))


def test_hub_position_frame_locates_the_hub_od_to_a_on_its_own_diameter(view_f_dimension) -> None:
    """regate-r1 #2: the hub OD's coaxiality is a native Ø position frame to A
    under its Ø.400 in detail D, the zone the hub wall minimum is built on."""
    env = view_f_dimension
    assert drawing._hub_position_frame(env.adapter, env.view, env.imported) is env.gtol
    zone = ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN["hub OD position to bore"]
    assert float(zone) * 25.4 == pytest.approx(ch_rocker_arm_spec.HUB_COAXIALITY_DIA)
    assert zone == ".004"
    assert drawing.HUB_OD.fields["position_datums"][0] == ["A"]
    expected = gtol_frame_signature(gtol_frame_xml("position", zone, datums=("A",), diameter=True))
    assert gtol_frame_signature(env.state["xml"]) == expected
    # The zone is diametral: the same frame without Ø is a different signature.
    assert expected != gtol_frame_signature(gtol_frame_xml("position", zone, datums=("A",)))
    assert env.calls == [
        "ClearSelection2", ("SelectByID2", ("RD3@Drawing View2", "DIMENSION")),
        "InsertGtol", "SetSymbolXml", "ClearSelection2", ("rebuild", "hub OD position to A"),
    ]


@pytest.mark.parametrize("defect,message", [
    ({"InsertGtol": None}, "hub OD position to A: InsertGtol returned nothing"),
    ({"format": 1}, "frame did not persist"),
    ({"attached": "other"}, "attached to another dimension"),
])
def test_hub_position_frame_refuses_an_unproven_frame(view_f_dimension, defect: dict, message: str) -> None:
    env = view_f_dimension
    env.reset(**{key: env.other if value == "other" else value for key, value in defect.items()})
    with pytest.raises(RuntimeError, match=message):
        drawing._hub_position_frame(env.adapter, env.view, env.imported)


def test_projection_barrier_is_void_and_precedes_native_math(bound, monkeypatch):
    events = []
    view = _native("IView", UpdateViewDisplayGeometry=lambda: events.append("barrier"))
    def project(_adapter, actual, points, **_kwargs):
        assert actual is view and events == ["barrier"]
        return [(0.180, 0.095)]
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    assert drawing._project(object(), view, [(0, 0, 0)], label="D physical centre") == [(0.180, 0.095)]


class _DetailCircle:
    """Native method-shaped labels, void setter, two out-double getter."""
    _native_interfaces = ("IDetailCircle",)
    def __init__(self, label, *, ignored=False):
        self.label, self.ignored = label, ignored
        self.xy = (0.0, 0.0)

    def GetLabel(self):
        return self.label

    def SetLabelPosition(self, x, y):
        if not self.ignored:
            self.xy = (x, y)

    def GetLabelPosition(self):
        return self.xy


@pytest.mark.parametrize("labels", [("E", "D"), ("D",), ("D", "D"), ("D", "E", "F")])
def test_detail_letters_bind_by_exact_native_label_not_enumeration(bound, monkeypatch, labels):
    circles = [_DetailCircle(label) for label in labels]
    front = _native("IView", GetDetailCircles=lambda: circles)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    if labels == ("E", "D"):
        drawing._place_detail_letters(object(), front)
        assert {circle.label: circle.xy for circle in circles} == drawing.DETAIL_LETTER_XY
    else:
        with pytest.raises(RuntimeError, match="exactly D/E"):
            drawing._place_detail_letters(object(), front)


def test_detail_letter_refuses_a_silently_ignored_void_setter(bound, monkeypatch):
    circles = [_DetailCircle("D"), _DetailCircle("E", ignored=True)]
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="native letter stayed"):
        drawing._place_detail_letters(object(), _native("IView", GetDetailCircles=lambda: circles))


class _DetailTransform:
    """Nonidentity native sketch transform; inverse maps back to sheet units."""
    _native_interfaces = ("IMathTransform",)
    __slots__ = ("scale", "translation", "bad_inverse", "bad_matrix", "inverse_calls")

    def __init__(self, scale=2.0, translation=(0.013, -0.007, 0.0)):
        self.scale, self.translation = scale, translation
        self.bad_inverse = self.bad_matrix = False
        self.inverse_calls = 0

    @property
    def ArrayData(self):
        return () if self.bad_matrix else (
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            *self.translation, self.scale, 0.0, 0.0, 0.0,
        )

    def Inverse(self):
        self.inverse_calls += 1
        if self.bad_inverse:
            return None
        return _DetailTransform(1.0 / self.scale, tuple(-v / self.scale for v in self.translation))

    def IInverse(self):
        raise AssertionError("R11 IDispatch rejects IInverse; use the automation Inverse method")

    def apply(self, xyz):
        return tuple(xyz[i] * self.scale + self.translation[i] for i in range(3))


class _DetailMathPoint:
    _native_interfaces = ("IMathPoint",)
    __slots__ = ("_coordinates",)

    def __init__(self, values):
        self._coordinates = tuple(values.value)  # VARIANT input, native tuple getter.
        assert len(self._coordinates) == 3

    @property
    def ArrayData(self):
        return self._coordinates

    def MultiplyTransform(self, transform):
        point = object.__new__(_DetailMathPoint)
        point._coordinates = transform.apply(self._coordinates)
        return point


class _DetailParent:
    _native_interfaces = ("IView",)
    __slots__ = ("transform", "ScaleRatio", "projection_scale", "display_updates")

    def __init__(self):
        self.transform = _DetailTransform()
        self.ScaleRatio = (1.0, 2.0)
        self.projection_scale = 0.5
        self.display_updates = 0

    def GetSketch(self):
        return _native("ISketch", ModelToSketchTransform=self.transform)

    @property
    def ModelToViewTransform(self):
        # Synthetic NEW cross-view hop; the original sketch hop is independent.
        assert self.display_updates > 0
        return _DetailTransform(self.projection_scale, (0.180, 0.175, 0.0))

    def UpdateViewDisplayGeometry(self):
        self.display_updates += 1

    def project(self, xyz):
        return (0.180 + xyz[0] * self.projection_scale,
                0.175 + xyz[1] * self.projection_scale)


class _DetailArc:
    """ISketchArc slice of the same native circle as its selectable segment."""

    _native_interfaces = ("ISketchArc",)

    def __init__(self, segment):
        self.segment = segment

    def IsCircle(self):
        return self.segment.complete  # Native INT 1/0.

    def GetCenterPoint2(self):
        centre = self.segment.centre
        if centre is None:
            return None
        return _native("ISketchPoint", X=centre[0], Y=centre[1], Z=centre[2])

    def GetRadius(self):
        return self.segment.radius


class _DetailProfile:
    _native_interfaces = ("ISketchSegment", "ISketchArc")
    __slots__ = ("centre", "radius", "sketch", "complete", "segment_type", "selectable")

    def __init__(self, centre, radius, sketch):
        self.centre, self.radius, self.sketch = centre, radius, sketch
        self.complete, self.segment_type, self.selectable = 1, 1, True

    def _native_query(self, interface):
        return self if interface == "ISketchSegment" else _DetailArc(self)

    def GetType(self):
        return self.segment_type

    def GetSketch(self):
        return self.sketch

    def Select4(self, _append, _data):
        return self.selectable


class _DetailCropCircle:
    _native_interfaces = ("IDetailCircle",)
    __slots__ = ("label", "profiles", "NoOutline", "_jagged", "full", "display", "style", "style_ok", "style_writes")

    def __init__(self, label, profile, *, style=None):
        self.label, self.profiles = label, (profile,)
        self.NoOutline = label == "D"
        self._jagged, self.full, self.display = False, True, 1
        self.style = drawing.DETAIL_STYLE[label] if style is None else style
        self.style_ok, self.style_writes = True, []

    def GetStyle(self):
        return self.style

    def SetStyle(self, style):
        self.style_writes.append(style)
        if self.style_ok is True:
            self.style = style
        return self.style_ok is not False

    @property
    def JaggedOutline(self):
        if self.NoOutline:
            raise AssertionError("JaggedOutline is undefined with NoOutline=True")
        return self._jagged

    @JaggedOutline.setter
    def JaggedOutline(self, value):
        self._jagged = value

    def GetLabel(self):
        return self.label

    def GetDisplay(self):
        return self.display

    def HasFullOutline(self):
        if self.NoOutline:
            raise AssertionError("HasFullOutline is undefined with NoOutline=True")
        return self.full

    def GetProfileItems(self):
        return self.profiles


class _DetailView:
    """Native bbox padding/offset is independent of the persisted crop circle."""
    _native_interfaces = ("IView",)
    __slots__ = ("parent", "radius", "defect", "_position", "physical",
                 "_scale_ratio", "UseParentScale", "UseSheetScale", "events",
                 "crop_circle", "padding", "bbox_offset", "model_centre", "notes", "annotations", "outline_reads")

    def __init__(self, parent, *, label="D", defect=None, padding=0.01096794, bbox_offset=(0.0, 0.005)):
        self.parent, self.defect = parent, defect
        self.model_centre, radius_mm = drawing._detail_fence(label)
        ratio = drawing.HUB_SCALE if label == "D" else drawing.END_SCALE
        self.radius = radius_mm / 1000.0 * ratio[0] / ratio[1]
        self.Position = (0.210, 0.110)
        self.physical = self._position
        self._scale_ratio = ratio
        self.UseParentScale = False
        self.UseSheetScale = 0
        self.events = []
        self.crop_circle = None
        self.padding, self.bbox_offset = padding, bbox_offset
        self.notes, self.annotations = [], []
        self.outline_reads = 0

    @property
    def Position(self):
        return None if self.defect == "missing-position" else self._position

    @Position.setter
    def Position(self, value):
        self._position = tuple(value)
        assert len(self._position) == 2

    @property
    def ScaleRatio(self):
        return self._scale_ratio

    @ScaleRatio.setter
    def ScaleRatio(self, value):
        # Native property puts receive VARIANT; getters expose a SAFEARRAY tuple.
        ratio = tuple(value.value)
        assert len(ratio) == 2
        self._scale_ratio = (1.0, 2.0) if self.defect == "scale" else ratio

    @property
    def ModelToViewTransform(self):
        assert self.events[-1] == "barrier"
        scale = self._scale_ratio[0] / self._scale_ratio[1]
        translation = tuple(self.physical[i] - self.model_centre[i] * scale for i in range(2))
        return _DetailTransform(scale, (*translation, 0.0))

    def GetBaseView(self):
        return object() if self.defect == "parent" else self.parent

    def GetDetail(self):
        return self.crop_circle

    def GetNotes(self):
        return tuple(self.notes)

    def GetAnnotationCount(self):
        return len(self.annotations)

    def GetAnnotations(self):
        return tuple(self.annotations)

    def project(self, xyz):
        assert self.events[-1] == "barrier"
        scale = self._scale_ratio[0] / self._scale_ratio[1]
        return tuple(self.physical[i] + (xyz[i] - self.model_centre[i]) * scale for i in range(2))

    def GetOutline(self):
        self.outline_reads += 1
        if self.defect == "invalid-bbox":
            return (0.0, 0.0, float("nan"), 1.0)
        x, y = (self._position[i] + self.bbox_offset[i] for i in range(2))
        radius = self.radius + self.padding
        return (x - radius, y - radius, x + radius, y + radius)

    def SetViewPosition(self, xy, _children):
        position = tuple(xy.value)
        assert len(position) == 2
        self.events.append("move")
        if self.defect == "move":
            return False
        if self.defect != "ignored-move":
            self.Position = position
        return True

    def UpdateViewDisplayGeometry(self):
        self.events.append("barrier")
        if self.defect != "stale":
            self.physical = self._position


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("defect", [None, "activation", "parent", "scale", "move", "ignored-move", "stale", "missing-position", "fence", "selection", "creation", "source-radius", "source-centre", "profile-radius", "profile-centre", "near-profile-centre", "partial", "missing-profile", "outline-flags", "projection-scale", "ignored-style", "refused-style", "lost-style"])
def test_native_detail_fences_parent_links_scale_and_settled_projection(bound, monkeypatch, label, defect):
    parent = _DetailParent()
    if defect == "projection-scale":
        parent.projection_scale = 0.7
    detail = _DetailView(parent, label=label, defect=defect)
    created = []
    class Manager:
        _native_interfaces = ("ISketchManager",)
        __slots__ = ("AddToDB",)
        def __init__(self):
            self.AddToDB = False
        def CreateCircle(self, *args):
            centre, rim = tuple(args[:3]), tuple(args[3:])
            circle = _DetailProfile(centre, math.dist(centre, rim), parent.GetSketch())
            circle.selectable = defect != "selection"
            if defect == "source-radius":
                circle.radius *= 1.5
            elif defect == "source-centre":
                circle.centre = (centre[0] + 0.01, centre[1], centre[2])
            created.append(circle)
            return None if defect == "fence" else circle
    class SelectData:
        _native_interfaces = ("ISelectData",)
        __slots__ = ("View",)
    manager = Manager()
    calls = []
    def create(*args):
        calls.append(args)
        source = created[0]
        profile = _DetailProfile(source.centre, source.radius, source.sketch)
        if defect == "profile-radius":
            profile.radius *= 1.5
        elif defect == "profile-centre":
            profile.centre = (profile.centre[0] + 0.01, profile.centre[1], profile.centre[2])
        elif defect == "near-profile-centre":
            shift = 0.00002 if label == "D" else 0.00004
            profile.centre = (profile.centre[0] + shift, profile.centre[1], profile.centre[2])
        elif defect == "partial":
            profile.complete = 0
        # The style argument persists unless the defect says it was ignored.
        detail.crop_circle = _DetailCropCircle(
            label, profile, style=1 if defect in ("ignored-style", "refused-style", "lost-style") else args[3],
        )
        if defect == "missing-profile":
            detail.crop_circle.profiles = ()
        elif defect == "outline-flags":
            detail.crop_circle.NoOutline = label != "D"
        elif defect == "refused-style":
            detail.crop_circle.style_ok = False
        elif defect == "lost-style":
            detail.crop_circle.style_ok = "lost"  # reports success, keeps the wrong style
        return None if defect == "creation" else detail
    doc = _native("IModelDoc2", "IDrawingDoc", ActivateView=lambda _name: defect != "activation", ClearSelection2=lambda _all: None,
    SketchManager=manager,
    SelectionManager=_native("ISelectionMgr", CreateSelectData=SelectData),
    CreateDetailViewAt4=create,)
    adapter = SimpleNamespace(
        currentModel=doc, swApp=_native("ISldWorks", IsSame=_APP.IsSame, GetMathUtility=lambda: _native("IMathUtility", CreatePoint=_DetailMathPoint)),
    )
    monkeypatch.setattr(drawing, "model_points_in_view",
                        lambda _adapter, view, points, **_kwargs: [view.project(point) for point in points])
    monkeypatch.setattr(drawing, "view_name", lambda *_a: "front")
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_a: None)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    centre, radius_mm = drawing._detail_fence(label)
    target = drawing.HUB_CENTER if label == "D" else drawing.END_CENTER
    scale = drawing.HUB_SCALE if label == "D" else drawing.END_SCALE
    kwargs = dict(centre=centre, radius_mm=radius_mm, target=target, scale=scale, label=label)
    if defect in (None, "ignored-style"):
        assert drawing._create_detail(adapter, parent, **kwargs) is detail
        assert detail.Position == pytest.approx(target, rel=0.0, abs=1e-12)
        assert detail.physical == pytest.approx(target, rel=0.0, abs=1e-12)
        assert tuple(detail.ScaleRatio) == scale
        assert detail.events.count("move") == 1
        assert detail.events.count("barrier") >= 4
        assert detail.GetOutline()[3] > target[1] + detail.radius
        assert created[0].radius == pytest.approx(radius_mm / 1000.0)  # Nonidentity sketch scale 2.
        assert parent.transform.inverse_calls >= 2
        # Both letters lead to their source circles; E is not a floating label.
        assert calls[0][3] == drawing.DETAIL_STYLE[label] == 2
        assert calls[0][7:] == (1, label == "E", False, label == "D", 5)
        # The documented setter runs only when creation ignored the style.
        expected_writes = [drawing.DETAIL_STYLE[label]] if defect == "ignored-style" else []
        assert detail.crop_circle.style_writes == expected_writes
        assert detail.crop_circle.GetStyle() == drawing.DETAIL_STYLE[label]
    else:
        with pytest.raises(RuntimeError):
            drawing._create_detail(adapter, parent, **kwargs)
    assert manager.AddToDB is False


def _native_crop_fixture(monkeypatch, label, *, centre=None, defect=None):
    """Readback fixture, including persisted geometry and a padded native bbox."""
    parent = _DetailParent()
    view = _DetailView(parent, label=label, defect=defect)
    view.Position = centre or (drawing.HUB_CENTER if label == "D" else drawing.END_CENTER)
    view.physical = view.Position
    source_centre, source_radius = drawing._detail_fence(label)
    xy = parent.project(source_centre)
    profile = _DetailProfile(
        parent.transform.apply((*xy, 0.0)),
        source_radius / 1000.0 * 0.5 * parent.transform.scale,
        parent.GetSketch(),
    )
    view.crop_circle = _DetailCropCircle(label, profile)
    adapter = SimpleNamespace(
        swApp=_native("ISldWorks", GetMathUtility=lambda: _native("IMathUtility", CreatePoint=_DetailMathPoint)),
        currentModel=_native("IModelDoc2", GraphicsRedraw2=lambda: None),
    )
    monkeypatch.setattr(drawing, "model_points_in_view",
                        lambda _adapter, native, points, **_kwargs: [native.project(p) for p in points])
    return adapter, view


def test_detail_transform_fake_refuses_native_inverse_but_supports_automation():
    transform = _DetailTransform()
    with pytest.raises(AssertionError, match="IDispatch rejects IInverse"):
        transform.IInverse()
    inverse = transform.Inverse()
    assert inverse is not None
    assert inverse.apply(transform.apply((0.180, 0.175, 0.0))) == pytest.approx((0.180, 0.175, 0.0))
    assert transform.inverse_calls == 1
    transform.bad_inverse = True
    assert transform.Inverse() is None


@pytest.mark.parametrize("label", ["D", "E"])
def test_crop_reads_persisted_circle_not_padded_or_offset_native_view_bbox(bound, monkeypatch, label):
    adapter, view = _native_crop_fixture(monkeypatch, label)
    crop = drawing._detail_crop(adapter, view, label=label)
    assert view.outline_reads == 1
    x, y = view.physical
    assert crop == pytest.approx((x - view.radius, y - view.radius, x + view.radius, y + view.radius))
    bbox = view.GetOutline()
    assert bbox[2] - bbox[0] > crop[2] - crop[0] + 0.020
    assert (bbox[1] + bbox[3]) / 2.0 == pytest.approx(y + 0.005)
    arc = _bind_owner(view.crop_circle.profiles[0], "ISketchArc")
    assert arc.GetRadius() != pytest.approx(view.radius)
    assert view.parent.ScaleRatio == (1.0, 2.0)  # Parent .5, native D 4 / E 2.
    assert view.parent.transform.inverse_calls == 1


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("no_outline", [None, 0, 1, False, True])
def test_detail_outline_mode_is_label_owned_and_identity_strict(
    bound, monkeypatch, label, no_outline,
):
    adapter, view = _native_crop_fixture(monkeypatch, label)
    view.crop_circle.NoOutline = no_outline
    if no_outline is (label == "D"):
        drawing._detail_crop(adapter, view, label=label)
    else:
        with pytest.raises(RuntimeError, match="NoOutline"):
            drawing._detail_crop(adapter, view, label=label)


@pytest.mark.parametrize("defect", ["jagged", "partial-outline"])
def test_e_retains_full_outline_while_d_skips_undefined_flag_reads(
    bound, monkeypatch, defect,
):
    adapter, end = _native_crop_fixture(monkeypatch, "E")
    end.crop_circle.JaggedOutline = defect == "jagged"
    end.crop_circle.full = defect != "partial-outline"
    with pytest.raises(RuntimeError, match="outline flags"):
        drawing._detail_crop(adapter, end, label="E")
    adapter, hub = _native_crop_fixture(monkeypatch, "D")
    # D's fake refuses these native reads altogether, per their documented scope.
    hub.crop_circle.JaggedOutline = True
    hub.crop_circle.full = False
    drawing._detail_crop(adapter, hub, label="D")



@pytest.mark.parametrize("label", ["D", "E"])
def test_crop_reads_one_current_outline_after_both_geometry_barriers(bound, monkeypatch, label):
    adapter, view = _native_crop_fixture(monkeypatch, label)
    current_outline = _DetailView.GetOutline
    reads = []
    def initially_stale_outline(native):
        if native is not view:
            return current_outline(native)
        reads.append((native.parent.display_updates, native.events.count("barrier")))
        if native.parent.display_updates == 0 or not native.events:
            # Historical swing B had an undersized first-create outline. This
            # box cannot contain the circle; only a display barrier refreshes it.
            x, y = native.physical
            half = native.radius * 0.4
            return (x - half, y - half, x + half, y + half)
        return current_outline(native)
    monkeypatch.setattr(_DetailView, "GetOutline", initially_stale_outline)
    crop = drawing._detail_crop(adapter, view, label=label)
    assert reads == [(1, 1)]
    assert view.outline_reads == 1
    x, y = view.physical
    assert crop == pytest.approx((x - view.radius, y - view.radius, x + view.radius, y + view.radius))


def test_crop_preserves_actual_native_geometry_within_readback_tolerance(bound, monkeypatch):
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    profile = view.crop_circle.profiles[0]
    profile.centre = (profile.centre[0] + 0.00002, *profile.centre[1:])
    profile.radius += 0.00002
    # Inverse sketch scale 2, then detail/parent magnification 8: 80 um on sheet.
    crop = drawing._detail_crop(adapter, view, label="D")
    x, y = view.physical[0] + 0.00008, view.physical[1]
    radius = view.radius + 0.00008
    assert crop == pytest.approx((x - radius, y - radius, x + radius, y + radius), abs=1e-12)
    assert (crop[0] + crop[2]) / 2.0 != pytest.approx(view.physical[0], abs=1e-6)
    assert (crop[2] - crop[0]) / 2.0 != pytest.approx(view.radius, abs=1e-6)


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("edge", range(4))
@pytest.mark.parametrize("delta", [-0.000051, 0.000051])
def test_crop_refuses_shared_box_drift_both_directions(bound, monkeypatch, label, edge, delta):
    adapter, view = _native_crop_fixture(monkeypatch, label)
    actual_reader = drawing.read_circular_detail_crop
    def wrong_box(*args, **kwargs):
        readback = actual_reader(*args, **kwargs)
        crop = list(readback.crop)
        crop[edge] += delta
        return replace(readback, crop=tuple(crop))
    monkeypatch.setattr(drawing, "read_circular_detail_crop", wrong_box)
    with pytest.raises(RuntimeError, match="shared/independent legacy crop mismatch"):
        drawing._detail_crop(adapter, view, label=label)


@pytest.mark.parametrize("delta", [-0.000049, 0.000049])
def test_crop_accepts_shared_box_drift_only_within_unchanged_tolerance(bound, monkeypatch, delta):
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    actual_reader = drawing.read_circular_detail_crop
    def within_tolerance(*args, **kwargs):
        readback = actual_reader(*args, **kwargs)
        return replace(readback, crop=tuple(v + delta for v in readback.crop))
    monkeypatch.setattr(drawing, "read_circular_detail_crop", within_tolerance)
    x, y = view.physical
    expected = (x - view.radius, y - view.radius, x + view.radius, y + view.radius)
    assert drawing._detail_crop(adapter, view, label="D") == pytest.approx(
        tuple(v + delta for v in expected), abs=1e-12,
    )


@pytest.mark.parametrize("defect", [
    "radius", "nan-radius", "zero-radius", "centre", "off-sheet-plane", "missing-centre", "partial", "segment",
    "empty", "missing-items", "multiple", "missing-segment",
    "missing-circle", "missing-parent", "no-outline", "display", "label", "style",
    "inverse", "matrix", "missing-sketch", "missing-transform", "missing-utility", "parent-scale", "parent-scale-shape", "projection-scale",
    "detail-scale", "detail-scale-shape", "parent-scale-link", "sheet-scale-link", "invalid-bbox",
])
def test_native_crop_refuses_wrong_persisted_geometry_flags_or_coordinate_frame(bound, monkeypatch, defect):
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    circle, parent = view.crop_circle, view.parent
    profile = circle.profiles[0]
    if defect == "radius":
        profile.radius *= 1.5
    elif defect == "nan-radius":
        profile.radius = float("nan")
    elif defect == "zero-radius":
        profile.radius = 0.0
    elif defect == "centre":
        profile.centre = (profile.centre[0] + 0.01, *profile.centre[1:])
    elif defect == "off-sheet-plane":
        profile.centre = (*profile.centre[:2], 0.01)
    elif defect == "missing-centre":
        profile.centre = None
    elif defect == "partial":
        profile.complete = 0
    elif defect == "segment":
        profile.segment_type = 0
    elif defect in ("empty", "missing-items", "multiple"):
        circle.profiles = {"empty": (), "missing-items": None, "multiple": (profile, profile)}[defect]
    elif defect == "missing-segment":
        circle.profiles = (None,)
    elif defect == "missing-circle":
        view.crop_circle = None
    elif defect == "missing-parent":
        view.parent = None
    elif defect == "no-outline":
        circle.NoOutline = False
    elif defect == "display":
        circle.display = 0
    elif defect == "label":
        circle.label = "X"
    elif defect == "style":
        circle.style = 0  # D's leader lost: the fence no longer names its detail
    elif defect == "inverse":
        parent.transform.bad_inverse = True
    elif defect == "matrix":
        parent.transform.bad_matrix = True
    elif defect == "missing-sketch":
        profile.sketch = None
    elif defect == "missing-transform":
        profile.sketch.ModelToSketchTransform = None
    elif defect == "missing-utility":
        adapter.swApp.GetMathUtility = lambda: None
    elif defect == "parent-scale":
        parent.ScaleRatio = (1.0, 1.0)
    elif defect == "parent-scale-shape":
        parent.ScaleRatio = None
    elif defect == "projection-scale":
        parent.projection_scale = 0.7
    elif defect == "detail-scale":
        view._scale_ratio = (1.0, 2.0)
    elif defect == "detail-scale-shape":
        view._scale_ratio = None
    elif defect == "parent-scale-link":
        view.UseParentScale = True
    elif defect == "sheet-scale-link":
        view.UseSheetScale = 1
    elif defect == "invalid-bbox":
        view.defect = "invalid-bbox"
    with pytest.raises(RuntimeError):
        drawing._detail_crop(adapter, view, label="D")


def _native_sheet(*, top=0.066, scale_retained=True, rule=True, missing_endpoint=None):
    template = drawing.DRAWING_TEMPLATES[drawing.SPEC.layout]
    def line(y):
        return _native("ISketchSegment", "ISketchLine", GetType=lambda: 0, GetStartPoint2=lambda: None if missing_endpoint == "start" else _native("ISketchPoint", X=template.title_block_left_m, Y=y), GetEndPoint2=lambda: None if missing_endpoint == "end" else _native("ISketchPoint", X=template.width_m - 0.0127, Y=y))
    state = {"scale": (1.0, 1.0)}
    def set_scale(numerator, denominator, _position, _text):
        if scale_retained:
            state["scale"] = (numerator, denominator)
        return True
    return _native("ISheet", SetScale=set_scale, GetProperties2=lambda: (0, 0, *state["scale"], 0, 0.4318, 0.2794, 0),
    GetTemplateSketch=lambda: _native("ISketch", GetSketchSegments=lambda: [line(top), line(top / 2)] if rule else []),)


@pytest.mark.parametrize("endpoint", ["start", "end"])
def test_title_block_rule_refuses_null_native_endpoint(bound, endpoint):
    with pytest.raises(RuntimeError, match="native title-block rule endpoint unavailable"):
        drawing._title_block_top(SimpleNamespace(), _native_sheet(missing_endpoint=endpoint))


class _CaptionTextFormat:
    """Read-only test surface for the native properties the probe reads."""

    _native_interfaces = ("ITextFormat",)

    CharHeight = property(lambda self: 0.0035)
    CharHeightInPts = property(lambda self: 10)
    TypeFaceName = property(lambda self: "Arial")
    LineSpacing = property(lambda self: 1.0)

    def IsHeightSpecifiedInPts(self):
        return False


class _CaptionNote(_FakeNote):
    def __init__(self, label, *, height=0.007):
        super().__init__((0.16 if label == "D" else 0.30, 0.07), height)
        self.label = label
        self._linked = "<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>"
        self.annotation.SetPosition2 = self.annotation.SetPosition
        self.annotation.GetTextFormatCount = lambda: 1
        self.annotation.GetTextFormat = lambda index: _CaptionTextFormat() if index == 0 else None
        self.annotation.GetUseDocTextFormat = lambda index: index == 0
        self.data = _ClearanceDisplayData([
            {"t": f"DETAIL {label}", "pos": [0.30, 0.07, 0.0], "h": 0.0035},
            {"t": "SCALE 2:1", "pos": [0.30, 0.065, 0.0], "h": 0.0035},
        ], [])
        self.annotation.GetDisplayData = lambda: self.data

    PropertyLinkedText = property(lambda self: self._linked, lambda self, value: setattr(self, "_linked", value))
    HasMultipleFonts = property(lambda self: False)

    def GetText(self):
        return f"DETAIL {self.label}\r\nSCALE 2:1"

    def GetHeight(self):
        return 0.0035

    def GetHeightInPoints(self):
        return 10

    def GetExtent(self):
        extent = list(super().GetExtent())
        extent[3] = extent[0] + 0.03145
        return tuple(extent)


def test_both_caption_diagnostics_log_native_text_formats_and_display_geometry(bound, monkeypatch):
    redraws = []
    adapter = SimpleNamespace(currentModel=_native("IModelDoc2", GraphicsRedraw2=lambda: redraws.append("redraw")))
    sheet = _native_sheet()
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    for label in ("D", "E"):
        note = _CaptionNote(label)
        view = _native("IView", GetNotes=lambda: (note,))
        drawing._record_detail_caption(adapter, view, sheet, label=label, stage="before guards")
    assert len(logs) == 2
    assert redraws == []
    for label, log in zip(("D", "E"), logs, strict=True):
        report = json.loads(log.split("native diagnostics: ", 1)[1])
        assert report["label"] == label and report["native_note_count"] == 1
        assert report["native_title_rule_top_m"] == 0.066
        assert report["native_read_errors"] == {}
        (note,) = report["notes"]
        assert note["native_property_linked_text"] == "<VLNAME> <VLLABEL>\r\nSCALE <VLSCALE>"
        assert note["native_get_text"] == f"DETAIL {label}\r\nSCALE 2:1"
        assert note["resolved_line_count"] == 2
        assert note["native_has_multiple_fonts"] is False
        assert note["native_text_format_count"] == 1
        assert note["native_text_formats"] == [{
            "index": 0, "use_doc_text_format": True, "char_height_m": 0.0035,
            "char_height_pts": 10, "is_height_specified_in_pts": False, "type_face_name": "Arial",
            "line_spacing": 1.0,
        }]
        assert len(note["native_note_get_extent"]) == 6
        assert note["native_note_get_height"] == 0.0035
        assert note["native_note_get_height_in_points"] == 10
        assert note["display_fragment_count"] == 2
        assert note["native_display_fragment_positions"] == [[0.30, 0.07, 0.0], [0.30, 0.065, 0.0]]
        assert [fragment["h"] for fragment in note["native_display_data"]["texts"]] == [0.0035, 0.0035]
        assert [fragment["font"] for fragment in note["native_display_data"]["texts"]] == ["Arial", "Arial"]
        assert note["display_decoder_estimate"]["extent_m"] is not None
        assert "not printed glyph ink" in note["display_decoder_estimate"]["coordinate_basis"]


@pytest.mark.parametrize("accessor,field", [
    ("GetTextHeightAtIndex", "h"), ("GetTextFontAtIndex", "font"),
    ("GetTextLineSpacingAtIndex", "ls"),
])
def test_caption_probe_never_reports_reader_defaults_as_native_fields(bound, monkeypatch, accessor, field):
    note = _CaptionNote("E")
    setattr(note.data, accessor, lambda _index: None)
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    logs, captures = [], []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", lambda *args, **kwargs: captures.append((args, kwargs)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    assert captures == []  # A diagnostic refusal cannot fail a valid native box.
    report = json.loads(next(log for log in logs if "native diagnostics: " in log).split("native diagnostics: ", 1)[1])
    (entry,) = report["notes"]
    assert entry["native_display_read_errors"][accessor] > 0
    assert all(fragment[field] is None for fragment in entry["native_display_data"]["texts"])
    assert entry["display_decoder_estimate"]["extent_m"] is None


def test_both_caption_probes_precede_the_first_caption_guard_in_build():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    probes = [node for node in calls if node.func.id == "_record_detail_caption"]
    seats = [node for node in calls if node.func.id == "_seat_detail_caption"]
    assert len(probes) == len(seats) == 2
    assert [next(k.value.value for k in node.keywords if k.arg == "label") for node in probes] == ["D", "E"]
    assert max(node.lineno for node in probes) < min(node.lineno for node in seats)


@pytest.mark.parametrize("capture_fails", [False, True])
def test_caption_failure_retains_original_exception_and_captures_before_close(bound, monkeypatch, capture_fails):
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [_CaptionNote("E")]
    original = RuntimeError("native extent refused")
    events, warnings = [], []
    def extent(*_args, **_kwargs):
        events.append("guard")
        raise original
    def capture(current_adapter, label, message, **context):
        events.append("capture")
        assert current_adapter is adapter
        assert label == "ch-rocker-arm-detail-E-caption"
        assert message == str(original) and context["exception"] is original
        assert context["sheet_png"] is True
        if capture_fails:
            raise OSError("forensic disk refused")
        raise original
    monkeypatch.setattr(drawing, "_note_extent", extent)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(drawing._telemetry, "warn", warnings.append)
    with pytest.raises(RuntimeError) as caught:
        try:
            drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
        finally:
            events.append("seat-close")
    assert caught.value is original
    assert events == ["guard", "capture", "seat-close"]
    assert bool(warnings) is capture_fails
    if capture_fails:
        assert "secondary capture failure" in warnings[0]


def test_valid_caption_never_captures_failure(bound, monkeypatch):
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [_CaptionNote("E")]
    captures = []
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", lambda *args, **kwargs: captures.append((args, kwargs)))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    assert captures == []


def test_caption_probe_failures_are_explicit_and_cannot_replace_guard(bound, monkeypatch):
    note = _CaptionNote("E")
    note.GetText = lambda: None
    note.GetExtent = lambda: None
    note.annotation.GetDisplayData = lambda: None
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    with pytest.raises(RuntimeError, match="detail E caption have no rendered extent"):
        drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    report = json.loads(next(log for log in logs if "native diagnostics: " in log).split("native diagnostics: ", 1)[1])
    assert {"GetText", "GetExtent", "GetDisplayData"} <= report["native_read_errors"].keys()
    (entry,) = report["notes"]
    assert entry["native_get_text"] is entry["native_note_get_extent"] is None
    assert entry["resolved_line_count"] is entry["display_fragment_count"] is None
    assert entry["display_decoder_estimate"]["extent_m"] is None


@pytest.mark.parametrize("top", [0.066, 0.070])
def test_end_caption_seats_actual_ink_between_crop_and_actual_title_rule(bound, monkeypatch, top):
    note = _FakeNote((0.30, 0.07), 0.007)
    note.PropertyLinkedText = "$PRPVIEW:DETAIL E SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(top=top), label="E")
    box = drawing._note_extent(adapter, note)
    assert box[3] <= 0.084 - 0.003
    assert box[1] >= top + 0.003
    assert (box[0] + box[2]) / 2 == pytest.approx(0.322)
    assert note.PropertyLinkedText == "$PRPVIEW:DETAIL E SCALE"


@pytest.mark.parametrize("width", [0.0234, 0.0324])
def test_end_caption_clears_land_angle_witness_without_moving_native_view(bound, monkeypatch, width):
    note = _FakeNote((0.318, 0.078), 0.007)
    note.PropertyLinkedText = "$PRPVIEW:DETAIL E SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    original_extent = note.GetExtent
    def measured_extent():
        values = list(original_extent())
        values[3] = values[0] + width
        return tuple(values)
    note.GetExtent = measured_extent
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    position = view.Position
    crop = drawing._detail_crop(adapter, view, label="E")
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, _native_sheet(), label="E")
    box = drawing._note_extent(adapter, note)
    # Native proof put the angle's vertical witness at X=341.5 mm; the
    # centred caption missed it by only 0.05 mm. Keep ordinary 3 mm air.
    assert 0.3415 - box[2] >= 0.003
    assert box[3] <= crop[1] - 0.003
    assert box[1] >= 0.066 + 0.003
    assert view.Position == position
    assert drawing._detail_crop(adapter, view, label="E") == crop
    assert note.PropertyLinkedText == "$PRPVIEW:DETAIL E SCALE"


@pytest.mark.parametrize("label", ["D", "E"])
def test_native_caption_target_has_margin_for_r12_one_pixel_extents(bound, monkeypatch, label):
    # R12's last two GetExtent upper Y values differ by exactly this much;
    # the active display reported 2.098 px/mm. Fifty microns cannot settle it.
    pixel = 0.06535530434782608 - 0.06487873578595318
    assert pixel * 1000.0 == pytest.approx(1.0 / 2.098, abs=0.0001)
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert drawing._DETAIL_CAPTION_SETTLE_M >= pixel
    note = _FakeNote((0.16 if label == "D" else 0.30, 0.04), 0.007)
    note.PropertyLinkedText = f"$PRPVIEW:DETAIL {label} SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    original_extent = note.GetExtent
    def quantized_extent():
        values = list(original_extent())
        values[3] = values[0] + 0.0324
        for index in (0, 1, 3, 4):
            values[index] = math.ceil(values[index] / pixel) * pixel
        return values
    note.GetExtent = quantized_extent
    adapter, view = _native_crop_fixture(monkeypatch, label)
    if label == "E":
        view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [note]
    sheet = _native_sheet()
    sheet.GetZoneMargin = lambda _side: 0.0127
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, sheet, label=label)
    box = drawing._note_extent(adapter, note)
    crop = drawing._detail_crop(adapter, view, label=label)
    assert crop[1] - box[3] >= 0.003
    floor = 0.0127 if label == "D" else 0.066
    assert box[1] - floor >= 0.003
    offset = -0.008 if label == "E" else 0.0
    assert abs((box[0] + box[2] - crop[0] - crop[2]) / 2.0 - offset) <= pixel
    assert note.PropertyLinkedText == f"$PRPVIEW:DETAIL {label} SCALE"
    if label == "D":
        # The same causal native pixel grid rejects the old near-boundary
        # target / 50-micron convergence rule; do not fix it by weakening air.
        monkeypatch.setattr(drawing, "_DETAIL_CAPTION_TARGET_AIR_M", 0.00305)
        monkeypatch.setattr(drawing, "_DETAIL_CAPTION_SETTLE_M", 0.00005)
        with pytest.raises(RuntimeError, match="caption ink did not settle"):
            drawing._seat_detail_caption(adapter, view, sheet, label=label)


@pytest.mark.parametrize("defect", ["height", "title-rule", "scale", "missing", "multiple", "unlinked", "slot", "ignored-position", "refused-position", "nan", "missing-extent", "missing-position", "lost-links", "air"])
def test_end_caption_fails_closed_without_real_ink_and_three_mm_air(bound, monkeypatch, defect):
    note = _FakeNote((0.30, 0.07), 0.020 if defect == "height" else 0.007,
                     tracking=0.0 if defect == "ignored-position" else 1.0)
    note.PropertyLinkedText = "" if defect == "unlinked" else "$PRPVIEW:DETAIL E SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    if defect == "nan":
        note.GetExtent = lambda: (float("nan"), 0.1, 0, 0.2, 0.11, 0)
    elif defect == "missing-extent":
        note.GetExtent = lambda: None
    elif defect == "missing-position":
        note.annotation.GetPosition = lambda: None
    elif defect == "refused-position":
        note.annotation.SetPosition2 = lambda *_args: False
    elif defect == "lost-links":
        def move_and_unlink(*args):
            result = note.annotation.SetPosition(*args)
            note.PropertyLinkedText = "lost link"
            return result
        note.annotation.SetPosition2 = move_and_unlink
    elif defect == "air":
        monkeypatch.setattr(drawing, "_DETAIL_CAPTION_TARGET_AIR_M", 0.0025)
    adapter, view = _native_crop_fixture(monkeypatch, "E")
    view.Position = view.physical = (0.330, 0.084 + view.radius)
    view.notes = [] if defect == "missing" else [note, note] if defect == "multiple" else [note]
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    captures = []
    def capture(current_adapter, _label, _message, **context):
        assert current_adapter is adapter and context["sheet_png"] is True
        captures.append(context["exception"])
        raise context["exception"]
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(RuntimeError) as caught:
        drawing._seat_detail_caption(
            adapter, view, _native_sheet(top=0.084 if defect == "slot" else 0.066, rule=defect != "title-rule", scale_retained=defect != "scale"), label="E",
        )
    assert captures == [caught.value]


class _CensusAnnotation:
    _native_interfaces = ("IAnnotation",)
    def __init__(self, name, *, kind=4, specific=None):
        self.name, self.kind, self.specific = name, kind, specific

    def GetType(self):  # noqa: N802
        return self.kind

    def GetSpecificAnnotation(self):  # noqa: N802
        return self.specific


class _CensusDisplayDimension:
    _native_interfaces = ("IDisplayDimension",)
    def __init__(self, dimension, *, hole_callout=False):
        self.dimension, self.hole_callout = dimension, hole_callout

    def GetDimension2(self, index):  # noqa: N802
        assert index == 0
        return self.dimension

    def IsHoleCallout(self):  # noqa: N802
        return self.hole_callout


@pytest.fixture
def native_annotation_binding(monkeypatch):
    """Opaque raw dispatches cannot expose members of their bound interfaces."""
    wrappers, calls = {}, []

    def raw(native, interface):
        _bind_owner(native, interface)
        dispatch = object()
        wrappers[id(dispatch)] = (dispatch, interface, native)
        return dispatch

    def bind(dispatch, interface, *_members):
        entry = wrappers.get(id(dispatch))
        if entry is None:
            return _bind_owner(dispatch, interface)
        assert entry[0] is dispatch and entry[1] == interface
        calls.append((interface, entry[2]))
        return _bind_owner(entry[2], interface)

    import _drawing_dimensions
    import _drawing_edge_dimensions
    import _drawing_layout_audit
    import _drawing_notes
    from solidworks_mcp.adapters import sw_type_info

    for module in (
        drawing, detail_crop, _drawing_dimensions, _drawing_edge_dimensions,
        _drawing_layout_audit, _drawing_notes,
    ):
        monkeypatch.setattr(module, "_early_bound", bind)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", bind)
    return SimpleNamespace(raw=raw, bind=bind, calls=calls)


@pytest.fixture
def raw_dimension_census(monkeypatch, native_annotation_binding):
    keeps = [list(keep) for keep in (
        drawing.FRONT_KEEP, drawing.HUB_KEEP, drawing.END_KEEP, drawing.RIGHT_KEEP,
    )]
    annotations = [[_CensusAnnotation(name) for name in keep] for keep in keeps]
    raws = [[native_annotation_binding.raw(ann, "IAnnotation") for ann in row]
            for row in annotations]
    native_views = [_native("IView", GetAnnotationCount=lambda row=row: len(row), GetAnnotations=lambda row=row: row)
                    for row in raws]
    views = [(label, native_annotation_binding.raw(view, "IView"), keep)
             for label, view, keep in zip(("front", "D", "E", "right"), native_views, keeps)]
    reads, logs = [], []

    def read_name(_adapter, annotation):
        reads.append(annotation)
        return annotation.name if isinstance(annotation, _CensusAnnotation) else ""

    monkeypatch.setattr(drawing, "dimension_name", read_name)
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    return SimpleNamespace(
        annotations=annotations, raws=raws, native_views=native_views, views=views,
        keeps=keeps, reads=reads, logs=logs, binding=native_annotation_binding,
    )


@pytest.mark.parametrize("defect", [None, "missing", "duplicate", "wrong-owner"])
def test_actual_per_view_dimension_census_is_an_exact_marked_union(raw_dimension_census, defect):
    case = raw_dimension_census
    if defect == "missing":
        case.raws[1].pop(case.keeps[1].index("PivotDia"))
    elif defect == "duplicate":
        case.raws[2].append(case.raws[2][0])
    elif defect == "wrong-owner":
        case.raws[0].append(case.raws[2].pop())
    if defect is None:
        drawing._require_dimension_census(object(), case.views)
        expected = [ann for row in case.annotations for ann in row]
        assert case.reads == expected
        assert [ann for interface, ann in case.binding.calls if interface == "IAnnotation"] == expected
        census_logs = [log for log in case.logs if "marked-dimension census=" in log]
        count_logs = [log for log in case.logs if "native GetAnnotationCount=" in log]
        assert len(census_logs) == len(count_logs) == len(case.views)
        assert all(f"native annotations={len(row)}" in log for row, log in zip(case.raws, census_logs))
        assert all(f"GetAnnotationCount={len(row)}, GetAnnotations length={len(row)}" in log
                   for row, log in zip(case.raws, count_logs))
    else:
        with pytest.raises(RuntimeError, match="native dimension owners"):
            drawing._require_dimension_census(object(), case.views)


@pytest.mark.parametrize("defect", ["missing", "duplicate"])
def test_census_union_refuses_even_when_each_native_view_matches_its_keep(raw_dimension_census, defect):
    case = raw_dimension_census
    if defect == "missing":
        index = case.keeps[1].index("PivotDia")
        case.raws[1].pop(index)
        case.keeps[1].pop(index)
    else:
        case.raws[1].append(case.raws[0][case.keeps[0].index("TopRadius")])
        case.keeps[1].append("TopRadius")
    with pytest.raises(RuntimeError, match="marked-dimension union is not exact"):
        drawing._require_dimension_census(object(), case.views)


@pytest.mark.parametrize("defect", ["unreadable", "hidden-duplicate", "hidden-wrong-owner"])
@pytest.mark.parametrize("hole_callout", [False, True])
def test_census_refuses_every_unnamed_actual_model_dimension(raw_dimension_census, defect, hole_callout):
    case = raw_dimension_census
    name = "PivotDia" if defect == "hidden-wrong-owner" else "TopRadius"
    display = _CensusDisplayDimension(_native("IDimension", Name=name), hole_callout=hole_callout)
    annotation = _CensusAnnotation("", specific=case.binding.raw(display, "IDisplayDimension"))
    raw = case.binding.raw(annotation, "IAnnotation")
    if defect == "unreadable":
        case.raws[0][case.keeps[0].index("TopRadius")] = raw
    else:
        case.raws[0].append(raw)
    with pytest.raises(RuntimeError, match=r"rocker front: native dimension #\d+ has no readable name"):
        drawing._require_dimension_census(object(), case.views)
    assert ("IDisplayDimension", display) in case.binding.calls


@pytest.mark.parametrize("kind", [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19])
def test_census_skips_documented_nondimension_annotations(raw_dimension_census, kind):
    case = raw_dimension_census
    annotation = _CensusAnnotation("", kind=kind)
    annotation.GetSpecificAnnotation = lambda: pytest.fail("non-dimension specific object was read")
    case.raws[0].append(case.binding.raw(annotation, "IAnnotation"))
    drawing._require_dimension_census(object(), case.views)
    assert case.reads[-1] is case.annotations[-1][-1]
    assert annotation in case.reads


def test_census_skips_native_hole_callout_with_null_underlying_dimension(raw_dimension_census):
    case = raw_dimension_census
    display = _CensusDisplayDimension(None, hole_callout=True)
    annotation = _CensusAnnotation("", specific=case.binding.raw(display, "IDisplayDimension"))
    case.raws[0].append(case.binding.raw(annotation, "IAnnotation"))
    drawing._require_dimension_census(object(), case.views)
    assert ("IDisplayDimension", display) in case.binding.calls


@pytest.mark.parametrize("identity", [False, None, 0, 1, "True", lambda: True])
def test_census_refuses_null_model_without_actual_hole_callout_identity(raw_dimension_census, identity):
    case = raw_dimension_census
    display = _CensusDisplayDimension(None, hole_callout=identity)
    annotation = _CensusAnnotation("", specific=case.binding.raw(display, "IDisplayDimension"))
    case.raws[0].append(case.binding.raw(annotation, "IAnnotation"))
    expected = "no underlying model dimension" if identity is False else "invalid hole-callout identity"
    with pytest.raises(RuntimeError, match=expected):
        drawing._require_dimension_census(object(), case.views)


def test_census_refuses_null_specific_display_dimension(raw_dimension_census):
    case = raw_dimension_census
    case.raws[0].append(case.binding.raw(_CensusAnnotation(""), "IAnnotation"))
    with pytest.raises(RuntimeError, match="has no native display dimension"):
        drawing._require_dimension_census(object(), case.views)


@pytest.mark.parametrize("kind", [None, True, False, 4.0, 4.5, "4", lambda: 4, 0, -1, 20])
def test_census_refuses_malformed_native_annotation_type(raw_dimension_census, kind):
    case = raw_dimension_census
    annotation = _CensusAnnotation("", kind=kind)
    annotation.GetSpecificAnnotation = lambda: pytest.fail("malformed annotation type was accepted")
    case.raws[0].append(case.binding.raw(annotation, "IAnnotation"))
    with pytest.raises(RuntimeError, match="has invalid type"):
        drawing._require_dimension_census(object(), case.views)


@pytest.mark.parametrize("stage", [
    "GetAnnotationCount", "GetAnnotations", "GetType", "GetSpecificAnnotation", "GetDimension2",
    "IsHoleCallout", "dimension_name", "bind-view", "bind-annotation", "bind-display",
])
def test_census_preserves_original_native_and_binding_exceptions(raw_dimension_census, monkeypatch, stage):
    case = raw_dimension_census
    display = _CensusDisplayDimension(None, hole_callout=True)
    annotation = _CensusAnnotation("", specific=case.binding.raw(display, "IDisplayDimension"))
    case.raws[0].append(case.binding.raw(annotation, "IAnnotation"))
    failure = OSError(f"native refusal at {stage}")

    def refuse(*_args, **_kwargs):
        raise failure

    if stage.startswith("bind-"):
        original = drawing._early_bound
        refused_interface = {
            "bind-view": "IView", "bind-annotation": "IAnnotation", "bind-display": "IDisplayDimension",
        }[stage]
        def bind(raw, interface):
            return refuse() if interface == refused_interface else original(raw, interface)
        monkeypatch.setattr(drawing, "_early_bound", bind)
    else:
        target = {
            "GetAnnotationCount": case.native_views[0], "GetAnnotations": case.native_views[0],
            "GetType": annotation, "GetSpecificAnnotation": annotation,
            "GetDimension2": display, "IsHoleCallout": display, "dimension_name": drawing,
        }[stage]
        monkeypatch.setattr(target, stage, refuse)
    with pytest.raises(OSError) as caught:
        drawing._require_dimension_census(object(), case.views)
    assert caught.value is failure


@pytest.mark.parametrize("raw", [None, (), []])
def test_bound_view_annotations_accepts_native_empty_array(native_annotation_binding, monkeypatch, raw):
    events, logs = [], []
    def count():
        events.append("GetAnnotationCount")
        return 0
    def annotations():
        events.append("GetAnnotations")
        return raw
    view = _native("IView", GetAnnotationCount=count, GetAnnotations=annotations)
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    assert drawing._bound_view_annotations(view, label="test view") == ()
    assert events == ["GetAnnotationCount", "GetAnnotations"]
    assert native_annotation_binding.calls == []
    array_evidence = "GetAnnotations=None" if raw is None else "GetAnnotations length=0"
    assert logs == [f"test view: native GetAnnotationCount=0, {array_evidence}"]


@pytest.mark.parametrize("array", [tuple, list])
def test_bound_view_annotations_binds_each_native_array_item(native_annotation_binding, monkeypatch, array):
    binding = native_annotation_binding
    annotations = [_CensusAnnotation("TopRadius"), _CensusAnnotation("BottomRadius")]
    raw = array(binding.raw(ann, "IAnnotation") for ann in annotations)
    events = []
    original = drawing._early_bound
    def bind(dispatch, interface):
        events.append(f"bind {interface}")
        return original(dispatch, interface)
    def count():
        events.append("GetAnnotationCount")
        return len(raw)
    def read():
        events.append("GetAnnotations")
        return raw
    view = _native("IView", GetAnnotationCount=count, GetAnnotations=read)
    monkeypatch.setattr(drawing, "_early_bound", bind)
    assert drawing._bound_view_annotations(binding.raw(view, "IView"), label="test view") == tuple(annotations)
    assert binding.calls == [("IView", view), *(("IAnnotation", ann) for ann in annotations)]
    assert events == ["bind IView", "GetAnnotationCount", "GetAnnotations", "bind IAnnotation", "bind IAnnotation"]


@pytest.mark.parametrize("raw", [False, 0, "", {}, object(), iter(())])
def test_bound_view_annotations_refuses_nonarray_native_shape(native_annotation_binding, raw):
    view = _native("IView", GetAnnotationCount=lambda: 0, GetAnnotations=lambda: raw)
    with pytest.raises(RuntimeError, match="test view: invalid native annotation array"):
        drawing._bound_view_annotations(view, label="test view")
    assert native_annotation_binding.calls == []


@pytest.mark.parametrize("array", [tuple, list])
@pytest.mark.parametrize("index", [0, 1])
def test_bound_view_annotations_refuses_null_array_item(native_annotation_binding, array, index):
    binding = native_annotation_binding
    raw = [binding.raw(_CensusAnnotation("TopRadius"), "IAnnotation"), None] if index else [None]
    view = _native("IView", GetAnnotationCount=lambda: len(raw), GetAnnotations=lambda: array(raw))
    with pytest.raises(RuntimeError, match=rf"test view: native annotation #{index} is null"):
        drawing._bound_view_annotations(view, label="test view")


@pytest.mark.parametrize("count", [1, 2])
def test_bound_view_annotations_refuses_positive_count_with_null_array(native_annotation_binding, monkeypatch, count):
    view = _native("IView", GetAnnotationCount=lambda: count, GetAnnotations=lambda: None)
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    with pytest.raises(RuntimeError, match=rf"native annotation count {count} returned no annotation array"):
        drawing._bound_view_annotations(view, label="test view")
    assert native_annotation_binding.calls == []
    assert logs == [f"test view: native GetAnnotationCount={count}, GetAnnotations=None"]


@pytest.mark.parametrize("array", [tuple, list])
@pytest.mark.parametrize("count,size", [(0, 1), (1, 0), (1, 2), (2, 1)])
def test_bound_view_annotations_refuses_count_array_length_mismatch(
    native_annotation_binding, monkeypatch, array, count, size,
):
    binding = native_annotation_binding
    raw = array(binding.raw(_CensusAnnotation("TopRadius"), "IAnnotation") for _ in range(size))
    view = _native("IView", GetAnnotationCount=lambda: count, GetAnnotations=lambda: raw)
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)
    with pytest.raises(RuntimeError, match=rf"native annotation array length {size}, expected count {count}"):
        drawing._bound_view_annotations(view, label="test view")
    assert binding.calls == []
    assert logs == [f"test view: native GetAnnotationCount={count}, GetAnnotations length={size}"]


@pytest.mark.parametrize("count", [None, True, False, -1, 1.0, "1", lambda: 1, object()])
def test_bound_view_annotations_refuses_malformed_count_before_array_read(native_annotation_binding, count):
    view = _native("IView", GetAnnotationCount=lambda: count, GetAnnotations=lambda: pytest.fail("GetAnnotations called after invalid native count"),)
    with pytest.raises(RuntimeError, match="test view: invalid native annotation count"):
        drawing._bound_view_annotations(view, label="test view")
    assert native_annotation_binding.calls == []


@pytest.mark.parametrize("stage", ["GetAnnotationCount", "GetAnnotations"])
def test_bound_view_annotations_preserves_native_exception_identity_and_read_order(native_annotation_binding, stage):
    events = []
    failure = OSError(f"native refusal at {stage}")
    def count():
        events.append("GetAnnotationCount")
        if stage == "GetAnnotationCount":
            raise failure
        return 1
    def annotations():
        events.append("GetAnnotations")
        raise failure
    view = _native("IView", GetAnnotationCount=count, GetAnnotations=annotations)
    with pytest.raises(OSError) as caught:
        drawing._bound_view_annotations(view, label="test view")
    assert caught.value is failure
    assert events == (["GetAnnotationCount"] if stage == "GetAnnotationCount" else ["GetAnnotationCount", "GetAnnotations"])
    assert native_annotation_binding.calls == []


@pytest.mark.parametrize("axis", ["X", "Y"])
@pytest.mark.parametrize("defect", [None, "wrong", "attachment", "uncentred", "basic", "text"])
def test_pin_coordinates_are_native_centred_basic_with_labels_after_boxing(monkeypatch, axis, defect):
    import _drawing_edge_dimensions
    adapter, _imported = _imported_native_quantities(monkeypatch)
    pivot, rod = object(), object()
    displays = {}
    monkeypatch.setattr(drawing, "_project", lambda *_a, **_k: [(0.18, 0.172), (0.246, 0.176)])
    monkeypatch.setattr(drawing, "visible_circle_edge", lambda _a, _v, diameter: pivot if diameter == drawing.PIVOT_HOLE_DIA else rod)
    monkeypatch.setattr(_drawing_edge_dimensions, "_is_same_attachment", lambda _a, actual, wanted, _kind: actual is wanted)
    def create(_adapter, _view, **kwargs):
        current_axis = "X" if kwargs["orientation"] == "horizontal" else "Y"
        mm = drawing.ROD_HOLE_X if current_axis == "X" else drawing.ROD_HOLE_Y - drawing.PIVOT_MID_Y
        display = _NativeQuantity(current_axis, mm)
        display.attached = (pivot, rod)
        display.arc_conditions = {1: 2, 2: 2}
        if current_axis == axis:
            if defect == "wrong":
                display.model.SystemValue += 0.0001
            elif defect == "attachment":
                display.attached = (pivot, object())
            elif defect == "uncentred":
                display.model.SetArcEndCondition = lambda *_a: 0
            elif defect == "basic":
                display.model.SetToleranceType = lambda _kind: True
            elif defect == "text":
                display.ignored_text = 4
        displays[current_axis] = display
        return display
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    if defect is None:
        drawing._add_pin_coordinates(adapter, object())
        for display in displays.values():
            assert display.arc_conditions == {1: 1, 2: 1}
            assert display.model.GetToleranceType() == 1
            assert display.text[4] == "PIN AXIS"
            assert display.writes[-2:] == [(4, ""), (4, "PIN AXIS")]
    else:
        with pytest.raises(RuntimeError):
            drawing._add_pin_coordinates(adapter, object())


@pytest.mark.parametrize("air,passes", [(0.001, True), (0.0009, False)])
def test_every_front_native_text_row_is_guarded_against_detail_crops(native_profile_clearance, bound, monkeypatch, air, passes):
    case = native_profile_clearance
    # Native records are historical detector inputs, not a current-coordinate proof.
    case.front.GetAnnotations = lambda: [case.r816]
    case.front.GetAnnotationCount = lambda: 1
    case.r816.data.texts = [{"t": "R816", "pos": [0.170, 0.128, 0], "h": 0.0035}]
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
    hub.Position = hub.physical = (0.180, 0.128 - air - hub.radius)
    _adapter, end = _native_crop_fixture(monkeypatch, "E")
    if passes:
        drawing._require_front_detail_air(case.adapter, case.front, hub, end)
    else:
        with pytest.raises(RuntimeError, match="required_air_mm=1.000"):
            drawing._require_front_detail_air(case.adapter, case.front, hub, end)
    assert any("actual_air_mm=" in log for log in case.logs)


def test_native_profile_guard_diagnoses_actual_radius_leader_crossing(native_profile_clearance):
    case = native_profile_clearance
    case.r816.leaders = [[0.050, 0.143, 0, 0.080, 0.143, 0, 0.120, 0.143, 0]]
    with pytest.raises(RuntimeError, match="actual native leader crossing"):
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)


@pytest.mark.parametrize("view_index", range(3))
@pytest.mark.parametrize("defect", [
    None, "empty", "missing", "duplicate",
    "bool-kind", "string-kind", "invalid-low", "invalid-high",
])
def test_each_face_retains_only_its_template_marks_without_batch_reinsertion(
    mark_census, monkeypatch, view_index, defect,
):
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    loops = [
        node for node in build.body
        if isinstance(node, ast.For)
        and any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_require_center_mark_census"
            for call in ast.walk(node)
        )
    ]
    assert len(loops) == 1
    assert [
        (entry.elts[0].value, entry.elts[1].id, entry.elts[2].value, entry.elts[3].value)
        for entry in loops[0].iter.elts
    ] == [("front", "front", 2, None), ("detail D", "hub", 1, "D"), ("detail E", "end", 1, "E")]
    assert not hasattr(drawing, "auto_center_marks")
    assert not any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "auto_center_marks"
        for call in ast.walk(build)
    )
    kinds_by_view = [[13, 13, 4], [13, 4], [13, 4]]
    invalid_kinds = {
        "bool-kind": True, "string-kind": "13", "invalid-low": 0, "invalid-high": 20,
    }
    if defect == "empty":
        kinds_by_view[view_index] = []
    elif defect == "missing":
        kinds_by_view[view_index].remove(13)
    elif defect == "duplicate":
        kinds_by_view[view_index].append(13)
    elif defect in invalid_kinds:
        kinds_by_view[view_index].append(invalid_kinds[defect])

    adapter, hub = _native_crop_fixture(monkeypatch, "D")
    _adapter, end = _native_crop_fixture(monkeypatch, "E")
    centres = (drawing.FRONT_CENTER, hub.physical, end.physical)
    views = []
    for index, (kinds, (x, y)) in enumerate(zip(kinds_by_view, centres, strict=True)):
        records = [
            (f"template-{index}-{ordinal}", (x + ordinal * 0.002, y, 0.0),
             {"lines": [_native_line(x + ordinal * 0.002 - 0.0005, y,
                                     x + ordinal * 0.002 + 0.0005, y)]})
            for ordinal, kind in enumerate(kinds) if type(kind) is int and kind == 13
        ]
        case = mark_census(records, crop=(0.100, 0.150, 0.260, 0.200))
        printed_raws = iter(case.raws)
        raw_annotations = [
            next(printed_raws) if type(kind) is int and kind == 13 else
            case.binding.raw(_native("IAnnotation", GetType=lambda kind=kind: kind), "IAnnotation")
            for kind in kinds
        ]
        if index and not (defect == "empty" and index == view_index):
            # Native details retain a readable off-crop zero-ink ghost. It
            # must not count as printed and must not be deleted by the loop.
            ghost = mark_census([(f"ghost-{index}", (0.700, 0.127, 0.005), {})])
            raw_annotations.extend(ghost.raws)
        if index:
            native_view = (hub, end)[index - 1]
            native_view.annotations = raw_annotations
            views.append(case.binding.raw(native_view, "IView"))
        else:
            case.raws[:] = raw_annotations
            views.append(case.view)
    reads = []
    counted_annotations = drawing._bound_view_annotations

    def record_counted_read(view, *, label):
        reads.append(view)
        return counted_annotations(view, label=label)

    monkeypatch.setattr(drawing, "_bound_view_annotations", record_counted_read)
    namespace = dict(
        adapter=adapter, front=views[0], hub=views[1], end=views[2],
        _require_center_mark_census=drawing._require_center_mark_census,
    )
    module = ast.Module(body=loops, type_ignores=[])
    code = compile(ast.fix_missing_locations(module), drawing.__file__, "exec")
    if defect is None:
        exec(code, namespace)
        assert reads == views
    else:
        with pytest.raises(RuntimeError):
            exec(code, namespace)
        assert reads == views[:view_index + 1]


@pytest.mark.parametrize("defect", [
    None, "missing", "null-display", "ignored", "strap-missing", "strap-ignored", "root-missing",
])
def test_hub_length_stack_callout_is_below_and_preserves_native_size(
    monkeypatch, defect,
):
    adapter, _imported = _imported_native_quantities(monkeypatch)
    hub = _NativeQuantity("HubLength", ch_rocker_arm_spec.HUB_LENGTH, precision=3)
    hub.band = tuple(value / 1000.0 for value in ch_rocker_arm_spec.HUB_LENGTH_BAND)
    hub.tolerance_type = 4
    strap = _NativeQuantity("StrapThickness", ch_rocker_arm_spec.ARM_THICKNESS, precision=3)
    strap.tolerance_type = 4
    root = _HubRootDisplay()
    before = [
        (d.model.SystemValue, d.band, d.tolerance_type, d.precision) for d in (hub, strap, root)
    ]
    if defect == "null-display":
        hub.annotation.GetSpecificAnnotation = lambda: None
    elif defect == "ignored":
        hub.ignored_text = 4
    elif defect == "strap-ignored":
        strap.ignored_text = 4
    displays = {
        "missing": (strap, root), "strap-missing": (hub, root), "root-missing": (hub, strap),
    }.get(defect, (hub, strap, root))
    annotations = [display.GetAnnotation() for display in displays]
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    start = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "right_annotations"
            for target in node.targets
        )
    )
    # View F's dressing (hub root, strap frame, the strap's centre plane, and
    # datum G with its BASIC to that plane) is one guarded block.
    stop = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Try)
        and any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "_strap_position_frame"
            for call in ast.walk(node)
        )
    )
    label_start = next(
        index for index, node in enumerate(build.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "set_dimension_callouts"
        and isinstance(node.value.args[1], ast.Name)
        and node.value.args[1].id == "right_annotations"
    )
    assert start < label_start < stop
    right, plane, placed, captured = object(), object(), [], []
    namespace = dict(
        adapter=adapter, right=right, RIGHT_KEEP=drawing.RIGHT_KEEP,
        DRAWING_DIMENSIONS=drawing.DRAWING_DIMENSIONS,
        curate_view_dimensions=lambda *_args, **_kwargs: annotations,
        set_dimension_callouts=drawing.set_dimension_callouts,
        dimension_name=drawing.dimension_name, _early_bound=drawing._early_bound,
        rocker_notes=ch_rocker_arm_notes, HUB_LENGTH_TEXT=drawing.HUB_LENGTH_TEXT,
        _dress_hub_root=drawing._dress_hub_root,
        _strap_position_frame=lambda _adapter, view, ann: placed.append(
            ("frame", view, ann)
        ),
        _strap_centre_plane=lambda _adapter, view: (
            placed.append(("centre plane", view)) or plane
        ),
        _hub_face_datum_g=lambda _adapter, view, centre, ann: placed.append(
            ("G", view, centre, ann)
        ),
        _capture_layout_failure=lambda _adapter, phase, _exc: captured.append(phase),
    )
    # This label test owns the right import, its callout/readback and view F's
    # dressing, not the preceding all-view precision checks and other views.
    module = ast.Module(
        body=[build.body[start], *build.body[label_start:stop + 1]], type_ignores=[],
    )
    code = compile(ast.fix_missing_locations(module), drawing.__file__, "exec")
    if defect is None:
        exec(code, namespace)
        # Hub length names its stack mate and the strap its fork fit, both in
        # below rows (above-text line breaks print as one run).
        assert hub.writes == [(4, drawing.HUB_LENGTH_TEXT)]
        assert "MHA-CH-05" in drawing.HUB_LENGTH_TEXT
        assert strap.writes == [(4, ch_rocker_arm_notes.STRAP_FIT_CALLOUT)]
        assert "MHA-CH-03" in ch_rocker_arm_notes.STRAP_FIT_CALLOUT
        # The position frame hangs on the strap width, then the centre plane
        # it locates, then G on the -Z face with its BASIC to that plane, read
        # back against the hub width.
        assert placed == [
            ("frame", right, strap.annotation),
            ("centre plane", right),
            ("G", right, plane, hub.annotation),
        ]
        assert root.ArcExtensionLineOrOppositeSide is False
        assert captured == []
    else:
        with pytest.raises((RuntimeError, ValueError)):
            exec(code, namespace)
    assert [
        (d.model.SystemValue, d.band, d.tolerance_type, d.precision) for d in (hub, strap, root)
    ] == before


def test_details_keep_native_scale_source_census_and_unclipped_overall_contract():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    definitions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    build_calls = [node for node in ast.walk(definitions["build"])
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    details = [node for node in build_calls if node.func.id == "_create_detail"]
    assert len(details) == 2
    assert [next(ast.unparse(k.value) for k in node.keywords if k.arg == "scale")
            for node in details] == ["HUB_SCALE", "END_SCALE"]
    assert drawing.HUB_SCALE == (4.0, 1.0) and drawing.END_SCALE == (2.0, 1.0)
    assert "create_detail_view" not in Path(drawing.__file__).read_text(encoding="utf-8")
    for required in ("_place_detail_letters", "_require_dimension_census", "_require_front_detail_air", "_require_radius_exterior"):
        assert sum(node.func.id == required for node in build_calls) == 1
    caps = [node for node in ast.walk(definitions["_add_rocker_outline_dimensions"])
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Attribute) and target.attr == "MaxWitnessLineLength"
                    for target in node.targets)]
    assert len(caps) == 4
    assert [ast.unparse(cap.targets[0]) for cap in caps] == [
        "taper_dimension.MaxWitnessLineLength",
        "left_taper_dimension.MaxWitnessLineLength",
        "land_dimension.MaxWitnessLineLength",
        "left_land_dimension.MaxWitnessLineLength",
    ]
    assert all(ast.unparse(cap.value) == "TAPER_WITNESS_LENGTH" for cap in caps)  # Overall remains full-length.
    assert not hasattr(drawing, "OVERALL_WITNESS_LENGTH")
    assert not hasattr(drawing, "PIVOT_PICK_ZOOM_HALF")
    assert set(drawing.FRONT_KEEP) == drawing.BASIC_PROFILE_DIMENSIONS | set(drawing.ARC_RADIUS_NAMES)
    assert not hasattr(drawing, "_sheet_xy")
    crop_calls = {"_seat_detail_caption": 1, "_require_ream_clearance": 1, "_require_front_detail_air": 2}
    for name, count in crop_calls.items():
        calls = [node for node in ast.walk(definitions[name]) if isinstance(node, ast.Call)]
        assert sum(isinstance(node.func, ast.Name) and node.func.id == "_detail_crop" for node in calls) == count
        assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "GetOutline" for node in calls)
    crop_attributes = {node.attr for node in ast.walk(definitions["_detail_crop"]) if isinstance(node, ast.Attribute)}
    shared_tree = ast.parse(Path(detail_crop.__file__).read_text(encoding="utf-8"))
    shared_definitions = {node.name: node for node in shared_tree.body if isinstance(node, ast.FunctionDef)}
    shared_reader = shared_definitions["read_circular_detail_crop"]
    shared_attributes = {node.attr for node in ast.walk(shared_reader) if isinstance(node, ast.Attribute)}
    native_outline_calls = [node for node in ast.walk(shared_reader) if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute) and node.func.attr == "GetOutline"]
    assert len(native_outline_calls) == 1
    outline_statement = next(i for i, statement in enumerate(shared_reader.body)
                             if native_outline_calls[0] in list(ast.walk(statement)))
    barrier_statements = [i for i, statement in enumerate(shared_reader.body)
                          if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                          and isinstance(statement.value.func, ast.Attribute)
                          and statement.value.func.attr == "UpdateViewDisplayGeometry"]
    assert len(barrier_statements) == 2 and max(barrier_statements) < outline_statement
    wrapper_calls = [node.func.id for node in ast.walk(definitions["_detail_crop"])
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert wrapper_calls.count("read_circular_detail_crop") == 1 and "_outline" not in wrapper_calls
    # GetText is valid only on the ordinary right-view HubLength/StrapThickness
    # displays, not the native wizard-hole callout: each read is name-guarded.
    build_text_calls = [
        node for node in ast.walk(definitions["build"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "GetText"
    ]
    # Both multi-row callouts are below text (row 4), read back by name.
    assert [ast.unparse(call) for call in build_text_calls] == [
        "display.GetText(4)", "display.GetText(4)",
    ]
    for call, name in zip(build_text_calls, ("HubLength", "StrapThickness"), strict=True):
        guard = next(
            node for node in ast.walk(definitions["build"])
            if isinstance(node, ast.If) and call in list(ast.walk(node.test))
        )
        assert isinstance(guard.test, ast.BoolOp) and isinstance(guard.test.op, ast.And)
        assert ast.unparse(guard.test.values[0]) == f"name == {name!r}"
    assert sum(node.func.id == "_require_rod_through_callout" for node in build_calls) == 1
    through_attributes = {node.attr for node in ast.walk(definitions["_require_rod_through_callout"]) if isinstance(node, ast.Attribute)}
    assert {"GetDisplayData", "GetTextCount", "GetTextAtIndex"} <= through_attributes
    assert "GetText" not in through_attributes
    assert {"GetDetail", "GetProfileItems", "Inverse", "ArrayData", "ModelToViewTransform"} <= shared_attributes
    assert "IInverse" not in crop_attributes | shared_attributes  # Automation Inverse only.
    assert "ModelToViewTransform" not in crop_attributes  # Recipe only adds independent source/F5 checks.
    sketch_loop = next(node for node in ast.walk(shared_reader)
                       if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "xyz")
    loop_calls = [node for node in ast.walk(sketch_loop) if isinstance(node, ast.Call)]
    mappings = [node for node in loop_calls if isinstance(node.func, ast.Name) and node.func.id == "_transform_point"]
    assert len(mappings) == 1 and ast.unparse(mappings[0].args[2]) == "inverse"
    # Sketch inverse ALREADY returns parent SHEET. Only the centre subsequently
    # takes parent-sheet -> MODEL -> detail-sheet; never parent forward twice.
    centre_mappings = [node for node in shared_reader.body
                       if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                       and isinstance(node.value.func, ast.Name) and node.value.func.id == "_transform_point"]
    assert [ast.unparse(node.value.args[2]) for node in centre_mappings] == ["parent_inverse", "detail_transform"]
    assert ast.unparse(centre_mappings[0].value.args[1]) == "(*parent_centre, 0.0)"
    assert ast.unparse(centre_mappings[1].value.args[1]) == "model_centre"
    circle_attributes = {node.attr for node in ast.walk(shared_definitions["native_circle_geometry"]) if isinstance(node, ast.Attribute)}
    assert {"GetType", "GetRadius", "GetCenterPoint2", "IsCircle"} <= circle_attributes
    assert not hasattr(drawing, "_native_circle_geometry")


def test_datum_landing_refuses_null_native_annotation(monkeypatch):
    import _drawing_gdt

    monkeypatch.setattr(_drawing_gdt, "_early_bound", _bind_owner)
    tag = _native("IDatumTag", GetAnnotation=lambda: None)
    with pytest.raises(RuntimeError, match="datum landing has no annotation.*rod-side radial land"):
        _drawing_gdt.assert_datum_landing(
            object(), tag, expected_xy=(0.21, 0.167), label="rod-side radial land",
        )


class _RenderedRodText:
    _native_interfaces = ("IDisplayData",)
    __slots__ = ("texts", "count", "reads")

    def __init__(self, texts):
        self.texts, self.count, self.reads = texts, len(texts), []

    def GetTextCount(self):
        return self.count

    def GetTextAtIndex(self, index):
        self.reads.append(index)
        return self.texts[index]


class _RenderedRodCallout:
    _native_interfaces = ("IDisplayDimension",)
    __slots__ = ("data",)

    def __init__(self, texts):
        self.data = _RenderedRodText(texts)

    def GetDisplayData(self):
        return self.data

    def GetText(self, _part):
        raise AssertionError("Hole callouts do not support GetText resolved compartments")


@pytest.mark.parametrize("texts", [
    ("#47 DRILL", "native diameter", "THRU"), ("#47 DRILL", "native diameter thru"), ("", "THRU"),
])
def test_rod_through_condition_reads_actual_rendered_callout_items(bound, texts):
    callout = _RenderedRodCallout(texts)
    drawing._require_rod_through_callout(callout)
    assert callout.data.reads == list(range(len(texts)))
    with pytest.raises(AssertionError, match="do not support GetText"):
        callout.GetText(1)


@pytest.mark.parametrize("defect", [
    "missing-data", "empty", "missing-count", "negative-count", "bool-count", "method-count",
    "missing-item", "method-item", "no-thru",
])
def test_rod_through_condition_cannot_pass_unreadable_or_non_through_native_ink(bound, defect):
    callout = _RenderedRodCallout(("#47 DRILL", "THRU"))
    if defect == "missing-data":
        callout.data = None
    elif defect == "empty":
        callout.data.count = 0
    elif defect == "missing-count":
        callout.data.count = None
    elif defect == "negative-count":
        callout.data.count = -1
    elif defect == "bool-count":
        callout.data.count = True
    elif defect == "method-count":
        callout.data.count = lambda: 2
    elif defect == "missing-item":
        callout.data.texts = ("#47 DRILL", None)
    elif defect == "method-item":
        callout.data.texts = ("#47 DRILL", lambda: "THRU")
    elif defect == "no-thru":
        callout.data.texts = ("#47 DRILL", "native diameter", "DEPTH")
        callout.data.count = len(callout.data.texts)
    with pytest.raises(RuntimeError):
        drawing._require_rod_through_callout(callout)


def test_d_caption_uses_left_of_title_block_space_not_global_title_top(bound, monkeypatch):
    note = _FakeNote((0.16, 0.04), 0.007)
    note.PropertyLinkedText = "$PRPVIEW:DETAIL D SCALE"
    note.annotation.SetPosition2 = note.annotation.SetPosition
    original_extent = note.GetExtent
    def narrow_caption():
        values = list(original_extent())
        values[3] = values[0] + 0.035
        return values
    note.GetExtent = narrow_caption
    adapter, view = _native_crop_fixture(monkeypatch, "D")
    view.notes = [note]
    sheet = _native_sheet()
    sheet.GetZoneMargin = lambda _side: 0.0127
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    drawing._seat_detail_caption(adapter, view, sheet, label="D")
    box = drawing._note_extent(adapter, note)
    assert box[3] < 0.066
    assert box[2] < drawing.DRAWING_TEMPLATES[drawing.SPEC.layout].title_block_left_m - 0.003
    assert box[1] >= 0.0127 + 0.003


@pytest.mark.parametrize("defect", [None, "crop", "notes", "missing", "invalid-text"])
def test_ream_native_text_clears_actual_detail_and_seated_notes(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    case.ream.data.texts = [{"t": "REAM +0.03", "pos": [0.094, 0.082, 0], "h": 0.0036}]
    case.ream.position = (0.120, 0.086, 0)
    if defect == "invalid-text":
        case.ream.data.texts[0]["h"] = 0.0
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: "PivotDia")
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
    if defect == "crop":
        hub.Position = hub.physical = (0.110 + hub.radius, drawing.HUB_CENTER[1])
    hub.annotations = [] if defect == "missing" else [case.ream]
    notes = (0.020, 0.016, 0.150, 0.082 if defect == "notes" else 0.070)
    if defect is None:
        drawing._require_ream_clearance(case.adapter, hub, notes)
        assert any("required_air_mm=1.000" in log for log in case.logs)
    else:
        with pytest.raises((RuntimeError, ValueError)):
            drawing._require_ream_clearance(case.adapter, hub, notes)


def test_ream_dimension_name_receives_bound_native_annotation(
    native_profile_clearance, native_annotation_binding, monkeypatch,
):
    case, binding = native_profile_clearance, native_annotation_binding
    case.ream.data.texts = [{"t": "REAM +0.03", "pos": [0.094, 0.082, 0], "h": 0.0036}]
    case.ream.position = (0.120, 0.086, 0)
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
    hub.annotations = [binding.raw(case.ream, "IAnnotation")]
    reads = []

    def read_name(_adapter, annotation):
        assert annotation is case.ream
        reads.append(annotation)
        return "PivotDia"

    monkeypatch.setattr(drawing, "dimension_name", read_name)
    drawing._require_ream_clearance(case.adapter, hub, (0.020, 0.016, 0.150, 0.070))
    assert reads == [case.ream]
    assert ("IAnnotation", case.ream) in binding.calls
    assert any("required_air_mm=1.000" in log for log in case.logs)


@pytest.mark.parametrize("defect", ["empty-view", "invalid-crop", "invalid-text"])
def test_front_detail_text_guard_cannot_pass_missing_native_geometry(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    case.front.GetAnnotations = lambda: [] if defect == "empty-view" else [case.r816]
    case.front.GetAnnotationCount = lambda: 0 if defect == "empty-view" else 1
    if defect == "invalid-text":
        case.r816.data.texts[0]["pos"][1] = float("nan")
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D", defect="invalid-bbox" if defect == "invalid-crop" else None)
    _adapter, end = _native_crop_fixture(monkeypatch, "E")
    with pytest.raises((RuntimeError, ValueError)):
        drawing._require_front_detail_air(case.adapter, case.front, hub, end)


@pytest.mark.parametrize("points", [[], [(0.18,)], [(0.18, float("nan"))], [(0.18, float("inf"))]])
def test_native_projection_fails_closed_on_missing_or_invalid_coordinates(bound, monkeypatch, points):
    events = []
    view = _native("IView", UpdateViewDisplayGeometry=lambda: events.append("barrier"))
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_a, **_k: points)
    with pytest.raises(RuntimeError, match="invalid native projected points"):
        drawing._project(object(), view, [(0.0, 0.008, 0.0)], label="detail D pivot")
    assert events == ["barrier"]


@pytest.mark.parametrize("defect", [None, "inside-circle", "missing-radius", "zero-projection", "invalid-position"])
def test_basic_radius_ink_uses_native_parent_circle_projection(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    annotations = []
    for name in ("TopRadius", "BottomRadius"):
        xy = drawing.FRONT_KEEP[name]
        text = _ClearanceDisplayData([{"t": "R800" if name == "TopRadius" else "R816",
                                      "pos": [*xy, 0.0], "h": 0.0035}], [])
        annotations.append(_ClearanceAnnotation(name, (*xy, 0.0), text, kind=4, hole_callout=False))
    if defect == "inside-circle":
        annotations[0].data.texts[0]["pos"][:2] = [0.130, 0.218]
    elif defect == "missing-radius":
        annotations.pop(0)
    elif defect == "invalid-position":
        annotations[0].position = (float("nan"), 0.136, 0.0)
    case.front.GetAnnotations = lambda: annotations
    case.front.GetAnnotationCount = lambda: len(annotations)
    events = []
    case.front.UpdateViewDisplayGeometry = lambda: events.append("barrier")
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    def native_project(_adapter, _view, points, **_kwargs):
        assert events == ["barrier"]
        return [_front_xy(0.0 if defect == "zero-projection" else x * 1000.0, y * 1000.0)
                for x, y, _z in points]
    monkeypatch.setattr(drawing, "model_points_in_view", native_project)
    if defect is None:
        drawing._require_radius_exterior(case.adapter, case.front)
        logs = "\n".join(case.logs)
        assert "native_circle_radius_mm=400.000" in logs
        assert "native_circle_radius_mm=408.000" in logs
        assert logs.count("actual_exterior_air_mm=") == 2
    else:
        with pytest.raises((RuntimeError, ValueError)):
            drawing._require_radius_exterior(case.adapter, case.front)


@pytest.mark.parametrize("defect", [None, "inside-circle", "missing-radius", "zero-projection", "invalid-position"])
def test_radius_ink_uses_native_parent_circle_projection(native_profile_clearance, bound, monkeypatch, defect):
    case = native_profile_clearance
    annotations = []
    for name in ("TopRadius", "BottomRadius"):
        xy = drawing.FRONT_KEEP[name]
        text = _ClearanceDisplayData([{"t": "R800" if name == "TopRadius" else "R816",
                                      "pos": [*xy, 0.0], "h": 0.0035}], [])
        annotations.append(_ClearanceAnnotation(name, (*xy, 0.0), text, kind=4, hole_callout=False))
    if defect == "inside-circle":
        annotations[0].data.texts[0]["pos"][:2] = [0.130, 0.218]
    elif defect == "missing-radius":
        annotations.pop(0)
    elif defect == "invalid-position":
        annotations[0].position = (float("nan"), 0.136, 0.0)
    case.front.GetAnnotations = lambda: annotations
    case.front.GetAnnotationCount = lambda: len(annotations)
    events = []
    case.front.UpdateViewDisplayGeometry = lambda: events.append("barrier")
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    def native_project(_adapter, _view, points, **_kwargs):
        assert events == ["barrier"]
        return [_front_xy(0.0 if defect == "zero-projection" else x * 1000.0, y * 1000.0)
                for x, y, _z in points]
    monkeypatch.setattr(drawing, "model_points_in_view", native_project)
    if defect is None:
        drawing._require_radius_exterior(case.adapter, case.front)
        logs = "\n".join(case.logs)
        assert "native_circle_radius_mm=400.000" in logs
        assert "native_circle_radius_mm=408.000" in logs
        assert logs.count("actual_exterior_air_mm=") == 2
    else:
        with pytest.raises((RuntimeError, ValueError)):
            drawing._require_radius_exterior(case.adapter, case.front)


def test_radius_dimension_name_receives_bound_native_annotations(
    native_profile_clearance, native_annotation_binding, monkeypatch,
):
    case, binding = native_profile_clearance, native_annotation_binding
    annotations = []
    for name in ("TopRadius", "BottomRadius"):
        xy = drawing.FRONT_KEEP[name]
        data = _ClearanceDisplayData([{"t": "R800" if name == "TopRadius" else "R816",
                                      "pos": [*xy, 0.0], "h": 0.0035}], [])
        annotations.append(_ClearanceAnnotation(name, (*xy, 0.0), data, kind=4, hole_callout=False))
    raw = [binding.raw(ann, "IAnnotation") for ann in annotations]
    case.front.GetAnnotations = lambda: raw
    case.front.GetAnnotationCount = lambda: len(raw)
    case.front.UpdateViewDisplayGeometry = lambda: None
    monkeypatch.setattr(drawing, "model_points_in_view",
                        lambda _adapter, _view, points, **_kwargs: [_front_xy(x * 1000.0, y * 1000.0) for x, y, _z in points])
    reads = []

    def read_name(_adapter, annotation):
        assert annotation in annotations
        reads.append(annotation)
        return annotation.name

    monkeypatch.setattr(drawing, "dimension_name", read_name)
    drawing._require_radius_exterior(case.adapter, case.front)
    assert reads == annotations * 2
    assert [ann for interface, ann in binding.calls if interface == "IAnnotation"] == annotations
    assert sum("actual_exterior_air_mm=" in log for log in case.logs) == 2


@pytest.mark.parametrize("properties", [None, (), (0.0, 0.0, 1.0)])
def test_sheet_scale_cannot_claim_success_without_native_properties(bound, properties):
    sheet = _native("ISheet", SetScale=lambda *_args: True, GetProperties2=lambda: properties)
    with pytest.raises(RuntimeError, match="sheet scale did not persist"):
        drawing._pin_sheet_scale(object(), sheet)


class _StyleTextFormat:
    """Native get/put properties; CharHeight switches authority to metres."""

    _native_interfaces = ("ITextFormat",)

    def __init__(self, height=0.00635, *, points=False, font="Century Gothic"):
        self._height, self.points, self.font = height, points, font

    CharHeight = property(
        lambda self: self._height,
        lambda self, value: (setattr(self, "_height", value), setattr(self, "points", False)),
    )
    CharHeightInPts = property(lambda self: 24)
    TypeFaceName = property(lambda self: self.font)

    def IsHeightSpecifiedInPts(self):
        return self.points


class _StyleNote(_CaptionNote):
    """R15 local formatting cannot resize the generated SCALE/ratio space."""

    def __init__(self, label, *, ordinary_height=None):
        super().__init__(label, height=0.0166799)
        self.rich = ordinary_height is None
        self.has_multiple = False  # Exercise height guards independently of this flag.
        self.use_doc = True
        self.text_format = _StyleTextFormat(0.00635 if self.rich else ordinary_height)
        self.font_height = self.text_format.CharHeight
        self.writes, self.events = [], []
        self.reset_result = self.write_result = True
        self.on_write = lambda: None
        self.readback_delta = 0.0
        self.document_applied = False
        self._linked = (
            "<VLNAME> <FONT size=3.5><VLLABEL>\r\n"
            "<VLSCALE><FONT size=6.35> <FONT size=3.5><VLSCALEV><FONT size=6.35>"
            if self.rich else '$PRPSHEET:"Manufacturing Notes"'
        )
        runs = [
            ("DETAIL ", 0.0035), (label + "\r\n", 0.0035),
            ("SCALE", 0.0035), (" ", 0.00635),
            ("4:1" if label == "D" else "2:1", 0.0035),
        ] if self.rich else [("1. TURN HUB\r\n", ordinary_height), ("2. REAM BORE", ordinary_height)]
        self.data = _ClearanceDisplayData([
            {"t": text, "h": height, "font": "Century Gothic", "pos": [0.30, 0.07, 0.0]}
            for text, height in runs
        ], [])
        self.data.GetTextFontAtIndex = lambda index: self.data.texts[index]["font"]
        self.annotation.GetDisplayData = lambda: self.data
        self.annotation.GetTextFormat = self.get_format
        self.annotation.GetUseDocTextFormat = lambda _index: self.use_doc
        self.annotation.SetTextFormat = self.set_format

    HasMultipleFonts = property(lambda self: self.has_multiple)

    def GetText(self):
        return " \r\n "  # Not resolved native view-field glyphs.

    def get_format(self, index):
        assert index == 0
        self.events.append("get-format")
        return self.text_format

    def set_format(self, index, use_doc, text_format):
        assert index == 0
        self.writes.append((index, use_doc, None if text_format is None else text_format.CharHeight))
        self.events.append("reset" if use_doc else "local")
        result = self.reset_result if use_doc else self.write_result
        if result is not True:
            return result
        if use_doc:
            assert text_format is None
            self.rich, self.use_doc = False, True
            self._linked = re.sub(r"<FONT[^>]*>", "", self._linked)
        else:
            if self.rich:
                return False
            self.font_height, self.use_doc = text_format.CharHeight, False
            for fragment in self.data.texts:
                if fragment["t"] != " ":  # Actual R15 standalone separator stays 6.35 mm.
                    fragment["h"] = self.font_height + self.readback_delta
            self.height = self.font_height * 2.0
            self.on_write()
        return True

    def apply_document_font(self, preferences):
        if not self.rich or self.document_applied:
            return
        # Generated native runs inherit distinct document detail-font families.
        for fragment, preference in zip(self.data.texts, ((42, 301), (43, 301), (44, 301), (18, 0), (45, 301)), strict=True):
            text_format = preferences[preference]
            fragment["h"] = text_format.CharHeight + self.readback_delta
            fragment["font"] = text_format.TypeFaceName
        self.font_height = self.data.texts[0]["h"]
        self.height = self.font_height * 2.0
        self.document_applied = True
        self.on_write()


class _StyleDocExtension:
    """Document-only native preference methods with detached fresh readbacks."""

    _native_interfaces = ("IModelDocExtension",)

    def __init__(self, notes, circles):
        self.notes, self.circles = notes, circles
        self.preferences = {
            pair: _StyleTextFormat(font="Arial")
            for pair in ((18, 0), (3, 301), (42, 301), (43, 301), (44, 301), (45, 301))
        }
        self.writes, self.reads = [], []
        self.result = True
        self.on_write = lambda _preference: None
        self.on_read = lambda _preference, text_format: text_format

    def SetUserPreferenceTextFormat(self, preference, option, text_format):
        self.writes.append((preference, option, text_format))
        if self.result is True:
            self.preferences[preference, option] = _StyleTextFormat(
                text_format.CharHeight, points=text_format.IsHeightSpecifiedInPts(),
                font=text_format.TypeFaceName,
            )
            self.on_write(preference)
        return self.result

    def GetUserPreferenceTextFormat(self, preference, option):
        self.reads.append((preference, option))
        installed = self.preferences[preference, option]
        return self.on_read(preference, _StyleTextFormat(
            installed.CharHeight, points=installed.IsHeightSpecifiedInPts(), font=installed.TypeFaceName,
        ))

    def create_details(self):
        assert len(self.writes) == 6
        for note in self.notes.values():
            note.apply_document_font(self.preferences)
        text_format = self.preferences[3, 301]
        for circle in self.circles.values():
            circle.font_height, circle.font = text_format.CharHeight, text_format.TypeFaceName
            circle.use_doc, circle.points = True, text_format.IsHeightSpecifiedInPts()


class _StyleCircle(_DetailCircle):
    """Local native circle formatting; a refused setter leaves format unmoved."""

    def __init__(self, label, front, view):
        super().__init__(label)
        self.xy = drawing.DETAIL_LETTER_XY[label]
        # Native textPt and GetLabelPosition need not describe the same anchor.
        self.display_xy = (self.xy[0] + 0.0007, self.xy[1] - 0.0004)
        self.arrows = []
        self.front, self.view = front, view
        self.font_height, self.use_doc, self.points = 0.00635, True, True
        self.font = "Century Gothic"
        self.result = True
        self.delta = self.display_delta = 0.0
        self.writes = []
        self.on_write = lambda: None

    def GetView(self):
        return self.front

    def GetDetailView(self):
        return self.view

    def GetTextFormat(self):
        return _StyleTextFormat(self.font_height, points=self.points, font=self.font)

    def GetUseDocTextFormat(self):
        return self.use_doc

    def SetTextFormat(self, use_doc, text_format):
        self.writes.append((use_doc, text_format.CharHeight))
        if self.result is True:
            self.font_height = text_format.CharHeight + self.delta
            self.use_doc, self.points = use_doc, text_format.IsHeightSpecifiedInPts()
            self.font = text_format.TypeFaceName
            self.on_write()
        return self.result


@pytest.fixture
def native_caption_style(bound, monkeypatch):
    import _drawing_notes

    monkeypatch.setattr(_drawing_notes, "_early_bound", _bind_owner)
    front = _native("IView")
    notes = {label: _StyleNote(label) for label in ("D", "E")}
    views = {
        label: _native("IView", GetNotes=lambda label=label: [notes[label]], GetBaseView=lambda: front,
        Position=drawing.HUB_CENTER if label == "D" else drawing.END_CENTER,
        ScaleRatio=drawing.HUB_SCALE if label == "D" else drawing.END_SCALE,
        UseParentScale=False, UseSheetScale=0,) for label in ("D", "E")
    }
    circles = {label: _StyleCircle(label, front, views[label]) for label in ("D", "E")}
    front.GetDetailCircles = lambda: [circles["E"], circles["D"]]

    display_order, display_reads = ["D", "E"], []
    circle_padding = []

    def circle_info():
        display_reads.append({label: tuple(circle.writes) for label, circle in circles.items()})
        values = [2.0]
        for label in display_order:
            circle = circles[label]
            values.extend([
                0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                *circle.display_xy, 0, circle.font_height + circle.display_delta, len(circle.arrows),
            ])
            for arrow in circle.arrows:
                values.extend(arrow)
        values.extend(circle_padding)
        return tuple(values)

    front.GetDetailCircleInfo2 = circle_info
    # Native allocation metadata is independent of a replaced info method.
    front.GetDetailCircleCount2 = lambda: (
        len(circles),
        1 + sum(16 + 9 * len(circle.arrows) for circle in circles.values()) + len(circle_padding),
    )
    events, captures = [], []
    extension = _StyleDocExtension(notes, circles)
    def redraw():
        events.append("redraw")
    adapter = SimpleNamespace(
        currentModel=_native("IModelDoc2", Extension=extension, GraphicsRedraw2=redraw),
        swApp=_native("ISldWorks", IsSame=_APP.IsSame),  # No application preferences exist.
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: events.append("rebuild"))
    monkeypatch.setattr(
        drawing._seat_forensics, "capture_com_failure",
        lambda *_args, **context: captures.append(context["exception"]),
    )
    return SimpleNamespace(
        adapter=adapter, front=front, notes=notes, views=views, circles=circles,
        source=_StyleNote("source", ordinary_height=0.0035), events=events, captures=captures,
        extension=extension, display_order=display_order, display_reads=display_reads,
        circle_padding=circle_padding,
    )


def _normalize_style(case):
    font_source = drawing._pin_detail_caption_font_source(case.adapter, case.source)
    case.extension.create_details()  # Native creation happens only AFTER the source pin.
    drawing._normalize_detail_caption_styles(
        case.adapter, case.front, case.views["D"], case.views["E"], font_source,
    )


@pytest.mark.parametrize("height", [0.0035, 0.0042])
@pytest.mark.parametrize("font", ["Century Gothic", "Arial"])
@pytest.mark.parametrize("display_order", [("D", "E"), ("E", "D")])
def test_normal_note_native_font_drives_document_captions_and_source_circles(native_caption_style, height, font, display_order):
    case = native_caption_style
    case.display_order[:] = display_order
    case.source.text_format.CharHeight = height
    case.source.text_format.font = font
    for fragment in case.source.data.texts:
        fragment["h"], fragment["font"] = height, font
    source_format = dict(vars(case.source.text_format))
    source_linked = case.source.PropertyLinkedText
    linked = {label: note.PropertyLinkedText for label, note in case.notes.items()}
    positions = {label: note.annotation.GetPosition() for label, note in case.notes.items()}
    _normalize_style(case)
    assert vars(case.source.text_format) == source_format
    assert case.source.PropertyLinkedText == source_linked
    assert case.source.writes == []
    assert [(preference, option) for preference, option, _format in case.extension.writes] == [
        (18, 0), (3, 301), (42, 301), (43, 301), (44, 301), (45, 301)
    ]
    assert all(text_format is case.source.text_format for _pref, _option, text_format in case.extension.writes)
    assert case.extension.reads == [(18, 0), (3, 301), (42, 301), (43, 301), (44, 301), (45, 301)] * 3
    for label in ("D", "E"):
        note, circle, view = case.notes[label], case.circles[label], case.views[label]
        assert note.writes == [] and note.events == []
        assert note.PropertyLinkedText == linked[label]
        assert note.annotation.GetPosition() == positions[label]
        assert note.annotation.GetUseDocTextFormat(0) is True
        assert [fragment["h"] for fragment in note.data.texts] == [height] * 5
        assert [fragment["font"] for fragment in note.data.texts] == [font] * 5
        assert note.data.texts[3]["t"] == " "  # Generated separator is not skipped.
        assert circle.writes == [(False, height)]
        assert circle.GetLabel() == label and circle.xy == drawing.DETAIL_LETTER_XY[label]
        assert math.dist(circle.display_xy, circle.GetLabelPosition()) > 1e-8
        assert circle.font_height == height and circle.GetUseDocTextFormat() is False
        assert circle.GetTextFormat().TypeFaceName == font
        assert view.Position == (drawing.HUB_CENTER if label == "D" else drawing.END_CENTER)
    assert case.events.count("rebuild") == 3 and case.events.count("redraw") == 6
    assert case.display_reads == [{label: ((False, height),) for label in ("D", "E")}]
    assert case.captures == []


def test_r15_local_reset_leaves_native_scale_space_but_document_source_pin_fixes_it(native_caption_style):
    local_note = _StyleNote("D")
    annotation = local_note.annotation
    assert annotation.SetTextFormat(0, True, None) is True
    text_format = annotation.GetTextFormat(0)
    text_format.CharHeight = 0.0035
    assert annotation.SetTextFormat(0, False, text_format) is True
    assert local_note.data.texts[3]["t"] == " "
    assert local_note.data.texts[3]["h"] == 0.00635
    assert all(fragment["h"] == 0.0035 for index, fragment in enumerate(local_note.data.texts) if index != 3)
    case = native_caption_style
    assert case.notes["D"].data.texts[3]["h"] == 0.00635
    _normalize_style(case)
    assert case.notes["D"].data.texts[3]["h"] == 0.0035
    assert case.notes["D"].writes == []


@pytest.mark.parametrize("defect", ["height", "font"])
def test_generated_space_must_inherit_source_even_when_all_document_preferences_read_back(native_caption_style, defect):
    case = native_caption_style
    create = case.extension.create_details
    def create_with_stale_separator():
        create()
        separator = case.notes["D"].data.texts[3]
        separator["h" if defect == "height" else "font"] = 0.00635 if defect == "height" else "Arial"
    case.extension.create_details = create_with_stale_separator
    with pytest.raises(RuntimeError, match="caption font/content readback mismatch") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert len(case.extension.reads) == 12
    assert all(circle.writes == [] for circle in case.circles.values())
    assert case.notes["D"].writes == []


@pytest.mark.parametrize("has_multiple", [True, None, 1, "false"])
def test_uniform_native_fragments_do_not_relax_multiple_fonts_guard(native_caption_style, has_multiple):
    case = native_caption_style
    case.notes["D"].has_multiple = has_multiple
    with pytest.raises(RuntimeError, match="caption font/content readback mismatch") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert all(fragment["h"] == 0.0035 for fragment in case.notes["D"].data.texts)
    assert all(circle.writes == [] for circle in case.circles.values())


@pytest.mark.parametrize("char_height", [None, 0.0041])
def test_ordinary_linked_note_factory_keeps_no_height_and_single_write_paths(native_caption_style, monkeypatch, char_height):
    import _drawing_notes

    note = _StyleNote("ordinary", ordinary_height=0.0035)
    calls = []
    def add_note(adapter, text, x, y):
        calls.append((adapter, text, x, y))
        return note
    monkeypatch.setattr(_drawing_notes, "add_note", add_note)
    returned = _drawing_notes.add_property_linked_note(
        native_caption_style.adapter, "Manufacturing Notes", 0.02, 0.08, char_height=char_height,
    )
    assert returned is note
    assert calls == [(native_caption_style.adapter, '$PRPSHEET:"Manufacturing Notes"', 0.02, 0.08)]
    assert note.PropertyLinkedText == '$PRPSHEET:"Manufacturing Notes"'
    assert note.writes == ([] if char_height is None else [(0, False, char_height)])
    assert "reset" not in note.events
    assert native_caption_style.extension.writes == []


@pytest.mark.parametrize("defect", [
    "missing-display", "missing-annotation", "no-fragments", "blank-text", "mixed-height",
    "mixed-font", "zero", "nan", "infinite", "missing-height", "missing-font", "bad-count",
])
def test_unavailable_mixed_or_invalid_normal_note_height_is_fatal_and_captured(native_caption_style, defect):
    case = native_caption_style
    source = case.source
    if defect == "missing-display":
        source.annotation.GetDisplayData = lambda: None
    elif defect == "missing-annotation":
        source.GetAnnotation = lambda: None
    elif defect == "no-fragments":
        source.data.texts.clear()
    elif defect == "blank-text":
        for fragment in source.data.texts:
            fragment["t"] = " \r\n "
    elif defect == "mixed-height":
        source.data.texts[-1]["h"] = 0.00635
    elif defect == "mixed-font":
        source.data.GetTextFontAtIndex = lambda index: "Arial" if index == 0 else "Century Gothic"
    elif defect == "missing-font":
        source.data.GetTextFontAtIndex = lambda _index: None
    elif defect == "bad-count":
        source.data.GetTextCount = lambda: True
    else:
        source.data.texts[0]["h"] = {
            "zero": 0.0, "nan": float("nan"), "infinite": float("inf"), "missing-height": None,
        }[defect]
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert all(note.writes == [] for note in case.notes.values())


@pytest.mark.parametrize("defect", [
    "missing-format", "getter-refusal", "stale-height", "zero-height", "nan-height", "bool-height",
    "missing-font", "wrong-font", "blank-font", "point-authority", "invalid-authority", "invalid-use-doc",
])
def test_source_format_must_match_actual_normal_note_ink_without_mutating_it(native_caption_style, defect):
    case = native_caption_style
    source = case.source
    if defect == "missing-format":
        source.annotation.GetTextFormat = lambda _index: None
    elif defect == "getter-refusal":
        def refuse(_index):
            raise RuntimeError("source format getter refused")
        source.annotation.GetTextFormat = refuse
    elif defect == "invalid-use-doc":
        source.use_doc = 1
    elif defect.endswith("height"):
        source.text_format._height = {
            "stale-height": 0.00635, "zero-height": 0.0, "nan-height": float("nan"), "bool-height": True,
        }[defect]
    elif defect.endswith("font"):
        source.text_format.font = {"missing-font": None, "wrong-font": "Arial", "blank-font": " "}[defect]
    else:
        source.text_format.points = True if defect == "point-authority" else 1
    before = dict(vars(source.text_format))
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.extension.writes == []
    assert vars(source.text_format) == before
    assert source.writes == []


@pytest.mark.parametrize("preference", [18, 3, 42, 43, 44, 45])
@pytest.mark.parametrize("phase", ["immediate", "after-rebuild"])
@pytest.mark.parametrize("defect", [
    "missing-format", "stale-height", "zero-height", "nan-height", "bool-height",
    "missing-font", "wrong-font", "point-authority", "invalid-authority",
])
def test_every_document_font_requires_fresh_native_source_readback(native_caption_style, preference, phase, defect):
    case = native_caption_style
    def corrupt(pref, text_format):
        if pref != preference or (phase == "after-rebuild" and len(case.extension.reads) <= 6):
            return text_format
        if defect == "missing-format":
            return None
        if defect.endswith("height"):
            text_format._height = {
                "stale-height": 0.00635, "zero-height": 0.0,
                "nan-height": float("nan"), "bool-height": True,
            }[defect]
        elif defect.endswith("font"):
            text_format.font = None if defect == "missing-font" else "Arial"
        else:
            text_format.points = True if defect == "point-authority" else 1
        return text_format
    case.extension.on_read = corrupt
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert all(note.writes == [] for note in case.notes.values())
    assert case.source.writes == []


@pytest.mark.parametrize("preference", [18, 3, 42, 43, 44, 45])
def test_each_document_preference_setter_refusal_is_fatal(native_caption_style, preference):
    case = native_caption_style
    original = case.extension.SetUserPreferenceTextFormat
    def refuse(pref, option, text_format):
        if pref == preference:
            return False
        return original(pref, option, text_format)
    case.extension.SetUserPreferenceTextFormat = refuse
    with pytest.raises(RuntimeError, match="document font setter refused") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("defect", ["format", "content", "position", "use-doc"])
def test_source_note_stays_unchanged_through_document_font_pin(native_caption_style, defect):
    case = native_caption_style
    def mutate(pref):
        if pref != 45:
            return
        if defect == "format":
            case.source.text_format.font = "Arial"
        elif defect == "content":
            case.source._linked += " DETACHED"
        elif defect == "position":
            case.source.annotation.position = (0.0, 0.0)
        else:
            case.source.use_doc = not case.source.use_doc
    case.extension.on_write = mutate
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("target", ["document", "circle"])
@pytest.mark.parametrize("result", [False, None, 1, "true"])
def test_native_font_setters_require_actual_true(native_caption_style, target, result):
    case = native_caption_style
    if target == "document":
        case.extension.result = result
    else:
        case.circles["D"].result = result
    with pytest.raises(RuntimeError, match="setter refused") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("defect", [
    "drop-name", "drop-label", "drop-scale", "drop-ratio", "reorder", "duplicate", "linked-content",
    "stale-height", "missing-fragment", "multiple-fonts", "bad-font-authority", "mixed-font", "wrong-uniform-font",
    "stale-space", "space-font", "missing-space", "lost-owner", "moved-view", "moved-caption",
    "scale-changed", "parent-scale-changed", "sheet-scale-changed", "replaced-note", "local-authority",
])
def test_document_source_pin_rejects_lost_fields_fragments_fonts_and_native_state(native_caption_style, defect):
    case = native_caption_style
    note, view = case.notes["D"], case.views["D"]
    def mutate():
        if defect.startswith("drop-"):
            field = {
                "drop-name": "<VLNAME>", "drop-label": "<VLLABEL>",
                "drop-scale": "<VLSCALE>", "drop-ratio": "<VLSCALEV>",
            }[defect]
            note._linked = note._linked.replace(field, "")
        elif defect == "reorder":
            note._linked = "<VLLABEL><VLNAME><VLSCALE><VLSCALEV>"
        elif defect == "duplicate":
            note._linked += "<VLLABEL>"
        elif defect == "linked-content":
            note._linked += " DETACHED TEXT"
        elif defect == "stale-height":
            note.data.texts[0]["h"] = 0.00635
        elif defect == "missing-fragment":
            note.data.texts.pop(1)
        elif defect == "multiple-fonts":
            note.has_multiple = True
        elif defect == "bad-font-authority":
            note.has_multiple = None
        elif defect == "mixed-font":
            note.data.GetTextFontAtIndex = lambda index: "Arial" if index == 0 else "Century Gothic"
        elif defect == "wrong-uniform-font":
            note.data.GetTextFontAtIndex = lambda _index: "Arial"
        elif defect == "stale-space":
            note.data.texts[3]["h"] = 0.00635
        elif defect == "space-font":
            note.data.texts[3]["font"] = "Arial"
        elif defect == "missing-space":
            note.data.texts.pop(3)
        elif defect == "lost-owner":
            view.GetBaseView = lambda: object()
        elif defect == "moved-view":
            view.Position = (0.0, 0.0)
        elif defect == "moved-caption":
            note.annotation.position = (0.0, 0.0)
        elif defect == "scale-changed":
            view.ScaleRatio = (1.0, 1.0)
        elif defect == "parent-scale-changed":
            view.UseParentScale = True
        elif defect == "sheet-scale-changed":
            view.UseSheetScale = 1
        elif defect == "replaced-note":
            replacement = _StyleNote("D")
            view.GetNotes = lambda: [replacement]
        elif defect == "local-authority":
            note.use_doc = False
    case.circles["D"].on_write = mutate
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("defect", [
    "format-height", "label", "position", "owner", "detail-owner",
    "doc-authority", "point-authority", "font",
])
def test_source_circle_readbacks_are_independent_and_preserve_native_identity(native_caption_style, label, defect):
    case = native_caption_style
    circle = case.circles[label]
    if defect == "format-height":
        circle.delta = 0.001
    else:
        def mutate():
            if defect == "label":
                circle.label = "X"
            elif defect == "position":
                circle.xy = (0.0, 0.0)
            elif defect == "owner":
                circle.front = object()
            elif defect == "detail-owner":
                circle.view = object()
            elif defect == "doc-authority":
                circle.use_doc = True
            elif defect == "point-authority":
                circle.points = True
            elif defect == "font":
                circle.font = "Arial"
        circle.on_write = mutate
    with pytest.raises(RuntimeError) as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == []


@pytest.mark.parametrize("display_order", [("D", "E"), ("E", "D")])
def test_native_circle_display_height_batch_needs_no_unique_text_anchor(native_caption_style, display_order):
    case = native_caption_style
    case.display_order[:] = display_order
    case.circles["E"].display_xy = case.circles["D"].display_xy
    _normalize_style(case)
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]
    assert case.captures == []


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("delta", [0.0, 0.00000005, 0.0000002])
def test_native_circle_display_height_batch_uses_existing_height_tolerance(native_caption_style, label, delta):
    case = native_caption_style
    case.circles[label].display_delta = delta
    if delta > drawing._NOTE_HEIGHT_READBACK_TOL_M:
        with pytest.raises(RuntimeError, match="displayed-height mismatch") as caught:
            _normalize_style(case)
        assert case.captures == [caught.value]
    else:
        _normalize_style(case)
        assert case.captures == []
    assert case.display_reads == [{letter: ((False, 0.0035),) for letter in ("D", "E")}]


@pytest.mark.parametrize("label", ["D", "E"])
@pytest.mark.parametrize("delta", [0.001, -0.001, float("nan"), float("inf")])
def test_native_circle_display_height_mismatch_is_fatal_after_both_writes(native_caption_style, label, delta):
    case = native_caption_style
    case.circles[label].display_delta = delta
    with pytest.raises(RuntimeError, match="displayed-height mismatch|invalid native circle display data") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == [{letter: ((False, 0.0035),) for letter in ("D", "E")}]
    assert all(circle.writes == [(False, 0.0035)] for circle in case.circles.values())


@pytest.mark.parametrize("defect", [
    "missing-info", "empty-info", "wrong-count", "fractional-count", "nonnumeric-info",
    "boolean-info", "nonfinite-info", "truncated-header", "truncated-arrow",
    "negative-arrows", "fractional-arrows", "trailing-data",
])
def test_native_circle_display_batch_requires_complete_flat_shape_and_arrows(native_caption_style, defect):
    case = native_caption_style
    original = case.front.GetDetailCircleInfo2

    def malformed_info():
        values = list(original())
        if defect == "missing-info":
            return None
        if defect == "empty-info":
            return ()
        if defect == "wrong-count":
            values[0] = 3.0
        elif defect == "fractional-count":
            values[0] = 2.5
        elif defect == "nonnumeric-info":
            values[1] = "layer"
        elif defect == "boolean-info":
            values[1] = False
        elif defect == "nonfinite-info":
            values[1] = float("nan")
        elif defect == "truncated-header":
            values.pop()
        elif defect == "truncated-arrow":
            values[-1] = 1.0
            values.extend([0.0] * 8)  # A complete native arrow has nine doubles.
        elif defect == "negative-arrows":
            values[16] = -1.0
        elif defect == "fractional-arrows":
            values[16] = 0.5
        elif defect == "trailing-data":
            values.append(0.0)
        return tuple(values)

    case.front.GetDetailCircleInfo2 = malformed_info
    with pytest.raises(RuntimeError, match="native circle (display data|arrow count)") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]
    if defect == "trailing-data":
        assert case.front.GetDetailCircleCount2() == (2, 33)
        assert "count/size mismatch" in str(caught.value)


@pytest.mark.parametrize("metadata", [
    None, 2, (), (2,), (2, 33, 0), [2, 33],
    (True, 33), (False, 33), (2.0, 33), ("2", 33), (None, 33),
    (float("nan"), 33), (float("inf"), 33), ((2,), 33),
    (0, 33), (-1, 33), (1, 33), (3, 33),
    (2, True), (2, False), (2, 33.0), (2, "33"), (2, None),
    (2, float("nan")), (2, float("inf")), (2, (33,)), (2, 0), (2, -1),
])
def test_native_circle_display_batch_requires_strict_count_allocation_pair(native_caption_style, metadata):
    case = native_caption_style
    case.front.GetDetailCircleCount2 = lambda: metadata
    with pytest.raises(RuntimeError, match="invalid native circle display data metadata") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == []
    assert all(circle.writes == [(False, 0.0035)] for circle in case.circles.values())


@pytest.mark.parametrize("size", [1, 32, 34, 69])
def test_native_circle_display_batch_requires_independent_allocation_size(native_caption_style, size):
    case = native_caption_style
    case.front.GetDetailCircleCount2 = lambda: (2, size)
    with pytest.raises(RuntimeError, match="native circle display data count/size mismatch") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]


@pytest.mark.parametrize("defect", [
    "missing-records", "first-header", "last-header", "first-arrow", "last-arrow",
    "first-arrow-consumes-next-header", "last-arrow-overflow",
])
def test_native_circle_display_batch_bounds_every_record_before_decode(native_caption_style, monkeypatch, defect):
    case = native_caption_style
    original = case.front.GetDetailCircleInfo2
    sizes = {
        "missing-records": 1, "first-header": 16, "last-header": 32,
        "first-arrow": 25, "last-arrow": 41,
        "first-arrow-consumes-next-header": 33, "last-arrow-overflow": 33,
    }
    case.front.GetDetailCircleCount2 = lambda: (2, sizes[defect])

    def truncated_info():
        values = list(original())
        if defect == "missing-records":
            return tuple(values[:1])
        if defect == "first-header":
            return tuple(values[:16])
        if defect == "last-header":
            return tuple(values[:-1])
        if defect == "first-arrow":
            values[16] = 1.0
            values = values[:17] + [0.0] * 8
        elif defect == "last-arrow":
            values[32] = 1.0
            values.extend([0.0] * 8)
        elif defect == "first-arrow-consumes-next-header":
            values[16] = 1.0
        elif defect == "last-arrow-overflow":
            values[32] = 9999.0
        return tuple(values)

    case.front.GetDetailCircleInfo2 = truncated_info
    monkeypatch.setattr(drawing, "_detail_circles", lambda _info: pytest.fail("incomplete native records reached decoder"))
    with pytest.raises(RuntimeError, match="truncated native circle (display data|arrow record)") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]
    if defect in ("first-arrow", "last-arrow", "last-arrow-overflow"):
        assert "arrow record" in str(caught.value)


def test_native_circle_display_batch_accepts_exact_r16_allocated_vector(native_caption_style, monkeypatch):
    case = native_caption_style
    # Exact native R16 records from artifact 3190, followed by its 36 zero doubles.
    info = (
        2.0,
        -1.0, 0.18, 0.1716763399685608, 0.0,
        0.18336249999999998, 0.1716763399685608, 0.0,
        0.18336249999999998, 0.1716763399685608, 0.0, 3.0,
        0.16538373244147153, 0.15733303678929766, -1.1181611215881618e-15, 0.0035, 0.0,
        -1.0, 0.24975295579711881, 0.17771793560798294, 0.0,
        0.25571249057224477, 0.17771793560798294, 0.0,
        0.25571249057224477, 0.17771793560798294, 0.0, 3.0,
        0.2626037190635451, 0.15018450836120403, -1.0682432143744043e-15, 0.0035, 0.0,
    ) + (0.0,) * 36
    original_info, original_decode = case.front.GetDetailCircleInfo2, drawing._detail_circles
    decoded_inputs = []

    def native_info():
        original_info()
        return info

    def record_decode(values):
        decoded_inputs.append(values)
        return original_decode(values)

    case.front.GetDetailCircleCount2 = lambda: (2, 69)
    case.front.GetDetailCircleInfo2 = native_info
    monkeypatch.setattr(drawing, "_detail_circles", record_decode)
    assert len(info) == 69
    assert info[15] == info[31] == 0.0035
    _normalize_style(case)
    assert decoded_inputs == [info]
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]
    assert case.captures == []


@pytest.mark.parametrize("padding_index", [0, 35])
@pytest.mark.parametrize("unused_value", [
    1.0, -1.0, 5e-324, float("nan"), float("inf"), -float("inf"),
    None, "0", False, (0.0,),
])
def test_native_circle_display_batch_rejects_corrupted_declared_unused_allocation(native_caption_style, monkeypatch, padding_index, unused_value):
    case = native_caption_style
    case.circle_padding.extend([0.0] * 36)
    case.circle_padding[padding_index] = unused_value
    assert case.front.GetDetailCircleCount2() == (2, 69)
    monkeypatch.setattr(drawing, "_detail_circles", lambda _info: pytest.fail("corrupted native allocation reached decoder"))
    with pytest.raises(RuntimeError, match="native circle display data") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]


@pytest.mark.parametrize("arrow_counts", [(0, 0), (0, 1), (1, 2), (2, 0)])
@pytest.mark.parametrize("padding_size", [0, 7, 36])
@pytest.mark.parametrize("container", [tuple, list])
def test_native_circle_display_height_batch_accepts_complete_variable_arrow_records(native_caption_style, arrow_counts, padding_size, container):
    case = native_caption_style
    arrow = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0005, 0.001, 0.0)
    for label, count in zip(("D", "E"), arrow_counts, strict=True):
        case.circles[label].arrows = [arrow] * count
    case.circle_padding.extend([0.0] * padding_size)
    original = case.front.GetDetailCircleInfo2
    case.front.GetDetailCircleInfo2 = lambda: container(original())
    assert case.front.GetDetailCircleCount2() == (2, 33 + 9 * sum(arrow_counts) + padding_size)
    _normalize_style(case)
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]
    assert case.captures == []


@pytest.mark.parametrize("decoded_count", [0, 1, 3])
def test_native_circle_display_batch_requires_exactly_two_decoded_entries(native_caption_style, monkeypatch, decoded_count):
    case = native_caption_style
    original = drawing._detail_circles

    def incomplete_decoder(info):
        decoded = original(info)
        return (decoded + decoded[:1])[:decoded_count]

    monkeypatch.setattr(drawing, "_detail_circles", incomplete_decoder)
    with pytest.raises(RuntimeError, match="exactly two native circle display-height readbacks") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]
    assert case.display_reads == [{label: ((False, 0.0035),) for label in ("D", "E")}]


@pytest.mark.parametrize("delta", [0.0, 0.00000005, 0.0002])
def test_native_font_quantization_is_small_not_a_pixel_or_point_fallback(native_caption_style, delta):
    case = native_caption_style
    for note in case.notes.values():
        note.readback_delta = delta
    for circle in case.circles.values():
        circle.delta = circle.display_delta = delta / 2
    if delta > drawing._NOTE_HEIGHT_READBACK_TOL_M:
        with pytest.raises(RuntimeError, match="readback mismatch"):
            _normalize_style(case)
    else:
        _normalize_style(case)
        assert case.captures == []


@pytest.mark.parametrize("phase", ["source", "document-get", "document-set", "caption", "circle", "circle-count-batch", "circle-display-batch"])
@pytest.mark.parametrize("capture_fails", [False, True])
def test_style_refusals_preserve_original_exception_and_forensics_before_seat_close(native_caption_style, monkeypatch, phase, capture_fails):
    case = native_caption_style
    events, warnings = [], []
    original = RuntimeError("native style read refused")
    def refuse(*_args, **_kwargs):
        events.append("refusal")
        raise original
    if phase == "source":
        case.source.annotation.GetDisplayData = refuse
    elif phase == "document-get":
        case.extension.GetUserPreferenceTextFormat = refuse
    elif phase == "document-set":
        case.extension.SetUserPreferenceTextFormat = refuse
    elif phase == "caption":
        case.notes["D"].annotation.GetDisplayData = refuse
    elif phase == "circle":
        case.circles["D"].GetTextFormat = refuse
    elif phase == "circle-count-batch":
        case.front.GetDetailCircleCount2 = refuse
    else:
        case.front.GetDetailCircleInfo2 = refuse
    def capture(adapter, _label, message, **context):
        events.append("capture")
        assert adapter is case.adapter and message == str(original)
        assert context["exception"] is original and context["sheet_png"] is True
        if capture_fails:
            raise OSError("disk refused")
        raise original
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(drawing._telemetry, "warn", warnings.append)
    with pytest.raises(RuntimeError) as caught:
        try:
            _normalize_style(case)
        finally:
            events.append("seat-close")
    assert caught.value is original
    assert events == ["refusal", "capture", "seat-close"]
    assert bool(warnings) is capture_fails
    if phase in ("circle-count-batch", "circle-display-batch"):
        assert all(circle.writes == [(False, 0.0035)] for circle in case.circles.values())


def test_style_normalization_precedes_settled_link_capture_and_both_final_probes():
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    (normalize,) = [node for node in calls if node.func.id == "_normalize_detail_caption_styles"]
    (letters,) = [node for node in calls if node.func.id == "_place_detail_letters"]
    (pin_source,) = [node for node in calls if node.func.id == "_pin_detail_caption_font_source"]
    detail_creations = [node for node in calls if node.func.id == "_create_detail"]
    (source_note,) = [
        node for node in calls if node.func.id == "add_property_linked_note"
        and len(node.args) > 1 and ast.literal_eval(node.args[1]) == "Manufacturing Notes"
    ]
    (source_seat,) = [node for node in calls if node.func.id == "_seat_notes_on_border"]
    assert source_note.lineno < source_seat.lineno < pin_source.lineno < min(node.lineno for node in detail_creations)
    assert tuple(ast.unparse(arg) for arg in source_note.args) == ("adapter", "'Manufacturing Notes'", "NOTES_LEFT", "NOTES_CEILING")
    assert tuple(ast.unparse(arg) for arg in pin_source.args) == ("adapter", "notes")
    probes = [node for node in calls if node.func.id == "_record_detail_caption"]
    seats = [node for node in calls if node.func.id == "_seat_detail_caption"]
    assert tuple(ast.unparse(arg) for arg in normalize.args) == ("adapter", "front", "hub", "end", "caption_font_source")
    assert letters.lineno < normalize.lineno < min(node.lineno for node in probes)
    assert max(node.lineno for node in probes) < min(node.lineno for node in seats)
    seat = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_seat_detail_caption")
    assert "note.PropertyLinkedText != linked" in ast.unparse(seat)
    assert drawing.END_CENTER[1] == 0.110
    assert drawing._DETAIL_CAPTION_TARGET_AIR_M == 0.004
    assert "crop[1] - 0.003" in ast.unparse(seat)
    assert "lower_boundary + 0.003" in ast.unparse(seat)
    source_creation_guard = next(
        node for node in ast.walk(build) if isinstance(node, ast.Try)
        and any(call is source_note for call in ast.walk(node))
    )
    assert "_capture_caption_failure(adapter, 'styles', exc)" in ast.unparse(source_creation_guard)
    source_pin = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_pin_detail_caption_font_source")
    assert "_capture_caption_failure(adapter, 'styles', exc)" in ast.unparse(source_pin)
    caption_check = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_require_detail_caption_style")
    assert "SetTextFormat" not in ast.unparse(caption_check)
    import _drawing_notes
    assert not hasattr(_drawing_notes, "set_note_text_height")


def test_native_document_font_regeneration_may_merge_runs_without_detaching_fields(native_caption_style):
    case = native_caption_style
    for note in case.notes.values():
        def merge(note=note):
            text = "".join(fragment["t"] for fragment in note.data.texts)
            note.data.texts[:] = [{"t": text, "h": note.font_height, "font": "Century Gothic", "pos": [0.30, 0.07, 0.0]}]
        case.circles[note.label].on_write = merge
    _normalize_style(case)
    assert all(len(note.data.texts) == 1 for note in case.notes.values())
    assert all(drawing._caption_fields(note, label=label) == drawing._CAPTION_FIELDS
               for label, note in case.notes.items())


@pytest.mark.parametrize("label", ["D", "E"])
def test_dropped_fields_during_rebuild_are_fatal_before_seat_close(native_caption_style, monkeypatch, label):
    case = native_caption_style
    note = case.notes[label]
    def rebuild(_adapter, *, label: str):
        if label == f"normalize detail {note.label} source-circle font":
            note._linked = note._linked.replace("<VLSCALEV>", "")
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    with pytest.raises(RuntimeError, match="field identities/order/counts") as caught:
        _normalize_style(case)
    assert case.captures == [caught.value]


@pytest.mark.parametrize("label", ["D", "E"])
def test_source_height_normalization_then_quantized_native_caption_seating_keeps_air(native_caption_style, monkeypatch, label):
    case = native_caption_style
    _normalize_style(case)
    note = case.notes[label]
    pixel = 0.06535530434782608 - 0.06487873578595318
    original_extent = note.GetExtent
    def quantized_extent():
        values = list(original_extent())
        for index in (0, 1, 3, 4):
            values[index] = round(values[index] / pixel) * pixel
        return tuple(values)
    note.GetExtent = quantized_extent
    crop = (0.14, 0.070, 0.22, 0.150) if label == "D" else (0.29, 0.084, 0.37, 0.164)
    monkeypatch.setattr(drawing, "_detail_crop", lambda *_args, **_kwargs: crop)
    sheet = _native_sheet()
    sheet.GetZoneMargin = lambda _index: BORDER_BOTTOM
    linked = note.PropertyLinkedText
    drawing._seat_detail_caption(case.adapter, case.views[label], sheet, label=label)
    box = drawing._note_extent(case.adapter, note)
    assert note.PropertyLinkedText == linked
    assert crop[1] - box[3] >= 0.003
    assert box[1] - (BORDER_BOTTOM if label == "D" else 0.066) >= 0.003
    assert case.views["E"].Position[1] == 0.110
    assert case.captures == []


_POST_CAPTION_PHASES = (
    "rebuild", "dimension census", "tip land location", "REAM clearance", "front-detail air",
    "radius exterior", "arc profile clearance",
    "R24 detail layout", "R24 DOT state", "R24 DOT route",
    "shared layout", "finalize",
)


@pytest.fixture
def post_caption_block():
    """Execute only the real final build guard, without native build setup."""
    import asyncio
    import contextlib

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    (guard,) = [
        node for node in build.body if isinstance(node, ast.Try)
        and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and call.func.id == "finalize_drawing" for call in ast.walk(node))
    ]
    capture = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_capture_layout_failure")
    function = ast.parse("async def run_post_caption():\n    pass\n").body[0]
    function.body = [guard]
    code = compile(ast.fix_missing_locations(ast.Module(body=[capture, function], type_ignores=[])),
                   drawing.__file__, "exec")
    events, calls, captures, warnings = [], [], [], []
    original = RuntimeError("post-caption refusal")
    secondary = OSError("forensic PNG refused")
    result = {"drawing": "unchanged output"}
    state = SimpleNamespace(failure_phase=None, capture_mode="success", seat_open=True)
    namespace = {
        name: object() for name in (
            "adapter", "front", "hub", "end", "right", "iso", "notes_box", "arc_profiles",
            "FRONT_KEEP", "HUB_KEEP", "END_KEEP", "RIGHT_KEEP", "OUTPUTS", "SHEET_SCALE",
            "taper_dimension", "taper_entities", "rod_land", "rod_tip_attached",
            "land_dimension", "land_entities",
            "rod_position_gtol", "rod_hole_edge", "rod_position_landing", "rod_position_signature",
        )
    }
    namespace.update(contextlib=contextlib, PART_STEM="ch-rocker-arm",
                     SPEC=SimpleNamespace(layout=object()))

    def step(phase):
        def call(*args, **kwargs):
            assert state.seat_open
            events.append(phase)
            calls.append((args, kwargs))
            if state.failure_phase == phase:
                raise original
        return call

    for name, phase in zip((
        "rebuild_drawing", "_require_dimension_census", "_require_land_location", "_require_ream_clearance",
        "_require_front_detail_air", "_require_radius_exterior",
        "_require_arc_profile_clearance", "_require_r24_detail_layout",
        "_require_rod_position_dot", "_require_rod_dot_route",
        "check_drawing_layout",
    ), _POST_CAPTION_PHASES[:-1], strict=True):
        namespace[name] = step(phase)

    async def finalize(*args, **kwargs):
        step("finalize")(*args, **kwargs)
        return result

    def capture(adapter, label, message, **context):
        assert state.seat_open
        assert adapter is namespace["adapter"]
        events.append("capture")
        captures.append((label, message, context))
        if state.capture_mode == "rethrow original":
            raise original
        if state.capture_mode in ("different error", "telemetry error"):
            raise secondary

    def warn(message):
        assert state.seat_open
        warnings.append(message)
        if state.capture_mode == "telemetry error":
            raise RuntimeError("telemetry refused")

    namespace.update(finalize_drawing=finalize,
                     _seat_forensics=SimpleNamespace(capture_com_failure=capture),
                     _telemetry=SimpleNamespace(warn=warn))
    exec(code, namespace)

    def run():
        try:
            return asyncio.run(namespace["run_post_caption"]())
        finally:
            state.seat_open = False
            events.append("seat-close")

    return SimpleNamespace(run=run, state=state, events=events, calls=calls,
                           captures=captures, warnings=warnings, original=original,
                           secondary=secondary, result=result, namespace=namespace)


@pytest.mark.parametrize("phase", _POST_CAPTION_PHASES)
@pytest.mark.parametrize("capture_mode", [
    "success", "rethrow original", "different error", "telemetry error",
])
def test_post_caption_refusals_capture_before_seat_close_and_preserve_identity(post_caption_block, phase, capture_mode):
    case = post_caption_block
    case.state.failure_phase = phase
    case.state.capture_mode = capture_mode
    with pytest.raises(RuntimeError) as caught:
        case.run()
    assert caught.value is case.original
    assert case.events == [*_POST_CAPTION_PHASES[:_POST_CAPTION_PHASES.index(phase) + 1],
                           "capture", "seat-close"]
    assert len(case.calls) == _POST_CAPTION_PHASES.index(phase) + 1
    # Distinct injectable steps retain the production detail/radius forensic phases.
    reported_phase = "R24 native detail routes" if phase.startswith("R24 ") else phase
    assert case.captures == [(
        "ch-rocker-arm-post-caption-finalize", str(case.original),
        {"api": "rocker post-caption audit/finalize", "exception": case.original,
         "sheet_png": True, "phase": reported_phase},
    )]
    if capture_mode in ("different error", "telemetry error"):
        assert len(case.warnings) == 1
        assert repr(case.secondary) in case.warnings[0]
        assert f"phase={reported_phase}" in case.warnings[0]
    else:
        assert case.warnings == []


def test_post_caption_success_keeps_order_arguments_result_and_skips_capture(post_caption_block):
    case = post_caption_block
    assert case.run() is case.result
    assert case.events == [*_POST_CAPTION_PHASES, "seat-close"]
    assert case.captures == []
    assert case.warnings == []
    ns = case.namespace
    adapter = ns["adapter"]
    assert case.calls == [
        ((adapter,), {"label": "rocker-arm layout audit"}),
        ((adapter, (
            ("front", ns["front"], ns["FRONT_KEEP"]),
            ("detail D", ns["hub"], ns["HUB_KEEP"]),
            ("detail E", ns["end"], ns["END_KEEP"]),
            ("right", ns["right"], ns["RIGHT_KEEP"]),
            ("iso", ns["iso"], {}),
        )), {}),
        ((adapter, (
            ("front", ns["front"]), ("detail D", ns["hub"]), ("detail E", ns["end"]),
            ("right", ns["right"]), ("iso", ns["iso"]),
        ), ns["land_dimension"], ns["land_entities"]), {}),
        ((adapter, ns["hub"], ns["notes_box"]), {}),
        ((adapter, ns["front"], ns["hub"], ns["end"]), {}),
        ((adapter, ns["front"]), {}),
        ((adapter, ns["front"], ns["arc_profiles"]), {}),
        ((adapter, ns["end"], ns["right"], ns["taper_dimension"], ns["taper_entities"],
          ns["rod_land"], ns["rod_tip_attached"]), {}),
        ((adapter, ns["rod_position_gtol"], ns["rod_hole_edge"],
          ns["rod_position_landing"], ns["rod_position_signature"]), {}),
        ((adapter, ns["end"], ns["rod_position_gtol"], ns["rod_position_landing"]), {}),
        ((adapter,), {"layout": ns["SPEC"].layout, "stem": ns["PART_STEM"]}),
        ((adapter, ns["OUTPUTS"]), {
            "pdf_title": "Rocker Arm Manufacturing Drawing",
            "scale": ns["SHEET_SCALE"], "layout": ns["SPEC"].layout,
        }),
    ]


@pytest.fixture
def early_r24_block():
    """Execute the real pre-caption R24 guards and existing phase capture."""
    import asyncio
    import contextlib

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    capture = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_capture_layout_failure")
    guards = {
        key: next(node for node in build.body if isinstance(node, ast.Try)
                  and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                          and call.func.id == member for call in ast.walk(node)))
        for key, member in (
            ("detail", "_require_rod_tip_endpoints"),
            ("dot", "_configure_rod_position_dot"),
        )
    }
    events, captures, warnings = [], [], []
    state = SimpleNamespace(failure_step=None, capture_mode="success", seat_open=True)
    original = RuntimeError("early R24 native refusal")
    secondary = OSError("native drawing/PNG capture refused")
    tip, land, attached = object(), object(), (object(), object())
    namespace = {
        "contextlib": contextlib, "PART_STEM": "ch-rocker-arm",
        "adapter": object(), "end": object(), "END_KEEP": drawing.END_KEEP,
        "DRAWING_DIMENSIONS": drawing.DRAWING_DIMENSIONS,
        "_TIP_FACE_MID_X": drawing._TIP_FACE_MID_X,
        "_TIP_FACE_MID_Y": drawing._TIP_FACE_MID_Y,
        "ARM_THICKNESS": drawing.ARM_THICKNESS,
        "rod_position_gtol": object(), "rod_hole_edge": object(),
        "rod_position_landing": object(),
        "dimension_name": lambda adapter, annotation: "RodTipLen",
    }

    def step(name, result):
        def call(*args, **kwargs):
            assert state.seat_open
            events.append(name)
            if state.failure_step == name:
                raise original
            return result
        return call

    namespace.update(
        curate_view_dimensions=step("import", [tip]),
        _dress_detail_dimensions=step("dress", None),
        scan_view_edges=lambda *_args, **_kwargs: SimpleNamespace(
            exact_line_through=step("land", land)),
        _require_rod_tip_endpoints=step("witnesses", attached),
        _configure_rod_position_dot=step("dot", object()),
    )

    def capture_native(adapter, label, message, **context):
        assert state.seat_open
        assert adapter is namespace["adapter"]
        events.append("capture")
        captures.append((label, message, context))
        if state.capture_mode == "rethrow original":
            raise original
        if state.capture_mode in ("different error", "telemetry error"):
            raise secondary

    def warn(message):
        warnings.append(message)
        if state.capture_mode == "telemetry error":
            raise RuntimeError("telemetry refused")

    namespace.update(
        _seat_forensics=SimpleNamespace(capture_com_failure=capture_native),
        _telemetry=SimpleNamespace(warn=warn),
    )

    def run(block):
        function = ast.parse("async def run_early():\n    pass\n").body[0]
        # Expose the real production assignment, not a fabricated expected tuple.
        function.body = [ast.Global(names=["rod_tip_attached"]), guards[block]]
        code = compile(ast.fix_missing_locations(ast.Module(body=[capture, function], type_ignores=[])),
                       drawing.__file__, "exec")
        exec(code, namespace)
        try:
            asyncio.run(namespace["run_early"]())
        finally:
            state.seat_open = False
            events.append("seat-close")

    return SimpleNamespace(run=run, state=state, events=events, captures=captures,
                           warnings=warnings, original=original, secondary=secondary,
                           namespace=namespace, attached=attached)


@pytest.mark.parametrize("step,phase", [
    ("import", "R24 detail E dimension import"),
    ("dress", "R24 detail E dimension import"),
    ("land", "R24 native 5.59 witnesses"),
    ("witnesses", "R24 native 5.59 witnesses"),
    ("dot", "R24 native DOT configuration"),
])
@pytest.mark.parametrize("capture_mode", [
    "success", "rethrow original", "different error", "telemetry error",
])
def test_early_r24_native_refusals_capture_actual_drawing_and_png_before_close(
    early_r24_block, step, phase, capture_mode,
):
    case = early_r24_block
    case.state.failure_step, case.state.capture_mode = step, capture_mode
    with pytest.raises(RuntimeError) as caught:
        case.run("dot" if step == "dot" else "detail")
    assert caught.value is case.original
    assert case.events[-2:] == ["capture", "seat-close"]
    assert case.captures == [(
        "ch-rocker-arm-post-caption-finalize", str(case.original),
        {"api": "rocker post-caption audit/finalize", "exception": case.original,
         "sheet_png": True, "phase": phase},
    )]
    if capture_mode in ("different error", "telemetry error"):
        assert len(case.warnings) == 1
        assert repr(case.secondary) in case.warnings[0]
    else:
        assert case.warnings == []


@pytest.mark.parametrize("block", ["detail", "dot"])
def test_early_r24_native_success_keeps_attachment_snapshot_and_skips_capture(early_r24_block, block):
    case = early_r24_block
    case.run(block)
    assert case.captures == []
    assert case.events == (["dot", "seat-close"] if block == "dot" else
                           ["import", "dress", "land", "witnesses", "seat-close"])
    if block == "detail":
        assert case.namespace["rod_tip_attached"] is case.attached


@pytest.mark.parametrize("guard", ["front-detail", "arc-profile"])
def test_downstream_clearance_guards_bind_every_native_annotation(
    native_profile_clearance, native_annotation_binding, monkeypatch, guard,
):
    case, binding = native_profile_clearance, native_annotation_binding
    case.front.GetAnnotations = lambda: [binding.raw(ann, "IAnnotation") for ann in case.annotations]
    original = drawing._dump_annotation
    reads = []
    def dump(reader, annotation):
        assert annotation in case.annotations
        reads.append(annotation)
        return original(reader, annotation)
    monkeypatch.setattr(drawing, "_dump_annotation", dump)
    if guard == "arc-profile":
        drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
    else:
        case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
        _adapter, end = _native_crop_fixture(monkeypatch, "E")
        drawing._require_front_detail_air(case.adapter, case.front, hub, end)
    assert reads == case.annotations
    assert [ann for interface, ann in binding.calls if interface == "IAnnotation"] == case.annotations


@pytest.mark.parametrize("guard", ["front-detail", "arc-profile"])
@pytest.mark.parametrize("raw", [None, (), [], False, 1, "", {}, [None]])
def test_downstream_clearance_guards_refuse_empty_or_malformed_annotation_arrays(
    native_profile_clearance, monkeypatch, guard, raw,
):
    case = native_profile_clearance
    case.front.GetAnnotations = lambda: raw
    case.front.GetAnnotationCount = lambda: len(raw) if type(raw) in (tuple, list) else len(case.annotations)
    with pytest.raises(RuntimeError):
        if guard == "arc-profile":
            drawing._require_arc_profile_clearance(case.adapter, case.front, case.profiles)
        else:
            drawing._require_front_detail_air(case.adapter, case.front, object(), object())


@pytest.mark.parametrize("skip", ["half-hidden", "hidden", "center-mark", "center-line"])
def test_front_detail_text_air_cannot_pass_with_zero_checked_boxes(
    native_profile_clearance, bound, monkeypatch, skip,
):
    case = native_profile_clearance
    case.front.GetAnnotations = lambda: [case.r816]
    case.front.GetAnnotationCount = lambda: 1
    if skip in ("half-hidden", "hidden"):
        case.r816.Visible = 2 if skip == "half-hidden" else 3
    else:
        case.r816.kind = 13 if skip == "center-mark" else 15
    case.adapter, hub = _native_crop_fixture(monkeypatch, "D")
    _adapter, end = _native_crop_fixture(monkeypatch, "E")
    with pytest.raises(RuntimeError, match="no visible native callout text was checked"):
        drawing._require_front_detail_air(case.adapter, case.front, hub, end)


def test_reference_dimension_rejects_display_dimension_as_annotation(monkeypatch):
    import _drawing_dimensions

    adapter, _imported = _imported_native_quantities(monkeypatch)
    display = _NativeQuantity("rocker overall width", 2.0 * drawing.ROD_TIP_X)
    nominal = display.model.SystemValue
    with pytest.raises(RuntimeError, match="native owner mismatch.*IAnnotation"):
        _drawing_dimensions.set_reference_dimension(
            adapter, display, label="rocker overall width",
        )
    assert display.writes == []
    assert display.model.SystemValue == nominal
    assert not hasattr(display, "GetSpecificAnnotation")
    assert not hasattr(display.GetAnnotation(), "GetAnnotation")
    assert not hasattr(display.GetAnnotation(), "SetText")


def test_overall_width_reference_follows_the_produced_bound_owner_chain(
    native_front, native_annotation_binding, monkeypatch,
):
    state, binding = native_front, native_annotation_binding
    original_create = drawing.add_edge_dimension
    produced = {}

    def create(*args, **kwargs):
        display = original_create(*args, **kwargs)
        if kwargs["label"] != "rocker overall width":
            return display
        annotation = display.GetAnnotation()
        raw_display = binding.raw(display, "IDisplayDimension")
        raw_annotation = binding.raw(annotation, "IAnnotation")
        display.GetAnnotation = lambda: raw_annotation
        annotation.GetSpecificAnnotation = lambda: raw_display
        produced.update(display=display, annotation=annotation)
        return raw_display

    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    drawing._add_rocker_outline_dimensions(state.adapter, object())
    display, annotation = produced["display"], produced["annotation"]
    assert annotation is not display
    assert binding.calls == [
        ("IDisplayDimension", display),
        ("IAnnotation", annotation),
        ("IAnnotation", annotation),  # Unchanged named-attachment measurement.
        ("IDisplayDimension", display),  # IAnnotation.GetSpecificAnnotation.
    ]
    assert display.writes == [(1, "("), (2, ")")]
    assert display.model.SystemValue == pytest.approx(2.0 * drawing.ROD_TIP_X / 1000.0)
    assert display.model.GetToleranceType() == 0
    assert state.calls[0]["entities"] == display.attached


def test_overall_width_refuses_null_annotation_before_reference_or_taper(
    native_front, monkeypatch,
):
    native_front.defect_label = "rocker overall width"
    native_front.defect = "null-annotation"
    monkeypatch.setattr(
        drawing, "set_reference_dimension",
        lambda *_args, **_kwargs: pytest.fail("NULL annotation cannot reach the reference helper"),
    )
    with pytest.raises(RuntimeError, match="rocker overall width has no native annotation"):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())
    assert [call["label"] for call in native_front.calls] == ["rocker overall width"]
    assert native_front.displays["rocker overall width"].writes == []


def test_overall_width_refuses_wrong_produced_interface_owner(native_front, monkeypatch):
    original_create = drawing.add_edge_dimension

    def create(*args, **kwargs):
        display = original_create(*args, **kwargs)
        if kwargs["label"] == "rocker overall width":
            display.GetAnnotation = lambda: display
        return display

    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    with pytest.raises(RuntimeError, match="native owner mismatch.*IAnnotation"):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())
    assert [call["label"] for call in native_front.calls] == ["rocker overall width"]
    assert native_front.displays["rocker overall width"].writes == []


@pytest.mark.parametrize("ignored_part", [1, 2])
def test_overall_width_owner_fix_retains_reference_prefix_suffix_guard(
    native_front, monkeypatch, ignored_part,
):
    original_create = drawing.add_edge_dimension

    def create(*args, **kwargs):
        display = original_create(*args, **kwargs)
        if kwargs["label"] == "rocker overall width":
            display.ignored_text = ignored_part
        return display

    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    with pytest.raises(RuntimeError, match="failed to parenthesize rocker overall width"):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())
    display = native_front.displays["rocker overall width"]
    assert display.writes == [(1, "("), (2, ")")]
    assert display.model.SystemValue == pytest.approx(2.0 * drawing.ROD_TIP_X / 1000.0)
    assert [call["label"] for call in native_front.calls] == ["rocker overall width"]


@pytest.mark.parametrize("factory", [
    pytest.param(lambda: _ProfileDisplay(), id="profile-display"),
    pytest.param(lambda: _ClearanceDisplayData([], []), id="clearance-display-data"),
    pytest.param(lambda: _ClearanceAnnotation("frame", (0, 0, 0), None), id="clearance-annotation"),
    pytest.param(lambda: _Tag(()), id="datum-tag"),
    pytest.param(lambda: _FakeAnnotation((0, 0)), id="note-annotation"),
    pytest.param(lambda: _FakeNote((0, 0), 0.01), id="ordinary-note"),
    pytest.param(lambda: _NativeQuantity("span", 1), id="native-dimension-display"),
    pytest.param(lambda: _NativeQuantity("span", 1).GetAnnotation(), id="native-dimension-annotation"),
    pytest.param(lambda: _NativeQuantity("span", 1).GetDimension2(0), id="native-model-dimension"),
    pytest.param(lambda: _NativeQuantity("span", 1).model.Tolerance, id="native-dimension-tolerance"),
    pytest.param(lambda: _DetailCircle("D"), id="detail-circle"),
    pytest.param(lambda: _DetailTransform(), id="detail-transform"),
    pytest.param(lambda: _DetailParent(), id="detail-parent-view"),
    pytest.param(lambda: _DetailView(_DetailParent()), id="detail-view"),
    pytest.param(lambda: _DetailCropCircle("D", None), id="detail-crop-circle"),
    pytest.param(lambda: _CensusAnnotation("size"), id="census-annotation"),
    pytest.param(lambda: _CensusDisplayDimension(None), id="census-display"),
    pytest.param(lambda: _RenderedRodCallout(("THRU",)), id="hole-callout-display"),
    pytest.param(lambda: _RenderedRodText(("THRU",)), id="hole-callout-display-data"),
    pytest.param(lambda: _CaptionTextFormat(), id="caption-text-format"),
    pytest.param(lambda: _CaptionNote("D"), id="caption-note"),
    pytest.param(lambda: _StyleNote("D"), id="rich-caption-note"),
    pytest.param(lambda: _StyleNote("D").GetAnnotation(), id="rich-caption-annotation"),
    pytest.param(lambda: _StyleNote("D").data, id="rich-caption-display-data"),
    pytest.param(lambda: _StyleTextFormat(), id="rich-caption-text-format"),
    pytest.param(lambda: _StyleDocExtension({}, {}), id="document-font-extension"),
    pytest.param(lambda: _StyleCircle("D", _native("IView"), _native("IView")), id="styled-detail-circle"),
    pytest.param(lambda: _native_sheet(), id="sheet"),
    pytest.param(lambda: _DetailParent().GetSketch(), id="detail-sketch"),
    pytest.param(lambda: _DetailProfile((0, 0, 0), 1, None), id="detail-segment-arc-qi"),
    pytest.param(lambda: _native("ISketchPoint", X=0, Y=0, Z=0), id="sketch-point"),
    pytest.param(lambda: _DetailMathPoint(drawing.double_array([0.0, 0.0, 0.0])), id="math-point"),
    pytest.param(lambda: _native("IMathUtility", CreatePoint=_DetailMathPoint), id="math-utility"),
    pytest.param(lambda: _native("ISketchManager", AddToDB=False), id="sketch-manager"),
    pytest.param(lambda: _native("ISelectionMgr", CreateSelectData=lambda: _native("ISelectData")), id="selection-manager"),
    pytest.param(lambda: _native("ISelectData"), id="select-data"),
    pytest.param(lambda: _native("IEntity", Select4=lambda *_args: True), id="selected-entity"),
    pytest.param(lambda: _native("IModelDoc2", "IDrawingDoc"), id="drawing-document-qi"),
    pytest.param(lambda: _APP, id="application"),
])
def test_rocker_local_native_families_refuse_every_wrong_interface(factory):
    native = factory()
    interfaces = (
        "IAnnotation", "IDisplayDimension", "IDimension", "IDimensionTolerance",
        "INote", "IDisplayData", "ITextFormat", "IDetailCircle", "IDatumTag",
        "IView", "ISheet", "ISketch", "ISketchSegment", "ISketchArc",
        "ISketchPoint", "IMathTransform", "IMathPoint", "IMathUtility",
        "ISketchManager", "ISelectionMgr", "ISelectData", "IEntity",
        "IModelDoc2", "IDrawingDoc", "IModelDocExtension", "ISldWorks",
    )
    for interface in interfaces:
        if interface in native._native_interfaces:
            assert interface in _bind_owner(native, interface)._native_interfaces
        else:
            with pytest.raises(RuntimeError, match="native owner mismatch"):
                _bind_owner(native, interface)


def test_native_owner_registry_refuses_unknown_or_forged_owner(native_annotation_binding):
    binding = native_annotation_binding
    with pytest.raises(RuntimeError, match="native owner mismatch"):
        binding.bind(object(), "IView")
    display = _NativeQuantity("span", 1)
    with pytest.raises(RuntimeError, match="native owner mismatch.*IAnnotation"):
        binding.raw(display, "IAnnotation")
    raw = binding.raw(display, "IDisplayDimension")
    with pytest.raises(AssertionError):
        binding.bind(raw, "IAnnotation")
    assert binding.bind(None, "IAnnotation") is None
    assert binding.calls == []


def test_detail_circle_qi_exposes_separate_segment_and_arc_member_slices():
    profile = _DetailProfile((0, 0, 0), 0.01, _DetailParent().GetSketch())
    segment = _bind_owner(profile, "ISketchSegment")
    arc = _bind_owner(profile, "ISketchArc")
    assert segment is profile and arc.segment is profile
    assert segment.GetType() == 1 and arc.IsCircle() == 1
    assert arc.GetRadius() == 0.01
    assert not hasattr(segment, "IsCircle")
    assert not hasattr(segment, "GetCenterPoint2")
    assert not hasattr(arc, "GetType")
    assert not hasattr(arc, "Select4")


@pytest.mark.parametrize("stage", ["source-note", "annotation", "display-data", "text-format", "document-extension"])
def test_rocker_source_font_helpers_refuse_wrong_interface_owners(native_caption_style, stage):
    case = native_caption_style
    if stage == "source-note":
        case.source = case.source.annotation
    elif stage == "annotation":
        case.source.GetAnnotation = lambda: case.source
    elif stage == "display-data":
        case.source.data = case.source.text_format
    elif stage == "text-format":
        case.source.text_format = case.source.data
    else:
        case.adapter.currentModel.Extension = case.source.annotation
    with pytest.raises(RuntimeError, match="native owner mismatch") as caught:
        drawing._pin_detail_caption_font_source(case.adapter, case.source)
    assert case.captures == [caught.value]
    assert case.extension.writes == []


@pytest.mark.parametrize("stage", ["caption-view", "caption-note", "source-circle", "circle-text-format"])
def test_rocker_style_normalization_refuses_wrong_interface_owners(native_caption_style, stage):
    case = native_caption_style
    font_source = drawing._pin_detail_caption_font_source(case.adapter, case.source)
    case.extension.create_details()
    if stage == "caption-view":
        case.views["D"] = case.notes["D"]
    elif stage == "caption-note":
        case.views["D"].GetNotes = lambda: [case.notes["D"].annotation]
    elif stage == "source-circle":
        case.front.GetDetailCircles = lambda: [case.notes["D"], case.circles["E"]]
    else:
        case.circles["D"].GetTextFormat = lambda: case.notes["D"].data
    with pytest.raises(RuntimeError, match="native owner mismatch") as caught:
        drawing._normalize_detail_caption_styles(
            case.adapter, case.front, case.views["D"], case.views["E"], font_source,
        )
    assert case.captures == [caught.value]


@pytest.mark.parametrize("helper", ["projection", "outline", "scale", "detail-crop", "bound-annotations", "through-callout"])
def test_rocker_local_readers_refuse_wrong_owner_before_member_access(bound, helper):
    wrong = _FakeNote((0, 0), 0.01)
    readers = {
        "projection": lambda: drawing._project(object(), wrong, [], label="wrong-owner"),
        "outline": lambda: drawing._outline(wrong, label="wrong-owner"),
        "scale": lambda: drawing._view_scale_ratio(wrong, label="wrong-owner"),
        "detail-crop": lambda: drawing._detail_crop(object(), wrong, label="D"),
        "bound-annotations": lambda: drawing._bound_view_annotations(wrong, label="wrong-owner"),
        "through-callout": lambda: drawing._require_rod_through_callout(wrong),
    }
    with pytest.raises(RuntimeError, match="native owner mismatch"):
        readers[helper]()


def test_native_fixture_cannot_declare_annotation_and_display_as_one_object():
    with pytest.raises(AssertionError, match="require distinct objects"):
        _native("IAnnotation", "IDisplayDimension")


class _AuthoredGdtAnnotation(_FakeAnnotation):
    """Native IAnnotation only; its producer owns tag/frame-specific methods."""

    def __init__(self, entity, data, *, leaders):
        super().__init__((0.0, 0.0))
        self.entity, self.data = entity, data
        self.leaders, self.dangling = leaders, False
        self.landing = (0.0, 0.0)
        self.leader_writes = []

    def SetPosition2(self, x, y, z):
        assert z == 0.0
        return self.SetPosition(x, y, z)

    def GetAttachedEntities3(self):
        return (self.entity,)

    def GetAttachedEntityCount3(self):
        return 1

    def GetAttachedEntityTypes(self):
        return (1,)  # swSelEDGES.

    def GetLeaderCount(self):
        return self.leaders

    def IsDangling(self):
        return self.dangling

    def GetDisplayData(self):
        return self.data

    def SetLeader3(self, *args):
        self.leader_writes.append(args)
        return 0  # Native integer status.

    def GetLeaderPointsAtIndex(self, index):
        assert index == 0
        return (*self.position, 0.0, *self.landing, 0.0)


class _AuthoredDatumTag:
    _native_interfaces = ("IDatumTag",)

    def __init__(self, annotation):
        self.annotation, self.label = annotation, ""
        self.Shoulder = self.ForcedShoulder = False

    def SetLabel(self, label):
        self.label = label
        return True

    def GetLabel(self):
        return self.label

    def GetAnnotation(self):
        return self.annotation


class _AuthoredGtolFrame:
    """Only IGtolFrame may read/write the XML payload."""

    _native_interfaces = ("IGtolFrame",)

    def __init__(self, events):
        self.xml = ""
        self.events, self.writes = events, []
        self.result = True
        self.on_write = lambda xml: xml

    def SetSymbolXml(self, xml):
        self.events.append("SetSymbolXml")
        self.writes.append(xml)
        if self.result is True:
            self.xml = self.on_write(xml)
        return self.result

    def GetSymbolXml(self):
        self.events.append("GetSymbolXml")
        return self.xml


class _AuthoredGtol:
    """Only IGtol may produce a frame; legacy migration retains native shapes."""

    _native_interfaces = ("IGtol",)

    def __init__(self, frame, annotation, events):
        self.frame, self.annotation, self.events = frame, annotation, events
        self.count, self.format = 0, 2
        self.add_result = True
        self.seed_symbols, self.seed_values = [], []

    def GetFrameCount(self):
        return self.count

    def AddFrame(self):
        self.events.append("AddFrame")
        if self.add_result is True:
            self.count += 1
        return self.add_result

    def GetFrame(self, index):
        assert index == 1
        self.events.append("GetFrame")
        return self.frame if self.format == 2 and self.count == 1 else None

    def GetFormat(self):
        return self.format

    def SetFrameSymbols2(self, *args):
        self.seed_symbols.append(args)
        return None  # Native VT_VOID.

    def SetFrameValues2(self, *args):
        self.seed_values.append(args)
        return True

    def CanConvertFormat(self):
        return True

    def ConvertFormat(self):
        assert self.count == 1 and self.seed_symbols and self.seed_values
        self.events.append("ConvertFormat")
        self.format = 2
        return 0  # Native conversion status.

    def GetAnnotation(self):
        return self.annotation


@pytest.fixture
def actual_rocker_gdt(native_annotation_binding, monkeypatch):
    """Execute actual selection, insertion, attachment, landing and XML helpers."""
    import _drawing_attachment
    import _drawing_gdt
    import _drawing_selection

    binding = native_annotation_binding
    for module in (_drawing_attachment, _drawing_gdt, _drawing_selection):
        monkeypatch.setattr(module, "_early_bound", binding.bind)

    events, selected = [], []
    view = _native("IView", GetName2=lambda: "rocker front")
    landing = (0.210, 0.167)
    data = _ClearanceDisplayData([], [], primitives={
        "arrows": [[*landing, 0.0, -1, 0, 0, 0.003, 0.003, 0, 0, 0, 1]],
    })
    state = SimpleNamespace(
        events=events, selected=selected, landing=landing, selection_result=True,
        on_rebuild=lambda: None,
    )

    def select(append, select_data):
        assert append is False and select_data.View is view
        selected[:] = [entity]
        events.append("Select4")
        return True

    entity = _native("IEntity", Select4=select)
    datum_annotation = _AuthoredGdtAnnotation(
        entity, binding.raw(data, "IDisplayData"), leaders=0,
    )
    frame_annotation = _AuthoredGdtAnnotation(entity, None, leaders=1)
    datum = _AuthoredDatumTag(binding.raw(datum_annotation, "IAnnotation"))
    frame = _AuthoredGtolFrame(events)
    gtol = _AuthoredGtol(
        binding.raw(frame, "IGtolFrame"),
        binding.raw(frame_annotation, "IAnnotation"), events,
    )
    state.datum_result = binding.raw(datum, "IDatumTag")
    state.gtol_result = binding.raw(gtol, "IGtol")

    def set_landing(index, mark, x, y, z):
        assert (index, mark, z) == (1, -1, 0.0)
        assert selected == [entity]
        events.append(("SetSelectionPoint2", x, y))
        if state.selection_result is True:
            datum_annotation.landing = frame_annotation.landing = (x, y)
            data.primitives["arrows"][0][:2] = [x, y]
        return state.selection_result

    manager = _native(
        "ISelectionMgr",
        CreateSelectData=lambda: _native("ISelectData"),
        GetSelectedObjectCount2=lambda _mark: len(selected),
        GetSelectedObject6=lambda index, mark: selected[index - 1],
        SetSelectionPoint2=set_landing,
    )

    def coordinate_select(name, kind, x, y, z, append, mark, callout, option):
        assert (name, kind, z, append, mark, option) == ("", "EDGE", 0.0, False, 0, 0)
        selected[:] = [entity]
        events.append("SelectByID2")
        return True

    extension = _native("IModelDocExtension", SelectByID2=coordinate_select)

    def insert(kind):
        events.append("InsertDatumTag2" if kind == "datum" else "InsertGtol")
        assert selected == [entity]
        return state.datum_result if kind == "datum" else state.gtol_result

    doc = _native(
        "IModelDoc2", "IDrawingDoc",
        SelectionManager=manager, Extension=extension,
        ActivateView=lambda name: name == "rocker front",
        ClearSelection2=lambda _all: selected.clear(),
        InsertDatumTag2=lambda: insert("datum"),
        InsertGtol=lambda: insert("frame"),
    )
    view.UpdateViewDisplayGeometry = lambda: events.append("UpdateViewDisplayGeometry")
    adapter = SimpleNamespace(
        currentModel=doc, swApp=_APP,
        _get_attr_or_call=lambda native, member: getattr(_bind_owner(native, "IView"), member)(),
    )

    def rebuild(_adapter, *, label):
        assert _adapter is adapter
        events.append(("rebuild", label))
        state.on_rebuild()

    monkeypatch.setattr(_drawing_gdt, "rebuild_drawing", rebuild)
    state.adapter, state.view, state.entity = adapter, view, entity
    state.datum, state.datum_annotation, state.data = datum, datum_annotation, data
    state.gtol, state.frame, state.frame_annotation = gtol, frame, frame_annotation
    state.manager, state.extension, state.doc, state.binding = manager, extension, doc, binding
    return state


def _author_actual_rocker_gdt(case, kind, *, coordinate=False, arc="TopRadius"):
    import _drawing_gdt

    pick = (
        {"edge_xy": case.landing, "expected_entity": case.entity}
        if coordinate and kind == "datum"
        else {"edge_xy": case.landing}
        if coordinate
        else {"edge_entity": case.entity}
    )
    if kind == "datum":
        return _drawing_gdt.add_datum_feature(
            case.adapter, case.view, **pick,
            symbol_xy=(0.225, 0.180), datum="C", label="+Z rod-side radial land",
            leader_attach_xy=case.landing,
        )
    return _drawing_gdt.add_feature_control_frame(
        case.adapter, case.view, **pick,
        frame_xy=drawing.ARC_PROFILE_FRAME_XY[arc], characteristic="profile_surface",
        tolerance=drawing.ARC_PROFILE_ZONE_TEXT,
        outside_disposition=drawing.ARC_PROFILE_OUTSIDE_TEXT[arc],
        datums=("A", "B", "C"), leader_attach_xy=case.landing,
        label=f"arc-system {arc} profile",
    )


@pytest.mark.parametrize("coordinate", [False, True])
def test_actual_datum_helper_retains_selected_land_and_rendered_triangle(actual_rocker_gdt, coordinate):
    import _drawing_gdt

    case = actual_rocker_gdt
    assert _author_actual_rocker_gdt(case, "datum", coordinate=coordinate) is case.datum
    assert case.datum.GetLabel() == "C"
    assert case.datum_annotation.GetPosition() == (0.225, 0.180, 0.0)
    assert _drawing_gdt.assert_datum_landing(
        case.adapter, case.datum, expected_xy=case.landing, label="strict datum C",
    ) == case.landing
    assert ("SetSelectionPoint2", *case.landing) in case.events
    assert case.events.index(("SetSelectionPoint2", *case.landing)) < case.events.index("InsertDatumTag2")
    assert ("IDatumTag", case.datum) in case.binding.calls
    assert ("IAnnotation", case.datum_annotation) in case.binding.calls
    assert ("IDisplayData", case.data) in case.binding.calls
    assert case.datum_annotation.GetLeaderCount() == 0
    assert case.datum_annotation.GetAttachedEntities3() == (case.entity,)


@pytest.mark.parametrize("stage", [
    "drawing-document", "selection-manager", "datum-tag", "annotation", "display-data", "selection-extension",
])
def test_actual_datum_helper_refuses_wrong_produced_interface(actual_rocker_gdt, stage):
    case = actual_rocker_gdt
    if stage == "drawing-document":
        case.adapter.currentModel = case.datum_annotation
    elif stage == "selection-manager":
        case.doc.SelectionManager = case.datum_annotation
    elif stage == "datum-tag":
        case.datum_result = case.frame
    elif stage == "annotation":
        case.datum.annotation = case.datum
    elif stage == "display-data":
        case.datum_annotation.data = case.frame
    else:
        case.doc.Extension = case.datum_annotation
    with pytest.raises((RuntimeError, AttributeError)):
        _author_actual_rocker_gdt(case, "datum", coordinate=stage == "selection-extension")


@pytest.mark.parametrize("defect", ["dangling", "missing-data", "moved-tip", "no-tip", "nonfinite-tip"])
def test_actual_datum_landing_refuses_unreadable_or_moved_triangle(actual_rocker_gdt, defect):
    import _drawing_gdt

    case = actual_rocker_gdt
    _author_actual_rocker_gdt(case, "datum")
    if defect == "dangling":
        case.datum_annotation.dangling = True
    elif defect == "missing-data":
        case.datum_annotation.data = None
    elif defect == "moved-tip":
        case.data.primitives["arrows"][0][0] += 0.000051
    elif defect == "no-tip":
        case.data.primitives.clear()
    else:
        case.data.primitives["arrows"][0][0] = float("nan")
    with pytest.raises(RuntimeError, match="datum landing"):
        _drawing_gdt.assert_datum_landing(
            case.adapter, case.datum, expected_xy=case.landing, label="strict datum C",
        )


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("coordinate", [False, True])
def test_actual_profile_frame_helper_preserves_unequal_xml_on_frame_owner(
    actual_rocker_gdt, legacy, coordinate,
):
    from _gtol_frame import gtol_frame_signature

    case = actual_rocker_gdt
    case.gtol.format = 1 if legacy else 2
    case.gtol.count = 1 if legacy else 0
    arc = "TopRadius"  # The drawing's one profile frame.
    assert _author_actual_rocker_gdt(case, "frame", arc=arc, coordinate=coordinate) is case.gtol
    signature = gtol_frame_signature(case.frame.GetSymbolXml())
    assert signature.tolerance == "0.02"
    assert signature.outside_disposition == "0.02"
    assert signature.datums == ("A", "B", "C")
    assert signature.tolerance_zone == "linear"
    assert len(case.frame.writes) == 1
    if legacy:
        assert "AddFrame" not in case.events  # AddFrame is current-format only.
        assert case.events.index("ConvertFormat") < case.events.index("SetSymbolXml")
    else:
        assert case.events.index("AddFrame") < case.events.index("SetSymbolXml")
    assert case.events.index(("SetSelectionPoint2", *case.landing)) < case.events.index("InsertGtol")
    assert case.gtol.GetFormat() == 2 and case.gtol.GetFrameCount() == 1
    assert bool(case.gtol.seed_symbols) is legacy
    assert bool(case.gtol.seed_values) is legacy
    if legacy:
        assert case.gtol.seed_values == [
            (1, drawing.ARC_PROFILE_ZONE_TEXT, "", "A", "B", "C"),
        ]
    assert ("IGtol", case.gtol) in case.binding.calls
    assert ("IGtolFrame", case.frame) in case.binding.calls
    assert ("IAnnotation", case.frame_annotation) in case.binding.calls
    assert case.frame_annotation.GetAttachedEntities3() == (case.entity,)
    assert case.frame_annotation.leader_writes == [(2, 0, True, False, False, False)]


@pytest.mark.parametrize("stage", [
    "selection-manager", "selection-extension", "gtol", "frame", "annotation",
])
def test_actual_profile_frame_helper_refuses_wrong_produced_interface(actual_rocker_gdt, stage):
    case = actual_rocker_gdt
    if stage == "selection-manager":
        case.doc.SelectionManager = case.frame_annotation
    elif stage == "selection-extension":
        case.doc.Extension = case.frame_annotation
    elif stage == "gtol":
        case.gtol_result = case.frame
    elif stage == "frame":
        case.gtol.frame = case.frame_annotation
    else:
        case.gtol.annotation = case.gtol
    with pytest.raises((RuntimeError, AttributeError)):
        _author_actual_rocker_gdt(case, "frame", coordinate=stage == "selection-extension")


@pytest.mark.parametrize("target", ["AddFrame", "SetSymbolXml"])
@pytest.mark.parametrize("result", [False, None, 1])
def test_actual_profile_frame_helper_requires_native_bool_writer_success(actual_rocker_gdt, target, result):
    case = actual_rocker_gdt
    if target == "AddFrame":
        case.gtol.add_result = result
    else:
        case.frame.result = result
    with pytest.raises(RuntimeError, match="failed to create|rejected feature-control frame XML"):
        _author_actual_rocker_gdt(case, "frame")
    assert case.frame.xml == ""


@pytest.mark.parametrize("kind", ["datum", "frame"])
@pytest.mark.parametrize("result", [False, None, 1])
def test_actual_gdt_helpers_require_true_selection_landing_before_insertion(actual_rocker_gdt, kind, result):
    case = actual_rocker_gdt
    case.selection_result = result
    with pytest.raises(RuntimeError, match="failed to set.*landing"):
        _author_actual_rocker_gdt(case, kind)
    assert "InsertDatumTag2" not in case.events and "InsertGtol" not in case.events


@pytest.mark.parametrize("defect", [
    "outside-before-rebuild", "outside-after-rebuild", "attachment", "leader-landing",
])
def test_actual_profile_frame_helper_retains_xml_attachment_and_landing_guards(actual_rocker_gdt, defect):
    from _gtol_frame import gtol_frame_xml

    case = actual_rocker_gdt
    symmetric = gtol_frame_xml("profile_surface", drawing.ARC_PROFILE_ZONE_TEXT, datums=("A", "B", "C"))
    if defect == "outside-before-rebuild":
        case.frame.on_write = lambda _xml: symmetric
    elif defect == "outside-after-rebuild":
        case.on_rebuild = lambda: setattr(case.frame, "xml", symmetric)
    elif defect == "attachment":
        case.on_rebuild = lambda: setattr(case.frame_annotation, "entity", object())
    else:
        case.on_rebuild = lambda: setattr(case.frame_annotation, "landing", (0.215, 0.167))
    with pytest.raises(RuntimeError, match="did not persist|changed semantics|lost its edge attachment|leader attachment moved"):
        _author_actual_rocker_gdt(case, "frame")


def test_actual_gdt_producers_keep_specific_frame_and_annotation_members_disjoint(actual_rocker_gdt):
    case = actual_rocker_gdt
    assert not hasattr(case.gtol, "SetSymbolXml")
    assert not hasattr(case.frame, "AddFrame")
    assert not hasattr(case.frame, "GetAnnotation")
    assert not hasattr(case.frame_annotation, "AddFrame")
    assert not hasattr(case.frame_annotation, "SetSymbolXml")
    assert not hasattr(case.datum_annotation, "SetLabel")
    for native, wrong in (
        (case.gtol, "IGtolFrame"), (case.frame, "IGtol"),
        (case.datum, "IAnnotation"), (case.datum_annotation, "IDatumTag"),
        (case.frame_annotation, "IGtolFrame"),
    ):
        with pytest.raises(RuntimeError, match="native owner mismatch"):
            case.binding.bind(native, wrong)


# R19 layout-audit replay (20261013T051541021Z-0456b55b4ef7424793cb5fdafaf10c41).
# The shared JSON rounds coordinates to 7dp. These are serialized fixtures,
# never unrounded COM evidence and never a production containment allowance.
_R19_NATIVE_MARK_CROPS = {
    "D": (0.15310000000000007, 0.0681000000000001,
          0.20689999999999992, 0.12189999999999995),
    "E": (0.30616186089949615, 0.08616186089949626,
          0.35383813910050377, 0.13383813910050388),
}
_R19_FRONT_OUTLINE = (0.1012847, 0.1620883, 0.2587153, 0.1879117)


def _r19_mark_lines(rows):
    return [[-1.0, 0.0, style, 0.0, x0, y0, 0.0, x1, y1, 0.0]
            for style, x0, y0, x1, y1 in rows]


_R19_MARK_LINES = {
    "front-pivot": _r19_mark_lines((
        (0, 0.18, 0.1716763, 0.18, 0.1729263),
        (0, 0.18, 0.1716763, 0.17875, 0.1716763),
        (0, 0.18, 0.1716763, 0.18, 0.1704263),
        (0, 0.18, 0.1716763, 0.18125, 0.1716763),
        (-1, 0.18, 0.1741763, 0.18, 0.1754763),
        (-1, 0.1775, 0.1716763, 0.1762, 0.1716763),
        (-1, 0.18, 0.1691763, 0.18, 0.1678763),
        (-1, 0.1825, 0.1716763, 0.1838, 0.1716763),
    )),
    "front-pin": _r19_mark_lines((
        (0, 0.2465337, 0.1759044, 0.2465337, 0.1771544),
        (0, 0.2465337, 0.1759044, 0.2452837, 0.1759044),
        (0, 0.2465337, 0.1759044, 0.2465337, 0.1746544),
        (0, 0.2465337, 0.1759044, 0.2477837, 0.1759044),
        (-1, 0.2465337, 0.1771544, 0.2465337, 0.1776528),
        (-1, 0.2452837, 0.1759044, 0.2447852, 0.1759044),
        (-1, 0.2465337, 0.1746544, 0.2465337, 0.1741559),
        (-1, 0.2477837, 0.1759044, 0.2482822, 0.1759044),
    )),
    "D": _r19_mark_lines((
        (0, 0.18, 0.095, 0.18, 0.105),
        (0, 0.18, 0.095, 0.17, 0.095),
        (0, 0.18, 0.095, 0.18, 0.085),
        (0, 0.18, 0.095, 0.19, 0.095),
        (-1, 0.18, 0.115, 0.18, 0.1219),
        (-1, 0.16, 0.095, 0.1531, 0.095),
        (-1, 0.18, 0.075, 0.18, 0.0681),
        (-1, 0.2, 0.095, 0.2069, 0.095),
    )),
    "E": _r19_mark_lines((
        (0, 0.317123, 0.1027457, 0.317123, 0.1077457),
        (0, 0.317123, 0.1027457, 0.312123, 0.1027457),
        (0, 0.317123, 0.1027457, 0.317123, 0.0977457),
        (0, 0.317123, 0.1027457, 0.322123, 0.1027457),
        (-1, 0.317123, 0.1077457, 0.317123, 0.1097396),
        (-1, 0.312123, 0.1027457, 0.3101291, 0.1027457),
        (-1, 0.317123, 0.0977457, 0.317123, 0.0957518),
        (-1, 0.322123, 0.1027457, 0.3241169, 0.1027457),
    )),
}
_R19_MARK_RECORDS = {
    "front": (
        ("DetailItem347", (0.1781134, 0.1699608, 0.0017641), "front-pivot"),
        ("DetailItem349", (0.2462447, 0.1754982, 0.000625), "front-pin"),
        ("DetailItem359", (0.1781134, 0.1699608, -0.0017641), "front-pivot"),
        ("DetailItem361", (0.2462447, 0.1754982, 0.000625), "front-pin"),
    ),
    "D": (
        ("DetailItem352", (0.1616543, 0.0860784, -0.014113), "D"),
        ("DetailItem354", (0.7086834, 0.1270803, 0.005), None),
        ("DetailItem362", (0.1616329, 0.0861226, 0.014113), "D"),
        ("DetailItem364", (0.7083548, 0.1280648, 0.005), None),
    ),
    "E": (
        ("DetailItem356", (0.0417128, 0.0815902, -0.0070565), None),
        ("DetailItem358", (0.3153098, 0.1019162, 0.0025), "E"),
        ("DetailItem365", (0.0453988, 0.0773014, 0.0070565), None),
        ("DetailItem367", (0.3153176, 0.1018994, 0.0025), "E"),
    ),
}


class _MarkDisplayData:
    """Closed IDisplayData surface, with explicit authoritative zero counts."""
    _native_interfaces = ("IDisplayData",)
    _primitives = {
        "lines": ("GetLineCount", ("GetLineAtIndex3", "GetLineAtIndex2")),
        "arcs": ("GetArcCount", ("GetArcAtIndex2",)),
        "arrows": ("GetArrowHeadCount", ("GetArrowHeadAtIndex2",)),
        "polylines": ("GetPolyLineCount", ("GetPolylineAtIndex2",)),
        "polygons": ("GetPolygonCount", ("GetPolygonAtIndex",)),
        "triangles": ("GetTriangleCount", ("GetTriangleAtIndex",)),
        "ellipses": ("GetEllipseCount", ("GetEllipseAtIndex2",)),
    }

    def __init__(self, display):
        self.display = display
        self.overrides, self.reads = {}, []

    def _answer(self, member, default, args):
        self.reads.append((member, args))
        value = self.overrides.get(member, default)
        if isinstance(value, Exception):
            raise value
        return value(*args) if callable(value) else value

    def __getattr__(self, member):
        for key, (count_member, getters) in self._primitives.items():
            if member == count_member:
                return lambda: self._answer(member, len(self.display.get(key, ())), ())
            if member in getters:
                return lambda index: self._answer(
                    member, lambda i: self.display.get(key, ())[i], (index,),
                )
        if member == "GetTextCount":
            return lambda: self._answer(member, len(self.display.get("texts", ())), ())
        raise AttributeError(f"IDisplayData does not own {member}")


class _MarkAnnotation:
    """IAnnotation owns the dispatch hop; it never owns display-data methods."""
    _native_interfaces = ("IAnnotation",)

    def __init__(self, name, position, data):
        self.name, self.position, self.data = name, position, data

    def GetType(self):
        return 13

    def GetName(self):
        return self.name

    def GetPosition(self):
        return self.position

    def GetDisplayData(self):
        return self.data


@pytest.fixture
def mark_census(monkeypatch, native_annotation_binding):
    """Actual census and decoders, opaque native dispatches at both owner hops."""
    binding = native_annotation_binding
    logs = []
    monkeypatch.setattr(drawing._telemetry, "info", logs.append)

    def make(records, *, crop=(0.0, 0.0, 0.1, 0.1)):
        annotations, datas, raws = [], [], []
        for name, position, display in records:
            data = _MarkDisplayData(display)
            annotation = _MarkAnnotation(name, position, binding.raw(data, "IDisplayData"))
            datas.append(data)
            annotations.append(annotation)
            raws.append(binding.raw(annotation, "IAnnotation"))
        view = _native(
            "IView", GetAnnotationCount=lambda: len(raws), GetAnnotations=lambda: tuple(raws),
            GetOutline=lambda: crop,
        )
        return SimpleNamespace(
            annotations=annotations, datas=datas, raws=raws, native_view=view,
            view=binding.raw(view, "IView"), logs=logs, binding=binding, crop=crop,
        )
    return make


def _r19_mark_census(mark_census, label, *, manual=False):
    records = _R19_MARK_RECORDS[label]
    records = records if manual else records[:2]
    crop = (_R19_FRONT_OUTLINE if label == "front"
            else tuple(round(value, 7) for value in _R19_NATIVE_MARK_CROPS[label]))
    return mark_census([
        (name, position, {} if key is None else {"lines": _R19_MARK_LINES[key]})
        for name, position, key in records
    ], crop=crop)


@pytest.mark.parametrize("label,required", [("front", 2), ("D", 1), ("E", 1)])
def test_r19_original_marks_count_printed_ink_not_all_type13_objects(mark_census, monkeypatch, label, required):
    case = _r19_mark_census(mark_census, label)
    crop_reads = []
    def crop(_adapter, view, *, label):
        assert view is case.view
        crop_reads.append(label)
        return case.crop  # Explicitly quantized replay, not a native crop substitute.
    monkeypatch.setattr(drawing, "_detail_crop", crop)
    counts = drawing._require_center_mark_census(
        object(), case.view, label=label, required=required,
        detail=None if label == "front" else label,
    )
    assert counts == {"NON_MARK": 0, "PRINTED": required, "GHOST": 2 - required, "FAIL": 0}
    assert len(case.raws) == 2
    assert sum(annotation.GetType() == 13 for annotation in case.annotations) == 2
    assert crop_reads == ([] if label == "front" else [label])
    expected_getters = {value[0] for value in _MarkDisplayData._primitives.values()} | {"GetTextCount"}
    for data in case.datas:
        assert expected_getters <= {member for member, _args in data.reads}
    assert [owner for interface, owner in case.binding.calls if interface == "IDisplayData"] == case.datas
    for annotation, data in zip(case.annotations, case.datas):
        log = next(log for log in case.logs if f"id={annotation.name!r}" in log)
        assert f"position={annotation.position!r}" in log
        assert f"line_count={len(data.display.get('lines', ()))!r}" in log
        assert f"class={'PRINTED' if data.display else 'GHOST'}" in log
    assert any(f"total_view_annotations=2, non_mark=0, printed={required}, ghost={2-required}, fail=0" in log
               for log in case.logs)


@pytest.mark.parametrize("label,required", [("front", 2), ("D", 1), ("E", 1)])
def test_r19_full_four_record_lists_do_not_ship_duplicate_printed_marks(mark_census, monkeypatch, label, required):
    case = _r19_mark_census(mark_census, label, manual=True)
    def crop(_adapter, view, *, label):
        assert view is case.view and label in ("D", "E")
        return case.crop  # Same 7dp coordinate domain as the serialized rows.
    monkeypatch.setattr(drawing, "_detail_crop", crop)
    with pytest.raises(RuntimeError, match=f"expected {required}.*PRINTED hole center marks, found {2*required}"):
        drawing._require_center_mark_census(
            object(), case.view, label=label, required=required,
            detail=None if label == "front" else label,
        )
    assert len(case.raws) == 4  # No deletion, move, or position-based coalescing.
    assert sum("class=PRINTED" in log for log in case.logs) == 2 * required
    assert sum("class=GHOST" in log for log in case.logs) == 4 - 2 * required
    assert any(f"total_view_annotations=4, non_mark=0, printed={2*required}, ghost={4-2*required}, fail=0" in log
               for log in case.logs)


@pytest.mark.parametrize("label", ["D", "E"])
def test_r19_crop_and_rows_have_explicit_serialization_intervals_not_a_runtime_allowance(label):
    quantum = 1e-7  # _drawing_layout_audit._round: 0.1 um serialized coordinates.
    native = _R19_NATIVE_MARK_CROPS[label]
    serialized = tuple(round(value, 7) for value in native)
    for observed, boundary in zip(serialized, native):
        assert observed - quantum / 2.0 <= boundary <= observed + quantum / 2.0
    record = next(record for record in _R19_MARK_RECORDS[label] if record[2] is not None)
    assert drawing._center_mark_bucket(record[1], {"lines": _R19_MARK_LINES[label]}, serialized) == "PRINTED"
    # Mixed readback/serialized coordinates differ by a few float64 ULP in D.
    # R23's display-only float32 spacing admits that difference, not the much
    # larger 0.1 um serialization interval; the interval is fixture evidence.
    assert drawing._center_mark_bucket(record[1], {"lines": _R19_MARK_LINES[label]}, native) == "PRINTED"
    row = list(_R19_MARK_LINES[label][0])
    row[4], row[7] = native[0] - quantum / 2.0, native[0] + 0.001
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket(record[1], {"lines": [row]}, native)


def test_center_mark_containment_rejects_two_float32_ulp_without_fixture_padding():
    crop = (0.0, 0.0, 0.1, 0.1)
    row = _native_line(0.05, 0.05, crop[2], 0.05)
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop) == "PRINTED"
    row[7] = crop[2] + 2.0 * math.ldexp(1.0, -27)  # Float32 spacing at 0.1 m.
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop)


@pytest.mark.parametrize("label", ["D", "E"])
def test_center_mark_census_uses_actual_persisted_detail_crop_not_padded_outline(mark_census, monkeypatch, label):
    adapter, native_view = _native_crop_fixture(monkeypatch, label)
    x, y = native_view.physical
    case = mark_census([
        ("printed", (x, y, 0), {"lines": [_native_line(x - 0.001, y, x + 0.001, y)]}),
        ("ghost", (x + 1.0, y, 0), {}),
    ])
    native_view.annotations = case.raws
    view = case.binding.raw(native_view, "IView")
    counts = drawing._require_center_mark_census(adapter, view, label=label, required=1, detail=label)
    assert counts == {"NON_MARK": 0, "PRINTED": 1, "GHOST": 1, "FAIL": 0}
    assert native_view.outline_reads == 1  # The persisted crop's existing independent read.
    assert native_view.crop_circle.NoOutline is (label == "D")
    # Ink in the padding is outside the physical crop and must remain fatal.
    outside = x + native_view.radius + native_view.padding / 2.0
    case.datas[0].display["lines"] = [_native_line(x, y, outside, y)]
    with pytest.raises(RuntimeError, match="outside crop"):
        drawing._require_center_mark_census(adapter, view, label=label, required=1, detail=label)


def test_center_mark_census_accounts_nonmark_and_all_marks_even_after_failure(mark_census):
    case = mark_census([
        ("inside-empty", (0.05, 0.05, 0), {}),
        ("outside-ghost", (0.5, 0.05, 0), {}),
        ("printed", (0.05, 0.05, 0), {"lines": [_native_line(0.04, 0.05, 0.06, 0.05)]}),
    ])
    nonmark = _native("IAnnotation", GetType=lambda: 6)
    case.raws.append(case.binding.raw(nonmark, "IAnnotation"))
    with pytest.raises(RuntimeError, match="inside-empty.*empty native centre-mark display inside crop"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert sum("class=FAIL" in log for log in case.logs) == 1
    assert sum("class=GHOST" in log for log in case.logs) == 1
    assert sum("class=PRINTED" in log for log in case.logs) == 1
    assert any("total_view_annotations=4, non_mark=1, printed=1, ghost=1, fail=1" in log for log in case.logs)
    assert len(case.raws) == 4


@pytest.mark.parametrize("position", [(0.05, 0.05, 0), (0, 0, 0), (0.1, 0.1, 0)])
def test_empty_center_mark_inside_or_on_crop_is_fatal(mark_census, position):
    case = mark_census([("inside-empty", position, {})])
    with pytest.raises(RuntimeError, match="empty native centre-mark display inside crop"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)


@pytest.mark.parametrize("position", [(0.05, 0.05, 0), (0.5, 0.05, 0)])
@pytest.mark.parametrize("failure", [None, RuntimeError("COM refused GetDisplayData")])
def test_null_or_unreadable_display_is_never_a_ghost(mark_census, position, failure):
    case = mark_census([("unreadable", position, {})])
    def unreadable():
        if isinstance(failure, Exception):
            raise failure
        return failure
    case.annotations[0].GetDisplayData = unreadable
    with pytest.raises(RuntimeError, match="GetDisplayData"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)
    assert any("class=FAIL" in log for log in case.logs)
    assert not any("class=GHOST" in log for log in case.logs)


@pytest.mark.parametrize("count_member", [
    "GetLineCount", "GetArcCount", "GetArrowHeadCount", "GetPolyLineCount",
    "GetPolygonCount", "GetTriangleCount", "GetEllipseCount", "GetTextCount",
])
@pytest.mark.parametrize("answer", [None, False, True, -1, 0.0, 1.5, "0", RuntimeError("COM refused count")])
def test_every_display_count_is_required_integer_not_permissive_false_to_zero(mark_census, count_member, answer):
    case = mark_census([("outside-empty", (0.5, 0.05, 0), {})])
    case.datas[0].overrides[count_member] = answer
    with pytest.raises(RuntimeError, match=count_member):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)
    assert any("class=FAIL" in log for log in case.logs)


@pytest.mark.parametrize("key", tuple(_NATIVE_CALLOUT_ROWS))
@pytest.mark.parametrize("failure", [None, RuntimeError("COM refused row")])
def test_counted_primitive_row_cannot_disappear_as_ghost(mark_census, key, failure):
    case = mark_census([("counted", (0.5, 0.05, 0), {key: [list(_NATIVE_CALLOUT_ROWS[key])]})])
    for getter in _MarkDisplayData._primitives[key][1]:
        case.datas[0].overrides[getter] = failure
    with pytest.raises(RuntimeError, match="unreadable native Get.*row #0"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert any("class=FAIL" in log for log in case.logs)


@pytest.mark.parametrize("key", tuple(_NATIVE_CALLOUT_ROWS))
@pytest.mark.parametrize("defect", ["empty", "short", "long", "nonfinite", "bool", "string", "false-row"])
def test_center_mark_malformed_rows_fail_before_any_tolerant_decoding(mark_census, key, defect):
    row = list(_NATIVE_CALLOUT_ROWS[key])
    if defect == "empty":
        row = []
    elif defect == "short":
        row.pop()
    elif defect == "long":
        row.append(0.0)
    elif defect == "nonfinite":
        row[-1] = math.nan
    elif defect == "bool":
        row[-1] = False
    elif defect == "string":
        row[-1] = "0"
    else:
        row = False
    case = mark_census([("malformed", (0.05, 0.05, 0), {key: [row]})])
    with pytest.raises(RuntimeError, match=f"invalid native {key}|unreadable native Get"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)


@pytest.mark.parametrize("key", tuple(_NATIVE_CALLOUT_ROWS))
def test_center_mark_counts_every_supported_primitive_family(mark_census, key):
    row = list(_NATIVE_CALLOUT_ROWS[key])
    case = mark_census([("primitive", (0.5, 0.05, 0), {key: [row]})])
    counts = drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert counts["PRINTED"] == 1 and counts["GHOST"] == 0
    assert any("class=PRINTED" in log and f"'{key}': 1" in log for log in case.logs)


@pytest.mark.parametrize("key,index", [
    ("lines", 7), ("arcs", 7), ("arrows", 0), ("polylines", 7),
    ("polygons", 5), ("triangles", 0), ("ellipses", 13),
])
def test_one_outside_primitive_fails_even_with_inside_anchor_and_other_inside_lines(mark_census, key, index):
    row = list(_NATIVE_CALLOUT_ROWS[key])
    if key == "arcs":
        # Exact binary fractions preserve the audited equal-radius contract.
        row = [-1, 0, 0, 0, 0.1875, 0.0625, 0, 0.0625, 0.1875, 0,
               0.0625, 0.0625, 0, 0, 0, 1, 1]
    else:
        row[index] = 0.2
    display = {"lines": [_native_line(0.04, 0.05, 0.06, 0.05)]}
    display.setdefault(key, []).append(row)
    case = mark_census([("outside-primitive", (0.05, 0.05, 0), display)])
    refusal = "envelope not certified inside" if key in ("arcs", "ellipses", "arrows") else "outside crop"
    with pytest.raises(RuntimeError, match=f"{key}.*{refusal}") as caught:
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert "raw=" in str(caught.value) and "crop=(0.0, 0.0, 0.1, 0.1)" in str(caught.value)
    if key in ("arcs", "ellipses", "arrows"):
        assert "outside crop" not in str(caught.value)


@pytest.mark.parametrize("row", [
    {"t": "X", "pos": [0.05, 0.05, 0], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.004},
    {}, None, False, {"t": "", "w": 0},
])
def test_center_mark_nonempty_text_count_is_fatal_without_speculative_text_extent_reads(mark_census, row):
    case = mark_census([("with-text", (0.5, 0.05, 0), {"texts": [row]})])
    with pytest.raises(RuntimeError, match="cannot certify primitive containment.*GetTextCount=1"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert any("class=FAIL" in log and "'texts': 1" in log for log in case.logs)
    assert not any("class=GHOST" in log for log in case.logs)
    assert {member for member, _args in case.datas[0].reads if member.startswith("GetText")} == {"GetTextCount"}


def test_pure_center_mark_text_data_cannot_use_relative_positions_as_absolute_bounds():
    text = {"t": "X", "pos": [0.05, 0.05, 0], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.004}
    with pytest.raises(ValueError, match="cannot certify primitive containment.*text"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"texts": [text]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("refusal", [None, [], (), RuntimeError("old overload refused")])
def test_center_mark_uses_only_existing_line3_to_line2_refusal_route(mark_census, refusal):
    case = mark_census([("fallback", (0.05, 0.05, 0), {"lines": [_native_line(0.04, 0.05, 0.06, 0.05)]})])
    case.datas[0].overrides["GetLineAtIndex3"] = refusal
    assert drawing._require_center_mark_census(object(), case.view, label="front", required=1)["PRINTED"] == 1
    assert ("GetLineAtIndex3", (0,)) in case.datas[0].reads
    assert ("GetLineAtIndex2", (0,)) in case.datas[0].reads


@pytest.mark.parametrize("malformed", [False, 0, [0.0], [0.0] * 9, [0.0] * 11])
def test_center_mark_malformed_line3_does_not_fall_back_and_hide_bad_data(mark_census, malformed):
    case = mark_census([("bad-overload", (0.05, 0.05, 0), {"lines": [_native_line(0.04, 0.05, 0.06, 0.05)]})])
    case.datas[0].overrides["GetLineAtIndex3"] = malformed
    with pytest.raises(RuntimeError, match="invalid native lines"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert ("GetLineAtIndex2", (0,)) not in case.datas[0].reads


@pytest.mark.parametrize("position", [
    None, (), (0.5, 0.05), (0.5, 0.05, math.nan), (0.5, math.inf, 0),
    (False, 0.5, 0), ("0.5", 0.5, 0),
])
def test_ghost_requires_a_readable_finite_three_coordinate_anchor(mark_census, position):
    case = mark_census([("bad-position", position, {})])
    with pytest.raises(RuntimeError, match="GetPosition"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)


@pytest.mark.parametrize("bbox", [
    None, (), (0, 0, 1), (0.1, 0, 0, 0.1), (0, 0.1, 0.1, 0),
    (0, 0, 0, 0.1), (0, 0, 0.1, math.nan), (False, 0, 0.1, 0.1),
])
def test_center_mark_invalid_or_inverted_crop_is_fatal(bbox):
    with pytest.raises(ValueError, match="crop bbox"):
        drawing._center_mark_bucket((0.5, 0.05, 0), {}, bbox)


def test_center_mark_invalid_decoded_bbox_cannot_count_as_printed(mark_census, monkeypatch):
    case = mark_census([("inverted", (0.05, 0.05, 0), {"lines": [_native_line(0.04, 0.05, 0.06, 0.05)]})])
    monkeypatch.setattr(drawing, "_center_mark_primitive_box", lambda *_args: Box(0.06, 0.05, 0.04, 0.05))
    with pytest.raises(RuntimeError, match="invalid native lines primitive bbox"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)


@pytest.mark.parametrize("bucket", [None, "", "OTHER", "NON_MARK", "FAIL"])
def test_center_mark_bucket_fallthrough_is_fatal_and_accounted(mark_census, monkeypatch, bucket):
    case = mark_census([("fallthrough", (0.5, 0.05, 0), {})])
    monkeypatch.setattr(drawing, "_center_mark_bucket", lambda *_args, **_kwargs: bucket)
    with pytest.raises(RuntimeError, match="bucket fallthrough"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)
    assert any("total_view_annotations=1, non_mark=0, printed=0, ghost=0, fail=1" in log for log in case.logs)


@pytest.mark.parametrize("buckets,total", [
    ([], 1), (["PRINTED"], 0), (["PRINTED", "GHOST"], 3), (["OTHER"], 1),
])
def test_center_mark_accounting_guard_rejects_count_mismatch_or_unknown_bucket(buckets, total):
    with pytest.raises(RuntimeError, match="bucket/count mismatch|bucket fallthrough"):
        drawing._center_mark_census_totals(buckets, total)


@pytest.mark.parametrize("reported", [0, 2, None, False])
def test_center_mark_native_annotation_count_is_not_inferred_from_array(mark_census, reported):
    case = mark_census([("ghost", (0.5, 0.05, 0), {})])
    case.native_view.GetAnnotationCount = lambda: reported
    with pytest.raises(RuntimeError, match="annotation (array length|count)|invalid native annotation count"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)


@pytest.mark.parametrize("wrong_owner", ["view", "annotation", "display-data"])
def test_center_mark_census_refuses_foreign_interface_owners(mark_census, wrong_owner):
    case = mark_census([("ghost", (0.5, 0.05, 0), {})])
    if wrong_owner == "view":
        case.view = case.annotations[0]
    elif wrong_owner == "annotation":
        case.raws[0] = case.binding.raw(case.datas[0], "IDisplayData")
    else:
        case.annotations[0].data = case.binding.raw(case.annotations[0], "IAnnotation")
    with pytest.raises((RuntimeError, AssertionError)):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)


def test_center_mark_fakes_keep_owners_and_member_surfaces_disjoint(mark_census):
    case = mark_census([("ghost", (0.5, 0.05, 0), {})])
    annotation, data = case.annotations[0], case.datas[0]
    assert not hasattr(annotation, "GetLineCount")
    assert not hasattr(annotation, "GetTextCount")
    assert not hasattr(data, "GetDisplayData")
    assert not hasattr(data, "GetType")
    assert not hasattr(data, "GetAnnotations")
    assert not hasattr(data, "GetSpecificAnnotation")
    assert not hasattr(data, "IGetDisplayData")
    for native, interface in ((annotation, "IDisplayData"), (data, "IAnnotation"), (data, "IView")):
        with pytest.raises(RuntimeError, match="native owner mismatch"):
            _bind_owner(native, interface)


@pytest.mark.parametrize("required", [1, 2])
def test_printed_count_goals_remain_fatal_even_when_every_annotation_is_accounted(mark_census, required):
    records = [("ghost", (0.5, 0.05, 0), {})]
    if required == 2:
        records.append(("printed", (0.05, 0.05, 0), {"lines": [_native_line(0.04, 0.05, 0.06, 0.05)]}))
    case = mark_census(records)
    with pytest.raises(RuntimeError, match=f"expected {required}.*PRINTED hole center marks, found {required-1}"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=required)
    assert any(f"printed={required-1}, ghost=1, fail=0" in log for log in case.logs)


@pytest.mark.parametrize("member,answer", [
    ("GetName", None), ("GetName", ""), ("GetName", False),
    ("GetPosition", RuntimeError("COM refused GetPosition")),
    ("GetType", None), ("GetType", False), ("GetType", 0), ("GetType", 20),
])
def test_center_mark_native_identity_refusals_are_fatal(mark_census, member, answer):
    case = mark_census([("bad-identity", (0.5, 0.05, 0), {})])
    def read():
        if isinstance(answer, Exception):
            raise answer
        return answer
    setattr(case.annotations[0], member, read)
    with pytest.raises(RuntimeError, match="GetName|GetPosition|annotation type"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)
    assert any("total_view_annotations=1, non_mark=0, printed=0, ghost=0, fail=1" in log for log in case.logs)


def test_counted_missing_row_is_fatal_not_a_smaller_primitive_set(mark_census):
    case = mark_census([("count-mismatch", (0.5, 0.05, 0), {})])
    case.datas[0].overrides["GetPolygonCount"] = 1
    with pytest.raises(RuntimeError, match="GetPolygonAtIndex.*row #0"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)
    assert any("'polygons': 1" in log and "class=FAIL" in log for log in case.logs)


@pytest.mark.parametrize("key,index", [("polylines", 6), ("polygons", 4)])
@pytest.mark.parametrize("count", [-1, 1.5, False, math.inf])
def test_center_mark_variable_point_count_is_strict(mark_census, key, index, count):
    row = list(_NATIVE_CALLOUT_ROWS[key])
    row[index] = count
    case = mark_census([("bad-point-count", (0.05, 0.05, 0), {key: [row]})])
    with pytest.raises(RuntimeError, match=f"invalid native {key}"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)


@pytest.mark.parametrize("key,header", [("polylines", 7), ("polygons", 5)])
def test_center_mark_nonempty_zero_point_primitive_is_not_silently_removed(mark_census, key, header):
    row = list(_NATIVE_CALLOUT_ROWS[key][:header])
    row[-1] = 0
    case = mark_census([("zero-point", (0.5, 0.05, 0), {key: [row]})])
    with pytest.raises(RuntimeError, match=f"unmeasurable native {key}: no points"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)


@pytest.mark.parametrize("key,header", [("polylines", 7), ("polygons", 5)])
def test_center_mark_one_point_primitive_has_bounds_and_cannot_disappear(key, header):
    row = list(_NATIVE_CALLOUT_ROWS[key][:header + 3])
    row[header - 1] = 1
    assert drawing._center_mark_bucket((0.5, 0.05, 0), {key: [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    row[header] = 0.2
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {key: [row]}, (0, 0, 0.1, 0.1))


def test_center_mark_degenerate_line_still_accounts_its_native_coordinates():
    row = _native_line(0.05, 0.05, 0.05, 0.05)
    assert drawing._center_mark_bucket((0.5, 0.05, 0), {"lines": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    row[4] = row[7] = 0.2
    with pytest.raises(ValueError, match="outside crop"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("direction,normal_z", [(1, 1), (0, 1), (1, -1), (-1, 1)])
def test_center_mark_arc_certifies_full_circle_without_guessing_sweep_or_normal_convention(direction, normal_z):
    row = [-1, 0, 0, 0, 0.1, 0.05, 0, 0, 0.05, 0,
           0.05, 0.05, 0, 0, 0, normal_z, direction]
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, (-0.1, -0.1, 0.2, 0.2)) == "PRINTED"
    # A partial sweep could fit, but a nearly closed circle is not distinguished
    # without inventing a threshold. The complete envelope must certify it.
    with pytest.raises(ValueError, match="cannot certify primitive containment.*partial native arcs") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, (-0.1, -0.1, 0.2, 0.075))
    assert "outside crop" not in str(caught.value)


def test_center_mark_closed_arc_bounds_every_cardinal_extremum():
    row = [-1, 0, 0, 0, 0.05, 0.05, 0, 0.05, 0.05, 0,
           0, 0.05, 0, 0, 0, 1, 1]
    with pytest.raises(ValueError, match="arcs.*envelope not certified inside"):
        drawing._center_mark_bucket((0, 0.05, 0), {"arcs": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("index,value", [(13, 1), (14, 1), (15, 0), (16, 2), (6, 1), (9, 1), (12, 1)])
def test_center_mark_arc_refuses_unmeasurable_plane_or_direction(index, value):
    row = list(_NATIVE_CALLOUT_ROWS["arcs"])
    row[index] = value
    with pytest.raises(ValueError, match="arcs plane/direction"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, (0, 0, 0.1, 0.1))


def test_center_mark_ellipse_uses_analytic_rotated_envelope_not_axis_endpoints():
    # X/Y axis extrema lie beyond the individually contained major/minor points.
    row = [-1, 0, 0, 0, 0.08, 0.08, 0, 0.08, 0.08, 0,
           0.05, 0.05, 0, 0.08, 0.08, 0, 0.02, 0.08, 0]
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    with pytest.raises(ValueError, match="ellipses.*envelope not certified inside"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0.02, 0.02, 0.08, 0.08))


def test_center_mark_invalid_ellipse_axes_do_not_fall_through():
    row = list(_NATIVE_CALLOUT_ROWS["ellipses"])
    row[16:19] = row[13:16]
    with pytest.raises(ValueError, match="ellipses axes"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("display", [None, [], {"unknown": []}, {"lines": None}])
def test_center_mark_unrecognized_display_data_is_fatal_not_empty(display):
    with pytest.raises(ValueError, match="invalid native"):
        drawing._center_mark_bucket((0.5, 0.05, 0), display, (0, 0, 0.1, 0.1))


def test_build_center_mark_census_keeps_exact_native_goals_without_any_authoring_calls():
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    module = ast.parse(source)
    build = next(node for node in module.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build")
    census_loop = next(node for node in ast.walk(build) if isinstance(node, ast.For)
                       and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                               and call.func.id == "_require_center_mark_census" for call in ast.walk(node)))
    assert [(entry.elts[0].value, entry.elts[2].value, entry.elts[3].value)
            for entry in census_loop.iter.elts] == [
        ("front", 2, None), ("detail D", 1, "D"), ("detail E", 1, "E"),
    ]
    call = next(node for node in ast.walk(census_loop) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "_require_center_mark_census")
    assert {keyword.arg for keyword in call.keywords} == {"label", "required", "detail"}
    methods = {node.func.attr for node in ast.walk(census_loop)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not methods  # No delete/insert/position/mark-specific native APIs.


@pytest.mark.parametrize("bbox", [None, (0.1, 0, 0, 0.1), (False, 0, 0.1, 0.1), ("0", 0, 0.1, 0.1)])
def test_front_native_outline_is_read_on_view_without_float_coercing_malformed_data(mark_census, bbox):
    case = mark_census([("ghost", (0.5, 0.05, 0), {})], crop=bbox)
    with pytest.raises(ValueError, match="invalid native centre-mark crop bbox"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=0)
    assert ("IView", case.native_view) in case.binding.calls


@pytest.mark.parametrize("data_size", [0, 7, 12])
def test_center_mark_type1_polyline_cannot_guess_undocumented_geomdata_layout(data_size):
    row = list(_NATIVE_CALLOUT_ROWS["polylines"])
    row[:2] = [1, data_size]
    with pytest.raises(ValueError, match="cannot certify primitive containment.*polylines type-1 GeomData"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"polylines": [row]}, (0, 0, 0.1, 0.1))
    row.append(0.05)
    with pytest.raises(ValueError, match="invalid native polylines"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"polylines": [row]}, (0, 0, 0.1, 0.1))


@pytest.mark.parametrize("style", [0, 1])
def test_center_mark_reuses_contracted_triangular_arrow_styles(style):
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[8] = style
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"arrows": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"


@pytest.mark.parametrize("style", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, -1, 0.5, 13])
def test_center_mark_uncontracted_arrow_glyph_does_not_use_triangle_as_fake_envelope(mark_census, style):
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[8] = style
    case = mark_census([("uncertifiable-arrow", (0.05, 0.05, 0), {"arrows": [row]})])
    with pytest.raises(RuntimeError, match="cannot certify primitive containment.*arrows style|invalid native arrows"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    assert any("class=FAIL" in log for log in case.logs)
    assert not any("class=GHOST" in log for log in case.logs)


def test_center_mark_partial_ellipse_accepts_only_proved_full_envelope_certificate():
    row = [-1, 0, 0, 0, 0.08, 0.08, 0, 0.02, 0.08, 0,
           0.05, 0.05, 0, 0.08, 0.08, 0, 0.02, 0.08, 0]
    assert drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0, 0, 0.1, 0.1)) == "PRINTED"
    with pytest.raises(ValueError, match="cannot certify primitive containment.*partial native ellipses") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"ellipses": [row]}, (0.02, 0.02, 0.08, 0.08))
    assert "raw=" in str(caught.value) and "crop=" in str(caught.value)
    assert "outside crop" not in str(caught.value)  # Sweep direction is unobserved.


@pytest.mark.parametrize("crop", [(-0.1, -0.1, 0.2, 0.2), (-0.1, -0.1, 0.2, 0.075)])
def test_center_mark_inconsistent_arc_radii_are_fatal_even_when_an_estimated_box_would_fit(crop):
    row = [-1, 0, 0, 0, 0.1, 0.05, 0, 0.025, 0.05, 0,
           0.05, 0.05, 0, 0, 0, 1, 1]
    with pytest.raises(ValueError, match="invalid native arcs radius: inconsistent endpoint radii") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arcs": [row]}, crop)
    assert "outside crop" not in str(caught.value)


def test_arc_subnormal_float64_endpoint_delta_keeps_strict_full_envelope_requirement():
    # This is the strict curve certificate, not the display bbox's float32 allowance.
    row = [-1, 0, 0, 0, 0.05, 0, 0, 0.05, math.nextafter(0.0, math.inf), 0,
           0, 0, 0, 0, 0, 1, 1]
    assert math.dist(row[4:6], row[10:12]) == math.dist(row[7:9], row[10:12])
    assert drawing._center_mark_bucket((0, 0, 0), {"arcs": [row]}, (-0.1, -0.1, 0.1, 0.1)) == "PRINTED"
    with pytest.raises(ValueError, match="cannot certify primitive containment.*partial native arcs"):
        drawing._center_mark_bucket((0, 0, 0), {"arcs": [row]}, (-0.1, -1e-100, 0.1, 1e-100))


@pytest.mark.parametrize("index,value", [
    (3, 0), (5, 1), (6, -1), (7, -1), (8, -1), (8, 0.5), (8, 13),
    (9, 1), (10, 1), (11, 0),
])
def test_center_mark_arrow_certificate_requires_valid_planar_direction_size_and_known_style(index, value):
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[index] = value
    with pytest.raises(ValueError, match="invalid native arrows"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arrows": [row]}, (0, 0, 0.1, 0.1))


def test_center_mark_arrow_two_sided_certificate_does_not_rely_on_empirical_base_convention():
    row = list(_NATIVE_CALLOUT_ROWS["arrows"])
    row[0:2] = [0.098, 0.05]
    # The historical triangle points left and would fit, but the documented
    # dimensions alone do not seat its base side. Refuse, do not claim outside.
    with pytest.raises(ValueError, match="cannot certify primitive containment.*native arrows") as caught:
        drawing._center_mark_bucket((0.05, 0.05, 0), {"arrows": [row]}, (0, 0, 0.1, 0.1))
    assert "outside crop" not in str(caught.value)


def test_center_mark_schema_cannot_spill_into_preexisting_callout_guards(native_callout_record, monkeypatch):
    def census_schema_must_not_run(*_args):
        pytest.fail("census-only schema reached a downstream callout guard")
    monkeypatch.setattr(drawing, "_validate_center_mark_display", census_schema_must_not_run)
    record = native_callout_record.dump()
    row = list(_NATIVE_CALLOUT_ROWS["polylines"])
    row[:2] = [1.0, 7.0]
    record["display"]["polylines"] = [row]
    assert drawing._arc_callout_geometry(record, 0.62).text_boxes


def test_center_mark_and_callout_schema_ownership_remains_separate():
    module = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    callout = next(node for node in module.body
                   if isinstance(node, ast.FunctionDef) and node.name == "_arc_callout_geometry")
    called_names = {node.func.id for node in ast.walk(callout)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "_validate_center_mark_display" not in called_names
    assert "_native_finite_row" not in called_names
    assert "_native_finite_scalar" not in called_names
    assert "_display_coordinate_ulp_m" not in called_names
    assert "_display_bbox_comparisons" not in called_names


@pytest.mark.parametrize("magnitude,spacing_exponent", [
    (0.0, -149),
    (math.nextafter(0.0, math.inf), -149),
    (math.ldexp(1.0, -150), -149),  # Half a subnormal rounds to zero.
    (math.ldexp(1.0, -149), -149),
    (math.ldexp(1.0, -126), -149),  # Minimum normal float32.
    (math.ldexp(1.0, -125), -148),
    (math.nextafter(math.ldexp(1.0, -125), 0.0), -148),
    (0.5, -24),
    (1.0 - math.ldexp(1.0, -24), -24),  # Previous float32 before 1.
    (math.nextafter(1.0, 0.0), -23),  # Float64 below 1 rounds UP to float32 1.
    (1.0, -23),
    (math.nextafter(2.0, 0.0), -22),
    (2.0, -22),
    (0.1, -27),
    (0.1531, -26),
])
@pytest.mark.parametrize("sign", [-1.0, 1.0])
@pytest.mark.parametrize("larger_operand", ["actual", "boundary"])
def test_display_coordinate_spacing_rounds_float32_before_deriving_ulp(
    magnitude, spacing_exponent, sign, larger_operand,
):
    actual, boundary = (sign * magnitude, 0.0) if larger_operand == "actual" else (0.0, sign * magnitude)
    assert drawing._display_coordinate_ulp_m(actual, boundary) == math.ldexp(1.0, spacing_exponent)


@pytest.mark.parametrize("actual,boundary", [
    (False, 0.1), (0.1, True), ("0.1", 0.1), (0.1, None),
    (math.nan, 0.1), (0.1, math.inf), (-math.inf, 0.1),
    (1e40, 0.1), (0.1, -1e40),
    (float.fromhex("0x1.fffffep+127"), 0.1),
    (0.1, math.nextafter(float.fromhex("0x1.fffffep+127"), 0.0)),
])
def test_display_coordinate_spacing_refuses_invalid_overflow_or_infinite_successor(actual, boundary):
    with pytest.raises(ValueError, match="display precision|display spacing"):
        drawing._display_coordinate_ulp_m(actual, boundary)


def test_display_bbox_allowance_is_per_side_not_a_global_padding():
    crop = (0.125, 0.125, 0.25, 0.25)
    low_ulp, high_ulp = math.ldexp(1.0, -26), math.ldexp(1.0, -25)
    box = Box(crop[0] - low_ulp, crop[1] - low_ulp, crop[2] + high_ulp, crop[3] + high_ulp)
    comparisons = drawing._display_bbox_comparisons(box, crop)
    assert [item["coordinate"] for item in comparisons] == ["xmin", "ymin", "xmax", "ymax"]
    assert [item["tolerance_m"] for item in comparisons] == [low_ulp, low_ulp, high_ulp, high_ulp]
    assert [item["overrun_m"] for item in comparisons] == [low_ulp, low_ulp, high_ulp, high_ulp]
    assert all(item["accepted"] and item["precision_error"] is None for item in comparisons)


@pytest.mark.parametrize("side", range(4))
def test_display_bbox_each_side_rejects_two_float32_ulp(side):
    crop = (0.125, 0.125, 0.25, 0.25)
    coordinates = list(crop)
    ulp = math.ldexp(1.0, -26 if side < 2 else -25)
    coordinates[side] += (-2.0 if side < 2 else 2.0) * ulp
    comparisons = drawing._display_bbox_comparisons(Box(*coordinates), crop)
    assert comparisons[side]["overrun_m"] == 2.0 * ulp
    assert comparisons[side]["accepted"] is False
    assert all(item["accepted"] for index, item in enumerate(comparisons) if index != side)


_R22_NATIVE_D_ROW_5 = [
    -1, 0, -1, 0, 0.16000000044703483, 0.09500000025714497, 0,
    0.15309999912977218, 0.09500000025714497, 0,
]


def test_r22_unrounded_native_row_and_persisted_crop_pass_with_coordinate_telemetry(mark_census, monkeypatch):
    crop = _R19_NATIVE_MARK_CROPS["D"]  # Exact persisted D crop also captured in R22.
    case = mark_census([
        ("native-row-replay", (0.16, 0.095, 0), {"lines": [_R22_NATIVE_D_ROW_5]}),
        ("empty-native-ghost", (0.7086834, 0.1270803, 0.005), {}),
    ], crop=crop)
    def persisted_crop(_adapter, view, *, label):
        assert view is case.view and label == "D"
        return crop  # Unrounded task-log readback, never the 7dp JSON crop.
    monkeypatch.setattr(drawing, "_detail_crop", persisted_crop)
    counts = drawing._require_center_mark_census(object(), case.view, label="D", required=1, detail="D")
    assert counts == {"NON_MARK": 0, "PRINTED": 1, "GHOST": 1, "FAIL": 0}
    row_logs = [log for log in case.logs if "centre-mark primitive" in log]
    assert len(row_logs) == 1
    log = row_logs[0]
    assert "id='native-row-replay', kind=lines, index=0, accepted=True" in log
    assert f"crop={crop!r}" in log and f"raw={_R22_NATIVE_D_ROW_5!r}" in log
    bbox = drawing._center_mark_primitive_box("lines", _R22_NATIVE_D_ROW_5)
    comparisons = drawing._display_bbox_comparisons(bbox, crop)
    assert comparisons[0]["overrun_m"] == crop[0] - _R22_NATIVE_D_ROW_5[7]
    assert comparisons[0]["overrun_m"] * 1e9 == pytest.approx(0.8702278898)
    assert comparisons[0]["tolerance_m"] == math.ldexp(1.0, -26)
    for item in comparisons:
        assert f"{item['coordinate']}: actual_m={item['actual_m']!r}, crop_m={item['crop_m']!r}" in log
        assert f"tolerance_m={item['tolerance_m']!r}, overrun_m={item['overrun_m']!r}" in log


@pytest.mark.parametrize("overrun", [2.0 * math.ldexp(1.0, -26), 1e-6])
def test_r22_row_larger_overrun_is_fatal_and_all_compared_rows_are_logged(mark_census, overrun):
    crop = _R19_NATIVE_MARK_CROPS["D"]
    outside = list(_R22_NATIVE_D_ROW_5)
    outside[7] = crop[0] - overrun
    case = mark_census([
        ("native-row-replay", (0.16, 0.095, 0), {"lines": [_R22_NATIVE_D_ROW_5, outside, _R22_NATIVE_D_ROW_5]}),
        ("empty-native-ghost", (0.7086834, 0.1270803, 0.005), {}),
    ], crop=crop)
    with pytest.raises(RuntimeError, match="lines #1 outside crop beyond one float32 ULP"):
        drawing._require_center_mark_census(object(), case.view, label="D-row-replay", required=1)
    row_logs = [log for log in case.logs if "centre-mark primitive" in log]
    assert len(row_logs) == 3
    assert [f"index={index}, accepted={accepted}" in log
            for index, accepted, log in zip(range(3), (True, False, True), row_logs)] == [True, True, True]
    for log in row_logs:
        assert "id='native-row-replay', kind=lines" in log and f"crop={crop!r}" in log
        assert log.count("tolerance_m=") == 4 and log.count("overrun_m=") == 4
    assert any("total_view_annotations=2, non_mark=0, printed=0, ghost=1, fail=1" in log for log in case.logs)


def test_float32_precision_failure_never_produces_infinite_acceptance(mark_census):
    maximum = float.fromhex("0x1.fffffep+127")
    crop = (0.0, 0.0, maximum, maximum)
    case = mark_census([("unverifiable-spacing", (0.5, 0.5, 0), {
        "lines": [_native_line(0.25, 0.5, 0.75, 0.5)],
    })], crop=crop)
    with pytest.raises(RuntimeError, match="display precision failed.*nonfinite native float32 display spacing"):
        drawing._require_center_mark_census(object(), case.view, label="front", required=1)
    row_log = next(log for log in case.logs if "centre-mark primitive" in log)
    assert "accepted=False" in row_log
    assert "tolerance_m=None" in row_log
    assert "precision_error='nonfinite native float32 display spacing" in row_log
    assert "tolerance_m=inf" not in row_log


def test_display_precision_allowance_does_not_change_exact_empty_ghost_anchors():
    crop = (0.0, 0.0, 0.1, 0.1)
    assert drawing._center_mark_bucket((math.nextafter(crop[2], math.inf), 0.05, 0), {}, crop) == "GHOST"
    for anchor_x in (crop[2], math.nextafter(crop[2], 0.0)):
        with pytest.raises(ValueError, match="empty native centre-mark display inside crop"):
            drawing._center_mark_bucket((anchor_x, 0.05, 0), {}, crop)


def test_display_containment_rejects_one_and_a_quarter_ulp_not_rounded_ulp_distance():
    crop = (0.0, 0.0, 0.125, 0.125)
    row = _native_line(0.1, 0.05, crop[2] + 1.25 * math.ldexp(1.0, -26), 0.05)
    evidence = []
    with pytest.raises(ValueError, match="lines #0 outside crop beyond one float32 ULP"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop, primitive_evidence=evidence)
    upper_x = evidence[0]["comparisons"][2]
    assert upper_x["overrun_m"] == 1.25 * math.ldexp(1.0, -26)
    assert upper_x["tolerance_m"] == math.ldexp(1.0, -26)
    assert upper_x["accepted"] is False


def test_display_containment_rejects_two_subnormal_steps_outside_zero_boundary():
    crop = (0.0, 0.0, 0.1, 0.1)
    row = _native_line(0.0, 0.05, -math.ldexp(1.0, -148), 0.05)
    evidence = []
    with pytest.raises(ValueError, match="lines #0 outside crop beyond one float32 ULP"):
        drawing._center_mark_bucket((0.05, 0.05, 0), {"lines": [row]}, crop, primitive_evidence=evidence)
    lower_x = evidence[0]["comparisons"][0]
    assert lower_x["overrun_m"] == math.ldexp(1.0, -148)
    assert lower_x["tolerance_m"] == math.ldexp(1.0, -149)
    assert lower_x["accepted"] is False


class _R24Annotation(_ClearanceAnnotation):
    """IAnnotation only; the display/model/data objects are distinct producers."""

    def __init__(self, name, position, data, *, kind=4, attached=(), leaders=()):
        super().__init__(name, position, data, kind=kind, leaders=leaders, hole_callout=False)
        self.attached = tuple(attached)
        self.dangling = False
        self.display = None

    def GetSpecificAnnotation(self):
        return self.display

    def GetAttachedEntities3(self):
        return self.attached

    def GetAttachedEntityCount3(self):
        return len(self.attached)

    def GetAttachedEntityTypes(self):
        return tuple(1 for _ in self.attached)

    def IsDangling(self):
        return self.dangling


def _r24_text(text, xy, *, width=0.0135042):
    return {"t": text, "pos": [*xy, 0.0], "h": 0.0035, "ref": 1, "ang": 0.0, "w": width}


@pytest.mark.parametrize("label,text_position,arrow_tips,connector", [
    ("dt-cylinder-gear/FaceWidth", (0.225, 0.220),
     ((0.2102924, 0.220), (0.2057924, 0.220)),
     [0.0, 0.0, 0.0, 0.0, 0.2080424, 0.220, 0.0464999, 0.2127281, 0.2172219, 0.0]),
    ("dt-crank-handle-pivot-screw/ReliefDia", (0.1155, 0.144),
     ((0.08575, 0.162225), (0.08575, 0.167775)),
     [0.0, 0.0, 0.0, 0.0, 0.08575, 0.165, -0.0003, 0.0908542, 0.138417, 0.0]),
    ("sm-gooseneck-spring-screw/ReliefDia", (0.23005, 0.1495),
     ((0.202, 0.1606), (0.202, 0.1694)),
     [0.0, 0.0, 0.0, 0.0, 0.202, 0.165, -0.0004, 0.2028181, 0.143917, 0.0]),
    ("fr-top-frame/PocketRise", (0.0422, 0.0785),
     ((0.070, 0.091875), (0.070, 0.099875)),
     [0.0, 0.0, 0.0, 0.0, 0.070, 0.095875, 0.107, 0.0656719, 0.0673875, -0.0]),
])
def test_r26_actual_four_native_linear_offset_samples_keep_dimension_midpoint_attachment(
    label, text_position, arrow_tips, connector,
):
    # Actual rows from C:/farm-runs/ms-stop/
    # 20261012T055029190Z-4b5f6c488dce44489a438169e748265c.out/reports/layout-audit/
    # <label before slash>.json. PocketRise is on a later sheet, Drawing View11.
    terminal = tuple(connector[4:6])
    midpoint = tuple((a + b) / 2.0 for a, b in zip(*arrow_tips, strict=True))
    assert terminal == pytest.approx(midpoint, abs=1e-12), label
    assert math.dist(terminal, text_position) > 0.001
    assert tuple(connector[7:9]) != terminal


@pytest.mark.parametrize("defect", [
    "bool-count", "negative-count", "missing-row", "truncated-row", "nonfinite-row",
    "bool-height", "null-position", "wrong-anchor-owner", "wrong-data-owner",
])
def test_r24_native_ink_refuses_bad_scalar_row_and_interface_contracts(r24_tip, defect):
    case = r24_tip
    if defect == "bool-count":
        case.data.GetLineCount = lambda: True
    elif defect == "negative-count":
        case.data.GetLineCount = lambda: -1
    elif defect == "missing-row":
        case.data.GetLineAtIndex3 = lambda _i: None
    elif defect == "truncated-row":
        case.data.lines[0] = [0.0] * 9
    elif defect == "nonfinite-row":
        case.data.lines[0][4] = float("nan")
    elif defect == "bool-height":
        case.data.texts[0]["h"] = True
    elif defect == "null-position":
        case.annotation.position = None
    elif defect == "wrong-anchor-owner":
        case.annotation._native_interfaces = ("IDisplayDimension",)
    elif defect == "wrong-data-owner":
        case.data._native_interfaces = ("IAnnotation",)
    with pytest.raises(RuntimeError):
        drawing._r24_record(case.adapter, case.annotation, label="strict ink")


@pytest.fixture
def r24_tip(bound, monkeypatch):
    """R23 actual native primitives, with the effective SP4 document gap."""
    from _drawing_edges import ViewEdge

    attached = (object(), object())
    top = (drawing.TOP_END_X, drawing.TOP_END_Y, drawing.ARM_THICKNESS / 2.0)
    bottom = (drawing.ROD_TIP_X, drawing._ROD_TIP_Y, drawing.ARM_THICKNESS / 2.0)
    land = ViewEdge(object(), (top, bottom), None, (object(), object()))
    data = _ClearanceDisplayData(
        [_r24_text(" 5.59 ", (0.3711812, 0.1272219), width=0.0116375)],
        [_native_line(0.3424517, 0.1286044, 0.3770938, 0.135),
         _native_line(0.3444807, 0.1176142, 0.3791228, 0.1240097),
         _native_line(0.3761104, 0.1348185, 0.3749576, 0.1410629),
         _native_line(0.3781394, 0.1238282, 0.3792923, 0.1175837)],
        primitives={"arrows": [
            [0.3761104, 0.1348185, 0.0002, -0.1815501, 0.9833817, 0,
             0.003556, 0.000762, 0, 0, 0, 1],
            [0.3781394, 0.1238282, 0.0002, 0.1815501, -0.9833817, 0,
             0.003556, 0.000762, 0, 0, 0, 1],
        ]},
    )
    ann = _R24Annotation("RodTipLen", (0.377, 0.130, 0.0002), data, attached=attached)
    state = SimpleNamespace(annotation=ann, data=data, land=land, calls=[],
                            gaps=[0.001, 0.001], use_doc=[True, True])

    def get_gap(index, use_doc, gap):
        state.calls.append((index, use_doc, gap))
        assert index in (0, 1) and use_doc is False and gap == 0.0
        return True, state.use_doc[index], state.gaps[index]

    model = _native("IDimension", SystemValue=drawing.TIP_FACE / 1000.0)
    display = _native("IDisplayDimension", GetWitnessLineGap=get_gap,
                      GetDimension2=lambda index: model if index == 0 else None)
    ann.display = display
    state.adapter = SimpleNamespace(swApp=_APP)
    state.model = model
    _centre, radius_mm = drawing._detail_fence("E")
    radius = radius_mm * drawing.END_SCALE[0] / drawing.END_SCALE[1] / 1000.0
    state.crop = (drawing.END_CENTER[0] - radius, drawing.END_CENTER[1] - radius,
                  drawing.END_CENTER[0] + radius, drawing.END_CENTER[1] + radius)
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, a: _bind_owner(a, "IAnnotation").name)
    monkeypatch.setattr(drawing, "_detail_crop", lambda *_a, **_k: state.crop)
    monkeypatch.setattr(drawing, "_project", lambda _a, _v, points, **_k: [_end_xy(x * 1000, y * 1000) for x, y, _z in points])
    state.invoke = lambda **kwargs: drawing._require_rod_tip_endpoints(
        state.adapter, object(), state.land, state.annotation, **kwargs,
    )
    return state


def _r24_tip_effective_gaps(case, gaps, use_doc):
    """A different legitimate native gap must change the actual line starts."""
    case.gaps[:], case.use_doc[:] = gaps, use_doc
    normal = (math.cos(ch_rocker_arm_spec._ALPHA_TOP), math.sin(ch_rocker_arm_spec._ALPHA_TOP))
    for index, (x, y, _z) in enumerate(case.land.line):
        point = _end_xy(x, y)
        case.data.lines[index][4:6] = (point[0] + normal[0] * gaps[index],
                                     point[1] + normal[1] * gaps[index])


def test_r24_5_point_59_observed_sp4_true_true_one_mm_gap_has_real_visible_corner_routes(r24_tip):
    case = r24_tip
    before = case.annotation.attached
    assert case.invoke() == before
    assert case.calls == [(0, False, 0.0), (1, False, 0.0)]
    assert case.annotation.attached == before
    assert case.model.SystemValue == drawing.TIP_FACE / 1000.0
    assert not hasattr(case.annotation.display, "SetWitnessLineGap")
    assert drawing.END_KEEP["RodTipLen"] == (0.377, 0.128)


@pytest.mark.parametrize("gaps,use_doc", [
    ((0.0015, 0.0015), (False, False)),
    ((0.001, 0.0015), (True, False)),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_r24_5_point_59_normal_native_gap_and_display_enumeration_do_not_require_zero(r24_tip, gaps, use_doc, reverse):
    case = r24_tip
    _r24_tip_effective_gaps(case, gaps, use_doc)
    if reverse:
        case.data.lines.reverse()
        case.data.primitives["arrows"].reverse()
        case.land = replace(case.land, line=tuple(reversed(case.land.line)))
    case.invoke()


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("gap", [0.0, 0.002])
def test_r24_5_point_59_sp4_readback_cannot_pass_by_ignoring_effective_gap(r24_tip, index, gap):
    r24_tip.gaps[index] = gap  # Leave the actual R23 1mm-gap primitives unmoved.
    with pytest.raises(RuntimeError, match="disagree with effective gap readback"):
        r24_tip.invoke()


@pytest.mark.parametrize("result", [
    None, True, (True, True), (False, True, 0.001), (1, True, 0.001),
    (True, 0, 0.001), (True, True, True), (True, True, float("nan")),
    (True, True, float("inf")), (True, True, -0.001),
])
def test_r24_5_point_59_effective_gap_refuses_false_and_malformed_generated_out_tuples(r24_tip, result):
    r24_tip.annotation.display.GetWitnessLineGap = lambda index, use_doc, gap: result
    with pytest.raises(RuntimeError, match="unreadable native witness gap"):
        r24_tip.invoke()


@pytest.mark.parametrize("defect", [
    "missing-witness", "off-corner", "inward-witness", "duplicate-witness",
    "missing-arrow", "wrong-arrow", "own-text",
])
@pytest.mark.parametrize("index", [0, 1])
def test_r24_5_point_59_valid_default_gap_never_waives_actual_native_route_defects(r24_tip, defect, index):
    case = r24_tip
    if defect == "missing-witness":
        case.data.lines.pop(index)
    elif defect == "off-corner":
        case.data.lines[index][5] += 0.001
    elif defect == "inward-witness":
        row = case.data.lines[index]
        row[7:9] = (row[4] - 0.01, row[5] - 0.01)
    elif defect == "duplicate-witness":
        case.data.lines.append(list(case.data.lines[index]))
    elif defect == "missing-arrow":
        case.data.primitives["arrows"].pop(index)
    elif defect == "wrong-arrow":
        case.data.primitives["arrows"][index][0] += 0.001
    elif defect == "own-text":
        row = case.data.lines[index]
        case.data.texts[0]["pos"][:2] = ((row[4] + row[7]) / 2.0,
                                      (row[5] + row[8]) / 2.0)
    with pytest.raises(RuntimeError):
        case.invoke()


@pytest.mark.parametrize("defect", ["null", "dangling", "replaced", "duplicate", "extra", "bool-same"])
def test_r24_5_point_59_actual_native_attachments_survive_to_final_guard(r24_tip, defect):
    case = r24_tip
    before = case.invoke()
    if defect == "null":
        case.annotation.attached = (None,)
    elif defect == "dangling":
        case.annotation.dangling = True
    elif defect == "replaced":
        case.annotation.attached = (before[0], object())
    elif defect == "duplicate":
        case.annotation.attached = (before[0], before[0])
    elif defect == "extra":
        case.annotation.attached += (object(),)
    elif defect == "bool-same":
        case.adapter.swApp = _native("ISldWorks", IsSame=lambda a, b: True)
    with pytest.raises(RuntimeError, match="native attachments"):
        case.invoke(expected_attachments=before)


@pytest.mark.parametrize("value", [None, math.nan, math.inf, drawing.TIP_FACE / 1000.0 + 0.0001])
def test_r24_5_point_59_final_native_model_dimension_still_measures_imported_end_face(r24_tip, value):
    r24_tip.model.SystemValue = value
    with pytest.raises(RuntimeError, match="imported RodTipLen"):
        r24_tip.invoke()


def test_r24_5_point_59_exact_circle_containment_has_no_census_precision_allowance(r24_tip):
    case = r24_tip
    top = _end_xy(case.land.line[0][0], case.land.line[0][1])
    radius = math.dist(top, drawing.END_CENTER) - 1e-10
    case.crop = (drawing.END_CENTER[0] - radius, drawing.END_CENTER[1] - radius,
                 drawing.END_CENTER[0] + radius, drawing.END_CENTER[1] + radius)
    with pytest.raises(RuntimeError, match="endpoint 0 outside unchanged crop"):
        case.invoke()


@pytest.mark.parametrize("beyond", [False, True])
def test_r24_5_point_59_native_witness_start_must_leave_visible_crop_ink_without_new_minimum(r24_tip, beyond):
    case = r24_tip
    start = tuple(case.data.lines[0][4:6])
    radius = math.dist(start, drawing.END_CENTER) + (-1e-10 if beyond else 1e-10)
    case.crop = (drawing.END_CENTER[0] - radius, drawing.END_CENTER[1] - radius,
                 drawing.END_CENTER[0] + radius, drawing.END_CENTER[1] + radius)
    if beyond:
        with pytest.raises(RuntimeError, match="endpoint 0.*no visible native witness"):
            case.invoke()
    else:
        case.invoke()


@pytest.mark.parametrize("field", [3, 6, 7])
def test_r24_5_point_59_native_dimension_arrow_requires_a_visible_footprint(r24_tip, field):
    row = r24_tip.data.primitives["arrows"][0]
    row[field] = 0.0
    if field == 3:
        row[4] = 0.0
    with pytest.raises(RuntimeError, match="arrow footprint"):
        r24_tip.invoke()


@pytest.mark.parametrize("kind", [None, True, 2, 6])
def test_r24_5_point_59_specific_annotation_requires_the_native_dimension_owner(r24_tip, kind):
    r24_tip.annotation.kind = kind
    with pytest.raises(RuntimeError, match="not a native display dimension"):
        r24_tip.invoke()


class _R24DotAnnotation(_R24Annotation):
    def __init__(self, data, edge, landing):
        super().__init__("RodPosition", (*drawing.FCF_XY, 0.0), data, kind=5, attached=(edge,),
                         leaders=[[0.30357, 0.0966, 0.0, 0.30992, 0.0966, 0.0, *landing, 0.0]])
        self.style, self.side, self.smart, self.arrow = 2, 0, True, 1
        self.setter_status, self.arrow_status = 0, 0
        self.calls = []

    def SetLeader3(self, style, side, smart, perpendicular, all_around, dashed):
        self.calls.append(("SetLeader3", style, side, smart, perpendicular, all_around, dashed))
        self.style, self.side, self.smart = style, side, smart
        return self.setter_status

    def SetArrowHeadStyleAtIndex(self, index, style):
        self.calls.append(("SetArrowHeadStyleAtIndex", index, style))
        assert index == 0
        self.arrow = style
        self.data.primitives["arrows"][0][8] = style
        return self.arrow_status

    def GetArrowHeadStyleAtIndex(self, index):
        assert index == 0
        return self.arrow

    def GetArrowHeadCount(self):
        return 1

    def GetLeaderStyle(self):
        return self.style

    def GetLeaderSide(self):
        return self.side

    def GetSmartArrowHeadStyle(self):
        return self.smart

    def GetLeaderAllAround(self):
        return False

    def GetLeaderPerpendicular(self):
        return False

    def GetDashedLeader(self):
        return False


@pytest.fixture
def r24_dot(bound, monkeypatch):
    from _gtol_frame import gtol_frame_xml
    from _drawing_edges import ViewEdge, ViewEdges

    edge = object()
    landing = _end_xy(drawing.ROD_HOLE_X, drawing.ROD_HOLE_Y - drawing._ROD_HOLE_DIA / 2.0)
    data = _ClearanceDisplayData(
        [_r24_text("0.20", (0.272, 0.094), width=0.009)],
        [_native_line(0.262, 0.0931, 0.262, 0.1001), _native_line(0.262, 0.1001, 0.30357, 0.1001),
         _native_line(0.30357, 0.1001, 0.30357, 0.0931), _native_line(0.30357, 0.0931, 0.262, 0.0931)],
        primitives={"arrows": [[*landing, 0, 1, 0, 0, 0.001, 0.001, 1, 0, 0, 1]]},
    )
    ann = _R24DotAnnotation(data, edge, landing)
    state = SimpleNamespace(annotation=ann, data=data, edge=edge, landing=landing, events=[], xml=None)
    state.xml = gtol_frame_xml("position", "0.20", datums=("A", "B"), diameter=True)
    frame = _native("IGtolFrame", GetSymbolXml=lambda: state.xml)
    def get_frame(index):
        assert index == 1  # IGtol frames, unlike arrow heads, are one-based.
        return frame
    state.gtol = _native("IGtol", GetAnnotation=lambda: ann, GetFrame=get_frame, GetFrameCount=lambda: 1)
    state.adapter = SimpleNamespace(swApp=_APP, currentModel=_native("IModelDoc2", GraphicsRedraw2=lambda: state.events.append("redraw")))
    centre = _end_xy(drawing.ROD_HOLE_X, drawing.ROD_HOLE_Y)
    mark_data = _ClearanceDisplayData([], [_native_line(*centre, centre[0], centre[1] - 0.005)])
    mark = _R24Annotation("PrintedSouthArm", (*centre, 0), mark_data, kind=13)
    ghost = _R24Annotation("Ghost", (0.01, 0.01, 0), _ClearanceDisplayData([], []), kind=13)
    state.view = _native("IView", GetAnnotations=lambda: [ghost, mark], GetAnnotationCount=lambda: 2)
    state.mark_data = mark_data
    taper = ViewEdge(object(), ((drawing.ROD_TIP_X, drawing._ROD_TIP_Y, drawing.ARM_THICKNESS / 2.0),
                               (drawing.BOT_END_X, drawing._BOT_END_Y, drawing.ARM_THICKNESS / 2.0)), None, (object(), object()))
    state.taper = taper
    scan = ViewEdges("E taper", (taper,))
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_k: scan)
    monkeypatch.setattr(drawing, "_project", lambda _a, _v, points, **_k: [_end_xy(x * 1000, y * 1000) for x, y, _z in points])
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: state.events.append("rebuild"))
    return state


def test_r24_dot_official_order_int_status_style_entity_frame_arm_and_taper_readbacks(r24_dot):
    case = r24_dot
    signature = drawing._configure_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing)
    drawing._require_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing, signature)
    drawing._require_rod_dot_route(case.adapter, case.view, case.gtol, case.landing)
    assert case.annotation.calls == [
        ("SetLeader3", 2, 2, False, False, False, False),
        ("SetArrowHeadStyleAtIndex", 0, 3),
    ]
    assert case.events == ["redraw", "rebuild"]
    assert signature.datums == ("A", "B") and signature.tolerance == "0.2"
    assert case.annotation.attached == (case.edge,)
    assert case.annotation.position[:2] == drawing.FCF_XY
    with pytest.raises(RuntimeError, match="owner mismatch"):
        _bind_owner(case.gtol, "IAnnotation")


@pytest.mark.parametrize("setter,value", [
    ("setter_status", -2), ("setter_status", True), ("setter_status", None),
    ("arrow_status", -3), ("arrow_status", True), ("arrow_status", None),
])
def test_r26_dot_int_status_nonzero_or_unconvertible_still_refuses(r24_dot, setter, value):
    setattr(r24_dot.annotation, setter, value)
    with pytest.raises((RuntimeError, TypeError, ValueError)):
        drawing._configure_rod_position_dot(r24_dot.adapter, r24_dot.gtol, r24_dot.edge, r24_dot.landing)


@pytest.mark.parametrize("setter", ["setter_status", "arrow_status"])
@pytest.mark.parametrize("status", [0, 0.0, "0", False])
def test_r26_dot_status_conversion_matches_proven_gdt_int_convention(r24_dot, setter, status):
    setattr(r24_dot.annotation, setter, status)
    drawing._configure_rod_position_dot(r24_dot.adapter, r24_dot.gtol, r24_dot.edge, r24_dot.landing)


@pytest.mark.parametrize("failure", ["setter", "style", "route"])
@pytest.mark.parametrize("capture_mode", ["success", "different error", "telemetry error"])
def test_r26_dot_failure_records_actual_leader_side_style_and_preserves_refusal(
    r24_dot, monkeypatch, failure, capture_mode,
):
    case = r24_dot
    if failure == "setter":
        case.annotation.setter_status = -2
    else:
        signature = drawing._configure_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing)
        if failure == "style":
            case.annotation.side = 0
        else:
            case.mark_data.lines = []
    captures = []

    def capture(_adapter, _label, _message, **context):
        captures.append(context)
        if capture_mode != "success":
            raise OSError("DOT forensic capture refused")

    def warn(_message):
        if capture_mode == "telemetry error":
            raise RuntimeError("DOT telemetry refused")

    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(drawing._telemetry, "warn", warn)
    with pytest.raises(RuntimeError) as caught:
        try:
            if failure == "setter":
                drawing._configure_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing)
            elif failure == "style":
                drawing._require_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing, signature)
            else:
                drawing._require_rod_dot_route(case.adapter, case.view, case.gtol, case.landing)
        except Exception as exc:
            drawing._capture_layout_failure(case.adapter, "R24 native rod-pin DOT", exc)
            raise
    assert len(captures) == 1 and captures[0]["exception"] is caught.value
    context = captures[0]["rod_dot_native"]
    assert context["leader_points"] == case.annotation.leaders[0]
    assert context["leader_side"] == case.annotation.side
    assert context["leader_style"] == case.annotation.style
    assert context["arrow_style"] == case.annotation.arrow
    assert context["record"]["leaders"] == case.annotation.leaders
    case.annotation.leaders[0][0] += 0.001
    assert context["leader_points"] != case.annotation.leaders[0]


@pytest.mark.parametrize("member,value", [
    ("GetArrowHeadStyleAtIndex", 1), ("GetArrowHeadCount", 0), ("GetArrowHeadCount", True),
    ("GetLeaderCount", 2), ("GetLeaderStyle", 1), ("GetLeaderSide", 0),
    ("GetSmartArrowHeadStyle", True), ("GetLeaderAllAround", True),
    ("GetLeaderPerpendicular", True), ("GetDashedLeader", True),
    ("GetAttachedEntityCount3", True),
])
def test_r24_dot_each_native_leader_style_owner_readback_is_independently_required(r24_dot, member, value):
    case = r24_dot
    signature = drawing._configure_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing)
    setattr(case.annotation, member, lambda *_args: value)
    with pytest.raises(RuntimeError):
        drawing._require_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing, signature)


@pytest.mark.parametrize("defect", [
    "edge", "null-edge", "dangling", "wrong-type", "leader-truncated", "leader-nan",
    "landing", "display-style", "display-landing", "frame-datum-order", "frame-zone",
    "frame-position", "no-annotation", "no-frame",
])
def test_r24_dot_does_not_waive_entity_frame_display_or_landing_failures(r24_dot, defect):
    from _gtol_frame import gtol_frame_xml
    case = r24_dot
    signature = drawing._configure_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing)
    ann = case.annotation
    if defect == "edge":
        ann.attached = (object(),)
    elif defect == "null-edge":
        ann.attached = (None,)
    elif defect == "dangling":
        ann.dangling = True
    elif defect == "wrong-type":
        ann.GetAttachedEntityTypes = lambda: (True,)
    elif defect == "leader-truncated":
        ann.leaders[0] = [0.0] * 8
    elif defect == "leader-nan":
        ann.leaders[0][-3] = float("nan")
    elif defect == "landing":
        ann.leaders[0][-3] += 0.001
    elif defect == "display-style":
        case.data.primitives["arrows"][0][8] = 1
    elif defect == "display-landing":
        case.data.primitives["arrows"][0][0] += 0.001
    elif defect == "frame-datum-order":
        case.xml = gtol_frame_xml("position", "0.20", datums=("B", "A"), diameter=True)
    elif defect == "frame-zone":
        case.xml = gtol_frame_xml("position", "0.20", datums=("A", "B"), diameter=False)
    elif defect == "frame-position":
        ann.position = (0.265, 0.1, 0)
    elif defect == "no-annotation":
        case.gtol.GetAnnotation = lambda: None
    elif defect == "no-frame":
        case.gtol.GetFrame = lambda _index: None
    with pytest.raises(RuntimeError):
        drawing._require_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing, signature)


@pytest.mark.parametrize("defect", ["missing-arm", "false-arm", "cross-taper"])
def test_r24_dot_actual_printed_arm_and_taper_route_are_not_inferred_from_request(r24_dot, defect):
    case = r24_dot
    drawing._configure_rod_position_dot(case.adapter, case.gtol, case.edge, case.landing)
    if defect == "missing-arm":
        case.mark_data.lines = []
    elif defect == "false-arm":
        case.mark_data.lines[0][4] += 0.001
        case.mark_data.lines[0][7] += 0.001
    else:
        a, b = [_end_xy(x, y) for x, y, _z in case.taper.line]
        middle = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        case.annotation.leaders[0] = [
            middle[0] - 0.010, middle[1], 0,
            middle[0] + 0.010, middle[1], 0, *case.landing, 0,
        ]
    with pytest.raises(RuntimeError):
        drawing._require_rod_dot_route(case.adapter, case.view, case.gtol, case.landing)


def test_r24_caps_taper_and_land_locator_but_preserves_uncapped_overall(native_front):
    case = native_front
    front_annotations, display, entities, land, land_entities = drawing._add_rocker_outline_dimensions(case.adapter, object())
    assert front_annotations is case.basic_calls[0]
    assert display is case.displays["taper intersection X"]
    assert display.MaxWitnessLineLength == drawing.TAPER_WITNESS_LENGTH == 0.008
    assert display.annotation.GetAttachedEntities3() == entities
    assert land is case.displays["tip land X location"]
    assert land.MaxWitnessLineLength == drawing.TAPER_WITNESS_LENGTH
    assert land.annotation.GetAttachedEntities3() == land_entities
    assert not hasattr(case.displays["rocker overall width"], "MaxWitnessLineLength")


def _r26_native_radius_rows(name, *, inside=False):
    # Copied coordinate rows, NOT a recomputed exterior-style radius fixture.
    # R23: prechips/20261013T124514403Z.../layout-audit/ch-rocker-arm.json.
    # Inside R800: prechips/20261011T220808877Z... from the a8dcea067 failure.
    if inside:
        assert name == "TopRadius"
        position = (0.130, 0.218, 5e-5)
        segments = [
            (0.1204048, 0.2152219, 0.1204048, 0.2207781),
            (0.1204048, 0.2207781, 0.1395952, 0.2207781),
            (0.1395952, 0.2207781, 0.1395952, 0.2152219),
            (0.1395952, 0.2152219, 0.1204048, 0.2152219),
            (0.180, 0.5756763, 0.1303884, 0.2207781),
            (0.124622, 0.1795283, 0.1296116, 0.2152219),
            (0.124622, 0.1795283, 0.1237429, 0.1732394),
        ]
        arrow = [0.124622, 0.1795283, 5e-5, -0.138445, -0.9903701, 0.0,
                 0.003556, 0.000762, 0.0, 0.0, -0.0, -1.0]
        text_position = (0.1214712, 0.2152219, 5e-5)
    elif name == "TopRadius":
        position = (0.145, 0.136, 5e-5)
        segments = [
            (0.1354048, 0.1332219, 0.1354048, 0.1387781),
            (0.1354048, 0.1387781, 0.1545952, 0.1387781),
            (0.1545952, 0.1387781, 0.1545952, 0.1332219),
            (0.1545952, 0.1332219, 0.1354048, 0.1332219),
            (0.1588691, 0.1762349, 0.1565382, 0.1321734),
            (0.1565382, 0.1321734, 0.1350493, 0.1321734),
        ]
        arrow = [0.1588691, 0.1762349, 5e-5, -0.0528273, -0.9986037, 0.0,
                 0.003556, 0.000762, 0.0, 0.0, -0.0, -1.0]
        text_position = (0.1364712, 0.1332219, 5e-5)
    else:
        assert name == "BottomRadius"
        position = (0.169, 0.128, 5e-5)
        segments = [
            (0.1594048, 0.1252219, 0.1594048, 0.1307781),
            (0.1594048, 0.1307781, 0.1785952, 0.1307781),
            (0.1785952, 0.1307781, 0.1785952, 0.1252219),
            (0.1785952, 0.1252219, 0.1594048, 0.1252219),
            (0.1804863, 0.1676766, 0.1805382, 0.1241734),
            (0.1805382, 0.1241734, 0.1590493, 0.1241734),
        ]
        arrow = [0.1804863, 0.1676766, 5e-5, 0.001192, -0.9999993, 0.0,
                 0.003556, 0.000762, 0.0, 0.0, -0.0, -1.0]
        text_position = (0.1604712, 0.1252219, 5e-5)
    lines = [[0.0, 0.0, 0.0, 0.0, x0, y0, 5e-5, x1, y1, 5e-5]
             for x0, y0, x1, y1 in segments]
    text = {"t": "R800.00" if name == "TopRadius" else "R816.00",
            "pos": list(text_position), "h": 0.0035, "ref": 1, "ang": 0.0,
            "font": "Century Gothic", "ls": 0.001, "w": 0.0170576}
    return position, _ClearanceDisplayData([text], lines, primitives={"arrows": [arrow]})


@pytest.fixture
def r24_radii(bound, monkeypatch):
    """Actual R23 native pair for the restored legacy exterior guard."""
    annotations = {}
    for name in ("TopRadius", "BottomRadius"):
        position, data = _r26_native_radius_rows(name)
        ann = _R24Annotation(name, position, data)
        ann.display = _native("IDisplayDimension", GetAnnotation=lambda ann=ann: ann, IsHoleCallout=lambda: False)
        annotations[name] = ann
    case = SimpleNamespace(annotations=annotations, adapter=SimpleNamespace(swApp=_APP), logs=[])
    case.view = _native("IView", GetAnnotations=lambda: list(annotations.values()),
                        GetAnnotationCount=lambda: len(annotations))
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, ann: _bind_owner(ann, "IAnnotation").name)
    monkeypatch.setattr(drawing._telemetry, "info", case.logs.append)
    monkeypatch.setattr(drawing, "_project", lambda _a, _v, points, **_k: [_front_xy(x * 1000, y * 1000) for x, y, _z in points])
    return case


def test_r26_actual_r23_radius_pair_passes_restored_exterior_guard_and_has_no_crossing(r24_radii):
    case = r24_radii
    # These rows are R23's ink for its (0.145, 0.136)/(0.169, 0.128) requests:
    # a replay of the guard and crossing checks, NOT evidence for the MR #1020
    # requests below the strap's left half, which only a native render proves
    # (the same guard runs live after the final rebuild).
    assert case.annotations["TopRadius"].position[:2] == (0.145, 0.136)
    assert case.annotations["BottomRadius"].position[:2] == (0.169, 0.128)
    assert drawing.FRONT_KEEP["TopRadius"] != (0.145, 0.136)
    assert drawing.FRONT_KEEP["BottomRadius"] != (0.169, 0.128)
    drawing._require_radius_exterior(case.adapter, case.view)
    top, top_geometry = drawing._r24_record(case.adapter, case.annotations["TopRadius"], label="actual R23 R800")
    bottom, bottom_geometry = drawing._r24_record(case.adapter, case.annotations["BottomRadius"], label="actual R23 R816")
    routes = []
    for record, geometry in ((top, top_geometry), (bottom, bottom_geometry)):
        rows = record["display"]["lines"]
        frame = [Segment(row[4], row[5], row[7], row[8]) for row in rows[:4]]
        assert len(frame) == 4
        assert all(s.length > 0.0 and (s.x0 == s.x1 or s.y0 == s.y1) for s in frame)
        assert len({(s.x0, s.y0) for s in frame}) == 4
        assert all((s.x1, s.y1) == (next_s.x0, next_s.y0)
                   for s, next_s in zip(frame, frame[1:] + frame[:1], strict=True))
        box = drawing.union_boxes([s.box() for s in frame])
        assert box is not None and geometry.text_boxes
        assert all(box.xmin <= text.xmin <= text.xmax <= box.xmax
                   and box.ymin <= text.ymin <= text.ymax <= box.ymax
                   for text in geometry.text_boxes)
        route = [Segment(row[4], row[5], row[7], row[8]) for row in rows[4:]]
        assert len(route) == 2
        assert (route[0].x1, route[0].y1) == (route[1].x0, route[1].y0)
        routes.append(route)
    top_route, bottom_route = routes
    drawing._r24_no_crossings(top_route, bottom_geometry.segments, label="actual R23 Top/Bottom pair")
    drawing._r24_no_crossings(bottom_route, top_geometry.segments, label="actual R23 Bottom/Top pair")
    for route, geometry in ((top_route, bottom_geometry), (bottom_route, top_geometry)):
        assert all(drawing.text_overlap(segment, geometry, box)[0] == 0.0
                   for segment in route for box in geometry.text_boxes)


def test_r26_actual_inside_r800_tail_and_strap_extension_refuse_restored_legacy_exterior_guard(r24_radii):
    case = r24_radii
    ann = case.annotations["TopRadius"]
    ann.position, ann.data = _r26_native_radius_rows("TopRadius", inside=True)
    assert ann.data.lines[4][4:6] == [0.180, 0.5756763]
    assert len(ann.data.lines) == 7  # Actual centre tail AND arrow/strap extension.
    with pytest.raises(RuntimeError, match="TopRadius:.*actual_exterior_air_mm"):
        drawing._require_radius_exterior(case.adapter, case.view)


@pytest.fixture
def r24_taper(native_front, bound, monkeypatch):
    case = native_front
    _front_annotations, taper, entities, _land_dimension, _land_entities = drawing._add_rocker_outline_dimensions(case.adapter, object())
    data = _ClearanceDisplayData(
        [_r24_text("132.76", (0.2118882, 0.132), width=0.0142236),
         _r24_text("R816/TAPER", (0.2059139, 0.1264437), width=0.0261722)],
        [_native_line(0.18, 0.1334438, 0.18, 0.1254438),
         _native_line(0.2463786, 0.1334438, 0.2463786, 0.1254438),
         _native_line(0.18, 0.1264438, 0.2463786, 0.1264438),
         # BASIC frame around 132.76: its sides are vertical, short, arrowless.
         _native_line(0.2108882, 0.131, 0.2108882, 0.1365),
         _native_line(0.2271118, 0.131, 0.2271118, 0.1365),
         _native_line(0.2108882, 0.131, 0.2271118, 0.131),
         _native_line(0.2108882, 0.1365, 0.2271118, 0.1365)],
        primitives={"arrows": [
            [0.18, 0.1264438, 0.0002, -1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1],
            [0.2463786, 0.1264438, 0.0002, 1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1],
        ]},
    )
    ann = taper.annotation
    ann.GetType = lambda: 4
    ann.GetPosition = lambda: (0.219, 0.132, 0)
    ann.GetDisplayData = lambda: data
    ann.GetLeaderCount = lambda: 0
    ann.OwnerType, ann.Visible = 0, 1
    state = SimpleNamespace(adapter=case.adapter, taper=taper, entities=entities, data=data,
                            parent_centre=(0.249753, 0.1777179), parent_radius=0.0059595)
    monkeypatch.setattr(drawing, "read_circular_detail_crop",
                        lambda *_a, **_k: SimpleNamespace(parent_centre=state.parent_centre, parent_radius=state.parent_radius))
    return state


def test_r24_taper_native_capped_witnesses_clear_parent_e_without_changing_measurement(r24_taper):
    case = r24_taper
    drawing._require_taper_witnesses(case.adapter, object(), case.taper, case.entities)
    assert case.taper.model.SystemValue == pytest.approx(drawing.BOT_END_X / 1000.0)
    assert case.taper.annotation.GetAttachedEntities3() == case.entities


def test_r24_taper_box_sides_are_not_witnesses(r24_taper):
    # r1/r2 farm: the then-BASIC box's two vertical sides were counted as witnesses.
    case = r24_taper
    _record, geometry = drawing._r24_record(case.adapter, case.taper.GetAnnotation(), label="t")
    value = geometry.text_boxes[0]
    x0, y0, x1, y1 = value.xmin - 0.0005, value.ymin - 0.0005, value.xmax + 0.0005, value.ymax + 0.0005
    case.data.lines.extend([
        _native_line(x0, y0, x1, y0), _native_line(x1, y0, x1, y1),
        _native_line(x1, y1, x0, y1), _native_line(x0, y1, x0, y0),
    ])
    drawing._require_taper_witnesses(case.adapter, object(), case.taper, case.entities)
    # A frame cannot stand in for a missing witness.
    case.data.lines.pop(1)
    with pytest.raises(RuntimeError, match="witness pair"):
        drawing._require_taper_witnesses(case.adapter, object(), case.taper, case.entities)


@pytest.mark.parametrize("defect", ["property", "nan-property", "long-ink", "cross-parent-circle", "wrong-nominal",
                                    "wrong-vertex", "missing-witness", "missing-arrow", "one-witness-two-arrows"])
def test_r24_taper_native_ink_parent_circle_and_original_measurement_all_govern(r24_taper, defect):
    case = r24_taper
    if defect == "property":
        case.taper.MaxWitnessLineLength = 0.010
    elif defect == "nan-property":
        case.taper.MaxWitnessLineLength = math.nan
    elif defect == "long-ink":
        case.data.lines[1][5] = 0.1721122
    elif defect == "cross-parent-circle":
        case.data.lines[1] = _native_line(0.2463786, 0.1817179, 0.2463786, 0.1737179)
        case.data.primitives["arrows"][1][1] = 0.1777179
    elif defect == "wrong-nominal":
        case.taper.model.SystemValue += 0.0001
    elif defect == "wrong-vertex":
        case.taper.attached = (case.entities[0], object())
    elif defect == "missing-witness":
        case.data.lines.pop(1)
    elif defect == "missing-arrow":
        case.data.primitives["arrows"].pop(1)
    elif defect == "one-witness-two-arrows":
        case.data.primitives["arrows"][1][:2] = [0.18, 0.1294438]
    message = "parent E circle" if defect == "cross-parent-circle" else None
    with pytest.raises(RuntimeError, match=message):
        drawing._require_taper_witnesses(case.adapter, object(), case.taper, case.entities)


@pytest.mark.parametrize("count", [0, 2, True, None])
def test_r24_dot_frame_census_cannot_hide_an_extra_or_missing_tolerance_frame(r24_dot, count):
    r24_dot.gtol.GetFrameCount = lambda: count
    with pytest.raises(RuntimeError, match="one unchanged native frame"):
        drawing._configure_rod_position_dot(r24_dot.adapter, r24_dot.gtol, r24_dot.edge, r24_dot.landing)


def test_r24_raw_text_metrics_are_unrounded_and_zero_table_width_remains_an_estimate(r24_tip):
    case = r24_tip
    case.data.texts[0]["pos"][0] += 3e-8
    case.data.texts[0]["w"] = 0.0
    record, _geometry = drawing._r24_record(case.adapter, case.annotation, label="native text metrics")
    assert record["display"]["texts"][0]["pos"] == case.data.texts[0]["pos"]
    assert "w" not in record["display"]["texts"][0]


@pytest.fixture
def r24_final_layout(r24_tip, r24_taper, monkeypatch):
    """Reprove only the remaining native 5.59, datum C, strap and taper contracts."""
    tip, taper = r24_tip, r24_taper
    # native_front (via r24_taper) installs a front-view projection. Bind the
    # combined fixture's actual E projection/crop BEFORE its initial witness
    # readback, not only before the final predicate.
    monkeypatch.setattr(drawing, "_project", lambda _a, _v, points, **_k: [_end_xy(x * 1000, y * 1000) for x, y, _z in points])
    monkeypatch.setattr(drawing, "_detail_crop", lambda *_a, **_k: tip.crop)
    rod_tip_attached = tip.invoke()
    # Option 4: E's one datum tag is C, hung under the rod-pin frame.
    tag_x, tag_y = drawing.ROD_DATUM_C_XY
    datum = _R24Annotation("C", (tag_x, tag_y, 0),
                           _ClearanceDisplayData([_r24_text("C", (tag_x - 0.0017, tag_y + 0.0007), width=0.0035)],
                                                 [_native_line(tag_x, tag_y + 0.007, tag_x, tag_y + 0.012)]), kind=2)
    datum.display = _native("IDatumTag", GetLabel=lambda: "C")
    state = SimpleNamespace(adapter=taper.adapter, tip=tip, taper=taper,
                            rod_tip_attached=rod_tip_attached, datum=datum)
    # Actual R23 2.500 text metrics; no fictitious 18 mm thickness neighbour.
    thickness = _R24Annotation("StrapThickness", (0.317, 0.175, 0.1461546),
                               _ClearanceDisplayData(
                                   [_r24_text(" 2.500 ±0.025 ", (0.302142, 0.1722219), width=0.029716)], []))
    state.end_annotations = [tip.annotation, datum]
    state.end = _native("IView", GetAnnotations=lambda: state.end_annotations,
                        GetAnnotationCount=lambda: len(state.end_annotations))
    state.right_annotations = [thickness]
    state.right = _native("IView", GetAnnotations=lambda: state.right_annotations,
                          GetAnnotationCount=lambda: len(state.right_annotations))
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, ann: _bind_owner(ann, "IAnnotation").name)
    state.invoke = lambda: drawing._require_r24_detail_layout(
        state.adapter, state.end, state.right, taper.taper, taper.entities, tip.land,
        rod_tip_attached,
    )
    return state


def test_r24_final_native_layout_rechecks_5_point_59_c_strap_and_taper(r24_final_layout):
    r24_final_layout.invoke()


@pytest.mark.parametrize("gaps,use_doc", [
    ((0.001, 0.001), (False, False)),
    ((0.0015, 0.0015), (False, False)),
    ((0.001, 0.0015), (True, False)),
])
def test_r24_final_native_layout_accepts_legitimate_effective_gap_regeneration(r24_final_layout, gaps, use_doc):
    case = r24_final_layout
    _r24_tip_effective_gaps(case.tip, gaps, use_doc)
    case.invoke()


@pytest.mark.parametrize("defect", [
    "attachment", "nominal", "missing-c", "missing-tip", "missing-thickness",
    "witness-gap-mismatch", "wrong-letter", "second-tag",
])
def test_r24_final_native_regeneration_cannot_bypass_approved_local_guards(r24_final_layout, defect):
    case = r24_final_layout
    if defect == "attachment":
        case.tip.annotation.attached = (case.rod_tip_attached[0], object())
    elif defect == "nominal":
        case.tip.model.SystemValue += 0.001
    elif defect == "missing-thickness":
        case.right_annotations.clear()
    elif defect == "missing-c":
        case.end_annotations[:] = [ann for ann in case.end_annotations if ann.GetType() != 2]
    elif defect == "wrong-letter":
        case.datum.display = _native("IDatumTag", GetLabel=lambda: "D")
    elif defect == "second-tag":
        case.end_annotations.append(case.datum)
    elif defect == "missing-tip":
        case.end_annotations.remove(case.tip.annotation)
    elif defect == "witness-gap-mismatch":
        case.tip.gaps[1] = 0.002  # Readback moves; actual 1mm native line start does not.
    match = "disagree with effective gap readback" if defect == "witness-gap-mismatch" else None
    with pytest.raises(RuntimeError, match=match):
        case.invoke()


@pytest.mark.parametrize("field,value", [
    ("w", math.nan), ("w", -0.001), ("w", True),
    ("ang", math.inf), ("ang", True), ("ref", True), ("ref", 6),
])
def test_r24_raw_native_text_metric_scalar_types_refuse_before_using_the_dump(r24_tip, field, value):
    r24_tip.data.texts[0][field] = value
    with pytest.raises(RuntimeError, match="native text scalar"):
        drawing._r24_record(r24_tip.adapter, r24_tip.annotation, label="native text metrics")


def test_r24_final_attachment_reproof_does_not_require_unproven_annotation_is_same(r24_final_layout):
    case = r24_final_layout
    original = case.adapter.swApp.IsSame
    calls = []
    def same_geometry(a, b):
        assert "IAnnotation" not in getattr(a, "_native_interfaces", ())
        assert "IAnnotation" not in getattr(b, "_native_interfaces", ())
        calls.append((a, b))
        return original(a, b)
    case.adapter.swApp = SimpleNamespace(IsSame=same_geometry)
    case.invoke()
    assert calls


def test_r24_actual_visible_5_point_59_witness_does_not_add_an_unapproved_one_mm_minimum(r24_tip):
    case = r24_tip
    start = tuple(case.data.lines[0][4:6])
    radius = math.dist(start, drawing.END_CENTER) + 0.0001
    case.crop = (drawing.END_CENTER[0] - radius, drawing.END_CENTER[1] - radius,
                 drawing.END_CENTER[0] + radius, drawing.END_CENTER[1] + radius)
    case.invoke()
    row = case.data.lines[0]
    witness = Segment(row[4], row[5], row[7], row[8])
    span = drawing.clip_segment_to_circle(witness, (*drawing.END_CENTER, radius))
    assert span is not None
    assert 0.0 < witness.length * (span[1] - span[0]) < 0.001


def test_r24_taper_parent_circle_clearance_is_nonintersection_not_a_new_one_mm_threshold(r24_taper):
    case = r24_taper
    case.parent_centre = (0.2463786 + case.parent_radius + 0.0005, 0.1294438)
    drawing._require_taper_witnesses(case.adapter, object(), case.taper, case.entities)


def test_least_tip_land_is_the_basic_land_shortened_by_the_taper_tilted_into_the_zone():
    # Independent of the vertex search: the land stays on its basic line and
    # the top arc on its basic radius; the taper keeps its bottom end and
    # swings its foot the whole zone into the material, so the land ends
    # where that tilted taper crosses it.
    top, tip, bottom = drawing._TOP, drawing._TIP, drawing._BOTTOM
    zone = ch_rocker_arm_spec.TOP_EDGE_BAND[0]
    tx, ty = bottom[0] - tip[0], bottom[1] - tip[1]
    length = math.hypot(tx, ty)
    normal = (-ty / length, tx / length)
    interior = ((top[0] + bottom[0]) / 2.0, (top[1] + bottom[1]) / 2.0)
    if (interior[0] - tip[0]) * normal[0] + (interior[1] - tip[1]) * normal[1] < 0.0:
        normal = (-normal[0], -normal[1])
    foot = (tip[0] + zone * normal[0], tip[1] + zone * normal[1])
    ux, uy = tip[0] - top[0], tip[1] - top[1]
    ex, ey = bottom[0] - foot[0], bottom[1] - foot[1]
    s = ((foot[0] - top[0]) * ey - (foot[1] - top[1]) * ex) / (ux * ey - uy * ex)
    tilted = s * math.hypot(ux, uy)
    assert drawing._least_tip_land_mm() == pytest.approx(tilted, abs=1e-9)
    assert drawing.TIP_LAND_LEAST_MM == 4.969
    assert 0.0 < drawing.TIP_LAND_LEAST_MM <= drawing._least_tip_land_mm()
    # A parallel shift of the taper (zone / sin of the land-taper angle) is
    # milder than the tilt; the land never lengthens past its basic as worst.
    cos_angle = abs(ux * tx + uy * ty) / (math.hypot(ux, uy) * length)
    parallel = ch_rocker_arm_spec.TIP_FACE - zone / math.sqrt(1.0 - cos_angle**2)
    assert drawing.TIP_LAND_LEAST_MM < parallel < ch_rocker_arm_spec.TIP_FACE


def test_curve_quality_is_precise_before_any_view() -> None:
    # Machinist review r1 (#2108 batch B): detail D's small circles printed
    # as polygons at the drawing's default curve resolution.
    build = next(
        node
        for node in ast.parse(Path(drawing.__file__).read_text(encoding="utf-8")).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [
        node.func.id
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    lines = {
        name: min(
            node.lineno
            for node in ast.walk(build)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        )
        for name in ("set_precise_curve_quality", "place_view")
    }
    assert calls.count("set_precise_curve_quality") == 1
    assert lines["set_precise_curve_quality"] < lines["place_view"]
