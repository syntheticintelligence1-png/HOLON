"""Oracle sidecars (holon-oracles/0.1): hashes and oracles as model parameters (BUILD_PLAN I12; whitepaper
§8.3 HASH and oracle rows, §8.5, Thm 6.15, Cor 6.16).

The oracle records of a facts file F live in F/../../lib/oracles.json, next to its target libraries. They
change no facts hash. Only M2+ milestones read them: the callers decide (holon.mpipeline.m2plus), M0 and M1
never pass a sidecar, so their models and statements are unchanged. A milestone's models over the facts of an
earlier milestone take the milestone's own sidecar, spec/<M>/lib/oracles.json, when its `facts` list names
them (Oracles.for_milestone; audit M2/1 F-M2-11: M2's Morph models over spec/M1/facts).

  {"oracles_version": "holon-oracles/0.1", "doc": str, "facts": [repo-relative facts paths] (optional),
   "oracles": [entry, ...]}
  entry = {"id", "oracle", "parameter": {"name", "type": "Fn<A,B>"}, "hypothesis": {"id", "doc", "kind": cf | hyp,
           "family", "predicate"}, "instance": {"bend", "doc"} | null, "status": modelled | not_in_scope, "reason",
           "ledger": [...]}

Format and rules: tests_m2/test_oracles.py (module docstring); holon.oracle_check.validate checks them.

The encoding (the plan's fallback, BUILD_PLAN I12 "Risks"). A Bend function value is Type, never Data, so a
binder of function type is erased or affine and a model that applies it twice cannot take it as a parameter
(docs/iterations/I7.md, Surprises). A modelled parameter p : Fn<A,B> is therefore held as Data, an oracle
table: List<&2, HO_p> of entries HO_p{k: A, v: B}, applied by ap_p(t, x), the v of the first entry whose k
equals x, else the default of B (0n, False{}, Nil{}). Tables are reusable (+), so step and run thread them
(holon.gen.machine). A law binder p : Fn<A,B> named like a parameter is that parameter, quantified over all
tables (holon.gen.mlaws).

Locality, the model assumption this rests on (ledger entry `oracle-tables`, spec/ledger/assumptions.json):
every function f agrees with some table on any finite set of points (its graph there). A statement over
finite traces queries f at finitely many points along its evaluation, and running with the graph of f on
the queried points makes the same queries and gets the same answers, step by step. So a law proved for all
tables holds for every function, and a table refuting a law is itself a function. It is not an axiom: no
statement assumes anything about tables beyond its own premises.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .. import ir

SIDECAR_VERSION = "holon-oracles/0.1"
SIDECAR = Path("lib") / "oracles.json"
KEY_TYPES = ("Nat", "Bool", "List<Nat>")     # parameter domains: decidable key equality in the prelude
_TOKEN = re.compile(r"\$\{(\w+):([^{}]*)\}|\$(args|\d)")


class OracleError(Exception):
    pass


def sidecar_path(facts_path: Path | str) -> Path:
    """F/../../lib/oracles.json for a facts file F."""
    return Path(facts_path).resolve().parent.parent / SIDECAR


def milestone_sidecar(milestone: str, root: Path | str) -> Path:
    """spec/<M>/lib/oracles.json: a milestone's own sidecar (holon-oracles/0.1 with a `facts` list of the
    repo-relative facts files it applies to; Oracles.for_milestone)."""
    return Path(root) / "spec" / milestone / SIDECAR


def load(path: Path | str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fn_types(t: str) -> tuple[str, str] | None:
    """Fn<A,B> -> (A, B), splitting at the top-level comma; None for any other type."""
    if not (isinstance(t, str) and t.startswith("Fn<") and t.endswith(">")):
        return None
    inner, depth = t[3:-1], 0
    for i, ch in enumerate(inner):
        depth += ch == "<"
        depth -= ch == ">"
        if ch == "," and depth == 0:
            return inner[:i].strip(), inner[i + 1:].strip()
    return None


def render_template(text: str, args: list[str], params: dict | None) -> str:
    """A holon-lib/0.1 builtin template: $0..$9 the arguments, $args all of them, ${param:NAME:DEFAULT} a facts
    parameter (DEFAULT when `params` is None or lacks NAME: a sidecar checked on its own)."""
    def sub(m: re.Match) -> str:
        if m.group(3) == "args":
            return ", ".join(args)
        if m.group(3) is not None:
            return args[int(m.group(3))]
        if m.group(1) != "param":
            raise OracleError(f"unknown template token {m.group(0)}")
        name, _, default = m.group(2).partition(":")
        return str((params or {}).get(name, default))
    return _TOKEN.sub(sub, text)


def inst_name(entry_id: str, taken: set | None = None) -> str:
    """The Bend name of an entry's instance function (inst_<id>, made an identifier)."""
    base = "inst_" + re.sub(r"[^A-Za-z0-9_]", "_", entry_id)
    while taken is not None and base in taken:
        base += "_"
    return base


