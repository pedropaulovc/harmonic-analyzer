"""Offline contracts for the two-sheet cone-swing-platform package (#917 S1).

Main's ruling on PR #929: the hole-location plan (View2), its callouts and
caption, and every view derived from it (section A-A, details B and D) move
to sheet 2 at the same 1:2 with no content change.  These tests judge that
split on the last one-sheet leaf's own read-back (``cone_swing_platform_ac4f
_dump``) with the planner's and the audit's rules.
"""

from __future__ import annotations

import inspect
import math
import re
from dataclasses import replace

import _drawing_common
import _drawing_leaders
import build_cone_swing_platform as part
import cone_swing_platform_ac4f_dump as ac4f
import draw_cone_swing_platform as drawing
import pytest
from _drawing_layout_check import CollisionScope, DrawableRegion, LayoutElement
from _drawing_registry import DrawingLayout
from _layout_geometry import (
    AnnotationGeometry,
    Box,
    Segment,
    SheetGeometry,
    ViewGeometry,
    estimate_text_box,
)
from _layout_planner import sheet_obstacles
from cone_post_dowel_spec import PLATE_DOWEL_REAM_DIA, POST_DOWEL_PLATE_XZ
from cone_swing_platform_spec import PIVOT_HOLE_DIA, POST_MOUNT_SPEC
from _hole_spec import blind_cut_dia_mm

MM = 0.001
_BOX = re.compile(r"\[(-?[\d.]+),(-?[\d.]+)\]\.\.\[(-?[\d.]+),(-?[\d.]+)\]")
_RUN = re.compile(r"\((-?[\d.]+),(-?[\d.]+)\)->\((-?[\d.]+),(-?[\d.]+)\)")

# The ac4f leaf's view names, by the recipe's own key for each view.
_AC4F_VIEWS = {
    "Drawing View1": "profile plan",
    "Drawing View2": "feature plan",
    "Drawing View3": "notch plan",
    "Drawing View4": "isometric",
    "Section View A-A": "pivot section",
    "Detail View B (2 : 1)": "tip screw slot detail",
    "Detail View D (2 : 1)": "lock notch cap detail",
    "Section View C-C": "tip screw slot section",
}
# Where ac4f put each property-linked caption (the recipe's anchors; ac4f
# read every one of them back owned by section A-A, the view active when
# they were inserted, so ownership cannot place them).
_CAPTION_ANCHORS = {
    "Profile View Note": (0.045, 0.085),
    "Feature View Note": (0.150, 0.085),
    "Notch View Note": drawing.NOTCH_CAPTION_UPPER_LEFT,
    "Isometric View Note": drawing.ISO_NOTE_UPPER_LEFT,
    "Pivot Relief Fit": drawing.RELIEF_NOTE_XY,
}
# ac4f's callout anchors (IAnnotation::GetPosition, read back).
_AC4F_CALLOUT_XY = {
    "RD1": (0.215, 0.107),
    "RD2": (0.200, 0.258),
    "RD3": (0.117, 0.222),
}


def _box(match: re.Match[str]) -> Box:
    return Box(*(float(value) * MM for value in match.groups()))


def _parse(dump: str) -> SheetGeometry:
    """The ac4f sheet as ``collect_sheet`` returned it, from its dump."""
    lines = dump.strip("\n").splitlines()
    region = None
    advance = 0.723
    keep_outs: list[tuple[str, Box]] = []
    views: list[ViewGeometry] = []
    rows: list[dict] = []
    current: dict | None = None
    for line in lines[1:]:
        if "inner border" in line:
            region = DrawableRegion(*(float(v) * MM for v in _BOX.search(line).groups()))
        elif "glyph advance ratio" in line:
            advance = float(line.split(":")[1])
        elif line.startswith("  keep-out "):
            keep_outs.append((line.split()[1].rstrip(":"), _box(_BOX.search(line))))
        elif line.startswith("  view '"):
            name = line.split("'")[1]
            views.append(
                ViewGeometry(name, _box(_BOX.search(line)), pictorial=name == "Drawing View4")
            )
        elif re.match(r"^  [a-z-]+ '", line):
            tail = line.split("text", 1)[1] if "text[" in line else ""
            current = {
                "label": line.split("'")[1],
                "kind": line.split()[0],
                "owner": re.search(r"owner='([^']*)'", line).group(1),
                "text_boxes": tuple(_box(m) for m in _BOX.finditer(tail)),
                "segments": [],
                "position": None,
                "exact": "text[exact]" in line,
            }
            rows.append(current)
        elif current is not None and "GetPosition=" in line:
            x, y = re.findall(r"-?[\d.]+", line.split("=", 1)[1])[:2]
            current["position"] = (float(x) * MM, float(y) * MM)
        elif current is not None and re.match(r"^\s+(line|leader):", line):
            role = line.strip().split(":")[0]
            run = _RUN.search(line)
            current["segments"].append(
                Segment(*(float(v) * MM for v in run.groups()), role=role)
            )
    assert region is not None
    return SheetGeometry(
        name="Sheet1",
        width=0.4318,
        height=0.2794,
        region=region,
        keep_outs=tuple(keep_outs),
        views=tuple(views),
        annotations=tuple(
            AnnotationGeometry(**{**row, "segments": tuple(row["segments"])}) for row in rows
        ),
        advance_ratio=advance,
    )


AC4F = _parse(ac4f.DUMP)


def _caption_of(item: AnnotationGeometry) -> str | None:
    for caption, anchor in _CAPTION_ANCHORS.items():
        if item.position is not None and math.dist(item.position, anchor) < 0.0006:
            return caption
    return None


def _sheet_of(item: AnnotationGeometry) -> str:
    caption = _caption_of(item)
    if caption is not None:
        return drawing.caption_sheet(caption)
    return drawing.VIEW_SHEETS[_AC4F_VIEWS[item.owner]]


