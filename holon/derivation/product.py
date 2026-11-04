"""The product machine (rules J1-J3, K1-K5): the adopted Solidity commit joined with the extracted Go consumer, at the
evaluator level, and `holon derivation product`.

API (for laws over the product, e.g. I39's):
  p = Product(root, side)                       loads the commit document's model, the deployment's state, the join
                                                and the consumer section
  p.join                                        J1's rows [member, Go field, batch field or None]
  p.genesis, p.state0                           the first parent header and the member's storage after deployment
  r = p.commit(state, parent, plan, blobs, k)   one commit step (K2): r["status"], r["header"] (bytes) the header the
                                                Solidity model committed (J3), r["written"], r["state"] (after the step),
                                                r["index"], r["args"], r["reason"]
  b = p.batch_of(args, blobs)                   J2: the derived batch's JSON (Go field names), blobs as hex
  o = p.derive(batch, answers)                  the consumer model on a batch: {"status", "error", "panic", "info",
                                                "site", "reason"} (holon.derivation.interp); raises NeedAnswer when an
                                                oracle answer is missing from answers
  rs = p.trace(plan, blobs_of)                  K1-K3: a trace's commits from the deployment, each next parent the
                                                header the previous commit wrote; stops at the first failure

A blob's hash in the commit's environment is a stand-in (0x01, then bytes 1..31 of the blob's sha256), not its KZG
versioned hash: the consumer reads no hash and the Solidity commit treats blob hashes as words.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import OUT_GEN, Refused, dumps, load, ref

PRODUCT_VERSION = "holon-derivation-product/0.1"
WORD = 1 << 256


def stand_in_blobhash(b: bytes) -> int:
    return int.from_bytes(b"\x01" + hashlib.sha256(b).digest()[1:], "big")


def h32(v: int) -> str:
    return "0x%064x" % (v % WORD)


def _instrs(fn: dict):
    for b in fn.get("blocks") or []:
        for ins in b.get("instrs") or []:
            yield ins


def join_fields(section: dict, batch_type: str) -> dict:
    """{Go source field: batch field}: every store of the join function into a field of a local of the batch type,
    its value traced back through conversions, loads, slices and one-argument static calls to a field read."""
    fn = section["join"]["ssa"]
    defs = {i["name"]: i for i in _instrs(fn) if i.get("name")}
    allocs = {n for n, i in defs.items() if i.get("op") == "Alloc" and i.get("type") == "*" + batch_type}
    fields = {n: i["fieldname"] for n, i in defs.items()
              if i.get("op") == "FieldAddr" and (i["operands"][0] or {}).get("v") in allocs}

    def source(o, depth=0):
        if depth > 16 or not isinstance(o, dict) or o.get("v") not in defs:
            return None
        i = defs[o["v"]]
        op = i.get("op")
        if op in ("Field", "FieldAddr"):
            return i.get("fieldname")
        if op in ("Convert", "ChangeType", "Slice") or (op == "UnOp" and i.get("unop") == "*"):
            return source(i["operands"][0], depth + 1)
        if op == "Call" and i["call"].get("mode") == "static" and len(i["call"].get("args") or []) == 1:
            return source(i["call"]["args"][0], depth + 1)
        return None
    out = {}
    for i in _instrs(fn):
        if i.get("op") == "Store" and (i["operands"][0] or {}).get("v") in fields:
            s = source(i["operands"][1])
            if s is not None:
                out[s] = fields[i["operands"][0]["v"]]
    return out


def join_rows(section: dict, side: dict, rollup_doc: dict) -> list:
    """J1: [member, the Go field its first letter capitalized names, the batch field or None], in member order."""
    pr = side["product"]
    act = next((a for a in rollup_doc["actions"] if a["name"] == pr["commit_action"]), None)
    if act is None:
        raise Refused(f"the commit document has no action {pr['commit_action']}")
    par = next((p for p in act["params"] if p["name"] == pr["commit_param"]), None)
    if par is None or not par.get("fields"):
        raise Refused(f"{pr['commit_action']} has no struct parameter {pr['commit_param']}")
    jf = join_fields(section, pr["batch_type"])
    rows = []
    for m in par["fields"]:
        go = m["name"][:1].upper() + m["name"][1:]
        rows.append([m["name"], go, jf.get(go)])
    return rows


class Product:
    def __init__(self, root: Path, side: dict):
        from ..machine import load_extracted
        self.root, self.side = root, side
        pr = side["product"]
        self.pr = pr
        doc_rel = side["extract"]["output"]
        if not (root / doc_rel).is_file():
            raise Refused(f"{doc_rel} is missing (run holon derivation extract first)")
        self.doc = load(root / doc_rel)
        self.section = self.doc["consumer"]
        self.rollup_doc = load(root / pr["rollup_document"])
        self.model = load_extracted(pr["rollup_document"], root)
        dep = load(root / pr["deployment"]["record"])
        mem = dep["members"][pr["deployment"]["member"]]
        self.address = int(mem["address"], 16)
        self.state0 = dict(mem["storage"])
        self.genesis = bytes.fromhex(pr["genesis"][2:])
        self.join = join_rows(self.section, side, self.rollup_doc)
        self.action = pr["commit_action"]

    # ------------------------------------------------------------------ the Solidity half
    def env(self, plan: dict, blobs: list, k: int, calldata_len: int) -> dict:
        actor = int(self.pr["actors"][str(plan["who"])], 16)
        ts = int(self.pr["timestamp"]["first"]) + int(self.pr["timestamp"]["step"]) * k
        calls = []
        for c in self.pr["calls"]:
            if c["answer"] == "true":
                calls.append({"fn": c["fn"], "to": None, "data": "0x00000000" + h32(actor)[2:], "args": None,
                              "ok": True, "ret": h32(1)})
            elif c["answer"] == "timestamp":
                calls.append({"fn": c["fn"], "to": None, "data": "0x00000000", "args": None, "ok": True,
                              "ret": h32(ts)})
            else:
                raise Refused(f"call answer {c['answer']!r}")
        return {"caller": actor, "this": self.address, "msg.value": 0, "msg.data.length": calldata_len,
                "block.timestamp": ts, "block.number": 1000 + k, "blobhash": [stand_in_blobhash(b) for b in blobs],
                "calls": calls}

    def commit(self, state: dict, parent: bytes, plan: dict, blobs: list, k: int, prev_root: str) -> dict:
        from .. import extracted_eval as EV
        args = {self.pr["commit_param"]: {
            "version": plan["version"], "parentBatchHeader": "0x" + parent.hex(),
            "lastBlockNumber": plan["lastBlockNumber"], "numL1Messages": 0, "prevStateRoot": prev_root,
            "postStateRoot": plan["postStateRoot"], "withdrawalRoot": plan["withdrawalRoot"]}}
        params = self.model.params(self.action)
        calldata = EV.abi_encode([EV.norm(args[p["name"]], p) for p in params], params)
        env = self.env(plan, blobs, k, 4 + len(calldata))
        out = {"status": None, "header": None, "written": None, "state": None, "index": None, "args": args,
               "reason": None}
        prog = self.model.program(self.action)
        e = EV.Eval(self.model, state, self.action, args, env)
        try:
            e.run(prog.steps)
        except EV.Reverted as x:
            out.update(status="revert", reason=f"guard {x.check.id}: {EV.hexb(x.data)}")
            return out
        except EV.CallReverted as x:
            out.update(status="revert", reason=f"external call {x.fn} reverted")
            return out
        except (EV.Unsupported, ArithmeticError, RecursionError) as x:
            out.update(status="unsupported", reason=f"{type(x).__name__}: {x}")
            return out
        w = next((s for s in prog.steps if getattr(s, "family", None) == self.pr["header_family"]), None)
        if w is None or not (isinstance(w.value, list) and len(w.value) == 2 and w.value[0] == "keccak256"):
            out.update(status="unsupported", reason="no keccak256 write to the header family")
            return out
        try:
            header = e.as_bytes(e.ev(w.value[1]))
            slot, _off, _tid = e.locate(EV.SRef(w.family, tuple(e.path(w.path))))
        except EV.Unsupported as x:
            out.update(status="unsupported", reason=f"the header: {x}")
            return out
        written = e.overlay.get(slot)
        new = dict(state)
        for s in e.touched:
            new[h32(s)] = h32(e.overlay[s])
        out.update(status="ok", header=header, written=written, state=new,
                   index=int.from_bytes(header[1:9], "big") if len(header) >= 9 else None)
        return out

    # ------------------------------------------------------------------ the join and the Go half
    def batch_of(self, args: dict, blobs_hex: list) -> dict:
        member = args[self.pr["commit_param"]]
        b: dict = {}
        for m, _go, field in self.join:
            if field is not None:
                b[field] = member[m]
        cur = b
        path = self.pr["blobs_field"]
        for name in path[:-1]:
            cur = cur.setdefault(name, {})
        cur[path[-1]] = list(blobs_hex)
        return b

    def derive(self, batch: dict, answers: dict) -> dict:
        from .interp import Interp
        return Interp(self.section, self.side["extract"].get("environment") or {}, answers).run(batch)

    def trace(self, plan: dict, blobs_of) -> list:
        """K1-K3: the commits of a trace; blobs_of(k) gives commit k's blobs (bytes)."""
        state, parent = dict(self.state0), self.genesis
        prev_root = "0x" + self.genesis[121:153].hex()
        out = []
        for k, cm in enumerate(plan["commits"], start=1):
            blobs = blobs_of(k)
            r = self.commit(state, parent, cm, blobs, k, prev_root)
            r["parent"] = parent
            r["k"] = k
            r["version"] = cm["version"]
            out.append(r)
            if r["status"] != "ok":
                break
            state, parent, prev_root = r["state"], r["header"], cm["postStateRoot"]
        return out


