"""I123 (M6, generality): the typed model's sort operations. Contract tests (spec/M6/predictions/I123.json;
prompts/I123_typed_sort_operations.md; HUMAN_ANSWERS Q100 (1)).

The wall I118 measured on Aave V3: three documents fall back at the typed runner and at bind, each while the runner
generates its typed model (holon.sorts.model3): a value sort used as a word, or a term needing a definition the typed
model does not hold. These are general gaps of the typed model; nothing here is designed from a spent target's or a
corpus entry's code. Every rule is read from the Solidity and EVM semantics, under the opt-in typed.sort_ops "word"
(a typed sidecar key, written only by holon eval holon when its protocol names it):

  W1  a typed value (a refined sort's word, kind t:<sort>) is read as the 256-bit word it occupies by exactly the
      operations whose result is defined on that word: & | ^ ~, masks, trunc, sext, wbyte, << >>, and + - outside
      checked code. The result is an unrefined word (kind w): it carries no sort, so no law concludes anything about
      the value's sort from it (a typed value's sort is a name over its word, never a predicate the word must meet).
  S1  shl(n, x) (the IR's ["<<", x, n]): x * 2^n mod 2^256; 0 when n >= 256.
  S2  shr(n, x) ([">>", x, n]): floor(x / 2^n); 0 when n >= 256.
  S3  sar(n, x) (["sar", x, n]): x read as two's complement, floor(x / 2^n), sign-extended from bit 255; 0 (x >= 0) or
      2^256 - 1 (x < 0) when n >= 256. Solidity's >> on a signed type is sar (it rounds towards negative infinity in
      every pinned release, 0.5.17 and later); << and >> on a narrow type keep the left operand's type, truncated (the
      frontend's trunc / sext), and are never overflow-checked, even in checked code.
  C1  checked and unchecked + - kept apart: a typed + or - whose term a checked fits of the same action reads keeps the
      typed discipline (an ill-sorted one stays refused); outside checked code (unchecked, assembly, a release below
      0.8.0) it is the wrapping word operation, and its result an unrefined word.
  R1  in a document compiled by a release below 0.8.0, a shift by a non-constant amount is refused: the term does not
      record the amount's type, and there a negative signed amount reverts (0.8.0 and later reject a signed amount at
      compile time).
  D1  a section over the typed model (holon.undo.trace.Trace and its subclasses, holon.gen.symsec's SYM section among
      them) that needs a constant shift the model does not define defines it itself, by the model's own builder.
Anything else stays refused: holon.sorts.model3.GenError, the document falls back (I116/I118's per-document fallback)
and its laws stay UNKNOWN, never guessed.

The planted fixture tests_m6/fixtures/i123/sol is written for these tests from the semantics alone. The real side is
the code the pinned solc compiles, run by the pinned forge (the replay harness's EVM); the model side is the typed
model's own definitions (checked as laws by Bend) and its step evaluator (holon.sorts.evaluate3). The harness is
holon.sorts.sortops_diff. The corpus smoke measures are results/M6/I123/holon/corpus.json; a run on I106's spent targets,
contaminated: post-I107, commits aggregates only (results/M6/I123/sealed.json; Q56, Q72, Q89).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i123" / "sol"
PROTO = "spec/M6/lib/i123_run.json"
OUT = ROOT / "results" / "M6" / "I123"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
BASE_CORPUS = OUT / "base" / "corpus.json"
SEALED = OUT / "sealed.json"
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
REFUSED = {"RSdiv": "sdiv", "RSmod": "smod", "RAddmod": "addmod", "RMulmod": "mulmod", "RSignext": "signextend",
           "RCheckedT": "ill-sorted", "PreVar05": "below 0.8.0", "PreVar06": "below 0.8.0", "PreVar07": "below 0.8.0"}
PRE = ("Pre05", "Pre06", "Pre07")


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I123.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def protocol(name: str = PROTO) -> dict:
    from holon.eval import common
    return json.loads(json.dumps(common.load_json(ROOT / name)))


def D():
    from holon.sorts import sortops_diff
    return sortops_diff


class _Fixture(unittest.TestCase):
    """The fixture's documents, extracted by the pinned solc each file's pragma selects, sorted with and without the
    opt-in in a scratch root (holon.sorts.sortops_diff.Fixture)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i123-"))
        cls.fx = D().Fixture(ROOT, FIX, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


# ----------------------------------------------------------------------------------------------- P1 the semantics
class TestSemantics(_Fixture):
    def test_p1_reference_equals_compiled_code(self):
        cs = D().cases()
        self.assertGreaterEqual(len(cs), pred("I123-P1")["expected"]["cases_at_least"])
        real = self.fx.real("SortOps", cs)
        bad = [(c["id"], D().reference(c), real[c["id"]]) for c in cs if D().reference(c) != real[c["id"]]]
        self.assertEqual(bad[:5], [])

    def test_p1_definitions_checked_by_bend(self):
        cs = D().cases()
        n, out = D().bend_check(cs, [D().reference(c) for c in cs], self.tmp / "bend_ok")
        self.assertEqual(out["code"], 0, out["text"][-2000:])
        self.assertIn("ALL PROOFS CHECK", out["text"])
        self.assertGreaterEqual(n, pred("I123-P1")["expected"]["bend_checked_at_least"])

    def test_p1_wrong_value_rejected(self):
        cs = D().cases()[:3]
        vals = [D().reference(c) for c in cs]
        vals[1] = (vals[1] + 1) % (1 << 256)
        _n, out = D().bend_check(cs, vals, self.tmp / "bend_bad")
        self.assertNotEqual(out["code"], 0)
        self.assertNotIn("ALL PROOFS CHECK", out["text"])


# ----------------------------------------------------------------------------------------------- P2 A/B differential
class TestDifferential(_Fixture):
    def test_p2_sortops_agrees_with_compiled_code(self):
        m = self.fx.model("SortOps", sort_ops=True)
        self.assertIsNotNone(m, self.fx.errors.get(("SortOps", True)))
        dis = self.fx.differential("SortOps", D().cases(), sort_ops=True)
        self.assertEqual(dis[:5], [])

    def test_p2_pre_releases_agree(self):
        for n in PRE:
            with self.subTest(contract=n):
                self.assertIsNotNone(self.fx.model(n, sort_ops=True), self.fx.errors.get((n, True)))
                self.assertEqual(self.fx.differential(n, D().pre_cases(n), sort_ops=True)[:5], [])
                self.assertEqual(self.fx.selected(n), {"Pre05": "0.5.17", "Pre06": "0.6.12", "Pre07": "0.7.6"}[n])


# ----------------------------------------------------------------------------------------------- P3, P4 planted laws
class TestLaws(_Fixture):
    def test_p3_false_laws_rejected(self):
        laws = D().false_laws()
        self.assertGreaterEqual(len(laws), pred("I123-P3")["expected"]["false_laws_at_least"])
        for lw in laws:
            with self.subTest(law=lw["id"]):
                # the compiled code itself refutes the law: its value is not the law's
                self.assertNotEqual(self.fx.real_one(lw), lw["claimed"])
                _n, out = D().bend_check([lw["case"]], [lw["claimed"]], self.tmp / f"false_{lw['id']}")
                self.assertNotEqual(out["code"], 0, lw["id"])

    def test_p4_true_laws_check(self):
        laws = D().true_laws()
        self.assertGreaterEqual(len(laws), pred("I123-P4")["expected"]["true_laws_at_least"])
        for lw in laws:
            with self.subTest(law=lw["id"]):
                self.assertEqual(self.fx.real_one(lw), lw["claimed"])
                _n, out = D().bend_check([lw["case"]], [lw["claimed"]], self.tmp / f"true_{lw['id']}")
                self.assertEqual(out["code"], 0, out["text"][-1500:])


# ----------------------------------------------------------------------------------------------- P5 refusal
class TestRefusal(_Fixture):
    def test_p5_just_outside_each_class_refused(self):
        for n, what in REFUSED.items():
            with self.subTest(contract=n):
                self.assertIsNone(self.fx.model(n, sort_ops=True), n)
                err = self.fx.errors[(n, True)]
                self.assertIn("GenError", err)
                self.assertIn(what, err)

    def test_p5_refused_document_falls_back(self):
        """The composed route's typed runner over SortOps and one refused document: the refused one falls back and no
        law over it is decided; SortOps's laws are as with SortOps alone."""
        res = self.fx.typed_runner(("SortOps", "RSdiv"), PROTO)
        for lid, st in res["laws"].items():
            if res["documents"][lid].endswith("RSdiv.extracted.json"):
                self.assertNotIn(st, ("PROVED", "REFUTED"), lid)


# ----------------------------------------------------------------------------------------------- P6, P11 the opt-in
class TestOptIn(_Fixture):
    def test_p6_without_opt_in_refused_as_before(self):
        self.assertIsNone(self.fx.model("SortOps", sort_ops=False))
        self.assertIn("sar", self.fx.errors[("SortOps", False)])

    def test_p6_models_without_opt_in_unchanged(self):
        """Every fixture document the base language compiles gives the same text with the build as without it (the
        generator with sort_ops off is the pre-I123 generator: holon.sorts.sortops_diff.pre_i123_text)."""
        for n in ("Pre05", "Pre06", "Pre07", "PreVar05", "RCheckedT"):
            with self.subTest(contract=n):
                a = self.fx.model(n, sort_ops=False)
                if a is not None:
                    self.assertEqual(a, self.fx.model_pre_i123(n))

    def test_p11_morph_models_byte_identical(self):
        """Morph's committed typed models regenerate byte-identical (no sidecar of Morph names sort_ops)."""
        n = D().morph_models_changed(ROOT)
        self.assertEqual(n, pred("I123-P6")["expected"]["morph_models_changed"])


# ----------------------------------------------------------------------------------------------- P8 D1 sections
class TestSections(_Fixture):
    def test_p8_section_defines_its_constant_shift(self):
        ok, text = self.fx.section_shift("SortOps", sort_ops=True)
        self.assertTrue(ok, text[-2000:])

    def test_p8_without_opt_in_refused(self):
        # amended (spec/M6/amendments/I123.jsonl): PreVar05, whose model builds without the opt-in
        ok, text = self.fx.section_shift("PreVar05", sort_ops=False)
        self.assertFalse(ok)
        self.assertIn("needs definitions the typed model does not hold", text)


# ----------------------------------------------------------------------------------------------- P7 regressions
class TestRegressions(unittest.TestCase):
    def test_p7_protocol_is_its_base_plus_sort_ops(self):
        b = protocol()
        a = protocol(b["base_protocol"])
        self.assertEqual(b["typed"].pop("sort_ops"), "word")
        b["typed"].pop("sort_ops_doc")
        b.pop("base_protocol")
        a.pop("base_protocol", None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_p7_no_earlier_protocol_or_sidecar_names_sort_ops(self):
        for p in sorted((ROOT / "spec").glob("*/lib/*.json")):
            # amended (spec/M6/amendments/I123.jsonl): base_run.json, the generated union of the landed keys' opt-ins
            # (Q104), names sort_ops once I123 has landed; it is not an earlier key's protocol
            if p.name in ("i123_run.json", "base_run.json"):
                continue
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            it = re.fullmatch(r"I(\d+)", str(d.get("iteration") or ""))
            if it and int(it.group(1)) >= 123:
                continue
            self.assertNotIn("sort_ops", d, p.relative_to(ROOT).as_posix())
            if isinstance(d.get("typed"), dict):
                self.assertNotIn("sort_ops", d["typed"], p.relative_to(ROOT).as_posix())

    def test_p7_sidecar_names_sort_ops_only_under_the_protocol(self):
        from holon.eval import holon_run as H
        self.assertEqual(H.typed_sidecar_keys(protocol()).get("sort_ops"), "word")
        self.assertNotIn("sort_ops", H.typed_sidecar_keys(protocol("spec/M6/lib/i117_run.json")))

    def test_p7_sidecar_value_checked(self):
        from holon.sorts import typed_sidecar
        self.assertEqual(typed_sidecar.sort_ops({"sort_ops": "word"}), "word")
        self.assertIsNone(typed_sidecar.sort_ops({}))
        with self.assertRaises(ValueError):
            typed_sidecar.sort_ops({"sort_ops": "bits"})

    def test_p7_no_bend_escape_hatch(self):
        from holon.sorts import sortops
        for text in sortops.texts():
            self.assertNotIn("?", text)
            self.assertNotIn("@unsafe", text)
            self.assertNotIn("import \"", text)

    def test_p7_holon_names_no_target(self):
        src = (ROOT / "holon" / "sorts" / "sortops.py").read_text(encoding="utf-8").lower()
        for w in ("aave", "eigen", "morph", "scroll"):
            self.assertNotIn(w, src)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i115",
                    "tests-m6-i117", "tests-m6-i119", "tests-m6-i123"):
            self.assertTrue(f"name: {job}" in wf, job)


# ----------------------------------------------------------------------------------------------- P9 corpus (smoke)
class TestCorpus(unittest.TestCase):
    """Smoke on contaminated data: I123's run beside the base protocol's own run on the same base."""

    def rows(self, p: Path) -> dict:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {r["id"]: r for r in d["rows"]}

    def test_p9_no_run_step_lost(self):
        a, b = self.rows(BASE_CORPUS), self.rows(HOLON_CORPUS)
        ok = lambda rs: sum(1 for r in rs.values() if (r.get("stages") or {}).get("run", {}).get("status") == "ok")
        self.assertGreaterEqual(ok(b), ok(a))

    def test_p9_typed_models_not_fewer(self):
        a, b = self.rows(BASE_CORPUS), self.rows(HOLON_CORPUS)
        def n(rs: dict) -> int:
            built = 0
            for r in rs.values():
                m = (r.get("run_runners") or {}).get("milestone") or {}
                if m.get("status") != "ok":
                    continue
                langs = {x.get("language") for x in r.get("documents") or []}
                if "solidity" not in langs:
                    continue
                self.assertEqual(langs, {"solidity"}, f"{r['id']}: the typed runner ran over a mix of languages")
                sol = sum(1 for x in r["documents"] if x.get("status") == "extracted")
                built += sol - int(m.get("fallback_documents") or 0)
            return built
        self.assertGreaterEqual(n(b), n(a))

    def test_p9_no_law_id_committed(self):
        for p in sorted(OUT.rglob("*.json")):
            if "vault" in p.parts:
                continue
            self.assertIsNone(LAW_ID.search(p.read_text(encoding="utf-8")), p.relative_to(ROOT).as_posix())


# ----------------------------------------------------------------------------------------------- P10 spent targets
class TestSealed(unittest.TestCase):
    """A measurement only, contaminated: post-I107 (Q56, Q72, Q89): aggregates and one bundle commitment per target."""

    def test_p10_aggregates_only(self):
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        txt = json.dumps(d)
        self.assertIsNone(LAW_ID.search(txt))
        for k in ("PROVED", "REFUTED", "witness", "plaintext"):
            self.assertNotIn(k, txt)
        for t in d["targets"].values():
            self.assertRegex(t["bundle_sha256"], r"^[0-9a-f]{64}$")
            self.assertIn("decided", t)

    def test_p10_aave_runner_fallbacks(self):
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        (t,) = [v for k, v in d["targets"].items() if "aave" in k.lower()]
        self.assertLessEqual(t["runner_fallback_documents"],
                             pred("I123-P10")["expected"]["aave_runner_fallback_documents_at_most"])

    def test_p10_aave_bind_fallbacks(self):
        # split from test_p10_aave_runner_fallbacks (spec/M6/amendments/I123.jsonl): the bind bound, unchanged
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        (t,) = [v for k, v in d["targets"].items() if "aave" in k.lower()]
        self.assertLessEqual(t["bind_fallback_documents"], 3)


if __name__ == "__main__":
    unittest.main()
