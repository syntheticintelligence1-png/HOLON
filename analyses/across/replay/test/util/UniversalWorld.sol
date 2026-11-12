// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ReplayBase } from "./Base.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { MintableERC20 } from "across/test/MockERC20.sol";
import { Universal_Adapter } from "across/chain-adapters/Universal_Adapter.sol";
import { HubPoolStore } from "across/chain-adapters/utilities/HubPoolStore.sol";
import { Universal_SpokePool } from "across/spoke-pools/Universal_SpokePool.sol";
import { SP1Helios } from "across/sp1-helios/SP1Helios.sol";
import { SP1MockVerifier } from "@sp1-contracts/src/SP1MockVerifier.sol";
import { ERC1967Proxy } from "@openzeppelin/contracts-v4/proxy/ERC1967/ERC1967Proxy.sol";
import { IERC20 } from "@openzeppelin/contracts-v4/token/ERC20/IERC20.sol";
import { ITokenMessenger } from "across/external/interfaces/CCTPInterfaces.sol";

// L1: HubPool + Universal_Adapter (delegatecalled) + HubPoolStore, all unmodified.
// "L2": Universal_SpokePool instances reading L1 storage through the real SP1Helios light client; only the SP1 zk
// verifier is the upstream mock (accepts empty proofs). The permissioned updater role is held by this test and
// proves exactly the HubPoolStore slots that the store's StoredCallData events announce (vm.load = L1 state).
abstract contract UniversalWorld is ReplayBase {
    MintableERC20 dai;
    HubPoolStore store;
    Universal_Adapter uAdapter;
    SP1Helios helios;
    uint256 constant X = 777;
    uint256 constant Y = 888;
    uint256 constant SLOTS_PER_PERIOD = 8192;
    uint256 head = 1000;

    function _setUpUniversal() internal {
        vm.warp(1_790_000_000); // realistic clock so the light client's slot arithmetic is well-defined
        createHubPoolFixture();
        dai = fixture.dai;
        store = new HubPoolStore(address(fixture.hubPool));
        uAdapter = new Universal_Adapter(store, IERC20(address(0)), ITokenMessenger(address(0)), 0, address(0), 0, 0);
        address[] memory updaters = new address[](1);
        updaters[0] = address(this);
        helios = new SP1Helios(
            SP1Helios.InitParams({
                executionStateRoot: bytes32(uint256(3)),
                genesisTime: block.timestamp - head * 12,
                head: head,
                header: bytes32(uint256(2)),
                heliosProgramVkey: bytes32(uint256(5)),
                secondsPerSlot: 12,
                slotsPerEpoch: 32,
                slotsPerPeriod: SLOTS_PER_PERIOD,
                syncCommitteeHash: bytes32(uint256(4)),
                verifier: address(new SP1MockVerifier()),
                vkeyUpdater: address(0),
                updaters: updaters
            })
        );
        enableToken(X, address(dai), fixture.l2Dai);
        fixture.hubPool.setPoolRebalanceRoute(Y, address(dai), fixture.l2Dai);
        addLiquidity(dai, 1000 ether);
    }

    function _newSpoke() internal returns (Universal_SpokePool s) {
        Universal_SpokePool impl = new Universal_SpokePool(
            1 days,
            address(helios),
            address(store),
            address(fixture.weth),
            3600,
            21600,
            IERC20(address(0)),
            ITokenMessenger(address(0)),
            0,
            0,
            address(0)
        );
        s = Universal_SpokePool(
            payable(
                new ERC1967Proxy(
                    address(impl),
                    abi.encodeCall(Universal_SpokePool.initialize, (0, address(fixture.hubPool), address(fixture.hubPool)))
                )
            )
        );
    }

    // Updater step of the light client: prove the given HubPoolStore slots at a fresh head.
    function _prove(uint256[] memory nonces) internal returns (uint256 newHead) {
        SP1Helios.StorageSlot[] memory slots = new SP1Helios.StorageSlot[](nonces.length);
        for (uint256 i = 0; i < nonces.length; i++) {
            bytes32 key = keccak256(abi.encode(nonces[i], uint256(0)));
            slots[i] = SP1Helios.StorageSlot({ key: key, value: vm.load(address(store), key), contractAddress: address(store) });
        }
        newHead = head + 1;
        SP1Helios.ProofOutputs memory po = SP1Helios.ProofOutputs({
            executionStateRoot: keccak256(abi.encode("esr", newHead)),
            newHeader: keccak256(abi.encode("hdr", newHead)),
            nextSyncCommitteeHash: bytes32(0),
            newHead: newHead,
            prevHeader: helios.headers(head),
            prevHead: head,
            syncCommitteeHash: bytes32(uint256(4)),
            startSyncCommitteeHash: helios.syncCommittees(head / SLOTS_PER_PERIOD),
            slots: slots
        });
        helios.update("", abi.encode(po));
        head = newHead;
    }

    function _n1(uint256 n) internal pure returns (uint256[] memory a) {
        a = new uint256[](1);
        a[0] = n;
    }

    function _n2(uint256 n, uint256 m) internal pure returns (uint256[] memory a) {
        a = new uint256[](2);
        a[0] = n;
        a[1] = m;
    }
}
