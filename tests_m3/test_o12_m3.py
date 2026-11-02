"""I33: the O12 intent contract on M3, the typed extracted Rollup (whitepaper §5.9 intent contracts, §9.3 G10;
docs/CASESTUDY.md N2 and O12; BUILD_PLAN §4 I33 and rows I64 (= I33a), I65 (= I33b), I68 and I71; docs/HUMAN_ANSWERS.md
Q4 and Q21). This docstring is the contract.

Scope. I65 registered C_o12 on M2's window view, where the undo pair L_undo_cancel is REFUTED and a ghost-counter bound
over traces is proved. I33 is the contract on M3, the typed model of the extracted Rollup, whose scope law is I71's
L_undo_cancel_Rollup_challengeState_setPause (UNDO, sub-form cancel): REFUTED, its witness through the deposit refund.
On M3 the M2 bound is false as stated (block.timestamp is free per step, F and W are mutable, and before I68 the mapping
slots aliased through the keccak table), so C_o12_m3 bounds the residue of one cancellation locally, the I64 C_t64_ext
shape (the human's Question Q-A asks whether the global form G of BUILD_PLAN I33 is wanted instead; G is a follow-up):

  from a reachable state s, after a successful challengeState x and a successful setPause y,
  (a) N(batchDataStore[k].finalizeTimestamp) moved by at most N(proofWindow) read in s, for every word k;
  (b) N(batchDataStore[k].originTimestamp) did not move;
  (c) N(batchChallengeReward[x's caller]) grew by at most N(x's msg.value).

N(w) is the word read as a natural number, so no sum wraps. It needs no time, parameter, deployment or separation
premise: I68's structural store keys every mapping value by (base slot, key path), so no two keys alias. I33 builds the
typed statement terms (B1), the contract (B3), its derivation into laws/M3 (B4), a typed runner for contract laws on
M3 (B5), a proof class for the residue of two steps (B6), and the integration (B7-B10). I33 lands after I68 and I71: its
build merges them, and every outcome is computed on the structural typed model with I71's scope record.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i33.py (B1, B2's real slot, B8 over tests_m3/_i64.py and tests_m3/_i65.py, B11's
witness shape; independently of holon/) and the fixture tests_m3/fixtures/o12_m3/ (C_o12_m3.json, the contract;
C_o12_m3_tight.json, the refund conjunct without x's msg.value; C_o12_m3_deadline_tight.json, the deadline conjunct
without W; C_o12_m3_open.json, a second true claim for the class).

B1 Typed terms. holon-ir/0.3 gains, additively, six terms over a holon-facts/0.3 document (spec/schemas/
   law_ir_0_3.schema.json lists each in $defs.term.oneOf; docs/adoption/Q4/schemas/ follows it byte for byte, I64's
   K10; each term has exactly the keys below, "member" optional on sread alone):
   - {"sread": F, "keys": [K...], "member": M, "from": S}: a Word, the word at storage family F of the facts at the
     mapping keys K (Word terms, as many as F's mapping depth; [] for a scalar) and, for a struct family, its member M
     (required exactly when F declares fields), in state S; a packed member is its masked field (I68's bit-field
     reading), and a key missing from the store reads 0.
   - {"wnat": W}: a Nat, N(W) = sum over the eight limbs of to_nat(limb_i) * 2^(32 i).
   - {"cmp": C, "args": [A, B]}: a Bool, A C B over Nat terms, C one of "<=", "<", "==".
   - {"ok": X, "from": S}: a Bool, every check of X's action holds from S (the model's chk_<action> is 0).
   - {"is": A, "act": X}: a Bool, X is an act of action A of the facts.
   - {"env": E, "of": X}: a Word, the field E of X's environment (caller, msg_value, block_timestamp, this,
     msg_data_length).
   S is a State term: a Reach binder, or {"step": X, "from": S} (the existing step term: the action's post-state when
   its checks hold, else S). holon.ir.render_term renders each term (sread[F.M](K.., S), N(W), A C B, ok(X, S),
   is[A](X), env.E(X)); holon.gen.refs' closure gives each storage family F a ref storage:<F> (sha256 of the family's
   canonical facts entry) and each action A of an is term a ref action:<A> (sha256 of the action's canonical facts
   entry), so a change to the layout or the action moves the statement hash. A law that uses none of them gets the
   law files, refs and record it got before (generator_sha256 aside).
B2 Emission. For a law over a holon-facts/0.3 document with a structural typed model (holon.sorts.model3, I68's S1-S5),
   the emitter writes one statement helper per distinct term instance in LAWS.bend, beside the law (part of the
   statement: a proof file can neither define nor change them): sread at I68's canonical key (S2: a scalar
   SK{b, 0, Nil}; a struct member SK{b, m.slot, Nil}; a mapping value SK{b, 0, [SP_m{clean(k), m.slot}]}), wnat as a
   Nat sum of limbs, cmp by Nat.is_le, Nat.is_lt and Nat.is_eq, ok by matching X's constructor and testing chk_<A> on
   the state's store, is by the constructor alone, env by the act's environment record. The refuter evaluates the
   helpers through the compiled model. The real slot of a key (tests_m3/_i33.real_slot) is used only to compare with
   real traces: in replay, never in a statement or a proof.
B3 The contract. laws/CONTRACTS/C_o12_m3.json is tests_m3/fixtures/o12_m3/C_o12_m3.json (equal as JSON), valid (K1)
   and registered (K2); laws/CONTRACTS/ then holds C_o12 (M2) and C_o12_m3 (M3) and nothing else. Its L_weak, binders
   s: Reach, x: Act, y: Act, k: Word; premises is[challengeState](x), ok(x, s), is[setPause](y), ok(y, step(x, s));
   claim, with s2 = step(y, step(x, s)): (a) N(f_k@s2) <= N(f_k@s) + N(W@s); (b) N(o_k@s2) == N(o_k@s); (c)
   N(rw[caller(x)]@s2) <= N(rw[caller(x)]@s) + N(msg_value(x)), where f_k and o_k are batchDataStore[k]'s
   finalizeTimestamp and originTimestamp, W proofWindow and rw batchChallengeReward. Its scope is I71's law alone.
B4 The derived law is a law of M3. laws/M3/L_contract_C_o12_m3.json is K3's derivation (facts
   spec/M2/facts/morph_rollup.extracted.json, its sha256 now). `holon derive --milestone M3` writes holon.rules' laws
   as before, then the contract laws (holon/contracts.py, as I65's O4 does for M2), and lists them in
   laws/M3/REGISTRY.json (each statement hash; each facts file with its sha256 in facts_files); DERIVATION.json lists
   the rules' laws only; the rule catalog does not change (no producer is added, so no M3 statement hash moves and no
   catalog_rederivation line is needed). No module of a generator closure imports holon/contracts.py (I64's K5).
B5 The typed runner. `holon run --milestone M3` decides an intended_weak law over a holon-facts/0.3 document on the
   structural typed model (K4: nothing special-cases its id): it emits LAWS.bend (B2), tries the proof class (B6), and
   searches for a counter-example with the typed refuter (holon.sorts.search3's reachable prefixes for s, the actions
   and the corpus key words for x, y and the Word binders); a REFUTED record carries the witness in the typed records'
   shape ({"prefix", the binders' acts and words, "hashes"}) and is replayed on the real Rollup (the typed replay that
   I71's records use: a direct test at the real slots of B2's keys); an UNKNOWN record names the bound searched. The
   run's last step applies the contracts (K5) as on every milestone.
B6 The class residue_bound (holon/sorts/residue.py, tried by the typed runner before the refuter; no other class
   changes). It applies to a law with binders s: Reach, x: Act, y: Act and zero or more Word binders, the four premises
   of B3's shape (is and ok of x from s, is and ok of y from step(x, s)) for two actions of the facts, and a claim that
   is a conjunction of props {eq: [{cmp: C, args: [A, B]}, true]} and {eq: [A, B]} over linear Nat sums whose atoms are
   wnat of sread or env terms at s, step(x, s) or step(y, step(x, s)) and Nat literals. It proves the claim by
   evaluating x's and y's statement chains over the structural store symbolically: the SK frame library (I68's S9:
   sk_eq, sst_same, sst_frame) for every store the claim's keys avoid; a key split on the action's own key words where
   a store's key may meet a claimed key; each passed check's equation carried down the chain (the convoy), so that on
   the success path a checked addition's word is the Nat sum of its operands (Word lemmas: w_add_ok(a, b) gives
   N(w_add(a, b)) = N(a) + N(b); w_le(a, b) iff N(a) <= N(b)); a loop by fuel induction when each iteration stores at
   one key indexed by the induction variable (challengeState's loop at Rollup.sol:489-493: after it, each f_i is f_i +
   W for i in the window but the challenged batch, else unchanged); and I68's bit-field lemmas for packed members.
   Every lemma is proved in the law's PROOF.bend: no axiom, no escape hatch (AGENTS rule 3); the byte-pinned core does
   not change. It searches no strengthening. A law of another shape gets no proof from it; Bend decides every proof it
   writes, and BendTT gives the kernel verdict.
B7 Non-vacuity. A PROVED contract law has premises, so G11V needs its checked inhabitant: a concrete s (a reachable
   prefix from s0), x, y and k satisfying the four premises, found by the typed search, whose LAWS.bend-side
   inhabitant check bend accepts; listed among its attempts (kind "inhabitant") and in its non_vacuity block.
B8 Marks and G10 on M3. K5 applies on M3 in results/M3 (I65's O5: results/M3/extracted_m1 does not exist on M3, so
   results/M3 is the one record directory). With C_o12_m3 proved, I71's record (REFUTED over the contract's facts at
   their current sha256) is marked: filter_bin "intended_bounded" and "intended" {contract C_o12_m3, l_weak
   L_contract_C_o12_m3, replaces: its unmarked filter_bin}; nothing else changes in it. results/M3/contracts.json is
   K5's document (tests_m3/_i33.contracts_doc). G10 in the typed gate (holon.sorts.gate3) passes on M3 and names the
   mark ("C_o12_m3 proved, marks L_undo_cancel_Rollup_challengeState_setPause"); tests_m3/_i33.g10 agrees. The final
   filter of `holon refute --milestone M3` keeps the mark as I65's O6 says (intended.replaces recomputed, the bin kept).
B9 Evidence. GEVID enforces on the derived law as on every M3 law (no exemption): the contract's evidence ["E2"],
   copied by K3, is among the levels the M3 evidence set computes for the law's actions (I72's E2 over the adopted
   transitions documents, gen/M3/evidence.json); the record's evidence fields are those GEVID computes.
B10 Records and bindings. The record is a v1 and v2 record of M3 (G9), its ledger over the structural typed model (I68's
   S8: A-keccak-structural among its model_assumptions), its statement_hash the registry's; spec/bindings/M3.json binds
   it (`holon bind --milestone M3`: a new law, no change entry); its lean4 entry is not_run with reason unsupported_form
   (no Lean emitter covers the B1 terms), and G7 passes over it.
B11 Fixtures. In a copy, each fixture registered beside C_o12_m3 (K2) and decided by derive then run --laws:
   C_o12_m3_tight is REFUTED by the typed refuter with a refund witness (x a challengeState with msg.value >= 1, y a
   setPause(true), s a reachable prefix) replayed on the real Rollup (tests_m3/_i33.witness_problems), and marks
   nothing (its scope law stays marked by C_o12_m3, the least proved id); C_o12_m3_open is PROVED by residue_bound;
   C_o12_m3_deadline_tight needs k in the window, two committed batches, so it is REFUTED with such a witness or
   UNKNOWN with its bound named (recorded, not counted).
B12 Rules. I33 adds one law to M3 (L_contract_C_o12_m3) and no other; changes no other M3 law, no M0-M2 law and no
   record's status; changes I71's record in the mark's two fields alone; adds no rule or producer (holon/rules/ does not
   change); writes no frozen root (AGENTS rule 1); and names no contract or law id of its own in holon/ (C_o12_m3, its
   fixtures' ids, L_undo_cancel_Rollup_challengeState_setPause; AGENTS rule 2). Its outcome paths are narrow:
   laws/CONTRACTS/C_o12_m3.json, laws/M3/L_contract_C_o12_m3.json, results/M3/L_contract_C_o12_m3.json,
   results/M3/contracts.json, gen/M3/laws/L_contract_, gen/M3/proofs/L_contract_ and docs/iterations/I33.md. Its code
   (the terms, the runner, the class, the integration) and the schema's terms are build commits; the M1, M2 and T32
   records change in generator_sha256 and seconds alone when a build commit touches a generator closure. I33's own
   commits are the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit that adds
   docs/iterations/I33.md. Earlier tests amended in this prereg, narrowed to I33's outcomes and logged in
   spec/M3/amendments.jsonl: I64-R1, tests_m3/test_contracts.py::TestRegressions.test_no_contract_on_the_real_milestones
   (the I33 key registers C_o12_m3 on M3, and a results/M3 record may carry the mark exactly when tests_m3/_i33
   .expected_marks licenses it). No other earlier test is amended: one that fails on I33's outcomes is a miss, reported.

Commands
  python -m holon contracts derive|apply --milestone M3 [--check]   K3, K5
  python -m holon derive --milestone M3                             B4 (with the contract law, listed)
  python -m holon run --milestone M3 [--laws ID,..]                 B5, with the last step
  python -m holon gate --milestone M3 [--checks ...]                B8, B9 (G10, GEVID, G7, G11V)
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

from tests_m3._m3 import ROOT, copy_repo, file_sha256, load_json, predictions, run_bend, run_holon, validate

FX = ROOT / "tests_m3" / "fixtures" / "o12_m3"
M = "M3"
FACTS = "spec/M2/facts/morph_rollup.extracted.json"
CID = "C_o12_m3"
LID = f"L_contract_{CID}"
SCOPE = "L_undo_cancel_Rollup_challengeState_setPause"
LAW_IR = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
NEW_TERMS = ("t_sread", "t_wnat", "t_cmp", "t_ok", "t_is", "t_env")
NEW_CLASS = "residue_bound"
# B12: ids of I33's own that holon/ never names (AGENTS rule 2)
OWN_IDS = re.compile(r"C_o12_m3|L_undo_cancel_Rollup_challengeState_setPause")
OUTCOME_PATHS = ("laws/CONTRACTS/C_o12_m3.json", "laws/M3/L_contract_C_o12_m3.json",
                 "results/M3/L_contract_C_o12_m3.json", "results/M3/contracts.json", "gen/M3/laws/L_contract_",
                 "gen/M3/proofs/L_contract_", "docs/iterations/I33.md")
_RUNS: dict = {}


def instrument():
    import tests_m3._i33 as I
    return I


def contract(name=CID) -> dict:
    return load_json(FX / f"{name}.json")


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def git(*args, cwd=ROOT) -> str:
    p = subprocess.run(["git", "-C", str(cwd), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I33 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "--topo-order", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and "I33" in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I33")


def own_commits() -> list:
    """B12: I33's own commits, oldest first, each with the (status, path) pairs it changes against its first parent."""
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", "docs/iterations/I33.md").split()
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


