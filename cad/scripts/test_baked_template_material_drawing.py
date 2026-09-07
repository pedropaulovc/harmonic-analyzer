"""Only an explicit material mode may change the linked value's vertical anchor."""

from copy import deepcopy
from contextlib import nullcontext
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _baked_template_layout as layout
from test_baked_template_layout_drawing import note
from test_title_cell_drawing import box_lines


def scene():
    notes = {
        "value": note(
            '$PRPSHEET:"Material"',
            "unresolved material",
            x=0.28,
            y=0.032,
            height=0.00238125,
            horizontal=1,
        ),
        "label": note(
            "MATERIAL", "MATERIAL", x=0.26, y=0.032, height=0.001524, horizontal=1
        ),
        "other": note("FINISH", "FINISH", x=0.26, y=0.021, horizontal=1),
    }
    lines = box_lines(0.25, 0.025, 0.42, 0.035)
    before = {
        "notes": notes,
        "units": [4, 0, 2],
        "template_geometry": layout.plain(lines),
        "surface_finishes": ["unchanged"],
    }
    return before, lines


def transformed():
    from diagnostics import _baked_template_material as material

    before, lines = scene()
    plan = material.material_plan(before["notes"], lines)
    after = deepcopy(before)
    value = after["notes"]["value"]
    value["vertical"] = 1
    value["position"] = plan["value"]["position"][:]
    value["extent"][1] -= 0.002
    value["display"]["texts"][0]["position"][1] -= 0.002
    return before, after, plan, lines


def test_material_plan_preserves_x_z_font_and_measures_cell_midpoint():
    from diagnostics import _baked_template_material as material

    before, lines = scene()
    original = deepcopy(before)
    plan = material.material_plan(before["notes"], lines)
    assert set(plan) == {"value"}
    assert plan["value"]["position"] == [0.28, (0.025 + 0.035) / 2, 0]
    assert plan["value"]["vertical"] == 1
    assert plan["value"]["height_m"] == before["notes"]["value"]["font"]["CharHeight"]
    assert before == original


def test_explicit_material_transition_passes_but_default_still_rejects_vertical():
    from diagnostics import _baked_template_material as material

    before, after, plan, lines = transformed()
    original = deepcopy((before, after, plan, lines))
    material.require_transition(before, after, plan, lines)
    assert (before, after, plan, lines) == original
    with pytest.raises(RuntimeError, match="outside explicit allowlist"):
        layout.require_transition(before, after, plan)


@pytest.mark.parametrize(
    "mode",
    [
        "label",
        "other",
        "text",
        "link",
        "font",
        "height",
        "geometry",
        "units",
        "sf",
        "horizontal",
        "clamped",
        "vertical",
        "glyph_text",
        "extra_plan",
        "invented_anchor",
    ],
)
def test_material_transition_rejects_every_unapproved_change(mode):
    from diagnostics import _baked_template_material as material

    before, after, plan, lines = transformed()
    value = after["notes"]["value"]
    if mode in ("label", "other"):
        after["notes"][mode]["vertical"] = 1
    if mode in ("text", "link"):
        value[mode] = "changed"
    if mode == "font":
        value["font"]["Bold"] = True
    if mode == "height":
        value["font"]["CharHeight"] /= 2
    if mode == "geometry":
        after["template_geometry"][0][0][0] += 0.001
    if mode == "units":
        after["units"][0] = 5
    if mode == "sf":
        after["surface_finishes"] = []
    if mode == "horizontal":
        value["horizontal"] = 2
    if mode == "clamped":
        value["position"][1] += 0.001
    if mode == "vertical":
        value["vertical"] = 0
    if mode == "glyph_text":
        value["display"]["texts"][0]["value"] = "changed"
    if mode == "extra_plan":
        plan["label"] = deepcopy(plan["value"])
    if mode == "invented_anchor":
        plan["value"]["position"][1] += 0.001
        value["position"] = plan["value"]["position"][:]
    with pytest.raises(RuntimeError, match="material|allowlist|clamped|font"):
        material.require_transition(before, after, plan, lines)


