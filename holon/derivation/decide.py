"""`holon derivation decide` (the contract is the docstring of tests_m3/test_derivation_laws.py: rules W1-W4, RP1-RP2,
D1-D4 and SP1): the evaluator-level search for a witness of each plan-stated product law, its replay on the real
consumer, the records and the hypothesis split report.

  python -m holon derivation decide [--check] [--laws-sidecar PATH] [--root DIR]

The candidates (W1) are built from the law set's sidecar: the steps of the product traces of the product sidecar it
names, the search's grammar of payloads, and the start getter its search names. Each candidate is evaluated (W2) on the
product machine (holon.derivation.product: the commit by holon.extracted_eval, the consumer by holon.derivation.interp),
the committed getters on the linked header component's compiled Bend model (holon.gen.linked), and the oracles by the
real library through the generated Go test (holon.derivation.goside); every answer is recorded, so --check re-runs the
model with no Go. A law's statement is evaluated term by term (the product terms of the sidecar's vocabulary, its
premises in order); its witness is the first candidate whose premises all hold and whose claim's sides differ (W3).
Each witness's batches run on the real consumer (RP1-RP2). The records' verdicts come from holon.derivation.laws.verdict:
UNKNOWN without a Bend model of the consumer (D1-D3). Nothing here names a target: every function, field, member and
getter comes from the sidecars and the documents.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from . import DerivationError, Refused, dumps, load, ref, sha256_file
from . import laws as LW

CANDIDATES_VERSION = "holon-derivation-laws-candidates/0.1"
EVALUATIONS_VERSION = "holon-derivation-laws-evaluations/0.1"
ENVIRONMENT_VERSION = "holon-derivation-laws-environment/0.1"
REPLAY_VERSION = "holon-derivation-laws-replay/0.1"
SPLITS_VERSION = "holon-splits/0.1"
RECORD_VERSION = "holon-record/0.2"
MAX_ROUNDS = 8
# the plan member of the product machine's commit plans (holon.derivation.product: Product.commit reads it) that a
# candidate sets to start + n - 1 (rule W1); the product's plan vocabulary, not the target's
PLAN_LAST = "lastBlockNumber"
PLAN_BLOBS = "blobs"
SINGLE = ("consistent", "last_number", "l1_count", "trailing")


# ====================================================================== the search space (W1)
def start_getter(side: dict) -> str:
    m = re.search(r"header's ([A-Za-z_][A-Za-z0-9_]*) getter", side["search"]["start"])
    if not m:
        raise Refused("the search's start names no getter")
    return m.group(1)


def context_bytes(side: dict, number: int, pair: tuple) -> bytes:
    """One block context in the search's layout: a field with a value in search.context takes it, the vocabulary's
    dequeue fields take the pair, and the one remaining field is the block number."""
    c = side["search"]["context"]
    dq = side["vocabulary"]["dequeue"]
    rest = [n for n, _w in c["layout"] if n not in c and n not in dq]
    if len(rest) != 1:
        raise Refused(f"the context layout leaves {rest} for the block number")
    out = b""
    for name, width in c["layout"]:
        if name in dq:
            v = pair[dq.index(name)]
        elif name in c:
            v = c[name]
            v = int(v, 16) if isinstance(v, str) else int(v)
        else:
            v = number
        out += int(v).to_bytes(width, "big")
    return out


def payload(side: dict, start: int, n: int, mutation: str) -> tuple:
    """(payload, calldata contexts or None) of one batch of a candidate (rule W1)."""
    nums = list(range(start, start + n))
    pairs = [(0, 0)] * n
    tx = bytes.fromhex(side["search"]["transaction"][2:])
    stream = b""
    if mutation.endswith("last_number"):
        nums[-1] += 1
    if mutation == "l1_count":
        pairs[0] = (1, 1)
    if mutation == "trailing" or mutation.startswith("calldata"):
        stream = tx
    ctxs = b"".join(context_bytes(side, k, pr) for k, pr in zip(nums, pairs))
    if mutation.startswith("calldata"):
        return stream, n.to_bytes(2, "big") + ctxs
    return ctxs + stream, None


def mutations_of(side: dict) -> list:
    out = []
    for m in side["search"]["mutations"]:
        if m not in SINGLE:
            raise Refused(f"mutation {m!r} is not in the contract's grammar")
        out.append([m])
    for pr in side["search"]["pairs"]:
        if len(pr) != 2 or not all(x.startswith("calldata") for x in pr):
            raise Refused(f"pair {pr!r} is not in the contract's grammar")
        out.append(list(pr))
    return out


# ====================================================================== evaluation helpers (W2)
class Header:
    """The committed and parent getters on the linked header component's compiled Bend model (holon.gen.linked)."""

    def __init__(self, root: Path, side: dict):
        from .. import bend
        from ..gen import linked as GL
        rel = side["vocabulary"]["header_component"]
        raw = (root / rel).read_bytes()
        doc = json.loads(raw)
        self.fmt = side["vocabulary"]["header_getter"]
        self.cm = GL.CompiledModel.build(doc, hashlib.sha256(raw).hexdigest(), doc["role"], bend.config(root))
        self.model_sha256 = sha256_file(self.cm.source)
        self.compiled_sha256 = sha256_file(self.cm.artifact)
        self.cache: dict = {}
        self.used: set = set()

    def get(self, name: str, header: bytes | None):
        """The getter's value (big-endian), or None when the component's getter answers None (its error)."""
        if header is None:
            return None
        fn = self.fmt.format(name)
        self.used.add(fn)
        key = (fn, header)
        if key not in self.cache:
            res = self.cm.calls([{"fn": fn, "args": [{"val": list(header)}]}])[0]
            if isinstance(res, dict) and "error" in res:
                raise DerivationError(f"the header component's {fn}: {res['error']}")
            self.cache[key] = None if res is None else int.from_bytes(bytes(res["$some"]), "big")
        return self.cache[key]


