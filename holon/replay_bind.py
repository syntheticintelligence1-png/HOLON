"""One rule for G6 and the final filter (I98): G6's judgement of every REFUTED record of a milestone's results.

A REFUTED record stands only on a passed replay that G6 binds to it, and that replay must observe the record's
obstruction on the real code (the lead's I98 rulings). This module holds that judgement, clause by clause. The gates
report it as G6: holon.sorts.gate3 for the typed I30 entries, UNDO, NAT and the other laws, and the families' gates
joined to it for DISCH, FACT, the contract laws and the bundle laws. The final filter (holon.refute_m3.concretize)
reads it through binding(...). It imports no gate, so a module that imports it takes in this module and the replay
readers it needs, not the gates (the lead's I98 ruling on the generator closure).

What each clause's replay observes (a record judged by several clauses is observed by each, or it is not bound):
  typed (I30)    the entry's obstruction_observed (holon.sorts.run3.replay_entry: a realize entry observes the real
                 panic in its span; an as_member or a reinterpret entry observes nothing);
  UNDO           the real runs with and without x;y diverge at t[diverges_at], where the model's do;
  DISCH          blocked_before and discharged_after, on the real storage;
  FACT, bundle   the replay's pass rule reads the obstruction on the real code (holon.fact.run,
                 holon.bundle.replay_laws, holon.bundle2.laws_replay);
  contract       the record's replay passed;
  NAT, PAR-init  the side's obstruction_observed (holon.rules.nat_replay.side, holon.versions.replay.side);
  go             every side's obstruction_observed (replay/<M>/{own,gocount,goops,par}/report.json);
  gox, symb      verdict agree, agree: the real code's results differ as the counter-law states;
  sym            nothing: its replay compares the deployment's outcomes with the model's and evaluates the claim on
                 the model with the deployment's call answers (holon.symd.run), reading no word of the real state;
  I40            every side of replay/<M>/refute/report.json passed with obstruction_observed.
A record whose replay passes without observing its obstruction is refused with UNOBSERVED, the reason the final filter
puts first in its bound (a later key re-binds such records on it).

GHOST_ONLY, the one exception, family-level and mechanical (ghost_only below): a record whose obstruction is stated
over ghost state alone binds on calls agreeing, a passed replay. It is decided from the law's IR: the claim, with the
coercion it applies expanded to its terms in laws/<M>/DERIVATION.json (its member function and its read). The violated
predicate names only generated ghost fields when none of those terms reads the code's state or inputs. A claim applying
any other definition compares the code's state by its family's definition. G6's detail names the rule and counts it.

A30: the A30 review's note at G6's typed clause said a replay that disagrees with its witness is "flagged here, never
absorbed into the status". The lead's I98 ruling supersedes "never absorbed into the status": G6's refusal moves the
status through the final filter.

The collection. judged(law) and refuse(law, why) report a judgment to every active collection (outside one they only
return): the clauses here, the two that live with their family (holon.rules.nat_replay.g6, holon.versions.replay.g6),
and the derivation law set's gate, whose records are not the milestone's results.

binding(milestone, root) runs every clause here inside a collection and returns (unbound, examined, G6's result) over
the records that are REFUTED at root:
  unbound   {law: [why]}, the records a clause refused;
  examined  [law], the records some clause judged.
It raises RuntimeError when the milestone cannot be judged (its derivation document is unreadable). A caller never reads
"nothing refused" from a judgement that did not run.

The final filter takes every unbound record out of REFUTED. The record becomes UNKNOWN, with G6's refusal as its bound
and an attempt that keeps the witness, the replay and the counter-law Bend accepted. So a record the filter leaves
REFUTED is one G6 binds, and G6 fails exactly when this rule would move a record.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

_ACTIVE: list = []

UNOBSERVED = "model-level counter-law accepted; obstruction not observed on the deployment"
# The term heads of a DERIVATION entry that read the code's state or inputs. The named ones are named by their head
# and argument; a map or an index is named through the storage or the parameter it reads.
CODE_HEADS = ("storage", "map", "index", "param", "caller", "env", "call", "outflow")
# The definitions a law's claim can apply: a coercion is expanded from its DERIVATION entry; every other one compares
# the code's state by its family's definition.
DEFINITIONS = ("coerce", "sym", "disch", "undo", "fact", "bundle", "symb", "square", "wnat", "own", "gox", "init")
# The parts of a claim that name nothing of the code: its binders, constants and equality, and a coercion's arguments.
CLAIM_PLAIN = ("eq", "bool", "var", "from", "on", "coerce")

# The replays of the laws no other clause judges, in the order the other-laws clause tries them: (kind, the report path
# under replay/<M>/, the report's layout). A law is judged by the first that names it.
OTHER_REPLAYS = (("go", "own/report.json", "laws"), ("go", "gocount/report.json", "laws"),
                 ("go", "goops/report.json", "laws"), ("go", "par/report.json", "laws"),
                 ("gox", "gox/{law}.json", "file"),
                 ("symb", "symb/{law}.json", "file"), ("sym", "sym/report.json", "laws"),
                 ("I40", "refute/report.json", "records"))
NAMED = 8   # the refusals a detail gives in full; every other refused law is still named, by id


class _Collection:
    def __init__(self):
        self.judged: set = set()
        self.refused: dict = {}


def judged(law: str) -> None:
    for c in _ACTIVE:
        c.judged.add(law)


def refuse(law: str, why: str) -> str:
    for c in _ACTIVE:
        c.judged.add(law)
        c.refused.setdefault(law, []).append(why)
    return why


def _res(ok: bool, detail: str) -> dict:
    return {"passed": bool(ok), "detail": detail}


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).is_file() else None
    except (OSError, ValueError):
        return None


def _status(p: Path):
    d = _load(p)
    return d.get("status") if isinstance(d, dict) else None


def _named(bad: list, laws: list) -> str:
    """The first NAMED refusals in full, then every other refused law by id (bad[i] is laws[i]'s refusal)."""
    rest = sorted(set(laws[NAMED:]) - set(laws[:NAMED]))
    return "; ".join(bad[:NAMED]) + (f"; also refused: {', '.join(rest)}" if rest else "")


# ------------------------------------------------------------------------------------------------ GHOST_ONLY
def _term_names(t, out: set) -> None:
    if isinstance(t, list) and t and isinstance(t[0], str):
        h = t[0]
        if h in ("storage", "param", "env") and len(t) > 1 and isinstance(t[1], str):
            out.add(f"{h} {t[1]}")
        elif h in ("caller", "outflow"):
            out.add(h)
        elif h == "call":
            out.add("call" + (f" {t[1]}" if len(t) > 1 and isinstance(t[1], str) else ""))
        for x in t[1:]:
            _term_names(x, out)
    elif isinstance(t, list):
        for x in t:
            _term_names(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            _term_names(x, out)


def _claim_keys(t, out: set) -> None:
    if isinstance(t, dict):
        out |= set(t)
        for x in t.values():
            _claim_keys(x, out)
    elif isinstance(t, list):
        for x in t:
            _claim_keys(x, out)


def ghost_only(law: dict | None, entry: dict | None) -> tuple[bool, list]:
    """GHOST_ONLY, decided from the law's IR: (True, []) when the violated predicate names only generated ghost fields,
    else (False, the code-observable terms it names). The predicate is the law's claim with the coercion it applies
    expanded to its DERIVATION entry's member function and read. A claim applying any other definition, or naming
    anything beyond its binders, constants and the coercion, is not ghost-only."""
    claim = ((law or {}).get("statement") or {}).get("claim")
    keys: set = set()
    _claim_keys(claim, keys)
    defs = sorted(k for k in keys if k in DEFINITIONS)
    if defs != ["coerce"]:
        return False, [f"the {d} definition" for d in defs if d != "coerce"] or ["a claim that applies no coercion"]
    extra = sorted(k for k in keys if k not in CLAIM_PLAIN)
    if extra:
        return False, extra
    if not isinstance(entry, dict) or not isinstance(entry.get("coercion"), dict):
        return False, ["a coercion with no DERIVATION entry"]
    names: set = set()
    _term_names(entry["coercion"].get("member_fn"), names)
    _term_names((entry.get("basis") or {}).get("read"), names)
    return (not names), sorted(names)


class Ctx:
    """One judgement of a milestone: its derivation document, records and laws, each read once, and the records
    GHOST_ONLY binds."""

    def __init__(self, milestone: str, root):
        self.m, self.root = milestone, Path(root)
        self.results = self.root / "results" / milestone
        dv = _load(self.root / "laws" / milestone / "DERIVATION.json")
        if not isinstance(dv, dict) or not isinstance(dv.get("laws"), list):
            raise RuntimeError(f"milestone {milestone} cannot be judged: laws/{milestone}/DERIVATION.json is not "
                               "readable")
        self.dv = {e["law_id"]: e for e in dv["laws"] if isinstance(e, dict) and "law_id" in e}
        self.ghost: dict = {}
        self._recs: dict = {}

    def record(self, lid: str):
        if lid not in self._recs:
            self._recs[lid] = _load(self.results / f"{lid}.json")
        return self._recs[lid]

    def law(self, lid: str):
        return _load(self.root / "laws" / self.m / f"{lid}.json")

    def entries(self, rule: str, subforms=None) -> list:
        return sorted(k for k, e in self.dv.items()
                      if e.get("rule") == rule and (subforms is None or e.get("subform") in subforms))

    def unobserved(self, lid: str, what: str) -> str | None:
        """A passed replay that does not observe the obstruction: None when GHOST_ONLY binds the record (counted), else
        the refusal, UNOBSERVED with what was found."""
        ok, terms = ghost_only(self.law(lid), self.dv.get(lid))
        if ok:
            self.ghost[lid] = what
            return None
        return f"{what}: {UNOBSERVED}; GHOST_ONLY does not apply (the predicate names {', '.join(terms)})"

    def ghost_detail(self) -> str:
        return ("GHOST_ONLY (an obstruction stated over ghost state alone, decided from the law's IR, binds on calls "
                f"agreeing): {len(self.ghost)} records" + (f" ({', '.join(sorted(self.ghost))})" if self.ghost else ""))


# ------------------------------------------------------------------------------------------------ the clauses
def typed(ctx: Ctx) -> tuple[list, list, int]:
    """I30's typed entries: every REFUTED entry is a passed entry of replay/<M>/sorts/report.json with its witness's
    trace, observing the obstruction. (A30 review) a REFUTED record stands on its kernels (AGENTS rule 6); its own
    replay on the real contract is checked too, and a record this clause refuses leaves REFUTED through the final
    filter. (bad, their laws, the entries judged)."""
    from .rules.sort import SUBFORMS
    rep = _load(ctx.root / "replay" / ctx.m / "sorts" / "report.json") or {"laws": {}}
    bad, laws, n = [], [], 0

    def no(lid, why):
        bad.append(refuse(lid, why))
        laws.append(lid)
    for lid in ctx.entries("SORT", SUBFORMS):
        r = ctx.record(lid)
        if not r or r.get("status") != "REFUTED":
            continue
        judged(lid)
        if (r.get("replay") or {}).get("status") not in ("passed", "not_applicable"):
            no(lid, f"{lid}: REFUTED, but its replay on the real contract is {(r.get('replay') or {}).get('status')}: "
                    f"{(r.get('replay') or {}).get('detail', '')[:200]}")
        for e, w in sorted((r.get("witnesses") or {}).items()):
            if w.get("status") != "REFUTED":
                continue
            n += 1
            x = (((rep.get("laws") or {}).get(lid) or {}).get("entries") or {}).get(e)
            if x is None:
                no(lid, f"{lid}/{e}: not replayed")
            elif x.get("status") != "passed" or x.get("trace") != w["witness"]["steps"]:
                no(lid, f"{lid}/{e}: replay {x.get('status')}")
            elif (w.get("replay") or {}).get("status") != "passed":
                no(lid, f"{lid}/{e}: the record's replay is {(w.get('replay') or {}).get('status')}")
            elif x.get("obstruction_observed") is not True:
                why = ctx.unobserved(lid, f"{lid}/{e}: its replay passes with calls agreeing, but obstruction_observed "
                                          f"is {x.get('obstruction_observed')}")
                if why:
                    no(lid, why)
    return bad, laws, n


def undo(ctx: Ctx) -> tuple[list, list, int]:
    """The UNDO laws (I27): every REFUTED UNDO record is a passed entry of replay/<M>/undo/report.json with its
    witness's two runs, which diverge on the real contract where the model's do. (bad, their laws, the records
    judged)."""
    rep = _load(ctx.root / "replay" / ctx.m / "undo" / "report.json") or {"laws": {}}
    bad, laws, n = [], [], 0
    for lid in ctx.entries("UNDO"):
        r = ctx.record(lid)
        if not r or r.get("status") != "REFUTED":
            continue
        n += 1
        judged(lid)
        x = (rep.get("laws") or {}).get(lid)
        w = r.get("witness") or {}
        pre = list(w.get("prefix") or [])
        # the run without x: prefix + t, or prefix + [y] + t for a cancel law (I71: y alone)
        alone = [w.get("y")] if ctx.dv[lid].get("subform") == "cancel" else []
        why = None
        if x is None:
            why = f"{lid}: not replayed"
        elif x.get("status") != "passed" or not x.get("calls_agree"):
            why = f"{lid}: replay {x.get('status')}"
        elif (x.get("with") or {}).get("trace") != pre + [w.get("x"), w.get("y")] + list(w.get("t") or []) or \
                (x.get("without") or {}).get("trace") != pre + alone + list(w.get("t") or []):
            why = f"{lid}: the replayed runs are not the record's witness"
        elif (r.get("replay") or {}).get("status") != "passed":
            why = f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}"
        elif x.get("diverges_at") is None:
            why = ctx.unobserved(lid, f"{lid}: its runs with and without x;y do not diverge on the real contract")
        if why:
            bad.append(refuse(lid, why))
            laws.append(lid)
    return bad, laws, n


def judged_elsewhere(ctx: Ctx) -> set:
    """The laws another clause judges: I30's entries, UNDO, NAT, the PAR-init laws, DISCH and FACT, the bundle laws
    (I84, I86), the contract laws and I88's derivation law set."""
    from .rules.sort import SUBFORMS
    from .rules import bundle2 as RB2
    from .sorts.contract3_run import contract_ids
    mine = set(ctx.entries("SORT", SUBFORMS)) | set(ctx.entries("UNDO")) | set(contract_ids(ctx.m, ctx.root))
    mine |= {k for k, e in ctx.dv.items() if e.get("rule") in ("DISCH", "FACT")}
    mine |= {k for k, e in ctx.dv.items() if RB2.RULE_OF.get(e.get("subform")) == e.get("rule")}
    for get in (lambda: __import__("holon.bundle.lawrun", fromlist=["x"]).bundle_entries(ctx.m, ctx.root),
                lambda: __import__("holon.rules.nat_run", fromlist=["x"]).nat_entries(ctx.m, ctx.root),
                lambda: __import__("holon.versions.run", fromlist=["x"]).init_entries(ctx.m, ctx.root)):
        try:
            mine |= set(get())
        except Exception:  # noqa: BLE001  (a family the milestone does not have)
            pass
    try:      # I88's derivation law set (holon.derivation.bendgate decides and checks it; its records are its own)
        from .ir import PLAN_LAWS_SIDECAR
        side = _load(ctx.root / PLAN_LAWS_SIDECAR) or {}
        if (side.get("law_set") or {}).get("milestone") == ctx.m:
            mine |= {e["id"] for e in side.get("laws") or [] if isinstance(e, dict) and "id" in e}
    except Exception:  # noqa: BLE001  (no derivation law set)
        pass
    return mine


def other(ctx: Ctx) -> tuple[list, str]:
    """I98: every other REFUTED record of the milestone, the laws no other clause judges (on M3 the PAR, SYM and OWN
    laws outside the bundle laws). Each is judged by the first replay of OTHER_REPLAYS that names it:
      go     replay/<M>/{own,gocount,goops}/report.json (holon.goreplay) and replay/<M>/par/report.json
             (holon.replay.main_replay_par), the base replay format: the record's replay field is
             holon.replay.replay_status of that report (its witness's sha256, every side passed), and every side
             observes the obstruction;
      gox    replay/<M>/gox/<law>.json (holon.gox): verdict agree, and its witness_sha256 the record witness's;
      symb   replay/<M>/symb/<law>.json (holon.symb): agree, and its witness_sha256 the record witness's;
      sym    replay/<M>/sym/report.json (I34): passed, and the record's sym.replay the report's entry; it observes no
             obstruction, so only GHOST_ONLY can bind such a record;
      I40    replay/<M>/refute/report.json's sides (I40's emitted tests, run on the real code): every side passed and
             observed its part of the obstruction, each side's test emitted for this law. Those sides are the record's
             replay, so the record's own replay field is not read (the final filter writes it from them).
    Every binding but I40's also needs the record's own replay to have passed. A record no replay names is refused.
    The PAR-init laws are holon.versions.replay.g6's, joined here. (bad, detail); the detail counts the records each
    kind binds, and each side provenance."""
    from .replay import replay_status
    from .gox.lawrun import witness_sha256 as gox_sha
    from .symb.lawrun import canon
    mine = judged_elsewhere(ctx)
    base = ctx.root / "replay" / ctx.m
    docs: dict = {}

    def doc(rel: str):
        if rel not in docs:
            docs[rel] = _load(base / rel)
        return docs[rel]

    bad, laws, bound, prov = [], [], Counter(), Counter()
    for p in sorted(ctx.results.glob("L*.json")):
        lid = p.stem
        if lid in mine:
            continue
        r = ctx.record(lid)
        if not isinstance(r, dict) or r.get("status") != "REFUTED":
            continue
        judged(lid)
        w, own = r.get("witness"), r.get("replay") or {}
        found = None
        for kind, rel, layout in OTHER_REPLAYS:
            rel = rel.format(law=lid)
            d = doc(rel)
            if not isinstance(d, dict):
                continue
            if layout == "file" or (layout == "laws" and lid in (d.get("laws") or {})) or \
                    (layout == "records" and f"{ctx.m}/{lid}" in (d.get("records") or {})):
                found = (kind, rel, d)
                break
        if found is None:
            bad.append(refuse(lid, f"{lid}: not replayed (no replay of its family names it: "
                                   f"{', '.join(sorted({k for k, _r, _l in OTHER_REPLAYS}))})"))
            laws.append(lid)
            continue
        kind, rel, d = found
        why = None
        if kind == "go":
            st = replay_status(d, lid, w)
            sides = {k: v for k, v in (d["laws"][lid] or {}).items() if isinstance(v, dict)}
            for side in sides.values():
                if side.get("provenance"):
                    prov[side["provenance"]] += 1
            unseen = [k for k, v in sorted(sides.items()) if v.get("obstruction_observed") is not True]
            if st["status"] != "passed":
                why = f"replay/{ctx.m}/{rel}: {st['detail']}"
            elif own != st:
                why = f"the record's replay is not replay/{ctx.m}/{rel}'s ({own.get('status')})"
            elif unseen:
                why = ctx.unobserved(lid, f"replay/{ctx.m}/{rel}: the {', '.join(unseen)} side(s) passed")
        elif kind == "gox":
            if d.get("witness_sha256") != gox_sha(w):
                why = f"replay/{ctx.m}/{rel} replays another witness"
            elif d.get("verdict") != "agree":
                why = f"replay/{ctx.m}/{rel}: verdict {d.get('verdict')}"
        elif kind == "symb":
            if d.get("witness_sha256") != hashlib.sha256(canon(w).encode()).hexdigest():
                why = f"replay/{ctx.m}/{rel} replays another witness"
            elif d.get("agree") is not True:
                why = f"replay/{ctx.m}/{rel}: the worlds do not differ as the counter-law states"
        elif kind == "sym":
            e = d["laws"][lid]
            if e.get("status") != "passed":
                why = f"replay/{ctx.m}/{rel}: {e.get('status')}"
            elif ((r.get("sym") or {}).get("replay") or {}) != e:
                why = f"the record's sym.replay is not replay/{ctx.m}/{rel}'s entry"
            else:
                why = ctx.unobserved(lid, f"replay/{ctx.m}/{rel} passes with the deployment's outcomes the model's, "
                                          "and reads no word of the real state")
        else:   # I40
            sides = (d["records"][f"{ctx.m}/{lid}"] or {}).get("sides") or {}
            for side in sides.values():
                if isinstance(side, dict) and side.get("provenance"):
                    prov[side["provenance"]] += 1
            bads = [k for k, v in sorted(sides.items()) if not (isinstance(v, dict) and v.get("status") == "passed"
                                                                and v.get("obstruction_observed") is True)]
            named = all(lid in str(v.get("test") or v.get("command") or "") for v in sides.values()
                        if isinstance(v, dict))
            if not sides:
                why = f"replay/{ctx.m}/{rel} holds no side for it"
            elif bads:
                why = f"replay/{ctx.m}/{rel}: the {', '.join(bads)} side(s) did not pass observing the obstruction"
            elif not named:
                why = f"replay/{ctx.m}/{rel}: a side's test is not the one emitted for this law"
        if why is None and kind not in ("I40", "go") and own.get("status") != "passed":
            why = f"the record's replay is {own.get('status')}"
        if why is not None:
            bad.append(refuse(lid, f"{lid}: {why}"))
            laws.append(lid)
        else:
            bound[kind] += 1
    try:      # I28 (V9): the REFUTED PAR-init records, bound to the versions replay report
        from .versions.replay import g6 as versions_g6
        pinit = versions_g6(ctx.m, ctx.root, ctx)
    except Exception as e:  # noqa: BLE001  (a crash is a failed clause)
        pinit = (False, f"PAR-init laws: the binding could not be checked: {type(e).__name__}: {e}")
    n = sum(bound.values())
    parts = []
    if n or bad:
        parts.append(f"the other laws: {n} REFUTED records bound to passed replays of their family, observing the "
                     "obstruction (" + ", ".join(f"{k} {v}" for k, v in sorted(bound.items())) + ")"
                     + (f", sides' provenance {', '.join(f'{k} {v}' for k, v in sorted(prov.items()))}" if prov else "")
                     + (f"; refused: {_named(bad, laws)}" if bad else ""))
    if pinit is not None:
        parts.append(pinit[1])
        if not pinit[0]:
            bad.append(pinit[1])
    return bad, "; ".join(parts)


def core(milestone: str, root, ctx: Ctx | None = None) -> dict:
    """holon.sorts.gate3's own G6: the typed entries, UNDO, the other laws (with the PAR-init laws) and NAT, and
    GHOST_ONLY's count over them (the joined clauses never bind by it: their pass rules observe)."""
    ctx = ctx or Ctx(milestone, root)
    bad, laws, n = typed(ctx)
    ub, ul, un = undo(ctx)
    bad, laws = bad + ub, laws + ul
    ob, oth = other(ctx)
    res = _res(not bad and not ob, (f"{n} REFUTED entry points and {un} REFUTED UNDO laws replayed and passed on the "
                                    "real contract, observing the obstruction" if not bad else _named(bad, laws))
               + (f"; {oth}" if oth else ""))
    try:      # I29 (N9): the REFUTED NAT records are bound to their runs of the NAT replay report
        from .rules.nat_replay import g6 as nat_g6
        nat = nat_g6(ctx.m, ctx.root, ctx)
    except Exception as e:  # noqa: BLE001  (a crash is a failed clause)
        nat = (False, f"NAT laws: the binding could not be checked: {type(e).__name__}: {e}")
    if nat is not None:
        res = _res(res["passed"] and nat[0], f"{res['detail']}; {nat[1]}")
    return _res(res["passed"], f"{res['detail']}; {ctx.ghost_detail()}")


def disch(milestone: str, root, ctx: Ctx | None = None) -> dict:
    """The DISCH laws (I31): every REFUTED DISCH record, and every PROVED one with a witness, is a passed entry of
    replay/<M>/disch/report.json with its witness's trace, its guard blocked before the step and discharged after it on
    the real storage. {"na": why} without one."""
    from .analysis import closure as C
    from .rules.disch import SUBFORMS
    ctx = ctx or Ctx(milestone, root)
    ids = ctx.entries("DISCH", SUBFORMS)
    if not ids:
        return {"na": "no DISCH law"}
    want = {lid: r for lid in ids for r in [ctx.record(lid)]
            if r and (r.get("status") == "REFUTED" or (r.get("status") == "PROVED" and r.get("witness")))}
    if not C.Sidecar(ctx.m, ctx.root, None).binding:
        return {"na": "the DISCH sidecar names no binding: no real side to replay on"}
    rep = _load(ctx.root / "replay" / ctx.m / "disch" / "report.json") or {"laws": {}}
    bad, laws = [], []
    for lid, r in sorted(want.items()):
        judged(lid)
        x = (rep.get("laws") or {}).get(lid)
        why = None
        if x is None:
            why = f"{lid}: not replayed"
        elif x.get("status") != "passed" or x.get("trace") != r["witness"]["steps"]:
            why = f"{lid}: replay {x.get('status')}"
        elif (r.get("replay") or {}).get("status") != "passed":
            why = f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}"
        elif not (x.get("blocked_before") is True and x.get("discharged_after") is True):
            why = ctx.unobserved(lid, f"{lid}: its replay does not show the guard blocked before the step and "
                                      "discharged after it")
        if why:
            bad.append(refuse(lid, why))
            laws.append(lid)
    return _res(not bad, f"{len(want)} DISCH witnesses replayed and passed on the real contract, observing the "
                         "obstruction" if not bad else _named(bad, laws))


