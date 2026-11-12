"""I111 (M6, generality): types totality. Contract tests (spec/M6/predictions/I111.json; prompts/I111_types_totality.md).

The wall I110 measured: `holon types` refuses a whole milestone over one ill-sorted term. HUMAN_ANSWERS Q77: a
per-document fallback, justified by the typed model's semantics, never by a corpus entry.

  (a) The types fallback (holon.sorts.opaque). Opt-in only: a typed-sorts sidecar names "types_fallback": "opaque"
      (the only value; any other is refused). Without the key nothing changes (N2: exit 2, nothing written). Under the
      key, holon types types each document on its own, in sorted order, and a document whose typed model generation
      raises the ill-sorted error is OPAQUE:
        O1 a recorded miss: one entry of gen/<M>/sorts/opaque.json {document, sha256, model, term, reason} (term: the
           error's first clause, the action and the operation; reason: its whole text, with the source span);
        O2 its state: no typed model, so no state variable of it exists in any model and nothing constrains it;
        O3 its actions: none is modelled and no law of any rule is derived over it, so every claim over it is UNKNOWN;
        O4 other documents may assume nothing new about it: every typed model is one document's, another contract is
           reached only through an external call whose answer is a free value (A-env), so a typed document's model,
           laws and verdicts do not depend on an opaque document being in the milestone (apart from the
           milestone-wide assignment hash in the model's header comment, and so its model_sha256);
        O5 every stage after types (model, disch, derive, run) reads the typed documents only; sorts and types read
           every document, and the assignment is the sort pass's over all of them;
        O6 a taint violation still refuses the milestone; an unreadable input still exits 1;
        O7 if every document is opaque, types.json has no model and holon types exits 0.
  (b) A law over a Go document (extraction.frontend "go") has a null coverage field: such a document carries its debt
      in itself (its "debt" list) and holon.coverage lists Solidity transitions sidecars only, as with a layout
      document (I62). Before, the record writer raised for want of a gen/<M>/coverage.json entry, so run decided no
      law over a Go machine.
  (c) The composed driver (holon eval holon --compose) copies the protocol's typed.types_fallback into every typed
      sidecar it writes, and each row records types_opaque {documents, typed, opaque, misses: [{document, term}]}
      (a stage reason before any decision, Q72).

  (2) The torsor-role search (holon.sorts.solve._search, HUMAN_ANSWERS Q78), one exact evaluation strategy, D1: after
      each propagation the constraints holding a variable with more than one role left are grouped by the connected
      components of those variables (a constraint with every variable decided is satisfied and drops out); with two or
      more parts the network is satisfiable iff every part is, each searched alone in order of its least open variable;
      with one part the old branching is unchanged. Same boolean on every input, so every sort output is the same
      (Q74 (1)); holon.sorts.solve.DECOMPOSE False is the old strategy, for the identity test only. No new tier: the
      sort budget's stays I110's, and the new strategy's units never exceed the old's (Q75, Q76).

The planted fixture tests_m6/fixtures/i111 is written for these tests (one Go package, three machines): Ledger is well
typed; Wiper writes a whole map in Reset (I109's A4 refusal), so it is opaque under the fallback; WiperKept is Wiper
without Reset, the constrained control. Their expectations are known from the source by construction.

The corpus smoke measures are results/M6/I111/holon/corpus.json (holon eval holon --protocol spec/M6/lib/i111_run.json
--compose). A run on I106's targets, labelled contaminated: post-I107, commits aggregates only
(results/M6/I111/sealed.json; Q56, Q72).
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i111"
SRC = FIX / "src"
PROTO = "spec/M6/lib/i111_run.json"
OUT = ROOT / "results" / "M6" / "I111"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
BASE = "a813b2b9"   # the lead at this key's start (#184): Morph's record as landed
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
WIPER_TERM = "Reset: a write of a whole mapping(uint64 => uint64) (Seen)"


def run_holon(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, env=ENV, capture_output=True, text=True,
                          timeout=timeout)


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I111.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def protocol(fallback: bool = True) -> dict:
    from holon.eval import common
    proto = json.loads(json.dumps(common.load_json(ROOT / PROTO)))
    if not fallback:
        proto["typed"].pop("types_fallback", None)
    return proto


def composed(docs: list[Path], tmp: Path, fallback: bool = True) -> tuple[dict, Path, str, str]:
    """The composed route's typed part over docs in one milestone (holon_run: roles installed where none exists, then
    sorts, types, model, disch, route C's stages, derive and run), under the protocol with or without the fallback.
    Every milestone has the same scratch paths, so outputs over the same document compare byte for byte."""
    from holon.eval import holon_run as H
    proto = protocol(fallback)
    S = H.scratch_root(ROOT, tmp, "holon/i111", SRC)
    rel = "results/eval/holon/i111"
    (S / rel / "sidecars").mkdir(parents=True)
    (S / rel / "facts").mkdir(parents=True)
    for d in docs:
        shutil.copy(d, S / rel / "facts" / d.name)
    M = proto["milestone"]
    lib = S / "spec" / M / "lib"
    stages: dict = {}
    R = H.Runner(H.Ctx(tmp, SRC), S, proto, {})
    rels = [f"{rel}/facts/{d.name}" for d in docs]
    stages["roles"] = R.holon("roles", ["roles", "--milestone", M, "--root", str(S), "--documents", ",".join(rels),
                                        "--out-dir", str(S / rel / "sidecars" / "roles"), "--mode", "static",
                                        "--install", "--roles", "hand"])
    H._rules(R, S, rel, M, proto, [{"file": d.name} for d in docs], stages, lambda: H._route_c(R, S, M, lib, stages))
    return stages, S, rel, M


def verdicts(S: Path, M: str) -> dict:
    """{law id: (the record's status, the law's facts document)} of every record of the milestone."""
    facts = law_facts(S, M)
    out = {}
    for p in sorted((S / "results" / M).glob("L*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        out[p.stem] = (r.get("status"), facts.get(p.stem))
    return out


def law_facts(S: Path, M: str) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")).get("facts") for p in sorted((S / "laws" / M).glob("L*.json"))}


def unseconds(x):
    if isinstance(x, dict):
        return {k: unseconds(v) for k, v in x.items() if k not in ("seconds", "model_sha256")}
    if isinstance(x, list):
        return [unseconds(v) for v in x]
    return x


class _Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i111-"))
        p = run_holon(["extract", "go_machines", "--root", str(ROOT), "--config", str(FIX / "go_config.json"),
                       "--src", str(SRC), "--out-dir", str(cls.tmp / "docs")])
        if p.returncode != 0:
            raise AssertionError(p.stderr[-3000:])
        cls.docs = {json.loads(x.read_text(encoding="utf-8"))["contract"].rsplit(".", 1)[-1]: x
                    for x in sorted((cls.tmp / "docs").glob("*.extracted.json"))}
        cls.runs: dict = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_of(self, names: tuple, fallback: bool = True):
        k = (names, fallback)
        if k not in self.runs:
            t = self.tmp / f"run{len(self.runs)}"
            t.mkdir()
            self.runs[k] = composed([self.docs[n] for n in names], t, fallback)
        return self.runs[k]

    def model(self, name: str) -> str:
        return f"bank.{name}.extracted"


class TestFallback(_Fixture):
    """P1: (a) O1, O5-O7 on the planted milestone."""

    def test_p1_fixture_shape(self):
        self.assertEqual(sorted(self.docs), ["Ledger", "Wiper", "WiperKept"])

    def test_p1_opaque_recorded(self):
        stages, S, _rel, M = self.run_of(("Ledger", "Wiper", "WiperKept"))
        self.assertEqual(stages["types"]["status"], "ok", stages["types"]["detail"][-2000:])
        op = json.loads((S / "gen" / M / "sorts" / "opaque.json").read_text(encoding="utf-8"))
        self.assertEqual([x["model"] for x in op["documents"]], [self.model("Wiper")])
        (w,) = op["documents"]
        self.assertEqual(w["term"], WIPER_TERM)
        self.assertIn("bank/bank.go:78", w["reason"])
        self.assertTrue(w["document"].endswith("bank.Wiper.extracted.json"))
        self.assertEqual(len(w["sha256"]), 64)
        types = json.loads((S / "gen" / M / "sorts" / "types.json").read_text(encoding="utf-8"))
        taint = json.loads((S / "gen" / M / "sorts" / "taint.json").read_text(encoding="utf-8"))
        want = sorted([self.model("Ledger"), self.model("WiperKept")])
        self.assertEqual(sorted(types["models"]), want)
        self.assertEqual(sorted(taint["models"]), want)
        models = sorted(p.name for p in (S / "gen" / M / "sorts" / "models").glob("*.bend"))
        self.assertEqual([m for m in models if m.startswith(("bank.Wiper.", "bank_Wiper_"))], [], models)

    def test_p1_without_the_key_refused_as_before(self):
        stages, S, _rel, M = self.run_of(("Ledger", "Wiper", "WiperKept"), fallback=False)
        self.assertEqual(stages["types"]["status"], "failed")
        self.assertEqual(stages["types"]["exit"], 2)
        self.assertIn("ill-sorted", stages["types"]["detail"])
        self.assertFalse((S / "gen" / M / "sorts" / "types.json").exists())
        self.assertFalse((S / "gen" / M / "sorts" / "opaque.json").exists())

    def test_p1_unknown_value_refused(self):
        from holon.sorts import opaque
        with self.assertRaises(ValueError):
            opaque.mode({"types_fallback": "skip"})
        self.assertIsNone(opaque.mode({}))
        self.assertEqual(opaque.mode({"types_fallback": "opaque"}), "opaque")

    def test_p1_deterministic(self):
        _st, S, _rel, M = self.run_of(("Ledger", "Wiper", "WiperKept"))
        sd = S / "gen" / M / "sorts"
        before = {n: (sd / n).read_bytes() for n in ("types.json", "taint.json", "opaque.json")}
        p = run_holon(["types", "--milestone", M, "--root", str(S), "--sidecar", "results/eval/holon/i111/sidecars/"
                       "sort_types.json", "--out", str(sd)])
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertEqual({n: (sd / n).read_bytes() for n in before}, before)

    def test_p1_all_opaque_exits_0(self):
        stages, S, _rel, M = self.run_of(("Wiper",))
        self.assertEqual(stages["types"]["status"], "ok", stages["types"]["detail"][-2000:])
        types = json.loads((S / "gen" / M / "sorts" / "types.json").read_text(encoding="utf-8"))
        self.assertEqual(types["models"], {})


class TestPlanted(_Fixture):
    """P2-P4: an ill-sorted document never makes a law PROVED (or REFUTED) where it would otherwise not be."""

    def no_decision_over_wiper(self, S: Path, M: str):
        wiper = "bank.Wiper.extracted.json"
        self.assertEqual([k for k, f in law_facts(S, M).items() if f and f.endswith(wiper)], [])
        self.assertEqual([k for k, (v, f) in verdicts(S, M).items() if f and f.endswith(wiper)], [])

    def test_p2_opaque_alone(self):
        stages, S, _rel, M = self.run_of(("Wiper",))
        self.assertEqual(stages["types"]["status"], "ok")
        self.no_decision_over_wiper(S, M)
        self.assertEqual(law_facts(S, M), {})
        # the constrained control decides what the opaque document leaves UNKNOWN
        stages, S, _rel, M = self.run_of(("WiperKept",))
        self.assertEqual(stages["run"]["status"], "ok", stages["run"]["detail"][-2000:])
        v = [x for x, _f in verdicts(S, M).values()]
        self.assertEqual(len(law_facts(S, M)), 4)
        self.assertIn("PROVED", v)
        self.assertIn("REFUTED", v)

    def test_p3_cross_document(self):
        _a, A, _rel, M = self.run_of(("Ledger",))
        stages, B, _rel, _M = self.run_of(("Ledger", "Wiper"))
        self.assertEqual(stages["run"]["status"], "ok", stages["run"]["detail"][-2000:])
        self.no_decision_over_wiper(B, M)
        la = sorted(p.name for p in (A / "laws" / M).glob("L*.json"))
        self.assertTrue(la)
        self.assertEqual(la, sorted(p.name for p in (B / "laws" / M).glob("L*.json")))
        for n in la:
            self.assertEqual((A / "laws" / M / n).read_bytes(), (B / "laws" / M / n).read_bytes(), n)
            ra = json.loads((A / "results" / M / n).read_text(encoding="utf-8"))
            rb = json.loads((B / "results" / M / n).read_text(encoding="utf-8"))
            self.assertEqual(unseconds(ra), unseconds(rb), n)
        mn = "bank.Ledger.extracted.bend"
        strip = lambda t: [x for x in t.splitlines() if not x.startswith("# assignment sorts_sha256:")]   # noqa: E731
        self.assertEqual(strip((A / "gen" / M / "sorts" / "models" / mn).read_text(encoding="utf-8")),
                         strip((B / "gen" / M / "sorts" / "models" / mn).read_text(encoding="utf-8")))
        for d in ("laws", "results"):
            for p in sorted((B / d / M).rglob("*")):
                if not p.is_file():
                    continue
                if p.name in ("DERIVATION.json", "REGISTRY.json"):   # the index: its laws entries, not its provenance
                    idx = json.loads(p.read_text(encoding="utf-8"))
                    per_law = [idx.get("laws"), idx.get("statements")]   # DERIVATION's laws, REGISTRY's statements
                    self.assertNotIn("bank.Wiper.extracted", json.dumps(per_law), p.name)
                    continue
                self.assertNotIn("bank.Wiper.extracted", p.read_text(encoding="utf-8"), p.name)
        for p in sorted((B / "gen" / M / "sorts" / "models").glob("*")):
            self.assertNotIn("bank.Wiper.extracted", p.name)

    def test_p4_constrained_law_unknown(self):
        _k, K, _rel, M = self.run_of(("WiperKept",))
        _l, L, _rel, _M = self.run_of(("Ledger",))
        stages, B, _rel, _M = self.run_of(("Ledger", "Wiper", "WiperKept"))
        self.assertEqual(stages["run"]["status"], "ok", stages["run"]["detail"][-2000:])
        kept = {k: v for k, (v, _f) in verdicts(K, M).items()}
        self.assertIn("PROVED", kept.values())
        both = {k: v for k, (v, _f) in verdicts(B, M).items()}
        alone = {**kept, **{k: v for k, (v, _f) in verdicts(L, M).items()}}
        self.assertEqual(both, alone)   # Ledger's and WiperKept's verdicts as alone; nothing over Wiper
        self.no_decision_over_wiper(B, M)


class TestGoCoverage(_Fixture):
    """P5: (b) a law over a Go document has a null coverage field, and run decides it."""

    def test_p5_coverage_null_for_a_go_document(self):
        from holon import records
        d = json.loads(self.docs["Ledger"].read_text(encoding="utf-8"))
        self.assertEqual((d["extraction"]["frontend"], d["extraction"]["kind"]), ("go", "transitions"))
        tmp = Path(tempfile.mkdtemp(prefix="holon-i111-cov-"))
        try:
            (tmp / "f").mkdir()
            shutil.copy(self.docs["Ledger"], tmp / "f" / "x.extracted.json")
            self.assertIsNone(records.coverage_field({"milestone": "M9", "facts": "f/x.extracted.json"}, tmp))
            d["extraction"]["frontend"] = "solidity"
            (tmp / "f" / "y.extracted.json").write_text(json.dumps(d))
            with self.assertRaises(ValueError):
                records.coverage_field({"milestone": "M9", "facts": "f/y.extracted.json"}, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p5_run_decides_ledger(self):
        stages, S, _rel, M = self.run_of(("Ledger",))
        self.assertEqual(stages["run"]["status"], "ok", stages["run"]["detail"][-2000:])
        laws = law_facts(S, M)
        self.assertEqual(len(laws), 4)
        self.assertEqual(sorted(verdicts(S, M)), sorted(laws))


# ----------------------------------------------------------------------------------------------- (2) the search
BLOWUP = FIX / "search" / "blowup.json"
I110_DOCS = ("results/M6/I109/holon/c02", "results/M6/I109/holon/c05", "results/M6/I109/holon/c17")


@contextlib.contextmanager
def strategy(decompose: bool, nodes: list | None = None):
    """The search under the new (True) or the old (False) strategy, in process; nodes collects one entry per call of
    holon.sorts.solve._search (a search node)."""
    from holon.sorts import solve as SV
    flag, orig = SV.DECOMPOSE, SV._search

    def counted(d, c):
        nodes.append(1)
        return orig(d, c)
    SV.DECOMPOSE = decompose
    if nodes is not None:
        SV._search = counted
    try:
        yield
    finally:
        SV.DECOMPOSE, SV._search = flag, orig


def answers(cs: list) -> dict:
    """Everything the solver answers about a system: ok, and per variable its family and its difference sorts with
    every other variable of the model (sorted, as text)."""
    from holon.sorts.solve import System
    sy = System(cs)
    out = {"ok": sy.ok}
    if not sy.ok:
        return out
    vs = sorted({v for c in cs for v in c["vars"]})
    out["family"] = {v: sy.family("m", v) for v in vs}
    out["diff"] = {f"{a}-{b}": sorted(str(x) for x in (sy.difference_sorts("m", a, b) or ())) for a in vs for b in vs}
    return out


class TestSearch(unittest.TestCase):
    """P11: the planted blow-up, built from the search's semantics (tools/i111_search_fixture.py)."""

    def test_p11_fixture_regenerates(self):
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "i111_search_fixture.py"), "--check"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_p11_planted_blowup(self):
        from holon.sorts.solve import System
        e = pred("I111-P11")["expected"]
        doc = json.loads(BLOWUP.read_text(encoding="utf-8"))
        old_nodes, new_nodes = {}, {}
        for n in sorted(map(int, doc["systems"])):
            cs = doc["systems"][str(n)]
            for flag, rec in ((False, old_nodes), (True, new_nodes)):
                nodes: list = []
                with strategy(flag, nodes):
                    self.assertEqual(System(cs).family("m", "r"), "Dur", (n, flag))
                rec[n] = len(nodes)
            with strategy(False):
                a_old = answers(cs)
            with strategy(True):
                a_new = answers(cs)
            self.assertEqual(a_old, a_new, n)
            self.assertLessEqual(new_nodes[n], 10 * n + 20, n)
        ns = sorted(old_nodes)
        for a, b in zip(ns, ns[1:]):
            self.assertGreaterEqual(old_nodes[b], 2 * old_nodes[a], (a, b, old_nodes))
        self.assertGreaterEqual(old_nodes[12], e["old_nodes_at_least_n12"])
        print("\nP11 search nodes (old, new):", json.dumps({n: [old_nodes[n], new_nodes[n]] for n in ns}))


