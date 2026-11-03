"""`python -m holon historical trans`: every in-scope transaction of the trans window, in chain order, stepped through
I20's extracted model, unchanged (the contract is the docstring of tests_m2/test_historical_exit.py).

    python -m holon historical trans [--milestone M2] [--supplement PATH] [--out PATH]

Inputs: the instrument (spec/<M>/lib/historical_exit.json), I59's index and snapshot (the in-scope transactions and
their receipts), the supplement (results/<M>/historical/supplement.json and its objects in the snapshot: headers,
storage, call answers, the implementation's code), the adopted transitions document and its extracted model
(holon.machine.load_extracted; holon.historical.stepper observes it), the pinned checkout and solc (the pinned build).

The replay (Replay, also the completion step of holon historical fetch-state):
  state    threaded through the whole window from one initial state (the instrument's storage_rule): a slot the replay
           has not yet touched holds the chain's value at from_block - 1; after a step that ends ok, the model's writes
           apply. A value the supplement lacks makes the step unsupported (a status disagreement), never 0.
  env      holon.historical.stepper.tx_env: the transaction, the block header, and as "calls" every call item at
           b - 1 (one entry per compiled function of that selector), never a call_after item.
  observed per step (holon.historical.stepper.Traced): the model's status, events, the slots it reads (pre-state
           reads) and writes, its external calls, the source lines it evaluated ("sites") and its width-site stores.
Comparisons with the chain:
  status   ok | revert | unsupported against the receipt's status (0x1 ok, else revert);
  events   the model's logs against the receipt's logs emitted by the proxy (topics and data, in order);
  storage  pre (the model's value before the step against the chain at b - 1) and post (after it against the chain at
           b) on every slot the step reads or writes; final (after the last step) on every slot the replay touched,
           against the chain at to_block; a differing final slot is a storage disagreement of the last step that
           wrote it on the model, or of the first step that read it if none did;
  calls    each call of a function in the instrument's call_logs against the logs of that event its callee emitted in
           the same receipt, whose data words equal the call's arguments in order (call_logs.rule); an unmatched call
           and an unmatched log (an address some call of the function went to) are calls disagreements.
call_stability counts the answers (calls with a b - 1 answer) and those whose call_after answer at b differs: a
diagnostic, never a disagreement. A step with any differing observable, or unsupported, is one disagreement of its
action's edge: id holon.refinement.disagreement_id("historical.<action>", tx hash), appended to
spec/<M>/disagreements.json as unexplained with no links and "milestone": "<M>"; its class is holon.refinement.classify
of the entry.

Outputs (canonical JSON, holon.ir.canonical_json): results/<M>/historical/trans.json (the contract's format; beside
it "width_sites": per width-site span, the steps that evaluated the store, the values over the field's width and the
largest value) and results/<M>/refinement/historical/<action>.json for each action stepped (the I16 record format,
kind "historical", with rho(e)'s implementation reference).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .. import extracted_eval as X
from .. import ir
from . import stepper as S
from .context import ContextError, Window

ROOT = Path(__file__).resolve().parents[2]
RECORD_VERSION = "holon-refinement/0.1"
OBSERVABLES = ["calls", "events", "status", "storage"]
NOT_APPLICABLE_REVERT = ("every in-scope transaction succeeded (each receipt has status 0x1; I59 indexes the "
                         "transactions of logs, and a reverted transaction emits none), so no step has a revert to "
                         "compare: the revert key (I20 clause 7) is not applicable")


def default_out(milestone: str = "M2", root: Path = ROOT) -> Path:
    return Path(root) / "results" / milestone / "historical" / "trans.json"


def write(doc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(ir.canonical_json(doc) + b"\n")
    tmp.replace(path)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def receipt_ok(rc: dict) -> bool:
    return int(rc.get("status") or "0x0", 16) == 1


def proxy_logs(rc: dict, proxy: str) -> list[dict]:
    return [{"topics": [t.lower() for t in lg["topics"]], "data": lg["data"].lower()}
            for lg in rc.get("logs") or [] if lg["address"].lower() == proxy]


def words(data: str) -> list[int]:
    h = data[2:]
    return [int(h[i:i + 64], 16) for i in range(0, len(h) - len(h) % 64, 64)]


def members_by_selector(model) -> dict:
    out: dict = {}
    for fn, entries in sorted((model.info.get("members") or {}).items()):
        for e in entries:
            if e.get("selector"):
                out.setdefault(e["selector"].lower(), []).append(fn)
    return out


def steps_of(w: Window, extras: list[dict]) -> list[dict]:
    """Every in-scope transaction (the instrument's in_scope.rule), sorted by (block, tx_index): I59's index items of
    kind tx in the trans window, plus `extras` ({block, tx, tx_sha, rc_sha}: the supplement's tx_other and
    receipt_other)."""
    rc = {x["tx"]: x for x in w.index_items("receipt")}
    out = []
    for x in w.index_items("tx"):
        if x["status"] != "ok" or x["tx"] not in rc or rc[x["tx"]]["status"] != "ok":
            raise ContextError(f"I59's index lacks the transaction or receipt of {x['tx']}")
        out.append({"tx": x["tx"], "block": x["block"], "tx_sha": x["sha256"], "rc_sha": rc[x["tx"]]["sha256"],
                    "extra": False})
    for e in extras:
        out.append({**e, "extra": True})
    for s in out:
        s["tx_obj"] = w.obj(s["tx_sha"])
        s["rc_obj"] = w.obj(s["rc_sha"])
        s["tx_index"] = int(s["tx_obj"]["transactionIndex"], 16)
    out.sort(key=lambda s: (s["block"], s["tx_index"]))
    return out


class Replay:
    """The threaded replay (module docstring). run() fills the step records and what is still needed."""

    def __init__(self, w: Window, model, plan: S.Plan, steps: list[dict], storage: dict, answers: dict,
                 headers: dict, hint_calls: dict | None = None):
        self.w, self.model, self.plan, self.steps = w, model, plan, steps
        self.storage, self.answers, self.headers = storage, answers, headers
        self.proxy = w.proxy
        self.lo, self.hi = w.trans["from_block"], w.trans["to_block"]
        self.by_sel = members_by_selector(model)
        self.calls_at: dict = {}
        for (kind, block, _key), a in sorted(answers.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
            if kind == "call":
                self.calls_at.setdefault(block, []).append(a)
        self.need_storage: set = set()
        self.need_calls: set = set()
        self.asked: dict = {}
        self.step_touch: dict = {}
        self.touched_all: set = set()
        self.records: list = []
        self.results: list = []

    def env_calls(self, block: int) -> list[dict]:
        out = []
        for a in self.calls_at.get(block, []):
            if a.get("from", "").lower() != self.proxy:
                continue
            for fn in self.by_sel.get(a["data"][:10].lower(), []):
                out.append({"fn": fn, "to": a["to"], "data": a["data"], "args": None, "ok": a["ok"],
                            "ret": a["ret"] if a["ret"] is not None else "0x"})
        return out

    def run(self) -> None:
        init = self.storage.get(self.lo - 1, {})
        state: dict = {}            # slots the replay wrote (model values)
        last_writer: dict = {}
        first_reader: dict = {}
        for i, s in enumerate(self.steps):
            b = s["block"]
            tx = s["tx_obj"]
            values = dict(init)
            values.update(state)
            reads, missing = set(), set()
            st = S.SlotState(values, reads, missing)
            env = S.tx_env(tx, self.proxy, self.headers.get(b), self.env_calls(b - 1))
            why = []
            if self.headers.get(b) is None:
                why.append(f"no header of block {b}")
            action = S.action_of(self.model, tx["input"])
            res, e, args = None, None, None
            if action is None:
                res = X._result("unsupported", reason=f"selector {tx['input'][:10]} is no action of the document")
            else:
                try:
                    args = S.decode_args(self.model, action, tx["input"])
                except Exception as x:  # noqa: BLE001 - calldata the compiled ABI rejects
                    res = X._result("unsupported", reason=f"{action}: calldata does not decode: {str(x)[:120]}")
            if res is None:
                res, e = S.traced_step(self.model, st, action, args, env, self.plan)
            self.need_storage |= {(self.lo - 1, x) for x in missing if x not in init}
            asked = S.asked_calls(self.model, self.plan, e) if e is not None else []
            self.asked[s["tx"]] = asked
            for c in asked:
                k = S.call_key(c["to"], c["data"], self.proxy)
                if ("call", b - 1, k) not in self.answers:
                    self.need_calls.add((c["to"], c["data"], self.proxy, b - 1, "call"))
                if ("call_after", b, k) not in self.answers:
                    self.need_calls.add((c["to"], c["data"], self.proxy, b, "call_after"))
            written = {int(k, 16): int(v, 16) for k, v in (res.get("writes") or {}).items()}
            rw = set(reads) | (set(e.touched) if e is not None else set()) | set(written)
            self.step_touch[s["tx"]] = rw
            # pre and post on every slot the step reads or writes
            pre_chain, post_chain = self.storage.get(b - 1, {}), self.storage.get(b, {})
            compared = differ = 0
            diff_slots = []
            for slot in sorted(rw):
                model_pre = values.get(slot)
                if model_pre is None:      # read but held by no value: the step is unsupported (its reason says so)
                    continue
                model_post = written.get(slot, model_pre) if res["status"] == "ok" else model_pre
                for side_v, chain, blk in ((model_pre, pre_chain, b - 1), (model_post, post_chain, b)):
                    if slot not in chain:
                        self.need_storage.add((blk, slot))
                        why.append(f"no chain value of slot 0x{slot:x} at block {blk}")
                        continue
                    compared += 1
                    if side_v != chain[slot]:
                        differ += 1
                        diff_slots.append(["0x%064x" % slot, blk])
            for slot in rw:
                self.touched_all.add(slot)
                first_reader.setdefault(slot, i)
            if res["status"] == "ok":
                for slot, v in written.items():
                    state[slot] = v
                    last_writer[slot] = i
            model_status = res["status"]
            if why and model_status != "unsupported":
                model_status = "unsupported"
            chain_status = "ok" if receipt_ok(s["rc_obj"]) else "revert"
            model_logs = [{"topics": [t.lower() for t in ev["topics"]], "data": ev["data"].lower()}
                          for ev in (res.get("events") or [])] if res["status"] == "ok" else []
            chain_logs = proxy_logs(s["rc_obj"], self.proxy)
            calls = list(e.calls_made) if e is not None else []
            have = {(c["fn"], c["to"], json.dumps(c["args"])) for c in calls}
            for c in asked:   # a call term evaluated outside its call check
                try:
                    sig = self.model.call_signature(c["fn"])
                    a = [S.arg_value(v) for v in X.abi_decode(bytes.fromhex(c["data"][10:]), sig["inputs"])] if sig else None
                except (X.Unsupported, ValueError, KeyError, TypeError):
                    a = None
                if a is not None and (c["fn"], c["to"], json.dumps(a)) not in have:
                    have.add((c["fn"], c["to"], json.dumps(a)))
                    calls.append({"fn": c["fn"], "to": c["to"], "args": a})
            batch = None
            for lg in chain_logs:
                if lg["topics"] and lg["topics"][0] in self.w.five and len(lg["topics"]) > 1:
                    batch = int(lg["topics"][1], 16)
                    break
            rec = {"tx": s["tx"], "block": b, "tx_index": s["tx_index"], "action": action,
                   "batch_index": batch,
                   "status": {"model": model_status, "chain": chain_status},
                   "events": {"model": len(model_logs), "chain": len(chain_logs), "agree": model_logs == chain_logs,
                              "logs": model_logs},
                   "storage": {"compared": compared, "differ": differ},
                   "calls": calls,
                   "sites": sorted(e.sites) if e is not None else []}
            if model_status != "ok":
                rec["model_reason"] = "; ".join(why + ([res["reason"]] if res.get("reason") else [])
                                                + ([f"reverted at {res['guard']}"] if res.get("guard") else []))[:600]
            if res["status"] == "revert":
                rec["revert"] = {"guard": res.get("guard"), "data": res.get("revert")}
            self.records.append(rec)
            self.results.append({"diff_slots": diff_slots, "asked": asked, "widths": list(e.width_values) if e else []})
        # the final comparison
        final_chain = self.storage.get(self.hi, {})
        fin = {"compared": 0, "differ": 0, "slots": []}
        for slot in sorted(self.touched_all):
            if slot not in final_chain:
                self.need_storage.add((self.hi, slot))
                continue
            fin["compared"] += 1
            v = state.get(slot, init.get(slot))
            if v is None or v != final_chain[slot]:
                fin["differ"] += 1
                at = last_writer.get(slot, first_reader.get(slot))
                fin["slots"].append({"slot": "0x%064x" % slot, "step": self.steps[at]["tx"] if at is not None else None})
        self.final = fin


def call_logs_observable(inst: dict, records: list[dict], steps: list[dict]) -> tuple[dict, dict]:
    """({fn: {logs, calls, matched}}, {tx: [why]}) of the instrument's call_logs (call_logs.rule)."""
    spec = {k: v for k, v in (inst.get("call_logs") or {}).items() if isinstance(v, dict) and v.get("topic0")}
    out, bad = {}, {}
    for fn, v in sorted(spec.items()):
        t0 = v["topic0"].lower()
        callees = {c["to"] for r in records for c in r["calls"] if c["fn"] == fn}
        q = (inst.get("in_scope") or {}).get("queue") or {}
        if (q.get("topic0") or "").lower() == t0 and q.get("address"):
            callees.add(q["address"].lower())
        logs_n = calls_n = matched = 0
        for r, s in zip(records, steps):
            calls = [c for c in r["calls"] if c["fn"] == fn]
            logs = [(lg["address"].lower(), words(lg["data"])) for lg in s["rc_obj"].get("logs") or []
                    if lg["topics"] and lg["topics"][0].lower() == t0 and lg["address"].lower() in callees]
            logs_n += len(logs)
            calls_n += len(calls)
            left = list(logs)
            for c in calls:
                hit = next((x for x in left if x[0] == c["to"] and x[1] == c["args"]), None)
                if hit is None:
                    bad.setdefault(r["tx"], []).append(f"call {fn}{tuple(c['args'])} to {c['to']} has no {v.get('event')} log")
                else:
                    left.remove(hit)
                    matched += 1
            for x in left:
                bad.setdefault(r["tx"], []).append(f"{v.get('event')} log {x[1]} of {x[0]} matches no call of {fn}")
        out[fn] = {"logs": logs_n, "calls": calls_n, "matched": matched}
    return out, bad


def load_supplement(w: Window, doc: dict) -> tuple[dict, dict, dict, list[dict], dict]:
    """(storage {block: {slot: value}}, answers {(kind, block, key): obj}, headers {block: obj}, extras, code
    {address: bytes}) of the supplement's ok items, read from the snapshot (each object re-hashed)."""
    storage, answers, headers, code = {}, {}, {}, {}
    other, orc = {}, {}
    for it in doc["items"]:
        if it["status"] != "ok":
            continue
        k, b = it["kind"], it["block"]
        if k == "storage":
            o = w.obj(it["sha256"])
            if o["address"].lower() == w.proxy:
                storage.setdefault(b, {})[int(o["slot"], 16)] = int(o["value"], 16)
        elif k in ("call", "call_after"):
            answers[(k, b, it["key"])] = w.obj(it["sha256"])
        elif k == "header":
            headers[b] = w.obj(it["sha256"])
        elif k == "code":
            code[it["key"]] = (w.snap.read(it["sha256"]), it["sha256"])
        elif k == "tx_other":
            other[(b, it["key"])] = it["sha256"]
        elif k == "receipt_other":
            orc[(b, it["key"])] = it["sha256"]
    extras = [{"block": b, "tx": t, "tx_sha": sha, "rc_sha": orc[(b, t)]} for (b, t), sha in sorted(other.items())
              if (b, t) in orc]
    return storage, answers, headers, extras, code


def transitions_model(w: Window):
    from .supplement import model_of
    return model_of(w)


def run(milestone: str = "M2", root: Path = ROOT, supplement: Path | None = None) -> dict:
    from .. import refinement as R
    w = Window(milestone, root)
    sp = supplement or (Path(root) / "results" / milestone / "historical" / "supplement.json")
    if not sp.is_file():
        raise ContextError(f"{sp} is missing: run python -m holon historical fetch-state")
    sdoc = json.loads(sp.read_text())
    storage, answers, headers, extras, code = load_supplement(w, sdoc)
    doc_rel, model = transitions_model(w)
    plan = S.Plan(model, doc_rel)
    steps = steps_of(w, extras)
    rp = Replay(w, model, plan, steps, storage, answers, headers)
    rp.run()
    recs = rp.records
    cl, cl_bad = call_logs_observable(w.inst, recs, steps)
    # the implementation
    impl = w.inst["implementation"]["last_upgrade"]["implementation"].lower()
    slot = int(w.inst["implementation"]["eip1967_implementation_slot"], 16)
    proxy_slot = storage.get(w.trans["to_block"], {}).get(slot)
    code_bytes, code_sha = code.get(impl, (None, None))
    from .pinned import PinnedError, pinned_build
    if code_bytes is None:
        pb = {"matched_config": None, "equal_masked": False, "immutables_masked": 0,
              "error": "the supplement holds no code item of the implementation"}
    else:
        try:
            pb = pinned_build(w.inst, code_bytes, root)
        except PinnedError as e:
            pb = {"matched_config": None, "equal_masked": False, "immutables_masked": 0, "error": str(e)[:400]}
    # disagreements, one per step
    dis, new_entries = [], []
    finals: dict = {}
    for x in rp.final["slots"]:
        finals.setdefault(x["step"], []).append(x["slot"])
    for n, (r, s) in enumerate(zip(recs, steps)):
        obs = []
        if r["status"]["model"] != r["status"]["chain"]:
            obs.append("status")
        if not r["events"]["agree"]:
            obs.append("events")
        if r["storage"]["differ"] or s["tx"] in finals:
            obs.append("storage")
        if s["tx"] in cl_bad:
            obs.append("calls")
        if r["status"]["model"] == "unsupported" and "status" not in obs:
            obs.append("status")
        if obs:
            edge = r["action"] or "unknown"
            did = R.disagreement_id(f"historical.{edge}", s["tx"])
            entry = {"id": did, "edge": edge, "milestone": milestone, "tx": s["tx"],
                     "observable": ",".join(sorted(obs)), "links": {}}
            new_entries.append({**entry, "input": {"tx": s["tx"], "block": s["block"]},
                                "detail": {"model_reason": r.get("model_reason"), "calls": cl_bad.get(s["tx"]),
                                           "storage": rp.results[n]["diff_slots"][:20],
                                           "final": finals.get(s["tx"])}})
            dis.append(entry)
    return {"w": w, "model": model, "doc_rel": doc_rel, "steps": steps, "replay": rp, "records": recs,
            "call_logs": cl, "pinned": pb, "impl": impl, "proxy_slot": proxy_slot, "code_sha": code_sha,
            "disagreements": dis, "new_entries": new_entries, "answers": answers, "supplement": sdoc}


def stability(rp: Replay, steps: list[dict]) -> dict:
    """answers: the steps' calls answered at b - 1; differ_at_b: those whose call_after answer at b differs (or is
    missing)."""
    n = d = 0
    for s, rec in zip(steps, rp.records):
        for c in rec["calls"]:
            data = S.calldata(rp.model, c["fn"], c["args"])
            if data is None:
                continue
            k = S.call_key(c["to"], data, rp.proxy)
            a = rp.answers.get(("call", s["block"] - 1, k))
            if a is None:
                continue
            n += 1
            z = rp.answers.get(("call_after", s["block"], k))
            if z is None or (z["ok"], z["ret"]) != (a["ok"], a["ret"]):
                d += 1
    return {"answers": n, "differ_at_b": d}


def width_sites(rp: Replay) -> dict:
    out: dict = {}
    for res in rp.results:
        seen = {}
        for span, val, width in res["widths"]:
            seen.setdefault(span, []).append((val, width))
        for span, vals in seen.items():
            o = out.setdefault(span, {"width": vals[0][1], "reached": 0, "over": 0, "undetermined": 0, "max": None})
            o["reached"] += 1
            if any(v is None for v, _w in vals):
                o["undetermined"] += 1
            if any(v is not None and v >> wd for v, wd in vals):
                o["over"] += 1
            m = max((v for v, _w in vals if v is not None), default=None)
            if m is not None and (o["max"] is None or m > int(o["max"], 16)):
                o["max"] = hex(m)
    return dict(sorted(out.items()))


def main(argv=None) -> int:
    from .. import refinement as R
    ap = argparse.ArgumentParser(prog="holon historical trans")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--supplement")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        r = run(a.milestone, ROOT, Path(a.supplement) if a.supplement else None)
    except (ContextError, S.StepperError) as e:
        print(f"historical trans: {e}", file=sys.stderr)
        return 2
    w, recs, rp, steps = r["w"], r["records"], r["replay"], r["steps"]
    by_action: dict = {}
    for x in recs:
        v = by_action.setdefault(x["action"] or "unknown", {"steps": 0, "ok": 0, "revert": 0, "unsupported": 0,
                                                           "events_agree": 0, "storage_compared": 0,
                                                           "storage_differ": 0})
        v["steps"] += 1
        v[x["status"]["model"]] += 1
        v["events_agree"] += int(x["events"]["agree"])
        v["storage_compared"] += x["storage"]["compared"]
        v["storage_differ"] += x["storage"]["differ"]
    calls_by_fn: dict = {}
    for x in recs:
        for c in x["calls"]:
            calls_by_fn[c["fn"]] = calls_by_fn.get(c["fn"], 0) + 1
    fin = rp.final
    sup_doc = r["supplement"]
    dis = []
    for d in r["disagreements"]:
        dis.append({**{k: d[k] for k in ("id", "edge", "tx", "observable", "links")}, "class": "unexplained"})
    # classes from the entries' links (after appending new ones)
    if r["new_entries"]:
        R.append_disagreements(ROOT, [{k: v for k, v in e.items()} for e in r["new_entries"]])
    entries = {e["id"]: e for e in json.loads((ROOT / R.DISAGREEMENTS).read_text())["disagreements"]}
    for d in dis:
        d["class"] = R.classify(entries[d["id"]], ROOT) if d["id"] in entries else "unexplained"
    doc = {
        "window": w.window("trans"),
        "facts": r["doc_rel"], "facts_sha256": sha256_file(ROOT / r["doc_rel"]),
        "model_sha256": sha256_file(ROOT / "gen" / a.milestone / "extracted" / "model.bend"),
        "implementation": {"address": r["impl"], "upgrade_block": w.inst["implementation"]["last_upgrade"]["block"],
                           "proxy_slot": ("0x%064x" % r["proxy_slot"]) if r["proxy_slot"] is not None else None,
                           "code_sha256": r["code_sha"], "pinned_build": r["pinned"]},
        "observables": OBSERVABLES, "not_applicable": {"revert": NOT_APPLICABLE_REVERT},
        "complete": {"other_rollup_logs": sum(1 for x in sup_doc["items"] if x["kind"] == "log_other"),
                     "extra_transactions": sum(1 for s in steps if s["extra"])},
        "steps": recs,
        "by_action": dict(sorted(by_action.items())),
        "storage": {"compared": sum(x["storage"]["compared"] for x in recs) + fin["compared"],
                    "differ": sum(x["storage"]["differ"] for x in recs) + fin["differ"],
                    "final": {"compared": fin["compared"], "differ": fin["differ"]}},
        "calls_by_fn": dict(sorted(calls_by_fn.items())),
        "call_stability": stability(rp, steps),
        "call_logs": r["call_logs"],
        "width_sites": width_sites(rp),
        "disagreements": dis,
        "unexplained": sum(1 for d in dis if d["class"] == "unexplained"),
    }
    out = Path(a.out) if a.out else default_out(a.milestone)
    write(doc, out)
    # one refinement record per action stepped (Def 4.7 rho(e))
    pin = w.inst["implementation"]["pinned"]
    for action in sorted(by_action):
        ss = [x for x in recs if x["action"] == action]
        ids = sorted({d["id"] for d in dis if d["edge"] == action})
        rec = {"record_version": RECORD_VERSION, "kind": "historical", "milestone": a.milestone, "edge": action,
               "diagram_edge": f"TRANS.{action}", "facts": r["doc_rel"], "facts_sha256": doc["facts_sha256"],
               "corpus": {"source": "historical", "window": w.window("trans"), "inputs": len(ss),
                          "inputs_sha256": R.sha256_json([x["tx"] for x in ss])},
               "compared": len(ss), "agree": len(ss) - len(ids), "disagreements": len(ids), "disagreement_ids": ids,
               "fixes": [],
               "implementation": {"address": r["impl"], "code_sha256": r["code_sha"], "source": pin["source"],
                                  "commit": pin["commit"]}}
        write(rec, ROOT / "results" / a.milestone / "refinement" / "historical" / f"{action}.json")
    print(json.dumps({"steps": len(recs), "by_action": doc["by_action"], "storage": doc["storage"],
                      "calls_by_fn": doc["calls_by_fn"], "call_stability": doc["call_stability"],
                      "call_logs": doc["call_logs"], "pinned_build": {k: r["pinned"].get(k) for k in
                                                                     ("matched_config", "equal_masked")},
                      "disagreements": len(dis), "unexplained": doc["unexplained"]}, sort_keys=True))
    print(f"wrote {out}")
    return 0 if not dis else 1
