"""I108 (M6, generality): pipeline totality, pass 2. Contract tests (spec/M6/predictions/I108.json;
prompts/I108_pipeline_totality.md).

Five blockers I103 and I105 measured, each fixed by the IR's or the language's semantics, never by a corpus entry:

  (a) holon-sort-types/0.4 is 0.3 plus rules S1-S3 for the IR's signed operators (holon.frontends.solidity.transitions,
      the two's-complement words of intN): S1 a signed comparison ["s<" | "s<=" | "s>" | "s>=", a, b] is a comparison
      event of its operands, as "<" is (the operands share a sort); S2 ["sext", bits, t] is t's value (t flows into the
      result, as through "?"); S3 ["sdiv" | "smod" | "sar", a, b] is an opaque fresh variable with its operands walked,
      as "/" "%" ">>" are (no debt). None of them is a coverage-debt entry. The typed model (holon.sorts.model3)
      compiles S1 as the unsigned order of the words with the sign bit flipped (two's complement) and S2 as sign
      extension of the low bits; sdiv, smod and sar stay outside the generator's language (a types refusal).
  (b) A string- or bytes-keyed mapping stays refused at types (SP_b, "not compiled in the structural mode"): no
      structural key over byte content and no opaque-key fallback is built in I108 (Not done, docs/iterations/I108.md).
  (c) holon.eval.layout (holon-layout/0.1): a unit's Foundry project's remappings (foundry.toml [profile.default], then
      remappings.txt, first (context, prefix) kept, rewritten relative to the checkout root, plus rule L2: foundry's
      base path is the project root) and git submodules initialized at their gitlinked commits only, refusing a URL the
      clone rule excludes or that is not a GitHub repository; every submodule recorded.
  (d) SYM in a multi-model milestone derives per model: holon.sym.typed_models lists every model's (facts, facts doc,
      assignment); the SYM producer derives each model's elements; a law's ref is computed from the model whose facts
      the law names. A single-model milestone derives exactly as before.
  (e) Go nil maps (Q60), the opt-in machines.nil_maps "unknown" of the Go machine config: every write into a Go map
      field (not a KV store) is a doc["debt"] entry of kind "nil_map", and the typed model refuses a Go document that
      carries one, so every law over that machine is UNKNOWN. Without the key nothing changes.

The planted fixture tests_m6/fixtures/i108 is written for these tests; its expectations are known from its source by
construction. The corpus smoke measures are results/M6/I108/holon/corpus.json (python -m holon eval holon --protocol
spec/M6/lib/i108_run.json) and results/M6/I108/go_machines.json (python -m holon eval go-machines --protocol
spec/M6/lib/i108_run.json).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i108"
SRC = FIX / "src"
LAYOUT = FIX / "layout" / "proj"
PROTO = "spec/M6/lib/i108_run.json"
HOLON_CORPUS = ROOT / "results" / "M6" / "I108" / "holon" / "corpus.json"
GO_CORPUS = ROOT / "results" / "M6" / "I108" / "go_machines.json"
BASE = "c2cd112c10f8058dc9e765b60f2e08f32455e8c6"   # the lead I108 is based on (Morph's record as landed)
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
SIGNED = ("s<", "s<=", "s>", "s>=", "sext")
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}


def run_holon(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=ENV, capture_output=True, text=True,
                          timeout=timeout)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def strip_stamp(x):
    if isinstance(x, dict):
        return {k: strip_stamp(v) for k, v in x.items() if k != "generator_sha256"}
    if isinstance(x, list):
        return [strip_stamp(v) for v in x]
    return x


def has_tag(term, tag: str) -> bool:
    return isinstance(term, list) and ((term[:1] == [tag]) or any(has_tag(t, tag) for t in term))


def extract(cfg: Path, out: Path) -> dict:
    p = run_holon(["extract", "go_machines", "--root", str(ROOT), "--config", str(cfg), "--src", str(SRC),
                   "--out-dir", str(out)])
    if p.returncode != 0:
        raise AssertionError(p.stderr[-3000:])
    return {json.loads(x.read_text(encoding="utf-8"))["contract"]: x for x in sorted(out.glob("*.extracted.json"))}


def typed_stages(docs: list[Path], sort_types_version: str, tmp: Path, tag: str) -> tuple[dict, Path, str, str]:
    """I51's typed steps (holon_run._rules: sorts, types, model, disch, derive) over docs in one milestone."""
    from holon.eval import common, holon_run as H
    proto = common.load_json(ROOT / PROTO)
    proto = json.loads(json.dumps(proto))
    proto["typed"]["sort_types_version"] = sort_types_version
    S = H.scratch_root(ROOT, tmp, f"holon/i108-{tag}", SRC)
    rel = f"results/eval/holon/i108{tag}"
    (S / rel / "sidecars").mkdir(parents=True)
    (S / rel / "facts").mkdir(parents=True)
    for d in docs:
        shutil.copy(d, S / rel / "facts" / d.name)
    stages: dict = {}
    R = H.Runner(H.Ctx(tmp, SRC), S, proto, {})
    H._rules(R, S, rel, proto["milestone"], proto, [{"file": d.name} for d in docs], stages)
    return stages, S, rel, proto["milestone"]


