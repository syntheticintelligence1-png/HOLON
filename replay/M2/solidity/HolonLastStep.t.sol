// SPDX-License-Identifier: MIT
// HOLON M2 last-step replay (holon/mreplay.py, `holon replay --milestone M2`; I15). Written for holon; it reuses the
// M1 trace harness (replay/M1/solidity/HolonTraceReplay.t.sol) unchanged, both copied into a scratch copy of morph's
// contracts/ tree.
//
// One model trace per run, from the JSON file $HOLON_LAST_TRACE: {"data": [F, W, D, t0, r0, nsteps, rows...]}, each
// row the harness's step encoding (W words). The deployment and every step but the last run in setUp(); the last step
// alone runs in test_last(), so that a debugger dump of test_last (forge test --debug --dump) holds that step's
// execution only. holon locates the step's Panic in that dump with solc's runtime source map
// (holon.mreplay.locate_panic). Step lines are the harness's: HOLON 0 <step> ok <hash> | HOLON 0 <step> rev <reason>.
pragma solidity =0.8.24;

import {HolonTraceReplayTest} from "./HolonTraceReplay.t.sol";

contract HolonLastStepTest is HolonTraceReplayTest {
    uint256[] internal rows;
    uint256 internal steps;

    function setUp() public {
        uint256[] memory d = HV.parseJsonUintArray(HV.readFile(HV.envString("HOLON_LAST_TRACE")), ".data");
        require(d.length >= 6 + W && d[5] >= 1 && d.length == 6 + d[5] * W, "HOLON_LAST_TRACE: malformed");
        steps = d[5];
        for (uint256 i = 0; i < d.length; i++) rows.push(d[i]);
        deploy(0, d[0], d[1], d[2], d[3], d[4]);
        for (uint256 si = 0; si + 1 < steps; si++) step(0, si, d, 6 + si * W);
    }

    function test_last() public {
        step(0, steps - 1, rows, 6 + (steps - 1) * W);
    }
}
