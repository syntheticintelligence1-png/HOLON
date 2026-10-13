"""`holon run` for state-machine milestones (holon-ir/0.2 and 0.3, M1 onward).

Same contract as M0 (holon.pipeline): every frozen law ends PROVED, REFUTED or UNKNOWN,
with a result record; Bend's verdict is final; witnesses come from the compiled model.

For each law, in law_id order:
  1. exists laws: the strategy search proposes a witness; the `evaluate` generator checks it;
  2. forall laws: try the proof generators (holon.gen.mproofs) in order;
  3. otherwise search the compiled model for a witness (holon/js/explore.mjs) and emit a
     counter-law; REFUTED iff Bend accepts it;
  4. otherwise UNKNOWN, with what was tried.

holon-ir/0.3 (I7): a law whose premises the IR rejects (holon.ir.check_premises, e.g. global
injectivity) is not run; the counter-law of a conjunction names the conjunct that fails at the
witness (evaluated on the compiled model), recorded as failing_conjunct; an existential law is
never REFUTED: when no witness is found it stays UNKNOWN with bounded_negative {H, space} and its
generated negation (holon.gen.mlaws.negation_ir) is decided by the same proof generators.

Hashes and oracles as parameters (I12; M2+ milestones): the model of a facts file with an oracle sidecar
(holon.gen.oracles) takes its hashes and oracles as parameters (oracle tables). A law whose hyp premises do
not resolve against the sidecar is not run. Its statement hash covers the hypotheses it names
(holon.gen.refs.law_hash(.., oracles=)); a law over the parameters alone is tried by param_premise
(mproofs) after the other classes; the refuter's candidates for a parameter are the sidecar's concrete
instances, then the empty table, and a counter-law supplies the table its witness denotes at the points
the statement queries, carrying the law's hypothesis premises as `exs hN` lines; model_assumptions is
exactly the set of hypothesis premises (§8.5); and the run writes <out>/splits.json (holon-splits/0.1:
hypothesis splits are law pairs, found from statements).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import bend, bindings, inhabit, ir, records
from . import facts as F
from .gen import mlaws, mproofs
from .gen import oracles as O
from .gen import refs as R
from .gen import targetlib
from .gen.machine import Machine
from .replay import replay_status, load_report

ROOT = Path(__file__).resolve().parents[1]
EXPLORE = Path(__file__).resolve().parent / "js" / "explore.mjs"
MACHINE_JS = Path(__file__).resolve().parent / "js" / "machine.mjs"
HOUDINI = Path(__file__).resolve().parent / "js" / "houdini.mjs"


def model_name(facts_path: Path) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_]", "_", Path(facts_path).stem) or "model"


class CompiledMachine:
    def __init__(self, source: Path, artifact: Path, facts: dict, machine: Machine, facts_path: Path | None = None,
                 cfg: dict | None = None):
        self.source, self.artifact, self.facts, self.m = source, artifact, facts, machine
        self.facts_path = Path(facts_path) if facts_path else None
        self.oracles = machine.orc
        self.cfg = cfg
        self._inst = None

    def hints(self) -> str | None:
        """The facts' untrusted search-hints module (holon.gen.targetlib), or None for the generic policy."""
        h = targetlib.hints_for(self.facts_path)
        return str(h) if h else None

    @classmethod
    def build(cls, facts_path: Path, cfg: dict | None = None, reach: bool = False,
              anchor: Path | None = None, oracles=None) -> "CompiledMachine":
        """reach: emit the Reach predicate (M2+ milestones, I8). anchor: the facts file whose target
        libraries and search hints apply (holon.gen.targetlib), when facts_path stands in for it (a
        `--facts` override such as a mutated copy); by default facts_path itself. oracles: the facts'
        oracle sidecar (M2+ milestones, I12)."""
        facts = F.load(facts_path)
        sha = F.sha256_file(facts_path)
        m = Machine(facts, anchor or facts_path, oracles=oracles, m2plus=reach)
        text = m.generate(sha, reach)
        tag = ("-reach" if reach else "") + (f"-orc{hashlib.sha256(text.encode()).hexdigest()[:8]}" if oracles else "")
        src, art = cls._compile(text, sha, tag, facts_path, cfg)
        return cls(src, art, facts, m, Path(anchor or facts_path), cfg)

    @staticmethod
    def _compile(text: str, sha: str, tag: str, facts_path: Path, cfg: dict | None) -> tuple[Path, Path]:
        """Write the model text to the build dir and compile it to an ES module (cached by the text's hash)."""
        src = bend.build_dir(ROOT) / "eval" / (sha[:16] + tag) / f"{model_name(facts_path)}.bend"
        src.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists() or src.read_text() != text:
            src.write_text(text)
        art = src.with_suffix(".mjs")
        stamp = src.with_suffix(".src.sha256")
        h = hashlib.sha256(text.encode()).hexdigest()
        if not (art.exists() and stamp.exists() and stamp.read_text() == h):
            r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=cfg)
            if r.code != 0 or not art.exists():
                raise RuntimeError(f"bend failed to compile {src}: {r.out[:2000]}")
            stamp.write_text(h)
        return src, art

    @classmethod
    def instrumented(cls, milestone: str, facts_path: Path, derivation: dict, cfg: dict | None = None,
                     anchor: Path | None = None, root: Path | None = None) -> "CompiledMachine":
        """The instrumented model of a document (I15; holon.sorts.sites.instrumented_model with the milestone's
        DERIVATION.json): the run's model, then the ghost section of its SORT-site laws. The machine is the run's
        (holon.sorts.sites.run_machine), so every generator emits against the model above the marker."""
        from .sorts import sites
        root = Path(root or ROOT)
        m, facts, text = sites.run_machine(milestone, Path(facts_path), root, anchor)
        inst = sites.instrumented_model(Path(facts_path), derivation, root, anchor)
        if not inst.startswith(text.rstrip("\n") + "\n\n" + sites.GHOST_MARKER + "\n"):
            raise RuntimeError(f"{facts_path}: the instrumented model does not extend the run's model")
        sha = F.sha256_file(facts_path)
        src, art = cls._compile(inst, sha, f"-reach-inst{hashlib.sha256(inst.encode()).hexdigest()[:8]}", Path(facts_path), cfg)
        return cls(src, art, facts, m, Path(anchor or facts_path), cfg)

    # ------------------------------------------------------------ oracle parameters (I12)
    def instance_module(self) -> tuple[Path | None, list[dict], list[str]]:
        """(compiled module, [{id, param, fn}], notes): the model plus one inst_<entry> def per sidecar instance,
        compiled for the refuter (untrusted search: an instance that does not compile is not tried)."""
        if self._inst is not None:
            return self._inst
        orc = self.m.orc
        items = [(e, O.inst_name(e["id"])) for e in (orc.entries if orc else [])
                 if e in orc.instances(e["parameter"]["name"])]
        model_text = self.source.read_text()

        def compiled(sel):
            text = model_text + "\n" + "\n".join(mlaws.instance_def(self.m, e, n, qualified=False) for e, n in sel)
            h = hashlib.sha256(text.encode()).hexdigest()
            src = self.source.parent / f"{self.source.stem}.inst-{h[:12]}.bend"
            art = src.with_suffix(".mjs")
            if not art.exists():
                src.write_text(text)
                r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=self.cfg)
                if r.code != 0 or not art.exists():
                    return None
            return art
        notes: list[str] = []
        art = compiled(items) if items else None
        if items and art is None:
            good = [x for x in items if compiled([x]) is not None]
            notes = [f"the instance of {e['id']} does not compile with the model: not tried" for e, n in items if (e, n) not in good]
            items = good
            art = compiled(items) if items else None
        self._inst = (art, [{"id": e["id"], "param": e["parameter"]["name"], "fn": n} for e, n in items], notes)
        return self._inst

    def oracle_req(self) -> dict | None:
        """What the refuter needs to know of the oracle parameters (holon/js/explore.mjs)."""
        if not self.m.oparams:
            return None
        art, insts, _ = self.instance_module()
        return {"params": {p: {"type": f"Fn<{a},{b}>", "dom": a, "cod": b} for p, (a, b) in self.m.oparams.items()},
                "threaded": list(self.m.threaded), "fnTabs": self.m.fn_tabs, "instances": insts,
                "instModule": str(art) if art else None}

    def _req(self, law: dict, **kw) -> str:
        """An explore.mjs request; hyp premises go as their predicates (the refuter evaluates premises). The ghost
        predicates of the SORT-site terms a statement uses go along (req.sites, I15)."""
        if O.hyp_names(law):
            law = O.expand_hyps(law, self.m.orc)
        r = {"module": str(self.artifact), "facts": self.facts, "hints": self.hints(), "law": law, **kw}
        orc = self.oracle_req()
        if orc is not None:
            r["oracles"] = orc
        sts = site_terms(law)
        if sts:
            r["sites"] = {sid: ghost_fns(sid, self.m) for sid in sts}
        return json.dumps(r)

    def site_search(self, law: dict, mode: str, entries: list[str], stage: str = "S2", seeds: dict | None = None,
                    s3max: int | None = None) -> dict:
        """The SORT-site search of holon/js/explore.mjs (stages S1-S3, untrusted) for a site law: mode "refute" (a
        witness per entry point where the ghost predicate is false) or "inhabit" (a reachable (s, a) that reaches a
        hit)."""
        sid = site_law(law)
        g = ghost_fns(sid, self.m)
        site = {"fn": g["site"], "hit": g["hit"], "entries": sorted(entries), "mode": mode, "stage": stage,
                "seeds": seeds or {}}
        if s3max is not None:
            site["s3max"] = s3max
        p = subprocess.run(["node", str(EXPLORE)], input=self._req(law, site=site, budget={}),
                           capture_output=True, text=True, timeout=7200)
        if p.returncode != 0:
            raise RuntimeError(f"site search failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def evaluate(self, law: dict, assignment: dict) -> dict:
        """Premises and claims of a law at one assignment, on the compiled model."""
        p = subprocess.run(["node", str(EXPLORE)], input=self._req(law, evaluate=assignment),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"evaluate failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def explore(self, law: dict, budget: dict | None = None) -> dict:
        p = subprocess.run(["node", str(EXPLORE)], input=self._req(law, budget=budget or {}),
                           capture_output=True, text=True, timeout=3600)
        if p.returncode != 0:
            raise RuntimeError(f"explore failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def houdini(self, budget: dict | None = None) -> dict:
        """Strengthening proposals (holon/js/houdini.mjs; untrusted)."""
        p = subprocess.run(["node", str(HOUDINI)], input=json.dumps({"module": str(self.artifact), "facts": self.facts,
                                                                      "hints": self.hints(), "budget": budget or {}}),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(f"houdini failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)

    def oracle_runtime(self) -> dict | None:
        """For machine.mjs and policy.mjs (holon/js/oracle_model.mjs): the model's oracle parameters answered by their
        sidecar instances (the I12 design), and the tables each function threads (passed empty). None without
        parameters (M0, M1)."""
        if not self.m.oparams:
            return None
        art, insts, _ = self.instance_module()
        return {"instModule": str(art) if art else None,
                "instances": [{"id": i["id"], "param": i["param"], "fn": i["fn"]} for i in insts], "fnTabs": self.m.fn_tabs}

    def calls(self, calls: list, instances: bool = False) -> list:
        """Evaluate model calls with machine.mjs. A function that threads oracle tables takes them as explicit
        arguments; with instances=True (the M2 trace corpus of `holon replay`, whose calls pass no tables) every
        lookup of a parameter with a sidecar instance is answered by that instance instead (oracle_runtime)."""
        req = {"module": str(self.artifact), "calls": calls}
        orc = self.oracle_runtime() if instances else None
        if orc is not None:
            req["oracles"] = orc
        p = subprocess.run(["node", str(MACHINE_JS)], input=json.dumps(req), capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-2000:])
        return json.loads(p.stdout)["results"]


# ---------------------------------------------------------------- I15: SORT-site laws
def site_terms(law: dict) -> list[str]:
    """The site ids of the SORT-site terms ({"site": ID, "on", "from"}, or the at_site premise) a statement uses."""
    out: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            for k in ("site", "at_site"):
                if isinstance(x.get(k), str) and "on" in x and "from" in x and x[k] not in out:
                    out.append(x[k])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(law.get("statement", {}))
    return out


def site_law(law: dict) -> str | None:
    """The site id of a SORT-site law (rule SORT, subform site, claim site(..) == true), else None."""
    if law.get("rule") != "SORT" or law.get("subform") != "site":
        return None
    c = law.get("statement", {}).get("claim", {})
    eq = c.get("eq") if isinstance(c, dict) else None
    if not (isinstance(eq, list) and len(eq) == 2 and isinstance(eq[0], dict) and isinstance(eq[0].get("site"), str)):
        return None
    return eq[0]["site"]


def ghost_fns(site_id: str, m: Machine) -> dict:
    """The ghost predicates of a site in the instrumented model: site_<x>, hit_<x> and the tables they take."""
    from .sorts.sites import ghost_x, law_id
    x = ghost_x(law_id(site_id))
    return {"site": f"site_{x}", "hit": f"hit_{x}", "tabs": list(m.threaded)}


def derivation_of(milestone: str, root: Path | None = None) -> dict | None:
    """laws/<M>/DERIVATION.json of the tree (holon derive, I15), or None."""
    p = Path(root or ROOT) / "laws" / milestone / "DERIVATION.json"
    return json.loads(p.read_text()) if p.exists() else None


def has_sites(derivation: dict | None, facts_path: Path, root: Path | None = None) -> bool:
    """Whether the derivation holds SORT-site laws of this document (so its run's model is instrumented)."""
    if not derivation:
        return False
    try:
        rel = Path(facts_path).resolve().relative_to(Path(root or ROOT).resolve()).as_posix()
    except ValueError:
        rel = Path(facts_path).as_posix()
    return any(e.get("facts") == rel and e.get("rule") == "SORT" and e.get("subform") == "site"
               for e in derivation.get("laws", []))


def relpath(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p)


def _first(out: str, n: int = 14) -> str:
    return "\n".join(out.strip().splitlines()[:n])


def witness_difference(cm: CompiledMachine, law: dict, witness: dict, conjunct: int | None = None) -> dict | None:
    """The claim's two sides at the witness (of conjunct `conjunct` of a conjunction), evaluated on the
    compiled model (decoded JSON)."""
    def to_js(t, ty_env):
        # IR term -> machine.mjs expression, with witness values substituted
        if "var" in t:
            n = t["var"]
            return _value_js(cm.m, ty_env[n], witness[n])
        if "nat" in t:
            return {"val": t["nat"]}
        if "bool" in t:
            return {"val": t["bool"]}
        if "nats" in t:
            return {"val": t["nats"]}
        if "s0" in t:
            return {"fn": "s0", "args": []}
        if "run" in t:
            return {"fn": "run", "args": [to_js(t["run"], ty_env), to_js(t["from"], ty_env)]}
        if "step" in t:
            return {"fn": "step", "args": [to_js(t["step"], ty_env), to_js(t["from"], ty_env)]}
        if "obs" in t:
            return {"fn": "obs", "args": [to_js(t["obs"], ty_env), to_js(t["from"], ty_env)]}
        if "trace" in t:
            return {"val": [_act_obj(cm.m, a, ty_env, witness) for a in t["trace"]]}
        if "cat" in t:
            a, b = to_js(t["cat"][0], ty_env), to_js(t["cat"][1], ty_env)
            if "val" not in a or "val" not in b:
                raise ValueError("cat of non-literal traces")
            return {"val": a["val"] + b["val"]}
        if "act" in t:
            return {"val": _act_obj(cm.m, t, ty_env, witness)}
        if "plus" in t:
            x, y = to_js(t["plus"][0], ty_env), to_js(t["plus"][1], ty_env)
            if "val" not in x or "val" not in y:
                raise ValueError("plus of computed terms")
            return {"val": x["val"] + y["val"]}
        if "obsv" in t:
            return {"fn": t["obsv"], "args": [to_js(t["of"], ty_env)]}
        if "mig" in t:
            return {"fn": "mig_" + t["mig"], "args": [to_js(t["of"], ty_env)] + [to_js(a, ty_env) for a in t.get("args", [])]}
        if "fn" in t:
            return {"fn": t["fn"], "args": [to_js(a, ty_env) for a in t["args"]]}
        raise ValueError(t)
    st = law["statement"]
    ty_env = {b["name"]: b["type"] for b in st["binders"]}
    if any(n in cm.m.oparams and t.startswith("Fn<") for n, t in ty_env.items()):   # oracle parameters (I12)
        try:
            sides = (cm.evaluate(law, witness).get("sides") or [])
        except RuntimeError:
            return None
        i = conjunct or 0
        return {"lhs": sides[i][0], "rhs": sides[i][1]} if i < len(sides) and sides[i] else None
    c = st["claim"]
    if "all" in c:
        if conjunct is None:
            return None
        c = c["all"][conjunct]
    if set(c) != {"eq"}:
        return None
    try:
        lhs, rhs = cm.calls([to_js(c["eq"][0], ty_env), to_js(c["eq"][1], ty_env)])
    except (ValueError, KeyError, RuntimeError):
        return None
    return {"lhs": lhs, "rhs": rhs}


def _value_js(m: Machine, ty: str, v):
    if ty == "Reach":
        ty = "State"
    if ty in ("Nat", "Bool"):
        return {"val": v}
    if ty == "Act":
        return {"val": _act_val(m, v)}
    if ty == "Trace":
        return {"val": [_act_val(m, a) for a in v]}
    if ty == "State":
        if "state" in v:
            return {"val": v["state"]}
        return {"fn": "run", "args": [{"val": [_act_val(m, a) for a in v["run"]]}, {"fn": "s0", "args": []}]}
    raise ValueError(ty)


def _act_val(m: Machine, a: dict) -> dict:
    spec = next(x for x in m.actions if x["name"] == a["op"])
    return {"$": f"A_{a['op']}", **{n: a[n] for n, _ in spec["inputs"]}}


def _act_obj(m, t, ty_env, witness):
    if "var" in t:
        return _act_val(m, witness[t["var"]])
    if "act" in t:
        spec = next(x for x in m.actions if x["name"] == t["act"])
        out = {"$": f"A_{t['act']}"}
        for n, _ in spec["inputs"]:
            x = t["args"][n]
            out[n] = x.get("nat", x.get("bool", x.get("nats", witness.get(x.get("var")))))
        return out
    raise ValueError(t)


def scope_fields(law: dict, rec: dict) -> dict:
    """A 0.3 record's scope, from the statement and never from the status (whitepaper §8.6, audit F-M2-01):
    scope is bounded iff statement.scope is not unbounded; statement_scope is the IR scope itself; scope_v2 gives
    its kind and horizon. The search bound of an UNKNOWN law stays in `bound`. (0.1/0.2 records keep their
    pinned M0/M1 meaning: scope there is the search's.)"""
    sc = ir.scope_of(law)
    kind = sc.get("kind")
    horizon = (f"bounded: every trace of at most {sc.get('H')} actions" if kind == "bounded"
               else f"at state {sc.get('ref')}" if kind == "at_state" else None)
    out = {"scope": "unbounded" if kind == "unbounded" else "bounded", "statement_scope": sc,
           "scope_v2": {"kind": "unbounded" if kind == "unbounded" else "bounded", "horizon": horizon}}
    if kind != "unbounded" and not rec.get("bound"):
        out["bound"] = horizon
    return out


def test_milestone(milestone: str) -> bool:
    """A test milestone (T15, ...: a fixture run in a copy, never committed) rather than a target milestone M<n>."""
    import re
    return re.fullmatch(r"M\d+", milestone) is None


def m2plus(milestone: str) -> bool:
    """Milestones after M1 (M2.., and the test milestones T*) use the core library and Reach (I8)."""
    return milestone not in ("M0", "M1")


def milestone_model(milestone: str, facts_path: Path, cfg: dict | None = None, anchor: Path | None = None,
                    root: Path | None = None) -> CompiledMachine:
    """The model milestone M compiles facts F to (audit M2/1 F-M2-11): for M2+ the Reach predicate (I8), permissions
    from the permission guards (F-M2-26) and the milestone's oracle sidecar, so hashes and oracles are parameters
    and their stand-ins survive only as instances (I12; holon.gen.oracles.Oracles.for_milestone: M2 over
    spec/M1/facts takes spec/M2/lib/oracles.json). M0 and M1: the model as bound. root: the tree F lives in."""
    orc = O.Oracles.for_milestone(milestone, anchor or facts_path, root or ROOT)
    return CompiledMachine.build(facts_path, cfg, reach=m2plus(milestone), anchor=anchor, oracles=orc)


def run_model(milestone: str, facts_path: Path, cfg: dict | None = None, anchor: Path | None = None,
              root: Path | None = None) -> CompiledMachine:
    """The model `holon run` checks a document's laws against: milestone_model, followed, when laws/<M>/DERIVATION.json
    holds SORT-site laws of the document, by their ghost section (the instrumented model, I15)."""
    der = derivation_of(milestone, root) if m2plus(milestone) else None
    if has_sites(der, anchor or facts_path, root):
        return CompiledMachine.instrumented(milestone, facts_path, der, cfg, anchor=anchor, root=root)
    return milestone_model(milestone, facts_path, cfg, anchor, root)


def main_model(args) -> int:
    """`holon model --milestone M --facts F [--out DIR]`: build milestone M's model of F, check it in Bend, print its
    oracle parameters; with --out, write <DIR>/<model>.bend."""
    cfg = bend.config(ROOT)
    fp = (ROOT / args.facts) if not Path(args.facts).is_absolute() else Path(args.facts)
    try:
        doc = json.loads(fp.read_text())
    except (OSError, ValueError):
        doc = None
    from . import machine as extracted_machine
    if extracted_machine.is_transitions(doc):   # an extracted transitions document (I20): the raw-family model
        return extracted_machine.main_model(args)
    cm = milestone_model(args.milestone, fp, cfg)
    r = bend.check(cm.source, cfg)
    print(f"model {cm.source}")
    print(f"oracle sidecar: {relpath(cm.oracles.path) if cm.oracles is not None else 'none'}; parameters "
          f"{sorted(cm.m.oparams) or 'none'}; threaded through step and run: {cm.m.threaded or 'none'}")
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / cm.source.name).write_text(cm.source.read_text())
        print(f"wrote {out / cm.source.name}")
    print(r.first_line)
    return 0 if r.ok else 1


# ---------------------------------------------------------------- I10: prover separation (whitepaper L14)
LEGACY_LAYOUT = ("M0", "M1")   # their gen/ trees are pinned byte for byte (tests_m2/test_target_agnostic.py)


def layout(milestone: str, gen: Path, lid: str) -> tuple[Path, Path, str]:
    """(laws dir, proofs dir, path from either dir up to gen/) of a law's LAWS.bend and PROOF.bend.

    M0 and M1 keep their layout: both files in gen/<law>/. Every other milestone separates the statement
    from its prover: gen/laws/<law>/LAWS.bend and gen/proofs/<law>/PROOF.bend, the proof importing the law
    by relative path (separated_proof), so G3 rejects any `law` declared under proofs/
    (holon.gate.laws_in_proofs). A law's inhabitant (gen/<law>/nonvac/) and the negation of an existential
    law (gen/<law>/neg/) are generated statements with their proofs, regenerated by G11V and G1; they stay in
    gen/<law>/ for every milestone."""
    if milestone in LEGACY_LAYOUT:
        return gen / lid, gen / lid, "../"
    return gen / "laws" / lid, gen / "proofs" / lid, "../../"


def separated_proof(text: str, laws_dir: Path, proofs_dir: Path) -> str:
    """A generated PROOF.bend that imports its LAWS.bend from the laws side (unchanged when both share a dir)."""
    if laws_dir == proofs_dir:
        return text
    rel = Path(os.path.relpath(laws_dir / "LAWS.bend", proofs_dir)).as_posix()
    return text.replace("import ./LAWS.bend as Laws", f"import {rel} as Laws", 1)


def write_pair(laws_dir: Path, proofs_dir: Path, laws_text: str, proof_text: str) -> Path:
    """Write a law and its proof where layout() puts them; returns the PROOF.bend path."""
    for x in (laws_dir, proofs_dir):
        x.mkdir(parents=True, exist_ok=True)
    (laws_dir / "LAWS.bend").write_text(laws_text)
    (proofs_dir / "PROOF.bend").write_text(separated_proof(proof_text, laws_dir, proofs_dir))
    return proofs_dir / "PROOF.bend"


def accepted(rr, proof: Path, laws_file: Path, em, proof_text: str) -> tuple[bool, str | None]:
    """(ok, error) at an acceptance point: Bend said ALL PROOFS CHECK, the law file states exactly the expected law,
    the proof imports that law file (law_import_problem) and neither file uses an escape hatch."""
    if not rr.ok:
        return False, _first(rr.out)
    if _law_names(em.text) != [em.name]:
        return False, f"the law file does not state exactly {em.name}"
    bad = law_import_problem(proof, laws_file)
    if bad:
        return False, bad
    if bend.escape_hatches(proof_text + em.text):
        return False, "escape hatch"
    return True, None


# what `holon run` writes under a milestone's gen dir, besides the law dirs gen/<m>/L* (audit F-M2-25): it removes and
# rewrites only these; every other command's output there (diagram/, sorts/, oracles/, evidence.json) stays
RUN_OUTPUTS = ("model", "core", "laws", "proofs")


def clean_gen(gen: Path, only: list[str] | None = None) -> None:
    """Remove what a run rewrites: gen/<m>/{model,core} and the law dirs (gen/<m>/L*, laws/<id>, proofs/<id>), all of
    them, or with `only` (--laws) those of the listed laws."""
    gen.mkdir(parents=True, exist_ok=True)
    for x in ("model", "core"):
        shutil.rmtree(gen / x, ignore_errors=True)
    for x in ("laws", "proofs"):
        if only is None:
            shutil.rmtree(gen / x, ignore_errors=True)
        else:
            for lid in only:
                shutil.rmtree(gen / x / lid, ignore_errors=True)
    for x in sorted(gen.glob(ir.LAW_GLOB.replace(".json", ""))):
        if only is not None and x.name not in only:
            continue
        if x.is_dir():
            shutil.rmtree(x)
        else:
            x.unlink()


def run_m1(milestone: str, facts_path: str | None, out: str | None, gen_dir: str | None, no_registry: bool, log=print,
           core: str = "import", only: list[str] | None = None) -> dict:
    cfg = bend.config(ROOT)
    laws = ir.load_laws_any(milestone, ROOT)
    reg = ir.load_registry(milestone, ROOT)
    if only is not None:
        unknown = sorted(set(only) - {l["law_id"] for l in laws})
        if unknown:
            raise ValueError(f"--laws names laws that laws/{milestone} does not hold: {unknown}")
    primary = reg["facts"]
    override = Path(facts_path) if facts_path else None
    out_dir = Path(out or ROOT / "results" / milestone)
    gen = Path(gen_dir or ROOT / "gen" / milestone)

    def fpath_of(law: dict) -> Path:
        return override if (override and law["facts"] == primary) else ROOT / law["facts"]
    if no_registry:
        laws = [ir.rebind_facts(l, F.sha256_file(fpath_of(l))) for l in laws]
    else:
        check_registry_multi(laws, reg, milestone)
    kver = bend.version(cfg)
    if kver != cfg["bend"]["pinned_version"]:
        raise RuntimeError(f"bend {kver} is not the pinned {cfg['bend']['pinned_version']}")
    verdict = bend.verdict_enabled(cfg)
    triage = {}
    tp = ROOT / "config" / "triage.json"
    if tp.exists():
        triage = json.loads(tp.read_text()).get(milestone, {})
    report = None if no_registry else load_report(milestone, ROOT)

    clean_gen(gen, only)
    (gen / "model").mkdir(parents=True)
    der = derivation_of(milestone) if m2plus(milestone) else None   # SORT-site laws and their entry points (I15)
    machines: dict = {}
    oracles_of: dict = {}   # law id -> the oracle sidecar of its facts (M2+, I12), for splits.json
    from .gen import core as C
    mproofs.CORE_MODE, mproofs.CORE_PASTE = None, ""
    if m2plus(milestone):
        mproofs.CORE_MODE = core
        if core == "import":
            C.emit(gen, cfg=cfg)
        else:
            mproofs.CORE_PASTE = C.paste_text(gen, cfg)
            shutil.rmtree(gen / "core", ignore_errors=True)

    def machine_for(law: dict):
        fp = fpath_of(law)
        if fp not in machines:
            # a --facts override stands in for the registry's facts: it takes their target libraries and
            # search hints (I6 put them next to the facts; a mutated copy elsewhere would otherwise lose them)
            anchor = ROOT / primary if (override and fp == override) else None
            orc = O.Oracles.for_milestone(milestone, anchor or fp, ROOT)   # M0, M1 never read one (I12; F-M2-11)
            if has_sites(der, anchor or fp):   # the instrumented model: the run's model and its ghost section (I15)
                cm_ = CompiledMachine.instrumented(milestone, fp, der, cfg, anchor=anchor)
            else:
                cm_ = CompiledMachine.build(fp, cfg, reach=m2plus(milestone), anchor=anchor, oracles=orc)
            src = gen / "model" / f"{model_name(fp)}.bend"
            src.write_text(cm_.source.read_text())
            (gen / "model" / f"{model_name(fp)}.defs.json").write_text(bindings.dump(bindings.defs_index(src, cfg)))
            machines[fp] = (cm_, src, f"../model/{model_name(fp)}.bend", F.sha256_file(fp))
        return machines[fp]
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {}
    kbound = {"milestone": milestone, "laws": {}}
    by_id = {l["law_id"]: l for l in laws}
    neg_recs: dict = {}   # frozen negation laws (negation_of, holon.ir.negation_law), run first so the ∃-law links them
    for law in sorted(laws, key=lambda l: (not l.get("negation_of"), l["law_id"])):
        lid = law["law_id"]
        if only is not None and lid not in only:
            continue
        sid = site_law(law) if m2plus(milestone) else None   # a SORT-site law (I15)
        cm, model_src, imp0, facts_sha = machine_for(law)
        d = gen / lid
        ld, pd, up = layout(milestone, gen, lid)   # I10: d for M0 and M1
        imp = f"{up}model/{model_src.name}"         # the model, from ld and pd (imp0 from d)
        attempts: list = []
        oracles_of[lid] = cm.oracles
        shash = R.law_hash(law, cm.facts, oracles=cm.oracles)
        rec = {"law_id": lid, "statement_hash": shash, "facts_sha256": facts_sha,
               "rule": law["rule"], "subform": law.get("subform"), "maps_to": law.get("maps_to"),
               "statement": ir.render_statement(law), "premises": ir.premises(law),
               "kernel": {"name": "bend", "version": kver, "verdict": "not_run"},
               "artifacts": {"laws": None, "proof": None, "model": relpath(model_src), "law_name": None},
               "checker": {"exit_code": None, "marker": "not_run"}, "witness": None, "difference": None,
               "triage": "none", "replay": {"status": "not_run", "detail": "certificates are not replayed; refinement replay corpus in replay/M1"}}
        status, em, r = "UNKNOWN", None, None
        bound = None
        stmt_text = records.ir_roots_text(law)
        try:
            ir.check_premises(law)
            if law.get("ir_version") == "holon-ir/0.3":   # record-ref binder types name a facts type (F-M2-18)
                ir.check_binder_types(law, cm.facts)
            if m2plus(milestone):
                O.check_law(law, cm.oracles)
            E = mlaws.Emitter(cm.m)
            em = E.emit(law, imp, note=shash)
            stmt_text = em.text
            exists = any(b["q"] == "exists" for b in law["statement"]["binders"])
            witness = None
            witness_raw = None
            if exists:
                s = cm.explore(law)
                attempts.append({"kind": "strategy-search", "tried": s["tried"], "hit": s["witness"] is not None})
                witness = witness_raw = s["witness"]
                bound = s["bound"]
                if witness is not None:   # oracle parameters (I12): the tables the witness denotes, as in counter-laws
                    witness = mlaws.resolve_witness(cm.m, em.binders, witness,
                                                    {p_: [k for k, _ in es] for p_, es in (s.get("tables") or {}).items()})
            for gname, g in mproofs.GENERATORS:
                text = g(em, cm.m, imp, witness) if gname == "evaluate" else g(em, cm.m, imp)
                if text is None:
                    continue
                proof_f = write_pair(ld, pd, em.text, text)
                rr = bend.check(proof_f, cfg)
                ok, why = accepted(rr, proof_f, ld / "LAWS.bend", em, text)
                attempts.append({"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker,
                                 "seconds": rr.seconds, **({} if ok else {"error": why})})
                if ok:
                    status, r = "PROVED", rr
                    if exists:
                        rec["witness"] = witness_raw
                    break
            if status != "PROVED" and sid is not None:   # I15: mirror the ghost chain (holon.gen.coercion)
                text, why = mproofs.coercion_guard(em, cm.m, imp, cm.source.read_text())
                if text is None:
                    attempts.append({"kind": "proof", "generator": "coercion_guard", "error": f"does not apply: {why}"})
                else:
                    proof_f = write_pair(ld, pd, em.text, text)
                    rr = bend.check(proof_f, cfg)
                    ok, err = accepted(rr, proof_f, ld / "LAWS.bend", em, text)
                    attempts.append({"kind": "proof", "generator": "coercion_guard", "exit_code": rr.code,
                                     "marker": rr.marker, "seconds": rr.seconds, "basis": why,
                                     **({} if ok else {"error": err})})
                    if ok:
                        status, r = "PROVED", rr
            if status != "PROVED" and not exists and sid is None:
                got = param_search(em, cm, imp, ld, pd, cfg, attempts)
                if got is not None:
                    status, r = "PROVED", got
            if status != "PROVED" and not exists and any(b["type"] == "Reach" for b in law["statement"]["binders"]):
                got = reach_search(em, cm, imp, ld, pd, cfg, attempts)
                if got is not None:
                    status, r = "PROVED", got
            if status != "PROVED" and exists:
                # never REFUTED: a bounded negative search, and the generated negation decided instead
                rec["bounded_negative"] = {"H": bound, "space": attempts[0]["tried"] if attempts else 0}
                neg = by_id.get(law.get("negation") or "")
                if neg is not None and neg.get("negation_of") == lid and lid + "_neg" in neg_recs:
                    rec["negation"] = neg_recs[lid + "_neg"]   # the frozen negation, run as an ordinary law (F-M2-19)
                else:   # no frozen negation in this milestone: generated and decided here, labelled not frozen
                    rec["negation"] = decide_negation(law, cm, imp0, d / "neg", cfg)
                attempts.append({"kind": "negation", "law_id": rec["negation"]["law_id"], "status": rec["negation"]["status"]})
            if status != "PROVED" and sid is not None:   # I15: one witness per entry point (S1-S3), each Bend-checked
                status, r, em2, wits, bound = refute_site(law, em, cm, imp, d, ld, pd, cfg, attempts, shash, verdict,
                                                          site_entries(der, lid), report)
                rec["witnesses"] = wits
                if status == "REFUTED":
                    em = em2
                    first = next(e for e in sorted(wits) if wits[e]["status"] == "REFUTED")
                    w = wits[first]["witness"]
                    rec["witness"] = w
                    rec["difference"] = witness_difference(cm, law, w)
                    t = triage.get(lid, {})
                    rec["triage"] = t.get("triage", "finding")
                    if t.get("why"):
                        rec["triage_why"] = t["why"]
                    rec["replay"] = replay_status(report, lid, w)
            elif status != "PROVED" and not exists:
                s = cm.explore(law)
                bound = s["bound"]
                attempts.append({"kind": "refute", "engine": "compiled-model trace search", "bound": s["bound"],
                                 "tried": s["tried"], "hit": s["witness"] is not None})
                if s["witness"] is not None:
                    w = s["witness"]
                    conj = failing_conjunct(cm, law, w)
                    em2 = mlaws.Emitter(cm.m).emit(law, imp, counter=True, note=shash, conjunct=conj)
                    # oracle parameters (I12): the tables the witness denotes, at the points the statement queries
                    wr = mlaws.resolve_witness(cm.m, em2.binders, w, {p_: [k for k, _ in es]
                                                                     for p_, es in (s.get("tables") or {}).items()})
                    tabs = mlaws.witness_tabs(cm.m, em2.binders, wr)
                    env = {n: mlaws.value_literal(cm.m, t, wr[n], tabs) for _, n, t in em2.binders}
                    E2 = mlaws.Emitter(cm.m)
                    lhs, _, ty = E2.claims(law["statement"], env, {n: ("State" if t == "Reach" else t)
                                                                   for _, n, t in em2.binders})[conj or 0]
                    text = mproofs.counter(em2, cm.m, imp, wr, lhs, ty)
                    for x in {d, ld, pd}:
                        shutil.rmtree(x, ignore_errors=True)
                    proof_f = write_pair(ld, pd, em2.text, text)
                    rr = bend.check(proof_f, cfg)
                    ok, why = accepted(rr, proof_f, ld / "LAWS.bend", em2, text)
                    attempts.append({"kind": "counter-law", "generator": "counter", "exit_code": rr.code, "marker": rr.marker,
                                     "seconds": rr.seconds, **({} if ok else {"error": why})})
                    if ok:
                        status, r, em = "REFUTED", rr, em2
                        rec["witness"] = w
                        if conj is not None:
                            rec["failing_conjunct"] = conj
                        rec["difference"] = witness_difference(cm, law, w, conj)
                        t = triage.get(lid, {})
                        rec["triage"] = t.get("triage", "finding")
                        if t.get("why"):
                            rec["triage_why"] = t["why"]
                        rec["replay"] = replay_status(report, lid, w)
        except mlaws.Unsupported as e:
            attempts.append({"kind": "emit", "error": f"unsupported statement form: {e}"})
        except ir.IRError as e:
            attempts.append({"kind": "ir", "error": f"rejected by the IR rules (G3): {e}"})
            bound = "not searched: the IR rejects the statement"
        except O.OracleError as e:
            attempts.append({"kind": "ir", "error": f"rejected by the oracle sidecar rules: {e}"})
            bound = "not searched: the statement's oracle premises do not resolve against the sidecar"
        if sid is not None:
            rec["site"] = sid
            rec.setdefault("witnesses", {})
            if status == "UNKNOWN" and not rec["witnesses"]:   # never searched (emission or IR failure)
                rec["witnesses"] = {e: site_entry_record(None, bound or "not searched", None)
                                    for e in site_entries(der, lid)}
        if status == "UNKNOWN":
            if "negation" in rec:   # keep the decided negation's files, drop everything else
                for x in (ld / "LAWS.bend", pd / "PROOF.bend"):
                    x.unlink(missing_ok=True)
            else:
                shutil.rmtree(d, ignore_errors=True)
            for x in {ld, pd} - {d}:   # the separated dirs (I10) hold nothing else
                shutil.rmtree(x, ignore_errors=True)
            rec["scope"] = "bounded"
            rec["bound"] = bound or "not searched"
        else:
            rec["scope"] = "unbounded"
            rec["artifacts"].update({"laws": relpath(ld / "LAWS.bend"), "proof": relpath(pd / "PROOF.bend"), "law_name": em.name})
            rec["checker"] = {"exit_code": r.code, "marker": r.marker, "seconds": r.seconds}
            if verdict:
                v = bend.check_verdict(pd / "PROOF.bend", cfg)
                rec["kernel"]["verdict"] = "checked" if v.ok else "failed"
                attempts.append({"kind": "verdict", "kernel": "BendTT (Lean-proven)", "exit_code": v.code,
                                 "marker": v.marker, "seconds": v.seconds})
        if law.get("ir_version") == "holon-ir/0.3":   # the statement's scope, separate from its status (F-M2-01)
            rec.update(scope_fields(law, rec))
        rec["status"] = status
        rec["attempts"] = attempts
        kbound["laws"][lid] = {"model": model_src.stem, "cone": law_cone(law, cm.facts, stmt_text, model_src, cfg)}
        rec.update(records.v2_fields(law, rec, stmt_text, model_src, law["facts"], cm.artifact, ROOT,
                                     ledger_required=not test_milestone(milestone)))
        if law.get("ir_version") == "holon-ir/0.3":
            rec["scope_v2"] = {**rec["scope_v2"], **scope_fields(law, rec)["scope_v2"]}
        if law.get("negation_of"):
            neg_recs[lid] = {"law_id": lid, "statement_hash": shash, "status": status, "frozen": True,
                             "statement": rec["statement"], "laws": rec["artifacts"]["laws"],
                             "proof": rec["artifacts"]["proof"], "generator": None, "attempts": []}
        if m2plus(milestone):   # §8.5: exactly the hypothesis premises, nothing else (I12)
            # ... and the ledger cone stays, in its own field (F-M2-12): every ledger entry meeting the cone that is
            # not a stand-in the model replaced by a parameter (abstractions, not_in_scope stand-ins)
            rec["ledger_assumptions"] = O.ledger_assumptions(rec["model_assumptions"], cm.oracles, cm.m)
            rec["model_assumptions"] = O.hypothesis_premises(law, cm.oracles)
        rec["non_vacuity"] = inhabit.inhabit(law, milestone, ROOT, d, cfg, cm=cm, rec=rec,
                                             entries=site_entries(der, lid) if sid is not None else None)
        (out_dir / f"{lid}.json").write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        summary[lid] = status
        log(f"{lid:22s} {status:8s} {rec['kernel']['verdict']:8s} {rec['triage']}")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (out_dir / "deps.json").write_text(bindings.dump(bindings.dependents(kbound)))
    if m2plus(milestone):   # hypothesis splits are law pairs (I12)
        (out_dir / "splits.json").write_text(json.dumps(O.splits(laws, summary, oracles_of, milestone),
                                                        indent=2, sort_keys=True) + "\n")
    return summary


# ---------------------------------------------------------------- I15: refutation per entry point
S3_MAX = 20000   # spec/M2/predictions.json I15 thresholds: neighbourhood_prefixes_per_entry_point_max


def site_entries(der: dict | None, lid: str) -> list[str]:
    """A SORT-site law's entry points, sorted (laws/<M>/DERIVATION.json)."""
    for e in (der or {}).get("laws", []):
        if e.get("law_id") == lid:
            return sorted(e.get("entry_points") or [])
    raise ValueError(f"{lid}: no entry in DERIVATION.json (run `holon derive`)")


def entry_replay(report: dict | None, lid: str, e: str, w: dict | None) -> dict:
    """A per-entry witness's replay, from the committed replay report (replay/<m>/report.json, holon.mreplay), only
    if the report replayed this witness."""
    from .replay import witness_sha256
    if w is None:
        return {"status": "not_run", "detail": "no witness", "panic_site": None}
    ent = (((report or {}).get("laws") or {}).get(lid) or {}).get("entries", {}).get(e)
    if not isinstance(ent, dict):
        return {"status": "not_run", "detail": "no replay report entry", "panic_site": None}
    if ((report.get("entry_witness_sha256") or {}).get(lid) or {}).get(e) != witness_sha256(w):
        return {"status": "not_run", "detail": "replay report is for a different witness", "panic_site": None}
    return {"status": ent.get("status", "not_run"),
            "detail": (f"real outcomes {ent.get('real')}; obstruction observed: {ent.get('obstruction_observed')} "
                       f"@ target commit {str(report.get('morph_commit', ''))[:12]}")[:500],
            "panic_site": ent.get("panic_site")}


def site_entry_record(w: dict | None, bound: str, check, laws: Path | None = None, proof: Path | None = None,
                      verdict: str = "not_run", stage: str | None = None, replay: dict | None = None) -> dict:
    """One entry point's part of a SORT-site record ("witnesses"; tests_m2/test_sort_site_outcomes.py)."""
    ok = check is not None and w is not None
    return {"status": "REFUTED" if ok else "UNKNOWN", "witness": w if ok else None,
            "laws": relpath(laws) if ok and laws else None, "proof": relpath(proof) if ok and proof else None,
            "checker": {"exit_code": check.code, "marker": check.marker} if ok else None,
            "verdict": verdict if ok else "not_run", "stage": stage if ok else None, "bound": bound,
            "replay": replay or {"status": "not_run", "detail": "no witness", "panic_site": None}}


def counter_text(law: dict, em2, cm: CompiledMachine, imp: str, w: dict, tables: dict | None) -> str:
    """The counter-law proof of a witness (holon.gen.mproofs.counter), its oracle tables materialised at the points
    the search's evaluation queried (I12: the sidecar instance applied there)."""
    wr = mlaws.resolve_witness(cm.m, em2.binders, w, {p_: [k for k, _ in es] for p_, es in (tables or {}).items()})
    tabs = mlaws.witness_tabs(cm.m, em2.binders, wr)
    env = {n: mlaws.value_literal(cm.m, t, wr[n], tabs) for _, n, t in em2.binders}
    lhs, _, ty = mlaws.Emitter(cm.m).claims(law["statement"], env, {n: ("State" if t == "Reach" else t)
                                                                   for _, n, t in em2.binders})[0]
    return mproofs.counter(em2, cm.m, imp, wr, lhs, ty)


def refute_site(law: dict, em, cm: CompiledMachine, imp: str, d: Path, ld: Path, pd: Path, cfg: dict, attempts: list,
                shash: str, verdict: bool, entries: list[str], report: dict | None):
    """Refutation of a SORT-site law, once per entry point (sorted): S1+S2 for every entry point, then S3 for those
    left without a checked witness, seeded by the checked ones (holon/js/explore.mjs). Each witness is a counter-law
    checked by Bend (and BendTT when enabled) in proofs/<id>/entry_<e>/PROOF.bend, importing the law's LAWS.bend; the
    primary witness (proofs/<id>/PROOF.bend) is the first entry point, sorted, with a checked counter-law.
    Returns (status, primary check, emitted counter-law, witnesses by entry point, bound)."""
    lid = law["law_id"]
    em2 = mlaws.Emitter(cm.m).emit(law, imp, counter=True, note=shash)
    for x in {d, ld, pd}:
        shutil.rmtree(x, ignore_errors=True)
    ld.mkdir(parents=True, exist_ok=True)
    (ld / "LAWS.bend").write_text(em2.text)
    got: dict = {}
    bounds: dict = {}
    eimp = "../" + imp   # proofs/<id>/entry_<e>/ lies one level below proofs/<id>/

    def try_entry(e: str, found: dict, stage: str) -> None:
        w, tables = found["witness"], found.get("tables")
        de = pd / f"entry_{e}"
        try:
            text = counter_text(law, em2, cm, eimp, w, tables)
        except (mlaws.Unsupported, ValueError, KeyError) as err:
            attempts.append({"kind": "counter-law", "generator": "counter", "entry": e, "stage": stage,
                             "error": f"inexpressible: {err}"})
            return
        de.mkdir(parents=True, exist_ok=True)
        pf = de / "PROOF.bend"
        pf.write_text(separated_proof(text, ld, de))
        rr = bend.check(pf, cfg)
        ok, why = accepted(rr, pf, ld / "LAWS.bend", em2, text)
        attempts.append({"kind": "counter-law", "generator": "counter", "entry": e, "stage": stage,
                         "exit_code": rr.code, "marker": rr.marker, "seconds": rr.seconds, **({} if ok else {"error": why})})
        v = "not_run"
        if ok and verdict:
            vv = bend.check_verdict(pf, cfg)
            v = "checked" if vv.ok else "failed"
            attempts.append({"kind": "verdict", "entry": e, "kernel": "BendTT (Lean-proven)", "exit_code": vv.code,
                             "marker": vv.marker, "seconds": vv.seconds})
        if ok and v != "failed":
            got[e] = {"witness": w, "tables": tables, "check": rr, "proof": pf, "verdict": v, "stage": stage}
        else:
            shutil.rmtree(de, ignore_errors=True)

    s2 = cm.site_search(law, "refute", entries, "S2")
    for e in entries:
        f = s2["site"][e]
        bounds[e] = f["bound"]
        if f["witness"] is not None:
            try_entry(e, f, "S2")
    attempts.append({"kind": "refute", "engine": "SORT-site search (S1 boundary variants, S2 prefixes)",
                     "tried": s2["tried"], "hit": {e: s2["site"][e]["witness"] is not None for e in entries},
                     "notes": s2.get("notes", [])})
    missing = [e for e in entries if e not in got]
    if missing and got:
        seeds = {e: got[e]["witness"][next(b["name"] for b in law["statement"]["binders"] if b["type"] == "Reach")]["run"]
                 for e in sorted(got)}
        s3 = cm.site_search(law, "refute", missing, "S3", seeds=seeds, s3max=S3_MAX)
        for e in missing:
            f = s3["site"][e]
            bounds[e] = f["bound"]
            if f["witness"] is not None:
                try_entry(e, f, "S3")
        attempts.append({"kind": "refute", "engine": "SORT-site search (S3 neighbourhood of the checked witnesses)",
                         "tried": s3["tried"], "hit": {e: s3["site"][e]["witness"] is not None for e in missing},
                         "notes": s3.get("notes", [])})
    wits = {}
    for e in entries:
        g = got.get(e)
        wits[e] = site_entry_record(g["witness"] if g else None, bounds.get(e, "not searched"), g["check"] if g else None,
                                    ld / "LAWS.bend", g["proof"] if g else None, g["verdict"] if g else "not_run",
                                    g["stage"] if g else None, entry_replay(report, lid, e, g["witness"] if g else None))
    bound = "; ".join(f"{e}: {bounds.get(e, 'not searched')}" for e in entries)
    if not got:
        return "UNKNOWN", None, None, wits, bound
    first = sorted(got)[0]
    text = counter_text(law, em2, cm, imp, got[first]["witness"], got[first]["tables"])
    pf = write_pair(ld, pd, em2.text, text)
    rr = bend.check(pf, cfg)
    ok, why = accepted(rr, pf, ld / "LAWS.bend", em2, text)
    attempts.append({"kind": "counter-law", "generator": "counter", "entry": first, "primary": True,
                     "exit_code": rr.code, "marker": rr.marker, "seconds": rr.seconds, **({} if ok else {"error": why})})
    if not ok:   # the entry's own file checked; the primary copy must too, else nothing is claimed
        return "UNKNOWN", None, None, {e: site_entry_record(None, bounds.get(e, "not searched"), None) for e in entries}, \
            bound + f"; the primary counter-law copy was rejected: {why}"
    return "REFUTED", rr, em2, wits, bound


def param_search(em, cm: CompiledMachine, imp: str, ld: Path, pd: Path, cfg: dict, attempts: list):
    """mproofs.param_premise (I12): its candidates in order, Bend picks. Returns the accepted check, or None."""
    texts = mproofs.param_premise(em, cm.m, imp)
    for i, text in enumerate(texts or []):
        proof_f = write_pair(ld, pd, em.text, text)
        rr = bend.check(proof_f, cfg)
        ok, why = accepted(rr, proof_f, ld / "LAWS.bend", em, text)
        attempts.append({"kind": "proof", "generator": "param_premise", "candidate": i, "exit_code": rr.code,
                         "marker": rr.marker, "seconds": rr.seconds, **({} if ok else {"error": why})})
        if ok:
            return rr
    return None


def reach_search(em, cm: CompiledMachine, imp: str, ld: Path, pd: Path, cfg: dict, attempts: list, max_tries: int = 120):
    """mproofs.ReachProof: first without strengthening, then with houdini's proposals; in each, Bend picks
    the case terms (the slot on the line it rejects advances). Returns the accepted check, or None."""
    import re
    houdini = None
    for mode in ("plain", "strengthened"):
        strength = []
        if mode == "strengthened":
            houdini = houdini or cm.houdini()
            strength = [(c["field"], c["type"], c["value"]) for c in houdini["candidates"]]
            if not strength:
                break
        try:
            rp = mproofs.ReachProof(em, cm.m, imp, strength)
        except mlaws.Unsupported as e:
            attempts.append({"kind": "proof", "generator": "reach_invariant", "error": f"unsupported: {e}"})
            return None
        choice: dict = {}
        tries, rr, ok, why = 0, None, False, "not checked"
        for tries in range(1, max_tries + 1):
            text, slot_at = rp.render(choice)   # separated_proof keeps the line count, so slot lines hold
            proof_f = write_pair(ld, pd, em.text, text)
            rr = bend.check(proof_f, cfg)
            ok, why = accepted(rr, proof_f, ld / "LAWS.bend", em, text)
            if ok or rr.ok:
                break
            mm = re.search(r"^\s*(\d+)>\|", rr.out, re.M)
            slot = slot_at.get(int(mm.group(1))) if mm else None
            if slot is None:
                break
            choice[slot] = choice.get(slot, 0) + 1
            if choice[slot] >= len(rp.candidates(slot[2])):
                break
        att = {"kind": "proof", "generator": "reach_invariant", "mode": mode, "tries": tries,
               "strengthening": [f"{f} == {json.dumps(v)}" for f, _, v in strength],
               "exit_code": rr.code if rr else None, "marker": rr.marker if rr else None, "seconds": rr.seconds if rr else None}
        if houdini and mode == "strengthened":
            att["houdini"] = {"states": houdini["states"], "bound": houdini["bound"]}
        if not ok:
            att["error"] = why
        attempts.append(att)
        if ok:
            return rr
    return None


def law_cone(law: dict, facts: dict, stmt_text: str, model_src: Path, cfg: dict) -> list[str]:
    """The kernel cone of a statement. A holon-ir/0.3 statement that names no model definition at all
    (only Fn binders and IR builtins, e.g. a collision-freedom law) has an empty cone; any other
    statement with an empty cone is an emitter bug (bindings.BindingError)."""
    from .gen.mlaws import BUILTINS
    if law.get("ir_version") == "holon-ir/0.3" and set(R.refs(law, facts)) <= set(BUILTINS):
        return []
    return bindings.kernel_cone(stmt_text, bindings.kernel_entries(model_src, cfg))


def failing_conjunct(cm: CompiledMachine, law: dict, w: dict) -> int | None:
    """The first conjunct of a conjunction that is false at the witness, on the compiled model."""
    if "all" not in law["statement"]["claim"]:
        return None
    ev = cm.evaluate(law, w)
    return next((i for i, ok in enumerate(ev["claims"]) if not ok), None)


def decide_negation(law: dict, cm: CompiledMachine, imp: str, d: Path, cfg: dict) -> dict:
    """Generate the negation of an existential law (for all binders, not claim) and try the proof
    generators on it. imp is relative to the law's directory, so the negation's import goes up one."""
    out = {"law_id": law["law_id"] + "_neg", "statement_hash": None, "status": "UNKNOWN", "laws": None, "proof": None,
           "generator": None, "statement": None, "frozen": False, "attempts": []}
    try:
        neg = ir.negation_law(law)   # the generator I15's derive freezes the pair with (audit F-M2-19)
        out["statement_hash"] = R.law_hash(neg, cm.facts, oracles=cm.oracles)
        out["statement"] = ir.render_statement(neg)
        nimp = "../" + imp
        em = mlaws.Emitter(cm.m).emit(neg, nimp, note=f"negation of {law['law_id']} ({out['statement_hash']})")
    except (mlaws.Unsupported, ir.IRError) as e:
        out["attempts"].append({"kind": "emit", "error": f"unsupported: {e}"})
        return out
    for gname, g in mproofs.GENERATORS:
        if gname == "evaluate":
            continue
        text = g(em, cm.m, nimp)
        if text is None:
            continue
        d.mkdir(parents=True, exist_ok=True)
        (d / "LAWS.bend").write_text(em.text)
        (d / "PROOF.bend").write_text(text)
        rr = bend.check(d / "PROOF.bend", cfg)
        ok, why = accepted(rr, d / "PROOF.bend", d / "LAWS.bend", em, text)
        out["attempts"].append({"kind": "proof", "generator": gname, "exit_code": rr.code, "marker": rr.marker,
                                **({} if ok else {"error": why})})
        if ok:
            if bend.verdict_enabled(cfg):
                v = bend.check_verdict(d / "PROOF.bend", cfg)
                out["attempts"].append({"kind": "verdict", "exit_code": v.code, "marker": v.marker})
                if not v.ok:
                    continue
            out.update({"status": "PROVED", "generator": gname, "laws": relpath(d / "LAWS.bend"),
                        "proof": relpath(d / "PROOF.bend")})
            return out
    shutil.rmtree(d, ignore_errors=True)
    return out


def check_registry_multi(laws: list[dict], reg: dict, milestone: str | None = None, root: Path | None = None) -> None:
    """The registry check of `holon run` and of gate G2, for every IR version: each facts file's sha256, the law
    ids, each law's facts_sha256, and each statement hash (holon.gen.refs.law_hash: 0.3 with its refs into the
    facts and the target library and, for M2+ milestones, the oracle sidecar). root: the tree checked."""
    from .pipeline import RegistryMismatch
    root = Path(root or ROOT)
    problems = []
    files = reg.get("facts_files") or {reg["facts"]: reg["facts_sha256"]}
    for path, sha in files.items():
        if not (root / path).is_file():
            problems.append(f"facts {path} does not exist")
        elif F.sha256_file(root / path) != sha:
            problems.append(f"facts {path} hash differs from the registry")
    if sorted(reg["statements"]) != sorted(l["law_id"] for l in laws):
        problems.append("registry and laws/ list different law ids")
    for law in laws:
        rel = law.get("facts") or reg.get("facts")
        if files.get(rel) != law["facts_sha256"]:
            problems.append(f"{law['law_id']}: facts_sha256 differs from its facts file")
        if not (root / rel).is_file():
            continue
        orc = O.Oracles.for_milestone(milestone, root / rel, root) if milestone else None
        if reg["statements"].get(law["law_id"]) != R.law_hash(law, F.load(root / rel), oracles=orc, root=root):
            problems.append(f"{law['law_id']}: statement hash differs from the registry")
    if problems:
        raise RegistryMismatch("; ".join(problems))


def law_import_problem(proof: Path, laws: Path) -> str | None:
    """Every acceptance point (audit F-M2-07): a PROOF.bend counts only when it imports exactly its LAWS.bend, by
    the relative path from the proof's directory, as Laws. Bend then requires every law of that module to be filled
    (an unfilled one is a TODO, probe bend/notes/p_ir03_import_depth); a proof that imports no law checks
    vacuously, since prover separation (I10) took away Bend's own "PROOF.bend must import ./LAWS.bend" rule for
    files apart. None when the import is there, else the reason."""
    import re
    proof, laws = Path(proof), Path(laws)
    want = Path(os.path.relpath(laws.resolve(), proof.resolve().parent)).as_posix()
    ok = {want, "./" + want} if "/" not in want else {want}
    try:
        text = proof.read_text(errors="replace")
    except OSError as e:
        return f"cannot read {proof.name}: {e}"
    found = []
    for line in text.splitlines():
        m = re.match(r"^import\s+(\S+)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$", line)
        if m and m.group(2) == "Laws":
            found.append(m.group(1))
    if found == [p for p in found if p in ok] and found:
        return None
    return (f"{proof.name} does not import its law ({want} as Laws; it imports {found or 'no law module'}): a proof "
            "that never imports the law it claims proves nothing")


def _law_names(text: str) -> list[str]:
    from .pipeline import law_names
    return law_names(text)
