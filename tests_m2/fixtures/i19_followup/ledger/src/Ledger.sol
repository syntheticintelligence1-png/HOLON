// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

// Planted fixture of the I19 follow-up (tests_m2/test_i19_followup.py): a contract written for the test, whose
// extraction is known by construction. Line numbers are cited by the test; edit with care.

interface IQ {
    function msgHash(uint256 index) external view returns (bytes32);
}

interface ICommit {
    function verify(uint256 index, bytes32 h) external view;
}

contract Owned {
    address internal _owner;
    bool internal _stopped;

    event OwnerSet(address indexed previous, address indexed next);

    modifier onlyOwner() {
        _check();
        _;
    }

    function _check() internal view {
        require(_owner == msg.sender, "not owner");
    }

    function owner() public view returns (address) {
        return _owner;
    }

    function transferOwnership(address next) external onlyOwner {
        require(next != address(0), "zero owner");
        emit OwnerSet(_owner, next);
        _owner = next;
    }
}

contract Ledger is Owned {
    struct Entry {
        uint64 idx;
        address who;
        uint256 amount;
        bool done;
    }

    mapping(uint256 => bytes32) public hashes;
    mapping(uint256 => Entry) public entries;
    uint256 public last;
    uint256 public total;
    address public q;
    address public verifier;

    event Committed(uint256 indexed index, bytes32 h);
    event Undone(uint256 indexed index);

    function _check2(bytes calldata b) internal pure {
        require(b.length > 0, "empty");
    }

    function pair(bytes calldata a, bytes calldata b) external pure {
        _check2(a);
        _check2(b);
    }

    function _big(uint256 b) internal pure returns (bool) {
        require(b > 1, "small");
        return true;
    }

    function sc(uint256 a, uint256 b) external {
        if (a > 0 && _big(b)) {
            total = 1;
        }
    }

    function commit(uint256 n, uint64 lbn) external onlyOwner {
        uint256 next = last + 1;
        uint256 ptr;
        uint256 p;
        assembly {
            ptr := mload(0x40)
            mstore(ptr, shl(192, lbn))
            p := add(ptr, 8)
        }
        uint256 t = total;
        for (uint256 i = 0; i < n; i++) {
            bytes32 m = IQ(q).msgHash(t + i);
            assembly {
                mstore(p, m)
                p := add(p, 0x20)
            }
        }
        bytes32 h;
        assembly {
            h := keccak256(ptr, sub(p, ptr))
            mstore(0x40, p)
        }
        hashes[next] = h;
        entries[next] = Entry(lbn, msg.sender, n, false);
        total = total + n;
        last = next;
        emit Committed(next, h);
    }

    function count() external view returns (uint256 c) {
        assembly {
            let i := 0
            for {} 1 {} {
                let bh := blobhash(i)
                if iszero(bh) {
                    break
                }
                i := add(i, 1)
            }
            c := i
        }
        require(c > 0, "no blob");
    }

    function undo(uint256 from, uint256 k) external onlyOwner {
        require(hashes[from + k] == bytes32(0), "not last");
        uint256 idx = from;
        while (k > 0) {
            emit Undone(idx);
            hashes[idx] = bytes32(0);
            total -= entries[idx].amount;
            unchecked {
                idx += 1;
                k -= 1;
            }
            if (hashes[idx] == bytes32(0)) {
                break;
            }
        }
        last = idx - 1;
    }

    function _sumTo(uint256 n) internal pure returns (uint256 s) {
        for (uint256 i = 0; i < n; i++) {
            s += i;
        }
    }

    function twice(uint256 n1, uint256 n2) external pure returns (uint256) {
        return _sumTo(n1) + _sumTo(n2);
    }

    function prove(uint256 index) external view {
        ICommit(verifier).verify(index, hashes[index]);
    }

    function share(uint256 a, uint256 b) external view returns (uint256) {
        return a / b + total % b;
    }

    function bump(uint256 a) external pure returns (uint256) {
        unchecked {
            return a + 1;
        }
    }

    function getLast() external view returns (uint256) {
        return last;
    }
}
