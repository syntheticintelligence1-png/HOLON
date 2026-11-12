// SPDX-License-Identifier: UNLICENSED
// I109 (e) planted fixture: a contract whose rendered terms exceed a small term budget and fit the default.
pragma solidity 0.8.24;

contract Wide {
    uint256 public a;
    uint256 public b;

    function set(uint256 x, uint256 y) external {
        if (x > y) {
            a = x + y + a;
        } else {
            b = x * y + b;
        }
    }
}
