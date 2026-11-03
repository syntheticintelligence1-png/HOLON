"""The sort grammar of whitepaper §7.1 as text, the §7.2 affine table, and writer labels (BUILD_PLAN I13).

Sort strings (canonical forms; `render(parse(s)) == s` for each):

  Time | Dur | SDur                      time points, durations, signed durations (Dur^±)
  Idx[k] | SIdx[k] | Cnt[k] | SCnt[k]     indices and counts of the index family k, and their signed forms
  Idx[k]_<label> | Cnt[k]_<label>         a writer-provenance refinement (§7.3); label: [a-z][a-z0-9]*
  Prin[role] | Amt[asset] | Dig[kind]     principals, amounts, digests
  Ver | Bool | Mach(w)                    versions, booleans, machine words of w bits
  <Record>                                a record type name (a product sort ⟨fields⟩), e.g. a facts type
  s1 + s2 (+ ...)                         an untagged union (§7.4); members rendered in lexicographic order
  Nat (unrefined)                         nothing refines the variable: nothing is guessed

Families. The solver (holon.sorts.solve) unifies BASE sorts, never labels (rule R2 of the contract in
tests_m2/test_sorts_morph.py). `family(s)` drops what flow does not unify: writer labels, the sign (a signed
value flows on unsigned, R1), and the kind of a digest or the role of a principal, which accumulate into
unions instead of clashing (R5). Families: Time, Dur, Idx[k], Cnt[k], Amt[a], Mach(w), Dig, Prin, Ver, Bool,
and Rec:<T> for a record.

Affine table (§7.2). Time is a torsor over the group Dur, and Idx[k] over the group Cnt[k]:

  P + G = P,  G + P = P,  G + G = G,  P + P ill-sorted        (P, G) = (Time, Dur) or (Idx[k], Cnt[k])
  P - P = G^±,  G - G = G^±,  G - P ill-sorted
  Idx[k] - Cnt[k] = SIdx[k]   (the §7.2 row Idx[κ] − Cnt[κ] = Idx[κ]^±)
  Time - Dur = Time           (no §7.2 row; the grammar has no signed Time, so the torsor action is used and
                               no sign is recorded: a question for the human, see docs/iterations/I13.md)
  Amt[a] ± Amt[a] = Amt[a],  Mach(w) ± Mach(w) = Mach(w)     (closed sorts; overflow is §7.6, not I13)
  anything else is ill-sorted: mixing index families, mixing a family with another, digests, principals,
  versions, booleans, records, unions, signed operands (a signed value is realized before it flows, R1).

Writer labels (§7.3, rule R4). The label of a writer set W is computed from the frozen sidecar
spec/M2/lib/sort_seeds.json, the only target vocabulary: the first rule of its writer_labels.rules whose
prefix starts every name in W gives the label; otherwise the documented fallback, "w" followed by the first 8
hex digits of sha256 of the sorted writer names joined by ",". An empty writer set has no label.

Assignment keys for holon-facts/0.1 documents (the contract leaves them to the implementer): one key
"<Record>.<field>" per field of every record type, whose sort is Mach(8 * width) from the declared byte
width (a "type" constraint). 0.1 documents carry no state machine, so they have no flow, affine, compare or
seed constraints, and their fields carry no doc for the lexical rules to match.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

UNREFINED_TEXT = "Nat (unrefined)"
SIMPLE = ("Time", "Dur", "SDur", "Ver", "Bool")
INDEXED = ("Idx", "SIdx", "Cnt", "SCnt", "Prin", "Amt", "Dig")
LABELLED = ("Idx", "Cnt")
SIGNED = {"SDur": "Dur", "SIdx": "Idx", "SCnt": "Cnt"}
UNION_FAMILIES = ("Dig", "Prin")  # members accumulate into unions instead of clashing (R5)

_ARG = r"[A-Za-z][A-Za-z0-9_]*"
_LABEL = r"[a-z][a-z0-9]*"
_RE_INDEXED = re.compile(rf"^(Idx|SIdx|Cnt|SCnt|Prin|Amt|Dig)\[({_ARG})\](?:_({_LABEL}))?$")
_RE_MACH = re.compile(r"^Mach\(([1-9][0-9]*)\)$")
_RE_RECORD = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
LABEL_RE = re.compile(rf"^{_LABEL}$")


class SortError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class Sort:
    """One sort. head: Time, Dur, SDur, Ver, Bool, Idx, SIdx, Cnt, SCnt, Prin, Amt, Dig, Mach, Rec, Union or
    Unrefined; arg: the family, role, asset, kind, width or record name; label: a writer label (Idx, Cnt);
    members: the members of a union (non-union sorts, at least two, sorted by their text)."""
    head: str
    arg: str | None = None
    label: str | None = None
    members: tuple = ()


UNREFINED = Sort("Unrefined")


def parse(text: str) -> Sort:
    if not isinstance(text, str):
        raise SortError(f"a sort is text, not {text!r}")
    if text == UNREFINED_TEXT:
        return UNREFINED
    if " + " in text:
        parts = [parse(p) for p in text.split(" + ")]
        return union(parts)
    if text in SIMPLE:
        return Sort(text)
    m = _RE_INDEXED.match(text)
    if m:
        head, arg, label = m.group(1), m.group(2), m.group(3)
        if label is not None and head not in LABELLED:
            raise SortError(f"{text}: only Idx[k] and Cnt[k] carry a writer label")
        return Sort(head, arg, label)
    m = _RE_MACH.match(text)
    if m:
        return Sort("Mach", m.group(1))
    if _RE_RECORD.match(text) and text not in ("Nat", "Mach", "Union", "Unrefined") + INDEXED:
        return Sort("Rec", text)
    raise SortError(f"{text!r} is not a sort of the §7.1 grammar")


def union(parts) -> Sort:
    """The union of sorts (flattening nested unions). One distinct member is that member itself."""
    flat = []
    for p in parts:
        if p.head == "Union":
            flat.extend(p.members)
        elif p.head == "Unrefined":
            raise SortError("Nat (unrefined) is not a union member")
        else:
            flat.append(p)
    uniq = sorted(set(flat), key=render)
    if not uniq:
        raise SortError("an empty union")
    if len(uniq) == 1:
        return uniq[0]
    return Sort("Union", members=tuple(uniq))


def render(s: Sort) -> str:
    h = s.head
    if h == "Unrefined":
        return UNREFINED_TEXT
    if h in SIMPLE:
        return h
    if h in INDEXED:
        return f"{h}[{s.arg}]" + (f"_{s.label}" if s.label else "")
    if h == "Mach":
        return f"Mach({s.arg})"
    if h == "Rec":
        return s.arg
    if h == "Union":
        return " + ".join(sorted(render(m) for m in s.members))
    raise SortError(f"unknown sort head {h!r}")


def canonical(text: str) -> str:
    return render(parse(text))


# ------------------------------------------------------------------ families (what flow unifies, R2)
def family(s: Sort) -> str | None:
    """The base family of a non-union sort; None for Nat (unrefined)."""
    h = h0 = s.head
    if h == "Unrefined":
        return None
    if h == "Union":
        raise SortError("a union has one family per member: use families()")
    h = SIGNED.get(h, h)
    if h in ("Time", "Dur", "Ver", "Bool"):
        return h
    if h in ("Idx", "Cnt", "Amt"):
        return f"{h}[{s.arg}]"
    if h in UNION_FAMILIES:
        return h
    if h == "Mach":
        return f"Mach({s.arg})"
    if h == "Rec":
        return f"Rec:{s.arg}"
    raise SortError(f"no family for {h0}")


def families(s: Sort) -> set[str]:
    if s.head == "Union":
        return {family(m) for m in s.members}
    f = family(s)
    return set() if f is None else {f}


def base(s: Sort) -> Sort:
    """The sort without its writer label."""
    return Sort(s.head, s.arg) if s.label else s


def unsigned(s: Sort) -> Sort:
    """R1: the sort a realized value flows on with (SDur -> Dur, SCnt[k] -> Cnt[k], SIdx[k] -> Idx[k])."""
    return Sort(SIGNED[s.head], s.arg) if s.head in SIGNED else s


def is_signed(s: Sort) -> bool:
    return s.head in SIGNED


# ------------------------------------------------------------------ torsor pairs (solve.py reads these)
def pair_role(fam: str) -> tuple[str, str] | None:
    """(pair id, role) of an arithmetic family: role P (point), G (group) or S (a closed sort); None when the
    family takes no part in affine arithmetic."""
    if fam == "Time":
        return ("T", "P")
    if fam == "Dur":
        return ("T", "G")
    m = re.fullmatch(r"(Idx|Cnt)\[(.+)\]", fam)
    if m:
        return (f"I:{m.group(2)}", "P" if m.group(1) == "Idx" else "G")
    if fam.startswith("Amt[") or fam.startswith("Mach("):
        return (f"S:{fam}", "S")
    return None


def family_of(pair: str, role: str) -> str:
    """Inverse of pair_role."""
    if pair == "T":
        return "Time" if role == "P" else "Dur"
    if pair.startswith("I:"):
        k = pair[2:]
        return f"Idx[{k}]" if role == "P" else f"Cnt[{k}]"
    if pair.startswith("S:"):
        return pair[2:]
    raise SortError(f"unknown pair {pair}")


# the affine relation on roles (result realized unsigned, R1)
ROLE_TABLE = {
    "+": {("P", "G"): "P", ("G", "P"): "P", ("G", "G"): "G", ("S", "S"): "S"},
    "-": {("P", "P"): "G", ("P", "G"): "P", ("G", "G"): "G", ("S", "S"): "S"},
}


def difference_sort(pair: str, ra: str, rb: str) -> Sort | None:
    """The §7.2 sort of a - b (signed where the table says so) for operand roles ra, rb in one pair."""
    out = ROLE_TABLE["-"].get((ra, rb))
    if out is None:
        return None
    fam = family_of(pair, out)
    if ra == "S":
        return parse(fam)
    if pair == "T":
        return Sort("SDur") if out == "G" else Sort("Time")
    k = pair[2:]
    if out == "G":
        return Sort("SCnt", k)
    return Sort("SIdx", k)


def affine(op: str, a: str, b: str) -> str | None:
    """The §7.2 table: the sort of `a op b`, or None when the combination is ill-sorted. Labels are dropped
    (writer labels are refinements of the base sort: arithmetic reads the base)."""
    if op not in ("+", "-"):
        raise SortError(f"affine operator {op!r} is not + or -")
    try:
        sa, sb = parse(a), parse(b)
    except SortError:
        return None
    if sa.head in ("Union", "Unrefined") or sb.head in ("Union", "Unrefined") or is_signed(sa) or is_signed(sb):
        return None
    pa, pb = pair_role(family(sa)), pair_role(family(sb))
    if pa is None or pb is None or pa[0] != pb[0]:
        return None
    pair, ra, rb = pa[0], pa[1], pb[1]
    if op == "+":
        out = ROLE_TABLE["+"].get((ra, rb))
        return None if out is None else render(parse(family_of(pair, out)))
    d = difference_sort(pair, ra, rb)
    return None if d is None else render(d)


# ------------------------------------------------------------------ writer labels (§7.3, R4)
def writer_label(writers, writer_labels: dict) -> str | None:
    """The label of a writer set under the sidecar's writer_labels (rules, then the documented fallback)."""
    ws = sorted(set(writers))
    if not ws:
        return None
    for rule in writer_labels.get("rules", []):
        if all(w.startswith(rule["prefix"]) for w in ws):
            label = rule["label"]
            if not LABEL_RE.match(label):
                raise SortError(f"writer label {label!r} (rule {rule.get('id')}) is not [a-z][a-z0-9]*")
            return label
    return "w" + hashlib.sha256(",".join(ws).encode("utf-8")).hexdigest()[:8]


def labelled(s: Sort, label: str | None) -> Sort:
    if label is None or s.head not in LABELLED:
        return s
    return Sort(s.head, s.arg, label)
