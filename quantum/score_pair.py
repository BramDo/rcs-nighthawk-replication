"""Score paired 21-qubit IBM counts and Fire Opal probability weights by XEB."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "quantum" / "pair_prepared"
sys.path.insert(0, str(PROJECT / "rcs-nighthawk"))
from rcs.io import extract_bits, load_shots  # noqa: E402


def score_shots(shots: np.ndarray, probabilities: np.ndarray, ideal_xeb: float) -> dict:
    if len(shots) < 2:
        raise ValueError("at least two shots required")
    indices = np.asarray(shots, dtype=np.int64)
    if np.any(indices < 0) or np.any(indices >= len(probabilities)):
        raise ValueError("shot index outside probability vector")
    values = (len(probabilities) * probabilities[indices] - 1.0) / ideal_xeb
    return {"fidelity": float(values.mean()),
            "shot_noise_se": float(values.std(ddof=1) / math.sqrt(len(values))),
            "shots": len(values)}


def score_counts(counts: dict[str, int], probabilities: np.ndarray, ideal_xeb: float) -> dict:
    shots = np.repeat(
        np.fromiter((int(k.replace(" ", ""), 2) for k in counts), dtype=np.uint64),
        np.fromiter((int(v) for v in counts.values()), dtype=np.int64),
    )
    return score_shots(shots, probabilities, ideal_xeb)


def score_weights(weights: dict[str, float], probabilities: np.ndarray, ideal_xeb: float) -> dict:
    total = 0.0
    numerator = 0.0
    for raw_key, raw_weight in weights.items():
        key = raw_key.replace(" ", "")
        if len(key) != 21 or set(key) - {"0", "1"}:
            raise ValueError("invalid 21-bit Fire Opal outcome")
        weight = float(raw_weight)
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("invalid Fire Opal probability weight")
        total += weight
        numerator += weight * (len(probabilities) * probabilities[int(key, 2)] - 1.0)
    if total <= 0:
        raise ValueError("zero Fire Opal weight")
    return {"fidelity": numerator / (total * ideal_xeb),
            "total_probability_weight": total,
            "outcome_count": len(weights),
            "shot_noise_se": None,
            "se_note": "Fire Opal probability weights are not treated as independent counts"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-release", action="store_true")
    parser.add_argument("--ibm-counts", type=Path)
    parser.add_argument("--fireopal-result", type=Path)
    args = parser.parse_args()
    plan = json.loads((ROOT / "pair_plan.json").read_text(encoding="utf-8"))
    with np.load(ROOT / "patch0_d36_ideal_probabilities.npz") as stored:
        p = stored["probabilities"]
    ideal = float(plan["ideal_xeb"])
    output = {"patch": "K3 d36 partition0 instance0 patch0", "ideal_xeb": ideal}
    if args.verify_release:
        shots = load_shots(PROJECT / "rcs-nighthawk" / "data" / "counts" /
                           "patched_K3_d36.npz")["partition0_instance0"]
        patch_shots = extract_bits(shots, plan["patch_logical_qubits"])
        measured = score_shots(patch_shots, p, ideal)
        expected = float(plan["released_2026_patch_fidelity"])
        if abs(measured["fidelity"] - expected) > 1e-9:
            raise RuntimeError("released XEB does not match this scorer")
        output["release_check"] = {"expected": expected, "recomputed": measured,
                                   "passed": True}
    if args.ibm_counts:
        counts = json.loads(args.ibm_counts.read_text(encoding="utf-8"))["counts"]
        output["ibm"] = score_counts(counts, p, ideal)
    if args.fireopal_result:
        weights = json.loads(args.fireopal_result.read_text(encoding="utf-8"))["probabilities"]
        output["fireopal"] = score_weights(weights, p, ideal)
    if "ibm" in output and "fireopal" in output:
        output["difference_fireopal_minus_ibm"] = (
            output["fireopal"]["fidelity"] - output["ibm"]["fidelity"])
        output["difference_significance_available"] = False
    path = ROOT / ("scoring_check.json" if args.verify_release and not args.ibm_counts and not args.fireopal_result
                   else "paired_xeb_result.json")
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
