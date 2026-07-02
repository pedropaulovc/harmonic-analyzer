---
name: otel-trace-local-viewing
description: How to view PR #76 OpenTelemetry traces+logs locally (Aspire native, or Jaeger) and run bounded traced builds without rebuilding the whole model
metadata:
  type: project
---

Verifying the PR #76 telemetry spine (`cad/scripts/_telemetry.py`) end-to-end on a real build.

**Docker is IMPOSSIBLE on this seat — don't retry it.** This machine is an Azure `Standard_NV6ads_A10_v5` (AMD-based GPU VM). Azure nested virtualization is Intel-only, so the WSL2/Hyper-V VM that Docker Desktop's Linux engine needs cannot boot — Docker Desktop fails with "Virtualization support not detected" even though WSL features are enabled, `hypervisorlaunchtype=Auto`, and firmware VT is on (`Win32_ComputerSystem.Model = "Virtual Machine"`, `VMMonitorModeExtensions=False`). The only fix is resizing to an Intel VM, which loses the A10 GPU — not worth it. So **no Docker-based viewer** (Aspire-container, SigNoz, Tempo/Loki).

**Preferred viewer = Aspire dashboard run NATIVELY (no Docker), showing logs+traces unified.** It's framework-dependent .NET, so: user-local ASP.NET Core runtime at `.tools/dotnet` (installed via dot.net/v1/dotnet-install.ps1 `-Runtime aspnetcore -Channel 9.0 -InstallDir`), and the dashboard from NuGet `Aspire.Dashboard.Sdk.win-x64` unpacked to `.tools/aspire/pkg/tools/`. **Launch with `.tools/start-aspire.ps1`** — UI `:18888`, OTLP/HTTP `:18890` (== spine default, so zero-env: no `OTEL_EXPORTER_OTLP_ENDPOINT` needed), OTLP/gRPC `:18889`. Two launch gotchas baked into that script: (1) `-WorkingDirectory` MUST be the exe dir or `wwwroot`/Blazor assets don't resolve → blank page; (2) `Dashboard__Frontend__AuthMode=Unsecured` (the `DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS` shorthand unsecures OTLP+API but NOT the browser frontend in 13.x). Aspire ingests OTLP logs too, so "see logs for a span" = Structured Logs tab (each row has a Trace link) or click a span in trace detail. In-memory; restart clears telemetry.

**Fallback viewer = Jaeger (traces only).** Standalone Windows binary at `.tools/jaeger/jaeger-2.19.0-windows-amd64/jaeger.exe` (untracked) — OTLP gRPC `:4317`, OTLP/HTTP `:4318`, UI `:16686`, in-memory, no args. Point the spine at it with `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`. Jaeger is **traces-only**: the spine's OTLP *log* export 404s on `/v1/logs` (harmless; logs still hit console + `cad/out/reports/telemetry/logs.jsonl`, correlatable by grepping `span_id`). `opentelemetry-exporter-otlp-proto-http` is installed (imported under `contextlib.suppress`, so a missing pkg would *silently* skip export — verify it's present).

**Bounded traced build (don't rebuild the world):** a plain `doit assembly:<stem>` drags the ENTIRE COM spine — PR #76 touched `_common.py`, which every part imports, so all ~50 parts + every prior assembly are stale, and `_spine_dep` makes each a hard `task_dep`. To trace just one assembly + a part, call `dodo._run([python, build_<x>.py], "label", log_stem=...)` directly under a `_telemetry.run_pipeline_span(...)` root: `_run` is the real harness launcher (opens `task <label>` span, injects `TRACEPARENT`, spawns subprocess), so the cross-process bridge is genuinely exercised without the spine. summing (13-component) full build ≈ 48s; slow parts like summing_lever ≈ 4min (many `param.dimension` spans).

**Gotcha — orphans mean you killed it, not a real gap.** The spine uses `SimpleSpanProcessor` (exports each span on its *end*). A build killed mid-run (e.g. `timeout`) flushes finished children but never their still-open `task`/`pipeline`/`build` parents → Jaeger shows children as orphan roots. Let builds COMPLETE before auditing. A clean summing+knife_stay run = 73 spans, 1 root, 0 orphans; per-part component-insert + mate spans, `gate.dof`/`gate.interference`/`gate.health` with per-component children. Note Jaeger merges driver+subprocess into one `processID` (identical resource attrs), so a processID-based cross-process detector reads 0 — the bridge is proven instead by 1-root/0-orphan across the process boundary.

**Auto-start at logon (2026-07-02).** Both viewers now come up automatically via
two Task Scheduler tasks — `Harmonic-OTel-Aspire` + `Harmonic-OTel-Jaeger` —
triggered `AtLogOn` of `pedro`, running each launcher hidden in the user session
(no admin/elevation, no Docker). Launchers: `.tools/start-aspire.ps1` (existing)
and `.tools/start-jaeger.ps1` (new). Registration is idempotent via
`.tools/register-startup-tasks.ps1` (`-Force` replaces; pass `-AtStartup` from an
ELEVATED shell to switch to a boot-time SYSTEM/session-0 trigger instead —
localhost ports stay reachable from the browser either way). Tasks use
`ExecutionTimeLimit 0` (don't kill the long-running dashboard) + `IgnoreNew`
(no duplicate on re-trigger). Smoke-test proven: after `Start-ScheduledTask`,
:18888/:18890 (Aspire) + :16686/:4318 (Jaeger) all listening, both processes up.
All of `.tools/` is gitignored (untracked, machine-local).

**Fan-out to BOTH viewers via a native OpenTelemetry Collector (2026-07-02).** To
push every event to Aspire AND Jaeger at once (no Docker), an `otelcol` v0.155.0
core binary (`.tools/otelcol/otelcol.exe`, ~195 MB, untracked) runs as a third
logon task `Harmonic-OTel-Collector` (`.tools/start-otelcol.ps1`,
`.tools/otelcol/config.yaml`). **The Collector OWNS the spine's default OTLP port
:18890** (HTTP) / :18889 (gRPC), so a plain build with **NO env var** exports to
it and it duplicates: traces → Aspire + Jaeger :4318; logs → Aspire ONLY (Jaeger
404s on `/v1/logs`). To free :18890 the **Aspire dashboard OTLP moved to :4319
(HTTP) / :4320 (gRPC)** — set in `start-aspire.ps1` via
`DOTNET_DASHBOARD_OTLP_HTTP_ENDPOINT_URL` / `DOTNET_DASHBOARD_OTLP_ENDPOINT_URL`;
Aspire UI stays :18888. Port map now: Collector-in 18890/18889 → Aspire 4319/4320
+ Jaeger 4318; UIs Aspire :18888, Jaeger :16686. **No `OTEL_EXPORTER_OTLP_ENDPOINT`
env var** — the zero-env `_resolve_otlp_endpoint` probe default (:18890) does the
routing (an earlier version pinned :4319 via a User env var; superseded — removed).
**Gotcha (cost 1 debug cycle):** the collector's `otlp_http` exporter defaults to
**gzip**, and Aspire's OTLP/HTTP receiver can't decode it → HTTP 500
`InvalidProtocolBufferException: invalid wire type` (Jaeger accepts gzip fine).
Fix = `compression: none` on the Aspire exporter only. Restart order when swapping
ports: stop both, start Aspire (grabs :4319), then collector (grabs :18890 →
:4319). To revert to Aspire-direct: point Aspire OTLP back to :18890 and stop the
collector task. Proven end-to-end: a zero-env span+log through the real spine
reached Jaeger's `/api/services` and the collector logged zero export failures.

Relates to [[harmonic-analyzer-project-decisions]].
