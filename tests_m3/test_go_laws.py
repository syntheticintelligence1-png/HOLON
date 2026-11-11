"""I93 (= I38d) contract: O5, O6 and D3 as laws over a Go part of rule PAR, with the frontend 0.3 config.

I91 tested HypZ and HypZ_len on the real codec and left the three laws to I93, each with a route I67's no-catalog-change
pattern does not give (I91's Questions 1, 6 and 7, unanswered; the routes below are the prereg's choice, disclosed). Its
instrument is tests_m3/_i93.py (independent of holon/); its sidecars spec/M3/lib/go_frontend_03.json and
spec/M3/lib/go_laws.json are fixed here.

G1 Frontend 0.3. Config holon-go-frontend/0.3 (frontend_version holon-go/0.3) is 0.2 plus four additive renderings:
   (a) compare: a comparison whose value is used (returned, stored or passed) is the term [op, l, r], op one of ==, !=,
       <, <=, >, >=, the vocabulary of path conditions, where 0.2 writes ["unknown", "compare"];
   (b) carried: each loop_bodies entry lists "carried": [{"name", "init"}], the loop header's phis other than the
       induction variable, named by their source variable, init their value on entry; each of its paths ending
       "continue" gets "updates": {name: term}, the value at the back edge, where ["carried", name] is the value at the
       iteration's start; a path leaving the loop reads ["carried", name] where 0.2 loses the value;
   (c) varargs: a call's variadic slice built at the call site is ["varargs", [terms]], the values stored into the fresh
       array in index order, where 0.2 writes the slice of its allocation;
   (d) primitive kind fill_bytes: (*big.Int).FillBytes(buf) is buf holding the receiver's big-endian magnitude, cell k
       ["byte", receiver, k] for k < len(buf), with a site of kind "fill_bytes" (the panic when the magnitude needs more
       bytes) whose status is "unknown".
   A 0.1 or 0.2 config extracts byte for byte what it extracts at the prereg base.
G2 The document. `holon extract go --milestone M3 --config spec/M3/lib/go_frontend_03.json` writes
   spec/M3/facts/morph_go03.go.extracted.json (common/batch and common/blob at the pinned commit, I67's packages), twice
   byte-identically.
G3 Catalog. The next free holon-rules version (expected holon-rules/1.15) adds the Go part of rule PAR,
   holon/rules/gox.py, with sub-forms go_round_trip, go_branch and go_recompute, run by derive for a milestone that has
   spec/<M>/lib/go_laws.json and never by the typed part. Every earlier catalog's producers are the same objects. The
   part writes gen/<M>/gox/basis.json: every basis element, with its law id or the reason it has none.
G4 go_round_trip (D3; P1 over unversioned Go codecs). A pair (E, k, D) of the document's codecs: E an encoder that no
   codecs.matches entry lists (not a versioned layout), k the index of one of its entries that is exact; D a decoder
   with one parameter whose type is not a codecs.predicates parameter type (not a linked carrier), every non-error
   return path of which requires len(param) == L, L the entry's length; every read of D covers cells of the entry that
   are ["byte", v, 0..w-1] of one value v. Law L_par_gort_<E>_<D>_<k>: for all E's inputs, D(E(inputs)) is the non-error
   result v (the cells of v, one U32 per byte, the established codec convention).
G5 go_branch (O5; PAR-branch, a size test that short-cuts a compressing path). In one function F of the document, return
   paths p and q, both with error "nil": p's returns are constants; q's conditions hold p's conditions but one, c, which
   q holds negated; c compares the length of a slice X ([<= or <, len(X), L]; the length of a slice with an explicit
   high bound is hi - lo, as the frontend writes it); q calls g(X), a call p does not make; q's Bool return at position i
   is (0.3) [> or >=, len(result 0 of g(X)), L]. Law L_par_gobr_<F>_p<p>_p<q>: for all inputs, c and q's other
   conditions imply that q's return i equals p's. Go int is Nat (non-negative, no overflow). Premise HypZ_len at X when g
   is the compression sidecar's enc or a call enc makes on a non-empty argument and returns as its own result:
   |g(X)| <= CB(|X|), CB the sidecar's term (G8). A pair that F holds only by inlining an analyzed callee holding a pair
   of the same g (go.calls) belongs to the callee, not to F.
G6 go_recompute (O6; cross-language, through the preimage). A role of the sidecar's recompute section names Go functions
   and a Solidity store site. For each Go function G: its non-error returns are Keccak256Hash(["varargs", [P]]) with P
   the Go preimage; the Solidity value is keccak256(slice(mem(...), 0, len)), the store's value in the named action, its
   preimage S over the action's inputs and call answers. Law L_par_gorc_<role>_<G>: every Go data hash is some on-chain
   one, for all of G's inputs there are Solidity inputs and answers with S == P (byte cells; keccak's congruence gives
   the digests). A Go function whose preimage holds an allocation ([alloc] under P) has no law: reason
   "alloc_preimage".
G7 Statements (holon-ir/0.3; facts: the document). The claim {"gox": <gox id>, "on": [binders]} == true, the gox id
   "<subform>:<law id's words after the prefix, joined by ':'>"; its ref "gox:<ID>" is the sha256 of the canonical
   {template "holon.rules.gox/<subform>", template_version 1, subform, basis}, recomputed from the sidecar and the
   documents. <E>, <D>, <F>, <G> are short names: "(*pkg.T).M" -> "T_M", "pkg.F" -> "F".
G8 Models. gen/<M>/gox/<law id>.bend, generated from the basis: byte cells U32, Go int Nat, Bool for compare, Go
   preimages and Solidity memory as lists of cells (the loop's carried value folded over the counted range, the
   Solidity mloop over its count). CB is the sidecar's hypz_len.cb term; it agrees with I91's HypZ_len text at
   n = 0, 1, 255, 256, 2047, 2048, 126976, 131071, 131072 and 2^20.
G9 Decision. PROVED when the pinned bend accepts the generated proof of the law; REFUTED when it accepts a counter-law
   with a concrete witness and the replay of G10 agrees, its witness_sha256 the witness's sha256; UNKNOWN otherwise,
   with what was tried. A go_branch counter-law's witness is the smallest blob count (1) with |X| at the bound, all of
   it in X's last slice operand; a go_recompute counter-law's witness is the fewest loop iterations and the empty
   rest.
G10 Replays (replay/<M>/gox/<law id>.json, generated harnesses, offline). go_branch: an internal test of F's package
   runs F on the witness, X's bytes the compression sidecar's stream kind (seed and construction from its sample
   section), and the real enc on X; agree when F returns p's value while |enc(X)| makes q's value differ. go_recompute:
   the Go function on the state the witness names (built with the package's constructor and its append method), and
   the Solidity store's value computed by the pinned contract through a harness inheriting it, at the inputs the
   correspondence of the witness names; agree when the two digests differ.
G11 Records. results/<M>/<law id>.json, the standard record (status, statement, artifacts, checker, witness, replay);
   bindings for holon.bindings; G11V's dual check where a premised law is PROVED.
G12 Target-agnostic code. No holon/ file names the target's packages, types, functions, fields or constants; every name
   comes from the sidecars and the documents.

K10 Earlier tests amended in this prereg: none. One that fails on I93's outcomes is a miss, reported.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i93 as I

ROOT = Path(__file__).resolve().parents[1]
KEY = "I93"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "go_laws.json"
CONFIG03 = ROOT / "spec" / "M3" / "lib" / "go_frontend_03.json"
DOC03 = ROOT / "spec" / "M3" / "facts" / "morph_go03.go.extracted.json"
GOX = ROOT / "gen" / "M3" / "gox"
RESULTS = ROOT / "results" / "M3"
REPLAY = ROOT / "replay" / "M3" / "gox"
ESTIMATORS = ("(*morph-l2/common/batch.BatchData).EstimateCompressedSizeWithNewPayload",
              "(*morph-l2/common/batch.BatchData).WillExceedCompressedSizeLimit")
ZSTD = "morph-l2/common/codec/zstd.CompressBatchBytes"
KECCAK = "github.com/morph-l2/go-ethereum/crypto.Keccak256Hash"


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def record(law: str) -> dict:
    p = RESULTS / f"{law}.json"
    if not p.exists():
        raise AssertionError(f"{law}: no record at {p.relative_to(ROOT)}")
    return load(p)


def key() -> dict:
    return load(ROOT / "spec" / "M3" / "predictions" / f"{KEY}.json")


def extract(config: Path, out: Path) -> None:
    p = subprocess.run(["python", "-m", "holon", "extract", "go", "--milestone", "M3", "--config", str(config),
                        "--out-dir", str(out)], cwd=str(ROOT), capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-2000:] + p.stderr[-2000:])


def size_term(t, call: str) -> bool:
    """[> or >=, ["len", ["result", ["call", call, [X]], 0]], L]."""
    return isinstance(t, list) and len(t) == 3 and t[0] in (">", ">=") and t[1][:1] == ["len"] \
        and t[1][1][:1] == ["result"] and t[1][1][1][:2] == ["call", call] and t[1][1][2] == 0


class TestBasis(unittest.TestCase):
    def test_k_the_key_pins_the_instrument_and_sidecars(self):
        th = key()["thresholds"]
        self.assertEqual(sha256(ROOT / th["instrument"]), th["instrument_sha256"])
        for s in th["sidecars"]:
            self.assertEqual(sha256(ROOT / s["path"]), s["sha256"], s["path"])
        self.assertEqual(sorted(th["law_ids"]), I.expected_law_ids())

    def test_k_cb_agrees_with_i91s_text(self):
        """G8: the sidecar's CB term evaluates as I91's HypZ_len text does."""
        def ev(t, n):
            if t == "n":
                return n
            if isinstance(t, int):
                return t
            op, *a = t
            if op == "?":
                return ev(a[1], n) if ev(a[0], n) else ev(a[2], n)
            x, y = ev(a[0], n), ev(a[1], n)
            return {"+": x + y, "-": x - y, ">>": x >> y, "<": int(x < y)}[op]
        cbt = load(SIDECAR)["hypz_len"]["cb"]
        self.assertIn("(n < 131072 ? (131072 - n) >> 11 : 0)",
                      load(ROOT / "spec" / "M3" / "lib" / "compression.json")["hypotheses"]["HypZ_len"]["statement"])
        for n in (0, 1, 255, 256, 2047, 2048, 126976, 131071, 131072, 1 << 20):
            self.assertEqual(ev(cbt, n), I.cb(n), n)


class TestFrontend(unittest.TestCase):
    def test_p1_frontend_03(self):
        """I93-P1 (G1, G2): the 0.2 configs extract byte for byte; the 0.3 document re-extracts byte for byte and holds
        the estimators' size terms, DataHash's carried preimage and BuildBlockContext's exact BaseFee layout."""
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            extract(ROOT / "spec" / "M3" / "lib" / "go_frontend.json", t / "m3")
            self.assertEqual((t / "m3" / "morph_blob.go.extracted.json").read_bytes(),
                             (ROOT / I.GO_DOC).read_bytes())
            extract(ROOT / "spec" / "M2" / "lib" / "go_frontend.json", t / "m2")
            for p in sorted((t / "m2").glob("*.go.extracted.json")):
                self.assertEqual(p.read_bytes(), (ROOT / "spec" / "M2" / "facts" / p.name).read_bytes(), p.name)
            extract(CONFIG03, t / "o3")
            self.assertEqual((t / "o3" / DOC03.name).read_bytes(), DOC03.read_bytes())
        d = load(DOC03)
        self.assertEqual(d["extraction"]["frontend_version"], "holon-go/0.3")
        fs = d["go"]["functions"]
        for fn, (p, q) in zip(ESTIMATORS, ((0, 3), (4, 7))):
            self.assertEqual(fs[fn]["paths"][p]["returns"][0], ["bool", False], fn)
            self.assertTrue(size_term(fs[fn]["paths"][q]["returns"][0], ZSTD), fn)
        (lb,) = fs["(*morph-l2/common/batch.BatchData).DataHash"]["loop_bodies"]
        self.assertEqual([c["name"] for c in lb["carried"]], ["bz"])
        cont = [p for p in lb["paths"] if p["end"] == "continue"]
        self.assertTrue(cont and all(p["updates"]["bz"][:2] == ["append", ["carried", "bz"]] for p in cont))
        self.assertTrue(all(p["updates"]["bz"][2][:2] == ["slice", ["field", ["param", "cks"], "blockContexts"]]
                            for p in cont))
        exits = [p for p in lb["paths"] if p["end"] == "return" and p["returns"][0][:2] == ["call", KECCAK]]
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["returns"][0][2], [["varargs", [["append", ["carried", "bz"],
                                                                   ["field", ["param", "cks"], "l1TxHashes"]]]]])
        ents = [e for e in d["go"]["codecs"]["encoders"] if e["function"] == "morph-l2/common/batch.BuildBlockContext"]
        self.assertEqual([e["exact"] for e in ents], [True, True])
        self.assertEqual(ents[1]["cells"][16:48],
                         [["byte", ["field", ["param", "header"], "BaseFee"], k] for k in range(32)])