def pass_out(root: Path, rel: str, decompose: bool) -> tuple[dict, int]:
    """holon.sorts.assign.run_pass over one document under the protocol's typed settings with a budget no document
    reaches (so every unit is counted): the outputs as holon sorts writes them, the scratch sidecar's own input entry
    removed, and the document's work units."""
    from holon.sorts import assign as A
    typed = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))["typed"]
    sc = {"sort_types_version": typed["sort_types_version"], "seeds": typed["seeds"], "binding": None,
          "search": typed["search"], "doc": "I111 search check", "documents": [rel], "sort_budget": 10 ** 15}
    tmp = Path(tempfile.mkdtemp(prefix="holon-i111-search-", dir=root))
    try:
        sp = tmp / "st.json"
        sp.write_text(json.dumps(sc))
        with strategy(decompose):
            out = A.run_pass([root / rel], root, "T510", seeds_path=root / sc["seeds"], sidecar_path=sp)
        texts = {}
        for name, doc in out.items():
            doc = dict(doc, inputs=[x for x in doc.get("inputs") or [] if not x["path"].endswith("/st.json")])
            texts[name] = A.dumps(doc)
        work = json.loads(texts.pop("budget"))["documents"][0]["work"]
        return texts, work
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def tree(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


class TestSearchIdentity(unittest.TestCase):
    """P12, P13: Q74 (2) and Q75/Q76: old versus new strategy, byte for byte and unit for unit."""

    @classmethod
    def docs(cls) -> list[str]:
        from holon.sorts import coverage as CV
        out = list(CV.documents(ROOT))
        for d in I110_DOCS:
            out += sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / d / "facts").glob("*.extracted.json"))
        out.append("spec/M2/facts/morph_rollup.extracted.json")
        return sorted(set(out))

    def test_p12_documents_identical(self):
        docs = self.docs()
        self.assertGreaterEqual(len(docs), 50)
        for rel in docs:
            new, _wn = pass_out(ROOT, rel, True)
            old, _wo = pass_out(ROOT, rel, False)
            self.assertEqual(old, new, rel)

    def test_p12_morph_passes_identical(self):
        from holon import sorts as S
        tmp = Path(tempfile.mkdtemp(prefix="holon-i111-morph-"))
        try:
            for m in ("M2", "M3"):
                with strategy(True):
                    self.assertEqual(S.run(m, str(ROOT), str(tmp / "new" / m), None), 0)
                with strategy(False):
                    self.assertEqual(S.run(m, str(ROOT), str(tmp / "old" / m), None), 0)
                new = tree(tmp / "new" / m)
                self.assertEqual(new, tree(tmp / "old" / m), m)
                committed = tree(ROOT / "gen" / m / "sorts")
                self.assertEqual(new, {k: v for k, v in committed.items() if k in new}, m)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p13_units_never_grow(self):
        rows = {}
        for rel in self.docs():
            _n, wn = pass_out(ROOT, rel, True)
            _o, wo = pass_out(ROOT, rel, False)
            self.assertLessEqual(wn, wo, rel)
            if wn != wo:
                rows[rel] = [wo, wn]
        print("\nP13 units that differ (old, new):", json.dumps(rows, sort_keys=True))