class Oracles:
    """One parsed sidecar."""

    def __init__(self, doc: dict, path: Path | str | None = None):
        if doc.get("oracles_version") != SIDECAR_VERSION:
            raise OracleError(f"{path}: oracles_version {doc.get('oracles_version')!r} is not {SIDECAR_VERSION}")
        self.doc, self.path = doc, (Path(path) if path else None)
        self.entries: list[dict] = list(doc.get("oracles", []))
        self.by_id = {e["id"]: e for e in self.entries}
        self.by_hyp = {e["hypothesis"]["id"]: e for e in self.entries if isinstance(e.get("hypothesis"), dict)}
        # modelled parameters, in sidecar order: name -> (A, B)
        self.params: dict[str, tuple[str, str]] = {}
        for e in self.entries:
            if e.get("status") != "modelled":
                continue
            p, t = e["parameter"]["name"], e["parameter"].get("type")
            sig = fn_types(t)
            if sig is None:
                raise OracleError(f"{e['id']}: a modelled parameter needs a Fn<A,B> type, got {t!r}")
            if p in self.params and self.params[p] != sig:
                raise OracleError(f"parameter {p} has two types: Fn<{','.join(self.params[p])}> and {t}")
            self.params[p] = sig
        names = [inst_name(e["id"]) for e in self.entries]
        if len(set(names)) != len(names):
            raise OracleError("two entry ids map to one instance name")

    @classmethod
    def for_facts(cls, facts_path: Path | str | None) -> "Oracles | None":
        """The sidecar of a facts file, or None when it has none."""
        if facts_path is None:
            return None
        p = sidecar_path(facts_path)
        return cls(load(p), p) if p.exists() else None

    @classmethod
    def for_milestone(cls, milestone: str, facts_path: Path | str | None, root: Path | str | None = None) -> "Oracles | None":
        """The sidecar the model of facts F takes in milestone M (audit M2/1 F-M2-11). None for M0 and M1, which never
        read one. Otherwise F's own sidecar, F/../../lib/oracles.json, when it has one (fixtures; the facts of the
        milestone itself, spec/M<k>/facts/); else the milestone-level sidecar spec/<M>/lib/oracles.json when its
        `facts` list names F (repo-relative): a milestone's models over the facts of an earlier milestone (M2 over
        spec/M1/facts, which may not be edited: their hash is in every M1 statement) take the milestone's oracles."""
        if facts_path is None or milestone in ("M0", "M1"):
            return None
        own = cls.for_facts(facts_path)
        if own is not None:
            return own
        root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
        p = milestone_sidecar(milestone, root)
        if not p.exists():
            return None
        doc = load(p)
        try:
            rel = Path(facts_path).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return None
        return cls(doc, p) if rel in (doc.get("facts") or []) else None

    def param_type(self, p: str) -> str:
        a, b = self.params[p]
        return f"Fn<{a},{b}>"

    def hyp_entry(self, h: str) -> dict | None:
        """The modelled kind-hyp entry whose hypothesis is h."""
        e = self.by_hyp.get(h)
        if e and e.get("status") == "modelled" and e["hypothesis"].get("kind") == "hyp":
            return e
        return None

    def cf_entry(self, p: str) -> dict | None:
        """The modelled kind-cf entry of parameter p (the first, if several)."""
        return next((e for e in self.entries if e.get("status") == "modelled" and e["parameter"]["name"] == p
                     and e["hypothesis"].get("kind") == "cf"), None)

    def instances(self, p: str) -> list[dict]:
        """The modelled entries of parameter p that carry a concrete instance, in sidecar order."""
        return [e for e in self.entries if e.get("status") == "modelled" and e["parameter"]["name"] == p
                and isinstance(e.get("instance"), dict) and isinstance(e["instance"].get("bend"), str)]

    def family(self, h: str) -> str:
        e = self.by_hyp.get(h)
        return (e["hypothesis"].get("family") or h) if e else h

    def hyp_ref(self, h: str) -> str:
        """The content hash a hyp premise naming h refers to: its entry restricted to {parameter, hypothesis}
        (instance, doc and ledger serve refutation, inhabitation and humans, and are not hashed)."""
        e = self.by_hyp.get(h)
        obj = None if e is None else {"parameter": e.get("parameter"), "hypothesis": e.get("hypothesis")}
        return "sha256:" + hashlib.sha256(ir.canonical_json(obj)).hexdigest()


