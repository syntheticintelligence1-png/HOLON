"""Oracle sidecar rules (G3) and hypothesis checks (A4, G11V) for hashes and oracles as parameters (I12).

  validate(doc) -> [problem]                       the holon-oracles/0.1 rules; [] when valid
  check(sidecar, out_dir, root=ROOT) -> {hypothesis id: result}
  python -m holon oracle check --milestone M2 [--root DIR]

Format: tests_m2/test_oracles.py (module docstring) and holon.gen.oracles. One optional key extends an entry:
"real_oracle": the name of an implementation of the real oracle available here (REAL_ORACLES), against which
A4 tests the hypothesis. An entry without one is "untestable_here".

A result is
  {"oracle": <entry id>, "kind": "cf" | "hyp" | None,
   "status": "checked" | "mismatch" | "untestable_here" | "not_in_scope", "reason": str (untestable_here,
   not_in_scope), "detail": str (checked, mismatch),
   "instance": {"status": "checked" | "failed" | "per_premise" | "not_applicable", "law", "proof", "reason"}}
  * status (A4): the hypothesis tested against the real oracle where one is available here: a kind-hyp
    predicate is evaluated on it; a kind-cf hypothesis (CF(p, S) for every finite S) is tested on a fixed
    sample of the parameter's domain, all of whose images must differ. "checked" is a test on that sample,
    not a proof.
  * instance (G11V): for kind hyp, a generated Bend law states that the entry's concrete instance satisfies
    the predicate (its conjuncts with p replaced by the instance), proved by evaluation; "checked" when Bend
    (and BendTT, when enabled) accepts it, else "failed". Files: out_dir/<hypothesis id>/{LAWS.bend,
    PROOF.bend}. Kind cf: "per_premise" (each law states its own S, inhabited per law, holon.inhabit). A
    not_in_scope entry: "not_applicable". A sidecar is checked on its own: templates render
    ${param:NAME:DEFAULT} as DEFAULT.

The CLI writes results/<M>/hypotheses.json (keyed by hypothesis id, sorted) and gen/<M>/oracles/. It merges:
the Hyp-Z0-kzg entry written by `holon oracle zero-blob` (I3) is kept exactly as written; every other
sidecar hypothesis gets a result; nothing else is kept.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from . import bend
from .gen import oracles as O

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = Path("spec") / "schemas" / "law_ir_0_3.schema.json"
ZERO_BLOB = "Hyp-Z0-kzg"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HYP_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
GROUND_BUILTINS = {"eq_nat", "eq_bool", "eq_nats"}
MODEL_TERMS = {"var", "s0", "run", "step", "obs", "obsv", "act", "trace", "mig", "proj", "cat"}


# ---------------------------------------------------------------- real oracles available here (A4)
def _words(ty: str, v) -> bytes:
    """A value of the parameter's domain as the bytes the real hash reads: a Nat is one 32-byte big-endian
    word, a List<Nat> the concatenation of its words (abi.encodePacked of a bytes32[]), a Bool one byte."""
    if ty == "Nat":
        return int(v).to_bytes(32, "big")
    if ty == "Bool":
        return b"\x01" if v else b"\x00"
    if ty == "List<Nat>":
        return b"".join(int(x).to_bytes(32, "big") for x in v)
    raise ValueError(f"no byte encoding for {ty}")


def _keccak256(ty: str, v) -> int:
    from .keccak import keccak256
    return int.from_bytes(keccak256(_words(ty, v)), "big")


def _keccak_selftest() -> bool:
    from .keccak import keccak256
    return keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470" and \
        keccak256(b"abc").hex() == "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"


REAL_ORACLES = {
    "keccak256": {"fn": _keccak256, "selftest": _keccak_selftest, "domains": ("Nat", "Bool", "List<Nat>"),
                  "doc": "Ethereum Keccak-256 of holon/keccak.py, over the domain value's 32-byte words"},
}


def _sample(ty: str) -> list:
    """The fixed sample a kind-cf hypothesis is tested on (deterministic)."""
    if ty == "Nat":
        return list(range(256))
    if ty == "Bool":
        return [False, True]
    if ty == "List<Nat>":
        vals = range(16)
        return [[]] + [[a] for a in vals] + [[a, b] for a in vals for b in vals]
    raise ValueError(f"no sample for {ty}")


# ---------------------------------------------------------------- validate (G3 and the sidecar rules)
def _keys(t, out: set) -> set:
    if isinstance(t, dict):
        out |= set(t)
        if "fn" in t and "args" in t:
            out.add("fn:" + str(t["fn"]))
        if "app" in t:
            out.add("app:" + str(t["app"]))
        for v in t.values():
            _keys(v, out)
    elif isinstance(t, list):
        for v in t:
            _keys(v, out)
    return out


def _schema(root: Path) -> dict:
    return json.loads((Path(root) / SCHEMA).read_text(encoding="utf-8"))


def validate(doc: dict, root: Path = ROOT) -> list[str]:
    """Every problem with a holon-oracles/0.1 document; [] when it is valid. G3: a cf over "*" (global
    injectivity, whitepaper L13) anywhere in a predicate is rejected."""
    from . import schema as S
    bad: list[str] = []
    if not isinstance(doc, dict):
        return ["not a JSON object"]
    if doc.get("oracles_version") != O.SIDECAR_VERSION:
        bad.append(f"oracles_version is not {O.SIDECAR_VERSION}")
    if not isinstance(doc.get("doc"), str):
        bad.append("doc: missing or not a string")
    entries = doc.get("oracles")
    if not isinstance(entries, list) or not entries:
        return bad + ["oracles: missing or empty"]
    sch = _schema(root)
    ids = [e.get("id") if isinstance(e, dict) else None for e in entries]
    hids = [e["hypothesis"].get("id") if isinstance(e, dict) and isinstance(e.get("hypothesis"), dict) else None
            for e in entries]
    if len(set(ids)) != len(ids):
        bad.append("entry ids are not unique")
    if len(set(hids)) != len(hids):
        bad.append("hypothesis ids are not unique")
    ptypes: dict[str, str] = {}
    for e in entries:
        if not isinstance(e, dict):
            bad.append("an entry is not an object")
            continue
        w = e.get("id")
        if not isinstance(w, str) or not w:
            bad.append(f"{w!r}: id")
        if not isinstance(e.get("oracle"), str) or not e["oracle"]:
            bad.append(f"{w}: oracle (canonical name) missing")
        par, hyp = e.get("parameter"), e.get("hypothesis")
        if not isinstance(par, dict) or not isinstance(par.get("name"), str) or not IDENT.fullmatch(par["name"]):
            bad.append(f"{w}: parameter.name is not an identifier")
            continue
        if not isinstance(hyp, dict) or not isinstance(hyp.get("id"), str) or not HYP_ID.fullmatch(hyp["id"]) \
                or not isinstance(hyp.get("doc"), str):
            bad.append(f"{w}: hypothesis needs an id matching {HYP_ID.pattern} and a doc")
            continue
        if "family" in hyp and (not isinstance(hyp["family"], str) or not hyp["family"]):
            bad.append(f"{w}: hypothesis.family must be a non-empty string")
        if "instance" not in e:
            bad.append(f"{w}: no instance key")
        if not isinstance(e.get("ledger", []), list) or not all(isinstance(x, str) for x in e.get("ledger", [])):
            bad.append(f"{w}: ledger must be a list of ledger ids")
        if "real_oracle" in e and e["real_oracle"] not in REAL_ORACLES:
            bad.append(f"{w}: real_oracle {e['real_oracle']!r} is none of {sorted(REAL_ORACLES)}")
        status = e.get("status")
        if status == "not_in_scope":
            if not isinstance(e.get("reason"), str) or not e["reason"].strip():
                bad.append(f"{w}: a not_in_scope entry states its reason")
            continue
        if status != "modelled":
            bad.append(f"{w}: status {status!r} is neither modelled nor not_in_scope")
            continue
        sig = O.fn_types(par.get("type"))
        if sig is None:
            bad.append(f"{w}: a modelled parameter needs a Fn<A,B> type")
            continue
        if ptypes.setdefault(par["name"], par["type"]) != par["type"]:
            bad.append(f"{w}: parameter {par['name']} has two types ({ptypes[par['name']]}, {par['type']})")
        if sig[0] not in O.KEY_TYPES:
            bad.append(f"{w}: parameter domain {sig[0]} is none of {list(O.KEY_TYPES)}")
        inst = e.get("instance")
        if not isinstance(inst, dict) or not isinstance(inst.get("bend"), str) or not inst["bend"].strip():
            bad.append(f"{w}: a modelled entry needs a concrete instance (a non-empty Bend template)")
        elif "?" in inst["bend"]:
            bad.append(f"{w}: the instance template contains '?' (an escape-hatch character)")
        kind = hyp.get("kind")
        if kind not in ("cf", "hyp"):
            bad.append(f"{w}: hypothesis.kind {kind!r} is neither cf nor hyp")
            continue
        if kind == "cf":
            if "predicate" in hyp:
                bad.append(f"{w}: a kind-cf hypothesis has no predicate (each law states its own finite set)")
            continue
        pred = hyp.get("predicate")
        if not isinstance(pred, list) or not pred:
            bad.append(f"{w}: a kind-hyp hypothesis needs a non-empty predicate")
            continue
        for p in pred:
            if not isinstance(p, dict):
                bad.append(f"{w}: predicate item {p!r} is not an object")
                continue
            if "cf" in p and not isinstance(p["cf"], dict):
                bad.append(f"{w}: malformed cf in the predicate")
                continue
            if "cf" in p and (not isinstance(p["cf"].get("set"), list) or not p["cf"]["set"]):
                bad.append(f"{w}: global injectivity: a cf over {p['cf'].get('set')!r} in the predicate (G3, L13)")
            elif S.errors(p, {"$ref": "#/$defs/premise"}, root=sch):
                bad.append(f"{w}: predicate item is not an IR 0.3 premise: {json.dumps(p, sort_keys=True)}")
            if "hyp" in p:
                bad.append(f"{w}: a predicate cannot cite another hypothesis")
            ks = _keys(p, set())
            if ks & MODEL_TERMS:
                bad.append(f"{w}: predicate is not ground (it uses {sorted(ks & MODEL_TERMS)})")
            apps = {k[4:] for k in ks if k.startswith("app:")}
            if apps - {par["name"]}:
                bad.append(f"{w}: predicate applies {sorted(apps - {par['name']})}, not only its parameter {par['name']}")
            fns = {k[3:] for k in ks if k.startswith("fn:")}
            if fns - GROUND_BUILTINS:
                bad.append(f"{w}: predicate calls {sorted(fns - GROUND_BUILTINS)}: only {sorted(GROUND_BUILTINS)}")
            if "cf" in p and p["cf"].get("fn") != par["name"]:
                bad.append(f"{w}: cf over {p['cf'].get('fn')!r}, not its parameter {par['name']}")
    return bad


# ---------------------------------------------------------------- ground predicates: evaluation and Bend
class _Ground:
    """Ground predicate terms (nat, bool, nats, plus, app p, eq builtins), typed by the entry's Fn<A,B>."""

    def __init__(self, p: str, A: str, B: str):
        self.p, self.A, self.B = p, A, B

    def ty(self, t) -> str:
        if "nat" in t or "plus" in t:
            return "Nat"
        if "bool" in t:
            return "Bool"
        if "nats" in t:
            return "List<Nat>"
        if "app" in t:
            return self.B
        if "fn" in t:
            return "Bool"
        raise ValueError(f"not a ground term: {t}")

    def value(self, t, f):
        if "nat" in t:
            return int(t["nat"])
        if "bool" in t:
            return bool(t["bool"])
        if "nats" in t:
            return [int(x) for x in t["nats"]]
        if "plus" in t:
            return self.value(t["plus"][0], f) + self.value(t["plus"][1], f)
        if "app" in t:
            return f(self.value(t["args"][0], f))
        if "fn" in t:
            a, b = (self.value(x, f) for x in t["args"])
            return a == b
        raise ValueError(f"not a ground term: {t}")

    def holds(self, prem, f) -> bool:
        if "cf" in prem:
            vs = [self.value({"app": self.p, "args": [x]}, f) for x in prem["cf"]["set"]]
            return len({json.dumps(v) for v in vs}) == len(vs)
        if "neq" in prem:
            return self.value(prem["neq"][0], f) != self.value(prem["neq"][1], f)
        return self.value(prem["eq"][0], f) == self.value(prem["eq"][1], f)

    # Bend, with p replaced by the instance function `inst`
    def bend(self, t, inst: str) -> str:
        if "nat" in t:
            return f"{int(t['nat'])}n"
        if "bool" in t:
            return "True{}" if t["bool"] else "False{}"
        if "nats" in t:
            return "[" + ", ".join(f"{int(x)}n" for x in t["nats"]) + "]" if t["nats"] else "Nil{}"
        if "plus" in t:
            return f"Nat.add({self.bend(t['plus'][0], inst)}, {self.bend(t['plus'][1], inst)})"
        if "app" in t:
            return f"{inst}({self.bend(t['args'][0], inst)})"
        if "fn" in t:
            fn = {"eq_nat": "Nat.is_eq", "eq_bool": "eq_bool", "eq_nats": "eq_list_nat"}[t["fn"]]
            return f"{fn}({', '.join(self.bend(x, inst) for x in t['args'])})"
        raise ValueError(f"not a ground term: {t}")

    def eq_of(self, ty: str) -> str:
        return {"Nat": "Nat.is_eq", "Bool": "eq_bool", "List<Nat>": "eq_list_nat"}[ty]

    def conjuncts(self, prem, inst: str) -> list[tuple[str, str, str]]:
        """(lhs, rhs, Bend type) per equation: a != b and each pair of a cf set in decidable form
        eq_T(a, b) == False{} (as holon.gen.mlaws renders premises)."""
        from .gen.machine import bt
        if "cf" in prem:
            S = prem["cf"]["set"]
            ap = lambda x: self.bend({"app": self.p, "args": [x]}, inst)  # noqa: E731
            return [(f"{self.eq_of(self.B)}({ap(S[i])}, {ap(S[j])})", "False{}", "Bool")
                    for i in range(len(S)) for j in range(i + 1, len(S))]
        if "neq" in prem:
            a, b = prem["neq"]
            return [(f"{self.eq_of(self.ty(a))}({self.bend(a, inst)}, {self.bend(b, inst)})", "False{}", "Bool")]
        a, b = prem["eq"]
        return [(self.bend(a, inst), self.bend(b, inst), bt(self.ty(a)))]


