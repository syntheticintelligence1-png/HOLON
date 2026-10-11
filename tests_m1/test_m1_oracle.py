"""Independent oracle cross-check for the M1 rollup machine.

The Oracle class below is a small Python reimplementation of the rollup
transition function, written directly from

  contracts/contracts/l1/rollup/Rollup.sol
  contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol
  contracts/contracts/l1/rollup/Submitter.sol

at Morph commit 3e44e795586af3e11285b603ab642c67823add51, using only the
register projection documented in docs/M1_REPORT.md (win = committedBatches
window LFI..LCI, s_* = residues above LCI, chs = challenges by absolute
index, log = newest-first per-step outcomes).  It never reads spec/M1/facts,
the generated model, or machine.mjs: the only use of those files is on the
machine side of the comparison (the model under test).

For every action trace enumerated by the search policy's parameter domain
(up to the depth cap, or depth 2 if that would exceed ~20k traces) and for
300 fixed-seed random traces, the test runs each step on both the compiled
Bend machine and the oracle and compares the resulting full register state,
including the outcome tag in the log head.
"""
import random
import unittest
from pathlib import Path

from holon.mpipeline import CompiledMachine, ROOT

FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"

OWNER, DEP, Z, AGG = 1, 1, 1, 1000


def _pair(a, b):
    return (a + b) * (a + b + 1) // 2 + b


def _enc(xs):  # injective list encoding standing in for keccak(concat)
    if not xs:
        return 0
    return 1 + _pair(xs[0], _enc(xs[1:]))


def _empty_entry():
    return {f: 0 for f in ("ver", "tot", "n", "hb", "prev", "post", "lbn",
                           "csr", "bvh", "tag", "bdo", "bdf", "bdn", "bds")}


def _empty_ch():
    return {"c": 0, "d": 0, "s": 0, "w": False, "f": False}


def _nth(xs, i):
    return xs[i] if i < len(xs) else 0


def _nth_ch(cs, i):
    return cs[i] if i < len(cs) else _empty_ch()


def _blob_count(xs):
    return sum(1 for x in xs if x != 0)


