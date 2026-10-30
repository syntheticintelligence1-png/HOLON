"""I85 (= I39a): the Go derivation extracted, with ParseBatch as an extracted consumer, and the product machine joining
the Solidity commit with Go derivation, refined against a Go replay; no law (whitepaper §5.1 consumer and cycle, §5.5,
F11; §10.1 Go; §8.7 refinement; BUILD_PLAN I39 and row I85). This docstring is the contract; its sha256 is the key's
thresholds.contract_docstring_sha256.

Scope. BUILD_PLAN I39 predicts O7, the O8 law pair under HypC, O24 and the F11 L1-count law. Its laws need the extracted
consumer and the product machine; extracting and refining them needs no law, so they go first, under their own key, as
I69 (= I36a) and I80 (= I37a) did. I85 states no law, changes no rule catalog, adopts no document into M3's derivation
(spec/M3/lib/derive_extracted.json does not change), adds no coverage entry and changes no file of any generator closure,
so no record is re-made. I39 keeps its number for the laws.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and a line in spec/M3/amendments.jsonl):
tests_m3/_i85.py (the rules below written a second time, independently of holon/, over tests_m2/_keccak.py);
spec/M3/lib/derivation.json (the sidecar: the target vocabulary, the environment boundary, the product's wiring and
environment, and the corpus, rule C1; no outcome). The key's thresholds pin both and this docstring by sha256.

Inputs, read and never written: I18's Go frontend config spec/M2/lib/go_frontend.json and document
spec/M2/facts/morph_derivation.go.extracted.json; the adopted Rollup document spec/M2/facts/morph_rollup.extracted.json;
I80's deployment record replay/M3/bundle2/deployment.json (I20's deployment, the Rollup's storage after it); the target
checkout (config/holon.json replay.morph) at the sidecar's commit, copied to a scratch workspace and never written; the
Go module cache.

Extraction (D1-D6; `holon derivation extract`)
  D1 The document spec/M3/facts/morph_derivation.extracted.json is the I18 frontend's document of the sidecar's
     extract.document stem under extract.frontend_config (holon.frontends.go: one ssadump run of every package of that
     config, its analyses unchanged), with one added top-level key, "consumer" (D2-D5), computed from the same ssadump
     run. Less "consumer", it is the frontend's document byte for byte (rendered by holon.frontends.go.render).
  D2 The closure: from extract.consumer, every function reached by a static call (Call, Go or Defer of mode static) or a
     MakeClosure whose body the ssadump run holds, except the functions extract.environment names. consumer.functions
     maps each to its SSA as dumped: {"package", "pos", "params", "freevars", "results", "blocks": [{"index", "preds",
     "succs", "instrs"}]} (instrs as ssadump prints them). consumer.join: {"function": extract.join, "ssa": its SSA}.
  D3 The environment: consumer.environment lists every static callee of the closure outside it, sorted by function,
     each {"function", "kind", "sites"} with kind "oracle", "slice_len" or "encoding" when extract.environment names it
     (its declared kind), "native" when holon/derivation's table of Go standard-library semantics holds it, else
     "unaccounted"; consumer.builtins the builtins called, consumer.invokes the interface calls [caller, method, pos],
     consumer.globals every global the closure reads {"global", "kind", "value"}: "initialized" with the frontend's
     go.globals value term when a package initializer of the run assigns it, "native" for a standard-library global the
     table holds, else "unaccounted".
  D4 consumer.coverage: {"functions", "instructions", "unaccounted": [{"function", "pos", "what"}]}: an instruction op
     the interpreter (G1) does not evaluate, an unaccounted callee, builtin or global is listed, never dropped.
     consumer.types holds every type the closure's SSA mentions, transitively, as ssadump prints it; consumer.package
     the entry's package {"path", "name", "dir"}; consumer.entry the entry; consumer.consumer_version
     "holon-derivation-consumer/0.1".
  D5 The read set: the field paths of the entry's batch parameter (extract.consumer_param) the entry reads: Field
     chains on the parameter, or FieldAddr chains on a local the parameter is stored into (tests_m3/_i85.py::reads).
  D6 holon/derivation/ names no target: every package, function, type, field or family comes from the sidecar, the
     documents or the ssadump output; it names only the Go standard library; it imports no test module, and no file of
     it is in a generator closure.

The join and the product machine (J1-J3, K1-K5; `holon derivation product`; evaluator-level)
  J1 The join rows: for each member m of the commit parameter (product.commit_param of product.commit_action in the
     Rollup document), [m, the member's name with its first letter capitalized (the Go struct field the derivation's ABI
     decoder fills), the batch field a store of the join function writes from that Go field (tests_m3/_i85.py::join:
     a store into a field of a local of product.batch_type, its value traced back through conversions, loads, slices
     and one-argument static calls to a field read) or null].
  J2 The derived batch of a commit: the batch type's value whose joined fields hold the commit's members (Go field
     names; bytes as hex, integers as numbers), whose product.blobs_field holds the commit's blobs, every other field
     zero.
  J3 The cycle edge: a commit's header is the bytes of the argument of the keccak256 that the commit action's write to
     product.header_family stores, evaluated by holon.extracted_eval's Eval after the step's run (its loop bindings
     kept); its keccak256 must be the word the step writes there. The next commit's parent header is that header; the
     first commit's parent is product.genesis.
  K1 Traces: the sidecar's corpus.product traces; each starts from the deployment record's member storage (I80's).
  K2 A commit step runs holon.extracted_eval on the Rollup document's commit action with the commit's members (version,
     parent header (J3), lastBlockNumber, numL1Messages 0, prevStateRoot the parent's postStateRoot (the genesis's from
     the deployment's committed state root), postStateRoot, withdrawalRoot) and env: caller the actor, this the member's
     address, msg.value 0, msg.data.length the call's ABI length, block.timestamp product.timestamp.first + 12 per step,
     blobhash the commit's blobs' stand-in hashes (0x01 followed by bytes 1..31 of the blob's sha256), calls answered as
     product.calls says ("true": ok with the word 1; "timestamp": ok with the step's timestamp).
  K3 A commit that succeeds moves the state by its writes and is derived (K4); a failure is recorded and ends the trace.
  K4 Derivation: the derived batch (J2) of every committed batch is a corpus case of source "product" (id
     "<trace>/<k>"), evaluated and compared like every other case (G, C4).
  K5 gen/M3/derivation/product.json: {"product_version": "holon-derivation-product/0.1", "sidecar": {"path",
     "sha256"}, "document": {"path", "sha256"}, "rollup_document": {"path", "sha256"}, "deployment": {"path", "sha256"},
     "join": J1's rows, "environment": the consumer's environment functions and kinds, "traces": [{"id", "commits":
     [{"k", "version", "status", "index", "header", "hash", "written", "parent", "batch": J2's value or null, "reason"}]}]}.

Evaluation and the Go replay (G1-G5)
  G1 The consumer model: an interpreter of consumer.functions (holon/derivation), run on the derived batch from a zero
     receiver: Go semantics for every op it evaluates (integers wrap at their type's width, division truncates, slices
     share backing arrays and append grows a fresh one past capacity, the slicing of a nil slice is nil, struct and
     array values copy, interface values carry their dynamic type), Go's runtime panics with their runtime texts
     (index and slice bounds, nil dereference, division by zero, makeslice), and "unsupported" (never a guess) for
     anything else.
  G2 Natives: the standard library functions of the table (fmt.Errorf's and errors.New's texts, bytes.NewReader,
     encoding/binary's Read and byte orders, math/big's integers) with their Go semantics.
  G3 Environment: an "oracle" function is answered by the real library: the generated Go helper runs it on the call's
     argument in the scratch workspace (results "bytes": the bytes or the error's text; "encodings": the list's
     elements' encodings, their nilness, or the error's text); "slice_len" is a slice's length; "encoding" an oracle
     element's encoding. results/M3/derivation/environment.json records every answer {function: {sha256 of the
     argument: answer}}, so `refine --check` re-evaluates without Go.
  G4 The Go replay: a test generated from the sidecar and the document (no hand-written Go), placed in the entry's
     package of a scratch copy of the pinned checkout, builds each case's batch by reflection from its Go field names,
     calls the entry on a new receiver under recover and records status ("ok", "error", "panic"), the error's text, the
     panic's text and the receiver's dump (G5). replay/M3/derivation/report.json: {"report_version":
     "holon-derivation-replay/0.1", "morph_commit", "go_version", "command", "cases": {id: outcome}}.
  G5 The dump of a value, by its type: booleans, integers and strings as JSON; byte arrays, byte slices and their named
     types as "0x" hex (a nil slice null); other arrays and slices as lists (nil null); structs as objects of every
     field by name; pointers null or the pointee's dump, *math/big.Int as {"big": decimal}; interfaces null or
     {"error": text}.

Corpus and comparison (C1-C5)
  C1 The corpus: the sidecar's corpus section (tests_m3/_i85.py::corpus at the prereg): planted cases (inputs chosen to
     end at each return of the entry), random cases (well-formed batches with at most one mutation) and the product
     traces (K1).
  C2 Payload segments: "0x.." bytes, or ["stream", seed, n] (tests_m3/_i85.py::stream). A case's blobs: the payload
     ("raw" segments compressed by extract.compressor through the real library; "compressed" used as given) packed
     canonically into blob j's field element k (32 bytes: a zero byte, then bytes 31(4096j + k) .. +31 of the data,
     zero padded), then the case's "set" overrides [blob, byte, value].
  C3 `holon derivation corpus` writes gen/M3/derivation/corpus.json: {"corpus_version": "holon-derivation-corpus/0.1",
     "sidecar": {"path", "sha256"}, "cases": [{"id", "source", "batch" (Go field names), "data": [hex of each
     case's packed data], "set"}], "product": [{"id", "commits": [{"k", "data", "blobs"}]}]}.
  C4 `holon derivation refine` evaluates every planted, random and product case on the model (G1-G3) and on the Go
     replay (G4) and compares status, error text, panic text and the receiver's dump; a difference, or an unsupported
     model step, is a disagreement. results/M3/derivation/steps.json: {"steps": [{"id", "source", "model": {"status",
     "error", "panic", "info", "site", "reason"}, "real": {"status", "error", "panic", "info"}, "agree"}]}, site the
     position of the instruction that ended the entry (its Return, or the panicking instruction).
  C5 results/M3/derivation/refinement.json: {"refinement_version": "holon-derivation-refinement/0.1", "corpus": {"path",
     "sha256"}, "cases": {source: n}, "agree", "disagreements": [ids], "unsupported": [ids], "sites": {file:line: n},
     "panics": {text: n}, "toolchain"}; results/M3/derivation/disagreements.json lists each disagreement with both
     sides. `refine --check` re-runs the model only (the recorded environment answers), never Go, and must reproduce
     steps.json's model sides and refinement.json.

Shared files, changed only so (not outcome paths): new modules under holon/derivation/ and holon/__main__.py's dispatch;
no file of the closures pinned in thresholds.closures, so no record under results/ but results/M3/derivation/ changes.

Own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
docs/iterations/I85.md (HEAD while none does). Commit rules (I85-R2): at least one adds
spec/M3/facts/morph_derivation.extracted.json; none changes a frozen root, laws/, spec/ other than that document,
holon/rules/, holon/frontends/, a file of thresholds.closures, a file under replay/ outside replay/M3/derivation/, a file
under gen/ outside gen/M3/derivation/, or a file under results/ outside results/M3/derivation/.

Earlier tests amended at this prereg: none. I85 adopts no document, adds no rule, law, catalog or coverage entry, moves
no generator closure and writes under new paths only. One that fails on I85's outcomes is a miss, reported.

Commands
  python -m holon derivation extract|corpus|product|refine [--check]
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input, no Go
  toolchain at the pinned version, a checkout not at the sidecar's commit), nothing written; 3 an extraction, product or
  replay error, nothing written. Outputs are canonical JSON (sorted keys, indent 1, a final newline), byte-identical
  across runs, with no timestamps and no absolute paths. extract and corpus run Go (the frontend's helper, the
  compressor); product runs none; refine runs the Go replay and the oracle, and refine --check runs no Go.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, holon_module, load_json, predictions, run_holon

KEY = "I85"
SIDE = ROOT / "spec" / "M3" / "lib" / "derivation.json"
DOC = ROOT / "spec" / "M3" / "facts" / "morph_derivation.extracted.json"
M2DOC = ROOT / "spec" / "M2" / "facts" / "morph_derivation.go.extracted.json"
ROLLUP_DOC = ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json"
CORPUS = ROOT / "gen" / "M3" / "derivation" / "corpus.json"
PRODUCT = ROOT / "gen" / "M3" / "derivation" / "product.json"
REF = ROOT / "results" / "M3" / "derivation" / "refinement.json"
STEPS = ROOT / "results" / "M3" / "derivation" / "steps.json"
DIS = ROOT / "results" / "M3" / "derivation" / "disagreements.json"
ENVA = ROOT / "results" / "M3" / "derivation" / "environment.json"
REPORT = ROOT / "replay" / "M3" / "derivation" / "report.json"
_CACHE: dict = {}


def th() -> dict:
    return predictions(KEY)["thresholds"]


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i85 as I
    return I


def section() -> dict:
    if "section" not in _CACHE:
        d = need(DOC)
        if "consumer" not in d:
            raise AssertionError("the document has no consumer section")
        _CACHE["section"] = d["consumer"]
    return _CACHE["section"]


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I85 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            d = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(d, dict) and KEY in (d.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I85")


def own_commits() -> list:
    """I85's own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
    docs/iterations/I85.md (HEAD while none does), oldest first, each with its (status, path) pairs."""
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", "docs/iterations/I85.md").split()
    end = added[0] if added else "HEAD"
    commits, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-status",
                  f"{prereg_commit()}..{end}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            commits.append(cur)
        elif ln.strip() and cur is not None:
            st, path = ln.split("\t", 1)
            cur[1].append((st[0], path.strip()))
    return commits


def holon_ok(args: list, timeout: int = 7200):
    p = run_holon(args, timeout=timeout)
    return p.returncode, (p.stdout[-1500:] + p.stderr[-1500:])


def closures(root: Path = ROOT) -> list:
    """Every file of the generator closures at root (holon modules imported here, inside the call)."""
    rec = holon_module("holon.records")
    run3 = holon_module("holon.sorts.run3")
    out = set()
    for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
        out |= set(rec.generator_files(v, root))
    starts = [list(run3.GEN3)]
    for mod, name in (("holon.fact.run", "GEN_FACT"), ("holon.undo.run", "GEN_UNDO"), ("holon.disch.run", "GEN_DISCH")):
        starts.append(list(getattr(holon_module(mod), name)) + list(run3.GEN3))
    for start in starts:
        seen, todo = set(), list(start)
        while todo:
            r = todo.pop()
            if r in seen or not (root / r).is_file():
                continue
            seen.add(r)
            if r.endswith(".py"):
                todo.extend(sorted(rec._holon_imports(r, root) - seen))
        out |= seen
    out |= set(holon_module("holon.profile").generator_files(root))
    return sorted(out)


def steps() -> dict:
    if "steps" not in _CACHE:
        _CACHE["steps"] = need(STEPS)
    return _CACHE["steps"]


# ---------------------------------------------------------------------------------------------- instruments
class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(SIDE), t["sidecar_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i85.py"), t["instrument_sha256"])
        d = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(d.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        for rel, sha in t["inputs_sha256"].items():
            self.assertEqual(file_sha256(ROOT / rel), sha, rel)

    def test_the_corpus_and_the_genesis_are_the_instruments(self):
        side = need(SIDE)
        I = instrument()
        self.assertEqual(side["corpus"], json.loads(json.dumps(I.corpus())))
        self.assertEqual(side["product"]["genesis"], I.hx(I.genesis(ROOT)))

    def test_the_consumer_source_has_the_predicted_returns(self):
        """The predicted reached and dead returns are exactly the return statements of the consumer's body."""
        t = th()["sites"]
        got = [r[0] for r in instrument().returns(ROOT)]
        self.assertEqual(sorted(got), sorted(t["reached"] + t["dead"]))
        self.assertEqual(set(t["reached"]) & set(t["dead"]), set())


