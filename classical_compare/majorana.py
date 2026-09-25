"""Jordan-Wigner Majorana-weight truncation for selected Z-parity observables.

Adapted from the user's random_graph classical cutoff implementation. This is
an observable estimator, not a sampler for random-circuit bitstrings.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

from qiskit import QuantumCircuit


class TermLimit(RuntimeError):
    pass


def _pauli_product(a: str, b: str) -> tuple[complex, str]:
    if a == "I":
        return 1, b
    if b == "I":
        return 1, a
    if a == b:
        return 1, "I"
    return {
        ("X", "Y"): (1j, "Z"), ("Y", "X"): (-1j, "Z"),
        ("Y", "Z"): (1j, "X"), ("Z", "Y"): (-1j, "X"),
        ("Z", "X"): (1j, "Y"), ("X", "Z"): (-1j, "Y"),
    }[(a, b)]


def _cz_image(a: str, b: str) -> tuple[float, str, str]:
    left = {"I": "II", "X": "XZ", "Y": "YZ", "Z": "ZI"}[a]
    right = {"I": "II", "X": "ZX", "Y": "ZY", "Z": "IZ"}[b]
    p0, c0 = _pauli_product(left[0], right[0])
    p1, c1 = _pauli_product(left[1], right[1])
    phase = p0 * p1
    assert abs(phase.imag) < 1e-12
    return float(phase.real), c0, c1


CZ_MAP = {(a, b): _cz_image(a, b) for a in "IXYZ" for b in "IXYZ"}


def majorana_weight(word: str) -> int:
    """Number of Jordan-Wigner Majorana factors in a q0-first Pauli word."""
    mask = 0
    for q, char in enumerate(word):
        prefix = (1 << (2 * q)) - 1
        if char == "X":
            mask ^= prefix ^ (1 << (2 * q))
        elif char == "Y":
            mask ^= prefix ^ (1 << (2 * q + 1))
        elif char == "Z":
            mask ^= (1 << (2 * q)) | (1 << (2 * q + 1))
        elif char != "I":
            raise ValueError(f"invalid Pauli character {char}")
    return mask.bit_count()


def _branches(word: str, name: str, qubits: tuple[int, ...], angle: float | None):
    if name in {"barrier", "id"}:
        return ((1.0, word),)
    if name == "cz":
        a, b = qubits
        phase, ca, cb = CZ_MAP[word[a], word[b]]
        chars = list(word)
        chars[a], chars[b] = ca, cb
        return ((phase, "".join(chars)),)
    if name not in {"rx", "rz"} or angle is None or len(qubits) != 1:
        raise ValueError(f"unsupported instruction {name}")
    q = qubits[0]
    c, s = math.cos(angle), math.sin(angle)
    char = word[q]
    if name == "rz":
        mapping = {"I": ((1, "I"),), "Z": ((1, "Z"),),
                   "X": ((c, "X"), (-s, "Y")),
                   "Y": ((s, "X"), (c, "Y"))}
    else:
        mapping = {"I": ((1, "I"),), "X": ((1, "X"),),
                   "Y": ((c, "Y"), (-s, "Z")),
                   "Z": ((s, "Y"), (c, "Z"))}
    out = []
    for factor, mapped in mapping[char]:
        if abs(factor) > 1e-14:
            chars = list(word)
            chars[q] = mapped
            out.append((factor, "".join(chars)))
    return out


def z_parity_expectation(
    circuit: QuantumCircuit,
    support: Sequence[int],
    max_weight: int,
    max_terms: int = 20_000,
) -> dict[str, float | int]:
    """Propagate output Z parity backwards and discard words over max_weight."""
    if not support or max_weight < 1:
        raise ValueError("nonempty support and positive cutoff required")
    n = circuit.num_qubits
    if any(q < 0 or q >= n for q in support):
        raise ValueError("support outside circuit")
    chars = ["I"] * n
    for q in support:
        chars[q] = "Z"
    terms = {"".join(chars): 1.0}
    indices = {q: i for i, q in enumerate(circuit.qubits)}
    peak = 1
    discarded = 0
    for rev_index, item in enumerate(reversed(circuit.data)):
        if item.clbits:
            raise ValueError("remove measurements before Majorana propagation")
        qubits = tuple(indices[q] for q in item.qubits)
        angle = float(item.operation.params[0]) if item.operation.name in {"rx", "rz"} else None
        updated: dict[str, float] = defaultdict(float)
        for word, coeff in terms.items():
            for factor, image in _branches(word, item.operation.name, qubits, angle):
                updated[image] += coeff * factor
        terms = {}
        for word, coeff in updated.items():
            if abs(coeff) <= 1e-14 or majorana_weight(word) > max_weight:
                discarded += 1
            else:
                terms[word] = coeff
        if len(terms) > max_terms:
            raise TermLimit(f">{max_terms} terms at reversed instruction {rev_index}")
        peak = max(peak, len(terms))
        if not terms:
            break
    expectation = sum(c for word, c in terms.items() if set(word) <= {"I", "Z"})
    return {"expectation": float(expectation), "surviving_terms": len(terms),
            "peak_terms": peak, "discarded_terms_accumulated": discarded}