class Oracle:
    """State = the modelled registers, projected from Rollup.sol storage."""

    def __init__(self):
        # initialize(...) + importGenesisBatch at block.timestamp 10
        self.s = {
            "t": 10, "lfi": 0, "inch": False, "bc": 0, "rri": 0,
            "paused": False, "W": 10, "F": 40, "D": 20,
            "qlen": 0, "qpend": 0, "enq": [],
            "active": [2, 3], "chals": [4],
            "fsr": [100], "chs": [],
            "win": [{"ver": 0, "tot": 0, "n": 0, "hb": 1, "prev": 0,
                     "post": 100, "lbn": 0, "csr": 100, "bvh": 1, "tag": 1,
                     "bdo": 10, "bdf": 10, "bdn": 0, "bds": 0}],
            "s_csr": [], "s_bd": [], "s_bvh": [], "s_tag": [],
            "log": [],
        }

    # -- storage views -----------------------------------------------------
    def lci(self, s):
        return s["lfi"] + len(s["win"]) - 1

    def w(self, s, idx):  # batchDataStore/header view of committed idx
        if s["lfi"] <= idx <= self.lci(s):
            return s["win"][idx - s["lfi"]]
        return _empty_entry()

    def bvh_at(self, s, idx):  # batchBlobVersionedHashes incl. residues
        if idx < s["lfi"]:
            return 0
        if idx <= self.lci(s):
            return self.w(s, idx)["bvh"]
        return _nth(s["s_bvh"], idx - self.lci(s) - 1)

    def tag_at(self, s, idx):  # ghost tag of the above
        if idx < s["lfi"]:
            return 0
        if idx <= self.lci(s):
            return self.w(s, idx)["tag"]
        return _nth(s["s_tag"], idx - self.lci(s) - 1)

    def enq_first(self, s):  # messageEnqueueTime[pendingQueueIndex]
        if s["qpend"] < s["qlen"] and _nth(s["enq"], s["qpend"]) != 0:
            return s["enq"][s["qpend"]]
        return s["t"]

    def open_ch(self, s, idx):  # batchInChallenge
        ch = _nth_ch(s["chs"], idx)
        return ch["c"] != 0 and not ch["f"]

    def blob_hash(self, ver, blobs):  # _computeBlobVersionedHash
        if ver == 2:
            return AGG + _enc(blobs)
        return Z if _nth(blobs, 0) == 0 else _nth(blobs, 0)

    # -- outcomes ------------------------------------------------------------
    def _ok(self, **eff):
        self.s.update(eff)
        self.s["log"] = [{"$": "O_Ok"}] + self.s["log"]

    def _rev(self, code):
        self.s["log"] = [{"$": "O_Rev", "code": code}] + self.s["log"]

    def _commit_common(self, a, who_check, allow_proof=False):
        """Shared tail of _commitBatch (Rollup.sol:293-375): version/root/parent
        checks, then the BatchData append with the proof-window carry-over."""
        s = self.s
        if a["ver"] > 2:
            return 8
        if a["prev"] == 0:
            return 9
        if a["post"] == 0:
            return 10
        lci = self.lci(s)
        if a["parent"] + 1 <= lci:
            return 11
        if a["parent"] != lci:
            return 12
        if self.w(s, a["parent"])["csr"] != a["prev"]:
            return 14
        tot = self.w(s, a["parent"])["tot"]
        if tot + a["n"] > s["qlen"]:
            return 15
        cstart = _nth_ch(s["chs"], s["bc"])["s"]
        if s["inch"] and s["t"] > s["W"] + cstart:
            return 16  # proofWindow + startTime - t underflows (Panic 0x11)
        prt = (s["W"] + cstart - s["t"]) if s["inch"] else 0
        return tot, prt

    def _push_entry(self, a, tot, prt, bvh, tag, bds, bdf):
        s = self.s
        e = {"ver": a["ver"], "tot": tot + a["n"], "n": a["n"], "hb": bvh,
             "prev": a["prev"], "post": a["post"], "lbn": a["lbn"],
             "csr": a["post"], "bvh": bvh, "tag": tag, "bdo": s["t"],
             "bdf": bdf, "bdn": a["lbn"], "bds": bds}
        self._ok(win=s["win"] + [e],
                 s_csr=s["s_csr"][1:], s_bd=s["s_bd"][1:],
                 s_bvh=s["s_bvh"][1:], s_tag=s["s_tag"][1:])

    # -- actions (Rollup.sol, in source guard order) -------------------------
    def commitBatch(self, a):
        s = self.s
        if a["who"] not in s["active"]:
            return self._rev(1)
        if s["rri"] != 0:
            return self._rev(2)
        if s["paused"]:
            return self._rev(3)
        if self.bvh_at(s, a["parent"] + 1) != 0:
            return self._rev(4)
        if self.enq_first(s) + s["D"] < s["t"] and a["n"] == 0:
            return self._rev(5)  # l1msg delay
        if a["ver"] == 2 and _blob_count(a["blobs"]) == 0:
            return self._rev(6)
        if a["ver"] != 2 and _nth(a["blobs"], 1) != 0:
            return self._rev(7)
        r = self._commit_common(a, True)
        if isinstance(r, int):
            return self._rev(r)
        tot, prt = r
        bvh = self.blob_hash(a["ver"], a["blobs"])
        tag = 2 if a["ver"] == 2 else 1
        self._push_entry(a, tot, prt, bvh, tag, a["who"], s["t"] + s["F"] + prt)

    def commitState(self, a):
        s = self.s
        if a["who"] not in s["active"]:
            return self._rev(1)
        if s["rri"] != 0:
            return self._rev(2)
        if s["paused"]:
            return self._rev(3)
        if _nth(a["blobs"], 0) != 0:
            return self._rev(17)  # commitState must not carry blob
        stored = self.bvh_at(s, a["parent"] + 1)
        if stored == 0:
            return self._rev(18)  # no stored blob hash for this batch
        if self.enq_first(s) + s["D"] < s["t"] and a["n"] == 0:
            return self._rev(5)
        r = self._commit_common(a, True)
        if isinstance(r, int):
            return self._rev(r)
        tot, prt = r
        self._push_entry(a, tot, prt, stored,
                         self.tag_at(s, a["parent"] + 1), a["who"],
                         s["t"] + s["F"] + prt)

    def commitBatchWithProof(self, a):
        s = self.s
        if s["rri"] != 0:
            return self._rev(2)
        if s["paused"]:
            return self._rev(3)
        rd = self.w(s, self.lci(s))["bdo"] + s["D"] < s["t"]
        qd = self.enq_first(s) + s["D"] < s["t"]
        if not (rd or not qd or a["n"] > 0):
            return self._rev(5)
        if not (rd or qd):
            return self._rev(19)  # invalid timing
        stored = self.bvh_at(s, a["parent"] + 1)
        if stored != 0 and _nth(a["blobs"], 0) != 0:
            return self._rev(20)  # must not carry blob with stored hash
        if stored == 0 and a["ver"] == 2 and _blob_count(a["blobs"]) == 0:
            return self._rev(6)
        if stored == 0 and a["ver"] != 2 and _nth(a["blobs"], 1) != 0:
            return self._rev(7)
        bvh = stored if stored != 0 else self.blob_hash(a["ver"], a["blobs"])
        tag = (self.tag_at(s, a["parent"] + 1) if stored != 0
               else (2 if a["ver"] == 2 else 1))
        r = self._commit_common(a, False)
        if isinstance(r, int):
            return self._rev(r)
        tot, prt = r
        if a["proof"] == 0:
            return self._rev(21)
        if a["proof"] != 1:
            return self._rev(22)
        # commitState path: batchDataStore is skipped (submitter 0, bdo = t)
        self._push_entry(a, tot, prt, bvh, tag, 0, s["t"])

    def revertBatch(self, a):
        s = self.s
        if a["who"] != OWNER:
            return self._rev(23)
        if a["count"] == 0:
            return self._rev(24)
        lci = self.lci(s)
        if a["idx"] > lci:
            return self._rev(25)
        if a["idx"] + a["count"] <= lci:
            return self._rev(26)
        if a["idx"] <= s["lfi"]:
            return self._rev(27)
        p = a["idx"] - s["lfi"]
        moved = s["win"][p:]
        lo, hi = a["idx"], lci
        any_open = any(lo <= i <= hi and c["c"] != 0 and not c["f"]
                       for i, c in enumerate(s["chs"]))
        chs = [_empty_ch() if lo <= i <= hi else c
               for i, c in enumerate(s["chs"])]
        self._ok(win=s["win"][:p],
                 s_csr=[e["csr"] for e in moved] + s["s_csr"],
                 s_bd=[{"o": e["bdo"], "f": e["bdf"],
                        "n": e["bdn"], "s": e["bds"]} for e in moved] + s["s_bd"],
                 s_bvh=[e["bvh"] for e in moved] + s["s_bvh"],
                 s_tag=[e["tag"] for e in moved] + s["s_tag"],
                 inch=s["inch"] and not any_open, chs=chs,
                 rri=0 if lo <= s["rri"] <= hi and s["rri"] > 0 else s["rri"])

    def challengeState(self, a):
        s = self.s
        if a["who"] not in s["chals"]:
            return self._rev(28)
        if s["rri"] != 0:
            return self._rev(2)
        if s["paused"]:
            return self._rev(3)
        if s["inch"]:
            return self._rev(29)
        if not (s["lfi"] < a["idx"]):
            return self._rev(30)
        if a["idx"] > self.lci(s):
            return self._rev(25)
        if self.w(s, a["idx"])["bdo"] == 0:
            return self._rev(31)
        if _nth_ch(s["chs"], a["idx"])["c"] != 0:
            return self._rev(32)
        if not (self.w(s, a["idx"])["bdf"] > s["t"]):
            return self._rev(33)
        if a["value"] < DEP:
            return self._rev(34)
        skip = a["idx"] - s["lfi"]
        win = [dict(e, bdf=e["bdf"] + s["W"]) if 0 < i != skip else e
               for i, e in enumerate(s["win"])]
        chs = list(s["chs"]) + [_empty_ch()] * (a["idx"] + 1 - len(s["chs"]))
        chs[a["idx"]] = {"c": a["who"], "d": a["value"], "s": s["t"],
                         "w": False, "f": False}
        self._ok(bc=a["idx"], chs=chs, win=win, inch=True)

    def proveState(self, a):
        s = self.s
        if s["rri"] != 0:
            return self._rev(2)
        if s["paused"]:
            return self._rev(3)
        if a["who"] not in s["active"]:
            return self._rev(1)
        if a["idx"] > self.lci(s):
            return self._rev(25)
        if not self.open_ch(s, a["idx"]):
            return self._rev(35)
        ch = _nth_ch(s["chs"], a["idx"])
        timeout = ch["s"] + s["W"] <= s["t"]
        if not timeout and a["proof"] == 0:
            return self._rev(21)
        if not timeout and a["proof"] != 1:
            return self._rev(22)
        chs = list(s["chs"])
        chs[a["idx"]] = dict(ch, f=True, w=timeout)
        active = s["active"]
        if timeout:  # _challengerWin: slash deactivates the submitter
            active = [x for x in active if x != self.w(s, a["idx"])["bds"]]
        self._ok(chs=chs, inch=False,
                 rri=a["idx"] if timeout else s["rri"], active=active)

    def finalizeBatch(self, a):
        s = self.s
        if s["rri"] != 0:
            return self._rev(2)
        if s["paused"]:
            return self._rev(3)
        if a["idx"] > self.lci(s):
            return self._rev(25)
        if a["idx"] < s["lfi"] or self.w(s, a["idx"])["bdo"] == 0:
            return self._rev(31)
        if self.open_ch(s, a["idx"]):
            return self._rev(35)
        if _nth_ch(s["chs"], a["idx"])["w"]:
            return self._rev(36)
        if self.w(s, a["idx"])["bdf"] > s["t"]:
            return self._rev(37)
        if a["idx"] < 1:
            return self._rev(41)
        e = self.w(s, a["idx"])
        if _nth(s["fsr"], a["idx"] - 1) != e["prev"]:
            return self._rev(14)
        if _nth(s["fsr"], a["idx"]) != 0:
            return self._rev(38)
        if s["lfi"] + 1 != a["idx"]:
            return self._rev(12)
        if e["n"] != 0 and s["qpend"] != e["tot"] - e["n"]:
            return self._rev(40)
        fsr = list(s["fsr"]) + [0] * (a["idx"] + 1 - len(s["fsr"]))
        fsr[a["idx"]] = e["post"]
        chs = list(s["chs"]) + [_empty_ch()] * (a["idx"] - len(s["chs"]))
        chs[a["idx"] - 1] = _empty_ch()
        self._ok(lfi=a["idx"], fsr=fsr,
                 qpend=e["tot"] if e["n"] != 0 else s["qpend"],
                 win=s["win"][1:], chs=chs)

    def setPause(self, a):
        s = self.s
        if a["who"] != OWNER:
            return self._rev(23)
        if a["status"] and s["paused"]:
            return self._rev(3)
        if not a["status"] and not s["paused"]:
            return self._rev(39)
        chs = list(s["chs"])
        if a["status"] and s["inch"]:
            while len(chs) <= s["bc"]:
                chs.append(_empty_ch())
            chs[s["bc"]] = _empty_ch()
        self._ok(paused=a["status"], chs=chs,
                 inch=s["inch"] and not a["status"])

    def sendMessage(self, a):
        self._ok(enq=self.s["enq"] + [self.s["t"]], qlen=self.s["qlen"] + 1)

    def wait(self, a):
        self._ok(t=self.s["t"] + a["dt"])

    def step(self, act):
        return getattr(self, act["op"])(act)


