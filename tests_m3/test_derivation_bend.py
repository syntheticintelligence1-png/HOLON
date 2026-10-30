"""I89 (= I39c): the Go consumer compiled to Bend from I85's extracted SSA, the blob layer as the stated hypothesis HypB,
the model refined against the real ParseBatch on I85's 169 cases, and I88's five frozen derivation laws decided on it by
the checker (whitepaper §5.1 consumer and cycle, §5.5, §8.5 HypC and split status, §11.3 O7, O8 and O24, App. A F11;
BUILD_PLAN I39 and rows I85, I88 and I89). This docstring is the contract; its sha256 is the key's
thresholds.contract_docstring_sha256.

Scope. I85 (= I39a) extracted the consumer (BatchInfo.ParseBatch's closure, 14 functions, 691 instructions) and refined
a Python interpreter of it against the real Go. I88 (= I39b, PR #63, C_K 905711b0) froze five plan-stated laws over the
product of the Solidity commit and that consumer, all UNKNOWN for lack of a Bend model of the consumer. I89 builds that
model by generation and decides the frozen statements. Stage 1 (the generator, the model, HypB's instance and the
refinement) needs only I85's outputs, on the lead. Stage 2 (the laws) starts after I88 merges and I89's branch merges
the lead. No catalog bump; no closure file moves; no rule-derived law or record changes.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and a line in spec/M3/amendments.jsonl):
tests_m3/_i89.py (the rules below written a second time, independently of holon/) and the sidecar
spec/M3/lib/derivation_bend.json (written by `python -m tests_m3._i89 --write`: the boundary, the natives' kinds, the
cone observables, the fuel and the outputs; no outcome). The key's thresholds pin both and this docstring by sha256.

Inputs, read and never written: I85's document spec/M3/facts/morph_derivation.extracted.json (its consumer section),
sidecar spec/M3/lib/derivation.json, corpus gen/M3/derivation/corpus.json, oracle answers
results/M3/derivation/environment.json and replay report replay/M3/derivation/report.json; the target checkout
(config/holon.json replay.morph) at I85's sidecar's commit, copied to a scratch workspace and never written, with the Go
module cache (GOPROXY=off). Stage 2 adds I88's sidecar spec/M3/lib/derivation_laws.json, laws laws/M3/derivation/ and
records results/M3/derivation/laws/, the Rollup's typed model gen/M3/sorts/models/morph_rollup_extracted.bend and I24's
header component gen/M3/codec/header_length.json.

The model (B1-B6; `holon derivation bend`)
  B1 The cut. In the consumer's entry, D is the one call of the sidecar's boundary.blob_layer.decompress. The blob-layer
     region is tests_m3/_i89.py::cut's: the backward closure of D's operands (operands and phi edges; every block of a
     natural loop holding a closure member taken whole), narrowed to the greatest set whose every use stays inside the
     region or is D; one partial block (a suffix), whole blocks, D first in its block; inputs read only as the blobs field
     path (boundary.blob_layer.blobs_field) and a load. The model replaces the region and D by one application of the
     parameter pl (HypB's) to the blobs: PlOk{bytes} continues as D returning (bytes, nil), PlDErr{err} as D returning
     (nil, err), PlRet{err} returns err from the entry (the region's Return), PlPanic{text} panics with text. The
     functions reached only through the region are not compiled. Nothing else is cut.
  B2 The decoder. The call of boundary.decoder.function applies the parameter dt (HypT's) to its argument's bytes:
     DtOk{txs} (each transaction an opaque unit carrying the encoding the oracle reported), DtErr{err}, DtPanic{text}.
  B3 Values follow I85's interpreter (holon.derivation.interp): Go integers of every width as two U32 limbs (64-bit
     two's complement) with Go's wraparound, booleans, slices as (cell, offset, length, capacity) over a heap of cells,
     arrays and structs as records of values, pointers as (cell, path), interfaces as (type, value), nil. A runtime panic
     is an outcome carrying Go's text as a template and its arguments; an error value carries its text's template (a
     format string of the document) and arguments, or the text an oracle answered. append's growth gives the new
     backing array exactly the new length as its capacity (I85's documented approximation).
  B4 Control. Each compiled function is one trampoline def over its blocks with a Nat fuel (the sidecar's fuel per
     call): every branch on a computed value goes through a helper def's parameter; fuel exhausted is the outcome OFuel,
     never a verdict. Out = ORet | OPanic | OFuel at every function; the entry's outcome adds the receiver's final
     value.
  B5 Natives. Each environment callee of kind native is the library def of its sidecar kind (errorf, errors_new,
     be_uint, bytes_reader, binary_read, big_setbytes, big_cmp, big_newint, slice_len, encoding), generated from Go's
     semantics; native globals likewise (byte_order). A construct, op, callee or global the generator cannot express
     faithfully raises Unsupported: the model is not written and the reason is printed (exit 2).
  B6 The cones. For each law of the sidecar's "laws", its cone is the closure's functions and blocks outside the
     region (derive_ok, a premise of every law, observes the status, which every check and panic site outside the
     region decides) and its observables: the union of its terms' sidecar observables (receiver fields, the blocks'
     members, the decoder's argument and answer). gen/M3/derivation/bend/model.json records the cut (as B1 gives it),
     the compiled functions, the template table (id -> format string or panic text template), the cones, and the
     model's sha256; gen/M3/derivation/bend/consumer.bend is the model. Bend checks the model file (exit 0, ALL PROOFS
     CHECK, no law, no escape hatch).

HypB's instance (H1-H3; `holon derivation bend-refine`)
  H1 The real blob layer is run on each of the 169 cases (tests_m3/_i89.py::case_ids) by a generated Go test (the
     sidecar's go.test, in a scratch copy of the checkout, offline): for each blob the retrieve function under recover,
     the concatenation, the decompress function under recover. replay/M3/derivation/bend/blob_layer.json holds per case
     the answer {"kind": PlOk|PlDErr|PlRet|PlPanic, "bytes" | "error" | "panic", "arg_sha256"} (arg_sha256: the
     decompressor's argument, null when it was not called), with "target_commit", "go_version" and "command".
  H2 The check against I85's records: for every case whose decompressor ran, its argument's sha256 is a key of I85's
     recorded answers of the decompressor's oracle (environment.json) and the recorded answer gives the same result
     (bytes, or an error whose text the answer's error holds). HypB itself: on each case of
     tests_m3/_i89.py::canonical_cases (a raw payload, at least one blob, no override: 132 cases), the answer is PlOk
     with exactly that payload. results/M3/derivation/bend/hypb.json: {"hypb_version", "sidecar", "cases": {id:
     {"canonical", "kind", "recorded": true|false|null, "hypb": true|false|null}}, "totals": {"cases", "recorded_agree",
     "recorded_disagree", "canonical", "hypb_holds", "hypb_fails"}}.
  H3 HypB and HypT stay hypotheses: the model takes pl and dt as parameters; no def of the model answers them, and no
     law of I89 states them without its premise.

The refinement (F1-F3; `holon derivation bend-refine`)
  F1 The compiled model (consumer.bend compiled to an ES module by the local Bend) is evaluated by node on each of the
     169 cases' batches (I85's corpus and product records, built as I85's refine builds them), with pl answered by H1's
     answer for that case (HypB's instance) and dt by I85's recorded decoder answers (HypT's instance, keyed by the
     sha256 of the argument). A dt argument with no recorded answer makes the case "unanswered".
  F2 A case agrees iff tests_m3/_i89.py::agree holds between the model's outcome (status, error text, panic text,
     receiver dump) and the real one in replay/M3/derivation/report.json: status, error and panic texts equal, and
     tests_m3/_i89.py::cone_view of both dumps equal (lastBlockNumber; blockContexts' Number, txsNum and l1MsgNum, in
     order). Templates are rendered by Go's verbs (%v, %d, %x of the values the model carries).
  F3 results/M3/derivation/bend/refinement.json: {"refinement_version", "sidecar", "model": {path, sha256},
     "cases": {id: {"model": {status, error, panic, info (the cone view)}, "agree"}}, "totals": {"cases", "agree",
     "disagree", "unsupported", "fuel", "unanswered"}}. `bend-refine --check` re-evaluates the model from the recorded
     answers (no Go) and compares byte for byte.

The laws (S1-S6; stage 2, after I88 merges; `holon derivation bend-decide`)
  S1 bend-decide runs I88's decider (holon.derivation.decide.run, rules W1-W4, RP1-RP2, D1-D4, SP1) with I89's Bend
     engine as its consumer model (holon.derivation.laws.verdict's `model`): I88's candidates, evaluations and replay
     are I88's; each verdict is the engine's. The engine renders each law of laws/M3/derivation/ (I88's frozen
     statement, its hash in I88's REGISTRY.json and in the key's thresholds.i88.statement_hashes) in Bend over the
     consumer model, the Rollup's typed model (Reach as its Reach over its keccak table, the established rendering of
     the document's keccak256) and I24's header component, in gen/M3/derivation/bend/laws/<law_id>/: LAWS.bend states
     exactly law_id.lower() (a proof attempt) or "cl_" + law_id.lower() (a counter-law, the exs form), with every
     premise of the statement, hypothesis premises included, never dropped, never added; PROOF.bend comes from a proof
     generator.
  S2 REFUTED iff Bend and BendTT (--verdict) both accept the counter-law at a witness found by a bounded search on the
     compiled models (the consumer model evaluated by node, the commit on the Rollup's typed model), I88's evaluator
     witness only its starting point, never the oracle; and the witness's consumer side replays on the real ParseBatch
     (I85's TestHolonReplay, offline) with the model's observation: replay/M3/derivation/bend/witnesses.json.
  S3 PROVED iff Bend and BendTT both accept a generated proof of the law (one generator per obligation class).
  S4 Anything else is UNKNOWN, with what was tried (the search's bound, the checker's output, the reason).
  S5 results/M3/derivation/bend/decisions.json: {"decisions_version", "sidecar", "laws": {id: {"status",
     "statement_hash", "law_name", "laws_file", "proof_file", "kernels": {"bend": {exit_code, marker}, "bendtt":
     {exit_code, marker}}, "witness", "observation", "replay", "tried"}}}; I88's decider re-decides its records
     results/M3/derivation/laws/<id>.json in place with the same status (I88's D3: the bend attempt replaced, the
     evaluator attempt kept) and re-makes results/M3/derivation/splits.json by its rule SP1.
  S6 BUILD_PLAN I39's outcomes are predicted in the key: O7 REFUTED; F11's L1-count law REFUTED; O8 under
     HypC_binds_trailing PROVED and under HypC_ignores_trailing REFUTED, the split true; O24 REFUTED.

Shared files, changed only so (not outcome paths): new modules under holon/derivation/; holon/derivation/__init__.py's
command table (bend, bend-refine, bend-decide); a new driver holon/js/derivation_bend.mjs; in stage 2, what I88's
decider re-makes in place (S5: its records and evaluations under results/M3/derivation/laws/, splits.json, and, only
if they move, gen/M3/derivation/laws/ and replay/M3/derivation/laws.json). No file of thresholds.closures changes.

Own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
docs/iterations/I89.md (HEAD while none does). Commit rules (I89-R2): no own commit changes any of: a frozen root;
laws/; spec/; holon/rules/ or holon/frontends/; a file of thresholds.closures; replay/ other than
replay/M3/derivation/bend/ and replay/M3/derivation/laws.json; gen/ outside gen/M3/derivation/bend/ and
gen/M3/derivation/laws/; results/ outside results/M3/derivation/bend/, results/M3/derivation/laws/ and
results/M3/derivation/splits.json (the I88 paths in stage 2 only, re-made by I88's decider).

Earlier tests amended at this prereg: none. Disclosed: I88's tests_m3/test_derivation_laws.py asserts I88's scope
(every law UNKNOWN, P2; split false, P5). Once I89 re-decides the records in place by I88's D3, those assertions fail
by design; they are reported, never amended by I89.

Commands
  python -m holon derivation bend [--check]
  python -m holon derivation bend-refine [--check]
  python -m holon derivation bend-decide [--check]          (stage 2)
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input, Unsupported,
  no Go toolchain or checkout when Go is needed), nothing written; 3 an evaluation or replay error, nothing written.
  Outputs are canonical JSON (indent 1, sorted keys, a final newline) and generated Bend, byte-identical across runs,
  with no timestamps and no absolute paths.
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

KEY = "I89"
SIDE = ROOT / "spec" / "M3" / "lib" / "derivation_bend.json"
_CACHE: dict = {}


def th() -> dict:
    return predictions(KEY)["thresholds"]


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i89 as I
    return I


def side() -> dict:
    if "side" not in _CACHE:
        _CACHE["side"] = need(SIDE)
    return _CACHE["side"]


def out(name: str) -> Path:
    return ROOT / side()["outputs"][name]


def section() -> dict:
    if "section" not in _CACHE:
        _CACHE["section"] = need(ROOT / side()["inputs"]["document"])["consumer"]
    return _CACHE["section"]


def side85() -> dict:
    if "side85" not in _CACHE:
        _CACHE["side85"] = need(ROOT / side()["inputs"]["product_sidecar"])
    return _CACHE["side85"]


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I89 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            d = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(d, dict) and KEY in (d.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I89")


def own_commits() -> list:
    """I89's own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding
    docs/iterations/I89.md (HEAD while none does), oldest first, each with its (status, path) pairs."""
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", "docs/iterations/I89.md").split()
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


def bend_check(path: Path, verdict: bool = False):
    """Run the checker on a file in its own directory: (exit code, first line)."""
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    args = ["bend", path.name] + (["--verdict"] if verdict else [])
    p = subprocess.run(args, cwd=path.parent, capture_output=True, text=True, timeout=3600, env=env)
    first = (p.stdout.strip().splitlines() or [""])[0]
    return p.returncode, first, p.stdout + p.stderr


ESCAPES = [re.compile(r"\?[A-Za-z_]"), re.compile(r"@unsafe"), re.compile(r"(?m)^\s*def\s+[\w.]+\?\("),
           re.compile(r'(?m)^\s*import\s+"')]


def strip_comments(text: str) -> str:
    return "\n".join(ln.split("#", 1)[0] for ln in text.splitlines())


# ---------------------------------------------------------------------------------------------- instruments
class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are (construction; green at the prereg)."""

    def test_the_key_pins_the_instruments(self):
        t = th()
        self.assertEqual(file_sha256(SIDE), t["sidecar_sha256"])
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i89.py"), t["instrument_sha256"])
        d = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(d.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])
        for rel, sha in t["inputs_sha256"].items():
            self.assertEqual(file_sha256(ROOT / rel), sha, rel)

    def test_the_sidecar_is_the_instruments(self):
        I = instrument()
        self.assertEqual(side(), json.loads(json.dumps(I.sidecar())))

    def test_the_cut_and_the_cases_are_as_pinned(self):
        I = instrument()
        t = th()
        self.assertEqual(json.loads(json.dumps(I.cut(section(), side()))), t["cut"])
        self.assertEqual(I.closure_outside(section(), side()), t["compiled_functions"])
        self.assertEqual(len(I.case_ids(side85())), t["cases"])
        self.assertEqual(sorted(I.canonical_cases(side85())), sorted(t["canonical_cases"]))


