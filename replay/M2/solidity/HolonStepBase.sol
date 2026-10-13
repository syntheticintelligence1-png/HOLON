// SPDX-License-Identifier: MIT
// HOLON I20 generic step harness (holon/replay_fragments.py). It compares nothing: it runs steps on the real code and
// writes what the real code did, one record per line, for Python to compare with the extracted model.
//
// A concrete harness inherits HolonStepBase and implements holonDeploy (deploy the real target and its dependencies;
// return the target's address), and, when its traces hold abstract rows (an older model's action encoding), holonAbstract
// (translate a row into a call on the target, or say it is an environment step), holonAbstractEnv and holonAfter.
// It may also declare a last-step contract (setUp() { holonSetUpLast(); } test_last() { holonRunLast(); }) so that
// holon can locate a Panic's source line in a debugger dump of the last step alone.
//
// Input: the JSON file $HOLON_STEPS_IN:
//   {"lens": [n_0, n_1, ...]      steps of each trace, in order
//    "steps": ["0x..", ...]       every step of every trace, abi.encode(uint8 kind, bool fork, bytes payload):
//                                   kind 1  abstract row: payload = abi.encode(uint256[] row)
//                                   kind 2  call: payload = abi.encode(address caller, uint256 value, uint256 timestamp
//                                           (0: unchanged), bytes32[] blobhashes, address to (0: the target), bytes data)
//                                   kind 3  poked call: payload = abi.encode(bytes32[] slots, bytes32[] words, bytes call)
//                                           with call a kind 2 payload: the target's slots are set to the words
//                                           (vm.store) and then the call runs, as one step
//                                 a fork step runs from a snapshot of the state before it and is reverted afterwards
//    "slots": ["0x<32 bytes>", ..] storage slots of the target read with vm.load after every step (its layout's slots)
//    "init": [uint, ...]}         the deployment parameters, given to holonDeploy
// Traces [$HOLON_LO, $HOLON_HI) run, each from a fresh deployment. Output: lines appended to the file $HOLON_STEPS_OUT:
//   T <tid> <target> <harness>                     after the deployment
//   S <tid> <id> <call|env> <fork> <ok> <to> <caller> <value> <timestamp> <number> <blobs> <data> <ret>
//                                                  one per step (id d: the deployment); env steps write - for the call
//   K <tid> <code>                                 the target's runtime code, after the deployment
//   Q <tid> <impl> <code>                          when the target is an EIP-1967 proxy (its implementation slot is not
//                                                  zero): the implementation's address and runtime code (its immutables)
//   V <tid> <id> <chainid> <basefee> <prevrandao> <coinbase> <gaslimit> <blobbasefee> <origin> <gasprice>
//     <target balance> <caller balance>            the block and transaction environment of a call step, and the
//                                                  balances before it (the call's value not yet transferred)
//   P <tid> <id> <slot> <word>                      a poked call's vm.store, before its S line (0 for zero)
//   W <tid> <id> <slot> <value> <reverted>          every storage write to the target during the step, in order
//   L <tid> <id> <topics> <data>                    every log the target emitted (topics comma-separated, or -)
//   C <tid> <id> <to> <data> <ok> <ret>             every external call the target made, in order, with its answer:
//                                                  re-run in order from the state before the step, as the target
//   D <tid> <id> <v,v,...>                          vm.load of every slot of "slots" after the step (0 for zero)
//   X <tid> <id> <note>                            a note from the concrete harness
//   E <tid> <n>                                    end of a trace;  DONE <lo> <hi>  at the end
// Gas metering is paused: the harness records what the code does, not what it costs. A call step's caller is dealt
// the call's value only when its balance is below it (an EVM-level transfer failure is not the contract's behaviour).
pragma solidity =0.8.24;

import {Test} from "forge-std/Test.sol";

