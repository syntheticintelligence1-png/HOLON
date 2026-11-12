"""I57: environment modules, time-indexed FACT and UNDO laws, and L9 by I54's definition.

  python -m holon m5 env [--check]   gen/M5/env/ (model, laws and proofs in the forms module and axiom),
                                     laws/M5/ENV.json, results/M5/L_env_*.json, results/M5/env/sensitivity.json
  python -m holon m5 l9  [--check]   results/M5/l9_I57.json: holon.m5.metrics.l9 over the M2, M3 and M5 records, the
                                     module records, the admitted observation sets and the sensitivity pairs

Inputs: spec/M5/lib/I57_modules.json (module records), spec/M5/lib/I57_laws.json (the law basis), the key I57
(pinned parameters, the observation tool's pin, the replay rule), the observation sets under
results/M5/env/observations/ and spec/M5/preregistration.json (I54's base).

The model is generated from the module records' parameters; each law's text comes from its subform's statement
template, and each proof from one generator per proof class (premise_rewrite, computation, bounded_cases,
counter_witness). The checker decides every status: PROVED when `bend PROOF.bend` prints ALL PROOFS CHECK and the law
named l_<id> is in LAWS.bend; REFUTED when the same holds for the counter-law cl_l_<id> with its witness; UNKNOWN
otherwise. Nothing here names a target.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import metrics
from .common import ROOT, dumps

KEY = "I57"
GEN = Path("gen") / "M5" / "env"
OBS = Path("results") / "M5" / "env" / "observations"
L9_OUT = Path("results") / "M5" / "l9_I57.json"
FORMS = ("module", "axiom")
CHECKED = "ALL PROOFS CHECK"


def _load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def key(root: Path) -> dict:
    return _load(root, "spec/M5/predictions.json")["iterations"][KEY]


def modules(root: Path) -> list[dict]:
    return _load(root, "spec/M5/lib/I57_modules.json")["modules"]


def classes(root: Path) -> list[dict]:
    return _load(root, "spec/M5/lib/I57_laws.json")["classes"]


def bend_name(law_id: str) -> str:
    return law_id.lower()


# ------------------------------------------------------------------ the model
def model_text(mods: dict) -> str:
    """The environment model: one section per module family, its parameter as a constant."""
    out = ["import Base", ""]
    for mid in sorted(mods):
        m = mods[mid]
        if m["family"] == "window":
            out += [f"# {mid}: window family, W = {m['parameters']['W']} (a premise)",
                    "def W() -> U32:", f"  {m['parameters']['W']}", "",
                    "def da_within(age: U32) -> Bool:", "  U32.is_le(age, W())", "",
                    "def da_deliver(age: U32, x: U32) -> Maybe<&2, U32>:", "  serve(da_within(age), x)", ""]
        elif m["family"] == "finality_depth":
            out += [f"# {mid}: finality_depth family, d = {m['parameters']['d']} (a premise)",
                    "def D() -> Nat:", f"  {m['parameters']['d']}n", "",
                    "def removed(k: Nat, j: Nat) -> Bool:", "  lt(k, j)", "",
                    "def consumed_depth(e: Nat) -> Nat:", "  Nat.add(D(), e)", ""]
        elif m["family"] == "availability":
            out += [f"# {mid}: availability family (no parameter)",
                    "def fetch_deliver(committed: Bool, x: U32) -> Maybe<&2, U32>:", "  serve(committed, x)", ""]
    # shared helpers come first in Bend's order: prepend them
    helpers = ["def serve(ok: Bool, x: U32) -> Maybe<&2, U32>:", "  match ok:", "    case True{}:", "      Some{x}",
               "    case False{}:", "      None{}", "",
               "def le(a: Nat, b: Nat) -> Bool:", "  match a b:", "    case 0n _:", "      True{}",
               "    case 1n+p 0n:", "      False{}", "    case 1n+p 1n+q:", "      le(p, q)", "",
               "def lt(k: Nat, j: Nat) -> Bool:", "  match k j:", "    case 0n _:", "      False{}",
               "    case 1n+p 0n:", "      True{}", "    case 1n+p 1n+q:", "      lt(p, q)", "",
               "def is_none(m: Maybe<&2, U32>) -> Type:", "  match m:", "    case None{}:", "      Unit",
               "    case Some{v}:", "      Empty", "",
               "def is_true(b: Bool) -> Type:", "  match b:", "    case True{}:", "      Unit", "    case False{}:",
               "      Empty", "",
               "def is_false(b: Bool) -> Type:", "  match b:", "    case False{}:", "      Unit", "    case True{}:",
               "      Empty", ""]
    return "\n".join(out[:2] + helpers + out[2:]).rstrip("\n") + "\n"


# ------------------------------------------------------------------ statements (per subform and form)
def _head(name: str) -> list[str]:
    return ["import Base", "import ../../model/env.bend as M", ""]


def statement(cls: dict, form: str, m: dict) -> tuple[str, str]:
    """(law name, LAWS.bend text). module: the claim with the module's term; axiom: the same term free (havoc).
    A claim the generator expects false is stated by its counter-law cl_<name> (a witness, AGENTS rule 6)."""
    n = bend_name(cls["id"])
    sub = cls["subform"]
    mx = "Maybe<&2, U32>"
    if form == "module":
        if sub == "time_window":
            body = [f"law {n}:", "  for age: U32", "  for x: U32", "  for h: {M.da_within(age) == True{} : Bool}",
                    f"  {{M.da_deliver(age, x) == Some{{x}} : {mx}}}"]
        elif sub == "time_any":
            n = "cl_" + n
            body = [f"law {n}:", "  exs age: U32", f"  {{M.da_deliver(age, 0) != Some{{0}} : {mx}}}"]
        elif sub == "fetcher":
            body = [f"law {n}:", "  for x: U32", f"  {{M.fetch_deliver(True{{}}, x) == Some{{x}} : {mx}}}"]
        elif sub == "reorg_residue":
            body = [f"law {n}:", "  for k: Nat", "  for e: Nat", "  for h: {M.le(k, M.D()) == True{} : Bool}",
                    "  {M.removed(k, M.consumed_depth(e)) == False{} : Bool}"]
        else:
            raise ValueError(sub)
    else:
        n = "cl_" + n
        if sub == "time_window":
            body = [f"law {n}:", "  exs av: U32 -> Bool",
                    f"  {{M.da_within(0) == True{{}} : Bool}} & {{M.serve(av(0), 0) != Some{{0}} : {mx}}}"]
        elif sub == "time_any":
            body = [f"law {n}:", "  exs av: U32 -> Bool", f"  {{M.serve(av(0), 0) != Some{{0}} : {mx}}}"]
        elif sub == "fetcher":
            body = [f"law {n}:", "  exs fa: Bool -> Bool", f"  {{M.serve(fa(True{{}}), 0) != Some{{0}} : {mx}}}"]
        elif sub == "reorg_residue":
            body = [f"law {n}:", "  exs k: Nat", "  {M.removed(k, M.consumed_depth(0n)) != False{} : Bool}"]
        else:
            raise ValueError(sub)
    return n, "\n".join(_head(n) + body) + "\n"


# ------------------------------------------------------------------ proofs (one generator per class)
def _proof_head() -> list[str]:
    return ["import Base", "import ./LAWS.bend as Laws", "import ../../model/env.bend as M", ""]


def proof_premise_rewrite(name: str, cls: dict, m: dict) -> list[str]:
    """Rewrite the module's predicate with the premise h, then compute."""
    return [f"def Laws.{name}(age, x, h):",
            "  %Equal.sym(Bool, M.da_within(age), True{}, h) : {M.serve(_, x) == Some{x} : Maybe<&2, U32>}",
            "  {==}"]


