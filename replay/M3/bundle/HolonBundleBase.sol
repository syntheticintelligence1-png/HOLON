// SPDX-License-Identifier: MIT
// HOLON I69 generic multi-target step harness (holon/bundle/harness.py; rules C1-C2 of the I69 contract). I20's
// HolonStepBase (replay/M2/solidity/HolonStepBase.sol) generalized from one target to the members of a bundle: it
// compares nothing; it runs steps on the real code and writes what the code did, one record per line.
//
// A concrete harness inherits HolonBundleBase and implements holonDeploy (deploy the real members; return their
// addresses in the bundle's member order) and, when its traces hold abstract rows, holonAbstract, holonAbstractEnv and
// holonAfter.
//
// Input: the JSON file $HOLON_STEPS_IN:
//   {"lens": [n_0, ...]   steps of each trace
//    "steps": ["0x..", ...] every step, abi.encode(uint8 kind, bytes payload):
//        kind 1  abstract row: payload = abi.encode(uint256[] row)
//        kind 2  call: payload = abi.encode(address caller, uint256 value, uint256 warp, address to, bytes data)
//                (warp: seconds added to the block time before the call; 0 none)
//        kind 3  poked call: payload = abi.encode(address account, bytes32[] slots, bytes32[] words, bytes call):
//                the account's slots are set (vm.store), then the kind 2 call runs, as one step
//    "watch": ["0x<address>", ...]  addresses whose balances are recorded before every call step
//    "init": [uint, ...]}  the deployment parameters
// Traces [$HOLON_LO, $HOLON_HI) run, each from a fresh deployment. Output lines (to $HOLON_STEPS_OUT):
//   T <tid> <member index> <address> <implementation or 0>     after the deployment, one per member
//   K <tid> <address> <code length>                            every member, implementation and watched address
//   Q <tid> <member index> <code>                              (trace 0) the runtime code the member runs: its
//                                                              implementation's behind a proxy (its immutables)
//   S <tid> <id> <call|env> <ok> <to> <caller> <value> <timestamp> <number> <data> <ret>
//   V <tid> <id> <chainid> <basefee> <prevrandao> <coinbase> <gaslimit> <origin> <gasprice>
//   A <tid> <id> <address> <balance>                           before a call step: every member and watched address
//   P <tid> <id> <account> <slot> <word>                       a poke, before its S line
//   W <tid> <id> <member index> <slot> <value> <reverted>      every storage write to a member during the step
//   L <tid> <id> <member index> <topics> <data>                every log a member emitted, in order
//   F <tid> <id> <parent> <caller> <member index> <selector> <value> <reverted>   every frame on a member
//   O <tid> <id> <member index> <to> <value> <data> <reverted> <ok> <ret>         every call a member made to a
//                                                              non-member, with its answer re-run from the state
//                                                              before the step, as that member
//   B <tid> <id> <member index> <balance>                      every member's balance after the step
//   E <tid> <n>  end of a trace;  DONE <lo> <hi>  at the end
// (id d: the deployment.) Gas metering is paused.
pragma solidity =0.8.24;

import {Test} from "forge-std/Test.sol";

interface HolonBundleVm {
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
    function load(address, bytes32) external view returns (bytes32);
    function store(address, bytes32, bytes32) external;
    function pauseGasMetering() external;
    function readFile(string calldata) external view returns (string memory);
    function writeLine(string calldata, string calldata) external;
    function envString(string calldata) external view returns (string memory);
    function envUint(string calldata) external view returns (uint256);
    function parseJsonUintArray(string calldata, string calldata) external pure returns (uint256[] memory);
    function parseJsonBytesArray(string calldata, string calldata) external pure returns (bytes[] memory);
    function parseJsonAddressArray(string calldata, string calldata) external pure returns (address[] memory);
    function toString(bytes calldata) external pure returns (string memory);
    function toString(uint256) external pure returns (string memory);
}

