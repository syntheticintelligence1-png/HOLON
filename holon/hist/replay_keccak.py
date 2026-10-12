"""keccak-256, pure Python (no dependencies).

Used ONLY for oracle work in the historical replay: ABI 4-byte selectors for
eth_call getters. It is never part of the model: the model's codec/transition
logic lives in the compiled Bend artifacts, and every keccak comparison against
on-chain values is made in the JS driver (holon/hist/replay_driver.mjs), which
carries the same routine. Verified against the standard vectors in tests_m2/S6.
"""
from __future__ import annotations

_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_MASK = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _MASK if n else x


def _keccak_f(st: list[int]) -> None:
    for rnd in range(24):
        c = [st[x] ^ st[x + 5] ^ st[x + 10] ^ st[x + 15] ^ st[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                st[x + 5 * y] ^= d[x]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(st[x + 5 * y], _ROT[x][y])
        for x in range(5):
            for y in range(5):
                st[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y])
        st[0] ^= _RC[rnd]


def keccak256(data: bytes) -> bytes:
    """Ethereum keccak-256 (pad 0x01, rate 136) -- NOT FIPS sha3-256."""
    rate = 136
    st = [0] * 25
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != rate - 1:
        padded.append(0x00)
    padded.append(0x80)
    for off in range(0, len(padded), rate):
        blk = padded[off:off + rate]
        for i in range(rate // 8):
            st[i] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        _keccak_f(st)
    out = bytearray()
    for i in range(4):
        out += st[i].to_bytes(8, "little")
    return bytes(out[:32])


def selector(sig: str) -> bytes:
    """ABI 4-byte function selector."""
    return keccak256(sig.encode())[:4]
