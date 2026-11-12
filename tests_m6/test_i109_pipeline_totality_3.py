"""I109 (M6, generality): pipeline totality, pass 3. Contract tests (spec/M6/predictions/I109.json;
prompts/I109_pipeline_totality_3.md).

The blockers I108 measured, each fixed by the IR's or the language's semantics, never by a corpus entry. A write or a
value that cannot be modelled soundly stays a havoc (an over-approximation) or a refusal, never a guess:

  (a) Types gaps of the Go machine rendering (holon.frontends.go_machines, holon.sorts.model3):
      A1 a static call of a method outside the document's packages passes its receiver as its first argument (go/ssa's
         calling convention: a method's Function has the receiver as Params[0]); the call's signature in info.members
         counts it, as an interface call's does ("*"), so every ["call", fn, args...] term has exactly as many args as
         its member has inputs;
      A2 len of a value that is not a string or a byte slice (a slice, map, array or channel, rendered as an opaque
         word) is an opaque call of the builtin len (A-env: a function of its argument), never ["len", w];
      A3 in a Go machine document, a write of a whole string field writes its slot with a free value (a havoc of
         the field: an environment member keyed by the written term); it touches the slot it writes;
      A4 a write of a whole map stays refused (no finite store states "every key reset").
  (b) The Go machine frontend's toolchain rule: a config with "toolchain": "go_directive" runs the lowest pinned
      release of config/toolchains.json go_set at or above the source's go directive (I103's rule and code), and the
      document's extraction.tool.go names it.
  (c) D9 sign rule SG1 (holon.analysis.closure.sign): a signed comparison whose two operands are both provably below
      2^255 as unsigned words (a literal below 2^255, ["trunc", N, x] with N <= 255, a len, a boolean operator, or a
      register read of a family declared bool, address or uint<N> with N < 256) orders them exactly as the unsigned
      comparison does, so it takes the unsigned operator's sign; any other signed comparison stays "?" (a signed
      order is not monotone under an unsigned increase).
  (d) SP_b in a Go machine document, Q61's opaque-key fallback: the key word of a string- or bytes-keyed map step is
      an environment member keyed by the key's term (syntactically equal keys share it; any two others are free, so
      never equated or ordered to prove anything, and a read after a write to a syntactically different key is
      unconstrained). A Solidity document's SP_b refusal is unchanged.
  (e) The Solidity term-size budget: a transitions sidecar may name "term_budget" (a positive integer); the walker
      renders under it and the document records it in extraction.term_budget; a sidecar without the key renders
      under TERM_BUDGET (400000) and its document is byte-identical to before (no key). spec/M6/lib/i109_run.json
      names the M6 tier.
  (g) Q60's constructor rule and Q64's default: machines.nil_maps is "unknown" unless the config says "zero" (the
      only opt-out, recorded in the document's extraction.machines). Under "unknown", a map field of T is non-nil in
      R0 iff T has a constructor (a function of the document's packages, not a method, returning T or *T) and on
      every return of every constructor the returned T's field was stored a made map (MakeMap) in a block that
      dominates the return; and no action writes the field whole. Every element write into another map field is
      nil_map debt, and the typed model refuses the document. I105's demo Vault has no constructor: its law is
      re-decided UNKNOWN.
  (h) Q62: a missing link sidecar means no codec components (holon.diagram.linked.load_sidecars gives no roles).

The planted fixture tests_m6/fixtures/i109 is written for these tests; its expectations are known from its source by
construction. The corpus smoke measures are results/M6/I109/holon/corpus.json (python -m holon eval holon --protocol
spec/M6/lib/i109_run.json) and results/M6/I109/go_machines.json (python -m holon eval go-machines --protocol
spec/M6/lib/i109_run.json).
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i109"
SRC = FIX / "src"
PROTO = "spec/M6/lib/i109_run.json"
HOLON_CORPUS = ROOT / "results" / "M6" / "I109" / "holon" / "corpus.json"
GO_CORPUS = ROOT / "results" / "M6" / "I109" / "go_machines.json"
BASE = "55c679dfe5d9667a85ad94834ba945e33443bc71"   # the lead's M6 tools landing (Morph's record as landed, re-stamped)
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
GAP_TEXTS = ("the length of a w value", "a write of a whole string")


def run_holon(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=ENV, capture_output=True, text=True,
                          timeout=timeout)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def extract(cfg: Path, out: Path, src: Path = SRC) -> dict:
    p = run_holon(["extract", "go_machines", "--root", str(ROOT), "--config", str(cfg), "--src", str(src),
                   "--out-dir", str(out)])
    if p.returncode != 0:
        raise AssertionError(p.stderr[-3000:])
    return {json.loads(x.read_text(encoding="utf-8"))["contract"]: x for x in sorted(out.glob("*.extracted.json"))}


def typed_stages(docs: list[Path], tmp: Path, tag: str, src: Path = SRC) -> tuple[dict, Path, str, str]:
    """I51's typed steps (holon_run._rules: sorts, types, model, disch, derive) over docs in one milestone."""
    from holon.eval import common, holon_run as H
    proto = json.loads(json.dumps(common.load_json(ROOT / PROTO)))
    S = H.scratch_root(ROOT, tmp, f"holon/i109-{tag}", src)
    rel = f"results/eval/holon/i109{tag}"
    (S / rel / "sidecars").mkdir(parents=True)
    (S / rel / "facts").mkdir(parents=True)
    for d in docs:
        shutil.copy(d, S / rel / "facts" / d.name)
    stages: dict = {}
    R = H.Runner(H.Ctx(tmp, src), S, proto, {})
    H._rules(R, S, rel, proto["milestone"], proto, [{"file": d.name} for d in docs], stages)
    return stages, S, rel, proto["milestone"]


