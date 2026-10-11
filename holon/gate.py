"""`holon gate`: regenerate and re-check everything from scratch (whitepaper §9.3, M0_SPEC §7).

Order: GENV, G2, G1, G3, G5, G11, G7, G4. The report is always written; exit 0 iff passed.

  GENV  no bunfig.toml / .env under root (else Bend is never invoked), pinned bend version
  G2    statement hashes match REGISTRY.json; registry lists exactly laws/<m>; facts hash
  G1    regeneration into a temp dir is byte-identical (gen/**/*.bend, summary.json)
  G3    no escape hatches in generated Bend; the checker reports no TODO / unsafe reliance
  G5    every PROVED/REFUTED PROOF.bend re-checks: exit 0 and ALL PROOFS CHECK
  G11   every law has a record; every checked LAWS.bend states exactly its expected law
  G7    second kernel: BendTT (--verdict) re-checks every proof, or the run is labelled
        single-kernel when Lean is unavailable
  G4    >= 10 canaries of >= 3 kinds (pin_const, swap_fn, negated), all rejected, each for a
        semantic reason (an expected/observed mismatch), never a parse error
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import bend, ir, refute
from .pipeline import law_names
from . import facts as F
from .gen import laws as LG
from .gen import proofs as PG
from .model_eval import CompiledModel, model_name

ROOT = Path(__file__).resolve().parents[1]
MIN_CANARIES = 10
MAX_CANARIES = 24
CHECK_ORDER = ["GENV", "G2", "G1", "G3", "G5", "G11", "G7", "G4"]


def _res(passed: bool, detail: str) -> dict:
    return {"passed": bool(passed), "detail": detail}


def _load(p: Path):
    return json.loads(Path(p).read_text())


def _resolve(root: Path, p: str | None) -> Path | None:
    if p is None:
        return None
    q = Path(p)
    return q if q.is_absolute() else root / q


class Gate:
    def __init__(self, milestone: str, root: Path):
        self.m, self.root = milestone, Path(root).resolve()
        self.cfg = bend.config(self.root)
        self.checks: dict[str, dict] = {}
        self.canaries: list[dict] = []
        self.bend_version = "not_run"
        self.facts_path = self.root / "facts" / "morph_header.json"
        self.results = self.root / "results" / milestone
        self.gen = self.root / "gen" / milestone
        self.check_outputs: list[str] = []

    # ------------------------------------------------------------ helpers
    def records(self) -> dict[str, dict]:
        out = {}
        for law in ir.load_laws(self.m, self.root):
            p = self.results / f"{law['law_id']}.json"
            out[law["law_id"]] = _load(p) if p.exists() else None
        return out

    def checked_dirs(self) -> list[tuple[str, dict, Path]]:
        """(law_id, record, proof dir) for every PROVED/REFUTED record."""
        out = []
        for lid, rec in self.records().items():
            if rec and rec.get("status") in ("PROVED", "REFUTED"):
                proof = _resolve(self.root, rec["artifacts"].get("proof"))
                out.append((lid, rec, proof.parent if proof else self.gen / lid))
        return out

    # ------------------------------------------------------------ checks
    def genv(self) -> bool:
        bad = bend.unsafe_env_files(self.root)
        if bad:
            self.checks["GENV"] = _res(False, f"unsafe Bun config present, Bend not invoked: {bad}")
            return False
        try:
            self.bend_version = bend.version(self.cfg)
        except Exception as e:  # noqa: BLE001
            self.checks["GENV"] = _res(False, f"cannot run bend: {e}")
            return False
        pin = self.cfg["bend"]["pinned_version"]
        self.checks["GENV"] = _res(self.bend_version == pin, f"bend {self.bend_version}, pinned {pin}")
        return self.bend_version == pin

    def g2(self) -> None:
        try:
            laws = ir.load_laws(self.m, self.root)
            reg = ir.load_registry(self.m, self.root)
            fsha = F.sha256_file(self.facts_path)
            bad = [l["law_id"] for l in laws if reg["statements"].get(l["law_id"]) != ir.statement_hash(l)]
            extra = sorted(set(reg["statements"]) ^ {l["law_id"] for l in laws})
            fbad = reg["facts_sha256"] != fsha or any(l["facts_sha256"] != fsha for l in laws)
            ok = not bad and not extra and not fbad
            self.checks["G2"] = _res(ok, "all statement hashes match the registry" if ok else
                                     f"hash mismatch: {bad}; id mismatch: {extra}; facts mismatch: {fbad}")
        except Exception as e:  # noqa: BLE001
            self.checks["G2"] = _res(False, f"error: {e}")

    def g1(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="holon-gate-g1-"))
        try:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(self.root) + os.pathsep + env.get("PYTHONPATH", "")
            p = subprocess.run([sys.executable, "-m", "holon", "run", "--milestone", self.m, "--out",
                                str(tmp / "results"), "--gen-dir", str(tmp / "gen")],
                               cwd=self.root, env=env, capture_output=True, text=True, timeout=3600)
            if p.returncode != 0:
                self.checks["G1"] = _res(False, f"regeneration failed: {(p.stdout + p.stderr)[-800:]}")
                return
            def bends(d: Path) -> dict[str, bytes]:
                return {f.relative_to(d).as_posix(): f.read_bytes() for f in sorted(d.rglob("*.bend"))}
            a, b = bends(self.gen), bends(tmp / "gen")
            diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            sa = self.results / "summary.json"
            same_summary = sa.exists() and _load(sa) == _load(tmp / "results" / "summary.json")
            ok = not diff and same_summary and bool(a)
            self.checks["G1"] = _res(ok, f"{len(a)} generated .bend files identical, summary identical" if ok else
                                     f"differs: {diff[:10]}; summary identical: {same_summary}; files: {len(a)}")
        except Exception as e:  # noqa: BLE001
            self.checks["G1"] = _res(False, f"error: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def g5(self) -> None:
        bad, n = [], 0
        for lid, rec, d in self.checked_dirs():
            n += 1
            proof = d / "PROOF.bend"
            if not proof.exists():
                bad.append(f"{lid}: PROOF.bend missing")
                continue
            r = bend.check(proof, self.cfg)
            self.check_outputs.append(r.out)
            if not r.ok:
                bad.append(f"{lid}: exit {r.code}, {r.first_line}")
        self.checks["G5"] = _res(not bad and n > 0, f"{n} proofs re-checked from scratch" if not bad else "; ".join(bad))

    def g3(self) -> None:
        bad = []
        for f in sorted(self.gen.rglob("*.bend")):
            hits = bend.escape_hatches(f.read_text())
            if hits:
                bad.append(f"{f.relative_to(self.root)}: {hits}")
        for out in self.check_outputs:
            if "TODO found" in out or "rely on unsafe or foreign code" in out or "relies on unsafe" in out:
                bad.append("checker reports an open goal or unsafe/foreign reliance")
                break
        self.checks["G3"] = _res(not bad, "no escape hatches" if not bad else "; ".join(bad))

    def g11(self) -> None:
        bad = []
        for lid, rec in self.records().items():
            if rec is None:
                bad.append(f"{lid}: no result record")
                continue
            if rec.get("status") not in ("PROVED", "REFUTED"):
                continue
            want = [LG.law_name(lid, counter=rec["status"] == "REFUTED")]
            laws_f = _resolve(self.root, rec["artifacts"].get("laws"))
            got = law_names(laws_f.read_text()) if laws_f and laws_f.exists() else []
            if got != want:
                bad.append(f"{lid}: LAWS.bend states {got or 'nothing'}, expected {want}")
        summ = self.results / "summary.json"
        if not summ.exists():
            bad.append("summary.json missing")
        self.checks["G11"] = _res(not bad, "every law has a record and a non-vacuous LAWS.bend" if not bad
                                  else "; ".join(bad))

    def g7(self) -> None:
        if not bend.verdict_enabled(self.cfg):
            self.checks["G7"] = _res(True, "single-kernel: BendTT/Lean unavailable, certificates labelled single-kernel")
            return
        bad, n = [], 0
        for lid, rec, d in self.checked_dirs():
            n += 1
            v = bend.check_verdict(d / "PROOF.bend", self.cfg)
            if not v.ok:
                bad.append(f"{lid}: {v.first_line or v.out[:200]}")
        self.checks["G7"] = _res(not bad, f"dual-kernel: {n} proofs re-checked by BendTT (--verdict)" if not bad
                                 else "; ".join(bad))

    # ------------------------------------------------------------ canaries (G4)
    def canary_candidates(self, facts: dict) -> list[tuple[str, str, dict]]:
        """(kind, source law, mutated law IR) from every PROVED law, in a fixed order."""
        out = []
        recs = self.records()
        fns = facts["functions"]
        for law in ir.load_laws(self.m, self.root):
            lid = law["law_id"]
            if not recs.get(lid) or recs[lid]["status"] != "PROVED":
                continue
            st = law["statement"]
            for i, p in enumerate(st.get("assume", [])):
                for side in (0, 1):
                    if "bytes" in p["eq"][side]:
                        b = bytes.fromhex(p["eq"][side]["bytes"][2:])
                        nb = bytes([(b[0] + 1) % 256]) + b[1:] if len(b) == 1 else b[:-1] + bytes([b[-1] ^ 1])
                        m = copy.deepcopy(law)
                        m["statement"]["assume"][i]["eq"][side]["bytes"] = "0x" + nb.hex()
                        out.append(("pin_const", lid, m))
            for side in (0, 1):
                t = st["claim"]["eq"][side]
                while "some" in t:
                    t = t["some"]
                if "call" in t:
                    kind = fns[t["call"]]["kind"]
                    for alt in sorted(f for f in fns if fns[f]["kind"] == kind and f != t["call"]):
                        m = copy.deepcopy(law)
                        tt = m["statement"]["claim"]["eq"][side]
                        while "some" in tt:
                            tt = tt["some"]
                        tt["call"] = alt
                        out.append(("swap_fn", lid, m))
            out.append(("negated", lid, copy.deepcopy(law)))
        return out

    def g4(self) -> None:
        try:
            facts = F.load(self.facts_path)
            model = CompiledModel.build(self.facts_path, cfg=self.cfg)
            name = model_name(self.facts_path)
            tmp = Path(tempfile.mkdtemp(prefix="holon-gate-g4-"))
            (tmp / "model").mkdir()
            shutil.copy(self.gen / "model" / f"{name}.bend", tmp / "model" / f"{name}.bend")
            imp = f"../model/{name}.bend"
            counts: dict[str, int] = {}
            for kind, src, law in self.canary_candidates(facts):
                if len(self.canaries) >= MAX_CANARIES:
                    break
                if counts.get(kind, 0) >= MAX_CANARIES // 3:
                    continue
                n = counts.get(kind, 0)
                law["law_id"] = f"CANARY_{kind}_{n}_{src}"
                if kind == "negated":
                    s = refute.search({**law, "statement": law["statement"]}, facts, model)
                    # the claim holds everywhere we look: take the first candidate as the point
                    pins = LG.collect_pins(law, facts)
                    label, env = next(refute.candidates(law, facts, pins))
                    if refute.evaluate(law, facts, model, env) is None or s.witness is not None:
                        continue
                    em = LG.emit(law, facts, imp, counter=True)
                    proof = PG.counter(em, facts, imp, env)
                    cex = env
                else:
                    s = refute.search(law, facts, model)
                    if s.witness is None:
                        continue  # the mutation did not make the law false: not a canary
                    em = LG.emit(law, facts, imp)
                    proof = next((t for _, g in PG.GENERATORS if (t := g(em, facts, imp))), None)
                    if proof is None:
                        continue
                    cex = s.witness
                d = tmp / law["law_id"]
                d.mkdir()
                (d / "LAWS.bend").write_text(em.text)
                (d / "PROOF.bend").write_text(proof)
                r = bend.check(d / "PROOF.bend", self.cfg)
                law.pop("notes", None)
                # A canary counts as rejected only for a semantic reason (a type mismatch the
                # checker explains); a parse or import error would reject it vacuously.
                semantic = r.marker == bend.MARK_FAIL and "- expected :" in r.out
                self.canaries.append({"id": law["law_id"], "kind": kind, "source_law": src,
                                      "negated": kind == "negated", "rejected": (not r.ok) and semantic,
                                      "checker_first_line": r.first_line, "counterexample": cex, "law": law})
                counts[kind] = n + 1
            shutil.rmtree(tmp, ignore_errors=True)
            kinds = {c["kind"] for c in self.canaries}
            accepted = [c["id"] for c in self.canaries if not c["rejected"]]
            ok = len(self.canaries) >= MIN_CANARIES and len(kinds) >= 3 and not accepted
            self.checks["G4"] = _res(ok, f"{len(self.canaries)} canaries of kinds {sorted(kinds)}, all rejected" if ok
                                     else f"{len(self.canaries)} canaries, kinds {sorted(kinds)}, ACCEPTED: {accepted}")
        except Exception as e:  # noqa: BLE001
            self.checks["G4"] = _res(False, f"error: {e}")

    # ------------------------------------------------------------ driver
    def run(self) -> dict:
        if self.genv():
            self.g2()
            self.g1()
            self.g5()
            self.g3()
            self.g11()
            self.g7()
            self.g4()
        else:
            for g in CHECK_ORDER[1:]:
                self.checks[g] = _res(False, "skipped: unsafe environment" if bend.unsafe_env_files(self.root)
                                      else "skipped: bend unavailable or not the pinned version")
        checks = {g: self.checks[g] for g in CHECK_ORDER}
        return {"milestone": self.m, "passed": all(c["passed"] for c in checks.values()),
                "bend_version": self.bend_version, "checks": checks, "canaries": self.canaries}


def main_gate(args) -> int:
    root = Path(args.root or ROOT).resolve()
    report_path = Path(args.report) if args.report else root / "results" / args.milestone / "gate_report.json"
    rep = Gate(args.milestone, root).run()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for g, c in rep["checks"].items():
        print(f"{g:5s} {'PASS' if c['passed'] else 'FAIL'}  {c['detail']}")
    print("GATE", "PASSED" if rep["passed"] else "FAILED")
    return 0 if rep["passed"] else 1
