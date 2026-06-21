r"""Remote build-artefact cache for the COM (SolidWorks) tasks.

The expensive tasks in this pipeline -- ``part:<stem>`` / ``assembly:<stem>`` --
drive a live SolidWorks seat (a part is ~20 s, a full assembly ~500 s). Their
outputs are a pure function of *hashed inputs*: a part's ``.SLDPRT`` is determined
by its build script + helper closure + the cad/config files it reads; an
assembly's ``.SLDASM`` by its recipe files + the content of the referenced part
artefacts. ``dodo.py`` already computes exactly those input sets as each task's
``file_dep``.

This module turns that into a *shared* cache: key a task by the content hash of
its ``file_dep`` (repo-relative, parsed-YAML-normalised -- identical across
machines and worktrees), pack its outputs into one ``.tar.gz``, and push/pull it
through an object store. A machine WITHOUT a SolidWorks seat can then download a
prebuilt ``.SLDPRT``/``.SLDASM`` for an unchanged input set instead of failing on
COM; a CI builder with a seat populates the cache for everyone else.

Design notes / invariants:

* **Content-addressed, input-keyed.** We key by INPUTS, never by output bytes.
  SolidWorks files embed timestamps, so two builds of the same inputs are not
  byte-identical -- that's fine: any valid build for those inputs is acceptable,
  and the first one to land wins the key. So the cache never needs reproducible
  output, only a deterministic input hash.

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
  ``off`` (disabled). It comes from ``HARMONIC_CACHE_MODE`` or, failing that, a
  gitignored one-line ``.harmonic-cache-mode`` file at the repo root, or finally
  ``_DEFAULT_MODE`` = ``rw``: both dev seats publish what they build by default,
  so neither rebuilds an artefact the other already produced. Drop a seat to
  ``ro``/``off`` via the file or env. A miss -- or an unauthorised push (RBAC
  denies a machine without the data-plane role) -- is never fatal: it falls
  through to the real build.

* **Fail-soft.** Any backend error (network, creds, corrupt archive) logs a
  warning and is treated as a miss / no-op push. The cache can only make a build
  FASTER, never make a correct build FAIL.

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

import hashlib
import io
import os
import sys
import tarfile
import time
from pathlib import Path

# Bump to invalidate EVERY cached entry pipeline-wide (e.g. after a change to the
# packed OUTPUT set, the pack format, or a build-logic change not captured by any
# file_dep). Combine with the salt for toolchain-version busting.
#   2 -- part entries gained the .STL sidecar; assembly entries gained the channel
#        stretch parts + top-level gallery/BOM. Old epoch-1 blobs are incomplete
#        for the current pipeline, so they MUST NOT be served (codex review).
_CACHE_EPOCH = "2"

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

# A machine's role (off | ro | rw). Read from HARMONIC_CACHE_MODE, else this
# gitignored one-line file at the repo root, else _DEFAULT_MODE. Default is rw:
# both dev seats build and PUBLISH, so each other's artefacts -- including private
# / experimental ones (content-addressed, so a unique input set => a unique key
# that never collides with the canonical cache) -- are pulled instead of rebuilt.
# Set the file/env to `ro` (pull only) or `off` (disabled) to downgrade a seat.
_MODE_FILE = REPO_ROOT / ".harmonic-cache-mode"
_DEFAULT_MODE = "rw"


def _log(msg: str) -> None:
    print(f"[cache] {msg}", file=sys.stderr, flush=True)


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


def cache_key(file_deps: list[str], digest_one) -> str:
    """Content hash of a task's ``file_dep`` set -> the cache key.

    ``digest_one(path) -> hex`` is dodo's per-file content digest
    (``ContentChecker._digest``: raw md5 for binaries, PARSED-yaml md5 for configs),
    passed in so the cache and the doit staleness check fold each file identically
    -- a comment-only YAML edit must not change the key, exactly as it must not
    invalidate the file_dep.

    Each file is tagged by its REPO-RELATIVE path (not absolute, unlike
    ``_digest_files``) so the key is identical across machines and worktrees.
    """
    salt = os.environ.get("HARMONIC_CACHE_SALT") or _DEFAULT_SALT
    h = hashlib.sha256()
    h.update(f"epoch={_CACHE_EPOCH}\0salt={salt}\0".encode())
    for path in sorted(file_deps, key=lambda p: _rel(Path(p))):
        rel = _rel(Path(path))
        try:
            content = digest_one(path)
        except OSError:
            content = "<missing>"
        h.update(f"{rel}\0{content}\0".encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Pack / unpack -- one gzip tar of a task's outputs, paths stored repo-relative
# --------------------------------------------------------------------------- #
def _pack(outputs: list[Path]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for out in outputs:
            if out.exists():
                tar.add(str(out), arcname=_rel(out))
    return buf.getvalue()


def _unpack(blob: bytes) -> None:
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            # A cache archive may ONLY write build outputs, all under cad/out/.
            # Enforcing that here blocks path traversal AND -- since any principal
            # with blob write access could poison a valid key -- stops a hostile
            # archive from overwriting tracked SOURCE like cad/scripts/*.py that a
            # later doit task would then execute (codex review). Reject links too.
            if member.islnk() or member.issym():
                raise RuntimeError(f"link member not allowed in cache archive: {member.name}")
            dest = (REPO_ROOT / member.name).resolve()
            try:
                dest.relative_to(_CACHE_OUTPUT_ROOT)
            except ValueError:
                raise RuntimeError(f"cache archive member escapes cad/out/: {member.name}")
        tar.extractall(REPO_ROOT)
        # tar.add recorded the BUILDER's mtimes; refresh restored files to now so a
        # pulled native part/assembly is never OLDER than a developer's pre-existing
        # derived export -- export_models.part_stl_stale compares mtimes, and a stale-
        # looking native would wrongly skip regeneration and ship old geometry (codex
        # review). Best-effort: a utime failure must not fail a restore.
        now = time.time()
        for member in members:
            if not member.isreg():
                continue
            try:
                os.utime((REPO_ROOT / member.name).resolve(), (now, now))
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Backend -- Azure Blob container over HTTPS (443)
# --------------------------------------------------------------------------- #
class _BlobBackend:
    """One Azure Blob container of content-addressed ``<key>.tar.gz`` entries.

    Retention/LRU is server-side (account last-access tracking + a
    delete-after-N-days lifecycle rule), so a HIT needs no client-side touch -- a
    download updates last-access-time on its own.
    """

    def __init__(self, container_client):
        self._cc = container_client

    def _name(self, key: str) -> str:
        # Shard by the first 2 hex chars (virtual prefix) to avoid one giant listing.
        return f"{key[:2]}/{key}.tar.gz"

    def get(self, key: str) -> bytes | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return self._cc.get_blob_client(self._name(key)).download_blob().readall()
        except ResourceNotFoundError:
            return None

    def put(self, key: str, blob: bytes) -> None:
        # Content-addressed: any concurrent writer stores identical bytes, so
        # overwrite is a harmless no-op (last-writer-wins). A blob upload commits
        # atomically, so a concurrent reader never observes a partial entry.
        self._cc.get_blob_client(self._name(key)).upload_blob(blob, overwrite=True)


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #
def _mode() -> str:
    env = os.environ.get("HARMONIC_CACHE_MODE")
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


_UNSET = object()
_BACKEND = _UNSET


def _make_backend():
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
        return _BlobBackend(ContainerClient(account_url, container, credential=sas))
    from azure.identity import DefaultAzureCredential
    return _BlobBackend(ContainerClient(account_url, container,
                                        credential=DefaultAzureCredential()))


def _backend():
    """Memoized ContainerClient (one credential handshake per process). Returns
    None when unconfigured / SDK absent, so the caller treats it as a miss."""
    global _BACKEND
    if _BACKEND is _UNSET:
        _BACKEND = _make_backend()
    return _BACKEND


def restore(key: str, outputs: list[Path], label: str) -> bool:
    """Try to download+unpack a cached build for ``key``. Return True on a HIT (the
    outputs are now on disk and the COM build can be skipped), False on a miss or
    any error (caller falls through to the real build). Never raises."""
    if not enabled():
        return False
    try:
        backend = _backend()
        if backend is None:
            return False
        blob = backend.get(key)
        if blob is None:
            _log(f"miss  {label} ({key[:12]})")
            return False
        _unpack(blob)
        _log(f"HIT   {label} ({key[:12]}) -> skipped COM build")
        return True
    except Exception as exc:  # noqa: BLE001 -- cache must never break a build
        _log(f"restore error for {label}: {exc!r} -- building locally")
        return False


def store(key: str, outputs: list[Path], label: str) -> None:
    """Pack+upload the just-built outputs under ``key``. No-op unless mode=rw.
    Swallows every error -- a failed push must not fail the build."""
    if not writable():
        return
    try:
        backend = _backend()
        if backend is None:
            return
        present = [o for o in outputs if o.exists()]
        if not present:
            _log(f"nothing to store for {label} (no outputs on disk)")
            return
        backend.put(key, _pack(present))
        _log(f"store {label} ({key[:12]})")
    except Exception as exc:  # noqa: BLE001
        _log(f"store error for {label}: {exc!r} -- continuing")
