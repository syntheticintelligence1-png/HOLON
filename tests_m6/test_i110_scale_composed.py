"""I110 (M6, generality): the scale wall and the composed driver. Contract tests (spec/M6/predictions/I110.json;
prompts/I110_scale_composed_driver.md).

The blockers I107 measured, each fixed by the pass's or the pipeline's semantics, never by a corpus entry:

  (a) The per-document sort budget (holon.sorts.budget). A typed-sorts sidecar may name "sort_budget", a positive
      integer: the most work units the sort pass may spend on one document. A work unit is one step of the pass's own
      loops (a term node the walk visits, an affine-table row a propagation sweep reads, a search node, a constraint a
      system reads), so the count is a function of the document and the code alone: deterministic, never wall-clock.
        B1 a sidecar without the key meters nothing: no budget.json, every output exactly as before;
        B2 under a budget no document exceeds, every output equals the unbudgeted pass's except the sidecar's own entry
           in the inputs listings (the sidecar is an input) and the added budget.json, which lists every document
           with its work and status "ok";
        B3 a document over budget is a recorded miss: budget.json lists it ("over_budget", the phase, the work at the
           stop), every variable of its model is unrefined (or it has none, when the walk itself ran out), and no
           conflict, site or union of it is written; every other document's assignment is unchanged;
        B4 the same inputs give byte-identical outputs on every run.
      spec/M6/lib/i110_run.json names the tier (typed.sort_budget), fixed in the prereg (Q69: never raised after a run
      sees its result).
  (b) The composed route A, `holon eval holon --compose` (the protocol's compose key; no fourth route): I103's
      extraction; I105's Go machines of every extracted Go package with compose.nil_maps (I109's default "unknown");
      I104's roles installed under spec/<M>/lib/ only where no hand sidecar exists (holon.roles.cli.install, mode
      hand); route C's codecs or Go-op documents, diagram and evidence; then route A's sorts, types, model, disch,
      derive (Q62: no link sidecar, an empty codec layer), run, replay and filter. Every derived record carries
      roles_source (row roles_sources per role sidecar: "hand" or the inference mode). Under Q56 the per-law rows are
      withheld; the aggregates keep roles_source.
  (c) `holon eval go-machines` records machines.nil_maps in its output (I107's Question 3).

The corpus smoke measures are results/M6/I110/holon/corpus.json (holon eval holon --protocol spec/M6/lib/i110_run.json
--compose) and results/M6/I110/go_machines.json (holon eval go-machines --protocol spec/M6/lib/i110_run.json). The
sort profile is results/M6/I110/sort_profile.json. A run on I106's targets, labelled contaminated: post-I107, commits
aggregates only (results/M6/I110/sealed.json; Q56, Q72).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PROTO = "spec/M6/lib/i110_run.json"
OUT = ROOT / "results" / "M6" / "I110"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
GO_CORPUS = OUT / "go_machines.json"
PROFILE = OUT / "sort_profile.json"
SEALED = OUT / "sealed.json"
BASE = "b65a863c"   # the lead at this key's start (I108's landing, #178): Morph's record as landed
MORPH_DIRS = ("results/M0", "results/M1", "results/M2", "results/M3", "laws/M0", "laws/M1", "laws/M2", "laws/M3")
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}
# planted inputs: committed corpus documents of I109's run (each small, their sort outputs committed beside them)
C02 = "results/M6/I109/holon/c02"
C05 = "results/M6/I109/holon/c05"
C17 = "results/M6/I109/holon/c17"


def key() -> dict:
    return json.loads((ROOT / "spec" / "M6" / "predictions" / "I110.json").read_text(encoding="utf-8"))


def pred(pid: str) -> dict:
    return {p["id"]: p for p in key()["predictions"]}[pid]


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def sorts(root: Path, sidecar: str, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", "sorts", "--milestone", "T510", "--root", str(root),
                           "--sidecar", sidecar, "--out", str(out)], cwd=ROOT, env=ENV, capture_output=True, text=True,
                          timeout=1800)


# the files the sort pass writes (holon.sorts.assign.DOCUMENTS, the coverage debt, I110's budget); gen/sorts also holds
# later stages' outputs (types, obstructions), which this key does not compare
PASS_FILES = ("constraints.json", "assignment.json", "conflicts.json", "unions.json", "unresolved.json",
              "coverage_debt.json", "budget.json")


def tree(d: Path) -> dict:
    return {p.name: p.read_bytes() for p in sorted(d.glob("*.json")) if p.name in PASS_FILES}


class _Budget(unittest.TestCase):
    """A scratch root holding three committed corpus entries' documents and their sort seeds."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i110-"))
        r = cls.tmp / "root"
        for e in (C02, C05, C17):
            shutil.copytree(ROOT / e / "facts", r / e / "facts")
        (r / "spec" / "M3" / "lib").mkdir(parents=True)
        shutil.copy(ROOT / "spec" / "M3" / "lib" / "sort_seeds.json", r / "spec" / "M3" / "lib" / "sort_seeds.json")
        base = json.loads((ROOT / C02 / "sidecars" / "sort_types.json").read_text(encoding="utf-8"))
        base["documents"] = sorted(f"{e}/facts/{p.name}" for e in (C02, C05, C17)
                                   for p in (ROOT / e / "facts").glob("*.extracted.json"))
        cls.root, cls.base = r, base
        cls.plain = cls.run_with(None, "plain")
        cls.big = cls.run_with(10 ** 12, "big")
        cls.work = {d["model"]: d["work"] for d in json.loads(cls.big["budget.json"])["documents"]}

    @classmethod
    def run_with(cls, budget, name: str) -> dict:
        sc = dict(cls.base)
        if budget is not None:
            sc["sort_budget"] = budget
        (cls.root / f"{name}.json").write_text(json.dumps(sc, indent=2, sort_keys=True) + "\n")
        out = cls.tmp / "out" / name
        p = sorts(cls.root, f"{name}.json", out)
        assert p.returncode == 0, p.stderr
        return tree(out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def strip_sidecar(text: bytes) -> dict:
        d = json.loads(text)
        d["inputs"] = [x for x in d.get("inputs") or [] if not x["path"].endswith(("plain.json", "big.json",
                                                                                    "small.json", "again.json"))]
        return d


class TestSortBudget(_Budget):
    def test_p2_b1_no_key_no_meter(self):
        self.assertNotIn("budget.json", self.plain)
        # and the pass over each entry alone still equals its committed outputs (holon.sorts.budget changes nothing)
        for e in (C02, C05, C17):
            out = self.tmp / "alone" / e.rsplit("/", 1)[-1]
            p = sorts(ROOT, f"{e}/sidecars/sort_types.json", out)
            self.assertEqual(p.returncode, 0, p.stderr)
            got, want = tree(out), tree(ROOT / e / "gen" / "sorts")
            self.assertEqual({k: v for k, v in want.items()}, {k: got[k] for k in want}, e)
            self.assertNotIn("budget.json", got)

    def test_p2_b2_generous_budget_changes_nothing_else(self):
        self.assertEqual(sorted(self.big), sorted([*self.plain, "budget.json"]))
        for n in self.plain:
            self.assertEqual(self.strip_sidecar(self.plain[n]), self.strip_sidecar(self.big[n]), n)
        b = json.loads(self.big["budget.json"])
        self.assertEqual(b["over_budget"], [])
        self.assertEqual({d["status"] for d in b["documents"]}, {"ok"})
        self.assertEqual(len(b["documents"]), len(self.base["documents"]))

    def test_p2_b3_over_budget_is_a_recorded_opaque_miss(self):
        heavy = max(self.work, key=lambda m: (self.work[m], m))
        limit = max(w for m, w in self.work.items() if m != heavy)
        self.assertLess(limit, self.work[heavy])
        small = self.run_with(limit, "small")
        b = json.loads(small["budget.json"])
        self.assertEqual(b["over_budget"], [heavy])
        (row,) = [d for d in b["documents"] if d["model"] == heavy]
        self.assertEqual(row["status"], "over_budget")
        self.assertIn(row["phase"], ("walk", "solve"))
        self.assertGreater(row["work"], limit)
        asg = json.loads(small["assignment.json"])
        full = json.loads(self.plain["assignment.json"])
        self.assertIn(heavy, asg["models"])
        self.assertEqual(set(asg["models"][heavy]["assignment"].values()) - {"Nat (unrefined)"}, set())
        self.assertFalse([s for s in asg["sites"] if s.get("model") == heavy])
        for k in ("conflicts", "unions"):
            self.assertFalse([x for x in json.loads(small[f"{k}.json"])[k] if x.get("model") == heavy], k)
        for m in full["models"]:
            if m != heavy:
                self.assertEqual(asg["models"][m]["assignment"], full["models"][m]["assignment"], m)

    def test_p2_b4_deterministic(self):
        again = self.run_with(10 ** 12, "again")
        for n in self.big:
            self.assertEqual(self.strip_sidecar(self.big[n]), self.strip_sidecar(again[n]), n)

    def test_p2_bad_budget_refused(self):
        for bad in (0, -1, "10", True):
            sc = dict(self.base, sort_budget=bad)
            (self.root / "bad.json").write_text(json.dumps(sc))
            p = sorts(self.root, "bad.json", self.tmp / "out" / "bad")
            self.assertEqual(p.returncode, 1, bad)
            self.assertIn("sort_budget", p.stderr)

    def test_p2_protocol_names_the_tier(self):
        proto = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(proto["typed"]["sort_budget"], pred("I110-P2")["expected"]["tier"])


class TestByteIdentity(unittest.TestCase):
    def test_p3_corpus_and_morph_sort_outputs_unchanged(self):
        """Every committed sort output of I108's and I109's corpus documents, re-made at this head, is byte-identical;
        and Morph's gate (holon gate M2/M3 compares gen/<M>/sorts) is run by CI."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-i110-p3-"))
        try:
            n = 0
            for k in ("I108", "I109"):
                for e in sorted((ROOT / "results" / "M6" / k / "holon").glob("c*")):
                    sc, g = e / "sidecars" / "sort_types.json", e / "gen" / "sorts"
                    if not (sc.is_file() and g.is_dir()):
                        continue
                    out = tmp / k / e.name
                    p = sorts(ROOT, sc.relative_to(ROOT).as_posix(), out)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    got = tree(out)
                    for name, want in tree(g).items():
                        self.assertEqual(got.get(name), want, f"{k} {e.name} {name}")
                    n += 1
            self.assertGreaterEqual(n, 5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestNilMapsRecorded(unittest.TestCase):
    def test_p1_go_machines_output_names_nil_maps(self):
        from holon.eval import go_machines_run as GM
        tmp = Path(tempfile.mkdtemp(prefix="holon-i110-c-"))
        try:
            row = {"id": "c03", "machines": 0, "actions": 0, "pipeline": "refused", "refused_at": "extract", "laws": 0}
            with mock.patch.object(GM, "run_entry", lambda e, p, r: dict(row)):
                for proto, want in ((PROTO, "unknown"), (None, "unknown")):
                    out = tmp / "o.json"
                    GM.cli(["--entries", "c03", "--out", str(out), *(["--protocol", proto] if proto else [])])
                    self.assertEqual(json.loads(out.read_text())["machines"], {"nil_maps": want})
                p = tmp / "zero.json"
                d = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
                d["go_machines"]["nil_maps"] = "zero"
                p.write_text(json.dumps(d))
                with mock.patch.object(GM, "ROOT", ROOT):
                    GM.cli(["--root", str(ROOT), "--entries", "c03", "--out", str(tmp / "z.json"), "--protocol",
                            os.path.relpath(p, ROOT)])
                self.assertEqual(json.loads((tmp / "z.json").read_text())["machines"], {"nil_maps": "zero"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p1_committed_run_names_it(self):
        self.assertTrue(GO_CORPUS.is_file(), "results/M6/I110/go_machines.json is missing")
        self.assertEqual(json.loads(GO_CORPUS.read_text(encoding="utf-8"))["machines"], {"nil_maps": "unknown"})


class TestComposedUnits(unittest.TestCase):
    def test_p6_roles_source_rules(self):
        from holon.eval import holon_run as H
        tmp = Path(tempfile.mkdtemp(prefix="holon-i110-rs-"))
        try:
            (tmp / "go_laws.json").write_text("{}")
            (tmp / "link.json").write_text("{}")
            self.assertEqual(H.roles_sources(tmp, ["link.json"], {"mode": "static"}),
                             {"go_laws.json": "static", "link.json": "hand"})
            self.assertEqual(H.law_roles_source({"go_laws.json": "static", "link.json": "hand"}), "hand+static")
            self.assertEqual(H.law_roles_source({}), "none")
            self.assertEqual(H.law_roles_source({"link.json": "hand"}), "hand")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p6_compose_needs_the_protocol_key(self):
        from holon.eval import common
        from holon.eval import holon_run as H
        with self.assertRaises(common.Refused):
            H.cli_holon(["--protocol", "spec/M6/lib/i109_run.json", "--compose", "--entries", "c01"])

    def test_p6_protocol_compose_key(self):
        proto = json.loads((ROOT / PROTO).read_text(encoding="utf-8"))
        self.assertEqual(proto["compose"]["nil_maps"], "unknown")
        self.assertNotIn("stop_after", proto)


class TestCorpusSmoke(unittest.TestCase):
    """P4-P7: smoke measures on I51's 20 entries (contaminated by I51, I103-I109 and I107; a later sealed draw scores)."""

    def rows(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I110/holon/corpus.json is missing")
        return {r["id"]: r for r in json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))["rows"]}

    def reach(self) -> dict:
        out = {}
        for i, r in self.rows().items():
            st = r.get("stages") or {}
            for s in ("extract", "machines", "roles", "sorts", "types", "model", "derive", "run"):
                if (st.get(s) or {}).get("status") == "ok":
                    out.setdefault(s, set()).add(i)
        return out

    def test_p4_profile_recorded(self):
        self.assertTrue(PROFILE.is_file(), "results/M6/I110/sort_profile.json is missing")
        prof = json.loads(PROFILE.read_text(encoding="utf-8"))
        e = pred("I110-P4")["expected"]
        docs = prof["documents"]
        self.assertGreaterEqual(len(docs), e["documents_at_least"])
        for d in docs:
            self.assertTrue({"facts", "work", "phases"} <= set(d), d.get("facts"))
        under = [d for d in docs if d["work"] <= prof["tier"]]
        self.assertGreaterEqual(len(under) / len(docs), e["share_under_tier_at_least"])

    def test_p5_stage_reach(self):
        e = pred("I110-P5")["expected"]
        r = self.reach()
        for s, n in e["entries_at_least"].items():
            self.assertGreaterEqual(len(r.get(s, ())), n, s)

    def test_p5_every_miss_has_a_reason(self):
        for i, r in sorted(self.rows().items()):
            self.assertTrue(r.get("compose"), i)
            for k, v in (r.get("stages") or {}).items():
                if v.get("status") not in ("ok", "not_applicable", "not_run"):
                    self.assertTrue((v.get("detail") or "").strip(), f"{i}: stage {k} has no reason")

    def test_p6_aggregates_carry_roles_source_and_withhold(self):
        for i, r in sorted(self.rows().items()):
            self.assertEqual(r.get("laws"), [], i)   # Q56: per-law rows withheld
            for k in (r.get("laws_aggregate") or {}):
                self.assertIn(" roles_source=", k, i)
                self.assertNotIn("roles_source=hand", k, i)   # the corpus has no hand role sidecar

    def test_p7_laws_aggregate(self):
        e = pred("I110-P7")["expected"]
        rows = self.rows()
        derived = sum(f["derived"] for r in rows.values() for f in (r.get("laws_aggregate") or {}).values())
        decided = sum(f["decided"] for r in rows.values() for f in (r.get("laws_aggregate") or {}).values())
        self.assertLessEqual(derived, e["derived_at_most"])
        self.assertLessEqual(decided, e["decided_at_most"])
        timeouts = sorted(i for i, r in rows.items() if ((r.get("stages") or {}).get("sorts") or {}).get("status")
                          == "timeout")
        self.assertEqual(timeouts, [])


class TestSealedContaminated(unittest.TestCase):
    """P8: I106's targets, contaminated: post-I107 (aggregates only, Q56; Q72)."""

    def test_p8_sorts_finish_under_the_tier(self):
        if not SEALED.is_file():
            self.skipTest("the contaminated measurement was not run (recorded under Not done)")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        e = pred("I110-P8")["expected"]
        for t in d["targets"]:
            self.assertNotEqual(t["stages"].get("sorts"), "timeout", t["id"])
            self.assertGreaterEqual(t["documents_under_tier"] / max(1, t["documents_sorted"]),
                                    e["share_under_tier_at_least"], t["id"])
            self.assertNotIn("laws", t)   # aggregates only


class TestRegressions(unittest.TestCase):
    def test_r1_morph_record_moves_only_by_restamp(self):
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

    def test_r2_morph_sidecars_name_no_sort_budget(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[0-3]/lib/*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(d, dict) and "sort_budget" in d:
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_r3_earlier_protocols_name_no_budget_or_compose(self):
        found = []
        for p in sorted((ROOT / "spec").glob("M[4-6]/lib/i*_run.json")):
            if p.name == "i110_run.json":
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            if "compose" in d or "sort_budget" in (d.get("typed") or {}):
                found.append(p.name)
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