def _split(sheet: SheetGeometry) -> dict[str, SheetGeometry]:
    """ac4f's one sheet cut the way the two-sheet recipe builds it."""
    return {
        name: replace(
            sheet,
            name=name,
            views=tuple(
                v for v in sheet.views if drawing.VIEW_SHEETS[_AC4F_VIEWS[v.name]] == name
            ),
            annotations=tuple(a for a in sheet.annotations if _sheet_of(a) == name),
        )
        for name in drawing.SHEET_NAMES
    }


def _moved_callout(
    item: AnnotationGeometry, dx: float, dy: float, rim: tuple[float, float, float]
) -> AnnotationGeometry:
    """A callout's text moved rigidly, its leader and shelf as the planner
    draws them there (``HoleCallout.leader``)."""
    leader = drawing.hole_callout(item, rim=rim).leader(dx, dy, (0.0, 0.0))
    return replace(
        item,
        text_boxes=tuple(
            Box(b.xmin + dx, b.ymin + dy, b.xmax + dx, b.ymax + dy) for b in item.text_boxes
        ),
        segments=tuple(Segment(s.x0, s.y0, s.x1, s.y1, role="leader") for s in leader),
        position=(item.position[0] + dx, item.position[1] + dy),
    )


def _rims() -> dict[str, tuple[float, float, float]]:
    """Each callout's rim on the features sheet, from the part's own stations."""
    center = drawing.FEATURE_CENTER
    north_dowel = min(POST_DOWEL_PLATE_XZ, key=lambda xz: math.hypot(*xz))
    return {
        "RD1": (*drawing.plan_xy(center, 0.0, 0.0), PIVOT_HOLE_DIA / 2 * drawing.PLAN_SCALE),
        "RD2": (
            *drawing.plan_xy(center, *drawing.post_mount_callout_xz()),
            blind_cut_dia_mm(POST_MOUNT_SPEC) / 2 * drawing.PLAN_SCALE,
        ),
        "RD3": (
            *drawing.plan_xy(center, *north_dowel),
            PLATE_DOWEL_REAM_DIA / 2 * drawing.PLAN_SCALE,
        ),
    }


def _seeded_features_sheet() -> SheetGeometry:
    """The features sheet with each callout moved from ac4f's anchor to the
    recipe's seed."""
    seeds = {
        "RD1": drawing.PIVOT_CALLOUT_XY,
        "RD2": drawing.POST_MOUNT_CALLOUT_XY,
        "RD3": drawing.PLATE_DOWEL_CALLOUT_XY,
    }
    sheet = _split(AC4F)[drawing.FEATURES_SHEET]
    rims = _rims()
    return replace(
        sheet,
        annotations=tuple(
            _moved_callout(
                item,
                seeds[item.label][0] - _AC4F_CALLOUT_XY[item.label][0],
                seeds[item.label][1] - _AC4F_CALLOUT_XY[item.label][1],
                rims[item.label],
            )
            if item.label in seeds
            else item
            for item in sheet.annotations
        ),
    )


# --- the sheet contract ---------------------------------------------------------


def test_the_package_is_two_named_sheets_at_the_plan_scale() -> None:
    assert drawing.SHEET_NAMES == ("PLANS", "FEATURES")
    assert drawing.SHEET_SCALES == {name: (1.0, 2.0) for name in drawing.SHEET_NAMES}
    assert drawing.SHEET_LAYOUTS == {
        name: drawing.SPEC.layout for name in drawing.SHEET_NAMES
    }


def test_the_feature_plan_takes_its_callouts_caption_and_derived_views() -> None:
    """Sheet 1 keeps the profile and notch plans, the isometric and C-C; the
    feature plan goes to sheet 2 with A-A, B and D, which are cut from it."""
    on = {
        name: {view for view, sheet in drawing.VIEW_SHEETS.items() if sheet == name}
        for name in drawing.SHEET_NAMES
    }
    assert on["PLANS"] == {"profile plan", "notch plan", "isometric", "tip screw slot section"}
    assert on["FEATURES"] == {
        "feature plan",
        "pivot section",
        "tip screw slot detail",
        "lock notch cap detail",
    }
    assert drawing.caption_sheet("Feature View Note") == "FEATURES"
    assert drawing.caption_sheet("Pivot Relief Fit") == "FEATURES"
    assert {drawing.caption_sheet(c) for c in ("Profile View Note", "Notch View Note", "Isometric View Note")} == {"PLANS"}
    assert drawing.sheet_contract_errors() == []


def test_a_derived_view_off_its_parents_sheet_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """SolidWorks creates a section or detail on its parent's sheet, so a split
    declaring otherwise cannot be built."""
    moved = {**drawing.VIEW_SHEETS, "pivot section": drawing.PLANS_SHEET}
    monkeypatch.setattr(drawing, "VIEW_SHEETS", moved)
    assert drawing.sheet_contract_errors() == [
        "pivot section is on PLANS but its parent feature plan is on FEATURES"
    ]


def test_the_ac4f_views_and_captions_map_onto_the_declared_sheets() -> None:
    """Every ac4f view has a recipe key, every caption was found at its anchor,
    and no annotation is left without a sheet."""
    assert set(_AC4F_VIEWS) == {view.name for view in AC4F.views}
    assert set(_AC4F_VIEWS.values()) == set(drawing.VIEW_SHEETS)
    found = {_caption_of(item) for item in AC4F.annotations} - {None}
    assert found == set(_CAPTION_ANCHORS) == set(drawing.CAPTION_VIEWS)
    split = _split(AC4F)
    assert sum(len(s.annotations) for s in split.values()) == len(AC4F.annotations)
    assert {a.label for a in split["FEATURES"].annotations} >= {"RD1", "RD2", "RD3", "PlateThk"}


def test_the_sheets_are_made_before_the_first_view_and_finalized_as_a_package() -> None:
    source = inspect.getsource(drawing.build)
    assert source.index("create_blank_drawing_sheets(") < source.index("place_view(")
    assert "expected_sheet_names=SHEET_NAMES" in source
    assert "sheet_layouts=SHEET_LAYOUTS" in source
    assert "sheet_scales=SHEET_SCALES" in source
    assert "check_every_sheet_layout(adapter)" in source
    assert "check_drawing_layout(" not in source


