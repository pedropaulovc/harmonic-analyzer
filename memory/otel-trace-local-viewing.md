---
name: otel-trace-local-viewing
description: How to view PR #76 OpenTelemetry traces+logs locally (Aspire native, or Jaeger) and run bounded traced builds without rebuilding the whole model
metadata:
  type: project
---

Verifying the PR #76 telemetry spine (`cad/scripts/_telemetry.py`) end-to-end on a real build.

**Docker is IMPOSSIBLE on this seat — don't retry it.** This machine is an Azure `Standard_NV6ads_A10_v5` (AMD-based GPU VM). Azure nested virtualization is Intel-only, so the WSL2/Hyper-V VM that Docker Desktop's Linux engine needs cannot boot — Docker Desktop fails with "Virtualization support not detected" even though WSL features are enabled, `hypervisorlaunchtype=Auto`, and firmware VT is on (`Win32_ComputerSystem.Model = "Virtual Machine"`, `VMMonitorModeExtensions=False`). The only fix is resizing to an Intel VM, which loses the A10 GPU — not worth it. So **no Docker-based viewer** (Aspire-container, SigNoz, Tempo/Loki).

**The whole stack lives OUTSIDE this repo at `C:\src\otelcol\`** (a standalone sibling folder, its own git repo — deliberately NOT under harmonic-analyzer, since it's a generic local-observability tool, and it was moved out of the ephemeral gitignored `.tools/` which a `/m` worktree-reset nukes). The `*.ps1` launchers + `config.yaml` are self-locating (`$PSScriptRoot`), so the folder can move freely; the downloaded binaries + logs sit under gitignored `C:\src\otelcol\bin\`. Recreate the binaries on any seat with **`C:\src\otelcol\bootstrap.ps1`** (downloads dotnet runtime + Aspire + Jaeger + Collector, then `otelcol validate`s the config), then **`C:\src\otelcol\register-startup-tasks.ps1`** to (re)register the three `OTel-*` scheduled tasks (`OTel-Collector`/`OTel-Aspire`/`OTel-Jaeger`, start at logon).

**Preferred viewer = Aspire dashboard run NATIVELY (no Docker), showing logs+traces unified.** It's framework-dependent .NET, so: user-local ASP.NET Core runtime at `C:\src\otelcol\bin\dotnet` (installed via dot.net/v1/dotnet-install.ps1 `-Runtime aspnetcore -Channel 9.0 -InstallDir`), and the dashboard from NuGet `Aspire.Dashboard.Sdk.win-x64` unpacked to `C:\src\otelcol\bin\aspire\pkg\tools\`. **Launch with `C:\src\otelcol\start-aspire.ps1`** — UI `:18888`, OTLP/HTTP `:18890` (== spine default, so zero-env: no `OTEL_EXPORTER_OTLP_ENDPOINT` needed), OTLP/gRPC `:18889`. Two launch gotchas baked into that script: (1) `-WorkingDirectory` MUST be the exe dir or `wwwroot`/Blazor assets don't resolve → blank page; (2) `Dashboard__Frontend__AuthMode=Unsecured` (the `DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS` shorthand unsecures OTLP+API but NOT the browser frontend in 13.x). Aspire ingests OTLP logs too, so "see logs for a span" = Structured Logs tab (each row has a Trace link) or click a span in trace detail. In-memory; restart clears telemetry.

**Current routing = zero-env fan-out.** The **OpenTelemetry Collector** (`start-otelcol.ps1`, `config.yaml`) OWNS the spine's DEFAULT OTLP port `:18890`/`:18889`, so a plain build with NO env var lands there, and the collector duplicates every trace to BOTH Aspire (`:4319`/`:4320`) and Jaeger (`:4318`). Logs go to Aspire only (Jaeger 404s on `/v1/logs`). Aspire was moved off the default port to `:4319`/`:4320` to free `:18890` for the collector. Exporter type is `otlphttp/<name>` with `compression: none` (Aspire's OTLP/HTTP receiver can't decode gzip → 500).

**Fallback viewer = Jaeger (traces only).** Standalone Windows binary at `C:\src\otelcol\bin\jaeger\jaeger-2.19.0-windows-amd64\jaeger.exe` (gitignored, from bootstrap) — OTLP gRPC `:4317`, OTLP/HTTP `:4318`, UI `:16686`, in-memory, no args. To bypass the collector and point the spine straight at Jaeger: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`. Jaeger is **traces-only**: the spine's OTLP *log* export 404s on `/v1/logs` (harmless; logs still hit console + `cad/out/reports/telemetry/logs.jsonl`, correlatable by grepping `span_id`). `opentelemetry-exporter-otlp-proto-http` is installed (imported under `contextlib.suppress`, so a missing pkg would *silently* skip export — verify it's present).

**Bounded traced build (don't rebuild the world):** a plain `doit assembly:<stem>` drags the ENTIRE COM spine — PR #76 touched `_common.py`, which every part imports, so all ~50 parts + every prior assembly are stale, and `_spine_dep` makes each a hard `task_dep`. To trace just one assembly + a part, call `dodo._run([python, build_<x>.py], "label", log_stem=...)` directly under a `_telemetry.run_pipeline_span(...)` root: `_run` is the real harness launcher (opens `task <label>` span, injects `TRACEPARENT`, spawns subprocess), so the cross-process bridge is genuinely exercised without the spine. summing (13-component) full build ≈ 48s; slow parts like summing_lever ≈ 4min (many `param.dimension` spans).

**Network export is batched; local capture is immediate.** The console and
`traces.jsonl`/`logs.jsonl` processors remain `Simple*`, while only the OTLP
processors are `Batch*`. Before this split, the first synchronous log request
and first synchronous span request each stalled about 2.01 s against the local
collector: a five-process positive control averaged 4.49 s per one-log/one-span
process. Batched export plus parallel trace/log provider shutdown averaged 2.46 s
(45% lower), and long CAD processes hide most first-export latency behind COM
work. `_common.run_build` closes the root span before `_telemetry.shutdown()`;
shutdown drains both providers exactly once. A mock OTLP/HTTP collector test pins
that even a short process delivers both `/v1/logs` and `/v1/traces` before exit.

**JSONL records use kernel-atomic append.** Do not replace `_AtomicJsonlWriter`
with persistent text-mode append handles. Multiple build subprocesses share each
telemetry file, and two real `logs.jsonl` records were observed spliced/truncated
under `-n 4` contention while `traces.jsonl` happened to remain clean. On Windows
the writer opens an append-only `CreateFile` handle and sends each formatted JSON
record through one `WriteFile`; POSIX uses one `O_APPEND` write. An 8-process,
2,000-record stress test verifies parseability and exact identity coverage. This
also avoids a `filelock`-per-record workaround: measured locally at ~0.003 ms per
kernel append versus ~0.65 ms per lock+seek+write+flush record.

**Gotcha — orphans mean you killed it, not a real gap.** A build killed mid-run
(e.g. `timeout`) cannot finish its still-open `task`/`pipeline`/`build` parents,
so Jaeger may show children as orphan roots even though completed records were
exported. Let builds COMPLETE before auditing. A clean summing+knife_stay run =
73 spans, 1 root, 0 orphans; per-part component-insert + mate spans,
`gate.dof`/`gate.interference`/`gate.health` with per-component children. Note
Jaeger merges driver+subprocess into one `processID` (identical resource attrs),
so a processID-based cross-process detector reads 0 — the bridge is proven
instead by 1-root/0-orphan across the process boundary.

Relates to [[harmonic-analyzer-project]].