# ---------------------------------------------------------------------------------------------- extraction
class TestExtraction(unittest.TestCase):
    def test_p1_the_consumer_is_extracted_as_read(self):
        """I85-P1 (D1-D4)."""
        t = th()
        d = need(DOC)
        rest = {k: v for k, v in d.items() if k != "consumer"}
        self.assertEqual(rest, need(M2DOC), "less its consumer key, the document is I18's derivation document")
        sec = section()
        self.assertEqual(sec["consumer_version"], "holon-derivation-consumer/0.1")
        self.assertEqual(sec["entry"], need(SIDE)["extract"]["consumer"])
        self.assertEqual(sorted(sec["functions"]), t["closure"])
        env = {e["function"]: e["kind"] for e in sec["environment"]}
        self.assertEqual(env, t["environment"])
        self.assertNotIn("unaccounted", set(env.values()))
        self.assertEqual([g for g in sec["globals"] if g["kind"] == "unaccounted"], [])
        self.assertEqual(sec["coverage"]["unaccounted"], [])
        self.assertEqual(sec["coverage"]["functions"], len(t["closure"]))
        fns, envs = instrument().closure(sec)
        self.assertEqual(fns, t["closure"], "the instrument's closure")
        self.assertEqual(envs, sorted(t["environment"]), "the instrument's environment")
        self.assertEqual(sec["join"]["function"], need(SIDE)["extract"]["join"])

    def test_p3_the_consumer_reads(self):
        """I85-P3 (D5): the read set of the batch parameter, and the fields it never reads."""
        t = th()
        got = instrument().reads(section(), need(SIDE)["extract"]["consumer_param"])
        self.assertEqual(got, t["reads"])
        top = {r.split(".")[0] for r in got}
        self.assertEqual(top & set(t["unread"]), set())
        bt = section()["types"][need(SIDE)["product"]["batch_type"]]
        fields = {f["name"] for f in section()["types"][bt["underlying"]]["fields"]}
        self.assertEqual(fields, top | set(t["unread"]))


