"""Round 8 (M3), auditor A4: representative search for a degenerate (D1) inhabitant, with the law's own inhabitant
generator and both kernels.

    cd <scratch tree of the target> && PYTHONPATH=. python <this file> sym|disch|disch0 <law id>

Run it only in a scratch tree of the target commit (it runs `holon run --milestone M3 --laws <id>` there, which
rewrites that tree's record and gen/ files). The law is decided exactly as `holon run` decides it; only the G11V
inhabitant search is narrowed, so that the inhabitant it emits cannot be degenerate by rule D1 (the inhabitant's state
is the initial state):
  sym    holon.symd.run's inhabitant search (holon.undo.search.UndoSearch.over_prefixes, through
         holon.symd.search.SymSearch.inhabitant) skips the empty prefix: the inhabitant's state is reached by at least
         one successful step;
  disch  holon.disch.search.LawSearch.inhabit skips the B-states reached by no step and accepts only a step that
         succeeds (code 0), so the inhabitant is neither the initial state nor a reverting step (for a blocking law:
         a step of the class's closure that runs and keeps B);
  disch0 the same, without the success condition (for a revert law, whose claim is that the step reverts).
The inhabitant is then emitted and checked by the generator's own code (holon.symd.proofs / holon.disch.run.emit) with
bend2 and BendTT, as for any record. Afterwards this script prints the record's non_vacuity entry and re-checks the
emitted nonvac PROOF.bend from scratch with `bend` and `bend --verdict`.
"""
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path


def patch_sym():
    from holon.undo import search as US
    orig = US.UndoSearch.over_prefixes

    def over_prefixes(self, entry, at):
        def at_nonempty(trace, g):
            return None if not trace else at(trace, g)
        return orig(self, entry, at_nonempty)
    US.UndoSearch.over_prefixes = over_prefixes


def patch_disch(require_ok: bool = True):
    from holon.disch import search as DS

    def inhabit(self, max_states=None):
        n = 0
        for trace, g, t in self.candidates():
            if not trace:
                continue
            if max_states is not None and n >= max_states:
                return None
            n += 1
            for a in self.entries:
                if self.out_of_time():
                    return None
                self.tries += 1

                def acc(st, code, g=g, t=t):
                    return (code == 0 or not require_ok) and int(st.env.get("block.timestamp") or 0) >= t and \
                        self.judge.premise(self.m, self.law, g, st, t)
                st = self.synth(g, trace, t, a, acc)
                if st is not None:
                    return trace + [st], t
        return None
    DS.LawSearch.inhabit = inhabit

    def neighbourhood(self, seeds, deadline=None, inhabit=False):   # the S3 fallback is not narrowed: switch it off
        self.s3 = {"seeds": [], "prefixes": 0, "max": 0, "insert": 0, "timebox": False, "bstates": 0, "tries": 0}
        return None
    orig_nb = DS.LawSearch.neighbourhood

    def nb(self, seeds, deadline=None, inhabit=False):
        return neighbourhood(self, seeds, deadline, inhabit) if inhabit else orig_nb(self, seeds, deadline, inhabit)
    DS.LawSearch.neighbourhood = nb


def main():
    mode, lid = sys.argv[1], sys.argv[2]
    {"sym": patch_sym, "disch": patch_disch, "disch0": lambda: patch_disch(False)}[mode]()
    sys.argv = ["holon", "run", "--milestone", "M3", "--laws", lid]
    try:
        runpy.run_module("holon", run_name="__main__", alter_sys=True)
    except SystemExit as e:
        print(f"a4_rep: holon run exited {e.code}")
    rec = json.loads(Path(f"results/M3/{lid}.json").read_text())
    nv = rec.get("non_vacuity") or {}
    w = nv.get("witness") or {}
    print("a4_rep: status", rec.get("status"))
    print("a4_rep: non_vacuity", json.dumps({k: nv.get(k) for k in ("status", "bound", "degenerate", "law")}))
    steps = w.get("steps") if isinstance(w.get("steps"), list) else None
    prefix = w.get("prefix") if isinstance(w.get("prefix"), list) else None
    print("a4_rep: witness steps", None if steps is None else [s.get("action") for s in steps],
          "prefix", None if prefix is None else [p.get("action") if isinstance(p, dict) else p for p in prefix],
          "x", (w.get("x") or {}).get("action") if isinstance(w.get("x"), dict) else None)
    if nv.get("law"):
        d = Path(nv["law"]).parent
        for extra in ([], ["--verdict"]):
            p = subprocess.run(["bend", "PROOF.bend", *extra], cwd=d, capture_output=True, text=True,
                               env=dict(os.environ, BEND_NO_TELEMETRY="1"))
            print(f"a4_rep: bend PROOF.bend {' '.join(extra)} -> exit {p.returncode}, "
                  f"{(p.stdout.strip().splitlines() or [''])[0]}")


if __name__ == "__main__":
    main()
