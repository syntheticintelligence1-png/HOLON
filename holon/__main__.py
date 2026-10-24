"""holon CLI.

  python -m holon run  --milestone M0 [--facts PATH] [--out DIR] [--gen-dir DIR] [--no-registry] [--core import|paste]
                       [--laws ID,ID]   (M1+: decide only those laws; I15)
  python -m holon gate --milestone M0 [--root DIR] [--report PATH] [--checks G6,G9]
  python -m holon contracts derive|apply --milestone M [--root DIR] [--check]   (intent contracts, K3 and K5; I64)
  python -m holon audit prereg --milestone M2 [--root DIR]
  python -m holon audit status [--json] [--root DIR]
  python -m holon audit regress --from A --to B [--json] [--root DIR]
  python -m holon audit hostile --milestone M2 --round 2 [--surface S ..] [--checkout PATH] [--snapshot DIR] [--check]
  python -m holon audit vacuity --milestone M2 --round 2 [--out FILE] [--check]   (auditors A2 and A4, round M2/2; I21)
  python -m holon bind --milestone M1 [--accept-change REASON]
  python -m holon oracle zero-blob [--morph PATH]
  python -m holon oracle check --milestone M2 [--root DIR]   (oracle sidecar hypotheses: A4, G11V; I12)
  python -m holon checker-upgrade --to FINGERPRINT [--bend-cmd CMD] [--milestones M0,M1] [--out PATH]
  python -m holon replay [--milestone M] [--morph PATH] [--forge F] [--solc S] [--work DIR] [--write-pins]
  python -m holon lean --milestone M0 [--json] [--jobs N]   (Lean 4 second kernel, I9)
  python -m holon theory2 --milestone M3 [--root DIR] [--out DIR] [--kernels] [--check]   (theory core II, I43)
  python -m holon layout FN VERSION [--facts PATH]      (layout algebra, for humans)
  python -m holon diagram --milestone M2 [--out DIR] [--root DIR]   (one diagram per fact document)
  python -m holon sorts [--milestone M2] [--root DIR] [--out DIR] [--facts PATH ...]   (refined sorts, I13)
  python -m holon derive --milestone M2 [--root DIR] [--out DIR] [--obstructions PATH] [--facts PATH ...]
                         [--assignment PATH] [--against DIR --diff PATH]   (rules registry: laws/<M>/, I15; then
                                                        the milestone's contract laws, listed in its registry: I65)
  python -m holon native --milestone M0 [--out PATH]    (native C model, results/M2/native.json, I16)
  python -m holon evidence [--milestone M2] [--root DIR] [--out PATH]   (evidence set E1-E6, gen/M2/evidence.json, I14)
  python -m holon refine --milestone M0 [--edges E1,E2] [--out DIR] [--morph PATH] [--work DIR] [--fix C ..]
  python -m holon metrics --milestone M [--root DIR]    (results/<M>/metrics.json, I16)
  python -m holon extract <frontend> ...                (fact extraction, holon-facts/0.3; I17 solidity, I18 go)
  python -m holon extract solidity [--milestone M2] [--sidecar PATH] [--root DIR] [--source DIR] [--out PATH] [--check]
  python -m holon coverage --milestone M2 [--root DIR] [--out PATH] [--check]   (gen/M2/coverage.json, G8; I19)
  python -m holon link --milestone M2 [--root DIR] [--out PATH] [--check]       (gen/M2/link.json; I19)
  python -m holon historical fetch [--milestone M2] [--from N] [--to M] [--index PATH] [--snapshot DIR]
  python -m holon historical replay [--milestone M2] [--index PATH] [--out PATH]   (on-chain history, I59)
  python -m holon historical fetch-state|codec|trans|laws|smoke|exit [--milestone M2] ...   (M2 exit evaluation, I23)
  python -m holon model --facts <transitions document> --out DIR   (the extracted model: model.bend, layout.json,
                                                                    window_check.json; holon.machine, I20)
  python -m holon differential --milestone M2 [--root DIR]  (the M1 laws on the extracted model through the window
                                                             view: gen/M2/abstraction_diff.json,
                                                             results/M2/differential.json; I20)
  python -m holon fragments [--facts DOC] [--binding PATH] [--out PATH] ...   (extracted refinement, I20)
  python -m holon hevm [--out PATH]                     (optional hevm equivalence, results/M2/hevm.json; I20)
  python -m holon intake [--milestone M] [--root DIR] [--inbox DIR] [--law ID ...] [--budget-s S] [--json]
  python -m holon intake --list [--milestone M] [--root DIR] [--json]   (the untrusted prover intake, I41)
  python -m holon codecs --milestone M3 [--root DIR] [--adoption PATH] [--link PATH] [--out DIR] [--check]
                                                        (the linked codec documents gen/<M>/codec/<role>.json; I24)
  python -m holon backtest --milestone M3 [--root DIR] [--out PATH]
                                                        (the back-test across documents, results/M3/backtest.json; I24)
  python -m holon profile --milestone T32 [--root DIR]   (discharge profiles, DISCH II, I32)
  python -m holon lossy --milestone M3 [--root DIR] [--out DIR] [--review PATH] [--records DIR] [--codec PATH ...]
                        [--gen-dir DIR] [--check]       (PAR-lossy and injective pushing: gen/<M>/par_lossy/,
                                                        spec/<M>/evidence_review.jsonl; I25)
  python -m holon refute --milestone M [--root DIR] [--sidecar PATH] [--only STAGE,..] [--check] [--results DIR]
                         [--gen-dir DIR] [--laws ID,..]   (the refutation engines, concretization, filter; I40)
  python -m holon eval <command> ...                   (I48: the evaluation corpus, the renaming tool and the
                                                        controls; holon.eval.cli lists the commands)
  python -m holon mutate list|sheet|project|replay|gate|run|rate ...   (I61: A1 mutation adequacy on real code;
                                                        holon.mutate.cli lists the commands)
  python -m holon basis --milestone M3 [--root DIR] [--out DIR] [--kernels] [--check]
                                                        (the theory core and basis sufficiency by application:
                                                        gen/<M>/theory/; I42)
  python -m holon versions extract|model|analyze|inhabit|replay [--check]   (versioned machines over the deployment
                                                        history, PAR-init and the in-flight inhabitants; I28)
  python -m holon types|termsize|model|run|replay --milestone M3 ...   (typed milestones, M3+ and T30+: I30's
                                                        holon.sorts; `run --laws` naming only laws outside I30's typed
                                                        SORT subforms, I24's PAR laws on M3, runs holon.pipeline)
"""
from __future__ import annotations

