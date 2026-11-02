"""I35: rule OWN from extracted backing identities (BUILD_PLAN I35; whitepaper §5.8 OWN-alias and OWN-lost-write, §10.1
slice headers, Appendix A F9 and F12.3, case-study rows O36 and O37). This docstring is the contract.

Scope. M1 stated one OWN law, L_own_txspayload, over a hand-written heap model (spec/M1/facts/morph_batchdata.json),
and no law states O37 (the value-receiver header cache whose write is lost). I18's Go frontend already extracts slice
backing identities (the go.slices section of the M3 Go document: result backings, in-place writes, stores and lost
writes). I35 derives rule OWN's laws from those facts alone, decides them on a generated Go heap model, and replays
every witness on the real Go code. No hand-written fact document is read.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i35.py (W1-W5 a second time, independently of holon/; Go 1.24's growth; the
BatchData traces), and spec/M3/lib/own.json (the OWN sidecar: the Go document, the growth oracle's constants with the
runtime file they come from, the search pool and budget), both fixed at this prereg.

Definitions over the Go document D = spec/M3/facts/morph_blob.go.extracted.json (its go section):
W1 Methods. A function of D whose id is "(T).M" or "(*T).M" is a method M of the named type T; its receiver is its
   first parameter; a value receiver when the id has no "*".
W2 Views. A case of a method's slice result (go.slices.results) whose backing is ["of", ["field", ["param", R],
   F]], R the receiver's name: the view (M, F) of T, region [offset, offset + len) of F's backing, under the case's
   cond.
W3 Writers. An entry of go.slices.writes of a method of T whose backing is ["of", ["field", ["param", R], G]]: an
   in-place write of the method into G's backing, region [from, to), under its cond. The writer methods of T are the
   methods with at least one.
W4 Alias laws. One per (view method V, writer method W) of one type T, V == W included, such that W writes in place
   the field some view of V returns (an E2 relation): L_own_alias_<pkg>_<T>_<V>_<W>, <pkg> the last element of T's
   package path, <T> its type name. A writer of another field is no law of V (the model's invariant that distinct
   fields never share a backing covers it, W9). Claim: from any state the type's methods reach from
   its constructor's value, v := V(); then one call of W with any arguments; then v's bytes are their snapshot at V's
   return (only W runs in between: each pair is attributed to its writer).
W5 Lost-write laws. One per entry (m, b, F) of go.slices.lost_writes whose method m has a value receiver of type T
   and some method of T reads F through its receiver (an occurrence of ["field", ["param", R], F], R that method's
   receiver, in a cond, backing, len, cap or offset of one of its slice results' cases: evidence E2, written via m and
   read via the reader through the original object): L_own_lost_<pkg>_<T>_<m>_<F>. Claim: for every value x of T and
   every call of m on x, x.F afterwards is the value m assigned to its receiver's F. A lost write without such a read
   is a gap, listed in the carrier document, not a law.

Build:
W6 Carrier documents. `holon own --milestone M3 [--check]` writes, for every type with a view or a lost write,
   gen/M3/own/<pkg>_<T>.json (own_version holon-own/0.1; json.dumps(indent=2, sort_keys=True) + "\\n"; no
   timestamps): {"own_version", "type", "document", "document_sha256", "views", "writers", "lost_writes" (each W5
   entry with "readers", and "law": true or false), "methods": {method: {"source", "params", "results", "span",
   "stores": its go.slices.stores entries, "writes": its W3 entries, "cases": its slice result cases}}, "modelled":
   the slice fields some view returns, sorted, "abstracted": the type's other slice fields with a store, sorted}. It
   removes a stale document; --check exits 1 on any difference. holon/own.py holds no target name.
W7 Diagram and evidence. `holon diagram --milestone M3` also writes gen/M3/diagram/own_<pkg>_<T>.json (holon-diagram/0.1;
   model own_<pkg>_<T>; facts the carrier document, facts_version holon-own/0.1): one carrier per field of
   "modelled" and per lost-write field, and one edge per method of the document {"id": "OWN.<method>", "kind": "OWN",
   "model_fn": method, "access": {"reads": the fields its views return or it reads (W5), sorted, "writes": the fields it
   writes in place (W3) or loses (W5), sorted}, ...}; every other diagram is unchanged. `holon evidence --milestone M3`
   adds one model per carrier document, with the E2 atoms holon.diagram.evidence computes over those edges' access
   sets (its rule unchanged): every OWN law names its methods' edges and its record's computed evidence levels include
   E2. spec/schemas/evidence.schema.json admits facts_version holon-own/0.1.
W8 Derivation. Rule OWN (holon/rules/own.py, sub-forms "alias" and "lost_write", deterministic law ids as W4 and W5)
   joins the catalog in the next free holon-rules version after I71's (the rules of the version before unchanged, the
   same producer objects); catalog_version("M3") returns it. Law IR holon-ir/0.3: rule OWN, facts the carrier
   document; binders alias (p: Trace, w: Call) and lost_write (x: Val, c: Call), with the type in their names, as the
   builder's IR rule fixes; claim {"eq": [{"own": <own id>, "on": [{"var": b} for each binder]}, {"bool": true}]},
   the own id "<pkg>_<T>:<subform>:<method>[:<method>|:<field>]", hashed through the ref "own:<id>" (the sha256 of
   canonical {"template": "holon.rules.own/<subform>", "template_version": 1, "subform", "basis"}, recomputed from
   the carrier document). The own term is additive in IR 0.3 (the IR 0.3 schema and holon.ir.render_term gain it).
   Every earlier law of laws/M3 is re-derived under the new catalog version (catalog_rederivation lines), and bound.
W9 The model. holon.gen.ownheap generates gen/M3/model/own_<pkg>_<T>.bend from the carrier document alone: the Go heap
   (each backing a byte list), each modelled field a slice header (backing, offset, len, cap), the constructor's value
   (a function of D returning *T or T whose stores set every modelled field to an empty make: len 0, cap 0, no backing),
   and per method of the append-store class: stores F = append(F, X) (X a byte-slice parameter, or a modelled field's
   bytes), transient appends (a W3 write with no store of its field), view results (F, or append(F, G...) for modelled
   F and G), all with Go's append semantics (in place when len + k <= cap, else a new backing of growslice's capacity
   by Go 1.24's nextslicecap and roundupsize over the sidecar's class table: assumption A-go-growth). A method outside
   the class makes the laws naming it Unsupported (UNKNOWN, with the reason). Abstracted fields: every store into one
   is an append onto that field or a fresh value (checked at generation, else Unsupported), so its backing is never a
   modelled field's (A-own-fields). A value-receiver method runs on a copy (W5). Contents are modelled for modelled
   fields; a lost write compares lengths (A-own-len: a write that changes a field's length is not lost when the length
   persists).
W10 Deciding. holon run decides an OWN law (holon.own_run): alias REFUTED by a counter-law (bend's acceptance point,
   then BendTT --verdict) at the first witness of the sidecar's bounded search over traces of the type's modelled
   methods with byte arguments from the sidecar's pool; PROVED by heap_disjoint (a Bend proof that every write W makes
   is outside the view's region, in another backing or past the view's end, by induction over the trace with the
   invariant that distinct modelled fields never share a backing) with a checked inhabitant; UNKNOWN otherwise, naming
   the route that failed. lost_write REFUTED by a counter-law at the type's zero value, or UNKNOWN. Witnesses come from
   the model, never from the instrument or the real code.
W11 Records and the gate. results/M3/<law id>.json (v1 and v2; evidence fields from gen/M3/evidence.json); the ledger
   bundle generated from the carrier document (the Go document's assumptions, introduced by the methods' definitions,
   plus A-go-growth, A-own-fields and A-own-len); `holon bind --milestone M3 --laws <the OWN laws>` binds them to their
   model and emission; no lean4 entry; when REFUTED, witness_provenance {"go": "library_api"}.
W12 Replay. `holon replay-go --milestone M3` also concretizes every REFUTED OWN record's witness and runs it on the
   real code, from an internal Go test of the type's package that it generates from the carrier document on a scratch
   copy of the pinned morph checkout: the trace's calls; for an alias law the view's bytes before and after W; for a
   lost write the field after m; for every append of a modelled field the real capacity, compared with the model's
   (A-go-growth's check). replay/M3/own/report.json {"milestone", "morph_commit", "go_version", "laws": {law: {"go":
   {"status", "provenance": "library_api", "obstruction_observed", "observed", "expected", "caps", "command"}}},
   "witness_sha256"}; passed iff the obstruction is observed and every capacity agrees. It stamps the records.
W13 Filter. holon refute --milestone M3 --only filter takes an OWN REFUTED record whose every side is a Go library call
   as go_only (I40's rule K2, as amended for I67), final bin pending ("node-level public path needs I39").
W14 Regenerated, never hand-written: holon own; holon diagram; holon evidence; holon derive (the OWN laws, the
   re-derivation of laws/M3 under the new catalog version, the registries); holon statement_diff recatalog and holon
   bind; holon run --milestone M3 --laws <the OWN laws>; holon replay-go; holon refute --only filter; holon metrics;
   and the generator stamps of every M1, M2, T32 and M3 record whose generator closures I35 changes.
W15 Coordination. I28 (holon-rules/1.6) and I71 (UNDO cancel) bump the catalog before I35; whoever merges later
   re-derives laws/M3 under the next free version and re-makes what changes. I35's checks are judged at I35's own
   commits.
W16 Earlier tests amended at this prereg, each narrowed to I35's outcomes: none known at the prereg beyond those that
   pin the M3 catalog version or count M3 laws; each found later is an amendment line with its reason, never a
   weakened claim.

Predictions are in spec/M3/predictions.json under I35; the tests below check them and the rules above.
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

import tests_m3._i35 as I
from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, records, run_holon

KEY = "I35"
M = "M3"
DOC = I.GO_DOC
SIDECAR = "spec/M3/lib/own.json"
OWN_DIR = ROOT / "gen" / M / "own"
REPORT = ROOT / "replay" / M / "own" / "report.json"
BD = "morph-l2/common/batch.BatchData"
ALIAS_REFUTED = "L_own_alias_batch_BatchData_TxsPayloadV2_Append"
ALIAS_SELF = "L_own_alias_batch_BatchData_TxsPayloadV2_TxsPayloadV2"
ALIAS_PROVED = ("L_own_alias_batch_BatchData_TxsPayload_Append",
                "L_own_alias_batch_BatchData_TxsPayload_EstimateCompressedSizeWithNewPayload")
LOST = ("L_own_lost_batch_BatchHeaderV0_Bytes_EncodedBytes", "L_own_lost_batch_BatchHeaderV1_Bytes_EncodedBytes")
OWN_LAWS = tuple(sorted((ALIAS_REFUTED, ALIAS_SELF) + ALIAS_PROVED + LOST))
TARGET_WORDS = re.compile(r"(morph|Morph|BatchData|BatchHeader|TxsPayload|EncodedBytes|blockContexts|txsPayload|"
                          r"l1TxHashes|EstimateCompressed)")
NEW_HOLON = ("holon/own.py", "holon/own_run.py", "holon/rules/own.py", "holon/gen/ownheap.py")


def git(*args) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def _is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode in (0, 1), p.stderr
    return p.returncode == 0


def prereg_commit() -> str:
    """C_K: the oldest commit of HEAD's history whose spec/M3/predictions.json holds iterations.I35."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            if KEY in json.loads(git("show", f"{c}:spec/M3/predictions.json")).get("iterations", {}):
                return c
        except (AssertionError, ValueError):
            continue
    raise AssertionError("no commit holds iterations.I35")


