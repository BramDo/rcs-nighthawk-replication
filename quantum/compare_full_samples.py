"""Compare the new full-width samples with the paper release, without QPU access."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "rcs-nighthawk/data/samples/full_d36.npz"
NEW = ROOT / "quantum/full_60qs/full_d36_1000000_shots.npz"
OUTPUT = ROOT / "quantum/full_60qs/measurement_comparison.json"


def summarize(values: np.ndarray) -> tuple[dict, np.ndarray, np.ndarray]:
    if values.dtype != np.uint64 or values.size != 1_000_000:
        raise ValueError("expected one million uint64 shots")
    if np.any(values >= np.uint64(1 << 61)):
        raise ValueError("sample exceeds 61 bits")
    weights = np.fromiter((int(v).bit_count() for v in values),
                          dtype=np.uint8, count=len(values))
    p_one = np.array([((values >> np.uint64(i)) & np.uint64(1)).mean()
                      for i in range(61)])
    summary = {
        "shots": int(values.size),
        "distinct_bitstrings": int(np.unique(values).size),
        "mean_ones_per_shot": float(weights.mean()),
        "std_ones_per_shot": float(weights.std()),
        "minimum_ones": int(weights.min()),
        "maximum_ones": int(weights.max()),
        "per_bit_one_fraction_min": float(p_one.min()),
        "per_bit_one_fraction_max": float(p_one.max()),
        "per_bit_one_fraction_mean": float(p_one.mean()),
        "per_bit_one_fraction_logical_0_to_60": p_one.tolist(),
        "hamming_histogram_0_to_61": np.bincount(weights, minlength=62).tolist(),
    }
    return summary, weights, p_one


def main() -> None:
    with np.load(PUBLISHED) as data:
        paper = data["shots"]
    with np.load(NEW) as data:
        new = data["shots"]
    paper_summary, paper_weights, paper_bits = summarize(paper)
    new_summary, new_weights, new_bits = summarize(new)
    bit_diff = new_bits - paper_bits
    # Standard errors describe only finite-shot noise, conditional on each
    # distribution; device drift and shared systematic effects are separate.
    hamming_se = float(np.hypot(paper_weights.std(), new_weights.std()) / 1000)
    bit_se = np.sqrt((paper_bits * (1 - paper_bits)
                      + new_bits * (1 - new_bits)) / 1_000_000)
    hist_paper = np.bincount(paper_weights, minlength=62) / 1_000_000
    hist_new = np.bincount(new_weights, minlength=62) / 1_000_000
    comparison = {
        "same_released_logical_circuit": True,
        "paper_sample_file": str(PUBLISHED.relative_to(ROOT)),
        "new_sample_file": str(NEW.relative_to(ROOT)),
        "published": paper_summary,
        "new": new_summary,
        "new_minus_published_mean_ones": float(new_weights.mean() - paper_weights.mean()),
        "mean_ones_difference_shot_noise_se": hamming_se,
        "new_minus_published_bit_one_fraction": bit_diff.tolist(),
        "rms_per_bit_one_fraction_difference": float(np.sqrt(np.mean(bit_diff**2))),
        "largest_absolute_bit_one_fraction_difference": float(np.max(np.abs(bit_diff))),
        "largest_difference_logical_bit": int(np.argmax(np.abs(bit_diff))),
        "largest_absolute_bit_difference_shot_noise_z": float(np.max(np.abs(bit_diff / bit_se))),
        "hamming_histogram_total_variation": float(np.abs(hist_new - hist_paper).sum() / 2),
        "fidelity_directly_verified_by_this_comparison": False,
    }
    OUTPUT.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "published": {k: paper_summary[k] for k in
                      ("shots", "distinct_bitstrings", "mean_ones_per_shot", "std_ones_per_shot",
                       "per_bit_one_fraction_min", "per_bit_one_fraction_max")},
        "new": {k: new_summary[k] for k in
                ("shots", "distinct_bitstrings", "mean_ones_per_shot", "std_ones_per_shot",
                 "per_bit_one_fraction_min", "per_bit_one_fraction_max")},
        "new_minus_published_mean_ones": comparison["new_minus_published_mean_ones"],
        "mean_ones_difference_shot_noise_se": hamming_se,
        "rms_per_bit_one_fraction_difference": comparison["rms_per_bit_one_fraction_difference"],
        "largest_absolute_bit_one_fraction_difference": comparison["largest_absolute_bit_one_fraction_difference"],
        "largest_difference_logical_bit": comparison["largest_difference_logical_bit"],
        "hamming_histogram_total_variation": comparison["hamming_histogram_total_variation"],
    }, indent=2))


if __name__ == "__main__":
    main()
