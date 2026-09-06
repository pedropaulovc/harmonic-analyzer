"""Shoulder controls change only native leader policy, never the datum feature."""

from types import SimpleNamespace

import pytest

from diagnostics import probe_datum_shoulder as probe


def test_all_manufacturing_snapshots_supply_exact_native_application():
    import ast
    import inspect

    calls = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(probe.probe)))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "attachments"
        and node.func.attr == "snapshot"
    ]
    assert len(calls) == 3
    assert all(
        any(
            keyword.arg == "app"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "app"
            for keyword in call.keywords
        )
        for call in calls
    )


def test_standalone_default_runs_positive_document_route_with_explicit_part(
    monkeypatch, tmp_path
):
    import sys

    drawing, part = tmp_path / "archived-source.SLDDRW", tmp_path / "rocker-arm.SLDPRT"
    drawing.write_bytes(b"drawing")
    part.write_bytes(b"part")
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "dodo",
        SimpleNamespace(_run=lambda *args, **kwargs: calls.append((args, kwargs))),
    )
    monkeypatch.setattr(sys, "argv", ["probe", str(drawing), "--part", str(part)])
    assert probe.main() == 0
    (arguments, title), keywords = calls[0]
    assert arguments[-2:] == ["--part", str(part.resolve())]
    assert arguments[arguments.index("--mode") + 1] == "document_length"
    assert "--worker" in arguments and keywords["com"] is True


def row():
    return {
        "label": "B",
        "owner_type": 0,
        "visible": 1,
        "dangling": False,
        "attachment_types": (2,),
        "null_attachments": (False,),
        "geometry": ("face",),
        "configuration": "Default",
        "style": 1,
        "label_render": ("B",),
        "shoulder": False,
        "forced_shoulder": False,
        "frame_relation": {"frame": (0.1, 0.2, 0.107, 0.207)},
    }


@pytest.mark.parametrize("policy", tuple(probe.ShoulderPolicy))
def test_explicit_shoulder_policy_has_exact_readback(policy):
    tag = SimpleNamespace(Shoulder=False, ForcedShoulder=False)
    result = probe.set_shoulder(tag, policy)
    assert result["actual"] is (policy is probe.ShoulderPolicy.BENT)


def test_rejected_native_shoulder_policy_fails_loud():
    class RejectedTag:
        ForcedShoulder = False

        @property
        def Shoulder(self):
            return False

        @Shoulder.setter
        def Shoulder(self, _value):
            pass

    with pytest.raises(RuntimeError, match="rejected requested policy"):
        probe.set_shoulder(RejectedTag(), probe.ShoulderPolicy.BENT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("shoulder", True),
        ("forced_shoulder", True),
        ("style", 2),
        ("attachment_types", (1,)),
        ("null_attachments", (True,)),
    ],
)
def test_control_must_start_with_exact_nonforced_straight_face(field, value):
    with pytest.raises(RuntimeError):
        probe.find_target({"datum": {**row(), field: value}})


def test_shoulder_property_change_is_not_a_semantic_feature_change():
    before = row()
    probe.same_target(
        before,
        {
            **before,
            "shoulder": True,
            "frame_relation": {"frame": (0.2, 0.3, 0.207, 0.307)},
        },
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("geometry", ("other face",)),
        ("label", "A"),
        ("label_render", ("C",)),
        ("style", 2),
        ("frame_relation", {"frame": (0.1, 0.2, 0.108, 0.207)}),
    ],
)
def test_geometry_label_or_frame_mutation_is_not_accepted(field, value):
    with pytest.raises(RuntimeError):
        probe.same_target(row(), {**row(), field: value})


def bent_record():
    return {
        "position": (0.29875, 0.1683376494921567, 0),
        "frame_relation": {
            "frame": (0.3051, 0.1648376494921567, 0.3121, 0.1718376494921567)
        },
        "measurement": {
            "body": {
                "xmin": 0.3051,
                "ymin": 0.1648376494921567,
                "xmax": 0.3121,
                "ymax": 0.1718376494921567,
            }
        },
        "view_outline": (0.290883750008, 0.15274964949, 0.309116249992, 0.19322028962),
        "generic": {
            "lines": [
                (
                    0,
                    0,
                    0,
                    0,
                    0.29875,
                    0.1683376494921567,
                    0,
                    0.3051,
                    0.1683376494921567,
                    0,
                )
            ]
        },
    }