def _merge() -> str | None:
    """M: the oldest merge on R..HEAD's ancestry path (R the oldest commit adding docs/iterations/I35.md) whose second
    parent reaches R and whose first parent does not; None on I35's own branch before its merge."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I35.md").split()
    if not added:
        return None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return c
    return None


def own_commits() -> dict[str, list[str]]:
    """I35's own non-merge commits after C_K with the paths each changes: along the first-parent line of M^2 back to
    the lead once merged, else C_K..HEAD. Another key's commits merged into I35's branch are never I35's."""
    pre, m = prereg_commit(), _merge()
    revs = [git("rev-parse", f"{m}^2").strip(), "^" + git("rev-parse", f"{m}^1").strip(), f"^{pre}"] if m else \
        [f"{pre}..HEAD"]
    out = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def at(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except (AssertionError, ValueError):
        return None


def go_doc() -> dict:
    return load_json(ROOT / DOC)["go"]


def thresholds() -> dict:
    return predictions(KEY)["thresholds"]


def contract_sha256() -> str:
    import hashlib
    return hashlib.sha256((__doc__ or "").encode("utf-8")).hexdigest()


def need_build(test: unittest.TestCase) -> None:
    if not OWN_DIR.is_dir() or not list(OWN_DIR.glob("*.json")):
        test.fail("no build: gen/M3/own/ holds no carrier document (I35 is built after its prereg)")


def own_laws() -> dict:
    return {p.stem: load_json(p) for p in sorted((ROOT / "laws" / M).glob("L_own_*.json"))}


# ------------------------------------------------------------------------------------------------ prereg
class TestPrereg(unittest.TestCase):
    def test_key_pins_the_contract_and_the_instrument(self):
        t = thresholds()
        self.assertEqual(t["contract_docstring_sha256"], contract_sha256())
        self.assertEqual(t["instrument_sha256"], file_sha256(ROOT / "tests_m3" / "_i35.py"))
        self.assertEqual(t["sidecar_sha256"], file_sha256(ROOT / SIDECAR))
        self.assertEqual(sorted(t["own_laws"]), list(OWN_LAWS))

    def test_the_instrument_on_the_document(self):
        """Construction: the instrument's views, writers, lost writes and laws on D are the key's pinned ones."""
        go = go_doc()
        t = thresholds()
        self.assertEqual(sorted(I.laws(go)), list(OWN_LAWS))
        self.assertEqual([[v["type"], v["method"], v["field"]] for v in I.views(go)], t["views"])
        self.assertEqual([[w["type"], w["method"], w["field"]] for w in I.writes(go)], t["writers"])
        self.assertEqual([[x["type"], x["method"], x["field"], x["readers"]] for x in I.lost_writes(go)],
                         t["lost_writes"])

    def test_the_growth_oracle_is_the_pinned_runtimes(self):
        """Construction: the sidecar's class table and the instrument's are runtime/sizeclasses.go's of the pinned Go
        toolchain (config replay.go_version), and the BatchData trace is the key's."""
        sc = load_json(ROOT / SIDECAR)
        self.assertEqual(tuple(sc["growth"]["class_to_size"]), I.CLASS_TO_SIZE)
        goroot = subprocess.run(["go", "env", "GOROOT"], capture_output=True, text=True, timeout=60).stdout.strip()
        text = (Path(goroot) / "src" / "runtime" / "sizeclasses.go").read_text(encoding="utf-8")
        m = re.search(r"var class_to_size = \[_NumSizeClasses\]uint16\{([0-9, ]+)\}", text)
        self.assertIsNotNone(m, "runtime/sizeclasses.go has no class_to_size table")
        self.assertEqual(tuple(int(x) for x in m.group(1).split(",")), I.CLASS_TO_SIZE)
        self.assertEqual(I.batchdata_alias_trace(), thresholds()["batchdata_trace"])


# ------------------------------------------------------------------------------------------------ build
class TestBuild(unittest.TestCase):
    def test_w6_carrier_documents(self):
        need_build(self)
        p = run_holon(["own", "--milestone", M, "--check"], cwd=ROOT, timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        go = go_doc()
        docs = {p.stem: load_json(p) for p in sorted(OWN_DIR.glob("*.json"))}
        self.assertEqual(sorted(docs), ["batch_BatchData", "batch_BatchHeaderV0", "batch_BatchHeaderV1"])
        bd = docs["batch_BatchData"]
        self.assertEqual(bd["own_version"], "holon-own/0.1")
        self.assertEqual(bd["document_sha256"], file_sha256(ROOT / DOC))
        self.assertEqual(sorted([v["method"], v["field"]] for v in bd["views"]),
                         sorted([v["method"], v["field"]] for v in I.views(go) if v["type"] == BD))
        self.assertEqual(sorted([w["method"], w["field"]] for w in bd["writers"]),
                         sorted([w["method"], w["field"]] for w in I.writes(go) if w["type"] == BD))
        self.assertEqual(bd["modelled"], ["blockContexts", "txsPayload"])
        for k in ("batch_BatchHeaderV0", "batch_BatchHeaderV1"):
            self.assertEqual([(x["method"], x["field"], x["law"]) for x in docs[k]["lost_writes"]],
                             [("Bytes", "EncodedBytes", True)])

    def test_w7_diagrams_and_e2(self):
        need_build(self)
        ev = load_json(ROOT / "gen" / M / "evidence.json")
        for model in ("own_batch_BatchData", "own_batch_BatchHeaderV0", "own_batch_BatchHeaderV1"):
            self.assertIn(model, ev["models"])
            self.assertEqual(ev["models"][model]["facts_version"], "holon-own/0.1")
        e2 = {(a["p"], a["q"]) for a in ev["atoms"] if a["model"] == "own_batch_BatchData" and a["level"] == "E2"}
        for lid in OWN_LAWS:
            x = I.laws(go_doc())[lid]
            if x["subform"] == "alias":
                self.assertIn((f"OWN.{x['writer']}", f"OWN.{x['view']}"), e2, lid)

    def test_w8_derivation(self):
        need_build(self)
        ls = own_laws()
        self.assertEqual(sorted(ls), list(OWN_LAWS))
        reg = load_json(ROOT / "laws" / M / "REGISTRY.json")
        cat = holon_module("holon.rules")
        self.assertEqual(reg["rule_catalog_version"], cat.catalog_version(M))
        self.assertIn("OWN", cat.CATALOGS[cat.catalog_version(M)])
        for lid, law in ls.items():
            self.assertEqual(law["rule"], "OWN", lid)
            self.assertEqual(law["subform"], I.laws(go_doc())[lid]["subform"], lid)
            self.assertTrue(law["facts"].startswith("gen/M3/own/"), lid)
            self.assertEqual(law["rule_catalog_version"], reg["rule_catalog_version"], lid)

    def test_w9_models_are_generated_and_name_no_target(self):
        need_build(self)
        for p in sorted(OWN_DIR.glob("*.json")):
            m = ROOT / "gen" / M / "model" / f"own_{p.stem}.bend"
            self.assertTrue(m.is_file(), m)
            self.assertIn("GENERATED", m.read_text(encoding="utf-8")[:400])
        for rel in NEW_HOLON:
            f = ROOT / rel
            if f.is_file():
                hits = sorted(set(TARGET_WORDS.findall(f.read_text(encoding="utf-8"))))
                self.assertEqual(hits, [], rel)


# ------------------------------------------------------------------------------------------------ predictions
class TestPredictions(unittest.TestCase):
    def test_p3_lost_writes_refuted_and_replayed(self):
        """I35-P3 (O37)."""
        item(KEY, "I35-P3")
        need_build(self)
        recs = records(M)
        rep = load_json(REPORT)
        for lid in LOST:
            self.assertEqual(recs[lid]["status"], "REFUTED", lid)
            self.assertIn(recs[lid]["kernels"][-1].get("result"), ("checked",), lid)
            g = rep["laws"][lid]["go"]
            self.assertEqual((g["status"], g["obstruction_observed"]), ("passed", True), lid)

    def test_p4_txspayloadv2_append_refuted_and_replayed(self):
        """I35-P4 (the O36 analogue on the extracted code)."""
        item(KEY, "I35-P4")
        need_build(self)
        rec = records(M)[ALIAS_REFUTED]
        self.assertEqual(rec["status"], "REFUTED")
        g = load_json(REPORT)["laws"][ALIAS_REFUTED]["go"]
        self.assertEqual((g["status"], g["obstruction_observed"]), ("passed", True))
        self.assertTrue(g["caps"], "the replay recorded no capacity")
        self.assertTrue(all(c["model"] == c["real"] for c in g["caps"]), g["caps"])

    def test_p5_disjoint_pairs_proved(self):
        """I35-P5."""
        item(KEY, "I35-P5")
        need_build(self)
        recs = records(M)
        for lid in ALIAS_PROVED:
            self.assertEqual(recs[lid]["status"], "PROVED", lid)
            ks = {k.get("name"): k.get("result") for k in recs[lid]["kernels"]}   # amended: entries are keyed "name"
            self.assertEqual(ks.get("bendtt"), "checked", lid)
            self.assertTrue((ROOT / "gen" / M / "proofs" / lid / "PROOF.bend").is_file(), lid)

    def test_p6_self_pair_unknown_named(self):
        """I35-P6."""
        item(KEY, "I35-P6")
        need_build(self)
        rec = records(M)[ALIAS_SELF]
        self.assertEqual(rec["status"], "UNKNOWN")
        self.assertRegex(json.dumps(rec.get("bound") or rec.get("attempts") or rec), r"overlap|disjoint")

    def test_p7_every_own_law_has_e2_and_gevid_passes(self):
        """I35-P7."""
        item(KEY, "I35-P7")
        need_build(self)
        recs = records(M)
        for lid in OWN_LAWS:
            levels = recs[lid].get("evidence_levels") or (recs[lid].get("evidence") or {}).get("levels") or []
            self.assertIn("E2", levels, lid)


# ------------------------------------------------------------------------------------------------ regressions
class TestRegressions(unittest.TestCase):
    def test_r1_the_m1_own_law_is_unchanged(self):
        """I35-R1: M1's law L_own_txspayload and spec/M1/facts/morph_batchdata.json are as at the prereg, and the
        law's record stays REFUTED (its generator stamps may move)."""
        item(KEY, "I35-R1")
        t = thresholds()
        for rel, sha in t["m1_pins"].items():
            self.assertEqual(file_sha256(ROOT / rel), sha, rel)
        self.assertEqual(records("M1")["L_own_txspayload"]["status"], "REFUTED")

    def test_r2_own_commits_change_no_other_status(self):
        """I35-R2: no commit of I35's own changes the status of a record it did not add (results/M3, results/M2 and
        results/M1 L*.json, each against its first parent); another key's changes merged into I35's branch are not
        counted."""
        item(KEY, "I35-R2")
        need_build(self)
        own = own_commits()
        self.assertTrue(own, "no commit of I35's after its prereg")
        for c, paths in own.items():
            for f in paths:
                if not re.fullmatch(r"results/M[1-3]/L[^/]*\.json", f) or f.startswith("results/M3/L_own_"):
                    continue
                old, new = at(f"{c}^1", f), at(c, f)
                if old is None or new is None:
                    continue
                self.assertEqual(new.get("status"), old.get("status"), f"{c[:12]} {f}")

    def test_r3_own_commits_change_no_earlier_law(self):
        """I35-R3: no commit of I35's own changes a file under laws/M0, laws/M1 or laws/M2."""
        item(KEY, "I35-R3")
        need_build(self)
        for c, paths in own_commits().items():
            self.assertEqual([f for f in paths if re.match(r"laws/M[0-2]/", f)], [], c[:12])

if __name__ == "__main__":
    unittest.main()
