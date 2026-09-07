"""Only measured MATERIAL/FINISH Y changes may enter the new explicit arm."""

from copy import deepcopy
import hashlib
import json

import pytest

from diagnostics import _baked_template_layout as layout
from diagnostics import _material_template_sources as sources
from test_baked_template_layout_drawing import note
from test_title_cell_drawing import box_lines


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
        targets[target] = {"notes": rows, "lines": layout.plain(lines), "fields": fields}
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
