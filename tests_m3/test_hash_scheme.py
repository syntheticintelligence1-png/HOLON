"""PV2A: content-addressed law identity (statement-hash scheme 2), the hash_migration lines, line ids, and the per-key
prereg sources with their generated aggregates. Infrastructure, no prereg key; the contract is BUILD_PLAN's pipeline v2
part A as the lead settled it:

  H1 One hash. holon.ir.statement_hash is the one implementation. Scheme 1 (a law without hash_scheme) is exactly the
     hash before PV2A: 0.1/0.2 over docs/M0_SPEC.md §3's keys, 0.3 over HASHED_KEYS_03 plus refs, a DISCH-profile law
     over its statement; every committed registry hash (M0-M3, the plan-stated product laws) and every T32 record's
     recomputes. Scheme 2 is 0.3 without rule_catalog_version, plus refs (an IR builtin's ref without it too).
  H2 hash_migration. One line per law, scheme 1 -> 2 over the byte-identical statement, both hashes recomputed on the
     tree with no Bend run; G2's tie needs both hashes. A scheme-2 law takes no catalog_rederivation line: recatalog
     skips it and check_entry rejects one. A scheme-2 law's registry hash changes only through such a line.
  H3 Line ids. Every new line carries the sha256 of its canonical JSON; G2 rejects a wrong or a second id, append
     refuses a line the log holds.
  H4 migrate-hash: a dry run writes nothing; --apply (on a copy) leaves every law of M3 (laws/M3 and the plan-stated
     product laws) under scheme 2, its registry, bindings and records on the new hashes and holon derive reproducing
     laws/M3, while M2 keeps scheme 1 byte for byte; a second run changes nothing.
  H5 Aggregates: spec/<M>/predictions.json and amendments.jsonl are what their per-key sources give (byte-identical to
     the files before PV2A for their keys); a later key lands at the end; a branch's aggregate-only key is absorbed; a
     conflict writes nothing; the prereg audit counts the sources as prereg inputs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests_m3._m3 import ROOT, copy_repo, holon_module, load_json

ZERO = "sha256:" + "0" * 64


def law_files(m: str, root: Path = ROOT) -> list[Path]:
    return sorted((root / "laws" / m).glob("L*.json")) + sorted((root / "laws" / m).glob("*/L*.json"))


def scheme1(law: dict) -> dict:
    return {k: v for k, v in law.items() if k != "hash_scheme"}


def pre_pv2a_hash(law: dict, refs: dict | None) -> str:
    """The statement hash as holon.ir and holon.rules.disch_profile computed it before PV2A (frozen copy)."""
    canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")  # noqa
    if law.get("ir_version") == "holon-disch-profile/0.1":
        return "sha256:" + hashlib.sha256(canon(law["statement"])).hexdigest()
    if law.get("ir_version") == "holon-ir/0.3":
        core = {k: law[k] for k in ("ir_version", "law_id", "rule", "rule_catalog_version", "statement")}
        core["refs"] = dict(sorted((refs or {}).items()))
    else:
        core = {k: law[k] for k in ("ir_version", "law_id", "rule", "facts_sha256", "statement")}
    return "sha256:" + hashlib.sha256(canon(core)).hexdigest()


def a_law() -> dict:
    """An M3 PAR law as scheme 1 (whatever scheme the tree is under)."""
    return scheme1(load_json(sorted((ROOT / "laws" / "M3").glob("L_par_*.json"))[0]))


class TestOneHash(unittest.TestCase):
    """H1."""

    def test_scheme_1_is_the_hash_before_pv2a(self):
        ir, R = holon_module("holon.ir"), holon_module("holon.gen.refs")
        n = 0
        for m in ("M0", "M1", "M2", "M3", "T32"):
            for p in law_files(m):
                law = scheme1(load_json(p))
                refs = R.tree_refs(law, ROOT) if law["ir_version"] == "holon-ir/0.3" else None
                with self.subTest(law=p.relative_to(ROOT).as_posix()):
                    self.assertEqual(ir.statement_hash(law, refs), pre_pv2a_hash(law, refs))
                    if refs is not None:   # the resolver form gives the same hash
                        self.assertEqual(ir.statement_hash(law, lambda l: R.tree_refs(l, ROOT)), pre_pv2a_hash(law, refs))
                n += 1
        self.assertGreaterEqual(n, 180)

    def test_every_registry_hash_recomputes(self):
        """M0, M1 and M2's registries (and M3's, and the plan-stated product laws') are what the one implementation
        gives; a scheme-2 law's scheme-1 hash is its hash_migration line's old hash. T32's records likewise."""
        ir, MP, SD = holon_module("holon.ir"), holon_module("holon.mpipeline"), holon_module("holon.statement_diff")
        R, DL = holon_module("holon.gen.refs"), holon_module("holon.derivation.laws")
        lines = [json.loads(x) for x in (ROOT / SD.LOG).read_text().splitlines() if x.strip()]
        mig = {(e["law_id"], e["new_hash"]): e for e in lines if e.get("kind") == "hash_migration"}
        for m in ("M0", "M1", "M2", "M3"):
            with self.subTest(milestone=m):
                laws, reg = ir.load_laws_any(m, ROOT), ir.load_registry(m, ROOT)
                MP.check_registry_multi(laws, reg, m, root=ROOT)
                for law in laws:
                    if law.get("hash_scheme", 1) == 2:
                        e = mig.get((law["law_id"], reg["statements"][law["law_id"]]))
                        self.assertIsNotNone(e, f"{law['law_id']}: scheme 2 without its hash_migration line")
                        self.assertEqual(e["old_hash"], R.tree_law_hash(scheme1(law), ROOT))
                        self.assertEqual(SD.unschemed(e["new"]), SD.unschemed(law))
        side = DL.side_of(ROOT, DL.LAWS_SIDECAR)
        reg = load_json(ROOT / side["law_set"]["laws"] / "REGISTRY.json")["statements"]
        for lid, h in reg.items():
            self.assertEqual(DL.statement_hash(load_json(ROOT / side["law_set"]["laws"] / f"{lid}.json"), ROOT), h)
        dp = holon_module("holon.rules.disch_profile")
        for p in law_files("T32"):
            law, rec = load_json(p), load_json(ROOT / "results" / "T32" / p.name)
            self.assertEqual(rec["statement_hash"], ir.statement_hash(law))
            self.assertEqual(rec["statement_hash"], dp.statement_hash(law["statement"]))

    def test_scheme_2_drops_the_catalog_version(self):
        ir, R = holon_module("holon.ir"), holon_module("holon.gen.refs")
        law = a_law()
        refs = R.tree_refs(law, ROOT)
        bumped = dict(law, rule_catalog_version="holon-rules/99.0")
        self.assertNotEqual(ir.statement_hash(law, refs), ir.statement_hash(bumped, refs))
        s2, b2 = ir.with_hash_scheme(law, 2), ir.with_hash_scheme(bumped, 2)
        self.assertEqual(ir.statement_hash(s2, refs), ir.statement_hash(b2, refs))
        self.assertNotEqual(ir.statement_hash(s2, refs), ir.statement_hash(law, refs))
        self.assertEqual(list(s2).index("hash_scheme"), list(s2).index("rule_catalog_version") + 1)
        for k in ("statement", "law_id", "rule"):   # every other hashed key still moves it
            other = copy.deepcopy(s2)
            other[k] = {"x": 1} if k == "statement" else "L_other"
            self.assertNotEqual(ir.statement_hash(other, refs), ir.statement_hash(s2, refs), k)
        # an IR builtin's ref: the catalog version under scheme 1 only
        for lw, moved in ((law, True), (s2, False)):
            a, b = R._Closure(lw, {}, None, [], ROOT), R._Closure(dict(lw, rule_catalog_version="holon-rules/99.0"),
                                                                  {}, None, [], ROOT)
            a.fn("eq_nat", [])
            b.fn("eq_nat", [])
            self.assertEqual(a.out["eq_nat"] != b.out["eq_nat"], moved)

    def test_hash_scheme_is_checked(self):
        ir = holon_module("holon.ir")
        law = a_law()
        for bad in (0, 3, True, "2", None):
            with self.subTest(hash_scheme=bad):
                with self.assertRaises(ir.IRError):
                    ir.statement_hash(dict(law, hash_scheme=bad), {})
        m0 = load_json(law_files("M0")[0])
        with self.assertRaises(ir.IRError):
            ir.statement_hash(dict(m0, hash_scheme=2))
        self.assertIs(ir.with_hash_scheme(m0, 2), m0)
        self.assertIs(ir.with_hash_scheme(law, 1), law)
        self.assertEqual(ir.statement_hash(dict(law, hash_scheme=1), {}), ir.statement_hash(law, {}))

    def test_the_schema_allows_scheme_2_only_beside_the_catalog_version(self):
        from tests_m3._m3 import validate
        a, b = ROOT / "spec/schemas/law_ir_0_3.schema.json", ROOT / "docs/adoption/Q4/schemas/law_ir_0_3.schema.json"
        self.assertEqual(a.read_bytes(), b.read_bytes())
        ir = holon_module("holon.ir")
        law = ir.with_hash_scheme(a_law(), 2)
        self.assertEqual(validate(law, a), [])
        self.assertNotEqual(validate(dict(law, hash_scheme=3), a), [])
        self.assertNotEqual(validate({k: v for k, v in law.items() if k != "rule_catalog_version"}, a), [])


