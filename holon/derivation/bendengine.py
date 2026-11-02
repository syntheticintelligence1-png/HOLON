"""I89 stage 2: the Bend engine, I88's decider's consumer model (the contract is the docstring of
tests_m3/test_derivation_bend.py, rules S1-S6):

  python -m holon derivation bend-decide [--check]
  python -m holon derivation decide --model holon.derivation.bendengine        (I88's decider, consumer_model(root))

bend-decide runs I88's decider offline (holon.derivation.decide.run with check=True: I88's candidates, evaluations,
environment and replay are read, never re-made) with this engine as its consumer model, and writes what the decider
re-makes in place (its records under results/M3/derivation/laws/ and splits.json) and the engine's own outputs: the
product module and the equivalence pair (holon.derivation.bendlaws, holon.derivation.bendequiv), each law's LAWS.bend and
PROOF.bend, results/M3/derivation/bend/decisions.json and replay/M3/derivation/bend/witnesses.json.

For each law (engine.decide(law, evidence)):
  hyp_apply   a law whose claim is the conclusion of one of its hypothesis premises at its own binders (the premises
              of that hypothesis the law's): LAWS.bend states it (law_id.lower()), PROOF.bend applies the premise
              (holon.derivation.bendproof.hyp_apply_proof). PROVED iff Bend and BendTT both accept it.
  counter     otherwise a bounded search on the compiled models: I88's candidates in its order, its evaluator witness
              first, at most SEARCH_BOUND, each a commit on the typed model (from the deployment state) and the consumer
              model's runs (node); the first whose premises hold there and whose claim fails is the witness. LAWS.bend
              states the counter-law ("cl_" + law_id.lower(), the exs form), PROOF.bend proves it at the witness
              (holon.derivation.bendproof.Gen). REFUTED iff Bend and BendTT both accept it and the witness's consumer
              side (I88's batches of the witness's candidate: the real blobs) replays on the real consumer
              (TestHolonReplay, offline) with the model's observation.
  anything else is UNKNOWN with what was tried.

The hypotheses (HypB, HypT, HypC_*) are premises of the laws that state them and are recorded as model assumptions; so
are the refinement of the consumer model (169 cases) and HypB's instance on I85's canonical cases, which are evidence
for the model, not proof. Nothing here names a target.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import DerivationError, Refused, load
from . import bendlaws as BL
from . import bendproof as BP

DECISIONS_VERSION = "holon-derivation-bend-decisions/0.1"
WITNESSES_VERSION = "holon-derivation-bend-witnesses/0.1"
SEARCH_BOUND = 8
BEND_SIDECAR = "spec/M3/lib/derivation_bend.json"
BENDTT_NOTE = ("BendTT (--verdict) re-checks bend2's elaboration of the same file: it shares the front end, so "
               "agreement is not independent evidence (class I1-shared, not I2)")
KERNEL_TIMEOUT = 5400


def dumps(o) -> str:
    return json.dumps(o, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def rel(root: Path, p: Path) -> str:
    return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()


def kernel(path: Path, verdict: bool, tries: int = 3) -> dict:
    """The pinned checker on a file in its own directory (holon.bend; BendTT with --verdict): {"exit_code", "marker"}
    (its first line). bend2's stack overflow (holon.bend.crashed) is no verdict either way: it is retried."""
    from .. import bend
    r = None
    for _ in range(tries):
        r = bend.check_verdict(path, timeout=KERNEL_TIMEOUT) if verdict else bend.check(path, timeout=KERNEL_TIMEOUT)
        if not bend.crashed(r):
            break
    if bend.timed_out(r):
        return {"exit_code": None, "marker": f"timeout after {KERNEL_TIMEOUT} s"}
    return {"exit_code": r.code, "marker": r.first_line}


def accepted(k: dict) -> bool:
    return k.get("exit_code") == 0 and k.get("marker") == "ALL PROOFS CHECK"


def nat_value(lit: str):
    """A node-printed Nat, Bool or list literal as a JSON value."""
    s = lit.strip()
    if s in ("Nil{}", "[]"):
        return []
    if s.startswith("["):
        return [nat_value(x) for x in BL.split_top(s[1:-1])]
    if s in ("True{}", "False{}"):
        return s == "True{}"
    if s.endswith("n") and s[:-1].isdigit():
        return int(s[:-1])
    raise DerivationError(f"not a value literal: {s[:80]}")