interface HolonStepVm {
    enum AccountAccessKind { Call, DelegateCall, CallCode, StaticCall, Create, SelfDestruct, Resume, Balance,
                             Extcodesize, Extcodehash, Extcodecopy }
    struct ChainInfo { uint256 forkId; uint256 chainId; }
    struct StorageAccess { address account; bytes32 slot; bool isWrite; bytes32 previousValue; bytes32 newValue;
                           bool reverted; }
    struct AccountAccess { ChainInfo chainInfo; AccountAccessKind kind; address account; address accessor;
                           bool initialized; uint256 oldBalance; uint256 newBalance; bytes deployedCode; uint256 value;
                           bytes data; bool reverted; StorageAccess[] storageAccesses; uint64 depth; }
    struct Log { bytes32[] topics; bytes data; address emitter; }
    function snapshotState() external returns (uint256);
    function revertToState(uint256) external returns (bool);
    function deleteStateSnapshot(uint256) external returns (bool);
    function startStateDiffRecording() external;
    function stopAndReturnStateDiff() external returns (AccountAccess[] memory);
    function recordLogs() external;
    function getRecordedLogs() external returns (Log[] memory);
    function prank(address) external;
    function deal(address, uint256) external;
    function warp(uint256) external;
    function blobhashes(bytes32[] calldata) external;
    function load(address, bytes32) external view returns (bytes32);
    function store(address, bytes32, bytes32) external;
    function pauseGasMetering() external;
    function readFile(string calldata) external view returns (string memory);
    function writeLine(string calldata, string calldata) external;
    function envString(string calldata) external view returns (string memory);
    function envUint(string calldata) external view returns (uint256);
    function parseJsonUintArray(string calldata, string calldata) external pure returns (uint256[] memory);
    function parseJsonBytesArray(string calldata, string calldata) external pure returns (bytes[] memory);
    function parseJsonBytes32Array(string calldata, string calldata) external pure returns (bytes32[] memory);
    function toString(bytes calldata) external pure returns (string memory);
    function toString(uint256) external pure returns (string memory);
}