# ---------------------------------------------------------------------------------------------- the product
class TestProduct(unittest.TestCase):
    def test_p2_the_join_is_as_read(self):
        """I85-P2 (J1)."""
        t = th()
        prod = need(PRODUCT)
        self.assertEqual(prod["join"], t["join"])
        self.assertEqual(instrument().join_rows(section(), need(SIDE), need(ROLLUP_DOC)), t["join"])

    def test_p4_the_product_commits_and_closes_the_cycle(self):
        """I85-P4 (J2, J3, K1-K5)."""
        side = need(SIDE)
        prod = need(PRODUCT)
        I = instrument()
        plans = {p["id"]: p for p in side["corpus"]["product"]}
        self.assertEqual(sorted(tr["id"] for tr in prod["traces"]), sorted(plans))
        by_id = {s["id"]: s for s in steps()["steps"]}
        for tr in prod["traces"]:
            plan = plans[tr["id"]]
            self.assertEqual(len(tr["commits"]), len(plan["commits"]), tr["id"])
            parent = side["product"]["genesis"]
            for k, (c, p) in enumerate(zip(tr["commits"], plan["commits"])):
                with self.subTest(trace=tr["id"], k=k):
                    self.assertEqual(c["status"], "ok", c.get("reason"))
                    self.assertEqual(c["index"], k + 1)
                    self.assertEqual(c["parent"], parent)
                    self.assertEqual(int(c["written"], 16), int.from_bytes(I.keccak(bytes.fromhex(c["header"][2:])), "big"))
                    s = by_id[f"{tr['id']}/{k + 1}"]
                    self.assertTrue(s["agree"], s["id"])
                    if p["version"] == 0:
                        self.assertEqual((s["real"]["status"], s["real"]["error"]), ("error", th()["product_v0_error"]))
                    else:
                        self.assertEqual(s["real"]["status"], "ok")
                        self.assertEqual(s["real"]["info"]["batchIndex"], k + 1)
                    parent = c["header"]


