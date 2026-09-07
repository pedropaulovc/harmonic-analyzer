"""Only measured MATERIAL/FINISH Y changes may enter the new explicit arm."""

from copy import deepcopy
import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _baked_template_layout as layout
from diagnostics import _material_template_sources as sources
from test_baked_template_layout_drawing import note
from test_title_cell_drawing import box_lines
from test_owned_native_documents_drawing import Model, native  # noqa: F401


MATERIAL = '$PRPSHEET:"Material"'
FINISH = '$PRPSHEET:"Finish"'


def scene():
    """Synthetic closed cells with the observed native-center offset shape."""
    lines = box_lines(0.25, 0.026, 0.34, 0.033) + box_lines(0.25, 0.033, 0.34, 0.047)
    notes = {
        "material": note(MATERIAL, x=0.275, y=0.031, height=0.00238125, horizontal=1),
        "finish": note(FINISH, x=0.265, y=0.041, height=0.00238125, horizontal=1),
        "material_label": note(
            "MATERIAL", "MATERIAL", x=0.26, y=0.030, height=0.001524, horizontal=1
        ),
        "finish_label": note(
            "FINISH", "FINISH", x=0.265, y=0.044, height=0.001524, horizontal=1
        ),
    }
    notes["material_label"]["extent"] = [0.26, 0.028, 0, 0.272, 0.030, 0]
    notes["finish_label"]["extent"] = [0.265, 0.042, 0, 0.273, 0.044, 0]
    targets = {}
    for target in sources.TARGETS:
        rows = deepcopy(notes)
        rows["material"].update(
            text="complete material " + target,
            vertical=1,
            position=[0.275, (0.026 + 0.033) / 2, 0],
        )
        rows["finish"].update(text="complete finish " + target)
        material_box = [0.275, 0.027, 0.326, 0.0322]
        finish_box = [0.265, 0.0329, 0.331, 0.040]
        if target != "tube_frame":
            material_box = [0.275, 0.028, 0.326, 0.0312]
            finish_box = [0.265, 0.035, 0.331, 0.040]
        fields = {}
        for name, row in rows.items():
            box = (
                material_box
                if name == "material"
                else finish_box
                if name == "finish"
                else [row["extent"][index] for index in (0, 1, 3, 4)]
            )
            row["extent"] = [*box[:2], 0, *box[2:], 0]
            fields[name] = {
                "link": row["link"],
                "native_text": row["text"],
                "native_box_m": box[:],
                "pdf_box_m": box[:],
                "region_m": [0.25, 0.026, 0.34, 0.033]
                if name.startswith("material")
                else [0.25, 0.033, 0.34, 0.047],
                "pdf": {
                    "text": row["text"],
                    "ink_box_pt": [value * 72 / 0.0254 for value in box],
                },
            }
            fields[name]["pdf_box_m"] = [
                value * 0.0254 / 72 for value in fields[name]["pdf"]["ink_box_pt"]
            ]
        targets[target] = {
            "notes": rows,
            "lines": layout.plain(lines),
            "fields": fields,
        }
    return notes, lines, targets


def test_new_mode_is_explicit_and_historical_modes_keep_their_values():
    from diagnostics import _baked_template_gaps as gaps
    from diagnostics import probe_populated_template as populated

    assert gaps.LayoutPolicy.MATERIAL_FINISH.value == "material-finish"
    assert populated.Population.MATERIAL_FINISH.value == "material-finish"
    assert gaps.LayoutPolicy.MATERIAL_CENTER.value == "material-center"
    assert gaps.LayoutPolicy.POPULATED_GAPS.value == "populated-gaps"


