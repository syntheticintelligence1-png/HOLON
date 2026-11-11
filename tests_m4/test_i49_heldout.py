"""I49: the held-out target's extraction, facts and diagram (key I49, spec/M4/predictions.json).

Written blind, at the I49 prereg: before anything under spec/heldout/ or from the sealed upstream was read, listed,
fetched or cloned. Every rule it checks is fixed in spec/M4/lib/heldout_protocol.json (the protocol) and recomputed by
tests_m4/_i49.py (the instrument), which never imports holon/.

Contract (the build must make every test here pass; it may add tests, never change these):

H0  The seal. spec/heldout/target.json is the human's description of the target (docs/HUMAN_ANSWERS.md Q7). Its
    values are found by role (_i49.sealed_roles: the one repository, the one 40-hex commit, the one .sol source).
    The I49 prereg commit touches nothing under spec/heldout/ and holds neither the sealed commit (full, or its first 8
    hex digits) nor the sealed source path in any file it changes; the sealed file is byte-identical at HEAD and at
    the prereg commit; every commit that adds a file of the held-out target (targets/<name>/, gen/targets/<name>/,
    gen/diagrams/<name>/, results/targets/<name>/) descends from the prereg commit.
H1  The target. Exactly one targets/<name>/target.json has checkout.sealed = "spec/heldout/target.json"; <name> follows
    rule T1; it validates against spec/M4/lib/target.schema.json; names holds every name of _i49.target_names;
    upstream.repo and upstream.pinned_commit are the sealed repository and commit; checkout.sealed_keys records the
    sealed key each came from; checkout.development is false. Its scope sidecar targets/<name>/extract_solidity.json
    follows rules S1-S5 (S3 recomputed by a regex walk of the sealed file's direct imports).
H2  `python -m holon target extract --target NAME [--check]` runs the target's extract method: for the held-out target
    the pinned Solidity frontend (holon extract solidity) with the scope sidecar over the checkout that config/holon.json
    extract.sources names for the sealed repository (HEAD the sealed commit), writing the document at the sidecar's
    output and the extraction report gen/targets/<name>/extraction.json (rule S6: dependency_version debt). --check
    writes nothing and exits 0 iff a fresh extraction reproduces both byte for byte.
H3  `python -m holon target coverage --target NAME [--check]` writes gen/targets/<name>/coverage.json in holon.coverage's
    format (the frontend's coverage walk over the compiler's output; it never reads the document it describes).
H4  `python -m holon target diagram --target NAME [--check]` writes one holon-diagram-transitions/0.1 diagram per fact
    document of the target at gen/diagrams/<name>/<stem_>.json (rules V1-V5, E1-E5); for the development target
    (morph) the one document is spec/M2/facts/morph_rollup.extracted.json, and for the toy target (abacus) the
    holon-facts/0.2 document goes through holon.diagram.build.
H5  `python -m holon target sizes [--check]` writes results/targets/sizes.json (spec/M4/lib/sizes.schema.json): the
    protocol's four rows, in order, each with |V|, |E|, per-kind counts and the obligations over its document.
H6  `python -m holon target gate --target NAME [--checks ID,..]` runs checks GENV, X1, X2, G8, D1, S1 in that order and
    writes results/targets/<name>/gate_report.json ({"target", "passed", "checks": {id: {"passed", "detail"}}},
    canonical JSON, no timing). GENV failing fails every other check as skipped. Exit 0 iff passed. I50 may add checks
    after these; it never drops or reorders them.

Tree claims are evaluated at HEAD; history claims over the first-parent chain from the I49 prereg commit to HEAD.
Tests that need the sealed checkout fail, never skip, when it is missing: fetch it as spec/heldout/target.json pins it.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m4._m4 import ROOT, copy_repo, load_json, predictions, validate
from tests_m4 import _i47
from tests_m4 import _i49 as H

KEY = "I49"
INSTRUMENTS = ["tests_m4/_i49.py", "spec/M4/lib/heldout_protocol.json", "spec/M4/lib/heldout_catalog_pin.json",
               "spec/M4/lib/sizes.schema.json", "spec/M4/lib/diagram_transitions.schema.json"]
I49_CHECKS = ["GENV", "X1", "X2", "G8", "D1", "S1"]
CATALOG = "holon-rules/1.15"
BASE = "7dc50894695b7c37c9a3ec4f2d1d5bfcdfcc545c"
AMENDED_PINS = {
    "tests_m4/_i49.py": "dd7dd81415d8aab9da1d2ba2f1149acab99672b536d2a68f887ed5acc4abcb02",
    "spec/M4/lib/heldout_protocol.json": "4e0fb1551931f6bcb235d19b5f1f531e60ecfa8599ce8ed788f3cded8a2d823d",
}
FACTS03_SCHEMA = ROOT / "spec" / "schemas" / "facts_0_3.schema.json"
MORPH_M3_DOC = "spec/M2/facts/morph_rollup.extracted.json"
MORPH_M3_DIAGRAM = "gen/diagrams/morph/morph_rollup_extracted.json"


def env() -> dict:
    e = dict(os.environ)
    e["BEND_NO_TELEMETRY"] = "1"
    return e


def holon(args: list[str], cwd: Path = ROOT, timeout: int = 3600) -> subprocess.CompletedProcess:
    e = env()
    e["PYTHONPATH"] = str(cwd) + os.pathsep + e.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, env=e, capture_output=True, text=True,
                          timeout=timeout)


def roles() -> dict:
    return H.sealed_roles(load_json(ROOT / H.SEAL))


def config() -> dict:
    return load_json(ROOT / "config" / "holon.json")


def checkout() -> Path:
    r = roles()
    src = (config().get("extract") or {}).get("sources") or {}
    if r["repo"] not in src:
        raise AssertionError(f"config/holon.json extract.sources has no checkout of {r['repo']}")
    p = Path(src[r["repo"]])
    if not (p / ".git").exists():
        raise AssertionError(f"no checkout at {p}: fetch it as {H.SEAL} pins it")
    return p


def solc_version() -> str:
    # Amended after the seal opened (spec/M4/amendments/I49.jsonl): the version number before '+', as the frontend
    # compares it (holon.frontends.solidity.compile.check_solc) and the development target's sidecar writes it
    out = subprocess.run([config()["replay"]["solc"], "--version"], capture_output=True, text=True).stdout
    return out.split("Version: ", 1)[1].split()[0].split("+", 1)[0]


def doc_rel(name: str) -> str:
    return load_json(ROOT / "targets" / name / "extract_solidity.json")["output"]


def diagram_rel(doc: str, name: str) -> str:
    return f"gen/diagrams/{name}/{Path(doc).name[:-len('.json')].replace('.', '_')}.json"


class TestPrereg(unittest.TestCase):
    def test_key_shape(self):
        k = predictions(KEY)
        self.assertEqual(k["tests"], ["tests_m4/test_i49_heldout.py"])
        self.assertEqual([p["id"] for p in k["predictions"]], [f"I49-P{i}" for i in range(1, 7)])
        self.assertEqual([p["id"] for p in k["regressions"]], [f"I49-R{i}" for i in range(1, 7)])
        self.assertEqual(k["thresholds"]["rule_catalog_version"], CATALOG)
        self.assertEqual(k["thresholds"]["base_commit"], BASE)
        self.assertEqual(load_json(H.PIN)["base_commit"], BASE)
        self.assertEqual(load_json(H.PIN)["rule_catalog_version"], CATALOG)

    def test_instruments_pinned(self):
        # Amended before the seal opened (spec/M4/amendments/I49.jsonl): rule V1 as first written refused a storage
        # name declared twice, which the development target's own document does (__gap); the amended protocol and
        # instrument are pinned here, every other pin is the key's.
        pins = dict(predictions(KEY)["thresholds"]["instrument_sha256"], **AMENDED_PINS)
        self.assertEqual(sorted(pins), sorted(INSTRUMENTS))
        for rel in INSTRUMENTS:
            with self.subTest(file=rel):
                self.assertEqual(H.sha256(ROOT / rel), pins[rel])

    def test_pin_is_the_base_tree(self):
        pin = load_json(H.PIN)
        files = sorted(x for x in H.git("ls-tree", "-r", "--name-only", BASE, "holon/").split("\n") if x)
        self.assertEqual(sorted(pin["files"]), files)
        for f in files:
            b = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{f}"], capture_output=True, check=True).stdout
            self.assertEqual(hashlib.sha256(b).hexdigest(), pin["files"][f], f)
        rules = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:holon/rules/__init__.py"], capture_output=True,
                               text=True, check=True).stdout
        import re
        versions = sorted({tuple(map(int, v.split("."))) for v in re.findall(r'"holon-rules/(\d+\.\d+)"', rules)})
        self.assertEqual(versions[-1], (1, 15), "the newest catalog at the base commit")
        self.assertIn('return GOX_CATALOG_VERSION if target_milestone(milestone)', rules)


class TestSeal(unittest.TestCase):
    """I49-R4 (H0)."""

    def test_prereg_commit_is_blind(self):
        c = H.prereg_commit()
        r = roles()
        files = H.changed(c)
        self.assertFalse([f for f in files if f.startswith("spec/heldout/")], files)
        self.assertFalse([f for f in files if f.startswith(("targets/", "gen/targets/", "gen/diagrams/", "results/targets/"))], files)
        needles = [r["commit"], r["commit"][:8], r["source"]]
        for f in files:
            try:
                text = H.git("show", f"{c}:{f}")
            except subprocess.CalledProcessError:
                continue   # deleted at c
            for n in needles:
                with self.subTest(file=f, needle=n[:12]):
                    self.assertNotIn(n, text)

    def test_seal_unchanged(self):
        c = H.prereg_commit()
        self.assertEqual(H.git("show", f"{c}:{H.SEAL}"), (ROOT / H.SEAL).read_text(encoding="utf-8"))
        self.assertEqual(H.git("show", f"{c}^:{H.SEAL}"), (ROOT / H.SEAL).read_text(encoding="utf-8"))

    def test_heldout_outputs_descend_from_prereg(self):
        c = H.prereg_commit()
        name, _ = H.heldout_target()
        prefixes = (f"targets/{name}/", f"gen/targets/{name}/", f"gen/diagrams/{name}/", f"results/targets/{name}/")
        commits = H.git("rev-list", "HEAD", "--", *prefixes).split()
        self.assertTrue(commits, "no commit adds the held-out target")
        for x in commits:
            with self.subTest(commit=x[:12]):
                r = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", c, x])
                self.assertEqual(r.returncode, 0, f"{x} changes the held-out target and does not descend from {c}")


class TestTarget(unittest.TestCase):
    """I49-P1 (H1)."""

    def test_target_file(self):
        r = roles()
        name, t = H.heldout_target()
        self.assertEqual(name, H.target_name(r["repo"]))
        self.assertEqual(validate(t, H.TARGET_SCHEMA), [])
        self.assertTrue(set(H.target_names(r)) <= set(t["names"]), t["names"])
        self.assertEqual(t["upstream"]["repo"], r["repo"])
        self.assertEqual(t["upstream"]["pinned_commit"], r["commit"])
        self.assertEqual(t["checkout"]["sealed_keys"], r["keys"])
        self.assertIs(t["checkout"].get("development"), False)

    def test_scope_sidecar(self):
        r = roles()
        name, _ = H.heldout_target()
        side = load_json(ROOT / "targets" / name / "extract_solidity.json")
        deps = config()["replay"].get("sol_deps")
        want = H.expected_sidecar(r, checkout(), Path(deps) if deps else None, solc_version(), name)
        self.assertEqual(H.sidecar_view(side), want)

    def test_checkout_at_the_sealed_commit(self):
        self.assertEqual(H.git("rev-parse", "HEAD", cwd=checkout()).strip(), roles()["commit"])


class TestExtraction(unittest.TestCase):
    """I49-P1 and I49-P6 (H2)."""

    def test_document(self):
        r = roles()
        name, t = H.heldout_target()
        rel = doc_rel(name)
        self.assertEqual(t["extract"]["documents"], {Path(rel).name: rel})
        d = load_json(ROOT / rel)
        self.assertEqual(validate(d, FACTS03_SCHEMA), [])
        self.assertEqual(d["facts_version"], "holon-facts/0.3")
        self.assertEqual(d["contract"], Path(r["source"]).stem)
        self.assertEqual(d["target"]["commit"], r["commit"])
        self.assertEqual(d["target"]["repo"], r["repo"])
        self.assertEqual(d["extraction"]["frontend"], "solidity")
        # Amended after the seal opened (spec/M4/amendments/I49.jsonl): the frontend records the sidecar as
        # {path, sha256}
        side = f"targets/{name}/extract_solidity.json"
        self.assertEqual(d["extraction"]["sidecar"], {"path": side, "sha256": H.sha256(ROOT / side)})
        self.assertGreaterEqual(len(d["actions"]), 1)

    def test_extraction_regenerates(self):
        name, _ = H.heldout_target()
        for _ in range(2):
            p = holon(["target", "extract", "--target", name, "--check"])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])

    def test_extraction_report(self):
        name, _ = H.heldout_target()
        rep = load_json(ROOT / "gen" / "targets" / name / "extraction.json")
        self.assertEqual(rep["document"], doc_rel(name))
        for item in rep["debt"]:
            self.assertEqual(sorted(item), ["detail", "kind", "unit"])
            self.assertEqual(item["kind"], "dependency_version")
            self.assertTrue(item["detail"].strip())


class TestCoverage(unittest.TestCase):
    """I49-P2 (H3)."""

    def test_coverage(self):
        name, _ = H.heldout_target()
        p = holon(["target", "coverage", "--target", name, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        rep = load_json(ROOT / "gen" / "targets" / name / "coverage.json")
        self.assertEqual(rep["unaccounted"], 0)
        self.assertEqual([d["document"] for d in rep["documents"]], [doc_rel(name)])
        for d in rep["documents"]:
            self.assertEqual(d["unaccounted"], [])
            self.assertGreaterEqual(d["statements"], d["extracted"])
            for item in d["debt"]:
                self.assertTrue(str(item.get("kind", "")).strip() and str(item.get("detail", "")).strip(), item)


class TestDiagram(unittest.TestCase):
    """I49-P3 and I49-P6 (H4)."""

    def check_diagram(self, doc: str, diagram: str):
        d = load_json(ROOT / diagram)
        self.assertEqual(validate(d, H.DIAGRAM_SCHEMA), [])
        self.assertEqual(d["facts"], doc)
        self.assertEqual(d["facts_sha256"], H.sha256(ROOT / doc))
        self.assertEqual(H.count_diagram(d), H.expected_counts(load_json(ROOT / doc)))

    def test_heldout_diagram(self):
        name, _ = H.heldout_target()
        self.check_diagram(doc_rel(name), diagram_rel(doc_rel(name), name))

    def test_morph_m3_diagram(self):
        self.check_diagram(MORPH_M3_DOC, MORPH_M3_DIAGRAM)

    def test_diagrams_regenerate(self):
        name, _ = H.heldout_target()
        for t in (name, "morph", "abacus"):
            with self.subTest(target=t):
                p = holon(["target", "diagram", "--target", t, "--check"])
                self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])


class TestSizes(unittest.TestCase):
    """I49-P5 and I49-P6 (H5)."""

    def test_sizes(self):
        rep = load_json(ROOT / H.SIZES)
        self.assertEqual(validate(rep, H.SIZES_SCHEMA), [])
        proto = {r["id"]: r for r in load_json(H.PROTOCOL)["sizes"]["rows"]}
        self.assertEqual([r["id"] for r in rep["rows"]], H.ROW_IDS)
        name, _ = H.heldout_target()
        for row in rep["rows"]:
            with self.subTest(row=row["id"]):
                want_doc = doc_rel(name) if row["id"] == "heldout" else proto[row["id"]]["document"]
                want_dia = diagram_rel(want_doc, name) if row["id"] == "heldout" else proto[row["id"]]["diagram"]
                self.assertEqual((row["document"], row["diagram"]), (want_doc, want_dia))
                self.assertEqual(row["document_sha256"], H.sha256(ROOT / row["document"]))
                self.assertEqual(row["diagram_sha256"], H.sha256(ROOT / row["diagram"]))
                counts = H.count_diagram(load_json(ROOT / row["diagram"]))
                self.assertEqual({k: row[k] for k in counts}, counts)
                if row["id"] in ("morph_m3", "heldout"):
                    self.assertEqual(counts, H.expected_counts(load_json(ROOT / row["document"])))
                ob = row["obligations"]
                if row["id"] == "heldout" and ob["pending"] is not None:
                    self.assertEqual(ob["pending"], "I50")
                    self.assertEqual([ob[k] for k in ("total", "by_rule", "by_rule_subform", "law_set_total")],
                                     [None] * 4)
                else:
                    self.assertIsNone(ob["pending"])
                    self.assertEqual({k: ob[k] for k in ("total", "by_rule", "by_rule_subform", "law_set_total")},
                                     H.obligations(ob["source"], row["document"]))
        self.assertEqual(rep["rows"][0]["obligations"]["source"], "targets/abacus/laws")
        self.assertEqual(rep["rows"][1]["obligations"]["source"], "laws/M2/DERIVATION.json")
        self.assertEqual(rep["rows"][2]["obligations"]["source"], "laws/M3/DERIVATION.json")

    def test_sizes_regenerate(self):
        for _ in range(2):
            p = holon(["target", "sizes", "--check"])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])


class TestGate(unittest.TestCase):
    """I49-P4 (H6)."""

    def gate(self, repo: Path, name: str) -> tuple[int, dict]:
        p = holon(["target", "gate", "--target", name], cwd=repo)
        rep = load_json(repo / "results" / "targets" / name / "gate_report.json")
        return p.returncode, rep

    def test_gate_passes(self):
        name, _ = H.heldout_target()
        repo = copy_repo()
        try:
            rc, rep = self.gate(repo, name)
            self.assertEqual(list(rep["checks"])[:len(I49_CHECKS)], I49_CHECKS)
            for c in I49_CHECKS:
                self.assertTrue(rep["checks"][c]["passed"], (c, rep["checks"][c]))
            self.assertTrue(rep["passed"], rep)
            self.assertEqual(rc, 0)
            committed = ROOT / "results" / "targets" / name / "gate_report.json"
            self.assertEqual(committed.read_bytes(), (repo / "results" / "targets" / name / "gate_report.json").read_bytes())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def tamper(self, how, failing: str):
        name, _ = H.heldout_target()
        repo = copy_repo()
        try:
            how(repo, name)
            rc, rep = self.gate(repo, name)
            self.assertNotEqual(rc, 0)
            self.assertFalse(rep["passed"])
            self.assertFalse(rep["checks"][failing]["passed"], rep["checks"][failing])
            return rep
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_bunfig_fails_genv_and_skips(self):
        rep = self.tamper(lambda repo, name: (repo / "bunfig.toml").write_text("preload = ['./x.ts']\n"), "GENV")
        for c in I49_CHECKS[1:]:
            self.assertFalse(rep["checks"][c]["passed"])
            self.assertIn("skipped", rep["checks"][c]["detail"])

    def test_edited_document_fails_x1(self):
        def how(repo, name):
            p = repo / doc_rel(name)
            d = json.loads(p.read_text())
            d["actions"] = d["actions"][1:]
            p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
        self.tamper(how, "X1")

    def test_hand_written_fact_fails_x2(self):
        def how(repo, name):
            src = repo / doc_rel(name)
            shutil.copyfile(src, src.parent / "hand.json")
        self.tamper(how, "X2")

    def test_edited_diagram_fails_d1(self):
        def how(repo, name):
            p = repo / diagram_rel(doc_rel(name), name)
            d = json.loads(p.read_text())
            d["edges"] = d["edges"][:-1]
            p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")
        self.tamper(how, "D1")


class TestRegressions(unittest.TestCase):
    def test_r1_generator_digests_unchanged(self):
        """I49-R1: at HEAD every generator_sha256 digest and the files they read are BASE's: no M0-M3 record moves."""
        base = _i47.export_tree(BASE, ["holon", "spec"])
        head = _i47.export_tree("HEAD", ["holon", "spec"])
        try:
            a, b = _i47.closures(base), _i47.closures(head)
            self.assertEqual(a["digests"], b["digests"])
            self.assertEqual(a["files"], b["files"])
        finally:
            shutil.rmtree(base, ignore_errors=True)
            shutil.rmtree(head, ignore_errors=True)

    def test_r2_outcomes_unchanged(self):
        """I49-R2: no non-merge first-parent commit from the I49 prereg on changes a committed M0-M3 outcome."""
        from tests_m4.test_i47_factory import OUTCOMES
        for c in H.first_parent_since(H.prereg_commit()):
            with self.subTest(commit=c[:12]):
                self.assertEqual([f for f in H.changed(c) if f.startswith(tuple(OUTCOMES))], [])

    def test_r3_target_agnostic(self):
        """I49-R3: no holon/ file names a declared target (the held-out target's names included), but I47's residue."""
        from tests_m4.test_i47_factory import PINNED_NAMES, RESIDUE
        names = set(PINNED_NAMES) | {n for ns in _i47.target_names(ROOT).values() for n in ns}
        name, t = H.heldout_target()
        self.assertTrue(set(t["names"]) <= names)
        hits = _i47.scan(ROOT, sorted(names))
        self.assertEqual(sorted(set(hits) - set(RESIDUE)), [], {k: hits[k] for k in sorted(set(hits) - set(RESIDUE))})
        heldout_names = set(t["names"])
        for f, ms in sorted(hits.items()):
            self.assertFalse({m.lower() for m in ms} & heldout_names, (f, ms))

    def test_r5_pin_changes_disclosed(self):
        """I49-R5: every holon/ file added, changed or removed since the catalog pin is disclosed."""
        ch = H.pin_changes()
        disc = {}
        for x in H.disclosures():
            self.assertEqual(sorted(x), ["affects", "path", "phase", "why"], x)
            self.assertIn(x["phase"], ("pre_seal", "post_seal"))
            self.assertTrue(x["why"].strip())
            self.assertIsInstance(x["affects"], list)
            disc.setdefault(x["path"], []).append(x)
        for kind in ("modified", "deleted", "added"):
            for f in ch[kind]:
                with self.subTest(kind=kind, path=f):
                    self.assertIn(f, disc, f"{f} ({kind} since the pin) is not disclosed")
        self.assertFalse([f for f in ch["modified"] + ch["deleted"] if f.startswith("holon/rules/")],
                         "the brief forbids editing holon/rules/ or the catalog")

    def test_r6_freeze_and_caveat(self):
        """I49-R6: the frozen files are unchanged, and the I49 report states the contamination caveat."""
        p = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        rep = (ROOT / "docs" / "iterations" / "I49.md").read_text(encoding="utf-8")
        label = load_json(H.PROTOCOL)["contamination"]["label"]
        self.assertIn("## Contamination caveat", rep)
        self.assertIn(label, rep)


if __name__ == "__main__":
    unittest.main()
