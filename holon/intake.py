"""`holon intake`: the untrusted prover intake (I41; whitepaper §9.1 "Provers (untrusted: tactic generators, agents) ->
PROOF/", §9.2(3) the proof loop, §9.4 "Provers have no write access to LAWS/", §10.4 "Agents ... fill the remaining
goals. The only thing they can produce that matters is a proof file the kernel accepts", §12 L14). The contract is the
docstring of tests_m3/test_intake.py; this module implements it and names no law and no target.

  python -m holon intake [--milestone M] [--root DIR] [--inbox DIR] [--law ID ...] [--budget-s S] [--json]
  python -m holon intake --list [--milestone M] [--root DIR] [--json]

Inbox. proofs/inbox/<law_id>/ holds exactly PROOF.bend and submission.json ({"law_id", "prover": "agent:<session>",
"statement_hash"}), both regular files. It is the only thing an agent writes; the intake reads nothing else an agent
could have written: the law, the model and the core library a proof is checked against are regenerated here.

Decision. The checks run in REASONS order and the first that fails is the reason: the submission's form; the law
belongs to a milestone (laws/<M>/<law_id>.json and a committed record); the statement hash is the record's; the law is
eligible (its generators left it UNKNOWN, or an agent proof was accepted for it earlier); no escape hatch
(holon.bend.escape_hatches, comments included); no law declared (holon.bend.declares_law, G3's rule for proof files);
the proof imports its own law file at the layout path (holon.mpipeline.law_import_problem); G1 (Regeneration below):
no law file, then no model or core file, of the milestone differs from its regeneration; every required kernel
(required_kernels) accepts the proof against the regenerated law file, bend2 within the budget (killed at it). No
kernel runs on a submission an earlier check refused.

Regeneration (G1 for the law's milestone). In a fresh temporary directory, with a fresh build directory (never the
tree's build/), from the frozen IR (laws/<M>/), the facts and the committed records: the model each law is run against
(holon.mpipeline.run_model; M0: holon.gen.model), the core library (M2 and later, holon.gen.core.emit), and the law file
of every law as `holon run` writes it (the statement of a PROVED record, the counter-law of a REFUTED one with its
failing_conjunct, the statement of the submission's own law). A law `holon run` writes no Bend file for (a SORT-width
law, decided by holon.sorts.width; a statement the emitter or the IR rules reject) has no law file, so no kernel can
accept a proof of it. The proof is checked only inside a fresh directory that holds the regenerated model of its law,
the regenerated core library and its regenerated law file, at the layout path: no kernel reads the tree's own law,
model or core files.

`holon run` (holon.mpipeline.run_m1) decides the same way, after its generators and its refuter, every law they left
UNKNOWN that has a submission in <root>/proofs/inbox (decide_in_run): the run's own outcome stands in for the committed
record, the files it has just generated are the regeneration (so G1 within the run finds nothing changed), and the
kernels see a fresh directory of exactly those files. The CLI writes nothing under the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import bend, ir

ROOT = Path(__file__).resolve().parents[1]

# the refusal reasons, in the order the checks run: the first failing check is the reason
REASONS = ("bad_submission", "unknown_law", "statement_mismatch", "not_unknown", "escape_hatch", "declares_law",
           "missing_expected_law", "law_file_changed", "generated_file_changed", "kernel_rejected", "over_budget")
KERNELS = ("bend2", "bendtt", "lean4")
INBOX = Path("proofs") / "inbox"
PROOF, MANIFEST = "PROOF.bend", "submission.json"
MANIFEST_KEYS = ("law_id", "prover", "statement_hash")
AGENT = re.compile(r"agent:[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
STATEMENT_HASH = re.compile(r"sha256:[0-9a-f]{64}")
MILESTONE = re.compile(r"[MT][0-9]+")
TMP_MARK = "<regenerated>"


class UsageError(ValueError):
    """A command line the intake refuses before deciding anything (exit status 2)."""


# ------------------------------------------------------------------ configuration
def configured_budget(root: Path | str = ROOT) -> float:
    """G5's per-file budget: bend.budget_s_per_file in config/holon.json (default 120 s)."""
    return float(bend.config(Path(root))["bend"].get("budget_s_per_file", 120))


