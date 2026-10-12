"""I13: refined sorts I on the M2 fact documents (whitepaper §7.1-§7.4, §7.7 steps 1-4, Thm 6.18 freezing
condition; BUILD_PLAN I13). This docstring is the contract every tests_m2/test_sorts_*.py module reads.

CLI
  python -m holon sorts [--milestone M2] [--root DIR] [--out DIR] [--facts PATH ...]
    Fact documents: holon.diagram.fact_documents(milestone, root) (facts/*.json, spec/M1/facts/*.json, ...),
    unless --facts names documents (repeatable; relative to the current directory or absolute; inside --root).
    Default --root: this checkout. Default --out: <root>/gen/<milestone>/sorts (created if missing). Inputs are read from --root
    only: the fact documents and the libraries and sidecars that apply to them (the diagram may be rebuilt in
    memory with holon.diagram.build). Nothing outside --out is written. Exit 0 whenever the solver ran
    (conflicts are results, not errors); nonzero only when an input is unreadable or holds a construct the
    pass cannot map (no silent drops).
    It writes exactly five files, deterministic (sorted keys, stable ids, no timestamps): constraints.json,
    assignment.json, conflicts.json, unions.json, unresolved.json. Each is a JSON object with the header
      {"document": <file stem>, "sorts_version": "holon-sorts/0.1", "milestone": "M2" (null under --facts),
       "inputs": [{"path": repo-relative, "sha256": hex}]   (every file read, sorted by path)}
    and validates against spec/schemas/sorts.schema.json: "$defs" holds one schema per document (named by
    the stems above) and the top level is a oneOf over them.

Variables (per model; a model is a fact document, named by its file stem)
  For a holon-facts/0.2 document each of these is a key of models[<model>]["assignment"]:
    "<f>"       state field f of type Nat, Bool, List<Nat> or List<Bool> (for a list: its elements)
    "<T>.<g>"   field g, of those types, of a record type T declared in "types"   e.g. "Entry.tot", "Ch.s"
    "<a>.<x>"   input x, of those types, of action a                              e.g. "wait.dt"
  Extra keys are allowed (lets as "<a>.<let>", migration inputs, ...). Every key names a facts binder, never a
  position: auxiliary variables for subterms (an arithmetic node, a call result) may appear in constraints.json
  but are not keys of "assignment". For holon-facts/0.1 documents the keys
  are the implementer's choice, documented in holon/sorts/grammar.py. Plan names map to keys as follows:
  win.bvh is "Entry.bvh" (win : List<Entry>); Ch.start is "Ch.s" (field s of Ch, the BatchChallenge record,
  is its startTime: challengeState writes s := t).

Sort strings (holon.sorts.grammar)
  Time | Dur | SDur | Idx[k] | SIdx[k] | Cnt[k] | SCnt[k] | Prin[role] | Amt[asset] | Dig[kind] | Ver | Bool |
  Mach(w) | <record> | s1 + s2 (+ ...) | "Nat (unrefined)"
  The "S" sorts are the signed sorts of §7.2: Dur^± = SDur, Cnt[k]^± = SCnt[k], Idx[k]^± = SIdx[k]. A
  writer-provenance refinement (§7.3) appends "_<label>" (label: [a-z][a-z0-9]*) to Idx[k] or Cnt[k], e.g.
  "Idx[queue]_fin". A union (§7.4) renders its members in lexicographic order joined by " + ". A variable the
  constraints do not refine is "Nat (unrefined)": nothing is guessed.
  holon.sorts.grammar.parse(text) -> object, render(object) -> text, render(parse(s)) == s for canonical s;
  holon.sorts.grammar.affine(op, a, b) -> sort string | None: the §7.2 table, op "+" or "-"; None = ill-sorted.

constraints.json  header + {"constraints": [{"id": str (unique), "model": str, "kind": "type" | "seed" | "flow"
    | "affine" | "compare" | "link" | "writer", "vars": [variable keys and auxiliary variables], "src": span | null,
    "text": str}]}
  A seed is a unit constraint: "vars" is [its variable], at most one "seed" constraint per (model, variable); it
  lists every ground for that seed (lexical, structural) in "grounds": [str] and names its sort in "sort".
  "affine": one arithmetic node (+ or -) under §7.2; its vars are the node's operands and result, a variable
  operand named directly (never routed through a separate flow constraint; a nested node is an auxiliary
  variable shared by the two affine constraints). "compare": one comparison (==, !=, <, <=, >, >=) of two
  Nat-based terms. Each constraint object carries every field holon.sorts.solve.satisfiable needs (operator,
  operand order, ...); satisfiable decides from the constraint objects alone.
  Span: "<path>:<line>" or "<path>:<line>-<line>", the leading part of a facts "src" string (any text after
  the first line range is dropped: ":636 (_batchIndex - 1, checked)" is ":636"). A constraint's src is the span
  of the facts entry it comes from: its guard or let, else (an effect) the action's effects_src, else the
  action's src; null when there is none.

assignment.json  header + {
    "models": {<model>: {"facts": repo-relative path of the fact document,
                         "assignment": {var: sort},
                         "provenance": {var: {"label": str, "writers": [names, sorted]}}}},
    "sites": [site],
    "sorts_sha256": hex}
  Input hashes appear only under "inputs". provenance has an entry for every variable whose sort carries a
  writer label: the actions and migrations whose effects write the variable (for a record field T.g: whose
  effects contain ["mk", T, {.. g ..}] or ["with", T, _, {.. g ..}]; an opaque builtin that returns records or
  lists of records is not a writer of their fields), and the label derived from that writer set.
  site = {"id": str (unique), "model", "span", "op": "-", "expr": the subtraction exactly as written in the
          facts (DSL JSON; lets not inlined), "sort": sort of the difference, "realized_in": base type ("Nat"),
          "obligation": "sign" | null, "entry_points": [names, sorted], "occurrences": [{"action", "where"}]}
  Sites are keyed by source span: one site per (model, span, expr); occurrences with the same span and
  expression are deduplicated into one site whose entry_points are their distinct actions. The span of a
  subtraction a - b is the narrowest of (i) the span of the facts entry that contains it (its guard or let if
  that has a src, else the action's effects_src for an effect, else the action's src) and (ii) the span of any
  guard of the same action whose require contains, as a subexpression, a comparison implying a - b >= 0
  (b <= a, a >= b, b < a, a > b, !(a < b) or !(b > a)) and whose span lies inside (i) (narrowest: fewest lines;
  a tie goes to the guard listed first in the action). At Rollup.sol the
  three copies of let prt = inch ? W + cstart - t : 0 (src :360-364) are narrowed by the guard
  !inch || t <= W + cstart (src :363) to the span :363.
  "obligation" is "sign" exactly when the sort is signed and realized in Nat (§7.2: a signed sort realized in
  unsigned arithmetic generates a sign obligation). Every subtraction in the guards and effects of every
  action of a 0.2 document is an occurrence of some site. Subtractions inside definitions (facts defs, library
  builtins) may be reported per definition (occurrences name the definition; span: its src, else
  "<model>:<def>") or per call site (occurrences name the calling action), deterministically either way.
  sorts_sha256 = sha256 of the canonical JSON (sorted keys, separators (",", ":"), UTF-8, no ASCII escaping) of
  assignment.json without its "sorts_sha256" and "inputs" keys: the frozen assignment's identity. No M2 registry
  exists yet; when laws/M2/REGISTRY.json is created (I15) its "sorts_sha256" must equal this value.

conflicts.json  header + {"conflicts": [{"id", "model", "kind": "affine" | "base", "src": span
    | null, "text": str, "core": [constraint ids]}]}
  One conflict per clash the solver detects. src: the src of the first "affine" or "compare" constraint in core
  order that has one, else the first non-null src in the core, else null (the planted fixture's conflict is at
  its planted sum). core: a minimal unsatisfiable subset of constraints.json, found by
  deletion (QuickXplain): unsatisfiable under holon.sorts.solve.satisfiable, satisfiable once any one of its
  constraints is removed. kind is "affine" for every conflict whose core contains an "affine" or "compare"
  constraint (every §7.2 violation, mixed index families included). Writes of distinct sorts to one register
  make a union (unions.json), not a conflict.

unions.json  header + {"unions": [{"id", "model", "vars": [keys, sorted], "members": [sorts, sorted], "sort": the
    union sort string, "writers": {member: [names, sorted]}}]}   every listed var is assigned "sort"

unresolved.json  header + {"count": int, "unresolved": [{"model", "var", "base_type", "why"}]}
  exactly the variables assigned "Nat (unrefined)"; count == len(unresolved)

Rules fixed at the prereg (the lead's decisions on the review's open contract points; whitepaper §7.2-§7.4, §7.8)
  R1 Realization (§7.8 realize). Every DSL subtraction is realized in Nat (truncating). A subtraction whose sort
     under §7.2 is signed (SDur, SCnt[k], SIdx[k]) is realized at its site: the site records the signed sort and
     "obligation": "sign"; the value flows on with the unsigned sort (SDur -> Dur, SCnt[k] -> Cnt[k], SIdx[k] ->
     Idx[k]). Assignment values therefore never carry a signed sort, and Time + SDur never arises in flow.
  R2 Base sorts and labels. Flow, affine and compare constraints unify BASE sorts (Time, Dur, Idx[k], Cnt[k],
     Dig[kind], ...); writer labels are not unified by flow. A variable written by actions (or migrations) has
     writer set W(v) (syntactic, as defined under "provenance"); its label is a function of W(v) (R4).
  R3 Writer-provenance refinement (§7.3, "with no value flow between them"). Two registers with the same base sort
     Idx[k] or Cnt[k] and different writer sets get distinct refined sorts, unless value flows each way between
     them (they lie in one strongly connected component of the register flow graph: an edge a -> b for every write
     of b whose written expression reads a, directly or through lets); registers of one such component share one
     label, computed from the union of their writer sets. A one-way copy (b := a) does not merge labels.
  R4 Label names. The only target vocabulary is spec/M2/lib/sort_seeds.json (frozen at the prereg; listed in every
     output's "inputs"): its lexical seed rules, and its writer_labels rules mapping a writer set to a label (a rule
     applies when every writer in the set starts with its prefix; otherwise the documented fallback). holon/sorts/*.py
     holds no target vocabulary of its own.
  R5 Unions (§7.4). A register written along edges whose values have distinct base sorts of one family (Dig[kind1],
     Dig[kind2]; or Idx[k] with distinct labels) carries their union; distinct families (Time vs Dur, Idx[k] vs
     Cnt[k], Idx[k1] vs Idx[k2]) are a conflict. A lexical seed on a register counts as one of its members.
  R6 I13 reports affine (§7.2) conflicts and base-sort conflicts; obligation-coherence conflicts (§7.3) are I15's
     obstructions and are not reported here (kind "coherence" is not emitted in I13).

APIs (also read by test_sorts_unit.py and test_sorts_fixture.py)
  holon.sorts.solve.satisfiable(constraints: list[dict]) -> bool    pure-Python union-find over the rules
  holon.sorts.core.minimal_core(items: list, satisfiable) -> list    see test_sorts_unit.py
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json, validate
from tests_m2._sorts import (FILES, OUT, SCHEMA, SORTS_VERSION, UNREFINED, Run, action_subtractions,
                             canonical_sha256, is_signed, members, required_keys, without)

DOCS = {"morph_header": "facts/morph_header.json",
        "morph_rollup": "spec/M1/facts/morph_rollup.json",
        "morph_batchdata": "spec/M1/facts/morph_batchdata.json"}
M1_MODELS = ("morph_rollup", "morph_batchdata")
ROLLUP = ROOT / DOCS["morph_rollup"]
COMMITS = ("commitBatch", "commitState", "commitBatchWithProof")
SITE_EXPR = ["-", ["+", "W", "cstart"], "t"]          # proofWindow + challenges[batchChallenged].startTime - block.timestamp
SITE_SPAN = "contracts/contracts/l1/rollup/Rollup.sol:363"
CALL_LINES = {"commitBatch": 268, "commitState": 285, "commitBatchWithProof": 411}
SPAN_RE = re.compile(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$")


def facts(model: str) -> dict:
    return load_json(ROOT / DOCS[model])


def morph_checkout() -> tuple[Path | None, str | None]:
    """The morph-l2/morph checkout at the facts' commit: HOLON_MORPH, else config replay.morph (the pin)."""
    pinned = load_json(ROOT / "config" / "holon.json").get("replay", {}).get("morph")
    for c in (os.environ.get("HOLON_MORPH"), pinned):
        if c and (Path(c) / "contracts").is_dir():
            return Path(c), pinned
    return None, pinned