import argparse
import json
import sys


def _typed_milestone(argv: list) -> bool:
    """Does the command name a milestone typed by I30's rules: M3 and later, or a test milestone T<n> with n >= 30 that
    names its typed-sorts sidecar (--sidecar), as I30's contract has every typed test milestone do? A test milestone
    without one is not I30's (I41's T41 and the T46/T47 canary fixtures are state-machine milestones), so the
    milestone's runners keep it (merge of I24, I41 and I30)."""
    from .sorts.typed_sidecar import typed
    for i, x in enumerate(argv):
        m = argv[i + 1] if x == "--milestone" and i + 1 < len(argv) else \
            x.split("=", 1)[1] if x.startswith("--milestone=") else None
        if m is not None:
            return typed(m) and (m.startswith("M") or any(a == "--sidecar" or a.startswith("--sidecar=")
                                                           for a in argv))
    return False


def _arg(argv: list, name: str) -> str | None:
    for i, x in enumerate(argv):
        if x == name and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(name + "="):
            return x.split("=", 1)[1]
    return None


def _untyped_laws(argv: list) -> bool:
    """`holon run --milestone M --laws ID,..` on a typed milestone naming only laws that are not I30's (no SORT
    realize, as_member or reinterpret entry in laws/<M>/DERIVATION.json; on M3, I24's PAR laws): the milestone runner
    (holon.pipeline, as at I24) decides them. Every other run or replay of a typed milestone is I30's (holon.sorts.run3),
    which decides the I30 laws only."""
    from pathlib import Path
    m, laws = _arg(argv, "--milestone"), _arg(argv, "--laws")
    ids = [x.strip() for x in (laws or "").split(",") if x.strip()]
    if argv[:1] != ["run"] or not m or not ids:
        return False
    try:
        dv = json.loads((Path(__file__).resolve().parents[1] / "laws" / m / "DERIVATION.json").read_text())
    except (OSError, ValueError):
        return False
    entries = {e.get("law_id"): e for e in dv.get("laws") or [] if isinstance(e, dict)}
    typed_subforms = ("as_member", "realize", "reinterpret")
    # rules UNDO (I27) and FACT (I26) are decided on the typed model too (holon.undo.run, holon.fact.run)
    return all(i in entries and not (entries[i].get("rule") == "SORT" and entries[i].get("subform") in typed_subforms)
               and entries[i].get("rule") not in ("UNDO", "FACT") for i in ids)


