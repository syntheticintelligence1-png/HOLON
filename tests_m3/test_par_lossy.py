"""I25: PAR-lossy and injective pushing over the frozen evidence set (whitepaper §10.3 step 6, Prop 6.11, Lemma 6.12,
L3; Def 4.4 and 4.5, Cor 6.16, §10.2, §12 L3 and L21; BUILD_PLAN I25; docs/HUMAN_ANSWERS.md, delegated Q19). This
docstring is the contract that tests_m3/test_par_lossy.py checks.

Instruments fixed at the prereg: tests_m3/_i25.py (rules L1-L9 written out a second time, independently of holon/, on
top of the I24 instruments tests_m3/_i24x.py and _i24.py), the planted fixture tests_m3/fixtures/par_lossy/ (I24's
linked fixture with one Go layout cell changed, see its derive_extracted.json, which makes its version-1 pair
injective; its version-2 pair stays non-injective because getter B is blind on 9-byte headers) and the frozen
sidecar spec/M3/lib/par_lossy.json (every value this contract predicts, computed at the prereg by
tests_m3/_i25.py::par_lossy_doc from the inputs it lists with their sha256; the core statements of rule L7; D7).

What the plan asks and what today's evidence set holds
  BUILD_PLAN I25: enumerate evidenced lossy pairs from the frozen evidence set, push through injective maps (Lemma
  6.12), report evidenced-pair coverage, open an evidence review for every uncovered replay disagreement; Lemma 6.12
  inj_push as a core law under CF premises for hash maps. Q19: everything here is over the adopted extracted documents.
  The frozen evidence set gen/M3/evidence.json (I24) holds 161 atoms over the one linked codec component header_length
  (rule X7: E1 102 = 70 inverse + 32 common_decoder, E2 55, E6 4) and an anchors-only model of the transitions document
  (no diagram, no atom: I24 gap G1). Every lossy edge of the component is a single-read decoder (a getter: a
  projection, Def 4.4) or enc_sol at version 0 (it drops lastBlockNumber), so every evidenced pair is a lossy pair.
  I24 already derived the obligations those atoms evidence where a rule exists: one round trip per inverse atom and,
  per group of common-decoder atoms, a cross-component law and its pinned variant. I25 adds no rule that derives a law
  (gap L-G1): it classifies the fragment, enumerates the evidenced lossy elements, decides by Lemma 6.12 which
  cross-component law is the pushed basis law of its pair and which over-claims (Prop 6.11), certifies each
  over-claim's collision in Bend, states inj_push as a core law, and measures coverage relative to the evidence set.

Gaps preregistered
  L-G1 No new law and no catalog version. PAR-lossy derives no law on today's set: its pushed laws are I24's
       cross-component laws (rule L4), and the evidenced reads that recover no field (rule L3: constant and partial
       reads) have no sub-form that states them. holon.rules.CATALOGS and catalog_version("M3") are untouched by I25,
       so I27's and I31's catalog pins (holon-rules/1.3, 1.4) are unaffected; laws/M3/ gains no file.
  L-G2 No HASH push has an instance. Rule X7 gives no atom through a HASH edge: the comparison that would evidence one
       (keccak256 of a presented header against the stored committedBatches entry, Rollup.sol:849 against :357) is a
       guard of the transitions document, which has no M3 diagram (I24 G1, G3: O7 stays a rule gap). Rule L6 lists such
       pairs as unevidenced candidates; they are not counted in coverage (Prop 6.11: completeness is relative to the
       evidenced set).
  L-G3 D7 (the 32-bit truncation of the Merkle tree index, discharged by leaf injectivity under CF; whitepaper §11.6)
       is a pushing candidate outside today's extraction: its sites (contracts/contracts/libraries/common/Verify.sol:9,
       :14-15; contracts/contracts/l1/L1CrossDomainMessenger.sol:138, :155) are in no adopted M3 document (the Solidity
       extractions cover Rollup.sol only). Its instance, a push through the leaf hash by core_inj_push under
       CF(keccak256, S), is I36's (BUILD_PLAN I36). The sidecar records it under "deferred".
  L-G4 Constant and partial reads are uncovered, reason no_rule. A new sub-form needs rule admission (L7: two instances
       and a basis argument; I45). Morph has 4 such pairs (6 elements); the question is raised for the human.
  L-G5 Coverage is direct: an element is covered by a law whose basis is that element (rules L3, L4), never by an
       implication between laws (that is I42/I43's).
  L-G6 Machine documents (holon-facts/0.2) and the transitions document are not analysed: no M3 diagram (G1).
  L-G7 No replay record is over an M3 component edge. Every codec and domain refinement record (results/M2/refinement/
       and historical/, 12 of the 15) names the hand-written M0 document facts/morph_header.json; the other three
       (extracted.json, historical/commitBatch.json and historical/finalizeBatch.json) name the transitions document
       spec/M2/facts/morph_rollup.extracted.json, which has no M3 diagram. So under rule L9 a future disagreement in any of them resolves to no
       component edge and opens a review with reason unresolved_edge; "covered" can only arise once an M3 codec edge
       has a record of its own (L1 replay over the extracted codec model; raised for the human).

CLI (every JSON file: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; deterministic, no timestamps)
  python -m holon lossy --milestone M [--root DIR] [--out DIR] [--review PATH] [--records DIR] [--codec PATH ...]
                        [--gen-dir DIR] [--check]
    Writes <out, default <root>/gen/<M>/par_lossy>/<role>.json for every linked component (rule L8),
    <out>/core/LAWS.bend and PROOF.bend (rule L7), <out>/collisions/<law_id>/LAWS.bend and PROOF.bend (rule L5), and
    the review <review> (rule L9; default <root>/spec/<M>/evidence_review.jsonl for a milestone M<k>,
    <out>/evidence_review.jsonl for a test milestone T<k>); it removes any other file under <out>. Exit 0 written;
    1 (--check) a file differs from a fresh build, nothing written; 2 refused, nothing written: an input missing,
    malformed or stale, named in the message; 3 a construct the rules refuse, named, nothing written.
    M<k>: the components are gen/<M>/codec/*.json with gen/<M>/diagram/<role>.json and the frozen evidence set
    gen/<M>/evidence.json, each byte for byte what holon codecs, diagram and evidence write now (else exit 2, as I24's
    derive); the component model (rule L5) is gen/<M>/model/<role>.bend, written by holon run (I24 rule X9); the
    refinement records are <records, default results/M2/refinement>/*.json and <records>/historical/*.json (a
    --records directory outside the root is refused, exit 2; a record's path in the review is root-relative).
    T<k>: --codec PATH names each linked codec document (as derive); its diagram and the evidence set are built in
    memory (as derive builds them); the component model is <gen-dir, default gen/<T>>/model/<role>.bend; records only
    when --records is given.
    It reads no law file and no record: I24's PAR basis over each component (rules X8, P0-P12) is recomputed in memory
    with holon-rules/1.1's PAR producers, exactly as derive computes it; every law id it names is a committed law of
    laws/<M> with that statement.
  python -m holon metrics --milestone M3 writes results/M3/metrics.json with the key "evidenced_pair_coverage" (rule
    L8), computed from gen/M3/par_lossy/*.json and spec/M3/evidence_review.jsonl; M0-M2 metrics are unchanged.

Rules (holon/rules/par_lossy.py; tests_m3/_i25.py writes each one out again)
  L0 Scope. Each linked codec component (facts_version holon-linked/0.1) of the milestone with its diagram and its
     atoms in the evidence set. No hand document is read (Q19). Names in outputs are diagram edge ids (CODEC.<fn>,
     HASH.<op>), law ids of I24's PAR basis, atom ids of the evidence set and record paths.
  L1 Fragment (Def 4.4: invertible iff injective on R_src; §10.2 layout algebra; Cor 6.16). One entry per CODEC and
     HASH edge, sorted by (edge, version): an encoder gets one entry per version v of its label, class "invertible" when
     its layout at v holds ["field", F, k] for every field F of its source record and every k < width(F), else "lossy",
     with "dropped": the fields not held whole, in record order ("version" is not counted on R_v when the record has a
     field named version: P0 fixes it), "dropped": [] when invertible; a decoder gets one entry (version null), class
     "lossy" iff its read offset is > 0 or some ok path accepts a byte string one byte longer than offset + width (any
     tag byte 0..255), else "invertible", with "reads": [offset, width]; a loader gets "unmodelled" (rule X5 models its
     domain only); a HASH edge gets "cf" (invertible under CF(h, S) for a finite S a law states, never globally).
     Entries: {"edge", "version", "class"} plus "dropped" (encoders) or "reads" (decoders).
  L2 Elements (the evidenced lossy pairs). From the component's atoms of levels E1-E5 (Def 4.5: PAR's obligations need
     evidence at least medium; E6 atoms are PAR-weak's intent questions and are counted under "weak" only):
     (a) round_trip: one per E1 inverse atom (encoder p, decoder q, its version);
     (b) observed: one per (p, q, v) with E1 common_decoder atoms (the X8b group): its observation family is the
         sorted set of those atoms' decoders, its push laws I24's cross-component laws of that group (rule L4);
     (c) constant_read / partial_read: one per E2 atom (writer p, reader q) and per common version v of p's and q's
         labels (P0: the intersection of the labels that carry one; v null when neither does) that has no inverse atom
         (p, q, v): constant_read when every cell of p's layout at v in q's read range is a constant ("bytes": those
         constants, "0x" lower-case hex), else partial_read; an E2 atom with no common version is excluded:
         {"atom", "p", "q", "reason": "no_common_version"} under "excluded", sorted by atom id;
     (d) other: one per E3, E4 or E5 atom (none over a component, rule X7).
     Element: {"kind", "p", "q", "version", "atoms": sorted ids, "laws": sorted, "covered", "reason"} plus "family",
     "blind" and "pushes" (observed) or "bytes" (constant_read); sorted by (kind in the order round_trip, observed,
     constant_read, partial_read, other; p; q; version with null first). "weak": {"atoms": E6 atoms, "with_law": E6
     atoms whose PAR-weak basis element gave a law or a duplicate}.
  L3 Coverage of an element. round_trip: covered iff its round_trip basis element (key {"atom": id}) gave a law or a
     duplicate; "laws": those ids; else reason no_law. observed: covered iff one of its push laws is pushed (rule L4);
     "laws": the pushed ones; else reason non_injective. constant_read, partial_read, other: never covered, reason
     no_rule (gap L-G4), "laws": [].
  L4 Push verdict (Lemma 6.12 by position). For a push law with claim [p(h), q(k)] and premises: the two layouts at v
     (rules X3, X4), a field cell of a binder replaced by the constant a premise pins it to (the version premise and
     the pins; correspondence premises fix no value). A family decoder is blind when it rejects a byte string of the
     images' length whose tag byte is v (I24's decoder conditions, as rule X9 evaluates them; P0: the version premise
     fixes the tag): it returns its error on every image, so it separates none of them and its read range is not
     observed. The observed positions are the union of the read ranges of the family's decoders that are not blind.
     The law is pushed iff the layouts have one length and every position that is not observed holds one constant in
     both; then the family is injective on p(R_v) and q(R_v) and Lemma 6.12 makes the law equivalent to the evidenced
     obligation (the observations agree), so it is the basis law of the pair and the kernel's verdict on it decides
     that obligation (PROVED: the pair agrees; REFUTED: an obstruction on an evidenced pair, a finding). Otherwise it
     is not pushed: the family is not injective on the images and the law claims more than any observation relates
     (Prop 6.11). It may then still be PROVED (it holds beyond the evidence; by core_inj_pull it implies the
     obligation) or REFUTED (possibly an over-claim: rule L5 certifies the collision). "collision": the first position
     that fails {"position", "kind", "p": its cell, "q": its cell}, kind "length" (cells null), "constants_differ",
     "unknown_cell" (an unwritten Solidity cell) or "unobserved_field". "pushes": [{"law", "pushed", "collision"}]
     sorted by law; the observed element also lists "blind": its blind decoders, sorted. A static verdict never changes
     a kernel status and a kernel status never changes a verdict; where they diverge from today's pairing (pushed and
     PROVED, not pushed and REFUTED) the divergence is reported.
  L5 Collision certificates (Prop 6.11 at a point). For each push law that is not pushed, W is the ones fill under its
     premises (every field byte of each binder 0x01, except the fields the version premise and the pins fix, which
     take those bytes; correspondence premises then hold). Kind "cross" when the two images of W differ at the
     collision (or in length): <out>/collisions/<law_id>/LAWS.bend imports the component model and states, as closed
     laws, obs_<d> for each decoder d of the family (d(p(W_h)) == d(q(W_k)): the observations agree) and differ
     (p(W_h) != q(W_k)): the law's own premises hold at W and the law fails there although no observation sees it.
     Kind "same_side" when the premises tie the collision (the ones-fill images agree there): the first side s of p, q
     whose collision cell is a field F of its binder b, provided every position of F in s's layout is unobserved;
     W2 = W_b with F's bytes all 0x02; the laws are obs_<d>: d(s(W_b)) == d(s(W2)) and differ: s(W_b) != s(W2) (two
     inputs of one side whose images differ while every observation agrees: the family is not injective on s(R_v)).
     A not-pushed law for which neither kind applies gets no certificate and is listed under "uncertified" (sorted;
     none today). PROOF.bend imports ./LAWS.bend and proves each law by evaluation or by a counter-law (BEND_PRIMER
     5.4); no escape hatch. Bend must accept it with every law present. The document's "collisions": [{"law",
     "family", "kind", "side" (same_side only: "p" or "q"), "witness": {binder: {field: "0x.."}} (cross: every binder;
     same_side: b only), "witness2": null (cross) or {b: {field: "0x.."}}, "laws": the obs_<d> names sorted, then
     "differ", "dir": "collisions/<law_id>"}] sorted by law.
  L6 HASH candidates. For each HASH edge h (src carrier c, digest op), every pair of the component's functions whose
     selected sink has op and whose target is c: {"hash", "pair": [two edge ids, sorted], "sinks": the first entry of
     each sink stack, "evidenced": whether an atom relates the two edges, "atoms": those atom ids}, sorted by (hash,
     pair). A candidate is pushed under the pointwise CF premise of core_inj_push once evidence relates it; it is never
     an element.
  L7 Core laws (Lemma 6.12 under CF premises, Cor 6.16). <out>/core/LAWS.bend: "import Base", then exactly the three
     statements of spec/M3/lib/par_lossy.json "core" (core_inj_push: the pushing direction under the premise that h is
     collision-free on {f(x), g(x)} at every x, never global injectivity; core_inj_pull: the other direction, no
     premise; core_cf_succ: an inhabitant of the CF premise, whitepaper L21), in that order and nothing else;
     PROOF.bend imports ./LAWS.bend and fills each law from a proof generator (never hand-written; no escape hatch).
     Both kernels must accept it (bend and bend --verdict). The canary (the sidecar's canary_inj_push_without_cf:
     core_inj_push without cf, false by Prop 6.11) must not check with the generated proof of core_inj_push.
     Placement (a deviation from the plan's "core law", stated): the three laws live in gen/M3/par_lossy/core/, not in
     holon.gen.core's catalog (gen/<M>/core/, I8). That catalog holds Nat/Bool lemmas proved by its own proof classes
     and is emitted for every M2+ milestone, so adding a type-polymorphic law there would rewrite gen/M2/core and
     gen/M3/core (M2 byte-identity regressions, I8/I24 outputs). A later law that pushes through a hash (D7 in I36)
     imports gen/M3/par_lossy/core/PROOF.bend (never LAWS.bend alone, I8) and instantiates core_inj_push.
  L8 The document and the metric. <out>/<role>.json: {"lossy_version": "holon-lossy/0.1", "document": "par_lossy",
     "milestone", "model": role, "facts": the linked codec document (repo-relative), "inputs": [{"path", "sha256"}]
     sorted (M<k>: the codec document, its diagram and the evidence set; T<k>: the codec document), "fragment" (L1),
     "elements" (L2-L4), "excluded", "weak" (L2), "hash_candidates" (L6), "collisions" and "uncertified"
     (L5), "coverage": {"elements",
     "covered", "rate": covered / elements (null when 0), "by_kind": {kind: {"elements", "covered"}} for all five
     kinds, "uncovered": [{"kind", "p", "q", "version", "reason"}] in element order}}. results/M3/metrics.json
     "evidenced_pair_coverage": {"evidence": {"path": "gen/M3/evidence.json", "evidence_sha256": that file's},
     "relative_to": the sentence of tests_m3/_i25.py::RELATIVE_TO, "elements", "covered", "rate", "by_kind" (summed over
     components), "uncovered": the number of uncovered elements, "excluded": {"no_common_version": n}, "weak":
     {"atoms", "with_law"}, "hash_candidates": n, "uncovered_disagreements": the review's entries, "models": sorted}.
  L9 Evidence review (L3's uncovered replay disagreements; adjudicated by A4 in I45). The refinement records are the
     I16, I20 and I23 records (results/M2/refinement/*.json, historical/*.json: holon.refinement.record_files). A
     per-edge record's disagreements are its disagreement_ids, at its (facts, diagram_edge); a step record's (kind
     "extracted") are its "disagreements" entries, at (facts, TRANS.<action>) when the entry names an action, else at
     no edge. A disagreement is covered iff its (facts, edge) is a component diagram edge (id == edge, "component" ==
     facts) that is p, q or a family decoder of a covered element. Each other disagreement gets one entry
     {"id": "review:<record path>#<disagreement id>", "record", "disagreement", "facts", "edge", "m3_edge": the resolved
     edge or null, "reason": "unresolved_edge" | "no_covered_element", "status": "open", "adjudicator": "A4",
     "adjudication": "I45", "evidence_sha256"}; the file holds one json.dumps(entry, sort_keys=True) line per entry,
     sorted by id, and is empty (0 bytes) when there is none. Today's expected count is 0: the 15 records (7 under
     results/M2/refinement/, 8 under historical/) list no disagreement (every disagreement_ids is [], extracted.json's
     disagreements is [], and results/M2/metrics.json reports refinement.unexplained 0).

Rules for the build
  - AGENTS.md is binding. Never edit facts/, spec/M1/, spec/M2/, laws/M0-M2, gen/M0-M2, results/M0-M2, laws/M3/,
    gen/M3/codec/, gen/M3/diagram/ or gen/M3/evidence.json (the evidence set is frozen). No law is added (L-G1).
  - holon/rules/par_lossy.py and every holon/ module whose name contains "lossy" name no target or fixture identifier,
    no law id and no source file of the target (tests below). Fixtures are test instruments, never M3 documents.
  - No skips. Predictions are never tuned; a miss is a Surprise.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i24x as X
from tests_m3 import _i25 as L
from tests_m3._m3 import (ROOT, SPEC3, canonical_json, copy_repo, file_sha256, holon_module, laws, load_json,
                          records, run_bend, run_holon)

SIDECAR = SPEC3 / "lib" / "par_lossy.json"
OUT3 = ROOT / "gen" / "M3" / "par_lossy"
REVIEW3 = SPEC3 / "evidence_review.jsonl"
METRICS3 = ROOT / "results" / "M3" / "metrics.json"
COMPONENT = "header_length"
CODEC_DOC = "gen/M3/codec/header_length.json"
DIAGRAM_DOC = "gen/M3/diagram/header_length.json"
EVIDENCE_DOC = "gen/M3/evidence.json"
SEMANTIC = ("lossy_version", "document", "milestone", "model", "facts", "fragment", "elements", "excluded", "weak",
            "hash_candidates", "collisions", "uncertified", "coverage")
CORE_NAMES = ["core_inj_push", "core_inj_pull", "core_cf_succ"]
PATCH = "BatchCache_createBatchHeaderWithSequencerSetHash"
CC_FULL = sorted([f"L_par_cc_{PATCH}_enc_sol_v2", "L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0",
                  "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1"])
CC_PINNED = sorted(x + "_pinned" for x in CC_FULL)
ESCAPES = (re.compile(r"@unsafe"), re.compile(r"^\s*def\s+[\w.]+\?\s*\(", re.M), re.compile(r"\?[A-Za-z_]\w*"),
           re.compile(r"^\s*import\s+\"", re.M))
OK, FAIL = "ALL PROOFS CHECK", "SOME PROOFS FAIL"


def need(p: Path):
    p = Path(p)
    if not p.exists():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing (I25 builds it)")
    return load_json(p)


def side() -> dict:
    return load_json(SIDECAR)


def morph_doc() -> dict:
    return need(OUT3 / f"{COMPONENT}.json")


def element(doc: dict, kind: str, p: str, q: str, v) -> dict:
    hits = [e for e in doc["elements"] if (e["kind"], e["p"], e["q"], e["version"]) == (kind, p, q, v)]
    if len(hits) != 1:
        raise AssertionError(f"{len(hits)} elements ({kind}, {p}, {q}, {v})")
    return hits[0]


def lossy(args: list, cwd: Path | None = None, timeout: int = 3600):
    return run_holon(["lossy", *[str(a) for a in args]], cwd=cwd, timeout=timeout)


def tree(d: Path) -> dict[str, bytes]:
    d = Path(d)
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def law_blocks(text: str) -> dict[str, str]:
    """law NAME: blocks of a Bend file, each as its lines with trailing whitespace stripped (comments removed)."""
    lines = [re.sub(r"#.*$", "", ln).rstrip() for ln in text.splitlines()]
    out, cur = {}, None
    for ln in lines:
        m = re.match(r"^law\s+(\w+)\s*:\s*$", ln)
        if m:
            cur = m.group(1)
            out[cur] = [ln]
        elif cur is not None and ln.startswith((" ", "\t")) and ln.strip():
            out[cur].append(ln)
        elif ln.strip():
            cur = None
    return {k: "\n".join(v) for k, v in out.items()}


def no_escape(test: unittest.TestCase, text: str, what: str) -> None:
    for rx in ESCAPES:
        test.assertIsNone(rx.search(text), f"{what}: escape hatch {rx.pattern}")


def bend_ok(test: unittest.TestCase, proof: Path) -> str:
    code, out = run_bend([proof.name], cwd=proof.parent, timeout=900)
    test.assertEqual(code, 0, f"{proof}: {out[-3000:]}")
    test.assertIn(OK, out, f"{proof}: {out[-3000:]}")
    return out


def bend_verdict_ok(test: unittest.TestCase, proof: Path) -> None:
    bend = holon_module("holon.bend")
    test.assertTrue(bend.verdict_available(), "bend --verdict needs Lean (BEND_NOTES 1); it is never skipped")
    r = bend.check_verdict(proof)
    test.assertEqual(r.code, 0, f"{proof} --verdict: {r.out[-3000:]}")
    test.assertIn(OK, r.out, f"{proof} --verdict: {r.out[-3000:]}")


def generated_modules() -> list[Path]:
    return sorted({ROOT / "holon" / "rules" / "par_lossy.py"} | set((ROOT / "holon").rglob("*lossy*.py")))


# ---------------------------------------------------------------------------------------------- the prereg's inputs
class TestPreregInstruments(unittest.TestCase):
    """Construction checks of the instruments fixed at the prereg (they hold before and after the build)."""

    def test_sidecar_is_the_computation(self):
        """Construction (I25-R6): spec/M3/lib/par_lossy.json is tests_m3/_i25.py::par_lossy_doc over unchanged inputs:
        every input's sha256 matches, and recomputing gives the same document (the review at the prereg aside: it is
        recomputed over the records at build time by TestReview)."""
        s = side()
        for i in s["inputs"]:
            with self.subTest(input=i["path"]):
                self.assertEqual(file_sha256(ROOT / i["path"]), i["sha256"], f"{i['path']} changed since the prereg")
        now = L.par_lossy_doc(ROOT)
        drop = ("review_at_prereg",)
        a = {k: v for k, v in now.items() if k not in drop}
        b = {k: v for k, v in s.items() if k not in drop}
        a["metric"] = {k: v for k, v in a["metric"].items() if k != "uncovered_disagreements"}
        b["metric"] = {k: v for k, v in b["metric"].items() if k != "uncovered_disagreements"}
        self.assertEqual(canonical_json(a), canonical_json(b))
        self.assertEqual(s["core"]["laws"], L.CORE)
        self.assertEqual(s["core"]["canary"], L.CANARY)

    def test_core_statements_are_well_typed_open_laws(self):
        """Construction (rule L7): the three frozen core statements type-check under the pinned bend as open laws
        (bend reports exactly 3 TODOs and no other error). No proof is attempted here."""
        tmp = Path(tempfile.mkdtemp(prefix="i25_core_"))
        try:
            (tmp / "LAWS.bend").write_text("import Base\n\n" + "\n\n".join(x["bend"] for x in side()["core"]["laws"])
                                           + "\n")
            (tmp / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
            code, out = run_bend(["PROOF.bend"], cwd=tmp)
            self.assertNotEqual(code, 0)
            self.assertIn(FAIL, out)
            self.assertRegex(out, r"Error: 3 TODOs found", out[-2000:])
            self.assertNotIn("expected :", out, out[-2000:])
            self.assertEqual(sorted(law_blocks((tmp / "LAWS.bend").read_text())), sorted(CORE_NAMES))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_frozen_evidence_set_is_rule_x7s(self):
        """I25-R2: the frozen evidence set's atoms over header_length are exactly rule X7's 161 (E1 102: 70 inverse and
        32 common_decoder; E2 55; E6 4), so every element below is computed from the committed set."""
        self.assertTrue(L.frozen_atoms_agree(ROOT), "gen/M3/evidence.json's header_length atoms are not rule X7's")
        ev = load_json(ROOT / EVIDENCE_DOC)
        ats = [a for a in ev["atoms"] if a["model"] == COMPONENT]
        cnt: dict = {}
        for a in ats:
            k = a["level"] + ("/" + a["via"]["kind"] if a["level"] == "E1" else "")
            cnt[k] = cnt.get(k, 0) + 1
        self.assertEqual(cnt, {"E1/inverse": 70, "E1/common_decoder": 32, "E2": 55, "E6": 4})

    def test_d7_is_outside_todays_extraction(self):
        """I25-R3 (construction; L-G3): no adopted M3 document mentions Verify.sol, L1CrossDomainMessenger.sol or
        verifyMerkleProof, the Solidity extraction sidecars name Rollup.sol only, and the sidecar defers D7 to I36 with
        its four sites. After the build, no I25 output names those files either."""
        docs = load_json(ROOT / "spec" / "M3" / "lib" / "derive_extracted.json")["documents"]
        for d in docs:
            text = (ROOT / d).read_text()
            for k in L.D7_FILES:
                self.assertNotIn(k, text, f"{d} mentions {k}")
        for sc in ("extract_solidity.json", "extract_rollup.json"):
            self.assertEqual(load_json(ROOT / "spec" / "M2" / "lib" / sc)["sources"],
                             ["contracts/contracts/l1/rollup/Rollup.sol"])
        d7 = side()["deferred"]
        self.assertEqual([x["id"] for x in d7], ["D7"])
        self.assertEqual(d7[0]["adopted_documents_mentioning_it"], [])
        self.assertFalse(d7[0]["in_extraction"])
        self.assertEqual(len(d7[0]["sites"]), 4)
        self.assertIn("I36", d7[0]["instance"])
        if OUT3.exists():
            for rel, data in tree(OUT3).items():
                for k in L.D7_FILES:
                    self.assertNotIn(k.encode(), data, f"gen/M3/par_lossy/{rel} names {k}")

    def test_no_replay_record_is_over_a_component_edge(self):
        """Construction (L-G7): the refinement records rule L9 reads (holon.refinement.record_files: 15 at the prereg)
        name only the hand-written M0 document facts/morph_header.json (12) or the transitions document (3), never a
        linked codec document, so no disagreement in them can resolve to a component edge today."""
        files = L.record_files(ROOT)
        self.assertEqual([f.relative_to(ROOT).as_posix() for f in files],
                         [f.relative_to(ROOT).as_posix() for f in holon_module("holon.refinement").record_files(ROOT)])
        facts = [load_json(f).get("facts") for f in files]
        self.assertGreaterEqual(len(facts), 15)
        comp, diag, _ = L.component(ROOT)
        component_docs = {e.get("component") for e in diag["edges"]} - {None}
        self.assertEqual(component_docs, {"spec/M2/facts/morph_batch.go.extracted.json",
                                          "spec/M2/facts/morph_header.extracted.json"})
        self.assertEqual([f for f in facts if f in component_docs], [])

    def test_i25_adds_no_law_and_no_catalog(self):
        """I25-R1 (L-G1): PAR-lossy derives no law: no laws/M3 file is an I25 law (prefix L_par_lossy), no catalog of
        holon.rules has a producer whose name contains lossy, and catalog_version('M3') holds I24's PAR producers."""
        self.assertFalse([n for n in laws("M3") if n.startswith("L_par_lossy")])
        rules = holon_module("holon.rules")
        for v, cat in rules.CATALOGS.items():
            for rule, subs in cat.items():
                self.assertNotIn("lossy", rule.lower(), v)
                self.assertFalse([s for s in subs if "lossy" in s.lower()], f"{v}: {rule}")
        cv = rules.catalog_version("M3")
        # I24's PAR producers, the same objects (I28 adds PAR's sub-form init_chain, and only it, beside them: amended
        # at the I28 prereg, spec/M3/amendments.jsonl)
        base = rules.CATALOGS["holon-rules/1.1"]["PAR"]
        for sub, prod in base.items():
            self.assertIs(rules.CATALOGS[cv]["PAR"].get(sub), prod, sub)
        self.assertLessEqual(set(rules.CATALOGS[cv]["PAR"]) - set(base), {"init_chain"})


