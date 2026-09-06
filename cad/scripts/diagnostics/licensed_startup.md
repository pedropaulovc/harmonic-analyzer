# Licensed startup: CEF environment comparison

On September 6, 2026, a normal licensed shortcut launch displayed “CEF for
SOLIDWORKS is not installed” even though the registered 147.0.34792.0 installation
and DLLs existed. The same launch succeeded after restoring four absent Windows
variables in the launcher child only. No registry or global environment value
was changed by that comparison.

## Reproduce one variant

Reserve the SolidWorks seat and ensure no session or connector launch is active.
Run **one** mode, not both automatically:

```powershell
uv run python cad/scripts/diagnostics/probe_licensed_startup.py inherited
uv run python cad/scripts/diagnostics/probe_licensed_startup.py native-defaults
```

The script acquires the machine-global seat itself. Both modes use the same
installed, platform-generated `SOLIDWORKS Design.lnk` via `os.startfile`.
The diagnostic intentionally bypasses the production launch helper after
resolving and validating that exact shortcut: automatic production environment
repair would otherwise silently repair the inherited control too. This is the
experimental baseline, not a recovery fallback.
`native-defaults` fills only absent values from native 64-bit HKLM:

| Child variable | Registry value |
|---|---|
| `PROCESSOR_ARCHITECTURE` | Session Manager/Environment `PROCESSOR_ARCHITECTURE` |
| `CommonProgramFiles` | CurrentVersion `CommonFilesDir` |
| `CommonProgramW6432` | CurrentVersion `CommonW6432Dir` |
| `CommonProgramFiles(x86)` | CurrentVersion `CommonFilesDir (x86)` |

Existing values, including differently cased names, are preserved. Native-default
scope is the observed 64-bit AMD64 installation; other architectures fail
explicitly. The report includes the allowlisted values, registry provenance,
actual child receipt, selected shortcut, process identities, loaded CEF module
paths/versions, and proof that the full parent environment remained unchanged.

Each invocation performs one launch. A sustained visible `#32770` dialog must
have a disabled owner in the same process before it counts as a blocking modal.
Its native text and cropped screenshot are retained; it is not dismissed.
Blank/transient notifications with enabled owners are not installation failures.
When the connector reports ready, a 20-second-bounded child attaches to the
existing instance and reads only `GetProcessID` and `RevisionNumber`. Native
identity/readiness is checked again afterward. Non-ready states exit nonzero;
no retry, kill, macro, model open/save, installer, or settings change follows.

The timeout leaves startup running. Arrange any subsequent observation or
recovery explicitly; do not run the next variant against an existing process.

## Recorded comparison

Times below are America/Los_Angeles. Evidence directories were owned by
`C:/src/ha-perf-vsta-probe/cad/out/reports/vsta-snapshot/`.

| Variant | Observed result | Evidence directory |
|---|---|---|
| Inherited, before repair | 13:19:17: CEF modal, SW PID 60040 | `licensed-baseline-bk5vqjpg` |
| Inherited, after approved matching MSI repair | 13:23:53: same modal, SW PID 52076 | `licensed-baseline-afjuv23w` |
| Four native defaults, same post-repair installation | 13:32:49: main window and CEF; 13:35:05: native attach passed, SW PID 37136, revision 34.3.0 | `licensed-environment-668u6rfk`, `licensed-baseline-iahcniqk`, `existing-readiness-k165o6pj` |

The successful child used `AMD64`, `C:/Program Files/Common Files` for both
native common-directory variables, and `C:/Program Files (x86)/Common Files`.
All four were absent before and remained absent in its parent afterward.
The running SolidWorks process loaded:

- `SWCEFComWrapper.dll` 147.0.34792.0
- `libcef.dll` 147.0.9+g2812b73+chromium-147.0.7727.49

Both came from `C:/Program Files/Common Files/SOLIDWORKS Shared/swcef`.
The repair completed successfully but did not remove the error in the inherited
environment; its log is under the root repository's
`cad/out/reports/cef-repair-66f92b7b7a2e44d4b2f2f7b79e663bbd/msi-repair.log`.

The original monitor stopped the successful launch at an untitled transient
notification because it classified every visible `#32770` as a modal. That was
a diagnostic assumption, not a SolidWorks failure. Same-PID observation resumed
without another launch and confirmed readiness. This tracked version uses the
sustained owner-disabled test above; offline tests cover that correction. Its
consolidated CLI has not been run natively again: the evidence is from the three
bounded predecessors retained at the report paths, not a claimed fourth launch.

This establishes an observed startup difference from the four-variable child
environment as a group. It does **not** isolate which variable is necessary,
prove a missing CEF installation, establish every launch mode, or imply that C#
VSTA runs in-process. The earlier macro-run modal text was not captured and is
not identified as this CEF message.

Microsoft documents default parent-to-child environment inheritance and explicit
child environment blocks in [Environment Variables](https://learn.microsoft.com/en-us/windows/win32/procthread/environment-variables).
Native readiness uses the documented
[GetProcessID](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~GetProcessID.html)
and [RevisionNumber](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~RevisionNumber.html)
methods. Neither a compiler success nor a successful shortcut invocation is
treated as native readiness.
