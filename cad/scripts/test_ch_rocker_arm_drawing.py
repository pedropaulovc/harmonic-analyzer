"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ch_rocker_arm_notes
import ch_rocker_arm_spec
import draw_ch_rocker_arm as drawing
import build_ch_rocker_arm as arm
from _drawing_layout_check import DrawableRegion
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_installation import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


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
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        ch_rocker_arm_spec.ROD_HOLE_X,
        ch_rocker_arm_spec.TOP_END_Y,
    )
    assert ch_rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert ch_rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert ch_rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert ch_rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert ch_rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert ch_rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert ch_rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    assert arm.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(ch_rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        ch_rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(ch_rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert ch_rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert ch_rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = ch_rocker_arm_notes.DRAWING_NOTES
    # Concentricity applies to nominal arcs, not independent profile deviations.
    assert "NOMINAL ARCS CONCENTRIC ON MIRROR AXIS." in notes
    assert "R800" not in notes
    assert "R816" not in notes
    # Processes and through conditions belong to the native size callouts.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "PIVOT HOLE: REAM" not in notes
    assert "16.00 REF" not in notes
    assert "ALL HOLES THRU" not in notes
    # Profile nominals print once, as native BASIC dimensions, not as prose.
    assert "808.00 REF FROM THE PIVOT" not in notes
    assert "INTEGRAL HUB DIA" not in notes
    assert "HUB LENGTH SETS THE PITCH" in " ".join(notes.split())
    assert "ARC LENGTHS" not in notes
    assert "EACH END:" not in notes
    assert re.findall(r"^(\d+)\.", notes, re.MULTILINE) == ["1", "2", "3", "4"]
    assert "UPPER ARC: AMPLITUDE-BAR CONTACT." in notes
    assert "LOWER ARC: MOVING STRAP ENVELOPE." in notes
    assert "ROD-PIN SETS CONNECTING-ROD GEOMETRY." in notes
    assert (
        "HUB OD COAXIAL WITH PIVOT BORE WITHIN Ø0.50 (TURN HUB AND REAM BORE IN ONE SETUP)"
        in " ".join(line.strip() for line in notes.splitlines())
    )
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert not re.search(r"\b(?:\d+\s*)?BA\b", notes)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert re.search(
        r'add_property_linked_note\(\s*adapter, "Manufacturing Notes"', source
    )


def test_native_gdt_and_finish_present() -> None:
    """Native print arguments retain the part-owned limit and A-B-C frame."""
    from _drawing_hole_callout import add_native_hole_callout

    assert drawing.add_native_hole_callout is add_native_hole_callout
    assert drawing.ROD_HOLE.fields["dia"][1] == (
        "ROD_HOLE_SPEC",
        ("_hole_spec", "NUMBER_DRILL_MM"),
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), C = rod-side tip
    # face; the rod-pin position frame references all three.
    assert source.count("add_datum_feature(") == 3
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
    assert printed_datums == ("A", "B", "C")
    printed_tolerance = eval(
        compile(ast.Expression(keywords["tolerance"]), drawing.__file__, "eval"),
        vars(drawing),
    )
    assert (
        printed_tolerance
        == ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"]
    )
    assert drawing.ROD_HOLE.fields["position_dia"][0] == float(printed_tolerance)
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
        drawing._PIVOT_MID_Y + drawing.TOP_EDGE_ABOVE_PIVOT + drawing.R_TOP
    )
    centre = drawing._sheet_xy(0.0, centre_model_y)
    for name, radius in (
        ("TopRadius", drawing.R_TOP),
        ("BottomRadius", drawing.R_BOTTOM),
    ):
        rendered_radius = math.dist(
            centre, drawing._sheet_xy(0.0, centre_model_y + radius)
        )
        assert math.dist(centre, drawing.FRONT_KEEP[name]) > rendered_radius
    # Negative control: the former top label lay inside the same nominal circle.
    top_rendered_radius = math.dist(
        centre, drawing._sheet_xy(0.0, centre_model_y + drawing.R_TOP)
    )
    assert math.dist(centre, (0.130, 0.218)) < top_rendered_radius


def test_top_radius_text_uses_corridor_right_of_pivot_finish() -> None:
    """Keep the R800 leader right of the existing pivot-bore finish text."""
    pivot_x, _pivot_y = drawing._sheet_xy(0.0, drawing._PIVOT_MID_Y)
    corridor_left = pivot_x + 0.050  # sheet placement clearance, not a tolerance
    assert drawing.FRONT_KEEP["TopRadius"][0] > corridor_left
    # Negative control: the first outside-circle placement crossed Ra 1.6.
    assert 0.215 <= corridor_left


class _ProfileDisplay:
    """Model COM property writes, including silently ignored setters."""

    def __init__(self, ignored: str | None = None) -> None:
        self.ignored = ignored
        self.writes: list[tuple[str, object]] = []
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


def _profile_annotations(monkeypatch: pytest.MonkeyPatch, displays: dict) -> list:
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    return [
        SimpleNamespace(name=name, GetSpecificAnnotation=lambda display=display: display)
        for name, display in displays.items()
    ]


def test_basic_profile_dimensions_converts_all_three_and_trims_only_radius_leaders(
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
    for name in ("TopRadius", "BottomRadius"):
        assert displays[name].writes == [
            ("ShortenedRadius", False),
            ("ArcExtensionLineOrOppositeSide", False),
            ("ArrowSide", 1),
            ("SolidLeader", False),
        ]
        assert displays[name].ShortenedRadius is False
        assert displays[name].ArcExtensionLineOrOppositeSide is False
        assert displays[name].ArrowSide == 1
        assert displays[name].SolidLeader is False
    assert displays["TopAbovePivot"].writes == []
    assert displays["PivotDia"].writes == []


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
@pytest.mark.parametrize("ignored", [
    "ShortenedRadius", "ArcExtensionLineOrOppositeSide", "ArrowSide", "SolidLeader",
])
def test_basic_profile_dimensions_rejects_ignored_radius_flags(
    bound: None, monkeypatch: pytest.MonkeyPatch, radius: str, ignored: str,
) -> None:
    displays = {
        name: _ProfileDisplay(ignored if name == radius else None)
        for name in ("TopRadius", "BottomRadius", "TopAbovePivot")
    }
    annotations = _profile_annotations(monkeypatch, displays)
    monkeypatch.setattr(drawing, "set_basic_dimension", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match=f"{radius} retained its centre-directed radius leader"):
        drawing._basic_profile_dimensions(object(), annotations)


def test_arc_profiles_attach_two_native_frames_to_nominal_circle_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, front = object(), object()
    edges = {1600.0: object(), 1632.0: object()}
    picks, frames = [], []

    def circle_edge(actual_adapter, actual_view, diameter):
        assert actual_adapter is adapter
        assert actual_view is front
        picks.append(diameter)
        return edges[diameter]

    monkeypatch.setattr(drawing, "visible_circle_edge", circle_edge)
    monkeypatch.setattr(
        drawing, "add_feature_control_frame",
        lambda *args, **kwargs: frames.append((args, kwargs)),
    )
    drawing._add_arc_profiles(adapter, front)
    assert picks == [1600.0, 1632.0]
    assert len(frames) == 2
    scale = drawing._S / 1000.0
    for (args, kwargs), name, radius, model_x, frame_xy, outside in zip(
        frames,
        ("TopRadius", "BottomRadius"),
        (800.0, 816.0),
        (-110.0, -100.0),
        ((0.114, 0.228), (0.040, 0.105)),
        ("0.5", "0"),
    ):
        assert args == (adapter, front)
        assert kwargs["edge_entity"] is edges[2.0 * radius]
        assert kwargs["characteristic"] == "profile_surface"
        assert kwargs["tolerance"] == "0.5"
        assert kwargs["outside_disposition"] == outside
        assert kwargs["datums"] == ("A", "B", "C")
        assert not kwargs.get("diameter", False)
        assert not kwargs.get("all_around", False)
        assert "edge_xy" not in kwargs
        assert kwargs["label"] == f"arc-system {name} profile"
        assert kwargs["frame_xy"] == frame_xy
        sheet_x, sheet_y = kwargs["leader_attach_xy"]
        x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
        y = (sheet_y - drawing.FRONT_CENTER[1]) / scale + drawing._BBOX_CY
        assert x == pytest.approx(model_x)
        assert y < ch_rocker_arm_spec.CENTER_Y
        assert math.hypot(x, y - ch_rocker_arm_spec.CENTER_Y) == pytest.approx(radius)


def test_lower_profile_leader_clears_native_ream_callout_corridor() -> None:
    # R6 native ink: the REAM pivot row spans x104.0..156.1 at y144.4..148.0.
    # The native frame leader starts 6.4mm left and 3.5mm below its placement.
    frame = drawing.ARC_PROFILE_FRAME_XY["BottomRadius"]
    start = (frame[0] - 0.0064, frame[1] - 0.0035)
    end = drawing._arc_profile_point("BottomRadius")
    for y in (0.1444, 0.1480):
        fraction = (y - start[1]) / (end[1] - start[1])
        x = start[0] + fraction * (end[0] - start[0])
        assert x < 0.1040 - 0.0017


def test_profile_zone_mirror_station_envelopes_and_template_aim() -> None:
    """Only at the mirror station is the arc normal vertical. These limits
    do not assert a rigid vertical offset of the curve at its ends."""
    centre = ch_rocker_arm_spec.CENTER_Y
    assert (ch_rocker_arm_spec.R_TOP, ch_rocker_arm_spec.R_BOTTOM) == (800.0, 816.0)
    nominal_top = centre - ch_rocker_arm_spec.R_TOP - ch_rocker_arm_spec.PIVOT_MID_Y
    nominal_bottom = centre - ch_rocker_arm_spec.R_BOTTOM
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
    assert zone == top_outside == bottom_inside == 0.5
    assert (nominal_top, nominal_top + top_outside) == pytest.approx((8.0, 8.5))
    assert (nominal_bottom, nominal_bottom + bottom_inside) == pytest.approx((0.0, 0.5))
    template_aim = nominal_top + zone / 2.0
    assert template_aim == pytest.approx(8.25)
    # The template's own ±0.03 inspection band is not the part's total zone.
    assert (template_aim - 0.03, template_aim + 0.03) == pytest.approx((8.22, 8.28))



def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-rocker-arm")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
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
        ("TOP_KEEP", "top"),
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
    assert ch_rocker_arm_spec.HUB_LENGTH_BAND == (0.05, 0.0)
    assert f"{ch_rocker_arm_spec.HUB_LENGTH:.2f}" not in ch_rocker_arm_notes.DRAWING_NOTES


def test_strap_thickness_prints_its_band_natively() -> None:
    """Main ruling 2026-10, option b: each inter-arm gap holds one tine of
    each neighbouring rod fork, so the strap prints 2.500 +/-0.025 at three
    places on the Strap extrude's own depth (drawing-simplicity-policy.md `How the repository implements the guidelines`), selected by
    feature and dimension name in the end view, and no note repeats it."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_spec.ARM_THICKNESS_BAND == (0.025, -0.025)
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


def test_strap_thickness_text_clears_datum_b_the_frame_and_the_iso_caption() -> None:
    x, y = drawing.STRAP_THICKNESS_TEXT_XY
    # Right of the end view's strap and its hub (1:1).
    assert x - drawing.RIGHT_CENTER[0] > ch_rocker_arm_spec.HUB_LENGTH / 2000.0 + 0.010
    # Its line runs above datum B's attachment on the broad face ...
    datum_b_y = drawing.RIGHT_CENTER[1] + (
        ch_rocker_arm_spec.ARM_DEPTH - 1.0 - drawing._PIVOT_MID_Y
    ) / 1000.0
    assert y >= datum_b_y + 0.003
    # ... and inside the strap's height above the hub, so it crosses no hub line.
    view_top = drawing.RIGHT_CENTER[1] + ch_rocker_arm_spec.TOP_END_Y / 2000.0
    assert y < view_top
    # Under the iso caption and the rod-pin frame.
    assert y < drawing.ISO_CAPTION_XY[1] - 0.006
    assert y < drawing.FCF_XY[1] - 0.007 - 0.010


def test_top_edge_model_band_is_unchanged_by_the_basic_drawing_override() -> None:
    """The source keeps its existing height band and centre equation; the
    drawing's imported height is BASIC and governed by surface profile."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = ch_rocker_arm_spec.TOP_EDGE_BAND
    assert lower == 0.0 < upper == 0.50
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
    assert ch_rocker_arm_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"] == 2


def test_pivot_bore_ream_band_rides_its_diameter_not_a_note() -> None:
    """Codex #936 sweep (drawing-guidelines.md rule 3 (decimal places carry the tolerance)): note 6 printed "REAM +0.03/0, Ra
    1.6" while the O6.50 printed bare. The band is now native on PivotDia and
    the Ra is the bore's own symbol; the note keeps only REAM."""
    from _drawing_contract import model_toleranced_dimensions

    assert model_toleranced_dimensions(arm)[("PivotHoleProfile", "PivotDia")] == (
        "*deviations(PIVOT_HOLE_BAND)"
    )
    assert "PivotDia" in drawing.FRONT_KEEP
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


def test_top_edge_height_text_stands_clear_above_the_strap() -> None:
    """The dimension runs up the mirror axis from the pivot centre; its text
    sits over the strap, right of datum A's box and left of the rod-pin
    frame."""
    pivot = drawing._sheet_xy(0.0, ch_rocker_arm_spec.PIVOT_MID_Y)
    edge = drawing._sheet_xy(
        0.0, ch_rocker_arm_spec.PIVOT_MID_Y + ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT
    )
    text = drawing.FRONT_KEEP["TopAbovePivot"]
    assert text[0] == pytest.approx(pivot[0])
    assert text[1] > edge[1] + 0.005
    datum_a = drawing._pivot_datum_request(pivot)
    assert datum_a[0] < text[0] - 0.012
    assert text[0] + 0.012 < drawing.FCF_XY[0]


_PIVOT_CENTRE = drawing._sheet_xy(0.0, ch_rocker_arm_spec.PIVOT_MID_Y)


class _Tag:
    def __init__(self, attached: tuple, dangling: bool = False) -> None:
        self.annotation = SimpleNamespace(
            GetAttachedEntities3=lambda: attached,
            IsDangling=lambda: dangling,
        )

    def GetAnnotation(self) -> SimpleNamespace:
        return self.annotation


_BORE, _HUB = object(), object()
_APP = SimpleNamespace(IsSame=lambda a, b: 1 if a is b else 0)


@pytest.fixture
def bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass native wrapping for offline logic only, not native-binding proof."""
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)


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
    def __init__(self, primary, name="PivotDia") -> None:
        self.primary = primary
        self.dimension = SimpleNamespace(Name=name)

    def GetDimension(self):
        return self.dimension

    def GetPrimaryPrecision2(self):
        return self.primary


class _PrecisionAnnotation:
    def __init__(self, display) -> None:
        self.display = display

    def GetSpecificAnnotation(self):
        return self.display


class _PrecisionExtension:
    def __init__(self, precision) -> None:
        self.precision = precision
        self.calls: list[tuple[int, int]] = []

    def GetUserPreferenceInteger(self, preference: int, option: int):
        self.calls.append((preference, option))
        return self.precision


def _pivot_precision_case(primary, document_precision=2, name="PivotDia"):
    """Method-shaped scalar getters model the typelib, not a live COM binding."""
    display = _PrecisionDisplay(primary, name)
    annotation = _PrecisionAnnotation(display)
    extension = _PrecisionExtension(document_precision)
    model = SimpleNamespace(Extension=extension)
    return _PrecisionAdapter(), model, annotation, extension


@pytest.mark.parametrize("primary", [2, -2], ids=["explicit", "inherited"])
def test_pivot_precision_matching_two_places_passes(bound: None, primary) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(primary)
    drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if primary == -2 else [])


@pytest.mark.parametrize("primary", [3, -2], ids=["explicit", "inherited"])
def test_pivot_precision_three_places_fails(bound: None, primary) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(primary, 3)
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*effective 3"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if primary == -2 else [])


@pytest.mark.parametrize(
    ("primary", "document_precision", "calls"),
    [
        (None, 2, []),
        (-2, None, [(24, 204)]),
        (-2, -2, [(24, 204)]),
    ],
    ids=["raw-missing", "document-missing", "document-still-sentinel"],
)
def test_pivot_precision_missing_readback_fails(
    bound: None, primary, document_precision, calls
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        primary, document_precision
    )
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == calls


@pytest.mark.parametrize("inherited", [False, True], ids=["raw", "document"])
@pytest.mark.parametrize(
    "unreadable",
    [True, 2.0, "2", Mock(), _PrecisionDisplay(2).GetPrimaryPrecision2],
    ids=["bool", "float", "string", "mock", "bound-method"],
)
def test_pivot_precision_never_coerces_unreadable_values(
    bound: None, inherited: bool, unreadable
) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        -2 if inherited else unreadable, unreadable
    )
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == ([(24, 204)] if inherited else [])


@pytest.mark.parametrize("empty", [True, False], ids=["empty", "other-dimension"])
def test_pivot_precision_missing_dimension_fails(bound: None, empty: bool) -> None:
    adapter, model, annotation, extension = _pivot_precision_case(
        2, name="TopAbovePivot"
    )
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*missing dimension"):
        drawing._assert_pivot_precision(adapter, model, [] if empty else [annotation])
    assert extension.calls == []


@pytest.mark.parametrize("stage", ["annotation", "dimension", "primary", "document"])
def test_pivot_precision_getter_exceptions_fail_closed(
    bound: None, monkeypatch: pytest.MonkeyPatch, stage: str
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
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])


@pytest.mark.parametrize("stage", ["display", "dimension", "name", "extension"])
def test_pivot_precision_unavailable_native_state_fails_closed(
    bound: None, stage: str
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
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])
    assert extension.calls == []


@pytest.mark.parametrize(
    "interface",
    ["IAnnotation", "IDisplayDimension", "IModelDoc2", "IModelDocExtension"],
)
def test_pivot_precision_binding_failures_fail_closed(
    monkeypatch: pytest.MonkeyPatch, interface: str
) -> None:
    adapter, model, annotation, _extension = _pivot_precision_case(-2)

    def bind(obj, requested):
        if requested == interface:
            raise RuntimeError("native binding unavailable")
        return obj

    monkeypatch.setattr(drawing, "_early_bound", bind)
    with pytest.raises(RuntimeError, match="PivotDia.*expected 2.*unreadable"):
        drawing._assert_pivot_precision(adapter, model, [annotation])


def test_build_keeps_pivot_out_of_strict_part_precision() -> None:
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    strict_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "assert_imported_precision"
    )
    assert {ast.literal_eval(key) for key in strict_call.args[2].keys} == {
        "TopAbovePivot",
        "HubLength",
        "StrapThickness",
    }


def test_datum_a_attached_to_the_bore_passes(bound: None) -> None:
    drawing._require_datum_on_bore(_APP, _Tag((_BORE,)), _BORE)


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
        fraction = round(math.dist(xy, _PIVOT_CENTRE) / drawing.PIVOT_BORE_SHEET_R, 6)
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
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE)
    assert [fraction for fraction, _ in picks] == [1.0]
    bearing = math.atan2(xy[1] - _PIVOT_CENTRE[1], xy[0] - _PIVOT_CENTRE[0])
    assert bearing == pytest.approx(drawing.PIVOT_DATUM_ANGLE)
    assert math.dist(xy, _PIVOT_CENTRE) == pytest.approx(drawing.PIVOT_BORE_SHEET_R)


def test_pivot_pick_moves_inward_when_the_rim_resolves_to_the_hub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda fraction: _HUB if fraction == 1.0 else _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE)
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
        drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE)


class _Window:
    def __init__(self) -> None:
        self.calls: list = []

    def ViewZoomTo2(self, *box: float) -> None:
        self.calls.append(("zoom", box))

    def ViewZoomtofit2(self) -> None:
        self.calls.append(("fit",))


def test_pivot_pick_zoom_frames_the_hub_and_restores_fit() -> None:
    window = _Window()
    adapter = SimpleNamespace(currentModel=window)
    half = drawing.PIVOT_PICK_ZOOM_HALF
    with pytest.raises(ValueError):
        with drawing._zoomed_on(adapter, _PIVOT_CENTRE, half):
            raise ValueError("pick failed")
    x, y = _PIVOT_CENTRE
    assert window.calls == [
        ("zoom", (x - half, y - half, 0.0, x + half, y + half, 0.0)),
        ("fit",),
    ]
    # The window holds the hub with margin, so the pick point is on screen.
    assert half > drawing.PIVOT_HUB_SHEET_R


# Datum A's frame as r743-4D printed it (coordinate pick, request 20 mm out on
# the 135-degree ray; 5100x3300 px render on 431.8x279.4 mm): the box spans
# 13.40..6.46 mm left of the requested point and 3.5 mm either side of it.
DATUM_BOX_LEFT = 0.01340
DATUM_BOX_RIGHT = 0.00646
DATUM_BOX_HALF_HEIGHT = 0.0035


def _strap_top_sheet_y(sheet_x: float) -> float:
    scale = drawing._S / 1000.0
    model_x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
    return drawing._sheet_xy(
        model_x,
        ch_rocker_arm_spec.CENTER_Y - math.sqrt(ch_rocker_arm_spec.R_TOP**2 - model_x**2),
    )[1]


def test_datum_a_frame_box_sits_off_the_part_outline() -> None:
    """r743-1RC: the entity-attached tag printed its frame on the strap. The
    coordinate-picked frame sits above the strap's top edge across its whole
    width, clear of the O6.50 text and above the notes."""
    rx, ry = drawing._pivot_datum_request(_PIVOT_CENTRE)
    box = (
        rx - DATUM_BOX_LEFT,
        ry - DATUM_BOX_HALF_HEIGHT,
        rx - DATUM_BOX_RIGHT,
        ry + DATUM_BOX_HALF_HEIGHT,
    )
    # r743-4D's measured frame for this same request: the fixture is that print.
    assert box == pytest.approx((0.15131, 0.18347, 0.15825, 0.19047), abs=2e-4)
    # The top edge is concave up, so its highest point under the box is at
    # one of the box's ends.
    strap_top = max(_strap_top_sheet_y(box[0]), _strap_top_sheet_y(box[2]))
    assert box[1] > strap_top + DATUM_BOX_HALF_HEIGHT
    _text_x, text_y = drawing.FRONT_KEEP["PivotDia"]
    assert box[1] > text_y + 0.010
    assert box[1] > drawing.NOTES_CEILING


def test_pivot_leaders_take_separate_quadrants() -> None:
    """r743-1RC: datum A, the Ra and the O6.50 converged on the bore. The
    O6.50 line runs through the centre, so it takes its text's quadrant and
    the opposite one; datum A and the Ra take the other two."""

    def quadrant(bearing: float) -> int:
        return int((bearing % math.tau) // (math.pi / 2.0))

    text = drawing.FRONT_KEEP["PivotDia"]
    dimension = math.atan2(text[1] - _PIVOT_CENTRE[1], text[0] - _PIVOT_CENTRE[0])
    rim, _symbol = drawing._pivot_finish_placement()
    finish = math.atan2(rim[1] - _PIVOT_CENTRE[1], rim[0] - _PIVOT_CENTRE[0])
    used = [
        quadrant(drawing.PIVOT_DATUM_ANGLE),
        quadrant(finish),
        quadrant(dimension),
        quadrant(dimension + math.pi),
    ]
    assert sorted(used) == [0, 1, 2, 3]
    # Datum A and the Ra land oblique to the centre-mark axes, not on them.
    for bearing in (drawing.PIVOT_DATUM_ANGLE, finish):
        assert math.degrees(bearing) % 90.0 == pytest.approx(45.0)


def test_pivot_diameter_text_is_clear_of_the_rod_pin_x_dimension() -> None:
    """r743-4D: the O6.50 leader, from text straight below the bore, crossed
    the rod-pin X location dimension. Its text now sits left of that
    dimension's span (pivot to rod-pin hole) and below the strap."""
    text_x, text_y = drawing.FRONT_KEEP["PivotDia"]
    pivot_x, pivot_y = drawing._sheet_xy(0.0, ch_rocker_arm_spec.PIVOT_MID_Y)
    # Diameter text runs ~2.6 mm a character from its anchor: "O6.50" is 5.
    assert text_x + 5 * 0.0026 < pivot_x - ch_rocker_arm_spec.HUB_DIA / 2000.0
    assert text_y < pivot_y - ch_rocker_arm_spec.ARM_DEPTH / 2000.0
    # Above the notes band.
    assert text_y > drawing.NOTES_CEILING + 0.010


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
            if keywords.get("label", "").startswith("'rod-pin") or keywords.get(
                "label", ""
            ).startswith('"rod-pin'):
                if node.func.id != "set_basic_dimension":
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
RIGHT_BORDER = 0.415
DRAWABLE = DrawableRegion(0.0127, BORDER_BOTTOM, 0.4191, 0.2667)


class _FakeAnnotation:
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
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None)
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
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
    # Every line stays within the widest line r743-2R already rendered
    # clear of the front view.
    assert max(len(line) for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()) <= 42


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
    fcf_bottom = drawing.FCF_XY[1] - 0.007
    assert top < fcf_bottom - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right


# The Ra symbol as r743-1RC printed it at note text height: its ink runs
# 7.2 mm above and 14.7 mm right of its anchor (the leader end).
FINISH_SYMBOL_HEIGHT = 0.0072
FINISH_SYMBOL_WIDTH = 0.0147


def _strap_bottom_sheet_y(sheet_x: float) -> float:
    scale = drawing._S / 1000.0
    model_x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
    return drawing._sheet_xy(
        model_x,
        ch_rocker_arm_spec.CENTER_Y
        - math.sqrt(ch_rocker_arm_spec.R_BOTTOM**2 - model_x**2),
    )[1]


def test_pivot_finish_leader_runs_up_left_from_a_symbol_below_the_strap() -> None:
    """r743-p1s-B2: from the 7:30 rim the leader ran up through the symbol,
    whose body draws up-right of its leader end. r743-1RC: at 1:30 it met the
    O6.50 line. At 4:30 the symbol sits down-right of its rim point, its whole
    body below the strap's bottom edge, at note text height."""
    rim, symbol = drawing._pivot_finish_placement()
    scale = drawing._S / 1000.0
    assert math.dist(rim, _PIVOT_CENTRE) == pytest.approx(
        ch_rocker_arm_spec.PIVOT_HOLE_DIA / 2.0 * scale
    )
    # Oblique to both centre-mark axes.
    assert abs(rim[0] - _PIVOT_CENTRE[0]) > 0.0005
    assert abs(rim[1] - _PIVOT_CENTRE[1]) > 0.0005
    assert symbol[0] > rim[0] and symbol[1] < rim[1]
    assert math.dist(symbol, _PIVOT_CENTRE) > ch_rocker_arm_spec.HUB_DIA / 2.0 * scale + 0.005
    # The bottom edge is concave up: its lowest point under the body is at
    # the body's left end.
    body_top = symbol[1] + FINISH_SYMBOL_HEIGHT
    assert body_top < _strap_bottom_sheet_y(symbol[0]) - 0.002
    # Right of the rod-pin X location's extension line through the pivot, and
    # above that dimension's line and text (y 0.138).
    assert rim[0] > _PIVOT_CENTRE[0]
    assert symbol[1] > 0.138 + 0.010
    assert symbol[0] + FINISH_SYMBOL_WIDTH < drawing._sheet_xy(
        ch_rocker_arm_spec.ROD_HOLE_X, 0.0
    )[0]
    assert drawing.PIVOT_FINISH_CHAR_HEIGHT <= 0.0025


def test_land_and_hub_sizes_are_marked_model_dimensions_at_normal_precision() -> None:
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["StrapProfile"] == {
        "TopRadius", "BottomRadius", "RodTipLen",
    }
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["HubProfile"] == {"HubDia"}
    assert {"RodTipLen", "HubDia"} <= set(drawing.FRONT_KEEP)
    assert not {"RodTipLen", "HubDia"} & set(drawing.RIGHT_KEEP)
    assert ch_rocker_arm_notes.DRAWING_PRECISION["HubProfile"]["HubDia"] == 2
    assert ch_rocker_arm_notes.DEFAULT_DRAWING_PRECISION == 2
    assert ch_rocker_arm_spec.LINEAR_2PL == pytest.approx(0.508)
    assert ch_rocker_arm_spec.STRAP_HUB_SYMMETRY == pytest.approx(0.10)
    joined = " ".join(ch_rocker_arm_notes.DRAWING_NOTES.split())
    assert "STRAP SYMMETRIC TO HUB WITHIN 0.10" in joined


def test_new_measured_quantities_follow_the_source_geometry_equations() -> None:
    spec = ch_rocker_arm_spec
    alpha = spec.TOP_ARC_LEN / (2.0 * spec.CURVE_RADIUS)
    assert spec._ALPHA_TOP == pytest.approx(alpha)
    assert 2.0 * spec.ROD_TIP_X == pytest.approx(
        2.0 * (spec.CURVE_RADIUS + spec.TIP_FACE) * math.sin(alpha),
    )
    assert spec.BOT_END_X == pytest.approx(
        (spec.CURVE_RADIUS + spec.ARM_DEPTH)
        * math.sin(spec.BOT_ARC_LEN / (2.0 * (spec.CURVE_RADIUS + spec.ARM_DEPTH))),
    )
    assert spec.TIP_FACE == pytest.approx(5.588)
    assert spec.HUB_DIA == pytest.approx(10.2)
    assert (spec.HUB_LENGTH - spec.ARM_THICKNESS) / 2.0 == pytest.approx(2.27825)


@pytest.mark.parametrize("ignored_part", [None, 1, 2])
def test_native_reference_parentheses_never_replace_the_measured_nominal(
    monkeypatch: pytest.MonkeyPatch, ignored_part: int | None,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    text = {1: "", 2: ""}
    writes = []
    model = SimpleNamespace(SystemValue=0.00227825)

    def set_text(part, value):
        writes.append((part, value))
        if part != ignored_part:
            text[part] = value

    display = SimpleNamespace(
        SetText=set_text, GetText=lambda part: text[part],
        GetDimension2=lambda _index: model,
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
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
    assert keywords["process"] == "drill_process(ROD_HOLE_SPEC) + '\\n'"
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
    model = None if defect == "missing" else SimpleNamespace(
        SystemValue=(expected + (0.1 if defect == "wrong" else 0.0)) / 1000.0,
    )
    if defect in {"nan", "inf", "no_value"}:
        model.SystemValue = None if defect == "no_value" else float(defect)
    attached = (first, neighbour if defect == "neighbour" else second)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: attached,
        GetAttachedEntityTypes=lambda: (1, 1),
        IsDangling=lambda: defect == "dangling",
    )
    display = SimpleNamespace(
        GetDimension2=lambda _index: model, GetAnnotation=lambda: annotation,
    )
    adapter = SimpleNamespace(swApp=_APP)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
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
        return True

    display = SimpleNamespace(
        SetPrecision3=set_precision, GetPrimaryPrecision2=lambda: state["precision"],
    )
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
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
def test_imported_hub_diameter_cannot_lose_the_model_two_place_size_band(
    monkeypatch: pytest.MonkeyPatch, defect: str | None,
) -> None:
    import _drawing_dimensions
    from solidworks_mcp.adapters import sw_type_info

    display = SimpleNamespace(
        GetPrimaryPrecision2=lambda: 1 if defect == "one_place" else 2,
        SetPrecision3=lambda *_: pytest.fail("imported hub precision is part-owned"),
    )
    annotation = SimpleNamespace(
        GetSpecificAnnotation=lambda: None if defect == "no_display" else display,
    )
    adapter = SimpleNamespace(_attempt=lambda fn: fn())
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda *_: "HubDia")
    annotations = [] if defect == "missing" else [annotation]
    precision = ch_rocker_arm_notes.DRAWING_PRECISION["HubProfile"]
    if defect is None:
        _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)
    else:
        with pytest.raises(RuntimeError):
            _drawing_dimensions.assert_imported_precision(adapter, annotations, precision)