def proof_computation(name: str, cls: dict, m: dict) -> list[str]:
    return [f"def Laws.{name}(x):", "  {==}"]


def proof_bounded_cases(name: str, cls: dict, m: dict) -> list[str]:
    """Case split on k to depth d + 1: each k <= d computes; k = d + 1 + r contradicts the premise h."""
    d = int(m["parameters"]["d"])
    out = ["def bot(h: {False{} == True{} : Bool}) -> Empty:", "  %h : M.is_false(_)", "  Unit{}", "",
           "def ex_falso(-P: Type, e: Empty) -> P:", "  match e:", "",
           "def bot_eq(-b: Bool, h: {False{} == True{} : Bool}) -> {b == False{} : Bool}:",
           "  ex_falso({b == False{} : Bool}, bot(h))", "", f"def Laws.{name}(k, e, h):"]
    var, pad = "k", "  "
    for i in range(d + 1):
        out += [f"{pad}match {var}:", f"{pad}  case 0n:", f"{pad}    {{==}}", f"{pad}  case 1n+k{i + 1}:"]
        var, pad = f"k{i + 1}", pad + "    "
    out.append(f"{pad}bot_eq(M.lt(1n+{var}, e), h)")
    return out


def proof_counter_witness(name: str, cls: dict, m: dict, form: str) -> list[str]:
    """A concrete witness; the inequality by a motive that sends the witness side to Unit and the claimed side to
    Empty (BEND_PRIMER 5.4)."""
    sub = cls["subform"]
    if form == "module" and sub == "time_any":
        return [f"def Laws.{name}():", f"  ({int(m['parameters']['W']) + 1}, e => (%e : M.is_none(_)", "  Unit{}))"]
    if form == "axiom" and sub == "time_window":
        return [f"def Laws.{name}():", "  (x => False{}, ({==}, e => (%e : M.is_none(_)", "  Unit{})))"]
    if form == "axiom" and sub in ("time_any", "fetcher"):
        return [f"def Laws.{name}():", "  (x => False{}, e => (%e : M.is_none(_)", "  Unit{}))"]
    if form == "axiom" and sub == "reorg_residue":
        return [f"def Laws.{name}():", f"  ({int(m['parameters']['d']) + 1}n, e => (%e : M.is_true(_)", "  Unit{}))"]
    raise ValueError((form, sub))


