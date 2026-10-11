// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";

contract RollupHarness is Rollup {
    constructor() Rollup(53077) {}

    function loadBatchHeader(bytes calldata h) external pure returns (uint256 memPtr, bytes32 batchHash) {
        return _loadBatchHeader(h);
    }
}

contract HolonReplayDomHdr is Test {
    RollupHarness internal harness;

    function setUp() public {
        harness = new RollupHarness();
    }

    function test_L_dom_hdr_witness_accepted() public view {
        bytes memory w = vm.envBytes("HOLON_DOM_WITNESS");
        assertGt(w.length, 249);
        assertEq(uint8(w[0]), 0);
        (, bytes32 h) = harness.loadBatchHeader(w);
        assertEq(h, keccak256(w));
        console2.log("OBSERVED _loadBatchHeader accepted witness, length", w.length);
        console2.logBytes32(h);
    }

    function test_version3_249_rejected() public {
        bytes memory w = new bytes(249);
        w[0] = bytes1(uint8(3));
        vm.expectRevert(bytes("Unsupported batch version"));
        harness.loadBatchHeader(w);
    }
}
