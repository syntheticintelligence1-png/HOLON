"""I19 follow-up (lead-directed audit A19; docs/iterations/I19.md "Follow-up: lead-directed audit (A19)").

Not preregistered. These tests pin the follow-up's additive extensions of the I19 transitions document (the module
docstring of holon/frontends/solidity/transitions.py and spec/schemas/facts_0_3.schema.json are their contract), of
the Go frontend (go.globals and the hex_to_array primitive kind: holon/frontends/go/extract.py) and of the linker
(holon/frontends/link.py), on planted fixtures whose extraction is known by construction
(tests_m2/fixtures/i19_followup/: ledger, probe, go_globals) and on the committed Morph documents.

  A19-01 writes, mstores, post             A19-02 checks, panics, calls, payable
  A19-03 guards[].reaches, order          A19-04/06/07/08 loop records, closed forms, counts, cost terms
  A19-05 short-circuit context            A19-09 events
  A19-10/15 inherited storage, field slots A19-11/12 inherited actions, params, returns, mutability
  A19-13 go.globals                        A19-14/16 term simplification, signed operators, closed tag grammar
  A19-17 try, new, Yul switch/functions, revert-style principals, constant reasons
  A19-18 fixture coverage, determinism, audit-hook reads, poisoned fact documents
  A19-19 link role validation

Round 2 (the verifier's findings V19-02..V19-05, fixture tests_m2/fixtures/i19_followup/round2):
  V19-02 booleans: conditions rendered by truthiness, the ite rules, bool leaves and cleanup, unchanged post families
  V19-03 revert data: guards[].error and args (custom errors and Error(string))
  V19-04 event topics                      V19-05 Panic 0x41 of a memory allocation, the calldata head check

The preregistered I19 tests (tests_m2/test_extract_transitions.py, tests_m2/test_coverage.py) are unchanged.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i17 as H17
from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon

FIX = ROOT / "tests_m2" / "fixtures" / "i19_followup"
LEDGER, PROBE, GOG, ROUND2 = FIX / "ledger", FIX / "probe", FIX / "go_globals", FIX / "round2"
MORPH = ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json"
GENESIS = ROOT / "spec" / "M2" / "facts" / "morph_genesis.go.extracted.json"
SIDE = ROOT / "spec" / "M2" / "lib" / "extract_rollup.json"
R = "contracts/contracts/l1/rollup/Rollup.sol"
PAUSABLE = "@openzeppelin/contracts-upgradeable/security/PausableUpgradeable.sol"

_CACHE: dict = {}


def extract(fixture: Path, sidecar: str) -> dict:
    """The fixture's transitions document (python -m holon extract solidity, cached per module run)."""
    key = str(fixture)
    if key not in _CACHE:
        tmp = Path(tempfile.mkdtemp(prefix="holon-a19-"))
        try:
            out = tmp / "doc.json"
            p = run_holon(["extract", "solidity", "--sidecar", str(fixture / sidecar), "--source", str(fixture),
                           "--out", str(out)], timeout=600)
            if p.returncode != 0:
                raise AssertionError(p.stdout[-1500:] + p.stderr[-1500:])
            _CACHE[key] = (json.loads(out.read_text()), out.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return _CACHE[key][0]


def ledger() -> dict:
    return extract(LEDGER, "extract_ledger.json")


def probe() -> dict:
    return extract(PROBE, "extract_probe.json")


def round2() -> dict:
    return extract(ROUND2, "extract_round2.json")


def morph() -> dict:
    if "morph" not in _CACHE:
        if not MORPH.is_file():
            raise AssertionError(f"{MORPH.relative_to(ROOT)} is missing")
        _CACHE["morph"] = load_json(MORPH)
    return _CACHE["morph"]


def act(d: dict, name: str) -> dict:
    hits = [a for a in d["actions"] if a["name"] == name]
    if len(hits) != 1:
        raise AssertionError(f"action {name}: {len(hits)} entries")
    return hits[0]


def line(fixture: Path, unit: str, text: str, nth: int = 1) -> str:
    """'<unit>:<line>' of the nth line of the fixture unit holding text."""
    k = 0
    for i, ln in enumerate((fixture / unit).read_text().splitlines(), 1):
        if text in ln:
            k += 1
            if k == nth:
                return f"{unit}:{i}"
    raise AssertionError(f"{unit} has no line with {text!r}")


def contains(t, sub) -> bool:
    if t == sub:
        return True
    return isinstance(t, list) and any(contains(x, sub) for x in t)


def tags(t, out: set) -> set:
    """Every term tag of a rendered term (struct members, pointer stacks and store paths are not terms)."""
    if isinstance(t, list) and t and isinstance(t[0], str):
        h = t[0]
        out.add(h)
        if h == "struct":
            for _m, v in t[2]:
                tags(v, out)
        elif h == "ptr":
            tags(t[2], out)
        elif h == "store":
            tags(t[1], out)
            for _k, x in t[2]:
                tags(x, out)
            tags(t[3], out)
        elif h == "mloop":
            tags(t[2], out)
            tags(t[3], out)
            for w in t[4]:
                tags(w, out)
        else:
            for x in t[1:]:
                if isinstance(x, list):
                    tags(x, out)
    elif isinstance(t, list):
        for x in t:
            tags(x, out)
    return out


TERM_KEYS = ("expr", "predicate", "iters", "args", "receiver", "value", "cond", "offset", "head", "break", "count",
             "bound", "entry", "returns", "topics")
# the closed tag grammar of the transitions terms (holon/frontends/solidity/transitions.py docstring, "Terms")
GRAMMAR = {
    "param", "caller", "storage", "map", "index", "member", "len", "byte", "word", "call", "at", "callok", "caught",
    "new", "alloc", "env", "this", "code", "balance", "codehash", "immutable", "blobhash", "blockhash", "sload", "str",
    "slot", "keccak256", "sha256", "slice", "mem", "mstore", "mstore8", "calldatacopy", "when", "mloop", "loop",
    "unknown", "mload", "ptr", "store", "?", "carried", "iter", "count", "exit", "returned", "sum", "struct", "tuple",
    "array", "update", "push", "pop", "input", "range", "cdoff", "calldataload", "calldata", "revertdata", "decl",
    "type", "global", "enum", "constant", "ref", "value", "!", "&&", "||", "==", "!=", "<", "<=", ">", ">=", "+", "-",
    "*", "/", "%", "&", "|", "^", "<<", ">>", "~", "neg", "**", "trunc", "sext", "s<", "s<=", "s>", "s>=", "sdiv",
    "smod", "sar", "addmod", "mulmod", "wbyte", "signextend", "fits", "sfits", "abi.encode", "abi.encodePacked",
    "abi.encodeWithSelector", "abi.encodeWithSignature", "abi.encodeCall", "abi.decode", "bytes.concat",
    "string.concat", "ripemd160", "ecrecover", "abi.inplace"}


def doc_tags(d: dict) -> set:
    out: set = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in TERM_KEYS:
                    tags(v, out)
                elif k == "post":
                    for v2 in v.values():
                        tags(v2, out)
                elif k == "path":
                    for _k, v2 in v:
                        tags(v2, out)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    for a in d["actions"]:
        walk(a)
    return out


# ================================================================================================ A19-01
class TestPost(unittest.TestCase):
    def test_ledger_commit_writes_values_and_post_state(self):
        c = act(ledger(), "commit")
        last1 = ["+", ["storage", "last"], 1]
        self.assertEqual(c["post"]["last"], last1)
        self.assertEqual(c["post"]["total"], ["+", ["storage", "total"], ["param", "n"]])
        h = c["post"]["hashes"]
        self.assertEqual(h[:3], ["store", ["storage", "hashes"], [["map", last1]]])
        self.assertEqual(h[3][0], "keccak256")
        self.assertEqual(c["post"]["entries"][3],
                         ["struct", "Entry", [["idx", ["param", "lbn"]], ["who", ["caller"]], ["amount", ["param", "n"]],
                                              ["done", 0]]])
        self.assertEqual([(w["family"], w["cond"]) for w in c["writes"]],
                         [("hashes", 1), ("entries", 1), ("total", 1), ("last", 1)])
        self.assertEqual([w["seq"] for w in c["writes"]], sorted(w["seq"] for w in c["writes"]))
        m0 = [m for m in c["mstores"] if m["offset"] == 0]
        self.assertEqual([(m["op"], m["value"]) for m in m0], [("mstore", ["<<", ["param", "lbn"], 192])])
        # effects are derived from writes
        self.assertEqual(sorted((e["family"], e["src"]) for e in c["effects"]),
                         sorted({(w["family"], w["src"]) for w in c["writes"]}))

    def test_morph_post_states(self):
        self.assertEqual(sorted(act(morph(), "commitBatch")["post"]),
                         ["batchBlobVersionedHashes", "batchDataStore", "committedBatches", "committedStateRoots",
                          "lastCommittedBatchIndex"])
        idx = [">>", ["word", ["param", "_batchHeader"], 1], 192]
        post = act(morph(), "finalizeBatch")["post"]
        self.assertEqual(post["finalizedStateRoots"],
                         ["store", ["storage", "finalizedStateRoots"], [["map", idx]], ["word", ["param", "_batchHeader"], 121]])
        self.assertEqual(post["withdrawalRoots"],
                         ["store", ["storage", "withdrawalRoots"], [["map", ["word", ["param", "_batchHeader"], 153]]], 1])
        self.assertEqual(post["lastFinalizedBatchIndex"], idx)
        for fam in ("batchDataStore", "committedStateRoots", "batchBlobVersionedHashes", "challenges"):
            with self.subTest(family=fam):
                self.assertEqual(post[fam], ["store", ["storage", fam], [["map", ["-", idx, 1]]], 0])


# ================================================================================================ A19-02
class TestPanics(unittest.TestCase):
    def test_checked_arithmetic_division_and_unchecked(self):
        c = act(ledger(), "commit")
        exprs = [p["expr"] for p in c["panics"] if p["code"] == 17]
        self.assertIn(["fits", 256, ["+", ["storage", "last"], 1]], exprs)
        span = c["loops"][0]["src"]
        inloop = [p for p in c["panics"] if p.get("loop") == c["loops"][0]["seq"] and p["op"] == "+"]
        self.assertTrue(any(contains(p["expr"], ["fits", 256, ["+", ["storage", "total"], ["iter", span]]])
                            for p in inloop), inloop)
        s = act(ledger(), "share")
        self.assertEqual([(p["code"], p["expr"]) for p in s["panics"] if p["code"] == 18],
                         [(18, ["!=", ["param", "b"], 0]), (18, ["!=", ["param", "b"], 0])])
        self.assertEqual(act(ledger(), "bump")["panics"], [])

    def test_calls_callvalue_and_abi_checks(self):
        pv = act(ledger(), "prove")
        self.assertEqual(pv["calls"][0]["expr"][:3], ["callok", "ICommit.verify", ["storage", "verifier"]])
        self.assertTrue(pv["calls"][0]["commit"])
        c = act(ledger(), "commit")
        self.assertFalse(c["payable"])
        self.assertEqual(c["checks"][0]["kind"], "callvalue")
        self.assertEqual(c["checks"][0]["expr"], ["==", ["env", "msg.value"], 0])
        self.assertIn({"kind": "abi", "param": "lbn", "expr": ["<", ["param", "lbn"], 1 << 64]},
                      [{k: x[k] for k in ("kind", "param", "expr")} for x in c["checks"] if x["kind"] == "abi"])
        self.assertEqual(c["order"][:2], [["check", 0], ["check", 1]])

    def test_probe_enum_pop_assert_and_struct_checks(self):
        p = probe()
        self.assertEqual([(x["code"], x["expr"]) for x in act(p, "mode")["panics"]], [(33, ["<", ["param", "a"], 2])])
        self.assertEqual([(x["code"], x["expr"]) for x in act(p, "popit")["panics"]],
                         [(49, ["!=", ["len", ["storage", "stack"]], 0])])
        g = act(p, "chk")["guards"]
        self.assertEqual([r.get("code") for r in g[0]["reaches"]], [1])
        mem = [x["expr"] for x in act(p, "mem")["checks"] if x["kind"] == "abi"]
        self.assertEqual(mem, [["<", ["member", ["param", "s"], "lo"], 1 << 64],
                               ["<", ["member", ["param", "s"], "who"], 1 << 160]])
        cd = [x for x in act(p, "cd")["checks"] if x["kind"] == "abi"]
        self.assertEqual([x["expr"] for x in cd], [["<", ["member", ["param", "s"], "lo"], 1 << 64]])
        self.assertEqual(cd[0]["src"], line(PROBE, "src/Probe.sol", "return s.lo;", 2))

    def test_morph_implicit_reverts(self):
        f = act(morph(), "finalizeBatch")
        p636 = [p for p in f["panics"] if p["src"] == f"{R}:636"]
        self.assertEqual([(p["code"], p["args"]) for p in p636],
                         [(17, [[">>", ["word", ["param", "_batchHeader"], 1], 192], 1])])
        c = act(morph(), "commitBatch")
        p363 = [p for p in c["panics"] if p["src"] == f"{R}:363"]
        self.assertEqual(len(p363), 2)
        for p in p363:
            self.assertTrue(contains(p["expr"], ["storage", "inChallenge"]), p)
        self.assertIn(f"{R}:439", [p["src"] for p in act(morph(), "revertBatch")["panics"]])
        self.assertTrue(c["payable"])
        self.assertNotIn("callvalue", [x["kind"] for x in c["checks"]])
        self.assertEqual(act(morph(), "finalizeBatch")["checks"][0]["kind"], "callvalue")
        oracle = [x for x in act(morph(), "proveState")["calls"] if x["fn"] == "IRollupVerifier.verifyAggregateProof"]
        self.assertEqual(len(oracle), 1)
        self.assertTrue(oracle[0]["commit"])
        self.assertTrue(contains(oracle[0]["expr"], "callok") and
                        contains(oracle[0]["expr"], "IRollupVerifier.verifyAggregateProof"), oracle[0]["expr"])


# ================================================================================================ A19-03
class TestReaches(unittest.TestCase):
    def test_ledger_pair_has_two_reaches(self):
        g = act(ledger(), "pair")["guards"]
        self.assertEqual(len(g), 1)
        rs = g[0]["reaches"]
        self.assertEqual([r["stack"] for r in rs], [[line(LEDGER, "src/Ledger.sol", "_check2(a);")],
                                                    [line(LEDGER, "src/Ledger.sol", "_check2(b);")]])
        self.assertEqual([r["expr"] for r in rs], [[">", ["len", ["param", "a"]], 0], [">", ["len", ["param", "b"]], 0]])

    def test_first_reach_is_the_entry_and_order_lists_every_reach(self):
        for d in (ledger(), probe(), morph()):
            for a in d["actions"]:
                n = 0
                for g in a["guards"]:
                    with self.subTest(action=a["name"], guard=g["src"]):
                        self.assertEqual(g["reaches"][0]["expr"], g["expr"])
                    n += len(g["reaches"])
                self.assertEqual(sum(1 for o in a["order"] if o[0] == "guard"), n)
                seqs = []
                for o in a["order"]:
                    if o[0] == "guard":
                        seqs.append([g for g in a["guards"] if g["src"] == o[1]][0]["reaches"][o[2]]["seq"])
                    else:
                        seqs.append(a[{"check": "checks", "panic": "panics", "call": "calls", "loop": "loops"}[o[0]]]
                                    [o[1]]["seq"])
                self.assertEqual(seqs, sorted(seqs), a["name"])

    def test_morph_second_header_and_modifier_stacks(self):
        g = [x for x in act(morph(), "commitBatchWithProof")["guards"] if x["src"] == f"{R}:825"][0]
        second = [r for r in g["reaches"] if r["stack"][:1] == [f"{R}:414"]]
        self.assertEqual([r["expr"] for r in second], [[">", ["len", ["param", "_batchHeader"]], 0]])
        g77 = [x for x in act(morph(), "setPause")["guards"] if x["src"] == f"{PAUSABLE}:77"][0]
        self.assertTrue(any(f"{PAUSABLE}:94" in r["stack"] for r in g77["reaches"]), g77["reaches"])


# ================================================================================================ A19-05
class TestShortCircuit(unittest.TestCase):
    def test_right_operands_run_under_the_left_condition(self):
        self.assertEqual(act(ledger(), "sc")["guards"][0]["expr"],
                         ["||", ["!", [">", ["param", "a"], 0]], [">", ["param", "b"], 1]])
        self.assertEqual(act(probe(), "orw")["post"]["z"], ["?", ["!", ["param", "c"]], 3, ["storage", "z"]])


# ================================================================================================ A19-04/06/07/08
class TestLoops(unittest.TestCase):
    def test_yul_for_with_break(self):
        a = act(ledger(), "count")
        lp = a["loops"][0]
        span = lp["src"]
        self.assertEqual(lp["kind"], "yulfor")
        self.assertEqual(lp["carried"], [{"name": "i", "entry": 0, "value": ["iter", span]}])
        self.assertEqual(lp["break"], ["==", ["blobhash", ["iter", span]], 0])
        self.assertEqual(lp["count"], ["count", span])
        self.assertEqual(a["cost"]["terms"], [{"loop": span, "iters": ["count", span]}])
        self.assertIn({"kind": "COMMIT", "fn": "blobhash", "src": line(LEDGER, "src/Ledger.sol", "blobhash(i)")},
                      a["edges"])
        self.assertEqual(a["guards"][0]["expr"], [">", ["count", span], 0])

    def test_counted_loop_closed_forms_and_mloop(self):
        c = act(ledger(), "commit")
        lp = c["loops"][0]
        span = lp["src"]
        ex = {e["name"]: e["value"] for e in lp["exit"]}
        self.assertEqual(ex["p"][2], ["+", 8, ["*", 32, ["param", "n"]]])
        self.assertEqual(ex["i"], ["param", "n"])
        writes = lp["regions"][0]["writes"]
        self.assertEqual(writes, [["mstore", ["+", 8, ["*", 32, ["iter", span]]],
                                   ["call", "IQ.msgHash", ["+", ["storage", "total"], ["iter", span]]]]])
        h = c["post"]["hashes"][3]
        self.assertTrue(contains(h, ["mloop", span, ["iter", span], ["param", "n"], writes]), h)
        self.assertTrue(contains(h, ["+", 8, ["*", 32, ["param", "n"]]]), h)

    def test_storage_loop_carries_families_with_events_and_panics(self):
        u = act(ledger(), "undo")
        lp = u["loops"][0]
        names = [e["name"] for e in lp["carried"]]
        self.assertIn(["storage", "hashes"], names)
        self.assertIn(["storage", "total"], names)
        self.assertEqual([e["loop"] for e in u["events"]], [lp["seq"]])
        self.assertTrue(any(p.get("loop") == lp["seq"] for p in u["panics"]))
        self.assertEqual(u["post"]["hashes"], ["exit", lp["src"], ["storage", "hashes"]])
        self.assertEqual(u["cost"]["terms"], [])

    def test_fixpoint_closed_forms_and_counts(self):
        p = probe()
        pre = act(p, "pre")
        self.assertEqual(pre["returns"], ["+", 100, ["param", "n"]])
        drys = act(p, "drys")
        self.assertEqual(drys["cost"]["terms"], [])
        self.assertTrue(contains(drys["guards"][-1]["expr"], ["exit", drys["loops"][0]["src"], ["storage", "x"]]))
        dry = act(p, "dry")["loops"][0]
        self.assertIn("y", [e["name"] for e in dry["carried"]])
        self.assertEqual([e["value"][0] for e in dry["next"] if e["name"] == "y"], ["?"])
        brk = act(p, "brk")["loops"][0]
        self.assertIn({"name": "y", "value": 9}, brk["at_break"])
        self.assertEqual(act(p, "yiv")["cost"]["terms"][0]["iters"], ["/", ["+", ["param", "n"], 1], 2])
        yb = act(p, "ybound")["cost"]["terms"][0]
        self.assertEqual(yb["iters"], ["count", yb["loop"]])
        self.assertEqual(act(p, "lc")["cost"]["terms"][0]["iters"], ["?", ["param", "go"], ["param", "n"], 0])
        self.assertEqual(act(p, "nest")["returns"], ["*", ["param", "m"], ["param", "n"]])
        ret = act(p, "ret")
        span = ret["loops"][0]["src"]
        self.assertEqual(ret["returns"], ["?", ["returned", span, 0], 42, 1])
        self.assertEqual(ret["loops"][0]["count"], ["count", span])

    def test_cost_sums_reaches(self):
        self.assertEqual(act(ledger(), "twice")["cost"]["terms"][0]["iters"], ["+", ["param", "n1"], ["param", "n2"]])

    def test_morph_loops(self):
        cwp = act(morph(), "commitBatchWithProof")
        g418 = [g for g in cwp["guards"] if g["src"] == f"{R}:418"][0]
        txt = json.dumps(g418["expr"])
        self.assertNotIn('"unknown"', txt)
        self.assertNotIn('"phi"', txt)
        self.assertIn('"mloop"', txt)
        g913 = [g for g in cwp["guards"] if g["src"] == f"{R}:913"][0]
        self.assertTrue(contains(g913["expr"], ["count", f"{R}:901-908"]), g913)
        for name in ("commitBatch", "commitBatchWithProof"):
            with self.subTest(action=name):
                a = act(morph(), name)
                self.assertEqual([t["loop"] for t in a["cost"]["terms"]], [f"{R}:901-908", f"{R}:936-943"])
                self.assertIn({"kind": "COMMIT", "fn": "blobhash", "src": f"{R}:902"}, a["edges"])
                lp = [x for x in a["loops"] if x["src"] == f"{R}:936-943"][0]
                ptr = [e for e in lp["exit"] if e["name"] == "_ptr"][0]["value"]
                self.assertEqual(ptr[2], ["+", 10, ["*", 32, ["member", ["param", "batchDataInput"], "numL1Messages"]]])
        self.assertEqual(act(morph(), "finalizeBatch")["cost"]["terms"][0]["iters"],
                         ["/", ["+", [">>", ["word", ["param", "_batchHeader"], 9], 192], 255], 256])


# ================================================================================================ A19-09
class TestEvents(unittest.TestCase):
    def test_ledger_event(self):
        from holon.keccak import keccak256
        e = act(ledger(), "commit")["events"]
        self.assertEqual(len(e), 1)
        self.assertEqual((e[0]["event"], e[0]["signature"], e[0]["indexed"], e[0]["anonymous"]),
                         ("Ledger.Committed", "Committed(uint256,bytes32)", [True, False], False))
        self.assertEqual(e[0]["topic0"], "0x" + keccak256(b"Committed(uint256,bytes32)").hex())
        self.assertEqual(e[0]["args"][0], ["+", ["storage", "last"], 1])
        self.assertEqual(e[0]["args"][1][0], "keccak256")
        t = act(ledger(), "transferOwnership")["events"]
        self.assertEqual([(x["event"], x["indexed"]) for x in t], [("Owned.OwnerSet", [True, True])])

    def test_morph_events(self):
        self.assertIn((f"{R}:376", "IRollup.CommitBatch"),
                      [(e["src"], e["event"]) for e in act(morph(), "commitBatch")["events"]])
        self.assertEqual([e["src"].rsplit("/", 1)[-1] for e in act(morph(), "setPause")["events"]],
                         ["PausableUpgradeable.sol:96", "Rollup.sol:583", "PausableUpgradeable.sol:108",
                          "Rollup.sol:586"])
        cov = load_json(ROOT / "gen" / "M2" / "coverage.json")
        kinds = {(d["kind"], d["detail"]) for doc in cov["documents"] for d in doc["debt"]}
        self.assertNotIn(("unsupported", "EmitStatement"), kinds)
        self.assertNotIn(("unsupported", "YulForLoop"), kinds)


# ================================================================================================ A19-10/15
class TestStorage(unittest.TestCase):
    def test_ledger_inherited_storage_and_field_slots(self):
        d = ledger()
        self.assertEqual([(s["name"], s["slot"], s["offset"], s["width"], s["declared_in"]) for s in d["inherited_storage"]],
                         [("_owner", 0, 0, 160, "Owned"), ("_stopped", 0, 20, 8, "Owned")])
        ent = [s for s in d["storage"] if s["name"] == "entries"][0]
        self.assertEqual([(f["name"], f["slot"], f["offset"]) for f in ent["fields"]],
                         [("idx", 0, 0), ("who", 0, 8), ("amount", 1, 0), ("done", 2, 0)])

    def test_morph_inherited_storage_and_packing(self):
        d = morph()
        inh = {(s["name"], s["slot"], s["offset"], s.get("width")) for s in d["inherited_storage"]}
        for want in (("_initialized", 0, 0, 8), ("_initializing", 0, 1, 8), ("_owner", 51, 0, 160),
                     ("_paused", 101, 0, 8)):
            with self.subTest(var=want[0]):
                self.assertIn(want, inh)
        ch = [s for s in d["storage"] if s["name"] == "challenges"][0]
        self.assertEqual([f["offset"] for f in ch["fields"]], [0, 8, 0, 0, 0, 1])
        self.assertEqual([f["slot"] for f in ch["fields"]], [0, 0, 1, 2, 3, 3])


# ================================================================================================ A19-11/12
class TestActions(unittest.TestCase):
    def test_ledger_interface(self):
        d = ledger()
        self.assertEqual((act(d, "owner")["declared_in"], act(d, "transferOwnership")["declared_in"]), ("Owned", "Owned"))
        self.assertEqual(act(d, "owner")["returns"], ["storage", "_owner"])
        self.assertEqual(act(d, "commit")["declared_in"], "Ledger")
        self.assertEqual([(p["name"], p["type"], p["width"]) for p in act(d, "commit")["params"]],
                         [("n", "uint256", 256), ("lbn", "uint64", 64)])
        self.assertEqual(act(d, "share")["returns"],
                         ["+", ["/", ["param", "a"], ["param", "b"]], ["%", ["storage", "total"], ["param", "b"]]])
        self.assertEqual((act(d, "getLast")["mutability"], act(d, "getLast")["payable"]), ("view", False))
        self.assertIsNone(act(d, "undo")["returns"])

    def test_morph_interface(self):
        d = morph()
        names = [a["name"] for a in d["actions"]]
        for n in ("owner", "paused", "renounceOwnership", "transferOwnership"):
            self.assertIn(n, names)
        self.assertEqual(len(names), 33)
        cs = act(d, "challengeState")
        self.assertEqual([(p["name"], p["width"]) for p in cs["params"]][0], ("batchIndex", 64))
        cb = act(d, "commitBatch")["params"][0]
        self.assertEqual([f["width"] for f in cb["fields"]], [8, None, 64, 16, 256, 256, 256])
        self.assertEqual(act(d, "isBatchFinalized")["returns"],
                         ["<=", ["param", "_batchIndex"], ["storage", "lastFinalizedBatchIndex"]])


# ================================================================================================ A19-14/16
class TestTerms(unittest.TestCase):
    def test_closed_tag_grammar(self):
        for name, d in (("ledger", ledger()), ("probe", probe()), ("round2", round2()), ("morph", morph())):
            with self.subTest(doc=name):
                t = doc_tags(d)
                self.assertEqual(sorted(t - GRAMMAR), [])
                self.assertNotIn("not", t)
                self.assertNotIn("phi", t)

    def test_header_writes_appear_once_in_the_commit_hash(self):
        g = [x for x in act(morph(), "commitBatchWithProof")["guards"] if x["src"] == f"{R}:418"][0]
        txt = json.dumps(g["expr"])
        self.assertEqual(txt.count('["mstore", 89, '), 1)
        self.assertEqual(txt.count('["mstore8", 0, '), 1)
        self.assertIn('"when"', txt)

    def test_signed_operators(self):
        sg = act(probe(), "sg")
        self.assertEqual(sg["returns"], ["tuple", ["s<", ["param", "a"], ["param", "b"]],
                                         ["sdiv", ["param", "a"], ["param", "b"]]])
        self.assertIn(["sfits", 256, ["sdiv", ["param", "a"], ["param", "b"]]], [p["expr"] for p in sg["panics"]])

    def test_the_schema_holds_the_follow_up_keys(self):
        from holon.schema import errors
        s = load_json(ROOT / "spec" / "schemas" / "facts_0_3.schema.json")
        for name, d in (("ledger", ledger()), ("probe", probe()), ("round2", round2()), ("morph", morph())):
            with self.subTest(doc=name):
                self.assertEqual(errors(d, s), [])
        bad = json.loads(json.dumps(ledger()))
        del act(bad, "commit")["guards"][0]["reaches"]
        self.assertNotEqual(errors(bad, s), [])


# ================================================================================================ A19-17
class TestConstructs(unittest.TestCase):
    def test_try_new_switch_principal_reason(self):
        p = probe()
        tr = act(p, "tr")
        ok = ["callok", "IE.f", ["storage", "ext"], ["param", "a"]]
        self.assertEqual([w["cond"] for w in tr["writes"]], [ok, ["!", ok]])
        self.assertEqual(tr["calls"][0].get("try"), True)
        self.assertEqual(tr["calls"][0]["expr"], 1)
        mk = act(p, "mk")
        self.assertEqual(mk["returns"], ["new", "Child"])
        self.assertEqual(mk["calls"][0]["fn"], "new Child")
        self.assertEqual(act(p, "ysw")["returns"],
                         ["?", ["==", ["param", "a"], 0], 1,
                          ["?", [">", ["param", "a"], 100], ["param", "a"], ["*", ["param", "a"], 2]]])
        ad = act(p, "admin")
        self.assertEqual(ad["principal"], {"modifier": "onlyAdmin",
                                           "predicate": ["!", ["!=", ["storage", "_admin"], ["caller"]]]})
        self.assertEqual([g["reason"] for g in ad["guards"]], ["NotAdmin", "too big"])

    def test_probe_coverage_has_no_construct_debt(self):
        cov = coverage(PROBE, "extract_probe.json")
        kinds = {(d["kind"], d["detail"]) for d in cov["debt"]}
        for nt in ("TryStatement", "YulSwitch", "YulFunctionDefinition", "YulForLoop", "EmitStatement", "FunctionCall"):
            self.assertNotIn(("unsupported", nt), kinds)


# ================================================================================================ A19-18
def coverage(fixture: Path, sidecar: str) -> dict:
    sol = holon_module("holon.frontends.solidity")
    side = sol.load_sidecar(fixture / sidecar)
    return sol.coverage_document(side, fixture / sidecar, ROOT, fixture)


class TestFixtureCoverageAndHonesty(unittest.TestCase):
    def test_fixture_coverage_is_known_by_construction(self):
        led = coverage(LEDGER, "extract_ledger.json")
        self.assertEqual((led["statements"], led["extracted"], led["unaccounted"]), (60, 59, []))
        self.assertEqual(sorted((d["kind"], d["detail"]) for d in led["debt"]),
                         [("external_call", "IQ.msgHash"), ("loop_storage_write", "hashes, total")])
        pr = coverage(PROBE, "extract_probe.json")
        self.assertEqual((pr["statements"], pr["unaccounted"]), (pr["extracted"] + 1, []))
        self.assertEqual(sorted((d["kind"], d["detail"]) for d in pr["debt"]),
                         [("external_call", "IE.f"), ("external_call", "new Child"), ("loop_storage_write", "x")])
        r2 = coverage(ROUND2, "extract_round2.json")
        self.assertEqual((r2["statements"], r2["extracted"], r2["unaccounted"], r2["debt"]), (35, 35, [], []))

    def test_two_runs_are_byte_identical(self):
        ledger()
        first = _CACHE[str(LEDGER)][1]
        tmp = Path(tempfile.mkdtemp(prefix="holon-a19-"))
        try:
            out = tmp / "again.json"
            p = run_holon(["extract", "solidity", "--sidecar", str(LEDGER / "extract_ledger.json"), "--source",
                           str(LEDGER), "--out", str(out)], timeout=600)
            self.assertEqual(p.returncode, 0, p.stderr[-1500:])
            self.assertEqual(out.read_bytes(), first)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_rollup_extraction_opens_only_the_frontend_inputs(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-a19-reads-"))
        try:
            code, opened, execs = H17.opened_during(["extract", "solidity", "--sidecar", str(SIDE), "--out",
                                                     str(tmp / "o.json")])
            self.assertEqual(code, 0, opened[-20:])
            root = os.path.realpath(ROOT) + os.sep
            inside = sorted({p[len(root):] for p, _ in opened if p.startswith(root)})
            allowed = ("holon/", "config/", "spec/schemas/", "spec/M2/lib/extract_rollup.json")
            self.assertEqual([p for p in inside if not p.startswith(allowed)], [])
            self.assertIn("spec/M2/lib/extract_rollup.json", inside)
            for argv in execs:
                self.assertEqual([a for a in argv if a.startswith(root) and not a[len(root):].startswith(allowed)], [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_poisoned_fact_documents_change_no_byte(self):
        repo = copy_repo()
        try:
            junk = '{"poisoned": "the extractor must not read this file"}\n'
            targets = sorted((repo / "facts").glob("*.json")) + sorted((repo / "spec" / "M1" / "facts").glob("*.json"))
            targets.append(repo / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
            for p in targets:
                p.write_text(junk)
            out = repo.parent / "o.json"
            p = run_holon(["extract", "solidity", "--sidecar", str(repo / "spec" / "M2" / "lib" / "extract_rollup.json"),
                           "--out", str(out)], cwd=repo, timeout=900)
            self.assertEqual(p.returncode, 0, p.stderr[-1500:])
            self.assertEqual(out.read_bytes(), MORPH.read_bytes())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ================================================================================================ A19-13
class TestGoGlobals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-a19-go-"))
        cls.proc = run_holon(["extract", "go", "--config", str(GOG / "config.json"), "--out-dir", str(cls.tmp)],
                             timeout=1200)
        p = cls.tmp / "toy_globals.go.extracted.json"
        cls.doc = json.loads(p.read_text()) if p.is_file() else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fixture_globals(self):
        self.assertIsNotNone(self.doc, self.proc.stdout[-1500:] + self.proc.stderr[-1500:])
        g = {x["global"].rsplit(".", 1)[-1]: x for x in self.doc["go"]["globals"]}
        self.assertEqual(sorted(g), ["Bad", "Count", "Long", "Magic", "Name", "Odd"])
        cells = lambda n: [c[1] if c[0] == "const" else c[0] for c in g[n]["cells"]]  # noqa: E731
        self.assertEqual(cells("Magic"), [0x00, 0xA1, 0xB2, 0xC3])
        self.assertEqual(cells("Odd"), [0x00, 0x00, 0x01, 0x23])
        self.assertEqual(cells("Long"), [0x02, 0x03, 0x04, 0x05])
        self.assertEqual(cells("Bad"), ["unknown"] * 4)
        self.assertEqual((g["Count"]["value"], g["Count"]["cells"]), (["const", 7], None))
        self.assertEqual(g["Name"]["value"], ["str", "abc"])
        self.assertEqual(g["Magic"]["value"], ["call", "toy.local/globals/hexlib.Parse", [["str", "0xa1b2c3"]]])
        self.assertIn("go-prim:toy.local/globals/hexlib.Parse", [a["id"] for a in self.doc["assumptions"]])

    def test_morph_genesis_records_the_initializer(self):
        d = load_json(GENESIS)
        hits = [x for x in d["go"]["globals"] if x["global"].endswith(".emptyBlobVersionedHash")]
        self.assertEqual(len(hits), 1)
        v = hits[0]["value"]
        self.assertEqual(v[0], "call")
        self.assertTrue(v[1].endswith(".HexToHash"))
        self.assertEqual(v[2], [["str", "0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014"]])
        self.assertEqual(len(hits[0]["cells"]), 32)


# ================================================================================================ A19-19
class TestLinkRobustness(unittest.TestCase):
    def test_a_malformed_role_is_refused_and_nothing_is_written(self):
        repo = copy_repo()
        try:
            side = repo / "spec" / "M2" / "lib" / "link.json"
            s = json.loads(side.read_text())
            del s["roles"]["zero_versioned_hash"]["go"]
            side.write_text(json.dumps(s))
            out = repo.parent / "link.json"
            p = run_holon(["link", "--milestone", "M2", "--out", str(out)], cwd=repo, timeout=600)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertFalse(out.exists())
            s["roles"]["zero_versioned_hash"]["go"] = {"document": "x.json", "global": "a", "constant": "b"}
            side.write_text(json.dumps(s))
            p = run_holon(["link", "--milestone", "M2", "--out", str(out)], cwd=repo, timeout=600)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertFalse(out.exists())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_the_global_reader(self):
        link = holon_module("holon.frontends.link")
        doc = {"go": {"globals": [
            {"global": "p/a.Z", "cells": [["const", 1], ["const", 255]], "value": ["x"]},
            {"global": "p/b.Z", "cells": [["const", 2]], "value": ["x"]},
            {"global": "p/b.W", "cells": [["byte", ["x"], 0]], "value": ["x"]}]}}
        self.assertEqual(link.global_value(doc, "p/a.Z"), "0x01ff")
        with self.assertRaises(link.LinkError):
            link.global_value(doc, "Z")
        self.assertIsNone(link.global_value(doc, "W"))
        self.assertIsNone(link.global_value(doc, "V"))


# ================================================================================================ round 2: V19-02
def keccak_hex(b: bytes, n: int = 32) -> str:
    from holon.keccak import keccak256
    return "0x" + keccak256(b)[:n].hex()


def r2_line(text: str, nth: int = 1) -> str:
    return line(ROUND2, "src/Round2.sol", text, nth)


class TestBooleans(unittest.TestCase):
    """V19-02. A bool read from storage is the raw byte at its offset (the compiler does not clean it on a read), so it
    is not a boolean term; a condition is rendered by its truthiness, the value-exact ite rules apply to any word, and
    the compiler's cleanup of bools (ABI encoding, storage stores, == and !=) is in the terms."""

    def test_ite_rules_and_condition_rendering(self):
        T = holon_module("holon.frontends.solidity.transitions")
        s, p = ("storage", "f"), ("<", ("param", "a"), 3)
        self.assertEqual(T.ite(("!", s), 0, s), s)                  # any word: where !s holds, s is 0
        self.assertEqual(T.ite(s, s, 0), s)                         # any word: where s fails, s is 0
        self.assertEqual(T.ite(("!", s), 1, s), ("?", ("!", s), 1, s))   # s may be 2: its value is not 1
        self.assertEqual(T.ite(("!", p), 1, p), 1)                  # a boolean p is 1 where it holds
        self.assertEqual(T.ite(p, 1, p), p)
        self.assertEqual(T.render(("?", ("!", s), 1, s), True), 1)  # as a condition it always holds
        self.assertEqual(T.render(("?", ("!", s), 1, s)), ["?", ["!", ["storage", "f"]], 1, ["storage", "f"]])
        self.assertEqual(T.render(("&&", s, ("?", s, ("<", s, 9), 0)), True), ["&&", ["storage", "f"],
                                                                              ["<", ["storage", "f"], 9]])

    def test_initializer_like_modifier(self):
        st = act(round2(), "setup")
        g = [x for x in st["guards"] if x["src"] == r2_line('require(_busy, "not inside");')][0]
        self.assertEqual((g["kind"], g["expr"], [r["expr"] for r in g["reaches"]]), ("modifier", 1, [1]))
        self.assertEqual(st["post"], {"_done": 1, "x": ["param", "a"]})      # _busy is restored: no post entry
        self.assertEqual([(w["family"], w["value"], w["cond"]) for w in st["writes"] if w["family"] == "_busy"],
                         [("_busy", 1, ["!", ["storage", "_busy"]]), ("_busy", 0, ["!", ["storage", "_busy"]])])

    def test_bool_cleanup_and_leaves(self):
        d = round2()
        flag = ["!=", ["storage", "flag"], 0]
        self.assertEqual(act(d, "copyFlag")["post"], {"copy": flag})
        self.assertEqual(act(d, "getFlag")["returns"], flag)
        self.assertEqual(act(d, "same")["returns"], ["==", flag, ["!=", ["storage", "copy"], 0]])
        self.assertEqual(act(d, "keep")["post"], {"copy": ["param", "f"]})   # a bool parameter is a boolean leaf

    def test_morph_initializer_and_pause(self):
        d = morph()
        ini = act(d, "initialize")
        g = [x for x in ini["guards"] if x["src"].endswith("Initializable.sol:133")][0]
        self.assertEqual([r["expr"] for r in g["reaches"]], [1, 1, 1, 1])
        self.assertNotIn("_initializing", ini["post"])
        self.assertEqual(act(d, "setPause")["post"]["_paused"], ["param", "_status"])
        self.assertEqual(act(d, "paused")["returns"], ["!=", ["storage", "_paused"], 0])
        for a in d["actions"]:
            for fam, v in a["post"].items():
                with self.subTest(action=a["name"], family=fam):
                    self.assertNotEqual(v, ["storage", fam])


# ================================================================================================ round 2: V19-03
class TestRevertData(unittest.TestCase):
    def test_custom_errors_and_strings(self):
        d = round2()
        bad = act(d, "fail")["guards"][0]
        sig = "Bad(uint256,string,address)"
        self.assertEqual(bad["error"], {"name": "Round2.Bad", "signature": sig, "selector": keccak_hex(sig.encode(), 4)})
        self.assertEqual(bad["args"], [["param", "c"], ["str", b"too big".hex()], ["caller"]])   # parameter order
        self.assertEqual(bad["reaches"][0]["args"], bad["args"])
        st = act(d, "setup")["guards"]
        once = [g for g in st if g["src"] == r2_line("revert AlreadyDone(_done, _busy);")][0]
        self.assertEqual((once["error"]["name"], once["error"]["signature"]), ("Init.AlreadyDone", "AlreadyDone(uint8,bool)"))
        self.assertEqual(once["args"], [["storage", "_done"], ["!=", ["storage", "_busy"], 0]])
        inside = [g for g in st if g["src"] == r2_line('require(_busy, "not inside");')][0]
        err = {"name": "Error", "signature": "Error(string)", "selector": keccak_hex(b"Error(string)", 4)}
        self.assertEqual((inside["error"], inside["args"]), (err, [["str", b"not inside".hex()]]))
        dyn = act(d, "dyn")["guards"][0]
        self.assertEqual((dyn["reason"], dyn["error"], dyn["args"], dyn["expr"]), (None, err, [["param", "why"]], 0))

    def test_morph_revert_data(self):
        d = morph()
        g = [x for x in act(d, "initialize")["guards"] if x["src"] == f"{R}:169"][0]
        self.assertEqual((g["error"], g["args"]), ({"name": "IRollup.ErrZeroAddress", "signature": "ErrZeroAddress()",
                                                    "selector": keccak_hex(b"ErrZeroAddress()", 4)}, []))
        for a in d["actions"]:
            for x in a["guards"]:
                with self.subTest(action=a["name"], guard=x["src"]):
                    codes = {r.get("code") for r in x["reaches"]}
                    if x.get("error", {}).get("name") == "Error" and x["reason"] is not None:
                        self.assertEqual(x["args"], [["str", x["reason"].encode().hex()]])
                    if "error" in x:
                        self.assertEqual([len(r["args"]) for r in x["reaches"]], [len(x["args"])] * len(x["reaches"]))
                    elif x["reason"] is not None:
                        self.fail("a guard with a reason has no revert data")
                    if codes == {1}:
                        self.assertNotIn("error", x)


# ================================================================================================ round 2: V19-04
class TestTopics(unittest.TestCase):
    def test_indexed_reference_arguments_are_hashed(self):
        from holon.keccak import keccak256
        e = act(round2(), "note")["events"]
        self.assertEqual(e[0]["topics"], [["keccak256", ["param", "label"]], ["keccak256", ["param", "blob"]],
                                          ["keccak256", ["abi.inplace", ["param", "xs"]]]])
        self.assertEqual(e[1]["topics"][:2], [int.from_bytes(keccak256(b"fixed"), "big"),
                                              int.from_bytes(keccak256(bytes([1, 2])), "big")])
        self.assertEqual(e[0]["indexed"], [True, True, True, False])
        pr = act(round2(), "pair")["events"][0]
        flag = ["!=", ["storage", "flag"], 0]
        self.assertEqual(pr["signature"], "Pair((uint256,uint256),bool,bool)")
        self.assertEqual(pr["topics"], [["keccak256", ["abi.inplace", ["struct", "P", [["a", ["param", "a"]],
                                                                                       ["b", 2]]]]], flag])
        self.assertEqual(pr["args"][1:], [flag, flag])

    def test_morph_topics(self):
        from holon.keccak import keccak256
        for a in morph()["actions"]:
            for ev in a["events"]:
                with self.subTest(action=a["name"], event=ev["event"], src=ev["src"]):
                    self.assertEqual(len(ev["topics"]), sum(ev["indexed"]))
        res = [ev for ev in act(morph(), "proveState")["events"] if ev["event"] == "IRollup.ChallengeRes"]
        self.assertEqual(len(res), 2)
        for ev in res:
            self.assertEqual(ev["signature"], "ChallengeRes(uint256,address,string)")
            self.assertEqual(ev["topics"][2], int.from_bytes(keccak256(bytes.fromhex(ev["args"][2][1])), "big"))


# ================================================================================================ round 2: V19-05
class TestAllocationAndCalldataHead(unittest.TestCase):
    def test_allocation_panics(self):
        al = act(round2(), "alloc")
        bound = (1 << 64) - 1
        self.assertEqual([(p["code"], p["op"], p["args"], p["expr"]) for p in al["panics"] if p["code"] == 65],
                         [(65, "alloc", [["param", "n"]], ["<=", ["param", "n"], bound])] * 2)
        self.assertEqual([p["src"] for p in al["panics"] if p["code"] == 65],
                         [r2_line("new uint256[](n)"), r2_line("new bytes(n)")])

    def test_static_head_of_the_calldata(self):
        d = round2()
        hd = act(d, "head")
        cs = [(c["kind"], c["expr"]) for c in hd["checks"]]
        # a, b (uint64), the offset of c, d (uint256[3], in place), p (two words, in place): 8 words after the selector
        self.assertEqual(cs[:3], [("callvalue", ["==", ["env", "msg.value"], 0]),
                                  ("calldatasize", [">=", ["env", "msg.data.length"], 4 + 32 * 8]),
                                  ("abi", ["<", ["param", "b"], 1 << 64])])
        self.assertEqual([c["kind"] for c in act(d, "getFlag")["checks"]], ["callvalue"])
        T = holon_module("holon.frontends.solidity.transitions")
        self.assertEqual([T.abi_static_size(t) for t in ("uint8", "bytes", "uint256[]", "uint256[2][3]",
                                                         "(uint256,bytes)", "(uint256,(bool,address))[2]")],
                         [32, None, None, 192, None, 192])

    def test_morph_heads(self):
        d = morph()
        want = {"commitBatchWithProof": 100, "initialize": 196, "challengeState": 68, "finalizeBatch": 36}
        for name, n in want.items():
            with self.subTest(action=name):
                cs = [c["expr"] for c in act(d, name)["checks"] if c["kind"] == "calldatasize"]
                self.assertEqual(cs, [[">=", ["env", "msg.data.length"], n]])
        for name in ("owner", "paused", "renounceOwnership", "receive"):
            self.assertNotIn("calldatasize", [c["kind"] for c in act(d, name)["checks"]])


# ================================================================================================ round 2: the compiler
class TestCompilerSemantics(unittest.TestCase):
    """The compiler and EVM facts behind the round-2 rules (V19-02..V19-05), run on the pinned solc and forge
    (config/holon.json "replay"): tests_m2/fixtures/i19_followup/round2/semantics/test/Semantics.t.sol."""

    def test_the_pinned_compiler_does_what_the_rules_say(self):
        import subprocess
        cfg = load_json(ROOT / "config" / "holon.json")["replay"]
        tmp = Path(tempfile.mkdtemp(prefix="holon-a19-sem-"))
        try:
            work = tmp / "semantics"
            shutil.copytree(ROUND2 / "semantics", work)
            p = subprocess.run([cfg["forge"], "test", "--root", str(work), "--offline", "--use", cfg["solc"]],
                               cwd=tmp, capture_output=True, text=True, timeout=900)
            out = p.stdout + p.stderr
            self.assertEqual(p.returncode, 0, out[-3000:])
            for t in ("test_storage_bool_is_the_raw_byte", "test_bools_are_cleaned_where_encoded_stored_or_compared",
                      "test_topics_of_indexed_reference_arguments", "test_memory_allocation_bound",
                      "test_storage_push_has_no_length_check", "test_short_calldata_reverts_with_empty_data",
                      "test_custom_error_revert_data"):
                self.assertIn(f"[PASS] {t}()", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