abstract contract HolonStepBase is Test {
    HolonStepVm internal constant SV = HolonStepVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    /// bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1), the EIP-1967 implementation slot
    bytes32 internal constant EIP1967_IMPLEMENTATION = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    struct HolonCall {
        address caller;
        uint256 value;
        uint256 timestamp;
        bytes32[] blobs;
        address to;
        bytes data;
    }

    address internal holonTarget;
    string internal holonOut;
    bytes32[] internal holonSlots;
    bytes[] internal holonLastSteps;   // last-step mode: the single trace's steps
    uint256[2] internal holonBalances;  // the target's and the caller's balance before the current call

    /// Deploy the real target and its dependencies for trace tid; return the target's address.
    function holonDeploy(uint256 tid, uint256[] memory init) internal virtual returns (address);

    /// Translate an abstract row into a call on the target (isCall), or say it is an environment step.
    function holonAbstract(uint256, uint256[] memory) internal virtual returns (bool, HolonCall memory) {
        revert("HolonStepBase: this harness takes no abstract rows");
    }

    /// Run an abstract environment step (not a call on the target).
    function holonAbstractEnv(uint256, uint256, uint256[] memory) internal virtual {
        revert("HolonStepBase: this harness takes no abstract rows");
    }

    /// Bookkeeping after an abstract row's call ran (ok: whether it returned).
    function holonAfter(uint256, uint256, uint256[] memory, bool) internal virtual {}

    function holonLine(string memory s) internal {
        SV.writeLine(holonOut, s);
    }

    function hx(bytes memory b) internal pure returns (string memory) {
        return SV.toString(b);
    }

    function ha(address a) internal pure returns (string memory) {
        return SV.toString(abi.encodePacked(a));
    }

    function hw(bytes32 w) internal pure returns (string memory) {
        return w == bytes32(0) ? "0" : SV.toString(abi.encodePacked(w));
    }

    function dec(uint256 v) internal pure returns (string memory) {
        return SV.toString(v);
    }

    function sid(uint256 id) internal pure returns (string memory) {
        return id == type(uint256).max ? "d" : SV.toString(id);
    }

    function pre(uint256 tid, uint256 id) internal pure returns (string memory) {
        return string.concat(dec(tid), " ", sid(id), " ");
    }

    function holonWrites(uint256 tid, uint256 id, HolonStepVm.AccountAccess[] memory acc) internal {
        for (uint256 i = 0; i < acc.length; i++) {
            HolonStepVm.StorageAccess[] memory st = acc[i].storageAccesses;
            for (uint256 j = 0; j < st.length; j++) {
                if (st[j].account != holonTarget || !st[j].isWrite) continue;
                holonLine(string.concat("W ", pre(tid, id), SV.toString(abi.encodePacked(st[j].slot)), " ",
                                        SV.toString(abi.encodePacked(st[j].newValue)), st[j].reverted ? " 1" : " 0"));
            }
        }
    }

    function holonDump(uint256 tid, uint256 id) internal {
        string memory s = "";
        for (uint256 i = 0; i < holonSlots.length; i++) {
            s = string.concat(s, i == 0 ? "" : ",", hw(SV.load(holonTarget, holonSlots[i])));
        }
        holonLine(string.concat("D ", pre(tid, id), bytes(s).length == 0 ? "-" : s));
    }

    function holonLogs(uint256 tid, uint256 id, HolonStepVm.Log[] memory logs) internal {
        for (uint256 i = 0; i < logs.length; i++) {
            if (logs[i].emitter != holonTarget) continue;
            string memory t = "";
            for (uint256 j = 0; j < logs[i].topics.length; j++) {
                t = string.concat(t, j == 0 ? "" : ",", SV.toString(abi.encodePacked(logs[i].topics[j])));
            }
            holonLine(string.concat("L ", pre(tid, id), bytes(t).length == 0 ? "-" : t, " ", hx(logs[i].data)));
        }
    }

    function blobList(bytes32[] memory b) internal pure returns (string memory s) {
        if (b.length == 0) return "-";
        for (uint256 i = 0; i < b.length; i++) s = string.concat(s, i == 0 ? "" : ",", SV.toString(abi.encodePacked(b[i])));
    }

    /// External calls the target made during the step: answered again, in order, from the state before it, as the
    /// target.
    function holonAnswers(uint256 tid, uint256 id, uint256 snapPre, HolonStepVm.AccountAccess[] memory acc) internal {
        uint256 n = 0;
        for (uint256 i = 0; i < acc.length; i++) if (isExternal(acc[i])) n++;
        if (n == 0) return;
        uint256 snapPost = SV.snapshotState();
        SV.revertToState(snapPre);
        for (uint256 i = 0; i < acc.length; i++) {
            if (!isExternal(acc[i])) continue;
            SV.prank(holonTarget);
            (bool ok, bytes memory ret) = acc[i].account.call{value: acc[i].value}(acc[i].data);
            holonLine(string.concat("C ", pre(tid, id), ha(acc[i].account), " ", hx(acc[i].data), ok ? " 1 " : " 0 ", hx(ret)));
        }
        SV.revertToState(snapPost);
        SV.deleteStateSnapshot(snapPost);
    }

    function isExternal(HolonStepVm.AccountAccess memory a) internal view returns (bool) {
        return (a.kind == HolonStepVm.AccountAccessKind.Call || a.kind == HolonStepVm.AccountAccessKind.StaticCall
                || a.kind == HolonStepVm.AccountAccessKind.CallCode)
            && a.accessor == holonTarget && a.account != holonTarget && a.account != address(SV)
            && a.account != address(0x000000000000000000636F6e736F6c652e6c6f67);
    }

    function envLine(uint256 tid, uint256 id) internal {
        string memory b = string.concat(dec(block.chainid), " ", dec(block.basefee), " ", dec(block.prevrandao), " ",
                                        ha(block.coinbase), " ", dec(block.gaslimit), " ");
        string memory t = string.concat(dec(block.blobbasefee), " ", ha(tx.origin), " ", dec(tx.gasprice), " ",
                                        dec(holonBalances[0]), " ", dec(holonBalances[1]));
        holonLine(string.concat("V ", pre(tid, id), b, t));
    }

    /// Run one call and record it.
    function holonExec(uint256 tid, uint256 id, bool fork, HolonCall memory c) internal returns (bool ok, bytes memory ret) {
        if (c.timestamp != 0) SV.warp(c.timestamp);
        if (c.to == address(0)) c.to = holonTarget;
        if (c.value > c.caller.balance) SV.deal(c.caller, c.value);
        SV.blobhashes(c.blobs);
        holonBalances = [holonTarget.balance, c.caller.balance];
        uint256 snapPre = SV.snapshotState();
        SV.recordLogs();
        SV.startStateDiffRecording();
        if (c.caller != address(this)) SV.prank(c.caller);
        (ok, ret) = c.to.call{value: c.value}(c.data);
        HolonStepVm.AccountAccess[] memory acc = SV.stopAndReturnStateDiff();
        HolonStepVm.Log[] memory logs = SV.getRecordedLogs();
        holonLine(string.concat("S ", pre(tid, id), "call ", fork ? "1 " : "0 ", ok ? "1 " : "0 ", callHead(c),
                                callTail(c, ret)));
        envLine(tid, id);
        holonWrites(tid, id, acc);
        holonLogs(tid, id, logs);
        holonAnswers(tid, id, snapPre, acc);
        SV.deleteStateSnapshot(snapPre);
        holonDump(tid, id);
        bytes32[] memory none = new bytes32[](0);
        SV.blobhashes(none);
    }

    function callHead(HolonCall memory c) internal view returns (string memory) {
        return string.concat(ha(c.to), " ", ha(c.caller), " ", dec(c.value), " ", dec(block.timestamp), " ",
                             dec(block.number), " ");
    }

    function callTail(HolonCall memory c, bytes memory ret) internal pure returns (string memory) {
        return string.concat(blobList(c.blobs), " ", hx(c.data), " ", hx(ret));
    }

    function envRecord(uint256 tid, uint256 id, bool fork, HolonStepVm.AccountAccess[] memory acc) internal {
        holonLine(string.concat("S ", pre(tid, id), "env ", fork ? "1 " : "0 ", "1 - - 0 ", dec(block.timestamp), " ",
                                dec(block.number), " - 0x 0x"));
        holonWrites(tid, id, acc);
        holonDump(tid, id);
    }

    function holonStep(uint256 tid, uint256 id, bytes memory raw) internal {
        (uint8 kind, bool fork, bytes memory payload) = abi.decode(raw, (uint8, bool, bytes));
        uint256 snap = fork ? SV.snapshotState() : 0;
        if (kind == 1) {
            uint256[] memory row = abi.decode(payload, (uint256[]));
            (bool isCall, HolonCall memory c) = holonAbstract(tid, row);
            if (isCall) {
                (bool ok,) = holonExec(tid, id, fork, c);
                holonAfter(tid, id, row, ok);
            } else {
                SV.startStateDiffRecording();
                holonAbstractEnv(tid, id, row);
                envRecord(tid, id, fork, SV.stopAndReturnStateDiff());
            }
        } else if (kind == 2) {
            holonExec(tid, id, fork, holonDecodeCall(payload));
        } else if (kind == 3) {
            holonExec(tid, id, fork, holonPoke(tid, id, payload, true));
        } else {
            revert("HolonStepBase: unknown step kind");
        }
        if (fork) {
            SV.revertToState(snap);
            SV.deleteStateSnapshot(snap);
        }
    }

    function holonDecodeCall(bytes memory payload) internal pure returns (HolonCall memory c) {
        (c.caller, c.value, c.timestamp, c.blobs, c.to, c.data) =
            abi.decode(payload, (address, uint256, uint256, bytes32[], address, bytes));
    }

    /// A poked call (kind 3): set the target's slots (vm.store; one P line each when recorded), then return the call.
    function holonPoke(uint256 tid, uint256 id, bytes memory payload, bool record) internal returns (HolonCall memory) {
        (bytes32[] memory ps, bytes32[] memory ws, bytes memory cp) = abi.decode(payload, (bytes32[], bytes32[], bytes));
        require(ps.length == ws.length, "HolonStepBase: a poke needs one word per slot");
        for (uint256 i = 0; i < ps.length; i++) {
            SV.store(holonTarget, ps[i], ws[i]);
            if (record) holonLine(string.concat("P ", pre(tid, id), hw(ps[i]), " ", hw(ws[i])));
        }
        return holonDecodeCall(cp);
    }

    function holonLoad() internal returns (uint256[] memory lens, bytes[] memory steps, uint256[] memory init) {
        string memory js = SV.readFile(SV.envString("HOLON_STEPS_IN"));
        holonOut = SV.envString("HOLON_STEPS_OUT");
        lens = SV.parseJsonUintArray(js, ".lens");
        steps = SV.parseJsonBytesArray(js, ".steps");
        bytes32[] memory slots = SV.parseJsonBytes32Array(js, ".slots");
        init = SV.parseJsonUintArray(js, ".init");
        for (uint256 i = 0; i < slots.length; i++) holonSlots.push(slots[i]);
    }

    function holonBegin(uint256 tid, uint256[] memory init) internal {
        SV.startStateDiffRecording();
        address target = holonDeploy(tid, init);
        HolonStepVm.AccountAccess[] memory acc = SV.stopAndReturnStateDiff();
        holonTarget = target;
        holonLine(string.concat("T ", dec(tid), " ", ha(target), " ", ha(address(this))));
        holonLine(string.concat("K ", dec(tid), " ", hx(target.code)));
        address impl = address(uint160(uint256(SV.load(target, EIP1967_IMPLEMENTATION))));
        if (impl != address(0)) holonLine(string.concat("Q ", dec(tid), " ", ha(impl), " ", hx(impl.code)));
        envRecord(tid, type(uint256).max, false, acc);
    }

    function test_steps() public {
        SV.pauseGasMetering();
        (uint256[] memory lens, bytes[] memory steps, uint256[] memory init) = holonLoad();
        uint256 lo = SV.envUint("HOLON_LO");
        uint256 hi = SV.envUint("HOLON_HI");
        uint256 p = 0;
        for (uint256 tid = 0; tid < lens.length && tid < hi; tid++) {
            if (tid < lo) {
                p += lens[tid];
                continue;
            }
            uint256 snap0 = SV.snapshotState();
            holonBegin(tid, init);
            for (uint256 si = 0; si < lens[tid]; si++) holonStep(tid, si, steps[p + si]);
            p += lens[tid];
            holonLine(string.concat("E ", dec(tid), " ", dec(lens[tid])));
            SV.revertToState(snap0);
            SV.deleteStateSnapshot(snap0);
        }
        holonLine(string.concat("DONE ", dec(lo), " ", dec(hi)));
    }

    /// Last-step mode: $HOLON_STEPS_IN holds one trace; the deployment and every step but the last run here (setUp).
    function holonSetUpLast() internal {
        SV.pauseGasMetering();
        (uint256[] memory lens, bytes[] memory steps, uint256[] memory init) = holonLoad();
        require(lens.length == 1 && lens[0] >= 1 && steps.length == lens[0], "HolonStepBase: one trace expected");
        holonBegin(0, init);
        for (uint256 si = 0; si + 1 < steps.length; si++) holonStep(0, si, steps[si]);
        holonLastSteps.push(steps[steps.length - 1]);
    }

    /// Last-step mode: the last step alone, unrecorded (a debugger dump of this test holds its execution only, so the
    /// first frame that reverts with a Panic is the step's).
    function holonRunLast() internal {
        SV.pauseGasMetering();
        (uint8 kind,, bytes memory payload) = abi.decode(holonLastSteps[0], (uint8, bool, bytes));
        HolonCall memory c;
        if (kind == 1) {
            bool isCall;
            (isCall, c) = holonAbstract(0, abi.decode(payload, (uint256[])));
            require(isCall, "HolonStepBase: the last step is not a call");
        } else if (kind == 3) {
            c = holonPoke(0, 0, payload, false);
        } else {
            c = holonDecodeCall(payload);
        }
        if (c.timestamp != 0) SV.warp(c.timestamp);
        if (c.to == address(0)) c.to = holonTarget;
        if (c.value > c.caller.balance) SV.deal(c.caller, c.value);
        SV.blobhashes(c.blobs);
        if (c.caller != address(this)) SV.prank(c.caller);
        (bool ok,) = c.to.call{value: c.value}(c.data);
        ok;
    }
}
