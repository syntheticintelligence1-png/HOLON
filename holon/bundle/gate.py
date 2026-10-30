"""The bundle laws' gate checks (I86; tests_m3/test_bundle_laws.py, rules RC1-RC3, D2 and RP1), joined by name with
holon.sorts.gate3's checks as holon.disch.gate's are:

  G5    every PROVED or REFUTED bundle record's PROOF.bend re-checks with the pinned Bend (ALL PROOFS CHECK)
  G11   every bundle law has a record; a decided one's LAWS.bend states exactly its law (or counter-law cl_<id>) as
        holon.bundle.lawrun.law_text writes it from the IR and the registry's statement hash, and its PROOF.bend
        imports that file
  G11V  every PROVED bundle law with premises carries a checked inhabitant: gen/<M>/<id>/nonvac/ holding exactly
        LAWS.bend (the non-vacuity law regenerated from the IR) and a PROOF.bend that checks, or, for an existential
        law, its own checked proof; a REFUTED law's non_vacuity is its counter-witness
  G6    every REFUTED bundle law and every PROVED existential one is replayed: its record's replay and its entry of
        replay/<M>/bundle_laws/report.json are passed
  G9    every bundle record is valid against the result record schemas (v1, v2) and names its rule, sub-form and
        dependencies

Nothing here names a target or a law.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CHECKS = ("G5", "G11", "G11V", "G6", "G9")


def _res(passed: bool, detail: str) -> dict:
    return {"passed": bool(passed), "detail": detail}


class BundleGate:
    def __init__(self, g3):
        from . import lawrun as LR
        self.LR = LR
        self.m, self.root, self.gen, self.results = g3.m, g3.root, g3.gen, g3.results
        self.entries = LR.bundle_entries(self.m, self.root)
        self.checks: dict = {}

    def records(self) -> dict:
        out = {}
        for lid in sorted(self.entries):
            p = self.results / f"{lid}.json"
            out[lid] = json.loads(p.read_text()) if p.is_file() else None
        return out

    def law(self, lid: str) -> dict:
        return json.loads((self.root / "laws" / self.m / f"{lid}.json").read_text())

    def run(self, only: list | None) -> None:
        for k in CHECKS:
            if only and k not in only:
                continue
            try:
                getattr(self, k.lower())()
            except Exception as e:  # noqa: BLE001  (a crash is a failed check)
                self.checks[k] = _res(False, f"error: {type(e).__name__}: {e}")

    def _check(self, p: Path) -> str | None:
        from .. import bend
        r = bend.check(p)
        return None if r.ok and (r.out or "").lstrip().startswith("ALL PROOFS CHECK") else (r.out or "")[-300:]

    def g5(self) -> None:
        bad, n = [], 0
        for lid, rec in self.records().items():
            if not rec or rec.get("status") not in ("PROVED", "REFUTED"):
                continue
            n += 1
            p = self.root / ((rec.get("artifacts") or {}).get("proof") or "-")
            why = "PROOF.bend missing" if not p.is_file() else self._check(p)
            if why:
                bad.append(f"{lid}: {why}")
        self.checks["G5"] = _res(not bad, f"{n} decided bundle laws re-check" if not bad else "; ".join(bad[:6]))

    def g11(self) -> None:
        from .. import ir
        reg = ir.load_registry(self.m, self.root)
        bad = []
        lctx = self.LR.LawCtx(self.root, self.m)
        for lid, rec in self.records().items():
            if rec is None:
                bad.append(f"{lid}: no result record")
                continue
            if rec.get("status") not in ("PROVED", "REFUTED"):
                continue
            sub, mname, site, _cls = self.LR.site_of(lctx, lid)
            lp = self.root / ((rec.get("artifacts") or {}).get("laws") or "-")
            kind = "counter" if rec["status"] == "REFUTED" else self.LR.law_kind(sub)
            want = self.LR.law_text(lid, sub, site, reg["statements"][lid],
                                    self.LR.rel_import(lp.parent, lctx.model_path(mname)),
                                    self.LR.rel_import(lp.parent, lctx.claims_path(mname)), kind)
            if not lp.is_file() or lp.read_text() != want:
                bad.append(f"{lid}: LAWS.bend is not the {kind} law generated from its IR")
                continue
            pp = self.root / ((rec.get("artifacts") or {}).get("proof") or "-")
            imp = self.LR.rel_import(pp.parent, lp) if pp.is_file() else None
            if imp is None or not re.search(rf"(?m)^import {re.escape(imp)} as Laws$", pp.read_text()):
                bad.append(f"{lid}: PROOF.bend does not import its LAWS.bend as Laws")
        self.checks["G11"] = _res(not bad, f"{len(self.entries)} bundle laws have records; every decided one states "
                                           "its generated law, which its proof imports" if not bad else
                                  "; ".join(bad[:6]))

    def g11v(self) -> None:
        from .. import ir
        reg = ir.load_registry(self.m, self.root)
        lctx = self.LR.LawCtx(self.root, self.m)
        bad, n = [], 0
        for lid, rec in self.records().items():
            if not rec:
                continue
            nv = rec.get("non_vacuity") or {}
            if nv.get("parent_statement_hash") != rec.get("statement_hash"):
                bad.append(f"{lid}: non_vacuity is for another statement")
            if rec.get("status") == "REFUTED":
                if nv.get("status") != "counter_witness":
                    bad.append(f"{lid}: REFUTED, but non_vacuity says {nv.get('status')!r}")
                continue
            if rec.get("status") != "PROVED":
                continue
            n += 1
            sub, mname, site, _cls = self.LR.site_of(lctx, lid)
            if sub == "keyed_external":   # an existential law's checked proof is its own inhabitant
                if nv.get("status") != "inhabited" or nv.get("law") != (rec.get("artifacts") or {}).get("laws"):
                    bad.append(f"{lid}: an existential PROVED law whose non_vacuity is not its own proof")
                continue
            d = self.gen / lid / "nonvac"
            files = sorted(f.name for f in d.iterdir()) if d.is_dir() else []
            if nv.get("status") != "inhabited" or files != ["LAWS.bend", "PROOF.bend"]:
                bad.append(f"{lid}: premised PROVED law without an inhabitant ({files})")
                continue
            want = self.LR.law_text(lid, sub, site, reg["statements"][lid],
                                    self.LR.rel_import(d, lctx.model_path(mname)),
                                    self.LR.rel_import(d, lctx.claims_path(mname)), "nonvac")
            if (d / "LAWS.bend").read_text() != want:
                bad.append(f"{lid}: the inhabitant's LAWS.bend is not the non-vacuity law generated from its IR")
                continue
            why = self._check(d / "PROOF.bend")
            if why:
                bad.append(f"{lid}: the inhabitant does not check: {why}")
        self.checks["G11V"] = _res(not bad, f"{n} PROVED bundle laws carry a checked inhabitant" if not bad else
                                   "; ".join(bad[:6]))

    def g6(self) -> None:
        rp = self.root / "replay" / self.m / "bundle_laws" / "report.json"
        rep = json.loads(rp.read_text()) if rp.is_file() else {"laws": {}}
        bad, n = [], 0
        for lid, rec in self.records().items():
            if not rec:
                continue
            sub = self.entries[lid].get("subform")
            if not (rec.get("status") == "REFUTED" or (rec.get("status") == "PROVED" and sub == "keyed_external")):
                continue
            n += 1
            x = (rep.get("laws") or {}).get(lid)
            if x is None or x.get("status") != "passed":
                bad.append(f"{lid}: replay {None if x is None else x.get('status')}")
            elif (rec.get("replay") or {}).get("status") != "passed":
                bad.append(f"{lid}: the record's replay is {(rec.get('replay') or {}).get('status')}")
        self.checks["G6"] = _res(not bad, f"{n} bundle witnesses replayed and passed on the real bundle" if not bad
                                 else "; ".join(bad[:6]))

    def g9(self) -> None:
        from .. import schema
        v1 = json.loads((self.root / "schemas" / "result_record.schema.json").read_text())
        v2 = json.loads((self.root / "spec" / "schemas" / "result_record_v2.schema.json").read_text())
        bad, n = [], 0
        for lid, rec in self.records().items():
            if rec is None:
                bad.append(f"{lid}: no result record")
                continue
            n += 1
            for name, sch in (("v1", v1), ("v2", v2)):
                errs = schema.errors(rec, sch)
                if errs:
                    bad.append(f"{lid}: {name}: {errs[:3]}")
            e = self.entries[lid]
            if (rec.get("rule"), rec.get("subform")) != (e.get("rule"), e.get("subform")):
                bad.append(f"{lid}: the record's rule and sub-form are not its law's")
            if not isinstance(rec.get("dependencies"), list):
                bad.append(f"{lid}: no dependencies list")
        self.checks["G9"] = _res(not bad and n > 0, f"{n} bundle records valid against v1 and v2" if not bad and n
                                 else "; ".join(bad[:6]) or "no records")


def join(g3, only: list | None) -> None:
    """Run the bundle laws' checks and join each with gate3's check of the same name (or add it)."""
    bg = BundleGate(g3)
    if not bg.entries:
        return
    bg.run(only)
    for k, r in bg.checks.items():
        if k in g3.checks:
            a = g3.checks[k]
            g3.checks[k] = _res(a["passed"] and r["passed"], f"{a['detail']}; bundle laws: {r['detail']}")
        else:
            why = g3.na.pop(k, None)
            g3.checks[k] = _res(r["passed"], f"bundle laws: {r['detail']}"
                                + (f"; I30 laws: not applicable ({why})" if why else ""))
