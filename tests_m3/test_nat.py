"""I29: rule NAT over I28's versioned machine: naturality squares across the deployed path's MIG edges for the operations
that read an in-flight type, composition coherence of the path's initializers, and native equivalence as generated gap
records (whitepaper §5.3 NAT (a)-(c), Thm 6.7 (c), §8.4's NAT row, §11.3 O13, O14, O18; BUILD_PLAN I29). This docstring
is the contract.

Scope. I28 built the versioned machine of the Rollup's deployed path (V3 .. V11, 8 MIG edges, the entry edge from the
proxy's placeholder) with its in-flight types: the in-flight entries of kind retyped or reinterpreted of the path's MIG
edges (I28 rule V3; I28's prereg docstring: "a downgrade's native equivalence over in-flight types is NAT's, I29"). I29
reads I28's outputs and never writes them: rule NAT's basis over the versioned document, its laws stated over the
versioned layer (gen/M3/versions/models/), their decision by the versioned machine and Bend, their witnesses replayed on
the real code through I28's versioned harness, and the native-equivalence obligations the machine cannot state, as gap
records.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an instrument_inconsistency line of
spec/M3/amendments.jsonl): tests_m3/_i29.py (rules N1-N5 written a second time, independently of holon/: it reads only
the committed JSON documents); spec/M3/lib/nat.json (the sidecar: outputs, the model module's name, the search order and
budget, the argument and caller rules, the gap metadata, replay settings; no outcome).

Inputs, read and never written (I28's outcome paths): spec/M3/lib/versions.json, gen/M3/versions/morph_rollup.versions.json
(the versioned document), gen/M3/versions/documents/<version>.json, gen/M3/versions/models/ (the versioned layer and
its version modules, with morph_rollup.versions.init.json), gen/M3/sorts/models/morph_rollup.extracted.init.json (the
deployment record), and holon/versions/ (I28's machine, layer literals and harness, which I29 calls and never edits).

Basis (N1-N4; tests_m3/_i29.py::basis over the versioned document and the per-version documents it lists)
  N1 Initializers. The introduced initializers of the deployed path are the "introduced" entries of the versioned
     document's entry edge (from the placeholder) and of its MIG edges, each (edge, function, reinitializer version), in
     path order.
  N2 Composition (whitepaper §5.3 (c): reachable migration sequences coincide). For each ordered pair of introduced
     initializers (f_i at edge e_i, version v_i) and (f_j at MIG edge e_j = a -> b, version v_j) with v_i < v_j, and f_i an
     action of a's document and of b's document with one selector: one basis element {"law_id":
     "L_nat_comp_<contract>_<f_i>_<f_j>", "subform": "composition", "edge": "<a>-><b>", "op": f_i, "early": {"edge",
     "function", "version"} (e_i, f_i, v_i), "late": (e_j, f_j, v_j)}. Its square: f_i applied before e_j's migration
     (as a call at a) against after it (as a call at b).
  N3 Naturality (§5.3 (b): eta . op^k = op^(k+1) . eta). For each in-flight type t of the versioned document (edge a -> b,
     entry, kind, reads): its touched words at b are "*" for kind reinterpreted, and for kind retyped the members of b's
     layout of the entry (the document's storage record "fields") whose (slot, offset) holds no member of a's layout of
     t's read with the same name and type (sorted; "*" when either layout has no fields). A reader is an action of b's
     document that reads the touched words: a read is a maximal member/map selection chain over a state term of the
     family (["storage", F], or a carried/exit/store wrapper of one), a bare state term being a whole read; threading
     positions are no read (the action's post; a loop record's carried, next, at_break and exit entries named by a state
     term); a reader reads a touched member, or reads the family or one of its entries whole, or (touched "*") reads the
     family at all. For each reader op with an action of a's document of the same selector: one basis element
     {"law_id": "L_nat_sq_<contract>_<a>_<b>_<label>_<op>", "subform": "naturality", "edge", "op", "entry", "kind",
     "touched"} (label: the entry's label).
  N4 Native gaps (§5.3 (a): op^(k+1)(eta(s)) = op^(k+1)(s^nat)). Native equivalence needs the state the new version's
     code would hold natively for the in-flight object: the touched words as b's writers write them. The versioned
     document defines none (b's writers of the touched words are reached through b's own entry points, whose calls the
     old version's history does not contain when their ABI changed, and a reinterpreted entry's native value is
     external), so each (in-flight type, reader) is a generated gap record {"id":
     "gap:M3:native:<a>-><b>:<entry>:<op>", "kind": "native", "edge", "entry", "in_flight_kind", "touched", "reader",
     "square": the reader's naturality law id or null, "obligation", "question", "status": "open"} (the last three from
     the sidecar's gaps.native), never hand-written.
  Analysis. `python -m holon nat analyze [--check]` writes gen/M3/nat/nat.json: {"nat_version": "holon-nat/0.1",
     "versioned": {"path", "sha256"}, "model", "composition", "naturality", "native_gaps"} (N2-N4 as the instrument's,
     each list sorted by id), and the claims module gen/M3/nat/models/morph_rollup_nat.bend (N6). Exit 0 written, 1
     --check differs, 2 refused (an input missing or not the one the versioned document records). Byte-identical across
     runs.

Laws (N5-N6)
  N5 One holon-ir/0.3 law per basis element of N2 and N3: {"ir_version", "law_id", "milestone": "M3", "rule": "NAT",
     "subform": "composition" | "naturality", "rule_catalog_version", "facts": the versioned document's path,
     "facts_sha256", "notes", "statement": tests_m3/_i29.py::expected_statement}: binders s: Reach (a reachable state of
     the versioned machine), a: Act (the op's call: its arguments and caller), u: Act (a migration step of the edge:
     upgradeTo, or upgradeToAndCall with an initializer the edge introduces, with its arguments and environment), e: Env
     (the op's environment), one Fn<Bytes,Word> per hash function a's or b's document applies; the claim
     {"eq": [{"square": "<model>:square:<a>:<b>:<op>", "on": [a, u, s, e]}, {"bool": true}]}, scope unbounded; no
     "evidence", no "predicted". The square term (additive in spec/schemas/law_ir_0_3.schema.json, docs/adoption/Q4/
     following it byte for byte; its statement ref square:<id> hashes the basis element and a's and b's documents, by
     sha256, recomputed from the versioned document) is the Bool: from s, the migration u then the op at b (left) and the
     op at a then u (right) end in the same version and the same storage (every slot either side's storage list holds
     reads the same word), the op succeeds on the left iff it does on the right, and u succeeds on the left iff it does
     on the right (definedness included, §5.1's reading of an equation).
  N6 The claims module gen/M3/nat/models/morph_rollup_nat.bend imports the versioned layer as M, holds one claim function
     per law (its arguments: the state, the op's arguments as layer values in parameter order, the caller word, the
     environment, the edge's migration choice M.UC_<a>_<b>, and one table per hash binder) and the equalities it uses,
     and no law and no escape hatch. A law's LAWS.bend (gen/M3/laws/<id>/LAWS.bend) imports the layer as M and the
     claims module as N and states, for every table, state s with r: M.VReach<tables, s>, argument, caller, environment
     and migration, that the claim function is True{} (the counter-law: exs and !=, named cl_<id lowercased>).

Decision, records, replay (N7-N9)
  N7 `python -m holon run --milestone M3 --laws <ids>` decides the NAT laws it names (holon.__main__ routes them, as I28
     routes the PAR-init laws; the list's other laws go on as before). The search (sidecar search): traces from vr0 by
     length up to max_trace, breadth first, a state already reached not expanded again; the candidate steps at a state
     are the migration along the path's next edge (upgradeToAndCall with each initializer the edge introduces, called
     with I28's upgrade-path arguments, initialize4's expected index the state's lastCommittedBatchIndex; then
     upgradeTo), then the deployment record's calls whose selector names an action of the state's version, each by its
     recorded caller with its recorded calldata. At every state at the square's version a, the op's candidate calls
     (sidecar search.op_calls) and the edge's candidate migrations (as above) are tried in order with I28's A-env; a
     witness is the first whose claim is false on the versioned machine (holon.versions.machine). Its counter-law
     PROOF.bend (gen/M3/proofs/<id>/PROOF.bend, importing LAWS.bend as Laws, the layer and the claims module) holds the
     trace's states, steps and step equations (I28's shape), the reachability of the trace's last state, the witness's
     values, and the claim false there by computation; Bend accepts it (BendTT too when the verdict is enabled): REFUTED
     (AGENTS rule 6). Otherwise UNKNOWN with what was tried (the bound, the states, the candidates) and, for a
     naturality law, the reason the search cannot reach an in-flight object (the model debt of a's successor-site
     actions, from the versioned model's init.json). No generator proves a NAT law.
  N8 Records: results/M3/<id>.json with the M3 record fields (v1 and v2 valid), "rule": "NAT", the subform, artifacts
     laws, proof (REFUTED only) and model, no lean4 entry (no Lean emitter reads the versioned document), and "witness":
     {"trace": [step], "square": {"edge", "op", "left": [migration step, op step at b], "right": [op step at a,
     migration step]}} for a REFUTED record, each step in I28's trace format with "ok". Its "replay" field is the NAT
     replay's (N9). holon refute's final filter gives each REFUTED record a concretization and a bin (I40) from its
     replay runs.
  N9 `python -m holon nat replay [--check]` writes replay/M3/nat/report.json {"replay_version": "holon-nat-replay/0.1",
     "toolchain", "implementations", "runs": [I28's run format]}: for every REFUTED NAT record two runs through I28's
     versioned harness on the real code, "<id>:left" (the trace, then the left steps) and "<id>:right" (the trace, then
     the right steps), each with I28's per-step comparison (statuses, revert data, the words of every written slot); a run
     passes when model and real agree at every step. G6 binds every REFUTED NAT record to its two passed runs (the
     witness's sha256), and the record's replay field says so; a disagreement is reported, never smoothed.

Catalog and derive (N10)
  holon/rules/__init__.py: CATALOGS gains "holon-rules/1.8" (holon-rules/1.7 is I71's, UNDO cancel): every rule and
  producer of the catalog M3 derives with when I29 builds (the same objects), plus "NAT": {"composition": ..,
  "naturality": ..} (holon/rules/nat.py: PRODUCERS, SUBFORMS in that order); catalog_version("M3") is holon-rules/1.8 (or
  a later version holding NAT's producers as the same objects); M2's and the test milestones' catalogs are unchanged. If
  another key holds holon-rules/1.8 when I29 merges, I29 takes the next free version and whoever merges second
  regenerates. Re-deriving M3 changes every earlier M3 law only in rule_catalog_version, each change a
  catalog_rederivation line of laws/STATEMENT_DIFF.jsonl; the NAT laws are bound in spec/bindings/M3.json (G2).

Own commits. C_K is the first commit, oldest first, whose spec/M3/predictions.json holds the key I29; end is the oldest
commit reachable from HEAD that adds docs/iterations/I29.md, else HEAD. I29's own commits are the non-merge commits of
`git log --first-parent C_K..end` when C_K is on end's first-parent chain; none otherwise (a line that merged the prereg
but not the build). The branch reaches the lead only as the second parent of a merge commit and merges only the lead.

Shared files, changed only so (not outcome paths): laws/M3/ (rule_catalog_version, REGISTRY.json, DERIVATION.json),
laws/STATEMENT_DIFF.jsonl (catalog_rederivation lines), spec/bindings/M3.json and changes.jsonl, the M3 records the
catalog moves (re-made on CI runners, statuses unchanged), results/M1, results/M2 and results/T32 (generator_sha256 and
seconds only: holon/rules/__init__.py is in their generator closures), results/M3/metrics.json and summary.json,
gen/M3/evidence.json, spec/schemas/law_ir_0_3.schema.json and docs/adoption/Q4/ (the square term), I40's outputs for
the new records, and the shared holon modules that route, bind, gate and filter the NAT laws (holon/__main__.py,
holon/ir.py, holon/gen/refs.py, holon/bindings.py, holon/gate.py, holon/refute_m3.py, holon/records.py).
Commit rules: no own commit writes gen/M3/versions/, gen/M3/history/, results/M3/history/, replay/M3/versions/,
holon/versions/ or a frozen root.

Commands
  python -m holon nat analyze|replay [--check]
  python -m holon derive --milestone M3                (catalog holon-rules/1.8: the NAT laws)
  python -m holon run --milestone M3 --laws <ids>      (N7)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

import tests_m3._i29 as I
from tests_m3._m3 import ROOT, file_sha256, holon_module, item, laws, load_json, predictions, run_bend, validate

M3 = "M3"
KEY = "I29"
REPORT = "docs/iterations/I29.md"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "nat.json"
ANALYSIS = "gen/M3/nat/nat.json"
MODULE = "gen/M3/nat/models/morph_rollup_nat.bend"
REPLAY = "replay/M3/nat/report.json"
IR03 = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
V2SCHEMA = ROOT / "spec" / "schemas" / "result_record_v2.schema.json"
V1SCHEMA = ROOT / "schemas" / "result_record.schema.json"
CATALOG = "holon-rules/1.8"
NAT_RULE = "NAT"
ESCAPES = re.compile(r"\?[A-Za-z_]\w*|\?TODO|@unsafe|\bdef\s+\w+\?\s*\(|import\s+\"[^\"]*\.c\"")
CATALOG_RE = re.compile(r"^holon-rules/1\.(\d+)$")
# the predicted ids (P1-P3): read at the prereg from I28's build outputs by the instrument (thresholds.basis)
COMPOSITION = ["L_nat_comp_Rollup_initialize2_initialize3", "L_nat_comp_Rollup_initialize2_initialize4",
               "L_nat_comp_Rollup_initialize3_initialize4", "L_nat_comp_Rollup_initialize_initialize2",
               "L_nat_comp_Rollup_initialize_initialize3", "L_nat_comp_Rollup_initialize_initialize4"]
NATURALITY = ["L_nat_sq_Rollup_V10_V11_batchDataStore_proveState",
              "L_nat_sq_Rollup_V10_V11_submitterContract_challengeState",
              "L_nat_sq_Rollup_V10_V11_submitterContract_proveState"]
FORBIDDEN_OWN = ("gen/M3/versions/", "gen/M3/history/", "results/M3/history/", "replay/M3/versions/", "holon/versions/",
                 "facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                 "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")


# ---------------------------------------------------------------------------------------------- helpers
def need(rel: str) -> Path:
    p = ROOT / rel
    if not p.exists():
        raise AssertionError(f"{rel} is missing (I29 builds it)")
    return p


def git(*args) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I29")


def end_commit() -> str:
    cs = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", REPORT).split()
    return cs[0] if cs else git("rev-parse", "HEAD").strip()


def own_commits() -> list:
    """[(sha, [paths])] of I29's own commits, oldest first (the contract's 'Own commits')."""
    c, end = prereg_commit(), end_commit()
    if c not in git("rev-list", "--first-parent", end).split():
        if (ROOT / REPORT).exists():
            raise AssertionError(f"{REPORT} exists but the prereg commit is not on its first-parent chain")
        return []
    out, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-only",
                  f"{c}..{end}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            out.append(cur)
        elif ln.strip() and cur is not None:
            cur[1].append(ln.strip())
    return out


def show(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except (AssertionError, ValueError):
        return None


def basis() -> dict:
    _rel, vd, docs = I.versioned()
    return I.basis(vd, docs)


def record(lid: str) -> dict:
    return load_json(need(f"results/{M3}/{lid}.json"))


def nat_laws() -> dict:
    return {k: v for k, v in laws(M3).items() if v.get("rule") == NAT_RULE}


def steps_ok(steps) -> list:
    return [bool(s.get("ok")) for s in steps]


# ---------------------------------------------------------------------------------------------- prereg
class TestPrereg(unittest.TestCase):
    def test_key_sidecar_and_instrument(self):
        """Construction: the key names this file, the prompt and the sidecar; the instrument's sha256 and this docstring's
        are the key's (thresholds), so a later edit to either shows."""
        k = predictions(KEY)
        self.assertIn("tests_m3/test_nat.py", k["tests"])
        self.assertTrue((ROOT / k["prompt"]).is_file())
        side = load_json(SIDECAR)
        self.assertEqual(side["nat_version"], "holon-nat/0.1")
        th = k["thresholds"]
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i29.py"), th["instrument_sha256"])
        import hashlib
        self.assertEqual(hashlib.sha256((__doc__ or "").encode()).hexdigest(), th["contract_docstring_sha256"])
        self.assertEqual(sorted(th["basis"]["law_ids"]), sorted(COMPOSITION + NATURALITY))


