"""The intent runner (key I55 design R1-R4, TT, O): decide every INTENT law with Bend.

  python -m holon intent run [--root DIR] [--check --tmp DIR]

For each law of laws/INTENT/, in law_id order:
  1. gen/M5/intent/<law_id>/LAWS.bend states exactly the law (law_id lower-cased) over the model imported as M.
  2. Proof classes, in order: computation (open s and every x, then {==}), then bool_cases (the Bool atoms of the
     statement, with each chk_<a> unfolded, abstracted into a lemma that Bend proves by exhaustive match and that the
     law instantiates). PROVED iff Bend prints ALL PROOFS CHECK, exits 0, and the law is present.
  3. Otherwise the witness search: the statement compiled to JavaScript with the model (bend -o .mjs) and evaluated by
     node over R2's candidates, never on any truth or oracle. The first candidate where it is False becomes the
     counter-law cl_<law_id lower-cased> in the exs form; REFUTED iff Bend accepts it.
  4. Otherwise UNKNOWN with the bound and the attempts; the law's directory is removed.
  5. A PROVED law gets its trivially-true check (TT): the twin (gen/M5/intent/<law_id>_twin/, every action function a
     binder) through the same proof classes, and the inhabitant (gen/M5/intent/<law_id>_inhabit/, an exs law that
     every action of the law succeeds, at a witness from the same search).
  6. results/M5/intent/records/<law_id>.json, with the review that spec/M5/intent/reviews.json gives the law (absent
     when the reviews file is missing, lacks the law, or reviewed other requests than results/M5/intent/
     review_requests.json holds).

--check runs everything into DIR (gen/ and results/ under it) and compares the records and the generated law
directories with the committed ones byte for byte.
"""
from __future__ import annotations

import argparse
import itertools
import re
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .. import bend as B
from .common import COMPILER, GEN, LAWS, OUT, ROOT, dumps, sha256_file
from .ir import binder_lines, law_text, model_import, statement_hash
from .model import BOOL_PRELUDE, MASK, Model, ident, render

RECORD_VERSION = "holon-intent-record/0.1"
MAX_CANDIDATES = 50000
MAX_ATOMS = 12
BASE_VALUES = (0, 1, 2, 3, 100, (1 << 160) - 1, MASK)
REVIEWS = "spec/M5/intent/reviews.json"


class NoProof(Exception):
    pass


# ------------------------------------------------------------------ binders and their records
class Shape:
    """The binders of a law: s (St) and one x per action, with their record fields."""

    def __init__(self, law: dict, mdl: Model):
        self.law, self.mdl = law, mdl
        self.binders = law["statement"]["binders"]
        self.fields = {}
        acts = iter(law["actions"])
        for b in self.binders:
            if b["type"] == "St":
                self.fields[b["name"]] = ("St", mdl.st_fields())
            else:
                a = next(acts)
                self.fields[b["name"]] = (mdl.x_type(a), mdl.x_fields(a))

    def pattern_vars(self, b: str) -> list[str]:
        return [f"{b}_{f}" for f in self.fields[b][1]]

    def ctor(self, b: str, prefix: str = "M.") -> str:
        ty, _ = self.fields[b]
        return f"{prefix}{ty}{{" + ", ".join(self.pattern_vars(b)) + "}"

    def opened(self, leaf: list[str], indent: int = 1) -> list[str]:
        """def body lines: nested matches opening every binder, then the leaf lines."""
        out, ind = [], indent
        for b in self.binders:
            ty, _ = self.fields[b["name"]]
            pv = ", ".join("+" + v for v in self.pattern_vars(b["name"]))
            out += ["  " * ind + f"match {b['name']}:", "  " * (ind + 1) + f"case M.{ty}{{{pv}}}:"]
            ind += 2
        return out + ["  " * ind + x for x in leaf]

    def literal(self, b: str, values: dict) -> str:
        ty, fs = self.fields[b]
        from .model import wlit
        return f"M.{ty}{{" + ", ".join(wlit(int(values[f]), "M.") for f in fs) + "}"


