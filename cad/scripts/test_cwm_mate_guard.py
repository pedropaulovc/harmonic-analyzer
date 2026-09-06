r"""SolidWorks-free contract for the copied-mate safeguard in ``_cwm``.

The guard exists because `CopyWithMates2` bypasses `_assembly._mate`'s
hard-error check, so a copied mate SolidWorks refuses to solve would otherwise
surface only as a misleading downstream pose assert. A safeguard is only worth
having if it fails CLOSED, so these tests pin exactly that: every ambiguous COM
read must raise or re-scan, never quietly report "clean".

Run: ``uv run python -m pytest cad/scripts/test_cwm_mate_guard.py -q``
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _cwm  # noqa: E402


class FakeFeature:
    """A MateGroup subfeature. ``code`` is the (error, is_warning) tuple."""

    def __init__(self, name, code=(0, False)):
        self.Name = name
        self._code = code

    def GetErrorCode2(self):
        if self._code == "raise":
            raise RuntimeError("COM read failed")
        return self._code


class FakeExtension:
    """`GetWhatsWrong` in its EARLY-BOUND form: outs ride the return tuple.

    ``mode="unusable"`` returns None, the case that must fall back to the walk
    rather than read as "clean".
    """

    def __init__(self, feats, mode="ok"):
        self._feats = feats
        self._mode = mode

    def GetWhatsWrong(self):
        if self._mode == "unusable":
            return None
        if self._mode == "raise":
            raise RuntimeError("COM read failed")
        rows = [(f, f._code) for f in self._feats
                if isinstance(f._code, tuple) and f._code[0]]
        return (
            True,
            tuple(f for f, _ in rows),
            tuple(c[0] for _, c in rows),
            tuple(c[1] for _, c in rows),
        )


class FakeModel:
    def __init__(self, ext):
        self.Extension = ext


class FakeAdapter:
    def __init__(self, feats, mode="ok"):
        self._all = feats
        self.currentModel = FakeModel(FakeExtension(feats, mode))

    def _attempt(self, op, default=None):
        try:
            return op()
        except Exception:
            return default


def _read_member_like_the_real_one(obj, name):
    """Mirror `solidworks_mcp...assembly._read_member` exactly.

    It calls the member and FALLS BACK TO THE BOUND MEMBER ITSELF when the call
    raises -- that fallback is precisely what made the guard fail open, so the
    fake must reproduce it or these tests prove nothing.
    """
    member = getattr(obj, name, None)
    if not callable(member):
        return member
    try:
        return member()
    except Exception:
        return member


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    """Bypass the COM-only helpers: identity early-bind, list-backed walk."""
    monkeypatch.setattr(_cwm, "_early_bound", lambda obj, _iface: obj)
    mod = type(sys)("solidworks_mcp.adapters.solidworks.assembly")
    mod._mate_group_subfeatures = lambda adapter: list(adapter._all)
    mod._read_member = _read_member_like_the_real_one
    monkeypatch.setitem(
        sys.modules, "solidworks_mcp.adapters.solidworks.assembly", mod)


def _chain(*specs):
    return [FakeFeature(n, c) for n, c in specs]


def test_clean_scan_reports_nothing():
    adapter = FakeAdapter(_chain(("Coincident1", (0, False)),
                                 ("Distance1", (0, False))))
    assert _cwm.new_mate_errors(adapter) == {}


def test_hard_error_is_reported():
    adapter = FakeAdapter(_chain(("Coincident1", (0, False)),
                                 ("Distance2", (47, False))))
    assert _cwm.new_mate_errors(adapter) == {"Distance2": 47}


def test_warning_is_not_an_error():
    """Code 46 over-define co-flags are tolerated across this codebase."""
    adapter = FakeAdapter(_chain(("Distance1", (46, True)),))
    assert _cwm.new_mate_errors(adapter) == {}


def test_preexisting_error_is_not_blamed_on_the_next_copy():
    feats = _chain(("Distance1", (47, False)))
    adapter = FakeAdapter(feats)
    assert _cwm.new_mate_errors(adapter) == {"Distance1": 47}  # first sighting
    assert _cwm.new_mate_errors(adapter) == {}                 # already known


def test_only_errors_appearing_after_the_baseline_are_reported():
    feats = _chain(("Coincident1", (0, False)))
    adapter = FakeAdapter(feats)
    _cwm.prime_mate_baseline(adapter)

    appended = FakeFeature("Distance2", (47, False))
    feats.append(appended)
    assert _cwm.new_mate_errors(adapter) == {"Distance2": 47}


def test_unusable_whats_wrong_falls_back_to_the_walk_not_to_clean():
    """The fail-open case: GetWhatsWrong returning nothing must not pass."""
    adapter = FakeAdapter(_chain(("Distance2", (47, False))), mode="unusable")
    assert _cwm.new_mate_errors(adapter) == {"Distance2": 47}


def test_raising_whats_wrong_falls_back_to_the_walk():
    adapter = FakeAdapter(_chain(("Distance2", (47, False))), mode="raise")
    assert _cwm.new_mate_errors(adapter) == {"Distance2": 47}


def test_unreadable_error_code_RAISES_rather_than_reading_as_clean():
    """A failed GetErrorCode2 on the walk path must not count as healthy."""
    adapter = FakeAdapter(_chain(("Distance2", "raise")), mode="unusable")
    with pytest.raises(RuntimeError, match="cannot"):
        _cwm.new_mate_errors(adapter)


def test_unexpected_error_code_shape_RAISES():
    adapter = FakeAdapter(_chain(("Distance2", 47)), mode="unusable")
    with pytest.raises(RuntimeError, match="expected the"):
        _cwm.new_mate_errors(adapter)


def test_clean_baseline_then_clean_scan_stays_quiet():
    adapter = FakeAdapter(_chain(("Coincident1", (0, False))))
    _cwm.prime_mate_baseline(adapter)
    assert _cwm.new_mate_errors(adapter) == {}


# --- the guard is actually WIRED INTO copy_with_mates ----------------------
# On a healthy build the guard emits nothing, so "silent" is indistinguishable
# from "never ran" in a build log. These two drive the real `copy_with_mates`
# body -- with the COM call stubbed -- so the wiring itself is proven, not
# inferred from a green build.


class FakeComponent:
    _oleobj_ = object()


class FakeAssemblyDoc:
    """Stands in for the IAssemblyDoc wrapper `copy_with_mates` binds.

    ``creates`` are the mate features the copy APPENDS -- staged inside
    CopyWithMates2, not before it, because the guard deliberately ignores
    faults that already existed when the copy started.
    """

    def __init__(self, adapter, creates=()):
        self._adapter = adapter
        self._creates = list(creates)
        self.copied = 0

    def GetComponentByName(self, name):
        return FakeComponent()

    def CopyWithMates2(self, *args):
        self.copied += 1
        self._adapter._all.extend(self._creates)
        return False  # the return value lies; the guard judges from the model


@pytest.fixture
def _stub_com(monkeypatch):
    """Stub the COM edges of copy_with_mates: interface binding and VARIANT."""
    import win32com.client

    monkeypatch.setattr(win32com.client, "VARIANT", lambda vt, val: (vt, val))

    def fake_early_bound(obj, iface, *rest):
        if iface == "IAssemblyDoc" and isinstance(obj, FakeModel):
            return obj._asm
        return obj

    monkeypatch.setattr(_cwm, "_early_bound", fake_early_bound)


def _wire_adapter(existing, creates=()):
    adapter = FakeAdapter(list(existing))
    adapter.currentModel._asm = FakeAssemblyDoc(adapter, creates)
    return adapter


def _copy(adapter, **kw):
    return _cwm.copy_with_mates(
        adapter, ["cylinder-gear-1"], 2, [0.0, 0.0070565],
        flips=[False, True], repeat=[True, False],
        new_entities=[None, FakeComponent()], **kw)


def test_copy_with_mates_RAISES_when_the_copy_leaves_a_hard_error(_stub_com):
    """The positive control: prove the guard fires from copy_with_mates."""
    adapter = _wire_adapter(
        _chain(("Coincident1", (0, False))),
        creates=[FakeFeature("Distance32", (47, False))])
    with pytest.raises(RuntimeError, match="UNSOLVED"):
        _copy(adapter)
    assert adapter.currentModel._asm.copied == 1  # the copy really was attempted


def test_the_raised_message_names_the_remedy_and_the_slots(_stub_com):
    adapter = _wire_adapter(
        [], creates=[FakeFeature("Distance32", (47, False))])
    with pytest.raises(RuntimeError) as exc:
        _copy(adapter)
    msg = str(exc.value)
    assert "Distance32" in msg and "swFeatureError_e 47" in msg
    assert "swFeatureErrorMateIlldefined" in msg
    assert "FlipAlignment" in msg            # the remedy the message points at
    assert "flip_dimension=True" in msg      # slot 1's real argument
    assert "repeat=False" in msg             # slot 1's real argument


def test_copy_with_mates_stays_quiet_when_the_copy_is_clean(_stub_com):
    """The negative control -- silence here means healthy, not un-wired."""
    adapter = _wire_adapter(
        _chain(("Coincident1", (0, False))),
        creates=[FakeFeature("Distance32", (0, False))])
    _copy(adapter)
    assert adapter.currentModel._asm.copied == 1


def test_a_preexisting_error_is_not_blamed_on_the_copy(_stub_com):
    """A fault already present when the copy started is not this copy's fault."""
    adapter = _wire_adapter(_chain(("Distance9", (47, False))))
    _copy(adapter)
    assert adapter.currentModel._asm.copied == 1


