"""I33 instrument (the O12 intent contract on M3, the typed extracted Rollup), fixed at the I33 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_o12_m3.py, rules B1-B12. This module writes B1, B3, B8 and B11 out a
second time, independently of holon/, so that the tests can decide what holon must derive, mark and replay. It takes
I64's and I65's instruments (tests_m3/_i64.py, tests_m3/_i65.py, each fixed at its own prereg) for what I33 leaves as it
was: contract validity (K1), the registry hash (K2), the derived law (K3), a contract's state (K5), the marks, the
contracts document and G10 over a milestone's record directories (O5, O7). It reads contract files, law files, result
records and facts documents as JSON, and computes keccak-256 with tests_m2/_keccak.py; nothing here imports holon/.

  NEW_TERMS                          B1: the six additive IR 0.3 terms and their exact key sets
  term_problems(t, facts)            B1: why a term tree breaks B1's shapes over a holon-facts/0.3 document ([] if none)
  reads(law)                         B1: the storage locations a statement reads, [(family, member or None, n keys)]
  family(facts, name)                B1: a storage family of the facts, by name (None when absent)
  real_slot(base, offset, path)      B2: the real slot of a structural key SK{base, offset, [(key word, offset)]}
  sk_of(facts, fam, member, keys)    B2: (base, offset, path) of a read whose key words are given (ints)
  clean_key(facts, fam, k)           B2: a mapping key word as solc hashes it (a narrow key masked to its width)
  derived_law(c, root)               K3 (I64): the law holon contracts derive from an intended contract
  expected_marks(root)               B8 (I65's O5 on M3): {record path: {"contract", "l_weak"}}
  contracts_doc(root)                B8: results/M3/contracts.json as the last step must write it
  g10(root)                          B8: (passed, [reasons]) as G10 must decide it on M3
  witness_problems(rec)              B11: why a REFUTED record of a fixture's derived law is not a refund witness
                                     replayed on the real Rollup ([] if it is one)
"""
from __future__ import annotations

from pathlib import Path

import tests_m3._i64 as I64
import tests_m3._i65 as I65
from tests_m2._keccak import keccak256

ROOT = Path(__file__).resolve().parents[1]
M = "M3"
FACTS = "spec/M2/facts/morph_rollup.extracted.json"
CONTRACT = "C_o12_m3"
LID = f"L_contract_{CONTRACT}"
SCOPE = "L_undo_cancel_Rollup_challengeState_setPause"
MOD = 1 << 256
load, sha256_bytes, canonical = I64.load, I64.sha256_bytes, I64.canonical
problems, content_sha256, derived_law = I64.problems, I64.content_sha256, I64.derived_law

# B1: each new term's exact key set (an optional key in brackets is listed in OPTIONAL)
NEW_TERMS = {
    "sread": {"sread", "keys", "from"},     # Word: the word at a storage location in a state (member optional)
    "wnat": {"wnat"},                       # Nat: N(w) = sum of limb_i * 2^(32 i), the word read as a natural number
    "cmp": {"cmp", "args"},                 # Bool: a comparison of two Nat terms, cmp in {"<=", "<", "=="}
    "ok": {"ok", "from"},                   # Bool: every check of the act's action holds from the state (chk == 0)
    "is": {"is", "act"},                    # Bool: the act is an act of the named action
    "env": {"env", "of"},                   # Word: a field of the act's environment
}
OPTIONAL = {"sread": {"member"}}
CMPS = ("<=", "<", "==")
ENV_FIELDS = ("caller", "msg_value", "block_timestamp", "this", "msg_data_length")


def family(facts: dict, name: str):
    for s in facts.get("storage", []):
        if s.get("name") == name:
            return s
    return None


def _actions(facts: dict) -> set:
    return {a.get("name") for a in facts.get("actions", []) if isinstance(a, dict)}


def term_problems(t, facts: dict, path: str = "$") -> list:
    """B1: every way a term tree breaks the new terms' shapes over a holon-facts/0.3 document: an unknown storage family,
    a member the family does not declare (or a member on a family without fields), a key count that is not the family's
    mapping depth, an unknown action or environment field, a cmp other than <=, < and ==, or two args."""
    out: list = []
    if isinstance(t, list):
        for i, x in enumerate(t):
            out += term_problems(x, facts, f"{path}[{i}]")
        return out
    if not isinstance(t, dict):
        return out
    kind = next((k for k in NEW_TERMS if k in t), None)
    if kind is not None:
        keys = set(t)
        if not (NEW_TERMS[kind] <= keys <= NEW_TERMS[kind] | OPTIONAL.get(kind, set())):
            out.append(f"{path}: a {kind} term has keys {sorted(keys)}")
        if kind == "sread":
            fam = family(facts, t.get("sread"))
            if fam is None:
                out.append(f"{path}: no storage family {t.get('sread')!r}")
            else:
                depth = _depth(fam)
                if not isinstance(t.get("keys"), list) or len(t["keys"]) != depth:
                    out.append(f"{path}: {fam['name']} takes {depth} key(s)")
                names = [f.get("name") for f in _fields(fam)]
                if "member" in t and t["member"] not in names:
                    out.append(f"{path}: {fam['name']} has no member {t['member']!r}")
                if "member" not in t and names:
                    out.append(f"{path}: {fam['name']} is a struct: a read names its member")
        if kind == "cmp" and (t.get("cmp") not in CMPS or not isinstance(t.get("args"), list) or len(t["args"]) != 2):
            out.append(f"{path}: a cmp term is one of {CMPS} over two args")
        if kind == "is" and t.get("is") not in _actions(facts):
            out.append(f"{path}: no action {t.get('is')!r}")
        if kind == "env" and t.get("env") not in ENV_FIELDS:
            out.append(f"{path}: no environment field {t.get('env')!r}")
    for k, v in t.items():
        out += term_problems(v, facts, f"{path}.{k}")
    return out


