// SPDX-License-Identifier: MIT
// HOLON M3 PAR replay harness (Solidity side), I98. Copied into a scratch copy of morph contracts/ by
// holon/replay.py (main_replay_par) and run with `forge test --match-contract HolonPar -vv`.
// It reads each witness from $HOLON_RESULTS/<law>.json. A test passes when the real code gives the claim's
// right side the value the witness's difference says it has, and logs one line HOLON <test> passed <observed>.
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";

/// Exposes the real header loader: Rollup._loadBatchHeader is internal.
contract HolonParRollupHarness is Rollup {
    constructor() Rollup(53077) {}

    function loadBatchHeader(bytes calldata h) external pure returns (uint256 memPtr, bytes32 batchHash) {
        return _loadBatchHeader(h);
    }
}

contract HolonParTest is Test {
    HolonParRollupHarness internal harness;

    function setUp() public {
        harness = new HolonParRollupHarness();
    }

    function _json(string memory law) internal view returns (string memory) {
        return vm.readFile(string.concat(vm.envString("HOLON_RESULTS"), "/", law, ".json"));
    }

    /// BatchHeaderBytes_validate(b) == ok_load_sol(b): the right side is the Solidity loader's acceptance.
    function test_L_par_dom_BatchHeaderBytes_validate_ok_load_sol() public {
        string memory json = _json("L_par_dom_BatchHeaderBytes_validate_ok_load_sol");
        bytes memory b = vm.parseBytes(vm.parseJsonString(json, ".witness.b"));
        bool rhs = vm.parseJsonBool(json, ".difference.rhs");
        bool ok;
        bytes32 hash;
        try harness.loadBatchHeader(b) returns (uint256, bytes32 h) {
            ok = true;
            hash = h;
        } catch {
            ok = false;
        }
        assertEq(ok, rhs);
        console.log(string.concat("HOLON test_L_par_dom_BatchHeaderBytes_validate_ok_load_sol passed len=",
            vm.toString(b.length), " _loadBatchHeader accepted=", ok ? "true" : "false", " batchHash=", vm.toString(hash)));
    }
}
