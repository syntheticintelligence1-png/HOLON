"""`holon gate`: regenerate and re-check everything from scratch (whitepaper §9.3, M0_SPEC §7).

Order: GENV, G2, G1, G3, G5, G11, G11V, G6, G9, G7, G4. The report is always written; exit 0 iff passed.
`--checks G6,G9` runs a subset (after GENV) and marks the report partial.

  GENV  no bunfig.toml / .env under root, no BENDTT override and no global bunfig ($XDG_CONFIG_HOME,
        $HOME) (else Bend is never invoked); the command resolves to an absolute bun +
        bend2/main.ts pair whose fingerprint (checkout HEAD, bend2 sources, bun version, bun
        executable sha256) equals bend.pinned_fingerprint; that fingerprint is not in
        results/quarantine.json (agent-writable: self-certified until Q1); with --verdict enabled,
        the cached BendTT kernel binary, if built, has sha256 bend.pinned_kernel_sha256; the
        command a run actually executed is the fingerprinted pair; pinned bend version
  G2    statement hashes match REGISTRY.json; registry lists exactly laws/<m>; facts hash; and
        spec/bindings/<m>.json matches the kernel (BendTT) form of every definition each statement
        reaches in the committed models, plus the emitted statement and counter-law (a mismatch
        names the laws and the definitions); self-certified until I10 and Q1
  G1    regeneration into a temp dir is byte-identical (gen/**/*.bend, summary.json, and every
        result record with `seconds` stripped and artifact paths normalised), from a fresh build dir
  G3    no escape hatches in generated Bend; the checker reports no TODO / unsafe reliance
  G5    every PROVED/REFUTED PROOF.bend re-checks: exit 0 and ALL PROOFS CHECK, each within
        bend.budget_s_per_file seconds (default 120); timings go to results/<m>/gate_timing.json
  G11   every law has a record; every checked LAWS.bend states exactly its expected law
  G11V  non-vacuity: every premised PROVED law has a dual-checked inhabitant stating exactly its
        premises (holon/inhabit.py); a premised REFUTED law counts through its counter-law witness
  G6    every REFUTED record is bound to a passed replay: its witness sha256 is in the replay
        report, the report is for the facts' target commit, and a side not replayed is labelled
        "model-only pending replay". Strict since I4: the report has exactly the sides each
        witness claims (holon.filter.claimed_sides, from the IR), each with a status, a boolean
        obstruction_observed (true only when passed), a provenance from the enum, what was
        observed and the command; the record's witness_provenance and filter_bin equal
        holon.filter recomputed from the report; the report's toolchain hashes equal the pins in
        config/holon.json replay. G6 reads no git and runs no tool.
  G9    every record validates against the frozen v1 schema and spec/schemas/result_record_v2
  G7    second kernel: BendTT (--verdict) re-checks every proof, or the run is labelled
        single-kernel when Lean is unavailable
  G4    >= 10 canaries of >= 3 kinds (pin_const, swap_fn, negated), all rejected, each for a
        semantic reason (an expected/observed mismatch), never a parse error; an accepted canary
        quarantines the checker's fingerprint (results/quarantine.json, see `quarantine`)
"""
from __future__ import annotations

import copy
import json
import os
import re
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
CHECK_ORDER = ["GENV", "G2", "G1", "G3", "G5", "G11", "G11V", "G6", "G9", "G7", "G4"]
MODEL_ONLY = "model-only pending replay"
# Gate outputs under results/: never part of what G1 regenerates and compares (G1 compares only
# L_*.json, summary.json and deps.json; this guards that list).
G1_EXCLUDED = ("gate_timing.json", "gate_report.json", "quarantine.json")
QUARANTINE_NOTE = ("agent-writable tripwire: an accepted canary quarantines this checker version until a human "
                   "clears it")


def quarantine_path(root: Path) -> Path:
    return Path(root) / "results" / "quarantine.json"