def test_length_target_comes_from_native_segment_and_actual_view_deficit():
    result = probe.bent_length_target(bent_record())
    assert result["native_measured_m"] == pytest.approx(0.00635)
    assert result["deficit_m"] == pytest.approx(0.007016249992)
    assert result["requested_m"] == pytest.approx(0.013366249992)


@pytest.mark.parametrize("lines", [[], [(0,) * 10, (0,) * 10]])
def test_length_control_requires_actual_unique_elbow_frame_segment(lines):
    record = bent_record()
    record["generic"]["lines"] = lines
    with pytest.raises(RuntimeError, match="not unique"):
        probe.bent_length_target(record)


def test_minus_one_length_is_recorded_not_a_fallback_or_feature_verdict():
    native = {
        "variant": "native_bent",
        "length": {
            "initial_readback_m": -1,
            "after_readback_m": -1,
            "reopened_readback_m": -1,
        },
        "styled": bent_record(),
        "after": bent_record(),
    }
    probe.verify_length_change(native)
    candidate = {
        **native,
        "variant": "extended_bent",
        "length": {**native["length"], "requested_m": 0.013},
    }
    with pytest.raises(RuntimeError, match="did not retain requested value"):
        probe.verify_length_change(candidate)


def test_document_length_uses_document_extension_and_exact_installed_enum(monkeypatch):
    monkeypatch.setattr(
        probe,
        "_installed_swconst",
        lambda: SimpleNamespace(
            swDetailingAnnotationBentLeaderLength=113,
            swDetailingNoOptionSpecified=0,
        ),
    )
    state = {"value": 0.00635}
    calls = []

    def setter(preference, option, value):
        calls.append((preference, option, value))
        state["value"] = value
        return True

    extension = SimpleNamespace(
        GetUserPreferenceDouble=lambda preference, option: state["value"],
        SetUserPreferenceDouble=setter,
    )
    result = probe.set_document_length(extension, 0.01336625)
    assert calls == [(113, 0, 0.01336625)]
    assert result == {
        "before_m": 0.00635,
        "returned": True,
        "requested_m": 0.01336625,
        "after_m": 0.01336625,
    }


def test_document_property_rejection_is_not_hidden_by_the_length_getter():
    with pytest.raises(RuntimeError, match="setter rejected"):
        probe.verify_document_length({"document_length": {"returned": False}})


def test_global_control_reports_intended_body_movement_without_waiving_semantics():
    initial = {
        "semantic": {"texts": ("A",)},
        "generic": {"lines": ((0, 0),)},
        "position": (0, 0),
    }
    actual = {**initial, "generic": {"lines": ((1, 0),)}, "position": (1, 0)}
    changes = probe.compare_all_annotation_layout(
        None, {"datum": initial}, {"datum": actual}
    )
    assert changes["datum"]["position_after"] == (1, 0)
    with pytest.raises(RuntimeError, match="semantics"):
        probe.compare_all_annotation_layout(
            None,
            {"datum": initial},
            {"datum": {**actual, "semantic": {"texts": ("B",)}}},
        )


def test_global_control_requires_same_exact_native_handles():
    app = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    row = {"semantic": {}, "generic": {}, "position": (0, 0)}
    with pytest.raises(RuntimeError, match="identity changed"):
        probe.compare_all_annotation_layout(
            app, {"a": row}, {"a": row}, {"a": (object(),)}, {"a": (object(),)}
        )


def test_global_control_keeps_missing_measurement_exclusions_explicit():
    row = {
        "semantic": {},
        "generic": {},
        "position": (0, 0),
        "measurement_exclusion": "unsupported font",
    }
    assert not probe.compare_all_annotation_layout(None, {"a": row}, {"a": row})
    with pytest.raises(RuntimeError, match="bounds support"):
        probe.compare_all_annotation_layout(
            None, {"a": row}, {"a": {**row, "measurement_exclusion": "missing body"}}
        )
