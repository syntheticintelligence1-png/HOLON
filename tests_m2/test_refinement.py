"""I16: per-edge corpus, refinement records, mechanical disagreement classes, refinement_refs
(whitepaper §8.6, §8.7 sources 1-3, Def 4.7 rho(e); BUILD_PLAN I16).

Each model edge is compared with ITS OWN implementation (never with another edge):
  enc_sol    the Solidity store (the header build block of _commitBatchWithBatchData: BatchHeaderCodecV0
             store* and BatchHeaderCodecV1.storeLastBlockNumber), through replay/M2/solidity/HolonCodec.t.sol
  enc_go_v0  Go BatchHeaderV0{..}.Bytes()         enc_go_v1  Go BatchHeaderV1{..}.Bytes()
  dec_go     Go decode: validate() then the getters (BlobCommitHash for the blob field)
  ok_go      Go validate() == nil                  ok_sol     Solidity _loadBatchHeader does not revert
These are the 4 CODEC edges of the I11 M0 diagram plus the two decoder domains (the domain predicates
of the Bytes interface carrier), which the plan's "decoder domains included" adds. Go edges run
through replay/M2/go/holon_codec_test.go. Harness dependencies stay outside the repo. The real outputs
are re-measured by two instruments fixed at this prereg (tests_m2/_i16.py): run_go_instrument for the
four Go edges and run_sol_instrument for enc_sol and ok_sol.

CLI these tests run:
  python -m holon refine --milestone M0 [--edges E1,E2] [--out DIR] [--morph PATH] [--work DIR] [--fix C ..]
      builds each edge's corpus (holon.corpus); evaluates the model side on the native C model
      (holon.model_native), or on the .mjs model when results/M2/native.json records a fallback; runs the
      real side on the pinned toolchain and morph checkout; writes <DIR or results/M2/refinement>/<edge>.json.
      --fix C (repeatable, 40 lowercase hex) names a fix commit this run measures; the record's `fixes` is
      the sorted list of them ([] without --fix). Without --edges it also writes cross_edge.json
      (results/M2/, or DIR) and appends each new disagreement to spec/M2/disagreements.json with class
      "unexplained" and no links. A record is byte-identical across runs and does not depend on --edges,
      --out, --work or --morph (no absolute path in it).
  python -m holon gate --milestone M0 --checks GREF --root R --report P

API these tests read:
  holon.corpus.SEED (int), holon.corpus.GRAMMAR_SAMPLES (== 2000)
  holon.corpus.corpus(edge) -> [{"source": "grammar" | "boundary" | "witness", "input": x}]
      deterministic in every process; x in canonical form (tests_m2/_i16.py), well formed, and in the
      edge's domain (enc_sol: version <= 2). Exactly 2000 grammar items; the boundary items cover every
      sort-boundary value (whitepaper §8.7: 0, 1, max, max - 1 and every sentinel constant, rule in
      tests_m2/_i16.py::required_boundary); the witness items hold every REFUTED M0 witness of the edge's
      input sort in its domain (_i16.m0_witnesses).
  holon.refinement.CLASSES == ("extraction_defect", "real_defect", "oracle_mismatch", "unexplained")
  holon.refinement.classify(entry, root) -> one of CLASSES, computed from entry["links"] and files under
      root only; entry["class"] (the label) is never read.
  holon.refinement.check_disagreements(root) -> [problem]: one problem per entry of
      root/spec/M2/disagreements.json whose computed class is unexplained or differs from its label, and per
      disagreement id listed in a refinement record (root/results/M2/refinement/*.json) without an entry;
      each problem names the id.
  holon.gate.CHECK_ORDER contains "GREF"; GREF passes iff check_disagreements(root) == [] (no git read).

results/M2/refinement/<edge>.json (one per edge above; file stem = model function name):
  edge, milestone ("M0"), kind ("codec" | "domain"), diagram_edge ("CODEC.<edge>" | null for a domain),
  facts ("facts/morph_header.json"), facts_sha256,
  implementation {lang: "go" | "solidity", harness: the harness path above, target: what is called},
  model_engine ("native" | "mjs"),
  corpus {seed, grammar, boundary, witness, inputs_sha256}   counts by source; digest of the inputs in order
  compared, agree, disagreements (ints), disagreement_ids [ids into spec/M2/disagreements.json],
  outputs_sha256 {model, real}   digests of the model's and the implementation's outputs in corpus order
  domain {in, out}               dec_go, ok_go, ok_sol only: inputs where the domain predicate (ok_go for
                                 dec_go) holds / fails
  fixes [40-hex commits]          the --fix commits this run measures (extraction_defect re-runs), sorted
  morph_commit (40 hex), toolchain {forge_sha256, solc_sha256, sol_deps_sha256, go_version} (= the pins
  in config/holon.json replay), command (the real side's harness invocation, as holon/replay.py records
  one: no absolute path, and the same whatever --edges, --out, --work or --morph).

results/M2/cross_edge.json (PAR differences between edges, never counted as refinement disagreements):
  {"milestone": "M0", "pairs": [[a, b], ..] (sorted pairs compared; at least [enc_go_v1, enc_sol] and
   [ok_go, ok_sol]), "differences": [{"edges": [a, b], "kind": "PAR", "law": law id | null,
   "count": n, "example": input}]}, one entry per (edges, law) group. The inputs compared for a pair
  [a, b] are corpus(a) followed by corpus(b), without repeats, restricted to inputs in both edges' domains;
  a difference is such an input on which the two edges' model outputs differ. count = differences in the
  group, example = the first of them in that order. A difference belongs to the group of the first M0 law
  (in law-id order) whose claim compares exactly the two edges and whose premises it satisfies;
  differences that satisfy no such law form the group with law null.

spec/M2/disagreements.json: {"disagreements": [entry]}, committed even when the list is empty;
  entry = {id, edge (model function name, e.g. enc_sol or step_commitBatch), milestone, input, model, real,
  class (label), links}. An id is a deterministic function of (edge, input), so a re-run never appends an
  entry twice. Classes, computed from the links alone: links holds exactly the keys of one kind
  ({fix_commit, rerun}, {law} or {hypothesis}); anything else is unexplained. tests_m2/_i16.py::expected_class
  writes these rules out (the prereg instrument; holon.refinement.classify must agree with it):
  extraction_defect  links {fix_commit: 40 lowercase hex, rerun: path of a record under
                     results/M2/refinement/} whose edge is the entry's edge, with disagreements == 0 and
                     fix_commit in its fixes
  real_defect        links {law: "<M>/<law_id>"}: results/<M>/<law_id>.json is REFUTED with replay status
                     passed and the entry's edge in its cone, replay/<M>/report.json holds
                     witness_sha256[law_id] == sha256(canonical_json(record witness)), and every side of
                     the law's report entry (M0: the entry itself; M1: entry["sides"]) has
                     obstruction_observed true
  oracle_mismatch    links {hypothesis: id}: results/M2/hypotheses.json[id].status == "failed"
  unexplained        everything else; GREF fails.
  Fix-commit existence needs git, which the gate never reads: it is left to `holon audit`.

Records: refinement_refs replaces "pending:I16" (and the v2 schema no longer accepts it). It is the
sorted list of
  M0: "results/M2/refinement/<edge>.json" for every edge above in the record's cone;
  M1: "replay/M1/report.json#/refinement/per_action/<a>" for every action a of the M1 corpus with
      step_<a> in the record's cone.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._util import config
from tests_m2 import _i16 as H
from tests_m2._m2 import ROOT, SCHEMAS2, copy_repo, holon_module, laws, load_json, records, run_holon, validate, write_json


def corpus_of(edge: str) -> list[dict]:
    return holon_module("holon.corpus").corpus(edge)


def run_gate(repo: Path, checks: str):
    report = repo / "gate_report_i16.json"
    p = run_holon(["gate", "--milestone", "M0", "--root", str(repo), "--report", str(report), "--checks", checks],
                  cwd=repo)
    return p, (load_json(report) if report.exists() else None)


# ---------------------------------------------------------------- per-edge records
class TestRecordsPerEdge(unittest.TestCase):
    """Construction: one record per edge, each against its own implementation, pinned."""

    def test_one_record_per_edge_against_its_own_implementation(self):
        diagram = load_json(H.DIAGRAM)
        codec = {e["model_fn"]: e for e in diagram["edges"] if e["kind"] == "CODEC"}
        domains = next(c for c in diagram["carriers"] if c["id"] == "Bytes")["domains"]
        self.assertEqual(sorted(codec), sorted(H.CODEC_EDGES), "the I11 M0 diagram's CODEC edges")
        self.assertEqual(sorted(domains), sorted(H.DOMAIN_EDGES))
        sha = hashlib.sha256(H.FACTS.read_bytes()).hexdigest()
        for edge in H.EDGES:
            with self.subTest(edge=edge):
                r = H.edge_record(edge)
                self.assertEqual(r["edge"], edge)
                self.assertEqual(r["milestone"], "M0")
                self.assertEqual(r["facts"], "facts/morph_header.json")
                self.assertEqual(r["facts_sha256"], sha)
                if edge in H.CODEC_EDGES:
                    self.assertEqual(r["kind"], "codec")
                    self.assertEqual(r["diagram_edge"], codec[edge]["id"])
                else:
                    self.assertEqual(r["kind"], "domain")
                    self.assertIsNone(r["diagram_edge"])
                lang = "go" if edge in H.GO_EDGES else "solidity"
                self.assertEqual(r["implementation"]["lang"], lang)
                self.assertEqual(r["implementation"]["harness"], H.HARNESS[lang])
                self.assertTrue((ROOT / H.HARNESS[lang]).is_file(), H.HARNESS[lang])
                self.assertIsInstance(r["implementation"]["target"], str)
                self.assertTrue(r["implementation"]["target"].strip())
                self.assertIn(r["model_engine"], ("native", "mjs"))
                self.assertIsInstance(r["fixes"], list)

    def test_records_are_pinned_to_the_toolchain_and_commit(self):
        cfg = config()["replay"]
        commit = H.facts()["target"]["commit"]
        for edge in H.EDGES:
            with self.subTest(edge=edge):
                r = H.edge_record(edge)
                self.assertRegex(r["morph_commit"], H.HEX40)
                self.assertTrue(r["morph_commit"].startswith(commit), r["morph_commit"])
                self.assertEqual(r["toolchain"], {k: cfg[k] for k in H.PIN_KEYS})
                self.assertIsInstance(r["command"], str)
                self.assertTrue(r["command"].strip())

    def test_harnesses_drive_the_real_code_and_keep_dependencies_outside(self):
        go = (ROOT / H.HARNESS["go"]).read_text(encoding="utf-8")
        for needle in ("package batch", "BatchHeaderV0", "BatchHeaderV1", ".Bytes()", "validate()"):
            self.assertIn(needle, go)
        sol = (ROOT / H.HARNESS["solidity"]).read_text(encoding="utf-8")
        for needle in ("pragma solidity", "BatchHeaderCodecV0", "BatchHeaderCodecV1", "_loadBatchHeader"):
            self.assertIn(needle, sol)
        bad = [str(p.relative_to(ROOT)) for p in (ROOT / "replay" / "M2").rglob("*")
               if p.name in ("node_modules", "lib", "vendor", "out", "cache", "bunfig.toml", ".env", "go.sum")]
        self.assertEqual(bad, [], "harness dependencies stay outside the repo")


# ---------------------------------------------------------------- corpus (I16-P2)
class _CorpusChecks:
    @classmethod
    def setUpClass(cls):
        cls.C = holon_module("holon.corpus")
        cls.fx = H.facts()
        cls.corpora = {e: cls.C.corpus(e) for e in H.EDGES}

    def check_grammar(self, edges):
        self.assertEqual(self.C.GRAMMAR_SAMPLES, H.GRAMMAR_SAMPLES)
        for edge in edges:
            with self.subTest(edge=edge):
                items = self.corpora[edge]
                self.assertTrue(all(it["source"] in H.SOURCES for it in items))
                grammar = [it["input"] for it in items if it["source"] == "grammar"]
                self.assertEqual(len(grammar), H.GRAMMAR_SAMPLES)
                for it in items:
                    self.assertTrue(H.well_formed(self.fx, edge, it["input"]), it)
                    self.assertTrue(H.in_domain(self.fx, edge, it["input"]), it)

    def check_boundary(self, edges):
        for edge in edges:
            boundary = [it["input"] for it in self.corpora[edge] if it["source"] == "boundary"]
            for desc, pred in H.required_boundary(edge):
                with self.subTest(edge=edge, boundary=desc):
                    self.assertTrue(any(pred(x) for x in boundary), f"{edge}: no boundary input with {desc}")

    def check_witnesses(self, edges):
        for edge in edges:
            wits = [it["input"] for it in self.corpora[edge] if it["source"] == "witness"]
            want = H.m0_witnesses(edge)
            self.assertTrue(want, f"{edge}: the M0 records hold REFUTED witnesses of its sort")
            for w in want:
                with self.subTest(edge=edge):
                    self.assertIn(w, wits)

    def check_records_compare_the_corpus(self, edges):
        for edge in edges:
            with self.subTest(edge=edge):
                items, r = self.corpora[edge], H.edge_record(edge)
                counts = {s: sum(1 for it in items if it["source"] == s) for s in H.SOURCES}
                self.assertEqual({s: r["corpus"][s] for s in H.SOURCES}, counts)
                self.assertEqual(r["corpus"]["seed"], self.C.SEED)
                self.assertEqual(r["corpus"]["inputs_sha256"], H.sha256_json([it["input"] for it in items]))
                self.assertEqual(r["compared"], len(items))
                self.assertEqual(r["agree"] + r["disagreements"], r["compared"])


class TestCorpus(_CorpusChecks, unittest.TestCase):
    """I16-P2: per codec edge, 2,000 grammar samples, all boundary values, all witnesses."""

    def test_two_thousand_grammar_samples_per_codec_edge(self):
        """I16-P2: exactly 2,000 seeded grammar samples per CODEC edge, each a well-formed input in the
        edge's domain."""
        self.check_grammar(H.CODEC_EDGES)

    def test_all_boundary_values_per_codec_edge(self):
        """I16-P2: every sort-boundary value of §8.7 (rule: tests_m2/_i16.py::required_boundary)."""
        self.check_boundary(H.CODEC_EDGES)

    def test_all_witnesses_per_codec_edge(self):
        """I16-P2: every REFUTED M0 witness of the edge's input sort (L_dom_hdr's for dec_go;
        L_par_hdr_v2's and L_par_hdr_ssvh's for the encoders)."""
        self.check_witnesses(H.CODEC_EDGES)

    def test_records_compare_the_whole_corpus(self):
        """I16-P2: the record compares exactly that corpus (counts and input digest)."""
        self.check_records_compare_the_corpus(H.CODEC_EDGES)

    def test_corpus_is_deterministic_across_processes(self):
        """Construction (AGENTS rule 7): the same corpus under different hash seeds."""
        here = {e: H.sha256_json(self.corpora[e]) for e in H.EDGES}
        code = ("import hashlib, json, sys; sys.path.insert(0, sys.argv[1]); from holon import corpus as C; "
                "print(json.dumps({e: hashlib.sha256(json.dumps(C.corpus(e), sort_keys=True, separators=(',', ':'), "
                "ensure_ascii=False).encode('utf-8')).hexdigest() for e in sys.argv[2:]}))")
        for seed in ("0", "4242"):
            p = subprocess.run([sys.executable, "-c", code, str(ROOT), *H.EDGES], cwd=ROOT, capture_output=True,
                               text=True, timeout=600, env={**os.environ, "PYTHONHASHSEED": seed})
            self.assertEqual(p.returncode, 0, p.stderr[-1500:])
            self.assertEqual(json.loads(p.stdout), here)


