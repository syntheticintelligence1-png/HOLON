// SPDX-License-Identifier: MIT
// HOLON I92 replay harness (holon/symb/replay.py; rule K7 of tests_m3/test_sym_bundle.py). GENERATED; do not edit.
// The bundle harness (HolonBundleTest) with two more step kinds:
//   kind 4  the block time, absolute: payload = abi.encode(uint256 t)
//   kind 5  a member's implementation: payload = abi.encode(uint256 member index, bytes code): code (creation code
//           with its constructor's arguments) is deployed and the member's proxy upgraded to it by the proxy admin;
//           empty code upgrades it back to the deployment's implementation
// Each prints an env record (S ... env), so that every step has one record.
pragma solidity =0.8.24;

import {HolonBundleTest} from "./HolonBundle.t.sol";
import {ITransparentUpgradeableProxy} from
    "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

contract HolonSymbTest is HolonBundleTest {
    address[] internal holonImpl0;

    function holonSymbStep(uint256 tid, uint256 id, bytes memory raw) internal {
        (uint8 kind, bytes memory payload) = abi.decode(raw, (uint8, bytes));
        if (kind == 4) {
            BV.warp(abi.decode(payload, (uint256)));
            BV.startStateDiffRecording();
            envRecord(tid, id, BV.stopAndReturnStateDiff());
        } else if (kind == 5) {
            (uint256 mi, bytes memory code) = abi.decode(payload, (uint256, bytes));
            address impl = holonImpl0[mi];
            if (code.length > 0) {
                assembly {
                    impl := create(0, add(code, 32), mload(code))
                }
                require(impl != address(0), "HolonSymb: the implementation's creation failed");
            }
            BV.startStateDiffRecording();
            BV.prank(PROXY_ADMIN);
            ITransparentUpgradeableProxy(payable(members[mi])).upgradeTo(impl);
            envRecord(tid, id, BV.stopAndReturnStateDiff());
        } else {
            holonStep(tid, id, raw);
        }
    }

    function test_symb() public {
        BV.pauseGasMetering();
        string memory js = BV.readFile(BV.envString("HOLON_STEPS_IN"));
        holonOut = BV.envString("HOLON_STEPS_OUT");
        uint256[] memory lens = BV.parseJsonUintArray(js, ".lens");
        bytes[] memory steps = BV.parseJsonBytesArray(js, ".steps");
        uint256[] memory init = BV.parseJsonUintArray(js, ".init");
        address[] memory w = BV.parseJsonAddressArray(js, ".watch");
        for (uint256 i = 0; i < w.length; i++) watched.push(w[i]);
        uint256 p = 0;
        for (uint256 tid = 0; tid < lens.length; tid++) {
            uint256 snap0 = BV.snapshotState();
            holonBegin(tid, init);
            delete holonImpl0;
            for (uint256 i = 0; i < members.length; i++) {
                holonImpl0.push(address(uint160(uint256(BV.load(members[i], EIP1967_IMPLEMENTATION)))));
            }
            for (uint256 si = 0; si < lens[tid]; si++) holonSymbStep(tid, si, steps[p + si]);
            p += lens[tid];
            holonLine(string.concat("E ", dec(tid), " ", dec(lens[tid])));
            BV.revertToState(snap0);
            BV.deleteStateSnapshot(snap0);
        }
        holonLine(string.concat("DONE 0 ", dec(lens.length)));
    }
}
