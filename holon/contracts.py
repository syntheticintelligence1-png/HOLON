"""Intent contracts and G10 (BUILD_PLAN I33; I64 = I33a; whitepaper §5.9, §5.8's volatile-view exception, §9.3 G10).

The contract is the docstring of tests_m3/test_contracts.py, rules K1-K10. tests_m3/_i64.py writes K1-K3, K5, K6 and K9
out a second time; this module never imports it.

  laws/CONTRACTS/<id>.json       a contract (K1): kind "intended" (scope, l_weak) or "volatile_view" (view)
  laws/CONTRACTS/REGISTRY.json   {"registry_version", "contracts": {id: {"milestone", "kind", "sha256"}}} (K2)
  laws/<M>/L_contract_<id>.json  an intended contract's L_weak as a law of its milestone (K3), which `holon run`
                                 decides like every other law (K4)
  results/<M>/contracts.json     every contract of M with its state and the records it marked (K5)

An intended contract is proved when its derived law is its l_weak over the facts file as it is now and that law's
record is PROVED over the same file, for the same statement hash. Every REFUTED record of a law in the scope of a proved
contract is then marked: filter_bin "intended_bounded" and intended {contract, l_weak, replaces}, replaces holding the
bin the mark replaced, so that `apply` can take the mark off again. A contract whose L_weak is not proved marks nothing.

Record directories (I65 = I33b, tests_m3/test_o12.py rules O5-O7): a milestone's records are results/<M> and, when it is a
directory, results/<M>/extracted_m1 (holon.differential's records of the M1 laws over the milestone's window view). A
scope law with a record in both is ambiguous: apply refuses and G10 fails. A REFUTED record is licensed for a mark only
when its facts_sha256 is the sha256 of the contract's facts file now (the L_weak and the law it bounds are statements
about one model). A record is named by its path relative to results/<M>: "L_x", or "extracted_m1/L_x".

  python -m holon contracts derive --milestone M [--check]   K3
  python -m holon contracts apply --milestone M [--check]    K5 without deciding (holon run's last step applies it too)
  Exit codes: 0 done (or --check reproduced); 1 --check differs; 2 refused, nothing written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-contract/0.1"
REGISTRY_VERSION = "holon-contracts-registry/0.1"
STATUS_VERSION = "holon-contracts/0.1"
KINDS = ("intended", "volatile_view")
RULES = ("PAR", "UNDO", "NAT", "SYM", "FACT", "SORT", "DISCH", "OWN", "INTENT")
EVIDENCE = ("E1", "E2", "E3", "E4", "E5", "E6")
COMMON = {"contract_version", "id", "kind", "milestone", "rule", "facts", "maps_to", "evidence", "rationale"}
EXTRA = {"intended": {"scope", "l_weak"}, "volatile_view": {"view"}}
NOT_APPLICABLE = ("M0", "M1")
MARK = "intended_bounded"
VIEW = "extracted_m1"   # holon.differential's records of the M1 laws over a milestone's window view (I65)
NOT_APPLICABLE_WHY = ("{m} holds no intent contracts: they start at M2 (BUILD_PLAN §2 invariant 10 and §4 I33; "
                      "whitepaper 5.9; Q15 is still open)")


class Refused(Exception):
    """A missing or malformed input: the command writes nothing and exits 2."""


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _text(doc) -> str:
    """Law files, records and results/<M>/contracts.json: the repository's JSON form (holon.mpipeline)."""
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _as_found(old: str, doc) -> str:
    """doc in the formatting its file already has (indent 2, keys sorted; ASCII escaping as found:
    holon.refute_m3.write_record)."""
    for ea in (True, False):
        if json.dumps(json.loads(old), indent=2, sort_keys=True, ensure_ascii=ea) + "\n" == old:
            return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=ea) + "\n"
    return _text(doc)


def contracts_dir(root: Path) -> Path:
    return Path(root) / "laws" / "CONTRACTS"


def contract_files(root: Path) -> list:
    d = contracts_dir(root)
    return sorted(p for p in d.glob("*.json") if p.name != "REGISTRY.json") if d.is_dir() else []


