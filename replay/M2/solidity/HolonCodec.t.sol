// SPDX-License-Identifier: MIT
// HOLON I16 refinement harness, Solidity side (holon/refinement.py; binding replay/M2/implementations.json).
//
// holon refine copies this file into a scratch Foundry project holding morph contracts/ at the facts'
// commit (laid out as holon/replay.py::replay_solidity does) and runs
//   HOLON_CODEC_IN=holon_codec_in.txt HOLON_CODEC_OUT=holon_codec_out.txt
//   forge test --match-contract HolonCodec --offline --use <solc 0.8.24> -vv
// It calls the real code on every input and writes what the real code returns; it compares nothing.
//
// Input: one line per item, "0x" + hex of (op byte || payload), then a line "0x" that ends the file.
//   op 1 (build)  payload = abi.encode(HolonHeader): the values the header build block of
//                 Rollup._commitBatchWithBatchData stores; output: the header that block hashes, "0x" + hex
//   op 2 (load)   payload = the bytes given to Rollup._loadBatchHeader; output: "true" if it returns,
//                 "false" if it reverts
// Output: one line per item, in input order, then "done <n>".
// Gas metering is paused: the harness measures what the code returns, not what it costs.
pragma solidity =0.8.24;

import {Test} from "forge-std/Test.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {BatchHeaderCodecV0} from "../contracts/libraries/codec/BatchHeaderCodecV0.sol";
import {BatchHeaderCodecV1} from "../contracts/libraries/codec/BatchHeaderCodecV1.sol";

/// Reaches the real header loader: Rollup._loadBatchHeader is internal.
contract HolonCodecRollup is Rollup {
    constructor() Rollup(53077) {}

    function holonLoad(bytes calldata batchHeader) external pure returns (uint256 memPtr, bytes32 batchHash) {
        return _loadBatchHeader(batchHeader);
    }
}

contract HolonCodecTest is Test {
    /// The values the build block stores, in the order it stores them (sequencerSetVerifyHash is the
    /// constant bytes32(0) there, so it is no input).
    struct HolonHeader {
        uint8 version;
        uint64 batchIndex;
        uint64 l1MessagePopped;
        uint64 totalL1MessagePopped;
        bytes32 dataHash;
        bytes32 blobVersionedHash;
        bytes32 prevStateRoot;
        bytes32 postStateRoot;
        bytes32 withdrawalRoot;
        bytes32 parentBatchHash;
        uint64 lastBlockNumber;
    }

    HolonCodecRollup internal rollup;

    function setUp() public {
        rollup = new HolonCodecRollup();
    }

    /// The header build block of Rollup._commitBatchWithBatchData, store call by store call.
    function holonBuild(HolonHeader memory h) internal pure returns (bytes memory header) {
        uint256 _headerLength = BatchHeaderCodecV0.BATCH_HEADER_LENGTH;
        if (h.version >= 1) {
            _headerLength = BatchHeaderCodecV1.BATCH_HEADER_LENGTH;
        }
        uint256 _batchPtr;
        assembly {
            _batchPtr := mload(0x40)
            mstore(0x40, add(_batchPtr, _headerLength))
        }
        BatchHeaderCodecV0.storeVersion(_batchPtr, h.version);
        BatchHeaderCodecV0.storeBatchIndex(_batchPtr, h.batchIndex);
        BatchHeaderCodecV0.storeL1MessagePopped(_batchPtr, h.l1MessagePopped);
        BatchHeaderCodecV0.storeTotalL1MessagePopped(_batchPtr, h.totalL1MessagePopped);
        BatchHeaderCodecV0.storeDataHash(_batchPtr, h.dataHash);
        BatchHeaderCodecV0.storeBlobVersionedHash(_batchPtr, h.blobVersionedHash);
        BatchHeaderCodecV0.storePrevStateHash(_batchPtr, h.prevStateRoot);
        BatchHeaderCodecV0.storePostStateHash(_batchPtr, h.postStateRoot);
        BatchHeaderCodecV0.storeWithdrawRootHash(_batchPtr, h.withdrawalRoot);
        BatchHeaderCodecV0.storeSequencerSetVerifyHash(_batchPtr, bytes32(0));
        BatchHeaderCodecV0.storeParentBatchHash(_batchPtr, h.parentBatchHash);
        if (h.version >= 1) {
            BatchHeaderCodecV1.storeLastBlockNumber(_batchPtr, h.lastBlockNumber);
        }
        // the bytes computeBatchHash(_batchPtr, _headerLength) hashes
        header = new bytes(_headerLength);
        assembly {
            for {
                let i := 0
            } lt(i, _headerLength) {
                i := add(i, 32)
            } {
                mstore(add(add(header, 32), i), mload(add(_batchPtr, i)))
            }
        }
    }

    /// One item, as an external call so that each item starts from fresh memory.
    function holonItem(bytes calldata item) external view returns (string memory) {
        require(item.length >= 1, "holon codec: empty item");
        uint8 op = uint8(item[0]);
        if (op == 1) {
            HolonHeader memory h = abi.decode(item[1:], (HolonHeader));
            return vm.toString(holonBuild(h));
        }
        if (op == 2) {
            try rollup.holonLoad(item[1:]) returns (uint256, bytes32) {
                return "true";
            } catch {
                return "false";
            }
        }
        revert("holon codec: unknown op");
    }

    function test_holon_codec() public {
        vm.pauseGasMetering();
        string memory inPath = vm.envString("HOLON_CODEC_IN");
        string memory outPath = vm.envString("HOLON_CODEC_OUT");
        uint256 free;
        assembly {
            free := mload(0x40)
        }
        uint256 n = 0;
        while (true) {
            assembly {
                mstore(0x40, free) // nothing an item allocates here outlives it: its output is written below
            }
            bytes memory item = vm.parseBytes(vm.readLine(inPath));
            if (item.length == 0) {
                break;
            }
            vm.writeLine(outPath, this.holonItem(item));
            n += 1;
        }
        vm.writeLine(outPath, string.concat("done ", vm.toString(n)));
    }
}