# --- the features sheet's callouts ----------------------------------------------


def test_ac4f_anchors_are_not_clear_even_alone_on_the_features_sheet() -> None:
    """The fail-first half: at ac4f's anchors the tap callout breaks the top
    border and the dowel callout lies on the plan -- a seed must move."""
    sheet = _split(AC4F)[drawing.FEATURES_SHEET]
    rims = _rims()
    for label in ("RD2", "RD3"):
        item = next(a for a in sheet.annotations if a.label == label)
        obstacles = sheet_obstacles(sheet, skip_labels=(label,))
        callout = drawing.hole_callout(item, rim=rims[label])
        assert drawing.callout_conflict(callout, 0.0, 0.0, obstacles) is not None


def test_each_callout_seed_is_already_clear_on_the_features_sheet() -> None:
    """At the recipe's seeds, with the other two callouts at theirs, the
    planner accepts each callout where it stands: no move, no search."""
    sheet = _seeded_features_sheet()
    rims = _rims()
    for label in ("RD1", "RD2", "RD3"):
        item = next(a for a in sheet.annotations if a.label == label)
        obstacles = sheet_obstacles(sheet, skip_labels=(label,))
        callout = drawing.hole_callout(item, rim=rims[label])
        assert drawing.callout_conflict(callout, 0.0, 0.0, obstacles) is None, label
        conflict = lambda dx, dy, c=callout, o=obstacles: drawing.callout_conflict(c, dx, dy, o)  # noqa: E731
        assert drawing.plan_shift(label, callout.text, conflict, obstacles) == (0.0, 0.0)


def _tap_rim(name: str) -> tuple[float, float, float]:
    return (
        *drawing.plan_xy(drawing.FEATURE_CENTER, *drawing.POST_MOUNT_TAPS[name]),
        blind_cut_dia_mm(POST_MOUNT_SPEC) / 2 * drawing.PLAN_SCALE,
    )


def test_the_callout_rims_are_where_ac4f_drew_the_leaders() -> None:
    """The rims the offline tests use are the ones the seat's leaders cross:
    the arrow runs across the hole, so two of each leader's ends lie on its
    rim, 0.15 mm either way (the dump prints 0.1 mm).  RD2 is the exception
    that F2 fixes: ac4f (and 24cb) drew it to the EAST tap, mount_edges[0];
    the recipe now names the west one."""
    rims = {**_rims(), "RD2": _tap_rim("east")}
    for label, (cx, cy, radius) in rims.items():
        item = next(a for a in AC4F.annotations if a.label == label)
        ends = {
            end
            for s in item.segments
            if abs(s.y0 - s.y1) > 1e-9
            for end in ((s.x0, s.y0), (s.x1, s.y1))
        }
        on_rim = [end for end in ends if abs(math.dist(end, (cx, cy)) - radius) < 0.00015]
        assert len(on_rim) == 2, (label, sorted(ends))


def test_the_seeded_callouts_clear_the_detail_circles_on_their_plan() -> None:
    """Details B and D are circled ON the hole-location plan; the dump cannot
    see those sketch circles, so each seeded callout's text and leader keep
    2 mm off both here."""
    circles = {
        "B": (
            drawing.plan_xy(drawing.FEATURE_CENTER, 0.0, drawing.DETAIL_MODEL_Z),
            drawing.DETAIL_RADIUS_MM * drawing.PLAN_SCALE,
        ),
        "D": (
            drawing.plan_xy(drawing.FEATURE_CENTER, *part.NOTCH_CAP_E_XZ),
            drawing.CAP_DETAIL_RADIUS_MM * drawing.PLAN_SCALE,
        ),
    }
    sheet = _seeded_features_sheet()
    for label in ("RD1", "RD2", "RD3"):
        item = next(a for a in sheet.annotations if a.label == label)
        for name, (centre, radius) in circles.items():
            for s in item.segments:
                run = ((s.x0, s.y0), (s.x1, s.y1))
                assert _drawing_leaders.distance_to_point(run, centre) - radius >= 0.002, (label, name)
            for box in item.text_boxes:
                nearest = (
                    min(max(centre[0], box.xmin), box.xmax),
                    min(max(centre[1], box.ymin), box.ymax),
                )
                assert math.dist(nearest, centre) - radius >= 0.002, (label, name)


def test_a_blocked_callout_moves_to_the_nearest_clear_spot() -> None:
    """With the dowel callout's seed blocked by the plan, the search walks to
    the nearest clear spot, and that spot passes the same rule."""
    sheet = _split(AC4F)[drawing.FEATURES_SHEET]
    item = next(a for a in sheet.annotations if a.label == "RD3")
    obstacles = sheet_obstacles(sheet, skip_labels=("RD3",))
    callout = drawing.hole_callout(item, rim=_rims()["RD3"])
    conflict = lambda dx, dy: drawing.callout_conflict(callout, dx, dy, obstacles)  # noqa: E731
    dx, dy = drawing.plan_shift("RD3", callout.text, conflict, obstacles)
    assert (dx, dy) != (0.0, 0.0)
    assert conflict(dx, dy) is None
    assert math.hypot(dx, dy) < 0.020


def test_a_callout_with_no_clear_spot_fails_naming_every_box() -> None:
    sheet = _split(AC4F)[drawing.FEATURES_SHEET]
    item = next(a for a in sheet.annotations if a.label == "RD2")
    obstacles = sheet_obstacles(sheet, skip_labels=("RD2",))
    with pytest.raises(RuntimeError) as failure:
        drawing.plan_shift("RD2", drawing._text_union(item), lambda dx, dy: "blocked", obstacles)
    message = str(failure.value)
    assert "RD2: no clear spot" in message
    for view in sheet.views:
        assert view.name in message
    assert "keep-out title-block" in message


# --- the 2X tap callout's hole (24cb eye pass, F2) -------------------------------