# ---------------------------------------------------------------------------------------------- Morph (the build)
class TestMorph(unittest.TestCase):
    """The Morph component header_length (gen/M3/par_lossy/header_length.json and its Bend files)."""

    def test_document_is_the_instrument(self):
        """Construction: every semantic key of the document is exactly what rules L1-L8 give (the sidecar's morph
        analysis, recomputed by the instrument); "inputs" are the codec document, its diagram and the evidence set
        with their current sha256, and no hand document (Q19)."""
        doc = morph_doc()
        want = side()["morph"]["analysis"]
        for k in SEMANTIC:
            with self.subTest(key=k):
                self.assertEqual(canonical_json(doc.get(k)), canonical_json(want[k]))
        self.assertEqual(doc["inputs"], [{"path": p, "sha256": file_sha256(ROOT / p)}
                                         for p in sorted([CODEC_DOC, DIAGRAM_DOC, EVIDENCE_DOC])])
        self.assertEqual(sorted(p.name for p in OUT3.glob("*.json")), [f"{COMPONENT}.json"])

    def test_fragment(self):
        """I25-P1: Def 4.4 over the 20 edges gives exactly 22 entries: enc_sol at version 0 lossy, dropping
        lastBlockNumber; enc_sol at 1 and 2, BatchHeaderV0_Bytes at 0, BatchHeaderV1_Bytes at 1 and the patch at 2
        invertible; the 14 BatchHeaderBytes getters lossy (each a projection of the byte string); load_sol unmodelled;
        HASH.keccak256 cf."""
        fr = morph_doc()["fragment"]
        self.assertEqual(len(fr), 22)
        by = {(x["edge"], x["version"]): x for x in fr}
        self.assertEqual(by[("CODEC.enc_sol", 0)]["class"], "lossy")
        self.assertEqual(by[("CODEC.enc_sol", 0)]["dropped"], ["lastBlockNumber"])
        for e, v in (("CODEC.enc_sol", 1), ("CODEC.enc_sol", 2), ("CODEC.BatchHeaderV0_Bytes", 0),
                     ("CODEC.BatchHeaderV1_Bytes", 1), (f"CODEC.{PATCH}", 2)):
            self.assertEqual((by[(e, v)]["class"], by[(e, v)]["dropped"]), ("invertible", []), (e, v))
        getters = sorted(e for (e, v), x in by.items() if e.startswith("CODEC.BatchHeaderBytes_"))
        self.assertEqual(len(getters), 14)
        self.assertEqual({by[(g, None)]["class"] for g in getters}, {"lossy"})
        self.assertEqual(by[("CODEC.load_sol", None)]["class"], "unmodelled")
        self.assertEqual(by[("HASH.keccak256", None)]["class"], "cf")

    def test_elements(self):
        """I25-P2: 79 evidenced lossy elements: 70 round_trip (one per inverse atom, each covered by its I24 round trip),
        3 observed (BatchHeaderV0_Bytes/enc_sol at 0 with 10 common-decoder atoms, BatchHeaderV1_Bytes/enc_sol at 1 and
        the patch/enc_sol at 2 with 11 each), 6 constant_read (BatchHeaderBytes_Version on the three Go encoders: 0x00,
        0x01, 0x02; BatchHeaderBytes_SequencerSetVerifyHash on enc_sol at 0, 1, 2: 32 zero bytes), no partial_read and no
        other; 3 E2 atoms excluded for no common version (the patch with BlobVersionedHash, BatchHeaderV0_Bytes and
        BatchHeaderV1_Bytes with BlobHashesHash); 4 E6 atoms, 2 with a PAR-weak law."""
        doc = morph_doc()
        cnt = {k: sum(1 for e in doc["elements"] if e["kind"] == k) for k in L.KINDS}
        self.assertEqual(cnt, {"round_trip": 70, "observed": 3, "constant_read": 6, "partial_read": 0, "other": 0})
        rt = [e for e in doc["elements"] if e["kind"] == "round_trip"]
        self.assertTrue(all(e["covered"] and len(e["laws"]) == 1 and e["laws"][0].startswith("L_par_rt_") for e in rt))
        obs = {(e["p"], e["q"], e["version"]): len(e["atoms"]) for e in doc["elements"] if e["kind"] == "observed"}
        self.assertEqual(obs, {("CODEC.BatchHeaderV0_Bytes", "CODEC.enc_sol", 0): 10,
                               ("CODEC.BatchHeaderV1_Bytes", "CODEC.enc_sol", 1): 11,
                               (f"CODEC.{PATCH}", "CODEC.enc_sol", 2): 11})
        reads = {(e["p"], e["q"], e["version"]): e["bytes"] for e in doc["elements"] if e["kind"] == "constant_read"}
        z = "0x" + "00" * 32
        self.assertEqual(reads, {("CODEC.BatchHeaderV0_Bytes", "CODEC.BatchHeaderBytes_Version", 0): "0x00",
                                 ("CODEC.BatchHeaderV1_Bytes", "CODEC.BatchHeaderBytes_Version", 1): "0x01",
                                 (f"CODEC.{PATCH}", "CODEC.BatchHeaderBytes_Version", 2): "0x02",
                                 ("CODEC.enc_sol", "CODEC.BatchHeaderBytes_SequencerSetVerifyHash", 0): z,
                                 ("CODEC.enc_sol", "CODEC.BatchHeaderBytes_SequencerSetVerifyHash", 1): z,
                                 ("CODEC.enc_sol", "CODEC.BatchHeaderBytes_SequencerSetVerifyHash", 2): z})
        self.assertEqual(sorted((x["p"], x["q"]) for x in doc["excluded"]),
                         sorted([(f"CODEC.{PATCH}", "CODEC.BatchHeaderBytes_BlobVersionedHash"),
                                 ("CODEC.BatchHeaderV0_Bytes", "CODEC.BatchHeaderBytes_BlobHashesHash"),
                                 ("CODEC.BatchHeaderV1_Bytes", "CODEC.BatchHeaderBytes_BlobHashesHash")]))
        self.assertEqual(doc["weak"], {"atoms": 4, "with_law": 2})
        committed = laws("M3")
        for e in doc["elements"]:
            for lid in e["laws"] + [x["law"] for x in e.get("pushes", [])]:
                self.assertIn(lid, committed, f"{lid} is no committed M3 law")

    def test_push_verdicts(self):
        """I25-P3: the 6 push laws: the 3 pinned cross-component laws are pushed (each observed pair's basis law); the 3
        full ones are not, each failing first at position 185, kind unobserved_field: the Go encoder's
        SequencerSetVerifyHash byte 0 against the Solidity constant 0 (the families of 10, 11 and 11 decoders leave
        positions 0 and 185..216 unread; position 0 is the version byte both sides fix). No family decoder is blind:
        each accepts the images' length (249 at version 0, 257 at 1 and 2) under the version's tag."""
        doc = morph_doc()
        pushes = {x["law"]: x for e in doc["elements"] if e["kind"] == "observed" for x in e["pushes"]}
        self.assertEqual(sorted(pushes), sorted(CC_FULL + CC_PINNED))
        for lid in CC_PINNED:
            self.assertEqual((pushes[lid]["pushed"], pushes[lid]["collision"]), (True, None), lid)
        for lid in CC_FULL:
            c = pushes[lid]["collision"]
            self.assertFalse(pushes[lid]["pushed"], lid)
            self.assertEqual((c["position"], c["kind"], c["q"]), (185, "unobserved_field", ["const", 0]), lid)
            self.assertEqual(c["p"][0], "field")
            self.assertEqual((c["p"][1].rsplit(".", 1)[-1], c["p"][2]), ("SequencerSetVerifyHash", 0), lid)
        for e in doc["elements"]:
            if e["kind"] == "observed":
                self.assertTrue(e["covered"])
                self.assertEqual(e["blind"], [])
                self.assertEqual(len(e["laws"]), 1)
                self.assertTrue(e["laws"][0].endswith("_pinned"))

    def test_static_verdicts_agree_with_the_kernel(self):
        """I25-R5 (construction): rule L4's verdicts agree with I24's committed M3 records: every pushed law is PROVED and
        every law that is not pushed is REFUTED, with a witness that satisfies the law's premises."""
        doc = morph_doc()
        recs = records("M3")
        pushes = [x for e in doc["elements"] for x in e.get("pushes", [])]
        self.assertEqual(len(pushes), 6, "the six cross-component laws of the three observed pairs")
        for x in pushes:
            with self.subTest(law=x["law"]):
                self.assertEqual(recs[x["law"]]["status"], "PROVED" if x["pushed"] else "REFUTED")

    def test_collision_certificates_check(self):
        """I25-P4: three collision certificates, one per full cross-component law, at the ones fill under its premises,
        each stating obs_<d> for the 10, 11 and 11 decoders of its family and differ; bend accepts each (ALL PROOFS
        CHECK, every law present, no escape hatch)."""
        doc = morph_doc()
        self.assertEqual([c["law"] for c in doc["collisions"]], CC_FULL)
        self.assertEqual(doc["uncertified"], [])
        self.assertEqual({c["kind"] for c in doc["collisions"]}, {"cross"})
        self.assertEqual([len(c["laws"]) - 1 for c in doc["collisions"]],
                         [11 if c["law"].endswith(("_v1", "_v2")) else 10 for c in doc["collisions"]])
        self.assertEqual(sorted(p.name for p in (OUT3 / "collisions").iterdir()), CC_FULL)
        for c in doc["collisions"]:
            with self.subTest(law=c["law"]):
                d = OUT3 / c["dir"]
                lt, pt = (d / "LAWS.bend").read_text(), (d / "PROOF.bend").read_text()
                self.assertEqual(sorted(law_blocks(lt)), sorted(c["laws"]))
                self.assertEqual(law_blocks(pt), {}, "a proof file declares no law")
                self.assertRegex(pt, r"(?m)^import \./LAWS\.bend as \w+$")
                no_escape(self, lt + pt, c["law"])
                bend_ok(self, d / "PROOF.bend")

    def test_hash_candidates(self):
        """I25-P7: exactly one HASH candidate: HASH.keccak256 with (enc_sol, load_sol), sinks Rollup.sol:357 and
        Rollup.sol:849, unevidenced (no atom relates them; L-G2); none is counted in coverage."""
        doc = morph_doc()
        self.assertEqual(doc["hash_candidates"], [
            {"hash": "HASH.keccak256", "pair": ["CODEC.enc_sol", "CODEC.load_sol"],
             "sinks": ["contracts/contracts/l1/rollup/Rollup.sol:357", "contracts/contracts/l1/rollup/Rollup.sol:849"],
             "evidenced": False, "atoms": []}])

    def test_coverage(self):
        """I25-P6 (the component): coverage 73 of 79 (rate 73/79), by kind round_trip 70/70, observed 3/3,
        constant_read 0/6; the uncovered elements are exactly the six constant reads, reason no_rule."""
        cov = morph_doc()["coverage"]
        self.assertEqual((cov["elements"], cov["covered"], cov["rate"]), (79, 73, 73 / 79))
        self.assertEqual(cov["by_kind"], {"round_trip": {"elements": 70, "covered": 70},
                                          "observed": {"elements": 3, "covered": 3},
                                          "constant_read": {"elements": 6, "covered": 0},
                                          "partial_read": {"elements": 0, "covered": 0},
                                          "other": {"elements": 0, "covered": 0}})
        self.assertEqual([(u["kind"], u["reason"]) for u in cov["uncovered"]], [("constant_read", "no_rule")] * 6)

    def test_cli_check_and_determinism(self):
        """Construction: holon lossy --milestone M3 --check exits 0 on the committed tree (nothing differs); in a copy two
        runs write byte-identical trees: <role>.json, core/LAWS.bend, core/PROOF.bend and the three collision
        directories, and the empty review."""
        p = lossy(["--milestone", "M3", "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        repo = copy_repo()
        try:
            outs = []
            for i in (1, 2):
                out = repo.parent / f"out{i}"
                rv = repo.parent / f"review{i}.jsonl"
                q = lossy(["--milestone", "M3", "--root", repo, "--out", out, "--review", rv], cwd=repo)
                self.assertEqual(q.returncode, 0, q.stdout[-2000:] + q.stderr[-2000:])
                outs.append((tree(out), rv.read_bytes()))
            self.assertEqual(outs[0], outs[1])
            want = {f"{COMPONENT}.json", "core/LAWS.bend", "core/PROOF.bend"} | {
                f"collisions/{lid}/{f}" for lid in CC_FULL for f in ("LAWS.bend", "PROOF.bend")}
            self.assertEqual(set(outs[0][0]), want)
            self.assertEqual(outs[0][0], tree(OUT3), "the committed gen/M3/par_lossy differs from a fresh run")
            self.assertEqual(outs[0][1], b"")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_stale_inputs_are_refused(self):
        """Construction (rule L0): a frozen evidence set that is not what holon evidence writes now is refused (exit 2),
        and nothing under gen/M3/par_lossy is written or removed."""
        need(OUT3 / f"{COMPONENT}.json")
        repo = copy_repo()
        try:
            ev = repo / EVIDENCE_DOC
            doc = load_json(ev)
            doc["atoms"] = doc["atoms"][1:]
            ev.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
            before = tree(repo / "gen" / "M3" / "par_lossy")
            review = (repo / "spec" / "M3" / "evidence_review.jsonl").read_bytes()
            p = lossy(["--milestone", "M3", "--root", repo], cwd=repo)
            self.assertEqual(p.returncode, 2, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertIn("evidence.json", p.stdout + p.stderr, "the refusal names the stale input")
            self.assertEqual(tree(repo / "gen" / "M3" / "par_lossy"), before)
            self.assertEqual((repo / "spec" / "M3" / "evidence_review.jsonl").read_bytes(), review)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_no_hand_document_is_read(self):
        """Construction (Q19): with facts/ and spec/M1/facts removed from a copy, holon lossy --milestone M3 writes the
        same files."""
        need(OUT3 / f"{COMPONENT}.json")
        repo = copy_repo()
        try:
            shutil.rmtree(repo / "facts")
            shutil.rmtree(repo / "spec" / "M1" / "facts")
            out, rv = repo.parent / "out", repo.parent / "review.jsonl"
            p = lossy(["--milestone", "M3", "--root", repo, "--out", out, "--review", rv], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertEqual(tree(out), tree(OUT3))
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_generic_code(self):
        """Construction (AGENTS rules 2 and 4): holon/rules/par_lossy.py and every holon/ module named *lossy* name no
        identifier of the Morph component or of the linked fixtures (I24's target_names), no law id and no target source
        file."""
        names = X.target_names(ROOT)
        compound = {n for n in names if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}
        quoted = {n for n in names if len(n) >= 3} - X.GENERIC_WORDS
        mods = generated_modules()
        self.assertTrue((ROOT / "holon" / "rules" / "par_lossy.py").exists(), "holon/rules/par_lossy.py is missing")
        for f in mods:
            with self.subTest(module=f.relative_to(ROOT).as_posix()):
                text = f.read_text(encoding="utf-8")
                self.assertEqual(sorted(n for n in compound
                                        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text)), [])
                self.assertEqual(sorted(n for n in quoted if re.search(rf"[\"']{re.escape(n)}[\"']", text)), [])
                self.assertNotRegex(text, r"L_par_\w*(v[0-9]|pinned)\b")
                self.assertNotRegex(text, r"(?i)\bmorph\b|Rollup\.sol|Verify\.sol|CrossDomainMessenger",
                                    "no target name or source file")


# ---------------------------------------------------------------------------------------------- the core law
class TestCore(unittest.TestCase):
    def test_inj_push_is_proved(self):
        """I25-P5: gen/M3/par_lossy/core/LAWS.bend holds exactly the sidecar's three statements (core_inj_push,
        core_inj_pull, core_cf_succ), in that order and nothing else; PROOF.bend imports ./LAWS.bend, declares no law and
        has no escape hatch; bend and bend --verdict accept it (ALL PROOFS CHECK)."""
        d = OUT3 / "core"
        lt = (d / "LAWS.bend").read_text() if (d / "LAWS.bend").exists() else ""
        self.assertTrue(lt, "gen/M3/par_lossy/core/LAWS.bend is missing (I25 builds it)")
        blocks = law_blocks(lt)
        want = {x["name"]: "\n".join(ln.rstrip() for ln in x["bend"].splitlines()) for x in side()["core"]["laws"]}
        self.assertEqual(list(blocks), CORE_NAMES)
        self.assertEqual(blocks, want)
        pt = (d / "PROOF.bend").read_text()
        self.assertRegex(pt, r"(?m)^import \./LAWS\.bend as \w+$")
        self.assertEqual(law_blocks(pt), {})
        no_escape(self, lt + pt, "core")
        bend_ok(self, d / "PROOF.bend")
        bend_verdict_ok(self, d / "PROOF.bend")

    def test_canary_is_rejected(self):
        """I25-P5 (canary): the generated core files with core_inj_push's statement replaced by the sidecar's canary
        (the same statement without its cf premise: false by Prop 6.11) and the cf binder (the seventh, in statement
        order) dropped from its def do not check. Everything else of the generated PROOF.bend is kept verbatim."""
        d = OUT3 / "core"
        self.assertTrue((d / "PROOF.bend").exists(), "gen/M3/par_lossy/core/PROOF.bend is missing (I25 builds it)")
        pt, lt = (d / "PROOF.bend").read_text(), (d / "LAWS.bend").read_text()
        m = re.search(r"(?m)^def (\w+)\.core_inj_push\(", pt)
        self.assertIsNotNone(m, "no def <alias>.core_inj_push(..) in the generated PROOF.bend")
        depth, i, cuts = 1, m.end(), [m.end()]
        while depth:
            self.assertLess(i, len(pt), "unbalanced parameter list")
            ch = pt[i]
            depth += {"(": 1, "{": 1, "[": 1, ")": -1, "}": -1, "]": -1}.get(ch, 0)
            if ch == "," and depth == 1:
                cuts.append(i + 1)
            i += 1
        ps = [pt[x:y].strip().rstrip(",").strip() for x, y in zip(cuts, cuts[1:] + [i])]
        ps[-1] = ps[-1][:-1].strip() if ps[-1].endswith(")") else ps[-1]
        self.assertGreaterEqual(len(ps), 8, f"core_inj_push binds X, A, B, h, f, g, cf, e: {ps}")
        del ps[6]
        canary_pt = pt[:m.end()] + ", ".join(ps) + ")" + pt[i:]
        canary = side()["core"]["canary"]["bend"].replace("law canary_inj_push_without_cf:", "law core_inj_push:")
        blocks = law_blocks(lt)
        self.assertIn("core_inj_push", blocks)
        laws_text = "import Base\n\n" + "\n\n".join(canary if n == "core_inj_push" else blocks[n] for n in blocks) + "\n"
        tmp = Path(tempfile.mkdtemp(prefix="i25_canary_"))
        try:
            (tmp / "LAWS.bend").write_text(laws_text)
            (tmp / "PROOF.bend").write_text(canary_pt)
            code, out = run_bend(["PROOF.bend"], cwd=tmp)
            self.assertNotEqual(code, 0, out[-2000:])
            self.assertIn(FAIL, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- the evidence review
def _plant(dirp: Path) -> None:
    """Four planted refinement records (rule L9): a covered edge, a hand-document edge, a resolved edge of no covered
    element and a step record's action."""
    (dirp / "historical").mkdir(parents=True)
    base = {"record_version": "holon-refinement/0.1", "kind": "codec", "compared": 1, "agree": 0, "disagreements": 1,
            "fixes": [], "milestone": "M2"}
    (dirp / "a_covered.json").write_text(json.dumps(dict(base, facts="spec/M2/facts/morph_batch.go.extracted.json",
                                                         diagram_edge="CODEC.BatchHeaderV0_Bytes", edge="x",
                                                         disagreement_ids=["planted-1"]), indent=2) + "\n")
    (dirp / "b_hand.json").write_text(json.dumps(dict(base, facts="facts/morph_header.json",
                                                      diagram_edge="CODEC.enc_go_v0", edge="enc_go_v0",
                                                      disagreement_ids=["planted-2"]), indent=2) + "\n")
    (dirp / "historical" / "c_loader.json").write_text(json.dumps(dict(
        base, kind="historical", facts="spec/M2/facts/morph_header.extracted.json", diagram_edge="CODEC.load_sol",
        edge="load_sol", disagreement_ids=["planted-3"]), indent=2) + "\n")
    (dirp / "d_step.json").write_text(json.dumps({"kind": "extracted", "facts": "spec/M2/facts/morph_rollup.extracted.json",
                                                  "disagreements": [{"id": "planted-4", "action": "commitBatch",
                                                                     "class": "unexplained", "links": {}}],
                                                  "unexplained": 1}, indent=2) + "\n")


class TestReview(unittest.TestCase):
    def test_morph_review_is_empty(self):
        """I25-P8: spec/M3/evidence_review.jsonl exists and is empty (0 bytes): rule L9 over the refinement records
        committed now (15 at the prereg: 7 under results/M2/refinement/, 8 under historical/) gives no entry, since they
        list no disagreement; the instrument agrees over the records committed at build time."""
        self.assertTrue(REVIEW3.exists(), "spec/M3/evidence_review.jsonl is missing (I25 builds it)")
        entries, rels, n = L.review_now(ROOT)
        self.assertEqual(REVIEW3.read_text(), L.review_text(entries))
        self.assertEqual(REVIEW3.read_bytes(), b"")
        self.assertEqual(n, 0)
        self.assertTrue(set(side()["review_at_prereg"]["records"]) <= set(rels))

    def test_planted_disagreements_open_reviews(self):
        """Construction (rule L9): over four planted records, holon lossy --milestone M3 --records DIR writes exactly the
        entries the instrument gives: none for the disagreement on BatchHeaderV0_Bytes (an endpoint of covered
        elements), unresolved_edge for the hand document's enc_go_v0 and for the step record's commitBatch,
        no_covered_element for load_sol (resolved, the endpoint of no element)."""
        need(OUT3 / f"{COMPONENT}.json")
        repo = copy_repo()
        try:
            recs = repo / "planted_records"
            _plant(recs)
            out, rv = repo.parent / "out", repo.parent / "review.jsonl"
            p = lossy(["--milestone", "M3", "--root", repo, "--out", out, "--review", rv, "--records", recs], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            comp, diag, ats = L.component(repo)
            an = L.analyse(comp, diag, ats, "M3")
            files = L.record_files(repo, Path("planted_records"))
            want = L.review(repo, files, {COMPONENT: (an, diag)}, load_json(repo / EVIDENCE_DOC)["evidence_sha256"])
            self.assertEqual(rv.read_text(), L.review_text(want))
            self.assertEqual(sorted((e["disagreement"], e["reason"]) for e in want),
                             [("planted-2", "unresolved_edge"), ("planted-3", "no_covered_element"),
                              ("planted-4", "unresolved_edge")])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- the metric
class TestMetric(unittest.TestCase):
    def test_metrics_json_reports_the_coverage(self):
        """I25-P6: results/M3/metrics.json "evidenced_pair_coverage" is the sidecar's metric (79 elements, 73 covered,
        rate 73/79, by kind, 6 uncovered, 3 excluded, weak 4/2, 1 HASH candidate, models [header_length]) with the evidence
        set's current evidence_sha256, the Prop 6.11 sentence and uncovered_disagreements equal to the review's entries
        (0)."""
        m = need(METRICS3)
        self.assertIn("evidenced_pair_coverage", m)
        got = m["evidenced_pair_coverage"]
        want = dict(side()["metric"])
        want["evidence"] = {"path": EVIDENCE_DOC, "evidence_sha256": load_json(ROOT / EVIDENCE_DOC)["evidence_sha256"]}
        want["uncovered_disagreements"] = len(REVIEW3.read_text().splitlines()) if REVIEW3.exists() else None
        self.assertEqual(got, want)
        self.assertEqual((got["elements"], got["covered"], got["uncovered_disagreements"]), (79, 73, 0))
        self.assertEqual(got["relative_to"], L.RELATIVE_TO)

    def test_metrics_regenerate_and_m2_is_untouched(self):
        """Construction and I25-R4 (part): holon metrics --milestone M3 reproduces results/M3/metrics.json byte for byte
        in a copy; results/M2/metrics.json carries no evidenced_pair_coverage."""
        self.assertNotIn("evidenced_pair_coverage", load_json(ROOT / "results" / "M2" / "metrics.json"))
        need(METRICS3)
        repo = copy_repo()
        try:
            p = run_holon(["metrics", "--milestone", "M3", "--root", str(repo)], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertEqual((repo / "results" / "M3" / "metrics.json").read_bytes(), METRICS3.read_bytes())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- planted fixtures
class TestFixtures(unittest.TestCase):
    """T251 (tests_m3/fixtures/par_lossy/: I24's linked fixture with the Go constant at position 6 set to 0, so its
    version-1 pair becomes injective) and T252 (I24's linked fixture itself), each derived under holon-rules/1.1 (I24's
    PAR), run by holon run (rule X9) and analysed by holon lossy, in a copy."""

    FIX = {"T251": L.FIX_INJ, "T252": L.FIX_NONINJ}

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        tmp = cls.repo.parent
        cls.logs, cls.codes, cls.docs, cls.recs, cls.outs = {}, {}, {}, {}, {}
        probe = run_holon(["lossy", "--help"], cwd=cls.repo)
        cls.probe = (probe.returncode, probe.stdout[-1500:] + probe.stderr[-1500:])
        if probe.returncode != 0:
            return
        for ms, fx in cls.FIX.items():
            codec = f"gen/{ms}/codec/{fx['role']}.json"
            steps = [["codecs", "--milestone", ms, "--root", str(cls.repo), "--adoption", fx["adoption"], "--link",
                      fx["link"]],
                     ["derive", "--milestone", ms, "--catalog", "holon-rules/1.1", "--root", str(cls.repo), "--out",
                      str(cls.repo / "laws" / ms), "--codec", codec],
                     ["run", "--milestone", ms, "--out", str(tmp / f"results_{ms}"), "--gen-dir", str(tmp / f"gen_{ms}")],
                     ["lossy", "--milestone", ms, "--root", str(cls.repo), "--codec", codec, "--out",
                      str(tmp / f"lossy_{ms}"), "--gen-dir", str(tmp / f"gen_{ms}")]]
            log, code = "", 0
            for s in steps:
                p = run_holon(s, cwd=cls.repo, timeout=3600)
                log += f"$ holon {' '.join(s)}\n{p.stdout[-2000:]}{p.stderr[-2000:]}\n"
                code = p.returncode
                if code != 0:
                    break
            cls.logs[ms], cls.codes[ms] = log, code
            cls.outs[ms] = tmp / f"lossy_{ms}"
            f = cls.outs[ms] / f"{fx['role']}.json"
            cls.docs[ms] = load_json(f) if f.exists() else None
            cls.recs[ms] = {p.stem: load_json(p) for p in sorted((tmp / f"results_{ms}").glob("L*.json"))}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def _ready(self, ms: str) -> dict:
        self.assertEqual(self.probe[0], 0, f"holon lossy is missing (I25 builds it): {self.probe[1]}")
        self.assertEqual(self.codes.get(ms), 0, self.logs.get(ms, "")[-4000:])
        self.assertIsNotNone(self.docs[ms], f"no {ms} document")
        return self.docs[ms]

    def _pushes(self, doc: dict) -> dict:
        return {x["law"]: x for e in doc["elements"] if e["kind"] == "observed" for x in e["pushes"]}

    def _certificates(self, ms: str, doc: dict) -> None:
        self.assertEqual(sorted(p.name for p in (self.outs[ms] / "collisions").iterdir()),
                         [c["law"] for c in doc["collisions"]])
        for c in doc["collisions"]:
            with self.subTest(fixture=ms, law=c["law"]):
                d = self.outs[ms] / c["dir"]
                lt, pt = (d / "LAWS.bend").read_text(), (d / "PROOF.bend").read_text()
                self.assertEqual(sorted(law_blocks(lt)), sorted(c["laws"]))
                self.assertEqual(law_blocks(pt), {}, "a proof file declares no law")
                no_escape(self, lt + pt, c["law"])
                bend_ok(self, d / "PROOF.bend")

    def test_fixture_documents_are_the_instruments(self):
        """Construction: each fixture's document is exactly rules L1-L8 over it (the sidecar's fixture analysis)."""
        for ms in self.FIX:
            doc = self._ready(ms)
            want = side()["fixtures"][ms]["analysis"]
            for k in SEMANTIC:
                with self.subTest(fixture=ms, key=k):
                    self.assertEqual(canonical_json(doc.get(k)), canonical_json(want[k]))

    def test_injective_fixture(self):
        """I25-P9 (a lossy fixture with an injective post-map gives a pushed law PROVED): on T251 the pairs at versions 0
        and 1 are pushed by their pinned laws (families {A, B} and {A, B, D}, none blind, read every position where the
        images can differ once C is pinned) and holon run decides both PROVED, L_par_cc_RecV1_Bytes_enc_x_v1_pinned for
        the first time (I24's par_linked has 255 at position 6 and refutes it). The pair at version 2 is not pushed:
        getter B rejects the 9-byte version-2 images, so it is blind and positions 3..4 are unobserved (collision at 3,
        unobserved_field, RecV0.B byte 0 against b byte 0), for the pinned and the full law alike; holon run still decides
        L_par_cc_Cache_makeV2_enc_x_v2_pinned PROVED (a law that holds beyond the evidence: not pushed and PROVED). The
        full laws at versions 0 and 1 fail the push at position 5 (unobserved field C byte 0); all three full laws are
        REFUTED. Coverage 22 of 33 (observed 2 of 3); four certificates check: cross for the full laws at 0 and 1,
        same_side (side p) for both laws at version 2."""
        doc = self._ready("T251")
        pu = self._pushes(doc)
        recs = self.recs["T251"]
        v0, v1, v2 = ("L_par_cc_RecV0_Bytes_enc_x_v0", "L_par_cc_RecV1_Bytes_enc_x_v1", "L_par_cc_Cache_makeV2_enc_x_v2")
        self.assertEqual(sorted(pu), sorted([v0, v1, v2, v0 + "_pinned", v1 + "_pinned", v2 + "_pinned"]))
        for lid in (v0 + "_pinned", v1 + "_pinned"):
            self.assertEqual((pu[lid]["pushed"], recs[lid]["status"]), (True, "PROVED"), lid)
        for lid in (v0, v1):
            c = pu[lid]["collision"]
            self.assertFalse(pu[lid]["pushed"], lid)
            self.assertEqual((c["position"], c["kind"]), (5, "unobserved_field"), lid)
        for lid in (v2, v2 + "_pinned"):
            c = pu[lid]["collision"]
            self.assertFalse(pu[lid]["pushed"], lid)
            self.assertEqual((c["position"], c["kind"], c["p"], c["q"]),
                             (3, "unobserved_field", ["field", "RecV0.B", 0], ["field", "b", 0]), lid)
        self.assertEqual({lid: recs[lid]["status"] for lid in (v0, v1, v2, v2 + "_pinned")},
                         {v0: "REFUTED", v1: "REFUTED", v2: "REFUTED", v2 + "_pinned": "PROVED"})
        obs = {(e["p"], e["version"]): e for e in doc["elements"] if e["kind"] == "observed"}
        self.assertEqual({k: (e["blind"], e["covered"], e["reason"]) for k, e in obs.items()},
                         {("CODEC.RecV0_Bytes", 0): ([], True, None), ("CODEC.RecV1_Bytes", 1): ([], True, None),
                          ("CODEC.Cache_makeV2", 2): (["CODEC.HdrBytes_B"], False, "non_injective")})
        cov = doc["coverage"]
        self.assertEqual((cov["elements"], cov["covered"]), (33, 22))
        self.assertEqual(cov["by_kind"]["observed"], {"elements": 3, "covered": 2})
        self.assertEqual({c["law"]: (c["kind"], c.get("side")) for c in doc["collisions"]},
                         {v0: ("cross", None), v1: ("cross", None), v2: ("same_side", "p"),
                          v2 + "_pinned": ("same_side", "p")})
        self.assertEqual(doc["uncertified"], [])
        self._certificates("T251", doc)

    def test_non_injective_fixture(self):
        """I25-P10 (a non-injective fixture yields no basis law and coverage below 100%): on T252 the observed pairs at
        versions 1 and 2 have no basis law. At version 1 the pinned law fails the push at position 6 (constants_differ:
        the Go constant 255 against the Solidity constant 0) and the full law at 5; at version 2 getter B is blind (it
        rejects the 9-byte images) and both laws fail at position 3 (unobserved_field). The pair at version 0 is pushed by
        its pinned law. Coverage 21 of 33 (observed 1 of 3), below 1; five certificates check (same_side for the two
        version-2 laws, cross for the other three). The kernel statuses are I24's (tests_m3/test_par_outcomes.py
        LINKED_STATUS: the v0 pinned law PROVED, the other five REFUTED), so on T252 every pushed law is PROVED and
        every law that is not pushed REFUTED."""
        doc = self._ready("T252")
        pu = self._pushes(doc)
        recs = self.recs["T252"]
        c = pu["L_par_cc_RecV1_Bytes_enc_x_v1_pinned"]["collision"]
        self.assertFalse(pu["L_par_cc_RecV1_Bytes_enc_x_v1_pinned"]["pushed"])
        self.assertEqual((c["position"], c["kind"], c["p"], c["q"]), (6, "constants_differ", ["const", 255], ["const", 0]))
        for lid in ("L_par_cc_Cache_makeV2_enc_x_v2", "L_par_cc_Cache_makeV2_enc_x_v2_pinned"):
            c = pu[lid]["collision"]
            self.assertFalse(pu[lid]["pushed"], lid)
            self.assertEqual((c["position"], c["kind"]), (3, "unobserved_field"), lid)
        self.assertTrue(pu["L_par_cc_RecV0_Bytes_enc_x_v0_pinned"]["pushed"])
        obs = {(e["p"], e["version"]): e for e in doc["elements"] if e["kind"] == "observed"}
        self.assertEqual({k: (e["blind"], e["covered"], e["reason"]) for k, e in obs.items()},
                         {("CODEC.RecV0_Bytes", 0): ([], True, None), ("CODEC.RecV1_Bytes", 1): ([], False, "non_injective"),
                          ("CODEC.Cache_makeV2", 2): (["CODEC.HdrBytes_B"], False, "non_injective")})
        cov = doc["coverage"]
        self.assertEqual((cov["elements"], cov["covered"]), (33, 21))
        self.assertLess(cov["rate"], 1)
        self.assertEqual(sorted((c["law"], c["kind"]) for c in doc["collisions"]),
                         [("L_par_cc_Cache_makeV2_enc_x_v2", "same_side"),
                          ("L_par_cc_Cache_makeV2_enc_x_v2_pinned", "same_side"),
                          ("L_par_cc_RecV0_Bytes_enc_x_v0", "cross"), ("L_par_cc_RecV1_Bytes_enc_x_v1", "cross"),
                          ("L_par_cc_RecV1_Bytes_enc_x_v1_pinned", "cross")])
        self.assertEqual(len(pu), 6)
        for lid, x in pu.items():
            self.assertEqual(recs[lid]["status"], "PROVED" if x["pushed"] else "REFUTED", lid)
        self._certificates("T252", doc)


# ---------------------------------------------------------------------------------------------- gate and regressions
class TestGateAndRegressions(unittest.TestCase):
    def test_partial_gate_m3_passes(self):
        """I25-R4 (part): holon gate --milestone M3 --checks G2,G3,G5,G9,G11,GEVID passes on a copy of the tree."""
        need(OUT3 / f"{COMPONENT}.json")
        repo = copy_repo()
        try:
            rep = repo.parent / "gate_report_i25.json"
            p = run_holon(["gate", "--milestone", "M3", "--root", str(repo), "--report", str(rep), "--checks",
                           "G2,G3,G5,G9,G11,GEVID"], cwd=repo, timeout=3600)
            self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_i25_outcome_commits_touch_no_frozen_or_earlier_output(self):
        """I25-R1, R2 and R4 (part): every commit that changes an I25 outcome path (gen/M3/par_lossy/,
        spec/M3/evidence_review.jsonl) changes no file under laws/, gen/M0-M3's codec, diagram and evidence set,
        results/M0-M2, gen/M0-M2 or replay/. Needs the real checkout's history: a missing .git is a failure, never a
        skip."""
        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        commits = git("log", "--format=%H", "--", "gen/M3/par_lossy", "spec/M3/evidence_review.jsonl").split()
        self.assertTrue(commits, "no commit writes an I25 outcome path")
        never = ("laws/", "gen/M3/codec/", "gen/M3/diagram/", "gen/M3/evidence.json", "results/M0/", "results/M1/",
                 "results/M2/", "gen/M0/", "gen/M1/", "gen/M2/", "replay/")
        for c in commits:
            touched = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c).split()
            self.assertEqual([f for f in touched if f.startswith(never)], [], c)
