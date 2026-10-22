r"""Tests for the artefact-cache provenance/observability surface (issue #73).

Pure python, NO SolidWorks and NO Azure -- the backend is faked in-memory and the
on-disk sinks (cache.jsonl, the per-label key sidecar) are redirected to a tmp dir.

    python cad/scripts/test_artifact_cache.py     # or: pytest cad/scripts/test_artifact_cache.py
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import logging
import os
import subprocess
import sys
import tarfile
import threading
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _artifact_cache as cache  # noqa: E402
import _telemetry  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures: a fake backend + tmp-redirected sinks, so nothing touches Azure or
# the real cad/out/reports/.
# --------------------------------------------------------------------------- #
class _FakeBackend:
    """In-memory stand-in for _BlobBackend: key -> packed bytes."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}

    def get(self, key):
        payload = self.blobs.get(key)
        return None if payload is None else io.BytesIO(payload)

    def etag(self, key):
        blob = self.blobs.get(key)
        return None if blob is None else hashlib.sha256(blob).hexdigest()

    def put(self, key, blob, *, replace_etag=None):
        if replace_etag is None:
            if self.exists(key):
                raise RuntimeError("already exists")
        elif self.etag(key) != replace_etag:
            raise RuntimeError("ETag changed")
        blob.seek(0)
        self.blobs[key] = blob.read()

    def exists(self, key):
        return key in self.blobs


def _packed(outputs):
    with cache._pack(outputs) as archive:
        return archive.read()


def _put_bytes(backend, key, payload, **kwargs):
    with io.BytesIO(payload) as archive:
        return backend.put(key, archive, **kwargs)


def _get_bytes(backend, key):
    archive = backend.get(key)
    if archive is None:
        return None
    with archive:
        return archive.read()


@pytest.fixture(autouse=True)
def private_archive_environment(tmp_path, monkeypatch):
    # Every test, including actual-SDK socket-free tests, stays off host caches.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.delenv("HARMONIC_ARCHIVE_CACHE_ROOT", raising=False)


@pytest.fixture
def real_unpack():
    return cache._unpack


@pytest.fixture
def fake(tmp_path, monkeypatch, real_unpack):
    """rw cache on a LOCAL-executor seat, wired to an in-memory backend with all
    sinks under tmp_path -- i.e. the role that both builds and publishes, so a HIT
    under an unpublished key is real drift. _unpack is a no-op (we test
    event/drift bookkeeping, not tar extraction)."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.delenv("HARMONIC_CACHE_DEBUG", raising=False)
    monkeypatch.setattr(cache, "_REPORTS", tmp_path)
    monkeypatch.setattr(cache, "_EVENTS_LOG", tmp_path / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", tmp_path / "cache-keys")
    monkeypatch.setattr(cache, "_unpack", lambda blob, outputs: None)
    monkeypatch.setattr(cache, "_KEY_INPUTS", {})
    monkeypatch.setattr(cache, "_KEY_CONTEXT", {})
    monkeypatch.setattr(cache, "_KEY_MANIFESTS", {})
    monkeypatch.setattr(cache, "_REFRESH_ETAGS", {})
    backend = _FakeBackend()
    monkeypatch.setattr(cache, "_BACKEND", backend)
    return backend


def _digest_one(path):
    """Stand-in for ContentChecker._digest: hash the file's text; missing -> OSError
    (exactly the contract cache_key/key_inputs rely on to mark a dep <missing>)."""
    return Path(path).read_text(encoding="utf-8")


def _events(tmp):
    log = tmp / "cache.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _make_dep(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# --------------------------------------------------------------------------- #
# Key derivation + provenance
# --------------------------------------------------------------------------- #
def test_cache_key_is_deterministic_and_label_inert(tmp_path):
    a = _make_dep(tmp_path, "a.txt", "alpha")
    b = _make_dep(tmp_path, "b.txt", "beta")
    k1 = cache.cache_key([a, b], _digest_one)
    k2 = cache.cache_key([b, a], _digest_one, label="part:x")  # order + label irrelevant
    assert k1 == k2
    # A content change must move the key.
    Path(a).write_text("ALPHA", encoding="utf-8")
    assert cache.cache_key([a, b], _digest_one) != k1


def test_key_inputs_sorted_with_missing_marker(tmp_path):
    present = _make_dep(tmp_path, "z.txt", "z")
    missing = str(tmp_path / "gone.txt")
    key, inputs = cache.key_inputs([present, missing], _digest_one)
    rels = [rel for rel, _ in inputs]
    assert rels == sorted(rels)
    digests = dict(inputs)
    assert digests["gone.txt"] == "<missing>"
    assert key == cache.cache_key([present, missing], _digest_one)


@pytest.mark.parametrize("as_iterator", [False, True])
def test_key_inputs_preserves_equal_tag_order_and_duplicates(
    tmp_path, monkeypatch, as_iterator
):
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path / "repo")
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    a = _make_dep(left, "same.txt", "alpha")
    z = _make_dep(right, "same.txt", "zeta")
    deps = [z, a, z]
    key, inputs = cache.key_inputs(
        iter(deps) if as_iterator else deps, _digest_one, salt="ties"
    )
    assert deps == [z, a, z]
    assert inputs == [("same.txt", "zeta"), ("same.txt", "alpha"), ("same.txt", "zeta")]
    expected = hashlib.sha256(f"epoch={cache._CACHE_EPOCH}\0salt=ties\0".encode())
    for tag, digest in inputs:
        expected.update(f"{tag}\0{digest}\0".encode())
    assert key == expected.hexdigest()
    assert cache.key_inputs([a, z, z], _digest_one, salt="ties")[0] != key


def test_key_inputs_refreshes_alias_tags_and_keeps_original_digest_paths(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path.resolve())
    first = tmp_path / "first"
    second = tmp_path / "second"
    for target in (first, second):
        target.mkdir()
        _make_dep(target, "input.yaml", '{ "value": 1 }\n')
        _make_dep(target, "input.bin", '{ "value": 1 }\n')
    alias = tmp_path / "alias"

    def point_alias(target):
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            # Junctions need no symlink privilege; both endpoints stay in tmp_path.
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
                check=True,
                capture_output=True,
                text=True,
            )

    def remove_alias():
        if alias.is_symlink():
            alias.unlink()
        else:
            alias.rmdir()

    calls = []

    def digest_one(path):
        calls.append(path)
        text = Path(path).read_text(encoding="utf-8")
        return json.dumps(json.loads(text)) if Path(path).suffix == ".yaml" else text

    deps = [str(alias / "input.yaml"), str(alias / "input.bin")]
    point_alias(first)
    try:
        first_result = cache.key_inputs(deps, digest_one, salt="alias")
        assert calls == [deps[1], deps[0]]
        assert first_result[1] == [
            ("first/input.bin", '{ "value": 1 }\n'),
            ("first/input.yaml", '{"value": 1}'),
        ]
        assert first_result == cache.key_inputs(
            [str(first / "input.yaml"), str(first / "input.bin")],
            digest_one,
            salt="alias",
        )
    finally:
        remove_alias()

    point_alias(second)
    try:
        calls.clear()
        second_result = cache.key_inputs(deps, digest_one, salt="alias")
        assert calls == [deps[1], deps[0]]
        assert second_result[1] == [
            ("second/input.bin", '{ "value": 1 }\n'),
            ("second/input.yaml", '{"value": 1}'),
        ]
        assert second_result == cache.key_inputs(
            [str(second / "input.yaml"), str(second / "input.bin")],
            digest_one,
            salt="alias",
        )
        assert second_result[0] != first_result[0]
    finally:
        remove_alias()




# --------------------------------------------------------------------------- #
# Event log + store/restore round-trip
# --------------------------------------------------------------------------- #
def test_store_then_restore_logs_events_and_stamps_key(tmp_path, fake):
    out = tmp_path / "out.bin"
    out.write_text("payload", encoding="utf-8")
    key = "k" * 64

    cache.store(key, [out], "part:x")
    assert key in fake.blobs                                  # published
    assert cache.last_stored_key("part:x") == key            # sidecar stamped

    assert cache.restore(key, [out], "part:x") is True        # HIT
    events = [e["event"] for e in _events(tmp_path)]
    assert events == ["store", "restore_hit"]
    assert all(e["key"] == key for e in _events(tmp_path))


def test_store_retains_last_published_input_provenance(tmp_path, fake):
    """Issue #255: after the working tree moves to a new key, the old per-dep
    digests must remain available beside the last published key for a readable
    historical diff."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    out = tmp_path / "out.bin"
    out.write_text("payload", encoding="utf-8")
    cache.store(key, [out], "part:x")

    assert cache.last_stored_key("part:x") == key
    assert cache.last_stored_inputs("part:x") == [("input.py", "VALUE = 1\n")]

    Path(dep).write_text("VALUE = 2\n", encoding="utf-8")
    cache.cache_key([dep], _digest_one, label="part:x")
    assert cache.last_stored_inputs("part:x") == [("input.py", "VALUE = 1\n")]