def test_the_named_callout_tap_is_the_one_nearest_the_callout() -> None:
    """The tap the leader lands on is named, and it is the nearer of the two
    to both the callout's anchor and its seeded text: no leader crosses the
    plate to the far tap."""
    assert drawing.POST_MOUNT_CALLOUT_TAP == "west"
    assert set(drawing.POST_MOUNT_TAPS) == {"west", "east"}
    assert drawing.post_mount_callout_xz() == part.POST_MOUNT_WEST_XZ
    text = drawing._text_union(
        next(a for a in _seeded_features_sheet().annotations if a.label == "RD2")
    )
    text_centre = ((text.xmin + text.xmax) / 2, (text.ymin + text.ymax) / 2)
    for target in (drawing.POST_MOUNT_CALLOUT_XY, text_centre):
        nearest = min(
            drawing.POST_MOUNT_TAPS,
            key=lambda name: math.dist(
                drawing.plan_xy(drawing.FEATURE_CENTER, *drawing.POST_MOUNT_TAPS[name]),
                target,
            ),
        )
        assert nearest == drawing.POST_MOUNT_CALLOUT_TAP, target


def test_the_tap_callout_leader_stays_on_its_own_side_of_the_plate() -> None:
    """24cb's leader ran ~45 mm diagonally across the plate.  From the named
    tap the rim-to-shelf run is the shorter: under the east tap's, and under
    40 mm (the shelf under the text is the same either way)."""
    item = next(a for a in _seeded_features_sheet().annotations if a.label == "RD2")
    lengths = {}
    for name in drawing.POST_MOUNT_TAPS:
        run, _shelf = drawing.hole_callout(item, rim=_tap_rim(name)).leader(0.0, 0.0, (0.0, 0.0))
        lengths[name] = math.dist((run.x0, run.y0), (run.x1, run.y1))
    assert lengths["west"] < lengths["east"], lengths
    assert lengths["west"] < 0.040, lengths


class _Curve:
    def __init__(self, centre_mm: tuple[float, float], radius_m: float) -> None:
        self.params = (centre_mm[0] / 1000, 0.00635, centre_mm[1] / 1000, 0.0, 1.0, 0.0, radius_m)

    def IsCircle(self) -> bool:  # noqa: N802 - COM name
        return True

    @property
    def CircleParams(self) -> tuple[float, ...]:  # noqa: N802 - COM name
        return self.params


class _Edge:
    def __init__(self, name: str, centre_mm: tuple[float, float], radius_m: float) -> None:
        self.name = name
        self.curve = _Curve(centre_mm, radius_m)

    def GetCurve(self) -> _Curve:  # noqa: N802 - COM name
        return self.curve


class _PlanView:
    def __init__(self, edges: list[_Edge]) -> None:
        self.edges = edges

    def GetVisibleComponents(self) -> tuple[str, ...]:  # noqa: N802 - COM name
        return ("plate",)

    def GetVisibleEntities2(self, _component: str, _kind: int) -> list[_Edge]:  # noqa: N802 - COM name
        return self.edges


class _Attempting:
    @staticmethod
    def _attempt(call, default=None):
        return call()


def _plan_edges(*mount_names: str) -> list[_Edge]:
    """The plan's visible rims, the post-mount taps in the given order (their
    stations straight from the part, not from the recipe under test)."""
    taps = {"west": part.POST_MOUNT_WEST_XZ, "east": part.POST_MOUNT_EAST_XZ}
    mount_radius = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000
    north_dowel = min(POST_DOWEL_PLATE_XZ, key=lambda xz: math.hypot(*xz))
    south_dowel = max(POST_DOWEL_PLATE_XZ, key=lambda xz: math.hypot(*xz))
    return [
        _Edge("pivot", (0.0, 0.0), PIVOT_HOLE_DIA / 2000),
        *(_Edge(name, taps[name], mount_radius) for name in mount_names),
        _Edge("north dowel", north_dowel, PLATE_DOWEL_REAM_DIA / 2000),
        _Edge("south dowel", south_dowel, PLATE_DOWEL_REAM_DIA / 2000),
    ]


@pytest.mark.parametrize("order", [("east", "west"), ("west", "east")])
def test_the_tap_rim_is_picked_by_name_not_by_edge_order(order: tuple[str, str]) -> None:
    """SolidWorks listed the east rim first on 24cb; whatever the order, the
    callout gets the named (west) tap."""
    pivot, mount, dowel = drawing._visible_plan_controls(_Attempting(), _PlanView(_plan_edges(*order)))
    assert (pivot.name, mount.name, dowel.name) == ("pivot", "west", "north dowel")


def test_a_plan_without_the_named_tap_fails_naming_the_rims_it_saw() -> None:
    edges = _plan_edges("east", "east")
    with pytest.raises(RuntimeError, match=r"0 rim\(s\) at the west post-mount tap") as failure:
        drawing._visible_plan_controls(_Attempting(), _PlanView(edges))
    assert str(round(part.POST_MOUNT_EAST_XZ[0], 3)) in str(failure.value)


# --- the descriptive thread callouts (24cb eye pass, F1) --------------------------


class _CalloutNote:
    def __init__(self, text: str) -> None:
        self.text = text
        self.annotation: _ThreadAnnotation | None = None

    def GetText(self) -> str:  # noqa: N802 - COM name
        return self.text

    def GetAnnotation(self) -> "_ThreadAnnotation | None":  # noqa: N802 - COM name
        return self.annotation


class _Thread:
    def __init__(self, callout: _CalloutNote | None) -> None:
        self.callout = callout

    @property
    def ThreadCallout(self) -> _CalloutNote | None:  # noqa: N802 - COM name
        return self.callout


class _ThreadAnnotation:
    """An IAnnotation: a cosmetic thread (1), a note (6) or a dimension (4)."""

    def __init__(
        self, drawing_model: "_ThreadDrawing", kind: int, specific, name: str = ""
    ) -> None:
        self.model, self.kind, self.specific, self.name = drawing_model, kind, specific, name
        self.Layer = ""

    def GetName(self) -> str:  # noqa: N802 - COM name
        return self.name

    def GetType(self) -> int:  # noqa: N802 - COM name
        return self.kind

    def GetSpecificAnnotation(self):  # noqa: N802 - COM name
        return self.specific

    def Select2(self, append: bool, mark: int) -> bool:  # noqa: N802 - COM name
        self.model.selected.append(self)
        return True