class Engine:
    """consumer_model(root): decide(law, evidence) for I88's decider; outputs() for bend-decide."""

    def __init__(self, root: Path, side_rel: str = BEND_SIDECAR, check: bool = False, replay: dict | None = None):
        from .bendgen import bend_sidecar
        from . import bendequiv as BE
        self.root = Path(root)
        self.side_rel, self.check = side_rel, check
        self.side = bend_sidecar(self.root, side_rel)
        self.I = BL.Inputs(self.root, self.side)
        self.model_path = self.root / self.side["outputs"]["model"]
        self.law_dir = self.root / self.side["outputs"]["laws"]
        self.pp = self.model_path.parent / "product.bend"
        self.ctext = self.model_path.read_text(encoding="utf-8")
        self.files: dict = {}
        self.differs: list = []
        self.put(self.pp, BL.Product(self.I).text())
        for p, t in BE.texts(self.I, self.pp).items():
            self.put(p, t)
        self.equiv = {"laws_file": rel(self.root, self.pp.parent / BE.DIR / "LAWS.bend"),
                      "proof_file": rel(self.root, self.pp.parent / BE.DIR / "PROOF.bend")}
        pf = self.root / self.equiv["proof_file"]
        self.equiv["kernels"] = {"bend": kernel(pf, False), "bendtt": kernel(pf, True)}
        s88 = self.I.s88
        self.reg = load(self.root / s88["law_set"]["laws"] / "REGISTRY.json")
        self.cands = load(self.root / s88["outputs"]["candidates"])["candidates"]
        self.recorded_replay = replay      # --check: the recorded witnesses' replay (no Go)
        self.decisions: dict = {}
        self.replays: dict = {}
        self._commit = None
        self._i88 = None
        ip, _t, _k, _s = self.I.typed()
        self.typed_path = Path(ip)

    # ---------------------------------------------------------------- files
    def put(self, path: Path, text: str):
        """A generated file: written (or, with --check, compared; a kernel then reads the committed copy)."""
        r = rel(self.root, path)
        self.files[r] = text
        p = self.root / r
        if self.check:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                self.differs.append(r)
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def imports(self, d: Path) -> list:
        return [("C", BL.rel_import(d, self.model_path)), ("M", BL.rel_import(d, self.typed_path)),
                ("P", BL.rel_import(d, self.pp)), ("H", BL.rel_import(d, self.I.header()))]

    def commit(self):
        if self._commit is None:
            self._commit = BP.Commit(self.root, self.I)
        return self._commit

    def close(self):
        if self._commit is not None:
            self._commit.close()
            self._commit = None

    # ---------------------------------------------------------------- the decider's interface
    def decide(self, law: dict, evidence: dict) -> dict:
        lid = law["law_id"]
        d = self.law_dir / lid
        imports = self.imports(d)
        sh = self.reg["statements"][lid]
        R = BL.Render(self.I)
        tried = []
        try:
            proof = BP.hyp_apply_proof(self.I, law, imports)
        except BL.Unsupported as e:
            proof = None
            tried.append(f"class hyp_apply: {e}")
        if proof is not None:
            self.put(d / "LAWS.bend", R.law_text(law, sh, imports, False))
            self.put(d / "PROOF.bend", proof)
            return self.finish(law, "hyp_apply", False, tried, None)
        return self.counter(law, evidence, R, sh, imports, tried)

    def kernels(self, d: Path) -> dict:
        pf = d / "PROOF.bend"
        if self.check and rel(self.root, pf) in self.differs:
            return {"bend": {"exit_code": None, "marker": "not run: the file differs"},
                    "bendtt": {"exit_code": None, "marker": "not run: the file differs"}}
        return {"bend": kernel(pf, False), "bendtt": kernel(pf, True)}

    # ---------------------------------------------------------------- counter-laws
    def order(self, evidence: dict) -> list:
        w = (evidence.get("witness") or {}).get("id")
        ids = [c["id"] for c in self.cands]
        first = [w] if w in ids else []
        return (first + [i for i in ids if i != w])[:SEARCH_BOUND]

    def counter(self, law: dict, evidence: dict, R, sh: str, imports: list, tried: list) -> dict:
        lid = law["law_id"]
        d = self.law_dir / lid
        found = None
        for cid in self.order(evidence):
            cand = next(c for c in self.cands if c["id"] == cid)
            try:
                got = self.evaluate(law, cand, imports)
            except BL.Unsupported as e:
                tried.append(f"candidate {cid}: unsupported: {e}")
                continue
            if not got["premises_hold"]:
                tried.append(f"candidate {cid}: a premise fails on the compiled models ({got['failed']})")
                continue
            if got["claim_holds"]:
                tried.append(f"candidate {cid}: the premises hold and so does the claim ({got['observation']})")
                continue
            found = (cand, got)
            tried.append(f"candidate {cid}: the premises hold and the claim fails on the compiled models: "
                         f"{got['observation']}")
            break
        if found is None:
            tried.append(f"search bound: {SEARCH_BOUND} candidates of I88's search space, its evaluator witness first")
            self.put(d / "LAWS.bend", R.law_text(law, sh, imports, True))
            return self.finish(law, "counter", True, tried, None, no_proof=True)
        cand, got = found
        self.put(d / "LAWS.bend", R.law_text(law, sh, imports, True))
        self.put(d / "PROOF.bend", got["gen"].proof_text(got["js"]))
        return self.finish(law, "counter", True, tried, (cand, got))

    def evaluate(self, law: dict, cand: dict, imports: list) -> dict:
        """A candidate on the compiled models: the commit on the typed model (from the deployment state), the consumer
        model's runs and the law's terms, by node."""
        from .product import Product as P85, stand_in_blobhash
        from .corpus import blob
        from .. import extracted_eval as EV
        I = self.I
        s85 = I.s85
        k = cand["step"]["k"]
        if k != 1:
            raise BL.Unsupported(f"the step is commit {k} of its trace (only the deployment state's step is rendered)")
        blobs = [blob(x, j, []) for j, x in enumerate(cand["batches"][0]["data"])]
        if len(blobs) != 1:
            raise BL.Unsupported(f"{len(blobs)} blobs (the witness's blob construction holds one)")
        if any(b["data"] != cand["batches"][0]["data"] or b["payload"] != cand["batches"][0]["payload"]
               for b in cand["batches"]):
            raise BL.Unsupported("the candidate's batches differ in their blobs")
        p85 = P85(self.root, s85)
        plan = next(p for p in s85["corpus"]["product"] if p["id"] == cand["step"]["trace"])
        args = {s85["product"]["commit_param"]: cand["members"]}
        params = p85.model.params(p85.action)
        calldata = EV.abi_encode([EV.norm(args[p["name"]], p) for p in params], params)
        env85 = p85.env(plan["commits"][k - 1], blobs, k, 4 + len(calldata))
        env = {kk: v for kk, v in env85.items()
               if kk in ("caller", "msg.value", "block.timestamp", "block.number", "blobhash")}
        c = self.commit().step(args, env)
        payload = bytes.fromhex(cand["batches"][0]["payload"][2:])
        ctx_vars = []
        for t in BL._terms(law["statement"]):
            v = (t.get("contexts") or {}).get("var") if isinstance(t, dict) else None
            if v is not None and v not in ctx_vars:
                ctx_vars.append(v)
        if len(ctx_vars) > len(cand["batches"]):
            raise BL.Unsupported("more contexts binders than the candidate's batches")
        ctxs = {}
        for i, v in enumerate(ctx_vars):
            cx = cand["batches"][i]["contexts"]
            if cx is None:
                raise BL.Unsupported(f"the candidate's batch {i} has no contexts for {v}")
            ctxs[v] = bytes.fromhex(cx[2:])
        W = BP.Witness(c["act"], c["kh"], payload, ctxs, stand_in_blobhash(blobs[0]), b"")
        mirror = rel(self.root, self.model_path.parent)
        deps = {rel(self.root, self.model_path): self.model_path, rel(self.root, self.pp): self.pp,
                rel(self.root, self.typed_path): self.typed_path, rel(self.root, self.I.header()): self.I.header()}
        wimp = [("C", "./" + self.model_path.name), ("M", BL.rel_import(self.model_path.parent, self.typed_path)),
                ("P", "./" + self.pp.name), ("H", BL.rel_import(self.model_path.parent, self.I.header()))]
        ptext = self.files[rel(self.root, self.pp)]
        aliases = {self.model_path.stem: "C", self.pp.stem: "P"}
        # 1. the decoder's argument (txs_data), which fixes the codec's table B
        G = BP.Gen(I, ptext, self.ctext, law, W, imports)
        G.pieces(None)
        ctx_terms = sorted({ctx for (_d, ctx) in G.runs})
        vals1 = {f"val_txs_{i}": (f"P.txs_data(w_x(), w_p(), cb_w, pl_w, {ctx}, P.fuel0())", "List<&2, Nat>")
                 for i, ctx in enumerate(ctx_terms)}
        m1 = G.module_text(wimp, False, vals1, {})
        js1 = BP.node_trace(BP.compile_module(f"{mirror}/W1.bend", m1, deps),
                            {"runs": {}, "values": sorted(vals1), "aliases": aliases})
        txs = {js1["values"][v] for v in vals1}
        if len(txs) != 1:
            raise BL.Unsupported("the runs' decoder arguments differ")
        bt = txs.pop()
        B = bytes(nat_value(bt)) if bt not in ("Nil{}", "[]") else b""
        W.B, W.ts = B, ([0] if B else [])
        # 2. the runs and the law's terms at the witness
        G = BP.Gen(I, ptext, self.ctext, law, W, imports)
        G.pieces(None)
        pl = G.plan()
        vals = dict(pl["values"])
        for (_d, _c), r in G.runs.items():
            vals[f"cells_{r}"] = (f"cells_{r}()", None)
            vals[f"batch_{r}"] = (f"batch_{r}()", None)
        m2 = G.module_text(wimp, True, {kk: v for kk, v in vals.items() if v[1] is not None}, G.runs)
        req = {"runs": {r: {"init": f"init_{r}", "step": "stepf"} for (_d, _c), r in G.runs.items()},
               "spent": {"pl": f"{self.model_path.stem}.pl_spent", "dt": f"{self.model_path.stem}.dt_spent"},
               "values": sorted(vals), "aliases": aliases}
        js = BP.node_trace(BP.compile_module(f"{mirror}/W2.bend", m2, deps), req)
        failed = []
        if c["status"] != "ok":
            failed.append(f"the commit's status is {c['status']}")
        for name, kind, data in pl["premises"]:
            if kind == "eq" and js["values"][f"val_{name}_l"] != js["values"][f"val_{name}_r"]:
                failed.append(name)
        lhs, rhs = js["values"]["val_claim_l"], js["values"]["val_claim_r"]
        obs = {"lhs": nat_value(lhs), "rhs": nat_value(rhs)}
        return {"premises_hold": not failed, "failed": ", ".join(failed), "claim_holds": lhs == rhs,
                "observation": obs, "gen": G, "js": js, "commit": c, "witness": W, "B": B}

    # ---------------------------------------------------------------- the replay (S2)
    def replay(self, law: dict, cand: dict, obs: dict) -> dict:
        """The witness's consumer side on the real consumer: I88's batches of the candidate (the real blobs, I88's
        recorded compressor), by TestHolonReplay, offline; the real observation is I88's rule over the real outcomes."""
        from . import decide as DC
        from . import laws as LW
        lid = law["law_id"]
        if self.recorded_replay is not None:
            r = (self.recorded_replay.get("laws") or {}).get(lid)
            if r is None:
                raise Refused(f"--check: no recorded replay of {lid}'s witness")
            return r
        if self._i88 is None:       # I88's evaluation of its search space, from its recorded environment (no Go)
            side88 = LW.side_of(self.root, LW.LAWS_SIDECAR)
            Rn = DC.Run(self.root, side88, LW.LAWS_SIDECAR, True, None)
            header = DC.Header(self.root, side88)
            cands = Rn.candidates(header)
            env = load(self.root / Rn.out["environment"])

            def no_go(queries):
                raise DerivationError(f"no recorded answer for {queries[0][0]}")
            self._i88 = (Rn, header) + tuple(Rn.evaluate(cands, env["compressor"], copy.deepcopy(env["answers"]),
                                                         no_go))
        Rn, header, commits, outs, batches = self._i88
        w = cand["id"]
        cases = [{"id": f"{lid}/{i}", "batch": batches[f"{w}/{i}"]} for i in range(len(cand["batches"]))]
        from .goside import Workspace
        with Workspace(self.root, Rn.pside, Rn.section) as ws:
            real = ws.run("TestHolonReplay", "HOLON_DERIV_REPLAY", {"cases": cases})
            go_version, command = ws.go_version, ws.command("TestHolonReplay")
        ids = [cs["id"] for cs in cases]
        rs = [real.get(i) for i in ids]
        if any(x is None for x in rs):
            raise DerivationError(f"{lid}: the replay answered no case for the witness")
        cm = commits[w]
        hdr = None if cm["header"] is None else bytes.fromhex(cm["header"][2:])
        getters = sorted({t["product"].partition(":")[2] for t in BL._terms(law["statement"])
                          if isinstance(t, dict) and str(t.get("product", "")).startswith("committed")})
        c = {"commit": {"ok": cm["status"] == "ok", "header": hdr, "members": cand["members"]},
             "batches": [outs[f"{w}/{i}"] for i in range(len(cand["batches"]))],
             "getters": {g: header.get(g, hdr) for g in getters}}
        realobs = Rn.real_observation(law, cand, c, rs, {})
        model = [obs["lhs"], obs["rhs"]]
        ok = all(x["status"] == "ok" for x in rs) and realobs == model
        return {"cases": {i: x for i, x in zip(ids, rs)}, "model": model, "real": realobs,
                "status": "passed" if ok else "failed", "target_commit": Rn.pside["target"]["commit"],
                "go_version": go_version, "command": command}

    # ---------------------------------------------------------------- the decision and I88's record fields
    def finish(self, law: dict, cls: str, counter: bool, tried: list, found, no_proof: bool = False) -> dict:
        lid = law["law_id"]
        d = self.law_dir / lid
        name = BL.law_name(lid, counter)
        lf, pf = rel(self.root, d / "LAWS.bend"), rel(self.root, d / "PROOF.bend")
        ks = {"bend": {"exit_code": None, "marker": "not run"}, "bendtt": {"exit_code": None, "marker": "not run"}}
        if not no_proof:
            ks = self.kernels(d)
        both = accepted(ks["bend"]) and accepted(ks["bendtt"])
        tried.append(f"kernels: bend {ks['bend']['marker']!r} (exit {ks['bend']['exit_code']}), bendtt "
                     f"{ks['bendtt']['marker']!r} (exit {ks['bendtt']['exit_code']})")
        status, witness, observation, replay = "UNKNOWN", None, None, None
        if cls == "hyp_apply" and both:
            status = "PROVED"
        if found is not None:
            cand, got = found
            observation = got["observation"]
            c = got["commit"]
            witness = {"candidate": cand["id"], "step": cand["step"], "members": cand["members"],
                       "payload": cand["batches"][0]["payload"],
                       "contexts": {k: "0x" + v.hex() for k, v in sorted(got["witness"].ctxs.items())},
                       "txs_data": "0x" + got["B"].hex(), "ts": got["witness"].ts,
                       "blobhash_word": hex(got["witness"].V), "commit": {"status": c["status"], "code": c["code"]},
                       "keccak_table": len(c["kh"]),
                       "instances": {"cb": "one blob, the payload itself", "pl": "PlOk with that blob's bytes",
                                     "vh": "the constant blob hash", "et/dt": "a codec of opaque tokens",
                                     "circ": "accepts every step"}}
            if both:
                replay = self.replay(law, cand, observation)
                self.replays[lid] = replay
                if replay["status"] == "passed":
                    status = "REFUTED"
                else:
                    tried.append(f"replay: the real consumer's observation {replay['real']} is not the model's "
                                 f"{replay['model']}")
        if status == "UNKNOWN" and not no_proof and not both:
            tried.append("no verdict: a kernel did not accept the file")
        dec = {"status": status, "statement_hash": self.reg["statements"][lid], "law_name": name,
               "laws_file": lf, "proof_file": None if no_proof else pf, "class": cls, "kernels": ks,
               "witness": witness, "observation": observation,
               "replay": None if replay is None else {k: v for k, v in replay.items() if k != "cases"},
               "tried": tried}
        self.decisions[lid] = dec
        attempt = {"engine": "bend", "result": status.lower(), "class": cls, "law_name": name, "laws_file": lf,
                   "proof_file": dec["proof_file"], "kernels": ks, "tried": tried}
        out = {"status": status, "attempt": attempt}
        if status == "UNKNOWN":
            return out
        bend_version = json.loads((self.root / "config" / "holon.json").read_text())["bend"]["pinned_version"]
        out.update({
            "kernel": {"name": "bend", "verdict": "checked", "version": bend_version},
            "kernels": [{"name": "bend2", "result": "checked", "role": "primary", "version": bend_version},
                        {"name": "bendtt", "note": BENDTT_NOTE, "result": "checked", "role": "second",
                         "shares_frontend_with": "bend2", "version": bend_version}],
            "checker": {"exit_code": ks["bend"]["exit_code"], "marker": ks["bend"]["marker"],
                        "bendtt": {"exit_code": ks["bendtt"]["exit_code"], "marker": ks["bendtt"]["marker"]}},
            "artifacts": {"laws": lf, "proof": pf, "law_name": name, "model": rel(self.root, self.model_path),
                          "product": rel(self.root, self.pp), "equivalence": self.equiv["proof_file"]},
            "prover": "generator", "independence_class": "I1-shared",
            "model_assumptions": self.assumptions(law)})
        if status == "REFUTED":
            out.update({
                "witness": witness, "difference": {"lhs": observation["lhs"], "rhs": observation["rhs"]},
                "replay": {"status": replay["status"], "report": self.side["outputs"]["witnesses"],
                           "model": replay["model"], "real": replay["real"]},
                "witness_provenance": {"go": "internal_harness", "solidity": "internal_harness"},
                "filter_bin": "finding", "triage": "finding", "evidence_triage": "finding",
                "non_vacuity": {"status": "counter_witness", "law": name,
                                "witness": {"candidate": witness["candidate"]}, "reachable": True,
                                "degenerate": False, "parent_statement_hash": self.reg["statements"][lid],
                                "bound": "the counter-law's witness satisfies every premise (Bend and BendTT): the "
                                         "commit from the deployment state, the consumer model's runs"}})
        else:
            out.update({
                "replay": {"status": "not_applicable", "detail": "a proof has no witness"},
                "non_vacuity": {"status": "unknown", "law": name, "witness": None, "reachable": None,
                                "degenerate": None, "parent_statement_hash": self.reg["statements"][lid],
                                "bound": "finding: PROVED, non-vacuity not established: no checked inhabitant of the "
                                         "law's premises (G11V); the proof applies a hypothesis premise, so it holds "
                                         "of every instance of that hypothesis, inhabited or not"}})
        return out

    def assumptions(self, law: dict) -> list:
        from . import laws as LW
        hyps = {LW.assumption_id(h) for h in LW.hyp_names(law["statement"])}
        return sorted(hyps | {"I89-consumer-model-refinement", "I89-HypB-instance-132-canonical-cases"})

    # ---------------------------------------------------------------- bend-decide's own outputs
    def outputs(self) -> dict:
        out = dict(self.files)
        out[self.side["outputs"]["decisions"]] = dumps({
            "decisions_version": DECISIONS_VERSION,
            "sidecar": {"path": self.side_rel, "sha256": BL.hashlib.sha256((self.root / self.side_rel).read_bytes())
                        .hexdigest()},
            "equivalence": self.equiv, "search_bound": SEARCH_BOUND,
            "laws": dict(sorted(self.decisions.items()))})
        out[self.side["outputs"]["witnesses"]] = dumps({
            "witnesses_version": WITNESSES_VERSION, "laws": dict(sorted(self.replays.items()))})
        return out