# ---------------------------------------------------------------------------------------------- refinement
class TestRefinement(unittest.TestCase):
    def test_p5_the_consumer_refines_the_real_parsebatch(self):
        """I85-P5 (G1-G5, C4-C5)."""
        t = th()
        rec = need(REF)
        rc = instrument().recount(steps())
        self.assertEqual(rc["by_source"], t["cases"])
        self.assertEqual(rec["cases"], t["cases"])
        self.assertEqual(rc["disagree"], [])
        self.assertEqual(rc["unsupported"], [])
        self.assertEqual(rec["disagreements"], [])
        self.assertEqual(rec["unsupported"], [])
        self.assertEqual(rec["agree"], rc["agree"])
        self.assertEqual(rec["sites"], rc["sites"])
        self.assertEqual(rec["panics"], rc["panics"])
        rep = need(REPORT)
        self.assertEqual(sorted(rep["cases"]), sorted(s["id"] for s in steps()["steps"]))
        self.assertEqual(rep["morph_commit"], need(SIDE)["target"]["commit"])
        for s in steps()["steps"]:
            self.assertEqual(s["real"], rep["cases"][s["id"]], s["id"])

    def test_p6_the_corpus_reaches_every_live_return(self):
        """I85-P6 (C4-C5): every live return of the entry ends an agreeing case, no dead one does, and the blob decoder's
        panic is reached."""
        t = th()["sites"]
        rc = instrument().recount(steps())
        for site in t["reached"]:
            self.assertGreaterEqual(rc["sites"].get(site, 0), 1, site)
        for site in t["dead"]:
            self.assertEqual(rc["sites"].get(site, 0), 0, site)
        self.assertGreaterEqual(rc["panics"].get(t["panic"], 0), 1)


