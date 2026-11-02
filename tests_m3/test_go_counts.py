"""I90 (= I38b): O28 at 65,536 L1 messages, through the count channels of a Go component (BUILD_PLAN rows I90 and I38;
whitepaper §7.6 width obligations, §5.1 PAR and its branch sub-form, §11.3 O28, Appendix A F12.7). This docstring is the
contract.

Scope. morph-l2/common/batch.BatchData counts the L1 messages of the batch it accumulates twice: Append appends each L1
transaction hash's 32 bytes to l1TxHashes, one per element of its parameter, and adds uint16(len(l1TxHashes)) to the
uint16 field l1TxNum. Once a batch holds 65,536 L1 messages the second count is 0 while the first holds 65,536 hashes
(O28: Σ n_l1 realized in uint16). DataHashV2 hashes both, and the submitter commits l1TxNum as numL1Messages. No law
states it: I20's SORT-width producer reads Solidity layouts and is not in M3's catalog, and I67's Go-op components hold
functions of one parameter. I90 adds count components (C1-C3), a model whose carrier is a parameter's length, a Nat
(parametric counts: no per-element cells), that decides their laws at 65,536 in both kernels (C4-C6), and the replay of
their witnesses on the real code (C7, C8). It changes no rule of PAR, no rule catalog, no frontend and no existing law.
I38's compression half (HypZ, HypZ_len, O5, O6, D3) is I91. D2 (Hyp-Z0-kzg, checked since I3) is a regression.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i90.py and its Go file tests_m3/fixtures/go_counts/holon_i90_instrument.go.txt
(what the real Append leaves in its fields after probe calls; the components, laws and witness of C1, C3 and C5 from the
sidecar, the Go document and its extraction config), written without holon/.

C1 Count components. The sidecar spec/M3/lib/go_counts.json (go_counts_version holon-go-counts/0.1) names a Go document
   and its components, each {"carrier": a Go type, "reach": text}. holon.diagram.gocount builds, per component, a
   holon-gocount/0.1 document. Its channels: for every function F of the document, in id order, whose id is a method of
   a pointer receiver ("(*<path>.<T>).<M>", its first parameter R the receiver) and which has a parameter P of the
   carrier's type, every store fact s of go.slices.stores with function F and target ["field", ["param", R], g] whose
   value is
     (wrap) ["op", "+", ["field", ["param", R], g], ["convert", U, ["len", ["param", P]]]] with U uint8, uint16 or uint32:
            kind "wrap", width 8, 16 or 32 (the length realized in that many bits); or
     (item) ["append", ["field", ["param", R], g], ["call", G, [X]]] with G a primitive of the document's extraction
            config of kind array_bytes or to_array and an integer width k >= 1, X an ["index", ["param", P], J] whose J
            mentions a ["var", <name>, "rangeindex"] term, and F having exactly one go.loops entry of kind range, with
            limit ["len", ["param", P]], init ["const", 0], step 1 and exits []: kind "item", width k (one k-byte item
            per element).
   A function with two parameters of the carrier's type, two channels of one name, or a component with no channel is
   refused (exit 3, nothing written). A channel's name is <F's model name>_<g> (I67's model name: <package>_<type>_
   <method>). Its entry: {"source": F, "params": F's params verbatim, "param": P, "receiver": R, "field": g, "kind",
   "width", "site": s's site, "store": s's value}. The document: {"gocount_version": "holon-gocount/0.1", "component",
   "document": the Go document's path, "document_sha256", "carrier": {"id", "type", "reach"}, "count": "Len_<id>",
   "channels": {name: entry}}; the carrier id is the type written as I67's result-carrier words write a type (every
   leading "[]" as Slice and "*" as Ptr, then the last name segment, first letter upper-cased: SliceHash). `holon codecs
   --milestone M3` writes it to gen/M3/goops/<component>.json beside the Go-op documents (the directory of the Go-level
   components; a document there is a Go-op document or a count document, by its version key), removes a stale one, and
   --check covers it. holon/diagram/gocount.py and holon/gen/gocount.py hold no target name: every name comes from the
   sidecar, the document and its config.
C2 Diagram and evidence. `holon diagram --milestone M3` also writes gen/M3/diagram/<component>.json per count component
   (holon-diagram/0.1; every other diagram unchanged): model the component, facts its gen/M3/goops path, facts_sha256,
   facts_version holon-gocount/0.1; carriers the carrier {"id", "cls": "rep", "base_type": id, "sort_ref": null,
   "interface": false, "reach": "external"} (no domain: no channel is partial or has an error result) and the count
   carrier {"id": "Len_<id>", "cls": "rep", "base_type": "Len_<id>", "sort_ref": null, "interface": false, "reach":
   null}; one edge per channel {"id": "CODEC.<name>", "kind": "CODEC", "model_fn": name, "src": the carrier id, "tgt":
   "Len_<id>", "partial": false, "version": null, "fn_kind": "count", "source": [{"fn": F}], "component": the Go
   document's path, "env": false, "pseudo": false, "principal_class": null, "access": {"reads": [], "writes": []}}.
   `holon evidence --milestone M3` adds one model per count component (facts, facts_sha256, facts_version, diagram and
   anchors: "codec" model_fn -> edge id, every other anchor key empty) and no atom: a channel has no layout (E1, E2) and
   no machine (E3-E5), and two channels of one function are related by P3's own basis, never by name tokens (E6 is
   computed over the linked and Go-op components only). spec/schemas/evidence.schema.json admits facts_version
   holon-gocount/0.1. Every other model and atom of the evidence set stays as it is.
C3 Derivation. `holon derive --milestone M3` reads the count components with the Go-op components, each document,
   diagram and the evidence set byte for byte what holon codecs, holon diagram and holon evidence write now (else
   refused: a stale input), and runs the catalog's PAR producers over each component's diagram and atoms, as they are
   (holon.rules.par changes in no line). Over l1_counts that gives exactly the law expected_laws gives (prediction
   I90-P2): rule PAR, sub-form branch (P3: two channels of one function are two paths of it), facts
   gen/M3/goops/l1_counts.json; and the cycle basis element of the non-tree edge is a duplicate of it. No other producer
   gives a law or a basis element over the component (no atom, no interface carrier, no version). The rule catalog
   does not change: no commit of I90's changes holon.rules' catalogs or laws/M3/REGISTRY.json's rule_catalog_version.
C4 The model. holon.gen.gocount.generate(doc, sha) is gen/M3/model/<component>.bend (holon run writes it), from the
   count document alone: per channel a function <name>(n: Nat) -> Nat, the count the channel's field records after one
   call of its function, from the receiver's zero value, on a parameter of length n: an item channel n (its field holds
   n items); a wrap channel of width w U32.to_nat(U32.and(U32.from_nat(n), 2^w - 1)), which is n mod 2^w for every n
   (2^w divides 2^32); and eq_count(a, b) = Nat.is_eq(a, b) and is_true, untrusted (BEND_PRIMER 5.4). The carrier's model
   is its length (parametric counts): no channel reads an element's value, and no per-element cell is modelled.
   Nothing else is modelled: the function's other parameters and stores, its paths and its panics. holon/gen/gocount.py
   names no target.
C5 Deciding. holon run decides a law whose facts is a count document through holon.codecrun (a fourth kind, gocount).
   Candidates, in order: 2^w for each distinct wrap width w of the channels the law's claim names, ascending, then 0. A
   law is REFUTED at the first candidate whose counter-law (exs x: Nat, the claim's two sides unequal, the motive the
   model's eq_count at the lhs) bend accepts at its acceptance point (holon.mpipeline.accepted); its record's kernel
   verdict is BendTT --verdict's on that proof (prediction I90-P1 says checked). Its witness is {<binder>: n} and its
   difference {"lhs", "rhs"} the two sides' values at n by the compiled model (holon/js/linked.mjs), the instrument's
   semantics a cross-check. A law no candidate refutes is UNKNOWN, its bound naming the candidates and that no proof
   generator covers a law over counts here. A law whose claim is not two channels of the component over the binder is
   UNKNOWN unsearched. The witness comes from the compiled model, never from the instrument or the real code. The
   witness is never re-parametrized to a smaller N: a law the kernel cannot check at its candidate within budget is
   UNKNOWN with the bound recorded.
C6 Records and the gate. results/M3/<law id>.json per law over a count document is holon.codecrun.decide's record (v1
   and v2 fields; evidence fields from gen/M3/evidence.json), status per C5, replay per C7. What the gate checks of such
   a law is made to hold by these changes, each generated: (a) the IR's binder rule takes a count document's carrier id
   as its record type (holon.ir.check_binder_types); (b) its ledger bundle is generated from the count document
   (holon.records): every assumption the Go document declares, introduced by the channels' definitions, and the model's
   own A-gocount-length (a parameter is its length), A-gocount-receiver (one call from the receiver's zero value; the
   other parameters are not modelled) and A-gocount-store (a channel is one store fact, run once per call or once per
   element; the function's paths, other stores and panics are not read), so ledger_match is exact; (c)
   evidence.schema.json admits holon-gocount/0.1 (C2); (d) holon.bindings binds a count law to
   gen/M3/model/<component>.bend and its emission (holon.gen.gocount.emit, as codecrun writes the law file), and
   `holon bind --milestone M3 --laws <the law>` adds its binding to spec/bindings/M3.json, logged as added only; (e) the
   statement hash's refs over a count document (holon.gen.refs) are "fn:<name>" for each channel the claim calls (its
   entry without source and site) and "carrier:<id>" (the carrier's {"id", "type"}). The record carries no lean4 entry
   (no Lean emitter reads a count document) and, when REFUTED, witness_provenance {"go": "library_api"} from
   replay/M3/gocount/report.json.
C7 Replay. `holon replay-go --milestone M3` also concretizes the witness n of every REFUTED record of a count law: from a
   Go test it generates from the count document (an internal test of the channels' package, added to a scratch copy of
   the pinned morph checkout, config replay.morph), it calls each function the law's channels cite once, each on a
   fresh receiver new(T), with the channel's parameter n zero elements and every other parameter its zero value, under
   recover(), and reads each named channel's field: a wrap channel's value, an item channel's length divided by its
   width. It writes
   replay/M3/gocount/report.json {"milestone", "morph_commit", "go_version", "laws": {law id: {"go": {"status": "passed"
   | "failed" | "not_run", "provenance": "library_api", "obstruction_observed", "observed": {channel: count},
   "expected": {channel: count}, "panic": text or null, "command": a text with no absolute or scratch path}}},
   "witness_sha256": {law id: holon.replay.witness_sha256(witness)}}. A side passes, with obstruction_observed true, iff
   nothing panicked and every observed count is the model's at the witness. It stamps the records' replay field and
   witness_provenance from the report, and holon run re-applies both. replay/M3/goops/report.json does not change.
C8 Filter. holon.refute_m3.i4_sides also reads replay/M3/gocount/report.json (key "M3/<law id>", at the record's own
   witness), so `holon refute --milestone M3 --only filter` gives a REFUTED count record kind go_only (rule K2: every
   side a Go library call), reason "node-level public path needs I39", and final bin pending (holon.filter.final_bin's
   F4, unchanged). holon.rank's channel rule K6 reads a count law as it reads a Go-op law, as I81's instrument reads every
   law over gen/M3/goops/: both channels complete on the witness with different counts, channel representation.
C9 Regenerated, never hand-written, by this recipe, in this order:
   - holon codecs --milestone M3: gen/M3/goops/l1_counts.json (gen/M3/codec/ and gen/M3/goops/blob_ops.json
     byte-identical);
   - holon diagram --milestone M3: gen/M3/diagram/l1_counts.json (the others byte-identical);
   - holon evidence --milestone M3: gen/M3/evidence.json;
   - holon derive --milestone M3: laws/M3/ (the law; REGISTRY.json; DERIVATION.json);
   - holon lossy --milestone M3: gen/M3/par_lossy/header_length.json, its evidence input sha256 alone;
   - holon run --milestone M3 --laws <every law results/M3/summary.json lists, and the law> (how M3's PAR records are
     made since I24; a run of fewer laws would drop the others from summary.json and gen/M3/model/): gen/M3/model/
     (header_length.bend and blob_ops.bend byte-identical, l1_counts.bend new) and gen/M3/core/, those laws' law and
     proof directories (the base's byte-identical), their records (the base's in generator_sha256 and seconds alone),
     results/M3/summary.json, deps.json and splits.json (the law added);
   - holon bind --milestone M3 --laws <the law>: spec/bindings/M3.json and one line of spec/bindings/changes.jsonl;
   - holon replay-go --milestone M3: replay/M3/gocount/report.json (replay/M3/goops/report.json byte-identical), and
     the REFUTED record's replay and witness_provenance fields;
   - holon run --milestone M1 and --milestone M2, and holon profile --milestone T32: every M1, M2 and T32 record in
     generator_sha256 and seconds alone (I90's code is in the holon-ir/0.2 and 0.3 closures), as I67 re-made them; no M0
     file changes;
   - holon refute --milestone M3 --only filter: the filter fields of every REFUTED M1-M3 record (written back as before,
     the new record gaining its own), and results/M3/refute/concretization.json and filter.json, which gain exactly the
     new record's entries;
   - holon metrics --milestone M3 and holon rank --milestone M3: results/M3/metrics.json, metrics_timing.json (timings
     only) and results/M3/ranking.json (the law added);
   - holon report --milestone M3 (I82's docs/M3_COMPARISON.md and spec/M3/appendixA_map.json), only when holon report
     --milestone M3 --check fails on the new record.
   Commits as I67's rule Y11 groups them: holon run --milestone M3 through the filter stage's write-back of the records
   is one commit; the filter stage's results/M3/refute/ documents a later commit of their own; holon metrics', holon
   rank's and holon report's files another. Every M3 record of a typed, UNDO, DISCH or FACT law, and I28's init_chain
   record, keeps its stamps (CI runs no M3 G1, as at the base).
C10 Coordination. I90's checks are judged at I90's own commits (each against its first parent), so another key's
   changes merged into I90's branch are never counted as I90's. Whichever key merges second re-derives laws/M3 and
   re-makes what changes.

Predictions are in spec/M3/predictions.json under I90; the tests below check them and the rules above.
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

import tests_m3._i90 as I
from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_holon

KEY = "I90"
M = "M3"
DOC = "spec/M3/facts/morph_blob.go.extracted.json"
COMP = "l1_counts"
COUNTS = f"gen/M3/goops/{COMP}.json"
DIAGRAM = f"gen/M3/diagram/{COMP}.json"
MODEL = f"gen/M3/model/{COMP}.bend"
REPORT = "replay/M3/gocount/report.json"
GOOPS_REPORT = "replay/M3/goops/report.json"
FN = "(*morph-l2/common/batch.BatchData).Append"
HASHES, NUM = "batch_BatchData_Append_l1TxHashes", "batch_BatchData_Append_l1TxNum"
LAW = f"L_par_br_{HASHES}_{NUM}"
CYCLE = f"L_par_cy_{NUM}"
CARRIER, COUNT = "SliceHash", "Len_SliceHash"
WITNESS = 65536
TARGET_WORDS = re.compile(r"(morph|Morph|BatchData|Append|l1TxNum|l1TxHashes|l1_counts|go-ethereum|common\.Hash|"
                          r"(?<![\w.])(65535|65536|65537|131072|2097152)(?![\w.]))")


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
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I90 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I90")


def i90_merge() -> tuple[str | None, str | None]:
    """(R, M) by ancestry: R the oldest commit reachable from HEAD that adds docs/iterations/I90.md, M the oldest merge of
    R..HEAD whose second parent reaches R and whose first parent does not (None on I90's own branch before its merge)."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I90.md").split()
    if not added:
        return None, None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return r, c
    return r, None


def own_commits() -> tuple[dict[str, list[str]], str, str]:
    """I90's own non-merge commits after its prereg, each with the paths it changes, the commit they end at, and the
    prereg commit: along the first-parent line of M^2 back to the lead when I90 is merged, else prereg..HEAD."""
    pre = prereg_commit()
    _, m = i90_merge()
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
    """(parent, commit) of every own commit of I90's (own_commits) that changes path."""
    own, _, _ = own_commits()
    return [(git("rev-parse", f"{c}^1").strip(), c) for c, paths in sorted(own.items()) if path in paths]


def need_built(test) -> None:
    for rel in (COUNTS, DIAGRAM):
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


def components() -> dict:
    sc, doc = load_json(I.SIDECAR), load_json(ROOT / DOC)
    return I.expected_channels(sc, doc, load_json(ROOT / doc["extraction"]["config"]["path"]))


def commit_of_doc() -> str:
    return load_json(ROOT / DOC)["target"]["commit"]


def scratch() -> Path:
    d = Path(tempfile.mkdtemp(prefix="holon-i90-test-"))
    _DIRS.append(d)
    return d


_DIRS: list[Path] = []


def tearDownModule():
    for d in _DIRS:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ instrument
class TestInstrument(unittest.TestCase):
    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i90.py"), t["instrument_sha256"])
        self.assertEqual(file_sha256(I.INSTRUMENT), t["go_instrument_sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        for k in ("sidecar", "document", "frontend_config"):
            with self.subTest(pinned=k):
                self.assertEqual(file_sha256(ROOT / t[k]["path"]), t[k]["sha256"])

    def test_the_real_code_wraps(self):
        """The real Append on the probe set (the key's thresholds.real_code_at_prereg, observed again by this key's own
        instrument): after calls with hash counts c_1..c_k from NewBatchData() or new(BatchData), l1TxNum is
        (c_1 + .. + c_k) mod 65536, len(l1TxHashes) is 32 (c_1 + .. + c_k), blockNum is k mod 65536, and nothing
        panics."""
        out = I.run_instrument(commit_of_doc())
        for p, o in zip(I.PROBES, out):
            n = sum(p["calls"])
            with self.subTest(probe=f"{p['fresh']} {len(p['calls'])} calls, {n} hashes"):
                self.assertEqual(o, {"l1TxNum": n % 65536, "l1TxHashes_len": 32 * n,
                                     "blockNum": len(p["calls"]) % 65536, "panic": ""})


# ------------------------------------------------------------------------------------------------ component
class TestComponent(unittest.TestCase):
    def test_c1_the_count_document(self):
        """C1: the committed l1_counts document is what `holon codecs --milestone M3 --check` accepts; its channels are
        the instrument's (Append's l1TxHashes, an item channel of 32-byte items, and l1TxNum, a wrap channel of 16
        bits), each entry from the document verbatim, and its carriers are named by rule."""
        need_built(self)
        p = run_holon(["codecs", "--milestone", M, "--check"], timeout=1800)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        want = components()
        self.assertEqual(sorted(want), [COMP])
        w = want[COMP]
        self.assertEqual({k: (v["kind"], v["width"], v["field"]) for k, v in w["channels"].items()},
                         {HASHES: ("item", 32, "l1TxHashes"), NUM: ("wrap", 16, "l1TxNum")})
        sc, doc, g = load_json(I.SIDECAR), load_json(ROOT / DOC), load_json(ROOT / COUNTS)
        self.assertEqual((g["gocount_version"], g["component"], g["document"], g["document_sha256"]),
                         ("holon-gocount/0.1", COMP, DOC, file_sha256(ROOT / DOC)))
        self.assertEqual(g["carrier"], {"id": CARRIER, "type": sc["components"][COMP]["carrier"],
                                        "reach": sc["components"][COMP]["reach"]})
        self.assertEqual(g["count"], COUNT)
        self.assertEqual(sorted(g["channels"]), sorted(w["channels"]))
        stores = {(s["function"], s["site"]): s for s in doc["go"]["slices"]["stores"]}
        for name, e in w["channels"].items():
            with self.subTest(channel=name):
                c = g["channels"][name]
                for k in ("source", "param", "receiver", "field", "kind", "width", "site"):
                    self.assertEqual(c[k], e[k], k)
                self.assertEqual(c["params"], doc["go"]["functions"][e["source"]]["params"])
                self.assertEqual(c["store"], stores[(e["source"], e["site"])]["value"])
        self.assertLessEqual({"blob_ops.json", f"{COMP}.json"},
                             {x.name for x in (ROOT / "gen" / M / "goops").glob("*.json")})

    def test_c1_c4_no_target_vocabulary(self):
        """I90-R3 (C1, C4): the new modules hold no target name, field, span or count constant and import no test
        oracle."""
        item(KEY, "I90-R3")
        for f in (ROOT / "holon" / "diagram" / "gocount.py", ROOT / "holon" / "gen" / "gocount.py"):
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(f.is_file(), "missing (no build)")
                text = f.read_text(encoding="utf-8")
                self.assertEqual(TARGET_WORDS.findall(text), [])
                self.assertIsNone(re.search(r"\w+\.(go|sol):\d+", text))
                self.assertIsNone(re.search(r"(?m)^\s*(from|import)\s+tests(_m\d+)?\b", text))

    def test_c2_diagram(self):
        """C2: `holon diagram --milestone M3` writes the committed diagrams, the others unchanged, and l1_counts's
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
                         (COMP, COUNTS, file_sha256(ROOT / COUNTS), "holon-gocount/0.1"))
        cars = {c["id"]: c for c in dg["carriers"]}
        self.assertEqual(cars, {
            CARRIER: {"id": CARRIER, "cls": "rep", "base_type": CARRIER, "sort_ref": None, "interface": False,
                      "reach": "external"},
            COUNT: {"id": COUNT, "cls": "rep", "base_type": COUNT, "sort_ref": None, "interface": False, "reach": None}})
        edges = {e["id"]: e for e in dg["edges"]}
        self.assertEqual(sorted(edges), [f"CODEC.{HASHES}", f"CODEC.{NUM}"])
        for ch in (HASHES, NUM):
            with self.subTest(edge=ch):
                self.assertEqual(edges[f"CODEC.{ch}"], {
                    "id": f"CODEC.{ch}", "kind": "CODEC", "model_fn": ch, "src": CARRIER, "tgt": COUNT,
                    "partial": False, "version": None, "fn_kind": "count", "source": [{"fn": FN}], "component": DOC,
                    "env": False, "pseudo": False, "principal_class": None, "access": {"reads": [], "writes": []}})

    def test_c2_evidence(self):
        """C2: gen/M3/evidence.json is what a fresh build gives; l1_counts's model has the contract's anchors and no
        atom; at each own commit that changes the set, every other model and atom is its parent's."""
        need_built(self)
        E = holon_module("holon.diagram.evidence")
        text = (ROOT / "gen" / M / "evidence.json").read_text(encoding="utf-8")
        self.assertEqual(E.render(E.build_milestone(M, ROOT)), text)
        ev = json.loads(text)
        mdl = ev["models"][COMP]
        self.assertEqual((mdl["facts"], mdl["facts_sha256"], mdl["facts_version"], mdl["diagram"]),
                         (COUNTS, file_sha256(ROOT / COUNTS), "holon-gocount/0.1", DIAGRAM))
        an = mdl["anchors"]
        self.assertEqual(an["codec"], {HASHES: f"CODEC.{HASHES}", NUM: f"CODEC.{NUM}"})
        self.assertFalse([k for k, v in an.items() if k != "codec" and v])
        self.assertEqual([a for a in ev["atoms"] if a["model"] == COMP], [])
        changes = own_changes("gen/M3/evidence.json")
        self.assertTrue(changes, "no own commit changes gen/M3/evidence.json")
        for parent, c in changes:   # judged at I90's own commits (C10)
            with self.subTest(commit=c[:12]):
                old, new = at(parent, "gen/M3/evidence.json"), at(c, "gen/M3/evidence.json")
                self.assertEqual({k: v for k, v in new["models"].items() if k != COMP},
                                 {k: v for k, v in old["models"].items() if k != COMP})
                self.assertEqual(new["atoms"], old["atoms"])


# ------------------------------------------------------------------------------------------------ derivation
class TestDerivation(unittest.TestCase):
    def test_p2_one_law_and_the_duplicate(self):
        """I90-P2 and C3: the laws over the count document are exactly the instrument's one, rule PAR, sub-form branch,
        with the producer's statement; DERIVATION records the cycle element of the non-tree edge as its duplicate and no
        other basis element over the component; no own commit changes the catalog; the committed laws/M3 regenerates."""
        item(KEY, "I90-P2")
        need_built(self)
        want, dups = I.expected_laws(components()[COMP])
        self.assertEqual(sorted(want), [LAW])
        self.assertEqual(dups, {CYCLE: LAW})
        mine = {p.stem: load_json(p) for p in sorted((ROOT / "laws" / M).glob("L*.json"))
                if load_json(p).get("facts") == COUNTS}
        self.assertEqual(sorted(mine), [LAW])
        lw = mine[LAW]
        self.assertEqual((lw["rule"], lw["subform"], lw["milestone"], lw["ir_version"]),
                         ("PAR", "branch", M, "holon-ir/0.3"))
        self.assertEqual(lw["statement"], want[LAW])
        self.assertEqual(lw["facts_sha256"], file_sha256(ROOT / COUNTS))
        der = load_json(ROOT / "laws" / M / "DERIVATION.json")
        rows = sorted((b["subform"], json.dumps(b["key"], sort_keys=True), b["laws"], b["duplicates"], b["reason"])
                      for b in der["par_basis"] if b["model"] == COMP)
        self.assertEqual(rows, [("branch", json.dumps({"p": f"CODEC.{HASHES}", "q": f"CODEC.{NUM}"}, sort_keys=True),
                                 [LAW], {}, None),
                                ("cycle", json.dumps({"edge": f"CODEC.{NUM}"}, sort_keys=True), [], {CYCLE: LAW},
                                 None)])
        self.assertEqual(der["cycle_rank"][COMP], {"E": 2, "V": 2, "kappa": 1, "rank": 1, "tree": [f"CODEC.{HASHES}"],
                                                   "non_tree": [f"CODEC.{NUM}"]})
        for parent, c in own_changes(f"laws/{M}/REGISTRY.json"):   # C3: no own commit changes the catalog
            with self.subTest(commit=c[:12]):
                self.assertEqual(at(c, f"laws/{M}/REGISTRY.json").get("rule_catalog_version"),
                                 at(parent, f"laws/{M}/REGISTRY.json").get("rule_catalog_version"))
        reg = load_json(ROOT / "laws" / M / "REGISTRY.json")
        self.assertEqual(lw["rule_catalog_version"], reg["rule_catalog_version"])
        rules, contracts = holon_module("holon.rules"), holon_module("holon.contracts")
        res = contracts.with_contracts(M, ROOT, rules.compute(M, ROOT))
        self.assertEqual(rules.dumps(res["laws"][LAW]), (ROOT / "laws" / M / f"{LAW}.json").read_text())
        self.assertEqual(res["derivation_text"], (ROOT / "laws" / M / "DERIVATION.json").read_text())
        self.assertEqual(rules.dumps(res["registry"]), (ROOT / "laws" / M / "REGISTRY.json").read_text())


# ------------------------------------------------------------------------------------------------ model
class TestModel(unittest.TestCase):
    def test_c4_the_model(self):
        """C4: the committed model is holon.gen.gocount.generate of the count document; it defines each channel over a
        Nat, eq_count and is_true; the wrap channel goes through U32.from_nat; and the compiled model's values are the
        instrument's semantics on a probe set of lengths."""
        need_built(self)
        G = holon_module("holon.gen.gocount")
        raw = (ROOT / COUNTS).read_bytes()
        doc = json.loads(raw)
        text = (ROOT / MODEL).read_text(encoding="utf-8")
        self.assertEqual(G.generate(doc, hashlib.sha256(raw).hexdigest()), text)
        for name in (f"def {HASHES}(n: Nat) -> Nat:", f"def {NUM}(n: Nat) -> Nat:", "def eq_count(", "def is_true("):
            with self.subTest(defines=name):
                self.assertIn(name, text)
        self.assertIn("U32.from_nat(n)", text)
        cm = G.CompiledModel.build(doc, hashlib.sha256(raw).hexdigest(), COMP, holon_module("holon.bend").config(ROOT))
        ns = [0, 1, 65535, 65536, 65537, 131072, 196607]
        got = cm.values([HASHES, NUM], ns)
        chans = components()[COMP]["channels"]
        for ch in (HASHES, NUM):
            with self.subTest(channel=ch):
                self.assertEqual(got[ch], [I.channel_value(chans[ch], n) for n in ns])


# ------------------------------------------------------------------------------------------------ outcomes
class TestOutcomes(unittest.TestCase):
    def test_p1_o28_refuted_at_65536(self):
        """I90-P1: O28's law is REFUTED at x = 65536, the instrument's witness (the first candidate, 2^16), with no
        reduced N; difference 65536 (the item channel) against 0 (the wrap channel); the counter-law accepted by bend,
        its record's kernel verdict checked by BendTT."""
        item(KEY, "I90-P1")
        r = rec(LAW)
        self.assertEqual(r["status"], "REFUTED")
        self.assertEqual(I.witness(list(components()[COMP]["channels"].values())), WITNESS)
        self.assertEqual(r["witness"], {"x": WITNESS})
        self.assertEqual(r["difference"], {"lhs": WITNESS, "rhs": 0})
        self.assertEqual((r["checker"]["exit_code"], r["checker"]["marker"]), (0, "ALL PROOFS CHECK"))
        self.assertEqual(r["kernel"]["verdict"], "checked")
        self.assertEqual(r["artifacts"]["law_name"], f"cl_{LAW.lower()}")
        laws_text = (ROOT / r["artifacts"]["laws"]).read_text(encoding="utf-8")
        self.assertIn(f"law cl_{LAW.lower()}:", laws_text)
        self.assertIn("exs x: Nat", laws_text)
        proof = (ROOT / r["artifacts"]["proof"]).read_text(encoding="utf-8")
        self.assertIn(f"{WITNESS}n", proof)

    def test_p3_replay_passed(self):
        """I90-P3 and C7: replay/M3/gocount/report.json holds one passed library_api side for the law, at the record's
        witness: on a fresh BatchData, one Append with 65536 zero hashes leaves 65536 items in l1TxHashes and l1TxNum 0,
        as the model says and as the instrument observes; replay/M3/goops/report.json is not changed by I90's commits."""
        item(KEY, "I90-P3")
        rep = load_json(ROOT / REPORT)
        R = holon_module("holon.replay")
        r = rec(LAW)
        self.assertEqual((rep["milestone"], rep["morph_commit"]), (M, commit_of_doc()))
        self.assertEqual(sorted(rep["laws"]), [LAW])
        side = rep["laws"][LAW]["go"]
        self.assertEqual((side["status"], side["provenance"], side["obstruction_observed"], side["panic"]),
                         ("passed", "library_api", True, None))
        self.assertEqual(side["observed"], {HASHES: WITNESS, NUM: 0})
        self.assertEqual(side["expected"], side["observed"])
        self.assertEqual(rep["witness_sha256"][LAW], R.witness_sha256(r["witness"]))
        self.assertIsNone(re.search(r"(^|[\s(=])/|tmp|holon-", side["command"]), side["command"])
        real = I.run_instrument(commit_of_doc(), [{"fresh": "zero", "calls": [WITNESS]}])[0]
        self.assertEqual({HASHES: real["l1TxHashes_len"] // 32, NUM: real["l1TxNum"]}, side["observed"])
        self.assertEqual(r["replay"]["status"], "passed")
        self.assertEqual(r["witness_provenance"], {"go": "library_api"})
        self.assertEqual(own_changes(GOOPS_REPORT), [])

    def test_p4_go_only_pending(self):
        """I90-P4 and C8: the REFUTED record carries concretization kind go_only (result null, the reason the node-level
        path) and filter_bin pending, and results/M3/refute/filter.json lists it."""
        item(KEY, "I90-P4")
        r = rec(LAW)
        self.assertEqual(r["concretization"]["kind"], "go_only")
        self.assertIsNone(r["concretization"].get("result"))
        self.assertEqual(r["filter_bin"], "pending")
        conc = load_json(ROOT / "results" / M / "refute" / "concretization.json")["records"][f"{M}/{LAW}"]
        self.assertEqual((conc["kind"], conc["result"], conc["reason"]),
                         ("go_only", None, "node-level public path needs I39"))
        f = load_json(ROOT / "results" / M / "refute" / "filter.json")["records"][f"{M}/{LAW}"]
        self.assertEqual((f["before"], f["after"], f["kind"]), (None, "pending", "go_only"))


# ------------------------------------------------------------------------------------------------ records and gate
class TestRecords(unittest.TestCase):
    def test_c6_what_the_gate_checks(self):
        """C6: the record's binder type is the IR's (a), its ledger bundle exact (b), its binding in spec/bindings/M3.json
        over the count model (d); no lean4 entry."""
        need_built(self)
        IR = holon_module("holon.ir")
        doc = load_json(ROOT / COUNTS)
        bundles = [b for b in holon_module("holon.records").all_bundles(ROOT, COUNTS, M) if b["facts"] == COUNTS]
        self.assertEqual(len(bundles), 1)
        entries = bundles[0]["entries"]
        n_doc = len(load_json(ROOT / DOC).get("assumptions") or [])
        self.assertEqual(sorted(e["source"] for e in entries if e["source"].startswith(DOC + "#")),
                         sorted(f"{DOC}#/assumptions/{i}" for i in range(n_doc)))
        self.assertEqual(sorted(e["id"] for e in entries if not e["source"].startswith(DOC + "#")),
                         ["A-gocount-length", "A-gocount-receiver", "A-gocount-store"])
        for e in entries:
            with self.subTest(entry=e["id"]):
                self.assertTrue(e["introduced_by"])
                self.assertTrue(set(e["introduced_by"]) <= set(doc["channels"]), e["introduced_by"])
        r, lw = rec(LAW), law(LAW)
        IR.check_binder_types(lw, doc)
        self.assertEqual(r["ledger_match"], "exact")
        self.assertEqual([k for k in r.get("kernels") or [] if k.get("name") == "lean4"], [])
        binds = load_json(ROOT / "spec" / "bindings" / "M3.json")["laws"]
        self.assertEqual(binds[LAW]["model"], MODEL)
        self.assertEqual(binds[LAW]["statement_hash"], r["statement_hash"])

    def test_c6_statement_refs(self):
        """C6(e): the law's statement refs are fn:<channel> for its two channels and carrier:SliceHash; a channel's ref
        ignores its source and site and follows its kind and width."""
        need_built(self)
        R = holon_module("holon.gen.refs")
        doc, lw = load_json(ROOT / COUNTS), law(LAW)
        refs = R.refs(lw, doc)
        self.assertEqual(sorted(refs), sorted([f"fn:{HASHES}", f"fn:{NUM}", f"carrier:{CARRIER}"]))
        moved = json.loads(json.dumps(doc))
        moved["channels"][NUM]["site"] = "elsewhere"
        moved["channels"][NUM]["source"] = "elsewhere"
        self.assertEqual(R.refs(lw, moved), refs)
        edited = json.loads(json.dumps(doc))
        edited["channels"][NUM]["width"] = 32
        self.assertNotEqual(R.refs(lw, edited), refs)


# ------------------------------------------------------------------------------------------------ regressions
class TestRegressions(unittest.TestCase):
    def test_r1_d2_still_checked(self):
        """I90-R1 (D2, checked since I3): results/M2/hypotheses.json's Hyp-Z0-kzg entry is checked, the zero blob's KZG
        versioned hash computed again by holon.oracles.zero_blob equals Morph's two constants at the document's commit
        and the committed entry, and no own commit of I90's changes the entry."""
        item(KEY, "I90-R1")
        Z = holon_module("holon.oracles.zero_blob")
        morph = Path((load_json(ROOT / "config" / "holon.json").get("replay") or {})["morph"])
        entry = load_json(ROOT / "results" / "M2" / "hypotheses.json")["Hyp-Z0-kzg"]
        self.assertEqual(entry["status"], "checked")
        fresh = Z.check(morph, commit_of_doc())
        self.assertEqual(fresh["status"], "checked")
        self.assertEqual((fresh["computed"], fresh["go"]["value"], fresh["solidity"]["value"]),
                         (entry["computed"], entry["computed"], entry["computed"]))
        for parent, c in own_changes("results/M2/hypotheses.json"):
            with self.subTest(commit=c[:12]):
                self.assertEqual(at(c, "results/M2/hypotheses.json")["Hyp-Z0-kzg"],
                                 at(parent, "results/M2/hypotheses.json")["Hyp-Z0-kzg"])

    def test_r2_nothing_else_changes(self):
        """I90-R2, judged commit by commit (C10): an own commit changes, under laws/M3, results/M3, gen/M3 and replay/M3,
        only the law and its record, its law and proof directories, gen/M3/goops/l1_counts.json,
        gen/M3/diagram/l1_counts.json, gen/M3/model/l1_counts.bend, replay/M3/gocount/ and what C9's recipe writes
        besides: gen/M3/evidence.json, laws/M3/REGISTRY.json and DERIVATION.json, gen/M3/par_lossy/header_length.json
        (its evidence input sha256 alone), results/M3/summary.json, deps.json, splits.json, metrics.json,
        metrics_timing.json, ranking.json, results/M3/refute/concretization.json and filter.json (gaining only the law's
        entries), and REFUTED records' filter fields. summary.json, DERIVATION.json and the refute documents gain only
        the law, every other entry unchanged (statement hashes included). At the end of I90's own commits the law is
        derived."""
        item(KEY, "I90-R2")
        own, end, _ = own_commits()
        self.assertTrue(own, "no commit of I90's after its prereg")
        fixed = {f"laws/M3/{LAW}.json", f"results/M3/{LAW}.json", COUNTS, DIAGRAM, MODEL, "gen/M3/evidence.json",
                 "laws/M3/REGISTRY.json", "laws/M3/DERIVATION.json", "gen/M3/par_lossy/header_length.json",
                 "results/M3/summary.json", "results/M3/deps.json", "results/M3/splits.json", "results/M3/metrics.json",
                 "results/M3/metrics_timing.json", "results/M3/ranking.json", "results/M3/refute/concretization.json",
                 "results/M3/refute/filter.json", REPORT}
        prefixes = tuple(f"gen/M3/{d}/{LAW}/" for d in ("laws", "proofs"))
        mine = f"{M}/{LAW}"
        for c, paths in sorted(own.items()):
            parent = git("rev-parse", f"{c}^1").strip()
            with self.subTest(commit=c[:12]):
                for f in paths:
                    if not re.match(r"^(laws|results|gen|replay)/M3/", f) or f in fixed or f.startswith(prefixes):
                        continue
                    o, n = at(parent, f), at(c, f)   # another M3 record: its filter fields alone
                    self.assertTrue(re.match(r"^results/M3/L[^/]*\.json$", f) and o is not None and n is not None, f)
                    strip = lambda d: {k: v for k, v in _unstamped(d).items() if k not in ("filter_bin",
                                                                                           "concretization")}
                    self.assertEqual(strip(n), strip(o), f)
                for f in ("results/M3/summary.json", "laws/M3/DERIVATION.json", "results/M3/refute/concretization.json",
                          "results/M3/refute/filter.json"):
                    if f not in paths:
                        continue
                    o, n = at(parent, f) or {}, at(c, f) or {}
                    if f.endswith("DERIVATION.json"):
                        o = {e["law_id"]: e for e in o.get("laws", [])}
                        n = {e["law_id"]: e for e in n.get("laws", [])}
                        new_ok = {LAW}
                    elif f.startswith("results/M3/refute/"):
                        o, n, new_ok = o.get("records") or {}, n.get("records") or {}, {mine}
                    else:
                        new_ok = {LAW}
                    self.assertEqual(sorted(set(n) - set(o) - new_ok), [], f)
                    self.assertEqual({k: n.get(k) for k in o if k not in new_ok},
                                     {k: v for k, v in o.items() if k not in new_ok}, f)
                f = "gen/M3/par_lossy/header_length.json"
                if f in paths:
                    o, n = at(parent, f), at(c, f)
                    strip = lambda d: {**d, "inputs": [i for i in d["inputs"] if i["path"] != "gen/M3/evidence.json"]}
                    self.assertEqual(strip(n), strip(o), f)
        new = {e["law_id"] for e in (at(end, "laws/M3/DERIVATION.json") or {}).get("laws", [])}
        self.assertIn(LAW, new)

    def test_r4_earlier_records_in_stamps_alone(self):
        """I90-R4 (C9): an own commit that changes a record of results/M1, results/M2 or results/T32 leaves it equal to
        its parent's version but for generator_sha256 and keys named seconds (holon run and holon profile re-make them,
        the filter stage writing their filter fields back in the same commit); no own commit changes a file under
        laws/M0, results/M0, gen/M0 or replay/M0."""
        item(KEY, "I90-R4")
        own, _, _ = own_commits()
        self.assertTrue(own, "no commit of I90's after its prereg")
        for c, paths in sorted(own.items()):
            parent = git("rev-parse", f"{c}^1").strip()
            with self.subTest(commit=c[:12]):
                self.assertEqual([f for f in paths if re.match(r"^(laws|results|gen|replay)/M0/", f)], [])
                for f in paths:
                    if re.match(r"^results/(M1|M2|T32)/L[^/]*\.json$", f):
                        o, n = at(parent, f), at(c, f)
                        if o is not None and n is not None:
                            self.assertEqual(_unstamped(n), _unstamped(o), f)

    def test_r5_the_go_op_component_is_unchanged(self):
        """I90-R5, judged commit by commit (C10): no own commit of I90's changes I67's Go-op component:
        gen/M3/goops/blob_ops.json, its diagram and model, its four laws and records' statements, and
        replay/M3/goops/report.json; the frontend config and the go_ops sidecar keep their I67 pins at HEAD."""
        item(KEY, "I90-R5")
        own, _, _ = own_commits()
        self.assertTrue(own, "no commit of I90's after its prereg")
        i67 = ("L_par_tot_batch_RetrieveBlobBytes", "L_par_tot_blob_RetrieveBlobBytes",
               "L_par_weak_batch_RetrieveBlobBytes_blob_RetrieveBlobBytes",
               "L_par_dom_ok_batch_RetrieveBlobBytes_ok_blob_RetrieveBlobBytes")
        fixed = {"gen/M3/goops/blob_ops.json", "gen/M3/diagram/blob_ops.json", "gen/M3/model/blob_ops.bend",
                 GOOPS_REPORT} | {f"laws/M3/{lid}.json" for lid in i67}
        for c, paths in sorted(own.items()):
            parent = git("rev-parse", f"{c}^1").strip()
            with self.subTest(commit=c[:12]):
                self.assertEqual(sorted(set(paths) & fixed), [])
                for lid in i67:
                    f = f"results/M3/{lid}.json"
                    if f in paths:
                        o, n = at(parent, f), at(c, f)
                        self.assertEqual((n["status"], n["statement_hash"], n.get("witness")),
                                         (o["status"], o["statement_hash"], o.get("witness")), f)
        i67 = predictions("I67")["thresholds"]
        for k in ("frontend_config", "sidecar"):
            with self.subTest(pin=k):
                self.assertEqual(file_sha256(ROOT / i67[k]["path"]), i67[k]["sha256"])


if __name__ == "__main__":
    unittest.main()
