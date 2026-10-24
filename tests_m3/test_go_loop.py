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
   config extracts byte for byte what it extracts at the base (every spec/M2/facts/*.go.extracted.json from
   spec/M2/lib/go_frontend.json). A 0.2 config writes extraction.frontend_version holon-go/0.2 and adds, to the entry of
   every function that is codec-shaped (holon.frontends.go.analyses.Analysis.codec_shaped, unchanged) and has a loop of
   kind counted or range with an induction phi, a fuel and step 1, the key loop_bodies: one entry per such loop, in
   header order, {"span", "iv", "init", "step", "cmp", "limit", "fuel", "exits", "paths"}. The first eight are what the
   loop's go.loops entry holds; paths are the loop-free paths of one iteration over the symbolic induction variable
   ["iv", <iv>]: the blocks before the loop run as in the function's path enumeration, the header binds the induction
   variable with init <= iv assumed, the header's own test forks the body from the exit, a jump back to the header
   ends a path "continue", the exit flows on to the function's return ("return", with its returns), and a bound site
   the reasoner cannot prove safe ends a path "panic" with its site id, by the enumeration's own rule. A path is
   {"cond": [atom], "end": "panic" | "return" | "continue", "returns": [term] | null, "site": site id | null}. No other
   key of a document changes meaning.
Y2 The M3 document. spec/M3/lib/go_frontend.json (config 0.2; one document, morph_blob, of morph-l2/common/batch and
   morph-l2/common/blob; source, primitives and limits as spec/M2/lib/go_frontend.json's) and
   `python -m holon extract go --milestone M3` write spec/M3/facts/morph_blob.go.extracted.json, byte for byte what
   holon.gate's G1 re-extracts (unchanged code: it covers M3 because spec/M3/lib/link.json exists). What its two
   RetrieveBlobBytes entries hold is prediction I67-P6.
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
   "R_" followed by the op's result types joined by "_", each written as an identifier: a leading "[]" as "Slice", a
   leading "*" as "Ptr", then the last name segment with its first letter upper-cased ([]byte, error: R_SliceByte_Error).
   `holon codecs --milestone M3` writes gen/M3/goops/<component>.json beside gen/M3/codec/ (whose files do not change),
   removes a stale one, and --check covers both. holon/diagram/goops.py holds no target name: every name comes from the
   sidecar and the document.
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
   unchanged); no other level (an op has no layout and no machine). Every other model and atom of gen/M3/evidence.json
   stays as it is.
Y5 Derivation. `holon derive --milestone M3` reads the Go-op components with the linked codec layer, each document,
   diagram and the evidence set byte for byte what holon codecs, holon diagram and holon evidence write now (else
   refused: a stale input), and runs the catalog's PAR producers over each component's diagram and atoms, as they are
   (holon.rules.par changes in no line). Over blob_ops that gives the laws expected_laws gives (prediction I67-P5),
   each with rule PAR and facts gen/M3/goops/blob_ops.json, and the cycle basis element of the component's non-tree
   edge is a duplicate of the weak law. The rule catalog version does not change.
Y6 The model. holon.gen.goloop.generate(doc, sha) is gen/M3/model/<component>.bend (holon run writes it), from the
   Go-op document alone: a type Out with constructors OPanic, OErr and ORet (a panic, a non-nil error, a nil error);
   per op a function <op> over the cell sequence List<&2, U32>, ok_<op>(b) = not is_panic(<op>(b)), and eq_out and
   eq_bool. An op's model is its one loop body: the iterations consume the cell sequence one node per iteration (cell k
   is the array cell the body reads at iteration k, blob[a*k + c] for its affine read with constants a and c of the
   document), the induction variable is a Nat, an open bound site a*iv + c' < C is the Nat threshold
   ceil((C - c') / a) compared with the induction variable, and no U32 arithmetic is done per iteration. The fuel is the
   loop's trip count. An op outside this class (no loop body, more than one loop, a path reading more than one cell, a
   non-affine index, a predicate other than a comparison of the cell with a constant) is Unsupported: the laws naming
   it are UNKNOWN, with the reason. holon/gen/goloop.py names no target.
Y7 Deciding. holon run decides a law whose facts is a Go-op document through holon.codecrun (a third kind, goops).
   Candidates, in order: per op of the component, by model name, its model's smallest panic witness (the first
   iteration k from the loop's init at which a panic path's conditions hold: cells before k at the continue path's
   cell value, cell k at the panic path's, cells after k at the continue value, n cells, n the trip count); then the n
   continue values. A law is REFUTED at the first candidate whose counter-law (the claim's negation at the candidate:
   eq_out or eq_bool of the two sides is False) bend accepts at its acceptance point (holon.mpipeline.accepted) and
   BendTT --verdict checks; its witness is {"b": "0x" + the n cells, one byte each, in hex} and its difference
   {"lhs", "rhs"} the sides' values at it ("OPanic", "OErr", "ORet"; true, false). A law no candidate refutes is
   UNKNOWN, its bound naming the candidates and that a forall law over cell sequences has no proof route here (gap G6):
   there is no proof generator for these laws. The witness comes from the compiled model, never from the instrument or
   the real code.
Y8 Records. results/M3/<law id>.json per law over a Go-op document is holon.codecrun.decide's record (v1 and v2
   fields; evidence fields from gen/M3/evidence.json; the lean4 kernel entry as for any codec law of M3), status per
   Y7, kernel verdict checked when REFUTED, replay per Y9. Laws over other documents are decided as before.
Y9 Replay. `holon replay-go --milestone M3` concretizes the witness of every REFUTED record of a Go-op law: the carrier
   value whose array cell blob[a*k + c] (Y6's read) is cell k of the witness and whose every other byte is 0. It runs
   each op the law names on it under recover(), from a Go test it generates from the Go-op document (the ops' function
   ids and the carrier's type) on a scratch copy of the pinned morph checkout (config replay.morph), and writes
   replay/M3/goops/report.json {"milestone", "morph_commit", "go_version", "laws": {law id: {"go": {"status": "passed"
   | "failed" | "not_run", "provenance": "library_api", "obstruction_observed", "observed": {op: real outcome},
   "expected": {op: model outcome}, "command"}}}, "witness_sha256": {law id: holon.replay.witness_sha256(witness)}}. A
   side passes, with obstruction_observed true, iff every op's real outcome class (nil error ORet, non-nil error OErr,
   panic OPanic) is the model's at the witness. holon run re-applies the report to the records
   (holon.replay.replay_status).
Y10 Filter. holon.refute_m3.i4_sides also reads replay/M3/goops/report.json (key "M3/<law id>"), so `holon refute
   --milestone M3 --only filter` sees a Go-op record's side: kind go_only (rule K2), concretization reason the node-level
   path I39 builds, and final bin pending (holon.filter.final_bin's F4, unchanged).
Y11 Regenerated, never hand-written: spec/M3/facts/morph_blob.go.extracted.json (holon extract go), gen/M3/goops/
   (holon codecs), gen/M3/diagram/blob_ops.json (holon diagram), gen/M3/evidence.json (holon evidence), laws/M3/
   (holon derive), gen/M3/model/blob_ops.bend, the four laws' law and proof directories and records (holon run over
   those laws), replay/M3/goops/report.json (holon replay-go), then the four records again (holon run) and their bins
   (holon refute --only filter). No other M3 record is re-made: they trail I67's generator closures until the next M3
   re-make, as I66's did (generator_sha256 is not compared for M3).
Y12 Coordination. I28's build holds holon-rules/1.6; I67 needs no catalog. Whichever of I67 and I28 merges second
   re-derives laws/M3 and re-makes what changes.

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
        """I67-R1 and Y1: the M2 sidecar (config 0.1) extracts the six committed M2 Go documents byte for byte."""
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
                    for p in lb["paths"]:
                        self.assertEqual(sorted(p), ["cond", "end", "returns", "site"])
                        self.assertIn(p["end"], ("panic", "return", "continue"))
                        self.assertEqual(p["site"] is not None, p["end"] == "panic")
                        self.assertEqual(p["returns"] is not None, p["end"] == "return")
        self.assertGreater(n, 0)

    def test_p6_the_two_loop_bodies(self):
        """I67-P6: the batch clone's loop body (4096 iterations from 0) has exactly one panic path, at the site the 0.1
        sites section holds open for that function (I18's data[i*32] at blob.go:49, witness i from 3968 to 4095); the
        blob clone's has no panic path and its sites are all safe."""
        item(KEY, "I67-P6")
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
        old = json.loads(git("show", f"{prereg_commit()}:gen/M3/evidence.json"))
        self.assertEqual({k: v for k, v in ev["models"].items() if k != COMP}, old["models"])
        self.assertEqual([a for a in ev["atoms"] if a["model"] != COMP], old["atoms"])


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
        old = json.loads(git("show", f"{prereg_commit()}:laws/{M}/REGISTRY.json"))
        new = load_json(ROOT / "laws" / M / "REGISTRY.json")
        self.assertEqual(new.get("rule_catalog_version"), old.get("rule_catalog_version"))
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
        self.assertIsNone(re.search(r"U32\.(add|sub|mul|div|mod)\b", text))


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
                self.assertEqual(side["observed"], {op: I.outcome_class(got[op]) for op in side["observed"]})
                self.assertEqual(side["observed"], side["expected"])

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
        """I67-R2: I67's own commits change, under laws/M3, results/M3 and gen/M3, only the four laws and records,
        their law and proof directories, gen/M3/goops/, gen/M3/diagram/blob_ops.json, gen/M3/model/blob_ops.bend,
        gen/M3/evidence.json, laws/M3/REGISTRY.json and laws/M3/DERIVATION.json; and every other law's DERIVATION entry
        (statement hash included) is the one at the prereg."""
        item(KEY, "I67-R2")
        own, end, pre = own_commits()
        self.assertTrue(own, "no commit of I67's after its prereg")
        allowed = {f"laws/M3/{lid}.json" for lid in LAWS} | {f"results/M3/{lid}.json" for lid in LAWS} | {
            "gen/M3/diagram/blob_ops.json", MODEL, "gen/M3/evidence.json", "laws/M3/REGISTRY.json",
            "laws/M3/DERIVATION.json"}
        prefixes = ("gen/M3/goops/",) + tuple(f"gen/M3/{d}/{lid}/" for d in ("laws", "proofs") for lid in LAWS)
        changed = sorted({f for paths in own.values() for f in paths})
        bad = [f for f in changed if re.match(r"^(laws|results|gen)/M3/", f) and f not in allowed
               and not f.startswith(prefixes)]
        self.assertEqual(bad, [])
        old = {e["law_id"]: e for e in json.loads(git("show", f"{pre}:laws/M3/DERIVATION.json"))["laws"]}
        new = {e["law_id"]: e for e in json.loads(git("show", f"{end}:laws/M3/DERIVATION.json"))["laws"]}
        self.assertEqual(sorted(set(new) - set(old)), sorted(LAWS))
        self.assertEqual({k: new[k] for k in old}, old)


if __name__ == "__main__":
    unittest.main()
