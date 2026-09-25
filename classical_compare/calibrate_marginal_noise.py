"""Estimate the 1000-shot noise floor for 61-bit marginal comparisons."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "quantum/full_60qs/full_d36_1000000_shots.npz"
OUTPUT = ROOT / "classical_compare/results/marginal_1000shot_noise_floor.json"


def main() -> None:
    with np.load(SOURCE) as data:
        full = data["shots"]
    if len(full) != 1_000_000:
        raise ValueError("unexpected quantum shot count")
    bits = ((full[:, None] >> np.arange(61, dtype=np.uint64)) & 1).astype(np.uint8)
    weights = bits.sum(axis=1).astype(np.uint8)
    reference_bits = bits.mean(axis=0)
    reference_hist = np.bincount(weights, minlength=62) / len(full)
    rng = np.random.default_rng(20260925)
    rms_values = []
    tv_values = []
    for _ in range(1000):
        index = rng.integers(0, len(full), size=1000)
        sampled_bits = bits[index].mean(axis=0)
        sampled_hist = np.bincount(weights[index], minlength=62) / 1000
        rms_values.append(float(np.sqrt(np.mean((sampled_bits - reference_bits) ** 2))))
        tv_values.append(float(np.abs(sampled_hist - reference_hist).sum() / 2))
    report = {
        "source": str(SOURCE.relative_to(ROOT)), "replicates": 1000,
        "shots_per_replicate": 1000, "seed": 20260925,
        "interpretation": "Noise floor if a 1000-shot sample follows the measured IBM distribution exactly.",
        "one_bit_rms": {"median": float(np.median(rms_values)),
                        "p95": float(np.quantile(rms_values, 0.95)),
                        "p99": float(np.quantile(rms_values, 0.99))},
        "hamming_tv": {"median": float(np.median(tv_values)),
                       "p95": float(np.quantile(tv_values, 0.95)),
                       "p99": float(np.quantile(tv_values, 0.99))},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