def _sub_vars(t, env: dict):
    if "var" in t:
        return env.get(t["var"], t)
    if "args" in t:
        return {**{k: v for k, v in t.items() if k != "args"}, "args": [_sub_vars(a, env) for a in t["args"]]}
    return t


# ------------------------------------------------------------------ bool_cases: atoms (design R1)
class Abstract:
    def __init__(self, mdl: Model, twin: bool):
        self.mdl, self.twin = mdl, twin
        self.atoms: list = []        # canonical json -> index
        self.keys: dict = {}

    def atom(self, t) -> dict:
        k = json.dumps(t, sort_keys=True)
        if k not in self.keys:
            self.keys[k] = len(self.atoms)
            self.atoms.append(t)
        return {"atom": self.keys[k]}

    def inline(self, t):
        """Unfold chk_<a>(s, x) into its body (not in a twin, where every action function is a binder)."""
        if "act" in t and not self.twin and t["act"].startswith("chk_"):
            a = next(a for a in self.mdl.actions if "chk_" + ident(a) == t["act"])
            s, x = (self.inline(u) for u in t["args"])
            return _sub_vars(self.mdl.actions[a]["chk"], {"s": s, "x": x})
        if "args" in t:
            return {**{k: v for k, v in t.items() if k != "args"}, "args": [self.inline(a) for a in t["args"]]}
        return t

    def u32(self, t):
        if "u32" in t:
            return t
        if t.get("m") == "ip_ite_u":
            c, a, b = t["args"]
            return {"m": "ip_ite_u", "args": [self.boolean(c), self.u32(a), self.u32(b)]}
        raise NoProof("an opaque U32 term")

    def boolean(self, t):
        if "bool" in t:
            return t
        f = t.get("fn")
        if f in ("Bool.not", "Bool.and", "Bool.or"):
            return {"fn": f, "args": [self.boolean(a) for a in t["args"]]}
        if f == "U32.is_eq":
            try:
                return {"fn": f, "args": [self.u32(a) for a in t["args"]]}
            except NoProof:
                return self.atom(t)
        if t.get("m") == "ip_ite_b":
            c, a, b = t["args"]
            return {"m": "ip_ite_b", "args": [self.boolean(c), self.boolean(a), self.boolean(b)]}
        if t.get("m") in BOOL_PRELUDE:
            return self.atom(t)
        raise NoProof(f"a Bool term the class cannot abstract ({str(t)[:80]})")


def _eval(t, env: list):
    if "atom" in t:
        return env[t["atom"]]
    if "bool" in t:
        return t["bool"]
    if "u32" in t:
        return t["u32"]
    f = t.get("fn") or t.get("m")
    a = t["args"]
    if f == "Bool.not":
        return not _eval(a[0], env)
    if f == "Bool.and":
        return _eval(a[0], env) and _eval(a[1], env)
    if f == "Bool.or":
        return _eval(a[0], env) or _eval(a[1], env)
    if f == "U32.is_eq":
        return _eval(a[0], env) == _eval(a[1], env)
    if f in ("ip_ite_u", "ip_ite_b"):
        return _eval(a[1], env) if _eval(a[0], env) else _eval(a[2], env)
    raise NoProof(f"cannot evaluate {f}")


def _render_abs(t, prefix: str, atoms: list[str]) -> str:
    if "atom" in t:
        return atoms[t["atom"]]
    if "bool" in t or "u32" in t:
        return render(t, prefix)
    args = ", ".join(_render_abs(a, prefix, atoms) for a in t["args"])
    if "fn" in t:
        return f"{t['fn']}({args})"
    return f"{prefix}{t['m']}({args})"


