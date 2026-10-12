"""Atom map for the S6 historical replay.

The model speaks in Nat atoms for every hash/address identity (M1 abstraction:
0 = zero value, 1 = Z = ZERO_VERSIONED_HASH; aggregate blob hashes are computed
inside the model by d_blob_hash from the blob-hash atoms). This map assigns
each distinct concrete value one atom, deterministically (first-seen order,
per sorted commit iteration), starting at FIRST_FRESH.

There are TWO documented concrete -> atom translations. `atom()` is the
global one: it is the only map used for values that are compared
cross-commit (state roots, stored batch hashes, addresses) or compared
concretely (legacy bvh atoms). `model_blob_atoms` (version == 2) is a
commit-local relabel used ONLY for v2 blob-hash atoms fed into
d_blob_hash: the v2 aggregate is symbolic and is only compared within the
same commit (entry.bvh, hb_eq_bvh, the edge-3 model_bvh_atom call), and
concrete correctness of the stored v2 hash is checked outside the model
by bvh_stored_vs_contract — so the local relabel cannot hide a real
defect. It exists because d_blob_hash nests a Cantor pairing whose value
grows ~a^(2^k) in k blobs and overflows Bend's 2^48 Nat immediate for
global atoms (>= 10000) with k >= 2; local atoms 2..k+1 keep the
intermediate within range for k <= 4. Every atom-level comparison in the
report is auditable via `table` plus the per-commit `blob_atom_map`
evidence.
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

    def model_blob_atoms(self, version: int,
                         versioned_hashes: list[str]) -> list[int]:
        """Blob-hash atoms as fed INTO the model's d_blob_hash.

        version == 2: a commit-local injective relabel — the second,
        documented concrete -> atom translation. Distinct canonical hashes
        get 2, 3, 4, ... in first-seen order within this commit (0 is the
        b_blob_count list terminator, 1 is Z), so equal hashes get equal
        atoms and k blobs need atoms 2..k+1. Sound because the v2
        aggregate is symbolic and only compared inside this commit
        (entry.bvh, hb_eq_bvh, edge-3 model_bvh_atom); the concrete stored
        bvh is checked by bvh_stored_vs_contract, not through the model.

        Any other version: `blob_atoms` unchanged — the model bvh IS the
        global concrete atom, compared by bvh_model_atom_vs_concrete, so
        it must stay global."""
        if version != 2:
            return self.blob_atoms(versioned_hashes)
        local: dict[str, int] = {}
        out = []
        for h in versioned_hashes:
            c = canon_b32(h)
            if c not in local:
                local[c] = len(local) + 2
            out.append(local[c])
        return out

    def table(self) -> dict:
        """Atom -> concrete, sorted by atom; for report auditability."""
        return {str(a): self.a2f[a] for a in sorted(self.a2f)}
