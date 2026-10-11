// SPDX-License-Identifier: MIT
// HOLON M2 refinement harness (Solidity side). Copied into a scratch copy of
// morph contracts/ by holon/native/refine.py and run with
// `forge test --match-contract HolonRefine -vv`.
// Reads $HOLON_VECTORS = {"v":[{"id":i,"b":"0x.."}]} and for every vector calls
// the real Rollup._loadBatchHeader, logging `HOLON <id> ok <batchHash>` or
// `HOLON <id> rev <reason>`.
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";

contract HolonRefineHarness is Rollup {
    constructor() Rollup(53077) {}

    function loadBatchHeader(bytes calldata h) external pure returns (uint256 memPtr, bytes32 batchHash) {
        return _loadBatchHeader(h);
    }
}

contract HolonRefineTest is Test {
    HolonRefineHarness internal harness;

    function setUp() public {
        harness = new HolonRefineHarness();
    }

    function test_refine() public {
        string memory json = vm.readFile(vm.envString("HOLON_VECTORS"));
        uint256 n = abi.decode(vm.parseJson(json, ".n"), (uint256));
        for (uint256 i = 0; i < n; i++) {
            bytes memory b = vm.parseBytes(vm.parseJsonString(json, string.concat(".v[", vm.toString(i), "].b")));
            (bool ok, bytes memory ret) =
                address(harness).staticcall(abi.encodeCall(HolonRefineHarness.loadBatchHeader, (b)));
            if (ok) {
                (, bytes32 hash) = abi.decode(ret, (uint256, bytes32));
                console.log(string.concat("HOLON ", vm.toString(i), " ok ", vm.toString(hash)));
            } else {
                console.log(string.concat("HOLON ", vm.toString(i), " rev ", _reason(ret)));
            }
        }
    }

    function _reason(bytes memory data) internal pure returns (string memory) {
        if (data.length >= 4 && bytes4(data) == 0x08c379a0) {
            bytes memory rest = new bytes(data.length - 4);
            for (uint256 i = 0; i < rest.length; i++) rest[i] = data[i + 4];
            return abi.decode(rest, (string));
        }
        if (data.length == 36 && bytes4(data) == 0x4e487b71) {
            uint256 code;
            assembly { code := mload(add(data, 36)) }
            return string.concat("panic:", vm.toString(code));
        }
        return "unknown";
    }
}
