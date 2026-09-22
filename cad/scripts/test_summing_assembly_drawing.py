"""Behavioral boundary contract for the summing assembly package."""

import _config
import build_summing_assembly
import draw_summing_assembly
import knife_hanger_stud_spec
import summing_assembly_spec as assembly_spec
from _buildgraph import references_of


def test_bom_tracks_direct_assembly_sources_and_released_part_identities() -> None:
    direct = {stem.replace("_", "-") for stem in references_of("summing")}
    assert set(assembly_spec.BOM_QUANTITIES) == direct
    assert assembly_spec.BOM_QUANTITIES == {
        stem: int(_config.parts(stem)["quantity"]) for stem in direct
    }
    assert assembly_spec.BOM_PART_NUMBERS == {
        stem: str(_config.parts(stem)["number"]) for stem in direct
    }
    assert set(assembly_spec.BOM_DESCRIPTIONS) == direct


def test_frame_and_channel_interfaces_are_identified_without_duplication() -> None:
    direct = {stem.replace("_", "-") for stem in references_of("summing")}
    interfaces = assembly_spec.EXTERNAL_INTERFACES
    assert set(interfaces) == {
        "top-frame",
        "gooseneck-set-screw",
        "spring-hook",
        "channel-spring-installed",
    }
    assert direct.isdisjoint(interfaces)
    assert interfaces == {
        stem: (
            str(_config.parts(stem)["number"]),
            int(_config.parts(stem)["quantity"]),
        )
        for stem in interfaces
    }


def test_stud_trim_note_agrees_with_the_assembly_hanger_fit_reference() -> None:
    hanger_fit_sheet = draw_summing_assembly.SHEET_NAMES[3]
    expected_head = (
        f"TRIM/INSPECT TO {build_summing_assembly.DRAWING_NUMBER} "
        f"SHEET {draw_summing_assembly.SHEET_NAMES.index(hanger_fit_sheet) + 1}, "
        f"{hanger_fit_sheet}, DETAIL {draw_summing_assembly.HANGER_DETAIL_LABEL}."
    )
    assert knife_hanger_stud_spec.DRAWING_NOTES.splitlines()[0] == expected_head


def test_bom_rows_may_grow_to_the_native_minimum_but_never_shrink() -> None:
    requested = draw_summing_assembly.BOM_ROW_HEIGHT
    assert draw_summing_assembly.bom_row_fit(requested, requested) == "exact"
    assert draw_summing_assembly.bom_row_fit(requested, requested + 1e-7) == "exact"
    assert draw_summing_assembly.bom_row_fit(requested, 0.0085) == "grown"
    assert draw_summing_assembly.bom_row_fit(requested, 0.0) == "short"
    assert draw_summing_assembly.bom_row_fit(requested, requested - 1e-5) == "short"


def test_bom_budget_uses_measured_extents_against_sheet_and_title_block() -> None:
    anchor = draw_summing_assembly.BOM_ANCHOR
    width = sum(draw_summing_assembly.BOM_COLUMN_WIDTHS.values())
    rows = len(assembly_spec.BOM_COMPONENTS) + 1
    assert draw_summing_assembly.bom_extent_violations(
        anchor, width, rows * draw_summing_assembly.BOM_ROW_HEIGHT
    ) == []
    # A doubled header (two-line wrap) still fits.
    assert draw_summing_assembly.bom_extent_violations(
        anchor, width, (rows + 1) * draw_summing_assembly.BOM_ROW_HEIGHT
    ) == []
    # A table tall enough to reach the title block is refused by name.
    violations = draw_summing_assembly.bom_extent_violations(anchor, width, 0.190)
    assert len(violations) == 1
    assert "title block" in violations[0]
    wide = draw_summing_assembly.bom_extent_violations(anchor, 0.300, 0.050)
    assert any("right edge" in violation for violation in wide)


class _LateBoundCurve:
    """A late-bound ICurve: no-argument methods read as plain values."""

    def __init__(self, identity: int, circle_params: tuple[float, ...] = ()) -> None:
        self.Identity = identity
        self.CircleParams = circle_params


class _EarlyBoundCurve:
    def __init__(self, late: _LateBoundCurve) -> None:
        self._late = late
        self.CircleParams = late.CircleParams

    def Identity(self) -> int:
        return self._late.Identity

    def IsCircle(self) -> bool:
        return self._late.Identity == 3002

    def IsLine(self) -> bool:
        return self._late.Identity == 3001

    def IsBcurve(self) -> bool:
        return self._late.Identity == 3005


class _Edge:
    def __init__(self, curve: _LateBoundCurve) -> None:
        self._curve = curve

    def GetCurve(self) -> _LateBoundCurve:
        return self._curve


class _Transform:
    # Identity rotation, origin at y = 500 mm, scale 1.
    ArrayData = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0.0, 0.5, 0.0, 1.0, 0, 0, 0)


