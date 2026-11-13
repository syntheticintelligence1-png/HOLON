// SPDX-License-Identifier: MIT
// I123 planted fixture (tests_m6/test_i123_typed_sort_operations.py), written from the Solidity and EVM semantics
// alone. Every result is stored, so the model's storage writes and the compiled code's are compared case by case.
// Slots: 0 r (a word), 1 s (a signed word), 2 last (a Time register: block.timestamp flows into it).
pragma solidity 0.8.24;

// In class (W1, S1-S3): every function's model is stated exactly under the opt-in sort_ops "word".
contract SortOps {
    uint256 public r;
    int256 public s;
    uint256 public last;

    function setLast() external { last = block.timestamp; }

    // S1, S2: Solidity << and >> on uint256 (the EVM's shl and shr: an amount of 256 or more gives 0)
    function shlV(uint256 x, uint256 n) external { r = x << n; }
    function shrV(uint256 x, uint256 n) external { r = x >> n; }
    function shlC(uint256 x) external { r = x << 255; }
    function shrC(uint256 x) external { r = x >> 255; }
    // S3: >> on int256 rounds towards negative infinity (sar)
    function sarV(int256 x, uint256 n) external { s = x >> n; }
    function sarC(int256 x) external { s = x >> 7; }
    // the EVM forms in Yul: the amount is the first operand
    function shlY(uint256 x, uint256 n) external { uint256 v; assembly { v := shl(n, x) } r = v; }
    function shrY(uint256 x, uint256 n) external { uint256 v; assembly { v := shr(n, x) } r = v; }
    function sarY(uint256 x, uint256 n) external { uint256 v; assembly { v := sar(n, x) } r = v; }
    function sarYC(uint256 x) external { uint256 v; assembly { v := sar(300, x) } r = v; }
    // narrow types: the result has the left operand's type, truncated to it; never overflow-checked
    function shl8(uint8 x, uint256 n) external { r = uint256(x << n); }
    function shr8(uint8 x, uint256 n) external { r = uint256(x >> n); }
    function sar8(int8 x, uint256 n) external { s = int256(x >> n); }
    function shlS8(int8 x, uint256 n) external { s = int256(x << n); }

    // W1: a typed value (Time) read as the word it occupies
    function packT(uint64 lo) external { r = (block.timestamp << 64) | lo; }
    function maskT() external { r = last & 0xffffffff; }
    function xorT(uint256 k) external { r = last ^ k; }
    function notT() external { r = ~last; }
    function orT(uint256 k) external { r = last | k; }
    function shrT(uint256 n) external { r = last >> n; }
    // W1 with C1: raw arithmetic on typed words outside checked code wraps
    function uncheckedT() external { unchecked { r = last + block.timestamp; } }
    function uncheckedSubT() external { unchecked { r = last - block.timestamp - block.timestamp; } }
}

// Just outside each class: each stays refused (its document falls back, its laws UNKNOWN).
contract RSdiv {
    int256 public s;
    function f(int256 a, int256 b) external { s = a / b; }
}

contract RSmod {
    int256 public s;
    function f(int256 a, int256 b) external { s = a % b; }
}

contract RAddmod {
    uint256 public r;
    function f(uint256 a, uint256 b, uint256 n) external { r = addmod(a, b, n); }
}

contract RMulmod {
    uint256 public r;
    function f(uint256 a, uint256 b, uint256 n) external { r = mulmod(a, b, n); }
}

contract RSignext {
    uint256 public r;
    function f(uint256 b, uint256 x) external { uint256 v; assembly { v := signextend(b, x) } r = v; }
}

// C1: the same Time + Time as uncheckedT, in checked code: the typed discipline holds and it stays refused
contract RCheckedT {
    uint256 public r;
    uint256 public last;
    function setLast() external { last = block.timestamp; }
    function f() external { r = last + block.timestamp; }
}
