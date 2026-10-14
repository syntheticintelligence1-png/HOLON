"""`holon gate` for a typed milestone (M3 and later; I30; the contract is the docstring of tests_m3/test_sort_types.py,
"Gate"): every check re-decided from scratch over the I30 laws, with the checks that have no meaning for the milestone
listed under not_applicable with a reason.

  GENV  the pinned checker (holon.gate.Gate.genv, unchanged)
  G2    the registry: `holon derive` reproduces laws/<M> byte for byte and every law's statement hash is the
        registry's; each law file states its law's coerce term; joined with holon.gate's G2 over every law (F30)
  G1    regeneration: `holon sorts`, `holon types`, `holon derive`, `holon model` and `holon termsize` reproduce
        gen/<M>/sorts (with the typed and untyped models), laws/<M> and the term-size report byte for byte, and
        `holon run` reproduces every I30 record and generated Bend file
  G3    no `law` under gen/<M>/proofs, no escape hatch in any generated Bend file, every law file imports exactly the
        typed model as M; joined with holon.gate's G3 over every law (F30)
  G8    holon.gate's G8 (the milestone's coverage report), when it applies (F30)
  G5    every PROOF.bend of a decided law (primary and per entry point) re-checked by Bend, importing its law
  G11   every record's statement hash is the registry's and its artifacts exist
  G11V  every PROVED law carries a checked, reachable inhabitant of its at-site premise (gen/<M>/<id>/nonvac/)
  G6    every REFUTED entry point is a passed entry of replay/<M>/sorts/report.json, with the record's trace, and
        no REFUTED record's own replay failed (a kernel-accepted counter-law the real contract disagrees with)
  G9    every record is valid under the v1 and v2 schemas
  G7    BendTT (--verdict) re-checks every decided law's proofs
  G4    canaries: per I30 subform among the laws, a counter-law whose witness is mutated (its entry step's clock or
        its first argument changed) must be rejected by Bend

The milestone's other laws (on M3, I24's PAR laws, merged with I30) keep holon.gate.Gate's G5, G11, G11V and G9 over
their records, and the milestone's evidence set its GEVID (Gate3.other_laws); each joins I30's check of the same name.
holon.gate.Gate's G2 (registry, statement lifecycle, bindings), G8 (coverage) and G3 run over every law of the
milestone, I30's included, and join I30's check of the same name (Gate3.whole_milestone, F30): a statement change on a
typed milestone is gated as on any other.
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
        # a milestone the gate cannot check (no registry, no derivation) fails every check with the reason, as
        # holon.gate.Gate does (audit F-M2-10), never with a traceback (F30)
        self.setup_error, self.entries, self.registry = None, {}, {}
        try:
            from .. import ir
            self.registry = ir.load_registry(milestone, self.root)
            dv = json.loads((self.root / "laws" / milestone / "DERIVATION.json").read_text())
            self.entries = {e["law_id"]: e for e in dv["laws"]
                            if e.get("rule") == "SORT" and e.get("subform") in SUBFORMS}
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.setup_error = f"milestone {milestone} cannot be checked: {type(e).__name__}: {e}"

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
            # the I30 laws only (I31: a DISCH law's G1 is its regeneration, holon.disch.gate)
            p = self.holon(["run", "--milestone", self.m, "--laws", ",".join(sorted(self.entries)), "--out",
                            tmp / "results", "--gen-dir", tmp / "gen", "--jobs", "3"], repo)
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
        if n == 0:
            self.na["G5"] = "no I30 law of this milestone is decided: no proof file to re-check"
            return
        self.checks["G5"] = _res(not bad and n > 0, f"{n} proof files re-checked by Bend (slowest {round(slow, 1)} s)"
                                 if not bad else "; ".join(bad[:8]))

    def g7(self):
        bad, n = [], 0
        for lid, label, proof, _laws in self.proofs():
            n += 1
            r = bend.check_verdict(proof)
            if not r.ok:
                bad.append(f"{lid} {label}: BendTT {r.first_line}")
        if n == 0:
            self.na["G7"] = "no I30 law of this milestone is decided: no proof file to re-check"
            return
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
            # (A30 review) a REFUTED record stands on its kernels (AGENTS rule 6); a replay on the real contract that
            # disagrees with its witness is a model/contract disagreement, flagged here, never absorbed into the status
            if (r.get("replay") or {}).get("status") not in ("passed", "not_applicable"):
                bad.append(f"{lid}: REFUTED, but its replay on the real contract is "
                           f"{(r.get('replay') or {}).get('status')}: {(r.get('replay') or {}).get('detail', '')[:200]}")
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
        if not self.canaries and not any(r and r.get("status") == "REFUTED" for r in self.records().values()):
            self.na["G4"] = "no I30 law of this milestone is REFUTED: no checked counter-law to mutate"
            return
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
            if self.setup_error is not None:   # F-M2-10, as holon.gate.Gate: every check fails with the reason
                for k in order + [x for x in ("G8", "GEVID") if not only or x in only]:
                    self.checks[k] = _res(False, self.setup_error)
                order, ok = [], False
            for k in order:
                if not ok:
                    self.checks[k] = _res(False, getattr(g, "genv_skip", "skipped: GENV failed"))
                    continue
                try:
                    getattr(self, k.lower())()
                except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                    self.checks[k] = _res(False, f"error: {type(e).__name__}: {e}")
            if self.setup_error is None and ok:
                from ..disch import gate as disch_gate     # I31: the DISCH laws' checks, joined by name
                try:
                    disch_gate.join(self, only)
                except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                    self.checks["G1"] = _res(False, f"DISCH checks: error: {type(e).__name__}: {e}")
            if self.setup_error is None:
                self.whole_milestone(g, ok, only, ("G2", "G8"))
                self.other_laws(g, ok, only)
                self.whole_milestone(g, ok, only, ("G3",))   # after G5: G3 reads the checker's output G5 recorded
        finally:
            if old is None:
                os.environ.pop("HOLON_BUILD_DIR", None)
            else:
                os.environ["HOLON_BUILD_DIR"] = old
            shutil.rmtree(build, ignore_errors=True)
        for k in ("GREF", "GEVID"):
            if k in self.checks or (k == "GEVID" and (self.gen / "evidence.json").is_file()):
                continue
            self.na.setdefault(k, {"GREF": "the disagreements of the typed model's refinement are filed in "
                                           f"results/{self.m}/sorts/disagreements.json (R5), not "
                                           "spec/M2/disagreements.json",
                                   "GEVID": f"no evidence set gen/{self.m}/evidence.json exists"}[k])
        rep = {"milestone": self.m, "passed": all(c["passed"] for c in self.checks.values()),
               "bend_version": g.bend_version, "checks": self.checks, "canaries": self.canaries,
               "not_applicable": self.na}
        if self.setup_error is not None:
            rep["setup_error"] = self.setup_error
        if only:
            rep["partial"] = True
        return rep


    # holon.gate.Gate's checks that hold for the milestone as a whole, over every law of it, I30's included (F30). I30's
    # routing of typed milestones here had dropped them:
    #   G2  the registry (holon.mpipeline.check_registry_multi), the statement lifecycle (every line of
    #       laws/STATEMENT_DIFF.jsonl accepted, every statement-hash change and deletion of laws/<M>/REGISTRY.json tied
    #       to an accepted entry, the frozen negations, the DERIVATION.json links, the binding change log) and the
    #       bindings spec/bindings/<M>.json of every law (holon.bindings; a typed law bound to the typed model);
    #   G8  the milestone's coverage report gen/<M>/coverage.json, when holon.gate says it applies;
    #   G3  escape hatches and bare core imports in every generated file, the checker's output of every proof G5
    #       re-checked, the IR premise and binder-type rules and the oracle rules over every law, no law under
    #       proofs/, and the Lean files.
    # Each result is joined with I30's check of the same name (I30's G2 and G3 stay as they were).
    WHOLE = ("G2", "G8", "G3")

    def whole_milestone(self, g, ok: bool, only: list | None, keys: tuple) -> None:
        for k in keys:
            if only and k not in only:
                continue
            if not ok:
                self.checks.setdefault(k, _res(False, getattr(g, "genv_skip", "skipped: GENV failed")))
                continue
            if k == "G8":
                why = g.g8_not_applicable()
                if why is not None:
                    self.na["G8"] = why
                    continue
            try:
                if k == "G3" and not g.check_outputs:   # G5 did not run: get the checker's output without recording it
                    g.recheck_outputs()
                getattr(g, k.lower())()
                r = g.checks[k]
            except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                r = _res(False, f"error: {type(e).__name__}: {e}")
            if k in self.checks:
                a = self.checks[k]
                self.checks[k] = _res(a["passed"] and r["passed"], f"I30 laws: {a['detail']}; holon.gate {k} over every "
                                                                   f"law of {self.m}: {r['detail']}")
            else:
                self.checks[k] = _res(r["passed"], f"holon.gate {k} over every law of {self.m}: {r['detail']}")

    # The milestone's laws outside I30's subforms (on M3, I24's PAR laws) keep the checks holon.gate.Gate gave them
    # before I30 routed typed milestones here (the merge of I24 and I30): G5, G11, G11V (F30) and G9 over their records
    # only, and GEVID over the milestone's evidence set when it has one. Each result is joined with I30's check of that
    # name.
    OTHER = ("G5", "G11", "G11V", "G9", "GEVID")

    def other_laws(self, g, ok: bool, only: list | None) -> None:
        from .. import ir
        from ..gate import Gate
        mine = set(self.entries)
        try:      # I31: the DISCH laws have their own checks (holon.disch.gate)
            dv = json.loads((self.root / "laws" / self.m / "DERIVATION.json").read_text())
            mine |= {e["law_id"] for e in dv["laws"] if e.get("rule") == "DISCH"}
        except (OSError, ValueError, KeyError):
            pass
        others = [law["law_id"] for law in ir.load_laws_any(self.m, self.root) if law["law_id"] not in mine]
        has_ev = (self.gen / "evidence.json").is_file()
        want = [k for k in self.OTHER if (not only or k in only) and (others if k != "GEVID" else has_ev)]
        if not want:
            return
        g.records = lambda: {k: v for k, v in Gate.records(g).items() if k not in mine}
        g.laws = lambda: [law for law in Gate.laws(g) if law["law_id"] not in mine]
        for k in want:
            if not ok:
                self.checks.setdefault(k, _res(False, getattr(g, "genv_skip", "skipped: GENV failed")))
                continue
            try:
                getattr(g, k.lower())()
                r = g.checks[k]
            except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                r = _res(False, f"error: {type(e).__name__}: {e}")
            if k == "GEVID":
                self.checks[k] = r
            elif k in self.checks:
                a = self.checks[k]
                self.checks[k] = _res(a["passed"] and r["passed"], f"I30 laws: {a['detail']}; the {len(others)} other "
                                                                   f"laws: {r['detail']}")
            else:
                why = self.na.pop(k, None)
                self.checks[k] = _res(r["passed"], f"the {len(others)} laws outside I30's subforms: {r['detail']}"
                                      + (f"; I30 laws: not applicable ({why})" if why else ""))


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
    if only and not args.report:   # as holon.gate.main_gate (F30): only a full run writes results/<m>/gate_report.json
        print("--checks writes a partial report: give --report (results/<m>/gate_report.json is only ever written by "
              "a full run)", file=sys.stderr)
        return 2
    rep = Gate3(args.milestone, root).run(only)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for k, c in rep["checks"].items():
        print(f"{k:5s} {'PASS' if c['passed'] else 'FAIL'}  {c['detail']}")
    for k, why in (rep.get("not_applicable") or {}).items():
        print(f"{k:5s} N/A   {why}")
    print("GATE", ("PASSED" if rep["passed"] else "FAILED") + (" (partial)" if rep.get("partial") else ""))
    return 0 if rep["passed"] else 1
