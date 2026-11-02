"""The historical replay's target library: spec/<M>/lib/historical_target.json (what the generic code must not name).

    contract          the key of the replayed contract in the frozen instrument's `contracts`
    abi               interface / interface_contract / implementation: source paths in the pinned checkout
    commit_functions  the functions whose transactions are commits
    parent_header     the calldata field (of the first parameter) that carries the parent header
    events            commit / revert / upgrade: event signatures, keys of the instrument's `events`
    rebuild.fields    how the encoder's Header is rebuilt from a commit's inputs, field by field:
                        ["calldata", name]                      the decoded calldata value
                        ["parent_plus", field, k]               the parent header's field (dec_go) + k
                        ["parent_plus_calldata", field, name]   the parent header's field + a calldata value
                        ["parent_keccak"]                       keccak256 of the parent header
                        ["zero"]                                zero bytes
                        ["header"]                              copied from the header being rebuilt (not evidence)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TargetError(ValueError):
    pass


def load(milestone: str = "M2", root: Path = ROOT) -> dict:
    p = Path(root) / "spec" / milestone / "lib" / "historical_target.json"
    try:
        t = json.loads(p.read_text())
    except (OSError, ValueError) as e:
        raise TargetError(f"{p}: {e}") from None
    for k in ("contract", "abi", "commit_functions", "parent_header", "events", "rebuild"):
        if k not in t:
            raise TargetError(f"{p}: no {k!r}")
    return t


def contract(side: dict, t: dict) -> dict:
    c = side["contracts"].get(t["contract"])
    if not isinstance(c, dict) or "address" not in c:
        raise TargetError(f"the instrument has no contract {t['contract']!r} with an address")
    return c


def topic(side: dict, t: dict, which: str) -> str:
    sig = t["events"][which]
    if sig not in side["events"]:
        raise TargetError(f"the instrument has no event {sig!r}")
    return side["events"][sig].lower()


def rebuild_inputs(t: dict) -> list[str]:
    """The calldata fields a rebuild reads."""
    out = []
    for op in t["rebuild"]["fields"].values():
        if op[0] == "calldata":
            out.append(op[1])
        elif op[0] == "parent_plus_calldata":
            out.append(op[2])
    return sorted(set(out))