def _rel(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(Path(p).resolve())


def instance_law(e: dict, shown: str) -> tuple[str, str, str]:
    """(law name, LAWS.bend, PROOF.bend): the entry's concrete instance satisfies its kind-hyp predicate."""
    from .gen.machine import PRELUDE_HEAD, PRELUDE_TAIL, bt
    A, B = O.fn_types(e["parameter"]["type"])
    p = e["parameter"]["name"]
    g = _Ground(p, A, B)
    inst = O.inst_name(e["id"])
    body = O.render_template(e["instance"]["bend"], ["x"], None)
    conj = [c for prem in e["hypothesis"]["predicate"] for c in g.conjuncts(prem, inst)]
    name = "hyp_" + re.sub(r"[^a-z0-9_]", "_", e["hypothesis"]["id"].lower())
    defs = [f"# the concrete instance of {e['id']}", f"def {inst}(x: {bt(A)}) -> {bt(B)}:", f"  {body}", ""]
    law = [f"law {name}:"] + [f"  exs c{i}: {{{a} == {b} : {t}}}" for i, (a, b, t) in enumerate(conj[:-1])]
    law.append(f"  {{{conj[-1][0]} == {conj[-1][1]} : {conj[-1][2]}}}")
    used = "\n".join(defs + law)
    prelude = PRELUDE_HEAD + PRELUDE_TAIL
    pnames = re.findall(r"^def\s+(\w+)\(", prelude, re.M)
    need = any(re.search(rf"(?<![\w.]){n}\(", used) for n in pnames)
    head = [f"# GENERATED by holon.oracle_check from {shown}; do not edit.".replace("?", ""),
            f"# hypothesis {e['hypothesis']['id']} (entry {e['id']}): its concrete instance satisfies the predicate.",
            "import Base", ""]
    laws = "\n".join(head + ([prelude] if need else []) + defs + law) + "\n"
    tup = "{==}"
    for _ in conj[:-1]:
        tup = f"({{==}}, {tup})"
    proof = "\n".join(["# GENERATED by holon.oracle_check; accepted only if Bend checks it.", "import Base",
                       "import ./LAWS.bend as Laws", "", "# class evaluate: every conjunct by computation",
                       f"def Laws.{name}():", f"  {tup}"]) + "\n"
    return name, laws, proof


def _a4(e: dict) -> dict:
    """A4: the hypothesis against the real oracle, where the entry names one available here."""
    kind = e["hypothesis"]["kind"]
    real = e.get("real_oracle")
    if real is None:
        return {"status": "untestable_here",
                "reason": f"no implementation of the real {e['oracle']} oracle is available here (the entry names "
                          "no real_oracle): the hypothesis is checked only through its concrete instance (G11V)"}
    R = REAL_ORACLES[real]
    A, B = O.fn_types(e["parameter"]["type"])
    if A not in R["domains"]:
        return {"status": "untestable_here", "reason": f"{real} does not read values of {A}"}
    if not R["selftest"]():
        return {"status": "untestable_here", "reason": f"{real} failed its known-answer self-test here"}
    f = lambda x: R["fn"](A, x)  # noqa: E731
    if kind == "cf":
        xs = _sample(A)
        seen: dict = {}
        for x in xs:
            d = f(x)
            if d in seen:
                return {"status": "mismatch", "detail": f"{real} collides on {json.dumps(seen[d])} and {json.dumps(x)}"}
            seen[d] = x
        return {"status": "checked", "detail": f"{real} ({R['doc']}) gives {len(xs)} pairwise different images on "
                                               f"the fixed sample of {A} (a test on a sample, not a proof)"}
    g = _Ground(e["parameter"]["name"], A, B)
    bad = [i for i, prem in enumerate(e["hypothesis"]["predicate"]) if not g.holds(prem, f)]
    if bad:
        return {"status": "mismatch", "detail": f"{real} falsifies predicate items {bad}"}
    return {"status": "checked", "detail": f"{real} ({R['doc']}) satisfies every predicate item"}


def check(sidecar: Path, out_dir: Path, root: Path = ROOT) -> dict:
    """{hypothesis id: result} for every entry of the sidecar (module docstring). Raises ValueError on an
    invalid sidecar."""
    sidecar, out_dir, root = Path(sidecar), Path(out_dir), Path(root)
    doc = O.load(sidecar)
    problems = validate(doc, root if (root / SCHEMA).exists() else ROOT)
    if problems:
        raise ValueError(f"{sidecar}: invalid oracle sidecar: " + "; ".join(problems))
    cfg = bend.config(ROOT)
    shown = _rel(sidecar, root)
    out: dict = {}
    for e in doc["oracles"]:
        h, hyp = e["hypothesis"]["id"], e["hypothesis"]
        res: dict = {"oracle": e["id"], "kind": hyp.get("kind")}
        if e["status"] == "not_in_scope":
            res.update({"status": "not_in_scope", "reason": e["reason"], "instance": {"status": "not_applicable"}})
            out[h] = res
            continue
        res.update(_a4(e))
        if hyp["kind"] == "cf":
            res["instance"] = {"status": "per_premise",
                               "reason": "each law states its own finite set S; CF(p, S) is inhabited per law by the "
                                         "instance (holon.inhabit, non_vacuity.witness)"}
        else:
            d = out_dir / h
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)
            name, laws, proof = instance_law(e, shown)
            (d / "LAWS.bend").write_text(laws)
            (d / "PROOF.bend").write_text(proof)
            inst = {"law": _rel(d / "LAWS.bend", root), "proof": _rel(d / "PROOF.bend", root)}
            if bend.escape_hatches(laws + proof):
                inst.update(status="failed", reason="the instance law uses an escape hatch")
            else:
                r = bend.check(d / "PROOF.bend", cfg)
                if not r.ok:
                    inst.update(status="failed", reason=f"bend rejects the instance law: {r.first_line}")
                elif bend.verdict_enabled(cfg) and not (v := bend.check_verdict(d / "PROOF.bend", cfg)).ok:
                    inst.update(status="failed", reason=f"BendTT rejects the instance law: {v.first_line}")
                else:
                    inst["status"] = "checked"
            res["instance"] = dict(sorted(inst.items()))
        out[h] = res
    return dict(sorted(out.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon oracle check",
                                 description="Check every hypothesis of a milestone's oracle sidecar (A4, G11V).")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    root = Path(a.root)
    sidecar = root / "spec" / a.milestone / "lib" / "oracles.json"
    out_dir = root / "gen" / a.milestone / "oracles"
    hp = root / "results" / a.milestone / "hypotheses.json"
    shutil.rmtree(out_dir, ignore_errors=True)
    res = check(sidecar, out_dir, root)
    old = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else {}
    merged = dict(res)
    if ZERO_BLOB in old:   # I3's entry, written by `holon oracle zero-blob`: kept exactly as written
        merged[ZERO_BLOB] = old[ZERO_BLOB]
    hp.parent.mkdir(parents=True, exist_ok=True)
    hp.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for h, r in sorted(merged.items()):
        inst = r.get("instance", {}).get("status", "-") if isinstance(r.get("instance"), dict) else "-"
        print(f"{h:24s} {r.get('status', '-'):16s} instance {inst}")
    bad = [h for h, r in res.items() if r["status"] == "mismatch" or r["instance"]["status"] == "failed"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
