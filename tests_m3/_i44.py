"""I44's instrument (the prereg sidecar of key I44 = I44b; written without holon's measure or ranking code, and
importing nothing from holon/). It decides the key's predictions two ways:

1. An independent computation over the committed inputs, by this module's own reading of the contract's rule M-NAT
   (the docstring of tests_m3/test_measures_i44.py): nat_observation folds the model's written words of each of a
   REFUTED NAT witness's two runs in replay/<M>/nat/report.json, pairs the steps of the square's two sides by label,
   and compares the end versions; nat_mass counts the components that differ.
2. The predicted values, fixed here at the prereg: NAT_EXPECTED (the six composition laws), NAT_UNKNOWN (the three
   cutover squares), PUBLIC_INPUT (I84's four public-input laws, for stage 2), and the stage-2 expectations for DISCH,
   F(Z, derivation) and persistence.

How NAT_EXPECTED was derived (by hand, before any measure code ran; thresholds.observed_before_prereg lists what was
read). Each composition square compares "the late initializer's migration, then the early initializer" (left) with
"the early initializer at the old version, then the migration" (right). On the left the early initializer reverts
(the late reinitializer has raised _initialized), so it writes nothing; on the right it succeeds. The initializers'
writes are the per-version documents' (gen/M3/versions/documents/V*.json, writes and storage slots), the same at every
version the squares use:
  initialize   slot 0 (_initialized/_initializing), 51 (_owner = the caller), 101 (_paused = 0), and the six parameters
               at 151 (l1StakingContract), 155, 156, 152, 153, 169
  initialize2  slot 0, and committedStateRoots[lastCommittedBatchIndex] (a hashed word; the key is 0, which no step of
               the witnesses writes) = its parameter
  initialize3  slot 0, 172 (rollupDelayPeriod) = its parameter
  initialize4  slot 0, 174 (legacyCutoverBatchIndex) = its second parameter, 151 (submitterContract) = its first
The witnesses' arguments are all nonzero except initialize4's second (0). So the storage words where the two ends
differ are the early initializer's words that the migration does not write and whose written value is not the start's:
slot 0 ends at the late version on both sides; 101 is written 0, which the start holds; for initialize4, 151 ends at
initialize4's value on both sides. The op's success differs (ok against revert); the migration succeeds on both sides
and both end at the late version. Mass = 1 (the op's outcome) + the differing words.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = "M3"
BASE = "76e7d555"   # the lead after I35's merge (PR #75): I29's 9 NAT laws present, holon-rules/1.9
HEADS_READ = {"I84": "74f03416", "I89": "a66529bb"}   # the branches read for the stage-2 predictions
ZERO = 0

# ---------------------------------------------------------------- predicted values (fixed at the prereg)
# law id -> (mass, the declared storage slots that differ, the number of hashed words that differ, the step labels
# whose success differs, whether the end versions differ)
_INIT_WORDS = frozenset({51, 151, 152, 153, 155, 156, 169})
NAT_EXPECTED = {
    "L_nat_comp_Rollup_initialize_initialize2": (8, _INIT_WORDS, 0, ("initialize",), False),
    "L_nat_comp_Rollup_initialize_initialize3": (8, _INIT_WORDS, 0, ("initialize",), False),
    "L_nat_comp_Rollup_initialize_initialize4": (7, _INIT_WORDS - {151}, 0, ("initialize",), False),
    "L_nat_comp_Rollup_initialize2_initialize3": (2, frozenset(), 1, ("initialize2",), False),
    "L_nat_comp_Rollup_initialize2_initialize4": (2, frozenset(), 1, ("initialize2",), False),
    "L_nat_comp_Rollup_initialize3_initialize4": (2, frozenset({172}), 0, ("initialize3",), False),
}
NAT_UNKNOWN = (
    "L_nat_sq_Rollup_V10_V11_batchDataStore_proveState",
    "L_nat_sq_Rollup_V10_V11_submitterContract_challengeState",
    "L_nat_sq_Rollup_V10_V11_submitterContract_proveState",
)
DECLARED_BELOW = 1 << 64   # a declared slot is a small number; a mapping entry's word is a keccak hash above it

# stage 2 (after I84 lands): M-FACT on the public_input sub-form: law id -> (kind, value, lower, upper), in bits
PUBLIC_INPUT = {
    "L_fact_pi_Rollup_commitBatchWithProof_LastBlockNumber": ("value", 64.0, 64.0, 64.0),
    "L_fact_pi_Rollup_commitBatchWithProof_Version": ("bound", None, 1.0, 1.584963),
    "L_fact_pi_Rollup_commitBatchWithProof_BatchIndex": ("bound", None, 1.0, 64.0),
    "L_fact_pi_Rollup_commitBatchWithProof_TotalL1MessagePopped": ("bound", None, 0, 64.0),
}
PI_PAIR = "F(PI, parent lbn)"
PI_LAW = "L_fact_pi_Rollup_commitBatchWithProof_LastBlockNumber"
Z_PAIR = "F(Z, derivation)"
PERSISTENCE_RULES = ("UNDO", "FACT", "SORT", "NAT")   # and the PAR laws whose claim is a versioned machine's init term
NAT_KINDS = {"value": 6, "bound": 3}


# ---------------------------------------------------------------- reading
def load(p) -> dict:
    return json.loads(Path(p).read_text())


def nat_report(root: Path = ROOT) -> dict:
    p = root / "replay" / M / "nat" / "report.json"
    return load(p) if p.is_file() else {}


def _witness_sha256(w: dict) -> str:
    return hashlib.sha256(json.dumps(w, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _side_trace(w: dict, side: str) -> list:
    return list(w.get("trace") or []) + [{k: v for k, v in st.items() if k != "revert"}
                                         for st in (w.get("square") or {}).get(side) or []]


def _word(v) -> int:
    return int(v, 16) if isinstance(v, str) and v.startswith("0x") else ZERO


def nat_observation(lid: str, rec: dict, report: dict) -> dict | None:
    """The model's observation of each side of a REFUTED NAT witness, from the report's runs <lid>:left and
    <lid>:right replaying it (same witness sha256, same trace), else None: {side: {"storage": {word: value},
    "outcomes": {(label, k): ok}, "version": v}}."""
    w = rec.get("witness") or {}
    runs = {r.get("name"): r for r in report.get("runs") or [] if isinstance(r, dict)}
    out = {}
    for side in ("left", "right"):
        r = runs.get(f"{lid}:{side}")
        if r is None or r.get("witness_sha256") != _witness_sha256(w) or r.get("trace") != _side_trace(w, side):
            return None
        steps = r.get("steps") or []
        storage: dict[int, int] = {}
        for st in steps:
            for s in st.get("slots") or []:
                storage[_word(s.get("slot"))] = _word(s.get("model"))
        n0 = len(w.get("trace") or [])
        sq = (w.get("square") or {}).get(side) or []
        outcomes, seen = {}, {}
        for j, st in enumerate(sq):
            lab = st.get("label")
            k = seen.get(lab, 0)
            seen[lab] = k + 1
            outcomes[(lab, k)] = steps[n0 + j].get("model") == "ok"
        out[side] = {"storage": storage, "outcomes": outcomes, "version": sq[-1].get("version") if sq else None}
    return out


def nat_mass(obs: dict) -> tuple[int, list[int], list[str], bool]:
    """(mass, the differing words, the labels whose success differs, whether the end versions differ)."""
    a, b = obs["left"], obs["right"]
    words = sorted(x for x in set(a["storage"]) | set(b["storage"])
                   if a["storage"].get(x, ZERO) != b["storage"].get(x, ZERO))
    pairs = sorted((p for p in set(a["outcomes"]) | set(b["outcomes"])
                    if a["outcomes"].get(p) != b["outcomes"].get(p)), key=lambda p: (str(p[0]), p[1]))
    version = a["version"] != b["version"]
    return len(words) + len(pairs) + (1 if version else 0), words, sorted({str(lab) for lab, _ in pairs}), version
