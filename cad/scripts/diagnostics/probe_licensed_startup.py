"""Compare one inherited/native-defaults licensed startup, without CAD changes.

Each invocation launches exactly once under the machine-global seat. It never
runs a macro, retries, repairs an installation, or changes global settings.
Only a fresh child environment may receive four absent native Windows defaults.
See licensed_startup.md for the observed CEF comparison and its limitations.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    "PROCESSOR_ARCHITECTURE": (
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        "PROCESSOR_ARCHITECTURE",
    ),
    "CommonProgramFiles": (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion",
        "CommonFilesDir",
    ),
    "CommonProgramW6432": (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion",
        "CommonW6432Dir",
    ),
    "CommonProgramFiles(x86)": (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion",
        "CommonFilesDir (x86)",
    ),
}
LAUNCH_GUARD_NAMES = (
    "sldworks.exe",
    "sldProcMon.exe",
    "swCefSubProc.exe",
    "sldsurfacing.exe",
    "SWXDesktopLauncher.exe",
    "CATSTART.exe",
    "ENOUSWCStart2.exe",
    "ENOUSWCStart3.exe",
    "ENOPLMCSAClient.exe",
    "SWConnectorTasksAgent.exe",
    "EdmServerV6.exe",
    "testConsole.exe",
)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_new_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def selected_environment(environment):
    normalized = {key.casefold(): value for key, value in environment.items()}
    return {key: normalized.get(key.casefold()) for key in SOURCES}


def child_environment(mode, parent, defaults):
    child = dict(parent)
    if mode == "inherited":
        return child, {}
    if mode != "native-defaults":
        raise ValueError(f"Unknown environment mode {mode!r}")
    if set(defaults) != set(SOURCES):
        raise ValueError("Native defaults must contain exactly the four allowed values")
    present = {key.casefold() for key in parent}
    changes = {
        key: value for key, value in defaults.items() if key.casefold() not in present
    }
    if any(not isinstance(value, str) or not value for value in changes.values()):
        raise ValueError("Native default values must be nonempty strings")
    child.update(changes)
    return child, changes


def native_defaults():
    import winreg

    if struct.calcsize("P") != 8:
        raise RuntimeError("This diagnostic requires native64 Python")
    values = {}
    for name, (key_path, value_name) in SOURCES.items():
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            key_path,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, kind = winreg.QueryValueEx(key, value_name)
        if kind != winreg.REG_SZ or not isinstance(value, str) or not value:
            raise ValueError(f"Expected nonempty native REG_SZ for {name}")
        if name == "PROCESSOR_ARCHITECTURE" and value != "AMD64":
            raise ValueError(
                f"Untested native architecture {value!r}; supported: AMD64"
            )
        if name != "PROCESSOR_ARCHITECTURE" and not Path(value).is_dir():
            raise ValueError(f"Native default directory is missing: {name}={value}")
        values[name] = value
    return values


def require_empty_inventory(rows):
    if rows:
        raise RuntimeError(
            f"Refusing launch with existing session/connector processes: {rows}"
        )


def blocking_candidate(row):
    return (
        row.get("class") == "#32770"
        and row.get("visible") is True
        and type(row.get("owner")) is int
        and row["owner"] != 0
        and row.get("owner_pid") == row.get("pid")
        and row.get("owner_enabled") is False
    )


@dataclass
class DialogTracker:
    sustain_s: float = 4
    since: dict = field(default_factory=dict)

    def blocking(self, rows, now):
        present = {}
        blocked = []
        for row in rows:
            if not blocking_candidate(row):
                continue
            identity = (
                row["pid"],
                row["hwnd"],
                row["owner"],
                row.get("title"),
                tuple(row.get("texts", ())),
            )
            started = self.since.get(identity, now)
            present[identity] = started
            if now - started >= self.sustain_s:
                blocked.append(row)
        self.since = present
        return blocked


def native_pid(rows, expected):
    pids = {row["pid"] for row in rows if row["name"].casefold() == "sldworks.exe"}
    if len(pids) > 1 or (expected is not None and pids != {expected}):
        raise RuntimeError(
            f"Unexpected native process identity: expected={expected}, observed={sorted(pids)}"
        )
    return next(iter(pids), expected)


def validate_attach(receipt, *, nonce, expected_pid):
    if receipt.get("nonce") != nonce:
        raise ValueError("Native receipt nonce mismatch")
    if type(receipt.get("pid")) is not int or receipt["pid"] != expected_pid:
        raise ValueError("Native receipt process identity mismatch")
    if not isinstance(receipt.get("revision"), str) or not receipt["revision"].strip():
        raise ValueError("Native receipt has no revision")
    return receipt


def observe_startup(
    *,
    read,
    attach,
    capture,
    now=time.monotonic,
    sleep=time.sleep,
    timeout_s=600,
    emit=None,
    audit=None,
):
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("Startup timeout must be finite and positive")
    result = audit if audit is not None else {}
    result.update(status="monitoring", observations=[])
    tracker = DialogTracker()
    expected = None
    deadline = now() + timeout_s
    previous = None
    while now() < deadline:
        row = read()
        signature = json.dumps(row, sort_keys=True)
        if signature != previous:
            result["observations"].append({"timestamp": stamp(), **row})
            if emit is not None:
                emit(row)
            previous = signature
        expected = native_pid(row["processes"], expected)
        blocked = tracker.blocking(row["windows"], now())
        if blocked:
            capture(blocked)
            result.update(status="modal_left_undismissed", blocking_dialogs=blocked)
            return result
        pending = any(blocking_candidate(window) for window in row["windows"])
        if expected is not None and row["state"] == "connected" and not pending:
            result["attach"] = attach(expected)
            final = read()
            result["final_observation"] = final
            native_pid(final["processes"], expected)
            if final["state"] != "connected" or any(
                blocking_candidate(window) for window in final["windows"]
            ):
                raise RuntimeError("Native readiness changed after bounded attach")
            result["status"] = "ready"
            return result
        sleep(min(2, max(0, deadline - now())))
    result["status"] = "startup_timeout_left_running"
    return result


def powershell_json(command):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return json.loads(result.stdout) if result.stdout.strip() else []


def process_inventory():
    names = ",".join(f"'{name}'" for name in LAUNCH_GUARD_NAMES)
    rows = powershell_json(
        f"Get-CimInstance Win32_Process | Where-Object {{ $_.Name -in @({names}) }} | "
        "Select-Object @{Name='name';Expression={$_.Name}},"
        "@{Name='pid';Expression={$_.ProcessId}},"
        "@{Name='parent_pid';Expression={$_.ParentProcessId}},"
        "@{Name='path';Expression={$_.ExecutablePath}} | ConvertTo-Json -Compress"
    )
    return rows if isinstance(rows, list) else [rows]


def native_windows(pids):
    import win32gui
    import win32process

    rows = []

    def visit(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        if pid not in pids:
            return
        owner = win32gui.GetWindow(hwnd, 4)
        row = {
            "hwnd": hwnd,
            "pid": pid,
            "class": win32gui.GetClassName(hwnd),
            "title": win32gui.GetWindowText(hwnd),
            "visible": True,
            "owner": owner,
            "owner_pid": win32process.GetWindowThreadProcessId(owner)[1]
            if owner
            else None,
            "owner_enabled": bool(win32gui.IsWindowEnabled(owner)) if owner else None,
            "rect": list(win32gui.GetWindowRect(hwnd)),
            "texts": [],
        }
        if row["class"] == "#32770":
            win32gui.EnumChildWindows(
                hwnd,
                lambda child, _: row["texts"].append(win32gui.GetWindowText(child)),
                None,
            )
        rows.append(row)

    win32gui.EnumWindows(visit, None)
    return rows


def os_snapshot():
    from solidworks_mcp.adapters import sw_recovery

    processes = process_inventory()
    return {
        "processes": processes,
        "windows": native_windows({row["pid"] for row in processes}),
        "state": sw_recovery.detect_state().value,
    }


def cef_modules(pid):
    if type(pid) is not int or pid <= 0:
        raise ValueError("Invalid native PID")
    return powershell_json(
        f"(Get-Process -Id {pid} -ErrorAction Stop).Modules | "
        "Where-Object { $_.ModuleName -in @('SWCEFComWrapper.dll','libcef.dll') } | "
        "Select-Object ModuleName,FileName,@{Name='Version';Expression={$_.FileVersionInfo.FileVersion}} | "
        "ConvertTo-Json -Compress"
    )


def child_command(kind, request, receipt):
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        kind,
        str(request),
        str(receipt),
    ]


def run_child(kind, request_path, receipt_path, *, environment=None, timeout_s=20):
    if receipt_path.exists():
        raise RuntimeError("Child receipt already exists; refusing stale evidence")
    completed = subprocess.run(
        child_command(kind, request_path, receipt_path),
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{kind} failed ({completed.returncode}): {completed.stderr}"
        )
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def child_main(kind, request_path, receipt_path):
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("Child requires the coordinated machine-global seat")
    if receipt_path.exists():
        raise RuntimeError("Refusing to overwrite a child receipt")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if kind == "launch-child":
        from solidworks_mcp.adapters import sw_install

        actual = selected_environment(os.environ)
        if actual != request["environment"]:
            raise RuntimeError("Child environment differs from the reviewed allowlist")
        strategy, shortcut = sw_install.resolve_launch_strategy()
        if (
            strategy is not sw_install.LaunchStrategy.PLATFORM_SHORTCUT
            or shortcut is None
        ):
            raise RuntimeError("No normal licensed platform shortcut")
        if shortcut.resolve() != Path(request["shortcut"]).resolve():
            raise RuntimeError("Licensed shortcut changed between parent and child")
        require_empty_inventory(process_inventory())
        # Experimental baseline: production launch helpers may repair the child
        # environment. Both variants must use the same raw licensed shortcut so
        # the inherited arm remains unchanged. This is not a recovery fallback.
        os.startfile(str(shortcut))
        write_new_json(
            receipt_path,
            {
                "nonce": request["nonce"],
                "pid": os.getpid(),
                "timestamp": stamp(),
                "shortcut": str(shortcut),
                "environment": actual,
            },
        )
        return
    import pythoncom
    import win32com.client
    from _common import _early_bound

    pythoncom.CoInitialize()
    try:
        app = _early_bound(
            win32com.client.GetActiveObject("SldWorks.Application"), "ISldWorks"
        )
        pid = int(app.GetProcessID())
        if pid != request["expected_pid"]:
            raise RuntimeError("Read-only attach reached a different native process")
        receipt = {
            "nonce": request["nonce"],
            "pid": pid,
            "revision": app.RevisionNumber(),
        }
        write_new_json(receipt_path, receipt)
    finally:
        pythoncom.CoUninitialize()


def launch_once(mode, *, report_root, timeout_s=600):
    import dodo
    from solidworks_mcp.adapters import sw_install
    from PIL import ImageGrab

    report_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=f"{mode}-", dir=report_root))
    audit = {"started": stamp(), "mode": mode, "status": "preparing"}
    parent_before = dict(os.environ)
    audit["parent_before"] = selected_environment(parent_before)
    nonce = uuid.uuid4().hex
    print(f"REPORT_DIRECTORY {output}", flush=True)
    try:
        defaults = native_defaults() if mode == "native-defaults" else {}
        environment, changes = child_environment(mode, parent_before, defaults)
        audit.update(child_values=selected_environment(environment), additions=changes)
        audit["native_sources"] = {
            name: {
                "hive": "HKLM64",
                "key": SOURCES[name][0],
                "value_name": SOURCES[name][1],
            }
            for name in defaults
        }
        audit["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        with dodo._com_seat(f"single licensed startup {mode}"):
            initial = process_inventory()
            audit["initial_processes"] = initial
            require_empty_inventory(initial)
            strategy, shortcut = sw_install.resolve_launch_strategy()
            if (
                strategy is not sw_install.LaunchStrategy.PLATFORM_SHORTCUT
                or shortcut is None
            ):
                raise RuntimeError("No normal licensed platform shortcut")
            environment["HARMONIC_COM_SEAT"] = os.environ["HARMONIC_COM_SEAT"]
            request = {
                "nonce": nonce,
                "shortcut": str(shortcut),
                "environment": selected_environment(environment),
            }
            request_path = output / "launch-request.json"
            write_new_json(request_path, request)
            audit["launch"] = run_child(
                "launch-child",
                request_path,
                output / "launch-receipt.json",
                environment=environment,
            )
            if (
                audit["launch"].get("nonce") != nonce
                or audit["launch"].get("environment") != request["environment"]
            ):
                raise RuntimeError("Launch receipt does not match this request")

            def attach(pid):
                path = output / "attach-request.json"
                write_new_json(path, {"nonce": nonce, "expected_pid": pid})
                receipt = run_child(
                    "attach-child", path, output / "attach-receipt.json"
                )
                return validate_attach(receipt, nonce=nonce, expected_pid=pid)

            def capture(rows):
                for index, row in enumerate(rows):
                    ImageGrab.grab(bbox=tuple(row["rect"]), all_screens=True).save(
                        output / f"blocking-dialog-{index}.png"
                    )

            outcome = observe_startup(
                read=os_snapshot,
                attach=attach,
                capture=capture,
                timeout_s=timeout_s,
                emit=lambda row: print(json.dumps(row), flush=True),
                audit=audit,
            )
            audit.update(outcome)
            if outcome["status"] == "ready":
                audit["cef_modules"] = cef_modules(outcome["attach"]["pid"])
    except Exception as exc:
        audit.update(status="failed", error=repr(exc))
        raise
    finally:
        audit["parent_after"] = selected_environment(os.environ)
        audit["parent_environment_unchanged"] = dict(os.environ) == parent_before
        audit["finished"] = stamp()
        write_new_json(output / "audit.json", audit)
        print(f"FINAL {audit['status']} {output / 'audit.json'}", flush=True)
    if not audit["parent_environment_unchanged"]:
        raise RuntimeError("Parent environment unexpectedly changed")
    return audit


def main():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "cad" / "scripts"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("inherited", "native-defaults", "launch-child", "attach-child")
    )
    parser.add_argument("child_paths", nargs="*", type=Path)
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/licensed-startup"
    )
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    if args.mode.endswith("-child"):
        if len(args.child_paths) != 2:
            parser.error("Internal child requires request and receipt paths")
        child_main(args.mode, *args.child_paths)
        return
    if args.child_paths:
        parser.error("Unexpected positional paths")
    if not math.isfinite(args.timeout) or not 1 <= args.timeout <= 900:
        parser.error("--timeout must be within1–900 seconds")
    outcome = launch_once(
        args.mode, report_root=args.report_root.resolve(), timeout_s=args.timeout
    )
    raise SystemExit(0 if outcome["status"] == "ready" else 1)


if __name__ == "__main__":
    main()