class TestDomainCorpus(_CorpusChecks, unittest.TestCase):
    """I16-P3, "decoder domains included": the domain predicates ok_go and ok_sol are compared on a Bytes
    corpus built by the same rule as the codec edges'."""

    def test_domain_predicates_follow_the_corpus_rule(self):
        self.check_grammar(H.DOMAIN_EDGES)
        self.check_boundary(H.DOMAIN_EDGES)
        self.check_witnesses(H.DOMAIN_EDGES)
        self.check_records_compare_the_corpus(H.DOMAIN_EDGES)


# ---------------------------------------------------------------- agreement (I16-P3)
class TestAgreement(unittest.TestCase):
    """I16-P3: 0 disagreements on every faithful edge, v2 inputs included, decoder domains included.
    Every edge is treated as faithful: no record can be excluded."""

    @classmethod
    def setUpClass(cls):
        cls.fx = H.facts()
        cls.corpora = {e: corpus_of(e) for e in H.EDGES}

    def test_zero_disagreements_on_every_edge(self):
        """I16-P3: every refinement record (the six above and any other under results/M2/refinement/)."""
        files = sorted(H.REF_DIR.glob("*.json"))
        self.assertTrue({f"{e}.json" for e in H.EDGES} <= {f.name for f in files}, [f.name for f in files])
        for f in files:
            with self.subTest(record=f.name):
                r = load_json(f)
                self.assertEqual(r["disagreements"], 0)
                self.assertEqual(r["disagreement_ids"], [])
                self.assertEqual(r["agree"], r["compared"])
                self.assertGreater(r["compared"], 0)
                self.assertRegex(r["outputs_sha256"]["model"], H.HEX64)
                self.assertEqual(r["outputs_sha256"]["real"], r["outputs_sha256"]["model"])

    def test_model_side_matches_the_reference_interpreter(self):
        """I16-P3: the model digest each record reports is the frozen reference interpreter's over the
        same corpus, so the model side was really evaluated on every input."""
        for edge in H.EDGES:
            with self.subTest(edge=edge):
                want = H.sha256_json([H.ref_output(self.fx, edge, it["input"]) for it in self.corpora[edge]])
                self.assertEqual(H.edge_record(edge)["outputs_sha256"]["model"], want)

    def test_v2_inputs_included_for_enc_go_v1(self):
        """I16-P3: enc_go_v1's corpus holds version-2 headers (from the grammar and from the boundary
        values); on them the model's enc_go_v1 writes byte 0 = 1, as Go's Bytes() does (the Go side is
        checked by TestIndependentGo), and the record counts 0 disagreements."""
        v2 = [it for it in self.corpora["enc_go_v1"] if it["input"]["version"] == "0x02"]
        self.assertTrue(any(it["source"] == "grammar" for it in v2), "no version-2 grammar sample")
        self.assertTrue(any(it["source"] == "boundary" for it in v2), "no version-2 boundary value")
        for it in v2:
            self.assertTrue(H.ref_output(self.fx, "enc_go_v1", it["input"]).startswith("0x01"))
        self.assertEqual(H.edge_record("enc_go_v1")["disagreements"], 0)

    def test_decoder_domains_included(self):
        """I16-P3: dec_go, ok_go and ok_sol are compared on inputs inside and outside their domains
        (ok_go for dec_go and ok_go, ok_sol for ok_sol), the record's domain counts are those, and each
        record counts 0 disagreements."""
        pred = {"dec_go": "ok_go", "ok_go": "ok_go", "ok_sol": "ok_sol"}
        for edge, p in pred.items():
            with self.subTest(edge=edge):
                inside = sum(1 for it in self.corpora[edge]
                             if H.RM.predicate(self.fx, p, H.RM.unhex(it["input"])))
                outside = len(self.corpora[edge]) - inside
                self.assertGreater(inside, 0)
                self.assertGreater(outside, 0)
                r = H.edge_record(edge)
                self.assertEqual(r["domain"], {"in": inside, "out": outside})
                self.assertEqual(r["disagreements"], 0)