def calls(t, out: list) -> list:
    if isinstance(t, list):
        if t[:1] == ["call"] and len(t) >= 2 and isinstance(t[1], str):
            out.append(t)
        for x in t:
            calls(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            calls(x, out)
    return out


class _Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i109-"))
        cls.dflt = extract(FIX / "go_config.json", cls.tmp / "default")
        cls.zero = extract(FIX / "go_config_zero.json", cls.tmp / "zero")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def doc(self, which: dict, typ: str) -> dict:
        (k,) = [k for k in which if k.endswith("." + typ)]
        return json.loads(which[k].read_text(encoding="utf-8"))

    def path(self, which: dict, typ: str) -> Path:
        (k,) = [k for k in which if k.endswith("." + typ)]
        return which[k]

    def stages_ok(self, typ: str, upto=("sorts", "types", "model")):
        tmp = Path(tempfile.mkdtemp(prefix=f"holon-i109-{typ.lower()}-"))
        try:
            stages, S, _rel, M = typed_stages([self.path(self.dflt, typ)], tmp, typ.lower())
            for st in upto:
                self.assertEqual(stages[st]["status"], "ok", f"{typ} {st}: {stages[st]['detail'][-2000:]}")
            return "".join(p.read_text(encoding="utf-8") for p in sorted((S / "gen" / M / "sorts" / "models")
                                                                          .glob("*.bend")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestTypesGaps(_Fixture):
    """P1: (a) A1-A4."""

    def test_p1_a1_call_arity_counts_the_receiver(self):
        d = self.doc(self.dflt, "Counter")
        mem = d["info"]["members"]
        cs = calls(d["actions"], [])
        self.assertTrue(any(c[1].endswith(").IsZero") for c in cs), cs)
        for c in cs:
            self.assertIn(c[1], mem, c[1])
            self.assertEqual(len(mem[c[1]][0]["inputs"]), len(c) - 2, c)

    def test_p1_a2_len_of_a_word_is_an_opaque_call(self):
        d = self.doc(self.dflt, "Counter")
        text = json.dumps(d["actions"])
        self.assertNotIn('["len", ["param", "cs"]]', text)
        self.assertTrue(any(c[1] == "len" for c in calls(d["actions"], [])), text[:2000])

    def test_p1_counter_compiles(self):
        self.stages_ok("Counter")

    def test_p1_a3_whole_string_write_is_a_havoc(self):
        text = self.stages_ok("Named")
        self.assertIn("go.string.", text)

    def test_p1_a4_whole_map_write_stays_refused(self):
        from holon.sorts import model3
        import inspect
        self.assertIn("a write of a whole", inspect.getsource(model3.Gen))


class TestGoToolchain(unittest.TestCase):
    """P2: (b) the go-directive rule in the Go machine frontend."""

    def test_p2_go_directive_selects_the_lowest_release_at_or_above(self):
        from holon.frontends.go import toolchains as TC
        sets = json.loads((ROOT / "config" / "toolchains.json").read_text(encoding="utf-8"))
        want = TC.select_go("1.25", sorted(sets["go_set"]["releases"]))
        self.assertTrue(want)
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-go125-"))
        try:
            got = extract(FIX / "go125" / "go_config.json", tmp, FIX / "go125" / "src")
            (p,) = got.values()
            d = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(d["extraction"]["tool"]["go"], "go" + want)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p2_without_the_rule_the_pin_runs(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-pin-"))
        try:
            got = extract(FIX / "go_config.json", tmp)
            holon_cfg = json.loads((ROOT / "config" / "holon.json").read_text(encoding="utf-8"))
            pin = holon_cfg["replay"]["go_version"].split()[2]
            for p in got.values():
                self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["extraction"]["tool"]["go"], pin)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSignedSign(unittest.TestCase):
    """P3: (c) D9's rule SG1."""

    def test_p3_nonnegative_operands_take_the_unsigned_sign(self):
        from holon.analysis.closure import sign
        p = ["storage", "x"]
        for op, uop in (("s<", "<"), ("s<=", "<="), ("s>", ">"), ("s>=", ">=")):
            t = [op, ["trunc", 64, p], 10]
            self.assertEqual(sign(t, "x"), sign([uop, ["trunc", 64, p], 10], "x"), t)
            self.assertNotEqual(sign(t, "x"), "?", t)

    def test_p3_other_signed_comparisons_stay_unknown(self):
        from holon.analysis.closure import sign
        p = ["storage", "x"]
        for t in (["s<", ["sext", 64, p], 10], ["s<", p, 10], ["s>", ["trunc", 64, p], 2 ** 255],
                  ["s<", ["trunc", 256, p], 1]):
            self.assertEqual(sign(t, "x"), "?", t)

    def test_p3_sg1_is_exact_on_random_words(self):
        """Below 2^255 the two's-complement order of 256-bit words is the unsigned order (the planted check)."""
        rnd = random.Random(109)
        for _ in range(20000):
            n = rnd.choice((8, 64, 128, 255))
            a, b = rnd.randrange(2 ** n), rnd.randrange(2 ** n)
            sa = a - 2 ** 256 if a >= 2 ** 255 else a
            sb = b - 2 ** 256 if b >= 2 ** 255 else b
            self.assertEqual(sa < sb, a < b)


class TestStringKeys(_Fixture):
    """P4: (d) Q61's opaque-key fallback, Go machine documents only."""

    def test_p4_names_compiles_with_opaque_keys(self):
        text = self.stages_ok("Names")
        self.assertIn("go.key.", text)

    def test_p4_solidity_sp_b_unchanged(self):
        from holon.sorts import model3
        import inspect
        self.assertIn("not compiled in the structural mode", inspect.getsource(model3.Gen.map_key))


class TestTermBudget(unittest.TestCase):
    """P5: (e) the recorded term budget."""

    def _side(self, tmp: Path, budget):
        tr = {"commit_interfaces": [], "contract": "Wide"}
        if budget is not None:
            tr["term_budget"] = budget
        side = {"sidecar_version": 1, "frontend": "solidity", "doc": "I109 (e) fixture",
                "target": {"repo": "holon/i109", "commit": "0" * 40, "scope": "contract Wide"},
                "output": str(tmp / "wide.extracted.json"), "sources": ["Wide.sol"],
                "compiler": {"version": "0.8.24", "settings": {"optimizer": {"enabled": False}}},
                "transitions": tr}
        p = tmp / f"wide_{budget}.json"
        p.write_text(json.dumps(side, indent=1, sort_keys=True) + "\n")
        return p

    def _extract(self, budget):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-budget-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        p = self._side(tmp, budget)
        out = tmp / "out.json"
        r = run_holon(["extract", "solidity", "--root", str(ROOT), "--sidecar", str(p), "--source",
                       str(FIX / "sol"), "--out", str(out)])
        return r, (json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None)

    def test_p5_small_budget_refuses_and_names_it(self):
        r, d = self._extract(5)
        self.assertNotEqual(r.returncode, 0)
        self.assertIsNone(d)
        self.assertIn("size budget of 5 nodes", r.stderr)

    def test_p5_budget_recorded(self):
        r, d = self._extract(4000000)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertEqual(d["extraction"]["term_budget"], 4000000)

    def test_p5_default_records_nothing(self):
        r, d = self._extract(None)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertNotIn("term_budget", d["extraction"])

    def test_p5_protocol_names_the_m6_tier(self):
        proto = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(proto["solidity"]["term_budget"], 4000000)


class TestNilMapDefault(_Fixture):
    """P6: (g) the constructor rule and Q64's default."""

    def nil(self, which, typ):
        return sorted({x["action"] for x in self.doc(which, typ)["debt"] if x["kind"] == "nil_map"})

    def test_p6_default_and_constructor_rule(self):
        self.assertEqual(self.nil(self.dflt, "Bare"), ["Credit"])     # no constructor: R0 is the zero value
        self.assertEqual(self.nil(self.dflt, "Loose"), ["Credit"])    # a constructor path leaves Bal nil
        self.assertEqual(self.nil(self.dflt, "Made"), [])             # every constructor return has Bal made
        self.assertEqual(self.nil(self.dflt, "Names"), [])
        for typ in ("Bare", "Loose", "Made", "Names"):
            self.assertEqual(self.doc(self.dflt, typ)["extraction"]["machines"], {"nil_maps": "unknown"})

    def test_p6_explicit_opt_out_is_recorded(self):
        for typ in ("Bare", "Loose", "Made", "Names", "Counter", "Named"):
            self.assertEqual(self.nil(self.zero, typ), [])
            self.assertEqual(self.doc(self.zero, typ)["extraction"]["machines"], {"nil_maps": "zero"})

    def test_p6_made_compiles_bare_refused(self):
        self.stages_ok("Made")
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-bare-"))
        try:
            stages, _S, _rel, _M = typed_stages([self.path(self.dflt, "Bare")], tmp, "bare")
            self.assertNotEqual(stages["types"]["status"], "ok")
            self.assertIn("nil map", stages["types"]["detail"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p6_i105_demo_redecided_unknown(self):
        demo = ROOT / "tests_m6" / "fixtures" / "i105_demo"
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-demo-"))
        try:
            got = extract(demo / "go_config.json", tmp / "docs", demo / "src")
            (p,) = got.values()
            d = json.loads(p.read_text(encoding="utf-8"))
            self.assertTrue([x for x in d["debt"] if x["kind"] == "nil_map"])
            stages, _S, _rel, _M = typed_stages([p], tmp, "demo", demo / "src")
            self.assertNotEqual(stages["types"]["status"], "ok")
            self.assertIn("nil map", stages["types"]["detail"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestNoLinkSidecar(unittest.TestCase):
    """P7: (h) Q62."""

    def test_p7_missing_link_sidecar_means_no_components(self):
        from holon.diagram import linked as L
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-q62-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "lib").mkdir()
        (tmp / "lib" / "ad.json").write_text(json.dumps({"derive_extracted_version": "x", "documents": []}))
        ad, roles, shas = L.load_sidecars(tmp, "lib/ad.json", "lib/link.json")
        self.assertEqual(roles, {})
        self.assertNotIn("lib/link.json", shas)
        self.assertEqual(L.render_all(tmp, "M9", "lib/ad.json", "lib/link.json"), {})

    def test_p7_a_present_but_broken_link_sidecar_still_refuses(self):
        from holon.diagram import linked as L
        tmp = Path(tempfile.mkdtemp(prefix="holon-i109-q62b-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "lib").mkdir()
        (tmp / "lib" / "ad.json").write_text(json.dumps({"derive_extracted_version": "x", "documents": []}))
        (tmp / "lib" / "link.json").write_text("{}")
        with self.assertRaises(L.SidecarError):
            L.load_sidecars(tmp, "lib/ad.json", "lib/link.json")


class TestCorpusSmoke(unittest.TestCase):
    """P8-P12: smoke measures on I51's 20 entries (contaminated by I51/I103/I105/I108; I107 scores)."""

    @classmethod
    def setUpClass(cls):
        key = json.loads((ROOT / "spec" / "M6" / "predictions" / "I109.json").read_text(encoding="utf-8"))
        cls.pred = {p["id"]: p for p in key["predictions"]}

    def rows(self, p: Path) -> dict:
        self.assertTrue(p.is_file(), f"{p.relative_to(ROOT)} is missing")
        return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}

    def test_p8_no_go_directive_refusal_on_go_machines(self):
        g = self.rows(GO_CORPUS)
        bad = sorted(i for i, r in g.items() if "requires go >=" in json.dumps(r) or "go.mod requires go" in json.dumps(r))
        self.assertEqual(bad, [])

    def test_p9_no_named_types_gap_remains(self):
        g = self.rows(GO_CORPUS)
        bad = []
        for i, r in sorted(g.items()):
            t = json.dumps((r.get("stages") or {}).get("types") or {})
            if any(x in t for x in GAP_TEXTS) or ("arguments, the term gives" in t):
                bad.append(i)
        self.assertEqual(bad, [])

    def test_p10_no_budget_refusal_under_the_tier(self):
        h = self.rows(HOLON_CORPUS)
        bad = sorted((i, d.get("file")) for i, r in h.items() for d in r.get("documents") or []
                     if "size budget of" in str(d.get("reason") or ""))
        self.assertEqual(bad, [])

    def test_p11_go_machine_entries_past_types(self):
        g = self.rows(GO_CORPUS)
        n = sum(1 for r in g.values() if ((r.get("stages") or {}).get("types") or {}).get("status") == "ok")
        self.assertGreaterEqual(n, self.pred["I109-P11"]["expected"]["past_types_at_least"])

    def test_p12_every_miss_has_stage_and_reason_and_no_verdict(self):
        h, g = self.rows(HOLON_CORPUS), self.rows(GO_CORPUS)
        for i, r in sorted(h.items()):
            st = r.get("stages") or {}
            for k, v in st.items():
                if v.get("status") not in ("ok", "not_applicable", "not_run"):
                    self.assertTrue((v.get("detail") or "").strip(), f"{i}: stage {k} has no reason")
            self.assertFalse(any(x.get("status") in ("PROVED", "REFUTED") for x in r.get("laws") or []
                                 if isinstance(x, dict)), i)
        for i, r in sorted(g.items()):
            if r.get("pipeline") != "complete":
                self.assertTrue(r.get("refused_at"), i)

    def test_p13_extraction_reach(self):
        h, g = self.rows(HOLON_CORPUS), self.rows(GO_CORPUS)
        out = {i for i, r in h.items() if any(d.get("status") == "extracted" for d in r.get("documents") or [])}
        out |= {i for i, r in g.items() if r.get("machines")}
        self.assertGreaterEqual(len(out), self.pred["I109-P13"]["expected"]["at_least"])


class TestRegressions(unittest.TestCase):
    def test_r1_morph_record_moves_only_by_restamp(self):
        """Compared as G1 compares: generator_sha256 and every `seconds` stripped, G1_EXCLUDED skipped."""
        from holon.gate import G1_EXCLUDED

        def unstamp(x):
            if isinstance(x, dict):
                return {k: unstamp(v) for k, v in x.items() if k not in ("generator_sha256", "seconds")}
            if isinstance(x, list):
                return [unstamp(v) for v in x]
            return x
        moved = []
        for d in MORPH_DIRS:
            base = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", BASE, "--", d)
                    .decode().splitlines()}
            head = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", "HEAD", "--", d)
                    .decode().splitlines()}
            for p in sorted(set(base) | set(head)):
                if base.get(p) == head.get(p) or p.rsplit("/", 1)[-1] in G1_EXCLUDED:
                    continue
                if p not in base or p not in head or not p.endswith(".json"):
                    moved.append(p)
                    continue
                if unstamp(json.loads(git("cat-file", "blob", base[p]))) != \
                        unstamp(json.loads(git("cat-file", "blob", head[p]))):
                    moved.append(p)
        self.assertEqual(moved, [])

    def test_r2_morph_sidecars_name_no_term_budget(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and isinstance(d.get("transitions"), dict) and "term_budget" in d["transitions"]:
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_r3_morph_has_its_link_sidecars(self):
        """Q62 never applies to Morph: every milestone with an adoption sidecar has its link sidecar."""
        missing = [p.parent.as_posix() for p in sorted((ROOT / "spec").glob("M[0-3]/lib/derive_extracted.json"))
                   if not (p.parent / "link.json").is_file()]
        self.assertEqual(missing, [])

    def test_r4_morph_documents_are_solidity(self):
        """(a), (d) and (g) apply to Go machine documents only: no Morph document is one."""
        go = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/facts/*.extracted.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if (d.get("extraction") or {}).get("frontend") == "go" and (d.get("extraction") or {}).get("kind") == \
                    "transitions":
                go.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(go, [])


if __name__ == "__main__":
    unittest.main()
