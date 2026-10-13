"""I20-B unit tests (not preregistered; written with the code): the refinement of an extracted transitions document
against the real contract (holon/replay_fragments.py, holon/fragments_corpus.py, holon/fragments_doc.py,
holon/evm_abi.py), and GREF's reading of a step refinement record (holon/refinement.py).

The end-to-end tests run the real harness with the pinned forge and solc on a planted toy (fixtures under
tests_m2/fixtures/i20_refine/toy/): a Ledger with inherited and packed storage, an external dependency, a custom error,
events and a checked uint64 accumulator. The toy's transitions document is extracted at test time with the I19
follow-up's frontend. The model side is the extracted model itself (holon.machine.load_extracted,
holon.extracted_eval.step: the one evaluator); tests_m2/fixtures/i20_refine/toy_model.py plants three defects on top
of it. The document view is checked on the I20-A toy's committed extraction (tests_m2/fixtures/i20_model/toy/).
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, load_json, run_holon

FIX = ROOT / "tests_m2" / "fixtures" / "i20_refine"
TOY = FIX / "toy"
BOOK = ROOT / "tests_m2" / "fixtures" / "i20_model" / "toy"
STUB = "tests_m2/fixtures/i20_refine/toy_model.py"
SRC = "src/Ledger.sol"
A1 = "0x0000000000000000000000000000000000001001"
OWNER = "0x7fa9385be102ac3eac297483dd6233d62b3e1496"


def compiled_layout() -> dict:
    """The compiler's storage layout of the I20-A toy Book (holon.machine's compiler information for it)."""
    from holon import machine
    return machine.load_extracted(BOOK / "book.extracted.json", ROOT, source=BOOK).info["layout"]


class TestAbi(unittest.TestCase):
    def setUp(self):
        from holon import evm_abi
        self.abi = evm_abi
        self.fn = {"name": "f", "inputs": [
            {"name": "x", "type": "tuple", "components": [{"name": "v", "type": "uint8"}, {"name": "b", "type": "bytes"},
                                                          {"name": "n", "type": "uint64"}]},
            {"name": "y", "type": "uint64"}, {"name": "z", "type": "bytes32[]"}, {"name": "s", "type": "string"}]}
        self.vals = {"x": {"v": 1, "b": "0x1234", "n": 7}, "y": 3, "z": ["0x" + "ab" * 32], "s": "hi"}

    def test_selector_and_round_trip(self):
        self.assertEqual(self.abi.selector("transfer", [{"type": "address"}, {"type": "uint256"}]), "0xa9059cbb")
        cd = self.abi.encode_call(self.fn, self.vals)
        self.assertEqual(self.abi.decode_args(self.fn["inputs"], bytes.fromhex(cd[10:])), self.vals)

    def test_dirty_calldata_is_rejected_strictly_and_decoded_raw_otherwise(self):
        for path, ty in ((("x", "n"), "uint64"), (("y",), "uint64"), (("x", "v"), "uint8")):
            with self.subTest(path=path):
                w = self.abi.dirty_words(ty)[0]
                cd = self.abi.dirty_call(self.fn, self.vals, path, w)
                body = bytes.fromhex(cd[10:])
                with self.assertRaises(self.abi.AbiError):
                    self.abi.decode_args(self.fn["inputs"], body)
                got = self.abi.decode_args(self.fn["inputs"], body, strict=False)
                self.assertEqual(self.abi.get_path(got, path), w)
        self.assertIsNone(self.abi.leaf_offset(self.fn["inputs"], self.vals, ("x", "b")))   # dynamic: no word

    def test_out_of_range_values_do_not_encode(self):
        with self.assertRaises(self.abi.AbiError):
            self.abi.encode_args([{"name": "a", "type": "uint8"}], {"a": 256})


class TestDocView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon.fragments_doc import DocView
        cls.DocView = DocView
        cls.doc = load_json(BOOK / "book.extracted.json")
        cls.v = DocView.build(cls.doc, compiled_layout())

    def test_reaches_are_the_models_checks_in_seq_order(self):
        """One rule for check ids: holon.machine's program (the evaluator's), every reach kind of the document."""
        from holon import machine
        m = machine.load_extracted(BOOK / "book.extracted.json", ROOT, source=BOOK)
        self.assertEqual([r.id for r in self.v.all_reaches()], [c.id for c in m.all_reaches()])
        got = [(r.id, r.kind, r.section) for r in self.v.reaches["deposit"]]
        B = "src/Book.sol"
        self.assertEqual(got, [
            (f"deposit#{B}:46-53#0", "calldatasize", "checks"), (f"deposit#{B}:46#0", "abi", "checks"),
            (f"deposit#{B}:21#0", "modifier", "guards"), (f"deposit#{B}:47#0", "require", "guards"),
            (f"deposit#{B}:48#0", "call", "calls"), (f"deposit#{B}:48#1", "require", "guards"),
            (f"deposit#{B}:49#0", "panic", "panics"), (f"deposit#{B}:50#0", "panic", "panics")])
        self.assertEqual(self.v.reach(f"deposit#{B}:49#0").code, 17)
        self.assertEqual([r.loop for r in self.v.reaches["seal"] if r.loop], [f"{B}:74-76", f"{B}:74-76"])
        seqs = [r.seq for r in self.v.reaches["deposit"]]
        self.assertEqual(seqs, sorted(seqs))

    def test_events_layout_and_widths(self):
        self.assertEqual(len(self.v.events("deposit")), 1)
        self.assertEqual(len(self.v.topics0()), 3)
        self.assertEqual([(e.name, e.source, e.declared_in) for e in self.v.layout],
                         [("_owner", "inherited_storage", "Owned"), ("_stopped", "inherited_storage", "Owned"),
                          ("total", "storage", None), ("gate", "storage", None), ("count", "storage", None),
                          ("entries", "storage", None), ("last", "storage", None)])
        self.assertEqual(self.v.dump_slots(), [0, 1, 2, 4])
        self.assertEqual(self.v.widths(), {8, 32, 64, 160, 256})
        sel = next(a["selector"] for a in self.doc["actions"] if a["name"] == "deposit")
        self.assertEqual(self.v.action_of(sel), "deposit")

    def test_a_document_slot_the_compiler_does_not_have_is_refused(self):
        from holon.fragments_doc import DocError
        doc = json.loads(json.dumps(self.doc))
        doc["storage"][0]["slot"] = 9
        with self.assertRaises(DocError):
            self.DocView.build(doc, compiled_layout())

    def test_a_document_without_the_follow_up_sections_is_refused(self):
        from holon.fragments_doc import DocError
        doc = {k: v for k, v in self.doc.items() if k != "inherited_storage"}
        with self.assertRaises(DocError):
            self.DocView.build(doc, compiled_layout())
        doc = json.loads(json.dumps(self.doc))
        for a in doc["actions"]:
            a.pop("panics", None)
        with self.assertRaises(DocError):
            self.DocView.build(doc, compiled_layout())


def planted_layout() -> dict:
    """A storage layout in solc's shape (inherited _owner/_paused/verifier, then last, entries)."""
    t = {"t_address": {"encoding": "inplace", "label": "address", "numberOfBytes": "20"},
         "t_bool": {"encoding": "inplace", "label": "bool", "numberOfBytes": "1"},
         "t_uint256": {"encoding": "inplace", "label": "uint256", "numberOfBytes": "32"},
         "t_uint64": {"encoding": "inplace", "label": "uint64", "numberOfBytes": "8"},
         "t_struct(Entry)1_storage": {"encoding": "inplace", "label": "struct P.Entry", "numberOfBytes": "32",
                                      "members": [{"label": "amount", "offset": 0, "slot": "0", "type": "t_uint64"},
                                                  {"label": "who", "offset": 8, "slot": "0", "type": "t_address"}]},
         "t_mapping(t_uint256,t_struct(Entry)1_storage)": {"encoding": "mapping", "key": "t_uint256",
                                                           "label": "mapping(uint256 => struct P.Entry)",
                                                           "numberOfBytes": "32",
                                                           "value": "t_struct(Entry)1_storage"}}
    s = [{"label": "_owner", "slot": "0", "offset": 0, "type": "t_address", "contract": "P.sol:Owned"},
         {"label": "_paused", "slot": "0", "offset": 20, "type": "t_bool", "contract": "P.sol:Owned"},
         {"label": "verifier", "slot": "1", "offset": 0, "type": "t_address", "contract": "P.sol:Gated"},
         {"label": "last", "slot": "2", "offset": 0, "type": "t_uint256", "contract": "P.sol:P"},
         {"label": "entries", "slot": "3", "offset": 0, "type": "t_mapping(t_uint256,t_struct(Entry)1_storage)",
          "contract": "P.sol:P"}]
    return {"storage": s, "types": t}


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        from holon import fragments_corpus as FC
        from holon.keccak import keccak256
        from holon.replay_fragments import Layout
        self.FC = FC
        slot = int.from_bytes(keccak256((5).to_bytes(32, "big") + (3).to_bytes(32, "big")), "big")
        state = {0: (1 << 160) | 0xAA, 2: (1 << 256) - 1, slot: (0xBB << 64) | 9}
        env = {"caller": "0x" + "00" * 19 + "aa", "msg.value": 3,
               "calls": [{"fn": "IV.verify", "args": {"n": 4}, "ok": False, "ret": "0x"}]}
        fn = {"inputs": [{"name": "n", "type": "uint256"}, {"name": "b", "type": "bytes"}]}
        self.ev = FC.Evaluator(Layout(planted_layout()), state, fn, {"n": 4, "b": "0x0102"}, env)

    def test_storage_packing_mappings_and_members(self):
        e, U = self.ev.ev, self.FC.U
        self.assertEqual(e(["storage", "_owner"]), 0xAA)
        self.assertEqual(e(["storage", "_paused"]), 1)
        self.assertEqual(e(["==", ["storage", "_owner"], ["caller"]]), 1)
        self.assertEqual(e(["member", ["map", ["storage", "entries"], 5], "amount"]), 9)
        self.assertEqual(e(["member", ["map", ["storage", "entries"], 5], "who"]), 0xBB)
        self.assertEqual(e(["byte", ["param", "b"], 1]), 2)
        self.assertIs(e(["carried", "s:1", "i"]), U)
        self.assertIs(e(["&&", ["iter", "s:1"], 1]), U)
        self.assertEqual(e(["&&", ["carried", "s:1", "i"], 0]), 0)

    def test_planned_implicit_check_terms(self):
        e = self.ev.ev
        self.assertEqual(e(["fits", 256, ["+", ["storage", "last"], 1]]), 0)
        self.assertEqual(e(["fits", 256, ["+", ["storage", "last"], 0]]), 1)
        self.assertEqual(e(["fits", 64, ["-", 3, ["env", "msg.value"]]]), 1)
        self.assertEqual(e(["fits", 64, ["-", 2, ["env", "msg.value"]]]), 0)
        self.assertEqual(e(["sfits", 8, ["+", 127, 1]]), 0)
        self.assertEqual(e(["sfits", 8, ["-", 0, 128]]), 1)
        self.assertEqual(e(["callok", "IV.verify", ["storage", "verifier"], ["param", "n"]]), 0)
        self.assertIs(e(["callok", "IV.verify", ["storage", "verifier"], 5]), self.FC.U)

    def test_pseudo_comparisons_of_fits(self):
        self.assertEqual(self.FC._pseudo_comparisons(["fits", 256, ["-", "x", "y"]]), [[">=", "x", "y"]])
        self.assertEqual(len(self.FC._pseudo_comparisons(["fits", 64, ["+", "x", "y"]])), 2)


