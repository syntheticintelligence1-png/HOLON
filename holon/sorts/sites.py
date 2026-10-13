"""Rule SORT, subform site: one law per subtraction realized in Nat (BUILD_PLAN I15; whitepaper §5.6, §7.2, §7.8,
Thm 6.18 localization, App. E SORT basis). The contract is the docstring of tests_m2/test_sort_sites.py.

  law_id(site_id)               R7: L_sort_site_<where>_<x8>, a function of the basis element (the I13 site)
  hit_points(facts, site, real) R8-R10: where an action evaluates the site, from the facts, the I13 site's
                                occurrences and the realization-check reasons of the sidecar
  produce(ctx)                  the producer holon.rules runs: one holon-ir/0.3 law and one DERIVATION entry per site
  site_spec / site_ref          what the statement ref "site:<id>" hashes (holon.gen.refs), recomputed from the facts
                                and the sidecar alone (so G2 needs no derive output)
  instrumented_model(...)       the model of a run, then GHOST_MARKER, then the ghost section
  ghost_plan(...)               the structure of the ghost section, for the proof generators that mirror it

Hit points. An action site (occurrences "guards[i].expr|require" or "effects.<f>") is hit at its occurrence, unless a
require g of the action before it (any require, for an effect occurrence) is a realization check of the site: g's
span (the leading "<path>:<line>[-<line>]" of its src) is the site's span and the text of g's reason in the facts'
reasons table is one of the sidecar's realization_check_reasons. Then the hit is at the first such g, evaluated just
before g's require (R8): g is the facts' model of the code's own check of this subtraction, so it never discharges
the obligation it models. A definition site (occurrences "defs.<d>.body") is hit at every guard or effect of an
action whose expression calls a definition whose evaluation reaches d (R9). Evaluation order (R10): guards in order
up to the first failing require, effects only when every require holds; ["?", c, x, y] evaluates x only when c
holds and y only when it fails, && and || short-circuit, a definition call evaluates its body with the arguments
bound, any other node evaluates every operand.

The ghost section (appended after the model, so nothing in the model can name it: Bend definitions see only the
definitions above them). For a law with x = law_id[len("L_sort_site_"):]:

  site_<x>(a, s[, tables])   matches a, then calls gs_<x>_<a>(s, inputs..[, tables]) for an entry point a (True
                             for any other action). gs_<x>_<a> matches s and walks a's guards as the model's decide
                             chain does: a let binds, a require calls the decision helper gs_<x>_<a>_<i>(c, ..),
                             whose False case is True (the action stops: no hit) and whose True case continues. At a
                             hit the obligation is evaluated: Nat.is_le(subtrahend, minuend) under the occurrence's
                             path condition (ite(Bool, cond, .., True{}) per condition, outermost first), or, for a
                             definition site, gd_<x>_<f>(args) at each call of a definition f reaching the site's
                             definition. Several evaluations at one hit are conjoined (Bool.and); a hit that is not
                             the action's last continues in gs_<x>_<a>_k<i> (Bool.and(obligation, continuation)).
  gd_<x>_<f>(params of f)    per definition f reaching the site's definition d: the conjunction, over the
                             evaluations in f's body that reach d (the subtraction itself when f is d, else a call
                             of such a definition), of their obligations under their path conditions in f's body.
  hit_<x>, gh_<x>_..,        the same chains, at_site instead of nonneg: true iff evaluating a from s evaluates the
  gdh_<x>_<f>                subtraction at least once (the requires before it hold, and so does every path
                             condition on the way, inside definitions included); Bool.or, False where it stops.

Ghost definitions only: no state field, no change to any definition above the marker.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..gen.machine import FactsError, Machine, bname, bt, fresh
from . import flow as F
from .assign import canonical, site_span

ROOT = Path(__file__).resolve().parents[2]
SIDECAR_VERSION = "holon-sort-sites/0.1"
SIDECAR = Path("spec") / "M2" / "lib" / "sort_sites.json"
TEMPLATE = "holon.sorts.sites/site_ok"
TEMPLATE_VERSION = 1
LAW_PREFIX = "L_sort_site_"
RULE, SUBFORM = "SORT", "site"
GHOST_MARKER = "# ---- ghost: SORT-site instrumentation (holon.sorts.sites)"
_SPAN = re.compile(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$")


class SiteError(ValueError):
    """A site that cannot be derived or instrumented (holon derive exits 3 and names it)."""


class StaleSites(ValueError):
    """The frozen assignment's sites disagree with the facts (holon derive exits 2)."""


# ------------------------------------------------------------------ R7: law ids
def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def split_site_id(site_id: str) -> tuple[str, str, str]:
    """(model, span, x8) of an I13 site id "<model>:<span>:<x8>"."""
    head, x8 = site_id.rsplit(":", 1)
    model, span = head.split(":", 1)
    return model, span, x8