def _disch_milestone(argv: list) -> bool:
    """Does the milestone derive DISCH laws (I31: a DISCH entry in laws/<M>/DERIVATION.json)?"""
    from pathlib import Path
    m = _arg(argv, "--milestone")
    try:
        dv = json.loads((Path(__file__).resolve().parents[1] / "laws" / str(m) / "DERIVATION.json").read_text())
    except (OSError, ValueError):
        return False
    return any(isinstance(e, dict) and e.get("rule") == "DISCH" for e in dv.get("laws") or [])


def _typed_run(argv: list) -> int | None:
    """`holon run | replay` of a typed milestone's laws other than FACT, or None when holon.pipeline decides them (a
    --laws list naming only laws that are not typed)."""
    if _disch_milestone(argv):
        # I31: the DISCH laws of a typed milestone (holon.disch.run, after I30's laws for a whole-milestone run); a
        # --laws list that names other laws too sends those on as before
        from .disch import run as disch_run
        split = disch_run.disch_ids_of(argv)
        if split is None:
            return disch_run.main(argv)
        dids, others = split
        if dids:
            rc = 0
            if others:
                rc = _main(disch_run.strip_args(argv, ("--laws", "--disch")) + ["--laws", ",".join(others)])
            return max(rc, disch_run.main(disch_run.strip_args(argv, ("--laws",)) + ["--laws", ",".join(dids)]))
    if not _untyped_laws(argv):
        # the I30 laws of a typed milestone (holon.sorts.run3) and its UNDO laws (I27, holon.undo.run): run, replay
        from .undo import run as undo_run
        return undo_run.main(argv)
    return None


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    rc = _main(argv)
    if rc == 0 and argv[:1] == ["run"]:   # K5 (I64): the run's last step applies the milestone's intent contracts
        from . import contracts
        rc = contracts.after_run(argv)
    return rc