class TestComparison(unittest.TestCase):
    def setUp(self):
        from holon import replay_fragments as RF
        self.RF = RF

    def test_revert_keys_follow_clause_7(self):
        RF = self.RF
        err = "0x08c379a0" + (32).to_bytes(32, "big").hex() + (2).to_bytes(32, "big").hex() + "6869" + "00" * 30
        self.assertEqual(RF.revert_key(err), ["error", "hi"])
        self.assertEqual(RF.revert_key("0x4e487b71" + (0x11).to_bytes(32, "big").hex()), ["panic", 17])
        self.assertEqual(RF.revert_key("0x3715f556" + (1).to_bytes(32, "big").hex()), ["custom", "0x3715f556"])
        self.assertEqual(RF.revert_key("0x3715f556" + (2).to_bytes(32, "big").hex()), ["custom", "0x3715f556"])
        self.assertEqual(RF.revert_key("0x"), ["raw", "0x"])

    def test_storage_and_events_are_compared_on_two_oks(self):
        RF = self.RF
        h = RF.hex32
        before, after = {1: 5}, {1: 6, 2: 7}
        real = {"status": "ok", "revert": None, "writes": {h(1): h(6), h(2): h(7)}, "events": [], "guard": None}
        model = {"status": "ok", "revert": None, "writes": {h(1): h(6), h(2): h(7)}, "events": [], "guard": None}
        self.assertEqual(RF.compare(model, real, before, after), ([], 2))
        model["writes"] = {h(1): h(6)}
        self.assertEqual(RF.compare(model, real, before, after), (["storage"], 2))
        model["writes"] = {h(1): h(6), h(2): h(7), h(3): h(0)}      # a write of the value already there agrees
        self.assertEqual(RF.compare(model, real, before, after), ([], 3))
        model["events"] = [{"topics": [h(1)], "data": "0x"}]
        self.assertEqual(RF.compare(model, real, before, after), (["events"], 3))
        self.assertEqual(RF.compare({**model, "status": "unsupported"}, real, before, after), (["status"], 0))

    def test_harness_lines_parse_and_tracking_checks_every_dump(self):
        RF = self.RF
        t = "0x" + "11" * 20
        text = "\n".join([
            f"T 0 {t} 0x{'22' * 20}", f"K 0 0x6080",
            "S 0 d env 0 1 - - 0 100 1 - 0x 0x", f"W 0 d 0x{1:064x} 0x{5:064x} 0", "D 0 d 0,5",
            f"S 0 0 call 0 1 {t} 0x{'33' * 20} 0 100 1 - 0x12345678 0x",
            f"V 0 0 31337 0 0 0x{'00' * 20} 30000000 1 0x{'44' * 20} 0 7 8",
            f"W 0 0 0x{1:064x} 0x{6:064x} 0", f"W 0 0 0x{1:064x} 0x{9:064x} 1",
            f"L 0 0 0x{'aa' * 32} 0x", f"C 0 0 0x{'55' * 20} 0xddca3f43 1 0x{2:064x}", "X 0 0 harness-mismatch", "D 0 0 0,6",
            f"S 0 1 call 1 1 {t} 0x{'33' * 20} 0 100 1 - 0x12345678 0x", f"W 0 1 0x{0:064x} 0x{1:064x} 0",
            "D 0 1 1,6", "E 0 2", "DONE 0 1"])
        (tr,) = RF.parse_output(text)
        self.assertEqual((tr.target, tr.code, len(tr.execs)), (t, "0x6080", 3))
        e = tr.execs[1]
        self.assertEqual((e.env["block.chainid"], e.balances, len(e.writes), e.calls[0][1]), (31337, (7, 8), 2, "0xddca3f43"))
        states = RF.track(tr, [0, 1])
        self.assertEqual(states[1][2], {1: 6})          # the reverted write is not applied
        self.assertEqual(RF.harness_notes([tr]), {"harness-mismatch": 1})
        self.assertEqual(states[2][2], {0: 1, 1: 6})     # a fork's state ...
        tr.execs[2].dump = [0, 6]
        with self.assertRaises(RF.FragmentsError):       # ... must match its dump
            RF.track(tr, [0, 1])

    def test_forks_are_inserted_before_their_position_and_merged_when_identical(self):
        from holon.fragments_corpus import insert_forks
        Step = self.RF.Step
        base = [[Step("call", data="0x01"), Step("call", data="0x02")]]
        f1 = {(0, 1): [Step("call", fork=True, data="0xaa", meta={"source": "boundary"})]}
        f2 = {(0, 1): [Step("call", fork=True, data="0xaa", meta={"source": "target", "targets": "r"})],
              (0, 2): [Step("call", fork=True, data="0xbb", meta={"source": "target"})]}
        out = insert_forks(base, f1, f2)
        self.assertEqual([s.data for s in out[0]], ["0x01", "0xaa", "0x02", "0xbb"])
        self.assertEqual(out[0][1].meta["also"], [{"source": "target", "targets": "r"}])


