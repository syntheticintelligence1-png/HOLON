"""I20: the extracted rollup model, with refinement, width obligations and the differential against the hand
abstraction (whitepaper §8.7, §7.6, §10.1 translators, L1; BUILD_PLAN I20). This docstring is the contract.

Inputs
  spec/M2/facts/morph_rollup.extracted.json (I19). It is compiled together with the inherited storage that its
  guards read (for example _paused and _owner, from solc's storageLayout of the full contract).

Deliverables and outputs (canonical JSON, sorted keys)
  1. machine.py compiles holon-facts/0.3 transitions documents (raw storage families), plus a window view where
     the facts declare one. `python -m holon model --facts <doc> --out gen/M2/extracted/` writes the Bend model
     (gen/M2/extracted/model.bend), which Bend checks. The raw-family model is authoritative. When the
     generated window view disagrees with the hand abstraction (spec/M1/facts/morph_rollup.json) on a corpus
     state, both are reported in gen/M2/extracted/window_check.json: {"states": n, "disagreements": [...]}.
  2. Refinement (I16 machinery). The extracted model's transitions are replayed against the real contract
     (Foundry, the pinned checkout) on the I16 corpus (the 300 M1 traces) plus the boundary corpus, whose
     values come from the extracted sorts and widths.
       results/M2/refinement/extracted.json: {"traces": n, "steps": n,
          "disagreements": [{"id", "class", "links"}], "unexplained": n}
     Classes and links follow holon.refinement, never a label.
  3. Width-site laws (rule SORT-width; holon/sorts/sites.py or holon/sorts/width.py). One law per
     store that narrows a value into a field of smaller width, derived by `holon derive --milestone M2` into
     laws/M2/L_sort_width_<span-id>.json and run like the I15 site laws.
       Record extras: {"width_site": {"span", "field", "width"}}.
  4. Differential. `python -m holon differential --milestone M2` re-runs the 15 rollup M1 laws (every
     laws/M1 law whose facts are spec/M1/facts/morph_rollup.json) on the extracted model, through the window
     view, with --no-registry. It writes:
       gen/M2/abstraction_diff.json: {"deltas": [{"id", "kind", "names": [...], "src": "<span or null>"}]}
         Each delta is derived mechanically from one concrete difference between the extracted document and the
         M1 facts. kind is one of:
           guard_missing   an M1 require with no extracted guard of the same action, matched by span;
           guard_extra     an extracted guard with no M1 require;
           state_unmapped  an M1 state field the window view cannot express from raw families;
           family_unmapped a raw family no M1 field maps;
           ghost           an M1 ghost field;
           external        state held by another contract, reached by external call.
         names lists the M1 names (state fields, defs, observers, actions) the difference touches.
       results/M2/differential.json: {"laws": {"<law id>": {"m1": status, "extracted": status,
                                                            "deltas": [delta ids]}}}
         deltas is non-empty exactly when the statuses differ. Every delta listed for a law must share a name
         with that law's cone (holon.mpipeline.law_cone over the M1 facts). Records of the extracted run are in
         results/M2/extracted_m1/.
  5. Re-extraction. I15's 10 SORT-site laws are re-derived on the extracted facts. Their changed statements go
     through laws/STATEMENT_DIFF.jsonl as "reextraction" entries. holon.statement_diff accepts such an entry
     unsigned only when G1 reproduces the changed refs from the pinned code with the pinned extractor, and when
     holon derive reproduces the new statement from the same (rule, subform, basis element). I20 implements
     this acceptance, which until now rejected every reextraction because no extractor existed.
  6. Optional: hevm equivalence for the top codec edges. results/M2/hevm.json records
     {"status": "run"|"not_run", "reason"}.

Rules
  - AGENTS.md is binding: never edit facts/, spec/M1/facts/ or laws/M1/.
  - A status difference is explained only by a mechanical delta, never by prose.
  - The raw model is authoritative.
  - No skips. Predictions are never tuned.
"""
import json
import unittest

from tests_m2._m2 import ROOT, load_json

M2 = ROOT / "results" / "M2"
UNDO_KEPT = {"L_sort_remaining": "REFUTED", "L_undo_BVH": "REFUTED", "L_undo_cancel": "REFUTED"}


def need(p):
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def width_records() -> dict:
    out = {}
    for p in sorted(M2.glob("L_sort_width_*.json")):
        r = load_json(p)
        out[r["law_id"]] = r
    return out


