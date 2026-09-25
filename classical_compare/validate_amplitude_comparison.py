"""Control state-vector ordering and the exact 21q patch reference."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, qpy
from qiskit_aer import AerSimulator

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "quantum/pair_prepared"


def state(qc: QuantumCircuit, method: str, chi: int | None = None) -> np.ndarray:
    circuit = qc.copy()
    circuit.save_statevector(label="psi")
    kwargs = {"method": method, "precision": "double", "max_memory_mb": 6000}
    if chi is not None:
        kwargs.update(matrix_product_state_max_bond_dimension=chi,
                      matrix_product_state_truncation_threshold=0.0)
    result = AerSimulator(**kwargs).run(circuit).result()
    if not result.success:
        raise RuntimeError(result.status)
    return np.asarray(result.data(0)["psi"], dtype=np.complex128)


def main() -> None:
    toy = QuantumCircuit(3)
    toy.h(0)
    toy.cx(0, 1)
    toy.ry(0.37, 2)
    toy.cz(1, 2)
    a = state(toy, "statevector")
    b = state(toy, "matrix_product_state", 8)
    toy_error = float(np.linalg.norm(a - b))
    if toy_error > 1e-12:
        raise RuntimeError(f"MPS statevector extraction control failed: {toy_error}")

    with (PATCH / "patch0_d36_logical.qpy").open("rb") as handle:
        patch = qpy.load(handle)[0]
    patch = patch.remove_final_measurements(inplace=False)
    exact = state(patch, "statevector")
    with np.load(PATCH / "patch0_d36_ideal_probabilities.npz") as data:
        probabilities = data["probabilities"]
    reference_error = float(np.max(np.abs(np.abs(exact)**2 - probabilities)))
    if reference_error > 1e-11:
        raise RuntimeError(f"exact patch probabilities disagree: {reference_error}")
    report = {"toy_mps_vs_exact_state_l2_error": toy_error,
              "patch_exact_vs_frozen_probabilities_max_abs_error": reference_error,
              "toy_control_passed": True, "patch_reference_passed": True}
    output = ROOT / "classical_compare/results/amplitude_comparison_validation.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
