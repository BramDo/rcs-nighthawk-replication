"""Classical exact and capped-MPS sampling on the quantum pair's exact 21q patch."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import qiskit
import qiskit_aer
from qiskit import qpy
from qiskit_aer import AerSimulator

PROJECT = Path(__file__).resolve().parents[1]
PAIR = PROJECT / "quantum" / "pair_prepared"
OUT = PROJECT / "classical_compare" / "results"
sys.path.insert(0, str(PROJECT / "quantum"))
sys.path.insert(0, str(PROJECT / "rcs-nighthawk"))
from run_full_mps import summarize_log  # noqa: E402
from score_pair import score_counts  # noqa: E402
from rcs.io import counts_to_shots, save_shots  # noqa: E402

SHOTS = 4096
SEED = 2025
CHIS = (8, 16, 32, 64)


def timed_samples(circuit, method: str, chi: int | None = None):
    options = {"method": method, "max_parallel_threads": 3,
               "max_parallel_experiments": 1, "max_memory_mb": 6000,
               "seed_simulator": SEED}
    if chi is not None:
        options.update(matrix_product_state_max_bond_dimension=chi,
                       matrix_product_state_truncation_threshold=0.0,
                       mps_log_data=True, mps_omp_threads=3)
    simulator = AerSimulator(**options)
    start = time.perf_counter()
    result = simulator.run(circuit, shots=SHOTS).result()
    elapsed = time.perf_counter() - start
    if not result.success:
        raise RuntimeError(f"classical {method} simulation failed")
    return result.get_counts(), elapsed, result.results[0].metadata


def main():
    plan = json.loads((PAIR / "pair_plan.json").read_text(encoding="utf-8"))
    with np.load(PAIR / "patch0_d36_ideal_probabilities.npz") as data:
        ideal = data["probabilities"]
    if hashlib.sha256(ideal.tobytes()).hexdigest() != plan["ideal_probabilities_sha256"]:
        raise RuntimeError("exact ideal probabilities changed")
    circuit_file = PAIR / "patch0_d36_logical.qpy"
    with circuit_file.open("rb") as handle:
        circuit = qpy.load(handle)[0]
    if circuit.num_qubits != 21 or circuit.count_ops().get("cz", 0) != 279:
        raise RuntimeError("wrong patch circuit")
    OUT.mkdir(exist_ok=True)
    quantum = json.loads((PAIR / "paired_xeb_result.json").read_text(encoding="utf-8"))
    report = {
        "case": "released K3 d36 partition0 instance0 patch0, barriers removed",
        "circuit_sha256": hashlib.sha256(circuit_file.read_bytes()).hexdigest(),
        "ideal_probabilities_sha256": plan["ideal_probabilities_sha256"],
        "qubits": 21, "cycles": 36, "cz": 279,
        "shots_per_run": SHOTS, "seed_simulator": SEED,
        "qiskit_version": qiskit.__version__,
        "qiskit_aer_version": qiskit_aer.__version__,
        "cpu_threads": 3,
        "quantum_reference": {"ibm_xeb": quantum["ibm"]["fidelity"],
                              "ibm_shot_noise_se": quantum["ibm"]["shot_noise_se"],
                              "fireopal_xeb": quantum["fireopal"]["fidelity"]},
        "classical": [],
    }
    for method, chi in [("statevector", None)] + [("matrix_product_state", c) for c in CHIS]:
        counts, seconds, metadata = timed_samples(circuit, method, chi)
        shots = counts_to_shots(counts)
        if len(shots) != SHOTS:
            raise RuntimeError("classical shot total changed")
        label = "exact" if chi is None else f"mps_chi{chi}"
        path = OUT / f"pair_patch_d36_{label}_{SHOTS}shots.npz"
        save_shots(path, {"shots": shots})
        row = {"method": label, "chi": chi, "seconds": seconds,
               "xeb": score_counts(counts, ideal, plan["ideal_xeb"]),
               "sample_file": str(path.relative_to(PROJECT)),
               "samples_sha256": hashlib.sha256(shots.tobytes()).hexdigest(),
               "peak_process_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
               "mps_diagnostics": summarize_log(metadata) if chi is not None else None}
        report["classical"].append(row)
        (OUT / "pair_patch_classical_quantum.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{label}: XEB {row['xeb']['fidelity']:.5f} ± {row['xeb']['shot_noise_se']:.5f}, "
              f"{seconds:.2f}s, unique {len(counts)}", flush=True)
    if abs(report["classical"][0]["xeb"]["fidelity"] - 1.0) > 0.1:
        raise RuntimeError("exact sampler XEB unexpectedly far from one")
    print("Wrote classical_compare/results/pair_patch_classical_quantum.json")


if __name__ == "__main__":
    main()