class _Shared(unittest.TestCase):
    sr: Run = None

    @classmethod
    def setUpClass(cls):
        if _Shared.sr is None:
            _Shared.sr = Run(["--milestone", "M2"])

    @property
    def r(self) -> Run:
        return _Shared.sr


class TestSortsContract(_Shared):
    def test_cli_writes_the_five_files_with_their_header(self):
        self.assertEqual(self.r.code, 0, self.r.log)
        self.assertEqual(sorted(self.r.docs), sorted(FILES), self.r.log)
        want_inputs = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in DOCS.values()}
        for name in FILES:
            with self.subTest(file=name):
                d = self.r.doc(name)
                self.assertEqual(d["document"], name)
                self.assertEqual(d["sorts_version"], SORTS_VERSION)
                self.assertEqual(d["milestone"], "M2")
                paths = [i["path"] for i in d["inputs"]]
                self.assertEqual(paths, sorted(paths))
                got = {i["path"]: i["sha256"] for i in d["inputs"]}
                for rel, sha in want_inputs.items():
                    self.assertEqual(got.get(rel), sha, f"{rel} is read and hashed")

    def test_the_only_target_vocabulary_is_the_frozen_seed_sidecar(self):
        """R4: the solver's target vocabulary is spec/M2/lib/sort_seeds.json, frozen at the prereg; every other input
        is a fact document, a target library, or the ledger (instruments are inputs, BUILD_PLAN §0.1)."""
        seeds = "spec/M2/lib/sort_seeds.json"
        allowed = re.compile(r"^(facts/[^/]+\.json|spec/M1/facts/[^/]+\.json|spec/(M[0-9]+/)?lib/[^/]+\.lib\.json|"
                             r"spec/ledger/[^/]+\.json|spec/M2/lib/sort_seeds\.json)$")
        for name in FILES:
            with self.subTest(file=name):
                paths = [i["path"] for i in self.r.doc(name)["inputs"]]
                self.assertIn(seeds, paths)
                self.assertEqual([p for p in paths if not allowed.match(p)], [], "an input outside the frozen set")

    def test_outputs_validate_against_the_sorts_schema(self):
        self.assertTrue(SCHEMA.exists(), SCHEMA)
        schema = load_json(SCHEMA)
        self.assertEqual(set(schema.get("$defs", {})) & set(FILES), set(FILES))
        for name in FILES:
            with self.subTest(file=name):
                self.assertEqual(validate(self.r.doc(name), SCHEMA), [])
                self.assertNotEqual(validate({"document": name}, SCHEMA), [],
                                    "the schema must reject a document without its body (non-vacuous)")

    def test_every_model_and_variable_is_assigned_a_parseable_sort(self):
        G = holon_module("holon.sorts.grammar")
        models = self.r.doc("assignment")["models"]
        self.assertEqual(set(models), set(DOCS))
        for m, rel in DOCS.items():
            with self.subTest(model=m):
                self.assertEqual(models[m]["facts"], rel)
                A = models[m]["assignment"]
                for var, sort in A.items():
                    self.assertEqual(G.render(G.parse(sort)), sort, f"{m}:{var} has a non-canonical sort {sort!r}")
                f = facts(m)
                if f["facts_version"] != "holon-facts/0.2":
                    continue
                for var, ty in required_keys(f).items():
                    self.assertIn(var, A, f"{m}: variable {var} ({ty}) is not assigned")
                    if ty in ("Bool", "List<Bool>"):
                        self.assertEqual(A[var], "Bool", f"{m}:{var}")

    def test_unresolved_lists_exactly_the_unrefined_variables(self):
        models = self.r.doc("assignment")["models"]
        unrefined = {(m, v) for m, mo in models.items() for v, s in mo["assignment"].items() if s == UNREFINED}
        u = self.r.doc("unresolved")
        listed = [(e["model"], e["var"]) for e in u["unresolved"]]
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(set(listed), unrefined)
        self.assertEqual(u["count"], len(listed))

    def test_sorts_sha256_is_the_hash_of_the_frozen_assignment(self):
        a = self.r.doc("assignment")
        self.assertRegex(a["sorts_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(a["sorts_sha256"], canonical_sha256(without(a, "sorts_sha256", "inputs")))
        reg = ROOT / "laws" / "M2" / "REGISTRY.json"
        if reg.exists():  # created by I15; until then the value lives in gen/M2/sorts/assignment.json
            self.assertEqual(load_json(reg).get("sorts_sha256"), a["sorts_sha256"])

    def test_sites_are_keyed_by_span_and_signed_sites_carry_a_sign_obligation(self):
        G = holon_module("holon.sorts.grammar")
        sites = self.r.doc("assignment")["sites"]
        ids = [s["id"] for s in sites]
        self.assertEqual(len(ids), len(set(ids)), "site ids are unique")
        keys = [(s["model"], s["span"], json.dumps(s["expr"], sort_keys=True)) for s in sites]
        self.assertEqual(len(keys), len(set(keys)), "one site per (model, span, expression)")
        for s in sites:
            with self.subTest(site=s["id"]):
                self.assertEqual(s["op"], "-")
                self.assertEqual(s["expr"][0], "-")
                self.assertTrue(isinstance(s["span"], str) and s["span"])
                self.assertEqual(G.render(G.parse(s["sort"])), s["sort"])
                self.assertEqual(s["entry_points"], sorted({o["action"] for o in s["occurrences"]}))
                want = "sign" if is_signed(s["sort"]) and s["realized_in"] == "Nat" else None
                self.assertEqual(s.get("obligation"), want)
        for m in M1_MODELS:
            f = facts(m)
            names = {a["name"] for a in f["actions"]}
            for s in sites:
                if s["model"] == m and {o["action"] for o in s["occurrences"]} <= names:
                    self.assertRegex(s["span"], SPAN_RE, f"{s['id']}: an action site's span is a source span")
            for action, expr in action_subtractions(f):
                with self.subTest(model=m, action=action, expr=expr):
                    self.assertTrue(any(s["model"] == m and s["expr"] == expr
                                        and action in {o["action"] for o in s["occurrences"]} for s in sites),
                                    "every subtraction in an action is an occurrence of some site")

    def test_conflict_cores_reference_constraints_and_affine_kinds_follow_the_core(self):
        cons = {c["id"]: c for c in self.r.doc("constraints")["constraints"]}
        self.assertEqual(len(cons), len(self.r.doc("constraints")["constraints"]), "constraint ids are unique")
        for c in cons.values():
            if c["kind"] == "seed":
                self.assertEqual(len(c["vars"]), 1, f"{c['id']}: a seed is a unit constraint")
        seeds = [(c["model"], c["vars"][0]) for c in cons.values() if c["kind"] == "seed"]
        self.assertEqual(len(seeds), len(set(seeds)), "at most one seed constraint per variable")
        for c in self.r.doc("conflicts")["conflicts"]:
            with self.subTest(conflict=c["id"]):
                self.assertTrue(c["core"])
                for i in c["core"]:
                    self.assertIn(i, cons)
                involved = {cons[i]["kind"] for i in c["core"]}
                self.assertEqual(c["kind"] == "affine", bool(involved & {"affine", "compare"}), involved)

    def test_union_variables_carry_the_union_sort(self):
        models = self.r.doc("assignment")["models"]
        listed = set()
        for u in self.r.doc("unions")["unions"]:
            with self.subTest(union=u["id"]):
                self.assertGreaterEqual(len(u["members"]), 2)
                self.assertEqual(u["members"], sorted(u["members"]))
                self.assertEqual(u["sort"], " + ".join(u["members"]))
                for v in u["vars"]:
                    self.assertEqual(models[u["model"]]["assignment"][v], u["sort"])
                    listed.add((u["model"], v))
        for m, mo in models.items():
            for v, s in mo["assignment"].items():
                if " + " in s:
                    self.assertIn((m, v), listed, f"{m}:{v} carries a union but no union lists it")


class TestPredictions(_Shared):
    def test_time_and_duration_sorts(self):
        """I13-P1: t is Time and wait.dt is Dur; W, F and D are Dur; Ch.start (key Ch.s) is Time."""
        A = self.r.assignment("morph_rollup")
        self.assertEqual(A.get("t"), "Time")
        self.assertEqual(A.get("wait.dt"), "Dur")
        for v in ("W", "F", "D"):
            with self.subTest(var=v):
                self.assertEqual(A.get(v), "Dur")
        self.assertEqual(A.get("Ch.s"), "Time")

    def test_one_signed_duration_site_at_rollup_363(self):
        """I13-P2 (a): W + cstart - t is SDur at one source site, Rollup.sol:363. The M1 facts duplicate the
        guard per action (morph_rollup.json lines 1110, 1502, 2017); deduplication by span yields one site,
        reached from commitBatch, commitState and commitBatchWithProof."""
        lines = [i + 1 for i, line in enumerate(ROLLUP.read_text(encoding="utf-8").splitlines()) if '"site": {' in line]
        self.assertEqual(lines, [1110, 1502, 2017], "premise: the facts carry the guard three times")
        hits = [s for s in self.r.sites("morph_rollup") if s["expr"] == SITE_EXPR]
        self.assertEqual(len(hits), 1, [(s["id"], s["span"]) for s in hits])
        s = hits[0]
        self.assertEqual(s["span"], SITE_SPAN)
        self.assertEqual(s["sort"], "SDur")
        self.assertEqual(s["entry_points"], sorted(COMMITS))
        self.assertEqual(sorted(o["action"] for o in s["occurrences"]), sorted(COMMITS))

    def test_site_and_entry_points_in_the_pinned_source(self):
        """I13-P2 (b): in morph at the facts' commit, the site's line holds the subtraction, inside
        _commitBatchWithBatchData, and each entry point reaches it through exactly one call of
        _commitBatchWithBatchData: commitBatch at :268, commitState at :285, commitBatchWithProof at :411.
        The entry points are read from the sorts output, their source ranges from the facts."""
        s = next((x for x in self.r.sites("morph_rollup") if x["expr"] == SITE_EXPR), None)
        self.assertIsNotNone(s, "no site for W + cstart - t")
        morph, pinned = morph_checkout()
        if morph is None:
            if pinned:
                self.fail(f"config/holon.json pins replay.morph = {pinned}, but no checkout is there")
            self.skipTest("no morph checkout and none pinned in config/holon.json")
        f = facts("morph_rollup")
        if (morph / ".git").exists():
            head = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"], capture_output=True, text=True)
            self.assertEqual(head.stdout.strip(), f["target"]["commit"], "morph checkout is at the facts' commit")
        m = SPAN_RE.match(s["span"])
        self.assertIsNotNone(m, s["span"])
        src = (morph / m["path"]).read_text(encoding="utf-8").splitlines()
        line = int(m["lo"])
        self.assertIn("proofWindow + challenges[batchChallenged].startTime - block.timestamp", src[line - 1])
        start = next(i + 1 for i, x in enumerate(src) if "function _commitBatchWithBatchData(" in x)
        end = next(i + 1 for i, x in enumerate(src) if i + 1 > start and re.match(r"\s*function\s", x))
        self.assertTrue(start < line < end, f"line {line} lies inside _commitBatchWithBatchData ({start}..{end})")
        acts = {a["name"]: a for a in f["actions"]}
        calls = {}
        for e in s["entry_points"]:
            am = SPAN_RE.match(acts[e]["src"].split()[0])
            lo, hi = int(am["lo"]), int(am["hi"] or am["lo"])
            got = [i for i in range(lo, hi + 1) if "_commitBatchWithBatchData(" in src[i - 1]]
            self.assertEqual(len(got), 1, f"{e}: calls of _commitBatchWithBatchData in {lo}..{hi}: {got}")
            calls[e] = got[0]
        self.assertEqual(calls, CALL_LINES)

    def test_queue_cursors_get_distinct_writer_refined_sorts(self):
        """I13-P3: qpend and Entry.tot get distinct sorts, Idx[queue]_fin and Idx[queue]_inc, through writer
        provenance (qpend is written by finalizeBatch only; Entry.tot by the three commit actions: they are the
        only effects holding ["mk", "Entry", ...], and no effect holds ["with", "Entry", ...])."""
        A = self.r.assignment("morph_rollup")
        prov = self.r.model("morph_rollup").get("provenance", {})
        self.assertEqual(A.get("qpend"), "Idx[queue]_fin")
        self.assertEqual(A.get("Entry.tot"), "Idx[queue]_inc")
        self.assertIn("qpend", prov)
        self.assertIn("Entry.tot", prov)
        self.assertEqual(prov["qpend"]["label"], "fin")
        self.assertEqual(set(prov["qpend"]["writers"]), {"finalizeBatch"})
        self.assertEqual(prov["Entry.tot"]["label"], "inc")
        self.assertEqual(set(prov["Entry.tot"]["writers"]), set(COMMITS))

    def test_bvh_registers_form_the_digest_union(self):
        """I13-P4: win.bvh (key Entry.bvh) and s_bvh form the union Dig[VH] + Dig[Agg]."""
        A = self.r.assignment("morph_rollup")
        want = {"Dig[VH]", "Dig[Agg]"}
        for v in ("Entry.bvh", "s_bvh"):
            with self.subTest(var=v):
                self.assertEqual(members(A.get(v, "")), want, A.get(v))
        us = [u for u in self.r.doc("unions")["unions"]
              if u["model"] == "morph_rollup" and {"Entry.bvh", "s_bvh"} <= set(u["vars"])]
        self.assertEqual(len(us), 1, "one union holds both registers")
        self.assertEqual(set(us[0]["members"]), want)

    def test_no_affine_conflicts_on_the_m1_facts(self):
        """I13-P5: 0 SORT-affine conflicts on the M1 facts (spec/M1/facts/*.json): no conflict of kind affine, and
        no conflict whose core holds an affine or compare constraint. Non-vacuity: the rollup arithmetic was
        constrained at all (the :363 site's let prt, src :360-364, yields an affine constraint, and its guard at :363
        a compare constraint); morph_batchdata's actions hold no + or - node."""
        cons = {c["id"]: c for c in self.r.doc("constraints")["constraints"]}
        rollup = [c for c in cons.values() if c["model"] == "morph_rollup"]
        self.assertTrue(any(c["kind"] == "affine" and c["src"] == "contracts/contracts/l1/rollup/Rollup.sol:360-364"
                            for c in rollup), "no affine constraint for let prt (:360-364): 0 conflicts would be vacuous")
        self.assertTrue(any(c["kind"] == "compare" and c["src"] == SITE_SPAN for c in rollup),
                        "no compare constraint for the :363 guard: 0 conflicts would be vacuous")
        bad = []
        for c in self.r.doc("conflicts")["conflicts"]:
            if c["model"] in M1_MODELS:
                kinds = {cons[i]["kind"] for i in c["core"] if i in cons}
                if c["kind"] == "affine" or kinds & {"affine", "compare"}:
                    bad.append((c["id"], c["kind"], c.get("src"), c.get("text")))
        self.assertEqual(bad, [])


class TestSortsFiles(_Shared):
    def test_two_runs_are_byte_identical_and_match_the_committed_files(self):
        """Exit: byte-identical assignments (and every other sorts file) across two runs, equal to the committed
        gen/M2/sorts/ (construction check, not a prediction)."""
        self.assertEqual(self.r.code, 0, self.r.log)
        again = Run(["--milestone", "M2"])
        try:
            self.assertEqual(again.code, 0, again.log)
            for name in FILES:
                with self.subTest(file=name):
                    a = (self.r.out / f"{name}.json").read_bytes()
                    self.assertEqual(a, (again.out / f"{name}.json").read_bytes(), f"{name}.json differs between runs")
                    committed = OUT / f"{name}.json"
                    self.assertTrue(committed.exists(), f"{committed} is not committed")
                    self.assertEqual(a, committed.read_bytes(), f"committed {name}.json is stale")
            self.assertEqual(sorted(p.name for p in again.out.iterdir()), sorted(f"{n}.json" for n in FILES),
                             "exactly the five files")
        finally:
            again.cleanup()

    def test_the_diagram_carries_no_sorts(self):
        """I13-R2 (regression): sorts live in gen/M2/sorts; every carrier of the committed gen/M2/diagram keeps
        sort_ref null (the diagram does not depend on the sorts pass)."""
        files = sorted((ROOT / "gen" / "M2" / "diagram").glob("*.json"))
        self.assertTrue(files, "gen/M2/diagram holds no diagram")
        for p in files:
            for c in load_json(p)["carriers"]:
                with self.subTest(diagram=p.stem, carrier=c["id"]):
                    self.assertIsNone(c.get("sort_ref"))


def tearDownModule():
    if _Shared.sr is not None:
        _Shared.sr.cleanup()
        _Shared.sr = None


if __name__ == "__main__":
    unittest.main()
