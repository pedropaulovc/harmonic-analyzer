"""Issue #1611 owner pack: sweep error_budget.yaml's knife.rolling_resistance_mm
in memory (the yaml is not edited) and report the knife closure term, the
total MAE and the pair gate at each value.  Run from a clean origin/main
worktree's cad/scripts:  uv run python <this file>"""

import copy
import json
import sys

sys.path.insert(0, ".")
import error_budget as eb  # noqa: E402

base = eb.load_budget()
rows = []
for f in (0.0025, 0.005, 0.0075, 0.010, 0.0125, 0.015, 0.020):
    b = copy.deepcopy(base)
    b["reserved"]["knife"]["rolling_resistance_mm"] = f
    r = eb.build_report(b)
    cl = r["closure"]
    rows.append(
        {
            "f_mm": f,
            "knife_pct": cl["knife"],
            "knife_allow": r["reserved_allowance"]["knife"],
            "total_mae": cl["total_mae"],
            "pair_worst": cl["pair_worst"],
            "fails": eb.budget_closes(r),
        }
    )
    print(json.dumps(rows[-1]), flush=True)
json.dump(rows, open(sys.argv[1] if len(sys.argv) > 1 else "sweep.json", "w"), indent=1)
