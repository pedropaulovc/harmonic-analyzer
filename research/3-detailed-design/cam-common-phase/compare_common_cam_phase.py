"""What a cam phase common to all 20 cylinder gears does to a drawn curve (#2361).

Every channel k draws A_k cos(k*theta + phi0) instead of A_k cos(k*theta).
Example input: A_k = 1/k, k = 1..20.  Writes common-cam-phase.png beside this file.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HARMONICS = np.arange(1, 21)
AMPLITUDES = 1.0 / HARMONICS
THETA = np.linspace(0.0, 2.0 * np.pi, 4001)
CASES = (
    (0.47, "fixture's common part, up to .47 deg (#2361)", "tab:red"),
    (1.5, "as modelled at crank home, 1.5 deg (#749)", "tab:blue"),
)


def curve(phase_deg: float) -> np.ndarray:
    phase = np.radians(phase_deg)
    return (AMPLITUDES[:, None] * np.cos(HARMONICS[:, None] * THETA + phase)).sum(
        axis=0
    )


def main() -> None:
    nominal = curve(0.0)
    scale = np.abs(AMPLITUDES).sum()
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    top.plot(
        np.degrees(THETA), nominal, color="black", lw=1.2, label="all cams in phase"
    )
    for phase_deg, label, colour in CASES:
        shifted = curve(phase_deg)
        top.plot(np.degrees(THETA), shifted, color=colour, lw=0.8, label=label)
        error = (shifted - nominal) / scale * 100.0
        bottom.plot(
            np.degrees(THETA),
            error,
            color=colour,
            lw=0.9,
            label=f"{label}: max {np.abs(error).max():.2f} %, mean {np.abs(error).mean():.2f} %",
        )
    top.set_ylabel("drawn ordinate (sum of 20 terms, A_k = 1/k)")
    top.legend(loc="upper center", fontsize=8)
    bottom.set_ylabel("error, % of summed amplitudes")
    bottom.set_xlabel("crank angle, deg")
    bottom.legend(loc="upper center", fontsize=8)
    fig.suptitle(
        "A cam phase common to all 20 cylinder gears: effect on the drawn curve"
    )
    fig.tight_layout()
    fig.savefig(Path(__file__).with_name("common-cam-phase.png"), dpi=130)


if __name__ == "__main__":
    main()