def test_restore_hit_over_a_share_locked_output_raises_instead_of_falling_through(
    tmp_path, fake, monkeypatch
):
    """The one restore failure that must not become "building locally": a cached
    build exists but SolidWorks still holds the output (Windows share lock), and
    a local rebuild would mint a token the fleet cannot reproduce."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"

    def refuse(_blob, _outputs):
        raise PermissionError(13, "Permission denied", "cad/out/sldprt/x.SLDPRT")

    monkeypatch.setattr(cache, "_unpack", refuse)

    with pytest.raises(cache.RestoreLocked, match="share-locked") as info:
        cache.restore(key, [], "part:x")

    assert info.value.key == key
    assert [e["event"] for e in _events(tmp_path)] == ["restore_locked"]


def test_restore_other_unpack_errors_still_fall_through(tmp_path, fake, monkeypatch):
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"
    monkeypatch.setattr(
        cache, "_unpack", lambda _blob, _outputs: (_ for _ in ()).throw(OSError("disk full"))
    )

    assert cache.restore(key, [], "part:x") is False
    assert [e["event"] for e in _events(tmp_path)] == ["restore_error"]


@pytest.fixture
def archive_tree(tmp_path, fake, real_unpack, monkeypatch):
    """Real replacement with all source/output paths confined to a throwaway repo."""
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path)
    root = tmp_path / "cad" / "out"
    root.mkdir(parents=True)
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", root)
    monkeypatch.setattr(cache, "_unpack", real_unpack)
    return root


@pytest.mark.parametrize("optional_directory", [False, True])
def test_restore_replaces_absent_outputs_and_whole_owned_directories(
    archive_tree, fake, optional_directory
):
    root = archive_tree
    native = root / "sldprt" / "leaf.SLDPRT"
    optional = root / "stl" / "leaf.STL"
    views = root / "png" / "leaf"
    native.parent.mkdir()
    native.write_bytes(b"winner-native")
    views.mkdir(parents=True)
    canonical = views / "canonical.png"
    canonical.write_bytes(b"winner-render")
    # Include duplicate/nested inventory entries: deleting the parent must not
    # delete an already-installed child on a later pass.
    outputs = [native, optional, views, canonical, views]
    fake.blobs["winner"] = _packed(outputs)
    native.write_bytes(b"loser-native")
    canonical.write_bytes(b"loser-render")
    optional.parent.mkdir()
    if optional_directory:
        optional.mkdir()
        (optional / "loser.STL").write_bytes(b"loser-only geometry")
    else:
        optional.write_bytes(b"loser-only geometry")
    stale = views / "loser-only"
    stale.mkdir()
    (stale / "geometry.STL").write_bytes(b"stale directory member")
    sibling = views.parent / "unrelated"
    sibling.mkdir()
    (sibling / "keep.png").write_bytes(b"unrelated")

    assert cache.restore("winner", outputs, "part:leaf") is True
    assert native.read_bytes() == b"winner-native"
    assert canonical.read_bytes() == b"winner-render"
    assert not optional.exists()
    assert not stale.exists()
    assert (sibling / "keep.png").read_bytes() == b"unrelated"
    assert not list(root.glob(".cache-restore-*"))


def test_restore_keeps_winner_files_missing_from_local_discovery_inventory(
    archive_tree, fake
):
    root = archive_tree
    native = root / "sldprt" / "channel.SLDASM"
    native.parent.mkdir()
    native.write_bytes(b"winner-native")
    winner_variant = native.parent / "spring-installed-stretch-10.SLDPRT"
    winner_variant.write_bytes(b"winner-spring")
    fake.blobs["winner"] = _packed([native, winner_variant])
    winner_variant.unlink()
    loser_variant = native.parent / "spring-installed-stretch-20.SLDPRT"
    loser_variant.write_bytes(b"loser-spring")
    sibling = native.parent / "unrelated.SLDPRT"
    sibling.write_bytes(b"unrelated")

    assert cache.restore("winner", [native, loser_variant], "assembly:channel")
    assert not loser_variant.exists()
    assert winner_variant.read_bytes() == b"winner-spring"
    assert sibling.read_bytes() == b"unrelated"


@pytest.mark.parametrize("invalid", ["output-root", "ancestor", "outside"])
def test_restore_validates_every_deletion_target_before_removal(
    archive_tree, fake, invalid
):
    root = archive_tree
    native = root / "leaf.SLDPRT"
    native.write_bytes(b"winner")
    fake.blobs["winner"] = _packed([native])
    native.write_bytes(b"loser")
    outside = root.parent / "unrelated.txt"
    outside.write_bytes(b"unrelated")
    bad = {"output-root": root, "ancestor": root.parent, "outside": outside}[invalid]

    assert cache.restore("winner", [native, bad], "part:leaf") is False
    assert native.read_bytes() == b"loser"
    assert outside.read_bytes() == b"unrelated"
    assert not list(root.glob(".cache-restore-*"))


def test_restore_rejects_aliased_deletion_target_without_deleting_its_sibling(
    archive_tree, fake
):
    root = archive_tree
    native = root / "leaf.SLDPRT"
    native.write_bytes(b"winner")
    fake.blobs["winner"] = _packed([native])
    native.write_bytes(b"loser")
    sibling = root / "unrelated"
    sibling.mkdir()
    (sibling / "keep.txt").write_bytes(b"unrelated")
    alias = root / "alias"
    try:
        alias.symlink_to(sibling, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(sibling)],
            check=True, capture_output=True, text=True,
        )
    try:
        assert cache.restore("winner", [native, alias], "part:leaf") is False
        assert native.read_bytes() == b"loser"
        assert (sibling / "keep.txt").read_bytes() == b"unrelated"
    finally:
        if alias.is_symlink():
            alias.unlink()
        else:
            alias.rmdir()


@pytest.mark.parametrize("name,kind", [
    ("cad/out/../../source.py", tarfile.REGTYPE),
    ("cad/scripts/source.py", tarfile.REGTYPE),
    ("cad/out/link", tarfile.SYMTYPE),
    ("cad/out/link", tarfile.LNKTYPE),
    ("cad/out/fifo", tarfile.FIFOTYPE),
    ("cad\\out\\alias", tarfile.REGTYPE),
    ("cad/out/leaf.SLDPRT:stream", tarfile.REGTYPE),
    ("cad/out", tarfile.DIRTYPE),
])
def test_restore_validates_all_archive_members_before_removal(
    archive_tree, fake, name, kind
):
    native = archive_tree / "leaf.SLDPRT"
    native.write_bytes(b"loser")
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        good = tarfile.TarInfo("cad/out/leaf.SLDPRT")
        good.size = len(b"winner")
        archive.addfile(good, io.BytesIO(b"winner"))
        bad = tarfile.TarInfo(name)
        bad.type = kind
        bad.linkname = "cad/out/leaf.SLDPRT" if bad.islnk() or bad.issym() else ""
        archive.addfile(bad)
    fake.blobs["winner"] = payload.getvalue()

    assert cache.restore("winner", [native], "part:leaf") is False
    assert native.read_bytes() == b"loser"
    assert not list(archive_tree.glob(".cache-restore-*"))


def test_restore_stages_complete_payload_before_removing_outputs(
    archive_tree, fake, monkeypatch
):
    native = archive_tree / "leaf.SLDPRT"
    native.write_bytes(b"winner")
    fake.blobs["winner"] = _packed([native])
    native.write_bytes(b"loser")
    original = tarfile.TarFile.makefile

    def incomplete(archive, member, targetpath):
        original(archive, member, targetpath)
        raise tarfile.ReadError("truncated payload after a staged member")

    monkeypatch.setattr(tarfile.TarFile, "makefile", incomplete)
    assert cache.restore("winner", [native], "part:leaf") is False
    assert native.read_bytes() == b"loser"
    assert not list(archive_tree.glob(".cache-restore-*"))


@pytest.mark.parametrize("damage", ["empty", "truncated", "conflicting-shape"])
def test_restore_rejects_invalid_real_archives_without_removing_outputs(
    archive_tree, fake, damage
):
    import gzip

    native = archive_tree / "leaf.SLDPRT"
    native.write_bytes(b"loser")
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:", format=tarfile.USTAR_FORMAT) as archive:
        if damage != "empty":
            good = tarfile.TarInfo("cad/out/leaf.SLDPRT")
            good.size = 4096
            archive.addfile(good, io.BytesIO(b"W" * good.size))
            if damage == "conflicting-shape":
                archive.addfile(tarfile.TarInfo("cad/out/leaf.SLDPRT/child"))
    raw = payload.getvalue()
    fake.blobs["winner"] = gzip.compress(raw[:612] if damage == "truncated" else raw)

    assert cache.restore("winner", [native], "part:leaf") is False
    assert native.read_bytes() == b"loser"
    assert not list(archive_tree.glob(".cache-restore-*"))


def test_miss_retains_previous_and_current_inputs(tmp_path, fake):
    """Once a rebuild publishes the new key, its sidecar advances; the miss event
    must therefore preserve both sides of the drift for later diagnosis."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    old_key = cache.cache_key([dep], _digest_one, label="part:x")
    out = tmp_path / "out.bin"
    out.write_text("payload", encoding="utf-8")
    cache.store(old_key, [out], "part:x")

    Path(dep).write_text("VALUE = 2\n", encoding="utf-8")
    new_key = cache.cache_key([dep], _digest_one, label="part:x")
    assert cache.restore(new_key, [], "part:x") is False
    event = _events(tmp_path)[-1]
    assert event["previous_key"] == old_key
    assert event["previous_inputs"] == [{"path": "input.py", "digest": "VALUE = 1\n"}]
    assert event["inputs"] == [{"path": "input.py", "digest": "VALUE = 2\n"}]


def test_store_nothing_on_disk_logs_empty(tmp_path, fake):
    cache.store("k" * 64, [tmp_path / "absent.bin"], "part:x")
    assert [e["event"] for e in _events(tmp_path)] == ["store_empty"]
    assert cache.last_stored_key("part:x") is None            # nothing published


def _telemetry_logger(caplog, monkeypatch):
    """The telemetry logger, wired so caplog sees its records."""
    logger = _telemetry.get_logger()
    monkeypatch.setattr(logger, "propagate", True)
    caplog.clear()
    return logger


def _records(caplog, logger, level):
    return [r.getMessage() for r in caplog.records
            if r.name == logger.name and r.levelno == level]


# --------------------------------------------------------------------------- #
# THE issue-#73 case: store-skip-on-hit drift is surfaced on a HIT -- loudly for
# a seat that publishes what it builds, quietly (but still recorded) for one that
# structurally cannot have published the key it hit.
# --------------------------------------------------------------------------- #
def test_hit_under_new_key_warns_drift(tmp_path, fake, caplog, monkeypatch):
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")          # this seat publishes k_old
    fake.blobs[k_new] = b"built-elsewhere"        # another seat publishes k_new
    logger = _telemetry_logger(caplog, monkeypatch)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        assert cache.restore(k_new, [out], "part:x") is True
    assert _records(caplog, logger, logging.WARNING)
    event = _events(tmp_path)[-1]
    assert event["event"] == "restore_hit_drift"
    assert event["label"] == "part:x"
    assert event["key"] == k_new
    assert event["previous_key"] == k_old
    assert event["drift_expected"] is False
    # A HIT does NOT re-stamp the sidecar -- the seat still only ever published k_old.
    assert cache.last_stored_key("part:x") == k_old


def test_farm_submitter_hit_on_worker_published_key_does_not_warn(
    tmp_path, fake, caplog, monkeypatch
):
    """Under ``--executor farm`` the submitter dispatches every cache-missing leaf
    and never reaches ``store``, so EVERY hit is under a key the worker published.
    Warning there fires on the correct path and trains the operator to ignore the
    signal -- it must stay off the console while cache.jsonl keeps the event."""
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")          # published back when it built locally
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    fake.blobs[k_new] = b"built-by-a-worker"
    logger = _telemetry_logger(caplog, monkeypatch)

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        assert cache.restore(k_new, [out], "part:x") is True
    assert _records(caplog, logger, logging.WARNING) == []
    event = _events(tmp_path)[-1]
    assert event["event"] == "restore_hit_drift"      # the record stays complete
    assert event["previous_key"] == k_old
    assert event["drift_expected"] is True
    assert event["drift_reason"] == "executor=farm"


def test_read_only_seat_hit_on_foreign_key_does_not_warn(
    tmp_path, fake, caplog, monkeypatch
):
    """Same reasoning by role rather than executor: a ``ro`` seat declines to
    publish, so it cannot have stored the key it hits."""
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")          # published while still rw
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    fake.blobs[k_new] = b"built-elsewhere"
    logger = _telemetry_logger(caplog, monkeypatch)

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        assert cache.restore(k_new, [out], "part:x") is True
    assert _records(caplog, logger, logging.WARNING) == []
    event = _events(tmp_path)[-1]
    assert event["drift_expected"] is True
    assert event["drift_reason"] == "cache_mode=ro"