def required_kernels(milestone: str, root: Path | str = ROOT) -> list[str]:
    """The kernels that must accept an agent proof of a law of `milestone`: bend2 always; bendtt when BendTT's
    --verdict is enabled (holon.bend.verdict_enabled); lean4 when the milestone is in I9's Lean-covered set
    (holon.lean.applicable: holon-ir/0.1, i.e. M0)."""
    from . import lean
    out = ["bend2"]
    if bend.verdict_enabled(bend.config(Path(root))):
        out.append("bendtt")
    if lean.applicable(milestone, root):
        out.append("lean4")
    return out


def _kernels_without_milestone(root: Path) -> list[str]:
    """Required kernels of a submission that names no milestone: bend2, and bendtt when enabled (lean4 is not
    applicable without a milestone)."""
    return ["bend2"] + (["bendtt"] if bend.verdict_enabled(bend.config(root)) else [])


def milestones(root: Path | str = ROOT) -> list[str]:
    """Every milestone with frozen laws: laws/<X>/ with a REGISTRY.json, X matching [MT][0-9]+."""
    d = Path(root) / "laws"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and MILESTONE.fullmatch(p.name) and (p / "REGISTRY.json").is_file())


def eligible(rec: dict | None) -> bool:
    """A law is eligible iff its generators returned UNKNOWN: its record is UNKNOWN, or PROVED by an agent proof the
    intake accepted earlier (prover agent:...)."""
    if not isinstance(rec, dict):
        return False
    return rec.get("status") == "UNKNOWN" or (rec.get("status") == "PROVED"
                                              and str(rec.get("prover", "")).startswith("agent:"))


def _rel(p: Path, root: Path) -> str:
    """Repo-relative when inside root, absolute otherwise."""
    p = Path(os.path.abspath(p))
    try:
        return p.relative_to(Path(os.path.abspath(root))).as_posix()
    except ValueError:
        return str(p)


