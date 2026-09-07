"""Offline contracts for the read-only native spare/deck contact diagnostic."""

from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from diagnostics import probe_spare_deck_contact as probe


def pose(rows=None, translation=(0.0, 0.0, 0.0)):
    rows = rows or ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return (*[v for row in rows for v in row], *translation, 1.0, 0.0, 0.0, 0.0)


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    app = NS(IsSame=lambda left, right: int(left is right))
    hashes = {}

    def component(filename, parent=None, configuration="Default", array=None):
        folder = "sldasm" if filename.endswith("SLDASM") else "sldprt"
        path = (probe.ROOT / "cad/out" / folder / filename).resolve()
        kind = 2 if folder == "sldasm" else 1
        model = NS(path=str(path), GetType=lambda: kind)
        # Source-model geometry must never substitute for configured component bodies.
        model.GetBodies2 = Mock(side_effect=AssertionError("last-saved geometry"))
        hashes[str(path)] = "exact input hash"
        return NS(
            GetPathName=lambda: str(path),
            ReferencedConfiguration=configuration,
            GetParent=lambda: parent,
            IsSuppressed=lambda: False,
            GetModelDoc2=lambda: model,
            Name2=filename + "-1",
            Transform2=NS(ArrayData=array or pose()),
        )

    paper = component("paper-drive.SLDASM")
    frame = component("frame.SLDASM")
    spare = component(
        "transgear-removable.SLDPRT",
        paper,
        "T18",
        pose(probe.ROT_X_NEG90, tuple(v / 1000 for v in probe.SPARE_GEAR_POS)),
    )
    base = component("harmonic-base.SLDPRT", frame)
    paper.GetChildren = Mock(return_value=(spare,))
    frame.GetChildren = Mock(return_value=(base,))
    root = NS(GetComponents=Mock(return_value=(paper, frame)))
    owner = NS(
        root=root,
        app=app,
        hashes=hashes,
        assert_active=Mock(),
        identity=lambda model: (model.path, model.GetType()),
    )

    def face(item, normal, point, closest):
        surface = NS(IsPlane=lambda: True, PlaneParams=(*normal, *point))
        native = NS(
            GetComponent=lambda: item,
            GetSurface=lambda: surface,
            FaceInSurfaceSense=lambda: False,
            GetClosestPointOn=Mock(side_effect=closest),
        )
        body = NS(GetType=lambda: 0, GetFaces=Mock(return_value=(native,)))
        item.GetBodies3 = Mock(return_value=((body,), (1,)))
        return native, surface, body

    underside, under_surface, under_body = face(
        spare,
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 0.0),
        lambda *_: (0.003, 0.0, 0.0, 0.0, 0.0),
    )
    deck, deck_surface, deck_body = face(
        base,
        (0.0, 1.0, 0.0),
        (0.0, probe.STACK_HEIGHT / 1000, 0.0),
        lambda x, y, z: (x, y, z, 0.0, 0.0),
    )
    return NS(**locals())


def test_contact_uses_configured_bodies_native_transform_and_trimmed_faces(scene):
    report = {}
    probe.contact(scene.owner, report)
    assert report["components"]["spare"]["configuration"] == "T18"
    assert report["plane_separation_m"] == pytest.approx(0.0, abs=1e-15)
    assert report["contact"]["distance_m"] == pytest.approx(0.0, abs=1e-15)
    assert report["contact"]["underside_world"] == pytest.approx(
        (
            probe.SPARE_GEAR_POS[0] / 1000 + 0.003,
            probe.SPARE_GEAR_POS[1] / 1000,
            probe.SPARE_GEAR_POS[2] / 1000,
        )
    )
    scene.spare.GetBodies3.assert_called_once_with(0)
    scene.base.GetBodies3.assert_called_once_with(0)
    scene.spare.GetModelDoc2().GetBodies2.assert_not_called()
    scene.base.GetModelDoc2().GetBodies2.assert_not_called()
    assert scene.root.GetComponents.call_args_list == [((True,),), ((True,),)]
    assert scene.owner.assert_active.call_count == 2


@pytest.mark.parametrize("height", [0.0024, -0.0024])
def test_native_gap_or_penetration_is_rejected_even_when_authored_pose_agrees(
    scene, monkeypatch, height
):
    moved = list(scene.spare.Transform2.ArrayData)
    moved[10] += height
    scene.spare.Transform2.ArrayData = tuple(moved)
    expected = list(probe.SPARE_GEAR_POS)
    expected[1] += height * 1000
    monkeypatch.setattr(probe, "SPARE_GEAR_POS", tuple(expected))
    report = {}
    with pytest.raises(RuntimeError, match="native support planes coplanar"):
        probe.contact(scene.owner, report)
    assert report["plane_separation_m"] == pytest.approx(height)
    scene.deck.GetClosestPointOn.assert_not_called()