def fact(milestone: str, root, ctx: Ctx | None = None) -> dict:
    """The FACT laws (I26): every REFUTED FACT record is a passed entry of replay/<M>/fact/report.json with its
    witness's runs or trace; the replay's pass rule (holon.fact.run) reads the obstruction on the real storage.
    {"na": why} without one."""
    from .rules import fact as RF
    ctx = ctx or Ctx(milestone, root)
    ids = ctx.entries(RF.RULE, RF.SUBFORMS)
    if not ids:
        return {"na": "no FACT law"}
    want = {lid: r for lid in ids for r in [ctx.record(lid)] if r and r.get("status") == "REFUTED"}
    if not RF.load_sidecar(ctx.m, ctx.root).doc.get("binding"):
        return {"na": "the FACT sidecar names no binding: no real side to replay on"}
    rep = _load(ctx.root / "replay" / ctx.m / "fact" / "report.json") or {"laws": {}}
    bad, laws = [], []
    for lid, r in sorted(want.items()):
        judged(lid)
        x = (rep.get("laws") or {}).get(lid)
        w = r.get("witness") or {}
        why = None
        if x is None:
            why = f"{lid}: not replayed"
        elif x.get("status") != "passed" or not x.get("calls_agree"):
            why = f"{lid}: replay {x.get('status')}"
        elif "runs" in w and [y.get("trace") for y in x.get("runs") or []] != \
                [list(q["prefix"]) + [q["x"]] for q in w["runs"]]:
            why = f"{lid}: the replayed runs are not the record's witness"
        elif "runs" not in w and x.get("trace") != list(w.get("prefix") or []) + [w.get("y")] + list(w.get("t") or []):
            why = f"{lid}: the replayed trace is not the record's witness"
        elif (r.get("replay") or {}).get("status") != "passed":
            why = f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}"
        if why:
            bad.append(refuse(lid, why))
            laws.append(lid)
    return _res(not bad, f"{len(want)} REFUTED FACT laws replayed and passed on the real contract, observing the "
                         "obstruction" if not bad else _named(bad, laws))


