"""F33: the fast lemma search of the equivalence generator (holon.gen.eqsearch; not preregistered: a fix iteration).

Contract:
  verdict        the search only finds lemmas. PROVED still means the final PROOF.bend, holding every lemma and the root
                 laws, was accepted whole by bend2 and BendTT (--verdict), names exactly the expected laws and holds no
                 escape hatch (F31's criterion, unchanged).
  determinism    the chosen proof of a definition is the first class, in a fixed order, whose candidate bend2 accepts,
                 and a candidate's text depends on its obligation alone: the final laws and proof are byte-identical
                 with one worker or two, any batch size, and a cold or warm cache.
  cache          a warm cache (one shared by pair modules of the same two models) finds every lemma without a candidate
                 check; a cached text the final check refuses is evicted and searched again, so a poisoned cache can
                 make the search slower, never a claim weaker: a planted non-equivalence is never PROVED through it.
  resume         the cache file is append-only JSON lines, reloaded by a new run (a line cut by a crash is skipped).
  bridge         (statement_diff, bindings) a binding_change may carry a statement-hash change only with an accepted
                 catalog_rederivation mapping exactly those two hashes; it then covers the rebinding of the hash and
                 the cone together, and nothing else.
  artifacts      G2 re-checks a committed binding_change from its proof artifacts (the files its acceptance record
                 hashes) in both kernels, and refuses a missing or altered artifact without running any search.
"""
from __future__ import annotations

import gzip
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT
from tests_m3.test_binding_equivalence import NEW, OLD, PLANTED, STATEMENT

from holon import bend
from holon import bindings as B
from holon import statement_diff as SD
from holon.gen import eqsearch as ES
from holon.gen import equivalence as E

_RUNS: dict = {}


def run(new: str = NEW, **kw) -> dict:
    key = (new, tuple(sorted((k, id(v) if k == "cache" else v) for k, v in kw.items())))
    if key not in _RUNS:
        _RUNS[key] = E.prove(OLD, new, STATEMENT, counter_tries=300, **kw)
    return _RUNS[key]


class TestDeterminism(unittest.TestCase):
    def test_workers_batches_and_cache_give_the_same_proof(self):
        base = run(workers=1, batch=1)
        self.assertEqual(base["status"], "PROVED", base["reason"])
        cache = ES.LemmaCache(None)
        variants = [run(workers=2, batch=2), run(workers=2, batch=48), run(workers=1, batch=48, cache=cache)]
        warm = E.prove(OLD, NEW, STATEMENT, counter_tries=300, workers=2, batch=48, cache=cache)
        for r in variants + [warm]:
            self.assertEqual(r["status"], "PROVED", r["reason"])
            for k in ("pair_sha256", "laws", "proof", "kernels"):
                self.assertEqual(r[k], base[k], k)
            self.assertEqual(json.dumps(r["lemmas"], sort_keys=True), json.dumps(base["lemmas"], sort_keys=True))
        self.assertEqual(warm["search"]["checks"], 0, "a warm cache needs no candidate check")
        self.assertGreater(warm["search"]["cache_hits"], 0)
        self.assertIn("bend", warm["kernels"], "the final whole-file check still runs")
        if bend.verdict_enabled():
            self.assertIn("BendTT", warm["kernels"])