def recording_interp(section: dict, environment: dict, answers: dict):
    """An interpreter that records each oracle query (function, argument key) it makes."""
    from .interp import Interp, arg_key
    from . import natives as NV

    class Recording(Interp):
        def __init__(self):
            super().__init__(section, environment, answers)
            self.queries = []

        def oracle(self, fid, args, rtype=""):
            if len(args) == 1:
                self.queries.append((fid, arg_key(NV.slice_bytes(args[0]))))
            return super().oracle(fid, args, rtype)
    return Recording()


def run_batches(section: dict, environment: dict, todo: list, answers: dict, ask, decoder: str) -> dict:
    """{batch id: model outcome with "decoded" and "decoded_items"}, asking the oracle for missing answers in rounds."""
    from .interp import NeedAnswer, arg_key
    done: dict = {}
    pending = list(todo)
    for _ in range(MAX_ROUNDS):
        queries: dict = {}
        nxt = []
        for bid, batch in pending:
            it = recording_interp(section, environment, answers)
            try:
                out = it.run(batch)
            except NeedAnswer as q:
                queries[(q.fid, arg_key(q.arg))] = (q.fid, q.arg)
                nxt.append((bid, batch))
                continue
            items, called = None, False
            for fid, key in it.queries:
                if fid == decoder:
                    a = answers[fid][key]
                    called = True
                    items = None if ("error" in a or "panic" in a) else ([] if a.get("nil") else list(a["items"]))
            out = dict(out, decoded=None if items is None else len(items), decoded_items=items, decoder_called=called)
            done[bid] = out
        if not queries:
            return done
        got = ask(sorted(queries.values(), key=lambda fa: (fa[0], arg_key(fa[1]))))
        for (fid, arg), a in got:
            answers.setdefault(fid, {})[arg_key(arg)] = a
        pending = nxt
    raise DerivationError(f"oracle answers still missing after {MAX_ROUNDS} rounds")


# ====================================================================== statements, term by term (W2-W4)
def _has_contexts(t) -> bool:
    if isinstance(t, list):
        return any(_has_contexts(x) for x in t)
    if isinstance(t, dict):
        return "contexts" in t or any(_has_contexts(v) for v in t.values())
    return False