@pytest.mark.parametrize(
    "mode", ["locked", "horizontal", "wrong_vertical", "duplicate"]
)
def test_material_plan_rejects_unreviewed_start_state(mode):
    from diagnostics import _baked_template_material as material

    before, lines = scene()
    value = before["notes"]["value"]
    if mode == "locked":
        value["lock"] = "locked"
    if mode == "horizontal":
        value["horizontal"] = 2
    if mode == "wrong_vertical":
        value["vertical"] = 2
    if mode == "duplicate":
        before["notes"]["duplicate"] = deepcopy(value)
    with pytest.raises(RuntimeError, match="material|template note"):
        material.material_plan(before["notes"], lines)


@pytest.mark.parametrize("mode", ["accepted", "ignored", "clamped", "foreign_owner"])
def test_material_native_calls_stop_on_rejected_readback(monkeypatch, mode):
    from diagnostics import _baked_template_material as material

    before, lines = scene()
    plan = material.material_plan(before["notes"], lines)
    owner, model = object(), SimpleNamespace(Visible=True, GraphicsRedraw2=Mock())
    native_note = SimpleNamespace(
        LockPosition=False,
        PropertyLinkedText=material.MATERIAL_LINK,
        GetTextJustification=lambda: 1,
        GetTextVerticalJustification=Mock(
            side_effect=[0, 0 if mode == "ignored" else 1]
        ),
        SetTextVerticalJustification=Mock(),
    )
    annotation = SimpleNamespace(
        Owner=object() if mode == "foreign_owner" else owner,
        GetSpecificAnnotation=lambda: native_note,
        SetPosition2=Mock(return_value=True),
        GetPosition=lambda: (
            [0.28, 0.031, 0] if mode == "clamped" else plan["value"]["position"][:]
        ),
    )
    adapter = SimpleNamespace(
        currentModel=model,
        ownership=SimpleNamespace(assert_current_owned=Mock()),
        swApp=SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
    )
    monkeypatch.setattr(layout.cells, "required", lambda value, _: value)
    receipt = []
    if mode == "accepted":
        material.apply_layout(
            adapter, {"value": (annotation, owner)}, plan, receipt, Mock()
        )
        assert receipt[0]["calls"] == ["SetTextVerticalJustification", "SetPosition2"]
        native_note.SetTextVerticalJustification.assert_called_once_with(1)
        annotation.SetPosition2.assert_called_once_with(*plan["value"]["position"])
        model.GraphicsRedraw2.assert_called_once_with()
        return
    with pytest.raises(RuntimeError, match="material"):
        material.apply_layout(
            adapter, {"value": (annotation, owner)}, plan, receipt, Mock()
        )
    model.GraphicsRedraw2.assert_not_called()
    if mode in ("ignored", "foreign_owner"):
        annotation.SetPosition2.assert_not_called()


def test_blank_phase_is_persistence_only_and_population_fit_stays_strict():
    from diagnostics import _baked_template_material as material

    _before, after, plan, lines = transformed()
    labels = material.static_label_plan(after["notes"], lines, plan)
    assert set(labels) == {"label"}
    scope = material.phase_scope(after["notes"])
    assert (
        scope["unresolved_linked_field_fit"] == "deferred_until_owned_source_population"
    )
    # An actually resolved multiline value crossing a rule is not accepted by
    # the separate native/PDF containment gates, whatever the setter reports.
    after["notes"]["value"]["extent"][1] = 0.024
    with pytest.raises(RuntimeError, match="native extent"):
        layout.require_field_fit(after["notes"], plan)


def test_material_pdf_containment_does_not_accept_a_boundary_overrun(
    tmp_path, monkeypatch
):
    from diagnostics import probe_retained_drawing_export as retained

    _, after, plan, _ = transformed()
    value = after["notes"]["value"]
    monkeypatch.setattr(
        retained,
        "pdf_title",
        lambda *_: {
            "text": value["text"],
            "ink_box_pt": [x * 72 / 0.0254 for x in (0.28, 0.024, 0.30, 0.031)],
        },
    )
    with pytest.raises(RuntimeError, match="PDF glyphs.*does not fit"):
        layout.pdf_field_fit(tmp_path / "fixture.pdf", after["notes"], plan)


