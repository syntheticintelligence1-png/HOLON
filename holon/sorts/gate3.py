"""`holon gate` for a typed milestone (M3 and later; I30; the contract is the docstring of tests_m3/test_sort_types.py,
"Gate"): every check re-decided from scratch over the I30 laws, with the checks that have no meaning for the milestone
listed under not_applicable with a reason.

  GENV  the pinned checker (holon.gate.Gate.genv, unchanged)
  G2    the registry: `holon derive` reproduces laws/<M> byte for byte and every law's statement hash is the
        registry's; each law file states its law's coerce term
  G1    regeneration: `holon sorts`, `holon types`, `holon derive`, `holon model` and `holon termsize` reproduce
        gen/<M>/sorts (with the typed and untyped models), laws/<M> and the term-size report byte for byte, and
        `holon run` reproduces every I30 record and generated Bend file
  G3    no `law` under gen/<M>/proofs, no escape hatch in any generated Bend file, every law file imports exactly the
        typed model as M
  G5    every PROOF.bend of a decided law (primary and per entry point) re-checked by Bend, importing its law
  G11   every record's statement hash is the registry's and its artifacts exist
  G11V  every PROVED law carries a checked, reachable inhabitant of its at-site premise (gen/<M>/<id>/nonvac/)
  G6    every REFUTED entry point is a passed entry of replay/<M>/sorts/report.json, with the record's trace
  G9    every record is valid under the v1 and v2 schemas
  G7    BendTT (--verdict) re-checks every decided law's proofs
  G4    canaries: per I30 subform among the laws, a counter-law whose witness is mutated (its entry step's clock or
        its first argument changed) must be rejected by Bend
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .. import bend

ROOT = Path(__file__).resolve().parents[2]
SUBFORMS = ("as_member", "realize", "reinterpret")
ESCAPES = (re.compile(r"\?[A-Za-z_]"), re.compile(r"@unsafe"), re.compile(r"(?m)^\s*def\s+[\w.]+\?"),
           re.compile(r"(?m)^\s*import\s+\""))


def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


def _strip(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text)


class Gate3:
    def __init__(self, milestone: str, root: Path):
        self.m = milestone
        self.root = Path(root).resolve()
        self.checks: dict = {}
        self.canaries: list = []
        self.na: dict = {}
        self.gen = self.root / "gen" / milestone
        self.results = self.root / "results" / milestone
        dv = json.loads((self.root / "laws" / milestone / "DERIVATION.json").read_text())
        self.entries = {e["law_id"]: e for e in dv["laws"] if e.get("rule") == "SORT" and e.get("subform") in SUBFORMS}
        self.registry = json.loads((self.root / "laws" / milestone / "REGISTRY.json").read_text())

    def holon(self, args: list, cwd: Path, timeout: int = 7200):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run([sys.executable, "-m", "holon"] + [str(a) for a in args], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=timeout)

    def records(self) -> dict:
        out = {}
        for lid in sorted(self.entries):
            p = self.results / f"{lid}.json"
            out[lid] = json.loads(p.read_text()) if p.is_file() else None
        return out

    def proofs(self) -> list:
        """(law id, label, PROOF.bend, LAWS.bend) of every proof file a decided record names."""
        out = []
        for lid, r in self.records().items():
            if not r or r.get("status") not in ("PROVED", "REFUTED"):
                continue
            laws = self.root / r["artifacts"]["laws"]
            if r["artifacts"].get("proof"):
                out.append((lid, "primary", self.root / r["artifacts"]["proof"], laws))
            for e, w in sorted((r.get("witnesses") or {}).items()):
                if w.get("status") == "REFUTED":
                    out.append((lid, f"entry {e}", self.root / w["proof"], self.root / w["laws"]))
            nv = r.get("non_vacuity") or {}
            if r["status"] == "PROVED" and nv.get("law"):
                out.append((lid, "nonvac", self.gen / lid / "nonvac" / "PROOF.bend", self.root / nv["law"]))
        return out

    # ---------------------------------------------------------- checks
    def g2(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-gate3-g2-"))
        try:
            p = self.holon(["derive", "--milestone", self.m, "--root", self.root, "--out", tmp / "laws",
                            "--obstructions", tmp / "obs.json"], self.root)
            if p.returncode != 0:
                self.checks["G2"] = _res(False, f"derive failed: {(p.stdout + p.stderr)[-600:]}")
                return
            ldir = self.root / "laws" / self.m
            a = {q.name: q.read_bytes() for q in sorted((tmp / "laws").iterdir())}
            b = {q.name: q.read_bytes() for q in sorted(ldir.iterdir()) if q.is_file()}
            diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            bad = list(diff)
            for lid in self.entries:
                lf = self.gen / "laws" / lid / "LAWS.bend"
                if lf.is_file() and f"M.coerce_{lid[len('L_sort_'):]}(" not in _strip(lf.read_text()):
                    bad.append(f"{lid}: LAWS.bend does not state coerce_{lid[len('L_sort_'):]}")
            self.checks["G2"] = _res(not bad, f"derive reproduces laws/{self.m} ({len(b)} files); {len(self.entries)} "
                                              "I30 law files state their coerce term" if not bad else f"differs: {bad[:8]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def g1(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-gate3-g1-"))
        try:
            repo = tmp / "repo"
            shutil.copytree(self.root, repo, symlinks=True,
                            ignore=shutil.ignore_patterns(".git", "build", "__pycache__", "node_modules"))
            notes, bad = [], []
            sorts = self.gen / "sorts"
            steps = [(["sorts", "--milestone", self.m, "--root", repo, "--out", tmp / "s"],
                      [("constraints.json", sorts), ("assignment.json", sorts), ("conflicts.json", sorts),
                       ("unions.json", sorts), ("unresolved.json", sorts)], tmp / "s"),
                     (["types", "--milestone", self.m, "--root", repo, "--out", tmp / "t"],
                      [("types.json", sorts), ("taint.json", sorts)], tmp / "t"),
                     (["derive", "--milestone", self.m, "--root", repo, "--out", tmp / "l", "--obstructions",
                       tmp / "obs" / "obstructions.json"], [("obstructions.json", sorts)], tmp / "obs"),
                     (["model", "--milestone", self.m, "--root", repo, "--out", tmp / "m"],
                      [(q.name, sorts / "models") for q in sorted((sorts / "models").iterdir())], tmp / "m")]
            for args, files, where in steps:
                p = self.holon(args, repo)
                if p.returncode != 0:
                    bad.append(f"holon {args[0]} failed: {(p.stdout + p.stderr)[-400:]}")
                    continue
                for name, d in files:
                    if (where / name).read_bytes() != (d / name).read_bytes():
                        bad.append(f"{args[0]}: {name} differs")
                notes.append(args[0])
            # the I30 records and generated Bend files, decided again from scratch
            p = self.holon(["run", "--milestone", self.m, "--out", tmp / "results", "--gen-dir", tmp / "gen"], repo)
            if p.returncode != 0:
                bad.append(f"holon run failed: {(p.stdout + p.stderr)[-600:]}")
            else:
                for lid in sorted(self.entries):
                    a = self.results / f"{lid}.json"
                    b = tmp / "results" / f"{lid}.json"
                    if not b.is_file() or norm_record(json.loads(a.read_text()), self.root, self.gen) != \
                            norm_record(json.loads(b.read_text()), repo, tmp / "gen"):
                        bad.append(f"record {lid} differs")
                for sub in ("laws", "proofs"):
                    for q in sorted((self.gen / sub).rglob("*.bend")):
                        if not q.relative_to(self.gen / sub).parts[0].startswith("L_sort_"):
                            continue
                        if q.parent.name.startswith(tuple(self.entries)) or any(x in str(q) for x in self.entries):
                            r = tmp / "gen" / q.relative_to(self.gen)
                            if not r.is_file() or r.read_text() != q.read_text():
                                bad.append(f"{q.relative_to(self.root)} differs")
                notes.append("run")
            p = self.holon(["termsize", "--milestone", self.m, "--root", repo, "--out", tmp / "ts.json"], repo)
            if p.returncode != 0 or (tmp / "ts.json").read_bytes() != (sorts / "term_size.json").read_bytes():
                bad.append("termsize: term_size.json differs from its regeneration")
            else:
                notes.append("termsize")
            self.checks["G1"] = _res(not bad, f"regenerated byte-identical: {', '.join(notes)}" if not bad
                                     else f"differs: {bad[:8]}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def g3(self):
        from ..gate import laws_in_proofs
        bad = [str(p.relative_to(self.root)) for p in laws_in_proofs(self.gen)]
        for p in sorted(self.gen.rglob("*.bend")):
            code = _strip(p.read_text(encoding="utf-8"))
            for rx in ESCAPES:
                if rx.search(code):
                    bad.append(f"{p.relative_to(self.root)}: escape hatch {rx.pattern}")
        model = (self.gen / "sorts" / "models").resolve()
        for lid in self.entries:
            lf = self.gen / "laws" / lid / "LAWS.bend"
            if not lf.is_file():
                continue
            imps = re.findall(r"^import\s+(\S+)(?:\s+as\s+(\S+))?\s*$", lf.read_text(), re.M)
            others = [(t, a) for t, a in imps if t != "Base"]
            if len(others) != 1 or others[0][1] != "M" or (lf.parent / others[0][0]).resolve().parent != model:
                bad.append(f"{lid}: LAWS.bend imports {others}, not exactly the typed model as M")
        self.checks["G3"] = _res(not bad, "no law under proofs/, no escape hatch, every law file imports the typed "
                                          "model as M" if not bad else "; ".join(bad[:8]))

    def g5(self):
        from ..mpipeline import law_import_problem
        bad, n, slow = [], 0, 0.0
        for lid, label, proof, laws in self.proofs():
            n += 1
            t = time.time()
            r = bend.check(proof)
            slow = max(slow, time.time() - t)
            if not r.ok:
                bad.append(f"{lid} {label}: {r.first_line}")
            prob = law_import_problem(proof, laws)
            if prob:
                bad.append(f"{lid} {label}: {prob}")
        self.checks["G5"] = _res(not bad and n > 0, f"{n} proof files re-checked by Bend (slowest {round(slow, 1)} s)"
                                 if not bad else "; ".join(bad[:8]))

    def g7(self):
        bad, n = [], 0
        for lid, label, proof, _laws in self.proofs():
            n += 1
            r = bend.check_verdict(proof)
            if not r.ok:
                bad.append(f"{lid} {label}: BendTT {r.first_line}")
        self.checks["G7"] = _res(not bad and n > 0, f"{n} proof files re-checked by BendTT (--verdict)" if not bad
                                 else "; ".join(bad[:8]))

    def g11(self):
        bad = []
        for lid, r in self.records().items():
            if r is None:
                bad.append(f"{lid}: no record")
                continue
            if r.get("statement_hash") != self.registry["statements"].get(lid):
                bad.append(f"{lid}: statement hash differs from the registry")
            for k in ("laws", "model"):
                if not (self.root / r["artifacts"][k]).exists():
                    bad.append(f"{lid}: artifact {k} missing")
        self.checks["G11"] = _res(not bad, f"{len(self.entries)} records match the registry and name existing "
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
            if not bend.check(p).ok:
                bad.append(f"{lid}: its inhabitant does not check")
        if n == 0:
            self.na["G11V"] = "no I30 law of this milestone is PROVED: no at-site premise to inhabit"
            return
        self.checks["G11V"] = _res(not bad, f"{n} PROVED laws carry a checked reachable inhabitant" if not bad
                                   else "; ".join(bad))

    def g6(self):
        rp = self.root / "replay" / self.m / "sorts" / "report.json"
        rep = json.loads(rp.read_text()) if rp.is_file() else {"laws": {}}
        bad, n = [], 0
        for lid, r in self.records().items():
            if not r or r.get("status") != "REFUTED":
                continue
            for e, w in sorted((r.get("witnesses") or {}).items()):
                if w.get("status") != "REFUTED":
                    continue
                n += 1
                x = ((rep["laws"].get(lid) or {}).get("entries") or {}).get(e)
                if x is None:
                    bad.append(f"{lid}/{e}: not replayed")
                elif x.get("status") != "passed" or x.get("trace") != w["witness"]["steps"]:
                    bad.append(f"{lid}/{e}: replay {x.get('status')}")
                elif (w.get("replay") or {}).get("status") != "passed":
                    bad.append(f"{lid}/{e}: the record's replay is {(w.get('replay') or {}).get('status')}")
        self.checks["G6"] = _res(not bad, f"{n} REFUTED entry points replayed and passed on the real contract"
                                 if not bad else "; ".join(bad[:8]))

    def g9(self):
        bad = []
        v1 = json.loads((self.root / "schemas" / "result_record.schema.json").read_text())
        v2 = json.loads((self.root / "spec" / "schemas" / "result_record_v2.schema.json").read_text())
        from .. import schema as S
        for lid, r in self.records().items():
            if r is None:
                continue
            for name, sch in (("v1", v1), ("v2", v2)):
                errs = S.errors(r, sch)
                if errs:
                    bad.append(f"{lid}: {name} {errs[:2]}")
        self.checks["G9"] = _res(not bad, f"{len(self.entries)} records valid under v1 and v2" if not bad
                                 else "; ".join(bad[:6]))

    def g4(self):
        """Canaries: per subform among the decided laws, the counter-law with its entry step mutated must fail."""
        done = set()
        for lid, r in self.records().items():
            if not r or r.get("status") != "REFUTED" or r["subform"] in done:
                continue
            proof = self.root / r["artifacts"]["proof"]
            text = proof.read_text(encoding="utf-8")
            m = list(re.finditer(r"(?m)^def w_a(\d+)\(\) -> M\.HAct:\n  (.*)$", text))
            if not m:
                continue
            last = m[-1]
            body = last.group(2)
            # mutate the entry step's first word literal: the witness then no longer refutes the law (or no longer
            # computes the same states), and a sound checker rejects the counter-law
            mut = re.sub(r"M\.w_of_limbs\(\[(\d+)", lambda mm: f"M.w_of_limbs([{int(mm.group(1)) ^ 1}", body, count=1)
            if mut == body:
                mut = body.replace("M.w0()", "M.w_of_limbs([1, 0, 0, 0, 0, 0, 0, 0])", 1)
            tmp = proof.parent / "PROOF.canary.bend"
            try:
                tmp.write_text(text.replace(body, mut, 1), encoding="utf-8")
                res = bend.check(tmp)
            finally:
                tmp.unlink(missing_ok=True)
            self.canaries.append({"law": {"law_id": lid, "rule": "SORT", "subform": r["subform"]},
                                  "mutation": "the entry step's first word literal changed", "accepted": res.ok,
                                  "detail": res.first_line})
            done.add(r["subform"])
        bad = [c for c in self.canaries if c["accepted"]]
        self.checks["G4"] = _res(bool(self.canaries) and not bad, f"{len(self.canaries)} canaries rejected (subforms "
                                 f"{sorted(done)})" if self.canaries and not bad else
                                 f"canaries accepted: {[c['law']['law_id'] for c in bad]}" if bad else "no canary")

    def run(self, only: list | None = None) -> dict:
        from ..gate import Gate
        g = Gate(self.m, self.root)
        build = Path(tempfile.mkdtemp(prefix="holon-gate3-build-"))
        old = os.environ.get("HOLON_BUILD_DIR")
        os.environ["HOLON_BUILD_DIR"] = str(build)
        try:
            ok = g.genv()
            self.checks["GENV"] = g.checks["GENV"]
            order = ["G2", "G1", "G3", "G5", "G11", "G11V", "G6", "G9", "G7", "G4"]
            if only:
                order = [x for x in order if x in only]
            for k in order:
                if not ok:
                    self.checks[k] = _res(False, getattr(g, "genv_skip", "skipped: GENV failed"))
                    continue
                try:
                    getattr(self, k.lower())()
                except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                    self.checks[k] = _res(False, f"error: {type(e).__name__}: {e}")
        finally:
            if old is None:
                os.environ.pop("HOLON_BUILD_DIR", None)
            else:
                os.environ["HOLON_BUILD_DIR"] = old
            shutil.rmtree(build, ignore_errors=True)
        for k in ("G8", "GREF", "GEVID"):
            self.na.setdefault(k, {"G8": "covered by holon coverage --milestone M3 (gen/M3/coverage.json, a file "
                                         "several M3 keys share), not an I30 check",
                                   "GREF": "the disagreements of the typed model's refinement are filed in "
                                           "results/M3/sorts/disagreements.json (R5), not spec/M2/disagreements.json",
                                   "GEVID": "the evidence set covers M0-M2 facts; no M3 evidence set exists"}[k])
        rep = {"milestone": self.m, "passed": all(c["passed"] for c in self.checks.values()),
               "bend_version": g.bend_version, "checks": self.checks, "canaries": self.canaries,
               "not_applicable": self.na}
        if only:
            rep["partial"] = True
        return rep


def norm_record(r: dict, root: Path, gen: Path) -> dict:
    """A record without timings, its artifact paths relative to its gen dir (G1 compares records this way)."""
    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items() if k != "seconds"}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, str):
            for base in (str(Path(gen).resolve()) + "/", str(Path(root).resolve()) + "/"):
                x = x.replace(base, "")
            return x.replace("gen/M3/", "").replace(str(gen) + "/", "")
        return x
    return walk(r)


def main_gate(args) -> int:
    root = Path(args.root or ROOT).resolve()
    report_path = Path(args.report) if args.report else root / "results" / args.milestone / "gate_report.json"
    only = [c.strip() for c in args.checks.split(",") if c.strip()] if getattr(args, "checks", None) else None
    rep = Gate3(args.milestone, root).run(only)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for k, c in rep["checks"].items():
        print(f"{k:5s} {'PASS' if c['passed'] else 'FAIL'}  {c['detail']}")
    for k, why in (rep.get("not_applicable") or {}).items():
        print(f"{k:5s} N/A   {why}")
    print("GATE", "PASSED" if rep["passed"] else "FAILED")
    return 0 if rep["passed"] else 1