def show(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except AssertionError:
        return None


def holon_ok(args, repo, what):
    p = run_holon(args, cwd=repo, timeout=7200)
    if p.returncode != 0:
        raise AssertionError(f"holon {' '.join(args)} ({what}) failed: {(p.stdout + p.stderr)[-3000:]}")
    return p


def register(repo: Path, c: dict) -> None:
    """Add (or replace) one contract in a copy's laws/CONTRACTS/ and its registry entry (K2)."""
    I = instrument()
    d = repo / "laws" / "CONTRACTS"
    write_json(d / f"{c['id']}.json", c)
    rp = d / "REGISTRY.json"
    reg = load_json(rp) if rp.is_file() else {"registry_version": "holon-contracts-registry/0.1", "contracts": {}}
    reg["contracts"][c["id"]] = {"milestone": c["milestone"], "kind": c["kind"], "sha256": I.content_sha256(c)}
    reg["contracts"] = dict(sorted(reg["contracts"].items()))
    write_json(rp, reg)


def redecide(repo: Path, lids) -> None:
    """In a copy: holon derive --milestone M3 (the contract laws and the registry, B4), then holon run --milestone M3
    --laws <lids>, whose last step applies the contracts (K5)."""
    holon_ok(["derive", "--milestone", M], repo, "derive")
    holon_ok(["run", "--milestone", M, "--laws", ",".join(lids)], repo, "run")


def gate(repo, checks):
    out = Path(tempfile.mkdtemp(prefix="i33-gate-")) / "gate_M3.json"
    p = run_holon(["gate", "--milestone", M, "--checks", checks, "--report", str(out)], cwd=repo, timeout=7200)
    rep = load_json(out) if out.is_file() else {}
    shutil.rmtree(out.parent, ignore_errors=True)
    return p, rep


def line(rep, check) -> dict:
    c = (rep.get("checks") or {}).get(check)
    return {"status": "PASS" if c["passed"] else "FAIL", "detail": c.get("detail", "")} if c else {}


def rechecked(test, repo, lid: str, rec: dict) -> None:
    """AGENTS rule 6, independently of the record: its PROOF.bend is accepted by Bend run here, imports exactly its
    LAWS.bend as Laws and states no law of its own; the LAWS.bend states exactly the law the status needs (l_<id> when
    PROVED, cl_l_<id> when REFUTED, lower-cased); and no escape hatch appears in either file (AGENTS rule 3)."""
    status = rec.get("status")
    test.assertIn(status, ("PROVED", "REFUTED"), lid)
    art = rec.get("artifacts") or {}
    proof, laws = (Path(art.get(k) or "") for k in ("proof", "laws"))
    proof, laws = (p if p.is_absolute() else repo / p for p in (proof, laws))
    test.assertTrue(proof.is_file() and laws.is_file(), (lid, art))
    code, out = run_bend([proof.name], cwd=proof.parent, timeout=3600)
    test.assertEqual(code, 0, (lid, out[-1500:]))
    test.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), (lid, out[-1500:]))
    name = ("cl_" if status == "REFUTED" else "") + lid.lower()
    test.assertEqual(re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", laws.read_text(), re.M), [name], lid)
    text = proof.read_text()
    want = Path(os.path.relpath(laws.resolve(), proof.resolve().parent)).as_posix()
    test.assertEqual(re.findall(r"^import\s+(\S+)\s+as\s+Laws\s*(?:#.*)?$", text, re.M), [want], lid)
    for t in (text, laws.read_text()):
        code_only = "\n".join(x.split("#", 1)[0] for x in t.splitlines())
        test.assertIsNone(re.search(r"\?[A-Za-z_]|@unsafe|def\s+\w+\?\s*\(|import\s+\"[^\"]+\.c\"", code_only), lid)
    code_only = "\n".join(x.split("#", 1)[0] for x in text.splitlines())
    test.assertEqual(re.findall(r"(?<![\w.])law\s+[A-Za-z0-9_.]+\s*:", code_only), [], lid)


def copied() -> Path:
    repo = copy_repo()
    _RUNS.setdefault("copies", []).append(repo.parent)
    return repo


def tearDownModule():
    for d in _RUNS.pop("copies", []):
        shutil.rmtree(d, ignore_errors=True)


def record(lid: str, repo: Path = ROOT) -> dict:
    return load_json(repo / "results" / M / f"{lid}.json")


def unmarked(rec: dict) -> dict:
    out = {k: v for k, v in rec.items() if k != "intended"}
    out["filter_bin"] = rec["intended"]["replaces"]
    return out


class TestInstrument(unittest.TestCase):
    """The key pins the instrument, the fixtures and this docstring; the fixtures state B3's bound."""

    def test_the_key_pins_the_instruments(self):
        k = predictions("I33")
        th = k["thresholds"]
        self.assertEqual(th["instrument"], "tests_m3/_i33.py")
        self.assertEqual(th["instrument_sha256"], file_sha256(ROOT / "tests_m3" / "_i33.py"))
        doc = (ROOT / "tests_m3" / "test_o12_m3.py").read_text(encoding="utf-8").split('"""')[1]
        import hashlib
        self.assertEqual(th["contract_docstring_sha256"], hashlib.sha256(doc.encode("utf-8")).hexdigest())
        for name, sha in th["fixtures_sha256"].items():
            self.assertEqual(file_sha256(FX / name), sha, name)
        self.assertEqual(tuple(k["outcome_paths"]), OUTCOME_PATHS)

    def test_the_fixtures_state_the_planned_bound(self):
        """B1 shapes over the facts, the reads B3 names, and the planted differences of the two tight fixtures."""
        I = instrument()
        facts = load_json(ROOT / FACTS)
        c = contract()
        for name in (CID, "C_o12_m3_tight", "C_o12_m3_deadline_tight", "C_o12_m3_open"):
            f = contract(name)
            self.assertEqual(I.term_problems(f["l_weak"], facts), [], name)
            self.assertEqual((f["milestone"], f["rule"], f["facts"], f["scope"]), (M, "UNDO", FACTS, {"laws": [SCOPE]}))
            self.assertEqual(f["l_weak"]["binders"], c["l_weak"]["binders"], name)
            self.assertEqual(f["l_weak"]["assume"], c["l_weak"]["assume"], name)
        self.assertEqual(I.reads({"statement": c["l_weak"]}),
                         [("batchChallengeReward", None, 1), ("batchDataStore", "finalizeTimestamp", 1),
                          ("batchDataStore", "originTimestamp", 1), ("proofWindow", None, 0)])
        a, b, cc = c["l_weak"]["claim"]["all"]
        t = contract("C_o12_m3_tight")["l_weak"]["claim"]["all"]
        d = contract("C_o12_m3_deadline_tight")["l_weak"]["claim"]["all"]
        self.assertEqual((t[0], t[1]), (a, b))
        self.assertNotEqual(t[2], cc)
        self.assertEqual((d[1], d[2]), (b, cc))
        self.assertNotEqual(d[0], a)


class TestTerms(unittest.TestCase):
    """B1, B2: the six terms in the schema and in holon."""

    def test_the_schema_admits_the_terms_and_nothing_looser(self):
        s = load_json(LAW_IR)
        defs = s["$defs"]
        refs = [e.get("$ref") for e in defs["term"]["oneOf"]]
        I = instrument()
        for t in NEW_TERMS:
            self.assertIn(f"#/$defs/{t}", refs, t)
            d = defs[t]
            self.assertFalse(d.get("additionalProperties", True), t)
            key = t[2:]
            self.assertEqual(set(d["required"]), I.NEW_TERMS[key], t)
            self.assertEqual(set(d["properties"]), I.NEW_TERMS[key] | I.OPTIONAL.get(key, set()), t)
        self.assertEqual((ROOT / "docs/adoption/Q4/schemas/law_ir_0_3.schema.json").read_bytes(), LAW_IR.read_bytes())
        law = I.derived_law(contract())
        self.assertEqual(validate(law, LAW_IR), [])
        bad = json.loads(json.dumps(law).replace('"cmp": "<="', '"cmp": ">="', 1))
        self.assertNotEqual(validate(bad, LAW_IR), [])

    def test_render_and_refs(self):
        from holon import ir
        law = instrument().derived_law(contract())
        text = ir.render_statement(law)
        for frag in ("sread[batchDataStore.finalizeTimestamp]", "N(", "is[challengeState]", "ok(", "env.caller",
                     "env.msg_value"):
            self.assertIn(frag, text)
        from holon.gen import refs as R
        facts = load_json(ROOT / FACTS)
        got = R.refs(law, facts, root=ROOT)
        for k in ("storage:batchDataStore", "storage:proofWindow", "storage:batchChallengeReward",
                  "action:challengeState", "action:setPause"):
            self.assertIn(k, got)


class TestContract(unittest.TestCase):
    """B3, B4: the contract and its derived law."""

    def test_the_contract_is_committed_and_registered(self):
        I = instrument()
        c = contract()
        self.assertEqual(load_json(ROOT / "laws" / "CONTRACTS" / f"{CID}.json"), c)
        self.assertEqual(I.problems(c, stem=CID), [])
        reg = load_json(ROOT / "laws" / "CONTRACTS" / "REGISTRY.json")
        self.assertEqual(reg["contracts"][CID], {"milestone": M, "kind": "intended", "sha256": I.content_sha256(c)})
        self.assertEqual(sorted(p.stem for p in (ROOT / "laws" / "CONTRACTS").glob("C_*.json")), ["C_o12", CID])

    def test_the_derived_law_is_a_law_of_m3(self):
        I = instrument()
        law = load_json(ROOT / "laws" / M / f"{LID}.json")
        self.assertEqual(law, I.derived_law(contract()))
        reg = load_json(ROOT / "laws" / M / "REGISTRY.json")
        entry = reg["statements"].get(LID)
        self.assertIsNotNone(entry, "laws/M3/REGISTRY.json does not list the contract law")
        self.assertEqual(reg["facts_files"].get(FACTS), file_sha256(ROOT / FACTS))
        der = load_json(ROOT / "laws" / M / "DERIVATION.json")
        self.assertNotIn(LID, json.dumps(der))
        self.assertEqual(record(LID)["statement_hash"], entry)


class TestPredictions(unittest.TestCase):

    def test_p1_the_l_weak_is_proved_by_residue_bound(self):
        """I33-P1: L_contract_C_o12_m3 is PROVED on the structural typed model by residue_bound, bend accepting its
        PROOF.bend (rechecked here) and BendTT's verdict checked; its record carries the registry's statement hash and
        A-keccak-structural among its model assumptions."""
        rec = record(LID)
        self.assertEqual(rec["status"], "PROVED", rec.get("attempts"))
        rechecked(self, ROOT, LID, rec)
        self.assertEqual((rec.get("kernel") or {}).get("verdict"), "checked")
        gens = [a.get("generator") for a in rec.get("attempts") or [] if a.get("kind") == "proof" and "error" not in a]
        self.assertEqual(gens[-1:], [NEW_CLASS])
        self.assertIn("A-keccak-structural", rec.get("model_assumptions") or [])

    def test_p2_the_law_is_inhabited(self):
        """I33-P2: its non-vacuity is a checked inhabitant (B7): an attempt of kind inhabitant with exit code 0, and a
        non_vacuity block that names it."""
        rec = record(LID)
        inh = [a for a in rec.get("attempts") or [] if a.get("kind") == "inhabitant"]
        self.assertTrue(inh and inh[-1].get("exit_code") == 0 and "error" not in inh[-1], rec.get("attempts"))
        self.assertEqual((rec.get("non_vacuity") or {}).get("status"), "inhabited")

    def test_p3_the_mark_lands_on_the_scope_record(self):
        """I33-P3: I71's record is marked intended_bounded by C_o12_m3, replacing its unmarked bin, and changes in
        nothing else; results/M3/contracts.json is K5's document; the instrument's marks are the records' marks."""
        I = instrument()
        rec = record(SCOPE)
        self.assertEqual(rec["status"], "REFUTED")
        self.assertEqual(rec["filter_bin"], "intended_bounded")
        self.assertEqual({k: rec["intended"][k] for k in ("contract", "l_weak")}, {"contract": CID, "l_weak": LID})
        self.assertEqual(I.expected_marks(ROOT), {SCOPE: {"contract": CID, "l_weak": LID}})
        self.assertEqual(load_json(ROOT / "results" / M / "contracts.json"), I.contracts_doc(ROOT))
        self.assertNotEqual(unmarked(rec)["filter_bin"], "intended_bounded")

    def test_p4_g10_on_m3_passes_and_names_the_mark(self):
        """I33-P4: G10 passes on M3 from the typed gate and from the instrument, its detail naming C_o12_m3 proved and
        the scope law marked."""
        _, rep = gate(ROOT, "G10")
        got = line(rep, "G10")
        self.assertEqual(got.get("status"), "PASS", rep)
        self.assertIn(CID, got.get("detail", ""))
        self.assertIn(SCOPE, got.get("detail", ""))
        ok, reasons = instrument().g10(ROOT)
        self.assertTrue(ok, reasons)

    def test_p5_the_tight_refund_bound_is_refuted_and_replayed(self):
        """I33-P5: with C_o12_m3_tight registered in a copy, its derived law is REFUTED by the typed refuter with a
        refund witness replayed on the real Rollup (tests_m3/_i33.witness_problems), and it marks nothing: the scope
        record keeps C_o12_m3's mark."""
        repo = copied()
        register(repo, contract("C_o12_m3_tight"))
        redecide(repo, ["L_contract_C_o12_m3_tight"])
        rec = record("L_contract_C_o12_m3_tight", repo)
        self.assertEqual(rec["status"], "REFUTED", rec.get("attempts"))
        rechecked(self, repo, "L_contract_C_o12_m3_tight", rec)
        self.assertEqual(instrument().witness_problems(rec), [])
        self.assertEqual(record(SCOPE, repo)["intended"]["contract"], CID)

    def test_p6_gevid_covers_the_law(self):
        """I33-P6: GEVID passes on M3 with the contract law in it, and the record's computed evidence levels include
        E2 (B9)."""
        _, rep = gate(ROOT, "GEVID")
        self.assertEqual(line(rep, "GEVID").get("status"), "PASS", rep)
        self.assertIn("E2", record(LID).get("evidence_levels") or [])

    def test_p7_the_deadline_tight_bound(self):
        """I33-P7 (recorded, not counted): with C_o12_m3_deadline_tight registered in a copy, its derived law is
        REFUTED with k in the window of a two-commit prefix, or UNKNOWN with its bound named."""
        repo = copied()
        register(repo, contract("C_o12_m3_deadline_tight"))
        redecide(repo, ["L_contract_C_o12_m3_deadline_tight"])
        rec = record("L_contract_C_o12_m3_deadline_tight", repo)
        self.assertIn(rec["status"], ("REFUTED", "UNKNOWN"))
        if rec["status"] == "REFUTED":
            rechecked(self, repo, "L_contract_C_o12_m3_deadline_tight", rec)
            commits = [s for s in rec["witness"].get("prefix") or []
                       if s.get("action") in ("commitBatch", "commitState", "commitBatchWithProof")]
            self.assertGreaterEqual(len(commits), 2)
        else:
            self.assertTrue(rec.get("bound"))

    def test_p8_the_class_proves_a_second_claim(self):
        """I33-P8 (recorded, a construction check): with C_o12_m3_open registered in a copy, residue_bound proves it."""
        repo = copied()
        register(repo, contract("C_o12_m3_open"))
        redecide(repo, ["L_contract_C_o12_m3_open"])
        rec = record("L_contract_C_o12_m3_open", repo)
        self.assertEqual(rec["status"], "PROVED", rec.get("attempts"))
        gens = [a.get("generator") for a in rec.get("attempts") or [] if a.get("kind") == "proof" and "error" not in a]
        self.assertEqual(gens[-1:], [NEW_CLASS])


class TestRegressions(unittest.TestCase):

    def test_r1_the_catalog_and_laws(self):
        """I33-R1: no producer is added and no M3 law but the contract law is added or changed by an own commit;
        holon/rules/ is not changed by one."""
        for c, changes in own_commits():
            for st, path in changes:
                self.assertFalse(path.startswith("holon/rules/"), (c, path))
                if path.startswith("laws/M3/") and path.endswith(".json") and "/L_" in path:
                    self.assertTrue(path.endswith(f"/{LID}.json"), (c, path))

    def test_r2_records_change_only_as_allowed(self):
        """I33-R2: every M3 record an own commit changes, but the contract law's, keeps its status at the commit's
        first parent; I71's record changes in filter_bin and intended alone; M1, M2 and T32 records change in
        generator_sha256 and keys named seconds alone."""
        def strip(x):
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items() if k not in ("seconds", "generator_sha256")}
            if isinstance(x, list):
                return [strip(v) for v in x]
            return x
        for c, changes in own_commits():
            for st, path in changes:
                if not re.fullmatch(r"results/(M1|M2|M3|T32)/L[^/]*\.json", path) or st != "M":
                    continue
                old, new = show(f"{c}^", path), show(c, path)
                if path.endswith(f"/{LID}.json"):
                    continue
                self.assertEqual(old.get("status"), new.get("status"), (c, path))
                if path.endswith(f"/{SCOPE}.json"):
                    o = {k: v for k, v in old.items() if k not in ("filter_bin", "intended")}
                    n = {k: v for k, v in new.items() if k not in ("filter_bin", "intended")}
                    self.assertEqual(strip(o), strip(n), (c, path))
                elif not path.startswith("results/M3/"):
                    self.assertEqual(strip(old), strip(new), (c, path))

    def test_r3_c_o12_on_m2_stays_proved(self):
        """I33-R3: C_o12 on M2 stays proved and its mark stays; G10 on M2 passes (the instrument's G10 too)."""
        import tests_m3._i65 as I65
        ok, reasons = I65.g10("M2", ROOT)
        self.assertTrue(ok, reasons)

    def test_r4_holon_names_no_i33_id_and_no_frozen_root_changes(self):
        """I33-R4: holon/ names none of I33's ids (AGENTS rule 2), and no own commit touches a frozen root."""
        hits = []
        for p in sorted((ROOT / "holon").rglob("*")):
            if p.is_file() and p.suffix in (".py", ".mjs", ".js", ".json", ".bend", ".go"):
                if OWN_IDS.search(p.read_text(encoding="utf-8", errors="replace")):
                    hits.append(str(p.relative_to(ROOT)))
        self.assertEqual(hits, [])
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                  "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py")
        for c, changes in own_commits():
            for st, path in changes:
                self.assertFalse(path.startswith(frozen), (c, path))


if __name__ == "__main__":
    unittest.main()
