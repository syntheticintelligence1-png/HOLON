"""Atom map for the S6 historical replay.

The model speaks in Nat atoms for every hash/address identity (M1 abstraction:
0 = zero value, 1 = Z = ZERO_VERSIONED_HASH; aggregate blob hashes are computed
inside the model by d_blob_hash from the blob-hash atoms). This map assigns
each distinct concrete value one atom, deterministically (first-seen order,
per sorted commit iteration), starting at FIRST_FRESH. It is the ONLY place
concrete -> atom translation happens, so every atom-level comparison in the
report is auditable via `table`.
"""
from __future__ import annotations

ZERO32 = "0x" + "00" * 32
ZERO_VH = "0x01" + "00" * 31
FIRST_FRESH = 10_000


def canon(v: str) -> str:
    """Canonical form for bytes32/address/uint concrete values: 0x-lower-hex."""
    v = v.lower()
    if not v.startswith("0x"):
        v = "0x" + v
    return v


def canon_addr(a: str) -> str:
    a = canon(a)
    return "0x" + a[2:].rjust(40, "0")


def canon_b32(h: str) -> str:
    h = canon(h)
    return "0x" + h[2:].rjust(64, "0")


class AtomMap:
    """Bidirectional concrete-value <-> Nat-atom map (deterministic)."""

    def __init__(self) -> None:
        self.f2a: dict[str, int] = {ZERO32: 0, ZERO_VH: 1}
        self.a2f: dict[int, str] = {0: ZERO32, 1: ZERO_VH}
        self._next = FIRST_FRESH

    def atom(self, concrete) -> int:
        """Atom for a bytes32/address/int-as-hex value; small ints pass through."""
        if isinstance(concrete, int):
            return concrete
        c = canon(concrete)
        if c in self.f2a:
            return self.f2a[c]
        a = self._next
        self._next += 1
        self.f2a[c] = a
        self.a2f[a] = c
        return a

    def concrete(self, atom: int):
        return self.a2f.get(atom)

    def blob_atoms(self, versioned_hashes: list[str]) -> list[int]:
        return [self.atom(canon_b32(h)) for h in versioned_hashes]

    def table(self) -> dict:
        """Atom -> concrete, sorted by atom; for report auditability."""
        return {str(a): self.a2f[a] for a in sorted(self.a2f)}