# ---------------------------------------------------------------------------
# Search-policy parameter domain (mirrors holon/js/policy_lib.mjs policyOf:
# the untrusted candidate-action generator that enumerates the domains).
def policy(s):
    lci = s["lfi"] + len(s["win"]) - 1
    last = s["win"][-1] if s["win"] else {}
    fresh = 100 + 10 * (lci + 1) + (len(s["log"]) % 7)
    blob = 7 + 10 * (lci + 1)
    room = max(0, s["qlen"] - last.get("tot", 0))
    ns = [0, 1] if room > 0 else [0]
    out = []
    for ver in (1, 2, 0):
        for n in ns:
            blobs_list = [[blob]] if ver == 2 else [[blob], [], [Z]]
            for blobs in blobs_list:
                out.append({"op": "commitBatch", "who": 2, "ver": ver,
                            "parent": lci, "n": n, "lbn": lci + 1,
                            "prev": last.get("csr", 0), "post": fresh,
                            "blobs": blobs})
    for ver in (1, 2):
        out.append({"op": "commitState", "who": 2, "ver": ver, "parent": lci,
                    "n": 0, "lbn": lci + 1, "prev": last.get("csr", 0),
                    "post": fresh, "blobs": []})
    for n in ns:
        out.append({"op": "commitBatchWithProof", "who": 5, "ver": 1,
                    "parent": lci, "n": n, "lbn": lci + 1,
                    "prev": last.get("csr", 0), "post": fresh,
                    "blobs": [blob], "proof": 1})
    if lci > s["lfi"]:
        out.append({"op": "revertBatch", "who": 1, "idx": lci, "count": 1})
    if lci > s["lfi"] + 1:
        out.append({"op": "revertBatch", "who": 1, "idx": s["lfi"] + 1,
                    "count": lci - s["lfi"]})
    for idx in {lci, s["lfi"] + 1}:
        if s["lfi"] < idx <= lci:
            out.append({"op": "challengeState", "who": 4, "idx": idx,
                        "value": 1})
    out.append({"op": "proveState", "who": 2, "idx": s["bc"], "proof": 1})
    out.append({"op": "finalizeBatch", "who": 5, "idx": s["lfi"] + 1})
    out.append({"op": "setPause", "who": 1, "status": not s["paused"]})
    out.append({"op": "sendMessage", "who": 5})
    dts = {1, s["W"], s["W"] + 1, s["F"], s["D"] + 1}
    for e in s["win"]:
        if e["bdf"] >= s["t"]:
            dts.add(e["bdf"] - s["t"])
            dts.add(e["bdf"] - s["t"] + 1)
    ch = s["chs"][s["bc"]] if s["bc"] < len(s["chs"]) else None
    if ch and s["inch"]:
        for d in (ch["s"] + s["W"] - s["t"], ch["s"] + s["W"] - s["t"] + 1):
            if d > 0:
                dts.add(d)
    if s["qpend"] < s["qlen"]:
        d = s["enq"][s["qpend"]] + s["D"] + 1 - s["t"]
        if d > 0:
            dts.add(d)
    dts.discard(0)
    for dt in sorted(dts):
        out.append({"op": "wait", "dt": dt})
    return out


