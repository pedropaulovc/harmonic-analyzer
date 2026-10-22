"""Offline behavioral coverage of purchased-member paths, exports and certificates."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _part_configuration_exports as exports
import _preferences


# These are the seven physical members of the three heterogeneous shared SKUs,
# not seven separate native parts. Keep the registry real throughout these tests.
_MEMBERS = {
    "sh-vn-chain-link": ("InnerLink", "OuterLink"),
    "sh-vn-clamping-kit-hardware": ("HoldDownStud", "TNut", "FlangeNut"),
    "sh-vn-music-wire": ("LeverWire", "PenWire"),
}
_MEMBER_CASES = [
    (stem, member) for stem, members in _MEMBERS.items() for member in members
]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _NativePart:
    """Selection changes metadata; only rebuilding changes the exported body."""

    def __init__(self, path: Path, members: tuple[str, ...]) -> None:
        self.path = path
        self.members = members
        self.active = members[0]
        self.geometry = members[0]
        self.selected_bodies = ["body-1"]
        self.view = None
        self.refuse_member = None
        self.refuse_default_restore = False
        self.ignore_member = None
        self.rebuild_fault = None
        self.step_fault = None
        self.fault_member = members[-1]
        self.mutate_native = False

    @property
    def ConfigurationManager(self):
        return SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name=self.active))

    def GetPathName(self):
        return str(self.path)

    def ShowConfiguration2(self, member):
        if (
            self.refuse_default_restore
            and member == self.members[0]
            and self.active != member
        ):
            return False
        if member == self.refuse_member:
            return False
        if member != self.ignore_member:
            self.active = member
        return member in self.members

    def ForceRebuild3(self, _top_only):
        if self.active == self.fault_member and self.rebuild_fault == "force":
            return False
        self.geometry = self.active
        return True

    def EditRebuild3(self):
        if self.active == self.fault_member:
            if self.rebuild_fault == "edit":
                return False
            if self.rebuild_fault == "switch":
                self.active = self.members[0]
        return True

    def ShowNamedView2(self, _name, view):
        self.view = view
        return True

    def ClearSelection2(self, _all):
        self.selected_bodies.clear()

    def SaveAs3(self, filename, _version, _options):
        if self.mutate_native:
            self.path.write_bytes(b"unexpected native save during neutral export")
        fault = self.step_fault if self.active == self.fault_member else None
        if fault == "raise":
            raise RuntimeError("fake STEP writer failed")
        if fault == "missing":
            return 1
        Path(filename).write_text(
            ""
            if fault == "empty"
            else json.dumps(
                {
                    "configuration": self.active,
                    "geometry": self.geometry,
                    "bodies": self.selected_bodies or ["body-1", "body-2"],
                }
            ),
            encoding="utf-8",
        )
        return 0


class _Adapter:
    def __init__(self, doc: _NativePart) -> None:
        self.currentModel = doc
        self.mutate_output = None
        self.png_fault = None

    def _attempt(self, call, default=None):
        return call()

    def _zoom_to_fit(self, _model):
        pass

    async def export_image(self, request):
        doc = self.currentModel
        fault = self.png_fault if doc.active == doc.fault_member else None
        if fault == "raise":
            raise RuntimeError("fake image writer failed")
        if fault != "missing":
            Path(request["file_path"]).write_text(
                ""
                if fault == "empty"
                else json.dumps(
                    {
                        "configuration": doc.active,
                        "geometry": doc.geometry,
                        "view": doc.view,
                        "orientation": request["view_orientation"],
                    }
                ),
                encoding="utf-8",
            )
        if doc.active == doc.fault_member and self.mutate_output is not None:
            content = self.mutate_output.read_bytes()
            self.mutate_output.write_bytes(b"x" + content[1:])
        return SimpleNamespace(
            is_success=fault != "status",
            error="fake image failure",
            data=None,
        )


@pytest.fixture
def native_export(tmp_path, monkeypatch):
    real_paths = exports.configuration_export_paths
    monkeypatch.setattr(
        exports,
        "configuration_export_paths",
        lambda stem, out=None: real_paths(stem, tmp_path if out is None else out),
    )
    # Seat preference I/O is outside this member-export contract. Keep the real
    # configuration activation, rebuild, STEP writer, view helper and result check.
    monkeypatch.setattr(_preferences, "enforce_preferences", lambda *_args: {})

    def create(stem="sh-vn-clamping-kit-hardware"):
        members = exports.member_configurations(stem)
        native = tmp_path / "sldprt" / f"{stem}.SLDPRT"
        native.parent.mkdir(exist_ok=True)
        native.write_bytes(b"freshly saved and reopened native part")
        doc = _NativePart(native, members)
        return SimpleNamespace(
            stem=stem,
            members=members,
            native=native,
            doc=doc,
            adapter=_Adapter(doc),
            root=tmp_path,
            paths=real_paths(stem, tmp_path),
            certificate=exports.configuration_manifest_path(stem, tmp_path),
            execution=native.with_name(f".{stem}.execution"),
        )

    return create


def _produce(case):
    asyncio.run(
        exports.export_member_configurations(case.adapter, case.stem, case.members)
    )


def _stamp_execution(case):
    # dodo stamps the fresh native after the part hook. The hook itself must not
    # require an already-present execution token or overwrite an older token.
    case.execution.write_text(_digest(case.native), encoding="utf-8")


@pytest.mark.parametrize("kind", ["step", "stl", "png"])
@pytest.mark.parametrize("stem,member", _MEMBER_CASES)
def test_real_registry_members_have_exact_physical_paths(tmp_path, stem, member, kind):
    row = _config.parts(stem)
    assert tuple(row["configuration_quantities"]) == _MEMBERS[stem]
    assert row["default_configuration"] == _MEMBERS[stem][0]
    assert exports.member_configurations(stem) == _MEMBERS[stem]
    qualified = f"{stem}--{member.lower()}"
    basename = (
        stem if member == row["default_configuration"] and kind != "stl" else qualified
    )
    expected = {
        "step": tmp_path / "step" / f"{basename}.STEP",
        "stl": tmp_path / "stl" / f"{basename}.STL",
        "png": tmp_path / "png" / basename / f"{basename}_isometric.png",
    }[kind]
    assert exports.configuration_export_paths(stem, tmp_path)[member][kind] == expected
    assert (
        exports.configuration_export_paths(stem.replace("-", "_"), tmp_path)[member][
            kind
        ]
        == expected
    )


@pytest.mark.parametrize("stem", _MEMBERS)
def test_member_metadata_and_paths_read_only_the_requested_registry_row(
    monkeypatch, tmp_path, stem
):
    reads = []
    rows = {name: _config.parts(name) for name in _MEMBERS}

    def own_row(name):
        reads.append(name)
        assert name == stem, f"member export read a foreign part row: {name}"
        return rows[name]

    monkeypatch.setattr(_config, "parts", own_row)
    assert exports.member_configurations(stem.replace("-", "_")) == _MEMBERS[stem]
    paths = exports.configuration_export_paths(stem, tmp_path)
    assert tuple(paths) == _MEMBERS[stem]
    assert reads == [stem, stem]
    assert all(
        path.is_relative_to(tmp_path) and stem in path.name
        for formats in paths.values()
        for path in formats.values()
    )


@pytest.mark.parametrize("stem", _MEMBERS)
def test_producer_exports_rebuilt_members_and_restores_saved_default(
    native_export, stem
):
    case = native_export(stem)
    before = case.native.read_bytes()
    case.execution.write_text("older execution token", encoding="utf-8")
    # A stale scene STL must neither become part-owned nor be touched by export.
    for paths in case.paths.values():
        paths["stl"].parent.mkdir(exist_ok=True)
        paths["stl"].write_bytes(b"scene-owned STL")
    _produce(case)

    assert case.native.read_bytes() == before
    assert case.execution.read_text(encoding="utf-8") == "older execution token"
    assert case.doc.active == case.members[0]
    assert case.doc.geometry == case.members[0]
    certificate = json.loads(case.certificate.read_text(encoding="utf-8"))
    assert certificate["source"] == f"sldprt/{stem}.SLDPRT"
    assert certificate["execution_identity"] == hashlib.sha256(before).hexdigest()
    assert certificate["default_configuration"] == case.members[0]
    assert set(certificate["configurations"]) == set(case.members)
    for member, paths in case.paths.items():
        assert json.loads(paths["step"].read_text(encoding="utf-8")) == {
            "configuration": member,
            "geometry": member,
            "bodies": ["body-1", "body-2"],
        }
        assert json.loads(paths["png"].read_text(encoding="utf-8")) == {
            "configuration": member,
            "geometry": member,
            "view": 7,
            "orientation": "isometric",
        }
        assert paths["stl"].read_bytes() == b"scene-owned STL"
        records = certificate["configurations"][member]
        assert set(records) == {"step", "png"}
        for kind in ("step", "png"):
            path = paths[kind]
            assert records[kind] == {
                "path": path.relative_to(case.root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _digest(path),
            }
    owned = {p[k] for p in case.paths.values() for k in ("step", "png")}
    assert set(exports.part_configuration_outputs(stem, case.root)) == owned | {
        case.certificate
    }
    _stamp_execution(case)
    assert exports.validate_member_exports(stem, case.root) == owned


def test_certificate_tracks_execution_not_later_parent_save_bytes(native_export):
    case = native_export()
    _produce(case)
    _stamp_execution(case)
    identity = case.execution.read_text(encoding="utf-8")
    case.native.write_bytes(
        b"legitimate raw native byte churn from a parent assembly save"
    )
    assert _digest(case.native) != identity
    assert exports.validate_member_exports(case.stem, case.root)
    case.execution.write_text(
        "a" * 64 if identity != "a" * 64 else "b" * 64, encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="identity"):
        exports.validate_member_exports(case.stem, case.root)


@pytest.mark.parametrize("fault", ["missing", "empty", "invalid"])
def test_certificate_requires_a_valid_execution_token(native_export, fault):
    case = native_export()
    _produce(case)
    if fault != "missing":
        case.execution.write_text(
            "" if fault == "empty" else "not-an-execution-digest", encoding="utf-8"
        )
    with pytest.raises(RuntimeError, match="identity"):
        exports.validate_member_exports(case.stem, case.root)


@pytest.mark.parametrize("kind", ["step", "png"])
@pytest.mark.parametrize("fault", ["missing", "empty", "mutated"])
def test_validator_rejects_missing_empty_or_changed_member_bytes(
    native_export, kind, fault
):
    case = native_export()
    _produce(case)
    _stamp_execution(case)
    output = case.paths[case.members[-1]][kind]
    if fault == "missing":
        output.unlink()
    elif fault == "empty":
        output.write_bytes(b"")
    else:
        content = output.read_bytes()
        output.write_bytes(b"x" + content[1:])  # same size: the hash must matter
    with pytest.raises(RuntimeError, match="missing/empty|stale member"):
        exports.validate_member_exports(case.stem, case.root)


@pytest.mark.parametrize("kind", ["step", "png"])
@pytest.mark.parametrize("fault", ["missing", "empty", "raise"])
def test_failed_output_removes_old_certificate_and_restores_default(
    native_export, kind, fault
):
    case = native_export()
    _produce(case)
    assert case.certificate.is_file()
    if kind == "step":
        case.doc.step_fault = fault
    else:
        case.adapter.png_fault = fault
    with pytest.raises(RuntimeError, match="STEP|output missing/empty|writer failed"):
        _produce(case)
    assert not case.certificate.exists()
    assert case.doc.active == case.members[0]
    assert case.doc.geometry == case.members[0]


def test_failed_image_status_cannot_certify_even_nonempty_output(native_export):
    case = native_export()
    _produce(case)
    case.adapter.png_fault = "status"
    with pytest.raises(RuntimeError, match="fake image failure"):
        _produce(case)
    assert case.paths[case.members[-1]]["png"].stat().st_size > 0
    assert not case.certificate.exists()
    assert case.doc.active == case.members[0]


@pytest.mark.parametrize("fault", ["refused", "ignored", "force", "edit", "switch"])
def test_member_activation_or_rebuild_failure_cannot_certify(native_export, fault):
    case = native_export()
    _produce(case)
    if fault == "refused":
        case.doc.refuse_member = case.members[-1]
    elif fault == "ignored":
        case.doc.ignore_member = case.members[-1]
    else:
        case.doc.rebuild_fault = fault
    with pytest.raises(
        RuntimeError,
        match="activate export member|rebuild failed|changed during rebuild",
    ):
        _produce(case)
    assert not case.certificate.exists()
    assert case.doc.active == case.members[0]
    assert case.doc.geometry == case.members[0]


def test_wrong_saved_active_member_invalidates_previous_certificate(native_export):
    case = native_export()
    _produce(case)
    case.doc.active = case.members[-1]
    with pytest.raises(RuntimeError, match="saved active export member"):
        _produce(case)
    assert not case.certificate.exists()


def test_native_save_during_export_cannot_certify(native_export):
    case = native_export()
    _produce(case)
    case.doc.mutate_native = True
    with pytest.raises(RuntimeError, match="native bytes changed"):
        _produce(case)
    assert not case.certificate.exists()
    assert case.doc.active == case.members[0]


@pytest.mark.parametrize("cleanup_fault", ["restore", "native", "both"])
@pytest.mark.parametrize("export_fault", ["step", "png", "activation"])
def test_export_failure_stays_primary_when_cleanup_also_fails(
    native_export,
    export_fault,
    cleanup_fault,
):
    case = native_export()
    _produce(case)
    case.doc.refuse_default_restore = cleanup_fault in {"restore", "both"}
    case.doc.mutate_native = cleanup_fault in {"native", "both"}
    if export_fault == "step":
        case.doc.step_fault = "raise"
        message = "fake STEP writer failed"
    elif export_fault == "png":
        case.adapter.png_fault = "raise"
        message = "fake image writer failed"
    else:
        case.doc.refuse_member = case.members[-1]
        message = f"{case.stem}: could not activate export member {case.members[-1]!r}"

    with pytest.raises(RuntimeError) as caught:
        _produce(case)

    assert str(caught.value) == message
    notes = "\n".join(caught.value.__notes__)
    if cleanup_fault in {"restore", "both"}:
        assert "Default member restoration failed" in notes
        assert f"could not activate export member {case.members[0]!r}" in notes
        assert case.doc.active != case.members[0]
    else:
        assert case.doc.active == case.members[0]
    if cleanup_fault in {"native", "both"}:
        assert "Native SHA guard failed" in notes
        assert "native bytes changed during member export" in notes
    assert not case.certificate.exists()


@pytest.mark.parametrize("native_changes", [False, True])
def test_cleanup_failure_without_export_failure_still_prevents_certificate(
    native_export,
    native_changes,
):
    case = native_export()
    _produce(case)
    case.doc.refuse_default_restore = True
    case.doc.mutate_native = native_changes

    with pytest.raises(RuntimeError) as caught:
        _produce(case)

    assert str(caught.value) == (
        f"{case.stem}: could not activate export member {case.members[0]!r}"
    )
    if native_changes:
        notes = "\n".join(caught.value.__notes__)
        assert "Native SHA guard failed" in notes
        assert "native bytes changed during member export" in notes
    assert case.doc.active == case.members[-1]
    assert not case.certificate.exists()


def test_later_export_cannot_certify_a_mutated_earlier_member(native_export):
    case = native_export()
    _produce(case)
    case.adapter.mutate_output = case.paths[case.members[0]]["step"]
    with pytest.raises(RuntimeError):
        _produce(case)
    assert not case.certificate.exists()
    assert case.doc.active == case.members[0]


@pytest.mark.parametrize("stem", _MEMBERS)
def test_restored_payload_requires_matching_adopted_execution_and_certificate(
    native_export,
    stem,
):
    case = native_export(stem)
    owned = {paths[kind] for paths in case.paths.values() for kind in ("step", "png")}
    payload_paths = owned | {case.native, case.execution, case.certificate}

    def snapshot():
        return {
            path.relative_to(case.root): path.read_bytes() for path in payload_paths
        }

    def restore(payload, root):
        for relative, content in payload.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    _produce(case)
    _stamp_execution(case)
    loser = snapshot()
    case.native.write_bytes(b"another successfully built native execution")
    _produce(case)
    _stamp_execution(case)
    winner = snapshot()
    native_relative = case.native.relative_to(case.root)
    execution_relative = case.execution.relative_to(case.root)
    assert loser[execution_relative] != winner[execution_relative]

    restored_root = case.root / "restored-cache"
    restore(loser, restored_root)
    restored_outputs = {restored_root / path.relative_to(case.root) for path in owned}
    # Validation has only restored files: no adapter, document or native seat.
    assert exports.validate_member_exports(stem, restored_root) == restored_outputs

    # Adopting the winning native identity is not permission to retain the
    # losing task's certificate/neutral payload, even for the same members.
    restore(
        {
            native_relative: winner[native_relative],
            execution_relative: winner[execution_relative],
        },
        restored_root,
    )
    with pytest.raises(RuntimeError, match="identity"):
        exports.validate_member_exports(stem, restored_root)

    restore(winner, restored_root)
    assert exports.validate_member_exports(stem, restored_root) == restored_outputs