def proof_text(name: str, cls: dict, form: str, m: dict) -> str:
    pc = cls["module_form"] if form == "module" else cls["axiom_form"]
    if pc == "premise_rewrite":
        body = proof_premise_rewrite(name, cls, m)
    elif pc == "computation":
        body = proof_computation(name, cls, m)
    elif pc == "bounded_cases":
        body = proof_bounded_cases(name, cls, m)
    elif pc == "counter_witness":
        body = proof_counter_witness(name, cls, m, form)
    else:
        raise ValueError(pc)
    return "\n".join(_proof_head() + body) + "\n"


# ------------------------------------------------------------------ generation and checking
def generate(root: Path) -> dict[str, str]:
    """{repo path: text} of every generated Bend file and laws/M5/ENV.json."""
    mods = {m["id"]: m for m in modules(root)}
    files = {(GEN / "model" / "env.bend").as_posix(): model_text(mods)}
    m3 = sorted(p.stem for p in (root / "results" / "M3").glob("L_*.json"))
    env = []
    for cls in sorted(classes(root), key=lambda c: c["id"]):
        m = mods[cls["module"]]
        entry = {"id": cls["id"], "rule": cls["rule"], "subform": cls["subform"], "module": m["id"],
                 "category": m["category"], "claim": cls["claim"],
                 "indexes": [i for i in m3 if re.search(cls["indexes"], i)], "forms": {}}
        for form in FORMS:
            name, laws = statement(cls, form, m)
            d = GEN / form / cls["id"]
            files[(d / "LAWS.bend").as_posix()] = laws
            files[(d / "PROOF.bend").as_posix()] = proof_text(name, cls, form, m)
            entry["forms"][form] = {"law": name, "laws": (d / "LAWS.bend").as_posix(),
                                    "proof_class": cls["module_form"] if form == "module" else cls["axiom_form"],
                                    "laws_sha256": hashlib.sha256(laws.encode()).hexdigest()}
        env.append(entry)
    files["laws/M5/ENV.json"] = dumps({"doc": "I57's time-indexed environment laws (holon.m5.env, from "
                                       "spec/M5/lib/I57_laws.json and spec/M5/lib/I57_modules.json)",
                                       "laws": env})
    return files


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _evidence(root: Path, d: Path, name: str, check) -> dict:
    laws = (root / d / "LAWS.bend").read_text(encoding="utf-8")
    r = check(root / d / "PROOF.bend")
    marker = r.first_line if r.code is not None else None
    return {"law": name, "marker": marker if marker else None,
            "law_present": bool(r.ok and f"law {name}:" in laws)}


