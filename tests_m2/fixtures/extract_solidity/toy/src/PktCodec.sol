// SPDX-License-Identifier: MIT
// HOLON I17 planted fixture (not target code): a toy packet codec whose extraction is known by construction.
pragma solidity =0.8.24;

library PktCodec {
    uint256 internal constant BASE_LEN = 49;
    uint256 internal constant LONG_LEN = 57;

    function load(bytes calldata _pkt) internal pure returns (uint256 ptr, uint256 len) {
        len = _pkt.length;
        require(len >= BASE_LEN, "pkt short");
        assembly {
            ptr := mload(0x40)
            calldatacopy(ptr, _pkt.offset, len)
            mstore(0x40, add(ptr, len))
        }
    }

    function loadLong(bytes calldata _pkt) internal pure returns (uint256 ptr, uint256 len) {
        len = _pkt.length;
        require(len == LONG_LEN, "pkt length");
        assembly {
            ptr := mload(0x40)
            calldatacopy(ptr, _pkt.offset, len)
            mstore(0x40, add(ptr, len))
        }
    }

    function getSeq(uint256 ptr) internal pure returns (uint256 _seq) {
        assembly {
            _seq := shr(192, mload(add(ptr, 1)))
        }
    }

    function putKind(uint256 ptr, uint256 _kind) internal pure {
        assembly {
            mstore8(ptr, _kind)
        }
    }

    function putSeq(uint256 ptr, uint256 _seq) internal pure {
        assembly {
            mstore(add(ptr, 1), shl(192, _seq))
        }
    }

    function putFlags(uint256 ptr, uint256 _flags) internal pure {
        assembly {
            mstore(add(ptr, 9), shl(224, _flags))
        }
    }

    function putPad(uint256 ptr, uint256 _pad) internal pure {
        assembly {
            mstore(add(ptr, 13), shl(224, _pad))
        }
    }

    function putRoot(uint256 ptr, bytes32 _root) internal pure {
        assembly {
            mstore(add(ptr, 17), _root)
        }
    }

    function putExtra(uint256 ptr, uint256 _extra) internal pure {
        assembly {
            mstore(add(ptr, 49), shl(192, _extra))
        }
    }

    function digest(uint256 ptr, uint256 len) internal pure returns (bytes32 h) {
        assembly {
            h := keccak256(ptr, len)
        }
    }
}