def test_common_native_envelope_and_finish_interval_derive_only_two_y_targets():
    from diagnostics import _baked_template_material_finish as packing

    notes, lines, targets = scene()
    original = deepcopy((notes, lines, targets))
    plan, witness = packing.measured_plan(notes, lines, targets)
    assert (notes, lines, targets) == original
    assert set(plan) == {"material", "finish"}
    assert plan["material"]["vertical"] == 1
    assert plan["finish"]["vertical"] == 0
    assert (
        plan["material"]["position"][1]
        < targets["tube_frame"]["notes"]["material"]["position"][1]
    )
    assert plan["finish"]["position"][1] > notes["finish"]["position"][1]
    lo, hi = witness["finish_interval_m"]
    assert witness["finish_shift_m"] == (lo + hi) / 2
    assert lo < witness["finish_shift_m"] < hi
    for name, row in plan.items():
        assert row["position"][::2] == notes[name]["position"][::2]
        assert row["height_m"] == notes[name]["font"]["CharHeight"]
    assert all(not row["issues"] for row in witness["targets"].values())


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "extra",
        "font",
        "text",
        "link",
        "anchor",
        "geometry",
        "nan",
        "pdf_missing",
        "pdf_overflow",
        "pdf_inconsistent",
        "region",
        "no_interval",
    ],
)
def test_changed_or_infeasible_samples_are_rejected_without_mutation(mode):
    from diagnostics import _baked_template_material_finish as packing

    notes, lines, targets = scene()
    tube = targets["tube_frame"]
    if mode == "missing":
        targets.pop("channel_lever")
    if mode == "extra":
        targets["other"] = deepcopy(tube)
    if mode == "font":
        tube["notes"]["finish"]["font"]["Bold"] = True
    if mode == "text":
        tube["fields"]["finish"]["native_text"] = "shortened"
    if mode == "link":
        tube["notes"]["finish"]["link"] = "$PRPSHEET:Other"
    if mode == "anchor":
        tube["notes"]["material"]["position"][1] += 0.001
    if mode == "geometry":
        tube["lines"] = []
    if mode == "nan":
        tube["fields"]["finish"]["pdf_box_m"][0] = float("nan")
    if mode == "pdf_missing":
        tube["fields"]["finish"].pop("pdf_box_m")
    if mode == "pdf_overflow":
        tube["fields"]["material"]["pdf_box_m"][2] = 0.4
    if mode == "pdf_inconsistent":
        tube["fields"]["material"]["pdf"]["ink_box_pt"][2] -= 1
    if mode == "region":
        tube["fields"]["finish"]["region_m"][3] += 0.01
    if mode == "no_interval":
        tube["fields"]["finish"]["native_box_m"][3] = 0.042
        tube["notes"]["finish"]["extent"][4] = 0.042
    with pytest.raises(RuntimeError, match="material-finish"):
        packing.measured_plan(notes, lines, targets)


def receipt():
    _, _, targets = scene()
    inputs = {"C:/test/templates/harmonic-analyzer.DRWDOT": "template"}
    trials = []
    for target, sample in targets.items():
        built = {
            "notes": sample["notes"],
            "template_geometry": {
                "segments": [{"sheet_points": line} for line in sample["lines"]]
            },
            "fit": {"fields": sample["fields"], "issues": []},
            "expected_link_values": {MATERIAL: sample["notes"]["material"]["text"]},
        }
        trials.append(
            {
                "target": target,
                "status": "observed",
                "copy_hashes": {
                    "initial": sources.TARGETS[target].source_sha256,
                    "final": sources.TARGETS[target].source_sha256,
                },
                "cold_delta": {"changed_leaf_count": 0},
                "png_delta": {"changed_pixel_count": 0},
                "printed": {"classification": "unchanged"},
                "linked_fields": {"built": deepcopy(built), "cold": deepcopy(built)},
                "acceptance_issues": [],
            }
        )
    return {
        "population": "material-center",
        "status": "failed",
        "inputs_before": inputs,
        "inputs_after": deepcopy(inputs),
        "trials": trials,
    }


@pytest.mark.parametrize(
    "mode",
    [
        "accepted",
        "sha",
        "template",
        "wrong_mode",
        "targets",
        "source",
        "cold",
        "pdf",
        "protected",
        "incomplete",
    ],
)
def test_receipt_requires_exact_sha_three_sources_and_full_cold_fields(tmp_path, mode):
    from diagnostics import _baked_template_material_finish as packing

    value = receipt()
    if mode == "wrong_mode":
        value["population"] = "material-baseline"
    if mode == "targets":
        value["trials"].pop()
    if mode == "source":
        value["trials"][0]["copy_hashes"] = {"initial": "wrong", "final": "wrong"}
    if mode == "cold":
        value["trials"][0]["cold_delta"]["changed_leaf_count"] = 1
    if mode == "pdf":
        value["trials"][0]["linked_fields"]["cold"]["fit"]["fields"]["material"][
            "pdf_box_m"
        ][1] -= 0.001
    if mode == "protected":
        value["inputs_after"]["other"] = "changed"
    if mode == "incomplete":
        value["trials"][0].pop("linked_fields")
    path = tmp_path / "population.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if mode == "accepted":
        found = packing.read_population(path, digest, "template")
        assert set(found["targets"]) == set(sources.TARGETS)
        return
    with pytest.raises(RuntimeError, match="material-finish|populated"):
        packing.read_population(
            path,
            "0" * 64 if mode == "sha" else digest,
            "wrong" if mode == "template" else "template",
        )