class TestIndependentGo(unittest.TestCase):
    """I16-P3, Go side measured by the prereg instrument (tests_m2/_i16.py::run_go_instrument), not by
    the I16 harness. The toolchain and the morph checkout are pinned in config/holon.json: never skipped."""

    @classmethod
    def setUpClass(cls):
        cls.fx = H.facts()
        cls.recs = {e: H.edge_record(e) for e in H.GO_EDGES}
        cls.corpora = {e: corpus_of(e) for e in H.GO_EDGES}
        cls.go = H.run_go_instrument({e: [it["input"] for it in cls.corpora[e]] for e in H.GO_EDGES})

    def test_go_real_outputs_match_the_records(self):
        """I16-P3: each Go record's real-output digest is what the real Go code returns on its corpus."""
        for edge in H.GO_EDGES:
            with self.subTest(edge=edge):
                self.assertEqual(len(self.go[edge]), len(self.corpora[edge]))
                self.assertEqual(H.sha256_json(self.go[edge]), self.recs[edge]["outputs_sha256"]["real"])

    def test_go_writes_byte0_1_on_v2_inputs_like_the_model(self):
        """I16-P3: "enc_go_v1 writes byte 0 = 1 exactly as Go does"."""
        n = 0
        for it, out in zip(self.corpora["enc_go_v1"], self.go["enc_go_v1"]):
            if it["input"]["version"] == "0x02":
                n += 1
                self.assertTrue(out.startswith("0x01"), out[:6])
                self.assertEqual(out, H.ref_output(self.fx, "enc_go_v1", it["input"]))
        self.assertGreater(n, 0)


