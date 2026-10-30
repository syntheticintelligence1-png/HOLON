# Audit round 1, M3: a dry run of the audit-loop machinery (I87)

**Label.** Same family and a dry run. The builder's own session ran the machinery's automated passes, and no auditor of another model family can be run here. So the round is labelled `same`, `dry_run: true`, `counts_toward_convergence: false`, and never counts (HUMAN_ANSWERS Q9). Its findings are real and stay open until fixed. `results/M3/audit_status.json` says converged = false: the streak is 0 of the 3 needed and no round counts.

**Target.** `2b4578afc7bb71c19715c1df680c824b218bd4ec` (I87's build commit). Its `laws/M3`, `results/M3` and `gen/M3` are the base's (`92c98e40`, 136 M3 laws).

**Inputs.** Every input is read from the target commit's tree (git archive into a scratch directory), so `--check` rebuilds both files byte for byte:
- the hostile-review packet `audit/rounds/M3/round1/packet.json`, the input every auditor of the round is given;
- `audit/rounds/M3/round1/a4.json`, auditor A4's output.

## What ran

**A4, vacuity** (`python -m holon audit vacuity --milestone M3 --round 1`). Every law was classified from G11V's records:

| Class | Laws |
|---|---|
| no_premises | 42 |
| not_decided (UNKNOWN) | 24 |
| counter_witness (REFUTED) | 18 |
| vacuous | 0 |
| degenerate | 40 |
| unreadable | 0 |
| ok | 12 |

The 40 degenerate inhabitants:
- **38 PAR codec inhabitants**, by D3: the generator puts zeros everywhere the premises leave free. Each has a representative: the generator's own counting fill, with the premise classes applied, written by the law's own inhabitant generator and accepted by bend2 and BendTT.
- **The FACT kernel law**, by D2: one run is used for both state binders.
- **One DISCH revert law**, by D1: a single step from the initial state.

The last two have no representative search in I87 (F-M3-01).

G11V's in-flight clause, reused unchanged, finds 0 of 8 MIG edges inhabited (F-M3-02). Two REFUTED FACT records label their non_vacuity `counter_witness` although their statements have no premise (F-M3-03). All four canaries are detected: an unsatisfiable premise, a degenerate state inhabitant, a degenerate pure inhabitant and a false oracle answer.

**A4, oracles** (inside `a4.json`):
- M3 has no oracle sidecar, so there is no hypothesis to test.
- keccak256 is the only oracle parameter. It is bound in 52 laws and constrained by no premise.
- All 550 hash-table entries in M3's witnesses and inhabitants equal the real Keccak-256 of their keys.

**Determinism.** Both files rebuild byte for byte from the target. `a4.json` also equals an earlier, independent run at the prereg commit.

**Not run:** A1 (mutation), A2 (hostile input), A3 (regression) and gate evasion. They belong to I45's rounds. The packet lists their targets.

## Findings (`audit/M3_findings.jsonl`)

- **F-M3-01** (medium): two premised PROVED laws have only degenerate inhabitants, and no representative was searched. Fix: I45's A4 round.
- **F-M3-02** (medium): none of the 8 MIG edges has an in-flight inhabitant. This is I28's P5 miss and the lane's known G11V red.
- **F-M3-03** (low): two REFUTED FACT records are labelled `counter_witness` without a premise. Fix: `holon.fact.run`.

No finding is high, so none blocks convergence (CV4). This round cannot count either way.