def bool_cases(law: dict, shape: Shape, holds: dict, twin_sub: dict | None) -> list[str]:
    """PROOF.bend lines after the imports for the law name (lemma + instantiation); NoProof when it cannot apply."""
    ab = Abstract(shape.mdl, twin_sub is not None)
    e = ab.boolean(ab.inline(holds))
    k = len(ab.atoms)
    if k > MAX_ATOMS:
        raise NoProof(f"{k} atoms (at most {MAX_ATOMS})")
    for bits in itertools.product((True, False), repeat=k):
        if _eval(e, list(bits)) is not True:
            raise NoProof(f"the abstraction is False at {dict(enumerate(bits))} ({k} atoms): the atoms are not "
                          "independent, or the law needs arithmetic")
    names = [f"b{i}" for i in range(k)]
    lem = f"ip_lem_{law['law_id'].lower()}"
    sig = ", ".join(f"+{n}: Bool" for n in names)
    lines = [f"def {lem}({sig}) -> {{{_render_abs(e, 'M.', names)} == True{{}} : Bool}}:"]
    if k == 0:
        lines.append("  {==}")
    else:
        lines.append("  match " + " ".join(names) + ":")
        for bits in itertools.product((True, False), repeat=k):
            lines.append("    case " + " ".join("True{}" if x else "False{}" for x in bits) + ":")
            lines.append("      {==}")
    # the instantiation: each atom with every binder written as its opened constructor
    ctor = {b["name"]: shape.ctor(b["name"]) for b in shape.binders}
    atoms_txt = [render(_sub_vars(a, {n: {"var": c} for n, c in ctor.items()}), "M.", twin_sub) for a in ab.atoms]
    return lines + [""], f"{lem}({', '.join(atoms_txt)})"


# ------------------------------------------------------------------ the checker
class Checker:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.verdict = B.verdict_enabled(cfg)

    def check(self, proof: Path, law_name: str) -> tuple[bool, str]:
        r = B.check(proof, cfg=self.cfg)
        laws = B.strip_comments((proof.parent / "LAWS.bend").read_text(encoding="utf-8"))
        present = re.findall(r"(?<![\w.])law\s+([A-Za-z0-9_.]+)\s*:", laws) == [law_name]
        return (r.ok and present), r.marker

    def second(self, proof: Path) -> str | None:
        if not self.verdict:
            return None
        return B.check_verdict(proof, cfg=self.cfg).marker


def proof_file(law: dict, name: str, params: list[str], body: list[str], extra: list[str]) -> str:
    head = ["import Base", model_import(law), "import ./LAWS.bend as Laws", ""]
    return "\n".join(head + extra + [f"def Laws.{name}({', '.join(params)}):"] + body) + "\n"