class LawEval:
    """A law's premises and claim at a candidate: c = {"commit": {"ok", "header", "members"}, "batches": [outcome],
    "getters": {name: value}}; a term's batch is batch 0 without contexts, else the one its contexts variable names."""

    def __init__(self, law: dict, side: dict, action: str):
        self.law, self.side, self.action = law, side, action
        st = law["statement"]
        self.pair = _has_contexts(st)
        self.ctx_vars = [b["name"] for b in st["binders"] if b["type"] == "List<Nat>" and _ctx_var(st, b["name"])]
        self.circuit = None
        for p in st.get("assume", []):
            for t in _terms(p):
                if t.get("product") == "circuit_accepts":
                    cv = t["on"][0].get("var")
                    for q in st["assume"]:
                        if isinstance(q.get("hyp"), dict) and {"var": cv} in q["hyp"].get("args", []):
                            self.circuit = side["hypotheses"][q["hyp"]["name"]]

    def batch_index(self, t: dict) -> int:
        c = t.get("contexts")
        if c is None:
            return 0
        return self.ctx_vars.index(c["var"])

    def value(self, t, c: dict):
        voc = self.side["vocabulary"]
        if "bool" in t:
            return t["bool"]
        if "nat" in t:
            return t["nat"]
        if "app" in t:
            # an encoder parameter applied to the decoded transactions: under HypT's instance the real codec, whose
            # encoder's image of ts is a stream its decoder answers ts on; ts is batch 0's decoded list
            return ("encoding", tuple(c["batches"][0]["decoded_items"] or ()))
        if "fn" in t:
            if t["fn"] == "last_ok":
                return c["commit"]["ok"]
            if t["fn"].startswith("is_"):
                return t["fn"][3:] == self.action
            raise DerivationError(f"{self.law['law_id']}: term fn {t['fn']}")
        pid = t.get("product")
        if pid is None:
            raise DerivationError(f"{self.law['law_id']}: term {sorted(t)}")
        kind, _, arg = pid.partition(":")
        if kind in ("committed_ok", "committed"):
            v = c["getters"].get(arg) if c["commit"]["ok"] else None
            return (v is not None) if kind == "committed_ok" else v
        if kind == "input":
            return c["commit"]["members"].get(arg)
        if kind == "blobs_match":
            return True   # the commit's blob hashes are the hashes of the very blobs the consumer reads (W2)
        if kind == "circuit_accepts":
            return self.accepts(c)
        b = c["batches"][self.batch_index(t)]
        if kind == "derive_ok":
            return b["status"] == "ok"
        if kind == "txs_data":
            if b["status"] in ("unsupported",):
                return None
            if b["decoder_called"] and b["decoded_items"] is None:
                return ("raw",)   # the decoder refused these bytes: no ts has them as its encoding
            return ("encoding", tuple(b["decoded_items"] or ()))
        if b["status"] != "ok":
            return None
        info = b["info"]
        blocks = info.get(voc["blocks_field"]) or []
        if kind == "derived":
            return info.get(arg)
        if kind == "derived_sum":
            return sum(int(x[arg]) for x in blocks)
        if kind == "derived_blocks":
            return [int(x[voc["block_number"]]) for x in blocks]
        if kind == "derived_batch":
            return info
        if kind == "trailing":
            a, bb = voc["dequeue"]
            return None if b["decoded"] is None else b["decoded"] - sum(int(x[a]) - int(x[bb]) for x in blocks)
        raise DerivationError(f"{self.law['law_id']}: product term {pid}")

    def accepts(self, c: dict) -> bool:
        """The circuit hypothesis's evaluator instance: an equation between two acceptances admits the circuit that
        accepts every step; a claim over one step admits the circuit that accepts exactly where the claim holds."""
        h = self.circuit
        if h is None:
            raise DerivationError(f"{self.law['law_id']}: a circuit term with no hypothesis on its circuit")
        cl = h["statement"]["claim"]["eq"]
        if all(isinstance(x, dict) and x.get("product") == "circuit_accepts" for x in cl):
            return True
        return self.value(cl[0], c) == self.value(cl[1], c)

    def premises(self, c: dict) -> str:
        for i, p in enumerate(self.law["statement"].get("assume", [])):
            if "hyp" in p:
                continue   # the evaluator runs each hypothesis's instance (rule W2)
            a, b = p["eq"]
            va, vb = self.value(a, c), self.value(b, c)
            if va is None or vb is None or va != vb:
                return f"fail:{i}"
        return "hold"

    def claim(self, c: dict):
        a, b = self.law["statement"]["claim"]["eq"]
        return self.value(a, c), self.value(b, c)