def law_id(site_id: str) -> str:
    """L_sort_site_<where>_<x8> (x8: the site id's last 8 hex digits, the hash of the subtraction as written).
    <where> is, for a source span "<path>:<lo>[-<hi>]", slug(file stem) + "_<lo>" [+ "_<hi>"]; for a definition span
    "<model>:<def>", "def_" + slug(<def>)."""
    model, span, x8 = split_site_id(site_id)
    m = _SPAN.match(span)
    if m:
        where = slug(Path(m["path"]).stem) + f"_{m['lo']}" + (f"_{m['hi']}" if m["hi"] else "")
    elif span.startswith(model + ":"):
        where = "def_" + slug(span.split(":", 1)[1])
    else:
        raise SiteError(f"site {site_id}: span {span!r} is neither a source span nor a definition of {model}")
    return f"{LAW_PREFIX}{where}_{x8}"


def ghost_x(lid: str) -> str:
    return lid[len(LAW_PREFIX):]


# ------------------------------------------------------------------ the sidecar
def sidecar_path(milestone: str, root: Path | str | None = None) -> Path:
    """spec/<M>/lib/sort_sites.json when it exists, else M2's (a test milestone such as T15 uses M2's)."""
    root = Path(root or ROOT)
    own = root / "spec" / milestone / "lib" / "sort_sites.json"
    return own if own.exists() else root / SIDECAR


def load_sidecar(milestone: str, root: Path | str | None = None) -> tuple[Path, dict, set]:
    p = sidecar_path(milestone, root)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("sort_sites_version") != SIDECAR_VERSION:
        raise SiteError(f"{p}: sort_sites_version {doc.get('sort_sites_version')!r} is not {SIDECAR_VERSION}")
    real = doc.get("realization_check_reasons")
    if not isinstance(real, list) or not all(isinstance(r, str) for r in real):
        raise SiteError(f"{p}: realization_check_reasons is not a list of reason texts")
    return p, doc, set(real)


# ------------------------------------------------------------------ walking expressions (R10)
def walk(e, conds: tuple = ()):
    """Every expression node of e in pre-order, left to right, with its path condition: the conditions that must
    hold for the real code to evaluate it, as ((condition, polarity), ..) outermost first (R10). A definition
    call's body is not entered here (callers handle definitions)."""
    if not isinstance(e, list) or not e:
        return
    yield e, conds
    op = e[0]
    if op == "?" and len(e) == 4:
        yield from walk(e[1], conds)
        yield from walk(e[2], conds + ((e[1], True),))
        yield from walk(e[3], conds + ((e[1], False),))
        return
    if op in ("&&", "||"):
        pol = op == "&&"   # && evaluates an operand only when the earlier ones hold, || only when they fail
        pre = conds
        for x in e[1:]:
            yield from walk(x, pre)
            pre = pre + ((x, pol),)
        return
    if op == "call":
        kids = e[2:]
    elif op == "get":
        kids = [e[1]]
    elif op == "mk":
        kids = list(e[2].values())
    elif op == "with":
        kids = [e[2], *e[3].values()]
    elif op == "list":
        kids = e[2:]
    else:
        kids = e[1:]
    for k in kids:
        yield from walk(k, conds)


def node_positions(e, node) -> list[tuple]:
    """The path conditions of every evaluation position of `node` (compared as written) in e."""
    key = canonical(node)
    return [c for n, c in walk(e) if canonical(n) == key]


def call_positions(e, targets) -> list[tuple]:
    """(callee, call node, path condition) of every call in e of a definition in `targets`, pre-order."""
    return [(n[1], n, c) for n, c in walk(e) if n[0] == "call" and len(n) > 1 and n[1] in targets]


def entries(action: dict) -> list[tuple[str, object]]:
    """(at, expression) of every guard (let or require) of an action, then of every effect."""
    out = [(f"guards[{i}]", g.get("require", g.get("expr"))) for i, g in enumerate(action.get("guards", []))]
    out += [(f"effects.{k}", x) for k, x in sorted((action.get("effects") or {}).items())]
    return out


def entry_expr(action: dict, at: str):
    for a, x in entries(action):
        if a == at:
            return x
    raise SiteError(f"{action.get('name')}: no guard or effect {at}")


def def_reach(facts: dict) -> dict[str, set]:
    """For each non-ghost definition, the non-ghost definitions its evaluation can call (itself included)."""
    defs = {n: d for n, d in (facts.get("defs") or {}).items() if not d.get("ghost")}
    direct = {n: {c for c, _, _ in call_positions(d["body"], defs)} for n, d in defs.items()}
    out = {}
    for n in defs:
        seen, todo = set(), [n]
        while todo:
            y = todo.pop()
            if y in seen:
                continue
            seen.add(y)
            todo.extend(direct[y] - seen)
        out[n] = seen
    return out


def is_def_site(site: dict) -> bool:
    occ = site.get("occurrences") or []
    kinds = {o["where"].startswith("defs.") for o in occ}
    if len(kinds) > 1:
        raise SiteError(f"site {site['id']}: occurrences in definitions and in actions at once")
    return kinds == {True}