class TestLaws(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basis = load(GOX / "basis.json")
        cls.registry = load(ROOT / "laws" / "M3" / "REGISTRY.json")

    def law_ids(self, sub: str) -> list:
        return sorted(e["law_id"] for e in self.basis["elements"] if e["subform"] == sub and e.get("law_id"))

    def test_p2_d3_round_trips_are_proved(self):
        """I93-P2 (G4): exactly two go_round_trip laws, BuildBlockContext's two exact entries against
        HeightFromBlockContextBytes, both PROVED (no premise)."""
        ids = self.law_ids("go_round_trip")
        self.assertEqual(ids, [f"L_par_gort_BuildBlockContext_HeightFromBlockContextBytes_{k}" for k in (0, 1)])
        for lid in ids:
            r = record(lid)
            self.assertEqual(r["status"], "PROVED", lid)
            self.assertEqual(r["premises"], [], lid)

    def test_p3_o5_the_estimators_short_cuts_are_refuted(self):
        """I93-P3 (G5, G9, G10): exactly two go_branch laws, one per estimator (none for their caller, none for the
        compressors' empty-input returns), both REFUTED under HypZ_len at maxBlobCount 1 with |X| = C = 126976 in the
        last slice operand; the replay on the real zstd agrees: the estimator answers (false, nil) and enc's output is
        126984 bytes."""
        ids = self.law_ids("go_branch")
        self.assertEqual(ids, ["L_par_gobr_BatchData_EstimateCompressedSizeWithNewPayload_p0_p3",
                               "L_par_gobr_BatchData_WillExceedCompressedSizeLimit_p4_p7"])
        for lid in ids:
            r = record(lid)
            self.assertEqual(r["status"], "REFUTED", lid)
            self.assertTrue(any("HypZ_len" in json.dumps(p) for p in r["premises"]), lid)
            w = r["witness"]
            self.assertEqual(w["maxBlobCount"], 1, lid)
            self.assertEqual(w["payload_length"], 126976, lid)
            rp = load(REPLAY / f"{lid}.json")
            self.assertEqual(rp["verdict"], "agree", lid)
            self.assertEqual(rp["witness_sha256"], r["witness_sha256"], lid)
            self.assertEqual(rp["observed"]["returns"], [False, None], lid)
            self.assertEqual(rp["observed"]["enc_length"], 126984, lid)

    def test_p4_o6_the_legacy_data_hash_is_refuted(self):
        """I93-P4 (G6, G9, G10): the data_hash role gives DataHash a law, REFUTED by one appended 60-byte context and no
        L1 message (a 58-byte Go preimage; every on-chain preimage has 10 + 32n bytes), replayed in both languages
        with differing digests; DataHashV2 has no law, reason alloc_preimage."""
        els = {e["function"]: e for e in self.basis["elements"] if e["subform"] == "go_recompute"}
        self.assertEqual(sorted(els), ["(*morph-l2/common/batch.BatchData).DataHash",
                                       "(*morph-l2/common/batch.BatchData).DataHashV2"])
        self.assertEqual(els["(*morph-l2/common/batch.BatchData).DataHashV2"].get("reason"), "alloc_preimage")
        lid = els["(*morph-l2/common/batch.BatchData).DataHash"]["law_id"]
        self.assertEqual(lid, "L_par_gorc_data_hash_BatchData_DataHash")
        r = record(lid)
        self.assertEqual(r["status"], "REFUTED")
        self.assertEqual(r["witness"]["appends"], 1)
        self.assertEqual(r["witness"]["go_preimage_length"], 58)
        rp = load(REPLAY / f"{lid}.json")
        self.assertEqual(rp["verdict"], "agree")
        self.assertEqual(rp["witness_sha256"], r["witness_sha256"])
        self.assertNotEqual(rp["observed"]["go_digest"], rp["observed"]["solidity_digest"])

    def test_p5_the_catalog_holds_exactly_the_five_laws(self):
        """I93-P5 (G3, G7): M3's catalog is the next version (expected holon-rules/1.15), the registry gains exactly the
        five laws of thresholds.law_ids over the base, and every base statement keeps its hash."""
        th = key()["thresholds"]
        # I100 (amended, spec/M3/amendments/I93.jsonl): I100's catalog holon-rules/1.16 adds its twelve laws; I93's
        # five are checked as before
        i100 = json.loads((ROOT / "spec" / "M3" / "predictions" / "I100.json").read_text())["thresholds"]
        cv = self.registry["rule_catalog_version"]
        self.assertIn(cv, (th["catalog_expected"], i100["catalog_expected"]))
        later = set(i100["constant_read_laws"]) | set(i100["record_laws"]) if cv == i100["catalog_expected"] else set()
        stm = self.registry["statements"]
        new = sorted(set(stm) - set(th["base_statement_hashes"]))
        self.assertEqual(new, sorted(set(th["law_ids"]) | later))
        for lid, h in th["base_statement_hashes"].items():
            self.assertEqual(stm.get(lid), h, lid)


class TestRegressions(unittest.TestCase):
    def test_r1_earlier_outputs_do_not_move(self):
        """I93-R1: the inputs of thresholds.inputs_sha256 keep their sha256 (I67's 0.2 document, the Solidity Rollup
        document, I91's compression sidecar and oracle results)."""
        for rel, h in key()["thresholds"]["inputs_sha256"].items():
            self.assertEqual(sha256(ROOT / rel), h, rel)

    def test_r2_own_commits_touch_nothing_forbidden(self):
        """I93-R2: I93's own commits (the non-merge commits of git log --first-parent <C_K>..<end>, end the oldest commit
        adding docs/iterations/I93.md, HEAD while there is none) write no frozen root and no other key's prediction,
        prompt or contract file."""
        def git(*a):
            return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout
        ck = git("log", "--diff-filter=A", "--format=%H", "--", f"spec/M3/predictions/{KEY}.json").split()[-1]
        added = git("log", "--first-parent", "--diff-filter=A", "--format=%H", f"{ck}..HEAD", "--",
                    f"docs/iterations/{KEY}.md").split()
        end = added[-1] if added else "HEAD"
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                  "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py")
        others = re.compile(r"^(spec/M\d/predictions/(?!I93\.json)|prompts/(?!I93_)|tests_m3/test_(?!go_laws\.py))")
        for c in git("log", "--first-parent", "--no-merges", "--format=%H", f"{ck}..{end}").split():
            for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", c).split("\n"):
                if f:
                    self.assertFalse(f.startswith(frozen), f"{c[:8]}: {f}")
                    self.assertFalse(others.match(f), f"{c[:8]}: {f}")

    def test_r3_prereg_audits_pass(self):
        """I93-R3: holon audit prereg passes for M3 and M2 at HEAD."""
        for m in ("M3", "M2"):
            p = subprocess.run(["python", "-m", "holon", "audit", "prereg", "--milestone", m], cwd=str(ROOT),
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])

    def test_r4_own_code_names_no_target(self):
        """I93-R4 (G12): no holon/ file names a target identifier of the three laws (names holon/ held at the base,
        such as the batch type and the commit action, are left out)."""
        names = ("BuildBlockContext", "HeightFromBlockContextBytes", "EstimateCompressedSizeWithNewPayload",
                 "WillExceedCompressedSizeLimit", "CompressBatchBytes", "DataHashV2", "blockContexts", "l1TxHashes",
                 "BaseFee", "126976")
        for p in (ROOT / "holon").rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            for n in names:
                self.assertNotIn(n, text, f"{p.relative_to(ROOT)} names {n}")


if __name__ == "__main__":
    unittest.main()
