# Harmonic analyzer video companion

Six engineerguy videos share an interactive view of the CAD-exported analyzer.
The original YouTube player sits in the model area's lower-right corner. While
a video plays, the 3D view follows a hand-authored shot table for that video;
drag, scroll or change a control to explore (orbit, pan, zoom, turn the crank,
set the twenty channels). **Follow the video** hands the view back. Compact
mode keeps the same visible player and its audio.

Website workstream status lives on the
[Harmonic Analyzer project](https://github.com/users/pedropaulovc/projects/1).
Design notes are in [`DESIGN.md`](DESIGN.md).

## Run locally

```sh
npm --prefix web ci
npm --prefix web run fetch-model          # GLB from the pinned release
npm --prefix web run dev
```

`fetch-model` downloads only `gltf/ha-harmonic-analyzer.glb` out of the release
zip named by `MODEL_RELEASE` in `scripts/fetch-model.mjs` (HTTP range requests,
about 150 MB), deduplicates and Meshopt-compresses it losslessly
(`scripts/optimize-model.mjs`) and writes the gitignored
`public/models/ha-harmonic-analyzer.glb`. Pass a path to use a local export
instead: `npm --prefix web run fetch-model -- ../cad/out/gltf/ha-harmonic-analyzer.glb`.
Without a model the page still loads, solves the mechanism and shows the force
readout, with a visible message.

Routes accept a slug or the YouTube ID; `t` opens at a time in seconds:

| Page | Query |
|---|---|
| Intro / History | `?video=intro-history` |
| Synthesis | `?video=synthesis` |
| Analysis | `?video=analysis` |
| Operation | `?video=operation` |
| Machine spin | `?video=machine-spin` |
| Rocker arms | `?video=rocker-arms&t=300` |

Checks: `npm --prefix web run build` (strict `tsc`, then Vite) and
`npm --prefix web test` (deployment, chunked-transport and optimizer tests).
Look at the result in a browser too: a joint driven on the wrong axis
typechecks perfectly.

## Shot tables

`content/tracks/<slug>.json` says what the 3D view shows while each video
plays; `content/cameras.json` names reusable cameras. A track has `presets`
(twenty channel amplitudes and cam phases) and contiguous `shots`, one per line:

```json
{"start":12.5,"end":19,"mode":"follow","camera":"synthesis-1","crankTurns":[0,2],"preset":"zero","setup":{"gearing":"medium-medium"}}
```

- `follow` interpolates linearly from start to end values: camera (position,
  orientation, `fov`, off-centre `principal` point) towards `cameraEnd`,
  `crankTurns`, `preset` towards `presetEnd`, and any `setupEnd` fields.
  `hold` freezes the previous follow shot's end state.
- A camera is a name from `cameras.json` or `{position, target, up?, fov, principal?}`
  in CAD machine metres; `principal` is a fraction of the view.
- `setup` overrides `MechanismInput` defaults (`gearing`, `magnification`,
  `counterHeightM`, `coneSwingRad`, `pinionCamRad`, `wireFixtureOffsetM`, …).
- `tiles` splits the 1920×1080 frame into several views (`rect` in video
  pixels, optional `mirror`); each tile inherits the shot's fields.
- `"review": "unverified"` marks rows nobody has checked against the footage;
  an optional `note` says what a row is meant to show.

To author shots, open `?video=<slug>&edit=1`. The editor scrubs the YouTube
video, lets you pick a named camera or orbit to frame one, set crank turns and
the channel preset, and copies a shot row to paste into the JSON (Vite reloads
it). It is a separate chunk, loaded only with `edit=1`. The tables were
converted once from the earlier fitted source tracks by
`scripts/convert-source-tracks.py` (in Git history).

## Mechanism data

`src/mechanics-data.ts` holds the dimensions, pivots, spring catalogue values
and chain paths that `src/mechanics.ts`, `src/magnifier.ts` and `src/scene.ts`
use. Regenerate it from the current CAD (pure spec/geometry modules and
`cad/config/`, no SolidWorks) after a CAD change:

```sh
uv run --frozen python web/scripts/export-mechanism.py --glb /path/to/raw/ha-harmonic-analyzer.glb
```

`--glb` is optional; it prints how far the CAD rest datums are from the GLB's
node transforms. To move to a new release, change `MODEL_RELEASE`, regenerate
`mechanics-data.ts`, and fix any renamed part in `src/bindings.ts` (unresolved
bindings are listed in the browser console and under the controls).

The video embeds use the official YouTube IFrame API. The site does not host or
redistribute the footage.

## Deployment

Cloudflare Workers Builds uses native Git integration (not a GitHub deployment
token or OIDC). Both Workers use repository root **`web`**, install with
`npm ci`, and build with **`npm run build:deploy`**. Wrangler is pinned to
**4.148.0** in the lockfile. The build produces **`web/dist/`** at base path `/`,
including `/deployment.json` with the exact `WORKERS_CI_COMMIT_SHA` and
`WORKERS_CI_BRANCH`. Local builds fall back to the current Git commit/branch;
detached checkouts must supply both native-build variables.
The npm `prebuild:deploy` lifecycle runs `npm run test:deployments` first, so the
deployment identity, reporting and cleanup regression tests gate native builds.

| Deployment | Account name / workers.dev subdomain | Account ID | Worker | Native deploy command |
|---|---|---|---|---|
| Production (`main` only) | `harmonicanalyzer-com-prod` | `6b2522c874d4613dc2bf47bd2ce521a2` | `harmonicanalyzer-com-prod` | `npm run deploy` |
| PPE (branch previews, all PR base branches) | `harmonicanalyzer-com-ppe` | `c8769c20b85cd2857afe22ef2f9a0a21` | `harmonicanalyzer-com-ppe` | `npm run deploy:preview` |

Worker service names match their account names and account subdomains; account
IDs are unchanged. Production's primary URL is `https://harmonicanalyzer.com`.
The companion origin remains
`https://harmonicanalyzer-com-prod.harmonicanalyzer-com-prod.workers.dev`.
The PPE service origin is
`https://harmonicanalyzer-com-ppe.harmonicanalyzer-com-ppe.workers.dev`;
branch Preview API URLs use
`https://<preview-slug>-harmonicanalyzer-com-ppe.harmonicanalyzer-com-ppe.workers.dev`.
GitHub's `production` and `web-preview` environment variables
`CLOUDFLARE_WORKERS_SUBDOMAIN` must match the respective account subdomains above.

Production `wrangler.jsonc` declares the apex as a Workers Custom Domain so
future deployments retain the binding. Worker logs, invocation logs and traces
are enabled with 100% head sampling. Static assets served without invoking the
Worker do not produce Worker invocation telemetry.

Cloudflare Web Analytics is enabled for `harmonicanalyzer.com` in the production
account, with automatic edge injection and full RUM (`lite: false`). Its beacon
collects page visits and Web Vitals; no duplicate script is installed in the app,
and PPE/local pages are not included. Manage this zone-owned setting in
Cloudflare **Web Analytics**, not Wrangler. Verify the injected
`static.cloudflareinsights.com/beacon.min.js` and successful `/cdn-cgi/rum`
requests in a browser; dashboard aggregates can lag collection.

PPE uses `wrangler preview --config wrangler.ppe.jsonc --name "$WORKERS_CI_BRANCH"`
for both its default branch and non-production branch build command. It never
publishes the PPE production Worker with `wrangler deploy`. Production
non-production branch builds must be **disabled in the dashboard**.
Native Git build watch paths use Cloudflare's `web/*` wildcard on both PPE
triggers (main and non-main) and production. GitHub workflow path filters use
`web/**`; these are separate matching systems. GitHub environment reporting and
PPE preview cleanup do not perform deployments. The sole GitHub cleanup token
belongs to the PPE environment/account, never the production account.

Native previews cover **same-repository PR branches**, including drafts and PRs
targeting any base branch, when `web/**` changes. Valid unsupported fork PRs are
**explicitly skipped**, not failed or represented as deployed; the job skips
before credentials, checkout or API calls. Malformed event payloads still fail.
Untrusted fork code never enters a credentialed native build. GitHub's PPE
environment records the actual Cloudflare Preview API URL, not a guessed branch
slug, and normally reports success only after `/deployment.json` matches the
exact PR head SHA and raw branch name. If native watch paths skipped a
non-`web/**` push, an older manifest commit is accepted only when the raw branch
matches and GitHub's root `web` subtree object SHA is identical for that commit
and the requested head. The successful deployment records the **actual manifest
SHA**, with `requestedSha` and `identityProof: "matching-web-tree"` in its
payload; it never mislabels old bytes as the new head. Changed-web mismatches
still fail within the bounded wait. An arbitrary HTTP 200 is not deployment
proof. Production
reporting uses the same exact-commit or proven web-tree-equivalence rule;
the standalone `wait` helper remains exact-SHA-only.
Native deployment is **push-only**: opening or reopening a PR does not trigger
a new Cloudflare build. After a closed PR's Preview has been deleted, reopening
that PR requires a **new push touching `web/`** to recreate it. A reopened PR
with no Preview fails reporting immediately with that instruction. A newly
opened PR still allows the normal bounded 20-minute native startup wait before
reporting a native-build-log/new-web-push diagnostic. Neither path attempts a
build through an additional PPE build-control token.

The PPE cleanup credential is used only to read Preview metadata and delete PPE
Previews. The accepted cleanup contract is **branch-only**: PR closure deletes
the closed branch's Preview resource and branch URL, releases its Preview quota,
and inactivates the GitHub deployment record, unless another open PR shares
that branch. **Immutable deployment URLs deliberately remain public** under the
accepted contract because of Cloudflare's beta behavior documented in
[issue 15945](https://github.com/cloudflare/workers-sdk/issues/15945). A live
cleanup probe confirmed that the Preview resource disappeared and the branch
URL returned 404 while an older immutable deployment URL still served its
deployed bytes. Branch cleanup does not promise full public-URL revocation.
Closed-PR cleanup issues the delete immediately, without the orphan grace
period; branch-URL removal then propagates asynchronously through Cloudflare.
A successful delete is not an instant data-plane 404: a second disposable probe
initially returned 200 after deletion and subsequently returned 404 within the
bounded propagation observation.

Cleanup retries still inactivate matching GitHub deployment records when the
Preview resource and Git branch are already gone. The helper decodes GitHub's
string-wrapped GraphQL deployment payload to recover the recorded branch, and
uses paginated bulk `latestStatus` data to skip already-inactive records without
a separate status-history request for every deployment.
Unreadable payloads are left unchanged without inferring ownership from their
Git refs. Valid later records are still cleaned up; afterward the run fails
with an aggregate error naming the unreadable deployment IDs. GitHub API and
status-write failures propagate immediately rather than being treated as
unreadable payloads.

An hourly reconciler catches late builds and orphaned Preview resources. It
preserves new Previews without a PR for their first **30 minutes**, allowing a
branch push to precede PR creation; otherwise orphan **Preview-resource**
cleanup occurs within **90 minutes of Preview creation**, excluding scheduler
delays. This bound does not imply immutable deployment URL revocation. Missing or
malformed API `created_on` timestamps stop reconciliation instead of risking
premature deletion. Open PR branches are preserved. The deployment lifecycle
helper can also be used manually:

```sh
node web/scripts/cloudflare-deployments.mjs preview
node web/scripts/cloudflare-deployments.mjs production
node web/scripts/cloudflare-deployments.mjs list
node web/scripts/cloudflare-deployments.mjs reconcile
node web/scripts/cloudflare-deployments.mjs cleanup 'raw/branch-name'
node web/scripts/cloudflare-deployments.mjs wait URL FULL_COMMIT_SHA [BRANCH [TIMEOUT_SECONDS]]
```

`wait` accepts an application base URL with or without a trailing slash and
preserves any non-root base path when resolving `deployment.json`.

`list`, `reconcile`, and cleanup require `CLOUDFLARE_CLEANUP_API_TOKEN` plus
the fixed PPE `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_WORKER_NAME`, and
`CLOUDFLARE_WORKERS_SUBDOMAIN` environment values. `cleanup` and `reconcile`
also require `GH_TOKEN` and `GITHUB_REPOSITORY` to protect open PR branches.
The low-level `delete RAW_BRANCH` command deliberately bypasses that open-PR
protection; reserve it for intentional preview-deletion smoke checks.

The Wrangler files explicitly pin account and Worker identity. Both use the
static asset binding and a lossless asset streaming Worker, with no storage,
secrets, unrelated bindings or scheduled triggers. Production also declares its
apex custom domain and observability settings; PPE has no custom domains.
`keep_vars` preserves dashboard variables.
PPE explicitly has a `previews` block to enable noninteractive deployments
without copying production resource settings. It enables Preview console logs
for structured `deployment-asset-stream-abort` diagnostics only; automatic
invocation logs are disabled. Wrangler 4.148.0 retains `assets` (including
`ASSETS` and `run_worker_first`) at the top level, not under `previews`.

The optimized v49 model is about **47 MB**, over the
[25 MiB per-file Workers Assets limit](https://developers.cloudflare.com/workers/platform/limits/#static-assets)
on both Free and Paid plans. `build:deploy` runs `fetch-model` (the release zip
on GitHub is a **build-time input only**; the deployed site makes no requests to
GitHub), then Vite. After Vite builds, every runtime file larger than 25 MiB
gets a lossless gzip representation and an identity fallback. Each
representation is split into ordered **24 MiB** pieces under
`dist/deployment-assets/`. The generated, ignored `.vite/deployment-assets.json`
records original URLs, decoded lengths and SHA-256 values, plus each
representation's encoded length, digest and ordered pieces. The build verifies
the pieces, reconstructed representations and exact decoded original bytes
before deployment.

For original chunked-asset URLs, the Worker selects gzip or identity from
`request.cf.clientAcceptEncoding`, not Cloudflare's normalized edge header.
Missing original Cloudflare metadata selects identity; non-Cloudflare requests
use their raw header.

**Native Preview limitation:** measured Cloudflare metadata drops `q` values and
wildcard entries before the Worker. Worker-first routing did not restore them.
The parser respects qualities and returns 406 when both codings are refused
only where raw/preserved metadata is available; it cannot recover preferences
discarded by the platform. This is not a deployed quality-negotiation guarantee.

GET/HEAD responses include the
selected representation's length and ETag, `Vary: Accept-Encoding`, and
`Content-Encoding: gzip` when selected. It sequentially streams immutable pieces
through a fixed-length stream, without runtime compression or a full-file buffer.
Initial missing chunks return 502; later missing/short chunks error the response
stream rather than silently completing a truncated 200. Ordinary files pass through
to `ASSETS` unchanged, including their native conditional-request behavior.
Each immutable `ASSETS` piece is requested with `Accept-Encoding: identity` and
must return 200 with a body. If a Content-Length header is visible it must match
the manifest, but the native binding can omit that header even though its public
HTTP endpoint supplies it. Piece length and SHA-256 checks, plus exact ordered
whole-file SHA reconstruction, are mandatory **producer/predeploy** checks.
Runtime bodies pipe directly into one native `FixedLengthStream`, which enforces
the **actual total byte length** without per-packet JavaScript processing or
materialized arrays. This relies on Cloudflare's immutable `ASSETS` producer for
individual pieces; there is no separate per-piece runtime byte/SHA scan.
Abort diagnostics identify the original URL, active piece path, and error
without body bytes. Header/status refusals include actual response status,
visible length, encoding and expected length.
Chunked routes also honor strong/weak `If-None-Match` and `*` with a 304 before
fetching any pieces, so cache revalidation does not redownload the full asset.
Reconstructed routes retain `Cache-Control: no-transform` so Cloudflare does
not recompress either the precompressed gzip or identity response: under
Cloudflare's default `Content-Encoding: zstd`, a 45 MB module failed partway
in a native headed browser while an identity override completed. The transport
uses Cloudflare's
[documented no-transform directive](https://developers.cloudflare.com/speed/optimization/content/compression/#content-length-header-handling)
and native stream piping (no per-buffer JavaScript), after a no-transform-only
deployment still hit `exceededResources` on concurrent loads.
Both configurations explicitly use `run_worker_first: false`, Cloudflare's
asset-first default. Ordinary uploaded files (including the transport pieces)
bypass the Worker; these static requests are
[free and unlimited](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/).
The producer deletes oversized originals only after writing all their pieces,
so requests to those original missing URLs fall through to the Worker and use
the manifest transport, regardless of their directory. Keep
`not_found_handling` at its default `none`: no SPA or custom 404 asset fallback
is configured to swallow these missing-original requests.
Reconstructed original requests still invoke the Worker and retain its
[plan limits](https://developers.cloudflare.com/workers/platform/limits/#daily-requests),
including **100,000 requests/day on Workers Free**; they are not unlimited
static delivery. No visitor/cost estimate is implied by the routing change.
No R2 storage or runtime external origin is required.

From a clean clone, the equivalent commands are:

```sh
npm --prefix web ci
npm --prefix web run build:deploy
# Authenticated local use only; native Builds supplies Cloudflare credentials.
npm --prefix web run deploy          # main -> production
npm --prefix web run deploy:preview  # actual branch -> PPE preview
```

Deployment never publishes the raw CAD export.