def site_defs(site: dict) -> list[str]:
    return sorted({o["where"].split(".")[1] for o in site["occurrences"]})


def reaching(facts: dict, site: dict) -> dict[str, list[str]]:
    """Definition f -> the site's definitions its evaluation reaches (non-ghost f only)."""
    D = site_defs(site)
    return {f: [d for d in D if d in r] for f, r in sorted(def_reach(facts).items()) if any(d in r for d in D)}


# ------------------------------------------------------------------ R8, R9: hit points
def _action_hits(facts: dict, site: dict, real: set) -> dict[tuple, dict]:
    reasons = {str(k): v for k, v in (facts.get("reasons") or {}).items()}
    acts = {a["name"]: a for a in facts["actions"]}
    out: dict[tuple, dict] = {}
    for o in site["occurrences"]:
        a = acts.get(o["action"])
        if a is None:
            raise SiteError(f"site {site['id']}: occurrence in {o['action']}, which is not an action")
        where = o["where"]
        at = where.split(".")[0] if where.startswith("guards[") else where
        hit = (at, "occurrence")
        for i, g in enumerate(a.get("guards", [])):
            if f"guards[{i}]" == at:
                break
            if "require" in g and F.span(g.get("src")) == site["span"] and reasons.get(str(g.get("reason"))) in real:
                hit = (f"guards[{i}]", "realization_check")
                break
        cur = out.setdefault((a["name"], hit[0]), {"action": a["name"], "at": hit[0], "kind": hit[1], "occurrences": []})
        if cur["kind"] != hit[1]:
            raise SiteError(f"site {site['id']}: {a['name']} {hit[0]} is both an occurrence and a realization check")
        cur["occurrences"].append(where)
    return out


def _def_hits(facts: dict, site: dict) -> dict[tuple, dict]:
    reach = reaching(facts, site)
    out: dict[tuple, dict] = {}
    for a in facts["actions"]:
        for at, e in entries(a):
            cs = call_positions(e, reach)
            if cs:
                f = cs[0][0]
                d = reach[f][0]
                out[(a["name"], at)] = {"action": a["name"], "at": at, "kind": "call", "via": [f] + ([d] if f != d else [])}
    return out


def hits_internal(facts: dict, site: dict, real: set) -> list[dict]:
    hs = _def_hits(facts, site) if is_def_site(site) else _action_hits(facts, site, real)
    return [hs[k] for k in sorted(hs)]


def hit_points(facts: dict, site: dict, real: set) -> list[dict]:
    """The DERIVATION hits of an I13 site: [{"action", "at", "kind"[, "via"]}] sorted by (action, at)."""
    return [{k: h[k] for k in ("action", "at", "kind", "via") if k in h} for h in hits_internal(facts, site, real)]


# ------------------------------------------------------------------ the site spec (statement ref site:<id>)
def basis(site: dict) -> dict:
    return {"kind": "site", "site_id": site["id"], "model": site["model"], "span": site["span"], "expr": site["expr"]}


def site_spec(site: dict, hits: list[dict], extracted=None) -> dict:
    """What the ref "site:<id>" hashes: the template, the basis element and the hits as DERIVATION.json lists them;
    with "extracted" when the milestone re-derives SORT-site laws on extracted facts (holon.sorts.reextract, I20)."""
    out = {"template": TEMPLATE, "template_version": TEMPLATE_VERSION,
           "basis": {"site_id": site["id"], "model": site["model"], "span": site["span"], "expr": site["expr"]},
           "hits": hits}
    if extracted is not None:
        out["extracted"] = extracted
    return out


def recompute_sites(model: str, facts: dict, builtins: dict) -> dict[str, dict]:
    """The I13 sites of a holon-facts/0.2 document, recomputed from the facts with I13's own walk and span rule
    (holon.sorts.flow, holon.sorts.assign.site_span): site id -> {id, model, span, expr, occurrences}. Sorts are
    not recomputed (they need the whole pass); the frozen assignment carries them."""
    prog = F.walk(model, facts, builtins)
    groups: dict = {}
    for ev in prog.events:
        if ev[0] != "sub":
            continue
        _, node, _l, _r, _o, ctx = ev
        sp = site_span(model, facts, ctx, node)
        key = (sp, canonical(node))
        g = groups.setdefault(key, {"node": node, "occ": set()})
        g["occ"].add((ctx.actor, ctx.where))
    out = {}
    for (sp, ckey), g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        sid = f"{model}:{sp}:{hashlib.sha256(ckey).hexdigest()[:8]}"
        out[sid] = {"id": sid, "model": model, "span": sp, "expr": g["node"],
                    "occurrences": [{"action": a, "where": w} for a, w in sorted(g["occ"])]}
    return out