@pytest.mark.parametrize("defect", [None, "selection", "landing", "creation"])
def test_native_angular_dimension_keeps_named_entities_and_explicit_pick_points(
    monkeypatch: pytest.MonkeyPatch, defect: str | None,
) -> None:
    import _drawing_edge_dimensions

    selected = []
    events = []
    view = object()
    display = object()

    def select(entity, append, data):
        assert data.View is view
        if not append:
            selected.clear()
        selected.append(entity)
        events.append(("select", entity))
        return defect != "selection"

    first = SimpleNamespace(Select4=lambda append, data: select("land", append, data))
    second = SimpleNamespace(Select4=lambda append, data: select("mirror", append, data))

    def landing(index, mark, x, y, z):
        events.append(("landing", index, mark, x, y, z))
        return defect != "landing"

    def create(x, y, z, kind, options):
        events.append(("create", x, y, z, kind, options))
        return (None if defect == "creation" else display), 0

    draw = SimpleNamespace(
        ActivateView=lambda _name: True,
        ClearSelection2=lambda _all: selected.clear(),
        SelectionManager=SimpleNamespace(
            CreateSelectData=SimpleNamespace,
            GetSelectedObjectCount2=lambda _mark: len(selected),
            SetSelectionPoint2=landing,
        ),
        Extension=SimpleNamespace(
            AddSpecificDimension=create,
            SelectByID2=lambda *_: pytest.fail("native angle must not coordinate hit-test"),
        ),
    )
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_edge_dimensions, "view_name", lambda *_: "front")
    kwargs = dict(
        p0=(0.22, 0.2), p1=(0.13, 0.2), text_xy=(0.24, 0.21),
        entities=(first, second), orientation="angular", label="end-land angle",
    )
    if defect is None:
        assert _drawing_edge_dimensions.add_edge_dimension(
            SimpleNamespace(currentModel=draw), view, **kwargs,
        ) is display
        assert events[-1] == ("create", 0.24, 0.21, 0.0, 3, 0)
        assert events[1] == ("landing", 1, -1, 0.22, 0.2, 0.0)
        assert events[3] == ("landing", 2, -1, 0.13, 0.2, 0.0)
    else:
        with pytest.raises(RuntimeError):
            _drawing_edge_dimensions.add_edge_dimension(
                SimpleNamespace(currentModel=draw), view, **kwargs,
            )
        if defect != "creation":
            assert not any(event[0] == "create" for event in events)


