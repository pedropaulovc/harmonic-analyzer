r"""Remote build-artefact cache for cache-keyed doit leaves.

The expensive tasks in this pipeline -- ``part:<stem>`` / ``assembly:<stem>`` /
``drawing:<stem>`` -- drive a live SolidWorks seat. Their hashed inputs determine
reusable geometry, not identical native bytes. A part's ``.SLDPRT`` is determined
by its build script + helper closure + the cad/config files it reads; an
assembly's ``.SLDASM`` by its recipe files + the recipe-stable referenced CAD
digests + the exact identities of those referenced artefacts; and a drawing by
its script/assets plus the exact restored part-identity token. ``dodo.py``
computes those input sets as each task's ``file_dep``.

This module turns that into a *shared* cache: key a task by the content hash of
its ``file_dep`` (repo-relative, parsed-YAML-normalised -- identical across
machines and worktrees), pack its outputs into one ``.tar.gz``, and push/pull it
through an object store. A machine WITHOUT a SolidWorks seat can then download a
prebuilt ``.SLDPRT``/``.SLDASM`` for an unchanged input set instead of failing on
COM; a CI builder with a seat populates the cache for everyone else.

The submitter-only ``check:machinist_review:<stem>`` leaves use the same cache
to freeze their aggregate verdict and retained evidence for unchanged review
inputs. They neither need a COM seat nor dispatch to the farm.

Design notes / invariants:

* **Content-addressed, input-keyed.** We key by INPUTS, never by the task's own
  output bytes. Referenced CAD inputs carry execution tokens that identify the
  exact artefacts whose PIDs/rebuild stamps the output was authored against; pure
  parent-save byte churn does not restamp them. Thus two valid outputs may differ
  in timestamp metadata, while incompatible child identities cannot share a key.

* **Repo-relative keys.** ``_digest_files`` in dodo tags by absolute path (correct
  for the local .doit.db, wrong for a shared cache). ``cache_key`` here tags by
  posix path RELATIVE to the repo root, so the same inputs hash equally on every
  machine.

* **Salt / epoch.** The toolchain (SolidWorks major version, the COM adapter) is
  NOT in any file_dep, so a SW upgrade that changes geometry would otherwise serve
  a stale hit. ``_DEFAULT_SALT`` (e.g. ``sw2024-sp3``, overridable by
  ``HARMONIC_CACHE_SALT``) is mixed into every key; bump it -- or the
  ``_CACHE_EPOCH`` constant -- to invalidate the whole cache.

* **Zero-config defaults.** The account/container/salt are committed constants
  (``_DEFAULT_*``), so a machine never has to be told where the cache lives -- it
  only declares a ROLE. Each is still overridable by the matching
  ``HARMONIC_CACHE_*`` env var (CI, tests, an unlanded salt bump).

* **Read/write roles.** The role is ``ro`` (pull only), ``rw`` (pull + push), or
  ``off`` (disabled). It comes from ``HARMONIC_REMOTE_CACHE_MODE`` or, failing
  that, a gitignored one-line ``.harmonic-remote-cache-mode`` file at the repo
  root, or finally
  ``_DEFAULT_MODE`` = ``rw``: both dev seats publish what they build by default,
  so neither rebuilds an artefact the other already produced. Drop a seat to
  ``ro``/``off`` via the file or env. A miss -- or an unauthorised ordinary push
  (RBAC denies a machine without the data-plane role) -- falls through to the
  real build. Explicit forced refreshes instead require successful publication.

* **Canonical publication.** Ordinary writes create only. After any upload error,
  a present entry means ``lost``: the action MUST adopt the winner's full archive,
  or fail. Absent-entry ordinary push failures remain soft. Explicit refresh alone
  may replace bytes, by CAS against its first pre-work ETag/absence snapshot.
  Downloads verify atomically committed archive hash/size metadata before unpack.
  Restores replace only the declared output inventory, including absent optional
  outputs and whole directory contents. Validate ownership and stage the complete
  archive before removing anything; a failed replacement is never a cache HIT.

* **Observable.** A cache miss must be explainable WITHOUT scrollback archaeology
  (issue #73). Three knobs, all best-effort and never able to fail a build:
  ``HARMONIC_CACHE_DEBUG=1`` logs every ``(relpath, digest)`` that feeds a key plus
  the final key, so a key shift is a readable diff; every restore/store event is
  appended to ``cad/out/reports/cache.jsonl`` (key + per-dependency inputs on
  miss/drift + event), so
  post-hoc debugging reads a file instead of the terminal; and a per-label
  ``cad/out/reports/cache-keys/<label>.key`` sidecar records the last key and input
  provenance THIS seat published, so on a HIT under a different key we WARN. This
  surfaces store-skip-on-hit drift (a HIT returns early and never re-stores, so the
  seat can serve a key it never published) directly -- but the WARN is reserved for
  a seat that PUBLISHES what it builds. A submitter under ``--executor farm`` (and
  a ``ro`` seat) never reaches ``store`` at all, so EVERY key it hits is one it
  structurally cannot have published; warning there fires on the normal path and
  teaches the operator to ignore the very signal it exists for. Those hits still
  emit the ``restore_hit_drift`` event, tagged ``drift_expected`` with the reason,
  at debug severity. ``cache_status`` (a doit task) prints all of the above per
  part/assembly in one command.

Backend: an **Azure Blob container** reached over HTTPS (443). Speaks plain object
storage, so it works from anywhere -- including networks (e.g. residential ISPs)
that block SMB/445, with no VPN, private endpoint, or mounted drive. A cache entry
is one ``<key>.tar.gz`` blob under a 2-hex virtual prefix. Configure with:

* ``HARMONIC_CACHE_ACCOUNT``   -- storage account name (e.g. ``stswbuildcache07aba2``)
* ``HARMONIC_CACHE_CONTAINER`` -- container name (default ``buildcache``)

Auth is keyless by default: ``DefaultAzureCredential`` picks up ``az login`` on a
dev box and the VM's managed identity on the builder (grant it *Storage Blob Data
Contributor*). For a keyed path (CI without RBAC), set ``HARMONIC_CACHE_SAS`` to a
container SAS token.

Eviction is server-side and MANAGED -- Azure Blob has a native lifecycle policy
(unlike Azure Files). With account *last-access-time tracking* enabled, a
``delete daysAfterLastAccessTimeGreaterThan: 7`` rule gives true LRU for free: a
restore is a blob *read*, which bumps last-access-time, so an artefact still in
active use is kept alive even when its inputs never change -- no client-side touch
and no scheduled cleanup job. See ``scripts/azure/provision_build_cache.ps1``.
"""

from __future__ import annotations

import atexit
import concurrent.futures
import contextlib
import errno
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO

# Bump to invalidate EVERY cached entry pipeline-wide (e.g. after a change to the
# packed OUTPUT set, the pack format, or a build-logic change not captured by any
# file_dep). Combine with the salt for toolchain-version busting.
#   2 -- part entries gained the .STL sidecar; assembly entries gained the channel
#        stretch parts + top-level gallery/BOM. Old epoch-1 blobs are incomplete
#        for the current pipeline, so they MUST NOT be served (codex review).
#   3 -- assembly entries renamed the free-DOF sidecar .park.json -> .dof.json
#        (park machinery removal). Epoch-2 assembly blobs carry the old sidecar
#        name, so a hit would restore no manifest and verify:kinematics would
#        fail on missing drive specs. (The recipe-digest shift from the same
#        change already keys new lookups away from old blobs; the bump makes
#        the archive-contract change explicit and unconditional -- codex #221.)
#   4 -- canonical first-writer publication with mandatory loser adoption and
#        atomically committed archive SHA-256/size metadata. No epoch-3 fallback:
#        old unconditional writers must never overwrite canonical native bytes.
_CACHE_EPOCH = "4"

# Project-wide defaults, committed so a machine opts in by setting only a MODE --
# never by rediscovering where the cache lives. Each is still overridable by the
# matching HARMONIC_CACHE_* env var (CI, tests, or a salt bump before it lands).
#   account/container -- not secret (RBAC-gated, public blob access off)
#   salt -- the toolchain epoch; bump it in the SAME commit that adapts to a new
#           SolidWorks version, so the cache busts in lockstep with the code.
_DEFAULT_ACCOUNT = "stswbuildcache07aba2"
_DEFAULT_CONTAINER = "buildcache"
_DEFAULT_SALT = "sw2024-sp3"

REPO_ROOT = Path(__file__).resolve().parents[2]

# A cache archive may write ONLY build outputs, all of which live under cad/out/.
# Constraining extraction here blocks both path traversal and a poisoned blob from
# overwriting tracked SOURCE (e.g. cad/scripts/*.py) that a later doit task runs.
_CACHE_OUTPUT_ROOT = REPO_ROOT / "cad" / "out"

# A machine's role (off | ro | rw). Read from HARMONIC_REMOTE_CACHE_MODE, else this
# gitignored one-line file at the repo root, else _DEFAULT_MODE. Default is rw:
# both dev seats build and PUBLISH, so each other's artefacts -- including private
# / experimental ones (content-addressed, so a unique input set => a unique key
# that never collides with the canonical cache) -- are pulled instead of rebuilt.
# Set the file/env to `ro` (pull only) or `off` (disabled) to downgrade a seat.
_MODE_FILE = REPO_ROOT / ".harmonic-remote-cache-mode"
_DEFAULT_MODE = "rw"