def _ctx_var(st: dict, name: str) -> bool:
    return any(t.get("contexts") == {"var": name} for t in _terms(st))


def _terms(t):
    if isinstance(t, list):
        for x in t:
            yield from _terms(x)
    elif isinstance(t, dict):
        yield t
        for v in t.values():
            yield from _terms(v)


# ====================================================================== the run
class Run:
    def __init__(self, root: Path, side: dict, side_rel: str, check: bool, model=None):
        from . import sidecar as product_sidecar
        from .product import Product
        self.root, self.side, self.side_rel, self.check, self.model = root, side, side_rel, check, model
        self.psr = side["inputs"]["product_sidecar"]
        self.pside = product_sidecar(root, self.psr)
        self.product = Product(root, self.pside)
        self.section = self.product.section
        self.environment = self.pside["extract"].get("environment") or {}
        self.corpus = load(root / side["inputs"]["corpus"])
        self.action = self.pside["product"]["commit_action"]
        self.laws = LW.committed_laws(root, side)
        self.reg = load(root / side["law_set"]["laws"] / "REGISTRY.json")
        self.out = side["outputs"]

    # ---------------------------------------------------------------- the steps and their candidates
    def steps(self):
        """(trace id, k, the plan's first k commits, the blobs of commits 1..k-1, the parent header)."""
        from .corpus import blob
        data = {tr["id"]: {c["k"]: c for c in tr["commits"]} for tr in self.corpus["product"]}
        for plan in self.pside["corpus"]["product"]:
            rs = self.product.trace(plan, lambda k, d=data[plan["id"]]: [blob(x, j, []) for j, x in
                                                                        enumerate(d[k]["data"])])
            for k in range(1, len(plan["commits"]) + 1):
                if k > len(rs):
                    break
                parent = rs[k - 1]["parent"]
                yield plan, k, parent, data[plan["id"]]
                if rs[k - 1]["status"] != "ok":
                    break

    def candidates(self, header: Header) -> list:
        out = []
        cid = 0
        getter = start_getter(self.side)
        for plan, k, parent, _data in self.steps():
            last = header.get(getter, parent)
            start = last + 1 if last is not None else 1
            for n in self.side["search"]["blocks"]:
                for muts in mutations_of(self.side):
                    if len(muts) != 1:
                        continue
                    cid += 1
                    out.append(self._cand(cid, plan, k, start, n, muts))
            for n in self.side["search"]["blocks"]:
                for muts in mutations_of(self.side):
                    if len(muts) == 1:
                        continue
                    cid += 1
                    out.append(self._cand(cid, plan, k, start, n, muts))
        return out

    def _cand(self, cid, plan, k, start, n, muts) -> dict:
        batches = []
        for m in muts:
            pay, ctx = payload(self.side, start, n, m)
            batches.append({"mutation": m, "payload": "0x" + pay.hex(), "contexts": None if ctx is None else
                            "0x" + ctx.hex()})
        return {"id": cid, "step": {"trace": plan["id"], "k": k}, "start": start, "n": n, "mutation": "+".join(muts),
                "batches": batches}

    # ---------------------------------------------------------------- evaluation
    def commit_of(self, cand: dict, plans: dict, data: dict, blobs: list) -> dict:
        from .corpus import blob
        plan = plans[cand["step"]["trace"]]
        k = cand["step"]["k"]
        cm = dict(plan["commits"][k - 1])
        cm[PLAN_LAST] = cand["start"] + cand["n"] - 1
        prefix = {"id": plan["id"], "commits": list(plan["commits"][:k - 1]) + [cm]}
        d = data[plan["id"]]
        rs = self.product.trace(prefix, lambda j: blobs if j == k else [blob(x, i, []) for i, x in
                                                                          enumerate(d[j]["data"])])
        if len(rs) < k:
            raise DerivationError(f"{plan['id']} commit {k - 1} failed before the candidate's step")
        return rs[k - 1]

    def evaluate(self, cands: list, compressed: dict, answers: dict, ask) -> tuple:
        from .corpus import blob, chunks
        plans = {p["id"]: p for p in self.pside["corpus"]["product"]}
        data = {tr["id"]: {c["k"]: c for c in tr["commits"]} for tr in self.corpus["product"]}
        voc = self.side["vocabulary"]
        commits, todo, meta = {}, [], {}
        for cand in cands:
            plan = plans[cand["step"]["trace"]]
            nblobs = int(plan["commits"][cand["step"]["k"] - 1][PLAN_BLOBS])
            rows = []
            for i, b in enumerate(cand["batches"]):
                key = hashlib.sha256(bytes.fromhex(b["payload"][2:])).hexdigest()
                if key not in compressed:
                    raise DerivationError(f"candidate {cand['id']}: no compressed payload")
                b["data"] = chunks(bytes.fromhex(compressed[key][2:]), nblobs)
                rows.append([blob(x, j, []) for j, x in enumerate(b["data"])])
            r = self.commit_of(cand, plans, data, rows[0])
            members = copy.deepcopy(r["args"][self.pside["product"]["commit_param"]])
            cand["members"] = members
            commits[cand["id"]] = {"status": r["status"], "header": None if r["header"] is None else
                                   "0x" + r["header"].hex(), "reason": r["reason"]}
            meta[cand["id"]] = r
            for i, b in enumerate(cand["batches"]):
                batch = self.product.batch_of(r["args"], ["0x" + x.hex() for x in rows[i]])
                if b["contexts"] is not None:
                    batch[voc["contexts_field"]] = b["contexts"]
                todo.append((f"{cand['id']}/{i}", batch))
        outs = run_batches(self.section, self.environment, todo, answers, ask, voc["decoder"])
        return commits, outs, dict(todo)

    # ---------------------------------------------------------------- the laws
    def judge(self, cands: list, commits: dict, outs: dict, header: Header) -> dict:
        getters = sorted({t["product"].partition(":")[2] for law in self.laws for t in _terms(law["statement"])
                          if t.get("product", "").startswith("committed")})
        evals = [LawEval(law, self.side, self.action) for law in self.laws]
        res = {law["law_id"]: {"witness": None, "held": 0, "lhs": None, "rhs": None} for law in self.laws}
        for cand in cands:
            cm = commits[cand["id"]]
            hdr = None if cm["header"] is None else bytes.fromhex(cm["header"][2:])
            c = {"commit": {"ok": cm["status"] == "ok", "header": hdr, "members": cand["members"]},
                 "batches": [outs[f"{cand['id']}/{i}"] for i in range(len(cand["batches"]))],
                 "getters": {g: header.get(g, hdr) for g in getters}}
            for ev in evals:
                if ev.pair != (len(cand["batches"]) == 2):
                    continue
                lid = ev.law["law_id"]
                if ev.premises(c) != "hold":
                    continue
                res[lid]["held"] += 1
                lhs, rhs = ev.claim(c)
                if res[lid]["witness"] is None and lhs != rhs:
                    res[lid].update(witness=cand["id"], lhs=lhs, rhs=rhs)
        return res

    # ---------------------------------------------------------------- the replay (RP1-RP2)
    def real_observation(self, law: dict, cand: dict, model_c: dict, real: list, header_values: dict):
        ev = LawEval(law, self.side, self.action)
        c = copy.deepcopy(model_c)
        for i, r in enumerate(real):
            m = c["batches"][i]
            c["batches"][i] = dict(m, status=r["status"], info=r["info"], error=r["error"], panic=r["panic"])
        a, b = law["statement"]["claim"]["eq"]
        return [ev.value(a, c), ev.value(b, c)]

    # ---------------------------------------------------------------- outputs
    def records(self, res: dict, cands: list, commits: dict, outs: dict, replay: dict, header: Header) -> dict:
        from .. import records as RC
        out = {}
        bend_version = json.loads((self.root / "config" / "holon.json").read_text())["bend"]["pinned_version"]
        statuses = {}
        n = len(cands)
        bound = (f"{n} candidates: every commit of the product traces of {self.psr} (W1), each with "
                 f"n in {self.side['search']['blocks']} blocks and the mutations {self.side['search']['mutations']}, "
                 f"and the calldata pairs {self.side['search']['pairs']}; the hypotheses' evaluator instances (W2)")
        for law in self.laws:
            lid = law["law_id"]
            r = res[lid]
            w = r["witness"]
            evidence = {"law": lid, "witness": None if w is None else next(c for c in cands if c["id"] == w),
                        "observation": None if w is None else {"lhs": r["lhs"], "rhs": r["rhs"]},
                        "replay": replay["witnesses"].get(lid), "held": r["held"], "candidates": n}
            v = LW.verdict(law, evidence, self.model)
            statuses[lid] = v["status"]
            rw = replay["witnesses"].get(lid)
            attempt = {"engine": "product-evaluator", "result": "witness" if w is not None else "no_witness",
                       "candidates": n, "held": r["held"],
                       "witness": None if w is None else {"candidate": w, "step": evidence["witness"]["step"],
                                                          "n": evidence["witness"]["n"],
                                                          "mutation": evidence["witness"]["mutation"]},
                       "observation": evidence["observation"],
                       "replay": {"status": "not_run" if rw is None else rw["status"],
                                  "report": self.out["replay"]},
                       "evaluations": self.out["evaluations"],
                       "consumer": ("holon.derivation.interp over the derivation document's consumer section, refined "
                                    "against the real code by results/M3/derivation/refinement.json")}
            st = law["statement"]
            rec = {"law_id": lid, "rule": law["rule"], "subform": law["subform"], "maps_to": law["maps_to"],
                   "statement": render_statement(law),
                   "statement_hash": self.reg["statements"][lid], "facts_sha256": law["facts_sha256"],
                   "status": v["status"],
                   "premises": [render_premise(p) for p in st.get("assume", [])],
                   "attempts": [v["attempt"], attempt], "bound": bound, "witness": None, "difference": None,
                   "replay": {"status": "not_applicable",
                              "detail": "no kernel-checked witness; the evaluator witness's replay is its attempt's"},
                   "record_version": RECORD_VERSION, "model_sha256": header.model_sha256,
                   "compiled_sha256": header.compiled_sha256, "generator_sha256": generator_sha256(self.root),
                   "cone": sorted(header.used), "ledger_match": "exact",
                   "model_assumptions": sorted({LW.assumption_id(h) for h in LW.hyp_names(st)}),
                   "scope": "unbounded", "statement_scope": {"kind": "unbounded"},
                   "scope_v2": {"kind": "unbounded", "horizon": None, "at_state": None},
                   "kernel": {"name": "bend", "version": bend_version, "verdict": "not_run"},
                   "kernels": [{"name": "bend2", "version": bend_version, "role": "primary", "result": "not_run"}],
                   "independence_class": "none", "refinement_refs": [], "coverage": RC.coverage_field(law, self.root),
                   "non_vacuity": {"status": "unknown", "law": None, "witness": None, "reachable": None,
                                   "degenerate": None, "parent_statement_hash": self.reg["statements"][lid],
                                   "bound": f"premises hold at {r['held']} of {n} candidates (evaluator level)"},
                   "witness_provenance": None, "filter_bin": None, "evidence_levels": None, "evidence_triage": "none",
                   "evidence_override": None, "prover": "generator", "triage": "none",
                   "checker": {"exit_code": None, "marker": "not_run"},
                   "artifacts": {"laws": f"{self.side['law_set']['laws']}/{lid}.json", "model":
                                 self.side["vocabulary"]["header_component"], "proof": None, "law_name": None}}
            if v["status"] != "UNKNOWN":
                rec.update({k: x for k, x in v.items() if k not in ("status", "attempt")})
            out[f"{self.side['law_set']['records']}/{lid}.json"] = dumps(rec)
        out[self.out["splits"]] = dumps(splits(self.laws, statuses, self.side))
        return out


