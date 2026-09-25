"""Check that capped MPS statevector snapshots predict sampled bitstrings."""

import unittest

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


class TestMpsSampling(unittest.TestCase):
    def test_snapshot_matches_samples(self):
        circuit = QuantumCircuit(5)
        for q in range(5):
            circuit.rx(0.3 + 0.17 * q, q)
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 4), (0, 4)):
            circuit.cz(a, b)
        for q in range(5):
            circuit.rz(0.4 + 0.11 * q, q)
            circuit.rx(0.7 + 0.19 * q, q)
        simulator = AerSimulator(method="matrix_product_state",
                                 matrix_product_state_max_bond_dimension=2,
                                 matrix_product_state_truncation_threshold=0.0,
                                 seed_simulator=123)
        saved = circuit.copy()
        saved.save_statevector()
        vector = np.asarray(simulator.run(saved).result().get_statevector())
        probabilities = np.abs(vector)**2
        self.assertAlmostEqual(float(probabilities.sum()), 1.0, places=10)

        measured = circuit.copy()
        measured.measure_all()
        counts = simulator.run(measured, shots=50_000).result().get_counts()
        empirical = np.zeros(2**5)
        for key, count in counts.items():
            empirical[int(key, 2)] = count / 50_000
        self.assertLess(float(np.abs(empirical - probabilities).sum() / 2), 0.025)


if __name__ == "__main__":
    unittest.main()