# Observability sinks (issue #73), all under the gitignored cad/out/reports/.
#   cache.jsonl       -- append-only event log (one JSON object per restore/store)
#   cache-keys/<l>.key -- the last key THIS seat PUBLISHED for label <l>, so a HIT
#                         under a different key is flagged as store-skip-on-hit drift
_REPORTS = REPO_ROOT / "cad" / "out" / "reports"
_EVENTS_LOG = _REPORTS / "cache.jsonl"
_KEYDIR = _REPORTS / "cache-keys"

# Per-process provenance carried from cache_key() into restore()/store(). A task
# computes its key immediately before those calls, so this stays bounded to the
# current doit process and avoids threading a second return value through dodo.
_KEY_INPUTS: dict[tuple[str, str], list[tuple[str, str]]] = {}
_KEY_CONTEXT: dict[tuple[str, str], tuple[str, str]] = {}
# Canonical snapshots are private/read-only and shared by telemetry + cache.jsonl.
_KEY_MANIFESTS: dict[tuple[str, str], tuple[dict, str, dict]] = {}
# Intentional refresh snapshots are captured at the FIRST probe, before work or
# seat wait, and never recaptured by an under-seat probe or upload. Alias entries
# use their root label with their own key. None means the entry was absent.
_REFRESH_ETAGS: dict[tuple[str, str], str | None] = {}

# Azure customDimensions values allow 8192 characters. ASCII JSON fragments keep
# both the character and UTF-8 byte size below that limit, including escaped paths.
# Chunks are structured DEBUG logs, not span events: SDK spans retain only 128
# events by default (and may be configured lower). Logs have no per-span count
# limit, so every input is emitted without adding spans or evicting decisions.
_MANIFEST_CHUNK_SIZE = 6000


def _provenance(label: str, key: str) -> dict:
    """The one recipe representation used by cache.jsonl and remote manifests."""
    pairs = _KEY_INPUTS.get((label, key))
    context = _KEY_CONTEXT.get((label, key))
    return {
        "schema": 1,
        "key": key,
        "epoch": context[0] if context else _CACHE_EPOCH,
        "salt": context[1] if context else _salt(),
        "recipe_known": pairs is not None and context is not None,
        "input_count": len(pairs) if pairs is not None else -1,
        "inputs": [{"path": path, "digest": digest} for path, digest in pairs or []],
    }


def _manifest(provenance: dict) -> tuple[str, dict]:
    """Canonical ASCII payload plus queryable integrity/completeness metadata."""
    payload = json.dumps(provenance, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    count = (len(payload) + _MANIFEST_CHUNK_SIZE - 1) // _MANIFEST_CHUNK_SIZE
    identity = hashlib.sha256(payload.encode("ascii")).hexdigest()
    return payload, {
        "manifest_id": identity,
        "manifest_schema": provenance["schema"],
        "manifest_chars": len(payload),
        "manifest_chunk_count": count,
        "manifest_emitted_chunks": count,
        "manifest_input_count": provenance["input_count"],
        "manifest_complete": provenance["recipe_known"],
        "manifest_transport": "logs",
    }


def _recipe_manifest(label: str, key: str) -> tuple[dict, str, dict]:
    """Serialize/hash each captured recipe once, without deduplicating signals."""
    identity = (label, key)
    saved = _KEY_MANIFESTS.get(identity)
    if saved is not None:
        return saved
    provenance = _provenance(label, key)
    payload, metadata = _manifest(provenance)
    saved = (provenance, payload, metadata)
    if provenance["recipe_known"]:
        _KEY_MANIFESTS[identity] = saved
    return saved


def _log(msg: str) -> None:
    with contextlib.suppress(Exception):
        import _telemetry  # cache remains usable even if telemetry is absent

        _telemetry.info(f"[cache] {msg}")


def _debug_log(msg: str) -> None:
    with contextlib.suppress(Exception):
        import _telemetry

        _telemetry.debug(f"[cache] {msg}")


def _warn(msg: str) -> None:
    """Cache drift and soft errors remain warnings; routine misses do not."""
    with contextlib.suppress(Exception):
        import _telemetry

        _telemetry.warn(f"[cache] {msg}")


def _event(name: str, label: str, key: str, **extra) -> None:
    """Keep outcome fields stable; emit bounded recipe fragments as DEBUG logs.

    No telemetry failure (including an unavailable module or a replaced sink)
    may turn a successful restore/store into a cache error. A manifest is emitted
    for misses AND successful hits/stores, so disposable seats need no sidecar
    to find a previous successful baseline. No dependency gets its own span."""
    try:
        import _telemetry

        if name not in ("cache.miss", "cache.hit", "cache.store"):
            _telemetry.event(name, label=label, key=key[:12], **extra)
            return
        provenance, payload, metadata = _recipe_manifest(label, key)
        _telemetry.event(
            name, label=label, key=key[:12], key_full=key,
            epoch=provenance["epoch"], salt=provenance["salt"], **metadata, **extra,
        )
        for index in range(metadata["manifest_chunk_count"]):
            _telemetry.debug(
                "cache.provenance", service=_telemetry.BUILD_INFRA_SERVICE,
                label=label, key=key[:12], key_full=key,
                outcome=name, **metadata, chunk_index=index,
                chunk=payload[index * _MANIFEST_CHUNK_SIZE:(index + 1) * _MANIFEST_CHUNK_SIZE],
            )
    except Exception:  # noqa: BLE001 -- observability must never change cache decisions
        pass


def _debug() -> bool:
    """HARMONIC_CACHE_DEBUG=1 (or any non-empty/non-``0`` value) -> log key inputs."""
    return os.environ.get("HARMONIC_CACHE_DEBUG", "").strip().lower() not in ("", "0", "false")


def _salt() -> str:
    return os.environ.get("HARMONIC_CACHE_SALT") or _DEFAULT_SALT


def _account() -> str:
    return os.environ.get("HARMONIC_CACHE_ACCOUNT") or _DEFAULT_ACCOUNT


def _container() -> str:
    return os.environ.get("HARMONIC_CACHE_CONTAINER") or _DEFAULT_CONTAINER


# --------------------------------------------------------------------------- #
# Key derivation
# --------------------------------------------------------------------------- #
def _rel(path: Path) -> str:
    """Repo-relative posix path -- the machine-independent identity of an input."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # Outside the repo (shouldn't happen for tracked inputs): fall back to the
        # basename so the key stays stable-ish rather than embedding an abs path.
        return path.name


def key_inputs(
    file_deps: list[str], digest_one, *, salt: str | None = None
) -> tuple[str, list[tuple[str, str]]]:
    """``(key, [(relpath, digest), ...])`` -- the cache key AND the per-file
    provenance that produced it, sorted by repo-relative path.

    ``digest_one(path) -> hex`` is dodo's per-file content digest
    (``ContentChecker._digest``: raw md5 for binaries, PARSED-yaml md5 for configs),
    passed in so the cache and the doit staleness check fold each file identically
    -- a comment-only YAML edit must not change the key, exactly as it must not
    invalidate the file_dep. Each file is tagged by its REPO-RELATIVE path (not
    absolute, unlike ``_digest_files``) so the key is identical across machines and
    worktrees. The input list is what ``HARMONIC_CACHE_DEBUG`` / ``cache_status``
    print so a key shift is a readable per-file diff (issue #73).

    Resolve each dependency's tag once per invocation and reuse it for sorting
    and provenance; equal tags retain input order, including duplicates. Tags
    are fresh on the next invocation. This is not an atomic filesystem snapshot:
    a symlink can still change between tagging and digesting its original path."""
    h = hashlib.sha256()
    h.update(f"epoch={_CACHE_EPOCH}\0salt={_salt() if salt is None else salt}\0".encode())
    pairs: list[tuple[str, str]] = []
    tagged = [(_rel(Path(path)), path) for path in file_deps]
    tagged.sort(key=lambda item: item[0])
    for rel, path in tagged:
        try:
            content = digest_one(path)
        except OSError:
            content = "<missing>"
        pairs.append((rel, content))
        h.update(f"{rel}\0{content}\0".encode())
    return h.hexdigest(), pairs


def cache_key(file_deps: list[str], digest_one, label: str | None = None) -> str:
    """Content hash of a task's ``file_dep`` set -> the cache key (see ``key_inputs``).

    With ``HARMONIC_CACHE_DEBUG`` set, logs each ``(digest, relpath)`` feeding the
    key and the resulting key, tagged by ``label`` -- so a debugger can see exactly
    which dep digest moved when a key shifts (issue #73)."""
    salt = _salt()
    key, pairs = key_inputs(file_deps, digest_one, salt=salt)
    if label:
        _KEY_INPUTS[(label, key)] = pairs
        _KEY_CONTEXT[(label, key)] = (_CACHE_EPOCH, salt)
        _KEY_MANIFESTS.pop((label, key), None)
    if _debug():
        head = label or "?"
        _log(f"key provenance {head} (epoch={_CACHE_EPOCH} salt={salt}):")
        for rel, content in pairs:
            _log(f"    {content}  {rel}")
        _log(f"  => {head} key {key}")
    return key


def key_input_paths(label: str, key: str) -> list[str] | None:
    """Repo-relative paths ``key`` was computed from for ``label`` in this
    process, or ``None`` when this process never computed it."""
    pairs = _KEY_INPUTS.get((label, key))
    return None if pairs is None else [path for path, _ in pairs]


# --------------------------------------------------------------------------- #
# Pack / unpack -- one gzip tar of a task's outputs, paths stored repo-relative
# --------------------------------------------------------------------------- #
# gzip level 6 (zlib's default), not tarfile's 9: the export and package entries
# (329 MB / 660 MB) spend most of their pack in deflate, and on the real 701 MB
# export payload level 9 took 25.1 s for 329.1 MB against 12.3 s for 348.1 MB at
# level 6. SLDPRT/PNG members are already compressed, so their size barely moves.
# Only the stored bytes change: keys hash inputs, and restore reads any level.
_PACK_LEVEL = 6


def _pack(outputs: list[Path]) -> BinaryIO:
    """Return an owned, seekable archive; the caller closes its private file."""
    archive = tempfile.TemporaryFile(mode="w+b")
    try:
        with tarfile.open(
            name="", fileobj=archive, mode="w:gz", compresslevel=_PACK_LEVEL,
        ) as tar:
            for out in outputs:
                if out.exists():
                    tar.add(str(out), arcname=_rel(out))
        archive.seek(0)
        return archive
    except BaseException:
        archive.close()
        raise


def _restore_path(path: Path) -> Path:
    """A replacement target must be a strict, unaliased child of cad/out/."""
    target = Path(os.path.abspath(path))
    if (
        target == _CACHE_OUTPUT_ROOT
        or not target.is_relative_to(_CACHE_OUTPUT_ROOT)
        or target.resolve() != target
    ):
        raise RuntimeError(f"unsafe cache output path: {path}")
    return target


def _unpack(blob: BinaryIO, outputs: list[Path]) -> None:
    # Validate EVERY deletion target before touching any of them. Collapsing
    # overlaps preserves directory ownership without deleting shared parents.
    owned = sorted({_restore_path(Path(output)) for output in outputs})
    roots = [
        path for path in owned
        if not any(parent in owned for parent in path.parents)
    ]
    blob.seek(0)
    with tarfile.open(fileobj=blob, mode="r:gz") as tar:
        members = tar.getmembers()
        if not members:
            raise RuntimeError("empty cache archive has no canonical outputs")
        for member in members:
            # Reject links/special files, traversal and Windows path aliases
            # (including alternate data streams), even on non-Windows readers.
            if (
                not (member.isreg() or member.isdir())
                or "\\" in member.name
                or ":" in member.name
                or ".." in Path(member.name).parts
            ):
                raise RuntimeError(f"unsafe cache archive member: {member.name}")
            _restore_path(REPO_ROOT / member.name)

        # Parse/extract the complete payload BEFORE deleting local outputs. A bad
        # member or truncated archive must leave the producer's tree untouched.
        # Same-volume staging lets installation move bytes, not copy them again.
        _CACHE_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".cache-restore-", dir=_CACHE_OUTPUT_ROOT
        ) as temporary:
            staged = Path(temporary)
            tar.extractall(staged, members=members, filter="data")
            # tar.add recorded the BUILDER's mtimes. Refresh them so downstream
            # export/release freshness guards see the newly restored geometry.
            now = time.time()
            for member in members:
                if member.isreg():
                    try:
                        os.utime(staged / member.name, (now, now))
                    except OSError:
                        pass
            for output in roots:
                # Recheck after staging, before replacement; do not follow a
                # newly introduced alias into a sibling's output tree.
                _restore_path(output)
            for output in roots:
                if output.is_dir():
                    shutil.rmtree(output)
                else:
                    output.unlink(missing_ok=True)
                source = staged / output.relative_to(REPO_ROOT)
                if source.exists():
                    output.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, output)
                # An absent optional output belongs to the winner too. A share
                # lock during deletion/install propagates to RestoreLocked and
                # the existing under-seat release/retry; never report a HIT.
            # Some inventories discover optional files from the local tree
            # (channel spring variants). A winner can contain new files the
            # receiver did not enumerate. Install those too, but never expand
            # recursive deletion to an archive-supplied shared directory.
            for member in members:
                source = staged / member.name
                if not source.exists():
                    continue  # already installed with an inventoried root
                dest = _restore_path(REPO_ROOT / member.name)
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, dest)


