# src/otelcol - local OpenTelemetry viewer stack

Native (no-Docker) local viewing for the pipeline's OpenTelemetry traces + logs.
This Azure AMD VM has no nested virtualization, so Docker Desktop's Linux engine
can't run here - every component below is a user-local process, no admin, no
container.

The pipeline spine (`cad/scripts/_telemetry.py`) exports OTLP to its default port
`:18890`. The **Collector** owns that port and fans every trace out to **both**
dashboards, so a plain `doit build` needs **no env var** to be fully traced.

```
build (spine)  --OTLP :18890/:18889-->  Collector  --+--> Aspire  :4319/:4320  (traces + logs)
                                                      +--> Jaeger  :4318/:4317  (traces only)
```

| Component | UI | OTLP in | Shows |
|-----------|----|---------|-------|
| Collector (`start-otelcol.ps1`) | - | :18890 HTTP / :18889 gRPC | fan-out only |
| Aspire (`start-aspire.ps1`) | http://localhost:18888 | :4319 HTTP / :4320 gRPC | traces **+ logs** (preferred) |
| Jaeger (`start-jaeger.ps1`) | http://localhost:16686 | :4318 HTTP / :4317 gRPC | traces only (fallback) |

## Setup

```powershell
# 1. download dotnet runtime + Aspire + Jaeger + Collector into ./bin (gitignored)
powershell -ExecutionPolicy Bypass -File src\otelcol\bootstrap.ps1

# 2. register the three auto-start tasks (start at logon; -AtStartup for boot-as-SYSTEM)
powershell -ExecutionPolicy Bypass -File src\otelcol\register-startup-tasks.ps1
```

`bootstrap.ps1` takes optional `-AspireVersion` / `-JaegerVersion` /
`-OtelcolVersion` / `-DotnetChannel` overrides. It validates `config.yaml`
against the freshly downloaded collector before finishing.

## Contents

- `bootstrap.ps1` - download all binaries into `./bin/`
- `register-startup-tasks.ps1` - (re)register the `Harmonic-OTel-*` scheduled tasks
- `start-otelcol.ps1` / `start-aspire.ps1` / `start-jaeger.ps1` - launchers (self-locating)
- `config.yaml` - Collector fan-out config (tracked)
- `bin/` - downloaded binaries + logs (gitignored)

Tracked scripts are location-independent (`$PSScriptRoot`), so the whole folder
can move with the repo. See `memory/otel-trace-local-viewing.md` for the launch
gotchas (Aspire working-dir / auth-mode, Jaeger-logs-404, orphan spans).