def test_assert_solved_False_skips_the_scan_entirely(_stub_com):
    """The documented opt-out must not raise even with a new error present."""
    adapter = _wire_adapter(
        [], creates=[FakeFeature("Distance32", (47, False))])
    _copy(adapter, assert_solved=False)
    assert adapter.currentModel._asm.copied == 1

def test_distance_mate_lookup_is_traced() -> None:
    source = Path(_cwm.__file__).read_text(encoding="utf-8")
    assert (
        '@_telemetry.traced("copy_with_mates.distance_mate_lookup", '
        'label_param="name")\ndef _component_distance_mate(' in source
    )


@pytest.fixture
def pose_bank(monkeypatch):
    """Record the COM boundary of repeated resets without simulating a solver."""
    lookups = []
    transforms = []
    writes = []

    class PoseComponent:
        def __init__(self, name):
            self.name = name

        @property
        def Transform2(self):
            raise AssertionError("pose reset must only write the target transform")

        @Transform2.setter
        def Transform2(self, transform):
            writes.append((self.name, transform))

    components = {name: PoseComponent(name) for name in ("rocker-1", "rod-1")}

    def lookup(name):
        lookups.append(name)
        return components.get(name)

    def create_transform(adapter, values):
        transform = SimpleNamespace(values=tuple(values))
        transforms.append(transform)
        return transform

    module = sys.modules["solidworks_mcp.adapters.solidworks.assembly"]
    module._create_math_transform = create_transform
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GetComponentByName=lookup))
    return SimpleNamespace(
        adapter=adapter, lookups=lookups, transforms=transforms, writes=writes,
    )