def _status(ev: dict) -> str:
    if ev["marker"] != CHECKED or not ev["law_present"]:
        return "UNKNOWN"
    return "REFUTED" if ev["law"].startswith("cl_") else "PROVED"


def records(root: Path, check=None) -> dict[str, str]:
    """{repo path: text} of results/M5/L_env_*.json, each form checked by the checker."""
    if check is None:
        from .. import bend
        check = bend.check
    mods = {m["id"]: m for m in modules(root)}
    env = json.loads(generate(root)["laws/M5/ENV.json"])["laws"]
    out = {}
    for e in env:
        m = mods[e["module"]]
        forms = {}
        for form in FORMS:
            f = e["forms"][form]
            d = GEN / form / e["id"]
            ev = _evidence(root, d, f["law"], check)
            prem = ({"id": m["id"], "category": m["category"], "form": "module", "module": m["id"]} if form == "module"
                    else {"id": f"havoc:{m['category']}", "category": m["category"], "form": "havoc", "module": None})
            forms[form] = {"status": _status(ev), "evidence": ev, "proof_class": f["proof_class"],
                           "environment": {"carriers": [m["category"]], "premises": [prem]},
                           "artifacts": {"laws": f["laws"], "proof": (d / "PROOF.bend").as_posix(),
                                         "model": (GEN / "model" / "env.bend").as_posix()}}
        mf = forms["module"]
        rec = {"law_id": e["id"], "milestone": "M5", "rule": e["rule"], "subform": e["subform"],
               "claim": e["claim"], "status": mf["status"], "evidence": mf["evidence"],
               "proof_class": mf["proof_class"], "environment": mf["environment"], "artifacts": mf["artifacts"],
               "ledger_assumptions": [], "model_assumptions": [], "premises": [],
               "module": {"id": m["id"], "family": m["family"], "parameters": m["parameters"]},
               "axiom_form": forms["axiom"], "indexes": e["indexes"],
               "generator": "holon.m5.env", "provenance": "spec/M5/lib/I57_laws.json"}
        out[f"results/M5/{e['id']}.json"] = dumps(rec)
    return out


# ------------------------------------------------------------------ observations and sensitivity
def admit(doc: dict | None, tool: dict, sources: list[str]) -> tuple[bool, str]:
    """The key's observation_tool.rule (the lead's condition G3)."""
    if doc is None:
        return False, "absent"
    if doc.get("producer") != tool["producer"] or doc.get("source_sha256") != tool["sha256"]:
        return False, "not produced by the pinned tool"
    reads = doc.get("reads") or []
    ok = re.compile(r"^(FILE [A-Za-z0-9_./-]+(#[A-Za-z0-9_,]+)?|GET (%s)/\S+|RPC (%s) eth_[A-Za-z]+)$"
                    % ("|".join(map(re.escape, sources)), "|".join(map(re.escape, sources))))
    if not reads or any(not ok.match(r) for r in reads) or "FILE spec/M5/lib/I57_modules.json" in reads:
        return False, "reads outside the tool's forms"
    return True, "admitted"


