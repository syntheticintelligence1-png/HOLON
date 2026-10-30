"""The gate's checks of Bundle II's laws (BUILD_PLAN row I84 = I37b; the PAR link_domain, FACT public_input and DISCH
self_controlled laws of holon.rules.bundle2), joined by holon.sorts.gate3 into its checks of the same name, as
holon.fact.gate joins the FACT laws':

  G1    `holon bundle2 laws --check` reproduces the analysis and the claims modules (one forge run of the laws'
        deployment), `holon bundle2 replay-laws --check` finds the report and the records in agreement, every law file
        regenerates from its IR (the law, or a REFUTED law's counter-law) byte for byte, and every record's
        generator_sha256 is the bundle laws' generators' digest now
  G5    every PROOF.bend of a decided law re-checked by Bend; G7 the same files by BendTT (--verdict)
  G11   every law has a record whose statement hash is the registry's and whose artifacts exist
  G11V  every PROVED law carries a checked, reachable inhabitant (none is PROVED by these deciders: not applicable
        while none is)
  G6    every REFUTED law is a passed entry of the replay report, and its record's replay passed
  G9    every record is valid under the v1 and v2 schemas

Nothing here names a target.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .. import bend

CHECKS = ("G1", "G5", "G11", "G11V", "G6", "G9", "G7")


def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


class BundleLawsGate:
    def __init__(self, g3):
        from .laws_decide import bundle_entries
        self.g3 = g3
        self.m = g3.m
        self.root = Path(g3.root)
        self.results = g3.results
        self.entries = bundle_entries(self.m, self.root)
        self.checks: dict = {}
        self.na: dict = {}

    def records(self) -> dict:
        out = {}
        for lid in sorted(self.entries):
            p = self.results / f"{lid}.json"
            out[lid] = json.loads(p.read_text()) if p.is_file() else None
        return out

    def proofs(self) -> list:
        return [(lid, self.root / r["artifacts"]["proof"]) for lid, r in self.records().items()
                if r and r.get("status") in ("PROVED", "REFUTED") and (r.get("artifacts") or {}).get("proof")]

    def holon(self, args: list) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "holon", *args], cwd=self.root, capture_output=True, text=True,
                              timeout=7200)

    # ------------------------------------------------------------------ checks
    def g1(self):
        from . import laws_decide as LD
        bad, notes = [], []
        p = self.holon(["bundle2", "laws", "--check", "--root", str(self.root)])
        if p.returncode != 0:
            bad.append(f"holon bundle2 laws --check: {(p.stdout + p.stderr)[-300:]}")
        notes.append("the analysis and the claims modules")
        p = self.holon(["bundle2", "replay-laws", "--check", "--root", str(self.root)])
        if p.returncode != 0:
            bad.append(f"holon bundle2 replay-laws --check: {(p.stdout + p.stderr)[-300:]}")
        notes.append("the replay report against the records")
        bad += self.law_files()
        notes.append("the law files")
        g = LD.generator_sha256(self.root)
        for lid, r in self.records().items():
            if r is not None and r.get("generator_sha256") != g:
                bad.append(f"{lid}: generator_sha256 is not the bundle laws' generators' digest now")
        notes.append("the records' generator digest")
        self.checks["G1"] = _res(not bad, f"bundle laws regenerated: {', '.join(notes)}" if not bad
                                 else f"bundle laws differ: {bad[:6]}")

    def law_files(self) -> list:
        """Every law file stated again from its IR and its record's status (holon.bundle2.laws_decide.law_text)."""
        from ..sorts import proofs3 as P3
        from . import laws_claims as LC
        from .laws import LawsCtx
        from .laws_decide import law_text
        bad = []
        L = LawsCtx(self.root, self.m)
        an = json.loads(L.analysis_path.read_text())
        claims, model = self.root / an["claims"]["section"], self.root / an["claims"]["model"]
        reg = json.loads((self.root / "laws" / self.m / "REGISTRY.json").read_text())
        for lid, r in self.records().items():
            if r is None:
                continue
            lp = self.root / r["artifacts"]["laws"]
            law = json.loads((self.root / "laws" / self.m / f"{lid}.json").read_text())
            hashes = [b["name"] for b in law["statement"]["binders"] if str(b.get("type", "")).startswith("Fn<")]
            want = law_text(law, reg["statements"][lid], P3.rel_import(lp.parent, model),
                            P3.rel_import(lp.parent, claims), hashes, r.get("status") == "REFUTED")
            if not lp.is_file() or lp.read_text() != want:
                bad.append(f"{lid}: its law file differs from its regeneration")
            fn = ("fact_" + LC.fact_x(lid)) if law.get("subform") == "public_input" else ("claim_" + LC.claim_x(lid))
            if f"F.{fn}(" not in want:
                bad.append(f"{lid}: its law file does not state its claim")
        return bad

    def g5(self):
        bad, n = [], 0
        for lid, proof in self.proofs():
            n += 1
            r = bend.check(proof)
            if not r.ok:
                bad.append(f"{lid}: {r.first_line}")
        if n == 0:
            self.na["G5"] = "no bundle law is decided"
            return
        self.checks["G5"] = _res(not bad, f"{n} bundle-law proof files re-checked by Bend" if not bad
                                 else "; ".join(bad[:8]))

    def g7(self):
        bad, n = [], 0
        for lid, proof in self.proofs():
            n += 1
            r = bend.check_verdict(proof)
            if not r.ok:
                bad.append(f"{lid}: BendTT {r.first_line}")
        if n == 0:
            self.na["G7"] = "no bundle law is decided"
            return
        self.checks["G7"] = _res(not bad, f"{n} bundle-law proof files re-checked by BendTT (--verdict)" if not bad
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
        self.checks["G11"] = _res(not bad, f"{len(self.entries)} bundle-law records match the registry and name "
                                           "existing artifacts" if not bad else "; ".join(bad[:8]))

    def g11v(self):
        proved = [lid for lid, r in self.records().items() if r and r.get("status") == "PROVED"]
        if not proved:
            self.na["G11V"] = "no bundle law is PROVED"
            return
        self.checks["G11V"] = _res(False, f"PROVED bundle laws without a checked reachable inhabitant: {proved[:6]}")

    def g6(self):
        want = {lid: r for lid, r in self.records().items() if r and r.get("status") == "REFUTED"}
        from .laws import LawsCtx
        L = LawsCtx(self.root, self.m)
        rep = json.loads(L.replay_path.read_text()) if L.replay_path.is_file() else {"laws": {}}
        bad = []
        for lid, r in sorted(want.items()):
            x = (rep.get("laws") or {}).get(lid)
            if x is None:
                bad.append(f"{lid}: not replayed")
            elif x.get("status") != "passed":
                bad.append(f"{lid}: replay {x.get('status')}")
            elif (r.get("replay") or {}).get("status") != "passed":
                bad.append(f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}")
        if not want:
            self.na["G6"] = "no bundle law is REFUTED"
            return
        self.checks["G6"] = _res(not bad, f"{len(want)} REFUTED bundle laws replayed and passed on the real code"
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
        self.checks["G9"] = _res(not bad, f"{len(self.entries)} bundle-law records valid under v1 and v2" if not bad
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
    """Run the bundle laws' checks and join each with gate3's check of the same name (or add it)."""
    bg = BundleLawsGate(g3)
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
    for k, why in bg.na.items():
        if k not in g3.checks:
            g3.na[k] = f"{g3.na[k]}; bundle laws: {why}" if k in g3.na else f"bundle laws: {why}"