def try_prove(law: dict, shape: Shape, d: Path, name: str, laws_text: str, holds: dict, ck: Checker,
              twin_sub: dict | None = None, fparams: list[str] | None = None) -> tuple[str | None, list[str]]:
    """(proof class or None, attempts). Leaves the accepted PROOF.bend in d."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "LAWS.bend").write_text(laws_text, encoding="utf-8")
    params = (fparams or []) + [b["name"] for b in shape.binders]
    attempts = []
    for cls in ("computation", "bool_cases"):
        try:
            if cls == "computation":
                text = proof_file(law, name, params, shape.opened(["{==}"]), [])
            else:
                extra, call = bool_cases(law, shape, holds, twin_sub)
                text = proof_file(law, name, params, shape.opened([call]), extra)
        except NoProof as e:
            attempts.append(f"{cls}: {e}")
            continue
        (d / "PROOF.bend").write_text(text, encoding="utf-8")
        ok, marker = ck.check(d / "PROOF.bend", name)
        if ok:
            second = ck.second(d / "PROOF.bend")
            if second in (None, B.MARK_OK):
                return cls, attempts + [f"{cls}: ALL PROOFS CHECK" + ("" if second is None else " (both kernels)")]
            attempts.append(f"{cls}: bend2 accepts and BendTT does not ({second}): a blocking cross-kernel "
                            "disagreement (Q22, Q8), not a proof")
            continue
        # the marker alone: a timeout's place depends on the machine, so the record says only that it failed
        attempts.append(f"{cls}: not accepted")
    p = d / "PROOF.bend"
    if p.exists():
        p.unlink()
    return None, attempts


# ------------------------------------------------------------------ the witness search (design R2)
JS_DRIVER = r"""
import M from "./EVAL.mjs";
import { readFileSync } from "node:fs";
const cfg = JSON.parse(readFileSync(process.argv[2], "utf8"));
const W = s => { const v = BigInt(s); const o = {$: "W"}; for (let i = 0; i < 8; i++) o["l" + i] = Number((v >> BigInt(32 * i)) & 0xffffffffn); return o; };
const vals = cfg.values.map(vs => vs.map(W));
const n = vals.reduce((a, v) => a * v.length, 1);
const cap = Math.min(n, cfg.cap);
const truthy = r => r === true || (r && r.$ === "True");
let i = 0;
for (; i < cap; i++) {
  let k = i; const dig = new Array(vals.length);
  for (let f = vals.length - 1; f >= 0; f--) { dig[f] = k % vals[f].length; k = Math.floor(k / vals[f].length); }
  const args = []; let f = 0;
  for (const [ctor, fields] of cfg.binders) {
    const o = {$: ctor};
    for (const name of fields) { o[name] = vals[f][dig[f]]; f++; }
    args.push(o);
  }
  if (truthy(M.ev(...args)) === cfg.want) { console.log(JSON.stringify({hit: i, digits: dig})); process.exit(0); }
}
console.log(JSON.stringify({hit: null, searched: i, space: n}));
"""


def candidate_values(mdl: Model, law: dict) -> list[int]:
    vs = set(BASE_VALUES)
    for k in mdl.literals(law["actions"]):
        vs.update({k, (k - 1) & MASK, (k + 1) & MASK})
    return sorted(vs)


def search(law: dict, shape: Shape, mdl: Model, root: Path, expr: dict, want: bool, cfg: dict) -> tuple[dict | None, str]:
    """(witness {binder: {field: decimal}} or None, bound text)."""
    vals = candidate_values(mdl, law)
    binders = [(shape.fields[b["name"]][0], shape.fields[b["name"]][1]) for b in shape.binders]
    nfields = sum(len(fs) for _, fs in binders)
    with tempfile.TemporaryDirectory(prefix="holon-intent-") as t:
        t = Path(t)
        (t / "model").mkdir()
        shutil.copy(root / law["model"], t / "model" / Path(law["model"]).name)
        (t / "ev").mkdir()
        sig = ", ".join(f"+{b['name']}: M.{b['type']}" for b in shape.binders)
        (t / "ev" / "EVAL.bend").write_text("\n".join(["import Base", model_import(law), "",
                                                        f"def ev({sig}) -> Bool:", "  " + render(expr, "M.")]) + "\n",
                                            encoding="utf-8")
        r = B.run([str(t / "ev" / "EVAL.bend"), "-o", str(t / "ev" / "EVAL.mjs")], cwd=t / "ev", cfg=cfg)
        if r.code != 0:
            return None, f"the evaluator did not compile: {r.out.strip()[:200]}"
        (t / "ev" / "drive.mjs").write_text(JS_DRIVER, encoding="utf-8")
        conf = {"binders": [[f"{ty}", fs] for ty, fs in binders], "values": [[str(v) for v in vals]] * nfields,
                "cap": MAX_CANDIDATES, "want": want}
        (t / "ev" / "cfg.json").write_text(json.dumps(conf), encoding="utf-8")
        node = json.loads((root / "config" / "holon.json").read_text(encoding="utf-8")).get("node", "node")
        p = subprocess.run([node, "drive.mjs", "cfg.json"], cwd=t / "ev", capture_output=True, text=True, timeout=1800)
        if p.returncode != 0:
            return None, f"the evaluator failed: {p.stderr.strip()[:200]}"
        res = json.loads(p.stdout.strip().splitlines()[-1])
    space = len(vals) ** nfields
    bound = (f"{min(space, MAX_CANDIDATES)} of {space} candidates ({nfields} fields x {len(vals)} values: "
             f"{', '.join(str(v) if v < 1 << 64 else hex(v) for v in vals)})")
    if res["hit"] is None:
        return None, bound
    wit, f = {}, 0
    for b in shape.binders:
        wit[b["name"]] = {}
        for name in shape.fields[b["name"]][1]:
            wit[b["name"]][name] = str(vals[res["digits"][f]])
            f += 1
    return wit, bound


def witness_term(shape: Shape, wit: dict) -> str:
    lits = [shape.literal(b["name"], wit[b["name"]]) for b in shape.binders]
    return lits


def exs_laws(law: dict, name: str, binders: list[dict], prop: str) -> str:
    return "\n".join(["import Base", model_import(law), "", f"law {name}:", *binder_lines(binders, "exs"),
                      f"  {prop}"]) + "\n"


def counter_proof(law: dict, shape: Shape, wit: dict, holds: dict, cname: str) -> str:
    """The counter-law's proof at a witness W. The statement's value at W is a closed lemma (ip_val: {holds(W) ==
    False}), proved by {==}; the hypothesis e : {holds(W) == True} is turned into {True == False} by a rewrite whose
    motive is the equation {_ == False}, and that into Empty by ip_is_true(_). No motive reduces the statement, so
    neither kernel evaluates it under an open context (I89's kernel behaviour 4; Q22: fix the generator)."""
    lits = witness_term(shape, wit)
    at = render(_sub_vars(holds, {b["name"]: {"var": lit} for b, lit in zip(shape.binders, lits)}), "M.")
    return "\n".join(["import Base", model_import(law), "import ./LAWS.bend as Laws", "",
                      f"def ip_val() -> {{{at} == False{{}} : Bool}}:", "  {==}", "",
                      f"def ip_flip(e: {{{at} == True{{}} : Bool}}) -> {{True{{}} == False{{}} : Bool}}:",
                      "  (%e : {_ == False{} : Bool}", "  ip_val())", "",
                      "def ip_absurd(r: {True{} == False{} : Bool}) -> Empty:", "  (%r : M.ip_is_true(_)", "  Unit{})",
                      "", f"def Laws.{cname}():", "  " + nest(lits, "e => ip_absurd(ip_flip(e))")]) + "\n"


def nest(lits: list[str], inner: str) -> str:
    out = inner
    for lit in reversed(lits):
        out = f"({lit}, {out})"
    return out


# ------------------------------------------------------------------ one law
def ok_all(law: dict) -> dict:
    xs = [b["name"] for b in law["statement"]["binders"] if b["name"] != "s"]
    parts = [{"fn": "U32.is_eq", "args": [{"act": f"chk_{ident(a)}", "args": [{"var": "s"}, {"var": x}]},
                                          {"u32": 0}]} for x, a in zip(xs, law["actions"])]
    e = parts[-1]
    for p in reversed(parts[:-1]):
        e = {"fn": "Bool.and", "args": [p, e]}
    return e


def act_names(t, out: set) -> set:
    if "act" in t:
        out.add(t["act"])
    for a in t.get("args", []):
        act_names(a, out)
    return out


def act_type(mdl: Model, name: str) -> str:
    kind, _, a = name.partition("_")
    a = next(x for x in mdl.actions if ident(x) == a)
    res = {"chk": "U32", "post": "M.St", "ret": "M.W"}[kind]
    return f"M.St -> M.{mdl.x_type(a)} -> {res}"


def decide(law: dict, mdl: Model, root: Path, gen: Path, ck: Checker, cfg: dict) -> dict:
    lid, name = law["law_id"], law["law_id"].lower()
    shape = Shape(law, mdl)
    holds = law["statement"]["holds"]
    d = gen / lid
    for extra in (d, gen / f"{lid}_twin", gen / f"{lid}_inhabit"):
        if extra.exists():
            shutil.rmtree(extra)
    rec = {"record_version": RECORD_VERSION, "law_id": lid, "law": name, "clauses": law["clauses"],
           "control": law["control"], "file": law["file"], "status": "UNKNOWN",
           "evidence": {"law": name, "marker": None, "law_present": False}, "verdict": None, "proof_class": None,
           "witness": None, "bound": None, "attempts": [], "trivial": {"twin": "not_run", "inhabited": None,
                                                                         "trivially_true": None},
           "statement_hash": statement_hash(law), "paths": {"model": law["model"], "law": f"{LAWS}/{lid}.json"}}
    cls, attempts = try_prove(law, shape, d, name, law_text(law), holds, ck)
    rec["attempts"] = attempts
    rel = f"{GEN}/{lid}"
    if cls:
        rec.update(status="PROVED", proof_class=cls, verdict=ck.second(d / "PROOF.bend") if ck.verdict else None,
                   evidence={"law": name, "marker": B.MARK_OK, "law_present": True})
        rec["paths"].update(laws=f"{rel}/LAWS.bend", proof=f"{rel}/PROOF.bend")
        rec["trivial"] = trivial(law, mdl, shape, root, gen, ck, cfg, rec)
        return rec
    wit, bound = search(law, shape, mdl, root, holds, False, cfg)
    rec["bound"] = bound
    if wit is not None:
        cname = "cl_" + name
        (d / "LAWS.bend").write_text(exs_laws(law, cname, shape.binders,
                                              f"{{{render(holds, 'M.')} != True{{}} : Bool}}"), encoding="utf-8")
        text = counter_proof(law, shape, wit, holds, cname)
        (d / "PROOF.bend").write_text(text, encoding="utf-8")
        ok, marker = ck.check(d / "PROOF.bend", cname)
        second = ck.second(d / "PROOF.bend") if ok else None
        rec["attempts"].append(f"counter-law at the search's witness: bend2 {marker}"
                               + ("" if second is None else f", BendTT {second}"))
        if ok and second in (None, B.MARK_OK):
            rec.update(status="REFUTED", witness=wit, verdict=second,
                       evidence={"law": cname, "marker": B.MARK_OK, "law_present": True})
            rec["paths"].update(laws=f"{rel}/LAWS.bend", proof=f"{rel}/PROOF.bend")
            return rec
        rec["attempts"].append("the model's witness is not a refutation: the checker's word is final"
                               + (" (BendTT rejects what bend2 accepts: a blocking cross-kernel disagreement, Q22)"
                                  if ok else ""))
    else:
        rec["attempts"].append(f"witness search: no candidate falsifies the law ({bound})")
    shutil.rmtree(d, ignore_errors=True)
    return rec


def trivial(law: dict, mdl: Model, shape: Shape, root: Path, gen: Path, ck: Checker, cfg: dict, rec: dict) -> dict:
    lid = law["law_id"]
    holds = law["statement"]["holds"]
    acts = sorted(act_names(holds, set()))
    sub = {a: f"f_{a}" for a in acts}
    tname = f"{lid}_twin".lower()
    fb = [f"  for f_{a}: {act_type(mdl, a)}" for a in acts]
    twin_laws = "\n".join(["import Base", model_import(law), "", f"law {tname}:", *fb,
                           *binder_lines(shape.binders), f"  {{{render(holds, 'M.', sub)} == True{{}} : Bool}}"]) + "\n"
    td = gen / f"{lid}_twin"
    tcls, tatt = try_prove(law, shape, td, tname, twin_laws, holds, ck, twin_sub=sub, fparams=[f"f_{a}" for a in acts])
    if tcls is None:
        shutil.rmtree(td, ignore_errors=True)
    else:
        rec["paths"].update(twin=f"{GEN}/{lid}_twin/PROOF.bend")
    rec["attempts"] += [f"twin {x}" for x in tatt]
    # the inhabitant
    iname = f"{lid}_inhabit".lower()
    ok_e = ok_all(law)
    wit, bound = search(law, shape, mdl, root, ok_e, True, cfg)
    inhabited = False
    idir = gen / f"{lid}_inhabit"
    if wit is not None:
        idir.mkdir(parents=True, exist_ok=True)
        (idir / "LAWS.bend").write_text(exs_laws(law, iname, shape.binders, f"{{{render(ok_e, 'M.')} == True{{}} : Bool}}"),
                                        encoding="utf-8")
        text = "\n".join(["import Base", model_import(law), "import ./LAWS.bend as Laws", "", f"def Laws.{iname}():",
                          "  " + nest(witness_term(shape, wit), "{==}")]) + "\n"
        (idir / "PROOF.bend").write_text(text, encoding="utf-8")
        inhabited, marker = ck.check(idir / "PROOF.bend", iname)
        second = ck.second(idir / "PROOF.bend") if inhabited else None
        inhabited = inhabited and second in (None, B.MARK_OK)
        rec["attempts"].append(f"inhabitant: bend2 {marker}" + ("" if second is None else f", BendTT {second}"))
    else:
        rec["attempts"].append(f"inhabitant: none found ({bound})")
    if inhabited:
        rec["paths"].update(inhabit=f"{GEN}/{lid}_inhabit/PROOF.bend")
    else:
        shutil.rmtree(idir, ignore_errors=True)
    return {"twin": "PROVED" if tcls else "UNKNOWN", "inhabited": inhabited,
            "trivially_true": bool(tcls) or not inhabited}


# ------------------------------------------------------------------ reviews (design V)
def review_of(root: Path, lid: str) -> dict:
    p = root / REVIEWS
    req = root / OUT / "review_requests.json"
    if not p.is_file():
        return {"reviewer": "absent", "compiler": COMPILER, "verdict": "absent"}
    rv = json.loads(p.read_text(encoding="utf-8"))
    same = req.is_file() and rv.get("requests_sha256") == sha256_file(req)
    v = (rv.get("verdicts") or {}).get(lid) if same else None
    return {"reviewer": rv["reviewer"], "compiler": rv["compiler"], "verdict": v["verdict"] if v else "absent"}


def run(root: Path, out_root: Path) -> list[Path]:
    """Decide every law into out_root (gen/ and results/ under it); the paths written."""
    cfg = B.config(root)
    ck = Checker(cfg)
    gen = out_root / GEN
    gen.mkdir(parents=True, exist_ok=True)
    if out_root != root:
        shutil.copytree(root / GEN / "model", gen / "model", dirs_exist_ok=True)
    recdir = out_root / OUT / "records"
    recdir.mkdir(parents=True, exist_ok=True)
    laws = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / LAWS).glob("L_intent_*.json"))]
    models: dict = {}
    written = []
    keep = set()
    for law in laws:
        if law["contract"] not in models:
            models[law["contract"]] = Model(json.loads((root / law["facts"]).read_text(encoding="utf-8")))
        rec = decide(law, models[law["contract"]], root, gen, ck, cfg)
        rec["review"] = review_of(root, law["law_id"])
        rv = rec["review"]
        rec["obstruction"] = (rec["status"] == "REFUTED" and rec["evidence"]["marker"] == B.MARK_OK
                              and rec["evidence"]["law_present"] and rv["verdict"] == "faithful"
                              and rv["reviewer"] != rv["compiler"])
        p = recdir / f"{law['law_id']}.json"
        p.write_text(dumps(rec), encoding="utf-8")
        written.append(p)
        keep.add(p.name)
    for p in sorted(recdir.glob("L_intent_*.json")):
        if p.name not in keep:
            p.unlink()
    lids = {lw["law_id"] for lw in laws}
    for p in sorted(gen.glob("L_intent_*")):
        if p.is_dir() and p.name.split("_twin")[0].split("_inhabit")[0] not in lids:
            shutil.rmtree(p)
    return written


def tree(base: Path) -> dict:
    out = {}
    for sub in (Path(GEN), Path(OUT) / "records"):
        d = base / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            rel = p.relative_to(base)
            if p.is_file() and (sub.name == "records" or rel.parts[3].startswith("L_intent_")):
                out[rel.as_posix()] = p.read_bytes()
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon intent run")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tmp", type=Path)
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if a.check:
        with tempfile.TemporaryDirectory(dir=a.tmp, prefix="intent-run-") as t:
            t = Path(t)
            run(root, t)
            got, want = tree(t), tree(root)
        bad = sorted(set(got) ^ set(want)) + sorted(k for k in set(got) & set(want) if got[k] != want[k])
        for b in bad:
            print(f"intent run: differs: {b}")
        print(f"intent run: {'CHECK OK' if not bad else 'CHECK FAILED'}")
        return 1 if bad else 0
    recs = run(root, root)
    for p in recs:
        r = json.loads(p.read_text(encoding="utf-8"))
        print(f"intent run: {r['law_id']} {r['status']}" + (f" ({r['proof_class']})" if r["proof_class"] else "")
              + (f" control {r['control']}" if r["control"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