def run(root: Path, side: dict, side_rel: str) -> dict:
    from .corpus import blob
    cor_rel = f"{OUT_GEN}/corpus.json"
    if not (root / cor_rel).is_file():
        raise Refused(f"{cor_rel} is missing (run holon derivation corpus first)")
    corpus = load(root / cor_rel)
    if corpus.get("sidecar", {}).get("sha256") != ref(root, side_rel)["sha256"]:
        raise Refused(f"{cor_rel} names another sidecar")
    p = Product(root, side)
    commits_of = {tr["id"]: {c["k"]: c for c in tr["commits"]} for tr in corpus["product"]}
    traces = []
    for plan in side["corpus"]["product"]:
        cc = commits_of[plan["id"]]
        rs = p.trace(plan, lambda k: [blob(c, j, []) for j, c in enumerate(cc[k]["data"])])
        rows = []
        for r in rs:
            batch = None
            if r["status"] == "ok":
                # the record keeps the batch's joined fields and its blob count; the blobs are the corpus commit's
                # (rule C2), and refine builds the full value from them
                batch = p.batch_of(r["args"], [])
                cur = batch
                for name in p.pr["blobs_field"][:-1]:
                    cur = cur[name]
                cur[p.pr["blobs_field"][-1]] = len(cc[r["k"]]["data"])
            hdr = r["header"]
            rows.append({"k": r["k"], "version": r["version"], "status": r["status"], "index": r["index"],
                         "header": "0x" + hdr.hex() if hdr is not None else None,
                         "hash": h32(int.from_bytes(_keccak(hdr), "big")) if hdr is not None else None,
                         "written": h32(r["written"]) if r["written"] is not None else None,
                         "parent": "0x" + r["parent"].hex(), "batch": batch, "reason": r["reason"]})
        traces.append({"id": plan["id"], "commits": rows})
    env = [[e["function"], e["kind"]] for e in p.section["environment"]]
    out = {"product_version": PRODUCT_VERSION, "sidecar": ref(root, side_rel),
           "document": ref(root, side["extract"]["output"]),
           "rollup_document": ref(root, side["product"]["rollup_document"]),
           "deployment": ref(root, side["product"]["deployment"]["record"]),
           "join": p.join, "environment": env, "traces": traces}
    return {f"{OUT_GEN}/product.json": dumps(out)}


def _keccak(b: bytes) -> bytes:
    from ..keccak import keccak256
    return keccak256(b)
