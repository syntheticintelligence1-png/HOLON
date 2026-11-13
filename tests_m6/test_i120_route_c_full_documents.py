"""I120 (M6, generality): route C reads beyond the store limit. Contract tests (spec/M6/predictions/I120.json;
prompts/I120_route_c_full_documents.md; HUMAN_ANSWERS Q93 (2), the lead's ruling).

The wall I117 measured: under go.ops "typed" the Go documents of c08, c09, c14 and c18 grew past the protocol's
go.store_max_bytes (1,000,000). holon eval holon removed a Go document over the limit from the run's working tree right
after extraction, before any later stage ran, so route C had no Go-op document for those entries and derived none of
their PAR laws (64 of I116's 93). The storage limit decided what was evaluated.

The ruling: a storage limit must not decide what is evaluated. Under the opt-in go.store_scope "commit"
(spec/M6/lib/i120_run.json):

  (1) Every extracted document stays whole in the run's working tree, and every stage (roles, route C's Go-op
      documents, diagram, evidence, the machines, derive, run, bind) reads it in full
      (holon.eval.holon_run.store_documents).
  (2) store_max_bytes governs only what is committed: a Go document over the limit is removed from the entry's
      committed output and recorded by sha256 and bytes only (stored false), exactly as before
      (holon.eval.holon_run.commit_documents); with --vault the whole document is kept in the vault, never in the
      repository. Every other committed file over the limit is recorded in <id>/large_files.json by store_large, as
      before.
  (3) The record says so per document: an extracted document's row carries evaluated "full" beside stored (false
      means "evaluated in full, stored by hash"). Without the key the row has no evaluated field, and a Go document
      over the limit is removed right after extraction (every earlier protocol).

The planted entry (tests_m6/fixtures/i120/planted.json) is a git repository built in a scratch directory from I117's
planted Go package (written from the Go specification, never from corpus code), run end to end through
holon.eval.holon_run.run_entry under --compose with three protocols: over (store_max_bytes below the size of its typed
document), under (the protocol's own limit) and the control (the small limit without store_scope, the wall). The
corpus measure is results/M6/I120/holon/corpus.json (holon eval holon --protocol spec/M6/lib/i120_run.json --compose),
on the base the coordinator names (Q92 (4)).
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

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m6" / "fixtures" / "i120"
PROTO = "spec/M6/lib/i120_run.json"
OUT = ROOT / "results" / "M6" / "I120"
HOLON_CORPUS = OUT / "holon" / "corpus.json"
I117_CORPUS = ROOT / "results" / "M6" / "I117" / "holon" / "corpus.json"
SEALED = OUT / "sealed.json"
LAW_ID = re.compile(r"\bL_[A-Za-z0-9_]+")
STORAGE = ("stored",)   # the row fields the store limit may move (sha256, bytes and evaluated never do)


def pred(pid: str) -> dict:
    d = json.loads((ROOT / "spec" / "M6" / "predictions" / "I120.json").read_text(encoding="utf-8"))
    (p,) = [x for x in d["predictions"] if x["id"] == pid]
    return p


def planted() -> dict:
    return json.loads((FIX / "planted.json").read_text(encoding="utf-8"))


def protocol(name: str = PROTO) -> dict:
    from holon.eval import common
    return json.loads(json.dumps(common.load_json(ROOT / name)))


def variant(kind: str) -> dict:
    """over: the planted small limit, store_scope "commit"; under: the protocol's own limit; control: the small limit
    without store_scope (the store limit decides what is evaluated, as before I120)."""
    p = protocol()
    if kind in ("over", "control"):
        p["go"]["store_max_bytes"] = planted()["store_max_bytes_small"]
    if kind == "control":
        p["go"].pop("store_scope")
        p["go"].pop("store_scope_doc")
    return p


_GIT_ENV = {"GIT_AUTHOR_NAME": "holon", "GIT_AUTHOR_EMAIL": "planted@holon.invalid", "GIT_COMMITTER_NAME": "holon",
            "GIT_COMMITTER_EMAIL": "planted@holon.invalid", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1"}


def _git(cwd: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **_GIT_ENV})
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def planted_entry(tmp: Path) -> tuple[dict, Path]:
    """The planted entry and the directory holding its bare clone (as common.repo_cache names it)."""
    from holon.eval import common
    f = planted()
    w = tmp / "work"
    shutil.copytree(ROOT / f["package"], w)
    _git(w, "init", "-q", "-b", "main")
    _git(w, "add", "-A")
    _git(w, "commit", "-q", "-m", "prefix")
    prefix = _git(w, "rev-parse", "HEAD")
    with open(w / f["fix_file"], "a", encoding="utf-8") as fh:
        fh.write("\n" + f["fix_line"] + "\n")
    _git(w, "commit", "-q", "-am", "fix")
    fix = _git(w, "rev-parse", "HEAD")
    repos = tmp / "repos"
    owner, name = common.gh_slug(f["entry"]["repo"])
    repos.mkdir()
    _git(tmp, "clone", "-q", "--bare", str(w), str(repos / f"{owner}__{name}.git"))
    return {**f["entry"], "prefix_commit": prefix, "fix_commit": fix}, repos


class _Planted(unittest.TestCase):
    """The planted entry, run once per protocol variant through holon_run.run_entry (--compose, roles static)."""
    runs: dict = {}
    tmp: Path | None = None

    @classmethod
    def setUpClass(cls):
        if _Planted.tmp is None:
            _Planted.tmp = Path(tempfile.mkdtemp(prefix="holon-i120-"))

    def run_of(self, kind: str) -> tuple[dict, Path, Path]:
        """(row, the entry's committed directory, the vault) for one variant."""
        if kind not in _Planted.runs:
            from holon.eval import common
            from holon.eval import holon_run as H
            t = _Planted.tmp / kind
            t.mkdir()
            entry, repos = planted_entry(t)
            old_repos, old_vault, old_reach = common.REPOS, H.VAULT, dict(common._REACH)
            vault = t / "vault"
            vault.mkdir()
            common.REPOS, H.VAULT = repos, vault
            try:
                stage = t / "stage"
                stage.mkdir()
                row = H.run_entry(entry, variant(kind), ROOT, stage, {}, {"mode": "static", "proposed": None}, True)
            finally:
                common.REPOS, H.VAULT = old_repos, old_vault
                common._REACH.clear()
                common._REACH.update(old_reach)
            _Planted.runs[kind] = (row, stage / entry["id"], vault / entry["id"])
        return _Planted.runs[kind]

    @staticmethod
    def doc_rows(row: dict) -> list:
        return [d for d in row["documents"] if d.get("language") == "go" and d.get("status") == "extracted"]

    @staticmethod
    def par(row: dict) -> int:
        return sum(f["derived"] for k, f in (row.get("laws_aggregate") or {}).items() if k.startswith("PAR/"))


class TestOverLimit(_Planted):
    """P1: the over-limit document is evaluated in full; the committed output holds its sha256 and size only."""

    def test_p1_route_c_derives_from_the_over_limit_document(self):
        row, edir, _v = self.run_of("over")
        (d,) = self.doc_rows(row)
        self.assertGreater(d["bytes"], planted()["store_max_bytes_small"])
        self.assertIs(d["stored"], False)
        self.assertEqual(d["evaluated"], "full")
        self.assertEqual(row["stages"]["goops"]["status"], "ok", row["stages"].get("goops"))
        for s in ("roles", "diagram", "evidence", "derive", "bind", "run"):
            self.assertEqual(row["stages"][s]["status"], "ok", (s, row["stages"][s]))
        self.assertGreaterEqual(self.par(row), pred("I120-P1")["expected"]["par_derived_at_least"])

    def test_p1_committed_output_holds_hash_and_size_only(self):
        row, edir, vault = self.run_of("over")
        (d,) = self.doc_rows(row)
        self.assertFalse((edir / "facts" / d["file"]).exists())
        self.assertEqual(len(d["sha256"]), 64)
        lim = planted()["store_max_bytes_small"]
        big = [p.relative_to(edir).as_posix() for p in edir.rglob("*") if p.is_file() and p.stat().st_size > lim]
        self.assertEqual(big, [])
        lf = json.loads((edir / "large_files.json").read_text()) if (edir / "large_files.json").is_file() else []
        self.assertNotIn(f"facts/{d['file']}", [r["path"] for r in lf])   # the row records it, once
        from holon.eval.holon_run import sha256_bytes
        kept = vault / "facts" / d["file"]   # the vault keeps the whole document, outside the repository
        self.assertTrue(kept.is_file())
        self.assertEqual((len(kept.read_bytes()), sha256_bytes(kept.read_bytes())), (d["bytes"], d["sha256"]))
        for p in edir.rglob("*"):
            if p.is_file():
                self.assertNotEqual(p.read_bytes(), kept.read_bytes(), p)


class TestEitherSide(_Planted):
    """P2: the same package under the limit: the derived laws, and every committed byte apart from the storage fields,
    are identical either side of the limit."""

    def test_p2_rows_identical_but_storage(self):
        a, _ea, _va = self.run_of("over")
        b, _eb, _vb = self.run_of("under")
        (db,) = self.doc_rows(b)
        self.assertIs(db["stored"], True)
        self.assertEqual(db["evaluated"], "full")

        def strip(r):
            r = json.loads(json.dumps(r))
            for d in r["documents"]:
                for k in STORAGE:
                    d.pop(k, None)
            return r
        self.assertEqual(strip(a), strip(b))
        self.assertGreater(self.par(b), 0)
        self.assertEqual(a["laws_aggregate"], b["laws_aggregate"])
        self.assertEqual(a["laws_bundle_sha256"], b["laws_bundle_sha256"])

    def test_p2_committed_bytes_identical_but_storage(self):
        from holon.eval.holon_run import _tree_bytes, sha256_bytes
        a, ea, _va = self.run_of("over")
        b, eb, _vb = self.run_of("under")
        A, B = _tree_bytes(ea), _tree_bytes(eb)
        lf = json.loads(A.pop("large_files.json")) if "large_files.json" in A else []
        recorded = {r["path"]: (r["sha256"], r["bytes"]) for r in lf}
        for d in self.doc_rows(a):
            recorded[f"facts/{d['file']}"] = (d["sha256"], d["bytes"])
        lim = planted()["store_max_bytes_small"]
        for k, v in B.items():
            if len(v) > lim:   # over the small limit: recorded by hash and size on the over side, never stored
                self.assertNotIn(k, A, k)
                self.assertEqual(recorded.get(k), (sha256_bytes(v), len(v)), k)
            else:
                self.assertEqual(A.get(k), v, k)
        self.assertEqual(set(A) - set(B), set())
        self.assertEqual(set(recorded), {k for k, v in B.items() if len(v) > lim})


class TestControl(_Planted):
    """P3: the control. Without store_scope the same small limit decides what is evaluated (the wall I117 measured):
    the document is removed before route C, no PAR law is derived, the row has no evaluated field."""

    def test_p3_the_wall_without_the_opt_in(self):
        row, edir, _v = self.run_of("control")
        (d,) = self.doc_rows(row)
        self.assertIs(d["stored"], False)
        self.assertNotIn("evaluated", d)
        self.assertNotIn("goops", row["stages"])
        self.assertEqual(self.par(row), 0)
        self.assertFalse((edir / "facts" / d["file"]).exists())
        over, _e, _v2 = self.run_of("over")
        self.assertEqual({k: d[k] for k in ("sha256", "bytes", "stored")},
                         {k: self.doc_rows(over)[0][k] for k in ("sha256", "bytes", "stored")})


class TestUnits(unittest.TestCase):
    """P4: the storage rule as a unit: store_scope's values, and store_documents without the opt-in as before."""

    def docs(self, tmp: Path, size: int) -> tuple[list, Path]:
        facts = tmp / "facts"
        facts.mkdir()
        (facts / "go_1.go.extracted.json").write_bytes(b"x" * size)
        (facts / "a.sol.extracted.json").write_bytes(b"y" * size)
        return [{"language": "go", "file": "go_1.go.extracted.json", "status": "extracted"},
                {"language": "solidity", "file": "a.sol.extracted.json", "status": "extracted"},
                {"language": "go", "status": "failed"}], facts

    def test_p4_scope_values(self):
        from holon.eval import common
        from holon.eval import holon_run as H
        self.assertEqual(H.store_scope({"go": {}}), "evaluate")
        self.assertEqual(H.store_scope({"go": {"store_scope": "commit"}}), "commit")
        with self.assertRaises(common.Refused):
            H.store_scope({"go": {"store_scope": "always"}})

    def test_p4_without_the_opt_in_as_before(self):
        from holon.eval import holon_run as H
        with tempfile.TemporaryDirectory() as t:
            docs, facts = self.docs(Path(t), 100)
            H.store_documents(docs, facts, {"go": {"store_max_bytes": 50}})
            self.assertFalse((facts / "go_1.go.extracted.json").exists())
            self.assertTrue((facts / "a.sol.extracted.json").exists())
            self.assertEqual([d.get("stored") for d in docs], [False, True, None])
            self.assertFalse(any("evaluated" in d for d in docs))
            self.assertEqual(H.commit_documents(Path(t), docs, {"go": {}}, "x"), [])

    def test_p4_with_the_opt_in_kept_then_committed_by_hash(self):
        from holon.eval import holon_run as H
        with tempfile.TemporaryDirectory() as t:
            docs, facts = self.docs(Path(t), 100)
            proto = {"go": {"store_max_bytes": 50, "store_scope": "commit"}}
            H.store_documents(docs, facts, proto)
            self.assertTrue((facts / "go_1.go.extracted.json").exists())
            self.assertEqual([d.get("evaluated") for d in docs], ["full", "full", None])
            self.assertEqual(docs[0]["sha256"], H.sha256_bytes(b"x" * 100))
            self.assertEqual(H.commit_documents(Path(t), docs, proto, "x"), ["go_1.go.extracted.json"])
            self.assertFalse((facts / "go_1.go.extracted.json").exists())
            self.assertTrue((facts / "a.sol.extracted.json").exists())


class TestCorpusSmoke(unittest.TestCase):
    """P5-P8: measures on I51's 20 entries (contaminated by I51, I103-I119 and I107), the counted run."""

    def doc(self) -> dict:
        self.assertTrue(HOLON_CORPUS.is_file(), "results/M6/I120/holon/corpus.json is missing")
        return json.loads(HOLON_CORPUS.read_text(encoding="utf-8"))

    def rows(self) -> dict:
        return {r["id"]: r for r in self.doc()["rows"]}

    def test_p5_documents_evaluated_in_full_stored_by_hash(self):
        e = pred("I120-P5")["expected"]
        self.assertEqual(self.doc()["preflight"]["status"], "ok")
        n = 0
        for i, r in self.rows().items():
            for d in r["documents"]:
                if d.get("status") == "extracted":
                    self.assertEqual(d.get("evaluated"), "full", (i, d["stem"]))
                    if d["stored"] is False:
                        n += 1
                        self.assertEqual(len(d["sha256"]), 64)
                        self.assertFalse((OUT / "holon" / i / "facts" / d["file"]).exists(), (i, d["file"]))
        self.assertGreaterEqual(n, e["documents_at_least"])

    def test_p6_par_laws_restored(self):
        e = pred("I120-P6")["expected"]
        par = sum(f["derived"] for r in self.rows().values() for k, f in (r.get("laws_aggregate") or {}).items()
                  if k.startswith("PAR/"))
        self.assertGreaterEqual(par, e["par_derived_at_least"])

    def test_p7_laws_aggregate(self):
        e = pred("I120-P7")["expected"]
        rows = self.rows()
        aggs = [(k, f) for r in rows.values() for k, f in (r.get("laws_aggregate") or {}).items()]
        for i, r in rows.items():
            self.assertEqual(r.get("laws"), [], i)   # Q56: per-law rows withheld
        for k, f in aggs:
            self.assertEqual(set(f), {"derived", "decided", "unknown"}, k)
            self.assertEqual(f["derived"], f["decided"] + f["unknown"], k)
        self.assertGreaterEqual(sum(f["derived"] for _k, f in aggs), e["derived_at_least"])
        self.assertGreaterEqual(sum(f["decided"] for _k, f in aggs), e["decided_at_least"])

    def test_p8_nothing_per_law_or_over_limit_committed(self):
        base = OUT / "holon"
        lim = protocol()["go"]["store_max_bytes"]
        hits = []
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(base).as_posix()
            if p.stat().st_size > lim and p.name != "corpus.json":
                hits.append(f"over the limit: {rel}")
            if LAW_ID.search(rel) or "/bindings/" in f"/{rel}" or p.name.endswith(".unbound.json"):
                hits.append(rel)
                continue
            if p.name == "corpus.json":
                for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                    if LAW_ID.search(json.dumps({k: v for k, v in r.items() if k != "laws_aggregate"})):
                        hits.append(f"corpus.json:{r['id']}")
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if LAW_ID.search(text):
                hits.append(rel)
        self.assertEqual(hits, [])


class TestSealedContaminated(unittest.TestCase):
    """P9: I106's targets, contaminated: post-I107 (aggregates only, Q56; Q72)."""

    def test_p9_spent_targets(self):
        self.assertTrue(SEALED.is_file(), "results/M6/I120/sealed.json is missing")
        d = json.loads(SEALED.read_text(encoding="utf-8"))
        self.assertEqual(d["label"], "contaminated: post-I107")
        for x in d["targets"]:
            self.assertNotIn("laws", x)
            self.assertEqual(len(x["bundle_sha256"]), 64, x["id"])
            for k in x.get("laws_aggregate", {}).values():
                self.assertEqual(set(k), {"derived", "decided", "unknown"}, x["id"])


class TestRegressions(unittest.TestCase):
    """P10: without the opt-in nothing changes."""

    def test_p10_no_earlier_protocol_names_store_scope(self):
        found = []
        for p in sorted((ROOT / "spec").glob("*/lib/*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if not isinstance(d, dict) or not isinstance(d.get("go"), dict) or "store_scope" not in d["go"]:
                continue
            it = str(d.get("iteration") or "")
            # amended (spec/M6/amendments/I120.jsonl): base_run.json is Q104's combined base, not an earlier protocol
            if p.name not in ("i120_run.json", "base_run.json") and not (it[1:].isdigit() and int(it[1:]) >= 120):
                found.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(found, [])

    def test_p10_protocol_is_its_base_plus_store_scope(self):
        b = protocol()
        a = protocol(b["base_protocol"])
        self.assertEqual(b["go"].pop("store_scope"), "commit")
        b["go"].pop("store_scope_doc")
        b.pop("base_protocol")
        a.pop("base_protocol", None)
        for d in (a, b):
            for k in ("doc", "iteration", "out"):
                d.pop(k)
            d["go_machines"].pop("out")
        self.assertEqual(a, b)

    def test_r1_earlier_jobs_listed(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        for job in ("tests-m6-i103", "tests-m6-i104", "tests-m6-i105", "tests-m6-i107", "tests-m6-i108",
                    "tests-m6-i109", "tests-m6-i110", "tests-m6-i111", "tests-m6-i112", "tests-m6-i115",
                    "tests-m6-i117"):
            self.assertTrue(f"name: {job}" in wf, job)


if __name__ == "__main__":
    unittest.main()
