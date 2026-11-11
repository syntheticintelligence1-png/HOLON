// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

/// I50b's generality fixture (tests_m4/test_i50b_rerun.py): a contract written for the rules, not taken from any
/// target. It copies a storage struct into memory, writes members of the copy and stores it back (the frontend's
/// `update` term), and calls internal functions with literal boolean arguments, one only with a constant (a branch the
/// walk folds away at every reach) and one with both constants (both branches live).
contract Tally {
    struct Totals {
        uint64 count;
        uint64 sum;
        uint8 mode;
        uint120 spare;
    }

    Totals public totals;
    uint256 public last;
    mapping(uint256 => uint256) public marks;

    function record(uint64 x) external {
        Totals memory t = totals;
        t.count = t.count + 1;
        t.sum = t.sum + x;
        totals = t;
        _settle(x, false);
        _note(x, false);
    }

    function settle(uint256 x) external {
        _settle(x, true);
    }

    function unused(uint256 x) external pure returns (uint256) {
        uint256 y = x + 1;
        return x;
    }

    function _settle(uint256 x, bool fast) internal {
        if (fast) {
            last = x;
        } else {
            marks[x] = 1;
        }
    }

    function _note(uint256 x, bool loud) internal {
        if (loud) {
            last = x + 1;
        }
    }
}