@pytest.mark.parametrize("defect", [
    None, "wrong", "degrees_as_radians", "supplementary", "wrong_type",
    "missing", "no_value", "nan", "inf",
])
def test_native_land_angle_measures_source_angle_in_radians_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, defect: str | None,
) -> None:
    expected = math.degrees(ch_rocker_arm_spec._ALPHA_TOP)
    radians = ch_rocker_arm_spec._ALPHA_TOP
    values = {
        "wrong": radians + math.radians(0.1),
        "degrees_as_radians": expected,
        "supplementary": math.pi - radians,
        "no_value": None,
        "nan": float("nan"),
        "inf": float("inf"),
    }
    model = SimpleNamespace(
        SystemValue=values.get(defect, radians),
        Type2=1 if defect == "wrong_type" else 3,
    )
    display = SimpleNamespace(
        Type2=1 if defect == "wrong_type" else 3,
        GetDimension2=lambda _index: None if defect == "missing" else model,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_: obj)
    kwargs = dict(expected_degrees=expected, label="end-land angle")
    if defect is None:
        assert drawing._require_native_angle(display, **kwargs) == pytest.approx(expected)
    else:
        with pytest.raises(RuntimeError):
            drawing._require_native_angle(display, **kwargs)


@pytest.mark.parametrize("name", [
    "ROD_TIP_X", "TIP_FACE", "_ALPHA_TOP", "BOT_END_X", "HUB_DIA",
    "HUB_LENGTH", "ARM_THICKNESS",
])
def test_measured_dimension_expectations_import_the_geometry_source(name: str) -> None:
    assert getattr(drawing, name) == getattr(ch_rocker_arm_spec, name)


