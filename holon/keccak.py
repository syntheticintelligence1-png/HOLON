"""Keccak-256 (Ethereum's padding, 0x01 ... 0x80), in pure Python.

Used by G6 to check that a logged header is the preimage of the committedBatches value the replay
read on chain, without running any tool. Written separately from the test suite's own copy
(tests_m2/_keccak.py), so the gate and the tests do not share an implementation.
"""
from __future__ import annotations

_M = 0xFFFFFFFFFFFFFFFF
_ROUND = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
    0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
    0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
    0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
# (destination lane, rotation) for each source lane x + 5y: rho and pi combined
_PI_RHO = {}
_x, _y = 1, 0
_PI_RHO[0] = (0, 0)
for _t in range(24):
    _r = ((_t + 1) * (_t + 2) // 2) % 64
    _PI_RHO[_x + 5 * _y] = (_y + 5 * ((2 * _x + 3 * _y) % 5), _r)
    _x, _y = _y, (2 * _x + 3 * _y) % 5


def _rotl(v: int, n: int) -> int:
    return ((v << n) | (v >> (64 - n))) & _M if n else v


def _permute(s: list[int]) -> None:
    for rc in _ROUND:
        c = [s[x] ^ s[x + 5] ^ s[x + 10] ^ s[x + 15] ^ s[x + 20] for x in range(5)]
        for x in range(5):
            d = c[(x + 4) % 5] ^ _rotl(c[(x + 1) % 5], 1)
            for y in range(0, 25, 5):
                s[x + y] ^= d
        b = [0] * 25
        for src, (dst, rot) in _PI_RHO.items():
            b[dst] = _rotl(s[src], rot)
        for y in range(0, 25, 5):
            row = b[y:y + 5]
            for x in range(5):
                s[x + y] = row[x] ^ ((row[(x + 1) % 5] ^ _M) & row[(x + 2) % 5])
        s[0] ^= rc


def keccak256(data: bytes) -> bytes:
    rate = 136
    pad = rate - len(data) % rate
    msg = bytes(data) + (b"\x81" if pad == 1 else b"\x01" + b"\x00" * (pad - 2) + b"\x80")
    s = [0] * 25
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            s[i] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        _permute(s)
    return b"".join(s[i].to_bytes(8, "little") for i in range(4))
