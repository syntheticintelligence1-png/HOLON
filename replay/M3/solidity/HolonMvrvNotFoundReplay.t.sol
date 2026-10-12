// SPDX-License-Identifier: MIT
// HOLON M3 MVRV not-found replay (Solidity side). Copied into a scratch copy of the pinned
// morph contracts/ tree and run with `forge test --match-contract HolonMvrvNotFoundReplay -vv`.
//
// Deploys the REAL MultipleVersionRollupVerifier (real constructor + real initialize).
// The only stand-in is LastFinalizedIndex, which supplies the one IRollup method MVRV reads
// (lastFinalizedBatchIndex) — rollup is a dependency, not a contract under test.
// No vm.store, no etched code, no mocks of MVRV itself.
// Logs one line per probe: HOLON mvrv <step> ok / HOLON mvrv <step> rev <hexdata>
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {MultipleVersionRollupVerifier} from "../contracts/l1/rollup/MultipleVersionRollupVerifier.sol";
import {IZkEvmVerifier} from "../contracts/libraries/verifier/IZkEvmVerifier.sol";

/// Minimal stand-in for the rollup dependency: the only thing MVRV calls on it.
contract LastFinalizedIndex {
    function lastFinalizedBatchIndex() external pure returns (uint256) {
        return 0;
    }
}

/// A real code-bearing verifier target: verifyBatch exists and succeeds.
contract AcceptingVerifier {
    function verifyBatch(bytes calldata, bytes32) external view {}
}

contract HolonMvrvNotFoundReplayTest is Test {
    MultipleVersionRollupVerifier internal mvrv;
    AcceptingVerifier internal accepting;

    function deploy() internal {
        uint256[] memory vs = new uint256[](0);
        address[] memory as_ = new address[](0);
        mvrv = new MultipleVersionRollupVerifier(vs, as_);
        mvrv.initialize(address(new LastFinalizedIndex()));
        accepting = new AcceptingVerifier();
    }

    function vap(uint256 v, uint256 idx) internal returns (bool ok, bytes memory data) {
        (ok, data) = address(mvrv).call(
            abi.encodeCall(MultipleVersionRollupVerifier.verifyAggregateProof, (v, idx, "", bytes32(0))));
    }

    function logResult(string memory step, bool ok, bytes memory data) internal view {
        if (ok) {
            console.log("HOLON mvrv %s ok", step);
        } else {
            console.log("HOLON mvrv %s rev %s", step, vm.toString(data));
        }
    }

    /// Probe: unregistered version 3, batch 1. getVerifier returns address(0);
    /// solc's extcodesize check on the code-less target reverts with empty data.
    function test_probe() public {
        deploy();
        (bool ok, bytes memory data) = vap(3, 1);
        logResult("vap_unregistered", ok, data);
        assertTrue(!ok);
        assertEq(data.length, 0);
    }

    /// Control A: code-bearing verifier at st=10. idx=9 hits the extracted
    /// not-found revert; idx=10 passes the guard and verifyBatch succeeds.
    function test_control_contract_verifier() public {
        deploy();
        mvrv.updateVerifier(3, 10, address(accepting));
        (bool ok9, bytes memory d9) = vap(3, 9);
        logResult("ctrlA_idx9", ok9, d9);
        assertTrue(!ok9);
        assertEq(bytes4(d9), MultipleVersionRollupVerifier.ErrorVerifierNotFound.selector);
        (bool ok10, bytes memory d10) = vap(3, 10);
        logResult("ctrlA_idx10", ok10, d10);
        assertTrue(ok10);
    }

    /// Control B: EOA verifier at st=10. idx=10 passes the guard but the
    /// code-less verifyBatch target reverts with empty data.
    function test_control_eoa_verifier() public {
        deploy();
        mvrv.updateVerifier(3, 10, address(0xE0A));
        (bool ok10, bytes memory d10) = vap(3, 10);
        logResult("ctrlB_idx10", ok10, d10);
        assertTrue(!ok10);
        assertEq(d10.length, 0);
    }
}