# ---------------------------------------------------------------------------------------------- the model
class TestModel(unittest.TestCase):
    def test_p1_the_cut_is_the_instruments(self):
        """I89-P1 (B1, B6): the model's record holds tests_m3/_i89.py's cut and compiled functions, and its cones."""
        I = instrument()
        info = need(out("model_info"))
        self.assertEqual(info.get("cut"), json.loads(json.dumps(I.cut(section(), side()))))
        self.assertEqual(info.get("functions"), I.closure_outside(section(), side()))
        cones = info.get("cones") or {}
        self.assertEqual(sorted(cones), sorted(side()["laws"]))
        for lid, terms in side()["laws"].items():
            with self.subTest(law=lid):
                c = cones[lid]
                self.assertEqual(c.get("functions"), I.closure_outside(section(), side()))
                want = {}
                for term in terms:
                    for k, v in side()["observables"][term].items():
                        want.setdefault(k, set())
                        want[k] |= set(v if isinstance(v, list) else [v])
                got = {k: set(v if isinstance(v, list) else [v]) for k, v in (c.get("observables") or {}).items()}
                self.assertEqual(got, want)

    def test_p2_the_model_is_generated_and_checks(self):
        """I89-P2 (B2-B6): consumer.bend is generated (`bend --check` reproduces it), takes pl and dt as parameters,
        and Bend checks it: exit 0, ALL PROOFS CHECK, no law, no escape hatch."""
        mp = out("model")
        self.assertTrue(mp.is_file(), f"{mp.relative_to(ROOT)} is missing")
        text = mp.read_text(encoding="utf-8")
        code = strip_comments(text)
        for rx in ESCAPES:
            self.assertIsNone(rx.search(code), f"escape hatch {rx.pattern}")
        self.assertIsNone(re.search(r"(?m)^\s*law\s", code), "the model states a law")
        info = need(out("model_info"))
        self.assertEqual(info.get("model", {}).get("sha256"), file_sha256(mp))
        self.assertEqual(info.get("unsupported"), [])
        rc, first, full = bend_check(mp)
        self.assertEqual((rc, first), (0, "ALL PROOFS CHECK"), full[-1500:])
        rc, o = holon_ok(["derivation", "bend", "--check"])
        self.assertEqual(rc, 0, o)