def _contracts(root: Path) -> list:
    """[(path, document or None when the file is not JSON)] for every contract file."""
    out = []
    for p in contract_files(root):
        try:
            out.append((p, _load(p)))
        except (OSError, ValueError):
            out.append((p, None))
    return out


def registry(root: Path) -> dict:
    """K2: the registry's entries ({} when there is no REGISTRY.json); Refused when it is not a registry."""
    p = contracts_dir(root) / "REGISTRY.json"
    if not p.is_file():
        return {}
    try:
        doc = _load(p)
    except ValueError:
        doc = None
    if not isinstance(doc, dict) or doc.get("registry_version") != REGISTRY_VERSION \
            or not isinstance(doc.get("contracts"), dict):
        raise Refused(f"REGISTRY.json: not a {REGISTRY_VERSION} document")
    return doc["contracts"]


def milestone_of(c) -> str | None:
    """The milestone a contract file belongs to: its milestone field when that names one G10 applies to (M<n> or T<n>,
    not M0 or M1), else None."""
    m = c.get("milestone") if isinstance(c, dict) else None
    return m if isinstance(m, str) and re.fullmatch(r"[MT][0-9]+", m) and m not in NOT_APPLICABLE else None


def repo_path(x) -> bool:
    """K1: a repository path: relative, without '..'."""
    return isinstance(x, str) and bool(x) and not Path(x).is_absolute() and ".." not in Path(x).parts


def l_weak_law(lw) -> dict:
    """K1: the law K3 would derive from an l_weak, with neutral values in every other field, so that a schema error
    can only be the statement's."""
    return {"ir_version": "holon-ir/0.3", "law_id": "L_contract_C_check", "milestone": "T0", "rule": "INTENT",
            "subform": "intended_weak", "rule_catalog_version": "holon-rules/0.1", "facts": "facts.json",
            "facts_sha256": "0" * 64, "statement": lw, "maps_to": "check", "evidence": ["E1"], "notes": "check"}


def scope_of(c) -> list:
    """The sorted law ids of an intended contract's scope ([] for a view, or a scope that is not a list of ids)."""
    s = c.get("scope") if isinstance(c, dict) and c.get("kind") == "intended" else None
    laws = s.get("laws") if isinstance(s, dict) else None
    return sorted(x for x in laws if isinstance(x, str)) if isinstance(laws, list) else []