class TestCacheNeverCounts(unittest.TestCase):
    def _poisoned(self, new: str, victim: str, text_of) -> tuple[dict, ES.LemmaCache]:
        """A cache holding a wrong text for victim's obligation key (computed exactly as the search does)."""
        pm = E.pair_module(OLD, new, STATEMENT)
        gen = E.Gen(pm)
        libs = E.libraries_for(pm)
        src = lambda d: E._source_name(d, pm.old_items)
        changed = sorted({src(d) for d in pm.dirty_entries if pm.old_items[src(d)].kind == "def"
                          and src(d) in pm.new_items and pm.new_items[src(d)].kind == "def"})
        head = f"import Base\nimport ./pair.bend as {E.ALIAS}\n\n" + E.CORE + "\n" + E.library_text(libs) + "\n"
        s = ES.Search(pm, gen, libs, changed, E._deps(pm, set(changed)), None, Path(tempfile.gettempdir()), head,
                      E.LEMMA, E.PREFIX, E.ALIAS)
        cache = ES.LemmaCache(None)
        cache.put(s.key(victim), victim, "congruence", text_of(victim), [])
        return E.prove(OLD, new, STATEMENT, counter_tries=300, cache=cache), cache

    def test_a_wrong_cached_text_is_evicted_and_searched_again(self):
        good = run(workers=1, batch=1)
        bogus = lambda f: (f"def {E.LEMMA}{f}(+a: {E.ALIAS}.W, +b: {E.ALIAS}.W) -> "
                           f"{{{E.ALIAS}.{E.PREFIX}{f}(a, b) == {E.ALIAS}.{f}(a, b) : Bool}}:\n  {{==}}\n")
        r, cache = self._poisoned(NEW, "w_eq", bogus)
        self.assertEqual(r["status"], "PROVED", r["reason"])
        self.assertEqual(r["proof"], good["proof"], "the evicted text is replaced by the search's own")
        self.assertNotIn("{==}\n\ndef", r["proof"].split(f"def {E.LEMMA}w_eq(")[1][:40])
        self.assertTrue(any("refused by the final check" in a for a in r["lemmas"]["w_eq"]["attempts"]))

    def test_a_poisoned_cache_never_proves_a_non_equivalence(self):
        # the planted one-limb change: w_eq ignores l2; a cached "proof" by reflexivity must not get it through
        bogus = lambda f: (f"def {E.LEMMA}{f}(+a: {E.ALIAS}.W, +b: {E.ALIAS}.W) -> "
                           f"{{{E.ALIAS}.{E.PREFIX}{f}(a, b) == {E.ALIAS}.{f}(a, b) : Bool}}:\n  {{==}}\n")
        r, _ = self._poisoned(PLANTED["limb"], "w_eq", bogus)
        self.assertNotEqual(r["status"], "PROVED")
        self.assertEqual(r["status"], "REFUTED", r["reason"])