def contract(milestone: str, root, ctx: Ctx | None = None) -> dict:
    """The typed contract laws (I33, holon.sorts.contract3_run.contract_ids): every REFUTED record's replay passed.
    {"na": why} when none is REFUTED."""
    from .sorts.contract3_run import contract_ids
    ctx = ctx or Ctx(milestone, root)
    ids = contract_ids(ctx.m, ctx.root)
    if not ids:
        return {"na": "no contract law"}
    want = {lid: r for lid in ids for r in [ctx.record(lid)] if r and r.get("status") == "REFUTED"}
    if not want:
        return {"na": "no contract law is REFUTED"}
    bad, laws = [], []
    for lid, r in sorted(want.items()):
        judged(lid)
        if (r.get("replay") or {}).get("status") != "passed":
            bad.append(refuse(lid, f"{lid}: replay {(r.get('replay') or {}).get('status')}"))
            laws.append(lid)
    return _res(not bad, f"{len(want)} REFUTED contract laws replayed and passed on the real contract"
                if not bad else _named(bad, laws))


def bundle2(milestone: str, root, ctx: Ctx | None = None) -> dict:
    """The bundle laws of I84 (holon.bundle2): every REFUTED record is a passed entry of the sidecar's replay report;
    the replay's pass rule (holon.bundle2.laws_replay) reads the obstruction on the real code. {"na": why} when none
    is REFUTED."""
    from .rules import bundle2 as RB2
    ctx = ctx or Ctx(milestone, root)
    ids = sorted(k for k, e in ctx.dv.items() if RB2.RULE_OF.get(e.get("subform")) == e.get("rule"))
    if not ids:
        return {"na": "no bundle law"}
    want = {lid: r for lid in ids for r in [ctx.record(lid)] if r and r.get("status") == "REFUTED"}
    if not want:
        return {"na": "no bundle law is REFUTED"}
    side = _load(RB2.sidecar_path(ctx.m, ctx.root)) or {}
    rep = _load(ctx.root / side["outputs"]["replay"]) or {"laws": {}}
    bad, laws = [], []
    for lid, r in sorted(want.items()):
        judged(lid)
        x = (rep.get("laws") or {}).get(lid)
        why = None
        if x is None:
            why = f"{lid}: not replayed"
        elif x.get("status") != "passed":
            why = f"{lid}: replay {x.get('status')}"
        elif (r.get("replay") or {}).get("status") != "passed":
            why = f"{lid}: the record's replay is {(r.get('replay') or {}).get('status')}"
        if why:
            bad.append(refuse(lid, why))
            laws.append(lid)
    return _res(not bad, f"{len(want)} REFUTED bundle laws replayed and passed on the real code, observing the "
                         "obstruction" if not bad else _named(bad, laws))