def site_ref(site_id: str, law: dict, facts: dict, builtins: dict, root: Path | str | None = None):
    """The object the statement ref "site:<site_id>" of a law hashes, recomputed from the facts and the sidecar of
    the law's milestone (no derive output): the site spec, or {"absent": site_id} when the facts hold no such site,
    or {"error": text} when the site cannot be read."""
    try:
        model, span, _ = split_site_id(site_id)
        sites = recompute_sites(model, facts, builtins)
        site = sites.get(site_id)
        if site is None:
            return {"absent": site_id}
        ms = str(law.get("milestone") or "M2")
        _, _, real = load_sidecar(ms, root)
        hs = hit_points(facts, site, real)
        from . import reextract
        return site_spec(site, hs, reextract.site_evidence(ms, root, law.get("facts"), site, hs))
    except (SiteError, F.FlowError, KeyError, TypeError, ValueError, IndexError, OSError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ------------------------------------------------------------------ laws (the producer holon.rules runs)
def law_ir(site: dict, milestone: str, facts_rel: str, facts_sha: str, params: list[tuple[str, str]],
           rule_catalog_version: str, entry_points: list[str]) -> dict:
    """The holon-ir/0.3 law of a site. params: the oracle parameters the model threads, (name, Fn<A,B>), in sidecar
    order."""
    binders = [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"}]
    for p, ty in params:
        if p in ("s", "a"):
            raise SiteError(f"oracle parameter {p} would shadow a binder of the site law")
        binders.append({"q": "forall", "name": p, "type": ty})
    obl = site.get("obligation")
    return {
        "ir_version": "holon-ir/0.3", "law_id": law_id(site["id"]), "milestone": milestone, "rule": RULE,
        "subform": SUBFORM, "rule_catalog_version": rule_catalog_version, "facts": facts_rel, "facts_sha256": facts_sha,
        "notes": (f"SORT-site law (holon.sorts.sites, rules R7-R10): every evaluation of the subtraction "
                  f"{render_dsl(site['expr'])} at {site['span']} (sort {site['sort']}, realized in "
                  f"{site['realized_in']}, obligation {obl or 'none'}) while action a runs from a reachable state s has "
                  f"minuend >= subtrahend; entry points: {', '.join(entry_points) or 'none'}. Provenance: "
                  "DERIVATION.json."),
        "statement": {"binders": binders, "assume": [],
                      "claim": {"eq": [{"site": site["id"], "on": {"var": "a"}, "from": {"var": "s"}}, {"bool": True}]},
                      "scope": {"kind": "unbounded"}},
    }


def render_dsl(e) -> str:
    """A facts DSL expression as text (for notes)."""
    if isinstance(e, bool):
        return "true" if e else "false"
    if isinstance(e, (int, str)):
        return str(e)
    if not isinstance(e, list) or not e:
        return repr(e)
    op = e[0]
    if op in ("+", "-", "<", "<=", ">", ">=", "==", "!=", "&&", "||") and len(e) >= 3:
        return "(" + f" {op} ".join(render_dsl(x) for x in e[1:]) + ")"
    if op == "!":
        return "!" + render_dsl(e[1])
    if op == "?":
        return f"({render_dsl(e[1])} ? {render_dsl(e[2])} : {render_dsl(e[3])})"
    if op == "call":
        return f"{e[1]}(" + ", ".join(render_dsl(x) for x in e[2:]) + ")"
    if op == "get":
        return f"{render_dsl(e[1])}.{e[2]}"
    return json.dumps(e, sort_keys=True)


def produce(ctx) -> list[tuple[dict, dict]]:
    """The SORT-site producer (holon.rules.CATALOG["SORT"]["site"]): for every holon-facts/0.2 document of the
    derivation and every I13 site of it realized in Nat, (law, DERIVATION entry without its statement hash).

    ctx: holon.rules.Context (milestone, root, documents, the frozen assignment, the sidecar's reasons, the oracle
    parameters each document's model threads, the rule catalog version)."""
    out = []
    for doc in ctx.documents:
        if doc.facts.get("facts_version") != "holon-facts/0.2":
            continue
        sites = [s for s in ctx.assignment.get("sites", []) if s.get("model") == doc.model and s.get("realized_in") == "Nat"]
        live = recompute_sites(doc.model, doc.facts, doc.builtins)
        for s in sites:
            got = live.get(s["id"])
            if got is None or got["occurrences"] != sorted(s["occurrences"], key=lambda o: (o["action"], o["where"])):
                raise StaleSites(f"the assignment's site {s['id']} is not the site the facts give now "
                                 f"({'absent' if got is None else 'other occurrences'}): a stale assignment")
            hs = hit_points(doc.facts, s, ctx.real)
            eps = sorted({h["action"] for h in hs})
            law = law_ir(s, ctx.milestone, doc.rel, doc.sha256, doc.params, ctx.rule_catalog_version, eps)
            entry = {"law_id": law["law_id"], "rule": RULE, "subform": SUBFORM, "facts": doc.rel, "basis": basis(s),
                     "sort": s["sort"], "obligation": s["obligation"], "realized_in": s["realized_in"],
                     "entry_points": eps, "hits": hs}
            from . import reextract
            ev = reextract.site_evidence(ctx.milestone, ctx.root, doc.rel, s, hs)
            if ev is not None:   # re-derived on extracted facts (I20): the evidence the site ref hashes
                entry["extracted"] = ev
            out.append((law, entry))
        # every site of the document must instrument: the ghost section is generated (and discarded) here
        mine = [(law, e) for law, e in out if e["facts"] == doc.rel]
        if mine:
            m = doc.machine()
            try:
                model_text = m.generate(doc.sha256, True)
            except FactsError as e:
                raise SiteError(f"{doc.rel}: the model cannot be generated: {e}") from e
            g = Ghost(m, doc.facts, ctx.real)
            g.section([e for _, e in mine])
            g.check_names(model_text)
    return out


# ------------------------------------------------------------------ the ghost section
class Ghost:
    """Generates the ghost section of one document from DERIVATION entries (module docstring). The plan of every
    generated chain is kept in self.plan for the proof generators that mirror it."""

    def __init__(self, m: Machine, facts: dict, real: set):
        self.m, self.f, self.real = m, facts, real
        self.acts = {a["name"]: a for a in facts["actions"]}
        self.out: list[str] = []
        self.names: list[str] = []
        self.plan: dict = {}

    # ---------------------------------------------------------- helpers
    def define(self, name: str, lines: list[str]) -> None:
        if name in self.names:
            raise SiteError(f"two ghost definitions would be named {name}")
        self.names.append(name)
        self.out += lines + [""]

    def check_names(self, model_text: str) -> None:
        """No ghost definition may share a name with a definition or type of the model above the marker."""
        taken = set(re.findall(r"(?m)^(?:def|type)\s+(\w+)", model_text))
        clash = sorted(taken & set(self.names))
        if clash:
            raise SiteError(f"ghost definitions would shadow model definitions: {clash}")

    def ext(self, e, env: dict, what: str) -> tuple[str, str]:
        try:
            return self.m.ex(e, env)
        except FactsError as err:   # R10: a free variable not bound where the hit is evaluated
            raise SiteError(f"{what}: {err}") from err

    def ex(self, e, env: dict, what: str) -> str:
        return self.ext(e, env, what)[0]

    def guarded(self, conds: tuple, base: str, env: dict, skip: str, what: str) -> str:
        """base under its path condition: one ite per condition, outermost first; `skip` where it is not evaluated."""
        out = base
        for c, pol in reversed(conds):
            ct = self.ex(c, env, what)
            out = f"ite(Bool, {ct}, {out}, {skip})" if pol else f"ite(Bool, {ct}, {skip}, {out})"
        return out

    @staticmethod
    def join(parts: list[str], hit: bool) -> str:
        seen = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        if not seen:
            return "False{}" if hit else "True{}"
        out = seen[-1]
        for p in reversed(seen[:-1]):
            out = f"Bool.{'or' if hit else 'and'}({p}, {out})"
        return out

    def nonneg(self, node, env: dict, what: str) -> str:
        if not (isinstance(node, list) and len(node) == 3 and node[0] == "-"):
            raise SiteError(f"{what}: {node} is not a subtraction")
        return f"Nat.is_le({self.ex(node[2], env, what)}, {self.ex(node[1], env, what)})"

    # ---------------------------------------------------------- one law
    def section(self, laws: list[dict]) -> str:
        for e in sorted(laws, key=lambda e: e["law_id"]):
            self.law(e)
        return "\n".join(self.out).rstrip("\n") + "\n"

    def law(self, entry: dict) -> None:
        x = ghost_x(entry["law_id"])
        b = entry["basis"]
        site = {"id": b["site_id"], "model": b["model"], "span": b["span"], "expr": b["expr"]}
        occ = self.occurrences(site)
        site["occurrences"] = occ
        hs = hits_internal(self.f, site, self.real)
        got = [{k: h[k] for k in ("action", "at", "kind", "via") if k in h} for h in hs]
        if got != entry["hits"]:
            raise SiteError(f"{entry['law_id']}: the facts give the hits {got}, DERIVATION.json says {entry['hits']}")
        plan = {"law_id": entry["law_id"], "x": x, "site_id": site["id"], "site": f"site_{x}", "hit": f"hit_{x}",
                "threaded": list(self.m.threaded), "defs": {}, "actions": {}}
        self.plan[entry["law_id"]] = plan
        defsite = is_def_site(site)
        reach = reaching(self.f, site) if defsite else {}
        for hit in (False, True):
            if defsite:
                self.def_ghosts(x, site, reach, hit, plan)
            by_action: dict[str, list] = {}
            for h in hs:
                by_action.setdefault(h["action"], []).append(h)
            for a in sorted(by_action):
                self.chain(x, site, reach, self.acts[a], by_action[a], hit, plan)
            self.dispatch(x, sorted(by_action), hit)

    def occurrences(self, site: dict) -> list[dict]:
        """The site's occurrences, recomputed from the facts (I13's walk and span rule)."""
        live = recompute_sites(site["model"], self.f, self.m.lib.builtins)
        got = live.get(site["id"])
        if got is None:
            raise SiteError(f"site {site['id']}: the facts hold no such site")
        return got["occurrences"]

    # ---------------------------------------------------------- definition ghosts
    def def_ghosts(self, x: str, site: dict, reach: dict, hit: bool, plan: dict) -> None:
        D = set(site_defs(site))
        order: list[str] = []

        def visit(f: str, stack: tuple) -> None:
            if f in order:
                return
            if f in stack:
                raise SiteError(f"site {site['id']}: definition {f} is recursive")
            for g, _, _ in call_positions(self.f["defs"][f]["body"], reach):
                if g != f:
                    visit(g, stack + (f,))
            order.append(f)
        for f in reach:
            visit(f, ())
        pre = "gdh" if hit else "gd"
        skip = "False{}" if hit else "True{}"
        for f in order:
            d = self.f["defs"][f]
            env = {p: t for p, t in d["params"]}
            env.update(self.m.tab_env(self.m.def_uses(f)))
            what = f"site {site['id']} in definition {f}"
            parts, pos = [], []
            if f in D:
                base = "True{}" if hit else self.nonneg(site["expr"], env, what)
                for conds in node_positions(d["body"], site["expr"]):
                    parts.append(self.guarded(conds, base, env, skip, what))
                    pos.append({"kind": "subtraction", "conds": [[c, p] for c, p in conds]})
            for g, n, conds in call_positions(d["body"], reach):
                if g == f:
                    continue
                args = [self.ex(y, env, what) for y in n[2:]] + self.m.tab_args(self.m.def_uses(g))
                parts.append(self.guarded(conds, f"{pre}_{x}_{g}({', '.join(args)})", env, skip, what))
                pos.append({"kind": "call", "callee": g, "args": n[2:], "conds": [[c, p] for c, p in conds]})
            params = ", ".join([f"+{bname(p)}: {bt(t)}" for p, t in d["params"]] + self.m.tab_params(self.m.def_uses(f)))
            name = f"{pre}_{x}_{f}"
            self.define(name, [f"# {'at_site' if hit else 'nonneg'} of {site['span']} in definition {f}".replace("?", ""),
                               f"def {name}({params}) -> Bool:", f"  {self.join(parts, hit)}"])
            plan["defs"].setdefault(f, {"params": [p for p, _ in d["params"]], "positions": pos})[
                "hit" if hit else "site"] = name

    # ---------------------------------------------------------- one action's chain
    def chain(self, x: str, site: dict, reach: dict, a: dict, hs: list[dict], hit: bool, plan: dict) -> None:
        m = self.m
        an = a["name"]
        guards = a.get("guards", [])
        n = len(guards)
        pre = "gh" if hit else "gs"
        stop = "False{}" if hit else "True{}"
        inputs = [(i, t) for i, t in a["inputs"]]
        if any(i in m.stypes for i, _ in inputs):
            raise SiteError(f"{an}: an input shadows a state field, which the ghost chain cannot bind")
        at_guard: dict[int, list] = {}
        at_effects: list = []
        for h in hs:
            if h["at"].startswith("guards["):
                at_guard.setdefault(int(h["at"][7:-1]), []).append(h)
            else:
                at_effects.append(h)
        last = n if at_effects else max(at_guard)
        env0 = {**{f: t for f, t in m.state}, **dict(inputs), **m.tab_env(m.threaded)}
        fv = m.fv
        what = f"site {site['id']} in {an}"
        ap = plan["actions"].setdefault(an, {"inputs": [i for i, _ in inputs], "hits": [], "steps": []})

        def hit_exprs(hl: list[dict]) -> list:
            """(kind, expression, positions) of what is evaluated at these hits."""
            out = []
            for h in hl:
                if h["kind"] == "call":
                    e = entry_expr(a, h["at"])
                    out.append(("call", e, call_positions(e, reach)))
                else:
                    for w in h["occurrences"]:
                        e = entry_expr(a, w.split(".")[0] if w.startswith("guards[") else w)
                        out.append(("node", e, node_positions(e, site["expr"])))
            return out

        def hit_fv(hl: list[dict]) -> set:
            s = set()
            for kind, _, ps in hit_exprs(hl):
                for item in ps:
                    if kind == "call":
                        g, node, conds = item
                        for y in node[2:]:
                            s |= fv(y)
                        s |= set(m.tab_args(m.def_uses(g)))
                    else:
                        conds = item
                        s |= fv(site["expr"])
                    for c, _ in conds:
                        s |= fv(c)
            return s

        def obligation(hl: list[dict], env: dict) -> str:
            skip = stop
            parts = []
            for kind, _, ps in hit_exprs(hl):
                for item in ps:
                    if kind == "call":
                        g, node, conds = item
                        args = [self.ex(y, env, what) for y in node[2:]] + m.tab_args(m.def_uses(g))
                        base = f"{'gdh' if hit else 'gd'}_{x}_{g}({', '.join(args)})"
                    else:
                        conds = item
                        base = "True{}" if hit else self.nonneg(site["expr"], env, what)
                    parts.append(self.guarded(conds, base, env, skip, what))
            return self.join(parts, hit)

        if not hit:
            for h in hs:
                ap["hits"].append({"at": h["at"], "kind": h["kind"],
                                   "evaluated_at": "effects" if h["at"].startswith("effects.") else h["at"],
                                   "positions": [{"kind": k, "at": h["at"],
                                                  "conds": [[c, p] for c, p in (it[2] if k == "call" else it)],
                                                  **({"callee": it[0], "args": it[1][2:]} if k == "call" else {})}
                                                 for k, _, ps in hit_exprs([h]) for it in ps]})

        memo: dict = {}

        def needed(i: int, done: bool) -> set:
            if (i, done) in memo:
                return memo[(i, done)]
            if i == n:
                s = hit_fv(at_effects) if last == n else set()
            elif i == last:
                s = set() if done else hit_fv(at_guard[i])
            else:
                s = set(needed(i + 1, False))
                g = guards[i]
                if "let" in g:
                    s.discard(g["let"])
                    s |= fv(g["expr"])
                else:
                    s |= fv(g["require"])
                if i in at_guard and not done:
                    s |= hit_fv(at_guard[i])
            memo[(i, done)] = s
            return s

        def params_of(local: dict, live: set) -> list[str]:
            return [v for v in local if v in live]

        def ptext(local: dict, ps: list[str]) -> list[str]:
            return [f"+{bname(v)}: {bt(local[v])}" for v in ps]

        def seq(i: int, scope: dict, done: bool) -> list[str]:
            local = dict(scope)
            lines: list[str] = []
            while True:
                if i == n:
                    lines.append(obligation(at_effects, local))
                    return lines
                if i in at_guard and not done:
                    ob = obligation(at_guard[i], local)
                    if i == last:
                        lines.append(ob)
                        return lines
                    ps = params_of(local, needed(i, True))
                    name = f"{pre}_{x}_{an}_k{i}"
                    body = seq(i, {v: local[v] for v in ps}, True)
                    self.define(name, [f"def {name}({', '.join(ptext(local, ps))}) -> Bool:"] + ["  " + y for y in body])
                    if not hit:
                        ap["steps"].append({"kind": "continuation", "guard": i, "site": name, "params": ps})
                    else:
                        _name_hit(i, "continuation", name)
                    lines.append(f"Bool.{'or' if hit else 'and'}({ob}, {name}({', '.join(bname(v) for v in ps)}))")
                    return lines
                done = False
                g = guards[i]
                if "let" in g and g["let"] not in needed(i + 1, False):   # a let nothing later reads binds nothing
                    i += 1
                    continue
                if "let" in g:
                    xt, ty = self.ext(g["expr"], local, what)
                    lines.append(f"+{bname(g['let'])} = {xt}")
                    local[g["let"]] = ty
                    i += 1
                    continue
                cond = self.ex(g["require"], local, what)
                ps = params_of(local, needed(i + 1, False))
                cv = fresh("c", {bname(v) for v in ps})
                name = f"{pre}_{x}_{an}_{i}"
                body = seq(i + 1, {v: local[v] for v in ps}, False)
                self.define(name, [f"# {g.get('src', '')}".replace("?", ""),
                                   f"def {name}({', '.join([f'{cv}: Bool'] + ptext(local, ps))}) -> Bool:",
                                   f"  match {cv}:", "    case False{}:", f"      {stop}", "    case True{}:"]
                            + ["      " + y for y in body])
                if not hit:
                    ap["steps"].append({"kind": "decision", "guard": i, "site": name, "cond": g["require"], "params": ps})
                else:
                    _name_hit(i, "decision", name)
                lines.append(f"{name}({', '.join([cond] + [bname(v) for v in ps])})")
                return lines

        def _name_hit(i: int, kind: str, name: str) -> None:
            for st in ap["steps"]:
                if st["guard"] == i and st["kind"] == kind:
                    st["hit"] = name

        body = seq(0, env0, False)
        taken = {bname(f) for f, _ in m.state} | {bname(i) for i, _ in inputs} | set(m.tab_args(m.threaded))
        sv = fresh("s", taken)
        params = [f"{sv}: HSt"] + [f"+{bname(i)}: {bt(t)}" for i, t in inputs] + m.tab_params(m.threaded)
        spat = ", ".join("+" + bname(f) for f, _ in m.state)
        name = f"{pre}_{x}_{an}"
        self.define(name, [f"# {'at_site' if hit else 'nonneg'} of {site['span']} while {an} runs".replace("?", ""),
                           f"def {name}({', '.join(params)}) -> Bool:", f"  match {sv}:", f"    case HSt{{{spat}}}:"]
                    + ["      " + y for y in body])
        ap["hit_entry" if hit else "site_entry"] = name

    # ---------------------------------------------------------- site_<x>, hit_<x>
    def dispatch(self, x: str, entry_points: list[str], hit: bool) -> None:
        m = self.m
        T = "".join(", " + p for p in m.tab_params(m.threaded))
        TA = m.tab_args(m.threaded)
        fn = f"{'hit' if hit else 'site'}_{x}"
        lines = [f"def {fn}(a: HAct, s: HSt{T}) -> Bool:", "  match a:"]
        for a in self.f["actions"]:
            ins = [fresh(bname(i), {"a", "s"} | set(TA)) for i, _ in a["inputs"]]
            if a["name"] in entry_points:
                args = ["s"] + ins + TA
                lines += [f"    case A_{a['name']}{{{', '.join('+' + i for i in ins)}}}:",
                          f"      {'gh' if hit else 'gs'}_{x}_{a['name']}({', '.join(args)})"]
            else:
                lines += [f"    case A_{a['name']}{{{', '.join('_' for _ in ins)}}}:", f"      {'False{}' if hit else 'True{}'}"]
        self.define(fn, [f"# {'at_site' if hit else 'nonneg'}: SORT-site law {LAW_PREFIX}{x}"] + lines)


# ------------------------------------------------------------------ the instrumented model
def _doc_entries(facts_path: Path, derivation: dict, root: Path) -> tuple[str, list[dict]]:
    try:
        rel = facts_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = facts_path.as_posix()
    return rel, sorted((e for e in derivation.get("laws", []) if e.get("facts") == rel), key=lambda e: e["law_id"])


def _paths(facts_path, root, anchor) -> tuple[Path, Path, Path]:
    root = Path(root or ROOT)
    fp = Path(facts_path)
    fp = fp if fp.is_absolute() else root / fp
    an = Path(anchor) if anchor else fp
    an = an if an.is_absolute() else root / an
    return root, fp, an


def run_machine(milestone: str, facts_path: Path, root: Path, anchor: Path | None = None) -> tuple[Machine, dict, str]:
    """(machine, facts, model text): the model holon builds for a run of milestone M on the document (Reach, the
    milestone's permissions and oracle tables), as holon.mpipeline.milestone_model / CompiledMachine.build generate
    it. anchor: the facts file whose target libraries and oracle sidecar apply when facts_path stands in for it (a
    --facts override such as a mutated copy elsewhere); by default facts_path itself."""
    from ..gen.oracles import Oracles
    from ..mpipeline import m2plus
    data = Path(facts_path).read_bytes()
    facts = json.loads(data.decode("utf-8"))
    an = Path(anchor or facts_path)
    orc = Oracles.for_milestone(milestone, an, root)
    plus = m2plus(milestone)
    m = Machine(facts, an, oracles=orc, m2plus=plus)
    return m, facts, m.generate(hashlib.sha256(data).hexdigest(), plus)


def instrumented_model(facts_path, derivation: dict, root=None, anchor=None) -> str:
    """The model holon builds for a run of derivation["milestone"] on the document (holon.mpipeline), then the line
    GHOST_MARKER, then the ghost section of the document's SORT-site laws in the derivation (module docstring).
    anchor: as for run_machine; the derivation's laws are those of the anchor's path."""
    root, fp, an = _paths(facts_path, root, anchor)
    _, laws = _doc_entries(an, derivation, root)
    m, facts, text = run_machine(str(derivation["milestone"]), fp, root, an)
    _, _, real = load_sidecar(str(derivation["milestone"]), root)
    helpers = len(m.helpers)
    g = Ghost(m, facts, real)
    ghost = g.section(laws) if laws else ""
    g.check_names(text)
    extra = m.helpers[helpers:]   # record helpers the ghost needs that the model did not (none in practice)
    return text.rstrip("\n") + "\n\n" + GHOST_MARKER + "\n" + "".join(x + "\n" for x in extra) + ghost


def ghost_plan(facts_path, derivation: dict, root=None, anchor=None) -> dict:
    """law id -> the structure of its ghost chains (Ghost.plan): per entry point its decision helpers (guard index,
    condition, parameters, site and hit helper names), continuations and hits with the path conditions of every
    evaluation; per definition reaching a definition site its ghosts and positions. For proof generators that
    mirror the chains (holon.gen.mproofs.coercion_guard)."""
    root, fp, an = _paths(facts_path, root, anchor)
    _, laws = _doc_entries(an, derivation, root)
    m, facts, _ = run_machine(str(derivation["milestone"]), fp, root, an)
    _, _, real = load_sidecar(str(derivation["milestone"]), root)
    g = Ghost(m, facts, real)
    g.section(laws)
    return g.plan
