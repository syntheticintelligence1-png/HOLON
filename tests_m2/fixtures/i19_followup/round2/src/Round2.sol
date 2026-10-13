// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture of the I19 follow-up, round 2 (tests_m2/test_i19_followup.py, V19-02..V19-05): an initializer-like
// modifier over packed bool storage, custom errors with arguments, string reasons, events with indexed reference-type
// arguments, memory allocation, the static head of the calldata, and the cleanup of bool values.

abstract contract Init {
    uint8 private _done;
    bool private _busy;

    error AlreadyDone(uint8 done, bool busy);

    modifier once() {
        bool top = !_busy;
        if (!(top && _done < 1)) {
            revert AlreadyDone(_done, _busy);
        }
        _done = 1;
        if (top) {
            _busy = true;
        }
        _;
        if (top) {
            _busy = false;
        }
    }

    modifier inside() {
        require(_busy, "not inside");
        _;
    }
}

contract Round2 is Init {
    struct P {
        uint256 a;
        uint256 b;
    }

    uint256 public x;
    bool public flag;
    bool public copy;

    error Bad(uint256 code, string why, address who);

    event Noted(string indexed label, bytes indexed blob, uint256[] indexed xs, uint256 plain);
    event Pair(P indexed p, bool indexed f, bool g);

    function setup(uint256 a) external once {
        _set(a);
    }

    function _set(uint256 a) internal inside {
        x = a;
    }

    function fail(uint256 c) external view {
        if (c > 3) {
            revert Bad({who: msg.sender, code: c, why: "too big"});
        }
    }

    function dyn(string calldata why) external pure {
        revert(why);
    }

    function note(string calldata label, bytes calldata blob, uint256[] calldata xs, uint256 plain) external {
        emit Noted(label, blob, xs, plain);
        emit Noted("fixed", hex"0102", xs, plain);
    }

    function pair(uint256 a) external {
        emit Pair(P(a, 2), flag, flag);
    }

    function alloc(uint256 n) external pure returns (uint256) {
        uint256[] memory m = new uint256[](n);
        bytes memory b = new bytes(n);
        return m.length + b.length;
    }

    function head(uint256 a, uint64 b, bytes calldata c, uint256[3] calldata d, P calldata p)
        external
        pure
        returns (uint256)
    {
        return a + b + c.length + d[0] + p.a;
    }

    function copyFlag() external {
        copy = flag;
    }

    function same() external view returns (bool) {
        return flag == copy;
    }

    function getFlag() external view returns (bool) {
        return flag;
    }

    function keep(bool f) external {
        bool r = f;
        if (f) {
            r = true;
        }
        copy = r;
    }
}