abstract contract HolonBundleBase is Test {
    HolonBundleVm internal constant BV = HolonBundleVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    bytes32 internal constant EIP1967_IMPLEMENTATION = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    struct HolonCall {
        address caller;
        uint256 value;
        uint256 warp;
        address to;
        bytes data;
    }

    address[] internal members;
    address[] internal watched;
    string internal holonOut;

    function holonDeploy(uint256 tid, uint256[] memory init) internal virtual returns (address[] memory);

    function holonAbstract(uint256, uint256, uint256[] memory) internal virtual returns (bool, HolonCall memory) {
        revert("HolonBundleBase: this harness takes no abstract rows");
    }

    function holonAbstractEnv(uint256, uint256, uint256[] memory) internal virtual {
        revert("HolonBundleBase: this harness takes no abstract rows");
    }

    function holonAfter(uint256, uint256, uint256[] memory, bool) internal virtual {}

    function holonLine(string memory s) internal {
        BV.writeLine(holonOut, s);
    }

    function hx(bytes memory b) internal pure returns (string memory) {
        return BV.toString(b);
    }

    function ha(address a) internal pure returns (string memory) {
        return BV.toString(abi.encodePacked(a));
    }

    function hw(bytes32 w) internal pure returns (string memory) {
        return BV.toString(abi.encodePacked(w));
    }

    function dec(uint256 v) internal pure returns (string memory) {
        return BV.toString(v);
    }

    function pre(uint256 tid, uint256 id) internal pure returns (string memory) {
        return string.concat(dec(tid), " ", id == type(uint256).max ? "d" : dec(id), " ");
    }

    function memberIndex(address a) internal view returns (uint256) {
        for (uint256 i = 0; i < members.length; i++) if (members[i] == a) return i;
        return type(uint256).max;
    }

    function isMember(address a) internal view returns (bool) {
        return memberIndex(a) != type(uint256).max;
    }

    function holonWrites(uint256 tid, uint256 id, HolonBundleVm.AccountAccess[] memory acc) internal {
        for (uint256 i = 0; i < acc.length; i++) {
            HolonBundleVm.StorageAccess[] memory st = acc[i].storageAccesses;
            for (uint256 j = 0; j < st.length; j++) {
                if (!st[j].isWrite || !isMember(st[j].account)) continue;
                holonLine(string.concat("W ", pre(tid, id), dec(memberIndex(st[j].account)), " ", hw(st[j].slot), " ",
                                        hw(st[j].newValue), st[j].reverted ? " 1" : " 0"));
            }
        }
    }

    function holonLogs(uint256 tid, uint256 id, HolonBundleVm.Log[] memory logs) internal {
        for (uint256 i = 0; i < logs.length; i++) {
            if (!isMember(logs[i].emitter)) continue;
            string memory t = "";
            for (uint256 j = 0; j < logs[i].topics.length; j++) {
                t = string.concat(t, j == 0 ? "" : ",", hw(logs[i].topics[j]));
            }
            holonLine(string.concat("L ", pre(tid, id), dec(memberIndex(logs[i].emitter)), " ",
                                    bytes(t).length == 0 ? "-" : t, " ", hx(logs[i].data)));
        }
    }

    function isCall(HolonBundleVm.AccountAccess memory a) internal pure returns (bool) {
        return a.kind == HolonBundleVm.AccountAccessKind.Call || a.kind == HolonBundleVm.AccountAccessKind.StaticCall
            || a.kind == HolonBundleVm.AccountAccessKind.CallCode;
    }

    function selectorOf(bytes memory data) internal pure returns (string memory) {
        if (data.length < 4) return data.length == 0 ? "0x" : hx(data);
        bytes memory s = new bytes(4);
        for (uint256 i = 0; i < 4; i++) s[i] = data[i];
        return hx(s);
    }

    /// Every frame on a member, in the order frames begin: its parent (the nearest enclosing member frame, -1 none),
    /// its caller, the member, the selector, the value and whether forge marks it reverted.
    function holonFrames(uint256 tid, uint256 id, HolonBundleVm.AccountAccess[] memory acc) internal {
        uint256[] memory stackDepth = new uint256[](acc.length + 1);
        uint256[] memory stackIdx = new uint256[](acc.length + 1);
        uint256 sp = 0;
        uint256 n = 0;
        for (uint256 i = 0; i < acc.length; i++) {
            if (!isCall(acc[i]) || !isMember(acc[i].account)) continue;
            while (sp > 0 && stackDepth[sp - 1] >= acc[i].depth) sp--;
            string memory parent = sp == 0 ? "-1" : dec(stackIdx[sp - 1]);
            holonLine(string.concat("F ", pre(tid, id), parent, " ", ha(acc[i].accessor), " ",
                                    dec(memberIndex(acc[i].account)), " ", selectorOf(acc[i].data), " ",
                                    dec(acc[i].value), acc[i].reverted ? " 1" : " 0"));
            stackDepth[sp] = acc[i].depth;
            stackIdx[sp] = n;
            sp++;
            n++;
        }
    }

    /// Calls a member made to a non-member: answered again, in order, from the state before the step, as the member.
    function holonOutgoing(uint256 tid, uint256 id, uint256 snapPre, HolonBundleVm.AccountAccess[] memory acc) internal {
        uint256 k = 0;
        for (uint256 i = 0; i < acc.length; i++) if (isOutgoing(acc[i])) k++;
        if (k == 0) return;
        uint256 snapPost = BV.snapshotState();
        BV.revertToState(snapPre);
        for (uint256 i = 0; i < acc.length; i++) {
            if (!isOutgoing(acc[i])) continue;
            if (acc[i].value > acc[i].accessor.balance) BV.deal(acc[i].accessor, acc[i].value);
            BV.prank(acc[i].accessor);
            (bool ok, bytes memory ret) = acc[i].account.call{value: acc[i].value}(acc[i].data);
            holonLine(string.concat("O ", pre(tid, id), dec(memberIndex(acc[i].accessor)), " ", ha(acc[i].account), " ",
                                    dec(acc[i].value), " ", hx(acc[i].data), acc[i].reverted ? " 1" : " 0",
                                    ok ? " 1 " : " 0 ", hx(ret)));
        }
        BV.revertToState(snapPost);
        BV.deleteStateSnapshot(snapPost);
    }

    function isOutgoing(HolonBundleVm.AccountAccess memory a) internal view returns (bool) {
        return isCall(a) && isMember(a.accessor) && !isMember(a.account) && a.account != address(BV)
            && a.account != CONSOLE;
    }

    function holonBalances(uint256 tid, uint256 id) internal {
        for (uint256 i = 0; i < members.length; i++) {
            holonLine(string.concat("B ", pre(tid, id), dec(i), " ", dec(members[i].balance)));
        }
    }

    function holonBefore(uint256 tid, uint256 id, address caller) internal {
        for (uint256 i = 0; i < members.length; i++) {
            holonLine(string.concat("A ", pre(tid, id), ha(members[i]), " ", dec(members[i].balance)));
        }
        for (uint256 i = 0; i < watched.length; i++) {
            holonLine(string.concat("A ", pre(tid, id), ha(watched[i]), " ", dec(watched[i].balance)));
        }
        if (!isMember(caller)) holonLine(string.concat("A ", pre(tid, id), ha(caller), " ", dec(caller.balance)));
    }

    function envLine(uint256 tid, uint256 id) internal {
        holonLine(string.concat("V ", pre(tid, id), dec(block.chainid), " ", dec(block.basefee), " ",
                                dec(block.prevrandao), " ", ha(block.coinbase), " ", dec(block.gaslimit), " ",
                                ha(tx.origin), " ", dec(tx.gasprice)));
    }

    function holonExec(uint256 tid, uint256 id, HolonCall memory c) internal returns (bool ok, bytes memory ret) {
        if (c.warp != 0) BV.warp(block.timestamp + c.warp);
        if (c.value > c.caller.balance) BV.deal(c.caller, c.value);
        holonBefore(tid, id, c.caller);
        uint256 snapPre = BV.snapshotState();
        BV.recordLogs();
        BV.startStateDiffRecording();
        if (c.caller != address(this)) BV.prank(c.caller);
        (ok, ret) = c.to.call{value: c.value}(c.data);
        HolonBundleVm.AccountAccess[] memory acc = BV.stopAndReturnStateDiff();
        HolonBundleVm.Log[] memory logs = BV.getRecordedLogs();
        holonLine(string.concat("S ", pre(tid, id), "call ", ok ? "1 " : "0 ", ha(c.to), " ", ha(c.caller), " ",
                                dec(c.value), " ", dec(block.timestamp), " ", dec(block.number), " ", hx(c.data), " ",
                                hx(ret)));
        envLine(tid, id);
        holonFrames(tid, id, acc);
        holonWrites(tid, id, acc);
        holonLogs(tid, id, logs);
        holonOutgoing(tid, id, snapPre, acc);
        BV.deleteStateSnapshot(snapPre);
        holonBalances(tid, id);
    }

    function envRecord(uint256 tid, uint256 id, HolonBundleVm.AccountAccess[] memory acc) internal {
        holonLine(string.concat("S ", pre(tid, id), "env 1 - - 0 ", dec(block.timestamp), " ", dec(block.number),
                                " 0x 0x"));
        holonWrites(tid, id, acc);
        holonBalances(tid, id);
    }

    function holonDecodeCall(bytes memory payload) internal pure returns (HolonCall memory c) {
        (c.caller, c.value, c.warp, c.to, c.data) = abi.decode(payload, (address, uint256, uint256, address, bytes));
    }

    function holonStep(uint256 tid, uint256 id, bytes memory raw) internal {
        (uint8 kind, bytes memory payload) = abi.decode(raw, (uint8, bytes));
        if (kind == 1) {
            uint256[] memory row = abi.decode(payload, (uint256[]));
            (bool isCallStep, HolonCall memory c) = holonAbstract(tid, id, row);
            if (isCallStep) {
                (bool ok,) = holonExec(tid, id, c);
                holonAfter(tid, id, row, ok);
            } else {
                BV.startStateDiffRecording();
                holonAbstractEnv(tid, id, row);
                envRecord(tid, id, BV.stopAndReturnStateDiff());
            }
        } else if (kind == 2) {
            holonExec(tid, id, holonDecodeCall(payload));
        } else if (kind == 3) {
            (address account, bytes32[] memory ps, bytes32[] memory ws, bytes memory cp) =
                abi.decode(payload, (address, bytes32[], bytes32[], bytes));
            require(ps.length == ws.length, "HolonBundleBase: a poke needs one word per slot");
            for (uint256 i = 0; i < ps.length; i++) {
                BV.store(account, ps[i], ws[i]);
                holonLine(string.concat("P ", pre(tid, id), ha(account), " ", hw(ps[i]), " ", hw(ws[i])));
            }
            holonExec(tid, id, holonDecodeCall(cp));
        } else {
            revert("HolonBundleBase: unknown step kind");
        }
    }

    function holonBegin(uint256 tid, uint256[] memory init) internal {
        BV.startStateDiffRecording();
        address[] memory ms = holonDeploy(tid, init);
        HolonBundleVm.AccountAccess[] memory acc = BV.stopAndReturnStateDiff();
        delete members;
        for (uint256 i = 0; i < ms.length; i++) members.push(ms[i]);
        for (uint256 i = 0; i < ms.length; i++) {
            address impl = address(uint160(uint256(BV.load(ms[i], EIP1967_IMPLEMENTATION))));
            holonLine(string.concat("T ", dec(tid), " ", dec(i), " ", ha(ms[i]), " ", ha(impl)));
            holonLine(string.concat("K ", dec(tid), " ", ha(ms[i]), " ", dec(ms[i].code.length)));
            if (impl != address(0)) holonLine(string.concat("K ", dec(tid), " ", ha(impl), " ", dec(impl.code.length)));
            address runs = impl != address(0) ? impl : ms[i];
            if (tid == 0) holonLine(string.concat("Q ", dec(tid), " ", dec(i), " ", hx(runs.code)));
        }
        for (uint256 i = 0; i < watched.length; i++) {
            holonLine(string.concat("K ", dec(tid), " ", ha(watched[i]), " ", dec(watched[i].code.length)));
        }
        envRecord(tid, type(uint256).max, acc);
    }

    function test_steps() public {
        BV.pauseGasMetering();
        string memory js = BV.readFile(BV.envString("HOLON_STEPS_IN"));
        holonOut = BV.envString("HOLON_STEPS_OUT");
        uint256[] memory lens = BV.parseJsonUintArray(js, ".lens");
        bytes[] memory steps = BV.parseJsonBytesArray(js, ".steps");
        uint256[] memory init = BV.parseJsonUintArray(js, ".init");
        address[] memory w = BV.parseJsonAddressArray(js, ".watch");
        for (uint256 i = 0; i < w.length; i++) watched.push(w[i]);
        uint256 lo = BV.envUint("HOLON_LO");
        uint256 hi = BV.envUint("HOLON_HI");
        uint256 p = 0;
        for (uint256 tid = 0; tid < lens.length && tid < hi; tid++) {
            if (tid < lo) {
                p += lens[tid];
                continue;
            }
            uint256 snap0 = BV.snapshotState();
            holonBegin(tid, init);
            for (uint256 si = 0; si < lens[tid]; si++) holonStep(tid, si, steps[p + si]);
            p += lens[tid];
            holonLine(string.concat("E ", dec(tid), " ", dec(lens[tid])));
            BV.revertToState(snap0);
            BV.deleteStateSnapshot(snap0);
        }
        holonLine(string.concat("DONE ", dec(lo), " ", dec(hi)));
    }
}