class TestHevmGeneration(unittest.TestCase):
    """The two sides holon.hevm_equiv hands to hevm, built from the facts and the binding (no hevm needed here)."""

    @classmethod
    def setUpClass(cls):
        from holon import facts as F
        from holon import hevm_equiv as H
        cls.H = H
        cls.facts = F.load(ROOT / "facts" / "morph_header.json")
        cls.binding = load_json(ROOT / "replay" / "M2" / "hevm_store.json")

    def test_side_b_is_the_model_layout_in_yul(self):
        y0 = self.H.model_yul(self.facts, "enc_sol", 0)
        self.assertIn("mstore8(add(p, 0), and(calldataload(0), 0xff))", y0)
        self.assertIn("mstore(add(p, 1), shl(192, and(calldataload(32), 0xffffffffffffffff)))", y0)
        self.assertIn("mstore(add(p, 185), 0)", y0)
        self.assertIn("return(p, 249)", y0)
        self.assertNotIn("add(p, 249)", y0)
        y1 = self.H.model_yul(self.facts, "enc_sol", 1)
        self.assertIn("mstore(add(p, 249), shl(192, and(calldataload(352), 0xffffffffffffffff)))", y1)
        self.assertIn("return(p, 257)", y1)

    def test_op_values_place_field_runs_and_constants(self):
        e = self.H.op_value([["field", "x", 1], ["field", "x", 2], ["const", 5]], {"x": 4}, {"x": 3})
        self.assertEqual(e, "or(shl(8, and(shr(8, calldataload(96)), 0xffff)), 5)")

    def test_side_a_calls_the_store_functions_as_the_binding_says(self):
        src = self.H.wrapper_source(self.binding, self.facts)
        v0 = src[src.index("contract HolonHevmStoreV0"):src.index("contract HolonHevmStoreV1")]
        self.assertIn("BatchHeaderCodecV0.storeDataHash(p, bytes32(_w(4)));", v0)
        self.assertIn("BatchHeaderCodecV0.storeSequencerSetVerifyHash(p, bytes32(0));", v0)
        self.assertNotIn("storeLastBlockNumber", v0)
        self.assertIn("BatchHeaderCodecV1.storeLastBlockNumber(p, _w(11));", src[src.index("contract HolonHevmStoreV1"):])

    def test_verdicts_follow_hevm_summary_lines(self):
        ok = "Found 1 total pairs of endstates\n   \x1b[32m[PASS]\x1b[0m Contracts behave equivalently\n\nNo discrepancies found\n"
        self.assertEqual(self.H.verdict(0, ok)[0], "equivalent")
        bad = "\x1b[31m[FAIL]\x1b[0m Contracts do not behave equivalently\nNot equivalent. The following inputs ...\n"
        self.assertEqual(self.H.verdict(1, bad)[0], "not_equivalent")
        unk = ("\x1b[31m[FAIL]\x1b[0m Contracts may not behave equivalently\nhevm was only able to partially explore\n"
               "1x -> SMT solver says: Result unknown by SMT solver\n")
        self.assertEqual(self.H.verdict(1, unk)[0], "unknown")
        self.assertEqual(self.H.verdict(0, "No discrepancies found\nhevm was only able to partially explore")[0],
                         "unknown")

    def test_the_negative_control_mutates_one_mask(self):
        y, what = self.H.control_yul(self.H.model_yul(self.facts, "enc_sol", 0))
        self.assertEqual(what, "and(calldataload(0), 0xff) -> and(calldataload(0), 0x7f)")
        self.assertIn("mstore8(add(p, 0), and(calldataload(0), 0x7f))", y)


