// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { UniversalWorld } from "./util/UniversalWorld.sol";
import { Universal_SpokePool } from "across/spoke-pools/Universal_SpokePool.sol";

// Channel property FIFO(admin): admin messages take effect in the order the HubPool owner issued them.
// HubPoolStore assigns increasing nonces (dataUuid++), but Universal_SpokePool.executeMessage is permissionless and
// accepts any proven nonce in any order (only a per-nonce replay bit). Final spoke state = last DELIVERED message.
contract T07_UniversalReorder is UniversalWorld {
    Universal_SpokePool spokeX;

    function setUp() public {
        _setUpUniversal();
        spokeX = _newSpoke();
        fixture.hubPool.setCrossChainContracts(X, address(uAdapter), address(spokeX));
    }

    function test_pauseThenUnpauseReordered() public {
        bytes memory unpause = abi.encodeWithSignature("pauseDeposits(bool)", false);
        bytes memory pause = abi.encodeWithSignature("pauseDeposits(bool)", true);
        fixture.hubPool.relaySpokePoolAdminFunction(X, unpause); // nonce 0
        fixture.hubPool.relaySpokePoolAdminFunction(X, pause); // nonce 1: owner's latest intent = paused
        uint256 h = _prove(_n2(0, 1));
        vm.startPrank(makeAddr("anyone"));
        spokeX.executeMessage(1, abi.encode(address(spokeX), pause), h);
        spokeX.executeMessage(0, abi.encode(address(spokeX), unpause), h);
        vm.stopPrank();
        assertFalse(spokeX.pausedDeposits(), "final state contradicts the owner's last instruction");
    }
}