def generator_sha256(root: Path) -> str:
    """sha256 over the decider's module and every holon module it imports, transitively (holon.records' form)."""
    from .. import records as RC
    seen, todo = set(), ["holon/derivation/decide.py"]
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        todo.extend(sorted(RC._holon_imports(rel, root) - seen))
    h = hashlib.sha256()
    for rel in sorted(seen):
        h.update(rel.encode() + b"\0" + (root / rel).read_bytes() + b"\0")
    return h.hexdigest()


def splits(laws: list, statuses: dict, side: dict) -> dict:
    """SP1: law pairs on a hypothesis family (holon-splits/0.1's shape)."""
    fam = {h: e["family"] for h, e in side["hypotheses"].items()}
    groups: dict = {}
    for law in laws:
        mine: dict = {}
        for h in LW.hyp_names(law["statement"]):
            mine.setdefault(fam[h], []).append(h)
        for f, hs in mine.items():
            if len(set(hs)) != 1:
                continue
            st = copy.deepcopy(law["statement"])
            for p in st.get("assume", []):
                if isinstance(p.get("hyp"), dict) and p["hyp"]["name"] in hs:
                    p["hyp"] = {k: v for k, v in p["hyp"].items() if k != "ref"}
                    p["hyp"]["name"] = f
            groups.setdefault((f, LW.canon(st)), {})[law["law_id"]] = hs[0]
    pairs = []
    for (f, _), members in groups.items():
        if len(set(members.values())) < 2:
            continue
        lw = {lid: {"hypothesis": h, "status": statuses.get(lid, "UNKNOWN")} for lid, h in sorted(members.items())}
        st = {x["status"] for x in lw.values()}
        pairs.append({"family": f, "laws": lw, "split": "PROVED" in st and "REFUTED" in st})
    pairs.sort(key=lambda y: (y["family"], sorted(y["laws"])))
    return {"splits_version": SPLITS_VERSION, "milestone": side["law_set"]["milestone"], "pairs": pairs}