@pytest.mark.parametrize("mode", ["exact", "text", "link", "font"])
def test_only_existing_normal_setup_edge_break_conversion_is_projected(mode):
    from diagnostics import _baked_template_material_finish as packing

    notes, lines, targets = scene()
    old = layout.sheet_setup._OLD_EDGE_BREAK_NOTE
    metric = layout.sheet_setup._METRIC_EDGE_BREAK_NOTE
    notes["edge"] = note(old, old, x=0.26, y=0.05, horizontal=1)
    for sample in targets.values():
        sample["notes"]["edge"] = deepcopy(notes["edge"])
        sample["notes"]["edge"].update(text=metric, link=metric)
    row = targets["tube_frame"]["notes"]["edge"]
    if mode in ("text", "link"):
        row[mode] = "different note"
    if mode == "font":
        row["font"]["Bold"] = True
    if mode == "exact":
        packing.measured_plan(notes, lines, targets)
        assert notes["edge"]["text"] == notes["edge"]["link"] == old
        return
    with pytest.raises(RuntimeError, match="blank style/content/anchor"):
        packing.measured_plan(notes, lines, targets)


def transition():
    from diagnostics import _baked_template_material_finish as packing

    notes, lines, targets = scene()
    before = {
        "notes": notes,
        "template_geometry": layout.plain(lines),
        "units": [4, 0, 2],
        "surface_finishes": ["unchanged"],
    }
    plan, _ = packing.measured_plan(notes, lines, targets)
    after = deepcopy(before)
    for name, destination in plan.items():
        after["notes"][name]["position"] = destination["position"][:]
        after["notes"][name]["vertical"] = destination["vertical"]
    return before, after, plan, lines, targets


@pytest.mark.parametrize(
    "mode",
    [
        "accepted",
        "text",
        "link",
        "font",
        "x",
        "z",
        "y",
        "label",
        "geometry",
        "units",
        "sf",
        "finish_vertical",
        "material_vertical",
        "plan",
    ],
)
def test_exhaustive_blank_transition_preserves_every_unapproved_field(mode):
    from diagnostics import _baked_template_material_finish as packing

    before, after, plan, lines, targets = transition()
    row = after["notes"]["finish"]
    if mode in ("text", "link"):
        row[mode] = "changed"
    if mode == "font":
        row["font"]["Bold"] = True
    if mode in ("x", "y", "z"):
        row["position"]["xyz".index(mode)] += 0.0001
    if mode == "label":
        after["notes"]["material_label"]["position"][1] += 0.001
    if mode == "geometry":
        after["template_geometry"][0][0][0] += 0.001
    if mode == "units":
        after["units"][0] = 0
    if mode == "sf":
        after["surface_finishes"] = []
    if mode == "finish_vertical":
        row["vertical"] = 1
    if mode == "material_vertical":
        after["notes"]["material"]["vertical"] = 0
    if mode == "plan":
        plan["finish"]["position"][1] += 0.001
        row["position"] = plan["finish"]["position"][:]
    if mode == "accepted":
        original = deepcopy((before, after, plan))
        packing.require_transition(before, after, plan, lines, targets)
        assert (before, after, plan) == original
        with pytest.raises(RuntimeError, match="outside explicit allowlist"):
            layout.require_transition(before, after, plan)
        return
    with pytest.raises(RuntimeError, match="material-finish|allowlist|clamped"):
        packing.require_transition(before, after, plan, lines, targets)