# --------------------------------------------------------------------------- #
# Backend -- Azure Blob container over HTTPS (443)
# --------------------------------------------------------------------------- #
# Parallel block transfers for the entries above the single-shot size: the
# export and package entries. The SDK default moves their 4 MiB blocks one at a
# time; downloading the 329 MB export entry took 244.3 s serially and 45.8 s at
# 8. Smaller entries still go in one request.
_TRANSFER_CONCURRENCY = 8
# One Put Blob up to this size (the SDK's own single-shot default); above it,
# ``_BlobBackend.put`` stages _BLOCK_SIZE blocks under writer-unique IDs.
_SINGLE_PUT_MAX = 64 * 1024 * 1024
_BLOCK_SIZE = 4 * 1024 * 1024

# Small gate stamps need one GET, not HEAD+GET. The SDK's first GET is bounded
# by this size; larger local hits discard that prefix and reuse verified disk
# bytes. 8 MiB is a conservative memory/probe policy, not a network-speed claim.
_ARCHIVE_CACHE_MIN = 8 * 1024 * 1024
_ARCHIVE_CACHE_CAP = 16 * 1024 * 1024 * 1024
_ARCHIVE_LOCK_WAIT_S = 0.05
_WORKER_ARCHIVE_ROOT = Path("C:/ProgramData/solidworks-pool/archive-cache/v1")
_HASH_NAME = re.compile(r"[0-9a-f]{64}")
_OBJECT_TEMP_NAME = re.compile(r"\.[0-9a-f]{64}\.[0-9a-f]{32}\.tmp")


def _archive_cache_roots() -> tuple[Path, ...]:
    local = os.environ.get("LOCALAPPDATA")
    producer = (Path(local) / "harmonic-analyzer" / "archive-cache" / "v1") if local else None
    return (*((producer,) if producer is not None else ()), _WORKER_ARCHIVE_ROOT)


class _LocalArchiveRefused(RuntimeError):
    """Reject optional store access without rejecting verified remote bytes."""

    def __init__(self, reason: str, message: str | None = None):
        self.reason = reason
        super().__init__(message if message is not None else reason)


def _archive_object_lock(root: Path, digest: str) -> Path:
    # Fixed 256 shards bound lease-file growth. Never unlink a lock inode:
    # competing opens could otherwise acquire different locks for one object.
    return root / "locks" / f"object-{digest[:2]}"


def _note_local_store(span, outcome: str) -> str:
    span.set_attribute("local_outcome", outcome)
    reason = {
        "disabled": "not_configured", "small": "below_threshold",
        "oversize": "size_limit", "corrupt": "identity_mismatch",
        "busy": "lock_busy", "persist_skipped_busy": "lock_busy",
        "persist_skipped_capacity": "capacity",
    }.get(outcome)
    if reason:
        span.set_attribute("local_reason", reason)
        _debug_log(f"local archive {outcome} ({reason})")
    return outcome


def _local_store_problem(span, operation: str, exc: OSError | _LocalArchiveRefused) -> str:
    outcome = "refused" if isinstance(exc, _LocalArchiveRefused) else "unavailable"
    _note_local_store(span, outcome)
    span.set_attribute("local_reason", exc.reason if isinstance(exc, _LocalArchiveRefused) else "io_error")
    _warn(f"local archive {operation} skipped ({exc!r})")
    return outcome