class _Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i108-"))
        cls.plain = extract(FIX / "go_config.json", cls.tmp / "plain")
        cls.nil = extract(FIX / "go_config_nil.json", cls.tmp / "nil")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def doc(self, which: dict, typ: str) -> dict:
        (k,) = [k for k in which if k.endswith("." + typ)]
        return json.loads(which[k].read_text(encoding="utf-8"))

    def path(self, which: dict, typ: str) -> Path:
        (k,) = [k for k in which if k.endswith("." + typ)]
        return which[k]


class TestSigned(_Fixture):
    """P1: rules S1-S3 (holon-sort-types/0.4) and the typed model's signed comparison and sign extension."""

    def test_p1_fixture_has_signed_terms(self):
        d = self.doc(self.plain, "Acct")
        text = json.dumps(d["actions"])
        for h in ("s<", "s>", "sext"):
            self.assertIn(json.dumps(h), text, h)

    def test_p1_sorts_03_records_signed_debt(self):
        from holon.sorts import extracted as X
        seeds = json.loads((ROOT / "spec/M3/lib/sort_seeds.json").read_text(encoding="utf-8"))
        w = X.walk("acct", self.doc(self.plain, "Acct"), seeds, X.SORT_TYPES_0_3)
        self.assertTrue({e["head"] for e in w.debt} & set(SIGNED), w.debt)

    def test_p1_sorts_04_has_no_signed_debt(self):
        from holon.sorts import extracted as X
        self.assertEqual(X.SORT_TYPES_0_4, "holon-sort-types/0.4")
        seeds = json.loads((ROOT / "spec/M3/lib/sort_seeds.json").read_text(encoding="utf-8"))
        w = X.walk("acct", self.doc(self.plain, "Acct"), seeds, X.SORT_TYPES_0_4)
        self.assertEqual([e for e in w.debt if e["head"] in SIGNED + ("sdiv", "smod", "sar")], [])

    def test_p1_acct_end_to_end(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i108-acct-"))
        try:
            stages, S, _rel, M = typed_stages([self.path(self.plain, "Acct")], "holon-sort-types/0.4", tmp, "acct")
            for st in ("sorts", "types", "model", "disch", "derive"):
                self.assertEqual(stages[st]["status"], "ok", f"{st}: {stages[st]['detail'][-2000:]}")
            models = sorted((S / "gen" / M / "sorts" / "models").glob("*.bend"))
            text = "".join(p.read_text(encoding="utf-8") for p in models)
            # S1 in the model: the order of the words with the sign bit flipped
            self.assertIn("w_xor(", text)
            laws = sorted(x.stem for x in (S / "laws" / M).glob("L*.json"))
            self.assertTrue(laws, "no law derived on Acct")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSymPerModel(_Fixture):
    """P2: SYM derives per model in a milestone of two models (Acct and Book, no nil-map opt-in)."""

    def test_p2_two_models_derive(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i108-two-"))
        try:
            docs = [self.path(self.plain, "Acct"), self.path(self.plain, "Book")]
            stages, S, rel, M = typed_stages(docs, "holon-sort-types/0.4", tmp, "two")
            for st in ("sorts", "types", "model", "disch", "derive"):
                self.assertEqual(stages[st]["status"], "ok", f"{st}: {stages[st]['detail'][-2000:]}")
            from holon import sym as S_
            models = S_.typed_models(S, M)
            self.assertEqual(sorted(r for r, _f, _a in models), sorted(f"{rel}/facts/{d.name}" for d in docs))
            for p in sorted((S / "laws" / M).glob("L_sym_*.json")):
                law = json.loads(p.read_text(encoding="utf-8"))
                self.assertIn(law["facts"], {r for r, _f, _a in models})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p2_single_model_unchanged(self):
        from holon import sym as S_
        import inspect
        # one model: typed_inputs gives the one model typed_models lists (the derivation of a one-model milestone is
        # the same code path as before)
        self.assertIn("typed_models", inspect.getsource(S_.typed_inputs))


class TestNilMaps(_Fixture):
    """P3: machines.nil_maps "unknown" (Q60)."""

    def test_p3_debt_only_under_the_opt_in(self):
        for typ in ("Acct", "Book"):
            self.assertEqual([d for d in self.doc(self.plain, typ)["debt"] if d["kind"] == "nil_map"], [])
        book = [d for d in self.doc(self.nil, "Book")["debt"] if d["kind"] == "nil_map"]
        self.assertEqual(sorted({d["action"] for d in book}), ["Credit"])
        self.assertTrue(all("Bal" in d["what"] for d in book), book)
        self.assertEqual([d for d in self.doc(self.nil, "Acct")["debt"] if d["kind"] == "nil_map"], [])

    def test_p3_plain_documents_unchanged_by_the_key(self):
        for typ in ("Acct", "Book"):
            a, b = self.doc(self.plain, typ), self.doc(self.nil, typ)
            for k in ("storage", "actions", "info"):
                self.assertEqual(a[k], b[k], f"{typ}.{k}")

    def test_p3_types_refuses_a_nil_map_machine(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i108-nil-"))
        try:
            stages, _S, _rel, _M = typed_stages([self.path(self.nil, "Book")], "holon-sort-types/0.4", tmp, "nil")
            self.assertEqual(stages["sorts"]["status"], "ok", stages["sorts"]["detail"][-2000:])
            self.assertNotEqual(stages["types"]["status"], "ok")
            self.assertIn("nil map", stages["types"]["detail"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestLayout(unittest.TestCase):
    """P4: holon.eval.layout, remappings and submodules (Q59)."""

    def test_p4_project_of(self):
        from holon.eval import layout as L
        self.assertEqual(L.project_of(LAYOUT, "packages/app/src/A.sol"), "packages/app")
        self.assertEqual(L.project_of(LAYOUT, "packages/app/lib/dep/src/D.sol"), "packages/app")
        self.assertIsNone(L.project_of(LAYOUT, "other/B.sol"))

    def test_p4_remappings(self):
        from holon.eval import layout as L
        got = L.remappings(LAYOUT, "packages/app")
        self.assertEqual([r["remapping"] for r in got], [
            "@dep/=packages/app/lib/dep/src/",
            "packages/app/ctx/:@x/=packages/app/lib/x/",
            "@other/=packages/app/lib/other/",
            "packages/app/:lib/=packages/app/lib/",
            "packages/app/:src/=packages/app/src/",
        ])
        self.assertEqual([r["source"] for r in got],
                         ["foundry.toml", "foundry.toml", "remappings.txt", "base_path", "base_path"])

    def test_p4_no_project_no_remapping(self):
        from holon.eval import layout as L
        self.assertEqual(L.remappings(LAYOUT, None), [])

    def _repo(self, url: str) -> Path:
        d = Path(tempfile.mkdtemp(prefix="holon-i108-sm-"))
        e = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@t"}
        g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, env=e)
        g("init", "-q")
        (d / ".gitmodules").write_text(f'[submodule "dep"]\n\tpath = lib/dep\n\turl = {url}\n')
        g("add", ".gitmodules")
        g("update-index", "--add", "--cacheinfo", "160000,1111111111111111111111111111111111111111,lib/dep")
        g("commit", "-qm", "t")
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def test_p4_submodule_url_not_github_refused(self):
        from holon.eval import layout as L
        d = self._repo("https://example.org/x/dep.git")
        head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        (r,) = L.submodules(d, head, "https://github.com/holon/i108")
        self.assertEqual((r["path"], r["commit"], r["status"]), ("lib/dep", "1" * 40, "refused"))
        self.assertIn("GitHub", r["reason"])

    def test_p4_submodule_excluded_refused_never_cloned(self):
        from holon.eval import common, layout as L
        pat = common.protocol()["excluded_repos"][0]["pattern"]
        url = pat if pat.startswith("https://github.com/") else "https://github.com/" + pat.strip("/")
        d = self._repo(url)
        head = subprocess.run(["git", "-C", str(d), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        (r,) = L.submodules(d, head, "https://github.com/holon/i108")
        self.assertEqual(r["status"], "refused")
        self.assertIn("exclude", r["reason"])


class TestStringKeys(_Fixture):
    """P5: (b) is not built: a string-keyed mapping stays refused at types, by the SP_b refusal."""

    def test_p5_string_keys_still_refused(self):
        from holon.sorts import model3
        import inspect
        self.assertIn("not compiled in the structural mode", inspect.getsource(model3.Gen.map_key))


class TestCorpusSmoke(unittest.TestCase):
    """P6-P10: the smoke measures on I51's 20 entries (contaminated by I51/I103/I105; I107 scores)."""

    @classmethod
    def setUpClass(cls):
        key = json.loads((ROOT / "spec" / "M6" / "predictions" / "I108.json").read_text(encoding="utf-8"))
        cls.pred = {p["id"]: p for p in key["predictions"]}

    def rows(self, p: Path) -> dict:
        self.assertTrue(p.is_file(), f"{p.relative_to(ROOT)} is missing")
        return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}

    def reached(self) -> set:
        h, g = self.rows(HOLON_CORPUS), self.rows(GO_CORPUS)
        out = {i for i, r in h.items() if any(d.get("status") == "extracted" for d in r.get("documents") or [])}
        out |= {i for i, r in g.items() if r.get("machines")}
        return out

    def test_p6_extraction_reach(self):
        self.assertGreaterEqual(len(self.reached()), self.pred["I108-P6"]["expected"]["at_least"])

    def test_p7_no_sorts_refusal_on_go_machines(self):
        g = self.rows(GO_CORPUS)
        at_sorts = sorted(i for i, r in g.items() if r.get("refused_at") == "sorts")
        self.assertEqual(at_sorts, [])
        signed = sorted(i for i, r in g.items()
                        if any(h in json.dumps((r.get("stages") or {}).get("sorts", {})) for h in ("'s>'", "'s<'", "'sext'")))
        self.assertEqual(signed, [])

    def test_p8_go_machines_complete(self):
        g = self.rows(GO_CORPUS)
        exp = self.pred["I108-P8"]["expected"]
        self.assertEqual(sum(r.get("pipeline") == "complete" for r in g.values()), exp["complete"])
        self.assertEqual(sum(int(r.get("laws") or 0) for r in g.values()), exp["laws"])

    def test_p9_c02_derives_per_model(self):
        h = self.rows(HOLON_CORPUS)
        r = h["c02"]
        self.assertEqual(r["stages"]["derive"]["status"], "ok", r["stages"]["derive"]["detail"][-1000:])
        self.assertGreaterEqual(len(r["laws"]), 1)

    def test_p10_every_miss_has_stage_and_reason(self):
        h, g = self.rows(HOLON_CORPUS), self.rows(GO_CORPUS)
        for i, r in sorted(h.items()):
            st = r.get("stages") or {}
            bad = [k for k, v in st.items() if v.get("status") not in ("ok", "not_applicable", "not_run")]
            for k in bad:
                self.assertTrue((st[k].get("detail") or "").strip(), f"{i}: stage {k} has no reason")
        for i, r in sorted(g.items()):
            if r.get("pipeline") != "complete":
                self.assertTrue(r.get("refused_at"), i)

    def test_p10_no_verdict_recorded(self):
        h = self.rows(HOLON_CORPUS)
        for i, r in sorted(h.items()):
            self.assertFalse(any(x.get("status") in ("PROVED", "REFUTED") for x in r.get("laws") or []
                                 if isinstance(x, dict)), i)


class TestRegressions(unittest.TestCase):
    def test_r1_morph_record_moves_only_by_restamp(self):
        moved = []
        for d in MORPH_DIRS:
            base = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", BASE, "--", d)
                    .decode().splitlines()}
            head = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", "HEAD", "--", d)
                    .decode().splitlines()}
            for p in sorted(set(base) | set(head)):
                if base.get(p) == head.get(p):
                    continue
                if p not in base or p not in head or not p.endswith(".json"):
                    moved.append(p)
                    continue
                a = json.loads(git("cat-file", "blob", base[p]))
                b = json.loads(git("cat-file", "blob", head[p]))
                if strip_stamp(a) != strip_stamp(b):
                    moved.append(p)
        self.assertEqual(moved, [])

    def test_r2_morph_documents_have_no_signed_heads(self):
        """(a) moves no Morph document: none holds a head S1-S3 names, so 0.4 walks each exactly as 0.3."""
        found = []
        for p in sorted((ROOT / "spec").glob("M*/facts/*.extracted.json")):
            text = p.read_text(encoding="utf-8")
            for h in SIGNED + ("sdiv", "smod", "sar"):
                if f'["{h}",' in text.replace(" ", ""):
                    found.append((p.relative_to(ROOT).as_posix(), h))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
