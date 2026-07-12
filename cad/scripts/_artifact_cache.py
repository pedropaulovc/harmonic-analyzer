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
  ``off`` (disabled). It comes from ``HARMONIC_REMOTE_CACHE_MODE`` or, failing
  that, a gitignored one-line ``.harmonic-remote-cache-mode`` file at the repo
  root, or finally
  ``_DEFAULT_MODE`` = ``rw``: both dev seats publish what they build by default,
  so neither rebuilds an artefact the other already produced. Drop a seat to
  ``ro``/``off`` via the file or env. A miss -- or an unauthorised push (RBAC
  denies a machine without the data-plane role) -- is never fatal: it falls
  through to the real build.

* **Fail-soft.** Any backend error (network, creds, corrupt archive) logs a
  warning and is treated as a miss / no-op push. The cache can only make a build
  FASTER, never make a correct build FAIL.

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
  seat can serve a key it never published) directly. ``cache_status`` (a doit task)
  prints all of the above per part/assembly in one command.

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
import json
import os
import tarfile
import time
from pathlib import Path

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
_CACHE_EPOCH = "3"

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


def _log(msg: str) -> None:
    import _telemetry  # local import: keeps the cache usable even if telemetry is absent

    _telemetry.info(f"[cache] {msg}")


def _warn(msg: str) -> None:
    """A cache MISS / drift / soft error is a WARNING, not routine info: it is the
    signal a debugger looks for when asking 'why did this rebuild?' -- it should
    stand out at ``!!`` severity (and in the OTel logs at WARNING) rather than blend
    into the ``--`` progress stream."""
    import _telemetry

    _telemetry.warn(f"[cache] {msg}")


def _event(name: str, label: str, key: str, **extra) -> None:
    """Record the cache outcome as a span EVENT on the active task span (best-effort).

    The restore/store run INSIDE the ``task part:``/``assembly:`` span dodo opens, so
    a hit/miss/store shows up ON the trace timeline (with the key + label) -- making a
    cache miss backtraceable from the trace, not only from cache.jsonl / the console.
    No-op when no span is recording (e.g. cache_status), so callers never guard."""
    import _telemetry

    _telemetry.event(name, label=label, key=key[:12], **extra)


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


def key_inputs(file_deps: list[str], digest_one) -> tuple[str, list[tuple[str, str]]]:
    """``(key, [(relpath, digest), ...])`` -- the cache key AND the per-file
    provenance that produced it, sorted by repo-relative path.

    ``digest_one(path) -> hex`` is dodo's per-file content digest
    (``ContentChecker._digest``: raw md5 for binaries, PARSED-yaml md5 for configs),
    passed in so the cache and the doit staleness check fold each file identically
    -- a comment-only YAML edit must not change the key, exactly as it must not
    invalidate the file_dep. Each file is tagged by its REPO-RELATIVE path (not
    absolute, unlike ``_digest_files``) so the key is identical across machines and
    worktrees. The input list is what ``HARMONIC_CACHE_DEBUG`` / ``cache_status``
    print so a key shift is a readable per-file diff (issue #73)."""
    h = hashlib.sha256()
    h.update(f"epoch={_CACHE_EPOCH}\0salt={_salt()}\0".encode())
    pairs: list[tuple[str, str]] = []
    for path in sorted(file_deps, key=lambda p: _rel(Path(p))):
        rel = _rel(Path(path))
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
    key, pairs = key_inputs(file_deps, digest_one)
    if label:
        _KEY_INPUTS[(label, key)] = pairs
    if _debug():
        head = label or "?"
        _log(f"key provenance {head} (epoch={_CACHE_EPOCH} salt={_salt()}):")
        for rel, content in pairs:
            _log(f"    {content}  {rel}")
        _log(f"  => {head} key {key}")
    return key


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
        # derived export -- the mtime-based downstream freshness guards (render_offline
        # and cut_release's SCENE_JSON check) would otherwise see a stale-looking native
        # and wrongly skip regeneration / ship old geometry (codex review). (export
        # itself now keys staleness on the churn-immune recipe digest, not mtime, and
        # re-stamps its outputs current after a successful run so those guards stay
        # truthful.) Best-effort: a utime failure must not fail a restore.
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

    def exists(self, key: str) -> bool:
        # Presence check without downloading the blob -- the cache_status diagnostic
        # probes every key, so a HEAD (exists) instead of a GET (download) keeps it cheap.
        return self._cc.get_blob_client(self._name(key)).exists()

    def put(self, key: str, blob: bytes) -> None:
        # Content-addressed: any concurrent writer stores identical bytes, so
        # overwrite is a harmless no-op (last-writer-wins). A blob upload commits
        # atomically, so a concurrent reader never observes a partial entry.
        self._cc.get_blob_client(self._name(key)).upload_blob(blob, overwrite=True)