@pytest.mark.parametrize(
    "mode",
    [
        "accepted",
        "hidden_entry",
        "foreign_material",
        "ignored_vertical",
        "error_vertical",
        "hide_vertical",
        "false_material",
        "clamped_material",
        "error_material",
        "hide_material",
        "foreign_finish",
        "false_finish",
        "clamped_finish",
        "error_finish",
        "hide_finish",
    ],
)
def test_native_readback_stops_all_following_writes_and_retains_partial_calls(
    monkeypatch, mode
):
    from diagnostics import _baked_template_material_finish as packing

    _, _, plan, _, _ = transition()
    primary = RuntimeError("material-finish injected native failure")
    model = SimpleNamespace(Visible=mode != "hidden_entry", GraphicsRedraw2=Mock())
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(ActiveDoc=model, IsSame=lambda a, b: int(a is b)),
        ownership=SimpleNamespace(assert_current_owned=Mock()),
    )
    history = []

    def native_note(role):
        owner = object()
        state = {"vertical": 0, "position": [0.0, 0.0, 0.0]}

        def vertical(value):
            history.append("vertical")
            if mode == "error_vertical":
                raise primary
            if mode != "ignored_vertical":
                state["vertical"] = value
            if mode == "hide_vertical":
                model.Visible = False

        def position(*xyz):
            history.append(role)
            if mode == "error_" + role:
                raise primary
            state["position"] = list(xyz)
            if mode == "clamped_" + role:
                state["position"][1] += 0.0001
            if mode == "hide_" + role:
                model.Visible = False
            return mode != "false_" + role

        note = SimpleNamespace(
            LockPosition=False,
            PropertyLinkedText=packing.LINKS[role],
            GetTextJustification=lambda: 1,
            GetTextVerticalJustification=lambda: state["vertical"],
            SetTextVerticalJustification=Mock(side_effect=vertical),
            SetTextJustification=Mock(
                side_effect=AssertionError("no horizontal setter")
            ),
        )
        annotation = SimpleNamespace(
            Owner=object() if mode == "foreign_" + role else owner,
            GetSpecificAnnotation=lambda: note,
            SetPosition2=Mock(side_effect=position),
            GetPosition=lambda: state["position"],
            SetTextFormat=Mock(side_effect=AssertionError("no font setter")),
        )
        return annotation, owner

    handles = {role: native_note(role) for role in packing.LINKS}
    monkeypatch.setattr(layout.cells, "required", lambda value, _: value)
    journal = []
    if mode == "accepted":
        packing.apply_layout(adapter, handles, plan, journal, Mock())
        assert history == ["vertical", "material", "finish"]
        assert [row["calls"] for row in journal] == [
            ["SetTextVerticalJustification", "SetPosition2"],
            ["SetPosition2"],
        ]
        model.GraphicsRedraw2.assert_called_once_with()
        return
    with pytest.raises(RuntimeError, match="material") as raised:
        packing.apply_layout(adapter, handles, plan, journal, Mock())
    if mode.startswith("error_"):
        assert raised.value is primary
    expected = [] if mode in ("hidden_entry", "foreign_material") else ["vertical"]
    if mode not in (
        "hidden_entry",
        "foreign_material",
        "ignored_vertical",
        "error_vertical",
        "hide_vertical",
    ):
        expected.append("material")
    if mode in ("false_finish", "clamped_finish", "error_finish", "hide_finish"):
        expected.append("finish")
    assert history == expected
    assert sum(len(row["calls"]) for row in journal) == len(history)
    model.GraphicsRedraw2.assert_not_called()