def _unalias(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    if (
        path.drive.startswith("\\\\") or not path.is_absolute()
        or absolute != path or path.resolve() != path
    ):
        raise _LocalArchiveRefused("unsafe_path", f"unsafe local archive cache path: {path}")
    return path


def _archive_cache_root() -> Path | None:
    allowed = _archive_cache_roots()
    raw = os.environ.get("HARMONIC_ARCHIVE_CACHE_ROOT")
    # Workers supply their validated root explicitly. Ordinary producers have a
    # per-user default; absent LOCALAPPDATA and configuration disables reuse.
    root = Path(raw) if raw else (allowed[0] if os.environ.get("LOCALAPPDATA") else None)
    if root is None:
        return None
    _unalias(root)
    repo = REPO_ROOT.resolve()
    if root not in allowed or root.is_relative_to(repo) or repo.is_relative_to(root):
        raise _LocalArchiveRefused("unapproved_root", f"unapproved local archive cache root: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("objects", "locks"):
        child = _unalias(root / name)
        child.mkdir(exist_ok=True)
        _unalias(child)
    return _unalias(root)


@contextlib.contextmanager
def _archive_lock(path: Path, *, blocking: bool = True):
    """Short, bounded cross-process leases for optional cache work.

    Stable lock files are never removed: unlinking a locked inode permits split
    locks on POSIX. A busy store must not hold a valid remote restore hostage.
    """
    _unalias(path)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + (_ARCHIVE_LOCK_WAIT_S if blocking else 0)
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    yield False
                    return
                time.sleep(min(0.01, remaining))
        try:
            yield True
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _archive_size(archive: BinaryIO) -> int:
    position = archive.tell()
    archive.seek(0, os.SEEK_END)
    size = archive.tell()
    archive.seek(position)
    return size


def _archive_identity(archive: BinaryIO) -> tuple[str, int]:
    archive.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := archive.read(_BLOCK_SIZE):
        digest.update(chunk)
        size += len(chunk)
    archive.seek(0)
    return digest.hexdigest(), size


def _archive_copy(
    source: BinaryIO, destination: BinaryIO, expected_size: int, *, hash_content: bool = True,
) -> tuple[str | None, int]:
    """Bound copies by authoritative length, even if a shared source grows.

    Shared objects always get hashed. Only persistence of an already-verified
    process-owned download disables the redundant second hash pass.
    """
    source.seek(0)
    digest = hashlib.sha256() if hash_content else None
    size = 0
    while size < expected_size:
        chunk = source.read(min(_BLOCK_SIZE, expected_size - size))
        if not chunk:
            break
        destination.write(chunk)
        if digest is not None:
            digest.update(chunk)
        size += len(chunk)
    if source.read(1):
        size += 1  # detect growth, but never copy excess bytes into the temp
    destination.flush()
    destination.seek(0)
    return digest.hexdigest() if digest is not None else None, size


def _local_archive(root: Path, digest: str, size: int) -> tuple[BinaryIO | None, str]:
    path = _unalias(root / "objects" / digest)
    with _archive_lock(_archive_object_lock(root, digest)) as acquired:
        if not acquired:
            return None, "busy"
        try:
            before = path.stat()
        except FileNotFoundError:
            return None, "miss"
        if not stat.S_ISREG(before.st_mode) or before.st_size != size:
            return None, "corrupt"
        with path.open("rb") as source:
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode) or opened.st_size != size:
                return None, "corrupt"
            private = tempfile.TemporaryFile(mode="w+b")
            try:
                actual = _archive_copy(source, private, size)
                if actual != (digest, size):
                    private.close()
                    return None, "corrupt"
                # Touch failure cannot discard verified, process-owned bytes.
                with _phase("cache.local_store", operation="touch") as touch:
                    try:
                        os.utime(_unalias(path), None)
                    except (OSError, _LocalArchiveRefused) as exc:
                        _local_store_problem(touch, "touch", exc)
                    else:
                        _note_local_store(touch, "touched")
                return private, "hit"
            except BaseException:
                private.close()
                raise


def _evict_archives(root: Path, *, reserve: int = 0, reason: str = "admission") -> bool:
    """Under the host lock, make room using only unleased NEW regular objects."""
    objects = _unalias(root / "objects")
    with _phase("cache.local_eviction", reserve_bytes=reserve, reason=reason) as eviction:
        entries = []
        skipped = 0
        busy = 0
        evicted = 0
        for path in objects.iterdir():
            temporary = _OBJECT_TEMP_NAME.fullmatch(path.name)
            if not temporary and not _HASH_NAME.fullmatch(path.name):
                continue
            try:
                safe = _unalias(path)
                info = safe.stat()
                if not stat.S_ISREG(info.st_mode):
                    skipped += 1
                    continue
                if temporary:
                    # All live publishers hold the same store lock.
                    safe.unlink(missing_ok=True)
                else:
                    entries.append((info.st_mtime_ns, safe, info.st_size))
            except (OSError, _LocalArchiveRefused) as exc:
                skipped += 1
                _debug_log(f"local archive eviction entry skipped ({exc!r})")
        total = sum(size for _, _, size in entries)
        for _, path, size in sorted(entries):
            if total + reserve <= _ARCHIVE_CACHE_CAP:
                break
            try:
                with _archive_lock(_archive_object_lock(root, path.name), blocking=False) as acquired:
                    if not acquired:
                        skipped += 1
                        busy += 1  # Includes conservative skips for shard collisions.
                        continue
                    _unalias(path).unlink(missing_ok=True)
                    total -= size
                    evicted += size
            except (OSError, _LocalArchiveRefused) as exc:
                skipped += 1
                _debug_log(f"local archive eviction entry skipped ({exc!r})")
        eviction.set_attribute("skipped_entries", skipped)
        eviction.set_attribute("busy_entries", busy)
        eviction.set_attribute("evicted_bytes", evicted)
        eviction.set_attribute("capacity_available", total + reserve <= _ARCHIVE_CACHE_CAP)
        return total + reserve <= _ARCHIVE_CACHE_CAP


def _save_archive(
    root: Path, digest: str, size: int, archive: BinaryIO, *, replace_corrupt: bool = False,
) -> str:
    """Persist an already-verified process-owned archive, without rehashing it."""
    if size > _ARCHIVE_CACHE_CAP:
        return "oversize"
    with _archive_lock(root / "locks" / "store") as store_acquired:
        if not store_acquired:
            return "persist_skipped_busy"
        path = _unalias(root / "objects" / digest)
        with _archive_lock(_archive_object_lock(root, digest)) as object_acquired:
            if not object_acquired:
                return "persist_skipped_busy"
            try:
                info = path.stat()
            except FileNotFoundError:
                info = None
            if info is not None:
                if not stat.S_ISREG(info.st_mode):
                    raise _LocalArchiveRefused("non_regular", f"unsafe local archive object: {path}")
                if not replace_corrupt and info.st_size == size:
                    # Another writer won. Do not rehash/rewrite/evict for an
                    # identical-address object; the next reader still rehashes.
                    return "already_present"
                _unalias(path).unlink()
            reason = "corrupt_replacement" if replace_corrupt or info is not None else "admission"
            if not _evict_archives(root, reserve=size, reason=reason):
                return "persist_skipped_capacity"
            temporary = path.with_name(f".{digest}.{secrets.token_hex(16)}.tmp")
            try:
                with temporary.open("x+b") as destination:
                    _, copied = _archive_copy(archive, destination, size, hash_content=False)
                    if copied != size:
                        raise RuntimeError("private archive changed before local publication")
                os.replace(temporary, path)
            finally:
                try:
                    _unalias(temporary).unlink(missing_ok=True)
                except (OSError, _LocalArchiveRefused) as exc:
                    # A cleanup failure must not replace a private-stream
                    # integrity/programming error with an optional I/O error.
                    _debug_log(f"local archive temp cleanup skipped ({exc!r})")
    archive.seek(0)
    return "persisted"


class _BlobBackend:
    """Canonical remote archives with optional verified, file-backed local reuse."""

    def __init__(self, container_client, credential=None):
        self._cc = container_client
        self._credential = credential

    def enable_credential_retries(self):
        """Promote a successfully warmed private credential to the normal policy."""
        if self._credential is not None:
            self._credential.enable_retries()

    def close(self):
        """Close a private backend; Azure's client closes sockets, not credentials."""
        try:
            self._cc.close()
        finally:
            if self._credential is not None:
                self._credential.close()

    def _name(self, key: str) -> str:
        # Shard by the first 2 hex chars (virtual prefix) to avoid one giant listing.
        return f"{key[:2]}/{key}.tar.gz"

    def get(self, key: str) -> BinaryIO | None:
        from azure.core.exceptions import ResourceNotFoundError

        with _phase("cache.download", phase="probe", network_bytes_known=False) as probe:
            try:
                blob = self._cc.get_blob_client(self._name(key))
                download = blob.download_blob(max_concurrency=_TRANSFER_CONCURRENCY)
            except ResourceNotFoundError:
                probe.set_attribute("found", False)
                probe.set_attribute("bytes", 0)
                probe.set_attribute("network_bytes", 0)
                probe.set_attribute("network_bytes_known", True)
                return None
            # Identity and prefix belong to the SAME response. The SDK pins its
            # ETag for every remaining range; no recipe map or second HEAD/GET.
            properties = download.properties
            metadata = properties.metadata
            size = properties.size
            digest = metadata.get("archive_sha256")
            if type(size) is not int or size < 0:
                raise RuntimeError(f"cache archive integrity mismatch for {key}")
            probe_bytes = min(size, _ARCHIVE_CACHE_MIN)
            probe.set_attribute("found", True)
            probe.set_attribute("bytes", probe_bytes)
            probe.set_attribute("network_bytes", probe_bytes)
            probe.set_attribute("network_bytes_known", True)
            probe.set_attribute("archive_bytes", size)
            if (
                metadata.get("epoch") != _CACHE_EPOCH
                or metadata.get("archive_size") != str(size)
                or not isinstance(digest, str) or not _HASH_NAME.fullmatch(digest)
                or not isinstance(properties.etag, str) or not properties.etag
            ):
                raise RuntimeError(f"cache archive integrity mismatch for {key}")
        with _phase(
            "cache.archive", archive_bytes=size, network_bytes=probe_bytes,
            probe_bytes=probe_bytes, reused_bytes=0, network_bytes_known=True,
        ) as reuse:
            root = None
            private = None
            lookup = "small" if size <= _ARCHIVE_CACHE_MIN else "oversize"
            if _ARCHIVE_CACHE_MIN < size <= _ARCHIVE_CACHE_CAP:
                with _phase("cache.local_store", operation="root") as local:
                    try:
                        root = _archive_cache_root()
                    except (OSError, _LocalArchiveRefused) as exc:
                        lookup = _local_store_problem(local, "root", exc)
                    else:
                        lookup = _note_local_store(local, "ready" if root is not None else "disabled")
                if root is not None:
                    with _phase("cache.local_store", operation="lookup") as local:
                        try:
                            private, lookup = _local_archive(root, digest, size)
                        except (OSError, _LocalArchiveRefused) as exc:
                            lookup = _local_store_problem(local, "lookup", exc)
                            root = None  # do not retry a refused/unavailable store on persistence
                        else:
                            _note_local_store(local, lookup)
            reuse.set_attribute("local_lookup_outcome", lookup)
            # Reasons stay on phase-specific spans: persistence can change the outcome.
            reuse.set_attribute("local_outcome", lookup)
            if private is not None:
                reuse.set_attribute("reused_bytes", size - probe_bytes)
                return private
            private = tempfile.TemporaryFile(mode="w+b")
            try:
                # Only network I/O is timed as cache.download. Verification and
                # optional local persistence have separate spans and byte units.
                try:
                    if size > probe_bytes:
                        reuse.set_attribute("network_bytes_known", False)
                        with _phase("cache.download", phase="body", network_bytes_known=False) as body:
                            download.readinto(private)
                            body.set_attribute("bytes", size - probe_bytes)
                            body.set_attribute("network_bytes", size - probe_bytes)
                            body.set_attribute("network_bytes_known", True)
                            body.set_attribute("archive_bytes", size)
                    else:
                        download.readinto(private)  # complete buffered prefix; no more network body
                except ResourceNotFoundError:
                    private.close()
                    return None
                reuse.set_attribute("network_bytes", size)
                reuse.set_attribute("network_bytes_known", True)
                with _phase("cache.verify", archive_bytes=size):
                    if _archive_identity(private) != (digest, size):
                        raise RuntimeError(f"cache archive integrity mismatch for {key}")
                if root is not None:
                    with _phase("cache.local_store", operation="persist", archive_bytes=size) as local:
                        try:
                            persisted = _save_archive(
                                root, digest, size, private, replace_corrupt=lookup == "corrupt",
                            )
                        except (OSError, _LocalArchiveRefused) as exc:
                            persisted = _local_store_problem(local, "persist", exc)
                        else:
                            _note_local_store(local, persisted)
                        reuse.set_attribute("local_outcome", persisted)
                private.seek(0)
                return private
            except BaseException:
                private.close()
                raise

    def exists(self, key: str) -> bool:
        # Presence check without downloading the blob -- the cache_status diagnostic
        # probes every key, so a HEAD (exists) instead of a GET (download) keeps it cheap.
        return self._cc.get_blob_client(self._name(key)).exists()

    def etag(self, key: str) -> str | None:
        """Snapshot a refresh precondition; None denotes an absent entry."""
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._cc.get_blob_client(self._name(key)).get_blob_properties().etag
        except ResourceNotFoundError:
            return None

    def put(self, key: str, blob: BinaryIO, *, replace_etag: str | None = None) -> None:
        # Input identity does not imply identical native bytes. Ordinary writers
        # create only; explicit refresh is the sole CAS replacement. Writer-unique
        # blocks also prevent interleaved uploads from committing a torn archive.
        from azure.core import MatchConditions

        digest, size = _archive_identity(blob)
        metadata = {
            "archive_sha256": digest,
            "archive_size": str(size),
            "epoch": _CACHE_EPOCH,
        }
        condition = (
            {"etag": replace_etag, "match_condition": MatchConditions.IfNotModified}
            if replace_etag is not None
            else {"match_condition": MatchConditions.IfMissing}
        )
        client = self._cc.get_blob_client(self._name(key))
        if size <= _SINGLE_PUT_MAX:
            client.upload_blob(
                blob, length=size, overwrite=replace_etag is not None, metadata=metadata,
                **(condition if replace_etag is not None else {}),
            )
            return
        from azure.storage.blob import BlobBlock

        writer = secrets.token_hex(16)
        count = -(-size // _BLOCK_SIZE)
        ids = [f"{writer}{index:016d}" for index in range(count)]
        reader_lock = threading.Lock()

        def stage(index: int) -> None:
            # Only a bounded block per active transfer, never a whole-archive
            # slice or a separate payload copy. Serialize seek/read, not upload.
            with reader_lock:
                blob.seek(index * _BLOCK_SIZE)
                chunk = blob.read(_BLOCK_SIZE)
            client.stage_block(ids[index], chunk)

        with concurrent.futures.ThreadPoolExecutor(_TRANSFER_CONCURRENCY) as pool:
            for _ in pool.map(stage, range(count)):
                pass
        client.commit_block_list(
            [BlobBlock(block_id=block_id) for block_id in ids],
            metadata=metadata, **condition,
        )


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #
def keyed_action(action):
    """Mark a doit action that uses the shared remote-cache key/probe/store path."""
    action._remote_cache_action = True
    return action


def validate_refresh_reason(reason: str | None) -> str:
    """Validate human refresh metadata before any cache or farm side effect."""
    if (
        not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > 160
        or any(
            unicodedata.category(char) in {"Cc", "Zl", "Zp"}
            or char in "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
            for char in reason
        )
    ):
        raise RuntimeError(
            "--force-cache-refresh-reason / HARMONIC_CACHE_REFRESH reason must "
            "be nonblank, single-line, free of control characters, and at most "
            "160 characters"
        )
    try:
        reason.encode("utf-8")
    except UnicodeEncodeError:
        raise RuntimeError(
            "--force-cache-refresh-reason / HARMONIC_CACHE_REFRESH reason must "
            "contain valid Unicode"
        ) from None
    return reason


def forced_refresh(label: str) -> str | None:
    """Read this invocation's explicit refresh set lazily, refusing bad carriers."""
    raw = os.environ.get("HARMONIC_CACHE_REFRESH")
    if raw is None:
        return None
    try:
        request = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise RuntimeError(f"HARMONIC_CACHE_REFRESH is not valid JSON: {exc}") from None
    if not isinstance(request, dict) or not isinstance(request.get("labels"), list):
        raise RuntimeError("HARMONIC_CACHE_REFRESH must contain a labels list and reason")
    labels = request["labels"]
    if not labels or any(not isinstance(item, str) or not item.strip() for item in labels):
        raise RuntimeError("HARMONIC_CACHE_REFRESH labels must be non-empty task names")
    reason = validate_refresh_reason(request.get("reason"))
    if not writable():
        raise RuntimeError("forced cache refresh requires HARMONIC_REMOTE_CACHE_MODE=rw")
    return reason if label in labels else None


def capture_refresh(label: str, key: str) -> None:
    """Capture a root/alias CAS once, before intentional refresh work begins."""
    if forced_refresh(label) is None or (label, key) in _REFRESH_ETAGS:
        return
    backend = _backend()
    if backend is None:
        raise RuntimeError(f"{label}: cannot snapshot forced cache refresh ({key[:12]})")
    _REFRESH_ETAGS[(label, key)] = backend.etag(key)


def note_refresh(label: str, key: str, reason: str) -> None:
    """Expose an intentionally skipped restore through every cache diagnostic."""
    capture_refresh(label, key)
    _warn(f"refresh {label} ({key[:12]}): {reason}")
    _event("cache.refresh", label, key, reason=reason)
    _record("refresh", label, key, reason=reason)


def require_refresh_store(label: str, outcome: str) -> str:
    """A requested refresh is successful only after the replacement is published."""
    if forced_refresh(label) is not None and outcome != "stored":
        raise RuntimeError(f"{label}: forced cache refresh did not store outputs ({outcome})")
    return outcome

def _mode() -> str:
    env = os.environ.get("HARMONIC_REMOTE_CACHE_MODE")
    if env:
        return env.lower()
    try:
        return _MODE_FILE.read_text(encoding="utf-8").strip().lower() or _DEFAULT_MODE
    except OSError:
        return _DEFAULT_MODE


def enabled() -> bool:
    return _mode() in ("ro", "rw")


def writable() -> bool:
    return _mode() == "rw"


def _farm_executor() -> bool:
    """Are this run's cache-missing leaves dispatched to the build farm (rather
    than executed on this box)? Answered by ``_farm.enabled()`` -- the one
    definition of what ``--executor farm`` means, never a second copy of the env
    check. Imported inside the call, like ``_telemetry``, so this module keeps no
    import-time dependency on the farm stack."""
    import _farm

    return _farm.enabled()


def _cannot_publish_reason() -> str | None:
    """Why this process structurally CANNOT publish the artefacts it consumes --
    or ``None`` when it can, and a HIT under an unpublished key is real drift.

    The store-skip-on-hit warning only carries information for a seat that builds
    its own leaves AND publishes them: there, a HIT under a key its sidecar never
    recorded means the seat is trusting an artefact it should have produced itself
    (the v0.9.0 bug). Two roles can never have published the key they hit:

    * ``executor=farm`` -- the submitter hands every cache-missing leaf to a
      worker, which builds and publishes the key; ``dodo._farm_build`` returns
      before the ``cache.store`` phase, so this process never stores anything and
      EVERY hit is under a worker-published key.
    * ``cache_mode=ro`` -- a pull-only seat declines to publish by configuration.

    For those the condition is the normal path, so it is logged, not warned."""
    if _farm_executor():
        return "executor=farm"
    if not writable():
        return f"cache_mode={_mode()}"
    return None


def config_summary() -> dict:
    """Effective cache config, for the cache_status header (issue #73)."""
    return {
        "mode": _mode(),
        "epoch": _CACHE_EPOCH,
        "salt": _salt(),
        "account": _account(),
        "container": _container(),
    }


# --------------------------------------------------------------------------- #
# Provenance sinks -- event log + per-label "last published key" sidecar.
# Every helper here is BEST-EFFORT: a logging failure must never break a build,
# so each swallows OSError and returns a benign default.
# --------------------------------------------------------------------------- #
def _record(event: str, label: str, key: str, **extra) -> None:
    """Append one cache event to cache.jsonl with the same recipe as telemetry.
    Miss/drift additionally retain the seat's previous published provenance
    (issue #255); successful hits/stores provide portable historical baselines.

    ``extra`` fields are written verbatim alongside the base record: cache.jsonl is
    the post-hoc record, so an outcome whose CONSOLE severity was demoted still
    lands here in full, carrying why it was demoted."""
    try:
        _REPORTS.mkdir(parents=True, exist_ok=True)
        provenance, _, metadata = _recipe_manifest(label, key)
        rec = {"ts": round(time.time(), 3), "event": event, "label": label,
               **provenance, **metadata}
        if event in ("restore_miss", "restore_hit_drift"):
            previous = _stored_provenance(label)
            if previous and previous["key"] != key:
                rec["previous_key"] = previous["key"]
                rec["previous_inputs"] = [
                    {"path": path, "digest": digest}
                    for path, digest in previous["inputs"]
                ]
        rec.update(extra)
        with _EVENTS_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def _key_sidecar(label: str) -> Path:
    return _KEYDIR / (label.replace(":", "-").replace("/", "-") + ".key")


def last_stored_key(label: str) -> str | None:
    """The last key THIS seat actually PUBLISHED for ``label`` (None if never).
    Updated only by a successful ``store`` -- a HIT does NOT update it, so a HIT
    under a different key reveals the store-skip-on-hit drift."""
    saved = _stored_provenance(label)
    return saved["key"] if saved else None


def last_stored_inputs(label: str) -> list[tuple[str, str]]:
    """Per-dependency provenance for the last key this seat published."""
    saved = _stored_provenance(label)
    return list(saved["inputs"]) if saved else []


def _stored_provenance(label: str) -> dict | None:
    """Read the JSON sidecar, accepting legacy plain-key files from issue #73."""
    try:
        raw = _key_sidecar(label).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    if not raw:
        return None
    try:
        saved = json.loads(raw)
    except json.JSONDecodeError:
        return {"key": raw, "inputs": []}
    if not isinstance(saved, dict) or not isinstance(saved.get("key"), str):
        return None
    inputs = saved.get("inputs", [])
    if not isinstance(inputs, list):
        inputs = []
    pairs = [
        (pair[0], pair[1])
        for pair in inputs
        if isinstance(pair, list)
        and len(pair) == 2
        and isinstance(pair[0], str)
        and isinstance(pair[1], str)
    ]
    return {"key": saved["key"], "inputs": pairs}


def _save_stored_key(label: str, key: str) -> None:
    try:
        _KEYDIR.mkdir(parents=True, exist_ok=True)
        saved = {"key": key, "inputs": _KEY_INPUTS.get((label, key), [])}
        _key_sidecar(label).write_text(json.dumps(saved) + "\n", encoding="utf-8")
    except OSError:
        pass


class _Unset:
    """Singleton sentinel marking '_BACKEND not yet initialised'.

    A dedicated class (rather than plain ``object()``) lets pyright understand
    the three-state union without a blanket ``# type: ignore`` on every access.
    """


_UNSET = _Unset()
_BACKEND: _BlobBackend | None | _Unset = _UNSET


class _NoSpan:
    """What :func:`_phase` yields when this process never loaded the telemetry spine."""

    def set_attribute(self, key: str, value) -> None:
        pass


@contextlib.contextmanager
def _phase(name: str, **attributes):
    """A ``build-infra`` span for one phase of a cache transfer. A farm leaf's own
    ``cache.probe`` (the first in its process) reads 0.90 s p50 for a part against
    0.15 s for a drawing, whose part dependencies were probed first (14 d, n=3194 /
    3221) -- with nothing inside it, so the SDK import, the token fetch, the
    transfer and the unpack each get their own span to say which one that is.

    Spans only where the telemetry spine is ALREADY loaded (every doit process).
    The pool's job runner imports this module bare to confirm a publish
    (``probe``); importing ``_telemetry`` there would configure a whole OTel
    pipeline in that helper just to time one HEAD."""
    telemetry = sys.modules.get("_telemetry")
    if telemetry is None:
        yield _NoSpan()
        return
    with telemetry.span(name, service=telemetry.BUILD_INFRA_SERVICE, **attributes) as sp:
        yield sp


def _token_request_identity(value):
    """Freeze request options without logging their potentially secret contents."""
    if isinstance(value, dict):
        return (dict, frozenset(
            (_token_request_identity(key), _token_request_identity(item))
            for key, item in value.items()
        ))
    if isinstance(value, (list, tuple)):
        return (type(value), tuple(_token_request_identity(item) for item in value))
    if isinstance(value, (set, frozenset)):
        return (type(value), frozenset(_token_request_identity(item) for item in value))
    return (type(value), value)


class _CredentialOutcome(Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    TRANSIENT = "transient"
    FAILURE = "failure"


@dataclass(frozen=True)
class _CredentialObservation:
    credential: str
    error_type: str
    cause_type: str
    outcome: _CredentialOutcome


def _transient_credential_cause(exc):
    from azure.core.exceptions import ServiceRequestError, ServiceResponseError

    pending = [exc]
    seen = set()
    while pending:
        cause = pending.pop()
        if cause is None or id(cause) in seen:
            continue
        seen.add(id(cause))
        if isinstance(cause, (subprocess.TimeoutExpired, TimeoutError,
                              ServiceRequestError, ServiceResponseError)):
            return cause
        pending.extend((cause.__cause__, cause.__context__))
    return None


def _credential_observation(inner, exc=None, *, established=False):
    from azure.identity import CredentialUnavailableError, ManagedIdentityCredential
    from azure.identity._credentials.imds import ImdsCredential

    cause = _transient_credential_cause(exc) if exc is not None else None
    if exc is None:
        outcome = _CredentialOutcome.SUCCESS
    elif not isinstance(exc, CredentialUnavailableError):
        outcome = _CredentialOutcome.FAILURE
    elif cause is None or (
        isinstance(inner, (ManagedIdentityCredential, ImdsCredential)) and not established
    ):
        # An unproven IMDS transport failure is endpoint discovery, not an outage
        # of an identity we know works. Other sources (notably CLI) need no probe.
        outcome = _CredentialOutcome.UNAVAILABLE
    else:
        outcome = _CredentialOutcome.TRANSIENT
    return _CredentialObservation(
        type(inner).__name__,
        type(exc).__name__ if exc is not None else "",
        type(cause).__name__ if cause is not None else "",
        outcome,
    )


_CREDENTIAL_COOLDOWN_S = 30.0
_CREDENTIAL_ATTEMPTS = 3


class _ObservedCredentialLink:
    """Forward a chain link unchanged while retaining typed, per-thread outcomes."""

    def __init__(self, inner, observation):
        self._inner = inner
        self._observation = observation
        self._established = False

    @property
    def __class__(self):
        # Azure includes this name in its original aggregate exception diagnostics.
        return self._inner.__class__

    def __getattr__(self, name):
        member = getattr(self._inner, name)
        if name not in ("get_token", "get_token_info"):
            return member

        def observed(*args, **kwargs):
            observations = getattr(self._observation, "links", None)
            try:
                token = member(*args, **kwargs)
            except Exception as exc:
                if observations is not None:
                    observations.append(_credential_observation(
                        self._inner, exc, established=self._established,
                    ))
                raise
            self._established = True
            if observations is not None:
                observations.append(_credential_observation(self._inner))
            return token

        return observed


class _SharedTokenCredential:
    """Singleflight token acquisition by interface, scopes and complete options.

    Azure blob clients already share a bearer policy; this proxy additionally
    coordinates concurrent acquisitions and preserves complete token identity.
    Refresh five minutes before expiry, or at ``refresh_on`` if earlier. Only
    typed transient causes of credential unavailability get up to three attempts
    with 1 s / 2 s backoff; managed identity additionally requires prior success.
    Authentication failures and unconfigured sources fail fast. Exhaustion
    suppresses retries for 30 s, never fresh acquisition. Concurrent waiters share
    their singleflight Future's exception; subsequent acquisitions never replay it.
    """

    def __init__(self, inner, *, attempts=_CREDENTIAL_ATTEMPTS):
        self._inner = inner
        self._tokens = {}
        self._token_lock = threading.Lock()
        self._inflight = {}
        self._retry_after = {}
        self._attempts = attempts
        self._observation = threading.local()
        self._authenticated = False
        from azure.identity import ChainedTokenCredential

        self._chain_size = 0
        if isinstance(inner, ChainedTokenCredential):
            # Mutate the private inner credential's tuple once, retaining Azure's
            # traversal and sticky-success behavior. Proxies observe typed errors
            # before its aggregate exception discards their types and causes.
            inner.credentials = tuple(
                _ObservedCredentialLink(link, self._observation)
                for link in inner.credentials
            )
            self._chain_size = len(inner.credentials)

    def enable_retries(self):
        self._attempts = _CREDENTIAL_ATTEMPTS

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def _get_token(self, method, scopes, kwargs):
        try:
            identity = (method, scopes, _token_request_identity(kwargs))
            hash(identity)
        except TypeError:
            # Opaque SDK options are valid inputs, just not safe cache keys.
            return self._acquire(method, scopes, kwargs)
        with self._token_lock:
            saved = self._tokens.get(identity)
            if saved is not None:
                refresh_at = saved.expires_on - 300
                refresh_on = getattr(saved, "refresh_on", None)
                if refresh_on is not None:
                    refresh_at = min(refresh_at, refresh_on)
                if time.time() < refresh_at:
                    return saved
            pending = self._inflight.get(identity)
            owner = pending is None
            if owner:
                pending = concurrent.futures.Future()
                self._inflight[identity] = pending
        if not owner:
            return pending.result()
        try:
            token = self._acquire(method, scopes, kwargs, identity)
            with self._token_lock:
                self._tokens[identity] = token
                self._retry_after.pop(identity, None)
            pending.set_result(token)
            return token
        except BaseException as exc:
            pending.set_exception(exc)
            raise
        finally:
            with self._token_lock:
                del self._inflight[identity]

    def _acquire(self, method, scopes, kwargs, identity=None):
        from azure.core.exceptions import ClientAuthenticationError
        from azure.identity import CredentialUnavailableError

        with self._token_lock:
            remaining = max(
                0.0, self._retry_after.get(identity, 0) - time.monotonic(),
            ) if identity is not None else 0.0
            attempts = 1 if remaining else self._attempts

        with _phase("cache.credential", credential=type(self._inner).__name__) as span:
            span.set_attribute("retry_suppressed", remaining > 0)
            span.set_attribute("retry_suppression_remaining_s", remaining)
            for attempt in range(1, attempts + 1):
                span.set_attribute("attempts", attempt)
                self._observation.links = []
                try:
                    token = getattr(self._inner, method)(*scopes, **kwargs)
                    self._authenticated = True
                    return token
                except ClientAuthenticationError as exc:
                    observations = self._observation.links or [
                        _credential_observation(
                            self._inner, exc, established=self._authenticated,
                        ),
                    ]
                    unavailable = isinstance(exc, CredentialUnavailableError)
                    complete_chain = (
                        self._chain_size > 0 and len(observations) == self._chain_size
                    )
                    transient = (
                        (unavailable or complete_chain)
                        and all(link.outcome in (
                            _CredentialOutcome.UNAVAILABLE, _CredentialOutcome.TRANSIENT,
                        ) for link in observations)
                        and any(link.outcome is _CredentialOutcome.TRANSIENT
                                for link in observations)
                    )
                    if not transient:
                        raise
                    if attempt == attempts:
                        if identity is not None and attempts > 1:
                            with self._token_lock:
                                self._retry_after[identity] = (
                                    time.monotonic() + _CREDENTIAL_COOLDOWN_S
                                )
                        raise
                    self._retry_notice(attempt, observations)
                finally:
                    self._observation.links = None
                # The singleflight future, not a held lock, owns this request.
                time.sleep(attempt)

    def _retry_notice(self, attempt, links):
        # A bare pool probe must not configure OTel just to report a retry.
        telemetry = sys.modules.get("_telemetry")
        if telemetry is None:
            return
        with contextlib.suppress(Exception):
            summary = ", ".join(
                f"{link.credential}:{link.error_type}/{link.cause_type or 'none'}"
                for link in links
            )
            telemetry.warn(
                f"[cache] credential unavailable; retry {attempt}/{self._attempts - 1} "
                f"in {attempt}s ({summary})"
            )
            for link in links:
                telemetry.event(
                    "cache.credential.retry", label="", key="",
                    credential=type(self._inner).__name__,
                    link_credential=link.credential, outcome=link.outcome.value,
                    attempt=attempt, delay_s=attempt,
                    error_type=link.error_type, cause_type=link.cause_type,
                )

    def get_token(self, *scopes, **kwargs):
        return self._get_token("get_token", scopes, kwargs)


class _SharedTokenInfoCredential(_SharedTokenCredential):
    """:class:`_SharedTokenCredential` for a credential that also offers ``get_token_info``
    (azure-core prefers it when present, so the proxy must expose it only then)."""

    def get_token_info(self, *scopes, **kwargs):
        return self._get_token("get_token_info", scopes, kwargs)


def _make_backend(*, attempts=_CREDENTIAL_ATTEMPTS) -> _BlobBackend | None:
    try:
        from azure.storage.blob import ContainerClient
    except ImportError:
        _log("azure-storage-blob not installed; cache disabled")
        return None

    account = os.environ.get("HARMONIC_CACHE_ACCOUNT") or _DEFAULT_ACCOUNT
    container = os.environ.get("HARMONIC_CACHE_CONTAINER") or _DEFAULT_CONTAINER
    account_url = f"https://{account}.blob.core.windows.net"
    sas = os.environ.get("HARMONIC_CACHE_SAS")
    if sas:
        return _BlobBackend(ContainerClient(
            account_url, container, credential=sas, max_single_get_size=_ARCHIVE_CACHE_MIN,
        ))
    from azure.identity import DefaultAzureCredential

    inner = DefaultAzureCredential()
    proxy = (
        _SharedTokenInfoCredential if hasattr(inner, "get_token_info") else _SharedTokenCredential
    )(inner, attempts=attempts)
    try:
        client = ContainerClient(
            account_url, container, credential=proxy, max_single_get_size=_ARCHIVE_CACHE_MIN,
        )
    except BaseException:
        with contextlib.suppress(Exception):
            proxy.close()
        raise
    return _BlobBackend(client, proxy)


_BACKEND_LOCK = threading.Lock()
# Created unset by :func:`prewarm`; set once its warming request has finished,
# failed or never started. ``None`` in a process that never prewarms.
_PREWARMED: threading.Event | None = None
# How long the first real cache call waits for an in-flight prewarm before
# opening its own connection. A healthy prewarm finishes in ~1.1 s, inside the
# ~2.7 s graph load, so this bound is met only by a stalled one; the cache
# verdict never depends on it.
_PREWARM_WAIT_S = 3.0
_PREWARM_JOIN_S = 2.0


def _backend() -> _BlobBackend | None:
    """Memoized ContainerClient with a shared expiry-aware token credential. Returns
    None when unconfigured / SDK absent, so the caller treats it as a miss. The
    first call's SDK import and client construction are ``cache.connect``.

    A :func:`prewarm` still in flight is waited for -- through its warming
    request, so this call reuses the connection it opened -- for at most
    :data:`_PREWARM_WAIT_S`; past that the caller proceeds on its own."""
    global _BACKEND
    warming = _PREWARMED
    if warming is not None:
        warming.wait(_PREWARM_WAIT_S)
    with _BACKEND_LOCK:
        if isinstance(_BACKEND, _Unset):
            with _phase("cache.connect"):
                _BACKEND = _make_backend()
    return _BACKEND


_PREWARM_THREAD = "cache-prewarm"


def _farm_leaf_execution() -> bool:
    """Is this process a farm worker's leaf execution?

    The pool appends ``farm.execution=<id>`` to ``OTEL_RESOURCE_ATTRIBUTES`` for
    exactly the build it runs as a leaf (solidworks-pool
    ``farm_worker.leaf_resource_attributes``); a submitter, a developer seat, a
    ``doit list`` or a test never carries it. Parsed by exact key, as the SDK's
    ``OTELResourceDetector`` does."""
    for entry in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "").split(","):
        key, separator, value = entry.partition("=")
        if separator and key.strip() == "farm.execution" and value.strip():
            return True
    return False


def _warm() -> None:
    """The prewarm thread's body: build the client, then HEAD a blob that never
    exists so the token is fetched and the pooled TLS connection is open.

    Speculative, so it never decides anything: a client that cannot be built
    (SDK absent, constructor error) leaves ``_BACKEND`` unset for the real call.
    A storage HEAD error can still leave a token-authenticated client reusable."""
    global _BACKEND
    warming = _PREWARMED
    backend = None
    published = False
    try:
        with contextlib.suppress(Exception), _phase("cache.prewarm"):
            with _BACKEND_LOCK:
                if not isinstance(_BACKEND, _Unset):
                    return
            import azure.storage.blob  # noqa: F401 -- absent SDK: stay unset

            with _phase("cache.connect"):
                backend = _make_backend(attempts=1)
            if backend is None:
                return
            # Keep the speculative credential private while acquiring its token.
            # A real probe past the wait bound must never queue behind this HEAD.
            from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

            try:
                backend.exists("prewarm")
            except HttpResponseError as exc:
                if (
                    isinstance(exc, ClientAuthenticationError)
                    or backend._credential is None
                    or not backend._credential._authenticated
                ):
                    raise
            with _BACKEND_LOCK:
                if isinstance(_BACKEND, _Unset):
                    # Once public, future real refreshes get the normal retry policy.
                    backend.enable_credential_retries()
                    _BACKEND = backend
                    published = True
    finally:
        if backend is not None and not published:
            with contextlib.suppress(Exception):
                backend.close()
        if warming is not None:
            warming.set()


def _join_prewarm(thread: threading.Thread) -> None:
    """At exit, give an in-flight prewarm a bounded moment to end its spans before
    telemetry's own exit hook (registered earlier, so run later) closes the
    exporters. A prewarm still running after that is abandoned: it decides nothing."""
    thread.join(_PREWARM_JOIN_S)


def prewarm() -> threading.Thread | None:
    """Open the cache connection on a daemon thread while the caller does other work.

    A farm leaf's first ``cache.probe`` measured 0.91 / 0.91 / 0.88 s on three
    part leaves (2026-09-28, 6a67cdf43): ``cache.connect`` (azure SDK import +
    client) 0.53 s and a cold ``cache.download`` 0.31-0.34 s -- of which the token
    was 0.03-0.04 s and the rest the first TLS connection; the same GET on the
    warm connection (``cache.reprobe``) took 0.07 s. None of that depends on the
    task, and the leaf spends ~2.7 s loading its graph first.

    Only a farm leaf execution in ``rw`` mode -- the one process certain to probe
    next -- starts it (:func:`_farm_leaf_execution`); every other graph load
    (``doit list``, ``check:*``, a submitter, a test) stays off Azure. Best-effort
    end to end: a thread that cannot start is simply no prewarm."""
    global _PREWARMED
    if not (writable() and _farm_leaf_execution()):
        return None
    _PREWARMED = threading.Event()
    thread = threading.Thread(target=_warm, name=_PREWARM_THREAD, daemon=True)
    try:
        thread.start()
    except RuntimeError:
        _PREWARMED.set()
        return None
    atexit.register(_join_prewarm, thread)
    return thread


def probe(key: str) -> bool | None:
    """Is ``key`` present in the backend, WITHOUT downloading it? True/False when the
    cache is reachable, None when disabled / unconfigured / unreachable. For the
    cache_status diagnostic -- never raises, never mutates anything."""
    if not enabled():
        return None
    try:
        backend = _backend()
        if backend is None:
            return None
        return backend.exists(key)
    except Exception as exc:  # noqa: BLE001
        _log(f"probe error for {key[:12]}: {exc!r}")
        return None


class RestoreLocked(RuntimeError):
    """A cached build for ``key`` EXISTS but could not be written over the seat's
    outputs: a share lock (Windows ``PermissionError``) -- SolidWorks still holds
    the document from an earlier session (a crashed/killed build, or a human with
    the artefact open in the UI).

    Deliberately NOT swallowed like other restore errors: "building locally" here
    would succeed (SolidWorks can save over its own resident document) and mint a
    fresh ``.execution`` token no other seat can reproduce -- forking every
    dependent's cache key off the fleet's (2026-09-17, farm worker 4:
    ``measuring_stick`` behind the open top-assembly drawing). The caller must
    release the seat's documents and retry, or fail loud."""

    def __init__(self, label: str, key: str, cause: OSError) -> None:
        self.label = label
        self.key = key
        self.cause = cause
        super().__init__(
            f"{label}: cached build {key[:12]} exists but its outputs are "
            f"share-locked on this seat ({cause.filename!s}) -- SolidWorks still "
            "holds the document; close it (release the seat) and retry"
        )


def _note_hit_provenance(label: str, key: str) -> None:
    """Record a HIT and, when it lands on a key this seat never published, decide
    how loudly to say so (see :func:`_cannot_publish_reason`).

    Best-effort like every other provenance sink, and deliberately its OWN guard:
    this runs after the outputs are already on disk, so an exception escaping into
    ``restore``'s handler would demote a served HIT to "building locally" -- which
    mints a fresh ``.execution`` token and forks every dependent's cache key off
    the fleet's. Bookkeeping must never cost a restore."""
    try:
        prev = last_stored_key(label)
        if not prev or prev == key:
            _record("restore_hit", label, key)
            return
        expected = _cannot_publish_reason()
        if expected:
            _debug_log(f"{label}: HIT under {key[:12]}; last published here was "
                       f"{prev[:12]}, but this process never publishes "
                       f"({expected}) -- expected, not store-skip-on-hit drift")
        else:
            _warn(f"{label}: HIT under {key[:12]} but this seat last published "
                  f"{prev[:12]} -- store-skip-on-hit drift; {key[:12]} is NOT being "
                  f"re-published from here")
        tags: dict[str, bool | str] = {"drift_expected": bool(expected)}
        if expected:
            tags["drift_reason"] = expected
        _event("cache.hit_drift", label, key, prev_key=prev[:12], **tags)
        _record("restore_hit_drift", label, key, **tags)
    except Exception as exc:  # noqa: BLE001 -- a HIT already succeeded; keep it
        _debug_log(f"{label}: drift check skipped ({exc!r})")


def restore(key: str, outputs: list[Path], label: str) -> bool:
    """Try to download+unpack a cached build for ``key``. Return True on a HIT (the
    outputs are now on disk and the COM build can be skipped), False on a miss or
    any error (caller falls through to the real build). Raises
    :class:`RestoreLocked` -- the ONE non-swallowed failure -- when the HIT's
    extraction is refused by a share lock on an output (see the class).

    On a HIT under a key this seat never PUBLISHED (its sidecar holds a different
    one), WARN -- the seat is serving an artefact it should have stored itself: the
    store-skip-on-hit drift from issue #73. A process that structurally cannot
    publish (a ``--executor farm`` submitter, a ``ro`` seat; see
    :func:`_cannot_publish_reason`) hits foreign keys as its NORMAL path, so there
    the same condition is logged at debug instead of warned. Only the console
    severity moves: every outcome, demoted drift included (tagged
    ``drift_expected`` plus the reason), is appended to cache.jsonl."""
    if not enabled():
        return False
    blob = None
    try:
        backend = _backend()
        if backend is None:
            return False
        with _phase("cache.fetch") as fetch:
            blob = backend.get(key)
            fetch.set_attribute("found", blob is not None)
            size = _archive_size(blob) if blob is not None else 0
            fetch.set_attribute("archive_bytes", size)
        if blob is None:
            # A miss is routine on changed inputs. Keep it at DEBUG so the default
            # warning-level build stays concise; the span event and cache.jsonl retain
            # full diagnostics for backtracing why the local build ran.
            _debug_log(f"miss  {label} ({key[:12]}) -> building locally")
            _event("cache.miss", label, key)
            with _phase("cache.record", event="restore_miss"):
                _record("restore_miss", label, key)
            return False
        try:
            with _phase("cache.unpack", bytes=size):
                _unpack(blob, outputs)
        except PermissionError as exc:
            locked = RestoreLocked(label, key, exc)
            _warn(str(locked))
            _event("cache.restore_locked", label, key, path=str(exc.filename))
            _record("restore_locked", label, key)
            raise locked from exc
        _log(f"HIT   {label} ({key[:12]}) -> skipped COM build")
        _event("cache.hit", label, key)
        _note_hit_provenance(label, key)
        return True
    except RestoreLocked:
        raise
    except Exception as exc:  # noqa: BLE001 -- cache must never break a build
        _warn(f"restore error for {label}: {exc!r} -- building locally")
        _event("cache.restore_error", label, key)
        _record("restore_error", label, key)
        return False
    finally:
        if blob is not None:
            blob.close()


def store(
    key: str, outputs: list[Path], label: str, *, refresh_label: str | None = None
) -> str:
    """Publish canonical outputs, or CAS a previously snapshotted root/alias."""
    authority = refresh_label or label
    refreshing = forced_refresh(authority) is not None
    replace_etag = None
    if refreshing:
        if (authority, key) not in _REFRESH_ETAGS:
            raise RuntimeError(f"{authority}: forced cache refresh was not probed before work")
        replace_etag = _REFRESH_ETAGS[(authority, key)]
    return require_refresh_store(
        authority, _store(key, outputs, label, replace_etag=replace_etag)
    )


def _store(
    key: str, outputs: list[Path], label: str, *, replace_etag: str | None = None
) -> str:
    """Pack+upload the just-built outputs under ``key``. No-op unless mode=rw.
    Absent-entry push failures remain soft; a present canonical entry returns
    ``lost`` for mandatory caller adoption. Records the event in cache.jsonl and
    stamps the per-label "last published key" sidecar so a later
    HIT under a shifted key can be flagged as drift.

    RETURNS the outcome (``stored``/``lost``/``skip``/``empty``/``error``/``off``).
    A lost publication REQUIRES the action to adopt the entire canonical archive;
    the caller's ``cache.store`` phase span carries the outcome so a publication,
    a deliberate read-only skip and a failed upload remain distinguishable."""
    if not writable():
        if enabled():  # ro: pulled but deliberately won't publish -- note the skip
            _record("store_skip", label, key)
            return "skip"
        return "off"
    blob = None
    try:
        backend = _backend()
        if backend is None:
            return "off"
        present = [o for o in outputs if o.exists()]
        if not present:
            _warn(f"nothing to store for {label} (no outputs on disk)")
            _event("cache.store_empty", label, key)
            _record("store_empty", label, key)
            return "empty"
        with _phase("cache.pack", outputs=len(present)) as pack:
            blob = _pack(present)
            size = _archive_size(blob)
            pack.set_attribute("bytes", size)
        with _phase("cache.upload", bytes=size):
            try:
                backend.put(key, blob, replace_etag=replace_etag)
            except Exception:
                # Includes ambiguous success/timeouts and InvalidBlockList after
                # a competing commit discarded our staged blocks. The canonical
                # postcondition, not an Azure error-code taxonomy, decides loss.
                if not backend.exists(key):
                    raise
                _log(f"lost  {label} ({key[:12]}): canonical entry present")
                _event("cache.store_lost", label, key)
                _record("store_lost", label, key)
                return "lost"
        _log(f"store {label} ({key[:12]})")
        _event("cache.store", label, key)
        _save_stored_key(label, key)
        _record("store", label, key)
        return "stored"
    except Exception as exc:  # noqa: BLE001
        _warn(f"store error for {label}: {exc!r}")
        _event("cache.store_error", label, key)
        _record("store_error", label, key)
        return "error"
    finally:
        if blob is not None:
            blob.close()
