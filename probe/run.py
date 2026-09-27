"""Run probe options in subprocesses and print compact summaries."""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
PY = "C:/src/harmonic-analyzer/.venv/Scripts/python.exe"


def run(name: str, spec: dict | None = None) -> dict:
    args = [PY, str(HERE / "pinion_cluster_probe.py"), name]
    if spec is not None:
        f = HERE / f"{name}.spec.json"
        f.write_text(json.dumps(spec))
        args.append(str(f))
    r = subprocess.run(args, capture_output=True, text=True, check=False)
    if r.returncode:
        print(r.stderr[-2000:])
        raise SystemExit(name)
    (HERE / f"{name}.json").write_text(r.stdout)
    return json.loads(r.stdout)


def summary(d: dict) -> None:
    f = lambda v: round(v, 3) if isinstance(v, float) else v  # noqa: E731
    print(f"=== {d['option']}  import_error={d['import_error']}")
    for x in d["assert_failures"]:
        print("   FAIL:", x[:160])
    for k in ("linkage", "strap_vs_collar", "sweeps", "axial", "pivot_block", "cam", "strap"):
        v = d.get(k, {})
        print(f"  {k}: " + ", ".join(f"{kk}={f(vv) if not isinstance(vv, list) else [f(x) if not isinstance(x, list) else [f(y) for y in x] for x in vv]}" for kk, vv in v.items() if kk not in ("strap_z", "cam_z")))
    print("  anchors:", {k: f(v) for k, v in d.get("anchors", {}).items()})
    br = d.get("base_required", {})
    if br:
        print("  base block xz need:", [[f(a) for a in p] for p in br["block_screw_xz"]])
        print("  base foot xz need :", [f(a) for a in br["foot_screw_xz"][0]], " has", [f(a) for a in br["foot_screw_xz_base_has"][0]])


if __name__ == "__main__":
    specs = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else {}
    names = sys.argv[2:] or list(specs)
    for n in names:
        summary(run(n, specs.get(n)))