# ---------------------------------------------------------------------------------------------- HypB
class TestHypB(unittest.TestCase):
    def test_p3_hypb_instance_on_the_169_cases(self):
        """I89-P3 (H1-H2): the real blob layer answers every case; it agrees with I85's recorded decompressor answers on
        every case whose decompressor ran, and HypB holds on all 132 canonical cases."""
        I = instrument()
        bl = need(out("blob_layer"))
        ids = I.case_ids(side85())
        self.assertEqual(sorted(bl.get("cases") or {}), sorted(ids))
        env = need(ROOT / side()["inputs"]["environment"])["answers"]
        dec = next(f for f in env if f.endswith("DecompressMorphDABatch"))
        canon = I.canonical_cases(side85())
        rec_ok = rec_bad = holds = fails = 0
        for cid in ids:
            a = bl["cases"][cid]
            with self.subTest(case=cid):
                if a.get("arg_sha256") is not None:
                    r = env[dec].get(a["arg_sha256"][2:] if a["arg_sha256"].startswith("0x") else a["arg_sha256"])
                    good = r is not None and (
                        (a["kind"] == "PlOk" and r.get("bytes") == a.get("bytes")) or
                        (a["kind"] == "PlDErr" and "error" in r and r["error"] in (a.get("error") or "")))
                    rec_ok += good
                    rec_bad += not good
                if cid in canon:
                    h = a["kind"] == "PlOk" and a.get("bytes") == "0x" + canon[cid].hex()
                    holds += h
                    fails += not h
        t = th()["predicted"]["hypb"]
        self.assertEqual({"recorded_disagree": rec_bad, "canonical": len(canon), "hypb_holds": holds,
                          "hypb_fails": fails}, t)
        hb = need(out("hypb"))
        self.assertEqual({k: hb["totals"][k] for k in t}, t)
        self.assertEqual(hb["totals"]["recorded_agree"], rec_ok)