def test_drift_bookkeeping_failure_cannot_demote_a_hit(tmp_path, fake, monkeypatch):
    """The severity decision runs AFTER the outputs are on disk (it reads the
    sidecar and imports `_farm`). If it raises, the HIT must still stand: falling
    through to "building locally" would mint a fresh .execution token and fork
    every dependent's cache key off the fleet's."""
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")
    fake.blobs[k_new] = b"built-elsewhere"

    def boom():
        raise ModuleNotFoundError("No module named '_farm'")

    monkeypatch.setattr(cache, "_cannot_publish_reason", boom)

    assert cache.restore(k_new, [out], "part:x") is True
    assert "restore_error" not in [e["event"] for e in _events(tmp_path)]


def test_hit_under_same_key_is_not_drift(tmp_path, fake):
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    key = "3" * 64
    cache.store(key, [out], "part:x")
    assert cache.restore(key, [out], "part:x") is True
    assert [e["event"] for e in _events(tmp_path)][-1] == "restore_hit"


# --------------------------------------------------------------------------- #
# Mode gating: off writes nothing; ro pulls but records a publish-skip
# --------------------------------------------------------------------------- #
def test_mode_off_is_silent(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    assert cache.restore("k" * 64, [], "part:x") is False
    cache.store("k" * 64, [tmp_path / "out.bin"], "part:x")
    assert _events(tmp_path) == []                            # no jsonl on a disabled seat


def test_mode_ro_records_store_skip(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    cache.store("k" * 64, [tmp_path / "out.bin"], "part:x")
    assert [e["event"] for e in _events(tmp_path)] == ["store_skip"]


def test_probe_presence_and_disabled(tmp_path, fake, monkeypatch):
    key = "p" * 64
    fake.blobs[key] = b"x"
    assert cache.probe(key) is True
    assert cache.probe("q" * 64) is False
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    assert cache.probe(key) is None                          # disabled -> unknown


# --------------------------------------------------------------------------- #
# Publish atomicity -- the blob backend against Azure block-blob semantics
# --------------------------------------------------------------------------- #
class _BlockBlobService:
    """One container's block blobs, with the service rules a chunked publish
    relies on: staged blocks are private to the blob until a commit; a commit
    resolves each listed ID to its uncommitted block, else its committed one
    (the SDK's ``latest``); and a commit garbage-collects every uncommitted
    block it did not list."""

    def __init__(self):
        self.committed: dict[str, list[tuple[str, bytes]]] = {}
        self.uncommitted: dict[str, dict[str, bytes]] = {}
        self.metadata = {}
        self.etags = {}
        self.calls = []
        self.on_stage = None

    def get_blob_client(self, name):
        service = self

        class _Client:
            def _condition(self, *, match_condition, etag=None):
                from azure.core import MatchConditions

                if match_condition == MatchConditions.IfMissing:
                    assert etag is None  # the SDK must not receive a wildcard etag
                    if name in service.committed:
                        raise RuntimeError("condition failed: already exists")
                elif match_condition == MatchConditions.IfNotModified:
                    if etag != service.etags.get(name):
                        raise RuntimeError("condition failed: ETag changed")
                else:
                    pytest.fail("unconditional block commit or replacement")

            def _published(self, metadata):
                service.metadata[name] = dict(metadata)
                service.etags[name] = str(int(service.etags.get(name, "0")) + 1)
                service.uncommitted.pop(name, None)

            def upload_blob(self, data, *, length, overwrite, metadata, **condition):
                service.calls.append(("upload", name, {"overwrite": overwrite, **condition}, metadata))
                if overwrite:
                    self._condition(**condition)
                elif name in service.committed:
                    raise RuntimeError("condition failed: already exists")
                payload = data.read()
                assert len(payload) == length
                service.committed[name] = [("single", payload)]
                self._published(metadata)

            def exists(self):
                return name in service.committed

            def get_blob_properties(self):
                from azure.core.exceptions import ResourceNotFoundError

                service.calls.append(("etag", name))
                if name not in service.committed:
                    raise ResourceNotFoundError("missing")
                return types.SimpleNamespace(
                    etag=service.etags[name], metadata=dict(service.metadata[name]),
                    size=len(service.content(name)),
                )

            def download_blob(self, **kwargs):
                from azure.core.exceptions import ResourceNotFoundError

                service.calls.append(("download", name, kwargs))
                assert kwargs["max_concurrency"] == cache._TRANSFER_CONCURRENCY
                if "etag" in kwargs:
                    self._condition(
                        etag=kwargs["etag"], match_condition=kwargs["match_condition"],
                    )
                if name not in service.committed:
                    raise ResourceNotFoundError("missing")
                # Snapshot body and response metadata together, like the SDK.
                data = service.content(name)
                properties = types.SimpleNamespace(
                    metadata=dict(service.metadata[name]), etag=service.etags[name],
                    size=len(data),
                )

                def readinto(stream):
                    service.calls.append(("readinto", name))
                    assert stream.seekable()
                    # Out-of-order SDK writes must be hashed only after completion.
                    split = len(data) // 2
                    stream.seek(split)
                    stream.write(data[split:])
                    stream.seek(0)
                    stream.write(data[:split])
                    return len(data)

                return types.SimpleNamespace(readinto=readinto, properties=properties)

            def stage_block(self, block_id, data):
                service.uncommitted.setdefault(name, {})[block_id] = bytes(data)
                if service.on_stage is not None:
                    service.on_stage()

            def commit_block_list(self, blocks, *, metadata, **condition):
                service.calls.append(("commit", name, condition, metadata))
                staged = service.uncommitted.get(name, {})
                old = dict(service.committed.get(name, []))
                resolved = []
                for block in blocks:
                    if block.id in staged:
                        resolved.append((block.id, staged[block.id]))
                    elif block.id in old:
                        resolved.append((block.id, old[block.id]))
                    else:
                        raise RuntimeError(f"InvalidBlockList: {block.id}")
                self._condition(**condition)
                service.committed[name] = resolved
                self._published(metadata)

        return _Client()

    def content(self, name):
        return b"".join(data for _, data in self.committed[name])


def test_interleaved_chunked_publishes_never_commit_a_torn_archive(monkeypatch):
    """Two writers of one key upload different bytes (tar mtimes, gzip level).
    If writer B publishes while writer A is between its first and second staged
    block, the stored entry must be one writer's archive whole -- never B's
    first block followed by A's tail (a CRC failure on every later restore)."""
    monkeypatch.setattr(cache, "_SINGLE_PUT_MAX", 8)
    monkeypatch.setattr(cache, "_BLOCK_SIZE", 4)
    monkeypatch.setattr(cache, "_TRANSFER_CONCURRENCY", 1)  # deterministic order
    service = _BlockBlobService()
    backend = cache._BlobBackend(service)
    key = "c" * 64
    first, second = b"A" * 16, b"B" * 16

    def competing_publish():
        service.on_stage = None
        _put_bytes(backend, key, second)

    service.on_stage = competing_publish
    with pytest.raises(RuntimeError, match="InvalidBlockList|condition failed"):
        _put_bytes(backend, key, first)

    assert service.content(backend._name(key)) == second
    assert _get_bytes(backend, key) == second


_LEAF_RESOURCE = "microsoft.applicationId=app,farm.worker=w@1,farm.execution=wf/run/1"


@pytest.fixture
def leaf(monkeypatch):
    """A farm leaf execution in rw mode, with prewarm state isolated per test and
    its exit hook captured instead of registered with the interpreter.

    Only the cache module's OWN ``atexit`` binding is replaced. Patching the shared
    ``atexit.register`` would also capture every other registration made in the
    window -- e.g. ``weakref.finalize``'s one-shot ``_exitfunc``, registered by
    whichever thread first builds a finalizer: the OTel batch exporter's first POST
    (a urllib3 pool) lands ~5 s into the process, so on a slow run it fell inside a
    prewarm test and failed check:cache."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", _LEAF_RESOURCE)
    monkeypatch.setattr(cache, "_BACKEND", cache._UNSET)
    monkeypatch.setattr(cache, "_PREWARMED", None)
    exits: list[tuple] = []
    monkeypatch.setattr(
        cache, "atexit", types.SimpleNamespace(register=lambda *args: exits.append(args))
    )
    return exits


def test_leaf_captures_only_the_cache_modules_exit_hooks(leaf):
    """An exit hook registered by other code while a leaf test runs (another
    thread's first ``weakref.finalize``) stays out of the captured list."""
    import atexit

    def unrelated():
        pass

    atexit.register(unrelated)
    atexit.unregister(unrelated)
    assert leaf == []


def _gated_backend():
    """A fake whose prewarm HEAD blocks until released, recording the order."""
    import threading

    backend = _FakeBackend()
    order: list[str] = []
    release = threading.Event()

    def head(key):
        order.append(f"head {key}")
        release.wait(5)
        order.append("head done")
        return False

    backend.exists = head
    return backend, order, release


def test_prewarm_opens_the_connection_once_and_the_probe_reuses_it(leaf, monkeypatch):
    """A probe that arrives while the prewarm's HEAD is still in flight waits for
    that request, so it reuses the connection it opens -- rather than racing it
    with a second cold TLS handshake -- and the client is built exactly once."""
    import threading

    backend, order, release = _gated_backend()
    built: list[int] = []
    monkeypatch.setattr(cache, "_make_backend", lambda: built.append(1) or backend)
    warm = cache.prewarm()
    assert warm is not None
    while "head prewarm" not in order:  # client built, HEAD in flight
        threading.Event().wait(0.01)

    threading.Timer(0.2, release.set).start()
    assert cache._backend() is backend
    order.append("probe")
    warm.join(5)
    assert order == ["head prewarm", "head done", "probe"]
    assert built == [1]
    assert [args[0] for args in leaf] == [cache._join_prewarm]


def test_a_stalled_prewarm_delays_the_probe_only_by_its_bound(leaf, monkeypatch):
    """The cache verdict never depends on the prewarm: a HEAD that hangs costs the
    first real call at most ``_PREWARM_WAIT_S``, after which it proceeds."""
    import time

    backend, order, release = _gated_backend()
    monkeypatch.setattr(cache, "_make_backend", lambda: backend)
    monkeypatch.setattr(cache, "_PREWARM_WAIT_S", 0.2)
    warm = cache.prewarm()
    try:
        while "head prewarm" not in order:
            time.sleep(0.01)
        started = time.monotonic()
        assert cache._backend() is backend
        assert time.monotonic() - started < 2
        assert "head done" not in order
    finally:
        release.set()
        warm.join(5)


def test_a_stalled_prewarm_holds_interpreter_exit_only_by_its_bound(leaf, monkeypatch):
    """The exit hook joins so the prewarm's spans end before telemetry closes its
    exporters -- but a hung prewarm must not hold the leaf's exit hostage."""
    import time

    backend, order, release = _gated_backend()
    monkeypatch.setattr(cache, "_make_backend", lambda: backend)
    monkeypatch.setattr(cache, "_PREWARM_JOIN_S", 0.2)
    warm = cache.prewarm()
    try:
        (hook, thread), = leaf
        started = time.monotonic()
        hook(thread)
        assert time.monotonic() - started < 2
        assert warm.is_alive()
    finally:
        release.set()
        warm.join(5)


@pytest.mark.parametrize("failure", ["none", "raises"])
def test_a_failed_prewarm_never_turns_the_cache_off(leaf, monkeypatch, failure):
    """Only the real call may memoize 'no backend': a prewarm whose client cannot
    be built leaves the backend unset, so the probe builds (and reports) its own."""
    attempts: list[str] = []

    def speculative_failure():
        attempts.append("prewarm")
        if failure == "raises":
            raise RuntimeError("constructor failed")
        return None

    monkeypatch.setattr(cache, "_make_backend", speculative_failure)
    cache.prewarm().join(5)
    assert isinstance(cache._BACKEND, cache._Unset)

    backend = _FakeBackend()
    monkeypatch.setattr(cache, "_make_backend", lambda: attempts.append("probe") or backend)
    assert cache._backend() is backend
    assert attempts == ["prewarm", "probe"]


@pytest.mark.parametrize(
    ("mode", "resource"),
    [
        ("rw", "microsoft.applicationId=app"),  # a developer seat / check gate
        ("rw", "farm.executionx=1,farm.execution.id=2"),  # exact key only
        ("rw", "farm.execution="),  # declared but empty
        ("ro", _LEAF_RESOURCE),  # an export-role helper: never publishes
        ("off", _LEAF_RESOURCE),
    ],
)
def test_prewarm_runs_only_in_a_publishing_farm_leaf(leaf, monkeypatch, mode, resource):
    """Every other graph load -- ``doit list``, ``check:*``, the submitter, tests
    that load dodo -- must stay off Azure."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", mode)
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", resource)
    monkeypatch.setattr(
        cache, "_make_backend", lambda: pytest.fail("a non-leaf process connected")
    )
    assert cache.prewarm() is None
    assert cache._PREWARMED is None
    assert leaf == []


def test_a_thread_that_cannot_start_is_no_prewarm(leaf, monkeypatch):
    """``Thread.start`` runs at dodo import: its RuntimeError must not abort doit,
    and must not leave the first probe waiting on a warm-up that never began."""
    import threading

    def refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", refuse)
    monkeypatch.setattr(cache, "_PREWARM_WAIT_S", 30)
    assert cache.prewarm() is None
    assert cache._PREWARMED.is_set()
    assert leaf == []


@pytest.fixture
def exported_cache_spans(monkeypatch):
    """Real SDK + in-memory exporter, not a mocked telemetry event echo."""
    from opentelemetry.sdk.trace import SpanLimits, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    providers = []

    def make(**limits):
        if "max_attribute_length" in limits:
            monkeypatch.setenv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT", str(limits["max_attribute_length"]))
        exporter = InMemorySpanExporter()
        provider = TracerProvider(
            span_limits=SpanLimits(**limits), shutdown_on_exit=False
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        providers.append(provider)
        tracer = provider.get_tracer("cache-test")
        monkeypatch.setattr(_telemetry, "get_tracer", lambda **kwargs: tracer)
        log_exporter = InMemoryLogRecordExporter()
        log_provider = LoggerProvider(
            resource=Resource.create({"service.name": _telemetry.BUILD_INFRA_SERVICE}),
            shutdown_on_exit=False,
        )
        log_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
        providers.append(log_provider)
        logger = logging.Logger("cache-test", level=logging.DEBUG)
        logger.addHandler(_telemetry._ResourceRoutedLoggingHandler(logger_provider=log_provider))
        monkeypatch.setattr(_telemetry, "get_logger", lambda: logger)
        monkeypatch.setattr(_telemetry, "_logger_provider_for_service", lambda service: log_provider)
        exporter.cache_logs = log_exporter
        return tracer, exporter

    yield make
    for provider in providers:
        provider.shutdown()


def _wire_events(exporter):
    """Read consumer-visible attributes after actual OTLP protobuf roundtrip."""
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.exporter.otlp.proto.common._log_encoder import encode_logs

    request = encode_spans(exporter.get_finished_spans())
    received = type(request).FromString(request.SerializeToString())
    events = [
        (event.name, {
            item.key: getattr(item.value, item.value.WhichOneof("value"))
            for item in event.attributes
        })
        for resource in received.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
        for event in span.events
    ]
    request = encode_logs(exporter.cache_logs.get_finished_logs())
    received = type(request).FromString(request.SerializeToString())
    events.extend(
        (record.body.string_value, {
            item.key: getattr(item.value, item.value.WhichOneof("value"))
            for item in record.attributes
        })
        for resource in received.resource_logs
        for scope in resource.scope_logs
        for record in scope.log_records
    )
    return events


def _received_recipe(events, outcome):
    """Independent consumer: fail closed on omission, truncation or unknown recipe."""
    decisions = [attrs for name, attrs in events if name == outcome]
    if len(decisions) != 1:
        return None
    decision = decisions[0]
    required = {
        "manifest_id", "manifest_schema", "manifest_chars", "manifest_chunk_count",
        "manifest_emitted_chunks", "manifest_input_count", "manifest_complete",
        "manifest_transport", "key_full",
    }
    if not required <= decision.keys() or decision["manifest_complete"] is not True:
        return None
    if decision["manifest_transport"] != "logs":
        return None
    if not isinstance(decision["manifest_id"], str) or len(decision["manifest_id"]) != 64:
        return None
    if not isinstance(decision["key_full"], str):
        return None
    for field in ("manifest_schema", "manifest_chars", "manifest_chunk_count",
                  "manifest_emitted_chunks", "manifest_input_count"):
        if type(decision[field]) is not int or decision[field] < 0:
            return None
    count = decision["manifest_chunk_count"]
    if count == 0 or decision["manifest_emitted_chunks"] != count:
        return None
    chunks = {}
    for name, attrs in events:
        if name == "cache.provenance" and attrs.get("manifest_id") == decision["manifest_id"]:
            if not {"chunk_index", "chunk"} <= attrs.keys():
                return None
            index, fragment = attrs["chunk_index"], attrs["chunk"]
            if type(index) is not int or not 0 <= index < count or not isinstance(fragment, str):
                return None
            if index in chunks and chunks[index] != fragment:
                return None
            chunks[index] = fragment
    if set(chunks) != set(range(count)) or decision["manifest_emitted_chunks"] != count:
        return None
    payload = "".join(chunks[index] for index in range(count))
    if len(payload) != decision["manifest_chars"]:
        return None
    try:
        if hashlib.sha256(payload.encode("ascii")).hexdigest() != decision["manifest_id"]:
            return None
        recipe = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        return None
    fields = {"schema", "key", "epoch", "salt", "recipe_known", "input_count", "inputs"}
    if not isinstance(recipe, dict) or not fields <= recipe.keys():
        return None
    if recipe["recipe_known"] is not True or not isinstance(recipe["inputs"], list):
        return None
    if recipe["schema"] != decision["manifest_schema"] or recipe["key"] != decision["key_full"]:
        return None
    if type(recipe["input_count"]) is not int:
        return None
    if len(recipe["inputs"]) != recipe["input_count"] or recipe["input_count"] != decision["manifest_input_count"]:
        return None
    if not isinstance(recipe["epoch"], str) or not isinstance(recipe["salt"], str):
        return None
    for item in recipe["inputs"]:
        if not isinstance(item, dict) or not {"path", "digest"} <= item.keys():
            return None
        if not isinstance(item["path"], str) or not isinstance(item["digest"], str):
            return None
    return recipe


@pytest.mark.parametrize("outcome", ["cache.miss", "cache.store", "cache.hit"])
def test_remote_recipe_survives_disposable_seat_without_sidecars(
    tmp_path, fake, monkeypatch, exported_cache_spans, outcome
):
    dep = _make_dep(tmp_path, "entrée.py", "source digest")
    monkeypatch.setenv("HARMONIC_CACHE_SALT", "salt-at-key-time")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    # Salt is recipe provenance, not the later environment at restore/store time.
    monkeypatch.setenv("HARMONIC_CACHE_SALT", "later-salt")
    out = tmp_path / "out.bin"
    out.write_bytes(b"payload")
    if outcome == "cache.hit":
        fake.blobs[key] = b"built-on-another-seat"
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("disposable-build"):
        if outcome == "cache.store":
            assert cache.store(key, [out], "part:x") == "stored"
        else:
            assert cache.restore(key, [out], "part:x") is (outcome == "cache.hit")

    events = _wire_events(exporter)
    recipe = _received_recipe(events, outcome)
    assert recipe == {
        "schema": 1, "key": key, "epoch": cache._CACHE_EPOCH,
        "salt": "salt-at-key-time", "recipe_known": True, "input_count": 1,
        "inputs": [{"path": "entrée.py", "digest": "source digest"}],
    }
    decision = next(attrs for name, attrs in events if name == outcome)
    assert decision["key"] == key[:12] and decision["key_full"] == key
    local = _events(tmp_path)[-1]
    assert {field: local[field] for field in recipe} == recipe
    assert local["manifest_id"] == decision["manifest_id"]
    # An independent re-derivation from the wire recipe verifies actual full key.
    h = hashlib.sha256()
    h.update(f"epoch={recipe['epoch']}\0salt={recipe['salt']}\0".encode())
    for item in recipe["inputs"]:
        h.update(f"{item['path']}\0{item['digest']}\0".encode())
    assert h.hexdigest() == recipe["key"]


@pytest.mark.parametrize("payload_chars", [5999, 6000, 6001, 12000, 12001])
def test_remote_manifest_exact_chunk_boundaries(
    tmp_path, fake, monkeypatch, exported_cache_spans, payload_chars
):
    # An empty dependency set is known, unlike an arbitrary key with no recipe.
    expected = {
        "schema": 1, "key": "0" * 64, "epoch": cache._CACHE_EPOCH, "salt": "",
        "recipe_known": True, "input_count": 0, "inputs": [],
    }
    overhead = len(json.dumps(expected, sort_keys=True, separators=(",", ":")))
    salt = "s" * (payload_chars - overhead)
    monkeypatch.setenv("HARMONIC_CACHE_SALT", salt)
    key = cache.cache_key([], _digest_one, label="part:boundary")
    expected.update(key=key, salt=salt)
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("boundary"):
        assert cache.restore(key, [], "part:boundary") is False
    events = _wire_events(exporter)
    assert _received_recipe(events, "cache.miss") == expected
    chunks = [attrs for name, attrs in events if name == "cache.provenance"]
    assert len(chunks) == (payload_chars + 5999) // 6000
    assert sum(len(attrs["chunk"]) for attrs in chunks) == payload_chars
    assert all(len(attrs["chunk"].encode("ascii")) <= 6000 for attrs in chunks)
    assert len(exporter.get_finished_spans()) == 3  # task, download, record; no dep spans


def test_remote_manifest_many_inputs_roundtrip(
    tmp_path, fake, exported_cache_spans
):
    deps = [
        _make_dep(tmp_path, f"recipe-{index:04d}.py", hashlib.md5(str(index).encode()).hexdigest())
        for index in range(250)
    ]
    key = cache.cache_key(deps, _digest_one, label="assembly:many")
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("many"):
        assert cache.restore(key, [], "assembly:many") is False
    events = _wire_events(exporter)
    recipe = _received_recipe(events, "cache.miss")
    assert recipe["input_count"] == 250
    assert recipe["inputs"] == _events(tmp_path)[-1]["inputs"]
    assert 1 < sum(name == "cache.provenance" for name, _ in events) < 32


@pytest.mark.parametrize("limits", [
    {"max_attribute_length": 64},
    {"max_event_attributes": 2},
])
def test_sdk_truncation_or_event_loss_cannot_appear_complete(
    tmp_path, fake, exported_cache_spans, limits
):
    dep = _make_dep(tmp_path, "long.py", "d" * 7000)
    key = cache.cache_key([dep], _digest_one, label="part:loss")
    tracer, exporter = exported_cache_spans(**limits)
    with tracer.start_as_current_span("limited"):
        assert cache.restore(key, [], "part:loss") is False
    assert _received_recipe(_wire_events(exporter), "cache.miss") is None


def test_unknown_recipe_is_explicitly_incomplete(tmp_path, fake, exported_cache_spans):
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("unknown"):
        assert cache.restore("a" * 64, [], "part:unknown") is False
    events = _wire_events(exporter)
    decision = next(attrs for name, attrs in events if name == "cache.miss")
    assert decision["manifest_input_count"] == -1
    assert decision["manifest_complete"] is False
    assert _received_recipe(events, "cache.miss") is None
    assert _events(tmp_path)[-1]["recipe_known"] is False


def test_large_manifest_emits_every_input_without_span_event_flood(
    tmp_path, fake, exported_cache_spans
):
    dep = _make_dep(tmp_path, "huge.py", "d" * (6000 * 32))
    key = cache.cache_key([dep], _digest_one, label="part:huge")
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("huge"):
        assert cache.restore(key, [], "part:huge") is False
    events = _wire_events(exporter)
    decision = next(attrs for name, attrs in events if name == "cache.miss")
    assert decision["manifest_chunk_count"] == 33
    assert decision["manifest_emitted_chunks"] == 33
    assert decision["manifest_complete"] is True
    assert decision["manifest_transport"] == "logs"
    assert sum(name == "cache.provenance" for name, _ in events) == 33
    assert _received_recipe(events, "cache.miss")["inputs"][0]["digest"] == "d" * (6000 * 32)
    assert not any(
        event.name == "cache.provenance"
        for span in exporter.get_finished_spans() for event in span.events
    )
    assert _events(tmp_path)[-1]["inputs"][0]["digest"] == "d" * (6000 * 32)


@pytest.mark.parametrize("failure_at", ["outcome", "chunk", "logging"])
def test_telemetry_sink_failure_preserves_successful_cache_behavior(
    tmp_path, fake, real_unpack, monkeypatch, exported_cache_spans, failure_at
):
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path)
    output_root = tmp_path / "cad" / "out"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(cache, "_unpack", real_unpack)
    dep = _make_dep(tmp_path, "input.py", "digest")
    key = cache.cache_key([dep], _digest_one, label="part:sink-failure")
    out = output_root / "out.bin"
    out.write_bytes(b"real packed payload")
    original_event = _telemetry.event
    original_debug = _telemetry.debug

    def event(name, **attributes):
        if failure_at == "outcome":
            raise RuntimeError("telemetry sink failed")
        original_event(name, **attributes)

    def debug(message, **attributes):
        if failure_at == "chunk" and message == "cache.provenance":
            raise RuntimeError("chunk sink failed")
        original_debug(message, **attributes)

    def broken_log(*args, **kwargs):
        raise RuntimeError("logging sink failed")

    monkeypatch.setattr(_telemetry, "event", event)
    monkeypatch.setattr(_telemetry, "debug", debug)
    if failure_at == "logging":
        for name in ("info", "debug", "warn"):
            monkeypatch.setattr(_telemetry, name, broken_log)
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("failing-sink"):
        assert cache.restore(key, [], "part:sink-failure") is False
        assert cache.store(key, [out], "part:sink-failure") == "stored"
        assert fake.blobs[key].startswith(b"\x1f\x8b")  # real gzip packing/upload
        assert cache.last_stored_key("part:sink-failure") == key
        out.unlink()
        assert cache.restore(key, [out], "part:sink-failure") is True
        assert out.read_bytes() == b"real packed payload"
    assert _received_recipe(_wire_events(exporter), "cache.store") is None
    assert [item["event"] for item in _events(tmp_path)] == [
        "restore_miss", "store", "restore_hit",
    ]


def test_manifest_logs_do_not_consume_span_event_budget(
    tmp_path, fake, exported_cache_spans
):
    dep = _make_dep(tmp_path, "many-fragments.py", "d" * 18000)
    key = cache.cache_key([dep], _digest_one, label="part:budget")
    tracer, exporter = exported_cache_spans(max_events=1)
    with tracer.start_as_current_span("single-event-budget") as task_span:
        assert cache.restore(key, [], "part:budget") is False
        trace_id = task_span.get_span_context().trace_id
        span_id = task_span.get_span_context().span_id
    events = _wire_events(exporter)
    assert _received_recipe(events, "cache.miss")["inputs"][0]["digest"] == "d" * 18000
    chunks = [
        record for record in exporter.cache_logs.get_finished_logs()
        if record.log_record.body == "cache.provenance"
    ]
    assert len(chunks) == 4
    assert all(record.log_record.trace_id == trace_id for record in chunks)
    assert all(record.log_record.span_id == span_id for record in chunks)
    assert all(
        record.resource.attributes["service.name"] == _telemetry.BUILD_INFRA_SERVICE
        for record in chunks
    )
    # Real exported evidence with one ingested fragment lost must fail closed.
    missing_one = []
    for name, attrs in events:
        if name == "cache.provenance" and attrs["chunk_index"] == 1:
            continue
        missing_one.append((name, attrs))
    assert _received_recipe(missing_one, "cache.miss") is None
    # An equal-length alteration is detected by checksum, not just counts.
    damaged = [
        (name, {**attrs, "chunk": "x" + attrs["chunk"][1:]})
        if name == "cache.provenance" and attrs["chunk_index"] == 1
        else (name, attrs)
        for name, attrs in events
    ]
    assert _received_recipe(damaged, "cache.miss") is None


@pytest.mark.parametrize("baseline", ["cache.store", "cache.hit"])
def test_remote_baseline_identifies_changed_dependency_across_disposable_seats(
    tmp_path, fake, monkeypatch, exported_cache_spans, baseline
):
    recipe_dep = _make_dep(tmp_path, "_stock_fastener.py", "old recipe digest")
    config_dep = _make_dep(tmp_path, "spring.yaml", "unchanged config digest")
    label = "part:sm_vn_counter_spring"
    old_key = cache.cache_key([recipe_dep, config_dep], _digest_one, label=label)
    out = tmp_path / "out.bin"
    out.write_bytes(b"payload")
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("previous-disposable-seat"):
        if baseline == "cache.store":
            assert cache.store(old_key, [out], label) == "stored"
        else:
            fake.blobs[old_key] = b"built-on-another-seat"
            assert cache.restore(old_key, [out], label) is True
    # New seat has neither process provenance nor the old local key sidecar.
    monkeypatch.setattr(cache, "_KEY_INPUTS", {})
    monkeypatch.setattr(cache, "_KEY_CONTEXT", {})
    monkeypatch.setattr(cache, "_KEY_MANIFESTS", {})
    monkeypatch.setattr(cache, "_KEYDIR", tmp_path / "new-seat" / "cache-keys")
    Path(recipe_dep).write_text("new recipe digest", encoding="utf-8")
    new_key = cache.cache_key([recipe_dep, config_dep], _digest_one, label=label)
    with tracer.start_as_current_span("current-disposable-seat"):
        assert cache.restore(new_key, [], label) is False
    assert cache.last_stored_key(label) is None
    evidence = _wire_events(exporter)
    previous = _received_recipe(evidence, baseline)
    current = _received_recipe(evidence, "cache.miss")
    assert previous["key"] == old_key and current["key"] == new_key
    assert previous["epoch"] == current["epoch"]
    assert previous["salt"] == current["salt"]
    old_inputs = {item["path"]: item["digest"] for item in previous["inputs"]}
    new_inputs = {item["path"]: item["digest"] for item in current["inputs"]}
    changed = {
        path for path in old_inputs.keys() | new_inputs.keys()
        if old_inputs.get(path) != new_inputs.get(path)
    }
    assert changed == {"_stock_fastener.py"}


def test_recipe_serialization_is_shared_without_suppressing_outcomes(
    tmp_path, fake, monkeypatch, exported_cache_spans
):
    dep = _make_dep(tmp_path, "input.py", "digest")
    key = cache.cache_key([dep], _digest_one, label="part:shared")
    out = tmp_path / "out.bin"
    out.write_bytes(b"payload")
    original = cache._manifest
    serialized = []

    def manifest(provenance):
        serialized.append(provenance["key"])
        return original(provenance)

    monkeypatch.setattr(cache, "_manifest", manifest)
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("shared-recipe"):
        assert cache.restore(key, [], "part:shared") is False
        assert cache.store(key, [out], "part:shared") == "stored"
        assert cache.restore(key, [out], "part:shared") is True
    assert serialized == [key]
    events = _wire_events(exporter)
    recipes = [
        _received_recipe(events, outcome)
        for outcome in ("cache.miss", "cache.store", "cache.hit")
    ]
    assert all(recipe == recipes[0] for recipe in recipes)
    assert recipes[0]["inputs"] == [{"path": "input.py", "digest": "digest"}]
    assert len(_events(tmp_path)) == 3
    # Recapturing provenance invalidates its private canonical snapshot.
    assert cache.cache_key([dep], _digest_one, label="part:shared") == key
    cache._record("restore_hit", "part:shared", key)
    assert serialized == [key, key]


def test_debug_provenance_uses_key_time_salt(tmp_path, fake, monkeypatch):
    dep = _make_dep(tmp_path, "input.py", "digest")
    monkeypatch.setenv("HARMONIC_CACHE_DEBUG", "1")
    salts = iter(["captured-salt"])
    monkeypatch.setattr(cache, "_salt", lambda: next(salts))
    records = []
    monkeypatch.setattr(_telemetry, "info", lambda message, **kwargs: records.append(message))
    key = cache.cache_key([dep], _digest_one, label="part:captured")
    assert cache._KEY_CONTEXT[("part:captured", key)] == (cache._CACHE_EPOCH, "captured-salt")
    assert any("salt=captured-salt" in record for record in records)




@pytest.mark.parametrize("raw", [
    "", "{not json", "null", "[]", "{}",
    '{"labels":"part:x","reason":"Audit"}',
    '{"labels":[],"reason":"Audit"}',
    '{"labels":["part:x",1],"reason":"Audit"}',
    '{"labels":["part:x"," "],"reason":"Audit"}',
    '{"labels":["part:x"]}',
    '{"labels":["part:x"],"reason":null}',
    '{"labels":["part:x"],"reason":" "}',
    '{"labels":["part:x"],"reason":"line\\nbreak"}',
])
def test_forced_refresh_rejects_malformed_carriers_loudly(monkeypatch, raw):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", raw)
    with pytest.raises(RuntimeError, match="HARMONIC_CACHE_REFRESH"):
        cache.forced_refresh("part:not-listed")


def test_forced_refresh_reads_current_environment_without_consuming_request(monkeypatch):
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
    assert cache.forced_refresh("part:x") is None
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    for reason in ("Audit one", "  Audit Ω 👩\u200d🔧  "):
        monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
            "labels": ["part:x"], "reason": reason,
        }))
        assert cache.forced_refresh("part:x") == reason
        assert cache.forced_refresh("part:not-listed") is None
        assert cache.forced_refresh("part:x") == reason


@pytest.mark.parametrize("mode", ["ro", "off"])
def test_forced_refresh_refuses_nonwritable_mode(monkeypatch, mode):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", mode)
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", '{"labels":["part:x"],"reason":"Audit"}')
    with pytest.raises(RuntimeError, match="requires HARMONIC_REMOTE_CACHE_MODE=rw"):
        cache.forced_refresh("part:x")


def test_refresh_diagnostics_carry_label_key_and_reason(
    fake, tmp_path, monkeypatch, caplog, capsys
):
    key = "a" * 64
    reason = "Owner - Re-evaluate unchanged inputs"
    events = []
    monkeypatch.setattr(
        _telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    logger = _telemetry_logger(caplog, monkeypatch)
    with caplog.at_level(logging.WARNING, logger=logger.name):
        cache.note_refresh("part:x", key, reason)
    warnings = _records(caplog, logger, logging.WARNING)
    assert any("part:x" in warning and key[:12] in warning and reason in warning
               for warning in warnings)
    assert "!!" in capsys.readouterr().err
    assert events == [("cache.refresh", {"label": "part:x", "key": key[:12], "reason": reason})]
    [record] = _events(tmp_path)
    assert (record["event"], record["label"], record["key"], record["reason"]) == (
        "refresh", "part:x", key, reason,
    )


def test_refresh_cas_replaces_the_same_key_and_requires_publication(fake, tmp_path, monkeypatch):
    key = "a" * 64
    output = tmp_path / "output.bin"
    output.write_bytes(b"replacement")
    fake.blobs[key] = b"old cached bytes"
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", '{"labels":["part:x"],"reason":"Audit"}')
    cache.capture_refresh("part:x", key)
    assert cache.store(key, [output], "part:x") == "stored"
    assert fake.blobs[key] != b"old cached bytes"
    assert cache.last_stored_key("part:x") == key

    def fail_upload(*_args, **_kwargs):
        raise OSError("upload denied")

    monkeypatch.setattr(fake, "put", fail_upload)
    with pytest.raises(RuntimeError, match="forced cache refresh did not store outputs \\(lost\\)"):
        cache.store(key, [output], "part:x")
    # An ordinary ambiguous publish with a canonical entry is a loss, not success.
    assert cache.store(key, [output], "part:ordinary") == "lost"
    # Absent-entry publication failures remain soft for ordinary leaves.
    assert cache.store("b" * 64, [output], "part:ordinary") == "error"


@pytest.mark.parametrize("large", [False, True], ids=["put-blob", "put-block-list"])
@pytest.mark.parametrize("refresh", [False, True], ids=["create", "cas"])
def test_blob_publication_conditions_and_atomic_metadata(monkeypatch, large, refresh):
    from azure.core import MatchConditions

    monkeypatch.setattr(cache, "_SINGLE_PUT_MAX", 8 if large else 1024)
    monkeypatch.setattr(cache, "_BLOCK_SIZE", 4)
    service = _BlockBlobService()
    backend = cache._BlobBackend(service)
    key, payload = "c" * 64, b"new native bytes"
    if refresh:
        _put_bytes(backend, key, b"old native bytes")
        before = backend.etag(key)
    else:
        before = None
    _put_bytes(backend, key, payload, replace_etag=before)
    name = backend._name(key)
    operation, written_name, condition, metadata = service.calls[-1]
    assert operation == ("commit" if large else "upload")
    assert written_name == name
    expected = {
        **({"etag": before} if refresh else {}),
        "match_condition": MatchConditions.IfNotModified if refresh else MatchConditions.IfMissing,
    }
    if not large:
        expected = {"overwrite": refresh, **(expected if refresh else {})}
    assert condition == expected
    assert metadata == service.metadata[name] == {
        "archive_sha256": hashlib.sha256(payload).hexdigest(),
        "archive_size": str(len(payload)), "epoch": "4",
    }
    assert _get_bytes(backend, key) == payload
    winner_etag = service.etags[name]
    with pytest.raises(RuntimeError, match="condition failed"):
        _put_bytes(backend, key, b"late writer bytes")
    assert _get_bytes(backend, key) == payload
    assert service.etags[name] == winner_etag


@pytest.mark.parametrize("field,value", [
    ("archive_sha256", "0" * 64), ("archive_size", "999"), ("epoch", "3"),
    ("archive_sha256", None),
])
def test_download_checks_response_metadata_before_unpack(monkeypatch, fake, field, value):
    service = _BlockBlobService()
    backend = cache._BlobBackend(service)
    key = "d" * 64
    _put_bytes(backend, key, b"archive")
    metadata = service.metadata[backend._name(key)]
    if value is None:
        metadata.pop(field)
    else:
        metadata[field] = value
    monkeypatch.setattr(cache, "_BACKEND", backend)
    monkeypatch.setattr(cache, "_unpack", lambda _blob, _outputs: pytest.fail("unpacked corrupt payload"))
    assert cache.restore(key, [], "part:x") is False
    assert not any(call[0] == "etag" for call in service.calls)


def test_download_uses_its_response_not_a_second_head():
    service = _BlockBlobService()
    backend = cache._BlobBackend(service)
    key = "e" * 64
    _put_bytes(backend, key, b"old response")
    client = service.get_blob_client(backend._name(key))
    original_download = client.download_blob

    def concurrent_refresh(**kwargs):
        response = original_download(**kwargs)
        _put_bytes(backend, key, b"new canonical", replace_etag=backend.etag(key))
        return response

    client.download_blob = concurrent_refresh
    original_client = service.get_blob_client
    service.get_blob_client = lambda _name: client
    try:
        assert _get_bytes(backend, key) == b"old response"
    finally:
        service.get_blob_client = original_client


@pytest.mark.parametrize("message", ["InvalidBlockList", "ambiguous timeout"])
@pytest.mark.parametrize("present", [False, True])
def test_every_failed_publish_classifies_canonical_presence(
    fake, tmp_path, monkeypatch, message, present
):
    key = "f" * 64
    output = tmp_path / "output.bin"
    output.write_bytes(b"loser")
    if present:
        fake.blobs[key] = b"winner"

    def fail(*_args, **_kwargs):
        raise OSError(message)

    monkeypatch.setattr(fake, "put", fail)
    assert cache.store(key, [output], "part:x") == ("lost" if present else "error")
    assert cache.last_stored_key("part:x") is None
    assert _events(tmp_path)[-1]["event"] == ("store_lost" if present else "store_error")
    if present:
        assert fake.blobs[key] == b"winner"


def test_failed_presence_check_is_an_ordinary_error(fake, tmp_path, monkeypatch):
    output = tmp_path / "output.bin"
    output.write_bytes(b"loser")

    def fail(*_args, **_kwargs):
        raise OSError("unreachable")

    monkeypatch.setattr(fake, "put", fail)
    monkeypatch.setattr(fake, "exists", fail)
    assert cache.store("f" * 64, [output], "part:x") == "error"


@pytest.mark.parametrize("initially_present", [False, True])
def test_refresh_never_recaptures_changed_or_absent_snapshot(
    fake, tmp_path, monkeypatch, initially_present
):
    key, label = "a" * 64, "part:x"
    output = tmp_path / "output.bin"
    output.write_bytes(b"refresh")
    if initially_present:
        _put_bytes(fake, key, b"original")
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": [label], "reason": "Owner - CAS snapshot",
    }))
    heads = []
    original_etag = fake.etag

    def etag(key):
        heads.append(key)
        return original_etag(key)

    monkeypatch.setattr(fake, "etag", etag)
    cache.note_refresh(label, key, "Owner - CAS snapshot")
    snapshot = cache._REFRESH_ETAGS[(label, key)]
    fake.blobs[key] = b"concurrent winner"
    cache.note_refresh(label, key, "Owner - CAS snapshot")
    assert heads == [key]
    assert cache._REFRESH_ETAGS[(label, key)] == snapshot
    with pytest.raises(RuntimeError, match="did not store outputs \\(lost\\)"):
        cache.store(key, [output], label)
    assert fake.blobs[key] == b"concurrent winner"


def test_ambiguous_own_commit_is_lost_without_a_published_key_sidecar(
    fake, tmp_path, monkeypatch
):
    key = "a" * 64
    output = tmp_path / "output.bin"
    output.write_bytes(b"server accepted these bytes")
    put = fake.put

    def commit_then_timeout(key, blob, *, replace_etag=None):
        put(key, blob, replace_etag=replace_etag)
        raise TimeoutError("reply lost after commit")

    monkeypatch.setattr(fake, "put", commit_then_timeout)
    assert cache.store(key, [output], "part:x") == "lost"
    assert fake.blobs[key].startswith(b"\x1f\x8b")
    assert cache.last_stored_key("part:x") is None
    assert _events(tmp_path)[-1]["event"] == "store_lost"


def test_refresh_requires_an_early_probe_not_a_preupload_head(fake, tmp_path, monkeypatch):
    output = tmp_path / "output.bin"
    output.write_bytes(b"refresh")
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", '{"labels":["part:x"],"reason":"Audit"}')
    monkeypatch.setattr(fake, "etag", lambda _key: pytest.fail("late refresh snapshot"))
    with pytest.raises(RuntimeError, match="not probed before work"):
        cache.store("a" * 64, [output], "part:x")


@pytest.fixture
def sdk_wire():
    """Real SDK -> RequestsTransport -> Session.request -> socket-free adapter."""
    import base64
    import io
    from urllib.parse import parse_qs, urlsplit
    import requests
    from azure.core.pipeline.transport import RequestsTransport
    from azure.storage.blob import ContainerClient

    class Adapter(requests.adapters.BaseAdapter):
        def __init__(self):
            self.requests = []
            self.status = 201
            self.payload = None
            self.range_active = 0
            self.range_peak = 0
            self.range_lock = threading.Lock()

        def send(self, request, **kwargs):
            self.requests.append(request)
            query = parse_qs(urlsplit(request.url).query)
            staged = query.get("comp") == ["block"]
            code = 200 if request.method == "HEAD" else 201 if staged else self.status
            body = b""
            download = request.method == "GET" and self.payload is not None
            if download:
                raw_range = request.headers.get("x-ms-range") or request.headers["Range"]
                start, end = (int(value) for value in raw_range.removeprefix("bytes=").split("-"))
                end = min(end, len(self.payload) - 1)
                body = self.payload[start:end + 1]
                code = 206
                with self.range_lock:
                    self.range_active += 1
                    self.range_peak = max(self.range_peak, self.range_active)
                # Let the actual SDK's range workers overlap at the transport.
                time.sleep(0.01)
                with self.range_lock:
                    self.range_active -= 1
            response = requests.Response()
            response.status_code = code
            response.reason = {
                200: "OK", 201: "Created", 206: "Partial Content",
                409: "Conflict", 412: "Precondition Failed",
            }[code]
            response.url = request.url
            response.request = request
            response.headers = requests.structures.CaseInsensitiveDict({
                "ETag": '"snapshot-etag"',
                "Last-Modified": "Mon, 19 Oct 2026 00:00:00 GMT",
                "x-ms-request-id": "offline-contract",
                "x-ms-version": "2025-11-05",
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": "application/xml",
                "Content-Length": "0",
            })
            if download:
                response.headers.update({
                    "Content-Range": f"bytes {start}-{end}/{len(self.payload)}",
                    "Content-Length": str(len(body)),
                    "Content-Type": "application/octet-stream",
                    "x-ms-meta-archive_sha256": hashlib.sha256(self.payload).hexdigest(),
                    "x-ms-meta-archive_size": str(len(self.payload)),
                    "x-ms-meta-epoch": cache._CACHE_EPOCH,
                })
            if code in (409, 412):
                error = "BlobAlreadyExists" if code == 409 else "ConditionNotMet"
                response.headers["x-ms-error-code"] = error
                body = f"<Error><Code>{error}</Code><Message>Conflict</Message></Error>".encode()
                response.headers["Content-Length"] = str(len(body))
            response._content = body
            response._content_consumed = True
            response.raw = io.BytesIO(body)
            return response

        def close(self):
            pass

    adapter = Adapter()
    with requests.Session() as session:
        session.trust_env = False
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        transport = RequestsTransport(session=session, session_owner=False)
        with ContainerClient(
            account_url="https://offline.blob.core.windows.net", container_name="cache",
            credential={
                "account_name": "offline",
                "account_key": base64.b64encode(b"offline-test-key-no-credentials").decode(),
            },
            transport=transport, retry_total=0, max_single_get_size=cache._ARCHIVE_CACHE_MIN,
        ) as container:
            yield types.SimpleNamespace(
                container=container, backend=cache._BlobBackend(container), adapter=adapter,
            )


@pytest.mark.parametrize("large", [False, True], ids=["put-blob", "put-block-list"])
@pytest.mark.parametrize("refresh", [False, True], ids=["if-missing", "if-match"])
@pytest.mark.parametrize("status", [201, 409, 412], ids=["created", "exists", "precondition"])
def test_real_azure_sdk_emits_wire_conditions_and_metadata(
    monkeypatch, sdk_wire, large, refresh, status
):
    """The adapter sits BELOW real Session.request, which rejects leaked kwargs."""
    from urllib.parse import parse_qs, urlsplit
    from azure.core.exceptions import HttpResponseError

    backend, adapter = sdk_wire.backend, sdk_wire.adapter
    adapter.status = status
    monkeypatch.setattr(cache, "_SINGLE_PUT_MAX", 8 if large else 1024)
    monkeypatch.setattr(cache, "_BLOCK_SIZE", 4)
    monkeypatch.setattr(cache, "_TRANSFER_CONCURRENCY", 1)
    payload, key = b"native publication archive", "c" * 64
    snapshot = backend.etag(key) if refresh else None
    if status != 201:
        with pytest.raises(HttpResponseError):
            _put_bytes(backend, key, payload, replace_etag=snapshot)
    else:
        _put_bytes(backend, key, payload, replace_etag=snapshot)
    writes = [
        request for request in adapter.requests
        if request.method == "PUT"
        and parse_qs(urlsplit(request.url).query).get("comp") != ["block"]
    ]
    assert len(writes) == 1
    request = writes[0]
    query = parse_qs(urlsplit(request.url).query)
    assert query.get("comp") == (["blocklist"] if large else None)
    if refresh:
        assert snapshot == '"snapshot-etag"'
        assert request.headers["If-Match"] == snapshot
        assert "If-None-Match" not in request.headers
    else:
        assert request.headers["If-None-Match"] == "*"
        assert "If-Match" not in request.headers
    assert request.headers["x-ms-meta-archive_sha256"] == hashlib.sha256(payload).hexdigest()
    assert request.headers["x-ms-meta-archive_size"] == str(len(payload))
    assert request.headers["x-ms-meta-epoch"] == "4"
    assert request.headers["Authorization"].startswith("SharedKey offline:")
    staged = [
        request for request in adapter.requests
        if parse_qs(urlsplit(request.url).query).get("comp") == ["block"]
    ]
    assert bool(staged) == large
    assert all("x-ms-meta-archive_sha256" not in request.headers for request in staged)


def test_real_sdk_rejects_pre_fix_wildcard_etag_before_adapter(sdk_wire):
    """Negative control for B1: the old kwargs fail below the real SDK pipeline."""
    from azure.core import MatchConditions
    from azure.storage.blob import BlobBlock

    client = sdk_wire.container.get_blob_client("negative-control.tar.gz")
    with pytest.raises(TypeError, match="unexpected keyword argument 'etag'"):
        client.commit_block_list(
            [BlobBlock(block_id="offline-block")],
            etag="*", match_condition=MatchConditions.IfMissing,
        )
    assert sdk_wire.adapter.requests == []


@pytest.fixture
def archive_store(monkeypatch):
    monkeypatch.setattr(cache, "_ARCHIVE_CACHE_MIN", 16)
    root = cache._archive_cache_root()
    service = _BlockBlobService()
    return types.SimpleNamespace(root=root, service=service, backend=cache._BlobBackend(service))


def test_large_local_reuse_validates_current_response_without_remaining_body(archive_store):
    root, service, backend = archive_store.root, archive_store.service, archive_store.backend
    key, payload = "a" * 64, b"canonical native archive" * 8
    _put_bytes(backend, key, payload)
    assert _get_bytes(backend, key) == payload
    assert _get_bytes(backend, key) == payload
    assert [call[0] for call in service.calls].count("download") == 2
    assert [call[0] for call in service.calls].count("readinto") == 1
    assert not any(call[0] == "etag" for call in service.calls)
    assert (root / "objects" / hashlib.sha256(payload).hexdigest()).read_bytes() == payload
    assert list((root / "objects").iterdir()) == [
        root / "objects" / hashlib.sha256(payload).hexdigest()
    ]


def test_refresh_same_recipe_uses_new_response_identity_not_previous_local_bytes(archive_store):
    backend, service = archive_store.backend, archive_store.service
    key = "b" * 64
    _put_bytes(backend, key, b"old native archive" * 8)
    assert _get_bytes(backend, key) == b"old native archive" * 8
    _put_bytes(backend, key, b"NEW native archive" * 8, replace_etag=backend.etag(key))
    assert _get_bytes(backend, key) == b"NEW native archive" * 8
    assert [call[0] for call in service.calls].count("readinto") == 2


def test_shared_object_is_rehashed_and_corruption_is_downloaded_again(archive_store):
    backend, root = archive_store.backend, archive_store.root
    key, payload = "c" * 64, b"native archive" * 8
    _put_bytes(backend, key, payload)
    assert _get_bytes(backend, key) == payload
    path = root / "objects" / hashlib.sha256(payload).hexdigest()
    path.write_bytes(b"x" * len(payload))  # same length is not integrity
    assert _get_bytes(backend, key) == payload
    assert path.read_bytes() == payload
    assert [call[0] for call in archive_store.service.calls].count("readinto") == 2


def test_local_return_is_a_private_snapshot_not_a_reopened_shared_path(archive_store):
    backend, root = archive_store.backend, archive_store.root
    key, payload = "d" * 64, b"native identity" * 8
    _put_bytes(backend, key, payload)
    assert _get_bytes(backend, key) == payload
    with backend.get(key) as private:
        path = root / "objects" / hashlib.sha256(payload).hexdigest()
        path.write_bytes(b"x" * len(payload))
        assert private.read() == payload
    assert _get_bytes(backend, key) == payload  # next caller detects corruption


def test_interrupted_download_never_publishes_a_local_object(archive_store, monkeypatch):
    backend, service, root = archive_store.backend, archive_store.service, archive_store.root
    key, payload = "e" * 64, b"native archive" * 8
    _put_bytes(backend, key, payload)
    client = service.get_blob_client(backend._name(key))
    original = client.download_blob
    files = []
    temporary = cache.tempfile.TemporaryFile

    def tracked_file(*args, **kwargs):
        file = temporary(*args, **kwargs)
        files.append(file)
        return file

    def interrupted(**kwargs):
        response = original(**kwargs)

        def readinto(stream):
            stream.write(payload[:10])
            raise OSError("interrupted")

        response.readinto = readinto
        return response

    monkeypatch.setattr(cache.tempfile, "TemporaryFile", tracked_file)
    monkeypatch.setattr(client, "download_blob", interrupted)
    monkeypatch.setattr(service, "get_blob_client", lambda _name: client)
    with pytest.raises(OSError, match="interrupted"):
        backend.get(key)
    assert files and all(file.closed for file in files)
    assert not list((root / "objects").iterdir())


@pytest.mark.parametrize("error", ["missing", "auth", "precondition"])
def test_download_azure_errors_are_not_silently_changed(archive_store, monkeypatch, error):
    from azure.core.exceptions import (
        ClientAuthenticationError, ResourceModifiedError, ResourceNotFoundError,
    )

    backend, service = archive_store.backend, archive_store.service
    client = service.get_blob_client("unused")
    failure = {
        "missing": ResourceNotFoundError("missing"),
        "auth": ClientAuthenticationError("denied"),
        "precondition": ResourceModifiedError("changed"),
    }[error]

    def fail(**_kwargs):
        raise failure

    monkeypatch.setattr(client, "download_blob", fail)
    monkeypatch.setattr(service, "get_blob_client", lambda _name: client)
    if error == "missing":
        assert backend.get("a" * 64) is None
    else:
        with pytest.raises(type(failure)):
            backend.get("a" * 64)


def test_concurrent_local_publications_use_unique_temps_and_converge(
    archive_store, monkeypatch
):
    backend, root = archive_store.backend, archive_store.root
    key, payload = "f" * 64, b"same canonical archive" * 8
    _put_bytes(backend, key, payload)
    barrier = threading.Barrier(2)
    lookup = cache._local_archive
    replace = cache.os.replace
    publications = []

    def simultaneous(*args):
        result = lookup(*args)
        assert result is None
        barrier.wait(timeout=10)
        return result

    def record_replace(source, destination):
        publications.append(Path(source))
        return replace(source, destination)

    monkeypatch.setattr(cache, "_local_archive", simultaneous)
    monkeypatch.setattr(cache.os, "replace", record_replace)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _index: _get_bytes(backend, key), range(2)))
    assert results == [payload, payload]
    assert len(publications) == len(set(publications)) == 2
    [path] = (root / "objects").iterdir()
    assert path.name == hashlib.sha256(payload).hexdigest()
    assert path.read_bytes() == payload


def test_scoped_lru_skips_leases_and_never_deletes_unknown_or_outside_files(
    archive_store, tmp_path, monkeypatch
):
    root = archive_store.root
    monkeypatch.setattr(cache, "_ARCHIVE_CACHE_CAP", 64)
    paths = []
    for index, payload in enumerate((b"A" * 32, b"B" * 32)):
        digest = hashlib.sha256(payload).hexdigest()
        cache._save_archive(root, digest, len(payload), io.BytesIO(payload))
        path = root / "objects" / digest
        os.utime(path, (index + 1, index + 1))
        paths.append(path)
    unrelated = root / "objects" / "keep-me"
    outside = tmp_path / "native.SLDPRT"
    unrelated.write_bytes(b"not an archive object")
    outside.write_bytes(b"native")
    orphan = root / "objects" / f".{'0' * 64}.{'1' * 32}.tmp"
    orphan.write_bytes(b"interrupted local publication")
    with cache._archive_lock(root / "locks" / paths[0].name):
        payload = b"C" * 32
        digest = hashlib.sha256(payload).hexdigest()
        cache._save_archive(root, digest, len(payload), io.BytesIO(payload))
        assert paths[0].exists()
        assert not paths[1].exists()
        assert (root / "objects" / digest).exists()
    assert not orphan.exists()
    assert unrelated.read_bytes() == b"not an archive object"
    assert outside.read_bytes() == b"native"


def test_local_reuse_updates_explicit_lru_time(archive_store):
    backend, root = archive_store.backend, archive_store.root
    key, payload = "a" * 64, b"native archive" * 8
    _put_bytes(backend, key, payload)
    assert _get_bytes(backend, key) == payload
    path = root / "objects" / hashlib.sha256(payload).hexdigest()
    os.utime(path, (1, 1))
    assert _get_bytes(backend, key) == payload
    assert path.stat().st_mtime > 1


def test_object_lease_is_cross_process_and_released_on_process_exit(archive_store):
    lock = archive_store.root / "locks" / ("a" * 64)
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import _artifact_cache as c; "
        "from pathlib import Path; "
        "lease = c._archive_lock(Path(sys.argv[2]), blocking=False); "
        "print(lease.__enter__(), flush=True)"
    )

    def child():
        return subprocess.run(
            [sys.executable, "-c", code, str(Path(cache.__file__).parent), str(lock)],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()

    with cache._archive_lock(lock):
        assert child() == "False"
    # The child's intentionally unclosed lease is also released by OS teardown.
    assert child() == "True"
    with cache._archive_lock(lock, blocking=False) as acquired:
        assert acquired


@pytest.mark.parametrize("root_kind", ["arbitrary", "relative", "inside-repo"])
def test_cache_root_rejects_unapproved_or_workspace_paths(
    tmp_path, monkeypatch, root_kind
):
    root = cache._archive_cache_roots()[0]
    if root_kind == "arbitrary":
        monkeypatch.setenv("HARMONIC_ARCHIVE_CACHE_ROOT", str(tmp_path / "other"))
    elif root_kind == "relative":
        monkeypatch.setenv("HARMONIC_ARCHIVE_CACHE_ROOT", "relative/archive-cache")
    else:
        monkeypatch.setattr(cache, "REPO_ROOT", root.parent)
    with pytest.raises(RuntimeError, match="(unapproved|unsafe) local archive cache"):
        cache._archive_cache_root()


def test_cache_root_absence_disables_local_reuse(monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert cache._archive_cache_root() is None


def test_local_cache_rejects_aliases_without_touching_their_target(
    archive_store, tmp_path
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"unrelated")
    objects = archive_store.root / "objects"
    objects.rmdir()
    try:
        objects.symlink_to(outside, target_is_directory=True)
    except OSError:
        objects.mkdir()
        pytest.skip("symlink creation requires privilege")
    try:
        with pytest.raises(RuntimeError, match="unsafe local archive cache"):
            cache._archive_cache_root()
        assert (outside / "keep").read_bytes() == b"unrelated"
    finally:
        objects.unlink()


def test_real_sdk_parallel_readinto_and_bounded_prefix_local_hit(sdk_wire):
    """Actual locked SDK ranged downloader, not a mocked readinto echo."""
    backend, adapter = sdk_wire.backend, sdk_wire.adapter
    adapter.payload = b"canonical native bytes-" * (1024 * 1024)
    key = "e" * 64
    assert _get_bytes(backend, key) == adapter.payload
    first = list(adapter.requests)
    assert len(first) > 2
    assert adapter.range_peak > 1
    assert adapter.range_peak <= cache._TRANSFER_CONCURRENCY
    assert all(request.method == "GET" for request in first)
    assert "If-Match" not in first[0].headers
    assert all(request.headers["If-Match"] == '"snapshot-etag"' for request in first[1:])
    adapter.requests.clear()
    assert _get_bytes(backend, key) == adapter.payload
    [probe] = adapter.requests
    assert probe.method == "GET"
    raw_range = probe.headers.get("x-ms-range") or probe.headers["Range"]
    assert raw_range == f"bytes=0-{cache._ARCHIVE_CACHE_MIN - 1}"


def test_large_file_upload_reads_only_bounded_blocks(archive_store, monkeypatch):
    backend = archive_store.backend
    monkeypatch.setattr(cache, "_SINGLE_PUT_MAX", 8)
    monkeypatch.setattr(cache, "_BLOCK_SIZE", 4)

    class BoundedFile(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= cache._BLOCK_SIZE
            return super().read(size)

    payload = b"large result transfer" * 16
    with BoundedFile(payload) as archive:
        backend.put("a" * 64, archive)
    assert archive_store.service.content(backend._name("a" * 64)) == payload


def test_local_hydration_keeps_provenance_sidecars_and_share_lock_contract(
    archive_tree, fake, real_unpack, archive_store, monkeypatch, tmp_path
):
    backend = archive_store.backend
    native = archive_tree / "leaf.SLDPRT"
    optional = archive_tree / "optional.json"
    native.write_bytes(b"canonical")
    key = "b" * 64
    _put_bytes(backend, key, _packed([native]))
    monkeypatch.setattr(cache, "_BACKEND", backend)
    monkeypatch.setattr(cache, "_unpack", real_unpack)
    assert cache.restore(key, [native, optional], "part:leaf")
    optional.write_bytes(b"loser-only")
    native.write_bytes(b"loser")
    assert cache.restore(key, [native, optional], "part:leaf")
    assert native.read_bytes() == b"canonical"
    assert not optional.exists()
    assert cache.last_stored_key("part:leaf") is None
    assert _events(tmp_path)[-1]["event"] == "restore_hit"
    assert [call[0] for call in archive_store.service.calls].count("readinto") == 1

    def locked(_blob, _outputs):
        raise PermissionError(13, "share-locked", str(native))

    monkeypatch.setattr(cache, "_unpack", locked)
    with pytest.raises(cache.RestoreLocked):
        cache.restore(key, [native, optional], "part:leaf")


def test_local_store_io_failure_does_not_consume_the_verified_download(
    archive_store, monkeypatch
):
    backend = archive_store.backend
    key, payload = "d" * 64, b"verified result archive" * 8
    _put_bytes(backend, key, payload)

    def full_disk(_root, _digest, _size, archive):
        archive.read(10)
        raise OSError("disk full")

    monkeypatch.setattr(cache, "_save_archive", full_disk)
    assert _get_bytes(backend, key) == payload


@pytest.mark.parametrize("field,value", [("etag", ""), ("size", 1), ("size", True)])
def test_response_identity_requires_real_length_and_etag(
    archive_store, monkeypatch, field, value
):
    backend, service = archive_store.backend, archive_store.service
    key, payload = "e" * 64, b"canonical archive" * 8
    _put_bytes(backend, key, payload)
    client = service.get_blob_client(backend._name(key))
    original = client.download_blob

    def damaged(**kwargs):
        response = original(**kwargs)
        setattr(response.properties, field, value)
        return response

    monkeypatch.setattr(client, "download_blob", damaged)
    monkeypatch.setattr(service, "get_blob_client", lambda _name: client)
    with pytest.raises(RuntimeError, match="integrity mismatch"):
        backend.get(key)
    assert not any(call[0] == "readinto" for call in service.calls)


def test_capacity_admission_skips_persistence_instead_of_evicting_live_objects(
    archive_store, monkeypatch
):
    root = archive_store.root
    monkeypatch.setattr(cache, "_ARCHIVE_CACHE_CAP", 32)
    first = b"A" * 32
    digest = hashlib.sha256(first).hexdigest()
    cache._save_archive(root, digest, len(first), io.BytesIO(first))
    with cache._archive_lock(root / "locks" / digest):
        second = b"B" * 32
        other = hashlib.sha256(second).hexdigest()
        cache._save_archive(root, other, len(second), io.BytesIO(second))
        assert (root / "objects" / digest).read_bytes() == first
        assert not (root / "objects" / other).exists()
        assert sum(path.stat().st_size for path in (root / "objects").iterdir()) == 32
    assert not list((root / "objects").glob(".*.tmp"))


def test_archive_larger_than_store_cap_is_served_without_persisting(
    archive_store, monkeypatch
):
    backend, root = archive_store.backend, archive_store.root
    monkeypatch.setattr(cache, "_ARCHIVE_CACHE_CAP", 32)
    payload = b"large canonical native archive" * 8
    _put_bytes(backend, "a" * 64, payload)
    assert _get_bytes(backend, "a" * 64) == payload
    assert not list((root / "objects").iterdir())


def test_small_actual_sdk_download_is_one_request_without_local_store(
    sdk_wire, monkeypatch
):
    sdk_wire.adapter.payload = b"small gate stamp"
    monkeypatch.setattr(
        cache, "_archive_cache_root", lambda: pytest.fail("small archive touched local store"),
    )
    assert _get_bytes(sdk_wire.backend, "a" * 64) == b"small gate stamp"
    [request] = sdk_wire.adapter.requests
    assert request.method == "GET"


def test_pack_and_unpack_use_an_owned_seekable_disk_file(archive_tree):
    native = archive_tree / "leaf.SLDPRT"
    native.write_bytes(b"canonical native")
    with cache._pack([native]) as archive:
        assert archive.fileno() >= 0
        assert archive.seekable()
        assert archive.read(2) == b"\x1f\x8b"
        native.write_bytes(b"loser")
        cache._unpack(archive, [native])
        assert native.read_bytes() == b"canonical native"
    assert archive.closed


def test_explicit_worker_store_overrides_producer_default_without_workspace_use(
    tmp_path, monkeypatch
):
    worker = tmp_path / "worker" / "archive-cache" / "v1"
    monkeypatch.setattr(cache, "_WORKER_ARCHIVE_ROOT", worker)
    monkeypatch.setenv("HARMONIC_ARCHIVE_CACHE_ROOT", str(worker))
    assert cache._archive_cache_root() == worker
    assert (worker / "objects").is_dir()
    assert not worker.is_relative_to(cache.REPO_ROOT)


def test_local_root_io_failure_does_not_turn_a_remote_hit_into_a_miss(
    archive_store, monkeypatch
):
    backend = archive_store.backend
    payload = b"canonical native archive" * 8
    _put_bytes(backend, "c" * 64, payload)

    def inaccessible():
        raise PermissionError("local cache directory unavailable")

    monkeypatch.setattr(cache, "_archive_cache_root", inaccessible)
    assert _get_bytes(backend, "c" * 64) == payload


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
