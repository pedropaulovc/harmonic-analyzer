"""Record exact inputs and outputs of the two normal VM2 drawing tasks."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _drawing_registry import DRAWINGS_BY_NAME  # noqa: E402

SPECS = tuple(DRAWINGS_BY_NAME[name] for name in ("pinion_lift_rod", "rack_pinion"))


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    if len(sys.argv) != 2:
        raise ValueError("provide a new own report directory")
    output = Path(sys.argv[1]).resolve()
    reports = ROOT / "cad/out/reports"
    if not output.is_relative_to(reports) or output == reports or output.exists():
        raise ValueError("choose a new child report directory")
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("requires own uv environment")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0" or os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise RuntimeError("requires attach-only mode and remote cache off")
    command = [sys.executable, "-m", "doit", "-n", "4",
               "drawing:pinion_lift_rod", "drawing:rack_pinion"]
    sources = [ROOT / f"cad/out/sldprt/{spec.artifact_stem}.SLDPRT" for spec in SPECS]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    adapter = subprocess.check_output(["git", "-C", "SolidworksMCP-python", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    scripts = [ROOT / f"cad/scripts/{name}" for name in (
        "draw_pinion_lift_rod.py", "draw_rack_pinion.py", "_native_axis_datum.py",
        "_rack_bore_finish.py", "_drawing_common.py")]
    report = {"kind": "vm2-normal-datum-drawing-tasks", "head": head, "adapter": adapter,
              "command": command, "cwd": str(ROOT), "status": "running",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "source_sha256_before": {str(path): digest(path) for path in sources},
              "script_sha256_before": {str(path): digest(path) for path in scripts},
              "scope": "two normal drawing tasks; not full retained-stack acceptance"}
    output.mkdir(parents=True)
    receipt = output / "receipt.json"
    receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    started = time.perf_counter()
    with (output / "build.log").open("wb") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    report.update(exit_code=result.returncode, elapsed_s=time.perf_counter() - started,
                  ended_utc=datetime.now(timezone.utc).isoformat(),
                  source_sha256_after={str(path): digest(path) for path in sources},
                  script_sha256_after={str(path): digest(path) for path in scripts},
                  log_sha256=digest(output / "build.log"))
    outputs = [spec.outputs[key] for spec in SPECS for key in ("slddrw", "pdf", "png")]
    report["outputs"] = {str(path): digest(path) for path in outputs if path.is_file()}
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report["head_after"] = current_head
    report["status"] = "passed" if result.returncode == 0 else "failed"
    if report["script_sha256_before"] != report["script_sha256_after"] or current_head != head:
        report["status"] = "source_changed_during_run"
    if result.returncode == 0 and len(report["outputs"]) != len(outputs):
        report["status"] = "missing_outputs"
    receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