def _main(argv: list) -> int:
    if argv[:1] == ["contracts"]:  # its flags go to holon.contracts unparsed (I64: intent contracts, K3 and K5)
        from . import contracts
        return contracts.main(argv[1:])
    if argv[:1] == ["checker-upgrade"]:  # its flags go to holon.checker_upgrade unparsed
        from . import checker_upgrade
        return checker_upgrade.main(argv[1:])
    if argv[:1] == ["mutate"]:  # likewise for holon.mutate.cli (I61: A1 mutation adequacy on real code)
        from .mutate import cli as mutate_cli
        return mutate_cli.main(argv[1:])
    if argv[:1] == ["eval"]:  # likewise for holon.eval.cli (I48)
        from .eval import cli as eval_cli
        return eval_cli.main(argv[1:])
    if argv[:1] == ["lean"]:  # likewise for holon.lean
        from . import lean
        return lean.main(argv[1:])
    if argv[:1] == ["refute"]:  # likewise for holon.refute3 (the refutation engines, I40)
        from . import refute3
        return refute3.main(argv[1:])
    if argv[:1] == ["sorts"]:  # likewise for holon.sorts
        from . import sorts
        return sorts.main(argv[1:])
    if argv[:1] == ["derive"]:  # likewise for holon.rules (the rules registry, I15), then the milestone's contract laws
        from . import contracts, rules   # (I65 rule O4: holon.contracts, which no generator closure imports)
        rc = contracts.before_derive(argv)
        if rc == 0:
            rc = rules.main(argv[1:])
        return contracts.after_derive(argv) if rc == 0 else rc
    if argv[:1] == ["native"]:  # likewise for holon.model_native
        from . import model_native
        return model_native.main(argv[1:])
    if argv[:1] == ["evidence"]:  # likewise for holon.diagram.evidence (I14)
        from .diagram import evidence
        return evidence.main(argv[1:])
    if argv[:1] == ["extract"]:  # likewise for holon.frontends (the frontend named by the next argument, I17)
        from . import frontends
        return frontends.main(argv[1:])
    if argv[:1] == ["coverage"]:  # likewise for holon.coverage (I19)
        from . import coverage
        return coverage.main(argv[1:])
    if argv[:1] == ["link"]:  # likewise for holon.frontends.link (I19)
        from .frontends import link
        return link.main(argv[1:])
    if argv[:1] == ["historical"]:  # likewise for holon.historical (fetch | replay, I59)
        from . import historical
        return historical.main(argv[1:])
    if argv[:1] == ["versions"]:  # likewise for holon.versions (versioned machines, I28: rules V1-V9, PI1-PI6)
        from . import versions
        return versions.main(argv[1:])
    if argv[:1] == ["history"]:  # likewise for holon.frontends.solidity.history (deployment history, I63)
        from .frontends.solidity import history
        return history.main(argv[1:])
    if argv[:1] == ["theory2"]:  # likewise for holon.gen.theory2 (theory core II, I43)
        from .gen import theory2
        return theory2.main(argv[1:])
    if argv[:1] == ["differential"]:  # likewise for holon.differential (I20)
        from . import differential
        return differential.main(argv[1:])
    if argv[:1] == ["fragments"]:  # likewise for holon.replay_fragments (I20)
        from . import replay_fragments
        return replay_fragments.main(argv[1:])
    if argv[:1] == ["hevm"]:  # likewise for holon.hevm_equiv (I20, optional)
        from . import hevm_equiv
        return hevm_equiv.main(argv[1:])
    if argv[:1] == ["intake"]:  # likewise for holon.intake (the untrusted prover intake, I41)
        from . import intake
        return intake.main(argv[1:])
    if argv[:1] == ["codecs"]:  # likewise for holon.diagram.linked (the linked codec layer, I24)
        from .diagram import linked
        return linked.main(argv[1:])
    if argv[:1] == ["profile"]:  # likewise for holon.profile (discharge profiles, DISCH II, I32)
        from . import profile
        return profile.main(argv[1:])
    if argv[:1] == ["backtest"]:  # likewise for holon.backtest (the back-test across documents, I24)
        from . import backtest
        return backtest.main(argv[1:])
    if argv[:1] == ["lossy"]:  # likewise for holon.rules.par_lossy (PAR-lossy and injective pushing, I25)
        from .rules import par_lossy
        return par_lossy.main(argv[1:])
    if argv[:1] == ["basis"]:  # likewise for holon.gen.basis (the theory core and basis sufficiency, I42)
        from .gen import basis
        return basis.main(argv[1:])
    if argv[:1] == ["disch"]:  # likewise for holon.analysis.closure (I31: DISCH I, the enableable write closure)
        from .analysis import closure
        return closure.main(argv[1:])
    if argv[:1] == ["fact"]:  # likewise for holon.rules.fact (I26: commitments, consumers, pins, F(m, c))
        from .rules import fact
        return fact.main(argv[1:])
    if argv[:1] == ["undo"]:  # likewise for holon.rules.undo (I27: undo pairs, residues, static deadness)
        from .rules import undo
        return undo.main(argv[1:])
    if argv[:1] == ["types"]:  # likewise for holon.sorts.types3 (I30: nominal types and the ghost-taint check)
        from .sorts import types3
        return types3.main(argv[1:])
    if argv[:1] == ["termsize"]:  # likewise for holon.sorts.termsize (I30)
        from .sorts import termsize
        return termsize.main(argv[1:])
    if argv[:1] == ["model"] and "--facts" not in argv and _typed_milestone(argv):
        from .sorts import model3   # the M3 model of a typed milestone's documents (I30)
        return model3.main(argv[1:])
    if argv[:1] == ["run"] and _typed_milestone(argv):
        # I28: the PAR-init laws (rule PAR, sub-form init_chain) a --laws list names are decided over the versioned
        # model (holon.versions.run); the list's other laws go on as before
        from .versions import run as versions_run
        split = versions_run.ids_of(argv)
        if split is not None:
            vids, others = split
            rc = 0
            if others:
                rc = _main(versions_run.strip_args(argv, ("--laws",)) + ["--laws", ",".join(others)])
            return max(rc, versions_run.main(versions_run.strip_args(argv, ("--laws",)) + ["--laws", ",".join(vids)]))
    if argv[:1] in (["run"], ["replay"]) and _typed_milestone(argv):
        from .fact import run as fact_run
        if fact_run.has_fact_laws(argv):
            # I26: the FACT laws of a typed milestone (holon.fact.run, after every other law of a whole-milestone run
            # or replay); a --laws list that names other laws too sends those on as before
            split = fact_run.fact_ids_of(argv)
            base = fact_run.strip_args(argv, ("--fact-sidecar",))
            if split is None:
                rc = _typed_run(base)
                return max(0 if rc is None else rc, fact_run.main(argv))
            fids, others = split
            if fids:
                rc = 0
                if others:
                    rc = _main(fact_run.strip_args(base, ("--laws",)) + ["--laws", ",".join(others)])
                return max(rc, fact_run.main(fact_run.strip_args(argv, ("--laws",)) + ["--laws", ",".join(fids)]))
        rc = _typed_run(argv)
        if rc is not None:
            return rc
    ap = argparse.ArgumentParser(prog="holon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="drive every frozen law to PROVED / REFUTED / UNKNOWN")
    r.add_argument("--milestone", default="M0")
    r.add_argument("--facts")
    r.add_argument("--out")
    r.add_argument("--gen-dir")
    r.add_argument("--no-registry", action="store_true")
    r.add_argument("--core", choices=["import", "paste"], default="import",
                   help="M2+ milestones: import the core library (default) or paste it into each proof (baseline)")
    r.add_argument("--laws", help="comma-separated law ids: decide only those laws (the registry is still checked whole; "
                                  "state-machine milestones)")
    g = sub.add_parser("gate", help="re-check everything from scratch (G1-G5, G7, G11, GENV, canaries)")
    g.add_argument("--milestone", default="M0")
    g.add_argument("--root")
    g.add_argument("--report")
    g.add_argument("--checks", help="comma-separated subset to run after GENV (the report is marked partial)")
    bd = sub.add_parser("bind", help="bind each law to the kernel form of the definitions it reaches (spec/bindings)")
    bd.add_argument("--milestone", default="M0")
    bd.add_argument("--root")
    bd.add_argument("--accept-change", help="reason for changing an existing binding (logged in spec/bindings/changes.jsonl)")
    bd.add_argument("--laws", help="comma-separated law ids: (re)bind only these; every other law keeps its binding "
                                   "(or stays unbound)")
    orc = sub.add_parser("oracle", help="oracle checks: `oracle zero-blob --morph PATH` (D2), `oracle check --milestone M2` "
                                        "(the oracle sidecar's hypotheses, I12); both write results/M2/hypotheses.json")
    orc.add_argument("which", choices=["zero-blob", "check"])
    orc.add_argument("rest", nargs=argparse.REMAINDER)
    cu = sub.add_parser("checker-upgrade", help="re-run gates and runs under a candidate checker; report every diff")
    cu.add_argument("rest", nargs=argparse.REMAINDER)
    au = sub.add_parser("audit", help="audits: `audit prereg --milestone M2` checks preregistration order; "
                                      "`audit status` summarises the adversarial audit findings; "
                                      "`audit regress --from A --to B` reports statement-hash changes and when each "
                                      "law, result and prediction was first committed (A3); "
                                      "`audit hostile|vacuity --milestone M2 --round 2 [--check]` are auditors A2 "
                                      "and A4 of audit round M2/2 (I21)")
    au.add_argument("what", choices=["prereg", "status", "regress", "hostile", "vacuity"])
    au.add_argument("rest", nargs=argparse.REMAINDER)
    rp = sub.add_parser("replay", help="replay REFUTED witnesses on the real Go and Solidity code")
    rp.add_argument("--milestone", default="M0")
    rp.add_argument("--morph", help="morph-l2/morph checkout at the facts' commit (default: config replay.morph)")
    rp.add_argument("--forge", help="forge binary (default: config replay.forge); its sha256 must match the pin")
    rp.add_argument("--solc", help="solc 0.8.24 binary for forge --use (default: config replay.solc), pinned likewise")
    rp.add_argument("--work")
    rp.add_argument("--corpus", type=int, default=300, help="M1: random refinement traces (seeded)")
    rp.add_argument("--write-pins", action="store_true",
                    help="write the toolchain's current sha256 values into config/holon.json replay.* (a human "
                         "should review that change); without it, a missing or different pin refuses to run")
    ln = sub.add_parser("lean", help="Lean 4 second kernel (M0): regenerate gen/<m>/lean and check every file")
    ln.add_argument("rest", nargs=argparse.REMAINDER)
    lay = sub.add_parser("layout", help="print the symbolic byte layout of an encoder")
    lay.add_argument("fn")
    lay.add_argument("version", type=int)
    lay.add_argument("--facts", default="facts/morph_header.json")
    dg = sub.add_parser("diagram", help="build the protocol diagram of every fact document (gen/<M>/diagram)")
    dg.add_argument("--milestone", default="M2")
    dg.add_argument("--out", help="output directory (default: <root>/gen/<milestone>/diagram)")
    dg.add_argument("--root", help="repository root holding the fact documents (default: this checkout)")
    nt = sub.add_parser("native", help="build the native C model and record results/M2/native.json (I16)")
    nt.add_argument("rest", nargs=argparse.REMAINDER)
    rf = sub.add_parser("refine", help="per-edge refinement records against each edge's own implementation (I16)")
    rf.add_argument("--milestone", default="M0")
    rf.add_argument("--edges", help="comma-separated subset of the refined edges (default: all, plus cross_edge.json "
                                    "and spec/M2/disagreements.json)")
    rf.add_argument("--out", help="output directory for the records (default: results/M2/refinement)")
    rf.add_argument("--morph", help="morph checkout at the facts' commit (default: config replay.morph)")
    rf.add_argument("--work", help="scratch directory for the harness workspaces (default: a temporary directory)")
    rf.add_argument("--fix", action="append", help="a fix commit (40 lowercase hex) this run measures; repeatable")
    md = sub.add_parser("model", help="build and check the model a milestone compiles a fact document to (M2+: "
                                      "Reach, guard-derived permissions, the milestone's oracle parameters)")
    md.add_argument("--milestone", default="M2")
    md.add_argument("--facts", required=True, help="the fact document (repo-relative)")
    md.add_argument("--out", help="directory to write <model>.bend into (default: print the build path only)")
    md.add_argument("--source", help="a transitions document's source tree, when the configuration names none for "
                                     "its target (holon.machine; a planted fixture)")
    mt = sub.add_parser("metrics", help="write results/<M>/metrics.json and metrics_timing.json (I16)")
    mt.add_argument("--milestone", default="M0")
    mt.add_argument("--root")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        from .pipeline import main_run
        return main_run(a)
    if a.cmd == "gate":
        from .gate import main_gate
        return main_gate(a)
    if a.cmd == "bind":
        from .bindings import main_bind
        return main_bind(a)
    if a.cmd == "oracle":
        if a.which == "check":
            from . import oracle_check
            return oracle_check.main(a.rest)
        from .oracles import zero_blob
        return zero_blob.main(a.rest)
    if a.cmd == "checker-upgrade":
        from . import checker_upgrade
        return checker_upgrade.main(a.rest)
    if a.cmd == "audit":
        if a.what == "status":
            from .audit import status
            return status.main(a.rest)
        if a.what == "regress":
            from .audit import regress
            return regress.main(a.rest)
        if a.what == "hostile":
            from .audit import hostile
            return hostile.main(a.rest)
        if a.what == "vacuity":
            from .audit import vacuity
            return vacuity.main(a.rest)
        from .audit import prereg
        return prereg.main(a.rest)
    if a.cmd == "replay":
        from .replay import main_replay
        return main_replay(a)
    if a.cmd == "refine":
        from .refinement import main_refine
        return main_refine(a)
    if a.cmd == "metrics":
        from .metrics import main_metrics
        return main_metrics(a)
    if a.cmd == "model":
        from .mpipeline import main_model
        return main_model(a)
    if a.cmd == "diagram":
        from . import diagram
        return diagram.run(a.milestone, a.out, a.root)
    if a.cmd == "layout":
        from . import facts, layout
        for i, c in enumerate(layout.layout(facts.load(a.facts), a.fn, a.version)):
            print(i, json.dumps(c))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
