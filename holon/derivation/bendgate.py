"""The gate's checks of I88's derivation law set as I89 decides it (holon.derivation.bendengine; the contract is the
docstring of tests_m3/test_derivation_bend.py), joined by holon.sorts.gate3 into its checks of the same name. A verdict
of the set counts only if these pass:

  G2    statement and binding integrity: each law file of the set (laws/<M>/derivation/) hashes to I88's REGISTRY.json
        (holon.derivation.laws.statement_hash), and its record and its decision carry that hash; each law's LAWS.bend is
        byte for byte the rendering of that frozen statement (holon.derivation.bendlaws.Render), imports exactly the
        consumer model, the typed model, the product module and the header component, and states the decided law; the
        product module and the equivalence pair are byte for byte their regeneration; a rendering deviation is checked
        (the equivalence pair, holon.derivation.bendequiv, accepted by Bend and BendTT; a term that takes a closure
        twice takes the same binder twice)
  G5    every decided law's PROOF.bend, and the equivalence pair, re-checked by Bend and by BendTT (--verdict)
  G11   every law of the set has a decision and a record of the same status, naming existing artifacts
  G11V  every REFUTED law's witness is the counter-law's (non_vacuity counter_witness, both kernels); a PROVED law
        carries a checked inhabitant of its premises, or the finding "PROVED, non-vacuity not established" fails it
  G6    every REFUTED law's witness replayed and passed on the real consumer
        (replay/<M>/derivation/bend/witnesses.json), with the decision's observation and the record's difference
  G9    every record of the set is valid under the v1 and v2 schemas

Nothing here names a target.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CHECKS = ("G2", "G5", "G11", "G11V", "G6", "G9")      # the checks the derivation set joins (holon.sorts.gate3)
BEND_SIDECAR = "spec/M3/lib/derivation_bend.json"


def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


class DerivationGate:
    def __init__(self, g3):
        from . import laws as LW
        self.g3 = g3
        self.m = g3.m
        self.root = Path(g3.root)
        self.checks: dict = {}
        self.na: dict = {}
        self.side88 = LW.side_of(self.root, LW.LAWS_SIDECAR)
        self.bside = json.loads((self.root / BEND_SIDECAR).read_text())
        self.ids = [e["id"] for e in self.side88["laws"]]
        self.law_dir = self.root / self.side88["law_set"]["laws"]
        self.reg = json.loads((self.law_dir / "REGISTRY.json").read_text())
        dp = self.root / self.bside["outputs"]["decisions"]
        self.dec = json.loads(dp.read_text()) if dp.is_file() else None
        self._kernels: dict = {}

    def applies(self) -> bool:
        return self.side88["law_set"]["milestone"] == self.m and self.dec is not None

    def decision(self, lid: str) -> dict | None:
        return (self.dec.get("laws") or {}).get(lid)

    def record(self, lid: str) -> dict | None:
        p = self.root / self.side88["law_set"]["records"] / f"{lid}.json"
        return json.loads(p.read_text()) if p.is_file() else None

    def decided(self) -> list:
        return [lid for lid in self.ids if (self.decision(lid) or {}).get("status") in ("PROVED", "REFUTED")]

    def proofs(self) -> list:
        out = [("equivalence", self.root / self.dec["equivalence"]["proof_file"])]
        out += [(lid, self.root / self.decision(lid)["proof_file"]) for lid in self.decided()]
        return out

    def kernels(self, path: Path) -> tuple:
        """(bend's Run, BendTT's Run) of a file, once per gate run; bend2's stack overflow is retried."""
        from .. import bend
        if path not in self._kernels:
            def go(verdict: bool):
                r = None
                for _ in range(3):
                    r = bend.check_verdict(path, timeout=5400) if verdict else bend.check(path, timeout=5400)
                    if not bend.crashed(r):
                        break
                return r
            self._kernels[path] = (go(False), go(True))
        return self._kernels[path]

    # ------------------------------------------------------------------ checks
    def g2(self):
        from . import laws as LW
        from . import bendlaws as BL
        from . import bendequiv as BE
        from .bendengine import Engine
        bad = []
        I = BL.Inputs(self.root, json.loads((self.root / BEND_SIDECAR).read_text()))
        eng = Engine.__new__(Engine)          # the engine's paths and imports, without its kernel runs
        eng.root, eng.I = self.root, I
        eng.model_path = self.root / self.bside["outputs"]["model"]
        eng.pp = eng.model_path.parent / "product.bend"
        ip, _t, _k, _s = I.typed()
        eng.typed_path = Path(ip)
        regen = {eng.pp: BL.Product(I).text()}
        regen.update(BE.texts(I, eng.pp))
        for p, t in sorted(regen.items()):
            if not p.is_file() or p.read_text(encoding="utf-8") != t:
                bad.append(f"{p.relative_to(self.root).as_posix()} is not its regeneration")
        eq = self.root / self.dec["equivalence"]["proof_file"]
        if (self.root / self.dec["equivalence"]["laws_file"]).read_text().count("\nlaw ") != 3:
            bad.append("the equivalence pair does not state its three laws")
        b2, tt = self.kernels(eq)
        if not (b2.ok and tt.ok):
            bad.append(f"the equivalence pair: bend {b2.first_line!r}, BendTT {tt.first_line!r}")
        R = BL.Render(I)
        for law in LW.committed_laws(self.root, self.side88):
            lid = law["law_id"]
            sh = self.reg["statements"].get(lid)
            if LW.statement_hash(law, self.root) != sh:
                bad.append(f"{lid}: the law file does not hash to the registry's statement")
            d = self.decision(lid)
            r = self.record(lid)
            if d is None or d.get("statement_hash") != sh:
                bad.append(f"{lid}: the decision does not carry the registry's statement hash")
            if r is None or r.get("statement_hash") != sh:
                bad.append(f"{lid}: the record does not carry the registry's statement hash")
            if d is None:
                continue
            counter = d.get("law_name", "").startswith("cl_")
            lf = self.root / d["laws_file"]
            want = R.law_text(law, sh, eng.imports(lf.parent), counter)
            text = lf.read_text(encoding="utf-8") if lf.is_file() else None
            if text != want:
                bad.append(f"{lid}: LAWS.bend is not the rendering of the frozen statement")
                continue
            if re.findall(r"(?m)^law\s+(\w+)\s*:", text) != [d["law_name"]]:
                bad.append(f"{lid}: LAWS.bend does not state exactly {d['law_name']}")
            imps = re.findall(r"(?m)^import\s+(\S+)\s+as\s+(\w+)\s*$", text)
            if sorted(imps) != sorted((p, a) for a, p in eng.imports(lf.parent)):
                bad.append(f"{lid}: LAWS.bend's imports are not the four models")
            for m in re.finditer(r"P\.trailing\(([^\n]*?), P\.fuel0\(\)\)", text):
                a = BL.split_top(m.group(1))
                if len(a) < 8 or a[2] != a[3] or a[4] != a[5] or a[6] != a[7]:
                    bad.append(f"{lid}: a trailing term's closure copies are not one binder")
        self.checks["G2"] = _res(not bad, f"{len(self.ids)} derivation laws: law files hash to I88's registry, LAWS.bend "
                                          "is the frozen statement's rendering over the four models, the product "
                                          "module and the equivalence pair regenerate, and the pair checks in Bend "
                                          "and BendTT" if not bad else "; ".join(bad[:8]))

    def g5(self):
        bad = []
        ps = self.proofs()
        for lid, p in ps:
            if not p.is_file():
                bad.append(f"{lid}: {p.name} is missing")
                continue
            b2, tt = self.kernels(p)
            if not b2.ok:
                bad.append(f"{lid}: bend {b2.first_line!r}")
            if not tt.ok:
                bad.append(f"{lid}: BendTT {tt.first_line!r}")
        self.checks["G5"] = _res(not bad, f"{len(ps) - 1} decided derivation laws and the equivalence pair re-checked "
                                          "by Bend and by BendTT" if not bad else "; ".join(bad[:8]))

    def g11(self):
        bad = []
        for lid in self.ids:
            d, r = self.decision(lid), self.record(lid)
            if d is None or r is None:
                bad.append(f"{lid}: no {'decision' if d is None else 'record'}")
                continue
            if d["status"] != r.get("status"):
                bad.append(f"{lid}: the record's status {r.get('status')} is not the decision's {d['status']}")
            if not (self.root / d["laws_file"]).is_file():
                bad.append(f"{lid}: its LAWS.bend is missing")
            if d["status"] in ("PROVED", "REFUTED"):
                a = r.get("artifacts") or {}
                if a.get("proof") != d["proof_file"] or not (self.root / d["proof_file"]).is_file():
                    bad.append(f"{lid}: the record's proof artifact is not the decision's file")
        self.checks["G11"] = _res(not bad, f"{len(self.ids)} derivation laws have a decision and a record that agree "
                                           "and name existing artifacts" if not bad else "; ".join(bad[:8]))

    def g11v(self):
        bad, n = [], 0
        for lid in self.decided():
            n += 1
            d, r = self.decision(lid), self.record(lid) or {}
            nv = r.get("non_vacuity") or {}
            if d["status"] == "REFUTED":
                if nv.get("status") != "counter_witness" or nv.get("law") != d["law_name"]:
                    bad.append(f"{lid}: REFUTED without the counter-law's witness as its inhabitant")
            elif nv.get("status") != "inhabited":
                bad.append(f"{lid}: PROVED, non-vacuity not established (finding: no checked inhabitant of its "
                           "premises)")
        if n == 0:
            self.na["G11V"] = "no derivation law is decided"
            return
        self.checks["G11V"] = _res(not bad, f"{n} decided derivation laws carry a checked inhabitant" if not bad
                                   else "; ".join(bad[:8]))

    def g6(self):
        rp = self.root / self.bside["outputs"]["witnesses"]
        rep = json.loads(rp.read_text()) if rp.is_file() else {"laws": {}}
        bad, n = [], 0
        for lid in self.decided():
            d, r = self.decision(lid), self.record(lid) or {}
            if d["status"] != "REFUTED":
                continue
            n += 1
            from .. import replay_bind as RB   # I98: each judgment, for the final filter's one rule
            RB.judged(lid)
            x = (rep.get("laws") or {}).get(lid)
            obs = d.get("observation") or {}
            if x is None:
                bad.append(RB.refuse(lid, f"{lid}: not replayed"))
            elif x.get("status") != "passed":
                bad.append(RB.refuse(lid, f"{lid}: replay {x.get('status')}"))
            elif x.get("model") != [obs.get("lhs"), obs.get("rhs")] or x.get("real") != x.get("model"):
                bad.append(RB.refuse(lid, f"{lid}: the replayed observation is not the decision's"))
            elif (r.get("difference") or {}) != {"lhs": obs.get("lhs"), "rhs": obs.get("rhs")}:
                bad.append(RB.refuse(lid, f"{lid}: the record's difference is not the decision's observation"))
            elif (r.get("replay") or {}).get("status") != "passed":
                bad.append(RB.refuse(lid, f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}"))
        if n == 0:
            self.na["G6"] = "no derivation law is REFUTED"
            return
        self.checks["G6"] = _res(not bad, f"{n} REFUTED derivation laws replayed and passed on the real consumer"
                                 if not bad else "; ".join(bad[:8]))

    def g9(self):
        from .. import schema as S
        bad = []
        v1 = json.loads((self.root / "schemas" / "result_record.schema.json").read_text())
        v2 = json.loads((self.root / "spec" / "schemas" / "result_record_v2.schema.json").read_text())
        for lid in self.ids:
            r = self.record(lid)
            if r is None:
                continue
            for name, sch in (("v1", v1), ("v2", v2)):
                errs = S.errors(r, sch)
                if errs:
                    bad.append(f"{lid}: {name} {errs[:2]}")
        from .. import records as R   # I99 (audit M3/5 F-M3-19): premises hold the law's assume clauses
        from .decide import render_premise
        recs = {lid: r for lid in self.ids for r in [self.record(lid)] if r}
        bad = R.premise_problems_of(self.root, self.m, recs, law_dir=self.law_dir,
                                    render=lambda law: [render_premise(p) for p in law["statement"].get("assume", [])]) + bad
        self.checks["G9"] = _res(not bad, f"{len(self.ids)} derivation records valid under v1 and v2, their premises "
                                 "holding every assume clause" if not bad else "; ".join(bad[:6]))

    def run(self, only: list | None) -> None:
        for k in CHECKS:
            if only and k not in only:
                continue
            try:
                getattr(self, k.lower())()
            except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                self.checks[k] = _res(False, f"error: {type(e).__name__}: {e}")


def join(g3, only: list | None) -> None:
    """Run the derivation set's checks and join each with gate3's check of the same name (or add it)."""
    dg = DerivationGate(g3)
    if not dg.applies():
        return
    dg.run(only)
    for k, r in dg.checks.items():
        if k in g3.checks:
            a = g3.checks[k]
            g3.checks[k] = {"passed": a["passed"] and r["passed"],
                            "detail": f"{a['detail']}; derivation laws: {r['detail']}"}
        else:
            why = g3.na.pop(k, None)
            g3.checks[k] = {"passed": r["passed"], "detail": f"derivation laws: {r['detail']}"
                            + (f"; I30 laws: not applicable ({why})" if why else "")}
    for k, why in dg.na.items():
        if k not in g3.checks:
            g3.na[k] = f"{g3.na[k]}; derivation laws: {why}" if k in g3.na else f"derivation laws: {why}"