def _norm(v):
    """Decoded machine values -> plain python for comparison."""
    if isinstance(v, list):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items() if k != "$"}
    return v


def _state_key(s):
    return repr(sorted((k, repr(v)) for k, v in s.items() if k != "log"))


class TestM1Oracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cm = CompiledMachine.build(FACTS)

    def _machine_steps(self, pairs):
        calls = []
        for act, mstate in pairs:
            mact = {"$": "A_" + act["op"],
                    **{k: v for k, v in act.items() if k != "op"}}
            calls.append({"fn": "step",
                          "args": [{"val": mact}, {"val": mstate}]})
        out = []
        for res in self.cm.calls(calls):
            if isinstance(res, dict) and "error" in res:
                raise AssertionError(f"machine step error: {res['error']}")
            out.append(res)
        return out

    def _check_step(self, node, act, where, m_next=None):
        if m_next is None:
            m_next = self._machine_steps([(act, node["m"])])[0]
        o = Oracle.__new__(Oracle)
        o.s = {k: (list(v) if isinstance(v, list) else v)
               for k, v in node["o"].items()}
        o.s = {k: [dict(x) if isinstance(x, dict) else x for x in v]
               if isinstance(v, list) else v for k, v in node["o"].items()}
        o.step(act)
        if _norm(o.s) != _norm(m_next):
            diff = {k for k in o.s if _norm(o.s[k]) != _norm(m_next.get(k))}
            raise AssertionError(
                f"oracle/machine disagree at {where} after {act}\n"
                f"fields: {sorted(diff)}\n"
                f"oracle: {sorted((k, o.s[k]) for k in diff)}\n"
                f"machine: {sorted((k, m_next.get(k)) for k in diff)}")
        return {"m": m_next, "o": o.s, "trace": node["trace"] + [act]}

    def _s0(self):
        m0 = self.cm.calls([{"fn": "s0", "args": []}])[0]
        o = Oracle()
        return {"m": m0, "o": o.s, "trace": []}

    def test_oracle_initial_state(self):
        n = self._s0()
        self.assertEqual(_norm(n["o"]), _norm(n["m"]),
                         "oracle initial state != machine s0")

    def test_oracle_exhaustive_and_random(self):
        root = self._s0()
        seen = {_state_key(root["o"])}
        frontier, traced = [root], 1
        depth = 0
        MAX = 20000
        while frontier and depth < 3:
            edges = []
            for node in frontier:
                for act in policy(node["o"]):
                    edges.append((node, act))
            results = self._machine_steps([(a, n["m"]) for n, a in edges])
            nxt = []
            for (node, act), m_next in zip(edges, results):
                child = self._check_step(node, act,
                                         f"depth {depth + 1} trace "
                                         f"{[a['op'] for a in node['trace']]}",
                                         m_next)
                k = _state_key(child["o"])
                if k not in seen:
                    seen.add(k)
                    nxt.append(child)
                    traced += 1
            if traced > MAX and depth < 2:
                break
            frontier, depth = nxt, depth + 1
        print(f"oracle BFS: {traced} distinct traces/states checked to depth {depth}")

        rng = random.Random(20251011)
        nodes = [self._s0() for _ in range(300)]
        acts_seq = []
        lens = [rng.randint(1, 12) for _ in range(300)]
        for step_i in range(max(lens)):
            live = [(i, n) for i, n in enumerate(nodes) if step_i < lens[i]]
            pairs = []
            for i, n in live:
                acts = policy(n["o"])
                a = rng.choice(acts)
                acts_seq.append((i, a))
                pairs.append((a, n["m"]))
            for (i, a), m_next in zip(acts_seq[-len(live):],
                                      self._machine_steps(pairs)):
                nodes[i] = self._check_step(nodes[i], a,
                                            f"random trace {i}", m_next)
        print("oracle random: 300 fixed-seed traces checked")


if __name__ == "__main__":
    unittest.main()