class TestCorpusSmoke(unittest.TestCase):
    """P7-P9: smoke measures on I51's 20 entries (contaminated by I51, I103-I110 and I107)."""

    def rows(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I111/holon/corpus.json is missing")
        return {r["id"]: r for r in json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))["rows"]}

    def test_p7_stage_reach(self):
        e = pred("I111-P7")["expected"]
        reach: dict = {}
        for i, r in self.rows().items():
            self.assertTrue(r.get("compose"), i)
            for s, v in (r.get("stages") or {}).items():
                if v.get("status") == "ok":
                    reach.setdefault(s, set()).add(i)
                elif v.get("status") not in ("not_applicable", "not_run"):
                    self.assertTrue((v.get("detail") or "").strip(), f"{i}: stage {s} has no reason")
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(reach.get(s, ())), n, s)

    def test_p8_typed_versus_opaque(self):
        e = pred("I111-P8")["expected"]
        typed = opaque = 0
        for i, r in sorted(self.rows().items()):
            if ((r.get("stages") or {}).get("types") or {}).get("status") != "ok":
                continue
            t = r["types_opaque"]
            self.assertEqual(t["typed"] + t["opaque"], t["documents"], i)
            self.assertEqual(len(t["misses"]), t["opaque"], i)
            for m in t["misses"]:
                self.assertTrue(m["document"] and m["term"], i)
            typed += t["typed"]
            opaque += t["opaque"]
        self.assertGreaterEqual(opaque, e["opaque_at_least"])
        self.assertGreaterEqual(typed, e["typed_at_least"])

    def test_p9_laws_aggregate(self):
        e = pred("I111-P9")["expected"]
        rows = self.rows()
        aggs = [(k, f) for r in rows.values() for k, f in (r.get("laws_aggregate") or {}).items()]
        for i, r in rows.items():
            self.assertEqual(r.get("laws"), [], i)   # Q56: per-law rows withheld
        for k, _f in aggs:
            self.assertIn(" roles_source=", k)
        self.assertGreaterEqual(sum(f["derived"] for _k, f in aggs), e["derived_at_least"])
        self.assertGreaterEqual(sum(f["decided"] for _k, f in aggs), e["decided_at_least"])
        for s in ("sorts", "types"):
            self.assertEqual(sorted(i for i, r in rows.items() if ((r.get("stages") or {}).get(s) or {})
                                    .get("status") == "timeout"), [], s)