# ---------------------------------------------------------------------------------------------- construction
class TestConstruction(unittest.TestCase):
    """The outputs reproduce (rules D1, C3, K5, C5's --check)."""

    def test_the_outputs_reproduce(self):
        for cmd in ("extract", "corpus", "product", "refine"):
            with self.subTest(cmd=cmd):
                rc, out = holon_ok(["derivation", cmd, "--check"])
                self.assertEqual(rc, 0, out)

    def test_the_records_name_their_inputs(self):
        cor = need(CORPUS)
        self.assertEqual(cor["sidecar"], {"path": "spec/M3/lib/derivation.json", "sha256": file_sha256(SIDE)})
        prod = need(PRODUCT)
        self.assertEqual(prod["document"]["sha256"], file_sha256(DOC))
        self.assertEqual(need(REF)["corpus"], {"path": "gen/M3/derivation/corpus.json", "sha256": file_sha256(CORPUS)})
        self.assertTrue(ENVA.is_file())
        self.assertTrue(DIS.is_file())


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_the_go_documents_regenerate(self):
        """I85-R1: I18's five documents and I67's M3 document re-extract byte for byte with their configs."""
        import tempfile
        for m, stems in (("M2", ("morph_batch", "morph_blob", "morph_derivation", "morph_genesis", "morph_nodetypes")),
                         ("M3", ("morph_blob",))):
            with tempfile.TemporaryDirectory(prefix="holon-i85-r1-") as tmp:
                rc, out = holon_ok(["extract", "go", "--milestone", m, "--out-dir", tmp])
                self.assertEqual(rc, 0, out)
                for s in stems:
                    with self.subTest(milestone=m, stem=s):
                        self.assertEqual((Path(tmp) / f"{s}.go.extracted.json").read_bytes(),
                                         (ROOT / "spec" / m / "facts" / f"{s}.go.extracted.json").read_bytes())

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I85-R2."""
        closed = set(th()["closures"])
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                  "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")
        doc = "spec/M3/facts/morph_derivation.extracted.json"
        added_doc = False
        for c, changes in own_commits():
            for st, path in changes:
                with self.subTest(commit=c[:12], path=path):
                    if path == doc and st == "A":
                        added_doc = True
                    self.assertFalse(path.startswith(frozen), "a frozen root")
                    self.assertFalse(path.startswith("laws/"), "laws/")
                    self.assertFalse(path.startswith("spec/") and path != doc, "spec/")
                    self.assertFalse(path.startswith(("holon/rules/", "holon/frontends/")), "rules or frontends")
                    self.assertNotIn(path, closed, "a file of a generator closure")
                    for top, mine in (("replay/", "replay/M3/derivation/"), ("gen/", "gen/M3/derivation/"),
                                      ("results/", "results/M3/derivation/")):
                        if path.startswith(top):
                            self.assertTrue(path.startswith(mine), f"{top} outside {mine}")
        if own_commits():
            self.assertTrue(added_doc, "no own commit adds the derivation document")

    def test_r3_the_prereg_audits_pass(self):
        """I85-R3 (the local part: both audits)."""
        for m in ("M2", "M3"):
            with self.subTest(milestone=m):
                rc, out = holon_ok(["audit", "prereg", "--milestone", m])
                self.assertEqual(rc, 0, out)

    def test_r4_holon_derivation_is_generic_and_outside_every_closure(self):
        """I85-R4 (D6)."""
        pkg = ROOT / "holon" / "derivation"
        self.assertTrue(pkg.is_dir(), "holon/derivation/ is missing")
        words = th()["forbidden"]
        for p in sorted(pkg.rglob("*.py")):
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=p.name):
                self.assertNotRegex(text, r"(?m)^\s*(from|import)\s+tests", "imports a test module")
                for w in words:
                    self.assertNotIn(w, text, f"names the target: {w}")
                self.assertIsNone(re.search(r"0x[0-9a-fA-F]{40}\b", text), "an address")
        self.assertEqual([f for f in closures(ROOT) if f.startswith("holon/derivation/")], [])


if __name__ == "__main__":
    unittest.main()