# ------------------------------------------------------------------ the committed tree (read only)
class Tree:
    """Laws and committed records of a repository root."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.ms = milestones(self.root)
        self._laws: dict[str, dict[str, dict]] = {}

    def laws(self, m: str) -> dict[str, dict]:
        if m not in self._laws:
            self._laws[m] = {law["law_id"]: law for law in ir.load_laws_any(m, self.root)}
        return self._laws[m]

    def record(self, m: str, lid: str) -> dict | None:
        p = self.root / "results" / m / f"{lid}.json"
        if not p.is_file():
            return None
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return r if isinstance(r, dict) else None

    def milestone_of(self, lid: str) -> str | None:
        """The milestone that has both laws/<M>/<law_id>.json (stating that law id) and a committed record for it."""
        for m in self.ms:
            if (self.root / "laws" / m / f"{lid}.json").is_file() and lid in self.laws(m) \
                    and self.record(m, lid) is not None:
                return m
        return None

    def eligible(self, m: str) -> list[str]:
        return sorted(lid for lid in self.laws(m) if eligible(self.record(m, lid)))


# ------------------------------------------------------------------ submissions
@dataclass
class Submission:
    law_id: str                     # the directory name
    path: Path
    prover: str | None = None       # the manifest's prover, when it is agent:<session>
    statement_hash: str | None = None
    proof: bytes | None = None      # PROOF.bend, when it is a regular file
    problems: list[str] = field(default_factory=list)

    @property
    def proof_sha256(self) -> str | None:
        return hashlib.sha256(self.proof).hexdigest() if self.proof is not None else None

    @property
    def text(self) -> str:
        return (self.proof or b"").decode("utf-8")


def read_submission(path: Path) -> Submission:
    """One inbox entry, read without following any link: what is wrong with it goes to `problems` (bad_submission)."""
    path = Path(path)
    sub = Submission(path.name, path)
    if path.is_symlink() or not path.is_dir():
        sub.problems.append(f"{path.name} is not a directory" + (" (it is a symbolic link)" if path.is_symlink() else ""))
        return sub
    names = sorted(os.listdir(path))
    extra = [n for n in names if n not in (PROOF, MANIFEST)]
    if extra:
        sub.problems.append(f"the submission holds more than {PROOF} and {MANIFEST}: {extra}")
    for n in (PROOF, MANIFEST):
        f = path / n
        if not os.path.lexists(f):
            sub.problems.append(f"{n} is missing")
        elif f.is_symlink() or not f.is_file():
            sub.problems.append(f"{n} is not a regular file")
    pf = path / PROOF
    if not pf.is_symlink() and pf.is_file():
        sub.proof = pf.read_bytes()
        try:
            sub.proof.decode("utf-8")
        except UnicodeDecodeError:
            sub.problems.append(f"{PROOF} is not UTF-8 text")
    mf = path / MANIFEST
    if mf.is_symlink() or not mf.is_file():
        return sub
    try:
        man = json.loads(mf.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        sub.problems.append(f"{MANIFEST} is not JSON: {type(e).__name__}")
        return sub
    if not isinstance(man, dict):
        sub.problems.append(f"{MANIFEST} is not a JSON object")
        return sub
    if sorted(man) != sorted(MANIFEST_KEYS):
        sub.problems.append(f"{MANIFEST} has keys {sorted(man)}, expected exactly {list(MANIFEST_KEYS)}")
    if man.get("law_id") != sub.law_id:
        sub.problems.append(f"law_id {man.get('law_id')!r} is not the directory name {sub.law_id!r}")
    pv = man.get("prover")
    if isinstance(pv, str) and AGENT.fullmatch(pv):
        sub.prover = pv
    else:
        sub.problems.append(f"prover {pv!r} is not agent:<session> (<session> matches [A-Za-z0-9][A-Za-z0-9_.-]{{0,63}}); "
                            "an agent cannot submit as the generators")
    h = man.get("statement_hash")
    if isinstance(h, str) and STATEMENT_HASH.fullmatch(h):
        sub.statement_hash = h
    else:
        sub.problems.append(f"statement_hash {h!r} is not sha256:<64 hex>")
    return sub


def submissions(inbox: Path) -> list[Submission]:
    """Every entry of the inbox, sorted by name (a missing inbox is empty)."""
    inbox = Path(inbox)
    if not inbox.is_dir():
        return []
    return [read_submission(inbox / n) for n in sorted(os.listdir(inbox))]


# ------------------------------------------------------------------ regeneration (G1 for one milestone)
def width_law(milestone: str, law: dict) -> bool:
    """Whether `holon run` decides the law without Bend (holon.mpipeline: a SORT-width law of an M2+ milestone goes to
    holon.sorts.width, which writes no law file)."""
    from .mpipeline import decided_without_bend
    return decided_without_bend(milestone, law)


class Regeneration:
    """The model, core library and law files of milestone m, regenerated under `tmp` (a fresh directory) with a fresh
    build directory, from the frozen IR, the facts and the committed records of `tree`."""

    def __init__(self, m: str, tree: Tree, cfg: dict, tmp: Path):
        self.m, self.tree, self.root, self.cfg, self.tmp = m, tree, tree.root, cfg, Path(tmp)
        self.files: dict[str, bytes] = {}           # repo-relative path -> bytes: models, core, decided law files
        self.statements: dict[str, str] = {}        # law id -> its statement text (every law with a Bend statement)
        self.models: dict[str, str] = {}            # law id -> the repo-relative path of the model its law imports
        self.no_statement: dict[str, str] = {}      # law id -> why holon run writes no law file for it
        self.law_paths: dict[str, str] = {}         # law id -> the repo-relative path of its law file (layout)
        self.proof_paths: dict[str, str] = {}       # law id -> the repo-relative path of its proof (layout)
        self.generated: list[str] = []              # the model and core paths, sorted
        if ir.ir_version_of(m, self.root) == "holon-ir/0.1":
            self._regen_01()
        else:
            self._regen_machine()
        self.generated = sorted(p for p in self.files if p not in set(self.law_paths.values()))

    def _layout(self, lid: str) -> str:
        from .mpipeline import layout
        ld, pd, up = layout(self.m, Path("gen") / self.m, lid)
        self.law_paths[lid] = (ld / "LAWS.bend").as_posix()
        self.proof_paths[lid] = (pd / "PROOF.bend").as_posix()
        return up

    def _regen_01(self) -> None:
        """M0 (holon/pipeline.py): the model of the registry's facts and the statement / counter-law per law."""
        from . import facts as F
        from .gen import laws as LG
        from .gen import model as G
        from .model_eval import model_name
        reg = ir.load_registry(self.m, self.root)
        fp = self.root / reg["facts"]   # the registry names the facts every law of the milestone is stated over
        facts, sha = F.load(fp), F.sha256_file(fp)
        name = model_name(fp)
        model_rel = f"gen/{self.m}/model/{name}.bend"
        self.files[model_rel] = G.generate(facts, sha).encode()
        imp = f"../model/{name}.bend"
        for lid, law in sorted(self.tree.laws(self.m).items()):
            self._layout(lid)
            self.models[lid] = model_rel
            try:
                em = LG.emit(law, facts, imp, header_note=ir.statement_hash(law))
            except LG.Unsupported as e:
                self.no_statement[lid] = f"holon run writes no law file for it (the emitter cannot express it: {e})"
                continue
            self.statements[lid] = em.text
            status = (self.tree.record(self.m, lid) or {}).get("status")
            if status == "PROVED":
                self.files[self.law_paths[lid]] = em.text.encode()
            elif status == "REFUTED":
                cl = LG.emit(law, facts, imp, counter=True, header_note=ir.statement_hash(law))
                self.files[self.law_paths[lid]] = cl.text.encode()

    def _regen_machine(self) -> None:
        """State-machine milestones (holon/mpipeline.py run_m1): per law, in the run's order, the model of its facts
        (run_model), its statement and, for a decided law, the law file the run writes; then the core library."""
        from . import mpipeline as MP
        from .gen import mlaws
        from .gen import oracles as O
        from .gen import refs as R
        laws = sorted(self.tree.laws(self.m).values(), key=lambda l: (not l.get("negation_of"), l["law_id"]))
        machines: dict[Path, tuple] = {}
        for law in laws:
            lid = law["law_id"]
            up = self._layout(lid)
            if width_law(self.m, law):
                self.no_statement[lid] = ("holon run decides this SORT-width law without Bend (holon.sorts.width: "
                                          "the extracted model has no reachability predicate) and writes no law file "
                                          "for it, so no kernel can check a proof against one")
                continue
            fp = self.root / law["facts"]
            if fp not in machines:
                cm = MP.run_model(self.m, fp, self.cfg, root=self.root)
                name = MP.model_name(fp)
                rel = f"gen/{self.m}/model/{name}.bend"
                self.files[rel] = cm.source.read_bytes()
                machines[fp] = (cm, name, rel)
            cm, name, model_rel = machines[fp]
            self.models[lid] = model_rel
            imp = f"{up}model/{name}.bend"
            rec = self.tree.record(self.m, lid) or {}
            try:
                shash = R.law_hash(law, cm.facts, oracles=cm.oracles, root=self.root)
                ir.check_premises(law)
                if law.get("ir_version") == "holon-ir/0.3":
                    ir.check_binder_types(law, cm.facts)
                if MP.m2plus(self.m):
                    O.check_law(law, cm.oracles)
                em = mlaws.Emitter(cm.m).emit(law, imp, note=shash)
                counter = (mlaws.Emitter(cm.m).emit(law, imp, counter=True, note=shash,
                                                    conjunct=rec.get("failing_conjunct"))
                           if rec.get("status") == "REFUTED" else None)
            except (mlaws.Unsupported, ir.IRError, O.OracleError) as e:
                self.no_statement[lid] = f"holon run writes no law file for it ({type(e).__name__}: {e})"
                continue
            self.statements[lid] = em.text
            if rec.get("status") == "PROVED":
                self.files[self.law_paths[lid]] = em.text.encode()
            elif counter is not None:
                self.files[self.law_paths[lid]] = counter.text.encode()
        if MP.m2plus(self.m):
            from .gen import core as C
            out = self.tmp / "core-gen"
            C.emit(out, cfg=self.cfg)
            for n in ("LAWS.bend", "PROOF.bend"):
                self.files[f"gen/{self.m}/core/{n}"] = (out / "core" / n).read_bytes()

    def differs(self, lid: str) -> tuple[list[str], list[str]]:
        """(law files, model and core files) of the tree that differ from the regeneration, repo-relative and sorted.
        A law file differs when it is present but different, or missing although its record names one (a decided
        law); a law file present where `holon run` writes none (an UNKNOWN law other than the submission's own)
        differs too. The submission's own law file may be absent: holon run writes none for an UNKNOWN law."""
        def have(rel: str) -> bytes | None:
            p = self.root / rel
            return p.read_bytes() if p.is_file() else None
        law_d = []
        for other, rel in sorted(self.law_paths.items()):
            got = have(rel)
            if rel in self.files:
                want = self.files[rel]
            elif other == lid:
                want = self.statements.get(lid, "").encode() if lid in self.statements else None
                if got is None:
                    continue
            else:
                want = None
            if got != want:
                law_d.append(rel)
        gen_d = [rel for rel in self.generated if have(rel) != self.files[rel]]
        return sorted(set(law_d)), sorted(gen_d)

    def kernel_files(self, lid: str) -> tuple[dict[str, bytes], str | None]:
        """What a kernel may read for a proof of lid: the regenerated model its law imports, the regenerated core
        library and its regenerated law file (the statement); with the reason when there is no law file."""
        out = {rel: b for rel, b in self.files.items() if rel.startswith(f"gen/{self.m}/core/")}
        if lid in self.models:
            out[self.models[lid]] = self.files[self.models[lid]]
        if lid in self.statements:
            out[self.law_paths[lid]] = self.statements[lid].encode()
            return out, None
        return out, self.no_statement.get(lid, "holon run writes no law file for it")