# ---------------------------------------------------------------- statements over the parameters
def hyp_names(law: dict) -> list[str]:
    """The hypothesis ids a law's hyp premises name, in premise order."""
    return [p["hyp"]["name"] for p in law["statement"].get("assume", []) if "hyp" in p]


def hypothesis_premises(law: dict, orc: "Oracles | None") -> list[str]:
    """§8.5: the sorted set of a law's hypothesis premises. A hyp premise gives its name; a cf premise gives the
    hypothesis id of the modelled kind-cf entry of its parameter (none when its function binder is no
    modelled parameter: an anonymous CF premise names no oracle hypothesis)."""
    out = set()
    for p in law["statement"].get("assume", []):
        if "hyp" in p:
            out.add(p["hyp"]["name"])
        elif "cf" in p and orc is not None:
            e = orc.cf_entry(p["cf"].get("fn"))
            if e is not None:
                out.add(e["hypothesis"]["id"])
    return sorted(out)


def params_used(machine) -> set:
    """The oracle parameters a model takes: those some facts expression (an action, a def, an observer, a
    migration) calls."""
    if machine is None or not getattr(machine, "oparams", None):
        return set()
    out = set(machine.threaded) | {p for ps in machine.fn_tabs.values() for p in ps}
    return out | set().union(set(), *(machine.def_uses(d) for d in machine.defs))


def replaced_stand_ins(orc: "Oracles | None", machine) -> set:
    """The ledger stand-ins a model replaces by parameters: the `ledger` of every modelled entry whose parameter
    the model takes. A not_in_scope entry's stand-in, or a modelled parameter no facts expression calls, stays."""
    used = params_used(machine)
    return {x for e in (orc.entries if orc is not None else []) if e.get("status") == "modelled"
            and e["parameter"]["name"] in used for x in e.get("ledger", [])}


def ledger_assumptions(cone_entries: list[str], orc: "Oracles | None", machine) -> list[str]:
    """(audit M2/1 F-M2-12) An M2+ record's ledger assumptions, kept beside its hypothesis premises
    (model_assumptions, §8.5): the ledger entries that meet its cone (holon.records.model_assumptions) minus the
    stand-ins the model replaces by parameters. Abstractions (abs-nat-tokens, ...) and the stand-ins still inside
    the model (not_in_scope entries: ISubmitter, the messenger, ...) stay."""
    gone = replaced_stand_ins(orc, machine)
    return sorted(x for x in cone_entries if x not in gone)


def _transitions(fp: Path) -> bool:
    """An extracted transitions document (holon-facts/0.3, I19/I20), whose model is holon.machine's, not a Machine."""
    try:
        d = json.loads(Path(fp).read_text())
    except (OSError, ValueError):
        return False
    return (isinstance(d, dict) and d.get("facts_version") == "holon-facts/0.3"
            and (d.get("extraction") or {}).get("kind") == "transitions")


def ledger_problems(milestone: str, root: Path, laws: list[dict], records: dict) -> list[str]:
    """G9 for M2+ milestones (F-M2-12): every record carries ledger_assumptions, equal to the recomputation from its
    cone, its facts' ledger bundle and the milestone's sidecar; a record whose cone meets ledger stand-ins never
    lists an empty set."""
    from .. import facts as F
    from .. import records as R
    from .machine import Machine
    bad, machines = [], {}
    for law in laws:
        rec = records.get(law["law_id"])
        if rec is None:
            continue
        if not isinstance(rec.get("ledger_assumptions"), list):
            bad.append(f"{law['law_id']}: an M2+ record lists no ledger_assumptions")
            continue
        fp = Path(root) / law["facts"]
        try:
            b, _ = R.resolve_bundle(rec["facts_sha256"], law["facts"], root)
        except R.LedgerError as e:
            bad.append(f"{law['law_id']}: {e}")
            continue
        meets = sorted(e["id"] for e in b["entries"] if R._meets(e, set(rec.get("cone") or [])))
        from ..codecrun import codec_kind
        if _transitions(fp) or codec_kind(law, root):   # an extracted model (I20), a codec model (I24): no oracle
            want = meets                                 # parameter replaces a ledger entry
        else:
            if fp not in machines:
                orc = Oracles.for_milestone(milestone, fp, root)
                machines[fp] = (orc, Machine(F.load(fp), fp, oracles=orc, m2plus=True))
            orc, m = machines[fp]
            want = ledger_assumptions(meets, orc, m)
        if rec["ledger_assumptions"] != want:
            what = "lists no ledger assumption" if not rec["ledger_assumptions"] else f"lists {rec['ledger_assumptions']}"
            bad.append(f"{law['law_id']}: {what}, but its cone meets the ledger stand-ins and abstractions {want}")
    return bad