# --------------------------------------------------------------------------- #
# Public surface
# --------------------------------------------------------------------------- #
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
def _record(event: str, label: str, key: str) -> None:
    """Append one cache event to cache.jsonl, including readable provenance for
    miss/drift outcomes so a historical key shift remains explainable even after
    the last-published sidecar advances to the newly built key (issue #255)."""
    try:
        _REPORTS.mkdir(parents=True, exist_ok=True)
        rec = {"ts": round(time.time(), 3), "event": event, "label": label,
               "key": key, "epoch": _CACHE_EPOCH, "salt": _salt()}
        if event in ("restore_miss", "restore_hit_drift"):
            pairs = _KEY_INPUTS.get((label, key))
            if pairs is not None:
                rec["inputs"] = [{"path": path, "digest": digest} for path, digest in pairs]
            previous = _stored_provenance(label)
            if previous and previous["key"] != key:
                rec["previous_key"] = previous["key"]
                rec["previous_inputs"] = [
                    {"path": path, "digest": digest}
                    for path, digest in previous["inputs"]
                ]
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


def _make_backend() -> _BlobBackend | None:
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


def _backend() -> _BlobBackend | None:
    """Memoized ContainerClient (one credential handshake per process). Returns
    None when unconfigured / SDK absent, so the caller treats it as a miss."""
    global _BACKEND
    if isinstance(_BACKEND, _Unset):
        _BACKEND = _make_backend()
    return _BACKEND


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


def restore(key: str, outputs: list[Path], label: str) -> bool:
    """Try to download+unpack a cached build for ``key``. Return True on a HIT (the
    outputs are now on disk and the COM build can be skipped), False on a miss or
    any error (caller falls through to the real build). Never raises.

    On a HIT, if this seat last PUBLISHED a different key for ``label`` (its sidecar
    differs), WARN: the seat is serving a key it never stored -- the
    store-skip-on-hit drift from issue #73. Every outcome is appended to cache.jsonl."""
    if not enabled():
        return False
    try:
        backend = _backend()
        if backend is None:
            return False
        blob = backend.get(key)
        if blob is None:
            # A MISS is why a COM build is about to run -- surface it at WARNING so
            # it stands out when backtracing an unexpected rebuild, and drop a span
            # event so the trace shows the miss right before the build it triggered.
            _warn(f"miss  {label} ({key[:12]}) -> building locally")
            _event("cache.miss", label, key)
            _record("restore_miss", label, key)
            return False
        _unpack(blob)
        _log(f"HIT   {label} ({key[:12]}) -> skipped COM build")
        _event("cache.hit", label, key)
        prev = last_stored_key(label)
        if prev and prev != key:
            _warn(f"{label}: HIT under {key[:12]} but this seat last published "
                  f"{prev[:12]} -- store-skip-on-hit drift; {key[:12]} is NOT being "
                  f"re-published from here")
            _event("cache.hit_drift", label, key, prev_key=prev[:12])
            _record("restore_hit_drift", label, key)
        else:
            _record("restore_hit", label, key)
        return True
    except Exception as exc:  # noqa: BLE001 -- cache must never break a build
        _warn(f"restore error for {label}: {exc!r} -- building locally")
        _event("cache.restore_error", label, key)
        _record("restore_error", label, key)
        return False


def store(key: str, outputs: list[Path], label: str) -> None:
    """Pack+upload the just-built outputs under ``key``. No-op unless mode=rw.
    Swallows every error -- a failed push must not fail the build. Records the event
    in cache.jsonl and stamps the per-label "last published key" sidecar so a later
    HIT under a shifted key can be flagged as drift."""
    if not writable():
        if enabled():  # ro: pulled but deliberately won't publish -- note the skip
            _record("store_skip", label, key)
        return
    try:
        backend = _backend()
        if backend is None:
            return
        present = [o for o in outputs if o.exists()]
        if not present:
            _warn(f"nothing to store for {label} (no outputs on disk)")
            _event("cache.store_empty", label, key)
            _record("store_empty", label, key)
            return
        backend.put(key, _pack(present))
        _log(f"store {label} ({key[:12]})")
        _event("cache.store", label, key)
        _save_stored_key(label, key)
        _record("store", label, key)
    except Exception as exc:  # noqa: BLE001
        _warn(f"store error for {label}: {exc!r} -- continuing")
        _event("cache.store_error", label, key)
        _record("store_error", label, key)