def _strip(o: dict) -> dict:
    return {k: v for k, v in o.items() if k not in ("decoded_items", "decoder_called")}


# ====================================================================== readable statements
def render(t) -> str:
    from .. import ir
    if isinstance(t, dict) and isinstance(t.get("product"), str):
        ctx = f" | {render(t['contexts'])}" if "contexts" in t else ""
        return f"{t['product']}({', '.join(render(a) for a in t['on'])}{ctx})"
    if isinstance(t, dict) and isinstance(t.get("fn"), str):
        return f"{t['fn']}({', '.join(render(a) for a in t['args'])})"
    if isinstance(t, dict) and isinstance(t.get("app"), str):
        return f"{t['app']}({', '.join(render(a) for a in t['args'])})"
    if isinstance(t, dict) and "step" in t:
        return f"step({render(t['step'])}, {render(t['from'])})"
    return ir.render_term(t)


def render_premise(p: dict) -> str:
    if isinstance(p.get("hyp"), dict):
        return f"{p['hyp']['name']}({', '.join(render(a) for a in p['hyp'].get('args', []))})"
    a, b = p["eq"]
    return f"{render(a)} == {render(b)}"


def render_statement(law: dict) -> str:
    st = law["statement"]
    head = ", ".join(f"∀ {b['name']}: {b['type']}" for b in st["binders"])
    prem = " ∧ ".join(render_premise(p) for p in st.get("assume", []))
    a, b = st["claim"]["eq"]
    return f"{head}. {prem} ⇒ {render(a)} == {render(b)}"