class TestHashMigrationLine(unittest.TestCase):
    """H2."""

    @classmethod
    def setUpClass(cls):
        cls.SD = holon_module("holon.statement_diff")
        cls.entry = cls.SD.hash_migration_entry(a_law(), "M3", ROOT, "(test)")

    def e(self) -> dict:
        return copy.deepcopy(self.entry)

    def test_a_line_is_accepted_and_every_other_change_rejected(self):
        SD = self.SD
        r = SD.check_entry(self.e(), ROOT)
        self.assertTrue(r["ok"], r["reason"])
        self.assertEqual(SD.acceptance(self.e(), r, ROOT)["schemes"], [1, 2])

        def setk(side, k, v):
            return lambda e: e[side].__setitem__(k, v)
        cases = {
            "the claim changes": lambda e: e["new"]["statement"].__setitem__("claim", {"eq": [{"bool": True},
                                                                                           {"bool": False}]}),
            "the notes change": setk("new", "notes", "edited"),
            "the catalog changes too": setk("new", "rule_catalog_version", "holon-rules/99.0"),
            "both under scheme 1": lambda e: e["new"].pop("hash_scheme"),
            "both under scheme 2": setk("old", "hash_scheme", 2),
            "scheme 2 -> 1": lambda e: (e["old"].__setitem__("hash_scheme", 2), e["new"].pop("hash_scheme")),
            "a wrong old hash": lambda e: e.__setitem__("old_hash", ZERO),
            "a wrong new hash": lambda e: e.__setitem__("new_hash", ZERO),
            "the hashes swapped": lambda e: e.update(old_hash=e["new_hash"], new_hash=e["old_hash"]),
            "another milestone": lambda e: e.__setitem__("milestone", "M2"),
            "a holon-ir/0.2 law": lambda e: (e["old"].__setitem__("ir_version", "holon-ir/0.2"),
                                             e["new"].__setitem__("ir_version", "holon-ir/0.2")),
            "two laws": setk("new", "law_id", "L_par_other"),
            "no old hash": lambda e: e.pop("old_hash"),
        }
        for name, edit in cases.items():
            with self.subTest(case=name):
                e = self.e()
                edit(e)
                r = SD.check_entry(e, ROOT)
                self.assertFalse(r["ok"], r["reason"])

    def test_the_tie_needs_both_hashes(self):
        SD, e = self.SD, self.e()
        ch = {"law_id": e["law_id"], "old": e["old"], "new": e["new"], "old_hash": e["old_hash"],
              "new_hash": e["new_hash"]}
        self.assertTrue(SD.covers(e, ch))
        self.assertFalse(SD.covers(e, {k: v for k, v in ch.items() if k != "new_hash"}))
        self.assertFalse(SD.covers(e, {**ch, "old_hash": ZERO}))
        self.assertFalse(SD.covers(e, {**ch, "new": None}), "a deletion is only ever a signed weakening")
        # a line that keeps the statement (a binding_change) never covers a scheme move: the cores differ
        self.assertNotEqual(SD.core(e["old"]), SD.core(e["new"]))
        self.assertEqual(SD.core(e["old"]), SD.core(dict(e["old"], hash_scheme=1)))

    def test_a_binding_moves_with_its_line_only_when_nothing_else_does(self):
        B, e = holon_module("holon.bindings"), self.e()
        lid = e["law_id"]
        self.assertTrue(B.entry_covers(e, lid, e["new"], True, []))
        self.assertFalse(B.entry_covers(e, lid, e["new"], True, ["some_def"]))
        self.assertFalse(B.entry_covers(e, lid, e["new"], True, [], hash_only=False))
        self.assertFalse(B.entry_covers(e, lid, e["new"], False, ["some_def"]))

    def test_a_scheme_2_law_takes_no_catalog_rederivation_line(self):
        SD = self.SD
        old = dict(self.e()["new"], rule_catalog_version="holon-rules/1.1")
        new = dict(self.e()["new"], rule_catalog_version="holon-rules/1.2")
        e = {"kind": "catalog_rederivation", "law_id": old["law_id"], "milestone": "M3", "old_catalog": "holon-rules/1.1",
             "new_catalog": "holon-rules/1.2", "old_hash": ZERO, "new_hash": ZERO, "derivation": {}, "old": old,
             "new": new}
        r = SD.check_entry(e, ROOT)
        self.assertFalse(r["ok"])
        self.assertIn("scheme 2", r["reason"])
        ch = {"law_id": old["law_id"], "old": old, "new": new, "at": "x", "old_hash": ZERO, "new_hash": ZERO}
        with mock.patch.object(SD, "registry_changes", lambda m, root: {"git": True, "changes": [ch], "note": ""}), \
                mock.patch.object(SD, "scan", lambda path, root, **kw: {"entries": []}):
            es, notes = SD.catalog_rederivation_entries("M3", ROOT)
        self.assertEqual(es, [])
        self.assertEqual(len(notes), 1)
        self.assertIn("scheme 2", notes[0])

    def test_scheme_2_hashes_move_only_through_hash_migration_lines(self):
        """Every registry change since the log was introduced whose new law is under scheme 2 is a scheme move covered
        by an accepted hash_migration line with the registry's two hashes (needs the history)."""
        SD = self.SD
        rc = SD.registry_changes("M3", ROOT)
        self.assertTrue(rc["git"], "the registry history needs the repository")
        s2 = [ch for ch in rc["changes"] if isinstance(ch.get("new"), dict) and ch["new"].get("hash_scheme", 1) == 2]
        if not s2:
            return   # before the migration: no scheme-2 law
        ok = [x["entry"] for x in SD.scan(ROOT / SD.LOG, ROOT, kinds=("hash_migration",))["entries"] if x["ok"]]
        for ch in s2:
            with self.subTest(law=ch["law_id"], at=ch["at"]):
                self.assertEqual(ch["old"].get("hash_scheme", 1), 1, "a scheme-2 hash moved again")
                self.assertTrue([e for e in ok if SD.covers(e, ch)])