class _NativeQuantity:
    """A native display/model pair, retaining independent text and size bands."""

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
        self.model = SimpleNamespace(
            SystemValue=mm / 1000.0,
            Type2=6 if name in {"PivotDia", "HubDia"} else 1,
            SetToleranceType=lambda kind: True,
            GetToleranceType=lambda: self.tolerance_type,
            Tolerance=SimpleNamespace(
                GetMaxValue=lambda: self.band[0],
                GetMinValue=lambda: self.band[1],
            ),
            GetArcEndCondition=lambda index: self.arc_conditions[index],
            SetArcEndCondition=self._set_arc_condition,
        )

    def GetSpecificAnnotation(self):
        return self

    def GetAnnotation(self):
        return self

    def GetDimension2(self, _index):
        return self.model

    def GetDimension(self):
        return self.model

    def _set_arc_condition(self, index, condition):
        self.arc_conditions[index] = condition
        return 0

    def GetAttachedEntities3(self):
        return self.attached

    def GetAttachedEntityTypes(self):
        return tuple(1 for _ in self.attached)

    def IsDangling(self):
        return self.dangling

    def GetText(self, part):
        return self.text[{5: 1, 6: 2, 7: 3, 8: 4}.get(part, part)]

    def SetText(self, part, value):
        self.writes.append((part, value))
        if part != self.ignored_text:
            self.text[part] = value

    def SetPrecision3(self, primary, *_rest):
        if not self.ignored_precision:
            self.precision = primary
        return True

    def GetPrimaryPrecision2(self):
        return self.precision

    def SetSecondArrow(self, use_doc, enabled):
        self.second_arrow = (use_doc, enabled)

    def GetUseDocSecondArrow(self):
        return self.second_arrow[0]

    def GetSecondArrow(self):
        return self.second_arrow[1]