# ---------------------------------------------------------------------------------------------- the refinement
class TestRefinement(unittest.TestCase):
    def test_p4_the_model_refines_the_real_consumer(self):
        """I89-P4 (F1-F3): on all 169 cases the compiled model agrees with the real ParseBatch (status, error text, panic
        text, the cone view); none unsupported, out of fuel or unanswered; `bend-refine --check` reproduces."""
        I = instrument()
        ref = need(out("refinement"))
        real = need(ROOT / side()["inputs"]["replay"])["cases"]
        ids = I.case_ids(side85())
        self.assertEqual(sorted(ref.get("cases") or {}), sorted(ids))
        self.assertEqual(ref.get("model", {}).get("sha256"), file_sha256(out("model")))
        agree = 0
        for cid in ids:
            m = ref["cases"][cid]["model"]
            r = dict(real[cid])
            r_view = {"status": r["status"], "error": r["error"], "panic": r["panic"], "info": r["info"]}
            got = I.agree(m, r_view, side())
            with self.subTest(case=cid):
                self.assertEqual(ref["cases"][cid]["agree"], got)
            agree += got
        self.assertEqual(ref["totals"], th()["predicted"]["refinement"])
        self.assertEqual(agree, th()["predicted"]["refinement"]["agree"])
        rc, o = holon_ok(["derivation", "bend-refine", "--check"])
        self.assertEqual(rc, 0, o)