def test_coplanar_unbounded_surfaces_do_not_prove_trimmed_face_contact(scene):
    scene.deck.GetClosestPointOn.side_effect = lambda x, y, z: (
        x + 0.01,
        y,
        z,
        0.0,
        0.0,
    )
    report = {}
    with pytest.raises(RuntimeError, match="trimmed native face contact"):
        probe.contact(scene.owner, report)
    assert report["plane_separation_m"] == pytest.approx(0.0, abs=1e-15)
    assert report["contact"]["distance_m"] == pytest.approx(0.01)


@pytest.mark.parametrize(
    "fault,match",
    [
        ("configuration", "expected one transgear-removable"),
        ("parent", "parent: native identity"),
        ("suppressed", "component is suppressed"),
        ("face_owner", "face component: native identity"),
        ("duplicate_face", "expected one native support plane"),
        ("user_body", "unchanged normal component body"),
        ("changed_instance", "unchanged spare instance"),
    ],
)
def test_selected_component_and_face_identity_are_required(scene, fault, match):
    if fault == "configuration":
        scene.spare.ReferencedConfiguration = "T24"
    if fault == "parent":
        scene.spare.GetParent = lambda: scene.frame
    if fault == "suppressed":
        scene.spare.IsSuppressed = lambda: True
    if fault == "face_owner":
        scene.underside.GetComponent = lambda: scene.base
    if fault == "duplicate_face":
        scene.under_body.GetFaces.return_value = (scene.underside, scene.underside)
    if fault == "user_body":
        scene.spare.GetBodies3.return_value = ((scene.under_body,), (0,))
    if fault == "changed_instance":
        replacement = NS(**vars(scene.spare))
        scene.paper.GetChildren.side_effect = [(scene.spare,), (replacement,)]
    with pytest.raises(RuntimeError, match=match):
        probe.contact(scene.owner, {})


@pytest.mark.parametrize(
    "result",
    [None, (), ((),), ((), ()), ((object(),), ()), ((), (1,)), ((object(),), (True,))],
)
def test_malformed_configured_body_return_cannot_prove_contact(scene, result):
    scene.spare.GetBodies3.return_value = result
    with pytest.raises(RuntimeError):
        probe.contact(scene.owner, {})


@pytest.mark.parametrize(
    "value",
    [
        None,
        (1.0,),
        (0, 0.0, 0.0),
        (True, 0.0, 0.0),
        (float("nan"), 0.0, 0.0),
        (float("inf"), 0.0, 0.0),
    ],
)
def test_bad_native_coordinates_are_not_coerced(value):
    with pytest.raises(RuntimeError):
        probe.doubles(value, 3, "native point")


def test_native_frame_transform_has_inverse_for_readback_points(scene):
    array = probe.transform(scene.spare)
    point = (0.003, 0.007, 0.0024)
    assert probe.local(array, probe.world(array, point)) == pytest.approx(
        point, abs=1e-15
    )


@pytest.mark.parametrize("fault", ["scale", "reflection", "nonorthogonal"])
def test_scaled_or_nonrigid_component_transform_is_rejected(scene, fault):
    array = list(scene.spare.Transform2.ArrayData)
    if fault == "scale":
        array[12] = 2.0
    if fault == "reflection":
        array[0] = -1.0
    if fault == "nonorthogonal":
        array[1] = 0.1
    scene.spare.Transform2.ArrayData = tuple(array)
    with pytest.raises(RuntimeError):
        probe.transform(scene.spare)


@pytest.mark.asyncio
async def test_primary_cleanup_and_hash_failures_all_remain_in_receipt(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    source = tmp_path / "cad/out/sldasm/harmonic-analyzer.SLDASM"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"native source fixture")
    primary, cleanup = (
        RuntimeError("native read rejected"),
        RuntimeError("owned close rejected"),
    )
    owner = NS(
        hashes={str(source): probe.digest(source)},
        open=AsyncMock(),
        close=AsyncMock(side_effect=cleanup),
        inventory=Mock(return_value={}),
        input_evidence=lambda: {str(source): {"status": "unreadable"}},
    )
    monkeypatch.setattr(probe, "OwnedAssembly", lambda *_: owner)
    monkeypatch.setattr(probe, "document_state", lambda _: {"model": "clean"})
    monkeypatch.setattr(probe, "contact", Mock(side_effect=primary))
    receipts = []
    monkeypatch.setattr(
        probe, "checkpoint", lambda _, row: receipts.append(deepcopy(row))
    )
    with pytest.raises(ExceptionGroup) as caught:
        await probe.measure(
            object(), {}, tmp_path / "contact.json", probe.digest(source)
        )
    assert caught.value.exceptions[:2] == (primary, cleanup)
    assert len(caught.value.exceptions) == 3
    assert receipts[-1]["status"] == "failed"
    assert receipts[-1]["inputs"][str(source)]["status"] == "unreadable"
    assert "final_inventory" not in receipts[-1]
    owner.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["passed", "failed"])