# ---------------------------------------------------------------------------------------------- basis and laws
class TestBasis(unittest.TestCase):
    def test_c1_the_analysis_is_the_instruments(self):
        """Construction (N1-N4): gen/M3/nat/nat.json holds the instrument's basis and gaps over the committed versioned
        document, each gap with the sidecar's obligation and question and status open; --check reproduces it."""
        doc = load_json(need(ANALYSIS))
        bs = basis()
        rel, _vd, _docs = I.versioned()
        self.assertEqual(doc["nat_version"], "holon-nat/0.1")
        self.assertEqual(doc["versioned"], {"path": rel, "sha256": file_sha256(ROOT / rel)})
        for k in ("composition", "naturality"):
            self.assertEqual(doc[k], bs[k], k)
        meta = load_json(SIDECAR)["gaps"]["native"]
        want = [dict(g, obligation=meta["obligation"], question=meta["question"], status="open")
                for g in bs["native_gaps"]]
        self.assertEqual(doc["native_gaps"], want)
        from tests._util import run_holon
        r = run_holon(["nat", "analyze", "--check"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_c2_the_catalog(self):
        """Construction (N10): holon-rules/1.8 holds every producer of the earlier M3 catalogs as the same objects and
        rule NAT's two producers (holon.rules.nat); M3 derives with it or a later catalog keeping them; M2 unchanged."""
        rules = holon_module("holon.rules")
        nat = holon_module("holon.rules.nat")
        self.assertEqual(list(nat.SUBFORMS), ["composition", "naturality"])
        cat = rules.CATALOGS[CATALOG]
        self.assertEqual(cat["NAT"], {s: nat.PRODUCERS[s] for s in nat.SUBFORMS})
        earlier = [v for v in rules.CATALOGS if CATALOG_RE.match(v) and 1 <= int(CATALOG_RE.match(v).group(1)) < 8]
        for v in earlier:
            for rule, subs in rules.CATALOGS[v].items():
                for s, prod in subs.items():
                    self.assertIs(cat[rule][s], prod, f"{v}: {rule}/{s}")
        cv = rules.catalog_version(M3)
        self.assertGreaterEqual(int(CATALOG_RE.match(cv).group(1)), 8)
        for s in nat.SUBFORMS:
            self.assertIs(rules.CATALOGS[cv]["NAT"][s], nat.PRODUCERS[s])
        self.assertEqual(rules.catalog_version("M2"), "holon-rules/1.0")

    def test_c3_the_nat_laws(self):
        """Construction (N5): laws/M3's NAT laws are exactly the basis's, each IR as N5 states (the instrument's
        statement), valid against IR 0.3, with M3's catalog version; DERIVATION.json lists each with its element."""
        bs = basis()
        got = nat_laws()
        self.assertEqual(sorted(got), I.law_ids(bs))
        rel, _vd, docs = I.versioned()
        side = load_json(ROOT / I.VERSIONS_SIDECAR)
        cv = holon_module("holon.rules").catalog_version(M3)
        dv = load_json(need(f"laws/{M3}/DERIVATION.json"))
        entries = {e["law_id"]: e for e in dv.get("laws") or [] if e.get("rule") == NAT_RULE}
        for el in bs["composition"] + bs["naturality"]:
            law = got[el["law_id"]]
            self.assertEqual(validate(law, IR03), [], el["law_id"])
            self.assertEqual((law["ir_version"], law["milestone"], law["rule"], law["subform"], law["facts"],
                              law["facts_sha256"], law["rule_catalog_version"]),
                             ("holon-ir/0.3", M3, NAT_RULE, el["subform"], rel, file_sha256(ROOT / rel), cv))
            self.assertEqual(law["statement"], I.expected_statement(side["model"], el, docs))
            self.assertNotIn("evidence", law)
            self.assertNotIn("predicted", law)
            self.assertEqual(entries[el["law_id"]]["basis"], el)

    def test_c4_the_law_files(self):
        """Construction (N6): the claims module and every NAT law's LAWS.bend have N6's shape: imports, no law in the
        module, no escape hatch anywhere, the law's name and its claim function."""
        mod = need(MODULE).read_text()
        self.assertIsNone(ESCAPES.search(mod))
        self.assertNotRegex(mod, r"(?m)^law ")
        self.assertRegex(mod, r"(?m)^import \S+morph_rollup_versions\.bend as M$")
        for lid in COMPOSITION + NATURALITY:
            txt = need(f"gen/{M3}/laws/{lid}/LAWS.bend").read_text()
            self.assertIsNone(ESCAPES.search(txt), lid)
            self.assertRegex(txt, r"(?m)^import \S+morph_rollup_versions\.bend as M$")
            self.assertRegex(txt, r"(?m)^import \S+morph_rollup_nat\.bend as N$")
            counter = record(lid)["status"] == "REFUTED"
            self.assertRegex(txt, rf"(?m)^law {'cl_' if counter else ''}{lid.lower()}:$")
            self.assertRegex(txt, r"\{N\.\w+\(s, ")


# ---------------------------------------------------------------------------------------------- predictions
class TestPredictions(unittest.TestCase):
    def test_p1_composition_is_refuted(self):
        """I29-P1: every composition law is REFUTED by a witness of N7's shape: a trace from vr0 of the shortest length
        reaching the edge's source version a, every step successful; on the right, the early initializer's call succeeds
        at a and the migration (upgradeToAndCall with the late initializer) then succeeds; on the left the same migration
        succeeds and the early initializer's call then reverts with OpenZeppelin's initializer guard. Its PROOF.bend
        imports its LAWS.bend as Laws, holds no escape hatch, and Bend accepts it."""
        bs = {x["law_id"]: x for x in basis()["composition"]}
        _rel, vd, _docs = I.versioned()
        for lid in COMPOSITION:
            with self.subTest(law=lid):
                rec = record(lid)
                self.assertEqual(rec["status"], "REFUTED")
                el = bs[lid]
                a, b = el["edge"].split("->")
                w = rec["witness"]
                tr = w["trace"]
                self.assertEqual(len(tr), I.min_length(vd, a))
                self.assertEqual(tr[-1]["version"], a)
                self.assertTrue(all(steps_ok(tr)))
                sq = w["square"]
                self.assertEqual((sq["edge"], sq["op"]), (el["edge"], el["op"]))
                (lm, lb), (ra, rm) = sq["left"], sq["right"]
                for m in (lm, rm):
                    self.assertEqual((m["kind"], m["label"], m["version"], m.get("call")),
                                     ("migrate", f"{a}->{b}", b, el["late"]["function"]))
                self.assertEqual((ra["kind"], ra["action"], ra["version"]), ("call", el["op"], a))
                self.assertEqual((lb["kind"], lb["action"], lb["version"]), ("call", el["op"], b))
                self.assertEqual((ra["caller"], ra["calldata"]), (lb["caller"], lb["calldata"]))
                self.assertEqual(lm["calldata"], rm["calldata"])
                self.assertEqual(steps_ok([lm, lb, ra, rm]), [True, False, True, True])
                self.assertEqual(lb.get("revert"), I.ERROR_INITIALIZED)
                pf = need(rec["artifacts"]["proof"])
                txt = pf.read_text()
                self.assertIsNone(ESCAPES.search(txt))
                self.assertRegex(txt, rf"(?m)^import \S*laws/{lid}/LAWS\.bend as Laws$")
                self.assertIn(f"def Laws.cl_{lid.lower()}(", txt)
                code, out = run_bend([str(pf)])
                self.assertEqual(code, 0, out[-1500:])
                self.assertIn("ALL PROOFS CHECK", out)

    def test_p2_naturality_is_unknown(self):
        """I29-P2: every naturality law is UNKNOWN: no witness within the sidecar's budget and no proof; the record's
        attempts name the search's bound, and its bound names the model debt of the edge's source version's
        successor-site actions (no in-flight object is reachable); no PROOF.bend."""
        for lid in NATURALITY:
            with self.subTest(law=lid):
                rec = record(lid)
                self.assertEqual(rec["status"], "UNKNOWN")
                self.assertIsNone(rec["artifacts"].get("proof"))
                self.assertFalse((ROOT / "gen" / M3 / "proofs" / lid / "PROOF.bend").exists())
                refute = [x for x in rec["attempts"] if x.get("kind") == "refute"]
                self.assertTrue(refute and all(x.get("found") is False for x in refute))
                self.assertIn("debt", rec.get("bound") or "")

    def test_p3_the_witnesses_replay(self):
        """I29-P3: every REFUTED NAT record's witness replays on the real code (N9): its runs <id>:left and <id>:right
        pass; on the real chain the left run's last step reverts with the initializer guard's Error(string) and the right
        run's last two steps succeed; the record's replay field is passed."""
        rep = load_json(need(REPLAY))
        runs = {r["name"]: r for r in rep["runs"]}
        for lid in COMPOSITION:
            with self.subTest(law=lid):
                rec = record(lid)
                if rec["status"] != "REFUTED":
                    self.fail(f"{lid} is {rec['status']}")
                L, R = runs[f"{lid}:left"], runs[f"{lid}:right"]
                self.assertTrue(L["passed"] and R["passed"])
                self.assertEqual(L["steps"][-1]["real"], "revert")
                self.assertEqual(L["steps"][-1]["revert"]["real"], I.ERROR_INITIALIZED)
                self.assertEqual([s["real"] for s in R["steps"][-2:]], ["ok", "ok"])
                self.assertEqual(rec["replay"]["status"], "passed")


# ---------------------------------------------------------------------------------------------- construction
class TestRecords(unittest.TestCase):
    def test_c5_records_are_valid(self):
        """Construction (N8): every NAT law has a record valid against v1 and v2, with rule, subform, artifacts laws and
        model, no lean4 entry; a REFUTED one has a witness with its square, a proof, and a concretization and bin from
        holon refute's filter stage."""
        for lid in COMPOSITION + NATURALITY:
            with self.subTest(law=lid):
                rec = record(lid)
                self.assertEqual(validate(rec, V2SCHEMA), [])
                self.assertEqual(validate(rec, V1SCHEMA), [])
                self.assertEqual((rec["rule"], rec["law_id"]), (NAT_RULE, lid))
                self.assertTrue(rec["artifacts"]["laws"] and rec["artifacts"]["model"])
                self.assertNotIn("lean4", rec.get("kernels") or {})
                if rec["status"] == "REFUTED":
                    self.assertTrue(rec["witness"]["trace"] and rec["witness"]["square"])
                    self.assertTrue(rec["artifacts"]["proof"])
                    self.assertIsInstance(rec.get("concretization"), dict)
                    self.assertIsNotNone(rec.get("filter_bin"))

    def test_c6_g6_binds_the_nat_records(self):
        """Construction (N9): G6 on M3 reports the NAT clause and every REFUTED NAT record bound to its passed runs."""
        import tempfile
        from tests._util import run_holon
        with tempfile.TemporaryDirectory() as d:
            r = run_holon(["gate", "--milestone", M3, "--checks", "G6", "--report", str(Path(d) / "gate.json")])
        g6 = [ln for ln in r.stdout.splitlines() if ln.startswith("G6 ")]
        self.assertEqual(len(g6), 1, r.stdout + r.stderr)
        self.assertRegex(g6[0], r"\d+ REFUTED NAT records bound to passed runs of replay/M3/nat/report\.json")
        self.assertNotRegex(g6[0], r"L_nat_\w+: ")


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_r1_the_o15_analogue(self):
        """I29-R1: the O15 analogue, M1's L_nat_eta2, stays REFUTED."""
        self.assertEqual(load_json(ROOT / "results" / "M1" / "L_nat_eta2.json")["status"], "REFUTED")

    def test_r2_own_commits_move_no_earlier_outcome(self):
        """I29-R2: judged one by one against its first parent, no own commit changes an earlier M3 law (not NAT) but in
        rule_catalog_version, or an earlier M3 record's status; none writes I28's outputs or code or a frozen root; and
        at end, every record directly under results/M1, results/M2 and results/T32 carries a generator_sha256 other than
        at the prereg."""
        own = own_commits()
        if (ROOT / REPORT).exists():
            self.assertTrue(own, "the report exists but I29 has no own commit")
        for sha, paths in own:
            for p in paths:
                self.assertFalse(any(p.startswith(x) for x in FORBIDDEN_OWN), f"{sha[:12]} writes {p}")
                m = re.fullmatch(r"laws/M3/(L\w+)\.json", p)
                if m and not m.group(1).startswith(I.CONTRACT_PREFIX):
                    new, old = show(sha, p), show(f"{sha}^", p)
                    if old is not None and new is not None:
                        old.pop("rule_catalog_version", None)
                        new.pop("rule_catalog_version", None)
                        self.assertEqual(new, old, f"{sha[:12]} changes {p} beyond rule_catalog_version")
                m = re.fullmatch(r"results/M3/(L\w+)\.json", p)
                if m and not m.group(1).startswith(I.CONTRACT_PREFIX):
                    new, old = show(sha, p), show(f"{sha}^", p)
                    if old is not None and new is not None:
                        self.assertEqual(new.get("status"), old.get("status"), f"{sha[:12]} moves {p}'s status")
        if not (ROOT / REPORT).exists():
            self.fail(f"{REPORT} is missing (I29 builds it)")
        c, end = prereg_commit(), end_commit()
        for m in ("M1", "M2", "T32"):
            for p in sorted((ROOT / "results" / m).glob("L*.json")):
                rel = p.relative_to(ROOT).as_posix()
                old, new = show(c, rel), show(end, rel)
                if old is None or new is None:
                    continue
                self.assertNotEqual(new.get("generator_sha256"), old.get("generator_sha256"), rel)

    def test_r3_the_pinit_law_stays_refuted(self):
        """I29-R3: I28's PAR-init law stays REFUTED with its witness (I28-P3)."""
        rec = record("L_pinit_Rollup_importGenesisBatch_committedBatches_17_9")
        self.assertEqual(rec["status"], "REFUTED")
        self.assertTrue(rec["witness"]["trace"])


if __name__ == "__main__":
    unittest.main()