def test_missing_population_is_rejected_before_blank_creation(tmp_path, monkeypatch):
    from diagnostics import probe_baked_template_layout as probe

    create = Mock(side_effect=AssertionError("no native creation allowed"))
    monkeypatch.setattr(probe, "bare_drawing", create)
    with pytest.raises(ValueError, match="material-finish requires"):
        asyncio.run(
            probe.transform(
                SimpleNamespace(),
                tmp_path,
                {"layout_policy": "material-finish"},
                Mock(),
            )
        )
    create.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        "accepted",
        "partial_creation",
        "partial_apply",
        "save_drift",
        "cold_drift",
        "print_drift",
        "replaced_handle",
    ],
)
def test_new_mode_uses_owned_blank_save_and_fresh_inheritance_with_old_planners_disabled(
    native, monkeypatch, tmp_path, mode  # noqa: F811
):
    from diagnostics import probe_baked_template_layout as probe
    from diagnostics import _baked_template_material_finish as packing
    from diagnostics import _owned_native_documents as owned

    before, after, plan, lines, _ = transition()
    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"original")
    value = receipt()
    value["inputs_before"] = {
        str(original.parent / "templates/harmonic-analyzer.DRWDOT"): hashlib.sha256(
            b"original"
        ).hexdigest()
    }
    value["inputs_after"] = deepcopy(value["inputs_before"])
    calibration = tmp_path / "population.json"
    calibration.write_text(json.dumps(value), encoding="utf-8")
    digest = hashlib.sha256(calibration.read_bytes()).hexdigest()
    monkeypatch.setattr(probe.sheet_setup, "PROJECT_DRWDOT", original)
    monkeypatch.setattr(probe.pilot, "helper_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {})
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(
        probe.gaps,
        "measured_plan",
        Mock(side_effect=AssertionError("old gap planner used")),
    )
    monkeypatch.setattr(
        layout,
        "layout_plan",
        Mock(side_effect=AssertionError("four-note planner used")),
    )
    baseline = Model(None, title="User unsaved", dirty=True)
    native.app.documents.append(baseline)
    native.app.ActiveDoc = baseline
    created, templates, applied = [], [], []

    def bare(adapter, template):
        model = Model(None, title=f"Blank{len(created)}", dirty=True)
        model.stage = "before" if not created else "cold"
        model.annotation, model.owner = object(), object()
        native.app.documents.append(model)
        native.app.ActiveDoc = adapter.currentModel = model
        created.append(model)
        templates.append(template)
        if mode == "partial_creation":
            raise RuntimeError("material-finish partial creation")

    def snapshot(adapter):
        model = adapter.currentModel
        state = deepcopy(before if model.stage == "before" else after)
        if (mode == "save_drift" and model.stage == "saved") or (
            mode == "cold_drift" and model.stage == "cold"
        ):
            state["notes"]["finish_label"]["text"] = "changed label"
        annotation = (
            object()
            if mode == "replaced_handle" and model.stage == "after"
            else model.annotation
        )
        return state, {"note": (annotation, model.owner)}, lines

    def apply(adapter, _handles, actual, journal, checkpoint):
        applied.append(deepcopy(actual))
        journal.append({"calls": ["retained partial boundary"]})
        adapter.currentModel.stage = "after"
        if mode == "partial_apply":
            raise RuntimeError("material-finish partial apply")

    def save(model, path, row):
        path.write_bytes(b"derived")
        model.path, model.title, model.dirty, model.stage = (
            str(path),
            path.name,
            False,
            "saved",
        )
        row["save_return"] = 0

    def printing(adapter, directory):
        pdf, png = directory / "sheet.pdf", directory / "sheet.png"
        pdf.write_bytes(b"PDF")
        png.write_bytes(b"PNG")
        return {"pdf": str(pdf), "png": str(png)}

    def compare(*_):
        if mode == "print_drift":
            raise RuntimeError("material-finish print changed")
        return {"changed_pixel_count": 0}

    monkeypatch.setattr(probe, "bare_drawing", bare)
    monkeypatch.setattr(layout, "blank_snapshot", snapshot)
    monkeypatch.setattr(packing, "apply_layout", apply)
    monkeypatch.setattr(layout, "pdf_field_fit", lambda *_: {})
    monkeypatch.setattr(probe.defaults, "save_prepared_template", save)
    monkeypatch.setattr(probe.printed, "printed_witness", printing)
    monkeypatch.setattr(probe.printed, "compare_printed", compare)

    async def callback(adapter):
        return await probe.probe(
            adapter,
            tmp_path / "reports",
            policy=probe.gaps.LayoutPolicy.MATERIAL_FINISH,
            population_path=calibration,
            population_sha256=digest,
        )

    if mode == "accepted":
        result = asyncio.run(owned.owned_callback(native.adapter, callback))
        assert result["outcome"] == "blank_template_layout_persisted"
    else:
        with pytest.raises(ExceptionGroup, match="baked template|owned"):
            asyncio.run(owned.owned_callback(native.adapter, callback))
    assert native.app.documents == [baseline] and baseline.dirty
    assert baseline not in native.app.closes
    assert not native.adapter.opens
    assert original.read_bytes() == b"original"
    assert hashlib.sha256(calibration.read_bytes()).hexdigest() == digest
    (path,) = (tmp_path / "reports").glob("*/template-layout.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["inputs_before"] == report["inputs_after"]
    assert report["status"] == ("passed" if mode == "accepted" else "failed")
    assert applied == ([] if mode == "partial_creation" else [plan])
    assert len(created) == (
        2 if mode in ("accepted", "cold_drift", "print_drift") else 1
    )
    if len(created) == 2:
        assert templates[0] == original
        assert str(templates[1]) == report["derived_template"]
        assert templates[1].read_bytes() == b"derived"