# ------------------------------------------------------------------ the checks
def _import_problem(text: str, law_rel: str, proof_rel: str) -> str | None:
    """holon.mpipeline.law_import_problem for the proof text at its layout path."""
    from .mpipeline import law_import_problem
    tmp = Path(tempfile.mkdtemp(prefix="holon-intake-import-"))
    try:
        pf = tmp / proof_rel
        pf.parent.mkdir(parents=True, exist_ok=True)
        pf.write_text(text, encoding="utf-8")
        return law_import_problem(pf, tmp / law_rel)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _first(out: str, tmp: Path | None = None, n: int = 14) -> str:
    if tmp is not None:
        out = out.replace(str(tmp), TMP_MARK)
    return "\n".join(out.strip().splitlines()[:n])


@dataclass
class KernelOutcome:
    kernels: dict
    seconds: float | None = None
    bend2: bend.Run | None = None
    reason: str | None = None
    detail: str = ""


def check_kernels(files: dict[str, bytes], no_statement: str | None, proof_rel: str, proof: bytes, required: list[str],
                  budget_s: float, cfg: dict, lean_law: tuple | None = None) -> KernelOutcome:
    """Run the required kernels on the proof inside a fresh directory that holds `files` (repo-relative paths), the
    proof at proof_rel: bend2 within budget_s (killed at it; a timeout is over_budget), then bendtt (--verdict), then
    lean4 (the Lean text holon.lean's emitters produce for the PROVED verdict of lean_law = (law, facts, facts_sha256)).
    The first kernel that does not accept refuses the proof (kernel_rejected); the later ones do not run."""
    k = {n: ("not_run" if n in required else "not_applicable") for n in KERNELS}
    tmp = Path(tempfile.mkdtemp(prefix="holon-intake-kernel-"))
    try:
        for rel, b in sorted(files.items()):
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b)
        pf = tmp / proof_rel
        pf.parent.mkdir(parents=True, exist_ok=True)
        pf.write_bytes(proof)
        r = bend.run_budgeted([pf.name], cwd=pf.parent, budget_s=budget_s, cfg=cfg)
        if r.code is None:
            k["bend2"] = "timeout"
            return KernelOutcome(k, r.seconds, r, "over_budget",
                                 f"bend2 did not finish within the budget of {budget_s:g} s and was killed")
        why = f"; {no_statement}" if no_statement else ""
        if not r.ok:
            k["bend2"] = "failed"
            return KernelOutcome(k, r.seconds, r, "kernel_rejected",
                                 f"bend2 rejected the proof against the regenerated law file{why}:\n{_first(r.out, tmp)}")
        k["bend2"] = "checked"
        if no_statement:   # never reached: a proof whose law file is absent cannot check; refuse it all the same
            return KernelOutcome(k, r.seconds, r, "kernel_rejected", f"no law file to check against: {no_statement}")
        if "bendtt" in required:
            v = bend.check_verdict(pf, cfg)
            k["bendtt"] = "checked" if v.ok else ("timeout" if v.code is None else "failed")
            if not v.ok:
                return KernelOutcome(k, r.seconds, r, "kernel_rejected",
                                     f"bendtt (--verdict) did not accept the proof:\n{_first(v.out, tmp)}")
        if "lean4" in required:
            res = _lean4(lean_law, tmp, cfg)
            k["lean4"] = res[0]
            if res[0] != "checked":
                return KernelOutcome(k, r.seconds, r, "kernel_rejected", f"lean4 did not accept the law: {res[1]}")
        names = " and ".join(n for n in KERNELS if k[n] == "checked")
        return KernelOutcome(k, r.seconds, r, None, f"accepted: {names} checked the proof against the regenerated law "
                                                    "file, and G1 found the milestone's law, model and core files as "
                                                    "their regeneration")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _lean4(lean_law: tuple | None, tmp: Path, cfg: dict) -> tuple[str, str]:
    """lean4 on a law of I9's Lean-covered set: the Lean text holon.lean's emitters produce for its PROVED verdict,
    checked from scratch (holon.lean.check_text)."""
    from . import lean
    if lean_law is None:
        return "failed", "no law to emit"
    law, facts, facts_sha = lean_law
    try:
        text, info = lean.emit_for(law, facts, facts_sha, "PROVED", None)
    except Exception as e:  # noqa: BLE001  (an inexpressible law is not accepted, never a crash)
        return "failed", f"the Lean emitters cannot express it: {type(e).__name__}: {e}"
    lcfg = lean.config()
    res = lean.check_text(text, tmp / "lean", expect=[info["main"]], cfg=lcfg,
                          timeout=float(lcfg.get("budget_s_per_file", 120)))
    out = {"checked": "checked", "timeout": "timeout"}.get(res["result"], "failed")
    return out, f"Lean result {res['result']}"