def quarantine(root: Path, fingerprint: str, ids) -> Path:
    """Quarantine a checker fingerprint after an accepted canary: GENV then refuses that checker.

    Writes <root>/results/quarantine.json. It is an agent-writable tripwire, not a protected record:
    deleting the file clears it, which only a human may do. A quarantine already recorded for the
    same fingerprint gains the new canary ids; one recorded for another fingerprint is kept under
    "earlier" (GENV refuses those too), so a new quarantine never clears an old one."""
    p = quarantine_path(root)
    old = None
    if p.exists():
        try:
            old = _load(p)
        except Exception:  # noqa: BLE001  (an unreadable file is replaced, its text kept as evidence)
            old = {"unreadable": p.read_text(errors="replace")}
    ids = set(ids)
    earlier = []
    if isinstance(old, dict):
        earlier = [e for e in old.get("earlier", []) if isinstance(e, dict)]
        if old.get("fingerprint") == fingerprint:
            ids |= set(old.get("canaries") or [])
        else:
            earlier.append({k: v for k, v in old.items() if k != "earlier"})
    rec = {"fingerprint": fingerprint, "canaries": sorted(ids), "note": QUARANTINE_NOTE}
    if earlier:
        rec["earlier"] = earlier
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
    return p


def quarantined_fingerprints(root: Path) -> set[str]:
    """Fingerprints quarantined under root (raises if the quarantine file is unreadable)."""
    p = quarantine_path(root)
    if not p.exists():
        return set()
    q = _load(p)
    if not isinstance(q, dict):
        raise ValueError("results/quarantine.json is not an object")
    out = {q.get("fingerprint")} | {e.get("fingerprint") for e in q.get("earlier", []) if isinstance(e, dict)}
    return {f for f in out if isinstance(f, str)}


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
    checker: dict | None = None          # bend.fingerprint() of the checker GENV accepted
    timings: dict | None = None          # {"G5": {law_id: seconds}} once G5 has run
    genv_skip = "skipped: GENV failed"   # why the other checks were not run

    def __init__(self, milestone: str, root: Path):
        self.m, self.root = milestone, Path(root).resolve()
        self.cfg = bend.config(self.root)
        self.checks: dict[str, dict] = {}
        self.canaries: list[dict] = []
        self.bend_version = "not_run"
        reg = ir.load_registry(milestone, self.root)
        self.facts_path = self.root / reg.get("facts", "facts/morph_header.json")
        self.irv = ir.ir_version_of(milestone, self.root)
        self.results = self.root / "results" / milestone
        self.gen = self.root / "gen" / milestone
        self.check_outputs: list[str] = []

    # ------------------------------------------------------------ helpers
    def records(self) -> dict[str, dict]:
        out = {}
        for law in ir.load_laws_any(self.m, self.root):
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

    def norm_records(self, results: Path, gen: Path) -> dict[str, dict]:
        """Records with every `seconds` removed and artifact paths made relative to their gen dir."""
        def strip(x):
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items() if k != "seconds"}
            if isinstance(x, list):
                return [strip(v) for v in x]
            return x

        def rel(p):
            if p is None:
                return None
            q = Path(p)
            q = q if q.is_absolute() else self.root / q
            try:
                return q.resolve().relative_to(gen.resolve()).as_posix()
            except ValueError:
                return f"<outside gen>/{q.name}"
        out = {}
        for f in sorted(Path(results).glob("L_*.json")):
            r = strip(_load(f))
            if isinstance(r.get("artifacts"), dict):
                r["artifacts"] = {k: (rel(v) if k in ("laws", "proof", "model") else v) for k, v in r["artifacts"].items()}
            if isinstance(r.get("non_vacuity"), dict) and r["non_vacuity"].get("law"):
                r["non_vacuity"] = {**r["non_vacuity"], "law": rel(r["non_vacuity"]["law"])}
            out[f.stem] = r
        return out

    def claimed_sides(self) -> dict[str, set]:
        from .filter import claimed_sides
        reg = ir.load_registry(self.m, self.root)
        return {law["law_id"]: claimed_sides(law, reg.get("facts")) for law in ir.load_laws_any(self.m, self.root)}

    def target_commits(self) -> dict[str, str]:
        """facts sha256 -> the target commit named by that facts file."""
        out = {}
        for law in ir.load_laws_any(self.m, self.root):
            fp = self.root / law["facts"] if "facts" in law else self.facts_path
            out[law["facts_sha256"]] = F.load(fp)["target"]["commit"]
        return out

    def g6(self) -> None:
        """REFUTED records bound to the committed replay report (G6). Never raises: a malformed
        record or report is a failure with a reason."""
        from .replay import load_report, witness_sha256
        bad, n, model_only = [], 0, []
        try:
            report = load_report(self.m, self.root)
        except Exception as e:  # noqa: BLE001
            report = None
            bad.append(f"replay report unreadable: {e}")
        targets = self.target_commits()
        refuted = {lid: rec for lid, rec in self.records().items() if rec and rec.get("status") == "REFUTED"}
        claimed = self.claimed_sides()
        if report is None:
            if refuted and not bad:
                bad.append(f"no replay report for {len(refuted)} REFUTED records")
        elif not isinstance(report, dict):
            bad.append("replay report is not an object")
        else:
            commit = report.get("morph_commit")
            hashes = report.get("witness_sha256")
            laws = report.get("laws")
            if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
                bad.append(f"replay report morph_commit {commit!r} is not a full 40-hex commit")
                commit = ""
            if not isinstance(hashes, dict) or not isinstance(laws, dict):
                bad.append("replay report lacks witness_sha256 / laws objects")
                hashes, laws = {}, {}
            if report.get("harness_mismatch"):
                bad.append("replay report records a harness mismatch (the harness disagreed with the real code's "
                           "own commitment check)")
            ref = report.get("refinement")
            if isinstance(ref, dict) and ref.get("n_disagreements", 0):
                bad.append(f"replay report records {ref.get('n_disagreements')} refinement disagreements")
            for lid in sorted((set(hashes) | set(laws)) - set(refuted)):
                bad.append(f"{lid}: the replay report lists a law that is not REFUTED")
            for lid, rec in sorted(refuted.items()):
                n += 1
                rp = rec.get("replay")
                if not isinstance(rp, dict) or rp.get("status") != "passed":
                    bad.append(f"{lid}: record replay status is {rp.get('status') if isinstance(rp, dict) else rp!r}, "
                               "not passed")
                    rp = rp if isinstance(rp, dict) else {}
                want = targets.get(rec.get("facts_sha256"), "")
                if not isinstance(want, str) or not want or not commit.startswith(want):
                    bad.append(f"{lid}: report is for morph {commit[:12] or '?'}, facts target {want or '?'}")
                if hashes.get(lid) != witness_sha256(rec.get("witness")):
                    bad.append(f"{lid}: witness sha256 differs from the replay report")
                entry = laws.get(lid)
                if not isinstance(entry, dict):
                    bad.append(f"{lid}: not in the replay report")
                    continue
                bad += self.g6_strict(lid, rec, rp, entry, claimed.get(lid), model_only)
            bad += self.g6_toolchain(report)
        for lid, rec in sorted(self.records().items()):
            if rec and rec.get("status") != "REFUTED" and (rec.get("witness_provenance") is not None
                                                          or rec.get("filter_bin") is not None):
                bad.append(f"{lid}: a {rec.get('status')} record carries witness_provenance / filter_bin")
        self.checks["G6"] = _res(not bad, f"{n} REFUTED records bound to passed replays with strict sides, provenance "
                                          f"and recomputed filter bins; {MODEL_ONLY}: {', '.join(model_only) or 'none'}"
                                 if not bad else "; ".join(bad))

    def g6_strict(self, lid: str, rec: dict, rp: dict, entry: dict, claimed: set | None, model_only: list) -> list[str]:
        """I4: every claimed side present and well-formed; the record's provenance and bin equal the
        filter recomputed from the report. Never reads git and never runs a tool."""
        from . import filter as FL
        bad: list[str] = []
        m1 = "sides" in entry
        if m1 and not isinstance(entry.get("sides"), dict):
            return [f"{lid}: replay entry 'sides' is not an object"]
        if not m1:
            junk = sorted(k for k, v in entry.items() if not isinstance(v, dict))
            if junk:
                bad.append(f"{lid}: M0 replay entry holds non-side keys {junk}")
        ss = FL.sides(entry)
        if not ss:
            return bad + [f"{lid}: replay entry has no side"]
        if claimed is not None and set(ss) != claimed:
            bad.append(f"{lid}: replay sides {sorted(ss)} differ from the sides its witness claims {sorted(claimed)} "
                       f"(missing: {sorted(claimed - set(ss)) or 'none'})")
        for side, v in sorted(ss.items()):
            st = v.get("status")
            if st not in FL.STATUSES:
                bad.append(f"{lid}: {side} side status {st!r}")
                continue
            if not isinstance(v.get("obstruction_observed"), bool):
                bad.append(f"{lid}: {side} side obstruction_observed is not a boolean")
            elif v["obstruction_observed"] and st != "passed":
                bad.append(f"{lid}: {side} side observed the obstruction without passing")
            if v.get("provenance") not in FL.PROVENANCE:
                bad.append(f"{lid}: {side} side provenance {v.get('provenance')!r} is not one of {list(FL.PROVENANCE)}")
            if not isinstance(v.get("observed"), str) or not v.get("observed"):
                bad.append(f"{lid}: {side} side records nothing observed")
            if st in ("passed", "failed") and (not isinstance(v.get("command"), str) or not v.get("command")):
                bad.append(f"{lid}: {side} side records no command")
            if st == "not_applicable":
                if not str(v.get("observed", "")).startswith(MODEL_ONLY):
                    bad.append(f"{lid}: {side} side not replayed and not labelled '{MODEL_ONLY}'")
                else:
                    model_only.append(f"{lid}/{side}")
                    if MODEL_ONLY not in str(rp.get("detail", "")):
                        bad.append(f"{lid}: record says replay passed without saying its {side} side is {MODEL_ONLY}")
            elif st != "passed":
                bad.append(f"{lid}: {side} side replay {st!r}")
        if m1:
            if (entry.get("status") == "passed") != all(v.get("status") == "passed" for v in ss.values()):
                bad.append(f"{lid}: law-level replay status {entry.get('status')!r} is not the conjunction of its sides")
            if entry.get("obstruction_reproduced") is not all(v.get("obstruction_observed") is True for v in ss.values()):
                bad.append(f"{lid}: obstruction_reproduced is not the conjunction of its sides")
        want_wp, want_bin = FL.provenance_of(ss), FL.bin_of(ss)
        if rec.get("witness_provenance") != want_wp:
            bad.append(f"{lid}: record witness_provenance {rec.get('witness_provenance')!r} != {want_wp!r} from the report")
        if rec.get("filter_bin") != want_bin:
            bad.append(f"{lid}: record filter_bin {rec.get('filter_bin')!r} != {want_bin!r} recomputed from the report")
        return bad

    def g6_toolchain(self, report: dict) -> list[str]:
        """The report's toolchain hashes equal the pins in config/holon.json replay."""
        from .replay import PIN_KEYS
        pins = self.cfg.get("replay") or {}
        tc = report.get("toolchain")
        if not isinstance(tc, dict):
            return ["replay report records no toolchain"]
        bad = []
        for k in PIN_KEYS:
            pin = pins.get(k)
            if not isinstance(pin, str) or re.fullmatch(r"[0-9a-f]{64}", pin) is None:
                bad.append(f"config/holon.json replay.{k} is not a sha256 pin")
            elif tc.get(k) != pin:
                bad.append(f"replay report toolchain {k} {tc.get(k)!r} != config pin {pin}")
        return bad

    def g9(self) -> None:
        from . import schema
        v1 = _load(self.root / "schemas" / "result_record.schema.json")
        v2 = _load(self.root / "spec" / "schemas" / "result_record_v2.schema.json")
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
        self.checks["G9"] = _res(not bad and n > 0, f"{n} records valid against v1 and v2" if not bad and n
                                 else "; ".join(bad) or "no records")

    # ------------------------------------------------------------ checks
    def genv(self) -> bool:
        def fail(detail: str, skip: str) -> bool:
            self.checks["GENV"] = _res(False, detail)
            self.genv_skip = skip
            return False
        bad = bend.unsafe_env_files(self.root)
        if bad:
            return fail(f"unsafe Bun config present, Bend not invoked: {bad}", "skipped: unsafe environment")
        if os.environ.get("BENDTT"):
            return fail("BENDTT is set: an unpinned second-kernel override is refused (unset it, or pin it in a "
                        "reviewed config change)", "skipped: unpinned BENDTT override")
        glob_cfg = bend.global_bunfig()
        if glob_cfg:
            return fail(f"global bunfig present, Bend not invoked: {glob_cfg} (a preload there runs inside the "
                        "checker)", "skipped: unsafe environment")
        # identify the checker before running it: an unresolvable command is never invoked
        try:
            fp = bend.fingerprint(self.cfg)
        except Exception as e:  # noqa: BLE001
            return fail(f"cannot fingerprint the checker: {e}", "skipped: checker not the pinned one")
        pin_fp = self.cfg["bend"].get("pinned_fingerprint")
        where = f"checkout {fp['checkout']} at {fp['head'][:12]}, bun {fp['bun']}"
        if fp["fingerprint"] != pin_fp:
            return fail(f"checker fingerprint {fp['fingerprint']} ({where}, sources {fp['sources_sha256'][:12]}) "
                        f"is not the pinned fingerprint {pin_fp}", "skipped: checker not the pinned one")
        try:
            quarantined = fp["fingerprint"] in quarantined_fingerprints(self.root)
        except Exception as e:  # noqa: BLE001  (fail closed: only a human clears or repairs a quarantine)
            return fail(f"quarantine file unreadable, refusing: {e}", "skipped: checker quarantined")
        if quarantined:
            return fail(f"checker fingerprint {fp['fingerprint']} is in quarantine "
                        f"({quarantine_path(self.root).relative_to(self.root)}: an accepted canary; agent-writable "
                        "tripwire: self-certified until Q1); a human must clear it", "skipped: checker quarantined")
        # the second kernel: with $BENDTT refused, --verdict executes the binary bend2 built from
        # bendtt.lean and cached under $HOME; once built, it is pinned by its bytes
        if bend.verdict_enabled(self.cfg):
            try:
                kp = bend.verdict_kernel_path(Path(fp["checkout"]))
            except Exception as e:  # noqa: BLE001
                return fail(f"cannot locate the --verdict kernel: {e}", "skipped: checker not the pinned one")
            pin_k = self.cfg["bend"].get("pinned_kernel_sha256")
            if kp.exists():
                got_k = bend.file_sha256(kp)
                if got_k != pin_k:
                    return fail(f"--verdict kernel {kp} has sha256 {got_k}, not the pinned kernel sha256 {pin_k}",
                                "skipped: checker not the pinned one")
                kernel = f"kernel {kp} sha256 {got_k[:12]} pinned"
            else:
                kernel = (f"kernel not built yet ({kp} is absent: the first --verdict run builds it from the "
                          "pinned bendtt.lean, and GENV pins it from then on)")
        else:
            kernel = "kernel not checked (--verdict disabled)"
        self.checker = fp
        try:
            r = bend.run(["version"], cfg=self.cfg)
        except Exception as e:  # noqa: BLE001
            return fail(f"cannot run bend: {e}", "skipped: bend unavailable or not the pinned version")
        if r.argv[:len(fp["command"])] != fp["command"]:
            return fail(f"the executed command {r.argv[:len(fp['command'])]} is not the fingerprinted checker "
                        f"{fp['command']}", "skipped: checker not the pinned one")
        try:
            self.bend_version = bend.parse_version(r)
        except Exception as e:  # noqa: BLE001
            return fail(f"cannot run bend: {e}", "skipped: bend unavailable or not the pinned version")
        pin = self.cfg["bend"]["pinned_version"]
        ok = self.bend_version == pin
        self.checks["GENV"] = _res(ok, f"bend {self.bend_version}, pinned {pin}; fingerprint {fp['fingerprint']} "
                                       f"pinned ({where}, bun sha256 {fp['bun_sha256'][:12]}); executes "
                                       f"{' '.join(fp['command'])}; {kernel}; no global bunfig; not quarantined "
                                       "(results/quarantine.json is agent-writable: self-certified until Q1)")
        if not ok:
            self.genv_skip = "skipped: bend unavailable or not the pinned version"
        return ok

    def g2(self) -> None:
        self.g2_registry()
        if not self.checks["G2"]["passed"]:
            return
        from . import bindings
        try:
            p = bindings.path(self.m, self.root)
            if not p.exists():
                self.checks["G2"] = _res(False, f"no bindings: {p.relative_to(self.root)} is missing")
                return
            bound = _load(p)
            laws, defs, msgs = bindings.diff(bound, bindings.derive(self.m, self.root, self.cfg))
            # the LAWS.bend the checker accepted is exactly the bound emission for its status
            for lid, rec in self.records().items():
                if not rec or rec.get("status") not in ("PROVED", "REFUTED") or lid not in bound.get("laws", {}):
                    continue
                key = "counter_sha256" if rec["status"] == "REFUTED" else "statement_sha256"
                f = _resolve(self.root, rec["artifacts"].get("laws"))
                got = bindings.text_sha256(f.read_text()) if f and f.exists() else None
                if got != bound["laws"][lid].get(key):
                    laws.append(lid)
                    msgs.append(f"{lid}: the checked LAWS.bend is not the bound {key.split('_')[0]} emission")
            if laws:
                self.checks["G2"] = _res(False, "bindings: " + "; ".join(msgs))
            else:
                n = len(_load(p)["laws"])
                self.checks["G2"] = _res(True, self.checks["G2"]["detail"] + f"; {n} laws bound to their emitted "
                                         "statement and counter-law and to the kernel form of every definition they "
                                         "reach (registry and bindings are agent-writable: self-certified until I10 "
                                         "and the human's freeze, Q1)")
        except Exception as e:  # noqa: BLE001
            self.checks["G2"] = _res(False, f"bindings: error: {type(e).__name__}: {e}")

    def g2_registry(self) -> None:
        if self.irv == "holon-ir/0.2":
            from .mpipeline import check_registry_multi
            try:
                import holon.mpipeline as _mp
                old = _mp.ROOT
                _mp.ROOT = self.root
                try:
                    check_registry_multi(ir.load_laws_any(self.m, self.root), ir.load_registry(self.m, self.root))
                finally:
                    _mp.ROOT = old
                self.checks["G2"] = _res(True, "all statement and facts hashes match the registry")
            except Exception as e:  # noqa: BLE001
                self.checks["G2"] = _res(False, str(e))
            return
        try:
            laws = ir.load_laws_any(self.m, self.root)
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
            env["HOLON_BUILD_DIR"] = str(tmp / "build")
            p = subprocess.run([sys.executable, "-m", "holon", "run", "--milestone", self.m, "--out",
                                str(tmp / "results"), "--gen-dir", str(tmp / "gen")],
                               cwd=self.root, env=env, capture_output=True, text=True, timeout=3600)
            if p.returncode != 0:
                self.checks["G1"] = _res(False, f"regeneration failed: {(p.stdout + p.stderr)[-800:]}")
                return
            def bends(d: Path) -> dict[str, bytes]:
                return {f.relative_to(d).as_posix(): f.read_bytes() for f in sorted(d.rglob("*"))
                        if f.is_file() and (f.suffix == ".bend" or f.name.endswith(".defs.json"))}
            a, b = bends(self.gen), bends(tmp / "gen")
            diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            same = {f: (self.results / f).exists() and (self.results / f).read_bytes() ==
                    (tmp / "results" / f).read_bytes() for f in ("summary.json", "deps.json")
                    if f not in G1_EXCLUDED}
            same_summary = all(same.values())
            ra = self.norm_records(self.results, self.gen)
            rb = self.norm_records(tmp / "results", tmp / "gen")
            # canonical bytes, not ==: 1, 1.0 and true must not compare equal
            rdiff = sorted(k for k in set(ra) | set(rb)
                           if (k in ra) != (k in rb) or ir.canonical_json(ra[k]) != ir.canonical_json(rb[k]))
            ok = not diff and same_summary and bool(a) and not rdiff and bool(ra)
            self.checks["G1"] = _res(ok, f"{len(a)} generated .bend and .defs.json files identical, summary and deps identical, "
                                         f"{len(ra)} records identical" if ok else
                                     f"differs: {diff[:10]}; records differ: {rdiff[:10]}; "
                                     + "; ".join(f"{f} identical: {v}" for f, v in same.items())
                                     + f"; files: {len(a)}; records: {len(ra)}")
        except Exception as e:  # noqa: BLE001
            self.checks["G1"] = _res(False, f"error: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def recheck_outputs(self) -> None:
        for _, _, d in self.checked_dirs():
            if (d / "PROOF.bend").exists():
                self.check_outputs.append(bend.check(d / "PROOF.bend", self.cfg).out)

    def g5(self) -> None:
        bad, n, timing = [], 0, {}
        budget = float(self.cfg["bend"].get("budget_s_per_file", 120))
        for lid, rec, d in self.checked_dirs():
            n += 1
            proof = d / "PROOF.bend"
            if not proof.exists():
                bad.append(f"{lid}: PROOF.bend missing")
                continue
            r = bend.check(proof, self.cfg)
            self.check_outputs.append(r.out)
            timing[lid] = r.seconds
            if not r.ok:
                bad.append(f"{lid}: exit {r.code}, {r.first_line}")
            if r.seconds > budget:
                bad.append(f"{lid}: {r.seconds} s exceeds the budget of {budget:g} s per file")
        self.timings = {"G5": dict(sorted(timing.items()))}
        slowest = max(timing.values(), default=0)
        self.checks["G5"] = _res(not bad and n > 0, f"{n} proofs re-checked from scratch, slowest {slowest} s "
                                 f"(budget {budget:g} s per file)" if not bad else "; ".join(bad))

    def write_timings(self) -> Path:
        """results/<m>/gate_timing.json: per-proof check seconds. Not compared by G1 (G1_EXCLUDED)."""
        p = self.results / "gate_timing.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.timings, indent=2, sort_keys=True) + "\n")
        return p

    def quarantine_accepted(self) -> str:
        """Quarantine the running checker if it accepted a canary (said ALL PROOFS CHECK on a false law);
        a canary rejected for a non-semantic reason fails G4 but does not quarantine. Returns a detail suffix."""
        accepted = sorted(c["id"] for c in self.canaries if c.get("checker_first_line") == bend.MARK_OK)
        if not accepted:
            return ""
        fp = (self.checker or {}).get("fingerprint")
        if not fp:
            return "; checker fingerprint unknown, not quarantined"
        p = quarantine(self.root, fp, accepted)
        return (f"; the checker accepted {accepted}: {fp} quarantined in {p.relative_to(self.root)} "
                "(agent-writable tripwire: self-certified until Q1)")

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

    def g11v(self) -> None:
        from . import inhabit
        ok, detail = inhabit.g11v(self)
        self.checks["G11V"] = _res(ok, detail)

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

    def g4_machine(self) -> None:
        from .mcanary import run_canaries
        from .mpipeline import CompiledMachine
        tmp = Path(tempfile.mkdtemp(prefix="holon-gate-g4m-"))
        try:
            cm = CompiledMachine.build(self.facts_path, self.cfg)
            laws = ir.load_laws_any(self.m, self.root)
            recs = {k: v for k, v in self.records().items() if v}
            self.canaries = run_canaries(cm, laws, recs, tmp, self.cfg)
            kinds = {c["kind"] for c in self.canaries}
            accepted = [c["id"] for c in self.canaries if not c["rejected"]]
            ok = len(self.canaries) >= MIN_CANARIES and len(kinds) >= 3 and not accepted
            self.checks["G4"] = _res(ok, f"{len(self.canaries)} canaries of kinds {sorted(kinds)}, all rejected" if ok
                                     else f"{len(self.canaries)} canaries, kinds {sorted(kinds)}, ACCEPTED: {accepted}"
                                     + self.quarantine_accepted())
        except Exception as e:  # noqa: BLE001
            self.checks["G4"] = _res(False, f"error: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def g4(self) -> None:
        if self.irv == "holon-ir/0.2":
            return self.g4_machine()
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
                                     else f"{len(self.canaries)} canaries, kinds {sorted(kinds)}, ACCEPTED: {accepted}"
                                     + self.quarantine_accepted())
        except Exception as e:  # noqa: BLE001
            self.checks["G4"] = _res(False, f"error: {e}")

    # ------------------------------------------------------------ driver
    def run(self, only: list[str] | None = None) -> dict:
        order = CHECK_ORDER if not only else ["GENV"] + [g for g in CHECK_ORDER[1:] if g in only]
        unknown = sorted(set(only or []) - set(CHECK_ORDER))
        if unknown:
            raise SystemExit(f"unknown checks: {unknown}")
        steps = {"G2": self.g2, "G1": self.g1, "G5": self.g5, "G3": self.g3, "G11": self.g11, "G11V": self.g11v,
                 "G6": self.g6, "G9": self.g9, "G7": self.g7, "G4": self.g4}
        # a fresh build directory: nothing compiled is reused from the tree under check
        build = Path(tempfile.mkdtemp(prefix="holon-gate-build-"))
        old_build = os.environ.get("HOLON_BUILD_DIR")
        os.environ["HOLON_BUILD_DIR"] = str(build)
        try:
            if self.genv():
                if "G3" in order and "G5" not in order:
                    self.recheck_outputs()  # G3 reads the checker's own output; get it without recording G5
                for g in ["G2", "G1", "G5", "G3", "G11", "G11V", "G6", "G9", "G7", "G4"]:
                    if g in order:
                        try:
                            steps[g]()
                        except Exception as e:  # noqa: BLE001  (a crash is a failed check, and the report is written)
                            self.checks[g] = _res(False, f"error: {type(e).__name__}: {e}")
            else:
                for g in order[1:]:
                    self.checks[g] = _res(False, self.genv_skip)
        finally:
            if old_build is None:
                os.environ.pop("HOLON_BUILD_DIR", None)
            else:
                os.environ["HOLON_BUILD_DIR"] = old_build
            shutil.rmtree(build, ignore_errors=True)
        if self.timings is not None:  # G5 ran (also in a --checks subset)
            self.write_timings()
        checks = {g: self.checks[g] for g in order}
        rep = {"milestone": self.m, "passed": all(c["passed"] for c in checks.values()),
               "bend_version": self.bend_version, "checks": checks, "canaries": self.canaries}
        if only:
            rep["partial"] = True
        return rep


def main_gate(args) -> int:
    root = Path(args.root or ROOT).resolve()
    report_path = Path(args.report) if args.report else root / "results" / args.milestone / "gate_report.json"
    only = [c.strip() for c in args.checks.split(",") if c.strip()] if getattr(args, "checks", None) else None
    if only and not args.report:
        print("--checks writes a partial report: give --report (the committed results/<m>/gate_report.json is "
              "only ever written by a full run)", file=sys.stderr)
        return 2
    rep = Gate(args.milestone, root).run(only)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for g, c in rep["checks"].items():
        print(f"{g:5s} {'PASS' if c['passed'] else 'FAIL'}  {c['detail']}")
    print("GATE", ("PASSED" if rep["passed"] else "FAILED") + (" (partial)" if rep.get("partial") else ""))
    return 0 if rep["passed"] else 1