def run(root: Path, side: dict, side_rel: str, check: bool = False, model=None) -> dict:
    R = Run(root, side, side_rel, check, model)
    header = Header(root, side)
    cands = R.candidates(header)
    payloads = sorted({b["payload"] for c in cands for b in c["batches"]})
    env_rel = R.out["environment"]
    if check:
        env = load(root / env_rel)
        compressed = env["compressor"]
        answers = copy.deepcopy(env["answers"])

        def no_go(queries):
            raise DerivationError(f"decide --check: no recorded answer for {queries[0][0]}")
        commits, outs, batches = R.evaluate(cands, compressed, answers, no_go)
        rep = load(root / R.out["replay"])
        return finish(R, cands, commits, outs, batches, header, env["compressor"], env["answers"], rep)
    from .goside import Workspace
    with Workspace(root, R.pside, R.section) as ws:
        got = ws.run("TestHolonCompress", "HOLON_DERIV_COMPRESS", {"payloads": payloads})
        compressed = {}
        for p, r in zip(payloads, got):
            if "bytes" not in r:
                raise DerivationError(f"the compressor refused a payload: {r}")
            compressed[hashlib.sha256(bytes.fromhex(p[2:])).hexdigest()] = r["bytes"]
        answers: dict = {}

        def ask(queries):
            out = ws.run("TestHolonOracle", "HOLON_DERIV_ORACLE",
                         {"queries": [{"fn": f, "arg": "0x" + a.hex()} for f, a in queries]})
            if len(out) != len(queries):
                raise DerivationError("the oracle answered a different number of queries")
            for (f, _a), o in zip(queries, out):
                if "unsupported" in o:
                    raise DerivationError(f"the oracle cannot answer {f}: {o['unsupported']}")
            return list(zip(queries, out))
        commits, outs, batches = R.evaluate(cands, compressed, answers, ask)
        res = R.judge(cands, commits, outs, header)
        cases = []
        for lid in sorted(res):
            w = res[lid]["witness"]
            if w is None:
                continue
            cand = next(c for c in cands if c["id"] == w)
            for i in range(len(cand["batches"])):
                cases.append({"id": f"{lid}/{i}", "batch": batches[f"{w}/{i}"]})
        real = ws.run("TestHolonReplay", "HOLON_DERIV_REPLAY", {"cases": cases}) if cases else {}
        for cid, r in real.items():
            if r.get("status") == "input":
                raise DerivationError(f"{cid}: the replay could not build the batch: {r.get('error')}")
        rep = {"report_version": REPLAY_VERSION, "target_commit": R.pside["target"]["commit"],
               "go_version": ws.go_version, "command": ws.command("TestHolonReplay"),
               "cases": dict(sorted(real.items())), "witnesses": {}}
        return finish(R, cands, commits, outs, batches, header, compressed, answers, rep, res)


