"""Compare low-order sample statistics; this does not compute RCS fidelity."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "rcs-nighthawk/data/samples/full_d36.npz"
QUANTUM = ROOT / "quantum/full_60qs/full_d36_1000000_shots.npz"
RESULTS = ROOT / "classical_compare/results"


def read_shots(path: Path) -> np.ndarray:
    with np.load(path) as data:
        shots = data["shots"]
    if shots.dtype != np.uint64 or np.any(shots >= np.uint64(1 << 61)):
        raise ValueError(f"invalid 61-bit shots in {path}")
    return shots


def summary(shots: np.ndarray) -> dict:
    weights = np.fromiter((int(x).bit_count() for x in shots),
                          dtype=np.uint8, count=len(shots))
    bit_ones = np.array([float(((shots >> np.uint64(i)) & 1).mean())
                         for i in range(61)])
    return {
        "shots": int(len(shots)),
        "mean_ones": float(weights.mean()),
        "std_ones": float(weights.std()),
        "mean_ones_shot_noise_se": float(weights.std() / np.sqrt(len(shots))),
        "bit_one_fractions": bit_ones.tolist(),
        "hamming_histogram": np.bincount(weights, minlength=62).tolist(),
    }


def main() -> None:
    paper = summary(read_shots(PAPER))
    quantum = summary(read_shots(QUANTUM))
    report = {"note": "Low-order marginals only; not full-distribution fidelity or XEB.",
              "paper": paper, "new_quantum": quantum, "mps": {}}
    for chi in (8, 16, 32, 64, 128):
        source = RESULTS / f"full_d36_chi{chi}_1000shots.npz"
        if not source.exists():
            continue
        row = summary(read_shots(source))
        for name, reference in (("paper", paper), ("new_quantum", quantum)):
            difference = row["mean_ones"] - reference["mean_ones"]
            se = np.hypot(row["mean_ones_shot_noise_se"],
                          reference["mean_ones_shot_noise_se"])
            bit_diff = np.asarray(row["bit_one_fractions"]) - reference["bit_one_fractions"]
            hist_diff = (np.asarray(row["hamming_histogram"]) / row["shots"]
                         - np.asarray(reference["hamming_histogram"]) / reference["shots"])
            row[f"mean_ones_minus_{name}"] = float(difference)
            row[f"mean_ones_difference_shot_noise_se_vs_{name}"] = float(se)
            row[f"rms_bit_fraction_difference_vs_{name}"] = float(np.sqrt(np.mean(bit_diff**2)))
            row[f"hamming_histogram_tv_vs_{name}"] = float(np.abs(hist_diff).sum() / 2)
        report["mps"][str(chi)] = row
    output = RESULTS / "full_d36_marginal_comparison.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"paper_mean_ones": paper["mean_ones"],
                      "new_quantum_mean_ones": quantum["mean_ones"],
                      "mps": {chi: {k: row[k] for k in
                                    ("shots", "mean_ones", "mean_ones_minus_new_quantum",
                                     "mean_ones_difference_shot_noise_se_vs_new_quantum",
                                     "rms_bit_fraction_difference_vs_new_quantum",
                                     "hamming_histogram_tv_vs_new_quantum")}
                              for chi, row in report["mps"].items()}}, indent=2))


if __name__ == "__main__":
    main()