class _Body:
    def __init__(self, edges: list[_Edge]) -> None:
        self._edges = edges

    def GetBodyBox(self) -> tuple[float, ...]:
        return (-0.006, -0.03, -0.006, 0.006, 0.01, 0.006)

    def GetEdges(self) -> list[_Edge]:
        return self._edges


class _Component:
    Name2 = "summing/knife-hanger-stud-1"
    Transform2 = _Transform()

    def __init__(self, edges: list[_Edge]) -> None:
        self._edges = edges

    def GetPathName(self) -> str:
        return "C:/cad/out/sldprt/knife-hanger-stud.SLDPRT"

    def GetBodies2(self, body_type: int) -> list[_Body]:
        assert body_type == 0
        return [_Body(self._edges)]


class _DrawingComponent:
    def __init__(self, component: _Component) -> None:
        self.Component = component


class _View:
    def __init__(self, component: _Component, edges: list[_Edge]) -> None:
        self._component = component
        self._edges = edges

    def GetName2(self) -> str:
        return "Detail View B (4 : 1)"

    def GetVisibleDrawingComponents(self) -> list[_DrawingComponent]:
        return [_DrawingComponent(self._component)]

    def GetVisibleComponents(self) -> list[_Component]:
        return [self._component]

    def GetVisibleEntities2(self, component: _Component, kind: int) -> list[_Edge]:
        return self._edges if kind == 1 else []


class _BrokenView(_View):
    def GetVisibleEntities2(self, component: _Component, kind: int) -> list[_Edge]:
        raise RuntimeError("seat went away")


def _bind_curves(obj, interface):
    """Offline stand-in for _common._early_bound: only ICurve changes shape."""
    if interface == "ICurve" and isinstance(obj, _LateBoundCurve):
        return _EarlyBoundCurve(obj)
    return obj


def _census_events(monkeypatch, view) -> dict[str, list[dict]]:
    events: dict[str, list[dict]] = {}
    monkeypatch.setattr(draw_summing_assembly, "_early_bound", _bind_curves)
    monkeypatch.setattr(
        draw_summing_assembly._telemetry,
        "event",
        lambda name, **attributes: events.setdefault(name, []).append(attributes),
    )
    draw_summing_assembly._census_component_geometry(
        (("detail", view),),
        component_stem="knife-hanger-stud",
        target_y_mm=495.0,
        label="finished tip",
    )
    return events


def test_stud_census_binds_late_bound_curves_before_calling_identity(
    monkeypatch,
) -> None:
    # r6 died on "'int' object is not callable": Identity() on a late-bound
    # curve. The census must bind ICurve first and classify every edge.
    tip = _LateBoundCurve(3002, (0.0, -0.005, 0.0, 0.0, 1.0, 0.0, 0.00508094))
    helix = _LateBoundCurve(3005)
    edges = [_Edge(tip), _Edge(helix)]
    component = _Component(edges)
    events = _census_events(monkeypatch, _View(component, edges))

    (visible,) = events["drawing.visible_edge_kinds"]
    assert "error" not in visible
    assert visible["component"] == "knife-hanger-stud-1"
    assert visible["edge_kinds"] == (("bcurve", 1), ("circle", 1))
    (brep,) = events["drawing.brep_circle_census"]
    assert brep["error"] is None
    assert brep["circles"] == ("y=495.0 r=5.08094 x1",)
    assert brep["origin_mm"] == (0.0, 500.0, 0.0)
    assert brep["body_y_range_mm"] == (470.0, 510.0)


def test_stud_census_records_a_failing_section_and_keeps_going(monkeypatch) -> None:
    tip = _LateBoundCurve(3002, (0.0, -0.005, 0.0, 0.0, 1.0, 0.0, 0.00508094))
    component = _Component([_Edge(tip)])
    events = _census_events(monkeypatch, _BrokenView(component, []))

    (visible,) = events["drawing.visible_edge_kinds"]
    assert visible["error"] == "RuntimeError: seat went away"
    # The B-rep section still ran after the view section failed.
    (brep,) = events["drawing.brep_circle_census"]
    assert brep["circles"] == ("y=495.0 r=5.08094 x1",)


def test_built_hanger_engagement_is_judged_against_the_receiver_band() -> None:
    top = draw_summing_assembly.KNIFE_MOUNT_TOP_Y
    target = draw_summing_assembly.HANGER_ENGAGEMENT_TARGET_MM
    violations = draw_summing_assembly.hanger_engagement_violations
    # r7's B-rep reading: tip rim at 993.5765 under the 999.45 mount top.
    assert violations(top, 993.5765) == []
    assert violations(top, top - target) == []
    # A built tip off the stack target by more than the readback tolerance.
    drifted = violations(top, top - target - 0.01)
    assert len(drifted) == 1 and "stack target" in drifted[0]
    # A tip driven past the complete female thread and out of the print band.
    deep = violations(top, top - 7.0)
    assert any("complete female thread" in item for item in deep)
    assert any("printed band" in item for item in deep)
    # A mount whose built top is not where the stack says.
    assert any("knife-mount top" in item for item in violations(top + 0.5, 993.5765))
