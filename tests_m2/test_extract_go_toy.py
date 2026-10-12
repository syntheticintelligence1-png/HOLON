"""I18 construction checks on the planted toy (tests_m2/fixtures/go_frontend/toy, config toy_config.json): a module
written for this test whose extraction is known by construction. Contract: the docstring of
tests_m2/test_extract_go.py. These checks are construction checks (I18-R6), not predictions.

The toy (module toy.local/fixture):
  codec  RecA.Bytes / RecB.Bytes: cached value-receiver encoders (13 bytes, tag 7; 21 bytes, tag 8; RecB embeds RecA
         and shadows its cache field memo); Frame (a named []byte) with kind/check (tags 7 -> 13; 8, 9 -> 21) and the
         getters Kind, Seq, Tag (through the config primitive prim.ToWord), Tail (tag >= 8), Unsafe (no check); Buf
         with Add (appends to both fields), Joined (append view over head), Body (view), Copy (fresh); Sum (a counted
         and a range loop), Scan (O4's shape: an error path indexing a 48-byte buffer at i*4 for i < 16), ScanSafe
         (the fixed copy), Forever (`for {}`), Between (n from lo while n <= hi).
  use    Consume (a Joined view passed to Sum), Hold (a Joined view held across Add), Fresh (a Copy held across Add:
         no view), Stamp (a standalone 21-byte encoder with tag 9), Patch (RecB.Bytes with byte 0 set to 9), Top ->
         mid -> codec.Scan from a range loop.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i18 as H

C, U = "toy.local/fixture/codec", "toy.local/fixture/use"
RECA, RECB = f"({C}.RecA).Bytes", f"({C}.RecB).Bytes"
CHECK = f"({C}.Frame).check"
STAMP, PATCH = f"{U}.Stamp", f"{U}.Patch"
BUF = f"(*{C}.Buf)"
PROBE_LENGTHS = (0, 1, 2, 8, 9, 10, 12, 13, 14, 20, 21, 22)
PROBE_TAGS = (0, 6, 7, 8, 9, 10, 255)


def toy_probes():
    return [H.Probe(n, cap, v) for n in PROBE_LENGTHS for cap in (n, n + 16) for v in (PROBE_TAGS if n else (0,))]


def check_ok(p) -> bool:
    return p.n > 0 and ((p.b0 == 7 and p.n == 13) or (p.b0 in (8, 9) and p.n == 21))


def byte_cells(term, n):
    return [["byte", term, k] for k in range(n)]


class _Toy(unittest.TestCase):
    run_: "H.Run" = None

    @classmethod
    def setUpClass(cls):
        if _Toy.run_ is None:
            _Toy.run_ = H.Run.toy()

    @property
    def docs(self) -> dict:
        return _Toy.run_.need()

    def fn(self, fid):
        return H.function(self.docs, fid)


class TestToyDocuments(_Toy):
    def test_two_documents_valid_and_deterministic(self):
        r = _Toy.run_
        self.assertEqual(r.code, 0, r.log)
        self.assertEqual(sorted(r.docs), ["toy_codec", "toy_use"])
        for stem, d in r.docs.items():
            with self.subTest(doc=stem):
                self.assertEqual(d["extraction"]["config"]["path"], "tests_m2/fixtures/go_frontend/toy_config.json")
                self.assertEqual(d["target"]["commit"], "0" * 40)
                self.assertEqual(H.grammar_problems(d), [])
                if H.GO_SCHEMA.exists():
                    self.assertEqual(H.validate(d, H.GO_SCHEMA), [])
        r2 = H.Run.toy()
        try:
            self.assertEqual(r2.texts, r.texts, "two runs differ")
        finally:
            r2.cleanup()

    def test_primitive_assumption(self):
        ids = [a["id"] for a in self.docs["toy_codec"]["assumptions"]]
        self.assertIn("go-prim:toy.local/fixture/prim.ToWord", ids)
        self.assertNotIn("go-prim:toy.local/fixture/prim.ToWord",
                         [a["id"] for a in self.docs["toy_use"]["assumptions"]])
        self.assertEqual(H.reads(self.docs, f"({C}.Frame).Tag", via=True), [(9, 4, "to_array")])

    def test_functions_and_path_reasons(self):
        fs = self.docs["toy_codec"]["go"]["functions"]
        self.assertIn(f"({C}.Frame).kind", fs)
        self.assertNotIn(f"{C}.init", fs)
        self.assertEqual(fs[f"{C}.Sum"]["paths_reason"], "loop")
        self.assertEqual(fs[f"{C}.NewBuf"]["paths_reason"], "not_codec")
        self.assertIsNotNone(fs[CHECK]["paths"])
        self.assertEqual(len(fs[CHECK]["paths"]), 8)


class TestToyCodecs(_Toy):
    def test_encoder_layouts(self):
        encs = {e["function"]: e for e in H.section(self.docs, "codecs", "encoders")}
        self.assertEqual(sorted(encs), sorted([RECA, RECB, STAMP]))
        r = ["param", "r"]
        a = encs[RECA]
        self.assertEqual((a["length"], a["exact"], a["conds"]),
                         (13, True, [[["<=", ["len", ["field", r, "memo"]], ["const", 0]]]]))
        self.assertEqual(a["cells"],
                         [["const", 7]] + byte_cells(["field", r, "Seq"], 8) + byte_cells(["field", r, "Tag"], 4))
        b = encs[RECB]
        ra = ["field", r, "RecA"]
        self.assertEqual(b["conds"], [[["<=", ["len", ["field", r, "memo"]], ["const", 0]]]], "RecB reads its own memo")
        self.assertEqual(b["cells"], [["const", 8]] + byte_cells(["field", ra, "Seq"], 8) +
                         byte_cells(["field", ra, "Tag"], 4) + byte_cells(["field", r, "Tail"], 8))
        s = encs[STAMP]
        self.assertEqual(s["cells"], [["const", 9]] + [["const", 0]] * 7 + [["const", 5]] + [["const", 0]] * 12)

    def test_partiality_on_probes(self):
        exp = {"check": check_ok, "Seq": check_ok, "Tag": check_ok,
               "Tail": lambda p: check_ok(p) and p.b0 >= 8, "kind": lambda p: p.n >= 1, "Kind": lambda p: p.n >= 1}
        for m, want in exp.items():
            with self.subTest(method=m):
                f = self.fn(f"({C}.Frame).{m}")
                bad = [p for p in toy_probes() if H.outcome(f, p) != ("ok" if want(p) else "err")]
                self.assertEqual(bad[:5], [])
        f = self.fn(f"({C}.Frame).Unsafe")
        bad = [p for p in toy_probes() if H.outcome(f, p) != ("panic" if p.cap < 21 else "ok")]
        self.assertEqual(bad[:5], [])

    def test_decoders_predicates_matches_absences(self):
        c = self.docs["toy_codec"]["go"]["codecs"]
        self.assertEqual([(d["function"].rsplit(".", 1)[1], [(r["offset"], r["width"], r["via"]) for r in d["reads"]])
                          for d in c["decoders"]],
                         [("Kind", [(0, 1, "index")]), ("Seq", [(1, 8, "be_uint")]), ("Tag", [(9, 4, "to_array")]),
                          ("Tail", [(13, 8, "be_uint")]), ("Unsafe", [(13, 8, "be_uint")]),
                          ("kind", [(0, 1, "index")])])
        self.assertEqual(c["predicates"], [{"function": CHECK, "param": "f", "tag_index": 0,
                                            "accepts": [{"value": 7, "length": 13}, {"value": 8, "length": 21},
                                                        {"value": 9, "length": 21}]}])
        self.assertEqual([(m["value"], m["length"], m["encoders"]) for m in c["matches"]],
                         [(7, 13, [RECA]), (8, 21, [RECB]), (9, 21, [STAMP])])
        self.assertEqual(c["absences"], [{"predicate": CHECK, "index": 0, "value": 9, "length": 21,
                                          "elsewhere": [STAMP]}])

    def test_patch(self):
        p = self.docs["toy_use"]["go"]["codecs"]["patches"]
        self.assertEqual([(x["function"], x["encoder"], [(w["index"], w["value"], w["site"].split(":")[1])
                                                         for w in x["writes"]], x["returned"], x["guards"]) for x in p],
                         [(PATCH, RECB, [(0, 9, "38")], True, [])])


class TestToyPartialitySites(_Toy):
    def site_table(self, fid):
        return [(s["id"].split(":")[1], s["kind"], s["status"], s["witness"]) for s in self.fn(fid)["sites"]]

    def test_scan_is_open_from_word_12_and_scansafe_is_safe(self):
        self.assertEqual(sorted(self.site_table(f"{C}.Scan")),
                         sorted([("170", "index", "safe", None),
                                 ("171", "index", "open", {"var": "i", "min": 12, "max": 15}),
                                 ("173", "slice", "safe", None), ("173", "slice", "safe", None)]))
        self.assertEqual(sorted(self.site_table(f"{C}.ScanSafe")),
                         sorted([("181", "index", "safe", None), ("182", "index", "safe", None),
                                 ("184", "slice", "safe", None), ("184", "slice", "safe", None)]))

    def test_unsafe_and_sum(self):
        self.assertEqual(self.site_table(f"({C}.Frame).Unsafe"), [("124", "slice", "open", None)])
        self.assertEqual(sorted(self.site_table(f"{C}.Sum")),
                         [("159", "index", "open", None), ("161", "index", "safe", None)])
        for g in ("check", "kind", "Kind", "Seq", "Tag", "Tail"):
            with self.subTest(getter=g):
                self.assertTrue(all(s["status"] == "safe" for s in self.fn(f"({C}.Frame).{g}")["sites"]))


class TestToySlices(_Toy):
    def test_backing_results(self):
        b = ["param", "b"]
        head, body = ["field", b, "head"], ["field", b, "body"]
        s = ["op", "+", ["len", head], ["len", body]]
        j = H.result_entry(self.docs, f"{BUF}.Joined", 0)["cases"]
        self.assertEqual([(c["backing"][0], c["offset"], c["len"], c["cap"], c["cond"]) for c in j],
                         [("of", ["const", 0], s, ["cap", head], [["<=", s, ["cap", head]]]),
                          ("fresh", ["const", 0], s, ["unknown", "growth"], [[">", s, ["cap", head]]])])
        self.assertEqual(j[0]["backing"], ["of", head])
        self.assertTrue(j[1]["backing"][1].startswith("codec/codec.go:142:"))
        self.assertEqual(H.result_entry(self.docs, f"{BUF}.Body", 0)["cases"],
                         [{"cond": [], "backing": ["of", body], "offset": ["const", 0], "len": ["len", body],
                           "cap": ["cap", body]}])
        cp = H.result_entry(self.docs, f"{BUF}.Copy", 0)["cases"]
        self.assertEqual([(c["backing"][0], c["len"]) for c in cp], [("fresh", s)])
        self.assertTrue(cp[0]["backing"][1].startswith("codec/codec.go:150:"))
        sc = H.result_entry(self.docs, f"{C}.Scan", 0)["cases"]
        self.assertEqual(sorted(c["backing"][0] for c in sc), ["fresh", "none"])
        ra = H.result_entry(self.docs, RECA, 0)["cases"]
        self.assertEqual([c["backing"][0] for c in ra], ["of", "fresh"])
        self.assertEqual((ra[1]["len"], ra[1]["cap"]), (["const", 13], ["const", 13]))

    def test_writes_stores_lost_writes(self):
        w = [(x["function"], x["site"].split(":")[0] + ":" + x["site"].split(":")[1], x["via"], x["backing"],
              x["from"]) for x in H.section(self.docs, "slices", "writes")]
        b = ["param", "b"]
        head, body = ["field", b, "head"], ["field", b, "body"]
        memo = ["field", ["param", "r"], "memo"]
        self.assertEqual(sorted(w, key=json.dumps), sorted([
            (f"{BUF}.Add", "codec/codec.go:137", "append", ["of", head], ["len", head]),
            (f"{BUF}.Add", "codec/codec.go:138", "append", ["of", body], ["len", body]),
            (f"{BUF}.Joined", "codec/codec.go:142", "append", ["of", head], ["len", head]),
            (PATCH, "use/use.go:38", "index", ["of", memo], ["const", 0])], key=json.dumps))
        st = [(x["function"], x["site"].split(":")[1], x["target"]) for x in H.section(self.docs, "slices", "stores")]
        self.assertEqual(st, [(f"{BUF}.Add", "137", head), (f"{BUF}.Add", "138", body)])
        lw = [(x["function"], x["site"].split(":")[1], x["param"], x["field"])
              for x in H.section(self.docs, "slices", "lost_writes")]
        self.assertEqual(lw, [(RECA, "44", "r", ["memo"]), (RECB, "57", "r", ["memo"])])


class TestToyCalls(_Toy):
    def test_edges(self):
        e = {(x["caller"], x["callee"], x["site"].rsplit(":", 1)[0]): x for x in H.section(self.docs, "calls", "edges")}
        top = e[(f"{U}.Top", f"{U}.mid", "use/use.go:45")]
        self.assertEqual((top["kind"], top["callee_kind"], top["in_loops"]), ("call", "analyzed", ["use/use.go:44"]))
        self.assertEqual(e[(f"{U}.mid", f"{C}.Scan", "use/use.go:53")]["callee_kind"], "analyzed")
        self.assertEqual(e[(f"({C}.Frame).Tag", "toy.local/fixture/prim.ToWord", "codec/codec.go:109")]["callee_kind"],
                         "primitive")
        dyn = [x for k, x in e.items() if k[0] == f"{C}.Forever"]
        self.assertEqual([(x["callee"], x["callee_kind"]) for x in dyn], [("dynamic:Read", "dynamic")])
        self.assertEqual(e[(f"{C}.Scan", "fmt.Errorf", "codec/codec.go:171")]["callee_kind"], "external")

    def test_flows(self):
        flows = {(f["producer"], f["caller"]): f for f in H.section(self.docs, "calls", "flows")}
        self.assertEqual(sorted(flows), sorted([(f"{BUF}.Joined", f"{U}.Consume"), (f"{BUF}.Joined", f"{U}.Hold"),
                                                (RECB, PATCH)]), "Copy is not a view: Fresh has no flow")
        con = flows[(f"{BUF}.Joined", f"{U}.Consume")]
        self.assertEqual(H.use_kinds(con["uses"]), [("arg", f"{C}.Sum", 0), ("len", None, None)])
        self.assertEqual((con["held_across"], con["opaque_between"]), ([], []))
        self.assertEqual([(i["callee"], i["param"], H.use_kinds(i["uses"])) for i in con["into"]],
                         [(f"{C}.Sum", 0, [("index", None, None), ("len", None, None)])])
        hold = flows[(f"{BUF}.Joined", f"{U}.Hold")]
        self.assertEqual(H.use_kinds(hold["uses"]), [("index", None, None)])
        self.assertEqual([(h["callee"], h["site"].rsplit(":", 1)[0]) for h in hold["held_across"]],
                         [(f"{BUF}.Add", "use/use.go:19")])
        pat = flows[(RECB, PATCH)]
        self.assertEqual(H.use_kinds(pat["uses"]), [("index_store", None, None), ("return", None, 0)])


class TestToyLoops(_Toy):
    def test_loops_and_debt(self):
        n, lo, hi = ["param", "n"], ["param", "lo"], ["param", "hi"]
        want = {
            f"{C}.Sum": [("codec/codec.go:158", "counted", "i", ["const", 0], 1, "<", n, n, []),
                         ("codec/codec.go:161", "range", None, ["const", 0], 1, "<", ["len", ["param", "xs"]],
                          ["len", ["param", "xs"]], [])],
            f"{C}.Scan": [("codec/codec.go:169", "counted", "i", ["const", 0], 1, "<", ["const", 16], ["const", 16],
                           ["return"])],
            f"{C}.ScanSafe": [("codec/codec.go:180", "counted", "i", ["const", 0], 1, "<", ["const", 16],
                               ["const", 16], ["return"])],
            f"{C}.Forever": [("codec/codec.go:191", "unbounded", None, None, None, None, None, None, ["return"])],
            f"{C}.Between": [("codec/codec.go:204", "counted", "n", lo, 1, "<=", hi,
                              ["op", "+", ["op", "-", hi, lo], ["const", 1]], [])],
            f"{U}.Top": [("use/use.go:44", "range", None, ["const", 0], 1, "<", ["len", ["param", "ds"]],
                          ["len", ["param", "ds"]], [])],
        }
        loops = H.section(self.docs, "loops")
        for fid, w in want.items():
            with self.subTest(function=fid):
                self.assertEqual([H.loop_shape(l) for l in loops if l["function"] == fid], w)
        self.assertEqual(sorted({l["function"] for l in loops}), sorted(want))
        debt = {(d["function"], d["kind"], d["where"]) for d in H.section(self.docs, "coverage", "debt")}
        self.assertIn((f"{C}.Forever", "loop_bound", "codec/codec.go:191"), debt)


class TestSsadumpHelper(_Toy):
    def test_the_helper_is_generic_relative_and_deterministic(self):
        """ssadump, built by the extractor into ~/.holon/tools, prints a deterministic holon-ssadump/0.1 document with
        positions relative to -dir on a scratch copy of the toy."""
        _ = self.docs
        key = H.ssadump_sha256()[:16]
        binary = Path.home() / ".holon" / "tools" / "ssadump" / key / "ssadump"
        self.assertTrue(binary.is_file(), binary)
        ws = Path(tempfile.mkdtemp(prefix="holon-i18-ssa-"))
        try:
            shutil.copytree(H.TOY, ws / "toy")
            outs = []
            for _i in range(2):
                p = subprocess.run([str(binary), "-dir", str(ws / "toy"), "./codec", "./use"], capture_output=True,
                                   text=True, timeout=600,
                                   env={**os.environ, "GOFLAGS": "-mod=readonly", "GOTOOLCHAIN": "local"})
                self.assertEqual(p.returncode, 0, p.stderr[-2000:])
                outs.append(p.stdout)
            self.assertEqual(outs[0], outs[1])
            doc = json.loads(outs[0])
            self.assertEqual(doc.get("ssadump_version"), H.SSADUMP_VERSION)
            self.assertNotIn(str(ws), outs[0])
        finally:
            shutil.rmtree(ws, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