# ---------------------------------------------------------------------------------------------------- K1, K9
def problems(c, root: Path = ROOT, stem: str | None = None) -> list:
    """Why a contract file is not valid (K1 format, K9 the volatile view's function), [] when it is. The texts are
    those of tests_m3/_i64.problems, which results/<M>/contracts.json repeats."""
    out = []
    if not isinstance(c, dict):
        return ["not a JSON object"]
    kind = c.get("kind")
    if kind not in KINDS:
        return [f"kind {kind!r} is not one of {KINDS}"]
    want = COMMON | EXTRA[kind]
    if set(c) != want:
        out.append(f"fields {sorted(set(c) ^ want)} are missing or not allowed")
    if c.get("contract_version") != VERSION:
        out.append("contract_version")
    cid = c.get("id")
    pref = "C_" if kind == "intended" else "V_"
    if not isinstance(cid, str) or not re.fullmatch(r"[CV]_[A-Za-z0-9_]+", cid) or not cid.startswith(pref):
        out.append(f"id {cid!r} (an intended contract is C_..., a volatile view V_...)")
    if stem is not None and cid != stem:
        out.append(f"id {cid!r} is not the file name {stem!r}")
    m = c.get("milestone")
    if not isinstance(m, str) or not re.fullmatch(r"[MT][0-9]+", m):
        out.append("milestone")
    elif m in NOT_APPLICABLE:
        out.append(f"milestone {m} (no contracts on M0 and M1)")
    if c.get("rule") not in RULES:
        out.append("rule")
    facts = c.get("facts")
    if not repo_path(facts) or not (Path(root) / facts).is_file():
        out.append(f"facts {facts!r} is not a file at a relative repository path")
    ev = c.get("evidence")
    if not isinstance(ev, list) or not ev or any(not isinstance(e, str) or e not in EVIDENCE for e in ev):
        out.append("evidence")
    for k in ("maps_to", "rationale"):
        if not isinstance(c.get(k), str) or not c[k].strip():
            out.append(k)
    if kind == "intended":
        scope = c.get("scope")
        laws = scope.get("laws") if isinstance(scope, dict) else None
        if not isinstance(scope, dict) or list(scope) != ["laws"] or not isinstance(laws, list) or not laws \
                or any(not isinstance(x, str) or not re.fullmatch(r"L[0-9]?_[A-Za-z0-9_]+", x) for x in laws):
            out.append("scope (exactly {\"laws\": [law ids]}, non-empty)")
        lw = c.get("l_weak")
        if not isinstance(lw, dict) or not {"binders", "claim"} <= set(lw):
            out.append("l_weak (an IR 0.3 statement)")
        else:
            from .schema import errors
            if errors(l_weak_law(lw), _load(ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json")):
                out.append("l_weak (an IR 0.3 statement)")
    else:
        v = c.get("view")
        if not isinstance(v, dict) or set(v) != {"facts", "function", "result"} or type(v.get("result")) is not int \
                or not repo_path(v.get("facts")) or not isinstance(v.get("function"), str):
            out.append("view (exactly {facts, function, result}, result an integer)")
        else:
            try:
                doc = _load(Path(root) / v["facts"])
                res = ((doc.get("go") or {}).get("slices") or {}).get("results") or []
                if not any(isinstance(r, dict) and r.get("function") == v["function"]
                           and type(r.get("result")) is int and r.get("result") == v["result"] for r in res):
                    out.append(f"view: {v['facts']} has no slice result {v['function']} #{v['result']}")
            except (OSError, ValueError, AttributeError):
                out.append(f"view: {v['facts']} is not a readable document")
    return out


# ---------------------------------------------------------------------------------------------------- K2, K3
def content_sha256(c: dict) -> str:
    """K2: sha256 of the contract's canonical JSON (sorted keys, no whitespace)."""
    return _sha256(json.dumps(c, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def law_id(cid: str) -> str:
    return f"L_contract_{cid}"


def derived_law(c: dict, root: Path = ROOT) -> dict:
    """K3: an intended contract's L_weak as a law of its milestone, over its facts file as it is now."""
    facts = c["facts"]
    return {"ir_version": "holon-ir/0.3", "law_id": law_id(c["id"]), "milestone": c["milestone"],
            "rule": c["rule"], "subform": "intended_weak", "rule_catalog_version": "holon-rules/0.1",
            "facts": facts, "facts_sha256": _sha256((Path(root) / facts).read_bytes()),
            "statement": c["l_weak"], "maps_to": c["maps_to"], "evidence": c["evidence"],
            "notes": f"L_weak of intent contract {c['id']} (laws/CONTRACTS/{c['id']}.json), derived by holon contracts"}


def derive(milestone: str, root: Path = ROOT, check: bool = False) -> int:
    """K3: laws/<M>/L_contract_<id>.json for every intended contract of M, and no other L_contract_* file. Any invalid
    contract file refuses (2) before anything is written."""
    root = Path(root)
    found = [(p.name, problems(c, root, p.stem)) for p, c in _contracts(root)]
    bad = [f"{name}: {'; '.join(why)}" for name, why in found if why]
    if bad:
        raise Refused("invalid contracts: " + " | ".join(bad))
    d = root / "laws" / milestone
    want = {}
    for _, c in _contracts(root):
        if c["kind"] == "intended" and c["milestone"] == milestone:
            want[f"{law_id(c['id'])}.json"] = _text(derived_law(c, root))
    have = {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("L_contract_*.json"))} if d.is_dir() else {}
    if check:
        diff = sorted(k for k in set(want) | set(have) if want.get(k) != have.get(k))
        for k in diff:
            print(f"differs: laws/{milestone}/{k}", file=sys.stderr)
        return 1 if diff else 0
    if want:
        d.mkdir(parents=True, exist_ok=True)
    for name, text in sorted(want.items()):
        if have.get(name) != text:
            (d / name).write_text(text, encoding="utf-8")
    for name in sorted(set(have) - set(want)):
        (d / name).unlink()
    print(f"derived {len(want)} contract law(s) for {milestone}" +
          (f"; removed {', '.join(sorted(set(have) - set(want)))}" if set(have) - set(want) else ""))
    return 0


# ---------------------------------------------------------------------------------------------------- K5
def statement_hash(law: dict, root: Path) -> str:
    """The statement hash `holon run` gives the law's record (holon.mpipeline.check_registry_multi's form)."""
    from . import facts as F
    from .gen import oracles as O
    from .gen import refs as R
    rel = law["facts"]
    orc = O.Oracles.for_milestone(law["milestone"], root / rel, root)
    return R.law_hash(law, F.load(root / rel), oracles=orc, root=root)


def states(milestone: str, root: Path = ROOT, results: Path | None = None) -> list:
    """[{"id", "kind", "scope", "state"}] for the contracts of the milestone, by id (K5). state: "proved", "valid" (a
    volatile view), or why neither."""
    root = Path(root)
    rdir = Path(results) if results is not None else root / "results" / milestone
    out = []
    for p, c in _contracts(root):
        if milestone_of(c) != milestone:
            continue
        probs = problems(c, root, p.stem)
        row = {"id": c.get("id"), "kind": c.get("kind"), "scope": scope_of(c)}
        if probs:
            row["state"] = "invalid: " + "; ".join(probs)
        elif c["kind"] == "volatile_view":
            row["state"] = "valid"
        else:
            row["state"] = _intended_state(c, milestone, root, rdir)
        out.append(row)
    return sorted(out, key=lambda r: str(r["id"]))


def _intended_state(c: dict, milestone: str, root: Path, rdir: Path) -> str:
    lid = law_id(c["id"])
    lp, rp = root / "laws" / milestone / f"{lid}.json", rdir / f"{lid}.json"
    if not lp.is_file() or not rp.is_file():
        return "not derived or not decided"
    try:
        law, rec = _load(lp), _load(rp)
    except ValueError:
        return "not derived or not decided"
    now = _sha256((root / c["facts"]).read_bytes())
    if not isinstance(law, dict) or law.get("statement") != c["l_weak"] or law.get("facts_sha256") != now:
        return "stale: the derived law is not the contract's L_weak over the current facts"
    if not isinstance(rec, dict) or rec.get("status") != "PROVED":
        return f"not proved: {rec.get('status') if isinstance(rec, dict) else None}"
    if rec.get("facts_sha256") != now:
        return "stale: decided over other facts"
    try:
        h = statement_hash(law, root)
    except Exception as e:  # noqa: BLE001  (a hash that cannot be computed is not the record's: K5's listed state)
        print(f"holon contracts: {c['id']}: the derived law's statement hash cannot be computed "
              f"({type(e).__name__}: {e})", file=sys.stderr)
        h = None
    if h is None or rec.get("statement_hash") != h:
        return "stale: decided for another statement (the record's statement_hash is not the derived law's)"
    return "proved"


def record_dirs(rdir: Path, root: Path | None = None, milestone: str | None = None) -> list:
    """[(key, directory)] of a milestone's records (O5): the results directory ("") and its extracted_m1 subdirectory
    ("extracted_m1") when that is a directory. When rdir is another tree than root's results/<milestone> (a run's --out)
    and has no extracted_m1 of its own, the committed one under root is read in its place: it is read, never written
    (apply writes only under rdir)."""
    rdir = Path(rdir)
    out = [("", rdir)]
    if (rdir / VIEW).is_dir():
        out.append((VIEW, rdir / VIEW))
    elif root is not None and milestone is not None and (Path(root) / "results" / milestone / VIEW).is_dir():
        out.append((VIEW, Path(root) / "results" / milestone / VIEW))
    return out


def _rel(key: str, lid: str) -> str:
    return f"{key}/{lid}" if key else lid


def _locate(dirs: list, lid: str) -> list:
    return [(k, d) for k, d in dirs if (d / f"{lid}.json").is_file()]


def ambiguous(rows: list, dirs: list) -> list:
    """The sorted scope laws of the intended contracts (rows) with a record in more than one directory (O5)."""
    lids = {lid for s in rows if s["kind"] == "intended" for lid in s["scope"]}
    return sorted(lid for lid in lids if len(_locate(dirs, lid)) > 1)


def _licensed(dirs: list, lid: str, facts_now: str | None) -> str | None:
    """The record path of lid a contract over facts with sha256 facts_now may mark (O5): the law's one record, REFUTED and
    decided over those facts; else None."""
    hits = _locate(dirs, lid)
    if len(hits) != 1 or facts_now is None:
        return None
    k, d = hits[0]
    try:
        r = _load(d / f"{lid}.json")
    except ValueError:
        return None
    if not isinstance(r, dict) or r.get("status") != "REFUTED" or r.get("facts_sha256") != facts_now:
        return None
    return _rel(k, lid)


def _facts_now(root: Path, rows: list) -> dict:
    """{contract id: the sha256 of its facts file now} for the intended contracts among rows (None when unreadable)."""
    docs = {c.get("id"): c for _, c in _contracts(root) if isinstance(c, dict)}
    out = {}
    for s in rows:
        c = docs.get(s["id"])
        try:
            out[s["id"]] = _sha256((root / c["facts"]).read_bytes()) if isinstance(c, dict) else None
        except (OSError, KeyError, TypeError):
            out[s["id"]] = None
    return out


def expected_marks(rows: list, dirs: list, facts: dict) -> dict:
    """{record path: {"contract", "l_weak"}}: every record a proved contract licenses (O5), naming the least id among the
    proved contracts that license it."""
    out = {}
    for s in rows:   # by id
        if s["kind"] != "intended" or s["state"] != "proved":
            continue
        for lid in s["scope"]:
            r = _licensed(dirs, lid, facts.get(s["id"]))
            if r is not None and r not in out:
                out[r] = {"contract": s["id"], "l_weak": law_id(s["id"])}
    return dict(sorted(out.items()))


def status_doc(milestone: str, rows: list, dirs: list, facts: dict):
    """results/<M>/contracts.json, or None when the milestone has no contract. marked: under every proved intended
    contract, the law ids of its scope whose records it licenses (O5)."""
    if not rows:
        return None
    rows = [dict(s, marked=(sorted(l for l in s["scope"] if _licensed(dirs, l, facts.get(s["id"])) is not None)
                            if s["kind"] == "intended" and s["state"] == "proved" else [])) for s in rows]
    return {"contracts_version": STATUS_VERSION, "milestone": milestone, "contracts": rows}


def unmarked(rec: dict, name: str) -> dict:
    """The record without its mark: filter_bin from intended.replaces, intended dropped."""
    if "intended" not in rec and rec.get("filter_bin") != MARK:
        return rec
    i = rec.get("intended")
    if not isinstance(i, dict) or "replaces" not in i or rec.get("filter_bin") != MARK:
        raise Refused(f"{name}: a half-made mark (filter_bin {rec.get('filter_bin')!r}, intended {i!r}); "
                      "rerun holon run for the milestone")
    out = {k: v for k, v in rec.items() if k != "intended"}
    out["filter_bin"] = i["replaces"]
    return out


def marked(rec: dict, mark: dict) -> dict:
    return dict(rec, filter_bin=MARK, intended={**mark, "replaces": rec.get("filter_bin")})


def _within(d: Path, top: Path) -> bool:
    return Path(d).resolve().is_relative_to(Path(top).resolve())


def apply(milestone: str, root: Path = ROOT, results: Path | None = None, check: bool = False) -> int:
    """K5 over the milestone's record directories (O5): unmark every record, mark the ones the proved contracts license,
    write results/<M>/contracts.json (removed when the milestone has no contract). Only a record whose content changes
    is written, in its file's formatting, and only under the results directory (a committed extracted_m1 read for an
    --out tree is never written). A scope law with a record in two directories refuses. M0 and M1: nothing."""
    root = Path(root)
    if milestone in NOT_APPLICABLE:
        return 0
    from .ir import record_files
    rdir = Path(results) if results is not None else root / "results" / milestone
    if not rdir.is_dir():
        raise Refused(f"{rdir} is not a directory")
    rows = states(milestone, root, rdir)
    dirs = record_dirs(rdir, root, milestone)
    amb = ambiguous(rows, dirs)
    if amb:
        raise Refused(f"scope laws with a record in more than one of results/{milestone} and "
                      f"results/{milestone}/{VIEW}: {', '.join(amb)}")
    facts = _facts_now(root, rows)
    marks = expected_marks(rows, dirs, facts)
    writes = {}
    for key, d in dirs:
        if not _within(d, rdir):
            continue
        for p in record_files(d):
            name = _rel(key, p.stem)
            old = p.read_text(encoding="utf-8")
            try:
                cur = json.loads(old)
            except ValueError as e:
                raise Refused(f"{name}.json is not JSON ({e})") from None
            if not isinstance(cur, dict):
                raise Refused(f"{name}.json is not a record")
            rec = unmarked(cur, f"{name}.json")
            if name in marks and rec.get("status") == "REFUTED":
                rec = marked(rec, marks[name])
            if rec != cur:
                writes[p] = _as_found(old, rec)
    sp = rdir / "contracts.json"
    doc = status_doc(milestone, rows, dirs, facts)
    now = sp.read_text(encoding="utf-8") if sp.is_file() else None
    want = _text(doc) if doc is not None else None
    if check:
        def shown(x: Path) -> str:
            return str(x.relative_to(root)) if x.is_relative_to(root) else str(x)
        diff = sorted(shown(p) for p in writes) + ([shown(sp)] if want != now else [])
        for x in diff:
            print(f"differs: {x}", file=sys.stderr)
        return 1 if diff else 0
    for p, text in sorted(writes.items()):
        p.write_text(text, encoding="utf-8")
    if want is None and now is not None:
        sp.unlink()
    elif want is not None and want != now:
        sp.write_text(want, encoding="utf-8")
    if doc is not None:
        print(f"contracts on {milestone}: " + "; ".join(f"{s['id']} {s['state']}" + (
            f" (marks {', '.join(s['marked'])})" if s["marked"] else "") for s in doc["contracts"]))
    return 0


def after_run(argv: list, root: Path = ROOT) -> int:
    """The last step of `holon run` (K5), with the run's own --milestone and --out."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--milestone", default="M0")
    ap.add_argument("--out")
    a, _ = ap.parse_known_args(argv[1:])
    try:
        return apply(a.milestone, root, Path(a.out) if a.out else None)
    except Refused as e:
        print(f"holon run's last step (intent contracts) refused: {e}", file=sys.stderr)
        return 2


# ---------------------------------------------------------------------------------------------------- K6
def g10(milestone: str, root: Path = ROOT) -> tuple:
    """K6: (passed, detail); (None, reason) on M0 and M1, where G10 is not applicable. It fails, naming each contract,
    file, registry entry or law, on: a REGISTRY.json that is not a registry, or an entry that is not {milestone, kind,
    sha256} of strings; a contract file or entry that belongs to no milestone G10 applies to; a contract of the
    milestone not registered with its current sha256, milestone and kind; an entry for the milestone without its
    contract file; an intended contract not proved or a volatile view not valid; a record that is not a JSON object;
    and a record whose mark is not the one the proved contracts license. Since I65 (O7) the records are those of both
    record directories (results/<M> and results/<M>/extracted_m1), a scope law with a record in both fails it, and a
    record is licensed only over its contract's facts as they are now."""
    root = Path(root)
    if milestone in NOT_APPLICABLE:
        return None, NOT_APPLICABLE_WHY.format(m=milestone)
    reasons = []
    try:
        reg = registry(root)
    except Refused as e:
        reasons.append(str(e))
        reg = {}
    docs = _contracts(root)
    for p, c in docs:   # a file G10 cannot attribute to a milestone it applies to fails it everywhere it applies
        if milestone_of(c) is None:
            reasons.append(f"{p.name}: belongs to no milestone G10 applies to ({'; '.join(problems(c, root, p.stem))})")
    for cid, r in sorted(reg.items()):   # so does a registry entry that is not one, or names no such milestone
        if not isinstance(r, dict) or set(r) != {"milestone", "kind", "sha256"} \
                or not all(isinstance(r[k], str) for k in ("milestone", "kind", "sha256")):
            reasons.append(f"REGISTRY.json: the entry {cid} is not {{milestone, kind, sha256}}")
        elif milestone_of(r) is None:
            reasons.append(f"REGISTRY.json: the entry {cid} is for {r['milestone']}, a milestone G10 never runs on")
    mine = {c["id"]: c for _, c in docs if milestone_of(c) == milestone and isinstance(c.get("id"), str)}
    for cid, c in sorted(mine.items()):
        r = reg.get(cid)
        if not isinstance(r, dict) or r.get("sha256") != content_sha256(c) or r.get("milestone") != c.get("milestone") \
                or r.get("kind") != c.get("kind"):
            reasons.append(f"{cid}: not in the registry, or changed since it was registered")
    for cid, r in sorted(reg.items()):
        if isinstance(r, dict) and r.get("milestone") == milestone and cid not in mine:
            reasons.append(f"{cid}: registered for {milestone}, but laws/CONTRACTS/{cid}.json is not one of its "
                           "contracts")
    rows = states(milestone, root)
    for s in rows:
        if s["state"] not in ("proved", "valid"):
            reasons.append(f"{s['id']}: {s['state']}")
    rdir = root / "results" / milestone
    dirs = record_dirs(rdir) if rdir.is_dir() else []
    for lid in ambiguous(rows, dirs):
        reasons.append(f"{lid}: a scope law with a record in more than one of results/{milestone} and "
                       f"results/{milestone}/{VIEW}")
    want = {k: {"filter_bin": MARK, **v} for k, v in expected_marks(rows, dirs, _facts_now(root, rows)).items()}
    have = {}
    from .ir import record_files
    for key, d in dirs:
        for p in record_files(d):
            name = _rel(key, p.stem)
            try:
                r = _load(p)
            except ValueError:
                r = None
            if not isinstance(r, dict):
                reasons.append(f"{name}: the record is not a JSON object")
                continue
            if r.get("filter_bin") == MARK or "intended" in r:
                i = r.get("intended") if isinstance(r.get("intended"), dict) else {}
                have[name] = {"filter_bin": r.get("filter_bin"), "contract": i.get("contract"),
                              "l_weak": i.get("l_weak")}
    for name in sorted(set(have) | set(want)):
        if have.get(name) != want.get(name):
            reasons.append(f"{name}: the record's mark {have.get(name)} is not the contracts' {want.get(name)}")
    if reasons:
        return False, "; ".join(reasons)
    if not rows:
        return True, f"no intent contract on {milestone} (laws/CONTRACTS/ holds none for it)"
    parts = []
    for s in rows:
        licensed = sorted(r.rpartition("/")[2] for r, v in want.items() if v["contract"] == s["id"])   # law ids
        parts.append(f"{s['id']} {s['state']}" + (f", marks {', '.join(licensed)}" if licensed else ""))
    return True, "; ".join(parts)


# ---------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon contracts", description="intent contracts (K3, K5)")
    ap.add_argument("what", choices=["derive", "apply"])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 when the committed files differ")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        if a.what == "derive":
            return derive(a.milestone, root, a.check)
        return apply(a.milestone, root, check=a.check)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"refused: {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