def _imported_native_quantities(monkeypatch: pytest.MonkeyPatch):
    from solidworks_mcp.adapters import sw_type_info
    import _drawing_dimensions
    import _drawing_edge_dimensions

    displays = {
        "PivotDia": _NativeQuantity("PivotDia", ch_rocker_arm_spec.PIVOT_HOLE_DIA),
        "RodTipLen": _NativeQuantity("RodTipLen", ch_rocker_arm_spec.TIP_FACE),
        "HubDia": _NativeQuantity("HubDia", ch_rocker_arm_spec.HUB_DIA),
    }
    adapter = SimpleNamespace(
        _attempt=lambda fn: fn(), swApp=_APP,
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_edge_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_dimensions, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, ann: ann.name)
    monkeypatch.setattr(_drawing_dimensions, "dimension_name", lambda _adapter, ann: ann.name)
    monkeypatch.setattr(_drawing_dimensions, "rebuild_drawing", lambda *_a, **_k: None)
    return adapter, displays


def test_front_native_process_keeps_the_nominal_token_and_model_bore_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    before = {name: display.model.SystemValue for name, display in displays.items()}
    drawing._dress_front_dimensions(adapter, list(displays.values()))
    pivot = displays["PivotDia"]
    assert pivot.text[1].startswith("REAM ")
    assert "<MOD-DIAM>" in pivot.text[1]
    assert "THRU" in pivot.text[2]
    assert not any(part == 0 for part, _text in pivot.writes)
    assert not any(nominal in text for _part, text in pivot.writes for nominal in (
        "6.50", "5.588", "10.20", "+0.03",
    ))
    assert {name: display.model.SystemValue for name, display in displays.items()} == before
    assert displays["HubDia"].precision == 2
    assert pivot.band == tuple(v / 1000.0 for v in ch_rocker_arm_spec.PIVOT_HOLE_BAND)
    assert pivot.model.GetToleranceType() == 4
    assert pivot.ShowDimensionValue is True
    assert (pivot.text[3], pivot.text[4]) == ("<native-upper>", "<native-lower>")