class _ThreadView:
    def __init__(self) -> None:
        self.annotations: list[_ThreadAnnotation] = []

    def GetAnnotations(self) -> list[_ThreadAnnotation]:  # noqa: N802 - COM name
        return list(self.annotations)


class _ThreadDrawing:
    """EditDelete removes the selection from the view; ``refuse`` keeps it
    (a delete SolidWorks silently ignores); ``stale`` leaves the thread still
    naming its deleted callout."""

    def __init__(self, view: _ThreadView, *, refuse: bool = False, stale: bool = False) -> None:
        self.view, self.refuse, self.stale = view, refuse, stale
        self.selected: list[_ThreadAnnotation] = []
        self.deleted: list[_ThreadAnnotation] = []
        self.rebuilds = 0

    def ClearSelection2(self, _all: bool) -> bool:  # noqa: N802 - COM name
        self.selected.clear()
        return True

    def EditDelete(self) -> None:  # noqa: N802 - COM name
        if self.refuse:
            return
        for annotation in self.selected:
            self.view.annotations = [
                kept for kept in self.view.annotations if kept.name != annotation.name
            ]
            self.deleted.append(annotation)
            if annotation.kind == 6 and not self.stale:
                for other in self.view.annotations:
                    if other.kind == 1 and other.specific.callout is annotation.specific:
                        other.specific.callout = None

    def EditRebuild3(self) -> bool:  # noqa: N802 - COM name
        self.rebuilds += 1
        return True


class _ThreadAdapter:
    def __init__(self, model: _ThreadDrawing) -> None:
        self.currentModel = model


def _plan_with_thread(
    *, callouts: int = 1, refuse: bool = False, twin_wrappers: bool = False, stale: bool = False
) -> tuple[_ThreadAdapter, _ThreadView]:
    """A plan whose cosmetic thread carries its descriptive callout, as 24cb's
    DetailItem357 (and the profile's DetailItem351) read.  ``twin_wrappers``
    hands the thread's route a second wrapper of the same note, as COM may."""
    view = _ThreadView()
    model = _ThreadDrawing(view, refuse=refuse, stale=stale)
    for index in range(callouts):
        name = f"DetailItem{357 + index}"
        note = _CalloutNote("1/4-20 Tapped Hole")
        note_annotation = _ThreadAnnotation(model, 6, note, name)
        note.annotation = (
            _ThreadAnnotation(model, 6, note, name) if twin_wrappers else note_annotation
        )
        view.annotations += [
            _ThreadAnnotation(model, 1, _Thread(note), f"CThread{index}"),
            note_annotation,
        ]
    view.annotations.append(
        _ThreadAnnotation(model, 6, _CalloutNote("DRILL THRU"), "DetailItem400")
    )
    return _ThreadAdapter(model), view


def test_the_plan_thread_callout_is_deleted_and_read_back_gone() -> None:
    adapter, view = _plan_with_thread()
    drawing._delete_thread_callouts(adapter, view, label="feature plan")
    assert [a.specific.text for a in adapter.currentModel.deleted] == ["1/4-20 Tapped Hole"]
    assert drawing._thread_callout_notes(view) == []
    # The thread's ink and every other note stay.
    assert [a.kind for a in view.annotations] == [1, 6]
    assert view.annotations[1].specific.text == "DRILL THRU"


def test_one_note_reached_by_its_thread_and_by_its_text_counts_once() -> None:
    adapter, view = _plan_with_thread(twin_wrappers=True)
    assert [text for text, _annotation in drawing._thread_callout_notes(view)] == [
        "1/4-20 Tapped Hole"
    ]
    drawing._delete_thread_callouts(adapter, view, label="feature plan")
    assert drawing._thread_callout_notes(view) == []


def test_a_thread_still_naming_its_deleted_callout_does_not_fail_the_read_back() -> None:
    """Gone means gone from the view (what the audit and finalize read), not
    a thread property that has yet to let go."""
    adapter, view = _plan_with_thread(stale=True)
    drawing._delete_thread_callouts(adapter, view, label="feature plan")
    assert drawing._thread_callout_notes(view, reach="on_view") == []


def test_a_thread_callout_that_survives_its_delete_fails_loud() -> None:
    adapter, view = _plan_with_thread(refuse=True)
    with pytest.raises(RuntimeError, match=r"feature plan: 1 thread callout\(s\) survived deletion"):
        drawing._delete_thread_callouts(adapter, view, label="feature plan")


@pytest.mark.parametrize("callouts", [0, 2])
def test_a_plan_without_exactly_one_thread_callout_fails_with_the_count(callouts: int) -> None:
    adapter, view = _plan_with_thread(callouts=callouts)
    with pytest.raises(RuntimeError, match=f"expected 1 'Tapped Hole' thread callout, read {callouts}"):
        drawing._delete_thread_callouts(adapter, view, label="profile plan")
    assert adapter.currentModel.deleted == []