def bundle(milestone: str, root, ctx: Ctx | None = None) -> dict:
    """The bundle laws of I86 (holon.bundle.lawrun.bundle_entries): every REFUTED record, and every PROVED
    keyed_external one, is a passed entry of replay/<M>/bundle_laws/report.json; the replay's pass rule
    (holon.bundle.replay_laws) reads the obstruction on the real bundle. {"na": why} without one."""
    from .bundle.lawrun import bundle_entries
    ctx = ctx or Ctx(milestone, root)
    ents = bundle_entries(ctx.m, ctx.root)
    if not ents:
        return {"na": "no bundle law"}
    rep = _load(ctx.root / "replay" / ctx.m / "bundle_laws" / "report.json") or {"laws": {}}
    bad, laws, n = [], [], 0
    for lid in sorted(ents):
        rec = ctx.record(lid)
        if not rec:
            continue
        sub = ents[lid].get("subform")
        if not (rec.get("status") == "REFUTED" or (rec.get("status") == "PROVED" and sub == "keyed_external")):
            continue
        n += 1
        judged(lid)
        x = (rep.get("laws") or {}).get(lid)
        why = None
        if x is None or x.get("status") != "passed":
            why = f"{lid}: replay {None if x is None else x.get('status')}"
        elif (rec.get("replay") or {}).get("status") != "passed":
            why = f"{lid}: the record's replay is {(rec.get('replay') or {}).get('status')}"
        if why:
            bad.append(refuse(lid, why))
            laws.append(lid)
    return _res(not bad, f"{n} bundle witnesses replayed and passed on the real bundle, observing the obstruction"
                if not bad else _named(bad, laws))