@pytest.mark.parametrize("name", ["RodTipLen", "HubDia"])
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
        drawing._dress_front_dimensions(adapter, list(displays.values()))


@pytest.mark.parametrize("ignored", ["prefix", "suffix", "hub_precision"])
def test_front_native_dressing_rejects_ignored_text_or_lost_hub_precision(
    monkeypatch: pytest.MonkeyPatch, ignored: str,
) -> None:
    adapter, displays = _imported_native_quantities(monkeypatch)
    if ignored == "hub_precision":
        displays["HubDia"].precision = 1
    else:
        displays["PivotDia"].ignored_text = 1 if ignored == "prefix" else 2
    with pytest.raises(RuntimeError):
        drawing._dress_front_dimensions(adapter, list(displays.values()))


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
        displays={}, calls=[], verticals=[], basic_calls=[],
        defect_label=None, defect=None,
    )

    def project(_adapter, _view, points, **_kwargs):
        return [drawing._sheet_xy(x * 1000.0, y * 1000.0) for x, y, _z in points]

    def vertical(_adapter, _front, points):
        entity = object()
        state.verticals.append((entity, points))
        return entity

    def create(_adapter, _front, **kwargs):
        state.calls.append(kwargs)
        label = kwargs["label"]
        entities = kwargs["entities"]
        if label == "rocker overall width":
            value_mm = abs(vertex_points[entities[1]][0] - vertex_points[entities[0]][0])
        elif label == "taper intersection X":
            value_mm = abs(vertex_points[entities[1]][0])
        elif label == "radial land angle to mirror axis":
            a, b = land.line
            radians = math.atan2(abs(a[0] - b[0]), abs(a[1] - b[1]))
            value_mm = radians * 1000.0
        else:
            pytest.fail(f"unowned native dimension {label}")
        display = _NativeQuantity(label, value_mm)
        display.attached = entities
        if kwargs["orientation"] == "angular":
            display.Type2 = 3
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
        state.displays[label] = display
        return display

    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_a, **_k: list(imported.values()))
    monkeypatch.setattr(
        drawing, "_basic_profile_dimensions",
        lambda _adapter, annotations: state.basic_calls.append(annotations),
    )
    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_k: scan)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "_land_vertical", vertical)
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
    assert drawing._add_rocker_outline_dimensions(state.adapter, object()) is state.land
    assert state.basic_calls
    assert all(point[2] == ch_rocker_arm_spec.ARM_THICKNESS / 2.0 for point in state.land.line)
    expected = {
        "rocker overall width": 2.0 * ch_rocker_arm_spec.ROD_TIP_X / 1000.0,
        "taper intersection X": ch_rocker_arm_spec.BOT_END_X / 1000.0,
        "radial land angle to mirror axis": ch_rocker_arm_spec._ALPHA_TOP,
    }
    assert {
        label: display.model.SystemValue for label, display in state.displays.items()
    } == pytest.approx(expected)
    width, angle, taper = state.calls
    assert width["entity_type"] == "VERTEX"
    assert angle["entities"] == (state.land.edge, state.verticals[0][0])
    assert angle["entity_types"] == ("EDGE", "SKETCHSEGMENT")
    assert taper["entity_types"] == ("EDGE", "VERTEX")
    assert state.displays["taper intersection X"].arc_conditions[1] == 1
    vertical_points = state.verticals[0][1]
    assert vertical_points[0][0] == vertical_points[1][0]
    # Local ray stays on the sheet instead of reaching the off-sheet R800 centre.
    assert all(
        DRAWABLE.xmin <= x <= DRAWABLE.xmax and DRAWABLE.ymin <= y <= DRAWABLE.ymax
        for x, y in vertical_points
    )
    assert state.displays["radial land angle to mirror axis"].text[4] == "TO MIRROR AXIS"


