# Nighthawk 61-qubit RCS follow-up

Public article source and analysis code for our independent follow-up to [Sedrakyan et al., arXiv:2609.28657](https://arxiv.org/abs/2609.28657). The original paper's circuit and measurements are available in [BramDo/rcs-nighthawk](https://github.com/BramDo/rcs-nighthawk). This repository is separate from the paper authors' release.

## Articles

- [Nederlandse reeks](https://edukaizen.nl/nighthawk-61-qubit-random-circuit-sampling/)
- [English series](https://edukaizen.nl/nighthawk-61-qubit-random-circuit-sampling-en/)

Both series have an overview and four parts: the paper's method, our 61-qubit IBM run, the classical MPS comparison, and RCS theory and applications.

## Scope of the follow-up

Our IBM `ibm_phoenix` job `dar90plvr3kc73eij3vg` returned one million outcomes from the released 61-qubit, 36-cycle circuit, with 19 seconds of provider-reported QPU usage. A local capped-MPS run at bond dimension χ=128 took 1,248.95 seconds for 1,000 samples. This is a large measured runtime lead over **that tested MPS implementation**. The new full-width quantum run has no directly measured ideal-circuit XEB, and the MPS output has not been shown to match its quality. The articles explain these boundaries and cite the paper's separate fidelity estimates.

## Code and data policy

`publication/rcs61-series/` contains the source for the live Dutch and English pages and the guarded WordPress publisher. `classical_compare/` and `quantum/` contain analysis scripts. The raw new IBM million-shot file, account metadata, Fire Opal credential workflows, and local QPY/NPZ research artifacts are **not included in this public repository**. The paper's original data remain available from its linked repository. The code expects the released paper repository at `rcs-nighthawk/` and, for comparisons with our new run, a local file at `quantum/full_60qs/full_d36_1000000_shots.npz`.

No script in this public snapshot submits a new quantum job.