def _pose_at(z):
    return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            0.0, 0.0, z, 1.0, 0.0, 0.0, 0.0]


def test_prepared_pose_resets_reuse_handles_and_transforms_in_order(pose_bank):
    """Repeated driver resets must not repeat component lookup or allocation."""
    targets = [("rocker-1", _pose_at(0.01)), ("rod-1", _pose_at(0.02))]
    prepared = _cwm.prepare_component_poses(pose_bank.adapter, iter(targets))
    assert pose_bank.writes == []  # preparation cannot change the solver's input

    for _ in range(6):  # three resets for each of two copied channels
        prepared.apply()

    assert pose_bank.lookups == ["rocker-1", "rod-1"]
    assert len(pose_bank.transforms) == 2
    expected = list(zip([name for name, _ in targets], pose_bank.transforms))
    assert pose_bank.writes == expected * 6
    assert [transform.values for transform in pose_bank.transforms] == [
        tuple(values) for _, values in targets
    ]


def test_prepare_missing_component_fails_before_any_pose_write(pose_bank):
    with pytest.raises(RuntimeError, match="component not found.*missing-1"):
        _cwm.prepare_component_poses(
            pose_bank.adapter,
            [("rocker-1", _pose_at(0.01)), ("missing-1", _pose_at(0.02))],
        )
    assert pose_bank.writes == []


def test_prepared_poses_cannot_be_applied_after_switching_documents(pose_bank):
    prepared = _cwm.prepare_component_poses(
        pose_bank.adapter, [("rocker-1", _pose_at(0.01))]
    )
    pose_bank.adapter.currentModel = object()
    with pytest.raises(RuntimeError, match="document changed"):
        prepared.apply()
    assert pose_bank.writes == []


def test_prepared_pose_groups_reset_only_the_requested_components(pose_bank):
    prepared = _cwm.prepare_component_poses(
        pose_bank.adapter,
        [("rocker-1", _pose_at(0.01)), ("rod-1", _pose_at(0.02))],
    )
    rocker, rod = prepared.groups(1)
    rocker.apply()
    rocker.apply()
    assert [name for name, _ in pose_bank.writes] == ["rocker-1", "rocker-1"]
    rod.apply()
    assert [name for name, _ in pose_bank.writes] == ["rocker-1", "rocker-1", "rod-1"]
    assert pose_bank.lookups == ["rocker-1", "rod-1"]
    assert len(pose_bank.transforms) == 2


def test_prepared_pose_groups_reject_an_incomplete_component_slice(pose_bank):
    prepared = _cwm.prepare_component_poses(
        pose_bank.adapter, [("rocker-1", _pose_at(0.01))]
    )
    with pytest.raises(ValueError, match="complete groups"):
        prepared.groups(4)