class TestRefinement(unittest.TestCase):
    def test_no_unexplained_disagreement_on_the_corpus(self):
        """I20-P1: 0 unexplained disagreements between the extracted model and the real contract on the 300-trace
        and boundary corpus."""
        r = need(M2 / "refinement" / "extracted.json")
        self.assertGreaterEqual(r["traces"], 300)
        self.assertEqual(r["unexplained"], 0)
        self.assertEqual([d["id"] for d in r["disagreements"] if not d.get("links")], [])


class TestWidth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = width_records()

    def _site(self, field):
        hits = [r for r in self.w.values() if r.get("width_site", {}).get("field") == field]
        self.assertEqual(len(hits), 1, sorted(self.w))
        return hits[0]

    def test_the_accumulator_width_law_is_unknown(self):
        """I20-P2: the width-site law at the totalL1MessagePopped store (the unchecked accumulator at Rollup.sol:324)
        is UNKNOWN, bounded, with no witness."""
        r = self._site("totalL1MessagePopped")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertFalse(r.get("witness"))

    def test_the_batch_index_width_law_is_unknown(self):
        """I20-P3: the width-site law at the batchIndex store is UNKNOWN, bounded, with no witness."""
        r = self._site("batchIndex")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertFalse(r.get("witness"))


class TestReextraction(unittest.TestCase):
    def test_reextraction_entries_for_the_site_laws_validate_unsigned(self):
        """I20-P4: the re-derived I15 site laws enter through reextraction entries that validate without a
        signature."""
        sd = __import__("holon.statement_diff", fromlist=["check_entry"])
        lines = [json.loads(l) for l in (ROOT / "laws" / "STATEMENT_DIFF.jsonl").read_text().splitlines() if l.strip()]
        re_ = [e for e in lines if e.get("kind") == "reextraction"]
        laws = {e.get("law_id") for e in re_}
        self.assertTrue({l for l in laws if l and l.startswith("L_sort_site_")}, re_)
        for e in re_:
            with self.subTest(law=e.get("law_id")):
                self.assertFalse(e.get("signature"))
                res = sd.check_entry(e)
                ok = res[0] if isinstance(res, tuple) else getattr(res, "ok", res)
                self.assertTrue(ok, res)


class TestDifferential(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = need(M2 / "differential.json")
        cls.deltas = {x["id"]: x for x in need(ROOT / "gen" / "M2" / "abstraction_diff.json")["deltas"]}

    def test_every_status_difference_links_a_mechanical_delta(self):
        """I20-P5: all 15 rollup laws are re-run; every status difference links to at least one delta of
        gen/M2/abstraction_diff.json, and no law without a difference lists one."""
        self.assertEqual(len(self.d["laws"]), 15)
        for lid, x in self.d["laws"].items():
            with self.subTest(law=lid):
                self.assertEqual(bool(x["deltas"]), x["m1"] != x["extracted"])
                self.assertLessEqual(set(x["deltas"]), set(self.deltas))

    def test_three_refutations_survive_extraction(self):
        """I20-P6: L_sort_remaining, L_undo_BVH and L_undo_cancel are REFUTED on the extracted model too."""
        for lid, st in UNDO_KEPT.items():
            with self.subTest(law=lid):
                self.assertEqual(self.d["laws"][lid]["extracted"], st)

    def test_the_ghost_tag_law_is_explained_by_the_ghost_delta(self):
        """I20-P7: L_tag_BVH, which reads the ghost tag, differs from its M1 status on the extracted model, and its
        deltas include a ghost delta."""
        x = self.d["laws"]["L_tag_BVH"]
        self.assertNotEqual(x["extracted"], x["m1"])
        self.assertIn("ghost", {self.deltas[i]["kind"] for i in x["deltas"]})


class TestConstruction(unittest.TestCase):
    def test_the_extracted_model_and_window_check_exist(self):
        self.assertTrue((ROOT / "gen" / "M2" / "extracted" / "model.bend").is_file())
        w = need(ROOT / "gen" / "M2" / "extracted" / "window_check.json")
        self.assertIn("disagreements", w)

    def test_hevm_is_recorded(self):
        h = need(M2 / "hevm.json")
        self.assertIn(h["status"], ("run", "not_run"))


if __name__ == "__main__":
    unittest.main()