async def test_final_checkpoint_failure_preserves_native_error_and_cleanup(
    monkeypatch, tmp_path, outcome
):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    source = tmp_path / "cad/out/sldasm/harmonic-analyzer.SLDASM"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"native source fixture")
    primary = RuntimeError("native read rejected")
    write_error = OSError("final receipt unavailable")
    owner = NS(
        hashes={str(source): probe.digest(source)},
        open=AsyncMock(),
        close=AsyncMock(),
        inventory=Mock(return_value={}),
        input_evidence=lambda: {str(source): {"status": "unchanged"}},
    )
    monkeypatch.setattr(probe, "OwnedAssembly", lambda *_: owner)
    monkeypatch.setattr(probe, "document_state", lambda _: {"model": "clean"})
    monkeypatch.setattr(
        probe, "contact", Mock(side_effect=primary if outcome == "failed" else None)
    )
    monkeypatch.setattr(
        probe, "checkpoint", Mock(side_effect=[None, None, write_error])
    )
    with pytest.raises(ExceptionGroup) as caught:
        await probe.measure(
            object(), {}, tmp_path / "contact.json", probe.digest(source)
        )
    assert caught.value.exceptions == (
        (primary, write_error) if outcome == "failed" else (write_error,)
    )
    owner.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("inventory_result", ["empty", "read_error"])
async def test_final_inventory_receipt_requires_actual_native_read(
    monkeypatch, tmp_path, inventory_result
):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    source = tmp_path / "cad/out/sldasm/harmonic-analyzer.SLDASM"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"native source fixture")
    read_error = RuntimeError("final inventory unavailable")
    owner = NS(
        hashes={str(source): probe.digest(source)},
        open=AsyncMock(),
        close=AsyncMock(),
        inventory=Mock(
            side_effect=[{}, read_error if inventory_result == "read_error" else {}]
        ),
        input_evidence=lambda: {str(source): {"status": "unchanged"}},
    )
    monkeypatch.setattr(probe, "OwnedAssembly", lambda *_: owner)
    monkeypatch.setattr(probe, "document_state", lambda _: {"model": "clean"})
    monkeypatch.setattr(probe, "contact", Mock())
    monkeypatch.setattr(probe, "checkpoint", Mock())
    report = {}
    if inventory_result == "read_error":
        with pytest.raises(ExceptionGroup) as caught:
            await probe.measure(
                object(), report, tmp_path / "contact.json", probe.digest(source)
            )
        assert caught.value.exceptions == (read_error,)
        assert "final_inventory" not in report
        assert report["status"] == "failed"
    if inventory_result == "empty":
        await probe.measure(
            object(), report, tmp_path / "contact.json", probe.digest(source)
        )
        assert report["final_inventory"] == []
        assert report["status"] == "passed"
    assert report["baseline_inventory"] == []
    assert owner.inventory.call_count == 2
    owner.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_outer_timing_checkpoint_cannot_replace_measure_failure(
    monkeypatch, tmp_path
):
    from solidworks_mcp.adapters import pywin32_adapter

    monkeypatch.setattr(probe, "ROOT", tmp_path)
    monkeypatch.setattr(probe.sys, "prefix", str(tmp_path / ".venv"))
    monkeypatch.setattr(
        pywin32_adapter, "__file__", str(tmp_path / "SolidworksMCP-python/adapter.py")
    )
    monkeypatch.setattr(probe.subprocess, "check_output", lambda *a, **kw: "f" * 40)
    monkeypatch.setattr(probe, "digest", lambda _: "e" * 64)
    primary = ExceptionGroup(
        "native and cleanup", [RuntimeError("native read rejected")]
    )
    write_error = OSError("timing receipt unavailable")
    monkeypatch.setattr(probe, "measure", AsyncMock(side_effect=primary))
    monkeypatch.setattr(probe, "checkpoint", Mock(side_effect=write_error))
    adapter = NS(swApp=NS(GetProcessID=lambda: 123, RevisionNumber=lambda: "34.3.0"))
    with pytest.raises(ExceptionGroup) as caught:
        await probe.probe(adapter, tmp_path, "e" * 64)
    assert caught.value.exceptions == (primary, write_error)