class TestIndependentSolidity(unittest.TestCase):
    """I16-P3, Solidity side measured by the prereg instrument (tests_m2/_i16.py::run_sol_instrument), not by
    the I16 harness. forge, solc, the dependencies and the morph checkout are pinned: never skipped."""

    @classmethod
    def setUpClass(cls):
        cls.recs = {e: H.edge_record(e) for e in H.SOL_EDGES}
        cls.corpora = {e: corpus_of(e) for e in H.SOL_EDGES}
        cls.sol = H.run_sol_instrument({e: [it["input"] for it in cls.corpora[e]] for e in H.SOL_EDGES})

    def test_solidity_real_outputs_match_the_records(self):
        """I16-P3: each Solidity record's real-output digest is what the real Solidity code returns on its
        corpus."""
        for edge in H.SOL_EDGES:
            with self.subTest(edge=edge):
                self.assertEqual(len(self.sol[edge]), len(self.corpora[edge]))
                self.assertEqual(H.sha256_json(self.sol[edge]), self.recs[edge]["outputs_sha256"]["real"])


class TestReproduction(unittest.TestCase):
    def test_refine_reproduces_the_dec_go_record(self):
        """Construction (AGENTS rule 7): `holon refine --edges dec_go` in a copy rewrites the committed
        dec_go record byte for byte (it runs the Go harness on the pinned toolchain)."""
        repo = copy_repo()
        try:
            out = repo / "i16_refine_out"
            fixes = [a for c in H.edge_record("dec_go")["fixes"] for a in ("--fix", c)]
            p = run_holon(["refine", "--milestone", "M0", "--edges", "dec_go", "--out", str(out), *fixes], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertEqual((out / "dec_go.json").read_bytes(), (H.REF_DIR / "dec_go.json").read_bytes())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------- cross-edge PAR differences (I16-P4)
class TestCrossEdge(unittest.TestCase):
    """I16-P4: O1 and O2 are cross-edge PAR differences linked to L_dom_hdr and L_par_hdr_v2, not
    refinement disagreements."""

    @classmethod
    def setUpClass(cls):
        cls.doc = load_json(H.CROSS)
        cls.fx = H.facts()
        cls.laws = laws("M0")
        cls.recs = records("M0")

    def find(self, edges: list[str], law: str) -> dict:
        hits = [d for d in self.doc["differences"] if d["edges"] == edges and d["law"] == law]
        self.assertEqual(len(hits), 1, f"one PAR difference {edges} linked to {law}: {self.doc['differences']}")
        d = hits[0]
        self.assertEqual(d["kind"], "PAR")
        self.assertGreaterEqual(d["count"], 1)
        self.assertEqual(self.recs[law]["status"], "REFUTED")
        self.assertEqual(H.claim_calls(self.laws[law]), set(edges))
        self.assertTrue(H.satisfies_premises(self.laws[law], d["example"]), d["example"])
        return d

    def test_o1_is_a_cross_edge_difference_linked_to_l_dom_hdr(self):
        """I16-P4 (O1): ok_sol accepts what ok_go rejects."""
        d = self.find(["ok_go", "ok_sol"], "L_dom_hdr")
        ex = d["example"]
        self.assertNotEqual(H.ref_output(self.fx, "ok_sol", ex), H.ref_output(self.fx, "ok_go", ex))

    def test_o2_is_a_cross_edge_difference_linked_to_l_par_hdr_v2(self):
        """I16-P4 (O2): on a version-2 header, enc_sol writes byte 0 = 2 and enc_go_v1 writes 1."""
        d = self.find(["enc_go_v1", "enc_sol"], "L_par_hdr_v2")
        ex = d["example"]
        sol, go = H.ref_output(self.fx, "enc_sol", ex), H.ref_output(self.fx, "enc_go_v1", ex)
        self.assertEqual(sol[2:4], "02")
        self.assertEqual(go[2:4], "01")

    def test_o1_o2_are_not_in_the_refinement_counts(self):
        """I16-P4: the four edges O1 and O2 involve each count 0 refinement disagreements, and no
        disagreement entry is explained by L_dom_hdr or L_par_hdr_v2."""
        for edge in ("ok_go", "ok_sol", "enc_go_v1", "enc_sol"):
            with self.subTest(edge=edge):
                self.assertEqual(H.edge_record(edge)["disagreements"], 0)
        for e in load_json(H.DISAGREEMENTS)["disagreements"]:
            self.assertNotIn(e.get("links", {}).get("law"), ("M0/L_dom_hdr", "M0/L_par_hdr_v2"), e)

    def test_every_linked_difference_names_a_law_comparing_its_pair(self):
        """I16-P4: links are mechanical. A law named by a difference is a REFUTED M0 law whose claim
        compares exactly that pair, and the example satisfies its premises."""
        pairs = self.doc["pairs"]
        for p in (["enc_go_v1", "enc_sol"], ["ok_go", "ok_sol"]):
            self.assertIn(p, pairs)
        self.assertEqual(self.doc["milestone"], "M0")
        for d in self.doc["differences"]:
            with self.subTest(diff=(d["edges"], d["law"])):
                self.assertEqual(d["edges"], sorted(d["edges"]))
                self.assertIn(d["edges"], pairs)
                self.assertEqual(d["kind"], "PAR")
                if d["law"] is not None:
                    self.assertIn(d["law"], self.laws)
                    self.assertEqual(self.recs[d["law"]]["status"], "REFUTED")
                    self.assertEqual(H.claim_calls(self.laws[d["law"]]), set(d["edges"]))
                    self.assertTrue(H.satisfies_premises(self.laws[d["law"]], d["example"]))


# ---------------------------------------------------------------- disagreements (I16-P5)
class TestDisagreements(unittest.TestCase):
    def test_zero_unexplained(self):
        """I16-P5: every entry classifies, from its links, to its label and never to unexplained; every
        disagreement id a refinement record lists has an entry; check_disagreements finds nothing."""
        R = holon_module("holon.refinement")
        self.assertEqual(tuple(R.CLASSES), H.CLASSES)
        doc = load_json(H.DISAGREEMENTS)
        self.assertIsInstance(doc["disagreements"], list)
        ids = set()
        for e in doc["disagreements"]:
            with self.subTest(entry=e.get("id")):
                want = H.expected_class(e, ROOT)
                self.assertNotEqual(want, "unexplained", e)
                self.assertEqual(R.classify(e, ROOT), want, e)
                self.assertEqual(want, e["class"], e)
                ids.add(e["id"])
        for f in sorted(H.REF_DIR.glob("*.json")):
            for did in load_json(f)["disagreement_ids"]:
                self.assertIn(did, ids, f"{f.name}: {did} has no entry")
        self.assertEqual(R.check_disagreements(ROOT), [])


def classifier_root() -> Path:
    """A minimal tree: the records, replay reports and laws the classes read, the hypothesis records plus
    the fixture's failing one, and the fixture's re-run records (none of these fixture files are in ROOT)."""
    fx = load_json(H.FIX / "classifier_cases.json")
    root = Path(tempfile.mkdtemp(prefix="holon-i16-classify-"))
    for d in ("laws/M0", "laws/M1", "results/M0", "results/M1"):
        shutil.copytree(ROOT / d, root / d)
    for f in ("replay/M0/report.json", "replay/M1/report.json"):
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, root / f)
    hyp = load_json(ROOT / "results" / "M2" / "hypotheses.json")
    hyp.update(fx["hypotheses"])
    (root / "results" / "M2").mkdir(parents=True, exist_ok=True)
    write_json(root / "results" / "M2" / "hypotheses.json", hyp)
    for rel, obj in fx["files"].items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        write_json(root / rel, obj)
    return root