def consumer_model(root: Path):
    """I88's decider's consumer model (holon.derivation.laws.verdict's `model`)."""
    return Engine(Path(root))


def run(root: Path, side_rel: str = BEND_SIDECAR, check: bool = False) -> tuple:
    """bend-decide: (outputs {rel: text}, the paths a --check found different)."""
    from . import decide as DC
    from . import laws as LW
    replay = None
    if check:
        side = load(Path(root) / side_rel)
        wp = Path(root) / side["outputs"]["witnesses"]
        if not wp.is_file():
            raise Refused(f"--check: {side['outputs']['witnesses']} is missing")
        replay = load(wp)
    eng = Engine(Path(root), side_rel, check=check, replay=replay)
    try:
        side88 = LW.side_of(Path(root), LW.LAWS_SIDECAR)
        recs = DC.run(Path(root), side88, LW.LAWS_SIDECAR, check=True, model=eng)
    finally:
        eng.close()
    out = eng.outputs()
    keep = {side88["outputs"]["splits"]} | {k for k in recs if k.startswith(side88["law_set"]["records"] + "/")}
    for k, v in recs.items():
        if k in keep:
            out[k] = v
        elif not (Path(root) / k).is_file() or (Path(root) / k).read_text(encoding="utf-8") != v:
            raise DerivationError(f"I88's {k} would move (bend-decide re-makes only its records and splits)")
    return out, eng.differs
