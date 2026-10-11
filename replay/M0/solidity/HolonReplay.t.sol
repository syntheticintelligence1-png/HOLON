// SPDX-License-Identifier: MIT
// HOLON M0 replay harness (Solidity side). Copied into a scratch copy of morph contracts/
// by holon/replay.py and run with `forge test --match-contract HolonReplay -vv`.
// It reads the L_dom_hdr witness from $HOLON_RESULTS/L_dom_hdr.json.
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";

/// Exposes the real header loader: Rollup._loadBatchHeader is internal.
contract HolonRollupHarness is Rollup {
    constructor() Rollup(53077) {}

    function loadBatchHeader(bytes calldata h) external pure returns (uint256 memPtr, bytes32 batchHash) {
        return _loadBatchHeader(h);
    }
}

contract HolonReplayTest is Test {
    HolonRollupHarness internal harness;

    function setUp() public {
        harness = new HolonRollupHarness();
    }

    function _witness() internal returns (bytes memory) {
        string memory json = vm.readFile(string.concat(vm.envString("HOLON_RESULTS"), "/L_dom_hdr.json"));
        return vm.parseBytes(vm.parseJsonString(json, ".witness.b"));
    }

    /// O1 / F12.1: Solidity accepts the 250-byte version-0 witness that Go rejects.
    function test_L_dom_hdr_witness_accepted() public {
        bytes memory b = _witness();
        (, bytes32 hash) = harness.loadBatchHeader(b);
        assertEq(b.length, 250);
        assertEq(uint8(b[0]), 0);
        console.log(string.concat("HOLON test_L_dom_hdr_witness_accepted passed len=", vm.toString(b.length),
            " version=0: _loadBatchHeader accepted; batchHash=", vm.toString(hash)));
    }

    /// Control: the model also says a 249-byte header with version 3 is rejected.
    function test_L_dom_hdr_control_version3_reverts() public {
        bytes memory b = new bytes(249);
        b[0] = bytes1(uint8(3));
        vm.expectRevert(bytes("Unsupported batch version"));
        harness.loadBatchHeader(b);
        console.log("HOLON test_L_dom_hdr_control_version3_reverts passed version=3 len=249 reverts");
    }
}