class TestLineIds(unittest.TestCase):
    """H3 (on a log outside the repository: every line is checked against the working tree)."""

    def setUp(self):
        self.SD = holon_module("holon.statement_diff")
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-test-ids-"))
        self.log = self.tmp / "STATEMENT_DIFF.jsonl"
        self.log.write_text("")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_append_writes_the_id_and_refuses_the_same_line(self):
        SD = self.SD
        e = SD.hash_migration_entry(a_law(), "M3", ROOT, "(test)")
        with mock.patch.object(SD, "LOG", self.log):
            r = SD.append(e, ROOT)
            self.assertTrue(r["ok"], r["reason"])
            line = json.loads(self.log.read_text())
            self.assertEqual(line["id"], SD.line_id(line))
            self.assertEqual(line["id"], r["id"])
            before = self.log.read_bytes()
            r2 = SD.append(e, ROOT)
            self.assertFalse(r2["ok"])
            self.assertEqual(self.log.read_bytes(), before)
        s = SD.scan(self.log, ROOT)
        self.assertEqual(s["problems"], [])

    def test_g2_rejects_a_wrong_or_a_second_id(self):
        SD = self.SD
        e = SD.hash_migration_entry(a_law(), "M3", ROOT, "(test)")
        with mock.patch.object(SD, "LOG", self.log):
            self.assertTrue(SD.append(e, ROOT)["ok"])
        good = self.log.read_text()
        self.log.write_text(good + good)
        s = SD.scan(self.log, ROOT)
        self.assertTrue(any("a second line with id" in p for p in s["problems"]), s["problems"])
        x = json.loads(good)
        x["reason"] = "edited after its id was computed"
        self.log.write_text(json.dumps(x, sort_keys=True) + "\n")
        s = SD.scan(self.log, ROOT)
        self.assertTrue(any("its id is not the sha256" in p for p in s["problems"]), s["problems"])


