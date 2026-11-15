"""Issue #2434: what the measuring-stick setting error costs, from error_budget.py.

Re-runs the shipped budget (cad/config/error_budget.yaml, origin/main) with only
the station_setting half-width changed, and prints the station_setting row, the
combined scatter, the closure total and whether the budget still closes.
Run from cad/scripts of an origin/main worktree:
    uv run --frozen python <this file>
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import error_budget as eb  # noqa: E402

base = eb.load_budget()
out = {}
for tol in (0.25, 0.5, 0.75, 1.0):
    b = copy.deepcopy(base)
    b["critical_features"]["station_setting"]["tolerance"] = tol
    r = eb.build_report(b)
    mc = r["monte_carlo"]
    row = {k: v for k, v in mc["per_feature"]["station_setting"].items() if k != "per_input"}
    comb = {k: v for k, v in mc["combined"].items() if k != "per_input"}
    out[tol] = {
        "station_setting": row,
        "combined": comb,
        "total_mae": r["closure"]["total_mae"],
        "total_mae_as_built": r["closure"]["total_mae_as_built"],
        "pair_worst": r["closure"]["pair_worst"],
        "violations": eb.budget_closes(r),
    }
    print(tol, json.dumps(out[tol], default=float)[:1500], flush=True)
Path(__file__).with_suffix(".json").write_text(json.dumps(out, indent=1, default=float))
