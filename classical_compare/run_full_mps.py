"""Bounded full-width MPS sampling preflight on the released 61-qubit circuit.

No ideal full-circuit probabilities are available here, so this measures
feasibility and runtime only. It does not estimate output fidelity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import resource
import sys
import time
from pathlib import Path

from qiskit import qpy
from qiskit_aer import AerSimulator

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "rcs-nighthawk"))
from rcs.io import counts_to_shots, save_shots  # noqa: E402


def summarize_log(metadata: dict) -> dict:
    log = str(metadata.get("MPS_log_data", ""))
    discarded = [float(x) for x in re.findall(r"discarded_value=([0-9.eE+\-]+)", log)]
    bonds = [int(x) for group in re.findall(r"BD=\[([0-9 ]+)\]", log) for x in group.split()]
    return {"log_present": bool(log), "max_logged_bond_dimension": max(bonds, default=None),
            "discarded_value_events": len(discarded),
            "sum_discarded_values_diagnostic": sum(discarded),
            "sum_is_rigorous_error_bound": False}


def run_one(circuit, chi: int, shots: int, out_dir: Path) -> dict:
    simulator = AerSimulator(
        method="matrix_product_state", precision="double",
        matrix_product_state_max_bond_dimension=chi,
        matrix_product_state_truncation_threshold=0.0,
        mps_log_data=True, mps_omp_threads=3,
        max_parallel_threads=3, max_parallel_experiments=1,
        max_memory_mb=6000, seed_simulator=2025,
    )
    sample_start = time.perf_counter()
    sample_result = simulator.run(circuit, shots=shots).result()
    sample_seconds = time.perf_counter() - sample_start
    if not sample_result.success:
        raise RuntimeError(f"MPS sample run failed: {sample_result.status}")
    counts = sample_result.get_counts()
    samples = counts_to_shots(counts)
    if len(samples) != shots:
        raise AssertionError("MPS shot total does not match request")
    sample_file = out_dir / f"full_d36_chi{chi}_{shots}shots.npz"
    save_shots(sample_file, {"shots": samples})
    digest = hashlib.sha256(samples.tobytes()).hexdigest()
    return {
        "chi": chi, "shots": shots,
        "sampling_run_seconds": sample_seconds,
        "sample_unique_bitstrings": len(counts),
        "samples_sha256": digest,
        "sample_file": str(sample_file.relative_to(PROJECT)),
        "mps_diagnostics": summarize_log(sample_result.results[0].metadata),
        "peak_process_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "fidelity_known": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chi", nargs="+", type=int, default=[8, 16])
    parser.add_argument("--shots", type=int, default=1000)
    args = parser.parse_args()
    if args.shots < 1 or any(chi < 1 for chi in args.chi):
        parser.error("positive shots and bond dimensions required")
    path = PROJECT / "rcs-nighthawk" / "data" / "circuits" / "full" / "d36_logical.qpy"
    with path.open("rb") as handle:
        circuit = qpy.load(handle)[0]
    if circuit.num_qubits != 61 or circuit.count_ops().get("cz", 0) != 918:
        raise AssertionError("unexpected full circuit")
    out_dir = PROJECT / "classical_compare" / "results"
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / "full_d36_mps_preflight.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("circuit") != str(path.relative_to(PROJECT))
            or report.get("qubits") != 61 or report.get("cycles") != 36
            or report.get("cz_gates") != 918):
            raise RuntimeError("existing MPS report is for a different circuit")
    else:
        report = {"circuit": str(path.relative_to(PROJECT)), "qubits": 61, "cycles": 36,
                  "cz_gates": 918, "environment": "WSL /home/bram/.venvs/qiskit/bin/python",
                  "scope": "feasibility and time only; no full-circuit fidelity estimate",
                  "runs": []}
    for chi in args.chi:
        if any(row["chi"] == chi and row["shots"] == args.shots for row in report["runs"]):
            raise RuntimeError(f"chi={chi}, shots={args.shots} already recorded")
        row = run_one(circuit, chi, args.shots, out_dir)
        report["runs"].append(row)
        print(f"chi={chi}, {args.shots} shots: sampling {row['sampling_run_seconds']:.2f}s, "
              f"max logged bond {row['mps_diagnostics']['max_logged_bond_dimension']}, "
              f"peak RSS {row['peak_process_rss_kb']/1024:.1f} MiB", flush=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Wrote classical_compare/results/full_d36_mps_preflight.json")


if __name__ == "__main__":
    main()