class TestSealedContaminated(unittest.TestCase):
    """P10: I106's targets, contaminated: post-I107 (aggregates only, Q56; Q72)."""

    def test_p10_types_ok_aggregates_only(self):
        if not SEALED.is_file():
            self.skipTest("the contaminated measurement was not run (recorded under Not done)")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        for t in d["targets"]:
            self.assertEqual(t["stages"].get("types"), "ok", t["id"])
            self.assertEqual(t["types_typed"] + t["types_opaque"], t["types_documents"], t["id"])
            self.assertNotIn("laws", t)   # aggregates only
            self.assertEqual(len(t["bundle_sha256"]), 64, t["id"])
            for k in t.get("laws_aggregate", {}).values():
                self.assertEqual(set(k), {"derived", "decided", "unknown"}, t["id"])


    def test_p14_search_on_the_spent_targets(self):
        if not SEALED.is_file():
            self.skipTest("the contaminated measurement was not run (recorded under Not done)")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        for t in d["targets"]:
            self.assertEqual(t["documents_over_tier"], 0, t["id"])
            for x in t.get("old_search_unlimited", []):
                self.assertIn(x["status"], ("identical", "not_finished"), t["id"])


class TestRegressions(unittest.TestCase):
    def test_p6_morph_record_moves_only_by_restamp(self):
        """Compared as G1 compares: generator_sha256 and every `seconds` stripped, G1_EXCLUDED skipped."""
        from holon.gate import G1_EXCLUDED

        def unstamp(x):
            if isinstance(x, dict):
                return {k: unstamp(v) for k, v in x.items() if k not in ("generator_sha256", "seconds")}
            if isinstance(x, list):
                return [unstamp(v) for v in x]
            return x
        moved = []
        for d in MORPH_DIRS:
            base = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", BASE, "--", d)
                    .decode().splitlines()}
            head = {ln.split("\t", 1)[1]: ln.split()[2] for ln in git("ls-tree", "-r", "HEAD", "--", d)
                    .decode().splitlines()}
            for p in sorted(set(base) | set(head)):
                if base.get(p) == head.get(p) or p.rsplit("/", 1)[-1] in G1_EXCLUDED:
                    continue
                if p not in base or p not in head or not p.endswith(".json"):
                    moved.append(p)
                    continue
                if unstamp(json.loads(git("cat-file", "blob", base[p]))) != \
                        unstamp(json.loads(git("cat-file", "blob", head[p]))):
                    moved.append(p)
        self.assertEqual(moved, [])

    def test_p6_morph_sidecars_name_no_types_fallback(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and "types_fallback" in d:
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_p6_earlier_protocols_name_no_types_fallback(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[4-6]/lib/i*_run.json")):
            # amended (spec/M6/amendments/I111.jsonl): the protocols of I111 and later keys are not earlier ones
            it = str(json.loads(p.read_text(encoding="utf-8")).get("iteration") or "")
            if p.name == "i111_run.json" or (it[1:].isdigit() and int(it[1:]) >= 111):
                continue
            if "types_fallback" in (json.loads(p.read_text(encoding="utf-8")).get("typed") or {}):
                found.append(p.name)
        self.assertEqual(found, [])

    def test_p6_protocol_is_i110s_plus_the_fallback(self):
        a = json.loads((ROOT / "spec/M6/lib/i110_run.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(b["typed"].pop("types_fallback"), "opaque")
        for d in (a, b):
            for k in ("doc", "iteration", "out", "typed_doc"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111"):
            self.assertIn(f"name: {job}", wf, job)
        self.assertIn("tests_m6.test_i110_scale_composed.TestRegressions", wf)


if __name__ == "__main__":
    unittest.main()