# ------------------------------------------------------------------ one decision
def _blank(sub: Submission, m: str | None, root: Path) -> dict:
    req = required_kernels(m, root) if m else _kernels_without_milestone(root)
    return {"law_id": sub.law_id, "milestone": m, "submission": _rel(sub.path, root), "prover": sub.prover,
            "proof_sha256": sub.proof_sha256, "verdict": "refused", "reason": None, "detail": "", "hatches": [],
            "differs": [], "kernels": {n: ("not_run" if n in req else "not_applicable") for n in KERNELS},
            "seconds": None}


def _refuse(d: dict, reason: str, detail: str) -> dict:
    assert reason in REASONS, reason
    d.update(verdict="refused", reason=reason, detail=detail)
    return d


def decide(sub: Submission, m: str | None, rec: dict | None, look, budget_s: float, cfg: dict, root: Path) -> dict:
    """The decision on one submission. `look` supplies what the checks after the textual ones need for the law's
    milestone m: paths(lid) -> (law file, proof) at the layout path, g1(lid) -> (law files, model/core files) that
    differ, kernel_files(lid) -> (files, reason there is no law file), lean_law(lid). The returned decision carries
    the bend2 run under the private key "_bend2" (popped before it is printed)."""
    d = _blank(sub, m, root)
    if sub.problems:
        return _refuse(d, "bad_submission", "; ".join(sub.problems))
    if m is None or rec is None:
        return _refuse(d, "unknown_law", f"no milestone has both laws/<M>/{sub.law_id}.json and a committed record "
                                         f"results/<M>/{sub.law_id}.json")
    if sub.statement_hash != rec.get("statement_hash"):
        return _refuse(d, "statement_mismatch", f"the submission names statement {sub.statement_hash}, the record's "
                                                f"(frozen) statement is {rec.get('statement_hash')}")
    if not eligible(rec):
        return _refuse(d, "not_unknown", f"its generators decided it: {rec.get('status')} (prover "
                                         f"{rec.get('prover', 'generator')}); only a law they left UNKNOWN takes an "
                                         "agent proof")
    text = sub.text
    hatches = bend.escape_hatches(text)
    if hatches:
        d["hatches"] = hatches
        return _refuse(d, "escape_hatch", f"PROOF.bend uses escape hatches {hatches} (comments included)")
    if bend.declares_law(text):
        return _refuse(d, "declares_law", "PROOF.bend declares a law (comments removed as Bend removes them): a "
                                          "prover has no write access to laws (G3, prover separation)")
    law_rel, proof_rel = look.paths(sub.law_id)
    bad = _import_problem(text, law_rel, proof_rel)
    if bad:
        return _refuse(d, "missing_expected_law", f"at {proof_rel}: {bad}")
    law_d, gen_d = look.g1(sub.law_id)
    d["differs"] = sorted(set(law_d) | set(gen_d))
    if law_d:
        return _refuse(d, "law_file_changed", f"G1: law files differ from their regeneration from the frozen IR: {law_d}")
    if gen_d:
        return _refuse(d, "generated_file_changed", f"G1: the model or core library differs from its regeneration: "
                                                    f"{gen_d}")
    files, no_statement = look.kernel_files(sub.law_id)
    req = [n for n in KERNELS if d["kernels"][n] == "not_run"]
    ko = check_kernels(files, no_statement, proof_rel, sub.proof or b"", req, budget_s, cfg,
                       look.lean_law(sub.law_id) if "lean4" in req else None)
    d["kernels"], d["seconds"], d["_bend2"] = ko.kernels, ko.seconds, ko.bend2
    if ko.reason is not None:
        return _refuse(d, ko.reason, ko.detail)
    d.update(verdict="accepted", reason=None, detail=ko.detail)
    return d