def _depth(fam: dict) -> int:
    """The number of mapping keys a read of the family takes (nested mappings count each level)."""
    n, v = 0, fam
    while isinstance(v, dict) and v.get("kind") == "mapping":
        n += 1
        v = v.get("inner") if isinstance(v.get("inner"), dict) else None
    return n


def _fields(fam: dict) -> list:
    return fam.get("fields") or []


def reads(law: dict) -> list:
    """B1: the storage locations the statement reads, sorted: (family, member or None, number of keys)."""
    out = set()

    def walk(x):
        if isinstance(x, dict):
            if "sread" in x:
                out.add((x["sread"], x.get("member"), len(x.get("keys") or [])))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(law.get("statement", law))
    return sorted(out, key=lambda r: (r[0], r[1] or "", r[2]))


# ---------------------------------------------------------------------------------------------------- B2
def clean_key(facts: dict, fam: dict, k: int) -> int:
    """A mapping key word as solc hashes it: an address or uintN key masked to its width, a bytesN key left-aligned."""
    kt = str(fam.get("key", "uint256"))
    if kt == "address":
        return k & ((1 << 160) - 1)
    if kt.startswith("uint") and kt[4:].isdigit():
        return k & ((1 << int(kt[4:])) - 1)
    if kt.startswith("bytes") and kt[5:].isdigit():
        n = int(kt[5:])
        return k & (((1 << (8 * n)) - 1) << (256 - 8 * n))
    return k % MOD


def sk_of(facts: dict, fam_name: str, member, keys: list) -> tuple:
    """(base, offset, path) of a read of the family at the given key words (I68's S2 canonical key)."""
    fam = family(facts, fam_name)
    m = next((f for f in _fields(fam) if f.get("name") == member), None)
    mo = int(m.get("slot", 0)) if m else 0
    if not keys:
        return int(fam["slot"]), mo, []
    path = [(clean_key(facts, fam, k), 0) for k in keys]
    path[-1] = (path[-1][0], mo)
    return int(fam["slot"]), 0, path


def real_slot(base: int, offset: int, path: list) -> int:
    """I68's S2: s = base + offset, then for each step (k, o2): s = keccak256(pad32(k) ++ pad32(s)) + o2 (mod 2**256)."""
    s = (base + offset) % MOD
    for k, o2 in path:
        s = (int.from_bytes(keccak256(k.to_bytes(32, "big") + s.to_bytes(32, "big")), "big") + o2) % MOD
    return s


# ---------------------------------------------------------------------------------------------------- B8
def expected_marks(root: Path = ROOT) -> dict:
    return I65.expected_marks(M, root)


def contracts_doc(root: Path = ROOT):
    return I65.contracts_doc(M, root)


def g10(root: Path = ROOT) -> tuple:
    return I65.g10(M, root)


# ---------------------------------------------------------------------------------------------------- B11
def _act(step) -> tuple:
    """(action name, args, env) of a witness step in the typed records' shape (I71's: {"action", "args", "calldata",
    "env": {"block.timestamp", "caller", "calls", "msg.value", "blobhash"}})."""
    if not isinstance(step, dict):
        return None, {}, {}
    return step.get("action"), step.get("args") or {}, step.get("env") or {}


def _int(v) -> int | None:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v, 0)
        except ValueError:
            return None
    return None


def witness_problems(rec: dict) -> list:
    """B11: a REFUTED record of a fixture's derived law is a refund witness replayed on the real Rollup when its witness
    (the typed records' shape: {"prefix", "x", "y", ...}, the reachable state s being the prefix's run from s0) binds x
    to a challengeState act whose msg.value is at least 1 and y to a setPause act whose _status is true, and its replay
    status is "passed" (the direct test on the real contract confirmed the difference)."""
    out = []
    if not isinstance(rec, dict) or rec.get("status") != "REFUTED":
        return ["not a REFUTED record"]
    w = rec.get("witness") or {}
    xn, _, xe = _act(w.get("x"))
    yn, ya, _ = _act(w.get("y"))
    if xn != "challengeState":
        out.append(f"x is {xn!r}, not challengeState")
    if (_int(xe.get("msg.value")) or 0) < 1:
        out.append("x's msg.value is not at least 1")
    if yn != "setPause":
        out.append(f"y is {yn!r}, not setPause")
    if _int(ya.get("_status")) != 1:
        out.append("y's _status is not true")
    if not isinstance(w.get("prefix"), list):
        out.append("the witness has no prefix (the reachable state s)")
    if (rec.get("replay") or {}).get("status") != "passed":
        out.append(f"replay status {(rec.get('replay') or {}).get('status')!r}, not passed")
    return out