# The joined clauses, in the order holon.sorts.gate3 joins their gates, with the label each gate's detail carries.
JOINED = (("DISCH laws", disch), ("FACT laws", fact), ("contract laws", contract), ("bundle laws", bundle2),
          ("bundle laws", bundle))


def judgement(milestone: str, root) -> dict:
    """G6 over the milestone's results, every clause here, composed as holon.sorts.gate3 composes the gates' (the
    derivation law set, whose records are its own, apart)."""
    ctx = Ctx(milestone, root)
    res = core(milestone, root, ctx)
    for label, fn in JOINED:
        r = fn(milestone, root, ctx)
        if "na" in r:
            continue
        res = _res(res["passed"] and r["passed"], f"{res['detail']}; {label}: {r['detail']}")
    return res


def binding(milestone: str, root) -> tuple[dict, list, dict]:
    root = Path(root)
    c = _Collection()
    _ACTIVE.append(c)
    try:
        g6 = judgement(milestone, root)
    finally:
        _ACTIVE.remove(c)
    refuted = {p.stem for p in (root / "results" / milestone).glob("L*.json") if _status(p) == "REFUTED"}
    unbound = {law: sorted(set(why)) for law, why in sorted(c.refused.items()) if law in refuted}
    return unbound, sorted(law for law in c.judged if law in refuted), g6


def unbound(milestone: str, root) -> dict:
    return binding(milestone, root)[0]


def examined(milestone: str, root) -> list:
    return binding(milestone, root)[1]
