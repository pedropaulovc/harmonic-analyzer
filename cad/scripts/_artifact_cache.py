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
  a stale hit. ``HARMONIC_CACHE_SALT`` (e.g. ``sw2024-sp3``) is mixed into every
  key; bump it -- or the ``_CACHE_EPOCH`` constant -- to invalidate the whole cache.

* **Read/write roles.** ``HARMONIC_CACHE_MODE`` = ``ro`` (dev: pull only),
  ``rw`` (builder: pull + push), or ``off`` (default: disabled, pipeline behaves
  exactly as before). A miss is never fatal -- it falls through to the real build.

* **Fail-soft.** Any backend error (network, creds, corrupt archive) logs a
  warning and is treated as a miss / no-op push. The cache can only make a build
  FASTER, never make a correct build FAIL.

Backend: a shared **directory** (``HARMONIC_CACHE_DIR``) -- in production an Azure
Files SMB share mounted on every builder (see ``scripts/azure/``). Zero extra
deps: a lookup is a file read, a push an atomic ``tmp + replace``. A cache entry
is one ``<key>.tar.gz`` under a 2-hex shard dir.

Eviction is age-based and EXTERNAL (Azure Files has no native lifecycle policy):
``scripts/azure/cleanup_build_cache.ps1`` deletes entries not written for 7 days.
To make that LRU rather than FIFO, a HIT *touches* the entry's mtime, so an
artefact still in active use is kept alive even when its inputs never change.
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
# pack format or a build-logic change not captured by any file_dep). Combine with
# HARMONIC_CACHE_SALT for toolchain-version busting.
_CACHE_EPOCH = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    salt = os.environ.get("HARMONIC_CACHE_SALT", "")
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
        for member in tar.getmembers():
            # Defensive: never let an archive escape the repo root (path traversal).
            dest = (REPO_ROOT / member.name).resolve()
            if not str(dest).startswith(str(REPO_ROOT)):
                raise RuntimeError(f"unsafe path in cache archive: {member.name}")
        tar.extractall(REPO_ROOT)


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #
class _DirBackend:
    """Shared-directory cache (NFS/SMB/local). Atomic publish via tmp + replace."""

    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        # Shard by the first 2 hex chars to avoid one giant flat dir.
        return self.root / key[:2] / f"{key}.tar.gz"

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        if not p.exists():
            return None
        blob = p.read_bytes()
        # Touch on HIT so the external age-based cleanup is LRU, not FIFO: an
        # artefact still in active use stays alive even if its inputs never change
        # (cleanup deletes by last-write time). Best-effort -- a read-only mount or
        # a clock skew must never fail a restore.
        try:
            now = time.time()
            os.utime(p, (now, now))
        except OSError:
            pass
        return blob

    def put(self, key: str, blob: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tar.gz.tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, p)  # atomic publish -- a concurrent reader sees all-or-nothing


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #
def _mode() -> str:
    return os.environ.get("HARMONIC_CACHE_MODE", "off").lower()


def enabled() -> bool:
    return _mode() in ("ro", "rw")


def writable() -> bool:
    return _mode() == "rw"


def _backend():
    root = os.environ.get("HARMONIC_CACHE_DIR")
    if not root:
        _log("HARMONIC_CACHE_DIR unset; cache disabled")
        return None
    return _DirBackend(Path(root))


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