def test_the_profile_hides_only_the_thread_ink_and_leaves_no_hidden_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DetailItem351 was layered out of sight; it is deleted now, so the
    hidden layer carries the thread ink alone."""

    class _Layer:
        Visible = True
        Printable = False

    class _Layers:
        def GetLayer(self, _name: str) -> _Layer:  # noqa: N802 - COM name
            return _Layer()

    adapter, view = _plan_with_thread()
    adapter.currentModel.GetLayerManager = lambda: _Layers()  # noqa: N802 - COM name
    drawing._hide_profile_cosmetic_threads(adapter, view)
    layered = {a.kind: a.Layer for a in view.annotations if a.Layer}
    assert layered == {1: drawing._COSMETIC_THREAD_LAYER}
    drawing._delete_thread_callouts(adapter, view, label="profile plan")
    assert not [a for a in view.annotations if a.Layer and a.kind != 1]


def test_both_plans_lose_their_thread_callout_and_finalize_trips_on_a_survivor() -> None:
    source = inspect.getsource(drawing.build)
    assert '_delete_thread_callouts(adapter, profile, label="profile plan")' in source
    assert '_delete_thread_callouts(adapter, feature, label="feature plan")' in source
    # Before the callouts are seeded and the sheets are read for placement.
    assert source.index("_delete_thread_callouts(adapter, feature") < source.index(
        "add_native_hole_callout("
    )
    assert "redundant_note_substrings=(THREAD_CALLOUT_TEXT,)" in source
    assert "expected_redundant_notes=0" in source
    hide = inspect.getsource(drawing._hide_profile_cosmetic_threads)
    assert "ThreadCallout" not in hide


# --- the sheet numbers ----------------------------------------------------------


def _sheet_number(
    sheet: SheetGeometry, number: int, anchor: tuple[float, float]
) -> AnnotationGeometry:
    """The note as a 3.5 mm line at ``anchor`` (the seat reads its real box)."""
    box = estimate_text_box(
        f"SHEET {number} OF 2", anchor=anchor, height=0.0035, advance_ratio=sheet.advance_ratio
    )
    return AnnotationGeometry("SheetNumber", "note", "sheet", (box,), (), anchor, False)


def test_the_plans_sheet_number_stands_at_the_package_spot() -> None:
    """Detail D left sheet 1, so the harmonic-base spot is clear there."""
    assert drawing.SHEET_NUMBER_XY[drawing.PLANS_SHEET] == (0.350, 0.263)
    plans = _split(AC4F)[drawing.PLANS_SHEET]
    note = _sheet_number(plans, 1, drawing.SHEET_NUMBER_XY[drawing.PLANS_SHEET])
    assert drawing.text_conflict(note, 0.0, 0.0, sheet_obstacles(plans)) is None


def test_the_features_sheet_number_sits_left_of_detail_d_on_the_same_line() -> None:
    """At the package spot detail D covers it; the seed on the features sheet
    keeps the line and is clear with every callout at its seed."""
    features = _seeded_features_sheet()
    obstacles = sheet_obstacles(features)
    blocked = _sheet_number(features, 2, drawing.SHEET_NUMBER_XY[drawing.PLANS_SHEET])
    assert "Detail View D" in drawing.text_conflict(blocked, 0.0, 0.0, obstacles)
    seed = drawing.SHEET_NUMBER_XY[drawing.FEATURES_SHEET]
    assert seed[1] == drawing.SHEET_NUMBER_XY[drawing.PLANS_SHEET][1]
    note = _sheet_number(features, 2, seed)
    assert drawing.text_conflict(note, 0.0, 0.0, obstacles) is None


# --- the plate thickness invariant ----------------------------------------------


def test_the_one_plate_thickness_sits_with_section_a_a() -> None:
    sheets = list(_split(AC4F).values())
    item = drawing.plate_thickness_annotation(sheets, "Section View A-A")
    assert item.owner == "Section View A-A"


def test_no_plate_thickness_is_refused() -> None:
    sheets = [
        replace(s, annotations=tuple(a for a in s.annotations if a.label != "PlateThk"))
        for s in _split(AC4F).values()
    ]
    with pytest.raises(RuntimeError, match="expected one plate thickness"):
        drawing.plate_thickness_annotation(sheets, "Section View A-A")


def test_a_plate_thickness_on_each_sheet_is_refused() -> None:
    split = _split(AC4F)
    thickness = next(a for a in split["FEATURES"].annotations if a.label == "PlateThk")
    plans = replace(split["PLANS"], annotations=(*split["PLANS"].annotations, thickness))
    with pytest.raises(RuntimeError, match="expected one plate thickness"):
        drawing.plate_thickness_annotation([plans, split["FEATURES"]], "Section View A-A")


def test_a_plate_thickness_away_from_section_a_a_is_refused() -> None:
    split = _split(AC4F)
    thickness = next(a for a in split["FEATURES"].annotations if a.label == "PlateThk")
    plans = replace(split["PLANS"], annotations=(*split["PLANS"].annotations, thickness))
    features = replace(
        split["FEATURES"],
        annotations=tuple(a for a in split["FEATURES"].annotations if a.label != "PlateThk"),
    )
    with pytest.raises(RuntimeError, match="not on the sheet carrying"):
        drawing.plate_thickness_annotation([plans, features], "Section View A-A")


# --- the per-sheet layout audit -------------------------------------------------


class _Sheet:
    def __init__(self, name: str) -> None:
        self.name = name

    def GetName(self) -> str:  # noqa: N802 - COM name
        return self.name


class _Drawing:
    """Just enough IDrawingDoc for sheet activation."""

    def __init__(self) -> None:
        self.current = drawing.SHEET_NAMES[0]
        self.activated: list[str] = []

    def ActivateSheet(self, name: str) -> bool:  # noqa: N802 - COM name
        self.current = name
        self.activated.append(name)
        return True

    def GetCurrentSheet(self) -> _Sheet:  # noqa: N802 - COM name
        return _Sheet(self.current)


class _Adapter:
    def __init__(self) -> None:
        self.currentModel = _Drawing()


_REGION = DrawableRegion(0.0127, 0.0127, 0.4191, 0.2667)


def _audited_sheets(monkeypatch: pytest.MonkeyPatch, crowded: set[str]) -> _Adapter:
    """Feed the REAL check_drawing_layout one element set per active sheet;
    each sheet in ``crowded`` carries two overlapping notes."""
    adapter = _Adapter()

    def collect(adapter_: _Adapter, *, layout: DrawingLayout):
        name = adapter_.currentModel.current
        elements = [LayoutElement(f"{name} view", "view", 0.05, 0.05, 0.10, 0.10)]
        if name in crowded:
            elements += [
                LayoutElement("note one", "note", 0.20, 0.20, 0.25, 0.21, scope=CollisionScope.ALL),
                LayoutElement("note two", "note", 0.22, 0.20, 0.27, 0.21, scope=CollisionScope.ALL),
            ]
        return elements, [], _REGION

    monkeypatch.setattr(_drawing_common, "collect_layout_elements", collect)
    return adapter


def test_the_layout_audit_passes_when_both_sheets_are_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _audited_sheets(monkeypatch, set())
    drawing.check_every_sheet_layout(adapter)
    assert adapter.currentModel.activated == list(drawing.SHEET_NAMES)


def test_an_overlap_on_sheet_2_alone_fails_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _audited_sheets(monkeypatch, {"FEATURES"})
    with pytest.raises(RuntimeError) as failure:
        drawing.check_every_sheet_layout(adapter)
    message = str(failure.value)
    assert "failed on 1 of 2 sheets" in message
    assert "sheet 2 FEATURES" in message
    assert "sheet 1 PLANS" not in message
    assert adapter.currentModel.activated == list(drawing.SHEET_NAMES)


def test_an_overlap_on_sheet_1_alone_fails_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _audited_sheets(monkeypatch, {"PLANS"})
    with pytest.raises(RuntimeError, match="sheet 1 PLANS"):
        drawing.check_every_sheet_layout(adapter)


# --- the placement round trip ---------------------------------------------------


class _Annotation:
    """Just enough IAnnotation for a read-back placement."""

    def __init__(self, name: str, position: tuple[float, float]) -> None:
        self.name = name
        self.position = position
        self.moves: list[tuple[float, float]] = []

    def GetName(self) -> str:  # noqa: N802 - COM name
        return self.name

    def GetPosition(self) -> tuple[float, float, float]:  # noqa: N802 - COM name
        return (*self.position, 0.0)

    def SetPosition2(self, x: float, y: float, z: float) -> bool:  # noqa: N802 - COM name
        self.moves.append((x, y))
        self.position = (x, y)
        return True


class _Model:
    def EditRebuild3(self) -> bool:  # noqa: N802 - COM name
        return True


class _PlacingAdapter:
    def __init__(self) -> None:
        self.currentModel = _Model()


def _with_note(sheet: SheetGeometry, anchor: tuple[float, float]) -> tuple[SheetGeometry, AnnotationGeometry]:
    note = replace(_sheet_number(sheet, 2, anchor), label="DetailItem900")
    return replace(sheet, annotations=(*sheet.annotations, note)), note


def test_a_blocked_note_is_moved_by_its_planned_shift_and_read_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded on detail D, the note moves by the planned shift through
    SetPosition2, and the sheet returned carries the re-read geometry."""
    features = _seeded_features_sheet()
    seed_xy = drawing.SHEET_NUMBER_XY[drawing.PLANS_SHEET]
    sheet, note = _with_note(features, seed_xy)
    annotation = _Annotation(note.label, seed_xy)

    def read_back(_adapter, raw, *, owner, advance_ratio):
        dx = raw.position[0] - seed_xy[0]
        dy = raw.position[1] - seed_xy[1]
        moved = tuple(Box(b.xmin + dx, b.ymin + dy, b.xmax + dx, b.ymax + dy) for b in note.text_boxes)
        return replace(note, text_boxes=moved, position=raw.position)

    monkeypatch.setattr(drawing, "annotation_geometry", read_back)
    placed = drawing._place_clear(
        _PlacingAdapter(),
        annotation,
        sheet=sheet,
        label="sheet number",
        owner=None,
        conflict_for=drawing._text_rule,
    )
    assert len(annotation.moves) == 1
    final = next(a for a in placed.annotations if a.label == note.label)
    obstacles = sheet_obstacles(sheet, skip_labels=(note.label,))
    assert drawing.placed_conflicts(final, obstacles) == []
    assert [a.label for a in placed.annotations].count(note.label) == 1