def public(d: dict) -> dict:
    """A decision as printed: without its private keys."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


def attempt(d: dict) -> dict:
    """The attempt `holon run` records for a decision (the record's last attempt)."""
    a = {"kind": "intake", "submission": d["submission"], "prover": d["prover"], "proof_sha256": d["proof_sha256"],
         "verdict": d["verdict"], "reason": d["reason"], "kernels": dict(d["kernels"]), "seconds": d["seconds"]}
    if d["verdict"] != "accepted":
        a["detail"] = d["detail"]
    return a


# ------------------------------------------------------------------ the CLI's view: the committed tree, regenerated
class CommittedLook:
    """For the CLI: the committed records decide eligibility, and G1 is a regeneration of the law's milestone."""

    def __init__(self, tree: Tree, m: str, cfg: dict, tmp: Path, regens: dict):
        self.tree, self.m, self.cfg, self.tmp, self.regens = tree, m, cfg, tmp, regens

    def regen(self) -> Regeneration:
        if self.m not in self.regens:
            self.regens[self.m] = Regeneration(self.m, self.tree, self.cfg, self.tmp / f"regen-{self.m}")
        return self.regens[self.m]

    def paths(self, lid: str) -> tuple[str, str]:
        from .mpipeline import layout
        ld, pd, _ = layout(self.m, Path("gen") / self.m, lid)
        return (ld / "LAWS.bend").as_posix(), (pd / "PROOF.bend").as_posix()

    def g1(self, lid: str) -> tuple[list[str], list[str]]:
        return self.regen().differs(lid)

    def kernel_files(self, lid: str):
        return self.regen().kernel_files(lid)

    def lean_law(self, lid: str):
        from . import facts as F
        law = self.tree.laws(self.m)[lid]
        reg = ir.load_registry(self.m, self.tree.root)
        fp = self.tree.root / law.get("facts", reg["facts"])
        return law, F.load(fp), F.sha256_file(fp)


def decide_inbox(root: Path, inbox: Path, milestone: str | None, only: list[str] | None, budget_s: float) -> list[dict]:
    """The CLI's decisions, sorted by law id (module docstring). Writes nothing under root: the regeneration and every
    kernel run happen in temporary directories, with a fresh build directory."""
    root = Path(root)
    cfg = bend.config(root)
    tree = Tree(root)
    subs = submissions(inbox)
    picked = []
    for sub in subs:
        m = tree.milestone_of(sub.law_id)
        if milestone is not None and m not in (milestone, None):
            continue
        if only is not None and sub.law_id not in only:
            continue
        picked.append((sub, m))
    if only is not None:
        missing = sorted(set(only) - {s.law_id for s, _ in picked})
        if missing:
            raise UsageError(f"--law names submissions that are not in {inbox}"
                             + (f" for milestone {milestone}" if milestone else "") + f": {missing}")
    tmp = Path(tempfile.mkdtemp(prefix="holon-intake-"))
    old = os.environ.get("HOLON_BUILD_DIR")
    os.environ["HOLON_BUILD_DIR"] = str(tmp / "build")   # a fresh build dir: nothing compiled is reused from the tree
    try:
        regens: dict = {}
        out = []
        for sub, m in sorted(picked, key=lambda x: x[0].law_id):
            rec = tree.record(m, sub.law_id) if m else None
            look = CommittedLook(tree, m, cfg, tmp, regens) if m else None
            out.append(public(decide(sub, m, rec, look, budget_s, cfg, root)))
        return out
    finally:
        if old is None:
            os.environ.pop("HOLON_BUILD_DIR", None)
        else:
            os.environ["HOLON_BUILD_DIR"] = old
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ holon run's view: the run's own outcome
class RunLook:
    """For holon run: the files the run has just generated are the regeneration (G1 finds nothing changed), and the
    kernels see exactly the law's model, the core library and its statement."""

    def __init__(self, law_rel: str, proof_rel: str, files: dict[str, bytes], no_statement: str | None):
        self.law_rel, self.proof_rel, self.files, self.no_statement = law_rel, proof_rel, files, no_statement

    def paths(self, lid: str) -> tuple[str, str]:
        return self.law_rel, self.proof_rel

    def g1(self, lid: str) -> tuple[list[str], list[str]]:
        return [], []

    def kernel_files(self, lid: str):
        return dict(self.files), self.no_statement

    def lean_law(self, lid: str):
        return None


def decide_in_run(milestone: str, law_id: str, statement_hash: str, files: dict[str, bytes], law_rel: str,
                  proof_rel: str, no_statement: str | None, cfg: dict, root: Path = ROOT,
                  inbox: Path | None = None) -> tuple[dict, bytes | None] | None:
    """holon run's decision on the submission for a law its generators and refuter left UNKNOWN, or None when the inbox
    holds none. statement_hash is the run's; files are the run's model of the law, its core library and the law's
    statement, at repo-relative gen/<M>/ paths (law_rel, proof_rel: the layout paths). The configured budget applies.
    Returns (decision, the proof's bytes)."""
    root = Path(root)
    p = Path(inbox or root / INBOX) / law_id
    if not os.path.lexists(p):
        return None
    sub = read_submission(p)
    rec = {"status": "UNKNOWN", "statement_hash": statement_hash, "prover": "generator"}
    d = decide(sub, milestone, rec, RunLook(law_rel, proof_rel, files, no_statement), configured_budget(root), cfg, root)
    return d, sub.proof


# ------------------------------------------------------------------ CLI
def _budget(arg: str | None, root: Path) -> float:
    conf = configured_budget(root)
    if arg is None:
        return conf
    try:
        b = float(arg)
    except ValueError:
        raise UsageError(f"--budget-s {arg!r} is not a number") from None
    if not math.isfinite(b) or b <= 0 or b > conf:
        raise UsageError(f"--budget-s {arg} must satisfy 0 < S <= {conf:g} (the configured bend.budget_s_per_file): "
                         "it can only lower the budget")
    return b


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon intake", description="decide agent proofs in proofs/inbox (I41)")
    ap.add_argument("--milestone")
    ap.add_argument("--root")
    ap.add_argument("--inbox")
    ap.add_argument("--law", nargs="+", action="extend", help="decide only these submissions")
    ap.add_argument("--budget-s", help="lower the per-file budget of bend2 for this run (0 < S <= configured)")
    ap.add_argument("--list", action="store_true", help="print the eligible laws (UNKNOWN, or PROVED by an agent)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        budget = _budget(a.budget_s, root)   # before anything is read
        ms = milestones(root)
        if a.milestone is not None and a.milestone not in ms:
            raise UsageError(f"--milestone {a.milestone}: no laws/{a.milestone}/REGISTRY.json under {root}")
        if a.list:
            tree = Tree(root)
            el = {m: tree.eligible(m) for m in ([a.milestone] if a.milestone else ms)}
            if a.json:
                print(json.dumps({"eligible": el}, indent=2, sort_keys=True))
            else:
                for m, ids in el.items():
                    print(f"{m}: {', '.join(ids) if ids else '(none)'}")
            return 0
        if a.inbox is not None:
            inbox = Path(a.inbox)
            inbox = inbox if inbox.is_absolute() else Path.cwd() / inbox
            if not inbox.is_dir():
                raise UsageError(f"--inbox {a.inbox}: not a directory")
        else:
            inbox = root / INBOX
        decisions = decide_inbox(root, inbox, a.milestone, a.law, budget)
    except UsageError as e:
        print(f"holon intake: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({"inbox": _rel(inbox, root), "budget_s": budget, "decisions": decisions}, indent=2,
                         sort_keys=True))
    else:
        print(f"inbox {_rel(inbox, root)}, budget {budget:g} s per file, {len(decisions)} submission(s)")
        for d in decisions:
            ks = ", ".join(f"{k} {v}" for k, v in d["kernels"].items() if v != "not_applicable")
            print(f"  {d['law_id']} ({d['milestone'] or 'no milestone'}): {d['verdict'].upper()}"
                  + (f" [{d['reason']}]" if d["reason"] else "") + f"; kernels: {ks}")
            for line in d["detail"].splitlines()[:6]:
                print(f"      {line}")
    return 0 if all(d["verdict"] == "accepted" for d in decisions) else 1


if __name__ == "__main__":
    sys.exit(main())
