"""The intent compiler (key I55 design T1-T3): atoms whose sentence matches a template, and whose documented
declaration the lane can bind and model, become INTENT laws.

  python -m holon intent compile [--root DIR] [--check]

reads results/M5/intent/atoms.json and writes laws/INTENT/L_intent_<atom id>.json, laws/INTENT/REGISTRY.json,
results/M5/intent/compile.json (one entry per atom, with the outcome and its reason), gen/M5/intent/facts/ (the
factory frontend's transitions documents, holon.intent.extract) and gen/M5/intent/model/<contract>.bend
(holon.intent.model). Every law names exactly one clause, the atom it was compiled from. A template is a pattern of
English, never a control's or a target's name; a binding resolves the clause's nouns against the documented
contract's own names (parameters, storage), normalized.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import extract as X
from .common import COMPILER, GEN, LAWS, OUT, ROOT, dumps, git, norm, sha256_file, write_or_check
from .ir import IR_VERSION, statement_hash
from .model import Model, Unsupported, act, fn, ident, m, var  # noqa: F401
from .scope import sources

_TAGLEAD = re.compile(r"^@[A-Za-z][A-Za-z:-]*\s*")
_W = r"[a-z][a-z ]*?"
TEMPLATES = (
    ("bound", re.compile(rf"^(?:the )?(?P<subj>{_W}) (?:is|are) (?:at most|no more than) (?P<n>[0-9]+) percent of "
                         rf"(?:the )?(?P<of>[a-z][a-z ]*)$")),
    ("access", re.compile(rf"^only (?:the |an? )?(?P<role>{_W}) (?:can|may) (?P<verb>[a-z]+)(?: .*)?$")),
    ("access", re.compile(rf"^only (?:the |an? )?(?P<role>{_W}) (?:is |are )?allowed$")),
    ("monotone", re.compile(rf"^(?:the )?(?P<var>{_W}) (?:never decreases|never moves backwards|is non-decreasing)$")),
)


def clause_text(text: str) -> str:
    t = _TAGLEAD.sub("", text).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t[:-1] if t[-1:] in ".;!?" else t


def match(text: str):
    t = clause_text(text)
    for name, rx in TEMPLATES:
        mm = rx.match(t)
        if mm:
            return name, mm.groupdict()
    return None, None


class _Fail(Exception):
    def __init__(self, outcome: str, detail: str):
        super().__init__(detail)
        self.outcome, self.detail = outcome, detail


# ------------------------------------------------------------------ statements (design S)
def _ok(a: str, x: str) -> dict:
    return fn("U32.is_eq", act(f"chk_{ident(a)}", var("s"), var(x)), {"u32": 0})


def _implies_ok(a: str, x: str, claim: dict) -> dict:
    return fn("Bool.or", fn("Bool.not", _ok(a, x)), claim)


def statement(template: str, mdl: Model, actions: list[str], b: dict) -> dict:
    xs = ["x"] if len(actions) == 1 else [f"x{k}" for k in range(len(actions))]
    binders = [{"name": "s", "type": "St"}] + [{"name": x, "type": mdl.x_type(a)} for x, a in zip(xs, actions)]
    if template == "bound":
        a, x = actions[0], xs[0]
        claim = m("ip_le_pct", act(f"ret_{ident(a)}", var("s"), var(x)), {"u32": b["percent"]},
                  m(f"x_{ident(a)}_p_{ident(b['name'])}", var(x)))
        holds = _implies_ok(a, x, claim)
    elif template == "access":
        a, x = actions[0], xs[0]
        holds = _implies_ok(a, x, m("w_eq", m(f"x_{ident(a)}_caller", var(x)), m(f"st_{ident(b['name'])}", var("s"))))
    else:
        parts = [_implies_ok(a, x, m("w_ge", m(f"st_{ident(b['name'])}", act(f"post_{ident(a)}", var("s"), var(x))),
                                     m(f"st_{ident(b['name'])}", var("s")))) for x, a in zip(xs, actions)]
        holds = parts[-1]
        for p in reversed(parts[:-1]):
            holds = fn("Bool.and", p, holds)
    return {"binders": binders, "holds": holds}


def reading(template: str, mdl: Model, actions: list[str], b: dict) -> str:
    c = mdl.contract
    sig = lambda a: f"{a}({', '.join(mdl.actions[a]['params'])})"  # noqa: E731
    if template == "bound":
        return (f"For every pre-transaction state of {c} and every call of {sig(actions[0])} that does not revert, "
                f"the value it returns, times 100, is at most {b['percent']} times its argument {b['name']} "
                f"(exact integers).")
    if template == "access":
        return (f"For every pre-transaction state of {c} and every call of {sig(actions[0])} that does not revert, "
                f"the caller is the address stored in {b['name']}.")
    return (f"For every pre-transaction state of {c} and every call of each of its state-changing functions "
            f"({', '.join(sig(a) for a in actions)}) that does not revert, {b['name']} after the call is at least "
            f"{b['name']} before it.")


# ------------------------------------------------------------------ binding (design T2)
class Compiler:
    def __init__(self, root: Path, write: bool, srcmap: dict | None = None):
        self.root, self.write = root, write
        self.srcmap = srcmap      # {repo: checkout}; None: config/holon.json extract.sources (I55b: the corpus)
        self.docs: dict = {}       # (repo, commit, file, contract) -> (rel, doc) or _Fail
        self.models: dict = {}     # contract -> Model
        self.problems: list = []

    def source_text(self, atom: dict) -> str:
        if atom["commit"] is None:
            return (self.root / atom["file"]).read_text(encoding="utf-8")
        src = Path((self.srcmap or sources(self.root))[atom["repo"]])
        return git(["show", f"{atom['commit']}:{atom['file']}"], src).decode("utf-8")

    def document(self, atom: dict, contract: str):
        k = (atom["repo"], atom["commit"], atom["file"], contract)
        if k not in self.docs:
            src = self.root if atom["commit"] is None else Path((self.srcmap or sources(self.root))[atom["repo"]])
            if self.srcmap and atom["commit"] is not None:
                git(["checkout", "-q", atom["commit"]], src)   # the frontend compiles a checkout at its commit
            try:
                self.docs[k] = X.extract(self.root, atom["repo"], atom["commit"], atom["file"], contract, src,
                                         write=self.write, problems=self.problems)
            except X.ExtractFailed as e:
                self.docs[k] = _Fail("extraction_failed", str(e))
        got = self.docs[k]
        if isinstance(got, _Fail):
            raise got
        return got

    def compile(self, atom: dict):
        tname, g = match(atom["text"])
        if tname is None:
            raise _Fail("no_template", "no template matches the sentence")
        if not atom["file"].endswith(".sol"):
            return tname, _Fail("not_solidity", f"{atom['file']} is not a Solidity file (the lane models Solidity only)")
        d = atom["decl"]
        if d is None or d["kind"] != "function":
            return tname, _Fail("decl_not_function", f"the comment documents {'nothing' if d is None else 'a ' + d['kind']}"
                                + ("" if d is None or not d.get("name") else f" ({d['name']})"))
        contract = X.contract_at(self.source_text(atom), d["line"])
        if contract is None:
            return tname, _Fail("extraction_failed", "no contract encloses the documented function")
        try:
            rel, doc = self.document(atom, contract)
        except _Fail as e:
            return tname, e
        mdl = self.models.setdefault(contract, Model(doc))
        try:
            actions, b = self.bind(tname, g, mdl, d["name"])
        except _Fail as e:
            return tname, e
        bad = [f"{a}: {mdl.unsupported[a]}" for a in actions if a in mdl.unsupported]
        if bad:
            return tname, _Fail("model_unsupported", "; ".join(bad))
        st = statement(tname, mdl, actions, b)
        law = {"ir_version": IR_VERSION, "law_id": f"L_intent_{atom['id']}", "template": tname,
               "clauses": [atom["id"]], "control": atom["control"], "file": atom["file"], "contract": contract,
               "actions": actions, "facts": rel, "facts_sha256": self.facts_sha(rel, doc), "binding": b,
               "model": f"{GEN}/model/{contract}.bend", "statement": st,
               "reading": reading(tname, mdl, actions, b),
               "notes": f"compiled by {COMPILER} from the {tname} template; one clause, the atom {atom['id']}"}
        return tname, law

    def facts_sha(self, rel: str, doc: dict) -> str:
        import hashlib
        return hashlib.sha256(dumps(doc).encode("utf-8")).hexdigest()

    def bind(self, tname: str, g: dict, mdl: Model, fname: str):
        acts = {a["name"]: a for a in mdl.doc.get("actions") or []}
        if fname not in acts:
            raise _Fail("binding_failed", f"{fname} is not an external or public action of {mdl.contract}")
        a = acts[fname]
        if tname == "bound":
            if norm(g["subj"].split(" ")[0]) != norm(fname):
                raise _Fail("binding_failed", f"the subject '{g['subj']}' does not name {fname}")
            if a.get("returns") is None:
                raise _Fail("binding_failed", f"{fname} returns no value")
            ps = [p["name"] for p in a.get("params") or [] if norm(p["name"]) == norm(g["of"])]
            if len(ps) != 1:
                raise _Fail("binding_failed", f"'{g['of']}' names {len(ps)} parameters of {fname}")
            return [fname], {"noun": g["of"], "name": ps[0], "percent": int(g["n"])}
        if tname == "access":
            hits = [n for n, ty in mdl.scalars if norm(n) == norm(g["role"]) and ty.startswith("address")]
            if len(hits) != 1:
                raise _Fail("binding_failed", f"'{g['role']}' names {len(hits)} address scalars of {mdl.contract}")
            return [fname], {"noun": g["role"], "name": hits[0], "percent": None}
        hits = [n for n, ty in mdl.scalars if norm(n) == norm(g["var"]) and ty.startswith("uint")]
        if len(hits) != 1:
            raise _Fail("binding_failed", f"'{g['var']}' names {len(hits)} uint scalars of {mdl.contract}")
        actions = sorted(n for n, x in acts.items() if x.get("mutability") not in ("view", "pure"))
        if not actions:
            raise _Fail("binding_failed", f"{mdl.contract} has no state-changing action")
        return actions, {"noun": g["var"], "name": hits[0], "percent": None}


def build(root: Path, write: bool) -> tuple[dict, list]:
    """({path: text} of every output, problems of a check)."""
    from ..sorts.prelude3 import PRELUDE
    atoms = json.loads((root / OUT / "atoms.json").read_text(encoding="utf-8"))
    comp = Compiler(root, write)
    entries, laws = [], {}
    for a in sorted(atoms["atoms"] + atoms["controls"], key=lambda a: (a["file"], a["lines"], a["id"])):
        try:
            tname, got = comp.compile(a)
        except _Fail as e:
            tname, got = None, e
        if isinstance(got, _Fail):
            entries.append({"atom": a["id"], "control": a["control"], "template": tname, "outcome": got.outcome,
                            "law_id": None, "detail": got.detail})
        else:
            laws[got["law_id"]] = got
            entries.append({"atom": a["id"], "control": a["control"], "template": tname, "outcome": "compiled",
                            "law_id": got["law_id"], "detail": f"{got['contract']}: {', '.join(got['actions'])}"})
    files = {root / LAWS / f"{lid}.json": dumps(lw) for lid, lw in sorted(laws.items())}
    files[root / LAWS / "REGISTRY.json"] = dumps({lid: statement_hash(lw) for lid, lw in sorted(laws.items())})
    files[root / OUT / "compile.json"] = dumps({"compiler": COMPILER, "entries": entries})
    for c, mdl in sorted(comp.models.items()):
        files[root / GEN / "model" / f"{c}.bend"] = mdl.text(PRELUDE)
    return files, comp.problems


def stale(root: Path, files: dict) -> list[Path]:
    keep = {Path(p) for p in files}
    out = [p for p in sorted((root / LAWS).glob("L_intent_*.json")) if p not in keep]
    out += [p for p in sorted((root / GEN / "model").glob("*.bend")) if p not in keep]
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon intent compile")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    files, probs = build(root, write=not a.check)
    if a.check:
        bad = probs + write_or_check(files, True) + [str(p) + " (stale)" for p in stale(root, files)]
        for b in bad:
            print(f"intent compile: differs: {b}")
        print(f"intent compile: {'CHECK OK' if not bad else 'CHECK FAILED'}")
        return 1 if bad else 0
    for p in stale(root, files):
        p.unlink()
    n = len(write_or_check(files, False))
    print(f"intent compile: {n} file(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
