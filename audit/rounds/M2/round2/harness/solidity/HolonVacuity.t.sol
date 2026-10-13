// SPDX-License-Identifier: MIT
// HOLON I21 (audit round M2/2, auditor A4) hypothesis harness, Solidity side (holon/audit/vacuity.py). It runs
// contracts and libraries of the pinned checkout, and the EVM, on the inputs it is given and writes what they
// return; holon/audit/vacuity.py judges the hypotheses from these outputs. It judges nothing itself.
//
// holon audit vacuity copies this file into the round's scratch Foundry project (the one holon audit hostile
// builds: the pinned checkout's contracts) and runs
//   HOLON_VACUITY_ITEM=<item> HOLON_HOSTILE_IN=<in> HOLON_HOSTILE_OUT=<out>
//   forge test --match-contract '^HolonVacuityTest$' --offline --use <solc>
// Input: one "0x" line per case, then a line "0x". Output: one line per case (below), then "done <n>".
//   keccak_words  case abi.encode(bytes32[] words): "<i> <keccak256(abi.encodePacked(words))>" (the EVM's KECCAK256)
//   header_hash   case: a header's bytes, loaded as Rollup._loadBatchHeader loads it (BatchHeaderCodecV0 or V1
//                 loadAndValidate by its version byte) and hashed by BatchHeaderCodecV0.computeBatchHash:
//                 "<i> 1 <hash>" or "<i> 0 <revert data>"
//   submitter     case abi.encode(uint8[] ops): the ops from a fresh Submitter (behind a proxy, initialized with
//                 minimumStake 1 ether, challengeDeposit 0.1 ether, rewardPercentage 50; the rollup is a view stand-in
//                 with code that reports batch indices 0 and calls slash), one line per op:
//                 "<i> <k> <op> <ok> <registered> <stakeOf> <withdrawing> <slashed> <isActive> <challengeDeposit>
//                  <minimumStake>" for the submitter S; slashed is 1 after a successful slash of S
//                 ops 0 addSubmitter(S) by the owner; 1 stake(S) with the current minimumStake; 2 setMinimumStake(
//                 minimumStake + 1 ether); 3 updateChallengeDeposit(challengeDeposit + 1); 4 withdraw() by S;
//                 5 removeSubmitter(S); 6 slash(S) by the rollup; 7 claimWithdrawal(S) by S
//   messenger     case abi.encode(address to, uint256 value, bytes message, uint256 gasLimit), sent in order through
//                 one L1CrossDomainMessenger wired to one L1MessageQueueWithGasPriceOracle (both behind proxies,
//                 maxGasLimit 10,000,000, a Whitelist with no entry, l2BaseFee 0) with msg.value = value:
//                 "<i> <ok> <next index before> <next index after> <QueueTransaction logs of the queue> <their
//                  queueIndex values, comma-separated or ->"
pragma solidity =0.8.24;

import {Submitter} from "../contracts/l1/rollup/Submitter.sol";
import {L1CrossDomainMessenger} from "../contracts/l1/L1CrossDomainMessenger.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {Whitelist} from "../contracts/libraries/common/Whitelist.sol";
import {BatchHeaderCodecV0} from "../contracts/libraries/codec/BatchHeaderCodecV0.sol";
import {BatchHeaderCodecV1} from "../contracts/libraries/codec/BatchHeaderCodecV1.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

interface HolonVacuityVm {
    struct Log {
        bytes32[] topics;
        bytes data;
        address emitter;
    }

    function snapshotState() external returns (uint256);
    function revertToState(uint256) external returns (bool);
    function prank(address) external;
    function deal(address, uint256) external;
    function readLine(string calldata) external returns (string memory);
    function writeLine(string calldata, string calldata) external;
    function envString(string calldata) external view returns (string memory);
    function parseBytes(string calldata) external pure returns (bytes memory);
    function toString(bytes calldata) external pure returns (string memory);
    function toString(bytes32) external pure returns (string memory);
    function toString(uint256) external pure returns (string memory);
    function pauseGasMetering() external;
    function recordLogs() external;
    function getRecordedLogs() external returns (Log[] memory);
}