def finish(R: Run, cands, commits, outs, batches, header, compressed, answers, rep, res=None) -> dict:
    if res is None:
        res = R.judge(cands, commits, outs, header)
    # the witnesses' real observations (RP2), recomputed from the real cases on every run (--check included)
    wit = {}
    for lid in sorted(res):
        w = res[lid]["witness"]
        if w is None:
            continue
        cand = next(c for c in cands if c["id"] == w)
        law = next(x for x in R.laws if x["law_id"] == lid)
        ids = [f"{lid}/{i}" for i in range(len(cand["batches"]))]
        real = [rep["cases"].get(i) for i in ids]
        if any(r is None for r in real):
            raise DerivationError(f"{lid}: the replay report has no case for its witness")
        cm = commits[w]
        hdr = None if cm["header"] is None else bytes.fromhex(cm["header"][2:])
        getters = sorted({t["product"].partition(":")[2] for t in _terms(law["statement"])
                          if t.get("product", "").startswith("committed")})
        c = {"commit": {"ok": cm["status"] == "ok", "header": hdr, "members": cand["members"]},
             "batches": [outs[f"{w}/{i}"] for i in range(len(cand["batches"]))],
             "getters": {g: header.get(g, hdr) for g in getters}}
        model = [res[lid]["lhs"], res[lid]["rhs"]]
        realobs = R.real_observation(law, cand, c, real, {})
        ok = all(r["status"] == "ok" for r in real) and realobs == model
        wit[lid] = {"cases": ids, "model": model, "real": realobs, "status": "passed" if ok else "failed"}
    rep = dict(rep, witnesses=wit)
    cand_doc = {"candidates_version": CANDIDATES_VERSION, "sidecar": ref(R.root, R.side_rel), "candidates": cands}
    ev_doc = {"evaluations_version": EVALUATIONS_VERSION, "sidecar": ref(R.root, R.side_rel),
              "candidates": [{"id": c["id"], "commit": commits[c["id"]],
                              "batches": [_strip(outs[f"{c['id']}/{i}"]) for i in range(len(c["batches"]))]}
                             for c in cands],
              "laws": res}
    env_doc = {"environment_version": ENVIRONMENT_VERSION, "compressor": dict(sorted(compressed.items())),
               "answers": {f: dict(sorted(a.items())) for f, a in sorted(answers.items())}}
    out = {R.out["candidates"]: dumps(cand_doc), R.out["evaluations"]: dumps(ev_doc),
           R.out["environment"]: dumps(env_doc), R.out["replay"]: dumps(rep)}
    out.update(R.records(res, cands, commits, outs, rep, header))
    return out
