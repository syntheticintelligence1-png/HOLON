"""I67 (= I38a): Go codecs at loop granularity, and O4 at the real blob size (BUILD_PLAN row I67 and I38; whitepaper §5.1
PAR including definedness and PAR-totality, A2, §11.3 O4, Appendix A F3). This docstring is the contract.

Scope. I18 localized O4 in M2: morph-l2/common/batch.RetrieveBlobBytes formats data[i*32] in its error branch, where
data has 4096 * 31 = 126976 bytes, so a blob whose field element i >= 3968 has a non-zero high-order byte panics, while
its clone morph-l2/common/blob.RetrieveBlobBytes formats blob[i*32] and is defined everywhere. No law states it: the I18
frontend summarizes a loop and never enumerates its body, and M3's rule PAR derives only over the linked codec layer
(I24), whose components are Solidity-Go link roles. I67 adds the frontend's loop bodies (Y1, Y2), Go-op components over
interface carriers (Y3-Y5), a structural model that decides their laws at the real size (Y6-Y8) and the replay of their
witnesses on the real code (Y9, Y10). It changes no rule of PAR, no rule catalog and no existing law. I38's compression
half (HypZ, HypZ_len) and its predictions O5, O6, O28 and D3 stay with I38.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i67.py and its Go file tests_m3/fixtures/go_loop/holon_i67_instrument.go.txt
(the real outcomes of the two clones on probe blobs; the components and laws of Y3 and Y5, from the sidecar and the Go
document; the concretization of Y9), written without holon/.

Y1 Frontend 0.2. holon.frontends.go accepts config_version holon-go-frontend/0.1 and holon-go-frontend/0.2. A 0.1
   config extracts byte for byte what it extracts at the base (the five spec/M2/facts/*.go.extracted.json from
   spec/M2/lib/go_frontend.json). A 0.2 config writes extraction.frontend_version holon-go/0.2 and adds, to the entry of
   every function that is codec-shaped (holon.frontends.go.analyses.Analysis.codec_shaped, unchanged) and has a loop of
   kind counted or range with an induction phi, a fuel and step 1, the key loop_bodies: one entry per such loop, in
   header order, {"span", "iv", "init", "step", "cmp", "limit", "fuel", "exits", "paths"}. The first eight are what the
   loop's go.loops entry holds; paths are the loop-free paths of one iteration over the symbolic induction variable
   ["iv", <iv>]: the blocks before the loop run as in the function's path enumeration, the header binds the induction
   variable with init <= iv assumed, every other phi of the header is an opaque term of its own (a loop-carried value
   is unknown in a later iteration), the header's own test forks the body from the exit, a jump back to the header ends
   a path "continue", the exit flows on to the function's return ("return", with its returns), and a bound site the
   reasoner cannot prove safe ends a path "panic" with its site id, by the enumeration's own rule. Memory the loop writes
   is read as at the loop's entry (per-iteration writes are not tracked; Y6 reads conditions over the induction variable
   and the parameter's cells only). A path is written as the paths section writes one: {"cond": [atom], "end": "panic" |
   "return" | "continue", "error": "nil" | "nonnil" | "unknown" | null (null unless the path returns), "returns": [term]
   | null, "site": site id | null}. A body over the path limit has paths null and a path_limit debt entry; an
   unsupported construct met in a body is a debt entry, as in a path enumeration. spec/schemas/facts_0_3_go.schema.json
   is extended additively (frontend_version holon-go/0.1 or 0.2, an optional loop_bodies of this shape). No other key of
   a document changes meaning.
Y2 The M3 document. spec/M3/lib/go_frontend.json (config 0.2; one document, morph_blob, of morph-l2/common/batch and
   morph-l2/common/blob; source, primitives and limits as spec/M2/lib/go_frontend.json's) and
   `python -m holon extract go --milestone M3` write spec/M3/facts/morph_blob.go.extracted.json, byte for byte what
   holon.gate's G1 re-extracts (unchanged code: it covers M3 because spec/M3/lib/link.json exists). From this prereg's
   merge to the build's, M3's full-gate G1 reports that document missing (the base frontend refuses config 0.2); CI runs
   no M3 G1. What its two RetrieveBlobBytes entries hold is recorded in I67-R4 (observed on the draft, not counted).
Y3 Go-op components. The sidecar spec/M3/lib/go_ops.json (go_ops_version holon-go-ops/0.1) names a Go document and its
   components, each {"carrier": a Go type, "reach": text}. holon.diagram.goops builds, per component, a holon-goops/0.1
   document {"goops_version", "component", "document": the Go document's path, "document_sha256", "carrier": {"id",
   "type", "reach"}, "ops": {model name: {"source", "params", "results", "span", "loop_bodies", "paths",
   "paths_reason", "sites"}}, "results": {result carrier id: [Go type]}}. The ops are every function of the document
   with exactly one parameter, of the carrier's type, whose last result is error. An op's model name is
   <package>_<function> for <path>/<package>.<function> and <package>_<type>_<method> for a method (<package> the
   import path's last segment); two ops with one model name, or a name that is not an identifier, are refused (exit 3,
   nothing written). "source" is the function id; the other op keys are the document's entry verbatim (loop_bodies
   null when absent). The carrier id is the type without its leading "*" and package path. A result carrier id is
   "R_" followed by the op's result types joined by "_", each written as an identifier: every leading "[]" as "Slice"
   and "*" as "Ptr", then the last name segment with its first letter upper-cased ([]byte, error: R_SliceByte_Error).
   `holon codecs --milestone M3` writes gen/M3/goops/<component>.json (--goops-out DIR overrides the directory; with
   --out alone no Go-op document is written, so --out DIR holds the linked codec documents only), removes a stale one,
   and --check covers both directories; gen/M3/codec/ does not change. holon/diagram/goops.py holds no target name:
   every name comes from the sidecar and the document.
Y4 Diagram and evidence. `holon diagram --milestone M3` also writes gen/M3/diagram/<component>.json per Go-op
   component (holon-diagram/0.1; the linked components' diagrams do not change): model the component, facts its
   gen/M3/goops path, facts_sha256, facts_version holon-goops/0.1; carriers the interface carrier {"id", "cls": "rep",
   "base_type": id, "sort_ref": null, "interface": true, "reach": "external", "domains": ["ok_<op>", ...] sorted,
   "key_space": "byte"} and per result carrier {"id", "cls": "rep", "base_type": id, "sort_ref": null, "interface":
   false, "reach": null}; one edge per op {"id": "CODEC.<op>", "kind": "CODEC", "model_fn": op, "src": the carrier id,
   "tgt": its result carrier id, "partial": false, "version": null, "fn_kind": "op", "source": [{"fn": function id}],
   "component": the Go document's path, "domain": "ok_<op>", "env": false, "pseudo": false, "principal_class": null,
   "access": {"reads": [], "writes": []}}. An op's error result is part of its value (partial false); its domain is
   where it does not panic. `holon evidence --milestone M3` adds one model per Go-op component (facts, facts_sha256,
   facts_version, diagram and anchors: "codec" model_fn -> edge id, "domains" ok_<op> -> [edge id], every other anchor
   key empty, as I24's for a linked component) and its E6 atoms (holon.diagram.evidence.e6 with I14's lexicon,
   unchanged); no other level (an op has no layout and no machine). spec/schemas/evidence.schema.json admits
   facts_version holon-goops/0.1. Every other model and atom of the evidence set stays as it is. A noted consequence: E6
   tokens come from the whole function id, so any two ops of one component with one result tuple share import-path
   tokens and get an E6 atom (the two clones also share retrieve, blob and bytes); the lexicon is I14's and unchanged.
Y5 Derivation. `holon derive --milestone M3` reads the Go-op components with the linked codec layer, each document,
   diagram and the evidence set byte for byte what holon codecs, holon diagram and holon evidence write now (else
   refused: a stale input), and runs the catalog's PAR producers over each component's diagram and atoms, as they are
   (holon.rules.par changes in no line). Over blob_ops that gives the laws expected_laws gives (prediction I67-P5),
   each with rule PAR and facts gen/M3/goops/blob_ops.json, and the cycle basis element of the component's non-tree
   edge is a duplicate of the weak law. The rule catalog does not change: no commit of I67's changes a law's
   rule_catalog_version or holon.rules' catalogs.
Y6 The model. holon.gen.goloop.generate(doc, sha) is gen/M3/model/<component>.bend (holon run writes it), from the
   Go-op document alone: a type Out with constructors OPanic, OErr and ORet (a panic, a non-nil error, a nil error);
   per op a function <op> over the cell sequence List<&2, U32>, ok_<op>(b) = not is_panic(<op>(b)), and eq_out and
   eq_bool. An op's model is its one loop body: the iterations consume the cell sequence one node per iteration (cell k
   is the array cell the body's path conditions read at iteration k, the parameter's cell a*k + c for constants a >= 1
   and c >= 0 of the document), the induction variable is a Nat, and a body path's index condition a*iv + c' REL C is
   the Nat condition on the induction variable it is equivalent to (a threshold such as iv >= ceil((C - c') / a)). A
   return path's outcome is its "error": nil is ORet, nonnil OErr; a panic path's is OPanic. The loop's exit paths give
   the outcome after the last iteration, and the fuel is the loop's trip count. The ops' definitions use no U32
   arithmetic (no U32 add, sub, mul, div, mod, shift or bit operation, no infix arithmetic on a U32): per iteration
   they compare the cell with constants (U32 comparisons) and the index with thresholds (Nat comparisons), and the
   index grows by Nat successor. An op outside this class (no loop body, more than one loop, a path condition reading a
   second cell or anything but the induction variable and the parameter's cells, a non-affine index, a return whose
   error is unknown, exit paths with two outcomes, body paths that do not partition the cell and index values) is
   Unsupported: the laws naming it are UNKNOWN, with the reason. holon/gen/goloop.py names no target.
Y7 Deciding. holon run decides a law whose facts is a Go-op document through holon.codecrun (a third kind, goops).
   Candidates, in order: per op of the component, by model name, its model's smallest panic witness (the first
   iteration k from the loop's init at which a panic path's conditions hold for some cell value: cell k the smallest
   byte value satisfying that path's cell conditions, every other cell the smallest byte value that keeps its iteration
   on a continue path; n cells, n the trip count); then the sequence of continue values (each the smallest such byte
   value). A law is REFUTED at the first candidate whose counter-law (BEND_PRIMER 5.4: exs b, the claim's two sides
   unequal; the motive the model's eq_out or eq_bool) bend accepts at its acceptance point (holon.mpipeline.accepted);
   its record's kernel verdict is BendTT --verdict's on that proof (predictions I67-P1-P3 say checked). Its witness is
   {"b": "0x" + the n cells, one byte each, in hex} and its difference {"lhs", "rhs"} the sides' values at it
   ("OPanic", "OErr", "ORet"; true, false). A law no candidate refutes is UNKNOWN, its bound naming the candidates and
   that a forall law over cell sequences has no proof route here (gap G6): there is no proof generator for these laws.
   The witness comes from the compiled model, never from the instrument or the real code.
Y8 Records and the gate. results/M3/<law id>.json per law over a Go-op document is holon.codecrun.decide's record (v1
   and v2 fields; evidence fields from gen/M3/evidence.json), status per Y7, replay per Y9. What the gate checks of
   such a law is made to hold by these changes, each generated, never hand-written: (a) the IR's binder rule takes a
   Go-op document's carrier id as its record type (holon.ir.check_binder_types); (b) its ledger bundle is generated from
   the Go-op document (holon.records' generated bundles, as I24's for a linked document): every assumption the Go
   document declares, introduced by the ops' definitions, and the model's own A-goloop-cells (an op's argument is the
   cells its body reads), A-goloop-outcome (errors and returned bytes are not modelled) and A-goloop-sites (an op panics
   only at the sites the frontend cannot prove safe; per-iteration writes are not tracked), so ledger_match is exact;
   (c) evidence.schema.json's facts_version enum admits holon-goops/0.1 (Y4); (d) holon.bindings binds a Go-op law to
   gen/M3/model/<component>.bend and its emission (holon.gen.goloop.emit, as codecrun writes the law file), and
   `holon bind --milestone M3 --laws <the four>` adds the four bindings to spec/bindings/M3.json, logged as added only
   (no other binding changes); (e) the statement hash's refs over a Go-op document (holon.gen.refs) are, for each op the
   claim names, "fn:<op>" (and "fn:ok_<op>" for its domain) the op's entry without source and span, and "carrier:<id>"
   the carrier's {"id", "type"}. The record carries no lean4 entry (no Lean emitter reads a Go-op document:
   holon.lean._attempted, as for I31's DISCH and I26's FACT laws) and, when REFUTED, witness_provenance {"go":
   "library_api"} from replay/M3/goops/report.json. Laws over other documents are decided as before.
Y9 Replay. `holon replay-go --milestone M3` concretizes the witness of every REFUTED record of a Go-op law: the carrier
   value whose array cell a*k + c (Y6's read) is cell k of the witness and whose every other byte is 0. It runs each op
   the law's claim names on it under recover(), from a Go test it generates from the Go-op document (the ops' function
   ids and the carrier's type) on a scratch copy of the pinned morph checkout (config replay.morph), and writes
   replay/M3/goops/report.json {"milestone", "morph_commit", "go_version", "laws": {law id: {"go": {"status": "passed"
   | "failed" | "not_run", "provenance": "library_api", "obstruction_observed", "observed": {op: real outcome class},
   "expected": {op: model outcome}, "detail": {op: what the real call did}, "command": a text with no absolute or
   scratch path}}}, "witness_sha256": {law id: holon.replay.witness_sha256(witness)}}. A side passes, with
   obstruction_observed true, iff every op's real outcome class (nil error ORet, non-nil error OErr, panic OPanic) is
   the model's at the witness. It stamps the records' replay field from the report, and holon run re-applies it
   (holon.replay.replay_status).
Y10 Filter. holon.refute_m3.i4_sides also reads replay/M3/goops/report.json (key "M3/<law id>", at the record's own
   witness). holon.refute_m3.kind_of takes a record every side of which is a Go library call (library_api) as go_only
   before its definedness (domain-witness) clause: rule K2 before K1's domain clause, amended in I40's contract and
   instrument at this prereg (Y13); no REFUTED record of the base changes kind under that order. So `holon refute
   --milestone M3 --only filter` gives a Go-op REFUTED record kind go_only, the reason "node-level public path needs
   I39", and final bin pending (holon.filter.final_bin's F4, unchanged).
Y11 Regenerated, never hand-written, by this recipe, in this order:
   - holon extract go --milestone M3: spec/M3/facts/morph_blob.go.extracted.json;
   - holon codecs --milestone M3: gen/M3/goops/blob_ops.json (gen/M3/codec/ byte-identical);
   - holon diagram --milestone M3: gen/M3/diagram/blob_ops.json (the others byte-identical);
   - holon evidence --milestone M3: gen/M3/evidence.json;
   - holon derive --milestone M3: laws/M3/ (the four laws; REGISTRY.json; DERIVATION.json);
   - holon lossy --milestone M3: gen/M3/par_lossy/header_length.json, its evidence input sha256 alone (the review file
     stays empty);
   - holon run --milestone M3 --laws <every PAR law of laws/M3> (how M3's PAR records are made since I24): gen/M3/model/
     (header_length.bend byte-identical, blob_ops.bend new), the PAR laws' law and proof directories (the base's
     byte-identical), their records (the base's 80 in generator_sha256 and seconds alone), results/M3/summary.json,
     deps.json and splits.json (the four laws added);
   - holon bind --milestone M3 --laws <the four>: spec/bindings/M3.json and one line of spec/bindings/changes.jsonl;
   - holon replay-go --milestone M3: replay/M3/goops/report.json, and the four records' replay fields;
   - holon run --milestone M1 and --milestone M2, and holon profile --milestone T32: every M1, M2 and T32 record in
     generator_sha256 and seconds alone, since I67's code is in the holon-ir/0.2 and 0.3 closures and in I32's
     (holon.profile.generator_files), as I66's V7 re-made them; no M0 file changes (holon-ir/0.1's closure has none of
     I67's files);
   - holon refute --milestone M3 --only filter: the filter fields of every REFUTED M1-M3 record (written back as before,
     the three new records gaining theirs), and results/M3/refute/concretization.json and filter.json, which gain
     exactly the three new records' entries;
   - holon metrics --milestone M3: results/M3/metrics.json.
   Every M3 record of a typed, UNDO, DISCH or FACT law trails I67's closures until the next M3 re-make, as at the base
   (the full M3 gate's G1 reports that staleness, holon/fact/gate.py and holon/sorts/gate3.py, as it does at the base;
   CI runs no M3 G1). No module of a generator closure comes to import one of I32's files (I32-R2 computes closures at
   HEAD).
Y12 Coordination. I28's build holds holon-rules/1.6 and re-makes the M3 records. I67's checks are judged at I67's own
   commits (each against its first parent), so another key's changes merged into I67's branch are never counted as
   I67's. Whichever of I67 and I28 merges second re-derives laws/M3 and re-makes what changes.
Y13 Earlier tests amended at this prereg (spec/M3/amendments.jsonl), each narrowed to I67's outcomes, as I28 and I66
   amended theirs: I24's helpers and checks that take every PAR law (tests_m3/test_derive_par.py _Morph.derived,
   test_derivation_follows_the_rules, test_cycle_basis_count_equals_the_preregistered_rank; tests_m3/test_par_outcomes.py
   par_records and test_every_m3_law_has_a_valid_record) leave out the laws over a Go-op document, and the cycle-rank
   and basis checks read the linked component's rows; I43's count of M3 PAR records (tests_m3/test_lean_promoted.py
   TestRegressions.test_statuses_and_bend_files_are_unchanged) counts those over the linked codec document; I40's rule
   order (tests_m3/_i40.py concretization_kind and the K1/K2 text of tests_m3/test_refute.py's contract) takes K2 before
   K1's domain clause (Y10); F39's tests-m3-catalog check (tests_m3/test_catalog_rederivation.py, no key's test) counts
   the PAR laws over the linked codec document.

Predictions are in spec/M3/predictions.json under I67; the tests below check them and the rules above.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import tests_m3._i67 as I
from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_holon

KEY = "I67"
M = "M3"
DOC = "spec/M3/facts/morph_blob.go.extracted.json"
COMP = "blob_ops"
GOOPS = f"gen/M3/goops/{COMP}.json"
DIAGRAM = f"gen/M3/diagram/{COMP}.json"
MODEL = f"gen/M3/model/{COMP}.bend"
REPORT = "replay/M3/goops/report.json"
BATCH, BLOB = "batch_RetrieveBlobBytes", "blob_RetrieveBlobBytes"
BATCH_FN, BLOB_FN = "morph-l2/common/batch.RetrieveBlobBytes", "morph-l2/common/blob.RetrieveBlobBytes"
TOT_BATCH, TOT_BLOB = f"L_par_tot_{BATCH}", f"L_par_tot_{BLOB}"
WEAK = f"L_par_weak_{BATCH}_{BLOB}"
DOM = f"L_par_dom_ok_{BATCH}_ok_{BLOB}"
LAWS = (DOM, TOT_BATCH, TOT_BLOB, WEAK)
CYCLE = f"L_par_cy_{BLOB}"
THRESHOLD = 3968
TARGET_WORDS = re.compile(r"(morph|Morph|kzg4844|RetrieveBlobBytes|MakeBlobCanonical|blob_ops|go-ethereum|"
                          r"(?<![\w.])(3967|3968|4095|4096|126976|131072)(?![\w.]))")


# ------------------------------------------------------------------------------------------------ helpers
def th() -> dict:
    return predictions(KEY)["thresholds"]


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def _is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base --is-ancestor {a} {b}: {p.stderr.strip()}")
    return p.returncode == 0


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I67 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I67")


def i67_merge() -> tuple[str | None, str | None]:
    """(R, M) by ancestry, as I32's test finds its own (tests_m3/test_disch_profile.py): R the oldest commit reachable
    from HEAD that adds docs/iterations/I67.md, M the oldest merge of R..HEAD whose second parent reaches R and whose
    first parent does not (None on I67's own branch before its merge)."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I67.md").split()
    if not added:
        return None, None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return r, c
    return r, None


def own_commits() -> tuple[dict[str, list[str]], str, str]:
    """I67's own non-merge commits after its prereg, each with the paths it changes, the commit they end at, and the
    prereg commit: along the first-parent line of M^2 back to the lead when I67 is merged, else prereg..HEAD."""
    pre = prereg_commit()
    _, m = i67_merge()
    if m is not None:
        first, second = git("rev-parse", f"{m}^1", f"{m}^2").split()
        revs, end = [second, f"^{first}", f"^{pre}"], second
    else:
        revs, end = [f"{pre}..HEAD"], "HEAD"
    out: dict[str, list[str]] = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out, end, pre


def _unstamped(x):
    """A record without generator_sha256 (at the top) and without any key named "seconds" (anywhere)."""
    def walk(v):
        if isinstance(v, dict):
            return {k: walk(w) for k, w in v.items() if k != "seconds"}
        if isinstance(v, list):
            return [walk(w) for w in v]
        return v
    return {k: v for k, v in walk(x).items() if k != "generator_sha256"}


def at(c: str, path: str):
    """The JSON document at path in commit c, or None when the commit holds no such file."""
    try:
        return json.loads(git("show", f"{c}:{path}"))
    except AssertionError:
        return None


def own_changes(path: str) -> list[tuple[str, str]]:
    """(parent, commit) of every own commit of I67's (own_commits) that changes path."""
    own, _, _ = own_commits()
    return [(git("rev-parse", f"{c}^1").strip(), c) for c, paths in sorted(own.items()) if path in paths]


def named_ops(law: dict) -> list[str]:
    """The ops a law's claim names (an op, or its domain ok_<op>), sorted."""
    out = set()
    for t in law["statement"]["claim"]["eq"]:
        f = t.get("call") if isinstance(t, dict) else None
        if isinstance(f, str):
            out.add(f[3:] if f.startswith("ok_") else f)
    return sorted(out)


def need_built(test) -> None:
    for rel in (DOC, GOOPS, DIAGRAM):
        test.assertTrue((ROOT / rel).is_file(), f"{rel} is not committed (no build)")


def law(lid: str) -> dict:
    p = ROOT / "laws" / M / f"{lid}.json"
    if not p.is_file():
        raise AssertionError(f"laws/{M}/{lid}.json is not committed (no build)")
    return load_json(p)


def rec(lid: str) -> dict:
    p = ROOT / "results" / M / f"{lid}.json"
    if not p.is_file():
        raise AssertionError(f"results/{M}/{lid}.json is not committed (no build)")
    return load_json(p)


def witness_cells(r: dict) -> list[int]:
    w = r.get("witness")
    if not isinstance(w, dict) or sorted(w) != ["b"]:
        raise AssertionError(f"{r.get('law_id')}: witness {str(w)[:80]!r} is not {{'b': cells}} (Y7)")
    return I.cells_of_hex(w["b"])


def real_outcomes(cells: list[int]) -> dict[str, str]:
    """The instrument's real outcomes of the two clones at a witness's concretization (Y9)."""
    out = I.run_instrument([I.cells_probe(cells)])
    return {BATCH: out["common/batch"][0], BLOB: out["common/blob"][0]}


def scratch() -> Path:
    d = Path(tempfile.mkdtemp(prefix="holon-i67-test-"))
    _DIRS.append(d)
    return d


_DIRS: list[Path] = []


def tearDownModule():
    for d in _DIRS:
        shutil.rmtree(d, ignore_errors=True)


def go_entry(doc: dict, fid: str) -> dict:
    f = doc["go"]["functions"].get(fid)
    if f is None:
        raise AssertionError(f"{DOC} has no function {fid}")
    return f


def body_paths(entry: dict) -> list[dict]:
    lbs = entry.get("loop_bodies")
    if not isinstance(lbs, list) or len(lbs) != 1:
        raise AssertionError(f"expected exactly one loop body, got {None if lbs is None else len(lbs)}")
    return lbs[0]["paths"]


# ------------------------------------------------------------------------------------------------ instrument
class TestInstrument(unittest.TestCase):
    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i67.py"), t["instrument_sha256"])
        self.assertEqual(file_sha256(I.INSTRUMENT), t["go_instrument_sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        for k in ("frontend_config", "sidecar"):
            with self.subTest(sidecar=k):
                self.assertEqual(file_sha256(ROOT / t[k]["path"]), t[k]["sha256"])

    def test_the_real_code_is_o4(self):
        """The real clones on the probe set (I18's O4 on the real code, observed again by this key's own instrument):
        the batch clone returns an error for an element below 3968 and panics with a runtime index error at data[32 e]
        (length 126976) from 3968 on; the blob clone returns an error for every element and never panics; both return
        the same bytes, with a nil error, on the zero blob and on payload bytes only; a non-zero element below the
        threshold comes first (error); the threshold element at 255 panics."""
        out = I.run_instrument()
        b, c = out["common/batch"], out["common/blob"]
        for e in range(I.CELLS):
            with self.subTest(element=e):
                if e < THRESHOLD:
                    self.assertEqual(I.kind(b[1 + e]), "err")
                else:
                    self.assertTrue(I.index_panic(b[1 + e], I.STRIDE * e, I.OUT_LEN), b[1 + e])
                self.assertEqual(I.kind(c[1 + e]), "err")
        n = 1 + I.CELLS
        self.assertEqual((I.kind(b[0]), b[0]), ("ok", c[0]))
        self.assertEqual((I.kind(b[n]), b[n]), ("ok", c[n]))
        self.assertEqual((I.kind(b[n + 1]), I.kind(c[n + 1])), ("err", "err"))
        self.assertTrue(I.index_panic(b[n + 2], I.STRIDE * THRESHOLD, I.OUT_LEN), b[n + 2])
        self.assertEqual((I.kind(b[n + 3]), I.kind(c[n + 3])), ("err", "err"))
        self.assertFalse([x for x in c if I.kind(x) == "panic"])


# ------------------------------------------------------------------------------------------------ frontend
class TestFrontend(unittest.TestCase):
    def test_r1_m2_documents_reextract_byte_identical(self):
        """I67-R1 and Y1: the M2 sidecar (config 0.1) extracts the five committed M2 Go documents byte for byte."""
        item(KEY, "I67-R1")
        out = scratch()
        p = run_holon(["extract", "go", "--milestone", "M2", "--out-dir", str(out)], timeout=3600)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        want = sorted((ROOT / "spec" / "M2" / "facts").glob("*.go.extracted.json"))
        self.assertEqual(sorted(x.name for x in out.iterdir()), [x.name for x in want])
        for w in want:
            with self.subTest(document=w.name):
                self.assertEqual((out / w.name).read_bytes(), w.read_bytes())

    def test_y2_m3_document_reextracts(self):
        """Y2: `holon extract go --milestone M3` writes the committed document, and only it, byte for byte."""
        need_built(self)
        out = scratch()
        p = run_holon(["extract", "go", "--milestone", M, "--out-dir", str(out)], timeout=3600)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(sorted(x.name for x in out.iterdir()), [Path(DOC).name])
        self.assertEqual((out / Path(DOC).name).read_bytes(), (ROOT / DOC).read_bytes())

    def test_y1_loop_bodies_shape(self):
        """Y1 on the M3 document: frontend holon-go/0.2, and every loop_bodies entry has the contract's keys, the
        go.loops entry's eight fields, and paths of the contract's shape."""
        need_built(self)
        doc = load_json(ROOT / DOC)
        self.assertEqual(doc["extraction"]["frontend_version"], "holon-go/0.2")
        loops = {}
        for lp in doc["go"]["loops"]:
            loops.setdefault(lp["function"], []).append(lp)
        n = 0
        for fid, f in sorted(doc["go"]["functions"].items()):
            for k, lb in enumerate(f.get("loop_bodies") or []):
                n += 1
                with self.subTest(function=fid, loop=k):
                    self.assertEqual(sorted(lb), sorted(["span", "iv", "init", "step", "cmp", "limit", "fuel", "exits",
                                                         "paths"]))
                    hits = [lp for lp in loops.get(fid, []) if lp["span"] == lb["span"]]
                    self.assertEqual(len(hits), 1)
                    for key in ("iv", "init", "step", "cmp", "limit", "fuel", "exits"):
                        self.assertEqual(lb[key], hits[0][key], key)
                    self.assertEqual(lb["step"], 1)
                    # as the paths section writes one: an error class only on a return from a function whose last
                    # result is error (null on every other path)
                    returns_error = bool(f.get("results")) and f["results"][-1] == "error"
                    for p in lb["paths"] or []:
                        self.assertEqual(sorted(p), ["cond", "end", "error", "returns", "site"])
                        self.assertIn(p["end"], ("panic", "return", "continue"))
                        self.assertEqual(p["site"] is not None, p["end"] == "panic")
                        self.assertEqual(p["returns"] is not None, p["end"] == "return")
                        self.assertIn(p["error"], (None, "nil", "nonnil", "unknown"))
                        self.assertEqual(p["error"] is not None, p["end"] == "return" and returns_error)
        self.assertGreater(n, 0)

    def test_r4_the_two_loop_bodies(self):
        """I67-R4 (recorded, not counted: observed on the draft before the prereg): the batch clone's loop body (4096
        iterations from 0) has exactly one panic path, at the site the 0.1 sites section holds open for that function
        (I18's data[i*32] at blob.go:49, witness i from 3968 to 4095); the blob clone's has no panic path and its sites
        are all safe."""
        item(KEY, "I67-R4")
        need_built(self)
        doc = load_json(ROOT / DOC)
        b, c = go_entry(doc, BATCH_FN), go_entry(doc, BLOB_FN)
        for e in (b, c):
            lb = e["loop_bodies"][0]
            self.assertEqual((lb["init"], lb["limit"], lb["step"]), (["const", 0], ["const", I.CELLS], 1))
        panics = [p for p in body_paths(b) if p["end"] == "panic"]
        self.assertEqual(len(panics), 1)
        open_sites = [s for s in b["sites"] if s.get("status") == "open"]
        self.assertEqual([s["id"] for s in open_sites], [panics[0]["site"]])
        self.assertTrue(open_sites[0]["id"].startswith("common/batch/blob.go:49:"), open_sites[0]["id"])
        self.assertEqual([p for p in body_paths(c) if p["end"] == "panic"], [])
        self.assertEqual([s for s in c["sites"] if s.get("status") == "open"], [])


# ------------------------------------------------------------------------------------------------ component
class TestComponent(unittest.TestCase):
    def test_y3_the_goops_document(self):
        """Y3: the committed blob_ops document is what `holon codecs --milestone M3 --check` accepts, its ops are the
        instrument's (the two clones), each op's entries are the document's verbatim, and its carriers are named by
        rule."""
        need_built(self)
        p = run_holon(["codecs", "--milestone", M, "--check"], timeout=1800)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        sc, doc, g = load_json(I.SIDECAR), load_json(ROOT / DOC), load_json(ROOT / GOOPS)
        want = I.expected_ops(sc, doc)
        self.assertEqual(sorted(want), [COMP])
        self.assertEqual(want[COMP]["ops"], {BATCH: BATCH_FN, BLOB: BLOB_FN})
        self.assertEqual((g["goops_version"], g["component"], g["document"], g["document_sha256"]),
                         ("holon-goops/0.1", COMP, DOC, file_sha256(ROOT / DOC)))
        self.assertEqual(g["carrier"], {"id": "Blob", "type": sc["components"][COMP]["carrier"],
                                        "reach": sc["components"][COMP]["reach"]})
        self.assertEqual(sorted(g["ops"]), [BATCH, BLOB])
        for name, fid in want[COMP]["ops"].items():
            f = go_entry(doc, fid)
            with self.subTest(op=name):
                o = g["ops"][name]
                self.assertEqual(o["source"], fid)
                for k in ("params", "results", "span", "paths", "paths_reason", "sites"):
                    self.assertEqual(o[k], f.get(k), k)
                self.assertEqual(o["loop_bodies"], f.get("loop_bodies"))
        self.assertEqual(g["results"], {"R_SliceByte_Error": ["[]byte", "error"]})

    def test_y3_y6_no_target_vocabulary(self):
        """I67-R3 (Y3, Y6, Y1): the new modules and the frontend's 0.2 code hold no target name, span or blob constant
        and import no test oracle."""
        item(KEY, "I67-R3")
        files = [ROOT / "holon" / "diagram" / "goops.py", ROOT / "holon" / "gen" / "goloop.py"]
        files += sorted((ROOT / "holon" / "frontends" / "go").glob("*.py"))
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(f.is_file(), "missing (no build)")
                text = f.read_text(encoding="utf-8")
                self.assertEqual(TARGET_WORDS.findall(text), [])
                self.assertIsNone(re.search(r"\w+\.(go|sol):\d+", text))
                self.assertIsNone(re.search(r"(?m)^\s*(from|import)\s+tests(_m\d+)?\b", text))

    def test_y4_diagram(self):
        """Y4: `holon diagram --milestone M3` writes the committed diagrams, the linked ones unchanged, and blob_ops's
        carriers and edges are the contract's."""
        need_built(self)
        out = scratch()
        p = run_holon(["diagram", "--milestone", M, "--out", str(out)], timeout=1800)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        have = sorted((ROOT / "gen" / M / "diagram").glob("*.json"))
        self.assertEqual(sorted(x.name for x in out.iterdir()), [x.name for x in have])
        for h in have:
            with self.subTest(diagram=h.name):
                self.assertEqual((out / h.name).read_bytes(), h.read_bytes())
        dg = load_json(ROOT / DIAGRAM)
        self.assertEqual((dg["model"], dg["facts"], dg["facts_sha256"], dg["facts_version"]),
                         (COMP, GOOPS, file_sha256(ROOT / GOOPS), "holon-goops/0.1"))
        cars = {c["id"]: c for c in dg["carriers"]}
        self.assertEqual(sorted(cars), ["Blob", "R_SliceByte_Error"])
        self.assertEqual(cars["Blob"], {"id": "Blob", "cls": "rep", "base_type": "Blob", "sort_ref": None,
                                        "interface": True, "reach": "external", "key_space": "byte",
                                        "domains": [f"ok_{BATCH}", f"ok_{BLOB}"]})
        self.assertEqual(cars["R_SliceByte_Error"], {"id": "R_SliceByte_Error", "cls": "rep",
                                                     "base_type": "R_SliceByte_Error", "sort_ref": None,
                                                     "interface": False, "reach": None})
        edges = {e["id"]: e for e in dg["edges"]}
        self.assertEqual(sorted(edges), [f"CODEC.{BATCH}", f"CODEC.{BLOB}"])
        for op, fid in ((BATCH, BATCH_FN), (BLOB, BLOB_FN)):
            with self.subTest(edge=op):
                self.assertEqual(edges[f"CODEC.{op}"], {
                    "id": f"CODEC.{op}", "kind": "CODEC", "model_fn": op, "src": "Blob", "tgt": "R_SliceByte_Error",
                    "partial": False, "version": None, "fn_kind": "op", "source": [{"fn": fid}], "component": DOC,
                    "domain": f"ok_{op}", "env": False, "pseudo": False, "principal_class": None,
                    "access": {"reads": [], "writes": []}})

    def test_y4_evidence(self):
        """Y4: gen/M3/evidence.json is what a fresh build gives; blob_ops's model has the contract's anchors and one E6
        atom, between the two clones; every other model and atom is the one at the prereg."""
        need_built(self)
        E = holon_module("holon.diagram.evidence")
        text = (ROOT / "gen" / M / "evidence.json").read_text(encoding="utf-8")
        self.assertEqual(E.render(E.build_milestone(M, ROOT)), text)
        ev = json.loads(text)
        mdl = ev["models"][COMP]
        self.assertEqual((mdl["facts"], mdl["facts_sha256"], mdl["facts_version"]),
                         (GOOPS, file_sha256(ROOT / GOOPS), "holon-goops/0.1"))
        an = mdl["anchors"]
        self.assertEqual(an["codec"], {BATCH: f"CODEC.{BATCH}", BLOB: f"CODEC.{BLOB}"})
        self.assertEqual(an["domains"], {f"ok_{BATCH}": [f"CODEC.{BATCH}"], f"ok_{BLOB}": [f"CODEC.{BLOB}"]})
        self.assertFalse([k for k, v in an.items() if k not in ("codec", "domains") and v])
        mine = [a for a in ev["atoms"] if a["model"] == COMP]
        self.assertEqual([(a["level"], a["p"], a["q"]) for a in mine], [("E6", f"CODEC.{BATCH}", f"CODEC.{BLOB}")])
        self.assertTrue({"retrieve", "blob", "bytes"} <= set(mine[0]["via"]["tokens"]), mine[0]["via"])
        changes = own_changes("gen/M3/evidence.json")
        self.assertTrue(changes, "no own commit changes gen/M3/evidence.json")
        for parent, c in changes:   # judged at I67's own commits (Y12): another key's models are never I67's
            with self.subTest(commit=c[:12]):
                old, new = at(parent, "gen/M3/evidence.json"), at(c, "gen/M3/evidence.json")
                self.assertEqual({k: v for k, v in new["models"].items() if k != COMP},
                                 {k: v for k, v in old["models"].items() if k != COMP})
                self.assertEqual([a for a in new["atoms"] if a["model"] != COMP],
                                 [a for a in old["atoms"] if a["model"] != COMP])


# ------------------------------------------------------------------------------------------------ derivation
class TestDerivation(unittest.TestCase):
    def test_p5_four_laws_and_the_duplicate(self):
        """I67-P5 and Y5: the laws over the Go-op document are exactly the instrument's four, rule PAR, with the
        producers' statements; DERIVATION records the cycle element of CODEC.blob_RetrieveBlobBytes as a duplicate of
        the weak law; the committed laws/M3 regenerates (holon derive's computation, as G1 runs it)."""
        item(KEY, "I67-P5")
        need_built(self)
        g = load_json(ROOT / GOOPS)
        want = I.expected_laws({"carrier": g["carrier"]["id"], "ops": g["ops"]})
        self.assertEqual(sorted(want), sorted(LAWS))
        mine = {p.stem: load_json(p) for p in sorted((ROOT / "laws" / M).glob("L*.json"))
                if load_json(p).get("facts") == GOOPS}
        self.assertEqual(sorted(mine), sorted(LAWS))
        subs = {TOT_BATCH: "totality", TOT_BLOB: "totality", WEAK: "weak", DOM: "domain_coherence"}
        for lid, lw in mine.items():
            with self.subTest(law=lid):
                self.assertEqual((lw["rule"], lw["subform"], lw["milestone"], lw["ir_version"]),
                                 ("PAR", subs[lid], M, "holon-ir/0.3"))
                self.assertEqual(lw["statement"], want[lid])
                self.assertEqual(lw["facts_sha256"], file_sha256(ROOT / GOOPS))
        der = load_json(ROOT / "laws" / M / "DERIVATION.json")
        cyc = [b for b in der["par_basis"] if b["model"] == COMP and b["subform"] == "cycle"]
        self.assertEqual([(b["key"], b["laws"], b["duplicates"]) for b in cyc],
                         [({"edge": f"CODEC.{BLOB}"}, [], {CYCLE: WEAK})])
        for parent, c in own_changes(f"laws/{M}/REGISTRY.json"):   # Y5: no own commit changes the catalog
            with self.subTest(commit=c[:12]):
                self.assertEqual(at(c, f"laws/{M}/REGISTRY.json").get("rule_catalog_version"),
                                 at(parent, f"laws/{M}/REGISTRY.json").get("rule_catalog_version"))
        reg = load_json(ROOT / "laws" / M / "REGISTRY.json")
        for lid in LAWS:
            with self.subTest(catalog=lid):
                self.assertEqual(law(lid)["rule_catalog_version"], reg["rule_catalog_version"])
        rules, contracts = holon_module("holon.rules"), holon_module("holon.contracts")
        res = contracts.with_contracts(M, ROOT, rules.compute(M, ROOT))
        for lid in LAWS:
            with self.subTest(regenerates=lid):
                self.assertEqual(rules.dumps(res["laws"][lid]), (ROOT / "laws" / M / f"{lid}.json").read_text())
        self.assertEqual(res["derivation_text"], (ROOT / "laws" / M / "DERIVATION.json").read_text())
        self.assertEqual(rules.dumps(res["registry"]), (ROOT / "laws" / M / "REGISTRY.json").read_text())


# ------------------------------------------------------------------------------------------------ model
class TestModel(unittest.TestCase):
    def test_y6_the_model(self):
        """Y6: the committed model is holon.gen.goloop.generate of the Go-op document; it defines Out (OPanic, OErr,
        ORet), each op, ok_<op>, eq_out and eq_bool; the open site is a Nat threshold (3968n) and no U32 arithmetic
        appears."""
        need_built(self)
        G = holon_module("holon.gen.goloop")
        raw = (ROOT / GOOPS).read_bytes()
        text = (ROOT / MODEL).read_text(encoding="utf-8")
        self.assertEqual(G.generate(json.loads(raw), hashlib.sha256(raw).hexdigest()), text)
        for name in ("OPanic", "OErr", "ORet", f"def {BATCH}(", f"def {BLOB}(", f"def ok_{BATCH}(", f"def ok_{BLOB}(",
                     "def eq_out(", "def eq_bool("):
            with self.subTest(defines=name):
                self.assertIn(name, text)
        self.assertIn(f"{THRESHOLD}n", text)
        self.assertIsNone(re.search(r"U32\.(add|sub|mul|div|mod|divmod|pow|shl|shr|shln|shrn|and|or|xor|not|inc|dec)\b",
                                    text))
        for line in text.splitlines():   # infix arithmetic only as the index's Nat successor 1n+<var>
            if line.lstrip().startswith("#"):
                continue
            rest = re.sub(r"\b1n\+[A-Za-z_]\w*", "", line)
            rest = re.sub(r"[-=]>|<[^<>]*>", "", rest)   # arrows and type arguments
            rest = re.sub(r"(?<=[(,{\s])\+(?=[A-Za-z_])", "", rest)   # reuse markers (+x) of binders
            with self.subTest(line=line.strip()):
                self.assertIsNone(re.search(r"[+*/%]|\s-\s", rest))


# ------------------------------------------------------------------------------------------------ outcomes
class TestOutcomes(unittest.TestCase):
    def _refuted(self, lid: str, diff: dict, real: dict[str, str]) -> dict:
        r = rec(lid)
        self.assertEqual(r["status"], "REFUTED")
        self.assertEqual(r["kernel"]["verdict"], "checked")
        cells = witness_cells(r)
        self.assertEqual(len(cells), I.CELLS)
        self.assertEqual(cells, I.single_cell(THRESHOLD))
        self.assertEqual(r["difference"], diff)
        for k in ("laws", "proof"):
            self.assertTrue((ROOT / r["artifacts"][k]).is_file(), r["artifacts"][k])
        self.assertEqual(r["replay"]["status"], "passed", r["replay"])
        got = real_outcomes(cells)
        for op, want in real.items():
            with self.subTest(real=op):
                self.assertEqual(I.outcome_class(got[op]), want, got[op])
        return r

    def test_p1_o4_totality_refuted_at_real_size(self):
        """I67-P1 (O4): L_par_tot_batch_RetrieveBlobBytes is REFUTED at the 4096-cell witness whose cell 3968 is 1,
        bend-accepted and BendTT-checked, its difference false against true; on the real code the batch clone panics
        with a runtime index error at data[126976] (length 126976), and the replay passed."""
        item(KEY, "I67-P1")
        self._refuted(TOT_BATCH, {"lhs": False, "rhs": True}, {BATCH: "OPanic"})
        got = real_outcomes(I.single_cell(THRESHOLD))
        self.assertTrue(I.index_panic(got[BATCH], I.STRIDE * THRESHOLD, I.OUT_LEN), got[BATCH])

    def test_p2_clone_pair_refuted(self):
        """I67-P2: the clone pair's weak law is REFUTED at the same witness, OPanic against OErr; replayed."""
        item(KEY, "I67-P2")
        self._refuted(WEAK, {"lhs": "OPanic", "rhs": "OErr"}, {BATCH: "OPanic", BLOB: "OErr"})

    def test_p3_domain_coherence_refuted(self):
        """I67-P3: the domains of the two clones disagree at the same witness, false against true; replayed."""
        item(KEY, "I67-P3")
        self._refuted(DOM, {"lhs": False, "rhs": True}, {BATCH: "OPanic", BLOB: "OErr"})

    def test_p4_fixed_copy_unknown(self):
        """I67-P4: the fixed copy's totality law is UNKNOWN, its bound naming the candidates and gap G6; no law file
        is kept; the real blob clone panics on no probe of the instrument."""
        item(KEY, "I67-P4")
        r = rec(TOT_BLOB)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertIn("G6", r["bound"])
        self.assertIn("candidate", r["bound"])
        self.assertIsNone(r["artifacts"]["laws"])
        self.assertFalse([x for x in I.run_instrument()["common/blob"] if I.kind(x) == "panic"])


# ------------------------------------------------------------------------------------------------ records and gate
class TestRecords(unittest.TestCase):
    def test_y8_what_the_gate_checks(self):
        """Y8: each record's binder type is the IR's (a), its ledger bundle exact (b), its evidence model admitted by the
        evidence schema (c), its binding in spec/bindings/M3.json over the Go-op model (d); no lean4 entry; a REFUTED
        record's witness_provenance is {"go": "library_api"}."""
        need_built(self)
        IR = holon_module("holon.ir")
        doc = load_json(ROOT / GOOPS)
        binds = load_json(ROOT / "spec" / "bindings" / "M3.json")["laws"]
        for lid in LAWS:
            r, lw = rec(lid), law(lid)
            with self.subTest(law=lid):
                IR.check_binder_types(lw, doc)
                self.assertEqual(r["ledger_match"], "exact")
                self.assertEqual([k for k in r.get("kernels") or [] if k.get("name") == "lean4"], [])
                if r["status"] == "REFUTED":
                    self.assertEqual(r["witness_provenance"], {"go": "library_api"})
                self.assertEqual(binds[lid]["model"], MODEL)
                self.assertEqual(binds[lid]["statement_hash"], r["statement_hash"])

    def test_y8_statement_refs(self):
        """Y8(e): a Go-op law's statement refs are fn:<op> (and fn:ok_<op>) for the ops its claim names and
        carrier:<id>; an op's ref ignores its source and span and follows its loop body."""
        need_built(self)
        R = holon_module("holon.gen.refs")
        doc = load_json(ROOT / GOOPS)
        for lid in LAWS:
            lw = law(lid)
            with self.subTest(law=lid):
                calls = sorted({t["call"] for t in lw["statement"]["claim"]["eq"] if isinstance(t, dict) and "call" in t})
                refs = R.refs(lw, doc)
                self.assertEqual(sorted(refs), sorted([f"fn:{f}" for f in calls] + ["carrier:Blob"]))
                op = named_ops(lw)[0]
                moved = json.loads(json.dumps(doc))
                moved["ops"][op]["span"] = "elsewhere"
                moved["ops"][op]["source"] = "elsewhere"
                self.assertEqual(R.refs(lw, moved), refs)
                edited = json.loads(json.dumps(doc))
                edited["ops"][op]["loop_bodies"] = []
                self.assertNotEqual(R.refs(lw, edited), refs)


# ------------------------------------------------------------------------------------------------ replay and filter
class TestReplay(unittest.TestCase):
    def test_y9_the_report(self):
        """Y9: replay/M3/goops/report.json holds one passed library_api side per REFUTED Go-op record, at that record's
        witness, its observed outcomes the instrument's classes and its expected outcomes the model's."""
        need_built(self)
        rep = load_json(ROOT / REPORT)
        R = holon_module("holon.replay")
        self.assertEqual(rep["milestone"], M)
        self.assertEqual(rep["morph_commit"], load_json(I.FRONTEND_CONFIG)["target"]["commit"])
        refuted = [lid for lid in LAWS if rec(lid)["status"] == "REFUTED"]
        self.assertEqual(sorted(rep["laws"]), sorted(refuted))
        for lid in refuted:
            r = rec(lid)
            with self.subTest(law=lid):
                side = rep["laws"][lid]["go"]
                self.assertEqual((side["status"], side["provenance"], side["obstruction_observed"]),
                                 ("passed", "library_api", True))
                self.assertEqual(rep["witness_sha256"][lid], R.witness_sha256(r["witness"]))
                got = real_outcomes(witness_cells(r))
                self.assertEqual(sorted(side["observed"]), named_ops(law(lid)))
                self.assertEqual(side["observed"], {op: I.outcome_class(got[op]) for op in side["observed"]})
                self.assertEqual(side["observed"], side["expected"])
                self.assertIsNone(re.search(r"(^|[\s(=])/|tmp|holon-", side["command"]), side["command"])

    def test_y10_the_bins(self):
        """Y10: the REFUTED Go-op records carry concretization kind go_only and filter_bin pending."""
        need_built(self)
        for lid in LAWS:
            r = rec(lid)
            if r["status"] != "REFUTED":
                continue
            with self.subTest(law=lid):
                self.assertEqual(r["concretization"]["kind"], "go_only")
                self.assertEqual(r["filter_bin"], "pending")


# ------------------------------------------------------------------------------------------------ regressions
class TestRegressions(unittest.TestCase):
    def test_r2_nothing_else_changes(self):
        """I67-R2, judged commit by commit: each of I67's own commits against its first parent (Y12: another key's
        changes merged into I67's branch, I28's re-make under holon-rules/1.6 for one, are never counted as I67's). An
        own commit changes, under laws/M3, results/M3 and gen/M3, only the four laws and records, their law and proof
        directories, gen/M3/goops/, gen/M3/diagram/blob_ops.json, gen/M3/model/blob_ops.bend and what Y11's recipe writes
        besides: gen/M3/evidence.json, laws/M3/REGISTRY.json and DERIVATION.json, gen/M3/par_lossy/header_length.json
        (its evidence input sha256 alone), results/M3/summary.json, deps.json, splits.json, metrics.json,
        results/M3/refute/concretization.json and filter.json (gaining only the four laws' entries), and the records, law
        and proof directories of the PAR laws its parent's summary lists, each such record equal to its parent's version
        but for generator_sha256 and keys named seconds. summary.json and DERIVATION.json gain only the four laws, every
        other entry unchanged (statement hashes included). At the end of I67's own commits the four laws are derived."""
        item(KEY, "I67-R2")
        own, end, pre = own_commits()
        self.assertTrue(own, "no commit of I67's after its prereg")
        fixed = {f"laws/M3/{lid}.json" for lid in LAWS} | {f"results/M3/{lid}.json" for lid in LAWS} | {
            "gen/M3/diagram/blob_ops.json", MODEL, "gen/M3/evidence.json", "laws/M3/REGISTRY.json",
            "laws/M3/DERIVATION.json", "gen/M3/par_lossy/header_length.json", "results/M3/summary.json",
            "results/M3/deps.json", "results/M3/splits.json", "results/M3/metrics.json",
            "results/M3/refute/concretization.json", "results/M3/refute/filter.json"}
        mine = {f"M3/{lid}" for lid in LAWS}
        for c, paths in sorted(own.items()):
            parent = git("rev-parse", f"{c}^1").strip()
            par = sorted(at(parent, "results/M3/summary.json") or {})
            allowed = fixed | {f"results/M3/{lid}.json" for lid in par}
            prefixes = ("gen/M3/goops/",) + tuple(f"gen/M3/{d}/{lid}/" for d in ("laws", "proofs")
                                                  for lid in LAWS + tuple(par))
            with self.subTest(commit=c[:12]):
                bad = [f for f in paths if re.match(r"^(laws|results|gen)/M3/", f) and f not in allowed
                       and not f.startswith(prefixes)]
                self.assertEqual(bad, [])
                for lid in par:
                    f = f"results/M3/{lid}.json"
                    if f in paths and lid not in LAWS:
                        o, n = at(parent, f), at(c, f)
                        if o is not None and n is not None:
                            self.assertEqual(_unstamped(n), _unstamped(o), lid)
                for f in ("results/M3/summary.json", "laws/M3/DERIVATION.json", "results/M3/refute/concretization.json",
                          "results/M3/refute/filter.json"):
                    if f not in paths:
                        continue
                    o, n = at(parent, f) or {}, at(c, f) or {}
                    if f.endswith("DERIVATION.json"):
                        o = {e["law_id"]: e for e in o.get("laws", [])}
                        n = {e["law_id"]: e for e in n.get("laws", [])}
                        new_ok = set(LAWS)
                    elif f.startswith("results/M3/refute/"):
                        o, n, new_ok = o.get("records") or {}, n.get("records") or {}, mine
                    else:
                        new_ok = set(LAWS)
                    self.assertEqual(sorted(set(n) - set(o) - new_ok), [], f)
                    self.assertEqual({k: n.get(k) for k in o if k not in new_ok},
                                     {k: v for k, v in o.items() if k not in new_ok}, f)
                f = "gen/M3/par_lossy/header_length.json"
                if f in paths:
                    o, n = at(parent, f), at(c, f)
                    strip = lambda d: {**d, "inputs": [i for i in d["inputs"] if i["path"] != "gen/M3/evidence.json"]}
                    self.assertEqual(strip(n), strip(o), f)
        new = {e["law_id"] for e in (at(end, "laws/M3/DERIVATION.json") or {}).get("laws", [])}
        self.assertEqual(sorted(set(LAWS) - new), [])

    def test_r5_earlier_records_in_stamps_alone(self):
        """I67-R5 (Y11): an own commit that changes a record of results/M1, results/M2 or results/T32 leaves it equal
        to its parent's version but for generator_sha256 and keys named seconds (holon run --milestone M1 and M2, holon
        profile --milestone T32, then the filter stage writing the filter fields back); no own commit changes a file
        under laws/M0, results/M0, gen/M0 or replay/M0."""
        item(KEY, "I67-R5")
        own, _, _ = own_commits()
        self.assertTrue(own, "no commit of I67's after its prereg")
        for c, paths in sorted(own.items()):
            parent = git("rev-parse", f"{c}^1").strip()
            with self.subTest(commit=c[:12]):
                self.assertEqual([f for f in paths if re.match(r"^(laws|results|gen|replay)/M0/", f)], [])
                for f in paths:
                    if re.match(r"^results/(M1|M2|T32)/L[^/]*\.json$", f):
                        o, n = at(parent, f), at(c, f)
                        if o is not None and n is not None:
                            self.assertEqual(_unstamped(n), _unstamped(o), f)


if __name__ == "__main__":
    unittest.main()
