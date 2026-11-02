"""I34 instrument (rule SYM on M3), fixed at the I34 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_sym.py, rules J1-J12. This module writes J1's families and roles, J3's law
ids, J5's eligible pairs and J7's sentinel sites out a second time, independently of holon/: it reads the typed
Rollup's facts (spec/M2/facts/morph_rollup.extracted.json) and, for the Time words, the committed structural typed model
(gen/M3/sorts/models/morph_rollup_extracted.bend, I68's store: a Time-typed read is T_Time{sload(.., SK{W{b, ..}, ..})}),
as JSON and text. Nothing here imports holon/.

  CONTRACT                          the facts' contract name ("Rollup")
  time_words(root)                  J1: the Time words, sorted ("storage:<family>.<member>", "env:block.timestamp",
                                    "call:<interface>.<function>")
  roles(facts)                      J1: the roles, sorted (a storage-reading principal predicate's modifier without its
                                    "only", lower-cased first letter; an address register written with the caller)
  eligible_pairs(facts)             J5: the static ω candidates, sorted (a, b) with a < b
  sentinel_sites(facts)             J7: [[register, write action, write src]] for each non-literal write of a sentinel
                                    register
  time_constant_compares(facts)     J6/P5: the comparisons of a Time word against a constant in a guard or a view return,
                                    as "<action>:<src or 'returns'>"
  expected_law_ids(root)            J3: the law ids holon derive must write for SYM, sorted
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = "spec/M2/facts/morph_rollup.extracted.json"
MODEL = "gen/M3/sorts/models/morph_rollup_extracted.bend"
CONTRACT = "Rollup"
CMP = ("==", "!=", "<", "<=", ">", ">=")
STATE_CHANGING = lambda a: a.get("mutability") not in ("view", "pure")   # noqa: E731


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def facts(root: Path = ROOT) -> dict:
    return load(Path(root) / FACTS)


def _storage(f: dict) -> dict:
    return {s["name"]: s for s in f["storage"]}


def _walk(e):
    yield e
    if isinstance(e, list):
        for x in e:
            yield from _walk(x)
    elif isinstance(e, dict):
        for x in e.values():
            yield from _walk(x)


def _families_in(e) -> set:
    """Storage families an expression reads: ["storage", F] anywhere in it."""
    return {x[1] for x in _walk(e) if isinstance(x, list) and len(x) == 2 and x[0] == "storage" and isinstance(x[1], str)}


def _reads(a: dict) -> set:
    out = set()
    for k in ("guards", "writes", "returns", "checks", "loops", "calls", "post"):
        out |= _families_in(a.get(k))
    return out


def _writes(a: dict) -> set:
    return {w.get("family") for w in a.get("writes") or [] if isinstance(w, dict)}


def _class(a: dict):
    p = a.get("principal")
    return p.get("modifier") if isinstance(p, dict) else None


# ---------------------------------------------------------------------------------------------------- J1
def time_words(root: Path = ROOT) -> list:
    """The Time words of the typed model: each structural storage key read as T_Time (its family and member from the
    facts' layout), block.timestamp when read as T_Time, and each external call answer read as T_Time."""
    f = facts(root)
    text = (Path(root) / MODEL).read_text(encoding="utf-8")
    by_slot = {int(s["slot"]): s for s in f["storage"]}
    out = set()
    for m in re.finditer(r"T_Time\{sload\([a-z_0-9]+, SK\{W\{(\d+), 0, 0, 0, 0, 0, 0, 0\}, ", text):
        fam = by_slot.get(int(m.group(1)))
        if fam is None:
            continue
        rest = text[m.end(): m.end() + 2000]
        if fam.get("kind") == "mapping" and fam.get("fields"):
            mo = re.search(r"\[SP_m\{.*?, W\{(\d+), 0, 0, 0, 0, 0, 0, 0\}\}\]\}\)", rest)
            off = int(mo.group(1)) if mo else 0
            mem = next((x["name"] for x in fam["fields"] if int(x.get("slot", 0)) == off), None)
            out.add(f"storage:{fam['name']}.{mem}")
        else:
            out.add(f"storage:{fam['name']}")
    if "T_Time{ge_e_block_timestamp(" in text:
        out.add("env:block.timestamp")
    for a in f["actions"]:
        for c in a.get("calls") or []:
            name = c.get("fn") or c.get("name") if isinstance(c, dict) else None
            if name and re.search(r"T_Time\{b_word\(a_ret\(c_find\(", text) and name.endswith("EnqueueTime"):
                out.add(f"call:{name}")
    return sorted(out)


def roles(f: dict) -> list:
    """J1's roles, sorted [name, kind]: a principal predicate that reads storage names a role (onlyChallenger ->
    challenger, onlyOwner -> owner), of kind "set" when it looks the caller up in a mapping and "singleton" when it
    compares the caller with a scalar; an address-typed register that some action writes with the caller names a role
    by its own name, "set" for a member of a mapping family's struct (one value per key) and "singleton" for a scalar.
    A name both ways takes "set" if either is."""
    st = _storage(f)
    kinds: dict = {}

    def add(name, kind):
        kinds[name] = "set" if "set" in (kinds.get(name), kind) else kind
    for a in f["actions"]:
        p = a.get("principal")
        if isinstance(p, dict) and p.get("modifier") and _families_in(p.get("predicate")):
            m = p["modifier"]
            m = m[4:] if m.startswith("only") else m
            pred = p.get("predicate")
            add(m[:1].lower() + m[1:], "set" if isinstance(pred, list) and pred[:1] == ["map"] else "singleton")
        for w in a.get("writes") or []:
            v = w.get("value")
            fam = st.get(w.get("family")) or {}
            if isinstance(v, list) and v[:1] == ["struct"]:
                types = {x["name"]: x.get("type") for x in fam.get("fields") or []}
                for name, val in v[2]:
                    if val == ["caller"] and types.get(name) == "address":
                        add(name, "set" if fam.get("kind") == "mapping" else "singleton")
            elif v == ["caller"] and fam.get("value") == "address":
                add(w["family"], "singleton")
    return sorted([k, v] for k, v in kinds.items())


def set_roles(f: dict) -> list:
    """The roles a π generator can act on (two distinct members possible): the "set" roles."""
    return [r for r, k in roles(f) if k == "set"]


def _initializer(a: dict) -> bool:
    return any(m in ("initializer", "reinitializer") for m in a.get("modifiers") or [])


# ---------------------------------------------------------------------------------------------------- J5
def _sinks(f: dict) -> set:
    out = set()
    for a in f["actions"]:
        for g in a.get("guards") or []:
            out |= _families_in(g.get("expr"))
        if not STATE_CHANGING(a):
            out |= _families_in(a.get("returns"))
    return out


def eligible_pairs(f: dict) -> list:
    """J5's static ω candidates: two state-changing actions, neither an initializer (a one-shot step of a version has no
    reordering within a deployment), of different principal classes, and a sink family (one a guard or a view's return
    reads) that one writes and the other writes or reads."""
    acts = sorted((a for a in f["actions"] if STATE_CHANGING(a) and not _initializer(a)), key=lambda a: a["name"])
    sinks = _sinks(f)
    out = []
    for i, a in enumerate(acts):
        for b in acts[i + 1:]:
            if _class(a) == _class(b):
                continue
            wa, wb, ra, rb = _writes(a), _writes(b), _reads(a), _reads(b)
            if ((wa & (wb | rb)) | (wb & ra)) & sinks:
                out.append((a["name"], b["name"]))
    return out


# ---------------------------------------------------------------------------------------------------- J7
def _compares(f: dict):
    """(action, where, cmp, register path, constant) for each comparison of a storage read against an integer constant
    in a guard or a view's return; register path "family" or "family.member"."""
    for a in f["actions"]:
        places = [(g.get("src") or "guard", g.get("expr")) for g in a.get("guards") or []]
        if not STATE_CHANGING(a):
            places.append(("returns", a.get("returns")))
        for where, e in places:
            for x in _walk(e):
                if isinstance(x, list) and len(x) == 3 and x[0] in CMP:
                    for reg, c in ((x[1], x[2]), (x[2], x[1])):
                        if isinstance(c, int) and not isinstance(c, bool):
                            path = _register(reg)
                            if path:
                                yield a["name"], where, x[0], path, c


def _register(e):
    if isinstance(e, list) and len(e) == 2 and e[0] == "storage":
        return e[1]
    if isinstance(e, list) and len(e) == 3 and e[0] == "member" and isinstance(e[1], list) and e[1][:1] == ["map"] \
            and isinstance(e[1][1], list) and e[1][1][:1] == ["storage"]:
        return f"{e[1][1][1]}.{e[2]}"
    return None


def _write_values(f: dict, path: str):
    """(action, src, value) for each write of a register path ("family" or "family.member")."""
    fam, _, mem = path.partition(".")
    for a in f["actions"]:
        for w in a.get("writes") or []:
            if w.get("family") != fam:
                continue
            v = w.get("value")
            if mem:
                if isinstance(v, list) and v[:1] == ["struct"]:
                    for name, val in v[2]:
                        if name == mem:
                            yield a["name"], w.get("src"), val
            elif not (isinstance(v, list) and v[:1] == ["struct"]):
                yield a["name"], w.get("src"), v


def sentinel_registers(root: Path = ROOT) -> list:
    """J7: a register compared against a constant c in a guard or a view is a sentinel register when it is a Time word
    (whitepaper §5.4: constants compared against Time- or Idx-sorted registers; no M3 model has an Idx sort); sorted
    [path, c]."""
    f = facts(root)
    tw = set(time_words(root))
    return sorted([list(x) for x in {(path, c) for _, _, _, path, c in _compares(f) if f"storage:{path}" in tw}])


def sentinel_sites(f: dict, root: Path = ROOT) -> list:
    """J7's write sites: each write of a sentinel register whose value is not the literal sentinel, sorted
    [path, action, src]."""
    out = set()
    for path, c in sentinel_registers(root):
        for act, src, v in _write_values(f, path):
            if v != c:
                out.add((path, act, src))
    return sorted([list(x) for x in out])


def time_constant_compares(f: dict, root: Path = ROOT) -> list:
    tw = set(time_words(root))
    return sorted({f"{act}:{where}" for act, where, _, path, _ in _compares(f) if f"storage:{path}" in tw})


# ---------------------------------------------------------------------------------------------------- J3
def _touches_time(a: dict, tw: set) -> bool:
    fams = _reads(a) | _writes(a)
    s = json.dumps([a.get(k) for k in ("guards", "writes", "returns", "checks")])
    return ('["env", "block.timestamp"]' in s) or any(w.startswith("storage:") and w[8:].split(".")[0] in fams
                                                     for w in tw)


def _role_touched(f: dict, a: dict, role: str) -> bool:
    p = a.get("principal")
    if isinstance(p, dict) and p.get("modifier"):
        m = p["modifier"][4:] if p["modifier"].startswith("only") else p["modifier"]
        if (m[:1].lower() + m[1:]) == role and _families_in(p.get("predicate")):
            return True
    st = _storage(f)
    for w in a.get("writes") or []:
        fam = st.get(w.get("family")) or {}
        if w.get("family") == role or any(x.get("name") == role for x in fam.get("fields") or []):
            if isinstance(w.get("value"), list) and w["value"][:1] == ["struct"]:
                if any(name == role for name, _ in w["value"][2]):
                    return True
            elif w.get("family") == role:
                return True
    reads = json.dumps([a.get(k) for k in ("guards", "writes", "returns", "checks", "calls")])
    return f'"{role}"]' in reads


def expected_law_ids(root: Path = ROOT) -> list:
    f = facts(root)
    tw = set(time_words(root))
    out = []
    acts = [a for a in f["actions"]]
    for a in acts:
        if _touches_time(a, tw):
            out.append(f"L_sym_tau_{CONTRACT}_{a['name']}")
    for role in set_roles(f):
        for a in acts:
            if _role_touched(f, a, role):
                out.append(f"L_sym_pi_{CONTRACT}_{a['name']}_{role}")
    for x, y in eligible_pairs(f):
        out.append(f"L_sym_omega_{CONTRACT}_{x}_{y}")
    for path, act, src in sentinel_sites(f, root):
        line = re.search(r":(\d+)(?:-\d+)?$", src or "")
        out.append(f"L_sym_sentinel_{CONTRACT}_{path.replace('.', '_')}_{act}_{line.group(1) if line else 'x'}")
    return sorted(set(out))