class TestClassifier(unittest.TestCase):
    """Construction: the mechanical classes follow the links (fixture cases fixed at this prereg)."""

    @classmethod
    def setUpClass(cls):
        cls.R = holon_module("holon.refinement")
        cls.fx = load_json(H.FIX / "classifier_cases.json")
        cls.root = classifier_root()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_classes_follow_the_links(self):
        for case in self.fx["cases"]:
            with self.subTest(case=case["entry"]["id"]):
                self.assertEqual(self.R.classify(case["entry"], self.root), case["expected"], case.get("why"))

    def test_the_label_is_never_trusted(self):
        for case in self.fx["cases"]:
            for label in H.CLASSES:
                with self.subTest(case=case["entry"]["id"], label=label):
                    e = dict(case["entry"], **{"class": label})
                    self.assertEqual(self.R.classify(e, self.root), case["expected"])

    def test_a_witness_that_no_longer_matches_its_replay_is_unexplained(self):
        root = classifier_root()
        try:
            rep = load_json(root / "replay" / "M0" / "report.json")
            rep["witness_sha256"]["L_dom_hdr"] = "0" * 64
            write_json(root / "replay" / "M0" / "report.json", rep)
            case = next(c for c in self.fx["cases"] if c["entry"]["id"] == "C-real-m0")
            self.assertEqual(self.R.classify(case["entry"], self.root), "real_defect")
            self.assertEqual(self.R.classify(case["entry"], root), "unexplained")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_check_disagreements_names_every_unexplained_or_mislabelled_entry(self):
        root = classifier_root()
        try:
            by_id = {c["entry"]["id"]: c["entry"] for c in self.fx["cases"]}
            good, mislabelled, red = by_id["C-extraction-ok"], by_id["C-label-ignored"], by_id["D-fixture-red"]
            (root / "spec" / "M2").mkdir(parents=True, exist_ok=True)
            write_json(root / "spec" / "M2" / "disagreements.json", {"disagreements": [good, mislabelled, red]})
            problems = "\n".join(self.R.check_disagreements(root))
            self.assertIn("C-label-ignored", problems)
            self.assertIn("D-fixture-red", problems)
            self.assertNotIn("C-extraction-ok", problems)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class TestGateGREF(unittest.TestCase):
    """GREF: the gate checks the links, not the labels."""

    def test_gref_is_a_gate_check(self):
        """Construction."""
        self.assertIn("GREF", holon_module("holon.gate").CHECK_ORDER)

    def test_gref_passes_on_the_committed_tree(self):
        """I16-P5: GREF passes on a copy of the committed tree (no .git)."""
        repo = copy_repo()
        try:
            p, rep = run_gate(repo, "GREF")
            self.assertIsNotNone(rep, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertIn("GREF", rep["checks"])
            self.assertTrue(rep["checks"]["GREF"]["passed"], rep["checks"]["GREF"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_gref_fails_on_a_mislabelled_entry(self):
        """Construction: a 'real_defect' linked to a PROVED law is unexplained; GREF fails and names it."""
        repo = copy_repo()
        try:
            p = repo / "spec" / "M2" / "disagreements.json"
            doc = load_json(p)
            doc["disagreements"].append({"id": "D-i16-mislabelled", "edge": "enc_sol", "milestone": "M0",
                                         "input": None, "model": "0x00", "real": "0x01", "class": "real_defect",
                                         "links": {"law": "M0/L_par_hdr_v0"}})
            write_json(p, doc)
            proc, rep = run_gate(repo, "GREF")
            self.assertIsNotNone(rep, proc.stdout[-2000:] + proc.stderr[-2000:])
            self.assertFalse(rep["checks"]["GREF"]["passed"])
            self.assertIn("D-i16-mislabelled", rep["checks"]["GREF"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_gref_fails_on_an_unrecorded_disagreement(self):
        """Construction: a disagreement a refinement record counts, with no entry, fails GREF."""
        repo = copy_repo()
        try:
            p = repo / "results" / "M2" / "refinement" / "enc_go_v1.json"
            r = load_json(p)
            r.update(disagreements=r["disagreements"] + 1, agree=r["agree"] - 1,
                     disagreement_ids=r["disagreement_ids"] + ["D-i16-unrecorded"])
            write_json(p, r)
            proc, rep = run_gate(repo, "GREF")
            self.assertIsNotNone(rep, proc.stdout[-2000:] + proc.stderr[-2000:])
            self.assertFalse(rep["checks"]["GREF"]["passed"])
            self.assertIn("D-i16-unrecorded", rep["checks"]["GREF"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------- refinement_refs in records
class TestRefinementRefs(unittest.TestCase):
    """Construction: records gain refinement_refs; pending:I16 is removed (BUILD_PLAN I1: the iteration
    that fills a pending field removes its pending value from the schema and asserts that removal)."""

    def test_schema_no_longer_accepts_pending_I16(self):
        schema = SCHEMAS2 / "result_record_v2.schema.json"
        rec = records("M0")["L_dom_hdr"]
        self.assertEqual(validate(dict(rec, refinement_refs=["results/M2/refinement/ok_go.json"]), schema), [])
        errs = validate(dict(rec, refinement_refs="pending:I16"), schema)
        self.assertTrue(any("refinement_refs" in e for e in errs), errs)

    def test_m0_records_reference_the_refined_edges_in_their_cone(self):
        for lid, rec in records("M0").items():
            with self.subTest(law=lid):
                want = sorted(f"results/M2/refinement/{e}.json" for e in H.EDGES if e in rec["cone"])
                self.assertTrue(want, f"{lid}: every M0 cone holds a refined edge")
                self.assertEqual(rec["refinement_refs"], want)

    def test_m1_records_reference_the_corpus_actions_in_their_cone(self):
        per_action = load_json(ROOT / "replay" / "M1" / "report.json")["refinement"]["per_action"]
        for lid, rec in records("M1").items():
            with self.subTest(law=lid):
                want = sorted(f"replay/M1/report.json#/refinement/per_action/{a}" for a in per_action
                              if f"step_{a}" in rec["cone"])
                self.assertEqual(rec["refinement_refs"], want)

    def test_every_ref_resolves_to_a_record_without_disagreements(self):
        n = 0
        for m in ("M0", "M1"):
            for lid, rec in records(m).items():
                self.assertIsInstance(rec["refinement_refs"], list, lid)
                for ref in rec["refinement_refs"]:
                    with self.subTest(law=lid, ref=ref):
                        path, _, pointer = ref.partition("#")
                        target = load_json(ROOT / path)
                        for part in [x for x in pointer.split("/") if x]:
                            target = target[part]
                        bad = target.get("disagreements", target.get("disagree"))
                        self.assertEqual(bad, 0, target)
                        n += 1
        self.assertGreater(n, 0)


# ---------------------------------------------------------------- regression (I16-R1)
class TestM1Corpus(unittest.TestCase):
    def test_m1_corpus_has_no_disagreements(self):
        """I16-R1 (regression): 0 disagreements on the M1 corpus."""
        rep = load_json(ROOT / "replay" / "M1" / "report.json")
        rf = rep["refinement"]
        self.assertGreater(rf["traces"], 0)
        self.assertEqual(rf["n_disagreements"], 0)
        self.assertEqual(rf["disagreements"], [])
        self.assertTrue(all(v["disagree"] == 0 for v in rf["per_action"].values()), rf["per_action"])
        self.assertIs(rep["harness_mismatch"], False)


if __name__ == "__main__":
    unittest.main()
