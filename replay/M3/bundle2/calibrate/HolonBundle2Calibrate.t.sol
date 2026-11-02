// SPDX-License-Identifier: MIT
// HOLON I84 calibration harness (tests_m3/test_bundle2_laws.py rules K2-K3 and D5; tools/calibrate_gas.py; the sidecar's
// calibration.strategy). From a fresh deployment (HolonBundle2LawsBase.lawsDeploy), setUp commits HOLON_K batches in
// order by the first active submitter (version 1, no L1 message, no blob, lastBlockNumber the batch's index,
// postStateRoot the index plus 1000, withdrawalRoot 0) at the deployment's clock, and prepares the challenge of batch
// lastFinalizedBatchIndex + 1 by the first challenger. The test function makes that one call.
//
// Forge runs setUp and a test as separate transactions, so the measured call's storage and accounts are as a fresh
// transaction finds them (cold, with their committed values as originals); the test function touches nothing the call
// touches before it. A transaction gas limit L (HOLON_TX_GAS) leaves the call frame L minus the calldata's intrinsic
// gas (21000 + 4 per zero byte + 16 per nonzero byte, Cancun), which the frame is given; without HOLON_TX_GAS the frame
// is unbounded.
//
// It logs, in setUp:  HOLON-CAL-STATE <k> lastCommittedBatchIndex=<v> lastFinalizedBatchIndex=<v> (the storage the
// count term of the cost site reads, by name)
// and in the test:    HOLON-CAL <k> <ok 0|1> <frame gas used> <refund> <tx gas limit or 0> <frame limit or 0> <calldata>
pragma solidity =0.8.24;

import {console} from "forge-std/Test.sol";
import {HolonBundle2LawsBase, HolonLawsVm} from "./HolonBundle2LawsBase.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";

contract HolonBundle2CalibrateTest is HolonBundle2LawsBase {
    uint256 internal k;
    uint256 internal deposit;
    bytes internal cd;

    function setUp() public {
        LV.pauseGasMetering();
        k = HV.envUint("HOLON_K");
        uint256[] memory init = lawsInit();
        lawsDeploy(0, init, LV.envUint("HOLON_VERSIONS", ","));
        uint256 prev = init[4];
        for (uint256 i = 1; i <= k; i++) {
            (bool ok,) = commitRow(0, row(2, 1, i - 1, 0, i, prev, 1000 + i));
            require(ok, "HolonBundle2Calibrate: a commit failed");
            prev = 1000 + i;
        }
        uint256 lfi = rollup.lastFinalizedBatchIndex();
        uint256 lci = rollup.lastCommittedBatchIndex();
        console.log(string.concat("HOLON-CAL-STATE ", HV.toString(k), " lastCommittedBatchIndex=", HV.toString(lci),
                                  " lastFinalizedBatchIndex=", HV.toString(lfi)));
        deposit = sub.challengeDeposit();
        cd = abi.encodeCall(Rollup.challengeState, (uint64(lfi + 1), keccak256(hdrs[0][lfi + 1])));
        LV.resumeGasMetering();
    }

    function intrinsic(bytes memory data) internal pure returns (uint256 g) {
        g = 21000;
        for (uint256 i = 0; i < data.length; i++) g += data[i] == 0 ? 4 : 16;
    }

    function test_challenge() public {
        bytes memory data = cd;
        uint256 value = deposit;
        address target = address(rollup);
        address challenger = who2addr(4);
        uint256 txGas = LV.envOr("HOLON_TX_GAS", uint256(0));
        uint256 frame = txGas == 0 ? 0 : txGas - intrinsic(data);
        bool ok;
        HV.prank(challenger);
        if (frame == 0) {
            (ok,) = target.call{value: value}(data);
        } else {
            (ok,) = target.call{value: value, gas: frame}(data);
        }
        HolonLawsVm.Gas memory g = LV.lastCallGas();
        require(g.gasRefunded >= 0, "HolonBundle2Calibrate: a negative refund");
        console.log(string.concat("HOLON-CAL ", HV.toString(k), " ", ok ? "1" : "0", " ", HV.toString(uint256(g.gasTotalUsed)),
                                  " ", HV.toString(uint256(uint64(g.gasRefunded))), " ", HV.toString(txGas), " ",
                                  HV.toString(frame), " ", hex0x(data)));
    }
}
