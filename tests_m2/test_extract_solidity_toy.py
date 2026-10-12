"""I17 planted fixture: the Solidity frontend on a toy written for the test (construction checks, not counted).

tests_m2/fixtures/extract_solidity/toy/src/{PktCodec.sol, Toy.sol} exercises every rule of the contract in
tests_m2/test_extract_solidity_layout.py on code small enough to read by hand: field naming by the innermost formal
through an intermediate call (_stamp), constant stores (putPad(ptr, 0), putRoot(ptr, bytes32(0))), a later write
overriding an earlier one (putRoot twice), shl widths 8 and 4, a conditional length and a conditional store on the same
condition, field-only requires (domain) and state requires (projected away), a field-only branch that merges away
(_mix's early return on flags == 0), a loop outside the store sequence (walk debt only), an unsupported Yul switch inside
a store sequence (edge debt, exact false), unselected sinks, a calldatacopy loader with an else-if version dispatch, and
an encoder whose bytes depend on a state variable (exit 3). Its expected extraction is
tests_m2/fixtures/extract_solidity/toy/expected.json, written by hand at the prereg before any extractor existed.
"""
import json
import unittest

from tests_m2 import _i17 as H
from tests_m2._m2 import load_json

EXPECTED = None


def expected() -> dict:
    global EXPECTED
    if EXPECTED is None:
        EXPECTED = load_json(H.TOY_EXPECTED)
    return EXPECTED


def canon_set(paths) -> list[str]:
    return sorted(json.dumps(p, sort_keys=True) for p in paths)


class TestToyExtraction(unittest.TestCase):
    ex: H.Extract = None

    @classmethod
    def setUpClass(cls):
        cls.ex = H.Extract(H.toy_args())

    @classmethod
    def tearDownClass(cls):
        cls.ex.cleanup()

    def doc(self) -> dict:
        self.assertEqual(self.ex.code, 0, self.ex.log)
        return self.ex.doc()

    def test_toy_document_header(self):
        d, x = self.doc(), expected()
        self.assertEqual(d["facts_version"], x["facts_version"])
        self.assertEqual(d["extraction"]["frontend_version"], x["frontend_version"])
        self.assertEqual([i["unit"] for i in d["extraction"]["inputs"]], x["inputs"])
        self.assertEqual(d["extraction"]["sidecar"]["path"], "tests_m2/fixtures/extract_solidity/toy/extract_solidity.json")
        self.assertEqual(d["target"], load_json(H.TOY_SIDECAR)["target"])
        self.assertEqual(sorted(d["functions"]), sorted(x["edges"]))
        self.assertEqual(self.ex.bytes(), H.canonical_bytes(d))

    def test_toy_types_and_fields(self):
        """N1-N2: names from the innermost formal (kind, not tag), widths from the store shape, value types from the
        outermost argument (kind is uint8 although _stamp's formal is uint256)."""
        self.assertEqual(self.doc()["types"], expected()["types"])

    def test_toy_assumptions(self):
        got = [{k: v for k, v in a.items() if k != "text"} for a in self.doc()["assumptions"]]
        self.assertEqual(got, expected()["assumptions"])
        self.assertTrue(all(isinstance(a.get("text"), str) and a["text"] for a in self.doc()["assumptions"]))

    def test_toy_edges_paths_and_debt(self):
        d = self.doc()
        for name, x in expected()["edges"].items():
            with self.subTest(edge=name):
                e = d["functions"][name]
                for k in ("kind", "from", "to", "lang", "memory_init", "sink", "exact", "debt"):
                    self.assertEqual(e[k], x[k], k)
                self.assertEqual(e["entry"]["fn"], x["entry_fn"])
                self.assertEqual(canon_set(p for p in e["paths"] if p["outcome"] == "revert"), canon_set(x["reverts"]))
                self.assertEqual(canon_set(p for p in e["paths"] if p["outcome"] == "ok"), canon_set(x["oks"]))
                self.assertEqual(len(e["paths"]), len(x["reverts"]) + len(x["oks"]))

    def test_toy_layouts_per_selector(self):
        d = self.doc()
        e, x = d["functions"]["enc_toy"], expected()["edges"]["enc_toy"]
        w = H.field_widths(d, e["from"])
        for v in range(256):
            with self.subTest(kind=v):
                got = H.layout_at(e, w, x["selector"], v)
                if v >= x["none_from"]:
                    self.assertIsNone(got)
                    self.assertTrue(H.reverts_at(e, x["selector"], v))
                else:
                    self.assertEqual(got, H.expand_runs(x["layouts"][str(v)]))
        bad, xb = d["functions"]["enc_bad"], expected()["edges"]["enc_bad"]
        oks = [p for p in bad["paths"] if p["outcome"] == "ok"]
        self.assertEqual(len(oks), 1)
        self.assertEqual(H.path_layout(oks[0]), H.expand_runs(xb["layouts"]["*"]))

    def test_toy_loader_grid(self):
        e = self.doc()["functions"]["load_toy"]
        for length in expected()["edges"]["load_toy"]["grid"]["lengths"]:
            for b0 in (range(256) if length else [0]):
                p = H.loader_outcome(e, "prev", b0, length)
                if length == 0:
                    want = "empty"
                elif b0 < 2:
                    want = "ok" if length >= 49 else "pkt short"
                elif b0 < 4:
                    want = "ok" if length == 57 else "pkt length"
                else:
                    want = "unknown kind"
                self.assertEqual(p.get("reason", "ok") if p["outcome"] == "revert" else "ok", want, (b0, length))
                if p["outcome"] == "ok":
                    self.assertEqual(H.path_layout(p, {("len", "prev"): length}),
                                     [["input", "prev", k] for k in range(length)])

    def test_toy_walks(self):
        d = self.doc()
        for name, x in expected()["edges"].items():
            with self.subTest(edge=name):
                wk = d["functions"][name]["walk"]
                self.assertEqual(wk["functions"], x["walk"]["functions"])
                self.assertEqual(wk["paths"], x["walk"]["paths"])
                self.assertEqual(canon_set(wk["sinks"]), canon_set(x["walk"]["sinks"]))
                self.assertEqual(wk["debt"], x["walk"]["debt"])

    def test_toy_two_runs_are_byte_identical(self):
        again = H.Extract(H.toy_args())
        try:
            self.assertEqual(again.code, 0, again.log)
            self.assertEqual(again.bytes(), self.ex.bytes())
        finally:
            again.cleanup()


class TestToyFailure(unittest.TestCase):
    def test_an_environment_dependent_layout_is_an_error_naming_the_edge(self):
        """J4: Toy._emitEnv writes 1 or 2 at byte 0 depending on a state variable; after projection both ok paths have
        the empty condition, so the extraction fails with exit 3, names enc_env and writes nothing."""
        f = expected()["failure"]
        run = H.Extract(H.toy_args(H.TOY_ENV_SIDECAR))
        try:
            self.assertEqual(run.code, f["exit"], run.log)
            self.assertIn(f["names"], run.stdout + run.stderr)
            self.assertNotIn("usage:", run.stderr)
            self.assertFalse(run.out.exists(), "a failed extraction wrote")
        finally:
            run.cleanup()


if __name__ == "__main__":
    unittest.main()