# ---------------------------------------------------------------------------------------------- the laws (stage 2)
class TestLaws(unittest.TestCase):
    def decision(self, lid: str) -> dict:
        d = need(out("decisions"))
        self.assertIn(lid, d.get("laws") or {})
        return d["laws"][lid]

    def check_decided(self, lid: str, status: str):
        e = self.decision(lid)
        self.assertEqual(e["status"], status, e.get("tried"))
        self.assertEqual(e["statement_hash"], th()["i88"]["statement_hashes"][lid])
        reg = need(ROOT / "laws" / "M3" / "derivation" / "REGISTRY.json")
        self.assertEqual(reg["statements"][lid], e["statement_hash"])
        want = ("cl_" if status == "REFUTED" else "") + lid.lower()
        self.assertEqual(e["law_name"], want)
        lf, pf = ROOT / e["laws_file"], ROOT / e["proof_file"]
        laws_text = strip_comments(lf.read_text(encoding="utf-8"))
        self.assertEqual(re.findall(r"(?m)^law\s+(\w+)\s*:", laws_text), [want])
        for p in (lf, pf):
            code = strip_comments(p.read_text(encoding="utf-8"))
            for rx in ESCAPES:
                self.assertIsNone(rx.search(code), f"{p.name}: escape hatch {rx.pattern}")
        for verdict in (False, True):
            rc, first, full = bend_check(pf, verdict=verdict)
            self.assertEqual((rc, first), (0, "ALL PROOFS CHECK"), full[-1500:])
        rec = need(ROOT / "results" / "M3" / "derivation" / "laws" / f"{lid}.json")
        self.assertEqual(rec["status"], status)
        if status == "REFUTED":
            self.assertEqual((e.get("replay") or {}).get("status"), "passed")
            pred = th()["predicted"]["laws"][lid]
            self.assertEqual([e["observation"]["lhs"], e["observation"]["rhs"]], pred["observation"])
        return e

    def test_p5_o7_is_refuted(self):
        """I89-P5 (S1, S2): L_prod_cycle_lastBlockNumber REFUTED in both kernels; the witness replays."""
        self.check_decided("L_prod_cycle_lastBlockNumber", "REFUTED")

    def test_p6_the_l1_count_is_refuted(self):
        """I89-P6 (S1, S2): L_prod_count_l1MsgNum REFUTED in both kernels; the witness replays."""
        self.check_decided("L_prod_count_l1MsgNum", "REFUTED")

    def test_p7_o8_under_binds_is_proved(self):
        """I89-P7 (S1, S3): L_prod_trailing_HypC_binds_trailing PROVED by a generated proof both kernels check."""
        self.check_decided("L_prod_trailing_HypC_binds_trailing", "PROVED")

    def test_p8_o8_under_ignores_is_refuted(self):
        """I89-P8 (S1, S2): L_prod_trailing_HypC_ignores_trailing REFUTED in both kernels; the witness replays."""
        self.check_decided("L_prod_trailing_HypC_ignores_trailing", "REFUTED")

    def test_p9_o24_is_refuted(self):
        """I89-P9 (S1, S2): L_prod_calldata_BlockContexts REFUTED in both kernels; the witness replays."""
        self.check_decided("L_prod_calldata_BlockContexts", "REFUTED")

    def test_p10_the_hypc_split(self):
        """I89-P10 (S5): splits.json holds the HypC pair, binds PROVED and ignores REFUTED, split true."""
        sp = need(ROOT / "results" / "M3" / "derivation" / "splits.json")
        self.assertEqual(sp, th()["predicted"]["splits"])


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_nothing_rule_derived_moves(self):
        """I89-R1: I85's `derivation product --check` and `refine --check` reproduce with I89's code present, and
        laws/M3's top level holds exactly the laws DERIVATION.json lists."""
        for args in (["derivation", "product", "--check"], ["derivation", "refine", "--check"]):
            rc, o = holon_ok(args)
            self.assertEqual(rc, 0, f"{args}: {o}")
        der = load_json(ROOT / "laws" / "M3" / "DERIVATION.json")
        # amended (spec/M3/amendments.jsonl): DERIVATION.json's "laws" is a list of entries keyed by "law_id"
        ids = [e["law_id"] for e in der["laws"]]
        top = sorted(p.stem for p in (ROOT / "laws" / "M3").glob("L*.json"))
        self.assertEqual(top, sorted(ids))

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I89-R2: the commit rules of the docstring."""
        closed = set(th()["closures"])
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/")
        frozen_files = {"docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256"}
        allowed_results = ("results/M3/derivation/bend/", "results/M3/derivation/laws/",
                           "results/M3/derivation/splits.json")
        for sha, changes in own_commits():
            for st, path in changes:
                with self.subTest(commit=sha[:12], path=path):
                    if path == "spec/M3/amendments.jsonl" and st == "M":
                        # amended (spec/M3/amendments.jsonl): the contract's route for a wrong instrument appends
                        # lines of iteration I89, of kind instrument_inconsistency, and nothing else
                        old, new = git("show", f"{sha}^:{path}"), git("show", f"{sha}:{path}")
                        self.assertTrue(new.startswith(old), "amendments.jsonl changed, not appended")
                        for ln in new[len(old):].splitlines():
                            d = json.loads(ln)
                            self.assertEqual((d.get("iteration"), d.get("kind")), (KEY, "instrument_inconsistency"),
                                             "an appended line is not an I89 instrument_inconsistency")
                        continue
                    self.assertFalse(path.startswith(frozen) or path in frozen_files, "a frozen root")
                    self.assertFalse(path.startswith("laws/"), "laws/")
                    self.assertFalse(path.startswith("spec/"), "spec/")
                    self.assertFalse(path.startswith(("holon/rules/", "holon/frontends/")), "rules or frontends")
                    self.assertNotIn(path, closed, "a file of a generator closure")
                    if path.startswith("replay/"):
                        self.assertTrue(path.startswith("replay/M3/derivation/bend/")
                                        or path == "replay/M3/derivation/laws.json", "replay/")
                    if path.startswith("gen/"):
                        self.assertTrue(path.startswith(("gen/M3/derivation/bend/", "gen/M3/derivation/laws/")), "gen/")
                    if path.startswith("results/"):
                        self.assertTrue(path.startswith(allowed_results), "results/")

    def test_r3_the_prereg_audits_pass(self):
        """I89-R3: holon audit prereg passes for M2 and M3."""
        for m in ("M2", "M3"):
            rc, o = holon_ok(["audit", "prereg", "--milestone", m])
            self.assertEqual(rc, 0, o)
            self.assertIn("PREREG OK", o)

    def test_r4_new_code_is_generic_and_outside_every_closure(self):
        """I89-R4: the modules I89 adds under holon/derivation/ and its driver name no target (thresholds.forbidden,
        anywhere in the file; tests_m2/test_target_agnostic_exhaustive's identifiers, in code), hold no address, import
        no test module, and no file of holon/derivation/ or the driver is in a generator closure."""
        ex = holon_module("tests_m2.test_target_agnostic_exhaustive")
        idents = ex.identifiers()
        base = set(th()["derivation_files_at_base"])
        pkg = ROOT / "holon" / "derivation"
        mine = sorted(p for p in pkg.rglob("*.py") if p.relative_to(ROOT).as_posix() not in base)
        drv = ROOT / "holon" / "js" / "derivation_bend.mjs"
        self.assertTrue(mine, "no new module under holon/derivation/")
        for p in mine + [drv]:
            self.assertTrue(p.is_file(), str(p))
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=p.name):
                self.assertNotRegex(text, r"(?m)^\s*(from|import)\s+tests", "imports a test module")
                for w in th()["forbidden"]:
                    self.assertNotIn(w, text, f"names the target: {w}")
                self.assertIsNone(re.search(r"0x[0-9a-fA-F]{40}\b", text), "an address")
                if p.suffix == ".py":
                    code = ex.code_py(text)
                    hits = sorted({w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", code) if w in idents})
                    self.assertEqual(hits, [], "target identifiers in code")
        rec = holon_module("holon.records")
        run3 = holon_module("holon.sorts.run3")
        files = set()
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            files |= set(rec.generator_files(v, ROOT))
        for mod, name in (("holon.fact.run", "GEN_FACT"), ("holon.undo.run", "GEN_UNDO"),
                          ("holon.disch.run", "GEN_DISCH")):
            seen, todo = set(), list(getattr(holon_module(mod), name)) + list(run3.GEN3)
            while todo:
                r = todo.pop()
                if r in seen or not (ROOT / r).is_file():
                    continue
                seen.add(r)
                if r.endswith(".py"):
                    todo.extend(sorted(rec._holon_imports(r, ROOT) - seen))
            files |= seen
        files |= set(holon_module("holon.profile").generator_files(ROOT))
        self.assertEqual(sorted(f for f in files if f.startswith("holon/derivation/")
                                or f == "holon/js/derivation_bend.mjs"), [])


if __name__ == "__main__":
    unittest.main()
