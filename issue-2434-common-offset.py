"""Issue #2434: coefficient error from a COMMON station offset on all 20 bars.

The nominal machine (error_budget.NominalTrial) run through the shipped
READOUT procedure, except that every bar actually stands `offset` mm from the
station the operator set and recorded (bars at zero included; nothing stops a
bar behind the pivot). Each reference input runs at its own ordinate scale f
(magnifier_setup). Prints MAE / max coefficient error in % of greatest term.

  offset -2.74: Michelson registration with the stick as drawn, READOUT's
                table read literally (the do-nothing outcome)
  offset +/-0.25: the stick's .XX length band, if its 10-end face is not the
                  scale datum

Run from cad/scripts of an origin/main worktree:
    uv run --frozen python <this file>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
import error_budget as eb  # noqa: E402

nom = eb.nominal()
trial = eb.NominalTrial(nom)
out: dict[str, dict[str, dict[str, float]]] = {}
for offset in (0.0, -2.74, -0.25, 0.25):
    rows = {}
    for name, x in eb.reference_inputs().items():
        f = trial.magnifier_setup(x).ordinate_scale
        set_st = f * x * nom.d_max
        actual = set_st + offset
        x_read = trial.x_read(set_st) / f
        kappa = trial.kappa(set_st)
        zero = float(np.mean(trial.trace(actual, eb.PERIOD)))
        readings = trial.trace(actual, eb.THETA_K) - zero
        measured = eb.read_coefficients(readings, x_read, kappa) - eb.ideal_coefficients(x_read - x)
        e = eb.coefficient_errors_pct(measured, x)
        rows[name] = {"f": f, "mae": float(np.mean(np.abs(e))), "max": float(np.max(np.abs(e)))}
    out[str(offset)] = rows
    print(offset, {k: (round(v["f"], 3), round(v["mae"], 3), round(v["max"], 3)) for k, v in rows.items()})
Path(__file__).with_suffix(".json").write_text(json.dumps(out, indent=1))