/// The rollup a Submitter is initialized with: code, batch indices 0, and the caller of slash.
contract HolonRollupView {
    function lastCommittedBatchIndex() external pure returns (uint256) {
        return 0;
    }

    function lastFinalizedBatchIndex() external pure returns (uint256) {
        return 0;
    }

    function slash(Submitter s, address who) external {
        s.slash(who);
    }

    receive() external payable {}
}

/// Rollup._loadBatchHeader's loading and hashing, through the codec libraries it calls.
contract HolonHeaderHasher {
    function hash(bytes calldata h) external pure returns (bytes32) {
        uint256 v = h.length == 0 ? 0 : uint8(h[0]);
        require(h.length > 0, "Empty batch header");
        uint256 ptr;
        uint256 len;
        if (v == 0) {
            (ptr, len) = BatchHeaderCodecV0.loadAndValidate(h);
        } else if (v == 1 || v == 2) {
            (ptr, len) = BatchHeaderCodecV1.loadAndValidate(h);
        } else {
            revert("Unsupported batch version");
        }
        return BatchHeaderCodecV0.computeBatchHash(ptr, len);
    }
}

contract HolonVacuityTest {
    HolonVacuityVm internal constant XV = HolonVacuityVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address internal constant ADMIN = address(0xAD);
    address internal constant S = address(0x5B);
    string internal inPath;
    string internal outPath;

    function line(string memory s) internal {
        XV.writeLine(outPath, s);
    }

    function b(bool x) internal pure returns (string memory) {
        return x ? "1" : "0";
    }

    function u(uint256 x) internal pure returns (string memory) {
        return XV.toString(x);
    }

    // ------------------------------------------------------------ items
    function keccakWords(uint256 i, bytes memory raw) internal {
        bytes32[] memory w = abi.decode(raw, (bytes32[]));
        line(string.concat(u(i), " ", XV.toString(keccak256(abi.encodePacked(w)))));
    }

    function headerHash(HolonHeaderHasher hh, uint256 i, bytes memory raw) internal {
        try hh.hash(raw) returns (bytes32 h) {
            line(string.concat(u(i), " 1 ", XV.toString(h)));
        } catch (bytes memory r) {
            line(string.concat(u(i), " 0 ", XV.toString(r)));
        }
    }

    function deploySubmitter() internal returns (Submitter sub, HolonRollupView rv) {
        rv = new HolonRollupView();
        Submitter impl = new Submitter();
        sub = Submitter(address(new TransparentUpgradeableProxy(address(impl), ADMIN, "")));
        sub.initialize(address(this), address(rv), 1 ether, 0.1 ether, 50);
        XV.deal(S, 100 ether);
    }

    function op(Submitter sub, HolonRollupView rv, uint8 k) internal returns (bool ok) {
        bytes memory data;
        address from = address(this);
        uint256 value = 0;
        if (k == 0) data = abi.encodeCall(Submitter.addSubmitter, (S));
        else if (k == 1) {
            data = abi.encodeCall(Submitter.stake, (S));
            from = S;
            value = sub.minimumStake();
        } else if (k == 2) data = abi.encodeCall(Submitter.setMinimumStake, (sub.minimumStake() + 1 ether));
        else if (k == 3) data = abi.encodeCall(Submitter.updateChallengeDeposit, (sub.challengeDeposit() + 1));
        else if (k == 4) {
            data = abi.encodeCall(Submitter.withdraw, ());
            from = S;
        } else if (k == 5) data = abi.encodeCall(Submitter.removeSubmitter, (S));
        else if (k == 6) {
            (ok,) = address(rv).call(abi.encodeCall(HolonRollupView.slash, (sub, S)));
            return ok;
        } else if (k == 7) {
            data = abi.encodeCall(Submitter.claimWithdrawal, (S));
            from = S;
        } else revert("holon vacuity: unknown op");
        if (from != address(this)) XV.prank(from);
        (ok,) = address(sub).call{value: value}(data);
    }

    function submitter(uint256 i, bytes memory raw, uint256 snap) internal {
        uint8[] memory ops = abi.decode(raw, (uint8[]));
        require(XV.revertToState(snap), "holon vacuity: no snapshot");
        (Submitter sub, HolonRollupView rv) = deploySubmitter();
        bool slashed = false;
        for (uint256 k = 0; k < ops.length; k++) {
            bool ok = op(sub, rv, ops[k]);
            if (ok && ops[k] == 6) slashed = true;
            line(observation(sub, i, k, ops[k], ok, slashed));
        }
    }

    function observation(Submitter sub, uint256 i, uint256 k, uint8 o, bool ok, bool slashed)
        internal view returns (string memory s) {
        s = string.concat(u(i), " ", u(k), " ", u(o), " ", b(ok));
        s = string.concat(s, " ", b(sub.registered(S)), " ", u(sub.stakeOf(S)), " ", b(sub.withdrawing(S)));
        s = string.concat(s, " ", b(slashed), " ", b(sub.isActive(S)), " ", u(sub.challengeDeposit()));
        s = string.concat(s, " ", u(sub.minimumStake()));
    }

    L1CrossDomainMessenger internal messengerC;
    L1MessageQueueWithGasPriceOracle internal queueC;

    function deployMessenger() internal {
        L1CrossDomainMessenger mimpl = new L1CrossDomainMessenger();
        messengerC = L1CrossDomainMessenger(payable(address(new TransparentUpgradeableProxy(address(mimpl), ADMIN, ""))));
        address rollupAddr = address(new HolonRollupView());
        L1MessageQueueWithGasPriceOracle qimpl =
            new L1MessageQueueWithGasPriceOracle(address(messengerC), rollupAddr, address(0xE7));
        queueC = L1MessageQueueWithGasPriceOracle(address(new TransparentUpgradeableProxy(address(qimpl), ADMIN, "")));
        Whitelist wl = new Whitelist(address(this));
        queueC.initialize(10_000_000, address(wl));
        messengerC.initialize(address(0xFEE), rollupAddr, address(queueC));
        XV.deal(address(this), 10_000 ether);
    }

    function messenger(uint256 i, bytes memory raw) internal {
        (address to, uint256 value, bytes memory message, uint256 gasLimit) =
            abi.decode(raw, (address, uint256, bytes, uint256));
        uint256 before = queueC.nextCrossDomainMessageIndex();
        XV.recordLogs();
        (bool ok,) = address(messengerC).call{value: value}(
            abi.encodeWithSignature("sendMessage(address,uint256,bytes,uint256)", to, value, message, gasLimit));
        HolonVacuityVm.Log[] memory logs = XV.getRecordedLogs();
        bytes32 topic = keccak256("QueueTransaction(address,address,uint256,uint64,uint256,bytes)");
        uint256 n = 0;
        string memory idx = "";
        for (uint256 j = 0; j < logs.length; j++) {
            if (logs[j].emitter != address(queueC) || logs[j].topics.length == 0 || logs[j].topics[0] != topic) continue;
            (, uint64 qi,,) = abi.decode(logs[j].data, (uint256, uint64, uint256, bytes));
            idx = n == 0 ? u(qi) : string.concat(idx, ",", u(qi));
            n += 1;
        }
        line(string.concat(u(i), " ", b(ok), " ", u(before), " ", u(queueC.nextCrossDomainMessageIndex()), " ", u(n),
            " ", n == 0 ? "-" : idx));
    }

    function test_vacuity() public {
        XV.pauseGasMetering();
        string memory item = XV.envString("HOLON_VACUITY_ITEM");
        inPath = XV.envString("HOLON_HOSTILE_IN");
        outPath = XV.envString("HOLON_HOSTILE_OUT");
        bytes32 it = keccak256(bytes(item));
        HolonHeaderHasher hh = new HolonHeaderHasher();
        if (it == keccak256("messenger")) deployMessenger();
        uint256 snap = XV.snapshotState();
        uint256 n = 0;
        for (;; n++) {
            uint256 fmp;
            assembly {
                fmp := mload(0x40)
            }
            bytes memory raw = XV.parseBytes(XV.readLine(inPath));
            if (raw.length == 0) break;
            if (it == keccak256("keccak_words")) keccakWords(n, raw);
            else if (it == keccak256("header_hash")) headerHash(hh, n, raw);
            else if (it == keccak256("submitter")) submitter(n, raw, snap);
            else if (it == keccak256("messenger")) messenger(n, raw);
            else revert("holon vacuity: unknown item");
            assembly {
                mstore(0x40, fmp)
            }
        }
        line(string.concat("done ", u(n)));
    }
}
