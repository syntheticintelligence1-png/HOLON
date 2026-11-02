"""The gate's checks of a typed milestone's contract laws (BUILD_PLAN I33; tests_m3/test_o12_m3.py rules B7 and B10),
joined by holon.sorts.gate3 into its checks of the same name (as holon.fact.gate's):

  G5    every PROOF.bend of a decided contract law (its proof or counter-law, and a PROVED law's inhabitant) re-checked
        by Bend; G7 the same files by BendTT (--verdict)
  G11   every contract law has a record whose statement hash is the registry's and whose artifacts exist
  G11V  every PROVED contract law carries a checked, reachable inhabitant of its premises
        (gen/<M>/<id>/nonvac/, the law nv_<id>)
  G6    every REFUTED contract law's record carries a passed replay on the real contract
  G9    every contract law's record is valid under the v1 and v2 schemas

The laws are holon.sorts.contract3_run.contract_ids's. Nothing here names a law, a contract or a target.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import bend
from . import contract3 as C3
from .contract3_run import contract_ids

CHECKS = ("G5", "G11", "G11V", "G6", "G9", "G7")


def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


class ContractGate:
    def __init__(self, g3):
        self.g3 = g3
        self.m, self.root, self.gen, self.results = g3.m, g3.root, g3.gen, g3.results
        self.checks: dict = {}
        self.na: dict = {}
        self.ids = contract_ids(self.m, self.root)

    def records(self) -> dict:
        out = {}
        for lid in self.ids:
            p = self.results / f"{lid}.json"
            out[lid] = json.loads(p.read_text()) if p.is_file() else None
        return out

    def nonvac(self, lid: str) -> Path:
        return self.gen / lid / "nonvac"

    def proofs(self) -> list:
        out = []
        for lid, r in self.records().items():
            if not r or r.get("status") not in ("PROVED", "REFUTED"):
                continue
            if r["artifacts"].get("proof"):
                out.append((lid, "primary", self.root / r["artifacts"]["proof"]))
            p = self.nonvac(lid) / "PROOF.bend"
            if r["status"] == "PROVED" and (r.get("non_vacuity") or {}).get("status") == "inhabited" and p.is_file():
                out.append((lid, "nonvac", p))
        return out

    def g5(self):
        bad, n = [], 0
        for lid, label, proof in self.proofs():
            n += 1
            r = bend.check(proof)
            if not r.ok:
                bad.append(f"{lid} {label}: {r.first_line}")
        if n == 0:
            self.na["G5"] = "no contract law is decided"
            return
        self.checks["G5"] = _res(not bad, f"{n} contract law proof files re-checked by Bend" if not bad
                                 else "; ".join(bad[:8]))

    def g7(self):
        bad, n = [], 0
        for lid, label, proof in self.proofs():
            n += 1
            r = bend.check_verdict(proof)
            if not r.ok:
                bad.append(f"{lid} {label}: BendTT {r.first_line}")
        if n == 0:
            self.na["G7"] = "no contract law is decided"
            return
        self.checks["G7"] = _res(not bad, f"{n} contract law proof files re-checked by BendTT (--verdict)" if not bad
                                 else "; ".join(bad[:8]))

    def g11(self):
        bad = []
        for lid, r in self.records().items():
            if r is None:
                bad.append(f"{lid}: no record")
                continue
            if r.get("statement_hash") != self.g3.registry["statements"].get(lid):
                bad.append(f"{lid}: statement hash differs from the registry")
            for k in ("laws", "model"):
                if not r["artifacts"].get(k) or not (self.root / r["artifacts"][k]).exists():
                    bad.append(f"{lid}: artifact {k} missing")
            if r.get("status") in ("PROVED", "REFUTED") and not (self.root / str(r["artifacts"].get("proof"))).is_file():
                bad.append(f"{lid}: artifact proof missing")
        self.checks["G11"] = _res(not bad, f"{len(self.ids)} contract law records match the registry and name "
                                           "existing artifacts" if not bad else "; ".join(bad[:8]))

    def g11v(self):
        bad, n = [], 0
        for lid, r in self.records().items():
            if not r or r.get("status") != "PROVED":
                continue
            n += 1
            nv = r.get("non_vacuity") or {}
            p = self.nonvac(lid) / "PROOF.bend"
            lp = self.nonvac(lid) / "LAWS.bend"
            if nv.get("status") != "inhabited" or nv.get("reachable") is not True or not p.is_file():
                bad.append(f"{lid}: non-vacuity {nv.get('status')}")
                continue
            if f"law {C3.law_name(lid, 'nonvac')}:" not in lp.read_text():
                bad.append(f"{lid}: its inhabitant law is not {C3.law_name(lid, 'nonvac')}")
                continue
            if not bend.check(p).ok:
                bad.append(f"{lid}: its inhabitant does not check")
        if n == 0:
            self.na["G11V"] = "no contract law is PROVED"
            return
        self.checks["G11V"] = _res(not bad, f"{n} PROVED contract laws carry a checked reachable inhabitant"
                                   if not bad else "; ".join(bad[:8]))

    def g6(self):
        want = {lid: r for lid, r in self.records().items() if r and r.get("status") == "REFUTED"}
        if not want:
            self.na["G6"] = "no contract law is REFUTED"
            return
        bad = [f"{lid}: replay {(r.get('replay') or {}).get('status')}" for lid, r in sorted(want.items())
               if (r.get("replay") or {}).get("status") != "passed"]
        self.checks["G6"] = _res(not bad, f"{len(want)} REFUTED contract laws replayed and passed on the real contract"
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
        self.checks["G9"] = _res(not bad, f"{len(self.ids)} contract law records valid under v1 and v2" if not bad
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
    """Run the contract law checks and join each with gate3's check of the same name (or add it)."""
    cg = ContractGate(g3)
    if not cg.ids:
        return
    cg.run(only)
    for k, r in cg.checks.items():
        if k in g3.checks:
            a = g3.checks[k]
            g3.checks[k] = _res(a["passed"] and r["passed"], f"{a['detail']}; contract laws: {r['detail']}")
        else:
            why = g3.na.pop(k, None)
            g3.checks[k] = _res(r["passed"], f"contract laws: {r['detail']}"
                                + (f"; I30 laws: not applicable ({why})" if why else ""))
    for k, why in cg.na.items():
        if k not in g3.checks:
            g3.na[k] = f"{g3.na[k]}; contract laws: {why}" if k in g3.na else f"contract laws: {why}"