def observation_sets(root: Path) -> tuple[list[dict], dict]:
    k = key(root)
    tool = k["thresholds"]["observation_tool"]
    plan = _load(root, tool["plan"])
    sources = sorted(plan["sources"].values())
    sets, report = [], {}
    for name in sorted(plan["sets"]):
        p = root / OBS / f"{name}.json"
        doc = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        ok, why = admit(doc, tool, sources)
        report[name] = {"admitted": ok, "why": why,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
        if ok:
            sets.append(doc)
    return sets, report


def replay(law: str, subform: str, params: dict, items: list[dict]) -> str:
    """The key's definitions of replay, by subform."""
    if subform == "time_window":
        reg, want_all = [o for o in items if o["q"] - o["t"] <= params["W"]], True
    elif subform == "time_any":
        reg, want_all = [o for o in items if o["q"] - o["t"] > params["W"]], False
    elif subform == "fetcher":
        reg, want_all = [o for o in items if o["committed"]], True
    elif subform == "reorg_residue":
        reg, want_all = [o for o in items if o["head"] - o["t"] >= params["d"]], True
    else:
        raise ValueError(subform)
    if not reg:
        return "absent"
    ok = all(o["observed"] for o in reg) if want_all else any(not o["observed"] for o in reg)
    return "passed" if ok else "failed"


def sensitivity(root: Path, recs: dict[str, dict], sets: list[dict]) -> list[dict]:
    by = {s["set"]: s for s in sets}
    mods = {m["id"]: m for m in modules(root)}
    pairs = []
    for cls in sorted(classes(root), key=lambda c: c["id"]):
        rec = recs.get(cls["id"])
        if rec is None:
            continue
        m = mods[cls["module"]]
        items = [o for s in m["observations"] if s in by for o in by[s]["items"]]
        pairs.append({"law": cls["id"], "module": m["id"], "status_axiom": rec["axiom_form"]["status"],
                      "status_module": rec["status"], "replay": replay(cls["id"], cls["subform"], m["parameters"],
                                                                       items),
                      "evidence": rec["evidence"]})
    return pairs


def build(root: Path, check=None) -> dict[str, str]:
    files = generate(root)
    _write(root, {k: v for k, v in files.items() if k.startswith(GEN.as_posix())})
    recs = records(root, check)
    files.update(recs)
    sets, report = observation_sets(root)
    pairs = sensitivity(root, {json.loads(v)["law_id"]: json.loads(v) for v in recs.values()}, sets)
    files["results/M5/env/sensitivity.json"] = dumps({"doc": "I57's sensitivity pairs (I54 sensitivity_pair), "
                                                      "one per law; replay by the key's definitions over the "
                                                      "admitted sets", "pairs": pairs, "sets": report})
    return files


def l9_doc(root: Path) -> dict:
    k = key(root)
    recs = []
    for m in ("M2", "M3", "M5"):
        recs += [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "results" / m).glob("L_*.json"))]
    sets, report = observation_sets(root)
    sens_p = root / "results" / "M5" / "env" / "sensitivity.json"
    pairs = json.loads(sens_p.read_text(encoding="utf-8"))["pairs"]
    prereg = _load(root, "spec/M5/preregistration.json")
    cls_p = root / "spec" / "M5" / "lib" / "environment_classes.json"
    mod_p = root / "spec" / "M5" / "lib" / "I57_modules.json"
    inp = {"records": recs, "classification": json.loads(cls_p.read_text(encoding="utf-8")),
           "modules": modules(root), "observation_sets": sets, "sensitivity": pairs,
           "base_dependent": prereg["base"]["l9_dependent"],
           "pinned_parameters": k["thresholds"]["pinned_parameters"]}
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    return {"key": KEY, "measured_by": "I54 definitions.L9 (spec/M5/preregistration.json), holon.m5.metrics.l9",
            "L9": metrics.l9(inp),
            "inputs": {"records": {m: sum(1 for r in recs if r.get("milestone", "") == m) for m in ("M5",)}
                       | {"M2_M3": sum(1 for r in recs if r.get("milestone") != "M5")},
                       "classification_sha256": sha(cls_p), "modules_sha256": sha(mod_p),
                       "sensitivity_sha256": sha(sens_p), "observation_sets": report,
                       "base_dependent": len(prereg["base"]["l9_dependent"])}}


def write(root: Path, check_only: bool, what: str) -> list[str]:
    """Files written (or, with check_only, the differences)."""
    if what == "env":
        files = build(root) if not check_only else _build_check(root)
    else:
        files = {L9_OUT.as_posix(): dumps(l9_doc(root))}
    out = []
    for rel, text in sorted(files.items()):
        p = root / rel
        have = p.read_text(encoding="utf-8") if p.is_file() else None
        if have != text:
            if check_only:
                out.append(f"{rel}: differs")
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                out.append(rel)
    return out


def _build_check(root: Path) -> dict[str, str]:
    """build() in a copy of the generated tree, so --check never writes the repo."""
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory(prefix="holon-m5-env-") as t:
        tmp = Path(t)
        for rel in ("spec/M5", "results/M5/env/observations"):
            src = root / rel
            if src.exists():
                shutil.copytree(src, tmp / rel, symlinks=True)
        (tmp / "results" / "M3").parent.mkdir(parents=True, exist_ok=True)
        (tmp / "results" / "M3").symlink_to(root / "results" / "M3", target_is_directory=True)
        files = build(tmp)
    return files