class TestMigrateHash(unittest.TestCase):
    """H4."""

    def test_a_dry_run_writes_nothing(self):
        SD = holon_module("holon.statement_diff")
        watched = ["laws/M3/REGISTRY.json", "laws/M2/REGISTRY.json", "spec/bindings/M3.json", "spec/bindings/changes.jsonl",
                   "laws/STATEMENT_DIFF.jsonl", "laws/M3/DERIVATION.json"]
        snap = lambda: {p: (ROOT / p).read_bytes() for p in watched} | {  # noqa: E731
            m: (ROOT / "spec" / m / "hash_scheme.json").is_file() for m in ("M2", "M3")}
        before = snap()
        out = []
        self.assertEqual(SD.migrate_hash("M3", ROOT, apply=False, log=out.append), 0)
        self.assertEqual(snap(), before)
        self.assertIn("dry run", out[-1])

    def test_apply_on_a_copy_moves_everything_and_a_second_run_changes_nothing(self):
        repo = copy_repo()
        try:
            SD, ir, MP = holon_module("holon.statement_diff"), holon_module("holon.ir"), holon_module("holon.mpipeline")
            rules, contracts = holon_module("holon.rules"), holon_module("holon.contracts")
            old_reg = {m: load_json(repo / "laws" / m / "REGISTRY.json")["statements"] for m in ("M3",)}
            was1 = {(m, load_json(p)["law_id"]) for m in ("M3",) for p in law_files(m, repo)
                    if load_json(p).get("hash_scheme", 1) == 1}
            m2 = lambda: {str(p.relative_to(repo)): p.read_bytes() for p in law_files("M2", repo)  # noqa: E731
                          + [repo / "laws/M2/REGISTRY.json", repo / "spec/bindings/M2.json"]}
            m2_before = m2()
            out = []
            self.assertEqual(SD.migrate_hash("M3", repo, apply=True, log=out.append), 0, "\n".join(out[-5:]))
            lines = [json.loads(x) for x in (repo / SD.LOG).read_text().splitlines() if x.strip()]
            mig = [e for e in lines if e.get("kind") == "hash_migration"]
            self.assertEqual(m2(), m2_before, "M2 keeps hash scheme 1")
            self.assertFalse((repo / "spec" / "M2" / "hash_scheme.json").exists())
            for m in ("M3",):
                with self.subTest(milestone=m):
                    laws, reg = ir.load_laws_any(m, repo), ir.load_registry(m, repo)
                    self.assertEqual({law.get("hash_scheme") for law in laws}, {2})
                    MP.check_registry_multi(laws, reg, m, root=repo)
                    res = contracts.with_contracts(m, repo, rules.compute(m, repo))
                    for lid, law in res["laws"].items():
                        self.assertEqual(rules.dumps(law), (repo / "laws" / m / f"{lid}.json").read_text(), lid)
                    self.assertEqual(rules.dumps(res["registry"]), (repo / "laws" / m / "REGISTRY.json").read_text())
                    bound = load_json(repo / "spec" / "bindings" / f"{m}.json")["laws"]
                    self.assertEqual({k: x["statement_hash"] for k, x in bound.items()}, reg["statements"])
                    for p in sorted((repo / "results" / m).glob("L*.json")):
                        h = load_json(p).get("statement_hash")
                        if h != reg["statements"].get(p.stem):   # only a record that trailed its registry before
                            self.assertNotEqual(h, old_reg[m].get(p.stem), p.name)
                    for lid in reg["statements"]:   # a law born under scheme 2 (after the migration) has no line
                        e = [x for x in mig if x["law_id"] == lid and x["milestone"] == m]
                        if (m, lid) in was1 or e:
                            self.assertEqual([x["new_hash"] for x in e], [reg["statements"][lid]], lid)
                            self.assertEqual(e[0]["id"], SD.line_id(e[0]))
            digest = lambda: {str(p.relative_to(repo)): p.read_bytes() for d in ("laws", "spec/bindings", "results/M3")  # noqa
                              for p in sorted((repo / d).rglob("*")) if p.is_file()}
            before = digest()
            self.assertEqual(SD.migrate_hash("M3", repo, apply=True, log=out.append), 0)
            self.assertEqual(digest(), before, "a second run changes nothing")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestAggregates(unittest.TestCase):
    """H5."""

    def setUp(self):
        self.A = holon_module("holon.aggregate")
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-test-agg-"))
        shutil.copytree(ROOT / "spec" / "M3", self.tmp / "spec" / "M3",
                        ignore=shutil.ignore_patterns("facts", "lib"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_committed_aggregates_are_generated(self):
        for m in ("M2", "M3", "M4"):
            with self.subTest(milestone=m):
                self.assertTrue((ROOT / "spec" / m / "predictions").is_dir())
                self.assertEqual(self.A.check(m, ROOT), [])
                self.assertEqual(self.A.render(m, ROOT), self.A.render(m, ROOT))

    def test_a_later_key_and_its_lines_land_at_the_end(self):
        A, d = self.A, self.tmp / "spec" / "M3"
        pred, amend = (d / "predictions.json").read_text(), (d / "amendments.jsonl").read_text()
        (d / "predictions" / "I999.json").write_text(A.dump({"prompt": "x"}))
        (d / "predictions" / "I100.json").write_text(A.dump({"prompt": "y"}))
        ln24 = json.dumps({"iteration": "I24", "kind": "instrument_inconsistency", "test": "t.py::a", "why": "w"})
        ln999 = json.dumps({"iteration": "I999", "kind": "instrument_inconsistency", "test": "t.py::b", "why": "w"})
        with (d / "amendments" / "I24.jsonl").open("a") as fh:
            fh.write(ln24 + "\n")
        (d / "amendments" / "I999.jsonl").write_text(ln999 + "\n")
        self.assertEqual(sorted(A.write("M3", self.tmp)), ["spec/M3/amendments.jsonl", "spec/M3/predictions.json"])
        its = list(json.loads((d / "predictions.json").read_text())["iterations"])
        self.assertEqual(its[-2:], ["I100", "I999"])
        self.assertEqual(its[:-2], list(json.loads(pred)["iterations"]))
        # the lines split at PV2A stay a byte-identical prefix; every later line follows, by key in natural order
        k = len(json.loads((d / "amendments" / "_index.json").read_text())["order"])
        new, old = (d / "amendments.jsonl").read_text().splitlines(), amend.splitlines()
        self.assertEqual(new[:k], old[:k])
        self.assertEqual(sorted(new), sorted(old + [ln24, ln999]))
        keys = [json.loads(x)["iteration"] for x in new[k:]]
        self.assertEqual(keys, sorted(keys, key=A.natural))
        self.assertEqual(new[-1], ln999)
        (d / "predictions" / "I999.json").unlink()
        (d / "predictions" / "I100.json").unlink()
        A.write("M3", self.tmp)
        self.assertEqual((d / "predictions.json").read_text(), pred, "the earlier keys' bytes are unchanged")

    def test_an_aggregate_only_key_is_absorbed_and_a_conflict_writes_nothing(self):
        A, d = self.A, self.tmp / "spec" / "M3"
        doc = json.loads((d / "predictions.json").read_text())
        doc["iterations"]["I998"] = {"prompt": "from a branch older than PV2A"}
        (d / "predictions.json").write_text(A.dump(doc))
        with (d / "amendments.jsonl").open("a") as fh:
            fh.write(json.dumps({"iteration": "I41", "test": "t.py::c", "why": "w"}) + "\n")
        self.assertNotEqual(A.check("M3", self.tmp), [])
        done = A.regenerate("M3", self.tmp)
        self.assertIn("spec/M3/predictions/I998.json", done)
        self.assertEqual(A.check("M3", self.tmp), [])
        self.assertEqual(json.loads((d / "predictions.json").read_text())["iterations"]["I998"],
                         {"prompt": "from a branch older than PV2A"})
        self.assertEqual(len((d / "amendments" / "I41.jsonl").read_text().splitlines()), 2)
        doc = json.loads((d / "predictions.json").read_text())
        doc["iterations"]["I41"] = {"edited": True}
        (d / "predictions.json").write_text(A.dump(doc))
        src = (d / "predictions" / "I41.json").read_bytes()
        with self.assertRaises(A.AggregateError):
            A.regenerate("M3", self.tmp)
        self.assertEqual((d / "predictions" / "I41.json").read_bytes(), src)

    def test_the_prereg_audit_counts_the_sources_as_prereg_inputs(self):
        P = holon_module("holon.audit.prereg")
        for f in ("spec/M3/predictions/I99.json", "spec/M3/amendments/I99.jsonl", "spec/M2/predictions/_index.json"):
            self.assertTrue(any(rx.match(f) for rx in P._ALWAYS_ALLOWED + P._AGGREGATE_SOURCES), f)
        for f in ("spec/M3/predictions/x/I99.json", "spec/M3/predictionsX.json", "spec/M3/lib2/x.json"):
            self.assertFalse(any(rx.match(f) for rx in P._ALWAYS_ALLOWED + P._AGGREGATE_SOURCES), f)


if __name__ == "__main__":
    unittest.main()
