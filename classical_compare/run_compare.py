"""Compare MPS state truncation and Majorana observable truncation on RCS circuits."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import qpy
from qiskit_aer import AerSimulator

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "rcs-nighthawk"))
from rcs.circuits import RCSConfig, build_rcs_circuit, split_patched_circuit  # noqa: E402
from rcs.estimators import ideal_xeb  # noqa: E402
from rcs.layout import load_layout  # noqa: E402
from majorana import TermLimit, z_parity_expectation  # noqa: E402


def circuit_for_case(case: str, depth: int):
    if case == "toy":
        matchings = {
            "A": [(3 * r, 3 * r + 1) for r in range(3)],
            "B": [(3 * r + 1, 3 * r + 2) for r in range(3)],
            "C": [(c, c + 3) for c in range(3)],
            "D": [(c + 3, c + 6) for c in range(3)],
        }
        return build_rcs_circuit(RCSConfig(9, depth, matchings), 2025, 0, measure=False), "toy full 3x3"
    root = PROJECT / "rcs-nighthawk"
    layout = load_layout(root / "data" / "layout.json")
    path = root / "data" / "circuits" / "patched" / "K3" / f"d{depth}" / "partition0_instance0.qpy"
    with path.open("rb") as handle:
        patched = qpy.load(handle)[0]
    _, patches = layout.partitions[3][0]
    subs, _ = split_patched_circuit(patched, patches)
    name = max(subs, key=lambda k: subs[k].num_qubits)
    return subs[name], f"published K3 patch partition0 instance0 {name}"


def statevector(circuit, method: str, chi: int | None = None):
    options = {"method": method, "max_parallel_threads": 3}
    if chi is not None:
        options.update(matrix_product_state_max_bond_dimension=chi,
                       matrix_product_state_truncation_threshold=0.0)
    simulator = AerSimulator(**options)
    saved = circuit.copy()
    saved.save_statevector()
    start = time.perf_counter()
    result = simulator.run(saved).result()
    if not result.success:
        raise RuntimeError(result.status)
    # Validate this snapshot against actual Aer samples in test_mps_sampling.py.
    vector = np.asarray(result.get_statevector(), dtype=np.complex128)
    raw_norm = float(np.vdot(vector, vector).real)
    if raw_norm <= 0:
        raise RuntimeError("MPS/statevector has nonpositive norm")
    return vector / math.sqrt(raw_norm), time.perf_counter() - start, raw_norm


def parity_from_probs(probs: np.ndarray, support: list[int]) -> float:
    indices = np.arange(len(probs), dtype=np.uint64)
    sign = np.ones(len(probs), dtype=np.float64)
    for q in support:
        sign *= 1 - 2 * ((indices >> q) & 1).astype(np.float64)
    return float(np.dot(sign, probs))


def run(case: str, depth: int, chis: list[int], weights: list[int], max_terms: int):
    circuit, description = circuit_for_case(case, depth)
    exact, exact_s, exact_raw_norm = statevector(circuit, "statevector")
    p_exact = np.abs(exact) ** 2
    assert math.isclose(float(p_exact.sum()), 1.0, abs_tol=1e-9)
    norm = ideal_xeb(p_exact)
    mps = []
    for chi in chis:
        candidate, elapsed, raw_norm = statevector(circuit, "matrix_product_state", chi)
        p_candidate = np.abs(candidate) ** 2
        mps.append({"chi": chi, "seconds": elapsed,
                    "raw_mps_norm_squared": raw_norm,
                    "state_fidelity": float(abs(np.vdot(exact, candidate)) ** 2),
                    "normalized_xeb_of_distribution": float((len(p_exact) * np.dot(p_exact, p_candidate) - 1) / norm),
                    "total_variation_distance": float(np.abs(p_exact - p_candidate).sum() / 2)})
    supports = [[0], [circuit.num_qubits // 2], [circuit.num_qubits - 1], [0, circuit.num_qubits - 1]]
    majorana = []
    for weight in weights:
        start = time.perf_counter()
        rows = []
        for support in supports:
            exact_value = parity_from_probs(p_exact, support)
            try:
                result = z_parity_expectation(circuit, support, weight, max_terms)
                rows.append({"support": support, "exact": exact_value, **result,
                             "absolute_error": abs(result["expectation"] - exact_value)})
            except TermLimit as exc:
                rows.append({"support": support, "exact": exact_value, "status": "term_limit", "error": str(exc)})
        errors = [r["absolute_error"] for r in rows if "absolute_error" in r]
        references = [r["exact"] for r in rows if "absolute_error" in r]
        majorana.append({"max_weight": weight, "seconds": time.perf_counter() - start,
                         "observable_rmse": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
                         "zero_predictor_rmse": float(np.sqrt(np.mean(np.square(references)))) if references else None,
                         "observables": rows, "sampling_supported": False})
    return {"case": case, "description": description, "depth": depth, "qubits": circuit.num_qubits,
            "exact_statevector_seconds": exact_s, "exact_raw_norm_squared": exact_raw_norm,
            "ideal_xeb": norm,
            "mps": mps, "majorana": majorana,
            "scope": "Patch or small-circuit validation only; no 61-qubit full-circuit fidelity claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("toy", "paper-patch"), default="toy")
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--chi", nargs="+", type=int, default=[4, 8, 16])
    parser.add_argument("--weights", nargs="+", type=int, default=[2, 4, 6])
    parser.add_argument("--max-terms", type=int, default=20_000)
    args = parser.parse_args()
    depth = args.depth or (4 if args.case == "toy" else 36)
    if depth < 1 or any(x < 1 for x in args.chi + args.weights) or args.max_terms < 1:
        parser.error("positive depth, cutoffs and term cap required")
    result = run(args.case, depth, args.chi, args.weights, args.max_terms)
    out = Path(__file__).parent / "results" / f"{args.case}_d{depth}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['description']}: {result['qubits']} qubits, depth {depth}, ideal XEB {result['ideal_xeb']:.4g}")
    for row in result["mps"]:
        print(f"MPS chi={row['chi']}: F_state={row['state_fidelity']:.6g}, XEB={row['normalized_xeb_of_distribution']:.6g}, TVD={row['total_variation_distance']:.6g}, {row['seconds']:.2f}s")
    for row in result["majorana"]:
        print(f"Majorana weight<={row['max_weight']}: observable RMSE={row['observable_rmse']}, {row['seconds']:.2f}s")
    print(f"Wrote {out}")
