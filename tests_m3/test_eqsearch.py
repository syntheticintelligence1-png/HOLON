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
                 hashes) in both kernels, and refuses a missing or altered artifact without running any search; the
                 pair module and LAWS.bend are regenerated from the two models and the statement and compared byte
                 for byte (a vacuous or empty LAWS.bend is refused).
  crashes        (F33 review) a bend2 crash is never a verdict: it never moves a definition to its next class and
                 never reaches the cache, so cold and warm runs give the same bytes; a lemma that crashes in every
                 larger file ends the search (UNKNOWN) instead of looping; a slice miss is never a candidate failure;
                 a search stop is UNKNOWN with the roots decided.
"""
from __future__ import annotations

import gzip
import json
import shutil
import tempfile
import time
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
        self.assertEqual(E.root_laws_text(E.pair_module(OLD, NEW, STATEMENT))[0], r["laws"],
                         "LAWS.bend regenerates from the pair module alone")
        old_b, new_b = OLD.encode(), NEW.encode()
        tmp = Path(tempfile.mkdtemp(prefix="holon-f33-"))
        try:
            e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M9"}
            acc = SD.acceptance({**e, "old": {}, "new": {}}, {"ok": True, "equivalence": {**r, "models": {}}}, tmp)
            eqv = acc["equivalence"]
            self.assertIn("missing", SD.recheck_artifacts(e, eqv, tmp, old_b, new_b, STATEMENT))
            SD.write_artifacts(e, eqv, r, tmp)
            d = tmp / SD.artifact_dir(e, eqv)
            first = {p.name: p.read_bytes() for p in d.iterdir()}
            SD.write_artifacts(e, eqv, r, tmp)
            self.assertEqual(first, {p.name: p.read_bytes() for p in d.iterdir()}, "deterministic bytes")
            self.assertIsNone(SD.recheck_artifacts(e, eqv, tmp, old_b, new_b, STATEMENT))
            self.assertIn("git history", SD.recheck_artifacts(e, eqv, tmp, None, new_b, STATEMENT),
                          "no old model (a copied tree): not re-checked, not accepted")
            proof = gzip.decompress((d / "PROOF.bend.gz").read_bytes()).decode()
            (d / "PROOF.bend.gz").write_bytes(gzip.compress((proof + "\n").encode(), mtime=0))
            self.assertIn("not the file its acceptance record hashes",
                          SD.recheck_artifacts(e, eqv, tmp, old_b, new_b, STATEMENT))
            (d / "PROOF.bend.gz").write_bytes(first["PROOF.bend.gz"])
            self.assertIn("not the pair module", SD.recheck_artifacts(e, eqv, tmp, old_b, PLANTED["bit"].encode(),
                                                                      STATEMENT))
        finally:
            shutil.rmtree(tmp)

    def test_g2_recheck_refuses_vacuous_or_empty_laws(self):
        """The review's attack: laws named like the root laws but stating {1n == 1n : Nat}, or no laws at all with every
        root recorded unchanged, pass both kernels; G2 regenerates the laws from the statement and refuses them."""
        r = run(workers=1, batch=1)
        head = f"import Base\nimport ./pair.bend as {E.ALIAS}\n\n"
        names = ["eq_look", "to_Reach", "from_Reach"]
        vac_laws = head + "\n".join(f"law {n}:\n  {{1n == 1n : Nat}}\n" for n in names)
        vac_proof = (head.replace("\n\n", "\nimport ./LAWS.bend as Laws\n\n")
                     + "\n".join(f"def Laws.{n}() -> {{1n == 1n : Nat}}:\n  {{==}}\n" for n in names))
        for laws, proof, roots in ((vac_laws, vac_proof, None), (head, head, "unchanged")):
            fake = {**r, "laws": laws, "proof": proof, "models": {}}
            if roots:
                fake["roots"] = [{"root": i["root"], "class": "unchanged"} for i in r["roots"]]
            tmp = Path(tempfile.mkdtemp(prefix="holon-f33-"))
            try:
                e = {"kind": "binding_change", "law_id": "L_x", "milestone": "M9"}
                eqv = SD.acceptance({**e, "old": {}, "new": {}}, {"ok": True, "equivalence": fake}, tmp)["equivalence"]
                SD.write_artifacts(e, eqv, fake, tmp)
                why = SD.recheck_artifacts(e, eqv, tmp, OLD.encode(), NEW.encode(), STATEMENT)
                self.assertIsNotNone(why)
                self.assertIn("LAWS.bend is not the root laws regenerated", why)
            finally:
                shutil.rmtree(tmp)


class TestCrashes(unittest.TestCase):
    """bend2's stack overflow is not deterministic (F33): a crash is never a verdict. It can cost a proof, never change
    one (cold and warm runs give the same bytes), and a lemma that crashes only in larger files ends the search instead
    of rebuilding the same batch forever (the review's livelock)."""
    OVERFLOW = "Error: the machine stack overflowed"

    @classmethod
    def setUpClass(cls):
        cls.c0 = ES.LemmaCache(None)
        cls.cold = E.prove(OLD, NEW, STATEMENT, counter_tries=0, workers=1, batch=48, cache=cls.c0)
        cls.T = {v["def"]: v["text"] for v in cls.c0.ok.values()}

    def crashing(self, cache, crash, **kw):
        orig = ES.Search._check

        def fake(search, text, job):
            if crash(text):
                return E.Check(False, self.OVERFLOW, 0.01, None)
            return orig(search, text, job)
        ES.Search._check = fake
        try:
            return E.prove(OLD, NEW, STATEMENT, counter_tries=0, workers=1, batch=48, cache=cache,
                           deadline=time.monotonic() + 300, **kw)
        finally:
            ES.Search._check = orig

    def test_a_crash_in_larger_files_gives_the_crash_free_proof_cold_and_warm(self):
        self.assertEqual(self.cold["status"], "PROVED", self.cold["reason"])
        T = self.T
        mine, uses, todo = T["look"], set(), ["look"]
        while todo:   # the lemmas look's file must hold
            t = T[todo.pop()]
            for g in T:
                if g not in uses and (E.LEMMA + g + "(") in t:
                    uses.add(g)
                    todo.append(g)
        others = [t for g, t in T.items() if g != "look" and g not in uses]
        self.assertTrue(others)
        cache = ES.LemmaCache(None)
        r = self.crashing(cache, lambda t: mine in t and any(o in t for o in others))
        self.assertEqual(r["status"], "PROVED", r["reason"])
        self.assertGreater(r["search"].get("overflow_retries", 0), 0, "the crash was injected")
        self.assertEqual(r["proof"], self.cold["proof"], "a crash never moves a definition to its next class")
        warm = E.prove(OLD, NEW, STATEMENT, counter_tries=0, workers=1, batch=48, cache=cache)
        self.assertEqual(warm["search"]["checks"], 0)
        self.assertEqual(warm["proof"], self.cold["proof"], "warm after a crash run == crash-free cold")

    def test_a_lemma_that_always_crashes_stays_unknown_and_nothing_is_cached(self):
        mine = self.T["look"]
        cache = ES.LemmaCache(None)
        r = self.crashing(cache, lambda t: mine in t)
        self.assertNotEqual(r["status"], "PROVED")
        self.assertEqual(r["lemmas"]["look"]["status"], "UNKNOWN")
        self.assertNotIn("look", {v["def"] for v in cache.ok.values()}, "no other class's text is cached")
        key = next(k for k, v in self.c0.ok.items() if v["def"] == "look")
        self.assertFalse([k for k in cache.bad if k[0] == key], "a crash is never cached as a failed candidate")
        warm = E.prove(OLD, NEW, STATEMENT, counter_tries=0, workers=1, batch=48, cache=cache)
        self.assertEqual(warm["proof"], self.cold["proof"])

    def test_a_proven_lemma_that_crashes_in_larger_files_ends_the_search(self):
        T = self.T
        cache = ES.LemmaCache(None)
        for k, v in self.c0.ok.items():
            if v["def"] != "look":
                cache.ok[k] = dict(v)
        before = json.dumps(cache.ok, sort_keys=True)
        r = self.crashing(cache, lambda t: T["st_get"] in t and T["kw_get"] in t)
        self.assertNotIn("search_stop", r, r.get("search_stop"))
        self.assertLess(r["search"]["checks"], 30, r["search"])
        self.assertEqual(r["lemmas"]["st_get"]["status"], "UNKNOWN")
        self.assertIn("crashed", " ".join(r["lemmas"]["st_get"]["attempts"]))
        self.assertEqual(r["lemmas"]["look"]["status"], "BLOCKED")
        self.assertNotEqual(r["status"], "PROVED")
        self.assertEqual(json.dumps(cache.ok, sort_keys=True), before, "the cache is unchanged by a crash")
        self.assertEqual(cache.bad, {})


class TestSliceMiss(unittest.TestCase):
    def test_a_slice_miss_pinned_on_a_candidate_is_never_its_failure(self):
        """bend2 reports a name a pair-module slice lacks as "expected : a defined name" with a Location at the
        referencing definition; the search switches to the whole pair module and caches nothing for the candidate."""
        base = run(workers=1, batch=1)
        orig = ES.Search._check
        seen = []

        def fake(search, text, job):
            if not search.full_pair and not seen and (E.LEMMA + "look(") in text:
                seen.append(job)
                return E.Check(False, "expected : a defined name\nobserved : P.nothing\nLocation: " + E.LEMMA + "look",
                               0.01, E.LEMMA + "look")
            return orig(search, text, job)
        cache = ES.LemmaCache(None)
        ES.Search._check = fake
        try:
            r = E.prove(OLD, NEW, STATEMENT, counter_tries=0, workers=1, batch=48, cache=cache)
        finally:
            ES.Search._check = orig
        self.assertTrue(seen)
        self.assertEqual(r["search"]["slice_misses"], 1)
        self.assertEqual(r["proof"], base["proof"])
        self.assertFalse([m for m in cache.bad.values() if "a defined name" in m])


class TestSearchStop(unittest.TestCase):
    def test_a_search_stop_is_unknown_with_roots_and_what_was_tried(self):
        orig = ES.Search._check
        ES.Search._check = lambda search, text, job: E.Check(False, "Error: something else", 0.01, None)
        try:
            r = E.prove(OLD, NEW, STATEMENT, counter_tries=0, workers=1, batch=48, cache=ES.LemmaCache(None))
        finally:
            ES.Search._check = orig
        self.assertEqual(r["status"], "UNKNOWN", r["reason"])
        self.assertIn("outside the lemmas", r["search_stop"])
        self.assertTrue(r["roots"], "the roots are still decided")
        self.assertIn("the lemma search stopped", r["reason"])


class TestTargetAgnostic(unittest.TestCase):
    def test_no_law_ids_or_target_names(self):
        src = (ROOT / "holon" / "gen" / "eqsearch.py").read_text()
        for word in ("L_sort", "rollup", "morph", "Rollup", "gh_step", "kw_set", "h_get", "M3"):
            self.assertNotIn(word, src, word)


if __name__ == "__main__":
    unittest.main()