def test_a_read_back_that_is_not_clear_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seat has the last word: a clear plan whose read-back lands on
    detail D fails the build, naming what it hit and every box."""
    features = _seeded_features_sheet()
    seed_xy = drawing.SHEET_NUMBER_XY[drawing.FEATURES_SHEET]
    sheet, note = _with_note(features, seed_xy)
    blocked = _sheet_number(features, 2, drawing.SHEET_NUMBER_XY[drawing.PLANS_SHEET])
    calls = []

    def read_back(_adapter, raw, *, owner, advance_ratio):
        calls.append(raw.name)
        return replace(blocked, label=note.label)

    monkeypatch.setattr(drawing, "annotation_geometry", read_back)
    with pytest.raises(RuntimeError) as failure:
        drawing._place_clear(
            _PlacingAdapter(),
            _Annotation(note.label, seed_xy),
            sheet=sheet,
            label="sheet number",
            owner=None,
            conflict_for=drawing._text_rule,
        )
    message = str(failure.value)
    assert "read back where it was moved, DetailItem900 is not clear" in message
    assert "Detail View D" in message and "keep-out title-block" in message
    assert calls == [note.label]


def test_a_callout_is_found_by_name_and_owning_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """SolidWorks names hole callouts per view: an RD2 on section A-A must
    neither be taken for the plan's RD2 nor be dropped from its obstacles."""
    sheet = _seeded_features_sheet()
    plan_rd2 = next(a for a in sheet.annotations if a.label == "RD2")
    twin = replace(plan_rd2, owner="Section View A-A")
    sheet = replace(sheet, annotations=(*sheet.annotations, twin))
    rim = _rims()["RD2"]
    seen: list[AnnotationGeometry] = []

    def read_back(_adapter, raw, *, owner, advance_ratio):
        return replace(plan_rd2, owner=owner)

    def rule(seed, obstacles):
        seen.append(seed)
        assert twin.text_boxes[0] in [box for label, box in obstacles.texts if label == "RD2"]
        return drawing._callout_rule(rim)(seed, obstacles)

    monkeypatch.setattr(drawing, "annotation_geometry", read_back)
    with pytest.raises(RuntimeError, match="not clear"):
        # The twin sits on the plan's RD2 exactly, so the plan's own read-back
        # cannot clear it: proof the twin stayed an obstacle.
        drawing._place_clear(
            _PlacingAdapter(),
            _Annotation("RD2", drawing.POST_MOUNT_CALLOUT_XY),
            sheet=sheet,
            label="tap callout",
            owner="Drawing View2",
            conflict_for=rule,
        )
    assert [seed.owner for seed in seen] == ["Drawing View2"]
    with pytest.raises(RuntimeError, match="read 2 times"):
        drawing._place_clear(
            _PlacingAdapter(),
            _Annotation("RD2", drawing.POST_MOUNT_CALLOUT_XY),
            sheet=sheet,
            label="tap callout",
            owner=None,
            conflict_for=rule,
        )