class TestResume(unittest.TestCase):
    def test_the_cache_file_reloads_and_skips_a_cut_line(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-f33-"))
        try:
            p = tmp / "c.jsonl"
            c = ES.LemmaCache(p)
            c.put("k1", "f", "congruence", "def q_f() -> T:\n  x\n", ["normalize: failed"])
            c.mark_failed("k2", "normalize", "text", "SOME PROOFS FAIL")
            c.put("k3", "g", "congruence", "t3", [])
            c.evict("k3")
            with p.open("a") as fh:
                fh.write('{"ok": true, "key": "k4", "te')   # a crash in the middle of a line
            d = ES.LemmaCache(p)
            self.assertEqual(d.get("k1")["text"], "def q_f() -> T:\n  x\n")
            self.assertEqual(d.get("k1")["attempts"], ["normalize: failed"])
            self.assertEqual(d.failed("k2", "normalize", "text"), "SOME PROOFS FAIL")
            self.assertIsNone(d.get("k3"))
            self.assertIsNone(d.get("k4"))
        finally:
            shutil.rmtree(tmp)

    def test_default_cache_lives_outside_the_repository(self):
        p = E.default_cache_path(OLD, NEW)
        self.assertTrue(str(p).startswith(str(Path.home() / ".holon" / "cache" / "eqv")), p)
        self.assertNotIn(str(ROOT), str(p))
        self.assertEqual(p, E.default_cache_path(OLD, NEW), "deterministic")
        self.assertNotEqual(p.parent, E.default_cache_path(OLD, PLANTED["bit"]).parent, "keyed by the model pair")


class TestStatementHashBridge(unittest.TestCase):
    LAW = {"law_id": "L_x", "milestone": "M3", "ir_version": "holon-ir/0.3", "facts": "facts/x.json",
           "statement": {"binders": [], "claim": {"eq": [{"nat": 0}, {"nat": 0}]}}}

    def bc(self, **kw):
        return {"kind": "binding_change", "law_id": "L_x", "old": self.LAW, "new": self.LAW, "defs": ["f", "g"], **kw}

    def test_a_bridged_binding_change_covers_hash_and_cone_together(self):
        e = self.bc(statement_hash={"old": "sha256:a", "new": "sha256:b"})
        self.assertTrue(B.entry_covers(e, "L_x", self.LAW, True, ["f"], False, ("sha256:a", "sha256:b")))
        self.assertTrue(B.entry_covers(e, "L_x", self.LAW, True, ["f"], False, None))
        self.assertFalse(B.entry_covers(e, "L_x", self.LAW, True, ["f"], False, ("sha256:a", "sha256:c")),
                         "another hash change")
        self.assertFalse(B.entry_covers(e, "L_x", self.LAW, True, ["h"], False, ("sha256:a", "sha256:b")),
                         "a definition the entry does not name")
        self.assertFalse(B.entry_covers(e, "L_x", self.LAW, True, [], True, ("sha256:a", "sha256:b")),
                         "a hash-only change is a catalog_rederivation's, not a binding_change's")
        plain = self.bc()
        self.assertFalse(B.entry_covers(plain, "L_x", self.LAW, True, ["f"], False, ("sha256:a", "sha256:b")),
                         "an unbridged binding_change never covers a statement-hash change")
        self.assertTrue(B.entry_covers(plain, "L_x", self.LAW, False, ["f"]))

    def test_no_bridge_without_an_accepted_catalog_line(self):
        self.assertIsNone(SD.catalog_bridge("M3", "L_x", "sha256:a", "sha256:b", ROOT))
        lines = [json.loads(x) for x in (ROOT / SD.LOG).read_text().splitlines() if x.strip()]
        cat = [x for x in lines if x.get("kind") == "catalog_rederivation" and x.get("milestone") == "M3"]
        x = cat[-1]
        br = SD.catalog_bridge("M3", x["law_id"], x["old_hash"], x["new_hash"], ROOT)
        self.assertIsNotNone(br)
        self.assertEqual((br["old"], br["new"]), (x["old_hash"], x["new_hash"]))
        self.assertIsNone(SD.catalog_bridge("M3", x["law_id"], x["new_hash"], x["old_hash"], ROOT), "reversed")
        self.assertIsNone(SD.catalog_bridge("M2", x["law_id"], x["old_hash"], x["new_hash"], ROOT), "milestone")


class TestArtifacts(unittest.TestCase):
    def test_g2_recheck_refuses_missing_or_altered_artifacts(self):
        r = run(workers=1, batch=1)
        self.assertEqual(r["status"], "PROVED", r["reason"])
        tmp = Path(tempfile.mkdtemp(prefix="holon-f33-"))
        try:
            e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M9"}
            acc = SD.acceptance({**e, "old": {}, "new": {}}, {"ok": True, "equivalence": {**r, "models": {}}}, tmp)
            eqv = acc["equivalence"]
            self.assertIn("missing", SD.recheck_artifacts(e, eqv, tmp, None, None))
            SD.write_artifacts(e, eqv, r, tmp)
            d = tmp / SD.artifact_dir(e, eqv)
            first = {p.name: p.read_bytes() for p in d.iterdir()}
            SD.write_artifacts(e, eqv, r, tmp)
            self.assertEqual(first, {p.name: p.read_bytes() for p in d.iterdir()}, "deterministic bytes")
            new_b = NEW.encode()
            self.assertIsNone(SD.recheck_artifacts(e, eqv, tmp, None, new_b))
            proof = gzip.decompress((d / "PROOF.bend.gz").read_bytes()).decode()
            (d / "PROOF.bend.gz").write_bytes(gzip.compress((proof + "\n").encode(), mtime=0))
            self.assertIn("not the file its acceptance record hashes", SD.recheck_artifacts(e, eqv, tmp, None, new_b))
            (d / "PROOF.bend.gz").write_bytes(first["PROOF.bend.gz"])
            self.assertIn("not the new model", SD.recheck_artifacts(e, eqv, tmp, None, PLANTED["bit"].encode()))
        finally:
            shutil.rmtree(tmp)


class TestTargetAgnostic(unittest.TestCase):
    def test_no_law_ids_or_target_names(self):
        src = (ROOT / "holon" / "gen" / "eqsearch.py").read_text()
        for word in ("L_sort", "rollup", "morph", "Rollup", "gh_step", "kw_set", "h_get", "M3"):
            self.assertNotIn(word, src, word)


if __name__ == "__main__":
    unittest.main()
