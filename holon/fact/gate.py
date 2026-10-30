"""The gate's checks of the FACT laws (BUILD_PLAN I26; the contract is the docstring of tests_m3/test_fact.py, "Gate"),
joined by holon.sorts.gate3 into its checks of the same name:

  G1    `holon fact` regenerates gen/<M>/fact/<model>.json, `holon derive` the FACT law files, the FACT section
        generator gen/<M>/fact/models/<model>.fact.bend, `holon fact --backtest` (in a copy) results/<M>/fact/
        backtest.json and gen/<M>/fact/backtest/, and the classification regenerated from the records is
        results/<M>/fact/classification.json, byte for byte; and (Q24: G1 on M3 is a full, independent rerun) the
        FACT laws are decided again from scratch in a copy of the tree, whose records (timings and I40's filter
        fields aside), replay report and generated law, proof and inhabitant files must be the committed ones, and
        every committed FACT record's generator_sha256 must be the FACT generators' digest now
  G5    every PROOF.bend of a decided FACT law (its proof or counter-law, and its inhabitant) re-checked by Bend; G7 the
        same files by BendTT (--verdict)
  G11   every FACT law has a record whose statement hash is the registry's and whose artifacts exist
  G11V  every PROVED FACT law carries a checked, reachable inhabitant of fhit_<x> (gen/<M>/<id>/nonvac/)
  G6    every REFUTED FACT law is a passed entry of replay/<M>/fact/report.json with the record's witness runs
  G9    every FACT record is valid under the v1 and v2 schemas

Nothing here names a target.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from .. import bend
from ..rules import fact as RF


CHECKS = ("G1", "G5", "G11", "G11V", "G6", "G9", "G7")   # the checks FACT joins (holon.sorts.gate3)


def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


class FactGate:
    def __init__(self, g3):
        self.g3 = g3
        self.m = g3.m
        self.root = g3.root
        self.gen = g3.gen
        self.results = g3.results
        self.checks: dict = {}
        self.na: dict = {}
        dv = json.loads((self.root / "laws" / self.m / "DERIVATION.json").read_text())
        self.entries = {e["law_id"]: e for e in dv["laws"] if e.get("rule") == RF.RULE and e.get("subform") in RF.SUBFORMS}

    def records(self) -> dict:
        out = {}
        for lid in sorted(self.entries):
            p = self.results / f"{lid}.json"
            out[lid] = json.loads(p.read_text()) if p.is_file() else None
        return out

    def proofs(self) -> list:
        out = []
        for lid, r in self.records().items():
            if not r or r.get("status") not in ("PROVED", "REFUTED"):
                continue
            if r["artifacts"].get("proof"):
                out.append((lid, "primary", self.root / r["artifacts"]["proof"]))
            nv = r.get("non_vacuity") or {}
            p = self.gen / lid / "nonvac" / "PROOF.bend"
            if r["status"] == "PROVED" and nv.get("status") == "inhabited" and p.is_file():
                out.append((lid, "nonvac", p))
        return out

    # ------------------------------------------------------------------ checks
    def g1(self):
        bad, notes = [], []
        tmp = Path(tempfile.mkdtemp(prefix="holon-gate3-fact-"))
        try:
            p = self.g3.holon(["fact", "--milestone", self.m, "--root", self.root, "--out", tmp / "f"], self.root)
            if p.returncode != 0:
                bad.append(f"holon fact failed: {(p.stdout + p.stderr)[-300:]}")
            else:
                for q in sorted((self.gen / "fact").glob("*.json")):
                    r = tmp / "f" / q.name
                    if not r.is_file() or r.read_bytes() != q.read_bytes():
                        bad.append(f"gen/{self.m}/fact/{q.name} differs from its regeneration")
                notes.append("fact")
            p = self.g3.holon(["derive", "--milestone", self.m, "--root", self.root, "--out", tmp / "l",
                               "--obstructions", tmp / "obs.json"], self.root)
            if p.returncode != 0:
                bad.append(f"holon derive failed: {(p.stdout + p.stderr)[-300:]}")
            else:
                ldir = self.root / "laws" / self.m
                for lid in sorted(self.entries):
                    a, b = ldir / f"{lid}.json", tmp / "l" / f"{lid}.json"
                    if not b.is_file() or a.read_bytes() != b.read_bytes():
                        bad.append(f"laws/{self.m}/{lid}.json differs from its derivation")
                notes.append(f"derive ({len(self.entries)} FACT laws)")
            bad += self.section_problems()
            notes.append("the FACT section")
            c = RF.dumps(RF.classification(self.m, self.root))
            cp = self.results / "fact" / "classification.json"
            if not cp.is_file() or cp.read_text() != c:
                bad.append(f"results/{self.m}/fact/classification.json differs from its regeneration")
            notes.append("classification")
            bad += self.backtest_problems(tmp)
            notes.append("back-test")
            bad += self.rerun_problems(tmp)
            notes.append(f"the {len(self.entries)} FACT laws decided again")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.checks["G1"] = _res(not bad, f"FACT regenerated byte-identical: {', '.join(notes)}" if not bad
                                 else f"FACT differs: {bad[:6]}")

    def section_problems(self) -> list:
        """The FACT section of every document the FACT laws read, generated again (holon.fact.section)."""
        from ..sorts import model3 as M3
        from ..sorts.evaluate3 import hashes_of
        from ..sorts.proofs3 import rel_import
        from . import section as S
        bad = []
        sc = RF.load_sidecar(self.m, self.root)
        for doc_rel in sorted({e["facts"] for e in self.entries.values()}):
            try:
                doc = json.loads((self.root / doc_rel).read_text())
                an = RF.analyse(doc, RF.model_of(doc_rel), sc.doc)
                init = M3.init_of(self.m, self.root, None, doc_rel)
                text, mm = M3.generate(self.m, self.root, doc_rel, typed=True, sidecar=None, init=init)
                d = self.gen / "fact" / "models"
                name = M3.model_name(doc_rel) + ".fact"
                target = self.gen / "sorts" / "models" / M3.importable(M3.model_name(doc_rel))
                mt = S.module_text(mm, text, doc, hashes_of(text), RF.elements(an), sc.doc.get("hypotheses") or {},
                                   rel_import(d, target))
            except Exception as e:  # noqa: BLE001
                bad.append(f"the FACT section of {doc_rel} cannot be generated: {type(e).__name__}: {e}")
                continue
            path = d / M3.importable(name)
            if not path.is_file() or path.read_text(encoding="utf-8") != mt:
                bad.append(f"{path.relative_to(self.root)} differs from its generation")
        return bad

    FILTER_FIELDS = ("concretization", "filter_bin")   # written after the run by I40's filter stage

    def rerun_problems(self, tmp: Path) -> list:
        """The FACT laws decided again, from scratch (no checkpoint), in a copy of the tree whose FACT records, replay
        report and generated FACT law files are removed first; and every committed record's generator_sha256 against the
        FACT generators' digest now (a record made by older generator code is stale even where it still reruns)."""
        from ..sorts.gate3 import norm_record
        from . import run as FR
        bad = []
        dig = FR.generator_sha256(self.root)
        for lid, r in sorted(self.records().items()):
            if r is not None and r.get("generator_sha256") != dig:
                bad.append(f"{lid}: its generator_sha256 is not the FACT generators' digest now (the record is stale)")
        repo = tmp / "repo"
        shutil.copytree(self.root, repo, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "build", "__pycache__", "node_modules"))
        rep = Path("replay") / self.m / "fact" / "report.json"
        (repo / rep).unlink(missing_ok=True)
        for lid in sorted(self.entries):
            (repo / "results" / self.m / f"{lid}.json").unlink(missing_ok=True)
            for d in self.law_dirs(repo / "gen" / self.m, lid):
                shutil.rmtree(d, ignore_errors=True)
        p = self.g3.holon(["run", "--milestone", self.m, "--laws", ",".join(sorted(self.entries))], repo,
                          timeout=4 * 3600)
        if p.returncode != 0:
            return bad + [f"holon run (the FACT laws, again) failed: {(p.stdout + p.stderr)[-400:]}"]

        def norm(path: Path, root: Path) -> dict | None:
            if not path.is_file():
                return None
            r = norm_record(json.loads(path.read_text()), root, root / "gen" / self.m)
            return {k: v for k, v in r.items() if k not in self.FILTER_FIELDS}
        for lid in sorted(self.entries):
            if norm(self.results / f"{lid}.json", self.root) != norm(repo / "results" / self.m / f"{lid}.json", repo):
                bad.append(f"record {lid} differs from its rerun")
            for a_dir, b_dir in zip(self.law_dirs(self.gen, lid), self.law_dirs(repo / "gen" / self.m, lid)):
                a_files = {q.relative_to(a_dir) for q in a_dir.rglob("*") if q.is_file()} if a_dir.is_dir() else set()
                b_files = {q.relative_to(b_dir) for q in b_dir.rglob("*") if q.is_file()} if b_dir.is_dir() else set()
                for rel in sorted(a_files | b_files):
                    if rel not in a_files or rel not in b_files or \
                            (a_dir / rel).read_bytes() != (b_dir / rel).read_bytes():
                        bad.append(f"gen/{self.m}/{a_dir.relative_to(self.gen) / rel} differs from its rerun")
        a, b = self.root / rep, repo / rep
        if a.is_file() != b.is_file() or (a.is_file() and a.read_bytes() != b.read_bytes()):
            bad.append(f"{rep} differs from its rerun")
        return bad

    @staticmethod
    def law_dirs(gen: Path, lid: str) -> list:
        """The directories a FACT law's run writes under gen/<M>: its law file, its proofs or counter-law, and its
        inhabitant."""
        return [gen / "laws" / lid, gen / "proofs" / lid, gen / lid]

    def backtest_problems(self, tmp: Path) -> list:
        """`holon fact --backtest` in a copy of the inputs it reads reproduces the back-test table and its files."""
        if not (self.results / "fact" / "backtest.json").is_file():
            return [] if RF.load_sidecar(self.m, self.root).backtest is None else \
                [f"results/{self.m}/fact/backtest.json is missing"]
        repo = tmp / "repo"
        shutil.copytree(self.root, repo, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", "build", "__pycache__", "node_modules", ".claude"))
        shutil.rmtree(repo / "gen" / self.m / "fact" / "backtest", ignore_errors=True)
        (repo / "results" / self.m / "fact" / "backtest.json").unlink(missing_ok=True)
        p = self.g3.holon(["fact", "--milestone", self.m, "--root", repo, "--out", tmp / "f2", "--backtest"], repo)
        if p.returncode != 0:
            return [f"holon fact --backtest failed: {(p.stdout + p.stderr)[-300:]}"]
        bad = []
        a, b = self.results / "fact" / "backtest.json", repo / "results" / self.m / "fact" / "backtest.json"
        if not b.is_file() or a.read_bytes() != b.read_bytes():
            bad.append(f"results/{self.m}/fact/backtest.json differs from its regeneration")
        mine = self.gen / "fact" / "backtest"
        theirs = repo / "gen" / self.m / "fact" / "backtest"
        fa = {q.relative_to(mine).as_posix(): q.read_bytes() for q in sorted(mine.rglob("*")) if q.is_file()}
        fb = {q.relative_to(theirs).as_posix(): q.read_bytes() for q in sorted(theirs.rglob("*")) if q.is_file()} \
            if theirs.is_dir() else {}
        bad += [f"gen/{self.m}/fact/backtest/{k} differs from its regeneration"
                for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)]
        return bad

    def g5(self):
        bad, n, slow = [], 0, 0.0
        for lid, label, proof in self.proofs():
            n += 1
            t = time.time()
            r = bend.check(proof)
            slow = max(slow, time.time() - t)
            if not r.ok:
                bad.append(f"{lid} {label}: {r.first_line}")
        if n == 0:
            self.na["G5"] = "no FACT law is decided"
            return
        self.checks["G5"] = _res(not bad, f"{n} FACT proof files re-checked by Bend (slowest {round(slow, 1)} s)"
                                 if not bad else "; ".join(bad[:8]))

    def g7(self):
        bad, n = [], 0
        for lid, label, proof in self.proofs():
            n += 1
            r = bend.check_verdict(proof)
            if not r.ok:
                bad.append(f"{lid} {label}: BendTT {r.first_line}")
        if n == 0:
            self.na["G7"] = "no FACT law is decided"
            return
        self.checks["G7"] = _res(not bad, f"{n} FACT proof files re-checked by BendTT (--verdict)" if not bad
                                 else "; ".join(bad[:8]))

    def g11(self):
        bad = []
        for lid, r in self.records().items():
            if r is None:
                bad.append(f"{lid}: no record")
                continue
            if r.get("statement_hash") != self.g3.registry["statements"].get(lid):
                bad.append(f"{lid}: statement hash differs from the registry")
            for k in ("laws", "model", "typed_model"):
                if not r["artifacts"].get(k) or not (self.root / r["artifacts"][k]).exists():
                    bad.append(f"{lid}: artifact {k} missing")
            if r.get("status") in ("PROVED", "REFUTED") and not (self.root / str(r["artifacts"].get("proof"))).is_file():
                bad.append(f"{lid}: artifact proof missing")
        self.checks["G11"] = _res(not bad, f"{len(self.entries)} FACT records match the registry and name existing "
                                           "artifacts" if not bad else "; ".join(bad[:8]))

    def g11v(self):
        bad, n = [], 0
        for lid, r in self.records().items():
            if not r or r.get("status") != "PROVED":
                continue
            n += 1
            nv = r.get("non_vacuity") or {}
            p = self.gen / lid / "nonvac" / "PROOF.bend"
            if nv.get("status") != "inhabited" or nv.get("reachable") is not True or not p.is_file():
                bad.append(f"{lid}: non-vacuity {nv.get('status')}")
                continue
            if f"F.fhit_{RF.ghost_x(lid)}(" not in (self.gen / lid / "nonvac" / "LAWS.bend").read_text():
                bad.append(f"{lid}: its inhabitant does not state fhit_{RF.ghost_x(lid)}")
                continue
            if not bend.check(p).ok:
                bad.append(f"{lid}: its inhabitant does not check")
        if n == 0:
            self.na["G11V"] = "no FACT law is PROVED"
            return
        self.checks["G11V"] = _res(not bad, f"{n} PROVED FACT laws carry a checked reachable inhabitant" if not bad
                                   else "; ".join(bad[:8]))

    def g6(self):
        want = {lid: r for lid, r in self.records().items() if r and r.get("status") == "REFUTED"}
        if not RF.load_sidecar(self.m, self.root).doc.get("binding"):
            self.na["G6"] = "the FACT sidecar names no binding: no real side to replay on"
            return
        rp = self.root / "replay" / self.m / "fact" / "report.json"
        rep = json.loads(rp.read_text()) if rp.is_file() else {"laws": {}}
        bad = []
        for lid, r in sorted(want.items()):
            x = (rep.get("laws") or {}).get(lid)
            w = r.get("witness") or {}
            if x is None:
                bad.append(f"{lid}: not replayed")
            elif x.get("status") != "passed" or not x.get("calls_agree"):
                bad.append(f"{lid}: replay {x.get('status')}")
            elif "runs" in w and [y.get("trace") for y in x.get("runs") or []] != \
                    [list(q["prefix"]) + [q["x"]] for q in w["runs"]]:
                bad.append(f"{lid}: the replayed runs are not the record's witness")
            elif "runs" not in w and x.get("trace") != list(w.get("prefix") or []) + [w.get("y")] + list(w.get("t") or []):
                bad.append(f"{lid}: the replayed trace is not the record's witness")
            elif (r.get("replay") or {}).get("status") != "passed":
                bad.append(f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}")
        self.checks["G6"] = _res(not bad, f"{len(want)} REFUTED FACT laws replayed and passed on the real contract"
                                 if not bad else "; ".join(bad[:8]))

    def g9(self):
        from .. import schema as S
        bad = []
        v1 = json.loads((self.root / "schemas" / "result_record.schema.json").read_text())
        v2 = json.loads((self.root / "spec" / "schemas" / "result_record_v2.schema.json").read_text())
        for lid, r in self.records().items():
            if r is None:
                continue
            for name, sch in (("v1", v1), ("v2", v2)):
                errs = S.errors(r, sch)
                if errs:
                    bad.append(f"{lid}: {name} {errs[:2]}")
        self.checks["G9"] = _res(not bad, f"{len(self.entries)} FACT records valid under v1 and v2" if not bad
                                 else "; ".join(bad[:6]))

    def run(self, only: list | None) -> None:
        for k in CHECKS:
            if only and k not in only:
                continue
            try:
                getattr(self, k.lower())()
            except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                self.checks[k] = _res(False, f"error: {type(e).__name__}: {e}")


def join(g3, only: list | None) -> None:
    """Run the FACT checks and join each with gate3's check of the same name (or add it)."""
    fg = FactGate(g3)
    if not fg.entries:
        return
    fg.run(only)
    for k, r in fg.checks.items():
        if k in g3.checks:
            a = g3.checks[k]
            g3.checks[k] = _res(a["passed"] and r["passed"], f"{a['detail']}; FACT laws: {r['detail']}")
        else:
            why = g3.na.pop(k, None)
            g3.checks[k] = _res(r["passed"], f"FACT laws: {r['detail']}"
                                + (f"; I30 laws: not applicable ({why})" if why else ""))
    for k, why in fg.na.items():
        if k not in g3.checks:
            g3.na[k] = f"{g3.na[k]}; FACT laws: {why}" if k in g3.na else f"FACT laws: {why}"