class TestGrefReadsStepRecords(unittest.TestCase):
    def test_step_records_are_checked_against_the_disagreements_file(self):
        from holon.refinement import check_disagreements
        tmp = Path(tempfile.mkdtemp(prefix="holon-i20b-"))
        try:
            (tmp / "spec" / "M2").mkdir(parents=True)
            (tmp / "results" / "M2" / "refinement").mkdir(parents=True)
            entry = {"id": "D-x-a-1", "edge": "a", "milestone": "M2", "class": "unexplained", "links": {}}
            (tmp / "spec" / "M2" / "disagreements.json").write_text(json.dumps({"disagreements": [entry]}))
            rec = {"kind": "extracted", "disagreements": [{"id": "D-x-a-1", "class": "unexplained", "links": {}}],
                   "unexplained": 1}
            p = tmp / "results" / "M2" / "refinement" / "extracted.json"
            p.write_text(json.dumps(rec))
            probs = check_disagreements(tmp)
            self.assertEqual(len(probs), 1, probs)               # only the unexplained entry itself
            self.assertIn("D-x-a-1: unexplained", probs[0])
            rec["unexplained"] = 0
            rec["disagreements"].append({"id": "D-x-a-2", "class": "unexplained", "links": {}})
            p.write_text(json.dumps(rec))
            probs = check_disagreements(tmp)
            self.assertTrue(any("D-x-a-2: listed by extracted.json" in x for x in probs), probs)
            self.assertTrue(any("counts 0 unexplained" in x for x in probs), probs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestToyEndToEnd(unittest.TestCase):
    """The real harness with the pinned forge on the planted Ledger, against the extracted model (about a minute)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i20b-toy-"))
        cls.doc = cls.tmp / "ledger.extracted.json"
        p = run_holon(["extract", "solidity", "--sidecar", str(TOY / "extract_ledger.json"), "--source", str(TOY),
                       "--out", str(cls.doc)], timeout=600)
        if p.returncode != 0:
            raise AssertionError(p.stdout[-1500:] + p.stderr[-1500:])
        from holon import machine
        cls.model = machine.load_extracted(cls.doc, ROOT, source=TOY)
        cls.runs = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fragments(self, name: str, binding: Path, evaluator: str | None, *extra: str) -> tuple[dict, dict, str]:
        if name not in self.runs:
            out, det = self.tmp / f"{name}.json", self.tmp / f"{name}.details.json"
            ev = ["--evaluator", evaluator] if evaluator else []
            p = run_holon(["fragments", "--facts", str(self.doc), "--binding", str(binding), *ev,
                           "--out", str(out), "--details", str(det), "--work", str(self.tmp / f"work_{name}"), *extra],
                          timeout=1800)
            self.assertIn(p.returncode, (0, 1), p.stdout[-2000:] + p.stderr[-2000:])
            self.runs[name] = (load_json(out), load_json(det), out.read_text())
        return self.runs[name]

    def faithful(self):
        return self.fragments("faithful", TOY / "fragments.json", None, "--no-file")

    def test_the_extracted_model_agrees_on_every_observable(self):
        rec, det, _ = self.faithful()
        # the two seed traces, and the suffix traces of the targeting search
        self.assertEqual((rec["traces"], rec["unexplained"], rec["disagreements"]), (2 + rec["corpus"]["suffix"], 0, []))
        self.assertEqual(sorted(rec["observables"]), ["events", "revert", "status", "storage"])
        self.assertGreater(rec["storage_slots"], 0)
        for a in ("deposit", "withdraw", "setPaused"):
            with self.subTest(action=a):
                self.assertGreaterEqual(rec["by_action"][a]["ok"], 1)
                self.assertGreaterEqual(rec["by_action"][a]["revert"], 1)
        g = rec["guard_coverage"]
        self.assertEqual(g["reaches"], len(self.model.all_reaches()))
        self.assertEqual(g["falsified"] + len(g["unfalsified"]), g["reaches"])
        for u in g["unfalsified"]:
            with self.subTest(reach=u["id"]):
                self.assertTrue(u["reason"].strip())
        self.assertEqual(rec["harness_notes"], {})
        self.assertEqual(rec["storage_layout"]["inherited"], 2)
        self.assertEqual(rec["evaluator"], "holon.extracted_eval:step (model: holon.machine.load_extracted)")

    def test_the_targeting_search_reaches_the_implicit_checks(self):
        """Dirty calldata for an ABI range check, a call value for the call-value checks; both sides revert there."""
        rec, det, _ = self.faithful()
        muts = {c["meta"].get("targets"): c["meta"].get("mutation") for c in det["compared"]
                if c["meta"].get("source") == "target"}
        abi = [r.id for r in self.model.all_reaches() if r.kind == "abi"]
        cv = [r.id for r in self.model.all_reaches() if r.kind == "callvalue"]
        self.assertTrue(abi and cv)
        for rid in abi:
            with self.subTest(reach=rid):
                self.assertTrue(str(muts.get(rid)).startswith("dirty "), muts)
        for rid in cv:
            with self.subTest(reach=rid):
                self.assertEqual(muts.get(rid), "msg.value=1")
        unf = {u["id"] for u in rec["guard_coverage"]["unfalsified"]}
        self.assertFalse(unf & (set(abi) | set(cv)), unf)

    def test_the_real_panic_is_located_at_the_checked_accumulator(self):
        rec, _, _ = self.faithful()
        self.assertEqual(rec["panics"], [{"code": "0x11", "model_src": f"{SRC}:51", "real_site": f"{SRC}:51",
                                          "site_agrees": True, "src": f"{SRC}:51", "steps": 1}])

    def test_the_external_answers_and_inherited_storage_reach_the_model(self):
        _, det, _ = self.faithful()
        seen = {(c["action"], c["real"]["status"], json.dumps(c["real"]["revert"])) for c in det["compared"]}
        self.assertIn(("deposit", "revert", json.dumps(["error", "not allowed"])), seen)
        self.assertIn(("deposit", "revert", json.dumps(["error", "fee"])), seen)
        self.assertIn(("withdraw", "revert", json.dumps(["custom", "0x3715f556"])), seen)
        self.assertIn(("setPaused", "revert", json.dumps(["error", "not owner"])), seen)
        self.assertIn(("deposit", "revert", json.dumps(["error", "paused"])), seen)

    def test_every_planted_defect_is_a_filed_disagreement_on_its_observable(self):
        dis = self.tmp / "disagreements.json"
        rec, _, _ = self.fragments("buggy", TOY / "fragments.json", f"{STUB}:step_buggy", "--disagreements",
                                   str(dis), "--no-locate")
        filed = load_json(dis)["disagreements"]
        self.assertEqual(sorted(d["id"] for d in rec["disagreements"]), sorted(e["id"] for e in filed))
        self.assertEqual(rec["unexplained"], len(filed))
        obs = {o for e in filed for o in e["observables"]}
        self.assertEqual(obs, {"status", "storage", "events"})
        for e in filed:
            with self.subTest(id=e["id"]):
                self.assertEqual((e["class"], e["links"], e["milestone"]), ("unexplained", {}, "M2"))
                self.assertTrue(e["id"].startswith("D-x-deposit-"))

    def min_binding(self) -> Path:
        bp = self.tmp / "binding_min.json"
        if not bp.exists():
            b = load_json(TOY / "fragments.json")
            b["corpus"] = {"traces": [[
                {"fn": "deposit", "args": {"amount": 5}, "caller": A1, "value": 2},
                {"fn": "withdraw", "args": {"id": 1}, "caller": A1},
                {"fn": "setPaused", "args": {"on": True}, "caller": OWNER}]]}
            bp.write_text(json.dumps(b))
        return bp

    def test_the_targeting_search_builds_steps_for_reaches_the_corpus_misses(self):
        bp = self.min_binding()
        rec, det, text = self.fragments("min", bp, None, "--no-file", "--no-locate")
        self.assertEqual(rec["unexplained"], 0)
        g = rec["guard_coverage"]
        self.assertEqual(g["reaches"], len(self.model.all_reaches()))
        targeted = {c["meta"].get("targets") for c in det["compared"] if c["meta"].get("source") == "target"}
        self.assertTrue({f"deposit#{SRC}:21#0", f"withdraw#{SRC}:21#0", f"setPaused#{SRC}:16#0"} <= targeted,
                        targeted)
        # the paused guards need a state the single-step search cannot build: a suffix trace sets it (setPaused)
        suffix = [c for c in det["compared"] if c["meta"].get("suffix")]
        self.assertTrue({f"deposit#{SRC}:21#0", f"withdraw#{SRC}:21#0"} <= {c["meta"]["targets"] for c in suffix})
        self.assertEqual({c["meta"]["suffix"][2] for c in suffix
                          if c["meta"]["targets"] in (f"deposit#{SRC}:21#0", f"withdraw#{SRC}:21#0")}, {"setPaused"})
        self.assertGreater(rec["corpus"]["target"], 0)
        # determinism: a second run writes the same record
        out2 = self.tmp / "min2.json"
        p = run_holon(["fragments", "--facts", str(self.doc), "--binding", str(bp),
                       "--out", str(out2), "--details", str(self.tmp / "min2.details.json"),
                       "--work", str(self.tmp / "work_min2"), "--no-file", "--no-locate"], timeout=1800)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertEqual(out2.read_text(), text)

    def test_without_targeting_every_missed_reach_is_listed_with_a_reason(self):
        rec, _, _ = self.fragments("bare", self.min_binding(), None, "--no-file", "--no-locate", "--sources", "m1")
        g = rec["guard_coverage"]
        self.assertEqual(g["falsified"] + len(g["unfalsified"]), g["reaches"])
        self.assertEqual(g["reaches"], len(self.model.all_reaches()))
        self.assertGreater(len(g["unfalsified"]), 0)
        for u in g["unfalsified"]:
            self.assertEqual(u["reason"], "no search ran for this reach")


if __name__ == "__main__":
    unittest.main()
