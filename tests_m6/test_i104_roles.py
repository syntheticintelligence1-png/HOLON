"""I104 (M6, generality): role inference. The contract of `python -m holon roles` (holon.roles):

  python -m holon roles --milestone M --root R --documents P[,P...] --out-dir D
                        [--mode static|static+ai] [--proposed PATH] [--install] [--roles hand|auto]

R1  It reads only the extracted documents P (paths relative to R) and, in mode static+ai, the proposal file, and
    writes into D: roles.json (the manifest, holon-roles/0.1) and every role sidecar it has a role for, in the
    readers' own formats: go_laws.json (holon.gox.basis), link.json (holon.frontends.link), go_ops.json
    (holon.diagram.goops), and the typed sidecars sort_types.json, disch.json, undo.json and fact.json over the
    transitions documents among P. Canonical JSON, byte-identical across runs.
R2  Every role in the manifest carries roles_source ("static" or "ai_proposal") and evidence {"rule", "facts"}, each
    fact a path among the inputs; the manifest lists every input with its sha256 and, in mode static+ai, the proposal
    with its sha256 and proposer "agent".
R3  Static inference never rests on a name alone: renaming every name that the static evidence rests on leaves the
    inferred roles the same up to those names. Two facts whose names agree and whose values differ get no link role.
R4  The proposal channel: in mode static the proposal is not read. In mode static+ai a proposed role is merged unless
    it conflicts with a static role (the same id, or a fact that already plays a static role); then static wins and
    the proposal is listed under "dropped". A proposal whose proposer is not "agent", or that holds a key "model"
    anywhere, is refused (exit 2, nothing written).
R5  --install writes each sidecar into R/spec/<M>/lib/ only where none exists (a hand sidecar wins); with --roles auto
    it replaces them (meant for a scratch root). Nothing under spec/ is touched without --install.
R6  holon/roles/ names no target.

Predictions are checked against the outcome files under results/M6/I104/ (the measured run).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m6 import _i104 as H

ROOT = H.ROOT
OUT = H.OUT
PRED = json.loads((ROOT / "spec" / "M6" / "predictions" / "I104.json").read_text())
TH = PRED["thresholds"]
SOURCES = {"static", "ai_proposal"}


def holon(*args, cwd=ROOT):
    env = dict(os.environ, BEND_NO_TELEMETRY="1")
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, capture_output=True, text=True, env=env,
                          timeout=1800)


def run_roles(out: Path, *extra, root=ROOT, docs=None):
    return holon("roles", "--milestone", "M3", "--root", str(root), "--documents",
                 ",".join(docs or TH["morph_documents"]), "--out-dir", str(out), *extra)


def tree_bytes(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


class TestBuild(unittest.TestCase):
    def test_b1_cli_exists(self):
        r = holon("roles", "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for flag in ("--documents", "--out-dir", "--mode", "--proposed", "--install", "--roles"):
            self.assertIn(flag, r.stdout)

    def test_b2_deterministic_and_recorded(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra, rb = run_roles(Path(a)), run_roles(Path(b))
            self.assertEqual(ra.returncode, 0, ra.stderr)
            self.assertEqual(rb.returncode, 0, rb.stderr)
            ta, tb = tree_bytes(Path(a)), tree_bytes(Path(b))
            self.assertEqual(ta, tb)
            self.assertIn("roles.json", ta)
            self.assertEqual(ta, tree_bytes(OUT / "morph"), "results/M6/I104/morph/ is not what holon roles writes")

    def test_b3_every_role_has_source_and_evidence(self):
        man = H.load(OUT / "morph" / "roles.json")
        self.assertEqual(man["roles_version"], "holon-roles/0.1")
        inputs = {i["path"]: i["sha256"] for i in man["inputs"]}
        for p in TH["morph_documents"]:
            self.assertEqual(inputs.get(p), hashlib.sha256((ROOT / p).read_bytes()).hexdigest(), p)
        self.assertTrue(man["roles"])
        for r in man["roles"]:
            self.assertIn(r["roles_source"], SOURCES, r)
            ev = r["evidence"]
            self.assertTrue(isinstance(ev.get("rule"), str) and ev["rule"], r)
            self.assertTrue(ev.get("facts"), r)
            for f in ev["facts"]:
                self.assertIn(f.split("#", 1)[0], inputs, r)

    def _renamed(self, tmp: Path) -> tuple[list, dict]:
        """Morph's documents with every Solidity constant and Go global renamed by a fixed map."""
        ren: dict = {}

        def nm(s):
            if s not in ren:
                ren[s] = f"zz{len(ren):04d}"
            return ren[s]

        docs = []
        for p in TH["morph_documents"]:
            d = json.loads((ROOT / p).read_text())
            if isinstance(d.get("constants"), dict):
                d["constants"] = {nm(k): v for k, v in d["constants"].items()}
            for g in (d.get("go") or {}).get("globals") or []:
                if isinstance(g.get("global"), str):
                    pkg, _, base = g["global"].rpartition(".")
                    g["global"] = f"{pkg}.{nm(base)}"
            q = tmp / p
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(json.dumps(d, sort_keys=True))
            docs.append(p)
        return docs, ren

    def test_b4_names_are_tie_breakers_only(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            docs, ren = self._renamed(tmp / "root")
            r0 = run_roles(tmp / "a")
            r1 = run_roles(tmp / "b", root=tmp / "root", docs=docs)
            self.assertEqual(r0.returncode, 0, r0.stderr)
            self.assertEqual(r1.returncode, 0, r1.stderr)

            def norm(items):
                out = set()
                for it in items:
                    out.add(tuple(ren.get(x, x) if isinstance(x, str) else x for x in it))
                return out
            a = {i for i in norm(H.auto_items(tmp / "a")) if i[0] == "link"}
            b = {i for i in H.auto_items(tmp / "b") if i[0] == "link"}
            self.assertEqual(a, b)

    def test_b4b_equal_names_unequal_values_no_link(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            sol = {"facts_version": "holon-facts/0.2", "contract": "C", "constants": {"SAME_NAME": "0x" + "11" * 32},
                   "actions": [], "storage": []}
            go = {"facts_version": "holon-facts/0.3", "go": {"functions": {}, "globals": [
                {"global": "ex/p.SAME_NAME", "package": "ex/p", "type": "[32]byte", "span": "p.go:1",
                 "cells": [["const", 0x22]] * 32, "value": None}], "codecs": {}}}
            (tmp / "r").mkdir()
            (tmp / "r" / "s.extracted.json").write_text(json.dumps(sol))
            (tmp / "r" / "g.go.extracted.json").write_text(json.dumps(go))
            r = run_roles(tmp / "o", root=tmp / "r", docs=["s.extracted.json", "g.go.extracted.json"])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual({i for i in H.auto_items(tmp / "o") if i[0] == "link"}, set())

    def _proposal(self, **kw) -> dict:
        p = {"roles_proposed_version": "holon-roles-proposed/0.1", "proposer": "agent",
             "doc": "planted (tests_m6/test_i104_roles.py)", "link": {}, "go_ops": {}, "recompute": {}}
        p.update(kw)
        return p

    def test_b5_proposals_merge_static_wins(self):
        man = H.load(OUT / "morph" / "roles.json")
        static_link = next(r for r in man["roles"] if r["sidecar"] == "link")
        go_doc = next(p for p in TH["morph_documents"] if p.endswith(".go.extracted.json"))
        prop = self._proposal(
            link={static_link["id"]: {"solidity": {"document": TH["morph_documents"][0], "constant": "X"},
                                      "go": {"document": go_doc, "global": "Y"}}},
            go_ops={"planted_ops": {"document": go_doc, "carrier": "*planted.T"}})
        with tempfile.TemporaryDirectory() as t:
            pp = Path(t) / "roles_proposed.json"
            pp.write_text(json.dumps(prop))
            r = run_roles(Path(t) / "o", "--mode", "static+ai", "--proposed", str(pp))
            self.assertEqual(r.returncode, 0, r.stderr)
            m = H.load(Path(t) / "o" / "roles.json")
            self.assertEqual(m["proposed"]["sha256"], hashlib.sha256(pp.read_bytes()).hexdigest())
            self.assertEqual(m["proposed"]["proposer"], "agent")
            by = {(r["sidecar"], r["id"]): r for r in m["roles"]}
            self.assertEqual(by[("link", static_link["id"])]["roles_source"], "static")
            self.assertEqual(by[("go_ops", "planted_ops")]["roles_source"], "ai_proposal")
            self.assertIn(("link", static_link["id"]), {(d["sidecar"], d["id"]) for d in m["dropped"]})
            r2 = run_roles(Path(t) / "s", "--proposed", str(pp))
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertNotIn("ai_proposal", {r["roles_source"] for r in H.load(Path(t) / "s" / "roles.json")["roles"]})

    def test_b6_proposal_provenance_is_model_free(self):
        for bad in (self._proposal(proposer="someone"), self._proposal(model="x"),
                    self._proposal(go_ops={"a": {"document": "d", "carrier": "T", "model": "x"}})):
            with tempfile.TemporaryDirectory() as t:
                pp = Path(t) / "p.json"
                pp.write_text(json.dumps(bad))
                r = run_roles(Path(t) / "o", "--mode", "static+ai", "--proposed", str(pp))
                self.assertEqual(r.returncode, 2, (bad, r.stdout, r.stderr))
                self.assertFalse((Path(t) / "o" / "roles.json").exists())

    def test_b7_install_hand_wins(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "root"
            for p in TH["morph_documents"]:
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / p, root / p)
            lib = root / "spec" / "M3" / "lib"
            lib.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / "spec" / "M3" / "lib" / "go_ops.json", lib / "go_ops.json")
            before = (lib / "go_ops.json").read_bytes()
            r = run_roles(Path(t) / "o", "--install", root=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((lib / "go_ops.json").read_bytes(), before)
            self.assertTrue((lib / "link.json").is_file())
            r = run_roles(Path(t) / "o2", "--install", "--roles", "auto", root=root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((lib / "go_ops.json").read_bytes(), (Path(t) / "o2" / "go_ops.json").read_bytes())

    def test_b8_no_target_names(self):
        pat = re.compile(r"morph|scroll|optimism|arbitrum|cosmos|wormhole", re.I)
        for p in sorted((ROOT / "holon" / "roles").rglob("*.py")):
            self.assertIsNone(pat.search(p.read_text()), p)

    def test_b9_hand_sidecars_unchanged(self):
        for rel, sha in TH["hand_sidecars_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), sha, rel)

    def test_b10_m0_m3_outputs_restamp_only(self):
        base = TH["base"]
        paths = ["laws/M0", "laws/M1", "laws/M2", "laws/M3", "results/M0", "results/M1", "results/M2", "results/M3",
                 "gen/M0", "gen/M1", "gen/M2", "gen/M3"]
        r = subprocess.run(["git", "diff", "--name-only", base, "HEAD", "--", *paths], cwd=ROOT, capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in r.stdout.split():
            old = subprocess.run(["git", "show", f"{base}:{f}"], cwd=ROOT, capture_output=True).stdout
            new = (ROOT / f).read_bytes() if (ROOT / f).is_file() else b""
            try:
                self.assertEqual(H.strip_stamp(json.loads(old)), H.strip_stamp(json.loads(new)), f)
            except ValueError:
                self.fail(f"{f}: a non-JSON M0-M3 output changed")


class TestPredictions(unittest.TestCase):
    def test_p1_morph_role_precision_recall(self):
        rec = H.load(OUT / "morph_roles.json")
        hand, auto = H.hand_items(), H.auto_items(OUT / "morph")
        m = hand & auto
        self.assertEqual(rec["precision"], [len(m), len(auto)])
        self.assertEqual(rec["recall"], [len(m), len(hand)])
        self.assertEqual(len(hand), TH["hand_items"])
        self.assertGreaterEqual(len(m) / len(hand), TH["recall_min"])
        self.assertGreaterEqual(len(m) / max(len(auto), 1), TH["precision_min"])

    def test_p2_m3_rederived(self):
        rec = H.load(OUT / "morph_auto.json")
        s = rec["summary"]
        rows = rec["laws"]
        dep = [r for r in rows if r["role_dependent"] and r["hand_status"] in ("PROVED", "REFUTED")]
        same = [r for r in dep if r["auto_status"] == r["hand_status"] and r["statement_same"]]
        self.assertEqual(s["role_dependent_decided"], len(dep))
        self.assertEqual(s["role_dependent_rederived"], len(same))
        self.assertGreaterEqual(len(same) / max(len(dep), 1), TH["rederived_min"])
        other = [r for r in rows if not r["role_dependent"] and r["hand_status"] in ("PROVED", "REFUTED")]
        self.assertTrue(all(r["law_same"] for r in other), [r["law_id"] for r in other if not r["law_same"]][:10])
        for r in rows:
            if r["auto_status"] is not None and r["role_dependent"]:
                self.assertIn(r["roles_source"], SOURCES, r)

    def test_p3_planted_wrong_roles_are_never_findings(self):
        rec = H.load(OUT / "planted.json")
        kinds = {c["kind"] for c in rec["cases"]}
        self.assertTrue(set(TH["planted_kinds"]) <= kinds, kinds)
        self.assertEqual(rec["findings"], 0)
        for c in rec["cases"]:
            for law in c["laws"]:
                self.assertIn(law["status"], ("PROVED", "REFUTED", "UNKNOWN"), law)
                if law["status"] == "REFUTED":
                    self.assertNotEqual(law["replay"], "confirmed", law)
                    self.assertIn(law["class"], ("role_defect", "model_defect"), law)
                self.assertNotEqual(law["class"], "finding", law)
                self.assertEqual(law["roles_source"], "ai_proposal", law)

    def test_p4_corpus_smoke(self):
        rec = H.load(OUT / "corpus_smoke.json")
        ids = [e["id"] for e in rec["entries"]]
        self.assertEqual(ids, TH["corpus_entries"])
        self.assertEqual(rec["with_role"], sum(1 for e in rec["entries"] if e["roles"] > 0))
        self.assertEqual(rec["with_law"], sum(1 for e in rec["entries"] if e["laws"] > 0))
        self.assertGreaterEqual(rec["with_role"], TH["smoke_with_role_min"])
        self.assertGreaterEqual(rec["with_law"], TH["smoke_with_law_min"])


if __name__ == "__main__":
    unittest.main()