# --- the one box reader ---------------------------------------------------------


class _Data:
    """IDisplayData: one line and one text run."""

    def __init__(self, line: tuple[float, ...], text: str, at: tuple[float, float]) -> None:
        self.line, self.text, self.at = line, text, at

    def GetLineCount(self) -> int:  # noqa: N802 - COM name
        return 1

    def GetLineAtIndex3(self, _index: int) -> tuple[float, ...]:  # noqa: N802 - COM name
        return (0, 0, 0, 0, *self.line)

    def GetArcCount(self) -> int:  # noqa: N802 - COM name
        return 0

    def GetTextCount(self) -> int:  # noqa: N802 - COM name
        return 1

    def GetTextAtIndex(self, _index: int) -> str:  # noqa: N802 - COM name
        return self.text

    def GetTextHeightAtIndex(self, _index: int) -> float:  # noqa: N802 - COM name
        return 0.0035

    def GetTextPositionAtIndex(self, _index: int) -> tuple[float, float, float]:  # noqa: N802
        return (*self.at, 0.0)

    def GetTextRefPositionAtIndex(self, _index: int) -> int:  # noqa: N802 - COM name
        return 1

    def GetTextAngleAtIndex(self, _index: int) -> float:  # noqa: N802 - COM name
        return 0.0


class _Note:
    def __init__(self, extent: tuple[float, ...]) -> None:
        self.extent = extent

    def GetExtent(self) -> tuple[float, ...]:  # noqa: N802 - COM name
        return self.extent


class _ReadAnnotation:
    """IAnnotation as the audit reader walks it."""

    def __init__(self, name, kind, data, *, note=None, owner_type=0) -> None:
        self.name, self.kind, self.data, self.note = name, kind, data, note
        self.OwnerType = owner_type
        self.Visible = 1

    def GetType(self) -> int:  # noqa: N802 - COM name
        return self.kind

    def GetName(self) -> str:  # noqa: N802 - COM name
        return self.name

    def GetPosition(self) -> tuple[float, float, float]:  # noqa: N802 - COM name
        return (*self.data.at, 0.0)

    def GetDisplayData(self) -> _Data:  # noqa: N802 - COM name
        return self.data

    def GetSpecificAnnotation(self):  # noqa: N802 - COM name
        return self.note

    def GetLeaderCount(self) -> int:  # noqa: N802 - COM name
        return 0


class _ReadView:
    def __init__(self, name, outline, annotations) -> None:
        self.Name, self.outline, self.annotations = name, outline, annotations
        self.ScaleRatio = (1.0, 2.0)

    def GetOutline(self):  # noqa: N802 - COM name
        return self.outline

    def GetOrientationName(self) -> str:  # noqa: N802 - COM name
        return "*Top"

    def GetAnnotations(self):  # noqa: N802 - COM name
        return self.annotations

    def GetTableAnnotations(self):  # noqa: N802 - COM name
        return []


class _ReadSheet:
    def GetName(self) -> str:  # noqa: N802 - COM name
        return "FEATURES"

    def GetProperties2(self):  # noqa: N802 - COM name
        return (0, 0, 1.0, 2.0, False, 0.4318, 0.2794, False)

    def GetZoneMargin(self, _side: int) -> float:  # noqa: N802 - COM name
        return 0.0127


class _ReadDrawing:
    def __init__(self, views) -> None:
        self.views = views

    def GetType(self) -> int:  # noqa: N802 - COM name
        return 3

    def GetViews(self):  # noqa: N802 - COM name
        return [[_ReadView("FEATURES", None, []), *self.views]]

    def Sheet(self, _name: str) -> _ReadSheet:  # noqa: N802 - COM name
        return _ReadSheet()


def test_one_annotation_reads_back_exactly_as_the_sheet_read_boxes_it() -> None:
    """``annotation_geometry`` is ``collect_document``'s own per-annotation
    read: with the sheet's owner and calibrated advance, a re-read callout
    and note equal what the whole-sheet read produced -- one box reader."""
    from diagnostics.drawing_layout_audit import annotation_geometry, collect_document

    callout = _ReadAnnotation(
        "RD2",
        4,
        _Data((0.1702, 0.2352, 0.0, 0.2050, 0.2170, 0.0), "M6 TAP", (0.2060, 0.2170)),
    )
    note = _ReadAnnotation(
        "DetailItem900",
        6,
        _Data((0.0, 0.0, 0.0, 0.0, 0.0, 0.0), "SHEET 2 OF 2", (0.2650, 0.2630)),
        note=_Note((0.2650, 0.2595, 0.0, 0.2958, 0.2630, 0.0)),
    )
    views = [_ReadView("Drawing View2", (0.1594, 0.1286, 0.2006, 0.2514), [callout, note])]
    drawing_doc = _ReadDrawing(views)
    [sheet] = collect_document(object(), drawing_doc)
    by_label = {item.label: item for item in sheet.annotations}
    assert set(by_label) == {"RD2", "DetailItem900"}
    assert by_label["DetailItem900"].exact and by_label["RD2"].text_boxes
    for raw in (callout, note):
        again = annotation_geometry(
            object(), raw, owner="Drawing View2", advance_ratio=sheet.advance_ratio
        )
        assert again == by_label[raw.name]
