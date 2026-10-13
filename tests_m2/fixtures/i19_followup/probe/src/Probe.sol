// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture of the I19 follow-up (tests_m2/test_i19_followup.py): walker constructs outside the ledger's reach
// (short-circuit writes, loop fixpoints, Yul assignments in loops, loops under a branch, signed arithmetic, try, new,
// Yul switch and functions, a revert-style principal, constant reasons, enum conversion, pop, assert, ABI checks).

interface IE {
    function f(uint256 a) external returns (uint256);
}

contract Child {
    uint256 public made;
}

abstract contract Auth {
    address internal _admin;

    error NotAdmin(address who);

    modifier onlyAdmin() {
        _checkAdmin();
        _;
    }

    function _checkAdmin() internal view {
        if (_admin != msg.sender) {
            revert NotAdmin(msg.sender);
        }
    }
}

contract Probe is Auth {
    enum Mode {
        Off,
        On
    }

    struct S {
        uint64 lo;
        address who;
    }

    string internal constant TOO_BIG = "too big";

    uint256 public x;
    uint256 public z;
    address public ext;
    uint256[] internal stack;

    function setz() internal returns (bool) {
        z = 3;
        return true;
    }

    function orw(bool c) external {
        if (c || setz()) {
            x = 1;
        }
    }

    function dry(uint256 n) external pure returns (uint256 y) {
        for (uint256 i = 0; i < n; i++) {
            if (i == 3) {
                y = 7;
            }
        }
    }

    function drys(uint256 n) external {
        for (uint256 i = 0; i < n; i++) {
            if (i == 3) {
                x = 7;
            }
        }
        require(x != 5, "x5");
    }

    function pre(uint256 n) external pure returns (uint256 w) {
        uint256 v = 100;
        for (uint256 i = 0; i < n; i++) {
            v += 1;
        }
        require(v > 50, "v");
        w = v;
    }

    function brk(uint256 n, uint256 k) external pure returns (uint256 y) {
        for (uint256 i = 0; i < n; i++) {
            if (k == i) {
                y = 9;
                break;
            }
        }
    }

    function yiv(uint256 n) external pure returns (uint256 s) {
        for (uint256 i = 0; i < n; i++) {
            assembly {
                i := add(i, 1)
            }
            s += 1;
        }
    }

    function ybound(uint256 n) external pure returns (uint256 s) {
        for (uint256 i = 0; i < n; i++) {
            assembly {
                n := sub(n, 1)
            }
            s += 1;
        }
    }

    function lc(uint256 n, bool go) external pure returns (uint256 s) {
        if (go) {
            for (uint256 i = 0; i < n; i++) {
                s += 1;
            }
        }
    }

    function sg(int256 a, int256 b) external pure returns (bool, int256) {
        return (a < b, a / b);
    }

    function tr(uint256 a) external returns (uint256) {
        try IE(ext).f(a) returns (uint256 r) {
            x = r;
            return r;
        } catch {
            x = 0;
            return 0;
        }
    }

    function mk() external returns (address) {
        Child c = new Child();
        return address(c);
    }

    function ysw(uint256 a) external pure returns (uint256 r) {
        assembly {
            function dbl(q) -> w {
                if gt(q, 100) {
                    w := q
                    leave
                }
                w := mul(q, 2)
            }
            switch a
            case 0 {
                r := 1
            }
            default {
                r := dbl(a)
            }
        }
    }

    function admin(uint256 a) external onlyAdmin {
        require(a < 10, TOO_BIG);
        x = a;
    }

    function mode(uint256 a) external pure returns (uint8) {
        return uint8(Mode(a));
    }

    function popit() external {
        stack.pop();
    }

    function chk(uint256 a) external pure {
        assert(a != 3);
    }

    function mem(S memory s) public pure returns (uint64) {
        return s.lo;
    }

    function cd(S calldata s) external pure returns (uint64) {
        return s.lo;
    }

    function ret(uint256 n) external pure returns (uint256) {
        for (uint256 i = 0; i < n; i++) {
            if (i == 2) {
                return 42;
            }
        }
        return 1;
    }

    function nest(uint256 n, uint256 m) external pure returns (uint256 s) {
        for (uint256 i = 0; i < n; i++) {
            for (uint256 j = 0; j < m; j++) {
                s += 1;
            }
        }
    }

    function unk(uint256 x) external pure returns (uint256 r) {
        while (x != 0) {
            x = x / 2;
            r += 1;
        }
    }
}
