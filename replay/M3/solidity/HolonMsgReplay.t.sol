// SPDX-License-Identifier: MIT
// HOLON M3 messenger replay (Solidity side). Copied into a scratch copy of the pinned morph
// contracts/ tree and run with `forge test --match-contract HolonMsgReplay -vv`.
//
// Deploys the REAL L1CrossDomainMessenger, the REAL L1MessageQueueWithGasPriceOracle and the
// REAL Whitelist, each behind a TransparentUpgradeableProxy with the real initialize calls.
// No vm.store and no mocks of the contracts under test. Logs one line per step:
//   HOLON <law> <step> ok <detail> / HOLON <law> <step> rev <reason>
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {L1CrossDomainMessenger} from "../contracts/l1/L1CrossDomainMessenger.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {Whitelist} from "../contracts/libraries/common/Whitelist.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

interface HolonVm {
    function prank(address) external;
    function deal(address, uint256) external;
    function toString(uint256) external pure returns (string memory);
    function toString(bytes memory) external pure returns (string memory);
}

contract HolonMsgReplayTest is Test {
    HolonVm internal constant HV = HolonVm(address(uint160(uint256(keccak256("hevm cheat code")))));

    address internal constant PROXY_ADMIN = address(0xAD);
    address internal constant FEE_VAULT = address(0xFEE);
    address internal constant ROLLUP = address(0xCAFE);
    address internal constant GATEWAY = address(0xE7);
    address internal constant ALICE = address(0xA11CE);
    address internal constant BOB = address(0xB0B);
    address internal constant TO = address(0x700);
    uint256 internal constant BASE_FEE = 1 gwei;
    uint32 internal constant GL = 200_000;

    L1CrossDomainMessenger internal msg1;
    L1MessageQueueWithGasPriceOracle internal queue;
    Whitelist internal wl;

    function deploy() internal {
        L1CrossDomainMessenger mimpl = new L1CrossDomainMessenger();
        msg1 = L1CrossDomainMessenger(payable(address(new TransparentUpgradeableProxy(address(mimpl), PROXY_ADMIN, ""))));
        L1MessageQueueWithGasPriceOracle qimpl =
            new L1MessageQueueWithGasPriceOracle(address(msg1), ROLLUP, GATEWAY);
        queue = L1MessageQueueWithGasPriceOracle(address(new TransparentUpgradeableProxy(address(qimpl), PROXY_ADMIN, "")));
        wl = new Whitelist(address(this));
        queue.initialize(10_000_000, address(wl));
        queue.setL2BaseFee(BASE_FEE);
        msg1.initialize(FEE_VAULT, ROLLUP, address(queue));
        HV.deal(ALICE, 10 ether);
        HV.deal(BOB, 10 ether);
    }

    function fee() internal view returns (uint256) {
        return uint256(GL) * BASE_FEE;
    }

    function reason(bytes memory data) internal view returns (string memory) {
        if (data.length >= 4 && bytes4(data) == 0x08c379a0) {
            bytes memory rest = new bytes(data.length - 4);
            for (uint256 i = 0; i < rest.length; i++) rest[i] = data[i + 4];
            return abi.decode(rest, (string));
        }
        return string.concat("raw:", HV.toString(data));
    }

    function trySend(address who, uint256 value, uint256 nonceHint) internal returns (uint256 nonce, string memory st) {
        nonce = queue.nextCrossDomainMessageIndex();
        HV.prank(who);
        (bool ok, bytes memory ret) = address(msg1).call{value: value}(
            abi.encodeWithSignature("sendMessage(address,uint256,bytes,uint256)", TO, 0, bytes("hi"), GL));
        st = ok ? "ok" : reason(ret);
    }

    function tryReplay(address who, uint256 nonce, uint256 value) internal returns (string memory st) {
        HV.prank(who);
        (bool ok, bytes memory ret) = address(msg1).call{value: value}(abi.encodeWithSignature(
            "replayMessage(address,address,uint256,uint256,bytes,uint32,address)",
            ALICE, TO, 0, nonce, bytes("hi"), GL, BOB));
        st = ok ? "ok" : reason(ret);
    }

    /// O34/F8: a third party can burn the sender's replay budget; the owner can lift it.
    function test_L_msg_budget_blocks_sender() public {
        deploy();
        uint256 mrt = msg1.maxReplayTimes();
        console.log("HOLON budget 0 maxReplayTimes", HV.toString(mrt));

        (uint256 n0, string memory st) = trySend(ALICE, fee(), 0);
        console.log("HOLON budget 1 send", st);
        require(keccak256(bytes(st)) == keccak256("ok"), st);

        for (uint256 i = 0; i < mrt; i++) {
            st = tryReplay(BOB, n0, fee());
            console.log(string.concat("HOLON budget ", HV.toString(i + 2), " replay(Bob)"), st);
            require(keccak256(bytes(st)) == keccak256("ok"), st);
        }
        st = tryReplay(ALICE, n0, fee());
        console.log(string.concat("HOLON budget ", HV.toString(mrt + 2), " replay(Alice)"), st);
        require(keccak256(bytes(st)) == keccak256(bytes("Exceed maximum replay times")), st);

        msg1.updateMaxReplayTimes(mrt + 1);
        st = tryReplay(ALICE, n0, fee());
        console.log("HOLON budget 9 replay-after-owner-lift", st);
        require(keccak256(bytes(st)) == keccak256("ok"), st);
    }

    /// O29: estimateCrossDomainMessageFee keys the whitelist waiver on _from (origin), not the
    /// replay caller. Alice whitelisted -> Bob replays free. Only Bob whitelisted -> replay of
    /// Alice's message still needs the fee.
    function test_L_msg_waiver_follows_origin() public {
        deploy();
        address[] memory one = new address[](1);

        one[0] = ALICE;
        wl.updateWhitelistStatus(one, true);
        (uint256 n0, string memory st) = trySend(ALICE, 0, 0);
        console.log("HOLON waiver 1 send(Alice,0wei)", string.concat(st, " feeVault=", HV.toString(FEE_VAULT.balance)));
        require(keccak256(bytes(st)) == keccak256("ok"), st);
        st = tryReplay(BOB, n0, 0);
        console.log("HOLON waiver 2 replay(Bob,0wei)", string.concat(st, " feeVault=", HV.toString(FEE_VAULT.balance)));
        require(keccak256(bytes(st)) == keccak256("ok"), st);
        require(FEE_VAULT.balance == 0, "fee vault received fee for whitelisted origin");

        // dual: only Bob whitelisted
        wl.updateWhitelistStatus(one, false);
        one[0] = BOB;
        wl.updateWhitelistStatus(one, true);
        uint256 n1 = queue.nextCrossDomainMessageIndex();
        (n1, st) = trySend(ALICE, fee(), 0);
        console.log("HOLON waiver 3 send(Alice,fee)", st);
        require(keccak256(bytes(st)) == keccak256("ok"), st);
        st = tryReplay(BOB, n1, 0);
        console.log("HOLON waiver 4 replay(Bob,0wei)", st);
        require(keccak256(bytes(st)) == keccak256(bytes("Insufficient msg.value for fee")), st);
    }
}
