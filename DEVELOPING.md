# Developing — local workflow notes

Practical, machine-local development notes that don't belong in `AGENTS.md`
(orientation) or the per-topic policy docs. Right now: the remote build cache.

## Remote build-artifact cache

The COM/SolidWorks tasks (`part:<stem>`, `assembly:<stem>`) are the slow part of
the pipeline — a part is ~20 s, a full assembly ~500 s. Their outputs are a pure
function of their hashed inputs, so a shared cache lets one machine **download a
prebuilt `.SLDPRT`/`.SLDASM`/`.STL`** for an unchanged input set instead of
driving SolidWorks. A seat-less machine can pull; a builder pulls **and**
publishes. Implementation: `cad/scripts/_artifact_cache.py`.

### TL;DR — it just works

Both dev seats are pre-authorized and the default role is `rw`, so **a clean
checkout needs zero setup**: it pulls what the other seat built and publishes
what it builds. You only touch anything to *opt out* or to bust the cache after a
SolidWorks upgrade.

### How keys work

Each task is keyed by a SHA-256 of its `file_dep` set, folded **exactly** like
doit's staleness check (`ContentChecker._digest`: raw bytes for binaries,
parsed-YAML for configs), so a cache hit and "doit up-to-date" always agree and a
comment-only YAML edit busts neither. Paths are tagged **repo-relative**, so the
key is identical across machines and worktrees.

Private/experimental work is cached too, with no namespacing: a unique input set
yields a unique key, so an experiment is stored under its own key and never
collides with the canonical artefacts. Two seats share a blob only when their
inputs are byte-identical.

### Backend: Azure Blob over HTTPS (443)

One content-addressed `<key>.tar.gz` blob per task in container `buildcache` on
storage account `stswbuildcache07aba2`. Reached over **443** — works from any
network, including ISPs that block SMB/445 (e.g. Comcast), with no VPN or mounted
drive. Auth is **keyless** via `DefaultAzureCredential`:

- **dev box** → your `az login` token. Run `az login` once.
- **builder (`vm-solidworks`)** → its system-assigned managed identity
  (granted *Storage Blob Data Contributor*); nothing to log in.

A machine without the data-plane RBAC role is **fail-soft**: its push is denied
and the build proceeds normally (a miss/error never fails a build).

### Roles and how to set them

Role is one of `off` | `ro` (pull only) | `rw` (pull + push). Resolved in order:

1. `HARMONIC_CACHE_MODE` env var, if set
2. `.harmonic-cache-mode` — a **gitignored one-line file at the repo root**
   (`C:\src\harmonic-analyzer\.harmonic-cache-mode`), contents just `off`/`ro`/`rw`
3. `_DEFAULT_MODE` = **`rw`** (the fallback)

`.harmonic-cache-mode` is **per-clone** (not global) and never committed. To
downgrade a seat — e.g. a collaborator without Azure access — drop the file at the
repo root:

```powershell
Set-Content .harmonic-cache-mode off    # disable (no pull, no push)
Set-Content .harmonic-cache-mode ro     # pull only
```

Or, equivalently, without a file: `$env:HARMONIC_CACHE_MODE = 'off'`.

Check the resolved role:

```powershell
uv run python -c "import sys; sys.path.insert(0,'cad/scripts'); import _artifact_cache as c; print(c._mode())"
```

### Defaults you can override

Account, container, and salt are committed constants in `_artifact_cache.py`
(`_DEFAULT_ACCOUNT`, `_DEFAULT_CONTAINER`, `_DEFAULT_SALT`). Each is overridable by
its matching `HARMONIC_CACHE_*` env var (CI, tests, an unlanded salt bump). None
is a secret — the account is RBAC-gated with public blob access off.

### Busting the cache (salt / epoch)

The toolchain (SolidWorks major version, COM adapter) is **not** in any
`file_dep`, so a SW upgrade that changes geometry would otherwise serve a stale
hit. Mix-ins guard this:

- **`_DEFAULT_SALT`** (e.g. `sw2024-sp3`) — bump it in the **same commit** that
  adapts to a new SolidWorks version, so the cache busts in lockstep with the
  code. All seats must agree on the salt or they never share hits.
- **`_CACHE_EPOCH`** — bump to invalidate *every* entry pipeline-wide (e.g. a
  pack-format change).

### Retention — server-side, no job

Account **last-access-time tracking** + a lifecycle rule
`delete daysAfterLastAccessTimeGreaterThan: 7`. A restore is a blob *read*, which
bumps last-access, so an artefact in active use keeps itself alive (true LRU). No
scheduled cleanup task, no client-side touch.

### Provisioning (one-time, operator)

`scripts/azure/provision_build_cache.ps1` is idempotent and does everything:
creates the container, enables last-access tracking, sets the lifecycle policy,
and grants `Storage Blob Data Contributor` to the signed-in operator and the
`vm-solidworks` managed identity. Run it once with `az` logged into the Dev/Test
subscription.

### Caveats

- The `rw` default means *any* clone attempts a push. Safe (RBAC denies an
  unauthorized seat, fail-soft), but an unauthorized seat pays a credential-probe
  delay per build — set `.harmonic-cache-mode off` there.
- Cross-machine hit rate depends on identical input **bytes**. Without a
  `.gitattributes` normalizing line endings, a `.py` re-materialized with
  different EOLs hashes differently → a miss (never a wrong artefact). Add
  `*.py text eol=lf` if hit rate disappoints.