@pytest.mark.parametrize("label", [
    "rocker overall width", "radial land angle to mirror axis", "taper intersection X",
])
@pytest.mark.parametrize("defect", ["creation", "wrong", "missing", "nan", "inf", "attachment"])
def test_each_new_outline_measurement_fails_closed(native_front, label, defect) -> None:
    native_front.defect_label = label
    native_front.defect = defect
    with pytest.raises(RuntimeError):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())


@pytest.mark.parametrize("source", ["ROD_TIP_X", "TIP_FACE", "_ALPHA_TOP", "BOT_END_X", "HUB_DIA"])
def test_source_geometry_change_invalidates_stale_front_measurements(
    native_front, monkeypatch: pytest.MonkeyPatch, source: str,
) -> None:
    monkeypatch.setattr(drawing, source, getattr(drawing, source) + 0.1)
    with pytest.raises(RuntimeError):
        drawing._add_rocker_outline_dimensions(native_front.adapter, object())


def test_datum_c_owns_the_named_positive_z_land_and_midpoint_landing(
    native_front, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    tag = object()

    def insert(_adapter, _front, **kwargs):
        calls.append(kwargs)
        return tag

    monkeypatch.setattr(drawing, "add_datum_feature", insert)
    assert drawing._add_land_datum(
        native_front.adapter, object(), native_front.land,
    ) is tag
    (call,) = calls
    assert call["datum"] == "C"
    assert call["edge_entity"] is native_front.land.edge
    assert "edge_xy" not in call and "expected_entity" not in call
    a, b = native_front.land.line
    expected = drawing._sheet_xy((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    assert call["leader_attach_xy"] == pytest.approx(expected)
    assert math.dist(call["symbol_xy"], expected) == pytest.approx(drawing.LAND_DATUM_STANDOFF)
    assert call["symbol_xy"][0] > expected[0]


@pytest.mark.parametrize("defect", ["rear_face", "wrong_length", "not_a_line"])
def test_datum_c_refuses_a_nonland_owner_before_insertion(
    native_front, monkeypatch: pytest.MonkeyPatch, defect: str,
) -> None:
    from dataclasses import replace

    a, b = native_front.land.line
    if defect == "rear_face":
        line = ((a[0], a[1], -a[2]), (b[0], b[1], -b[2]))
    elif defect == "wrong_length":
        line = (a, (b[0] + 1.0, b[1], b[2]))
    else:
        line = None
    monkeypatch.setattr(
        drawing, "add_datum_feature", lambda *_a, **_k: pytest.fail("invalid C owner inserted"),
    )
    with pytest.raises(RuntimeError):
        drawing._add_land_datum(
            native_front.adapter, object(), replace(native_front.land, line=line),
        )


@pytest.fixture
def native_offset(monkeypatch: pytest.MonkeyPatch):
    import _drawing_edge_dimensions
    from _drawing_edges import ViewEdge, ViewEdges

    adapter, _imported = _imported_native_quantities(monkeypatch)
    a = (drawing.TOP_END_X, drawing.TOP_END_Y, drawing.ARM_THICKNESS / 2.0)
    b = (drawing.ROD_TIP_X, drawing._ROD_TIP_Y, drawing.ARM_THICKNESS / 2.0)
    strap = ViewEdge(object(), (a, b), None, (object(), object()))
    rear = ViewEdge(
        object(), ((a[0], a[1], -a[2]), (b[0], b[1], -b[2])), None,
        (object(), object()),
    )
    hub = ViewEdge(
        object(), None,
        (0.0, drawing.PIVOT_MID_Y, drawing.HUB_LENGTH / 2.0, 0.0, 0.0, 1.0, drawing.HUB_DIA / 2.0),
        None,
    )
    back_hub = ViewEdge(
        object(), None,
        (0.0, drawing.PIVOT_MID_Y, -drawing.HUB_LENGTH / 2.0, 0.0, 0.0, 1.0, drawing.HUB_DIA / 2.0),
        None,
    )
    scan = ViewEdges("right native CAD", (rear, back_hub, strap, hub))
    state = SimpleNamespace(adapter=adapter, scan=scan, strap=strap, hub=hub, display=None, defect=None)

    def create(_adapter, _view, **kwargs):
        assert kwargs["entities"] == (hub.edge, strap.edge)
        assert kwargs["orientation"] == "horizontal"
        mm = hub.circle[2] - strap.midpoint_mm[2]
        display = _NativeQuantity("offset", mm, precision=3)
        display.attached = kwargs["entities"]
        if state.defect == "creation":
            raise RuntimeError("offset native creation refused")
        if state.defect == "wrong":
            display.model.SystemValue += 0.0001
        elif state.defect in {"nan", "inf"}:
            display.model.SystemValue = float(state.defect)
        elif state.defect == "missing":
            display.model.SystemValue = None
        elif state.defect == "attachment":
            display.attached = (hub.edge, object())
        elif state.defect == "band":
            display.tolerance_type = 2
        elif state.defect == "precision":
            display.ignored_precision = True
        elif state.defect in {"prefix", "suffix"}:
            display.ignored_text = 1 if state.defect == "prefix" else 2
        state.display = display
        return display

    monkeypatch.setattr(drawing, "scan_view_edges", lambda *_a, **_k: scan)
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [
            (drawing.RIGHT_CENTER[0] - z, drawing.RIGHT_CENTER[1] + y)
            for _x, y, z in points
        ],
    )
    monkeypatch.setattr(drawing, "add_edge_dimension", create)
    monkeypatch.setattr(
        drawing, "set_arc_endpoints_to_center",
        lambda *_a, **_k: pytest.fail("projected hub end rim is not a circular endpoint"),
    )
    monkeypatch.setattr(
        _drawing_edge_dimensions, "_is_same_attachment",
        lambda _adapter, actual, wanted, _kind: actual is wanted,
    )
    return state


def test_offset_is_the_measured_hub_end_to_strap_face_reference(native_offset) -> None:
    display = drawing._add_strap_offset_dimension(native_offset.adapter, object())
    assert display is native_offset.display
    assert display.model.SystemValue * 1000.0 == pytest.approx(
        (ch_rocker_arm_spec.HUB_LENGTH - ch_rocker_arm_spec.ARM_THICKNESS) / 2.0,
    )
    assert display.model.GetToleranceType() == 0
    assert display.precision == 2
    assert display.text[1] == "(" and display.text[2] == ")"
    assert display.writes == [(1, "("), (2, ")")]
    assert ch_rocker_arm_spec.STRAP_HUB_SYMMETRY == 0.10


@pytest.mark.parametrize("defect", [
    "creation", "wrong", "missing", "nan", "inf", "attachment",
    "band", "precision", "prefix", "suffix",
])
def test_offset_cannot_ship_a_wrong_or_unchecked_reference(native_offset, defect) -> None:
    native_offset.defect = defect
    with pytest.raises(RuntimeError):
        drawing._add_strap_offset_dimension(native_offset.adapter, object())


@pytest.mark.parametrize("source,delta", [("HUB_LENGTH", 0.001), ("ARM_THICKNESS", 0.0001)])
def test_offset_formula_change_invalidates_stale_native_measurement(
    native_offset, monkeypatch: pytest.MonkeyPatch, source: str, delta: float,
) -> None:
    # Both changed picks remain within exact/circle selector tolerances; it is
    # the formula readback, not a missing entity, that must reject the stale CAD.
    monkeypatch.setattr(drawing, source, getattr(drawing, source) + delta)
    with pytest.raises(RuntimeError, match="strap offset from hub end measures"):
        drawing._add_strap_offset_dimension(native_offset.adapter, object())
