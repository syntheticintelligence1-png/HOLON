// SPDX-License-Identifier: MIT
// I123 planted fixture for solc 0.6.12 (a release below 0.8.0: no checked arithmetic; a shift amount may be signed, and a
// negative amount reverts). Written from the language specification alone.
pragma solidity 0.6.12;

// In class: constant shift amounts only (R1 refuses a non-constant one in a release below 0.8.0)
contract Pre06 {
    uint256 public r;
    int256 public s;

    function shlC(uint256 x) public { r = x << 200; }
    function shrC(uint256 x) public { r = x >> 3; }
    function sarC(int256 x) public { s = x >> 3; }
    function shl8C(uint8 x) public { r = uint256(x << 3); }
    function sarYC(uint256 x) public { uint256 v; assembly { v := sar(260, x) } r = v; }
}

// R1: a shift by a non-constant amount, whose type the term does not record, stays refused
contract PreVar06 {
    uint256 public r;
    function f(uint256 x, uint256 n) public { r = x << n; }
}