def expand_hyps(law: dict, orc: "Oracles | None") -> dict:
    """The law with each hyp premise replaced by its hypothesis' predicate (for the refuter, which evaluates
    premises; the frozen statement keeps the reference). Unknown names raise OracleError."""
    import copy
    out = copy.deepcopy(law)
    prem = []
    for p in law["statement"].get("assume", []):
        if "hyp" in p:
            e = orc.hyp_entry(p["hyp"]["name"]) if orc else None
            if e is None:
                raise OracleError(f"hyp premise {p['hyp']['name']!r} names no modelled kind-hyp hypothesis of the sidecar")
            prem += copy.deepcopy(e["hypothesis"]["predicate"])
        else:
            prem.append(copy.deepcopy(p))
    if prem:
        out["statement"]["assume"] = prem
    return out


def check_law(law: dict, orc: "Oracles | None") -> None:
    """Raise OracleError when a law's oracle premises do not resolve against the sidecar: a hyp premise must
    name a modelled kind-hyp hypothesis whose parameter the law binds as a Fn binder of the sidecar's type."""
    binders = {b["name"]: b["type"] for b in law["statement"].get("binders", [])}
    for h in hyp_names(law):
        e = orc.hyp_entry(h) if orc else None
        if e is None:
            raise OracleError(f"hyp premise {h!r} names no modelled kind-hyp hypothesis of the oracle sidecar")
        p = e["parameter"]["name"]
        if binders.get(p) != orc.param_type(p):
            raise OracleError(f"hyp premise {h!r} constrains parameter {p}, which the law does not bind as {orc.param_type(p)}")
    for n, t in binders.items():
        if orc is not None and n in orc.params and fn_types(t) and t != orc.param_type(n):
            raise OracleError(f"binder {n}: {t} is named like the parameter {n} of type {orc.param_type(n)}")


def splits(laws: list[dict], statuses: dict[str, str], oracles_of: dict, milestone: str) -> dict:
    """holon-splits/0.1: hypothesis splits are law pairs (whitepaper §8.5; BUILD_PLAN I7, I12).

    Laws pair on family F when they name different hypotheses of F and their statements are equal once every
    hyp premise name of family F is replaced by F; pairs come from statements, never from law ids. A law that
    names two hypotheses of one family pairs on none of them; laws over different facts files never pair.
    split: some law of the pair PROVED and some REFUTED. oracles_of: law id -> the sidecar of its facts."""
    groups: dict[tuple, dict] = {}
    for law in laws:
        orc = oracles_of.get(law["law_id"])
        hs = hyp_names(law)
        fams: dict[str, list[str]] = {}
        for h in hs:
            fams.setdefault(orc.family(h) if orc else h, []).append(h)
        for fam, mine in fams.items():
            if len(set(mine)) != 1:
                continue
            norm = json.loads(json.dumps(law["statement"]))
            for p in norm.get("assume", []):
                if "hyp" in p and p["hyp"]["name"] in mine:
                    p["hyp"]["name"] = fam
            key = (fam, law.get("facts"), ir.canonical_json(norm).decode())
            groups.setdefault(key, {})[law["law_id"]] = mine[0]
    pairs = []
    for (fam, _, _), members in groups.items():
        if len(set(members.values())) < 2:
            continue
        laws_out = {lid: {"hypothesis": h, "status": statuses.get(lid, "UNKNOWN")} for lid, h in sorted(members.items())}
        st = {x["status"] for x in laws_out.values()}
        pairs.append({"family": fam, "laws": laws_out, "split": "PROVED" in st and "REFUTED" in st})
    pairs.sort(key=lambda y: (y["family"], sorted(y["laws"])))
    return {"splits_version": "holon-splits/0.1", "milestone": milestone, "pairs": pairs}
