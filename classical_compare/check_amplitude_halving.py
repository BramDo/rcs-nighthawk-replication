"""Measure phase-aligned MPS state-vector error on the exact 21q patch."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import qpy
from qiskit_aer import AerSimulator

ROOT = Path(__file__).resolve().parents[1]
CIRCUIT = ROOT / "quantum/pair_prepared/patch0_d36_logical.qpy"
OUTPUT = ROOT / "classical_compare/results/patch_amplitude_error_vs_chi.json"
CHIS = (8, 16, 32, 64, 128)


def vector(circuit, method: str, chi: int | None = None) -> tuple[np.ndarray, float]:
    options = {"method": method, "precision": "double", "max_parallel_threads": 3,
               "max_parallel_experiments": 1, "max_memory_mb": 6000}
    if chi is not None:
        options.update(matrix_product_state_max_bond_dimension=chi,
                       matrix_product_state_truncation_threshold=0.0,
                       mps_omp_threads=3)
    sim = AerSimulator(**options)
    start = time.perf_counter()
    result = sim.run(circuit).result()
    elapsed = time.perf_counter() - start
    if not result.success:
        raise RuntimeError(f"{method}, chi={chi}: {result.status}")
    return np.asarray(result.data(0)["psi"], dtype=np.complex128), elapsed


def main() -> None:
    with CIRCUIT.open("rb") as handle:
        circuit = qpy.load(handle)[0]
    if circuit.num_qubits != 21 or circuit.count_ops().get("cz", 0) != 279:
        raise RuntimeError("unexpected patch circuit")
    circuit = circuit.remove_final_measurements(inplace=False)
    circuit.save_statevector(label="psi")
    exact, exact_seconds = vector(circuit, "statevector")
    norm_exact = np.linalg.norm(exact)
    if not np.isclose(norm_exact, 1, atol=1e-8):
        raise RuntimeError("exact state is not normalized")
    report = {"circuit": str(CIRCUIT.relative_to(ROOT)), "qubits": 21,
              "cz": 279, "exact_statevector_seconds": exact_seconds,
              "error_definition": "min_global_phase ||psi_MPS-psi_exact||_2 for normalized states",
              "runs": []}
    for chi in CHIS:
        approx, seconds = vector(circuit, "matrix_product_state", chi)
        norm_approx = np.linalg.norm(approx)
        inner = np.vdot(exact, approx) / (norm_exact * norm_approx)
        magnitude = min(float(abs(inner)), 1.0)
        error = float(np.sqrt(max(0.0, 2 - 2 * magnitude)))
        row = {"chi": chi, "seconds": seconds,
               "normalized_state_overlap_fidelity": magnitude**2,
               "phase_aligned_relative_amplitude_l2_error": error,
               "approx_state_norm": float(norm_approx)}
        report["runs"].append(row)
        print(json.dumps(row), flush=True)
        del approx
    report["successive_amplitude_error_ratios"] = [
        report["runs"][i]["phase_aligned_relative_amplitude_l2_error"] /
        report["runs"][i-1]["phase_aligned_relative_amplitude_l2_error"]
        for i in range(1, len(report["runs"]))]
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
