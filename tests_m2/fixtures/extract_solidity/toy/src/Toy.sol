// SPDX-License-Identifier: MIT
// HOLON I17 planted fixture (not target code): a toy contract whose extraction is known by construction.
pragma solidity =0.8.24;

import {PktCodec} from "./PktCodec.sol";

interface IFeed {
    function next(uint256 i) external view returns (bytes32);
}

contract Toy {
    struct Msg {
        uint8 kind;
        uint32 flags;
        uint64 extra;
        bytes32 root;
        bytes prev;
    }

    mapping(uint256 => bytes32) public digests;
    uint256 public last;
    address public feed;

    function submit(Msg calldata m) external {
        _emitPkt(m);
    }

    function _emitPkt(Msg calldata m) internal {
        require(m.kind <= 3, "bad kind");
        require(m.root != bytes32(0), "zero root");
        (uint256 p0, bytes32 prevDigest) = _loadPkt(m.prev);
        uint256 seq = PktCodec.getSeq(p0);
        require(seq == last, "stale");
        require(digests[seq] == prevDigest, "wrong prev");
        bytes32 mixed = _mix(m.flags);
        assembly {
            seq := add(seq, 1)
        }
        uint256 len = PktCodec.BASE_LEN;
        if (m.kind >= 2) {
            len = PktCodec.LONG_LEN;
        }
        uint256 ptr;
        assembly {
            ptr := mload(0x40)
            mstore(0x40, add(ptr, len))
        }
        _stamp(ptr, m.kind);
        PktCodec.putSeq(ptr, seq);
        PktCodec.putFlags(ptr, m.flags);
        PktCodec.putPad(ptr, 0);
        PktCodec.putRoot(ptr, bytes32(0));
        PktCodec.putRoot(ptr, m.root);
        if (m.kind >= 2) {
            PktCodec.putExtra(ptr, m.extra);
        }
        digests[seq] = PktCodec.digest(ptr, len);
        last = seq;
        emit Sent(seq, mixed);
    }

    event Sent(uint256 seq, bytes32 mixed);

    function _stamp(uint256 ptr, uint256 _tag) internal pure {
        PktCodec.putKind(ptr, _tag);
    }

    function _loadPkt(bytes calldata _prev) internal pure returns (uint256 p, bytes32 d) {
        require(_prev.length > 0, "empty");
        uint8 k = uint8(_prev[0]);
        uint256 n;
        if (k < 2) {
            (p, n) = PktCodec.load(_prev);
        } else if (k == 2 || k == 3) {
            (p, n) = PktCodec.loadLong(_prev);
        } else {
            revert("unknown kind");
        }
        d = PktCodec.digest(p, n);
    }

    function _mix(uint256 _flags) internal view returns (bytes32 acc) {
        if (_flags == 0) {
            return bytes32(0);
        }
        uint256 base;
        assembly {
            base := mload(0x40)
            mstore(0x40, add(base, 32))
        }
        for (uint256 i = 0; i < _flags; i++) {
            acc = IFeed(feed).next(i);
        }
        assembly {
            mstore(base, acc)
            acc := keccak256(base, 32)
        }
    }

    function _emitBad(uint256 _n) internal returns (bytes32 h) {
        uint256 ptr;
        assembly {
            ptr := mload(0x40)
            mstore(0x40, add(ptr, 32))
            switch lt(_n, 10)
            case 1 {
                mstore(ptr, 1)
            }
            default {
                mstore(ptr, 2)
            }
            h := keccak256(ptr, 32)
        }
        last = uint256(h);
    }

    function _emitEnv(uint256 _v) internal returns (bytes32 h) {
        uint256 ptr;
        assembly {
            ptr := mload(0x40)
            mstore(0x40, add(ptr, 33))
        }
        if (last > 5) {
            PktCodec.putKind(ptr, 1);
        } else {
            PktCodec.putKind(ptr, 2);
        }
        PktCodec.putRoot(ptr, bytes32(_v));
        h = PktCodec.digest(ptr, 33);
    }

    function bad(uint256 n) external returns (bytes32) {
        return _emitBad(n);
    }

    function env(uint256 v) external returns (bytes32) {
        return _emitEnv(v);
    }
}