def test_actual_material_transform_never_invokes_historical_planners(
    tmp_path, monkeypatch
):
    from diagnostics import probe_baked_template_layout as probe
    from diagnostics import _baked_template_material as material

    before, lines = scene()
    report = {"layout_policy": "material-center"}
    model = SimpleNamespace(Visible=True)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
        ownership=SimpleNamespace(
            creating_document=lambda *_: nullcontext(), assert_current_owned=Mock()
        )
    )
    monkeypatch.setattr(probe, "bare_drawing", Mock())
    monkeypatch.setattr(layout, "blank_snapshot", lambda _: (before, {}, lines))
    monkeypatch.setattr(
        layout,
        "layout_plan",
        Mock(side_effect=AssertionError("four-note planner used")),
    )
    monkeypatch.setattr(
        probe.gaps,
        "measured_plan",
        Mock(side_effect=AssertionError("historical gap planner used")),
    )
    apply = Mock(side_effect=RuntimeError("stop at material-only native boundary"))
    monkeypatch.setattr(material, "apply_layout", apply)
    with pytest.raises(RuntimeError, match="stop at material-only native boundary"):
        asyncio.run(probe.transform(adapter, tmp_path, report, Mock()))
    assert set(report["plan"]) == {"value"}
    apply.assert_called_once()
    with pytest.raises(ValueError, match="cannot combine historical"):
        asyncio.run(
            probe.transform(adapter, tmp_path, report, Mock(), {"old": "receipt"})
        )
    assert apply.call_count == 1


@pytest.mark.parametrize("visible", [False, None, 1])
def test_material_route_rejects_invisible_document_before_first_extent(
    tmp_path, monkeypatch, visible
):
    from diagnostics import probe_baked_template_layout as probe
    from diagnostics import _baked_template_material as material

    model = SimpleNamespace(Visible=visible)
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
        ownership=SimpleNamespace(
            creating_document=lambda *_: nullcontext(), assert_current_owned=Mock()
        ),
    )
    monkeypatch.setattr(probe, "bare_drawing", Mock())
    snapshot = Mock(side_effect=AssertionError("GetExtent must not run invisibly"))
    apply = Mock(side_effect=AssertionError("no setter may run invisibly"))
    monkeypatch.setattr(layout, "blank_snapshot", snapshot)
    monkeypatch.setattr(material, "apply_layout", apply)
    with pytest.raises(RuntimeError, match="visible"):
        asyncio.run(
            probe.transform(adapter, tmp_path, {"layout_policy": "material-center"}, Mock())
        )
    snapshot.assert_not_called()
    apply.assert_not_called()
    assert model.Visible is visible  # Reject; never force visibility.


@pytest.mark.parametrize("hide_at", ["entry", "vertical", "position"])
def test_material_mutation_rechecks_visibility_and_stops_further_writes(
    monkeypatch, hide_at
):
    from diagnostics import _baked_template_material as material

    before, lines = scene()
    plan = material.material_plan(before["notes"], lines)
    owner = object()
    model = SimpleNamespace(Visible=hide_at != "entry", GraphicsRedraw2=Mock())
    vertical = [0]

    def set_vertical(value):
        vertical[0] = value
        if hide_at == "vertical":
            model.Visible = False

    def set_position(*xyz):
        if hide_at == "position":
            model.Visible = False
        return True

    note = SimpleNamespace(
        LockPosition=False,
        PropertyLinkedText=material.MATERIAL_LINK,
        GetTextJustification=lambda: 1,
        GetTextVerticalJustification=lambda: vertical[0],
        SetTextVerticalJustification=Mock(side_effect=set_vertical),
    )
    annotation = SimpleNamespace(
        Owner=owner,
        GetSpecificAnnotation=lambda: note,
        SetPosition2=Mock(side_effect=set_position),
        GetPosition=lambda: plan["value"]["position"],
    )
    adapter = SimpleNamespace(
        currentModel=model,
        ownership=SimpleNamespace(assert_current_owned=Mock()),
        swApp=SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
    )
    monkeypatch.setattr(layout.cells, "required", lambda value, _: value)
    with pytest.raises(RuntimeError, match="visible"):
        material.apply_layout(adapter, {"value": (annotation, owner)}, plan, [], Mock())
    assert model.Visible is False
    assert note.SetTextVerticalJustification.call_count == (0 if hide_at == "entry" else 1)
    assert annotation.SetPosition2.call_count == (1 if hide_at == "position" else 0)
    model.GraphicsRedraw2.assert_not_called()
